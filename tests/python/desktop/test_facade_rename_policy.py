from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.rename.policy import (
    CONFIRM_RENAME_APPLY_MESSAGE,
    CONFIRM_RENAME_APPLY_WARNING,
    MISSING_RENAME_SELECTION_MESSAGE,
    NO_RENAME_SELECTION_MESSAGE,
    NO_RENAME_SELECTION_WARNING,
    dict_bool,
    dict_str,
    dict_terms,
    missing_rename_selection_warnings,
    remove_terms_from_request,
    rename_clean_filename_preview_from_request,
    rename_cleaning_policy_from_config,
    rename_cleaning_policy_from_request,
    rename_cleaning_policy_fingerprint,
    rename_apply_blockers_result,
    rename_apply_confirmation_required_result,
    rename_apply_exception_result,
    rename_apply_missing_selection_result,
    rename_apply_no_selection_result,
    rename_apply_service_unavailable_result,
    rename_apply_success_result,
    rename_blocker_error_lines,
    rename_plan_kwargs_from_request,
    rename_plan_build_exception_result,
    rename_preview_change_kind_counts,
    rename_preview_confidence_counts,
    rename_preview_counts,
    rename_preview_fingerprint,
    rename_preview_source_counts,
    rename_preview_warnings,
    rename_request_paths,
    rename_request_with_cleaning_policy,
    select_rename_plan_rows,
    selected_rename_sources,
)
from mediapipeline.core.rename.movie import clean_pipeline_movie_name
from mediapipeline.core.rename.tv import clean_pipeline_tv_name_part


