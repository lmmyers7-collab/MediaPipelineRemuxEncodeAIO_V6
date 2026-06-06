from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import uuid
from typing import Any, Iterable, Mapping

from mediapipeline.core.completed.policy import completed_record_key
from mediapipeline.core.config.library_profiles import library_profiles_from_config
from mediapipeline.core.kernel.config_keys import (
    KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED,
    KEY_FINAL_LIBRARY_PROMOTION_ENABLED,
    KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING,
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE,
    KEY_OUTSOURCE,
)
from mediapipeline.desktop.models import CompletedJobRecord, ResolvedPaths

from .promotion_parts.cleanup import cleanup_verified_files
from .promotion_parts.planning import (
    destination_for_output,
    match_library_profile_for_source,
    match_rule_for_source,
    normalized_path_key,
    path_within_root,
    plan_promotion_file_targets,
    relative_path_under_root,
)
from .promotion_parts.results import (
    default_promotion_row_fields,
    promotion_row_counts,
    promotion_status_warnings,
    row_promoted_fields,
    status_label,
    utc_now_text,
)
from .promotion_parts.transfer import (
    companion_sidecars,
    copy_files_transactionally,
    copy_file_with_verification,
    sha256_file,
    verify_copy,
)


FINAL_LIBRARY_PROMOTION_STATUS_SCHEMA_VERSION = "desktop_final_library_promotion_status.v1"
FINAL_LIBRARY_PROMOTION_RUN_SCHEMA_VERSION = "final_library_promotion_run.v1"
FINAL_LIBRARY_PROMOTION_ITEM_SCHEMA_VERSION = "final_library_promotion_item.v1"
FINAL_LIBRARY_PROMOTION_STATE_FOLDER = "FinalLibraryPromotion"
ITEM_EVIDENCE_FILE = "items.json"
ACTIVE_RUN_FILE = "active_run.json"
CONSECUTIVE_FAILURE_LIMIT = 3


@dataclass(frozen=True)
class PromotionRule:
    id: str
    label: str
    enabled: bool
    source_root: Path
    destination_root: Path

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "enabled": self.enabled,
            "source_root": str(self.source_root),
            "destination_root": str(self.destination_root),
        }


@dataclass(frozen=True)
class LibraryPromotionProfile:
    id: str
    label: str
    enabled: bool
    designation: str
    source_root: Path | None = None
    output_root: Path | None = None
    promotion_enabled: bool = False
    promotion_destination: Path | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "enabled": self.enabled,
            "designation": self.designation,
            "source_root": str(self.source_root or ""),
            "output_root": str(self.output_root or ""),
            "promotion_enabled": self.promotion_enabled,
            "promotion_destination": str(self.promotion_destination or ""),
        }


@dataclass(frozen=True)
class PromotionSettingsSnapshot:
    enabled: bool
    rules: list[PromotionRule] = field(default_factory=list)
    library_profiles: list[LibraryPromotionProfile] = field(default_factory=list)
    verification_mode: str = "cautious"
    cleanup_after_verified: bool = False
    overwrite_existing: bool = False
    publish_root: Path | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "verification_mode": self.verification_mode,
            "cleanup_after_verified": self.cleanup_after_verified,
            "overwrite_existing": self.overwrite_existing,
            "publish_root": str(self.publish_root or ""),
            "rules": [rule.to_mapping() for rule in self.rules],
            "library_profiles": [profile.to_mapping() for profile in self.library_profiles],
        }


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, int | float):
        return value != 0
    text = str(value).strip().casefold()
    if not text:
        return default
    return text in {"1", "true", "yes", "on", "enabled", "enable"}


def _rule_text(rule: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = rule.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _coerce_rules(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, "", False):
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        raw = json.loads(text)
    if isinstance(raw, Mapping):
        raw = [raw]
    if not isinstance(raw, Iterable) or isinstance(raw, (bytes, bytearray, str)):
        return []
    rules: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping):
            rules.append(dict(item))
    return rules


