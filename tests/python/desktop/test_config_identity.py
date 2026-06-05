from __future__ import annotations

import sys
import tempfile
import unittest
import os
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest import mock

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.identity import (  # noqa: E402
    CONFIG_IDENTITY_SCHEMA_VERSION,
    MIN_OPERATOR_CONFIG_KEY_COUNT,
    build_config_identity,
    config_identity_block_reasons,
    last_good_snapshot_path,
    user_last_good_snapshot_path,
    write_last_good_config_snapshot,
)


def _operator_config(root: Path) -> dict[str, object]:
    data: dict[str, object] = {f"Key{index}": index for index in range(MIN_OPERATOR_CONFIG_KEY_COUNT)}
    data.update(
        {
            "SourceMovies": r"\\LAYNE-SERVER\Users\Layne\Videos\Encode\Movies",
            "SourceTV": r"\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV",
            "Outsource": r"\\LAYNE-SERVER\Users\Layne\Videos\outsource\Movies",
            "LocalBase": str(root / "Scratch"),
        }
    )
    return data


class ConfigIdentityTests(unittest.TestCase):
    def test_identity_ready_for_operator_config_and_writes_last_good_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config_path = root / "MediaPipeline_config.psd1"
            config_path.write_text("@{ SourceMovies = '\\\\server\\Movies' }\n", encoding="utf-8")
            data = _operator_config(root)

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(root / "LocalAppData")}, clear=False):
                identity = build_config_identity(config_path, data, app_root=root / "DesktopApp", workspace_root=root)
                snapshot = write_last_good_config_snapshot(config_path, root / "Scratch", identity)
                user_snapshot = user_last_good_snapshot_path()

            self.assertEqual(identity["schema_version"], CONFIG_IDENTITY_SCHEMA_VERSION)
            self.assertFalse(identity["blocks_operations"])
            self.assertEqual(identity["status_state"], "ready")
            self.assertEqual(identity["key_count"], len(data))
            self.assertEqual(snapshot, last_good_snapshot_path(root / "Scratch"))
            self.assertEqual(snapshot.read_text(encoding="utf-8"), config_path.read_text(encoding="utf-8"))
            self.assertIsNotNone(user_snapshot)
            assert user_snapshot is not None
            self.assertEqual(user_snapshot.read_text(encoding="utf-8"), config_path.read_text(encoding="utf-8"))

    def test_identity_blocks_missing_template_and_underloaded_configs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            template = root / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
            active = root / "MediaPipeline_config.psd1"
            template.parent.mkdir(parents=True)
            template_text = "@{ SourceMovies = 'C:\\MediaPipeline\\Incoming\\Movies' }\n"
            template.write_text(template_text, encoding="utf-8")
            active.write_text(template_text, encoding="utf-8")

            missing = build_config_identity(root / "missing.psd1", {}, app_root=root / "apps" / "desktop", workspace_root=root)
            low = build_config_identity(active, {"SourceMovies": r"C:\Movies"}, app_root=root / "apps" / "desktop", workspace_root=root)
            template_identity = build_config_identity(
                active,
                {
                    "SourceMovies": r"C:\MediaPipeline\Incoming\Movies",
                    "SourceTV": r"C:\MediaPipeline\Incoming\TV",
                    "Outsource": r"C:\MediaPipeline\Processed",
                    "LocalBase": r"C:\MediaPipeline\Scratch",
                    **{f"Key{index}": index for index in range(MIN_OPERATOR_CONFIG_KEY_COUNT)},
                },
                app_root=root / "apps" / "desktop",
                workspace_root=root,
            )

            self.assertTrue(missing["blocks_operations"])
            self.assertTrue(low["suspicious_low_key_count"])
            self.assertTrue(low["blocks_operations"])
            self.assertTrue(template_identity["template_path_match"])
            self.assertTrue(template_identity["template_hash_match"])
            self.assertIn("Config file is missing", "\n".join(config_identity_block_reasons(missing)))
            self.assertIn("operator threshold", "\n".join(config_identity_block_reasons(low)))


if __name__ == "__main__":
    unittest.main()
