from __future__ import annotations

from importlib import import_module

ConfigPreview = import_module("mediapipeline.core.config.contracts").ConfigPreview
ConfigSaveResult = import_module("mediapipeline.core.config.contracts").ConfigSaveResult
ResolvedPaths = import_module("mediapipeline.core.paths.contracts").ResolvedPaths
Snapshot = import_module("mediapipeline.core.status.contracts").Snapshot
TelemetrySnapshot = import_module("mediapipeline.core.telemetry.contracts").TelemetrySnapshot
