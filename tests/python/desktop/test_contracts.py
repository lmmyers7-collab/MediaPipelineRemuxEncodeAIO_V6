from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.contracts import (
    ActiveJobRecord,
    CompletedJob,
    ContractError,
    ControlFlagRecord,
    PENDING_PUSH_MANIFEST_STATES,
    PendingPushManifest,
    PipelineEvent,
    ProcessFileResult,
    ProgressState,
    QueuePlanSnapshot,
    accepted_run_rows_fingerprint,
)
from mediapipeline.contracts.config import DESKTOP_SCHEMA_CONFIG_KEYS, NETWORK_CONFIG_KEYS


PROJECT_ROOT = find_repo_root(Path(__file__))
SCHEMA_DIR = PROJECT_ROOT / "ops" / "pipeline" / "config" / "schemas"
VOBSUB_CONFIG_KEYS = {
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "VobSubExtractLanguages",
    "VobSubOcrToolPath",
    "VobSubOcrTimeoutSeconds",
    "TreatVobSubSignsSongsAsForced",
}


def current_pending_manifest_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "pending_push_manifest.v1",
        "parked_at": "2026-05-06T12:00:00Z",
        "product_version": "2026.06.04.001",
        "pipeline_version": "4",
        "publish_transaction_id": "tx",
        "manifest_state": "parked",
        "local_file": r"C:\Scratch\Pending\Movie.mkv",
        "original_local_file": r"C:\Scratch\Movie.mkv",
        "parked_file": r"C:\Scratch\Pending\Movie.mkv",
        "server_out": r"\\server\Movies\Movie.mkv",
        "route": "remux",
        "route_reason_code": "container_only",
        "route_reason": "Container normalization only",
        "media_type": "movie",
        "source_identity": "source-v1",
        "source_identity_v2": "source-v2",
        "source_identity_v2_algorithm": "fixture-v2",
        "source_path": r"C:\Media\Source\Movie.mkv",
        "source_size": 42,
        "source_mtime_utc": "2026-05-06T11:59:00Z",
        "output_size": 42,
        "output_sha256": "a" * 64,
        "output_hash_algorithm": "SHA256",
        "publish_mode": "deferred",
        "sidecar_files": [],
        "tx3g_srt_tracks": [],
        "tx3g_srt_failures": [],
        "bdpgs_srt_failures": [],
        "vobsub_srt_failures": [],
        "tx3g_embedded_srt_tracks": [],
        "bdpgs_embedded_srt_tracks": [],
        "vobsub_embedded_srt_tracks": [],
        "tx3g_srt_conversion_enabled": False,
        "tx3g_external_srt_sidecars_enabled": False,
        "drop_tx3g_after_conversion": False,
        "bdpgs_srt_conversion_enabled": False,
        "drop_bdpgs_after_conversion": False,
        "vobsub_srt_conversion_enabled": False,
        "drop_vobsub_after_conversion": False,
    }
    payload.update(overrides)
    return payload


