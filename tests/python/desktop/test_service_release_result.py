from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.maintenance.release_result import release_artifact_fingerprint, release_capture_fields, release_result_payload
from mediapipeline.desktop.subprocess_runner import CapturedCommandResult


class ReleaseResultTests(unittest.TestCase):
    def test_release_capture_fields_normalize_timeout_and_kill_message(self) -> None:
        result = CapturedCommandResult(
            args=["pwsh"],
            returncode=None,
            stdout="out",
            stderr="err",
            timed_out=True,
            kill_message="process killed",
        )

        returncode, stdout, stderr, timed_out = release_capture_fields(result)

        self.assertEqual(returncode, -1)
        self.assertEqual(stdout, "out")
        self.assertEqual(stderr, "err\nprocess killed")
        self.assertTrue(timed_out)

    def test_release_result_payload_reports_artifacts_and_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "release"
            destination.mkdir()
            manifest_path = destination / "release_manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            zip_path = Path(str(destination) + ".zip")
            zip_path.write_text("zip", encoding="utf-8")

            payload = release_result_payload(
                result=CapturedCommandResult(args=["pwsh"], returncode=0, stdout="ok", stderr=""),
                command_line="pwsh -File Build.ps1",
                destination=destination,
                manifest_path=manifest_path,
                zip_path=zip_path,
                dry_run=False,
                elapsed_seconds=1.25,
                manifest={"ok": True},
            )

        self.assertTrue(payload["success"])
        self.assertFalse(payload["timed_out"])
        self.assertEqual(payload["returncode"], 0)
        self.assertTrue(payload["manifest_exists"])
        self.assertFalse(payload["manifest_preexisting"])
        self.assertTrue(payload["manifest_created"])
        self.assertTrue(payload["zip_exists"])
        self.assertFalse(payload["zip_preexisting"])
        self.assertTrue(payload["zip_created"])
        self.assertEqual(payload["manifest"], {"ok": True})

    def test_release_result_payload_distinguishes_dry_run_preexisting_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "release"
            destination.mkdir()
            manifest_path = destination / "release_manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            zip_path = Path(str(destination) + ".zip")
            zip_path.write_text("zip", encoding="utf-8")

            payload = release_result_payload(
                result=CapturedCommandResult(args=["pwsh"], returncode=0, stdout="ok", stderr=""),
                command_line="pwsh -File Build.ps1 -DryRun",
                destination=destination,
                manifest_path=manifest_path,
                zip_path=zip_path,
                dry_run=True,
                elapsed_seconds=1.25,
                manifest={"ok": True},
                manifest_preexisting=True,
                zip_preexisting=True,
            )

        self.assertTrue(payload["success"])
        self.assertTrue(payload["manifest_exists"])
        self.assertTrue(payload["manifest_preexisting"])
        self.assertFalse(payload["manifest_created"])
        self.assertTrue(payload["zip_exists"])
        self.assertTrue(payload["zip_preexisting"])
        self.assertFalse(payload["zip_created"])

    def test_release_result_payload_marks_dry_run_preexisting_artifact_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "release"
            destination.mkdir()
            manifest_path = destination / "release_manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            zip_path = Path(str(destination) + ".zip")
            zip_path.write_text("zip", encoding="utf-8")
            manifest_before = release_artifact_fingerprint(manifest_path)
            zip_before = release_artifact_fingerprint(zip_path)
            manifest_path.write_text('{"changed": true}', encoding="utf-8")
            zip_path.write_text("zip changed", encoding="utf-8")

            payload = release_result_payload(
                result=CapturedCommandResult(args=["pwsh"], returncode=0, stdout="ok", stderr=""),
                command_line="pwsh -File Build.ps1 -DryRun",
                destination=destination,
                manifest_path=manifest_path,
                zip_path=zip_path,
                dry_run=True,
                elapsed_seconds=1.25,
                manifest={"changed": True},
                manifest_preexisting=True,
                zip_preexisting=True,
                manifest_fingerprint_before=manifest_before,
                zip_fingerprint_before=zip_before,
            )

        self.assertTrue(payload["success"])
        self.assertTrue(payload["manifest_preexisting"])
        self.assertFalse(payload["manifest_created"])
        self.assertTrue(payload["manifest_changed"])
        self.assertTrue(payload["zip_preexisting"])
        self.assertFalse(payload["zip_created"])
        self.assertTrue(payload["zip_changed"])

    def test_release_result_payload_marks_nonzero_and_timeout_as_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "release"
            timed_out = release_result_payload(
                result=CapturedCommandResult(args=["pwsh"], returncode=0, stdout="", stderr="", timed_out=True),
                command_line="pwsh",
                destination=destination,
                manifest_path=destination / "release_manifest.json",
                zip_path=Path(str(destination) + ".zip"),
                dry_run=True,
                elapsed_seconds=2.0,
                manifest=None,
            )
            nonzero = release_result_payload(
                result=CapturedCommandResult(args=["pwsh"], returncode=1, stdout="", stderr="failed"),
                command_line="pwsh",
                destination=destination,
                manifest_path=destination / "release_manifest.json",
                zip_path=Path(str(destination) + ".zip"),
                dry_run=True,
                elapsed_seconds=2.0,
                manifest=None,
            )

        self.assertFalse(timed_out["success"])
        self.assertFalse(nonzero["success"])
        self.assertEqual(nonzero["stderr"], "failed")


if __name__ == "__main__":
    unittest.main()
