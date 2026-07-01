"""Compatibility shim for media path helpers moved to ``core.paths``."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _media_paths() -> Any:
    return import_module("mediapipeline.core.paths.media_paths")


def split_path_segments(raw_path: str) -> list[str]:
    return _media_paths().split_path_segments(raw_path)


def extract_season_token(value: str) -> str:
    return _media_paths().extract_season_token(value)


def strip_parenthetical_season(value: str) -> str:
    return _media_paths().strip_parenthetical_season(value)


def is_season_only_lookup(value: str) -> bool:
    return _media_paths().is_season_only_lookup(value)


def derive_tv_lookup_title(raw_path: str) -> str:
    return _media_paths().derive_tv_lookup_title(raw_path)


def parse_pipeline_datetime(value: str) -> Any:
    return _media_paths().parse_pipeline_datetime(value)


def ensure_aware_datetime(value: Any) -> Any:
    return _media_paths().ensure_aware_datetime(value)


def derive_media_type_from_path(raw_path: str) -> str:
    return _media_paths().derive_media_type_from_path(raw_path)


def derive_lookup_title_from_output_path(raw_path: str) -> str:
    return _media_paths().derive_lookup_title_from_output_path(raw_path)


def derive_relative_media_path(raw_path: str) -> str:
    return _media_paths().derive_relative_media_path(raw_path)


_derive_lookup_title_from_output_path = derive_lookup_title_from_output_path
_derive_media_type_from_path = derive_media_type_from_path
_derive_relative_media_path = derive_relative_media_path
_derive_tv_lookup_title = derive_tv_lookup_title
_ensure_aware = ensure_aware_datetime
_is_season_only_lookup = is_season_only_lookup
_parse_iso_datetime = parse_pipeline_datetime
_split_path_segments = split_path_segments
