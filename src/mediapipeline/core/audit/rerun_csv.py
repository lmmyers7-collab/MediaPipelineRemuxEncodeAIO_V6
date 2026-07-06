from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, UTC
from pathlib import Path, PureWindowsPath
from typing import Any

from mediapipeline.core.audit.contracts import AuditRecord
from mediapipeline.core.audit.rerun_records import audit_row_value, rerun_media_kind_from_audit

RERUN_CSV_COLUMNS = (
    "enabled",
    "source_path",
    "media_kind",
    "audit_issue_codes",
    "stage_mode",
    "post_success_original",
    "return_mode",
    "plex_planned_path",
    "source_size",
    "source_mtime_utc",
    "source_identity_v2",
    "priority_fix_level",
    "effective_bucket",
    "primary_issue_code",
    "lookup_title",
    "relative_path",
    "notes",
)


_MOVIE_NOISE_RE = re.compile(
    r"\b(?:"
    r"2160p|1080p|720p|480p|uhd|hdr10\+?|hdr|dv|dovi|dolby[\s._-]*vision|"
    r"hevc|h\.?264|h\.?265|x264|x265|av1|avc|blu[\s._-]*ray|brrip|bdrip|"
    r"webrip|web[\s._-]*dl|webdl|web|hdtv|dvdrip|dvd|remux|extended|remastered|"
    r"remaster|unrated|theatrical|proper|repack|rerip|imax|criterion|directors?[\s._-]*cut|"
    r"final[\s._-]*cut|open[\s._-]*matte|amzn|nf|dsnp|hmax|hulu|itunes|appletv|mkv|mp4|m4v"
    r")\b",
    re.IGNORECASE,
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _mapping_value(row: Mapping[str, Any], *names: str) -> Any:
    lowered = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        key = name.casefold()
        if key in lowered:
            return lowered[key]
    return None


def _row_text(row: Mapping[str, Any], *names: str) -> str:
    return _clean_text(_mapping_value(row, *names))


def _csv_bool(value: Any, default: bool) -> bool:
    text = _clean_text(value).casefold()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on", "enabled", "run"}


def _path_leaf(path_text: str) -> str:
    text = _clean_text(path_text)
    if not text:
        return ""
    if "\\" in text or ":" in text:
        return PureWindowsPath(text).name
    return Path(text).name


def _path_stem(path_text: str) -> str:
    leaf = _path_leaf(path_text)
    if not leaf:
        return ""
    if "\\" in leaf or ":" in leaf:
        return PureWindowsPath(leaf).stem
    return Path(leaf).stem


def _with_output_container(relative_path: str, output_container: str) -> str:
    text = _clean_text(relative_path)
    if not text:
        return ""
    container = normalize_rerun_output_container(output_container)
    if "\\" in text or ":" in text:
        parsed = PureWindowsPath(text)
        parent = str(parsed.parent)
        leaf = f"{parsed.stem}.{container}"
        return leaf if parent in {"", "."} else str(PureWindowsPath(parent) / leaf)
    parsed_path = Path(text)
    parent = str(parsed_path.parent)
    leaf = f"{parsed_path.stem}.{container}"
    return leaf if parent in {"", "."} else str(parsed_path.parent / leaf)


def normalize_rerun_output_container(value: Any) -> str:
    text = _clean_text(value).lower().lstrip(".")
    return text or "mkv"


def rerun_output_container_from_config(config: Mapping[str, Any] | None) -> str:
    if not isinstance(config, Mapping):
        return "mkv"
    return normalize_rerun_output_container(_mapping_value(config, "OutputContainer", "output_container"))


def _clean_movie_title(value: str) -> str:
    base = _clean_text(_path_stem(value) or value)
    if not base:
        return ""
    year = ""
    bracketed = re.search(r"[\(\[](19|20)(\d{2})[\)\]]", base)
    if bracketed:
        year = f"{bracketed.group(1)}{bracketed.group(2)}"
    else:
        unbracketed = re.search(r"\b(19|20)\d{2}\b", base)
        if unbracketed:
            year = unbracketed.group(0)

    title = base
    for _ in range(5):
        stripped = re.sub(r"\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}", " ", title)
        if stripped == title:
            break
        title = stripped
    title = re.sub(r"[{}\[\]()]", " ", title)
    title = _MOVIE_NOISE_RE.sub(" ", title)
    title = title.replace(".", " ").replace("_", " ")
    title = re.sub(r"\s-\s|\s-|-\s", " ", title)
    if year and not bracketed:
        title = re.sub(rf"\b{re.escape(year)}\b", " ", title)
    title = re.sub(r'[<>:"/\\|?*]', "", title)
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        title = re.sub(r'[<>:"/\\|?*]', "", base).strip()
    if year and title:
        return f"{title} ({year})"
    return title


def normalize_rerun_planned_output_key(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    normalized = text.replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.rstrip("/").casefold()


def planned_output_key_for_rerun_row(row: Mapping[str, Any], *, output_container: str = "mkv") -> str:
    media_kind = _row_text(row, "media_kind", "MediaKind").casefold()
    relative_path = _row_text(row, "relative_path", "RelativePath")
    if media_kind == "tv" and relative_path:
        return normalize_rerun_planned_output_key(_with_output_container(relative_path, output_container))

    source_path = _row_text(row, "source_path", "Path", "SourcePath")
    lookup_title = _row_text(row, "lookup_title", "LookupTitle")
    title_seed = _path_stem(source_path) or lookup_title or _path_stem(relative_path)
    movie_title = _clean_movie_title(title_seed)
    if not movie_title:
        return ""
    container = normalize_rerun_output_container(output_container)
    return normalize_rerun_planned_output_key(f"{movie_title}/{movie_title}.{container}")


def append_rerun_note(row: dict[str, str], note: str) -> None:
    existing = str(row.get("notes") or "").strip()
    row["notes"] = f"{existing}; {note}" if existing else note


def disable_duplicate_planned_output_rows(rows: list[dict[str, str]], *, output_container: str = "mkv") -> int:
    seen: dict[str, int] = {}
    disabled = 0
    for index, row in enumerate(rows):
        if not _csv_bool(row.get("enabled"), True):
            continue
        key = planned_output_key_for_rerun_row(row, output_container=output_container)
        if not key:
            continue
        kept_index = seen.get(key)
        if kept_index is None:
            seen[key] = index
            continue
        row["enabled"] = "false"
        append_rerun_note(
            row,
            f"disabled duplicate planned output path; kept_row_index={kept_index}; planned_output_key={key}",
        )
        disabled += 1
    return disabled


def build_rerun_csv_row(
    record: AuditRecord,
    *,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
) -> dict[str, str] | None:
    source_path = record.path
    if not source_path:
        return None
    return {
        "enabled": "true",
        "source_path": str(source_path),
        "media_kind": rerun_media_kind_from_audit(record),
        "audit_issue_codes": record.row.get("NonSidecarIssueCodes", "").strip()
        or record.row.get("IssueCodes", "").strip()
        or record.primary_issue_code,
        "stage_mode": stage_mode,
        "post_success_original": original_mode,
        "return_mode": return_mode,
        "plex_planned_path": audit_row_value(record, "plex_planned_path", "PlannedOutputPath", "OutputPath"),
        "source_size": "",
        "source_mtime_utc": "",
        "source_identity_v2": audit_row_value(record, "source_identity_v2", "SourceIdentityV2"),
        "priority_fix_level": record.priority_fix_level,
        "effective_bucket": record.effective_bucket,
        "primary_issue_code": record.primary_issue_code,
        "lookup_title": record.lookup_title,
        "relative_path": record.relative_path,
        "notes": "",
    }


def apply_rerun_source_metadata(row: dict[str, str], metadata: dict[str, Any] | None) -> dict[str, str]:
    updated = dict(row)
    if not metadata:
        return updated
    updated["source_size"] = str(metadata.get("source_size") or "")
    updated["source_mtime_utc"] = str(metadata.get("source_mtime_utc") or "")
    if not updated["source_identity_v2"]:
        updated["source_identity_v2"] = str(metadata.get("source_identity_v2") or "")
    if not bool(metadata.get("exists", False)):
        updated["enabled"] = "false"
        updated["notes"] = f"source metadata failed: {metadata.get('error') or 'source unavailable'}"
    return updated


def source_stat_to_rerun_values(st_size: int, st_mtime: float) -> tuple[str, str]:
    return str(st_size), datetime.fromtimestamp(st_mtime, UTC).isoformat()
