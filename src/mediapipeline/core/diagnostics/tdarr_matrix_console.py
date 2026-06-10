"""Backend read models and keyed actions for the Tdarr Matrix diagnostics console."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from mediapipeline.core.kernel.dto_base import json_safe


TDARR_MATRIX_CONSOLE_SCHEMA_VERSION = "desktop_tdarr_matrix_console.v1"
TDARR_MATRIX_RUNS_SCHEMA_VERSION = "desktop_tdarr_matrix_runs.v1"
TDARR_MATRIX_COMPARE_SCHEMA_VERSION = "desktop_tdarr_matrix_compare.v1"
TDARR_MATRIX_EVIDENCE_COMMAND = "diagnostics.tdarr_matrix.evidence_open"
TDARR_MATRIX_RERUN_COMMAND = "diagnostics.tdarr_matrix.rerun"
TDARR_MATRIX_AUDIT_RUN_SENTINEL = ".tdarr-matrix-audit-run.json"
TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS = (
    "stdout",
    "stderr",
    "worker_result",
    "source_hashes",
    "failure_artifact",
    "output",
    "report_folder",
)


def _command_result(**fields: Any) -> Any:
    from mediapipeline.core.kernel.dto_commands import CommandResult

    return CommandResult(**fields)


def _bounded_text(value: Any, *, limit: int = 600) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


def _safe_key_part(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^A-Za-z0-9_.=:-]+", "-", text)
    return text.strip("-") or "unknown"


def _safe_slug(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_.=-]+", "-", text)
    return text.strip("-") or "unknown"


def _int_value(value: Any) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return 0


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def tdarr_matrix_runs_root(workspace_root: Path) -> Path:
    return workspace_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns"


def _run_root(workspace_root: Path, run_id: Any) -> Path:
    run_id_text = str(run_id or "").strip()
    if not run_id_text or run_id_text in {".", ".."} or "/" in run_id_text or "\\" in run_id_text:
        raise ValueError("A valid Tdarr Matrix run ID is required.")
    root = tdarr_matrix_runs_root(workspace_root)
    candidate = root / run_id_text
    if not _is_under(candidate, root):
        raise ValueError("Tdarr Matrix run root must stay under TdarrMatrixRuns.")
    return candidate


def _report_path(run_root: Path) -> Path:
    return run_root / "manifests" / "audit" / "tdarr_matrix_audit_report.json"


def _manifest_path(run_root: Path) -> Path:
    return run_root / "manifests" / "materialized_library.csv"


def _artifact_dir(run_root: Path, case_id: Any, view: Any) -> Path:
    return run_root / "manifests" / "audit" / "files" / _safe_slug(f"{case_id}-{view}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_report(run_root: Path) -> dict[str, Any]:
    return _read_json(_report_path(run_root))


def _read_manifest_rows(run_root: Path) -> list[dict[str, Any]]:
    path = _manifest_path(run_root)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError:
        return []


def _finding_identity(finding: dict[str, Any]) -> str:
    return ":".join(
        _safe_key_part(finding.get(name))
        for name in ("case_id", "view", "code", "diagnostic_bucket")
    )


def tdarr_matrix_finding_key(run_id: str, finding: dict[str, Any], index: int) -> str:
    return ":".join(
        [
            _safe_key_part(run_id),
            _safe_key_part(finding.get("case_id")),
            _safe_key_part(finding.get("view")),
            _safe_key_part(finding.get("code")),
            f"{index:04d}",
        ]
    )


def _worker_result_for(run_root: Path, finding: dict[str, Any]) -> dict[str, Any]:
    evidence = finding.get("evidence") if isinstance(finding.get("evidence"), dict) else {}
    worker_result = evidence.get("worker_result") if isinstance(evidence.get("worker_result"), dict) else None
    if worker_result is not None:
        return dict(worker_result)
    path = _artifact_dir(run_root, finding.get("case_id"), finding.get("view")) / "worker_result.json"
    return _read_json(path)


def _candidate_evidence_path(run_root: Path, finding: dict[str, Any], target: str) -> Path | None:
    artifact_dir = _artifact_dir(run_root, finding.get("case_id"), finding.get("view"))
    if target == "stdout":
        return artifact_dir / "stdout.log"
    if target == "stderr":
        return artifact_dir / "stderr.log"
    if target == "worker_result":
        return artifact_dir / "worker_result.json"
    if target == "source_hashes":
        return artifact_dir / "source_hashes.json"
    if target == "report_folder":
        return _report_path(run_root).parent
    worker_result = _worker_result_for(run_root, finding)
    candidate_keys = {
        "failure_artifact": ("FailureArtifact", "FailureArtifactPath", "failure_artifact", "failure_artifact_path"),
        "output": ("OutputPath", "OutputFile", "output_path", "output_file"),
    }.get(target, ())
    for key in candidate_keys:
        value = str(worker_result.get(key) or "").strip()
        if value:
            return Path(value)
    return None


def _available_evidence_targets(run_root: Path, finding: dict[str, Any]) -> list[str]:
    available: list[str] = []
    for target in TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS:
        candidate = _candidate_evidence_path(run_root, finding, target)
        if candidate is None or not candidate.exists():
            continue
        if _is_under(candidate, run_root):
            available.append(target)
    return available


def _summary_counts(rows: Iterable[dict[str, Any]], findings: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row_list = list(rows)
    finding_list = list(findings)
    by_bucket: dict[str, dict[str, Any]] = {}
    for row in row_list:
        bucket = str(row.get("diagnostic_bucket") or "unknown")
        item = by_bucket.setdefault(
            bucket,
            {
                "diagnostic_bucket": bucket,
                "selected_count": 0,
                "queued_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "movie_count": 0,
                "tv_count": 0,
                "finding_count": 0,
                "severity_counts": {},
            },
        )
        item["selected_count"] += 1
        item["queued_count"] += 1
        view = str(row.get("view") or "").casefold()
        if view == "movies":
            item["movie_count"] += 1
        elif view == "tv":
            item["tv_count"] += 1
    severity_by_bucket: dict[str, Counter[str]] = defaultdict(Counter)
    failed_buckets: Counter[str] = Counter()
    for finding in finding_list:
        bucket = str(finding.get("diagnostic_bucket") or "unknown")
        severity = str(finding.get("severity") or "info")
        item = by_bucket.setdefault(
            bucket,
            {
                "diagnostic_bucket": bucket,
                "selected_count": 0,
                "queued_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "movie_count": 0,
                "tv_count": 0,
                "finding_count": 0,
                "severity_counts": {},
            },
        )
        item["finding_count"] += 1
        severity_by_bucket[bucket][severity] += 1
        if severity in {"critical", "error", "warning"}:
            failed_buckets[bucket] += 1
    for bucket, item in by_bucket.items():
        item["severity_counts"] = dict(severity_by_bucket[bucket])
        item["failed_count"] = int(failed_buckets[bucket])
        item["passed_count"] = max(0, int(item["selected_count"]) - int(item["failed_count"]))
    sample_summary = {
        "selected_count": len(row_list),
        "movie_count": sum(1 for row in row_list if str(row.get("view") or "").casefold() == "movies"),
        "tv_count": sum(1 for row in row_list if str(row.get("view") or "").casefold() == "tv"),
    }
    return sample_summary, sorted(by_bucket.values(), key=lambda item: str(item["diagnostic_bucket"]))


def _run_sort_key(run_root: Path) -> tuple[float, str]:
    candidates = [_report_path(run_root), run_root]
    newest = 0.0
    for candidate in candidates:
        try:
            newest = max(newest, candidate.stat().st_mtime)
        except OSError:
            continue
    return (newest, run_root.name)


def _run_progress_summary(run_root: Path, selected_count: int) -> dict[str, Any]:
    files_root = run_root / "manifests" / "audit" / "files"
    try:
        result_paths = list(files_root.glob("*/worker_result.json")) if files_root.exists() else []
    except OSError:
        result_paths = []
    completed = len(result_paths)
    percent = round((completed / selected_count) * 100.0, 1) if selected_count > 0 else 0.0
    summary: dict[str, Any] = {
        "worker_result_count": completed,
        "progress_percent": percent,
        "completed_per_hour": 0.0,
        "estimated_total_hours": 0.0,
        "estimated_remaining_hours": 0.0,
        "first_worker_result_at": "",
        "last_worker_result_at": "",
    }
    if completed <= 0:
        return summary
    mtimes = [path.stat().st_mtime for path in result_paths]
    first = min(mtimes)
    last = max(mtimes)
    elapsed_hours = max((last - first) / 3600.0, 1 / 3600.0)
    rate = completed / elapsed_hours
    summary.update(
        {
            "completed_per_hour": round(rate, 2),
            "estimated_total_hours": round(selected_count / rate, 1) if rate > 0 and selected_count > 0 else 0.0,
            "estimated_remaining_hours": round(max(0, selected_count - completed) / rate, 1) if rate > 0 and selected_count > 0 else 0.0,
            "first_worker_result_at": datetime.fromtimestamp(first).astimezone().isoformat(timespec="seconds"),
            "last_worker_result_at": datetime.fromtimestamp(last).astimezone().isoformat(timespec="seconds"),
        }
    )
    return summary


def _run_metadata(run_root: Path, *, include_progress: bool = False) -> dict[str, Any]:
    report = _read_report(run_root)
    rows = _read_manifest_rows(run_root)
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    severity_counts = Counter(str(finding.get("severity") or "info") for finding in findings if isinstance(finding, dict))
    report_path = _report_path(run_root)
    sentinel_exists = (run_root / TDARR_MATRIX_AUDIT_RUN_SENTINEL).exists()
    report_exists = report_path.exists()
    selected_count = len(rows)
    metadata = {
        "run_id": run_root.name,
        "run_root": str(run_root),
        "report_path": str(report_path),
        "report_exists": report_exists,
        "manifest_path": str(_manifest_path(run_root)),
        "sentinel_exists": sentinel_exists,
        "status": "complete" if report_exists else "preparing" if sentinel_exists else "starting",
        "generated_at_utc": str(report.get("generated_at_utc") or report.get("created_at_utc") or ""),
        "mode": str(report.get("mode") or ""),
        "finding_count": len(findings),
        "selected_count": selected_count,
        "severity_counts": dict(severity_counts),
    }
    if include_progress:
        progress = _run_progress_summary(run_root, selected_count)
        metadata.update(progress)
        if not report_exists and int(progress.get("worker_result_count") or 0) > 0:
            metadata["status"] = "processing"
    return metadata


def _pending_run_payload(workspace_root: Path, selected_run_id: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    run_root = _run_root(workspace_root, selected_run_id)
    selected_run = _run_metadata(run_root, include_progress=True)
    return json_safe(
        {
            "schema_version": TDARR_MATRIX_CONSOLE_SCHEMA_VERSION,
            "runs_root": str(tdarr_matrix_runs_root(workspace_root)),
            "latest_run_id": selected_run_id,
            "run": selected_run,
            "runs": runs,
            "report_path": str(_report_path(run_root)),
            "manifest_path": str(_manifest_path(run_root)),
            "findings": [],
            "finding_count": 0,
            "finding_limit": 0,
            "findings_truncated": False,
            "severity_counts": {},
            "code_counts": {},
            "sample_summary": {"selected_count": 0, "movie_count": 0, "tv_count": 0},
            "bucket_summary": [],
            "message": f"Tdarr Matrix run {selected_run_id} has been requested but has not written its audit report yet.",
        }
    )


def tdarr_matrix_discover_runs(workspace_root: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    root = tdarr_matrix_runs_root(workspace_root)
    if not root.exists():
        return []
    run_roots = [
        child
        for child in root.iterdir()
        if child.is_dir() and (child / TDARR_MATRIX_AUDIT_RUN_SENTINEL).exists()
    ]
    run_roots.sort(key=_run_sort_key, reverse=True)
    return [_run_metadata(run_root) for run_root in run_roots[: max(0, int(limit))]]


def tdarr_matrix_runs_payload(workspace_root: Path, *, limit: int = 50) -> dict[str, Any]:
    runs = tdarr_matrix_discover_runs(workspace_root, limit=limit)
    return json_safe(
        {
            "schema_version": TDARR_MATRIX_RUNS_SCHEMA_VERSION,
            "runs_root": str(tdarr_matrix_runs_root(workspace_root)),
            "runs": runs,
            "run_count": len(runs),
        }
    )


def _enriched_findings(run_root: Path, run_id: str, raw_findings: Iterable[Any]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for index, item in enumerate(raw_findings):
        finding = dict(item or {}) if isinstance(item, dict) else {}
        worker_result = _worker_result_for(run_root, finding)
        route = str(worker_result.get("Route") or finding.get("route") or "")
        reason = str(worker_result.get("Reason") or finding.get("reason") or "")
        row = {
            **finding,
            "finding_key": tdarr_matrix_finding_key(run_id, finding, index),
            "finding_identity": _finding_identity(finding),
            "run_id": run_id,
            "message": _bounded_text(finding.get("message"), limit=500),
            "route": route,
            "route_reason_code": str(worker_result.get("RouteReasonCode") or ""),
            "status": str(worker_result.get("Status") or ""),
            "reason": _bounded_text(reason, limit=300),
            "source_name": _bounded_text(worker_result.get("SourceName") or finding.get("generated_path"), limit=500),
        }
        row["available_evidence_targets"] = _available_evidence_targets(run_root, row)
        enriched.append(row)
    return enriched


def tdarr_matrix_console_payload(
    workspace_root: Path,
    *,
    run_id: Any = "",
    finding_limit: int = 100,
) -> dict[str, Any]:
    runs = tdarr_matrix_discover_runs(workspace_root)
    selected_run_id = str(run_id or "").strip()
    if selected_run_id:
        run_root = _run_root(workspace_root, selected_run_id)
        if not (run_root / TDARR_MATRIX_AUDIT_RUN_SENTINEL).exists():
            return _pending_run_payload(workspace_root, selected_run_id, runs)
    elif runs:
        selected_run_id = str(runs[0]["run_id"])
        run_root = _run_root(workspace_root, selected_run_id)
    else:
        return json_safe(
            {
                "schema_version": TDARR_MATRIX_CONSOLE_SCHEMA_VERSION,
                "runs_root": str(tdarr_matrix_runs_root(workspace_root)),
                "latest_run_id": "",
                "run": {},
                "runs": [],
                "findings": [],
                "finding_count": 0,
                "severity_counts": {},
                "code_counts": {},
                "sample_summary": {"selected_count": 0, "movie_count": 0, "tv_count": 0},
                "bucket_summary": [],
                "message": "No Tdarr Matrix sample runs were found.",
            }
        )
    report = _read_report(run_root)
    rows = _read_manifest_rows(run_root)
    raw_findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    findings = _enriched_findings(run_root, selected_run_id, raw_findings)
    sample_summary, bucket_summary = _summary_counts(rows, findings)
    severity_counts = Counter(str(finding.get("severity") or "info") for finding in findings)
    code_counts = Counter(str(finding.get("code") or "unknown") for finding in findings)
    limit = max(0, int(finding_limit))
    selected_run = _run_metadata(run_root, include_progress=True)
    return json_safe(
        {
            "schema_version": TDARR_MATRIX_CONSOLE_SCHEMA_VERSION,
            "runs_root": str(tdarr_matrix_runs_root(workspace_root)),
            "latest_run_id": selected_run_id,
            "run": selected_run,
            "runs": runs,
            "report_path": str(_report_path(run_root)),
            "manifest_path": str(_manifest_path(run_root)),
            "findings": findings[:limit],
            "finding_count": len(findings),
            "finding_limit": limit,
            "findings_truncated": len(findings) > limit,
            "severity_counts": dict(severity_counts),
            "code_counts": dict(code_counts),
            "sample_summary": sample_summary,
            "bucket_summary": bucket_summary,
        }
    )


def _find_finding(workspace_root: Path, run_id: Any, finding_key: Any) -> tuple[Path, dict[str, Any]]:
    run_id_text = str(run_id or "").strip()
    key_text = str(finding_key or "").strip()
    if not run_id_text or not key_text:
        raise ValueError("run_id and finding_key are required.")
    run_root = _run_root(workspace_root, run_id_text)
    if not (run_root / TDARR_MATRIX_AUDIT_RUN_SENTINEL).exists():
        raise ValueError(f"Tdarr Matrix run not found or missing sentinel: {run_id_text}")
    report = _read_report(run_root)
    raw_findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    for finding in _enriched_findings(run_root, run_id_text, raw_findings):
        if finding.get("finding_key") == key_text:
            return run_root, finding
    raise ValueError("Finding key was not found in the selected Tdarr Matrix run.")


def tdarr_matrix_evidence_path(workspace_root: Path, request: dict[str, Any]) -> Path:
    target = str(request.get("target") or "").strip()
    if target not in TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS:
        allowed = ", ".join(TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS)
        raise ValueError(f"Unsupported evidence target. Allowed targets: {allowed}")
    run_root, finding = _find_finding(workspace_root, request.get("run_id"), request.get("finding_key"))
    candidate = _candidate_evidence_path(run_root, finding, target)
    if candidate is None:
        raise ValueError(f"Evidence target is not available for this finding: {target}")
    candidate = candidate.resolve(strict=False)
    if not _is_under(candidate, run_root):
        raise ValueError("Resolved evidence path escaped the Tdarr Matrix run root.")
    if not candidate.exists():
        raise ValueError(f"Evidence target is missing: {target}")
    return candidate


def tdarr_matrix_evidence_open_result(
    workspace_root: Path,
    request: dict[str, Any],
    *,
    opener: Callable[[Path], Any] | None = None,
) -> Any:
    try:
        path = tdarr_matrix_evidence_path(workspace_root, request)
    except Exception as exc:
        return _command_result(
            command=TDARR_MATRIX_EVIDENCE_COMMAND,
            ok=False,
            message=f"Tdarr Matrix evidence open failed: {exc}",
            severity="error",
            errors=[str(exc)],
            refresh_hint="diagnostics",
            data={"allowed_targets": list(TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS)},
        )
    if not callable(opener):
        return _command_result(
            command=TDARR_MATRIX_EVIDENCE_COMMAND,
            ok=False,
            message="Tdarr Matrix evidence opener is not available.",
            severity="error",
            errors=["opener is required"],
            refresh_hint="diagnostics",
            data={"path": str(path), "target": str(request.get("target") or "")},
        )
    opener(path)
    return _command_result(
        command=TDARR_MATRIX_EVIDENCE_COMMAND,
        ok=True,
        message=f"Opened Tdarr Matrix evidence target: {request.get('target')}",
        severity="info",
        errors=[],
        refresh_hint="diagnostics",
        data={
            "run_id": str(request.get("run_id") or ""),
            "finding_key": str(request.get("finding_key") or ""),
            "target": str(request.get("target") or ""),
            "path": str(path),
        },
    )


def tdarr_matrix_rerun_case_keys(workspace_root: Path, request: dict[str, Any]) -> list[str]:
    source_run_id = str(request.get("source_run_id") or request.get("run_id") or "").strip()
    selection = str(request.get("selection") or "selected").strip().casefold().replace("_", "-")
    run_root = _run_root(workspace_root, source_run_id)
    if not (run_root / TDARR_MATRIX_AUDIT_RUN_SENTINEL).exists():
        raise ValueError(f"Tdarr Matrix run not found or missing sentinel: {source_run_id}")
    report = _read_report(run_root)
    raw_findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    findings = _enriched_findings(run_root, source_run_id, raw_findings)
    if selection == "latest-failures":
        selected = [
            finding
            for finding in findings
            if str(finding.get("severity") or "").casefold() in {"critical", "error", "warning"}
            or "failure" in str(finding.get("code") or "").casefold()
        ]
    elif selection == "selected":
        requested = {str(key or "").strip() for key in (request.get("finding_keys") or []) if str(key or "").strip()}
        selected = [finding for finding in findings if str(finding.get("finding_key") or "") in requested]
    else:
        raise ValueError("selection must be selected or latest_failures.")
    case_keys: list[str] = []
    seen: set[str] = set()
    for finding in selected:
        case_id = str(finding.get("case_id") or "").strip()
        view = str(finding.get("view") or "").strip()
        if not case_id or not view:
            continue
        key = f"{case_id}:{view}"
        if key not in seen:
            case_keys.append(key)
            seen.add(key)
    return case_keys


def _comparison_identity(finding: dict[str, Any]) -> str:
    return _finding_identity(finding)


def tdarr_matrix_compare_runs_payload(
    workspace_root: Path,
    *,
    left_run_id: Any = "",
    right_run_id: Any = "",
) -> dict[str, Any]:
    runs = tdarr_matrix_discover_runs(workspace_root)
    left = str(left_run_id or "").strip()
    right = str(right_run_id or "").strip()
    if not left and len(runs) >= 1:
        left = str(runs[0]["run_id"])
    if not right and len(runs) >= 2:
        right = str(runs[1]["run_id"])
    if not left or not right:
        return json_safe(
            {
                "schema_version": TDARR_MATRIX_COMPARE_SCHEMA_VERSION,
                "left_run_id": left,
                "right_run_id": right,
                "counts": {"new": 0, "resolved": 0, "repeated": 0, "changed": 0},
                "new": [],
                "resolved": [],
                "repeated": [],
                "changed": [],
                "message": "Two Tdarr Matrix runs are required for comparison.",
            }
        )
    left_payload = tdarr_matrix_console_payload(workspace_root, run_id=left, finding_limit=10_000)
    right_payload = tdarr_matrix_console_payload(workspace_root, run_id=right, finding_limit=10_000)
    left_by_identity = {_comparison_identity(finding): finding for finding in left_payload.get("findings", [])}
    right_by_identity = {_comparison_identity(finding): finding for finding in right_payload.get("findings", [])}
    left_keys = set(left_by_identity)
    right_keys = set(right_by_identity)
    new = [right_by_identity[key] for key in sorted(right_keys - left_keys)]
    resolved = [left_by_identity[key] for key in sorted(left_keys - right_keys)]
    repeated: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for key in sorted(left_keys & right_keys):
        left_finding = left_by_identity[key]
        right_finding = right_by_identity[key]
        repeated.append(left_finding)
        if (
            str(left_finding.get("severity") or "") != str(right_finding.get("severity") or "")
            or str(left_finding.get("message") or "") != str(right_finding.get("message") or "")
        ):
            changed.append(
                {
                    "identity": key,
                    "left": left_finding,
                    "right": right_finding,
                    "left_message": str(left_finding.get("message") or ""),
                    "right_message": str(right_finding.get("message") or ""),
                    "left_severity": str(left_finding.get("severity") or ""),
                    "right_severity": str(right_finding.get("severity") or ""),
                }
            )
    return json_safe(
        {
            "schema_version": TDARR_MATRIX_COMPARE_SCHEMA_VERSION,
            "left_run_id": left,
            "right_run_id": right,
            "counts": {
                "new": len(new),
                "resolved": len(resolved),
                "repeated": len(repeated),
                "changed": len(changed),
            },
            "new": new,
            "resolved": resolved,
            "repeated": repeated,
            "changed": changed,
            "new_findings": new,
            "resolved_findings": resolved,
            "repeated_findings": repeated,
            "changed_findings": changed,
        }
    )


__all__ = [
    "TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS",
    "TDARR_MATRIX_CONSOLE_SCHEMA_VERSION",
    "TDARR_MATRIX_COMPARE_SCHEMA_VERSION",
    "TDARR_MATRIX_EVIDENCE_COMMAND",
    "TDARR_MATRIX_RERUN_COMMAND",
    "TDARR_MATRIX_RUNS_SCHEMA_VERSION",
    "tdarr_matrix_compare_runs_payload",
    "tdarr_matrix_console_payload",
    "tdarr_matrix_discover_runs",
    "tdarr_matrix_evidence_open_result",
    "tdarr_matrix_evidence_path",
    "tdarr_matrix_finding_key",
    "tdarr_matrix_rerun_case_keys",
    "tdarr_matrix_runs_payload",
]
