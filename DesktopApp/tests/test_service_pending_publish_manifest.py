from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.publish.pending_manifest import pending_manifest_row


class ServicePendingPublishManifestTests(unittest.TestCase):
    def test_unreadable_manifest_returns_health_row_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "bad.manifest.json"
            manifest_path.write_text("{", encoding="utf-8")

            row = pending_manifest_row(manifest_path)

        self.assertEqual(row["state"], "unreadable")
        self.assertIn("manifest_path", row)
        self.assertEqual(row["output_size"], 0)
        self.assertTrue(row["error"])

    def test_legacy_manifest_uses_payload_size_fallback_and_sidecar_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            missing_sidecar = root / "payload.mkv.pipeline.json"
            manifest_path = root / "payload.mkv.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_state": "parked",
                        "local_file": str(payload),
                        "server_out": str(root / "server.mkv"),
                        "source_path": str(root / "source.mkv"),
                        "sidecar_files": [{"local_file": str(missing_sidecar)}],
                    }
                ),
                encoding="utf-8",
            )

            row = pending_manifest_row(manifest_path)

        self.assertEqual(row["schema_version"], "legacy")
        self.assertEqual(row["state"], "parked")
        self.assertEqual(row["output_size"], len("payload"))
        self.assertEqual(row["missing_sidecar_count"], 1)
        self.assertIn("sidecar", row["error"])


if __name__ == "__main__":
    unittest.main()
