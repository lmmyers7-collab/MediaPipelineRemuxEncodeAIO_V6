from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mediapipeline.tools.paths import find_repo_root

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest  # noqa: E402
from mediapipeline.core.paths.contracts import ResolvedPaths  # noqa: E402
from mediapipeline.core.processes.rerun_results import (  # noqa: E402
    rerun_promote_dry_run,
    rerun_promote_to_pending_publish,
    rerun_results_payload,
)
from mediapipeline.core.publish.pending_manifest import pending_manifest_row  # noqa: E402


def _resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    state_root = local_base / "State"
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host="pwsh",
        local_base=local_base,
        state_root=state_root,
        pending_push_path=state_root / "PendingServerPush",
        audit_reports_path=local_base / "AuditReports",
    )


class RerunResultsTests(unittest.TestCase):
    def test_promote_to_pending_publish_writes_current_manifest_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            review_output = root / "Review" / "Movie.mkv"
            final_output = root / "Outsource" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            review_output.parent.mkdir(parents=True)
            source.write_bytes(b"source-media")
            review_output.write_bytes(b"verified-output")
            review_sidecar = review_output.with_name("Movie.pipeline.json")
            review_srt = review_output.with_name("Movie.eng.srt")
            review_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            review_sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_sidecar.v1",
                        "pipeline_version": "1.0",
                        "route": "remux",
                        "output_file": review_output.name,
                        "output_path": str(review_output),
                        "publish_state": "published",
                        "publish_transaction_id": "nested-rerun",
                        "source_identity_v2": "rerun-test-source",
                        "output_size": review_output.stat().st_size,
                        "tx3g_srt_tracks": [
                            {
                                "path": str(review_srt),
                                "file_name": review_srt.name,
                                "status": "written",
                                "language": "eng",
                                "cue_count": 1,
                            }
                        ],
                        "tx3g_srt_failures": [],
                        "bdpgs_srt_failures": [],
                        "vobsub_srt_failures": [],
                        "converted_srt_sidecar_candidates": [{"selected": True, "srt_path": str(review_srt)}],
                        "subtitle_output_reduction": [],
                        "tx3g_embedded_srt_tracks": [],
                        "bdpgs_embedded_srt_tracks": [],
                        "vobsub_embedded_srt_tracks": [],
                        "tx3g_srt_conversion_enabled": True,
                        "tx3g_external_srt_sidecars_enabled": True,
                        "drop_tx3g_after_conversion": False,
                        "bdpgs_srt_conversion_enabled": False,
                        "drop_bdpgs_after_conversion": False,
                        "vobsub_srt_conversion_enabled": False,
                        "drop_vobsub_after_conversion": False,
                        "route_plan": {"decision": "remux"},
                    }
                ),
                encoding="utf-8",
            )

            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_batch.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-test",
                        "status": "complete",
                        "rows": [
                            {
                                "status": "complete",
                                "source_path": str(source),
                                "verified_output_path": str(review_output),
                                "final_output_path": str(final_output),
                                "source_size": source.stat().st_size,
                                "source_mtime_utc": "2026-07-02T04:00:00Z",
                                "source_identity_v2": "rerun-test-source",
                                "source_identity_v2_algorithm": "rerun_results_test",
                                "media_kind": "movie",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            row = rerun_results_payload(resolved)["rows"][0]
            dry_run = rerun_promote_dry_run(
                resolved,
                {"row_key": row["row_key"]},
            )
            fingerprint = dry_run.data["dry_run_fingerprint"]
            result = rerun_promote_to_pending_publish(
                resolved,
                {"row_key": row["row_key"], "dry_run_fingerprint": fingerprint, "confirm_promote": True},
                product_version="2026.06.04.001",
            )

            self.assertTrue(result.ok, result.message)
            self.assertFalse(review_output.exists())
            self.assertTrue(source.exists())
            payload_path = Path(result.data["pending_publish_payload_path"])
            manifest_path = Path(result.data["pending_publish_manifest_path"])
            self.assertEqual(payload_path.read_bytes(), b"verified-output")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = PendingPushManifest.from_mapping(payload)
            row = pending_manifest_row(manifest_path)

            self.assertEqual(manifest.pipeline_version, "1.0")
            self.assertEqual(manifest.product_version, "2026.06.04.001")
            self.assertTrue(manifest.publish_transaction_id.startswith("rerun-promote-"))
            self.assertEqual(manifest.manifest_state, "parked")
            self.assertEqual(len(manifest.sidecar_files), 1)
            self.assertEqual(Path(manifest.sidecar_files[0]["local_file"]).read_text(encoding="utf-8"), review_srt.read_text(encoding="utf-8"))
            self.assertEqual(manifest.sidecar_files[0]["server_out"], str(final_output.with_name("Movie.eng.srt")))
            self.assertEqual(manifest.tx3g_srt_tracks[0]["status"], "pending")
            self.assertEqual(manifest.tx3g_srt_tracks[0]["path"], str(final_output.with_name("Movie.eng.srt")))
            self.assertEqual(payload["converted_srt_sidecar_candidates"][0]["selected"], True)
            self.assertEqual(payload["route_plan"]["decision"], "remux")
            self.assertEqual(manifest.vobsub_srt_failures, [])
            self.assertEqual(row["state"], "parked")
            self.assertEqual(row["error"], "")

    def test_promote_writes_pending_move_manifest_before_media_move(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            source = root / "Source" / "Movie.mkv"
            review_output = root / "Review" / "Movie.mkv"
            final_output = root / "Outsource" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            review_output.parent.mkdir(parents=True)
            source.write_bytes(b"source-media")
            review_output.write_bytes(b"verified-output")

            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            (manifest_root / "rerun_batch.json").write_text(
                json.dumps(
                    {
                        "batch_id": "rerun-test",
                        "status": "complete",
                        "rows": [
                            {
                                "status": "complete",
                                "source_path": str(source),
                                "verified_output_path": str(review_output),
                                "final_output_path": str(final_output),
                                "source_size": source.stat().st_size,
                                "source_identity_v2": "rerun-test-source",
                                "media_kind": "movie",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            row = rerun_results_payload(resolved)["rows"][0]
            dry_run = rerun_promote_dry_run(resolved, {"row_key": row["row_key"]})
            with mock.patch("mediapipeline.core.processes.rerun_results.shutil.move", side_effect=OSError("move blocked")):
                result = rerun_promote_to_pending_publish(
                    resolved,
                    {
                        "row_key": row["row_key"],
                        "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
                        "confirm_promote": True,
                    },
                )

            self.assertFalse(result.ok)
            self.assertTrue(review_output.exists())
            manifest_path = Path(result.data["pending_publish_manifest_path"])
            self.assertTrue(manifest_path.exists())
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["manifest_state"], "pending_move")


if __name__ == "__main__":
    unittest.main()
