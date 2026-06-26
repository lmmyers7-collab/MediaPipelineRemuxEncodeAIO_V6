from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.desktop.api.path_dialogs import select_windows_paths_with_dialog
from mediapipeline.desktop.application.dto import CommandResult

from .command_results import (
    backend_shutdown_success_payload,
    backend_shutdown_unavailable_payload,
    close_readiness_unavailable_payload,
    resolved_paths_unavailable_payload,
)


def _validate_pipeline_single_file_browse_path(raw_path: str) -> dict[str, Any]:
    path_text = str(raw_path or "").strip()
    validation: dict[str, Any] = {
        "schema_version": "desktop_pipeline_single_file_validation.v1",
        "path": path_text,
        "exists": False,
        "is_file": False,
        "is_absolute": False,
        "media_suffix": "",
        "media_suffix_supported": False,
        "supported_suffixes": sorted(MEDIA_FILE_SUFFIXES),
        "status_state": "blocked",
        "message": "No file was selected.",
    }
    if not path_text:
        return validation
    try:
        candidate = Path(path_text)
        validation["is_absolute"] = candidate.is_absolute()
        validation["media_suffix"] = candidate.suffix.casefold()
        validation["media_suffix_supported"] = validation["media_suffix"] in MEDIA_FILE_SUFFIXES
        validation["exists"] = candidate.exists()
        validation["is_file"] = candidate.is_file()
    except OSError as exc:
        validation["message"] = f"Selected single-file path could not be checked: {exc}"
        return validation

    if not validation["is_absolute"]:
        validation["message"] = "Selected single-file path is not absolute."
    elif not validation["exists"]:
        validation["message"] = "Selected single-file path does not exist."
    elif not validation["is_file"]:
        validation["message"] = "Selected single-file path exists but is not a file."
    elif not validation["media_suffix_supported"]:
        suffix = validation["media_suffix"] or "(none)"
        validation["message"] = f"Selected single-file path uses unsupported media suffix {suffix}."
    else:
        validation["status_state"] = "ready"
        validation["message"] = "Selected single-file path is a supported media file. Review start readiness before launching."
    return validation


