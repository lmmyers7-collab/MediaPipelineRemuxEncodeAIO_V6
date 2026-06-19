"""Append a real-world bad rename case to the JSONL regression corpus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mediapipeline.core.rename.bad_case_corpus import (
    DEFAULT_RENAME_BAD_CASE_FIXTURE,
    RenameBadCaseCorpusError,
    VALID_RENAME_BAD_CASE_STATUSES,
    append_bad_rename_case_from_request,
)
from mediapipeline.tools.paths import find_repo_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", dest="case_id", default="", help="Stable case id. Defaults to a slug from the expected show and source file.")
    parser.add_argument("--source-folder", required=True, help="Source folder leaf or repo-safe relative folder text.")
    parser.add_argument("--source-file", required=True, help="Source media filename.")
    parser.add_argument("--expected-name", required=True, help="Expected renamed filename.")
    parser.add_argument("--expected-show", default="", help="Expected TV show title. Defaults to the part before ' - SxxEyy' in --expected-name.")
    parser.add_argument("--expected-clean-folder", default="", help="Expected cleaned source folder title. Defaults to --expected-show.")
    parser.add_argument("--expected-season", type=int, default=None, help="Expected season detected from the source folder.")
    parser.add_argument("--season-number", type=int, default=1, help="Fallback season_number argument for auto-TV rename.")
    parser.add_argument(
        "--status",
        choices=sorted(VALID_RENAME_BAD_CASE_STATUSES),
        default="active",
        help="Use pending to log an unfixed case without gating tests.",
    )
    parser.add_argument("--notes", default="", help="Short note explaining what leaked or why this case exists.")
    parser.add_argument("--fixture-path", default=DEFAULT_RENAME_BAD_CASE_FIXTURE.as_posix(), help="Repo-relative fixture path.")
    parser.add_argument("--allow-current-mismatch", action="store_true", help="Allow appending an active case even when current filters do not pass it.")
    args = parser.parse_args(argv)

    repo_root = find_repo_root(Path(__file__))
    fixture_path = repo_root / args.fixture_path
    request = {
        "case_id": args.case_id,
        "source_folder": args.source_folder,
        "source_file": args.source_file,
        "expected_name": args.expected_name,
        "expected_show": args.expected_show,
        "expected_clean_folder": args.expected_clean_folder,
        "expected_season": args.expected_season,
        "season_number": args.season_number,
        "status": args.status,
        "notes": args.notes,
        "confirm_append": True,
        "allow_current_mismatch": args.allow_current_mismatch,
    }

    try:
        result = append_bad_rename_case_from_request(request, fixture_path=fixture_path, require_confirmation=True)
    except RenameBadCaseCorpusError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    rel = fixture_path.relative_to(repo_root).as_posix()
    print(f"Added rename filter case {result['case_id']} to {rel}")
    print("Run: apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_rename_bad_case_corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
