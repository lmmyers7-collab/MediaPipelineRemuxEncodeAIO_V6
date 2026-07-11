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
from mediapipeline.tools.dev.tdarr_matrix_models import *  # noqa: F403
from mediapipeline.tools.dev.tdarr_matrix_operations import *  # noqa: F403

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


def read_evidence_excerpt(path: Path, *, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")[:limit]
    except OSError:
        return ""


def process_outcome_log_excerpt(outcome: ProcessOutcome, *, limit: int = 4000) -> str:
    stdout = read_evidence_excerpt(outcome.stdout_path, limit=limit)
    stderr = read_evidence_excerpt(outcome.stderr_path, limit=limit)
    return f"{stdout}\n{stderr}"[:limit]


def startup_config_failure_finding(row: ManifestRow, *, result_path: Path, outcome: ProcessOutcome) -> Finding | None:
    excerpt = process_outcome_log_excerpt(outcome)
    match = CONFIG_MISSING_KEY_PATTERN.search(excerpt)
    if not match:
        return None
    missing_key = match.group(1)
    return finding_for_row(
        row,
        severity="error",
        code="worker_startup_config_invalid",
        message=f"SingleFile exited before writing a worker result because config is missing required key: {missing_key}.",
        evidence=outcome.to_dict()
        | {
            "worker_result_path": str(result_path),
            "missing_config_key": missing_key,
            "log_excerpt": excerpt,
        },
    )


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
        startup_finding = startup_config_failure_finding(row, result_path=result_path, outcome=outcome)
        if startup_finding:
            findings.append(startup_finding)
            return findings
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
    if error_code.strip().upper() in WORKER_CHILD_GUARD_ERROR_CODES:
        findings.append(
            finding_for_row(
                row,
                severity="warning",
                code="classified_processing_failure",
                message="SingleFile worker-child guard produced structured failure evidence.",
                evidence={
                    "worker_result": payload,
                    "worker_result_classification": "worker_child_result_guard",
                },
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


def audit_existing_worker_evidence(
    rows: Sequence[ManifestRow],
    *,
    library_root: Path,
    audit_dir: Path,
) -> list[Finding]:
    files_dir = audit_dir / "files"
    if not files_dir.exists():
        return []
    findings: list[Finding] = []
    for row in rows:
        item_dir = files_dir / safe_slug(f"{row.case_id}-{row.view}")
        if not item_dir.exists():
            continue
        stdout_path = item_dir / "stdout.log"
        stderr_path = item_dir / "stderr.log"
        worker_result_path = item_dir / "worker_result.json"
        if not stdout_path.exists() and not stderr_path.exists() and not worker_result_path.exists():
            continue
        outcome = ProcessOutcome(
            command=[],
            returncode=None,
            timed_out=False,
            duration_seconds=0.0,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        findings.extend(audit_worker_result(row, result_path=worker_result_path, outcome=outcome, library_root=library_root))
    return findings



__all__ = [
    "expected_media_kind",
    "normalized_media_kind",
    "audit_queue_snapshot",
    "audit_source_hashes",
    "audit_bucket_classification",
    "iter_json_path_values",
    "iter_json_payloads",
    "audit_path_containment",
    "load_worker_result",
    "read_evidence_excerpt",
    "process_outcome_log_excerpt",
    "startup_config_failure_finding",
    "failure_artifact_count",
    "audit_worker_result",
    "run_sample_processing",
    "audit_existing_worker_evidence",
]
