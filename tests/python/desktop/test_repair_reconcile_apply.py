from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.validation.boundary import ValidationFailure, validate_api_payload
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.test_application_facade import DummyWorkflowFacadeService
from tests.python.desktop.test_repair_reconcile_dry_run import _completed_fixture, _file_state, _pending_fixture


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

    def test_orphan_payload_reconcile_apply_is_manifest_only_and_blocks_incomplete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _pending_fixture(root, orphan_payload=True)
            before = _file_state(files["pending_payload"])
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            row_key = facade.get_pending_publish_preview(resolved).to_mapping()["rows"][0]["row_key"]

            result = facade.apply_repair_reconcile(
                resolved,
                candidate_command="pending_publish.reconcile_orphan_payloads",
                request={
                    "scope": "selected",
                    "row_key": row_key,
                    "limit": 100,
                    "reason": "manifest only",
                    "dry_run_fingerprint": "bad-fingerprint",
                    "confirm_apply": True,
                },
            ).to_mapping()

            self.assertFalse(result["ok"])
            self.assertFalse(result["data"]["applied"])
            self.assertFalse(result["data"]["written_paths"])
            self.assertFalse((files["pending_payload"].with_suffix(files["pending_payload"].suffix + ".manifest.json")).exists())
            self.assertEqual(_file_state(files["pending_payload"]), before)

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

    def test_local_api_confirmed_apply_is_journaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _files = _completed_fixture(root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            row_key = facade.get_completed_preview(resolved).to_mapping()["rows"][0]["row_key"]
            dry_run = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="completed.repair_sidecar_metadata",
                request={"scope": "selected", "row_key": row_key},
            ).to_mapping()["data"]
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                request = Request(
                    f"{server.url}/api/completed/repair-sidecar-metadata",
                    data=json.dumps(_apply_request(dry_run)).encode("utf-8"),
                    headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                    payload = json.loads(response.read().decode("utf-8"))
                commands_request = Request(
                    f"{server.url}/api/commands?limit=10",
                    headers={"Authorization": "Bearer test-token"},
                )
                with urlopen(commands_request, timeout=5) as response:  # noqa: S310 - localhost test server
                    commands = json.loads(response.read().decode("utf-8"))
            finally:
                server.stop()

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["applied"])
        self.assertEqual(len(commands["entries"]), 1)
        self.assertEqual(commands["entries"][0]["command"], "completed.repair_sidecar_metadata")

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
