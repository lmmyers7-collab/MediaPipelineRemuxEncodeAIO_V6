from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.contracts.api_commands import validate_api_command_payload  # noqa: E402
from mediapipeline.core.maintenance.productization import (  # noqa: E402
    PRODUCTIZATION_STATUS_SCHEMA_VERSION,
    SUPPORT_EXPORT_SCHEMA_VERSION,
    productization_status_payload,
    write_support_export,
)
from mediapipeline.core.validation.boundary import ValidationFailure, validate_api_payload  # noqa: E402
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT  # noqa: E402
from mediapipeline.desktop.api.routes_read import GET_ROUTE_HANDLERS  # noqa: E402
from mediapipeline.desktop.models import ResolvedPaths  # noqa: E402


class DummyProductizationService:
    def __init__(self, root: Path) -> None:
        self.app_root = root / "apps" / "desktop"
        self.workspace_root = root
        self.desktop_log_path = root / "RunLogs" / "desktop.log"
        self.logger = None


def _resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    return ResolvedPaths(
        app_root=root / "apps" / "desktop",
        workspace_root=root,
        pipeline_path=root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
        config_path=root / "ops" / "pipeline" / "config" / "MediaPipeline_config.psd1",
        audit_script_path=root / "ops" / "pipeline" / "entrypoints" / "Audit.ps1",
        rerun_script_path=root / "ops" / "pipeline" / "entrypoints" / "Rerun.ps1",
        powershell_host=None,
        local_base=local_base,
        state_root=local_base / "State",
        app_state_path=local_base / "State" / "App" / "desktop_app_state.json",
        log_file=local_base / "pipeline_debug.log",
        config_data={
            "LocalBase": str(local_base),
            "SourceMovies": str(root / "SourceMovies"),
            "WorkerAuthToken": "secret-token",
            "LibraryProfiles": {"movies": {"source": str(root / "SourceMovies")}},
        },
    )


class ProductizationSupportTests(unittest.TestCase):
    def test_productization_routes_are_backend_contract_routes(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        self.assertEqual(
            GET_ROUTE_HANDLERS["/api/maintenance/productization"].method_name,
            "_maintenance_productization_payload",
        )
        self.assertEqual(routes["/api/maintenance/productization"]["response_schema"], PRODUCTIZATION_STATUS_SCHEMA_VERSION)
        self.assertEqual(routes["/api/maintenance/productization"]["effect"], "none")
        self.assertEqual(routes["/api/maintenance/support-export"]["data_schema"], SUPPORT_EXPORT_SCHEMA_VERSION)
        self.assertEqual(routes["/api/maintenance/support-export"]["effect"], "diagnostics-artifact-write")

    def test_support_export_payload_contract_is_strict(self) -> None:
        payload = {"reason": "operator support", "include_recent_logs": True, "max_log_bytes": 32768}

        self.assertEqual(validate_api_command_payload("/api/maintenance/support-export", payload), payload)
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/maintenance/support-export", {**payload, "path": r"C:\Media\Movie.mkv"})
        with self.assertRaises(ValidationFailure):
            validate_api_payload("/api/maintenance/support-export", {**payload, "include_recent_logs": "true"})

    def test_productization_status_reports_nsis_prompted_updates_and_appdata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            appdata = root / "AppData"
            service = DummyProductizationService(root)
            resolved = _resolved(root)
            with patch.dict(
                os.environ,
                {
                    "MEDIAPIPELINE_APPDATA_ROOT": str(appdata),
                    "MEDIAPIPELINE_PRODUCTIZED_APP": "1",
                    "MEDIAPIPELINE_RELEASE_CHANNEL": "beta",
                },
                clear=False,
            ):
                payload = productization_status_payload(
                    service=service,
                    resolved=resolved,
                    app_version="2026.06.04.001",
                    close_readiness={"schema_version": "desktop_close_readiness.v1", "safe_to_close": True},
                )

        self.assertEqual(payload["schema_version"], PRODUCTIZATION_STATUS_SCHEMA_VERSION)
        self.assertEqual(payload["installer"]["target"], "nsis")
        self.assertFalse(payload["installer"]["msi_enabled"])
        self.assertEqual(payload["updater"]["mode"], "prompted")
        self.assertEqual(payload["updater"]["active_channel"], "beta")
        self.assertTrue(payload["runtime_roots"]["appdata_available"])
        self.assertTrue(payload["migration"]["guarded_import_runs_in_productized_mode"])
        self.assertFalse(payload["migration"]["writes_media"])

    def test_support_export_redacts_paths_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            appdata = root / "AppData"
            service = DummyProductizationService(root)
            resolved = _resolved(root)
            service.desktop_log_path.parent.mkdir(parents=True)
            service.desktop_log_path.write_text(
                f"opened {root}\\SourceMovies\\Movie.mkv token=secret-token\n",
                encoding="utf-8",
            )
            resolved.local_base.mkdir(parents=True)
            resolved.log_file.write_text(
                f"Authorization: Bearer secret-token path={root}\\LocalBase\\pipeline_debug.log\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "MEDIAPIPELINE_APPDATA_ROOT": str(appdata),
                    "MEDIAPIPELINE_PRODUCTIZED_APP": "1",
                },
                clear=False,
            ):
                result = write_support_export(
                    service=service,
                    resolved=resolved,
                    app_version="2026.06.04.001",
                    request={"reason": "operator token=secret-token", "include_recent_logs": True},
                    close_readiness={"schema_version": "desktop_close_readiness.v1", "safe_to_close": True},
                ).to_mapping()

            export_path = Path(result["data"]["export_path"])
            payload_text = export_path.read_text(encoding="utf-8")
            payload = json.loads(payload_text)

        self.assertTrue(result["ok"])
        self.assertEqual(payload["schema_version"], SUPPORT_EXPORT_SCHEMA_VERSION)
        self.assertTrue(payload["redaction"]["personal_paths_redacted"])
        self.assertTrue(payload["redaction"]["secrets_redacted"])
        self.assertFalse(payload["redaction"]["full_config_included"])
        self.assertNotIn(str(root), payload_text)
        self.assertNotIn("secret-token", payload_text)
        self.assertIn("<redacted>", payload_text)
        self.assertFalse(payload["media_safety"]["support_export_writes_media"])
        self.assertFalse(payload["media_safety"]["support_export_deletes_media"])


if __name__ == "__main__":
    unittest.main()
