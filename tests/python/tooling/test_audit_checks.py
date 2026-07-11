from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from mediapipeline.tools.dev import audit_checks, ai_guardrail
from mediapipeline.tools.dev.release_package_scope import release_package_omits_path
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
GITHUB_WORKFLOWS_OMITTED = release_package_omits_path(REPO_ROOT, ".github/workflows")


class AuditCheckManifestTests(unittest.TestCase):
    def test_precommit_suite_preserves_existing_guardrail_coverage(self) -> None:
        self.assertEqual(
            [check.id for check in audit_checks.suite_checks("precommit")],
            [
                "summary-freshness",
                "project-index",
                "pipeline-map",
                "lifecycle-map",
                "config-schema",
                "stage-schema",
                "risky-file-registry",
                "architecture-guardrails-staged",
                "dependency-boundaries-max-internal-1",
                "naming-lint-staged",
                "active-doc-references",
                "change-packet-staged-coverage",
                "python-typing",
            ],
        )

    def test_phase1_suite_keeps_dynamic_github_checks_out_of_manifest(self) -> None:
        check_ids = {check.id for check in audit_checks.suite_checks("phase1-generated")}

        self.assertIn("summary-freshness", check_ids)
        self.assertIn("stage-schema", check_ids)
        self.assertIn("python-typing", check_ids)
        self.assertIn("python-lint", check_ids)
        self.assertNotIn("naming-lint-staged", check_ids)
        self.assertNotIn("change-packet-staged-coverage", check_ids)

    def test_deep_audit_suite_includes_prior_postflight_only_checks(self) -> None:
        check_ids = {check.id for check in audit_checks.suite_checks("deep-audit")}

        self.assertIn("feature-file-map", check_ids)
        self.assertIn("change-packets", check_ids)
        self.assertIn("dependency-boundaries", check_ids)
        self.assertIn("naming-lint", check_ids)
        self.assertIn("python-lint", check_ids)
        self.assertIn("god-file-guard", check_ids)
        self.assertIn("marketecture-guard", check_ids)

    def test_release_suite_marks_source_tree_only_checks_for_package_downshift(self) -> None:
        manifest = audit_checks.suite_to_dict("release-self-test")
        checks = {check["id"]: check for check in manifest["checks"]}

        self.assertTrue(checks["summary-freshness"]["source_tree_only"])
        self.assertTrue(checks["active-doc-references"]["source_tree_only"])
        self.assertFalse(checks["config-schema"]["source_tree_only"])
        self.assertFalse(checks["dependency-boundaries-max-internal-1"]["source_tree_only"])
        self.assertTrue(checks["python-lint"]["source_tree_only"])
        self.assertEqual(checks["dependency-boundaries-max-internal-1"]["arguments"], ["--max-internal-imports", "1"])

    def test_ai_guardrail_plan_uses_shared_manifest(self) -> None:
        expected = [check.id for check in audit_checks.suite_checks("ai-guardrail")]
        actual = [check.name for check in ai_guardrail.build_check_plan("postflight")]

        self.assertEqual(actual, expected)

    def test_emit_command_outputs_release_suite_json(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = audit_checks.main(["emit", "release-self-test"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["suite"], "release-self-test")
        self.assertIn("checks", payload)

    def test_local_surfaces_reference_manifest_backed_suites(self) -> None:
        precommit = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        release_test = (REPO_ROOT / "ops" / "scripts" / "release" / "test.ps1").read_text(encoding="utf-8")

        self.assertIn("mediapipeline.tools.dev.audit_checks run precommit", precommit)
        self.assertIn("mediapipeline.tools.dev.check_python_lint", precommit)
        self.assertIn("mediapipeline.tools.dev.audit_checks emit release-self-test", release_test)
        self.assertNotIn("mediapipeline.tools.dev.refresh_summaries --check", precommit)

    @unittest.skipIf(
        GITHUB_WORKFLOWS_OMITTED,
        "GitHub workflow metadata is intentionally omitted from release packages.",
    )
    def test_workflow_surfaces_reference_manifest_backed_suites(self) -> None:
        phase1 = (REPO_ROOT / ".github" / "workflows" / "phase1-drift.yml").read_text(encoding="utf-8")
        deep = (REPO_ROOT / ".github" / "workflows" / "deep-audit.yml").read_text(encoding="utf-8")

        self.assertIn("mediapipeline.tools.dev.audit_checks run phase1-generated", phase1)
        self.assertIn("mediapipeline.tools.dev.audit_checks run deep-audit", deep)


if __name__ == "__main__":
    unittest.main()
