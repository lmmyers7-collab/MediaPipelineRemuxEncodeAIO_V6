from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.audit.sources import (
    AuditSourceMetricsServiceMixin,
    audit_source_state_payload,
    scan_audit_sources,
    sync_audit_sources_from_completed_audit,
    update_audit_sources,
)
from mediapipeline.contracts.api_commands import validate_api_command_payload
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.routes import GET_ROUTE_HANDLERS, POST_ROUTE_HANDLERS
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.application_facade_test_support import LocalApiHttpTestMixin


class _AuditSourceSyncLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def info(self, message: object, *args: object, **_kwargs: object) -> None:
        self.infos.append(str(message) % args if args else str(message))

    def warning(self, message: object, *args: object, **_kwargs: object) -> None:
        self.warnings.append(str(message) % args if args else str(message))


class _AuditSourceSyncService(AuditSourceMetricsServiceMixin):
    def __init__(self) -> None:
        self.logger = _AuditSourceSyncLogger()


class _AuditProc:
    pid = 12345


def _resolved(root: Path, *, with_state: bool = True) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
        state_root=(root / "State") if with_state else None,
        local_base=None,
        config_data={"NetworkRole": "standalone"},
    )


class AuditSourcesTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_audit_source_payload_reports_missing_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            payload = audit_source_state_payload(_resolved(Path(raw_root), with_state=False))

        self.assertFalse(payload["available"])
        self.assertEqual(payload["schema_version"], "desktop_audit_sources.v1")
        self.assertIn("state_root is not configured", payload["warnings"][0])

    def test_audit_source_scan_counts_media_sidecars_and_folders(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_a = root / "DriveA"
            source_b = root / "DriveB"
            (source_a / "Movies").mkdir(parents=True)
            (source_b / "Shows" / "Season 01").mkdir(parents=True)
            (source_a / "Movies" / "Movie.mkv").write_bytes(b"movie")
            (source_a / "Movies" / "Movie.en.srt").write_text("subtitle", encoding="utf-8")
            (source_a / "Movies" / "Movie.pipeline.json").write_text("{}", encoding="utf-8")
            (source_b / "Shows" / "Season 01" / "Episode.mp4").write_bytes(b"episode")
            (source_b / "Shows" / "Season 01" / "Episode.ass").write_text("ass", encoding="utf-8")
            resolved = _resolved(root)

            add_a = update_audit_sources(resolved, {"action": "add", "path": str(source_a)})
            add_b = update_audit_sources(resolved, {"action": "add", "path": str(source_b)})
            self.assertTrue(add_a["ok"])
            self.assertTrue(add_b["ok"])

            state = audit_source_state_payload(resolved)
            source_ids = [row["source_id"] for row in state["roots"]]
            scan = scan_audit_sources(resolved, {"source_ids": source_ids})

            self.assertTrue(scan["ok"])
            scanned = scan["data"]["audit_sources"]
            self.assertEqual(scanned["source_count"], 2)
            self.assertEqual(scanned["media_file_count"], 2)
            self.assertEqual(scanned["sidecar_file_count"], 3)
            self.assertEqual(scanned["folder_count"], 5)
            self.assertFalse(scanned["counts_truncated"])
            by_path = {row["path"]: row for row in scanned["roots"]}
            self.assertEqual(by_path[str(source_a)]["media_file_count"], 1)
            self.assertEqual(by_path[str(source_a)]["sidecar_file_count"], 2)
            self.assertEqual(by_path[str(source_b)]["folder_count"], 3)

    def test_completed_audit_sync_updates_selected_source_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_a = root / "DriveA"
            source_b = root / "DriveB"
            (source_a / "Movies").mkdir(parents=True)
            (source_b / "Shows" / "Season 01").mkdir(parents=True)
            (source_a / "Movies" / "Movie.mkv").write_bytes(b"movie")
            (source_b / "Shows" / "Season 01" / "Episode.mp4").write_bytes(b"episode")
            (source_b / "Shows" / "Season 01" / "Episode.pipeline.json").write_text("{}", encoding="utf-8")
            resolved = _resolved(root)

            self.assertTrue(update_audit_sources(resolved, {"action": "add", "path": str(source_a)})["ok"])
            self.assertTrue(update_audit_sources(resolved, {"action": "add", "path": str(source_b)})["ok"])

            result = sync_audit_sources_from_completed_audit(
                resolved,
                metadata={"library_roots": [str(source_b)]},
            )

            self.assertTrue(result["ok"])
            by_path = {row["path"]: row for row in result["data"]["audit_sources"]["roots"]}
            self.assertEqual(by_path[str(source_a)]["scan_status"], "not_scanned")
            self.assertEqual(by_path[str(source_a)]["media_file_count"], 0)
            self.assertEqual(by_path[str(source_b)]["scan_status"], "complete")
            self.assertEqual(by_path[str(source_b)]["media_file_count"], 1)
            self.assertEqual(by_path[str(source_b)]["sidecar_file_count"], 1)
            self.assertEqual(by_path[str(source_b)]["folder_count"], 3)

    def test_audit_completion_service_hook_syncs_source_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Library"
            source.mkdir()
            (source / "Clip.mkv").write_bytes(b"clip")
            resolved = _resolved(root)
            self.assertTrue(update_audit_sources(resolved, {"action": "add", "path": str(source)})["ok"])

            service = _AuditSourceSyncService()
            service.sync_audit_sources_after_process_exit(
                _AuditProc(),
                resolved=resolved,
                job_kind="audit",
                return_code=0,
                metadata={"library_roots": [str(source)]},
            )

            state = audit_source_state_payload(resolved)
            self.assertEqual(state["media_file_count"], 1)
            self.assertEqual(state["roots"][0]["scan_status"], "complete")
            self.assertTrue(service.logger.infos)
            self.assertFalse(service.logger.warnings)

    def test_audit_source_routes_are_registered_and_validated(self) -> None:
        self.assertIn("/api/audit-sources", GET_ROUTE_HANDLERS)
        self.assertEqual(GET_ROUTE_HANDLERS["/api/audit-sources"].method_name, "_audit_sources_payload")
        self.assertIn("/api/audit/sources", POST_ROUTE_HANDLERS)
        self.assertIn("/api/audit/sources/scan", POST_ROUTE_HANDLERS)
        self.assertEqual(POST_ROUTE_HANDLERS["/api/audit/sources"].method_name, "_audit_sources_command_payload")
        self.assertEqual(POST_ROUTE_HANDLERS["/api/audit/sources/scan"].method_name, "_audit_sources_scan_payload")

        routes = {item["path"]: item for item in LOCAL_API_ROUTE_CONTRACT}
        self.assertEqual(routes["/api/audit-sources"]["response_schema"], "desktop_audit_sources.v1")
        self.assertEqual(routes["/api/audit/sources"]["effect"], "audit-source-state-write")
        self.assertEqual(routes["/api/audit/sources/scan"]["effect"], "audit-source-scan-state-write")
        self.assertIn("does not process", routes["/api/audit/sources/scan"]["purpose"])
        self.assertTrue(validate_api_command_payload("/api/audit/sources", {"action": "add", "path": r"D:\Media"}))
        self.assertTrue(validate_api_command_payload("/api/audit/sources/scan", {"source_ids": ["src_test"]}))

    def test_local_api_post_audit_sources_uses_command_handler(self) -> None:
        source_paths = [
            r"\\LAYNE-SERVER\Users\Layne\Videos\outsource",
            r"\\LAYNE-SERVER\share\Video",
        ]
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            facade = MediaPipelineApplicationFacade(object(), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                results = [
                    self._post_json(
                        f"{server.url}/api/audit/sources",
                        {"action": "add", "path": source_path, "enabled": True},
                        token="test-token",
                    )
                    for source_path in source_paths
                ]
                status, payload = self._get_json(f"{server.url}/api/audit-sources", token="test-token")
            finally:
                server.stop()

        self.assertEqual([item[0] for item in results], [200, 200])
        self.assertTrue(all(item[1]["ok"] for item in results))
        self.assertEqual(status, 200)
        table_paths = [row["path"] for row in payload["roots"]]
        self.assertEqual(table_paths, source_paths)
        self.assertEqual(payload["source_count"], 2)
        self.assertEqual(payload["enabled_source_count"], 2)


if __name__ == "__main__":
    unittest.main()
