from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from app.rename.policy import OUTSIDE_CONFIGURED_ROOTS_WARNING
from DesktopApp.tests.test_application_facade import DummyWorkflowFacadeService


class ApplicationFacadeRenameTests(unittest.TestCase):
    def test_rename_preview_uses_existing_tv_scrub_logic(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Season 02" / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            media.parent.mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"media")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_rename_preview(
                {
                    "paths": [str(media)],
                    "mode": "tv",
                    "season": "S02",
                    "remove_terms_text": "",
                    "use_pipeline_naming_preview": False,
                }
            ).to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_rename_preview.v1")
        self.assertEqual(preview["counts"]["total"], 1)
        self.assertIn(preview["rows"][0]["status"], {"ready", "match", "warning"})
        self.assertEqual(preview["rows"][0]["pipeline_guess"], "Serial Experiments Lain - S02E01 - Weird.mkv")
        self.assertEqual(preview["rows"][0]["preview_source"], "auto_tv_heuristic")
        self.assertEqual(preview["rows"][0]["confidence"], "medium")
        self.assertEqual(preview["rows"][0]["change_kind"], "rename")
        self.assertEqual(preview["rows"][0]["source_parent"], str(media.parent))
        self.assertEqual(preview["rows"][0]["destination_parent"], str(media.parent))
        self.assertEqual(preview["rows"][0]["sidecar_count"], 0)
        self.assertFalse(preview["rows"][0]["destination_exists"])
        self.assertTrue(preview["rows"][0]["confidence_reasons"])
        self.assertEqual(preview["confidence_counts"], {"medium": 1})
        self.assertEqual(preview["preview_source_counts"], {"auto_tv_heuristic": 1})
        self.assertEqual(preview["change_kind_counts"], {"rename": 1})
        self.assertEqual(preview["active_template"], "tv_standard")
        self.assertTrue(any(item["key"] == "tv_no_episode_title" for item in preview["template_catalog"]))

    def test_rename_apply_requires_confirmation_and_applies_selected_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first = root / "Serial Experiments Lain E01 Weird.mkv"
            second = root / "Serial Experiments Lain E02 Girls.mkv"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            request = {
                "paths": [str(first), str(second)],
                "mode": "tv",
                "show_name": "Serial Experiments Lain",
                "season": "S01",
                "start_episode": "E01",
                "selected_sources": [str(first)],
            }

            rejected = facade.apply_rename_selection(dict(request))
            string_rejected = facade.apply_rename_selection({**request, "confirm_apply": "false"})
            applied = facade.apply_rename_selection({**request, "confirm_apply": True})
            renamed_first = root / "Serial Experiments Lain - S01E01 - Weird.mkv"
            renamed_second = root / "Serial Experiments Lain - S01E02 - Girls.mkv"

            self.assertFalse(rejected.ok)
            self.assertIn("confirmation", rejected.message)
            self.assertFalse(string_rejected.ok)
            self.assertIn("confirmation", string_rejected.message)
            self.assertTrue(applied.ok)
            self.assertEqual(applied.command, "rename.apply")
            self.assertEqual(applied.data["selected"], 1)
            self.assertEqual(applied.data["renamed"], 1)
            self.assertEqual(applied.data["unchanged"], 0)
            self.assertEqual(applied.data["media_operations"], 1)
            self.assertEqual(applied.data["sidecar_operations"], 0)
            self.assertEqual(applied.data["rename_progress"]["schema_version"], "desktop_rename_apply_progress.v1")
            self.assertEqual(applied.data["progress_bars"][0]["id"], "rename_apply")
            self.assertEqual(applied.data["progress_bars"][0]["percent"], 100.0)
            self.assertTrue(renamed_first.exists())
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())
            self.assertFalse(renamed_second.exists())
            Path(str(applied.data["undo_manifest"])).unlink(missing_ok=True)

    def test_rename_preview_marks_paths_outside_configured_media_roots(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            configured = root / "ConfiguredMovies"
            outside = root / "StandaloneFolder"
            configured.mkdir()
            outside.mkdir()
            media = outside / "Example Movie 2024 1080p BluRay.mkv"
            media.write_text("media", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_rename_preview(
                {
                    "paths": [str(media)],
                    "_configured_media_roots": [str(configured)],
                    "mode": "movie",
                    "movie_title": "Example Movie",
                    "movie_year": "2024",
                    "use_pipeline_naming_preview": False,
                }
            ).to_mapping()

        row = preview["rows"][0]
        self.assertEqual(row["path_authority"], "outside_configured_roots")
        self.assertEqual(row["path_authority_status"], "review")
        self.assertEqual(row["status"], "warning")
        self.assertEqual(row["confidence"], "review")
        self.assertIn(OUTSIDE_CONFIGURED_ROOTS_WARNING, row["warnings"])

    def test_rename_clean_filename_preview_uses_backend_movie_cleaner(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            default_preview = facade.get_rename_clean_filename_preview(
                {
                    "filename": "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir",
                    "movie_filter_options": {
                        "video_source": True,
                        "audio_channels": True,
                        "editions": True,
                        "file_size": True,
                        "services_containers": True,
                        "release_groups": True,
                    },
                }
            )
            editable_preview = facade.get_rename_clean_filename_preview(
                {
                    "filename": "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv",
                    "movie_filter_terms": {"release_groups": ["neonoir"]},
                    "movie_filter_options": {"release_groups": True},
                }
            )
            catalog = facade.get_rename_movie_filter_catalog()

        self.assertEqual(default_preview["schema_version"], "desktop_rename_clean_filename_preview.v1")
        self.assertTrue(default_preview["ok"])
        self.assertEqual(default_preview["target_name"], "Together (2025)")
        self.assertTrue(default_preview["assumed_media_extension"])
        self.assertTrue(default_preview["warnings"])
        self.assertEqual(editable_preview["target_name"], "Together (2025).mkv")
        self.assertTrue(editable_preview["movie_filter_terms_enabled"])
        self.assertEqual(editable_preview["movie_filter_terms_mode"], "always_on")
        self.assertEqual(editable_preview["movie_filter_term_counts"], {"release_groups": 1})
        self.assertEqual(catalog["schema_version"], "desktop_rename_movie_filter_catalog.v1")
        self.assertTrue(catalog["movie_filter_terms_enabled"])
        self.assertIn("cmrg", catalog["default_terms"]["release_groups"])
        self.assertIn("neonoir", catalog["default_terms"]["release_groups"])

    def test_rename_apply_requires_extra_confirmation_for_outside_configured_roots(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            configured = root / "ConfiguredMovies"
            outside = root / "StandaloneFolder"
            configured.mkdir()
            outside.mkdir()
            media = outside / "Example Movie 2024 1080p BluRay.mkv"
            media.write_text("media", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            request = {
                "paths": [str(media)],
                "_configured_media_roots": [str(configured)],
                "mode": "movie",
                "movie_title": "Example Movie",
                "movie_year": "2024",
                "selected_sources": [str(media)],
                "confirm_apply": True,
                "use_pipeline_naming_preview": False,
            }

            rejected = facade.apply_rename_selection(dict(request))
            string_rejected = facade.apply_rename_selection({**request, "allow_outside_configured_roots": "false"})
            allowed = facade.apply_rename_selection({**request, "allow_outside_configured_roots": True})

            renamed = outside / "Example Movie (2024).mkv"
            self.assertFalse(rejected.ok)
            self.assertIn("outside configured media roots", rejected.message)
            self.assertFalse(string_rejected.ok)
            self.assertIn("outside configured media roots", string_rejected.message)
            self.assertTrue(allowed.ok)
            self.assertTrue(renamed.exists())
            self.assertFalse(media.exists())
            Path(str(allowed.data["undo_manifest"])).unlink(missing_ok=True)

    def test_rename_apply_accepts_multiple_selected_sources(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            first = root / "Serial Experiments Lain E01 Weird.mkv"
            second = root / "Serial Experiments Lain E02 Girls.mkv"
            third = root / "Serial Experiments Lain E03 Psyche.mkv"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")
            third.write_text("c", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            applied = facade.apply_rename_selection(
                {
                    "paths": [str(first), str(second), str(third)],
                    "mode": "tv",
                    "show_name": "Serial Experiments Lain",
                    "season": "S01",
                    "start_episode": "E01",
                    "selected_sources": [str(first), str(third)],
                    "confirm_apply": True,
                }
            )

            renamed_first = root / "Serial Experiments Lain - S01E01 - Weird.mkv"
            renamed_second = root / "Serial Experiments Lain - S01E02 - Girls.mkv"
            renamed_third = root / "Serial Experiments Lain - S01E03 - Psyche.mkv"
            self.assertTrue(applied.ok)
            self.assertEqual(applied.data["selected"], 2)
            self.assertEqual(applied.data["renamed"], 2)
            self.assertEqual(applied.data["progress_bars"][0]["detail"].split(";")[0], "2 renamed / 2 planned")
            self.assertTrue(renamed_first.exists())
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())
            self.assertFalse(renamed_second.exists())
            self.assertTrue(renamed_third.exists())
            self.assertFalse(third.exists())
            Path(str(applied.data["undo_manifest"])).unlink(missing_ok=True)

    def test_rename_apply_uses_backend_apply_lock_before_building_plan(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Serial Experiments Lain E01 Weird.mkv"
            service = DummyWorkflowFacadeService(root)
            plan_calls: list[dict[str, object]] = []

            def fake_plan(*args: object, **kwargs: object) -> list[dict[str, object]]:
                plan_calls.append({"args": args, "kwargs": kwargs})
                return []

            service.plan_rename_paths = fake_plan  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)

            self.assertTrue(facade._rename_apply_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                result = facade.apply_rename_selection(
                    {
                        "paths": [str(source)],
                        "selected_sources": [str(source)],
                        "confirm_apply": True,
                    }
                )
            finally:
                facade._rename_apply_lock.release()  # type: ignore[attr-defined]

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "rename.apply")
        self.assertEqual(result.severity, "warning")
        self.assertIn("another rename apply command is already in progress", result.message)
        self.assertEqual(plan_calls, [])
