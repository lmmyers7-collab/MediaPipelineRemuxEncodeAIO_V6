"""Path-related Basic-page settings metadata."""

from __future__ import annotations

BASIC_PATH_FIELDS = (
{
        "page": "Basic",
        "section": "Paths",
        "key": "SourceMovies",
        "label": "Movies Source",
        "kind": "path",
        "help": "Folder the pipeline scans for incoming movie files.",
    },
{
        "page": "Basic",
        "section": "Paths",
        "key": "SourceTV",
        "label": "TV Source",
        "kind": "path",
        "help": "Folder the pipeline scans for incoming TV files.",
    },
{
        "page": "Basic",
        "section": "Paths",
        "key": "Outsource",
        "label": "Final Output",
        "kind": "path",
        "help": "Final processed library destination.",
    },
{
        "page": "Basic",
        "section": "Libraries",
        "key": "LibraryProfiles",
        "label": "Library Profiles",
        "kind": "json",
        "default": "[]",
        "help": "Per-library source, output, designation, optional promotion destination, and explicit editor/video/subtitle/audio overrides. Movie and TV are synthesized from legacy paths when this is not configured.",
    },
{
        "page": "Basic",
        "section": "Paths",
        "key": "LocalBase",
        "label": "Scratch Disk",
        "kind": "path",
        "help": "Fast local working directory for copies, remuxes, and temporary files.",
    },
)

BASIC_PATH_BEHAVIOR_FIELDS = (
{
        "page": "Basic",
        "section": "Paths",
        "key": "CreateTVSubfolder",
        "label": "Create TV Library Folders",
        "kind": "bool",
        "help": "When enabled, TV outputs are placed under TV\\Show\\Season NN style folders for Plex-style libraries.",
    },
)
