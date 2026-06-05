"""Pure trust-field builders for pending-publish DTO rows."""

from __future__ import annotations

from typing import Any, Mapping


def build_pending_publish_row_trust_fields(
    row: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
    *,
    missing_sidecars: int,
    ready_to_drain: bool,
) -> dict[str, Any]:
    status = str(diagnostics.get("diagnostic_status") or "unknown").strip()
    severity = str(diagnostics.get("diagnostic_severity") or "unknown").strip().casefold()
    recommendation = str(diagnostics.get("drain_recommendation") or "review").strip().casefold()
    state = str(row.get("state") or "").strip().casefold()
    issues: list[str] = []
    if recommendation == "do_not_drain":
        issues.append("backend marked do_not_drain")
    if severity == "error":
        issues.append("diagnostic severity is error")
    if row.get("local_exists") is False:
        issues.append("local payload missing")
    if missing_sidecars > 0:
        issues.append(f"{missing_sidecars} missing sidecar{'s' if missing_sidecars != 1 else ''}")
    if state in {"invalid_manifest", "unreadable_manifest", "invalid_contract", "unreadable"} or status in {"invalid_manifest", "unreadable_manifest"}:
        issues.append("manifest unreadable or invalid")
    if state == "orphan_payload" or status == "orphan_payload":
        issues.append("orphan payload")
    if row.get("error"):
        issues.append(f"row error: {row.get('error')}")

    if recommendation == "do_not_drain" or severity == "error":
        trust_state = "do-not-drain"
        safe_action = "Do not drain; inspect pending manifest/payload/sidecar evidence, Last Stderr, and Run Logs first."
    elif issues:
        trust_state = "review-before-drain"
        safe_action = "Review backend-selected row targets before Publish Parked Outputs; backend drain validation remains authoritative."
    elif ready_to_drain:
        trust_state = "ready-looking"
        safe_action = "Use only backend-owned Publish Parked Outputs after page-level validation still agrees."
    else:
        trust_state = "review-before-drain"
        safe_action = "Treat this row as review-needed until a refreshed pending scan marks it ready."

    proof = [
        f"diagnostic={status} / {diagnostics.get('diagnostic_severity') or 'unknown'}",
        f"drain={diagnostics.get('drain_recommendation') or 'review'}",
        f"recovery={diagnostics.get('recovery_class') or 'manual_review'}",
        f"payload={row.get('local_file') or 'not reported'}",
        f"manifest={row.get('manifest_path') or 'not reported'}",
        f"destination={row.get('server_out') or 'not reported'}",
    ]
    diagnostics_targets = ["pending_publish", "run_logs", "last_stderr_log"]
    if trust_state == "do-not-drain" or "manifest unreadable or invalid" in issues:
        diagnostics_targets.append("state")
    return {
        "operator_trust_state": trust_state,
        "primary_concern": "; ".join(issues) if issues else "row has no blocker in the loaded pending publish scan",
        "safe_next_action": safe_action,
        "unsafe_if_ignored": "Draining review or blocker rows can lose parked output context, overwrite the wrong destination, or strand payload/sidecar evidence.",
        "proof_summary": proof,
        "recommended_diagnostics_targets": diagnostics_targets,
    }


__all__ = ["build_pending_publish_row_trust_fields"]
