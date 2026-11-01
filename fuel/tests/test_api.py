from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from fuel.domain.entities import Coordinate, Route
from fuel.domain.errors import RoutingServiceError
from fuel.models import City, FuelStation

ROUTE = "fuel.infrastructure.osrm.OsrmRouter.route"


def fake_route(start: Coordinate, finish: Coordinate) -> Route:
    """A straight line, 690 miles long, so one refuel is needed."""
    steps = 50
    points = [
        Coordinate(start.lat + (finish.lat - start.lat) * i / steps, start.lon + (finish.lon - start.lon) * i / steps)
        for i in range(steps + 1)
    ]
    return Route(distance_miles=690, duration_seconds=36000, points=points)


class TripApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        City.objects.create(state="KS", name="Start", key="start", latitude=37.0, longitude=-98.0)
        City.objects.create(state="NE", name="Finish", key="finish", latitude=47.0, longitude=-98.0)
        for opis_id, lat, price in [(1, 37.0, 3.50), (2, 40.0, 3.20), (3, 42.0, 2.90)]:
            FuelStation.objects.create(
                opis_id=opis_id, name=f"Stop {opis_id}", address="I-35", city="Town", state="KS",
                retail_price=price, latitude=lat, longitude=-98.0,
            )

    def setUp(self):
        cache.clear()

    def get(self, start="Start, KS", finish="Finish, NE", path="/api/trips/"):
        return self.client.get(path, {"start": start, "finish": finish})

    @mock.patch(ROUTE, side_effect=fake_route)
    def test_returns_route_stops_and_total_cost(self, route):
        response = self.get()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["distance_miles"], 690)
        self.assertEqual(body["total_gallons"], 69)
        self.assertEqual([s["station"]["id"] for s in body["fuel_stops"]], [1, 3])
        self.assertEqual(body["total_cost"], round(sum(s["cost"] for s in body["fuel_stops"]), 2))
        self.assertEqual(body["route"]["type"], "LineString")
        self.assertIn("/api/trips/map/?", body["map_url"])
        route.assert_called_once()

    @mock.patch(ROUTE, side_effect=fake_route)
    def test_repeat_requests_and_the_map_reuse_one_routing_call(self, route):
        self.get()
        self.get()
        response = self.get(path="/api/trips/map/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "trip-data")
        route.assert_called_once()

    @mock.patch(ROUTE, side_effect=fake_route)
    def test_accepts_coordinates(self, route):
        self.assertEqual(self.get(start="37.0,-98.0", finish="47.0,-98.0").status_code, 200)

    def test_unknown_city_is_a_bad_request(self):
        response = self.get(start="Atlantis, KS")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown US city", response.json()["detail"])

    def test_location_outside_usa_is_a_bad_request(self):
        self.assertEqual(self.get(start="51.5,-0.12").status_code, 400)

    def test_missing_finish_is_a_bad_request(self):
        response = self.client.get("/api/trips/", {"start": "Start, KS"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("finish", response.json())

    @mock.patch(ROUTE, side_effect=RoutingServiceError("Routing service is unavailable."))
    def test_routing_outage_is_a_bad_gateway(self, route):
        self.assertEqual(self.get().status_code, 502)
