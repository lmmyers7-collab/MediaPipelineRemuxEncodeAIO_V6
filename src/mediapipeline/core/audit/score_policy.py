from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mediapipeline.core.audit.rerun_file_io import atomic_write_text


DEFAULT_AUDIT_SCORE_BASE_POLICY: dict[str, int] = {
    "redownload_bucket": 100,
    "high_issue": 90,
    "rerun_bucket": 60,
    "medium_issue": 40,
    "review_bucket": 20,
    "fallback_issue": 10,
    "redownload_bonus": 100,
    "rerun_bonus": 40,
}
HIGH_AUDIT_SCORE_MARKERS: tuple[dict[str, str], ...] = (
    {"code": "ffprobe-open-failed", "description": "ffprobe could not open the media file."},
    {"code": "missing-video-stream", "description": "No video stream was found."},
    {"code": "missing-audio-stream", "description": "No audio stream was found."},
    {"code": "audio-multiple-defaults", "description": "More than one audio stream is marked default."},
    {
        "code": "audio-default-policy-mismatch",
        "description": "The default audio stream does not match the saved preferred-language or fidelity policy.",
    },
    {"code": "subtitle-multiple-defaults", "description": "More than one subtitle stream is marked default."},
    {"code": "audio-missing-explicit-default", "description": "No explicit default audio stream was found."},
    {"code": "commentary-default-audio", "description": "A commentary audio stream appears to be the default."},
    {"code": "tx3g-extraction-failed", "description": "TX3G subtitle extraction failed."},
    {"code": "bdpgs-ocr-failed", "description": "BDPGS OCR subtitle conversion failed."},
    {"code": "vobsub-ocr-failed", "description": "VobSub OCR subtitle conversion failed."},
    {"code": "foreign-audio-no-subtitles", "description": "Foreign-language audio was found without subtitle support."},
    {
        "code": "foreign-audio-no-text-subtitles",
        "description": "Foreign-language audio was found without usable text subtitles.",
    },
)
MEDIUM_AUDIT_SCORE_MARKERS: tuple[dict[str, str], ...] = (
    {"code": "multiple-video-streams", "description": "More than one video stream was found."},
    {"code": "audio-track-titles-missing", "description": "One or more audio stream titles are missing."},
    {"code": "subtitle-track-titles-missing", "description": "One or more subtitle stream titles are missing."},
    {"code": "default-audio-language-unknown", "description": "The default audio language is unknown."},
    {"code": "default-subtitle-language-unknown", "description": "The default subtitle language is unknown."},
    {"code": "default-audio-may-transcode", "description": "The default audio stream may trigger transcoding."},
    {"code": "default-ass-subtitle", "description": "An ASS subtitle stream is marked default."},
    {"code": "ass-only-subtitles", "description": "Only ASS subtitles were found."},
    {"code": "tx3g-only-subtitles", "description": "Only TX3G subtitles were found."},
    {"code": "tx3g-subtitles-extractable", "description": "TX3G subtitles look extractable to SRT."},
    {"code": "bdpgs-only-subtitles", "description": "Only BDPGS image subtitles were found."},
    {"code": "bdpgs-subtitles-ocr-candidate", "description": "BDPGS subtitles look like OCR candidates."},
    {"code": "vobsub-only-subtitles", "description": "Only VobSub image subtitles were found."},
    {"code": "vobsub-subtitles-ocr-candidate", "description": "VobSub subtitles look like OCR candidates."},
    {"code": "default-image-subtitle", "description": "An image subtitle stream is marked default."},
    {"code": "image-only-subtitles", "description": "Only image subtitles were found."},
    {"code": "audio-language-tags-unknown", "description": "Audio language tags are unknown."},
    {"code": "subtitle-language-tags-unknown", "description": "Subtitle language tags are unknown."},
    {"code": "ambiguous-tv-naming", "description": "TV naming could not be parsed cleanly."},
)
AUDIT_SCORE_POLICY_VERSION = 2
AUDIT_SCORE_MIN = 0
AUDIT_SCORE_MAX = 1000


