"""Shared config file location helpers."""

from __future__ import annotations

import os
from pathlib import Path

CONFIG_CANONICAL_NAME = "MediaPipeline_config.psd1"
CONFIG_LEGACY_NAME = "MediaPipeline_config_chatgpt.psd1"
# Stable per-user config home, used by packaged builds where the gitignored
# personal config does not ship inside the install tree.
PER_USER_APP_DIR_NAME = "MediaPipelineRemuxEncodeAIO"


def user_config_dir() -> Path | None:
    """Return %LOCALAPPDATA%/MediaPipelineRemuxEncodeAIO, or None if unset."""
    base = os.environ.get("LOCALAPPDATA")
    if not base or not str(base).strip():
        return None
    return Path(base) / PER_USER_APP_DIR_NAME


def user_config_candidates() -> list[Path]:
    base = user_config_dir()
    if base is None:
        return []
    return [base / CONFIG_CANONICAL_NAME, base / CONFIG_LEGACY_NAME]


__all__ = [
    "CONFIG_CANONICAL_NAME",
    "CONFIG_LEGACY_NAME",
    "PER_USER_APP_DIR_NAME",
    "user_config_candidates",
    "user_config_dir",
]
