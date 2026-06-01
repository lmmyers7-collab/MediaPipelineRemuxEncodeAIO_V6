from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.storage.constants import APP_STATE_NAME
from app.storage.state_migration import (
    app_state_path_for_state_root,
    migrate_app_state_path,
    migrate_app_state_path_for_service,
)


class DummyLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, *args: object) -> None:
        self.warnings.append(message % args)


class DummyService:
    def __init__(self, app_root: Path) -> None:
        self.app_root = app_root
        self.logger = DummyLogger()
        self.app_state_path = app_root / APP_STATE_NAME


class ServicePathStateMigrationTests(unittest.TestCase):
    def test_app_state_path_for_state_root_uses_state_app_folder(self) -> None:
        self.assertEqual(
            app_state_path_for_state_root(Path("D:/Media/State")),
            Path("D:/Media/State") / "App" / APP_STATE_NAME,
        )

    def test_migrate_app_state_path_copies_legacy_state_when_preferred_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            app_root.mkdir()
            legacy = app_root / APP_STATE_NAME
            legacy.write_text('{"legacy": true}', encoding="utf-8")
            preferred = root / "LocalBase" / "State" / "App" / APP_STATE_NAME
            logger = DummyLogger()

            selected = migrate_app_state_path(app_root, preferred, logger)

            self.assertEqual(selected, preferred)
            self.assertEqual(preferred.read_text(encoding="utf-8"), '{"legacy": true}')
            self.assertEqual(logger.warnings, [])

    def test_migrate_app_state_path_keeps_preferred_when_no_legacy_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            app_root.mkdir()
            preferred = root / "LocalBase" / "State" / "App" / APP_STATE_NAME
            logger = DummyLogger()

            selected = migrate_app_state_path(app_root, preferred, logger)

            self.assertEqual(selected, preferred)
            self.assertFalse(preferred.exists())
            self.assertEqual(logger.warnings, [])

    def test_migrate_app_state_path_falls_back_to_legacy_on_copy_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            app_root.mkdir()
            legacy = app_root / APP_STATE_NAME
            legacy.write_text("legacy", encoding="utf-8")
            preferred = root / "LocalBase" / "State" / "App" / APP_STATE_NAME
            logger = DummyLogger()

            with patch(
                "app.storage.state_migration.shutil.copy2",
                side_effect=OSError("locked"),
            ):
                selected = migrate_app_state_path(app_root, preferred, logger)

            self.assertEqual(selected, legacy)
            self.assertFalse(preferred.exists())
            self.assertEqual(logger.warnings, ["App state migration failed: locked"])

    def test_migrate_app_state_path_for_service_sets_service_app_state_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = DummyService(root / "DesktopApp")
            service.app_root.mkdir()
            preferred = root / "LocalBase" / "State" / "App" / APP_STATE_NAME

            migrate_app_state_path_for_service(service, preferred)

            self.assertEqual(service.app_state_path, preferred)


if __name__ == "__main__":
    unittest.main()
