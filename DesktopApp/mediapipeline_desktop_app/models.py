from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Any

from .models_core import ConfigPreview, ConfigSaveResult, ResolvedPaths, Snapshot, TelemetrySnapshot
from .models_media_paths import (
    _derive_lookup_title_from_output_path,
    _derive_media_type_from_path,
    _derive_relative_media_path,
    _derive_tv_lookup_title,
    _ensure_aware,
    _is_season_only_lookup,
    _parse_iso_datetime,
    _split_path_segments,
)


def _decision_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


@dataclass
class AuditRecord:
    source_csv: Path
    row: dict[str, str]

    @property
    def path(self) -> Path | None:
        raw = self.row.get("Path", "").strip()
        return Path(raw) if raw else None

    @property
    def relative_path(self) -> str:
        return self.row.get("RelativePath", "").strip()

    @property
    def lookup_title(self) -> str:
        raw = self.row.get("LookupTitle", "").strip()
        if self.media_type == "TV" and (_is_season_only_lookup(raw) or not raw):
            derived = _derive_tv_lookup_title(str(self.path or self.relative_path))
            if derived:
                return derived
        return raw

    @property
    def media_type(self) -> str:
        return self.row.get("MediaType", "").strip()

    @property
    def effective_bucket(self) -> str:
        return self.row.get("EffectiveBucket", "").strip() or self.row.get("Bucket", "").strip()

    @property
    def priority_fix_level(self) -> str:
        return self.row.get("PriorityFixLevel", "").strip()

    @property
    def priority_score(self) -> int:
        raw = self.row.get("PriorityScore", "").strip()
        try:
            return int(float(raw))
        except ValueError:
            return 0

    @property
    def primary_issue_code(self) -> str:
        return self.row.get("PrimaryIssueCode", "").strip()

    @property
    def primary_suggested_action(self) -> str:
        return self.row.get("PrimarySuggestedAction", "").strip()

    @property
    def issue_messages(self) -> str:
        return self.row.get("IssueMessages", "").strip()

    @property
    def normalized_lookup_title(self) -> str:
        base = self.lookup_title.strip()
        if not base and self.path:
            base = self.path.stem
        if not base:
            base = self.relative_path
        normalized = base.casefold()
        normalized = re.sub(r"\((?:19|20)\d{2}\)", " ", normalized)
        normalized = re.sub(r"\bseason\s*\d{1,2}\b", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bs\d{1,2}\b", " ", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized


@dataclass
class QueueRecord:
    source_path: Path
    source_root: Path
    media_type: str
    is_priority: bool
    priority_reasons: list[str]
    priority_rank: float
    sort_name: str
    display_name: str
    relative_path: str
    show_folder: str
    season_folder: str
    season_number: int
    episode_number: int
    source_mtime: float
    size_gb: float
    route_name: str
    route_reason: str
    matched_show_override: str
    queue_index: int
    queue_total: int
    phase: str
    global_order: int
    # Manifest-based priority level: "high" | "normal" | "low" | "hold"
    # "normal" means no manifest entry (or entry explicitly set to normal).
    manifest_priority_level: str = "normal"

    @property
    def queue_position(self) -> str:
        return f"{self.queue_index}/{self.queue_total}"


@dataclass
class FailureRecord:
    source_json: Path
    payload: dict[str, Any]

    @property
    def source_path(self) -> Path | None:
        raw = str(self.payload.get("SourcePath", "") or "").strip()
        return Path(raw) if raw else None

    @property
    def source_path_text(self) -> str:
        return str(self.payload.get("SourcePath", "") or "").strip()

    @property
    def stage(self) -> str:
        return str(self.payload.get("Stage", "") or "").strip()

    @property
    def reason(self) -> str:
        return str(self.payload.get("Reason", "") or "").strip()

    @property
    def classification(self) -> str:
        return str(self.payload.get("Classification", "") or "").strip()

    @property
    def error_code(self) -> str:
        return str(self.payload.get("ErrorCode", "") or "").strip()

    @property
    def artifact_path(self) -> Path | None:
        raw = str(self.payload.get("ArtifactPath", "") or "").strip()
        return Path(raw) if raw else None

    @property
    def repro_path(self) -> Path | None:
        raw = str(self.payload.get("ReproPath", "") or "").strip()
        return Path(raw) if raw else None

    @property
    def suggested_action(self) -> str:
        return str(self.payload.get("SuggestedAction", "") or "").strip()

    @property
    def suggested_rename(self) -> str:
        return str(self.payload.get("SuggestedRename", "") or "").strip()

    @property
    def recorded_at(self) -> str:
        return str(self.payload.get("RecordedAt", "") or "").strip()

    @property
    def retry_count(self) -> int:
        raw = self.payload.get("RetryCount")
        try:
            return int(raw) if raw not in (None, "") else 0
        except (TypeError, ValueError):
            return 0

    @property
    def retry_limit(self) -> int:
        raw = self.payload.get("RetryLimit")
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
        parts = _split_path_segments(self.source_path_text)
        lower_parts = [part.casefold() for part in parts]
        try:
            if "movies" in lower_parts:
                index = lower_parts.index("movies")
                if index + 1 < len(parts):
                    return parts[index + 1]
            if "tv" in lower_parts:
                derived = _derive_tv_lookup_title(self.source_path_text)
                if derived:
                    return derived
        except Exception:
            pass
        return path.stem

    def _path_segments(self) -> list[str]:
        return [segment.casefold() for segment in _split_path_segments(self.source_path_text)]


@dataclass
class CompletedJobRecord:
    sidecar_path: Path
    payload: dict[str, Any]

    @property
    def source_path_text(self) -> str:
        return str(self.payload.get("source_path", "") or "").strip()

    @property
    def source_path(self) -> Path | None:
        raw = self.source_path_text
        return Path(raw) if raw else None

    @property
    def source_identity_v2(self) -> str:
        return str(self.payload.get("source_identity_v2", "") or "").strip()

    @property
    def output_path(self) -> Path:
        raw = str(self.payload.get("output_path", "") or "").strip()
        if raw:
            return Path(raw)
        raw_file = str(self.payload.get("output_file", "") or "").strip()
        if raw_file:
            return self.sidecar_path.parent / raw_file
        leaf = self.sidecar_path.name
        if leaf.endswith(".pipeline.json"):
            base = leaf[: -len(".pipeline.json")]
            return self.sidecar_path.with_name(base)
        return self.sidecar_path

    @property
    def output_exists(self) -> bool:
        cached = self.payload.get("_diagnostics_output_exists")
        if isinstance(cached, bool):
            return cached
        with contextlib.suppress(Exception):
            return self.output_path.exists()
        return False

    @property
    def output_health(self) -> str:
        return str(self.payload.get("_diagnostics_output_health", "") or "").strip()

    @property
    def audio_decisions(self) -> list[dict[str, Any]]:
        return _decision_records(self.payload.get("audio_decisions"))

    @property
    def subtitle_decisions(self) -> list[dict[str, Any]]:
        return _decision_records(self.payload.get("subtitle_decisions"))

    @property
    def encode_selected_encoder(self) -> str:
        return str(self.payload.get("encode_selected_encoder", "") or "").strip()

    @property
    def encode_selected_encoder_kind(self) -> str:
        return str(self.payload.get("encode_selected_encoder_kind", "") or "").strip()

    @property
    def encode_selected_gpu_device(self) -> str:
        return str(self.payload.get("encode_selected_gpu_device", "") or "").strip()

    @property
    def output_file(self) -> str:
        return self.output_path.name

    @property
    def completed_at(self) -> datetime | None:
        """Always returns a timezone-aware datetime, or None.

        The pipeline historically wrote ``encoded_at`` in two formats:
        tz-aware ISO (``2026-04-23T08:57:51.168-04:00``) and naive US
        (``04/24/2026 08:20:32``). Mixing those in ``sorted()`` raises
        ``TypeError: can't compare offset-naive and offset-aware``, which
        silently aborts the completed-jobs tree render. Normalizing here
        fixes every downstream comparison — naive values are assumed to
        be local time.
        """
        parsed = _parse_iso_datetime(str(self.payload.get("encoded_at", "") or ""))
        if parsed is not None:
            return _ensure_aware(parsed)
        # Fallback: use the sidecar file's mtime. This is skipped for UNC
        # (network) paths to avoid blocking backend refreshes with a remote stat;
        # those records will safely return None and sort to the oldest end of
        # the table.
        sidecar_str = str(self.sidecar_path)
        if sidecar_str.startswith("\\\\") or sidecar_str.startswith("//"):
            return None
        with contextlib.suppress(Exception):
            ts = datetime.fromtimestamp(self.sidecar_path.stat().st_mtime)
            return _ensure_aware(ts)
        return None

    @property
    def completed_at_text(self) -> str:
        value = self.completed_at
        if not value:
            return "Unknown"
        day = str(value.day)
        hour = value.strftime("%I").lstrip("0") or "12"
        return value.strftime(f"%b {day} {hour}:%M %p")

    @property
    def route(self) -> str:
        return str(self.payload.get("route", "") or "").strip().lower()

    @property
    def route_label(self) -> str:
        mapping = {
            "remux": "REMUX",
            "encode": "ENCODE",
            "encode-cpu-fallback": "ENCODE (CPU)",
        }
        return mapping.get(self.route, self.route.upper() if self.route else "UNKNOWN")

    @property
    def elapsed_seconds(self) -> float | None:
        raw = self.payload.get("elapsed_seconds")
        try:
            if raw in (None, ""):
                return None
            return float(raw)
        except (TypeError, ValueError):
            return None

    @property
    def elapsed_text(self) -> str:
        seconds = self.elapsed_seconds
        if seconds is None:
            return "Unavailable"
        total_seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {secs}s"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    @property
    def publish_state(self) -> str:
        raw = str(self.payload.get("publish_state", "") or "").strip().lower()
        return raw or "published"

    @property
    def publish_mode(self) -> str:
        raw = str(self.payload.get("publish_mode", "") or "").strip().lower()
        return raw or "immediate"

    @property
    def publish_label(self) -> str:
        mode_labels = {
            "immediate": "Published",
            "deferred": "Published (Deferred)",
            "retry": "Published (Retry)",
        }
        if self.publish_state != "published":
            return self.publish_state.replace("-", " ").title()
        return mode_labels.get(self.publish_mode, f"Published ({self.publish_mode})")

    @property
    def source_size_bytes(self) -> int | None:
        raw = self.payload.get("source_size")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def output_size_bytes(self) -> int | None:
        raw = self.payload.get("output_size")
        try:
            if raw is not None:
                return int(raw)
        except (TypeError, ValueError):
            pass
        with contextlib.suppress(Exception):
            path = self.output_path
            if path.exists():
                return path.stat().st_size
        return None

    @property
    def size_reduction_pct(self) -> float | None:
        src = self.source_size_bytes
        out = self.output_size_bytes
        if src and out and src > 0:
            return (1.0 - out / src) * 100.0
        return None

    @property
    def size_reduction_text(self) -> str:
        pct = self.size_reduction_pct
        if pct is None:
            return ""
        src = self.source_size_bytes or 0
        out = self.output_size_bytes or 0
        src_gb = src / (1024 ** 3)
        out_gb = out / (1024 ** 3)
        return f"{pct:+.1f}%  ({src_gb:.2f} → {out_gb:.2f} GB)"

    @property
    def media_type(self) -> str:
        # Pipelines from this version forward stamp `media_type` directly
        # on the sidecar (and therefore on completed_jobs.jsonl entries)
        # so the Completed tab doesn't have to guess from the output
        # path. Older sidecars predate that field; fall back to the path
        # heuristic which now also recognizes "Season XX" parents,
        # SxxEyy filenames, and "(YYYY)" movie folders.
        raw = str(self.payload.get("media_type") or "").strip().lower()
        if raw == "tv":
            return "TV"
        if raw in ("movie", "movies"):
            return "Movie"
        return _derive_media_type_from_path(str(self.output_path))

    @property
    def lookup_title(self) -> str:
        derived = _derive_lookup_title_from_output_path(str(self.output_path))
        if derived:
            return derived
        return self.output_path.stem

    @property
    def relative_path(self) -> str:
        return _derive_relative_media_path(str(self.output_path))
