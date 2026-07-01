from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mediapipeline.contracts.config import CONFIG_SCHEMA_VERSION
from mediapipeline.core.config.constants import (
    AUDIO_PASSTHROUGH_PROFILE_CODECS,
    AUDIO_PASSTHROUGH_PROFILE_DEFAULT,
)
from mediapipeline.core.config.library_profiles import mirror_legacy_keys_from_library_profiles
from mediapipeline.core.config.contracts import ConfigPreview


ValidateConfigValuesFunc = Callable[[dict[str, Any]], tuple[list[str], list[str]]]
SerializeConfigFunc = Callable[[dict[str, Any]], str]


def build_config_preview(
    base_config: dict[str, Any],
    managed_values: dict[str, Any],
    managed_keys: list[str],
    *,
    validate_values: ValidateConfigValuesFunc,
    serialize_document: SerializeConfigFunc,
) -> ConfigPreview:
    merged = dict(base_config or {})
    merged.setdefault("ConfigSchemaVersion", CONFIG_SCHEMA_VERSION)
    preserved_keys = sorted([key for key in merged.keys() if key not in managed_keys], key=str.casefold)

    optional_blank_keys = {"ConsoleLogLevel", "FileLogLevel", "MinPipelineVersion", "OutputSizeMultiplier", "FallbackCpuQuality"}
    for key, value in managed_values.items():
        if key in optional_blank_keys and (value is None or str(value).strip() == ""):
            merged.pop(key, None)
        else:
            merged[key] = value

    encode_tuning = str(merged.get("EncodeTuningPreset", "balanced_nvenc") or "balanced_nvenc").strip().lower()
    if encode_tuning != "custom_legacy_flags" and "ExtraVideoFlags" in managed_keys:
        merged["ExtraVideoFlags"] = []
    audio_profile = str(merged.get("AudioPassthroughProfile", AUDIO_PASSTHROUGH_PROFILE_DEFAULT) or AUDIO_PASSTHROUGH_PROFILE_DEFAULT).strip().lower()
    audio_profile_managed = "AudioPassthroughProfile" in managed_keys or "AudioPassthroughProfile" in managed_values
    audio_codecs_managed = "CompatibleAudioCodecs" in managed_keys
    if audio_profile in AUDIO_PASSTHROUGH_PROFILE_CODECS and (audio_profile_managed or audio_codecs_managed):
        merged["CompatibleAudioCodecs"] = list(AUDIO_PASSTHROUGH_PROFILE_CODECS[audio_profile])

    merged = mirror_legacy_keys_from_library_profiles(merged, require_profiles=True)

    errors, warnings = validate_values(merged)
    preview_text = serialize_document(merged)
    return ConfigPreview(
        merged_config=merged,
        preview_text=preview_text,
        errors=errors,
        warnings=warnings,
        preserved_keys=preserved_keys,
    )
