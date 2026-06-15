from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, get_args, get_origin

from mediapipeline.tools.paths import find_repo_root

from pydantic import ValidationError

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


REPO_ROOT = find_repo_root(Path(__file__))

VALID_PAYLOADS = {
    StageName.ingest: {
        "source_path": r"C:\media\source.mkv",
        "scratch_root": r"D:\scratch",
        "intent": "copy_to_scratch",
    },
    StageName.probe: {"scratch_path": r"D:\scratch\source.mkv"},
    StageName.decide: {
        "file_size_bytes": 10 * 1024 * 1024,
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
    StageName.publish: {"output_path": r"D:\scratch\out.mkv", "final_root": r"Z:\Library", "intent": "dry_run"},
    StageName.drain: {"pending_publish_id": "pending-1", "final_root": r"Z:\Library", "intent": "dry_run"},
    StageName.rename: {"target_path": r"Z:\Library\Old.mkv", "proposed_name": "New.mkv", "intent": "dry_run"},
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

EXPECTED_JOURNAL_EVENTS = {
    StageName.ingest: "pipeline.stage.ingest",
    StageName.probe: "pipeline.stage.probe",
    StageName.decide: "pipeline.stage.decide",
    StageName.transcode: "pipeline.stage.transcode",
    StageName.subtitle_convert: "pipeline.stage.subtitle_convert",
    StageName.audio_mix: "pipeline.stage.audio_mix",
    StageName.publish: "pipeline.stage.publish",
    StageName.drain: "pipeline.stage.drain",
    StageName.rename: "pipeline.stage.rename",
}


class StageContractTests(unittest.TestCase):
    def test_every_stage_has_representative_payload_data_and_journal_event(self) -> None:
        for stage, contract in STAGE_REGISTRY.items():
            with self.subTest(stage=stage.value):
                request = build_stage_request(stage, VALID_PAYLOADS[stage])
                data_model, payload = VALID_DATA[stage]
                data = validate_stage_data(stage, payload)

                self.assertIsInstance(request.payload, contract.payload_model)
                self.assertIsInstance(data, data_model)
                self.assertEqual(contract.journal_event_type, EXPECTED_JOURNAL_EVENTS[stage])

    def test_stage_request_rejects_payload_for_wrong_stage(self) -> None:
        with self.assertRaises(ValidationError):
            StageRequest.model_validate({"stage": "probe", "payload": VALID_PAYLOADS[StageName.decide]})

    def test_mutation_capable_payloads_use_shared_intent_or_disabled_ingest_exception(self) -> None:
        exceptions: list[StageName] = []
        for stage, contract in STAGE_REGISTRY.items():
            if not contract.mutation_capable:
                continue
            intent = contract.payload_model.model_fields.get("intent")
            values = set(get_args(intent.annotation)) if intent and get_origin(intent.annotation) is Literal else set()
            if {"dry_run", "execute"}.issubset(values):
                continue
            exceptions.append(stage)

        self.assertEqual(exceptions, [StageName.ingest])
        self.assertFalse(STAGE_REGISTRY[StageName.ingest].enabled_in_entrypoint)

    def test_stage_result_requires_structured_error_on_failure(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        ok = StageResult.model_validate(
            {
                "stage": "decide",
                "ok": True,
                "started_at": now,
                "finished_at": now,
                "duration_ms": 0,
                "journal_event_type": "pipeline.stage.decide",
                "data": {"route": "remux"},
            }
        )
        self.assertTrue(ok.ok)

        with self.assertRaises(ValidationError):
            StageResult.model_validate(
                {
                    "stage": "decide",
                    "ok": False,
                    "started_at": now,
                    "finished_at": now,
                    "duration_ms": 0,
                    "journal_event_type": "pipeline.stage.decide",
                }
            )

    def test_generated_stage_schema_matches_contract(self) -> None:
        schema_path = REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "stages.v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        generated = StageContractSchema.model_json_schema()

        self.assertEqual(schema["$defs"], generated["$defs"])
        for contract in STAGE_REGISTRY.values():
            self.assertIn(contract.payload_model.__name__, schema["$defs"])
            self.assertIn(contract.result_model.__name__, schema["$defs"])


if __name__ == "__main__":
    unittest.main()
