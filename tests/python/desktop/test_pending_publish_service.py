from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.publish.pending_service import PendingPublishServiceMixin
from mediapipeline.core.publish.pending_policy import pending_publish_preview_fields, pending_publish_rows


class DummyPendingPublishService(PendingPublishServiceMixin):
    pass


class CountingPendingPublishService(PendingPublishServiceMixin):
    def __init__(self) -> None:
        self.manifest_rows_read: list[Path] = []

    def _pending_manifest_row(self, manifest_path: Path) -> dict[str, object]:
        self.manifest_rows_read.append(manifest_path)
        return {
            "schema_version": "pending_push_manifest.v1",
            "manifest_path": str(manifest_path),
            "local_file": "",
            "sidecar_paths": [],
            "server_out": str(manifest_path.with_suffix(".mkv")),
            "route": "remux",
            "state": "parked",
            "error": "",
            "output_size": 1,
        }


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

    def _current_manifest(
        self,
        *,
        root: Path,
        payload: Path,
        server_out: Path,
        source: Path,
        state: str = "parked",
        **overrides: object,
    ) -> dict[str, object]:
        manifest: dict[str, object] = {
            "schema_version": "pending_push_manifest.v1",
            "parked_at": "2026-05-19T04:00:00Z",
            "product_version": "v5-test",
            "pipeline_version": "1.0",
            "publish_transaction_id": "tx-parked",
            "manifest_state": state,
            "local_file": str(payload),
            "original_local_file": str(root / "Encoded" / payload.name),
            "parked_file": str(payload),
            "server_out": str(server_out),
            "route": "encode",
            "route_reason_code": "bitrate_over_threshold",
            "route_reason": "fixture",
            "media_type": "movie",
            "source_identity": "sid-v1",
            "source_identity_v2": "sid-v2",
            "source_identity_v2_algorithm": "fixture-v2",
            "source_path": str(source),
            "source_size": 123456,
            "source_mtime_utc": "2026-05-19T03:00:00Z",
            "output_size": payload.stat().st_size if payload.exists() else 123,
            "publish_mode": "deferred",
            "sidecar_files": [],
            "tx3g_srt_tracks": [],
            "tx3g_srt_failures": [],
            "bdpgs_srt_failures": [],
            "vobsub_srt_failures": [],
            "tx3g_embedded_srt_tracks": [],
            "bdpgs_embedded_srt_tracks": [],
            "vobsub_embedded_srt_tracks": [],
            "tx3g_srt_conversion_enabled": False,
            "tx3g_external_srt_sidecars_enabled": False,
            "drop_tx3g_after_conversion": False,
            "bdpgs_srt_conversion_enabled": False,
            "drop_bdpgs_after_conversion": False,
            "vobsub_srt_conversion_enabled": False,
            "drop_vobsub_after_conversion": False,
        }
        manifest.update(overrides)
        return manifest

    def test_missing_payload_is_reported_as_health_row(self) -> None:
        service = DummyPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            missing_payload = root / "missing-output.mkv"
            manifest = self._current_manifest(
                root=root,
                payload=missing_payload,
                server_out=root / "server-output.mkv",
                source=root / "source.mkv",
            )
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
            manifest = self._current_manifest(
                root=root,
                payload=payload,
                server_out=server_out,
                source=source,
                sidecar_files=[
                    {
                        "kind": "tx3g_srt",
                        "local_file": str(sidecar),
                        "parked_file": str(sidecar),
                        "server_out": str(root / "server-output.eng.srt"),
                        "preserve_existing": True,
                    }
                ],
            )
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
            manifest = self._current_manifest(
                root=root,
                payload=payload,
                server_out=root / "server-output.mkv",
                source=root / "source.mkv",
                state="mystery_state",
            )
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

        self.assertEqual(result["health_count"], 1)
        self.assertEqual(result["rows"][0]["state"], "parked")
        self.assertEqual(result["rows"][0]["schema_version"], "legacy")
        dto_row = pending_publish_rows([result["rows"][0]])[0]
        self.assertFalse(dto_row["ready_to_drain"])
        self.assertEqual(dto_row["diagnostic_status"], "invalid_manifest")
        self.assertIn("Legacy pending manifest", result["rows"][0]["error"])

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

    def test_large_pending_publish_scan_can_cap_manifest_reads_for_normal_diagnostics(self) -> None:
        service = CountingPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            for index in range(1000):
                (root / f"movie-{index:04d}.mkv.manifest.json").write_text("{}", encoding="utf-8")

            bounded = service.scan_pending_publish(
                self._resolved(root),
                manifest_limit=25,
                include_orphan_rows=False,
            )
            bounded_read_count = len(service.manifest_rows_read)
            service.manifest_rows_read.clear()
            deep = service.scan_pending_publish(self._resolved(root), manifest_limit=None)

        self.assertEqual(bounded["count"], 1000)
        self.assertEqual(bounded["manifest_rows_read"], 25)
        self.assertEqual(bounded_read_count, 25)
        self.assertTrue(bounded["scan_limited"])
        self.assertTrue(bounded["rows_truncated"])
        self.assertIn("capped", " ".join(bounded["warnings"]))
        self.assertEqual(bounded["file_inventory"]["status"], "sampled")
        self.assertFalse(bounded["file_inventory"]["references_complete"])
        self.assertEqual(deep["manifest_rows_read"], 1000)
        self.assertFalse(deep["scan_limited"])

    def test_retry_exhausted_manifest_is_dead_letter_review_and_not_drain_ready(self) -> None:
        service = DummyPendingPublishService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = root / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            manifest = self._current_manifest(
                root=root,
                payload=payload,
                server_out=root / "server-output.mkv",
                source=root / "source.mkv",
                retry_count=3,
            )
            (root / "payload.mkv.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = service.scan_pending_publish(self._resolved(root))
            dto_row = pending_publish_rows([result["rows"][0]])[0]
            preview = pending_publish_preview_fields(result)

        self.assertEqual(result["rows"][0]["retry_count"], 3)
        self.assertEqual(result["rows"][0]["retry_limit"], 3)
        self.assertTrue(result["rows"][0]["retry_exhausted"])
        self.assertFalse(dto_row["ready_to_drain"])
        self.assertEqual(dto_row["diagnostic_status"], "retry_exhausted")
        self.assertEqual(dto_row["drain_recommendation"], "do_not_drain")
        self.assertEqual(dto_row["operator_trust_state"], "do-not-drain")
        self.assertEqual(dto_row["recovery_class"], "dead_letter_review")
        self.assertEqual(dto_row["dead_letter_status"], "retry_exhausted_review")
        self.assertEqual(preview["retry_budget"]["status"], "blocked")
        self.assertEqual(preview["retry_budget"]["exhausted_count"], 1)
        self.assertEqual(preview["retry_exhausted_count"], 1)


if __name__ == "__main__":
    unittest.main()
