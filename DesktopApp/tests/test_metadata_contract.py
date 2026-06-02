from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.library_profiles import LIBRARY_OVERRIDE_GROUP_BY_KEY, LIBRARY_OVERRIDE_KEYS_BY_GROUP
from app.config.metadata_parts.field_definitions import (
    CONFIG_FIELD_DEFINITIONS,
    METADATA_ADVANCED_VISIBILITY_VALUES,
    METADATA_LIBRARY_OVERRIDE_GROUP_BY_KEY,
    METADATA_MIGRATION_STATUS_VALUES,
    METADATA_RULE_TAXONOMY_VALUES,
    METADATA_SCOPE_VALUES,
    METADATA_STRICTNESS_VALUES,
)
from app.contracts.config import Config


CONTRACT_FIELDS = {
    "key",
    "label",
    "short_label",
    "help_text",
    "persisted_key",
    "section",
    "override_group",
    "scope",
    "value_type",
    "allowed_values",
    "min",
    "max",
    "step",
    "unit",
    "default_source",
    "default_value",
    "library_override_allowed",
    "rule_taxonomy",
    "strictness",
    "advanced_visibility",
    "unavailable_reason",
    "validation_owner",
    "runtime_consumer",
    "migration_status",
}

LABEL_ONLY_RENAMES = {
    "RoutingProfile": ("Processing Strategy", "editor"),
    "RouteThresholdMode": ("Enforcement Mode", "editor"),
    "SizeGuardMode": ("Output Size Check", "editor"),
    "EncodeTuningPreset": ("Encoder Quality Preset", "editor"),
    "EncodeLadder": ("Encode Target Mode", "editor"),
    "MaxEncodeGrowthPercent": ("Quality-encode size tolerance", "editor"),
    "CompatibilityEncodeGrowthPercent": ("Compatibility-encode size tolerance", "editor"),
    "EncodeThresholdGB": ("Movie target output size", "editor"),
    "TVEncodeThresholdGB": ("TV target output size", "editor"),
    "MovieRouteMaxVideoBitrateMbps": ("Movie max bitrate for direct copy", "editor"),
    "TVRouteMaxVideoBitrateMbps": ("TV max bitrate for direct copy", "editor"),
    "VideoPreset": ("Encoder Speed Preset", "video"),
    "ExtraVideoFlags": ("Advanced Encoder Flags", "video"),
    "RemuxSafeVideoCodecs": ("Direct Copy Video Codec Allowlist", "video"),
}

DISPLAY_SECTION_GROUP_EXPECTATIONS = {
    "RoutingProfile": ("Routing", "editor"),
    "RouteThresholdMode": ("Routing", "editor"),
    "SizeGuardMode": ("Size / Bitrate Guards", "editor"),
    "EncodeTuningPreset": ("Presets", "editor"),
    "EncodeLadder": ("Presets", "editor"),
    "VideoCodec": ("Video", "editor"),
    "OutputContainer": ("Container", "editor"),
    "EncodeThresholdGB": ("Size / Bitrate Guards", "editor"),
    "TVEncodeThresholdGB": ("Size / Bitrate Guards", "editor"),
    "MovieRouteMaxVideoBitrateMbps": ("Size / Bitrate Guards", "editor"),
    "TVRouteMaxVideoBitrateMbps": ("Size / Bitrate Guards", "editor"),
    "MaxEncodeGrowthPercent": ("Size / Bitrate Guards", "editor"),
    "CompatibilityEncodeGrowthPercent": ("Size / Bitrate Guards", "editor"),
    "VideoPreset": ("Video", "video"),
    "RemuxSafeVideoCodecs": ("Source / Compatibility", "video"),
    "ExtraVideoFlags": ("Advanced", "video"),
}

