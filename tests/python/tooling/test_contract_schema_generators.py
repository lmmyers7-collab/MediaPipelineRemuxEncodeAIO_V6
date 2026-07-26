from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mediapipeline.contracts.config import NETWORK_CONFIG_KEYS
from mediapipeline.tools.dev import generate_config_schema, generate_run_monitor_schema


class ContractSchemaGeneratorTests(unittest.TestCase):
    def test_config_pipeline_mirror_has_only_documented_consumer_differences(self) -> None:
        outputs = generate_config_schema._expected_outputs()
        canonical = json.loads(outputs[generate_config_schema.CANONICAL_SCHEMA_PATH])
        pipeline = json.loads(outputs[generate_config_schema.PIPELINE_SCHEMA_PATH])

        canonical_id = canonical.pop("$id")
        pipeline_id = pipeline.pop("$id")
        for key in NETWORK_CONFIG_KEYS:
            canonical["properties"].pop(key)
            if "required" in canonical:
                canonical["required"] = [name for name in canonical["required"] if name != key]

        self.assertNotEqual(canonical_id, pipeline_id)
        self.assertEqual(canonical, pipeline)
        self.assertEqual(pipeline["properties"]["DynamicHdrPolicy"]["default"], "preserve_or_review")

    def test_run_monitor_mirrors_differ_only_by_consumer_id(self) -> None:
        outputs = generate_run_monitor_schema._expected_outputs()
        canonical = json.loads(outputs[generate_run_monitor_schema.CANONICAL_SCHEMA_PATH])
        pipeline = json.loads(outputs[generate_run_monitor_schema.PIPELINE_SCHEMA_PATH])

        canonical_id = canonical.pop("$id")
        pipeline_id = pipeline.pop("$id")

        self.assertNotEqual(canonical_id, pipeline_id)
        self.assertEqual(canonical, pipeline)

    def test_check_mode_rejects_drift_in_each_generated_mirror(self) -> None:
        for generator in (generate_config_schema, generate_run_monitor_schema):
            with self.subTest(generator=generator.__name__), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                canonical = root / "contracts.schema.json"
                pipeline = root / "pipeline.schema.json"
                with (
                    mock.patch.object(generator, "REPO_ROOT", root),
                    mock.patch.object(generator, "CANONICAL_SCHEMA_PATH", canonical),
                    mock.patch.object(generator, "PIPELINE_SCHEMA_PATH", pipeline),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(generator.main([]), 0)
                    self.assertEqual(generator.main(["--check"]), 0)
                    pipeline.write_text("{}\n", encoding="utf-8")
                    self.assertEqual(generator.main(["--check"]), 1)


if __name__ == "__main__":
    unittest.main()
