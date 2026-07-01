from __future__ import annotations

from typing import Any

from mediapipeline.core.config.settings_risk_policy import (
    build_settings_patch_risk_summary,
    source_mutation_setting,
    truthy_setting,
)


class SettingsRiskFacadeMixin:
    """Risk classification helpers for settings patch preview/save commands."""

    def _settings_patch_risk_summary(
        self,
        base_config: dict[str, Any],
        merged: dict[str, Any],
        changed_keys: list[str],
        removed_keys: list[str],
    ) -> dict[str, Any]:
        return build_settings_patch_risk_summary(base_config, merged, changed_keys, removed_keys)

    @staticmethod
    def _truthy_setting(value: Any) -> bool:
        return truthy_setting(value)

    @staticmethod
    def _source_mutation_setting(key: str, value: Any) -> bool:
        return source_mutation_setting(key, value)


__all__ = [
    "SettingsRiskFacadeMixin",
]
