from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.config.contracts import ConfigPreview, ConfigSaveResult
from mediapipeline.core.config.document_runner import (
    load_config_data_for_service,
    validate_config_document_for_save_for_service,
)
from mediapipeline.core.config.profiles import (
    config_profile_path,
    config_profiles_dir,
    normalize_profile_name,
)
from mediapipeline.core.config.preview import build_config_preview as build_config_preview_helper
from mediapipeline.core.config.load import (
    load_psd1_mapping,
    order_top_level_config,
    psd1_key,
    psd1_lines,
    psd1_quote,
    serialize_psd1_document,
)
from mediapipeline.core.config.save_runner import (
    config_backup_path,
    list_config_profiles_for_service,
    load_config_profile_for_service,
    normalize_config_path_value as normalize_config_path_value_helper,
    save_config_document_for_service,
    save_config_profile_for_service,
)
from mediapipeline.core.config.settings_store import (
    SettingsStoreError,
    import_psd1_settings_for_service,
    import_psd1_settings_preview_for_service,
    load_settings_authority_for_service,
    save_settings_authority_for_service,
    settings_store_metadata_for_service,
)
from mediapipeline.core.config.validation import (
    config_path_overlap_warning,
    split_list_input as split_config_list_input,
    validate_config_values as validate_config_value_set,
)
from mediapipeline.core.config.path_warnings import (
    config_warning_path_within_root,
    normalized_config_warning_path_key,
)
from mediapipeline.core.kernel.runtime.subprocess_runner import run_capture


class ConfigProfileServiceMixin:
    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]:
        return load_config_data_for_service(
            self,
            config_path,
            powershell_host,
            run_capture_func=run_capture,
        )

    def load_settings_authority(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]:
        return load_settings_authority_for_service(
            self,
            config_path,
            powershell_host,
            psd1_loader=self._load_psd1_mapping_for_settings_authority,
        )

    def split_list_input(self, raw: str) -> list[str]:
        return split_config_list_input(raw)

    def _load_psd1_mapping_for_settings_authority(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]:
        result = load_psd1_mapping(
            config_path,
            powershell_host,
            run_capture_func=run_capture,
            timeout_seconds=30,
            extra_popen_kwargs=self._subprocess_kwargs_hidden(),
            label="config import",
        )
        if result.timed_out:
            self.logger.warning("Config authority import timed out for %s: %s", config_path, result.kill_message)
            raise SettingsStoreError(result.error or "Config import timed out.")
        if not result.ok:
            self.logger.warning("Config authority import failed for %s: %s", config_path, result.error)
            raise SettingsStoreError(result.error or f"Config PSD1 import failed: {config_path}")
        return result.data

    def build_config_preview(self, base_config: dict[str, Any], managed_values: dict[str, Any], managed_keys: list[str]) -> ConfigPreview:
        return build_config_preview_helper(
            base_config,
            managed_values,
            managed_keys,
            validate_values=self.validate_config_values,
            serialize_document=self.serialize_psd1_document,
        )

    def validate_config_values(self, values: dict[str, Any]) -> tuple[list[str], list[str]]:
        return validate_config_value_set(
            values,
            normalized_path_key=normalized_config_warning_path_key,
            path_within_root=config_warning_path_within_root,
        )

    def _config_path_overlap_warning(self, left_key: str, right_key: str, path_values: dict[str, str]) -> str | None:
        return config_path_overlap_warning(
            left_key,
            right_key,
            path_values,
            normalized_path_key=self._normalized_path_key,
            path_within_root=self._path_within_root,
        )

    def validate_config_document_for_save(
        self,
        document_text: str,
        *,
        config_values: dict[str, Any] | None = None,
        powershell_host: str | None = None,
    ) -> tuple[list[str], list[str]]:
        return validate_config_document_for_save_for_service(
            self,
            document_text,
            config_values=config_values,
            powershell_host=powershell_host,
            run_capture_func=run_capture,
        )

    def _config_backup_path(self, output_path: Path) -> Path:
        return config_backup_path(output_path)

    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict[str, Any] | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult:
        return save_config_document_for_service(
            self,
            output_path,
            document_text,
            create_backup,
            config_values=config_values,
            powershell_host=powershell_host,
        )

    def save_settings_authority(self, resolved: ResolvedPaths, candidate_settings: dict[str, Any]) -> ConfigSaveResult:
        return save_settings_authority_for_service(
            self,
            resolved,
            candidate_settings,
            psd1_loader=self._load_psd1_mapping_for_settings_authority,
        )

    def import_psd1_settings_preview(self, resolved: ResolvedPaths) -> dict[str, Any]:
        return import_psd1_settings_preview_for_service(
            self,
            resolved,
            psd1_loader=self._load_psd1_mapping_for_settings_authority,
        )

    def import_psd1_settings(self, resolved: ResolvedPaths) -> dict[str, Any]:
        return import_psd1_settings_for_service(
            self,
            resolved,
            psd1_loader=self._load_psd1_mapping_for_settings_authority,
        )

    def settings_store_metadata(self, config_path: Path) -> dict[str, Any]:
        return settings_store_metadata_for_service(self, config_path)

    def normalize_profile_name(self, raw_name: str) -> str:
        return normalize_profile_name(raw_name)

    def config_profiles_dir(self, config_path: Path) -> Path:
        return config_profiles_dir(config_path)

    def config_profile_path(self, config_path: Path, profile_name: str) -> tuple[str, Path]:
        return config_profile_path(config_path, profile_name, path_within_root=self._path_within_root)

    def list_config_profiles(self, config_path: Path) -> list[str]:
        return list_config_profiles_for_service(self, config_path)

    def normalize_config_path_value(self, path_text: str) -> str:
        return normalize_config_path_value_helper(path_text)

    def save_config_profile(self, resolved: ResolvedPaths, profile_name: str) -> tuple[str, Path]:
        return save_config_profile_for_service(self, resolved, profile_name)

    def load_config_profile(self, resolved: ResolvedPaths, profile_name: str) -> tuple[str, Path, ConfigSaveResult]:
        return load_config_profile_for_service(self, resolved, profile_name)

    def serialize_psd1_document(self, data: dict[str, Any]) -> str:
        return serialize_psd1_document(data)

    def _order_top_level_config(self, data: dict[str, Any]) -> dict[str, Any]:
        return order_top_level_config(data)

    def _psd1_lines(self, value: Any, indent: int, top_level: bool = False) -> list[str]:
        return psd1_lines(value, indent=indent, top_level=top_level)

    def _psd1_key(self, key: str) -> str:
        return psd1_key(key)

    def _psd1_quote(self, value: str) -> str:
        return psd1_quote(value)
