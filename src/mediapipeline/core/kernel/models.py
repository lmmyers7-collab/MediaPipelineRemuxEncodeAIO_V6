from __future__ import annotations

from importlib import import_module

from .models_core import ConfigPreview, ConfigSaveResult, Snapshot, TelemetrySnapshot

AuditRecord = import_module("mediapipeline.core.audit.contracts").AuditRecord
CompletedJobRecord = import_module("mediapipeline.core.completed.contracts").CompletedJobRecord
FailureRecord = import_module("mediapipeline.core.failures.contracts").FailureRecord
QueueRecord = import_module("mediapipeline.core.queue.contracts").QueueRecord
ResolvedPaths = import_module("mediapipeline.core.paths.contracts").ResolvedPaths
