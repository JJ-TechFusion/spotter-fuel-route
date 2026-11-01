from rest_framework import serializers


class RoundedFloatField(serializers.FloatField):
    def __init__(self, decimals: int = 2, **kwargs):
        self.decimals = decimals
        super().__init__(**kwargs)

    def to_representation(self, value):
        return round(float(value), self.decimals)


class TripQuerySerializer(serializers.Serializer):
    start = serializers.CharField(max_length=200, help_text="'City, ST' or 'lat,lon'")
    finish = serializers.CharField(max_length=200, help_text="'City, ST' or 'lat,lon'")


class CoordinateSerializer(serializers.Serializer):
    lat = RoundedFloatField(decimals=5)
    lon = RoundedFloatField(decimals=5)


class StationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    price = RoundedFloatField(decimals=3)
    location = CoordinateSerializer()


class FuelStopSerializer(serializers.Serializer):
    station = StationSerializer()
    mile = RoundedFloatField(decimals=1)
    gallons = RoundedFloatField()
    cost = RoundedFloatField()


class TripPlanSerializer(serializers.Serializer):
    start = CoordinateSerializer()
    finish = CoordinateSerializer()
    distance_miles = RoundedFloatField(decimals=1, source="route.distance_miles")
    duration_hours = serializers.SerializerMethodField()
    total_gallons = RoundedFloatField()
    total_cost = RoundedFloatField()
    fuel_stops = FuelStopSerializer(source="stops", many=True)
    route = serializers.SerializerMethodField()

    def get_duration_hours(self, plan):
        return round(plan.route.duration_seconds / 3600, 1)

    def get_route(self, plan):
        """GeoJSON LineString, ready for Leaflet, Mapbox or geojson.io."""
        return {
            "type": "LineString",
            "coordinates": [[round(p.lon, 5), round(p.lat, 5)] for p in plan.route.points],
        }
