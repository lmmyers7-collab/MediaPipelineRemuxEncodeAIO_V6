"""Validate the logical-block inventory for the legacy reliability suite."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
INVENTORY_PATH = (
    REPO_ROOT
    / "docs"
    / "inventories"
    / "TEST_SUITE_SUBSYSTEM_INVENTORY.v1.json"
)
LEGACY_SCRIPT_PATH = (
    REPO_ROOT
    / "ops"
    / "pipeline"
    / "tests"
    / "Legacy"
    / "Invoke-LegacyDesktopReliabilityRegressionChecks.ps1"
)

SCHEMA_VERSION = "test_suite_subsystem_inventory.v1"
CLASSIFICATIONS = {
    "uniquely_valuable_needing_migration",
    "already_covered_by_focused_tests",
    "obsolete_removed_surface",
    "unclear_preserve",
}
EQUIVALENCE_STATUSES = {"equivalent", "partial", "none", "unknown"}
RUNNABILITY_STATUSES = {"runnable", "conditional", "not_runnable", "unknown"}
REAL_MEDIA_STATUSES = {
    "required",
    "not_required",
    "required_if_behavior_changes",
}
REMOVED_STATUS = "removed"
BLOCK_ID_PATTERN = re.compile(r"^LDRR-(?:STATIC|PS|PY)-[0-9]{3}$")
DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
DISPOSITION_STATUSES = {
    "preserve",
    "migrate_pending",
    "replacement_verified_removal_eligible",
    "obsolete_verified_removal_eligible",
    REMOVED_STATUS,
}
RISK_DOMAINS = {
    "source",
    "scratch",
    "publishing",
    "process_lifecycle",
    "queue",
    "subtitle",
    "audio",
    "shutdown",
    "ffmpeg_media_policy",
    "config_state",
}
HIGH_RISK_DOMAINS = {
    "audio",
    "pending_publish",
    "process_lifecycle",
    "publish",
    "publishing",
    "queue",
    "scratch",
    "shutdown",
    "source",
    "subtitle",
    "subtitles",
}

TOP_LEVEL_KEYS = {
    "schema_version",
    "owner_document",
    "legacy_script",
    "baseline_sha256",
    "block_marker_format",
    "coverage_exclusions",
    "blocks",
}
BLOCK_KEYS = {
    "id",
    "title",
    "legacy_location",
    "domain",
    "risk_domains",
    "behavior_or_invariant",
    "boundary_register_refs",
    "production_surfaces",
    "equivalent_coverage",
    "runnability",
    "fixtures_environment",
    "real_media_requirement",
    "classification",
    "proposed_destination",
    "disposition",
    "evidence",
}
LOCATION_KEYS = {
    "baseline_start_line",
    "baseline_end_line",
    "start_anchor",
    "end_anchor",
    "active",
}
EQUIVALENCE_KEYS = {"status", "paths", "evidence"}
RUNNABILITY_KEYS = {
    "status",
    "checked_command",
    "checked_date",
    "requirements",
    "blockers",
}
FIXTURE_KEYS = {"fixtures", "environment", "temp_writes"}
REAL_MEDIA_KEYS = {"status", "reason"}
DESTINATION_KEYS = {"suite", "path", "rationale"}
DISPOSITION_KEYS = {"status", "change_packet"}
EVIDENCE_KEYS = {"replacement_or_obsolescence", "validation"}
EXCLUSION_KEYS = {"id", "anchor", "reason"}

_ASSERTION_PATTERNS = (
    (
        "powershell_assert",
        re.compile(r"^\s*(?!function\b)(?:&\s*)?Assert-True(?:\s|\()", re.IGNORECASE),
    ),
    (
        "powershell_behavior_check",
        re.compile(
            r"^\s*(?!function\b)(?:&\s*)?Invoke-PowerShellBehaviorCheck(?:\s|\()",
            re.IGNORECASE,
        ),
    ),
    ("python_assert", re.compile(r"^\s*assert(?:\s|\()")),
    (
        "python_raise_assertion_error",
        re.compile(r"^\s*raise\s+AssertionError(?:\s|\()"),
    ),
)


@dataclass(frozen=True)
class InventoryFinding:
    rule_id: str
    path: str
    message: str


@dataclass(frozen=True)
class AssertionLine:
    line_number: int
    text: str
    kind: str


@dataclass(frozen=True)
class _ActiveSpan:
    block_id: str
    start_line: int
    end_line: int


def load_inventory(path: Path = INVENTORY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_assertion_lines(legacy_text: str) -> list[AssertionLine]:
    """Return the assertion-bearing lines governed by the inventory."""

    assertions: list[AssertionLine] = []
    for line_number, line in enumerate(legacy_text.splitlines(), start=1):
        for kind, pattern in _ASSERTION_PATTERNS:
            if pattern.search(line):
                assertions.append(
                    AssertionLine(
                        line_number=line_number,
                        text=line,
                        kind=kind,
                    )
                )
                break
    return assertions


def _add(
    findings: list[InventoryFinding],
    rule_id: str,
    path: str,
    message: str,
) -> None:
    findings.append(InventoryFinding(rule_id, path, message))


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_list(value: object) -> bool:
    return isinstance(value, list)


def _has_content(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return value is not None


def _require_object_keys(
    findings: list[InventoryFinding],
    value: object,
    *,
    path: str,
    keys: set[str],
    rule_id: str,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _add(findings, rule_id, path, "must be an object")
        return None
    missing = sorted(keys - set(value))
    if missing:
        _add(
            findings,
            rule_id,
            path,
            "missing required fields: " + ", ".join(missing),
        )
    unexpected = sorted(set(value) - keys)
    if unexpected:
        _add(
            findings,
            rule_id,
            path,
            "unexpected fields: " + ", ".join(unexpected),
        )
    return value


def _require_list_fields(
    findings: list[InventoryFinding],
    value: dict[str, Any],
    fields: tuple[str, ...],
    *,
    path: str,
    rule_id: str,
) -> None:
    for field in fields:
        if field in value and not _is_list(value[field]):
            _add(findings, rule_id, f"{path}.{field}", "must be a list")


def _require_string_array(
    findings: list[InventoryFinding],
    value: object,
    *,
    path: str,
    rule_id: str,
) -> None:
    if not isinstance(value, list):
        _add(findings, rule_id, path, "must be a list")
        return
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not _is_nonempty_string(item):
            _add(findings, rule_id, f"{path}[{index}]", "must be a non-empty string")
            continue
        if item in seen:
            _add(findings, rule_id, path, f"contains duplicate item: {item}")
        seen.add(item)


def _anchor_offsets(text: str, anchor: str) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        offset = text.find(anchor, cursor)
        if offset < 0:
            return offsets
        offsets.append(offset)
        cursor = offset + max(len(anchor), 1)


def _line_at_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _validation_passed(validation: object) -> bool:
    if not isinstance(validation, list):
        return False
    passed_words = {"green", "pass", "passed", "success", "succeeded"}
    for item in validation:
        if isinstance(item, str):
            words = set(re.findall(r"[a-z]+", item.lower()))
            if words & passed_words:
                return True
        elif isinstance(item, dict):
            for key in ("result", "status", "outcome"):
                result = item.get(key)
                if isinstance(result, str) and result.strip().lower() in passed_words:
                    return True
    return False


def _validate_top_level(
    inventory: object,
    findings: list[InventoryFinding],
) -> dict[str, Any] | None:
    if not isinstance(inventory, dict):
        _add(findings, "TSI002", "inventory", "inventory must be an object")
        return None
    if inventory.get("schema_version") != SCHEMA_VERSION:
        _add(
            findings,
            "TSI001",
            "schema_version",
            f"schema_version must be {SCHEMA_VERSION}",
        )
    missing = sorted(TOP_LEVEL_KEYS - set(inventory))
    if missing:
        _add(
            findings,
            "TSI002",
            "inventory",
            "missing required fields: " + ", ".join(missing),
        )
    unexpected = sorted(set(inventory) - TOP_LEVEL_KEYS)
    if unexpected:
        _add(findings, "TSI002", "inventory", "unexpected fields: " + ", ".join(unexpected))
    expected_paths = {
        "owner_document": "docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md",
        "legacy_script": "ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1",
    }
    for field, expected in expected_paths.items():
        if field in inventory and inventory[field] != expected:
            _add(findings, "TSI004", field, f"must be exactly {expected}")
    if "block_marker_format" in inventory and not _is_nonempty_string(
        inventory["block_marker_format"]
    ):
        _add(findings, "TSI004", "block_marker_format", "must be a non-empty string")
    baseline = inventory.get("baseline_sha256")
    if "baseline_sha256" in inventory and (
        not isinstance(baseline, str)
        or re.fullmatch(r"[0-9a-f]{64}", baseline) is None
    ):
        _add(findings, "TSI004", "baseline_sha256", "must be a 64-character SHA-256 hex digest")
    if "coverage_exclusions" in inventory and not isinstance(
        inventory["coverage_exclusions"], list
    ):
        _add(findings, "TSI004", "coverage_exclusions", "must be a list")
    if "blocks" in inventory and not isinstance(inventory["blocks"], list):
        _add(findings, "TSI003", "blocks", "must be a list")
    elif inventory.get("blocks") == []:
        _add(findings, "TSI003", "blocks", "must contain at least one block")
    return inventory


def _validate_block_shape(
    block: object,
    *,
    index: int,
    findings: list[InventoryFinding],
) -> dict[str, Any] | None:
    path = f"blocks[{index}]"
    if not isinstance(block, dict):
        _add(findings, "TSI005", path, "block must be an object")
        return None
    missing = sorted(BLOCK_KEYS - set(block))
    if missing:
        for field in missing:
            _add(findings, "TSI006", path, f"missing required field: {field}")
    unexpected = sorted(set(block) - BLOCK_KEYS)
    if unexpected:
        _add(findings, "TSI006", path, "unexpected fields: " + ", ".join(unexpected))

    for field in ("id", "title", "domain", "behavior_or_invariant"):
        if field in block and not _is_nonempty_string(block[field]):
            _add(findings, "TSI008", f"{path}.{field}", "must be a non-empty string")
    block_id = block.get("id")
    if isinstance(block_id, str) and BLOCK_ID_PATTERN.fullmatch(block_id) is None:
        _add(findings, "TSI008", f"{path}.id", "does not match the LDRR block ID format")
    for field in ("boundary_register_refs", "production_surfaces"):
        if field in block:
            _require_string_array(
                findings,
                block[field],
                path=f"{path}.{field}",
                rule_id="TSI008",
            )
    risk_domains = block.get("risk_domains")
    if "risk_domains" in block:
        _require_string_array(
            findings,
            risk_domains,
            path=f"{path}.risk_domains",
            rule_id="TSI008",
        )
        if isinstance(risk_domains, list):
            for risk_index, risk_domain in enumerate(risk_domains):
                if isinstance(risk_domain, str) and risk_domain not in RISK_DOMAINS:
                    _add(
                        findings,
                        "TSI008",
                        f"{path}.risk_domains[{risk_index}]",
                        "invalid risk domain",
                    )
    surfaces = block.get("production_surfaces")
    if isinstance(surfaces, list):
        if not surfaces:
            _add(findings, "TSI012", f"{path}.production_surfaces", "must not be empty")

    classification = block.get("classification")
    if classification not in CLASSIFICATIONS:
        _add(
            findings,
            "TSI010",
            f"{path}.classification",
            "classification must be exactly one of: " + ", ".join(sorted(CLASSIFICATIONS)),
        )

    location = _require_object_keys(
        findings,
        block.get("legacy_location"),
        path=f"{path}.legacy_location",
        keys=LOCATION_KEYS,
        rule_id="TSI011",
    )
    if location is not None:
        for field in ("baseline_start_line", "baseline_end_line"):
            value = location.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                _add(findings, "TSI011", f"{path}.legacy_location.{field}", "must be a positive integer")
        start_line = location.get("baseline_start_line")
        end_line = location.get("baseline_end_line")
        if isinstance(start_line, int) and isinstance(end_line, int) and start_line > end_line:
            _add(findings, "TSI011", f"{path}.legacy_location", "baseline line range is reversed")
        for field in ("start_anchor", "end_anchor"):
            if field in location and not _is_nonempty_string(location[field]):
                _add(findings, "TSI011", f"{path}.legacy_location.{field}", "must be a non-empty string")
        if "active" in location and not isinstance(location["active"], bool):
            _add(findings, "TSI011", f"{path}.legacy_location.active", "must be a boolean")

    equivalence = _require_object_keys(
        findings,
        block.get("equivalent_coverage"),
        path=f"{path}.equivalent_coverage",
        keys=EQUIVALENCE_KEYS,
        rule_id="TSI013",
    )
    if equivalence is not None:
        if equivalence.get("status") not in EQUIVALENCE_STATUSES:
            _add(findings, "TSI013", f"{path}.equivalent_coverage.status", "invalid equivalence status")
        _require_list_fields(
            findings,
            equivalence,
            ("paths", "evidence"),
            path=f"{path}.equivalent_coverage",
            rule_id="TSI013",
        )
        for field in ("paths", "evidence"):
            if field in equivalence:
                _require_string_array(
                    findings,
                    equivalence[field],
                    path=f"{path}.equivalent_coverage.{field}",
                    rule_id="TSI013",
                )
        if equivalence.get("status") == "equivalent" and (
            not _has_content(equivalence.get("paths"))
            or not _has_content(equivalence.get("evidence"))
        ):
            _add(
                findings,
                "TSI013",
                f"{path}.equivalent_coverage",
                "equivalent coverage requires paths and evidence",
            )

    runnability = _require_object_keys(
        findings,
        block.get("runnability"),
        path=f"{path}.runnability",
        keys=RUNNABILITY_KEYS,
        rule_id="TSI014",
    )
    if runnability is not None:
        if runnability.get("status") not in RUNNABILITY_STATUSES:
            _add(findings, "TSI014", f"{path}.runnability.status", "invalid runnability status")
        if "checked_command" in runnability and not _is_nonempty_string(
            runnability["checked_command"]
        ):
            _add(findings, "TSI014", f"{path}.runnability.checked_command", "must be a non-empty string")
        checked_date = runnability.get("checked_date")
        if not isinstance(checked_date, str):
            _add(findings, "TSI014", f"{path}.runnability.checked_date", "must be a date string")
        elif DATE_PATTERN.fullmatch(checked_date) is None:
            _add(findings, "TSI014", f"{path}.runnability.checked_date", "must be an ISO full-date")
        else:
            try:
                dt.date.fromisoformat(checked_date)
            except ValueError:
                _add(findings, "TSI014", f"{path}.runnability.checked_date", "must be a valid ISO full-date")
        _require_list_fields(
            findings,
            runnability,
            ("requirements", "blockers"),
            path=f"{path}.runnability",
            rule_id="TSI014",
        )
        for field in ("requirements", "blockers"):
            if field in runnability:
                _require_string_array(
                    findings,
                    runnability[field],
                    path=f"{path}.runnability.{field}",
                    rule_id="TSI014",
                )

    fixtures = _require_object_keys(
        findings,
        block.get("fixtures_environment"),
        path=f"{path}.fixtures_environment",
        keys=FIXTURE_KEYS,
        rule_id="TSI015",
    )
    if fixtures is not None:
        _require_list_fields(
            findings,
            fixtures,
            ("fixtures", "environment", "temp_writes"),
            path=f"{path}.fixtures_environment",
            rule_id="TSI015",
        )
        for field in ("fixtures", "environment", "temp_writes"):
            if field in fixtures:
                _require_string_array(
                    findings,
                    fixtures[field],
                    path=f"{path}.fixtures_environment.{field}",
                    rule_id="TSI015",
                )

    real_media = _require_object_keys(
        findings,
        block.get("real_media_requirement"),
        path=f"{path}.real_media_requirement",
        keys=REAL_MEDIA_KEYS,
        rule_id="TSI016",
    )
    if real_media is not None:
        if real_media.get("status") not in REAL_MEDIA_STATUSES:
            _add(findings, "TSI016", f"{path}.real_media_requirement.status", "invalid real-media status")
        if "reason" in real_media and not _is_nonempty_string(real_media["reason"]):
            _add(findings, "TSI016", f"{path}.real_media_requirement.reason", "must be a non-empty string")

    destination = _require_object_keys(
        findings,
        block.get("proposed_destination"),
        path=f"{path}.proposed_destination",
        keys=DESTINATION_KEYS,
        rule_id="TSI017",
    )
    if destination is not None:
        for field in DESTINATION_KEYS:
            if field in destination and not _is_nonempty_string(destination[field]):
                _add(findings, "TSI017", f"{path}.proposed_destination.{field}", "must be a non-empty string")

    disposition = _require_object_keys(
        findings,
        block.get("disposition"),
        path=f"{path}.disposition",
        keys=DISPOSITION_KEYS,
        rule_id="TSI017",
    )
    if disposition is not None:
        for field in DISPOSITION_KEYS:
            if field in disposition and not _is_nonempty_string(disposition[field]):
                _add(findings, "TSI017", f"{path}.disposition.{field}", "must be a non-empty string")
        if disposition.get("status") not in DISPOSITION_STATUSES:
            _add(findings, "TSI017", f"{path}.disposition.status", "invalid disposition status")

    evidence = _require_object_keys(
        findings,
        block.get("evidence"),
        path=f"{path}.evidence",
        keys=EVIDENCE_KEYS,
        rule_id="TSI017",
    )
    if evidence is not None:
        _require_list_fields(
            findings,
            evidence,
            ("replacement_or_obsolescence", "validation"),
            path=f"{path}.evidence",
            rule_id="TSI017",
        )
        for field in ("replacement_or_obsolescence", "validation"):
            if field in evidence:
                _require_string_array(
                    findings,
                    evidence[field],
                    path=f"{path}.evidence.{field}",
                    rule_id="TSI017",
                )

    risk_domains = block.get("risk_domains")
    if isinstance(risk_domains, list):
        normalized_risks = {
            str(item).strip().lower().replace("-", "_").replace(" ", "_")
            for item in risk_domains
        }
        if normalized_risks & HIGH_RISK_DOMAINS and not _has_content(
            block.get("boundary_register_refs")
        ):
            _add(
                findings,
                "TSI030",
                f"{path}.boundary_register_refs",
                "high-risk blocks require at least one no-touch boundary reference",
            )
    return block


def _validate_exclusions(
    exclusions: object,
    *,
    legacy_text: str,
    assertions_by_line: dict[int, AssertionLine],
    findings: list[InventoryFinding],
) -> dict[int, list[str]]:
    coverage: dict[int, list[str]] = {}
    if not isinstance(exclusions, list):
        return coverage
    seen_ids: set[str] = set()
    for index, exclusion in enumerate(exclusions):
        path = f"coverage_exclusions[{index}]"
        value = _require_object_keys(
            findings,
            exclusion,
            path=path,
            keys=EXCLUSION_KEYS,
            rule_id="TSI018",
        )
        if value is None:
            continue
        exclusion_id = value.get("id")
        anchor = value.get("anchor")
        reason = value.get("reason")
        for field, field_value in (("id", exclusion_id), ("anchor", anchor), ("reason", reason)):
            if not _is_nonempty_string(field_value):
                _add(findings, "TSI018", f"{path}.{field}", "must be a non-empty string")
        if not _is_nonempty_string(exclusion_id) or not _is_nonempty_string(anchor):
            continue
        if exclusion_id in seen_ids:
            _add(findings, "TSI018", path, f"duplicate exclusion id: {exclusion_id}")
        seen_ids.add(exclusion_id)
        offsets = _anchor_offsets(legacy_text, anchor)
        if len(offsets) != 1:
            _add(
                findings,
                "TSI019",
                path,
                f"exclusion anchor must occur exactly once; found {len(offsets)}",
            )
            continue
        line_number = _line_at_offset(legacy_text, offsets[0])
        if line_number not in assertions_by_line:
            _add(findings, "TSI019", path, "exclusion anchor is not on an assertion-bearing line")
            continue
        coverage.setdefault(line_number, []).append(f"exclusion:{exclusion_id}")
    return coverage


def _active_span(
    block: dict[str, Any],
    *,
    index: int,
    legacy_text: str,
    findings: list[InventoryFinding],
) -> _ActiveSpan | None:
    location = block.get("legacy_location")
    if not isinstance(location, dict) or location.get("active") is not True:
        return None
    start_anchor = location.get("start_anchor")
    end_anchor = location.get("end_anchor")
    if not _is_nonempty_string(start_anchor) or not _is_nonempty_string(end_anchor):
        return None
    block_id = str(block.get("id") or f"blocks[{index}]")
    start_offsets = _anchor_offsets(legacy_text, start_anchor)
    end_offsets = _anchor_offsets(legacy_text, end_anchor)
    if not start_offsets:
        _add(findings, "TSI020", block_id, "active start anchor was not found")
    elif len(start_offsets) > 1:
        _add(findings, "TSI021", block_id, f"active start anchor occurs {len(start_offsets)} times")
    if not end_offsets:
        _add(findings, "TSI020", block_id, "active end anchor was not found")
    elif len(end_offsets) > 1:
        _add(findings, "TSI021", block_id, f"active end anchor occurs {len(end_offsets)} times")
    if len(start_offsets) != 1 or len(end_offsets) != 1:
        return None
    start_offset = start_offsets[0]
    end_offset = end_offsets[0]
    if start_offset > end_offset:
        _add(findings, "TSI022", block_id, "active block start anchor occurs after its end anchor")
        return None
    return _ActiveSpan(
        block_id=block_id,
        start_line=_line_at_offset(legacy_text, start_offset),
        end_line=_line_at_offset(legacy_text, end_offset + len(end_anchor) - 1),
    )


def _validate_removal_gate(
    block: dict[str, Any],
    *,
    index: int,
    findings: list[InventoryFinding],
) -> None:
    path = str(block.get("id") or f"blocks[{index}]")
    location = block.get("legacy_location")
    disposition = block.get("disposition")
    if not isinstance(location, dict) or not isinstance(disposition, dict):
        return
    active = location.get("active")
    status = disposition.get("status")
    removed = active is False or status == REMOVED_STATUS
    if isinstance(active, bool) and ((active and status == REMOVED_STATUS) or (not active and status != REMOVED_STATUS)):
        _add(
            findings,
            "TSI026",
            path,
            "legacy_location.active and disposition.status=removed must agree",
        )
    if not removed:
        return
    evidence = block.get("evidence")
    replacement_or_obsolescence = (
        evidence.get("replacement_or_obsolescence") if isinstance(evidence, dict) else None
    )
    validation = evidence.get("validation") if isinstance(evidence, dict) else None
    if not _has_content(replacement_or_obsolescence) or not _has_content(validation):
        _add(
            findings,
            "TSI027",
            path,
            "removed blocks must retain replacement or obsolescence evidence and validation",
        )
    classification = block.get("classification")
    if classification == "unclear_preserve":
        _add(findings, "TSI029", path, "unclear_preserve blocks cannot be removed")
    if classification in {
        "uniquely_valuable_needing_migration",
        "already_covered_by_focused_tests",
    }:
        equivalent = block.get("equivalent_coverage")
        has_equivalent = (
            isinstance(equivalent, dict)
            and equivalent.get("status") == "equivalent"
            and _has_content(equivalent.get("paths"))
            and _has_content(equivalent.get("evidence"))
        )
        if not has_equivalent or not _validation_passed(validation):
            _add(
                findings,
                "TSI028",
                path,
                "removed unique/covered blocks require equivalent focused coverage and a passed replacement validation",
            )
    elif classification == "obsolete_removed_surface" and not _validation_passed(validation):
        _add(
            findings,
            "TSI027",
            path,
            "removed obsolete blocks require passed validation of the obsolescence evidence",
        )


def validate_inventory(
    inventory: object,
    *,
    legacy_text: str,
) -> list[InventoryFinding]:
    """Validate schema, anchors, assertion coverage, and removal evidence."""

    findings: list[InventoryFinding] = []
    value = _validate_top_level(inventory, findings)
    if value is None:
        return findings
    assertions = find_assertion_lines(legacy_text)
    assertions_by_line = {item.line_number: item for item in assertions}
    coverage = _validate_exclusions(
        value.get("coverage_exclusions"),
        legacy_text=legacy_text,
        assertions_by_line=assertions_by_line,
        findings=findings,
    )

    blocks = value.get("blocks")
    if not isinstance(blocks, list):
        blocks = []
    seen_ids: set[str] = set()
    spans: list[_ActiveSpan] = []
    for index, raw_block in enumerate(blocks):
        block = _validate_block_shape(raw_block, index=index, findings=findings)
        if block is None:
            continue
        block_id = block.get("id")
        if _is_nonempty_string(block_id):
            if block_id in seen_ids:
                _add(findings, "TSI007", f"blocks[{index}]", f"duplicate block id: {block_id}")
            seen_ids.add(block_id)
        _validate_removal_gate(block, index=index, findings=findings)
        span = _active_span(
            block,
            index=index,
            legacy_text=legacy_text,
            findings=findings,
        )
        if span is not None:
            for previous in spans:
                if span.start_line <= previous.end_line and previous.start_line <= span.end_line:
                    _add(
                        findings,
                        "TSI023",
                        span.block_id,
                        f"active block overlaps {previous.block_id}",
                    )
            spans.append(span)
            for assertion in assertions:
                if span.start_line <= assertion.line_number <= span.end_line:
                    coverage.setdefault(assertion.line_number, []).append(f"block:{span.block_id}")

    for assertion in assertions:
        owners = coverage.get(assertion.line_number, [])
        if not owners:
            _add(
                findings,
                "TSI024",
                f"legacy:{assertion.line_number}",
                f"uncovered {assertion.kind}: {assertion.text.strip()}",
            )
        elif len(owners) > 1:
            _add(
                findings,
                "TSI025",
                f"legacy:{assertion.line_number}",
                "assertion is covered more than once: " + ", ".join(owners),
            )
    return findings


def render_findings(findings: list[InventoryFinding]) -> str:
    lines = ["Test-suite subsystem inventory validation failed:"]
    for finding in findings:
        lines.append(f"- {finding.rule_id}: {finding.path}: {finding.message}")
    return "\n".join(lines)


def _json_output(findings: list[InventoryFinding], *, legacy_text: str) -> str:
    assertions = find_assertion_lines(legacy_text)
    return json.dumps(
        {
            "ok": not findings,
            "assertion_line_count": len(assertions),
            "findings": [asdict(finding) for finding in findings],
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--legacy-script", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    args = parser.parse_args(argv)

    try:
        inventory = load_inventory(args.inventory)
    except (OSError, json.JSONDecodeError) as exc:
        finding = InventoryFinding("TSI000", str(args.inventory), f"unable to load inventory: {exc}")
        if args.json:
            print(json.dumps({"ok": False, "findings": [asdict(finding)]}, indent=2))
        else:
            print(render_findings([finding]), file=sys.stderr)
        return 1

    legacy_path = args.legacy_script
    if legacy_path is None:
        configured = inventory.get("legacy_script")
        legacy_path = REPO_ROOT / configured if isinstance(configured, str) else LEGACY_SCRIPT_PATH
    try:
        legacy_text = legacy_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        finding = InventoryFinding("TSI000", str(legacy_path), f"unable to load legacy script: {exc}")
        if args.json:
            print(json.dumps({"ok": False, "findings": [asdict(finding)]}, indent=2))
        else:
            print(render_findings([finding]), file=sys.stderr)
        return 1

    findings = validate_inventory(inventory, legacy_text=legacy_text)
    if args.json:
        print(_json_output(findings, legacy_text=legacy_text))
    elif findings:
        print(render_findings(findings), file=sys.stderr)
    else:
        assertion_count = len(find_assertion_lines(legacy_text))
        try:
            inventory_label = args.inventory.relative_to(REPO_ROOT)
        except ValueError:
            inventory_label = args.inventory
        print(f"OK: {inventory_label} maps {assertion_count} assertion-bearing lines exactly once.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
