from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


BUILD_LABEL_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{3}$")
VERSION_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class ReleaseIdentity:
    release_label: str
    build_id: str
    source_revision: str
    source_dirty: bool
    tool_semver: str


def _repo_root(root: Path | None = None) -> Path:
    return root if root is not None else find_repo_root(Path(__file__))


def next_calendar_build_label(root: Path | None = None, *, today: dt.date | None = None) -> str:
    repo_root = _repo_root(root)
    release_date = today or dt.date.today()
    prefix = release_date.strftime("%Y.%m.%d.")
    max_sequence = 0

    candidates: list[str] = []
    version_file = repo_root / "ops" / "release" / "metadata" / "VERSION"
    if version_file.is_file():
        candidates.append(version_file.read_text(encoding="utf-8").strip())

    manifest_path = repo_root / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
        if isinstance(manifest, dict):
            candidates.extend(str(manifest.get(key, "")).strip() for key in ("version", "build_id"))

    changes_root = repo_root / "ops" / "release" / "changes"
    for packet in changes_root.glob("**/*.json") if changes_root.exists() else []:
        try:
            data = json.loads(packet.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            candidates.append(str(data.get("version_target", "")).strip())

    for value in candidates:
        if value.startswith(prefix) and BUILD_LABEL_RE.fullmatch(value):
            max_sequence = max(max_sequence, int(value.rsplit(".", 1)[1]))

    return f"{prefix}{max_sequence + 1:03d}"


def validate_release_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned:
        raise ValueError("Release label must not be blank.")
    if not VERSION_LABEL_RE.fullmatch(cleaned):
        raise ValueError("Release label may only contain letters, numbers, dots, dashes, and underscores.")
    return cleaned


def read_release_label(root: Path | None = None, *, default: str | None = None) -> str:
    repo_root = _repo_root(root)
    version_file = repo_root / "ops" / "release" / "metadata" / "VERSION"
    if version_file.is_file():
        label = version_file.read_text(encoding="utf-8").strip()
        if label:
            return validate_release_label(label)

    manifest_path = repo_root / "ops" / "release" / "metadata" / "RELEASE_MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
        if isinstance(manifest, dict):
            for key in ("version", "build_id"):
                value = str(manifest.get(key, "")).strip()
                if value:
                    return validate_release_label(value)

    if default:
        return validate_release_label(default)
    return next_calendar_build_label(repo_root)


def _git_text(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""
    return completed.stdout.strip()


def source_revision(root: Path | None = None) -> str:
    return _git_text(_repo_root(root), "rev-parse", "--short=12", "HEAD") or "unknown"


def source_dirty(root: Path | None = None) -> bool:
    repo_root = _repo_root(root)
    return bool(_git_text(repo_root, "status", "--short"))


def semver_for_tools(release_label: str, revision: str, dirty: bool) -> str:
    normalized_label = re.sub(r"[^0-9A-Za-z.]+", ".", release_label).strip(".") or "0"
    normalized_revision = re.sub(r"[^0-9A-Za-z.]+", ".", revision).strip(".") or "unknown"
    suffix = f"{normalized_label}.g{normalized_revision}"
    if dirty:
        suffix += ".dirty"
    return f"0.0.0+{suffix}"


def resolve_release_identity(root: Path | None = None, *, label: str | None = None) -> ReleaseIdentity:
    repo_root = _repo_root(root)
    release_label = validate_release_label(label) if label else read_release_label(repo_root)
    revision = source_revision(repo_root)
    dirty = source_dirty(repo_root)
    build_id = release_label if BUILD_LABEL_RE.fullmatch(release_label) else next_calendar_build_label(repo_root)
    return ReleaseIdentity(
        release_label=release_label,
        build_id=build_id,
        source_revision=revision,
        source_dirty=dirty,
        tool_semver=semver_for_tools(release_label, revision, dirty),
    )