REPRESENTATIVE_DISPLAY_TAXONOMY = {
    "RoutingProfile": (
        "Strategy",
        "Routing",
        ("routing", "playback"),
        "hard",
        "Overall processing strategy. Controls the copy/remux-first policy before encoding is considered.",
    ),
    "RouteThresholdMode": (
        "Enforcement",
        "Routing",
        ("routing", "size", "bitrate"),
        "hard",
        "Used before processing to decide copy/remux versus encode. Selects which route gates are hard: target output size, max bitrate for direct copy, or either.",
    ),
    "SizeGuardMode": (
        "Size Check",
        "Size / Bitrate Guards",
        ("size", "verification"),
        "hard",
        "Checked after encode. Warns but does not block in warn-only mode. Blocks publish when configured to block if output exceeds the configured size budget.",
    ),
    "EncodeTuningPreset": (
        "Quality Preset",
        "Presets",
        ("quality", "output"),
        "soft",
        "Applies only when encoding is required. Chooses the encoder speed/compression tradeoff without changing copy/remux decisions by itself.",
    ),
    "EncodeThresholdGB": (
        "Movie Target",
        "Size / Bitrate Guards",
        ("size", "routing"),
        "soft",
        "GB target output size used as the movie size budget for route and size-policy checks; not the Mbps max bitrate for direct copy.",
    ),
    "MovieRouteMaxVideoBitrateMbps": (
        "Movie Copy Max",
        "Size / Bitrate Guards",
        ("bitrate", "routing"),
        "hard",
        "Maximum movie video bitrate in Mbps used before processing to decide whether direct copy/remux remains eligible. Above this cap, routing may choose encode.",
    ),
    "VideoPreset": (
        "Speed Preset",
        "Video",
        ("quality",),
        "soft",
        "Applies only when encoding is required. Selects the encoder speed/compression tradeoff.",
    ),
    "AudioPassthroughProfile": (
        "Passthrough",
        "Audio",
        ("playback", "compatibility"),
        "hard",
        "Audio copy policy. Controls which audio codecs may pass through instead of being transcoded.",
    ),
    "ConvertVobSubToSrt": (
        "VobSub OCR",
        "Subtitles",
        ("compatibility", "output"),
        "hard",
        "Subtitle processing option that OCRs VobSub bitmap subtitles to SRT using the configured OCR tool.",
    ),
}

REPRESENTATIVE_LIBRARY_FIELDS = {
    "RoutingProfile": ("editor", "string"),
    "OutputContainer": ("editor", "string"),
    "VideoCodec": ("editor", "string"),
    "VideoPreset": ("video", "string"),
    "AudioPassthroughProfile": ("audio", "string"),
    "ConvertTx3gToSrt": ("subtitles", "boolean"),
    "ConvertBdpgsToSrt": ("subtitles", "boolean"),
    "ConvertVobSubToSrt": ("subtitles", "boolean"),
    "SizeGuardMode": ("editor", "string"),
}

VOBSUB_LIBRARY_OVERRIDE_KEYS = {
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "VobSubExtractLanguages",
    "VobSubOcrToolPath",
    "VobSubOcrTimeoutSeconds",
    "TreatVobSubSignsSongsAsForced",
}


def _fields_by_key() -> dict[str, dict[str, object]]:
    return {str(field["key"]): field for field in CONFIG_FIELD_DEFINITIONS}


def _backend_library_override_keys() -> set[str]:
    return {key for keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.values() for key in keys}


