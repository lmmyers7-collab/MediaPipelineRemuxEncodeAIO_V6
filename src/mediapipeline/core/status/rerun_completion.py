"""Backend-authored terminal summaries for the most recent CSV rerun."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.rerun_results import rerun_results_payload


_CANCELLED_MANIFEST_STATUSES = {"cancelled", "canceled", "aborted", "stopped", "stopped_after_current"}
_COMPLETED_MANIFEST_STATUSES = {"complete", "completed", "done", "succeeded", "success", "finished"}
_INCOMPLETE_QUEUE_STATUSES = {"pending", "active", "blocked", "warning", "stopped", "pending_reduction"}


def _manifest_mtime(manifest: dict[str, Any]) -> float:
    try:
        return Path(str(manifest.get("manifest_path") or "")).stat().st_mtime
    except OSError:
        return 0.0


def _manifest_csv_path(manifest: dict[str, Any]) -> str:
    path = Path(str(manifest.get("manifest_path") or ""))
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return ""
    if not isinstance(raw, dict):
        return ""
    request = raw.get("request_summary")
    request = request if isinstance(request, dict) else {}
    return str(raw.get("csv_path") or raw.get("source_csv_path") or request.get("csv_path") or "")


def _csv_name(csv_path: str, batch_id: str) -> str:
    parts = str(csv_path or "").replace("\\", "/").split("/")
    return next((part for part in reversed(parts) if part), "") or batch_id or "CSV rerun"


def _totals(manifest: dict[str, Any]) -> dict[str, int]:
    counts = manifest.get("queue_status_counts")
    counts = counts if isinstance(counts, dict) else {}
    number = lambda key: max(0, int(counts.get(key, 0) or 0))
    total = max(0, int(manifest.get("row_count", 0) or 0))
    pending = sum(number(key) for key in _INCOMPLETE_QUEUE_STATUSES)
    return {
        "total": total,
        "processed": max(0, total - pending),
        "completed": number("completed") + number("replaced_returned"),
        "failed": number("failed"),
        "skipped": number("skipped"),
        "held": number("awaiting_review"),
        "pending": pending,
        "pending_publish": number("pending_publish"),
    }


def _summary_presentation(manifest: dict[str, Any], totals: dict[str, int]) -> tuple[str, bool, bool, str, str]:
    manifest_status = str(manifest.get("status") or "").strip().casefold()
    rows = manifest.get("rows") if isinstance(manifest.get("rows"), list) else []
    all_rows_terminal = bool(rows) and all(row.get("is_terminal") is True for row in rows if isinstance(row, dict))
    if manifest_status in _CANCELLED_MANIFEST_STATUSES:
        return "cancelled", True, True, "CSV rerun stopped", "warning"
    if not rows and manifest_status in _COMPLETED_MANIFEST_STATUSES:
        return "empty", True, False, "CSV rerun complete — no rows", "ok"
    if not all_rows_terminal:
        return "active", False, False, "CSV rerun active", "running"
    if totals["failed"]:
        return "completed_with_failures", True, True, "CSV rerun complete with failures", "warning"
    if totals["pending_publish"]:
        return "pending_publish", True, True, "CSV rerun complete — pending publish", "warning"
    if totals["held"]:
        return "review_required", True, True, "CSV rerun complete — review required", "warning"
    return "complete", True, False, "CSV rerun complete", "ok"


def _detail(csv_name: str, totals: dict[str, int]) -> str:
    return " · ".join(
        [
            csv_name,
            f"{totals['processed']} processed",
            f"{totals['completed']} completed",
            f"{totals['failed']} failed",
            f"{totals['skipped']} skipped",
            f"{totals['held']} held",
            f"{totals['pending']} pending",
            f"{totals['pending_publish']} pending publish",
        ]
    )


def csv_rerun_completion_summary(resolved: ResolvedPaths) -> dict[str, Any]:
    """Return a read-only current CSV rerun lifecycle summary, when one exists."""

    payload = rerun_results_payload(resolved, limit=24)
    candidates = [
        manifest
        for manifest in [*(payload.get("manifests") or []), *(payload.get("network_manifests") or [])]
        if isinstance(manifest, dict)
    ]
    if not candidates:
        return {}

    computed = [(manifest, _totals(manifest)) for manifest in candidates]
    active = [entry for entry in computed if _summary_presentation(*entry)[0] == "active"]
    manifest, totals = max(active or computed, key=lambda entry: _manifest_mtime(entry[0]))
    status, terminal, attention_required, display_label, display_state = _summary_presentation(manifest, totals)
    batch_id = str(manifest.get("batch_id") or "")
    csv_path = _manifest_csv_path(manifest)
    csv_name = _csv_name(csv_path, batch_id)
    return {
        "schema_version": "desktop_csv_rerun_completion.v1",
        "evidence_authority": "backend_manifest",
        "status": status,
        "terminal": terminal,
        "attention_required": attention_required,
        "display_label": display_label,
        "display_state": display_state,
        "detail": _detail(csv_name, totals),
        "csv_name": csv_name,
        "csv_path": csv_path,
        "batch_id": batch_id,
        "manifest_path": str(manifest.get("manifest_path") or ""),
        "totals": totals,
        "historical_evidence_note": "Earlier progress evidence remains available for review and is not current-run state.",
    }


__all__ = ["csv_rerun_completion_summary"]
