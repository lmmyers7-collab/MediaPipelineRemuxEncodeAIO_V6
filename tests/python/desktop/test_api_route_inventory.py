from __future__ import annotations

import re
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT


REPO_ROOT = find_repo_root(Path(__file__))
ROUTE_ROW_PATTERN = re.compile(r"^\|\s*`(GET|POST) (/api/[^`]+)`\s*\|")
ROUTE_COUNT_HEADING_PATTERN = re.compile(r"^(#{2,3})\s+.+?\((?:[^)]*?\u2014\s*)?(\d+) routes\)\s*$")


def _contract_route_keys() -> set[tuple[str, str]]:
    return {(str(route["method"]).upper(), str(route["path"])) for route in LOCAL_API_ROUTE_CONTRACT}


def _contract_route_effects() -> dict[tuple[str, str], str]:
    return {
        (str(route["method"]).upper(), str(route["path"])): str(route["effect"])
        for route in LOCAL_API_ROUTE_CONTRACT
    }


def _contract_effect_routes() -> dict[str, set[tuple[str, str]]]:
    grouped: defaultdict[str, set[tuple[str, str]]] = defaultdict(set)
    for route_key, effect in _contract_route_effects().items():
        grouped[effect].add(route_key)
    return dict(grouped)


def _route_rows_from_markdown(path: Path) -> list[tuple[str, str]]:
    return [
        (match.group(1).upper(), match.group(2))
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := ROUTE_ROW_PATTERN.match(line))
    ]


def _route_keys_from_markdown(path: Path) -> set[tuple[str, str]]:
    return set(_route_rows_from_markdown(path))


