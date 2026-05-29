from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.shared.constants import FOLDER_POLICY_SCHEMA_VERSION, FOLDER_POLICY_SIDECAR_NAME
from app.shared.utils import _atomic_write_text, _read_json_file


def folder_policy_path(folder: Path) -> Path:
    return folder / FOLDER_POLICY_SIDECAR_NAME


def load_folder_policy_file(folder: Path, *, default_policy: dict[str, Any]) -> dict[str, Any]:
    path = folder_policy_path(folder)
    if not path.exists():
        return default_policy
    raw = _read_json_file(path)
    if not isinstance(raw, dict):
        raise RuntimeError(f"Folder policy has an unexpected shape: {path}")
    return raw


def save_folder_policy_file(folder: Path, policy: dict[str, Any]) -> Path:
    payload = dict(policy or {})
    payload.setdefault("schema_version", FOLDER_POLICY_SCHEMA_VERSION)
    payload.setdefault("folder", str(folder))
    path = folder_policy_path(folder)
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
