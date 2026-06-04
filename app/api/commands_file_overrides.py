from __future__ import annotations

# ==============================================================================
# app/api/commands_file_overrides.py
# ==============================================================================
# POST /api/queue/file-overrides  — set or clear per-file processing overrides.
# GET  /api/queue/file-overrides  — read current override manifest or a single entry.
#
# The implementation helpers live under app/api/file_overrides/. This module
# remains the compatibility/mixin entry point for Local API command handlers.
# ==============================================================================

from collections.abc import Mapping
from typing import Any

from app.orchestration.runner import run_probe_stage  # legacy patch point for track-probe tests
from app.queue.file_overrides import (
    CLEARABLE_FILE_OVERRIDE_FIELDS,
    FileOverrideValidationError,
    _empty_manifest,
    _write_atomic,
    clear_file_override_entry,
    clear_file_override_fields,
    file_override_payload_warnings,
    file_overrides_to_api_payload,
    get_file_override_entry,
    read_file_overrides,
    set_file_override_entry,
    validate_file_override_payload,
)

from .command_results import resolved_paths_unavailable_payload
from .file_overrides.effective_fields import _file_override_effective_payload
from .file_overrides.folder_preview import (
    _file_override_folder_preview_payload,
    _folder_rule_command_payload,
    _folder_rule_library_root_error,
    _validate_folder_preview_options,
    _validate_folder_preview_proposal,
    _validate_folder_rule_confirmation,
    _validate_folder_rule_override,
    _validate_folder_source_path,
)
from .file_overrides.results import (
    FOLDER_PREVIEW_COMMAND,
    FOLDER_RULE_COMMAND,
    ROUTE_PREVIEW_COMMAND,
    TRACKS_COMMAND,
    _fo_command_result_payload,
    _fo_error,
    _fo_read_error,
    _fo_unavailable,
    _fo_validation_error,
    _folder_preview_error,
    _folder_preview_validation_error,
    _folder_rule_error,
    _folder_rule_validation_error,
    _query_text,
    _route_preview_error,
    _route_preview_validation_error,
    _unsupported_folder_preview_key_errors,
    _unsupported_folder_rule_key_errors,
    _unsupported_post_key_errors,
    _unsupported_route_preview_key_errors,
)
from .file_overrides.route_preview import (
    _file_override_route_preview_payload,
    _validate_route_preview_proposal,
)
from .file_overrides.selectors import _override_exact_selector_validation
from .file_overrides.series import (
    file_override_series_apply_payload,
    file_override_series_preview_payload,
    unsupported_series_apply_key_errors,
    unsupported_series_preview_key_errors,
    validate_series_override_payload,
)
from .file_overrides.tracks import (
    _file_override_tracks_payload_from_probe_result,
    _probe_tracks_for_source_path,
)


def validate_queue_source_path(resolved: Any, raw_path: Any, **kwargs: Any):
    from mediapipeline_desktop_app.api.queue_source_path_policy import (
        validate_queue_source_path as _validate_queue_source_path,
    )

    return _validate_queue_source_path(resolved, raw_path, **kwargs)


