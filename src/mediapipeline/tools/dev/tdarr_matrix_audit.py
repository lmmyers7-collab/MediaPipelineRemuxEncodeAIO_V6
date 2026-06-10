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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from mediapipeline.tools.dev import materialize_tdarr_test_library as tdarr_matrix
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_LIBRARY_ROOT = tdarr_matrix.DEFAULT_LIBRARY_ROOT
DEFAULT_RUNS_ROOT = REPO_ROOT / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns"
DEFAULT_PIPELINE_ENTRYPOINT = REPO_ROOT / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1"
DEFAULT_TEMPLATE = tdarr_matrix.DEFAULT_TEMPLATE
CONFIG_NAME = tdarr_matrix.CONFIG_NAME
AUDIT_SCHEMA = "tdarr_matrix_audit.v1"
AUDIT_RUN_SENTINEL = ".tdarr-matrix-audit-run.json"
AUDIT_DIR_NAME = "audit"
DEFAULT_SAMPLES_PER_BUCKET = 5
DEFAULT_SAMPLE_TIMEOUT_SECONDS = 1800
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    def from_record(cls, record: Mapping[str, object], *, library_root: Path) -> "ManifestRow":
        generated_path = str(record.get("generated_path") or "").replace("\\", "/")
        source_path = Path(str(record.get("source_path") or ""))
        generated_abs = library_root / generated_path
        copied = {field: str(record.get(field) or "") for field in MANIFEST_FIELDNAMES}
        copied["generated_path"] = generated_path
        return cls(
            schema_version=copied["schema_version"],
            view=copied["view"].strip().casefold(),
            case_id=copied["case_id"],
            diagnostic_bucket=copied["diagnostic_bucket"],
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
        message="Tdarr fixture manifest says this case is video, but ffprobe found no usable video stream.",
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


def assert_allowed_run_root(run_root: Path, *, repo_root: Path) -> None:
    allowed_root = (repo_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns").resolve()
    try:
        run_root.resolve().relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(f"Audit run root must be under {allowed_root}") from exc


def prepare_run_root(run_root: Path, *, repo_root: Path = REPO_ROOT, rebuild: bool = False) -> None:
    assert_allowed_run_root(run_root, repo_root=repo_root)
    sentinel = run_root / AUDIT_RUN_SENTINEL
    existing_children = list(run_root.iterdir()) if run_root.exists() else []
    if existing_children and not rebuild:
        raise FileExistsError(f"{run_root} already has content; pass --rebuild-run to regenerate it.")
    if existing_children and rebuild and not sentinel.exists():
        raise FileExistsError(f"{run_root} has no {AUDIT_RUN_SENTINEL}; refusing destructive rebuild.")
    if existing_children and rebuild:
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)


def materialize_run_subset(
    *,
    rows: Sequence[ManifestRow],
    run_root: Path,
    repo_root: Path = REPO_ROOT,
    template_path: Path = DEFAULT_TEMPLATE,
    rebuild: bool = False,
) -> dict[str, Any]:
    run_root = resolve_path(run_root, repo_root=repo_root)
    template_path = resolve_path(template_path, repo_root=repo_root)
    prepare_run_root(run_root, repo_root=repo_root, rebuild=rebuild)
    for path in (
        run_root / "source" / "Movies",
        run_root / "source" / "TV",
        run_root / "output" / "Movies",
        run_root / "output" / "TV",
        run_root / "scratch",
        run_root / "config",
        run_root / "manifests",
    ):
        path.mkdir(parents=True, exist_ok=True)
    for row in rows:
        destination = run_root / row.generated_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"Generated target already exists: {destination}")
        if not row.source_path.exists():
            raise FileNotFoundError(f"Source sample is missing: {row.source_path}")
        os.link(row.source_path, destination)
    write_materialized_manifest(run_root, rows, link_mode="hardlink")
    config_path = run_root / "config" / CONFIG_NAME
    config_path.write_text(tdarr_matrix.render_config(template_path, run_root), encoding="utf-8", newline="\n")
    sentinel = {
        "schema_version": AUDIT_SCHEMA,
        "generated_at_utc": utc_now(),
        "source_library_root": "",
        "run_root": str(run_root),
        "selected_count": len(rows),
        "link_mode": "hardlink",
    }
    (run_root / AUDIT_RUN_SENTINEL).write_text(json.dumps(sentinel, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "run_root": str(run_root),
        "config_path": str(config_path),
        "manifest_csv": str(run_root / "manifests" / "materialized_library.csv"),
        "selected_count": len(rows),
    }


def discover_run_roots(runs_root: Path) -> list[Path]:
    """Sentinel-marked run directories directly under ``runs_root``, oldest first."""
    if not runs_root.exists():
        return []
    marked = [
        child
        for child in runs_root.iterdir()
        if child.is_dir() and (child / AUDIT_RUN_SENTINEL).exists()
    ]
    return sorted(marked, key=lambda path: path.stat().st_mtime)


def prune_run_roots(runs_root: Path, *, keep_last: int, repo_root: Path = REPO_ROOT, dry_run: bool = False) -> dict[str, Any]:
    """Retain the newest ``keep_last`` sentinel-marked run roots and remove older ones (G4).

    Safety rails: ``keep_last`` must be >= 1 (so the just-created run, always the newest, is
    never deleted); only directories that sit directly under the canonical TdarrMatrixRuns root
    and carry ``AUDIT_RUN_SENTINEL`` are eligible; non-sentinel directories are never touched.
    Pass ``dry_run=True`` to preview removals without deleting.
    """
    runs_root = resolve_path(runs_root, repo_root=repo_root)
    allowed_root = (repo_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns").resolve()
    if runs_root != allowed_root:
        raise ValueError(f"Run prune root must be {allowed_root}")
    if keep_last < 1:
        raise ValueError("keep_last must be >= 1 so the newest run is always retained")
    candidates = discover_run_roots(runs_root)
    to_remove = candidates[:-keep_last]
    removed: list[str] = []
    for run_dir in to_remove:
        if not (run_dir / AUDIT_RUN_SENTINEL).exists():
            continue
        if run_dir.resolve().parent != runs_root:
            continue
        if not dry_run:
            shutil.rmtree(run_dir)
        removed.append(str(run_dir))
    return {
        "runs_root": str(runs_root),
        "kept": [str(path) for path in candidates[len(candidates) - keep_last :]],
        "removed": removed,
        "dry_run": dry_run,
    }


def build_powershell_file_command(powershell: str, entrypoint: Path) -> list[str]:
    return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(entrypoint)]


def build_validate_command(powershell: str, entrypoint: Path, config_path: Path) -> list[str]:
    return [*build_powershell_file_command(powershell, entrypoint), "-ConfigPath", str(config_path), "-ValidateOnly"]


def build_effective_config_command(powershell: str, entrypoint: Path, config_path: Path, output_path: Path) -> list[str]:
    return [
        *build_powershell_file_command(powershell, entrypoint),
        "-ConfigPath",
        str(config_path),
        "-DumpEffectiveConfigPath",
        str(output_path),
    ]


def build_queue_snapshot_command(powershell: str, entrypoint: Path, config_path: Path, output_path: Path) -> list[str]:
    return [
        *build_powershell_file_command(powershell, entrypoint),
        "-ConfigPath",
        str(config_path),
        "-EmitQueuePlan",
        "-QueuePlanOutPath",
        str(output_path),
    ]


def build_single_file_command(
    powershell: str,
    entrypoint: Path,
    config_path: Path,
    source_path: Path,
    worker_result_path: Path,
    *,
    run_id: str,
    claim_id: str,
) -> list[str]:
    return [
        *build_powershell_file_command(powershell, entrypoint),
        "-ConfigPath",
        str(config_path),
        "-SingleFile",
        str(source_path),
        "-WorkerChild",
        "-WorkerSlotId",
        "1",
        "-WorkerRunId",
        run_id,
        "-WorkerClaimId",
        claim_id,
        "-WorkerResultPath",
        str(worker_result_path),
    ]


def text_from_timeout(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        return
    process.kill()


def run_subprocess_capture(command: list[str], *, cwd: Path, timeout_seconds: int, stdout_path: Path, stderr_path: Path) -> ProcessOutcome:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout = text_from_timeout(exc.stdout)
            stderr = text_from_timeout(exc.stderr)
        duration = time.monotonic() - started
        stdout_path.write_text(stdout or "", encoding="utf-8")
        stderr_path.write_text(stderr or "", encoding="utf-8")
        return ProcessOutcome(command=command, returncode=None, timed_out=True, duration_seconds=duration, stdout_path=stdout_path, stderr_path=stderr_path)
    duration = time.monotonic() - started
    stdout_path.write_text(stdout or "", encoding="utf-8")
    stderr_path.write_text(stderr or "", encoding="utf-8")
    return ProcessOutcome(
        command=command,
        returncode=process.returncode,
        timed_out=False,
        duration_seconds=duration,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def default_audit_dir(library_root: Path) -> Path:
    return library_root / "manifests" / AUDIT_DIR_NAME


def default_config_path(library_root: Path) -> Path:
    return library_root / "config" / CONFIG_NAME


def default_queue_snapshot_path(library_root: Path) -> Path:
    return default_audit_dir(library_root) / "queue_snapshot.json"


def default_effective_config_path(library_root: Path) -> Path:
    return default_audit_dir(library_root) / "effective_config.json"


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload is not an object: {path}")
    return payload


def command_failure_finding(label: str, outcome: ProcessOutcome) -> Finding | None:
    if outcome.timed_out:
        return Finding(
            severity="critical",
            code="subprocess_timeout",
            message=f"{label} timed out.",
            evidence=outcome.to_dict(),
        )
    if outcome.returncode not in (0, None):
        return Finding(
            severity="critical",
            code="subprocess_failed",
            message=f"{label} exited with code {outcome.returncode}.",
            evidence=outcome.to_dict(),
        )
    return None


def prepare_pipeline_evidence(
    *,
    library_root: Path,
    config_path: Path,
    powershell: str,
    entrypoint: Path,
    cwd: Path = REPO_ROOT,
    timeout_seconds: int = 600,
) -> tuple[Path, Path, list[Finding]]:
    audit_dir = default_audit_dir(library_root)
    command_dir = audit_dir / "commands"
    audit_dir.mkdir(parents=True, exist_ok=True)
    effective_config_path = default_effective_config_path(library_root)
    queue_snapshot_path = default_queue_snapshot_path(library_root)
    steps = [
        ("validate", build_validate_command(powershell, entrypoint, config_path)),
        ("effective-config", build_effective_config_command(powershell, entrypoint, config_path, effective_config_path)),
        ("queue-snapshot", build_queue_snapshot_command(powershell, entrypoint, config_path, queue_snapshot_path)),
    ]
    findings: list[Finding] = []
    outcomes: list[dict[str, Any]] = []
    for label, command in steps:
        outcome = run_subprocess_capture(
            command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            stdout_path=command_dir / f"{label}.stdout.log",
            stderr_path=command_dir / f"{label}.stderr.log",
        )
        outcomes.append({"label": label, **outcome.to_dict()})
        finding = command_failure_finding(label, outcome)
        if finding:
            findings.append(finding)
    (audit_dir / "prepare_evidence_results.json").write_text(json.dumps(outcomes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return effective_config_path, queue_snapshot_path, findings


def expected_media_kind(row: ManifestRow) -> str:
    return "tv" if row.view == "tv" else "movie"


def normalized_media_kind(value: object) -> str:
    text = str(value or "").strip().casefold()
    if text in {"movies", "movie"}:
        return "movie"
    if text in {"tv", "television", "episode"}:
        return "tv"
    return text


def audit_queue_snapshot(rows: Sequence[ManifestRow], snapshot: Mapping[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    snapshot_rows = [row for row in snapshot.get("rows", []) if isinstance(row, Mapping)]
    excluded_rows = [row for row in snapshot.get("excluded_rows", []) if isinstance(row, Mapping)]
    by_source = {path_key(str(row.get("source_path") or "")): row for row in snapshot_rows if row.get("source_path")}
    excluded_by_source = {path_key(str(row.get("source_path") or "")): row for row in excluded_rows if row.get("source_path")}
    for manifest_row in rows:
        key = path_key(manifest_row.generated_abs)
        queue_row = by_source.get(key)
        if queue_row:
            expected = expected_media_kind(manifest_row)
            actual = normalized_media_kind(queue_row.get("media_kind") or queue_row.get("library_designation"))
            if actual and actual != expected:
                findings.append(
                    finding_for_row(
                        manifest_row,
                        severity="error",
                        code="media_kind_mismatch",
                        message=f"Expected {expected} queue media kind but found {actual}.",
                        evidence={"queue_media_kind": queue_row.get("media_kind"), "library_designation": queue_row.get("library_designation")},
                    )
                )
            blocked_code = str(queue_row.get("blocked_reason_code") or "").strip()
            if blocked_code:
                findings.append(
                    finding_for_row(
                        manifest_row,
                        severity="warning",
                        code="queue_row_excluded",
                        message=f"Queue row is excluded: {blocked_code}.",
                        evidence={"blocked_reason_code": blocked_code, "blocked_reason": queue_row.get("blocked_reason")},
                    )
                )
                continue
            run_queue_index = int_value(queue_row.get("run_queue_index"))
            route = str(queue_row.get("route") or "").strip()
            if run_queue_index > 0 and not route:
                findings.append(
                    finding_for_row(
                        manifest_row,
                        severity="error",
                        code="route_preview_missing",
                        message="Runnable queue row has no route preview.",
                        evidence={"run_queue_index": run_queue_index, "route_reason": queue_row.get("route_reason")},
                    )
                )
            continue
        excluded_row = excluded_by_source.get(key)
        if excluded_row:
            reason_code = str(excluded_row.get("reason_code") or "").strip()
            severity = "warning" if reason_code else "error"
            findings.append(
                finding_for_row(
                    manifest_row,
                    severity=severity,
                    code="queue_row_excluded" if reason_code else "queue_row_missing",
                    message=f"Manifest row is excluded from queue: {reason_code or 'missing reason'}.",
                    evidence={"reason_code": reason_code, "reason": excluded_row.get("reason")},
                )
            )
            continue
        findings.append(
            finding_for_row(
                manifest_row,
                severity="error",
                code="queue_row_missing",
                message="Manifest row is missing from the queue snapshot and has no exclusion row.",
                evidence={"expected_source_path": str(manifest_row.generated_abs)},
            )
        )
    return findings


def audit_source_hashes(rows: Sequence[ManifestRow]) -> list[Finding]:
    findings: list[Finding] = []
    for row in rows:
        try:
            actual_hash = sha256_file(row.generated_abs)
        except OSError as exc:
            findings.append(
                finding_for_row(
                    row,
                    severity="critical",
                    code="source_unreadable",
                    message=f"Generated source path is unreadable: {exc}",
                    evidence={"generated_abs": str(row.generated_abs)},
                )
            )
            continue
        if row.sha256 and actual_hash.casefold() != row.sha256.casefold():
            findings.append(
                finding_for_row(
                    row,
                    severity="critical",
                    code="source_hash_changed",
                    message="Generated source hash does not match the Tdarr inventory SHA-256.",
                    evidence={"expected_sha256": row.sha256, "actual_sha256": actual_hash, "generated_abs": str(row.generated_abs)},
                )
            )
    return findings


def audit_bucket_classification(rows: Sequence[ManifestRow]) -> list[Finding]:
    """Flag manifest rows whose codec hit the catch-all or drifted from its recorded bucket (G6)."""
    findings: list[Finding] = []
    for row in rows:
        bucket, is_fallback = tdarr_matrix.classify_bucket(row.medium, row.video_codec, row.container)
        if is_fallback:
            findings.append(
                finding_for_row(
                    row,
                    severity="warning",
                    code="bucket_classification_fallback",
                    message=(
                        f"Video codec '{row.video_codec}' is not mapped to an explicit diagnostic "
                        "bucket; it defaulted to legacy-video. Add a classification rule."
                    ),
                    evidence={"video_codec": row.video_codec, "container": row.container, "medium": row.medium, "bucket": bucket},
                )
            )
        elif row.diagnostic_bucket and bucket != row.diagnostic_bucket:
            findings.append(
                finding_for_row(
                    row,
                    severity="warning",
                    code="bucket_classification_drift",
                    message=f"Recorded bucket '{row.diagnostic_bucket}' does not match recomputed bucket '{bucket}'.",
                    evidence={"recorded_bucket": row.diagnostic_bucket, "recomputed_bucket": bucket},
                )
            )
    return findings


def iter_json_path_values(payload: Any, *, key: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(payload, Mapping):
        for child_key, child_value in payload.items():
            child_key_text = str(child_key)
            yield from iter_json_path_values(child_value, key=child_key_text)
    elif isinstance(payload, list):
        for item in payload:
            yield from iter_json_path_values(item, key=key)
    elif isinstance(payload, str):
        key_folded = key.strip().casefold()
        if key_folded in CONTAINMENT_PATH_KEYS and key_folded not in SOURCE_PATH_KEYS:
            yield key, payload


def iter_json_payloads(path: Path) -> Iterable[tuple[int, Any]]:
    if path.suffix.casefold() == ".jsonl":
        for line_no, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError:
                continue
        return
    try:
        yield 1, json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return


def audit_path_containment(library_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    candidates: list[Path] = []
    for parts in CONTAINMENT_SCAN_SUBDIRS:
        pattern_root = library_root.joinpath(*parts)
        if pattern_root.exists():
            candidates.extend(path for path in pattern_root.rglob("*") if path.suffix.casefold() in {".json", ".jsonl"})
    for evidence_path in candidates:
        for line_no, payload in iter_json_payloads(evidence_path):
            for key, value in iter_json_path_values(payload):
                candidate = Path(value)
                if not candidate.is_absolute():
                    continue
                if is_under(candidate, library_root):
                    continue
                findings.append(
                    Finding(
                        severity="critical",
                        code="path_escaped_test_root",
                        message=f"Evidence path field {key} points outside the active Tdarr test root.",
                        evidence={"evidence_path": str(evidence_path), "line": line_no, "field": key, "value": value, "library_root": str(library_root)},
                    )
                )
    return findings


def load_worker_result(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def failure_artifact_count(library_root: Path) -> int:
    failure_root = library_root / "scratch" / "State" / "Failures"
    if not failure_root.exists():
        return 0
    return sum(1 for path in failure_root.rglob("*") if path.is_file())


def audit_worker_result(row: ManifestRow, *, result_path: Path, outcome: ProcessOutcome, library_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    payload = load_worker_result(result_path)
    if outcome.timed_out and not payload:
        findings.append(
            finding_for_row(
                row,
                severity="critical",
                code="subprocess_timeout",
                message="SingleFile processing timed out without a structured worker result.",
                evidence=outcome.to_dict() | {"worker_result_path": str(result_path)},
            )
        )
        return findings
    if not payload:
        findings.append(
            finding_for_row(
                row,
                severity="error",
                code="worker_result_missing",
                message="SingleFile processing did not produce a structured worker result.",
                evidence=outcome.to_dict() | {"worker_result_path": str(result_path)},
            )
        )
        return findings
    success = bool(payload.get("Success"))
    status = str(payload.get("Status") or "")
    reason = str(payload.get("Reason") or "")
    error_code = str(payload.get("ErrorCode") or "")
    if success:
        if row.diagnostic_bucket == "audio-only":
            # G9 (advisory by design): audio-only success is reported as a WARNING, not an
            # error, so the strict gate does not fail on it. The audit surfaces the event for
            # operator review; it does not enforce the "audio-only must be rejected" media
            # policy. Promoting this to an error is a media-policy (AGENTS.md s7) decision and
            # would require real-media validation; see docs/dev/tdarr-matrix-audit-gaps.md G9.
            findings.append(
                finding_for_row(
                    row,
                    severity="warning",
                    code="audio_only_processed_successfully",
                    message="Audio-only sample completed successfully; verify this is intended media-policy behavior.",
                    evidence={"worker_result": payload},
                )
            )
        return findings
    reason_folded = f"{status} {reason} {error_code}".casefold()
    if "already" in reason_folded and "processed" in reason_folded:
        findings.append(
            finding_for_row(
                row,
                severity="warning",
                code="already_processed_skip",
                message="Sample was skipped as already processed.",
                evidence={"worker_result": payload},
            )
        )
        return findings
    if reason.strip() or error_code.strip() or failure_artifact_count(library_root) > 0:
        findings.append(
            finding_for_row(
                row,
                severity="warning",
                code="classified_processing_failure",
                message="SingleFile processing failed with structured evidence.",
                evidence={"worker_result": payload},
            )
        )
        return findings
    findings.append(
        finding_for_row(
            row,
            severity="error",
            code="processing_failure_unclassified",
            message="SingleFile processing failed without error code, reason, or failure artifact evidence.",
            evidence={"worker_result": payload, "outcome": outcome.to_dict()},
        )
    )
    return findings


def run_sample_processing(
    *,
    rows: Sequence[ManifestRow],
    library_root: Path,
    config_path: Path,
    powershell: str,
    entrypoint: Path,
    run_id: str,
    timeout_seconds: int,
    cwd: Path = REPO_ROOT,
) -> list[Finding]:
    findings: list[Finding] = []
    files_dir = default_audit_dir(library_root) / "files"
    for row in rows:
        item_dir = files_dir / safe_slug(f"{row.case_id}-{row.view}")
        item_dir.mkdir(parents=True, exist_ok=True)
        worker_result_path = item_dir / "worker_result.json"
        pre_hash = ""
        pre_error = ""
        try:
            pre_hash = sha256_file(library_root / row.generated_path)
        except OSError as exc:
            pre_error = str(exc)
        command = build_single_file_command(
            powershell,
            entrypoint,
            config_path,
            library_root / row.generated_path,
            worker_result_path,
            run_id=run_id,
            claim_id=safe_slug(f"{row.case_id}-{row.view}"),
        )
        outcome = run_subprocess_capture(
            command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            stdout_path=item_dir / "stdout.log",
            stderr_path=item_dir / "stderr.log",
        )
        post_hash = ""
        post_error = ""
        try:
            post_hash = sha256_file(library_root / row.generated_path)
        except OSError as exc:
            post_error = str(exc)
        hash_record = {
            "case_id": row.case_id,
            "view": row.view,
            "generated_path": row.generated_path,
            "expected_sha256": row.sha256,
            "pre_sha256": pre_hash,
            "post_sha256": post_hash,
            "pre_error": pre_error,
            "post_error": post_error,
        }
        (item_dir / "source_hashes.json").write_text(json.dumps(hash_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if pre_hash and post_hash and pre_hash != post_hash:
            findings.append(
                finding_for_row(
                    row,
                    severity="critical",
                    code="source_hash_changed",
                    message="Generated source hash changed during SingleFile processing.",
                    evidence=hash_record,
                )
            )
        findings.extend(audit_worker_result(row, result_path=worker_result_path, outcome=outcome, library_root=library_root))
    return findings


def required_input_findings(*, manifest_path: Path, config_path: Path, queue_snapshot_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for label, path in (("manifest", manifest_path), ("config", config_path), ("queue snapshot", queue_snapshot_path)):
        if not path.exists():
            findings.append(
                Finding(
                    severity="critical",
                    code="required_input_unreadable",
                    message=f"Required {label} input is missing or unreadable.",
                    evidence={"path": str(path), "label": label},
                )
            )
    return findings


def report_paths(audit_dir: Path) -> tuple[Path, Path, Path]:
    return (
        audit_dir / "tdarr_matrix_audit_report.json",
        audit_dir / "tdarr_matrix_audit_summary.md",
        audit_dir / "tdarr_matrix_findings.csv",
    )


def write_reports(
    *,
    library_root: Path,
    audit_dir: Path,
    rows: Sequence[ManifestRow],
    findings: Sequence[Finding],
    queue_snapshot_path: Path | None = None,
    effective_config_path: Path | None = None,
    mode: str = "report",
) -> dict[str, Any]:
    audit_dir.mkdir(parents=True, exist_ok=True)
    severity_counts = Counter(finding.severity for finding in findings)
    code_counts = Counter(finding.code for finding in findings)
    report = {
        "schema_version": AUDIT_SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": mode,
        "library_root": str(library_root),
        "manifest_count": len(rows),
        "queue_snapshot_path": str(queue_snapshot_path or ""),
        "effective_config_path": str(effective_config_path or ""),
        "severity_counts": dict(sorted(severity_counts.items())),
        "code_counts": dict(sorted(code_counts.items())),
        "findings": [finding.to_dict() for finding in findings],
    }
    json_path, markdown_path, csv_path = report_paths(audit_dir)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_lines = [
        "# Tdarr Matrix Audit Summary",
        "",
        f"- Schema: `{AUDIT_SCHEMA}`",
        f"- Mode: `{mode}`",
        f"- Library root: `{library_root}`",
        f"- Manifest rows: `{len(rows)}`",
        f"- Findings: `{len(findings)}`",
        "",
        "## Severity Counts",
        "",
    ]
    for severity in ("critical", "error", "warning", "info"):
        markdown_lines.append(f"- {severity}: `{severity_counts.get(severity, 0)}`")
    markdown_lines.extend(["", "## Top Finding Codes", ""])
    if code_counts:
        for code, count in code_counts.most_common(20):
            markdown_lines.append(f"- `{code}`: `{count}`")
    else:
        markdown_lines.append("- none")
    markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "severity",
            "code",
            "message",
            "case_id",
            "view",
            "diagnostic_bucket",
            "generated_path",
            "source_path",
            "evidence",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for finding in findings:
            row = finding.to_dict()
            row["evidence"] = json.dumps(row["evidence"], sort_keys=True)
            writer.writerow(row)
    return report


def exit_code_for_findings(findings: Sequence[Finding], *, strict: bool) -> int:
    if not strict:
        return 0
    return 1 if any(finding.severity in FAIL_SEVERITIES for finding in findings) else 0


def audit_existing_library(
    *,
    library_root: Path,
    manifest_path: Path,
    config_path: Path,
    queue_snapshot_path: Path,
    effective_config_path: Path | None = None,
    audit_dir: Path | None = None,
    hash_sources: bool = False,
    mode: str = "report",
    ffprobe: str = "ffprobe",
    fixture_probe_timeout_seconds: int = DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS,
) -> tuple[list[ManifestRow], list[Finding], dict[str, Any]]:
    audit_dir = audit_dir or default_audit_dir(library_root)
    findings = required_input_findings(manifest_path=manifest_path, config_path=config_path, queue_snapshot_path=queue_snapshot_path)
    rows: list[ManifestRow] = []
    if manifest_path.exists():
        try:
            rows = load_manifest_rows(manifest_path, library_root=library_root)
        except Exception as exc:
            findings.append(Finding(severity="critical", code="required_input_unreadable", message=f"Could not read materialized manifest: {exc}", evidence={"path": str(manifest_path)}))
    snapshot: dict[str, Any] = {}
    if queue_snapshot_path.exists():
        try:
            snapshot = load_json_object(queue_snapshot_path)
        except Exception as exc:
            findings.append(Finding(severity="critical", code="required_input_unreadable", message=f"Could not read queue snapshot: {exc}", evidence={"path": str(queue_snapshot_path)}))
    if rows and snapshot:
        findings.extend(audit_queue_snapshot(rows, snapshot))
    if rows and hash_sources:
        findings.extend(audit_source_hashes(rows))
    if rows:
        _, fixture_probe_findings = audit_fixture_video_probes(rows, ffprobe=ffprobe, timeout_seconds=fixture_probe_timeout_seconds)
        findings.extend(fixture_probe_findings)
        findings.extend(audit_bucket_classification(rows))
    findings.extend(audit_path_containment(library_root))
    report = write_reports(
        library_root=library_root,
        audit_dir=audit_dir,
        rows=rows,
        findings=findings,
        queue_snapshot_path=queue_snapshot_path,
        effective_config_path=effective_config_path,
        mode=mode,
    )
    return rows, findings, report


def run_id_default() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")


def command_report(args: argparse.Namespace) -> int:
    library_root = resolve_path(args.library_root)
    manifest_path = resolve_path(args.manifest_csv or library_root / "manifests" / "materialized_library.csv")
    config_path = resolve_path(args.config_path or default_config_path(library_root))
    queue_snapshot_path = resolve_path(args.queue_snapshot or default_queue_snapshot_path(library_root))
    effective_config_path = resolve_path(args.effective_config or default_effective_config_path(library_root))
    audit_dir = resolve_path(args.audit_dir or default_audit_dir(library_root))
    prepare_findings: list[Finding] = []
    if args.prepare_evidence:
        effective_config_path, queue_snapshot_path, prepare_findings = prepare_pipeline_evidence(
            library_root=library_root,
            config_path=config_path,
            powershell=args.powershell,
            entrypoint=resolve_path(args.entrypoint),
            timeout_seconds=args.prepare_timeout_seconds,
        )
    rows, findings, report = audit_existing_library(
        library_root=library_root,
        manifest_path=manifest_path,
        config_path=config_path,
        queue_snapshot_path=queue_snapshot_path,
        effective_config_path=effective_config_path,
        audit_dir=audit_dir,
        hash_sources=args.hash_sources,
        mode="report",
        ffprobe=args.ffprobe,
        fixture_probe_timeout_seconds=args.fixture_probe_timeout_seconds,
    )
    findings = [*prepare_findings, *findings]
    if prepare_findings:
        report = write_reports(
            library_root=library_root,
            audit_dir=audit_dir,
            rows=rows,
            findings=findings,
            queue_snapshot_path=queue_snapshot_path,
            effective_config_path=effective_config_path,
            mode="report",
        )
    print(json.dumps({"manifest_count": len(rows), "finding_count": len(findings), "report_path": str(report_paths(audit_dir)[0])}, indent=2, sort_keys=True))
    return exit_code_for_findings(findings, strict=not args.report_only)


def command_run_samples(args: argparse.Namespace) -> int:
    source_library_root = resolve_path(args.library_root)
    source_manifest_path = source_library_root / "manifests" / "materialized_library.csv"
    source_rows = load_manifest_rows(source_manifest_path, library_root=source_library_root)
    fixture_probe_findings: list[Finding] = []
    if getattr(args, "case_key", None):
        selected_rows = select_case_key_rows(source_rows, args.case_key)
        _, fixture_probe_findings = audit_fixture_video_probes(
            selected_rows,
            ffprobe=args.ffprobe,
            timeout_seconds=args.fixture_probe_timeout_seconds,
        )
    elif bool(getattr(args, "all_samples", False)):
        selected_rows = select_all_sample_rows(source_rows)
        _, fixture_probe_findings = audit_fixture_video_probes(
            selected_rows,
            ffprobe=args.ffprobe,
            timeout_seconds=args.fixture_probe_timeout_seconds,
        )
    else:
        selected_rows, fixture_probe_findings, _fixture_probe_results = select_sample_rows_with_fixture_probe_filter(
            source_rows,
            samples_per_bucket=args.samples_per_bucket,
            ffprobe=args.ffprobe,
            timeout_seconds=args.fixture_probe_timeout_seconds,
        )
    run_id = args.run_id or run_id_default()
    runs_root = resolve_path(args.runs_root)
    run_root = resolve_path(args.run_root or runs_root / run_id)
    materialize_run_subset(
        rows=selected_rows,
        run_root=run_root,
        repo_root=REPO_ROOT,
        template_path=resolve_path(args.template),
        rebuild=args.rebuild_run,
    )
    run_rows = load_manifest_rows(run_root / "manifests" / "materialized_library.csv", library_root=run_root)
    config_path = run_root / "config" / CONFIG_NAME
    effective_config_path, queue_snapshot_path, findings = prepare_pipeline_evidence(
        library_root=run_root,
        config_path=config_path,
        powershell=args.powershell,
        entrypoint=resolve_path(args.entrypoint),
        timeout_seconds=args.prepare_timeout_seconds,
    )
    findings = [*fixture_probe_findings, *findings]
    if queue_snapshot_path.exists():
        try:
            findings.extend(audit_queue_snapshot(run_rows, load_json_object(queue_snapshot_path)))
        except Exception as exc:
            findings.append(Finding(severity="critical", code="required_input_unreadable", message=f"Could not read queue snapshot: {exc}", evidence={"path": str(queue_snapshot_path)}))
    findings.extend(audit_source_hashes(run_rows))
    findings.extend(
        run_sample_processing(
            rows=run_rows,
            library_root=run_root,
            config_path=config_path,
            powershell=args.powershell,
            entrypoint=resolve_path(args.entrypoint),
            run_id=run_id,
            timeout_seconds=args.sample_timeout_seconds,
        )
    )
    findings.extend(audit_source_hashes(run_rows))
    findings.extend(audit_bucket_classification(run_rows))
    findings.extend(audit_path_containment(run_root))
    report = write_reports(
        library_root=run_root,
        audit_dir=default_audit_dir(run_root),
        rows=run_rows,
        findings=findings,
        queue_snapshot_path=queue_snapshot_path,
        effective_config_path=effective_config_path,
        mode="run-samples",
    )
    summary: dict[str, Any] = {
        "run_root": str(run_root),
        "selected_count": len(run_rows),
        "finding_count": len(findings),
        "report_path": str(report_paths(default_audit_dir(run_root))[0]),
    }
    if getattr(args, "case_key", None):
        summary["case_keys"] = [manifest_case_key(row) for row in run_rows]
    if bool(getattr(args, "all_samples", False)):
        summary["all_samples"] = True
    if args.keep_last >= 1:
        summary["pruned"] = prune_run_roots(runs_root, keep_last=args.keep_last, dry_run=args.prune_dry_run)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return exit_code_for_findings(findings, strict=not args.report_only)


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--library-root", default=str(DEFAULT_LIBRARY_ROOT))
    parser.add_argument("--powershell", default=resolve_default_powershell())
    parser.add_argument("--entrypoint", default=str(DEFAULT_PIPELINE_ENTRYPOINT))
    parser.add_argument("--prepare-timeout-seconds", type=int, default=600)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--fixture-probe-timeout-seconds", type=int, default=DEFAULT_FIXTURE_PROBE_TIMEOUT_SECONDS)
    parser.add_argument("--report-only", action="store_true", help="Write findings but exit zero unless inputs crash the tool.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the generated Tdarr Matrix scratch test library.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report", help="Audit existing Tdarr Matrix evidence.")
    add_common_arguments(report)
    report.add_argument("--manifest-csv", default="")
    report.add_argument("--config-path", default="")
    report.add_argument("--queue-snapshot", default="")
    report.add_argument("--effective-config", default="")
    report.add_argument("--audit-dir", default="")
    report.add_argument("--prepare-evidence", action="store_true")
    report.add_argument("--hash-sources", action="store_true", help="Hash every generated source path during report mode.")

    samples = subparsers.add_parser("run-samples", help="Create an isolated sample run and process selected files.")
    add_common_arguments(samples)
    samples.add_argument("--runs-root", default=str(DEFAULT_RUNS_ROOT))
    samples.add_argument("--run-root", default="")
    samples.add_argument("--run-id", default="")
    samples.add_argument("--samples-per-bucket", type=int, default=DEFAULT_SAMPLES_PER_BUCKET)
    samples.add_argument("--sample-timeout-seconds", type=int, default=DEFAULT_SAMPLE_TIMEOUT_SECONDS)
    samples.add_argument("--all-samples", action="store_true", help="Select every manifest row for a full-library proof run.")
    samples.add_argument(
        "--case-key",
        action="append",
        default=[],
        help="Materialize and process an exact manifest case key, formatted as '<case_id>:<view>'. May be repeated.",
    )
    samples.add_argument("--rebuild-run", action="store_true")
    samples.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    samples.add_argument(
        "--keep-last",
        type=int,
        default=0,
        help="If >=1, prune older sentinel-marked run roots after a successful run, keeping the newest N. 0 disables pruning.",
    )
    samples.add_argument(
        "--prune-dry-run",
        action="store_true",
        help="With --keep-last, preview which run roots would be removed without deleting them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "report":
        return command_report(args)
    if args.command == "run-samples":
        return command_run_samples(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
