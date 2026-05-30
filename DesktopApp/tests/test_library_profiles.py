from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.library_profiles import (
    LIBRARY_DESIGNATIONS,
    coerce_library_overrides,
    effective_library_profiles_from_config,
    library_override_state,
    library_profiles_from_config,
    mirror_legacy_keys_from_library_profiles,
    resolve_effective_library_settings,
    validate_library_profiles,
)
from app.config.validation import validate_config_values
from app.contracts.config import Config


def _path_key(path: str | Path) -> str:
    return str(path).rstrip("\\/").casefold()


def _path_within_root(path: str | Path, root: str | Path) -> bool:
    left = _path_key(path)
    right = _path_key(root)
    return left == right or left.startswith(right + "\\") or left.startswith(right + "/")


def _base_config() -> dict:
    return {
        "SourceMovies": r"C:\Incoming\Movies",
        "SourceTV": r"C:\Incoming\TV",
        "Outsource": r"D:\Processed",
        "LocalBase": r"E:\Scratch",
        "VideoCodec": "hevc_nvenc",
        "VideoPreset": "p7",
        "VideoQuality": 22,
        "OutputContainer": "mkv",
        "EncodeThresholdGB": 8,
        "TVEncodeThresholdGB": 3,
        "MinFreeSpaceGB": 50,
        "OutsourceMinFreeSpaceGB": 50,
        "CompatibleAudioCodecs": ["aac", "ac3"],
        "SubKeepLanguages": ["eng"],
        "SubSDHTitleKeywords": ["sdh"],
        "SubSupplementalKeywords": ["sign"],
        "DropAssAfterConversion": False,
        "RemuxSafeVideoCodecs": ["hevc"],
        "ValidExtensions": [".mkv"],
        "FileStabilityWait": 15,
        "EnableIntegrityCheck": True,
        "CreateTVSubfolder": True,
        "RobocopyFlags": ["/J"],
        "DebugMode": True,
        "SkipStabilityCheck": False,
        "RoutingProfile": "plex_direct_stream",
        "RouteThresholdMode": "compatibility_advisory",
        "SizeGuardMode": "advisory",
        "EncodeTuningPreset": "balanced_nvenc",
        "EncodeLadder": "auto",
        "AudioPassthroughProfile": "custom_codec_list",
        "AudioTranscodeCodec": "eac3",
        "AudioTranscodeBitrate": "640k",
        "AudioDownmixMode": "max_channels",
        "MergeThresholdMs": 150,
        "FFmpegEncodeTimeoutSeconds": 3600,
        "FFmpegRemuxTimeoutSeconds": 1800,
        "SubtitleExtractTimeoutSeconds": 300,
        "SubtitleProbeTimeoutSeconds": 30,
        "BdpgsOcrTimeoutSeconds": 1800,
        "PriorityMarkers": ["[NOW]"],
        "SourceScanIntervalSeconds": 300,
        "ProcessedIndexRefreshSeconds": 900,
        "TransientFailureRetryLimit": 3,
        "RobocopyTimeoutSeconds": 3600,
        "SourceScanTimeoutSeconds": 300,
        "IndexScanTimeoutSeconds": 300,
        "CleanupScanTimeoutSeconds": 300,
        "CleanupStaleAgeHours": 24,
    }


