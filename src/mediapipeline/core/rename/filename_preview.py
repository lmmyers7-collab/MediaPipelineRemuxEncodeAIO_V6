"""Read-only rename filename preview and filter catalog payloads."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from collections.abc import Callable, Mapping

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.rename.cleaning_policy import (
    RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY,
    dict_bool,
    dict_str,
    dict_terms,
    remove_terms_from_request,
    rename_cleaning_policy_from_config,
    rename_cleaning_policy_from_request,
)
from mediapipeline.core.rename.movie import (
    normalize_movie_filter_options,
    normalize_movie_filter_terms,
    rename_movie_filter_default_terms,
)
from mediapipeline.core.rename.plan_policy import normalize_rename_template_preset, rename_template_includes_tv_episode_title
from mediapipeline.core.rename.tv import (
    clean_pipeline_tv_name_part,
    normalize_tv_filter_options,
    normalize_tv_filter_terms,
    rename_tv_filter_default_terms,
)


def rename_filename_leaf(value: object) -> str:
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    return PureWindowsPath(PurePosixPath(text).name).name


def rename_clean_filename_preview_from_request(
    request: Mapping[str, Any],
    *,
    parse_remove_terms: Callable[[str], list[str]] | None = None,
    clean_movie_name: Callable[
        [str, list[str] | None, dict[str, bool] | None, dict[str, list[str]] | None],
        str,
    ],
    build_auto_tv_name: Callable[..., str] | None = None,
) -> dict[str, Any]:
    raw_input = str(request.get("filename") or request.get("file_name") or request.get("input") or "").strip()
    input_name = rename_filename_leaf(raw_input)
    mode = str(request.get("mode") or "movie").strip().casefold()
    if mode not in {"movie", "tv"}:
        mode = "movie"
    template_preset = normalize_rename_template_preset(request.get("template_preset"), mode)
    policy_source = str(request.get(RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY) or "staged").strip().casefold() or "staged"
    if policy_source not in {"saved", "staged"}:
        policy_source = "staged"
    warnings: list[str] = []
    if raw_input and input_name != raw_input.strip().strip('"'):
        warnings.append("Only the filename portion was evaluated; parent paths are ignored by this read-only test.")
    if not input_name:
        return {
            "schema_version": "desktop_rename_clean_filename_preview.v1",
            "ok": False,
            "input": raw_input,
            "input_name": "",
            "cleaned_title": "",
            "target_name": "",
            "mode": mode,
            "template_preset": template_preset,
            "preview_source": "backend_tv_cleaner" if mode == "tv" else "backend_movie_cleaner",
            "evidence_authority": "backend",
            "rename_cleaning_policy_source": policy_source,
            "effective_policy_source": policy_source,
            "movie_filter_terms_mode": policy_source,
            "filter_evidence": _rename_filter_evidence(
                mode=mode,
                policy_source=policy_source,
                input_name=input_name,
                source_folder=str(request.get("source_folder") or ""),
                options={},
                terms={},
                remove_terms=[],
            ),
            "warnings": [f"Enter a filename to test the backend {mode} cleaner."],
            "errors": [],
            "mutation_boundary": "read-only filename preview; no filesystem paths are opened, renamed, moved, deleted, or written",
        }

    suffix = PureWindowsPath(input_name).suffix.lower()
    has_media_suffix = suffix in MEDIA_FILE_SUFFIXES
    cleaner_input = input_name if has_media_suffix else f"{input_name}.mkv"
    if mode == "tv":
        return _rename_tv_clean_filename_preview_from_request(
            request,
            raw_input=raw_input,
            input_name=input_name,
            cleaner_input=cleaner_input,
            suffix=suffix,
            has_media_suffix=has_media_suffix,
            warnings=warnings,
            policy_source=policy_source,
            template_preset=template_preset,
            parse_remove_terms=parse_remove_terms,
            build_auto_tv_name=build_auto_tv_name,
        )
    remove_terms = remove_terms_from_request(request, parse_remove_terms)
    movie_filter_options = dict_bool(request.get("movie_filter_options"))
    movie_filter_terms = dict_terms(request.get("movie_filter_terms"), parse_remove_terms)
    try:
        cleaned_title = clean_movie_name(cleaner_input, remove_terms, movie_filter_options, movie_filter_terms)
    except Exception as exc:
        payload = {
            "schema_version": "desktop_rename_clean_filename_preview.v1",
            "ok": False,
            "input": raw_input,
            "input_name": input_name,
            "cleaned_title": "",
            "target_name": "",
            "mode": mode,
            "template_preset": template_preset,
            "preview_source": "backend_movie_cleaner",
            "evidence_authority": "backend",
            "rename_cleaning_policy_source": policy_source,
            "effective_policy_source": policy_source,
            "movie_filter_terms_mode": policy_source,
            "filter_evidence": _rename_filter_evidence(
                mode=mode,
                policy_source=policy_source,
                input_name=input_name,
                source_folder="",
                options=movie_filter_options,
                terms=movie_filter_terms,
                remove_terms=remove_terms,
            ),
            "warnings": warnings,
            "errors": [str(exc)],
            "mutation_boundary": "read-only filename preview; no filesystem paths are opened, renamed, moved, deleted, or written",
        }
        return _with_case_analysis(payload, request)

    target_name = f"{cleaned_title}{suffix}" if cleaned_title and has_media_suffix else cleaned_title
    if not has_media_suffix:
        warnings.append("No known media extension was supplied; the cleaner assumed .mkv internally and returned a title-only preview.")
    payload = {
        "schema_version": "desktop_rename_clean_filename_preview.v1",
        "ok": bool(cleaned_title),
        "input": raw_input,
        "input_name": input_name,
        "cleaned_title": cleaned_title,
        "target_name": target_name,
        "mode": mode,
        "template_preset": template_preset,
        "preview_source": "backend_movie_cleaner",
        "evidence_authority": "backend",
        "rename_cleaning_policy_source": policy_source,
        "effective_policy_source": policy_source,
        "remove_terms_count": len(remove_terms),
        "movie_filter_terms_enabled": True,
        "movie_filter_terms_mode": policy_source,
        "movie_filter_option_count": len(movie_filter_options),
        "movie_filter_term_counts": {key: len(values) for key, values in movie_filter_terms.items()},
        "filter_evidence": _rename_filter_evidence(
            mode=mode,
            policy_source=policy_source,
            input_name=input_name,
            source_folder="",
            options=movie_filter_options,
            terms=movie_filter_terms,
            remove_terms=remove_terms,
        ),
        "assumed_media_extension": not has_media_suffix,
        "warnings": warnings,
        "errors": [] if cleaned_title else ["Filename is empty after backend movie cleaning."],
        "mutation_boundary": "read-only filename preview; no filesystem paths are opened, renamed, moved, deleted, or written",
    }
    return _with_case_analysis(payload, request)


def _season_number_from_request(request: Mapping[str, Any]) -> int:
    raw = str(request.get("season") or request.get("season_value") or "S01")
    match = re.search(r"\d{1,2}", raw)
    return int(match.group(0)) if match else 1


def _rename_tv_clean_filename_preview_from_request(
    request: Mapping[str, Any],
    *,
    raw_input: str,
    input_name: str,
    cleaner_input: str,
    suffix: str,
    has_media_suffix: bool,
    warnings: list[str],
    policy_source: str,
    template_preset: str,
    parse_remove_terms: Callable[[str], list[str]] | None,
    build_auto_tv_name: Callable[..., str] | None,
) -> dict[str, Any]:
    if not callable(build_auto_tv_name):
        return {
            "schema_version": "desktop_rename_clean_filename_preview.v1",
            "ok": False,
            "input": raw_input,
            "input_name": input_name,
            "cleaned_title": "",
            "target_name": "",
            "mode": "tv",
            "template_preset": template_preset,
            "preview_source": "backend_tv_cleaner",
            "evidence_authority": "backend",
            "rename_cleaning_policy_source": policy_source,
            "effective_policy_source": policy_source,
            "movie_filter_terms_mode": policy_source,
            "tv_filter_terms_mode": policy_source,
            "warnings": warnings,
            "errors": ["Rename TV cleaner is not available."],
            "mutation_boundary": "read-only filename preview; no filesystem paths are opened, renamed, moved, deleted, or written",
        }
    tv_remove_terms = remove_terms_from_request(
        request,
        parse_remove_terms,
        key="tv_remove_terms",
        text_key="tv_remove_terms_text",
        fallback_key="remove_terms",
        fallback_text_key="remove_terms_text",
    )
    tv_filter_options = dict_bool(request.get("tv_filter_options"))
    tv_filter_terms = dict_terms(request.get("tv_filter_terms"), parse_remove_terms)
    source_folder = str(request.get("source_folder") or "").strip().strip('"')
    source = Path(source_folder or "Show") / cleaner_input
    try:
        target_name = build_auto_tv_name(
            source,
            season_number=_season_number_from_request(request),
            remove_terms=tv_remove_terms,
            tv_filter_options=tv_filter_options,
            tv_filter_terms=tv_filter_terms,
            include_episode_title=rename_template_includes_tv_episode_title(template_preset),
        )
    except Exception as exc:
        payload = {
            "schema_version": "desktop_rename_clean_filename_preview.v1",
            "ok": False,
            "input": raw_input,
            "input_name": input_name,
            "cleaned_title": "",
            "target_name": "",
            "mode": "tv",
            "template_preset": template_preset,
            "source_folder": source_folder,
            "preview_source": "backend_tv_cleaner",
            "evidence_authority": "backend",
            "rename_cleaning_policy_source": policy_source,
            "effective_policy_source": policy_source,
            "movie_filter_terms_mode": policy_source,
            "tv_filter_terms_mode": policy_source,
            "filter_evidence": _rename_filter_evidence(
                mode="tv",
                policy_source=policy_source,
                input_name=input_name,
                source_folder=source_folder,
                options=tv_filter_options,
                terms=tv_filter_terms,
                remove_terms=tv_remove_terms,
            ),
            "warnings": warnings,
            "errors": [str(exc)],
            "mutation_boundary": "read-only filename preview; no filesystem paths are opened, renamed, moved, deleted, or written",
        }
        return _with_case_analysis(payload, request)
    if not has_media_suffix:
        warnings.append("No known media extension was supplied; the cleaner assumed .mkv internally and returned a filename preview.")
    cleaned_title = Path(target_name).stem
    payload = {
        "schema_version": "desktop_rename_clean_filename_preview.v1",
        "ok": bool(target_name),
        "input": raw_input,
        "input_name": input_name,
        "cleaned_title": cleaned_title,
        "target_name": target_name if has_media_suffix else cleaned_title,
        "mode": "tv",
        "template_preset": template_preset,
        "source_folder": source_folder,
        "preview_source": "backend_tv_cleaner",
        "evidence_authority": "backend",
        "rename_cleaning_policy_source": policy_source,
        "effective_policy_source": policy_source,
        "remove_terms_count": len(tv_remove_terms),
        "tv_filter_terms_enabled": True,
        "tv_filter_terms_mode": policy_source,
        "tv_filter_option_count": len(tv_filter_options),
        "tv_filter_term_counts": {key: len(values) for key, values in tv_filter_terms.items()},
        "movie_filter_terms_mode": policy_source,
        "filter_evidence": _rename_filter_evidence(
            mode="tv",
            policy_source=policy_source,
            input_name=input_name,
            source_folder=source_folder,
            options=tv_filter_options,
            terms=tv_filter_terms,
            remove_terms=tv_remove_terms,
        ),
        "assumed_media_extension": not has_media_suffix,
        "warnings": warnings,
        "errors": [] if target_name else ["Filename is empty after backend TV cleaning."],
        "mutation_boundary": "read-only filename preview; no filesystem paths are opened, renamed, moved, deleted, or written",
    }
    return _with_case_analysis(payload, request)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _parse_int(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _target_stem(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return Path(rename_filename_leaf(text)).stem


def _parse_tv_fields(name: object) -> dict[str, Any]:
    stem = _target_stem(name)
    match = re.match(
        r"(?i)^(?P<show>.+?)\s+-\s+S(?P<season>\d{2})E(?P<episode>\d{2,3})"
        r"(?:-E(?P<episode_end>\d{2,3}))?(?:\s+-\s+(?P<title>.+))?$",
        stem,
    )
    if not match:
        return {"show": "", "season": None, "episode": None, "episode_end": None, "episode_title": "", "target_stem": stem}
    return {
        "show": _clean_text(match.group("show")),
        "season": int(match.group("season")),
        "episode": int(match.group("episode")),
        "episode_end": int(match.group("episode_end")) if match.group("episode_end") else None,
        "episode_title": _clean_text(match.group("title") or ""),
        "target_stem": stem,
    }


def _parse_movie_fields(name: object) -> dict[str, Any]:
    stem = _target_stem(name)
    match = re.match(r"^(?P<title>.+?)\s+\((?P<year>(?:19|20)\d{2})\)$", stem)
    if not match:
        return {"movie_title": _clean_text(stem), "year": "", "target_stem": stem}
    return {
        "movie_title": _clean_text(match.group("title")),
        "year": match.group("year"),
        "target_stem": stem,
    }


def _format_expected_tv_name(request: Mapping[str, Any], suffix: str, template_preset: str) -> str:
    explicit = _clean_text(request.get("expected_name"))
    if explicit:
        return explicit
    show = _clean_text(request.get("expected_show"))
    season = _parse_int(request.get("expected_season"))
    episode = _parse_int(request.get("expected_episode"))
    if not show or season is None or episode is None:
        return ""
    episode_title = _clean_text(request.get("expected_episode_title"))
    episode_end = _parse_int(request.get("expected_episode_end"))
    range_part = f"-E{episode_end:02d}" if episode_end is not None else ""
    title_part = f" - {episode_title}" if episode_title and rename_template_includes_tv_episode_title(template_preset) else ""
    return f"{show} - S{season:02d}E{episode:02d}{range_part}{title_part}{suffix}"


def _format_expected_movie_name(request: Mapping[str, Any], suffix: str) -> str:
    explicit = _clean_text(request.get("expected_name"))
    if explicit:
        return explicit
    title = _clean_text(request.get("expected_movie_title"))
    year = _clean_text(request.get("expected_year"))
    if not title:
        return ""
    return f"{title} ({year}){suffix}" if year else f"{title}{suffix}"


def _case_suffix(payload: Mapping[str, Any]) -> str:
    input_name = str(payload.get("input_name") or "")
    suffix = Path(input_name).suffix.lower()
    return suffix if suffix in MEDIA_FILE_SUFFIXES else ""


def _expected_fields(request: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "movie")
    suffix = _case_suffix(payload)
    if mode == "tv":
        template_preset = str(payload.get("template_preset") or normalize_rename_template_preset(request.get("template_preset"), "tv"))
        expected_name = _format_expected_tv_name(request, suffix, template_preset)
        parsed = _parse_tv_fields(expected_name)
        parsed.update(
            {
                "expected_name": expected_name,
                "show": _clean_text(request.get("expected_show")) or parsed.get("show", ""),
                "season": _parse_int(request.get("expected_season")) if _clean_text(request.get("expected_season")) else parsed.get("season"),
                "episode": _parse_int(request.get("expected_episode")) if _clean_text(request.get("expected_episode")) else parsed.get("episode"),
                "episode_end": (
                    _parse_int(request.get("expected_episode_end"))
                    if _clean_text(request.get("expected_episode_end"))
                    else parsed.get("episode_end")
                ),
                "episode_title": _clean_text(request.get("expected_episode_title")) or parsed.get("episode_title", ""),
                "template_preset": template_preset,
            }
        )
        if not rename_template_includes_tv_episode_title(template_preset):
            parsed["episode_title"] = ""
        return parsed
    expected_name = _format_expected_movie_name(request, suffix)
    parsed = _parse_movie_fields(expected_name)
    parsed.update(
        {
            "expected_name": expected_name,
            "movie_title": _clean_text(request.get("expected_movie_title")) or parsed.get("movie_title", ""),
            "year": _clean_text(request.get("expected_year")) or parsed.get("year", ""),
            "template_preset": str(payload.get("template_preset") or "movie_standard"),
        }
    )
    return parsed


def _actual_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    target_name = str(payload.get("target_name") or payload.get("cleaned_title") or "")
    if str(payload.get("mode") or "movie") == "tv":
        parsed = _parse_tv_fields(target_name)
    else:
        parsed = _parse_movie_fields(target_name)
    parsed["target_name"] = target_name
    parsed["template_preset"] = str(payload.get("template_preset") or "")
    return parsed


def _comparison_for_fields(mode: str, actual: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    keys = ["show", "season", "episode", "episode_end", "episode_title"] if mode == "tv" else ["movie_title", "year"]
    rows: list[dict[str, Any]] = []
    for key in keys:
        expected_value = expected.get(key)
        if expected_value in (None, ""):
            continue
        actual_value = actual.get(key)
        rows.append(
            {
                "field": key,
                "actual": actual_value,
                "expected": expected_value,
                "ok": str(actual_value or "").casefold() == str(expected_value or "").casefold(),
            }
        )
    expected_name = str(expected.get("expected_name") or "")
    actual_name = str(actual.get("target_name") or "")
    if expected_name:
        rows.append(
            {
                "field": "target_name",
                "actual": actual_name,
                "expected": expected_name,
                "ok": actual_name.casefold() == expected_name.casefold(),
            }
        )
    failed = [row["field"] for row in rows if not row["ok"]]
    return {
        "ok": bool(rows) and not failed,
        "checked_fields": [row["field"] for row in rows],
        "failed_fields": failed,
        "fields": rows,
    }


def _normalized_words(value: object) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+", str(value or ""))
        if token and token.casefold() not in {"s", "e"}
    }


def _source_text(request: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            str(request.get("source_folder") or payload.get("source_folder") or ""),
            str(payload.get("input_name") or request.get("filename") or ""),
        )
        if part
    )


def _default_destination_for_term(term: str, mode: str, *, source_tail: bool) -> tuple[str, str]:
    folded = term.casefold()
    video = {"2160p", "1080p", "1080i", "720p", "720i", "480p", "4k", "uhd", "hdr", "hdr10", "hdr10+", "hlg", "dv", "dovi", "hevc", "h264", "h.264", "h265", "h.265", "x264", "x265", "av1", "avc", "xvid", "divx", "blu ray", "blu-ray", "bluray", "brrip", "bdrip", "webrip", "web dl", "webdl", "hdtv", "hdrip", "dvdrip", "dvd", "dvdscr", "dcprip", "dcp rip", "remux", "hybrid", "10bit", "10 bit", "8bit", "8 bit"}
    audio = {"truehd", "atmos", "flac", "opus", "eac3", "ac3", "aac", "dd", "dd+", "ddp", "dts", "dts hd", "dtsx", "dts-x", "dtshd", "lpcm", "pcm", "mp3", "mp2", "1.0", "2.0", "5.1", "7.1", "stereo", "mono", "6ch", "6 ch", "8ch", "8 ch"}
    language = {"eng", "ita", "fre", "fra", "ger", "deu", "spa", "esp", "jpn", "jap", "kor", "chi", "zho", "rus", "por", "dut", "nld", "swe", "dan", "nor", "fin", "pol", "cze", "ces", "hun", "gre", "ell", "tur", "ara", "hin", "tha", "vie", "ukr", "sub", "subs", "subbed", "dub", "dubs", "dubbed", "multi", "multi audio", "dual audio", "dual-audio"}
    release_flags = {"proper", "repack", "rerip", "uncensored", "censored"}
    if folded in video:
        return ("tv_filter_terms.video_source" if mode == "tv" else "movie_filter_terms.video_source", "video/source tag")
    if folded in audio:
        return ("tv_filter_terms.audio_channels" if mode == "tv" else "movie_filter_terms.audio_channels", "audio/channel tag")
    if folded in language:
        return ("tv_filter_terms.languages_subs_dubs" if mode == "tv" else "movie_filter_terms.languages_subs_dubs", "language/subtitle/dub tag")
    if mode == "tv" and folded in release_flags:
        return ("tv_filter_terms.release_flags", "TV release flag")
    if source_tail or re.fullmatch(r"[A-Z0-9]{2,20}", term):
        return ("tv_filter_terms.release_groups" if mode == "tv" else "movie_filter_terms.release_groups", "release group")
    return ("tv_remove_terms" if mode == "tv" else "remove_terms", "custom negative term")


def _term_present(text: str, term: str) -> bool:
    pattern = re.escape(term.strip()).replace(r"\ ", r"[\s._+-]+")
    return bool(pattern and re.search(rf"(?i)(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])", text))


def _term_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _terms_include_term(values: list[str], term: str) -> bool:
    key = _term_key(term)
    return bool(key) and any(_term_key(value) == key for value in values)


def _split_request_terms(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    return [term.strip() for term in str(value or "").replace(";", ",").replace("\n", ",").split(",") if term.strip()]


def _suggestion_filter_coverage(request: Mapping[str, Any], mode: str, term: str, destination: str) -> tuple[bool, str]:
    if destination == "ignore":
        return False, "ignored"
    if destination == "remove_terms":
        terms = _split_request_terms(request.get("remove_terms")) + _split_request_terms(request.get("remove_terms_text"))
        return (_terms_include_term(terms, term), "already in movie custom negative terms")
    if destination == "tv_remove_terms":
        terms = _split_request_terms(request.get("tv_remove_terms")) + _split_request_terms(request.get("tv_remove_terms_text"))
        return (_terms_include_term(terms, term), "already in TV custom negative terms")

    movie_match = re.fullmatch(r"movie_filter_terms\.(.+)", destination)
    if movie_match:
        category = movie_match.group(1)
        options = normalize_movie_filter_options(dict_bool(request.get("movie_filter_options")))
        if not options.get(category, True):
            return False, "movie filter category is off"
        custom_terms = normalize_movie_filter_terms(dict_terms(request.get("movie_filter_terms"))).get(category, [])
        default_terms = rename_movie_filter_default_terms().get(category, [])
        if _terms_include_term(custom_terms, term):
            return True, f"already in movie {category.replace('_', ' ')} terms"
        if _terms_include_term(default_terms, term):
            return True, f"already covered by movie {category.replace('_', ' ')} defaults"
        return False, "not in active movie filter terms"

    tv_match = re.fullmatch(r"tv_filter_terms\.(.+)", destination)
    if tv_match:
        category = tv_match.group(1)
        options = normalize_tv_filter_options(dict_bool(request.get("tv_filter_options")))
        if not options.get(category, True):
            return False, "TV filter category is off"
        custom_terms = normalize_tv_filter_terms(dict_terms(request.get("tv_filter_terms"))).get(category, [])
        default_terms = rename_tv_filter_default_terms().get(category, [])
        if _terms_include_term(custom_terms, term):
            return True, f"already in TV {category.replace('_', ' ')} terms"
        if _terms_include_term(default_terms, term):
            return True, f"already covered by TV {category.replace('_', ' ')} defaults"
        return False, "not in active TV filter terms"

    return False, "not in active filters"


def _suggestion_destinations_for_mode(mode: str) -> list[str]:
    if mode == "tv":
        return [
            "ignore",
            "tv_remove_terms",
            "tv_filter_terms.video_source",
            "tv_filter_terms.audio_channels",
            "tv_filter_terms.release_flags",
            "tv_filter_terms.services_containers",
            "tv_filter_terms.languages_subs_dubs",
            "tv_filter_terms.release_groups",
        ]
    return [
        "ignore",
        "remove_terms",
        "movie_filter_terms.video_source",
        "movie_filter_terms.audio_channels",
        "movie_filter_terms.editions",
        "movie_filter_terms.file_size",
        "movie_filter_terms.services_containers",
        "movie_filter_terms.languages_subs_dubs",
        "movie_filter_terms.release_groups",
    ]


def _suggest_filter_terms(
    request: Mapping[str, Any],
    payload: Mapping[str, Any],
    expected: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mode = str(payload.get("mode") or "movie")
    source = _source_text(request, payload)
    expected_blob = " ".join(str(value or "") for value in expected.values())
    expected_words = _normalized_words(expected_blob)
    expected_words.update({"mkv", "mp4", "m4v", "mov", "avi", "webm", "ts", "m2ts"})
    candidates: list[tuple[str, bool]] = []
    known_terms = rename_tv_filter_default_terms() if mode == "tv" else rename_movie_filter_default_terms()
    for values in known_terms.values():
        for term in values:
            if _term_present(source, term) and not _term_present(expected_blob, term):
                candidates.append((term, False))
    source_tokens = re.findall(r"[A-Za-z0-9]+(?:\+[A-Za-z0-9]+)?", source)
    for index, token in enumerate(source_tokens):
        folded = token.casefold()
        if folded in expected_words or len(folded) < 2:
            continue
        if re.fullmatch(r"(?:19|20)\d{2}", token) and token == str(expected.get("year") or ""):
            continue
        if re.fullmatch(r"s\d{1,2}e\d{1,3}", token, flags=re.IGNORECASE):
            continue
        candidates.append((token, index >= max(len(source_tokens) - 2, 0)))
    seen: set[str] = set()
    suggestions: list[dict[str, Any]] = []
    for term, source_tail in candidates:
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        destination, reason = _default_destination_for_term(term, mode, source_tail=source_tail)
        already_filtered, coverage_reason = _suggestion_filter_coverage(request, mode, term, destination)
        covered_by_current_result = bool(comparison.get("ok")) and not already_filtered
        stage_recommended = not already_filtered and not covered_by_current_result and destination != "ignore"
        if already_filtered:
            coverage_status = "already_filtered"
        elif covered_by_current_result:
            coverage_status = "already_handled"
            coverage_reason = "current result already matches expected output"
        else:
            coverage_status = "new"
        destinations = _suggestion_destinations_for_mode(mode)
        suggestions.append(
            {
                "term": term,
                "default_destination": destination,
                "destinations": destinations,
                "reason": reason,
                "coverage_status": coverage_status,
                "coverage_reason": coverage_reason,
                "already_filtered": already_filtered or covered_by_current_result,
                "stage_recommended": stage_recommended,
                "source": "source_folder" if term and _term_present(str(request.get("source_folder") or ""), term) else "source_file",
            }
        )
    return suggestions[:24]


def _case_payload_for_preview(request: Mapping[str, Any], payload: Mapping[str, Any], expected: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "movie")
    source_folder = _clean_text(request.get("source_folder") or payload.get("source_folder") or ("Movies" if mode == "movie" else ""))
    source_file = _clean_text(payload.get("input_name") or request.get("filename"))
    case_payload: dict[str, Any] = {
        "kind": "tv_auto" if mode == "tv" else "movie_auto",
        "source_folder": source_folder,
        "source_file": source_file,
        "expected_name": expected.get("expected_name") or "",
        "template_preset": expected.get("template_preset") or payload.get("template_preset") or "",
        "status": "pending",
        "confirm_append": True,
    }
    notes = _clean_text(request.get("notes"))
    if notes:
        case_payload["notes"] = notes
    if mode == "tv":
        case_payload.update(
            {
                "season_number": _parse_int(request.get("season")) or _parse_int(request.get("season_number")) or 1,
                "expected_show": expected.get("show") or "",
            }
        )
        if expected.get("season") is not None:
            case_payload["expected_season"] = expected.get("season")
        if expected.get("episode") is not None:
            case_payload["expected_episode"] = expected.get("episode")
        if expected.get("episode_end") is not None:
            case_payload["expected_episode_end"] = expected.get("episode_end")
        if expected.get("episode_title"):
            case_payload["expected_episode_title"] = expected.get("episode_title")
        tv_filter_options = dict_bool(request.get("tv_filter_options"))
        tv_filter_terms = dict_terms(request.get("tv_filter_terms"))
        tv_remove_terms = remove_terms_from_request(
            request,
            key="tv_remove_terms",
            text_key="tv_remove_terms_text",
            fallback_key="remove_terms",
            fallback_text_key="remove_terms_text",
        )
        source_folder_leaf = re.split(r"[\\/]", source_folder)[-1]
        case_payload["expected_clean_folder"] = clean_pipeline_tv_name_part(
            source_folder_leaf,
            tv_remove_terms or None,
            tv_filter_options or None,
            tv_filter_terms or None,
        )
        if tv_filter_options:
            case_payload["tv_filter_options"] = tv_filter_options
        if tv_filter_terms:
            case_payload["tv_filter_terms"] = tv_filter_terms
        if tv_remove_terms:
            case_payload["tv_remove_terms"] = tv_remove_terms
    else:
        case_payload.update(
            {
                "expected_movie_title": expected.get("movie_title") or "",
                "expected_year": expected.get("year") or "",
            }
        )
        movie_filter_options = dict_bool(request.get("movie_filter_options"))
        movie_filter_terms = dict_terms(request.get("movie_filter_terms"))
        remove_terms = remove_terms_from_request(request)
        if movie_filter_options:
            case_payload["movie_filter_options"] = movie_filter_options
        if movie_filter_terms:
            case_payload["movie_filter_terms"] = movie_filter_terms
        if remove_terms:
            case_payload["remove_terms"] = remove_terms
    return case_payload


def _with_case_analysis(payload: dict[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    has_expected = any(
        _clean_text(request.get(key))
        for key in (
            "expected_name",
            "expected_show",
            "expected_season",
            "expected_episode",
            "expected_episode_end",
            "expected_episode_title",
            "expected_movie_title",
            "expected_year",
        )
    )
    if not (_truthy(request.get("include_case_analysis")) or has_expected):
        return payload
    actual = _actual_fields(payload)
    expected = _expected_fields(request, payload)
    mode = str(payload.get("mode") or "movie")
    payload["actual_fields"] = actual
    payload["expected_fields"] = expected
    comparison = _comparison_for_fields(mode, actual, expected)
    payload["comparison"] = comparison
    payload["filter_suggestions"] = _suggest_filter_terms(request, payload, expected, comparison)
    payload["case_payload"] = _case_payload_for_preview(request, payload, expected)
    return payload


def _rename_filter_evidence(
    *,
    mode: str,
    policy_source: str,
    input_name: str,
    source_folder: str,
    options: Mapping[str, bool],
    terms: Mapping[str, list[str]],
    remove_terms: list[str],
) -> list[dict[str, Any]]:
    enabled = [key for key, value in options.items() if value]
    disabled = [key for key, value in options.items() if not value]
    evidence = [
        {"kind": "mode", "label": "Mode", "value": mode},
        {"kind": "policy", "label": "Policy source", "value": policy_source},
        {
            "kind": "context_guard",
            "label": "Context guard",
            "value": "movie title-before-year tokens are preserved" if mode == "movie" else "TV folder and episode tokens are parsed before release-token filtering",
        },
        {"kind": "custom_remove_terms", "label": "Custom negative terms", "value": len(remove_terms)},
        {"kind": "enabled_categories", "label": "Enabled categories", "value": len(enabled)},
    ]
    if disabled:
        evidence.append({"kind": "disabled_categories", "label": "Disabled categories", "value": ", ".join(disabled)})
    if source_folder:
        evidence.append({"kind": "source_folder", "label": "Source folder", "value": source_folder})
    if input_name:
        evidence.append({"kind": "input_name", "label": "Input filename", "value": input_name})
    for key, values in terms.items():
        evidence.append(
            {
                "kind": "category_terms",
                "category": key,
                "label": key.replace("_", " "),
                "value": len(values or []),
            }
        )
    return evidence


def rename_movie_filter_catalog_payload(config: Mapping[str, Any] | object | None = None) -> dict[str, Any]:
    default_terms = rename_movie_filter_default_terms()
    saved_policy = rename_cleaning_policy_from_config(config)
    saved_terms = dict(saved_policy["movie_filter_terms"])
    saved_remove_terms = list(saved_policy["remove_terms"])
    return {
        "schema_version": "desktop_rename_movie_filter_catalog.v1",
        "ok": True,
        "preview_source": "backend_movie_cleaner",
        "evidence_authority": "backend",
        "movie_filter_terms_enabled": True,
        "movie_filter_terms_mode": "saved",
        "rename_cleaning_policy_source": "saved",
        "default_terms": default_terms,
        "default_terms_text": {key: ", ".join(values) for key, values in default_terms.items()},
        "saved_terms": saved_terms,
        "saved_terms_text": {key: ", ".join(values) for key, values in saved_terms.items()},
        "saved_options": dict(saved_policy["movie_filter_options"]),
        "saved_remove_terms": saved_remove_terms,
        "saved_remove_terms_text": ", ".join(saved_remove_terms),
        "option_keys": list(default_terms.keys()),
        "mutation_boundary": "read-only movie filter catalog; no filesystem paths are opened, renamed, moved, deleted, or written",
    }


def rename_cleaning_filter_catalog_payload(config: Mapping[str, Any] | object | None = None) -> dict[str, Any]:
    saved_policy = rename_cleaning_policy_from_config(config)
    movie_defaults = rename_movie_filter_default_terms()
    tv_defaults = rename_tv_filter_default_terms()
    return {
        "schema_version": "desktop_rename_cleaning_filter_catalog.v1",
        "ok": True,
        "preview_source": "backend_rename_cleaners",
        "evidence_authority": "backend",
        "rename_cleaning_policy_source": "saved",
        "movie": {
            "default_terms": movie_defaults,
            "default_terms_text": {key: ", ".join(values) for key, values in movie_defaults.items()},
            "saved_terms": dict(saved_policy["movie_filter_terms"]),
            "saved_terms_text": {key: ", ".join(values) for key, values in dict(saved_policy["movie_filter_terms"]).items()},
            "saved_options": dict(saved_policy["movie_filter_options"]),
            "saved_remove_terms": list(saved_policy["remove_terms"]),
            "saved_remove_terms_text": ", ".join(saved_policy["remove_terms"]),
            "option_keys": list(movie_defaults.keys()),
        },
        "tv": {
            "default_terms": tv_defaults,
            "default_terms_text": {key: ", ".join(values) for key, values in tv_defaults.items()},
            "saved_terms": dict(saved_policy["tv_filter_terms"]),
            "saved_terms_text": {key: ", ".join(values) for key, values in dict(saved_policy["tv_filter_terms"]).items()},
            "saved_options": dict(saved_policy["tv_filter_options"]),
            "saved_remove_terms": list(saved_policy["tv_remove_terms"]),
            "saved_remove_terms_text": ", ".join(saved_policy["tv_remove_terms"]),
            "option_keys": list(tv_defaults.keys()),
        },
        "mutation_boundary": "read-only rename filter catalog; no filesystem paths are opened, renamed, moved, deleted, or written",
    }


def _optional_strict_bool(request: Mapping[str, Any], key: str, default: bool) -> bool:
    if key not in request or request.get(key) is None:
        return default
    value = request.get(key)
    if isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be a boolean.")


def _strict_bool_map(value: Any, key: str) -> dict[str, bool]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object of boolean values.")
    result: dict[str, bool] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_value, bool):
            raise ValueError(f"{key}.{raw_name} must be a boolean.")
        result[str(raw_name)] = raw_value
    return result


def rename_plan_kwargs_from_request(
    request: Mapping[str, Any],
    *,
    parse_remove_terms: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    mode = str(request.get("mode") or "tv")
    media_mode = mode.strip().casefold()
    remove_terms = remove_terms_from_request(
        request,
        parse_remove_terms,
        key="tv_remove_terms" if media_mode == "tv" else "remove_terms",
        text_key="tv_remove_terms_text" if media_mode == "tv" else "remove_terms_text",
        fallback_key="remove_terms" if media_mode == "tv" else None,
        fallback_text_key="remove_terms_text" if media_mode == "tv" else None,
    )
    return {
        "mode": mode,
        "show_name": str(request.get("show_name") or ""),
        "season_value": request.get("season", request.get("season_value", "S01")),
        "start_episode_value": request.get("start_episode", request.get("start_episode_value", "E01")),
        "movie_title": str(request.get("movie_title") or ""),
        "movie_year": str(request.get("movie_year") or ""),
        "remove_terms": remove_terms,
        "movie_filter_options": dict_bool(request.get("movie_filter_options")),
        "movie_filter_terms": dict_terms(request.get("movie_filter_terms"), parse_remove_terms),
        "tv_filter_options": dict_bool(request.get("tv_filter_options")),
        "tv_filter_terms": dict_terms(request.get("tv_filter_terms"), parse_remove_terms),
        "cleaning_policy": rename_cleaning_policy_from_request(request),
        "final_name_overrides": dict_str(request.get("final_name_overrides")),
        "rename_sidecars": _optional_strict_bool(request, "rename_sidecars", True),
        "force_pipeline_name": _optional_strict_bool(request, "force_pipeline_name", False),
        "force_pipeline_name_overrides": _strict_bool_map(request.get("force_pipeline_name_overrides"), "force_pipeline_name_overrides"),
        "powershell_host": str(request.get("powershell_host") or "") or None,
        "use_pipeline_naming_preview": _optional_strict_bool(request, "use_pipeline_naming_preview", False),
        "template_preset": str(request.get("template_preset") or ""),
    }


__all__ = [
    "rename_filename_leaf",
    "rename_clean_filename_preview_from_request",
    "rename_cleaning_filter_catalog_payload",
    "rename_movie_filter_catalog_payload",
    "rename_plan_kwargs_from_request",
]