def normalize_promotion_rules(raw: Any) -> list[PromotionRule]:
    rules: list[PromotionRule] = []
    for index, rule in enumerate(_coerce_rules(raw), start=1):
        source_text = _rule_text(rule, "source_root", "sourceRoot", "source", "SourceRoot")
        destination_text = _rule_text(
            rule,
            "destination_root",
            "destinationRoot",
            "destination",
            "DestinationRoot",
        )
        label = _rule_text(rule, "label", "name", "Label") or f"Rule {index}"
        seed = "|".join([label, source_text, destination_text]).encode("utf-8", errors="replace")
        rule_id = _rule_text(rule, "id", "rule_id", "RuleId") or hashlib.sha256(seed).hexdigest()[:12]
        if not source_text or not destination_text:
            continue
        rules.append(
            PromotionRule(
                id=rule_id,
                label=label,
                enabled=_bool_value(rule.get("enabled", True), True),
                source_root=Path(source_text),
                destination_root=Path(destination_text),
            )
        )
    return rules


def normalize_library_promotion_profiles(config: Mapping[str, Any]) -> list[LibraryPromotionProfile]:
    profiles: list[LibraryPromotionProfile] = []
    try:
        raw_profiles = library_profiles_from_config(config)
    except Exception:
        return profiles
    for profile in raw_profiles:
        source_text = str(profile.get("source_path") or "").strip()
        output_text = str(profile.get("output_path") or "").strip()
        destination_text = str(profile.get("promotion_destination") or "").strip()
        profiles.append(
            LibraryPromotionProfile(
                id=str(profile.get("id") or ""),
                label=str(profile.get("name") or profile.get("id") or ""),
                enabled=_bool_value(profile.get("enabled", True), True),
                designation=str(profile.get("designation") or ""),
                source_root=Path(source_text) if source_text else None,
                output_root=Path(output_text) if output_text else None,
                promotion_enabled=_bool_value(profile.get("promotion_enabled", False), False),
                promotion_destination=Path(destination_text) if destination_text else None,
            )
        )
    return profiles


def promotion_settings_from_config(config: Mapping[str, Any]) -> PromotionSettingsSnapshot:
    mode = str(config.get(KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE, "cautious") or "cautious").strip().casefold()
    if mode not in {"fast", "cautious"}:
        mode = "cautious"
    publish_root_text = str(config.get(KEY_OUTSOURCE, "") or "").strip()
    library_profiles = normalize_library_promotion_profiles(config)
    profile_promotion_enabled = any(
        profile.enabled and profile.promotion_enabled
        for profile in library_profiles
    )
    return PromotionSettingsSnapshot(
        enabled=_bool_value(config.get(KEY_FINAL_LIBRARY_PROMOTION_ENABLED, False), False) or profile_promotion_enabled,
        rules=normalize_promotion_rules(config.get(KEY_FINAL_LIBRARY_PROMOTION_RULES)),
        library_profiles=library_profiles,
        verification_mode=mode,
        cleanup_after_verified=_bool_value(
            config.get(KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED, False),
            False,
        ),
        overwrite_existing=_bool_value(
            config.get(KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING, False),
            False,
        ),
        publish_root=Path(publish_root_text) if publish_root_text else None,
    )


def promotion_state_root(resolved: ResolvedPaths) -> Path:
    if resolved.state_root is not None:
        return resolved.state_root / FINAL_LIBRARY_PROMOTION_STATE_FOLDER
    if resolved.local_base is not None:
        return resolved.local_base / "State" / FINAL_LIBRARY_PROMOTION_STATE_FOLDER
    return resolved.app_root / "LocalBase" / "State" / FINAL_LIBRARY_PROMOTION_STATE_FOLDER


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(path)
    finally:
        with contextlib.suppress(OSError):
            if tmp_path.exists():
                tmp_path.unlink()


def read_item_evidence(resolved: ResolvedPaths) -> dict[str, dict[str, Any]]:
    root = promotion_state_root(resolved)
    payload = _read_json(root / ITEM_EVIDENCE_FILE, {})
    if not isinstance(payload, Mapping):
        return {}
    items = payload.get("items", payload)
    if not isinstance(items, Mapping):
        return {}
    return {str(key): dict(value) for key, value in items.items() if isinstance(value, Mapping)}


def write_item_evidence(resolved: ResolvedPaths, items: Mapping[str, Mapping[str, Any]]) -> None:
    root = promotion_state_root(resolved)
    _write_json_atomic(
        root / ITEM_EVIDENCE_FILE,
        {
            "schema_version": FINAL_LIBRARY_PROMOTION_ITEM_SCHEMA_VERSION,
            "updated_at": utc_now_text(),
            "items": {str(key): dict(value) for key, value in items.items()},
        },
    )


