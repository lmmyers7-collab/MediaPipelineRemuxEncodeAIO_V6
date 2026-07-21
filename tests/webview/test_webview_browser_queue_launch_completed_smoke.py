from __future__ import annotations

from datetime import UTC, datetime
import json
import os
import shutil
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
from mediapipeline.contracts.run_monitor import RUN_MONITOR_STAGE_IDS, RunMonitorRecord
from mediapipeline.core.kernel.contracts import accepted_run_rows_fingerprint
from mediapipeline.core.paths.queue_input_fingerprint import queue_input_fingerprint
from mediapipeline.core.status.run_monitor_storage import RunMonitorStore
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import Snapshot

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyProc, DummyWorkflowFacadeService, _resolved
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyProc, DummyWorkflowFacadeService, _resolved
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _queue_row(
    source: Path,
    *,
    root: Path,
    order: int,
    route: str = "remux",
    route_reason: str = "Fixture source is eligible for the deterministic backend-owned plan.",
    blocked_reason_code: str = "",
    blocked_reason: str = "",
) -> dict[str, Any]:
    return {
        "global_order": order,
        "phase": "tv",
        "media_kind": "tv",
        "queue_index": order,
        "queue_total": 3,
        "is_priority": False,
        "source_path": str(source),
        "root_path": str(root),
        "relative_path": str(source.relative_to(root)),
        "display_name": source.name,
        "size_gb": 0.01,
        "route": route if not blocked_reason else "",
        "route_reason_code": "fixture_backend_plan" if not blocked_reason else "",
        "route_reason": route_reason if not blocked_reason else "",
        "blocked_reason_code": blocked_reason_code,
        "blocked_reason": blocked_reason,
        "last_write_utc": _utc_now(),
    }


def _queue_snapshot_payload(fixture: SimpleNamespace, *, completed: bool) -> dict[str, Any]:
    rows = (
        [fixture.blocked_row]
        if completed
        else [fixture.runnable_row_a, fixture.runnable_row_b, fixture.blocked_row]
    )
    return {
        "schema_version": "queue_plan_snapshot.v1",
        "produced_at": _utc_now(),
        "config_path": str(fixture.root / "config.psd1"),
        "local_base": str(fixture.root),
        "source_movies": str(fixture.movies_root),
        "source_tv": str(fixture.tv_root),
        "outsource": str(fixture.output_root),
        "movie_count_total": 0,
        "tv_count_total": 4,
        "priority_count": 0,
        "runnable_count": 0 if completed else 2,
        "total_row_count": len(rows),
        "shown_row_count": len(rows),
        "rows_truncated": False,
        "excluded_count": 1,
        "excluded_row_limit": 100,
        "excluded_rows_truncated": False,
        "excluded_rows": [fixture.excluded_row],
        "accepted_run_rows": [] if completed else fixture.accepted_run_rows,
        "rows": rows,
    }


