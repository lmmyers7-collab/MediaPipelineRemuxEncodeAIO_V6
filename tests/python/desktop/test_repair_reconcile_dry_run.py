from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.kernel.contracts.active_job import ACTIVE_JOB_SCHEMA_VERSION
from mediapipeline.core.kernel.contracts.pending_publish import PENDING_PUSH_MANIFEST_SCHEMA_VERSION
from mediapipeline.core.storage.db import CURRENT_SCHEMA_VERSION, STATE_DB_FILENAME
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.test_application_facade import DummyWorkflowFacadeService, _resolved


REQUIRED_DRY_RUN_FIELDS = {
    "schema_version",
    "candidate_command",
    "dry_run_only",
    "effect",
    "scope",
    "selected_row_keys",
    "precondition_results",
    "diff_summary",
    "would_write_paths",
    "would_move_paths",
    "would_delete_paths",
    "would_not_touch",
    "safe_to_apply",
    "mutation_route_available",
    "operator_confirmation_scope",
    "suppress_command_journal",
}


def _file_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False}
    data = path.read_bytes()
    return {
        "exists": True,
        "mtime_ns": path.stat().st_mtime_ns,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _assert_dry_run_shape(test: unittest.TestCase, data: dict[str, object], candidate_command: str) -> None:
    test.assertEqual(data["schema_version"], "desktop_repair_reconcile_dry_run.v1")
    test.assertEqual(data["candidate_command"], candidate_command)
    test.assertTrue(data["dry_run_only"])
    test.assertEqual(data["effect"], "none")
    test.assertIsInstance(data["mutation_route_available"], bool)
    test.assertIsInstance(data.get("apply_route_available"), bool)
    test.assertIsInstance(data.get("dry_run_fingerprint"), str)
    test.assertTrue(data["suppress_command_journal"])
    test.assertTrue(REQUIRED_DRY_RUN_FIELDS.issubset(data))
    test.assertIsInstance(data["precondition_results"], list)
    test.assertIsInstance(data["diff_summary"], dict)
    test.assertIsInstance(data["would_write_paths"], list)
    test.assertIsInstance(data["would_move_paths"], list)
    test.assertIsInstance(data["would_delete_paths"], list)
    test.assertIsInstance(data["would_not_touch"], dict)


def _assert_startup_reconciliation_shape(test: unittest.TestCase, data: dict[str, object]) -> None:
    test.assertEqual(data["schema_version"], "desktop_startup_reconciliation_dry_run.v1")
    test.assertEqual(data["candidate_command"], "startup.reconcile_state")
    test.assertTrue(data["dry_run_only"])
    test.assertEqual(data["effect"], "none")
    test.assertFalse(data["mutation_route_available"])
    test.assertFalse(data["startup_repair_available"])
    test.assertTrue(data["suppress_command_journal"])
    test.assertFalse(data["safe_to_apply"])
    test.assertEqual(data["would_write_paths"], [])
    test.assertEqual(data["would_move_paths"], [])
    test.assertEqual(data["would_delete_paths"], [])
    test.assertIsInstance(data["precondition_results"], list)
    test.assertIsInstance(data["categories"], dict)
    test.assertIsInstance(data["diff_summary"], dict)
    test.assertIn("pending_manifests", data["categories"])
    test.assertIn("orphaned_parked_outputs", data["categories"])
    test.assertIn("active_jobs", data["categories"])
    test.assertIn("sqlite_mirror", data["categories"])


def _completed_fixture(root: Path, *, missing_sidecar: bool = False) -> tuple[object, dict[str, Path]]:
    source = root / "Source" / "Movie.mkv"
    output = root / "Outsource" / "Movie.mkv"
    sidecar = output.with_suffix(".pipeline.json")
    manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source-bytes")
    output.write_bytes(b"output-bytes")
    if not missing_sidecar:
        sidecar.write_text(
            json.dumps(
                {
                    "source_path": str(root / "Old" / "Movie.mkv"),
                    "output_path": str(root / "Old" / "Movie-output.mkv"),
                    "output_file": "Movie-output.mkv",
                }
            ),
            encoding="utf-8",
        )
    manifest.write_text(
        json.dumps(
            {
                "source_path": str(source),
                "output_path": str(output),
                "output_file": output.name,
                "route": "remux",
                "publish_mode": "deferred",
                "publish_state": "pending",
                "encoded_at": "2026-06-18T08:00:00-04:00",
                "source_size": source.stat().st_size,
                "output_size": output.stat().st_size,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    resolved = _resolved(root)
    resolved.completed_manifest_path = manifest
    return resolved, {
        "source": source,
        "output": output,
        "sidecar": sidecar,
        "completed_manifest": manifest,
    }


def _pending_manifest_payload(payload: Path, destination: Path, source: Path) -> dict[str, object]:
    return {
        "schema_version": PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
        "product_version": "v6-test",
        "pipeline_version": "v6-test",
        "publish_transaction_id": "publish-test-1",
        "manifest_state": "parked",
        "local_file": str(payload),
        "parked_file": str(payload),
        "server_out": str(destination),
        "source_path": str(source),
        "source_identity_v2": "test-source-identity",
        "source_identity_v2_algorithm": "test",
        "route": "remux",
        "publish_mode": "deferred",
        "output_size": payload.stat().st_size,
        "parked_at": "2026-06-18T08:05:00-04:00",
        "sidecar_files": [],
        "tx3g_srt_tracks": [],
        "tx3g_srt_failures": [],
        "bdpgs_srt_failures": [],
        "vobsub_srt_failures": [],
        "tx3g_embedded_srt_tracks": [],
        "bdpgs_embedded_srt_tracks": [],
        "vobsub_embedded_srt_tracks": [],
    }


def _pending_fixture(
    root: Path,
    *,
    unreadable_manifest: bool = False,
    invalid_manifest: bool = False,
    orphan_payload: bool = False,
    duplicate_target: bool = False,
) -> tuple[object, dict[str, Path]]:
    pending_root = root / "PendingServerPush"
    source = root / "Source" / "Movie.mkv"
    output = root / "Outsource" / "Movie.mkv"
    payload = pending_root / "Movie.mkv"
    manifest = pending_root / "Movie.mkv.manifest.json"
    pending_root.mkdir(parents=True, exist_ok=True)
    source.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source-bytes")
    output.write_bytes(b"existing-output")
    payload.write_bytes(b"pending-payload")
    if orphan_payload:
        manifest = pending_root / "missing.manifest.json"
    elif unreadable_manifest:
        manifest.write_text("{not json", encoding="utf-8")
    else:
        manifest_payload = _pending_manifest_payload(payload, output, source)
        if invalid_manifest:
            manifest_payload["manifest_state"] = "unsafe_unknown_state"
        manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
        if duplicate_target:
            duplicate_payload = pending_root / "Movie-copy.mkv"
            duplicate_payload.write_bytes(b"duplicate-payload")
            (pending_root / "Movie-copy.mkv.manifest.json").write_text(
                json.dumps(_pending_manifest_payload(duplicate_payload, output, source)),
                encoding="utf-8",
            )
    resolved = _resolved(root)
    resolved.pending_push_path = pending_root
    resolved.state_root = root / "State"
    return resolved, {
        "source": source,
        "output": output,
        "pending_payload": payload,
        "pending_manifest": manifest,
        "pending_root": pending_root,
    }


def _write_active_job_record(path: Path, *, pid: int | None = None, status: str = "active") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": ACTIVE_JOB_SCHEMA_VERSION,
                "launch_id": path.stem,
                "job_kind": "pipeline",
                "mode": "continuous",
                "status": status,
                "pid": pid,
                "app_pid": 100,
                "command_line": "MediaPipeline.ps1 -Continuous",
                "args": ["MediaPipeline.ps1", "-Continuous"],
                "cwd": str(path.parent.parent),
                "stdout_log": "",
                "stderr_log": "",
                "show_console": False,
                "metadata": {},
                "launched_at": "2026-06-18T08:00:00+00:00",
                "last_update": "2026-06-18T08:00:00+00:00",
                "completed_at": "",
                "return_code": None,
            }
        ),
        encoding="utf-8",
    )


def _write_empty_state_db(state_root: Path) -> Path:
    state_root.mkdir(parents=True, exist_ok=True)
    db_path = state_root / STATE_DB_FILENAME
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        conn.execute(
            """
            CREATE TABLE completed_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                job_key TEXT NOT NULL,
                output_path TEXT NOT NULL,
                sidecar_path TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


class RepairReconcileDryRunTests(unittest.TestCase):
    def test_completed_dry_runs_return_required_schema_and_do_not_mutate_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _completed_fixture(root)
            before = {name: _file_state(path) for name, path in files.items()}
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preview = facade.get_completed_preview(resolved).to_mapping()
            row_key = preview["rows"][0]["row_key"]

            manifest_result = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="completed.reconcile_manifest",
                request={"scope": "selected", "row_key": row_key, "reason": "test"},
            ).to_mapping()
            sidecar_result = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="completed.repair_sidecar_metadata",
                request={"scope": "selected", "row_key": row_key, "reason": "test"},
            ).to_mapping()
            after = {name: _file_state(path) for name, path in files.items()}

        _assert_dry_run_shape(self, manifest_result["data"], "completed.reconcile_manifest")
        _assert_dry_run_shape(self, sidecar_result["data"], "completed.repair_sidecar_metadata")
        self.assertEqual(before, after)
        self.assertFalse(manifest_result["data"]["would_move_paths"])
        self.assertFalse(sidecar_result["data"]["would_delete_paths"])
        self.assertTrue(sidecar_result["data"]["would_write_paths"])

    def test_missing_selected_row_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _files = _completed_fixture(root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            result = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="completed.reconcile_manifest",
                request={"scope": "selected", "row_key": "missing-row"},
            ).to_mapping()

        _assert_dry_run_shape(self, result["data"], "completed.reconcile_manifest")
        statuses = {row["key"]: row["status"] for row in result["data"]["precondition_results"]}
        self.assertEqual(statuses["selected_row_exists"], "blocked")
        self.assertFalse(result["data"]["safe_to_apply"])

    def test_missing_sidecar_precondition_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _files = _completed_fixture(root, missing_sidecar=True)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preview = facade.get_completed_preview(resolved).to_mapping()
            row_key = preview["rows"][0]["row_key"]

            result = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="completed.repair_sidecar_metadata",
                request={"scope": "selected", "row_key": row_key},
            ).to_mapping()

        _assert_dry_run_shape(self, result["data"], "completed.repair_sidecar_metadata")
        self.assertTrue(
            any(row["status"] == "blocked" and "sidecar" in row["key"] for row in result["data"]["precondition_results"])
        )
        self.assertFalse(result["data"]["safe_to_apply"])

    def test_pending_dry_runs_report_manifest_and_orphan_preconditions_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, files = _pending_fixture(root, orphan_payload=True)
            before = {name: _file_state(path) for name, path in files.items() if path.is_file()}
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            preview = facade.get_pending_publish_preview(resolved).to_mapping()
            orphan_key = preview["rows"][0]["row_key"]

            manifest_result = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="pending_publish.repair_manifest",
                request={"scope": "all", "limit": 25},
            ).to_mapping()
            orphan_result = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="pending_publish.reconcile_orphan_payloads",
                request={"scope": "selected", "row_key": orphan_key},
            ).to_mapping()
            after = {name: _file_state(path) for name, path in files.items() if path.is_file()}

        _assert_dry_run_shape(self, manifest_result["data"], "pending_publish.repair_manifest")
        _assert_dry_run_shape(self, orphan_result["data"], "pending_publish.reconcile_orphan_payloads")
        self.assertEqual(before, after)
        self.assertFalse(orphan_result["data"]["would_move_paths"])
        self.assertFalse(orphan_result["data"]["would_delete_paths"])
        self.assertTrue(
            any(row["status"] == "review" and "ambiguity" in row["key"] for row in orphan_result["data"]["precondition_results"])
        )

    def test_unreadable_invalid_and_duplicate_pending_manifest_preconditions_are_blocked(self) -> None:
        cases = [
            ("unreadable", {"unreadable_manifest": True}, "unreadable_manifest"),
            ("invalid", {"invalid_manifest": True}, "invalid_manifest"),
            ("duplicate", {"duplicate_target": True}, "duplicate_target"),
        ]
        for label, kwargs, diagnostic in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    resolved, _files = _pending_fixture(root, **kwargs)
                    facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
                    preview = facade.get_pending_publish_preview(resolved).to_mapping()
                    target = next(row for row in preview["rows"] if row.get("diagnostic_status") == diagnostic)
                    result = facade.plan_repair_reconcile_dry_run(
                        resolved,
                        candidate_command="pending_publish.repair_manifest",
                        request={"scope": "selected", "row_key": target["row_key"]},
                    ).to_mapping()

                _assert_dry_run_shape(self, result["data"], "pending_publish.repair_manifest")
                self.assertTrue(any(row["status"] == "blocked" for row in result["data"]["precondition_results"]))
                self.assertFalse(result["data"]["safe_to_apply"])

    def test_active_work_blocked_precondition_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _files = _completed_fixture(root)
            service = DummyWorkflowFacadeService(root)
            service.find_related_pipeline_processes = lambda *args, **kwargs: [type("Proc", (), {"pid": 12345})()]
            facade = MediaPipelineApplicationFacade(service)

            result = facade.plan_repair_reconcile_dry_run(
                resolved,
                candidate_command="completed.reconcile_manifest",
                request={"scope": "all"},
            ).to_mapping()

        _assert_dry_run_shape(self, result["data"], "completed.reconcile_manifest")
        statuses = {row["key"]: row["status"] for row in result["data"]["precondition_results"]}
        self.assertEqual(statuses["pipeline_idle"], "blocked")

    def test_local_api_dry_run_suppresses_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _files = _completed_fixture(root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                request = Request(
                    f"{server.url}/api/completed/reconcile-manifest-dry-run",
                    data=json.dumps({"scope": "all"}).encode("utf-8"),
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
        _assert_dry_run_shape(self, payload["data"], "completed.reconcile_manifest")
        self.assertEqual(commands["entries"], [])

    def test_startup_reconciliation_dry_run_reports_ambiguity_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, completed_files = _completed_fixture(root)
            pending_resolved, pending_files = _pending_fixture(root, orphan_payload=True)
            resolved.pending_push_path = pending_resolved.pending_push_path
            resolved.state_root = pending_resolved.state_root
            resolved.active_jobs_path = resolved.state_root / "ActiveJobs"
            active_job = resolved.active_jobs_path / "active-missing-pid.json"
            _write_active_job_record(active_job, pid=None)
            db_path = _write_empty_state_db(resolved.state_root)
            files = {
                **completed_files,
                **{name: path for name, path in pending_files.items() if path.is_file()},
                "active_job": active_job,
                "state_db": db_path,
            }
            before = {name: _file_state(path) for name, path in files.items()}
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            result = facade.plan_startup_reconciliation_dry_run(
                resolved,
                request={"scope": "all", "limit": 50, "reason": "restart check"},
            ).to_mapping()
            after = {name: _file_state(path) for name, path in files.items()}

        data = result["data"]
        _assert_startup_reconciliation_shape(self, data)
        self.assertEqual(before, after)
        self.assertEqual(data["overall_status"], "blocked")
        self.assertEqual(data["categories"]["orphaned_parked_outputs"]["status"], "review")
        self.assertEqual(data["categories"]["active_jobs"]["status"], "blocked")
        self.assertEqual(data["categories"]["sqlite_mirror"]["status"], "review")
        codes = {row["code"] for row in data["diff_summary"]["rows"]}
        self.assertIn("startup_pending_orphan_payload", codes)
        self.assertIn("startup_active_job_missing_pid", codes)
        self.assertIn("startup_sqlite_completed_mirror_count_mismatch", codes)

    def test_local_api_startup_reconciliation_dry_run_suppresses_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _completed_files = _completed_fixture(root)
            pending_resolved, _pending_files = _pending_fixture(root, orphan_payload=True)
            resolved.pending_push_path = pending_resolved.pending_push_path
            resolved.state_root = pending_resolved.state_root
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                request = Request(
                    f"{server.url}/api/startup/reconcile-dry-run",
                    data=json.dumps({"scope": "all", "limit": 25}).encode("utf-8"),
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
        _assert_startup_reconciliation_shape(self, payload["data"])
        self.assertEqual(commands["entries"], [])


if __name__ == "__main__":
    unittest.main()
