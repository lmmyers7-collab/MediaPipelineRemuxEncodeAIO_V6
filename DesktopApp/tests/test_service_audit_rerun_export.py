from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import AuditRecord, ResolvedPaths
from app.audit.rerun_export import save_rerun_records_csv_for_service


def _audit_record(**row: str) -> AuditRecord:
    return AuditRecord(source_csv=Path("audit.csv"), row=row)


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
    )


class DummyRerunExportService:
    def __init__(self, metadata: dict[str, dict[str, object]] | None = None) -> None:
        self.metadata = metadata or {}
        self.metadata_source_paths: list[Path] = []

    def _load_rerun_source_metadata(self, _resolved: ResolvedPaths, source_paths: list[Path]) -> dict[str, dict[str, object]]:
        self.metadata_source_paths = source_paths
        return self.metadata


class ServiceAuditRerunExportTests(unittest.TestCase):
    def test_save_rerun_records_csv_writes_safe_modes_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Movie.mkv"
            source.write_bytes(b"media")
            output_csv = root / "rerun.csv"
            record = _audit_record(
                Path=str(source),
                MediaType="Movie",
                LookupTitle="Movie",
                IssueCodes="needs-rerun",
            )
            service = DummyRerunExportService(
                {
                    str(source).casefold(): {
                        "exists": True,
                        "source_size": 123,
                        "source_mtime_utc": "2026-05-08T12:00:00+00:00",
                        "source_identity_v2": "identity-from-helper",
                    }
                }
            )

            count = save_rerun_records_csv_for_service(
                service,
                output_csv,
                [record],
                _resolved(root),
                stage_mode="move",
                original_mode="delete",
                return_mode="publish",
            )

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(count, 1)
        self.assertEqual(service.metadata_source_paths, [source])
        self.assertEqual(rows[0]["stage_mode"], "copy")
        self.assertEqual(rows[0]["post_success_original"], "keep")
        self.assertEqual(rows[0]["return_mode"], "park")
        self.assertEqual(rows[0]["source_size"], "123")
        self.assertEqual(rows[0]["source_identity_v2"], "identity-from-helper")

    def test_save_rerun_records_csv_rejects_empty_and_no_source_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = DummyRerunExportService()

            with self.assertRaisesRegex(ValueError, "No audit records"):
                save_rerun_records_csv_for_service(
                    service,
                    root / "empty.csv",
                    [],
                    _resolved(root),
                    stage_mode="copy",
                    original_mode="keep",
                    return_mode="park",
                )

            with self.assertRaisesRegex(ValueError, "No rerun rows"):
                save_rerun_records_csv_for_service(
                    service,
                    root / "empty.csv",
                    [_audit_record(MediaType="Movie")],
                    _resolved(root),
                    stage_mode="copy",
                    original_mode="keep",
                    return_mode="park",
                )

    def test_save_rerun_records_csv_preserves_metadata_note_when_stat_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing_source = root / "Missing.mkv"
            output_csv = root / "rerun.csv"
            record = _audit_record(
                Path=str(missing_source),
                MediaType="Movie",
                LookupTitle="Missing",
                IssueCodes="needs-rerun",
            )
            service = DummyRerunExportService(
                {
                    str(missing_source).casefold(): {
                        "exists": False,
                        "error": "metadata helper could not read source",
                    }
                }
            )

            count = save_rerun_records_csv_for_service(
                service,
                output_csv,
                [record],
                _resolved(root),
                stage_mode="copy",
                original_mode="keep",
                return_mode="park",
            )

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["enabled"], "false")
        self.assertIn("source metadata failed: metadata helper could not read source", rows[0]["notes"])
        self.assertIn("source stat failed:", rows[0]["notes"])


if __name__ == "__main__":
    unittest.main()
