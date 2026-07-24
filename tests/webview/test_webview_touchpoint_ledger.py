from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPO_ROOT / "docs" / "generated" / "WEBVIEW_TOUCHPOINT_LEDGER.json"
SMOKE_MAP_PATH = REPO_ROOT / "docs" / "generated" / "SMOKE_WRAPPER_MAP.json"
AUDIT_DISPOSITION_PATH = (
    REPO_ROOT
    / "docs"
    / "reviews"
    / "comprehensive-production-audit-2026-07-19"
    / "DISPOSITION_LEDGER.md"
)
GENERATOR_PATH = REPO_ROOT / "ops" / "scripts" / "dev" / "generate-webview-touchpoint-ledger.mjs"
REPORT_BEGIN = "<!-- BEGIN WEBVIEW BROWSER CONTROL CLOSURE SUMMARY -->"
REPORT_END = "<!-- END WEBVIEW BROWSER CONTROL CLOSURE SUMMARY -->"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_ledger() -> dict[str, object]:
    return _load_json(LEDGER_PATH)


def _authored_records(ledger: dict[str, object]) -> list[dict[str, object]]:
    return [record for record in ledger["records"] if record["origin"] == "static_control"]


def _reported_closure_summary() -> dict[str, object]:
    text = AUDIT_DISPOSITION_PATH.read_text(encoding="utf-8")
    block = text.split(REPORT_BEGIN, 1)[1].split(REPORT_END, 1)[0]
    match = re.search(r"```json\s*(\{.*?\})\s*```", block, flags=re.DOTALL)
    assert match, "audit disposition ledger is missing the machine-readable closure JSON"
    return json.loads(match.group(1))


def test_touchpoint_ledger_is_current_and_collision_free() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the generated WebView touchpoint ledger check.")

    result = subprocess.run(
        [node, str(GENERATOR_PATH), "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_authored_control_denominator_and_states_are_row_derived() -> None:
    ledger = _load_ledger()
    records = ledger["records"]
    authored = _authored_records(ledger)
    counts = ledger["counts"]
    reconciliation = ledger["inventory_reconciliation"]["authored_controls"]

    assert ledger["schema_version"] == "webview_touchpoint_ledger.v2"
    assert len({record["touchpoint_id"] for record in records}) == len(records)
    assert counts["static_controls"] == len(authored)
    assert counts["static_controls"] == counts["main_static_controls"] + counts["auxiliary_static_controls"]
    assert counts["static_controls"] == counts["id_backed_static_controls"] + counts["semantic_static_controls"]
    assert Counter(record["surface"]["page"] for record in authored) == counts["static_controls_by_surface"]
    assert Counter(record["audit"]["status"] for record in authored) == {
        key: value
        for key, value in counts["authored_controls_by_audit_status"].items()
        if value
    }
    assert Counter(record["disposition"]["closure_class"] for record in authored) == {
        key: value
        for key, value in counts["authored_controls_by_closure_class"].items()
        if value
    }
    assert reconciliation == {
        "source_control_rows": len(authored),
        "ledger_control_rows": len(authored),
        "evidence_state_rows": len(authored),
        "disposition_rows": len(authored),
        "exact_match": True,
    }


def test_every_authored_control_has_stable_identity_and_disposition() -> None:
    authored = _authored_records(_load_ledger())
    required_identity = {
        "page",
        "panel",
        "workflow",
        "dom_id",
        "selector",
        "control_type",
        "backend_route",
        "local_only_behavior",
        "mutation_classification",
        "expected_prerequisite",
        "test_owner",
        "current_evidence_state",
        "disposition",
    }
    allowed_states = {"passed", "blocked", "skipped", "failed", "flaky", "not_run"}

    for record in authored:
        identity = record["control_identity"]
        disposition = record["disposition"]
        assert required_identity <= identity.keys()
        assert identity["page"] and identity["workflow"] and identity["selector"] and identity["control_type"]
        assert bool(identity["backend_route"]) != bool(identity["local_only_behavior"])
        assert identity["expected_prerequisite"] and identity["test_owner"] and identity["disposition"]
        assert identity["current_evidence_state"] in allowed_states
        assert record["label"] and record["classification"]["reason"]
        assert record["expected_transition"] and record["required_evidence"]
        assert disposition["category"] != "unexplained_evidence_gap"
        assert disposition["exact_prerequisite"]
        assert disposition["why_it_matters"]
        assert isinstance(disposition["automation_feasible"], bool)
        assert disposition["automation_scope"]
        assert disposition["next_evidence_action"]
        assert disposition["owner"]
        if disposition["closure_class"] == "manual_native_only":
            assert disposition["manual_recipe"]


def test_inventory_and_browser_catalog_reconciliation_are_disk_derived() -> None:
    ledger = _load_ledger()
    smoke_map = _load_json(SMOKE_MAP_PATH)
    reconciliation = ledger["inventory_reconciliation"]

    assert reconciliation["dom"]["authored_control_ids_missing_from_inventory"] == 0
    assert reconciliation["dom"]["inventory_document_scoped_id_count"] >= reconciliation["dom"]["authored_control_id_count"]
    assert reconciliation["browser_evidence"]["browser_wrapper_count"] == smoke_map["summary"]["browser_wrapper_count"]
    assert reconciliation["browser_evidence"]["browser_test_module_count"] == smoke_map["summary"]["browser_module_count"]
    assert reconciliation["browser_evidence"]["wrapped_browser_test_module_count"] == smoke_map["summary"]["browser_wrapper_backed_module_count"]
    assert len(reconciliation["browser_evidence"]["direct_only_browser_test_modules"]) == smoke_map["summary"]["browser_direct_only_module_count"]
    assert smoke_map["summary"]["drift_finding_count"] == 0


def test_reported_audit_totals_match_every_authored_row() -> None:
    ledger = _load_ledger()
    counts = ledger["counts"]
    report = _reported_closure_summary()["current"]

    assert report["authored_total"] == counts["static_controls"]
    assert report["evidence_state"] == counts["authored_controls_by_audit_status"]
    assert report["closure"] == counts["authored_controls_by_closure_class"]
    assert sum(report["evidence_state"].values()) == report["authored_total"]
    assert sum(report["closure"].values()) == report["authored_total"]


def test_future_network_controls_remain_explicitly_unreachable() -> None:
    authored = _authored_records(_load_ledger())
    future_network = [
        record
        for record in authored
        if "data-network-future-control" in record["locator"]["selector"]
    ]
    assert future_network
    assert all(record["classification"]["status"] == "unreachable" for record in future_network)
    assert all(record["action"]["route"] is None for record in future_network)
    assert all(record["audit"]["status"] == "blocked" for record in future_network)
    assert all(record["disposition"]["closure_class"] == "legitimately_blocked" for record in future_network)


def test_priority_export_controls_keep_distinct_staging_and_command_semantics() -> None:
    authored = _authored_records(_load_ledger())
    launch_scope = next(
        record
        for record in authored
        if record["locator"]["selector"]
        == 'button[data-pipeline-scope-preset="priority_export"]'
    )
    queue_export = next(
        record
        for record in authored
        if record["locator"]["dom_id"] == "queue-priority-export-btn"
    )

    assert launch_scope["action"]["kind"] == "local_staging"
    assert (
        launch_scope["action"]["ownership_classification"]
        == "local-launch-intent-staging"
    )
    assert launch_scope["action"]["route"] is None
    assert queue_export["action"]["kind"] == "api_command"
    assert queue_export["action"]["method"] == "POST"
    assert queue_export["action"]["route"] == "/api/queue/priority-export"
