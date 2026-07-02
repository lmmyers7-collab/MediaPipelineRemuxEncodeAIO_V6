"""Typed launch preflight check helpers."""

from __future__ import annotations

from typing import Any, Literal, TypedDict
from collections.abc import Iterable

PreflightStatus = Literal["ready", "review", "high review", "blocked", "unknown"]


class PreflightCheck(TypedDict, total=False):
    key: str
    label: str
    status: str
    evidence: str
    action: str
    detail: list[Any]
    recovery_actions: list[dict[str, Any]]


def preflight_check(
    key: str,
    label: str,
    status: str,
    evidence: str,
    action: str,
    *,
    detail: list[Any] | None = None,
    recovery_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": key,
        "label": label,
        "status": status,
        "evidence": evidence,
        "action": action,
        "detail": detail or [],
    }
    if recovery_actions:
        row["recovery_actions"] = recovery_actions
    return row


def preflight_status(checks: Iterable[dict[str, Any]]) -> str:
    statuses = {str(check.get("status") or "").casefold() for check in checks}
    if "blocked" in statuses:
        return "blocked"
    if "high review" in statuses:
        return "high review"
    if "review" in statuses:
        return "review"
    if "unknown" in statuses:
        return "unknown"
    return "ready"


def preflight_counts(checks: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for check in checks:
        status = str(check.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def preflight_display_status(status: str) -> str:
    normalized = str(status or "").casefold()
    if normalized == "blocked":
        return "Blocked"
    if normalized == "high review":
        return "High review"
    if normalized == "review":
        return "Review"
    if normalized == "unknown":
        return "Evidence incomplete"
    if normalized == "ready":
        return "Ready"
    return "Evidence incomplete"


__all__ = [
    "PreflightCheck",
    "PreflightStatus",
    "preflight_check",
    "preflight_counts",
    "preflight_display_status",
    "preflight_status",
]
