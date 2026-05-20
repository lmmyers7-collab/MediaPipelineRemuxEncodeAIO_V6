"""
Shared network diagnostic formatting helpers.
"""
from __future__ import annotations


DIAGNOSTIC_PREVIEW_CHARS = 240
DIAGNOSTIC_TRUNCATION_SUFFIX = "...<truncated>"


def diagnostic_preview(text: object, *, limit: int = DIAGNOSTIC_PREVIEW_CHARS) -> str:
    """Return a bounded single-value diagnostic string for logs and UI status."""
    detail = str(text)
    if len(detail) <= limit:
        return detail
    return detail[:limit] + DIAGNOSTIC_TRUNCATION_SUFFIX
