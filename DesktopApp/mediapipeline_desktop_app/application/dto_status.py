"""Compatibility shim. Moved to ``app.kernel.dto_status`` by ADR-0013 (Wave 4).

Re-exports the full public namespace from the new home so existing imports
keep working. New code should import from ``app.kernel.dto_status`` directly;
this shim is removed in the ADR-0013 Wave 6 cleanup.
"""
from app.kernel import dto_status as _moved
globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved

# Literal __all__ mirrors app.kernel.dto_status (application public-API
# contract, tests/test_application_public_api.py requires a literal list here).
__all__ = [
    "HealthDto",
    "AppSnapshotDto",
    "TelemetryDto",
    "DiagnosticsDto",
    "CloseReadinessDto",
]