def _route_count_sections(path: Path) -> list[tuple[int, int, int]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    sections: list[tuple[int, int, int]] = []
    for index, line in enumerate(lines):
        heading = ROUTE_COUNT_HEADING_PATTERN.match(line)
        if not heading:
            continue
        level = len(heading.group(1))
        declared = int(heading.group(2))
        actual = 0
        for candidate in lines[index + 1 :]:
            next_heading = re.match(r"^(#{1,6})\s+", candidate)
            if next_heading and len(next_heading.group(1)) <= level:
                break
            if ROUTE_ROW_PATTERN.match(candidate):
                actual += 1
        sections.append((index + 1, declared, actual))
    return sections


def _api_inventory_route_effects(path: Path) -> dict[tuple[str, str], str]:
    text = path.read_text(encoding="utf-8")
    return {
        (method.upper(), route): effect
        for method, route, effect in re.findall(
            r"^\|\s*`(GET|POST) (/api/[^`]+)`\s*\|\s*`([^`]+)`\s*\|",
            text,
            flags=re.MULTILINE,
        )
    }


def _normalize_summary_route(token: str, method: str) -> tuple[str, str] | None:
    value = token.strip()
    explicit = re.fullmatch(r"(GET|POST)\s+(/api/\S+)", value)
    if explicit:
        return explicit.group(1), explicit.group(2)
    if not method:
        return None
    if value.startswith("/api/"):
        return method, value
    if re.fullmatch(r"[a-z0-9][a-z0-9_./-]*", value, flags=re.IGNORECASE):
        return method, f"/api/{value.lstrip('/')}"
    return None


def _api_inventory_effect_summary(path: Path) -> dict[str, dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"^## Effect Class Summary\s*$\n(?P<section>.*?)(?=^---\s*$|^##\s)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise AssertionError("API route inventory has no Effect Class Summary section")

    result: dict[str, dict[str, object]] = {}
    for line in match.group("section").splitlines():
        row = re.match(r"^\|\s*`([^`]+)`(?:\s*\([^)]*\))?\s*\|\s*(\d+)\s*\|\s*(.*?)\s*\|$", line)
        if not row:
            continue
        effect, count_text, route_cell = row.groups()
        routes: set[tuple[str, str]] = set()
        current_method = ""
        for token in re.findall(r"`([^`]+)`", route_cell):
            explicit_method = re.match(r"^(GET|POST)\s+", token)
            if explicit_method:
                current_method = explicit_method.group(1)
            route_key = _normalize_summary_route(token, current_method)
            if route_key:
                routes.add(route_key)
        result[effect] = {"count": int(count_text), "routes": routes}
    return result


def _method_counts(keys: set[tuple[str, str]]) -> dict[str, int]:
    return {
        "GET": sum(1 for method, _route in keys if method == "GET"),
        "POST": sum(1 for method, _route in keys if method == "POST"),
    }


class ApiRouteInventoryTests(unittest.TestCase):
    def test_api_route_inventory_matches_local_api_contract(self) -> None:
        inventory = REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md"
        contract_keys = _contract_route_keys()
        inventory_keys = _route_keys_from_markdown(inventory)
        counts = _method_counts(contract_keys)
        text = inventory.read_text(encoding="utf-8")

        self.assertEqual(inventory_keys, contract_keys)
        self.assertIn(f"Total: {len(contract_keys)} routes", text)
        self.assertIn(f"{counts['GET']} GET", text)
        self.assertIn(f"{counts['POST']} POST", text)

    def test_api_route_inventory_documents_each_contract_route_once(self) -> None:
        inventory = REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md"
        route_rows = _route_rows_from_markdown(inventory)
        duplicates = {route: count for route, count in Counter(route_rows).items() if count > 1}

        self.assertEqual(duplicates, {})
        self.assertEqual(set(route_rows), _contract_route_keys())

    def test_api_route_inventory_heading_counts_match_route_rows(self) -> None:
        inventory = REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md"

        for line_number, declared, actual in _route_count_sections(inventory):
            with self.subTest(line=line_number):
                self.assertEqual(declared, actual)

    def test_api_route_inventory_effects_match_local_api_contract(self) -> None:
        inventory = REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md"

        self.assertEqual(_api_inventory_route_effects(inventory), _contract_route_effects())

    def test_api_route_inventory_effect_summary_names_match_contract(self) -> None:
        inventory = REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md"
        summary = _api_inventory_effect_summary(inventory)

        self.assertEqual(set(summary), set(_contract_effect_routes()))

    def test_api_route_inventory_effect_summary_counts_match_contract(self) -> None:
        inventory = REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md"
        summary = _api_inventory_effect_summary(inventory)

        self.assertEqual(
            {effect: details["count"] for effect, details in summary.items()},
            {effect: len(routes) for effect, routes in _contract_effect_routes().items()},
        )

    def test_api_route_inventory_effect_summary_routes_match_contract(self) -> None:
        inventory = REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md"
        summary = _api_inventory_effect_summary(inventory)
        contract_effect_routes = _contract_effect_routes()

        for effect, routes in contract_effect_routes.items():
            if effect == "none":
                continue
            with self.subTest(effect=effect):
                self.assertEqual(summary[effect]["routes"], routes)

    def test_local_api_route_ownership_map_matches_local_api_contract(self) -> None:
        ownership_map = REPO_ROOT / "docs" / "inventories" / "LOCAL_API_ROUTE_OWNERSHIP_MAP.md"
        contract_keys = _contract_route_keys()
        ownership_keys = _route_keys_from_markdown(ownership_map)
        counts = _method_counts(contract_keys)
        text = ownership_map.read_text(encoding="utf-8")

        self.assertEqual(ownership_keys, contract_keys)
        self.assertIn(f"Total routes: {len(contract_keys)}", text)
        self.assertIn(f"{counts['GET']} read", text)
        self.assertIn(f"{counts['POST']} command", text)

    def test_local_api_evidence_mutation_matrix_matches_local_api_contract(self) -> None:
        matrix = REPO_ROOT / "docs" / "architecture" / "LOCAL_API_EVIDENCE_MUTATION_MATRIX.md"
        contract_keys = _contract_route_keys()
        matrix_keys = _route_keys_from_markdown(matrix)
        counts = _method_counts(contract_keys)
        text = matrix.read_text(encoding="utf-8")

        self.assertEqual(matrix_keys, contract_keys)
        self.assertIn(f"Total routes: {len(contract_keys)}", text)
        self.assertIn(f"{counts['GET']} read", text)
        self.assertIn(f"{counts['POST']} command", text)

    def test_all_three_route_documents_have_identical_route_sets(self) -> None:
        paths = (
            REPO_ROOT / "docs" / "inventories" / "API_ROUTE_INVENTORY.md",
            REPO_ROOT / "docs" / "inventories" / "LOCAL_API_ROUTE_OWNERSHIP_MAP.md",
            REPO_ROOT / "docs" / "architecture" / "LOCAL_API_EVIDENCE_MUTATION_MATRIX.md",
        )

        contract_keys = _contract_route_keys()
        self.assertTrue(all(_route_keys_from_markdown(path) == contract_keys for path in paths))

    def test_run_monitor_artifact_and_authority_boundaries_are_documented(self) -> None:
        runtime_inventory = (REPO_ROOT / "docs" / "inventories" / "RUNTIME_ARTIFACT_INVENTORY.md").read_text(
            encoding="utf-8"
        )
        state_reference = (REPO_ROOT / "docs" / "inventories" / "STATE_FILE_SCHEMA_REFERENCE.md").read_text(
            encoding="utf-8"
        )
        architecture = (REPO_ROOT / "docs" / "architecture" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        module_map = (REPO_ROOT / "docs" / "architecture" / "MODULE_MAP.md").read_text(encoding="utf-8")

        self.assertIn(r"State\RunMonitor\<run_id>.json", runtime_inventory)
        self.assertIn(r"State\RunMonitor\latest.json", runtime_inventory)
        self.assertIn("`GET /api/run-monitor`", runtime_inventory)
        self.assertIn("## RunMonitorRecord", state_reference)
        self.assertIn("`pipeline_run_monitor.v1`", state_reference)
        self.assertIn("`pipeline_run_monitor_pointer.v1`", state_reference)
        self.assertIn("`desktop_run_monitor.v1`", state_reference)
        self.assertIn("authoritative for accepted run membership", architecture)
        self.assertIn("Completed, Pending Publish, and failure artifacts remain terminal proof authorities", architecture)
        self.assertIn(r"RunMonitor/<run_id>.json", module_map)
        self.assertIn("GET `/api/run-monitor`", module_map)


if __name__ == "__main__":
    unittest.main()
