from __future__ import annotations

import json
import sys
import unittest
import uuid
from datetime import datetime, timezone, UTC
from pathlib import Path
from typing import Literal, get_args, get_origin

from mediapipeline.tools.paths import find_repo_root

from pydantic import ValidationError

sys.path.insert(0, str(find_repo_root(Path(__file__))))

from mediapipeline.contracts.stages import (
    STAGE_REGISTRY,
    AudioMixResult,
    DecideResult,
    DrainResult,
    IngestResult,
    ProbeResult,
    PublishResult,
    RenameResult,
    StageContractSchema,
    StageName,
    StageRequest,
    StageResult,
    SubtitleConvertResult,
    TranscodeResult,
    build_stage_request,
    validate_stage_data,
)


VALID_PAYLOADS = {
    StageName.ingest: {
        "source_path": r"C:\media\source.mkv",
        "scratch_root": r"D:\scratch",
        "intent": "dry_run",
    },
    StageName.probe: {"scratch_path": r"D:\scratch\source.mkv"},
    StageName.decide: {
        "file_size_bytes": 10 * 1024 * 1024,
        "is_tv": False,
        "duration_seconds": 3600,
        "video_codec": "hevc",
        "video_height": 1080,
        "route_threshold_mode": "compatibility_advisory",
        "movie_route_max_video_bitrate_mbps": 35,
        "tv_route_max_video_bitrate_mbps": 18,
        "route_1080p_bucket_max_height": 1200,
        "route_1080p_max_video_bitrate_mbps": 20,
        "route_4k_bucket_min_height": 1800,
        "route_4k_max_video_bitrate_mbps": 35,
    },
    StageName.transcode: {
        "scratch_path": r"D:\scratch\source.mkv",
        "output_path": r"D:\scratch\out.mkv",
        "decision": {"route": "encode", "should_encode": True},
        "intent": "dry_run",
    },
    StageName.subtitle_convert: {
        "scratch_path": r"D:\scratch\source.mkv",
        "output_path": r"D:\scratch\out.mkv",
        "intent": "dry_run",
    },
    StageName.audio_mix: {
        "scratch_path": r"D:\scratch\source.mkv",
        "output_path": r"D:\scratch\out.mkv",
        "intent": "dry_run",
    },
    StageName.publish: {
        "output_path": r"D:\scratch\out.mkv",
        "final_root": r"Z:\Library",
        "intent": "dry_run",
    },
    StageName.drain: {
        "pending_publish_id": "pending-1",
        "final_root": r"Z:\Library",
        "intent": "dry_run",
    },
    StageName.rename: {
        "target_path": r"Z:\Library\Old.mkv",
        "proposed_name": "New.mkv",
        "intent": "dry_run",
    },
}


VALID_DATA = {
    StageName.ingest: (
        IngestResult,
        {
            "scratch_path": r"D:\scratch\source.mkv",
            "size_bytes": 1,
            "source_unchanged": True,
            "rollback_actions": ["delete scratch"],
            "recovery_actions": ["rerun ingest"],
            "boundary_checks": ["scratch target is a child of scratch_root"],
        },
    ),
    StageName.probe: (ProbeResult, {"probe_ok": True, "tool_path": r"C:\Tools\ffprobe.exe", "video_codec": "hevc"}),
    StageName.decide: (DecideResult, {"route": "remux", "should_encode": False}),
    StageName.transcode: (TranscodeResult, {"output_path": r"D:\scratch\out.mkv", "output_size_bytes": 1}),
    StageName.subtitle_convert: (SubtitleConvertResult, {"tracks_kept": 1}),
    StageName.audio_mix: (AudioMixResult, {"tracks_passed_through": 1}),
    StageName.publish: (PublishResult, {"final_path": r"Z:\Library\out.mkv"}),
    StageName.drain: (DrainResult, {"moved": 1}),
    StageName.rename: (RenameResult, {"final_path": r"Z:\Library\New.mkv"}),
}


