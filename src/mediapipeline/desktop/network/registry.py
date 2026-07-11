"""
network.registry
================
``InFlightRegistry`` — coordinator-side tracking of claimed-but-not-yet-done
encode jobs.

Thread safety: every public method acquires ``_lock`` before touching shared
state.  Callers must not hold any other lock when calling in here to avoid
deadlocks.

Phase 1: full implementation.
"""
from __future__ import annotations

import copy
import json
import logging
import ntpath
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.network.url_policy import redact_network_secret_text

from .failure_reasons import REASON_ENCODE_ERROR, bounded_failure_reason, normalize_failure_reason_code
from .json_policy import loads_strict_json
from .protocol import (
    WorkerEntry,
    coerce_finite_float,
    coerce_library_id_list,
    coerce_nonnegative_int,
    coerce_progress_percent,
)

_log = logging.getLogger(__name__)



from mediapipeline.desktop.network.registry_support import *  # noqa: F403
from mediapipeline.desktop.network.registry_lifecycle import InFlightRegistryLifecycleMixin
from mediapipeline.desktop.network.registry_recovery import InFlightRegistryRecoveryMixin
from mediapipeline.desktop.network.registry_snapshots import InFlightRegistrySnapshotsMixin
from mediapipeline.desktop.network.registry_persistence import InFlightRegistryPersistenceMixin

class InFlightRegistry(
    InFlightRegistryLifecycleMixin,
    InFlightRegistryRecoveryMixin,
    InFlightRegistrySnapshotsMixin,
    InFlightRegistryPersistenceMixin,
):
    """Thread-safe coordinator-side registry of in-progress encode jobs."""

    _RECENT_COMPLETION_TTL_SECONDS = 30.0
    _MAX_RECLAIM_LEDGER_ENTRIES = 128
    _MAX_LATE_TERMINAL_REPORTS = 128
    _MAX_FAILURE_LEDGER_ENTRIES = 5000
    _MIN_RECLAIMED_SOURCE_QUARANTINE_SECONDS = 900.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._jobs: dict[str, InFlightJob] = {}        # job_id  → job
        self._claimed_paths: dict[str, str] = {}       # source identity → job_id
        # N10 — source_path → epoch-seconds completion time. Read by
        # is_in_flight() which lazy-prunes stale entries on access.
        self._recent_completions: dict[str, float] = {}
        self.session_completed: int = 0
        self.session_failed: int    = 0
        # Per-worker cumulative session stats plus last terminal failure reason.
        self._worker_stats: dict[str, dict[str, Any]] = {}
        # Worker/source failure ledger used to suppress repeated same-reason
        # redispatch loops without mutating source media or queue records.
        self._failure_ledger: dict[str, dict[str, Any]] = {}
        # Reclaim and late-terminal ledgers preserve evidence after stale takeover.
        self._reclaim_ledger: dict[str, dict[str, Any]] = {}
        self._late_terminal_reports: list[dict[str, Any]] = []
        self._reclaimed_source_quarantine: dict[str, dict[str, Any]] = {}
