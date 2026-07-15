from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.rename.bad_case_corpus import (
    RenameBadCaseCorpusError,
    append_bad_rename_case_from_request,
    build_bad_rename_case,
    validate_active_bad_rename_case,
)


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "rename" / "bad_rename_cases.jsonl"
REQUIRED_STRING_FIELDS = ("id", "status", "kind", "source_folder", "source_file")
REQUIRED_ACTIVE_CASE_IDS = {
    "subsplease-kanan-sama-12v2",
    "tv-canonical-range",
    "tv-noncanonical-range-blocked",
    "tv-invalid-range-blocked",
    "tv-e100",
    "tv-e1000-blocked",
    "tv-ordinal-third-season",
    "tv-ova-special",
    "tv-revision-v2-title",
    "tv-revision-v3-title",
    "tv-legitimate-web-audio-proper",
    "tv-policy-override",
    "movie-proper-revision",
    "movie-repack-revision",
    "movie-rerip-revision",
    "movie-a-proper-man",
    "movie-the-web",
    "movie-audio-drama",
    "movie-12-angry-men",
    "movie-10-cloverfield-lane",
    "movie-dc-league",
    "movie-ma",
    "movie-cam",
    "movie-2001-a-space-odyssey",
    "movie-blade-runner-2049",
    "movie-1917",
    "movie-1984",
    "movie-policy-override-hoppers",
}


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{FIXTURE_PATH}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise AssertionError(f"{FIXTURE_PATH}:{line_number}: case must be a JSON object.")
            payload["_line_number"] = line_number
            cases.append(payload)
    return cases


