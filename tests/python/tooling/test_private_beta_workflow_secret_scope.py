from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "private-beta-windows.yml"

PRIVATE_SECRET_STEPS = {
    "TAURI_SIGNING_PRIVATE_KEY": {"Build signed NSIS updater bundle with step-scoped credentials"},
    "TAURI_SIGNING_PRIVATE_KEY_PASSWORD": {"Build signed NSIS updater bundle with step-scoped credentials"},
    "WINDOWS_CERTIFICATE_BASE64": {"Build signed NSIS updater bundle with step-scoped credentials"},
    "WINDOWS_CERTIFICATE_PASSWORD": {"Build signed NSIS updater bundle with step-scoped credentials"},
    "TAURI_UPDATER_PUBLIC_KEY": {
        "Private beta release preflight without private signing credentials",
        "Build signed NSIS updater bundle with step-scoped credentials",
    },
}


def _workflow() -> dict[str, object]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@unittest.skipUnless(
    WORKFLOW.is_file(),
    "Private-beta GitHub workflow metadata is intentionally omitted from release packages.",
)
class PrivateBetaWorkflowSecretScopeTests(unittest.TestCase):
    def test_validation_and_signing_are_separate_jobs_with_nonsecret_handoff(self) -> None:
        jobs = _workflow()["jobs"]
        validation = jobs["validate-windows"]
        signing = jobs["sign-windows"]

        self.assertNotIn("environment", validation)
        self.assertEqual(validation["permissions"], {"actions": "read", "contents": "read"})
        self.assertEqual(signing["needs"], "validate-windows")
        self.assertEqual(signing["environment"], "${{ inputs.channel }}-release")
        self.assertEqual(signing["permissions"], {"actions": "read", "contents": "write"})
        self.assertNotIn("secrets.", json.dumps(validation))
        self.assertNotIn("secrets.", json.dumps(validation.get("env", {})))
        self.assertNotIn("secrets.", json.dumps(signing.get("env", {})))

        validation_names = [step["name"] for step in validation["steps"]]
        signing_names = [step["name"] for step in signing["steps"]]
        self.assertLess(
            validation_names.index("Full release self-test without signing secrets"),
            validation_names.index("Create SHA-256-bound nonsecret validation handoff"),
        )
        self.assertLess(
            signing_names.index("Verify validation handoff before secret access"),
            signing_names.index("Build signed NSIS updater bundle with step-scoped credentials"),
        )

        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("private_beta_validation_handoff.v1", text)
        self.assertIn("Get-FileHash -LiteralPath $archive -Algorithm SHA256", text)
        self.assertIn("actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c", text)

    def test_sentinel_signing_credentials_resolve_only_in_reviewed_consuming_steps(self) -> None:
        signing = _workflow()["jobs"]["sign-windows"]
        resolved_sentinels: dict[str, set[str]] = {name: set() for name in PRIVATE_SECRET_STEPS}

        for step in signing["steps"]:
            step_name = step["name"]
            for env_name, value in step.get("env", {}).items():
                for secret_name in PRIVATE_SECRET_STEPS:
                    token = "${{ secrets." + secret_name + " }}"
                    resolved = str(value).replace(token, f"sentinel:{secret_name}")
                    if f"sentinel:{secret_name}" in resolved:
                        self.assertEqual(env_name, secret_name)
                        resolved_sentinels[secret_name].add(step_name)

        self.assertEqual(resolved_sentinels, PRIVATE_SECRET_STEPS)

    def test_dependency_and_test_steps_precede_the_only_private_secret_step(self) -> None:
        steps = _workflow()["jobs"]["sign-windows"]["steps"]
        names = [step["name"] for step in steps]
        build_index = names.index("Build signed NSIS updater bundle with step-scoped credentials")

        self.assertLess(names.index("Install Tauri dependencies without signing secrets"), build_index)
        self.assertLess(names.index("Verify validation handoff before secret access"), build_index)
        private_steps = {
            step["name"]
            for step in steps
            if any(
                secret in json.dumps(step.get("env", {}))
                for secret in (
                    "TAURI_SIGNING_PRIVATE_KEY",
                    "TAURI_SIGNING_PRIVATE_KEY_PASSWORD",
                    "WINDOWS_CERTIFICATE_BASE64",
                    "WINDOWS_CERTIFICATE_PASSWORD",
                )
            )
        }
        self.assertEqual(private_steps, {names[build_index]})

    def test_certificate_material_is_cleaned_inside_the_secret_scoped_build_step(self) -> None:
        steps = _workflow()["jobs"]["sign-windows"]["steps"]
        build = next(
            step
            for step in steps
            if step["name"] == "Build signed NSIS updater bundle with step-scoped credentials"
        )
        run = build["run"]

        self.assertIn("try {", run)
        self.assertIn("} finally {", run)
        self.assertIn("Remove-Item -LiteralPath $certificateStorePath", run)
        self.assertIn("Imported signing certificate cleanup failed", run)
        self.assertIn("Remove-Item -LiteralPath $certificateRoot -Recurse -Force", run)
        self.assertIn("Signing certificate file cleanup failed", run)
        self.assertNotIn("GITHUB_ENV", run)


if __name__ == "__main__":
    unittest.main()
