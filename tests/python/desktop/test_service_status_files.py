from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.status.service import StatusServiceMixin
from mediapipeline.core.observability.status_files import (
    latest_audit_csv,
    latest_failure_json,
    latest_matching_file,
)


def _resolved(root: Path, *, audit_reports_path: Path | None = None, failed_reports_path: Path | None = None) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
        audit_reports_path=audit_reports_path,
        failed_reports_path=failed_reports_path,
    )


def _touch(path: Path, timestamp: float) -> Path:
    path.write_text(path.name, encoding="utf-8")
    os.utime(path, (timestamp, timestamp))
    return path


class StatusFileHelperTests(unittest.TestCase):
    def test_latest_matching_file_returns_none_for_missing_folder(self) -> None:
        self.assertIsNone(latest_matching_file(None, "*.txt"))
        self.assertIsNone(latest_matching_file(Path("does-not-exist"), "*.txt"))

    def test_latest_matching_file_picks_newest_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            older = _touch(folder / "round_failures_older.txt", 1000)
            newer = _touch(folder / "round_failures_newer.txt", 2000)
            _touch(folder / "ignored.json", 3000)

            self.assertEqual(latest_matching_file(folder, "round_failures_*.txt"), newer)
            self.assertNotEqual(latest_matching_file(folder, "round_failures_*.txt"), older)

    def test_latest_matching_file_skips_unreadable_match_without_dropping_valid_reports(self) -> None:
        class FakeReport:
            def __init__(self, name: str, mtime: float, *, stat_fails: bool = False) -> None:
                self.name = name
                self._mtime = mtime
                self._stat_fails = stat_fails

            def stat(self):
                if self._stat_fails:
                    raise OSError("report is temporarily unavailable")
                return type("StatResult", (), {"st_mtime": self._mtime})()

        class FakeFolder:
            def __init__(self, items: list[FakeReport]) -> None:
                self._items = items

            def exists(self) -> bool:
                return True

            def glob(self, pattern: str) -> list[FakeReport]:
                self.pattern = pattern
                return list(self._items)

        valid = FakeReport("round_failures_valid.txt", 2000)
        unreadable = FakeReport("round_failures_locked.txt", 3000, stat_fails=True)
        folder = FakeFolder([valid, unreadable])

        self.assertIs(latest_matching_file(folder, "round_failures_*.txt"), valid)  # type: ignore[arg-type]
        self.assertEqual(folder.pattern, "round_failures_*.txt")

    def test_latest_audit_csv_keeps_priority_and_standard_reports_separate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "AuditReports"
            audit.mkdir()
            standard_old = _touch(audit / "audit_summary_20260507.csv", 1000)
            standard_new = _touch(audit / "audit_summary_20260508.csv", 3000)
            priority_new = _touch(audit / "audit_summary_20260508.priority.csv", 4000)

            resolved = _resolved(root, audit_reports_path=audit)

            self.assertEqual(latest_audit_csv(resolved, priority_only=False), standard_new)
            self.assertNotEqual(latest_audit_csv(resolved, priority_only=False), standard_old)
            self.assertEqual(latest_audit_csv(resolved, priority_only=True), priority_new)

    def test_latest_audit_csv_prefers_completed_progress_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "AuditReports"
            audit.mkdir()
            newer_by_mtime = _touch(audit / "audit_summary_20260509.csv", 3000)
            pointed = _touch(audit / "audit_summary_20260508.csv", 1000)
            priority = _touch(audit / "audit_summary_20260508.priority.csv", 1000)
            (audit / "audit_progress.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "completed": True,
                        "failed": False,
                        "latest_csv_path": str(pointed),
                        "latest_priority_csv_path": str(priority),
                    }
                ),
                encoding="utf-8",
            )

            resolved = _resolved(root, audit_reports_path=audit)

            self.assertEqual(latest_audit_csv(resolved, priority_only=False), pointed)
            self.assertNotEqual(latest_audit_csv(resolved, priority_only=False), newer_by_mtime)
            self.assertEqual(latest_audit_csv(resolved, priority_only=True), priority)

    def test_latest_audit_csv_ignores_unsafe_progress_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "AuditReports"
            outside = root / "Outside"
            audit.mkdir()
            outside.mkdir()
            expected = _touch(audit / "audit_summary_20260508.csv", 1000)
            unsafe = _touch(outside / "audit_summary_20260509.csv", 5000)
            (audit / "audit_progress.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "completed": True,
                        "failed": False,
                        "latest_csv_path": str(unsafe),
                    }
                ),
                encoding="utf-8",
            )

            resolved = _resolved(root, audit_reports_path=audit)

            self.assertEqual(latest_audit_csv(resolved, priority_only=False), expected)

    def test_latest_audit_csv_uses_report_stamp_before_mtime_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "AuditReports"
            audit.mkdir()
            older_stamp_touched_later = _touch(audit / "audit_summary_20260507_010000.csv", 4000)
            newer_stamp = _touch(audit / "audit_summary_20260508_010000.csv", 1000)

            resolved = _resolved(root, audit_reports_path=audit)

            self.assertEqual(latest_audit_csv(resolved, priority_only=False), newer_stamp)
            self.assertNotEqual(latest_audit_csv(resolved, priority_only=False), older_stamp_touched_later)

    def test_latest_failure_json_selects_latest_round_failure_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failed = root / "Failed"
            failed.mkdir()
            _touch(failed / "round_failures_old.json", 1000)
            newest = _touch(failed / "round_failures_new.json", 2000)
            _touch(failed / "round_failures_new.txt", 3000)

            self.assertEqual(latest_failure_json(_resolved(root, failed_reports_path=failed)), newest)

    def test_service_mixin_preserves_status_file_wrapper_methods(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = root / "AuditReports"
            failed = root / "Failed"
            audit.mkdir()
            failed.mkdir()
            csv_path = _touch(audit / "audit_summary_20260508.csv", 1000)
            json_path = _touch(failed / "round_failures_20260508.json", 1000)
            resolved = _resolved(root, audit_reports_path=audit, failed_reports_path=failed)
            service = StatusServiceMixin()

            self.assertEqual(service.latest_audit_csv(resolved, priority_only=False), csv_path)
            self.assertEqual(service.latest_failure_json(resolved), json_path)
            self.assertEqual(service.latest_matching_file(failed, "*.json"), json_path)


if __name__ == "__main__":
    unittest.main()
