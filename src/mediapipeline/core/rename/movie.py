from __future__ import annotations

import re
from datetime import date
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
MOVIE_VERIFIED_METADATA_ANCHOR_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"(?:2160|1080|720|480)[pi]|4k|uhd|hdr(?:10\+?)?|hlg|dv|dovi|dolby[\s._-]*vision|"
    r"hevc|h[\s._-]*\.?26[45]|x26[45]|av1|avc|xvid|divx|"
    r"blu[\s._-]*ray|bluray|brrip|bdrip|web[\s._-]*dl|webdl|webrip|hdtv|"
    r"hdrip|dvdrip|dvdscr|remux|"
    r"truehd|atmos|flac|opus|eac3|ac3|aac|ddp?|dts(?:[\s._-]*hd)?|dtshd|lpcm|pcm|"
    r"(?:10|8)[\s._-]*bit|\d+(?:\.\d+)?[\s._-]*(?:mb|gb)"
    r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)
MOVIE_REVISION_TAIL_PATTERN = re.compile(
    r"(?:^|[\s._-]+)(?P<term>proper|repack|rerip)[\s._-]*$",
    re.IGNORECASE,
)
MOVIE_NON_CREDIBLE_ANCHOR_PREFIXES = frozenset({"a", "an", "the"})
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
    "asiimov",
    "rapta",
    "licdom",
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
        "10bit",
        "10 bits",
        "10bits",
        "10-bit",
        "10-bits",
        "8 bit",
        "8bit",
        "8 bits",
        "8bits",
        "8-bit",
        "8-bits",
        "upscale",
        "upscaled",
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
MOVIE_UPPERCASE_TOKENS = frozenset({"4k", "avc", "dc"})


def _rightmost_movie_year_match(base: str) -> re.Match[str] | None:
    maximum_year = date.today().year + 1

    def plausible(match: re.Match[str]) -> bool:
        raw_year = match.groupdict().get("year") or match.group(0)
        if not 1888 <= int(raw_year) <= maximum_year:
            return False
        remainder = f"{base[: match.start()]} {base[match.end() :]}"
        return re.search(r"[A-Za-z0-9]", remainder) is not None

    bracketed = [
        match
        for match in re.finditer(r"[\(\[]\s*(?P<year>\d{4})\s*[\)\]]", base)
        if plausible(match)
    ]
    if bracketed:
        return bracketed[-1]
    loose = [match for match in re.finditer(r"(?<!\d)(?P<year>\d{4})(?!\d)", base) if plausible(match)]
    return loose[-1] if loose else None


def _movie_year_value(year_match: re.Match[str] | None) -> str:
    if year_match is None:
        return ""
    return str(year_match.groupdict().get("year") or year_match.group(0))


def _movie_base_without_selected_year(base: str, year_match: re.Match[str] | None) -> str:
    if year_match is None:
        return base
    return f"{base[: year_match.start()]} {base[year_match.end() :]}"


def _trailing_movie_filter_term_start(text: str, term: str) -> int | None:
    pattern = movie_filter_term_pattern(term, bounded=False)
    if not pattern:
        return None
    match = re.search(rf"(?i)(?:^|[\s._-]+)(?P<term>{pattern})[\s._-]*$", text)
    if match is None:
        return None
    start = match.start("term")
    return start if text[:start].strip(" .-_") else None


def _enabled_movie_metadata_terms(
    filter_options: dict[str, bool],
    filter_terms: dict[str, list[str]],
    *,
    custom_only: bool,
) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for category in RENAME_MOVIE_FILTER_OPTION_KEYS:
        if not filter_options.get(category, True):
            continue
        category_terms = movie_filter_terms_for_key(filter_terms, category) or []
        if custom_only:
            default_keys = {term.casefold() for term in RENAME_MOVIE_FILTER_DEFAULT_TERMS.get(category, ())}
            category_terms = [term for term in category_terms if term.casefold() not in default_keys]
        else:
            category_terms = collective_movie_filter_terms(filter_terms, category)
        for term in category_terms:
            key = term.casefold()
            if key in seen:
                continue
            seen.add(key)
            terms.append(term)
    return sorted(terms, key=len, reverse=True)


def _movie_metadata_anchor_region_is_metadata_only(
    text: str,
    filter_options: dict[str, bool],
    filter_terms: dict[str, list[str]],
) -> bool:
    remainder = MOVIE_VERIFIED_METADATA_ANCHOR_PATTERN.sub(" ", text)
    for term in _enabled_movie_metadata_terms(filter_options, filter_terms, custom_only=False):
        pattern = movie_filter_term_pattern(term)
        if pattern:
            remainder = re.sub(pattern, " ", remainder, flags=re.IGNORECASE)
    return re.search(r"[A-Za-z0-9]", remainder) is None


