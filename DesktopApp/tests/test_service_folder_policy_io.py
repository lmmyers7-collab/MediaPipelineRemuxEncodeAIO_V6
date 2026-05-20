from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mediapipeline_desktop_app.service_constants import FOLDER_POLICY_SIDECAR_NAME
from mediapipeline_desktop_app.service_folder_policy_io import (
    folder_policy_path,
    load_folder_policy_file,
    save_folder_policy_file,
)


class ServiceFolderPolicyIoTests(unittest.TestCase):
    def test_folder_policy_path_uses_standard_sidecar_name(self) -> None:
        folder = Path("C:/Media/Show")

        self.assertEqual(folder_policy_path(folder), folder / FOLDER_POLICY_SIDECAR_NAME)

    def test_load_folder_policy_returns_default_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            default = {"schema_version": "folder_policy.v1", "folder": str(folder)}

            self.assertEqual(load_folder_policy_file(folder, default_policy=default), default)

    def test_save_folder_policy_fills_schema_and_folder_then_loads_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)

            path = save_folder_policy_file(folder, {"audio": {"passthrough_profile": "plex_balanced"}})
            payload = load_folder_policy_file(folder, default_policy={})

            self.assertEqual(path, folder / FOLDER_POLICY_SIDECAR_NAME)
            self.assertEqual(payload["schema_version"], "folder_policy.v1")
            self.assertEqual(payload["folder"], str(folder))
            self.assertEqual(payload["audio"]["passthrough_profile"], "plex_balanced")

    def test_load_folder_policy_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / FOLDER_POLICY_SIDECAR_NAME).write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "unexpected shape"):
                load_folder_policy_file(folder, default_policy={})


if __name__ == "__main__":
    unittest.main()
