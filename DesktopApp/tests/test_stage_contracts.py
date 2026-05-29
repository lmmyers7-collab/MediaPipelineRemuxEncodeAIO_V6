from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.contracts.stages import (
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
        "intent": "copy_to_scratch",
    },
    StageName.probe: {"scratch_path": r"D:\scratch\source.mkv"},
    StageName.decide: {
        "file_size_bytes": 10 * 1024 * 1024,
        "is_tv": False,
        "duration_seconds": 3600,
        "video_codec": "hevc",
        "video_height": 1080,
        "movie_route_max_video_bitrate_mbps": 35,
        "tv_route_max_video_bitrate_mbps": 18,
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
    StageName.ingest: (IngestResult, {"scratch_path": r"D:\scratch\source.mkv", "size_bytes": 1}),
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

    def test_stage_result_requires_data_or_structured_error(self) -> None:
        now = datetime.now(timezone.utc)
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
        schema_path = Path(__file__).resolve().parents[2] / "schemas" / "stages.v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        generated = StageContractSchema.model_json_schema()

        self.assertEqual(schema["$defs"], generated["$defs"])
        for contract in STAGE_REGISTRY.values():
            self.assertIn(contract.payload_model.__name__, schema["$defs"])
            self.assertIn(contract.result_model.__name__, schema["$defs"])


if __name__ == "__main__":
    unittest.main()