def _verified_movie_metadata_anchor(
    text: str,
    filter_options: dict[str, bool],
    filter_terms: dict[str, list[str]],
    *,
    selected_year_index: int | None,
) -> re.Match[str] | None:
    matches = list(MOVIE_VERIFIED_METADATA_ANCHOR_PATTERN.finditer(text))
    if not matches:
        return None

    if selected_year_index is not None:
        post_year = next((match for match in matches if match.start() >= selected_year_index), None)
        if post_year is not None:
            return post_year
        candidates = [match for match in matches if match.start() < selected_year_index]
        region_end = selected_year_index
    else:
        candidates = matches
        region_end = len(text)
    if not candidates:
        return None

    candidate = candidates[0]
    prefix = re.sub(r"[\s._-]+", " ", text[: candidate.start()]).strip().casefold()
    if prefix and prefix not in MOVIE_NON_CREDIBLE_ANCHOR_PREFIXES:
        return candidate
    candidate_region = text[candidate.start() : region_end]
    if len(list(MOVIE_VERIFIED_METADATA_ANCHOR_PATTERN.finditer(candidate_region))) >= 2 and _movie_metadata_anchor_region_is_metadata_only(
        candidate_region,
        filter_options,
        filter_terms,
    ):
        return candidate
    return None


def _verified_movie_metadata_tail_start(
    text: str,
    filter_options: dict[str, bool],
    filter_terms: dict[str, list[str]],
    *,
    precedes_year: bool,
    selected_year_index: int | None = None,
) -> int | None:
    anchor = _verified_movie_metadata_anchor(
        text,
        filter_options,
        filter_terms,
        selected_year_index=selected_year_index,
    )
    if anchor is not None:
        start = anchor.start()
        for _ in range(8):
            prefix = text[:start]
            expanded = next(
                (
                    term_start
                    for term in _enabled_movie_metadata_terms(filter_options, filter_terms, custom_only=False)
                    if (term_start := _trailing_movie_filter_term_start(prefix, term)) is not None
                ),
                None,
            )
            if expanded is None:
                break
            start = expanded
        return start
    if not precedes_year:
        return None
    revision = MOVIE_REVISION_TAIL_PATTERN.search(text)
    if revision is not None and text[: revision.start("term")].strip(" .-_"):
        return revision.start("term")
    for term in _enabled_movie_metadata_terms(filter_options, filter_terms, custom_only=True):
        start = _trailing_movie_filter_term_start(text, term)
        if start is not None:
            return start
    return None


def _movie_title_before_verified_tail(
    text: str,
    filter_options: dict[str, bool],
    filter_terms: dict[str, list[str]],
    *,
    precedes_year: bool,
    selected_year_index: int | None = None,
) -> str:
    tail_start = _verified_movie_metadata_tail_start(
        text,
        filter_options,
        filter_terms,
        precedes_year=precedes_year,
        selected_year_index=selected_year_index,
    )
    return text[:tail_start] if tail_start is not None else text


def _normalize_movie_title_region(
    title: str,
    remove_terms: list[str] | None,
    filter_options: dict[str, bool],
    filter_terms: dict[str, list[str]],
) -> str:
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
    result = strip_movie_release_groups(result, filter_options, filter_terms)
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
        if lower in MOVIE_UPPERCASE_TOKENS:
            formatted = lower.upper()
        elif lower in MOVIE_ROMAN_NUMERALS:
            formatted = lower.upper()
        elif lower == "the":
            formatted = "the" if index > 0 and previous_lower in MOVIE_LOWER_THE_AFTER else "The"
        elif index > 0 and lower in MOVIE_SMALL_WORDS and not (previous_lower.isdigit() and lower in {"a", "an", "the"}):
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
    year_match = _rightmost_movie_year_match(base)
    if year_match is not None:
        year = _movie_year_value(year_match)
    if all(filter_options.values()):
        title_region = _movie_base_without_selected_year(base, year_match)
        title_region = _movie_title_before_verified_tail(
            title_region,
            filter_options,
            filter_terms,
            precedes_year=year_match is not None,
            selected_year_index=year_match.start() if year_match is not None else None,
        )
        title = _normalize_movie_title_region(title_region, remove_terms, filter_options, filter_terms)
        if title:
            return f"{title} ({year})" if year else title
        return ""
    title = _movie_base_without_selected_year(base, year_match)
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
    title = normalize_plex_filename_component(title, remove_terms)
    title = title_case_movie_name(title)
    if not title:
        return ""
    if year:
        return f"{title} ({year})"
    return title
