from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPO_ROOT / "docs" / "generated" / "WEBVIEW_TOUCHPOINT_LEDGER.json"
GENERATOR_PATH = REPO_ROOT / "ops" / "scripts" / "dev" / "generate-webview-touchpoint-ledger.mjs"

EXPECTED_STATIC_BY_SURFACE = {
    "app-shell": 32,
    "completed": 37,
    "diagnostics": 75,
    "home": 49,
    "launch": 36,
    "libraries": 17,
    "maintenance": 30,
    "metrics": 17,
    "network": 82,
    "pending": 31,
    "pipeline-log-window": 3,
    "queue": 98,
    "rename": 39,
    "reports": 87,
    "schedule": 10,
    "settings": 324,
    "settings-save-dialog": 3,
}


def _load_ledger() -> dict[str, object]:
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


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


def test_touchpoint_ledger_has_exact_authored_control_denominator() -> None:
    ledger = _load_ledger()
    records = ledger["records"]
    static_records = [record for record in records if record["origin"] == "static_control"]
    identifiers = [record["touchpoint_id"] for record in records]

    assert ledger["schema_version"] == "webview_touchpoint_ledger.v1"
    assert ledger["counts"]["static_controls"] == 970
    assert ledger["counts"]["main_static_controls"] == 967
    assert ledger["counts"]["auxiliary_static_controls"] == 3
    assert ledger["counts"]["total_touchpoint_instances"] >= 967
    assert ledger["counts"]["id_backed_static_controls"] == 661
    assert ledger["counts"]["semantic_static_controls"] == 309
    assert ledger["counts"]["unclassified"] == 0
    assert len(static_records) == 970
    assert len(identifiers) == len(set(identifiers))
    assert all(record["label"] for record in static_records)
    assert Counter(record["surface"]["page"] for record in static_records) == EXPECTED_STATIC_BY_SURFACE


def test_touchpoint_ledger_classifies_every_authored_control() -> None:
    records = [record for record in _load_ledger()["records"] if record["origin"] == "static_control"]
    classification_counts = Counter(record["classification"]["status"] for record in records)

    assert classification_counts == {
        "safe": 874,
        "safe_reversible": 88,
        "destructive": 2,
        "unreachable": 6,
    }
    assert all(record["classification"]["reason"] for record in records)
    assert all(record["expected_transition"] for record in records)
    assert all(record["required_evidence"] for record in records)
    assert all(record["audit"]["status"] in {"not_run", "passed", "blocked", "skipped", "failed", "flaky"} for record in records)

    future_network = [
        record
        for record in records
        if "data-network-future-control" in record["locator"]["selector"]
    ]
    assert len(future_network) == 6
    assert all(record["classification"]["status"] == "unreachable" for record in future_network)
    assert all(record["action"]["route"] is None for record in future_network)
