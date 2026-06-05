from __future__ import annotations

from typing import Any


CLOSE_READINESS_UNAVAILABLE_REASON = "Close readiness is unknown because resolved paths are unavailable."
CLOSE_READINESS_UNAVAILABLE_WARNING = "Resolved paths were unavailable while evaluating close readiness."


def read_unavailable_payload(label: str) -> dict[str, Any]:
    return {"error": f"{label} unavailable"}


def close_readiness_unavailable_payload() -> dict[str, Any]:
    return {
        "schema_version": "desktop_close_readiness.v1",
        "safe_to_close": False,
        "state": "unknown",
        "active_work": True,
        "reason": CLOSE_READINESS_UNAVAILABLE_REASON,
        "warnings": [CLOSE_READINESS_UNAVAILABLE_WARNING],
    }
