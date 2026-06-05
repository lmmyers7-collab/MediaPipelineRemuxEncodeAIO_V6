from __future__ import annotations

import unittest

from pydantic import ValidationError

from mediapipeline.contracts.config import Config
from mediapipeline.contracts.runtime_evidence import (
    LIBRARY_EFFECTIVE_SETTINGS_REF,
    RUNTIME_EFFECTIVE_SETTINGS_SCHEMA,
    RUNTIME_EVIDENCE_LAYER_ORDER,
    build_runtime_effective_settings,
    runtime_effective_settings_payload,
    runtime_evidence_layer,
)


class RuntimeEvidenceContractTests(unittest.TestCase):
    def test_default_shape_is_diagnostic_only_and_keeps_library_reference(self) -> None:
        payload = runtime_effective_settings_payload()

        self.assertEqual(payload["schema"], RUNTIME_EFFECTIVE_SETTINGS_SCHEMA)
        self.assertEqual(payload["scope"], "job")
        self.assertEqual(payload["library_effective_settings_ref"], LIBRARY_EFFECTIVE_SETTINGS_REF)
        self.assertEqual([layer["name"] for layer in payload["layers"]], list(RUNTIME_EVIDENCE_LAYER_ORDER))
        self.assertEqual([layer["keys"] for layer in payload["layers"]], [{}, {}, {}, {}, {}, {}])
        self.assertTrue(all(layer["known"] for layer in payload["layers"]))
        self.assertFalse(payload["layers"][-1]["saved_config"])
        self.assertEqual(payload["layers"][-1]["source"], "ffprobe/probe")
        self.assertEqual(payload["effective_values"], {})
        self.assertEqual(payload["unsupported_keys"], [])
        self.assertEqual(payload["ignored_keys"], [])
        self.assertEqual(payload["warnings"], [])
        self.assertNotIn("library_effective_settings", payload)

    def test_layer_merge_records_final_value_and_provenance_without_decisions(self) -> None:
        evidence = build_runtime_effective_settings(
            layers=[
                runtime_evidence_layer("global", keys={"VideoCodec": "H264", "AudioMaxChannels": 8}),
                runtime_evidence_layer("library", keys={"VideoCodec": "HEVC"}),
                runtime_evidence_layer("show", keys={}),
                runtime_evidence_layer("folder", keys={"VideoCodec": "H264"}),
                runtime_evidence_layer("file", keys={"AudioMaxChannels": 2}),
                runtime_evidence_layer("source", keys={"source_video_codec": "hevc"}),
            ]
        )
        values = evidence.model_dump(mode="json")["effective_values"]

        self.assertEqual(
            values["VideoCodec"],
            {"value": "H264", "source_layer": "folder", "overrode": ["global", "library"]},
        )
        self.assertEqual(
            values["AudioMaxChannels"],
            {"value": 2, "source_layer": "file", "overrode": ["global"]},
        )
        self.assertEqual(
            values["source_video_codec"],
            {"value": "hevc", "source_layer": "source", "overrode": []},
        )
        self.assertFalse(evidence.layers[-1].saved_config)

    def test_unsupported_ignored_and_warning_lists_are_explicit(self) -> None:
        payload = runtime_effective_settings_payload(
            unsupported_keys=["UnknownFolderKey"],
            ignored_keys=["OutputContainer"],
            warnings=["Folder OutputContainer evidence is diagnostic-only in Phase 6."],
        )

        self.assertEqual(payload["unsupported_keys"], ["UnknownFolderKey"])
        self.assertEqual(payload["ignored_keys"], ["OutputContainer"])
        self.assertEqual(payload["warnings"], ["Folder OutputContainer evidence is diagnostic-only in Phase 6."])

    def test_runtime_effective_settings_is_not_a_saved_config_field(self) -> None:
        self.assertNotIn("runtime_effective_settings", Config.model_fields)
        self.assertNotIn("library_effective_settings", Config.model_fields)

    def test_contract_rejects_unknown_runtime_layer_names(self) -> None:
        with self.assertRaises(ValidationError):
            build_runtime_effective_settings(
                layers=[
                    {
                        "name": "promotion",
                        "source": "FinalLibraryPromotionRules",
                        "keys": {},
                        "known": True,
                        "saved_config": False,
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()
