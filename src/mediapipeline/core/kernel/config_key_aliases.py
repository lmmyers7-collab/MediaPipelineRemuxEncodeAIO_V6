"""Compatibility aliases for configuration keys."""

from __future__ import annotations

from typing import Final

CONFIG_KEY_ALIASES: Final[dict[str, str]] = {
    # Legacy output-root names observed in compatibility evidence. These are
    # accepted only during explicit PSD1 import/migration; save-patch still
    # requires canonical keys.
    "OutsourcePath": "Outsource",
    "OutputRoot": "Outsource",
    "ServerOut": "Outsource",
    "ScratchRoot": "LocalBase",
}

__all__ = ("CONFIG_KEY_ALIASES",)
