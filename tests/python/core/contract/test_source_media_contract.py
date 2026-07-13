from __future__ import annotations

import json
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

from pydantic import ValidationError

from mediapipeline.contracts.source_media import (
    SourceMediaInfo,
    source_media_from_ffprobe,
    source_media_from_probe_result,
)
from mediapipeline.contracts.stages import ProbeResult, StreamSummary


REPO_ROOT = find_repo_root(Path(__file__))
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "source_media"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class SourceMediaContractTests(unittest.TestCase):
    def test_p010_pixel_format_normalizes_as_ten_bit(self) -> None:
        p010 = source_media_from_ffprobe(
            {"streams": [{"index": 0, "codec_type": "video", "pix_fmt": "p010le"}], "format": {}}
        )
        explicit = source_media_from_ffprobe(
            {
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "video",
                        "pix_fmt": "p010le",
                        "bits_per_raw_sample": "12",
                    }
                ],
                "format": {},
            }
        )

        self.assertEqual(p010.video_streams[0].bit_depth, 10)
        self.assertEqual(explicit.video_streams[0].bit_depth, 12)

    def test_raw_ffprobe_fixture_normalizes_source_facts(self) -> None:
        source = source_media_from_ffprobe(load_fixture("tv_h264_1080p_12mbps_mkv.json"))

        self.assertEqual(source.schema_version, "source_media.v1")
        self.assertEqual(source.container.media_type, "tv")
        self.assertEqual(source.container.format_name, "matroska,webm")
        self.assertEqual(source.container.title, "Pilot")
        self.assertEqual(source.video_streams[0].codec, "h264")
        self.assertEqual(source.video_streams[0].codec_profile, "High")
        self.assertEqual(source.video_streams[0].width, 1920)
        self.assertEqual(source.video_streams[0].display_width, 1920)
        self.assertAlmostEqual(source.video_streams[0].frame_rate, 23.976, places=3)
        self.assertEqual(source.video_streams[0].scan_type, "progressive")
        self.assertEqual(source.video_streams[0].bit_depth, 8)
        self.assertEqual(source.audio_streams[0].codec, "ac3")
        self.assertTrue(source.audio_streams[0].default)
        self.assertEqual(source.subtitle_streams[0].subtitle_kind, "text")
        self.assertTrue(source.subtitle_streams[0].passthrough_candidate)
        self.assertFalse(source.subtitle_streams[0].drop_candidate)
        self.assertFalse(source.derived.unknown_metadata)

    def test_representative_fixtures_cover_dimensions_bitrate_hdr_audio_and_subtitles(self) -> None:
        expectations = {
            "tv_h264_1080p_12mbps_mkv.json": ("tv", "1080p", "medium", "h264", False, 1, 1),
            "tv_h264_1080p_24mbps_mkv.json": ("tv", "1080p", "high", "h264", False, 1, 0),
            "movie_h264_1080p_30mbps_mkv.json": ("movie", "1080p", "high", "h264", False, 1, 0),
            "movie_h264_1080p_45mbps_mkv.json": ("movie", "1080p", "very_high", "h264", False, 1, 0),
            "movie_hevc_4k_hdr_high_bitrate_mkv.json": ("movie", "4k", "very_high", "hevc", True, 1, 1),
            "avi_mpeg2_480p.json": ("movie", "480p", "low", "mpeg2video", False, 1, 0),
            "source_with_image_subtitles.json": ("movie", "1080p", "medium", "hevc", False, 1, 2),
            "interlaced_source.json": ("tv", "1080p", "medium", "h264", False, 1, 0),
            "multi_audio_tracks.json": ("movie", "1080p", "medium", "hevc", False, 3, 0),
            "unknown_bitrate_source.json": ("unknown", "720p", "unknown", "h264", False, 1, 0),
        }

        for fixture, expected in expectations.items():
            with self.subTest(fixture=fixture):
                media_type, dimension, bitrate, codec, hdr, audio_count, subtitle_count = expected
                source = source_media_from_ffprobe(load_fixture(fixture))

                self.assertEqual(source.container.media_type, media_type)
                self.assertEqual(source.derived.dimensions_bucket, dimension)
                self.assertEqual(source.derived.bitrate_bucket, bitrate)
                self.assertEqual(source.video_streams[0].codec, codec)
                self.assertEqual(source.video_streams[0].is_hdr, hdr)
                self.assertEqual(len(source.audio_streams), audio_count)
                self.assertEqual(len(source.subtitle_streams), subtitle_count)

    def test_image_subtitles_and_interlaced_video_are_visible_as_source_facts(self) -> None:
        image_subs = source_media_from_ffprobe(load_fixture("source_with_image_subtitles.json"))
        self.assertEqual(image_subs.derived.subtitle_burn_candidates, [2, 3])
        self.assertEqual(image_subs.derived.subtitle_convert_candidates, [2, 3])
        self.assertTrue(all(stream.image_based for stream in image_subs.subtitle_streams))
        self.assertTrue(all(not stream.drop_candidate for stream in image_subs.subtitle_streams))

        interlaced = source_media_from_ffprobe(load_fixture("interlaced_source.json"))
        self.assertEqual(interlaced.video_streams[0].scan_type, "interlaced")

    def test_policy_facts_are_annotations_not_routes(self) -> None:
        high_bitrate_movie = source_media_from_ffprobe(load_fixture("movie_h264_1080p_45mbps_mkv.json"))
        dts_audio = high_bitrate_movie.audio_streams[0]

        self.assertTrue(high_bitrate_movie.derived.primary_video_codec_allowed)
        self.assertFalse(high_bitrate_movie.derived.already_remux_compatible)
        self.assertFalse(high_bitrate_movie.derived.audio_passthrough_safe)
        self.assertFalse(dts_audio.passthrough_safe)

    def test_unknown_metadata_stays_visible_and_conservative(self) -> None:
        source = source_media_from_ffprobe(load_fixture("unknown_bitrate_source.json"))

        self.assertEqual(source.derived.bitrate_bucket, "unknown")
        self.assertIn("container.file_size_bytes", source.derived.unknown_metadata)
        self.assertIn("container.overall_bitrate_bps", source.derived.unknown_metadata)
        self.assertEqual(source.derived.already_remux_compatible, False)

    def test_derived_bitrate_prefers_file_size_duration_over_stream_hint(self) -> None:
        source = source_media_from_ffprobe(
            {
                "source": {
                    "path": "fixtures/conflicting-bitrate.mkv",
                    "file_size_bytes": 18_000_000_000,
                    "media_type": "movie",
                },
                "format": {
                    "format_name": "matroska,webm",
                    "duration": "3600.0",
                    "bit_rate": "40000000",
                },
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "bit_rate": "5000000",
                    }
                ],
            }
        )

        self.assertEqual(source.derived.bitrate_bucket, "very_high")
        self.assertFalse(source.derived.already_remux_compatible)

    def test_existing_probe_result_shape_adapts_to_source_media_info(self) -> None:
        probe = ProbeResult(
            probe_ok=True,
            container="matroska,webm",
            duration_seconds=300.0,
            bitrate_bps=8000000,
            video_codec="hevc",
            width=1920,
            height=1080,
            is_hdr=True,
            color_transfer="smpte2084",
            estimated_bitrate_mbps=8.0,
            size_bytes=300000000,
            streams=[
                StreamSummary(index=0, kind="video", codec="hevc", width=1920, height=1080),
                StreamSummary(index=1, kind="audio", codec="eac3", channels=6, language="eng", default=True),
                StreamSummary(index=2, kind="subtitle", codec="ass", language="eng"),
            ],
        )

        source = source_media_from_probe_result(probe, source_path=r"D:\scratch\episode.mkv", media_type="tv")

        self.assertEqual(source.container.path, r"D:\scratch\episode.mkv")
        self.assertEqual(source.container.media_type, "tv")
        self.assertEqual(source.video_streams[0].codec, "hevc")
        self.assertTrue(source.video_streams[0].is_hdr)
        self.assertEqual(source.video_streams[0].hdr_format, "smpte2084")
        self.assertEqual(source.audio_streams[0].codec, "eac3")
        self.assertEqual(source.subtitle_streams[0].codec, "ass")
        self.assertEqual(source.subtitle_streams[0].subtitle_kind, "text")
        self.assertTrue(source.subtitle_streams[0].convert_candidate)
        self.assertFalse(source.subtitle_streams[0].drop_candidate)
        self.assertEqual(source.derived.dimensions_bucket, "1080p")

    def test_unknown_subtitle_codecs_remain_drop_candidates(self) -> None:
        probe = ProbeResult(
            probe_ok=True,
            container="matroska,webm",
            duration_seconds=300.0,
            bitrate_bps=8000000,
            video_codec="hevc",
            width=1920,
            height=1080,
            estimated_bitrate_mbps=8.0,
            size_bytes=300000000,
            streams=[
                StreamSummary(index=0, kind="video", codec="hevc", width=1920, height=1080),
                StreamSummary(index=2, kind="subtitle", codec="unknown_binary_subtitle", language="eng"),
            ],
        )

        source = source_media_from_probe_result(probe, source_path=r"D:\scratch\episode.mkv", media_type="tv")

        self.assertEqual(source.subtitle_streams[0].subtitle_kind, "unknown")
        self.assertFalse(source.subtitle_streams[0].passthrough_candidate)
        self.assertFalse(source.subtitle_streams[0].convert_candidate)
        self.assertFalse(source.subtitle_streams[0].burn_candidate)
        self.assertTrue(source.subtitle_streams[0].drop_candidate)

    def test_source_media_model_rejects_unexpected_fields(self) -> None:
        with self.assertRaises(ValidationError):
            SourceMediaInfo.model_validate({"schema_version": "source_media.v1", "unexpected": True})


if __name__ == "__main__":
    unittest.main()
