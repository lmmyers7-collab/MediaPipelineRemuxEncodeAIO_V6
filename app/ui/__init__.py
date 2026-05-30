"""WebView UI preference persistence helpers."""

from .preferences import (
    UI_PREFERENCES_SCHEMA_VERSION,
    read_ui_preferences,
    ui_preferences_path,
    write_ui_preferences,
)

__all__ = [
    "UI_PREFERENCES_SCHEMA_VERSION",
    "read_ui_preferences",
    "ui_preferences_path",
    "write_ui_preferences",
]