def _clamped_score(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(AUDIT_SCORE_MIN, min(AUDIT_SCORE_MAX, number))


def _known_issue_code_groups() -> dict[str, str]:
    groups: dict[str, str] = {}
    for marker in HIGH_AUDIT_SCORE_MARKERS:
        groups[marker["code"]] = "high"
    for marker in MEDIUM_AUDIT_SCORE_MARKERS:
        groups[marker["code"]] = "medium"
    return groups


def _default_issue_code_weights(base_policy: dict[str, int]) -> dict[str, int]:
    weights: dict[str, int] = {}
    for code, group in _known_issue_code_groups().items():
        weights[code] = base_policy["high_issue"] if group == "high" else base_policy["medium_issue"]
    return weights


DEFAULT_AUDIT_SCORE_POLICY: dict[str, Any] = {
    **DEFAULT_AUDIT_SCORE_BASE_POLICY,
    "issue_code_weights": _default_issue_code_weights(DEFAULT_AUDIT_SCORE_BASE_POLICY),
}


def _score_policy_marker_rows() -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = [
        {
            "type": "base",
            "key": "redownload_bucket",
            "label": "Redownload candidate bucket",
            "applies_when": "Any effective issue has bucket REDOWNLOAD_CANDIDATE.",
        },
        {
            "type": "group_default",
            "key": "high_issue",
            "group": "high",
            "label": "High issue-code marker default",
            "applies_when": "Default score for high issue-code markers that do not have an explicit per-code value.",
        },
    ]
    markers.extend(
        {
            "type": "issue_code",
            "code": marker["code"],
            "group": "high",
            "label": f"High issue: {marker['code']}",
            "applies_when": marker["description"],
        }
        for marker in HIGH_AUDIT_SCORE_MARKERS
    )
    markers.extend(
        [
            {
                "type": "base",
                "key": "rerun_bucket",
                "label": "Rerun pipeline bucket",
                "applies_when": "Any remaining effective issue has bucket RERUN_PIPELINE.",
            },
            {
                "type": "group_default",
                "key": "medium_issue",
                "group": "medium",
                "label": "Medium issue-code marker default",
                "applies_when": "Default score for medium issue-code markers that do not have an explicit per-code value.",
            },
        ]
    )
    markers.extend(
        {
            "type": "issue_code",
            "code": marker["code"],
            "group": "medium",
            "label": f"Medium issue: {marker['code']}",
            "applies_when": marker["description"],
        }
        for marker in MEDIUM_AUDIT_SCORE_MARKERS
    )
    markers.extend(
        [
            {
                "type": "base",
                "key": "review_bucket",
                "label": "Review bucket",
                "applies_when": "Any remaining effective issue has bucket REVIEW.",
            },
            {
                "type": "base",
                "key": "fallback_issue",
                "label": "Fallback issue marker",
                "applies_when": "Any effective issue not matched by redownload, high, rerun, medium, or review markers.",
            },
            {
                "type": "base",
                "key": "redownload_bonus",
                "label": "Redownload candidate bonus",
                "applies_when": "Added once when at least one effective REDOWNLOAD_CANDIDATE issue is present.",
            },
            {
                "type": "base",
                "key": "rerun_bonus",
                "label": "Rerun pipeline bonus",
                "applies_when": "Added once when no redownload issue is present and at least one effective RERUN_PIPELINE issue is present.",
            },
        ]
    )
    return markers


def normalize_audit_score_policy(raw: Any = None) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    normalized: dict[str, Any] = dict(DEFAULT_AUDIT_SCORE_BASE_POLICY)
    for key, default in DEFAULT_AUDIT_SCORE_BASE_POLICY.items():
        normalized[key] = _clamped_score(data.get(key, default), default)
    defaults = _default_issue_code_weights(normalized)
    raw_weights = data.get("issue_code_weights")
    if not isinstance(raw_weights, dict):
        raw_weights = {}
    issue_code_weights: dict[str, int] = {}
    for code, default in defaults.items():
        issue_code_weights[code] = _clamped_score(raw_weights.get(code, default), default)
    normalized["issue_code_weights"] = issue_code_weights
    return normalized


def read_audit_score_policy(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return normalize_audit_score_policy()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return normalize_audit_score_policy()
    if not isinstance(payload, dict):
        return normalize_audit_score_policy()
    return normalize_audit_score_policy(payload.get("policy", payload))


def write_audit_score_policy(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_audit_score_policy(policy)
    payload = {
        "version": AUDIT_SCORE_POLICY_VERSION,
        "policy": normalized,
    }
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return normalized


def reset_audit_score_policy(path: Path) -> dict[str, Any]:
    return write_audit_score_policy(path, normalize_audit_score_policy())


def audit_score_policy_payload(path: Path | None) -> dict[str, Any]:
    policy = read_audit_score_policy(path)
    return {
        "schema_version": "desktop_audit_score_policy.v2",
        "path": str(path or ""),
        "policy": policy,
        "defaults": normalize_audit_score_policy(),
        "markers": _score_policy_marker_rows(),
        "min": AUDIT_SCORE_MIN,
        "max": AUDIT_SCORE_MAX,
        "persisted": bool(path and path.exists()),
    }


__all__ = [
    "AUDIT_SCORE_MAX",
    "AUDIT_SCORE_MIN",
    "AUDIT_SCORE_POLICY_VERSION",
    "DEFAULT_AUDIT_SCORE_BASE_POLICY",
    "DEFAULT_AUDIT_SCORE_POLICY",
    "HIGH_AUDIT_SCORE_MARKERS",
    "MEDIUM_AUDIT_SCORE_MARKERS",
    "audit_score_policy_payload",
    "normalize_audit_score_policy",
    "read_audit_score_policy",
    "reset_audit_score_policy",
    "write_audit_score_policy",
]
