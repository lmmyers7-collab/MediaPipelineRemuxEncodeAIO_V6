from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT


REPO_ROOT = find_repo_root(Path(__file__))


def _contract_route_keys() -> set[tuple[str, str]]:
    return {(str(route["method"]).upper(), str(route["path"])) for route in LOCAL_API_ROUTE_CONTRACT}


def _route_keys_from_markdown(path: Path) -> set[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    return {
        (method.upper(), route)
        for method, route in re.findall(r"^\|\s*`(GET|POST) (/api/[^`]+)`\s*\|", text, flags=re.MULTILINE)
    }


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


if __name__ == "__main__":
    unittest.main()
