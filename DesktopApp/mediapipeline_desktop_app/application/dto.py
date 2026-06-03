"""Compatibility shim. Moved to ``app.kernel.dto`` by ADR-0013 (Wave 4).

This aggregator re-exports the kernel DTO families. The full public namespace
is copied from the new home so existing imports (including
``application/__init__.py``) keep working. New code should import from
``app.kernel.dto`` directly; this shim is removed in the ADR-0013 Wave 6
cleanup.
"""
from app.kernel import dto as _moved
globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved

# Literal __all__ mirrors app.kernel.dto (application public-API contract,
# tests/test_application_public_api.py requires a literal list here).
__all__ = [
    "AppSnapshotDto",
    "AuditPreviewDto",
    "CloseReadinessDto",
    "CommandResult",
    "CompletedPreviewDto",
    "DiagnosticsDto",
    "FailurePreviewDto",
    "HealthDto",
    "JsonMap",
    "MaintenanceWorkspaceDto",
    "NetworkWorkersDto",
    "PendingPublishPreviewDto",
    "PublishReconciliationDto",
    "QueuePreviewDto",
    "RenamePreviewDto",
    "ScheduleWorkspaceDto",
    "SettingsWorkspaceDto",
    "TelemetryDto",
    "json_safe",
    "split_summary_lines",
]
