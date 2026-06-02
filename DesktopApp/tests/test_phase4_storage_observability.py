from __future__ import annotations

import io
import json
import logging
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.observability.logging import JsonLineFormatter, bind_run_context
from app.orchestration.runner import RunnerOptions, StageProcessResult, run_decide_stage
from app.storage.db import CURRENT_SCHEMA_VERSION, STATE_DB_FILENAME, StateDbIncompatibleVersion, open_state_db
from app.validation.boundary import ValidationFailure, validate_api_payload, validate_stage_payload, validate_stage_result
from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.api.command_journal import CommandJournal
from mediapipeline_desktop_app.api.command_journal_policy import COMMAND_RESULT_SCHEMA_VERSION
from mediapipeline_desktop_app.models import ResolvedPaths
from app.completed.service import CompletedJobsServiceMixin
from app.queue.dry_run_runner import run_queue_dry_run_for_service
from app.queue.snapshot import queue_snapshot_write_path, read_queue_snapshot
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


def _stage_stdout() -> str:
    now = datetime.now(timezone.utc).isoformat()
    return json.dumps(
        {
            "schema_version": "v1",
            "stage": "decide",
            "ok": True,
            "started_at": now,
            "finished_at": now,
            "duration_ms": 0,
            "journal_event_type": "pipeline.stage.decide",
            "data": {"route": "remux", "should_encode": False},
        }
    )


