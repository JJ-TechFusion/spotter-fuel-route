"""Database reads, returned as domain entities."""

from fuel.domain.entities import Coordinate, Station
from fuel.domain.places import normalize_place_name
from fuel.models import City, FuelStation


def find_city(name: str, state: str) -> Coordinate | None:
    city = City.objects.filter(state=state.upper(), key=normalize_place_name(name)).first()
    return Coordinate(city.latitude, city.longitude) if city else None


def stations_in_box(south: float, west: float, north: float, east: float) -> list[Station]:
    rows = FuelStation.objects.filter(
        latitude__range=(south, north), longitude__range=(west, east)
    ).values_list("opis_id", "name", "address", "city", "state", "retail_price", "latitude", "longitude")
    return [
        Station(id=i, name=n, address=a, city=c, state=s, price=float(p), location=Coordinate(lat, lon))
        for i, n, a, c, s, p, lat, lon in rows
    ]
