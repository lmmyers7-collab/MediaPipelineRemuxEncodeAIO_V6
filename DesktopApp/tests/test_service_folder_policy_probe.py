from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.folder_policy.probe import parse_ffprobe_stream_signature


class FolderPolicyProbeParserTests(unittest.TestCase):
    def test_parse_ffprobe_stream_signature_groups_audio_and_subtitles(self) -> None:
        media = Path(r"C:\Media\Show\E01.mkv")
        parsed = parse_ffprobe_stream_signature(
            media,
            """
            {
              "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "hevc"},
                {"index": 1, "codec_type": "audio", "codec_name": "EAC3", "channels": 6, "tags": {"language": "ENG"}},
                {"index": 2, "codec_type": "subtitle", "codec_name": "ASS", "tags": {"language": "jpn"}, "disposition": {"forced": 1}}
              ]
            }
            """,
        )

        self.assertEqual(parsed["path"], str(media))
        self.assertEqual(len(parsed["audio"]), 1)
        self.assertEqual(parsed["audio"][0]["codec"], "eac3")
        self.assertEqual(parsed["audio"][0]["language"], "eng")
        self.assertEqual(parsed["audio"][0]["channels"], 6)
        self.assertEqual(len(parsed["subtitles"]), 1)
        self.assertEqual(parsed["subtitles"][0]["codec"], "ass")
        self.assertTrue(parsed["subtitles"][0]["forced"])

    def test_parse_ffprobe_stream_signature_treats_non_list_streams_as_empty(self) -> None:
        parsed = parse_ffprobe_stream_signature(Path("Movie.mkv"), '{"streams": {"bad": true}}')

        self.assertEqual(parsed["audio"], [])
        self.assertEqual(parsed["subtitles"], [])

    def test_parse_ffprobe_stream_signature_normalizes_invalid_audio_channels(self) -> None:
        parsed = parse_ffprobe_stream_signature(
            Path("Movie.mkv"),
            '{"streams": [{"codec_type": "audio", "codec_name": "aac", "channels": "N/A"}]}',
        )

        self.assertEqual(parsed["audio"][0]["channels"], 0)

    def test_parse_ffprobe_stream_signature_preserves_json_decode_errors(self) -> None:
        with self.assertRaises(ValueError):
            parse_ffprobe_stream_signature(Path("Movie.mkv"), "{not-json")


if __name__ == "__main__":
    unittest.main()
