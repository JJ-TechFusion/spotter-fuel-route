"""Geometry helpers: route distances and matching stations to a route.

Uses a local flat-earth approximation per route segment, which is accurate
to well under a mile at the distances involved here.
"""

import math

import numpy as np

from .entities import Coordinate, Route, Station, StationOnRoute

EARTH_RADIUS_MILES = 3958.8
MILES_PER_DEGREE = math.pi * EARTH_RADIUS_MILES / 180
_CHUNK = 128  # stations per vectorised batch; bounds memory on long routes


def haversine_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def thin_points(points: list[Coordinate], min_spacing_miles: float) -> list[Coordinate]:
    """Drop vertices closer than `min_spacing_miles` to the previous kept one."""
    if len(points) < 3:
        return list(points)
    kept = [points[0]]
    for point in points[1:-1]:
        if haversine_miles(kept[-1].lat, kept[-1].lon, point.lat, point.lon) >= min_spacing_miles:
            kept.append(point)
    kept.append(points[-1])
    return kept


def stations_along_route(route: Route, stations: list[Station], max_offset_miles: float) -> list[StationOnRoute]:
    """Stations within `max_offset_miles` of the route, with their mile marker along it."""
    if not stations or len(route.points) < 2:
        return []
    lats = np.array([p.lat for p in route.points])
    lons = np.array([p.lon for p in route.points])
    seg_miles = haversine_miles(lats[:-1], lons[:-1], lats[1:], lons[1:])
    cum_miles = np.concatenate([[0.0], np.cumsum(seg_miles)])
    # Scale to the router's own distance so mile markers line up with route.distance_miles.
    if cum_miles[-1] > 0:
        cum_miles *= route.distance_miles / cum_miles[-1]
        seg_miles = np.diff(cum_miles)

    nearby = _near_route_cells(lats, lons, stations, max_offset_miles)
    if not nearby:
        return []
    s_lats = np.array([s.location.lat for s in nearby])
    s_lons = np.array([s.location.lon for s in nearby])

    result = []
    for start in range(0, len(nearby), _CHUNK):
        miles, offsets = _project(lats, lons, cum_miles, seg_miles, s_lats[start : start + _CHUNK], s_lons[start : start + _CHUNK])
        for station, mile, offset in zip(nearby[start : start + _CHUNK], miles, offsets):
            if offset <= max_offset_miles:
                result.append(StationOnRoute(station=station, mile=float(mile)))
    return result


def _project(lats, lons, cum_miles, seg_miles, p_lats, p_lons):
    """Nearest point on the route polyline for each station: (mile marker, offset in miles)."""
    lon_scale = np.cos(np.radians((lats[:-1] + lats[1:]) / 2)) * MILES_PER_DEGREE
    seg_x = (lons[1:] - lons[:-1]) * lon_scale
    seg_y = (lats[1:] - lats[:-1]) * MILES_PER_DEGREE
    seg_len2 = np.maximum(seg_x**2 + seg_y**2, 1e-12)

    px = (p_lons[:, None] - lons[None, :-1]) * lon_scale
    py = (p_lats[:, None] - lats[None, :-1]) * MILES_PER_DEGREE
    t = np.clip((px * seg_x + py * seg_y) / seg_len2, 0.0, 1.0)
    dist2 = (px - t * seg_x) ** 2 + (py - t * seg_y) ** 2

    nearest = np.argmin(dist2, axis=1)
    rows = np.arange(len(p_lats))
    miles = cum_miles[nearest] + t[rows, nearest] * seg_miles[nearest]
    return miles, np.sqrt(dist2[rows, nearest])


def _near_route_cells(lats, lons, stations: list[Station], radius_miles: float) -> list[Station]:
    """Cheap pre-filter: keep stations in or next to a grid cell the route passes through.

    Cells are at least `radius_miles` wide, so nothing within the radius is dropped.
    """
    lat_step = radius_miles / MILES_PER_DEGREE
    lon_step = radius_miles / (MILES_PER_DEGREE * math.cos(math.radians(np.abs(lats).max())))

    # Sample the route every half radius so long straight segments don't skip cells.
    seg = haversine_miles(lats[:-1], lons[:-1], lats[1:], lons[1:])
    steps = np.maximum(1, np.ceil(seg / (radius_miles / 2))).astype(int)
    idx = np.repeat(np.arange(len(seg)), steps)
    frac = (np.arange(steps.sum()) - np.repeat(np.cumsum(steps) - steps, steps)) / np.repeat(steps, steps)
    sample_lats = np.append(lats[idx] + frac * (lats[idx + 1] - lats[idx]), lats[-1])
    sample_lons = np.append(lons[idx] + frac * (lons[idx + 1] - lons[idx]), lons[-1])

    cells = set(zip(np.floor(sample_lats / lat_step).astype(int).tolist(), np.floor(sample_lons / lon_step).astype(int).tolist()))
    cells = {(r + dr, c + dc) for r, c in cells for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
    return [
        s
        for s in stations
        if (math.floor(s.location.lat / lat_step), math.floor(s.location.lon / lon_step)) in cells
    ]
