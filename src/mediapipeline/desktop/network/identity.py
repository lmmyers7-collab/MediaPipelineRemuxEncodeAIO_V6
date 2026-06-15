from __future__ import annotations

import re
from typing import Any

# Worker identifiers must be small printable strings. UUIDs are 36 chars
# (8-4-4-4-12 with dashes); the extra headroom covers machine_id variants.
WORKER_ID_MAX_LEN = 64
WORKER_NAME_MAX_LEN = 80
WORKER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._\-]+$")
WORKER_NAME_PATTERN = re.compile(r"^[\w .,:\-_/\\()@'\"]+$", re.UNICODE)
WORKER_NAME_DISALLOWED_PATTERN = re.compile(r"[^\w .,:\-_/\\()@'\"]", re.UNICODE)
LOG_DISPLAY_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]+")
LOG_DISPLAY_SPACES_PATTERN = re.compile(r" {2,}")

LOG_EVENT_MAX_LEN = 64
LOG_MESSAGE_MAX_LEN = 4096
LOG_MESSAGE_TRUNCATION_SUFFIX = "…[truncated]"


def is_valid_worker_id(value: str) -> bool:
    worker_id = str(value or "")
    return len(worker_id) <= WORKER_ID_MAX_LEN and bool(WORKER_ID_PATTERN.match(worker_id))


def coerce_worker_name(raw_name: str, worker_id: str) -> str:
    fallback = str(worker_id or "")[:8]
    worker_name = str(raw_name or fallback).strip() or fallback
    if len(worker_name) > WORKER_NAME_MAX_LEN:
        worker_name = worker_name[:WORKER_NAME_MAX_LEN]
    if not WORKER_NAME_PATTERN.match(worker_name):
        worker_name = WORKER_NAME_DISALLOWED_PATTERN.sub("_", worker_name) or fallback
    return worker_name


def sanitize_log_display_text(value: Any, max_len: int | None = None) -> str:
    text = str(value or "")
    if max_len is not None and len(text) > max_len:
        text = text[:max_len]
    text = LOG_DISPLAY_CONTROL_PATTERN.sub(" ", text)
    return LOG_DISPLAY_SPACES_PATTERN.sub(" ", text).strip()


def sanitize_log_entry_fields(entry: Any) -> Any:
    if getattr(entry, "worker_id", "") and not is_valid_worker_id(entry.worker_id):
        entry.worker_id = ""
    entry.worker_name = sanitize_log_display_text(getattr(entry, "worker_name", ""), WORKER_NAME_MAX_LEN)
    entry.role = sanitize_log_display_text(getattr(entry, "role", ""), 32)
    entry.level = sanitize_log_display_text(getattr(entry, "level", ""), 16)
    entry.timestamp = sanitize_log_display_text(getattr(entry, "timestamp", ""), 80)
    entry.source_path = sanitize_log_display_text(getattr(entry, "source_path", ""), 4096)
    if getattr(entry, "job_id", "") and not is_valid_worker_id(entry.job_id):
        entry.job_id = ""
    entry.event = sanitize_log_display_text(getattr(entry, "event", ""), LOG_EVENT_MAX_LEN)
    message = sanitize_log_display_text(getattr(entry, "message", ""), LOG_MESSAGE_MAX_LEN)
    if len(getattr(entry, "message", "") or "") > LOG_MESSAGE_MAX_LEN:
        message += LOG_MESSAGE_TRUNCATION_SUFFIX
    entry.message = message
    return entry
