from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.storage.constants import APP_STATE_NAME
from app.rename.service import RenameServiceMixin
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


class DummyRenameService(RenameServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_rename_service")
        self.logger.addHandler(logging.NullHandler())


class RenameServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DummyRenameService()

    def test_discover_uses_natural_sort_for_episode_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("Show.10.mkv", "Show.1.mkv", "Show.2.mkv"):
                (root / name).write_text("x", encoding="utf-8")

            names = [path.name for path in self.service.discover_rename_media_files(root)]

            self.assertEqual(names, ["Show.1.mkv", "Show.2.mkv", "Show.10.mkv"])

    def test_rename_undo_manifest_uses_state_root_when_app_state_is_state_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.service.app_state_path = root / "State" / "App" / APP_STATE_NAME  # type: ignore[attr-defined]

            path = self.service._write_rename_undo_manifest({"operations": []})

            self.assertEqual(path.parent, root / "State" / "RenameUndo")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["path"], str(path))

    def test_rename_undo_manifest_uses_state_root_for_legacy_app_state_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.service.app_root = root  # type: ignore[attr-defined]
            self.service.app_state_path = root / APP_STATE_NAME  # type: ignore[attr-defined]

            path = self.service._write_rename_undo_manifest({"operations": []})

            self.assertEqual(path.parent, root / "State" / "RenameUndo")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["path"], str(path))

    def test_rename_undo_manifest_uses_app_root_state_when_app_state_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.service.app_root = root  # type: ignore[attr-defined]

            path = self.service._write_rename_undo_manifest({"operations": []})

            self.assertEqual(path.parent, root / "State" / "RenameUndo")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["path"], str(path))

    def test_movie_prediction_matches_pipeline_clean_name_for_release_filename(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "[RARBG] The.Matrix.(1999).1080p.BluRay.x265.TrueHD.Atmos.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths([source], mode="movie")

            self.assertEqual(plan[0]["pipeline_guess"], "The Matrix (1999).mkv")
            self.assertEqual(plan[0]["target_name"], "The Matrix (1999).mkv")
            self.assertEqual(plan[0]["preview_source"], "movie_scrub_heuristic")
            self.assertEqual(plan[0]["confidence"], "medium")

    def test_movie_prediction_uses_pipeline_preview_runner_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "[RARBG] The.Matrix.(1999).1080p.BluRay.x265.TrueHD.Atmos.mkv"
            source.write_text("x", encoding="utf-8")
            script = root / "Get-MediaPipelineNamingPreview.ps1"
            script.write_text("# test", encoding="utf-8")

            def fake_run(args, **_kwargs):
                output_path = Path(args[args.index("-OutputJsonPath") + 1])
                output_path.write_text(
                    json.dumps(
                        {
                            "rows": [
                                {
                                    "ok": True,
                                    "source_path": str(source),
                                    "file_name": "Pipeline Clean Name.mkv",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                return CapturedCommandResult(args=args, returncode=0, stdout="", stderr="")

            with patch.object(self.service, "_naming_preview_script_path", return_value=script):
                with patch("app.rename.service.run_capture", fake_run):
                    plan = self.service.plan_rename_paths(
                        [source],
                        mode="movie",
                        powershell_host="pwsh",
                    )

            self.assertEqual(plan[0]["pipeline_guess"], "Pipeline Clean Name.mkv")
            self.assertEqual(plan[0]["target_name"], "Pipeline Clean Name.mkv")
            self.assertEqual(plan[0]["preview_source"], "pipeline_movie_preview")
            self.assertEqual(plan[0]["confidence"], "high")

    def test_force_pipeline_name_can_be_set_per_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "Show.1.mkv"
            second = Path(td) / "Show.2.mkv"
            first.write_text("x", encoding="utf-8")
            second.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [first, second],
                mode="tv",
                show_name="Example",
                season_value="S01",
                start_episode_value="E01",
                force_pipeline_name=False,
                force_pipeline_name_overrides={str(first).casefold(): True},
            )

            self.assertTrue(plan[0]["force_pipeline_name"])
            self.assertFalse(plan[1]["force_pipeline_name"])

    def test_tv_prediction_autodetects_show_episode_and_confident_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S01E01 - Weird.mkv")
            self.assertEqual(plan[0]["target_name"], "Serial Experiments Lain - S01E01 - Weird.mkv")
            self.assertEqual(plan[0]["preview_source"], "auto_tv_heuristic")
            self.assertEqual(plan[0]["confidence"], "medium")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_template_can_omit_episode_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
                template_preset="tv_no_episode_title",
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S01E01.mkv")
            self.assertEqual(plan[0]["target_name"], "Serial Experiments Lain - S01E01.mkv")
            self.assertEqual(plan[0]["template_preset"], "tv_no_episode_title")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_prediction_uses_folder_season_for_episode_only_filename(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for folder_name in (
                "Serial Experiments Lain Season 2",
                "Serial Experiments Lain - Season 2",
                "Serial Experiments Lain.Season.2",
                "Serial Experiments Lain S2",
                "Serial Experiments Lain S 2",
                "Serial Experiments Lain.S02",
                "Serial Experiments Lain (Season 2)",
                "[Group] Serial Experiments Lain Season 2 [1080p]",
                "Serial Experiments Lain Season 2 Complete",
                "Serial Experiments Lain - 2nd Season",
            ):
                with self.subTest(folder_name=folder_name):
                    folder = Path(td) / folder_name
                    folder.mkdir(parents=True)
                    source = folder / "E01 Reboot 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
                    source.write_text("x", encoding="utf-8")

                    plan = self.service.plan_rename_paths(
                        [source],
                        mode="tv",
                        show_name="",
                        season_value="S01",
                        start_episode_value="E01",
                        use_pipeline_naming_preview=False,
                    )

                    self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S02E01 - Reboot.mkv")
                    self.assertEqual(plan[0]["preview_source"], "auto_tv_heuristic")
                    self.assertIn("Auto TV scrub inferred", " ".join(plan[0]["confidence_reasons"]))
                    self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_prediction_uses_release_tagged_folder_season_and_filename_show(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Serial Experiments Lain 1998 Season 02 1080p BluRay FLAC 2.0 x264-Chotab"
            folder.mkdir(parents=True)
            source = folder / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S02E01 - Weird.mkv")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_prediction_defaults_episode_only_filename_to_season_one(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Serial Experiments Lain"
            folder.mkdir(parents=True)
            source = folder / "E02 Girls 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S01E02 - Girls.mkv")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_prediction_ignores_far_specials_ancestor_for_plain_show_folder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Extras" / "Library" / "Serial Experiments Lain"
            folder.mkdir(parents=True)
            source = folder / "E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S01E01 - Weird.mkv")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_prediction_uses_filename_season_before_episode_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Serial Experiments Lain S02 E03 Reset 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S02E03 - Reset.mkv")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_prediction_uses_specials_folder_as_season_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Serial Experiments Lain" / "OVA"
            folder.mkdir(parents=True)
            source = folder / "E01 Extra Layer 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S00E01 - Extra Layer.mkv")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_filename_season_overrides_specials_folder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Serial Experiments Lain" / "Extras"
            folder.mkdir(parents=True)
            source = folder / "Serial Experiments Lain S01E04 Religion 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Serial Experiments Lain - S01E04 - Religion.mkv")
            self.assertNotEqual(plan[0]["status"], "blocked")

    def test_tv_manual_sequence_can_append_confident_episode_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Noisy.Show.E22.Miscalled.Title.1080p.x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="Clean Show",
                season_value="S02",
                start_episode_value="E22",
            )

            self.assertEqual(plan[0]["pipeline_guess"], "Clean Show - S02E22 - Miscalled Title.mkv")

    def test_apply_updates_renamed_pipeline_sidecar_output_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Noisy.Movie.2020.mkv"
            source.write_text("x", encoding="utf-8")
            sidecar = source.with_suffix(".pipeline.json")
            sidecar.write_text(
                json.dumps({"schema_version": "pipeline_sidecar.v1", "output_path": str(source), "output_file": source.name}),
                encoding="utf-8",
            )

            plan = self.service.plan_rename_paths(
                [source],
                mode="movie",
                movie_title="Clean Movie",
                movie_year="2020",
                rename_sidecars=True,
            )
            summary = self.service.apply_rename_path_plan(plan)
            new_path = Path(td) / "Clean Movie (2020).mkv"
            new_sidecar = new_path.with_suffix(".pipeline.json")
            data = json.loads(new_sidecar.read_text(encoding="utf-8"))

            self.assertTrue(new_path.exists())
            self.assertFalse(source.exists())
            self.assertEqual(data["output_path"], str(new_path))
            self.assertEqual(data["output_file"], new_path.name)
            self.assertEqual(data["RenameTool"]["FinalName"], new_path.name)
            Path(str(summary["undo_manifest"])).unlink(missing_ok=True)

    def test_apply_rolls_back_prior_renames_when_later_row_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "one.mkv"
            second = Path(td) / "two.mkv"
            first.write_text("x", encoding="utf-8")
            second.write_text("x", encoding="utf-8")
            plan = self.service.plan_rename_paths(
                [first, second],
                mode="tv",
                show_name="Example",
                season_value="S01",
                start_episode_value="E01",
            )
            original_rename = self.service._rename_path_case_safe
            original_manifest_write = self.service._write_rename_undo_manifest
            undo_paths: list[Path] = []

            def fail_second(source: Path, destination: Path) -> None:
                if source.name == "two.mkv":
                    raise PermissionError("locked")
                original_rename(source, destination)

            def record_manifest(manifest: dict) -> Path:
                path = original_manifest_write(manifest)
                undo_paths.append(path)
                return path

            self.service._rename_path_case_safe = fail_second  # type: ignore[method-assign]
            self.service._write_rename_undo_manifest = record_manifest  # type: ignore[method-assign]

            try:
                with self.assertRaises(PermissionError):
                    self.service.apply_rename_path_plan(plan)
            finally:
                for path in set(undo_paths):
                    path.unlink(missing_ok=True)

            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertFalse((Path(td) / "Example - S01E01.mkv").exists())

    def test_apply_restores_pipeline_sidecar_text_when_metadata_update_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "one.mkv"
            second = Path(td) / "two.mkv"
            first.write_text("x", encoding="utf-8")
            second.write_text("x", encoding="utf-8")
            first_sidecar = first.with_suffix(".pipeline.json")
            second_sidecar = second.with_suffix(".pipeline.json")
            first_original = '{"schema_version":"pipeline_sidecar.v1","output_path":"one","output_file":"one.mkv"}\n'
            second_original = '{"schema_version":"pipeline_sidecar.v1","output_path":"two","output_file":"two.mkv"}\n'
            first_sidecar.write_text(first_original, encoding="utf-8")
            second_sidecar.write_text(second_original, encoding="utf-8")

            plan = self.service.plan_rename_paths(
                [first, second],
                mode="tv",
                show_name="Example",
                season_value="S01",
                start_episode_value="E01",
                rename_sidecars=True,
            )
            original_update = self.service._update_pipeline_sidecar_after_rename
            original_manifest_write = self.service._write_rename_undo_manifest
            undo_paths: list[Path] = []

            def fail_second_sidecar(path: Path, payload: dict, destination: Path) -> None:
                if "S01E02" in path.name:
                    raise RuntimeError("sidecar update failed")
                original_update(path, payload, destination)

            def record_manifest(manifest: dict) -> Path:
                path = original_manifest_write(manifest)
                undo_paths.append(path)
                return path

            self.service._update_pipeline_sidecar_after_rename = fail_second_sidecar  # type: ignore[method-assign]
            self.service._write_rename_undo_manifest = record_manifest  # type: ignore[method-assign]

            try:
                with self.assertRaisesRegex(RuntimeError, "sidecar update failed"):
                    self.service.apply_rename_path_plan(plan)
            finally:
                for path in set(undo_paths):
                    path.unlink(missing_ok=True)

            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertTrue(first_sidecar.exists())
            self.assertTrue(second_sidecar.exists())
            self.assertEqual(first_sidecar.read_text(encoding="utf-8"), first_original)
            self.assertEqual(second_sidecar.read_text(encoding="utf-8"), second_original)
            self.assertFalse((Path(td) / "Example - S01E01.pipeline.json").exists())


if __name__ == "__main__":
    unittest.main()
