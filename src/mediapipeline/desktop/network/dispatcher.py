"""
network.dispatcher
==================
Abstract base class and shared data types for queue dispatch.

All three network modes (Standalone, Coordinator, Worker) implement
``QueueDispatcher``.  The rest of the app only ever talks to this
interface — it never knows which concrete implementation is active.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import QueueRecord


@dataclass
class ClaimedJob:
    """A single queue item that has been atomically reserved for encoding.

    Attributes
    ----------
    job_id:
        UUID string uniquely identifying this claim.  The coordinator
        uses this to correlate heartbeats and completion reports.
    record:
        The ``QueueRecord`` for the file to encode.
    encode_config:
        Snapshot of the encode-relevant config keys taken at claim time.
        Workers use this rather than reading their local config so that
        a coordinator config change mid-run does not affect in-flight jobs.
    claimed_at:
        Wall-clock time when the claim was made.
    worker_id:
        UUID string identifying the machine that made the claim.
        In standalone mode this is the local machine ID.
    """

    job_id:        str
    record:        "QueueRecord"
    encode_config: dict          = field(default_factory=dict)
    claimed_at:    datetime      = field(default_factory=datetime.now)
    worker_id:     str           = ""


class QueueDispatcher(ABC):
    """Decide what gets encoded next and track completion.

    Implementations must be thread-safe: ``claim_next`` and ``mark_done``
    may be called from backend control and worker threads concurrently.
    """

    @abstractmethod
    def claim_next(self) -> ClaimedJob | None:
        """Return the next job to encode, atomically reserved.

        Returns ``None`` when the queue is empty or when the dispatcher
        cannot reach the coordinator (worker mode, network error).
        The caller should sleep ``WorkerPollIntervalSecs`` and retry.
        """

    @abstractmethod
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
        """Report a job as finished (success or failure).

        The dispatcher is responsible for routing this to the appropriate
        completion handler — local completion logic in standalone/coordinator
        mode, or a remote ``POST /api/done`` call in worker mode.
        """

    @abstractmethod
    def release(self, job: ClaimedJob) -> None:
        """Return a job to the queue without marking it done.

        Called when the worker is shutting down cleanly mid-encode so the
        file is immediately available to the next worker rather than
        waiting for the heartbeat timeout to expire.
        """

    def heartbeat(
        self,
        job: ClaimedJob,
        *,
        progress: float = 0.0,
        stage: str = "",
    ) -> bool:
        """Signal that the worker is still alive and encoding.

        The default implementation is a no-op that always returns ``True``.
        ``CoordinatorDispatcher`` and ``WorkerDispatcher`` override this.

        Returns
        -------
        bool
            ``True``  — continue encoding normally.
            ``False`` — the coordinator has reclaimed this job (timed out
                        a previous heartbeat or received a conflicting
                        claim).  The worker should abort and re-enter the
                        poll loop.
        """
        return True

    def shutdown(self) -> None:
        """Optional cleanup called when the app is closing.

        Override to stop background threads, close sockets, etc.
        The default implementation is a no-op.
        """
