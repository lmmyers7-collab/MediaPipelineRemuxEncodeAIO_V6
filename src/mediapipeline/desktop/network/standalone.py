"""
network.standalone
==================
``StandaloneDispatcher`` — wraps the existing single-machine queue behaviour.

This is the default dispatcher used when ``NetworkRole == "standalone"``.
It wraps the ``queue_records`` list that the app already maintains. Claims,
releases, and terminal completion share application-scoped reservation state
so separately created dispatcher instances cannot claim one record twice.

No networking or filesystem side effects.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from .dispatcher import ClaimedJob, QueueDispatcher

if TYPE_CHECKING:
    from ..app import MediaPipelineApp


@dataclass
class _StandaloneDispatchState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    inflight: dict[str, object] = field(default_factory=dict)


_STATE_INIT_LOCK = threading.Lock()
_STATE_ATTRIBUTE = "_standalone_dispatch_state"


class StandaloneDispatcher(QueueDispatcher):
    """Single-machine dispatcher.  Pops from the local queue_records list."""

    def __init__(self, app: MediaPipelineApp) -> None:
        self._app = app
        with _STATE_INIT_LOCK:
            state = getattr(app, _STATE_ATTRIBUTE, None)
            if not isinstance(state, _StandaloneDispatchState):
                state = _StandaloneDispatchState()
                setattr(app, _STATE_ATTRIBUTE, state)
            self._state = state

    # ------------------------------------------------------------------
    # QueueDispatcher interface
    # ------------------------------------------------------------------

    def claim_next(self) -> ClaimedJob | None:
        """Pop the first item from the local queue.

        Returns ``None`` when the queue is empty.
        """
        with self._state.lock:
            records = getattr(self._app, "queue_records", None)
            if not records:
                return None

            record = records.pop(0)
            job = ClaimedJob(
                job_id=str(uuid.uuid4()),
                record=record,
                encode_config=self._snapshot_encode_config(),
                claimed_at=datetime.now(),
                worker_id=getattr(self._app, "_machine_id", "local"),
            )
            self._state.inflight[job.job_id] = record
            return job

    def mark_done(
        self,
        job: ClaimedJob,
        *,
        success: bool,
        output_path: str | None = None,
        error: str | None = None,
        elapsed_seconds: float = 0.0,
        output_size_bytes: int | None = None,
        completion_status: str | None = None,
        publish_state: str | None = None,
        publish_mode: str | None = None,
        route: str | None = None,
        queue_terminal: bool = False,
        reason_code: str | None = None,
        reason: str | None = None,
        worker_result_artifact: dict | None = None,
        worker_result_artifact_path: str | None = None,
    ) -> None:
        """Terminalize this dispatcher's reservation for a completed job.

        The existing encode loop remains responsible for all completion side
        effects; this method only removes the in-memory ownership record.
        """
        # The existing encode loop owns completion side effects. The
        # dispatcher only terminalizes its reservation, once.
        with self._state.lock:
            self._state.inflight.pop(job.job_id, None)

    def release(self, job: ClaimedJob) -> None:
        """Re-insert the job's record at the front of the queue.

        Called when the app is shutting down mid-encode so the file is
        not silently dropped from the queue.
        """
        with self._state.lock:
            records = getattr(self._app, "queue_records", None)
            reserved = self._state.inflight.get(job.job_id)
            if records is None or reserved is None:
                return
            self._state.inflight.pop(job.job_id, None)
            source = getattr(reserved, "source_path", None)
            already_queued = (
                any(getattr(record, "source_path", None) == source for record in records)
                if source is not None
                else any(record is reserved for record in records)
            )
            if not already_queued:
                records.insert(0, reserved)

    # heartbeat() inherited — always returns True (no coordinator to notify)
    # shutdown()  inherited — no-op

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _snapshot_encode_config(self) -> dict:
        """Return a dict of encode-relevant config keys.

        Snapshotted at claim time so a config change during a long encode
        does not affect the in-flight job's settings.
        """
        resolved = getattr(self._app, "resolved", None)
        if resolved is None or not hasattr(resolved, "config_data"):
            return {}
        cfg = resolved.config_data
        keys = (
            "VideoCodec",
            "VideoPreset",
            "VideoQuality",
            "OutputContainer",
            "EncodeTuningPreset",
            "EncodeLadder",
            "ExtraVideoFlags",
            "FallbackCpuQuality",
            "RoutingProfile",
            "RouteThresholdMode",
            "MovieRoute1080pTargetSizeGB",
            "MovieRoute1440pTargetSizeGB",
            "MovieRoute4KTargetSizeGB",
            "TVRoute1080pTargetSizeGB",
            "TVRoute1440pTargetSizeGB",
            "TVRoute4KTargetSizeGB",
            "Route1080pUpperHeightTolerancePercent",
            "Route1080pMaxVideoBitrateMbps",
            "Route1440pLowerHeightTolerancePercent",
            "Route1440pUpperHeightTolerancePercent",
            "Route1440pMaxVideoBitrateMbps",
            "Route4KLowerHeightTolerancePercent",
            "Route4KMaxVideoBitrateMbps",
            "AllowH264RemuxIfPlexCompatible",
            "H264RemuxMaxBitrateMbps",
            "H264RemuxMaxHeight",
            "SizeGuardMode",
            "MaxEncodeGrowthPercent",
            "CompatibilityEncodeGrowthPercent",
        )
        return {k: cfg.get(k) for k in keys if k in cfg}
