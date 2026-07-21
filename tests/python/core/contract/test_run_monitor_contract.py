from __future__ import annotations

import json
import unittest
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from mediapipeline.contracts.run_monitor import (
    AUDIO_COLLECTION_STATES,
    ITEM_LIFECYCLE_STATES,
    RUN_LIFECYCLE_STATES,
    RUN_MONITOR_STAGE_IDS,
    STAGE_STATES,
    SUBTITLE_COLLECTION_STATES,
    RunMonitorPointer,
    RunMonitorRecord,
)
from mediapipeline.tools.paths import find_repo_root


RUN_ID = "run-20260716-0001"
UPDATED_AT = "2026-07-16T15:00:00Z"
REPO_ROOT = find_repo_root(Path(__file__))


def _evidence(source: str = "pipeline_engine", *, recorded_at: str = UPDATED_AT) -> dict[str, object]:
    return {
        "source": source,
        "provenance": "backend_confirmed",
        "recorded_at": recorded_at,
    }


def _progress(
    kind: str = "none",
    *,
    numerator: int | None = None,
    denominator: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"kind": kind}
    if numerator is not None:
        payload["numerator"] = numerator
    if denominator is not None:
        payload["denominator"] = denominator
    return payload


def _stages(*, active_stage: str | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    active_index = RUN_MONITOR_STAGE_IDS.index(active_stage) if active_stage else -1
    for index, stage_id in enumerate(RUN_MONITOR_STAGE_IDS):
        if stage_id == "accepted":
            state = "completed"
        elif active_index >= 0 and index < active_index:
            state = "completed"
        elif stage_id == active_stage:
            state = "active"
        else:
            state = "not_started"
        rows.append(
            {
                "stage_id": stage_id,
                "state": state,
                "started_at": UPDATED_AT if state in {"active", "completed"} else "",
                "updated_at": UPDATED_AT if state in {"active", "completed"} else "",
                "completed_at": UPDATED_AT if state == "completed" else "",
                "detail": "",
                "reason_code": "",
                "progress": _progress(),
                "evidence": _evidence(),
            }
        )
    return rows


def _route(
    state: str,
    *,
    route: str = "",
    reason: str = "",
    reason_code: str = "",
    source: str = "pipeline_engine",
) -> dict[str, object]:
    return {
        "state": state,
        "route": route,
        "reason": reason,
        "reason_code": reason_code,
        "evidence": _evidence(source),
    }


def _item(
    position: int,
    total: int,
    *,
    lifecycle_state: str = "queued",
    active_stage: str | None = None,
    leaf_name: str | None = None,
) -> dict[str, object]:
    display_name = leaf_name or f"Movie-{position:04d}.mkv"
    parent = f"Collection-{position:04d}"
    return {
        "job_id": f"{RUN_ID}:item:{position}",
        "source_identity": {
            "value": f"source-v2-{position}",
            "algorithm": "source_identity_v2",
        },
        "source_path": rf"C:\Media\{parent}\{display_name}",
        "display_name": display_name,
        "parent_context": parent,
        "position": position,
        "total": total,
        "lifecycle_state": lifecycle_state,
        "lifecycle_evidence": _evidence(),
        "updated_at": UPDATED_AT,
        "routes": {
            "planned": _route(
                "available",
                route="remux",
                reason="Container normalization only",
                reason_code="container_only",
                source="queue_snapshot",
            ),
            "executed": _route("awaiting_evidence"),
            "final": _route("awaiting_evidence"),
        },
        "stages": _stages(active_stage=active_stage),
        "audio": {
            "state": "awaiting_evidence",
            "tracks": [],
            "evidence": _evidence(),
        },
        "subtitles": {
            "state": "awaiting_evidence",
            "tracks": [],
            "evidence": _evidence(),
        },
        "output": {
            "state": "awaiting_evidence",
            "scratch_path": "",
            "working_output_path": "",
            "published_path": "",
            "parked_path": "",
            "intended_final_path": "",
            "size_bytes": None,
            "verification_state": "unknown",
            "sidecars": [],
            "evidence": _evidence(),
        },
        "terminal_references": [],
        "failure": {
            "state": "none",
            "reason_code": "",
            "reason": "",
            "retryable": None,
            "reference": "",
            "evidence": _evidence(),
        },
        "recovery": {
            "owner": "pipeline",
            "next_action": "Wait for backend evidence.",
            "retryable": None,
            "evidence": _evidence(),
        },
    }


def _payload(
    items: list[dict[str, object]],
    *,
    lifecycle_state: str = "running",
    workers: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "pipeline_run_monitor.v1",
        "write_sequence": 1,
        "run": {
            "run_id": RUN_ID,
            "command_id": "command-1",
            "mode": "once",
            "scope": "backend_queue",
            "accepted_queue": {
                "schema_version": "queue_plan_fingerprint.v1",
                "fingerprint": "sha256:accepted-plan",
                "accepted_count": len(items),
            },
            "lifecycle_state": lifecycle_state,
            "started_at": "2026-07-16T14:59:00Z",
            "updated_at": UPDATED_AT,
            "ended_at": "" if lifecycle_state not in {"completed", "failed", "stopped", "force_stopped"} else UPDATED_AT,
            "stop_after_current": {
                "state": "not_requested",
                "requested_at": "",
                "evidence": _evidence(),
            },
            "counts": {
                "accepted": len(items),
                "queued": sum(1 for item in items if item["lifecycle_state"] == "queued"),
                "active": sum(1 for item in items if item["lifecycle_state"] == "active"),
                "completed": sum(1 for item in items if item["lifecycle_state"] == "completed"),
                "failed": sum(1 for item in items if item["lifecycle_state"] == "failed"),
                "skipped": sum(1 for item in items if item["lifecycle_state"] == "skipped"),
                "blocked": sum(1 for item in items if item["lifecycle_state"] == "blocked"),
                "review": sum(1 for item in items if item["lifecycle_state"] == "review"),
                "parked": sum(1 for item in items if item["lifecycle_state"] == "parked"),
                "stopped": sum(1 for item in items if item["lifecycle_state"] == "stopped"),
            },
            "evidence": _evidence(),
        },
        "items": items,
        "current_workers": workers or [],
    }


def _worker(number: int, job_id: str, *, stage_id: str = "transcode") -> dict[str, object]:
    return {
        "worker_id": f"local-worker-{number}",
        "run_id": RUN_ID,
        "job_id": job_id,
        "state": "active",
        "stage_id": stage_id,
        "route": "encode",
        "progress": _progress("determinate", numerator=25 * number, denominator=100),
        "updated_at": UPDATED_AT,
        "evidence": _evidence("worker_heartbeat"),
    }


class RunMonitorContractTests(unittest.TestCase):
    def test_preserves_backend_planned_rename_display_name_without_changing_source_identity(self) -> None:
        item = _item(1, 1, leaf_name="Django Unchained (2012).mkv")
        item["source_path"] = r"C:\Media\Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv"

        record = RunMonitorRecord.model_validate(_payload([item]))

        accepted = record.items[0]
        self.assertEqual(accepted.display_name, "Django Unchained (2012).mkv")
        self.assertEqual(
            accepted.source_path,
            r"C:\Media\Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv",
        )

    def test_preserves_every_accepted_item_exactly_once_beyond_queue_render_limit(self) -> None:
        items = [_item(index, 507) for index in range(1, 508)]
        items[0] = _item(1, 507, leaf_name="Episode.mkv")
        items[1] = _item(2, 507, leaf_name="Episode.mkv")

        record = RunMonitorRecord.model_validate(_payload(items))

        self.assertEqual(len(record.items), 507)
        self.assertEqual([item.position for item in record.items], list(range(1, 508)))
        self.assertEqual({item.total for item in record.items}, {507})
        self.assertNotEqual(record.items[0].job_id, record.items[1].job_id)
        self.assertNotEqual(record.items[0].source_path, record.items[1].source_path)

    def test_rejects_duplicate_job_id_source_identity_or_run_position(self) -> None:
        duplicate_cases: list[tuple[str, Callable[[list[dict[str, object]]], None]]] = [
            ("job_id", lambda items: items[1].update(job_id=items[0]["job_id"])),
            (
                "source identity",
                lambda items: items[1].update(source_identity=dict(items[0]["source_identity"])),
            ),
            ("position", lambda items: items[1].update(position=1)),
        ]
        for label, mutate in duplicate_cases:
            with self.subTest(label=label):
                items = [_item(1, 2), _item(2, 2)]
                mutate(items)
                with self.assertRaisesRegex(ValidationError, label):
                    RunMonitorRecord.model_validate(_payload(items))

    def test_requires_the_complete_explicit_stage_ledger_with_semantic_states(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="verification")
        record = RunMonitorRecord.model_validate(_payload([item]))

        self.assertEqual(tuple(stage.stage_id for stage in record.items[0].stages), RUN_MONITOR_STAGE_IDS)
        self.assertEqual(record.items[0].stage("verification").state, "active")
        self.assertEqual(record.items[0].stage("probe").state, "completed")

        item["stages"] = [stage for stage in item["stages"] if stage["stage_id"] != "probe"]
        with self.assertRaisesRegex(ValidationError, "stage ledger"):
            RunMonitorRecord.model_validate(_payload([item]))

    def test_keeps_planned_executed_and_final_route_evidence_separate(self) -> None:
        item = _item(1, 1, lifecycle_state="completed")
        item["routes"] = {
            "planned": _route("available", route="remux", reason="Plan", source="queue_snapshot"),
            "executed": _route("available", route="encode", reason="Runtime fallback", source="route_selected_event"),
            "final": _route("available", route="encode", reason="Verified publish", source="completed_sidecar"),
        }

        record = RunMonitorRecord.model_validate(_payload([item], lifecycle_state="completed"))

        routes = record.items[0].routes
        self.assertEqual(routes.planned.route, "remux")
        self.assertEqual(routes.executed.reason, "Runtime fallback")
        self.assertEqual(routes.final.reason, "Verified publish")
        self.assertEqual(routes.planned.evidence.source, "queue_snapshot")
        self.assertEqual(routes.executed.evidence.source, "route_selected_event")
        self.assertEqual(routes.final.evidence.source, "completed_sidecar")

    def test_terminal_unknown_route_can_explain_a_verified_pre_route_failure(self) -> None:
        item = _item(1, 1, lifecycle_state="failed")
        item["routes"]["final"] = {
            "state": "unknown",
            "route": "",
            "reason": "Source probe failed before a runtime route could be selected.",
            "reason_code": "SOURCE_PROBE_FAILED",
            "evidence": _evidence("failure_artifact"),
        }

        record = RunMonitorRecord.model_validate(_payload([item], lifecycle_state="failed"))

        self.assertEqual(record.items[0].routes.final.state, "unknown")
        self.assertEqual(record.items[0].routes.final.route, "")
        self.assertEqual(record.items[0].routes.final.reason_code, "SOURCE_PROBE_FAILED")
        self.assertEqual(record.items[0].routes.final.evidence.source, "failure_artifact")

    def test_preserves_complete_audio_and_subtitle_track_evidence(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="subtitles")
        item["audio"] = {
            "state": "active",
            "policy_final": True,
            "evidence": _evidence("audio_policy"),
            "tracks": [
                {
                    "track_id": "audio:1",
                    "stream_index": 1,
                    "language": "jpn",
                    "source_codec": "truehd",
                    "source_channels": 8,
                    "source_layout": "7.1",
                    "planned_action": "transcode",
                    "current_action": "downmix",
                    "state": "active",
                    "started_at": "2026-07-16T15:00:00Z",
                    "updated_at": "2026-07-16T15:00:05Z",
                    "completed_at": "",
                    "output_codec": "aac",
                    "output_channels": 2,
                    "output_layout": "stereo",
                    "is_default": True,
                    "reason_code": "profile_stereo_compatibility",
                    "reason": "Profile requires a stereo compatibility track.",
                    "progress": _progress("indeterminate"),
                    "result": "",
                    "evidence": _evidence("audio_policy"),
                },
                {
                    "track_id": "audio:2",
                    "stream_index": 2,
                    "language": "eng",
                    "source_codec": "aac",
                    "source_channels": 2,
                    "source_layout": "stereo",
                    "planned_action": "passthrough",
                    "current_action": "passthrough",
                    "state": "completed",
                    "started_at": "2026-07-16T14:59:58Z",
                    "updated_at": "2026-07-16T15:00:02Z",
                    "completed_at": "2026-07-16T15:00:02Z",
                    "output_codec": "aac",
                    "output_channels": 2,
                    "output_layout": "stereo",
                    "is_default": False,
                    "reason_code": "profile_passthrough",
                    "reason": "Codec is allowed by the selected profile.",
                    "progress": _progress("none"),
                    "result": "copied",
                    "evidence": _evidence("audio_policy"),
                },
            ],
        }
        item["subtitles"] = {
            "state": "active",
            "policy_final": True,
            "evidence": _evidence("subtitle_policy"),
            "tracks": [
                {
                    "track_id": "subtitle:4",
                    "stream_index": 4,
                    "language": "eng",
                    "source_codec": "hdmv_pgs_subtitle",
                    "source_type": "image",
                    "preserve": True,
                    "extract": True,
                    "convert": True,
                    "ocr": True,
                    "write_embedded": True,
                    "write_sidecar": True,
                    "planned_action": "preserve_and_ocr",
                    "current_action": "ocr",
                    "state": "active",
                    "started_at": "2026-07-16T15:00:03Z",
                    "updated_at": "2026-07-16T15:00:08Z",
                    "completed_at": "",
                    "output_codec": "subrip",
                    "output_location": "external_sidecar",
                    "output_path": r"C:\Scratch\Movie.eng.srt",
                    "parked_path": "",
                    "intended_final_path": r"D:\Library\Movie.eng.srt",
                    "reason_code": "preferred_language_srt",
                    "reason": "Generate a preferred-language SRT while preserving the original.",
                    "progress": _progress("indeterminate"),
                    "result": "",
                    "evidence": _evidence("pgs_ocr"),
                }
            ],
        }

        record = RunMonitorRecord.model_validate(_payload([item]))

        self.assertEqual(len(record.items[0].audio.tracks), 2)
        self.assertEqual(record.items[0].audio.tracks[0].language, "jpn")
        self.assertTrue(record.items[0].audio.policy_final)
        self.assertEqual(record.items[0].audio.tracks[0].current_action, "downmix")
        self.assertEqual(record.items[0].audio.tracks[0].started_at, "2026-07-16T15:00:00Z")
        self.assertEqual(record.items[0].audio.tracks[1].completed_at, "2026-07-16T15:00:02Z")
        self.assertEqual(record.items[0].subtitles.tracks[0].language, "eng")
        self.assertTrue(record.items[0].subtitles.policy_final)
        self.assertTrue(record.items[0].subtitles.tracks[0].preserve)
        self.assertEqual(record.items[0].subtitles.tracks[0].progress.kind, "indeterminate")
        self.assertEqual(record.items[0].subtitles.tracks[0].output_codec, "subrip")
        self.assertEqual(record.items[0].subtitles.tracks[0].output_location, "external_sidecar")
        self.assertEqual(record.items[0].subtitles.tracks[0].output_path, r"C:\Scratch\Movie.eng.srt")
        self.assertEqual(record.items[0].subtitles.tracks[0].intended_final_path, r"D:\Library\Movie.eng.srt")
        self.assertEqual(record.items[0].subtitles.tracks[0].updated_at, "2026-07-16T15:00:08Z")

    def test_absent_subtitle_terminal_output_fields_remain_backward_compatible_unknowns(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="subtitles")
        item["subtitles"] = {
            "state": "awaiting_evidence",
            "evidence": _evidence("subtitle_policy"),
            "tracks": [
                {
                    "track_id": "subtitle:sidecar:0",
                    "source_ordinal": 0,
                    "language": "eng",
                    "source_codec": "ass",
                    "source_type": "text",
                    "source_kind": "sidecar",
                    "planned_action": "convert_ass_to_srt",
                    "current_action": "",
                    "state": "awaiting_evidence",
                    "evidence": _evidence("subtitle_policy"),
                }
            ],
        }

        record = RunMonitorRecord.model_validate(_payload([item]))
        track = record.items[0].subtitles.tracks[0]

        self.assertEqual(track.output_codec, "")
        self.assertEqual(track.output_location, "unknown")
        self.assertEqual(track.output_path, "")
        self.assertEqual(track.parked_path, "")
        self.assertEqual(track.intended_final_path, "")
        self.assertEqual(track.started_at, "")
        self.assertEqual(track.updated_at, "")
        self.assertEqual(track.completed_at, "")
        self.assertFalse(record.items[0].subtitles.policy_final)

    def test_missing_track_evidence_is_awaiting_evidence_not_pending(self) -> None:
        record = RunMonitorRecord.model_validate(_payload([_item(1, 1)]))

        self.assertEqual(record.items[0].audio.state, "awaiting_evidence")
        self.assertEqual(record.items[0].subtitles.state, "awaiting_evidence")
        self.assertNotIn("pending", AUDIO_COLLECTION_STATES)
        self.assertNotIn("pending", SUBTITLE_COLLECTION_STATES)

    def test_progress_requires_a_truthful_numerator_and_denominator(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="copy_to_scratch")
        copy_stage = next(stage for stage in item["stages"] if stage["stage_id"] == "copy_to_scratch")
        copy_stage["progress"] = _progress("determinate", numerator=50, denominator=100)
        record = RunMonitorRecord.model_validate(_payload([item]))
        self.assertEqual(record.items[0].stage("copy_to_scratch").progress.fraction, 0.5)

        for invalid in (
            _progress("determinate", numerator=1),
            _progress("determinate", denominator=10),
            _progress("determinate", numerator=11, denominator=10),
            {"kind": "indeterminate", "numerator": 2, "denominator": 4},
        ):
            with self.subTest(invalid=invalid):
                copy_stage["progress"] = invalid
        with self.assertRaises(ValidationError):
            RunMonitorRecord.model_validate(_payload([item]))

    def test_determinate_progress_rejects_nonfinite_values(self) -> None:
        for numerator, denominator in (
            (float("inf"), float("inf")),
            (1.0, float("inf")),
            (float("nan"), 100.0),
            (1.0, float("nan")),
            (float("-inf"), 100.0),
        ):
            with self.subTest(numerator=numerator, denominator=denominator):
                item = _item(1, 1, lifecycle_state="active", active_stage="copy_to_scratch")
                copy_stage = next(stage for stage in item["stages"] if stage["stage_id"] == "copy_to_scratch")
                copy_stage["progress"] = {
                    "kind": "determinate",
                    "numerator": numerator,
                    "denominator": denominator,
                }
                with self.assertRaises(ValidationError):
                    RunMonitorRecord.model_validate(_payload([item]))

    def test_ocr_progress_distinguishes_tool_determinate_from_indeterminate_work(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="subtitles")
        base_track = {
            "track_id": "subtitle:4",
            "stream_index": 4,
            "language": "eng",
            "source_codec": "hdmv_pgs_subtitle",
            "source_type": "image",
            "preserve": True,
            "extract": True,
            "convert": True,
            "ocr": True,
            "write_embedded": True,
            "write_sidecar": True,
            "planned_action": "preserve_and_ocr",
            "current_action": "ocr",
            "state": "active",
            "started_at": UPDATED_AT,
            "updated_at": UPDATED_AT,
            "reason_code": "preferred_language_srt",
            "reason": "Generate SRT while preserving the original track.",
            "result": "",
            "evidence": _evidence("pgs_ocr"),
        }
        item["subtitles"] = {
            "state": "active",
            "evidence": _evidence("subtitle_policy"),
            "tracks": [
                {
                    **base_track,
                    "step_index": 2,
                    "step_total": 4,
                    "step_name": "convert_ocr",
                    "progress_unit": "pages",
                    "cue_count": None,
                    "progress": _progress("determinate", numerator=40, denominator=200),
                }
            ],
        }
        determinate = RunMonitorRecord.model_validate(_payload([item]))
        determinate_track = determinate.items[0].subtitles.tracks[0]
        self.assertEqual(determinate_track.progress.fraction, 0.2)
        self.assertEqual(determinate_track.step_index, 2)
        self.assertEqual(determinate_track.step_total, 4)
        self.assertEqual(determinate_track.step_name, "convert_ocr")
        self.assertEqual(determinate_track.progress_unit, "pages")
        self.assertIsNone(determinate_track.cue_count)

        item["subtitles"]["tracks"] = [
            {
                **base_track,
                "step_index": 2,
                "step_total": 4,
                "step_name": "convert_ocr",
                "progress_unit": "pages",
                "cue_count": 17,
                "progress": _progress("indeterminate"),
            }
        ]
        indeterminate = RunMonitorRecord.model_validate(_payload([item]))
        indeterminate_track = indeterminate.items[0].subtitles.tracks[0]
        self.assertIsNone(indeterminate_track.progress.fraction)
        self.assertEqual(indeterminate_track.step_index, 2)
        self.assertEqual(indeterminate_track.step_total, 4)
        self.assertEqual(indeterminate_track.step_name, "convert_ocr")
        self.assertEqual(indeterminate_track.progress_unit, "pages")
        self.assertEqual(indeterminate_track.cue_count, 17)

    def test_subtitle_step_metadata_fails_closed_and_absent_fields_remain_compatible(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="subtitles")
        track = {
            "track_id": "subtitle:4",
            "stream_index": 4,
            "state": "active",
            "started_at": UPDATED_AT,
            "updated_at": UPDATED_AT,
            "progress": _progress("indeterminate"),
            "evidence": _evidence("pgs_ocr"),
        }
        item["subtitles"] = {
            "state": "active",
            "evidence": _evidence("subtitle_policy"),
            "tracks": [track],
        }

        compatible = RunMonitorRecord.model_validate(_payload([item]))
        compatible_track = compatible.items[0].subtitles.tracks[0]
        self.assertEqual(compatible_track.step_index, 0)
        self.assertEqual(compatible_track.step_total, 0)
        self.assertEqual(compatible_track.step_name, "")
        self.assertEqual(compatible_track.progress_unit, "")
        self.assertIsNone(compatible_track.cue_count)

        for invalid_metadata in (
            {"step_index": 3, "step_total": 2},
            {"step_index": 1, "step_total": 0},
            {"step_index": 1, "step_total": 2, "progress_unit": "invented_percent"},
            {"cue_count": -1},
        ):
            with self.subTest(metadata=invalid_metadata):
                track.update(invalid_metadata)
                with self.assertRaises(ValidationError):
                    RunMonitorRecord.model_validate(_payload([item]))
                for key in invalid_metadata:
                    track.pop(key, None)

    def test_terminal_run_cannot_retain_active_or_queued_items_or_workers(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="verification")
        with self.assertRaisesRegex(ValidationError, "terminal run"):
            RunMonitorRecord.model_validate(
                _payload([item], lifecycle_state="completed", workers=[_worker(1, str(item["job_id"]), stage_id="verification")])
            )

    def test_terminal_item_cannot_retain_an_active_stage(self) -> None:
        item = _item(1, 1, lifecycle_state="completed", active_stage="verification")

        with self.assertRaisesRegex(ValidationError, "terminal item"):
            RunMonitorRecord.model_validate(_payload([item], lifecycle_state="completed"))

    def test_stage_and_evidence_timestamps_fail_closed(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="verification")
        verification = next(stage for stage in item["stages"] if stage["stage_id"] == "verification")
        verification["started_at"] = ""
        with self.assertRaisesRegex(ValidationError, "active stage"):
            RunMonitorRecord.model_validate(_payload([item]))

        verification["started_at"] = UPDATED_AT
        verification["evidence"]["recorded_at"] = "not-a-timestamp"
        with self.assertRaisesRegex(ValidationError, "ISO-8601"):
            RunMonitorRecord.model_validate(_payload([item]))

    def test_active_audio_and_subtitle_tracks_require_truthful_nonterminal_timestamps(self) -> None:
        for collection_name, stage_id, base_track in (
            (
                "audio",
                "transcode",
                {"track_id": "audio:1", "stream_index": 1},
            ),
            (
                "subtitles",
                "subtitles",
                {"track_id": "subtitle:2", "stream_index": 2},
            ),
        ):
            for field, invalid_value in (
                ("started_at", ""),
                ("updated_at", ""),
                ("completed_at", UPDATED_AT),
            ):
                with self.subTest(collection=collection_name, field=field):
                    item = _item(1, 1, lifecycle_state="active", active_stage=stage_id)
                    track = {
                        **base_track,
                        "state": "active",
                        "started_at": UPDATED_AT,
                        "updated_at": UPDATED_AT,
                        "completed_at": "",
                        "evidence": _evidence(f"{collection_name}_runtime"),
                    }
                    track[field] = invalid_value
                    item[collection_name] = {
                        "state": "active",
                        "tracks": [track],
                        "evidence": _evidence(f"{collection_name}_runtime"),
                    }

                    label = "subtitle" if collection_name == "subtitles" else collection_name
                    with self.assertRaisesRegex(ValidationError, f"active {label} track"):
                        RunMonitorRecord.model_validate(_payload([item]))

    def test_terminal_track_timestamps_are_consistent_without_breaking_absent_nonactive_evidence(self) -> None:
        for collection_name, base_track in (
            ("audio", {"track_id": "audio:1", "stream_index": 1}),
            ("subtitles", {"track_id": "subtitle:2", "stream_index": 2}),
        ):
            with self.subTest(collection=collection_name, state="completed"):
                item = _item(1, 1, lifecycle_state="completed")
                item[collection_name] = {
                    "state": "completed",
                    "tracks": [
                        {
                            **base_track,
                            "state": "completed",
                            "started_at": UPDATED_AT,
                            "updated_at": UPDATED_AT,
                            "completed_at": UPDATED_AT,
                            "evidence": _evidence(f"{collection_name}_terminal"),
                        }
                    ],
                    "evidence": _evidence(f"{collection_name}_terminal"),
                }
                RunMonitorRecord.model_validate(_payload([item], lifecycle_state="completed"))

                item[collection_name]["tracks"][0]["completed_at"] = ""
                label = "subtitle" if collection_name == "subtitles" else collection_name
                with self.assertRaisesRegex(ValidationError, f"completed {label} track"):
                    RunMonitorRecord.model_validate(_payload([item], lifecycle_state="completed"))

            with self.subTest(collection=collection_name, state="awaiting_evidence"):
                item = _item(1, 1)
                item[collection_name] = {
                    "state": "awaiting_evidence",
                    "tracks": [
                        {
                            **base_track,
                            "state": "awaiting_evidence",
                            "evidence": _evidence(f"{collection_name}_policy"),
                        }
                    ],
                    "evidence": _evidence(f"{collection_name}_policy"),
                }
                record = RunMonitorRecord.model_validate(_payload([item]))
                self.assertEqual(record.items[0].model_dump()[collection_name]["tracks"][0]["updated_at"], "")

    def test_active_track_collection_and_item_lifecycle_claims_are_exactly_correlated(self) -> None:
        for collection_name, stage_id, base_track in (
            ("audio", "transcode", {"track_id": "audio:1", "stream_index": 1}),
            ("subtitles", "subtitles", {"track_id": "subtitle:2", "stream_index": 2}),
        ):
            active_track = {
                **base_track,
                "state": "active",
                "started_at": UPDATED_AT,
                "updated_at": UPDATED_AT,
                "completed_at": "",
                "evidence": _evidence(f"{collection_name}_runtime"),
            }

            for lifecycle_state in ("queued", "completed"):
                with self.subTest(collection=collection_name, lifecycle=lifecycle_state):
                    item = _item(1, 1, lifecycle_state=lifecycle_state)
                    item[collection_name] = {
                        "state": "active",
                        "tracks": [dict(active_track)],
                        "evidence": _evidence(f"{collection_name}_runtime"),
                    }
                    run_state = "completed" if lifecycle_state == "completed" else "running"
                    with self.assertRaisesRegex(ValidationError, "active track evidence requires an active item lifecycle"):
                        RunMonitorRecord.model_validate(_payload([item], lifecycle_state=run_state))

            with self.subTest(collection=collection_name, mismatch="active_collection_without_active_track"):
                item = _item(1, 1, lifecycle_state="active", active_stage=stage_id)
                item[collection_name] = {
                    "state": "active",
                    "tracks": [
                        {
                            **base_track,
                            "state": "awaiting_evidence",
                            "evidence": _evidence(f"{collection_name}_policy"),
                        }
                    ],
                    "evidence": _evidence(f"{collection_name}_runtime"),
                }
                label = "subtitle" if collection_name == "subtitles" else collection_name
                with self.assertRaisesRegex(ValidationError, f"active {label} collection"):
                    RunMonitorRecord.model_validate(_payload([item]))

            with self.subTest(collection=collection_name, mismatch="active_track_without_active_collection"):
                item = _item(1, 1, lifecycle_state="active", active_stage=stage_id)
                item[collection_name] = {
                    "state": "awaiting_evidence",
                    "tracks": [dict(active_track)],
                    "evidence": _evidence(f"{collection_name}_runtime"),
                }
                label = "subtitle" if collection_name == "subtitles" else collection_name
                with self.assertRaisesRegex(ValidationError, f"active {label} track"):
                    RunMonitorRecord.model_validate(_payload([item]))

    def test_every_visible_contract_timestamp_uses_the_same_iso_validator(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
        item["audio"] = {
            "state": "active",
            "tracks": [
                {
                    "track_id": "audio:1",
                    "stream_index": 1,
                    "state": "active",
                    "started_at": UPDATED_AT,
                    "updated_at": UPDATED_AT,
                    "progress": _progress(),
                    "evidence": _evidence("audio_policy"),
                }
            ],
            "evidence": _evidence("audio_policy"),
        }
        item["subtitles"] = {
            "state": "active",
            "tracks": [
                {
                    "track_id": "subtitle:2",
                    "stream_index": 2,
                    "state": "active",
                    "started_at": UPDATED_AT,
                    "updated_at": UPDATED_AT,
                    "progress": _progress(),
                    "evidence": _evidence("subtitle_policy"),
                }
            ],
            "evidence": _evidence("subtitle_policy"),
        }
        base = _payload([item], workers=[_worker(1, str(item["job_id"]))])
        mutations: tuple[tuple[str, Callable[[dict[str, object]], None]], ...] = (
            ("run.started_at", lambda payload: payload["run"].__setitem__("started_at", "invalid")),
            ("run.updated_at", lambda payload: payload["run"].__setitem__("updated_at", "invalid")),
            ("run.ended_at", lambda payload: payload["run"].__setitem__("ended_at", "invalid")),
            ("stop.requested_at", lambda payload: payload["run"]["stop_after_current"].__setitem__("requested_at", "invalid")),
            ("item.updated_at", lambda payload: payload["items"][0].__setitem__("updated_at", "invalid")),
            ("stage.updated_at", lambda payload: payload["items"][0]["stages"][8].__setitem__("updated_at", "invalid")),
            ("audio.updated_at", lambda payload: payload["items"][0]["audio"]["tracks"][0].__setitem__("updated_at", "invalid")),
            ("subtitle.started_at", lambda payload: payload["items"][0]["subtitles"]["tracks"][0].__setitem__("started_at", "invalid")),
            ("worker.updated_at", lambda payload: payload["current_workers"][0].__setitem__("updated_at", "invalid")),
        )
        for label, mutate in mutations:
            with self.subTest(timestamp=label):
                payload = json.loads(json.dumps(base))
                mutate(payload)
                with self.assertRaisesRegex(ValidationError, "ISO-8601"):
                    RunMonitorRecord.model_validate(payload)

        with self.assertRaisesRegex(ValidationError, "ISO-8601"):
            RunMonitorPointer.model_validate(
                {
                    "schema_version": "pipeline_run_monitor_pointer.v1",
                    "run_id": RUN_ID,
                    "updated_at": "invalid",
                }
            )

    def test_non_active_stage_and_track_evidence_cannot_remain_indeterminate(self) -> None:
        item = _item(1, 1)
        accepted = item["stages"][0]
        accepted["progress"] = _progress("indeterminate")
        with self.assertRaisesRegex(ValidationError, "non-active stage"):
            RunMonitorRecord.model_validate(_payload([item]))

        for collection, track in (
            (
                "audio",
                {
                    "track_id": "audio:1",
                    "stream_index": 1,
                    "state": "completed",
                    "started_at": UPDATED_AT,
                    "updated_at": UPDATED_AT,
                    "completed_at": UPDATED_AT,
                    "progress": _progress("indeterminate"),
                    "evidence": _evidence(),
                },
            ),
            (
                "subtitles",
                {
                    "track_id": "subtitle:2",
                    "stream_index": 2,
                    "state": "completed",
                    "started_at": UPDATED_AT,
                    "updated_at": UPDATED_AT,
                    "completed_at": UPDATED_AT,
                    "progress": _progress("indeterminate"),
                    "evidence": _evidence(),
                },
            ),
        ):
            with self.subTest(collection=collection):
                terminal_item = _item(1, 1)
                terminal_item[collection] = {
                    "state": "completed",
                    "tracks": [track],
                    "evidence": _evidence(),
                }
                with self.assertRaisesRegex(ValidationError, "non-active"):
                    RunMonitorRecord.model_validate(_payload([terminal_item]))

    def test_contract_rejects_unknown_fields_and_generated_schema_matches_model(self) -> None:
        payload = _payload([_item(1, 1)])
        payload["frontend_guess"] = "encode"
        with self.assertRaises(ValidationError):
            RunMonitorRecord.model_validate(payload)

        schema_path = REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "run_monitor.v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        generated = RunMonitorRecord.model_json_schema()
        self.assertEqual(schema["properties"], generated["properties"])
        self.assertEqual(schema["$defs"], generated["$defs"])
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_accepts_all_correlated_active_workers_and_rejects_uncorrelated_workers(self) -> None:
        items = [
            _item(1, 2, lifecycle_state="active", active_stage="transcode"),
            _item(2, 2, lifecycle_state="active", active_stage="verification"),
        ]
        workers = [_worker(1, str(items[0]["job_id"])), _worker(2, str(items[1]["job_id"]), stage_id="verification")]

        record = RunMonitorRecord.model_validate(_payload(items, workers=workers))

        self.assertEqual([worker.worker_id for worker in record.current_workers], ["local-worker-1", "local-worker-2"])
        workers[1]["run_id"] = "other-run"
        with self.assertRaisesRegex(ValidationError, "run_id"):
            RunMonitorRecord.model_validate(_payload(items, workers=workers))

    def test_contract_enums_preserve_required_semantic_distinctions(self) -> None:
        self.assertTrue(
            {
                "starting",
                "scanning",
                "running",
                "paused",
                "stop_requested",
                "stopping",
                "completed",
                "failed",
                "stopped",
                "force_stopped",
                "unknown",
            }.issubset(RUN_LIFECYCLE_STATES)
        )
        self.assertTrue(
            {"accepted", "queued", "active", "completed", "failed", "skipped", "blocked", "review", "parked", "stopped", "unknown"}.issubset(
                ITEM_LIFECYCLE_STATES
            )
        )
        self.assertTrue(
            {"not_started", "active", "completed", "skipped", "not_applicable", "unknown", "blocked", "review", "failed"}.issubset(
                STAGE_STATES
            )
        )


if __name__ == "__main__":
    unittest.main()
