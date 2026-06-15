from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from mediapipeline.core.storage.constants import APP_STATE_NAME
from mediapipeline.core.storage.contracts import AppStateMigrationServiceProtocol, WarningLogger


def app_state_path_for_state_root(state_root: Path) -> Path:
    return state_root / "App" / APP_STATE_NAME


def _copy_file_atomically(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        dir=destination_path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb"):
            pass
        shutil.copy2(source_path, tmp_path)
        with tmp_path.open("r+b") as target:
            os.fsync(target.fileno())
        os.replace(tmp_path, destination_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def migrate_app_state_path(app_root: Path, preferred_path: Path, logger: WarningLogger) -> Path:
    legacy_path = app_root / APP_STATE_NAME
    if not preferred_path.exists() and legacy_path.exists():
        try:
            _copy_file_atomically(legacy_path, preferred_path)
        except OSError as exc:
            logger.warning("App state migration failed: %s", exc)
            return legacy_path
    return preferred_path


def migrate_app_state_path_for_service(service: AppStateMigrationServiceProtocol, preferred_path: Path) -> None:
    service.app_state_path = migrate_app_state_path(service.app_root, preferred_path, service.logger)
