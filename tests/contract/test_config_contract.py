from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.config.load import config_to_flat_dict
from app.contracts.config import CONFIG_SCHEMA_VERSION, Config


REPO_ROOT = Path(__file__).resolve().parents[2]


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
        self.assertEqual(config.MovieRouteMaxVideoBitrateMbps, 35)
        self.assertEqual(config.TVRouteMaxVideoBitrateMbps, 18)
        self.assertEqual(config.ConsoleLogLevel, "DEBUG")
        self.assertEqual(data["OperatorLocalKey"], "preserve")

    def test_generated_schema_matches_config_contract(self) -> None:
        schema_path = REPO_ROOT / "schemas" / "config.v1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        generated = Config.model_json_schema()

        self.assertEqual(schema["properties"], generated["properties"])
        self.assertEqual(schema["x-config-schema-version"], CONFIG_SCHEMA_VERSION)

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
        ):
            with self.subTest(key=key, value=value), self.assertRaises(Exception):
                Config.model_validate({key: value})


if __name__ == "__main__":
    unittest.main()
