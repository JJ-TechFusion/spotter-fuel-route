"""Use case: plan the cheapest fuel stops for a trip between two US locations."""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace

from django.conf import settings
from django.core.cache import cache

from fuel.domain.entities import Coordinate, Route, Station, TripPlan
from fuel.domain.errors import InvalidLocation
from fuel.domain.geo import stations_along_route, thin_points
from fuel.domain.optimizer import plan_fuel_stops
from fuel.infrastructure import repositories
from fuel.infrastructure.osrm import OsrmRouter

# Contiguous USA, with a small margin. The fuel data covers no other part of the country.
_USA_BOUNDS = {"south": 24.0, "north": 49.5, "west": -125.0, "east": -66.5}
_LAT_LON = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
_CITY_STATE = re.compile(r"^\s*(.+?)\s*,\s*([A-Za-z]{2})\s*$")
ROUTE_SPACING_MILES = 0.5  # route detail kept for matching and for the response


def parse_location(text: str) -> Coordinate:
    """Accepts 'City, ST' (e.g. 'Dallas, TX') or 'lat,lon' (e.g. '32.77,-96.79')."""
    if match := _LAT_LON.match(text):
        point = Coordinate(float(match[1]), float(match[2]))
    elif match := _CITY_STATE.match(text):
        point = repositories.find_city(match[1], match[2])
        if point is None:
            raise InvalidLocation(f"Unknown US city: '{text}'.")
    else:
        raise InvalidLocation(f"Use 'City, ST' or 'lat,lon', got '{text}'.")

    b = _USA_BOUNDS
    if not (b["south"] <= point.lat <= b["north"] and b["west"] <= point.lon <= b["east"]):
        raise InvalidLocation(f"'{text}' is outside the contiguous USA.")
    return point


@dataclass
class TripPlanner:
    route: Callable[[Coordinate, Coordinate], Route]
    find_stations: Callable[[float, float, float, float], list[Station]]
    range_miles: float
    mpg: float
    corridor_miles: float
    stop_overhead: float

    def plan(self, start: Coordinate, finish: Coordinate) -> TripPlan:
        route = self.route(start, finish)
        route = replace(route, points=thin_points(route.points, ROUTE_SPACING_MILES))

        margin = self.corridor_miles / 50  # degrees; generous on purpose, the exact filter runs next
        candidates = self.find_stations(
            min(p.lat for p in route.points) - margin,
            min(p.lon for p in route.points) - margin,
            max(p.lat for p in route.points) + margin,
            max(p.lon for p in route.points) + margin,
        )
        on_route = stations_along_route(route, candidates, self.corridor_miles)
        stops = plan_fuel_stops(
            on_route,
            route.distance_miles,
            self.range_miles,
            self.mpg,
            stop_overhead=self.stop_overhead,
            start_window_miles=self.corridor_miles,
        )
        return TripPlan(
            start=start,
            finish=finish,
            route=route,
            stops=stops,
            total_gallons=sum(s.gallons for s in stops),
            total_cost=sum(s.cost for s in stops),
        )


def default_planner() -> TripPlanner:
    router = OsrmRouter(settings.OSRM_BASE_URL, settings.OSRM_TIMEOUT_SECONDS)
    return TripPlanner(
        route=router.route,
        find_stations=repositories.stations_in_box,
        range_miles=settings.VEHICLE_RANGE_MILES,
        mpg=settings.VEHICLE_MPG,
        corridor_miles=settings.STATION_CORRIDOR_MILES,
        stop_overhead=settings.FUEL_STOP_OVERHEAD_USD,
    )


def plan_trip(start_text: str, finish_text: str, planner: TripPlanner | None = None) -> TripPlan:
    start, finish = parse_location(start_text), parse_location(finish_text)
    key = f"trip:{start.lat:.4f},{start.lon:.4f}:{finish.lat:.4f},{finish.lon:.4f}"
    plan = cache.get(key)
    if plan is None:
        plan = (planner or default_planner()).plan(start, finish)
        cache.set(key, plan)
    return plan
