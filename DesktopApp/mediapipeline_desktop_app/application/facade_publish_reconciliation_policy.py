from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .dto import PublishReconciliationDto
from .dto_base import json_safe
from .facade_completed_policy import bounded_completed_limit


PUBLISH_RECONCILIATION_SCHEMA_VERSION = "desktop_publish_reconciliation.v1"


def publish_reconciliation_limit(value: Any) -> int:
    return bounded_completed_limit(value, default=250, minimum=1, maximum=500)


def _first_value(item: Mapping[str, Any] | None, keys: tuple[str, ...]) -> str:
    if not isinstance(item, Mapping):
        return ""
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_path(value: Any) -> str:
    return str(value or "").strip().replace("/", "\\").lower()


def _leaf(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return next((part for part in reversed(text.replace("/", "\\").split("\\")) if part), text).lower()


def _path_looks_absolute(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and (len(text) > 2 and text[1:3] in {":\\", ":/"} or text.startswith("\\\\") or "\\" in text or "/" in text))


def _completed_output(row: Mapping[str, Any]) -> str:
    return _first_value(row, ("output_path", "server_out", "destination_path", "final_path", "output_file"))


def _completed_source(row: Mapping[str, Any]) -> str:
    return _first_value(row, ("source_path", "input_path", "source_file"))


def _pending_destination(row: Mapping[str, Any]) -> str:
    return _first_value(row, ("server_out", "destination_path", "output_path"))


def _pending_source(row: Mapping[str, Any]) -> str:
    return _first_value(row, ("source_path", "input_path", "source_file"))


def _pending_local(row: Mapping[str, Any]) -> str:
    return _first_value(row, ("local_file", "payload_path", "scratch_path", "manifest_path"))


def _row_key(row: Mapping[str, Any] | None, fallback: str = "") -> str:
    return _first_value(row, ("row_key", "source_path", "output_path", "server_out", "local_file", "manifest_path")) or fallback


def _completed_label(row: Mapping[str, Any]) -> str:
    return _first_value(row, ("lookup_title", "output_file", "title", "route_label")) or _leaf(_completed_output(row)) or "(completed row)"


def _pending_label(row: Mapping[str, Any]) -> str:
    return _first_value(row, ("lookup_title", "output_file", "title", "state")) or _leaf(_pending_destination(row) or _pending_local(row)) or "(pending row)"


def _completed_missing_output(row: Mapping[str, Any]) -> bool:
    health = str(row.get("output_health") or row.get("output_status") or row.get("operator_status") or "").casefold()
    return bool(
        row.get("output_exists") is False
        or row.get("missing_output") is True
        or any(token in health for token in ("missing", "not_found", "not found", "deleted", "unavailable"))
    )


def _pending_status(row: Mapping[str, Any]) -> str:
    severity = str(row.get("diagnostic_severity") or row.get("operator_severity") or "").casefold()
    status = str(row.get("diagnostic_status") or row.get("state") or "").casefold()
    recommendation = str(row.get("drain_recommendation") or "").casefold()
    if severity == "error" or recommendation == "do_not_drain" or status in {"unreadable_manifest", "invalid_manifest"}:
        return "blocked"
    if severity == "warning" or recommendation == "review_before_drain" or row.get("ready_to_drain") is False:
        return "warning"
    return "match"


def _drain_status(item: Mapping[str, Any]) -> str:
    status = str(item.get("status") or item.get("result") or "").casefold()
    if item.get("error") or status in {"error", "failed", "failure", "stopped"}:
        return "blocked"
    if status in {"succeeded", "success", "already_published", "published"}:
        return "match"
    if status in {"skipped", "deferred", "remaining"}:
        return "warning"
    return "warning"


def _signal_label(signal: str) -> str:
    return {
        "pending_destination_overlap": "Exact completed output -> pending destination",
        "completed_source_still_pending": "Exact completed source -> pending source",
        "drain_summary_output_proof": "Completed output in durable drain summary",
        "drain_summary_source_proof": "Completed source in durable drain summary",
        "same_leaf_hint": "Same-leaf duplicate-title hint",
        "missing_output_still_pending": "Missing completed output still parked",
        "missing_output_with_drain_proof": "Missing completed output with durable drain proof",
        "missing_output_without_proof": "Missing completed output without pending/drain proof",
    }.get(signal, signal or "Review")


def _safe_action(signal: str, status: str) -> str:
    if signal == "missing_output_still_pending":
        return "Treat as deferred-publish or stale Completed proof; inspect Pending Publish and do not rerun, clean up, or delete until the parked payload is explained."
    if signal == "missing_output_with_drain_proof":
        return "Treat as final-placement conflict; compare output folder, durable drain summary, Run Logs, and Last Stderr before rerun or cleanup."
    if signal == "missing_output_without_proof":
        return "Open Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun; empty pending state is not publish proof."
    if signal == "same_leaf_hint":
        return "Treat as duplicate-title guidance only; compare folders before cleanup, rerun, or deletion."
    if status == "blocked":
        return "Inspect blocker evidence before retrying drain, rerun, cleanup, or output deletion."
    if signal in {"pending_destination_overlap", "completed_source_still_pending"}:
        return "Compare Completed, Pending Publish, and Run Logs before retrying or deleting any output."
    if status == "match":
        return "Use as supporting publish evidence; backend logs and output existence remain authoritative."
    return "Review the evidence and owning pages before acting."


def _indexes(rows: list[Mapping[str, Any]], *, is_drain: bool = False) -> dict[str, dict[str, list[dict[str, Any]]]]:
    destination: dict[str, list[dict[str, Any]]] = {}
    source: dict[str, list[dict[str, Any]]] = {}
    leaf: dict[str, list[dict[str, Any]]] = {}

    def add(target: dict[str, list[dict[str, Any]]], key: str, record: dict[str, Any]) -> None:
        if key:
            target.setdefault(key, []).append(record)

    for index, row in enumerate(rows):
        dest = _pending_destination(row)
        src = _pending_source(row)
        local = _pending_local(row)
        record = {"row": row, "index": index, "destination": dest, "source": src, "local": local, "is_drain": is_drain}
        if _path_looks_absolute(dest):
            add(destination, _normalize_path(dest), record)
        if _path_looks_absolute(src):
            add(source, _normalize_path(src), record)
        add(leaf, _leaf(dest or local), record)
    return {"destination": destination, "source": source, "leaf": leaf}


def _warning_list(completed: Mapping[str, Any], pending: Mapping[str, Any], drain_summary: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    for value in [*(completed.get("warnings") or []), *(pending.get("warnings") or []), *(drain_summary.get("warnings") or [])]:
        text = str(value).strip()
        if text and text not in warnings:
            warnings.append(text)
    if completed.get("error"):
        warnings.append(f"Completed history unavailable: {completed.get('error')}")
    if pending.get("error"):
        warnings.append(f"Pending Publish unavailable: {pending.get('error')}")
    if drain_summary.get("read_error"):
        warnings.append(f"Pending drain summary unreadable: {drain_summary.get('read_error')}")
    return warnings


def publish_reconciliation_from_payloads(
    completed_payload: Mapping[str, Any],
    pending_payload: Mapping[str, Any],
    *,
    limit: Any = 250,
) -> PublishReconciliationDto:
    bounded_limit = publish_reconciliation_limit(limit)
    completed_rows = [row for row in completed_payload.get("rows") or [] if isinstance(row, Mapping)]
    pending_rows = [row for row in pending_payload.get("rows") or [] if isinstance(row, Mapping)]
    drain_summary = pending_payload.get("drain_summary") if isinstance(pending_payload.get("drain_summary"), Mapping) else {}
    drain_items = [item for item in drain_summary.get("items") or [] if isinstance(item, Mapping)]

    pending_index = _indexes(pending_rows)
    drain_index = _indexes(drain_items, is_drain=True)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    counts = {
        "exact_pending_destination_count": 0,
        "exact_pending_source_count": 0,
        "drain_output_count": 0,
        "drain_source_count": 0,
        "same_leaf_hint_count": 0,
        "missing_with_pending_proof_count": 0,
        "missing_with_drain_proof_count": 0,
        "missing_without_proof_count": 0,
    }

    def add_row(
        signal: str,
        completed: Mapping[str, Any],
        *,
        status: str,
        match_path: str = "",
        pending: Mapping[str, Any] | None = None,
        drain_item: Mapping[str, Any] | None = None,
        pending_index_value: int | None = None,
        drain_index_value: int | None = None,
    ) -> None:
        signature = "|".join([
            signal,
            _row_key(completed),
            _row_key(pending),
            _row_key(drain_item, str(drain_index_value or "")),
            match_path,
        ])
        if signature in seen or len(rows) >= bounded_limit:
            return
        seen.add(signature)
        rows.append({
            "signal": signal,
            "signal_label": _signal_label(signal),
            "status": status,
            "completed_row_key": _row_key(completed),
            "completed_title": _completed_label(completed),
            "completed_output": _completed_output(completed),
            "completed_source": _completed_source(completed),
            "pending_row_key": _row_key(pending),
            "pending_title": _pending_label(pending) if pending else "",
            "pending_destination": _pending_destination(pending or {}),
            "pending_source": _pending_source(pending or {}),
            "pending_local": _pending_local(pending or {}),
            "drain_index": drain_index_value,
            "drain_status": str((drain_item or {}).get("status") or ""),
            "match_path": match_path,
            "evidence": _reconciliation_evidence(signal, completed, pending, drain_item, match_path),
            "safe_next_action": _safe_action(signal, status),
            "completed": dict(completed),
            "pending": dict(pending or {}),
            "drain_item": dict(drain_item or {}),
            "pending_index": pending_index_value,
        })
        if signal == "pending_destination_overlap":
            counts["exact_pending_destination_count"] += 1
        elif signal == "completed_source_still_pending":
            counts["exact_pending_source_count"] += 1
        elif signal == "drain_summary_output_proof":
            counts["drain_output_count"] += 1
        elif signal == "drain_summary_source_proof":
            counts["drain_source_count"] += 1
        elif signal == "same_leaf_hint":
            counts["same_leaf_hint_count"] += 1
        elif signal == "missing_output_still_pending":
            counts["missing_with_pending_proof_count"] += 1
        elif signal == "missing_output_with_drain_proof":
            counts["missing_with_drain_proof_count"] += 1
        elif signal == "missing_output_without_proof":
            counts["missing_without_proof_count"] += 1

    for completed_index, completed in enumerate(completed_rows):
        output = _completed_output(completed)
        source = _completed_source(completed)
        output_key = _normalize_path(output)
        source_key = _normalize_path(source)
        exact_matches = 0
        missing_output = _completed_missing_output(completed)

        for record in pending_index["destination"].get(output_key, []):
            add_row(
                "missing_output_still_pending" if missing_output else "pending_destination_overlap",
                completed,
                status="warning" if missing_output and _pending_status(record["row"]) == "match" else _pending_status(record["row"]),
                match_path=record["destination"],
                pending=record["row"],
                pending_index_value=record["index"],
            )
            exact_matches += 1
        for record in pending_index["source"].get(source_key, []):
            add_row(
                "missing_output_still_pending" if missing_output else "completed_source_still_pending",
                completed,
                status="warning" if missing_output and _pending_status(record["row"]) == "match" else _pending_status(record["row"]),
                match_path=record["source"],
                pending=record["row"],
                pending_index_value=record["index"],
            )
            exact_matches += 1
        for record in drain_index["destination"].get(output_key, []):
            drain_status = _drain_status(record["row"])
            add_row(
                "missing_output_with_drain_proof" if missing_output else "drain_summary_output_proof",
                completed,
                status="warning" if missing_output and drain_status == "match" else drain_status,
                match_path=record["destination"],
                drain_item=record["row"],
                drain_index_value=record["index"],
            )
            exact_matches += 1
        for record in drain_index["source"].get(source_key, []):
            drain_status = _drain_status(record["row"])
            add_row(
                "missing_output_with_drain_proof" if missing_output else "drain_summary_source_proof",
                completed,
                status="warning" if missing_output and drain_status == "match" else drain_status,
                match_path=record["source"],
                drain_item=record["row"],
                drain_index_value=record["index"],
            )
            exact_matches += 1

        if exact_matches == 0:
            leaf_key = _leaf(output)
            leaf_records = [*pending_index["leaf"].get(leaf_key, []), *drain_index["leaf"].get(leaf_key, [])]
            for record in leaf_records[:3]:
                add_row(
                    "same_leaf_hint",
                    completed,
                    status="warning",
                    match_path=record.get("destination") or record.get("local") or "",
                    pending=record["row"] if not record.get("is_drain") else None,
                    drain_item=record["row"] if record.get("is_drain") else None,
                    pending_index_value=None if record.get("is_drain") else record["index"],
                    drain_index_value=record["index"] if record.get("is_drain") else None,
                )
            if missing_output:
                add_row(
                    "missing_output_without_proof",
                    completed,
                    status="blocked",
                    match_path=output,
                )

    blocker_count = sum(1 for row in rows if row.get("status") == "blocked")
    warning_count = sum(1 for row in rows if row.get("status") == "warning")
    status = _overall_status(completed_payload, pending_payload, rows)
    warnings = _warning_list(completed_payload, pending_payload, drain_summary)
    summary_lines = _summary_lines(
        status=status,
        completed_payload=completed_payload,
        pending_payload=pending_payload,
        drain_summary=drain_summary,
        completed_rows=completed_rows,
        pending_rows=pending_rows,
        drain_items=drain_items,
        rows=rows,
        counts=counts,
        warnings=warnings,
    )
    return PublishReconciliationDto(
        rows=json_safe(rows),
        summary_lines=summary_lines,
        status=status,
        completed_source=str(completed_payload.get("source") or ""),
        pending_root=str(pending_payload.get("pending_root") or ""),
        drain_summary_path=str(drain_summary.get("path") or ""),
        completed_count=int(completed_payload.get("count") or len(completed_rows)),
        pending_count=int(pending_payload.get("count") or len(pending_rows)),
        drain_item_count=len(drain_items),
        exact_pending_destination_count=counts["exact_pending_destination_count"],
        exact_pending_source_count=counts["exact_pending_source_count"],
        drain_output_count=counts["drain_output_count"],
        drain_source_count=counts["drain_source_count"],
        same_leaf_hint_count=counts["same_leaf_hint_count"],
        missing_with_pending_proof_count=counts["missing_with_pending_proof_count"],
        missing_with_drain_proof_count=counts["missing_with_drain_proof_count"],
        missing_without_proof_count=counts["missing_without_proof_count"],
        warning_count=warning_count,
        blocker_count=blocker_count,
        warnings=warnings,
    )


def _reconciliation_evidence(
    signal: str,
    completed: Mapping[str, Any],
    pending: Mapping[str, Any] | None,
    drain_item: Mapping[str, Any] | None,
    match_path: str,
) -> str:
    bits = []
    if signal == "pending_destination_overlap":
        bits.append("Completed output exactly matches current Pending Publish destination.")
    elif signal == "completed_source_still_pending":
        bits.append("Completed source exactly matches current Pending Publish source.")
    elif signal == "drain_summary_output_proof":
        bits.append("Completed output appears in the latest durable pending drain summary.")
    elif signal == "drain_summary_source_proof":
        bits.append("Completed source appears in the latest durable pending drain summary.")
    elif signal == "same_leaf_hint":
        bits.append("Only filename leaf matches; full normalized paths differ or are missing.")
    elif signal == "missing_output_still_pending":
        bits.append("Completed row reports a missing output, but exact pending publish proof still exists for this source/output.")
    elif signal == "missing_output_with_drain_proof":
        bits.append("Completed row reports a missing output, but exact durable drain-summary proof exists for this source/output.")
    elif signal == "missing_output_without_proof":
        bits.append("Completed row reports a missing output and no exact pending/drain proof matched.")
    if match_path:
        bits.append(f"Path: {match_path}")
    if pending and pending.get("drain_recommendation"):
        bits.append(f"Drain recommendation: {pending.get('drain_recommendation')}")
    if drain_item and drain_item.get("status"):
        bits.append(f"Drain status: {drain_item.get('status')}")
    if completed.get("output_health"):
        bits.append(f"Output health: {completed.get('output_health')}")
    return " ".join(bits)


def _overall_status(completed_payload: Mapping[str, Any], pending_payload: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> str:
    if completed_payload.get("error"):
        return "completed_unavailable"
    if pending_payload.get("error"):
        return "pending_unavailable"
    if not completed_payload.get("rows"):
        return "no_completed_rows"
    if any(row.get("status") == "blocked" for row in rows):
        return "review_blockers"
    if any(row.get("signal") in {"missing_output_still_pending", "missing_output_with_drain_proof"} for row in rows):
        return "review_final_placement"
    if any(row.get("signal") in {"pending_destination_overlap", "completed_source_still_pending"} for row in rows):
        return "review_overlaps"
    if any(row.get("signal") == "same_leaf_hint" for row in rows):
        return "review_leaf_hints"
    if any(row.get("signal") in {"drain_summary_output_proof", "drain_summary_source_proof"} for row in rows):
        return "proof_aligned"
    return "no_overlap"


def _status_label(status: str) -> str:
    return {
        "completed_unavailable": "Completed unavailable",
        "pending_unavailable": "Pending unavailable",
        "no_completed_rows": "No completed rows",
        "review_blockers": "Review blockers",
        "review_final_placement": "Review final placement",
        "review_overlaps": "Review overlaps",
        "review_leaf_hints": "Review leaf hints",
        "proof_aligned": "Proof aligned",
        "no_overlap": "No overlap",
    }.get(status, status or "Unknown")


def _summary_lines(
    *,
    status: str,
    completed_payload: Mapping[str, Any],
    pending_payload: Mapping[str, Any],
    drain_summary: Mapping[str, Any],
    completed_rows: list[Mapping[str, Any]],
    pending_rows: list[Mapping[str, Any]],
    drain_items: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    counts: Mapping[str, int],
    warnings: list[str],
) -> list[str]:
    lines = [
        "Backend publish reconciliation:",
        f"Status: {_status_label(status)}",
        f"Completed rows: {completed_payload.get('count') or len(completed_rows)}",
        f"Pending rows: {pending_payload.get('count') or len(pending_rows)}",
        f"Drain summary items: {len(drain_items)}",
        f"Exact completed output -> pending destination: {counts['exact_pending_destination_count']}",
        f"Exact completed source -> pending source: {counts['exact_pending_source_count']}",
        f"Completed output/source in durable drain summary: {counts['drain_output_count'] + counts['drain_source_count']}",
        f"Missing completed output with pending proof: {counts['missing_with_pending_proof_count']}",
        f"Missing completed output with drain proof: {counts['missing_with_drain_proof_count']}",
        f"Missing completed output without pending/drain proof: {counts['missing_without_proof_count']}",
        f"Same-leaf duplicate-title hints: {counts['same_leaf_hint_count']}",
        f"Rows produced: {len(rows)}",
        f"Last drain summary: {'unreadable' if drain_summary.get('read_error') else 'not found' if drain_summary.get('exists') is False else 'loaded' if drain_summary.get('started_at') or drain_summary.get('completed_at') else 'not loaded'}",
        "",
        "Proof order: Completed Manifest row -> exact output/source path -> current Pending Publish row/state -> latest durable pending drain summary -> Run Logs / Last Stderr.",
        "Boundary: same-leaf rows are duplicate-title hints only; exact normalized paths are stronger evidence.",
        "Mutation guardrail: this backend evidence endpoint is read-only and cannot mark done, repair, rerun, drain, delete, publish, rewrite manifests, or touch media.",
    ]
    if warnings:
        lines.append(f"Warnings: {' | '.join(warnings[:5])}")
    if status == "review_blockers":
        lines.append("First action: inspect blocker rows on Completed, Pending Publish, and Diagnostics before rerun, cleanup, deletion, or another drain.")
    elif status == "review_final_placement":
        lines.append("First action: treat missing-output rows with pending/drain proof as final-placement conflicts; compare output folder, Pending Publish, durable drain summary, Run Logs, and Last Stderr before rerun or cleanup.")
    elif status == "review_overlaps":
        lines.append("First action: review exact overlaps; they can indicate deferred publish, stale pending state, or a failed drain.")
    elif status == "review_leaf_hints":
        lines.append("First action: compare folders before acting; same-leaf matches do not prove the same media file.")
    elif status == "proof_aligned":
        lines.append("First action: use this as supporting evidence, then confirm output existence and logs if a title is missing.")
    elif status == "no_overlap":
        lines.append("First action: no exact publish overlap is visible in backend-loaded payloads. Continue from page-level Completed/Pending evidence.")
    return lines

__all__ = [
    "PUBLISH_RECONCILIATION_SCHEMA_VERSION",
    "publish_reconciliation_limit",
    "publish_reconciliation_from_payloads",
]
