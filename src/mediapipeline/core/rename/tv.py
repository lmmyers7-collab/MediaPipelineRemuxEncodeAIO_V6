from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mediapipeline.core.rename.constants import RENAME_TV_FILTER_OPTION_KEYS
from mediapipeline.core.rename.movie import movie_filter_term_pattern, remove_movie_filter_terms
from mediapipeline.core.rename.tv_folder import (
    resolve_tv_folder_season_info as resolve_tv_folder_season_info_with_cleaner,
)
from mediapipeline.core.rename.utils import normalize_plex_filename_component, remove_default_priority_markers, strip_known_media_suffix


TV_SEASON_EPISODE_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])S(?P<season>\d{1,2})E(?P<episode>\d{1,4})"
    r"(?:(?:E|-E|_E)(?P<episode_end>\d{1,4}))?(?P<revision>v\d+)?(?![A-Za-z0-9])"
)
TV_NXM_PATTERN = re.compile(r"(?i)(?<!\d)(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?!\d)")
TV_SEASON_ONLY_PATTERN = re.compile(r"(?i)(?<![A-Za-z0-9])(?:Season|S)[\s._-]*(?P<season>\d{1,2})(?![A-Za-z0-9])")
TV_EXPLICIT_EPISODE_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:Episode|Ep|E)[\s._-]*(?P<episode>\d{1,4})(?P<revision>v\d+)?(?![A-Za-z0-9])"
)
TV_BARE_ANIME_EPISODE_PATTERN = re.compile(
    r"(?i)(?<=\s-\s)(?P<episode>\d{1,3})(?P<revision>v\d+)?(?=\s*(?:\(|\[|$|\s-\s))"
)
TV_STRUCTURED_RELEASE_TAIL_PATTERN = re.compile(
    r"(?i)[\s._-]+(?:2160p|1080p|720p|480p|uhd|hdr10\+?|hdr|dv|dolby[\s._-]*vision|"
    r"hevc|h\.?264|h\.?265|x264|x265|av1|10[\s._-]*bit|8[\s._-]*bit|bd|bdrip|"
    r"blu[\s._-]*ray|bluray|web[\s._-]*dl|webdl|webrip|hdtv|dvd|dvdrip|remux|"
    r"dual[\s._-]*audio|multi[\s._-]*audio|eng[\s._-]*subs?|multi[\s._-]*subs?|"
    r"subbed|dubbed|flac|aac|opus|ac3|eac3|ddp\d*|ddp|dts|truehd|atmos|"
    r"1\.0|2\.0|5\.1|7\.1|6[\s._-]*ch|8[\s._-]*ch|mkv|mp4)"
    r"(?:[\s._-]+(?:2160p|1080p|720p|480p|uhd|hdr10\+?|hdr|dv|dolby[\s._-]*vision|"
    r"hevc|h\.?264|h\.?265|x264|x265|av1|10[\s._-]*bit|8[\s._-]*bit|bd|bdrip|"
    r"blu[\s._-]*ray|bluray|web[\s._-]*dl|webdl|webrip|hdtv|dvd|dvdrip|remux|"
    r"dual[\s._-]*audio|multi[\s._-]*audio|eng[\s._-]*subs?|multi[\s._-]*subs?|"
    r"subbed|dubbed|flac|aac|opus|ac3|eac3|ddp\d*|ddp|dts|truehd|atmos|"
    r"1\.0|2\.0|5\.1|7\.1|6[\s._-]*ch|8[\s._-]*ch|mkv|mp4))*\s*$"
)
TV_AUDIO_CHANNEL_TAG_PATTERN = re.compile(r"\b(?:1\.0|2\.0|5\.1|7\.1|6\s*ch|8\s*ch|6ch|8ch)\b", re.IGNORECASE)
TV_RELEASE_GROUP_SUFFIX_PATTERN = re.compile(
    r"(?i)(?:[\s._-]+(?:chotab|subsplease|erai[\s._-]*raws?|judas|ember|bonkai|neohevc|"
    r"animetime|lostyears|nai|asw|sam|tnp|dedsec|mtbb|smugcat|commie|horriblesubs|"
    r"kametsu|db|kawaiika|tlacatlc6|ttga))+$"
)
TV_FORMATTED_TITLE_PATTERN = re.compile(r"(?i)^(?P<prefix>.+\s+-\s+S\d{2}E\d{2,3}(?:-E\d{2,3})?)(?:\s+-\s+.+)$")
TV_TARGET_NAME_PATTERN = re.compile(
    r"(?i)^(?P<show>.+?)\s+-\s+S(?P<season>\d{2})E(?P<episode>\d{2,3})"
    r"(?:-E(?P<episode_end>\d{2,3}))?(?:\s+-\s+(?P<episode_title>.*))?$"
)
TV_ORDINAL_SEASON_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?P<ordinal>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d{1,2}(?:st|nd|rd|th))\s+(?:season|cour)(?![A-Za-z0-9])"
)
TV_SPECIAL_MARKER_PATTERN = re.compile(r"(?i)(?<![A-Za-z0-9])(?P<kind>OVA|OAV|ONA|Specials?)(?![A-Za-z0-9])")
TV_NONCANONICAL_RANGE_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:Episode|Ep)[\s._-]*\d{1,3}\s*-\s*(?:(?:Episode|Ep)[\s._-]*)?\d{1,3}(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])\d{1,3}\s*-\s*\d{1,3}(?![A-Za-z0-9])"
)
TV_MALFORMED_SXX_RANGE_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])S\d{1,2}E\d{1,4}[-_]\d{1,4}(?![A-Za-z0-9])"
)
TV_ORDINAL_VALUES = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
RENAME_TV_FILTER_DEFAULT_TERMS: dict[str, tuple[str, ...]] = {
    "video_source": (
        "2160p",
        "1080p",
        "720p",
        "480p",
        "uhd",
        "hdr",
        "hdr10",
        "dv",
        "dolby vision",
        "hevc",
        "h264",
        "h.264",
        "h265",
        "h.265",
        "x264",
        "x265",
        "av1",
        "bd",
        "bdrip",
        "blu ray",
        "blu-ray",
        "bluray",
        "web dl",
        "webdl",
        "webrip",
        "hdtv",
        "dvd",
        "dvdrip",
        "remux",
        "10 bit",
        "8 bit",
    ),
    "audio_channels": (
        "flac",
        "aac",
        "opus",
        "ac3",
        "eac3",
        "ddp",
        "dts",
        "truehd",
        "atmos",
        "1.0",
        "2.0",
        "5.1",
        "7.1",
        "6ch",
        "6 ch",
        "8ch",
        "8 ch",
    ),
    "release_flags": ("proper", "repack", "rerip", "uncensored", "censored"),
    "services_containers": ("mkv", "mp4"),
    "languages_subs_dubs": (
        "dual audio",
        "multi audio",
        "eng sub",
        "eng subs",
        "multi sub",
        "multi subs",
        "subs",
        "sub",
        "subbed",
        "dubbed",
    ),
    "release_groups": (
        "chotab",
        "subsplease",
        "erai raws",
        "erai-raws",
        "judas",
        "ember",
        "bonkai",
        "neohevc",
        "animetime",
        "lostyears",
        "nai",
        "asw",
        "sam",
        "tnp",
        "dedsec",
        "mtbb",
        "smugcat",
        "commie",
        "horriblesubs",
        "kametsu",
        "db",
        "kawaiika",
        "tlacatlc6",
        "ttga",
    ),
}


