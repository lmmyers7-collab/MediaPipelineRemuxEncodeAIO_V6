from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult
from tests.python.desktop.application_facade_test_support import DummyFacadeService, DummyWorkflowFacadeService, _resolved


class ApplicationFacadeCompletedTests(unittest.TestCase):
    def test_completed_preview_reads_local_manifest_without_output_share_scan(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Movie (2024).mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"x" * 2048)
            sidecar = output.with_suffix(".pipeline.json")
            sidecar.write_text("{}", encoding="utf-8")
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(root / "Source" / "Movie.mkv"),
                        "output_path": str(output),
                        "route": "encode",
                        "encoded_at": "2026-05-07T21:00:00-04:00",
                        "elapsed_seconds": 65,
                        "source_size": 4 * 1024 ** 3,
                        "output_size": 2 * 1024 ** 3,
                        "route_plan": {
                            "estimated_bitrate_mbps": 19.1,
                            "bitrate_threshold_mbps": 20.0,
                            "bitrate_over_threshold": False,
                            "source_media_profile": {
                                "duration_seconds": 1800,
                            },
                        },
                        "publish_state": "published",
                        "publish_mode": "immediate",
                        "encode_selected_encoder": "hevc_nvenc",
                        "route_reason_code": "subtitle_srt_required",
                        "route_reason": "needs preferred-language SRT",
                        "audio_decisions": [
                            {
                                "audio_ordinal": 0,
                                "language": "eng",
                                "source_codec": "aac",
                                "action": "copy",
                                "reason": "compatible",
                            }
                        ],
                        "subtitle_decisions": [
                            {
                                "subtitle_ordinal": 0,
                                "language": "eng",
                                "source_codec": "ass",
                                "action": "srt",
                                "reason": "plex_srt",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            old_mtime = time.time() - 10 * 24 * 60 * 60
            os.utime(manifest, (old_mtime, old_mtime))
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_completed_preview(resolved).to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_completed_preview.v1")
        self.assertEqual(preview["manifest_freshness_status"], "stale")
        self.assertGreaterEqual(preview["manifest_age_seconds"], 604800)
        self.assertTrue(preview["manifest_mtime_utc"])
        self.assertEqual(preview["count"], 1)
        self.assertEqual(preview["inventory_progress"]["schema_version"], "desktop_completed_inventory_progress.v1")
        self.assertEqual(preview["inventory_progress"]["rows_loaded"], 1)
        self.assertEqual(preview["progress_bars"][0]["id"], "completed_inventory")
        self.assertEqual(preview["encode_count"], 1)
        self.assertEqual(preview["missing_output_count"], 0)
        self.assertEqual(preview["total_output_bytes"], 2 * 1024 ** 3)
        self.assertEqual(preview["route_counts"], {"encode": 1})
        self.assertEqual(preview["publish_counts"], {"published": 1})
        self.assertEqual(preview["health_counts"], {"ok": 1})
        self.assertEqual(preview["operator_status_counts"], {"Healthy": 1})
        self.assertEqual(preview["operator_status_state_counts"], {"match": 1})
        self.assertEqual(preview["operator_severity_counts"], {"ok": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"consistent-looking": 1})
        self.assertEqual(preview["consistency_status_counts"], {"Consistent": 1})
        self.assertEqual(preview["consistency_severity_counts"], {"ok": 1})
        self.assertEqual(preview["validation_status_state_counts"], {"validation-needed": 1})
        self.assertEqual(preview["validation_state"]["schema_version"], "desktop_validation_state.v1")
        self.assertEqual(preview["validation_state"]["status_state"], "validation-needed")
        self.assertEqual(preview["validation_state"]["validation_needed_count"], 1)
        self.assertEqual(preview["size_bucket_counts"], {"shrink_or_equal": 1})
        self.assertEqual(preview["missing_sidecar_count"], 0)
        self.assertEqual(preview["output_sidecar_mismatch_count"], 0)
        self.assertEqual(preview["stale_sidecar_count"], 0)
        self.assertEqual(preview["missing_manifest_output_path_count"], 0)
        self.assertEqual(preview["media_type_counts"], {"Movie": 1})
        self.assertEqual(preview["decision_totals"], {"audio": 1, "subtitle": 1})
        self.assertEqual(preview["size_growth_count"], 0)
        self.assertEqual(preview["size_growth_over_5_count"], 0)
        self.assertEqual(preview["size_unknown_count"], 0)
        self.assertEqual(preview["rows"][0]["route_label"], "ENCODE")
        self.assertEqual(preview["rows"][0]["route_reason_code"], "subtitle_srt_required")
        self.assertEqual(preview["rows"][0]["route_reason"], "needs preferred-language SRT")
        self.assertEqual(preview["rows"][0]["output_size_text"], "2.00 GB")
        self.assertEqual(preview["rows"][0]["size_delta_percent"], -50.0)
        self.assertEqual(preview["rows"][0]["size_delta_label"], "-50.0%")
        self.assertFalse(preview["rows"][0]["size_growth_over_5"])
        self.assertEqual(preview["rows"][0]["duration_seconds"], 1800.0)
        self.assertEqual(preview["rows"][0]["bitrate_text"], "9.5 Mbps")
        self.assertEqual(preview["rows"][0]["output_bitrate_text"], "9.5 Mbps")
        self.assertEqual(preview["rows"][0]["source_bitrate_text"], "19.1 Mbps")
        self.assertEqual(preview["rows"][0]["bitrate_threshold_text"], "20 Mbps")
        self.assertIs(preview["rows"][0]["bitrate_over_threshold"], False)
        self.assertEqual(preview["rows"][0]["operator_status"], "Healthy")
        self.assertEqual(preview["rows"][0]["operator_status_state"], "match")
        self.assertEqual(preview["rows"][0]["operator_severity"], "ok")
        self.assertEqual(preview["rows"][0]["operator_trust_state"], "consistent-looking")
        self.assertIn("no output, sidecar, size, or runtime blocker", preview["rows"][0]["primary_concern"])
        self.assertIn("historical proof", preview["rows"][0]["safe_next_action"])
        self.assertIn("stale or inconsistent completed rows", preview["rows"][0]["unsafe_if_ignored"])
        self.assertIn("completed_manifest", preview["rows"][0]["recommended_diagnostics_targets"])
        self.assertIn("consistency=Consistent", preview["rows"][0]["proof_summary"])
        self.assertIn("encoded", preview["rows"][0]["review_flags"])
        self.assertEqual(preview["rows"][0]["route_decision_summary"], "ENCODE (subtitle_srt_required)")
        self.assertEqual(preview["rows"][0]["consistency_status"], "Consistent")
        self.assertEqual(preview["rows"][0]["consistency_severity"], "ok")
        self.assertEqual(preview["rows"][0]["validation_status_state"], "validation-needed")
        self.assertIsNone(preview["rows"][0]["validation_probe_ok"])
        self.assertIsNone(preview["rows"][0]["validation_hash_ok"])
        self.assertTrue(preview["rows"][0]["validation_playback_required"])
        self.assertIn("ffprobe output proof not reported", preview["rows"][0]["validation_unavailable_reasons"])
        self.assertEqual(preview["rows"][0]["size_bucket"], "shrink_or_equal")
        self.assertTrue(preview["rows"][0]["sidecar_exists"])
        self.assertTrue(preview["rows"][0]["sidecar_matches_output"])
        self.assertEqual(preview["rows"][0]["consistency_issues"], [])
        self.assertIn("Route: ENCODE", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Reason code: subtitle_srt_required", preview["rows"][0]["route_evidence_lines"])
        self.assertIn(
            "Bitrate: output=9.5 Mbps; source=19.1 Mbps; threshold=20 Mbps; over threshold=no",
            preview["rows"][0]["route_evidence_lines"],
        )
        self.assertIn("Audio: a:0 eng aac -> copy (compatible)", preview["rows"][0]["route_evidence_lines"])
        self.assertIn("Subtitles: s:0 eng ass -> srt (plex_srt)", preview["rows"][0]["route_evidence_lines"])
        self.assertEqual(preview["rows"][0]["audio_decision_count"], 1)
        self.assertEqual(preview["rows"][0]["audio_decision_preview"], ["a:0 eng aac -> copy (compatible)"])
        self.assertEqual(
            preview["rows"][0]["audio_decision_details"],
            [
                {
                    "kind": "audio",
                    "track_label": "a:0",
                    "language": "eng",
                    "source_codec": "aac",
                    "action": "copy",
                    "reason": "compatible",
                    "summary": "a:0 eng aac -> copy (compatible)",
                }
            ],
        )
        self.assertEqual(preview["rows"][0]["subtitle_decision_count"], 1)
        self.assertEqual(preview["rows"][0]["subtitle_decision_preview"], ["s:0 eng ass -> srt (plex_srt)"])
        self.assertEqual(
            preview["rows"][0]["subtitle_decision_details"],
            [
                {
                    "kind": "subtitle",
                    "track_label": "s:0",
                    "language": "eng",
                    "source_codec": "ass",
                    "action": "srt",
                    "reason": "plex_srt",
                    "summary": "s:0 eng ass -> srt (plex_srt)",
                }
            ],
        )
        self.assertTrue(preview["rows"][0]["row_key"])

    def test_completed_preview_flags_oversized_rows_for_operator_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Large Output.mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"x" * 8192)
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(root / "Source" / "Small Source.mkv"),
                        "output_path": str(output),
                        "route": "encode",
                        "encoded_at": "2026-05-07T21:00:00-04:00",
                        "source_size": 4096,
                        "output_size": 8192,
                        "publish_state": "published",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_completed_preview(resolved).to_mapping()

        row = preview["rows"][0]
        self.assertEqual(row["operator_status"], "Review size growth")
        self.assertEqual(row["operator_severity"], "warning")
        self.assertEqual(preview["operator_status_counts"], {"Review size growth": 1})
        self.assertEqual(preview["operator_status_state_counts"], {"warning": 1})
        self.assertEqual(preview["operator_severity_counts"], {"warning": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"review-before-rerun-or-cleanup": 1})
        self.assertEqual(row["operator_trust_state"], "review-before-rerun-or-cleanup")
        self.assertIn("sidecar is missing", row["primary_concern"])
        self.assertIn("sidecar/output consistency", row["safe_next_action"])
        self.assertIn("latest_failure_report", row["recommended_diagnostics_targets"])
        self.assertEqual(row["consistency_status"], "Review")
        self.assertEqual(row["consistency_severity"], "warning")
        self.assertEqual(row["size_bucket"], "growth_over_5")
        self.assertFalse(row["sidecar_exists"])
        self.assertIn("missing_sidecar", row["consistency_issues"])
        self.assertEqual(preview["missing_sidecar_count"], 1)
        self.assertEqual(preview["size_bucket_counts"], {"growth_over_5": 1})
        self.assertIn("Size: source=4.0 KB; output=8.0 KB; delta=+100.0%", row["route_evidence_lines"])
        self.assertIn("size_growth_over_5", row["review_flags"])
        self.assertIn("intentional compatibility encode", row["operator_guidance"])

    def test_completed_preview_correlates_recent_runtime_outcomes_by_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Source" / "Movie.mkv"
            output = root / "Outsource" / "Movies" / "Movie (2024).mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"x" * 4096)
            output.with_suffix(".pipeline.json").write_text("{}", encoding="utf-8")
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            event_file = root / "State" / "Progress" / "pipeline_events.jsonl"
            manifest.parent.mkdir(parents=True)
            event_file.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(source),
                        "output_path": str(output),
                        "route": "remux",
                        "encoded_at": "2026-05-07T21:00:00-04:00",
                        "source_size": 4096,
                        "output_size": 4096,
                        "publish_state": "published",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            events = [
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "evt-completed-failed",
                    "event_type": "job_completed",
                    "timestamp": "2999-01-01T00:00:00Z",
                    "created_at": "2999-01-01T00:00:00Z",
                    "stage": "publish",
                    "route": "remux",
                    "status": "failed",
                    "source_path": str(source),
                    "data": {
                        "success": False,
                        "completion_status": "failed",
                        "queue_terminal": False,
                        "retryable": True,
                        "reason": "Publish destination rejected the copy.",
                        "error_code": "OUTPUT_DESTINATION_LOW_SPACE",
                        "route": "remux",
                        "publish_state": "park_failed",
                        "publish_mode": "deferred",
                        "output_path": str(output),
                    },
                }
            ]
            event_file.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            service.read_pipeline_events_tail = lambda _resolved, line_count=300: events  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            resolved.event_file = event_file

            preview = facade.get_completed_preview(resolved).to_mapping()

        self.assertEqual(preview["runtime_outcome_source"], str(event_file))
        self.assertEqual(preview["runtime_outcome_event_count"], 1)
        self.assertEqual(preview["runtime_outcome_match_count"], 1)
        self.assertEqual(preview["runtime_outcome_status_counts"], {"failed": 1})
        self.assertEqual(preview["runtime_outcome_error_code_counts"], {"OUTPUT_DESTINATION_LOW_SPACE": 1})
        self.assertEqual(preview["runtime_outcome_event_type_counts"], {"job_completed": 1})
        self.assertEqual(preview["runtime_outcome_freshness_counts"], {"fresh": 1})
        self.assertEqual(preview["operator_status_counts"], {"Recent runtime conflict": 1})
        self.assertEqual(preview["operator_status_state_counts"], {"warning": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"review-before-rerun-or-cleanup": 1})
        row = preview["rows"][0]
        self.assertEqual(row["runtime_outcome_status"], "failed")
        self.assertEqual(row["runtime_outcome_error_code"], "OUTPUT_DESTINATION_LOW_SPACE")
        self.assertEqual(row["operator_status"], "Recent runtime conflict")
        self.assertEqual(row["operator_status_state"], "warning")
        self.assertEqual(row["operator_severity"], "warning")
        self.assertEqual(row["operator_trust_state"], "review-before-rerun-or-cleanup")
        self.assertIn("OUTPUT_DESTINATION_LOW_SPACE", row["primary_concern"])
        self.assertIn("runtime_outcome:failed", row["review_flags"])
        self.assertIn("runtime_error:OUTPUT_DESTINATION_LOW_SPACE", row["review_flags"])
        self.assertIn("Runtime error code: OUTPUT_DESTINATION_LOW_SPACE", row["route_evidence_lines"])
        self.assertIn("Runtime match: exact_source_path", row["route_evidence_lines"])

    def test_completed_preview_treats_successful_runtime_and_small_delta_as_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Source" / "Jennifer.mkv"
            output = root / "Outsource" / "Movies" / "Jennifer's Body (2009)" / "Jennifer's Body (2009).mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"x" * 5261)
            output.with_suffix(".pipeline.json").write_text("{}", encoding="utf-8")
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            event_file = root / "State" / "Progress" / "pipeline_events.jsonl"
            manifest.parent.mkdir(parents=True)
            event_file.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(source),
                        "output_path": str(output),
                        "route": "remux",
                        "route_reason_code": "codec_remux_safe",
                        "encoded_at": "2026-05-30T22:41:00-04:00",
                        "source_size": 5240,
                        "output_size": 5261,
                        "publish_state": "published",
                        "audio_decisions": [{"action": "copy"}, {"action": "copy"}],
                        "subtitle_decisions": [{"action": "copy"} for _ in range(5)],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            events = [
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "evt-completed-succeeded",
                    "event_type": "job_completed",
                    "timestamp": "2999-01-01T00:00:00Z",
                    "created_at": "2999-01-01T00:00:00Z",
                    "stage": "publish",
                    "route": "remux",
                    "status": "succeeded",
                    "source_path": str(source),
                    "data": {
                        "success": True,
                        "completion_status": "succeeded",
                        "queue_terminal": True,
                        "route": "remux",
                        "publish_state": "published",
                        "publish_mode": "immediate",
                        "output_path": str(output),
                    },
                }
            ]
            event_file.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            service.read_pipeline_events_tail = lambda _resolved, line_count=300: events  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            resolved.event_file = event_file

            preview = facade.get_completed_preview(resolved).to_mapping()

        row = preview["rows"][0]
        self.assertEqual(row["runtime_outcome_status"], "succeeded")
        self.assertEqual(row["runtime_outcome_match"], "exact_source_path")
        self.assertEqual(row["size_delta_percent"], 0.4)
        self.assertEqual(row["operator_status"], "Healthy")
        self.assertEqual(row["operator_status_state"], "match")
        self.assertEqual(row["operator_severity"], "ok")
        self.assertEqual(row["operator_trust_state"], "consistent-looking")
        self.assertIn("no output, sidecar, size, or runtime blocker", row["primary_concern"])
        self.assertNotIn("runtime_outcome", row["review_flags"])
        self.assertNotIn("runtime_outcome:succeeded", row["review_flags"])
        self.assertNotIn("size_growth", row["review_flags"])
        self.assertEqual(preview["operator_status_counts"], {"Healthy": 1})
        self.assertEqual(preview["operator_status_state_counts"], {"match": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"consistent-looking": 1})

    def test_completed_preview_flags_missing_output_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Missing Output.mkv"
            mismatched_sidecar = output.with_suffix(".pipeline.json")
            mismatched_sidecar.parent.mkdir(parents=True)
            mismatched_sidecar.write_text("{}", encoding="utf-8")
            older = time.time() - 120
            os.utime(mismatched_sidecar, (older, older))
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(root / "Source" / "Missing Source.mkv"),
                        "output_path": str(output),
                        "route": "remux",
                        "encoded_at": "2026-05-07T21:00:00-04:00",
                        "source_size": 4096,
                        "output_size": 4096,
                        "publish_state": "published",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_completed_preview(resolved).to_mapping()

        row = preview["rows"][0]
        self.assertEqual(row["consistency_status"], "Broken")
        self.assertEqual(row["consistency_severity"], "error")
        self.assertEqual(row["operator_trust_state"], "broken-output")
        self.assertIn("missing or unhealthy output", row["primary_concern"])
        self.assertIn("missing_output", row["consistency_issues"])
        self.assertEqual(preview["missing_output_count"], 1)
        self.assertEqual(preview["consistency_status_counts"], {"Broken": 1})
        self.assertEqual(preview["consistency_severity_counts"], {"error": 1})
        self.assertEqual(row["validation_status_state"], "blocked")
        self.assertIn("missing output", row["validation_failure_reason"])
        self.assertFalse(row["validation_playback_required"])
        self.assertEqual(preview["validation_status_state_counts"], {"blocked": 1})
        self.assertEqual(preview["validation_state"]["blocked_count"], 1)

    def test_completed_preview_limit_all_loads_full_history(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "source_path": str(root / "Source" / f"Movie {index}.mkv"),
                            "output_path": str(root / "Outsource" / f"Movie {index}.mkv"),
                            "route": "remux",
                            "encoded_at": "2026-05-07T21:00:00-04:00",
                        }
                    )
                    for index in range(505)
                )
                + "\n",
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            bounded = facade.get_completed_preview(resolved, limit=999).to_mapping()
            full = facade.get_completed_preview(resolved, limit="all").to_mapping()

        self.assertEqual(bounded["count"], 500)
        self.assertEqual(full["count"], 505)

    def test_completed_preview_force_refresh_rechecks_output_existence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Movie.mkv"
            output.parent.mkdir(parents=True)
            output.write_text("media", encoding="utf-8")
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(root / "Source" / "Movie.mkv"),
                        "output_path": str(output),
                        "route": "remux",
                        "encoded_at": "2026-05-07T21:00:00-04:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service)

            first = facade.get_completed_preview(resolved).to_mapping()
            output.unlink()
            cached = facade.get_completed_preview(resolved).to_mapping()
            refreshed = facade.get_completed_preview(resolved, force_refresh=True).to_mapping()

        self.assertTrue(first["rows"][0]["output_exists"])
        self.assertTrue(cached["rows"][0]["output_exists"])
        self.assertFalse(refreshed["rows"][0]["output_exists"])
        self.assertEqual(refreshed["missing_output_count"], 1)

    def test_completed_open_uses_backend_manifest_row_key_not_frontend_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            output = root / "Outsource" / "Movies" / "Movie (2024).mkv"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"media")
            sidecar = output.with_suffix(".pipeline.json")
            sidecar.write_text("{}", encoding="utf-8")
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(root / "Source" / "Movie.mkv"),
                        "output_path": str(output),
                        "route": "remux",
                        "encoded_at": "2026-05-07T21:00:00-04:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            service = DummyWorkflowFacadeService(root)
            default_opened_paths: list[Path] = []

            def open_with_default_app(path: Path | str | None) -> None:
                if path is None:
                    raise FileNotFoundError("Path does not exist: <none>")
                target = Path(path)
                if not target.exists():
                    raise FileNotFoundError(f"Path does not exist: {target}")
                default_opened_paths.append(target)

            service.open_path_with_default_app = open_with_default_app  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service)
            row_key = facade.get_completed_preview(resolved).to_mapping()["rows"][0]["row_key"]

            played = facade.open_completed_location(resolved, {"row_key": row_key, "target": "play_output_file"})
            opened_file = facade.open_completed_location(resolved, {"row_key": row_key, "target": "output_file"})
            opened = facade.open_completed_location(resolved, {"row_key": row_key, "target": "output_folder"})
            rejected = facade.open_completed_location(resolved, {"row_key": row_key, "target": str(root / "secret.txt")})
            missing = facade.open_completed_location(resolved, {"row_key": "not-a-row", "target": "output_folder"})

        self.assertTrue(played.ok)
        self.assertEqual(played.data["target"], "play_output_file")
        self.assertEqual(default_opened_paths, [output])
        self.assertTrue(opened_file.ok)
        self.assertEqual(opened_file.data["target"], "output_file")
        self.assertTrue(opened.ok)
        self.assertEqual(opened.command, "completed.open")
        self.assertEqual(opened.data["target"], "output_folder")
        self.assertEqual(service.opened_paths, [output, output.parent])
        self.assertFalse(rejected.ok)
        self.assertIn("target is not allowed", rejected.message)
        self.assertFalse(missing.ok)
        self.assertIn("no longer available", missing.message)

    def test_completed_open_resolves_rows_visible_from_full_history(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            old_output = root / "Outsource" / "Movies" / "Old Movie.mkv"
            old_output.parent.mkdir(parents=True)
            old_output.write_bytes(b"old-media")
            manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            lines: list[str] = []
            for index in range(501):
                output = old_output if index == 0 else root / "Outsource" / "Movies" / f"Movie {index}.mkv"
                lines.append(
                    json.dumps(
                        {
                            "source_path": str(root / "Source" / f"Movie {index}.mkv"),
                            "output_path": str(output),
                            "route": "remux",
                            "encoded_at": f"2026-05-07T21:{index % 60:02d}:00-04:00",
                        }
                    )
                )
            manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
            resolved = _resolved(root)
            resolved.completed_manifest_path = manifest
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service)
            full_preview = facade.get_completed_preview(resolved, limit="all").to_mapping()
            old_row_key = full_preview["rows"][-1]["row_key"]

            opened = facade.open_completed_location(resolved, {"row_key": old_row_key, "target": "output_file"})

        self.assertTrue(opened.ok)
        self.assertEqual(opened.data["path"], str(old_output))
        self.assertEqual(service.opened_paths, [old_output])

    def test_completed_backfill_returns_runner_stdout_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "Outsource").mkdir()
            (root / "Backfill-CompletedManifest.ps1").write_text("param()", encoding="utf-8")
            resolved = _resolved(root)
            resolved.local_base = root
            resolved.config_data = {"Outsource": str(root / "Outsource")}
            service = DummyWorkflowFacadeService(root)
            service._path_or_none = lambda value: Path(value) if value else None
            service._completed_history_cache_key = "stale"
            checkpoint_path = root / "RunLogs" / "backfill_checkpoint.json"

            def fake_run(args: list[str], **kwargs: object) -> CapturedCommandResult:
                self.assertIn("-DryRun", args)
                self.assertIn("-CheckpointPath", args)
                self.assertIn(str(checkpoint_path), args)
                self.assertEqual(kwargs["label"], "completed manifest backfill")
                return CapturedCommandResult(args=args, returncode=0, stdout="Backfill wrote 1 row.\n", stderr="")

            with patch("mediapipeline.core.completed.service.run_capture", fake_run):
                ok, message = service.backfill_completed_manifest(
                    resolved,
                    dry_run=True,
                    checkpoint_path=checkpoint_path,
                )

        self.assertTrue(ok)
        self.assertEqual(message, "Backfill wrote 1 row.")
        self.assertIsNone(service._completed_history_cache_key)

    def test_completed_backfill_dry_run_forces_dry_run_and_temp_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            calls: list[dict[str, object]] = []

            def fake_backfill(resolved: ResolvedPaths, **kwargs: object) -> tuple[bool, str]:
                calls.append({"resolved": resolved, **kwargs})
                return (
                    True,
                    "\n".join(
                        [
                            "Backfill dry run complete.",
                            "  Sidecars ingested : 9",
                            "  Skipped (bad JSON): 1",
                            f"  Manifest          : {resolved.completed_manifest_path}",
                        ]
                    ),
                )

            service.backfill_completed_manifest = fake_backfill  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service)
            resolved = _resolved(root)

            result = facade.run_completed_backfill_dry_run(resolved, {"timeout_seconds": 99999})

        self.assertTrue(result.ok)
        self.assertEqual(result.command, "maintenance.completed_backfill_dry_run")
        self.assertIn("9 sidecar(s)", result.message)
        self.assertFalse(result.data["writes_manifest"])
        self.assertEqual(result.data["sidecars_ingested"], "9")
        self.assertEqual(calls[-1]["dry_run"], True)
        self.assertEqual(calls[-1]["timeout_seconds"], 1800.0)
        self.assertIn("RunLogs", str(calls[-1]["checkpoint_path"]))
