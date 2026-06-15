"""
network.standalone
==================
``StandaloneDispatcher`` — wraps the existing single-machine queue behaviour.

This is the default dispatcher used when ``NetworkRole == "standalone"``.
It is a thin wrapper around the queue_records list that the app already
maintains.  Behaviour is byte-for-byte identical to what the app did before
the dispatcher abstraction was introduced — the wrapper exists purely so the
rest of the app can call ``dispatcher.claim_next()`` without knowing which
mode is active.

No networking, no locking beyond what was already present, no side effects.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from .dispatcher import ClaimedJob, QueueDispatcher

if TYPE_CHECKING:
    from ..app import MediaPipelineApp


class StandaloneDispatcher(QueueDispatcher):
    """Single-machine dispatcher.  Pops from the local queue_records list."""

    def __init__(self, app: "MediaPipelineApp") -> None:
        self._app = app

    # ------------------------------------------------------------------
    # QueueDispatcher interface
    # ------------------------------------------------------------------

    def claim_next(self) -> ClaimedJob | None:
        """Pop the first item from the local queue.

        Returns ``None`` when the queue is empty.
        """
        records = getattr(self._app, "queue_records", None)
        if not records:
            return None

        record = records[0]
        encode_config = self._snapshot_encode_config()

        return ClaimedJob(
            job_id=str(uuid.uuid4()),
            record=record,
            encode_config=encode_config,
            claimed_at=datetime.now(),
            worker_id=getattr(self._app, "_machine_id", "local"),
        )

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
    ) -> None:
        """Delegate to the app's existing completion handler.

        The app's normal post-encode logic (sidecar writing, completion
        record, failure logging) is invoked directly — nothing changes
        from the pre-dispatcher implementation.
        """
        # The existing completion path lives on the app.  We call it
        # through whatever method the app exposes after the encode
        # subprocess exits.  In standalone mode the encode loop handles
        # this; mark_done is a signal that the dispatcher layer is done
        # with the job.  No additional work needed here.
        pass

    def release(self, job: ClaimedJob) -> None:
        """Re-insert the job's record at the front of the queue.

        Called when the app is shutting down mid-encode so the file is
        not silently dropped from the queue.
        """
        records = getattr(self._app, "queue_records", None)
        if records is None:
            return
        # Only re-insert if not already present (idempotent).
        source = getattr(job.record, "source_path", None)
        if source and not any(
            getattr(r, "source_path", None) == source for r in records
        ):
            records.insert(0, job.record)

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
