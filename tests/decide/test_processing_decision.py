from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.contracts.decision_policy import EffectiveDecisionPolicy
from app.contracts.source_media import SourceMediaInfo, source_media_from_ffprobe
from app.decide.processing_decision import REQUIRED_REASON_CODES
from app.decide.processing_decision import decision_policy_from_mapping
from app.decide.routing import build_processing_decision


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def load_source(name: str) -> SourceMediaInfo:
    raw = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    return source_media_from_ffprobe(raw)


def reason_codes(decision) -> set[str]:
    return {reason.code for reason in decision.route_reasons}


class ProcessingDecisionTests(unittest.TestCase):
    def test_required_reason_framework_is_available_without_emitting_future_reasons(self) -> None:
        self.assertIn("FILTERS_ENABLED_ENCODE_REQUIRED", REQUIRED_REASON_CODES)
        self.assertIn("SUBTITLE_BURN_IN_REQUIRES_ENCODE", REQUIRED_REASON_CODES)
        self.assertIn("AUDIO_TRANSCODE_REQUIRED", REQUIRED_REASON_CODES)

    def test_legacy_mapping_builds_abstract_effective_policy(self) -> None:
        policy = decision_policy_from_mapping(
            {
                "RoutingProfile": "plex_direct_play",
                "RouteThresholdMode": "bitrate",
                "EncodeThresholdGB": 9,
                "TVEncodeThresholdGB": 4,
                "MovieRouteMaxVideoBitrateMbps": 40,
                "TVRouteMaxVideoBitrateMbps": 20,
                "OutputContainer": "mp4",
                "RemuxSafeVideoCodecs": ["hevc", "h264"],
            }
        )

        self.assertEqual(policy.routing_profile, "plex_direct_play")
        self.assertEqual(policy.route_threshold_mode, "bitrate")
        self.assertEqual(policy.movie_route_size_limit_gb, 9)
        self.assertEqual(policy.tv_route_size_limit_gb, 4)
        self.assertEqual(policy.output_container, "mp4")
        self.assertEqual(policy.direct_copy_video_codecs, ["hevc", "h264"])

    def test_core_fixtures_match_current_route_characterization(self) -> None:
        cases = [
            (
                "tv_h264_1080p_12mbps_mkv.json",
                "REMUX",
                "copy",
                "remux",
                "plex_compatible_h264_remux",
                {"SOURCE_CODEC_COMPATIBLE", "VIDEO_BITRATE_UNDER_DIRECT_COPY_CAP", "RESOLUTION_UNDER_LIMIT"},
            ),
            (
                "tv_h264_1080p_24mbps_mkv.json",
                "ENCODE",
                "encode",
                "encode",
                "bitrate_over_threshold",
                {"VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP"},
            ),
            (
                "movie_h264_1080p_30mbps_mkv.json",
                "REMUX",
                "copy",
                "remux",
                "plex_compatible_h264_remux",
                {"SOURCE_CODEC_COMPATIBLE", "VIDEO_BITRATE_UNDER_DIRECT_COPY_CAP"},
            ),
            (
                "movie_h264_1080p_45mbps_mkv.json",
                "ENCODE",
                "encode",
                "encode",
                "bitrate_over_threshold",
                {"VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP"},
            ),
            (
                "movie_hevc_4k_hdr_high_bitrate_mkv.json",
                "ENCODE",
                "encode",
                "encode",
                "bitrate_over_threshold",
                {"VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP"},
            ),
            (
                "avi_mpeg2_480p.json",
                "ENCODE",
                "encode",
                "encode",
                "codec_not_remux_safe",
                {"SOURCE_CODEC_INCOMPATIBLE", "VIDEO_BITRATE_UNDER_DIRECT_COPY_CAP"},
            ),
        ]

        for fixture, summary, video_action, legacy_route, legacy_reason, expected_reasons in cases:
            with self.subTest(fixture=fixture):
                decision = build_processing_decision(load_source(fixture))

                self.assertEqual(decision.route_summary, summary)
                self.assertEqual(decision.stream_actions.video.action, video_action)
                self.assertEqual(decision.legacy_route, legacy_route)
                self.assertEqual(decision.legacy_reason_code, legacy_reason)
                self.assertTrue(expected_reasons.issubset(reason_codes(decision)))
                self.assertIn("CONTAINER_REMUX_ONLY", reason_codes(decision))
                self.assertEqual(decision.effective_settings.routing_profile, "plex_direct_stream")

    def test_size_threshold_advisory_remains_distinct_from_hard_route(self) -> None:
        decision = build_processing_decision(load_source("multi_audio_tracks.json"))

        self.assertEqual(decision.route_summary, "REMUX")
        self.assertEqual(decision.stream_actions.video.action, "copy")
        self.assertEqual(decision.legacy_reason_code, "plex_compatible_size_advisory")
        self.assertIn("SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT", {reason.code for reason in decision.soft_targets_exceeded})
        self.assertNotIn("SOURCE_SIZE_EXCEEDS_ROUTE_LIMIT", {reason.code for reason in decision.hard_rules_triggered})

    def test_output_size_check_warn_only_is_advisory_verification_requirement(self) -> None:
        decision = build_processing_decision(
            load_source("tv_h264_1080p_24mbps_mkv.json"),
            EffectiveDecisionPolicy(output_size_check_action="warn_only"),
        )
        requirements = {item.code: item for item in decision.verification_requirements}
        size_guard = next(guard for guard in decision.verification_guards if guard.code == "OUTPUT_SIZE_CHECK")

        self.assertEqual(decision.route_summary, "ENCODE")
        self.assertEqual(requirements["OUTPUT_SIZE_CHECK_WARN_ONLY"].enforcement, "advisory")
        self.assertEqual(size_guard.enforcement, "ADVISORY")
        self.assertEqual(size_guard.on_fail, "record_advisory_warning")
        self.assertEqual(decision.verification_result.output_size_check.action, "warn_only")
        self.assertEqual(decision.verification_result.output_size_check.status, "planned")
        self.assertEqual(decision.verification_result.advisory_warnings, [])
        self.assertEqual(decision.verification_result.failures, [])

    def test_output_size_check_block_publish_is_publish_requirement_not_failure(self) -> None:
        decision = build_processing_decision(
            load_source("tv_h264_1080p_24mbps_mkv.json"),
            EffectiveDecisionPolicy(output_size_check_action="block_publish"),
        )
        publish_codes = {item.code for item in decision.publish_requirements}
        size_guard = next(guard for guard in decision.verification_guards if guard.code == "OUTPUT_SIZE_CHECK")

        self.assertIn("OUTPUT_SIZE_BLOCK_USES_PENDING_PUBLISH", publish_codes)
        self.assertEqual(size_guard.enforcement, "HARD_BLOCK")
        self.assertEqual(size_guard.on_fail, "park_pending_publish")

    def test_output_size_check_fail_job_is_distinct_from_block_publish(self) -> None:
        decision = build_processing_decision(
            load_source("tv_h264_1080p_24mbps_mkv.json"),
            EffectiveDecisionPolicy(output_size_check_action="fail_job"),
        )
        publish_codes = {item.code for item in decision.publish_requirements}
        size_guard = next(guard for guard in decision.verification_guards if guard.code == "OUTPUT_SIZE_CHECK")

        self.assertIn("OUTPUT_SIZE_FAILS_JOB_BEFORE_PUBLISH", publish_codes)
        self.assertNotIn("OUTPUT_SIZE_BLOCK_USES_PENDING_PUBLISH", publish_codes)
        self.assertEqual(size_guard.on_fail, "fail_job")

    def test_unknown_media_type_uses_conservative_caps_and_preserves_missing_metadata(self) -> None:
        decision = build_processing_decision(load_source("unknown_bitrate_source.json"))

        self.assertEqual(decision.route_summary, "REMUX")
        self.assertEqual(decision.stream_actions.video.action, "copy")
        self.assertEqual(decision.source_facts_used["media_type"], "unknown")
        self.assertIn("MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP", {reason.code for reason in decision.advisory_warnings})
        self.assertIn("MISSING_BITRATE_METADATA", {reason.code for reason in decision.advisory_warnings})

    def test_h264_bitrate_cap_zero_is_uncapped_without_crashing(self) -> None:
        policy = EffectiveDecisionPolicy(
            movie_direct_copy_max_bitrate_mbps=0,
            tv_direct_copy_max_bitrate_mbps=0,
            h264_direct_copy_max_bitrate_mbps=0,
        )

        decision = build_processing_decision(load_source("tv_h264_1080p_12mbps_mkv.json"), policy)

        self.assertEqual(decision.route_summary, "REMUX")
        self.assertEqual(decision.stream_actions.video.action, "copy")
        self.assertEqual(decision.legacy_reason_code, "plex_compatible_h264_remux")
        self.assertEqual(decision.source_facts_used["estimated_video_bitrate_mbps"], 12.0)

    def test_h264_specific_bitrate_cap_applies_when_general_cap_is_disabled(self) -> None:
        policy = EffectiveDecisionPolicy(
            movie_direct_copy_max_bitrate_mbps=0,
            tv_direct_copy_max_bitrate_mbps=0,
            h264_direct_copy_max_bitrate_mbps=10,
        )

        decision = build_processing_decision(load_source("tv_h264_1080p_12mbps_mkv.json"), policy)

        self.assertEqual(decision.route_summary, "ENCODE")
        self.assertEqual(decision.stream_actions.video.action, "encode")
        self.assertEqual(decision.legacy_reason_code, "bitrate_over_threshold")
        self.assertIn("VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP", reason_codes(decision))

    def test_unprobeable_source_rejects_without_crashing(self) -> None:
        decision = build_processing_decision(SourceMediaInfo())

        self.assertEqual(decision.route_summary, "REJECT")
        self.assertEqual(decision.stream_actions.video.action, "reject")
        self.assertEqual(decision.legacy_route, "reject")
        self.assertIn("SOURCE_UNPROBEABLE_REJECT", reason_codes(decision))
        self.assertEqual(decision.publish_requirements[0].code, "NO_PUBLISH_FOR_REJECTED_SOURCE")

    def test_mp4_subtitle_cross_constraint_forces_video_encode_for_image_subtitles(self) -> None:
        decision = build_processing_decision(
            load_source("source_with_image_subtitles.json"),
            EffectiveDecisionPolicy(output_container="mp4"),
        )

        self.assertEqual(decision.route_summary, "ENCODE")
        self.assertEqual(decision.stream_actions.video.action, "encode")
        self.assertTrue(all(stream.action == "burn" for stream in decision.stream_actions.subtitles))
        self.assertIn("SUBTITLE_FORMAT_INCOMPATIBLE_WITH_CONTAINER", reason_codes(decision))
        self.assertIn("SUBTITLE_BURN_IN_REQUIRES_ENCODE", reason_codes(decision))

    def test_mp4_audio_cross_constraint_is_per_stream_without_forcing_video_encode(self) -> None:
        decision = build_processing_decision(
            load_source("multi_audio_tracks.json"),
            EffectiveDecisionPolicy(output_container="mp4"),
        )

        self.assertEqual(decision.route_summary, "REMUX")
        self.assertEqual(decision.stream_actions.video.action, "copy")
        self.assertEqual(decision.stream_actions.audio[0].action, "transcode")
        self.assertEqual(decision.stream_actions.audio[1].action, "copy")
        self.assertEqual(decision.stream_actions.audio[2].action, "copy")
        self.assertIn("AUDIO_CODEC_INCOMPATIBLE_WITH_CONTAINER", reason_codes(decision))
        self.assertIn("AUDIO_TRANSCODE_REQUIRED", reason_codes(decision))

    def test_video_filter_setting_forces_video_encode_with_planned_output(self) -> None:
        decision = build_processing_decision(
            load_source("tv_h264_1080p_12mbps_mkv.json"),
            EffectiveDecisionPolicy(video_filter_names=["deinterlace"], video_output_codec="hevc_nvenc"),
        )

        self.assertEqual(decision.route_summary, "ENCODE")
        self.assertEqual(decision.stream_actions.video.action, "encode")
        self.assertIn("FILTERS_ENABLED_ENCODE_REQUIRED", reason_codes(decision))
        self.assertTrue(decision.planned_encode_output.video.active)
        self.assertEqual(decision.planned_encode_output.video.filters, ["deinterlace"])
        self.assertEqual(decision.planned_encode_output.video.codec, "hevc_nvenc")

    def test_resolution_limit_downscale_forces_video_encode(self) -> None:
        decision = build_processing_decision(
            load_source("tv_h264_1080p_12mbps_mkv.json"),
            EffectiveDecisionPolicy(resolution_limit="720p"),
        )

        self.assertEqual(decision.route_summary, "ENCODE")
        self.assertEqual(decision.stream_actions.video.action, "encode")
        self.assertIn("RESOLUTION_EXCEEDS_LIMIT", reason_codes(decision))
        self.assertEqual(decision.planned_encode_output.video.output_height, 720)

    def test_subtitle_forced_burn_in_forces_video_encode(self) -> None:
        decision = build_processing_decision(
            load_source("source_with_image_subtitles.json"),
            EffectiveDecisionPolicy(subtitle_burn_in_forced=True),
        )

        self.assertEqual(decision.route_summary, "ENCODE")
        self.assertEqual(decision.stream_actions.video.action, "encode")
        self.assertEqual(decision.stream_actions.subtitles[0].action, "burn")
        self.assertEqual(decision.stream_actions.subtitles[1].action, "copy")
        self.assertIn("SUBTITLE_BURN_IN_REQUIRES_ENCODE", reason_codes(decision))
        self.assertEqual(decision.planned_encode_output.subtitles.burned_streams, [2])

    def test_audio_policy_transcode_does_not_force_video_encode(self) -> None:
        decision = build_processing_decision(
            load_source("multi_audio_tracks.json"),
            EffectiveDecisionPolicy(audio_max_channels=6),
        )

        self.assertEqual(decision.route_summary, "REMUX")
        self.assertEqual(decision.stream_actions.video.action, "copy")
        self.assertEqual(decision.stream_actions.audio[0].action, "transcode")
        self.assertEqual(decision.planned_encode_output.audio.transcode_streams, [1])
        self.assertFalse(decision.planned_encode_output.video.active)


if __name__ == "__main__":
    unittest.main()