class RenameFacadePolicyTests(unittest.TestCase):
    def test_preview_counts_and_warnings_are_stable(self) -> None:
        rows = [
            {"status": "ready", "confidence": "high", "preview_source": "pipeline_tv_preview", "change_kind": "rename", "warnings": ["shared", "ready warning"]},
            {"status": "match", "confidence": "high", "preview_source": "manual_tv_sequence", "change_kind": "unchanged", "warnings": ["shared"]},
            {"status": "warning", "confidence": "medium", "preview_source": "auto_tv_heuristic", "change_kind": "rename", "warnings": ["row warning"]},
            {"status": "blocked", "confidence": "blocked", "preview_source": "error", "change_kind": "blocked", "warnings": []},
            {"status": "other", "warnings": None},
        ]

        self.assertEqual(
            rename_preview_counts(rows),
            {"total": 5, "ready": 1, "match": 1, "warning": 1, "blocked": 1},
        )
        self.assertEqual(rename_preview_warnings(rows), ["ready warning", "row warning", "shared"])
        self.assertEqual(rename_preview_confidence_counts(rows), {"blocked": 1, "high": 2, "medium": 1, "unknown": 1})
        self.assertEqual(
            rename_preview_source_counts(rows),
            {"auto_tv_heuristic": 1, "error": 1, "manual_tv_sequence": 1, "pipeline_tv_preview": 1, "unknown": 1},
        )
        self.assertEqual(rename_preview_change_kind_counts(rows), {"blocked": 1, "rename": 2, "unchanged": 1, "unknown": 1})

    def test_preview_fingerprint_is_bound_to_the_applied_cleaning_policy(self) -> None:
        base = {
            "source": "C:/Media/Movie.mkv",
            "destination": "C:/Media/Movie (2024).mkv",
            "target_name": "Movie (2024).mkv",
            "status": "ready",
            "mode": "movie",
            "errors": [],
            "sidecar_moves": [],
        }

        left = rename_preview_fingerprint([{**base, "rename_cleaning_policy_fingerprint": "a" * 64}])
        right = rename_preview_fingerprint([{**base, "rename_cleaning_policy_fingerprint": "b" * 64}])

        self.assertNotEqual(left, right)

    def test_preview_fingerprint_is_bound_to_parsed_identity_evidence(self) -> None:
        base = {
            "source": "C:/Media/Example Show S01E01.mkv",
            "destination": "C:/Media/Example Show - S01E01.mkv",
            "target_name": "Example Show - S01E01.mkv",
            "status": "ready",
            "mode": "tv",
            "errors": [],
            "sidecar_moves": [],
            "parsed_identity": {
                "show": "Example Show",
                "season": 1,
                "episode_start": 1,
                "episode_end": None,
            },
            "destination_identity_key": "example show_S01E01",
        }

        with self.subTest("parsed identity"):
            changed_identity = {
                **base,
                "parsed_identity": {**base["parsed_identity"], "episode_end": 2},
            }
            self.assertNotEqual(
                rename_preview_fingerprint([base]),
                rename_preview_fingerprint([changed_identity]),
            )

        with self.subTest("destination identity key"):
            changed_key = {**base, "destination_identity_key": "example show_S01E01-E02"}
            self.assertNotEqual(
                rename_preview_fingerprint([base]),
                rename_preview_fingerprint([changed_key]),
            )

    def test_selected_sources_and_plan_matching_use_backend_path_keys(self) -> None:
        first = "  C:/Media/Show E01.mkv  "
        second = "C:/Media/Show E02.mkv"
        selected = selected_rename_sources({"selected_sources": [first, "", None, second]})
        plan = [
            {"source": "c:/media/show e01.mkv", "destination": "C:/Media/Show - S01E01.mkv"},
            {"source": "C:/Media/Show E03.mkv", "destination": "C:/Media/Show - S01E03.mkv"},
        ]

        selected_plan, missing = select_rename_plan_rows(plan, selected)

        self.assertEqual(selected, ["C:/Media/Show E01.mkv", "C:/Media/Show E02.mkv"])
        self.assertEqual(len(selected_plan), 1)
        self.assertEqual(selected_plan[0]["destination"], "C:/Media/Show - S01E01.mkv")
        self.assertEqual(missing, ["c:\\media\\show e02.mkv"] if "\\" in str(Path("C:/x")) else ["c:/media/show e02.mkv"])
        self.assertEqual(
            missing_rename_selection_warnings(missing),
            [f"Missing selected source: {missing[0]}"],
        )
        self.assertEqual(CONFIRM_RENAME_APPLY_MESSAGE, "Rename apply requires explicit confirmation.")
        self.assertEqual(CONFIRM_RENAME_APPLY_WARNING, "confirm_apply must be true.")
        self.assertEqual(NO_RENAME_SELECTION_MESSAGE, "Select one or more rename rows before applying.")
        self.assertEqual(NO_RENAME_SELECTION_WARNING, "No selected_sources were provided.")
        self.assertEqual(MISSING_RENAME_SELECTION_MESSAGE, "One or more selected rename rows are no longer in the current plan.")

    def test_blocker_messages_use_source_leaf_names(self) -> None:
        rows = [
            {"source": "C:/Media/Show E01.mkv", "errors": ["destination exists", "sidecar locked"]},
            {"source": "", "errors": ["missing source"]},
        ]

        self.assertEqual(
            rename_blocker_error_lines(rows),
            ["Show E01.mkv: destination exists; sidecar locked", ": missing source"],
        )

    def test_apply_command_results_preserve_backend_contract(self) -> None:
        confirmation = rename_apply_confirmation_required_result()
        no_selection = rename_apply_no_selection_result()
        unavailable = rename_apply_service_unavailable_result()
        build_error = rename_plan_build_exception_result(RuntimeError("plan failed"))
        missing = rename_apply_missing_selection_result(["c:/media/show e02.mkv"])
        blockers = rename_apply_blockers_result(
            [{"source": "C:/Media/Show E01.mkv", "errors": ["destination exists"]}]
        )
        failure = rename_apply_exception_result(RuntimeError("rename failed"))
        success = rename_apply_success_result(
            {
                "renamed": 1,
                "rows": [{"source": "C:/Media/Show E01.mkv", "destination": Path("C:/Media/Show - S01E01.mkv")}],
                "undo_manifest": Path("C:/State/Rename/undo.json"),
            },
            renamed=1,
        )

        self.assertEqual(confirmation.command, "rename.apply")
        self.assertEqual(confirmation.warnings, [CONFIRM_RENAME_APPLY_WARNING])
        self.assertEqual(no_selection.warnings, [NO_RENAME_SELECTION_WARNING])
        self.assertEqual(unavailable.errors, ["Rename apply service is not available."])
        self.assertEqual(build_error.errors, ["plan failed"])
        self.assertEqual(missing.warnings, ["Missing selected source: c:/media/show e02.mkv"])
        self.assertEqual(blockers.errors, ["Show E01.mkv: destination exists"])
        self.assertEqual(failure.errors, ["rename failed"])
        self.assertTrue(success.ok)
        self.assertEqual(success.message, "Rename applied: 1 file(s) renamed.")
        self.assertEqual(success.data["applied_count"], 1)
        self.assertEqual(success.data["renamed"], 1)

    def test_request_parsing_preserves_rename_contract(self) -> None:
        request = {
            "paths": ["C:/Media/Show E01.mkv", "", None],
            "mode": "movie",
            "show_name": "Ignored",
            "season": "S02",
            "start_episode": "E04",
            "movie_title": "The Matrix",
            "movie_year": 1999,
            "remove_terms_text": "sample, trailer",
            "movie_filter_options": {"video": 1, "audio": 0},
            "movie_filter_terms": {"video_source": "custom tag, local rip", "release_groups": ["Group", "group"]},
            "tv_remove_terms_text": "tv sample, tv trailer",
            "tv_filter_options": {"release_groups": True, "audio_channels": False},
            "tv_filter_terms": {"release_groups": ["TTGA", "ttga"]},
            "final_name_overrides": {"C:/Media/Show E01.mkv": None},
            "rename_sidecars": False,
            "force_pipeline_name": True,
            "force_pipeline_name_overrides": {"C:/Media/Show E01.mkv": True},
            "powershell_host": "  C:/PowerShell/pwsh.exe  ",
            "use_pipeline_naming_preview": True,
            "template_preset": "movie_standard",
        }

        terms = remove_terms_from_request(request, lambda raw: raw.split(", "))
        kwargs = rename_plan_kwargs_from_request(request, parse_remove_terms=lambda raw: raw.split(", "))

        self.assertEqual(rename_request_paths(request), [Path("C:/Media/Show E01.mkv")])
        self.assertEqual(terms, ["sample", "trailer"])
        self.assertEqual(kwargs["mode"], "movie")
        self.assertEqual(kwargs["season_value"], "S02")
        self.assertEqual(kwargs["start_episode_value"], "E04")
        self.assertEqual(kwargs["movie_title"], "The Matrix")
        self.assertEqual(kwargs["movie_year"], "1999")
        self.assertEqual(kwargs["remove_terms"], ["sample", "trailer"])
        self.assertEqual(kwargs["movie_filter_options"], {"video": True, "audio": False})
        self.assertEqual(kwargs["movie_filter_terms"], {"video_source": ["custom tag", "local rip"], "release_groups": ["Group"]})
        self.assertEqual(kwargs["tv_filter_options"], {"release_groups": True, "audio_channels": False})
        self.assertEqual(kwargs["tv_filter_terms"], {"release_groups": ["TTGA"]})
        self.assertEqual(kwargs["final_name_overrides"], {"C:/Media/Show E01.mkv": "None"})
        self.assertFalse(kwargs["rename_sidecars"])
        self.assertTrue(kwargs["force_pipeline_name"])
        self.assertEqual(kwargs["force_pipeline_name_overrides"], {"C:/Media/Show E01.mkv": True})
        self.assertEqual(kwargs["powershell_host"], "  C:/PowerShell/pwsh.exe  ")
        self.assertTrue(kwargs["use_pipeline_naming_preview"])
        self.assertEqual(kwargs["template_preset"], "movie_standard")
        self.assertEqual(kwargs["cleaning_policy"]["movie"]["remove_terms"], ["sample", "trailer"])
        self.assertEqual(kwargs["cleaning_policy"]["tv"]["remove_terms"], ["tv sample", "tv trailer"])

    def test_request_parsing_rejects_non_bool_rename_mutation_flags(self) -> None:
        base = {"paths": ["C:/Media/Show E01.mkv"]}
        cases = [
            {"rename_sidecars": "false"},
            {"rename_sidecars": 0},
            {"force_pipeline_name": "false"},
            {"force_pipeline_name": 1},
            {"use_pipeline_naming_preview": "false"},
            {"use_pipeline_naming_preview": 0},
            {"force_pipeline_name_overrides": {"C:/Media/Show E01.mkv": "false"}},
            {"force_pipeline_name_overrides": {"C:/Media/Show E01.mkv": 1}},
        ]

        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    rename_plan_kwargs_from_request({**base, **override})

    def test_dict_helpers_ignore_non_dict_values(self) -> None:
        self.assertEqual(dict_bool(None), {})
        self.assertEqual(dict_str([]), {})
        self.assertEqual(dict_terms([], lambda raw: raw.split(",")), {})
        self.assertEqual(dict_bool({"enabled": ""}), {"enabled": False})
        self.assertEqual(dict_bool({"enabled": "false", "other": "yes"}), {"enabled": False, "other": True})
        self.assertEqual(dict_str({"value": 5}), {"value": "5"})
        self.assertEqual(dict_terms({"video": "sample; trailer"}, lambda raw: raw.replace(";", ",").split(",")), {"video": ["sample", "trailer"]})

    def test_rename_cleaning_policy_from_saved_config_normalizes_terms(self) -> None:
        policy = rename_cleaning_policy_from_config(
            {
                "RenameMovieFilterOptions": {"release_groups": "true", "audio_channels": "false", "unknown": False},
                "RenameMovieFilterTerms": {
                    "release_groups": ["SupaCvnt", "supacvnt", "", "BYNDR"],
                    "services_containers": "MA, ma, ",
                    "unknown": ["Ignored"],
                },
                "RenameMovieRemoveTerms": ["sample", "", "SAMPLE", "behind the scenes"],
                "RenameTVFilterOptions": {"release_groups": "true", "audio_channels": "false", "unknown": False},
                "RenameTVFilterTerms": {
                    "release_groups": ["TTGA", "ttga", ""],
                    "release_flags": "uncensored, uncensored, ",
                    "unknown": ["Ignored"],
                },
                "RenameTVRemoveTerms": ["ova", "", "OVA", "special"],
            }
        )

        self.assertEqual(policy["schema_version"], "rename_cleaning_policy.v1")
        self.assertEqual(policy["policy_fingerprint"], rename_cleaning_policy_fingerprint(policy))
        self.assertEqual(len(policy["policy_fingerprint"]), 64)
        self.assertTrue(policy["movie"]["options"]["release_groups"])
        self.assertEqual(policy["movie"]["terms"]["release_groups"], ["SupaCvnt", "BYNDR"])
        self.assertEqual(policy["movie"]["remove_terms"], ["sample", "behind the scenes"])
        self.assertEqual(policy["tv"]["terms"]["release_groups"], ["TTGA"])
        self.assertEqual(policy["tv"]["remove_terms"], ["ova", "special"])
        self.assertTrue(policy["movie_filter_options"]["release_groups"])
        self.assertFalse(policy["movie_filter_options"]["audio_channels"])
        self.assertNotIn("unknown", policy["movie_filter_options"])
        self.assertEqual(policy["movie_filter_terms"]["release_groups"], ["SupaCvnt", "BYNDR"])
        self.assertEqual(policy["movie_filter_terms"]["services_containers"], ["MA"])
        self.assertIn("languages_subs_dubs", policy["movie_filter_terms"])
        self.assertIn("eng", policy["movie_filter_terms"]["languages_subs_dubs"])
        self.assertIn("ita", policy["movie_filter_terms"]["languages_subs_dubs"])
        self.assertNotIn("unknown", policy["movie_filter_terms"])
        self.assertEqual(policy["remove_terms"], ["sample", "behind the scenes"])
        self.assertTrue(policy["tv_filter_options"]["release_groups"])
        self.assertFalse(policy["tv_filter_options"]["audio_channels"])
        self.assertNotIn("unknown", policy["tv_filter_options"])
        self.assertEqual(policy["tv_filter_terms"]["release_groups"], ["TTGA"])
        self.assertEqual(policy["tv_filter_terms"]["release_flags"], ["uncensored"])
        self.assertNotIn("unknown", policy["tv_filter_terms"])
        self.assertEqual(policy["tv_remove_terms"], ["ova", "special"])

    def test_rename_cleaning_policy_from_request_parses_workbench_remove_term_text(self) -> None:
        policy = rename_cleaning_policy_from_request(
            {
                "remove_terms_text": "sample; behind the scenes",
                "tv_remove_terms_text": "ova\nspecial",
                "movie_filter_terms": {"release_groups": ["GalaxyRG"]},
                "tv_filter_terms": {"release_groups": ["TTGA"]},
            },
            parse_remove_terms=lambda raw: [
                term.strip()
                for term in raw.replace(";", "\n").splitlines()
                if term.strip()
            ],
        )

        self.assertEqual(policy["movie"]["remove_terms"], ["sample", "behind the scenes"])
        self.assertEqual(policy["tv"]["remove_terms"], ["ova", "special"])
        self.assertEqual(policy["movie"]["terms"]["release_groups"], ["GalaxyRG"])
        self.assertEqual(policy["tv"]["terms"]["release_groups"], ["TTGA"])

    def test_rename_cleaning_policy_fingerprint_is_deterministic_and_content_bound(self) -> None:
        left = rename_cleaning_policy_from_config(
            {
                "RenameMovieFilterOptions": {"release_groups": True, "audio_channels": False},
                "RenameMovieFilterTerms": {"release_groups": ["SupaCvnt", "BYNDR"]},
            }
        )
        reordered = rename_cleaning_policy_from_config(
            {
                "RenameMovieFilterTerms": {"release_groups": ["SupaCvnt", "BYNDR"]},
                "RenameMovieFilterOptions": {"audio_channels": False, "release_groups": True},
            }
        )
        changed = rename_cleaning_policy_from_config(
            {
                "RenameMovieFilterOptions": {"release_groups": True, "audio_channels": False},
                "RenameMovieFilterTerms": {"release_groups": ["SupaCvnt", "OTHER"]},
            }
        )

        self.assertEqual(left["policy_fingerprint"], reordered["policy_fingerprint"])
        self.assertNotEqual(left["policy_fingerprint"], changed["policy_fingerprint"])

    def test_all_enabled_categories_still_apply_custom_movie_and_tv_terms(self) -> None:
        movie = clean_pipeline_movie_name(
            "Movie.CustomSource.2024.mkv",
            movie_filter_terms={"video_source": ["CustomSource"]},
        )
        tv = clean_pipeline_tv_name_part(
            "Show CustomSource",
            tv_filter_terms={"video_source": ["CustomSource"]},
        )

        self.assertEqual(movie, "Movie (2024)")
        self.assertEqual(tv, "Show")

    def test_clean_filename_preview_reports_staged_and_saved_policy_sources(self) -> None:
        staged = rename_clean_filename_preview_from_request(
            {
                "filename": "Iron.Lung.2026.1080p.WEBRip.x265.6CH-SupaCvnt.mkv",
                "movie_filter_terms": {"release_groups": ["SupaCvnt"]},
                "movie_filter_options": {"release_groups": True},
                "_rename_movie_filter_policy_source": "staged",
            },
            clean_movie_name=clean_pipeline_movie_name,
        )
        saved_request = rename_request_with_cleaning_policy(
            {"filename": "Hoppers.2026.2160p.MA.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-BYNDR.mkv"},
            rename_cleaning_policy_from_config(
                {
                    "RenameMovieFilterTerms": {"release_groups": ["BYNDR"], "services_containers": ["MA"]},
                }
            ),
            source="saved",
            strip_existing=True,
        )
        saved = rename_clean_filename_preview_from_request(
            saved_request,
            clean_movie_name=clean_pipeline_movie_name,
        )

        self.assertEqual(staged["target_name"], "Iron Lung (2026).mkv")
        self.assertEqual(staged["rename_cleaning_policy_source"], "staged")
        self.assertEqual(staged["movie_filter_terms_mode"], "staged")
        self.assertEqual(saved["target_name"], "Hoppers (2026).mkv")
        self.assertEqual(saved["rename_cleaning_policy_source"], "saved")
        self.assertEqual(saved["movie_filter_terms_mode"], "saved")

    def test_clean_filename_preview_supports_tv_context_and_split_filters(self) -> None:
        from mediapipeline.core.rename.tv import build_auto_tv_rename_name

        preview = rename_clean_filename_preview_from_request(
            {
                "mode": "tv",
                "source_folder": "The Web S01 1080p WEB-DL-TTGA",
                "filename": "S01E01-Pilot.1080p.WEB-DL-TTGA.mkv",
                "tv_filter_terms": {"release_groups": ["TTGA"]},
                "tv_filter_options": {"release_groups": True},
                "_rename_movie_filter_policy_source": "staged",
            },
            clean_movie_name=clean_pipeline_movie_name,
            build_auto_tv_name=build_auto_tv_rename_name,
        )

        self.assertEqual(preview["target_name"], "The Web - S01E01 - Pilot.mkv")
        self.assertEqual(preview["mode"], "tv")
        self.assertEqual(preview["preview_source"], "backend_tv_cleaner")
        self.assertEqual(preview["tv_filter_terms_mode"], "staged")
        self.assertTrue(any(item["kind"] == "context_guard" for item in preview["filter_evidence"]))

    def test_clean_filename_preview_reports_tv_case_analysis(self) -> None:
        from mediapipeline.core.rename.tv import build_auto_tv_rename_name

        preview = rename_clean_filename_preview_from_request(
            {
                "mode": "tv",
                "source_folder": "Ascendance of a Bookworm S03+SP 1080p Dual Audio BD Remux FLAC-TTGA",
                "filename": "S03E01-The Beginning of Winter.mkv",
                "expected_show": "Ascendance of a Bookworm",
                "expected_season": "3",
                "expected_episode": "1",
                "expected_episode_title": "The Beginning of Winter",
                "include_case_analysis": "true",
            },
            clean_movie_name=clean_pipeline_movie_name,
            build_auto_tv_name=build_auto_tv_rename_name,
        )

        self.assertEqual(preview["target_name"], "Ascendance of a Bookworm - S03E01 - The Beginning of Winter.mkv")
        self.assertTrue(preview["comparison"]["ok"], preview["comparison"])
        self.assertEqual(preview["actual_fields"]["show"], "Ascendance of a Bookworm")
        self.assertEqual(preview["expected_fields"]["episode"], 1)
        self.assertEqual(preview["case_payload"]["kind"], "tv_auto")
        suggestion = next(item for item in preview["filter_suggestions"] if item["term"].casefold() == "1080p")
        self.assertEqual(suggestion["coverage_status"], "already_filtered")
        self.assertFalse(suggestion["stage_recommended"])
        self.assertIn("tv_filter_terms.video_source", suggestion["destinations"])
        self.assertIn("tv_remove_terms", suggestion["destinations"])
        self.assertFalse(any(destination.startswith("movie_filter_terms.") for destination in suggestion["destinations"]))
        self.assertNotIn("remove_terms", suggestion["destinations"])

    def test_clean_filename_preview_reports_range_end_and_preserves_tv_case_policy(self) -> None:
        from mediapipeline.core.rename.tv import build_auto_tv_rename_name

        preview = rename_clean_filename_preview_from_request(
            {
                "mode": "tv",
                "source_folder": "Anime",
                "filename": "Example Show S01E01-E02 CustomSource.mkv",
                "expected_show": "Example Show",
                "expected_season": 1,
                "expected_episode": 1,
                "expected_episode_end": 2,
                "tv_filter_options": {"video_source": True},
                "tv_filter_terms": {"video_source": ["CustomSource"]},
                "tv_remove_terms": ["sample"],
                "include_case_analysis": True,
            },
            clean_movie_name=clean_pipeline_movie_name,
            build_auto_tv_name=build_auto_tv_rename_name,
        )

        self.assertTrue(preview["comparison"]["ok"], preview["comparison"])
        self.assertEqual(preview["actual_fields"]["episode_end"], 2)
        self.assertEqual(preview["expected_fields"]["episode_end"], 2)
        self.assertIn("episode_end", preview["comparison"]["checked_fields"])
        self.assertEqual(preview["case_payload"]["expected_episode_end"], 2)
        self.assertEqual(preview["case_payload"]["expected_clean_folder"], "Anime")
        self.assertEqual(preview["case_payload"]["tv_filter_options"], {"video_source": True})
        self.assertEqual(preview["case_payload"]["tv_filter_terms"], {"video_source": ["CustomSource"]})
        self.assertEqual(preview["case_payload"]["tv_remove_terms"], ["sample"])

    def test_clean_filename_preview_honors_tv_no_episode_title_template(self) -> None:
        from mediapipeline.core.rename.tv import build_auto_tv_rename_name

        preview = rename_clean_filename_preview_from_request(
            {
                "mode": "tv",
                "source_folder": "The Web S01",
                "filename": "S01E01-Pilot.mkv",
                "template_preset": "tv_no_episode_title",
                "expected_show": "The Web",
                "expected_season": "1",
                "expected_episode": "1",
                "expected_episode_title": "Pilot",
                "include_case_analysis": "true",
            },
            clean_movie_name=clean_pipeline_movie_name,
            build_auto_tv_name=build_auto_tv_rename_name,
        )

        self.assertEqual(preview["target_name"], "The Web - S01E01.mkv")
        self.assertEqual(preview["expected_fields"]["expected_name"], "The Web - S01E01.mkv")
        self.assertEqual(preview["expected_fields"]["episode_title"], "")
        self.assertTrue(preview["comparison"]["ok"], preview["comparison"])

    def test_clean_filename_preview_reports_movie_case_analysis(self) -> None:
        preview = rename_clean_filename_preview_from_request(
            {
                "mode": "movie",
                "filename": "Scary Movie 2026 1080p DCPRip x264-FS.mkv",
                "expected_movie_title": "Scary Movie",
                "expected_year": "2026",
                "include_case_analysis": "true",
            },
            clean_movie_name=clean_pipeline_movie_name,
        )

        self.assertEqual(preview["target_name"], "Scary Movie (2026).mkv")
        self.assertEqual(preview["actual_fields"]["movie_title"], "Scary Movie")
        self.assertTrue(preview["comparison"]["ok"], preview["comparison"])
        self.assertEqual(preview["case_payload"]["kind"], "movie_auto")
        destinations = {item["default_destination"] for item in preview["filter_suggestions"]}
        self.assertIn("movie_filter_terms.video_source", destinations)
        self.assertIn("movie_filter_terms.release_groups", destinations)
        self.assertTrue(all(not item["stage_recommended"] for item in preview["filter_suggestions"]))
        for item in preview["filter_suggestions"]:
            self.assertIn("movie_filter_terms.video_source", item["destinations"])
            self.assertIn("remove_terms", item["destinations"])
            self.assertFalse(any(destination.startswith("tv_filter_terms.") for destination in item["destinations"]))
            self.assertNotIn("tv_remove_terms", item["destinations"])

    def test_clean_filename_preview_blocks_metadata_only_movie_fallback(self) -> None:
        preview = rename_clean_filename_preview_from_request(
            {
                "mode": "movie",
                "filename": "1080p.WEB-DL.x265.2024.mkv",
            },
            clean_movie_name=clean_pipeline_movie_name,
        )

        self.assertFalse(preview["ok"])
        self.assertEqual(preview["cleaned_title"], "")
        self.assertEqual(preview["target_name"], "")
        self.assertEqual(preview["errors"], ["Filename is empty after backend movie cleaning."])

    def test_clean_filename_preview_marks_missing_movie_terms_as_stage_recommended(self) -> None:
        preview = rename_clean_filename_preview_from_request(
            {
                "mode": "movie",
                "filename": "Scary Movie 2026 1080p DCPRip x264-FS.mkv",
                "expected_movie_title": "Scary Movie",
                "expected_year": "2026",
                "include_case_analysis": "true",
                "movie_filter_options": {
                    "video_source": False,
                    "release_groups": True,
                    "audio_channels": True,
                    "editions": True,
                    "file_size": True,
                    "services_containers": True,
                    "languages_subs_dubs": True,
                },
            },
            clean_movie_name=clean_pipeline_movie_name,
        )

        self.assertFalse(preview["comparison"]["ok"], preview["comparison"])
        suggestions = {item["term"].casefold(): item for item in preview["filter_suggestions"]}
        self.assertTrue(suggestions["1080p"]["stage_recommended"])
        self.assertEqual(suggestions["1080p"]["coverage_status"], "new")
        self.assertTrue(suggestions["dcprip"]["stage_recommended"])


if __name__ == "__main__":
    unittest.main()
