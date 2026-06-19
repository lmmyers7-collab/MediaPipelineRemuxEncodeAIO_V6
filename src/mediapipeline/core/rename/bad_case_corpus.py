"""Helpers for the rename bad-case regression corpus."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mediapipeline.core.rename.tv import (
    build_auto_tv_rename_name,
    clean_pipeline_tv_name_part,
    resolve_tv_folder_season_info,
)

DEFAULT_RENAME_BAD_CASE_FIXTURE = Path("tests/fixtures/rename/bad_rename_cases.jsonl")
RENAME_BAD_CASE_APPEND_SCHEMA_VERSION = "rename_bad_case_corpus_append.v1"
VALID_RENAME_BAD_CASE_STATUSES = {"active", "pending"}


class RenameBadCaseCorpusError(ValueError):
    """Raised when a bad rename corpus entry is invalid or unsafe to append."""


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:80].strip("-") or "rename-case"


def load_bad_rename_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                cases.append(payload)
    return cases


def unique_case_id(base: str, existing_ids: set[str]) -> str:
    case_id = slugify(base)
    if case_id not in existing_ids:
        return case_id
    for suffix in range(2, 1000):
        candidate = f"{case_id}-{suffix}"
        if candidate not in existing_ids:
            return candidate
    raise RenameBadCaseCorpusError(f"Could not create a unique case id from {base!r}.")


def expected_show_from_name(expected_name: str) -> str:
    match = re.match(r"(?i)^(?P<show>.+?)\s+-\s+S\d{2}E\d{2,3}\b", expected_name)
    return match.group("show").strip() if match else ""


def expected_season_from_name(expected_name: str) -> int | None:
    match = re.search(r"(?i)\bS(?P<season>\d{2})E\d{2,3}\b", expected_name)
    return int(match.group("season")) if match else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _compact_note(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value))


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None or _text(value) == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RenameBadCaseCorpusError(f"{field_name} must be an integer.") from exc


def _require_text(data: dict[str, Any], field_name: str) -> str:
    value = _text(data.get(field_name))
    if not value:
        raise RenameBadCaseCorpusError(f"{field_name} is required.")
    if "\n" in value or "\r" in value:
        raise RenameBadCaseCorpusError(f"{field_name} cannot contain newlines.")
    return value


def _validate_safe_relative_folder(value: str) -> None:
    if ":" in value:
        raise RenameBadCaseCorpusError("source_folder must be repo-safe relative text, not an absolute path.")
    if Path(value).is_absolute():
        raise RenameBadCaseCorpusError("source_folder must be repo-safe relative text, not an absolute path.")
    parts = [part for part in re.split(r"[\\/]+", value) if part]
    if any(part in {".", ".."} for part in parts):
        raise RenameBadCaseCorpusError("source_folder cannot contain relative traversal segments.")


def _validate_filename(value: str, field_name: str) -> None:
    if "/" in value or "\\" in value:
        raise RenameBadCaseCorpusError(f"{field_name} must be a filename, not a path.")


def current_tv_auto_result(case: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    source = Path("TV") / str(case["source_folder"]) / str(case["source_file"])
    remove_terms = case.get("remove_terms") or None
    cleaned_folder = clean_pipeline_tv_name_part(source.parent.name, remove_terms)
    folder_info = resolve_tv_folder_season_info(source, remove_terms)
    output_name = build_auto_tv_rename_name(
        source,
        season_number=int(case.get("season_number", 1)),
        remove_terms=remove_terms,
    )
    return cleaned_folder, output_name, folder_info


def validate_active_bad_rename_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if case["kind"] != "tv_auto":
        return [f"Unsupported kind for current validation: {case['kind']}"]
    try:
        cleaned_folder, output_name, folder_info = current_tv_auto_result(case)
    except Exception as exc:  # pragma: no cover - surfaced through command/CLI output
        return [f"Current rename helper raised {type(exc).__name__}: {exc}"]

    expected_clean_folder = str(case.get("expected_clean_folder") or "").strip()
    if expected_clean_folder and cleaned_folder != expected_clean_folder:
        errors.append(f"expected_clean_folder mismatch: current {cleaned_folder!r}")
    expected_season = case.get("expected_season")
    if expected_season is not None and (folder_info is None or folder_info.get("season") != expected_season):
        errors.append(f"expected_season mismatch: current {None if folder_info is None else folder_info.get('season')!r}")
    expected_show = str(case.get("expected_show") or "").strip()
    if expected_show and (folder_info is None or folder_info.get("show") != expected_show):
        errors.append(f"expected_show mismatch: current {None if folder_info is None else folder_info.get('show')!r}")
    if output_name != case["expected_name"]:
        errors.append(f"expected_name mismatch: current {output_name!r}")
    return errors


def build_bad_rename_case(data: dict[str, Any], existing_ids: set[str]) -> dict[str, Any]:
    kind = _text(data.get("kind") or "tv_auto")
    if kind != "tv_auto":
        raise RenameBadCaseCorpusError(f"Unsupported rename case kind: {kind}")
    status = _text(data.get("status") or "active").lower()
    if status not in VALID_RENAME_BAD_CASE_STATUSES:
        raise RenameBadCaseCorpusError(f"status must be one of: {', '.join(sorted(VALID_RENAME_BAD_CASE_STATUSES))}.")

    source_folder = _require_text(data, "source_folder")
    source_file = _require_text(data, "source_file")
    expected_name = _require_text(data, "expected_name")
    _validate_safe_relative_folder(source_folder)
    _validate_filename(source_file, "source_file")
    _validate_filename(expected_name, "expected_name")

    season_number = _optional_int(data.get("season_number"), "season_number") or 1
    if season_number < 1:
        raise RenameBadCaseCorpusError("season_number must be 1 or greater.")
    expected_show = _text(data.get("expected_show")) or expected_show_from_name(expected_name)
    expected_clean_folder = _text(data.get("expected_clean_folder")) or expected_show
    expected_season = _optional_int(data.get("expected_season"), "expected_season")
    if expected_season is None:
        expected_season = expected_season_from_name(expected_name)
    if expected_season is not None and expected_season < 0:
        raise RenameBadCaseCorpusError("expected_season must be 0 or greater.")

    explicit_case_id = _text(data.get("case_id") or data.get("id"))
    if explicit_case_id and explicit_case_id in existing_ids:
        raise RenameBadCaseCorpusError(f"Case id already exists: {explicit_case_id}")
    base_id = explicit_case_id or f"{expected_show or source_folder}-{Path(source_file).stem}"

    case: dict[str, Any] = {
        "id": explicit_case_id or unique_case_id(base_id, existing_ids),
        "status": status,
        "kind": "tv_auto",
        "source_folder": source_folder,
        "source_file": source_file,
        "season_number": season_number,
        "expected_show": expected_show,
        "expected_clean_folder": expected_clean_folder,
        "expected_name": expected_name,
    }
    if expected_season is not None:
        case["expected_season"] = expected_season
    remove_terms = data.get("remove_terms")
    if remove_terms:
        case["remove_terms"] = remove_terms
    notes = _compact_note(data.get("notes"))
    if notes:
        case["notes"] = notes
    return case


def append_bad_rename_case(path: Path, case: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_leading_newline = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        if needs_leading_newline:
            handle.write("\n")
        handle.write(json.dumps(case, ensure_ascii=True, separators=(",", ":")))


def append_bad_rename_case_from_request(
    request: dict[str, Any],
    *,
    fixture_path: Path,
    require_confirmation: bool = True,
) -> dict[str, Any]:
    if require_confirmation and request.get("confirm_append") is not True:
        raise RenameBadCaseCorpusError("confirm_append must be true before appending a rename filter case.")

    existing = load_bad_rename_cases(fixture_path)
    existing_ids = {str(case.get("id")) for case in existing if case.get("id")}
    case = build_bad_rename_case(request, existing_ids)
    validation_errors: list[str] = []
    if case["status"] == "active":
        validation_errors = validate_active_bad_rename_case(case)
        if validation_errors and request.get("allow_current_mismatch") is not True:
            joined = "; ".join(validation_errors)
            raise RenameBadCaseCorpusError(
                "Active case does not pass current rename filters. "
                f"{joined} Use status=pending to log it before the filter fix."
            )

    append_bad_rename_case(fixture_path, case)
    return {
        "schema_version": RENAME_BAD_CASE_APPEND_SCHEMA_VERSION,
        "case_id": case["id"],
        "status": case["status"],
        "fixture_path": str(fixture_path),
        "current_validation_errors": validation_errors,
        "case": case,
    }
