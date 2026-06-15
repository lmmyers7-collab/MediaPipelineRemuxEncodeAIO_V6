"""Diagnostics facade command adapter for Tdarr Matrix audits."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from mediapipeline.core.diagnostics.tdarr_matrix_audit import (
    TDARR_MATRIX_AUDIT_COMMAND,
    tdarr_matrix_audit_exception_result,
    tdarr_matrix_audit_invalid_action_result,
    tdarr_matrix_audit_preset,
    tdarr_matrix_audit_result,
    tdarr_matrix_audit_unavailable_result,
)
from mediapipeline.core.diagnostics.tdarr_matrix_console import (
    TDARR_MATRIX_RERUN_COMMAND,
    tdarr_matrix_compare_runs_payload,
    tdarr_matrix_console_payload,
    tdarr_matrix_evidence_open_result,
    tdarr_matrix_rerun_case_keys,
    tdarr_matrix_runs_payload,
)


class DiagnosticsTdarrMatrixAuditFacadeMixin:
    """Runs allowlisted Tdarr Matrix diagnostics presets through the backend."""

    def run_tdarr_matrix_audit(self, request: dict[str, Any]) -> Any:
        preset = tdarr_matrix_audit_preset(request.get("action"))
        if preset is None:
            return tdarr_matrix_audit_invalid_action_result(request.get("action"))
        runner = getattr(self.service, "run_tdarr_matrix_audit", None)
        if not callable(runner):
            return tdarr_matrix_audit_unavailable_result("run_tdarr_matrix_audit is required.")
        lock, block_message = self._acquire_tdarr_matrix_audit_lock()
        if block_message:
            return tdarr_matrix_audit_unavailable_result(block_message)
        try:
            result = runner(
                action=str(preset["action"]),
                confirm_delete_full_matrix=bool(request.get("confirm_delete_full_matrix")),
            )
        except Exception as exc:
            return tdarr_matrix_audit_exception_result(exc)
        finally:
            self._release_tdarr_matrix_audit_lock(lock)
        if not isinstance(result, dict):
            return tdarr_matrix_audit_unavailable_result("run_tdarr_matrix_audit must return a dictionary.")
        return tdarr_matrix_audit_result(result)

    def read_tdarr_matrix_console(self, request: dict[str, Any]) -> dict[str, Any]:
        workspace_root = getattr(self.service, "workspace_root", None)
        if workspace_root is None:
            return tdarr_matrix_console_payload_from_error("workspace_root is required.")
        try:
            return tdarr_matrix_console_payload(
                Path(workspace_root),
                run_id=request.get("run_id", ""),
                finding_limit=_safe_int(request.get("finding_limit"), 100),
            )
        except Exception as exc:
            return tdarr_matrix_console_payload_from_error(str(exc))

    def list_tdarr_matrix_runs(self, request: dict[str, Any] | None = None) -> dict[str, Any]:
        workspace_root = getattr(self.service, "workspace_root", None)
        if workspace_root is None:
            return tdarr_matrix_runs_payload_from_error("workspace_root is required.")
        request = request or {}
        try:
            return tdarr_matrix_runs_payload(Path(workspace_root), limit=_safe_int(request.get("limit"), 50))
        except Exception as exc:
            return tdarr_matrix_runs_payload_from_error(str(exc))

    def compare_tdarr_matrix_runs(self, request: dict[str, Any]) -> dict[str, Any]:
        workspace_root = getattr(self.service, "workspace_root", None)
        if workspace_root is None:
            return tdarr_matrix_compare_payload_from_error("workspace_root is required.")
        try:
            return tdarr_matrix_compare_runs_payload(
                Path(workspace_root),
                left_run_id=request.get("left_run_id") or request.get("left") or "",
                right_run_id=request.get("right_run_id") or request.get("right") or "",
            )
        except Exception as exc:
            return tdarr_matrix_compare_payload_from_error(str(exc))

    def open_tdarr_matrix_evidence(self, request: dict[str, Any]) -> Any:
        opener = getattr(self.service, "open_path", None)
        workspace_root = getattr(self.service, "workspace_root", None)
        if workspace_root is None:
            return tdarr_matrix_audit_unavailable_result("workspace_root is required.")
        return tdarr_matrix_evidence_open_result(Path(workspace_root), request, opener=opener)

    def rerun_tdarr_matrix_cases(self, request: dict[str, Any]) -> Any:
        workspace_root = getattr(self.service, "workspace_root", None)
        if workspace_root is None:
            return tdarr_matrix_audit_unavailable_result("workspace_root is required.")
        try:
            case_keys = tdarr_matrix_rerun_case_keys(Path(workspace_root), request)
        except Exception as exc:
            return tdarr_matrix_rerun_unavailable_result(str(exc))
        if not case_keys:
            return tdarr_matrix_rerun_unavailable_result("No Tdarr Matrix cases were selected for rerun.")
        runner = getattr(self.service, "run_tdarr_matrix_audit", None)
        if not callable(runner):
            return tdarr_matrix_audit_unavailable_result("run_tdarr_matrix_audit is required.")
        lock, block_message = self._acquire_tdarr_matrix_audit_lock()
        if block_message:
            return tdarr_matrix_audit_unavailable_result(block_message)
        try:
            result = runner(action="proof-pack", case_keys=case_keys)
        except Exception as exc:
            return tdarr_matrix_audit_exception_result(exc)
        finally:
            self._release_tdarr_matrix_audit_lock(lock)
        if not isinstance(result, dict):
            return tdarr_matrix_audit_unavailable_result("run_tdarr_matrix_audit must return a dictionary.")
        command_result = tdarr_matrix_audit_result(result)
        data = dict(getattr(command_result, "data", {}) or {})
        data.update(
            {
                "source_run_id": str(request.get("source_run_id") or ""),
                "selection": str(request.get("selection") or ""),
                "case_keys": case_keys,
                "rerun_case_count": len(case_keys),
            }
        )
        return replace(command_result, command=TDARR_MATRIX_RERUN_COMMAND, data=data)

    def _acquire_tdarr_matrix_audit_lock(self) -> tuple[object | None, str]:
        lock = getattr(self, "_diagnostics_command_lock", None)
        if lock is None:
            return None, ""
        try:
            acquired = lock.acquire(blocking=False)
        except Exception as exc:
            self._log_tdarr_matrix_audit_exception("Tdarr Matrix audit lock acquisition failed", exc)
            return None, f"{TDARR_MATRIX_AUDIT_COMMAND} blocked because the diagnostics command lock could not be verified: {exc}"
        if not acquired:
            return None, f"{TDARR_MATRIX_AUDIT_COMMAND} blocked because another diagnostics command is already in progress."
        return lock, ""

    def _release_tdarr_matrix_audit_lock(self, lock: object | None) -> None:
        if lock is None:
            return
        try:
            lock.release()  # type: ignore[attr-defined]
        except Exception as exc:
            self._log_tdarr_matrix_audit_exception("Tdarr Matrix audit lock release failed", exc)

    def _log_tdarr_matrix_audit_exception(self, message: str, exc: Exception) -> None:
        logger = getattr(getattr(self, "service", None), "logger", None)
        if logger is None:
            return
        try:
            logger.warning("%s: %s", message, exc, exc_info=True)
        except Exception:
            return


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return default


def tdarr_matrix_console_payload_from_error(message: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_tdarr_matrix_console.v1",
        "error": message,
        "runs": [],
        "findings": [],
        "finding_count": 0,
    }


def tdarr_matrix_runs_payload_from_error(message: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_tdarr_matrix_runs.v1",
        "error": message,
        "runs": [],
        "run_count": 0,
    }


def tdarr_matrix_compare_payload_from_error(message: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_tdarr_matrix_compare.v1",
        "error": message,
        "counts": {"new": 0, "resolved": 0, "repeated": 0, "changed": 0},
        "new": [],
        "resolved": [],
        "repeated": [],
        "changed": [],
    }


def tdarr_matrix_rerun_unavailable_result(reason: str) -> Any:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(
        command=TDARR_MATRIX_RERUN_COMMAND,
        ok=False,
        message=f"Tdarr Matrix targeted rerun is not available: {reason}",
        severity="error",
        errors=[reason],
        refresh_hint="diagnostics",
        data={"writes_canonical_tdarr_cache": False},
    )


__all__ = [
    "DiagnosticsTdarrMatrixAuditFacadeMixin",
]
