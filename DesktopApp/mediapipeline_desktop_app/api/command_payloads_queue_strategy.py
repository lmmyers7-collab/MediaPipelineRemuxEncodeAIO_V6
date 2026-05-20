from __future__ import annotations

# ==============================================================================
# api/command_payloads_queue_strategy.py
# ==============================================================================
# POST /api/queue/strategy  — set the active queue ordering strategy.
# GET  /api/queue/strategy  — return the current strategy and valid options.
#
# POST request body:
#   { "strategy": "Standard" | "FreshestFirst" | "ShowComplete" | "RoundRobin"
#                           | "DeadlineAware"  | "SmallFirst"   | "LargeFirst"
#                           | "ManualOrder" }
#
# Response (both GET and POST):
#   {
#     "ok":               true | false,
#     "command":          "queue.strategy" | "queue.strategy.read",
#     "severity":         "ok" | "error",
#     "message":          "...",
#     "strategy":         "<active strategy name>",
#     "set_at":           "<ISO-8601 UTC>",
#     "source":           "state_file" | "default",
#     "default_strategy": "Standard",
#     "valid_strategies": [...],
#     "strategy_labels":  { "<name>": "<display label>", ... }
#   }
# ==============================================================================

from typing import Any

from .command_payloads_policy import resolved_paths_unavailable_payload
from ..service_queue_strategy import (
    DEFAULT_STRATEGY,
    VALID_STRATEGIES,
    read_queue_strategy,
    set_queue_strategy,
    strategy_to_api_payload,
)


def _strategy_command_result_payload(payload: dict) -> dict:
    result = dict(payload)
    result["schema_version"] = "desktop_command_result.v1"
    result.setdefault("refresh_hint", "queue")
    if not result.get("ok") and "errors" not in result:
        result["errors"] = [str(result.get("message") or "Queue strategy command failed.")]
    return result


def _strategy_unavailable_payload(reason: str, *, command_result: bool = False) -> dict:
    payload = {
        "ok":       False,
        "command":  "queue.strategy",
        "severity": "error",
        "message":  f"Queue strategy service unavailable: {reason}",
    }
    return _strategy_command_result_payload(payload) if command_result else payload


def _strategy_error_payload(message: str) -> dict:
    return _strategy_command_result_payload({
        "ok":       False,
        "command":  "queue.strategy",
        "severity": "error",
        "message":  message,
    })


class LocalApiQueueStrategyCommandPayloadMixin:

    def _queue_strategy_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/strategy — persist a new ordering strategy."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.strategy", "queue")

        strategy_path = getattr(resolved, "queue_strategy_path", None)
        if strategy_path is None:
            return _strategy_unavailable_payload(
                "state_root is not configured (LocalBase may be missing from config)",
                command_result=True,
            )

        strategy_raw = str(request.get("strategy", "")).strip()
        if not strategy_raw:
            return _strategy_error_payload("'strategy' is required.")
        if strategy_raw not in VALID_STRATEGIES:
            return _strategy_error_payload(
                f"Invalid strategy {strategy_raw!r}. "
                f"Valid values: {sorted(VALID_STRATEGIES)}"
            )

        try:
            state = set_queue_strategy(strategy_path, strategy_raw)
        except Exception as exc:
            self.logger.exception("queue.strategy update failed: %s", exc)
            return _strategy_error_payload(f"Failed to write strategy file: {exc}")

        payload = strategy_to_api_payload(state)
        payload["ok"]       = True
        payload["command"]  = "queue.strategy"
        payload["severity"] = "ok"
        payload["message"]  = (
            f"Queue ordering strategy set to '{strategy_raw}'. "
            "Takes effect on the next queue build."
        )
        return _strategy_command_result_payload(payload)

    def _queue_strategy_read_payload(self) -> dict[str, Any]:
        """GET /api/queue/strategy — return the current strategy."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.strategy.read", "queue")

        strategy_path = getattr(resolved, "queue_strategy_path", None)
        if strategy_path is None:
            return _strategy_unavailable_payload("state_root is not configured")

        state = read_queue_strategy(strategy_path)
        payload = strategy_to_api_payload(state)
        payload["ok"]       = True
        payload["command"]  = "queue.strategy.read"
        payload["severity"] = "ok"
        payload["message"]  = f"Active queue ordering strategy: {state['strategy']}."
        return payload