def powershell_pending_current_contract(payload: dict[str, object]) -> dict[str, object]:
    pwsh = PROJECT_ROOT / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
    module = PROJECT_ROOT / "ops" / "pipeline" / "engine" / "publish" / "pending_manifest_store.ps1"
    with tempfile.TemporaryDirectory() as raw_root:
        manifest_path = Path(raw_root) / "manifest.json"
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        environment = os.environ.copy()
        environment["MP_PENDING_PARITY_MODULE"] = str(module)
        environment["MP_PENDING_PARITY_MANIFEST"] = str(manifest_path)
        completed = subprocess.run(
            [
                str(pwsh),
                "-NoProfile",
                "-Command",
                ". $env:MP_PENDING_PARITY_MODULE; $manifest = Get-Content -LiteralPath $env:MP_PENDING_PARITY_MANIFEST -Raw | ConvertFrom-Json; Test-PendingManifestCurrentContractFields -Manifest $manifest -ManifestPath $env:MP_PENDING_PARITY_MANIFEST | ConvertTo-Json -Compress",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if completed.returncode != 0:
        raise AssertionError(
            f"PowerShell pending contract failed\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


class ContractTests(unittest.TestCase):
    def test_contract_schema_files_are_valid_json(self) -> None:
        expected = {
            "media_pipeline_pipeline_event.schema.json",
            "media_pipeline_process_file_result.schema.json",
            "media_pipeline_queue_plan_snapshot.schema.json",
            "media_pipeline_pending_push_manifest.schema.json",
            "media_pipeline_completed_job.schema.json",
            "media_pipeline_progress.schema.json",
            "media_pipeline_run_monitor.schema.json",
            "media_pipeline_control_flag.schema.json",
            "media_pipeline_config.schema.json",
        }
        for name in expected:
            with self.subTest(name=name):
                payload = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
                self.assertEqual(payload.get("$schema"), "https://json-schema.org/draft/2020-12/schema")
                self.assertIn("$id", payload)
                self.assertEqual(payload.get("type"), "object")

    def test_generated_config_contract_includes_cpu_encode_controls(self) -> None:
        payload = json.loads((SCHEMA_DIR / "media_pipeline_config.schema.json").read_text(encoding="utf-8"))
        properties = payload["properties"]

        self.assertEqual(
            properties["CpuEncodePreset"]["enum"],
            ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"],
        )
        self.assertEqual(
            properties["CpuEncodeProcessPriority"]["enum"],
            ["inherit", "idle", "belownormal", "normal", "abovenormal", "high"],
        )
        self.assertEqual(properties["CpuEncodeMaxThreads"]["minimum"], 0)
        self.assertEqual(properties["CpuEncodeMaxThreads"]["maximum"], 256)
        self.assertEqual(properties["FFmpegCpuEncodeTimeoutSeconds"]["minimum"], 1)

    def test_config_schema_covers_non_network_desktop_schema_keys(self) -> None:
        payload = json.loads((SCHEMA_DIR / "media_pipeline_config.schema.json").read_text(encoding="utf-8"))
        properties = set(payload["properties"])
        non_network_desktop_keys = set(DESKTOP_SCHEMA_CONFIG_KEYS) - set(NETWORK_CONFIG_KEYS)

        self.assertEqual(sorted(non_network_desktop_keys - properties), [])

    def test_generated_config_contract_includes_vobsub_controls(self) -> None:
        payload = json.loads((SCHEMA_DIR / "media_pipeline_config.schema.json").read_text(encoding="utf-8"))
        properties = payload["properties"]

        self.assertLessEqual(VOBSUB_CONFIG_KEYS, set(properties))
        self.assertEqual(properties["ConvertVobSubToSrt"]["type"], "boolean")
        self.assertEqual(properties["DropVobSubAfterConversion"]["type"], "boolean")
        self.assertEqual(properties["VobSubExtractLanguages"]["type"], "array")
        self.assertEqual(properties["VobSubExtractLanguages"]["items"]["type"], "string")
        self.assertEqual(properties["VobSubOcrToolPath"]["type"], "string")
        self.assertEqual(properties["VobSubOcrTimeoutSeconds"]["type"], "integer")
        self.assertEqual(properties["VobSubOcrTimeoutSeconds"]["minimum"], 60)
        self.assertEqual(properties["VobSubOcrTimeoutSeconds"]["maximum"], 14400)
        self.assertEqual(properties["TreatVobSubSignsSongsAsForced"]["type"], "boolean")

    def test_pipeline_event_contract_accepts_job_completed_shape(self) -> None:
        payload = {
            "schema_version": "pipeline_event.v1",
            "event_id": "abc",
            "event_type": "job_completed",
            "timestamp": "2026-05-06T12:00:00Z",
            "created_at": "2026-05-06T12:00:00Z",
            "stage": "completed",
            "route": "remux",
            "status": "succeeded",
            "source_path": r"C:\Media\Source\Movie.mkv",
            "product_version": "2026.06.04.001",
            "pipeline_version": "1.0",
            "data": {
                "schema_version": "process_file_result.v1",
                "success": True,
                "output_path": r"C:\Media\Out\Movie.mkv",
            },
        }

        event = PipelineEvent.from_mapping(payload)

        self.assertEqual(event.event_type, "job_completed")
        self.assertEqual(event.product_version, "2026.06.04.001")
        self.assertTrue(event.data["success"])
        self.assertEqual(event.to_mapping()["event_type"], "job_completed")

    def test_active_job_contract_accepts_launch_and_terminal_shape(self) -> None:
        payload = {
            "schema_version": "desktop_active_job.v1",
            "launch_id": "20260506_120000_pipeline_1234_abcd",
            "job_kind": "pipeline",
            "mode": "once",
            "status": "failed_immediate",
            "pid": 1234,
            "process_create_time": 1778083200.125,
            "app_pid": 4321,
            "command_line": "pwsh -File pipeline.ps1",
            "args": ["pwsh", "-File", "pipeline.ps1"],
            "cwd": r"C:\MediaPipeline",
            "stdout_log": r"C:\MediaPipeline\RunLogs\run.stdout.log",
            "stderr_log": r"C:\MediaPipeline\RunLogs\run.stderr.log",
            "show_console": False,
            "metadata": {"show_config": False},
            "launched_at": "2026-05-06T12:00:00-04:00",
            "last_update": "2026-05-06T12:00:01-04:00",
            "completed_at": "2026-05-06T12:00:01-04:00",
            "return_code": 7,
        }

        record = ActiveJobRecord.from_mapping(payload)

        self.assertEqual(record.job_kind, "pipeline")
        self.assertEqual(record.status, "failed_immediate")
        self.assertEqual(record.process_create_time, 1778083200.125)
        self.assertEqual(record.return_code, 7)
        self.assertEqual(record.to_mapping()["process_create_time"], 1778083200.125)
        self.assertEqual(record.to_mapping()["schema_version"], "desktop_active_job.v1")

    def test_control_flag_contract_accepts_pause_stop_rescan_shapes(self) -> None:
        for action, label in (("pause", "Pause"), ("stop", "Stop"), ("rescan", "Rescan")):
            with self.subTest(action=action):
                payload = {
                    "schema_version": "pipeline_control_flag.v1",
                    "action": action,
                    "label": label,
                    "request_id": f"{action}-1",
                    "created_at": "2026-05-06T12:00:00-04:00",
                    "app_pid": 123,
                }

                record = ControlFlagRecord.from_mapping(payload)

                self.assertEqual(record.action, action)
                self.assertEqual(record.label, label)
                self.assertEqual(record.to_mapping()["schema_version"], "pipeline_control_flag.v1")

    def test_control_flag_contract_accepts_correlated_stop_after_current(self) -> None:
        payload = {
            "schema_version": "pipeline_control_flag.v1",
            "action": "stop_after_current",
            "label": "Stop After Current",
            "request_id": "stop-after-current-1",
            "created_at": "2026-07-16T12:00:00-04:00",
            "app_pid": 123,
            "run_id": "run-once-123",
            "target_pid": 24680,
            "target_launch_id": "launch-123",
        }

        record = ControlFlagRecord.from_mapping(payload)

        self.assertEqual(record.action, "stop_after_current")
        self.assertEqual(record.run_id, "run-once-123")
        self.assertEqual(record.target_pid, 24680)
        self.assertEqual(record.target_launch_id, "launch-123")
        self.assertEqual(record.to_mapping(), payload)

    def test_control_flag_schema_exposes_correlated_stop_after_current(self) -> None:
        schema = json.loads((SCHEMA_DIR / "media_pipeline_control_flag.schema.json").read_text(encoding="utf-8"))

        self.assertIn("stop_after_current", schema["properties"]["action"]["enum"])
        self.assertEqual(schema["properties"]["run_id"]["type"], "string")
        self.assertEqual(schema["properties"]["target_pid"]["minimum"], 1)
        self.assertEqual(schema["properties"]["target_launch_id"]["type"], "string")
        self.assertTrue(schema["allOf"], "stop_after_current correlation must be represented in the JSON schema")

    def test_control_flag_contract_rejects_uncorrelated_stop_after_current(self) -> None:
        with self.assertRaisesRegex(ContractError, "requires run_id or target_pid correlation"):
            ControlFlagRecord.from_mapping(
                {
                    "schema_version": "pipeline_control_flag.v1",
                    "action": "stop_after_current",
                    "label": "Stop After Current",
                    "request_id": "stop-after-current-uncorrelated",
                    "created_at": "2026-07-16T12:00:00-04:00",
                }
            )

    def test_progress_contract_accepts_current_progress_shape(self) -> None:
        payload = {
            "ProgressVersion": 2,
            "LastUpdate": "2026-05-06 12:00:00",
            "SessionStartedAt": "2026-05-06T11:59:00",
            "CurrentFile": "Movie.mkv",
            "CurrentFileDisplay": "Movie.mkv",
            "CurrentFilePath": r"C:\Media\Movie.mkv",
            "CurrentMediaType": "movie",
            "CurrentLibraryId": "movies",
            "CurrentLibraryName": "Movies",
            "CurrentLibraryDesignation": "movie",
            "CurrentLibrarySourceRoot": r"C:\Media",
            "CurrentLibraryOutputRoot": r"D:\Plex\Movies",
            "CurrentQueuePhase": "movie",
            "CurrentQueueIndex": 1,
            "CurrentQueueTotal": 4,
            "CurrentRoute": "remux",
            "CurrentStage": "remux_mux",
            "CurrentStagePercent": 42.5,
            "CurrentItemStartedAt": "2026-05-06T12:00:00",
            "CurrentStageStartedAt": "2026-05-06T12:01:00",
            "CopyState": None,
            "PushState": None,
            "SidecarState": None,
            "AudioProgress": {
                "schema_version": "pipeline_audio_progress.v1",
                "action": "copy",
                "status": "Audio policy complete",
            },
            "PendingDrainProgress": {
                "schema_version": "pipeline_pending_drain_progress.v1",
                "manifest_count": 2,
                "attempted_count": 1,
            },
            "PauseRequested": False,
            "StopRequested": False,
            "ControlRequests": {"Pause": {"Requested": False}},
            "Status": "Processing",
            "TotalProcessed": 3,
            "Encoded": 1,
            "Remuxed": 2,
            "Failed": 0,
            "Movies": 3,
            "TVEpisodes": 0,
        }

        progress = ProgressState.from_mapping(payload)

        self.assertEqual(progress.progress_version, 2)
        self.assertEqual(progress.current_stage_percent, 42.5)
        self.assertEqual(progress.current_library_name, "Movies")
        self.assertEqual(progress.to_mapping()["CurrentQueueIndex"], 1)
        self.assertEqual(progress.to_mapping()["CurrentLibrarySourceRoot"], r"C:\Media")
        self.assertEqual(progress.to_mapping()["AudioProgress"]["schema_version"], "pipeline_audio_progress.v1")
        self.assertEqual(progress.to_mapping()["PendingDrainProgress"]["manifest_count"], 2)

    def test_process_result_contract_accepts_powershell_pascal_case_shape(self) -> None:
        payload = {
            "SchemaVersion": "process_file_result.v1",
            "Success": True,
            "Status": "processed",
            "QueueTerminal": True,
            "Retryable": False,
            "SourcePath": r"C:\Media\Source\Movie.mkv",
            "SourceName": "Movie.mkv",
            "Route": "remux",
            "OutputSizeBytes": 42,
            "PublishedPath": r"D:\Library\Movie.mkv",
            "ParkedPath": "",
            "IntendedFinalPath": r"D:\Library\Movie.mkv",
            "ManifestPath": "",
            "PipelineSidecarPath": r"D:\Library\Movie.mkv.pipeline.json",
            "SidecarPaths": [r"D:\Library\Movie.eng.srt", r"D:\Library\Movie.mkv.pipeline.json"],
            "PublishTransactionId": "publish-tx-1",
        }

        result = ProcessFileResult.from_mapping(payload)

        self.assertTrue(result.success)
        self.assertEqual(result.source_name, "Movie.mkv")
        self.assertEqual(result.output_size_bytes, 42)
        self.assertEqual(result.published_path, r"D:\Library\Movie.mkv")
        self.assertEqual(result.intended_final_path, r"D:\Library\Movie.mkv")
        self.assertEqual(result.pipeline_sidecar_path, r"D:\Library\Movie.mkv.pipeline.json")
        self.assertEqual(result.sidecar_paths, [r"D:\Library\Movie.eng.srt", r"D:\Library\Movie.mkv.pipeline.json"])
        self.assertEqual(result.publish_transaction_id, "publish-tx-1")

    def test_process_result_contract_defaults_absent_terminal_paths_for_backward_compatibility(self) -> None:
        result = ProcessFileResult.from_mapping(
            {
                "SchemaVersion": "process_file_result.v1",
                "Success": False,
                "Status": "failed",
            }
        )

        self.assertEqual(result.published_path, "")
        self.assertEqual(result.parked_path, "")
        self.assertEqual(result.intended_final_path, "")
        self.assertEqual(result.manifest_path, "")
        self.assertEqual(result.pipeline_sidecar_path, "")
        self.assertEqual(result.sidecar_paths, [])
        self.assertEqual(result.publish_transaction_id, "")

    def test_queue_snapshot_contract_accepts_route_preview_rows(self) -> None:
        payload = {
            "schema_version": "queue_plan_snapshot.v1",
            "produced_at": "2026-05-06T12:00:00Z",
            "movie_count_total": 1,
            "tv_count_total": 0,
            "priority_count": 0,
            "runnable_count": 1,
            "total_row_count": 2,
            "shown_row_count": 1,
            "row_limit": 500,
            "rows_truncated": True,
            "excluded_count": 1,
            "excluded_row_limit": 500,
            "excluded_rows_truncated": False,
            "excluded_rows": [
                {
                    "source_order": 1,
                    "reason_code": "already_processed",
                    "reason": "Already processed",
                    "phase": "movie",
                    "media_kind": "movie",
                    "source_path": r"C:\Media\Source\Existing.mkv",
                    "root_path": r"C:\Media\Source",
                    "display_name": "Existing.mkv",
                    "size_gb": 2.0,
                }
            ],
            "rows": [
                {
                    "global_order": 0,
                    "phase": "movie",
                    "media_kind": "movie",
                    "queue_index": 1,
                    "queue_total": 1,
                    "is_priority": False,
                    "source_path": r"C:\Media\Source\Movie.mkv",
                    "root_path": r"C:\Media\Source",
                    "display_name": "Movie.mkv",
                    "size_gb": 1.5,
                    "route": "REMUX",
                    "route_reason_code": "CONTAINER_ONLY",
                    "route_reason": "Container normalization only",
                    "route_decision_trace": [{"code": "size_evaluated"}],
                    "estimated_bitrate_mbps": 12.5,
                    "route_size_threshold_gb": 8.0,
                    "route_bitrate_threshold_mbps": 35.0,
                    "route_threshold_mode": "compatibility_advisory",
                    "size_over_threshold": False,
                    "bitrate_over_threshold": False,
                    "blocked_reason_code": "",
                    "blocked_reason": "",
                    "runtime_checks_deferred": True,
                    "runtime_check_codes": ["source_stability", "output_path_capability"],
                    "runtime_check_notes": [
                        "Source stability is checked by Test-FileStable only when processing starts.",
                        "Output path capability is checked by Test-OutputPathCapability only when processing starts.",
                    ],
                }
            ],
        }

        snapshot = QueuePlanSnapshot.from_mapping(payload)

        self.assertEqual(snapshot.runnable_count, 1)
        self.assertEqual(snapshot.total_row_count, 2)
        self.assertEqual(snapshot.shown_row_count, 1)
        self.assertEqual(snapshot.row_limit, 500)
        self.assertTrue(snapshot.rows_truncated)
        self.assertEqual(snapshot.rows[0].source_path, r"C:\Media\Source\Movie.mkv")
        self.assertEqual(snapshot.rows[0].route_decision_trace, [{"code": "size_evaluated"}])
        self.assertEqual(snapshot.rows[0].estimated_bitrate_mbps, 12.5)
        self.assertEqual(snapshot.rows[0].route_size_threshold_gb, 8.0)
        self.assertEqual(snapshot.rows[0].route_bitrate_threshold_mbps, 35.0)
        self.assertEqual(snapshot.rows[0].route_threshold_mode, "compatibility_advisory")
        self.assertFalse(snapshot.rows[0].size_over_threshold)
        self.assertFalse(snapshot.rows[0].bitrate_over_threshold)
        self.assertEqual(snapshot.rows[0].blocked_reason_code, "")
        self.assertTrue(snapshot.rows[0].runtime_checks_deferred)
        self.assertEqual(snapshot.rows[0].runtime_check_codes, ["source_stability", "output_path_capability"])
        self.assertEqual(snapshot.excluded_count, 1)
        self.assertEqual(snapshot.excluded_row_limit, 500)
        self.assertFalse(snapshot.excluded_rows_truncated)
        self.assertEqual(snapshot.excluded_rows[0].reason_code, "already_processed")

    def test_queue_snapshot_contract_preserves_planned_rename_display_name(self) -> None:
        payload = {
            "schema_version": "queue_plan_snapshot.v1",
            "produced_at": "2026-07-17T12:00:00Z",
            "runnable_count": 1,
            "accepted_run_rows": [
                {
                    "source_identity": "source-identity-1",
                    "source_identity_algorithm": "path_size_mtime_sha256.v1",
                    "source_path": r"C:\Media\Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv",
                    "display_name": "Django Unchained (2012).mkv",
                    "planned_display_name": "Django Unchained (2012).mkv",
                    "planned_display_name_source": "plex_destination_plan.v1",
                    "parent_context": r"C:\Media",
                    "run_queue_index": 1,
                    "run_queue_total": 1,
                    "route": "REMUX",
                    "route_reason_code": "CONTAINER_ONLY",
                    "route_reason": "Container normalization only",
                }
            ],
        }
        payload["accepted_run_rows_fingerprint_schema"] = "accepted_run_rows_fingerprint.v1"
        payload["accepted_run_rows_fingerprint"] = accepted_run_rows_fingerprint(
            payload["accepted_run_rows"]
        )

        snapshot = QueuePlanSnapshot.from_mapping(payload)
        accepted = snapshot.accepted_run_rows[0]

        self.assertEqual(accepted.display_name, "Django Unchained (2012).mkv")
        self.assertEqual(accepted.planned_display_name, "Django Unchained (2012).mkv")
        self.assertEqual(accepted.planned_display_name_source, "plex_destination_plan.v1")
        self.assertEqual(
            accepted.source_path,
            r"C:\Media\Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv",
        )
        self.assertTrue(snapshot.accepted_run_rows_fingerprint_is_valid)

        payload["accepted_run_rows"][0]["planned_display_name"] = "Tampered Raw Release.mkv"
        self.assertFalse(
            QueuePlanSnapshot.from_mapping(payload).accepted_run_rows_fingerprint_is_valid
        )
        payload["accepted_run_rows"][0]["planned_display_name"] = "Django Unchained (2012).mkv"

        payload["accepted_run_rows"][0]["display_name"] = "  "
        with self.assertRaisesRegex(ContractError, "display_name"):
            QueuePlanSnapshot.from_mapping(payload)

    def test_accepted_run_rows_fingerprint_matches_unicode_cross_runtime_vector(self) -> None:
        row = {
            "run_queue_index": 1,
            "run_queue_total": 1,
            "source_identity": "source-straße-STRASSE",
            "source_identity_algorithm": "path_size_mtime_sha256.v1",
            "source_path": r"C:\Médien\Straße\STRASSE.mkv",
            "planned_display_name": "Straße and STRASSE (2026).mkv",
            "planned_display_name_source": "plex_destination_plan.v1",
            "parent_context": r"C:\Médien\Straße",
            "route": "remux",
            "route_reason_code": "compatible",
            "route_reason": "Preserve Straße and STRASSE distinctly",
            "intended_final_path": r"C:\Final\Straße and STRASSE (2026).mkv",
        }

        fingerprint = accepted_run_rows_fingerprint([row])
        self.assertEqual(
            fingerprint,
            "ace99b28d58a6f32177a320dbfddb64781e10cfea8d773fd7ab6ca1bbe27cd63",
        )
        ascii_case_variant = dict(row, source_path=r"c:\Médien\Straße\strasse.mkv")
        self.assertEqual(accepted_run_rows_fingerprint([ascii_case_variant]), fingerprint)
        unicode_text_change = dict(row, source_path=r"C:\Médien\STRASSE\STRASSE.mkv")
        self.assertNotEqual(accepted_run_rows_fingerprint([unicode_text_change]), fingerprint)

    def test_accepted_workload_ignores_render_only_name_but_binds_production_name(self) -> None:
        row = {
            "run_queue_index": 1,
            "run_queue_total": 1,
            "source_identity": "stable-source-identity",
            "source_identity_algorithm": "path_size_mtime_sha256.v1",
            "source_path": r"C:\Media\Raw.Release.Name.mkv",
            "display_name": "Queue render label A",
            "planned_display_name": "Canonical Movie (2026).mkv",
            "planned_display_name_source": "plex_destination_plan.v1",
            "parent_context": r"C:\Media",
            "route": "remux",
            "route_reason_code": "copy_compatible",
            "route_reason": "Already compatible",
            "intended_final_path": r"C:\Final\Canonical Movie (2026).mkv",
        }
        baseline = accepted_run_rows_fingerprint([row])

        self.assertEqual(
            accepted_run_rows_fingerprint([{**row, "display_name": "Queue render label B"}]),
            baseline,
        )
        self.assertNotEqual(
            accepted_run_rows_fingerprint(
                [
                    {
                        **row,
                        "planned_display_name": "Operator Canonical Movie (2026).mkv",
                        "intended_final_path": r"C:\Final\Operator Canonical Movie (2026).mkv",
                    }
                ]
            ),
            baseline,
        )
        self.assertNotEqual(
            accepted_run_rows_fingerprint(
                [
                    {
                        **row,
                        "source_identity": "replacement-source-identity",
                        "source_path": r"C:\Media\Replacement.mkv",
                    }
                ]
            ),
            baseline,
        )

    def test_queue_snapshot_path_uniqueness_preserves_non_ascii_distinctions(self) -> None:
        rows = [
            {
                "source_identity": "source-straße",
                "source_identity_algorithm": "path_size_mtime_sha256.v1",
                "source_path": r"C:\Médien\Straße\Same.mkv",
                "display_name": "Straße (2026).mkv",
                "planned_display_name": "Straße (2026).mkv",
                "planned_display_name_source": "plex_destination_plan.v1",
                "parent_context": r"C:\Médien\Straße",
                "run_queue_index": 1,
                "run_queue_total": 2,
                "route": "remux",
                "route_reason_code": "compatible",
                "route_reason": "Compatible streams",
                "intended_final_path": r"C:\Final\Straße (2026).mkv",
            },
            {
                "source_identity": "source-STRASSE",
                "source_identity_algorithm": "path_size_mtime_sha256.v1",
                "source_path": r"C:\Médien\STRASSE\Same.mkv",
                "display_name": "STRASSE (2026).mkv",
                "planned_display_name": "STRASSE (2026).mkv",
                "planned_display_name_source": "plex_destination_plan.v1",
                "parent_context": r"C:\Médien\STRASSE",
                "run_queue_index": 2,
                "run_queue_total": 2,
                "route": "remux",
                "route_reason_code": "compatible",
                "route_reason": "Compatible streams",
                "intended_final_path": r"C:\Final\STRASSE (2026).mkv",
            },
        ]

        def snapshot_payload(accepted_rows: list[dict[str, object]]) -> dict[str, object]:
            return {
                "schema_version": "queue_plan_snapshot.v1",
                "produced_at": "2026-07-18T12:00:00Z",
                "runnable_count": len(accepted_rows),
                "accepted_run_rows_fingerprint_schema": "accepted_run_rows_fingerprint.v1",
                "accepted_run_rows_fingerprint": accepted_run_rows_fingerprint(accepted_rows),
                "accepted_run_rows": accepted_rows,
                "rows": [],
                "excluded_rows": [],
            }

        distinct = QueuePlanSnapshot.from_mapping(snapshot_payload(rows))

        self.assertEqual(len(distinct.accepted_run_rows), 2)
        self.assertTrue(distinct.accepted_run_rows_fingerprint_is_valid)

        duplicate_rows = [dict(row) for row in rows]
        duplicate_rows[1]["source_path"] = r"c:\médien\straße\same.mkv"
        with self.assertRaisesRegex(ContractError, "unique source identities and paths"):
            QueuePlanSnapshot.from_mapping(snapshot_payload(duplicate_rows))

    def test_queue_snapshot_builder_records_deterministic_preflight_block_codes(self) -> None:
        queue_root = PROJECT_ROOT / "ops" / "pipeline" / "engine" / "queue"
        source = "\n".join(
            (
                queue_root / "pipeline_engine.ps1",
                queue_root / "snapshot_rows.ps1",
            )[index].read_text(encoding="utf-8")
            for index in range(2)
        )

        self.assertIn("function Get-QueuePlanPreflightBlock", source)
        self.assertIn("$runtimeChecksDeferred = $true", source)
        self.assertIn("'source_stability', 'output_path_capability'", source)
        self.assertIn("runtime_checks_deferred = [bool]$runtimeChecksDeferred", source)
        self.assertIn("'bad_extension'", source)
        self.assertIn("'source_failure_operator_required'", source)
        self.assertIn("'source_failure_permanent'", source)
        self.assertIn("'tv_parse_unreliable'", source)
        self.assertIn("'already_processed_check_failed'", source)
        self.assertRegex(source, r"blocked_reason_code\s+=\s+\$blockedCode")

    def test_pending_push_manifest_contract_accepts_current_manifest_shape(self) -> None:
        payload = current_pending_manifest_payload(
            sidecar_files=[
                {
                    "local_file": r"C:\Scratch\Pending\Movie.eng.srt",
                    "server_out": r"\\server\Movies\Movie.eng.srt",
                    "output_size": 12,
                    "output_sha256": "b" * 64,
                    "output_hash_algorithm": "SHA256",
                }
            ],
            tx3g_srt_tracks=[{"language": "eng"}],
            vobsub_srt_failures=[{"reason": "ocr unavailable"}],
            tx3g_embedded_srt_tracks=[{"language": "eng"}],
            vobsub_embedded_srt_tracks=[{"language": "eng"}],
            tx3g_srt_conversion_enabled=True,
            vobsub_srt_conversion_enabled=True,
        )

        manifest = PendingPushManifest.from_mapping(payload)

        self.assertEqual(manifest.manifest_state, "parked")
        self.assertEqual(manifest.product_version, "2026.06.04.001")
        self.assertEqual(manifest.media_type, "movie")
        self.assertEqual(manifest.source_mtime_utc, "2026-05-06T11:59:00Z")
        self.assertEqual(manifest.vobsub_srt_failures, [{"reason": "ocr unavailable"}])
        self.assertEqual(manifest.vobsub_embedded_srt_tracks, [{"language": "eng"}])
        self.assertTrue(manifest.tx3g_srt_conversion_enabled)
        self.assertTrue(manifest.vobsub_srt_conversion_enabled)

    def test_pending_push_manifest_states_match_schema_enum(self) -> None:
        schema = json.loads((SCHEMA_DIR / "media_pipeline_pending_push_manifest.schema.json").read_text(encoding="utf-8"))
        schema_states = set(schema["properties"]["manifest_state"]["enum"])

        self.assertEqual(schema_states, PENDING_PUSH_MANIFEST_STATES)
        for field in (
            "media_type",
            "source_mtime_utc",
            "vobsub_srt_failures",
            "vobsub_embedded_srt_tracks",
            "vobsub_srt_conversion_enabled",
            "drop_vobsub_after_conversion",
        ):
            self.assertIn(field, schema["properties"])
        for field in (
            "pipeline_version",
            "publish_transaction_id",
            "manifest_state",
            "local_file",
            "server_out",
            "route",
            "source_identity_v2",
            "source_identity_v2_algorithm",
            "source_path",
            "output_size",
            "output_sha256",
            "output_hash_algorithm",
            "sidecar_files",
            "tx3g_srt_tracks",
            "tx3g_srt_failures",
            "bdpgs_srt_failures",
            "vobsub_srt_failures",
            "tx3g_embedded_srt_tracks",
            "bdpgs_embedded_srt_tracks",
            "vobsub_embedded_srt_tracks",
        ):
            self.assertIn(field, schema["required"])
        for field in (
            "pipeline_version",
            "publish_transaction_id",
            "manifest_state",
            "local_file",
            "server_out",
            "route",
            "source_identity_v2",
            "source_identity_v2_algorithm",
            "source_path",
        ):
            self.assertEqual(schema["properties"][field].get("minLength"), 1)
        self.assertEqual(
            set(schema["properties"]["sidecar_files"]["items"]["required"]),
            {
                "local_file",
                "server_out",
                "output_size",
                "output_sha256",
                "output_hash_algorithm",
            },
        )

    def test_pending_push_manifest_contract_accepts_recovery_and_sidecar_retry_states(self) -> None:
        for state in ("parked_recovered", "retry_sidecar_backup_failed", "retry_sidecar_failed"):
            with self.subTest(state=state):
                manifest = PendingPushManifest.from_mapping(current_pending_manifest_payload(manifest_state=state))
                self.assertEqual(manifest.manifest_state, state)

    def test_completed_job_contract_accepts_sidecar_schema_manifest_entries(self) -> None:
        payload = {
            "schema_version": "pipeline_sidecar.v1",
            "product_version": "2026.06.04.001",
            "pipeline_version": "4",
            "created_at": "2026-05-06T12:00:00Z",
            "encoded_at": "2026-05-06T12:00:00Z",
            "logged_at": "2026-05-06T12:01:00Z",
            "route": "encode",
            "output_file": "Movie.mkv",
            "output_path": r"\\server\Movies\Movie.mkv",
        }

        completed = CompletedJob.from_mapping(payload)

        self.assertEqual(completed.schema_version, "pipeline_sidecar.v1")
        self.assertEqual(completed.product_version, "2026.06.04.001")
        self.assertEqual(completed.output_file, "Movie.mkv")

    def test_contracts_reject_wrong_schema_version(self) -> None:
        with self.assertRaises(ContractError):
            PipelineEvent.from_mapping(
                {
                    "schema_version": "pipeline_event.v0",
                    "event_id": "abc",
                    "event_type": "job_started",
                    "timestamp": "2026-05-06T12:00:00Z",
                    "created_at": "2026-05-06T12:00:00Z",
                    "data": {},
                }
            )

    def test_active_job_contract_rejects_unknown_current_status(self) -> None:
        with self.assertRaises(ContractError):
            ActiveJobRecord.from_mapping(
                {
                    "schema_version": "desktop_active_job.v1",
                    "launch_id": "launch",
                    "job_kind": "pipeline",
                    "status": "mystery",
                    "args": [],
                    "metadata": {},
                }
            )

    def test_control_flag_contract_rejects_unknown_action(self) -> None:
        with self.assertRaises(ContractError):
            ControlFlagRecord.from_mapping(
                {
                    "schema_version": "pipeline_control_flag.v1",
                    "action": "kill",
                    "label": "Kill",
                    "request_id": "kill-1",
                    "created_at": "2026-05-06T12:00:00-04:00",
                }
            )

    def test_active_job_contract_accepts_orphaned_reconciliation_status(self) -> None:
        record = ActiveJobRecord.from_mapping(
            {
                "schema_version": "desktop_active_job.v1",
                "launch_id": "launch",
                "job_kind": "pipeline",
                "status": "orphaned",
                "args": [],
                "metadata": {},
            }
        )

        self.assertEqual(record.status, "orphaned")

    def test_active_job_contract_accepts_kill_degraded_reconciliation_status(self) -> None:
        record = ActiveJobRecord.from_mapping(
            {
                "schema_version": "desktop_active_job.v1",
                "launch_id": "launch",
                "job_kind": "rerun_csv",
                "status": "kill_degraded",
                "args": [],
                "metadata": {},
            }
        )

        self.assertEqual(record.status, "kill_degraded")

    def test_pending_push_manifest_rejects_unknown_current_state(self) -> None:
        with self.assertRaises(ContractError):
            PendingPushManifest.from_mapping(current_pending_manifest_payload(manifest_state="mystery_state"))

    def test_pending_push_manifest_rejects_blank_required_current_fields(self) -> None:
        for field in (
            "pipeline_version",
            "publish_transaction_id",
            "manifest_state",
            "local_file",
            "server_out",
            "route",
            "source_identity_v2",
            "source_identity_v2_algorithm",
            "source_path",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ContractError):
                    PendingPushManifest.from_mapping(current_pending_manifest_payload(**{field: "  "}))

    def test_pending_push_manifest_rejects_missing_required_arrays_and_output_size(self) -> None:
        for field in (
            "sidecar_files",
            "tx3g_srt_tracks",
            "tx3g_srt_failures",
            "bdpgs_srt_failures",
            "vobsub_srt_failures",
            "tx3g_embedded_srt_tracks",
            "bdpgs_embedded_srt_tracks",
            "vobsub_embedded_srt_tracks",
            "output_size",
        ):
            payload = current_pending_manifest_payload()
            payload.pop(field)
            with self.subTest(field=field):
                with self.assertRaises(ContractError):
                    PendingPushManifest.from_mapping(payload)

    def test_pending_push_manifest_requires_media_and_sidecar_sha256_proof(self) -> None:
        for field in ("output_sha256", "output_hash_algorithm"):
            payload = current_pending_manifest_payload()
            payload.pop(field)
            with self.subTest(field=field):
                with self.assertRaises(ContractError):
                    PendingPushManifest.from_mapping(payload)

        for field in (
            "local_file",
            "server_out",
            "output_size",
            "output_sha256",
            "output_hash_algorithm",
        ):
            sidecar = {
                "local_file": r"C:\Scratch\Pending\Movie.eng.srt",
                "server_out": r"\\server\Movies\Movie.eng.srt",
                "output_size": 12,
                "output_sha256": "b" * 64,
                "output_hash_algorithm": "SHA256",
            }
            sidecar.pop(field)
            with self.subTest(sidecar_field=field):
                with self.assertRaises(ContractError):
                    PendingPushManifest.from_mapping(
                        current_pending_manifest_payload(sidecar_files=[sidecar])
                    )

    def test_python_and_powershell_current_manifest_hash_contracts_agree(self) -> None:
        payload = current_pending_manifest_payload(
            sidecar_files=[
                {
                    "local_file": r"C:\Scratch\Pending\Movie.eng.srt",
                    "server_out": r"\\server\Movies\Movie.eng.srt",
                    "output_size": 12,
                    "output_sha256": "b" * 64,
                    "output_hash_algorithm": "SHA256",
                }
            ]
        )
        PendingPushManifest.from_mapping(payload)
        self.assertTrue(powershell_pending_current_contract(payload)["Ok"])

        payload.pop("output_sha256")
        with self.assertRaises(ContractError):
            PendingPushManifest.from_mapping(payload)
        powershell_result = powershell_pending_current_contract(payload)
        self.assertFalse(powershell_result["Ok"])
        self.assertEqual(powershell_result["ReasonCode"], "OUTPUT_HASH_MISSING")

    def test_progress_contract_rejects_invalid_percent(self) -> None:
        with self.assertRaises(ContractError):
            ProgressState.from_mapping(
                {
                    "ProgressVersion": 2,
                    "LastUpdate": "2026-05-06 12:00:00",
                    "Status": "Processing",
                    "CurrentStagePercent": 101,
                    "CurrentQueueIndex": 0,
                    "CurrentQueueTotal": 0,
                    "ControlRequests": {},
                    "TotalProcessed": 0,
                    "Encoded": 0,
                    "Remuxed": 0,
                    "Failed": 0,
                    "Movies": 0,
                    "TVEpisodes": 0,
                }
            )


if __name__ == "__main__":
    unittest.main()
