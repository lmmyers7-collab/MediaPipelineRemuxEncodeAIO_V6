from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.folder_policy.constants import FOLDER_POLICY_SCHEMA_VERSION
from app.folder_policy.service import FolderPolicyServiceMixin
from app.folder_policy.contracts import (
    default_folder_policy,
    stream_signature,
    stream_topology,
)


class DummyFolderPolicyService(FolderPolicyServiceMixin):
    pass


class FolderPolicyContractTests(unittest.TestCase):
    def test_default_policy_preserves_audio_subtitle_routing_shape(self) -> None:
        folder = Path(r"C:\Media\Show")
        policy = default_folder_policy(folder)

        self.assertEqual(policy["schema_version"], FOLDER_POLICY_SCHEMA_VERSION)
        self.assertEqual(policy["folder"], str(folder))
        self.assertEqual(policy["audio"]["passthrough_codecs"], [])
        self.assertTrue(policy["subtitles"]["ass"]["enabled"])
        self.assertTrue(policy["subtitles"]["tx3g"]["enabled"])
        self.assertFalse(policy["subtitles"]["bdpgs"]["enabled"])
        self.assertEqual(policy["routing"]["force_route"], "auto")
        self.assertTrue(policy["validation"]["require_uniform_stream_topology"])

    def test_stream_signature_normalizes_missing_tags_and_disposition(self) -> None:
        signature = stream_signature({"index": 4, "codec_type": "audio", "codec_name": "EAC3", "channels": "6"})

        self.assertEqual(
            signature,
            {
                "index": 4,
                "type": "audio",
                "codec": "eac3",
                "channels": 6,
                "language": "und",
                "title": "",
                "default": False,
                "forced": False,
            },
        )

    def test_stream_topology_uses_audio_codec_language_channels_and_subtitle_language(self) -> None:
        topology = stream_topology(
            {
                "audio": [
                    {"codec": "eac3", "language": "eng", "channels": 6},
                    {"codec": "aac", "language": "jpn", "channels": 2},
                ],
                "subtitles": [
                    {"codec": "ass", "language": "eng"},
                    {"codec": "subrip", "language": "und"},
                ],
            }
        )

        self.assertEqual(topology["audio"], [("eac3", "eng", 6), ("aac", "jpn", 2)])
        self.assertEqual(topology["subtitles"], [("ass", "eng"), ("subrip", "und")])

    def test_service_wrappers_match_extracted_contract_helpers(self) -> None:
        service = DummyFolderPolicyService()
        folder = Path(r"C:\Media\Show")
        stream = {
            "index": 1,
            "codec_type": "subtitle",
            "codec_name": "ASS",
            "tags": {"language": "ENG", "title": "Signs"},
            "disposition": {"default": 1, "forced": 0},
        }

        self.assertEqual(service.default_folder_policy(folder), default_folder_policy(folder))
        self.assertEqual(service._stream_signature(stream), stream_signature(stream))


if __name__ == "__main__":
    unittest.main()
