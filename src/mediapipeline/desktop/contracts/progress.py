"""Compatibility shim. Moved to `mediapipeline.core.kernel.contracts.progress` by ADR-0013 (Wave 5).

Re-exports the public namespace from the new home. New code should import from
`mediapipeline.core.kernel.contracts.progress` directly; removed in the ADR-0013 Wave 6 cleanup.
"""
from mediapipeline.core.kernel.contracts import progress as _moved
globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved
