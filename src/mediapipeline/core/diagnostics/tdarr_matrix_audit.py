"""Backend-owned Tdarr Matrix audit command policy and service runner."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.kernel.dto_base import json_safe
from mediapipeline.core.kernel.runtime.subprocess_runner import run_capture
from mediapipeline.core.diagnostics.tdarr_matrix_proof import (
    tdarr_case_keys_for_pack,
    tdarr_expected_manifest_count,
    tdarr_proof_pack_root,
    tdarr_proof_runs_root,
)

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional desktop dependency
    psutil = None  # type: ignore


TDARR_MATRIX_AUDIT_COMMAND = "diagnostics.tdarr_matrix_audit"
TDARR_MATRIX_AUDIT_REFRESH_HINT = "diagnostics"
TDARR_MATRIX_AUDIT_PROGRESS_SCHEMA_VERSION = "desktop_tdarr_matrix_audit_progress.v1"
TDARR_MATRIX_AUDIT_TOOL_MODULE = "mediapipeline.tools.dev.tdarr_matrix_audit"
TDARR_PROOF_PACK_TOOL_MODULE = "mediapipeline.tools.dev.tdarr_proof_pack"
TDARR_MATRIX_AUDIT_ALLOWED_ACTIONS = (
    "prepare-proof-pack",
    "report",
    "smoke-pack",
    "proof-pack",
    "strict-report",
    "cleanup-plan",
    "cleanup-archive",
    "cleanup-delete",
)
TDARR_MATRIX_AUDIT_FINDINGS_PREVIEW_LIMIT = 50

# Number of diagnostic buckets the run-samples harness iterates. Must stay equal to
# len(materialize_tdarr_test_library.BUCKET_SERIES) and tdarr_matrix_audit.BUCKET_ORDER;
# enforced by test_bucket_definitions_are_in_sync. Used to size the runner timeout (G1).
TDARR_MATRIX_AUDIT_BUCKET_COUNT = 6
# Fixed slack added on top of the worst-case prepare + sample budget so audit/IO overhead
# cannot trip the outer process timeout.
TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS = 300

TDARR_MATRIX_AUDIT_PRESETS: dict[str, dict[str, Any]] = {
    "prepare-proof-pack": {
        "label": "Prepare Tdarr Proof Pack",
        "mode": "proof-pack-materialize",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 7200,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
    "report": {
        "label": "Prepare Tdarr Proof Pack Audit Report",
        "mode": "report",
        "report_only": True,
        "prepare_timeout_seconds": 1800,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 900,
        "hash_sources": True,
    },
    "smoke-pack": {
        "label": "Run Tdarr Smoke Pack",
        "mode": "run-samples",
        "report_only": True,
        "prepare_timeout_seconds": 600,
        "sample_timeout_seconds": 900,
        "samples_per_bucket": 0,
        "sample_count_hint": tdarr_expected_manifest_count("smoke-pack"),
        "case_pack": "smoke-pack",
        "runner_timeout_seconds": 24000,
        "background": True,
    },
    "proof-pack": {
        "label": "Run Tdarr Proof Pack",
        "mode": "run-samples",
        "report_only": True,
        "prepare_timeout_seconds": 600,
        "sample_timeout_seconds": 1800,
        "samples_per_bucket": 0,
        "sample_count_hint": tdarr_expected_manifest_count("proof-pack"),
        "case_pack": "proof-pack",
        "runner_timeout_seconds": 172200,
        "background": True,
    },
    # strict-report is a STATIC gate (G9): it runs the pipeline validate / effective-config /
    # queue-snapshot commands, audits the queue snapshot and path containment, and verifies
    # source hashes (hash_sources). It does NOT process media, and it fails only on
    # critical/error findings -- audio-only "processed successfully" stays an advisory warning
    # and does not fail the gate. See docs/dev/tdarr-matrix-audit-gaps.md G9.
    "strict-report": {
        "label": "Run Tdarr Proof Pack Strict Report Gate",
        "mode": "report",
        "report_only": False,
        "prepare_timeout_seconds": 1800,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 900,
        "hash_sources": True,
    },
    "cleanup-plan": {
        "label": "Plan Tdarr Full Matrix Cleanup",
        "mode": "proof-pack-cleanup",
        "cleanup_action": "plan",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 900,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
    "cleanup-archive": {
        "label": "Archive Tdarr Full Matrix Evidence",
        "mode": "proof-pack-cleanup",
        "cleanup_action": "archive",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 1800,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
    "cleanup-delete": {
        "label": "Delete Verified Tdarr Full Matrix",
        "mode": "proof-pack-cleanup",
        "cleanup_action": "delete",
        "report_only": True,
        "prepare_timeout_seconds": 0,
        "sample_timeout_seconds": 0,
        "samples_per_bucket": 0,
        "runner_timeout_seconds": 3600,
        "tool_module": TDARR_PROOF_PACK_TOOL_MODULE,
    },
}



from mediapipeline.core.diagnostics import tdarr_matrix_audit_support as _audit_support
from mediapipeline.core.diagnostics.tdarr_matrix_audit_support import *  # noqa: F403


def _with_process_adapter(function, *args, **kwargs):
    original = _audit_support.psutil
    try:
        _audit_support.psutil = psutil
        return function(*args, **kwargs)
    finally:
        _audit_support.psutil = original


def tdarr_matrix_incomplete_full_run_evidence(*args, **kwargs):
    return _with_process_adapter(
        _audit_support.tdarr_matrix_incomplete_full_run_evidence,
        *args,
        **kwargs,
    )


def tdarr_matrix_background_close_evidence(*args, **kwargs):
    return _with_process_adapter(
        _audit_support.tdarr_matrix_background_close_evidence,
        *args,
        **kwargs,
    )


def tdarr_matrix_incomplete_full_run(*args, **kwargs):
    return _with_process_adapter(
        _audit_support.tdarr_matrix_incomplete_full_run,
        *args,
        **kwargs,
    )


def _write_tdarr_background_process_metadata(path: Path, payload: dict[str, Any]) -> None:
    """Atomically persist and read-verify lifecycle identity in the target directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        persisted = json.loads(path.read_text(encoding="utf-8"))
        if persisted != payload:
            raise OSError(f"lifecycle metadata verification failed for {path}")
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


