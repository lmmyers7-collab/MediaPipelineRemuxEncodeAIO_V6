"""Status label and state text helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mediapipeline.core.rename.movie import clean_pipeline_movie_name
from mediapipeline.core.rename.tv import clean_pipeline_tv_name_part, extract_confident_tv_episode_title


def _movie_cleaning_policy_value(policy: Mapping[str, Any] | None, key: str, expected_type: type) -> Any:
    if not isinstance(policy, Mapping):
        return None
    value = policy.get(key)
    return value if isinstance(value, expected_type) else None


def _clean_movie_progress_label(file_name: str, movie_cleaning_policy: Mapping[str, Any] | None = None) -> str:
    return clean_pipeline_movie_name(
        file_name,
        _movie_cleaning_policy_value(movie_cleaning_policy, "remove_terms", list),
        _movie_cleaning_policy_value(movie_cleaning_policy, "movie_filter_options", dict),
        _movie_cleaning_policy_value(movie_cleaning_policy, "movie_filter_terms", dict),
    )


def _progress_text(progress: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = progress.get(key)
        if value not in (None, ""):
            text = str(value).strip()
            if text and text.casefold() != "none":
                return text
    return ""


def display_library_relative_path(path_text: str, media_type: str) -> str:
    parts = [segment for segment in re.split(r"[\\/]+", path_text or "") if segment]
    if not parts:
        return ""
    lower_parts = [part.casefold() for part in parts]
    marker = media_type if media_type in {"movie", "tv"} else ""
    if marker and marker in lower_parts:
        index = lower_parts.index(marker)
        remainder = parts[index + 1 :]
        if remainder:
            return "\\".join(remainder)
    if "movies" in lower_parts:
        index = lower_parts.index("movies")
        remainder = parts[index + 1 :]
        if remainder:
            return "\\".join(remainder)
    if "tv" in lower_parts:
        index = lower_parts.index("tv")
        remainder = parts[index + 1 :]
        if remainder:
            return "\\".join(remainder)
    return ""


def _strip_progress_name_prefixes(value: str) -> str:
    text = (value or "").strip()
    for _ in range(3):
        before = text
        match = re.match(r"^\[[^\]]+\]\s*(?P<name>.+)$", text)
        if match:
            text = match.group("name").strip()
        text = re.sub(r"(?i)^slot\s+\d+\s*:\s*", "", text).strip()
        if text == before:
            break
    return text


def _path_leaf(value: str) -> str:
    text = _strip_progress_name_prefixes(value)
    if not text:
        return ""
    return re.split(r"[\\/]+", text)[-1] or text


def _candidate_current_leaf(progress: dict[str, Any]) -> str:
    for key in (
        "CurrentDisplayName",
        "CleanDisplayName",
        "CleanedName",
        "CurrentFileDisplay",
        "CurrentFilePath",
        "CurrentFile",
        "InputFile",
        "SourceFile",
        "SourcePath",
        "InputPath",
        "OutputPath",
    ):
        leaf = _path_leaf(str(progress.get(key) or ""))
        if leaf:
            return leaf
    return ""


def _strip_release_group_suffix(file_name: str) -> str:
    leaf = _path_leaf(file_name)
    if not leaf:
        return ""
    suffix = Path(leaf).suffix
    stem = Path(leaf).stem if suffix else leaf
    has_release_tags = re.search(
        r"(?i)\b(?:480p|720p|1080p|2160p|4k|web[- ]?rip|web[- ]?dl|bluray|brrip|hdrip|dvdrip|x264|x265|h\.?264|h\.?265|hevc|ddp?5|aac|dts)\b",
        stem,
    )
    if has_release_tags:
        stem = re.sub(r"(?i)-[a-z0-9][a-z0-9._-]{1,}$", "", stem).strip()
    return f"{stem}{suffix}" if suffix else stem


def _progress_media_type(progress: dict[str, Any]) -> str:
    for key in ("CurrentMediaType", "CurrentLibraryDesignation", "CurrentQueuePhase"):
        value = str(progress.get(key) or "").strip().casefold()
        if value in {"movie", "movies"}:
            return "movie"
        if value in {"tv", "episode", "episodes", "show", "shows"}:
            return "tv"
    return ""


def _display_word(value: str) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ").strip()
    if not text:
        return ""
    tokens = []
    for token in text.split():
        upper = token.upper()
        if upper in {"CPU", "GPU", "AV", "TV", "SRT", "HDR"}:
            tokens.append(upper)
        else:
            tokens.append(token[:1].upper() + token[1:].lower())
    return " ".join(tokens)


def _tv_show_from_path(path_text: str) -> str:
    parts = [segment for segment in re.split(r"[\\/]+", path_text or "") if segment]
    if not parts:
        return ""
    lower_parts = [part.casefold() for part in parts]
    if "tv" in lower_parts:
        index = lower_parts.index("tv")
        if index + 1 < len(parts):
            return clean_pipeline_tv_name_part(parts[index + 1])
    if len(parts) >= 3 and re.match(r"(?i)^season\s+\d+$", parts[-2]):
        return clean_pipeline_tv_name_part(parts[-3])
    if len(parts) >= 2:
        return clean_pipeline_tv_name_part(parts[-2])
    return ""


def _clean_tv_item_label(leaf: str, path_text: str) -> str:
    cleaned_leaf = _strip_release_group_suffix(leaf)
    stem = Path(cleaned_leaf).stem if cleaned_leaf else ""
    token = re.search(r"(?i)\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})\b", stem)
    if token:
        show_fragment = stem[: token.start()]
        show = clean_pipeline_tv_name_part(show_fragment) or _tv_show_from_path(path_text)
        season = int(token.group("season"))
        episode = int(token.group("episode"))
        episode_code = f"S{season:02d}E{episode:02d}"
        title = extract_confident_tv_episode_title(stem)
        return " - ".join(part for part in (show, episode_code, title) if part)
    return clean_pipeline_tv_name_part(stem) or stem


def current_work_item_label(progress: dict[str, Any], movie_cleaning_policy: Mapping[str, Any] | None = None) -> str:
    leaf = _candidate_current_leaf(progress)
    if not leaf:
        return ""
    media_type = _progress_media_type(progress)
    path_text = _progress_text(progress, "CurrentFilePath", "CurrentFile", "SourcePath", "InputPath")
    if media_type == "movie":
        return _clean_movie_progress_label(_strip_release_group_suffix(leaf), movie_cleaning_policy) or Path(leaf).stem
    if media_type == "tv":
        return _clean_tv_item_label(leaf, path_text) or Path(leaf).stem
    cleaned = _strip_progress_name_prefixes(Path(leaf).stem)
    return cleaned or Path(leaf).stem


def current_work_phase_label(progress: dict[str, Any]) -> str:
    stage = _progress_text(progress, "CurrentStage").casefold()
    status = _progress_text(progress, "Status").casefold()
    if stage in {"copy_to_scratch", "copy"}:
        return "Copying to scratch"
    if stage in {"remux_prepare", "remux_mux", "remux_verify", "remux_av", "remux-mkvmerge", "remux"}:
        return "Remuxing"
    if stage in {"encode_prepare", "encode", "encode_cpu", "encode_verify"}:
        return "Encoding"
    if stage == "push":
        return "Publishing output"
    if stage == "retry_pending_push":
        return "Publishing parked outputs"
    if stage == "sidecar":
        return "Writing sidecars"
    if stage == "scanning":
        return "Scanning"
    if stage == "startup":
        return "Initializing"
    if stage in {"paused", "stopped", "completed"}:
        return _display_word(stage)
    if stage in {"idle", "sleeping"}:
        return "Idle"
    if status in {"processing", "running", "active"}:
        route = _progress_text(progress, "CurrentRoute", "Route").casefold()
        if route.startswith("remux"):
            return "Remuxing"
        if route.startswith("encode"):
            return "Encoding"
        return "Processing"
    return _display_word(stage or status) or "No active work"


def current_work_library_label(progress: dict[str, Any]) -> str:
    library = _progress_text(progress, "CurrentLibraryName", "CurrentLibraryProfileName", "LibraryName", "library_name")
    if library:
        return library
    media_type = _progress_media_type(progress)
    if media_type == "movie":
        return "Movies"
    if media_type == "tv":
        return "TV"
    designation = _progress_text(progress, "CurrentLibraryDesignation", "LibraryDesignation", "library_designation")
    return _display_word(designation)


def current_work_queue_label(progress: dict[str, Any]) -> str:
    phase = _progress_text(progress, "CurrentQueuePhase").casefold()
    if phase == "priority":
        return "Priority"
    if phase == "pending_push":
        return "Pending publish"
    media_type = _progress_media_type(progress)
    if media_type == "movie":
        return "Movies"
    if media_type == "tv":
        return "TV"
    return _display_word(phase)


def current_work_queue_position_label(progress: dict[str, Any]) -> str:
    try:
        index = int(progress.get("CurrentQueueIndex") or 0)
        total = int(progress.get("CurrentQueueTotal") or 0)
    except (TypeError, ValueError):
        return ""
    if index > 0 and total > 0:
        return f"item {index} of {total}"
    return ""


def current_work_route_label(progress: dict[str, Any]) -> str:
    route = _progress_text(progress, "CurrentRoute", "Route")
    if not route:
        return ""
    return f"{_display_word(route)} route"


def current_work_percent_label(progress: dict[str, Any]) -> str:
    value = progress.get("CurrentStagePercent")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    bounded = max(0.0, min(100.0, number))
    if bounded.is_integer():
        return f"{int(bounded)}%"
    return f"{bounded:.1f}%"


def structured_status_from_progress(progress: dict[str, Any]) -> str:
    stage = str(progress.get("CurrentStage", "") or "").strip().lower()
    route = str(progress.get("CurrentRoute", "") or "").strip().lower()
    copy_state = str(progress.get("CopyState", "") or "").strip().lower()
    push_state = str(progress.get("PushState", "") or "").strip().lower()
    sidecar_state = str(progress.get("SidecarState", "") or "").strip().lower()
    percent_raw = progress.get("CurrentStagePercent")
    percent_text = ""
    try:
        if percent_raw not in ("", None):
            percent_text = f"{int(float(percent_raw))}%"
    except (TypeError, ValueError):
        percent_text = ""

    # encode_cpu gets its own label so the live status tile makes a
    # multi-hour libx265 fallback obvious instead of looking the same
    # as a fast NVENC encode.
    if stage == "encode_cpu":
        return f"encode (CPU) {percent_text}".strip()
    if stage == "encode":
        return f"encode {percent_text}".strip()
    if stage == "remux_av":
        return f"remux {percent_text}".strip()
    if stage == "copy_to_scratch":
        if copy_state == "complete":
            return "copy to scratch complete"
        return "copy to scratch"
    if stage == "remux_prepare":
        return "remux preparation"
    if stage == "remux_mux":
        return "remux mux"
    if stage == "remux_verify":
        return "remux verify"
    if stage == "encode_prepare":
        return "encode preparation"
    if stage == "encode_verify":
        return "encode verify"
    if stage == "push":
        if push_state == "failed":
            return "server push failed"
        if push_state == "deferred":
            return "parked until output space is available"
        if push_state == "complete":
            return "server push complete"
        return "server push"
    if stage == "sidecar":
        if sidecar_state == "failed":
            return "sidecar write failed"
        if sidecar_state == "complete":
            return "sidecar complete"
        return "sidecar write"
    if stage == "retry_pending_push":
        return "publishing parked outputs"
    if stage == "scanning":
        return "scanning sources"
    if stage == "sleeping":
        return "idle / sleeping until next scan"
    if stage == "paused":
        return "paused"
    if stage == "stopped":
        return "stopped"
    if stage == "idle":
        return "idle / waiting for next item"
    if stage == "startup":
        return "initializing"
    if stage == "completed":
        if route:
            return f"{route} complete"
        return "completed"
    return ""


__all__ = [
    "display_library_relative_path",
    "current_work_item_label",
    "current_work_phase_label",
    "current_work_library_label",
    "current_work_queue_label",
    "current_work_queue_position_label",
    "current_work_route_label",
    "current_work_percent_label",
    "structured_status_from_progress",
]
