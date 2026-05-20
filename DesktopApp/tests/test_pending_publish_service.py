from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.service_pending_publish import PendingPublishServiceMixin


class DummyPendingPublishService(PendingPublishServiceMixin):
    pass


class PendingPublishServiceTests(unittest.TestCase):
    def _resolved(self, pending_root: Path) -> ResolvedPaths:
        return ResolvedPaths(
            app_root=pending_root,
            workspace_root=pending_root,
            pipeline_path=pending_root / "pipeline.ps1",
            config_path=pending_root / "config.psd1",
            audit_script_path=pending_root / "audit.ps1",
            rerun_script_path=pending_root / "rerun.ps1",
            powershell_host=None,
            pending_push_path=pending_root,
        )

    def test_missing_payload_is_reported_as_health_row(self) -> None:
        service = DummyPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            missing_payload = root / "missing-output.mkv"
            manifest = {
                "schema_version": "pending_push_manifest.v1",
                "manifest_state": "parked",
                "local_file": str(missing_payload),
                "server_out": str(root / "server-output.mkv"),
                "source_path": str(root / "source.mkv"),
                "output_size": 123,
            }
            (root / "missing-output.mkv.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = service.scan_pending_publish(self._resolved(root))

        self.assertEqual(result["missing_local_count"], 1)
        self.assertEqual(result["health_count"], 1)
        self.assertIn("missing", str(result["health_rows"][0]["error"]).casefold())
        self.assertEqual(result["rows"][0]["state"], "parked")

    def test_parked_manifest_reports_media_plus_sidecar_evidence(self) -> None:
        service = DummyPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = root / "payload.mkv"
            payload.write_bytes(b"verified-output")
            sidecar = root / "payload.eng.srt"
            sidecar.write_text("1\r\n00:00:01,000 --> 00:00:02,000\r\nhello\r\n", encoding="utf-8")
            server_out = root / "server-output.mkv"
            source = root / "source.mkv"
            manifest = {
                "schema_version": "pending_push_manifest.v1",
                "parked_at": "2026-05-19T04:00:00Z",
                "product_version": "v5-test",
                "pipeline_version": "1.0",
                "publish_transaction_id": "tx-parked",
                "manifest_state": "parked",
                "local_file": str(payload),
                "original_local_file": str(root / "scratch-output.mkv"),
                "parked_file": str(payload),
                "server_out": str(server_out),
                "route": "encode",
                "route_reason_code": "bitrate_over_threshold",
                "route_reason": "fixture",
                "source_identity": "sid-v1",
                "source_identity_v2": "sid-v2",
                "source_identity_v2_algorithm": "fixture-v2",
                "source_path": str(source),
                "source_size": 123456,
                "output_size": payload.stat().st_size,
                "publish_mode": "deferred",
                "sidecar_files": [
                    {
                        "kind": "tx3g_srt",
                        "local_file": str(sidecar),
                        "parked_file": str(sidecar),
                        "server_out": str(root / "server-output.eng.srt"),
                        "preserve_existing": True,
                    }
                ],
            }
            (root / "payload.mkv.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = service.scan_pending_publish(self._resolved(root))

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["health_count"], 0)
        self.assertEqual(result["missing_local_count"], 0)
        self.assertEqual(result["total_bytes"], len(b"verified-output"))
        row = result["rows"][0]
        self.assertEqual(row["schema_version"], "pending_push_manifest.v1")
        self.assertEqual(row["state"], "parked")
        self.assertEqual(row["publish_mode"], "deferred")
        self.assertEqual(row["route"], "encode")
        self.assertEqual(row["local_file"], str(payload))
        self.assertTrue(row["local_exists"])
        self.assertEqual(row["server_out"], str(server_out))
        self.assertEqual(row["source_path"], str(source))
        self.assertEqual(row["sidecar_count"], 1)
        self.assertEqual(row["missing_sidecar_count"], 0)
        self.assertEqual(row["sidecar_paths"], [str(sidecar)])
        self.assertEqual(row["error"], "")

    def test_current_schema_manifest_with_unknown_state_is_reported_invalid(self) -> None:
        service = DummyPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            manifest = {
                "schema_version": "pending_push_manifest.v1",
                "manifest_state": "mystery_state",
                "publish_transaction_id": "tx",
                "local_file": str(payload),
                "server_out": str(root / "server-output.mkv"),
                "source_path": str(root / "source.mkv"),
                "output_size": payload.stat().st_size,
            }
            (root / "payload.mkv.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = service.scan_pending_publish(self._resolved(root))

        self.assertEqual(result["health_count"], 1)
        self.assertEqual(result["rows"][0]["state"], "invalid_contract")
        self.assertIn("contract invalid", result["rows"][0]["error"])

    def test_legacy_manifest_without_schema_still_scans_tolerantly(self) -> None:
        service = DummyPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            manifest = {
                "manifest_state": "parked",
                "local_file": str(payload),
                "server_out": str(root / "server-output.mkv"),
                "source_path": str(root / "source.mkv"),
                "output_size": payload.stat().st_size,
            }
            (root / "payload.mkv.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = service.scan_pending_publish(self._resolved(root))

        self.assertEqual(result["health_count"], 0)
        self.assertEqual(result["rows"][0]["state"], "parked")
        self.assertEqual(result["rows"][0]["schema_version"], "legacy")

    def test_duplicate_manifest_targets_are_reported_as_health_rows(self) -> None:
        service = DummyPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            server_out = root / "server-output.mkv"
            for index in (1, 2):
                manifest = {
                    "manifest_state": "parked",
                    "local_file": str(payload),
                    "server_out": str(server_out),
                    "source_path": str(root / f"source-{index}.mkv"),
                    "output_size": payload.stat().st_size,
                }
                (root / f"payload-{index}.mkv.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = service.scan_pending_publish(self._resolved(root))

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["health_count"], 2)
        errors = "\n".join(str(row.get("error") or "") for row in result["health_rows"])
        self.assertIn("Duplicate pending publish local payload", errors)
        self.assertIn("Duplicate pending publish server destination", errors)


if __name__ == "__main__":
    unittest.main()
