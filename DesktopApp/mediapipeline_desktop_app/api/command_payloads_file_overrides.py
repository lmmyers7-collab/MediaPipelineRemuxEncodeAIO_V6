from __future__ import annotations

# ==============================================================================
# api/command_payloads_file_overrides.py
# ==============================================================================
# POST /api/queue/file-overrides  — set or clear per-file processing overrides.
# GET  /api/queue/file-overrides  — read current override manifest or a single entry.
#
# POST request body (set/update):
#   {
#     "path":  "<source path or folder>",   // required
#     "audio": { ... },                     // optional audio section
#     "subtitles": { ... }                  // optional subtitle section
#   }
#
# POST request body (clear one entry):
#   { "path": "<source path>", "clear": true }
#
# POST request body (clear all entries):
#   { "clear_all": true }
#
# GET query params:
#   ?path=<source path>  — return the resolved override for a single path
#   (no params)          — return the entire manifest
#
# Response:
#   {
#     "ok":          true | false,
#     "command":     "queue.file_overrides" | "queue.file_overrides.read",
#     "severity":    "ok" | "error",
#     "message":     "...",
#     "manifest_path": "...",
#     "entry_count": <int>,
#     "entries":     { ... },     // full manifest (GET without ?path)
#     "entry":       { ... }      // resolved entry for ?path  (GET with ?path)
#   }
# ==============================================================================

from typing import Any

from .command_payloads_policy import resolved_paths_unavailable_payload
from .queue_source_path_policy import validate_queue_source_path
from ..service_file_overrides import (
    clear_file_override_entry,
    file_overrides_to_api_payload,
    get_file_override_entry,
    read_file_overrides,
    set_file_override_entry,
)


def _fo_command_result_payload(payload: dict) -> dict:
    result = dict(payload)
    result["schema_version"] = "desktop_command_result.v1"
    result.setdefault("refresh_hint", "queue")
    if not result.get("ok") and "errors" not in result:
        result["errors"] = [str(result.get("message") or "File override command failed.")]
    return result


def _fo_unavailable(reason: str, *, command_result: bool = False) -> dict:
    payload = {
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  f"File overrides service unavailable: {reason}",
    }
    return _fo_command_result_payload(payload) if command_result else payload


def _fo_error(message: str) -> dict:
    return _fo_command_result_payload({
        "ok":       False,
        "command":  "queue.file_overrides",
        "severity": "error",
        "message":  message,
    })


class LocalApiFileOverridesCommandPayloadMixin:

    def _file_overrides_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides — set / update / clear overrides."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.file_overrides", "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _fo_unavailable("state_root is not configured (LocalBase may be missing from config)", command_result=True)

        # ── Clear all ──────────────────────────────────────────────────────
        if request.get("clear_all"):
            try:
                from ..service_file_overrides import _write_atomic, _empty_manifest
                manifest = _empty_manifest()
                _write_atomic(fo_path, manifest)
            except Exception as exc:
                self.logger.exception("queue.file_overrides clear_all failed: %s", exc)
                return _fo_error(f"Failed to clear overrides: {exc}")
            payload = file_overrides_to_api_payload({"version": 1, "entries": {}}, fo_path)
            payload["command"]  = "queue.file_overrides"
            payload["severity"] = "ok"
            payload["message"]  = "All file overrides cleared."
            return _fo_command_result_payload(payload)

        # ── Require path for all other operations ──────────────────────────
        path_raw = str(request.get("path", "")).strip()
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _fo_error(error if path_raw else "'path' is required (or use 'clear_all': true to clear everything).")

        # ── Clear single entry ─────────────────────────────────────────────
        if request.get("clear"):
            try:
                manifest = clear_file_override_entry(fo_path, source_path or "")
            except Exception as exc:
                self.logger.exception("queue.file_overrides clear failed: %s", exc)
                return _fo_error(f"Failed to clear override for '{source_path}': {exc}")
            payload = file_overrides_to_api_payload(manifest, fo_path)
            payload["command"]  = "queue.file_overrides"
            payload["severity"] = "ok"
            payload["message"]  = f"Override cleared for: {source_path}"
            return _fo_command_result_payload(payload)

        # ── Set / update entry ─────────────────────────────────────────────
        override_data: dict[str, Any] = {}
        for key in ("audio", "subtitles"):
            val = request.get(key)
            if val is not None:
                if not isinstance(val, dict):
                    return _fo_error(f"'{key}' must be an object.")
                override_data[key] = val

        if not override_data:
            return _fo_error(
                "No override fields provided. "
                "Include at least one of: audio, subtitles. "
                "To clear an entry use 'clear': true."
            )

        try:
            manifest = set_file_override_entry(fo_path, source_path or "", override_data)
        except Exception as exc:
            self.logger.exception("queue.file_overrides set failed: %s", exc)
            return _fo_error(f"Failed to write override for '{source_path}': {exc}")

        payload = file_overrides_to_api_payload(manifest, fo_path)
        payload["command"]  = "queue.file_overrides"
        payload["severity"] = "ok"
        payload["message"]  = f"Override saved for: {source_path}"
        return _fo_command_result_payload(payload)

    def _file_overrides_read_payload(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET /api/queue/file-overrides — read manifest or single entry."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.file_overrides.read", "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _fo_unavailable("state_root is not configured")

        manifest = read_file_overrides(fo_path)

        # Single-path query: return resolved entry for one source path
        path_raw = ""
        if query and isinstance(query, dict):
            path_value = query.get("path", "")
            if isinstance(path_value, list):
                path_value = path_value[0] if path_value else ""
            path_raw = str(path_value).strip()
        if path_raw:
            source_path, error = validate_queue_source_path(resolved, path_raw)
            if error:
                return _fo_unavailable(error)
            entry = get_file_override_entry(manifest, source_path or "")
            return {
                "ok":           True,
                "command":      "queue.file_overrides.read",
                "severity":     "ok",
                "message":      f"Override entry for: {source_path}",
                "manifest_path": str(fo_path),
                "path":         source_path,
                "entry":        entry,
                "has_override": entry is not None,
            }

        # Full manifest
        payload = file_overrides_to_api_payload(manifest, fo_path)
        payload["command"]  = "queue.file_overrides.read"
        payload["severity"] = "ok"
        payload["message"]  = f"{len(manifest.get('entries', {}))} file override entries."
        return payload
