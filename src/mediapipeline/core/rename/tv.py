from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mediapipeline.core.rename.movie import remove_movie_filter_terms
from mediapipeline.core.rename.tv_folder import (
    TV_ORDINAL_WORDS,
    TV_SPECIALS_FOLDER_PATTERN,
    resolve_tv_folder_season_info as resolve_tv_folder_season_info_with_cleaner,
)
from mediapipeline.core.rename.utils import normalize_plex_filename_component, remove_default_priority_markers, strip_known_media_suffix


TV_SEASON_EPISODE_PATTERN = re.compile(r"(?i)\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})(?:[-_]?E(?P<episode_end>\d{1,3}))?\b")
TV_NXM_PATTERN = re.compile(r"(?i)(?<!\d)(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?!\d)")
TV_SEASON_ONLY_PATTERN = re.compile(r"(?i)(?<![A-Za-z0-9])(?:Season|S)[\s._-]*(?P<season>\d{1,2})(?![A-Za-z0-9])")
TV_EXPLICIT_EPISODE_PATTERN = re.compile(r"(?i)(?<![A-Za-z0-9])(?:Episode|Ep|E)[\s._-]*(?P<episode>\d{1,3})(?![A-Za-z0-9])")
TV_RELEASE_TAG_PATTERN = re.compile(
    r"\b(?:2160p|1080p|720p|480p|uhd|hdr10\+?|hdr|dv|dolby[\s._-]*vision|"
    r"hevc|h\.?264|h\.?265|x264|x265|av1|10\s*bit|8\s*bit|bd|bdrip|blu[\s._-]*ray|"
    r"bluray|web[\s._-]*dl|webdl|webrip|web|hdtv|dvd|dvdrip|remux|proper|repack|rerip|"
    r"dual[\s._-]*audio|multi[\s._-]*audio|eng[\s._-]*subs?|multi[\s._-]*subs?|subs?|"
    r"subbed|dubbed|flac|aac|opus|ac3|eac3|ddp\d*|ddp|dts|truehd|atmos|mkv|mp4)\b",
    re.IGNORECASE,
)
TV_AUDIO_CHANNEL_TAG_PATTERN = re.compile(r"\b(?:1\.0|2\.0|5\.1|7\.1|6\s*ch|8\s*ch|6ch|8ch)\b", re.IGNORECASE)
TV_RELEASE_GROUP_SUFFIX_PATTERN = re.compile(
    r"(?i)(?:[\s._-]+(?:chotab|subsplease|erai[\s._-]*raws?|judas|ember|bonkai|neohevc|"
    r"animetime|lostyears|nai|asw|sam|tnp|dedsec|mtbb|smugcat|commie|horriblesubs|"
    r"kametsu|db|kawaiika|tlacatlc6))+$"
)
TV_FORMATTED_TITLE_PATTERN = re.compile(r"(?i)^(?P<prefix>.+\s+-\s+S\d{2}E\d{2,3})(?:\s+-\s+.+)$")


def apply_tv_episode_title_template(file_name: str, *, include_episode_title: bool) -> str:
    if include_episode_title:
        return file_name
    suffix = Path(file_name).suffix
    stem = Path(file_name).stem if suffix else str(file_name)
    match = TV_FORMATTED_TITLE_PATTERN.match(stem)
    if not match:
        return file_name
    return f"{match.group('prefix')}{suffix}"


def build_tv_rename_name(
    source: Path,
    *,
    show_name: str,
    season_number: int,
    episode_number: int,
    remove_terms: list[str] | None,
    include_episode_title: bool = True,
) -> str:
    cleaned_show = normalize_plex_filename_component(show_name, remove_terms)
    if not cleaned_show:
        raise ValueError("Show name is required after invalid characters and remove terms are filtered.")
    episode_title = extract_confident_tv_episode_title(source.stem, remove_terms)
    if not include_episode_title:
        episode_title = ""
    title_part = f" - {episode_title}" if episode_title else ""
    return f"{cleaned_show} - S{season_number:02d}E{episode_number:02d}{title_part}{source.suffix.lower()}"


