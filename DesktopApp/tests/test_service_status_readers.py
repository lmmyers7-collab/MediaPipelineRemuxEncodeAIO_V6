from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.status.service import StatusServiceMixin
from app.status.readers import (
    read_audit_progress_file,
    read_log_tail_file,
    read_pipeline_events_tail_file,
    read_progress_file,
)


class CaptureLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def warning(self, message: str, *args: object) -> None:
        self.messages.append(message % args if args else message)


def _progress_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ProgressVersion": 2,
        "LastUpdate": "2026-05-08T12:00:00",
        "Status": "Encoding",
        "CurrentStage": "encode",
        "CurrentStagePercent": 50,
        "TotalProcessed": 1,
        "Encoded": 1,
        "Remuxed": 0,
        "Failed": 0,
        "Movies": 1,
        "TVEpisodes": 0,
    }
    payload.update(overrides)
    return payload


def _event_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "pipeline_event.v1",
        "event_id": "event-1",
        "event_type": "tool_completed",
        "timestamp": "2026-05-08T12:00:00",
        "created_at": "2026-05-08T12:00:00",
        "run_id": "run-1",
        "correlation_id": "corr-1",
        "job_id": "job-1",
        "product_version": "v4.000",
        "pipeline_version": "v4.000",
        "stage": "encode",
        "route": "encode",
        "status": "succeeded",
        "source_path": r"C:\Media\Movie.mkv",
        "data": {},
    }
    payload.update(overrides)
    return payload


def _resolved(root: Path, *, progress_file: Path | None = None, audit_reports_path: Path | None = None, log_file: Path | None = None, event_file: Path | None = None) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
        progress_file=progress_file,
        audit_reports_path=audit_reports_path,
        log_file=log_file,
        event_file=event_file,
    )


class StatusReaderHelperTests(unittest.TestCase):
    def test_read_progress_file_validates_contract_and_preserves_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pipeline_progress.json"
            path.write_text(json.dumps(_progress_payload(CurrentFile="Movie.mkv")), encoding="utf-8")

            progress = read_progress_file(path)

        self.assertIsNotNone(progress)
        self.assertEqual(progress["Status"], "Encoding")
        self.assertEqual(progress["CurrentFile"], "Movie.mkv")

    def test_read_progress_file_logs_invalid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pipeline_progress.json"
            path.write_text(json.dumps(_progress_payload(CurrentStagePercent=150)), encoding="utf-8")
            logger = CaptureLogger()

            self.assertIsNone(read_progress_file(path, logger))

        combined = "\n".join(logger.messages)
        self.assertIn("Progress contract invalid", combined)
        self.assertIn(str(path), combined)

    def test_read_progress_file_logs_malformed_json_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pipeline_progress.json"
            path.write_text("{not json", encoding="utf-8")
            logger = CaptureLogger()

            self.assertIsNone(read_progress_file(path, logger))

        combined = "\n".join(logger.messages)
        self.assertIn("Progress read failed", combined)
        self.assertIn(str(path), combined)

    def test_read_audit_progress_file_returns_raw_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "AuditReports"
            audit.mkdir()
            (audit / "audit_progress.json").write_text(json.dumps({"status": "scanning", "processed_files": 2}), encoding="utf-8")

            self.assertEqual(read_audit_progress_file(audit), {"status": "scanning", "processed_files": 2})

    def test_read_audit_progress_file_logs_malformed_json_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "AuditReports"
            audit.mkdir()
            path = audit / "audit_progress.json"
            path.write_text("{not json", encoding="utf-8")
            logger = CaptureLogger()

            self.assertIsNone(read_audit_progress_file(audit, logger))

        combined = "\n".join(logger.messages)
        self.assertIn("Audit progress read failed", combined)
        self.assertIn(str(path), combined)

    def test_read_log_tail_file_reports_missing_empty_and_tail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = root / "missing.log"
            empty = root / "empty.log"
            log = root / "pipeline_debug.log"
            empty.write_text("", encoding="utf-8")
            log.write_text("one\ntwo\nthree\n", encoding="utf-8")

            self.assertEqual(read_log_tail_file(missing), "No pipeline_debug.log found yet.")
            self.assertEqual(read_log_tail_file(empty), "(log is empty)")
            self.assertEqual(read_log_tail_file(log, line_count=2), "two\nthree")

    def test_read_pipeline_events_tail_file_filters_invalid_contract_records(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            event_file = Path(td) / "pipeline_events.jsonl"
            event_file.write_text(
                "\n".join(
                    [
                        json.dumps(_event_payload(event_id="valid")),
                        json.dumps({"schema_version": "pipeline_event.v1", "event_type": ""}),
                    ]
                ),
                encoding="utf-8",
            )
            logger = CaptureLogger()

            events = read_pipeline_events_tail_file(event_file, logger=logger)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], "valid")
        combined = "\n".join(logger.messages)
        self.assertIn("Skipped 1 invalid pipeline event record", combined)
        self.assertIn(str(event_file), combined)

    def test_service_mixin_preserves_reader_wrapper_methods(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "AuditReports"
            audit.mkdir()
            progress_file = root / "pipeline_progress.json"
            log_file = root / "pipeline_debug.log"
            event_file = root / "pipeline_events.jsonl"
            progress_file.write_text(json.dumps(_progress_payload()), encoding="utf-8")
            (audit / "audit_progress.json").write_text(json.dumps({"status": "done"}), encoding="utf-8")
            log_file.write_text("line1\nline2", encoding="utf-8")
            event_file.write_text(json.dumps(_event_payload()), encoding="utf-8")
            resolved = _resolved(
                root,
                progress_file=progress_file,
                audit_reports_path=audit,
                log_file=log_file,
                event_file=event_file,
            )
            service = StatusServiceMixin()
            service.logger = CaptureLogger()

            self.assertEqual(service.read_progress(resolved)["Status"], "Encoding")
            self.assertEqual(service.read_audit_progress(resolved), {"status": "done"})
            self.assertEqual(service.read_log_tail(resolved, line_count=1), "line2")
            self.assertEqual(len(service.read_pipeline_events_tail(resolved)), 1)


if __name__ == "__main__":
    unittest.main()
