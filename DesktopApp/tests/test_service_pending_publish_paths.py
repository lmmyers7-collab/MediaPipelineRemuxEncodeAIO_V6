from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_pending_publish import PendingPublishServiceMixin
from mediapipeline_desktop_app.service_pending_publish_paths import (
    build_pending_orphan_payload_row,
    path_from_manifest,
    path_from_texts,
    pending_item_mtime,
)


class PendingPublishPathHelperTests(unittest.TestCase):
    def test_path_from_manifest_uses_first_non_empty_key(self) -> None:
        manifest = {"local_file": "   ", "parked_file": r"C:\Pending\Movie.mkv"}

        self.assertEqual(path_from_manifest(manifest, "local_file", "parked_file"), Path(r"C:\Pending\Movie.mkv"))
        self.assertIsNone(path_from_manifest(manifest, "missing", "local_file"))

    def test_path_from_texts_uses_first_non_empty_value(self) -> None:
        self.assertEqual(path_from_texts("", "  ", r"C:\Out\Movie.mkv"), Path(r"C:\Out\Movie.mkv"))
        self.assertIsNone(path_from_texts("", None))  # type: ignore[arg-type]

    def test_pending_item_mtime_returns_zero_for_missing_paths(self) -> None:
        self.assertEqual(pending_item_mtime(Path(r"Z:\missing\payload.mkv")), 0.0)

    def test_build_pending_orphan_payload_row_reports_size_and_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            payload = Path(td) / "orphan.mkv"
            payload.write_bytes(b"12345")

            row = build_pending_orphan_payload_row(payload)

        self.assertEqual(row["state"], "orphan_payload")
        self.assertEqual(row["local_file"], str(payload))
        self.assertEqual(row["local_exists"], True)
        self.assertEqual(row["output_size"], 5)
        self.assertEqual(row["size_text"], "5 B")
        self.assertEqual(row["error"], "Payload file has no matching .manifest.json.")

    def test_service_wrapper_methods_delegate_to_path_helpers(self) -> None:
        service = PendingPublishServiceMixin()
        manifest = {"local_file": "", "parked_file": r"C:\Pending\Movie.mkv"}

        self.assertEqual(service._path_from_manifest(manifest, "local_file", "parked_file"), Path(r"C:\Pending\Movie.mkv"))
        self.assertEqual(service._path_from_texts("", r"C:\Server\Movie.mkv"), Path(r"C:\Server\Movie.mkv"))
        self.assertEqual(service._pending_item_mtime(Path(r"Z:\missing\payload.mkv")), 0.0)
        self.assertEqual(service._pending_orphan_payload_row(Path(r"Z:\missing\payload.mkv"))["state"], "orphan_payload")


if __name__ == "__main__":
    unittest.main()
