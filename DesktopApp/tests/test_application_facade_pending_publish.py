from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from mediapipeline_desktop_app.models import ResolvedPaths
from DesktopApp.tests.test_application_facade import DummyWorkflowFacadeService, _resolved


class ApplicationFacadePendingPublishTests(unittest.TestCase):
    def test_pending_publish_preview_uses_existing_scan_service(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            pending_root = root / "PendingServerPush"
            pending_root.mkdir()
            payload = pending_root / "Movie.mkv"
            payload.write_bytes(b"abc")
            resolved = _resolved(root)
            resolved.pending_push_path = pending_root
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_pending_publish_preview(resolved).to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_pending_publish_preview.v1")
        self.assertTrue(preview["exists"])
        self.assertEqual(preview["payload_count"], 1)
        self.assertEqual(preview["total_bytes"], 3)
        self.assertEqual(preview["health_count"], 1)
        self.assertEqual(preview["state_counts"], {"orphan_payload": 1})
        self.assertEqual(preview["route_counts"], {"unknown": 1})
        self.assertEqual(preview["diagnostic_status_counts"], {"orphan_payload": 1})
        self.assertEqual(preview["diagnostic_severity_counts"], {"warning": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"review-before-drain": 1})
        self.assertEqual(preview["recovery_class_counts"], {"orphan_payload_review": 1})
        self.assertEqual(preview["recommended_open_target_counts"], {"local_file": 1})
        self.assertEqual(preview["issue_count"], 1)
        self.assertEqual(preview["ready_count"], 0)
        self.assertEqual(preview["orphan_payload_count"], 1)
        self.assertEqual(preview["invalid_manifest_count"], 0)
        self.assertEqual(preview["missing_sidecar_count"], 0)
        self.assertFalse(preview["drain_summary"]["exists"])
        self.assertTrue(preview["drain_summary"]["path"].endswith("pending_drain_summary.json"))
        self.assertEqual(preview["rows"][0]["state"], "orphan_payload")
        self.assertIn("payload has no manifest", preview["rows"][0]["issue_summary"])
        self.assertFalse(preview["rows"][0]["ready_to_drain"])
        self.assertEqual(preview["rows"][0]["diagnostic_status"], "orphan_payload")
        self.assertEqual(preview["rows"][0]["diagnostic_severity"], "warning")
        self.assertEqual(preview["rows"][0]["drain_recommendation"], "review_before_drain")
        self.assertEqual(preview["rows"][0]["operator_trust_state"], "review-before-drain")
        self.assertIn("orphan payload", preview["rows"][0]["primary_concern"])
        self.assertIn("Review backend-selected row targets", preview["rows"][0]["safe_next_action"])
        self.assertIn("overwrite the wrong destination", preview["rows"][0]["unsafe_if_ignored"])
        self.assertIn("pending_publish", preview["rows"][0]["recommended_diagnostics_targets"])
        self.assertIn("payload=", " ".join(preview["rows"][0]["proof_summary"]))
        self.assertIn("leftover", preview["rows"][0]["operator_guidance"])
        self.assertEqual(preview["rows"][0]["recovery_class"], "orphan_payload_review")
        self.assertIn("orphan payload", preview["rows"][0]["recovery_action"])
        self.assertEqual(preview["rows"][0]["evidence_fields"], ["local_file", "error"])
        self.assertEqual(preview["rows"][0]["recommended_open_targets"], ["local_file"])
        self.assertIn("row_key", preview["rows"][0])
        self.assertEqual(preview["recovery_summary"]["status"], "review")
        self.assertEqual(preview["recovery_summary"]["review_count"], 1)
        self.assertIn("orphan_payload_review", preview["recovery_summary"]["class_counts"])

    def test_pending_publish_preview_classifies_unreadable_manifest_for_operator_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            pending_root = root / "PendingServerPush"
            pending_root.mkdir()
            manifest = pending_root / "Broken.mkv.manifest.json"
            manifest.write_text("{not json", encoding="utf-8")
            resolved = _resolved(root)
            resolved.pending_push_path = pending_root
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_pending_publish_preview(resolved).to_mapping()

        self.assertEqual(preview["invalid_manifest_count"], 1)
        self.assertEqual(preview["diagnostic_status_counts"], {"unreadable_manifest": 1})
        self.assertEqual(preview["diagnostic_severity_counts"], {"error": 1})
        self.assertEqual(preview["operator_trust_state_counts"], {"do-not-drain": 1})
        self.assertEqual(preview["recovery_class_counts"], {"manifest_repair": 1})
        self.assertEqual(preview["recommended_open_target_counts"], {"manifest": 1})
        self.assertEqual(preview["recovery_summary"]["status"], "blocked")
        self.assertEqual(preview["recovery_summary"]["blocker_count"], 1)
        self.assertIn("Open unreadable/invalid manifests", " ".join(preview["recovery_summary"]["next_steps"]))
        row = preview["rows"][0]
        self.assertEqual(row["state"], "unreadable")
        self.assertEqual(row["diagnostic_status"], "unreadable_manifest")
        self.assertEqual(row["diagnostic_severity"], "error")
        self.assertEqual(row["drain_recommendation"], "do_not_drain")
        self.assertEqual(row["operator_trust_state"], "do-not-drain")
        self.assertIn("manifest unreadable or invalid", row["primary_concern"])
        self.assertIn("state", row["recommended_diagnostics_targets"])
        self.assertEqual(row["recovery_class"], "manifest_repair")
        self.assertIn("JSON", row["operator_guidance"])
        self.assertIn("JSON validity", row["recovery_action"])
        self.assertIn("manifest_path", row["evidence_fields"])
        self.assertEqual(row["recommended_open_targets"], ["manifest"])

    def test_pending_publish_preview_exposes_durable_drain_summary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            pending_root = state_root / "PendingServerPush"
            summary_path = state_root / "Progress" / "pending_drain_summary.json"
            pending_root.mkdir(parents=True)
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_drain_summary.v1",
                        "started_at": "2026-05-13T01:00:00Z",
                        "completed_at": "2026-05-13T01:01:00Z",
                        "force": True,
                        "pending_root": str(pending_root),
                        "manifest_count_at_start": 2,
                        "attempted_count": 2,
                        "recovered_count": 1,
                        "succeeded_count": 1,
                        "already_published_count": 1,
                        "error_count": 0,
                        "skipped_count": 0,
                        "remaining_count": 0,
                        "stopped": False,
                        "deferred": False,
                        "status_counts": {"already_published": 1, "succeeded": 1},
                        "route_counts": {"encode": 1, "remux": 1},
                        "items": [
                            {
                                "manifest_path": str(pending_root / "Movie.mkv.manifest.json"),
                                "local_file": str(pending_root / "Movie.mkv"),
                                "server_out": str(root / "Outsource" / "Movie.mkv"),
                                "route": "remux",
                                "status": "succeeded",
                                "sidecar_count": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.state_root = state_root
            resolved.pending_push_path = pending_root
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_pending_publish_preview(resolved).to_mapping()

        summary = preview["drain_summary"]
        self.assertTrue(summary["exists"])
        self.assertEqual(summary["path"], str(summary_path))
        self.assertEqual(summary["schema_version"], "pending_drain_summary.v1")
        self.assertEqual(summary["attempted_count"], 2)
        self.assertEqual(summary["status_counts"], {"already_published": 1, "succeeded": 1})
        self.assertEqual(summary["items"][0]["status"], "succeeded")

    def test_publish_reconciliation_correlates_completed_pending_and_drain_summary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Source" / "Movie.mkv"
            output = root / "Outsource" / "Movie.mkv"
            missing_output = root / "Outsource" / "Missing.mkv"
            missing_pending_output = root / "Outsource" / "MissingPending.mkv"
            missing_drained_output = root / "Outsource" / "MissingDrained.mkv"
            source.parent.mkdir(parents=True)
            output.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            output.write_bytes(b"output")

            completed_manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            completed_manifest.parent.mkdir(parents=True)
            completed_manifest.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "source_path": str(source),
                                "output_path": str(output),
                                "output_file": output.name,
                                "route": "remux",
                                "publish_mode": "deferred",
                                "source_size": source.stat().st_size,
                                "output_size": output.stat().st_size,
                                "encoded_at": "2026-05-14T08:00:00-04:00",
                            }
                        ),
                        json.dumps(
                            {
                                "source_path": str(root / "Source" / "Missing.mkv"),
                                "output_path": str(missing_output),
                                "output_file": missing_output.name,
                                "route": "encode",
                                "publish_mode": "deferred",
                                "encoded_at": "2026-05-14T08:01:00-04:00",
                            }
                        ),
                        json.dumps(
                            {
                                "source_path": str(root / "Source" / "MissingPending.mkv"),
                                "output_path": str(missing_pending_output),
                                "output_file": missing_pending_output.name,
                                "route": "remux",
                                "publish_mode": "deferred",
                                "encoded_at": "2026-05-14T08:02:00-04:00",
                            }
                        ),
                        json.dumps(
                            {
                                "source_path": str(root / "Source" / "MissingDrained.mkv"),
                                "output_path": str(missing_drained_output),
                                "output_file": missing_drained_output.name,
                                "route": "remux",
                                "publish_mode": "deferred",
                                "encoded_at": "2026-05-14T08:03:00-04:00",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            state_root = root / "State"
            pending_root = root / "PendingServerPush"
            pending_root.mkdir()
            pending_payload = pending_root / output.name
            pending_payload.write_bytes(output.read_bytes())
            (pending_root / f"{output.name}.manifest.json").write_text(
                json.dumps(
                    {
                        "manifest_state": "parked",
                        "local_file": str(pending_payload),
                        "server_out": str(output),
                        "source_path": str(source),
                        "route": "remux",
                        "output_size": output.stat().st_size,
                    }
                ),
                encoding="utf-8",
            )
            missing_pending_payload = pending_root / missing_pending_output.name
            missing_pending_payload.write_bytes(b"still parked")
            (pending_root / f"{missing_pending_output.name}.manifest.json").write_text(
                json.dumps(
                    {
                        "manifest_state": "parked",
                        "local_file": str(missing_pending_payload),
                        "server_out": str(missing_pending_output),
                        "source_path": str(root / "Source" / "MissingPending.mkv"),
                        "route": "remux",
                        "output_size": missing_pending_payload.stat().st_size,
                    }
                ),
                encoding="utf-8",
            )
            summary_path = state_root / "Progress" / "pending_drain_summary.json"
            summary_path.parent.mkdir(parents=True)
            summary_path.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_drain_summary.v1",
                        "started_at": "2026-05-14T08:10:00Z",
                        "completed_at": "2026-05-14T08:11:00Z",
                        "items": [
                            {
                                "local_file": str(pending_payload),
                                "server_out": str(output),
                                "source_path": str(source),
                                "route": "remux",
                                "status": "succeeded",
                            },
                            {
                                "local_file": str(pending_root / missing_drained_output.name),
                                "server_out": str(missing_drained_output),
                                "source_path": str(root / "Source" / "MissingDrained.mkv"),
                                "route": "remux",
                                "status": "succeeded",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            resolved = _resolved(root)
            resolved.state_root = state_root
            resolved.completed_manifest_path = completed_manifest
            resolved.pending_push_path = pending_root
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_publish_reconciliation_preview(resolved, limit=50).to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_publish_reconciliation.v1")
        self.assertEqual(preview["status"], "review_blockers")
        self.assertEqual(preview["completed_count"], 4)
        self.assertEqual(preview["pending_count"], 2)
        self.assertEqual(preview["drain_item_count"], 2)
        self.assertEqual(preview["exact_pending_destination_count"], 1)
        self.assertEqual(preview["exact_pending_source_count"], 1)
        self.assertGreaterEqual(preview["drain_output_count"], 1)
        self.assertEqual(preview["missing_with_pending_proof_count"], 2)
        self.assertEqual(preview["missing_with_drain_proof_count"], 2)
        self.assertEqual(preview["missing_without_proof_count"], 1)
        signals = {row["signal"] for row in preview["rows"]}
        self.assertIn("pending_destination_overlap", signals)
        self.assertIn("completed_source_still_pending", signals)
        self.assertIn("drain_summary_output_proof", signals)
        self.assertIn("missing_output_still_pending", signals)
        self.assertIn("missing_output_with_drain_proof", signals)
        self.assertIn("missing_output_without_proof", signals)
        self.assertIn("Backend publish reconciliation:", "\n".join(preview["summary_lines"]))
        self.assertIn("Missing completed output with pending proof: 2", "\n".join(preview["summary_lines"]))
        self.assertIn("Missing completed output with drain proof: 2", "\n".join(preview["summary_lines"]))
        self.assertIn("Mutation guardrail", "\n".join(preview["summary_lines"]))
        blocked = [row for row in preview["rows"] if row["signal"] == "missing_output_without_proof"][0]
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("Completed Manifest", blocked["safe_next_action"])
        final_placement = [row for row in preview["rows"] if row["signal"] == "missing_output_with_drain_proof"][0]
        self.assertEqual(final_placement["status"], "warning")
        self.assertIn("final-placement conflict", final_placement["safe_next_action"])

    def test_publish_reconciliation_endpoint_is_read_only(self) -> None:
        from urllib.request import Request, urlopen

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.completed_manifest_path = root / "State" / "Completed" / "completed_jobs.jsonl"
            resolved.pending_push_path = root / "PendingServerPush"
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(facade, token="web-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                request = Request(
                    f"{server.url}/api/publish-reconciliation?limit=25",
                    headers={"Authorization": "Bearer web-token"},
                )
                with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.stop()

        self.assertEqual(payload["schema_version"], "desktop_publish_reconciliation.v1")
        self.assertEqual(payload["status"], "no_completed_rows")
        self.assertEqual(service.opened_paths, [])

    def test_pending_publish_open_uses_backend_row_key_not_frontend_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            pending_root = root / "PendingServerPush"
            pending_root.mkdir()
            payload = pending_root / "Movie.mkv"
            payload.write_bytes(b"abc")
            source = root / "Source" / "Movie.mkv"
            source.parent.mkdir()
            source.write_bytes(b"source")
            destination = root / "Outsource" / "Movies" / "Movie.mkv"
            destination.parent.mkdir(parents=True)
            manifest = pending_root / "Movie.mkv.manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "manifest_state": "parked",
                        "local_file": str(payload),
                        "server_out": str(destination),
                        "source_path": str(source),
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.pending_push_path = pending_root
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service)
            preview = facade.get_pending_publish_preview(resolved).to_mapping()
            row_key = preview["rows"][0]["row_key"]

            opened_payload = facade.open_pending_publish_location(resolved, {"row_key": row_key, "target": "local_file"})
            opened_manifest = facade.open_pending_publish_location(resolved, {"row_key": row_key, "target": "manifest"})
            opened_destination = facade.open_pending_publish_location(resolved, {"row_key": row_key, "target": "destination_folder"})
            rejected = facade.open_pending_publish_location(resolved, {"row_key": row_key, "target": str(root / "secret.txt")})

        self.assertTrue(opened_payload.ok)
        self.assertEqual(opened_payload.command, "pending_publish.open")
        self.assertEqual(opened_payload.data["target"], "local_file")
        self.assertTrue(opened_manifest.ok)
        self.assertTrue(opened_destination.ok)
        self.assertEqual(service.opened_paths, [payload, manifest, destination.parent])
        self.assertFalse(rejected.ok)
        self.assertIn("not allowed", rejected.message)

    def test_pending_publish_open_reports_scan_failure_instead_of_missing_row(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            service = DummyWorkflowFacadeService(root)

            def fail_scan(_resolved: ResolvedPaths) -> dict[str, object]:
                raise RuntimeError("pending scan locked")

            service.scan_pending_publish = fail_scan
            facade = MediaPipelineApplicationFacade(service)

            result = facade.open_pending_publish_location(resolved, {"row_key": "row-1", "target": "local_file"})

        self.assertFalse(result.ok)
        self.assertEqual(result.severity, "error")
        self.assertIn("Pending publish scan failed before open", result.message)
        self.assertIn("pending scan locked", result.message)
        self.assertEqual(result.data["row_key"], "row-1")

    def test_pending_publish_open_supports_orphan_payload_row_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            pending_root = root / "PendingServerPush"
            pending_root.mkdir()
            payload = pending_root / "Orphan.mkv"
            payload.write_bytes(b"abc")
            resolved = _resolved(root)
            resolved.pending_push_path = pending_root
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service)
            preview = facade.get_pending_publish_preview(resolved).to_mapping()
            row_key = preview["rows"][0]["row_key"]

            result = facade.open_pending_publish_location(resolved, {"row_key": row_key, "target": "local_file"})

        self.assertTrue(row_key.startswith("\x1f"))
        self.assertTrue(result.ok)
        self.assertEqual(result.command, "pending_publish.open")
        self.assertEqual(service.opened_paths, [payload])

    def test_pending_publish_recovery_plan_is_backend_authored_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            pending_root = root / "PendingServerPush"
            pending_root.mkdir()
            payload = pending_root / "Movie.mkv"
            payload.write_bytes(b"abc")
            broken_manifest = pending_root / "Broken.mkv.manifest.json"
            broken_manifest.write_text("{not json", encoding="utf-8")
            resolved = _resolved(root)
            resolved.pending_push_path = pending_root
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            result = facade.plan_pending_publish_recovery(resolved, {"scope": "all"})
            selected_row_key = next(row["row_key"] for row in result.data["rows"] if row["state"] == "orphan_payload")
            selected = facade.plan_pending_publish_recovery(resolved, {"scope": "selected", "row_key": selected_row_key})
            missing = facade.plan_pending_publish_recovery(resolved, {"scope": "selected", "row_key": "not-current"})

        self.assertTrue(result.ok)
        self.assertEqual(result.command, "pending_publish.recovery_plan_dry_run")
        self.assertEqual(result.severity, "warning")
        self.assertEqual(result.data["schema_version"], "pending_publish_recovery_plan.v1")
        self.assertEqual(result.data["scope"], "all")
        self.assertEqual(result.data["row_count"], 2)
        self.assertEqual(result.data["blocker_count"], 1)
        self.assertEqual(result.data["review_count"], 1)
        self.assertTrue(result.data["dry_run_only"])
        self.assertFalse(result.data["would_mutate"])
        self.assertIn("unlock_or_repair_manifest_json", result.data["action_counts"])
        self.assertIn("classify_orphan_payload_before_cleanup_or_rerun", result.data["action_counts"])
        self.assertTrue(all(row["dry_run_only"] for row in result.data["rows"]))
        self.assertTrue(all(row["would_mutate"] is False for row in result.data["rows"]))
        self.assertTrue(selected.ok)
        self.assertEqual(selected.data["scope"], "selected")
        self.assertEqual(selected.data["row_count"], 1)
        self.assertFalse(missing.ok)
        self.assertEqual(missing.severity, "warning")
        self.assertEqual(missing.refresh_hint, "pending_publish")

    def test_pending_publish_recovery_plan_reports_scan_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            service = DummyWorkflowFacadeService(root)

            def fail_scan(_resolved: ResolvedPaths) -> dict[str, object]:
                raise RuntimeError("pending scan locked")

            service.scan_pending_publish = fail_scan
            facade = MediaPipelineApplicationFacade(service)

            result = facade.plan_pending_publish_recovery(resolved, {"scope": "all"})

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "pending_publish.recovery_plan_dry_run")
        self.assertEqual(result.severity, "error")
        self.assertIn("Pending publish scan failed before recovery plan", result.message)
        self.assertTrue(result.data["dry_run_only"])
        self.assertFalse(result.data["would_mutate"])
