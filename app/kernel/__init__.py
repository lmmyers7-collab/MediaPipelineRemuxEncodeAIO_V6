"""Shared kernel: cross-layer types and constants.

Per ADR-0012 / ADR-0013, this package holds types depended on by both
``app`` and ``mediapipeline_desktop_app``. It must not import anything else
from ``app.*`` or ``mediapipeline_desktop_app.*``.

Wave 1 (ADR-0013) seeds it with the ``models`` trio.
"""
