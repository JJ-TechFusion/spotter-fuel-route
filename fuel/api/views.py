from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from fuel.application.plan_trip import plan_trip
from fuel.domain.entities import TripPlan
from fuel.domain.errors import InvalidLocation, RoutingServiceError, TripPlanningError

from .serializers import TripPlanSerializer, TripQuerySerializer


class UnplannableTrip(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "unplannable_trip"


class RoutingUnavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "routing_unavailable"


def get_trip_plan(query_params) -> TripPlan:
    """Validate the query and run the use case, translating domain errors to HTTP ones."""
    query = TripQuerySerializer(data=query_params)
    query.is_valid(raise_exception=True)
    try:
        return plan_trip(query.validated_data["start"], query.validated_data["finish"])
    except InvalidLocation as exc:
        raise ValidationError({"detail": str(exc)}) from exc
    except TripPlanningError as exc:
        raise UnplannableTrip(str(exc)) from exc
    except RoutingServiceError as exc:
        raise RoutingUnavailable(str(exc)) from exc


class TripPlanView(APIView):
    """GET /api/trips/?start=Chicago, IL&finish=Denver, CO"""

    def get(self, request):
        plan = get_trip_plan(request.query_params)
        data = TripPlanSerializer(plan).data
        data["map_url"] = request.build_absolute_uri(f"{reverse('trip-map')}?{request.GET.urlencode()}")
        return Response(data)


def error_text(detail) -> str:
    """Flatten DRF error detail ({"detail": ...}, {"field": [...]}, or a string) to plain text."""
    if isinstance(detail, dict):
        return "\n".join(
            error_text(value) if key == "detail" else f"{key}: {error_text(value)}" for key, value in detail.items()
        )
    if isinstance(detail, list):
        return " ".join(error_text(item) for item in detail)
    return str(detail)


def trip_map_view(request):
    """GET /api/trips/map/?start=...&finish=... renders the same plan on a Leaflet map."""
    try:
        plan = get_trip_plan(request.GET)
    except APIException as exc:
        return HttpResponse(error_text(exc.detail), status=exc.status_code, content_type="text/plain")
    return render(request, "fuel/map.html", {"trip": TripPlanSerializer(plan).data})
