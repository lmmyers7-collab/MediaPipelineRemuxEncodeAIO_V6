from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .json_policy import loads_strict_json


HTTP_TIMEOUT = 15
HTTP_MAX_RESPONSE_BYTES = 1 * 1024 * 1024
HTTP_JSON_ERROR_PREVIEW_BYTES = 500
RequestSigner = Callable[[str, str, bytes], Mapping[str, str]]


def http_read_capped(response: Any, max_bytes: int = HTTP_MAX_RESPONSE_BYTES) -> bytes:
    """Read a bounded response body, raising instead of silently truncating."""
    data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise RuntimeError(f"Coordinator response exceeds {max_bytes} bytes; refusing to parse.")
    return data


def _json_error_preview(body: bytes) -> str:
    return body[:HTTP_JSON_ERROR_PREVIEW_BYTES].decode("utf-8", errors="replace")


def _request_json(url: str, request: urllib.request.Request, *, timeout_seconds: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = http_read_capped(response)
            try:
                return loads_strict_json(body)
            except Exception as exc:
                preview = _json_error_preview(body)
                raise RuntimeError(f"Invalid JSON from {url}: {preview}") from exc
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = _json_error_preview(http_read_capped(exc))
        except Exception as body_exc:
            body = f"<failed to read error body: {body_exc}>"
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc


def http_get_json(
    base_url: str,
    path: str,
    *,
    headers: Mapping[str, str],
    params: Mapping[str, str] | None = None,
    sign_request: RequestSigner | None = None,
    timeout_seconds: int = HTTP_TIMEOUT,
) -> dict[str, Any]:
    path_with_query = path
    url = base_url + path_with_query
    if params:
        path_with_query += "?" + urllib.parse.urlencode(dict(params))
        url = base_url + path_with_query
    request_headers = dict(headers)
    if sign_request is not None:
        request_headers.update(dict(sign_request("GET", path_with_query, b"")))
    request = urllib.request.Request(url, headers=request_headers, method="GET")
    return _request_json(url, request, timeout_seconds=timeout_seconds)


def http_post_json(
    base_url: str,
    path: str,
    data: Mapping[str, Any],
    *,
    headers: Mapping[str, str],
    sign_request: RequestSigner | None = None,
    timeout_seconds: int = HTTP_TIMEOUT,
) -> dict[str, Any]:
    url = base_url + path
    payload = json.dumps(dict(data), allow_nan=False).encode()
    request_headers = dict(headers)
    if sign_request is not None:
        request_headers.update(dict(sign_request("POST", path, payload)))
    request = urllib.request.Request(url, data=payload, headers=request_headers, method="POST")
    return _request_json(url, request, timeout_seconds=timeout_seconds)
