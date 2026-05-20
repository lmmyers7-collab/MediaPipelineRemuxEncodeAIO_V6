from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ConfigPreview, ConfigSaveResult, ResolvedPaths
from .service_config_document_runner import (
    load_config_data_for_service,
    validate_config_document_for_save_for_service,
)
from .service_config_profiles import (
    config_profile_path,
    config_profiles_dir,
    normalize_profile_name,
)
from .service_config_preview import build_config_preview as build_config_preview_helper
from .service_config_psd1 import order_top_level_config, psd1_key, psd1_lines, psd1_quote, serialize_psd1_document
from .service_config_save_runner import (
    config_backup_path,
    list_config_profiles_for_service,
    load_config_profile_for_service,
    normalize_config_path_value as normalize_config_path_value_helper,
    save_config_document_for_service,
    save_config_profile_for_service,
)
from .service_config_validation import (
    config_path_overlap_warning,
    split_list_input as split_config_list_input,
    validate_config_values as validate_config_value_set,
)
from .subprocess_runner import run_capture


class ConfigProfileServiceMixin:
    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]:
        return load_config_data_for_service(
            self,
            config_path,
            powershell_host,
            run_capture_func=run_capture,
        )

    def split_list_input(self, raw: str) -> list[str]:
        return split_config_list_input(raw)

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
            normalized_path_key=self._normalized_path_key,
            path_within_root=self._path_within_root,
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