class MetadataContractTests(unittest.TestCase):
    def test_metadata_contract_declares_expected_enum_values(self) -> None:
        self.assertLessEqual(
            {"global_only", "library_overridable", "source_derived", "computed_only", "advanced"},
            set(METADATA_SCOPE_VALUES),
        )
        self.assertLessEqual({"standard", "advanced"}, set(METADATA_ADVANCED_VISIBILITY_VALUES))
        self.assertLessEqual(
            {"routing", "compatibility", "quality", "size", "bitrate", "output", "playback", "verification", "publish", "advisory", "source_fact", "computed_evidence", "advanced"},
            set(METADATA_RULE_TAXONOMY_VALUES),
        )
        self.assertLessEqual(
            {"hard", "soft", "advisory", "computed", "read_only", "inherited", "explicit", "advanced"},
            set(METADATA_STRICTNESS_VALUES),
        )
        self.assertIn("stable_persisted_key", METADATA_MIGRATION_STATUS_VALUES)

    def test_every_metadata_record_has_contract_fields_without_renaming_persisted_keys(self) -> None:
        for field in CONFIG_FIELD_DEFINITIONS:
            with self.subTest(key=field["key"]):
                self.assertLessEqual(CONTRACT_FIELDS, set(field))
                self.assertEqual(field["persisted_key"], field["key"])
                self.assertIn(field["scope"], METADATA_SCOPE_VALUES)
                self.assertIn(field["advanced_visibility"], METADATA_ADVANCED_VISIBILITY_VALUES)
                self.assertIn(field["migration_status"], METADATA_MIGRATION_STATUS_VALUES)
                self.assertIn(field["strictness"], METADATA_STRICTNESS_VALUES)
                self.assertTrue(field["label"])
                self.assertTrue(field["short_label"])
                self.assertTrue(field["help_text"])
                self.assertTrue(field["rule_taxonomy"])
                self.assertLessEqual(set(field["rule_taxonomy"]), set(METADATA_RULE_TAXONOMY_VALUES))
                self.assertEqual(field["validation_owner"], "backend")
                self.assertIn(field["runtime_consumer"], {"unknown", "deferred"})

    def test_every_metadata_record_declares_known_value_type(self) -> None:
        for field in CONFIG_FIELD_DEFINITIONS:
            with self.subTest(key=field["key"], kind=field.get("kind")):
                self.assertNotEqual(field["value_type"], "unknown")

    def test_every_config_contract_field_has_backend_metadata(self) -> None:
        fields = _fields_by_key()

        self.assertEqual(sorted(set(Config.model_fields) - set(fields)), [])

    def test_phase3_label_only_renames_preserve_persisted_keys_and_override_groups(self) -> None:
        fields = _fields_by_key()

        for key, (label, override_group) in LABEL_ONLY_RENAMES.items():
            with self.subTest(key=key):
                field = fields[key]
                self.assertEqual(field["label"], label)
                self.assertEqual(field["persisted_key"], key)
                self.assertEqual(field["override_group"], override_group)
                self.assertTrue(field["library_override_allowed"])

    def test_display_sections_are_not_persisted_override_groups(self) -> None:
        fields = _fields_by_key()

        for key, (section, override_group) in DISPLAY_SECTION_GROUP_EXPECTATIONS.items():
            with self.subTest(key=key):
                field = fields[key]
                self.assertEqual(field["section"], section)
                self.assertEqual(field["override_group"], override_group)
                self.assertEqual(field["persisted_key"], key)

        routing_editor_keys = {"RoutingProfile", "RouteThresholdMode"}
        size_editor_keys = {"SizeGuardMode", "EncodeThresholdGB", "TVEncodeThresholdGB"}
        video_section_groups = {fields[key]["override_group"] for key in ("VideoCodec", "VideoPreset")}

        self.assertEqual({fields[key]["override_group"] for key in routing_editor_keys}, {"editor"})
        self.assertEqual({fields[key]["override_group"] for key in size_editor_keys}, {"editor"})
        self.assertEqual(video_section_groups, {"editor", "video"})

    def test_representative_phase3_display_taxonomy_is_backend_owned(self) -> None:
        fields = _fields_by_key()

        for key, (short_label, section, taxonomy, strictness, help_text) in REPRESENTATIVE_DISPLAY_TAXONOMY.items():
            with self.subTest(key=key):
                field = fields[key]
                self.assertEqual(field["short_label"], short_label)
                self.assertEqual(field["section"], section)
                self.assertEqual(field["rule_taxonomy"], taxonomy)
                self.assertEqual(field["strictness"], strictness)
                self.assertEqual(field["help_text"], help_text)

    def test_route_and_size_help_text_uses_precise_non_ambiguous_terms(self) -> None:
        fields = _fields_by_key()

        self.assertNotIn("advisory", str(fields["RouteThresholdMode"]["help_text"]).lower())
        self.assertNotIn("advisory", str(fields["SizeGuardMode"]["help_text"]).lower())
        self.assertNotIn("threshold", str(fields["RouteThresholdMode"]["help_text"]).lower())
        self.assertIn("Used before processing to decide copy/remux versus encode.", fields["RouteThresholdMode"]["help_text"])
        self.assertIn("Checked after encode.", fields["SizeGuardMode"]["help_text"])
        self.assertIn("Warns but does not block", fields["SizeGuardMode"]["help_text"])
        self.assertIn("Blocks publish when configured to block", fields["SizeGuardMode"]["help_text"])
        self.assertIn("GB target output size", fields["EncodeThresholdGB"]["help_text"])
        self.assertIn("not the Mbps max bitrate for direct copy", fields["EncodeThresholdGB"]["help_text"])
        self.assertIn("GB target output size", fields["TVEncodeThresholdGB"]["help_text"])
        self.assertIn("not the Mbps max bitrate for direct copy", fields["TVEncodeThresholdGB"]["help_text"])
        self.assertIn("Maximum movie video bitrate in Mbps", fields["MovieRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertIn("direct copy/remux remains eligible", fields["MovieRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertIn("Maximum TV video bitrate in Mbps", fields["TVRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertIn("direct copy/remux remains eligible", fields["TVRouteMaxVideoBitrateMbps"]["help_text"])
        self.assertIn("Applies only when encoding is required.", fields["EncodeTuningPreset"]["help_text"])
        self.assertIn("Applies only when encoding is required.", fields["VideoPreset"]["help_text"])

    def test_representative_library_metadata_has_override_groups_and_types(self) -> None:
        fields = _fields_by_key()
        for key, (override_group, value_type) in REPRESENTATIVE_LIBRARY_FIELDS.items():
            with self.subTest(key=key):
                field = fields[key]
                self.assertTrue(field["library_override_allowed"])
                self.assertEqual(field["scope"], "library_overridable")
                self.assertEqual(field["override_group"], override_group)
                self.assertEqual(field["value_type"], value_type)
                self.assertIsNotNone(field["default_source"])
                self.assertEqual(field["migration_status"], "stable_persisted_key")

    def test_every_backend_library_override_key_has_metadata_contract(self) -> None:
        fields = _fields_by_key()
        missing = sorted(_backend_library_override_keys() - set(fields))

        self.assertEqual(missing, [])
        self.assertEqual(METADATA_LIBRARY_OVERRIDE_GROUP_BY_KEY, LIBRARY_OVERRIDE_GROUP_BY_KEY)
        for key, expected_group in LIBRARY_OVERRIDE_GROUP_BY_KEY.items():
            with self.subTest(key=key):
                field = fields[key]
                self.assertTrue(field["library_override_allowed"])
                self.assertEqual(field["scope"], "library_overridable")
                self.assertEqual(field["override_group"], expected_group)

    def test_every_library_overridable_metadata_item_has_backend_override_group(self) -> None:
        for field in CONFIG_FIELD_DEFINITIONS:
            if not field["library_override_allowed"]:
                continue
            key = str(field["key"])
            with self.subTest(key=key):
                self.assertEqual(field["scope"], "library_overridable")
                self.assertIn(field["override_group"], LIBRARY_OVERRIDE_KEYS_BY_GROUP)
                self.assertIn(key, LIBRARY_OVERRIDE_KEYS_BY_GROUP[str(field["override_group"])])

    def test_library_overridable_fields_have_display_metadata_without_runtime_evidence_shape(self) -> None:
        for key in sorted(_backend_library_override_keys()):
            field = _fields_by_key()[key]
            with self.subTest(key=key):
                self.assertEqual(field["persisted_key"], key)
                self.assertTrue(str(field["label"]).strip())
                self.assertTrue(str(field["short_label"]).strip())
                self.assertTrue(str(field["help_text"]).strip())
                self.assertIsNotNone(field["override_group"])
                self.assertNotIn("runtime_effective_settings", field)
                self.assertNotIn("library_effective_settings", field)

    def test_vobsub_metadata_contract_is_explicitly_library_overridable(self) -> None:
        fields = _fields_by_key()

        self.assertLessEqual(VOBSUB_LIBRARY_OVERRIDE_KEYS, set(fields))
        for key in sorted(VOBSUB_LIBRARY_OVERRIDE_KEYS):
            with self.subTest(key=key):
                field = fields[key]
                self.assertEqual(field["persisted_key"], key)
                self.assertEqual(field["scope"], "library_overridable")
                self.assertEqual(field["override_group"], "subtitles")
                self.assertTrue(field["library_override_allowed"])

    def test_known_allowed_values_and_numeric_limits_are_represented(self) -> None:
        fields = _fields_by_key()

        self.assertIn("plex_direct_stream", fields["RoutingProfile"]["allowed_values"])
        self.assertIn("mkv", fields["OutputContainer"]["allowed_values"])
        self.assertEqual(fields["EncodeThresholdGB"]["min"], 1)
        self.assertEqual(fields["EncodeThresholdGB"]["unit"], "GB")
        self.assertEqual(fields["MixPriorityPhase"]["default_value"], False)
        self.assertEqual(fields["QueueOrderingStrategy"]["allowed_values"], (
            "Standard",
            "FreshestFirst",
            "ShowComplete",
            "RoundRobin",
            "DeadlineAware",
            "SmallFirst",
            "LargeFirst",
            "ManualOrder",
        ))
        self.assertEqual(fields["ShowOverrides"]["value_type"], "json")
        self.assertEqual(fields["ShowOverrides"]["default_value"], {})
        self.assertEqual(fields["VobSubOcrTimeoutSeconds"]["min"], 60)
        self.assertEqual(fields["VobSubOcrTimeoutSeconds"]["max"], 14400)
        self.assertEqual(fields["VobSubOcrTimeoutSeconds"]["unit"], "seconds")


if __name__ == "__main__":
    unittest.main()
