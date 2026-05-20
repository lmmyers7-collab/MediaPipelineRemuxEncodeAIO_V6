from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from mediapipeline_desktop_app.models import ConfigSaveResult, ResolvedPaths
from mediapipeline_desktop_app.service_config_profiles import (
    config_profile_path,
    config_profiles_dir,
    normalize_profile_name,
)
from mediapipeline_desktop_app.service_config_save_runner import (
    list_config_profiles_for_service,
    load_config_profile_for_service,
    normalize_config_path_value,
    save_config_document_for_service,
    save_config_profile_for_service,
)


class _DummyConfigSaveService:
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_config_save_runner")
        self.logger.addHandler(logging.NullHandler())
        self.validation_errors: list[str] = []
        self.validation_calls: list[tuple[str, dict | None, str | None]] = []
        self.saved_documents: list[tuple[Path, str, bool, dict | None, str | None]] = []
        self.loaded_profile_data: dict = {"Name": "Profile"}

    def validate_config_document_for_save(
        self,
        document_text: str,
        *,
        config_values: dict | None = None,
        powershell_host: str | None = None,
    ) -> tuple[list[str], list[str]]:
        self.validation_calls.append((document_text, config_values, powershell_host))
        return list(self.validation_errors), []

    def _config_backup_path(self, output_path: Path) -> Path:
        return output_path.parent / "ConfigBackups" / f"{output_path.stem}.backup{output_path.suffix}"

    def config_profiles_dir(self, config_path: Path) -> Path:
        return config_profiles_dir(config_path)

    def normalize_profile_name(self, raw_name: str) -> str:
        return normalize_profile_name(raw_name)

    def config_profile_path(self, config_path: Path, profile_name: str) -> tuple[str, Path]:
        return config_profile_path(config_path, profile_name, path_within_root=lambda path, root: str(path).startswith(str(root)))

    def load_config_data(self, profile_path: Path, powershell_host: str | None) -> dict:
        _ = profile_path, powershell_host
        return dict(self.loaded_profile_data)

    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult:
        self.saved_documents.append((output_path, document_text, create_backup, config_values, powershell_host))
        return ConfigSaveResult(output_path=output_path, backup_path=output_path.with_suffix(".backup.psd1"))


def _resolved(config_path: Path, powershell_host: str | None = "pwsh") -> ResolvedPaths:
    return ResolvedPaths(
        app_root=config_path.parent,
        workspace_root=config_path.parent,
        pipeline_path=config_path.parent / "MediaPipeline.ps1",
        config_path=config_path,
        audit_script_path=config_path.parent / "Audit.ps1",
        rerun_script_path=config_path.parent / "Rerun.ps1",
        powershell_host=powershell_host,
    )


class ServiceConfigSaveRunnerTests(unittest.TestCase):
    def test_save_config_document_validates_backs_up_and_writes_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            config_path.write_text("@{ Name = 'old' }", encoding="utf-8")
            service = _DummyConfigSaveService()

            result = save_config_document_for_service(
                service,
                config_path,
                "@{ Name = 'new' }",
                True,
                config_values={"Name": "new"},
                powershell_host="pwsh",
            )

            self.assertEqual(config_path.read_text(encoding="utf-8"), "@{ Name = 'new' }")
            self.assertIsNotNone(result.backup_path)
            self.assertEqual(result.backup_path.read_text(encoding="utf-8"), "@{ Name = 'old' }")
            self.assertEqual(service.validation_calls, [("@{ Name = 'new' }", {"Name": "new"}, "pwsh")])

    def test_save_config_document_rejects_validation_errors_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            config_path.write_text("@{ Name = 'old' }", encoding="utf-8")
            service = _DummyConfigSaveService()
            service.validation_errors = ["bad config"]

            with self.assertRaisesRegex(ValueError, "bad config"):
                save_config_document_for_service(
                    service,
                    config_path,
                    "@{ Name = 'new' }",
                    False,
                    config_values=None,
                    powershell_host=None,
                )

            self.assertEqual(config_path.read_text(encoding="utf-8"), "@{ Name = 'old' }")

    def test_list_config_profiles_sorts_safe_names_and_ignores_unsafe_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            profiles_dir = config_profiles_dir(config_path)
            profiles_dir.mkdir()
            (profiles_dir / "z_Profile.psd1").write_text("@{}", encoding="utf-8")
            (profiles_dir / "A_Profile.psd1").write_text("@{}", encoding="utf-8")
            (profiles_dir / "bad@name.psd1").write_text("@{}", encoding="utf-8")

            names = list_config_profiles_for_service(_DummyConfigSaveService(), config_path)

            self.assertEqual(names, ["A_Profile", "z_Profile"])

    def test_normalize_config_path_value_unquotes_and_resolves_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path_text = f'"{Path(temp_dir) / "Media Pipeline"}"'

            normalized = normalize_config_path_value(path_text)

            self.assertTrue(normalized.endswith("Media Pipeline"))
            self.assertNotIn('"', normalized)

    def test_save_config_profile_validates_current_config_before_profile_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            config_path.write_text("@{ Name = 'current' }", encoding="utf-8")
            service = _DummyConfigSaveService()

            safe_name, profile_path = save_config_profile_for_service(service, _resolved(config_path), "Night Run")

            self.assertEqual(safe_name, "Night_Run")
            self.assertEqual(profile_path.read_text(encoding="utf-8"), "@{ Name = 'current' }")
            self.assertEqual(service.validation_calls, [("@{ Name = 'current' }", None, "pwsh")])

    def test_load_config_profile_validates_profile_and_saves_to_active_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            config_path.write_text("@{ Name = 'active' }", encoding="utf-8")
            profiles_dir = config_profiles_dir(config_path)
            profiles_dir.mkdir()
            profile_path = profiles_dir / "Night_Run.psd1"
            profile_path.write_text("@{ Name = 'profile' }", encoding="utf-8")
            service = _DummyConfigSaveService()

            safe_name, loaded_path, result = load_config_profile_for_service(service, _resolved(config_path), "Night Run")

            self.assertEqual(safe_name, "Night_Run")
            self.assertEqual(loaded_path, profile_path)
            self.assertEqual(result.output_path, config_path)
            self.assertEqual(service.validation_calls, [("@{ Name = 'profile' }", {"Name": "Profile"}, "pwsh")])
            self.assertEqual(
                service.saved_documents,
                [(config_path, "@{ Name = 'profile' }", True, {"Name": "Profile"}, "pwsh")],
            )


if __name__ == "__main__":
    unittest.main()