class TdarrMatrixAuditServiceMixin:
    def tdarr_matrix_background_close_evidence(self, workspace_root: Path) -> dict[str, Any]:
        """Expose background-process close evidence through the diagnostics service boundary."""
        return tdarr_matrix_background_close_evidence(Path(workspace_root))

    """Runs the Tdarr Matrix developer audit tool through the stable tool wrapper."""

    def tdarr_matrix_audit_python_path(self) -> Path:
        candidates = (
            self.workspace_root / "apps" / "desktop" / "runtime" / "Python" / "python.exe",
            self.app_root / "runtime" / "Python" / "python.exe",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path(sys.executable)

    def run_tdarr_matrix_audit(
        self,
        *,
        action: str,
        case_keys: list[str] | tuple[str, ...] | None = None,
        confirm_delete_full_matrix: bool = False,
    ) -> dict[str, Any]:
        preset = tdarr_matrix_audit_preset(action)
        if preset is None:
            raise ValueError(f"Unsupported Tdarr Matrix audit action: {action}")
        workspace_root = Path(self.workspace_root)
        runner = tdarr_matrix_runner_script(workspace_root)
        library_root = tdarr_matrix_default_library_root(workspace_root)
        runs_root = tdarr_matrix_default_runs_root(workspace_root)
        entrypoint = tdarr_matrix_default_entrypoint(workspace_root)
        python_path = self.tdarr_matrix_audit_python_path()
        tool_module = str(preset.get("tool_module") or TDARR_MATRIX_AUDIT_TOOL_MODULE)
        if not runner.exists():
            return self._tdarr_matrix_missing_result(preset, runner, library_root)
        manifest_path = library_root / "manifests" / "materialized_library.csv"
        if str(preset.get("mode") or "") in {"report", "run-samples"} and not manifest_path.exists():
            return self._tdarr_matrix_missing_library_result(preset, library_root, manifest_path)
        powershell = self._tdarr_matrix_powershell_host()
        background = bool(preset.get("background"))
        if background:
            existing_evidence = tdarr_matrix_incomplete_full_run_evidence(
                runs_root,
                selected_count=_int_value(preset.get("sample_count_hint")),
                psutil_module=psutil,
            )
            existing = existing_evidence.get("active")
            if existing is not None:
                return self._tdarr_matrix_existing_full_run_result(
                    preset=preset,
                    library_root=library_root,
                    run_root=existing,
                    process_state=existing_evidence.get("active_process") if isinstance(existing_evidence, dict) else None,
                )
            stale = existing_evidence.get("stale") if isinstance(existing_evidence, dict) else None
            if stale is not None:
                return self._tdarr_matrix_stale_full_run_result(
                    preset=preset,
                    library_root=library_root,
                    run_root=stale,
                    process_state=existing_evidence.get("stale_process") if isinstance(existing_evidence, dict) else None,
                )
        run_id = tdarr_matrix_background_run_id(str(preset["action"]), runs_root) if background else ""
        audit_args = tdarr_matrix_audit_arguments(
            action=str(preset["action"]),
            library_root=library_root,
            powershell=powershell,
            entrypoint=entrypoint,
            runs_root=runs_root,
            case_keys=case_keys,
            run_id=run_id,
            confirm_delete_full_matrix=confirm_delete_full_matrix,
        )
        args = [
            str(python_path),
            str(runner),
            tool_module,
            *audit_args,
        ]
        command_line = subprocess.list2cmdline(args)
        logger = getattr(self, "logger", None)
        if logger is not None:
            logger.info("Tdarr Matrix audit requested: %s", command_line)
        env = self._tdarr_matrix_launch_environment()
        started = time.monotonic()
        if background:
            return self._run_tdarr_matrix_audit_background(
                args=args,
                command_line=command_line,
                workspace_root=workspace_root,
                env=env,
                preset=preset,
                library_root=library_root,
                runs_root=runs_root,
                run_id=run_id,
                started=started,
            )
        capture = run_capture(
            args,
            cwd=str(workspace_root),
            env=env,
            encoding="utf-8",
            errors="replace",
            timeout_seconds=tdarr_matrix_audit_runner_timeout(preset),
            extra_popen_kwargs=self._tdarr_matrix_subprocess_kwargs(),
            label="tdarr matrix audit",
            kill_tree=getattr(self, "kill_process_tree", None),
        )
        stdout = capture.stdout or ""
        parsed = _parse_last_json_object(stdout)
        stderr = capture.stderr or capture.kill_message or ""
        returncode = -1 if capture.returncode is None else int(capture.returncode)
        result: dict[str, Any] = {
            "success": returncode == 0 and not capture.timed_out,
            "timed_out": bool(capture.timed_out),
            "returncode": returncode,
            "command": command_line,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_seconds": time.monotonic() - started,
            "library_root": str(library_root),
            **preset,
            **parsed,
        }
        return result

    def _run_tdarr_matrix_audit_background(
        self,
        *,
        args: list[str],
        command_line: str,
        workspace_root: Path,
        env: dict[str, str],
        preset: dict[str, Any],
        library_root: Path,
        runs_root: Path,
        run_id: str,
        started: float,
    ) -> dict[str, Any]:
        runs_root.mkdir(parents=True, exist_ok=True)
        log_root = runs_root / "_background"
        log_root.mkdir(parents=True, exist_ok=True)
        stdout_path = log_root / f"{run_id}.stdout.log"
        stderr_path = log_root / f"{run_id}.stderr.log"
        metadata_path = _tdarr_matrix_background_process_metadata_path(runs_root, run_id)
        run_root = runs_root / run_id
        audit_dir = run_root / "manifests" / "audit"

        def failure_result(
            error: BaseException,
            *,
            pid: int = 0,
            partial_start: bool = False,
            cleanup_evidence: str = "",
        ) -> dict[str, Any]:
            error_text = " ".join(str(error).split()) or type(error).__name__
            cleanup_text = f" Cleanup: {cleanup_evidence}" if cleanup_evidence else ""
            return {
                "success": False,
                "timed_out": False,
                "background_started": False,
                "partial_start": partial_start,
                "reconciliation_required": partial_start,
                "returncode": -1,
                "pid": pid,
                "run_id": run_id,
                "command": command_line,
                "stdout": f"Background stdout: {stdout_path}",
                "stderr": (
                    f"Tdarr Matrix background lifecycle persistence failed: {error_text}."
                    f"{cleanup_text} Background stderr: {stderr_path}"
                ),
                "elapsed_seconds": time.monotonic() - started,
                "library_root": str(library_root),
                "run_root": str(run_root),
                "report_path": str(audit_dir / "tdarr_matrix_audit_report.json"),
                "process_metadata_path": str(metadata_path),
                "selected_count": _int_value(preset.get("sample_count_hint")),
                "finding_count": 0,
                **preset,
            }

        reservation = {
            "schema_version": "tdarr_matrix_background_process.v1",
            "lifecycle_status": "launch_reserved",
            "run_id": run_id,
            "pid": 0,
            "process_start_time": "",
            "started_at": datetime.now(UTC).isoformat(),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
        try:
            _write_tdarr_background_process_metadata(metadata_path, reservation)
        except Exception as exc:
            return failure_result(exc)

        stdout_handle = stdout_path.open("ab")
        stderr_handle = stderr_path.open("ab")
        kwargs: dict[str, Any] = {
            "cwd": str(workspace_root),
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": stdout_handle,
            "stderr": stderr_handle,
        }
        kwargs.update(self._tdarr_matrix_subprocess_kwargs())
        if os.name == "nt":
            kwargs.setdefault(
                "creationflags",
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            kwargs.setdefault("start_new_session", True)
        try:
            proc = subprocess.Popen(args, **kwargs)
        except Exception:
            with contextlib.suppress(OSError):
                metadata_path.unlink(missing_ok=True)
            raise
        finally:
            stdout_handle.close()
            stderr_handle.close()
        pid = int(getattr(proc, "pid", 0) or 0)
        process_start_time = _tdarr_matrix_process_start_time_text(pid, psutil_module=psutil)
        process_metadata = {
            "schema_version": "tdarr_matrix_background_process.v1",
            "lifecycle_status": "active",
            "run_id": run_id,
            "pid": pid,
            "process_start_time": process_start_time,
            "started_at": datetime.now(UTC).isoformat(),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
        try:
            _write_tdarr_background_process_metadata(metadata_path, process_metadata)
        except Exception as exc:
            cleanup_evidence = ""
            try:
                kill_tree = getattr(self, "kill_process_tree", None)
                if callable(kill_tree):
                    cleanup_evidence = str(kill_tree(proc, "Tdarr Matrix background audit"))
                else:
                    proc.terminate()
                    proc.wait(timeout=10)
                    cleanup_evidence = f"Terminated exact child PID {pid}."
            except Exception as cleanup_exc:
                cleanup_evidence = f"Exact-child cleanup could not be verified: {cleanup_exc}"
            return failure_result(
                exc,
                pid=pid,
                partial_start=True,
                cleanup_evidence=cleanup_evidence,
            )
        return {
            "success": True,
            "timed_out": False,
            "background_started": True,
            "returncode": 0,
            "pid": pid,
            "run_id": run_id,
            "command": command_line,
            "stdout": f"Background stdout: {stdout_path}",
            "stderr": f"Background stderr: {stderr_path}",
            "elapsed_seconds": time.monotonic() - started,
            "library_root": str(library_root),
            "run_root": str(run_root),
            "report_path": str(audit_dir / "tdarr_matrix_audit_report.json"),
            "selected_count": _int_value(preset.get("sample_count_hint")),
            "finding_count": 0,
            **preset,
        }

    def _tdarr_matrix_existing_full_run_result(
        self,
        *,
        preset: dict[str, Any],
        library_root: Path,
        run_root: Path,
        process_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = run_root.name
        audit_dir = run_root / "manifests" / "audit"
        process_state = process_state or {}
        return {
            "success": True,
            "timed_out": False,
            "already_running": True,
            "returncode": 0,
            "pid": _int_value(process_state.get("pid")),
            "run_id": run_id,
            "command": "",
            "stdout": "",
            "stderr": "",
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            "run_root": str(run_root),
            "report_path": str(audit_dir / "tdarr_matrix_audit_report.json"),
            "selected_count": _int_value(preset.get("sample_count_hint")),
            "finding_count": 0,
            **preset,
        }

    def _tdarr_matrix_stale_full_run_result(
        self,
        *,
        preset: dict[str, Any],
        library_root: Path,
        run_root: Path,
        process_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = run_root.name
        audit_dir = run_root / "manifests" / "audit"
        process_state = process_state or {}
        stale_reason = str(process_state.get("reason") or "stale_incomplete_run")
        return {
            "success": False,
            "timed_out": False,
            "already_running": False,
            "stale_incomplete_run": True,
            "stale_reason": stale_reason,
            "returncode": 2,
            "pid": _int_value(process_state.get("pid")),
            "run_id": run_id,
            "command": "",
            "stdout": "",
            "stderr": f"Stale Tdarr Proof Pack run requires review before another proof run starts: {stale_reason}",
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            "run_root": str(run_root),
            "report_path": str(audit_dir / "tdarr_matrix_audit_report.json"),
            "selected_count": _int_value(preset.get("sample_count_hint")),
            "finding_count": 0,
            "process_metadata_path": str(process_state.get("metadata_path") or ""),
            **preset,
        }

    def _tdarr_matrix_missing_result(self, preset: dict[str, Any], runner: Path, library_root: Path) -> dict[str, Any]:
        return {
            "success": False,
            "timed_out": False,
            "returncode": 127,
            "command": f'"{self.tdarr_matrix_audit_python_path()}" "{runner}" {TDARR_MATRIX_AUDIT_TOOL_MODULE}',
            "stdout": "",
            "stderr": f"Tdarr Matrix audit runner not found: {runner}",
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            **preset,
        }

    def _tdarr_matrix_missing_library_result(self, preset: dict[str, Any], library_root: Path, manifest_path: Path) -> dict[str, Any]:
        guidance = (
            "python -m mediapipeline.tools.dev.tdarr_proof_pack materialize"
        )
        return {
            "success": False,
            "timed_out": False,
            "returncode": 2,
            "command": "",
            "stdout": "",
            "stderr": (
                f"Tdarr Proof Pack is not materialized (missing {manifest_path}). "
                f"Generate it first, then re-run this audit: {guidance}"
            ),
            "elapsed_seconds": 0.0,
            "library_root": str(library_root),
            **preset,
        }

    def _tdarr_matrix_powershell_host(self) -> str:
        resolver = getattr(self, "resolve_powershell_host", None)
        if callable(resolver):
            resolved = resolver()
            if resolved:
                return str(resolved)
        return "pwsh"

    def _tdarr_matrix_launch_environment(self) -> dict[str, str]:
        builder = getattr(self, "_build_launch_environment", None)
        env = builder() if callable(builder) else dict(os.environ)
        src_root = Path(self.workspace_root) / "src"
        if src_root.exists():
            src_root_text = str(src_root)
            existing = env.get("PYTHONPATH", "")
            parts = [part for part in existing.split(os.pathsep) if part]
            if src_root_text.casefold() not in {part.casefold() for part in parts}:
                parts.insert(0, src_root_text)
            env["PYTHONPATH"] = os.pathsep.join(parts)
        return env

    def _tdarr_matrix_subprocess_kwargs(self) -> dict[str, Any]:
        kwargs = getattr(self, "_subprocess_kwargs_hidden", None)
        if callable(kwargs):
            value = kwargs()
            return dict(value or {}) if isinstance(value, dict) else {}
        return {}
