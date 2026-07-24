from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.service import RenameServiceMixin
from mediapipeline.core.rename.apply_runner import apply_rename_path_plan_for_service
import mediapipeline.core.rename.undo_runner as undo_runner


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

    def test_apply_runner_moves_manual_tv_batch_into_aligned_show_season_folder_and_undo_restores(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_folder = root / "Last of Us" / "Season 1"
            source_folder.mkdir(parents=True)
            source = source_folder / "TLOU.S01E01.When.Youre.Lost.in.the.Dark.1080p.WEB-DL.mkv"
            source.write_text("media", encoding="utf-8")
            undo_root = root / "State" / "RenameUndo"
            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="The Last of Us",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
                rename_sidecars=False,
            )

            result = apply_rename_path_plan_for_service(self.service, plan, undo_manifest_root=undo_root)
            destination = root / "The Last of Us" / "Season 01" / "The Last of Us - S01E01 - When Youre Lost in the Dark.mkv"
            manifest = Path(str(result["undo_manifest"]))
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            destination_exists_after_apply = destination.exists()
            source_exists_after_apply = source.exists()
            undone = self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            self.assertEqual(result["renamed"], 1)
            self.assertEqual(manifest_data["operations"][0]["boundary_root"], str(root))
            self.assertTrue(destination_exists_after_apply)
            self.assertFalse(source_exists_after_apply)
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())
            self.assertEqual(undone["undone"], 1)

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

    def test_multi_episode_apply_and_undo_preserve_range_identity_in_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Example Show S01E01-E02.mkv"
            sidecar = root / "Example Show S01E01-E02.pipeline.json"
            undo_root = root / "State" / "RenameUndo"
            source.write_text("media", encoding="utf-8")
            sidecar.write_text(json.dumps({"output_path": str(source), "output_file": source.name}), encoding="utf-8")
            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                use_pipeline_naming_preview=False,
                rename_sidecars=True,
            )

            applied = apply_rename_path_plan_for_service(self.service, plan, undo_manifest_root=undo_root)
            destination = root / "Example Show - S01E01-E02.mkv"
            destination_sidecar = root / "Example Show - S01E01-E02.pipeline.json"
            sidecar_payload = json.loads(destination_sidecar.read_text(encoding="utf-8"))
            undo_manifest = Path(str(applied["undo_manifest"]))
            undo_payload = json.loads(undo_manifest.read_text(encoding="utf-8"))
            undone = self.service.undo_rename_manifest(undo_manifest, undo_manifest_root=undo_root)

            self.assertTrue(source.exists())
            self.assertTrue(sidecar.exists())
            self.assertFalse(destination.exists())
            self.assertFalse(destination_sidecar.exists())
            self.assertEqual(sidecar_payload["RenameTool"]["TVIdentity"]["episode_end"], 2)
            self.assertIn("S01E01-E02", sidecar_payload["RenameTool"]["DestinationIdentityKey"])
            media_operation = next(item for item in undo_payload["operations"] if item["kind"] == "media")
            self.assertEqual(media_operation["tv_identity"]["episode_end"], 2)
            self.assertEqual(media_operation["parsed_identity"]["episode_end"], 2)
            undone_media = next(item for item in undone["rows"] if item["kind"] == "media")
            self.assertEqual(undone_media["parsed_identity"]["episode_end"], 2)
            self.assertEqual(undone_media["destination_identity_key"], media_operation["destination_identity_key"])
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

    def test_undo_manifest_rejects_metadata_backup_outside_operation_boundary_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            boundary = root / "Library"
            boundary.mkdir()
            source = boundary / "Original.mkv"
            destination = boundary / "Renamed.mkv"
            destination.write_text("media", encoding="utf-8")
            outside = root / "outside.json"
            outside.write_text("do-not-touch", encoding="utf-8")
            undo_root = root / "State" / "RenameUndo"
            undo_root.mkdir(parents=True)
            undo_manifest = undo_root / "rename-undo.json"
            undo_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "rename_undo.v1",
                        "status": "completed",
                        "operations": [
                            {
                                "kind": "media",
                                "source": str(source),
                                "destination": str(destination),
                                "boundary_root": str(boundary),
                            }
                        ],
                        "metadata_backups": [
                            {
                                "path": str(outside),
                                "content": "malicious",
                                "operation_destination": str(destination),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "metadata backup"):
                self.service.undo_rename_manifest(undo_manifest, undo_manifest_root=undo_root)

            self.assertEqual(outside.read_text(encoding="utf-8"), "do-not-touch")
            self.assertTrue(destination.exists())
            self.assertFalse(source.exists())

    def test_undo_manifest_checkpoints_each_operation_and_resumes_after_mid_loop_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            undo_root, manifest, paths = self._write_two_operation_undo_fixture(root)
            before_hashes = {
                name: sha256(path.read_bytes()).hexdigest()
                for name, path in paths.items()
                if name.startswith("destination")
            }
            real_rename = self.service._rename_path_case_safe
            rename_calls = 0

            def fail_second_rename(source: Path, destination: Path, *, boundary_root: Path) -> None:
                nonlocal rename_calls
                rename_calls += 1
                if rename_calls == 2:
                    raise OSError("injected sharing violation")
                real_rename(source, destination, boundary_root=boundary_root)

            with patch.object(self.service, "_rename_path_case_safe", side_effect=fail_second_rename):
                with self.assertRaisesRegex(OSError, "injected sharing violation"):
                    self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            failed = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(failed["undo_status"], "failed")
            self.assertEqual(
                [item["status"] for item in failed["undo_progress"]["operations"]],
                ["prepared", "committed"],
            )
            self.assertTrue(paths["destination_one"].exists())
            self.assertTrue(paths["source_two"].exists())

            resumed = self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            self.assertEqual(resumed["undone"], 1)
            self.assertEqual(resumed["skipped"], 1)
            self.assertFalse(paths["destination_one"].exists())
            self.assertFalse(paths["destination_two"].exists())
            self.assertEqual(sha256(paths["source_one"].read_bytes()).hexdigest(), before_hashes["destination_one"])
            self.assertEqual(sha256(paths["source_two"].read_bytes()).hexdigest(), before_hashes["destination_two"])
            completed = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(completed["undo_status"], "completed")
            self.assertTrue(all(item["status"] == "committed" for item in completed["undo_progress"]["operations"]))

    def test_undo_manifest_recovers_rename_completed_before_checkpoint_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            undo_root, manifest, paths = self._write_two_operation_undo_fixture(root)
            real_write = undo_runner._write_manifest
            write_calls = 0

            def lose_checkpoint(path: Path, payload: dict[str, object]) -> None:
                nonlocal write_calls
                write_calls += 1
                if write_calls >= 2:
                    raise OSError("injected checkpoint outage")
                real_write(path, payload)

            with patch.object(undo_runner, "_write_manifest", side_effect=lose_checkpoint):
                with self.assertRaisesRegex(OSError, "injected checkpoint outage"):
                    self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            stranded = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(stranded["undo_status"], "undoing")
            self.assertTrue(all(item["status"] == "prepared" for item in stranded["undo_progress"]["operations"]))
            self.assertTrue(paths["source_two"].exists())
            self.assertFalse(paths["destination_two"].exists())

            resumed = self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            self.assertEqual(resumed["undone"], 1)
            self.assertEqual(resumed["skipped"], 1)
            self.assertTrue(paths["source_one"].exists())
            self.assertTrue(paths["source_two"].exists())
            self.assertFalse(paths["destination_one"].exists())
            self.assertFalse(paths["destination_two"].exists())

    def test_undo_manifest_resumes_legacy_mixed_layout_without_progress_journal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            undo_root, manifest, paths = self._write_two_operation_undo_fixture(root)
            paths["destination_two"].rename(paths["source_two"])
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["undo_status"] = "failed"
            payload["undo_errors"] = ["legacy mid-loop failure"]
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            resumed = self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            self.assertEqual(resumed["undone"], 1)
            self.assertEqual(resumed["skipped"], 1)
            self.assertTrue(paths["source_one"].exists())
            self.assertTrue(paths["source_two"].exists())
            self.assertFalse(paths["destination_one"].exists())
            self.assertFalse(paths["destination_two"].exists())
            completed = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(all(item["status"] == "committed" for item in completed["undo_progress"]["operations"]))

    def test_undo_manifest_rejects_progress_identity_tampering_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            undo_root, manifest, paths = self._write_two_operation_undo_fixture(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["undo_progress"] = {
                "schema_version": "rename_undo_progress.v1",
                "operations": [
                    {"operation_index": 0, "operation_id": "tampered", "status": "prepared"},
                    {"operation_index": 1, "operation_id": "tampered", "status": "prepared"},
                ],
            }
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "progress identity"):
                self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            self.assertTrue(paths["destination_one"].exists())
            self.assertTrue(paths["destination_two"].exists())
            self.assertFalse(paths["source_one"].exists())
            self.assertFalse(paths["source_two"].exists())

    def test_undo_manifest_rejects_committed_status_when_layout_is_still_forward(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            undo_root, manifest, paths = self._write_two_operation_undo_fixture(root)
            with patch.object(self.service, "_rename_path_case_safe", side_effect=OSError("fail before mutation")):
                with self.assertRaisesRegex(OSError, "fail before mutation"):
                    self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["undo_progress"]["operations"][0]["status"] = "committed"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "committed original path is missing"):
                self.service.undo_rename_manifest(manifest, undo_manifest_root=undo_root)

            self.assertTrue(paths["destination_one"].exists())
            self.assertTrue(paths["destination_two"].exists())
            self.assertFalse(paths["source_one"].exists())
            self.assertFalse(paths["source_two"].exists())

    @staticmethod
    def _write_two_operation_undo_fixture(root: Path) -> tuple[Path, Path, dict[str, Path]]:
        undo_root = root / "State" / "RenameUndo"
        undo_root.mkdir(parents=True)
        paths = {
            "source_one": root / "Original One.mkv",
            "destination_one": root / "Renamed One.mkv",
            "source_two": root / "Original Two.srt",
            "destination_two": root / "Renamed Two.srt",
        }
        paths["destination_one"].write_bytes(b"media-one-content")
        paths["destination_two"].write_bytes(b"subtitle-two-content")
        manifest = undo_root / "rename-undo.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "rename_undo.v1",
                    "status": "completed",
                    "operations": [
                        {
                            "kind": "media",
                            "source": str(paths["source_one"]),
                            "destination": str(paths["destination_one"]),
                            "boundary_root": str(root),
                        },
                        {
                            "kind": "sidecar",
                            "source": str(paths["source_two"]),
                            "destination": str(paths["destination_two"]),
                            "boundary_root": str(root),
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return undo_root, manifest, paths


if __name__ == "__main__":
    unittest.main()
