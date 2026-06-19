"""Read-only rename filename preview and filter catalog payloads."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES
from mediapipeline.core.rename.cleaning_policy import (
    RENAME_MOVIE_FILTER_POLICY_SOURCE_KEY,
    dict_bool,
    dict_str,
    dict_terms,
    remove_terms_from_request,
    rename_cleaning_policy_from_config,
)
from mediapipeline.core.rename.movie import rename_movie_filter_default_terms
from mediapipeline.core.rename.tv import rename_tv_filter_default_terms


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
            parse_remove_terms=parse_remove_terms,
            build_auto_tv_name=build_auto_tv_name,
        )
    remove_terms = remove_terms_from_request(request, parse_remove_terms)
    movie_filter_options = dict_bool(request.get("movie_filter_options"))
    movie_filter_terms = dict_terms(request.get("movie_filter_terms"), parse_remove_terms)
    try:
        cleaned_title = clean_movie_name(cleaner_input, remove_terms, movie_filter_options, movie_filter_terms)
    except Exception as exc:
        return {
            "schema_version": "desktop_rename_clean_filename_preview.v1",
            "ok": False,
            "input": raw_input,
            "input_name": input_name,
            "cleaned_title": "",
            "target_name": "",
            "mode": mode,
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

    target_name = f"{cleaned_title}{suffix}" if cleaned_title and has_media_suffix else cleaned_title
    if not has_media_suffix:
        warnings.append("No known media extension was supplied; the cleaner assumed .mkv internally and returned a title-only preview.")
    return {
        "schema_version": "desktop_rename_clean_filename_preview.v1",
        "ok": bool(cleaned_title),
        "input": raw_input,
        "input_name": input_name,
        "cleaned_title": cleaned_title,
        "target_name": target_name,
        "mode": mode,
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
        )
    except Exception as exc:
        return {
            "schema_version": "desktop_rename_clean_filename_preview.v1",
            "ok": False,
            "input": raw_input,
            "input_name": input_name,
            "cleaned_title": "",
            "target_name": "",
            "mode": "tv",
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
    if not has_media_suffix:
        warnings.append("No known media extension was supplied; the cleaner assumed .mkv internally and returned a filename preview.")
    cleaned_title = Path(target_name).stem
    return {
        "schema_version": "desktop_rename_clean_filename_preview.v1",
        "ok": bool(target_name),
        "input": raw_input,
        "input_name": input_name,
        "cleaned_title": cleaned_title,
        "target_name": target_name if has_media_suffix else cleaned_title,
        "mode": "tv",
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
