"""Config identity, health, and last-known-good snapshot helpers."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.kernel.config_locations import user_config_dir

CONFIG_IDENTITY_SCHEMA_VERSION = "desktop_config_identity.v1"
CONFIG_SNAPSHOT_DIR_NAME = "ConfigSnapshots"
LAST_GOOD_CONFIG_NAME = "last_good.psd1"
MIN_OPERATOR_CONFIG_KEY_COUNT = 80
TEMPLATE_CONFIG_NAME = "MediaPipeline_config_template.psd1"
KEY_SOURCE_MOVIES = "SourceMovies"
KEY_SOURCE_TV = "SourceTV"
KEY_OUTSOURCE = "Outsource"
KEY_LOCAL_BASE = "LocalBase"
TEMPLATE_PATH_VALUES = {
    KEY_SOURCE_MOVIES: r"C:\MediaPipeline\Incoming\Movies",
    KEY_SOURCE_TV: r"C:\MediaPipeline\Incoming\TV",
    KEY_OUTSOURCE: r"C:\MediaPipeline\Processed",
    KEY_LOCAL_BASE: r"C:\MediaPipeline\Scratch",
}
REQUIRED_OPERATOR_ROOT_KEYS = (KEY_SOURCE_MOVIES, KEY_SOURCE_TV, KEY_OUTSOURCE, KEY_LOCAL_BASE)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def path_modified_utc(path: Path) -> str:
    try:
        modified = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(modified, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def config_template_candidates(app_root: Path, workspace_root: Path) -> list[Path]:
    return [
        workspace_root / "Pipeline" / TEMPLATE_CONFIG_NAME,
        app_root / "Pipeline" / TEMPLATE_CONFIG_NAME,
        workspace_root / TEMPLATE_CONFIG_NAME,
        app_root / TEMPLATE_CONFIG_NAME,
    ]


def _template_hashes(app_root: Path, workspace_root: Path) -> set[str]:
    hashes: set[str] = set()
    for candidate in config_template_candidates(app_root, workspace_root):
        if not candidate.is_file():
            continue
        try:
            hashes.add(file_sha256(candidate))
        except OSError:
            continue
    return hashes


def _same_path_value(left: Any, right: str) -> bool:
    return str(left or "").strip().rstrip("\\/").casefold() == right.rstrip("\\/").casefold()


def config_looks_like_template(config_data: Mapping[str, Any]) -> bool:
    if not config_data:
        return False
    return all(_same_path_value(config_data.get(key), value) for key, value in TEMPLATE_PATH_VALUES.items())


def build_config_identity(
    config_path: Path,
    config_data: Mapping[str, Any] | None,
    *,
    app_root: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    data = dict(config_data or {})
    exists = config_path.is_file()
    sha256 = ""
    read_error = ""
    if exists:
        try:
            sha256 = file_sha256(config_path)
        except OSError as exc:
            read_error = str(exc)

    key_count = len(data)
    missing_required = [key for key in REQUIRED_OPERATOR_ROOT_KEYS if not str(data.get(key) or "").strip()]
    template_hash_match = bool(sha256 and sha256 in _template_hashes(app_root, workspace_root))
    template_path_match = config_looks_like_template(data)
    suspicious_low_key_count = bool(data) and key_count < MIN_OPERATOR_CONFIG_KEY_COUNT
    reasons: list[str] = []
    if not exists:
        reasons.append(f"Config file is missing: {config_path}")
    if read_error:
        reasons.append(f"Config file fingerprint could not be read: {read_error}")
    if exists and not data:
        reasons.append("Config PSD1 did not load into backend settings data.")
    if suspicious_low_key_count:
        reasons.append(
            f"Config key count {key_count} is below the operator threshold {MIN_OPERATOR_CONFIG_KEY_COUNT}."
        )
    if template_hash_match or template_path_match:
        reasons.append("Active config matches the deployment template/default paths.")
    if missing_required:
        reasons.append(f"Required operator root key(s) missing: {', '.join(missing_required)}.")

    blocks_operations = bool(reasons)
    status_state = "blocked" if blocks_operations else "ready"
    operator_status = "Config unavailable" if blocks_operations else "Config ready"
    if data and blocks_operations:
        operator_status = "Config requires recovery"
    return {
        "schema_version": CONFIG_IDENTITY_SCHEMA_VERSION,
        "config_path": str(config_path),
        "exists": exists,
        "modified_utc": path_modified_utc(config_path),
        "sha256": sha256,
        "key_count": key_count,
        "min_operator_key_count": MIN_OPERATOR_CONFIG_KEY_COUNT,
        "required_root_keys": list(REQUIRED_OPERATOR_ROOT_KEYS),
        "missing_required_root_keys": missing_required,
        "template_hash_match": template_hash_match,
        "template_path_match": template_path_match,
        "suspicious_low_key_count": suspicious_low_key_count,
        "blocks_operations": blocks_operations,
        "status_state": status_state,
        "operator_status": operator_status,
        "reasons": reasons,
        "last_good_snapshot_path": "",
        "snapshot_error": "",
    }


def config_identity_block_reasons(identity: Mapping[str, Any] | None) -> list[str]:
    if not identity or not bool(identity.get("blocks_operations")):
        return []
    reasons = identity.get("reasons")
    if isinstance(reasons, list):
        return [str(item) for item in reasons if str(item).strip()]
    return [str(identity.get("operator_status") or "Config is not ready.")]


def config_operation_block_message(identity: Mapping[str, Any] | None, operation: str) -> str:
    reasons = config_identity_block_reasons(identity)
    detail = "; ".join(reasons) if reasons else "Config is not ready."
    return f"{operation} blocked because the active config is not a verified operator config: {detail}"


def config_operation_block_data(identity: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "config_identity": dict(identity or {}),
        "config_block_reasons": config_identity_block_reasons(identity),
        "writes_config": False,
        "can_execute": False,
    }


def last_good_snapshot_path(local_base: Path) -> Path:
    return local_base / "State" / CONFIG_SNAPSHOT_DIR_NAME / LAST_GOOD_CONFIG_NAME


def user_last_good_snapshot_path() -> Path | None:
    base = user_config_dir()
    if base is None:
        return None
    return base / CONFIG_SNAPSHOT_DIR_NAME / LAST_GOOD_CONFIG_NAME


def _copy_config_snapshot_if_changed(config_path: Path, target: Path, source_hash: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and source_hash:
        try:
            if file_sha256(target) == source_hash:
                return target
        except OSError:
            pass
    shutil.copy2(config_path, target)
    return target


def write_last_good_config_snapshot(
    config_path: Path,
    local_base: Path | None,
    identity: Mapping[str, Any],
) -> Path | None:
    if config_identity_block_reasons(identity):
        return None
    if not config_path.is_file():
        return None
    source_hash = str(identity.get("sha256") or "")
    targets: list[Path] = []
    if local_base is not None:
        targets.append(last_good_snapshot_path(local_base))
    user_snapshot = user_last_good_snapshot_path()
    if user_snapshot is not None and user_snapshot not in targets:
        targets.append(user_snapshot)
    written: list[Path] = []
    for target in targets:
        written.append(_copy_config_snapshot_if_changed(config_path, target, source_hash))
    return written[0] if written else None


__all__ = [
    "CONFIG_IDENTITY_SCHEMA_VERSION",
    "CONFIG_SNAPSHOT_DIR_NAME",
    "LAST_GOOD_CONFIG_NAME",
    "MIN_OPERATOR_CONFIG_KEY_COUNT",
    "REQUIRED_OPERATOR_ROOT_KEYS",
    "TEMPLATE_CONFIG_NAME",
    "build_config_identity",
    "config_identity_block_reasons",
    "config_looks_like_template",
    "config_operation_block_data",
    "config_operation_block_message",
    "file_sha256",
    "last_good_snapshot_path",
    "path_modified_utc",
    "user_last_good_snapshot_path",
    "write_last_good_config_snapshot",
]
