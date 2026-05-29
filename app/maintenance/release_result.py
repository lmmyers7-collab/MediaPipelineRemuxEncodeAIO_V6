from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


def release_capture_fields(result: CapturedCommandResult) -> tuple[int, str, str, bool]:
    returncode = -1 if result.returncode is None else int(result.returncode)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    timed_out = result.timed_out
    if timed_out and result.kill_message:
        stderr = (stderr + "\n" + result.kill_message).strip()
    return returncode, stdout, stderr, timed_out


def release_result_payload(
    *,
    result: CapturedCommandResult,
    command_line: str,
    destination: Path,
    manifest_path: Path,
    zip_path: Path,
    dry_run: bool,
    elapsed_seconds: float,
    manifest: Any | None,
) -> dict[str, Any]:
    returncode, stdout, stderr, timed_out = release_capture_fields(result)
    return {
        "success": returncode == 0 and not timed_out,
        "timed_out": timed_out,
        "returncode": returncode,
        "command": command_line,
        "stdout": stdout,
        "stderr": stderr,
        "destination_root": str(destination),
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "zip_path": str(zip_path),
        "zip_exists": zip_path.exists(),
        "dry_run": dry_run,
        "elapsed_seconds": elapsed_seconds,
        "manifest": manifest,
    }

