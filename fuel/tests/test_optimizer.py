from django.test import SimpleTestCase

from fuel.domain.entities import Coordinate, Station, StationOnRoute
from fuel.domain.errors import NoFeasiblePlan
from fuel.domain.optimizer import plan_fuel_stops


def on_route(mile: float, price: float, id: int | None = None) -> StationOnRoute:
    station = Station(id=id or int(mile), name=f"S{mile}", address="", city="", state="TX", price=price, location=Coordinate(0, 0))
    return StationOnRoute(station=station, mile=mile)


class PlanFuelStopsTests(SimpleTestCase):
    def plan(self, stations, total, **kwargs):
        return plan_fuel_stops(stations, total, range_miles=500, mpg=10, **kwargs)

    def test_short_trip_is_one_stop_at_the_start(self):
        stops = self.plan([on_route(0, 3.00)], total=200)
        self.assertEqual(len(stops), 1)
        self.assertAlmostEqual(stops[0].gallons, 20)
        self.assertAlmostEqual(stops[0].cost, 60)

    def test_buys_only_enough_to_reach_a_cheaper_station(self):
        stops = self.plan([on_route(0, 4.00), on_route(100, 3.00)], total=400)
        self.assertEqual([s.mile for s in stops], [0, 100])
        self.assertAlmostEqual(stops[0].gallons, 10)
        self.assertAlmostEqual(stops[1].gallons, 30)

    def test_picks_the_cheapest_station_in_range(self):
        stations = [on_route(0, 3.00), on_route(300, 4.00), on_route(450, 2.50), on_route(700, 4.00)]
        stops = self.plan(stations, total=900)
        self.assertEqual([s.mile for s in stops], [0, 450])
        self.assertAlmostEqual(sum(s.cost for s in stops), 45 * 3.00 + 45 * 2.50)

    def test_gallons_always_cover_the_whole_trip(self):
        stations = [on_route(m, 3 + (m % 7) / 10) for m in range(0, 2000, 37)]
        stops = self.plan(stations, total=2000)
        self.assertAlmostEqual(sum(s.gallons for s in stops), 200)

    def test_stop_overhead_skips_stops_that_save_pennies(self):
        stations = [on_route(0, 3.01), on_route(5, 3.00)]
        self.assertEqual(len(self.plan(stations, total=300)), 2)
        self.assertEqual(len(self.plan(stations, total=300, stop_overhead=5)), 1)

    def test_first_stop_is_charged_for_the_drive_from_the_start(self):
        stops = self.plan([on_route(20, 3.00)], total=300)
        self.assertAlmostEqual(stops[0].gallons, 30)

    def test_gap_longer_than_range_is_reported(self):
        with self.assertRaisesMessage(NoFeasiblePlan, "between mile 100 and mile 700"):
            self.plan([on_route(0, 3.0), on_route(100, 3.0), on_route(700, 3.0)], total=900)

    def test_no_stations_is_infeasible(self):
        with self.assertRaises(NoFeasiblePlan):
            self.plan([], total=100)
