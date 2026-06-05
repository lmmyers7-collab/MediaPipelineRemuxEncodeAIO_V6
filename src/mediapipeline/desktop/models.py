"""Compatibility shim. Moved to ``mediapipeline.core.kernel.models`` by ADR-0013 (Wave 1).

This module re-exports the public API from its new home. New code should
import from ``mediapipeline.core.kernel.models`` directly; this shim is removed in the
ADR-0013 Wave 6 cleanup.
"""
from mediapipeline.core.kernel.models import *  # noqa: F401,F403
