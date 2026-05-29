from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.publish.pending_manifest_rows import (
    invalid_contract_pending_manifest_row,
    pending_output_size,
    pending_payload_error_text,
    pending_sidecar_status,
    readable_pending_manifest_row,
    unreadable_pending_manifest_row,
)


class PendingPublishManifestRowsTests(unittest.TestCase):
    def test_unreadable_and_invalid_contract_rows_preserve_health_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "bad.manifest.json"
            manifest_path.write_text("{", encoding="utf-8")

            unreadable = unreadable_pending_manifest_row(manifest_path, ValueError("bad json"))
            invalid = invalid_contract_pending_manifest_row(
                manifest_path,
                {"schema_version": "pending_push_manifest.v1", "local_file": r"D:\missing.mkv"},
                schema_version="pending_push_manifest.v1",
                exc=ValueError("bad contract"),
            )

        self.assertEqual(unreadable["state"], "unreadable")
        self.assertEqual(unreadable["output_size"], 0)
        self.assertEqual(invalid["state"], "invalid_contract")
        self.assertIn("bad contract", invalid["error"])

    def test_pending_sidecar_status_ignores_invalid_entries_and_counts_missing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = root / "movie.mkv.pipeline.json"
            existing.write_text("{}", encoding="utf-8")
            missing = root / "movie.eng.srt"

            paths, missing_count = pending_sidecar_status(
                [
                    {"local_file": str(existing)},
                    "not-a-dict",
                    {"parked_file": str(missing)},
                    {},
                ]
            )

        self.assertEqual(paths, [str(existing), str(missing)])
        self.assertEqual(missing_count, 1)

    def test_pending_output_size_prefers_manifest_then_payload_stat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = Path(temp_dir) / "payload.mkv"
            payload.write_text("payload", encoding="utf-8")
            self.assertEqual(pending_output_size({"output_size": 99}, payload), 99)
            self.assertEqual(pending_output_size({}, payload), len("payload"))
            self.assertEqual(pending_output_size({}, None), 0)

    def test_payload_error_text_prioritizes_missing_payload_before_sidecars(self) -> None:
        self.assertIn("payload is missing", pending_payload_error_text(Path(r"D:\missing.mkv"), False, 2))
        self.assertIn("2 pending sidecar", pending_payload_error_text(Path(r"D:\payload.mkv"), True, 2))
        self.assertEqual(pending_payload_error_text(Path(r"D:\payload.mkv"), True, 0), "")

    def test_readable_row_formats_state_size_paths_and_schema(self) -> None:
        row = readable_pending_manifest_row(
            manifest_path=Path(r"D:\pending\movie.manifest.json"),
            parked_at="2026-05-08T01:02:03Z",
            publish_mode="server",
            route="remux",
            state="",
            local_path=Path(r"D:\pending\movie.mkv"),
            local_exists=True,
            server_path=Path(r"\\server\out\movie.mkv"),
            source_path=Path(r"D:\source\movie.mkv"),
            output_size=1024,
            sidecar_paths=[r"D:\pending\movie.pipeline.json"],
            missing_sidecars=0,
            schema_version="",
            error_text="",
        )
        self.assertEqual(row["state"], "unknown")
        self.assertEqual(row["schema_version"], "legacy")
        self.assertEqual(row["size_text"], "1.0 KB")
        self.assertEqual(row["sidecar_count"], 1)


if __name__ == "__main__":
    unittest.main()