def _write_queue_launch_completed_fixture(root: Path) -> SimpleNamespace:
    tv_root = root / "TV"
    movies_root = root / "Movies"
    output_root = root / "Outsource"
    runnable_source_a = tv_root / "Runnable Alpha" / "Season 01" / "[SubsPlease] Runnable.Alpha.S01E01.1080p.WEB-DL.x265-GROUP.mkv"
    runnable_source_b = tv_root / "Runnable Beta" / "Season 01" / "[Judas] Runnable.Beta.S01E01.1080p.BluRay.x264.mkv"
    planned_name_a = "Runnable Alpha - S01E01.mkv"
    planned_name_b = "Runnable Beta - S01E01.mkv"
    blocked_source = tv_root / "Blocked Show" / "Season 01" / "Blocked Show S01E02 Needs Review.mkv"
    excluded_source = tv_root / "Excluded Show" / "Season 01" / "Excluded Show S01E03 Held.mkv"
    for path, payload in (
        (runnable_source_a, b"queue-runnable-source-a-fixture"),
        (runnable_source_b, b"queue-runnable-source-b-fixture"),
        (blocked_source, b"queue-blocked-source-fixture"),
        (excluded_source, b"queue-excluded-source-fixture"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    movies_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    state_root = root / "State"
    queue_snapshot_path = state_root / "Progress" / "queue_snapshot.json"
    progress_path = state_root / "Progress" / "pipeline_progress.json"
    event_file = state_root / "Progress" / "pipeline_events.jsonl"
    completed_manifest_path = state_root / "Completed" / "completed_jobs.jsonl"
    failure_report_path = state_root / "Failures" / "backend-queue-job-b.failure.json"
    pending_root = root / "PendingServerPush"
    pending_root.mkdir(parents=True, exist_ok=True)
    command_journal_path = state_root / "RunLogs" / "local_api_command_history.json"
    output = output_root / "TV" / "Runnable Alpha" / "Season 01" / planned_name_a
    output_sidecar = output.with_name(output.name + ".pipeline.json")

    fixture = SimpleNamespace(
        root=root,
        tv_root=tv_root,
        movies_root=movies_root,
        output_root=output_root,
        state_root=state_root,
        runnable_source=runnable_source_a,
        runnable_source_a=runnable_source_a,
        runnable_source_b=runnable_source_b,
        planned_name_a=planned_name_a,
        planned_name_b=planned_name_b,
        blocked_source=blocked_source,
        excluded_source=excluded_source,
        queue_snapshot_path=queue_snapshot_path,
        progress_path=progress_path,
        event_file=event_file,
        completed_manifest_path=completed_manifest_path,
        failure_report_path=failure_report_path,
        pending_root=pending_root,
        command_journal_path=command_journal_path,
        output=output,
        output_sidecar=output_sidecar,
    )
    fixture.runnable_row_a = _queue_row(
        runnable_source_a,
        root=tv_root,
        order=1,
        route="remux",
        route_reason="Queue plan confirms direct-stream-compatible streams for Alpha.",
    )
    fixture.runnable_row_b = _queue_row(
        runnable_source_b,
        root=tv_root,
        order=2,
        route="encode_hardware",
        route_reason="Queue plan requests hardware encode for Beta.",
    )
    fixture.runnable_row = fixture.runnable_row_a
    fixture.blocked_row = _queue_row(
        blocked_source,
        root=tv_root,
        order=3,
        blocked_reason_code="fixture_operator_review",
        blocked_reason="Fixture row remains blocked for explicit operator review.",
    )
    fixture.excluded_row = {
        "source_order": 4,
        "media_type": "tv",
        "media_kind": "tv",
        "source_path": str(excluded_source),
        "relative_path": str(excluded_source.relative_to(tv_root)),
        "display_name": excluded_source.name,
        "reason_code": "fixture_hold_manifest",
        "reason": "Fixture row remains excluded by backend queue curation.",
    }
    fixture.accepted_run_rows = [
        {
            "source_identity": f"fixture-source-{position}",
            "source_identity_algorithm": "source_identity_v2",
            "source_path": str(source),
            "display_name": planned_name,
            "planned_display_name": planned_name,
            "planned_display_name_source": "plex_destination_plan.v1",
            "parent_context": str(source.parent),
            "run_queue_index": position,
            "run_queue_total": 2,
            "route": row["route"],
            "route_reason_code": row["route_reason_code"],
            "route_reason": row["route_reason"],
            "intended_final_path": str(
                output
                if position == 1
                else output_root / "TV" / "Runnable Beta" / "Season 01" / planned_name
            ),
        }
        for position, source, planned_name, row in (
            (1, runnable_source_a, planned_name_a, fixture.runnable_row_a),
            (2, runnable_source_b, planned_name_b, fixture.runnable_row_b),
        )
    ]

    _write_json_atomic(queue_snapshot_path, _queue_snapshot_payload(fixture, completed=False))
    _write_json_atomic(
        progress_path,
        {
            "ProgressVersion": 2,
            "Status": "Idle",
            "CurrentStage": "idle",
            "CurrentQueueIndex": 0,
            "CurrentQueueTotal": 2,
            "TotalProcessed": 0,
            "Remuxed": 0,
            "Encoded": 0,
            "Failed": 0,
            "UpdatedAt": _utc_now(),
        },
    )
    fixture.uncorrelated_completed_event = {
        "schema_version": "pipeline_event.v1",
        "event_id": "fixture-recent-uncorrelated-job-completed",
        "event_type": "job_completed",
        "timestamp": _utc_now(),
        "created_at": _utc_now(),
        "stage": "publish-verification",
        "route": "remux",
        "status": "completed",
        "source_path": str(root / "Unrelated" / "Already Finished.mkv"),
        "run_id": "ffffffffffffffffffffffffffffffff",
        "job_id": "ffffffffffffffffffffffffffffffff-item-00000001",
        "data": {
            "success": True,
            "completion_status": "completed",
            "queue_terminal": True,
            "output_path": str(root / "Unrelated" / "Already Finished.output.mkv"),
        },
    }
    _write_text_atomic(
        event_file,
        json.dumps(fixture.uncorrelated_completed_event, ensure_ascii=False, sort_keys=True) + "\n",
    )
    _write_text_atomic(completed_manifest_path, "")

    resolved = _resolved(root)
    resolved.local_base = root
    resolved.state_root = state_root
    resolved.source_movies = movies_root
    resolved.source_tv = tv_root
    resolved.outsource = output_root
    resolved.queue_snapshot_path = queue_snapshot_path
    resolved.completed_manifest_path = completed_manifest_path
    resolved.pending_push_path = pending_root
    resolved.event_file = event_file
    resolved.config_data = {
        "NetworkRole": "standalone",
        "SourceMovies": str(movies_root),
        "SourceTV": str(tv_root),
        "Outsource": str(output_root),
        "LocalBase": str(root),
        "RoutingProfile": "plex_direct_stream",
        "SizeGuardMode": "advisory",
        "MinFreeSpaceGB": 0,
        "OutsourceMinFreeSpaceGB": 0,
        "DeferredPublish": False,
    }
    fixture.queue_preview_request_id = "browser-backend-queue-preview"
    fixture.queue_plan_fingerprint = "sha256:browser-backend-queue-plan"
    snapshot = _queue_snapshot_payload(fixture, completed=False)
    input_fingerprint = queue_input_fingerprint(resolved)
    snapshot.update(
        {
            "queue_snapshot_origin": "dry_run",
            "desktop_queue_preview_request_id": fixture.queue_preview_request_id,
            "queue_input_fingerprint_schema": input_fingerprint["schema_version"],
            "queue_input_fingerprint": input_fingerprint["fingerprint"],
            "queue_input_components": input_fingerprint["components"],
            "queue_plan_fingerprint_schema": "queue_plan_fingerprint.v1",
            "queue_plan_fingerprint": fixture.queue_plan_fingerprint,
            "accepted_run_rows_fingerprint_schema": "accepted_run_rows_fingerprint.v1",
            "accepted_run_rows_fingerprint": accepted_run_rows_fingerprint(fixture.accepted_run_rows),
            "desktop_queue_snapshot_fallback_used": False,
            "desktop_queue_snapshot_fallback_reason": "",
            "pending_publish_index_health": {"status": "ready"},
            "pending_publish_backpressure": {"blocked": False},
        }
    )
    _write_json_atomic(queue_snapshot_path, snapshot)
    fixture.resolved = resolved
    return fixture


def _monitor_evidence(
    timestamp: str,
    source: str,
    provenance: str = "backend_confirmed",
) -> dict[str, Any]:
    return {"source": source, "provenance": provenance, "recorded_at": timestamp}


def _monitor_progress(
    kind: str = "none",
    *,
    numerator: int | None = None,
    denominator: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": kind}
    if numerator is not None:
        payload["numerator"] = numerator
    if denominator is not None:
        payload["denominator"] = denominator
    return payload


def _monitor_route(
    timestamp: str,
    state: str,
    *,
    route: str = "",
    reason: str = "",
    reason_code: str = "",
    source: str = "run_monitor_state",
    provenance: str = "backend_confirmed",
) -> dict[str, Any]:
    return {
        "state": state,
        "route": route,
        "reason": reason,
        "reason_code": reason_code,
        "evidence": _monitor_evidence(timestamp, source, provenance),
    }


def _monitor_stages(
    timestamp: str,
    *,
    active_stage: str = "",
    terminal_state: str = "",
    no_subtitles: bool = False,
) -> list[dict[str, Any]]:
    active_index = RUN_MONITOR_STAGE_IDS.index(active_stage) if active_stage else -1
    review_index = RUN_MONITOR_STAGE_IDS.index("subtitles")
    rows: list[dict[str, Any]] = []
    for index, stage_id in enumerate(RUN_MONITOR_STAGE_IDS):
        state = "not_started"
        detail = "Awaiting exact backend evidence."
        if terminal_state == "completed":
            if no_subtitles and stage_id == "subtitles":
                state = "not_applicable"
                detail = "Backend policy confirms this accepted item has no subtitle tracks."
            else:
                state = "completed"
                detail = "Terminal artifact proves this stage complete."
        elif terminal_state == "review":
            if index < review_index:
                state = "completed"
                detail = "Backend stage evidence completed before review."
            elif index == review_index or stage_id == "final_evidence":
                state = "review"
                detail = "Subtitle conversion requires operator review."
            else:
                state = "skipped"
                detail = "Skipped because review stopped publication."
        elif active_index >= 0:
            if index < active_index:
                if no_subtitles and stage_id == "subtitles":
                    state = "not_applicable"
                    detail = "Backend policy confirms this accepted item has no subtitle tracks."
                else:
                    state = "completed"
                    detail = "Backend stage evidence completed."
            elif index == active_index:
                state = "active"
                detail = "Backend-confirmed active stage."
        elif stage_id == "accepted":
            state = "completed"
            detail = "Accepted into this exact Backend Queue run."
        terminal = state in {"completed", "skipped", "not_applicable", "blocked", "review", "failed"}
        rows.append(
            {
                "stage_id": stage_id,
                "state": state,
                "started_at": timestamp if state in {"active", "completed"} else "",
                "updated_at": timestamp if state != "not_started" else "",
                "completed_at": timestamp if terminal else "",
                "detail": detail,
                "reason_code": "fixture_review_required" if state == "review" else "",
                "progress": (
                    _monitor_progress("determinate", numerator=40, denominator=100)
                    if state == "active" and stage_id in {"copy_to_scratch", "transcode"}
                    else _monitor_progress("indeterminate")
                    if state == "active"
                    else _monitor_progress()
                ),
                "evidence": _monitor_evidence(
                    timestamp,
                    "engine_stage_ledger",
                    "engine_event" if state != "not_started" else "unknown",
                ),
            }
        )
    return rows


def _monitor_audio(
    timestamp: str,
    *,
    active: bool = False,
    completed: bool = False,
) -> dict[str, Any]:
    if not active and not completed:
        return {
            "state": "awaiting_evidence",
            "policy_final": False,
            "tracks": [],
            "evidence": _monitor_evidence(timestamp, "run_monitor_state", "unknown"),
        }
    track_state = "completed" if completed else "active"
    return {
        "state": "completed" if completed else "active",
        "policy_final": True,
        "tracks": [
            {
                "track_id": "audio:1",
                "stream_index": 1,
                "language": "eng",
                "source_codec": "aac",
                "source_channels": 6,
                "source_layout": "5.1",
                "planned_action": "passthrough",
                "current_action": "" if completed else "passthrough",
                "state": track_state,
                "started_at": timestamp,
                "updated_at": timestamp,
                "completed_at": timestamp if completed else "",
                "output_codec": "aac",
                "output_channels": 6,
                "output_layout": "5.1",
                "is_default": True,
                "reason_code": "profile_passthrough",
                "reason": "Backend profile preserves the source audio track.",
                "progress": _monitor_progress(),
                "result": "Passthrough written" if completed else "",
                "evidence": _monitor_evidence(timestamp, "audio_policy_ledger", "engine_event"),
            }
        ],
        "evidence": _monitor_evidence(timestamp, "audio_policy_ledger", "engine_event"),
    }


def _monitor_subtitles(
    timestamp: str,
    *,
    active: bool = False,
    review: bool = False,
    policy_known: bool = False,
) -> dict[str, Any]:
    if active:
        return {
            "state": "active",
            "policy_final": True,
            "tracks": [
                {
                    "track_id": "subtitle:2",
                    "stream_index": 2,
                    "source_ordinal": 0,
                    "language": "jpn",
                    "source_codec": "hdmv_pgs_subtitle",
                    "source_type": "image",
                    "source_kind": "embedded",
                    "preserve": True,
                    "extract": True,
                    "convert": True,
                    "ocr": True,
                    "write_embedded": True,
                    "write_sidecar": True,
                    "planned_action": "Preserve original and OCR preferred-language SRT",
                    "current_action": "OCR",
                    "state": "active",
                    "started_at": timestamp,
                    "updated_at": timestamp,
                    "completed_at": "",
                    "output_codec": "srt",
                    "output_location": "external_sidecar",
                    "output_path": "",
                    "parked_path": "",
                    "intended_final_path": "",
                    "reason_code": "preferred_language_ocr",
                    "reason": "The backend is OCRing this track while preserving the original.",
                    "progress": _monitor_progress("indeterminate"),
                    "result": "",
                    "evidence": _monitor_evidence(timestamp, "subtitle_ocr_progress", "engine_event"),
                }
            ],
            "evidence": _monitor_evidence(timestamp, "subtitle_policy_ledger", "engine_event"),
        }
    if not review and not policy_known:
        return {
            "state": "awaiting_evidence",
            "policy_final": False,
            "tracks": [],
            "evidence": _monitor_evidence(timestamp, "run_monitor_state", "unknown"),
        }
    if not review:
        return {
            "state": "not_applicable",
            "policy_final": True,
            "tracks": [],
            "evidence": _monitor_evidence(timestamp, "subtitle_policy_ledger", "engine_event"),
        }
    return {
        "state": "review",
        "policy_final": True,
        "tracks": [
            {
                "track_id": "subtitle:2",
                "stream_index": 2,
                "source_ordinal": 0,
                "language": "jpn",
                "source_codec": "hdmv_pgs_subtitle",
                "source_type": "image",
                "source_kind": "embedded",
                "preserve": True,
                "extract": True,
                "convert": True,
                "ocr": True,
                "write_embedded": True,
                "write_sidecar": True,
                "planned_action": "Preserve original and OCR preferred-language SRT",
                "current_action": "Review OCR failure",
                "state": "review",
                "started_at": timestamp,
                "updated_at": timestamp,
                "completed_at": timestamp,
                "output_codec": "srt",
                "output_location": "unknown",
                "output_path": "",
                "parked_path": "",
                "intended_final_path": "",
                "reason_code": "ocr_review_required",
                "reason": "OCR could not produce a trustworthy sidecar; the original subtitle remains preserved.",
                "progress": _monitor_progress(),
                "result": "Review required; publication blocked",
                "evidence": _monitor_evidence(timestamp, "failure_artifact", "terminal"),
            }
        ],
        "evidence": _monitor_evidence(timestamp, "failure_artifact", "terminal"),
    }


def _monitor_item(
    fixture: SimpleNamespace,
    *,
    run_id: str,
    position: int,
    lifecycle_state: str,
    timestamp: str,
    active_stage: str = "",
) -> dict[str, Any]:
    source = fixture.runnable_source_a if position == 1 else fixture.runnable_source_b
    planned_name = fixture.planned_name_a if position == 1 else fixture.planned_name_b
    planned_route = "remux" if position == 1 else "encode_hardware"
    planned_reason = (
        "Queue plan confirms direct-stream-compatible streams for Alpha."
        if position == 1
        else "Queue plan requests hardware encode for Beta."
    )
    runtime_available = lifecycle_state not in {"queued", "accepted"} and active_stage not in {"", "source_discovery", "copy_to_scratch", "probe", "route_decision"}
    executed_route = "remux" if position == 1 else "cpu_encode_fallback"
    executed_reason = (
        "Runtime stream mapping confirmed remux execution."
        if position == 1
        else "Backend runtime evidence confirmed CPU fallback after hardware initialization failed."
    )
    terminal_kind = "completed" if lifecycle_state == "completed" else "review" if lifecycle_state == "review" else ""
    final_available = bool(terminal_kind)
    if terminal_kind == "review":
        final_route = "cpu_encode_fallback"
        final_reason = "Failure artifact proves CPU fallback stopped at subtitle review before publication."
        final_source = "failure_artifact"
    else:
        final_route = "remux"
        final_reason = "Completed sidecar proves verified direct publication."
        final_source = "completed_sidecar"
    terminal = lifecycle_state in {"completed", "review"}
    audio_stage_index = RUN_MONITOR_STAGE_IDS.index("audio")
    subtitle_stage_index = RUN_MONITOR_STAGE_IDS.index("subtitles")
    active_stage_index = RUN_MONITOR_STAGE_IDS.index(active_stage) if active_stage else -1
    audio_completed = terminal or active_stage_index > audio_stage_index
    output_state = "published" if lifecycle_state == "completed" else "review" if lifecycle_state == "review" else "active" if lifecycle_state == "active" else "awaiting_evidence"
    output = {
        "state": output_state,
        "scratch_path": str(fixture.root / "Scratch" / run_id / f"item-{position}" / source.name),
        "working_output_path": str(fixture.root / "Scratch" / run_id / f"item-{position}" / "output.partial.mkv") if lifecycle_state == "active" else "",
        "published_path": str(fixture.output) if lifecycle_state == "completed" else "",
        "parked_path": "",
        "intended_final_path": str(fixture.output if position == 1 else fixture.output_root / "TV" / "Runnable Beta" / "Season 01" / planned_name),
        "size_bytes": fixture.output.stat().st_size if lifecycle_state == "completed" else None,
        "verification_state": "completed" if terminal else "active" if active_stage == "verification" else "not_started",
        "sidecars": (
            [
                {
                    "kind": "pipeline",
                    "state": "written",
                    "path": str(fixture.output_sidecar),
                    "reason": "Terminal pipeline evidence sidecar.",
                    "evidence": _monitor_evidence(timestamp, "completed_sidecar", "terminal"),
                }
            ]
            if lifecycle_state == "completed"
            else []
        ),
        "evidence": _monitor_evidence(
            timestamp,
            final_source if terminal else "output_ledger",
            "terminal" if terminal else "engine_event",
        ),
    }
    terminal_references: list[dict[str, Any]] = []
    failure = {
        "state": "none",
        "reason_code": "",
        "reason": "",
        "retryable": None,
        "reference": "",
        "evidence": _monitor_evidence(timestamp, "failure_ledger", "backend_confirmed"),
    }
    recovery = {
        "owner": "pipeline",
        "next_action": "Continue monitoring this accepted Backend Queue run.",
        "retryable": None,
        "evidence": _monitor_evidence(timestamp, "run_monitor_state", "backend_confirmed"),
    }
    if lifecycle_state == "completed":
        terminal_references.append(
            {
                "kind": "completed",
                "reference": "completed_jobs.jsonl#job-a",
                "path": str(fixture.output),
                "evidence": _monitor_evidence(timestamp, "completed_manifest", "terminal"),
            }
        )
        recovery.update({"next_action": "No action required.", "retryable": False})
    elif lifecycle_state == "review":
        terminal_references.append(
            {
                "kind": "review",
                "reference": "backend-queue-job-b.failure.json",
                "path": str(fixture.failure_report_path),
                "evidence": _monitor_evidence(timestamp, "failure_artifact", "terminal"),
            }
        )
        failure = {
            "state": "review",
            "reason_code": "ocr_review_required",
            "reason": "Subtitle OCR evidence was not trustworthy enough to publish.",
            "retryable": True,
            "reference": "backend-queue-job-b.failure.json",
            "evidence": _monitor_evidence(timestamp, "failure_artifact", "terminal"),
        }
        recovery = {
            "owner": "operator",
            "next_action": "Open Reports, review the preserved subtitle evidence, then retry when corrected.",
            "retryable": True,
            "evidence": _monitor_evidence(timestamp, "failure_artifact", "terminal"),
        }
    return {
        "job_id": _run_monitor_job_id(run_id, position),
        "source_identity": {"value": f"fixture-source-{position}", "algorithm": "source_identity_v2"},
        "source_path": str(source),
        "display_name": planned_name,
        "display_name_evidence": _monitor_evidence(timestamp, "plex_destination_plan.v1", "queue_plan"),
        "parent_context": str(source.parent),
        "position": position,
        "total": 2,
        "lifecycle_state": lifecycle_state,
        "lifecycle_evidence": _monitor_evidence(
            timestamp,
            final_source if terminal else "run_monitor_state",
            "terminal" if terminal else "backend_confirmed",
        ),
        "updated_at": timestamp,
        "routes": {
            "planned": _monitor_route(
                timestamp,
                "available",
                route=planned_route,
                reason=planned_reason,
                reason_code="fixture_backend_plan",
                source="queue_snapshot",
                provenance="queue_plan",
            ),
            "executed": _monitor_route(
                timestamp,
                "available" if runtime_available or final_available else "awaiting_evidence",
                route=executed_route if runtime_available or final_available else "",
                reason=executed_reason if runtime_available or final_available else "",
                reason_code="runtime_route_selected" if runtime_available or final_available else "",
                source="route_selected_event" if runtime_available or final_available else "run_monitor_state",
                provenance="engine_event" if runtime_available or final_available else "unknown",
            ),
            "final": _monitor_route(
                timestamp,
                "available" if final_available else "awaiting_evidence",
                route=final_route if final_available else "",
                reason=final_reason if final_available else "",
                reason_code="terminal_route_proof" if final_available else "",
                source=final_source if final_available else "run_monitor_state",
                provenance="terminal" if final_available else "unknown",
            ),
        },
        "stages": _monitor_stages(
            timestamp,
            active_stage=active_stage,
            terminal_state=terminal_kind,
            no_subtitles=position == 1,
        ),
        "audio": _monitor_audio(
            timestamp,
            active=active_stage == "audio",
            completed=audio_completed,
        ),
        "subtitles": _monitor_subtitles(
            timestamp,
            active=active_stage == "subtitles",
            review=lifecycle_state == "review",
            policy_known=terminal or active_stage_index > subtitle_stage_index,
        ),
        "output": output,
        "terminal_references": terminal_references,
        "failure": failure,
        "recovery": recovery,
    }


def _monitor_worker(
    timestamp: str,
    *,
    run_id: str,
    position: int,
    worker_id: str,
    stage_id: str,
    route: str = "",
) -> dict[str, Any]:
    return {
        "worker_id": worker_id,
        "run_id": run_id,
        "job_id": _run_monitor_job_id(run_id, position),
        "state": "active",
        "stage_id": stage_id,
        "route": route,
        "progress": _monitor_progress("determinate", numerator=40, denominator=100),
        "updated_at": timestamp,
        "evidence": _monitor_evidence(timestamp, "worker_heartbeat", "worker_heartbeat"),
    }


def _run_monitor_job_id(run_id: str, position: int) -> str:
    return f"{run_id}-item-{position:08d}"


class _RunMonitorJourney:
    def __init__(
        self,
        fixture: SimpleNamespace,
        *,
        run_id: str,
        command_id: str,
        accepted_queue_fingerprint: str,
    ) -> None:
        self.fixture = fixture
        self.run_id = run_id
        self.command_id = command_id
        self.accepted_queue_fingerprint = accepted_queue_fingerprint
        self.store = RunMonitorStore(fixture.state_root)
        self._lock = threading.Lock()
        self._index = 0
        self._reads = 0
        self._reads_per_state = 4
        self.terminal_seen = threading.Event()
        self.state_names = ["starting", "scanning", "multi_worker", "handoff", "review", "completed"]
        self.seed_record = self.store.read(run_id)
        self._sequence_base = int(self.seed_record.write_sequence) if self.seed_record is not None else 1
        self.started_at = self.seed_record.run.started_at if self.seed_record is not None else _utc_now()
        if self.seed_record is None:
            self._write_state(0)
        else:
            expected_membership = [
                (
                    _run_monitor_job_id(run_id, position),
                    row["source_identity"],
                    row["source_identity_algorithm"],
                    row["source_path"],
                    row["run_queue_index"],
                    row["run_queue_total"],
                )
                for position, row in enumerate(self.fixture.accepted_run_rows, start=1)
            ]
            actual_membership = [
                (
                    item.job_id,
                    item.source_identity.value,
                    item.source_identity.algorithm,
                    item.source_path,
                    item.position,
                    item.total,
                )
                for item in self.seed_record.items
            ]
            if self.seed_record.run.accepted_queue.fingerprint != accepted_queue_fingerprint:
                raise AssertionError("pre-spawn Run Monitor seed did not preserve the accepted Queue fingerprint")
            if actual_membership != expected_membership:
                raise AssertionError(
                    "pre-spawn Run Monitor seed did not preserve exact uncapped accepted membership: "
                    f"{actual_membership!r}"
                )

    def _ensure_completed_artifact(self) -> None:
        if self.fixture.output.is_file() and self.fixture.output_sidecar.is_file():
            return
        self.fixture.output.parent.mkdir(parents=True, exist_ok=True)
        self.fixture.output.write_bytes(b"test-only-completed-output-fixture")
        _write_json_atomic(
            self.fixture.output_sidecar,
            {
                "schema_version": "pipeline_sidecar.v1",
                "source_path": str(self.fixture.runnable_source_a),
                "output_path": str(self.fixture.output),
                "route": "remux",
                "route_reason_code": "h264_direct_stream_safe",
                "fixture_only": True,
                "run_id": self.run_id,
                "job_id": _run_monitor_job_id(self.run_id, 1),
            },
        )
        completed_record = {
            "source_path": str(self.fixture.runnable_source_a),
            "output_path": str(self.fixture.output),
            "sidecar_path": str(self.fixture.output_sidecar),
            "route": "remux",
            "route_reason": "Deterministic test-only Backend Queue handoff.",
            "route_reason_code": "h264_direct_stream_safe",
            "encoder": "copy",
            "audio_summary": "fixture passthrough",
            "subtitle_summary": "fixture has no subtitle tracks",
            "source_size": self.fixture.runnable_source_a.stat().st_size,
            "output_size": self.fixture.output.stat().st_size,
            "encoded_at": _utc_now(),
            "elapsed_seconds": 0,
            "publish_state": "published",
            "run_id": self.run_id,
            "job_id": _run_monitor_job_id(self.run_id, 1),
        }
        _write_text_atomic(
            self.fixture.completed_manifest_path,
            json.dumps(completed_record, ensure_ascii=False, sort_keys=True) + "\n",
        )

    def _ensure_review_artifact(self) -> None:
        if self.fixture.failure_report_path.is_file():
            return
        _write_json_atomic(
            self.fixture.failure_report_path,
            {
                "schema_version": "pipeline_failure.v1",
                "run_id": self.run_id,
                "job_id": _run_monitor_job_id(self.run_id, 2),
                "source_path": str(self.fixture.runnable_source_b),
                "status": "review",
                "reason_code": "ocr_review_required",
                "reason": "Subtitle OCR evidence was not trustworthy enough to publish.",
                "retryable": True,
                "recovery_owner": "operator",
                "next_action": "Review preserved subtitle evidence before retrying.",
                "created_at": _utc_now(),
            },
        )

    def _record_for(self, index: int) -> RunMonitorRecord:
        timestamp = _utc_now()
        if index == 0:
            run_state = "starting"
            items = [
                _monitor_item(self.fixture, run_id=self.run_id, position=1, lifecycle_state="queued", timestamp=timestamp),
                _monitor_item(self.fixture, run_id=self.run_id, position=2, lifecycle_state="queued", timestamp=timestamp),
            ]
            workers: list[dict[str, Any]] = []
        elif index == 1:
            run_state = "scanning"
            items = [
                _monitor_item(self.fixture, run_id=self.run_id, position=1, lifecycle_state="active", timestamp=timestamp, active_stage="source_discovery"),
                _monitor_item(self.fixture, run_id=self.run_id, position=2, lifecycle_state="queued", timestamp=timestamp),
            ]
            workers = [
                _monitor_worker(timestamp, run_id=self.run_id, position=1, worker_id="local-worker-a", stage_id="source_discovery")
            ]
        elif index == 2:
            run_state = "running"
            items = [
                _monitor_item(self.fixture, run_id=self.run_id, position=1, lifecycle_state="active", timestamp=timestamp, active_stage="transcode"),
                _monitor_item(self.fixture, run_id=self.run_id, position=2, lifecycle_state="active", timestamp=timestamp, active_stage="audio"),
            ]
            workers = [
                _monitor_worker(timestamp, run_id=self.run_id, position=1, worker_id="local-worker-a", stage_id="transcode", route="remux"),
                _monitor_worker(timestamp, run_id=self.run_id, position=2, worker_id="local-worker-b", stage_id="audio", route="cpu_encode_fallback"),
            ]
        elif index == 3:
            run_state = "running"
            items = [
                _monitor_item(self.fixture, run_id=self.run_id, position=1, lifecycle_state="completed", timestamp=timestamp),
                _monitor_item(self.fixture, run_id=self.run_id, position=2, lifecycle_state="active", timestamp=timestamp, active_stage="subtitles"),
            ]
            workers = [
                _monitor_worker(timestamp, run_id=self.run_id, position=2, worker_id="local-worker-b", stage_id="subtitles", route="cpu_encode_fallback")
            ]
        else:
            run_state = "completed" if index == 5 else "running"
            items = [
                _monitor_item(self.fixture, run_id=self.run_id, position=1, lifecycle_state="completed", timestamp=timestamp),
                _monitor_item(self.fixture, run_id=self.run_id, position=2, lifecycle_state="review", timestamp=timestamp),
            ]
            workers = []
        counts = {
            "accepted": 2,
            **{
                state: sum(1 for item in items if item["lifecycle_state"] == state)
                for state in ("queued", "active", "completed", "failed", "skipped", "blocked", "review", "parked", "stopped")
            },
        }
        terminal = run_state == "completed"
        payload = {
            "schema_version": "pipeline_run_monitor.v1",
            "write_sequence": self._sequence_base + index,
            "run": {
                "run_id": self.run_id,
                "command_id": self.command_id,
                "mode": "once",
                "scope": "backend_queue",
                "accepted_queue": {
                    "schema_version": "queue_plan_fingerprint.v1",
                    "fingerprint": self.accepted_queue_fingerprint,
                    "accepted_count": 2,
                },
                "lifecycle_state": run_state,
                "started_at": self.started_at,
                "updated_at": timestamp,
                "ended_at": timestamp if terminal else "",
                "stop_after_current": {
                    "state": "not_requested",
                    "requested_at": "",
                    "evidence": _monitor_evidence(timestamp, "control_flag_state", "backend_confirmed"),
                },
                "outcome": (
                    {
                        "state": "completed",
                        "reason_code": "run_complete_with_review",
                        "reason": "Every accepted item reached terminal evidence; one item requires review.",
                        "retryable": True,
                        "owner": "operator",
                        "next_action": "Open Reports for the review item; the completed output needs no action.",
                        "evidence": _monitor_evidence(timestamp, "run_monitor_manifest", "terminal"),
                    }
                    if terminal
                    else {
                        "state": "pending",
                        "reason_code": "run_active",
                        "reason": "Backend Queue work remains active.",
                        "retryable": None,
                        "owner": "pipeline",
                        "next_action": "Continue monitoring Current Work.",
                        "evidence": _monitor_evidence(timestamp, "run_monitor_state", "backend_confirmed"),
                    }
                ),
                "counts": counts,
                "evidence": _monitor_evidence(timestamp, "run_monitor_manifest", "backend_confirmed"),
            },
            "items": items,
            "current_workers": workers,
        }
        return RunMonitorRecord.model_validate(payload)

    def _write_state(self, index: int) -> None:
        if index >= 3:
            self._ensure_completed_artifact()
        if index >= 4:
            self._ensure_review_artifact()
        self.store.write(self._record_for(index))

    def serve(self, reader: Any, resolved: object, *, run_id: str = "") -> dict[str, object]:
        with self._lock:
            current_index = self._index
            result = reader(resolved, run_id=run_id)
            self._reads += 1
            if current_index == len(self.state_names) - 1:
                self.terminal_seen.set()
            elif self._reads >= self._reads_per_state:
                self._index += 1
                self._reads = 0
                self._write_state(self._index)
            return result


class _StatefulFakeProcess(DummyProc):
    def __init__(self) -> None:
        super().__init__(os.getpid())
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def finish(self, *, outcome: str) -> None:
        self.returncode = 0 if outcome == "completed" else 1
        lease = getattr(self, "_mediapipeline_lifecycle_lease", None)
        if lease is not None:
            lease.release(outcome=outcome)


class _StatefulQueueCompletionService(DummyWorkflowFacadeService):
    def __init__(self, fixture: SimpleNamespace) -> None:
        super().__init__(fixture.root)
        self.fixture = fixture
        self.start_calls: list[dict[str, Any]] = []
        self.fake_processes: list[_StatefulFakeProcess] = []
        self.real_pipeline_child_launch_count = 0
        self.media_tool_invocations: list[str] = []
        self.network_worker_launch_count = 0
        self.started = threading.Event()
        self.completed = threading.Event()
        self.cancel = threading.Event()
        self.runner_failure: BaseException | None = None
        self.runner_thread: threading.Thread | None = None
        self.monitor_journey: _RunMonitorJourney | None = None
        self.accepted_run_rows_at_start: list[dict[str, Any]] = []

    def cleanup_stale_launch_guards(self, _resolved_arg: object) -> list[str]:
        return []

    def find_related_pipeline_processes(self, _resolved_arg: object, **_kwargs: object) -> list[object]:
        return []

    def is_progress_stale(self, _progress: dict[str, Any]) -> bool:
        return False

    def is_audit_progress_stale(self, _progress: dict[str, Any]) -> bool:
        return True

    def read_queue_scan_status(self, _resolved_arg: object) -> dict[str, Any]:
        return {
            "schema_version": "desktop_queue_scan_status.v1",
            "status": "completed",
            "phase": "complete",
            "mode": "full",
            "queue_preview_request_id": self.fixture.queue_preview_request_id,
        }

    def read_progress(self, _resolved_arg: object) -> dict[str, Any]:
        return json.loads(self.fixture.progress_path.read_text(encoding="utf-8"))

    def read_audit_progress(self, _resolved_arg: object) -> dict[str, Any]:
        return {}

    def build_snapshot(self, resolved: object, audit_root: str) -> Snapshot:
        _ = audit_root
        progress = self.read_progress(resolved)
        active = str(progress.get("CurrentStage") or "").casefold() not in {
            "",
            "completed",
            "idle",
            "stopped",
        }
        events: list[dict[str, Any]] = []
        if self.fixture.event_file.exists():
            for line in self.fixture.event_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        return Snapshot(
            resolved=resolved,
            current_activity=(
                "Test-only queue completion runner is active."
                if active
                else "Test-only queue completion runner is idle."
            ),
            status_summary="Processing one fixture row." if active else "Fixture queue handoff complete.",
            log_tail="",
            progress=progress,
            audit_progress=None,
            latest_failure_report=None,
            latest_failure_json=None,
            latest_audit_csv=None,
            latest_priority_csv=None,
            pipeline_events=events,
        )

    def start_pipeline(
        self,
        resolved: object,
        mode: str,
        show_config: bool,
        sleep_seconds: int,
        extra_args: str,
        show_console: bool,
        single_file: str | None = None,
        extra_argv: list[str] | tuple[str, ...] | None = None,
        expected_queue_plan_fingerprint: str = "",
        command_id: str = "",
        run_id: str = "",
    ) -> _StatefulFakeProcess:
        if self.start_calls:
            raise AssertionError("test-only pipeline runner was invoked more than once")
        if mode != "once":
            raise AssertionError(f"test-only pipeline runner expected once mode, got {mode!r}")
        if single_file:
            raise AssertionError(f"Backend Queue runner received an unexpected Single File: {single_file!r}")
        if expected_queue_plan_fingerprint != self.fixture.queue_plan_fingerprint:
            raise AssertionError(
                "Backend Queue runner received the wrong accepted queue fingerprint: "
                f"{expected_queue_plan_fingerprint!r}"
            )
        if len(run_id) != 32 or any(character not in "0123456789abcdef" for character in run_id):
            raise AssertionError(f"Backend Queue runner received an invalid run identity: {run_id!r}")
        if not command_id:
            raise AssertionError("Backend Queue runner did not receive the command correlation identity")
        queue_snapshot = json.loads(self.fixture.queue_snapshot_path.read_text(encoding="utf-8"))
        accepted_run_rows = queue_snapshot.get("accepted_run_rows")
        if not isinstance(accepted_run_rows, list) or accepted_run_rows != self.fixture.accepted_run_rows:
            raise AssertionError(
                "Backend Queue runner did not retain the exact uncapped accepted pre-scan membership: "
                f"{accepted_run_rows!r}"
            )
        self.accepted_run_rows_at_start = [dict(row) for row in accepted_run_rows]
        self.start_calls.append(
            {
                "resolved": resolved,
                "mode": mode,
                "show_config": show_config,
                "sleep_seconds": sleep_seconds,
                "extra_args": extra_args,
                "show_console": show_console,
                "single_file": single_file,
                "extra_argv": list(extra_argv or []),
                "expected_queue_plan_fingerprint": expected_queue_plan_fingerprint,
                "command_id": command_id,
                "run_id": run_id,
            }
        )
        self.monitor_journey = _RunMonitorJourney(
            self.fixture,
            run_id=run_id,
            command_id=command_id,
            accepted_queue_fingerprint=expected_queue_plan_fingerprint,
        )
        assert self.fixture.resolved.active_jobs_path is not None
        self.fixture.active_job_path = self.fixture.resolved.active_jobs_path / "browser-backend-queue-run.json"
        _write_json_atomic(
            self.fixture.active_job_path,
            {
                "schema_version": "desktop_active_job.v1",
                "launch_id": "browser-backend-queue-run",
                "job_kind": "pipeline",
                "mode": "once",
                "status": "active",
                "pid": os.getpid(),
                "metadata": {"run_id": run_id},
            },
        )
        process = _StatefulFakeProcess()
        self.fake_processes.append(process)
        _write_json_atomic(
            self.fixture.progress_path,
            {
                "ProgressVersion": 2,
                "Status": "Processing",
                "CurrentStage": "scanning",
                "CurrentFile": "Uncorrelated Legacy Worker Route.mkv",
                "CurrentFileDisplay": "Uncorrelated Legacy Worker Route.mkv",
                "CurrentRoute": "encode",
                "CurrentQueueIndex": 0,
                "CurrentQueueTotal": 2,
                "TotalProcessed": 0,
                "Remuxed": 0,
                "Encoded": 0,
                "Failed": 0,
                "UpdatedAt": _utc_now(),
            },
        )
        self.started.set()
        self.runner_thread = threading.Thread(
            target=self._finish_after_duplicate_is_journaled,
            args=(process,),
            name="QueueLaunchCompletedFakeRunner",
            daemon=True,
        )
        self.runner_thread.start()
        return process

    def _pipeline_start_outcome_journal_entries(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.fixture.command_journal_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return []
        return [
            entry
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("command") == "pipeline.start"
            and isinstance(entry.get("data"), dict)
            and entry["data"].get("evidence_phase") in {"running", "rejected"}
        ]

    def _wait_for_duplicate_journal(self) -> None:
        deadline = time.monotonic() + 25.0
        while time.monotonic() < deadline:
            outcomes = self._pipeline_start_outcome_journal_entries()
            if len(outcomes) >= 2 and any(entry.get("ok") is True for entry in outcomes) and any(
                entry.get("ok") is False for entry in outcomes
            ):
                return
            if self.cancel.wait(0.025):
                raise RuntimeError("test-only queue completion runner canceled")
        raise TimeoutError("duplicate pipeline start was not durably journaled before fake completion")

    def _finish_after_duplicate_is_journaled(self, process: _StatefulFakeProcess) -> None:
        try:
            self._wait_for_duplicate_journal()
            if self.monitor_journey is None or not self.monitor_journey.terminal_seen.wait(timeout=35.0):
                raise TimeoutError("browser did not observe the complete backend Run Monitor journey")
            _write_json_atomic(
                self.fixture.queue_snapshot_path,
                _queue_snapshot_payload(self.fixture, completed=True),
            )
            event = {
                "schema_version": "pipeline_event.v1",
                "event_id": "fixture-backend-queue-job-a-completed",
                "event_type": "job_completed",
                "timestamp": _utc_now(),
                "created_at": _utc_now(),
                "stage": "publish-verification",
                "route": "remux",
                "status": "completed",
                "source_path": str(self.fixture.runnable_source),
                "run_id": self.monitor_journey.run_id,
                "job_id": _run_monitor_job_id(self.monitor_journey.run_id, 1),
                "data": {
                    "success": True,
                    "completion_status": "completed",
                    "queue_terminal": True,
                    "output_path": str(self.fixture.output),
                    "sidecar_path": str(self.fixture.output_sidecar),
                },
            }
            _write_text_atomic(
                self.fixture.event_file,
                json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            )
            _write_json_atomic(
                self.fixture.progress_path,
                {
                    "ProgressVersion": 2,
                    "Status": "Idle",
                    "CurrentStage": "idle",
                    "CurrentFile": "",
                    "CurrentFileDisplay": "",
                    "CurrentQueueIndex": 0,
                    "CurrentQueueTotal": 2,
                    "TotalProcessed": 2,
                    "Remuxed": 1,
                    "Encoded": 0,
                    "Failed": 1,
                    "UpdatedAt": _utc_now(),
                },
            )
            _write_json_atomic(
                self.fixture.active_job_path,
                {
                    "schema_version": "desktop_active_job.v1",
                    "launch_id": "browser-backend-queue-run",
                    "job_kind": "pipeline",
                    "mode": "once",
                    "status": "completed",
                    "pid": os.getpid(),
                    "metadata": {"run_id": self.monitor_journey.run_id},
                },
            )
            process.finish(outcome="completed")
            self.completed.set()
        except BaseException as exc:  # surfaced by the owning unittest
            self.runner_failure = exc
            try:
                process.finish(outcome="failed")
            finally:
                self.completed.set()

    def stop_fake_runner(self) -> None:
        self.cancel.set()
        thread = self.runner_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)


def _browser_queue_launch_completed_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function queueLaunchCompletedScript() {
          return `
          (async () => {
            const posts = [];
            const runMonitorGets = [];
            const api = window.mediaPipelineApi;
            const originalApiPost = api.apiPost;
            const originalWindowApiGet = window.apiGet;
            window.apiGet = async (path, options) => {
              const result = await originalWindowApiGet(path, options);
              if (String(path || "").startsWith("/api/run-monitor")) runMonitorGets.push(String(path));
              return result;
            };
            api.apiPost = async (path, body, options) => {
              const result = await originalApiPost(path, body, options);
              posts.push({
                path: String(path || ""),
                body: body || {},
                ok: result?.ok === true,
                command: result?.command || "",
                message: result?.message || "",
                evidencePhase: result?.data?.evidence_phase || "",
                runId: result?.data?.run_id || "",
                acceptedQueueFingerprint: result?.data?.accepted_queue_fingerprint || "",
                runMonitor: result?.data?.run_monitor || null,
              });
              return result;
            };
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function tableText(id) { const node = byId(id); return node ? node.innerText || node.textContent || "" : ""; }
            function activePage() { return document.querySelector("[data-page-panel].is-visible")?.dataset.pagePanel || ""; }
            function setInput(id, value) {
              const input = byId(id);
              if (!input) throw new Error("missing input " + id);
              input.value = value;
              input.dispatchEvent(new Event("input", { bubbles: true }));
              input.dispatchEvent(new Event("change", { bubbles: true }));
            }
            async function waitFor(predicate, label, detail = () => "") {
              const deadline = Date.now() + 30000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (await predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label
                + (lastError ? ": " + lastError.message : "")
                + "\\nState:\\n" + detail());
            }
            function clickRow(tbodyId, fragment) {
              const row = Array.from(byId(tbodyId)?.querySelectorAll("tr") || [])
                .find((candidate) => (candidate.innerText || candidate.textContent || "").includes(fragment));
              if (!row) throw new Error(tbodyId + " missing row " + fragment + "\\n" + tableText(tbodyId));
              row.click();
              return row;
            }
            const announcements = [];
            function captureAnnouncement() {
              const value = text("run-monitor-announcer").trim();
              if (value && announcements[announcements.length - 1] !== value) announcements.push(value);
            }
            async function waitForMonitor(label, predicate) {
              const deadline = Date.now() + 30000;
              let lastPayload = null;
              while (Date.now() < deadline) {
                lastPayload = await window.mediaPipelineRunMonitor.refresh({ automatic: false });
                await new Promise((resolve) => setTimeout(resolve, 35));
                captureAnnouncement();
                if (predicate(lastPayload)) return lastPayload;
              }
              throw new Error("Timed out waiting for Run Monitor " + label + "\\n" + [
                "state=" + text("run-monitor-state"),
                "freshness=" + text("run-monitor-freshness"),
                "items=" + tableText("run-monitor-items"),
                "workers=" + tableText("run-monitor-workers"),
                "detail=" + tableText("run-monitor-detail"),
                "payload=" + JSON.stringify(lastPayload),
              ].join("\\n\\n"));
            }
            try {
              window.showPage("queue");
              await waitFor(
                () => tableText("queue-rows").includes("[SubsPlease] Runnable.Alpha.S01E01.1080p.WEB-DL.x265-GROUP.mkv")
                  && tableText("queue-rows").includes("[Judas] Runnable.Beta.S01E01.1080p.BluRay.x264.mkv")
                  && tableText("queue-rows").includes("Blocked Show S01E02 Needs Review.mkv")
                  && tableText("queue-excluded-rows").includes("Excluded Show S01E03 Held.mkv"),
                "initial accepted Backend Queue plan, blocked row, and excluded row",
                () => [tableText("queue-rows"), tableText("queue-excluded-rows")].join("\\n\\n"),
              );
              const queueHeaders = Array.from(byId("queue-rows")?.closest("table")?.querySelectorAll("thead th") || []).map((node) => node.textContent.trim()).join(" | ");
              if (!queueHeaders.includes("Planned route") || !queueHeaders.includes("Planned reason")) {
                throw new Error("Queue predictive evidence was not explicitly labelled planned: " + queueHeaders);
              }
              const queueLoadedIdleSnapshot = await api.apiGet("/api/snapshot");
              const unloadedMonitor = await api.apiGet("/api/run-monitor");
              if (queueLoadedIdleSnapshot?.pipeline_state !== "idle") {
                throw new Error("Queue-loaded pre-launch state was not backend-confirmed idle: " + JSON.stringify(queueLoadedIdleSnapshot));
              }
              const unrelatedCompletion = (queueLoadedIdleSnapshot?.recent_events || []).find((event) => (
                event?.event_type === "job_completed"
                && event?.run_id === "ffffffffffffffffffffffffffffffff"
                && event?.job_id === "ffffffffffffffffffffffffffffffff-item-00000001"
              ));
              if (!unrelatedCompletion) {
                throw new Error("Fixture did not expose the recent uncorrelated job_completed event needed by this regression: " + JSON.stringify(queueLoadedIdleSnapshot?.recent_events));
              }
              if (unloadedMonitor?.run?.run_id
                  || (unloadedMonitor?.items || []).length !== 0
                  || (unloadedMonitor?.current_workers || []).length !== 0
                  || !["unavailable", "unknown"].includes(String(unloadedMonitor?.freshness?.state || ""))) {
                throw new Error("Queue-loaded idle state exposed active run/current claims before Start: " + JSON.stringify(unloadedMonitor));
              }
              clickRow("queue-rows", "[SubsPlease] Runnable.Alpha.S01E01");
              const selected = window.mediaPipelineQueueView.getSelectedQueueRow();
              if (!selected || !String(selected.source_path || "").includes("[SubsPlease] Runnable.Alpha.S01E01")) {
                throw new Error("runnable Queue row selection did not become selected-row context: " + JSON.stringify(selected));
              }
              clickRow("queue-launch-decision-rows", "Selected row");
              if (!text("queue-launch-decision-detail").includes("Queue-to-Launch handoff:")) {
                throw new Error("Queue handoff checkpoint detail did not render after selection.");
              }

              window.showPage("launch");
              window.mediaPipelineLaunchView.activateLaunchTab("pipeline", { persist: false });
              const backendQueuePreset = document.querySelector('[data-pipeline-scope-preset="queue"]');
              if (!backendQueuePreset) throw new Error("missing Launch Backend Queue scope preset");
              backendQueuePreset.click();
              setInput("pipeline-start-mode", "once");
              setInput("pipeline-start-sleep", "1");
              setInput("pipeline-start-schedule-override", "");
              setInput("pipeline-start-single-file", "");
              await window.mediaPipelineLaunchView.refreshLaunchBackendPreflight();
              window.mediaPipelineLaunchView.updateLaunchCommandButtonStates(
                { pipeline_state: "idle", progress: { Status: "Completed", CurrentStage: "completed" } },
                { safe_to_close: true, active_work: false, state: "completed" },
              );
              await waitFor(
                () => {
                  const button = byId("pipeline-start-button");
                  return Boolean(button && !button.disabled);
                },
                "enabled Backend Queue Start button",
                () => [text("pipeline-start-disabled-reason"), text("launch-backend-preflight-summary")].join("\\n\\n"),
              );
              byId("pipeline-start-button").click();
              await waitFor(
                () => posts.some((post) => post.path === "/api/pipeline/start" && post.ok),
                "successful pipeline start POST",
                () => JSON.stringify(posts),
              );
              const successful = posts.find((post) => post.path === "/api/pipeline/start" && post.ok);
              const duplicate = await originalApiPost("/api/pipeline/start", successful.body);
              posts.push({
                path: "/api/pipeline/start",
                body: successful.body,
                ok: duplicate?.ok === true,
                command: duplicate?.command || "",
                message: duplicate?.message || "",
                evidencePhase: duplicate?.data?.evidence_phase || "",
                runId: duplicate?.data?.run_id || "",
                acceptedQueueFingerprint: duplicate?.data?.accepted_queue_fingerprint || "",
                runMonitor: duplicate?.data?.run_monitor || null,
              });
              if (duplicate?.ok === true) {
                throw new Error("duplicate pipeline start was accepted: " + JSON.stringify(duplicate));
              }
              if (!String(duplicate?.message || "").toLowerCase().includes("lifecycle")) {
                throw new Error("duplicate pipeline start was not rejected by durable lifecycle guard: " + JSON.stringify(duplicate));
              }

              if (successful.body.mode !== "once" || String(successful.body.single_file || "") !== "") {
                throw new Error("standard journey did not submit mode=once with a blank Single File: " + JSON.stringify(successful.body));
              }
              if (!successful.runId || successful.runMonitor?.run_id !== successful.runId) {
                throw new Error("launch response did not expose one stable Run Monitor identity: " + JSON.stringify(successful));
              }
              if (successful.runMonitor?.route !== "/api/run-monitor"
                  || successful.runMonitor?.acceptance_state !== "backend_accepted"
                  || successful.runMonitor?.expected_queue?.fingerprint !== successful.acceptedQueueFingerprint) {
                throw new Error("launch response did not correlate the accepted Backend Queue fingerprint: " + JSON.stringify(successful));
              }
              await waitFor(
                () => activePage() === "home" && document.activeElement === byId("current-work-heading"),
                "launch navigation to the focused Current Work heading",
                () => "page=" + activePage() + "; focus=" + (document.activeElement?.id || document.activeElement?.tagName || "none"),
              );

              const starting = await waitForMonitor("starting accepted workload", () => (
                text("run-monitor-state").includes("Starting")
                && text("run-monitor-mode") === "Run Once · Backend Queue"
                && text("run-monitor-freshness") === "Backend-confirmed current"
              ));
              if (starting.run?.accepted_queue?.fingerprint !== successful.acceptedQueueFingerprint || starting.items?.length !== 2) {
                throw new Error("starting monitor did not preserve the exact accepted plan: " + JSON.stringify(starting));
              }
              const preScanIdentities = starting.items.map((item) => ({
                value: item?.source_identity?.value || "",
                algorithm: item?.source_identity?.algorithm || "",
                sourcePath: item?.source_path || "",
                position: item?.position || 0,
                total: item?.total || 0,
              }));
              if (JSON.stringify(preScanIdentities.map((item) => [item.value, item.algorithm, item.position, item.total]))
                  !== JSON.stringify([
                    ["fixture-source-1", "source_identity_v2", 1, 2],
                    ["fixture-source-2", "source_identity_v2", 2, 2],
                  ])
                  || !preScanIdentities[0].sourcePath.includes("Runnable Alpha")
                  || !preScanIdentities[1].sourcePath.includes("Runnable Beta")) {
                throw new Error("starting monitor did not preserve exact uncapped pre-scan identities/positions: " + JSON.stringify(preScanIdentities));
              }
              const workloadToggle = byId("run-monitor-items-toggle");
              if (workloadToggle?.getAttribute("aria-expanded") !== "false"
                  || byId("run-monitor-items")?.querySelectorAll(".run-monitor-item-preview").length !== 2
                  || byId("run-monitor-items")?.querySelector("button")
                  || !tableText("run-monitor-items").includes("Runnable Alpha - S01E01.mkv")
                  || !tableText("run-monitor-items").includes("Runnable Beta - S01E01.mkv")
                  || tableText("run-monitor-items").includes("[SubsPlease]")
                  || tableText("run-monitor-items").includes("[Judas]")
                  || !text("run-monitor-items-help").includes("verified backend production naming plan")) {
                throw new Error("accepted workload did not default to its folded filename-only preview:\\n" + tableText("run-monitor-items"));
              }
              workloadToggle.click();
              await new Promise((resolve) => setTimeout(resolve, 35));
              const acceptedButtons = Array.from(byId("run-monitor-items")?.querySelectorAll(".run-monitor-item-button") || []);
              if (workloadToggle.getAttribute("aria-expanded") !== "true"
                  || acceptedButtons.length !== 2
                  || !tableText("run-monitor-items").includes("Runnable Alpha - S01E01.mkv")
                  || !tableText("run-monitor-items").includes("Runnable Beta - S01E01.mkv")
                  || tableText("run-monitor-items").includes("[SubsPlease]")
                  || tableText("run-monitor-items").includes("[Judas]")
                  || !acceptedButtons[0].getAttribute("aria-label")?.includes("File 1 of 2")
                  || !acceptedButtons[1].getAttribute("aria-label")?.includes("File 2 of 2")) {
                throw new Error("opened accepted workload did not expose every exact selectable identity:\\n" + tableText("run-monitor-items"));
              }
              if (byId("run-monitor-items")?.querySelectorAll(".run-monitor-item").length !== 2) {
                throw new Error("accepted workload did not render every accepted item exactly once.");
              }
              const uncorrelatedCompletionChangedAuthority = starting.run?.lifecycle_state !== "starting"
                || starting.items.some((item) => (
                  !["accepted", "queued"].includes(String(item?.lifecycle_state || ""))
                  || item?.routes?.final?.state === "available"
                  || (item?.stages || []).some((stage) => stage?.stage_id === "final_evidence" && stage?.state === "completed")
                ));
              if (uncorrelatedCompletionChangedAuthority) {
                throw new Error("recent uncorrelated job_completed changed run/final evidence: " + JSON.stringify(starting));
              }

              const scanning = await waitForMonitor("scanning", () => (
                text("run-monitor-state").includes("Scanning")
                && tableText("run-monitor-stage-list").includes("Source discovery / scanning")
                && tableText("run-monitor-stage-list").includes("Active")
              ));
              if (scanning.current_workers?.length !== 1 || scanning.current_workers[0].job_id !== scanning.items[0].job_id) {
                throw new Error("scanning worker was not correlated to the exact accepted job: " + JSON.stringify(scanning.current_workers));
              }

              const multiWorker = await waitForMonitor("all active workers and runtime route evidence", () => (
                text("run-monitor-state").includes("Running")
                && text("run-monitor-workers-count") === "2 active"
                && tableText("run-monitor-workers").includes("Worker local-worker-a")
                && tableText("run-monitor-workers").includes("Worker local-worker-b")
              ));
              const jobA = multiWorker.items[0].job_id;
              const jobB = multiWorker.items[1].job_id;
              window.mediaPipelineRunMonitor.selectJob(jobB, { focusButton: true });
              await new Promise((resolve) => setTimeout(resolve, 35));
              const routeDetail = text("run-monitor-routes");
              for (const label of ["Planned route", "Planned reason", "Executed route", "Executed reason", "Final route", "Final reason"]) {
                if (!routeDetail.includes(label)) throw new Error("selected runtime route evidence missing label " + label + "\\n" + routeDetail);
              }
              for (const evidenceText of ["encode_hardware", "cpu_encode_fallback", "route_selected_event", "Awaiting backend evidence"]) {
                if (!routeDetail.includes(evidenceText)) throw new Error("selected runtime route evidence missing " + evidenceText + "\\n" + routeDetail);
              }
              const executedRouteCard = Array.from(byId("run-monitor-routes")?.querySelectorAll(".run-monitor-route-card") || [])
                .find((card) => card.querySelector("strong")?.textContent.trim() === "Executed route");
              const executedRouteValue = executedRouteCard?.children?.[1]?.textContent?.trim() || "";
              if (executedRouteValue !== "cpu_encode_fallback") {
                throw new Error("selected item did not show its exact runtime route evidence: " + executedRouteValue);
              }
              const activeWorkerText = tableText("run-monitor-workers");
              if (activeWorkerText.includes("Uncorrelated Legacy Worker Route.mkv")
                  || activeWorkerText.includes("Executed route: encode —")
                  || executedRouteValue === "encode") {
                throw new Error("generic legacy CurrentRoute=encode leaked into worker/item route authority: " + activeWorkerText + "\\n" + routeDetail);
              }
              const selectedBeforeRefresh = window.mediaPipelineRunMonitor.getSelectedJobId();
              if (selectedBeforeRefresh !== jobB || document.activeElement?.dataset?.runMonitorJobId !== jobB) {
                throw new Error("exact job selection/focus was not established before refresh.");
              }

              const handoff = await waitForMonitor("file A terminal while file B remains current", () => (
                tableText("run-monitor-items").includes("Completed")
                && tableText("run-monitor-items").includes("Current · Active")
                && text("run-monitor-workers-count") === "1 active"
              ));
              if (handoff.items.length !== 2 || handoff.items[0].job_id !== jobA || handoff.items[1].job_id !== jobB) {
                throw new Error("terminal handoff changed exact accepted membership or order: " + JSON.stringify(handoff.items));
              }
              if (window.mediaPipelineRunMonitor.getSelectedJobId() !== jobB || document.activeElement?.dataset?.runMonitorJobId !== jobB) {
                throw new Error("automatic refresh reset the selected/current file or keyboard focus.");
              }
              window.mediaPipelineRunMonitor.selectJob(jobA, { focusButton: true });
              await new Promise((resolve) => setTimeout(resolve, 35));
              const terminalRoute = text("run-monitor-routes");
              for (const proof of ["Final route", "Final reason", "remux", "Completed sidecar proves", "completed_sidecar"]) {
                if (!terminalRoute.includes(proof)) throw new Error("terminal route proof missing " + proof + "\\n" + terminalRoute);
              }
              if (!tableText("run-monitor-terminal-links").includes("Open Completed Output proof")) {
                throw new Error("completed accepted row did not expose its deep terminal proof link.");
              }
              const endKey = new KeyboardEvent("keydown", { key: "End", bubbles: true });
              byId("run-monitor-items").querySelector('[data-run-monitor-job-id="' + jobA + '"]').dispatchEvent(endKey);
              await new Promise((resolve) => setTimeout(resolve, 35));
              if (window.mediaPipelineRunMonitor.getSelectedJobId() !== jobB || document.activeElement?.dataset?.runMonitorJobId !== jobB) {
                throw new Error("End did not move conventional roving selection/focus to the last accepted job.");
              }
              const tabStops = Array.from(byId("run-monitor-items").querySelectorAll("button")).filter((button) => button.tabIndex === 0);
              if (tabStops.length !== 1) throw new Error("accepted workload exposed more than one row in the Tab order.");

              const review = await waitForMonitor("review-required terminal item", () => (
                tableText("run-monitor-items").includes("Review")
                && tableText("run-monitor-recovery").includes("OCR")
              ));
              const reviewRow = byId("run-monitor-items")?.querySelector('.run-monitor-item[data-state="review"]');
              if (!reviewRow || !reviewRow.textContent.includes("Review")) {
                throw new Error("review row lacked its non-color state cue.");
              }
              if (review.items.length !== 2 || review.items[1].job_id !== jobB) {
                throw new Error("review transition dropped or text-matched the accepted job identity.");
              }
              for (const guidance of ["Failure state: Review", "Retryable: yes", "Owner: operator", "Open Reports"]) {
                if (!tableText("run-monitor-recovery").includes(guidance)) {
                  throw new Error("review recovery guidance missing " + guidance + "\\n" + tableText("run-monitor-recovery"));
                }
              }
              if (!tableText("run-monitor-terminal-links").includes("Open Reports proof")) {
                throw new Error("review item did not expose its Reports proof link.");
              }

              const terminal = await waitForMonitor("run complete", () => (
                text("run-monitor-state").includes("Completed")
                && text("run-monitor-freshness") === "Terminal backend evidence"
                && text("run-monitor-workers-count") === "0 active"
              ));
              if (terminal.items.length !== 2 || !text("run-monitor-outcome").includes("Every accepted item reached terminal evidence")) {
                throw new Error("run-complete summary did not preserve terminal workload/outcome: " + JSON.stringify(terminal));
              }
              const expectedMonitorRoute = "/api/run-monitor?run_id=" + encodeURIComponent(successful.runId);
              if (!runMonitorGets.includes(expectedMonitorRoute)
                  || runMonitorGets.some((route) => route.includes("?run_id=") && route !== expectedMonitorRoute)) {
                throw new Error("Current Work did not query the exact launch-confirmed run identity: " + JSON.stringify(runMonitorGets));
              }
              await new Promise((resolve) => setTimeout(resolve, 50));
              captureAnnouncement();
              if (!announcements.some((value) => value.includes("Current work changed"))) {
                throw new Error("semantic live region did not announce a new current file: " + JSON.stringify(announcements));
              }
              if (!announcements.some((value) => value.includes("is now review"))) {
                throw new Error("semantic live region did not announce the review transition: " + JSON.stringify(announcements));
              }
              if (!announcements.some((value) => value.includes("Run Once workload complete"))) {
                throw new Error("semantic live region did not announce run completion: " + JSON.stringify(announcements));
              }
              const announcementText = announcements.join(" ");
              if (!announcementText.includes("Runnable Alpha - S01E01.mkv")
                  || !announcementText.includes("Runnable Beta - S01E01.mkv")
                  || announcementText.includes("[SubsPlease]")
                  || announcementText.includes("[Judas]")) {
                throw new Error("semantic transitions must announce verified clean names, not raw release labels: " + JSON.stringify(announcements));
              }

              await waitFor(
                async () => {
                  await window.refreshAllNow();
                  window.showPage("queue");
                  const queue = tableText("queue-rows");
                  const excluded = tableText("queue-excluded-rows");
                  window.showPage("completed");
                  const completed = tableText("completed-rows") + "\\n" + tableText("completed-history-rows");
                  return !queue.includes("[SubsPlease] Runnable.Alpha.S01E01")
                    && !queue.includes("[Judas] Runnable.Beta.S01E01")
                    && queue.includes("Blocked Show S01E02 Needs Review.mkv")
                    && excluded.includes("Excluded Show S01E03 Held.mkv")
                    && completed.includes("Runnable Alpha - S01E01");
                },
                "persisted Backend Queue-to-Completed state transition",
                () => [
                  "page=" + activePage(),
                  "queue=" + tableText("queue-rows"),
                  "excluded=" + tableText("queue-excluded-rows"),
                  "completed=" + tableText("completed-rows"),
                  "completedHistory=" + tableText("completed-history-rows"),
                  "posts=" + JSON.stringify(posts),
                ].join("\\n\\n"),
              );
              const closeReadiness = await window.mediaPipelineApi.apiGet("/api/backend/close-readiness");
              if (closeReadiness?.safe_to_close !== true || closeReadiness?.active_work !== false) {
                throw new Error("backend did not return to safe close readiness: " + JSON.stringify(closeReadiness));
              }
              const idleSnapshot = await window.mediaPipelineApi.apiGet("/api/snapshot");
              if (idleSnapshot?.pipeline_state !== "idle") {
                throw new Error("backend did not return to fresh idle after durable run completion: " + JSON.stringify(idleSnapshot));
              }
              window.showPage("home");
              window.mediaPipelineRunMonitor.selectJob(jobA, { focusButton: true });
              await new Promise((resolve) => setTimeout(resolve, 35));
              if (window.mediaPipelineRunMonitor.getSelectedJobId() !== jobA
                  || document.activeElement?.dataset?.runMonitorJobId !== jobA) {
                throw new Error("terminal proof handoff was not anchored to exact job A selection/focus.");
              }
              const completedLink = byId("run-monitor-terminal-links").querySelector('[data-run-monitor-deep-link="completed"]');
              if (!completedLink) throw new Error("selected completed file lost its deep proof link.");
              const completedLinkLabel = completedLink.getAttribute("aria-label") || "";
              if (!completedLinkLabel.includes("completed_jobs.jsonl#job-a") || !completedLinkLabel.includes("Runnable Alpha")) {
                throw new Error("Completed proof link did not expose exact terminal reference/path identity: " + completedLinkLabel);
              }
              completedLink.click();
              await waitFor(
                () => activePage() === "completed"
                  && document.activeElement?.matches?.("#completed-rows tr[data-row-key], #completed-history-rows tr[data-row-key]")
                  && document.activeElement?.dataset?.terminalReferenceMatch === "artifact_path"
                  && (document.activeElement?.textContent || "").includes("Runnable Alpha - S01E01")
                  && tableText("completed-rows").includes("Runnable Alpha - S01E01"),
                "visible Completed Output destination and exact artifact-path row focus",
                () => "page=" + activePage()
                  + "; focus=" + (document.activeElement?.textContent || "")
                  + "; focusRowKey=" + (document.activeElement?.dataset?.rowKey || "")
                  + "; match=" + (document.activeElement?.dataset?.terminalReferenceMatch || "")
                  + "; completed=" + tableText("completed-rows"),
              );
              const queueText = tableText("queue-rows");
              const excludedText = tableText("queue-excluded-rows");
              const completedText = tableText("completed-rows") + "\\n" + tableText("completed-history-rows");
              return {
                posts,
                runMonitorGets,
                successful,
                duplicate: {
                  ok: duplicate?.ok === true,
                  command: duplicate?.command || "",
                  message: duplicate?.message || "",
                  evidencePhase: duplicate?.data?.evidence_phase || "",
                },
                announcements,
                runId: successful.runId,
                acceptedQueueFingerprint: successful.acceptedQueueFingerprint,
                acceptedItemCount: terminal.items.length,
                monitorState: terminal.run.lifecycle_state,
                monitorFreshness: terminal.freshness.state,
                queueText,
                excludedText,
                completedText,
                closeReadiness,
              };
            } finally {
              api.apiPost = originalApiPost;
              window.apiGet = originalWindowApiGet;
            }
          })()
          `;
        }

        function queueLaunchCompletedReloadScript() {
          return `
          (async () => {
            function byId(id) { return document.getElementById(id); }
            function tableText(id) { const node = byId(id); return node ? node.innerText || node.textContent || "" : ""; }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 25000;
              while (Date.now() < deadline) {
                if (await predicate()) return;
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + " after reload\\n"
                + [tableText("queue-rows"), tableText("queue-excluded-rows"), tableText("completed-rows"), tableText("completed-history-rows")].join("\\n\\n"));
            }
            await waitFor(
              () => {
                const queue = tableText("queue-rows");
                const excluded = tableText("queue-excluded-rows");
                const completed = tableText("completed-rows") + "\\n" + tableText("completed-history-rows");
                return !queue.includes("[SubsPlease] Runnable.Alpha.S01E01")
                  && !queue.includes("[Judas] Runnable.Beta.S01E01")
                  && queue.includes("Blocked Show S01E02 Needs Review.mkv")
                  && excluded.includes("Excluded Show S01E03 Held.mkv")
                  && completed.includes("Runnable Alpha - S01E01");
              },
              "persisted Queue and Completed rows",
            );
            window.showPage("home");
            const monitor = await window.mediaPipelineRunMonitor.refresh({ automatic: false });
            const workloadToggle = byId("run-monitor-items-toggle");
            const foldedWorkload = tableText("run-monitor-items");
            if (!foldedWorkload.includes("Runnable Alpha - S01E01.mkv")
                || foldedWorkload.includes("[SubsPlease]")
                || foldedWorkload.includes("[Judas]")) {
              throw new Error("reloaded folded workload did not retain verified clean names: " + foldedWorkload);
            }
            if (workloadToggle?.getAttribute("aria-expanded") !== "true") workloadToggle?.click();
            if (monitor?.run?.lifecycle_state !== "completed"
                || monitor?.freshness?.state !== "terminal"
                || monitor?.items?.length !== 2
                || !tableText("run-monitor-items").includes("Review")
                || !tableText("run-monitor-items").includes("Completed")) {
              throw new Error("durable Run Monitor did not survive reload as visible terminal evidence: " + JSON.stringify(monitor)
                + "\\nVisible items:\\n" + tableText("run-monitor-items"));
            }
            const closeReadiness = await window.mediaPipelineApi.apiGet("/api/backend/close-readiness");
            return {
              queueText: tableText("queue-rows"),
              excludedText: tableText("queue-excluded-rows"),
              completedText: tableText("completed-rows") + "\\n" + tableText("completed-history-rows"),
              monitorState: monitor.run.lifecycle_state,
              monitorFreshness: monitor.freshness.state,
              monitorItems: monitor.items.length,
              closeReadiness,
            };
          })()
          `;
        }

        async function waitForAppReady(client, label) {
          const expression = `Boolean(
            document.readyState === "complete"
            && document.getElementById("queue-rows")
            && document.getElementById("queue-excluded-rows")
            && document.getElementById("completed-rows")
            && document.getElementById("pipeline-start-button")?.dataset.pipelineStartBound === "true"
            && typeof window.showPage === "function"
            && typeof window.refreshAllNow === "function"
            && typeof window.mediaPipelineApi?.apiPost === "function"
            && typeof window.mediaPipelineApi?.apiGet === "function"
            && typeof window.mediaPipelineQueueView?.getSelectedQueueRow === "function"
            && typeof window.mediaPipelineLaunchView?.refreshLaunchBackendPreflight === "function"
            && typeof window.mediaPipelineRunMonitor?.refresh === "function"
          )`;
          const deadline = Date.now() + 25000;
          while (Date.now() < deadline) {
            const ready = await client.send("Runtime.evaluate", { expression, returnByValue: true });
            if (ready.result?.value === true) return;
            await sleep(100);
          }
          throw new Error("WebView did not become ready for " + label);
        }

        async function evaluate(client, expression) {
          const result = await client.send("Runtime.evaluate", {
            expression,
            awaitPromise: true,
            returnByValue: true,
          });
          if (result.exceptionDetails) {
            const details = result.exceptionDetails;
            throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
          }
          return result.result?.value || {};
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            await waitForAppReady(client, "initial workflow");
            const workflow = await evaluate(client, queueLaunchCompletedScript());
            await client.send("Page.reload", { ignoreCache: true });
            await waitForAppReady(client, "persisted reload");
            const reload = await evaluate(client, queueLaunchCompletedReloadScript());
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: { workflow, reload } }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_queue_launch_completed_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed Queue-to-Completed smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        payload_path = tmp / "browser-queue-launch-completed-payload.json"
        runner_path = tmp / "browser-queue-launch-completed-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": _free_port(),
                    "tmpRoot": str(tmp),
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_queue_launch_completed_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed Queue -> Launch -> Completed stateful smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=100,
        )


class WebViewBrowserQueueLaunchCompletedSmoke(unittest.TestCase):
    def test_real_browser_runs_authoritative_backend_queue_once_through_terminal_monitor(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed Queue-to-Completed smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            fixture = _write_queue_launch_completed_fixture(Path(raw_root))
            source_snapshot = capture_media_no_mutation_snapshot(fixture.tv_root)
            service = _StatefulQueueCompletionService(fixture)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            facade._autonomy_health_for_resolved = lambda _resolved_arg, **_kwargs: {  # type: ignore[method-assign]
                "overall_status": "ready"
            }
            original_run_monitor_reader = facade.get_run_monitor

            def read_journey_monitor(resolved_arg: object, *, run_id: str = "") -> dict[str, object]:
                journey = service.monitor_journey
                if journey is None:
                    return original_run_monitor_reader(resolved_arg, run_id=run_id)  # type: ignore[arg-type]
                return journey.serve(original_run_monitor_reader, resolved_arg, run_id=run_id)

            facade.get_run_monitor = read_journey_monitor  # type: ignore[method-assign]
            server = LocalApiServer(
                facade,
                token="browser-queue-launch-completed-token",
                resolved_provider=lambda: fixture.resolved,
                snapshot_provider=lambda: service.build_snapshot(fixture.resolved, str(fixture.root)),
                audit_root_provider=lambda: str(fixture.root),
                command_journal_path=fixture.command_journal_path,
            )
            try:
                server.start()
                result = _run_browser_queue_launch_completed_smoke(browser_path=browser_path, url=server.url)
            finally:
                service.stop_fake_runner()
                server.stop()

            self.assertTrue(result["ok"])
            self.assertIsNone(service.runner_failure)
            self.assertTrue(service.started.is_set())
            self.assertTrue(service.completed.is_set())
            self.assertEqual(len(service.start_calls), 1)
            self.assertEqual(service.start_calls[0]["mode"], "once")
            self.assertIsNone(service.start_calls[0]["single_file"])
            self.assertEqual(
                service.start_calls[0]["expected_queue_plan_fingerprint"],
                fixture.queue_plan_fingerprint,
            )
            self.assertEqual(service.accepted_run_rows_at_start, fixture.accepted_run_rows)
            self.assertEqual(
                [row["source_identity"] for row in service.accepted_run_rows_at_start],
                ["fixture-source-1", "fixture-source-2"],
            )
            self.assertEqual(
                [row["run_queue_index"] for row in service.accepted_run_rows_at_start],
                [1, 2],
            )
            self.assertEqual(
                {row["run_queue_total"] for row in service.accepted_run_rows_at_start},
                {2},
            )
            self.assertIsNotNone(service.monitor_journey)
            assert service.monitor_journey is not None
            self.assertIsNotNone(service.monitor_journey.seed_record)
            assert service.monitor_journey.seed_record is not None
            self.assertEqual(service.monitor_journey.seed_record.write_sequence, 1)
            self.assertEqual(service.monitor_journey.seed_record.run.lifecycle_state, "starting")
            self.assertEqual(
                [item.job_id for item in service.monitor_journey.seed_record.items],
                [
                    _run_monitor_job_id(service.start_calls[0]["run_id"], 1),
                    _run_monitor_job_id(service.start_calls[0]["run_id"], 2),
                ],
            )
            self.assertEqual(
                [item.routes.planned.route for item in service.monitor_journey.seed_record.items],
                ["remux", "encode_hardware"],
            )
            self.assertEqual(len(service.start_calls[0]["run_id"]), 32)
            self.assertEqual(len(service.fake_processes), 1)
            self.assertEqual(service.fake_processes[0].returncode, 0)
            self.assertEqual(service.real_pipeline_child_launch_count, 0)
            self.assertEqual(service.media_tool_invocations, [])
            self.assertEqual(service.network_worker_launch_count, 0)

            browser_result = result["result"]
            workflow = browser_result["workflow"]
            reload_result = browser_result["reload"]
            pipeline_posts = [post for post in workflow["posts"] if post["path"] == "/api/pipeline/start"]
            self.assertEqual(len(pipeline_posts), 2)
            self.assertEqual(sum(1 for post in pipeline_posts if post["ok"]), 1)
            self.assertEqual(workflow["successful"]["body"]["mode"], "once")
            self.assertFalse(workflow["successful"]["body"].get("single_file"))
            self.assertEqual(workflow["acceptedQueueFingerprint"], fixture.queue_plan_fingerprint)
            self.assertEqual(workflow["runId"], service.start_calls[0]["run_id"])
            self.assertIn(
                f"/api/run-monitor?run_id={workflow['runId']}",
                workflow["runMonitorGets"],
            )
            self.assertEqual(workflow["acceptedItemCount"], 2)
            self.assertEqual(workflow["monitorState"], "completed")
            self.assertEqual(workflow["monitorFreshness"], "terminal")
            self.assertEqual(reload_result["monitorState"], "completed")
            self.assertEqual(reload_result["monitorFreshness"], "terminal")
            self.assertEqual(reload_result["monitorItems"], 2)
            self.assertFalse(workflow["duplicate"]["ok"])
            self.assertIn("lifecycle", workflow["duplicate"]["message"].casefold())
            for state in (workflow, reload_result):
                self.assertNotIn("[SubsPlease] Runnable.Alpha.S01E01", state["queueText"])
                self.assertNotIn("[Judas] Runnable.Beta.S01E01", state["queueText"])
                self.assertIn(fixture.blocked_source.name, state["queueText"])
                self.assertIn(fixture.excluded_source.name, state["excludedText"])
                self.assertIn(Path(fixture.planned_name_a).stem, state["completedText"])
                self.assertTrue(state["closeReadiness"]["safe_to_close"])
                self.assertFalse(state["closeReadiness"]["active_work"])

            journal = json.loads(fixture.command_journal_path.read_text(encoding="utf-8"))
            pipeline_entries = [entry for entry in journal["entries"] if entry.get("command") == "pipeline.start"]
            self.assertEqual(len(pipeline_entries), 4)
            accepted = [entry for entry in pipeline_entries if entry.get("data", {}).get("evidence_phase") == "accepted"]
            outcomes = [
                entry
                for entry in pipeline_entries
                if entry.get("data", {}).get("evidence_phase") in {"running", "rejected"}
            ]
            self.assertEqual(len(accepted), 2)
            self.assertEqual(len(outcomes), 2)
            self.assertEqual(sum(1 for entry in outcomes if entry.get("ok") is True), 1)
            self.assertEqual(sum(1 for entry in outcomes if entry.get("ok") is False), 1)

            queue_snapshot = json.loads(fixture.queue_snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(queue_snapshot["runnable_count"], 0)
            self.assertEqual([row["source_path"] for row in queue_snapshot["rows"]], [str(fixture.blocked_source)])
            self.assertEqual(
                [row["source_path"] for row in queue_snapshot["excluded_rows"]],
                [str(fixture.excluded_source)],
            )
            completed_lines = fixture.completed_manifest_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(completed_lines), 1)
            completed_record = json.loads(completed_lines[0])
            self.assertEqual(completed_record["source_path"], str(fixture.runnable_source_a))
            self.assertEqual(completed_record["output_path"], str(fixture.output))
            self.assertEqual(completed_record["sidecar_path"], str(fixture.output_sidecar))
            self.assertTrue(fixture.output.is_file())
            sidecar = json.loads(fixture.output_sidecar.read_text(encoding="utf-8"))
            self.assertEqual(sidecar["schema_version"], "pipeline_sidecar.v1")
            self.assertEqual(sidecar["source_path"], str(fixture.runnable_source_a))
            failure_report = json.loads(fixture.failure_report_path.read_text(encoding="utf-8"))
            self.assertEqual(failure_report["source_path"], str(fixture.runnable_source_b))
            self.assertEqual(failure_report["status"], "review")
            self.assertEqual(failure_report["run_id"], service.start_calls[0]["run_id"])
            terminal_monitor = RunMonitorStore(fixture.state_root).read(service.start_calls[0]["run_id"])
            self.assertIsNotNone(terminal_monitor)
            assert terminal_monitor is not None
            self.assertEqual(terminal_monitor.run.lifecycle_state, "completed")
            self.assertEqual(terminal_monitor.run.accepted_queue.fingerprint, fixture.queue_plan_fingerprint)
            self.assertEqual([item.position for item in terminal_monitor.items], [1, 2])
            self.assertEqual([item.lifecycle_state for item in terminal_monitor.items], ["completed", "review"])
            self.assertEqual(
                json.loads(fixture.progress_path.read_text(encoding="utf-8"))["CurrentStage"],
                "idle",
            )
            self.assertEqual(LifecycleLeaseStore(fixture.state_root).status()["status"], "idle")
            self.assertEqual(list(fixture.pending_root.iterdir()), [])
            self.assertFalse((fixture.state_root / "Network").exists())
            assert_media_no_mutation(self, source_snapshot)


if __name__ == "__main__":
    unittest.main()
