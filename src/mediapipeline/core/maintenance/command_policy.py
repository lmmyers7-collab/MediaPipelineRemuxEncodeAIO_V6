"""Maintenance command result policy."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mediapipeline.desktop.application.dto_commands import CommandResult


MAINTENANCE_REFRESH_HINT = "maintenance"
RELEASE_DRY_RUN_COMMAND = "maintenance.release_dry_run"
RELEASE_BUILD_COMMAND = "maintenance.release_build"
COMPLETED_BACKFILL_DRY_RUN_COMMAND = "maintenance.completed_backfill_dry_run"
DEPENDENCY_ATLAS_COMMAND = "maintenance.dependency_atlas"
RELEASE_PROGRESS_SCHEMA_VERSION = "desktop_release_package_progress.v1"
BACKFILL_PROGRESS_SCHEMA_VERSION = "desktop_maintenance_backfill_progress.v1"
DEPENDENCY_ATLAS_PROGRESS_SCHEMA_VERSION = "desktop_dependency_atlas_progress.v1"
RELEASE_PROGRESS_STEPS = [
    ("layout", "Layout"),
    ("copy", "Copy plan"),
    ("manifest", "Manifest"),
    ("validate", "Validate"),
    ("optional_smoke", "Optional smoke"),
]


def request_bool_option(request: dict[str, Any], key: str, default: bool) -> bool:
    value = request.get(key, default)
    return value if isinstance(value, bool) else default


def _command_result(**fields: Any) -> "CommandResult":
    from mediapipeline.desktop.application.dto_commands import CommandResult

    return CommandResult(**fields)


def _json_safe(value: Any) -> Any:
    from mediapipeline.desktop.application.dto_base import json_safe

    return json_safe(value)


def maintenance_int_value(value: Any) -> int:
    try:
        if value not in (None, ""):
            return int(float(value))
    except (TypeError, ValueError):
        return 0
    return 0


def release_stdout_value(stdout: str, label: str) -> str:
    target = label.strip().casefold()
    for line in stdout.splitlines():
        stripped = line.strip()
        if ":" not in stripped:
            continue
        raw_key, raw_value = stripped.split(":", 1)
        if raw_key.strip().casefold() == target:
            return raw_value.strip()
    return ""


def release_dry_run_builder_kwargs(request: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    return {
        "destination_root": str(request.get("destination_root") or "").strip(),
        "zip_package": request_bool_option(request, "zip_package", True),
        "verify": request_bool_option(request, "verify", True),
        "include_tests": request_bool_option(request, "include_tests", False),
        "include_dev_docs": request_bool_option(request, "include_dev_docs", False),
        "include_optional_tools": request_bool_option(request, "include_optional_tools", False),
        "include_tool_docs": request_bool_option(request, "include_tool_docs", False),
        "keep_personal_config": request_bool_option(request, "keep_personal_config", False),
        "force": request_bool_option(request, "force", False),
        "dry_run": True,
        "timeout_seconds": timeout_seconds,
    }


def release_build_builder_kwargs(request: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    kwargs = release_dry_run_builder_kwargs(request, timeout_seconds)
    kwargs["dry_run"] = False
    return kwargs


def release_dry_run_message(result: dict[str, Any]) -> str:
    stdout = str(result.get("stdout") or "")
    copy_files = release_stdout_value(stdout, "Copy files")
    excluded = release_stdout_value(stdout, "Exclude")
    if copy_files or excluded:
        return f"Release dry run complete: {copy_files or '?'} file(s) would be copied; {excluded or '?'} excluded."
    return "Release dry run complete. No files were copied."


def release_build_message(result: dict[str, Any]) -> str:
    stdout = str(result.get("stdout") or "")
    copy_files = release_stdout_value(stdout, "Copy files")
    manifest = bool(result.get("manifest_exists", False))
    zip_written = bool(result.get("zip_exists", False))
    parts = [f"{copy_files or '?'} file(s) copied"]
    parts.append(f"manifest {'written' if manifest else 'not found'}")
    parts.append(f"zip {'written' if zip_written else 'not written'}")
    return f"Deployment build complete: {'; '.join(parts)}."


def release_build_evidence_errors(result: dict[str, Any], request: dict[str, Any]) -> list[str]:
    if not bool(result.get("success")):
        return []
    errors: list[str] = []
    manifest_path = str(result.get("manifest_path") or "release_manifest.json")
    if not bool(result.get("manifest_exists", False)):
        errors.append(f"Release manifest was not found after deployment build: {manifest_path}")
    zip_requested = request_bool_option(request, "zip_package", True)
    if zip_requested and not bool(result.get("zip_exists", False)):
        zip_path = str(result.get("zip_path") or "release zip")
        errors.append(f"Release zip was requested but not found after deployment build: {zip_path}")
    return errors


def release_dry_run_evidence_errors(result: dict[str, Any]) -> list[str]:
    if not bool(result.get("success")):
        return []
    errors: list[str] = []
    if bool(result.get("manifest_created", False)):
        errors.append(f"Release dry run unexpectedly created a manifest: {result.get('manifest_path') or 'release_manifest.json'}")
    elif bool(result.get("manifest_changed", False)):
        errors.append(f"Release dry run unexpectedly changed a preexisting manifest: {result.get('manifest_path') or 'release_manifest.json'}")
    if bool(result.get("zip_created", False)):
        errors.append(f"Release dry run unexpectedly created a zip: {result.get('zip_path') or 'release zip'}")
    elif bool(result.get("zip_changed", False)):
        errors.append(f"Release dry run unexpectedly changed a preexisting zip: {result.get('zip_path') or 'release zip'}")
    return errors


def maintenance_progress_bar_from_steps(
    *,
    bar_id: str,
    label: str,
    steps: list[dict[str, Any]],
    status: str,
    detail: str,
    source: str,
    updated_at: str,
) -> dict[str, Any]:
    total = len(steps)
    completed = sum(1 for step in steps if str(step.get("status") or "").lower() in {"complete", "skipped"})
    percent = 100.0 if total <= 0 else round((completed / total) * 100.0, 1)
    return {
        "id": bar_id,
        "label": label,
        "mode": "stepped",
        "percent": percent,
        "status": status,
        "detail": detail,
        "source": source,
        "updated_at": updated_at,
        "stale": False,
        "step_index": completed,
        "step_total": total,
        "completed_steps": [
            str(step.get("label") or step.get("key") or "")
            for step in steps
            if str(step.get("status") or "").lower() in {"complete", "skipped"}
        ],
    }


def release_dry_run_progress_payload(result: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    process_success = bool(result.get("success"))
    evidence_errors = release_dry_run_evidence_errors(result)
    success = process_success and not evidence_errors
    timed_out = bool(result.get("timed_out"))
    returncode = maintenance_int_value(result.get("returncode"))
    stdout = str(result.get("stdout") or "")
    copy_files = release_stdout_value(stdout, "Copy files")
    excluded = release_stdout_value(stdout, "Exclude")
    verify_requested = request_bool_option(request, "verify", True)
    dry_run = bool(result.get("dry_run", True))
    status = "complete" if success else "blocked" if timed_out or evidence_errors else "error"
    detail = (
        f"Release dry run completed; copy plan {copy_files or '?'} file(s), excluded {excluded or '?'}."
        if success
        else "Release dry run artifact verification failed: " + "; ".join(evidence_errors)
        if evidence_errors
        else f"Release dry run failed with exit {returncode}."
    )
    step_status = "complete" if process_success else "blocked" if timed_out else "error"
    manifest_issue = bool(result.get("manifest_created", False)) or bool(result.get("manifest_changed", False))
    zip_issue = bool(result.get("zip_created", False)) or bool(result.get("zip_changed", False))
    manifest_status = "blocked" if evidence_errors and manifest_issue else "skipped" if process_success and dry_run else step_status
    zip_status = "blocked" if evidence_errors and zip_issue else "skipped" if process_success and dry_run else step_status
    updated_at = datetime.now().isoformat(timespec="seconds")
    steps = [
        {
            "key": "layout",
            "label": "Layout",
            "status": step_status,
            "detail": f"Destination planned: {result.get('destination_root', '')}",
        },
        {
            "key": "copy",
            "label": "Copy plan",
            "status": step_status,
            "detail": f"Dry-run copy plan reports {copy_files or '?'} file(s) copied and {excluded or '?'} excluded.",
        },
        {
            "key": "manifest",
            "label": "Manifest",
            "status": manifest_status,
            "detail": (
                f"Unexpected manifest created by dry-run: {result.get('manifest_path', '')}"
                if bool(result.get("manifest_created", False))
                else f"Unexpected preexisting manifest changed by dry-run: {result.get('manifest_path', '')}"
                if bool(result.get("manifest_changed", False))
                else "Manifest write skipped by dry-run boundary."
                if dry_run
                else f"Manifest path: {result.get('manifest_path', '')}"
            ),
        },
        {
            "key": "validate",
            "label": "Validate",
            "status": "complete" if success else "blocked" if evidence_errors else step_status,
            "detail": (
                "Release builder exited successfully and the dry-run artifact boundary held."
                if success
                else "Release builder exited successfully, but dry-run artifact evidence changed."
                if evidence_errors
                else f"Return code {returncode}."
            ),
        },
        {
            "key": "optional_smoke",
            "label": "Optional smoke",
            "status": zip_status if zip_issue else "skipped" if process_success else "blocked",
            "detail": (
                f"Unexpected zip artifact changed by dry-run: {result.get('zip_path', '')}"
                if zip_issue
                else "Verify/smoke is only planned in this WebView dry-run; no release artifacts were created."
                if verify_requested
                else "Verify/smoke was not requested."
            ),
        },
    ]
    bar = maintenance_progress_bar_from_steps(
        bar_id="release_package",
        label="Release package",
        steps=steps,
        status=status,
        detail=detail,
        source=RELEASE_DRY_RUN_COMMAND,
        updated_at=updated_at,
    )
    return {
        "schema_version": RELEASE_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "dry_run": True,
        "detail": detail,
        "artifact_verification_errors": evidence_errors,
        "updated_at": updated_at,
        "steps": steps,
        "progress_bars": [bar],
    }


def release_build_progress_payload(result: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    process_success = bool(result.get("success"))
    evidence_errors = release_build_evidence_errors(result, request)
    success = process_success and not evidence_errors
    timed_out = bool(result.get("timed_out"))
    returncode = maintenance_int_value(result.get("returncode"))
    stdout = str(result.get("stdout") or "")
    copy_files = release_stdout_value(stdout, "Copy files")
    excluded = release_stdout_value(stdout, "Exclude")
    verify_requested = request_bool_option(request, "verify", True)
    zip_requested = request_bool_option(request, "zip_package", True)
    manifest_exists = bool(result.get("manifest_exists", False))
    zip_exists = bool(result.get("zip_exists", False))
    status = "complete" if success else "blocked" if timed_out or evidence_errors else "error"
    if success:
        detail = f"Deployment build completed; copied {copy_files or '?'} file(s), excluded {excluded or '?'}, manifest written, zip {'written' if zip_exists else 'not written'}."
    elif evidence_errors:
        detail = "Deployment build artifact verification failed: " + "; ".join(evidence_errors)
    else:
        detail = f"Deployment build failed with exit {returncode}."
    step_status = "complete" if process_success else "blocked" if timed_out else "error"
    manifest_status = "complete" if process_success and manifest_exists else "blocked" if process_success else step_status
    zip_status = (
        "complete"
        if process_success and zip_exists
        else "skipped"
        if process_success and not zip_requested
        else "blocked"
        if process_success
        else step_status
    )
    verify_status = (
        "complete"
        if success and verify_requested
        else "skipped"
        if process_success and not verify_requested
        else "blocked"
        if evidence_errors
        else step_status
    )
    if success and verify_requested:
        verify_detail = "Release verification was requested and required artifacts were found."
    elif process_success and not verify_requested:
        verify_detail = "Verify was not requested."
    elif evidence_errors:
        verify_detail = "Required artifact evidence is missing after release verification."
    else:
        verify_detail = f"Return code {returncode}."
    updated_at = datetime.now().isoformat(timespec="seconds")
    steps = [
        {
            "key": "layout",
            "label": "Layout",
            "status": step_status,
            "detail": f"Destination: {result.get('destination_root', '')}",
        },
        {
            "key": "copy",
            "label": "Copy",
            "status": step_status,
            "detail": f"Release builder reported {copy_files or '?'} file(s) copied and {excluded or '?'} excluded.",
        },
        {
            "key": "manifest",
            "label": "Manifest",
            "status": manifest_status,
            "detail": f"Manifest path: {result.get('manifest_path', '')}" if manifest_exists else "Manifest was not found after deployment build.",
        },
        {
            "key": "validate",
            "label": "Validate",
            "status": "complete" if success else "blocked" if evidence_errors else step_status,
            "detail": (
                "Release builder exited successfully and required artifacts were found."
                if success
                else "Release builder exited successfully, but required artifact evidence is missing."
                if evidence_errors
                else f"Return code {returncode}."
            ),
        },
        {
            "key": "zip",
            "label": "Zip",
            "status": zip_status,
            "detail": f"Zip path: {result.get('zip_path', '')}" if zip_exists else "Zip was not requested." if not zip_requested else "Zip was requested but not found.",
        },
        {
            "key": "verify",
            "label": "Verify",
            "status": verify_status,
            "detail": verify_detail,
        },
    ]
    bar = maintenance_progress_bar_from_steps(
        bar_id="release_package",
        label="Deployment package",
        steps=steps,
        status=status,
        detail=detail,
        source=RELEASE_BUILD_COMMAND,
        updated_at=updated_at,
    )
    return {
        "schema_version": RELEASE_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "dry_run": False,
        "detail": detail,
        "artifact_verification_errors": evidence_errors,
        "updated_at": updated_at,
        "steps": steps,
        "progress_bars": [bar],
    }


def completed_backfill_progress_payload(ok: bool, output: str, *, dry_run: bool = True) -> dict[str, Any]:
    sidecars = maintenance_int_value(release_stdout_value(output, "Sidecars ingested"))
    skipped = maintenance_int_value(release_stdout_value(output, "Skipped (bad JSON)"))
    scanned = sidecars + skipped
    written = 0 if dry_run else sidecars
    status = "complete" if ok else "error"
    updated_at = datetime.now().isoformat(timespec="seconds")
    detail = (
        f"Backfill dry run scanned {scanned} record(s); would write {sidecars}; wrote {written}."
        if ok
        else "Completed manifest backfill dry run failed before record counts could be trusted."
    )
    bar = {
        "id": "maintenance_backfill",
        "label": "Maintenance backfill",
        "mode": "determinate",
        "percent": 100.0 if ok else 0.0,
        "status": status,
        "detail": detail,
        "source": COMPLETED_BACKFILL_DRY_RUN_COMMAND,
        "updated_at": updated_at,
        "stale": False,
    }
    return {
        "schema_version": BACKFILL_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "dry_run": dry_run,
        "records_scanned": scanned,
        "records_written": written,
        "records_would_write": sidecars,
        "records_skipped": skipped,
        "detail": detail,
        "updated_at": updated_at,
        "progress_bars": [bar],
    }


def dependency_atlas_message(result: dict[str, Any]) -> str:
    stdout = str(result.get("stdout") or "")
    modules = release_stdout_value(stdout, "Modules")
    domains = release_stdout_value(stdout, "Domains")
    links = release_stdout_value(stdout, "HTML local links checked")
    if modules or domains or links:
        return f"Dependency atlas updated: {modules or '?'} module(s), {domains or '?'} domain(s), {links or '?'} HTML link(s) checked."
    return "Dependency atlas updated."


def dependency_atlas_progress_payload(result: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    del request
    success = bool(result.get("success"))
    timed_out = bool(result.get("timed_out"))
    returncode = maintenance_int_value(result.get("returncode"))
    stdout = str(result.get("stdout") or "")
    modules = release_stdout_value(stdout, "Modules")
    domain_edges = release_stdout_value(stdout, "Domain edges")
    diagrams = release_stdout_value(stdout, "Detail diagrams")
    links = release_stdout_value(stdout, "HTML local links checked")
    status = "complete" if success else "blocked" if timed_out else "error"
    detail = (
        f"Dependency atlas generated; modules {modules or '?'}, domain edges {domain_edges or '?'}, diagrams {diagrams or '?'}, links checked {links or '?'}."
        if success
        else f"Dependency atlas generation failed with exit {returncode}."
    )
    updated_at = datetime.now().isoformat(timespec="seconds")
    step_status = "complete" if success else "blocked" if timed_out else "error"
    output_status = (
        "complete"
        if success and bool(result.get("html_exists")) and bool(result.get("png_exists")) and bool(result.get("svg_exists"))
        else "blocked" if success else step_status
    )
    csv_status = (
        "complete"
        if success and bool(result.get("summary_csv_exists")) and bool(result.get("domain_edges_csv_exists")) and bool(result.get("module_edges_csv_exists"))
        else "blocked" if success else step_status
    )
    steps = [
        {
            "key": "parse",
            "label": "Parse imports",
            "status": step_status,
            "detail": f"Parsed local Python imports; modules reported: {modules or '?'}." if success else f"Return code {returncode}.",
        },
        {
            "key": "overview",
            "label": "Render overview",
            "status": output_status,
            "detail": f"Overview HTML/PNG/SVG: {result.get('atlas_html', '')}",
        },
        {
            "key": "detail",
            "label": "Render detail diagrams",
            "status": step_status,
            "detail": f"Focused diagrams reported: {diagrams or '?'}." if success else "Detail diagrams were not trusted.",
        },
        {
            "key": "csv",
            "label": "Write CSV exports",
            "status": csv_status,
            "detail": f"CSV outputs: {result.get('summary_csv', '')}",
        },
        {
            "key": "validate",
            "label": "Validate links",
            "status": step_status,
            "detail": f"HTML local links checked: {links or '?'}." if success else "HTML link validation did not complete cleanly.",
        },
    ]
    bar = maintenance_progress_bar_from_steps(
        bar_id="dependency_atlas",
        label="Dependency atlas",
        steps=steps,
        status=status,
        detail=detail,
        source=DEPENDENCY_ATLAS_COMMAND,
        updated_at=updated_at,
    )
    return {
        "schema_version": DEPENDENCY_ATLAS_PROGRESS_SCHEMA_VERSION,
        "status": status,
        "dry_run": False,
        "detail": detail,
        "updated_at": updated_at,
        "steps": steps,
        "progress_bars": [bar],
    }


def maintenance_command_blocked_result(command: str, message: str) -> CommandResult:
    return _command_result(
        command=command,
        ok=False,
        message=message,
        severity="warning",
        warnings=[message],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_builder_unavailable_result() -> CommandResult:
    return _command_result(
        command=RELEASE_DRY_RUN_COMMAND,
        ok=False,
        message="Release package builder is not available.",
        severity="error",
        errors=["build_release_package is required."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_build_confirmation_required_result() -> CommandResult:
    return _command_result(
        command=RELEASE_BUILD_COMMAND,
        ok=False,
        message="Deployment build requires explicit confirmation before creating release files.",
        severity="warning",
        warnings=["confirm_create must be true."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_build_unavailable_result() -> CommandResult:
    return _command_result(
        command=RELEASE_BUILD_COMMAND,
        ok=False,
        message="Deployment package builder is not available.",
        severity="error",
        errors=["build_release_package is required."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_build_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=RELEASE_BUILD_COMMAND,
        ok=False,
        message=f"Deployment build failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_build_invalid_result() -> CommandResult:
    return _command_result(
        command=RELEASE_BUILD_COMMAND,
        ok=False,
        message="Deployment build returned an invalid result.",
        severity="error",
        errors=["build_release_package must return a dictionary."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_dry_run_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=RELEASE_DRY_RUN_COMMAND,
        ok=False,
        message=f"Release dry run failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_dry_run_invalid_result() -> CommandResult:
    return _command_result(
        command=RELEASE_DRY_RUN_COMMAND,
        ok=False,
        message="Release dry run returned an invalid result.",
        severity="error",
        errors=["build_release_package must return a dictionary."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def release_dry_run_result(result: dict[str, Any], request: dict[str, Any]) -> CommandResult:
    process_success = bool(result.get("success"))
    evidence_errors = release_dry_run_evidence_errors(result)
    success = process_success and not evidence_errors
    timed_out = bool(result.get("timed_out"))
    returncode = maintenance_int_value(result.get("returncode"))
    severity = "info" if success else "warning" if timed_out else "error"
    progress = release_dry_run_progress_payload(result, request)
    if success:
        message = release_dry_run_message(result)
        errors: list[str] = []
    elif evidence_errors:
        message = "Release dry run artifact verification failed: " + "; ".join(evidence_errors)
        errors = evidence_errors
    else:
        message = f"Release dry run failed with exit {returncode}."
        errors = [str(result.get("stderr") or result.get("stdout") or f"returncode={returncode}")]
    return _command_result(
        command=RELEASE_DRY_RUN_COMMAND,
        ok=success,
        message=message,
        severity=severity,
        errors=errors,
        refresh_hint=MAINTENANCE_REFRESH_HINT,
        data=_json_safe(
            {
                "dry_run": True,
                "destination_root": result.get("destination_root", ""),
                "manifest_path": result.get("manifest_path", ""),
                "zip_path": result.get("zip_path", ""),
                "manifest_exists": bool(result.get("manifest_exists", False)),
                "manifest_preexisting": bool(result.get("manifest_preexisting", False)),
                "manifest_created": bool(result.get("manifest_created", False)),
                "manifest_changed": bool(result.get("manifest_changed", False)),
                "zip_exists": bool(result.get("zip_exists", False)),
                "zip_preexisting": bool(result.get("zip_preexisting", False)),
                "zip_created": bool(result.get("zip_created", False)),
                "zip_changed": bool(result.get("zip_changed", False)),
                "returncode": returncode,
                "timed_out": timed_out,
                "elapsed_seconds": result.get("elapsed_seconds", 0.0),
                "command": result.get("command", ""),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "process_success": process_success,
                "artifact_verification_errors": evidence_errors,
                "options": {
                    "zip_package": request_bool_option(request, "zip_package", True),
                    "verify": request_bool_option(request, "verify", True),
                    "include_tests": request_bool_option(request, "include_tests", False),
                    "include_dev_docs": request_bool_option(request, "include_dev_docs", False),
                    "include_optional_tools": request_bool_option(request, "include_optional_tools", False),
                    "include_tool_docs": request_bool_option(request, "include_tool_docs", False),
                    "keep_personal_config": request_bool_option(request, "keep_personal_config", False),
                },
                "release_progress": progress,
                "progress_bars": progress["progress_bars"],
            }
        ),
    )


def release_build_result(result: dict[str, Any], request: dict[str, Any]) -> CommandResult:
    process_success = bool(result.get("success"))
    evidence_errors = release_build_evidence_errors(result, request)
    success = process_success and not evidence_errors
    timed_out = bool(result.get("timed_out"))
    returncode = maintenance_int_value(result.get("returncode"))
    severity = "info" if success else "warning" if timed_out else "error"
    progress = release_build_progress_payload(result, request)
    if success:
        message = release_build_message(result)
        errors: list[str] = []
    elif evidence_errors:
        message = "Deployment build artifact verification failed: " + "; ".join(evidence_errors)
        errors = evidence_errors
    else:
        message = f"Deployment build failed with exit {returncode}."
        errors = [str(result.get("stderr") or result.get("stdout") or f"returncode={returncode}")]
    return _command_result(
        command=RELEASE_BUILD_COMMAND,
        ok=success,
        message=message,
        severity=severity,
        errors=errors,
        refresh_hint=MAINTENANCE_REFRESH_HINT,
        data=_json_safe(
            {
                "dry_run": False,
                "destination_root": result.get("destination_root", ""),
                "manifest_path": result.get("manifest_path", ""),
                "zip_path": result.get("zip_path", ""),
                "manifest_exists": bool(result.get("manifest_exists", False)),
                "manifest_changed": bool(result.get("manifest_changed", False)),
                "zip_exists": bool(result.get("zip_exists", False)),
                "zip_changed": bool(result.get("zip_changed", False)),
                "returncode": returncode,
                "timed_out": timed_out,
                "elapsed_seconds": result.get("elapsed_seconds", 0.0),
                "command": result.get("command", ""),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "writes_release_package": success,
                "process_success": process_success,
                "artifact_verification_errors": evidence_errors,
                "options": {
                    "zip_package": request_bool_option(request, "zip_package", True),
                    "verify": request_bool_option(request, "verify", True),
                    "include_tests": request_bool_option(request, "include_tests", False),
                    "include_dev_docs": request_bool_option(request, "include_dev_docs", False),
                    "include_optional_tools": request_bool_option(request, "include_optional_tools", False),
                    "include_tool_docs": request_bool_option(request, "include_tool_docs", False),
                    "keep_personal_config": request_bool_option(request, "keep_personal_config", False),
                    "force": request_bool_option(request, "force", False),
                },
                "release_progress": progress,
                "progress_bars": progress["progress_bars"],
            }
        ),
    )


def completed_backfill_unavailable_result() -> CommandResult:
    return _command_result(
        command=COMPLETED_BACKFILL_DRY_RUN_COMMAND,
        ok=False,
        message="Completed manifest backfill service is not available.",
        severity="error",
        errors=["backfill_completed_manifest is required."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def completed_backfill_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=COMPLETED_BACKFILL_DRY_RUN_COMMAND,
        ok=False,
        message=f"Completed manifest backfill dry run failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def dependency_atlas_unavailable_result() -> CommandResult:
    return _command_result(
        command=DEPENDENCY_ATLAS_COMMAND,
        ok=False,
        message="Dependency atlas generator is not available.",
        severity="error",
        errors=["generate_dependency_atlas is required."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def dependency_atlas_exception_result(exc: Exception) -> CommandResult:
    return _command_result(
        command=DEPENDENCY_ATLAS_COMMAND,
        ok=False,
        message=f"Dependency atlas generation failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def dependency_atlas_invalid_result() -> CommandResult:
    return _command_result(
        command=DEPENDENCY_ATLAS_COMMAND,
        ok=False,
        message="Dependency atlas generation returned an invalid result.",
        severity="error",
        errors=["generate_dependency_atlas must return a dictionary."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
    )


def dependency_atlas_result(result: dict[str, Any], request: dict[str, Any]) -> CommandResult:
    success = bool(result.get("success"))
    timed_out = bool(result.get("timed_out"))
    returncode = maintenance_int_value(result.get("returncode"))
    severity = "info" if success else "warning" if timed_out else "error"
    progress = dependency_atlas_progress_payload(result, request)
    stdout = str(result.get("stdout") or "")
    return _command_result(
        command=DEPENDENCY_ATLAS_COMMAND,
        ok=success,
        message=dependency_atlas_message(result) if success else f"Dependency atlas generation failed with exit {returncode}.",
        severity=severity,
        errors=[] if success else [str(result.get("stderr") or result.get("stdout") or f"returncode={returncode}")],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
        data=_json_safe(
            {
                "dry_run": False,
                "writes_dependency_atlas": success,
                "writes_media": False,
                "atlas_html": result.get("atlas_html", ""),
                "atlas_png": result.get("atlas_png", ""),
                "atlas_svg": result.get("atlas_svg", ""),
                "assets_dir": result.get("assets_dir", ""),
                "summary_csv": result.get("summary_csv", ""),
                "domain_edges_csv": result.get("domain_edges_csv", ""),
                "module_edges_csv": result.get("module_edges_csv", ""),
                "html_exists": bool(result.get("html_exists", False)),
                "png_exists": bool(result.get("png_exists", False)),
                "svg_exists": bool(result.get("svg_exists", False)),
                "summary_csv_exists": bool(result.get("summary_csv_exists", False)),
                "domain_edges_csv_exists": bool(result.get("domain_edges_csv_exists", False)),
                "module_edges_csv_exists": bool(result.get("module_edges_csv_exists", False)),
                "modules": release_stdout_value(stdout, "Modules"),
                "module_edges": release_stdout_value(stdout, "Module edges"),
                "domains": release_stdout_value(stdout, "Domains"),
                "domain_edges": release_stdout_value(stdout, "Domain edges"),
                "detail_diagrams": release_stdout_value(stdout, "Detail diagrams"),
                "html_links_checked": release_stdout_value(stdout, "HTML local links checked"),
                "returncode": returncode,
                "timed_out": timed_out,
                "elapsed_seconds": result.get("elapsed_seconds", 0.0),
                "command": result.get("command", ""),
                "stdout": stdout,
                "stderr": result.get("stderr", ""),
                "options": {
                    "min_overview_edge_count": maintenance_int_value(request.get("min_overview_edge_count")) or 4,
                    "min_overview_files": maintenance_int_value(request.get("min_overview_files")) or 2,
                },
                "dependency_atlas_progress": progress,
                "progress_bars": progress["progress_bars"],
            }
        ),
    )


def completed_backfill_dry_run_result(
    ok: bool,
    message: object,
    *,
    completed_manifest_path: Path | None,
    checkpoint_path: Path | None,
    timeout_seconds: int,
) -> CommandResult:
    output = str(message or "")
    sidecars = release_stdout_value(output, "Sidecars ingested")
    skipped = release_stdout_value(output, "Skipped (bad JSON)")
    manifest = release_stdout_value(output, "Manifest")
    summary = f"Completed manifest backfill dry run found {sidecars or '?'} sidecar(s); {skipped or '0'} skipped."
    progress = completed_backfill_progress_payload(bool(ok), output, dry_run=True)
    return _command_result(
        command=COMPLETED_BACKFILL_DRY_RUN_COMMAND,
        ok=bool(ok),
        message=summary if ok else f"Completed manifest backfill dry run failed: {output or 'unknown error'}",
        severity="info" if ok else "error",
        errors=[] if ok else [output or "Backfill dry run failed."],
        refresh_hint=MAINTENANCE_REFRESH_HINT,
        data=_json_safe(
            {
                "dry_run": True,
                "stdout": output,
                "sidecars_ingested": sidecars,
                "skipped_bad_json": skipped,
                "manifest_path": manifest or str(completed_manifest_path or ""),
                "checkpoint_path": str(checkpoint_path or ""),
                "timeout_seconds": timeout_seconds,
                "writes_manifest": False,
                "backfill_progress": progress,
                "progress_bars": progress["progress_bars"],
            }
        ),
    )

__all__ = [
    "MAINTENANCE_REFRESH_HINT",
    "RELEASE_DRY_RUN_COMMAND",
    "RELEASE_BUILD_COMMAND",
    "COMPLETED_BACKFILL_DRY_RUN_COMMAND",
    "DEPENDENCY_ATLAS_COMMAND",
    "RELEASE_PROGRESS_SCHEMA_VERSION",
    "BACKFILL_PROGRESS_SCHEMA_VERSION",
    "DEPENDENCY_ATLAS_PROGRESS_SCHEMA_VERSION",
    "RELEASE_PROGRESS_STEPS",
    "maintenance_int_value",
    "release_stdout_value",
    "release_dry_run_builder_kwargs",
    "release_build_builder_kwargs",
    "release_dry_run_message",
    "release_build_message",
    "release_dry_run_evidence_errors",
    "release_build_evidence_errors",
    "maintenance_progress_bar_from_steps",
    "release_dry_run_progress_payload",
    "release_build_progress_payload",
    "completed_backfill_progress_payload",
    "dependency_atlas_message",
    "dependency_atlas_progress_payload",
    "maintenance_command_blocked_result",
    "release_builder_unavailable_result",
    "release_build_confirmation_required_result",
    "release_build_unavailable_result",
    "release_build_exception_result",
    "release_build_invalid_result",
    "release_dry_run_exception_result",
    "release_dry_run_invalid_result",
    "release_dry_run_result",
    "release_build_result",
    "completed_backfill_unavailable_result",
    "completed_backfill_exception_result",
    "dependency_atlas_unavailable_result",
    "dependency_atlas_exception_result",
    "dependency_atlas_invalid_result",
    "dependency_atlas_result",
    "completed_backfill_dry_run_result",
]
