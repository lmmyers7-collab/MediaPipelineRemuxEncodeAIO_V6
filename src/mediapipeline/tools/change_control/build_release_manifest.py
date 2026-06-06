from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from mediapipeline.tools.release_identity import BUILD_LABEL_RE, resolve_release_identity, validate_release_label
from typing import Any


REPO_ROOT = find_repo_root(Path(__file__))
UNRELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "unreleased"
RELEASED_DIR = REPO_ROOT / "ops" / "release" / "changes" / "released"
VERSION_FILE = REPO_ROOT / "ops" / "release" / "metadata" / "VERSION"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"
LEGACY_CHANGE_PATH_PREFIX = "ops/ops/release/metadata/changes/"
LEGACY_CHANGE_SUMMARY_PREFIX = "docs/generated/summaries/ops/ops/release/metadata/changes/"
REMOVED_QUICK_START_STEM = "tl" + "dr"
REMOVED_ACTIVE_ARTIFACTS = {
    f"docs/{REMOVED_QUICK_START_STEM}.md",
    f"docs/generated/summaries/docs/{REMOVED_QUICK_START_STEM}.md.md",
}

CHANNELS = {"dev", "alpha", "beta", "rc", "stable", "hotfix", "local"}
SOURCES = {"unreleased", "released", "auto"}
BUILD_ID_RE = re.compile(r"^(?P<date>\d{4}\.\d{2}\.\d{2})\.(?P<seq>\d{3})$")


def _packet_paths(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.glob(pattern) if path.is_file())


