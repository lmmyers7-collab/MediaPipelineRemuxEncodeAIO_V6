from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
