from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def _split_path_segments(raw_path: str) -> list[str]:
    return [segment for segment in re.split(r"[\\/]+", raw_path or "") if segment]


def _extract_season_token(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"(?:season\s*|s)(\d{1,2})\b", text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).zfill(2)


def _strip_parenthetical_season(value: str) -> str:
    text = re.sub(r"\s*\((?:season\s*|s)\d{1,2}\)\s*$", "", str(value or ""), flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+(?:season\s*|s)\d{1,2}\s*$", "", text, flags=re.IGNORECASE).strip()
    return text


def _is_season_only_lookup(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(re.fullmatch(r"(?i)(?:season\s*\d{1,2}|s\d{1,2})(?:\s*\((?:season\s*|s)\d{1,2}\))?", text))


def _derive_tv_lookup_title(raw_path: str) -> str:
    parts = _split_path_segments(raw_path)
    lower_parts = [part.casefold() for part in parts]
    if "tv" not in lower_parts:
        return ""
    index = lower_parts.index("tv")
    if index + 1 >= len(parts):
        return ""
    show_name = parts[index + 1]
    season_value = ""
    if index + 2 < len(parts):
        season_value = _extract_season_token(parts[index + 2])
    if not season_value and index + 3 < len(parts):
        season_value = _extract_season_token(parts[index + 3])
    if not season_value and parts:
        season_value = _extract_season_token(parts[-1])
    if season_value:
        return f"{_strip_parenthetical_season(show_name)} (Season {season_value})"
    return show_name


def _parse_iso_datetime(value: str) -> datetime | None:
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


def _ensure_aware(value: datetime) -> datetime:
    """Promote a naive datetime to timezone-aware by attaching the local tz."""
    if value.tzinfo is not None:
        return value
    return value.astimezone()


_TV_FILENAME_PATTERN = re.compile(r"\bs\d{1,2}e\d{1,3}\b", re.IGNORECASE)
_TV_SEASON_FOLDER_PATTERN = re.compile(r"^\s*season\s*\d{1,2}\s*$|^\s*s\d{1,2}\s*$", re.IGNORECASE)
_MOVIE_YEAR_FOLDER_PATTERN = re.compile(r"\(\d{4}\)\s*$")


def _derive_media_type_from_path(raw_path: str) -> str:
    """Best-effort media type from the output path.

    Plex layouts the pipeline produces:
      TV    : <root>\\TV\\<Show>\\Season XX\\<file>.mkv   (CreateTVSubfolder=$true)
      Movie : <root>\\<Title (YYYY)>\\<Title (YYYY)>.mkv  (no Movies library folder)

    Older code only recognized literal 'TV' / 'Movies' library segments,
    which left movies blank for the default flat-Movie layout (see
    Get-OutputPaths in MediaPipeline_chatgpt.ps1 — Movie branch does NOT
    pass -IncludeLibraryFolder). New sidecars carry an explicit
    `media_type` field; this helper is the fallback for sidecars written
    before that fix.

    Detection order:
      1. literal 'tv' segment            → TV
      2. literal 'movies' segment        → Movie
      3. SxxEyy in filename / parent     → TV
      4. 'Season XX' parent folder       → TV
      5. parent folder ending in (YYYY)  → Movie
    """
    parts = _split_path_segments(raw_path)
    if not parts:
        return ""
    lower_parts = [segment.casefold() for segment in parts]
    if "tv" in lower_parts:
        return "TV"
    if "movies" in lower_parts:
        return "Movie"

    leaf = parts[-1] if parts else ""
    parent = parts[-2] if len(parts) >= 2 else ""

    # SxxEyy anywhere in the filename or parent dir is a strong TV signal.
    if leaf and _TV_FILENAME_PATTERN.search(leaf):
        return "TV"
    if parent and _TV_FILENAME_PATTERN.search(parent):
        return "TV"
    # "Season XX" / "S01" parent folder is the canonical Plex TV shape.
    if parent and _TV_SEASON_FOLDER_PATTERN.match(parent):
        return "TV"
    # Plex movie convention: the parent folder ends with "(YYYY)" and
    # the file basename usually matches it. The year-suffix check is a
    # very strong movie signal because "Some Show Season 1 (2020)" would
    # have been caught by the SxxEyy / Season checks above.
    if parent and _MOVIE_YEAR_FOLDER_PATTERN.search(parent):
        return "Movie"
    return ""


def _derive_lookup_title_from_output_path(raw_path: str) -> str:
    parts = _split_path_segments(raw_path)
    lower_parts = [part.casefold() for part in parts]
    try:
        if "movies" in lower_parts:
            index = lower_parts.index("movies")
            if index + 1 < len(parts):
                return parts[index + 1]
        if "tv" in lower_parts:
            derived = _derive_tv_lookup_title(raw_path)
            if derived:
                return derived
    except Exception:
        pass
    if parts:
        return Path(parts[-1]).stem
    return ""


def _derive_relative_media_path(raw_path: str) -> str:
    parts = _split_path_segments(raw_path)
    lower_parts = [part.casefold() for part in parts]
    for anchor in ("movies", "tv"):
        if anchor in lower_parts:
            index = lower_parts.index(anchor)
            remainder = parts[index + 1 :]
            if remainder:
                return "\\".join(remainder)
    return raw_path
