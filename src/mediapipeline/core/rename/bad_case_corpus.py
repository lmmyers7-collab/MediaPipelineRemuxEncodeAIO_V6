"""Helpers for the rename bad-case regression corpus."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.rename.movie import clean_pipeline_movie_name
from mediapipeline.core.rename.plan_policy import normalize_rename_template_preset, rename_template_includes_tv_episode_title
from mediapipeline.core.rename.tv import (
    build_auto_tv_rename_name,
    clean_pipeline_tv_name_part,
    parse_tv_identity,
    resolve_tv_folder_season_info,
)

DEFAULT_RENAME_BAD_CASE_FIXTURE = Path("tests/fixtures/rename/bad_rename_cases.jsonl")
RENAME_BAD_CASE_APPEND_SCHEMA_VERSION = "rename_bad_case_corpus_append.v1"
VALID_RENAME_BAD_CASE_STATUSES = {"active", "pending"}
VALID_RENAME_BAD_CASE_KINDS = {"tv_auto", "movie_auto"}


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


def expected_episode_from_name(expected_name: str) -> int | None:
    match = re.search(r"(?i)\bS\d{2}E(?P<episode>\d{2,3})\b", expected_name)
    return int(match.group("episode")) if match else None


def expected_episode_end_from_name(expected_name: str) -> int | None:
    match = re.search(r"(?i)\bS\d{2}E\d{2,3}-E(?P<episode_end>\d{2,3})\b", expected_name)
    return int(match.group("episode_end")) if match else None


def expected_episode_title_from_name(expected_name: str) -> str:
    stem = Path(expected_name).stem
    match = re.match(r"(?i)^.+?\s+-\s+S\d{2}E\d{2,3}(?:-E\d{2,3})?\s+-\s+(?P<title>.+)$", stem)
    return match.group("title").strip() if match else ""


def expected_movie_title_from_name(expected_name: str) -> str:
    stem = Path(expected_name).stem
    match = re.match(r"^(?P<title>.+?)\s+\((?:19|20)\d{2}\)$", stem)
    return match.group("title").strip() if match else stem.strip()


def expected_movie_year_from_name(expected_name: str) -> str:
    match = re.search(r"\((?P<year>(?:19|20)\d{2})\)", expected_name)
    return match.group("year") if match else ""


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


def _suffix_for_source_file(source_file: str) -> str:
    suffix = Path(source_file).suffix.lower()
    return suffix if suffix in MEDIA_FILE_SUFFIXES else ""


def _expected_movie_name(data: dict[str, Any], source_file: str) -> str:
    explicit = _text(data.get("expected_name"))
    if explicit:
        return explicit
    title = _text(data.get("expected_movie_title"))
    year = _text(data.get("expected_year"))
    if not title:
        raise RenameBadCaseCorpusError("expected_name or expected_movie_title is required for movie_auto cases.")
    suffix = _suffix_for_source_file(source_file)
    return f"{title} ({year}){suffix}" if year else f"{title}{suffix}"


def _tv_remove_terms(case: dict[str, Any]) -> list[str] | None:
    if "tv_remove_terms" in case:
        return list(case.get("tv_remove_terms") or [])
    return case.get("remove_terms") or None


def current_tv_auto_result(case: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    source = Path("TV") / str(case["source_folder"]) / str(case["source_file"])
    remove_terms = _tv_remove_terms(case)
    tv_filter_options = case.get("tv_filter_options") or None
    tv_filter_terms = case.get("tv_filter_terms") or None
    template_preset = normalize_rename_template_preset(case.get("template_preset"), "tv")
    cleaned_folder = clean_pipeline_tv_name_part(source.parent.name, remove_terms, tv_filter_options, tv_filter_terms)
    folder_info = resolve_tv_folder_season_info(source, remove_terms, tv_filter_options, tv_filter_terms)
    output_name = build_auto_tv_rename_name(
        source,
        season_number=int(case.get("season_number", 1)),
        remove_terms=remove_terms,
        tv_filter_options=tv_filter_options,
        tv_filter_terms=tv_filter_terms,
        include_episode_title=rename_template_includes_tv_episode_title(template_preset),
    )
    return cleaned_folder, output_name, folder_info


def current_movie_auto_result(case: dict[str, Any]) -> str:
    source_file = str(case["source_file"])
    remove_terms = case.get("remove_terms") or None
    output_title = clean_pipeline_movie_name(
        source_file,
        remove_terms,
        case.get("movie_filter_options") or None,
        case.get("movie_filter_terms") or None,
    )
    suffix = _suffix_for_source_file(source_file)
    return f"{output_title}{suffix}" if output_title else ""


def validate_active_bad_rename_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if case["kind"] == "movie_auto":
        try:
            output_name = current_movie_auto_result(case)
        except Exception as exc:  # pragma: no cover - surfaced through command/CLI output
            return [f"Current movie rename helper raised {type(exc).__name__}: {exc}"]
        if case.get("expected_blocked") is True:
            if output_name:
                errors.append(f"expected blocked movie result: current {output_name!r}")
        elif output_name != case["expected_name"]:
            errors.append(f"expected_name mismatch: current {output_name!r}")
        return errors
    if case["kind"] != "tv_auto":
        return [f"Unsupported kind for current validation: {case['kind']}"]
    source = Path("TV") / str(case["source_folder"]) / str(case["source_file"])
    remove_terms = _tv_remove_terms(case)
    tv_filter_options = case.get("tv_filter_options") or None
    tv_filter_terms = case.get("tv_filter_terms") or None
    identity = parse_tv_identity(
        source,
        season_number=int(case.get("season_number", 1)),
        remove_terms=remove_terms,
        tv_filter_options=tv_filter_options,
        tv_filter_terms=tv_filter_terms,
    )
    expected_blocked = case.get("expected_blocked") is True
    expected_episode = case.get("expected_episode")
    if expected_episode is not None and identity.get("episode_start") != expected_episode:
        errors.append(f"expected_episode mismatch: current {identity.get('episode_start')!r}")
    if "expected_episode_end" in case and identity.get("episode_end") != case.get("expected_episode_end"):
        errors.append(f"expected_episode_end mismatch: current {identity.get('episode_end')!r}")
    if expected_blocked:
        if identity.get("reliable"):
            errors.append("expected blocked TV parse: current identity is reliable")
        expected_parse_mode = _text(case.get("expected_parse_mode"))
        if expected_parse_mode and identity.get("parse_mode") != expected_parse_mode:
            errors.append(f"expected_parse_mode mismatch: current {identity.get('parse_mode')!r}")
        expected_error = _text(case.get("expected_error_contains"))
        if expected_error and expected_error.casefold() not in _text(identity.get("parse_error")).casefold():
            errors.append(f"expected_error_contains mismatch: current {identity.get('parse_error')!r}")
        expected_reason = _text(case.get("expected_block_reason_code"))
        if expected_reason and expected_reason != "tv_parse_unreliable":
            errors.append("expected_block_reason_code mismatch: current 'tv_parse_unreliable'")
        return errors
    if not identity.get("reliable"):
        return [f"Current TV identity is unreliable: {identity.get('parse_error')}"]
    try:
        cleaned_folder, output_name, folder_info = current_tv_auto_result(case)
    except Exception as exc:  # pragma: no cover - surfaced through command/CLI output
        return [f"Current rename helper raised {type(exc).__name__}: {exc}"]

    expected_clean_folder = str(case.get("expected_clean_folder") or "").strip()
    if expected_clean_folder and cleaned_folder != expected_clean_folder:
        errors.append(f"expected_clean_folder mismatch: current {cleaned_folder!r}")
    expected_season = case.get("expected_season")
    if expected_season is not None and identity.get("season") != expected_season:
        errors.append(f"expected_season mismatch: current {identity.get('season')!r}")
    expected_show = str(case.get("expected_show") or "").strip()
    if expected_show and identity.get("show") != expected_show:
        errors.append(f"expected_show mismatch: current {identity.get('show')!r}")
    if output_name != case["expected_name"]:
        errors.append(f"expected_name mismatch: current {output_name!r}")
    expected_parse_mode = _text(case.get("expected_parse_mode"))
    if expected_parse_mode and identity.get("parse_mode") != expected_parse_mode:
        errors.append(f"expected_parse_mode mismatch: current {identity.get('parse_mode')!r}")
    expected_episode_title = str(case.get("expected_episode_title") or "").strip()
    if expected_episode_title and expected_episode_title_from_name(output_name) != expected_episode_title:
        errors.append(f"expected_episode_title mismatch: current {expected_episode_title_from_name(output_name)!r}")
    return errors


def _copy_optional_case_fields(case: dict[str, Any], data: dict[str, Any], *, kind: str) -> None:
    for field_name in (
        "expected_parse_mode",
        "expected_block_reason_code",
        "expected_error_contains",
        "expected_queue_show_sort_key",
        "expected_queue_block_reason_code",
    ):
        value = _text(data.get(field_name))
        if value:
            case[field_name] = value
    for field_name in ("expected_queue_season_sort_order", "expected_queue_episode_sort_order"):
        value = _optional_int(data.get(field_name), field_name)
        if value is not None:
            case[field_name] = value
    for field_name in ("expected_blocked", "expected_queue_blocked"):
        if field_name not in data:
            continue
        value = data.get(field_name)
        if not isinstance(value, bool):
            raise RenameBadCaseCorpusError(f"{field_name} must be a boolean.")
        case[field_name] = value
    policy_fields = (
        ("movie_filter_options", dict),
        ("movie_filter_terms", dict),
        ("remove_terms", list),
    ) if kind == "movie_auto" else (
        ("tv_filter_options", dict),
        ("tv_filter_terms", dict),
        ("tv_remove_terms", list),
    )
    for field_name, field_type in policy_fields:
        if field_name not in data:
            continue
        value = data.get(field_name)
        if not isinstance(value, field_type):
            raise RenameBadCaseCorpusError(f"{field_name} must be a {field_type.__name__}.")
        if field_name.endswith("_filter_options") and any(not isinstance(item, bool) for item in value.values()):
            raise RenameBadCaseCorpusError(f"{field_name} values must be booleans.")
        if field_name.endswith("_filter_terms") and any(
            not isinstance(items, list) or any(not isinstance(item, str) for item in items)
            for items in value.values()
        ):
            raise RenameBadCaseCorpusError(f"{field_name} values must be lists of strings.")
        if field_name.endswith("remove_terms") and any(not isinstance(item, str) for item in value):
            raise RenameBadCaseCorpusError(f"{field_name} values must be strings.")
        case[field_name] = value.copy() if isinstance(value, dict) else list(value)


def build_bad_rename_case(data: dict[str, Any], existing_ids: set[str]) -> dict[str, Any]:
    kind = _text(data.get("kind") or "tv_auto")
    if kind not in VALID_RENAME_BAD_CASE_KINDS:
        raise RenameBadCaseCorpusError(f"Unsupported rename case kind: {kind}")
    status = _text(data.get("status") or "active").lower()
    if status not in VALID_RENAME_BAD_CASE_STATUSES:
        raise RenameBadCaseCorpusError(f"status must be one of: {', '.join(sorted(VALID_RENAME_BAD_CASE_STATUSES))}.")

    if kind == "movie_auto":
        source_folder = _text(data.get("source_folder")) or "Movies"
        if "\n" in source_folder or "\r" in source_folder:
            raise RenameBadCaseCorpusError("source_folder cannot contain newlines.")
    else:
        source_folder = _require_text(data, "source_folder")
    source_file = _require_text(data, "source_file")
    expected_blocked = data.get("expected_blocked") is True
    expected_name = (
        _expected_movie_name(data, source_file)
        if kind == "movie_auto"
        else _text(data.get("expected_name"))
    )
    if kind == "tv_auto" and not expected_name and not expected_blocked:
        raise RenameBadCaseCorpusError("expected_name is required unless expected_blocked is true.")
    _validate_safe_relative_folder(source_folder)
    _validate_filename(source_file, "source_file")
    _validate_filename(expected_name, "expected_name")
    if "remove_terms" in data:
        remove_terms = data.get("remove_terms")
        if not isinstance(remove_terms, list) or any(not isinstance(item, str) for item in remove_terms):
            raise RenameBadCaseCorpusError("remove_terms must be a list of strings.")

    if kind == "movie_auto":
        expected_movie_title = _text(data.get("expected_movie_title")) or expected_movie_title_from_name(expected_name)
        expected_year = _text(data.get("expected_year")) or expected_movie_year_from_name(expected_name)
        explicit_case_id = _text(data.get("case_id") or data.get("id"))
        if explicit_case_id and explicit_case_id in existing_ids:
            raise RenameBadCaseCorpusError(f"Case id already exists: {explicit_case_id}")
        base_id = explicit_case_id or f"{expected_movie_title or Path(source_file).stem}-{expected_year or 'movie'}"
        case = {
            "id": explicit_case_id or unique_case_id(base_id, existing_ids),
            "status": status,
            "kind": "movie_auto",
            "source_folder": source_folder,
            "source_file": source_file,
            "expected_movie_title": expected_movie_title,
            "expected_name": expected_name,
        }
        if expected_year:
            case["expected_year"] = expected_year
        _copy_optional_case_fields(case, data, kind="movie_auto")
        notes = _compact_note(data.get("notes"))
        if notes:
            case["notes"] = notes
        return case

    season_number = _optional_int(data.get("season_number"), "season_number") or 1
    if season_number < 1:
        raise RenameBadCaseCorpusError("season_number must be 1 or greater.")
    expected_show = _text(data.get("expected_show")) or expected_show_from_name(expected_name)
    expected_clean_folder = _text(data.get("expected_clean_folder"))
    if not expected_clean_folder:
        source_folder_leaf = re.split(r"[\\/]", source_folder)[-1]
        remove_terms = data.get("tv_remove_terms") if "tv_remove_terms" in data else data.get("remove_terms")
        expected_clean_folder = clean_pipeline_tv_name_part(
            source_folder_leaf,
            remove_terms or None,
            data.get("tv_filter_options") or None,
            data.get("tv_filter_terms") or None,
        )
    expected_season = _optional_int(data.get("expected_season"), "expected_season")
    if expected_season is None:
        expected_season = expected_season_from_name(expected_name)
    if expected_season is not None and expected_season < 0:
        raise RenameBadCaseCorpusError("expected_season must be 0 or greater.")
    expected_episode = _optional_int(data.get("expected_episode"), "expected_episode")
    if expected_episode is None:
        expected_episode = expected_episode_from_name(expected_name)
    if status == "active" and expected_blocked and expected_episode is None:
        raise RenameBadCaseCorpusError("expected_episode is required for active blocked tv_auto cases.")
    if expected_episode is not None and expected_episode < 0:
        raise RenameBadCaseCorpusError("expected_episode must be 0 or greater.")
    expected_episode_end = _optional_int(data.get("expected_episode_end"), "expected_episode_end")
    if status == "active" and expected_blocked and "expected_episode_end" not in data:
        raise RenameBadCaseCorpusError("expected_episode_end is required for active blocked tv_auto cases.")
    if expected_episode_end is None and not expected_blocked:
        expected_episode_end = expected_episode_end_from_name(expected_name)
    template_preset = normalize_rename_template_preset(data.get("template_preset"), "tv")
    expected_episode_title = _text(data.get("expected_episode_title")) or expected_episode_title_from_name(expected_name)

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
        "template_preset": template_preset,
        "expected_show": expected_show,
        "expected_clean_folder": expected_clean_folder,
        "expected_name": expected_name,
    }
    if expected_season is not None:
        case["expected_season"] = expected_season
    if expected_episode is not None:
        case["expected_episode"] = expected_episode
    case["expected_episode_end"] = expected_episode_end
    if expected_episode_title:
        case["expected_episode_title"] = expected_episode_title
    remove_terms = data.get("remove_terms")
    if remove_terms:
        case["remove_terms"] = remove_terms
    _copy_optional_case_fields(case, data, kind="tv_auto")
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
