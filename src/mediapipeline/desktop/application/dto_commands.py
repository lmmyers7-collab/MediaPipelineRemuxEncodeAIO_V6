"""Compatibility shim. Moved to ``mediapipeline.core.kernel.dto_commands`` by ADR-0013 (Wave 3).

Re-exports the full public namespace from the new home so existing imports
keep working. New code should import from ``mediapipeline.core.kernel.dto_commands``
directly; this shim is removed in the ADR-0013 Wave 6 cleanup.
"""
from mediapipeline.core.kernel import dto_commands as _moved
globals().update({_k: getattr(_moved, _k) for _k in dir(_moved) if not _k.startswith("__")})
del _moved

# Literal __all__ mirrors mediapipeline.core.kernel.dto_commands (application public-API
# contract, tests/test_application_public_api.py requires a literal list here).
__all__ = ["CommandResult"]
