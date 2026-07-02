from __future__ import annotations

import re
from pathlib import Path

from mediapipeline.core.rename.constants import RENAME_MOVIE_FILTER_OPTION_KEYS
from mediapipeline.core.rename.utils import normalize_plex_filename_component, remove_default_priority_markers


MOVIE_VIDEO_SOURCE_TAG_PATTERN = re.compile(
    r"\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10\+?|dv|dovi|dolby[\s._-]*vision|"
    r"hevc|h\.?264|h\.?265|x264|x265|av1|avc|blu[\s._-]*ray|brrip|bdrip|"
    r"webrip|web[\s._-]*dl|webdl|web|hdtv|dvdrip|dvd|remux)\b",
    re.IGNORECASE,
)
MOVIE_EDITION_TAG_PATTERN = re.compile(
    r"\b(?:imax|proper|repack|rerip|extended|remastered|remaster|unrated|theatrical|"
    r"criterion|directors?[\s._-]*cut|final[\s._-]*cut|open[\s._-]*matte)\b",
    re.IGNORECASE,
)
MOVIE_SERVICE_CONTAINER_TAG_PATTERN = re.compile(r"\b(?:amzn|nf|dsnp|hmax|hulu|itunes|appletv|mkv|mp4|m4v)\b", re.IGNORECASE)
MOVIE_AUDIO_TAG_PATTERN = re.compile(
    r"\b(?:truehd|atmos|flac|opus|eac3|ac3|aac|ddp?|dts(?:[\s._-]*hd)?|dtshd)"
    r"(?:[\s._-]*(?:1\.0|2\.0|5\.1|7\.1|6ch|8ch))?\b|"
    r"\b(?:1\.0|2\.0|5\.1|7\.1|6\s*ch|8\s*ch)\b",
    re.IGNORECASE,
)
MOVIE_SIZE_TAG_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mb|gb)\b", re.IGNORECASE)
MOVIE_RELEASE_GROUP_TERMS = (
    "rarbg",
    "rbg",
    "yify",
    "yts",
    "yts lt",
    "galaxyrg",
    "bone",
    "psa",
    "tigole",
    "kris",
    "sparks",
    "ntb",
    "evo",
    "tepes",
    "flux",
    "framestor",
    "cmrg",
    "neonoir",
)
RENAME_MOVIE_FILTER_DEFAULT_TERMS: dict[str, tuple[str, ...]] = {
    "video_source": (
        "2160p",
        "1080p",
        "1080i",
        "720p",
        "720i",
        "480p",
        "4k",
        "uhd",
        "hdr",
        "hdr10",
        "hdr10+",
        "hlg",
        "dv",
        "dovi",
        "dolby vision",
        "hevc",
        "h264",
        "h.264",
        "h265",
        "h.265",
        "x264",
        "x265",
        "av1",
        "avc",
        "xvid",
        "divx",
        "blu ray",
        "bluray",
        "brrip",
        "bdrip",
        "webrip",
        "web dl",
        "webdl",
        "web",
        "hdtv",
        "hdrip",
        "dvdrip",
        "dvd",
        "dvdscr",
        "ts",
        "cam",
        "scr",
        "remux",
        "hybrid",
        "10 bit",
        "8 bit",
    ),
    "audio_channels": (
        "truehd",
        "atmos",
        "flac",
        "opus",
        "eac3",
        "ac3",
        "aac",
        "dd",
        "dd+",
        "ddp",
        "dts",
        "dts hd",
        "dts-x",
        "dtsx",
        "dtshd",
        "lpcm",
        "pcm",
        "mp3",
        "mp2",
        "1.0",
        "2.0",
        "5.1",
        "7.1",
        "stereo",
        "mono",
        "6ch",
        "6 ch",
        "8ch",
        "8 ch",
    ),
    "editions": (
        "imax",
        "proper",
        "repack",
        "rerip",
        "extended",
        "remastered",
        "remaster",
        "restored",
        "restoration",
        "unrated",
        "theatrical",
        "criterion",
        "director cut",
        "directors cut",
        "director's cut",
        "dc",
        "final cut",
        "open matte",
        "redux",
        "special edition",
        "se",
        "anniversary",
        "collectors edition",
        "supercut",
    ),
    "file_size": (
        "500mb",
        "700mb",
        "1400mb",
        "1gb",
        "1.5gb",
        "2gb",
        "3gb",
        "4.7gb",
        "5gb",
        "6gb",
        "8gb",
        "10gb",
        "15gb",
        "20gb",
        "25gb",
        "30gb",
    ),
    "services_containers": (
        "amzn",
        "nf",
        "dsnp",
        "hmax",
        "hulu",
        "itunes",
        "appletv",
        "atvp",
        "peacock",
        "pck",
        "vudu",
        "stan",
        "sho",
        "mkv",
        "mp4",
        "m4v",
        "avi",
        "mov",
        "wmv",
    ),
    "languages_subs_dubs": (
        "eng",
        "ita",
        "fre",
        "fra",
        "ger",
        "deu",
        "spa",
        "esp",
        "jpn",
        "jap",
        "kor",
        "chi",
        "zho",
        "rus",
        "por",
        "dut",
        "nld",
        "swe",
        "dan",
        "nor",
        "fin",
        "pol",
        "cze",
        "ces",
        "hun",
        "gre",
        "ell",
        "tur",
        "ara",
        "hin",
        "tha",
        "vie",
        "ukr",
        "sub",
        "subs",
        "subbed",
        "dub",
        "dubs",
        "dubbed",
        "multi",
        "multi audio",
        "dual audio",
        "dual-audio",
        "vostfr",
        "vose",
    ),
    "release_groups": MOVIE_RELEASE_GROUP_TERMS,
}
MOVIE_SMALL_WORDS = frozenset({"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "nor", "of", "on", "or", "per", "to", "vs", "via", "with"})
MOVIE_LOWER_THE_AFTER = frozenset({"by", "for", "from", "in", "into", "of", "on", "to", "with"})
MOVIE_ROMAN_NUMERALS = frozenset({"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"})


def _title_region_before_year(base: str, year_match: re.Match[str] | None) -> str:
    if not year_match:
        return ""
    return base[: year_match.start()].strip(" .-_")


def _normalize_movie_title_region(title: str, remove_terms: list[str] | None) -> str:
    result = str(title or "")
    for _ in range(5):
        before = result
        result = re.sub(r"\([^()]*\)", " ", result)
        result = re.sub(r"\[[^\[\]]*\]", " ", result)
        result = re.sub(r"\{[^{}]*\}", " ", result)
        if result == before:
            break
    result = re.sub(r"[{}\[\]()]", " ", result)
    result = remove_movie_filter_terms(result, remove_terms)
    result = re.sub(r"[\._]", " ", result)
    result = re.sub(r"\s-\s", " ", result)
    result = re.sub(r"\s-|-\s", " ", result)
    result = normalize_plex_filename_component(result, remove_terms)
    return title_case_movie_name(result)


def normalize_movie_filter_options(movie_filter_options: dict[str, bool] | None = None) -> dict[str, bool]:
    options = dict.fromkeys(RENAME_MOVIE_FILTER_OPTION_KEYS, True)
    for key, value in (movie_filter_options or {}).items():
        if key in options:
            options[key] = bool(value)
    return options


def movie_filter_enabled(movie_filter_options: dict[str, bool] | None, key: str) -> bool:
    return normalize_movie_filter_options(movie_filter_options).get(key, True)


def movie_filter_options_are_default(movie_filter_options: dict[str, bool] | None = None) -> bool:
    return all(normalize_movie_filter_options(movie_filter_options).values())


def normalize_movie_filter_terms(movie_filter_terms: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    for key, values in (movie_filter_terms or {}).items():
        if key not in RENAME_MOVIE_FILTER_OPTION_KEYS:
            continue
        parsed: list[str] = []
        seen: set[str] = set()
        for value in values or []:
            term = str(value or "").strip()
            term_key = term.casefold()
            if not term or term_key in seen:
                continue
            seen.add(term_key)
            parsed.append(term)
        terms[key] = parsed
    return terms


def rename_movie_filter_default_terms() -> dict[str, list[str]]:
    return {key: list(values) for key, values in RENAME_MOVIE_FILTER_DEFAULT_TERMS.items()}


def movie_filter_terms_for_key(movie_filter_terms: dict[str, list[str]] | None, key: str) -> list[str] | None:
    normalized = normalize_movie_filter_terms(movie_filter_terms)
    return normalized[key] if key in normalized else None


def collective_movie_filter_terms(movie_filter_terms: dict[str, list[str]] | None, key: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for term in list(RENAME_MOVIE_FILTER_DEFAULT_TERMS.get(key, ())) + list(movie_filter_terms_for_key(movie_filter_terms, key) or []):
        term_key = str(term or "").casefold()
        if not term_key or term_key in seen:
            continue
        seen.add(term_key)
        terms.append(str(term))
    return terms


def remove_custom_movie_filter_terms(text: str, movie_filter_terms: dict[str, list[str]] | None, key: str) -> str:
    custom_terms = movie_filter_terms_for_key(movie_filter_terms, key)
    return remove_movie_filter_terms(text, custom_terms) if custom_terms is not None else text


def title_case_movie_name(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    tokens: list[str] = []
    previous_lower = ""
    raw_tokens = [token for token in text.split(" ") if token]
    for index, token in enumerate(raw_tokens):
        word = token.lower() if token == token.upper() else token
        lower = word.casefold()
        if lower in MOVIE_ROMAN_NUMERALS:
            formatted = lower.upper()
        elif lower == "the":
            formatted = "the" if index > 0 and previous_lower in MOVIE_LOWER_THE_AFTER else "The"
        elif index > 0 and lower in MOVIE_SMALL_WORDS:
            formatted = lower
        elif "-" in word:
            formatted = "-".join(part[:1].upper() + part[1:] if part else part for part in word.split("-"))
        else:
            formatted = word[:1].upper() + word[1:] if word else word
        tokens.append(formatted)
        previous_lower = formatted.casefold()
    return " ".join(tokens)


def movie_filter_term_pattern(term: str, *, bounded: bool = True) -> str:
    raw_term = str(term or "").strip()
    if not raw_term:
        return ""
    pieces = [re.escape(piece) for piece in re.split(r"[\s._-]+", raw_term) if piece]
    body = r"[\s._-]*".join(pieces) if pieces else re.escape(raw_term)
    if not bounded or not re.search(r"[A-Za-z0-9]", raw_term):
        return body
    return rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])"


def remove_movie_filter_terms(text: str, remove_terms: list[str] | None) -> str:
    result = str(text or "")
    for term in remove_terms or []:
        pattern = movie_filter_term_pattern(term)
        if not pattern:
            continue
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    return result


def strip_movie_release_groups(
    text: str,
    movie_filter_options: dict[str, bool] | None = None,
    movie_filter_terms: dict[str, list[str]] | None = None,
) -> str:
    if not movie_filter_enabled(movie_filter_options, "release_groups"):
        return str(text or "")
    result = str(text or "")
    release_group_terms = collective_movie_filter_terms(movie_filter_terms, "release_groups")
    for _ in range(4):
        before = result
        for term in release_group_terms:
            pattern = movie_filter_term_pattern(term, bounded=False)
            if not pattern:
                continue
            result = re.sub(rf"(?i)^\s*[\[\(]?\s*{pattern}\s*[\]\)]?[\s._-]+", " ", result)
            result = re.sub(rf"(?i)[\s._-]+[\[\(]?\s*{pattern}\s*[\]\)]?\s*$", " ", result)
        result = re.sub(r"\s+", " ", result).strip(" .-_")
        if result == before:
            break
    return result


def clean_pipeline_movie_name(
    file_name: str,
    remove_terms: list[str] | None = None,
    movie_filter_options: dict[str, bool] | None = None,
    movie_filter_terms: dict[str, list[str]] | None = None,
) -> str:
    filter_options = normalize_movie_filter_options(movie_filter_options)
    filter_terms = normalize_movie_filter_terms(movie_filter_terms)
    base = remove_default_priority_markers(Path(file_name).stem)
    year = ""
    year_match: re.Match[str] | None = None
    bracketed_year = re.search(r"[\(\[](19|20)(\d{2})[\)\]]", base)
    if bracketed_year:
        year_match = bracketed_year
        year = bracketed_year.group(1) + bracketed_year.group(2)
    else:
        loose_year = re.search(r"\b(?:19|20)\d{2}\b", base)
        if loose_year:
            year_match = loose_year
            year = loose_year.group(0)
    title_region = _title_region_before_year(base, year_match)
    if year and title_region and all(filter_options.values()):
        title = _normalize_movie_title_region(title_region, remove_terms)
        if title:
            return f"{title} ({year})"

    title = base
    for _ in range(5):
        before = title
        title = re.sub(r"\([^()]*\)", " ", title)
        title = re.sub(r"\[[^\[\]]*\]", " ", title)
        title = re.sub(r"\{[^{}]*\}", " ", title)
        if title == before:
            break
    title = re.sub(r"[{}\[\]()]", " ", title)
    if filter_options["file_size"]:
        title = MOVIE_SIZE_TAG_PATTERN.sub(" ", title)
        title = remove_custom_movie_filter_terms(title, filter_terms, "file_size")
    if filter_options["audio_channels"]:
        title = MOVIE_AUDIO_TAG_PATTERN.sub(" ", title)
        title = remove_custom_movie_filter_terms(title, filter_terms, "audio_channels")
    if filter_options["video_source"]:
        title = MOVIE_VIDEO_SOURCE_TAG_PATTERN.sub(" ", title)
        title = re.sub(r"\b(?:10|8)\s*bit\b", " ", title, flags=re.IGNORECASE)
        title = remove_custom_movie_filter_terms(title, filter_terms, "video_source")
    if filter_options["editions"]:
        title = MOVIE_EDITION_TAG_PATTERN.sub(" ", title)
        title = remove_custom_movie_filter_terms(title, filter_terms, "editions")
    if filter_options["services_containers"]:
        title = MOVIE_SERVICE_CONTAINER_TAG_PATTERN.sub(" ", title)
        title = remove_custom_movie_filter_terms(title, filter_terms, "services_containers")
    if filter_options["languages_subs_dubs"]:
        title = remove_movie_filter_terms(title, collective_movie_filter_terms(filter_terms, "languages_subs_dubs"))
    title = remove_movie_filter_terms(title, remove_terms)
    title = strip_movie_release_groups(title, filter_options, filter_terms)
    title = re.sub(r"[\._]", " ", title)
    title = re.sub(r"\s-\s", " ", title)
    title = re.sub(r"\s-|-\s", " ", title)
    if year and not bracketed_year:
        title = re.sub(rf"\b{re.escape(year)}\b", " ", title)
    title = normalize_plex_filename_component(title, remove_terms)
    title = title_case_movie_name(title)
    if not title:
        title = normalize_plex_filename_component(base, remove_terms)
    if year:
        return f"{title} ({year})"
    return title
