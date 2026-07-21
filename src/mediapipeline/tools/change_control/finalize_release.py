from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any

from .build_release_manifest import validate_version_label


REPO_ROOT = find_repo_root(Path(__file__))
UNRELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "unreleased"
RELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "released"
VERSION_FILE = REPO_ROOT / "ops" / "release" / "metadata" / "VERSION"
MANIFEST_PATH = REPO_ROOT / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"
CHANGELOG_PATH = REPO_ROOT / "docs" / "change_control" / "CHANGELOG.md"
INDEX_PATH = REPO_ROOT / "docs" / "change_control" / "CHANGE_INDEX.md"
HISTORY_ROOT = REPO_ROOT / "ops" / "release" / "metadata" / "history"

CHANNELS = {"dev", "alpha", "beta", "rc", "stable", "hotfix", "local"}
ARCHIVE_FILES = [
    VERSION_FILE,
    MANIFEST_PATH,
    CHANGELOG_PATH,
    INDEX_PATH,
]


def _packet_paths() -> list[Path]:
    paths: list[Path] = []
    if UNRELEASED_DIR.exists():
        paths.extend(UNRELEASED_DIR.glob("*.json"))
    archived = UNRELEASED_DIR.parent / "archived"
    if archived.exists():
        paths.extend(archived.glob("**/*.json"))
    return sorted(path for path in paths if path.is_file())


