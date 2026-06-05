"""Shared kernel: cross-layer types and constants.

Per ADR-0012 / ADR-0013, this package holds types depended on by both
``mediapipeline.core`` and ``mediapipeline.desktop``. It must not import anything else
from ``mediapipeline.core.*`` or ``mediapipeline.desktop.*``.

Wave 1 (ADR-0013) seeds it with the ``models`` trio.
"""
