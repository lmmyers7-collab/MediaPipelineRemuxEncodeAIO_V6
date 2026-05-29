from __future__ import annotations

# ==============================================================================
# app/api/commands_queue_priority.py
# ==============================================================================
# POST /api/queue/priority  — set, update, or clear the manifest priority level
#                             for one or more source paths / folders.
#
# Single-item request body:
#   {
#     "path":   "<source path or folder>",  // required
#     "level":  "high" | "normal" | "low" | "hold",   // required
#     "reason": "<optional operator note>"
#   }
#
# Bulk request body:
#   {
#     "items": [
#       {"path": "...", "level": "high", "reason": "..."},
#       ...
#     ]
#   }
#
# Response:
#   {
#     "ok":            true | false,
#     "command":       "queue.priority",
#     "severity":      "ok" | "error",
#     "message":       "...",
#     "manifest_path": "<path on disk>",
#     "entry_count":   <int>,
#     "entries":       { ... }   // full manifest entry map
#   }
# ==============================================================================

from typing import Any

from mediapipeline_desktop_app.api.queue_source_path_policy import validate_queue_source_path
from app.queue.priority_manifest import (
    VALID_LEVELS,
    manifest_to_api_payload,
    read_priority_manifest,
    set_manifest_entries_bulk,
    set_manifest_entry,
)

from .command_results import resolved_paths_unavailable_payload


def _priority_command_result_payload(payload: dict) -> dict:
    result = dict(payload)
    result["schema_version"] = "desktop_command_result.v1"
    result.setdefault("refresh_hint", "queue")
    if not result.get("ok") and "errors" not in result:
        result["errors"] = [str(result.get("message") or "Queue priority command failed.")]
    return result


def _priority_unavailable_payload(reason: str, *, command_result: bool = False) -> dict:
    payload = {
        "ok": False,
        "command": "queue.priority",
        "severity": "error",
        "message": f"Priority manifest unavailable: {reason}",
    }
    return _priority_command_result_payload(payload) if command_result else payload


def _priority_error_payload(message: str) -> dict:
    return _priority_command_result_payload({
        "ok": False,
        "command": "queue.priority",
        "severity": "error",
        "message": message,
    })


class LocalApiQueuePriorityCommandPayloadMixin:

    def _queue_priority_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.priority", "queue")

        manifest_path = getattr(resolved, "priority_manifest_path", None)
        if manifest_path is None:
            return _priority_unavailable_payload(
                "state_root is not configured (LocalBase may be missing from config)",
                command_result=True,
            )

        # ----------------------------------------------------------------
        # Bulk mode — "items" key present
        # ----------------------------------------------------------------
        items_raw = request.get("items")
        if items_raw is not None:
            if not isinstance(items_raw, list):
                return _priority_error_payload("'items' must be a list of {path, level, reason?} objects.")
            if not items_raw:
                return _priority_error_payload("'items' list is empty.")
            items: list[dict[str, str]] = []
            for item in items_raw:
                if not isinstance(item, dict):
                    return _priority_error_payload("Each item in 'items' must be an object.")
                level = str(item.get("level", "")).lower()
                if level not in VALID_LEVELS:
                    return _priority_error_payload(
                        f"Invalid level {level!r} in bulk items. Must be one of: {sorted(VALID_LEVELS)}"
                    )
                source_path, error = validate_queue_source_path(resolved, item.get("path", ""))
                if error:
                    return _priority_error_payload(error)
                items.append({
                    "path": source_path or "",
                    "level": level,
                    "reason": str(item.get("reason", "")).strip(),
                })
            try:
                manifest = set_manifest_entries_bulk(manifest_path, items)
            except Exception as exc:
                self.logger.exception("queue.priority bulk update failed: %s", exc)
                return _priority_error_payload(f"Failed to write priority manifest: {exc}")

            payload = manifest_to_api_payload(manifest, manifest_path)
            payload["command"] = "queue.priority"
            payload["severity"] = "ok"
            payload["message"] = f"Priority updated for {len(items)} path(s)."
            return _priority_command_result_payload(payload)

        # ----------------------------------------------------------------
        # Single-item mode
        # ----------------------------------------------------------------
        path_raw = str(request.get("path", "")).strip()
        level_raw = str(request.get("level", "")).lower()
        reason = str(request.get("reason", "")).strip()

        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _priority_error_payload(error)
        if level_raw not in VALID_LEVELS:
            return _priority_error_payload(
                f"Invalid level {level_raw!r}. Must be one of: {sorted(VALID_LEVELS)}"
            )

        try:
            manifest = set_manifest_entry(manifest_path, source_path or "", level_raw, reason)
        except Exception as exc:
            self.logger.exception("queue.priority update failed: %s", exc)
            return _priority_error_payload(f"Failed to write priority manifest: {exc}")

        payload = manifest_to_api_payload(manifest, manifest_path)
        payload["command"] = "queue.priority"
        payload["severity"] = "ok"
        payload["message"] = (
            f"Priority set to '{level_raw}' for: {source_path}"
            if level_raw != "normal"
            else f"Priority cleared (reset to normal) for: {source_path}"
        )
        return _priority_command_result_payload(payload)

    def _queue_priority_read_payload(self) -> dict[str, Any]:
        """GET /api/queue/priority — return the current manifest contents."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.priority.read", "queue")

        manifest_path = getattr(resolved, "priority_manifest_path", None)
        if manifest_path is None:
            return _priority_unavailable_payload("state_root is not configured")

        manifest = read_priority_manifest(manifest_path)
        payload = manifest_to_api_payload(manifest, manifest_path)
        payload["command"] = "queue.priority.read"
        payload["severity"] = "ok"
        payload["message"] = f"{len(manifest.get('entries', {}))} priority manifest entries."
        return payload
