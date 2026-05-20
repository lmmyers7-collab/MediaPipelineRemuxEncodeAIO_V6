from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .http_helpers import content_type_for, resolve_asset_path
from .static_files_policy import (
    STATIC_INDEX_BOOTSTRAP_PLACEHOLDER,
    StaticFileResponse,
    local_api_bootstrap,
    missing_bootstrap_placeholder_response,
    missing_index_response,
    render_index_html,
    render_static_includes,
    static_error_response,
    static_not_found_response,
)


def default_static_root() -> Path:
    return Path(__file__).resolve().parents[1] / "ui_web" / "static"


def render_index(
    static_root: Path,
    bootstrap: dict[str, Any],
    *,
    logger: logging.Logger | None = None,
) -> StaticFileResponse:
    index_path = static_root / "index.html"
    if not index_path.exists():
        return missing_index_response()
    try:
        html = index_path.read_text(encoding="utf-8")
        html = render_static_includes(html, static_root)
        if STATIC_INDEX_BOOTSTRAP_PLACEHOLDER not in html:
            if logger is not None:
                logger.error("local API index render failed: bootstrap placeholder missing")
            return missing_bootstrap_placeholder_response()
        return StaticFileResponse(body=render_index_html(html, bootstrap), content_type="text/html; charset=utf-8")
    except Exception as exc:
        if logger is not None:
            logger.exception("local API index render failed")
        return static_error_response(exc)


def read_static_asset(
    static_root: Path,
    route: str,
    *,
    logger: logging.Logger | None = None,
) -> StaticFileResponse:
    path = resolve_asset_path(static_root, route)
    if path is None:
        return static_not_found_response()
    try:
        return StaticFileResponse(body=path.read_bytes(), content_type=content_type_for(path))
    except Exception as exc:
        if logger is not None:
            logger.exception("local API static asset read failed: %s", path)
        return static_error_response(exc)
