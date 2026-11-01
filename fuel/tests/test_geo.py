from django.test import SimpleTestCase

from fuel.domain.entities import Coordinate, Route, Station
from fuel.domain.geo import MILES_PER_DEGREE, stations_along_route, thin_points


def station(id: int, lat: float, lon: float) -> Station:
    return Station(id=id, name="", address="", city="", state="KS", price=3.0, location=Coordinate(lat, lon))


class StationsAlongRouteTests(SimpleTestCase):
    # A straight north-south route along lon -98, 0.0 -> 2.0 degrees of latitude.
    route = Route(
        distance_miles=2 * MILES_PER_DEGREE,
        duration_seconds=0,
        points=[Coordinate(38.0, -98.0), Coordinate(39.0, -98.0), Coordinate(40.0, -98.0)],
    )

    def test_stations_near_the_route_get_a_mile_marker(self):
        found = stations_along_route(self.route, [station(1, 38.5, -98.05)], max_offset_miles=10)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0].mile, 0.5 * MILES_PER_DEGREE, delta=0.5)

    def test_stations_far_from_the_route_are_dropped(self):
        far_east = station(2, 38.5, -97.5)  # ~27 miles off the route
        self.assertEqual(stations_along_route(self.route, [far_east], max_offset_miles=10), [])

    def test_thin_points_keeps_endpoints(self):
        points = [Coordinate(38 + i * 0.001, -98) for i in range(100)]
        thinned = thin_points(points, min_spacing_miles=1)
        self.assertEqual(thinned[0], points[0])
        self.assertEqual(thinned[-1], points[-1])
        self.assertLess(len(thinned), 20)
