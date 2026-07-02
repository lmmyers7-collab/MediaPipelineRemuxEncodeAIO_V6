from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any

from . import packet_coverage


REPO_ROOT = find_repo_root(Path(__file__))
UNRELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "unreleased"
CHANGE_ID_RE = re.compile(r"^MP-CHANGE-\d{4}-\d{4}-\d{3}$")
STATUSES = ("planned", "in_progress", "complete")
LIST_FIELDS = (
    "affected_areas",
    "files_touched",
    "tests_added",
    "manual_validation",
    "related_changes",
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append changed paths and evidence to an unreleased change packet."
    )
    parser.add_argument("change_id", help="Change packet ID, for example MP-CHANGE-2026-0604-001.")
    parser.add_argument("paths", nargs="*", help="Repo-relative paths to append to files_touched.")
    parser.add_argument(
        "--from-staged",
        action="store_true",
        help="Append the currently staged changed paths to files_touched.",
    )
    parser.add_argument(
        "--validation",
        action="append",
        default=[],
        help='Append manual validation evidence, for example "command - passed".',
    )
    parser.add_argument(
        "--test",
        action="append",
        default=[],
        dest="tests_added",
        help="Append a test path to tests_added.",
    )
    parser.add_argument(
        "--area",
        action="append",
        default=[],
        dest="areas",
        help="Append an affected area label.",
    )
    parser.add_argument(
        "--status",
        choices=STATUSES,
        help="Set packet status.",
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Set status to complete and date_completed to today's date.",
    )
    parser.add_argument(
        "--note",
        action="append",
        default=[],
        dest="notes",
        help="Append a short note without erasing existing notes.",
    )
    return parser.parse_args(argv)


def _packet_path(change_id: str) -> Path:
    return UNRELEASED_DIR / f"{change_id}.json"


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _load_packet(path: Path) -> dict[str, Any]:
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{_relative(path)}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise SystemExit(f"{_relative(path)}: could not read packet: {exc}") from exc
    if not isinstance(packet, dict):
        raise SystemExit(f"{_relative(path)}: packet must be a JSON object")
    return packet


def _normalize_path(value: str) -> str:
    return packet_coverage.normalize_repo_path(value)


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _merge_list(packet: dict[str, Any], field: str, values: list[str]) -> None:
    merged = {_normalize_path(item) if field in {"files_touched", "tests_added"} else str(item).strip() for item in _string_items(packet.get(field))}
    for value in values:
        normalized = _normalize_path(value) if field in {"files_touched", "tests_added"} else str(value).strip()
        if normalized:
            merged.add(normalized)
    packet[field] = sorted(merged)


def _append_notes(packet: dict[str, Any], notes: list[str]) -> None:
    clean_notes = [str(note).strip() for note in notes if str(note).strip()]
    if not clean_notes:
        return
    existing = str(packet.get("notes") or "").strip()
    lines = [line.strip() for line in existing.splitlines() if line.strip()]
    for note in clean_notes:
        if note not in lines:
            lines.append(note)
    packet["notes"] = "\n".join(lines)


def _staged_paths() -> list[str]:
    paths, error = packet_coverage.changed_files_from_staged(REPO_ROOT, require_git=True)
    if error:
        raise SystemExit(error)
    return paths


def _validate_change_id(change_id: str) -> None:
    if not CHANGE_ID_RE.match(change_id):
        raise SystemExit("change_id must match MP-CHANGE-YYYY-MMDD-### format")


def update_packet(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    change_id = str(args.change_id).strip()
    _validate_change_id(change_id)
    packet_path = _packet_path(change_id)
    if not packet_path.exists():
        raise SystemExit(f"Unreleased change packet not found: ops/release/changes/unreleased/{change_id}.json")

    packet = _load_packet(packet_path)
    if packet.get("id") not in {None, change_id}:
        raise SystemExit(f"{_relative(packet_path)}: packet id {packet.get('id')!r} does not match {change_id!r}")

    touched_paths = [_normalize_path(path) for path in args.paths if _normalize_path(path)]
    if args.from_staged:
        touched_paths.extend(_staged_paths())
    touched_paths.append(_relative(packet_path))

    _merge_list(packet, "files_touched", touched_paths)
    _merge_list(packet, "tests_added", list(args.tests_added))
    _merge_list(packet, "manual_validation", list(args.validation))
    _merge_list(packet, "affected_areas", list(args.areas))
    for field in LIST_FIELDS:
        if field not in packet:
            packet[field] = []
        elif isinstance(packet[field], list):
            _merge_list(packet, field, [])
    _append_notes(packet, list(args.notes))

    if args.complete:
        packet["status"] = "complete"
        packet["date_completed"] = dt.date.today().isoformat()
    elif args.status:
        packet["status"] = args.status

    packet_path.write_text(
        json.dumps(packet, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return packet_path, packet


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    packet_path, packet = update_packet(args)
    print(
        "Updated "
        f"{_relative(packet_path)}: "
        f"{len(packet.get('files_touched') or [])} files_touched, "
        f"status={packet.get('status')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
