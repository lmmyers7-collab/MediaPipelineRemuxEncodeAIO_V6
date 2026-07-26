from __future__ import annotations

import io
import importlib.util
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MODULE_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "check_risky_file_registry.py"
spec = importlib.util.spec_from_file_location("check_risky_file_registry_for_tests", MODULE_PATH)
assert spec and spec.loader
registry_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = registry_check
spec.loader.exec_module(registry_check)


class RiskyFileRegistryTests(unittest.TestCase):
    def test_changed_paths_distinguishes_successful_empty_and_nonempty_diffs(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout="src\\mediapipeline\\core\\publish\\pending.py\nREADME.md\n",
            stderr="",
        )
        with mock.patch.object(registry_check.subprocess, "run", return_value=completed) as run:
            paths = registry_check.changed_paths(staged=True)

        self.assertEqual(paths, ["src/mediapipeline/core/publish/pending.py", "README.md"])
        self.assertIn("--cached", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["timeout"], registry_check.GIT_ENUMERATION_TIMEOUT_SECONDS)

        completed.stdout = ""
        with mock.patch.object(registry_check.subprocess, "run", return_value=completed):
            self.assertEqual(registry_check.changed_paths(staged=False), [])

    def test_changed_paths_raises_for_every_git_failure_class(self) -> None:
        command = ["git", "diff", "--name-only", "HEAD"]
        failures = (
            FileNotFoundError("git missing"),
            subprocess.TimeoutExpired(command, registry_check.GIT_ENUMERATION_TIMEOUT_SECONDS),
            subprocess.CalledProcessError(128, command, stderr="bad revision"),
            PermissionError("repository denied"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(registry_check.subprocess, "run", side_effect=failure):
                    with self.assertRaises(registry_check.PathEnumerationError):
                        registry_check.changed_paths()

    def test_changed_cli_reports_enumeration_failure_and_exits_nonzero(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(registry_check, "load_registry", return_value={"entries": []}),
            mock.patch.object(registry_check, "validate_registry", return_value=[]),
            mock.patch.object(
                registry_check,
                "changed_paths",
                side_effect=registry_check.PathEnumerationError("Git changed-path enumeration failed with exit 128"),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            exit_code = registry_check.main(["--changed", "--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["path_enumeration"]["requested"])
        self.assertFalse(payload["path_enumeration"]["ok"])
        self.assertIn("exit 128", payload["path_enumeration"]["error"])
        self.assertIn("enumeration failed", stderr.getvalue())

    def test_successful_empty_changed_cli_and_explicit_paths_remain_valid(self) -> None:
        registry = {
            "entries": [
                {
                    "id": "release",
                    "path_globs": ["ops/scripts/release/*.ps1"],
                    "risk_level": "high",
                    "validation_rung": "release",
                    "required_checks": ["release-test"],
                    "manual_gates": [],
                }
            ]
        }
        stdout = io.StringIO()
        with (
            mock.patch.object(registry_check, "load_registry", return_value=registry),
            mock.patch.object(registry_check, "validate_registry", return_value=[]),
            mock.patch.object(registry_check, "changed_paths", return_value=[]),
            redirect_stdout(stdout),
        ):
            exit_code = registry_check.main(["--changed", "--json"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["path_enumeration"]["ok"])
        self.assertEqual(payload["path_enumeration"]["path_count"], 0)

        stdout = io.StringIO()
        with (
            mock.patch.object(registry_check, "load_registry", return_value=registry),
            mock.patch.object(registry_check, "validate_registry", return_value=[]),
            mock.patch.object(
                registry_check,
                "changed_paths",
                side_effect=AssertionError("explicit --paths must not invoke Git"),
            ),
            redirect_stdout(stdout),
        ):
            exit_code = registry_check.main(["--paths", "ops/scripts/release/build.ps1", "--json"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["path_enumeration"]["requested"])
        self.assertEqual(len(payload["matches"]), 1)

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Complete active-doc and generated-summary registry inputs are omitted from release packages.",
    )
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

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Complete active-doc and generated-summary registry inputs are omitted from release packages.",
    )
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
