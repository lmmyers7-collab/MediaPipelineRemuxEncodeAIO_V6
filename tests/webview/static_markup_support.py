from __future__ import annotations

import re
from pathlib import Path


_STATIC_INCLUDE_RE = re.compile(r"<!--\s*mp-include:\s*(?P<path>partials/[-A-Za-z0-9_.]+\.html)\s*-->")


def settings_markup(static_root: Path) -> str:
    """Return Settings partials in the exact order authored by index.html."""

    index = (static_root / "index.html").read_text(encoding="utf-8")
    include_paths = [
        match.group("path")
        for match in _STATIC_INCLUDE_RE.finditer(index)
        if Path(match.group("path")).name.startswith("page-settings")
    ]
    if not include_paths or include_paths[0] != "partials/page-settings.html":
        raise AssertionError("The Settings partial sequence is missing its page shell.")
    return "".join((static_root / Path(path)).read_text(encoding="utf-8") for path in include_paths)
