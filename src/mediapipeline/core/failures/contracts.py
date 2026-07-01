from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.media_paths import (
    derive_tv_lookup_title,
    split_path_segments,
)


def _payload_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


@dataclass
class FailureRecord:
    source_json: Path
    payload: dict[str, Any]

    @property
    def source_path(self) -> Path | None:
        raw = self.source_path_text
        return Path(raw) if raw else None

    @property
    def source_path_text(self) -> str:
        return _payload_text(self.payload, "SourcePath", "source_path", "source_full_path")

    @property
    def stage(self) -> str:
        return _payload_text(self.payload, "Stage", "stage", "operation")

    @property
    def reason(self) -> str:
        return _payload_text(self.payload, "Reason", "reason", "Error", "error", "message")

    @property
    def classification(self) -> str:
        return _payload_text(self.payload, "Classification", "classification")

    @property
    def error_code(self) -> str:
        return _payload_text(self.payload, "ErrorCode", "error_code", "code")

    @property
    def artifact_path(self) -> Path | None:
        raw = _payload_text(self.payload, "ArtifactPath", "artifact_path")
        return Path(raw) if raw else None

    @property
    def repro_path(self) -> Path | None:
        raw = _payload_text(self.payload, "ReproPath", "ReproductionPath", "repro_path", "reproduction_path")
        return Path(raw) if raw else None

    @property
    def suggested_action(self) -> str:
        return _payload_text(self.payload, "SuggestedAction", "OperatorAction", "suggested_action", "operator_action")

    @property
    def suggested_rename(self) -> str:
        return _payload_text(self.payload, "SuggestedRename", "suggested_rename")

    @property
    def recorded_at(self) -> str:
        return _payload_text(self.payload, "RecordedAt", "recorded_at")

    @property
    def job_id(self) -> str:
        return _payload_text(self.payload, "JobId", "job_id")

    @property
    def correlation_id(self) -> str:
        return _payload_text(self.payload, "CorrelationId", "correlation_id")

    @property
    def retryable(self) -> bool | None:
        raw = self.payload.get("Retryable", self.payload.get("retryable"))
        if isinstance(raw, bool):
            return raw
        text = str(raw or "").strip().casefold()
        if not text:
            return None
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
        return None

    @property
    def retry_count(self) -> int:
        raw = self.payload.get("RetryCount", self.payload.get("retry_count"))
        try:
            return int(raw) if raw not in (None, "") else 0
        except (TypeError, ValueError):
            return 0

    @property
    def retry_limit(self) -> int:
        raw = self.payload.get("RetryLimit", self.payload.get("retry_limit"))
        try:
            return int(raw) if raw not in (None, "") else 0
        except (TypeError, ValueError):
            return 0

    @property
    def escalated(self) -> bool:
        raw = self.payload.get("Escalated")
        if isinstance(raw, bool):
            return raw
        return str(raw or "").strip().casefold() in {"true", "1", "yes"}

    @property
    def media_type(self) -> str:
        parts = self._path_segments()
        if "tv" in parts:
            return "TV"
        if "movies" in parts:
            return "Movie"
        return ""

    @property
    def lookup_title(self) -> str:
        path = self.source_path
        if not path:
            return ""
        parts = split_path_segments(self.source_path_text)
        lower_parts = [part.casefold() for part in parts]
        try:
            if "movies" in lower_parts:
                index = lower_parts.index("movies")
                if index + 1 < len(parts):
                    return parts[index + 1]
            if "tv" in lower_parts:
                derived = derive_tv_lookup_title(self.source_path_text)
                if derived:
                    return derived
        except Exception:
            pass
        return path.stem

    def _path_segments(self) -> list[str]:
        return [segment.casefold() for segment in split_path_segments(self.source_path_text)]
