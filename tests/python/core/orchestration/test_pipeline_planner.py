from __future__ import annotations

import json
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

from mediapipeline.core.config.preset_policy import PresetV2
from mediapipeline.contracts.pipeline_plan import PIPELINE_PLAN_SCHEMA_VERSION
from mediapipeline.contracts.decision_policy import EffectiveDecisionPolicy
from mediapipeline.contracts.source_media import SourceMediaInfo, source_media_from_ffprobe
from mediapipeline.core.decide.routing import build_processing_decision
from mediapipeline.core.orchestration.planner import build_pipeline_plan, build_pipeline_plan_from_preset


REPO_ROOT = find_repo_root(Path(__file__))
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def load_source(name: str) -> SourceMediaInfo:
    raw = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    return source_media_from_ffprobe(raw)


def step_operations(plan) -> list[str]:
    return [step.operation for command_plan in plan.command_plans for step in command_plan.steps]


class PipelinePlannerTests(unittest.TestCase):
    def test_copy_plan_keeps_source_payload_unchanged_when_container_is_kept(self) -> None:
        source = load_source("tv_h264_1080p_12mbps_mkv.json")
        decision = build_processing_decision(source, EffectiveDecisionPolicy(force_container_remux=False))

        plan = build_pipeline_plan(source, decision, plan_id="copy-plan")

        self.assertEqual(plan.schema_version, PIPELINE_PLAN_SCHEMA_VERSION)
        self.assertEqual(plan.route_summary, "COPY")
        self.assertTrue(plan.output.copy_unchanged_possible)
        self.assertEqual(step_operations(plan)[0], "copy_source")
        self.assertTrue(plan.command_plans[0].dry_run_only)
        self.assertFalse(plan.command_plans[0].can_execute)
        self.assertEqual(plan.verification_result.output_size_check.status, "disabled")
        self.assertTrue(any(item["code"] == "PENDING_PUBLISH_SAFETY_REQUIRED" for item in plan.publish_requirements))

    def test_remux_plan_is_distinct_from_encode_and_never_invokes_video_encode(self) -> None:
        source = load_source("tv_h264_1080p_12mbps_mkv.json")
        decision = build_processing_decision(source)

        plan = build_pipeline_plan(source, decision, plan_id="remux-plan")
        operations = step_operations(plan)
        preview = "\n".join(plan.command_plans[0].preview_lines).lower()

        self.assertEqual(plan.route_summary, "REMUX")
        self.assertIn("copy_video", operations)
        self.assertIn("mux_container", operations)
        self.assertNotIn("encode_video", operations)
        self.assertIn("why:", preview)
        self.assertNotIn("ffmpeg", preview)
        self.assertEqual(plan.runtime_fallbacks[0].fallback_id, "remux-codec-recheck")

    def test_encode_plan_includes_dimensions_filters_audio_external_srt_posture_and_container(self) -> None:
        source = load_source("tv_h264_1080p_12mbps_mkv.json")
        decision = build_processing_decision(
            source,
            EffectiveDecisionPolicy(
                output_container="mp4",
                resolution_limit="720p",
                video_filter_names=["deinterlace"],
                audio_force_transcode=True,
                video_output_codec="hevc_nvenc",
                video_target_mode="constant_quality",
                video_quality_target=21,
            ),
        )

        plan = build_pipeline_plan(source, decision, plan_id="encode-plan")
        operations = step_operations(plan)
        video_step = next(step for step in plan.command_plans[0].steps if step.operation == "encode_video")

        self.assertEqual(plan.route_summary, "ENCODE")
        self.assertIn("encode_video", operations)
        self.assertIn("transcode_audio", operations)
        self.assertIn("drop_subtitle", operations)
        self.assertNotIn("convert_subtitle", operations)
        self.assertNotIn("burn_subtitle", operations)
        self.assertIn("mux_container", operations)
        self.assertEqual(video_step.details["codec"], "hevc_nvenc")
        self.assertEqual(video_step.details["targetMode"], "constant_quality")
        self.assertEqual(video_step.details["qualityTarget"], 21)
        self.assertEqual(video_step.details["outputHeight"], 720)
        self.assertEqual(video_step.details["filters"], ["deinterlace"])
        self.assertEqual(plan.output.container, "mp4")
        self.assertEqual(plan.runtime_fallbacks[0].fallback_id, "nvenc-cpu-fallback")
        self.assertTrue(any(guard.code == "OUTPUT_SIZE_CHECK" for guard in plan.verification_guards))
        self.assertEqual(plan.verification_result.output_size_check.action, "warn_only")

    def test_rejected_mp4_image_subtitle_plan_has_no_command(self) -> None:
        source = load_source("source_with_image_subtitles.json")
        decision = build_processing_decision(source, EffectiveDecisionPolicy(output_container="mp4"))

        plan = build_pipeline_plan(source, decision, plan_id="reject-image-subtitles")

        self.assertEqual(plan.route_summary, "REJECT")
        self.assertEqual(plan.publish_strategy, "no_publish")
        self.assertEqual(step_operations(plan), ["no_command"])
        self.assertEqual(plan.command_plans[0].steps[0].details["routeSummary"], "REJECT")

    def test_plan_from_preset_carries_effective_preset_snapshot_and_publish_strategy(self) -> None:
        source = load_source("movie_h264_1080p_30mbps_mkv.json")
        preset = PresetV2(
            name="Deferred MP4 preview",
            container={"format": "mp4"},
            publish={"deferredPublish": True},
            guards={"size": {"onExceeded": "block_publish"}},
            video={"targetMode": "average_bitrate", "targetBitrateMbps": 8.0},
        )

        plan = build_pipeline_plan_from_preset(source, preset, plan_id="preset-plan")
        dumped = plan.model_dump(mode="json", by_alias=True)

        self.assertEqual(plan.publish_strategy, "park_pending_publish")
        self.assertTrue(any(item["code"] == "OUTPUT_SIZE_BLOCK_USES_PENDING_PUBLISH" for item in plan.publish_requirements))
        self.assertEqual(plan.effective_preset_snapshot["presetV2"]["name"], "Deferred MP4 preview")
        self.assertEqual(dumped["schemaVersion"], PIPELINE_PLAN_SCHEMA_VERSION)
        self.assertIn("commandPlans", dumped)
        self.assertEqual(dumped["intent"], "dry_run")

    def test_auto_plan_id_distinguishes_publish_policy_with_same_route(self) -> None:
        source = load_source("tv_h264_1080p_12mbps_mkv.json")

        base = build_pipeline_plan_from_preset(source, {"OutputContainer": "mkv"})
        deferred = build_pipeline_plan_from_preset(
            source,
            {"OutputContainer": "mkv", "DeferredPublish": True},
        )

        self.assertEqual(base.route_summary, deferred.route_summary)
        self.assertEqual(
            [reason.code for reason in base.reason_summary],
            [reason.code for reason in deferred.reason_summary],
        )
        self.assertEqual(base.publish_strategy, "publish_with_pending_safety")
        self.assertEqual(deferred.publish_strategy, "park_pending_publish")
        self.assertNotEqual(base.plan_id, deferred.plan_id)


if __name__ == "__main__":
    unittest.main()
