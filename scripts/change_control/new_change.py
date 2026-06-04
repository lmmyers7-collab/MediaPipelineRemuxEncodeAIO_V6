from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
UNRELEASED_DIR = REPO_ROOT / "changes" / "unreleased"
RELEASED_DIR = REPO_ROOT / "changes" / "released"
VERSION_FILE = REPO_ROOT / "release" / "VERSION"

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


def _packet_paths() -> list[Path]:
    paths: list[Path] = []
    if UNRELEASED_DIR.exists():
        paths.extend(UNRELEASED_DIR.glob("*.json"))
    if RELEASED_DIR.exists():
        paths.extend(RELEASED_DIR.glob("**/*.json"))
    return sorted(path for path in paths if path.is_file())


def _next_change_id(today: dt.date) -> str:
    prefix = f"MP-CHANGE-{today:%Y-%m%d}-"
    pattern = re.compile(rf"^{re.escape(prefix)}(?P<seq>\d{{3}})$")
    max_sequence = 0

    for path in _packet_paths():
        match = pattern.match(path.stem)
        if match:
            max_sequence = max(max_sequence, int(match.group("seq")))

    return f"{prefix}{max_sequence + 1:03d}"


def _default_version_target() -> str:
    if VERSION_FILE.exists():
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        if version:
            return version
    return "unreleased"


def _build_packet(args: argparse.Namespace, today: dt.date) -> dict[str, object]:
    change_id = _next_change_id(today)
    return {
        "id": change_id,
        "title": args.title or "Untitled change",
        "version_target": args.version_target or _default_version_target(),
        "status": "planned",
        "type": args.change_type,
        "risk_level": args.risk,
        "date_started": today.isoformat(),
        "date_completed": None,
        "summary": "",
        "reason": "",
        "affected_areas": [],
        "behavior_before": "",
        "behavior_after": "",
        "files_touched": [],
        "tests_added": [],
        "manual_validation": [],
        "rollback_plan": "",
        "related_changes": [],
        "notes": "",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a new unreleased JSON change packet."
    )
    parser.add_argument("--title", default="", help="Short change title.")
    parser.add_argument(
        "--type",
        choices=sorted(ALLOWED_TYPES),
        default="docs",
        dest="change_type",
        help="Change type. Defaults to docs.",
    )
    parser.add_argument(
        "--risk",
        choices=sorted(ALLOWED_RISKS),
        default="low",
        help="Change risk level. Defaults to low.",
    )
    parser.add_argument(
        "--version-target",
        default="",
        help="Target version. Defaults to release/VERSION when available.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    today = dt.date.today()
    packet = _build_packet(args, today)
    change_id = str(packet["id"])

    UNRELEASED_DIR.mkdir(parents=True, exist_ok=True)
    packet_path = UNRELEASED_DIR / f"{change_id}.json"
    if packet_path.exists():
        raise SystemExit(f"Change packet already exists: {packet_path}")

    relative_path = packet_path.relative_to(REPO_ROOT).as_posix()
    packet["files_touched"] = [relative_path]
    packet_path.write_text(
        json.dumps(packet, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Created {relative_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
