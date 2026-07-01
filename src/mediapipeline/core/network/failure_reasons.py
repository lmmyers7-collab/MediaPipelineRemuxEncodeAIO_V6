"""Structured failure reason helpers for network worker completion reports."""

from __future__ import annotations

import re
from typing import Any


REASON_SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
REASON_OUTPUT_UNWRITABLE = "OUTPUT_UNWRITABLE"
REASON_AUTH = "AUTH"
REASON_TIMEOUT = "TIMEOUT"
REASON_ENCODE_ERROR = "ENCODE_ERROR"
REASON_WORKER_CRASH = "WORKER_CRASH"

KNOWN_REASON_CODES = {
    REASON_SOURCE_NOT_FOUND,
    REASON_OUTPUT_UNWRITABLE,
    REASON_AUTH,
    REASON_TIMEOUT,
    REASON_ENCODE_ERROR,
    REASON_WORKER_CRASH,
}

_CODE_PATTERN = re.compile(r"[^A-Z0-9_]+")


def bounded_failure_reason(value: Any, *, limit: int = 500) -> str:
    """Return a single-line reason detail bounded for wire/state payloads."""
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def normalize_failure_reason_code(value: Any) -> str:
    """Return a known reason code or an empty string for unknown input."""
    code = _CODE_PATTERN.sub("_", str(value or "").strip().upper()).strip("_")
    return code if code in KNOWN_REASON_CODES else ""


def classify_failure_reason(
    *,
    success: bool,
    reason_code: Any = "",
    reason: Any = "",
    error_message: Any = "",
    completion_status: Any = "",
    source_path: Any = "",
    output_path: Any = "",
    route: Any = "",
) -> tuple[str, str]:
    """Classify a failed worker outcome into a bounded reason code/detail.

    This classifier is intentionally conservative: it does not alter retry
    policy, and unrecognized failures stay in the generic ENCODE_ERROR bucket.
    """
    if success:
        return "", ""

    detail = bounded_failure_reason(
        reason or error_message or completion_status or "Worker failed without detail."
    )
    explicit_code = normalize_failure_reason_code(reason_code)
    if explicit_code:
        return explicit_code, detail

    text = " ".join(
        str(part or "")
        for part in (error_message, completion_status, source_path, output_path, route)
    ).lower()

    if any(
        needle in text
        for needle in (
            "401",
            "403",
            "auth",
            "unauthorized",
            "forbidden",
            "invalid token",
            "hmac",
            "signature",
        )
    ):
        return REASON_AUTH, detail

    if any(
        needle in text
        for needle in (
            "timeout",
            "timed out",
            "winerror 10060",
            "connection aborted",
            "connection reset",
            "read timed out",
        )
    ):
        return REASON_TIMEOUT, detail

    if any(
        needle in text
        for needle in (
            "source not found",
            "input not found",
            "not found on worker",
            "no such file",
            "cannot find the file",
            "file not found",
            "does not exist",
            "unable to open input",
        )
    ):
        return REASON_SOURCE_NOT_FOUND, detail

    if any(
        needle in text
        for needle in (
            "output unwritable",
            "destination unwritable",
            "cannot write",
            "write failed",
            "permission denied",
            "access denied",
            "no space left",
            "disk full",
            "read-only file system",
            "failed to publish",
        )
    ):
        return REASON_OUTPUT_UNWRITABLE, detail

    return REASON_ENCODE_ERROR, detail


__all__ = [
    "KNOWN_REASON_CODES",
    "REASON_AUTH",
    "REASON_ENCODE_ERROR",
    "REASON_OUTPUT_UNWRITABLE",
    "REASON_SOURCE_NOT_FOUND",
    "REASON_TIMEOUT",
    "REASON_WORKER_CRASH",
    "bounded_failure_reason",
    "classify_failure_reason",
    "normalize_failure_reason_code",
]
