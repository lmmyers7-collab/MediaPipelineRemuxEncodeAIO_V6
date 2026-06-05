from __future__ import annotations

from mediapipeline.core.api.commands import COMMAND_ROUTE_METHODS

from .routes_shared import RouteHandlerSpec


POST_ROUTE_HANDLERS: dict[str, RouteHandlerSpec] = {
    route: RouteHandlerSpec(method_name)
    for route, method_name in COMMAND_ROUTE_METHODS.items()
}