def write_active_run(resolved: ResolvedPaths, active_run: Mapping[str, Any] | None) -> None:
    root = promotion_state_root(resolved)
    path = root / ACTIVE_RUN_FILE
    if active_run is None:
        with contextlib.suppress(OSError):
            path.unlink()
        return
    _write_json_atomic(path, dict(active_run))


def write_run_manifest(resolved: ResolvedPaths, run_id: str, payload: Mapping[str, Any]) -> Path:
    root = promotion_state_root(resolved)
    path = root / f"{run_id}.run.json"
    _write_json_atomic(path, dict(payload))
    return path


def write_item_manifest(resolved: ResolvedPaths, run_id: str, row_key: str, payload: Mapping[str, Any]) -> Path:
    root = promotion_state_root(resolved)
    safe_key = hashlib.sha256(row_key.encode("utf-8", errors="replace")).hexdigest()[:16]
    path = root / f"{run_id}.{safe_key}.item.json"
    _write_json_atomic(path, dict(payload))
    return path


def _pending_path_keys(pending_payload: Mapping[str, Any] | None) -> set[str]:
    if not isinstance(pending_payload, Mapping):
        return set()
    keys: set[str] = set()
    for row in pending_payload.get("rows") or ():
        if not isinstance(row, Mapping):
            continue
        values = [
            row.get("source"),
            row.get("source_path"),
            row.get("server_out"),
            row.get("destination"),
            row.get("destination_path"),
            row.get("local_file"),
            row.get("payload_path"),
            *(row.get("sidecar_paths") or [] if isinstance(row.get("sidecar_paths"), list) else []),
        ]
        for value in values:
            key = normalized_path_key(value)
            if key:
                keys.add(key)
    return keys


