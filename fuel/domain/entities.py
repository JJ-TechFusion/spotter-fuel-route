"""Plain data types the rest of the app passes around. No Django in here."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float


@dataclass(frozen=True)
class Station:
    id: int
    name: str
    address: str
    city: str
    state: str
    price: float  # USD per gallon
    location: Coordinate


@dataclass(frozen=True)
class Route:
    distance_miles: float
    duration_seconds: float
    points: list[Coordinate]


@dataclass(frozen=True)
class StationOnRoute:
    station: Station
    mile: float  # distance from the start, measured along the route


@dataclass(frozen=True)
class FuelStop:
    station: Station
    mile: float
    gallons: float
    cost: float


@dataclass(frozen=True)
class TripPlan:
    start: Coordinate
    finish: Coordinate
    route: Route
    stops: list[FuelStop]
    total_gallons: float
    total_cost: float
