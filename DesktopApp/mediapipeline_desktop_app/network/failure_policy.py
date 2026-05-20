from __future__ import annotations

from collections.abc import Iterable
import logging


_log = logging.getLogger(__name__)


def source_has_prior_failure(source_path: str, failure_records: Iterable[object]) -> bool:
    source_key = str(source_path or "").casefold()
    for record in failure_records:
        try:
            failed_source = str(getattr(record, "source_path_text", "") or "").casefold()
            if failed_source and failed_source == source_key:
                return True
        except Exception as exc:
            _log.warning("Could not inspect prior failure record for source %s: %s", source_path, exc)
    return False
