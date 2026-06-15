from __future__ import annotations

from typing import TYPE_CHECKING

from .contract import LOCAL_API_CONTRACT_SCHEMA_VERSION, LOCAL_API_ROUTE_CONTRACT

if TYPE_CHECKING:
    from .server import LocalApiServer


def __getattr__(name: str) -> object:
    if name == "LocalApiServer":
        from .server import LocalApiServer

        return LocalApiServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["LOCAL_API_CONTRACT_SCHEMA_VERSION", "LOCAL_API_ROUTE_CONTRACT", "LocalApiServer"]
