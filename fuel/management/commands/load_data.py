"""Load the gazetteer and fuel prices into the database. Safe to re-run."""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from fuel.domain.places import US_STATES, normalize_place_name
from fuel.infrastructure.gazetteer import lookup_keys, read_fuel_prices, read_gazetteer
from fuel.models import City, FuelStation

# Incorporated places first; county subdivisions only fill the gaps (New England towns, townships).
GAZETTEER_FILES = ["gaz_places.zip", "gaz_cousubs.zip"]
PRICES_FILE = "fuel_prices.csv"


class Command(BaseCommand):
    help = "Load US places and geocoded fuel stations from the files in data/."

    def handle(self, *args, **options):
        data_dir = settings.DATA_DIR
        cities = self._build_city_index(data_dir)
        stations, skipped = self._build_stations(data_dir, cities)

        with transaction.atomic():
            City.objects.all().delete()
            FuelStation.objects.all().delete()
            City.objects.bulk_create(cities.values(), batch_size=5000)
            FuelStation.objects.bulk_create(stations, batch_size=2000)

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(cities)} places and {len(stations)} fuel stations."))
        if skipped:
            self.stdout.write(f"Skipped {len(skipped)} US stations with no gazetteer match, e.g. {skipped[:5]}")

    def _build_city_index(self, data_dir) -> dict[tuple[str, str], City]:
        cities = {}
        for filename in GAZETTEER_FILES:
            for place in read_gazetteer(data_dir / filename):
                for key in lookup_keys(place.name):
                    cities.setdefault(
                        (place.state, key),
                        City(state=place.state, name=place.name, key=key, latitude=place.lat, longitude=place.lon),
                    )
        return cities

    def _build_stations(self, data_dir, cities) -> tuple[list[FuelStation], list[str]]:
        # The CSV lists some stations more than once; keep the cheapest price per OPIS id.
        cheapest = {}
        for row in read_fuel_prices(data_dir / PRICES_FILE):
            if row.state in US_STATES and (row.opis_id not in cheapest or row.price < cheapest[row.opis_id].price):
                cheapest[row.opis_id] = row

        stations, skipped = [], []
        for row in cheapest.values():
            city = cities.get((row.state, normalize_place_name(row.city)))
            if city is None:
                skipped.append(f"{row.city}, {row.state}")
                continue
            stations.append(
                FuelStation(
                    opis_id=row.opis_id,
                    name=row.name,
                    address=row.address,
                    city=row.city,
                    state=row.state,
                    retail_price=round(row.price, 5),
                    latitude=city.latitude,
                    longitude=city.longitude,
                )
            )
        return stations, skipped
