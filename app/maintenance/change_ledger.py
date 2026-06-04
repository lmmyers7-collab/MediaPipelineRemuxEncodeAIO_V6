"""Read-only change-control ledger payloads for Maintenance."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import sys
from typing import Any

CHANGE_CONTROL_DIR = Path(__file__).resolve().parents[2] / "scripts" / "change_control"
if str(CHANGE_CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CHANGE_CONTROL_DIR))

import packet_coverage


CHANGE_LEDGER_SCHEMA_VERSION = "desktop_change_ledger.v1"
CHANGE_LEDGER_HYGIENE_SCHEMA_VERSION = "desktop_change_ledger_hygiene.v1"

REQUIRED_PACKET_FIELDS = (
    "id",
    "title",
    "version_target",
    "status",
    "type",
    "risk_level",
    "date_started",
    "date_completed",
    "summary",
    "reason",
    "affected_areas",
    "behavior_before",
    "behavior_after",
    "files_touched",
    "tests_added",
    "manual_validation",
    "rollback_plan",
    "related_changes",
    "notes",
)

COMPLETE_PACKET_REQUIRED_FIELDS = (
    "summary",
    "reason",
    "behavior_before",
    "behavior_after",
    "files_touched",
    "manual_validation",
    "rollback_plan",
)

SOURCE_PATHS = (
    "CHANGELOG.md",
    "Docs/change_control/CHANGELOG.md",
    "Docs/change_control/CHANGE_INDEX.md",
    "changes/unreleased",
    "changes/released",
)


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [_as_text(item) for item in _as_list(value) if _as_text(item)]


def _packet_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    unreleased = root / "changes" / "unreleased"
    released = root / "changes" / "released"
    if unreleased.exists():
        paths.extend(unreleased.glob("*.json"))
    if released.exists():
        paths.extend(released.glob("**/*.json"))
    return sorted(path for path in paths if path.is_file())


def _release_location(root: Path, path: Path) -> tuple[str, str]:
    try:
        relative = path.relative_to(root / "changes" / "released")
    except ValueError:
        return "unreleased", ""
    version = relative.parts[0] if len(relative.parts) > 1 else ""
    return "released", version


def _packet_issue(source_path: str, severity: str, message: str) -> dict[str, Any]:
    return {
        "source_path": source_path,
        "severity": severity,
        "message": message,
    }


def _load_packet(root: Path, path: Path, issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    source_path = _relative_path(root, path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(_packet_issue(source_path, "error", f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"))
        return None
    except OSError as exc:
        issues.append(_packet_issue(source_path, "error", f"Could not read packet: {exc}"))
        return None
    if not isinstance(payload, dict):
        issues.append(_packet_issue(source_path, "error", "Change packet must be a JSON object."))
        return None
    return payload


def _missing_packet_fields(packet: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_PACKET_FIELDS if field not in packet]


def _incomplete_complete_fields(packet: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in COMPLETE_PACKET_REQUIRED_FIELDS:
        value = packet.get(field)
        if isinstance(value, list):
            if not value:
                missing.append(field)
        elif not _as_text(value):
            missing.append(field)
    return missing


def _python_group(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return "other_python"
    if parts[0] == "app" and len(parts) > 1:
        return f"app/{parts[1]}"
    if parts[0] == "DesktopApp" and len(parts) > 2:
        if parts[1] == "tests":
            return "DesktopApp/tests"
        if parts[1] == "mediapipeline_desktop_app":
            return "DesktopApp/mediapipeline_desktop_app"
    if parts[0] == "scripts" and len(parts) > 1:
        return f"scripts/{parts[1]}"
    if parts[0] == "tests" and len(parts) > 1:
        return f"tests/{parts[1]}"
    return parts[0] if len(parts) == 1 else f"{parts[0]}/{parts[1]}"


def python_impact_for_files(files_touched: list[str]) -> dict[str, Any]:
    python_files = sorted({path for path in files_touched if path.replace("\\", "/").casefold().endswith(".py")})
    grouped: dict[str, list[str]] = {}
    for path in python_files:
        grouped.setdefault(_python_group(path), []).append(path)
    groups = [
        {
            "group": group,
            "count": len(paths),
            "files": paths,
            "summary": f"{group}: {len(paths)} Python file(s)",
        }
        for group, paths in sorted(grouped.items())
    ]
    if not python_files:
        summary = "No Python scripts touched."
    else:
        summary = f"{len(python_files)} Python script(s): " + ", ".join(f"{item['group']} ({item['count']})" for item in groups)
    return {
        "schema_version": "desktop_change_python_impact.v1",
        "file_count": len(python_files),
        "files": python_files,
        "groups": groups,
        "summary": summary,
    }


def _validation_status(packet: dict[str, Any], missing_fields: list[str], incomplete_fields: list[str]) -> str:
    if missing_fields:
        return "invalid"
    if _as_text(packet.get("status")) == "complete" and incomplete_fields:
        return "incomplete"
    if _as_text(packet.get("status")) == "complete":
        return "complete"
    return "open"


def _row_from_packet(root: Path, path: Path, packet: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any]:
    source_path = _relative_path(root, path)
    missing_fields = _missing_packet_fields(packet)
    incomplete_fields = _incomplete_complete_fields(packet) if _as_text(packet.get("status")) == "complete" else []
    for field in missing_fields:
        issues.append(_packet_issue(source_path, "error", f"Missing required field: {field}"))
    if incomplete_fields:
        issues.append(_packet_issue(source_path, "warning", "Complete packet has empty evidence fields: " + ", ".join(incomplete_fields)))

    files_touched = _string_list(packet.get("files_touched"))
    location, release_version = _release_location(root, path)
    change_id = _as_text(packet.get("id")) or path.stem
    return {
        "row_key": change_id,
        "id": change_id,
        "title": _as_text(packet.get("title")) or "(untitled change)",
        "version_target": _as_text(packet.get("version_target")),
        "status": _as_text(packet.get("status")) or "unknown",
        "type": _as_text(packet.get("type")) or "unknown",
        "risk_level": _as_text(packet.get("risk_level")) or "unknown",
        "date_started": _as_text(packet.get("date_started")),
        "date_completed": _as_text(packet.get("date_completed")),
        "summary": _as_text(packet.get("summary")),
        "reason": _as_text(packet.get("reason")),
        "affected_areas": _string_list(packet.get("affected_areas")),
        "behavior_before": _as_text(packet.get("behavior_before")),
        "behavior_after": _as_text(packet.get("behavior_after")),
        "files_touched": files_touched,
        "tests_added": _string_list(packet.get("tests_added")),
        "manual_validation": _string_list(packet.get("manual_validation")),
        "rollback_plan": _as_text(packet.get("rollback_plan")),
        "related_changes": _string_list(packet.get("related_changes")),
        "notes": _as_text(packet.get("notes")),
        "source_path": source_path,
        "location": location,
        "release_version": release_version,
        "validation_status": _validation_status(packet, missing_fields, incomplete_fields),
        "missing_fields": missing_fields,
        "incomplete_fields": incomplete_fields,
        "python_impact": python_impact_for_files(files_touched),
    }


def _source_path_status(root: Path, packet_paths: list[Path]) -> list[dict[str, Any]]:
    newest_packet_mtime = max((path.stat().st_mtime for path in packet_paths), default=0.0)
    rows: list[dict[str, Any]] = []
    for relative in SOURCE_PATHS:
        path = root / relative
        exists = path.exists()
        stale = bool(exists and path.is_file() and newest_packet_mtime and path.stat().st_mtime < newest_packet_mtime)
        rows.append(
            {
                "path": relative,
                "exists": exists,
                "kind": "directory" if path.is_dir() else "file",
                "stale": stale,
            }
        )
    return rows


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    statuses = Counter(_as_text(row.get("status")) for row in rows)
    risks = Counter(_as_text(row.get("risk_level")) for row in rows)
    locations = Counter(_as_text(row.get("location")) for row in rows)
    return {
        "total": len(rows),
        "unreleased": locations["unreleased"],
        "released": locations["released"],
        "planned": statuses["planned"],
        "in_progress": statuses["in_progress"],
        "complete": statuses["complete"],
        "high_or_critical_risk": risks["high"] + risks["critical"],
    }


def _aggregate_python_impact(rows: list[dict[str, Any]]) -> dict[str, Any]:
    files: list[str] = []
    for row in rows:
        files.extend(_string_list((row.get("python_impact") or {}).get("files") if isinstance(row.get("python_impact"), dict) else []))
    return python_impact_for_files(files)


def _hygiene(
    rows: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    source_paths: list[dict[str, Any]],
    coverage: packet_coverage.CoverageResult,
) -> dict[str, Any]:
    uncovered = list(coverage.uncovered_files)
    generated_issues = [
        _packet_issue(str(item["path"]), "warning", "Generated changelog/index may be stale compared with latest packet.")
        for item in source_paths
        if item["path"] in {"Docs/change_control/CHANGELOG.md", "Docs/change_control/CHANGE_INDEX.md"} and item.get("stale")
    ]
    missing_source_issues = [
        _packet_issue(str(item["path"]), "warning", "Expected changelog source path is missing.")
        for item in source_paths
        if not item.get("exists")
    ]
    coverage_issues = [
        _packet_issue(".git", "warning", f"Coverage check unavailable: {error}")
        for error in coverage.errors
    ]
    if uncovered:
        sample = ", ".join(uncovered[:8])
        suffix = f" (+{len(uncovered) - 8} more)" if len(uncovered) > 8 else ""
        coverage_issues.insert(
            0,
            _packet_issue(
                ".git",
                "warning",
                f"{len(uncovered)} changed file(s) are not listed in files_touched of any unreleased packet: {sample}{suffix}",
            ),
        )
    all_issues = coverage_issues + issues + generated_issues + missing_source_issues
    has_packet_error = any(issue.get("severity") == "error" for issue in issues)
    operator_status = "blocked" if has_packet_error else "review" if (uncovered or all_issues) else "ready"
    summary_lines = [
        f"Unrecorded changed files: {len(uncovered)}",
        f"Change ledger hygiene: {operator_status}",
        f"Loaded packets: {len(rows)}",
        f"Issues: {len(all_issues)}",
        f"Coverage scope: {coverage.scope}",
        "Mutation guardrail: this ledger is read-only. It does not edit changelog files, create packets, run codegen, launch work, or touch media.",
    ]
    return {
        "schema_version": CHANGE_LEDGER_HYGIENE_SCHEMA_VERSION,
        "read_only": True,
        "operator_status": operator_status,
        "issue_count": len(all_issues),
        "issues": all_issues,
        "unlogged_change_count": len(uncovered),
        "unlogged_changes": uncovered[:25],
        "unrecorded_change_count": len(uncovered),
        "unrecorded_changes": uncovered[:25],
        "summary_lines": summary_lines,
    }


def change_ledger_payload(root: Path) -> dict[str, Any]:
    repo_root = Path(root)
    packet_paths = _packet_paths(repo_root)
    issues: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for path in packet_paths:
        packet = _load_packet(repo_root, path, issues)
        if packet is not None:
            rows.append(_row_from_packet(repo_root, path, packet, issues))
    rows.sort(key=lambda item: _as_text(item.get("id")), reverse=True)
    source_paths = _source_path_status(repo_root, packet_paths)
    counts = _counts(rows)
    coverage = packet_coverage.coverage_for_worktree(repo_root, require_git=False)
    hygiene = _hygiene(rows, issues, source_paths, coverage)
    summary_lines = [
        f"Change ledger: {counts['total']} packet(s)",
        f"Unreleased: {counts['unreleased']}; released: {counts['released']}",
        f"Open: {counts['planned'] + counts['in_progress']}; complete: {counts['complete']}",
        f"High/critical risk: {counts['high_or_critical_risk']}",
        "Canonical sources: root CHANGELOG.md plus structured change-control packets and generated Docs/change_control outputs.",
    ]
    return {
        "schema_version": CHANGE_LEDGER_SCHEMA_VERSION,
        "read_only": True,
        "rows": rows,
        "counts": counts,
        "coverage": coverage.to_dict(),
        "python_impact": _aggregate_python_impact(rows),
        "hygiene": hygiene,
        "source_paths": source_paths,
        "warnings": [str(issue.get("message") or "") for issue in hygiene.get("issues", []) if issue.get("severity") != "error"],
        "summary_lines": summary_lines,
    }


__all__ = [
    "CHANGE_LEDGER_SCHEMA_VERSION",
    "change_ledger_payload",
    "python_impact_for_files",
]