def build_promotion_item_rows(
    resolved: ResolvedPaths,
    records: Iterable[CompletedJobRecord],
    *,
    active_run: Mapping[str, Any] | None = None,
    pending_payload: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], PromotionSettingsSnapshot]:
    settings = promotion_settings_from_config(resolved.config_data)
    evidence_items = read_item_evidence(resolved)
    pending_keys = _pending_path_keys(pending_payload)
    active_item_states = active_run.get("item_states", {}) if isinstance(active_run, Mapping) else {}
    if not isinstance(active_item_states, Mapping):
        active_item_states = {}
    rows: list[dict[str, Any]] = []
    publish_root = settings.publish_root

    for record in records:
        row_key = completed_record_key(record)
        output_path = record.output_path
        source_path = record.source_path_text
        evidence = evidence_items.get(row_key, {})
        promoted_fields = row_promoted_fields(evidence)
        row = {
            **default_promotion_row_fields(),
            **promoted_fields,
            "schema_version": FINAL_LIBRARY_PROMOTION_ITEM_SCHEMA_VERSION,
            "row_key": row_key,
            "source_path": source_path,
            "publish_output_path": str(output_path),
            "output_path": str(output_path),
            "output_exists": bool(record.output_exists),
            "lookup_title": record.lookup_title,
            "media_type": record.media_type,
            "output_file": record.output_file,
            "publish_state": record.publish_state,
        }

        status = "ready"
        if row["promoted_cleaned"]:
            status = "promoted_cleaned"
        elif row["promoted"]:
            status = "promoted"
        elif not settings.enabled:
            status = "disabled"
        elif not record.output_exists:
            status = "missing_output"
        elif record.publish_state != "published":
            status = "pending_publish_unresolved"
        elif pending_keys and (
            normalized_path_key(output_path) in pending_keys
            or normalized_path_key(source_path) in pending_keys
        ):
            status = "pending_publish_unresolved"
        else:
            library_profile = match_library_profile_for_source(source_path, settings.library_profiles)
            library_publish_root = library_profile.output_root if library_profile and library_profile.output_root else publish_root
            if library_profile is not None:
                row["library_profile_id"] = library_profile.id
                row["library_profile_label"] = library_profile.label
                row["library_designation"] = library_profile.designation
                row["library_output_root"] = str(library_profile.output_root or "")
            if library_publish_root is None or destination_for_output(output_path, library_publish_root, Path(".")) is None:
                status = "outside_outsource"
            elif (
                library_profile is not None
                and library_profile.promotion_enabled
                and library_profile.promotion_destination is not None
            ):
                destination_path = destination_for_output(
                    output_path,
                    library_publish_root,
                    library_profile.promotion_destination,
                )
                row["final_library_rule_id"] = f"library-profile-{library_profile.id}"
                row["final_library_rule_label"] = library_profile.label
                row["final_library_destination_root"] = str(library_profile.promotion_destination)
                row["final_library_destination_path"] = str(destination_path or "")
                row["destination_root_exists"] = library_profile.promotion_destination.exists()
                if not library_profile.promotion_destination.exists():
                    status = "destination_offline"
                    row["destination_offline"] = True
                else:
                    row["ready_for_promotion"] = True
            else:
                rule = match_rule_for_source(source_path, settings.rules)
                if rule is None:
                    status = "no_destination_rule"
                    row["no_destination_rule"] = True
                else:
                    destination_path = destination_for_output(output_path, library_publish_root, rule.destination_root)
                    row["final_library_rule_id"] = rule.id
                    row["final_library_rule_label"] = rule.label
                    row["final_library_destination_root"] = str(rule.destination_root)
                    row["final_library_destination_path"] = str(destination_path or "")
                    row["destination_root_exists"] = rule.destination_root.exists()
                    if not rule.destination_root.exists():
                        status = "destination_offline"
                        row["destination_offline"] = True
                    else:
                        row["ready_for_promotion"] = True

        active_state = active_item_states.get(row_key)
        if isinstance(active_state, Mapping):
            active_status = str(active_state.get("status") or "").strip()
            if active_status in {"promoting", "paused", "promotion_failed"}:
                status = active_status
                row["promoting"] = active_status == "promoting"
                row["paused"] = active_status == "paused"
                row["promotion_failed"] = active_status == "promotion_failed"
                row["promotion_error"] = str(active_state.get("error") or "")
            elif active_status in {"promoted", "promoted_cleaned"}:
                status = active_status
                row["promoted"] = True
                row["promoted_cleaned"] = active_status == "promoted_cleaned"

        if status == "no_destination_rule":
            row["no_destination_rule"] = True
        elif status == "destination_offline":
            row["destination_offline"] = True
        elif status == "promotion_failed":
            row["promotion_failed"] = True
        elif status == "promoting":
            row["promoting"] = True
        elif status == "paused":
            row["paused"] = True

        row["final_library_promotion_status"] = status
        row["final_library_promotion_status_label"] = status_label(status)
        rows.append(row)

    return rows, settings


