from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from mediapipeline.core.completed.contracts import CompletedJobRecord


# Completed-job live-proof budgeting (backend-load-performance Packet 1).
#
# Live filesystem proof (Path.exists()/stat()) of completed outputs dominates
# broad-refresh load time. ``proof_mode`` bounds how many of the returned rows
# receive that synchronous proof so the first WebView refresh stays fast while
# keeping the evidence explicit rather than silently assumed.
PROOF_MODE_SUMMARY = "summary"   # prove nothing; every row is "not checked"
PROOF_MODE_BOUNDED = "bounded"   # prove the first viewport rows; defer the rest
PROOF_MODE_LIVE = "live"         # prove every returned row (full live proof)
COMPLETED_PROOF_MODES = (PROOF_MODE_SUMMARY, PROOF_MODE_BOUNDED, PROOF_MODE_LIVE)
DEFAULT_COMPLETED_PROOF_MODE = PROOF_MODE_LIVE
COMPLETED_BOUNDED_PROOF_LIMIT = 100

# Per-row proof stamp written onto each record payload so downstream DTO policy
# can report whether output existence was actually checked.
OUTPUT_PROOF_LIVE = "live"
OUTPUT_PROOF_DEFERRED = "deferred"
COMPLETED_MANIFEST_TAIL_CHUNK_BYTES = 64 * 1024


def normalize_proof_mode(value: object) -> str:
    text = str(value or "").strip().casefold()
    if text in COMPLETED_PROOF_MODES:
        return text
    return DEFAULT_COMPLETED_PROOF_MODE


def _row_has_live_proof_budget(index: int, proof_mode: str, bounded_proof_limit: int) -> bool:
    """Whether the row at ``index`` (0-based, most-recent-first) gets live proof."""
    if proof_mode == PROOF_MODE_LIVE:
        return True
    if proof_mode == PROOF_MODE_BOUNDED:
        return index < max(0, bounded_proof_limit)
    return False  # summary


def completed_sidecar_path_from_payload(manifest_path: Path, payload: dict) -> Path:
    output_path_str = payload.get("output_path")
    if output_path_str:
        op = Path(str(output_path_str))
        return op.with_suffix(".pipeline.json")
    return manifest_path


def _recent_manifest_lines(manifest_path: Path, limit: int) -> list[str]:
    """Return up to ``limit`` recent JSONL lines without reading the full file."""
    if limit <= 0:
        return []

    collected: list[bytes] = []
    with manifest_path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        buffer = b""
        while position > 0:
            read_size = min(COMPLETED_MANIFEST_TAIL_CHUNK_BYTES, position)
            position -= read_size
            handle.seek(position)
            buffer = handle.read(read_size) + buffer
            lines = buffer.splitlines()
            if position == 0:
                collected = lines
                break
            if buffer and not buffer.startswith((b"\n", b"\r")):
                lines = lines[1:]
            non_empty = sum(1 for line in lines if line.strip())
            if non_empty >= limit:
                collected = lines
                break
        else:
            collected = buffer.splitlines()

    decoded = [
        line.decode("utf-8", errors="replace").strip().lstrip("\ufeff")
        for line in collected
        if line.strip()
    ]
    return list(reversed(decoded[-limit:]))


def annotate_completed_output_health(record: CompletedJobRecord) -> None:
    payload = record.payload
    try:
        output_exists = record.output_path.exists()
    except Exception as exc:
        output_exists = False
        payload["_diagnostics_output_health"] = f"output existence check failed: {exc}"
    else:
        payload["_diagnostics_output_health"] = "ok" if output_exists else "completed metadata without media"
    payload["_diagnostics_output_exists"] = bool(output_exists)


def read_completed_manifest_records(
    manifest_path: Path,
    *,
    limit: int | None,
    logger: logging.Logger,
    proof_mode: str = DEFAULT_COMPLETED_PROOF_MODE,
    bounded_proof_limit: int = COMPLETED_BOUNDED_PROOF_LIMIT,
) -> list[CompletedJobRecord]:
    proof_mode = normalize_proof_mode(proof_mode)
    parsed: list[CompletedJobRecord] = []
    if limit is None:
        raw = manifest_path.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip().lstrip("\ufeff") for line in raw.splitlines()]
        recent_first = False
    else:
        lines = _recent_manifest_lines(manifest_path, limit)
        recent_first = True
    for line_no, line in enumerate(lines, start=1):
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed manifest line %d in %s", line_no, manifest_path)
            continue
        if not isinstance(payload, dict):
            continue
        sidecar_path = completed_sidecar_path_from_payload(manifest_path, payload)
        record = CompletedJobRecord(sidecar_path=sidecar_path, payload=payload)
        parsed.append(record)
    if not recent_first:
        parsed.reverse()
    if limit is not None and len(parsed) > limit:
        parsed = parsed[:limit]
    # Apply live output proof only to the in-budget rows (Packet 1). Rows
    # outside the budget are stamped "deferred" so the DTO reports "not
    # checked" explicitly instead of implying a verified result. Annotation
    # runs after the limit slice so we never stat rows the caller discards.
    for index, record in enumerate(parsed):
        if _row_has_live_proof_budget(index, proof_mode, bounded_proof_limit):
            annotate_completed_output_health(record)
            record.payload["_diagnostics_output_proof"] = OUTPUT_PROOF_LIVE
        else:
            record.payload["_diagnostics_output_proof"] = OUTPUT_PROOF_DEFERRED
    return parsed