def _load_packet(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_unreleased_packets() -> list[tuple[Path, dict[str, Any]]]:
    packets: list[tuple[Path, dict[str, Any]]] = []
    for path in _packet_paths():
        packet = _load_packet(path)
        if packet.get("status") == "complete":
            packets.append((path, packet))
    return packets


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _run_script(name: str, *args: str) -> None:
    module = f"mediapipeline.tools.change_control.{Path(name).stem}"
    command = [sys.executable, "-m", module, *args]
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def _read_version_file() -> str:
    if not VERSION_FILE.exists():
        return ""
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def _write_packet(path: Path, packet: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(packet, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _snapshot_files(paths: list[Path]) -> dict[Path, bytes | None]:
    snapshots: dict[Path, bytes | None] = {}
    for path in paths:
        snapshots[path] = path.read_bytes() if path.is_file() else None
    return snapshots


def _restore_file_snapshots(snapshots: dict[Path, bytes | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            if path.is_file():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _remove_created_dir(path: Path, *, existed_before: bool) -> None:
    if existed_before or not path.exists():
        return
    shutil.rmtree(path)


def _dedupe_sorted(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value).strip()})


def _list_values(packets: list[dict[str, Any]], field: str) -> list[str]:
    values: list[Any] = []
    for packet in packets:
        field_value = packet.get(field)
        if isinstance(field_value, list):
            values.extend(field_value)
    return _dedupe_sorted(values)


def _highest_risk(packets: list[dict[str, Any]]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    risks = [str(packet.get("risk_level", "")) for packet in packets]
    known = [risk for risk in risks if risk in order]
    if not known:
        return "-"
    return max(known, key=lambda risk: order[risk])


def _summary_markdown(
    version: str,
    channel: str,
    release_date: str,
    packets: list[dict[str, Any]],
) -> str:
    included_changes = [str(packet.get("id", "")) for packet in packets]
    high_risks = []
    rollback_notes = []
    for packet in packets:
        change_id = str(packet.get("id", ""))
        risk = str(packet.get("risk_level", ""))
        if risk in {"high", "critical"}:
            high_risks.append(
                f"{change_id}: {packet.get('title', '')} ({risk}) - {packet.get('summary', '')}"
            )
        rollback = str(packet.get("rollback_plan", "")).strip()
        if rollback:
            rollback_notes.append(f"{change_id}: {rollback}")

    lines = [
        f"# Release Summary - {version}",
        "",
        f"- Version: `{version}`",
        f"- Channel: `{channel}`",
        f"- Release date: {release_date}",
        f"- Highest risk: `{_highest_risk(packets)}`",
        "",
        "## Included Change IDs",
        "",
    ]
    lines.extend(f"- {change_id}" for change_id in included_changes or ["-"])
    lines.extend(["", "## Affected Areas", ""])
    lines.extend(f"- {area}" for area in _list_values(packets, "affected_areas") or ["-"])
    lines.extend(["", "## High/Critical Risks", ""])
    lines.extend(f"- {risk}" for risk in sorted(high_risks) or ["-"])
    lines.extend(["", "## Rollback Notes", ""])
    lines.extend(f"- {note}" for note in sorted(rollback_notes) or ["-"])
    return "\n".join(lines).rstrip() + "\n"


def _print_dry_run(
    version: str,
    channel: str,
    packets: list[tuple[Path, dict[str, Any]]],
) -> None:
    release_dir = RELEASED_DIR / version
    archive_dir = HISTORY_ROOT / version
    current_version = _read_version_file()

    print("Finalize release dry run:")
    print(f"- Version: {version}")
    print(f"- Channel: {channel}")
    if current_version != version:
        print(f"- Would update ops/release/metadata/VERSION from '{current_version or '-'}' to '{version}'")
    else:
        print("- ops/release/metadata/VERSION already matches")

    print("- Would move completed packets:")
    if packets:
        for path, packet in packets:
            target = release_dir / path.name
            print(f"  - {_relative(path)} -> {_relative(target)} ({packet.get('id')})")
    else:
        print("  - No completed unreleased packets")

    today = dt.date.today().isoformat()
    print("- Would set packet metadata:")
    for _path, packet in packets:
        change_id = packet.get("id")
        print(f"  - {change_id}: version_target={version}, date_completed={packet.get('date_completed') or today}")

    print("- Would generate:")
    print("  - docs/change_control/CHANGE_INDEX.md")
    print("  - docs/change_control/CHANGELOG.md")
    print("  - ops/release/metadata/RELEASE_MANIFEST.json")
    print("- Would archive into:")
    print(f"  - {_relative(archive_dir)}")
    for archive_file in ARCHIVE_FILES:
        print(f"  - copy {_relative(archive_file)}")
    print("  - create RELEASE_SUMMARY.md")


def _finalize(
    version: str,
    channel: str,
    packets: list[tuple[Path, dict[str, Any]]],
) -> None:
    release_dir = RELEASED_DIR / version
    archive_dir = HISTORY_ROOT / version
    release_date = dt.date.today().isoformat()
    target_paths = [(source_path, release_dir / source_path.name) for source_path, _packet in packets]
    for _source_path, target_path in target_paths:
        if target_path.exists():
            raise SystemExit(f"Refusing to overwrite existing packet: {_relative(target_path)}")

    packet_snapshots = _snapshot_files([source_path for source_path, _target_path in target_paths])
    metadata_snapshots = _snapshot_files(list(ARCHIVE_FILES))
    release_dir_existed = release_dir.exists()
    archive_dir_existed = archive_dir.exists()
    moved_targets: list[Path] = []

    try:
        release_dir.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_text(version + "\n", encoding="utf-8")

        moved_packets: list[dict[str, Any]] = []
        for source_path, packet in packets:
            target_path = release_dir / source_path.name

            finalized_packet = dict(packet)
            finalized_packet["version_target"] = version
            if not finalized_packet.get("date_completed"):
                finalized_packet["date_completed"] = release_date
            _write_packet(target_path, finalized_packet)
            source_path.unlink()
            moved_targets.append(target_path)
            moved_packets.append(finalized_packet)

        _run_script("build_change_index.py")
        _run_script("build_changelog.py")
        _run_script(
            "build_release_manifest.py",
            "--version",
            version,
            "--channel",
            channel,
            "--source",
            "released",
        )

        archive_dir.mkdir(parents=True, exist_ok=True)
        for source in ARCHIVE_FILES:
            if source.exists():
                shutil.copy2(source, archive_dir / source.name)
        (archive_dir / "RELEASE_SUMMARY.md").write_text(
            _summary_markdown(version, channel, release_date, moved_packets),
            encoding="utf-8",
        )
    except Exception:
        for target_path in moved_targets:
            if target_path.is_file():
                target_path.unlink()
        _restore_file_snapshots(packet_snapshots)
        _restore_file_snapshots(metadata_snapshots)
        _remove_created_dir(archive_dir, existed_before=archive_dir_existed)
        _remove_created_dir(release_dir, existed_before=release_dir_existed)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize completed unreleased change packets into a versioned release."
    )
    parser.add_argument("--version", required=True, help="Version to finalize.")
    parser.add_argument(
        "--channel",
        choices=sorted(CHANNELS),
        required=True,
        help="Release channel.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned moves, generation, and archive actions without editing files.",
    )
    parser.add_argument(
        "--allow-empty-release",
        action="store_true",
        help="Allow finalizing even when no completed unreleased packets exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    version = validate_version_label(args.version)

    packets = _complete_unreleased_packets()
    if not packets and not args.allow_empty_release:
        raise SystemExit(
            "No completed unreleased change packets found. Use --allow-empty-release "
            "to finalize an empty release."
        )

    _run_script("validate_changes.py")

    if args.dry_run:
        _print_dry_run(version, args.channel, packets)
        return 0

    _finalize(version, args.channel, packets)
    print(f"Finalized {version}: moved {len(packets)} packet(s).")
    print(f"Archive: {_relative(HISTORY_ROOT / version)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
