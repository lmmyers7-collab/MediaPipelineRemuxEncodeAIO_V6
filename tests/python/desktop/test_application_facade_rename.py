from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.rename.policy import OUTSIDE_CONFIGURED_ROOTS_WARNING, rename_configured_media_roots_from_resolved
from tests.python.desktop.application_facade_test_support import DummyProc, DummyWorkflowFacadeService, _resolved


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
        self.assertTrue(preview["preview_fingerprint"])

    def test_rename_apply_rejects_missing_or_stale_backend_preview_fingerprint_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Noisy Movie 2024.mkv"
            media.write_text("media", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            request = {
                "paths": [str(media)],
                "_configured_media_roots": [str(root)],
                "mode": "movie",
                "movie_title": "Clean Movie",
                "movie_year": "2024",
                "selected_sources": [str(media)],
                "confirm_apply": True,
                "use_pipeline_naming_preview": False,
            }

            missing = facade.apply_rename_selection(dict(request))
            stale = facade.apply_rename_selection({**request, "preview_fingerprint": "stale"})

            self.assertFalse(missing.ok)
            self.assertFalse(stale.ok)
            self.assertIn("preview", missing.message.casefold())
            self.assertIn("stale", stale.message.casefold())
            self.assertTrue(media.exists())
            self.assertFalse((root / "Clean Movie (2024).mkv").exists())

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
                "_configured_media_roots": [str(root)],
                "mode": "tv",
                "show_name": "Serial Experiments Lain",
                "season": "S01",
                "start_episode": "E01",
                "selected_sources": [str(first)],
            }
            request["preview_fingerprint"] = facade.get_rename_preview(request).preview_fingerprint

            rejected = facade.apply_rename_selection(dict(request))
            string_rejected = facade.apply_rename_selection({**request, "confirm_apply": "false"})
            applied = facade.apply_rename_selection({**request, "confirm_apply": True})
            hierarchy_parent = root / "Serial Experiments Lain" / "Season 01"
            renamed_first = hierarchy_parent / "Serial Experiments Lain - S01E01 - Weird.mkv"
            renamed_second = hierarchy_parent / "Serial Experiments Lain - S01E02 - Girls.mkv"

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

    def test_rename_preview_and_apply_treat_sidecar_inputs_as_media_companions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Ranma - S01E19.mkv"
            sidecar = media.with_suffix(".pipeline.json")
            media.write_text("media", encoding="utf-8")
            sidecar.write_text(
                json.dumps({"schema_version": "pipeline_sidecar.v1", "output_path": str(media), "output_file": media.name}),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            request = {
                "paths": [str(media), str(sidecar)],
                "_configured_media_roots": [str(root)],
                "mode": "tv",
                "show_name": "Ranma",
                "season": "S02",
                "start_episode": "E01",
                "selected_sources": [str(media)],
                "use_pipeline_naming_preview": False,
            }

            preview = facade.get_rename_preview(request).to_mapping()
            applied = facade.apply_rename_selection(
                {**request, "confirm_apply": True, "preview_fingerprint": preview["preview_fingerprint"]}
            )
            hierarchy_parent = root / "Ranma" / "Season 02"
            renamed_media = hierarchy_parent / "Ranma - S02E01.mkv"
            renamed_sidecar = hierarchy_parent / "Ranma - S02E01.pipeline.json"

            self.assertEqual(preview["counts"]["total"], 1)
            self.assertEqual(preview["input_counts"]["raw"], 2)
            self.assertEqual(preview["input_counts"]["media"], 1)
            self.assertEqual(preview["input_counts"]["ignored_sidecar"], 1)
            self.assertIn("sidecar", " ".join(preview["warnings"]))
            self.assertEqual(preview["rows"][0]["source"], str(media))
            self.assertEqual(preview["rows"][0]["target_name"], "Ranma - S02E01.mkv")
            self.assertEqual(preview["rows"][0]["sidecar_count"], 1)
            self.assertTrue(applied.ok)
            self.assertEqual(applied.data["media_operations"], 1)
            self.assertEqual(applied.data["sidecar_operations"], 1)
            self.assertTrue(renamed_media.exists())
            self.assertTrue(renamed_sidecar.exists())
            self.assertFalse(media.exists())
            self.assertFalse(sidecar.exists())
            data = json.loads(renamed_sidecar.read_text(encoding="utf-8"))
            self.assertEqual(data["output_file"], renamed_media.name)
            self.assertEqual(data["output_path"], str(renamed_media))
            Path(str(applied.data["undo_manifest"])).unlink(missing_ok=True)

    def test_rename_preview_keeps_outside_configured_media_roots_advisory(self) -> None:
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
        self.assertNotEqual(row["status"], "warning")
        self.assertNotIn(OUTSIDE_CONFIGURED_ROOTS_WARNING, row.get("warnings") or [])
        self.assertNotIn(
            "outside configured media roots",
            " ".join(str(item) for item in row.get("confidence_reasons") or []).casefold(),
        )

    def test_rename_preview_accepts_enabled_library_profile_roots(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            profile_source = root / "AnimeSource"
            profile_output = root / "AnimeOutput"
            profile_final = root / "AnimeFinal"
            disabled_source = root / "DisabledSource"
            for directory in (profile_source, profile_output, profile_final, disabled_source):
                directory.mkdir()
            media = profile_final / "Example Movie 2024 1080p BluRay.mkv"
            media.write_text("media", encoding="utf-8")
            resolved = SimpleNamespace(
                source_movies=None,
                source_tv=None,
                config_data={
                    "SourceMovies": str(root / "ConfiguredMovies"),
                    "SourceTV": str(root / "ConfiguredTV"),
                    "Outsource": str(root / "Outsource"),
                    "LibraryProfiles": [
                        {
                            "id": "anime",
                            "enabled": True,
                            "source_path": str(profile_source),
                            "output_path": str(profile_output),
                            "promotion_enabled": True,
                            "promotion_destination": str(profile_final),
                        },
                        {
                            "id": "disabled-anime",
                            "enabled": False,
                            "source_path": str(disabled_source),
                        },
                    ],
                },
            )
            roots = rename_configured_media_roots_from_resolved(resolved)
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))

            preview = facade.get_rename_preview(
                {
                    "paths": [str(media)],
                    "_configured_media_roots": roots,
                    "mode": "movie",
                    "movie_title": "Example Movie",
                    "movie_year": "2024",
                    "use_pipeline_naming_preview": False,
                }
            ).to_mapping()

        row = preview["rows"][0]
        self.assertIn(str(profile_source), roots)
        self.assertIn(str(profile_output), roots)
        self.assertIn(str(profile_final), roots)
        self.assertNotIn(str(disabled_source), roots)
        self.assertEqual(row["path_authority"], "configured_media_root")
        self.assertEqual(row["path_authority_status"], "ready")
        self.assertNotIn(OUTSIDE_CONFIGURED_ROOTS_WARNING, row["warnings"])

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
            tv_preview = facade.get_rename_clean_filename_preview(
                {
                    "mode": "tv",
                    "source_folder": "The Web S01 1080p WEB-DL-TTGA",
                    "filename": "S01E01-Pilot.1080p.WEB-DL-TTGA.mkv",
                    "tv_filter_terms": {"release_groups": ["TTGA"]},
                    "tv_filter_options": {"release_groups": True},
                }
            )
            split_catalog = facade.get_rename_cleaning_filter_catalog()
            catalog = facade.get_rename_movie_filter_catalog()

        self.assertEqual(default_preview["schema_version"], "desktop_rename_clean_filename_preview.v1")
        self.assertTrue(default_preview["ok"])
        self.assertEqual(default_preview["target_name"], "Together (2025)")
        self.assertTrue(default_preview["assumed_media_extension"])
        self.assertTrue(default_preview["warnings"])
        self.assertEqual(editable_preview["target_name"], "Together (2025).mkv")
        self.assertTrue(editable_preview["movie_filter_terms_enabled"])
        self.assertEqual(editable_preview["movie_filter_terms_mode"], "staged")
        self.assertEqual(editable_preview["rename_cleaning_policy_source"], "staged")
        self.assertEqual(editable_preview["movie_filter_term_counts"], {"release_groups": 1})
        self.assertEqual(tv_preview["target_name"], "The Web - S01E01 - Pilot.mkv")
        self.assertEqual(tv_preview["preview_source"], "backend_tv_cleaner")
        self.assertEqual(tv_preview["tv_filter_term_counts"], {"release_groups": 1})
        self.assertEqual(split_catalog["schema_version"], "desktop_rename_cleaning_filter_catalog.v1")
        self.assertIn("movie", split_catalog)
        self.assertIn("tv", split_catalog)
        self.assertIn("ttga", split_catalog["tv"]["default_terms"]["release_groups"])
        self.assertEqual(catalog["schema_version"], "desktop_rename_movie_filter_catalog.v1")
        self.assertTrue(catalog["movie_filter_terms_enabled"])
        self.assertEqual(catalog["movie_filter_terms_mode"], "saved")
        self.assertEqual(catalog["rename_cleaning_policy_source"], "saved")
        self.assertIn("cmrg", catalog["default_terms"]["release_groups"])
        self.assertIn("neonoir", catalog["default_terms"]["release_groups"])
        self.assertIn("saved_terms", catalog)
        self.assertIn("saved_options", catalog)

    def test_rename_workbench_uses_the_synthetic_production_destination_plan_as_actual(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            captured: dict[str, object] = {}

            def fake_production_preview(**kwargs: object) -> dict[str, object]:
                captured.update(kwargs)
                policy = dict(kwargs["cleaning_policy"])  # type: ignore[arg-type]
                fingerprint = str(policy["policy_fingerprint"])
                return {
                    "ok": True,
                    "requested_policy_fingerprint": fingerprint,
                    "applied_policy_fingerprint": fingerprint,
                    "policy_fingerprint_match": True,
                    "row": {
                        "ok": True,
                        "synthetic": True,
                        "file_base_name": "Edge of Tomorrow (2014)",
                        "file_name": "Edge of Tomorrow (2014)",
                        "relative_directory": "Edge of Tomorrow (2014)",
                        "relative_path": "Edge of Tomorrow (2014)\\Edge of Tomorrow (2014)",
                        "identity_key": "Edge of Tomorrow (2014)",
                        "parsed_identity": {
                            "media_kind": "Movie",
                            "title": "Edge of Tomorrow",
                            "year": 2014,
                        },
                    },
                    "error": "",
                }

            service._load_synthetic_pipeline_name_preview = fake_production_preview  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)

            preview = facade.get_rename_clean_filename_preview(
                {
                    "mode": "movie",
                    "filename": "Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
                    "expected_movie_title": "Edge of Tomorrow",
                    "expected_year": "2014",
                    "include_case_analysis": True,
                    "_rename_movie_filter_policy_source": "staged",
                },
                powershell_host="C:/Runtime/pwsh.exe",
                require_production=True,
            )

        self.assertEqual(captured["filename"], "Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265")
        self.assertEqual(captured["source_folder"], "")
        self.assertEqual(captured["media_kind"], "Movie")
        self.assertEqual(captured["powershell_host"], "C:/Runtime/pwsh.exe")
        self.assertEqual(preview["target_name"], "Edge of Tomorrow (2014)")
        self.assertEqual(preview["preview_source"], "pipeline_movie_destination_plan")
        self.assertEqual(preview["evidence_authority"], "production_naming_plan")
        self.assertTrue(preview["policy_fingerprint_match"])
        self.assertEqual(preview["requested_policy_fingerprint"], preview["applied_policy_fingerprint"])
        self.assertEqual(preview["comparison"]["status"], "match")
        self.assertEqual(preview["comparison"]["authority"], "production_naming_plan")
        self.assertTrue(preview["comparison"]["ok"], preview["comparison"])

    def test_rename_workbench_exposes_production_drift_instead_of_the_python_cleaner_result(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            service = DummyWorkflowFacadeService(Path(raw_root))

            def fake_drifted_preview(**kwargs: object) -> dict[str, object]:
                fingerprint = str(dict(kwargs["cleaning_policy"])["policy_fingerprint"])  # type: ignore[arg-type]
                return {
                    "ok": True,
                    "requested_policy_fingerprint": fingerprint,
                    "applied_policy_fingerprint": fingerprint,
                    "policy_fingerprint_match": True,
                    "row": {
                        "ok": True,
                        "synthetic": True,
                        "file_base_name": "Edge of Tomorrow GalaxyRG265 (2014)",
                        "file_name": "Edge of Tomorrow GalaxyRG265 (2014)",
                        "parsed_identity": {
                            "media_kind": "Movie",
                            "title": "Edge of Tomorrow GalaxyRG265",
                            "year": 2014,
                        },
                    },
                    "error": "",
                }

            service._load_synthetic_pipeline_name_preview = fake_drifted_preview  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)
            preview = facade.get_rename_clean_filename_preview(
                {
                    "mode": "movie",
                    "filename": "Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265",
                    "expected_movie_title": "Edge of Tomorrow",
                    "expected_year": "2014",
                    "include_case_analysis": True,
                },
                powershell_host="pwsh",
                require_production=True,
            )

        self.assertEqual(preview["target_name"], "Edge of Tomorrow GalaxyRG265 (2014)")
        self.assertFalse(preview["comparison"]["ok"])
        self.assertEqual(preview["comparison"]["status"], "mismatch")
        self.assertIn("movie_title", preview["comparison"]["failed_fields"])

    def test_rename_workbench_pass_requires_exact_runtime_parity_even_when_production_matches_expected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            service = DummyWorkflowFacadeService(Path(raw_root))
            service._clean_pipeline_movie_name = lambda *_args, **_kwargs: "EDGE OF TOMORROW (2014)"  # type: ignore[method-assign]

            def fake_production_preview(**kwargs: object) -> dict[str, object]:
                fingerprint = str(dict(kwargs["cleaning_policy"])["policy_fingerprint"])  # type: ignore[arg-type]
                return {
                    "ok": True,
                    "requested_policy_fingerprint": fingerprint,
                    "applied_policy_fingerprint": fingerprint,
                    "policy_fingerprint_match": True,
                    "row": {
                        "ok": True,
                        "synthetic": True,
                        "file_base_name": "Edge of Tomorrow (2014)",
                        "file_name": "Edge of Tomorrow (2014)",
                        "parsed_identity": {
                            "media_kind": "Movie",
                            "title": "Edge of Tomorrow",
                            "year": 2014,
                        },
                    },
                    "error": "",
                }

            service._load_synthetic_pipeline_name_preview = fake_production_preview  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)
            preview = facade.get_rename_clean_filename_preview(
                {
                    "mode": "movie",
                    "filename": "Edge.of.Tomorrow.2014.1080p.BluRay.x265-GalaxyRG265",
                    "expected_movie_title": "Edge of Tomorrow",
                    "expected_year": "2014",
                    "include_case_analysis": True,
                },
                powershell_host="pwsh",
                require_production=True,
            )

        self.assertTrue(preview["comparison"]["expected_match"])
        self.assertFalse(preview["comparison"]["ok"])
        self.assertEqual(preview["production_parity"]["status"], "mismatch")
        self.assertEqual(preview["production_parity"]["reference_target_name"], "EDGE OF TOMORROW (2014)")
        self.assertEqual(preview["production_parity"]["production_target_name"], "Edge of Tomorrow (2014)")
        self.assertIn("runtime_parity", preview["comparison"]["failed_fields"])

    def test_rename_workbench_fails_closed_when_production_preview_or_policy_evidence_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            service = DummyWorkflowFacadeService(Path(raw_root))
            facade = MediaPipelineApplicationFacade(service)
            request = {
                "mode": "movie",
                "filename": "Edge.of.Tomorrow.2014.1080p.BluRay.x265-GalaxyRG265.mkv",
                "expected_movie_title": "Edge of Tomorrow",
                "expected_year": "2014",
                "include_case_analysis": True,
            }

            for label, result in (
                (
                    "unavailable",
                    {
                        "ok": False,
                        "requested_policy_fingerprint": "a" * 64,
                        "applied_policy_fingerprint": "",
                        "policy_fingerprint_match": False,
                        "row": {},
                        "error": "pipeline movie synthetic naming preview unavailable",
                    },
                ),
                (
                    "fingerprint mismatch",
                    {
                        "ok": True,
                        "requested_policy_fingerprint": "a" * 64,
                        "applied_policy_fingerprint": "b" * 64,
                        "policy_fingerprint_match": False,
                        "row": {
                            "ok": True,
                            "synthetic": True,
                            "file_base_name": "Edge of Tomorrow (2014)",
                            "file_name": "Edge of Tomorrow (2014).mkv",
                        },
                        "error": "pipeline movie naming preview policy fingerprint mismatch",
                    },
                ),
            ):
                with self.subTest(label=label):
                    service._load_synthetic_pipeline_name_preview = lambda result=result, **_kwargs: result  # type: ignore[method-assign]
                    preview = facade.get_rename_clean_filename_preview(
                        request,
                        powershell_host="pwsh",
                        require_production=True,
                    )
                    self.assertFalse(preview["ok"])
                    self.assertEqual(preview["target_name"], "")
                    self.assertEqual(preview["comparison"]["status"], "unavailable")
                    self.assertFalse(preview["comparison"]["ok"])
                    self.assertEqual(preview["filter_suggestions"], [])
                    self.assertTrue(preview["errors"])

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
            request["preview_fingerprint"] = facade.get_rename_preview(request).preview_fingerprint

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

    def test_rename_apply_blocks_unscoped_operator_paths_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "StandaloneFolder" / "Example Movie 2024 1080p BluRay.mkv"
            media.parent.mkdir()
            media.write_text("media", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root))
            request = {
                "paths": [str(media)],
                "mode": "movie",
                "movie_title": "Example Movie",
                "movie_year": "2024",
                "selected_sources": [str(media)],
                "confirm_apply": True,
                "use_pipeline_naming_preview": False,
            }
            request["preview_fingerprint"] = facade.get_rename_preview(request).preview_fingerprint

            rejected = facade.apply_rename_selection(dict(request))
            outside_confirmation_rejected = facade.apply_rename_selection(
                {**request, "allow_outside_configured_roots": True}
            )

            renamed = media.parent / "Example Movie (2024).mkv"
            self.assertFalse(rejected.ok)
            self.assertEqual(rejected.command, "rename.apply")
            self.assertIn("without configured media-root authority", rejected.message)
            self.assertFalse(outside_confirmation_rejected.ok)
            self.assertIn("without configured media-root authority", outside_confirmation_rejected.message)
            self.assertTrue(media.exists())
            self.assertFalse(renamed.exists())

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

            request = {
                    "paths": [str(first), str(second), str(third)],
                    "_configured_media_roots": [str(root)],
                    "mode": "tv",
                    "show_name": "Serial Experiments Lain",
                    "season": "S01",
                    "start_episode": "E01",
                    "selected_sources": [str(first), str(third)],
                    "confirm_apply": True,
                }
            request["preview_fingerprint"] = facade.get_rename_preview(request).preview_fingerprint
            applied = facade.apply_rename_selection(request)

            hierarchy_parent = root / "Serial Experiments Lain" / "Season 01"
            renamed_first = hierarchy_parent / "Serial Experiments Lain - S01E01 - Weird.mkv"
            renamed_second = hierarchy_parent / "Serial Experiments Lain - S01E02 - Girls.mkv"
            renamed_third = hierarchy_parent / "Serial Experiments Lain - S01E03 - Psyche.mkv"
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

    def test_rename_apply_blocks_active_work_before_building_plan(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "Serial Experiments Lain E01 Weird.mkv"
            source.write_text("media", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            resolved = _resolved(root)
            plan_calls: list[dict[str, object]] = []
            apply_calls: list[object] = []

            service.cleanup_stale_launch_guards = lambda _resolved_paths: []  # type: ignore[method-assign]
            service.find_related_pipeline_processes = lambda _resolved_paths, job_kinds=None: [DummyProc(24681)]  # type: ignore[method-assign]

            def fake_plan(*args: object, **kwargs: object) -> list[dict[str, object]]:
                plan_calls.append({"args": args, "kwargs": kwargs})
                return []

            def fake_apply(*args: object, **kwargs: object) -> dict[str, object]:
                apply_calls.append({"args": args, "kwargs": kwargs})
                return {"renamed": 0, "rows": []}

            service.plan_rename_paths = fake_plan  # type: ignore[method-assign]
            service.apply_rename_path_plan = fake_apply  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service)

            result = facade.apply_rename_selection(
                {
                    "paths": [str(source)],
                    "_configured_media_roots": [str(root)],
                    "selected_sources": [str(source)],
                    "confirm_apply": True,
                },
                resolved=resolved,
            )
            source_still_exists = source.exists()

        self.assertFalse(result.ok)
        self.assertEqual(result.command, "rename.apply")
        self.assertEqual(result.severity, "error")
        self.assertEqual(result.errors, ["active_work"])
        self.assertIn("PID(s) 24681", result.message)
        self.assertEqual(plan_calls, [])
        self.assertEqual(apply_calls, [])
        self.assertTrue(source_still_exists)