def promotion_status_payload(
    resolved: ResolvedPaths,
    records: Iterable[CompletedJobRecord],
    *,
    active_run: Mapping[str, Any] | None = None,
    pending_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows, settings = build_promotion_item_rows(
        resolved,
        records,
        active_run=active_run,
        pending_payload=pending_payload,
    )
    counts = promotion_row_counts(rows)
    warnings = promotion_status_warnings(
        enabled=settings.enabled,
        overwrite_existing=settings.overwrite_existing,
        cleanup_after_verified=settings.cleanup_after_verified,
    )
    return {
        "schema_version": FINAL_LIBRARY_PROMOTION_STATUS_SCHEMA_VERSION,
        "enabled": settings.enabled,
        "verification_mode": settings.verification_mode,
        "cleanup_after_verified": settings.cleanup_after_verified,
        "overwrite_existing": settings.overwrite_existing,
        "publish_root": str(settings.publish_root or ""),
        "library_profiles": [profile.to_mapping() for profile in settings.library_profiles],
        "evidence_root": str(promotion_state_root(resolved)),
        "active_run": dict(active_run or {}),
        "pause_state": str((active_run or {}).get("pause_state") or "idle"),
        "counts": counts,
        "items": rows,
        "item_rows": rows,
        "warnings": warnings,
    }


def promote_item(item: Mapping[str, Any], settings: PromotionSettingsSnapshot) -> dict[str, Any]:
    started_at = utc_now_text()
    output_path = Path(str(item.get("publish_output_path") or item.get("output_path") or ""))
    item_publish_root = str(item.get("library_output_root") or "").strip()
    publish_root = Path(item_publish_root) if item_publish_root else settings.publish_root
    destination_path_text = str(item.get("final_library_destination_path") or "").strip()
    destination_root_text = str(item.get("final_library_destination_root") or "").strip()
    destination_path = Path(destination_path_text) if destination_path_text else None
    evidence: dict[str, Any] = {
        "schema_version": FINAL_LIBRARY_PROMOTION_ITEM_SCHEMA_VERSION,
        "row_key": str(item.get("row_key") or ""),
        "started_at": started_at,
        "source_path": str(item.get("source_path") or ""),
        "publish_output_path": str(output_path),
        "destination_path": str(destination_path or ""),
        "verification_mode": settings.verification_mode,
        "copied_files": [],
        "missing_sidecars": [],
        "overwritten_files": [],
        "rolled_back_files": [],
        "rollback_errors": [],
        "warnings": [],
        "failures": [],
        "success": False,
    }
    if publish_root is None:
        evidence["failures"].append("Publish root is not configured.")
        evidence["completed_at"] = utc_now_text()
        return evidence
    if not output_path.exists():
        evidence["failures"].append("Publish output no longer exists.")
        evidence["completed_at"] = utc_now_text()
        return evidence
    if destination_path is None:
        evidence["failures"].append("Final destination path is not resolved.")
        evidence["completed_at"] = utc_now_text()
        return evidence
    if not destination_root_text:
        evidence["failures"].append("Final destination root is not resolved.")
        evidence["completed_at"] = utc_now_text()
        return evidence

    destination_root = Path(destination_root_text)
    copy_plan = plan_promotion_file_targets(
        output_path,
        publish_root,
        destination_root,
        companion_sidecars(output_path),
    )
    evidence["copy_plan"] = copy_plan.to_mapping()
    if not copy_plan.ok:
        evidence["failures"].extend(copy_plan.failures)
        evidence["completed_at"] = utc_now_text()
        return evidence

    transaction = copy_files_transactionally(
        copy_plan.files,
        destination_root=destination_root,
        verification_mode=settings.verification_mode,
        overwrite_existing=settings.overwrite_existing,
    )
    evidence["rolled_back_files"].extend(transaction.get("rolled_back_files") or [])
    evidence["rollback_errors"].extend(transaction.get("rollback_errors") or [])
    if not transaction.get("ok"):
        evidence["failures"].extend(transaction.get("failures") or [])
        if transaction.get("rollback_errors"):
            evidence["failures"].append(
                {
                    "error": "Promotion transaction failed and rollback had errors.",
                    "rollback_error_count": len(transaction.get("rollback_errors") or []),
                }
            )
        evidence["completed_at"] = utc_now_text()
        return evidence
    evidence["copied_files"].extend(transaction.get("copied_files") or [])
    evidence["overwritten_files"].extend(transaction.get("overwritten_files") or [])

    if settings.cleanup_after_verified:
        evidence["cleanup_result"] = cleanup_verified_files(evidence["copied_files"], publish_root)
        if not evidence["cleanup_result"].get("completed"):
            evidence["failures"].append("Verified promotion completed, but cleanup failed.")
            evidence["completed_at"] = utc_now_text()
            return evidence
    else:
        evidence["cleanup_result"] = {
            "completed": False,
            "skipped": True,
            "reason": "cleanup_after_verified_disabled",
        }

    evidence["success"] = True
    evidence["completed_at"] = utc_now_text()
    return evidence


__all__ = [
    "CONSECUTIVE_FAILURE_LIMIT",
    "FINAL_LIBRARY_PROMOTION_RUN_SCHEMA_VERSION",
    "FINAL_LIBRARY_PROMOTION_STATUS_SCHEMA_VERSION",
    "PromotionRule",
    "PromotionSettingsSnapshot",
    "LibraryPromotionProfile",
    "build_promotion_item_rows",
    "cleanup_verified_files",
    "companion_sidecars",
    "copy_files_transactionally",
    "copy_file_with_verification",
    "default_promotion_row_fields",
    "destination_for_output",
    "match_rule_for_source",
    "match_library_profile_for_source",
    "normalize_promotion_rules",
    "normalize_library_promotion_profiles",
    "promotion_settings_from_config",
    "promotion_state_root",
    "promotion_status_payload",
    "promote_item",
    "read_item_evidence",
    "relative_path_under_root",
    "utc_now_text",
    "verify_copy",
    "write_active_run",
    "write_item_evidence",
    "write_item_manifest",
    "write_run_manifest",
]
