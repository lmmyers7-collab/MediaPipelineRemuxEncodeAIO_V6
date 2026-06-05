"""Startup recovery for the live operator config (config hardening #1).

The live config (``MediaPipeline_config.psd1``) is a gitignored operator file.
Historically a missing canonical file silently fell back to the legacy
``_chatgpt`` name or to defaults, which surfaced only as a cryptic
``settings loaded=no`` at launch time. This module makes startup self-heal:

- canonical present              -> ``present``
- canonical missing, legacy here -> copy legacy -> canonical (``migrated``)
- local config present/migrated  -> seed missing per-user packaged fallback
- local config missing, per-user -> use/migrate per-user config
- both missing, a backup exists  -> ``backup_available`` (names newest; no
                                    silent auto-restore)
- nothing                        -> ``absent``

Filesystem only: no PowerShell, no psd1 parsing here, so it stays cheap and
unit-testable. Parsing/validation remains the caller's existing path.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from mediapipeline.core.config.identity import (
    build_config_identity,
    config_identity_block_reasons,
    last_good_snapshot_path,
    user_last_good_snapshot_path,
)
from mediapipeline.core.kernel.config_locations import (
    CONFIG_CANONICAL_NAME as CANONICAL_CONFIG_NAME,
    CONFIG_LEGACY_NAME as LEGACY_CONFIG_NAME,
    user_config_candidates,
    user_config_dir,
)

BACKUP_DIR_NAME = "ConfigBackups"
CONFIG_SNAPSHOT_DIR_NAME = "ConfigSnapshots"
LoadConfigData = Callable[[Path, str | None], Mapping[str, Any]]


@dataclass(frozen=True)
class ConfigRecoveryResult:
    action: str
    ok: bool
    canonical_path: Path
    source_path: Path | None
    message: str


def _canonical_candidates(app_root: Path, workspace_root: Path) -> list[Path]:
    # Same order/locations as mediapipeline.core.paths.defaults.default_config_path_for_roots.
    return [
        workspace_root / "ops" / "pipeline" / "config" / CANONICAL_CONFIG_NAME,
        app_root / "config" / CANONICAL_CONFIG_NAME,
    ]


def _legacy_candidates(app_root: Path, workspace_root: Path) -> list[Path]:
    return [
        workspace_root / "ops" / "pipeline" / "config" / LEGACY_CONFIG_NAME,
        app_root / "config" / LEGACY_CONFIG_NAME,
    ]


def _first_existing(paths: list[Path]) -> Path | None:
    for candidate in paths:
        if candidate.is_file():
            return candidate
    return None


def _newest_backup(config_dir: Path) -> Path | None:
    backup_dir = config_dir / BACKUP_DIR_NAME
    if not backup_dir.is_dir():
        return None
    backups = [path for path in backup_dir.glob("*.psd1") if path.is_file()]
    if not backups:
        return None
    return max(backups, key=lambda path: path.stat().st_mtime)


def _last_good_snapshot_candidates(canonical_target: Path, local_base: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    user_snapshot = user_last_good_snapshot_path()
    if user_snapshot is not None:
        candidates.append(user_snapshot)
    if local_base is not None:
        candidates.append(last_good_snapshot_path(local_base))
    candidates.append(canonical_target.parent / CONFIG_SNAPSHOT_DIR_NAME / "last_good.psd1")
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate).casefold()
        if text in seen:
            continue
        seen.add(text)
        unique.append(candidate)
    return unique


def _newest_last_good_snapshot(canonical_target: Path, local_base: Path | None = None) -> Path | None:
    snapshots = [path for path in _last_good_snapshot_candidates(canonical_target, local_base) if path.is_file()]
    if not snapshots:
        return None
    return max(snapshots, key=lambda path: path.stat().st_mtime)


def _user_canonical_target() -> Path | None:
    base = user_config_dir()
    return None if base is None else base / CANONICAL_CONFIG_NAME


def _use_or_seed_user_config(source: Path) -> tuple[Path, str]:
    user_existing = _first_existing(user_config_candidates())
    if user_existing is not None:
        if user_existing.name == CANONICAL_CONFIG_NAME:
            return user_existing, f"Using per-user config: {user_existing}"
        user_target = _user_canonical_target()
        if user_target is None:
            return source, f"LOCALAPPDATA unavailable; using local config: {source}"
        user_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(user_existing, user_target)
        return (
            user_target,
            f"Completed per-user legacy->canonical migration: copied {user_existing} to {user_target}",
        )
    seeded = seed_user_config(source)
    if seeded is None:
        return source, f"LOCALAPPDATA unavailable; using local config: {source}"
    return seeded, f"Seeded durable per-user config from {source}: {seeded}"


def ensure_canonical_config(app_root: Path, workspace_root: Path) -> ConfigRecoveryResult:
    """Ensure the canonical live config exists, self-healing where safe.

    Only ever copies (never deletes/overwrites an existing canonical file) and
    never restores a backup silently. Returns a structured result the caller
    surfaces in startup progress.
    """
    canonical_candidates = _canonical_candidates(app_root, workspace_root)
    canonical_target = canonical_candidates[0]

    user_existing = _first_existing(user_config_candidates())
    if user_existing is not None:
        selected, message = _use_or_seed_user_config(user_existing)
        return ConfigRecoveryResult(
            action="user_present" if user_existing.name == CANONICAL_CONFIG_NAME else "user_migrated",
            ok=True,
            canonical_path=selected,
            source_path=user_existing if user_existing != selected else None,
            message=message,
        )

    existing_canonical = _first_existing(canonical_candidates)
    if existing_canonical is not None:
        selected, message = _use_or_seed_user_config(existing_canonical)
        return ConfigRecoveryResult(
            action="seeded_user" if selected != existing_canonical else "present",
            ok=True,
            canonical_path=selected,
            source_path=existing_canonical if selected != existing_canonical else None,
            message=message,
        )

    legacy = _first_existing(_legacy_candidates(app_root, workspace_root))
    if legacy is not None:
        canonical_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, canonical_target)
        selected, message = _use_or_seed_user_config(canonical_target)
        return ConfigRecoveryResult(
            action="migrated_seeded_user" if selected != canonical_target else "migrated",
            ok=True,
            canonical_path=selected,
            source_path=legacy,
            message=(
                f"Completed legacy->canonical config migration: copied {legacy} "
                f"to {canonical_target}; {message}"
            ),
        )

    last_good = _newest_last_good_snapshot(_user_canonical_target() or canonical_target)
    if last_good is not None:
        restore_target = _user_canonical_target() or canonical_target
        restore_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(last_good, restore_target)
        return ConfigRecoveryResult(
            action="restored_last_good",
            ok=True,
            canonical_path=restore_target,
            source_path=last_good,
            message=f"Restored live config from last-known-good snapshot {last_good} to {restore_target}",
        )

    newest_backup = _newest_backup(canonical_target.parent)
    if newest_backup is not None:
        restore_target = _user_canonical_target() or canonical_target
        return ConfigRecoveryResult(
            action="backup_available",
            ok=False,
            canonical_path=restore_target,
            source_path=newest_backup,
            message=(
                "No live config found. Restore the most recent backup to "
                f"{restore_target} to recover settings: {newest_backup}"
            ),
        )

    missing_target = _user_canonical_target() or canonical_target
    return ConfigRecoveryResult(
        action="absent",
        ok=False,
        canonical_path=missing_target,
        source_path=None,
        message=(
            "No live config, legacy config, or backup found near "
            f"{missing_target.parent}. Settings, launch, and save operations "
            "will remain blocked until an operator config is restored."
        ),
    )


def restore_verified_last_good_config(
    target: Path,
    *,
    app_root: Path,
    workspace_root: Path,
    powershell_host: str | None,
    load_config_data: LoadConfigData,
    local_base: Path | None = None,
) -> ConfigRecoveryResult:
    """Restore a last-good snapshot only after parsing and identity checks."""
    snapshot = _newest_last_good_snapshot(target, local_base)
    if snapshot is None:
        return ConfigRecoveryResult(
            action="last_good_unavailable",
            ok=False,
            canonical_path=target,
            source_path=None,
            message="Active config is blocked and no last-known-good config snapshot is available.",
        )
    try:
        snapshot_data = dict(load_config_data(snapshot, powershell_host) or {})
    except Exception as exc:
        return ConfigRecoveryResult(
            action="last_good_unreadable",
            ok=False,
            canonical_path=target,
            source_path=snapshot,
            message=f"Last-known-good config snapshot could not be loaded: {snapshot}; {exc}",
        )
    snapshot_identity = build_config_identity(
        snapshot,
        snapshot_data,
        app_root=app_root,
        workspace_root=workspace_root,
    )
    block_reasons = config_identity_block_reasons(snapshot_identity)
    if block_reasons:
        return ConfigRecoveryResult(
            action="last_good_rejected",
            ok=False,
            canonical_path=target,
            source_path=snapshot,
            message=(
                "Last-known-good config snapshot was rejected by identity checks: "
                + "; ".join(block_reasons)
            ),
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot, target)
    return ConfigRecoveryResult(
        action="restored_verified_last_good",
        ok=True,
        canonical_path=target,
        source_path=snapshot,
        message=f"Restored blocked live config from verified last-known-good snapshot {snapshot}",
    )


def seed_user_config(source: Path) -> Path | None:
    """Copy ``source`` into the per-user canonical config location.

    Returns the destination path, or None if no per-user dir is available
    (LOCALAPPDATA unset). Non-destructive create/overwrite of the per-user
    copy; never touches ``source``.
    """
    base = user_config_dir()
    if base is None:
        return None
    base.mkdir(parents=True, exist_ok=True)
    target = base / CANONICAL_CONFIG_NAME
    shutil.copy2(source, target)
    return target
