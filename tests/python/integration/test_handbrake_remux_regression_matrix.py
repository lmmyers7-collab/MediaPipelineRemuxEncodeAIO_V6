from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any

from mediapipeline.core.config.preset_migration import (
    effective_decision_policy_from_legacy_or_preset,
    effective_decision_policy_from_preset_v2,
    preset_v2_from_legacy_config,
)
from mediapipeline.core.config.preset_policy import PresetV2
from mediapipeline.contracts.pipeline_plan import PIPELINE_PLAN_SCHEMA_VERSION
from mediapipeline.contracts.decision_policy import EffectiveDecisionPolicy
from mediapipeline.contracts.source_media import SourceMediaInfo, source_media_from_ffprobe
from mediapipeline.contracts.verification import evaluate_output_size_check, verification_result_from_size_check
from mediapipeline.core.decide.routing import build_processing_decision
from mediapipeline.core.orchestration.planner import build_pipeline_plan, build_pipeline_plan_from_preset


REPO_ROOT = find_repo_root(Path(__file__))
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def source_from_fixture(name: str, **overrides: Any) -> SourceMediaInfo:
    raw = copy.deepcopy(load_fixture(name))
    source_updates = overrides.pop("source", {})
    format_updates = overrides.pop("format", {})
    remove_subtitles = bool(overrides.pop("remove_subtitles", False))

    raw.setdefault("source", {}).update(source_updates)
    raw.setdefault("format", {}).update(format_updates)
    if remove_subtitles:
        raw["streams"] = [stream for stream in raw.get("streams", []) if stream.get("codec_type") != "subtitle"]
    if overrides:
        raise AssertionError(f"Unhandled source fixture overrides: {sorted(overrides)}")
    return source_media_from_ffprobe(raw)


def reason_codes(decision) -> set[str]:
    return {reason.code for reason in decision.route_reasons}


def advisory_codes(decision) -> set[str]:
    return {reason.code for reason in decision.advisory_warnings}


def step_operations(plan) -> list[str]:
    return [step.operation for command_plan in plan.command_plans for step in command_plan.steps]


