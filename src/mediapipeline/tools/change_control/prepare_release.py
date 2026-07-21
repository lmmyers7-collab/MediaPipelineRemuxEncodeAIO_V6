from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any

from .build_release_manifest import validate_version_label


REPO_ROOT = find_repo_root(Path(__file__))
UNRELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "unreleased"
VERSION_FILE = REPO_ROOT / "ops" / "release" / "metadata" / "VERSION"
MANIFEST_PATH = REPO_ROOT / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"

CHANNELS = {"dev", "alpha", "beta", "rc", "stable", "hotfix", "local"}
DEV_PLACEHOLDERS = {"", "dev", "development", "unreleased"}
GENERATED_FILES = [
    "docs/change_control/CHANGE_INDEX.md",
    "docs/change_control/CHANGELOG.md",
    "ops/release/metadata/RELEASE_MANIFEST.json",
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


def _is_dev_placeholder(value: Any) -> bool:
    text = "" if value is None else str(value).strip()
    lower = text.lower()
    return lower in DEV_PLACEHOLDERS or lower.endswith("-dev")


def _update_version_file(version: str, dry_run: bool) -> None:
    if dry_run:
        return
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(version.strip() + "\n", encoding="utf-8")


def _update_packet_targets(version: str, dry_run: bool) -> list[str]:
    updated: list[str] = []
    for path in _packet_paths():
        packet = _load_packet(path)
        if packet.get("status") != "complete":
            continue
        if not _is_dev_placeholder(packet.get("version_target")):
            continue
        if str(packet.get("version_target", "")).strip() == version:
            continue

        updated.append(str(packet.get("id", path.stem)))
        if not dry_run:
            packet["version_target"] = version
            path.write_text(
                json.dumps(packet, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
    return updated


def _run_script(name: str, *args: str) -> None:
    module = f"mediapipeline.tools.change_control.{Path(name).stem}"
    command = [sys.executable, "-m", module, *args]
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def _included_changes() -> list[str]:
    if not MANIFEST_PATH.exists():
        return []
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    changes = manifest.get("included_changes")
    if not isinstance(changes, list):
        return []
    return [str(change) for change in changes]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare generated release documentation and manifest."
    )
    parser.add_argument("--version", required=True, help="Version to prepare.")
    parser.add_argument(
        "--channel",
        choices=sorted(CHANNELS),
        required=True,
        help="Release channel.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run checks and generators without updating version files or packets.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    version = validate_version_label(args.version)

    _update_version_file(version, args.dry_run)
    target_updates = _update_packet_targets(version, args.dry_run)

    _run_script("validate_changes.py")
    _run_script("build_change_index.py")
    _run_script("build_changelog.py")
    manifest_args = [
        "--version",
        version,
        "--channel",
        args.channel,
        "--source",
        "auto",
    ]
    if args.dry_run:
        manifest_args.append("--include-dev-placeholders")
    _run_script("build_release_manifest.py", *manifest_args)

    mode = "dry run" if args.dry_run else "release preparation"
    print("")
    print(f"Prepare release summary ({mode}):")
    print(f"- Version: {version}")
    print(f"- Channel: {args.channel}")
    print(f"- Included change IDs: {', '.join(_included_changes()) or '-'}")
    print(f"- Version-target updates: {', '.join(target_updates) or '-'}")
    print(f"- Generated files: {', '.join(GENERATED_FILES)}")
    if args.dry_run:
        print("- Dry run: ops/release/metadata/VERSION and change packets were not modified")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
