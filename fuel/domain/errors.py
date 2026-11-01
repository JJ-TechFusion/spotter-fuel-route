class TripPlanningError(Exception):
    """A problem with the request itself; safe to show to the caller."""


class InvalidLocation(TripPlanningError):
    pass


class RouteNotFound(TripPlanningError):
    pass


class NoFeasiblePlan(TripPlanningError):
    pass


class RoutingServiceError(Exception):
    """The external routing service failed or is unreachable."""
