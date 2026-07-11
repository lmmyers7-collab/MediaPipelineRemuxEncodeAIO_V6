from __future__ import annotations

import json
import hashlib
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
import sys
import tempfile
import unittest

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.publish.pending_manifest import pending_manifest_row
from mediapipeline.core.publish.pending_policy import pending_publish_rows


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
        self.assertIn("Legacy pending manifest", row["error"])

    def test_current_manifest_missing_required_proof_is_invalid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            manifest_path = root / "payload.mkv.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_push_manifest.v1",
                        "pipeline_version": "1.0",
                        "publish_transaction_id": "tx",
                        "manifest_state": "parked",
                        "local_file": str(payload),
                        "server_out": str(root / "server.mkv"),
                        "route": "encode",
                        "source_identity_v2": "",
                        "source_identity_v2_algorithm": "fixture-v2",
                        "source_path": str(root / "source.mkv"),
                        "output_size": payload.stat().st_size,
                        "sidecar_files": [],
                        "tx3g_srt_tracks": [],
                        "tx3g_srt_failures": [],
                        "bdpgs_srt_failures": [],
                        "vobsub_srt_failures": [],
                        "tx3g_embedded_srt_tracks": [],
                        "bdpgs_embedded_srt_tracks": [],
                        "vobsub_embedded_srt_tracks": [],
                    }
                ),
                encoding="utf-8",
            )

            row = pending_manifest_row(manifest_path)
            dto_row = pending_publish_rows([row])[0]

        self.assertEqual(row["state"], "invalid_contract")
        self.assertEqual(dto_row["diagnostic_status"], "invalid_manifest")
        self.assertFalse(dto_row["ready_to_drain"])
        self.assertIn("source_identity_v2", row["error"])

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
        self.assertEqual(dto_row["diagnostic_status"], "invalid_manifest")
        self.assertEqual(dto_row["drain_recommendation"], "do_not_drain")

    def test_current_manifest_reports_sha256_proof_and_in_progress_attempt_as_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = root / "payload.mkv"
            payload.write_bytes(b"payload")
            manifest_path = root / "payload.mkv.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_push_manifest.v1",
                        "pipeline_version": "1.0",
                        "publish_transaction_id": "tx",
                        "manifest_state": "parked",
                        "local_file": str(payload), "server_out": str(root / "server.mkv"), "route": "encode",
                        "source_identity_v2": "source-v2", "source_identity_v2_algorithm": "fixture-v2",
                        "source_path": str(root / "source.mkv"), "output_size": payload.stat().st_size,
                        "output_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(), "output_hash_algorithm": "SHA256",
                        "drain_attempt_id": "attempt-1", "drain_attempt_status": "in_progress",
                        "sidecar_files": [], "tx3g_srt_tracks": [], "tx3g_srt_failures": [], "bdpgs_srt_failures": [],
                        "vobsub_srt_failures": [], "tx3g_embedded_srt_tracks": [], "bdpgs_embedded_srt_tracks": [], "vobsub_embedded_srt_tracks": [],
                    }
                ), encoding="utf-8"
            )
            row = pending_publish_rows([pending_manifest_row(manifest_path)])[0]

        self.assertEqual(row["copy_proof_state"], "sha256_recorded")
        self.assertEqual(row["drain_attempt_status"], "in_progress")
        self.assertFalse(row["ready_to_drain"])
        self.assertIn("in progress", row["issue_summary"])

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
        self.assertEqual(dto_row["diagnostic_status"], "invalid_manifest")
        self.assertEqual(dto_row["drain_recommendation"], "do_not_drain")


if __name__ == "__main__":
    unittest.main()
