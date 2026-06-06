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
from mediapipeline.core.rename.path_authority import rename_authority_fields_for_source


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

    def test_unc_configured_media_root_marks_unc_child_ready_without_share_mutation(self) -> None:
        fields = rename_authority_fields_for_source(
            r"\\media-server\TV\Example\S01E01.mkv",
            [Path(r"\\media-server\TV")],
        )

        self.assertEqual(fields["path_authority"], "configured_media_root")
        self.assertEqual(fields["path_authority_status"], "ready")


if __name__ == "__main__":
    unittest.main()
