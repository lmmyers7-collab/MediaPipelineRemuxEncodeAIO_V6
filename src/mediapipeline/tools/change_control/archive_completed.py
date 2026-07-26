from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mediapipeline.tools.paths import find_repo_root

from . import validate_changes


REPO_ROOT = find_repo_root(Path(__file__))
UNRELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "unreleased"
ARCHIVED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "archived"
RELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "released"
SUMMARY_ROOT = REPO_ROOT / "docs" / "generated" / "summaries"

REGEN_MODULES = (
    "mediapipeline.tools.change_control.build_change_index",
    "mediapipeline.tools.change_control.build_changelog",
)
REGENERATED_OUTPUTS = (
    REPO_ROOT / "docs" / "change_control" / "CHANGE_INDEX.md",
    REPO_ROOT / "docs" / "change_control" / "CHANGELOG.md",
)


@dataclass(frozen=True)
class ArchiveMove:
    change_id: str
    source: Path
    target: Path
    summary: Path


@dataclass(frozen=True)
class ArchivePlan:
    moves: tuple[ArchiveMove, ...]
    refusals: tuple[str, ...]
    invalid_skipped: tuple[str, ...]
    already_archived: tuple[str, ...]
    active_open_count: int


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _load_packet(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        return None, f"{_relative(path)}: invalid or unreadable JSON: {exc}"
    if not isinstance(packet, dict):
        return None, f"{_relative(path)}: packet must be a JSON object"
    return packet, ""


def _parse_date(value: Any) -> dt.date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        return None


def _summary_path(source: Path) -> Path:
    relative = source.relative_to(REPO_ROOT).as_posix()
    return SUMMARY_ROOT.joinpath(*Path(relative + ".md").parts)


def _existing_locations(change_id: str) -> list[Path]:
    name = f"{change_id}.json"
    locations: list[Path] = []
    for root in (ARCHIVED_DIR, RELEASED_DIR):
        if root.exists():
            locations.extend(path for path in root.rglob(name) if path.is_file())
    return sorted(locations)


def build_plan(
    *,
    packet_ids: tuple[str, ...] = (),
    completed_through: dt.date | None = None,
    limit: int | None = None,
) -> ArchivePlan:
    requested = {value.strip() for value in packet_ids if value.strip()}
    active_paths = sorted(
        path for path in UNRELEASED_DIR.glob("*.json") if path.is_file()
    ) if UNRELEASED_DIR.exists() else []
    by_id = {path.stem: path for path in active_paths}
    refusals: list[str] = []
    invalid_skipped: list[str] = []
    already_archived: list[str] = []
    eligible: list[ArchiveMove] = []
    active_open_count = 0

    if requested:
        for change_id in sorted(requested - set(by_id)):
            locations = _existing_locations(change_id)
            if locations:
                already_archived.append(
                    f"{change_id}: already stored at {_relative(locations[0])}"
                )
            else:
                refusals.append(f"{change_id}: active packet not found")

    for path in active_paths:
        packet, load_error = _load_packet(path)
        if load_error:
            if path.stem in requested:
                refusals.append(load_error)
            elif not requested:
                invalid_skipped.append(load_error)
            continue
        assert packet is not None
        change_id = str(packet.get("id") or path.stem)
        status = str(packet.get("status") or "")
        if status != "complete":
            active_open_count += 1
            if change_id in requested:
                refusals.append(
                    f"{_relative(path)}: refusing status={status or 'missing'}; only complete packets are eligible"
                )
            continue
        if requested and change_id not in requested:
            continue

        completed_date = _parse_date(packet.get("date_completed"))
        if completed_date is None:
            message = (
                f"{_relative(path)}: complete packet requires a valid date_completed before archival"
            )
            if change_id in requested:
                refusals.append(message)
            else:
                invalid_skipped.append(message)
            continue
        if completed_through is not None and completed_date > completed_through:
            continue

        packet_errors = validate_changes.packet_validation_errors(
            path,
            packet,
            repo_root=REPO_ROOT,
        )
        if packet_errors:
            if change_id in requested:
                refusals.extend(packet_errors)
            else:
                invalid_skipped.extend(packet_errors)
            continue

        bucket = completed_date.strftime("%Y-%m")
        target = ARCHIVED_DIR / bucket / path.name
        if target.exists():
            message = (
                f"{_relative(path)}: refusing existing archive target {_relative(target)}"
            )
            if change_id in requested:
                refusals.append(message)
            else:
                invalid_skipped.append(message)
            continue
        eligible.append(
            ArchiveMove(
                change_id=change_id,
                source=path,
                target=target,
                summary=_summary_path(path),
            )
        )

    eligible.sort(key=lambda item: item.change_id)
    if limit is not None:
        eligible = eligible[:limit]
    return ArchivePlan(
        moves=tuple(eligible),
        refusals=tuple(sorted(set(refusals))),
        invalid_skipped=tuple(sorted(set(invalid_skipped))),
        already_archived=tuple(sorted(set(already_archived))),
        active_open_count=active_open_count,
    )


def _run_regeneration() -> None:
    for module in REGEN_MODULES:
        subprocess.run(
            [sys.executable, "-m", module],
            cwd=REPO_ROOT,
            check=True,
        )


def apply_plan(plan: ArchivePlan) -> None:
    if plan.refusals:
        raise SystemExit("Refusing archival because the preview contains errors.")

    for move in plan.moves:
        if move.target.exists():
            raise SystemExit(f"Refusing to overwrite existing packet: {_relative(move.target)}")

    moved: list[ArchiveMove] = []
    removed_summaries: dict[Path, bytes] = {}
    generated_snapshots = {
        path: path.read_bytes() if path.is_file() else None
        for path in REGENERATED_OUTPUTS
    }
    try:
        for move in plan.moves:
            move.target.parent.mkdir(parents=True, exist_ok=True)
            move.source.replace(move.target)
            moved.append(move)
            if move.summary.is_file():
                removed_summaries[move.summary] = move.summary.read_bytes()
                move.summary.unlink()
        _run_regeneration()
    except Exception:
        for path, content in generated_snapshots.items():
            if content is None:
                if path.is_file():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        for summary, content in removed_summaries.items():
            summary.parent.mkdir(parents=True, exist_ok=True)
            summary.write_bytes(content)
        for move in reversed(moved):
            if move.target.is_file():
                move.source.parent.mkdir(parents=True, exist_ok=True)
                move.target.replace(move.source)
        raise


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or archive validated completed packets without marking them released. "
            "Preview is the default; pass --apply to move evidence."
        )
    )
    parser.add_argument(
        "--packet-id",
        "--id",
        action="append",
        default=[],
        help="Select an exact packet ID. Repeat for multiple packets.",
    )
    parser.add_argument(
        "--completed-through",
        default="",
        help="Select packets completed on or before YYYY-MM-DD.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Archive at most this many eligible packets after stable ID sorting.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the previewed moves and regenerate indexes.",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    if not args.packet_id and not args.completed_through and args.limit is None:
        parser.error("select packets with --packet-id/--id, --completed-through, or --limit")
    return args


def _completed_through(value: str) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit("--completed-through must use a valid YYYY-MM-DD date") from exc


def _print_plan(plan: ArchivePlan, *, applying: bool) -> None:
    print("Completed packet archival " + ("apply:" if applying else "preview:"))
    print(f"- Eligible moves: {len(plan.moves)}")
    print(f"- Active planned/in-progress packets left untouched: {plan.active_open_count}")
    print(f"- Already archived/released: {len(plan.already_archived)}")
    print(f"- Refusals: {len(plan.refusals)}")
    print(f"- Invalid/incomplete packets skipped: {len(plan.invalid_skipped)}")
    for move in plan.moves:
        print(f"  - {_relative(move.source)} -> {_relative(move.target)}")
    for message in plan.already_archived:
        print(f"  - NOOP: {message}")
    for message in plan.refusals:
        print(f"  - REFUSED: {message}", file=sys.stderr)
    for message in plan.invalid_skipped:
        print(f"  - SKIPPED INVALID: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    plan = build_plan(
        packet_ids=tuple(args.packet_id),
        completed_through=_completed_through(args.completed_through),
        limit=args.limit,
    )
    _print_plan(plan, applying=args.apply)
    if plan.refusals:
        return 1
    if args.apply and plan.moves:
        apply_plan(plan)
        print(f"Archived {len(plan.moves)} packet(s); generated indexes refreshed.")
    elif args.apply:
        print("No eligible packets required changes.")
    else:
        print("Preview only; no files changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
