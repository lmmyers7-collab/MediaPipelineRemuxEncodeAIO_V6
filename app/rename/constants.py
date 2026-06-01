from __future__ import annotations


RENAME_MOVIE_FILTER_OPTION_KEYS = (
    "video_source",
    "audio_channels",
    "editions",
    "file_size",
    "services_containers",
    "release_groups",
)
RENAME_TOOL_SIDECAR_SCHEMA_VERSION = "rename_tool.v1"
PLEX_RENAME_DEFAULT_REMOVE_TERMS = (
    "sample",
    "trailer",
    "extras",
    "featurette",
    "deleted scenes",
    "behind the scenes",
)


__all__ = [
    "PLEX_RENAME_DEFAULT_REMOVE_TERMS",
    "RENAME_MOVIE_FILTER_OPTION_KEYS",
    "RENAME_TOOL_SIDECAR_SCHEMA_VERSION",
]
