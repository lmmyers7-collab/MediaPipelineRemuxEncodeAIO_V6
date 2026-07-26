from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .application_facade_test_support import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
except ImportError:  # pragma: no cover - fallback for direct test execution
    from application_facade_test_support import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state


def _get_json(url: str, token: str | None = None) -> tuple[int, dict[str, object]]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, object], token: str | None = None) -> tuple[int, dict[str, object]]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class LocalApiMaintenanceDryRunContractSmoke(unittest.TestCase):
    def test_maintenance_dry_run_routes_execute_against_temp_state_without_media_or_manifest_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, source, output = _write_fixture_state(root)
            self.assertIsInstance(resolved, ResolvedPaths)
            completed_manifest = resolved.completed_manifest_path
            self.assertIsNotNone(completed_manifest)
            before_manifest = Path(completed_manifest).read_text(encoding="utf-8")
            before_source_bytes = source.read_bytes()
            before_output_bytes = output.read_bytes()
            deploy_root = root / "DeployableDryRun"
            backfill_calls: list[dict[str, object]] = []

            service = DummyWorkflowFacadeService(root)

            def fake_backfill(resolved_arg: ResolvedPaths, **kwargs: object) -> tuple[bool, str]:
                backfill_calls.append({"resolved": resolved_arg, **kwargs})
                return (
                    True,
                    "\n".join(
                        [
                            "Backfill dry run complete.",
                            "  Sidecars ingested : 4",
                            "  Skipped (bad JSON): 0",
                            f"  Manifest          : {resolved_arg.completed_manifest_path}",
                        ]
                    ),
                )

            service.backfill_completed_manifest = fake_backfill  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="maintenance-dry-run-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                unauth_release_status, unauth_release = _post_json(
                    f"{server.url}/api/maintenance/release-dry-run",
                    {"destination_root": str(deploy_root)},
                )
                unauth_backfill_status, unauth_backfill = _post_json(
                    f"{server.url}/api/maintenance/completed-backfill-dry-run",
                    {},
                )
                maintenance_status, maintenance = _get_json(
                    f"{server.url}/api/maintenance",
                    token="maintenance-dry-run-token",
                )
                release_status, release = _post_json(
                    f"{server.url}/api/maintenance/release-dry-run",
                    {
                        "destination_root": str(deploy_root),
                        "zip_package": True,
                        "verify": True,
                        "include_optional_tools": True,
                        "force": True,
                        "timeout_seconds": 99999,
                    },
                    token="maintenance-dry-run-token",
                )
                backfill_status, backfill = _post_json(
                    f"{server.url}/api/maintenance/completed-backfill-dry-run",
                    {"timeout_seconds": 99999},
                    token="maintenance-dry-run-token",
                )
                retention_status, retention = _post_json(
                    f"{server.url}/api/maintenance/retention-dry-run",
                    {"limit": 25, "reason": "maintenance smoke"},
                    token="maintenance-dry-run-token",
                )
                history_status, history = _get_json(
                    f"{server.url}/api/commands?limit=10",
                    token="maintenance-dry-run-token",
                )
            finally:
                server.stop()
            after_manifest = Path(completed_manifest).read_text(encoding="utf-8")
            after_source_bytes = source.read_bytes()
            after_output_bytes = output.read_bytes()
            deploy_root_exists = deploy_root.exists()
            deploy_zip_exists = Path(str(deploy_root) + ".zip").exists()

        self.assertEqual(unauth_release_status, 401)
        self.assertEqual(unauth_release["error"], "unauthorized")
        self.assertEqual(unauth_backfill_status, 401)
        self.assertEqual(unauth_backfill["error"], "unauthorized")
        self.assertEqual(maintenance_status, 200)
        self.assertEqual(maintenance["schema_version"], "desktop_maintenance_workspace.v1")

        self.assertEqual(release_status, 200)
        self.assertEqual(release["schema_version"], "desktop_command_result.v1")
        self.assertEqual(release["command"], "maintenance.release_dry_run")
        self.assertTrue(release["ok"])
        release_data = release["data"]
        self.assertIsInstance(release_data, dict)
        self.assertTrue(release_data["dry_run"])
        self.assertFalse(release_data["manifest_exists"])
        self.assertFalse(release_data["zip_exists"])
        self.assertEqual(release_data["returncode"], 0)
        self.assertEqual(release_data["options"]["verify"], True)
        self.assertEqual(release_data["options"]["include_tests"], True)
        self.assertEqual(release_data["options"]["include_tauri_preview_binary"], False)
        self.assertEqual(release_data["options"]["include_optional_tools"], True)
        self.assertEqual(release_data["options"]["force"], True)
        self.assertEqual(service.release_build_calls[-1]["destination_root"], str(deploy_root))
        self.assertEqual(service.release_build_calls[-1]["dry_run"], True)
        self.assertEqual(service.release_build_calls[-1]["verify"], True)
        self.assertEqual(service.release_build_calls[-1]["include_tests"], True)
        self.assertEqual(service.release_build_calls[-1]["include_tauri_preview_binary"], False)
        self.assertEqual(service.release_build_calls[-1]["force"], True)
        self.assertEqual(service.release_build_calls[-1]["timeout_seconds"], 1800)
        self.assertFalse(deploy_root_exists)
        self.assertFalse(deploy_zip_exists)

        self.assertEqual(backfill_status, 200)
        self.assertEqual(backfill["schema_version"], "desktop_command_result.v1")
        self.assertEqual(backfill["command"], "maintenance.completed_backfill_dry_run")
        self.assertTrue(backfill["ok"])
        backfill_data = backfill["data"]
        self.assertIsInstance(backfill_data, dict)
        self.assertTrue(backfill_data["dry_run"])
        self.assertFalse(backfill_data["writes_manifest"])
        self.assertEqual(backfill_data["sidecars_ingested"], "4")
        self.assertEqual(backfill_data["skipped_bad_json"], "0")
        self.assertEqual(backfill_data["timeout_seconds"], 1800)
        self.assertEqual(len(backfill_calls), 1)
        self.assertEqual(backfill_calls[0]["dry_run"], True)
        self.assertEqual(backfill_calls[0]["timeout_seconds"], 1800.0)
        checkpoint_path = Path(str(backfill_calls[0]["checkpoint_path"]))
        self.assertEqual(checkpoint_path.parent, root / "RunLogs")

        self.assertEqual(retention_status, 200)
        self.assertEqual(retention["schema_version"], "desktop_command_result.v1")
        self.assertEqual(retention["command"], "maintenance.retention_dry_run")
        self.assertTrue(retention["ok"])
        retention_data = retention["data"]
        self.assertIsInstance(retention_data, dict)
        self.assertEqual(retention_data["schema_version"], "desktop_retention_dry_run.v1")
        self.assertTrue(retention_data["dry_run_only"])
        self.assertEqual(retention_data["effect"], "none")
        self.assertEqual(retention_data["would_delete_paths"], [])
        self.assertEqual(retention_data["would_move_paths"], [])
        self.assertEqual(retention_data["would_write_paths"], [])
        self.assertTrue(retention_data["suppress_command_journal"])

        self.assertEqual(after_manifest, before_manifest)
        self.assertEqual(after_source_bytes, before_source_bytes)
        self.assertEqual(after_output_bytes, before_output_bytes)

        self.assertEqual(history_status, 200)
        self.assertEqual(history["schema_version"], "desktop_command_history.v1")
        commands = [entry["command"] for entry in history["entries"]]
        self.assertIn("maintenance.release_dry_run", commands)
        self.assertIn("maintenance.completed_backfill_dry_run", commands)
        self.assertNotIn("maintenance.retention_dry_run", commands)


if __name__ == "__main__":
    unittest.main()
