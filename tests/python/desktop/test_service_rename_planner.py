from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.service import RenameServiceMixin
from mediapipeline.core.rename.planner import plan_rename_paths_for_service
from mediapipeline.core.rename.path_authority import (
    annotate_rename_plan_path_authority,
    rename_authority_fields_for_source,
)


class DummyRenamePlannerService(RenameServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_rename_planner")
        self.logger.addHandler(logging.NullHandler())


class RenamePlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DummyRenamePlannerService()

    def test_plan_helper_matches_service_tv_prediction_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            source.write_text("x", encoding="utf-8")

            direct = plan_rename_paths_for_service(
                self.service,
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )
            via_service = self.service.plan_rename_paths(
                [source],
                mode="tv",
                show_name="",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

            self.assertEqual(direct, via_service)
            self.assertEqual(direct[0]["target_name"], "Serial Experiments Lain - S01E01 - Weird.mkv")

    def test_plan_helper_rejects_invalid_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "tv or movie"):
            plan_rename_paths_for_service(self.service, [Path("example.mkv")], mode="music")

    def test_duplicate_destination_marks_every_colliding_row_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "Show E01.mkv"
            second = Path(td) / "Show E02.mkv"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")

            plan = plan_rename_paths_for_service(
                self.service,
                [first, second],
                mode="tv",
                show_name="Show",
                season_value="S01",
                start_episode_value="E01",
                final_name_overrides={
                    str(first): "Show - S01E01.mkv",
                    str(second): "Show - S01E01.mkv",
                },
                use_pipeline_naming_preview=False,
            )

        self.assertEqual([row["status"] for row in plan], ["blocked", "blocked"])
        self.assertEqual([row["change_kind"] for row in plan], ["blocked", "blocked"])
        self.assertTrue(
            all("two selected files would produce the same destination" in row["errors"] for row in plan)
        )
        self.assertTrue(all(row["confidence"] == "blocked" for row in plan))

    def test_duplicate_movie_title_fixture_marks_every_colliding_row_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "Feature.Part.1.mkv"
            second = Path(td) / "Feature.Part.2.mkv"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")

            plan = plan_rename_paths_for_service(
                self.service,
                [first, second],
                mode="movie",
                movie_title="Duplicate Feature",
                movie_year="2024",
                use_pipeline_naming_preview=False,
            )

        self.assertEqual([row["target_name"] for row in plan], ["Duplicate Feature (2024).mkv"] * 2)
        self.assertEqual([row["status"] for row in plan], ["blocked", "blocked"])
        self.assertTrue(
            all("two selected files would produce the same destination" in row["errors"] for row in plan)
        )

    def test_manual_tv_template_aligns_series_and_season_folder_destination(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_folder = root / "Last of Us" / "Season 1"
            source_folder.mkdir(parents=True)
            first = source_folder / "TLOU.S01E01.When.Youre.Lost.in.the.Dark.1080p.WEB-DL.mkv"
            second = source_folder / "TLOU.S01E02.Infected.1080p.WEB-DL.mkv"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")

            plan = plan_rename_paths_for_service(
                self.service,
                [first, second],
                mode="tv",
                show_name="The Last of Us",
                season_value="S01",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

        expected_parent = root / "The Last of Us" / "Season 01"
        self.assertEqual([row["destination_parent"] for row in plan], [str(expected_parent), str(expected_parent)])
        self.assertEqual([row["series_folder"] for row in plan], [str(root / "The Last of Us")] * 2)
        self.assertEqual([row["season_folder"] for row in plan], [str(expected_parent), str(expected_parent)])
        self.assertEqual([row["hierarchy_aligned"] for row in plan], [True, True])
        self.assertEqual([row["mutation_root"] for row in plan], [str(root), str(root)])
        self.assertEqual(
            [row["target_name"] for row in plan],
            [
                "The Last of Us - S01E01 - When Youre Lost in the Dark.mkv",
                "The Last of Us - S01E02 - Infected.mkv",
            ],
        )

    def test_sidecar_inputs_do_not_consume_manual_tv_episode_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "Ranma - S01E19.mkv"
            second = root / "Ranma - S01E20.mkv"
            first_sidecar = first.with_suffix(".pipeline.json")
            second_sidecar = second.with_suffix(".pipeline.json")
            first.write_text("media", encoding="utf-8")
            second.write_text("media", encoding="utf-8")
            first_sidecar.write_text("{}", encoding="utf-8")
            second_sidecar.write_text("{}", encoding="utf-8")

            plan = plan_rename_paths_for_service(
                self.service,
                [first, first_sidecar, second, second_sidecar],
                mode="tv",
                show_name="Ranma",
                season_value="S02",
                start_episode_value="E01",
                use_pipeline_naming_preview=False,
            )

        self.assertEqual([row["source"] for row in plan], [first, second])
        self.assertEqual([row["target_name"] for row in plan], ["Ranma - S02E01.mkv", "Ranma - S02E02.mkv"])
        self.assertEqual([row["sidecar_count"] for row in plan], [1, 1])
        aligned_parent = root / "Ranma" / "Season 02"
        self.assertEqual([row["destination_parent"] for row in plan], [str(aligned_parent), str(aligned_parent)])
        self.assertEqual(plan[0]["sidecar_moves"][0]["source"], str(first_sidecar))
        self.assertEqual(plan[0]["sidecar_moves"][0]["destination"], str(aligned_parent / "Ranma - S02E01.pipeline.json"))
        self.assertEqual(plan[1]["sidecar_moves"][0]["source"], str(second_sidecar))
        self.assertEqual(plan[1]["sidecar_moves"][0]["destination"], str(aligned_parent / "Ranma - S02E02.pipeline.json"))

    def test_unc_configured_media_root_marks_unc_child_ready_without_share_mutation(self) -> None:
        fields = rename_authority_fields_for_source(
            r"\\media-server\TV\Example\S01E01.mkv",
            [Path(r"\\media-server\TV")],
        )

        self.assertEqual(fields["path_authority"], "configured_media_root")
        self.assertEqual(fields["path_authority_status"], "ready")

    def test_destination_outside_source_configured_root_requires_outside_authority(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            configured_season = root / "Original Show" / "Season 01"
            configured_season.mkdir(parents=True)
            source = configured_season / "Episode 01.mkv"
            source.write_text("media", encoding="utf-8")
            destination = root / "Renamed Show" / "Season 01" / "Renamed Show - S01E01.mkv"

            rows = annotate_rename_plan_path_authority(
                [{"source": source, "destination": destination, "sidecar_moves": []}],
                [configured_season],
            )

        self.assertEqual(rows[0]["path_authority"], "outside_configured_roots")
        self.assertEqual(rows[0]["path_authority_status"], "review")
        self.assertIn(str(destination), rows[0]["path_authority_outside_paths"])


if __name__ == "__main__":
    unittest.main()
