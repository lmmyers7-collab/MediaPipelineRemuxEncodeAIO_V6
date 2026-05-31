from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "DesktopApp"))

from app.config.metadata_parts.field_definitions import CONFIG_FIELD_DEFINITIONS
from app.config.load import config_to_flat_dict
from app.config.library_profiles import LIBRARY_OVERRIDE_KEYS_BY_GROUP as BACKEND_LIBRARY_OVERRIDE_KEYS_BY_GROUP
from app.contracts.config import (
    CONFIG_SCHEMA_VERSION,
    DESKTOP_SCHEMA_CONFIG_KEYS,
    FINAL_LIBRARY_PROMOTION_RULE_KEYS,
    LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP,
    LIBRARY_PROFILE_TOP_LEVEL_KEYS,
    NETWORK_CONFIG_KEYS,
    PS_CONFIG_KEY_ORDER,
    Config,
)


PS_SCHEMA_ONLY_KEYS = {
    "MixPriorityPhase",
    "QueueOrderingStrategy",
    "ShowOverrides",
}
VOBSUB_CONFIG_KEYS = {
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "VobSubExtractLanguages",
    "VobSubOcrToolPath",
    "VobSubOcrTimeoutSeconds",
    "TreatVobSubSignsSongsAsForced",
}


class ConfigContractTests(unittest.TestCase):
    def test_representative_config_payload_validates_and_preserves_unknown_keys(self) -> None:
        config = Config.model_validate(
            {
                "ConfigSchemaVersion": CONFIG_SCHEMA_VERSION,
                "SourceMovies": r"C:\Movies",
                "SourceTV": r"C:\TV",
                "Outsource": r"D:\Out",
                "LocalBase": r"E:\Scratch",
                "RoutingProfile": "PLEX_DIRECT_STREAM",
                "ConsoleLogLevel": "debug",
                "OperatorLocalKey": "preserve",
            }
        )
        data = config_to_flat_dict(config)

        self.assertEqual(config.RoutingProfile, "plex_direct_stream")
        self.assertEqual(config.RouteThresholdMode, "compatibility_advisory")
        self.assertEqual(config.MovieRouteMaxVideoBitrateMbps, 35)
        self.assertEqual(config.TVRouteMaxVideoBitrateMbps, 18)
        self.assertEqual(config.ConsoleLogLevel, "DEBUG")
        self.assertEqual(data["OperatorLocalKey"], "preserve")

    def test_friendly_display_labels_are_not_canonical_config_fields(self) -> None:
        friendly_aliases = {
            "ProcessingStrategy",
            "EnforcementMode",
            "OutputSizeCheck",
            "EncoderQualityPreset",
            "EncodeTargetMode",
            "EncoderSpeedPreset",
        }
        schema = Config.model_json_schema()

        self.assertLessEqual({"RoutingProfile", "RouteThresholdMode", "SizeGuardMode", "VideoPreset"}, set(Config.model_fields))
        self.assertEqual(friendly_aliases & set(Config.model_fields), set())
        self.assertEqual(friendly_aliases & set(schema["properties"]), set())

    def test_library_profiles_contract_preserves_phase4_inheritance_shape(self) -> None:
        config = Config.model_validate(
            {
                "ConfigSchemaVersion": CONFIG_SCHEMA_VERSION,
                "SourceMovies": r"C:\Movies",
                "SourceTV": r"C:\TV",
                "Outsource": r"D:\Out",
                "LocalBase": r"E:\Scratch",
                "LibraryProfiles": [
                    {
                        "id": "concerts",
                        "name": "Concerts",
                        "enabled": True,
                        "designation": "auto",
                        "source_path": r"C:\Concerts",
                        "output_path": "",
                        "promotion_enabled": True,
                        "promotion_destination": r"F:\Concerts",
                        "default_tracking": {
                            "schema_version": "library_profile_default_tracking.v1",
                            "inherited_fields": ["output_path"],
                            "field_default_keys": {"output_path": "Outsource"},
                            "future_field": {"preserve": True},
                        },
                        "overrides": {
                            "editor": {"RoutingProfile": "manual"},
                            "video": {"VideoPreset": "p5"},
                            "subtitles": {"ConvertVobSubToSrt": True},
                            "audio": {"AudioMaxChannels": 2},
                        },
                    }
                ],
            }
        )
        data = config_to_flat_dict(config)
        profile = data["LibraryProfiles"][0]

        self.assertEqual(profile["id"], "concerts")
        self.assertEqual(profile["default_tracking"]["inherited_fields"], ["output_path"])
        self.assertEqual(profile["default_tracking"]["field_default_keys"]["output_path"], "Outsource")
        self.assertEqual(profile["default_tracking"]["future_field"], {"preserve": True})
        self.assertEqual(tuple(profile["overrides"]), ("editor", "video", "subtitles", "audio"))
        self.assertEqual(profile["overrides"]["subtitles"]["ConvertVobSubToSrt"], True)

    def test_contract_accepts_legacy_profile_overrides_and_promotion_rule_shape(self) -> None:
        config = Config.model_validate(
            {
                "ConfigSchemaVersion": CONFIG_SCHEMA_VERSION,
                "SourceMovies": r"C:\Movies",
                "SourceTV": r"C:\TV",
                "Outsource": r"D:\Out",
                "LocalBase": r"E:\Scratch",
                "LibraryProfiles": [
                    {
                        "id": "archive",
                        "name": "Archive",
                        "enabled": True,
                        "designation": "mixed",
                        "source_path": r"C:\Archive",
                        "output_path": r"D:\Archive",
                        "editor_overrides": {"RoutingProfile": "manual"},
                        "media_overrides": {
                            "VideoPreset": "p5",
                            "ConvertVobSubToSrt": True,
                            "AudioMaxChannels": 2,
                        },
                        "future_profile_metadata": {"preserve": True},
                    }
                ],
                "FinalLibraryPromotionRules": [
                    {
                        "id": "archive",
                        "label": "Archive",
                        "enabled": True,
                        "source_root": r"C:\Archive",
                        "output_root": r"D:\Archive",
                        "destination_root": r"F:\Archive",
                        "library_id": "archive",
                        "designation": "auto",
                    }
                ],
            }
        )
        data = config_to_flat_dict(config)
        profile = data["LibraryProfiles"][0]
        rule = data["FinalLibraryPromotionRules"][0]

        self.assertEqual(profile["designation"], "mixed")
        self.assertEqual(profile["editor_overrides"]["RoutingProfile"], "manual")
        self.assertTrue(profile["media_overrides"]["ConvertVobSubToSrt"])
        self.assertEqual(profile["future_profile_metadata"], {"preserve": True})
        self.assertLessEqual(set(FINAL_LIBRARY_PROMOTION_RULE_KEYS), set(rule))

    def test_generated_contract_schema_declares_profile_override_shapes(self) -> None:
        self.assertEqual(LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP, BACKEND_LIBRARY_OVERRIDE_KEYS_BY_GROUP)
        schema = Config.model_json_schema()
        library_profiles = schema["properties"]["LibraryProfiles"]
        profile_schema = library_profiles["items"]
        profile_properties = profile_schema["properties"]

        self.assertTrue(profile_schema["additionalProperties"])
        self.assertLessEqual(set(LIBRARY_PROFILE_TOP_LEVEL_KEYS), set(profile_properties))
        self.assertEqual(profile_properties["overrides"]["additionalProperties"], False)
        for group, keys in LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP.items():
            with self.subTest(group=group):
                group_schema = profile_properties["overrides"]["properties"][group]
                self.assertEqual(group_schema["additionalProperties"], False)
                self.assertEqual(set(group_schema["properties"]), set(keys))
        self.assertIn("ConvertVobSubToSrt", profile_properties["overrides"]["properties"]["subtitles"]["properties"])
        self.assertNotIn("ProcessingStrategy", profile_properties["overrides"]["properties"]["editor"]["properties"])

        self.assertEqual(set(profile_properties["editor_overrides"]["properties"]), set(LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP["editor"]))
        media_keys = set().union(
            set(LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP["video"]),
            set(LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP["subtitles"]),
            set(LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP["audio"]),
        )
        self.assertEqual(set(profile_properties["media_overrides"]["properties"]), media_keys)

    def test_pipeline_schema_declares_profile_and_promotion_shapes_without_label_aliases(self) -> None:
        schema_path = REPO_ROOT / "Pipeline" / "Schemas" / "media_pipeline_config.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        profile_schema = schema["properties"]["LibraryProfiles"]["items"]
        profile_properties = profile_schema["properties"]
        promotion_rule = schema["properties"]["FinalLibraryPromotionRules"]["items"]

        self.assertTrue(profile_schema["additionalProperties"])
        self.assertLessEqual(set(LIBRARY_PROFILE_TOP_LEVEL_KEYS), set(profile_properties))
        self.assertEqual(profile_properties["overrides"]["additionalProperties"], False)
        for group, keys in LIBRARY_PROFILE_OVERRIDE_KEYS_BY_GROUP.items():
            with self.subTest(group=group):
                group_schema = profile_properties["overrides"]["properties"][group]
                self.assertEqual(group_schema["additionalProperties"], False)
                self.assertEqual(set(group_schema["properties"]), set(keys))
        self.assertNotIn("ProcessingStrategy", profile_properties["overrides"]["properties"]["editor"]["properties"])
        self.assertLessEqual(set(FINAL_LIBRARY_PROMOTION_RULE_KEYS), set(promotion_rule["properties"]))

    def test_generated_schema_matches_config_contract(self) -> None:
        schema_path = REPO_ROOT / "schemas" / "config.v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        generated = Config.model_json_schema()

        self.assertEqual(schema["properties"], generated["properties"])
        self.assertEqual(schema["x-config-schema-version"], CONFIG_SCHEMA_VERSION)

    def test_pipeline_json_schema_covers_non_network_config_surfaces(self) -> None:
        schema_path = REPO_ROOT / "Pipeline" / "Schemas" / "media_pipeline_config.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_keys = set(schema["properties"])
        network_keys = set(NETWORK_CONFIG_KEYS)
        backend_metadata_keys = {str(field["key"]) for field in CONFIG_FIELD_DEFINITIONS}

        self.assertEqual(schema_keys, set(PS_CONFIG_KEY_ORDER))
        self.assertEqual(schema_keys & network_keys, set())
        self.assertEqual(sorted((set(DESKTOP_SCHEMA_CONFIG_KEYS) - network_keys) - schema_keys), [])
        self.assertEqual(sorted((backend_metadata_keys - network_keys) - schema_keys), [])
        self.assertEqual(sorted(schema_keys - backend_metadata_keys), sorted(PS_SCHEMA_ONLY_KEYS))

    def test_pipeline_json_schema_explicitly_covers_vobsub_keys(self) -> None:
        schema_path = REPO_ROOT / "Pipeline" / "Schemas" / "media_pipeline_config.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        properties = schema["properties"]

        self.assertLessEqual(VOBSUB_CONFIG_KEYS, set(properties))
        self.assertEqual(properties["ConvertVobSubToSrt"]["type"], "boolean")
        self.assertEqual(properties["DropVobSubAfterConversion"]["type"], "boolean")
        self.assertEqual(properties["VobSubExtractLanguages"]["type"], "array")
        self.assertEqual(properties["VobSubExtractLanguages"]["items"]["type"], "string")
        self.assertEqual(properties["VobSubOcrToolPath"]["type"], "string")
        self.assertEqual(properties["VobSubOcrTimeoutSeconds"]["type"], "integer")
        self.assertEqual(properties["VobSubOcrTimeoutSeconds"]["minimum"], 60)
        self.assertEqual(properties["VobSubOcrTimeoutSeconds"]["maximum"], 14400)
        self.assertEqual(properties["TreatVobSubSignsSongsAsForced"]["type"], "boolean")
        self.assertIn("DropVobSubAfterConversion", json.dumps(schema.get("allOf", [])))
        self.assertIn("ConvertVobSubToSrt", json.dumps(schema.get("allOf", [])))

    def test_invalid_config_payload_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            Config.model_validate(
                {
                    "SourceMovies": "",
                    "SourceTV": r"C:\TV",
                    "Outsource": r"D:\Out",
                    "LocalBase": r"E:\Scratch",
                }
            )

        for key, value in (
            ("MovieRouteMaxVideoBitrateMbps", 0),
            ("TVRouteMaxVideoBitrateMbps", -1),
            ("MovieRouteMaxVideoBitrateMbps", 501),
            ("RouteThresholdMode", "unknown"),
            ("VideoCodec", "vp9"),
            ("VideoPreset", "p9"),
            ("VideoQuality", 0),
            ("VideoQuality", 52),
            ("SubtitleExtractTimeoutSeconds", 29),
            ("BdpgsOcrTimeoutSeconds", 59),
            ("OutputSizeMultiplier", 2.1),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(Exception):
                Config.model_validate({key: value})


if __name__ == "__main__":
    unittest.main()
