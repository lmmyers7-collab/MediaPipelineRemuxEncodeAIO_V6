"""Compatibility shim for schedule-stop watcher helpers.

New code should import from ``mediapipeline.core.schedule.stop_watcher``.
"""

from __future__ import annotations

from mediapipeline.core.schedule.stop_watcher import *  # noqa: F401,F403
