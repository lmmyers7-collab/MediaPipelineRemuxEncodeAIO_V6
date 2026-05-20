from __future__ import annotations

import urllib.parse


def validate_coordinator_url(raw: str) -> str:
    """Validate and normalize a worker coordinator base URL."""
    url = (raw or "").strip().rstrip("/")
    if not url:
        raise ValueError(
            "WorkerCoordinatorUrl is empty. Enter the coordinator's base "
            "URL (e.g. http://192.168.1.10:7830) in Settings > Network."
        )
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"WorkerCoordinatorUrl must start with http:// or https:// "
            f"(got {parsed.scheme or '(no scheme)'})."
        )
    if not parsed.hostname:
        raise ValueError(f"WorkerCoordinatorUrl is missing a host (got {url!r}).")
    if parsed.path and parsed.path not in ("", "/"):
        raise ValueError(
            f"WorkerCoordinatorUrl must be the coordinator base URL only "
            f"(no path component); got {url!r}."
        )
    if parsed.query or parsed.fragment:
        raise ValueError("WorkerCoordinatorUrl must not include a query string or fragment.")
    if parsed.username or parsed.password:
        raise ValueError(
            "WorkerCoordinatorUrl must not embed userinfo "
            "(use the bearer token in WorkerAuthToken instead)."
        )
    return url
