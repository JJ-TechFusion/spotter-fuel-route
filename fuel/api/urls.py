from django.urls import path

from .views import TripPlanView, trip_map_view

urlpatterns = [
    path("trips/", TripPlanView.as_view(), name="trip-plan"),
    path("trips/map/", trip_map_view, name="trip-map"),
]
