from __future__ import annotations

from typing import Any

from .contract_payload import local_api_contract_payload
from .http_helpers import QueryValidationError, query_bool, query_int, query_value
from .read_payloads_policy import close_readiness_unavailable_payload, read_unavailable_payload
from mediapipeline.core.status.run_monitor import unavailable_run_monitor_projection
from mediapipeline.core.status.run_monitor_storage import RUN_ID_PATTERN
from mediapipeline.desktop.watch import watch_folder_state_mapping


def _run_monitor_run_id(query: dict[str, list[str]]) -> str:
    values = query.get("run_id")
    if not values:
        return ""
    if len(values) != 1:
        raise QueryValidationError("query parameter run_id must appear at most once")
    run_id = str(values[0] or "").strip()
    if not RUN_ID_PATTERN.fullmatch(run_id) or run_id.casefold() == "latest":
        raise QueryValidationError("query parameter run_id is not a valid backend run identity")
    return run_id


class LocalApiStatusReadPayloadMixin:
    def _health_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        payload = self.facade.get_health(resolved).to_mapping()
        startup_progress = getattr(self, "startup_progress", None)
        if isinstance(startup_progress, dict):
            payload["startup_progress"] = dict(startup_progress)
        return payload

    def _contract_payload(self) -> dict[str, Any]:
        return local_api_contract_payload(app_version=self.facade.app_version, host=self.host)

    def _snapshot_payload(self) -> dict[str, Any]:
        snapshot = self._snapshot()
        if snapshot is None:
            return read_unavailable_payload("snapshot")
        return self.facade.snapshot_to_dto(snapshot).to_mapping()

    def _run_monitor_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return unavailable_run_monitor_projection(
                reason_code="resolved_paths_unavailable",
                backend_activity_state="unavailable",
                detail="Resolved backend state paths are unavailable.",
            )
        return self.facade.get_run_monitor(
            resolved,
            run_id=_run_monitor_run_id(query),
        )

    def _diagnostics_payload(self) -> dict[str, Any]:
        snapshot = self._snapshot()
        if snapshot is None:
            return read_unavailable_payload("diagnostics")
        return self.facade.get_diagnostics(snapshot).to_mapping()

    def _diagnostics_tail_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("diagnostics_tail")
        request = {
            "target": query.get("target", [""])[0] if query.get("target") else "",
            "max_bytes": query_int(query, "max_bytes", 65_536),
        }
        return self.facade.read_diagnostics_tail(resolved, request)

    def _diagnostics_state_summary_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("diagnostics_state_summary")
        return self.facade.read_diagnostics_state_summary(resolved)

    def _tdarr_matrix_console_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        request = {
            "run_id": query_value(query, "run_id", ""),
            "finding_limit": query_int(query, "finding_limit", 100),
        }
        return self.facade.read_tdarr_matrix_console(request)

    def _tdarr_matrix_runs_payload(self) -> dict[str, Any]:
        return self.facade.list_tdarr_matrix_runs({})

    def _tdarr_matrix_compare_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        request = {
            "left_run_id": query_value(query, "left_run_id", query_value(query, "left", "")),
            "right_run_id": query_value(query, "right_run_id", query_value(query, "right", "")),
        }
        return self.facade.compare_tdarr_matrix_runs(request)

    def _telemetry_payload(self) -> dict[str, Any]:
        return self.facade.get_cached_telemetry().to_mapping()

    def _close_readiness_payload(self) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return close_readiness_unavailable_payload()
        return self.facade.get_close_readiness(resolved, self._snapshot()).to_mapping()

    def _backend_recovery_status_payload(self) -> dict[str, Any]:
        reader = getattr(self.facade, "get_recovery_status", None)
        if not callable(reader):
            return {"schema_version": "desktop_lifecycle_recovery.v1", "status": "unknown", "classification": "unknown", "operator_action_required": "Backend recovery status is unavailable.", "items": []}
        return dict(reader())

    def _watch_folders_status_payload(self) -> dict[str, Any]:
        state_reader = getattr(self.facade, "get_watch_folder_state", None)
        if not callable(state_reader):
            return watch_folder_state_mapping(None)
        try:
            return dict(state_reader())
        except Exception as exc:
            payload = watch_folder_state_mapping(None)
            payload["status"] = "error"
            payload["reason"] = "Watch-folder state could not be read."
            payload["last_error"] = str(exc)
            return payload

    def _launch_preflight_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return read_unavailable_payload("launch preflight")
        target = query_value(query, "target", "pipeline")
        request: dict[str, Any] = {"target": target}
        if target in {"pipeline", ""}:
            request.update(
                {
                    "mode": query_value(query, "mode", "validate"),
                    "sleep_seconds": query_int(query, "sleep_seconds", 30),
                    "show_config": query_bool(query, "show_config", False),
                    "show_console": query_bool(query, "show_console", False),
                    "schedule_override": query_value(query, "schedule_override", ""),
                    "extra_args": query_value(query, "extra_args", ""),
                    "allow_extra_args": query_bool(query, "allow_extra_args", False),
                    "refresh_encoder_capability_report": query_bool(query, "refresh_encoder_capability_report", False),
                }
            )
        elif target == "audit":
            request.update(
                {
                    "library_root": query_value(query, "library_root", ""),
                    "include_sidecars": query_bool(query, "include_sidecars", False),
                    "show_console": query_bool(query, "show_console", False),
                }
            )
        elif target in {"rerun", "csv"}:
            request.update(
                {
                    "csv_path": query_value(query, "csv_path", ""),
                    "dry_run": query_bool(query, "dry_run", False),
                    "plan_only": query_bool(query, "plan_only", False),
                    "execution_mode": query_value(query, "execution_mode", "one_at_a_time"),
                    "destination_mode": query_value(query, "destination_mode", "auto_replace_clean_else_pending_review"),
                    "collision_policy": query_value(query, "collision_policy", "replace_final"),
                    "window_size": query_int(query, "window_size", 1),
                    "confirm_replace_final": query_bool(query, "confirm_replace_final", False),
                    "confirm_source_overwrite": query_bool(query, "confirm_source_overwrite", False),
                }
            )
            if "stage_mode" in query:
                request["stage_mode"] = query_value(query, "stage_mode", "copy")
            if "original_mode" in query:
                request["original_mode"] = query_value(query, "original_mode", "keep")
            if "return_mode" in query:
                request["return_mode"] = query_value(query, "return_mode", "park")
        return self.facade.get_launch_preflight(resolved, request)

    def _command_history_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        return self.command_journal.to_mapping(limit=query_int(query, "limit", 20))
