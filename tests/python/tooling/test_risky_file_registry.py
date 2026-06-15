from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MODULE_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "check_risky_file_registry.py"
spec = importlib.util.spec_from_file_location("check_risky_file_registry_for_tests", MODULE_PATH)
assert spec and spec.loader
registry_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = registry_check
spec.loader.exec_module(registry_check)


class RiskyFileRegistryTests(unittest.TestCase):
    def test_current_repository_registry_is_valid(self) -> None:
        registry = registry_check.load_registry()

        self.assertEqual(registry_check.validate_registry(registry), [])

    def test_registry_validator_requires_validation_for_high_risk_entries(self) -> None:
        registry = {
            "schema_version": "risky_file_registry.v1",
            "entries": [
                {
                    "id": "unsafe",
                    "path_globs": ["ops/pipeline/engine/storage/disk.ps1"],
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

        findings = registry_check.validate_registry(registry, known_paths={"ops/pipeline/engine/storage/disk.ps1"})

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

    def test_registry_validator_flags_missing_owner_docs(self) -> None:
        registry = {
            "schema_version": "risky_file_registry.v1",
            "entries": [
                {
                    "id": "missing_owner_doc",
                    "path_globs": ["src/mediapipeline/tools/dev/check_risky_file_registry.py"],
                    "risk_level": "medium",
                    "risk_domains": ["tooling"],
                    "validation_rung": "unit",
                    "required_checks": ["tests"],
                    "manual_gates": [],
                    "owner_docs": ["docs/architecture/DOES_NOT_EXIST.md"],
                    "rationale": "test",
                }
            ],
        }

        findings = registry_check.validate_registry(
            registry,
            known_paths={"src/mediapipeline/tools/dev/check_risky_file_registry.py"},
        )

        self.assertIn("RISK015", {finding.rule_id for finding in findings})

    def test_classify_paths_returns_validation_requirements(self) -> None:
        registry = {
            "schema_version": "risky_file_registry.v1",
            "entries": [
                {
                    "id": "publish",
                    "path_globs": ["src/mediapipeline/core/publish/pending_*.py"],
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

        matches = registry_check.classify_paths(["src/mediapipeline/core/publish/pending_manifest.py"], registry)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].entry_id, "publish")
        self.assertEqual(matches[0].required_checks, ("pending-tests",))

    def test_current_registry_classifies_promoted_domain_paths(self) -> None:
        registry = registry_check.load_registry()

        matches = registry_check.classify_paths(
            [
                "src/mediapipeline/core/publish/pending_manifest.py",
                "src/mediapipeline/core/rename/apply.py",
                "ops/pipeline/engine/config/config_schema.ps1",
                "src/mediapipeline/tools/dev/check_dependency_boundaries.py",
                "docs/generated/summaries/src/mediapipeline/core/config/validation.py.md",
            ],
            registry,
        )

        matched_ids = {match.entry_id for match in matches}
        self.assertIn("publish_and_pending_publish", matched_ids)
        self.assertIn("rename_apply", matched_ids)
        self.assertIn("settings_and_config", matched_ids)
        self.assertIn("ai_guardrails_and_generated_context", matched_ids)

    def test_current_registry_generated_summary_glob_matches_files(self) -> None:
        registry = registry_check.load_registry()

        findings = registry_check.validate_registry(
            registry,
            known_paths={"docs/generated/summaries/src/mediapipeline/core/config/validation.py.md"},
        )

        self.assertNotIn(
            ("RISK010", "ai_guardrails_and_generated_context"),
            {(finding.rule_id, finding.path) for finding in findings},
        )


if __name__ == "__main__":
    unittest.main()

