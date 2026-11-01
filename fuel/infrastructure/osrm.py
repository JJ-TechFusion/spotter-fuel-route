"""Client for OSRM (https://project-osrm.org), a free routing API. One HTTP call per route."""

import requests

from fuel.domain.entities import Coordinate, Route
from fuel.domain.errors import RouteNotFound, RoutingServiceError

METERS_PER_MILE = 1609.344


class OsrmRouter:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def route(self, start: Coordinate, finish: Coordinate) -> Route:
        url = f"{self.base_url}/route/v1/driving/{start.lon},{start.lat};{finish.lon},{finish.lat}"
        params = {"overview": "full", "geometries": "geojson", "alternatives": "false", "steps": "false"}
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RoutingServiceError("Routing service is unavailable.") from exc

        if response.status_code >= 500:
            raise RoutingServiceError("Routing service is unavailable.")
        if data.get("code") != "Ok" or not data.get("routes"):
            raise RouteNotFound(data.get("message") or "No drivable route between these locations.")

        best = data["routes"][0]
        return Route(
            distance_miles=best["distance"] / METERS_PER_MILE,
            duration_seconds=best["duration"],
            points=[Coordinate(lat=lat, lon=lon) for lon, lat in best["geometry"]["coordinates"]],
        )
