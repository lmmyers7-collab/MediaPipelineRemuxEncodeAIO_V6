from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.maintenance import change_ledger as change_ledger_module
from mediapipeline.core.maintenance.change_ledger import change_ledger_payload, python_impact_for_files
from tests.python.desktop.application_facade_test_support import DummyFacadeService, _resolved
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.routes_read import GET_ROUTE_HANDLERS
from mediapipeline.desktop.api.server import LocalApiServer
from mediapipeline.desktop.application import MediaPipelineApplicationFacade


def _packet(change_id: str, **overrides: Any) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "id": change_id,
        "title": "Add ledger",
        "version_target": "0.1.0-dev",
        "status": "complete",
        "type": "feature",
        "risk_level": "medium",
        "date_started": "2026-06-04",
        "date_completed": "2026-06-04",
        "summary": "Add a read-only Maintenance change ledger.",
        "reason": "Operators need one definitive change surface.",
        "affected_areas": ["maintenance", "change_control"],
        "behavior_before": "Change history was scattered.",
        "behavior_after": "Maintenance displays structured change history.",
        "files_touched": [
            "src/mediapipeline/core/maintenance/change_ledger.py",
            "tests/python/desktop/test_maintenance_change_ledger.py",
            "docs/change_control/README.md",
        ],
        "tests_added": ["tests/python/desktop/test_maintenance_change_ledger.py"],
        "manual_validation": ["unit test"],
        "rollback_plan": "Revert the ledger change.",
        "related_changes": [],
        "notes": "Read-only; no media behavior changed.",
    }
    packet.update(overrides)
    return packet


def _write_packet(root: Path, relative: str, packet: dict[str, Any]) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    return path


