from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.queue.policy import (
    EMPTY_QUEUE_SNAPSHOT_WARNING,
    INVALID_QUEUE_SNAPSHOT_WARNING,
    NO_QUEUE_SNAPSHOT_WARNING,
    QUEUE_PREVIEW_SERVICE_WARNING,
    queue_preview_metadata,
    queue_preview_rows,
    queue_preview_track_metadata_summary,
    queue_preview_warnings,
    queue_record_to_row,
    queue_source_scan_progress_payload,
)
from mediapipeline.core.queue.file_overrides import (
    clear_file_override_fields,
    get_file_override_entry,
    normalize_file_override_path,
    resolve_file_override_match,
    set_file_override_entry,
    validate_file_override_payload,
)
from mediapipeline.desktop.models import QueueRecord


def _record() -> QueueRecord:
    return QueueRecord(
        source_path=Path("C:/Source/TV/Show/Season 01/Show - S01E01.mkv"),
        source_root=Path("C:/Source/TV"),
        media_type="TV",
        is_priority=True,
        priority_reasons=["manual marker"],
        priority_rank=1.5,
        sort_name="show",
        display_name="Show - S01E01.mkv",
        relative_path="Show\\Season 01\\Show - S01E01.mkv",
        show_folder="Show",
        season_folder="Season 01",
        season_number=1,
        episode_number=1,
        source_mtime=1778173200.0,
        size_gb=1.25,
        route_name="remux",
        route_reason="already compatible",
        matched_show_override="",
        queue_index=1,
        queue_total=12,
        phase="tv",
        global_order=7,
        manifest_priority_level="high",
    )


