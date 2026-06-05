from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


def release_artifact_fingerprint(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "size": None, "mtime_ns": None}
    return {"exists": True, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def release_artifact_changed(before: dict[str, Any] | None, after: dict[str, Any]) -> bool:
    if not isinstance(before, dict):
        return False
    before_exists = bool(before.get("exists"))
    after_exists = bool(after.get("exists"))
    if before_exists != after_exists:
        return True
    if not before_exists:
        return False
    return before.get("size") != after.get("size") or before.get("mtime_ns") != after.get("mtime_ns")


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
    manifest_preexisting: bool = False,
    zip_preexisting: bool = False,
    manifest_fingerprint_before: dict[str, Any] | None = None,
    zip_fingerprint_before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    returncode, stdout, stderr, timed_out = release_capture_fields(result)
    manifest_fingerprint_after = release_artifact_fingerprint(manifest_path)
    zip_fingerprint_after = release_artifact_fingerprint(zip_path)
    manifest_exists = bool(manifest_fingerprint_after.get("exists"))
    zip_exists = bool(zip_fingerprint_after.get("exists"))
    manifest_created = manifest_exists if not dry_run else manifest_exists and not manifest_preexisting
    zip_created = zip_exists if not dry_run else zip_exists and not zip_preexisting
    manifest_changed = release_artifact_changed(manifest_fingerprint_before, manifest_fingerprint_after)
    zip_changed = release_artifact_changed(zip_fingerprint_before, zip_fingerprint_after)
    return {
        "success": returncode == 0 and not timed_out,
        "timed_out": timed_out,
        "returncode": returncode,
        "command": command_line,
        "stdout": stdout,
        "stderr": stderr,
        "destination_root": str(destination),
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_exists,
        "manifest_preexisting": manifest_preexisting,
        "manifest_created": manifest_created,
        "manifest_changed": manifest_changed,
        "zip_path": str(zip_path),
        "zip_exists": zip_exists,
        "zip_preexisting": zip_preexisting,
        "zip_created": zip_created,
        "zip_changed": zip_changed,
        "dry_run": dry_run,
        "elapsed_seconds": elapsed_seconds,
        "manifest": manifest,
    }