def normalize_tv_filter_options(tv_filter_options: dict[str, bool] | None = None) -> dict[str, bool]:
    options = dict.fromkeys(RENAME_TV_FILTER_OPTION_KEYS, True)
    for key, value in (tv_filter_options or {}).items():
        if key in options:
            options[key] = bool(value)
    return options


def normalize_tv_filter_terms(tv_filter_terms: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, values in (tv_filter_terms or {}).items():
        if key not in RENAME_TV_FILTER_OPTION_KEYS:
            continue
        seen: set[str] = set()
        terms: list[str] = []
        for value in values or []:
            term = str(value or "").strip()
            folded = term.casefold()
            if not term or folded in seen:
                continue
            seen.add(folded)
            terms.append(term)
        if terms:
            normalized[key] = terms
    return normalized


def rename_tv_filter_default_terms() -> dict[str, list[str]]:
    return {key: list(values) for key, values in RENAME_TV_FILTER_DEFAULT_TERMS.items()}


def find_tv_episode_token(stem: str) -> tuple[str, re.Match[str]] | None:
    for kind, pattern in (
        ("season_episode", TV_SEASON_EPISODE_PATTERN),
        ("nxm", TV_NXM_PATTERN),
        ("explicit", TV_EXPLICIT_EPISODE_PATTERN),
        ("bare_anime", TV_BARE_ANIME_EPISODE_PATTERN),
    ):
        match = pattern.search(stem)
        if match:
            return kind, match
    return None


def collective_tv_filter_terms(tv_filter_terms: dict[str, list[str]] | None, key: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for term in list(RENAME_TV_FILTER_DEFAULT_TERMS.get(key, ())) + list(normalize_tv_filter_terms(tv_filter_terms).get(key, [])):
        folded = str(term or "").casefold()
        if not folded or folded in seen:
            continue
        seen.add(folded)
        terms.append(str(term))
    return terms


def strip_tv_release_groups(text: str, tv_filter_options: dict[str, bool] | None = None, tv_filter_terms: dict[str, list[str]] | None = None) -> str:
    if not normalize_tv_filter_options(tv_filter_options).get("release_groups", True):
        return str(text or "")
    result = TV_RELEASE_GROUP_SUFFIX_PATTERN.sub(" ", str(text or ""))
    for term in collective_tv_filter_terms(tv_filter_terms, "release_groups"):
        pattern = movie_filter_term_pattern(term, bounded=False)
        if not pattern:
            continue
        result = re.sub(rf"(?i)[\s._-]+[\[\(]?\s*{pattern}\s*[\]\)]?\s*$", " ", result)
    return result


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
    tv_filter_options: dict[str, bool] | None = None,
    tv_filter_terms: dict[str, list[str]] | None = None,
    include_episode_title: bool = True,
) -> str:
    cleaned_show = normalize_plex_filename_component(show_name, remove_terms)
    if not cleaned_show:
        raise ValueError("Show name is required after invalid characters and remove terms are filtered.")
    episode_title = extract_confident_tv_episode_title(source.stem, remove_terms, tv_filter_options, tv_filter_terms)
    if not include_episode_title:
        episode_title = ""
    title_part = f" - {episode_title}" if episode_title else ""
    return f"{cleaned_show} - S{season_number:02d}E{episode_number:02d}{title_part}{source.suffix.lower()}"


def _parent_or_self(path: Path) -> Path:
    return path.parent if path.parent != path else path


def _title_tokens(value: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", value) if len(token) > 2}


def _titles_overlap(left: str, right: str) -> bool:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    shared = left_tokens.intersection(right_tokens)
    return len(shared) >= min(2, len(left_tokens), len(right_tokens))


def _manual_tv_hierarchy_root(
    source: Path,
    *,
    show_folder_name: str,
    remove_terms: list[str] | None,
    tv_filter_options: dict[str, bool] | None,
    tv_filter_terms: dict[str, list[str]] | None,
) -> Path:
    folder_info = resolve_tv_folder_season_info(source, remove_terms, tv_filter_options, tv_filter_terms)
    if folder_info is not None:
        source_kind = str(folder_info.get("source") or "")
        if source_kind in {"season-folder", "s-folder", "specials-folder"}:
            show_folder = _parent_or_self(source.parent)
            return _parent_or_self(show_folder)
        return _parent_or_self(source.parent)

    parent_show = clean_pipeline_tv_name_part(
        source.parent.name,
        remove_terms,
        tv_filter_options,
        tv_filter_terms,
        preserve_title_terms=True,
    )
    if parent_show.casefold() == show_folder_name.casefold() or _titles_overlap(parent_show, show_folder_name):
        return _parent_or_self(source.parent)
    return source.parent


def build_manual_tv_hierarchy_destination(
    source: Path,
    *,
    target_name: str,
    show_name: str,
    season_number: int,
    remove_terms: list[str] | None,
    tv_filter_options: dict[str, bool] | None = None,
    tv_filter_terms: dict[str, list[str]] | None = None,
) -> dict[str, Any] | None:
    show_folder_name = normalize_plex_filename_component(show_name, remove_terms)
    if not show_folder_name:
        return None

    target_match = TV_TARGET_NAME_PATTERN.match(Path(target_name).stem)
    target_season = int(target_match.group("season")) if target_match else season_number
    season_folder_name = "Specials" if target_season == 0 else f"Season {target_season:02d}"
    mutation_root = _manual_tv_hierarchy_root(
        source,
        show_folder_name=show_folder_name,
        remove_terms=remove_terms,
        tv_filter_options=tv_filter_options,
        tv_filter_terms=tv_filter_terms,
    )
    series_folder = mutation_root / show_folder_name
    season_folder = series_folder / season_folder_name
    destination = season_folder / target_name
    return {
        "destination": destination,
        "mutation_root": mutation_root,
        "series_folder": series_folder,
        "season_folder": season_folder,
        "season_folder_name": season_folder_name,
        "show_folder_name": show_folder_name,
    }


def clean_pipeline_tv_name_part(
    value: str,
    remove_terms: list[str] | None = None,
    tv_filter_options: dict[str, bool] | None = None,
    tv_filter_terms: dict[str, list[str]] | None = None,
    *,
    preserve_title_terms: bool = False,
) -> str:
    filter_options = normalize_tv_filter_options(tv_filter_options)
    filter_terms = normalize_tv_filter_terms(tv_filter_terms)
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
    text = re.sub(r"(?i)\b(?:season|s)\s*\d{1,2}\s*(?:\+\s*(?:sp|specials?))?\b", " ", text)
    text = re.sub(r"(?i)\b(?:specials?|ova|oav|ona|cour)\b", " ", text)
    if preserve_title_terms:
        for category in RENAME_TV_FILTER_OPTION_KEYS:
            if filter_options.get(category, True):
                text = remove_movie_filter_terms(text, filter_terms.get(category, []))
        text = strip_tv_release_groups(text, filter_options, filter_terms)
    else:
        for category in ("video_source", "audio_channels", "release_flags", "services_containers", "languages_subs_dubs"):
            if filter_options.get(category, True):
                text = remove_movie_filter_terms(text, collective_tv_filter_terms(filter_terms, category))
        if filter_options.get("audio_channels", True):
            text = TV_AUDIO_CHANNEL_TAG_PATTERN.sub(" ", text)
        text = strip_tv_release_groups(text, filter_options, filter_terms)
    text = remove_movie_filter_terms(text, remove_terms)
    text = re.sub(r"[\[\]{}()]", " ", text)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"[\._]+", " ", text)
    text = re.sub(r"\s-\s", " ", text)
    text = re.sub(r"\s-|-\s", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .-_")
    return text


def resolve_tv_folder_season_info(
    source: Path,
    remove_terms: list[str] | None = None,
    tv_filter_options: dict[str, bool] | None = None,
    tv_filter_terms: dict[str, list[str]] | None = None,
) -> dict[str, Any] | None:
    def clean_show_name(value: str, terms: list[str] | None) -> str:
        return clean_pipeline_tv_name_part(
            value,
            terms,
            tv_filter_options,
            tv_filter_terms,
            preserve_title_terms=True,
        )

    return resolve_tv_folder_season_info_with_cleaner(source, remove_terms, clean_name=clean_show_name)


def extract_confident_tv_episode_title(
    stem: str,
    remove_terms: list[str] | None = None,
    tv_filter_options: dict[str, bool] | None = None,
    tv_filter_terms: dict[str, list[str]] | None = None,
) -> str:
    text = strip_known_media_suffix(stem)
    token = find_tv_episode_token(text)
    if token is None:
        return ""
    _, match = token
    after = text[match.end() :].strip(" ._-")
    if not after:
        return ""
    hyphen_match = re.match(r"^\s*[-–]\s*(.+)$", after)
    title_fragment = hyphen_match.group(1) if hyphen_match else after
    if not title_fragment:
        return ""
    title_fragment = strip_tv_release_groups(title_fragment, tv_filter_options, tv_filter_terms)
    title_fragment = TV_STRUCTURED_RELEASE_TAIL_PATTERN.sub(" ", title_fragment)
    title_fragment = re.sub(r"(?i)[\s._-]+(?:v\d+|proper|repack|rerip)\s*$", " ", title_fragment)
    title = clean_pipeline_tv_name_part(
        title_fragment,
        remove_terms,
        tv_filter_options,
        tv_filter_terms,
        preserve_title_terms=True,
    )
    if not title or len(title) > 80:
        return ""
    if re.fullmatch(r"\d+", title):
        return ""
    if re.fullmatch(r"(?i)(?:v\d+|audio|subs?|subtitles?|dubbed|subbed|english|japanese|bd|hevc|x264|x265)", title):
        return ""
    return title


def _tv_identity_error(message: str, *, parse_mode: str = "invalid") -> dict[str, Any]:
    return {
        "show": "",
        "season": 0,
        "episode_start": 0,
        "episode_end": None,
        "episode_title": "",
        "revision": "",
        "parse_mode": parse_mode,
        "reliable": False,
        "parse_error": message,
    }


def _ordinal_season_number(match: re.Match[str] | None) -> int | None:
    if match is None:
        return None
    value = match.group("ordinal").casefold()
    if value in TV_ORDINAL_VALUES:
        return TV_ORDINAL_VALUES[value]
    numeric = re.match(r"\d{1,2}", value)
    return int(numeric.group(0)) if numeric else None


def _tv_revision_from_match(match: re.Match[str]) -> str:
    group_names = match.re.groupindex
    if "revision" in group_names:
        return str(match.groupdict().get("revision") or "").casefold()
    return ""


def _tv_episode_code(identity: dict[str, Any]) -> str:
    code = f"S{int(identity['season']):02d}E{int(identity['episode_start']):02d}"
    episode_end = identity.get("episode_end")
    if episode_end is not None:
        code += f"-E{int(episode_end):02d}"
    return code


def tv_identity_key(identity: dict[str, Any]) -> str:
    show_key = re.sub(r"[^a-z0-9]+", " ", str(identity.get("show") or "").casefold()).strip()
    return f"{show_key}_{_tv_episode_code(identity)}"


def parse_formatted_tv_identity(value: str) -> dict[str, Any] | None:
    stem = strip_known_media_suffix(value)
    match = TV_TARGET_NAME_PATTERN.fullmatch(stem)
    if match is None:
        return None
    episode_start = int(match.group("episode"))
    episode_end = int(match.group("episode_end")) if match.group("episode_end") else None
    if episode_start < 1 or episode_start > 999 or (episode_end is not None and (episode_end > 999 or episode_end <= episode_start)):
        return None
    return {
        "show": match.group("show").strip(),
        "season": int(match.group("season")),
        "episode_start": episode_start,
        "episode_end": episode_end,
        "episode_title": str(match.group("episode_title") or "").strip(),
        "revision": "",
        "parse_mode": "formatted-sxxexx-range" if episode_end is not None else "formatted-sxxexx",
        "reliable": True,
        "parse_error": "",
    }


def parse_tv_identity(
    source: Path,
    *,
    season_number: int,
    remove_terms: list[str] | None = None,
    tv_filter_options: dict[str, bool] | None = None,
    tv_filter_terms: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    stem = source.stem
    token = find_tv_episode_token(stem)
    has_canonical_identity = token is not None and token[0] == "season_episode"
    if TV_MALFORMED_SXX_RANGE_PATTERN.search(stem) or (
        not has_canonical_identity and TV_NONCANONICAL_RANGE_PATTERN.search(stem)
    ):
        return _tv_identity_error(
            "Noncanonical TV episode range; use SxxEyy-Ezz (for example S01E01-E02).",
            parse_mode="noncanonical-range",
        )

    folder_info = resolve_tv_folder_season_info(source, remove_terms, tv_filter_options, tv_filter_terms)
    season = 0
    episode_start = 0
    episode_end: int | None = None
    revision = ""
    show_fragment = ""
    parse_mode = "ambiguous"
    special_kind = ""

    if token is not None and token[0] == "season_episode":
        _, match = token
        season = int(match.group("season"))
        episode_start = int(match.group("episode"))
        episode_end = int(match.group("episode_end")) if match.group("episode_end") else None
        revision = _tv_revision_from_match(match)
        show_fragment = stem[: match.start()]
        parse_mode = "sxxexx-range" if episode_end is not None else "sxxexx"
    elif token is not None and token[0] == "nxm":
        _, match = token
        season = int(match.group("season"))
        episode_start = int(match.group("episode"))
        show_fragment = stem[: match.start()]
        parse_mode = "nxm"
    else:
        season_match = TV_SEASON_ONLY_PATTERN.search(stem)
        episode_match = token[1] if token is not None and token[0] in {"explicit", "bare_anime"} else None
        if season_match and episode_match is not None and token is not None and token[0] == "explicit":
            season = int(season_match.group("season"))
            episode_start = int(episode_match.group("episode"))
            revision = _tv_revision_from_match(episode_match)
            show_fragment = stem[: season_match.start()]
            parse_mode = "season+episode"
        elif episode_match is not None:
            episode_start = int(episode_match.group("episode"))
            revision = _tv_revision_from_match(episode_match)
            ordinal_match = TV_ORDINAL_SEASON_PATTERN.search(stem)
            special_match = TV_SPECIAL_MARKER_PATTERN.search(stem)
            if folder_info is not None:
                season = int(folder_info["season"])
                show_fragment = stem[: episode_match.start()]
                parse_mode = "folder-season+episode"
            elif ordinal_match is not None:
                season = int(_ordinal_season_number(ordinal_match) or 0)
                show_fragment = stem[: ordinal_match.start()]
                parse_mode = "ordinal-season"
            elif special_match is not None:
                season = 0
                special_kind = special_match.group("kind").upper().rstrip("S")
                show_fragment = stem[: special_match.start()] if special_match.start() < episode_match.start() else stem[: episode_match.start()]
                parse_mode = "filename-special"
            else:
                season = season_number if season_number >= 0 else 1
                show_fragment = stem[: episode_match.start()]
                parse_mode = "default-season+episode"

    if episode_start <= 0:
        return _tv_identity_error(
            "TV auto preview needs SxxEyy, NxM, Episode N, Ep N, or E01 in the filename, or a canonical SxxEyy-Ezz range.",
            parse_mode="missing-episode",
        )
    if season < 0 or season > 99 or episode_start > 999:
        return _tv_identity_error(
            "TV season/episode is outside S00-S99 and E001-E999; use SxxEyy-Ezz for ranges.",
            parse_mode="out-of-range",
        )
    if episode_end is not None and (episode_end < 1 or episode_end > 999 or episode_end <= episode_start):
        return _tv_identity_error(
            "TV episode range must increase within E001-E999; use SxxEyy-Ezz (for example S01E01-E02).",
            parse_mode="invalid-range",
        )
    show = clean_pipeline_tv_name_part(
        show_fragment,
        remove_terms,
        tv_filter_options,
        tv_filter_terms,
        preserve_title_terms=True,
    )
    if not show and folder_info is not None:
        show = str(folder_info.get("show") or "")
    if not show:
        show = clean_pipeline_tv_name_part(
            source.parent.name,
            remove_terms,
            tv_filter_options,
            tv_filter_terms,
            preserve_title_terms=True,
        )
    if not show:
        return _tv_identity_error(
            "TV auto preview could not infer a show name before the episode token.",
            parse_mode="missing-show",
        )
    episode_title = extract_confident_tv_episode_title(stem, remove_terms, tv_filter_options, tv_filter_terms)
    return {
        "show": show,
        "season": season,
        "episode_start": episode_start,
        "episode_end": episode_end,
        "episode_title": episode_title,
        "revision": revision,
        "special_kind": special_kind,
        "parse_mode": parse_mode,
        "reliable": True,
        "parse_error": "",
    }


def build_auto_tv_rename_name(
    source: Path,
    *,
    season_number: int,
    remove_terms: list[str] | None,
    tv_filter_options: dict[str, bool] | None = None,
    tv_filter_terms: dict[str, list[str]] | None = None,
    include_episode_title: bool = True,
) -> str:
    identity = parse_tv_identity(
        source,
        season_number=season_number,
        remove_terms=remove_terms,
        tv_filter_options=tv_filter_options,
        tv_filter_terms=tv_filter_terms,
    )
    if not identity["reliable"]:
        raise ValueError(str(identity["parse_error"]))
    episode_title = str(identity["episode_title"])
    if not include_episode_title:
        episode_title = ""
    title_part = f" - {episode_title}" if episode_title else ""
    return f"{identity['show']} - {_tv_episode_code(identity)}{title_part}{source.suffix.lower()}"
