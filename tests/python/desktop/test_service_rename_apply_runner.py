from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.service import RenameServiceMixin
from mediapipeline.core.rename.apply_runner import apply_rename_path_plan_for_service


class DummyRenameApplyRunnerService(RenameServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_rename_apply_runner")
        self.logger.addHandler(logging.NullHandler())


class RenameApplyRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DummyRenameApplyRunnerService()

    def test_apply_runner_rejects_blocked_rows(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "blocked row"):
            apply_rename_path_plan_for_service(self.service, [{"errors": ["blocked"]}])

    def test_apply_runner_renames_single_media_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Noisy.Movie.2020.mkv"
            source.write_text("x", encoding="utf-8")
            plan = self.service.plan_rename_paths(
                [source],
                mode="movie",
                movie_title="Clean Movie",
                movie_year="2020",
                rename_sidecars=False,
            )

            result = apply_rename_path_plan_for_service(self.service, plan)
            destination = Path(td) / "Clean Movie (2020).mkv"

            self.assertEqual(result["renamed"], 1)
            self.assertTrue(destination.exists())
            self.assertFalse(source.exists())
            Path(str(result["undo_manifest"])).unlink(missing_ok=True)

    def test_apply_runner_writes_undo_manifest_to_requested_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Noisy.Movie.2020.mkv"
            undo_root = root / "State" / "RenameUndo"
            source.write_text("x", encoding="utf-8")
            plan = self.service.plan_rename_paths(
                [source],
                mode="movie",
                movie_title="Clean Movie",
                movie_year="2020",
                rename_sidecars=False,
            )

            result = apply_rename_path_plan_for_service(self.service, plan, undo_manifest_root=undo_root)
            undo_manifest = Path(str(result["undo_manifest"]))

            self.assertEqual(undo_manifest.parent, undo_root)
            self.assertTrue(undo_manifest.exists())
            undo_manifest.unlink(missing_ok=True)

    def test_undo_manifest_reverses_media_sidecar_and_restores_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Noisy.Movie.2020.mkv"
            sidecar = root / "Noisy.Movie.2020.pipeline.json"
            undo_root = root / "State" / "RenameUndo"
            source.write_text("media", encoding="utf-8")
            original_sidecar = {
                "output_path": str(source),
                "output_file": source.name,
                "custom": "keep",
            }
            sidecar.write_text(json.dumps(original_sidecar), encoding="utf-8")
            plan = self.service.plan_rename_paths(
                [source],
                mode="movie",
                movie_title="Clean Movie",
                movie_year="2020",
                rename_sidecars=True,
            )

            applied = apply_rename_path_plan_for_service(self.service, plan, undo_manifest_root=undo_root)
            undo_manifest = Path(str(applied["undo_manifest"]))
            manifest_data = json.loads(undo_manifest.read_text(encoding="utf-8"))
            destination = root / "Clean Movie (2020).mkv"
            destination_sidecar = root / "Clean Movie (2020).pipeline.json"

            undone = self.service.undo_rename_manifest(undo_manifest, undo_manifest_root=undo_root)

            self.assertTrue(source.exists())
            self.assertTrue(sidecar.exists())
            self.assertFalse(destination.exists())
            self.assertFalse(destination_sidecar.exists())
            self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8")), original_sidecar)
            self.assertEqual(applied["media_operations"], 1)
            self.assertEqual(applied["sidecar_operations"], 1)
            self.assertTrue(manifest_data["metadata_backups"])
            self.assertEqual(undone["schema_version"], "desktop_rename_undo_result.v1")
            self.assertEqual(undone["media_operations"], 1)
            self.assertEqual(undone["sidecar_operations"], 1)
            self.assertEqual(undone["undone"], 2)

    def test_undo_manifest_blocks_missing_destination_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Original.mkv"
            destination = root / "Renamed.mkv"
            undo_root = root / "State" / "RenameUndo"
            undo_root.mkdir(parents=True)
            undo_manifest = undo_root / "rename-undo.json"
            undo_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "rename_undo.v1",
                        "status": "completed",
                        "operations": [
                            {"kind": "media", "source": str(source), "destination": str(destination)}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "renamed path is missing"):
                self.service.undo_rename_manifest(undo_manifest, undo_manifest_root=undo_root)


if __name__ == "__main__":
    unittest.main()
