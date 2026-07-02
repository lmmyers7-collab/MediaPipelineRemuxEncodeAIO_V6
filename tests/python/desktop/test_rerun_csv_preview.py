from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.processes.rerun_preview import (  # noqa: E402
    materialize_scoped_rerun_csv,
    recent_rerun_csv_candidates,
    rerun_import_csv_root,
    rerun_csv_preview_payload,
)
from mediapipeline.desktop.models import ResolvedPaths  # noqa: E402


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "MediaPipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host="pwsh",
        local_base=root / "LocalBase",
        state_root=root / "LocalBase" / "State",
        audit_reports_path=root / "LocalBase" / "AuditReports",
    )


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "enabled",
        "source_path",
        "audit_issue_codes",
        "stage_mode",
        "post_success_original",
        "return_mode",
        "effective_bucket",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class RerunCsvPreviewTests(unittest.TestCase):
    def test_preview_counts_blocked_disabled_duplicate_and_scoped_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": r"C:\Media\One.mkv", "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "false", "source_path": r"C:\Media\Two.mkv", "audit_issue_codes": "SUBTITLE", "effective_bucket": "REVIEW"},
                    {"enabled": "true", "source_path": r"C:\Media\Three.mkv", "stage_mode": "move", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "true", "source_path": r"C:\Media\One.mkv", "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "true", "source_path": "", "audit_issue_codes": "MISSING", "effective_bucket": "RERUN_PIPELINE"},
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "scope": {
                        "enabled_only": True,
                        "skip_blocked": True,
                        "skip_warning_rows": False,
                        "issue_filter": "AUDIO",
                        "preview_limit": 3,
                    },
                },
            )

        self.assertEqual(payload["schema_version"], "desktop_rerun_csv_preview.v1")
        self.assertEqual(payload["status"], "review")
        self.assertEqual(payload["counts"]["total_rows"], 5)
        self.assertEqual(payload["counts"]["disabled_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_rows"], 2)
        self.assertEqual(payload["counts"]["blocked_mode_rows"], 1)
        self.assertEqual(payload["counts"]["duplicate_source_rows"], 2)
        self.assertEqual(payload["counts"]["missing_source_rows"], 1)
        self.assertEqual(payload["counts"]["effective_scoped_rows"], 2)
        self.assertEqual(len(payload["rows"]), 3)
        self.assertEqual(payload["execution_mode"], "one_at_a_time")
        self.assertEqual(payload["destination_mode"], "review_workspace")
        self.assertIn("AUDIO", [item["value"] for item in payload["filter_options"]["issue_filters"]])
        self.assertEqual(Path(payload["import_csv_root"]), root / "LocalBase" / "State" / "Rerun" / "ImportCsv")

    def test_pending_publish_destination_does_not_block_rows_without_legacy_override(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": r"C:\Media\One.mkv", "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {
                        "enabled": "true",
                        "source_path": r"C:\Media\Two.mkv",
                        "audit_issue_codes": "SUBTITLE",
                        "effective_bucket": "RERUN_PIPELINE",
                        "return_mode": "replace_original",
                    },
                ],
            )

            payload = rerun_csv_preview_payload(
                _resolved(root),
                {
                    "csv_path": str(csv_path),
                    "destination_mode": "pending_publish",
                    "collision_policy": "suffix",
                    "original_policy": "keep",
                    "scope": {
                        "enabled_only": True,
                        "skip_blocked": True,
                        "preview_limit": 10,
                    },
                },
            )

        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["safe_modes"])
        self.assertEqual(payload["destination_mode"], "pending_publish")
        self.assertEqual(payload["return_mode"], "pending_publish")
        self.assertEqual(payload["counts"]["total_rows"], 2)
        self.assertEqual(payload["counts"]["blocked_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_mode_rows"], 1)
        self.assertEqual(payload["counts"]["effective_scoped_rows"], 1)
        self.assertEqual(payload["counts"]["blocked_scoped_rows"], 0)
        self.assertEqual(payload["rows"][0]["status"], "ready")
        self.assertEqual(payload["rows"][0]["return_mode"], "pending_publish")
        self.assertEqual(payload["rows"][1]["status"], "blocked")
        self.assertIn("blocked source-mutating", payload["rows"][1]["reason"])

    def test_materialize_scoped_csv_writes_only_filtered_rows_under_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            _write_csv(
                csv_path,
                [
                    {"enabled": "true", "source_path": r"C:\Media\One.mkv", "audit_issue_codes": "AUDIO", "effective_bucket": "RERUN_PIPELINE"},
                    {"enabled": "true", "source_path": r"C:\Media\Two.mkv", "audit_issue_codes": "SUBTITLE", "effective_bucket": "REVIEW"},
                    {"enabled": "true", "source_path": r"C:\Media\Three.mkv", "stage_mode": "move", "effective_bucket": "RERUN_PIPELINE"},
                ],
            )
            resolved = _resolved(root)
            request = {
                "csv_path": str(csv_path),
                "scope": {
                    "enabled_only": True,
                    "skip_blocked": True,
                    "issue_filter": "AUDIO",
                    "preview_limit": 10,
                },
            }
            preview = rerun_csv_preview_payload(resolved, request)

            scoped = materialize_scoped_rerun_csv(resolved, request, preview=preview)
            scoped_path = Path(scoped["scoped_csv_path"])
            with scoped_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertTrue(scoped_path.exists())
            self.assertIn("State", str(scoped_path))
            self.assertEqual(scoped["row_count"], 1)
            self.assertEqual(rows[0]["source_path"], r"C:\Media\One.mkv")

    def test_recent_candidates_are_limited_to_import_and_scoped_rerun_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            import_root = rerun_import_csv_root(resolved)
            assert import_root is not None
            import_csv = import_root / "audit_rerun_export_20260701_120000.csv"
            scoped_csv = resolved.state_root / "Rerun" / "ScopedCsv" / "rerun_scoped_20260701.csv"
            audit_csv = resolved.audit_reports_path / "audit_full_20260701.csv"
            for path in (import_csv, scoped_csv, audit_csv):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("source_path\nC:/Media/Movie.mkv\n", encoding="utf-8")

            candidates = recent_rerun_csv_candidates(resolved)
            paths = {Path(item["path"]) for item in candidates}

        self.assertIn(import_csv, paths)
        self.assertIn(scoped_csv, paths)
        self.assertNotIn(audit_csv, paths)


if __name__ == "__main__":
    unittest.main()
