"""Compatibility shim. Moved to `app.kernel.contracts.process_result` by ADR-0013 (Wave 5).

Re-exports the public namespace from the new home. New code should import from
`app.kernel.contracts.process_result` directly; removed in the ADR-0013 Wave 6 cleanup.
"""
from app.kernel.contracts import process_result as _moved
globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
