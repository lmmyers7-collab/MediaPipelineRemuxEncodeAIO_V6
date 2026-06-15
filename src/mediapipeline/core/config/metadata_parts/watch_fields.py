"""Watch-folder settings field definitions."""

from __future__ import annotations


WATCH_CONFIG_FIELD_DEFINITIONS = (
    {
        "page": "Schedule",
        "section": "Watch Folders",
        "key": "EnableWatchFolders",
        "label": "Enable Watch Folders",
        "kind": "bool",
        "default": False,
        "help": "Master switch for background source-root polling. Disabled means no watcher filesystem reads.",
    },
    {
        "page": "Schedule",
        "section": "Watch Folders",
        "key": "WatchFolderRoots",
        "label": "Watch Folder Roots",
        "kind": "list",
        "default": (),
        "help": "Explicit roots to poll. Leave empty to derive enabled library profile source roots.",
    },
    {
        "page": "Schedule",
        "section": "Watch Folders",
        "key": "WatchDebounceSeconds",
        "label": "Watch Debounce (s)",
        "kind": "int",
        "default": 30,
        "help": "Seconds an unchanged candidate file must span before it can trigger pending watch work.",
    },
    {
        "page": "Schedule",
        "section": "Watch Folders",
        "key": "WatchAction",
        "label": "Watch Action",
        "kind": "combo",
        "choices": ("enqueue_only", "enqueue_and_launch"),
        "default": "enqueue_only",
        "help": "enqueue_only records pending detected work; enqueue_and_launch requests the existing gated once-launch path.",
    },
    {
        "page": "Schedule",
        "section": "Watch Folders",
        "key": "WatchRespectScheduleWindow",
        "label": "Respect Schedule Window",
        "kind": "bool",
        "default": True,
        "help": "When enabled, auto-launch attempts respect the saved schedule gate and retry while the window is closed.",
    },
)