class LibraryProfileTests(unittest.TestCase):
    def test_legacy_config_synthesizes_movie_and_tv_profiles(self) -> None:
        profiles = library_profiles_from_config(_base_config())

        self.assertEqual([profile["id"] for profile in profiles[:2]], ["movies", "tv"])
        self.assertEqual(profiles[0]["source_path"], r"C:\Incoming\Movies")
        self.assertEqual(profiles[1]["source_path"], r"C:\Incoming\TV")
        self.assertEqual(profiles[0]["output_path"], r"D:\Processed")

    def test_library_overrides_merge_with_default_editor_video_subtitle_and_audio(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "name": "Movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "editor": {"RoutingProfile": "manual"},
                    "video": {"VideoQuality": 19},
                    "subtitles": {"SubKeepLanguages": ["eng", "und"]},
                    "audio": {"AudioMaxChannels": 2},
                },
            }
        ]

        profile = effective_library_profiles_from_config(values)[0]

        self.assertEqual(profile["effective_editor"]["VideoCodec"], "hevc_nvenc")
        self.assertEqual(profile["effective_editor"]["RoutingProfile"], "manual")
        self.assertEqual(profile["effective_video"]["VideoQuality"], 19)
        self.assertEqual(profile["effective_subtitles"]["SubKeepLanguages"], ["eng", "und"])
        self.assertEqual(profile["effective_audio"]["AudioMaxChannels"], 2)
        self.assertEqual(profile["effective_media"]["AudioMaxChannels"], 2)

    def test_old_configs_without_overrides_load_with_empty_override_groups(self) -> None:
        profile = library_profiles_from_config(_base_config())[0]

        self.assertEqual(profile["overrides"], {"editor": {}, "video": {}, "subtitles": {}, "audio": {}})

    def test_new_custom_libraries_start_with_empty_overrides(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "concerts", "designation": "auto", "source_path": r"F:\Concerts", "output_path": r"G:\Processed"},
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")

        self.assertEqual(profile["overrides"], {"editor": {}, "video": {}, "subtitles": {}, "audio": {}})

    def test_missing_override_fields_inherit_global_defaults(self) -> None:
        values = _base_config()
        profile = {
            "id": "movies",
            "designation": "movie",
            "overrides": {"audio": {"AudioMaxChannels": 2}},
        }

        effective = resolve_effective_library_settings(values, profile)

        self.assertEqual(effective["audio"]["AudioMaxChannels"], 2)
        self.assertEqual(effective["audio"]["AudioTranscodeCodec"], "eac3")
        self.assertEqual(effective["video"]["VideoQuality"], 22)

    def test_override_fields_beat_global_defaults(self) -> None:
        values = _base_config()
        profile = {"id": "movies", "overrides": {"video": {"VideoPreset": "p5"}}}

        effective = resolve_effective_library_settings(values, profile)

        self.assertEqual(effective["video"]["VideoPreset"], "p5")

    def test_override_equal_to_global_default_still_counts_as_override(self) -> None:
        values = _base_config()
        profile = {"id": "movies", "overrides": {"audio": {"AudioTranscodeCodec": "eac3"}}}

        effective = resolve_effective_library_settings(values, profile)
        state = library_override_state(profile)

        self.assertEqual(effective["audio"]["AudioTranscodeCodec"], "eac3")
        self.assertTrue(state["audio"]["AudioTranscodeCodec"])

    def test_clearing_one_override_restores_only_that_field(self) -> None:
        values = _base_config()
        profile = {"id": "movies", "overrides": {"audio": {"AudioMaxChannels": 2}}}

        effective = resolve_effective_library_settings(values, profile)

        self.assertEqual(effective["audio"]["AudioMaxChannels"], 2)
        self.assertEqual(effective["audio"]["AudioTranscodeCodec"], "eac3")
        self.assertNotIn("AudioTranscodeCodec", library_override_state(profile)["audio"])

    def test_clearing_all_overrides_restores_full_inheritance(self) -> None:
        values = _base_config()
        profile = {
            "id": "movies",
            "overrides": {"editor": {}, "video": {}, "subtitles": {}, "audio": {}},
        }

        effective = resolve_effective_library_settings(values, profile)

        self.assertEqual(effective["editor"]["RoutingProfile"], values["RoutingProfile"])
        self.assertEqual(effective["video"]["VideoQuality"], values["VideoQuality"])
        self.assertEqual(effective["subtitles"]["SubKeepLanguages"], values["SubKeepLanguages"])
        self.assertEqual(effective["audio"]["AudioTranscodeCodec"], values["AudioTranscodeCodec"])

    def test_legacy_editor_and_media_overrides_coerce_to_nested_groups(self) -> None:
        profile = {
            "id": "movies",
            "editor_overrides": {"RoutingProfile": "manual"},
            "media_overrides": {"VideoQuality": 19, "AudioMaxChannels": 2, "SubKeepLanguages": ["und"]},
        }

        overrides = coerce_library_overrides(profile)

        self.assertEqual(overrides["editor"]["RoutingProfile"], "manual")
        self.assertEqual(overrides["video"]["VideoQuality"], 19)
        self.assertEqual(overrides["audio"]["AudioMaxChannels"], 2)
        self.assertEqual(overrides["subtitles"]["SubKeepLanguages"], ["und"])

    def test_legacy_mixed_and_custom_designations_normalize_to_auto(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "extras", "name": "Extras", "designation": "mixed", "source_path": r"F:\Extras", "output_path": r"G:\Processed"},
            {"id": "concerts", "name": "Concerts", "designation": "custom", "source_path": r"F:\Concerts", "output_path": r"G:\Processed"},
        ]

        profiles = {profile["id"]: profile for profile in library_profiles_from_config(values)}

        self.assertEqual(LIBRARY_DESIGNATIONS, ("movie", "tv", "auto"))
        self.assertEqual(profiles["extras"]["designation"], "auto")
        self.assertEqual(profiles["concerts"]["designation"], "auto")

    def test_profile_patch_mirrors_legacy_paths_and_promotion_rules(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "name": "Movies",
                "designation": "movie",
                "source_path": r"F:\Movies",
                "output_path": r"G:\Processed",
                "promotion_enabled": True,
                "promotion_destination": r"H:\Movies",
            },
            {
                "id": "tv",
                "name": "TV",
                "designation": "tv",
                "source_path": r"F:\TV",
                "output_path": r"G:\Processed",
            },
        ]

        mirrored = mirror_legacy_keys_from_library_profiles(values, require_profiles=True)

        self.assertEqual(mirrored["SourceMovies"], r"F:\Movies")
        self.assertEqual(mirrored["SourceTV"], r"F:\TV")
        self.assertEqual(mirrored["Outsource"], r"G:\Processed")
        self.assertEqual(mirrored["FinalLibraryPromotionRules"][0]["destination_root"], r"H:\Movies")

    def test_validation_rejects_blank_enabled_library_paths(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": "", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
            {"id": "anime", "designation": "tv", "source_path": "", "output_path": r"D:\Processed", "enabled": True},
        ]
        errors: list[str] = []
        warnings: list[str] = []

        validate_library_profiles(
            values,
            errors,
            warnings,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("Library profile Anime source_path is required.", errors)

    def test_validation_rejects_unknown_designation_with_auto_wording(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Incoming\Movies", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
            {"id": "extras", "designation": "documentary", "source_path": r"C:\Incoming\Extras", "output_path": r"D:\Processed"},
        ]
        errors: list[str] = []
        warnings: list[str] = []

        validate_library_profiles(
            values,
            errors,
            warnings,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("Library profile Extras designation must be movie, tv, or auto.", errors)

    def test_config_contract_accepts_library_profiles(self) -> None:
        config = Config.model_validate(
            {
                **_base_config(),
                "LibraryProfiles": [
                    {
                        "id": "movies",
                        "name": "Movies",
                        "enabled": True,
                        "designation": "movie",
                        "source_path": r"C:\Incoming\Movies",
                        "output_path": r"D:\Processed",
                        "promotion_enabled": False,
                        "promotion_destination": "",
                        "overrides": {
                            "editor": {},
                            "video": {},
                            "subtitles": {},
                            "audio": {},
                        },
                    }
                ],
            }
        )

        self.assertEqual(config.LibraryProfiles[0]["id"], "movies")

    def test_preview_save_validation_accepts_library_profiles_and_warns_mirror(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Incoming\Movies", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])
        self.assertTrue(any("mirrors its primary Movie/TV paths" in warning for warning in warnings))

    def test_validation_rejects_invalid_library_override_value(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {"audio": {"AudioMaxChannels": 99}},
            },
        ]

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertTrue(any("Library profile Movies override is invalid" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
