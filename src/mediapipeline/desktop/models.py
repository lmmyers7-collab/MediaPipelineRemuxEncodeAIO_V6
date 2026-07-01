"""Compatibility shim. Moved to core-owned record modules by ADR-0013/#23.

This module re-exports the public API from its new home. New code should
import domain records from their core homes directly; this shim is removed in
the ADR-0013 Wave 6 cleanup.
"""
from mediapipeline.core.audit.contracts import AuditRecord  # noqa: F401
from mediapipeline.core.completed.contracts import CompletedJobRecord  # noqa: F401
from mediapipeline.core.config.contracts import ConfigPreview, ConfigSaveResult  # noqa: F401
from mediapipeline.core.failures.contracts import FailureRecord  # noqa: F401
from mediapipeline.core.kernel.models import *  # noqa: F401,F403
from mediapipeline.core.paths.contracts import ResolvedPaths  # noqa: F401
from mediapipeline.core.queue.contracts import QueueRecord  # noqa: F401
from mediapipeline.core.status.contracts import Snapshot  # noqa: F401
from mediapipeline.core.telemetry.contracts import TelemetrySnapshot  # noqa: F401
