from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .handler_policy import bounded_error_text


STATIC_INDEX_BOOTSTRAP_PLACEHOLDER = "__MEDIA_PIPELINE_BOOTSTRAP__"
STATIC_INCLUDE_RE = re.compile(r"<!--\s*mp-include:\s*(?P<path>[-A-Za-z0-9_./]+)\s*-->")


@dataclass(frozen=True)
class StaticFileResponse:
    body: bytes
    status: int = 200
    content_type: str = "application/octet-stream"


def local_api_bootstrap(
    *,
    token: str,
    require_token: bool,
    app_version: str,
    shell_surface: str = "webview",
    startup_progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface = str(shell_surface or "webview")
    include_token = bool(require_token) and surface.casefold() != "tauri"
    payload = {
        "apiBase": "",
        "token": token if include_token else "",
        "appVersion": app_version,
        "shellSurface": surface,
    }
    if bool(require_token) and not include_token:
        payload["tokenSource"] = "tauri-initialization-script"
    if startup_progress is not None:
        payload["startupProgress"] = startup_progress
    return payload


def render_index_html(template: str, bootstrap: dict[str, Any]) -> bytes:
    html = template.replace(STATIC_INDEX_BOOTSTRAP_PLACEHOLDER, json.dumps(bootstrap, ensure_ascii=False))
    return html.encode("utf-8")


def render_static_includes(template: str, static_root: Path) -> str:
    root = Path(static_root).resolve()

    def include(match: re.Match[str]) -> str:
        include_name = match.group("path").strip()
        relative = PurePosixPath(include_name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe static include path: {include_name}")
        if not relative.parts or relative.parts[0] != "partials" or relative.suffix != ".html":
            raise ValueError(f"unsupported static include path: {include_name}")
        include_path = (root / Path(*relative.parts)).resolve()
        if root not in include_path.parents:
            raise ValueError(f"static include escaped root: {include_name}")
        if not include_path.is_file():
            raise FileNotFoundError(f"static include not found: {include_name}")
        return include_path.read_text(encoding="utf-8")

    return STATIC_INCLUDE_RE.sub(include, template)


def missing_index_response() -> StaticFileResponse:
    return StaticFileResponse(
        body=b"MediaPipeline local web assets are not installed.",
        status=404,
        content_type="text/plain; charset=utf-8",
    )


def missing_bootstrap_placeholder_response() -> StaticFileResponse:
    return StaticFileResponse(
        body=b"MediaPipeline local web index is missing the backend bootstrap placeholder.",
        status=500,
        content_type="text/plain; charset=utf-8",
    )


def static_not_found_response() -> StaticFileResponse:
    return StaticFileResponse(body=b"not found", status=404, content_type="text/plain; charset=utf-8")


def static_error_response(exc: Exception) -> StaticFileResponse:
    return StaticFileResponse(
        body=bounded_error_text(exc).encode("utf-8"),
        status=500,
        content_type="text/plain; charset=utf-8",
    )
