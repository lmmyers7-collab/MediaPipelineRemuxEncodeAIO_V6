from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "dev" / "check_risky_file_registry.py"
spec = importlib.util.spec_from_file_location("check_risky_file_registry_for_tests", MODULE_PATH)
assert spec and spec.loader
registry_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = registry_check
spec.loader.exec_module(registry_check)


class RiskyFileRegistryTests(unittest.TestCase):
    def test_registry_validator_requires_validation_for_high_risk_entries(self) -> None:
        registry = {
            "schema_version": "risky_file_registry.v1",
            "entries": [
                {
                    "id": "unsafe",
                    "path_globs": ["Pipeline/Modules/Disk.ps1"],
                    "risk_level": "high",
                    "risk_domains": ["cleanup"],
                    "validation_rung": "release",
                    "required_checks": [],
                    "manual_gates": [],
                    "owner_docs": ["AGENTS.md"],
                    "rationale": "test",
                }
            ],
        }

        findings = registry_check.validate_registry(registry, known_paths={"Pipeline/Modules/Disk.ps1"})

        self.assertIn("RISK013", {finding.rule_id for finding in findings})

    def test_registry_validator_flags_unmatched_globs(self) -> None:
        registry = {
            "schema_version": "risky_file_registry.v1",
            "entries": [
                {
                    "id": "missing",
                    "path_globs": ["missing/**/*.py"],
                    "risk_level": "medium",
                    "risk_domains": ["tooling"],
                    "validation_rung": "unit",
                    "required_checks": ["tests"],
                    "manual_gates": [],
                    "owner_docs": ["AGENTS.md"],
                    "rationale": "test",
                }
            ],
        }

        findings = registry_check.validate_registry(registry, known_paths=set())

        self.assertIn("RISK010", {finding.rule_id for finding in findings})

    def test_classify_paths_returns_validation_requirements(self) -> None:
        registry = {
            "schema_version": "risky_file_registry.v1",
            "entries": [
                {
                    "id": "publish",
                    "path_globs": ["Pipeline/Modules/Pending*.ps1"],
                    "risk_level": "critical",
                    "risk_domains": ["pending_publish"],
                    "validation_rung": "pending",
                    "required_checks": ["pending-tests"],
                    "manual_gates": ["real-media"],
                    "owner_docs": ["AGENTS.md"],
                    "rationale": "test",
                }
            ],
        }

        matches = registry_check.classify_paths(["Pipeline/Modules/PendingPush.ps1"], registry)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].entry_id, "publish")
        self.assertEqual(matches[0].required_checks, ("pending-tests",))


if __name__ == "__main__":
    unittest.main()
