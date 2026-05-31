from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.contracts import (
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
)
from app.contracts.config import DESKTOP_SCHEMA_CONFIG_KEYS, NETWORK_CONFIG_KEYS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "Pipeline" / "Schemas"
VOBSUB_CONFIG_KEYS = {
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "VobSubExtractLanguages",
    "VobSubOcrToolPath",
    "VobSubOcrTimeoutSeconds",
    "TreatVobSubSignsSongsAsForced",
}


class ContractTests(unittest.TestCase):
    def test_contract_schema_files_are_valid_json(self) -> None:
        expected = {
            "media_pipeline_pipeline_event.schema.json",
            "media_pipeline_process_file_result.schema.json",
            "media_pipeline_queue_plan_snapshot.schema.json",
            "media_pipeline_pending_push_manifest.schema.json",
            "media_pipeline_completed_job.schema.json",
            "media_pipeline_progress.schema.json",
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
            "product_version": "v6.000",
            "pipeline_version": "1.0",
            "data": {
                "schema_version": "process_file_result.v1",
                "success": True,
                "output_path": r"C:\Media\Out\Movie.mkv",
            },
        }

        event = PipelineEvent.from_mapping(payload)

        self.assertEqual(event.event_type, "job_completed")
        self.assertEqual(event.product_version, "v6.000")
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
        self.assertEqual(record.return_code, 7)
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
        }

        result = ProcessFileResult.from_mapping(payload)

        self.assertTrue(result.success)
        self.assertEqual(result.source_name, "Movie.mkv")
        self.assertEqual(result.output_size_bytes, 42)

    def test_queue_snapshot_contract_accepts_route_preview_rows(self) -> None:
        payload = {
            "schema_version": "queue_plan_snapshot.v1",
            "produced_at": "2026-05-06T12:00:00Z",
            "movie_count_total": 1,
            "tv_count_total": 0,
            "priority_count": 0,
            "runnable_count": 1,
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

    def test_queue_snapshot_builder_records_deterministic_preflight_block_codes(self) -> None:
        source = (PROJECT_ROOT / "engine" / "queue" / "pipeline_engine.ps1").read_text(encoding="utf-8")

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
        payload = {
            "schema_version": "pending_push_manifest.v1",
            "parked_at": "2026-05-06T12:00:00Z",
            "product_version": "v6.000",
            "pipeline_version": "4",
            "publish_transaction_id": "tx",
            "manifest_state": "parked",
            "local_file": r"C:\Scratch\Pending\Movie.mkv",
            "original_local_file": r"C:\Scratch\Movie.mkv",
            "parked_file": r"C:\Scratch\Pending\Movie.mkv",
            "server_out": r"\\server\Movies\Movie.mkv",
            "route": "remux",
            "source_path": r"C:\Media\Source\Movie.mkv",
            "source_size": 42,
            "output_size": 42,
            "publish_mode": "deferred",
            "sidecar_files": [],
            "tx3g_srt_conversion_enabled": True,
        }

        manifest = PendingPushManifest.from_mapping(payload)

        self.assertEqual(manifest.manifest_state, "parked")
        self.assertEqual(manifest.product_version, "v6.000")
        self.assertTrue(manifest.tx3g_srt_conversion_enabled)

    def test_pending_push_manifest_states_match_schema_enum(self) -> None:
        schema = json.loads((SCHEMA_DIR / "media_pipeline_pending_push_manifest.schema.json").read_text(encoding="utf-8"))
        schema_states = set(schema["properties"]["manifest_state"]["enum"])

        self.assertEqual(schema_states, PENDING_PUSH_MANIFEST_STATES)

    def test_pending_push_manifest_contract_accepts_recovery_and_sidecar_retry_states(self) -> None:
        base = {
            "schema_version": "pending_push_manifest.v1",
            "publish_transaction_id": "tx",
            "local_file": r"C:\Scratch\Pending\Movie.mkv",
            "server_out": r"\\server\Movies\Movie.mkv",
        }
        for state in ("parked_recovered", "retry_sidecar_failed"):
            with self.subTest(state=state):
                manifest = PendingPushManifest.from_mapping({**base, "manifest_state": state})
                self.assertEqual(manifest.manifest_state, state)

    def test_completed_job_contract_accepts_sidecar_schema_manifest_entries(self) -> None:
        payload = {
            "schema_version": "pipeline_sidecar.v1",
            "product_version": "v6.000",
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
        self.assertEqual(completed.product_version, "v6.000")
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

    def test_pending_push_manifest_rejects_unknown_current_state(self) -> None:
        with self.assertRaises(ContractError):
            PendingPushManifest.from_mapping(
                {
                    "schema_version": "pending_push_manifest.v1",
                    "publish_transaction_id": "tx",
                    "manifest_state": "mystery_state",
                    "local_file": r"C:\Scratch\Pending\Movie.mkv",
                    "server_out": r"\\server\Movies\Movie.mkv",
                }
            )

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
