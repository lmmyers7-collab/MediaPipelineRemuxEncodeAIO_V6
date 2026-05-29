"""Structured JSON logging helpers for new Python paths."""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Mapping, MutableMapping
from datetime import datetime, timezone
from typing import Any, TextIO

REDACTED = "[redacted]"
SECRET_FRAGMENTS = ("token", "secret", "password", "credential", "authorization")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): (REDACTED if _is_secret_key(str(key)) else _redact(item)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def _is_secret_key(key: str) -> bool:
    folded = key.casefold()
    return any(fragment in folded for fragment in SECRET_FRAGMENTS)


def _exception_payload(record: logging.LogRecord) -> dict[str, Any] | None:
    if not record.exc_info:
        return None
    exc_type, exc, tb = record.exc_info
    return {
        "type": exc_type.__name__ if exc_type is not None else "",
        "message": str(exc or ""),
        "traceback": "".join(traceback.format_exception(exc_type, exc, tb))[-4000:],
    }


class JsonLineFormatter(logging.Formatter):
    """Render log records as one strict JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        event = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": _utc_now(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": event,
            "run_id": str(getattr(record, "run_id", "") or ""),
            "command_id": str(getattr(record, "command_id", "") or ""),
            "stage": str(getattr(record, "stage", "") or ""),
            "source": str(getattr(record, "source", "") or "python"),
        }
        structured = getattr(record, "structured", None)
        if isinstance(structured, dict):
            payload.update(_redact(structured))
        error = _exception_payload(record)
        if error is not None:
            payload["error"] = _redact(error)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str)


class RunContextAdapter(logging.LoggerAdapter[Any]):
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        extra = dict(kwargs.get("extra") or {})
        merged = dict(self.extra) if isinstance(self.extra, Mapping) else {}
        merged.update(extra)
        kwargs["extra"] = merged
        return msg, kwargs


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def bind_run_context(
    logger: logging.Logger,
    *,
    run_id: str = "",
    command_id: str = "",
    stage: str = "",
) -> RunContextAdapter:
    return RunContextAdapter(
        logger,
        {
            "run_id": run_id,
            "command_id": command_id,
            "stage": stage,
            "source": "python",
        },
    )


def configure_json_logging(
    stream: TextIO,
    *,
    level: int = logging.INFO,
    logger_name: str | None = None,
) -> logging.Handler:
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(JsonLineFormatter())
    target = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    target.setLevel(level)
    target.addHandler(handler)
    return handler


__all__ = [
    "JsonLineFormatter",
    "RunContextAdapter",
    "get_logger",
    "bind_run_context",
    "configure_json_logging",
]
