from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mediapipeline_desktop_app.models import AuditRecord, ResolvedPaths
from app.audit.rerun_io import (
    load_audit_records,
    load_failure_marker_records,
    load_failure_records,
    save_audit_records_csv,
)


class ServiceAuditRerunIoTests(unittest.TestCase):
    def test_load_and_save_audit_records_preserves_union_field_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "audit.csv"
            source.write_text("Path,Issue\nmovie.mkv,bad audio\n", encoding="utf-8")

            records = load_audit_records(source)
            records.append(AuditRecord(source_csv=source, row={"Path": "show.mkv", "Extra": "value"}))
            output = root / "export.csv"
            count = save_audit_records_csv(output, records)
            text = output.read_text(encoding="utf-8")

        self.assertEqual(count, 2)
        self.assertEqual(records[0].row["Path"], "movie.mkv")
        self.assertTrue(text.startswith("Path,Issue,Extra"))

    def test_load_failure_records_rejects_non_list_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "failures.json"
            path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                load_failure_records(path)

    def test_load_failure_marker_records_skips_invalid_marker_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markers = root / "markers"
            markers.mkdir()
            (markers / "bad.json").write_text("{", encoding="utf-8")
            (markers / "good.json").write_text(
                json.dumps({"source_path": "source.mkv", "error_code": "TEST"}),
                encoding="utf-8",
            )
            resolved = ResolvedPaths(
                app_root=root,
                workspace_root=root,
                pipeline_path=root / "pipeline.ps1",
                config_path=root / "config.psd1",
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host=None,
                failed_markers_path=markers,
            )

            records = load_failure_marker_records(resolved)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].error_code, "TEST")


if __name__ == "__main__":
    unittest.main()
