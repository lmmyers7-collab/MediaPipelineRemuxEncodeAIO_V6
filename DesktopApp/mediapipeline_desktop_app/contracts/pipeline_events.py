"""Compatibility shim. Moved to `app.kernel.contracts.pipeline_events` by ADR-0013 (Wave 5).

Re-exports the public namespace from the new home. New code should import from
`app.kernel.contracts.pipeline_events` directly; removed in the ADR-0013 Wave 6 cleanup.
"""
from app.kernel.contracts import pipeline_events as _moved
globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
