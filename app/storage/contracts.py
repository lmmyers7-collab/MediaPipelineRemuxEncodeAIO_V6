from __future__ import annotations

from pathlib import Path
from typing import Protocol


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class AppStateMigrationServiceProtocol(Protocol):
    app_root: Path
    app_state_path: Path | None
    logger: WarningLogger
