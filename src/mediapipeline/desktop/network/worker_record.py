from __future__ import annotations

from pathlib import Path

from .protocol import ClaimResponse


def make_queue_record(claim: ClaimResponse):
    """Build a minimal QueueRecord from a coordinator claim response."""
    from ..models import QueueRecord  # local import to avoid circular deps

    src = Path(claim.source_path)
    return QueueRecord(
        source_path=src,
        source_root=src.parent,
        media_type="Unknown",
        is_priority=claim.priority,
        priority_reasons=[],
        priority_rank=0.0,
        sort_name=src.stem,
        display_name=src.name,
        relative_path=claim.source_path,
        show_folder="",
        season_folder="",
        season_number=0,
        episode_number=0,
        source_mtime=0.0,
        size_gb=claim.estimated_size_gb,
        route_name="worker",
        route_reason="Coordinator-assigned",
        matched_show_override="",
        queue_index=1,
        queue_total=1,
        phase="WORKER",
        global_order=0,
    )
