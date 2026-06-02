from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.publish.pending_manifest import pending_manifest_row
from app.publish.pending_policy import pending_publish_rows


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

    def test_manifest_missing_destination_is_not_ready_for_drain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            manifest_path = root / "payload.mkv.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_state": "parked",
                        "local_file": str(payload),
                        "source_path": str(root / "source.mkv"),
                        "output_size": payload.stat().st_size,
                    }
                ),
                encoding="utf-8",
            )

            row = pending_manifest_row(manifest_path)
            dto_row = pending_publish_rows([row])[0]

        self.assertIn("server_out destination is missing", row["error"])
        self.assertFalse(dto_row["ready_to_drain"])
        self.assertEqual(dto_row["diagnostic_status"], "row_error")
        self.assertEqual(dto_row["drain_recommendation"], "do_not_drain")

    def test_legacy_manifest_unknown_state_is_not_ready_for_drain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            manifest_path = root / "payload.mkv.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "manifest_state": "mystery_state",
                        "local_file": str(payload),
                        "server_out": str(root / "server.mkv"),
                        "source_path": str(root / "source.mkv"),
                        "output_size": payload.stat().st_size,
                    }
                ),
                encoding="utf-8",
            )

            row = pending_manifest_row(manifest_path)
            dto_row = pending_publish_rows([row])[0]

        self.assertIn("Manifest state 'mystery_state' is not recognized", row["error"])
        self.assertFalse(dto_row["ready_to_drain"])
        self.assertEqual(dto_row["diagnostic_status"], "row_error")
        self.assertEqual(dto_row["drain_recommendation"], "do_not_drain")


if __name__ == "__main__":
    unittest.main()
