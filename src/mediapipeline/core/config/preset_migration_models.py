"""Internal helpers for preset migration DTO conversion."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mediapipeline.contracts.config import Config, default_config
from mediapipeline.contracts.verification import OutputSizeCheckAction, output_size_check_action_from_settings

def _size_on_exceeded(mode: str) -> OutputSizeCheckAction:
    return output_size_check_action_from_settings(mode)

def _legacy_config_and_extra(value: Config | Mapping[str, Any] | None) -> tuple[Config, dict[str, Any]]:
    if value is None:
        return default_config(), {}
    if isinstance(value, Config):
        return value, dict(value.model_extra or {})
    raw = {str(key): item for key, item in value.items()}
    config = Config.model_validate(raw)
    extra = {key: item for key, item in raw.items() if key not in Config.model_fields}
    return config, extra

def _legacy_number(value: float | int | None) -> float | int | None:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value
