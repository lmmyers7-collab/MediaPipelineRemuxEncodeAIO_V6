"""Audit and sample-run harness for the generated Tdarr Matrix test library."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from collections.abc import Iterable, Mapping, Sequence

from mediapipeline.tools.dev import materialize_tdarr_test_library as tdarr_matrix
from mediapipeline.tools.paths import find_repo_root
from mediapipeline.core.diagnostics.tdarr_matrix_proof import (
    tdarr_policy_proof_runs_root,
    tdarr_proof_pack_root,
    tdarr_proof_runs_root,
)


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_LIBRARY_ROOT = tdarr_proof_pack_root(REPO_ROOT)
DEFAULT_RUNS_ROOT = tdarr_proof_runs_root(REPO_ROOT)
DEFAULT_PIPELINE_ENTRYPOINT = REPO_ROOT / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1"
DEFAULT_TEMPLATE = tdarr_matrix.DEFAULT_TEMPLATE
CONFIG_NAME = tdarr_matrix.CONFIG_NAME
AUDIT_SCHEMA = "tdarr_matrix_audit.v1"
AUDIT_RUN_SENTINEL = ".tdarr-matrix-audit-run.json"
AUDIT_DIR_NAME = "audit"
DEFAULT_SAMPLES_PER_BUCKET = 5
DEFAULT_SAMPLE_TIMEOUT_SECONDS = 1800
DEFAULT_PREPARE_TIMEOUT_SECONDS = 1800
DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS = 30
BUCKET_ORDER = (
    "audio-only",
    "h264-h265-direct",
    "av1-vp-modern",
    "legacy-video",
    "mjpeg-large",
    "container-stress",
)
FAIL_SEVERITIES = {"critical", "error"}
MANIFEST_FIELDNAMES = [
    "schema_version",
    "view",
    "case_id",
    "diagnostic_bucket",
    "generated_path",
    "source_path",
    "original_name",
    "source_url",
    "source_page",
    "medium",
    "container",
    "resolution",
    "video_codec",
    "audio_codec",
    "duration",
    "advertised_size_mb",
    "actual_size_bytes",
    "sha256",
    "link_mode",
]
CONTAINMENT_PATH_KEYS = {
    "destination_path",
    "final_path",
    "final_output_path",
    "local_output_path",
    "local_path",
    "manifest_path",
    "output_path",
    "payload_path",
    "pending_path",
    "sidecar_path",
    "target_path",
}
SOURCE_PATH_KEYS = {"original_source_path", "source_file", "source_path"}
# G10: path-containment scans these evidence subtrees for absolute paths under
# CONTAINMENT_PATH_KEYS. Both sets must track the pipeline's evidence-writing code; if a new
# evidence location or path-bearing key is added there, extend these so escapes stay caught.
# test_path_containment_scans_all_declared_roots verifies every declared root is scanned.
CONTAINMENT_SCAN_SUBDIRS = (
    ("output",),
    ("scratch", "State", "Completed"),
    ("scratch", "State", "PendingServerPush"),
    ("scratch", "State", "Failures"),
)
AUDIO_ONLY_TOKENS = {"audio", "audio-only", "audioonly", "sound"}
NO_VIDEO_CODEC_TOKENS = {"", "none", "no-video", "novideo", "audio", "audio-only", "unknown"}
CONFIG_MISSING_KEY_PATTERN = re.compile(r"Config missing key:\s*([A-Za-z0-9_.-]+)", re.IGNORECASE)
WORKER_CHILD_GUARD_ERROR_CODES = {
    "WORKER_CHILD_SINGLE_FILE_EXCEPTION",
    "WORKER_CHILD_RESULT_FALLBACK",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def resolve_path(value: str | Path, *, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def path_key(path: str | Path) -> str:
    return str(Path(path).resolve(strict=False)).casefold()


def is_under(path: str | Path, root: str | Path) -> bool:
    try:
        Path(path).resolve(strict=False).relative_to(Path(root).resolve(strict=False))
        return True
    except ValueError:
        return False


def safe_manifest_relative_path(value: object, *, field_name: str) -> str:
    text = str(value or "").replace("\\", "/").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty relative path")
    windows_path = PureWindowsPath(text)
    if PurePosixPath(text).is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ValueError(f"{field_name} must be a relative path: {text}")
    if ".." in PurePosixPath(text).parts:
        raise ValueError(f"{field_name} must not contain parent traversal: {text}")
    return text


def contained_manifest_child(root: Path, value: object, *, field_name: str) -> tuple[str, Path]:
    relative_path = safe_manifest_relative_path(value, field_name=field_name)
    child = root / relative_path
    if not is_under(child, root):
        raise ValueError(f"{field_name} resolves outside {root}: {relative_path}")
    return relative_path, child


def int_value(value: object, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.=-]+", "-", value.strip()).strip("-")
    return slug or "item"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_default_powershell() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell"


@dataclass(frozen=True)
class ManifestRow:
    schema_version: str
    view: str
    case_id: str
    diagnostic_bucket: str
    library_root: Path
    generated_path: str
    generated_abs: Path
    source_path: Path
    original_name: str
    source_url: str
    source_page: str
    medium: str
    container: str
    resolution: str
    video_codec: str
    audio_codec: str
    duration: str
    advertised_size_mb: str
    actual_size_bytes: int
    sha256: str
    link_mode: str
    record: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: Mapping[str, object], *, library_root: Path) -> ManifestRow:
        library_root = library_root.resolve(strict=False)
        generated_path, generated_abs = contained_manifest_child(
            library_root,
            record.get("generated_path"),
            field_name="generated_path",
        )
        source_path = Path(str(record.get("source_path") or ""))
        copied = {field: str(record.get(field) or "") for field in MANIFEST_FIELDNAMES}
        copied["generated_path"] = generated_path
        return cls(
            schema_version=copied["schema_version"],
            view=copied["view"].strip().casefold(),
            case_id=copied["case_id"],
            diagnostic_bucket=copied["diagnostic_bucket"],
            library_root=library_root,
            generated_path=generated_path,
            generated_abs=generated_abs,
            source_path=source_path,
            original_name=copied["original_name"],
            source_url=copied["source_url"],
            source_page=copied["source_page"],
            medium=copied["medium"],
            container=copied["container"],
            resolution=copied["resolution"],
            video_codec=copied["video_codec"],
            audio_codec=copied["audio_codec"],
            duration=copied["duration"],
            advertised_size_mb=copied["advertised_size_mb"],
            actual_size_bytes=int_value(copied["actual_size_bytes"]),
            sha256=copied["sha256"].strip().casefold(),
            link_mode=copied["link_mode"],
            record=copied,
        )

    def manifest_record(self) -> dict[str, str]:
        record = dict(self.record)
        record["generated_path"] = self.generated_path
        record["source_path"] = str(self.source_path)
        record["actual_size_bytes"] = str(self.actual_size_bytes)
        record["sha256"] = self.sha256
        return record


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    case_id: str = ""
    view: str = ""
    diagnostic_bucket: str = ""
    generated_path: str = ""
    source_path: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "case_id": self.case_id,
            "view": self.view,
            "diagnostic_bucket": self.diagnostic_bucket,
            "generated_path": self.generated_path,
            "source_path": self.source_path,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class ProcessOutcome:
    command: list[str]
    returncode: int | None
    timed_out: bool
    duration_seconds: float
    stdout_path: Path
    stderr_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "duration_seconds": round(self.duration_seconds, 3),
            "stdout_path": str(self.stdout_path),
            "stderr_path": str(self.stderr_path),
        }


@dataclass(frozen=True)
class FixtureProbeResult:
    expected_video: bool
    probe_ok: bool
    has_video: bool
    format_name: str = ""
    streams: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    error: str = ""
    stderr: str = ""

    @property
    def excludes_auto_selection(self) -> bool:
        return self.expected_video and not self.has_video and self.error != "ffprobe_unavailable"


def finding_for_row(row: ManifestRow, *, severity: str, code: str, message: str, evidence: Mapping[str, Any] | None = None) -> Finding:
    return Finding(
        severity=severity,
        code=code,
        message=message,
        case_id=row.case_id,
        view=row.view,
        diagnostic_bucket=row.diagnostic_bucket,
        generated_path=row.generated_path,
        source_path=str(row.source_path),
        evidence=evidence or {},
    )


def load_manifest_rows(manifest_path: Path, *, library_root: Path) -> list[ManifestRow]:
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        return [ManifestRow.from_record(row, library_root=library_root) for row in csv.DictReader(handle)]


def write_materialized_manifest(library_root: Path, rows: Sequence[ManifestRow], *, link_mode: str = "hardlink") -> None:
    manifest_dir = library_root / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for row in rows:
        record = row.manifest_record()
        record["link_mode"] = link_mode
        records.append(record)
    with (manifest_dir / "materialized_library.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)
    payload = {
        "schema_version": tdarr_matrix.MANIFEST_SCHEMA,
        "generated_at_utc": utc_now(),
        "library_root": str(library_root),
        "link_mode": link_mode,
        "count": len(records),
        "files": records,
    }
    (manifest_dir / "materialized_library.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def spread_select(rows: Sequence[ManifestRow], count: int) -> list[ManifestRow]:
    if count <= 0 or not rows:
        return []
    if len(rows) <= count:
        return list(rows)
    if count == 1:
        return [rows[0]]
    positions = [round(index * (len(rows) - 1) / (count - 1)) for index in range(count)]
    selected: list[ManifestRow] = []
    seen: set[int] = set()
    for position in positions:
        if position not in seen:
            selected.append(rows[position])
            seen.add(position)
    cursor = 0
    while len(selected) < count and cursor < len(rows):
        if cursor not in seen:
            selected.append(rows[cursor])
            seen.add(cursor)
        cursor += 1
    return selected[:count]


def sample_sort_key(row: ManifestRow) -> tuple[int, str, str, str]:
    return (row.actual_size_bytes, row.case_id, row.view, row.generated_path.casefold())


def select_bucket_sample_rows(bucket_rows: Sequence[ManifestRow], *, samples_per_bucket: int = DEFAULT_SAMPLES_PER_BUCKET) -> list[ManifestRow]:
    bucket_selected = spread_select(bucket_rows, samples_per_bucket)
    selected_keys = {row.generated_path for row in bucket_selected}
    available_views = {row.view for row in bucket_rows}
    missing_views = [view for view in ("movies", "tv") if view in available_views and view not in {row.view for row in bucket_selected}]
    for view in missing_views:
        replacement = spread_select([row for row in bucket_rows if row.view == view], 1)
        if not replacement:
            continue
        candidate = replacement[0]
        if candidate.generated_path in selected_keys:
            continue
        replace_index = len(bucket_selected) - 1
        while replace_index >= 0 and bucket_selected[replace_index].view in missing_views:
            replace_index -= 1
        if replace_index < 0:
            replace_index = len(bucket_selected) - 1
        bucket_selected[replace_index] = candidate
        selected_keys = {row.generated_path for row in bucket_selected}
    return sorted(bucket_selected, key=sample_sort_key)


def select_sample_rows(rows: Sequence[ManifestRow], *, samples_per_bucket: int = DEFAULT_SAMPLES_PER_BUCKET) -> list[ManifestRow]:
    selected: list[ManifestRow] = []
    for bucket in BUCKET_ORDER:
        bucket_rows = sorted((row for row in rows if row.diagnostic_bucket == bucket), key=sample_sort_key)
        selected.extend(select_bucket_sample_rows(bucket_rows, samples_per_bucket=samples_per_bucket))
    return selected


def codec_container_key(row: ManifestRow) -> tuple[str, str]:
    """Return the explicit codec/container axis hidden by bucket-first selection."""
    return normalized_token(row.video_codec) or "no-video", normalized_token(row.container) or "unknown-container"


def select_balanced_sample_rows(rows: Sequence[ManifestRow], *, samples_per_bucket: int = DEFAULT_SAMPLES_PER_BUCKET) -> list[ManifestRow]:
    """Keep one row for every available codec/container pair before filling bucket quotas.

    Container-stress intentionally owns AVI/MOV/WMV/MP2 inputs, but the old five-per-bucket
    selection could silently represent only one codec inside that bucket.  This selector keeps
    the existing bucket ordering and deterministic sort while making the hidden cross-product
    visible.  A bucket may therefore exceed ``samples_per_bucket`` when it has more distinct
    codec/container pairs than its quota.
    """
    selected: list[ManifestRow] = []
    for bucket in BUCKET_ORDER:
        bucket_rows = sorted((row for row in rows if row.diagnostic_bucket == bucket), key=sample_sort_key)
        represented: set[tuple[str, str]] = set()
        bucket_selected: list[ManifestRow] = []
        for row in bucket_rows:
            key = codec_container_key(row)
            if key not in represented:
                represented.add(key)
                bucket_selected.append(row)
        quota = max(samples_per_bucket, len(bucket_selected))
        selected_keys = {manifest_case_key(row) for row in bucket_selected}
        for row in select_bucket_sample_rows(bucket_rows, samples_per_bucket=quota):
            if manifest_case_key(row) not in selected_keys:
                bucket_selected.append(row)
                selected_keys.add(manifest_case_key(row))
        selected.extend(sorted(bucket_selected, key=sample_sort_key))
    return selected


def select_all_sample_rows(rows: Sequence[ManifestRow]) -> list[ManifestRow]:
    bucket_index = {bucket: index for index, bucket in enumerate(BUCKET_ORDER)}
    return sorted(
        rows,
        key=lambda row: (
            bucket_index.get(row.diagnostic_bucket, len(BUCKET_ORDER)),
            *sample_sort_key(row),
        ),
    )


def manifest_case_key(row: ManifestRow) -> str:
    return f"{row.case_id}:{row.view}"


def normalized_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().casefold()).strip("-")


def manifest_row_declares_video(row: ManifestRow) -> bool:
    medium = normalized_token(row.medium)
    bucket = normalized_token(row.diagnostic_bucket)
    video_codec = normalized_token(row.video_codec)
    if medium in AUDIO_ONLY_TOKENS or bucket == "audio-only":
        return False
    if video_codec in NO_VIDEO_CODEC_TOKENS:
        return False
    return medium == "video" or bool(video_codec)


def ffprobe_command_available(ffprobe: str) -> bool:
    ffprobe_text = str(ffprobe or "").strip()
    if not ffprobe_text:
        return False
    ffprobe_path = Path(ffprobe_text)
    if ffprobe_path.is_absolute() or any(separator in ffprobe_text for separator in ("/", "\\")):
        return ffprobe_path.exists()
    return shutil.which(ffprobe_text) is not None


def summarize_probe_stream(stream: Mapping[str, Any]) -> dict[str, Any]:
    disposition_value = stream.get("disposition")
    disposition = disposition_value if isinstance(disposition_value, dict) else {}
    summary: dict[str, Any] = {
        "index": stream.get("index"),
        "codec_type": stream.get("codec_type"),
        "codec_name": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "attached_pic": disposition.get("attached_pic"),
    }
    return {key: value for key, value in summary.items() if value not in (None, "")}


def has_usable_video_stream(streams: Sequence[Mapping[str, Any]]) -> bool:
    for stream in streams:
        if str(stream.get("codec_type") or "").casefold() != "video":
            continue
        disposition_value = stream.get("disposition")
        disposition = disposition_value if isinstance(disposition_value, dict) else {}
        if str(disposition.get("attached_pic") or "0").casefold() in {"1", "true"}:
            continue
        return True
    return False


def probe_fixture_row(
    row: ManifestRow,
    *,
    ffprobe: str,
    timeout_seconds: int = DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS,
) -> FixtureProbeResult:
    expected_video = manifest_row_declares_video(row)
    if not expected_video:
        return FixtureProbeResult(expected_video=False, probe_ok=True, has_video=False)
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(row.generated_abs),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
    except FileNotFoundError:
        return FixtureProbeResult(expected_video=True, probe_ok=False, has_video=False, error="ffprobe_unavailable")
    except subprocess.TimeoutExpired as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return FixtureProbeResult(expected_video=True, probe_ok=False, has_video=False, error="ffprobe_timeout", stderr=stderr[:1000])

    stderr = str(completed.stderr or "").strip()
    if completed.returncode != 0:
        return FixtureProbeResult(expected_video=True, probe_ok=False, has_video=False, error="ffprobe_failed", stderr=stderr[:1000])
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        return FixtureProbeResult(expected_video=True, probe_ok=False, has_video=False, error="ffprobe_json_invalid", stderr=str(exc))
    raw_streams = [stream for stream in payload.get("streams", []) if isinstance(stream, dict)]
    streams = tuple(summarize_probe_stream(stream) for stream in raw_streams)
    format_value = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    return FixtureProbeResult(
        expected_video=True,
        probe_ok=True,
        has_video=has_usable_video_stream(raw_streams),
        format_name=str(format_value.get("format_name") or ""),
        streams=streams,
        stderr=stderr[:1000],
    )


def fixture_probe_evidence(row: ManifestRow, result: FixtureProbeResult) -> dict[str, Any]:
    return {
        "classification": "fixture_metadata_no_usable_video",
        "expected_negative": True,
        "strict_gate_effect": "warning_only",
        "manifest_medium": row.medium,
        "manifest_container": row.container,
        "manifest_video_codec": row.video_codec,
        "manifest_audio_codec": row.audio_codec,
        "format_name": result.format_name,
        "streams": list(result.streams),
        "probe_error": result.error,
        "stderr": result.stderr,
    }


def fixture_probe_mismatch_finding(row: ManifestRow, result: FixtureProbeResult) -> Finding:
    return finding_for_row(
        row,
        severity="warning",
        code="fixture_probe_mismatch",
        message=(
            "Tdarr fixture manifest says this case is video, but ffprobe found no usable "
            "video stream; treating it as an expected-negative fixture inventory mismatch."
        ),
        evidence=fixture_probe_evidence(row, result),
    )


def fixture_probe_unavailable_finding(ffprobe: str, video_manifest_rows: int) -> Finding:
    return Finding(
        severity="warning",
        code="fixture_probe_unavailable",
        message="ffprobe was not available; Tdarr fixture probe filtering was skipped.",
        evidence={"ffprobe": ffprobe, "video_manifest_rows": video_manifest_rows},
    )


def audit_fixture_video_probes(
    rows: Sequence[ManifestRow],
    *,
    ffprobe: str,
    timeout_seconds: int = DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS,
) -> tuple[dict[str, FixtureProbeResult], list[Finding]]:
    expected_rows = [row for row in rows if manifest_row_declares_video(row)]
    if not expected_rows:
        return {}, []
    if not ffprobe_command_available(ffprobe):
        return {}, [fixture_probe_unavailable_finding(ffprobe, len(expected_rows))]

    results: dict[str, FixtureProbeResult] = {}
    findings: list[Finding] = []
    for row in expected_rows:
        result = probe_fixture_row(row, ffprobe=ffprobe, timeout_seconds=timeout_seconds)
        results[manifest_case_key(row)] = result
        if result.error == "ffprobe_unavailable":
            findings.append(
                Finding(
                    severity="warning",
                    code="fixture_probe_unavailable",
                    message="ffprobe became unavailable; Tdarr fixture probe filtering was incomplete.",
                    evidence={"ffprobe": ffprobe, "case_key": manifest_case_key(row)},
                )
            )
            break
        if result.excludes_auto_selection:
            findings.append(fixture_probe_mismatch_finding(row, result))
    return results, findings


def filter_auto_sample_probe_mismatches(
    rows: Sequence[ManifestRow],
    probe_results: Mapping[str, FixtureProbeResult],
) -> list[ManifestRow]:
    return [
        row
        for row in rows
        if not probe_results.get(manifest_case_key(row), FixtureProbeResult(False, True, False)).excludes_auto_selection
    ]


def select_sample_rows_with_fixture_probe_filter(
    rows: Sequence[ManifestRow],
    *,
    samples_per_bucket: int,
    ffprobe: str,
    timeout_seconds: int = DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS,
) -> tuple[list[ManifestRow], list[Finding], dict[str, FixtureProbeResult]]:
    expected_count = sum(1 for row in rows if manifest_row_declares_video(row))
    if expected_count and not ffprobe_command_available(ffprobe):
        return select_sample_rows(rows, samples_per_bucket=samples_per_bucket), [fixture_probe_unavailable_finding(ffprobe, expected_count)], {}

    selected: list[ManifestRow] = []
    findings: list[Finding] = []
    probe_results: dict[str, FixtureProbeResult] = {}
    for bucket in BUCKET_ORDER:
        remaining = sorted((row for row in rows if row.diagnostic_bucket == bucket), key=sample_sort_key)
        while remaining:
            candidates = select_bucket_sample_rows(remaining, samples_per_bucket=samples_per_bucket)
            if not candidates:
                break
            candidate_results, candidate_findings = audit_fixture_video_probes(candidates, ffprobe=ffprobe, timeout_seconds=timeout_seconds)
            probe_results.update(candidate_results)
            findings.extend(candidate_findings)
            eligible_candidates = filter_auto_sample_probe_mismatches(candidates, candidate_results)
            if len(eligible_candidates) == len(candidates):
                selected.extend(candidates)
                break
            rejected_keys = {
                manifest_case_key(row)
                for row in candidates
                if candidate_results.get(manifest_case_key(row), FixtureProbeResult(False, True, False)).excludes_auto_selection
            }
            remaining = [row for row in remaining if manifest_case_key(row) not in rejected_keys]
    return selected, findings, probe_results


def select_case_key_rows(rows: Sequence[ManifestRow], case_keys: Sequence[str]) -> list[ManifestRow]:
    requested = [str(key or "").strip() for key in case_keys if str(key or "").strip()]
    requested_set = set(requested)
    by_key = {manifest_case_key(row): row for row in rows}
    selected: list[ManifestRow] = []
    missing: list[str] = []
    for key in requested:
        row = by_key.get(key)
        if row is None:
            missing.append(key)
            continue
        if manifest_case_key(row) not in {manifest_case_key(existing) for existing in selected}:
            selected.append(row)
    if missing:
        raise ValueError(f"Requested Tdarr Matrix case keys were not found in the manifest: {', '.join(missing)}")
    return [row for row in selected if manifest_case_key(row) in requested_set]




__all__ = [
    "AUDIO_ONLY_TOKENS",
    "AUDIT_DIR_NAME",
    "audit_fixture_video_probes",
    "AUDIT_RUN_SENTINEL",
    "AUDIT_SCHEMA",
    "BUCKET_ORDER",
    "codec_container_key",
    "CONFIG_MISSING_KEY_PATTERN",
    "CONFIG_NAME",
    "contained_manifest_child",
    "CONTAINMENT_PATH_KEYS",
    "CONTAINMENT_SCAN_SUBDIRS",
    "DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS",
    "DEFAULT_LIBRARY_ROOT",
    "DEFAULT_PIPELINE_ENTRYPOINT",
    "DEFAULT_PREPARE_TIMEOUT_SECONDS",
    "DEFAULT_RUNS_ROOT",
    "DEFAULT_SAMPLE_TIMEOUT_SECONDS",
    "DEFAULT_SAMPLES_PER_BUCKET",
    "DEFAULT_TEMPLATE",
    "FAIL_SEVERITIES",
    "ffprobe_command_available",
    "filter_auto_sample_probe_mismatches",
    "Finding",
    "finding_for_row",
    "fixture_probe_evidence",
    "fixture_probe_mismatch_finding",
    "fixture_probe_unavailable_finding",
    "FixtureProbeResult",
    "has_usable_video_stream",
    "int_value",
    "is_under",
    "load_manifest_rows",
    "manifest_case_key",
    "MANIFEST_FIELDNAMES",
    "manifest_row_declares_video",
    "ManifestRow",
    "NO_VIDEO_CODEC_TOKENS",
    "normalized_token",
    "path_key",
    "probe_fixture_row",
    "ProcessOutcome",
    "REPO_ROOT",
    "resolve_default_powershell",
    "resolve_path",
    "safe_manifest_relative_path",
    "safe_slug",
    "sample_sort_key",
    "select_all_sample_rows",
    "select_balanced_sample_rows",
    "select_bucket_sample_rows",
    "select_case_key_rows",
    "select_sample_rows",
    "select_sample_rows_with_fixture_probe_filter",
    "sha256_file",
    "SOURCE_PATH_KEYS",
    "spread_select",
    "summarize_probe_stream",
    "utc_now",
    "WORKER_CHILD_GUARD_ERROR_CODES",
    "write_materialized_manifest",
]
