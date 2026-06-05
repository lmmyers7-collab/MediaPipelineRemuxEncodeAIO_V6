from __future__ import annotations

import shutil
from pathlib import Path

from mediapipeline.core.storage.constants import APP_STATE_NAME
from mediapipeline.core.storage.contracts import AppStateMigrationServiceProtocol, WarningLogger


def app_state_path_for_state_root(state_root: Path) -> Path:
    return state_root / "App" / APP_STATE_NAME


def migrate_app_state_path(app_root: Path, preferred_path: Path, logger: WarningLogger) -> Path:
    legacy_path = app_root / APP_STATE_NAME
    if not preferred_path.exists() and legacy_path.exists():
        try:
            preferred_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_path, preferred_path)
        except OSError as exc:
            logger.warning("App state migration failed: %s", exc)
            return legacy_path
    return preferred_path


def migrate_app_state_path_for_service(service: AppStateMigrationServiceProtocol, preferred_path: Path) -> None:
    service.app_state_path = migrate_app_state_path(service.app_root, preferred_path, service.logger)