class LocalApiFileOverridesCommandPayloadMixin:

    def _file_overrides_folder_rule_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/folder-rule — save/clear validated folder-prefix rules."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(FOLDER_RULE_COMMAND, "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _folder_rule_error("state_root is not configured (LocalBase may be missing from config)")

        top_level_errors = _unsupported_folder_rule_key_errors(request)
        if top_level_errors:
            return _folder_rule_validation_error(top_level_errors)

        folder_path, path_error = _validate_folder_source_path(resolved, request.get("folder_path", ""))
        if path_error:
            return _folder_rule_error(path_error)

        library_root_error = _folder_rule_library_root_error(resolved, folder_path or "")
        if library_root_error:
            return _folder_rule_error(library_root_error)

        if request.get("clear"):
            try:
                manifest = clear_file_override_entry(fo_path, folder_path or "")
            except Exception as exc:
                self.logger.exception("queue.file_overrides.folder_rule clear failed: %s", exc)
                return _folder_rule_error(f"Failed to clear folder override for '{folder_path}': {exc}")
            return _folder_rule_command_payload(
                manifest=manifest,
                manifest_path=fo_path,
                resolved=resolved,
                folder_path=folder_path or "",
                message=f"Folder override cleared for: {folder_path}",
                cleared=True,
            )

        confirmation_errors = _validate_folder_rule_confirmation(request.get("confirmation"))
        override_data, override_errors = _validate_folder_rule_override(request.get("override"))
        errors = confirmation_errors + override_errors
        if errors:
            return _folder_rule_validation_error(errors)

        try:
            manifest = set_file_override_entry(fo_path, folder_path or "", override_data)
        except FileOverrideValidationError as exc:
            return _folder_rule_validation_error(exc.errors)
        except Exception as exc:
            self.logger.exception("queue.file_overrides.folder_rule save failed: %s", exc)
            return _folder_rule_error(f"Failed to write folder override for '{folder_path}': {exc}")

        return _folder_rule_command_payload(
            manifest=manifest,
            manifest_path=fo_path,
            resolved=resolved,
            folder_path=folder_path or "",
            message=f"Folder override saved for: {folder_path}",
        )

    def _file_overrides_folder_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/folder-preview — read-only folder rule impact preview."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(FOLDER_PREVIEW_COMMAND, "queue")

        top_level_errors = _unsupported_folder_preview_key_errors(request)
        if top_level_errors:
            return _folder_preview_validation_error(top_level_errors)

        folder_path, path_error = _validate_folder_source_path(resolved, request.get("folder_path", ""))
        if path_error:
            return _folder_preview_error(path_error)

        proposed_override, proposal_errors = _validate_folder_preview_proposal(request.get("proposed_override", {}))
        options, option_errors = _validate_folder_preview_options(request.get("options", {}))
        errors = proposal_errors + option_errors
        if errors:
            return _folder_preview_validation_error(errors)

        return _file_override_folder_preview_payload(
            resolved=resolved,
            folder_path=folder_path or "",
            proposed_override=proposed_override,
            options=options,
        )

    def _file_overrides_route_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/route-preview — read-only route impact preview."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(ROUTE_PREVIEW_COMMAND, "queue")

        top_level_errors = _unsupported_route_preview_key_errors(request)
        if top_level_errors:
            return _route_preview_validation_error(top_level_errors)

        path_raw = str(request.get("path", "")).strip()
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _route_preview_error(error if path_raw else "'path' is required.")

        proposed_override, validation_errors, validation_warnings = _validate_route_preview_proposal(
            request.get("proposed_override", {})
        )
        if validation_errors:
            payload = _route_preview_validation_error(validation_errors)
            payload["warnings"] = validation_warnings
            return payload

        payload = _file_override_route_preview_payload(
            resolved=resolved,
            source_path=source_path or "",
            proposed_override=proposed_override,
        )
        if payload.get("ok") and validation_warnings:
            payload["warnings"] = validation_warnings + list(payload.get("warnings") or [])
        return payload

    def _file_overrides_series_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/series-preview — read-only current-series impact preview."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.file_overrides.series_preview", "queue")

        top_level_errors = unsupported_series_preview_key_errors(request)
        if top_level_errors:
            return {
                "ok": False,
                "command": "queue.file_overrides.series_preview",
                "severity": "error",
                "schema_version": "queue_file_override_series_preview.v1",
                "message": "Invalid series preview payload.",
                "errors": top_level_errors,
                "blockers": [{"code": "blocked", "message": error} for error in top_level_errors],
                "rows": [],
                "counts": {},
            }

        path_raw = str(request.get("path", "")).strip()
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return {
                "ok": False,
                "command": "queue.file_overrides.series_preview",
                "severity": "error",
                "schema_version": "queue_file_override_series_preview.v1",
                "message": error if path_raw else "'path' is required.",
                "errors": [error if path_raw else "'path' is required."],
                "blockers": [{"code": "blocked", "message": error if path_raw else "'path' is required."}],
                "rows": [],
                "counts": {},
            }

        proposed_override, validation_errors, validation_warnings = validate_series_override_payload(
            request.get("proposed_override")
        )
        if validation_errors:
            return {
                "ok": False,
                "command": "queue.file_overrides.series_preview",
                "severity": "error",
                "schema_version": "queue_file_override_series_preview.v1",
                "message": "Invalid series preview payload.",
                "errors": validation_errors,
                "blockers": [{"code": "blocked", "message": error} for error in validation_errors],
                "warnings": [{"code": "warning", "message": warning} for warning in validation_warnings],
                "rows": [],
                "counts": {},
            }

        return file_override_series_preview_payload(
            resolved=resolved,
            source_path=source_path or "",
            proposed_override=proposed_override,
            validation_warnings=validation_warnings,
        )

    def _file_overrides_series_apply_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides/series-apply — confirmed current-series override write."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.file_overrides.series_apply", "queue")

        def series_apply_error(message: str, errors: list[str] | None = None) -> dict[str, Any]:
            return _fo_command_result_payload({
                "ok":       False,
                "command":  "queue.file_overrides.series_apply",
                "severity": "error",
                "message":  message,
                "errors":   errors or [message],
            })

        top_level_errors = unsupported_series_apply_key_errors(request)
        if top_level_errors:
            return series_apply_error("Invalid series apply payload.", top_level_errors)
        if request.get("confirm_apply") is not True:
            return series_apply_error("'confirm_apply' must be true before applying a series override.")

        path_raw = str(request.get("path", "")).strip()
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return series_apply_error(error if path_raw else "'path' is required.")

        proposed_override, validation_errors, validation_warnings = validate_series_override_payload(
            request.get("proposed_override")
        )
        if validation_errors:
            return series_apply_error("Invalid series apply payload.", validation_errors)

        payload = file_override_series_apply_payload(
            resolved=resolved,
            source_path=source_path or "",
            proposed_override=proposed_override,
            preview_fingerprint=str(request.get("preview_fingerprint") or "").strip(),
            validation_warnings=validation_warnings,
        )
        return _fo_command_result_payload(payload)

    def _file_overrides_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        """POST /api/queue/file-overrides — set / update / clear overrides."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("queue.file_overrides", "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _fo_unavailable("state_root is not configured (LocalBase may be missing from config)", command_result=True)

        top_level_errors = _unsupported_post_key_errors(request)
        if top_level_errors:
            return _fo_validation_error(top_level_errors)

        # ── Clear all ──────────────────────────────────────────────────────
        if request.get("clear_all"):
            try:
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

        # ── Clear selected fields from exact file entry ────────────────────
        if "clear_fields" in request:
            raw_clear_fields = request.get("clear_fields")
            if not isinstance(raw_clear_fields, list) or not raw_clear_fields:
                return _fo_error("'clear_fields' must be a non-empty list of field paths.")
            clear_fields: list[str] = []
            for value in raw_clear_fields:
                if not isinstance(value, str) or not value.strip():
                    return _fo_error("'clear_fields' must contain non-empty field path strings.")
                clear_fields.append(value.strip())
            invalid_fields = [field for field in clear_fields if field not in CLEARABLE_FILE_OVERRIDE_FIELDS]
            if invalid_fields:
                allowed = ", ".join(sorted(CLEARABLE_FILE_OVERRIDE_FIELDS))
                return _fo_error(
                    "Unsupported clear_fields path(s): "
                    f"{', '.join(invalid_fields)}. Allowed fields: {allowed}."
                )
            try:
                manifest = clear_file_override_fields(fo_path, source_path or "", clear_fields)
            except Exception as exc:
                self.logger.exception("queue.file_overrides clear_fields failed: %s", exc)
                return _fo_error(f"Failed to clear override fields for '{source_path}': {exc}")
            payload = file_overrides_to_api_payload(manifest, fo_path)
            payload["command"]  = "queue.file_overrides"
            payload["severity"] = "ok"
            payload["message"]  = f"Override fields cleared for: {source_path}"
            return _fo_command_result_payload(payload)

        # ── Set / update entry ─────────────────────────────────────────────
        override_data: dict[str, Any] = {}
        for key in ("audio", "subtitles", "routing", "video"):
            val = request.get(key)
            if val is not None:
                if not isinstance(val, dict):
                    return _fo_error(f"'{key}' must be an object.")
                if key in {"routing", "video"} and not val:
                    continue
                override_data[key] = val

        if not override_data:
            return _fo_error(
                "No override fields provided. "
                "Include at least one of: audio, subtitles, routing, video. "
                "To clear an entry use 'clear': true."
            )

        validation_errors = validate_file_override_payload(override_data)
        if validation_errors:
            return _fo_validation_error(validation_errors)
        exact_errors, exact_warnings = _override_exact_selector_validation(
            override_data,
            source_path or "",
            state_db_root=getattr(resolved, "state_root", None),
        )
        if exact_errors:
            return _fo_validation_error(exact_errors)
        validation_warnings = file_override_payload_warnings(override_data) + exact_warnings
        subtitles = override_data.get("subtitles") if isinstance(override_data.get("subtitles"), Mapping) else {}
        burn_track = subtitles.get("burnTrack") if isinstance(subtitles, Mapping) else None

        try:
            manifest = set_file_override_entry(fo_path, source_path or "", override_data)
        except FileOverrideValidationError as exc:
            return _fo_validation_error(exc.errors)
        except Exception as exc:
            self.logger.exception("queue.file_overrides set failed: %s", exc)
            return _fo_error(f"Failed to write override for '{source_path}': {exc}")

        payload = file_overrides_to_api_payload(manifest, fo_path)
        payload["command"]  = "queue.file_overrides"
        payload["severity"] = "ok"
        payload["message"]  = f"Override saved for: {source_path}"
        if isinstance(burn_track, Mapping):
            stream_index = burn_track.get("streamIndex", "?")
            payload["message"] = (
                f"Override saved for: {source_path}. "
                f"Subtitle burn-in selected for stream {stream_index}; output subtitles will be dropped."
            )
            payload["confirmation"] = {
                "type":         "subtitle_burn_in",
                "source_path":  source_path,
                "streamIndex":  stream_index,
                "message":      f"Burn subtitle stream {stream_index} into video for {source_path}; selectable subtitles will be dropped.",
            }
        if validation_warnings:
            payload["warnings"] = validation_warnings
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
        path_raw = _query_text(query, "path")
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

    def _file_overrides_effective_read_payload(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET /api/queue/file-overrides/effective — inspect resolved drawer settings."""
        command = "queue.file_overrides.effective"
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(command, "queue")

        fo_path = getattr(resolved, "file_overrides_path", None)
        if fo_path is None:
            return _fo_read_error(command, "File overrides service unavailable: state_root is not configured")

        path_raw = _query_text(query, "path")
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _fo_read_error(command, error if path_raw else "'path' is required.")

        manifest = read_file_overrides(fo_path)
        config = getattr(resolved, "config_data", {}) or {}
        return _file_override_effective_payload(
            manifest=manifest,
            manifest_path=fo_path,
            source_path=source_path or "",
            config=config if isinstance(config, Mapping) else {},
            state_db_root=getattr(resolved, "state_root", None),
        )

    def _file_overrides_tracks_read_payload(self, query: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET /api/queue/file-overrides/tracks — read normalized track metadata."""
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload(TRACKS_COMMAND, "queue")

        path_raw = _query_text(query, "path")
        source_path, error = validate_queue_source_path(resolved, path_raw)
        if error:
            return _fo_read_error(TRACKS_COMMAND, error if path_raw else "'path' is required.")

        return _probe_tracks_for_source_path(source_path or "", state_db_root=getattr(resolved, "state_root", None))
