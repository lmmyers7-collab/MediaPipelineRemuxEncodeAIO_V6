from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.config.library_profiles import (
    LIBRARY_DESIGNATIONS,
    LIBRARY_OVERRIDE_KEYS_BY_GROUP,
    apply_library_profile_resets,
    coerce_library_overrides,
    effective_library_profile_for_source_path,
    effective_library_profiles_from_config,
    library_profiles_from_wizard_payload,
    library_override_state,
    library_profile_signature,
    library_profile_state_from_config,
    library_profiles_from_config,
    library_compatibility_presets,
    mirror_legacy_keys_from_library_profiles,
    mp4_compatibility_preset,
    normalize_library_profile_config_values,
    promotion_rules_from_library_profiles,
    resolve_effective_library_settings,
    validate_library_profiles,
)
from mediapipeline.core.config.load import default_powershell_host, load_psd1_mapping, serialize_psd1_document
from mediapipeline.core.config.metadata import CONFIG_MANAGED_KEYS
from mediapipeline.core.config.metadata_parts.field_definitions import (
    CONFIG_FIELD_DEFINITIONS,
    METADATA_LIBRARY_OVERRIDE_KEYS_BY_GROUP,
)
from mediapipeline.core.config.settings_wizard import wizard_changes
from mediapipeline.core.config.validation import validate_config_values
from mediapipeline.contracts.config import CONFIG_KEY_ORDER, NETWORK_CONFIG_KEYS, Config


VOBSUB_LIBRARY_OVERRIDE_KEYS = {
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "VobSubExtractLanguages",
    "VobSubOcrToolPath",
    "VobSubOcrTimeoutSeconds",
    "TreatVobSubSignsSongsAsForced",
}


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
        "MovieRoute1080pTargetSizeGB": 8,
        "MovieRoute1440pTargetSizeGB": 8,
        "MovieRoute4KTargetSizeGB": 8,
        "TVRoute1080pTargetSizeGB": 3,
        "TVRoute1440pTargetSizeGB": 3,
        "TVRoute4KTargetSizeGB": 3,
        "Route1080pMaxVideoBitrateMbps": 20,
        "Route1440pMaxVideoBitrateMbps": 35,
        "Route4KMaxVideoBitrateMbps": 35,
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
        "VobSubOcrTimeoutSeconds": 1800,
        "PriorityMarkers": ["[NOW]"],
        "SourceScanIntervalSeconds": 300,
        "ProcessedIndexRefreshSeconds": 900,
        "CoordinatorMaxJobRetries": 3,
        "TransientFailureRetryLimit": 3,
        "RobocopyTimeoutSeconds": 3600,
        "SourceScanTimeoutSeconds": 300,
        "IndexScanTimeoutSeconds": 300,
        "CleanupScanTimeoutSeconds": 300,
        "CleanupStaleAgeHours": 24,
    }


def _backend_library_override_keys() -> set[str]:
    return {key for keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.values() for key in keys}


def _backend_library_override_keys_by_group_from_metadata() -> dict[str, tuple[str, ...]]:
    return {group: tuple(keys) for group, keys in METADATA_LIBRARY_OVERRIDE_KEYS_BY_GROUP.items()}


def _powershell_library_override_keys() -> set[str]:
    engine_paths = find_repo_root(Path(__file__)) / "ops" / "pipeline" / "engine" / "paths"
    module_text = "\n".join(
        (
            engine_paths / path
        ).read_text(encoding="utf-8")
        for path in ("output_path_planning.ps1", "effective_settings.ps1")
    )
    match = re.search(
        r"function\s+Get-MediaPipelineLibraryOverrideConfigKeys\s*\{(?P<body>.*?)^\}",
        module_text,
        re.S | re.M,
    )
    if match is None:
        raise AssertionError("Get-MediaPipelineLibraryOverrideConfigKeys was not found.")
    return set(re.findall(r"'([^']+)'", match.group("body")))


def _backend_field_metadata() -> dict[str, dict[str, object]]:
    return {str(field["key"]): field for field in CONFIG_FIELD_DEFINITIONS}


def _inherited_fields(profile: dict) -> set[str]:
    tracking = profile.get("default_tracking", {})
    fields = tracking.get("inherited_fields", []) if isinstance(tracking, dict) else []
    return {str(field) for field in fields}


def _profile_state_by_id(values: dict) -> dict[str, dict]:
    return {str(state["library_id"]): state for state in library_profile_state_from_config(values)}


def _profile_by_id(values: dict) -> dict[str, dict]:
    return {str(profile["id"]): profile for profile in library_profiles_from_config(values)}


