from __future__ import annotations

from pathlib import Path

from .protocol import ClaimResponse


def make_queue_record(claim: ClaimResponse):
    """Build a minimal QueueRecord from a coordinator claim response."""
    from ..models import QueueRecord  # local import to avoid circular deps

    source_path = str(claim.source_path or "").strip()
    if not source_path or source_path == ".":
        raise ValueError("claimed network job requires a non-empty source_path")
    src = Path(claim.source_path)
    record = QueueRecord(
        source_path=src,
        source_root=src.parent,
        media_type="Unknown",
        is_priority=claim.priority,
        priority_reasons=[],
        priority_rank=0.0,
        sort_name=src.stem,
        display_name=src.name,
        relative_path=claim.relative_path or claim.source_path,
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
    record.library_id = claim.library_id
    record.job_kind = claim.job_kind or "pipeline_queue"
    record.rerun_batch_id = claim.rerun_batch_id
    record.rerun_row_key = claim.rerun_row_key
    record.rerun_row_index = claim.rerun_row_index
    record.planned_output_path = claim.planned_output_path
    record.output_handoff = dict(claim.output_handoff)
    record.source_identity = dict(claim.source_identity)
    record.coordinator_source_path = claim.coordinator_source_path or claim.source_path
    record.worker_source_path = claim.worker_source_path or claim.source_path
    record.handoff_probe = dict(claim.handoff_probe)
    if record.job_kind == "csv_rerun_row":
        record.route_name = "network_csv_rerun_row"
        record.route_reason = "Coordinator-assigned Network CSV rerun row"
    return record
