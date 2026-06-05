from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mediapipeline.core.rename.utils import remove_default_priority_markers


TV_SPECIALS_FOLDER_PATTERN = re.compile(
    r"(?i)^\s*(?:specials?|ovas?|oads?|oavs?|onas?|extras?|bonus|featurettes?|"
    r"behind[\s._-]*(?:the[\s._-]*)?scenes|deleted[\s._-]*scenes|interviews?|"
    r"shorts?|trailers?|clips?|promos?|samples?|bts)\s*$"
)
TV_ORDINAL_WORDS = {
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


def resolve_tv_folder_season_info(
    source: Path,
    remove_terms: list[str] | None = None,
    *,
    clean_name: Callable[[str, list[str] | None], str],
) -> dict[str, Any] | None:
    current = source.parent
    for _depth in range(2):
        if not current or not str(current):
            break
        leaf = remove_default_priority_markers(current.name)
        if not leaf:
            break
        flexible_leaf = leaf
        for _pass in range(5):
            before = flexible_leaf
            flexible_leaf = re.sub(r"\[[^\[\]]*\]", " ", flexible_leaf)
            flexible_leaf = re.sub(r"\{[^{}]*\}", " ", flexible_leaf)
            flexible_leaf = re.sub(
                r"(?i)\([^)]*(?:2160p|1080p|720p|480p|uhd|hdr|hevc|h264|h265|x264|x265|av1|bd|blu[\s._-]*ray|web[\s._-]*dl|webdl|webrip|subs?|dual[\s._-]*audio)[^)]*\)",
                " ",
                flexible_leaf,
            )
            if flexible_leaf == before:
                break
        flexible_leaf = re.sub(r"[\._]+", " ", flexible_leaf)
        flexible_leaf = re.sub(r"\s+", " ", flexible_leaf).strip(" .-_")
        parent_leaf = current.parent.name if current.parent and current.parent != current else ""

        if TV_SPECIALS_FOLDER_PATTERN.fullmatch(leaf):
            show = clean_name(parent_leaf, remove_terms)
            return {"season": 0, "show": show, "source": "specials-folder"}

        match = re.fullmatch(r"(?i)\s*Season[\s._-]*(\d{1,2})\s*", flexible_leaf)
        if match:
            show = clean_name(parent_leaf, remove_terms)
            return {"season": int(match.group(1)), "show": show, "source": "season-folder"}

        match = re.fullmatch(r"(?i)\s*S[\s._-]*(\d{1,2})\s*", flexible_leaf)
        if match:
            show = clean_name(parent_leaf, remove_terms)
            return {"season": int(match.group(1)), "show": show, "source": "s-folder"}

        match = re.fullmatch(r"(?i)(?P<show>.+?)\s*\((?:Season\s*)?S?(?P<season>\d{1,2})\)\s*", leaf)
        if match:
            return {
                "season": int(match.group("season")),
                "show": clean_name(match.group("show"), remove_terms),
                "source": "show-folder-suffix",
            }

        match = re.fullmatch(r"(?i)(?P<show>.+?)\s+S(?P<season>\d{1,2})(?![A-Za-z0-9])\s*", flexible_leaf)
        if match:
            return {
                "season": int(match.group("season")),
                "show": clean_name(match.group("show"), remove_terms),
                "source": "show-s-folder",
            }

        match = re.fullmatch(
            r"(?i)(?P<show>.+?)(?:\s+|[\._-]+)(?:[-\u2013]\s*)?(?:Season[\s._-]*(?P<season_word>\d{1,2})|S[\s._-]*(?P<season_s>\d{1,2})(?![A-Za-z0-9]))(?:\s+.*)?",
            flexible_leaf,
        )
        if match:
            season_text = match.group("season_word") or match.group("season_s")
            return {
                "season": int(season_text),
                "show": clean_name(match.group("show"), remove_terms),
                "source": "show-season-folder",
            }

        ordinal_match = re.fullmatch(
            r"(?i)(?P<show>.+?)\s*(?:[-\u2013]\s*)?(?P<ordinal>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th))\s+(?:Season|Cour)(?:\s*(?:complete)\s*)?",
            flexible_leaf,
        )
        if ordinal_match:
            ordinal_text = ordinal_match.group("ordinal").casefold()
            if ordinal_text in TV_ORDINAL_WORDS:
                ordinal_season = TV_ORDINAL_WORDS[ordinal_text]
            else:
                ordinal_season = int(re.match(r"\d+", ordinal_text).group(0))
            return {
                "season": ordinal_season,
                "show": clean_name(ordinal_match.group("show"), remove_terms),
                "source": "show-ordinal-season-folder",
            }

        current = current.parent
    return None
