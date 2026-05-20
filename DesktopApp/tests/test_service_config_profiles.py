from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from mediapipeline_desktop_app.service_config import ConfigProfileServiceMixin
from mediapipeline_desktop_app.service_config_profiles import (
    config_profile_path,
    config_profiles_dir,
    normalize_profile_name,
)


class _ConfigProfileServiceWithPathGuard(ConfigProfileServiceMixin):
    def _path_within_root(self, path: Path, root: Path) -> bool:
        return str(path).startswith(str(root))


class ServiceConfigProfileTests(unittest.TestCase):
    def test_normalize_profile_name_replaces_spaces_and_rejects_unsafe_names(self) -> None:
        self.assertEqual(normalize_profile_name("Night Run"), "Night_Run")

        for raw in ("", "../bad", "bad:name", "bad/name"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    normalize_profile_name(raw)

    def test_config_profile_path_stays_under_profiles_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            profiles_dir = config_profiles_dir(config_path)

            safe_name, profile_path = config_profile_path(config_path, "Direct Play")

        self.assertEqual(safe_name, "Direct_Play")
        self.assertEqual(profile_path, profiles_dir / "Direct_Play.psd1")

    def test_config_profile_path_uses_injected_path_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            with self.assertRaises(RuntimeError):
                config_profile_path(config_path, "Night", path_within_root=lambda _path, _root: False)

    def test_service_mixin_preserves_profile_wrapper_methods(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "MediaPipeline_config.psd1"
            service = _ConfigProfileServiceWithPathGuard()

            self.assertEqual(service.normalize_profile_name("Night Run"), "Night_Run")
            self.assertEqual(service.config_profiles_dir(config_path), config_path.parent / "Profiles")
            safe_name, profile_path = service.config_profile_path(config_path, "Night Run")

        self.assertEqual(safe_name, "Night_Run")
        self.assertEqual(profile_path.name, "Night_Run.psd1")


if __name__ == "__main__":
    unittest.main()