class LibraryProfileTests(unittest.TestCase):
    def test_vobsub_keys_are_backend_subtitle_library_overrides(self) -> None:
        self.assertLessEqual(VOBSUB_LIBRARY_OVERRIDE_KEYS, set(LIBRARY_OVERRIDE_KEYS_BY_GROUP["subtitles"]))

    def test_library_override_registry_is_derived_from_backend_metadata(self) -> None:
        self.assertEqual(
            LIBRARY_OVERRIDE_KEYS_BY_GROUP,
            _backend_library_override_keys_by_group_from_metadata(),
        )

    def test_backend_library_override_keys_have_field_metadata(self) -> None:
        self.assertEqual(sorted(_backend_library_override_keys() - set(CONFIG_MANAGED_KEYS)), [])

    def test_mp4_compatibility_preset_is_library_override_only_and_validates(self) -> None:
        preset = mp4_compatibility_preset()
        self.assertEqual(preset["id"], "mp4_compatibility")
        self.assertEqual(library_compatibility_presets()[0]["id"], "mp4_compatibility")
        override_keys = _backend_library_override_keys()
        for group, values in preset["overrides"].items():
            with self.subTest(group=group):
                self.assertIn(group, LIBRARY_OVERRIDE_KEYS_BY_GROUP)
            for key in values:
                with self.subTest(group=group, key=key):
                    self.assertIn(key, override_keys)
                    self.assertIn(key, LIBRARY_OVERRIDE_KEYS_BY_GROUP[group])

        config = _base_config()
        config["LibraryProfiles"] = [
            {
                "id": "movies",
                "name": "Movies",
                "enabled": True,
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": preset["overrides"],
            }
        ]
        errors, warnings = validate_config_values(
            config,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )
        self.assertEqual(errors, [])
        self.assertIsInstance(warnings, list)

    def test_backend_library_override_metadata_matches_persisted_groups(self) -> None:
        self.assertEqual(tuple(LIBRARY_OVERRIDE_KEYS_BY_GROUP), ("editor", "video", "subtitles", "audio"))
        metadata = _backend_field_metadata()

        for group, keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.items():
            for key in keys:
                with self.subTest(group=group, key=key):
                    field = metadata[key]
                    self.assertEqual(field["persisted_key"], key)
                    self.assertEqual(field["override_group"], group)
                    self.assertEqual(field["scope"], "library_overridable")
                    self.assertTrue(field["library_override_allowed"])

    def test_non_library_metadata_scopes_are_not_backend_override_keys(self) -> None:
        metadata = _backend_field_metadata()
        backend_keys = _backend_library_override_keys()

        for field in metadata.values():
            key = str(field["key"])
            if field["scope"] == "library_overridable":
                continue
            with self.subTest(key=key, scope=field["scope"]):
                self.assertFalse(field["library_override_allowed"])
                self.assertNotIn(key, backend_keys)

    def test_backend_library_override_keys_are_registered_config_keys(self) -> None:
        registered_keys = set(CONFIG_KEY_ORDER) | set(NETWORK_CONFIG_KEYS)

        self.assertEqual(sorted(_backend_library_override_keys() - registered_keys), [])

    def test_powershell_library_override_allowlist_matches_backend_keys(self) -> None:
        self.assertEqual(_powershell_library_override_keys(), _backend_library_override_keys())
        self.assertLessEqual(VOBSUB_LIBRARY_OVERRIDE_KEYS, _powershell_library_override_keys())

    def test_legacy_config_synthesizes_movie_and_tv_profiles(self) -> None:
        profiles = library_profiles_from_config(_base_config())

        self.assertEqual([profile["id"] for profile in profiles[:2]], ["movies", "tv"])
        self.assertEqual(profiles[0]["source_path"], r"C:\Incoming\Movies")
        self.assertEqual(profiles[1]["source_path"], r"C:\Incoming\TV")
        self.assertEqual(profiles[0]["output_path"], r"D:\Processed")
        self.assertLessEqual({"source_path", "output_path"}, _inherited_fields(profiles[0]))
        self.assertLessEqual({"source_path", "output_path"}, _inherited_fields(profiles[1]))

    def test_backend_normalization_preserves_builtin_profiles_when_patch_omits_them(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "anime",
                "name": "Anime",
                "designation": "tv",
                "source_path": r"F:\Anime",
                "output_path": r"G:\AnimeProcessed",
            }
        ]

        normalized = normalize_library_profile_config_values(values, require_profiles=True)
        profiles = normalized["LibraryProfiles"]

        self.assertEqual([profile["id"] for profile in profiles[:3]], ["movies", "tv", "anime"])
        self.assertEqual(profiles[0]["source_path"], r"C:\Incoming\Movies")
        self.assertEqual(profiles[1]["source_path"], r"C:\Incoming\TV")

    def test_validation_rejects_disabled_builtin_profile(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "enabled": False, "source_path": r"C:\Incoming\Movies", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertIn("Movies is a required default library and cannot be disabled.", errors)

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

    def test_custom_library_missing_output_path_inherits_outsource(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "concerts", "designation": "auto", "source_path": r"F:\Concerts"},
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")

        self.assertEqual(profile["source_path"], r"F:\Concerts")
        self.assertEqual(profile["output_path"], r"D:\Processed")
        self.assertIn("output_path", _inherited_fields(profile))
        self.assertNotIn("source_path", _inherited_fields(profile))

    def test_custom_library_blank_output_path_inherits_outsource(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "concerts", "designation": "auto", "source_path": r"F:\Concerts", "output_path": "   "},
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")

        self.assertEqual(profile["output_path"], r"D:\Processed")
        self.assertIn("output_path", _inherited_fields(profile))
        self.assertNotIn("source_path", _inherited_fields(profile))

    def test_custom_library_explicit_output_path_remains_explicit(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": r"G:\ConcertsProcessed",
            },
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")

        self.assertEqual(profile["output_path"], r"G:\ConcertsProcessed")
        self.assertNotIn("output_path", _inherited_fields(profile))

    def test_custom_library_explicit_output_equal_to_outsource_stays_explicit_after_outsource_changes(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "concerts", "designation": "auto", "source_path": r"F:\Concerts", "output_path": r"D:\Processed"},
        ]
        normalized = normalize_library_profile_config_values(values, require_profiles=True)
        profile = next(profile for profile in normalized["LibraryProfiles"] if profile["id"] == "concerts")

        changed_values = {**_base_config(), "Outsource": r"E:\NewProcessed", "LibraryProfiles": [profile]}
        changed_profile = next(
            profile for profile in library_profiles_from_config(changed_values) if profile["id"] == "concerts"
        )

        self.assertEqual(profile["output_path"], r"D:\Processed")
        self.assertNotIn("output_path", _inherited_fields(profile))
        self.assertEqual(changed_profile["output_path"], r"D:\Processed")
        self.assertNotIn("output_path", _inherited_fields(changed_profile))

    def test_default_tracking_unknown_fields_are_preserved(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": "",
                "default_tracking": {
                    "inherited_fields": ["output_path"],
                    "field_default_keys": {"custom_path": "CustomDefault"},
                    "custom_tracking_note": {"kept": True},
                },
            },
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")

        self.assertEqual(profile["output_path"], r"D:\Processed")
        self.assertEqual(profile["default_tracking"]["custom_tracking_note"], {"kept": True})
        self.assertEqual(profile["default_tracking"]["field_default_keys"]["custom_path"], "CustomDefault")
        self.assertEqual(profile["default_tracking"]["field_default_keys"]["output_path"], "Outsource")

    def test_default_tracking_local_dirty_fields_do_not_define_backend_inheritance(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": r"D:\Processed",
                "default_tracking": {
                    "schema_version": "library_profile_default_tracking.v1",
                    "inherited_fields": [],
                    "field_default_keys": {"output_path": "Outsource"},
                    "dirty_fields": ["output_path"],
                    "local_inherited_fields": ["output_path"],
                },
            },
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")
        path_state = _profile_state_by_id(values)["concerts"]["path_fields"]["output_path"]

        self.assertEqual(path_state["state"], "explicit")
        self.assertEqual(path_state["source_key"], "")
        self.assertNotIn("output_path", _inherited_fields(profile))
        self.assertEqual(profile["default_tracking"]["dirty_fields"], ["output_path"])
        self.assertEqual(profile["default_tracking"]["local_inherited_fields"], ["output_path"])

    def test_malformed_default_tracking_normalizes_custom_missing_output_to_inherited_outsource(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "default_tracking": "legacy-bad-shape",
            },
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")

        self.assertEqual(profile["output_path"], r"D:\Processed")
        self.assertIn("output_path", _inherited_fields(profile))

    def test_promotion_destination_is_not_inherited_from_default_tracking(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": "",
                "promotion_enabled": True,
                "promotion_destination": "",
                "default_tracking": {
                    "inherited_fields": ["output_path", "promotion_destination"],
                    "field_default_keys": {"output_path": "Outsource", "promotion_destination": "Outsource"},
                },
            },
        ]

        profile = next(profile for profile in library_profiles_from_config(values) if profile["id"] == "concerts")
        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(profile["output_path"], r"D:\Processed")
        self.assertEqual(profile["promotion_destination"], "")
        self.assertNotIn("promotion_destination", _inherited_fields(profile))
        self.assertIn("Library profile Concerts promotion_destination is required when promotion is enabled.", errors)

    def test_backend_path_state_identifies_synthesized_builtin_defaults(self) -> None:
        states = _profile_state_by_id(_base_config())

        movie_paths = states["movies"]["path_fields"]
        tv_paths = states["tv"]["path_fields"]

        self.assertEqual(movie_paths["source_path"]["state"], "synthesized_builtin_default")
        self.assertEqual(movie_paths["source_path"]["source_key"], "SourceMovies")
        self.assertEqual(movie_paths["output_path"]["state"], "synthesized_builtin_default")
        self.assertEqual(movie_paths["output_path"]["source_key"], "Outsource")
        self.assertEqual(tv_paths["source_path"]["state"], "synthesized_builtin_default")
        self.assertEqual(tv_paths["source_path"]["source_key"], "SourceTV")
        self.assertEqual(tv_paths["output_path"]["state"], "synthesized_builtin_default")
        self.assertEqual(tv_paths["output_path"]["source_key"], "Outsource")

    def test_backend_path_state_preserves_configured_builtin_explicit_paths(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"F:\Movies",
                "output_path": r"G:\MoviesProcessed",
            },
            {
                "id": "tv",
                "designation": "tv",
                "source_path": r"F:\TV",
                "output_path": r"G:\TVProcessed",
            },
        ]

        states = _profile_state_by_id(values)

        self.assertEqual(states["movies"]["path_fields"]["source_path"]["state"], "explicit")
        self.assertEqual(states["movies"]["path_fields"]["source_path"]["source_key"], "")
        self.assertEqual(states["movies"]["path_fields"]["output_path"]["state"], "explicit")
        self.assertEqual(states["movies"]["path_fields"]["output_path"]["source_key"], "")
        self.assertEqual(states["tv"]["path_fields"]["source_path"]["state"], "explicit")
        self.assertEqual(states["tv"]["path_fields"]["source_path"]["source_key"], "")
        self.assertEqual(states["tv"]["path_fields"]["output_path"]["state"], "explicit")
        self.assertEqual(states["tv"]["path_fields"]["output_path"]["source_key"], "")

    def test_backend_path_state_distinguishes_custom_inherited_and_explicit_paths(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "inherited-out", "designation": "auto", "source_path": r"F:\Inherited"},
            {"id": "explicit-out", "designation": "auto", "source_path": r"F:\Explicit", "output_path": r"D:\Processed"},
        ]

        states = _profile_state_by_id(values)
        inherited_paths = states["inherited-out"]["path_fields"]
        explicit_paths = states["explicit-out"]["path_fields"]

        self.assertEqual(inherited_paths["source_path"]["state"], "explicit")
        self.assertEqual(inherited_paths["source_path"]["explicit_value"], r"F:\Inherited")
        self.assertEqual(inherited_paths["output_path"]["state"], "inherited")
        self.assertEqual(inherited_paths["output_path"]["source_key"], "Outsource")
        self.assertEqual(inherited_paths["output_path"]["explicit_value"], None)
        self.assertEqual(explicit_paths["output_path"]["state"], "explicit")
        self.assertEqual(explicit_paths["output_path"]["explicit_value"], r"D:\Processed")
        self.assertEqual(explicit_paths["output_path"]["source_key"], "")

    def test_backend_path_state_reports_invalid_unresolved_required_paths(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "broken", "designation": "auto", "source_path": "", "output_path": ""},
        ]

        state = _profile_state_by_id(values)["broken"]["path_fields"]

        self.assertEqual(state["source_path"]["state"], "invalid_unresolved")
        self.assertTrue(state["source_path"]["required"])
        self.assertEqual(state["output_path"]["state"], "inherited")
        self.assertEqual(state["output_path"]["source_key"], "Outsource")

    def test_backend_path_state_marks_legacy_coerced_origin_without_renaming_fields(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "library_id": "extras",
                "designation": "custom",
                "source_path": r"F:\Extras",
                "output_path": r"G:\ExtrasProcessed",
            },
        ]

        paths = _profile_state_by_id(values)["extras"]["path_fields"]

        self.assertEqual(paths["source_path"]["state"], "explicit")
        self.assertEqual(paths["source_path"]["origin"], "legacy_coerced")
        self.assertEqual(paths["output_path"]["state"], "explicit")
        self.assertEqual(paths["output_path"]["origin"], "legacy_coerced")

    def test_backend_setting_state_distinguishes_inherited_explicit_and_equal_to_global(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "audio": {
                        "AudioTranscodeCodec": "eac3",
                        "AudioMaxChannels": 2,
                    }
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        audio_state = _profile_state_by_id(values)["movies"]["setting_overrides"]["audio"]

        self.assertEqual(audio_state["AudioPassthroughProfile"]["state"], "inherited")
        self.assertEqual(audio_state["AudioTranscodeCodec"]["state"], "explicit")
        self.assertTrue(audio_state["AudioTranscodeCodec"]["value_equals_global"])
        self.assertEqual(audio_state["AudioMaxChannels"]["state"], "explicit")
        self.assertFalse(audio_state["AudioMaxChannels"]["value_equals_global"])

    def test_reset_setting_overrides_removes_keys_without_copying_global_values(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "editor": {"RoutingProfile": "manual"},
                    "video": {"VideoPreset": "p5", "VideoQuality": 19},
                    "subtitles": {"ConvertVobSubToSrt": True},
                    "audio": {},
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        updated, errors = apply_library_profile_resets(
            values,
            [
                {
                    "library_id": "movies",
                    "overrides": {
                        "editor": ["RoutingProfile"],
                        "video": ["VideoPreset"],
                        "subtitles": ["ConvertVobSubToSrt"],
                    },
                }
            ],
        )
        movie = _profile_by_id(updated)["movies"]

        self.assertEqual(errors, [])
        self.assertNotIn("RoutingProfile", movie["overrides"]["editor"])
        self.assertNotIn("VideoPreset", movie["overrides"]["video"])
        self.assertNotIn("ConvertVobSubToSrt", movie["overrides"]["subtitles"])
        self.assertEqual(movie["overrides"]["video"]["VideoQuality"], 19)
        self.assertNotEqual(movie["overrides"]["editor"].get("RoutingProfile"), values["RoutingProfile"])
        self.assertNotEqual(movie["overrides"]["video"].get("VideoPreset"), values["VideoPreset"])

    def test_reset_does_not_remove_explicit_override_equal_to_global_unless_targeted(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "audio": {"AudioTranscodeCodec": "eac3", "AudioMaxChannels": 2},
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        updated, errors = apply_library_profile_resets(
            values,
            [{"library_id": "movies", "overrides": {"audio": ["AudioMaxChannels"]}}],
        )
        audio = _profile_by_id(updated)["movies"]["overrides"]["audio"]

        self.assertEqual(errors, [])
        self.assertEqual(audio["AudioTranscodeCodec"], "eac3")
        self.assertNotIn("AudioMaxChannels", audio)

    def test_reset_builtin_path_fields_use_global_inheritance_markers(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"F:\Movies",
                "output_path": r"G:\MoviesProcessed",
            },
            {
                "id": "tv",
                "designation": "tv",
                "source_path": r"F:\TV",
                "output_path": r"G:\TVProcessed",
            },
        ]

        updated, errors = apply_library_profile_resets(
            values,
            [
                {"library_id": "movies", "path_fields": ["source_path", "output_path"]},
                {"library_id": "tv", "path_fields": ["source_path"]},
            ],
        )
        profiles = _profile_by_id(updated)

        self.assertEqual(errors, [])
        self.assertEqual(profiles["movies"]["source_path"], r"C:\Incoming\Movies")
        self.assertEqual(profiles["movies"]["output_path"], r"D:\Processed")
        self.assertEqual(profiles["movies"]["default_tracking"]["field_default_keys"]["source_path"], "SourceMovies")
        self.assertEqual(profiles["movies"]["default_tracking"]["field_default_keys"]["output_path"], "Outsource")
        self.assertLessEqual({"source_path", "output_path"}, _inherited_fields(profiles["movies"]))
        self.assertEqual(profiles["tv"]["source_path"], r"C:\Incoming\TV")
        self.assertEqual(profiles["tv"]["default_tracking"]["field_default_keys"]["source_path"], "SourceTV")
        self.assertIn("source_path", _inherited_fields(profiles["tv"]))

    def test_reset_custom_output_path_inherits_and_follows_future_outsource_changes(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": r"G:\ConcertsProcessed",
            },
        ]

        updated, errors = apply_library_profile_resets(
            values,
            [{"library_id": "concerts", "path_fields": ["output_path"]}],
        )
        profile = _profile_by_id(updated)["concerts"]
        moved = _profile_by_id({**updated, "Outsource": r"E:\MovedProcessed"})["concerts"]

        self.assertEqual(errors, [])
        self.assertEqual(profile["output_path"], r"D:\Processed")
        self.assertIn("output_path", _inherited_fields(profile))
        self.assertEqual(profile["default_tracking"]["field_default_keys"]["output_path"], "Outsource")
        self.assertEqual(moved["output_path"], r"E:\MovedProcessed")

    def test_reset_rejects_custom_source_and_promotion_destination_inheritance(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": r"G:\ConcertsProcessed",
                "promotion_enabled": True,
                "promotion_destination": r"H:\Concerts",
            },
        ]

        updated, errors = apply_library_profile_resets(
            values,
            [{"library_id": "concerts", "path_fields": ["source_path", "promotion_destination"]}],
        )
        profile = _profile_by_id(updated)["concerts"]

        self.assertIn("Library profile Concerts source_path cannot be reset to inherited.", errors)
        self.assertIn("Library profile Concerts promotion_destination cannot be reset to inherited.", errors)
        self.assertEqual(profile["source_path"], r"F:\Concerts")
        self.assertEqual(profile["promotion_destination"], r"H:\Concerts")
        self.assertNotIn("source_path", _inherited_fields(profile))
        self.assertNotIn("promotion_destination", _inherited_fields(profile))

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

    def test_missing_global_keys_inherit_backend_metadata_defaults(self) -> None:
        values = _base_config()
        for key in (
            "MovieRoute1080pTargetSizeGB",
            "MovieRoute1440pTargetSizeGB",
            "MovieRoute4KTargetSizeGB",
            "TVRoute1080pTargetSizeGB",
            "TVRoute1440pTargetSizeGB",
            "TVRoute4KTargetSizeGB",
            "Route1080pMaxVideoBitrateMbps",
            "Route1440pMaxVideoBitrateMbps",
            "Route4KMaxVideoBitrateMbps",
        ):
            values.pop(key, None)
        profile = {
            "id": "tv",
            "designation": "tv",
            "source_path": r"C:\Incoming\TV",
            "output_path": r"D:\Processed",
        }

        effective = resolve_effective_library_settings(values, profile)
        state = _profile_state_by_id({**values, "LibraryProfiles": [profile]})["tv"]["setting_overrides"]["editor"]

        self.assertEqual(effective["editor"]["MovieRoute1080pTargetSizeGB"], 8)
        self.assertEqual(effective["editor"]["MovieRoute1440pTargetSizeGB"], 8)
        self.assertEqual(effective["editor"]["MovieRoute4KTargetSizeGB"], 8)
        self.assertEqual(effective["editor"]["TVRoute1080pTargetSizeGB"], 3)
        self.assertEqual(effective["editor"]["TVRoute1440pTargetSizeGB"], 3)
        self.assertEqual(effective["editor"]["TVRoute4KTargetSizeGB"], 3)
        self.assertEqual(effective["editor"]["Route1080pMaxVideoBitrateMbps"], 20)
        self.assertEqual(effective["editor"]["Route1440pMaxVideoBitrateMbps"], 35)
        self.assertEqual(effective["editor"]["Route4KMaxVideoBitrateMbps"], 35)
        self.assertEqual(state["Route1080pMaxVideoBitrateMbps"]["state"], "inherited")
        self.assertEqual(state["Route1080pMaxVideoBitrateMbps"]["effective_value"], 20)
        self.assertEqual(state["Route1080pMaxVideoBitrateMbps"]["inherited_value"], 20)

    def test_override_fields_beat_global_defaults(self) -> None:
        values = _base_config()
        profile = {"id": "movies", "overrides": {"video": {"VideoPreset": "p5"}}}

        effective = resolve_effective_library_settings(values, profile)

        self.assertEqual(effective["video"]["VideoPreset"], "p5")

    def test_resolution_bitrate_bucket_overrides_inherit_override_and_reset(self) -> None:
        values = {
            **_base_config(),
            "Route1080pMaxVideoBitrateMbps": 20,
            "Route1440pMaxVideoBitrateMbps": 35,
            "Route4KMaxVideoBitrateMbps": 35,
        }
        profile = {
            "id": "movies",
            "designation": "movie",
            "source_path": r"C:\Incoming\Movies",
            "output_path": r"D:\Processed",
            "overrides": {
                "editor": {
                    "Route1080pMaxVideoBitrateMbps": 24,
                    "Route4KMaxVideoBitrateMbps": 42,
                }
            },
        }

        effective = resolve_effective_library_settings(values, profile)
        state = _profile_state_by_id({**values, "LibraryProfiles": [profile]})["movies"]["setting_overrides"]["editor"]

        self.assertEqual(effective["editor"]["Route1080pMaxVideoBitrateMbps"], 24)
        self.assertEqual(effective["editor"]["Route1440pMaxVideoBitrateMbps"], 35)
        self.assertEqual(effective["editor"]["Route4KMaxVideoBitrateMbps"], 42)
        self.assertEqual(state["Route1440pMaxVideoBitrateMbps"]["state"], "inherited")
        self.assertEqual(state["Route1080pMaxVideoBitrateMbps"]["state"], "explicit")

        updated, errors = apply_library_profile_resets(
            {**values, "LibraryProfiles": [profile]},
            [{"library_id": "movies", "overrides": {"editor": ["Route1080pMaxVideoBitrateMbps"]}}],
        )
        movie = _profile_by_id(updated)["movies"]
        reset_effective = resolve_effective_library_settings(values, movie)

        self.assertEqual(errors, [])
        self.assertNotIn("Route1080pMaxVideoBitrateMbps", movie["overrides"]["editor"])
        self.assertEqual(movie["overrides"]["editor"]["Route4KMaxVideoBitrateMbps"], 42)
        self.assertEqual(reset_effective["editor"]["Route1080pMaxVideoBitrateMbps"], 20)

    def test_global_changes_update_inherited_overrides_but_not_explicit_equal_to_old_global(self) -> None:
        values = _base_config()
        profile = {
            "id": "movies",
            "designation": "movie",
            "overrides": {"video": {"VideoPreset": values["VideoPreset"]}},
        }
        changed_values = {**values, "VideoPreset": "p3", "VideoQuality": 18}

        effective = resolve_effective_library_settings(changed_values, profile)
        state = _profile_state_by_id({**changed_values, "LibraryProfiles": [profile]})["movies"]["setting_overrides"]["video"]

        self.assertEqual(effective["video"]["VideoPreset"], values["VideoPreset"])
        self.assertEqual(effective["video"]["VideoQuality"], 18)
        self.assertEqual(state["VideoPreset"]["state"], "explicit")
        self.assertFalse(state["VideoPreset"]["value_equals_global"])
        self.assertEqual(state["VideoQuality"]["state"], "inherited")

    def test_phase3_metadata_does_not_change_library_effective_settings_shape(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "editor": {"RoutingProfile": "manual"},
                    "video": {"VideoPreset": "p5"},
                    "subtitles": {"ConvertVobSubToSrt": True},
                    "audio": {"AudioMaxChannels": 2},
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        row = effective_library_profiles_from_config(values)[0]

        self.assertEqual(set(row["effective_settings"]), {"editor", "video", "subtitles", "audio"})
        self.assertEqual(set(row["overrides"]), {"editor", "video", "subtitles", "audio"})
        self.assertNotIn("runtime_effective_settings", row)
        self.assertNotIn("show_effective_settings", row)
        self.assertNotIn("folder_effective_settings", row)
        self.assertEqual(row["effective_editor"]["RoutingProfile"], "manual")
        self.assertEqual(row["effective_video"]["VideoPreset"], "p5")
        self.assertEqual(row["effective_video"]["VideoQuality"], values["VideoQuality"])
        self.assertTrue(row["effective_subtitles"]["ConvertVobSubToSrt"])
        self.assertEqual(row["effective_audio"]["AudioMaxChannels"], 2)

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

    def test_legacy_override_equal_to_global_remains_explicit(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "editor_overrides": {"RoutingProfile": values["RoutingProfile"]},
                "media_overrides": {"VideoPreset": values["VideoPreset"]},
            }
        ]

        state = _profile_state_by_id(values)["movies"]["setting_overrides"]

        self.assertEqual(state["editor"]["RoutingProfile"]["state"], "explicit")
        self.assertTrue(state["editor"]["RoutingProfile"]["value_equals_global"])
        self.assertEqual(state["video"]["VideoPreset"]["state"], "explicit")
        self.assertTrue(state["video"]["VideoPreset"]["value_equals_global"])

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

    def test_promotion_rules_use_normalized_custom_output_inherited_from_outsource(self) -> None:
        values = _base_config()
        values["Outsource"] = r"G:\Processed"
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "name": "Concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "promotion_enabled": True,
                "promotion_destination": r"H:\Concerts",
            },
        ]

        rules = promotion_rules_from_library_profiles(values, include_existing=False)

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["source_root"], r"F:\Concerts")
        self.assertEqual(rules[0]["output_root"], r"G:\Processed")
        self.assertEqual(rules[0]["destination_root"], r"H:\Concerts")
        self.assertEqual(rules[0]["library_id"], "concerts")
        self.assertEqual(rules[0]["designation"], "auto")

    def test_promotion_rules_use_explicit_custom_output_equal_to_outsource(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "name": "Concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": values["Outsource"],
                "promotion_enabled": True,
                "promotion_destination": r"H:\Concerts",
            },
        ]

        rules = promotion_rules_from_library_profiles(values, include_existing=False)
        path_state = _profile_state_by_id(values)["concerts"]["path_fields"]["output_path"]

        self.assertEqual(rules[0]["output_root"], values["Outsource"])
        self.assertEqual(path_state["state"], "explicit")
        self.assertEqual(path_state["source_key"], "")

    def test_profile_promotion_rules_suppress_stale_fallback_for_covered_source_roots(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "concerts",
                "name": "Concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": r"G:\ConcertsProcessed",
                "promotion_enabled": True,
                "promotion_destination": r"H:\Concerts",
            },
        ]
        values["FinalLibraryPromotionRules"] = [
            {
                "id": "stale-concerts",
                "source_root": r"F:\Concerts\\",
                "output_root": r"Z:\OldProcessed",
                "destination_root": r"H:\OldConcerts",
                "library_id": "old-concerts",
                "designation": "movie",
            },
            {
                "id": "legacy-uncovered",
                "source_root": r"F:\Legacy",
                "output_root": r"G:\LegacyProcessed",
                "destination_root": r"H:\Legacy",
            },
        ]

        rules = promotion_rules_from_library_profiles(values, include_existing=True)

        self.assertEqual([rule["id"] for rule in rules], ["library-profile-concerts", "legacy-uncovered"])
        self.assertEqual(rules[0]["output_root"], r"G:\ConcertsProcessed")
        self.assertEqual(rules[0]["destination_root"], r"H:\Concerts")
        self.assertEqual(rules[0]["library_id"], "concerts")
        self.assertEqual(rules[0]["designation"], "auto")
        self.assertEqual(rules[1]["source_root"], r"F:\Legacy")

    def test_psd1_round_trip_preserves_backend_patch_shape_and_legacy_mirroring(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "name": "Movies",
                "designation": "movie",
                "source_path": r"F:\Movies",
                "output_path": r"D:\Processed",
                "editor_overrides": {"RoutingProfile": values["RoutingProfile"]},
                "media_overrides": {
                    "VideoPreset": values["VideoPreset"],
                    "ConvertVobSubToSrt": True,
                },
            },
            {
                "id": "tv",
                "name": "TV",
                "designation": "tv",
                "source_path": r"F:\TV",
                "output_path": r"D:\Processed",
            },
            {
                "id": "concerts",
                "name": "Concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": "",
                "promotion_enabled": True,
                "promotion_destination": r"H:\Concerts",
                "overrides": {
                    "editor": {"RoutingProfile": "manual"},
                    "video": {"VideoPreset": values["VideoPreset"]},
                    "subtitles": {"ConvertVobSubToSrt": True},
                    "audio": {},
                },
            },
        ]
        values["FinalLibraryPromotionRules"] = [
            {
                "id": "stale-concerts",
                "source_root": r"F:\Concerts",
                "output_root": r"Z:\OldProcessed",
                "destination_root": r"H:\OldConcerts",
                "library_id": "old-concerts",
                "designation": "movie",
            },
            {
                "id": "legacy-uncovered",
                "source_root": r"F:\Legacy",
                "output_root": r"G:\LegacyProcessed",
                "destination_root": r"H:\Legacy",
            },
        ]

        preview_values = {**values, "RoutingProfile": "manual"}
        preview_values, reset_errors = apply_library_profile_resets(
            preview_values,
            [{"library_id": "concerts", "overrides": {"editor": ["RoutingProfile"]}}],
        )
        preview_values = mirror_legacy_keys_from_library_profiles(
            normalize_library_profile_config_values(preview_values, require_profiles=True),
            require_profiles=True,
        )
        validation_errors, _warnings = validate_config_values(
            preview_values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )
        document_text = serialize_psd1_document(preview_values)

        self.assertEqual(reset_errors, [])
        self.assertEqual(validation_errors, [])
        self.assertIn("RoutingProfile", document_text)
        self.assertNotIn("ProcessingStrategy", document_text)
        self.assertNotIn("OutputSizeCheck", document_text)
        self.assertNotIn("EnforcementMode", document_text)
        self.assertNotIn("library_effective_settings", document_text)
        self.assertNotIn("runtime_effective_settings", document_text)

        with tempfile.TemporaryDirectory() as raw_root:
            config_path = Path(raw_root) / "MediaPipelineConfig.psd1"
            config_path.write_text(document_text, encoding="utf-8")
            loaded = load_psd1_mapping(config_path, default_powershell_host())

        self.assertTrue(loaded.ok, loaded.error)
        reloaded = mirror_legacy_keys_from_library_profiles(
            normalize_library_profile_config_values(loaded.data, require_profiles=True),
            require_profiles=True,
        )
        profiles = _profile_by_id(reloaded)
        state = _profile_state_by_id(reloaded)
        promotion_rules = {str(rule["id"]): rule for rule in reloaded["FinalLibraryPromotionRules"]}

        self.assertEqual(reloaded["RoutingProfile"], "manual")
        self.assertNotIn("ProcessingStrategy", reloaded)
        self.assertNotIn("library_effective_settings", reloaded)
        self.assertNotIn("runtime_effective_settings", reloaded)
        self.assertEqual(reloaded["SourceMovies"], r"F:\Movies")
        self.assertEqual(reloaded["SourceTV"], r"F:\TV")
        self.assertEqual(reloaded["Outsource"], r"D:\Processed")

        self.assertEqual(profiles["concerts"]["output_path"], r"D:\Processed")
        self.assertIn("output_path", _inherited_fields(profiles["concerts"]))
        self.assertNotIn("RoutingProfile", profiles["concerts"]["overrides"]["editor"])
        self.assertEqual(profiles["concerts"]["overrides"]["video"]["VideoPreset"], values["VideoPreset"])
        self.assertTrue(profiles["concerts"]["overrides"]["subtitles"]["ConvertVobSubToSrt"])
        self.assertEqual(
            state["concerts"]["setting_overrides"]["video"]["VideoPreset"]["state"],
            "explicit",
        )
        self.assertTrue(state["concerts"]["setting_overrides"]["video"]["VideoPreset"]["value_equals_global"])

        self.assertEqual(
            state["movies"]["setting_overrides"]["editor"]["RoutingProfile"]["state"],
            "explicit",
        )
        self.assertFalse(state["movies"]["setting_overrides"]["editor"]["RoutingProfile"]["value_equals_global"])
        self.assertEqual(
            state["movies"]["setting_overrides"]["video"]["VideoPreset"]["state"],
            "explicit",
        )
        self.assertTrue(state["movies"]["setting_overrides"]["video"]["VideoPreset"]["value_equals_global"])

        self.assertIn("library-profile-concerts", promotion_rules)
        self.assertIn("legacy-uncovered", promotion_rules)
        self.assertNotIn("stale-concerts", promotion_rules)
        self.assertEqual(promotion_rules["library-profile-concerts"]["output_root"], r"D:\Processed")
        self.assertEqual(promotion_rules["library-profile-concerts"]["destination_root"], r"H:\Concerts")
        self.assertEqual(promotion_rules["library-profile-concerts"]["library_id"], "concerts")
        self.assertEqual(promotion_rules["library-profile-concerts"]["designation"], "auto")

    def test_wizard_changes_emit_canonical_library_profiles_and_promotion_rules(self) -> None:
        wizard = {
            "libraries": [
                {"id": "movies", "name": "Movies", "designation": "movie", "default_source_role": "source_movies", "source_path": r"F:\Movies", "output_path": r"G:\Processed", "enabled": True},
                {"id": "tv", "name": "TV", "designation": "tv", "default_source_role": "source_tv", "source_path": r"F:\TV", "output_path": r"G:\Processed", "enabled": True},
                {"id": "anime", "name": "Anime", "designation": "tv", "source_path": r"F:\Anime", "output_path": r"G:\AnimeProcessed", "promotion_enabled": True, "promotion_destination": r"H:\Anime", "enabled": True},
            ],
            "output": {"root": r"G:\Processed", "publish_mode": "staged_pending", "existing_policy": "skip_existing"},
            "scratch": {"path": r"E:\Scratch"},
            "hardware": {"preferred_codec": "hevc_nvenc"},
            "audio": {"transcode_codec": "eac3"},
            "subtitles": {"languages": ["eng"]},
            "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
            "safety": {},
        }

        changes = wizard_changes(wizard, _base_config())
        profiles = {profile["id"]: profile for profile in changes["LibraryProfiles"]}

        self.assertEqual(changes["SourceMovies"], r"F:\Movies")
        self.assertEqual(changes["SourceTV"], r"F:\TV")
        self.assertEqual(changes["Outsource"], r"G:\Processed")
        self.assertEqual(profiles["anime"]["output_path"], r"G:\AnimeProcessed")
        self.assertTrue(changes["FinalLibraryPromotionEnabled"])
        self.assertEqual(changes["FinalLibraryPromotionRules"][0]["source_root"], r"F:\Anime")
        self.assertEqual(changes["FinalLibraryPromotionRules"][0]["output_root"], r"G:\AnimeProcessed")
        self.assertEqual(changes["FinalLibraryPromotionRules"][0]["destination_root"], r"H:\Anime")

    def test_wizard_and_library_tab_profile_payloads_are_equivalent(self) -> None:
        base = _base_config()
        library_rows = [
            {"id": "movies", "name": "Movies", "designation": "movie", "default_source_role": "source_movies", "source_path": r"F:\Movies", "output_path": r"G:\Processed", "enabled": True},
            {"id": "tv", "name": "TV", "designation": "tv", "default_source_role": "source_tv", "source_path": r"F:\TV", "output_path": r"G:\Processed", "enabled": True},
            {"id": "concerts", "name": "Concerts", "designation": "auto", "source_path": r"F:\Concerts", "output_path": r"G:\ConcertsProcessed", "enabled": True},
        ]
        wizard_profiles = library_profiles_from_wizard_payload(
            {"libraries": library_rows, "output": {"root": r"G:\Processed"}},
            base,
        )
        tab_values = normalize_library_profile_config_values(
            {**base, "SourceMovies": r"F:\Movies", "SourceTV": r"F:\TV", "Outsource": r"G:\Processed", "LibraryProfiles": wizard_profiles},
            require_profiles=True,
        )

        self.assertEqual(
            [library_profile_signature(profile) for profile in wizard_profiles],
            [library_profile_signature(profile) for profile in tab_values["LibraryProfiles"]],
        )

    def test_wizard_preserves_existing_library_overrides_when_row_does_not_edit_them(self) -> None:
        base = _base_config()
        base["LibraryProfiles"] = [
            {
                "id": "movies",
                "name": "Movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {"audio": {"AudioMaxChannels": 2}, "subtitles": {"SubKeepLanguages": ["eng", "und"]}},
            },
            {"id": "tv", "name": "TV", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        changes = wizard_changes(
            {
                "libraries": [
                    {"id": "movies", "name": "Movies", "designation": "movie", "default_source_role": "source_movies", "source_path": r"C:\Incoming\Movies", "enabled": True},
                    {"id": "tv", "name": "TV", "designation": "tv", "default_source_role": "source_tv", "source_path": r"C:\Incoming\TV", "enabled": True},
                ],
                "output": {"root": r"D:\Processed"},
                "scratch": {"path": r"E:\Scratch"},
                "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
                "safety": {},
            },
            base,
        )
        movie = next(profile for profile in changes["LibraryProfiles"] if profile["id"] == "movies")

        self.assertEqual(movie["overrides"]["audio"]["AudioMaxChannels"], 2)
        self.assertEqual(movie["overrides"]["subtitles"]["SubKeepLanguages"], ["eng", "und"])

    def test_wizard_empty_tracking_and_override_payload_preserves_existing_metadata(self) -> None:
        base = _base_config()
        base["LibraryProfiles"] = [
            {
                "id": "movies",
                "name": "Movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {"editor": {"RoutingProfile": base["RoutingProfile"]}},
                "default_tracking": {
                    "schema_version": "library_profile_default_tracking.v1",
                    "inherited_fields": ["source_path"],
                    "field_default_keys": {"source_path": "SourceMovies", "output_path": "Outsource"},
                    "custom_tracking_note": {"kept": True},
                },
            },
            {"id": "tv", "name": "TV", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        changes = wizard_changes(
            {
                "libraries": [
                    {
                        "id": "movies",
                        "name": "Movies",
                        "designation": "movie",
                        "default_source_role": "source_movies",
                        "source_path": r"C:\Incoming\Movies",
                        "output_path": r"D:\Processed",
                        "enabled": True,
                        "overrides": {},
                        "default_tracking": {},
                    },
                    {"id": "tv", "name": "TV", "designation": "tv", "default_source_role": "source_tv", "source_path": r"C:\Incoming\TV", "enabled": True},
                ],
                "output": {"root": r"D:\Processed"},
                "scratch": {"path": r"E:\Scratch"},
                "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
                "safety": {},
            },
            base,
        )
        movie = next(profile for profile in changes["LibraryProfiles"] if profile["id"] == "movies")
        state = _profile_state_by_id({**base, **changes})["movies"]["setting_overrides"]["editor"]["RoutingProfile"]

        self.assertEqual(movie["overrides"]["editor"]["RoutingProfile"], base["RoutingProfile"])
        self.assertEqual(movie["default_tracking"]["custom_tracking_note"], {"kept": True})
        self.assertEqual(state["state"], "explicit")
        self.assertTrue(state["value_equals_global"])

    def test_wizard_custom_blank_output_inherits_outsource(self) -> None:
        base = _base_config()

        profiles = library_profiles_from_wizard_payload(
            {
                "libraries": [
                    {"id": "concerts", "name": "Concerts", "designation": "auto", "source_path": r"F:\Concerts", "output_path": "", "enabled": True},
                ],
                "output": {"root": r"G:\Processed"},
            },
            base,
        )
        values = {**base, "Outsource": r"G:\Processed", "LibraryProfiles": profiles}
        concerts = _profile_by_id(values)["concerts"]
        path_state = _profile_state_by_id(values)["concerts"]["path_fields"]["output_path"]

        self.assertEqual(concerts["output_path"], r"G:\Processed")
        self.assertIn("output_path", _inherited_fields(concerts))
        self.assertEqual(path_state["state"], "inherited")
        self.assertEqual(path_state["source_key"], "Outsource")

    def test_wizard_preserves_explicit_output_equal_to_outsource(self) -> None:
        base = _base_config()
        base["LibraryProfiles"] = [
            {
                "id": "concerts",
                "name": "Concerts",
                "designation": "auto",
                "source_path": r"F:\Concerts",
                "output_path": base["Outsource"],
                "overrides": {"video": {"VideoPreset": base["VideoPreset"]}},
                "default_tracking": {
                    "schema_version": "library_profile_default_tracking.v1",
                    "inherited_fields": [],
                    "field_default_keys": {"output_path": "Outsource"},
                },
            }
        ]

        changes = wizard_changes(
            {
                "libraries": [
                    {
                        "id": "concerts",
                        "name": "Concerts",
                        "designation": "auto",
                        "source_path": r"F:\Concerts",
                        "output_path": base["Outsource"],
                        "enabled": True,
                        "overrides": {},
                        "default_tracking": {},
                    },
                ],
                "output": {"root": base["Outsource"]},
                "scratch": {"path": r"E:\Scratch"},
                "hardware": {"video_preset": base["VideoPreset"]},
                "workers": {"max_parallel_encodes": 1, "parallel_encode_mode": "single"},
                "safety": {},
            },
            base,
        )
        concerts = next(profile for profile in changes["LibraryProfiles"] if profile["id"] == "concerts")
        state = _profile_state_by_id({**base, **changes})["concerts"]

        self.assertNotIn("output_path", _inherited_fields(concerts))
        self.assertEqual(state["path_fields"]["output_path"]["state"], "explicit")
        self.assertEqual(concerts["overrides"]["video"]["VideoPreset"], base["VideoPreset"])
        self.assertEqual(state["setting_overrides"]["video"]["VideoPreset"]["state"], "explicit")
        self.assertTrue(state["setting_overrides"]["video"]["VideoPreset"]["value_equals_global"])

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

    def test_config_contract_rejects_strict_library_profile_json_text(self) -> None:
        cases = [
            (
                "LibraryProfiles",
                '[{"id": "movies", "id": "shadow"}]',
                "duplicate JSON object key: id",
            ),
            (
                "LibraryProfiles",
                '[{"id": "movies", "enabled": NaN}]',
                "non-finite JSON value is not allowed: NaN",
            ),
            (
                "LibraryProfiles",
                '[{"id": "movies", "enabled": Infinity}]',
                "non-finite JSON value is not allowed: Infinity",
            ),
            (
                "FinalLibraryPromotionRules",
                '[{"id": "rule-a", "id": "rule-b"}]',
                "duplicate JSON object key: id",
            ),
            (
                "FinalLibraryPromotionRules",
                '[{"id": "rule-a", "enabled": NaN}]',
                "non-finite JSON value is not allowed: NaN",
            ),
        ]
        for key, raw, expected in cases:
            with self.subTest(key=key, raw=raw):
                with self.assertRaises(ValidationError) as raised:
                    Config.model_validate({**_base_config(), key: raw})
                self.assertIn(expected, str(raised.exception))

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

    def test_validation_rejects_invalid_raw_library_route_overrides(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "editor": {
                        "RouteThresholdMode": "all",
                        "MovieRoute1080pTargetSizeGB": -1,
                        "Route1080pMaxVideoBitrateMbps": "many",
                        "Route4KMaxVideoBitrateMbps": 0,
                    }
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )
        joined = "\n".join(errors)

        self.assertIn("Library profile Movies override is invalid", joined)
        self.assertIn("RouteThresholdMode must be one of", joined)
        self.assertIn("MovieRoute1080pTargetSizeGB must be >= 1.", joined)
        self.assertIn("Route1080pMaxVideoBitrateMbps must be an integer.", joined)
        self.assertIn("Route4KMaxVideoBitrateMbps must be >= 1.", joined)

    def test_validation_rejects_unsupported_groups_global_keys_and_friendly_labels(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "display": {"RoutingProfile": "manual"},
                    "editor": {
                        "ProcessingStrategy": "manual",
                        "SourceMovies": r"C:\DisplayOnly",
                        "ConfigSchemaVersion": "config.v2",
                    },
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )
        joined = "\n".join(errors)

        self.assertIn("Library profile Movies override group is unsupported: display.", joined)
        self.assertIn("Library profile Movies override editor.ProcessingStrategy is not a supported library override key.", joined)
        self.assertIn("Library profile Movies override editor.SourceMovies is not a supported library override key.", joined)
        self.assertIn("Library profile Movies override editor.ConfigSchemaVersion is not a supported library override key.", joined)

    def test_validation_accepts_persisted_key_after_rejecting_friendly_label_alias(self) -> None:
        invalid_values = _base_config()
        invalid_values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {"editor": {"ProcessingStrategy": "manual"}},
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]
        errors, _warnings = validate_config_values(
            invalid_values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )
        self.assertIn(
            "Library profile Movies override editor.ProcessingStrategy is not a supported library override key.",
            errors,
        )

        valid_values = _base_config()
        valid_values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {"editor": {"RoutingProfile": "manual"}},
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]
        errors, _warnings = validate_config_values(
            valid_values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])

    def test_validation_rejects_invalid_library_option_value(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {"video": {"VideoPreset": "p9"}},
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertTrue(any("VideoPreset must be one of: p1, p2, p3, p4, p5, p6, p7." in error for error in errors))

    def test_validation_accepts_vobsub_library_overrides(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    "subtitles": {
                        "ConvertVobSubToSrt": True,
                        "DropVobSubAfterConversion": False,
                        "VobSubExtractLanguages": ["eng", "und"],
                        "VobSubOcrToolPath": r"Tools\SubtitleEdit\SubtitleEdit.exe",
                        "VobSubOcrTimeoutSeconds": 1200,
                        "TreatVobSubSignsSongsAsForced": True,
                    }
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])

    def test_validation_accepts_every_backend_library_override_key(self) -> None:
        values = Config.model_validate(_base_config()).model_dump(mode="python")
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {
                    group: {key: values[key] for key in keys}
                    for group, keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.items()
                },
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        errors, _warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertEqual(errors, [])

    def test_validation_rejects_duplicate_enabled_library_source_roots(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Incoming\Movies", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
            {"id": "alpha", "designation": "movie", "source_path": r"F:\Shared", "output_path": r"G:\Alpha"},
            {"id": "beta", "designation": "movie", "source_path": r"F:\Shared", "output_path": r"G:\Beta"},
        ]

        errors, warnings = validate_config_values(
            values,
            normalized_path_key=_path_key,
            path_within_root=_path_within_root,
        )

        self.assertTrue(any("Beta shares an enabled source root with Alpha" in error for error in errors))
        self.assertFalse(any("shares a source root" in warning for warning in warnings))

    def test_nested_enabled_source_roots_warn(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Media", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Media\TV", "output_path": r"D:\Processed"},
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

        self.assertEqual(errors, [])
        self.assertTrue(any("source root is inside" in warning for warning in warnings))

    def test_sibling_source_roots_do_not_warn(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Media\Movies", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Media\TV", "output_path": r"D:\Processed"},
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

        self.assertEqual(errors, [])
        self.assertFalse(any("source root is inside" in warning for warning in warnings))

    def test_duplicate_movies_id_keeps_first_occurrence(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "name": "First Movies", "designation": "movie", "source_path": r"C:\A", "output_path": r"D:\Processed"},
            {"id": "movies", "name": "Second Movies", "designation": "movie", "source_path": r"C:\B", "output_path": r"D:\Processed"},
        ]

        profiles = library_profiles_from_config(values)
        movies = [profile for profile in profiles if profile["id"] == "movies"]

        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0]["name"], "First Movies")

    def test_effective_profile_for_path_resolves_dotdot_and_case(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Media\Movies", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Media\TV", "output_path": r"D:\Processed"},
        ]

        profile = effective_library_profile_for_source_path(values, r"C:\Media\Other\..\tv\Show\ep.mkv")

        self.assertIsNotNone(profile)
        self.assertEqual(profile["id"], "tv")

    def test_effective_profile_for_path_honors_selection(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Media", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Media\TV", "output_path": r"D:\Processed"},
        ]
        path = r"C:\Media\TV\Show\ep.mkv"

        # Default: the deepest matching enabled source root wins.
        self.assertEqual(effective_library_profile_for_source_path(values, path)["id"], "tv")
        # Selection: a selected enabled profile whose root contains the path wins.
        self.assertEqual(
            effective_library_profile_for_source_path(values, path, selected_profile_id="movies")["id"],
            "movies",
        )

    def test_apply_resets_returns_error_on_malformed_profiles(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = "not-json-or-list{"

        updated, errors = apply_library_profile_resets(
            values,
            [{"library_id": "movies", "path_fields": ["output_path"]}],
        )

        self.assertTrue(any("LibraryProfiles is invalid" in error for error in errors))
        self.assertEqual(updated.get("LibraryProfiles"), "not-json-or-list{")

    def test_custom_library_name_colliding_with_builtin_warns(self) -> None:
        values = _base_config()
        values["LibraryProfiles"] = [
            {"id": "movies", "designation": "movie", "source_path": r"C:\Incoming\Movies", "output_path": r"D:\Processed"},
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
            {"name": "Show", "designation": "tv", "source_path": r"C:\Incoming\Shows", "output_path": r"D:\Processed"},
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

        self.assertTrue(any("maps to the reserved 'tv' library" in warning for warning in warnings))

    def test_explicit_inherited_output_path_follows_tracking(self) -> None:
        values = _base_config()  # Outsource = D:\Processed
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"E:\CustomOut",
                "default_tracking": {"inherited_fields": ["output_path"]},
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
        ]

        movies = next(p for p in library_profiles_from_config(values) if p["id"] == "movies")

        # Explicit inherited_fields wins: the typed output is treated as inherited from Outsource.
        self.assertEqual(movies["output_path"], r"D:\Processed")
        self.assertIn("output_path", movies["default_tracking"]["inherited_fields"])

    def test_base_config_errors_not_attributed_to_profile_override(self) -> None:
        values = _base_config()
        values["MovieRoute1080pTargetSizeGB"] = -1  # pre-existing invalid base value, untouched by the override
        values["LibraryProfiles"] = [
            {
                "id": "movies",
                "designation": "movie",
                "source_path": r"C:\Incoming\Movies",
                "output_path": r"D:\Processed",
                "overrides": {"audio": {"AudioMaxChannels": 6}},
            },
            {"id": "tv", "designation": "tv", "source_path": r"C:\Incoming\TV", "output_path": r"D:\Processed"},
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

        self.assertFalse(
            any("override is invalid" in error and "MovieRoute1080pTargetSizeGB" in error for error in errors),
            msg=f"base error mis-attributed to override: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
