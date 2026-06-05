"""Compatibility shim. Moved to ``mediapipeline.core.kernel.runtime.subprocess_runner`` by ADR-0013 (Wave 2).

This module re-exports the public API from its new home. New code should
import from ``mediapipeline.core.kernel.runtime.subprocess_runner`` directly; this shim is
removed in the ADR-0013 Wave 6 cleanup.
"""
from mediapipeline.core.kernel.runtime.subprocess_runner import *  # noqa: F401,F403
