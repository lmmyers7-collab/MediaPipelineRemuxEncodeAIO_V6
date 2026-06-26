from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.application_facade_test_support import DummyFacadeService


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _retention_resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    state_root = local_base / "State"
    source_movies = root / "Movies"
    source_tv = root / "TV"
    outsource = root / "Outsource"
    resolved = ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
        local_base=local_base,
        state_root=state_root,
        active_jobs_path=state_root / "ActiveJobs",
        source_movies=source_movies,
        source_tv=source_tv,
        log_file=local_base / "pipeline_debug.log",
        progress_file=state_root / "Progress" / "pipeline_progress.json",
        event_file=state_root / "Progress" / "pipeline_events.jsonl",
        failed_reports_path=state_root / "Failures" / "Reports",
        failed_markers_path=state_root / "Failures" / "Markers",
        pending_push_path=state_root / "PendingServerPush",
        completed_manifest_path=state_root / "Completed" / "completed_jobs.jsonl",
        config_data={
            "LocalBase": str(local_base),
            "SourceMovies": str(source_movies),
            "SourceTV": str(source_tv),
            "Outsource": str(outsource),
        },
    )
    return resolved


class MaintenanceRetentionDryRunTests(unittest.TestCase):
    def test_retention_dry_run_reports_only_allowlisted_runtime_candidates_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _retention_resolved(root)
            assert resolved.local_base is not None
            assert resolved.state_root is not None
            assert resolved.pending_push_path is not None
            source_movie = resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
            pending_payload = resolved.pending_push_path / "parked.mkv"
            outsource_file = Path(resolved.config_data["Outsource"]) / "Movie.mkv"
            runtime_files = {
                "log": resolved.log_file,
                "events": resolved.event_file,
                "completed_manifest": resolved.completed_manifest_path,
                "failure_report": resolved.failed_reports_path / "failure.json",  # type: ignore[operator]
                "temp_orphan": resolved.local_base / "Temp" / "orphan.tmp",
                "cache_artifact": resolved.local_base / "Cache" / "probe-cache.bin",
            }
            for index, path in enumerate(runtime_files.values(), start=1):
                _write_bytes(path, f"runtime-{index}".encode("ascii"))
            _write_bytes(source_movie, b"source-media")
            _write_bytes(pending_payload, b"parked-output")
            _write_bytes(outsource_file, b"final-output")
            before = {path: path.read_bytes() for path in [*runtime_files.values(), source_movie, pending_payload, outsource_file]}

            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            result = facade.run_retention_dry_run(resolved, {"limit": 100, "reason": "7-day soak prep"}).to_mapping()

            after = {path: path.read_bytes() for path in before}

        self.assertEqual(before, after)
        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "maintenance.retention_dry_run")
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        data = result["data"]
        self.assertEqual(data["schema_version"], "desktop_retention_dry_run.v1")
        self.assertTrue(data["dry_run_only"])
        self.assertEqual(data["effect"], "none")
        self.assertEqual(data["would_delete_paths"], [])
        self.assertEqual(data["would_move_paths"], [])
        self.assertEqual(data["would_write_paths"], [])
        self.assertTrue(data["suppress_command_journal"])
        self.assertFalse(data["mutation_route_available"])
        self.assertFalse(data["safe_to_apply"])
        self.assertEqual(data["request_summary"]["limit"], 100)
        self.assertTrue(data["request_summary"]["reason_present"])
        candidates = data["candidates"]
        candidate_paths = {Path(row["path"]) for row in candidates}
        self.assertEqual(candidate_paths, set(runtime_files.values()))
        for row in candidates:
            candidate_path = Path(row["path"])
            self.assertTrue(row["cleanup_eligible"], row)
            self.assertFalse(row["would_delete"], row)
            self.assertTrue(candidate_path.is_relative_to(resolved.local_base) or candidate_path.is_relative_to(resolved.state_root))
            self.assertFalse(candidate_path.is_relative_to(resolved.source_movies))
            self.assertFalse(candidate_path.is_relative_to(resolved.source_tv))
            self.assertFalse(candidate_path.is_relative_to(resolved.pending_push_path))
            self.assertFalse(candidate_path.is_relative_to(Path(resolved.config_data["Outsource"])))
        categories = data["categories"]
        self.assertEqual(categories["logs"]["candidate_count"], 1)
        self.assertEqual(categories["jsonl_state"]["candidate_count"], 2)
        self.assertEqual(categories["failure_reports"]["candidate_count"], 1)
        self.assertEqual(categories["temp_scratch_orphans"]["candidate_count"], 1)
        self.assertEqual(categories["cache_artifacts"]["candidate_count"], 1)
        exclusions = {Path(row["path"]): row for row in data["guardrail_exclusions"]}
        self.assertIn(resolved.source_movies, exclusions)
        self.assertIn(resolved.source_tv, exclusions)
        self.assertIn(resolved.pending_push_path, exclusions)
        self.assertIn(Path(resolved.config_data["Outsource"]), exclusions)
        for row in exclusions.values():
            self.assertFalse(row["cleanup_eligible"], row)
            self.assertFalse(row["would_delete"], row)
        self.assertIn("source_media", data["would_not_touch"])
        self.assertIn("pending_publish", data["would_not_touch"])
        self.assertIn("final_output", data["would_not_touch"])

    def test_retention_dry_run_local_api_is_authenticated_read_only_and_unjournaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _retention_resolved(root)
            assert resolved.log_file is not None
            _write_bytes(resolved.log_file, b"log")
            before_log = resolved.log_file.read_bytes()
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="retention-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                unauth_status, unauth_payload = self._post_json(f"{server.url}/api/maintenance/retention-dry-run", {})
                status, payload = self._post_json(
                    f"{server.url}/api/maintenance/retention-dry-run",
                    {"limit": 25, "reason": "external poll"},
                    token="retention-token",
                )
                history_status, history = self._get_json(f"{server.url}/api/commands?limit=5", token="retention-token")
            finally:
                server.stop()
            after_log = resolved.log_file.read_bytes()

        self.assertEqual(before_log, after_log)
        self.assertEqual(unauth_status, 401)
        self.assertEqual(unauth_payload["error"], "unauthorized")
        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "maintenance.retention_dry_run")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["schema_version"], "desktop_retention_dry_run.v1")
        self.assertEqual(payload["data"]["would_delete_paths"], [])
        self.assertTrue(payload["data"]["suppress_command_journal"])
        self.assertEqual(history_status, 200)
        self.assertNotIn("maintenance.retention_dry_run", [entry["command"] for entry in history["entries"]])

    def _post_json(self, url: str, payload: dict[str, object], token: str | None = None) -> tuple[int, dict[str, object]]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _get_json(self, url: str, token: str | None = None) -> tuple[int, dict[str, object]]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