def _load_packet(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_version() -> str:
    if not VERSION_FILE.exists():
        raise SystemExit("ops/release/metadata/VERSION is missing")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("ops/release/metadata/VERSION is empty")
    return version


def validate_version_label(version: str) -> str:
    try:
        return validate_release_label(version)
    except ValueError as exc:
        raise SystemExit(
            f"Invalid release version: {exc} Path separators and spaces are not allowed."
        ) from exc


def _is_dev_placeholder(value: Any) -> bool:
    text = "" if value is None else str(value).strip()
    lower = text.lower()
    return lower in {"", "dev", "development", "unreleased"} or lower.endswith("-dev")


def _matches_version(packet: dict[str, Any], version: str) -> bool:
    return str(packet.get("version_target", "")).strip() == version


def _complete_unreleased_packets(
    version: str,
    include_dev_placeholders: bool = False,
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for path in _packet_paths(UNRELEASED_DIR, "*.json"):
        packet = _load_packet(path)
        if packet.get("status") != "complete":
            continue
        if _matches_version(packet, version) or (
            include_dev_placeholders and _is_dev_placeholder(packet.get("version_target"))
        ):
            packets.append(packet)
    return sorted(packets, key=lambda item: str(item.get("id", "")))


def _released_packets(version: str) -> list[dict[str, Any]]:
    release_dir = RELEASED_DIR / version
    packets: list[dict[str, Any]] = []
    for path in _packet_paths(release_dir, "*.json"):
        packet = _load_packet(path)
        if packet.get("status") == "complete":
            packets.append(packet)
    return sorted(packets, key=lambda item: str(item.get("id", "")))


def _select_packets(
    version: str,
    source: str,
    include_dev_placeholders: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    if source == "unreleased":
        return source, _complete_unreleased_packets(version, include_dev_placeholders)
    if source == "released":
        return source, _released_packets(version)

    unreleased = _complete_unreleased_packets(version, include_dev_placeholders)
    if unreleased:
        return "unreleased", unreleased
    return "released", _released_packets(version)


def _dedupe_sorted(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value).strip()})


def _normalize_display_path(value: Any) -> str:
    text = str(value).replace("\\", "/")
    if text.startswith(LEGACY_CHANGE_SUMMARY_PREFIX):
        suffix = text[len(LEGACY_CHANGE_SUMMARY_PREFIX) :]
        return f"docs/generated/summaries/ops/release/changes/{suffix}"
    if text.startswith(LEGACY_CHANGE_PATH_PREFIX):
        suffix = text[len(LEGACY_CHANGE_PATH_PREFIX) :]
        return f"ops/release/changes/{suffix}"
    return text


def _is_removed_active_artifact(value: str) -> bool:
    return value.replace("\\", "/").lower() in REMOVED_ACTIVE_ARTIFACTS


def _list_values(
    packets: list[dict[str, Any]],
    field: str,
    *,
    normalize_paths: bool = False,
) -> list[str]:
    values: list[Any] = []
    for packet in packets:
        field_value = packet.get(field)
        if isinstance(field_value, list):
            values.extend(field_value)
    if normalize_paths:
        values = [_normalize_display_path(value) for value in values]
    if field == "files_touched":
        values = [value for value in values if not _is_removed_active_artifact(str(value))]
    return _dedupe_sorted(values)


def _load_existing_manifest(output_path: Path) -> dict[str, Any] | None:
    if not output_path.exists():
        return None
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _build_id(version: str, release_date: str, channel: str, output_path: Path) -> str:
    if BUILD_LABEL_RE.fullmatch(version):
        return version

    date_part = release_date.replace("-", ".")
    existing = _load_existing_manifest(output_path)
    if not existing:
        return f"{date_part}.001"

    existing_id = str(existing.get("build_id", ""))
    match = BUILD_ID_RE.match(existing_id)
    if not match or match.group("date") != date_part:
        return f"{date_part}.001"

    if (
        existing.get("version") == version
        and existing.get("release_date") == release_date
        and existing.get("release_channel") == channel
    ):
        return existing_id

    return f"{date_part}.{int(match.group('seq')) + 1:03d}"


def build_manifest(
    version: str | None = None,
    channel: str = "dev",
    source: str = "auto",
    output_path: Path = DEFAULT_MANIFEST_PATH,
    include_dev_placeholders: bool = False,
) -> dict[str, Any]:
    if channel not in CHANNELS:
        raise SystemExit(f"Invalid release channel: {channel}")
    if source not in SOURCES:
        raise SystemExit(f"Invalid manifest source: {source}")

    resolved_version = validate_version_label(version or _read_version())
    identity = resolve_release_identity(REPO_ROOT, label=resolved_version)
    release_date = dt.date.today().isoformat()
    resolved_source, packets = _select_packets(
        resolved_version,
        source,
        include_dev_placeholders,
    )
    included_changes = [str(packet.get("id")) for packet in packets]

    known_risks: list[str] = []
    rollback_notes: list[str] = []
    for packet in packets:
        change_id = str(packet.get("id", ""))
        risk = str(packet.get("risk_level", ""))
        title = str(packet.get("title", ""))
        summary = str(packet.get("summary", ""))
        rollback = str(packet.get("rollback_plan", "")).strip()
        if risk in {"high", "critical"}:
            known_risks.append(f"{change_id}: {title} ({risk}) - {summary}")
        if rollback:
            rollback_notes.append(f"{change_id}: {rollback}")

    return {
        "app_name": "MediaPipeline",
        "version": identity.release_label,
        "version_scheme": "calendar-build",
        "release_channel": channel,
        "release_date": release_date,
        "build_id": _build_id(identity.release_label, release_date, channel, output_path),
        "source_revision": identity.source_revision,
        "source_dirty": identity.source_dirty,
        "tool_semver": identity.tool_semver,
        "change_source": resolved_source,
        "included_changes": included_changes,
        "affected_areas": _list_values(packets, "affected_areas"),
        "risk_levels": _dedupe_sorted([packet.get("risk_level", "") for packet in packets]),
        "files_touched": _list_values(packets, "files_touched", normalize_paths=True),
        "known_risks": sorted(known_risks),
        "rollback_notes": sorted(rollback_notes),
        "config_schema_version": 1,
        "database_schema_version": 1,
        "media_profile_schema_version": 1,
    }


def _output_path(value: str | None) -> Path:
    if not value:
        return DEFAULT_MANIFEST_PATH
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a release manifest from complete unreleased changes or "
            "finalized released changes."
        )
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Manifest version. Defaults to ops/release/metadata/VERSION.",
    )
    parser.add_argument(
        "--channel",
        choices=sorted(CHANNELS),
        default="dev",
        help="Release channel to write into the manifest. Defaults to dev.",
    )
    parser.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="auto",
        help="Use unreleased, released, or automatic packet selection.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path. Defaults to ops/release/metadata/RELEASE_MANIFEST.json.",
    )
    parser.add_argument(
        "--include-dev-placeholders",
        action="store_true",
        help=(
            "Include complete unreleased packets with dev placeholder version "
            "targets when building a manifest for a concrete version."
        ),
    )
    return parser.parse_args()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    args = _parse_args()
    output_path = _output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        version=args.version,
        channel=args.channel,
        source=args.source,
        output_path=output_path,
        include_dev_placeholders=args.include_dev_placeholders,
    )
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {_display_path(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