class QueueFacadePolicyTests(unittest.TestCase):
    def test_queue_record_to_row_preserves_operator_fields(self) -> None:
        row = queue_record_to_row(_record())

        self.assertEqual(row["source_path"], str(Path("C:/Source/TV/Show/Season 01/Show - S01E01.mkv")))
        self.assertEqual(row["source_root"], str(Path("C:/Source/TV")))
        self.assertEqual(row["media_type"], "TV")
        self.assertTrue(row["is_priority"])
        self.assertEqual(row["priority_reasons"], ["manual marker"])
        self.assertEqual(row["priority_rank"], 1.5)
        self.assertEqual(row["display_name"], "Show - S01E01.mkv")
        self.assertEqual(row["relative_path"], "Show\\Season 01\\Show - S01E01.mkv")
        self.assertEqual(row["show_folder"], "Show")
        self.assertEqual(row["season_folder"], "Season 01")
        self.assertEqual(row["season_number"], 1)
        self.assertEqual(row["episode_number"], 1)
        self.assertEqual(row["size_gb"], 1.25)
        self.assertEqual(row["route_name"], "remux")
        self.assertEqual(row["route_reason"], "already compatible")
        self.assertEqual(row["queue_index"], 1)
        self.assertEqual(row["queue_total"], 12)
        self.assertEqual(row["phase"], "tv")
        self.assertEqual(row["global_order"], 7)
        self.assertEqual(row["manifest_priority_level"], "high")
        self.assertEqual(row["available_open_targets"], ["source_file", "source_folder", "source_root"])
        self.assertFalse(row["track_metadata_available"])

    def test_queue_preview_rows_filter_non_dicts_and_keep_invalid_rows(self) -> None:
        def factory(raw: dict[str, object]) -> object:
            if raw.get("source_path") == "bad":
                raise ValueError("bad source")
            if raw.get("source_path") == "not-record":
                return {"ignored": True}
            return _record()

        rows = queue_preview_rows(
            [
                {"source_path": "ok"},
                "not-a-row",
                {"source_path": "bad", "raw_value": 5},
                {"source_path": "not-record"},
            ],
            factory,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["route_name"], "remux")
        self.assertEqual(rows[1]["status"], "invalid")
        self.assertEqual(rows[1]["error"], "bad source")
        self.assertEqual(rows[1]["raw"], {"source_path": "bad", "raw_value": 5})
        self.assertEqual(rows[1]["available_open_targets"], [])
        self.assertFalse(rows[1]["track_metadata_available"])

    def test_queue_preview_rows_add_track_summary_from_cached_streams(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Source/TV/Show/Season 01/Show - S01E01.mkv",
                    "streams": [
                        {"index": 0, "kind": "video", "codec": "h264"},
                        {"index": 1, "kind": "audio", "language": "eng", "channels": 6, "default": True},
                        {"index": 2, "kind": "audio", "language": "jpn", "channels": 2},
                        {"index": 3, "kind": "subtitle", "language": "eng", "forced": True},
                        {
                            "index": 4,
                            "kind": "subtitle",
                            "tags": {"language": "spa"},
                            "disposition": {"forced": 0},
                        },
                    ],
                }
            ],
            factory,
        )

        row = rows[0]
        self.assertTrue(row["track_metadata_available"])
        self.assertEqual(row["audio_track_count"], 2)
        self.assertEqual(row["subtitle_track_count"], 2)
        self.assertEqual(row["audio_languages"], ["eng", "jpn"])
        self.assertEqual(row["subtitle_languages"], ["eng", "spa"])
        self.assertTrue(row["has_forced_subtitles"])
        self.assertNotIn("streams", row)

    def test_queue_preview_rows_without_track_cache_does_not_probe(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        with patch("mediapipeline.core.orchestration.runner.run_probe_stage") as probe_stage:
            rows = queue_preview_rows(
                [{"source_path": "C:/Source/TV/Show/Season 01/Show - S01E01.mkv"}],
                factory,
            )

        probe_stage.assert_not_called()
        self.assertFalse(rows[0]["track_metadata_available"])
        self.assertNotIn("audio_track_count", rows[0])
        self.assertNotIn("subtitle_track_count", rows[0])

    def test_queue_preview_track_summary_accepts_existing_summary_fields(self) -> None:
        summary = queue_preview_track_metadata_summary(
            {
                "track_metadata_available": True,
                "audio_track_count": "3",
                "subtitle_track_count": 5,
                "audio_languages": ["eng", "ENG", "jpn", ""],
                "subtitle_languages": ["spa", "eng"],
                "has_forced_subtitles": "yes",
            }
        )

        self.assertEqual(
            summary,
            {
                "track_metadata_available": True,
                "audio_track_count": 3,
                "subtitle_track_count": 5,
                "audio_languages": ["eng", "jpn"],
                "subtitle_languages": ["spa", "eng"],
                "has_forced_subtitles": True,
            },
        )

    def test_file_override_resolver_reports_exact_folder_and_deepest_match_metadata(self) -> None:
        source = "C:/Source/TV/Show/Season 01/Show - S01E01.mkv"
        manifest = {
            "version": 1,
            "entries": {
                "c:/source/tv": {"audio": {"maxChannels": 2}, "set_at": "old"},
                "c:/source/tv/show": {"audio": {"maxChannels": 6}},
                "c:/source/tv/show/season 01/show - s01e01.mkv": {"subtitles": {"stripAll": False}},
            },
        }

        exact = resolve_file_override_match(manifest, source)
        self.assertEqual(exact["scope"], "file")
        self.assertTrue(exact["is_exact"])
        self.assertEqual(exact["matched_path"], "c:/source/tv/show/season 01/show - s01e01.mkv")
        self.assertEqual(exact["entry"], {"subtitles": {"stripAll": False}})
        self.assertEqual(get_file_override_entry(manifest, source), {"subtitles": {"stripAll": False}})

        folder_only = {"version": 1, "entries": {k: v for k, v in manifest["entries"].items() if not k.endswith(".mkv")}}
        folder = resolve_file_override_match(folder_only, source)
        self.assertEqual(folder["scope"], "folder")
        self.assertFalse(folder["is_exact"])
        self.assertEqual(folder["matched_path"], "c:/source/tv/show")
        self.assertEqual(folder["entry"], {"audio": {"maxChannels": 6}})

        missing = resolve_file_override_match(folder_only, "C:/Other/Movie.mkv")
        self.assertIsNone(missing["entry"])
        self.assertIsNone(missing["matched_path"])
        self.assertIsNone(missing["scope"])

    def test_clear_file_override_fields_removes_only_requested_nested_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest_path = root / "State" / "file_overrides.json"
            source = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")

            set_file_override_entry(
                manifest_path,
                source,
                {
                    "audio": {
                        "keepTracks": [{"language": "eng"}],
                        "maxChannels": 6,
                    },
                    "subtitles": {
                        "keepTracks": [{"language": "eng"}],
                        "stripAll": True,
                    },
                },
            )

            manifest = clear_file_override_fields(manifest_path, source, ["audio.maxChannels"])
            entry = manifest["entries"][normalize_file_override_path(source)]
            self.assertNotIn("maxChannels", entry["audio"])
            self.assertEqual(entry["audio"]["keepTracks"], [{"language": "eng"}])

            manifest = clear_file_override_fields(manifest_path, source, ["subtitles.stripAll"])
            entry = manifest["entries"][normalize_file_override_path(source)]
            self.assertNotIn("stripAll", entry["subtitles"])
            self.assertEqual(entry["subtitles"]["keepTracks"], [{"language": "eng"}])

            manifest = clear_file_override_fields(manifest_path, source, ["audio.keepTracks"])
            entry = manifest["entries"][normalize_file_override_path(source)]
            self.assertNotIn("audio", entry)
            self.assertIn("subtitles", entry)

            manifest = clear_file_override_fields(manifest_path, source, ["subtitles.keepTracks"])
            self.assertNotIn(normalize_file_override_path(source), manifest["entries"])

    def test_clear_file_override_fields_leaves_folder_entries_and_missing_manifest_safe(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest_path = root / "State" / "file_overrides.json"
            folder = root / "TV" / "Show"
            source = folder / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")

            set_file_override_entry(manifest_path, folder, {"audio": {"maxChannels": 6}})
            set_file_override_entry(manifest_path, source, {"audio": {"maxChannels": 2}})

            manifest = clear_file_override_fields(manifest_path, folder, ["audio.maxChannels"])
            folder_key = normalize_file_override_path(folder)
            self.assertEqual(manifest["entries"][folder_key]["audio"]["maxChannels"], 6)

            manifest = clear_file_override_fields(manifest_path, source, ["audio.maxChannels"])
            self.assertIn(folder_key, manifest["entries"])
            self.assertNotIn(normalize_file_override_path(source), manifest["entries"])

            missing_manifest = clear_file_override_fields(
                root / "State" / "missing_file_overrides.json",
                source,
                ["audio.maxChannels"],
            )
            self.assertEqual(missing_manifest["entries"], {})

    def test_clear_file_override_fields_rejects_unknown_field_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")

            with self.assertRaises(ValueError):
                clear_file_override_fields(root / "State" / "file_overrides.json", source, ["audio.renameTracks"])

    def test_validate_file_override_payload_enforces_current_drawer_fields(self) -> None:
        valid = {
            "audio": {
                "keepTracks": [{"language": "eng"}],
                "dropTracks": [{"language": "jpn"}],
                "maxChannels": 6,
                "preferDefaultLanguage": "eng",
            },
            "subtitles": {
                "keepTracks": [{"language": "eng"}],
                "dropTracks": [{"language": "und"}],
                "burnTrack": {"streamIndex": 3, "language": "eng", "codec": "subrip", "forced": True},
                "stripAll": False,
            },
        }
        self.assertEqual(validate_file_override_payload(valid), [])
        self.assertEqual(
            validate_file_override_payload(
                {
                    "audio": {
                        "keepTracks": [
                            {"streamIndex": 1, "language": "eng", "codec": "ac3", "channels": 6}
                        ]
                    },
                    "subtitles": {
                        "keepTracks": [
                            {"streamIndex": 3, "language": "eng", "codec": "subrip", "forced": True}
                        ]
                    },
                }
            ),
            [],
        )

        invalid_cases = [
            ({"route": "encode"}, "Unsupported override field(s): route"),
            ({"audio": {"renameTracks": []}}, "Unsupported audio field(s): renameTracks"),
            ({"subtitles": {"correctLanguageTags": {"und": "eng"}}}, "Unsupported subtitles field(s): correctLanguageTags"),
            ({"audio": {"keepTracks": ["eng"]}}, "'audio.keepTracks[0]' must be an object"),
            ({"audio": {"dropTracks": [{"language": 5}]}}, "'audio.dropTracks[0].language' must be a string"),
            ({"subtitles": {"keepTracks": [{"language": ""}]}}, "'subtitles.keepTracks[0].language' must not be empty"),
            ({"audio": {"keepTracks": [{"streamIndex": "1"}]}}, "'audio.keepTracks[0].streamIndex' must be an integer"),
            ({"audio": {"keepTracks": [{"streamIndex": -1}]}}, "'audio.keepTracks[0].streamIndex' must be zero or greater"),
            ({"audio": {"keepTracks": [{"streamIndex": 1, "map": "0:a:0"}]}}, "Unsupported audio.keepTracks[0] field(s): map"),
            ({"audio": {"keepTracks": [{"streamIndex": 1, "channels": 0}]}}, "'audio.keepTracks[0].channels' must be greater than zero"),
            ({"subtitles": {"keepTracks": [{"streamIndex": 3, "forced": "true"}]}}, "'subtitles.keepTracks[0].forced' must be a boolean"),
            ({"subtitles": {"burnTrack": [{"streamIndex": 3}]}}, "'subtitles.burnTrack' must be an object"),
            ({"subtitles": {"burnTrack": {"language": "eng"}}}, "'subtitles.burnTrack.streamIndex' is required"),
            ({"subtitles": {"burnTrack": {"streamIndex": "3"}}}, "'subtitles.burnTrack.streamIndex' must be an integer"),
            (
                {"routing": {"profile": "remux"}, "subtitles": {"burnTrack": {"streamIndex": 3}}},
                "'routing.profile' remux cannot be combined with subtitles.burnTrack",
            ),
            ({"audio": {"maxChannels": "6"}}, "'audio.maxChannels' must be an integer"),
            ({"audio": {"maxChannels": 0}}, "'audio.maxChannels' must be one of: 2, 6, 8"),
            ({"audio": {"preferDefaultLanguage": 5}}, "'audio.preferDefaultLanguage' must be a string"),
            ({"audio": {"preferDefaultLanguage": ""}}, "'audio.preferDefaultLanguage' must not be empty"),
            ({"audio": {"downmixMode": "invalid"}}, "Unsupported audio field(s): downmixMode"),
            ({"audio": {"transcodeBitrate": "not-a-bitrate"}}, "Unsupported audio field(s): transcodeBitrate"),
            ({"subtitles": {"stripAll": "true"}}, "'subtitles.stripAll' must be a boolean"),
        ]
        for payload, expected in invalid_cases:
            with self.subTest(payload=payload):
                self.assertIn(expected, "\n".join(validate_file_override_payload(payload)))

    def test_subtitle_burn_save_clears_conflicting_subtitle_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest_path = root / "State" / "file_overrides.json"
            source = root / "Movie.mkv"
            source.write_bytes(b"media")

            manifest = set_file_override_entry(
                manifest_path,
                source,
                {
                    "subtitles": {
                        "keepTracks": [{"language": "eng"}],
                        "dropTracks": [{"language": "spa"}],
                        "stripAll": True,
                        "burnTrack": {"streamIndex": 3, "language": "eng", "codec": "subrip", "forced": False},
                    }
                },
            )

            entry = manifest["entries"][normalize_file_override_path(source)]
            self.assertEqual(
                entry["subtitles"],
                {"burnTrack": {"streamIndex": 3, "language": "eng", "codec": "subrip", "forced": False}},
            )

    def test_queue_preview_rows_surface_library_profile_evidence(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Anime/Show/Season 01/Show - S01E01.mkv",
                    "root_path": "C:/Anime",
                    "library_id": "anime",
                    "library_name": "Anime",
                    "library_designation": "tv",
                    "library_output_root": "D:/AnimeProcessed",
                    "library_promotion_enabled": True,
                    "library_promotion_destination": "H:/FinalAnime",
                    "library_promotion_rule_id": "library-profile-anime",
                    "library_promotion_rule_label": "Anime promotion",
                    "library_settings_override_keys": ["AudioMaxChannels", "SubKeepLanguages"],
                    "library_settings_overrides": {"AudioMaxChannels": 6},
                    "library_effective_settings": {"AudioMaxChannels": 6, "VideoQuality": 22},
                    "route_decision_trace": [{"code": "routing_profile_selected"}, {"code": "size_evaluated"}],
                    "estimated_bitrate_mbps": 12.5,
                    "route_size_threshold_gb": 3,
                    "route_bitrate_threshold_mbps": 18,
                    "route_threshold_mode": "bitrate",
                    "size_over_threshold": False,
                    "bitrate_over_threshold": False,
                }
            ],
            factory,
        )

        self.assertEqual(rows[0]["library_id"], "anime")
        self.assertEqual(rows[0]["library_designation"], "tv")
        self.assertEqual(rows[0]["library_source_root"], "C:/Anime")
        self.assertEqual(rows[0]["library_output_root"], "D:/AnimeProcessed")
        self.assertTrue(rows[0]["library_promotion_enabled"])
        self.assertEqual(rows[0]["library_promotion_destination"], "H:/FinalAnime")
        self.assertEqual(rows[0]["library_promotion_rule_id"], "library-profile-anime")
        self.assertEqual(rows[0]["library_promotion_rule_label"], "Anime promotion")
        self.assertEqual(rows[0]["library_settings_overrides"], {"AudioMaxChannels": 6})
        self.assertEqual(rows[0]["library_effective_settings"]["VideoQuality"], 22)
        self.assertEqual(rows[0]["library_effective_settings_scope"], "library_only")
        self.assertFalse(rows[0]["runtime_effective_settings_available"])
        self.assertEqual(rows[0]["runtime_evidence_note"], "resolved during job processing")
        self.assertEqual(rows[0]["override_layers_pending"], ["show", "folder", "file"])
        self.assertEqual(rows[0]["estimated_bitrate_mbps"], 12.5)
        self.assertEqual(rows[0]["route_size_threshold_gb"], 3.0)
        self.assertEqual(rows[0]["route_bitrate_threshold_mbps"], 18.0)
        self.assertEqual(rows[0]["route_threshold_mode"], "bitrate")
        self.assertIn("Library profile: Anime (anime)", rows[0]["route_evidence_lines"])
        self.assertIn("Library designation: tv", rows[0]["route_evidence_lines"])
        self.assertIn("Library source root: C:/Anime", rows[0]["route_evidence_lines"])
        self.assertIn("Library output root: D:/AnimeProcessed", rows[0]["route_evidence_lines"])
        self.assertIn("Library override keys: AudioMaxChannels, SubKeepLanguages", rows[0]["route_evidence_lines"])
        self.assertIn(
            "Library effective settings: library-only (global settings plus library overrides)",
            rows[0]["route_evidence_lines"],
        )
        self.assertIn("Library promotion: enabled", rows[0]["route_evidence_lines"])
        self.assertIn("Library promotion destination: H:/FinalAnime", rows[0]["route_evidence_lines"])
        self.assertIn("Library promotion rule: Anime promotion (library-profile-anime)", rows[0]["route_evidence_lines"])
        self.assertIn(
            "Runtime effective settings: resolved during job processing; pending layers: show, folder, file",
            rows[0]["route_evidence_lines"],
        )
        self.assertIn("Route threshold mode: bitrate", rows[0]["route_evidence_lines"])
        self.assertIn("Size threshold: 3 GB; over threshold: no", rows[0]["route_evidence_lines"])
        self.assertIn("Bitrate estimate: 12.5 Mbps; threshold: 18 Mbps; over threshold: no", rows[0]["route_evidence_lines"])
        self.assertIn("Route trace: routing_profile_selected, size_evaluated", rows[0]["route_evidence_lines"])

    def test_queue_preview_rows_annotate_file_override_matches_without_runtime_effective_claim(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        exact_source = str(Path("C:/Source/TV/Show/Season 01/Show - S01E01.mkv"))
        manifest = {
            "version": 1,
            "entries": {
                exact_source.replace("\\", "/").lower(): {"audio": {"maxChannels": 6}},
            },
        }

        rows = queue_preview_rows(
            [
                {
                    "source_path": exact_source,
                    "root_path": "C:/Source/TV",
                    "audio_tracks": [
                        {"stream_index": 1, "language": "eng"},
                    ],
                    "subtitle_tracks": [
                        {"stream_index": 3, "language": "eng", "forced": False},
                    ],
                }
            ],
            factory,
            file_override_manifest=manifest,
        )

        self.assertTrue(rows[0]["has_file_override"])
        self.assertEqual(rows[0]["file_override_scope"], "file")
        self.assertEqual(rows[0]["file_override_path"], exact_source.replace("\\", "/").lower())
        self.assertTrue(rows[0]["track_metadata_available"])
        self.assertEqual(rows[0]["audio_track_count"], 1)
        self.assertEqual(rows[0]["subtitle_track_count"], 1)
        self.assertFalse(rows[0]["runtime_effective_settings_available"])
        self.assertEqual(rows[0]["library_effective_settings_scope"], "library_only")

    def test_queue_preview_rows_annotate_folder_override_and_clear_no_match(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [{"source_path": "C:/Source/TV/Show/Season 01/Show - S01E01.mkv", "root_path": "C:/Source/TV"}],
            factory,
            file_override_manifest={
                "version": 1,
                "entries": {"c:/source/tv/show/season 01": {"subtitles": {"stripAll": True}}},
            },
        )
        self.assertTrue(rows[0]["has_file_override"])
        self.assertEqual(rows[0]["file_override_scope"], "folder")
        self.assertEqual(rows[0]["file_override_path"], "c:/source/tv/show/season 01")

        no_match = queue_preview_rows(
            [{"source_path": "C:/Source/TV/Show/Season 01/Show - S01E01.mkv", "root_path": "C:/Source/TV"}],
            factory,
            file_override_manifest={"version": 1, "entries": {}},
        )
        self.assertFalse(no_match[0]["has_file_override"])

    def test_queue_preview_rows_do_not_annotate_override_artifact_rows_as_media(self) -> None:
        def factory(_raw: dict[str, object]) -> QueueRecord:
            record = _record()
            record.source_path = Path("C:/Source/TV/Show/Season 01/Show - S01E01.mediapipeline.override.json")
            record.display_name = "Show - S01E01.mediapipeline.override.json"
            return record

        rows = queue_preview_rows(
            [{"source_path": "C:/Source/TV/Show/Season 01/Show - S01E01.mediapipeline.override.json"}],
            factory,
            file_override_manifest={
                "version": 1,
                "entries": {"c:/source/tv/show/season 01": {"audio": {"maxChannels": 2}}},
            },
        )

        self.assertNotIn("has_file_override", rows[0])
        self.assertFalse(rows[0]["track_metadata_available"])

    def test_queue_preview_library_effective_settings_stays_library_only(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Anime/Show/Season 01/Show - S01E01.mkv",
                    "root_path": "C:/Anime",
                    "library_id": "anime",
                    "library_name": "Anime",
                    "library_output_root": "D:/AnimeProcessed",
                    "library_settings_overrides": {"VideoPreset": "p5"},
                    "library_effective_settings": {"VideoPreset": "p5", "RoutingProfile": "plex"},
                    "runtime_effective_settings": {"VideoPreset": "p7", "FolderOverride": "not-library"},
                }
            ],
            factory,
        )

        self.assertEqual(rows[0]["library_effective_settings"], {"VideoPreset": "p5", "RoutingProfile": "plex"})
        self.assertEqual(rows[0]["library_effective_settings_scope"], "library_only")
        self.assertFalse(rows[0]["runtime_effective_settings_available"])
        self.assertEqual(rows[0]["override_layers_pending"], ["show", "folder", "file"])
        self.assertNotIn("runtime_effective_settings", rows[0])
        self.assertNotIn("FolderOverride", rows[0]["library_effective_settings"])

    def test_queue_completion_gate_keeps_promotion_evidence_without_final_runtime_claim(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Concerts/Concert.mkv",
                    "root_path": "C:/Concerts",
                    "library_id": "concerts",
                    "library_name": "Concerts",
                    "library_designation": "auto",
                    "library_output_root": "D:/Processed",
                    "library_promotion_enabled": True,
                    "library_promotion_destination": "H:/Concerts",
                    "library_promotion_rule_id": "library-profile-concerts",
                    "library_promotion_rule_label": "Concerts promotion",
                    "library_settings_override_keys": ["RoutingProfile", "ConvertVobSubToSrt"],
                    "library_effective_settings": {
                        "RoutingProfile": "plex",
                        "ConvertVobSubToSrt": True,
                    },
                    "runtime_effective_settings": {
                        "RoutingProfile": "encode",
                        "ShowOverride": "not-library",
                        "FolderOverride": "not-library",
                        "FileOverride": "not-library",
                    },
                }
            ],
            factory,
        )

        row = rows[0]
        self.assertEqual(row["library_id"], "concerts")
        self.assertEqual(row["library_designation"], "auto")
        self.assertTrue(row["library_promotion_enabled"])
        self.assertEqual(row["library_promotion_destination"], "H:/Concerts")
        self.assertEqual(row["library_promotion_rule_id"], "library-profile-concerts")
        self.assertEqual(row["library_effective_settings_scope"], "library_only")
        self.assertFalse(row["runtime_effective_settings_available"])
        self.assertEqual(row["override_layers_pending"], ["show", "folder", "file"])
        self.assertNotIn("runtime_effective_settings", row)
        self.assertNotIn("ShowOverride", row["library_effective_settings"])
        self.assertNotIn("FolderOverride", row["library_effective_settings"])
        self.assertNotIn("FileOverride", row["library_effective_settings"])
        self.assertIn("Library profile: Concerts (concerts)", row["route_evidence_lines"])
        self.assertIn("Library designation: auto", row["route_evidence_lines"])
        self.assertIn("Library promotion: enabled", row["route_evidence_lines"])
        self.assertIn("Library promotion destination: H:/Concerts", row["route_evidence_lines"])
        self.assertIn("Library promotion rule: Concerts promotion (library-profile-concerts)", row["route_evidence_lines"])
        self.assertIn(
            "Runtime effective settings: resolved during job processing; pending layers: show, folder, file",
            row["route_evidence_lines"],
        )

    def test_queue_preview_promotion_evidence_handles_inherited_output_root(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Concerts/Concert.mkv",
                    "root_path": "C:/Concerts",
                    "library_id": "concerts",
                    "library_name": "Concerts",
                    "library_designation": "auto",
                    "library_output_root": "D:/Processed",
                    "library_output_root_state": "inherited",
                    "library_output_root_source_key": "Outsource",
                    "library_promotion_enabled": True,
                    "library_promotion_destination": "H:/Concerts",
                    "library_promotion_rule_id": "library-profile-concerts",
                    "library_promotion_rule_label": "Concerts promotion",
                    "library_settings_override_keys": ["RoutingProfile"],
                    "library_effective_settings": {"RoutingProfile": "plex"},
                }
            ],
            factory,
        )

        row = rows[0]
        self.assertEqual(row["library_output_root"], "D:/Processed")
        self.assertEqual(row["library_output_root_state"], "inherited")
        self.assertEqual(row["library_output_root_source_key"], "Outsource")
        self.assertTrue(row["library_promotion_enabled"])
        self.assertEqual(row["library_promotion_destination"], "H:/Concerts")
        self.assertEqual(row["library_promotion_rule_id"], "library-profile-concerts")
        self.assertIn("Library output root state: inherited from Outsource", row["route_evidence_lines"])
        self.assertIn("Library promotion: enabled", row["route_evidence_lines"])
        self.assertIn("Library promotion destination: H:/Concerts", row["route_evidence_lines"])
        self.assertIn("Library promotion rule: Concerts promotion (library-profile-concerts)", row["route_evidence_lines"])
        self.assertFalse(row["runtime_effective_settings_available"])
        self.assertNotIn("runtime_effective_settings", row)

    def test_queue_preview_promotion_evidence_handles_explicit_output_equal_to_outsource(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Concerts/Concert.mkv",
                    "root_path": "C:/Concerts",
                    "library_id": "concerts",
                    "library_name": "Concerts",
                    "library_designation": "auto",
                    "library_output_root": "D:/Processed",
                    "path_field_state": {
                        "output_path": {
                            "state": "explicit",
                            "source_key": "",
                        }
                    },
                    "library_promotion_enabled": True,
                    "final_library_destination_root": "H:/Concerts",
                    "final_library_rule_id": "library-profile-concerts",
                    "final_library_rule_label": "Concerts promotion",
                    "library_settings_override_keys": ["RoutingProfile"],
                    "library_effective_settings": {"RoutingProfile": "plex"},
                }
            ],
            factory,
        )

        row = rows[0]
        self.assertEqual(row["library_output_root"], "D:/Processed")
        self.assertEqual(row["library_output_root_state"], "explicit")
        self.assertEqual(row["library_promotion_destination"], "H:/Concerts")
        self.assertEqual(row["library_promotion_rule_id"], "library-profile-concerts")
        self.assertIn("Library output root state: explicit", row["route_evidence_lines"])
        self.assertNotIn("Library output root state: inherited from Outsource", row["route_evidence_lines"])
        self.assertIn("Library promotion rule: Concerts promotion (library-profile-concerts)", row["route_evidence_lines"])

    def test_queue_preview_promotion_evidence_handles_disabled_promotion(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Movies/Movie.mkv",
                    "root_path": "C:/Movies",
                    "library_id": "movies",
                    "library_name": "Movies",
                    "library_designation": "movie",
                    "library_output_root": "D:/Outsource",
                    "library_promotion_enabled": False,
                    "library_settings_override_keys": [],
                    "library_effective_settings": {"RoutingProfile": "plex"},
                }
            ],
            factory,
        )

        row = rows[0]
        self.assertFalse(row["library_promotion_enabled"])
        self.assertEqual(row["library_promotion_destination"], "")
        self.assertEqual(row["library_promotion_rule_id"], "")
        self.assertIn("Library promotion: disabled", row["route_evidence_lines"])
        self.assertFalse(row["runtime_effective_settings_available"])

    def test_queue_preview_keeps_persisted_override_keys_for_vobsub_and_equal_global(self) -> None:
        def factory(_raw: dict[str, object]) -> object:
            return _record()

        rows = queue_preview_rows(
            [
                {
                    "source_path": "C:/Movies/Movie.mkv",
                    "root_path": "C:/Movies",
                    "library_id": "movies",
                    "library_name": "Movies",
                    "library_designation": "movie",
                    "library_output_root": "D:/Outsource/Movies",
                    "library_settings_override_keys": [
                        "VideoPreset",
                        "ConvertVobSubToSrt",
                        "DropVobSubAfterConversion",
                        "VobSubExtractLanguages",
                        "VobSubOcrToolPath",
                        "VobSubOcrTimeoutSeconds",
                        "TreatVobSubSignsSongsAsForced",
                    ],
                    "library_settings_overrides": {
                        "VideoPreset": "p5",
                        "ConvertVobSubToSrt": True,
                    },
                    "library_effective_settings": {
                        "VideoPreset": "p5",
                        "ConvertVobSubToSrt": True,
                    },
                }
            ],
            factory,
        )

        row = rows[0]
        self.assertIn("VideoPreset", row["library_settings_override_keys"])
        self.assertIn("ConvertVobSubToSrt", row["library_settings_override_keys"])
        self.assertIn("VobSubOcrTimeoutSeconds", row["library_settings_override_keys"])
        self.assertEqual(row["library_settings_overrides"]["VideoPreset"], "p5")
        self.assertEqual(row["library_effective_settings"]["VideoPreset"], "p5")
        self.assertNotIn("Processing Strategy", row["library_settings_override_keys"])
        self.assertNotIn("Encoder Speed Preset", row["library_settings_override_keys"])
        self.assertIn(
            "Library override keys: VideoPreset, ConvertVobSubToSrt, DropVobSubAfterConversion, VobSubExtractLanguages, VobSubOcrToolPath, VobSubOcrTimeoutSeconds, TreatVobSubSignsSongsAsForced",
            row["route_evidence_lines"],
        )

    def test_queue_preview_metadata_counts_backend_open_targets(self) -> None:
        rows = [queue_record_to_row(_record())]
        metadata = queue_preview_metadata(
            {
                "movie_count_total": 0,
                "tv_count_total": 1,
                "runnable_count": 1,
                "excluded_rows": [
                    {
                        "source_path": "C:/Source/TV/Show/Season 01/Already Done.mkv",
                        "root_path": "C:/Source/TV",
                        "reason_code": "completed_manifest",
                    }
                ],
            },
            rows,
        )

        self.assertEqual(
            metadata["available_open_target_counts"],
            {"source_file": 1, "source_folder": 1, "source_root": 1},
        )
        self.assertEqual(metadata["excluded_rows"][0]["available_open_targets"], ["source_file", "source_folder", "source_root"])

    def test_queue_preview_metadata_preserves_zero_runnable_count(self) -> None:
        rows = [queue_record_to_row(_record())]
        metadata = queue_preview_metadata(
            {
                "movie_count_total": 1,
                "tv_count_total": 0,
                "runnable_count": 0,
                "excluded_rows": [],
            },
            rows,
        )

        self.assertEqual(metadata["runnable_count"], 0)
        self.assertEqual(metadata["completed_excluded_count"], 1)

    def test_queue_source_scan_progress_is_backend_authored_indeterminate(self) -> None:
        payload = queue_source_scan_progress_payload(
            source="C:/State/Progress/queue_snapshot.json",
            row_count=2,
            metadata={
                "produced_at": "2026-05-17T10:00:00Z",
                "source_count_total": 3,
                "movie_count_total": 1,
                "tv_count_total": 2,
                "runnable_count": 2,
                "snapshot_file_freshness_status": "fresh",
                "produced_freshness_status": "fresh",
            },
        )

        self.assertEqual(payload["schema_version"], "desktop_queue_source_scan_progress.v1")
        self.assertEqual(payload["status"], "complete")
        self.assertFalse(payload["stale"])
        self.assertIn("indeterminate until backend scanner telemetry", "\n".join(payload["summary_lines"]))
        self.assertEqual(payload["progress_bars"][0]["id"], "queue_source_scan")
        self.assertEqual(payload["progress_bars"][0]["mode"], "indeterminate")
        self.assertEqual(payload["progress_bars"][0]["status"], "complete")

    def test_queue_source_scan_progress_preserves_zero_runnable_count(self) -> None:
        payload = queue_source_scan_progress_payload(
            row_count=2,
            metadata={
                "source_count_total": 2,
                "movie_count_total": 2,
                "tv_count_total": 0,
                "runnable_count": 0,
            },
        )

        self.assertIn("Runnable rows loaded: 0", payload["summary_lines"])
        self.assertIn("runnable 0", payload["progress_bars"][0]["detail"])

    def test_queue_preview_warning_constants_are_stable(self) -> None:
        self.assertEqual(queue_preview_warnings([]), [EMPTY_QUEUE_SNAPSHOT_WARNING])
        self.assertEqual(queue_preview_warnings([{"source_path": "C:/Source/file.mkv"}]), [])
        self.assertEqual(NO_QUEUE_SNAPSHOT_WARNING, "No queue snapshot is available yet.")
        self.assertEqual(QUEUE_PREVIEW_SERVICE_WARNING, "Queue preview service is not available.")
        self.assertEqual(INVALID_QUEUE_SNAPSHOT_WARNING, "Queue snapshot is missing or invalid.")


if __name__ == "__main__":
    unittest.main()
