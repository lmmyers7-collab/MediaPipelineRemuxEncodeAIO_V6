"""Compatibility shim. Moved to ``mediapipeline.core.kernel.config_keys`` by ADR-0013 (Wave 2).

This module re-exports the public API from its new home. New code should
import from ``mediapipeline.core.kernel.config_keys`` directly; this shim is removed in the
ADR-0013 Wave 6 cleanup.
"""
from mediapipeline.core.kernel.config_keys import *  # noqa: F401,F403