def clean_pipeline_tv_name_part(value: str, remove_terms: list[str] | None = None) -> str:
    text = remove_default_priority_markers(strip_known_media_suffix(value))
    for _ in range(5):
        before = text
        text = re.sub(r"\[[^\[\]]*\]", " ", text)
        text = re.sub(r"\{[^{}]*\}", " ", text)
        text = re.sub(
            r"(?i)\([^)]*(?:season|specials?|cour|uncensored|censored|2160p|1080p|720p|480p|uhd|hdr|hevc|h264|h265|x264|x265|av1|bd|blu-ray|bluray|web-dl|webdl|webrip|remux|dual\s*audio|multi\s*audio|eng\s*subs?|subs?)[^)]*\)",
            " ",
            text,
        )
        if text == before:
            break
    text = TV_SEASON_EPISODE_PATTERN.sub(" ", text)
    text = TV_NXM_PATTERN.sub(" ", text)
    text = re.sub(r"(?i)\b(?:season|s)\s*\d{1,2}\s*(?:\+\s*specials?)?\b", " ", text)
    text = re.sub(r"(?i)\b(?:specials?|ova|oav|ona|cour)\b", " ", text)
    text = TV_AUDIO_CHANNEL_TAG_PATTERN.sub(" ", text)
    text = TV_RELEASE_TAG_PATTERN.sub(" ", text)
    text = TV_RELEASE_GROUP_SUFFIX_PATTERN.sub(" ", text)
    text = remove_movie_filter_terms(text, remove_terms)
    text = re.sub(r"[\[\]{}()]", " ", text)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"[\._]+", " ", text)
    text = re.sub(r"\s-\s", " ", text)
    text = re.sub(r"\s-|-\s", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .-_")
    return text


def resolve_tv_folder_season_info(source: Path, remove_terms: list[str] | None = None) -> dict[str, Any] | None:
    return resolve_tv_folder_season_info_with_cleaner(source, remove_terms, clean_name=clean_pipeline_tv_name_part)


def extract_confident_tv_episode_title(stem: str, remove_terms: list[str] | None = None) -> str:
    text = strip_known_media_suffix(stem)
    title_fragment = ""
    for pattern in (TV_SEASON_EPISODE_PATTERN, TV_NXM_PATTERN, TV_EXPLICIT_EPISODE_PATTERN):
        match = pattern.search(text)
        if not match:
            continue
        after = text[match.end() :].strip(" ._-")
        if not after:
            continue
        hyphen_match = re.match(r"^\s*[-–]\s*(.+)$", after)
        title_fragment = hyphen_match.group(1) if hyphen_match else after
        break
    if not title_fragment:
        return ""
    source_tag = TV_RELEASE_TAG_PATTERN.search(title_fragment)
    if source_tag:
        title_fragment = title_fragment[: source_tag.start()]
    title_fragment = re.sub(r"(?i)\b(?:v\d+|proper|repack|rerip)\b.*$", " ", title_fragment)
    title = clean_pipeline_tv_name_part(title_fragment, remove_terms)
    if not title or len(title) > 80:
        return ""
    if re.fullmatch(r"(?i)(?:e?\d{1,3}|v\d+|audio|subs?|subtitles?|dubbed|subbed|english|japanese|bd|hevc|x264|x265)(?:\s+.*)?", title):
        return ""
    return title


def build_auto_tv_rename_name(
    source: Path,
    *,
    season_number: int,
    remove_terms: list[str] | None,
    include_episode_title: bool = True,
) -> str:
    stem = source.stem
    season = 0
    episode = 0
    show_fragment = ""
    folder_info = resolve_tv_folder_season_info(source, remove_terms)
    marker_match = TV_SEASON_EPISODE_PATTERN.search(stem)
    if marker_match:
        season = int(marker_match.group("season"))
        episode = int(marker_match.group("episode"))
        show_fragment = stem[: marker_match.start()]
    else:
        marker_match = TV_NXM_PATTERN.search(stem)
        if marker_match:
            season = int(marker_match.group("season"))
            episode = int(marker_match.group("episode"))
            show_fragment = stem[: marker_match.start()]
        else:
            season_match = TV_SEASON_ONLY_PATTERN.search(stem)
            episode_match = TV_EXPLICIT_EPISODE_PATTERN.search(stem)
            if season_match and episode_match:
                season = int(season_match.group("season"))
                episode = int(episode_match.group("episode"))
                show_fragment = stem[: season_match.start()]
            elif episode_match:
                if folder_info is not None:
                    season = int(folder_info["season"])
                else:
                    season = season_number if season_number >= 0 else 1
                episode = int(episode_match.group("episode"))
                show_fragment = stem[: episode_match.start()]

    if season <= 0 or episode <= 0:
        if season == 0 and episode > 0:
            pass
        else:
            raise ValueError("TV auto preview needs SxxEyy, NxM, Episode N, Ep N, or E01 in the filename, or a Show name in the TV fields.")
    show = clean_pipeline_tv_name_part(show_fragment, remove_terms)
    if not show and folder_info is not None:
        show = str(folder_info.get("show") or "")
    if not show:
        show = clean_pipeline_tv_name_part(source.parent.name, remove_terms)
    if not show:
        raise ValueError("TV auto preview could not infer a show name before the episode token.")
    episode_title = extract_confident_tv_episode_title(stem, remove_terms)
    if not include_episode_title:
        episode_title = ""
    title_part = f" - {episode_title}" if episode_title else ""
    return f"{show} - S{season:02d}E{episode:02d}{title_part}{source.suffix.lower()}"
