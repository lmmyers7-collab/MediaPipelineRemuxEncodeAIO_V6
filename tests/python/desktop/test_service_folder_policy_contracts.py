from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.folder_policy.constants import FOLDER_POLICY_SCHEMA_VERSION, FOLDER_POLICY_SIDECAR_NAME
from mediapipeline.core.folder_policy.service import FolderPolicyServiceMixin
from mediapipeline.core.folder_policy.contracts import (
    default_folder_policy,
    stream_signature,
    stream_topology,
)


class DummyFolderPolicyService(FolderPolicyServiceMixin):
    def __init__(self) -> None:
        self.probed_paths: list[Path] = []

    def probe_media_stream_signature(self, media_path: Path, *, timeout: int = 30) -> dict[str, object]:
        self.probed_paths.append(media_path)
        return {
            "path": str(media_path),
            "audio": [{"codec": "eac3", "language": "eng", "channels": 6}],
            "subtitles": [],
        }


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

    def test_validate_folder_policy_rejects_sample_outside_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            folder = root / "Season 01"
            folder.mkdir()
            (folder / "Episode 01.mkv").write_bytes(b"placeholder")
            outside_sample = root / "Outside Sample.mkv"
            outside_sample.write_bytes(b"placeholder")
            (folder / FOLDER_POLICY_SIDECAR_NAME).write_text(
                json.dumps(
                    {
                        "schema_version": FOLDER_POLICY_SCHEMA_VERSION,
                        "folder": str(folder),
                        "audio": {},
                        "subtitles": {},
                        "validation": {
                            "sample_file": "..\\Outside Sample.mkv",
                            "require_uniform_stream_topology": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            service = DummyFolderPolicyService()
            result = service.validate_folder_policy(folder)

        self.assertFalse(result["ok"])
        self.assertIn("Sample file must be inside folder", result["errors"][0])
        self.assertEqual(result["files"], [])
        self.assertEqual(service.probed_paths, [])

    def test_validate_folder_policy_dry_run_leaves_sidecar_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            folder = root / "Season 01"
            folder.mkdir()
            (folder / "Episode 01.mkv").write_bytes(b"placeholder")
            (folder / "Episode 02.mkv").write_bytes(b"placeholder")
            sidecar = folder / FOLDER_POLICY_SIDECAR_NAME
            original_payload = {
                "schema_version": FOLDER_POLICY_SCHEMA_VERSION,
                "folder": str(folder),
                "audio": {},
                "subtitles": {},
                "validation": {
                    "sample_file": "Episode 01.mkv",
                    "require_uniform_stream_topology": True,
                },
            }
            original_text = json.dumps(original_payload)
            sidecar.write_text(original_text, encoding="utf-8")

            service = DummyFolderPolicyService()
            result = service.validate_folder_policy(folder)
            saved_payload = json.loads(sidecar.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["saved_policy_path"], "")
        self.assertEqual(saved_payload, original_payload)
        self.assertEqual([path.name for path in service.probed_paths], ["Episode 01.mkv", "Episode 02.mkv"])

    def test_validate_folder_policy_explicit_save_persists_folder_relative_sample(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            folder = root / "Season 01"
            folder.mkdir()
            (folder / "Episode 01.mkv").write_bytes(b"placeholder")
            (folder / "Episode 02.mkv").write_bytes(b"placeholder")
            sidecar = folder / FOLDER_POLICY_SIDECAR_NAME
            sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": FOLDER_POLICY_SCHEMA_VERSION,
                        "folder": str(folder),
                        "audio": {},
                        "subtitles": {},
                        "validation": {
                            "sample_file": "Episode 01.mkv",
                            "require_uniform_stream_topology": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            service = DummyFolderPolicyService()
            result = service.validate_folder_policy(folder, save=True)
            saved_payload = json.loads(sidecar.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["saved_policy_path"], str(sidecar))
        self.assertEqual(saved_payload["validation"]["sample_file"], "Episode 01.mkv")
        self.assertEqual(saved_payload["validation"]["checked_count"], 2)
        self.assertEqual([path.name for path in service.probed_paths], ["Episode 01.mkv", "Episode 02.mkv"])


if __name__ == "__main__":
    unittest.main()
