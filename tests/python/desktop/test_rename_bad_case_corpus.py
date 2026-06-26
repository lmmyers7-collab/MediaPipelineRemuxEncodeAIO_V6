from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.rename.bad_case_corpus import RenameBadCaseCorpusError, append_bad_rename_case_from_request
from mediapipeline.core.rename.tv import (
    build_auto_tv_rename_name,
    clean_pipeline_tv_name_part,
    resolve_tv_folder_season_info,
)


FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "rename" / "bad_rename_cases.jsonl"
REQUIRED_STRING_FIELDS = ("id", "status", "kind", "source_folder", "source_file", "expected_name")


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
                for field in ("source_folder", "source_file"):
                    self.assertNotIn("\n", case[field])

    def test_active_tv_auto_cases_match_expected_output(self) -> None:
        active_cases = [case for case in load_cases() if case.get("status") == "active" and case.get("kind") == "tv_auto"]
        self.assertGreaterEqual(len(active_cases), 1)
        for case in active_cases:
            with self.subTest(case=case["id"]):
                source = Path("TV") / case["source_folder"] / case["source_file"]
                remove_terms = case.get("remove_terms") or None
                expected_clean_folder = str(case.get("expected_clean_folder") or "").strip()
                if expected_clean_folder:
                    self.assertEqual(clean_pipeline_tv_name_part(source.parent.name, remove_terms), expected_clean_folder)

                folder_info = resolve_tv_folder_season_info(source, remove_terms)
                if "expected_season" in case:
                    self.assertIsNotNone(folder_info)
                    self.assertEqual(folder_info["season"], case["expected_season"])
                expected_show = str(case.get("expected_show") or "").strip()
                if expected_show:
                    self.assertIsNotNone(folder_info)
                    self.assertEqual(folder_info["show"], expected_show)

                self.assertEqual(
                    build_auto_tv_rename_name(
                        source,
                        season_number=int(case.get("season_number", 1)),
                        remove_terms=remove_terms,
                    ),
                    case["expected_name"],
                )

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