class Phase4StorageObservabilityTests(unittest.TestCase):
    def test_state_db_migrations_are_idempotent_and_use_wal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = open_state_db(root)
            db.apply_migrations()

            conn = sqlite3.connect(root / STATE_DB_FILENAME)
            try:
                version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                migrations = conn.execute("SELECT version FROM schema_migrations").fetchall()
            finally:
                conn.close()

        self.assertEqual(version, CURRENT_SCHEMA_VERSION)
        self.assertEqual(journal_mode, "wal")
        self.assertEqual([row[0] for row in migrations], [1])

    def test_state_db_rejects_newer_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / STATE_DB_FILENAME
            conn = sqlite3.connect(path)
            try:
                conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
                conn.commit()
            finally:
                conn.close()
            with self.assertRaises(StateDbIncompatibleVersion):
                open_state_db(Path(td))

    def test_state_db_records_all_phase4_mirror_tables(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = open_state_db(Path(td))
            db.record_command({"command": "settings.reload", "ok": True, "message": "reloaded"})
            db.record_stage_event(
                {
                    "event_type": "pipeline.stage.decide",
                    "run_id": "run-1",
                    "command_id": "cmd-1",
                    "stage": "decide",
                    "ok": True,
                }
            )
            db.record_queue_snapshot({"produced_at": "2026-05-28T00:00:00Z", "rows": [{"source_path": "a.mkv"}]})
            db.record_completed_job({"output_path": "out.mkv", "sidecar_path": "out.pipeline.json"})

            commands = db.list_recent_commands()
            events = db.list_recent_events({"stage": "decide"})

            conn = sqlite3.connect(Path(td) / STATE_DB_FILENAME)
            try:
                queue_count = conn.execute("SELECT COUNT(*) FROM queue_snapshots").fetchone()[0]
                completed_count = conn.execute("SELECT COUNT(*) FROM completed_jobs").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(commands[0]["command"], "settings.reload")
        self.assertEqual(events[0]["event_type"], "pipeline.stage.decide")
        self.assertEqual(queue_count, 1)
        self.assertEqual(completed_count, 1)

    def test_completed_job_mirror_preserves_same_output_append_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = open_state_db(Path(td))
            first = {
                "output_path": "out.mkv",
                "sidecar_path": "out.pipeline.json",
                "completed_at": "2026-05-28T00:00:00Z",
                "route": "remux",
            }
            second = {
                "output_path": "out.mkv",
                "sidecar_path": "out.pipeline.json",
                "completed_at": "2026-05-28T00:01:00Z",
                "route": "encode",
            }

            db.record_completed_job(first)
            db.record_completed_job(second)
            db.record_completed_job(first)

            conn = sqlite3.connect(Path(td) / STATE_DB_FILENAME)
            try:
                rows = conn.execute("SELECT output_path, payload_json FROM completed_jobs ORDER BY id").fetchall()
            finally:
                conn.close()

        self.assertEqual(len(rows), 2)
        self.assertEqual([row[0] for row in rows], ["out.mkv", "out.mkv"])
        self.assertEqual([json.loads(row[1])["route"] for row in rows], ["remux", "encode"])

    def test_command_journal_dual_writes_json_and_sqlite_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal_path = root / "RunLogs" / "local_api_command_history.json"
            journal = CommandJournal(path=journal_path, state_db_root=root / "State")
            journal.record(
                {
                    "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
                    "command": "settings.reload",
                    "ok": True,
                    "severity": "info",
                    "message": "Settings reloaded",
                }
            )

            payload = json.loads(journal_path.read_text(encoding="utf-8"))
            commands = open_state_db(root / "State").list_recent_commands()

        self.assertEqual(payload["entries"][0]["command"], "settings.reload")
        self.assertEqual(commands[0]["command"], "settings.reload")

    def test_command_journal_sqlite_mirror_uses_redacted_bounded_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal = CommandJournal(
                path=root / "RunLogs" / "local_api_command_history.json",
                state_db_root=root / "State",
            )
            journal.record(
                {
                    "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
                    "command": "pipeline.start",
                    "ok": True,
                    "severity": "info",
                    "message": "started",
                    "data": {"mode": "once", "secret_token": "hidden"},
                },
                request={"authorization": "Bearer hidden", "mode": "once"},
            )

            command = open_state_db(root / "State").list_recent_commands()[0]

        payload = command["payload"]
        self.assertEqual(payload["data"]["secret_token"], "<redacted>")
        self.assertEqual(payload["request"]["authorization"], "<redacted>")
        self.assertEqual(payload["request"]["mode"], "once")
        self.assertNotIn("hidden", json.dumps(payload, sort_keys=True))

    def test_local_api_command_journal_mirror_uses_latest_resolved_state_root(self) -> None:
        class DummyFacade:
            app_version = "v6-test"

        def resolved_for(root: Path, state_root: Path) -> ResolvedPaths:
            return ResolvedPaths(
                app_root=root / "DesktopApp",
                workspace_root=root,
                pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
                config_path=root / "Pipeline" / "config.psd1",
                audit_script_path=root / "Pipeline" / "audit.ps1",
                rerun_script_path=root / "Pipeline" / "rerun.ps1",
                powershell_host="pwsh",
                local_base=state_root.parent,
                state_root=state_root,
            )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_state_root = root / "OldLocalBase" / "State"
            new_state_root = root / "NewLocalBase" / "State"
            current = {"resolved": resolved_for(root, old_state_root)}
            server = LocalApiServer(
                DummyFacade(),  # type: ignore[arg-type]
                resolved_provider=lambda: current["resolved"],
                command_journal_path=root / "RunLogs" / "local_api_command_history.json",
                logger=logging.getLogger("test.phase4.command_journal"),
            )
            current["resolved"] = resolved_for(root, new_state_root)

            server._record_command_journal(
                {
                    "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
                    "command": "settings.reload",
                    "ok": True,
                    "severity": "info",
                    "message": "Settings reloaded",
                }
            )

            commands = open_state_db(new_state_root).list_recent_commands()

        self.assertFalse((old_state_root / STATE_DB_FILENAME).exists())
        self.assertEqual(commands[0]["command"], "settings.reload")

    def test_stage_runner_dual_writes_stage_event_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            def fake_run(args, **kwargs):
                return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(), stderr="")

            result = run_decide_stage(
                {"file_size_bytes": 1024, "run_id": "run-1", "job_id": "cmd-1"},
                RunnerOptions(
                    entrypoint_path=Path(__file__),
                    powershell_path="pwsh",
                    run_capture_func=fake_run,
                    state_db_root=root / "State",
                ),
            )

            events = open_state_db(root / "State").list_recent_events({"stage": "decide"})

        self.assertTrue(result.ok)
        self.assertEqual(events[0]["run_id"], "run-1")
        self.assertEqual(events[0]["command_id"], "cmd-1")

    def test_queue_dry_run_dual_writes_legacy_snapshot_and_sqlite_mirror(self) -> None:
        class DummyQueueService:
            QUEUE_DRY_RUN_TIMEOUT_SECONDS = 120.0
            QUEUE_DRY_RUN_OUTPUT_TAIL_LINES = 3

            def __init__(self, root: Path) -> None:
                self.app_root = root / "DesktopApp"
                self.workspace_root = root
                self.app_root.mkdir()
                self._queue_completed_cache_status = ""
                self.logger = logging.getLogger("test.queue.dualwrite")

            def _queue_snapshot_write_path(self, resolved: ResolvedPaths) -> Path | None:
                return queue_snapshot_write_path(resolved)

            def _read_queue_snapshot(self, path: Path) -> dict | None:
                return read_queue_snapshot(path)

            def _queue_snapshot_is_current_for_request(self, _path: Path, _snapshot: dict, _started_at: float) -> bool:
                return True

            def _build_launch_environment(self) -> dict[str, str]:
                return {}

            def _subprocess_kwargs_hidden(self) -> dict[str, object]:
                return {}

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            local_base = root / "LocalBase"
            resolved = ResolvedPaths(
                app_root=root / "DesktopApp",
                workspace_root=root,
                pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
                config_path=root / "Pipeline" / "config.psd1",
                audit_script_path=root / "Pipeline" / "audit.ps1",
                rerun_script_path=root / "Pipeline" / "rerun.ps1",
                powershell_host="pwsh",
                local_base=local_base,
                state_root=local_base / "State",
            )
            service = DummyQueueService(root)

            def fake_run_capture(args, **kwargs):
                temp_path = Path(args[args.index("-QueuePlanOutPath") + 1])
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "queue_plan_snapshot.v1",
                            "produced_at": "2026-05-28T00:00:00Z",
                            "config_path": "config.psd1",
                            "local_base": "LocalBase",
                            "source_movies": "Movies",
                            "source_tv": "TV",
                            "outsource": "Out",
                            "movie_count_total": 1,
                            "tv_count_total": 0,
                            "priority_count": 0,
                            "runnable_count": 1,
                            "rows": [{"source_path": "source.mkv"}],
                        }
                    ),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="", stderr="")

            with patch("app.queue.dry_run_runner.run_capture", fake_run_capture):
                snapshot = run_queue_dry_run_for_service(service, resolved)

            final_path = queue_snapshot_write_path(resolved)
            assert final_path is not None
            legacy_snapshot_exists = final_path.exists()
            mirrored_rows = sqlite3.connect(resolved.state_root / STATE_DB_FILENAME)
            try:
                queue_count = mirrored_rows.execute("SELECT COUNT(*) FROM queue_snapshots").fetchone()[0]
            finally:
                mirrored_rows.close()

        self.assertIsNotNone(snapshot)
        self.assertTrue(legacy_snapshot_exists)
        self.assertEqual(queue_count, 1)

    def test_completed_jobs_service_dual_writes_sqlite_mirror_without_changing_manifest_read(self) -> None:
        class DummyCompletedService(CompletedJobsServiceMixin):
            def __init__(self) -> None:
                self.logger = logging.getLogger("test.completed.dualwrite")
                self._completed_history_cache_key = None
                self._completed_history_cached_at = 0.0
                self._completed_history_manifest_mtime = 0.0
                self._completed_history_records = []

            def _path_or_none(self, value):
                return Path(value) if value else None

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_root = root / "State"
            manifest = state_root / "Completed" / "completed_jobs.jsonl"
            manifest.parent.mkdir(parents=True)
            output = root / "out.mkv"
            output.write_text("media", encoding="utf-8")
            manifest.write_text(json.dumps({"output_path": str(output), "route": "remux"}) + "\n", encoding="utf-8")
            resolved = ResolvedPaths(
                app_root=root / "DesktopApp",
                workspace_root=root,
                pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
                config_path=root / "Pipeline" / "config.psd1",
                audit_script_path=root / "Pipeline" / "audit.ps1",
                rerun_script_path=root / "Pipeline" / "rerun.ps1",
                powershell_host="pwsh",
                local_base=root / "LocalBase",
                state_root=state_root,
                completed_manifest_path=manifest,
                config_data={"Outsource": str(root)},
            )

            rows = DummyCompletedService().load_recent_completed_jobs(resolved, limit=10, force_refresh=True)
            conn = sqlite3.connect(state_root / STATE_DB_FILENAME)
            try:
                completed_count = conn.execute("SELECT COUNT(*) FROM completed_jobs").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(completed_count, 1)

    def test_boundary_validation_helpers_preserve_compatibility_and_reject_bad_stage_payloads(self) -> None:
        payload = validate_api_payload("/api/settings/reload", {"anything": "legacy-compatible"})

        self.assertEqual(payload["anything"], "legacy-compatible")
        with self.assertRaises(ValidationFailure):
            validate_stage_payload("decide", {})
        with self.assertRaises(ValidationFailure):
            validate_stage_result("probe", json.loads(_stage_stdout()))

    def test_json_logging_required_fields_redacts_secret_keys_and_serializes_exceptions(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonLineFormatter())
        logger = logging.getLogger("test.phase4.json")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        adapter = bind_run_context(logger, run_id="run-1", command_id="cmd-1", stage="decide")
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            adapter.exception(
                "stage failed",
                extra={"structured": {"auth_token": "secret-value", "safe": "visible"}},
            )

        line = json.loads(stream.getvalue())

        self.assertEqual(line["event"], "stage failed")
        self.assertEqual(line["run_id"], "run-1")
        self.assertEqual(line["command_id"], "cmd-1")
        self.assertEqual(line["stage"], "decide")
        self.assertEqual(line["auth_token"], "[redacted]")
        self.assertEqual(line["safe"], "visible")
        self.assertEqual(line["error"]["type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
