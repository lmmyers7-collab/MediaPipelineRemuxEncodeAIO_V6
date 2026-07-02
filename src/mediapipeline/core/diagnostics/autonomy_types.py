"""Typed autonomy health payload helpers."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict
from collections.abc import Iterable, Mapping

AutonomyStatus = Literal["ready", "review", "blocked", "unknown"]
AutonomySeverity = Literal["low", "medium", "high", "critical"]


class AutonomyRecoveryAction(TypedDict, total=False):
    schema_version: str
    kind: str
    label: str
    method: str
    route: str
    request: dict[str, Any]
    requires_confirmation: bool
    frontend_should_autorun: bool
    mutates_media: bool
    mutates_runtime_state: bool
    mutates_queue: NotRequired[bool]
    evidence_path: NotRequired[str]
    safe_next_step: str


class AutonomyIssue(TypedDict, total=False):
    code: str
    category: str
    severity: str
    message: str
    evidence_path: str
    age_seconds: int | None
    next_action: str
    recovery_action: AutonomyRecoveryAction


class AutonomyCategory(TypedDict):
    key: str
    label: str
    status: str
    status_state: str
    metrics: dict[str, Any]
    summary_lines: list[str]
    blockers: list[dict[str, Any]]
    review_items: list[dict[str, Any]]


def status_state(status: str) -> str:
    normalized = str(status or "").casefold()
    if normalized == "blocked":
        return "blocked"
    if normalized in {"review", "high review"}:
        return "warning"
    if normalized == "ready":
        return "ready"
    return "unknown"


def issue_status(blockers: list[dict[str, Any]], review_items: list[dict[str, Any]]) -> str:
    if blockers:
        return "blocked"
    if review_items:
        return "review"
    return "ready"


def overall_status(statuses: Iterable[str]) -> str:
    normalized = {str(status or "").casefold() for status in statuses}
    if "blocked" in normalized:
        return "blocked"
    if "review" in normalized or "unknown" in normalized:
        return "review"
    return "ready"


def category(
    key: str,
    status: str,
    *,
    labels: Mapping[str, str],
    label: str | None = None,
    metrics: Mapping[str, Any] | None = None,
    summary_lines: list[str] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    review_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label or labels.get(key, key.replace("_", " ").title()),
        "status": status,
        "status_state": status_state(status),
        "metrics": dict(metrics or {}),
        "summary_lines": summary_lines or [],
        "blockers": blockers or [],
        "review_items": review_items or [],
    }


def issue(
    code: str,
    category_name: str,
    severity: str,
    message: str,
    *,
    evidence_path: str = "",
    age_seconds: int | float | None = None,
    next_action: str,
    recovery_action: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code,
        "category": category_name,
        "severity": severity,
        "message": message,
        "evidence_path": evidence_path,
        "age_seconds": None if age_seconds is None else int(age_seconds),
        "next_action": next_action,
    }
    if isinstance(recovery_action, Mapping):
        result["recovery_action"] = dict(recovery_action)
    return result


def recovery_action(
    *,
    kind: str,
    label: str,
    method: str,
    route: str,
    request: Mapping[str, Any] | None = None,
    requires_confirmation: bool,
    frontend_should_autorun: bool = False,
    mutates_media: bool = False,
    mutates_runtime_state: bool = False,
    safe_next_step: str,
    evidence_path: str = "",
) -> dict[str, Any]:
    normalized_method = str(method or "").strip().upper()
    normalized_route = str(route or "").strip()
    if normalized_method not in {"GET", "POST"}:
        raise ValueError(f"Unsupported recovery action method: {method}")
    if not normalized_route.startswith("/api/"):
        raise ValueError(f"Recovery action route must be a backend API route: {route}")
    result: dict[str, Any] = {
        "schema_version": "desktop_autonomy_recovery_action.v1",
        "kind": kind,
        "label": label,
        "method": normalized_method,
        "route": normalized_route,
        "request": dict(request or {}),
        "requires_confirmation": bool(requires_confirmation),
        "frontend_should_autorun": bool(frontend_should_autorun),
        "mutates_media": bool(mutates_media),
        "mutates_runtime_state": bool(mutates_runtime_state),
        "safe_next_step": safe_next_step,
    }
    if evidence_path:
        result["evidence_path"] = evidence_path
    return result


__all__ = [
    "AutonomyCategory",
    "AutonomyIssue",
    "AutonomyRecoveryAction",
    "AutonomySeverity",
    "AutonomyStatus",
    "category",
    "issue",
    "issue_status",
    "overall_status",
    "recovery_action",
    "status_state",
]
