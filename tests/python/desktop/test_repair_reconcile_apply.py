from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.completed.policy import completed_record_key
from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest
from mediapipeline.core.validation.boundary import ValidationFailure, validate_api_payload
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import CompletedJobRecord
from tests.python.desktop.test_application_facade import DummyWorkflowFacadeService
from tests.python.desktop.test_repair_reconcile_dry_run import _completed_fixture, _file_state, _pending_fixture, _pending_manifest_payload


def _apply_request(dry_run_data: dict[str, object], *, reason: str = "operator confirmed test") -> dict[str, object]:
    return {
        "scope": dry_run_data["scope"],
        "row_key": dry_run_data["selected_row_keys"][0],
        "limit": dry_run_data["request_summary"]["limit"],
        "reason": reason,
        "dry_run_fingerprint": dry_run_data["dry_run_fingerprint"],
        "confirm_apply": True,
    }


class RepairReconcileApplyTests(unittest.TestCase):
    def test_completed_sidecar_repair_apply_writes_only_selected_sidecar_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _completed_fixture(root)
            sidecar = files["sidecar"]
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            payload["operator_note"] = "preserve me"
            sidecar.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            output_before = _file_state(files["output"])
            source_before = _file_state(files["source"])
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            row_key = facade.get_completed_preview(resolved).to_mapping()["rows"][0]["row_key"]
            dry_run = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="completed.repair_sidecar_metadata",
                request={"scope": "selected", "row_key": row_key, "reason": "test"},
            ).to_mapping()["data"]

            result = facade.apply_repair_reconcile(
                resolved,
                candidate_command="completed.repair_sidecar_metadata",
                request=_apply_request(dry_run),
            ).to_mapping()

            repaired = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertEqual(result["data"]["schema_version"], "desktop_repair_reconcile_apply.v1")
            self.assertTrue(result["data"]["applied"])
            self.assertEqual(result["data"]["selected_row_keys"], [row_key])
            self.assertEqual(result["data"]["written_paths"], [str(sidecar)])
            self.assertEqual(result["data"]["backup_paths"][0].split("\\")[-1], sidecar.name)
            self.assertTrue(Path(result["data"]["backup_paths"][0]).exists())
            self.assertEqual(repaired["source_path"], str(files["source"]))
            self.assertEqual(repaired["output_path"], str(files["output"]))
            self.assertEqual(repaired["output_file"], files["output"].name)
            self.assertEqual(repaired["operator_note"], "preserve me")
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertTrue(result["data"]["source_payload_output_unchanged"])

    def test_completed_manifest_reconcile_apply_writes_only_manifest_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _completed_fixture(root)
            manifest = files["completed_manifest"]
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preview = facade.get_completed_preview(resolved).to_mapping()
            row = dict(preview["rows"][0])
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload.pop("output_path", None)
            manifest_payload["output_file"] = files["output"].name
            manifest.write_text(json.dumps(manifest_payload, sort_keys=True) + "\n", encoding="utf-8")
            row_key = completed_record_key(CompletedJobRecord(sidecar_path=manifest, payload=dict(manifest_payload)))
            row.update(
                {
                    "row_key": row_key,
                    "source_path": str(files["source"]),
                    "output_path": str(files["output"]),
                    "output_file": files["output"].name,
                    "output_exists": True,
                    "manifest_output_path": "",
                    "manifest_output_file": files["output"].name,
                    "sidecar_path": str(manifest),
                    "expected_sidecar_path": str(files["sidecar"]),
                    "sidecar_exists": True,
                    "sidecar_matches_output": False,
                    "consistency_issues": ["manifest_missing_output_path"],
                }
            )
            preview["rows"] = [row]
            manifest_before = _file_state(manifest)
            source_before = _file_state(files["source"])
            output_before = _file_state(files["output"])
            sidecar_before = _file_state(files["sidecar"])
            original_get_completed_preview = facade.get_completed_preview
            facade.get_completed_preview = lambda _resolved, **_kwargs: SimpleNamespace(to_mapping=lambda: preview)  # type: ignore[method-assign]
            try:
                dry_run = facade.plan_repair_reconcile_dry_run(
                    resolved,
                    candidate_command="completed.reconcile_manifest",
                    request={"scope": "selected", "row_key": row_key, "reason": "restore output path"},
                ).to_mapping()["data"]

                result = facade.apply_repair_reconcile(
                    resolved,
                    candidate_command="completed.reconcile_manifest",
                    request=_apply_request(dry_run, reason="manifest only"),
                ).to_mapping()
            finally:
                facade.get_completed_preview = original_get_completed_preview  # type: ignore[method-assign]

            repaired = json.loads(manifest.read_text(encoding="utf-8"))
            backup_path = Path(result["data"]["backup_paths"][0])
            dry_run_row = dry_run["diff_summary"]["rows"][0]
            self.assertTrue(dry_run["safe_to_apply"])
            self.assertEqual(dry_run_row["status"], "candidate")
            self.assertEqual(dry_run_row["reasons"], ["manifest_missing_output_path"])
            self.assertTrue(result["ok"])
            self.assertTrue(result["data"]["applied"])
            self.assertEqual(result["data"]["selected_row_keys"], [row_key])
            self.assertEqual(result["data"]["written_paths"], [str(manifest)])
            self.assertEqual(backup_path.name, manifest.name)
            self.assertTrue(backup_path.exists())
            self.assertEqual(json.loads(backup_path.read_text(encoding="utf-8")), manifest_payload)
            self.assertNotEqual(_file_state(manifest), manifest_before)
            self.assertEqual(repaired["source_path"], str(files["source"]))
            self.assertEqual(repaired["output_path"], str(files["output"]))
            self.assertEqual(repaired["output_file"], files["output"].name)
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertEqual(_file_state(files["sidecar"]), sidecar_before)
            self.assertTrue(result["data"]["source_payload_output_unchanged"])

    def test_apply_rejects_mismatched_dry_run_fingerprint_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _completed_fixture(root)
            before = _file_state(files["sidecar"])
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            row_key = facade.get_completed_preview(resolved).to_mapping()["rows"][0]["row_key"]

            result = facade.apply_repair_reconcile(
                resolved,
                candidate_command="completed.repair_sidecar_metadata",
                request={
                    "scope": "selected",
                    "row_key": row_key,
                    "limit": 100,
                    "reason": "fingerprint mismatch",
                    "dry_run_fingerprint": "bad-fingerprint",
                    "confirm_apply": True,
                },
            ).to_mapping()

            self.assertFalse(result["ok"])
            self.assertFalse(result["data"]["applied"])
            self.assertIn("fingerprint", result["errors"][0])
            self.assertEqual(_file_state(files["sidecar"]), before)

    def test_pending_manifest_repair_apply_writes_only_manifest_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _pending_fixture(root, repairable_manifest=True)
            manifest = files["pending_manifest"]
            drain_summary = resolved.state_root / "Progress" / "pending_drain_summary.json"
            drain_summary.parent.mkdir(parents=True, exist_ok=True)
            drain_summary.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_drain_summary.v1",
                        "status": "completed",
                        "items": [
                            {
                                "status": "succeeded",
                                "local_file": str(root / "OtherPending" / "AlreadyDrained.mkv"),
                                "server_out": str(root / "Outsource" / "AlreadyDrained.mkv"),
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            source_before = _file_state(files["source"])
            output_before = _file_state(files["output"])
            payload_before = _file_state(files["pending_payload"])
            manifest_before = _file_state(manifest)
            drain_summary_before = _file_state(drain_summary)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preview = facade.get_pending_publish_preview(resolved).to_mapping()
            row_key = next(row["row_key"] for row in preview["rows"] if row.get("diagnostic_status") == "invalid_manifest")
            dry_run = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="pending_publish.repair_manifest",
                request={"scope": "selected", "row_key": row_key, "reason": "normalize"},
            ).to_mapping()["data"]

            result = facade.apply_repair_reconcile(
                resolved,
                candidate_command="pending_publish.repair_manifest",
                request=_apply_request(dry_run),
            ).to_mapping()

            repaired = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertTrue(result["data"]["applied"])
            self.assertEqual(result["data"]["written_paths"], [str(manifest)])
            self.assertEqual(result["data"]["backup_paths"][0].split("\\")[-1], manifest.name)
            self.assertTrue(Path(result["data"]["backup_paths"][0]).exists())
            self.assertNotEqual(_file_state(manifest), manifest_before)
            PendingPushManifest.from_mapping(repaired)
            self.assertEqual(repaired["local_file"], str(files["pending_payload"]))
            self.assertEqual(repaired["output_size"], files["pending_payload"].stat().st_size)
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertEqual(_file_state(files["pending_payload"]), payload_before)
            self.assertEqual(_file_state(drain_summary), drain_summary_before)
            self.assertTrue(result["data"]["source_payload_output_unchanged"])
            repaired_preview = facade.get_pending_publish_preview(resolved).to_mapping()
            repaired_row = repaired_preview["rows"][0]
            self.assertEqual(repaired_row["state"], "parked")
            self.assertEqual(repaired_row["diagnostic_status"], "ready")
            self.assertTrue(repaired_row["ready_to_drain"])
            self.assertEqual(repaired_row["drain_recommendation"], "ready_to_drain")
            self.assertTrue(repaired_preview["drain_summary"]["exists"])
            self.assertEqual(repaired_preview["drain_summary"]["path"], str(drain_summary))

    def test_orphan_payload_reconcile_apply_is_manifest_only_and_blocks_incomplete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _pending_fixture(root, orphan_payload=True)
            before = _file_state(files["pending_payload"])
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            row_key = facade.get_pending_publish_preview(resolved).to_mapping()["rows"][0]["row_key"]
            dry_run = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="pending_publish.reconcile_orphan_payloads",
                request={"scope": "selected", "row_key": row_key},
            ).to_mapping()["data"]
            dry_run_row = dry_run["diff_summary"]["rows"][0]

            result = facade.apply_repair_reconcile(
                resolved,
                candidate_command="pending_publish.reconcile_orphan_payloads",
                request=_apply_request(dry_run, reason="manifest only"),
            ).to_mapping()

            self.assertFalse(dry_run["safe_to_apply"])
            self.assertEqual(dry_run_row["status"], "blocked")
            self.assertFalse(dry_run_row["proposed_manifest_available"])
            self.assertIn("server_out", dry_run_row["missing_required_manifest_fields"])
            self.assertIn("source_path", dry_run_row["missing_required_manifest_fields"])
            self.assertFalse(result["ok"])
            self.assertIn("safe_to_apply is false", result["errors"][0])
            self.assertFalse(result["data"]["applied"])
            self.assertFalse(result["data"]["written_paths"])
            self.assertFalse((files["pending_payload"].with_suffix(files["pending_payload"].suffix + ".manifest.json")).exists())
            self.assertEqual(_file_state(files["pending_payload"]), before)

    def test_orphan_payload_reconcile_apply_writes_only_backend_proposed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _pending_fixture(root, orphan_payload=True)
            manifest = Path(str(files["pending_payload"]) + ".manifest.json")
            drain_summary = resolved.state_root / "Progress" / "pending_drain_summary.json"
            drain_summary.parent.mkdir(parents=True, exist_ok=True)
            drain_summary.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_drain_summary.v1",
                        "status": "completed",
                        "items": [
                            {
                                "status": "succeeded",
                                "local_file": str(root / "OtherPending" / "AlreadyDrained.mkv"),
                                "server_out": str(root / "Outsource" / "AlreadyDrained.mkv"),
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            source_before = _file_state(files["source"])
            output_before = _file_state(files["output"])
            payload_before = _file_state(files["pending_payload"])
            drain_summary_before = _file_state(drain_summary)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            original_get_pending_publish_preview = facade.get_pending_publish_preview
            preview = facade.get_pending_publish_preview(resolved).to_mapping()
            row = preview["rows"][0]
            row["backend_manifest_proposal"] = _pending_manifest_payload(files["pending_payload"], files["output"], files["source"])
            facade.get_pending_publish_preview = lambda _resolved: SimpleNamespace(to_mapping=lambda: preview)  # type: ignore[method-assign]
            dry_run = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="pending_publish.reconcile_orphan_payloads",
                request={"scope": "selected", "row_key": row["row_key"], "reason": "recover manifest"},
            ).to_mapping()["data"]

            result = facade.apply_repair_reconcile(
                resolved,
                candidate_command="pending_publish.reconcile_orphan_payloads",
                request=_apply_request(dry_run, reason="manifest only"),
            ).to_mapping()
            facade.get_pending_publish_preview = original_get_pending_publish_preview  # type: ignore[method-assign]

            written = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(dry_run["safe_to_apply"])
            self.assertTrue(result["ok"])
            self.assertTrue(result["data"]["applied"])
            self.assertEqual(result["data"]["written_paths"], [str(manifest)])
            self.assertEqual(result["data"]["backup_paths"], [])
            PendingPushManifest.from_mapping(written)
            self.assertEqual(written["local_file"], str(files["pending_payload"]))
            self.assertEqual(written["server_out"], str(files["output"]))
            self.assertEqual(written["source_path"], str(files["source"]))
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertEqual(_file_state(files["pending_payload"]), payload_before)
            self.assertEqual(_file_state(drain_summary), drain_summary_before)
            self.assertTrue(result["data"]["source_payload_output_unchanged"])
            repaired_preview = facade.get_pending_publish_preview(resolved).to_mapping()
            repaired_row = repaired_preview["rows"][0]
            self.assertEqual(repaired_row["state"], "parked")
            self.assertEqual(repaired_row["diagnostic_status"], "ready")
            self.assertTrue(repaired_row["ready_to_drain"])
            self.assertEqual(repaired_row["drain_recommendation"], "ready_to_drain")
            self.assertTrue(repaired_preview["drain_summary"]["exists"])
            self.assertEqual(repaired_preview["drain_summary"]["path"], str(drain_summary))

    def test_confirmed_apply_payload_is_strict_and_rejects_frontend_paths(self) -> None:
        payload = {
            "scope": "selected",
            "row_key": "row-1",
            "limit": 1,
            "reason": "repair",
            "dry_run_fingerprint": "abc",
            "confirm_apply": True,
        }

        self.assertEqual(validate_api_payload("/api/completed/repair-sidecar-metadata", payload), payload)
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/completed/repair-sidecar-metadata", {**payload, "path": "C:/Media/Movie.mkv"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/completed/repair-sidecar-metadata", {**payload, "confirm_apply": "true"})

    def test_local_api_completed_sidecar_apply_is_journaled_without_touching_media(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _completed_fixture(root)
            sidecar = files["sidecar"]
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            payload["operator_note"] = "preserve me through local api"
            sidecar.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            source_before = _file_state(files["source"])
            output_before = _file_state(files["output"])
            sidecar_before = _file_state(sidecar)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            row_key = facade.get_completed_preview(resolved).to_mapping()["rows"][0]["row_key"]
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                dry_run_request = Request(
                    f"{server.url}/api/completed/repair-sidecar-metadata-dry-run",
                    data=json.dumps({"scope": "selected", "row_key": row_key, "reason": "repair sidecar metadata"}).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(dry_run_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    dry_run_payload = json.loads(response.read().decode("utf-8"))
                request = Request(
                    f"{server.url}/api/completed/repair-sidecar-metadata",
                    data=json.dumps(_apply_request(dry_run_payload["data"], reason="sidecar metadata only")).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                    apply_payload = json.loads(response.read().decode("utf-8"))
                commands_request = Request(
                    f"{server.url}/api/commands?limit=10",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(commands_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    commands = json.loads(response.read().decode("utf-8"))
            finally:
                server.stop()

            repaired = json.loads(sidecar.read_text(encoding="utf-8"))
            backup_path = Path(apply_payload["data"]["backup_paths"][0])
            self.assertTrue(dry_run_payload["ok"])
            self.assertTrue(dry_run_payload["data"]["safe_to_apply"])
            self.assertTrue(dry_run_payload["data"]["suppress_command_journal"])
            self.assertTrue(apply_payload["ok"])
            self.assertTrue(apply_payload["data"]["applied"])
            self.assertEqual(apply_payload["data"]["candidate_command"], "completed.repair_sidecar_metadata")
            self.assertEqual(apply_payload["data"]["selected_row_keys"], [row_key])
            self.assertEqual(apply_payload["data"]["written_paths"], [str(sidecar)])
            self.assertEqual(backup_path.name, sidecar.name)
            self.assertTrue(backup_path.exists())
            self.assertEqual(json.loads(backup_path.read_text(encoding="utf-8")), payload)
            self.assertNotEqual(_file_state(sidecar), sidecar_before)
            self.assertEqual(repaired["source_path"], str(files["source"]))
            self.assertEqual(repaired["output_path"], str(files["output"]))
            self.assertEqual(repaired["output_file"], files["output"].name)
            self.assertEqual(repaired["operator_note"], "preserve me through local api")
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertTrue(apply_payload["data"]["source_payload_output_unchanged"])
            self.assertEqual(len(commands["entries"]), 1)
            self.assertEqual(commands["entries"][0]["command"], "completed.repair_sidecar_metadata")
            self.assertFalse(any("drain" in str(entry.get("command", "")).lower() for entry in commands["entries"]))

    def test_local_api_completed_manifest_apply_is_journaled_without_touching_media(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _completed_fixture(root)
            manifest = files["completed_manifest"]
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            preview = facade.get_completed_preview(resolved).to_mapping()
            row = dict(preview["rows"][0])
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_payload.pop("output_path", None)
            manifest_payload["output_file"] = files["output"].name
            manifest.write_text(json.dumps(manifest_payload, sort_keys=True) + "\n", encoding="utf-8")
            row_key = completed_record_key(CompletedJobRecord(sidecar_path=manifest, payload=dict(manifest_payload)))
            row.update(
                {
                    "row_key": row_key,
                    "source_path": str(files["source"]),
                    "output_path": str(files["output"]),
                    "output_file": files["output"].name,
                    "output_exists": True,
                    "manifest_output_path": "",
                    "manifest_output_file": files["output"].name,
                    "sidecar_path": str(manifest),
                    "expected_sidecar_path": str(files["sidecar"]),
                    "sidecar_exists": True,
                    "sidecar_matches_output": False,
                    "consistency_issues": ["manifest_missing_output_path"],
                }
            )
            preview["rows"] = [row]
            manifest_before = _file_state(manifest)
            source_before = _file_state(files["source"])
            output_before = _file_state(files["output"])
            sidecar_before = _file_state(files["sidecar"])
            original_get_completed_preview = facade.get_completed_preview
            facade.get_completed_preview = lambda _resolved, **_kwargs: SimpleNamespace(to_mapping=lambda: preview)  # type: ignore[method-assign]
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                dry_run_request = Request(
                    f"{server.url}/api/completed/reconcile-manifest-dry-run",
                    data=json.dumps({"scope": "selected", "row_key": row_key, "reason": "restore output path"}).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(dry_run_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    dry_run_payload = json.loads(response.read().decode("utf-8"))
                apply_request = Request(
                    f"{server.url}/api/completed/reconcile-manifest",
                    data=json.dumps(_apply_request(dry_run_payload["data"], reason="manifest only")).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(apply_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    apply_payload = json.loads(response.read().decode("utf-8"))
                commands_request = Request(
                    f"{server.url}/api/commands?limit=10",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(commands_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    commands = json.loads(response.read().decode("utf-8"))
            finally:
                facade.get_completed_preview = original_get_completed_preview  # type: ignore[method-assign]
                server.stop()

            repaired = json.loads(manifest.read_text(encoding="utf-8"))
            backup_path = Path(apply_payload["data"]["backup_paths"][0])
            self.assertTrue(dry_run_payload["ok"])
            self.assertTrue(dry_run_payload["data"]["safe_to_apply"])
            self.assertTrue(dry_run_payload["data"]["suppress_command_journal"])
            self.assertEqual(dry_run_payload["data"]["diff_summary"]["rows"][0]["reasons"], ["manifest_missing_output_path"])
            self.assertTrue(apply_payload["ok"])
            self.assertTrue(apply_payload["data"]["applied"])
            self.assertEqual(apply_payload["data"]["candidate_command"], "completed.reconcile_manifest")
            self.assertEqual(apply_payload["data"]["selected_row_keys"], [row_key])
            self.assertEqual(apply_payload["data"]["written_paths"], [str(manifest)])
            self.assertEqual(backup_path.name, manifest.name)
            self.assertTrue(backup_path.exists())
            self.assertEqual(json.loads(backup_path.read_text(encoding="utf-8")), manifest_payload)
            self.assertNotEqual(_file_state(manifest), manifest_before)
            self.assertEqual(repaired["source_path"], str(files["source"]))
            self.assertEqual(repaired["output_path"], str(files["output"]))
            self.assertEqual(repaired["output_file"], files["output"].name)
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertEqual(_file_state(files["sidecar"]), sidecar_before)
            self.assertTrue(apply_payload["data"]["source_payload_output_unchanged"])
            self.assertEqual(len(commands["entries"]), 1)
            self.assertEqual(commands["entries"][0]["command"], "completed.reconcile_manifest")
            self.assertFalse(any("drain" in str(entry.get("command", "")).lower() for entry in commands["entries"]))

    def test_local_api_pending_manifest_apply_is_journaled_without_draining_or_touching_media(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _pending_fixture(root, repairable_manifest=True)
            manifest = files["pending_manifest"]
            drain_summary = resolved.state_root / "Progress" / "pending_drain_summary.json"
            drain_summary.parent.mkdir(parents=True, exist_ok=True)
            drain_summary.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_drain_summary.v1",
                        "status": "completed",
                        "items": [
                            {
                                "status": "succeeded",
                                "local_file": str(root / "OtherPending" / "AlreadyDrained.mkv"),
                                "server_out": str(root / "Outsource" / "AlreadyDrained.mkv"),
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            source_before = _file_state(files["source"])
            output_before = _file_state(files["output"])
            payload_before = _file_state(files["pending_payload"])
            manifest_before = _file_state(manifest)
            drain_summary_before = _file_state(drain_summary)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            preview = facade.get_pending_publish_preview(resolved).to_mapping()
            row_key = next(row["row_key"] for row in preview["rows"] if row.get("diagnostic_status") == "invalid_manifest")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                dry_run_request = Request(
                    f"{server.url}/api/pending-publish/repair-manifest-dry-run",
                    data=json.dumps({"scope": "selected", "row_key": row_key, "reason": "normalize pending manifest"}).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(dry_run_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    dry_run_payload = json.loads(response.read().decode("utf-8"))
                apply_request = Request(
                    f"{server.url}/api/pending-publish/repair-manifest",
                    data=json.dumps(_apply_request(dry_run_payload["data"], reason="normalize pending manifest only")).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(apply_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    apply_payload = json.loads(response.read().decode("utf-8"))
                pending_request = Request(
                    f"{server.url}/api/pending-publish",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(pending_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_payload = json.loads(response.read().decode("utf-8"))
                commands_request = Request(
                    f"{server.url}/api/commands?limit=10",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(commands_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    commands = json.loads(response.read().decode("utf-8"))
            finally:
                server.stop()

            repaired = json.loads(manifest.read_text(encoding="utf-8"))
            backup_path = Path(apply_payload["data"]["backup_paths"][0])
            self.assertTrue(dry_run_payload["ok"])
            self.assertTrue(dry_run_payload["data"]["safe_to_apply"])
            self.assertTrue(dry_run_payload["data"]["suppress_command_journal"])
            self.assertTrue(apply_payload["ok"])
            self.assertTrue(apply_payload["data"]["applied"])
            self.assertEqual(apply_payload["data"]["candidate_command"], "pending_publish.repair_manifest")
            self.assertEqual(apply_payload["data"]["written_paths"], [str(manifest)])
            self.assertEqual(backup_path.name, manifest.name)
            self.assertTrue(backup_path.exists())
            self.assertNotEqual(_file_state(manifest), manifest_before)
            PendingPushManifest.from_mapping(repaired)
            self.assertEqual(repaired["local_file"], str(files["pending_payload"]))
            self.assertEqual(repaired["server_out"], str(files["output"]))
            self.assertEqual(repaired["source_path"], str(files["source"]))
            self.assertEqual(repaired["output_size"], files["pending_payload"].stat().st_size)
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertEqual(_file_state(files["pending_payload"]), payload_before)
            self.assertEqual(_file_state(drain_summary), drain_summary_before)
            self.assertTrue(apply_payload["data"]["source_payload_output_unchanged"])
            self.assertEqual(len(commands["entries"]), 1)
            self.assertEqual(commands["entries"][0]["command"], "pending_publish.repair_manifest")
            self.assertFalse(any("drain" in str(entry.get("command", "")).lower() for entry in commands["entries"]))
            pending_row = pending_payload["rows"][0]
            self.assertEqual(pending_row["state"], "parked")
            self.assertEqual(pending_row["diagnostic_status"], "ready")
            self.assertTrue(pending_row["ready_to_drain"])
            self.assertEqual(pending_row["drain_recommendation"], "ready_to_drain")
            self.assertTrue(pending_payload["drain_summary"]["exists"])
            self.assertEqual(pending_payload["drain_summary"]["path"], str(drain_summary))

    def test_local_api_orphan_apply_is_journaled_without_draining_or_touching_media(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _pending_fixture(root, orphan_payload=True)
            manifest = Path(str(files["pending_payload"]) + ".manifest.json")
            drain_summary = resolved.state_root / "Progress" / "pending_drain_summary.json"
            drain_summary.parent.mkdir(parents=True, exist_ok=True)
            drain_summary.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_drain_summary.v1",
                        "status": "completed",
                        "items": [
                            {
                                "status": "succeeded",
                                "local_file": str(root / "OtherPending" / "AlreadyDrained.mkv"),
                                "server_out": str(root / "Outsource" / "AlreadyDrained.mkv"),
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            source_before = _file_state(files["source"])
            output_before = _file_state(files["output"])
            payload_before = _file_state(files["pending_payload"])
            manifest_before = _file_state(manifest)
            drain_summary_before = _file_state(drain_summary)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            original_get_pending_publish_preview = facade.get_pending_publish_preview
            preview = facade.get_pending_publish_preview(resolved).to_mapping()
            row = preview["rows"][0]
            row["backend_manifest_proposal"] = _pending_manifest_payload(files["pending_payload"], files["output"], files["source"])
            facade.get_pending_publish_preview = lambda _resolved: SimpleNamespace(to_mapping=lambda: preview)  # type: ignore[method-assign]
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                dry_run_request = Request(
                    f"{server.url}/api/pending-publish/reconcile-orphan-payloads-dry-run",
                    data=json.dumps({"scope": "selected", "row_key": row["row_key"]}).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(dry_run_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    dry_run_payload = json.loads(response.read().decode("utf-8"))
                apply_request = Request(
                    f"{server.url}/api/pending-publish/reconcile-orphan-payloads",
                    data=json.dumps(_apply_request(dry_run_payload["data"], reason="recover pending manifest only")).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(apply_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    apply_payload = json.loads(response.read().decode("utf-8"))
                facade.get_pending_publish_preview = original_get_pending_publish_preview  # type: ignore[method-assign]
                pending_request = Request(
                    f"{server.url}/api/pending-publish",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(pending_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_payload = json.loads(response.read().decode("utf-8"))
                commands_request = Request(
                    f"{server.url}/api/commands?limit=10",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(commands_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    commands = json.loads(response.read().decode("utf-8"))
            finally:
                facade.get_pending_publish_preview = original_get_pending_publish_preview  # type: ignore[method-assign]
                server.stop()

            written = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(dry_run_payload["ok"])
            self.assertTrue(dry_run_payload["data"]["safe_to_apply"])
            self.assertTrue(dry_run_payload["data"]["suppress_command_journal"])
            self.assertTrue(apply_payload["ok"])
            self.assertTrue(apply_payload["data"]["applied"])
            self.assertEqual(apply_payload["data"]["candidate_command"], "pending_publish.reconcile_orphan_payloads")
            self.assertEqual(apply_payload["data"]["written_paths"], [str(manifest)])
            self.assertEqual(apply_payload["data"]["backup_paths"], [])
            self.assertEqual(manifest_before, {"exists": False})
            PendingPushManifest.from_mapping(written)
            self.assertEqual(written["local_file"], str(files["pending_payload"]))
            self.assertEqual(written["server_out"], str(files["output"]))
            self.assertEqual(written["source_path"], str(files["source"]))
            self.assertEqual(_file_state(files["source"]), source_before)
            self.assertEqual(_file_state(files["output"]), output_before)
            self.assertEqual(_file_state(files["pending_payload"]), payload_before)
            self.assertEqual(_file_state(drain_summary), drain_summary_before)
            self.assertTrue(apply_payload["data"]["source_payload_output_unchanged"])
            self.assertEqual(len(commands["entries"]), 1)
            self.assertEqual(commands["entries"][0]["command"], "pending_publish.reconcile_orphan_payloads")
            self.assertFalse(any("drain" in str(entry.get("command", "")).lower() for entry in commands["entries"]))
            pending_row = pending_payload["rows"][0]
            self.assertEqual(pending_row["state"], "parked")
            self.assertEqual(pending_row["diagnostic_status"], "ready")
            self.assertTrue(pending_row["ready_to_drain"])
            self.assertEqual(pending_row["drain_recommendation"], "ready_to_drain")
            self.assertTrue(pending_payload["drain_summary"]["exists"])
            self.assertEqual(pending_payload["drain_summary"]["path"], str(drain_summary))

    def test_local_api_validation_rejects_unknown_apply_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _files = _completed_fixture(root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                request = Request(
                    f"{server.url}/api/completed/repair-sidecar-metadata",
                    data=json.dumps(
                        {
                            "scope": "selected",
                            "row_key": "row-1",
                            "limit": 1,
                            "reason": "bad",
                            "dry_run_fingerprint": "abc",
                            "confirm_apply": True,
                            "path": "C:/Media/Movie.mkv",
                        }
                    ).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=5)  # noqa: S310 - localhost test server
            finally:
                server.stop()

        self.assertEqual(raised.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
