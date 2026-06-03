from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audit.rerun_file_io import atomic_write_text


DEFAULT_AUDIT_SCORE_POLICY: dict[str, int] = {
    "redownload_bucket": 100,
    "high_issue": 90,
    "rerun_bucket": 60,
    "medium_issue": 40,
    "review_bucket": 20,
    "fallback_issue": 10,
    "redownload_bonus": 100,
    "rerun_bonus": 40,
}
AUDIT_SCORE_POLICY_VERSION = 1
AUDIT_SCORE_MIN = 0
AUDIT_SCORE_MAX = 1000


def normalize_audit_score_policy(raw: Any = None) -> dict[str, int]:
    data = raw if isinstance(raw, dict) else {}
    normalized = dict(DEFAULT_AUDIT_SCORE_POLICY)
    for key in DEFAULT_AUDIT_SCORE_POLICY:
        value = data.get(key, normalized[key])
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = normalized[key]
        normalized[key] = max(AUDIT_SCORE_MIN, min(AUDIT_SCORE_MAX, number))
    return normalized


def read_audit_score_policy(path: Path | None) -> dict[str, int]:
    if path is None or not path.exists():
        return dict(DEFAULT_AUDIT_SCORE_POLICY)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return dict(DEFAULT_AUDIT_SCORE_POLICY)
    if not isinstance(payload, dict):
        return dict(DEFAULT_AUDIT_SCORE_POLICY)
    return normalize_audit_score_policy(payload.get("policy", payload))


def write_audit_score_policy(path: Path, policy: dict[str, Any]) -> dict[str, int]:
    normalized = normalize_audit_score_policy(policy)
    payload = {
        "version": AUDIT_SCORE_POLICY_VERSION,
        "policy": normalized,
    }
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return normalized


def reset_audit_score_policy(path: Path) -> dict[str, int]:
    return write_audit_score_policy(path, dict(DEFAULT_AUDIT_SCORE_POLICY))


def audit_score_policy_payload(path: Path | None) -> dict[str, Any]:
    policy = read_audit_score_policy(path)
    return {
        "schema_version": "desktop_audit_score_policy.v1",
        "path": str(path or ""),
        "policy": policy,
        "defaults": dict(DEFAULT_AUDIT_SCORE_POLICY),
        "min": AUDIT_SCORE_MIN,
        "max": AUDIT_SCORE_MAX,
        "persisted": bool(path and path.exists()),
    }


__all__ = [
    "AUDIT_SCORE_MAX",
    "AUDIT_SCORE_MIN",
    "AUDIT_SCORE_POLICY_VERSION",
    "DEFAULT_AUDIT_SCORE_POLICY",
    "audit_score_policy_payload",
    "normalize_audit_score_policy",
    "read_audit_score_policy",
    "reset_audit_score_policy",
    "write_audit_score_policy",
]