class HandBrakeRemuxRegressionMatrixTests(unittest.TestCase):
    def test_route_matrix_preserves_copy_remux_encode_regression_cases(self) -> None:
        mp4_source_factory = lambda: source_from_fixture(
            "tv_h264_1080p_12mbps_mkv.json",
            source={"path": "fixtures/container_only_h264_1080p.mp4"},
            format={"format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            remove_subtitles=True,
        )

        cases = [
            {
                "name": "TV under bitrate cap",
                "source": lambda: source_from_fixture("tv_h264_1080p_12mbps_mkv.json"),
                "policy": EffectiveDecisionPolicy(),
                "route": {"COPY", "REMUX"},
                "video": "copy",
                "reasons": {"VIDEO_BITRATE_UNDER_DIRECT_COPY_CAP", "SOURCE_CODEC_COMPATIBLE"},
                "forbidden_steps": {"encode_video"},
            },
            {
                "name": "TV over bitrate cap",
                "source": lambda: source_from_fixture("tv_h264_1080p_24mbps_mkv.json"),
                "policy": EffectiveDecisionPolicy(),
                "route": {"ENCODE"},
                "video": "encode",
                "reasons": {"VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP"},
                "required_steps": {"encode_video"},
            },
            {
                "name": "Movie 1080p over bucket bitrate cap",
                "source": lambda: source_from_fixture("movie_h264_1080p_30mbps_mkv.json"),
                "policy": EffectiveDecisionPolicy(),
                "route": {"ENCODE"},
                "video": "encode",
                "reasons": {"VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP"},
                "required_steps": {"encode_video"},
            },
            {
                "name": "Movie over bitrate cap",
                "source": lambda: source_from_fixture("movie_h264_1080p_45mbps_mkv.json"),
                "policy": EffectiveDecisionPolicy(),
                "route": {"ENCODE"},
                "video": "encode",
                "reasons": {"VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP"},
                "required_steps": {"encode_video"},
            },
            {
                "name": "Incompatible codec",
                "source": lambda: source_from_fixture("avi_mpeg2_480p.json"),
                "policy": EffectiveDecisionPolicy(),
                "route": {"ENCODE"},
                "video": "encode",
                "reasons": {"SOURCE_CODEC_INCOMPATIBLE"},
                "required_steps": {"encode_video"},
            },
            {
                "name": "Container-only remux",
                "source": mp4_source_factory,
                "policy": EffectiveDecisionPolicy(output_container="mkv"),
                "route": {"REMUX"},
                "video": "copy",
                "container": "remux",
                "reasons": {"CONTAINER_REMUX_ONLY"},
                "forbidden_steps": {"encode_video"},
            },
            {
                "name": "Filter forces encode",
                "source": lambda: source_from_fixture("tv_h264_1080p_12mbps_mkv.json"),
                "policy": EffectiveDecisionPolicy(video_filter_names=["deinterlace"]),
                "route": {"ENCODE"},
                "video": "encode",
                "reasons": {"FILTERS_ENABLED_ENCODE_REQUIRED"},
                "required_steps": {"encode_video"},
            },
            {
                "name": "Resolution over cap",
                "source": lambda: source_from_fixture("movie_hevc_4k_hdr_high_bitrate_mkv.json"),
                "policy": EffectiveDecisionPolicy(resolution_limit="1080p"),
                "route": {"ENCODE"},
                "video": "encode",
                "reasons": {"RESOLUTION_EXCEEDS_LIMIT"},
                "required_steps": {"encode_video"},
                "output_height": 1080,
            },
            {
                "name": "Audio-only incompatibility",
                "source": lambda: source_from_fixture("multi_audio_tracks.json"),
                "policy": EffectiveDecisionPolicy(output_container="mp4"),
                "route": {"REMUX"},
                "video": "copy",
                "audio_actions": ["drop", "copy", "drop"],
                "reasons": {
                    "AUDIO_CODEC_INCOMPATIBLE_WITH_CONTAINER",
                    "AUDIO_TRANSCODE_REQUIRED",
                    "MP4_COMPATIBILITY_SINGLE_AUDIO_TRACK",
                },
                "forbidden_steps": {"encode_video"},
            },
            {
                "name": "Container x subtitle",
                "source": lambda: source_from_fixture("source_with_image_subtitles.json"),
                "policy": EffectiveDecisionPolicy(output_container="mp4"),
                "route": {"REJECT"},
                "video": "reject",
                "subtitle_actions": ["unknown", "unknown"],
                "reasons": {
                    "SUBTITLE_FORMAT_INCOMPATIBLE_WITH_CONTAINER",
                    "SUBTITLE_IMAGE_REQUIRES_EXPLICIT_REVIEW",
                },
            },
            {
                "name": "Subtitle burn-in",
                "source": lambda: source_from_fixture("source_with_image_subtitles.json"),
                "policy": EffectiveDecisionPolicy(subtitle_burn_in_forced=True),
                "route": {"ENCODE"},
                "video": "encode",
                "subtitle_actions": ["burn", "copy"],
                "reasons": {"SUBTITLE_BURN_IN_REQUIRES_ENCODE"},
                "required_steps": {"burn_subtitle", "encode_video"},
            },
            {
                "name": "Missing bitrate and unknown media type",
                "source": lambda: source_from_fixture("unknown_bitrate_source.json"),
                "policy": EffectiveDecisionPolicy(),
                "route": {"COPY", "REMUX", "UNKNOWN", "ENCODE"},
                "video": "copy",
                "advisories": {"MISSING_BITRATE_METADATA", "MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP"},
                "forbidden_steps": {"encode_video"},
            },
            {
                "name": "Missing duration ignores probe bitrate",
                "source": lambda: source_from_fixture(
                    "tv_h264_1080p_24mbps_mkv.json",
                    source={"file_size_bytes": 1024**3},
                    format={"duration": "0.0"},
                ),
                "policy": EffectiveDecisionPolicy(route_threshold_mode="bitrate"),
                "route": {"COPY", "REMUX"},
                "video": "copy",
                "advisories": {"MISSING_BITRATE_METADATA"},
                "forbidden_steps": {"encode_video"},
            },
        ]

        for case in cases:
            with self.subTest(case=case["name"]):
                source = case["source"]()
                decision = build_processing_decision(source, case["policy"])

                self.assertIn(decision.route_summary, case["route"])
                self.assertEqual(decision.stream_actions.video.action, case["video"])
                if "container" in case:
                    self.assertEqual(decision.stream_actions.container, case["container"])
                if "audio_actions" in case:
                    self.assertEqual([stream.action for stream in decision.stream_actions.audio], case["audio_actions"])
                if "subtitle_actions" in case:
                    self.assertEqual(
                        [stream.action for stream in decision.stream_actions.subtitles],
                        case["subtitle_actions"],
                    )
                self.assertTrue(case.get("reasons", set()).issubset(reason_codes(decision)))
                self.assertTrue(case.get("advisories", set()).issubset(advisory_codes(decision)))
                if "output_height" in case:
                    self.assertEqual(decision.planned_encode_output.video.output_height, case["output_height"])

                if decision.route_summary != "REJECT":
                    plan = build_pipeline_plan(source, decision, plan_id=case["name"].lower().replace(" ", "-"))
                    operations = set(step_operations(plan))
                    self.assertTrue(plan.command_plans[0].dry_run_only)
                    self.assertFalse(plan.command_plans[0].can_execute)
                    self.assertTrue(case.get("required_steps", set()).issubset(operations))
                    self.assertFalse(case.get("forbidden_steps", set()).intersection(operations))

    def test_unprobeable_source_rejects_without_publish_plan(self) -> None:
        decision = build_processing_decision(SourceMediaInfo())

        self.assertEqual(decision.route_summary, "REJECT")
        self.assertEqual(decision.stream_actions.video.action, "reject")
        self.assertIn("SOURCE_UNPROBEABLE_REJECT", reason_codes(decision))
        self.assertEqual(decision.publish_requirements[0].code, "NO_PUBLISH_FOR_REJECTED_SOURCE")

    def test_output_size_check_matrix_separates_warn_block_and_fail(self) -> None:
        cases = [
            ("warn_only", "warning", 1, 0, 0, "record_advisory_warning"),
            ("block_publish", "blocked", 0, 0, 1, "park_pending_publish"),
            ("fail_job", "failed", 0, 1, 0, "fail_job"),
        ]

        for action, status, warnings, failures, blockers, on_fail in cases:
            with self.subTest(action=action):
                check = evaluate_output_size_check(
                    action=action,
                    source_size_bytes=100,
                    actual_output_size_bytes=130,
                    growth_tolerance_percent=10,
                )
                result = verification_result_from_size_check(check)

                self.assertEqual(check.status, status)
                self.assertEqual(check.on_fail, on_fail)
                self.assertEqual(len(result.advisory_warnings), warnings)
                self.assertEqual(len(result.failures), failures)
                self.assertEqual(len(result.publish_blockers), blockers)

    def test_legacy_config_and_v2_preset_feed_same_decision_and_plan_shape(self) -> None:
        source = source_from_fixture("multi_audio_tracks.json")
        legacy_config = {
            "RoutingProfile": "plex_direct_stream",
            "RouteThresholdMode": "compatibility_advisory",
            "SizeGuardMode": "advisory",
            "OutputContainer": "mp4",
            "RemuxSafeVideoCodecs": ["hevc", "h265", "h.265"],
            "AudioMaxChannels": 6,
            "Route1080pUpperHeightTolerancePercent": 11.111111,
            "Route1080pMaxVideoBitrateMbps": 20,
            "Route4KLowerHeightTolerancePercent": 16.666667,
            "Route4KMaxVideoBitrateMbps": 35,
        }
        preset = preset_v2_from_legacy_config(legacy_config, name="Matrix legacy parity")
        legacy_decision = build_processing_decision(source, effective_decision_policy_from_legacy_or_preset(legacy_config))
        v2_decision = build_processing_decision(source, effective_decision_policy_from_preset_v2(preset))
        plan = build_pipeline_plan_from_preset(source, preset, plan_id="legacy-v2-parity")

        self.assertEqual(v2_decision.route_summary, legacy_decision.route_summary)
        self.assertEqual(v2_decision.stream_actions.video.action, legacy_decision.stream_actions.video.action)
        self.assertEqual(
            [stream.action for stream in v2_decision.stream_actions.audio],
            [stream.action for stream in legacy_decision.stream_actions.audio],
        )
        self.assertEqual(plan.schema_version, PIPELINE_PLAN_SCHEMA_VERSION)
        self.assertEqual(plan.route_summary, "REMUX")
        self.assertTrue(plan.command_plans[0].dry_run_only)
        self.assertFalse(plan.command_plans[0].can_execute)

    def test_v2_preset_can_drive_encode_plan_and_block_publish_preview(self) -> None:
        source = source_from_fixture("tv_h264_1080p_12mbps_mkv.json")
        preset = PresetV2(
            name="Matrix v2 encode preview",
            dimensions={"resolutionLimit": "720p"},
            filters={"deinterlace": "decomb"},
            video={"codec": "hevc_nvenc", "targetMode": "constant_quality", "qualityTarget": 21},
            guards={"size": {"onExceeded": "block_publish"}},
        )

        plan = build_pipeline_plan_from_preset(source, preset, plan_id="v2-encode-block-publish")
        operations = set(step_operations(plan))

        self.assertEqual(plan.route_summary, "ENCODE")
        self.assertIn("encode_video", operations)
        self.assertIn("OUTPUT_SIZE_BLOCK_USES_PENDING_PUBLISH", {item["code"] for item in plan.publish_requirements})
        self.assertEqual(plan.verification_result.output_size_check.action, "block_publish")
        self.assertEqual(plan.effective_preset_snapshot["presetV2"]["name"], "Matrix v2 encode preview")


if __name__ == "__main__":
    unittest.main()
