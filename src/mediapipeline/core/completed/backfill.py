from __future__ import annotations

from pathlib import Path

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


def completed_backfill_script_path(resolved: ResolvedPaths) -> Path:
    return resolved.pipeline_path.parent / "Backfill-CompletedManifest.ps1"


def validate_completed_backfill_request(
    resolved: ResolvedPaths,
    *,
    outsource: Path | None,
    script_path: Path | None = None,
) -> tuple[bool, str]:
    if not resolved.powershell_host:
        return False, "PowerShell 7 (pwsh) not found — cannot run backfill script."
    if not resolved.local_base:
        return False, "LocalBase not resolved from config; cannot locate manifest."
    if not outsource:
        return False, "Outsource path not set in config; backfill needs the sidecar source."

    script = script_path or completed_backfill_script_path(resolved)
    if not script.exists():
        return False, f"Backfill script not found: {script}"
    return True, ""


def build_completed_backfill_args(
    resolved: ResolvedPaths,
    *,
    outsource: Path,
    script_path: Path | None = None,
    dry_run: bool = False,
    checkpoint_path: Path | str | None = None,
) -> list[str]:
    script = script_path or completed_backfill_script_path(resolved)
    args = [
        str(resolved.powershell_host),
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(script),
        "-OutsourceRoot",
        str(outsource),
        "-LocalBase",
        str(resolved.local_base),
    ]
    if dry_run:
        args.append("-DryRun")
    if checkpoint_path:
        args.extend(["-CheckpointPath", str(checkpoint_path)])
    return args


def completed_backfill_launch_exception_message(exc: Exception) -> str:
    return f"Backfill failed to launch: {type(exc).__name__}: {exc}"


def completed_backfill_result_message(result: CapturedCommandResult, timeout_seconds: float) -> tuple[bool, str]:
    if result.timed_out:
        suffix = f" {result.kill_message}" if result.kill_message else ""
        return False, f"Backfill timed out after {timeout_seconds:.0f}s.{suffix}"
    if result.returncode != 0:
        err = result.output_tail[:500]
        return False, f"Backfill exit {result.returncode}: {err}"
    return True, (result.stdout.strip() or "Backfill complete.")
