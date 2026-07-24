from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.processes.rerun_results import (
    rerun_open_backend_known_path,
    rerun_promote_dry_run,
    rerun_promote_to_pending_publish,
)

from .command_results import (
    backend_shutdown_cleanup_failure_payload,
    backend_shutdown_scheduling_failure_payload,
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
    def _request_backend_shutdown_after_response(self) -> tuple[bool, str]:
        shutdown_request = self.shutdown_request
        if shutdown_request is None:
            return False, "Backend shutdown callback is unavailable."

        def _run() -> None:
            try:
                shutdown_request()
            except Exception:
                self.logger.exception("local API backend shutdown callback failed")

        try:
            timer = threading.Timer(0.1, _run)
            timer.daemon = True
            timer.start()
        except Exception as exc:
            self.logger.exception("local API backend shutdown timer start failed")
            return False, f"{type(exc).__name__}: {exc}"
        return True, ""

    def _pipeline_control_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("pipeline.control", "snapshot")
        return self.facade.request_pipeline_control(
            resolved,
            str(request.get("action") or ""),
            confirm_force_stop=request.get("confirm_force_stop") is True,
            expected_run_id=str(request.get("expected_run_id") or ""),
        ).to_mapping()

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
            result = {
                "ok": False,
                "canceled": False,
                "selection_mode": "files",
                "paths": [],
                "message": "Pipeline file picker backend adapter is unavailable.",
                "errors": ["pipeline_file_picker_adapter_unavailable"],
            }
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

    def _rerun_control_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.control", "snapshot")
        return self.facade.request_rerun_stop_after_current(resolved, request).to_mapping()

    def _rerun_continue_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.continue", "snapshot")
        return self.facade.continue_rerun_pending_rows(resolved, request).to_mapping()

    def _rerun_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.preview", "snapshot")
        return self.facade.preview_rerun_csv(resolved, request)

    def _rerun_network_preview_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.network_preview", "snapshot")
        return self.facade.preview_network_rerun_csv(resolved, request)

    def _rerun_network_start_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.network.start_dry_run", "snapshot")
        return self.facade.dry_run_network_rerun_csv_start(resolved, request).to_mapping()

    def _rerun_network_start_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.network.start", "snapshot")
        journal_recorder = None
        record = getattr(self, "_record_command_journal", None)
        if callable(record):
            def journal_recorder(payload: dict[str, Any], request_body: dict[str, Any] | None = None) -> None:
                record(payload, request=request_body, strict=True)

        return self.facade.start_network_rerun_csv_batch(
            resolved,
            request,
            journal_recorder=journal_recorder,
        ).to_mapping()

    def _rerun_network_retry_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.network.retry", "snapshot")
        return self.facade.request_network_rerun_retry(resolved, request).to_mapping()

    def _rerun_open_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.open", "snapshot")
        return rerun_open_backend_known_path(resolved, self.facade.service, request).to_mapping()

    def _rerun_promote_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.promote_dry_run", "snapshot")
        return rerun_promote_dry_run(resolved, request).to_mapping()

    def _rerun_promote_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("rerun.promote", "snapshot")
        return rerun_promote_to_pending_publish(
            resolved,
            request,
            product_version=str(getattr(self.facade, "app_version", "") or ""),
        ).to_mapping()

    def _force_active_work_shutdown_cleanup(self, resolved: Any) -> tuple[list[str], list[str]]:
        messages: list[str] = []
        errors: list[str] = []
        service = getattr(self.facade, "service", None)
        if service is None:
            return messages, ["Backend process cleanup service is unavailable."]

        def run_cleanup(label: str, cleanup: Any, *args: Any) -> None:
            if not callable(cleanup):
                errors.append(f"{label} cleanup is unavailable.")
                return
            try:
                result = cleanup(*args)
            except Exception as exc:
                self.logger.exception("local API %s cleanup failed before backend shutdown: %s", label, exc)
                errors.append(f"{label.capitalize()} cleanup failed: {exc}")
                return
            if result is False:
                errors.append(f"{label.capitalize()} cleanup reported failure.")
                return
            if not isinstance(result, (list, tuple)):
                errors.append(f"{label.capitalize()} cleanup returned no verifiable cleanup evidence.")
                return
            messages.extend(str(item) for item in result if str(item).strip())

        cleanup_tracked = getattr(service, "kill_active_spawned_processes", None)
        run_cleanup("tracked process", cleanup_tracked)
        cleanup_related = getattr(service, "kill_related_pipeline_processes", None)
        run_cleanup("related process", cleanup_related, resolved)
        return messages, errors

    def _backend_lifecycle_reconcile_dry_run_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("backend.lifecycle.reconcile_dry_run", "snapshot")
        return self.facade.preview_lifecycle_reconciliation(resolved, request).to_mapping()

    def _backend_lifecycle_reconcile_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        resolved = self._resolved()
        if resolved is None:
            return resolved_paths_unavailable_payload("backend.lifecycle.reconcile", "snapshot")
        return self.facade.apply_lifecycle_reconciliation(resolved, request).to_mapping()

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
        cleanup_errors: list[str] = []
        post_cleanup_readiness: dict[str, Any] | None = None
        safe_to_close = isinstance(readiness, dict) and readiness.get("safe_to_close") is True
        if not safe_to_close and not force_active_work_shutdown:
            return backend_shutdown_success_payload(readiness)
        if force_active_work_shutdown and not safe_to_close:
            if resolved is None:
                cleanup_errors.append("Resolved paths are unavailable for forced active-work cleanup.")
            else:
                cleanup_messages, cleanup_errors = self._force_active_work_shutdown_cleanup(resolved)
            if not cleanup_errors and resolved is not None:
                try:
                    post_cleanup = self.facade.get_close_readiness(resolved, self._snapshot()).to_mapping()
                    if isinstance(post_cleanup, dict):
                        post_cleanup_readiness = post_cleanup
                    else:
                        cleanup_errors.append("Post-cleanup close-readiness evidence was malformed.")
                except Exception as exc:
                    self.logger.exception(
                        "local API close-readiness verification failed after forced backend cleanup: %s",
                        exc,
                    )
                    cleanup_errors.append(f"Post-cleanup close readiness could not be verified: {exc}")
                if (
                    post_cleanup_readiness is None
                    or post_cleanup_readiness.get("safe_to_close") is not True
                ):
                    if not cleanup_errors:
                        cleanup_errors.append(
                            str(post_cleanup_readiness.get("reason") or "Post-cleanup close readiness remains unsafe.")
                        )
            if cleanup_errors:
                return backend_shutdown_cleanup_failure_payload(
                    readiness,
                    cleanup_messages=cleanup_messages,
                    cleanup_errors=cleanup_errors,
                    post_cleanup_readiness=post_cleanup_readiness,
                )
        shutdown_scheduled, scheduling_error = self._request_backend_shutdown_after_response()
        if not shutdown_scheduled:
            return backend_shutdown_scheduling_failure_payload(
                readiness,
                scheduling_error=scheduling_error,
                force_active_work_shutdown=force_active_work_shutdown,
                cleanup_messages=cleanup_messages,
                post_cleanup_readiness=post_cleanup_readiness,
            )
        return backend_shutdown_success_payload(
            readiness,
            force_active_work_shutdown=force_active_work_shutdown,
            cleanup_messages=cleanup_messages,
            post_cleanup_readiness=post_cleanup_readiness,
        )
