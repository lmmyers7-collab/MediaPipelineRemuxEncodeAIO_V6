from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteHandlerSpec:
    method_name: str
    needs_query: bool = False
