from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rename.policy import (
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
    rename_preview_source_counts,
    rename_preview_warnings,
    rename_request_paths,
    select_rename_plan_rows,
    selected_rename_sources,
)


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
            "final_name_overrides": {"C:/Media/Show E01.mkv": None},
            "rename_sidecars": False,
            "force_pipeline_name": True,
            "force_pipeline_name_overrides": {"C:/Media/Show E01.mkv": "yes"},
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
        self.assertEqual(kwargs["final_name_overrides"], {"C:/Media/Show E01.mkv": "None"})
        self.assertFalse(kwargs["rename_sidecars"])
        self.assertTrue(kwargs["force_pipeline_name"])
        self.assertEqual(kwargs["force_pipeline_name_overrides"], {"C:/Media/Show E01.mkv": True})
        self.assertEqual(kwargs["powershell_host"], "  C:/PowerShell/pwsh.exe  ")
        self.assertTrue(kwargs["use_pipeline_naming_preview"])
        self.assertEqual(kwargs["template_preset"], "movie_standard")

    def test_dict_helpers_ignore_non_dict_values(self) -> None:
        self.assertEqual(dict_bool(None), {})
        self.assertEqual(dict_str([]), {})
        self.assertEqual(dict_terms([], lambda raw: raw.split(",")), {})
        self.assertEqual(dict_bool({"enabled": ""}), {"enabled": False})
        self.assertEqual(dict_str({"value": 5}), {"value": "5"})
        self.assertEqual(dict_terms({"video": "sample; trailer"}, lambda raw: raw.replace(";", ",").split(",")), {"video": ["sample", "trailer"]})


if __name__ == "__main__":
    unittest.main()