class RenameBadCaseCorpusTests(unittest.TestCase):
    def test_corpus_schema_has_unique_ids(self) -> None:
        seen: set[str] = set()
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 1)
        for case in cases:
            with self.subTest(case=case.get("id", f"line-{case.get('_line_number')}")):
                for field in REQUIRED_STRING_FIELDS:
                    self.assertIsInstance(case.get(field), str, field)
                    self.assertTrue(case[field].strip(), field)
                self.assertIn(case["status"], {"active", "pending"})
                self.assertIn(case["kind"], {"tv_auto", "movie_auto"})
                self.assertNotIn(case["id"], seen)
                seen.add(case["id"])
                self.assertIsInstance(case.get("season_number", 1), int)
                if "expected_season" in case:
                    self.assertIsInstance(case["expected_season"], int)
                if case["status"] == "active" and case["kind"] == "tv_auto":
                    self.assertIn("expected_episode", case)
                    self.assertIsInstance(case["expected_episode"], int)
                    self.assertIn("expected_episode_end", case)
                    self.assertTrue(case["expected_episode_end"] is None or isinstance(case["expected_episode_end"], int))
                for field in (
                    "expected_queue_season_sort_order",
                    "expected_queue_episode_sort_order",
                ):
                    if field in case:
                        self.assertIsInstance(case[field], int)
                for field in ("expected_blocked", "expected_queue_blocked"):
                    if field in case:
                        self.assertIsInstance(case[field], bool)
                for field in (
                    "expected_parse_mode",
                    "expected_block_reason_code",
                    "expected_error_contains",
                    "expected_queue_show_sort_key",
                    "expected_queue_block_reason_code",
                ):
                    if field in case:
                        self.assertIsInstance(case[field], str)
                for field in ("movie_filter_options", "movie_filter_terms", "tv_filter_options", "tv_filter_terms"):
                    if field in case:
                        self.assertIsInstance(case[field], dict)
                for field in ("remove_terms", "tv_remove_terms"):
                    if field in case:
                        self.assertIsInstance(case[field], list)
                for field in ("source_folder", "source_file"):
                    self.assertNotIn("\n", case[field])

    def test_required_regressions_are_active(self) -> None:
        active_ids = {case["id"] for case in load_cases() if case.get("status") == "active"}

        self.assertEqual(REQUIRED_ACTIVE_CASE_IDS - active_ids, set())

    def test_every_active_auto_case_matches_python(self) -> None:
        active_cases = [case for case in load_cases() if case.get("status") == "active"]
        self.assertGreaterEqual(len(active_cases), len(REQUIRED_ACTIVE_CASE_IDS))
        for case in active_cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(validate_active_bad_rename_case(case), [])

    def test_case_builder_preserves_identity_queue_and_policy_overrides(self) -> None:
        case = build_bad_rename_case(
            {
                "kind": "tv_auto",
                "status": "pending",
                "source_folder": "Example Show",
                "source_file": "Example Show S01E02-E01.mkv",
                "expected_blocked": True,
                "expected_block_reason_code": "tv_parse_unreliable",
                "expected_error_contains": "range must increase",
                "expected_episode": 2,
                "expected_episode_end": 1,
                "expected_parse_mode": "invalid-range",
                "expected_queue_show_sort_key": "Example Show",
                "expected_queue_season_sort_order": 1,
                "expected_queue_episode_sort_order": 2,
                "expected_queue_blocked": True,
                "expected_queue_block_reason_code": "tv_parse_unreliable",
                "tv_filter_options": {"video_source": True},
                "tv_filter_terms": {"video_source": ["CustomSource"]},
                "tv_remove_terms": ["sample"],
            },
            set(),
        )

        self.assertEqual(case["expected_name"], "")
        self.assertEqual(case["expected_episode_end"], 1)
        self.assertEqual(case["expected_parse_mode"], "invalid-range")
        self.assertEqual(case["expected_queue_episode_sort_order"], 2)
        self.assertTrue(case["expected_blocked"])
        self.assertEqual(case["tv_filter_terms"], {"video_source": ["CustomSource"]})
        self.assertEqual(case["tv_remove_terms"], ["sample"])

    def test_active_blocked_tv_cases_require_and_validate_episode_gates(self) -> None:
        base = {
            "kind": "tv_auto",
            "status": "active",
            "source_folder": "Anime",
            "source_file": "Example Show S01E01-01.mkv",
            "expected_blocked": True,
            "expected_parse_mode": "noncanonical-range",
            "expected_error_contains": "Noncanonical TV episode range",
        }

        with self.assertRaisesRegex(RenameBadCaseCorpusError, "expected_episode"):
            build_bad_rename_case(base, set())

        case = build_bad_rename_case(
            {**base, "status": "pending", "expected_episode": 999, "expected_episode_end": 998},
            set(),
        )
        case["status"] = "active"
        errors = validate_active_bad_rename_case(case)

        self.assertTrue(any("expected_episode mismatch" in error for error in errors), errors)
        self.assertTrue(any("expected_episode_end mismatch" in error for error in errors), errors)

    def test_case_builder_uses_source_folder_for_clean_folder_expectation(self) -> None:
        case = build_bad_rename_case(
            {
                "kind": "tv_auto",
                "status": "active",
                "source_folder": "Anime",
                "source_file": "Example Show S01E01.mkv",
                "expected_name": "Example Show - S01E01.mkv",
                "expected_episode": 1,
                "expected_episode_end": None,
            },
            set(),
        )

        self.assertEqual(case["expected_clean_folder"], "Anime")
        self.assertEqual(validate_active_bad_rename_case(case), [])

    def test_case_builder_rejects_malformed_nested_policy_overrides(self) -> None:
        invalid_overrides = (
            ("tv_filter_options", {"video_source": "false"}),
            ("tv_filter_terms", {"video_source": "CustomSource"}),
            ("tv_remove_terms", ["sample", 7]),
        )
        base = {
            "kind": "tv_auto",
            "status": "pending",
            "source_folder": "Anime",
            "source_file": "Example Show S01E01.mkv",
            "expected_name": "Example Show - S01E01.mkv",
        }

        for field_name, value in invalid_overrides:
            with self.subTest(field=field_name):
                with self.assertRaisesRegex(RenameBadCaseCorpusError, field_name):
                    build_bad_rename_case({**base, field_name: value}, set())

    def test_explicit_empty_tv_remove_terms_override_legacy_remove_terms(self) -> None:
        case = build_bad_rename_case(
            {
                "kind": "tv_auto",
                "status": "active",
                "source_folder": "Anime",
                "source_file": "Sample Show S01E01.mkv",
                "expected_name": "Sample Show - S01E01.mkv",
                "expected_episode": 1,
                "expected_episode_end": None,
                "remove_terms": ["sample"],
                "tv_remove_terms": [],
            },
            set(),
        )

        self.assertEqual(validate_active_bad_rename_case(case), [])

    def test_movie_auto_case_append_builds_expected_name(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw_dir:
            fixture_path = Path(raw_dir) / "bad_rename_cases.jsonl"
            payload = append_bad_rename_case_from_request(
                {
                    "kind": "movie_auto",
                    "source_file": "Scary Movie 2026 1080p DCPRip x264-FS.mkv",
                    "expected_movie_title": "Scary Movie",
                    "expected_year": "2026",
                    "status": "pending",
                    "confirm_append": True,
                },
                fixture_path=fixture_path,
            )

            self.assertEqual(payload["case"]["kind"], "movie_auto")
            self.assertEqual(payload["case"]["source_folder"], "Movies")
            self.assertEqual(payload["case"]["expected_name"], "Scary Movie (2026).mkv")

    def test_movie_auto_case_append_requires_confirmation(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw_dir:
            fixture_path = Path(raw_dir) / "bad_rename_cases.jsonl"
            with self.assertRaises(RenameBadCaseCorpusError):
                append_bad_rename_case_from_request(
                    {
                        "kind": "movie_auto",
                        "source_file": "Scary Movie 2026.mkv",
                        "expected_movie_title": "Scary Movie",
                        "expected_year": "2026",
                    },
                    fixture_path=fixture_path,
                )
            self.assertFalse(fixture_path.exists())


if __name__ == "__main__":
    unittest.main()
