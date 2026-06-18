from __future__ import annotations

from collections.abc import Iterable
import logging

from .registry import normalize_source_identity

_log = logging.getLogger(__name__)


def source_has_prior_failure(source_path: str, failure_records: Iterable[object]) -> bool:
    source_key = normalize_source_identity(source_path)
    for record in failure_records:
        try:
            failed_source = normalize_source_identity(getattr(record, "source_path_text", "") or "")
            if failed_source and failed_source == source_key:
                return True
        except Exception as exc:
            _log.warning("Could not inspect prior failure record for source %s: %s", source_path, exc)
    return False
