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


def sanitize_log_entry_fields(entry: Any) -> Any:
    if getattr(entry, "worker_id", "") and not is_valid_worker_id(entry.worker_id):
        entry.worker_id = ""
    if getattr(entry, "worker_name", "") and len(entry.worker_name) > WORKER_NAME_MAX_LEN:
        entry.worker_name = entry.worker_name[:WORKER_NAME_MAX_LEN]
    if getattr(entry, "job_id", "") and not is_valid_worker_id(entry.job_id):
        entry.job_id = ""
    if len(getattr(entry, "event", "") or "") > LOG_EVENT_MAX_LEN:
        entry.event = entry.event[:LOG_EVENT_MAX_LEN]
    if len(getattr(entry, "message", "") or "") > LOG_MESSAGE_MAX_LEN:
        entry.message = entry.message[:LOG_MESSAGE_MAX_LEN] + LOG_MESSAGE_TRUNCATION_SUFFIX
    return entry
