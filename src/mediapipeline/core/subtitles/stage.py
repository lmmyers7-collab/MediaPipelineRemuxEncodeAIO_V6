"""Scratch-only Python executor for standalone ASS/SSA to SRT conversion."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mediapipeline.contracts.stage_mutation import SubtitleConvertPayload, SubtitleConvertResult
from mediapipeline.core.paths.layout import ensure_path_boundary_safe_for_mutation, path_within_root
from mediapipeline.pipeline.ass_to_srt.ass_events import collect_dialogue_cues, load_ass_with_best_encoding
from mediapipeline.pipeline.ass_to_srt.srt import apply_minimum_gap, merge_overlapping_cues, render_srt
from mediapipeline.pipeline.ass_to_srt.styles import DEFAULT_EXCLUDE_STYLES, compile_style_matcher

ASS_ENCODINGS = ("utf-8", "utf-8-sig", "cp932", "shift_jis", "euc_jp", "cp1252")
MAX_ASS_BYTES = 64 * 1024 * 1024


class SubtitleStageBoundaryError(RuntimeError):
    """The requested conversion is outside the scratch-only boundary."""


class SubtitleStageFingerprintError(RuntimeError):
    """The execute request no longer matches its dry-run evidence."""


class SubtitleStageRecoveryError(RuntimeError):
    """Conversion output could not be committed or rolled back safely."""


def _path_key(path: Path) -> str:
    text = os.path.abspath(str(path.resolve(strict=False)))
    return os.path.normcase(text) if os.name == "nt" else text


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.remove(temporary_name)
        except OSError:
            pass
        raise


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _validated_paths(payload: SubtitleConvertPayload) -> tuple[Path, Path, Path, list[str]]:
    input_path = Path(payload.input_ass_path)
    scratch_root = Path(payload.scratch_root)
    output_path = input_path.with_suffix(".srt")

    if not scratch_root.exists() or not scratch_root.is_dir():
        raise SubtitleStageBoundaryError(f"scratch_root must be an existing directory: {scratch_root}")
    try:
        ensure_path_boundary_safe_for_mutation(input_path, scratch_root)
        ensure_path_boundary_safe_for_mutation(output_path, scratch_root, allow_missing_leaf=True)
    except RuntimeError as exc:
        raise SubtitleStageBoundaryError(str(exc)) from exc
    if not input_path.is_file():
        raise SubtitleStageBoundaryError(f"input_ass_path must be one existing regular scratch file: {input_path}")
    if input_path.suffix.casefold() not in {".ass", ".ssa"}:
        raise SubtitleStageBoundaryError("subtitle stage accepts only standalone .ass or .ssa scratch files")
    if input_path.stat().st_size > MAX_ASS_BYTES:
        raise SubtitleStageBoundaryError(
            f"subtitle stage input exceeds the {MAX_ASS_BYTES}-byte standalone artifact limit"
        )
    if output_path.exists():
        raise FileExistsError(f"Subtitle output already exists: {output_path}")

    for source_root_text in payload.source_roots:
        source_root = Path(source_root_text)
        if not source_root.is_absolute():
            raise SubtitleStageBoundaryError(f"source_roots entries must be absolute paths: {source_root}")
        if path_within_root(input_path, source_root):
            raise SubtitleStageBoundaryError(f"input_ass_path overlaps a protected source root: {source_root}")
        if path_within_root(scratch_root, source_root) or path_within_root(source_root, scratch_root):
            raise SubtitleStageBoundaryError(
                f"scratch_root must be disjoint from every protected source root: {source_root}"
            )
    return input_path, output_path, scratch_root, [
        "input ASS/SSA and output SRT are children of scratch_root",
        "scratch_root is disjoint from every protected source root",
        "input is a regular non-reparse subtitle file and output does not already exist",
        f"input size is at most {MAX_ASS_BYTES} bytes",
        "conversion writes one new SRT sidecar and never modifies the ASS/SSA input",
        "TX3G extraction, BDPGS OCR, embedded streams, and publish integration are disabled",
    ]


def _conversion_plan(payload: SubtitleConvertPayload) -> dict[str, Any]:
    input_path, output_path, scratch_root, boundary_checks = _validated_paths(payload)
    input_hash = _sha256_file(input_path)
    try:
        import pysubs2
    except ImportError as exc:  # pragma: no cover - bundled runtime dependency gate
        raise RuntimeError("pysubs2 is required for scratch ASS/SSA conversion") from exc

    subs, encoding, diagnostics, load_error = load_ass_with_best_encoding(
        str(input_path),
        ASS_ENCODINGS,
        pysubs2,
    )
    review_reason = ""
    srt_text = ""
    cue_count = 0
    if subs is None:
        review_reason = f"ASS/SSA decode requires review: {load_error or 'no safe encoding'}"
    else:
        dialogue = collect_dialogue_cues(
            subs,
            style_is_noise=compile_style_matcher(DEFAULT_EXCLUDE_STYLES),
            style_is_dialog=compile_style_matcher([]),
            remove_karaoke=True,
            strip_formatting=True,
        )
        cues = apply_minimum_gap(merge_overlapping_cues(dialogue["cues"]), gap_ms=1)
        cue_count = len(cues)
        if cue_count == 0:
            review_reason = "ASS/SSA conversion produced no dialogue cues; manual review is required."
        else:
            srt_text = render_srt(cues)

    plan_evidence = {
        "schema_version": "pipeline_stage_subtitle_convert_dry_run.v1",
        "operation": payload.operation,
        "input_ass_path": _path_key(input_path),
        "output_srt_path": _path_key(output_path),
        "scratch_root": _path_key(scratch_root),
        "source_roots": sorted(_path_key(Path(root)) for root in payload.source_roots),
        "input_sha256": input_hash,
        "encoding": encoding,
        "cues_written": cue_count,
        "output_sha256": _sha256_bytes(srt_text.encode("utf-8")) if srt_text else "",
        "review_reason": review_reason,
    }
    fingerprint = _sha256_bytes(
        json.dumps(plan_evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return {
        "input_path": input_path,
        "output_path": output_path,
        "scratch_root": scratch_root,
        "input_hash": input_hash,
        "encoding": encoding,
        "diagnostics": diagnostics,
        "srt_text": srt_text,
        "cue_count": cue_count,
        "output_hash": plan_evidence["output_sha256"],
        "review_reason": review_reason,
        "fingerprint": fingerprint,
        "boundary_checks": boundary_checks,
    }


def execute_scratch_subtitle_stage(payload: SubtitleConvertPayload) -> SubtitleConvertResult:
    """Preview or execute one standalone ASS/SSA-to-SRT conversion in scratch."""

    plan = _conversion_plan(payload)
    input_path: Path = plan["input_path"]
    output_path: Path = plan["output_path"]
    scratch_root: Path = plan["scratch_root"]
    input_hash = str(plan["input_hash"])
    fingerprint = str(plan["fingerprint"])
    review_reason = str(plan["review_reason"])
    rollback_actions = [f"delete newly created SRT sidecar {output_path} if evidence cannot commit"]
    recovery_actions = ["regenerate the SRT from the unchanged scratch ASS/SSA input after review"]

    common = {
        "input_ass_path": str(input_path),
        "output_srt_path": str(output_path),
        "cues_written": int(plan["cue_count"]),
        "encoding": str(plan["encoding"]),
        "input_sha256_before": input_hash,
        "input_sha256_after": input_hash,
        "output_sha256": str(plan["output_hash"]),
        "dry_run_fingerprint": fingerprint,
        "source_boundary_untouched": True,
        "review_required": bool(review_reason),
        "review_reason": review_reason,
        "rollback_actions": rollback_actions,
        "recovery_actions": recovery_actions,
        "boundary_checks": list(plan["boundary_checks"]),
    }
    if payload.intent == "dry_run":
        return SubtitleConvertResult(**common)
    if payload.dry_run_fingerprint != fingerprint:
        raise SubtitleStageFingerprintError(
            "Subtitle execute dry_run_fingerprint does not match the current scratch-only conversion plan."
        )
    if review_reason:
        return SubtitleConvertResult(**common, operation_id=payload.operation_id)

    evidence_root = scratch_root / ".mediapipeline-stage" / "subtitle-convert"
    evidence_path = evidence_root / f"{payload.operation_id}.json"
    try:
        ensure_path_boundary_safe_for_mutation(evidence_path, scratch_root, allow_missing_leaf=True)
    except RuntimeError as exc:
        raise SubtitleStageBoundaryError(str(exc)) from exc
    if evidence_path.exists():
        raise FileExistsError(f"Subtitle operation evidence already exists: {evidence_path}")
    evidence_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "pipeline_stage_subtitle_convert_evidence.v1",
        "operation_id": payload.operation_id,
        "status": "planned",
        "created_at": datetime.now(UTC).isoformat(),
        "input_ass_path": str(input_path),
        "output_srt_path": str(output_path),
        "input_sha256": input_hash,
        "output_sha256": str(plan["output_hash"]),
        "dry_run_fingerprint": fingerprint,
        "source_media_mutation": "forbidden",
    }
    _write_manifest(evidence_path, manifest)

    output_written = False
    try:
        _atomic_write_text(output_path, str(plan["srt_text"]))
        output_written = True
        if _sha256_file(input_path) != input_hash:
            raise SubtitleStageRecoveryError("Scratch ASS/SSA input content changed during conversion.")
        if _sha256_file(output_path) != str(plan["output_hash"]):
            raise SubtitleStageRecoveryError("Written SRT content hash does not match the dry-run plan.")
        manifest.update({"status": "completed", "completed_at": datetime.now(UTC).isoformat()})
        _write_manifest(evidence_path, manifest)
    except Exception as exc:
        rollback_error = ""
        if output_written and output_path.exists():
            try:
                output_path.unlink()
            except OSError as rollback_exc:  # pragma: no cover - platform/filesystem failure edge
                rollback_error = str(rollback_exc)
        manifest.update(
            {
                "status": "rollback_failed" if rollback_error else "rolled_back",
                "failed_at": datetime.now(UTC).isoformat(),
                "failure": str(exc),
                "rollback_error": rollback_error,
            }
        )
        try:
            _write_manifest(evidence_path, manifest)
        except Exception:
            pass
        if rollback_error:
            raise SubtitleStageRecoveryError(
                f"Subtitle conversion failed and output rollback failed; recover from {evidence_path}: {rollback_error}"
            ) from exc
        raise SubtitleStageRecoveryError(
            f"Subtitle conversion failed and the SRT was rolled back; evidence: {evidence_path}"
        ) from exc

    return SubtitleConvertResult(
        **common,
        tracks_converted=1,
        sidecars_written=[str(output_path)],
        evidence_path=str(evidence_path),
        operation_id=payload.operation_id,
    )


__all__ = [
    "SubtitleStageBoundaryError",
    "SubtitleStageFingerprintError",
    "SubtitleStageRecoveryError",
    "execute_scratch_subtitle_stage",
]