class LocalApiProcessCommandPayloadMixin:
    def _request_backend_shutdown_after_response(self) -> None:
        shutdown_request = self.shutdown_request
        if shutdown_request is None:
            return

        def _run() -> None:
            try:
                shutdown_request()
            except Exception:
                self.logger.exception("local API backend shutdown callback failed")

        try:
            timer = threading.Timer(0.1, _run)
            timer.daemon = True
            timer.start()
        except Exception:
            self.logger.exception("local API backend shutdown timer start failed")

    def _pipeline_control_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("pipeline.control", "snapshot")
        return self.facade.request_pipeline_control(resolved, str(request.get("action") or "")).to_mapping()

    def _pipeline_browse_file_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        requested_mode = str(request.get("selection_mode") or "files").strip().lower()
        if requested_mode not in {"", "files"}:
            return CommandResult(
                command="pipeline.browse_file",
                ok=False,
                severity="error",
                message="Pipeline single-file browse only supports selecting files.",
                errors=["unsupported_selection_mode"],
                data={
                    "schema_version": "desktop_pipeline_single_file_browse.v1",
                    "allowed_selection_modes": ["files"],
                    "writes_config": False,
                    "stages_only": True,
                    "launches_work": False,
                },
            ).to_mapping()

        initial_path = str(request.get("initial_path") or "")
        picker = getattr(self, "_pipeline_file_picker", None)
        picker_kwargs = {
            "selection_mode": "files",
            "initial_path": initial_path,
            "dialog_title": "Select one media file for Pipeline single-file mode",
            "file_filter": "Media files (*.mkv;*.mp4;*.m4v;*.mov;*.avi;*.ts;*.m2ts;*.webm)|*.mkv;*.mp4;*.m4v;*.mov;*.avi;*.ts;*.m2ts;*.webm|All files (*.*)|*.*",
        }
        if callable(picker):
            result = picker(**picker_kwargs)
        else:
            result = select_windows_paths_with_dialog(**picker_kwargs)
        paths = [str(path).strip() for path in result.get("paths", []) if str(path).strip()]
        selected_path = paths[0] if paths else ""
        canceled = bool(result.get("canceled", False))
        picker_ok = bool(result.get("ok", False))
        validation = _validate_pipeline_single_file_browse_path(selected_path)
        validation_ready = validation.get("status_state") == "ready"
        ok = picker_ok and (canceled or validation_ready)
        if canceled:
            message = "Windows file browser canceled. No Launch field was changed."
            severity = "info"
        elif picker_ok and validation_ready:
            message = f"Windows file browser selected single file: {selected_path}"
            severity = "info"
        elif picker_ok:
            message = str(validation.get("message") or "Selected single-file path did not pass backend validation.")
            severity = "warning"
        else:
            message = str(result.get("message") or "Windows file browser failed.")
            severity = "error"
        return CommandResult(
            command="pipeline.browse_file",
            ok=ok,
            severity=severity,
            message=message,
            errors=[str(error) for error in result.get("errors", [])],
            data={
                "schema_version": "desktop_pipeline_single_file_browse.v1",
                "paths": paths,
                "selected_path": selected_path,
                "selection_mode": "files",
                "canceled": canceled,
                "path_count": len(paths),
                "source": "windows_file_browser",
                "validation": validation,
                "writes_config": False,
                "stages_only": True,
                "launches_work": False,
            },
        ).to_mapping()

    def _pipeline_start_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("pipeline.start", "snapshot")
        return self.facade.start_pipeline_process(resolved, request).to_mapping()

    def _audit_start_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.start", "snapshot")
        return self.facade.start_audit_process(resolved, request).to_mapping()

    def _audit_stop_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("audit.stop", "snapshot")
        return self.facade.stop_audit_process(resolved, request).to_mapping()

    def _rerun_start_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.start", "snapshot")
        return self.facade.start_rerun_csv_process(resolved, request).to_mapping()

    def _force_active_work_shutdown_cleanup(self, resolved: Any) -> list[str]:
        messages: list[str] = []
        service = getattr(self.facade, "service", None)
        if service is None:
            return messages
        cleanup_tracked = getattr(service, "kill_active_spawned_processes", None)
        if callable(cleanup_tracked):
            try:
                messages.extend(str(item) for item in cleanup_tracked())
            except Exception as exc:
                self.logger.exception("local API tracked process cleanup failed before backend shutdown: %s", exc)
                messages.append(f"Tracked process cleanup failed: {exc}")
        cleanup_related = getattr(service, "kill_related_pipeline_processes", None)
        if callable(cleanup_related):
            try:
                messages.extend(str(item) for item in cleanup_related(resolved))
            except Exception as exc:
                self.logger.exception("local API related process cleanup failed before backend shutdown: %s", exc)
                messages.append(f"Related process cleanup failed: {exc}")
        return [message for message in messages if str(message).strip()]

    def _backend_shutdown_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.shutdown_request is None:
            return backend_shutdown_unavailable_payload()
        readiness = None
        resolved = self._resolved()
        if resolved is None:
            readiness = close_readiness_unavailable_payload()
        else:
            try:
                readiness = self.facade.get_close_readiness(resolved, self._snapshot()).to_mapping()
            except Exception as exc:
                self.logger.exception("local API close-readiness verification failed before backend shutdown: %s", exc)
                readiness = {
                    "safe_to_close": False,
                    "state": "unknown",
                    "active_work": True,
                    "reason": "Close readiness could not be verified before backend shutdown.",
                }
        force_active_work_shutdown = request.get("force_active_work_shutdown", False) is True
        cleanup_messages: list[str] = []
        if (
            isinstance(readiness, dict)
            and not bool(readiness.get("safe_to_close", True))
            and not force_active_work_shutdown
        ):
            return backend_shutdown_success_payload(readiness)
        if (
            force_active_work_shutdown
            and resolved is not None
            and isinstance(readiness, dict)
            and not bool(readiness.get("safe_to_close", True))
        ):
            cleanup_messages = self._force_active_work_shutdown_cleanup(resolved)
        self._request_backend_shutdown_after_response()
        return backend_shutdown_success_payload(
            readiness,
            force_active_work_shutdown=force_active_work_shutdown,
            cleanup_messages=cleanup_messages,
        )
