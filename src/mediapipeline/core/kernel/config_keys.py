from __future__ import annotations

from .config_key_aliases import CONFIG_KEY_ALIASES
from .config_key_groups import *
from .config_key_order import ALL_CONFIG_KEYS, CONFIG_KEY_ORDER, NETWORK_CONFIG_KEYS, PYTHON_SCHEMA_CONFIG_KEYS

__all__ = tuple(name for name in globals() if name.startswith("KEY_")) + (
    "CONFIG_KEY_ORDER",
    "NETWORK_CONFIG_KEYS",
    "PYTHON_SCHEMA_CONFIG_KEYS",
    "ALL_CONFIG_KEYS",
)
