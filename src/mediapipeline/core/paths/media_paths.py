from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def split_path_segments(raw_path: str) -> list[str]:
    return [segment for segment in re.split(r"[\\/]+", raw_path or "") if segment]


def extract_season_token(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"(?:season\s*|s)(\d{1,2})\b", text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).zfill(2)


def strip_parenthetical_season(value: str) -> str:
    text = re.sub(r"\s*\((?:season\s*|s)\d{1,2}\)\s*$", "", str(value or ""), flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+(?:season\s*|s)\d{1,2}\s*$", "", text, flags=re.IGNORECASE).strip()
    return text


def is_season_only_lookup(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(re.fullmatch(r"(?i)(?:season\s*\d{1,2}|s\d{1,2})(?:\s*\((?:season\s*|s)\d{1,2}\))?", text))


def derive_tv_lookup_title(raw_path: str) -> str:
    parts = split_path_segments(raw_path)
    lower_parts = [part.casefold() for part in parts]
    if "tv" not in lower_parts:
        return ""
    index = lower_parts.index("tv")
    if index + 1 >= len(parts):
        return ""
    show_name = parts[index + 1]
    season_value = ""
    if index + 2 < len(parts):
        season_value = extract_season_token(parts[index + 2])
    if not season_value and index + 3 < len(parts):
        season_value = extract_season_token(parts[index + 3])
    if not season_value and parts:
        season_value = extract_season_token(parts[-1])
    if season_value:
        return f"{strip_parenthetical_season(show_name)} (Season {season_value})"
    return show_name


def parse_pipeline_datetime(value: str) -> datetime | None:
    """Parse a datetime from formats the pipeline has historically emitted."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def ensure_aware_datetime(value: datetime) -> datetime:
    """Promote a naive datetime to timezone-aware by attaching the local tz."""
    if value.tzinfo is not None:
        return value
    return value.astimezone()


_TV_FILENAME_PATTERN = re.compile(r"\bs\d{1,2}e\d{1,3}\b", re.IGNORECASE)
_TV_SEASON_FOLDER_PATTERN = re.compile(r"^\s*season\s*\d{1,2}\s*$|^\s*s\d{1,2}\s*$", re.IGNORECASE)
_MOVIE_YEAR_FOLDER_PATTERN = re.compile(r"\(\d{4}\)\s*$")


def derive_media_type_from_path(raw_path: str) -> str:
    """Best-effort media type from the output path."""
    parts = split_path_segments(raw_path)
    if not parts:
        return ""
    lower_parts = [segment.casefold() for segment in parts]
    if "tv" in lower_parts:
        return "TV"
    if "movies" in lower_parts:
        return "Movie"

    leaf = parts[-1] if parts else ""
    parent = parts[-2] if len(parts) >= 2 else ""

    if leaf and _TV_FILENAME_PATTERN.search(leaf):
        return "TV"
    if parent and _TV_FILENAME_PATTERN.search(parent):
        return "TV"
    if parent and _TV_SEASON_FOLDER_PATTERN.match(parent):
        return "TV"
    if parent and _MOVIE_YEAR_FOLDER_PATTERN.search(parent):
        return "Movie"
    return ""


def derive_lookup_title_from_output_path(raw_path: str) -> str:
    parts = split_path_segments(raw_path)
    lower_parts = [part.casefold() for part in parts]
    try:
        if "movies" in lower_parts:
            index = lower_parts.index("movies")
            if index + 1 < len(parts):
                return parts[index + 1]
        if "tv" in lower_parts:
            derived = derive_tv_lookup_title(raw_path)
            if derived:
                return derived
    except Exception:
        pass
    if parts:
        return Path(parts[-1]).stem
    return ""


def derive_relative_media_path(raw_path: str) -> str:
    parts = split_path_segments(raw_path)
    lower_parts = [part.casefold() for part in parts]
    for anchor in ("movies", "tv"):
        if anchor in lower_parts:
            index = lower_parts.index(anchor)
            remainder = parts[index + 1 :]
            if remainder:
                return "\\".join(remainder)
    return raw_path
