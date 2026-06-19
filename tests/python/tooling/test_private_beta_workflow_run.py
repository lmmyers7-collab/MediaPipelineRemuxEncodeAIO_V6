from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Test-PrivateBetaWorkflowRun.ps1"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for workflow run verification tests.")
    return shell


def _run_payload(*, conclusion: str = "success", status: str = "completed") -> dict[str, object]:
    return {
        "id": 123456789,
        "name": "Private Beta Windows Installer",
        "path": ".github/workflows/private-beta-windows.yml",
        "event": "workflow_dispatch",
        "status": status,
        "conclusion": conclusion,
        "display_title": "MediaPipelineRemuxEncodeAIO 2026.6.4+001 beta app-v2026.6.4+001",
        "head_sha": "f" * 40,
        "html_url": "https://github.com/owner/repo/actions/runs/123456789",
        "created_at": "2026-06-18T12:00:00Z",
        "updated_at": "2026-06-18T12:30:00Z",
    }


def _artifacts_payload(*, include_expected: bool = True, expired: bool = False) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    if include_expected:
        artifacts.append(
            {
                "id": 98765,
                "name": "mediapipeline-beta-windows-x64",
                "expired": expired,
                "size_in_bytes": 2048,
                "archive_download_url": "https://api.github.com/repos/owner/repo/actions/artifacts/98765/zip",
            }
        )
    artifacts.append(
        {
            "id": 87654,
            "name": "unrelated-artifact",
            "expired": False,
            "size_in_bytes": 32,
        }
    )
    return {"total_count": len(artifacts), "artifacts": artifacts}


def _run_verifier(run_json: Path, artifacts_json: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-Channel",
            "beta",
            "-Repository",
            "owner/repo",
            "-ReleaseTag",
            "app-v2026.6.4+001",
            "-Version",
            "2026.6.4+001",
            "-RunJsonPath",
            str(run_json),
            "-ArtifactsJsonPath",
            str(artifacts_json),
            "-AsJson",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class PrivateBetaWorkflowRunTests(unittest.TestCase):
    def test_workflow_run_verifier_accepts_successful_run_with_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_json = temp_root / "run.json"
            artifacts_json = temp_root / "artifacts.json"
            run_json.write_text(json.dumps(_run_payload()), encoding="utf-8")
            artifacts_json.write_text(json.dumps(_artifacts_payload()), encoding="utf-8")
            result = _run_verifier(run_json, artifacts_json)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema_version"], "private_beta_workflow_run_verification.v1")
        self.assertEqual(payload["run_id"], "123456789")
        self.assertIn("mediapipeline-beta-windows-x64", payload["artifact_names"])

    def test_workflow_run_verifier_rejects_failed_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_json = temp_root / "run.json"
            artifacts_json = temp_root / "artifacts.json"
            run_json.write_text(json.dumps(_run_payload(conclusion="failure")), encoding="utf-8")
            artifacts_json.write_text(json.dumps(_artifacts_payload()), encoding="utf-8")
            result = _run_verifier(run_json, artifacts_json)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("run:conclusion_success", failed_names)

    def test_workflow_run_verifier_rejects_missing_expected_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_json = temp_root / "run.json"
            artifacts_json = temp_root / "artifacts.json"
            run_json.write_text(json.dumps(_run_payload()), encoding="utf-8")
            artifacts_json.write_text(json.dumps(_artifacts_payload(include_expected=False)), encoding="utf-8")
            result = _run_verifier(run_json, artifacts_json)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        failed_names = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("artifacts:expected_name", failed_names)

    def test_script_does_not_mutate_workflow_runs_or_artifacts(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("gh_workflow_run_by_id", text)
        self.assertIn("gh_workflow_run_artifacts", text)
        self.assertNotIn("run cancel", text)
        self.assertNotIn("run rerun", text)
        self.assertNotIn("artifact delete", text)
        self.assertNotIn("release upload", text)


if __name__ == "__main__":
    unittest.main()