class StageContractTests(unittest.TestCase):
    def test_every_stage_payload_and_data_model_validates(self) -> None:
        for stage, contract in STAGE_REGISTRY.items():
            with self.subTest(stage=stage.value):
                request = build_stage_request(stage, VALID_PAYLOADS[stage])
                self.assertIsInstance(request.payload, contract.payload_model)

                data_model, payload = VALID_DATA[stage]
                data = validate_stage_data(stage, payload)
                self.assertIsInstance(data, data_model)

    def test_stage_request_rejects_payload_for_wrong_stage(self) -> None:
        with self.assertRaises(ValidationError):
            StageRequest.model_validate(
                {
                    "stage": "probe",
                    "payload": VALID_PAYLOADS[StageName.decide],
                }
            )

    def test_mutation_payloads_require_explicit_intent_and_execute_confirmation(self) -> None:
        with self.assertRaises(ValidationError):
            build_stage_request(StageName.ingest, {"source_path": "source.mkv", "scratch_root": "D:\\Scratch"})
        with self.assertRaises(ValidationError):
            build_stage_request(
                StageName.ingest,
                {
                    "source_path": "source.mkv",
                    "scratch_root": "D:\\Scratch",
                    "intent": "execute",
                },
            )
        with self.assertRaises(ValidationError):
            build_stage_request(StageName.publish, {"output_path": "out.mkv", "final_root": "Z:\\Library"})
        with self.assertRaises(ValidationError):
            build_stage_request(
                StageName.rename,
                {
                    "target_path": "old.mkv",
                    "proposed_name": "new.mkv",
                    "intent": "execute",
                },
            )

    def test_execute_confirmations_reject_string_booleans(self) -> None:
        with self.assertRaises(ValidationError):
            build_stage_request(
                StageName.ingest,
                {
                    "source_path": "source.mkv",
                    "scratch_root": "D:\\Scratch",
                    "intent": "execute",
                    "confirm_ingest": "true",
                },
            )
        with self.assertRaises(ValidationError):
            build_stage_request(
                StageName.rename,
                {
                    "target_path": "old.mkv",
                    "proposed_name": "new.mkv",
                    "intent": "execute",
                    "confirm_apply": "true",
                },
            )
        request = build_stage_request(
            StageName.ingest,
                {
                    "source_path": "source.mkv",
                    "scratch_root": "D:\\Scratch",
                    "intent": "execute",
                    "confirm_ingest": True,
                    "operation_id": "b8ed5543-1370-46d5-868a-7fbf3596d525",
                    "scratch_reservation_id": "stage_ingest_reservation",
                    "dry_run_fingerprint": "a" * 64,
                },
        )
        self.assertTrue(request.payload.confirm_ingest)

    def test_ingest_execute_requires_a_valid_dry_run_operation_binding(self) -> None:
        operation_id = str(uuid.uuid4())
        base = {
            "source_path": "source.mkv",
            "scratch_root": "D:\\Scratch",
            "intent": "execute",
            "confirm_ingest": True,
            "operation_id": operation_id,
            "scratch_reservation_id": "stage_ingest_reservation",
        }
        with self.assertRaises(ValidationError):
            build_stage_request(StageName.ingest, base)
        with self.assertRaises(ValidationError):
            build_stage_request(
                StageName.ingest,
                {
                    **base,
                    "operation_id": "not-a-uuid",
                    "dry_run_fingerprint": "a" * 64,
                },
            )
        request = build_stage_request(
            StageName.ingest,
            {
                **base,
                "dry_run_fingerprint": "a" * 64,
            },
        )
        self.assertEqual(request.payload.operation_id, operation_id)

    def test_mutation_capable_payloads_use_shared_intent(self) -> None:
        exceptions: list[StageName] = []
        for stage, contract in STAGE_REGISTRY.items():
            if not contract.mutation_capable:
                continue
            intent = contract.payload_model.model_fields.get("intent")
            values = set(get_args(intent.annotation)) if intent and get_origin(intent.annotation) is Literal else set()
            if {"dry_run", "execute"}.issubset(values):
                continue
            exceptions.append(stage)

        self.assertEqual(exceptions, [])
        self.assertTrue(STAGE_REGISTRY[StageName.ingest].enabled_in_entrypoint)
        enabled_mutation_stages = [
            stage for stage, contract in STAGE_REGISTRY.items() if contract.mutation_capable and contract.enabled_in_entrypoint
        ]
        self.assertEqual(enabled_mutation_stages, [StageName.ingest])

    def test_stage_result_requires_data_or_structured_error(self) -> None:
        now = datetime.now(UTC)
        ok = StageResult.model_validate(
            {
                "stage": "decide",
                "ok": True,
                "started_at": now.isoformat(),
                "finished_at": now.isoformat(),
                "duration_ms": 0,
                "journal_event_type": "pipeline.stage.decide",
                "data": {"route": "remux"},
            }
        )
        self.assertTrue(ok.ok)

        failed = StageResult.model_validate(
            {
                "stage": "decide",
                "ok": False,
                "started_at": now.isoformat(),
                "finished_at": now.isoformat(),
                "duration_ms": 0,
                "journal_event_type": "pipeline.stage.decide",
                "error": {"code": "stage.invalid_payload", "message": "bad payload"},
            }
        )
        self.assertEqual(failed.error.code if failed.error else "", "stage.invalid_payload")

        with self.assertRaises(ValidationError):
            StageResult.model_validate(
                {
                    "stage": "decide",
                    "ok": False,
                    "started_at": now.isoformat(),
                    "finished_at": now.isoformat(),
                    "duration_ms": 0,
                    "journal_event_type": "pipeline.stage.decide",
                }
            )

    def test_generated_stage_schema_is_current_and_references_all_models(self) -> None:
        schema_path = find_repo_root(Path(__file__)) / "src" / "mediapipeline" / "contracts" / "schemas" / "stages.v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        generated = StageContractSchema.model_json_schema()
        size_guard_enum = schema["$defs"]["DecidePayload"]["properties"]["size_guard_mode"]["enum"]

        self.assertIn("fallback_remux", size_guard_enum)
        self.assertEqual(schema["$defs"], generated["$defs"])
        for contract in STAGE_REGISTRY.values():
            self.assertIn(contract.payload_model.__name__, schema["$defs"])
            self.assertIn(contract.result_model.__name__, schema["$defs"])


if __name__ == "__main__":
    unittest.main()
