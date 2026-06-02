from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rename.apply import (
    build_rename_operations,
    pipeline_sidecar_paths_for_destination,
    read_json_dict_for_rename,
    rename_path_case_safe,
    rollback_rename_operations,
    update_pipeline_sidecar_after_rename,
    update_rename_sidecar_metadata,
    write_rename_undo_manifest,
)
from app.rename.utils import casefold_path, pipeline_sidecar_path, resolve_same_file


class RenameApplyHelperTests(unittest.TestCase):
    def test_rename_path_case_safe_handles_case_only_rename(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Example.mkv"
            destination = Path(td) / "example.mkv"
            source.write_text("media", encoding="utf-8")

            rename_path_case_safe(source, destination, same_file=resolve_same_file)

            self.assertTrue(destination.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "media")

    def test_rename_path_case_safe_restores_temp_after_case_only_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Example.mkv"
            destination = Path(td) / "example.mkv"
            source.write_text("media", encoding="utf-8")
            original_rename = Path.rename
            calls: list[tuple[Path, Path]] = []

            def flaky_rename(path: Path, target: Path) -> Path:
                calls.append((path, target))
                if len(calls) == 2:
                    raise PermissionError("simulated final rename failure")
                return original_rename(path, target)

            with patch.object(Path, "rename", flaky_rename):
                with self.assertRaisesRegex(PermissionError, "simulated final rename failure"):
                    rename_path_case_safe(source, destination, same_file=resolve_same_file)

            self.assertTrue(source.exists())
            self.assertEqual(source.read_text(encoding="utf-8"), "media")
            self.assertEqual(list(Path(td).glob(".mediapipeline-rename-*.mkv")), [])

    def test_read_json_dict_for_rename_marks_invalid_sidecar_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sidecar = Path(td) / "bad.json"
            sidecar.write_text("{not json", encoding="utf-8")

            data = read_json_dict_for_rename(sidecar)

            self.assertEqual(data, {"PreviousSidecarDecodeError": True})

    def test_update_rename_sidecar_metadata_preserves_decode_error_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sidecar = Path(td) / "movie.mediapipeline.rename.json"
            sidecar.write_text("{not json", encoding="utf-8")
            payload = {
                "AppliedAt": "2026-05-08T10:00:00",
                "OriginalPath": "old.mkv",
                "RenamedPath": "new.mkv",
                "PipelineGuess": "new.mkv",
                "FinalName": "new.mkv",
                "ForcePipelineName": True,
                "Mode": "movie",
            }

            update_rename_sidecar_metadata(sidecar, payload)
            data = json.loads(sidecar.read_text(encoding="utf-8"))

            self.assertTrue(data["PreviousSidecarDecodeError"])
            self.assertEqual(data["RenameTool"], payload)

    def test_update_pipeline_sidecar_after_rename_rewrites_output_fields_and_caps_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sidecar = Path(td) / "old.pipeline.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_sidecar.v1",
                        "output_path": "old.mkv",
                        "output_file": "old.mkv",
                        "rename_history": [
                            {
                                "applied_at": f"2026-05-08T09:{minute:02d}:00",
                                "original_path": f"old-{minute}.mkv",
                                "renamed_path": f"new-{minute}.mkv",
                                "final_name": f"new-{minute}.mkv",
                                "force_pipeline_name": False,
                            }
                            for minute in range(30)
                        ],
                    }
                ),
                encoding="utf-8",
            )
            destination = Path(td) / "New Movie (2020).mkv"
            payload = {
                "AppliedAt": "2026-05-08T10:00:00",
                "OriginalPath": "old.mkv",
                "RenamedPath": str(destination),
                "PipelineGuess": destination.name,
                "FinalName": destination.name,
                "ForcePipelineName": False,
                "Mode": "movie",
            }

            update_pipeline_sidecar_after_rename(sidecar, payload, destination)
            data = json.loads(sidecar.read_text(encoding="utf-8"))

            self.assertEqual(data["output_path"], str(destination))
            self.assertEqual(data["output_file"], destination.name)
            self.assertEqual(data["RenameTool"], payload)
            self.assertEqual(len(data["rename_history"]), 25)
            self.assertEqual(data["rename_history"][-1]["final_name"], destination.name)

    def test_pipeline_sidecar_paths_for_destination_deduplicates_equivalent_candidates(self) -> None:
        destination = Path("Example.mkv")

        paths = pipeline_sidecar_paths_for_destination(
            destination,
            pipeline_sidecar_path=pipeline_sidecar_path,
            casefold_path=casefold_path,
        )

        self.assertEqual(paths, [Path("Example.pipeline.json"), Path("Example.mkv.pipeline.json")])

    def test_write_rename_undo_manifest_reuses_existing_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = {"schema_version": "rename_undo.v1", "status": "planned"}

            first_path = write_rename_undo_manifest(manifest, root=root)
            manifest["status"] = "completed"
            second_path = write_rename_undo_manifest(manifest, root=root)
            data = json.loads(second_path.read_text(encoding="utf-8"))

            self.assertEqual(first_path, second_path)
            self.assertEqual(data["status"], "completed")

    def test_build_rename_operations_detects_duplicate_media_destination(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "one.mkv"
            second = Path(td) / "two.mkv"
            destination = Path(td) / "target.mkv"
            first.write_text("x", encoding="utf-8")
            second.write_text("x", encoding="utf-8")
            plan = [
                {"source": first, "destination": destination, "rename_sidecars": False},
                {"source": second, "destination": destination, "rename_sidecars": False},
            ]

            with self.assertRaisesRegex(RuntimeError, "same path"):
                build_rename_operations(plan, same_file=resolve_same_file, casefold_path=casefold_path)

    def test_build_rename_operations_rejects_cross_root_destination(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_dir = root / "source"
            outside_dir = root / "outside"
            source_dir.mkdir()
            outside_dir.mkdir()
            source = source_dir / "one.mkv"
            destination = outside_dir / "one.mkv"
            source.write_text("x", encoding="utf-8")
            plan = [{"source": source, "destination": destination, "rename_sidecars": False}]

            with self.assertRaisesRegex(RuntimeError, "OUTSIDE_ALLOWED_ROOT"):
                build_rename_operations(plan, same_file=resolve_same_file, casefold_path=casefold_path)

    def test_build_rename_operations_detects_duplicate_sidecar_destination(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "one.mkv"
            second = Path(td) / "two.mkv"
            first_sidecar = Path(td) / "one.pipeline.json"
            second_sidecar = Path(td) / "two.pipeline.json"
            first.write_text("x", encoding="utf-8")
            second.write_text("x", encoding="utf-8")
            first_sidecar.write_text("{}", encoding="utf-8")
            second_sidecar.write_text("{}", encoding="utf-8")
            target = Path(td) / "shared.pipeline.json"
            plan = [
                {
                    "source": first,
                    "destination": first,
                    "rename_sidecars": True,
                    "sidecar_moves": [{"source": first_sidecar, "destination": target}],
                },
                {
                    "source": second,
                    "destination": second,
                    "rename_sidecars": True,
                    "sidecar_moves": [{"source": second_sidecar, "destination": target}],
                },
            ]

            with self.assertRaisesRegex(RuntimeError, "same sidecar path"):
                build_rename_operations(plan, same_file=resolve_same_file, casefold_path=casefold_path)

    def test_rollback_rename_operations_restores_completed_paths_in_reverse_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first_source = root / "one.mkv"
            second_source = root / "two.mkv"
            first_destination = root / "show - s01e01.mkv"
            second_destination = root / "show - s01e02.mkv"
            first_destination.write_text("one", encoding="utf-8")
            second_destination.write_text("two", encoding="utf-8")
            operations = [
                {"kind": "media", "source": first_source, "destination": first_destination},
                {"kind": "media", "source": second_source, "destination": second_destination},
            ]

            errors = rollback_rename_operations(
                operations,
                rename_path=lambda source, destination: rename_path_case_safe(source, destination, same_file=resolve_same_file),
                same_file=resolve_same_file,
            )

            self.assertEqual(errors, [])
            self.assertTrue(first_source.exists())
            self.assertTrue(second_source.exists())
            self.assertFalse(first_destination.exists())
            self.assertFalse(second_destination.exists())


if __name__ == "__main__":
    unittest.main()
