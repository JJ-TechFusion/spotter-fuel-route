"""Cheapest refuelling plan along a fixed route.

Dynamic programming over the stations on the route, solved backwards from the
destination. At each stop the vehicle buys exactly the fuel for the leg to its
next stop (at most one tank). Each stop also carries a small fixed overhead, so
the plan doesn't detour into a stop just to save a few cents.

The tank starts empty: the first stop is the first station on the route or any
other within `start_window_miles` of the start, and the fuel used to get there
is charged at that station's price, so the total covers the whole trip.
"""

from bisect import bisect_right

import numpy as np

from .entities import FuelStop, StationOnRoute
from .errors import NoFeasiblePlan


def plan_fuel_stops(
    stations: list[StationOnRoute],
    total_miles: float,
    range_miles: float,
    mpg: float,
    stop_overhead: float = 0.0,
    start_window_miles: float = 0.0,
) -> list[FuelStop]:
    if total_miles <= 0:
        return []
    stations = sorted((s for s in stations if s.mile <= total_miles), key=lambda s: s.mile)
    if not stations:
        raise NoFeasiblePlan("No fuel stations along this route.")

    miles = np.array([s.mile for s in stations])
    price_per_mile = np.array([s.station.price for s in stations]) / mpg
    n = len(stations)

    # best[j]: cheapest cost from station j to the destination; nxt[j]: the stop after j (n = destination).
    best = np.full(n, np.inf)
    nxt = np.full(n, -1)
    for j in range(n - 1, -1, -1):
        if total_miles - miles[j] <= range_miles:
            best[j], nxt[j] = price_per_mile[j] * (total_miles - miles[j]), n
        end = bisect_right(miles, miles[j] + range_miles)
        if end > j + 1:
            options = price_per_mile[j] * (miles[j + 1 : end] - miles[j]) + stop_overhead + best[j + 1 : end]
            k = int(np.argmin(options))
            if options[k] < best[j]:
                best[j], nxt[j] = options[k], j + 1 + k

    first_choices = np.arange(bisect_right(miles, max(start_window_miles, miles[0])))
    first_choices = first_choices[miles[first_choices] <= range_miles]
    start_costs = price_per_mile[first_choices] * miles[first_choices] + best[first_choices]
    if len(first_choices) == 0 or not np.isfinite(start_costs.min()):
        raise NoFeasiblePlan(_gap_message(miles, total_miles, range_miles))

    stops = []
    j = int(first_choices[np.argmin(start_costs)])
    leg_start = 0.0  # the first purchase also covers the drive from the start
    while j != n:
        k = int(nxt[j])
        leg_end = total_miles if k == n else miles[k]
        gallons = (leg_end - leg_start) / mpg
        station = stations[j]
        stops.append(FuelStop(station=station.station, mile=station.mile, gallons=gallons, cost=gallons * station.station.price))
        leg_start, j = leg_end, k
    return stops


def _gap_message(miles, total_miles: float, range_miles: float) -> str:
    points = [0.0, *miles.tolist(), total_miles]
    for a, b in zip(points, points[1:]):
        if b - a > range_miles:
            return f"No fuel station between mile {a:.0f} and mile {b:.0f}; that exceeds the {range_miles:.0f}-mile range."
    return "No feasible refuelling plan for this route."
