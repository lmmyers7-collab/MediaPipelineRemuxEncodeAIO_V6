from __future__ import annotations

import json
import re
import sys
import datetime as dt
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
UNRELEASED_DIR = REPO_ROOT / "changes" / "unreleased"
RELEASED_DIR = REPO_ROOT / "changes" / "released"
VERSION_FILE = REPO_ROOT / "release" / "VERSION"
RELEASE_HISTORY_DIR = REPO_ROOT / "release" / "history"

REQUIRED_FIELDS = [
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
]
ALLOWED_STATUSES = {"planned", "in_progress", "complete"}
ALLOWED_TYPES = {
    "feature",
    "bugfix",
    "behavior_change",
    "refactor",
    "config",
    "schema",
    "docs",
    "test",
    "release",
    "tooling",
}
ALLOWED_RISKS = {"low", "medium", "high", "critical"}
CHANGE_ID_RE = re.compile(r"^MP-CHANGE-\d{4}-\d{4}-\d{3}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _packet_paths() -> list[Path]:
    paths: list[Path] = []
    if UNRELEASED_DIR.exists():
        paths.extend(UNRELEASED_DIR.glob("*.json"))
    if RELEASED_DIR.exists():
        paths.extend(RELEASED_DIR.glob("**/*.json"))
    return sorted(path for path in paths if path.is_file())


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _load_packet(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(
            f"{_relative(path)}: invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )
        return None
    except UnicodeDecodeError as exc:
        errors.append(f"{_relative(path)}: could not read as UTF-8 JSON: {exc}")
        return None

    if not isinstance(data, dict):
        errors.append(f"{_relative(path)}: packet must be a JSON object")
        return None

    return data


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _validate_date(label: str, field: str, value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, str) or not DATE_RE.match(value):
        return [f"{label}: {field} must use YYYY-MM-DD format when present"]
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return [f"{label}: {field} is not a valid calendar date"]
    return []


def _validate_packet(path: Path, packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    label = _relative(path)

    for field in REQUIRED_FIELDS:
        if field not in packet:
            errors.append(f"{label}: missing required field '{field}'")

    change_id = packet.get("id")
    if change_id != path.stem:
        errors.append(f"{label}: id must match filename stem '{path.stem}'")
    if not isinstance(change_id, str) or not CHANGE_ID_RE.match(change_id):
        errors.append(
            f"{label}: id must match MP-CHANGE-YYYY-MMDD-### format"
        )

    status = packet.get("status")
    if status not in ALLOWED_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_STATUSES))
        errors.append(f"{label}: invalid status '{status}', expected one of: {allowed}")

    change_type = packet.get("type")
    if change_type not in ALLOWED_TYPES:
        allowed = ", ".join(sorted(ALLOWED_TYPES))
        errors.append(f"{label}: invalid type '{change_type}', expected one of: {allowed}")

    risk = packet.get("risk_level")
    if risk not in ALLOWED_RISKS:
        allowed = ", ".join(sorted(ALLOWED_RISKS))
        errors.append(
            f"{label}: invalid risk_level '{risk}', expected one of: {allowed}"
        )

    errors.extend(_validate_date(label, "date_started", packet.get("date_started")))
    errors.extend(_validate_date(label, "date_completed", packet.get("date_completed")))

    if status == "complete":
        for field in [
            "summary",
            "reason",
            "behavior_before",
            "behavior_after",
            "rollback_plan",
        ]:
            if not _non_empty_string(packet.get(field)):
                errors.append(f"{label}: {field} must be non-empty when complete")
        if not _non_empty_list(packet.get("files_touched")):
            errors.append(f"{label}: files_touched must be non-empty when complete")
        if not _non_empty_list(packet.get("manual_validation")):
            errors.append(
                f"{label}: manual_validation must be non-empty when complete"
            )

    if risk in {"high", "critical"}:
        if not (
            _non_empty_string(packet.get("notes"))
            or _non_empty_string(packet.get("rollback_plan"))
        ):
            errors.append(
                f"{label}: high/critical changes require notes or rollback detail"
            )

    return errors


def _released_version_for(path: Path) -> str | None:
    try:
        relative = path.relative_to(RELEASED_DIR)
    except ValueError:
        return None
    if len(relative.parts) < 2:
        return ""
    return relative.parts[0]


def _validate_released_packet(path: Path, packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    label = _relative(path)
    released_version = _released_version_for(path)
    if released_version is None:
        return errors

    if not released_version:
        errors.append(f"{label}: released packets must live under changes/released/<version>/")
        return errors

    if packet.get("version_target") != released_version:
        errors.append(
            f"{label}: version_target must match released folder '{released_version}'"
        )

    if packet.get("status") in {"planned", "in_progress"}:
        errors.append(f"{label}: released packets must not be planned or in_progress")

    if packet.get("status") == "complete" and not _non_empty_string(
        packet.get("date_completed")
    ):
        errors.append(f"{label}: released complete packets require date_completed")

    return errors


def main() -> int:
    packet_paths = _packet_paths()
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: dict[str, Path] = {}
    released_versions: set[str] = set()

    if not VERSION_FILE.exists():
        errors.append("release/VERSION is missing")

    if not packet_paths:
        errors.append("No change packets found under changes/unreleased or changes/released")

    for path in packet_paths:
        packet = _load_packet(path, errors)
        if packet is not None:
            errors.extend(_validate_packet(path, packet))
            errors.extend(_validate_released_packet(path, packet))
            change_id = packet.get("id")
            if isinstance(change_id, str):
                if change_id in seen_ids:
                    errors.append(
                        f"{_relative(path)}: duplicate change id also found in "
                        f"{_relative(seen_ids[change_id])}"
                    )
                else:
                    seen_ids[change_id] = path

            released_version = _released_version_for(path)
            if released_version:
                released_versions.add(released_version)

    for version in sorted(released_versions):
        archive_dir = RELEASE_HISTORY_DIR / version
        if not archive_dir.exists():
            warnings.append(
                f"release history archive missing for {version}: "
                f"{archive_dir.relative_to(REPO_ROOT).as_posix()}"
            )

    if errors:
        print("Change validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if warnings:
        print("Change validation warnings:", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    print(f"Change validation passed: {len(packet_paths)} packet(s) valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