def _get_json(url: str, token: str | None = None) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class MaintenanceChangeLedgerTests(unittest.TestCase):
    def test_python_impact_groups_touched_python_scripts(self) -> None:
        impact = python_impact_for_files(
            [
                "src/mediapipeline/core/maintenance/change_ledger.py",
                "src/mediapipeline/core/api/commands.py",
                "tests/python/desktop/test_maintenance_change_ledger.py",
                "README.md",
            ]
        )

        self.assertEqual(impact["file_count"], 3)
        self.assertIn("src/mediapipeline/core/maintenance", impact["summary"])
        self.assertIn("tests/python/desktop", impact["summary"])

    def test_change_ledger_loads_unreleased_and_released_packets(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "docs" / "change_control").mkdir(parents=True)
            (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
            (root / "docs" / "change_control" / "CHANGELOG.md").write_text("# Change Log\n", encoding="utf-8")
            (root / "docs" / "change_control" / "CHANGE_INDEX.md").write_text("# Change Index\n", encoding="utf-8")
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001"))
            _write_packet(
                root,
                "ops/release/changes/released/1.0.0/MP-CHANGE-2026-0601-001.json",
                _packet("MP-CHANGE-2026-0601-001", version_target="1.0.0", risk_level="low"),
            )

            payload = change_ledger_payload(root)

        self.assertEqual(payload["schema_version"], "desktop_change_ledger.v1")
        self.assertTrue(payload["read_only"])
        self.assertEqual(payload["counts"]["total"], 2)
        self.assertEqual(payload["counts"]["unreleased"], 1)
        self.assertEqual(payload["counts"]["released"], 1)
        self.assertEqual(payload["coverage"]["scope"], "worktree")
        self.assertEqual(payload["coverage"]["uncovered_count"], 0)
        released = next(row for row in payload["rows"] if row["location"] == "released")
        self.assertEqual(released["release_version"], "1.0.0")
        self.assertIn("src/mediapipeline/core/maintenance", payload["python_impact"]["summary"])

    def test_change_ledger_bounds_rows_without_losing_full_counts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            for index in range(1, 4):
                _write_packet(
                    root,
                    f"ops/release/changes/unreleased/MP-CHANGE-2026-0604-00{index}.json",
                    _packet(f"MP-CHANGE-2026-0604-00{index}"),
                )

            payload = change_ledger_payload(root, row_limit=2)
            all_payload = change_ledger_payload(root, row_limit="all")

        self.assertEqual(payload["counts"]["total"], 3)
        self.assertEqual(payload["row_count"], 3)
        self.assertEqual(payload["returned_row_count"], 2)
        self.assertEqual(payload["row_limit"], 2)
        self.assertEqual(payload["truncated_row_count"], 1)
        self.assertEqual([row["id"] for row in payload["rows"]], ["MP-CHANGE-2026-0604-003", "MP-CHANGE-2026-0604-002"])
        self.assertEqual(all_payload["row_limit"], "all")
        self.assertEqual(all_payload["returned_row_count"], 3)
        self.assertEqual(all_payload["truncated_row_count"], 0)

    def test_change_ledger_reports_uncovered_worktree_paths_as_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001"))
            coverage = change_ledger_module.packet_coverage.CoverageResult(
                scope="worktree",
                available=True,
                changed_files=("README.md",),
                covered_files=(),
                uncovered_files=("README.md",),
                packet_paths=("ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json",),
                errors=(),
            )

            with patch.object(change_ledger_module.packet_coverage, "coverage_for_worktree", return_value=coverage):
                payload = change_ledger_payload(root)

        self.assertEqual(payload["coverage"]["uncovered_count"], 1)
        self.assertEqual(payload["hygiene"]["operator_status"], "review")
        self.assertEqual(payload["hygiene"]["summary_lines"][0], "Unrecorded changed files: 1")
        self.assertEqual(payload["hygiene"]["unrecorded_changes"], ["README.md"])
        self.assertIn("README.md", payload["hygiene"]["issues"][0]["message"])

    def test_change_ledger_reports_invalid_and_incomplete_packets_as_hygiene(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            bad_json = root / "ops" / "release" / "changes" / "unreleased" / "MP-CHANGE-2026-0604-002.json"
            bad_json.parent.mkdir(parents=True)
            bad_json.write_text("{not json", encoding="utf-8")
            _write_packet(
                root,
                "ops/release/changes/unreleased/MP-CHANGE-2026-0604-003.json",
                {"id": "MP-CHANGE-2026-0604-003", "status": "complete"},
            )

            payload = change_ledger_payload(root)

        self.assertEqual(payload["counts"]["total"], 1)
        self.assertEqual(payload["coverage"]["scope"], "worktree")
        self.assertEqual(payload["hygiene"]["operator_status"], "blocked")
        messages = "\n".join(issue["message"] for issue in payload["hygiene"]["issues"])
        self.assertIn("Invalid JSON", messages)
        self.assertIn("Missing required field", messages)

    def test_local_api_exposes_change_ledger_as_token_protected_read_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-001.json", _packet("MP-CHANGE-2026-0604-001"))
            _write_packet(root, "ops/release/changes/unreleased/MP-CHANGE-2026-0604-002.json", _packet("MP-CHANGE-2026-0604-002"))
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="ledger-token",
                resolved_provider=lambda: _resolved(root),
            )
            try:
                server.start()
                denied_status, denied = _get_json(f"{server.url}/api/maintenance/change-ledger")
                ok_status, payload = _get_json(f"{server.url}/api/maintenance/change-ledger?limit=1", token="ledger-token")
            finally:
                server.stop()

        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(ok_status, 200)
        self.assertEqual(payload["schema_version"], "desktop_change_ledger.v1")
        self.assertEqual(payload["counts"]["total"], 2)
        self.assertEqual(payload["row_count"], 2)
        self.assertEqual(payload["returned_row_count"], 1)
        self.assertEqual(payload["truncated_row_count"], 1)
        self.assertIn("coverage", payload)

    def test_change_ledger_route_is_documented_as_read_only(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        self.assertIn("/api/maintenance/change-ledger", GET_ROUTE_HANDLERS)
        self.assertTrue(GET_ROUTE_HANDLERS["/api/maintenance/change-ledger"].needs_query)
        self.assertEqual(routes["/api/maintenance/change-ledger"]["method"], "GET")
        self.assertEqual(routes["/api/maintenance/change-ledger"]["effect"], "none")
        self.assertEqual(routes["/api/maintenance/change-ledger"]["query_keys"], ["limit"])
        self.assertEqual(routes["/api/maintenance/change-ledger"]["response_schema"], "desktop_change_ledger.v1")


if __name__ == "__main__":
    unittest.main()
