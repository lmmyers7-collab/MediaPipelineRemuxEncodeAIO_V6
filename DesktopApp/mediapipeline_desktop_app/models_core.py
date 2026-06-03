"""Compatibility shim. Moved to ``app.kernel.models_core`` by ADR-0013 (Wave 1).

This module re-exports the public API from its new home. New code should
import from ``app.kernel.models_core`` directly; this shim is removed in the
ADR-0013 Wave 6 cleanup.
"""
from app.kernel.models_core import *  # noqa: F401,F403
