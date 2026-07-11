from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


PROJECT_ROOT = find_repo_root(Path(__file__))
WORKSHEET_SCRIPT = PROJECT_ROOT / "ops" / "scripts" / "operator" / "New-RealMediaValidationWorksheet.ps1"
RELEASE_BUILD_SCRIPT = PROJECT_ROOT / "ops" / "scripts" / "release" / "build.ps1"


def _powershell_host() -> str | None:
    bundled = PROJECT_ROOT / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("pwsh") or shutil.which("powershell")


class RealMediaValidationWorksheetTests(unittest.TestCase):
    def test_worksheet_helper_is_bounded_and_non_media_mutating(self) -> None:
        script = WORKSHEET_SCRIPT
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("SupportsShouldProcess", source)
        self.assertIn("PositionalBinding = $false", source)
        self.assertIn("PlanOnly", source)
        self.assertIn("SampleCategory", source)
        self.assertIn("ExpectedRoute", source)
        self.assertIn("QueueSnapshotPath", source)
        self.assertIn("Set-PilotEvidencePacketTable", source)
        self.assertIn("Set-QueueEvidenceTable", source)
        self.assertIn("Read-QueueSnapshotEvidence", source)
        self.assertIn("docs\\sample-validation\\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md", source)
        self.assertIn("REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md", source)
        self.assertIn("Markdown evidence worksheet only", source)
        self.assertIn("does not launch the app, process media", source)
        self.assertIn("does not process media or mutate source/output/scratch paths", source)
        self.assertIn("Set-Content", source)
        self.assertIn("Move-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("MediaPipeline.ps1", source)
        self.assertNotIn("& ffmpeg", source.casefold())
        self.assertNotIn("ffprobe", source.casefold())
        self.assertNotIn("rename.apply", source)
        self.assertNotIn("pending-publish/drain", source)
        self.assertNotIn("settings/save-patch", source)

    def test_worksheet_plan_only_returns_json_without_writing(self) -> None:
        pwsh = _powershell_host()
        if not pwsh:
            raise unittest.SkipTest("PowerShell is required for worksheet helper execution.")

        with tempfile.TemporaryDirectory() as raw_tmp:
            out_dir = Path(raw_tmp) / "runs"
            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(WORKSHEET_SCRIPT),
                    "-OutputDirectory",
                    str(out_dir),
                    "-RunId",
                    "unit-test-run",
                    "-SamplePath",
                    r"D:\Samples\Movie One.mkv",
                    "-SampleCategory",
                    "h264-remux-safe",
                    "-ExpectedRoute",
                    "remux",
                    "-PlanOnly",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema"], "real_media_validation_worksheet_plan.v1")
            self.assertEqual(payload["run_id"], "unit-test-run")
            self.assertEqual(payload["sample_count"], 1)
            self.assertEqual(payload["samples"][0]["source_path"], r"D:\Samples\Movie One.mkv")
            self.assertEqual(payload["samples"][0]["category"], "h264-remux-safe")
            self.assertEqual(payload["samples"][0]["expected_route"], "remux")
            self.assertTrue(payload["plan_only"])
            self.assertIn("does not process media", payload["boundary"])
            self.assertFalse(out_dir.exists())

    def test_worksheet_plan_only_reports_queue_snapshot_matches_without_writing(self) -> None:
        pwsh = _powershell_host()
        if not pwsh:
            raise unittest.SkipTest("PowerShell is required for worksheet helper execution.")

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            out_dir = tmp / "runs"
            snapshot = tmp / "queue_snapshot.json"
            sample_path = r"\\SERVER\Encode\Movies\Movie One.mkv"
            snapshot.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_queue_preview.v1",
                        "produced_at": "2026-05-17T10:00:00Z",
                        "rows": [
                            {
                                "source_path": sample_path,
                                "route": "REMUX (codec check pending)",
                                "route_reason": "H.264 source is Plex-compatible",
                                "route_reason_code": "plex_compatible_h264_remux",
                                "blocked_reason": None,
                                "root_path": r"\\SERVER\Encode\Movies",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            expected_snapshot_path = str(snapshot.resolve(strict=False))

            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(WORKSHEET_SCRIPT),
                    "-OutputDirectory",
                    str(out_dir),
                    "-RunId",
                    "unit-test-queue-plan",
                    "-SamplePath",
                    sample_path,
                    "-SampleCategory",
                    "h264-remux-safe",
                    "-ExpectedRoute",
                    "remux",
                    "-QueueSnapshotPath",
                    str(snapshot),
                    "-PlanOnly",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["queue_snapshot_path"], expected_snapshot_path)
            self.assertEqual(payload["queue_snapshot_rows"], 1)
            self.assertEqual(payload["queue_snapshot_sample_matches"], 1)
            self.assertFalse(out_dir.exists())

    def test_worksheet_creation_prefills_sample_rows_and_boundary_text(self) -> None:
        pwsh = _powershell_host()
        if not pwsh:
            raise unittest.SkipTest("PowerShell is required for worksheet helper execution.")

        with tempfile.TemporaryDirectory() as raw_tmp:
            out_dir = Path(raw_tmp) / "runs"
            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(WORKSHEET_SCRIPT),
                    "-OutputDirectory",
                    str(out_dir),
                    "-RunId",
                    "unit-test-create",
                    "-Operator",
                    "Test Operator",
                    "-Shell",
                    "WebView preview",
                    "-SamplePath",
                    r"D:\Samples\Movie One.mkv",
                    r"\\SERVER\TV\Show\S01E01.mkv",
                    "-SampleCategory",
                    "h264-remux-safe,subtitle-bearing",
                    "-ExpectedRoute",
                    "remux,remux-plus-srt",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            path = Path(payload["output_path"])
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8-sig")
            self.assertIn("Generated by New-RealMediaValidationWorksheet.ps1", text)
            self.assertIn("Boundary: this worksheet generator writes Markdown evidence only.", text)
            self.assertIn("Test Operator", text)
            self.assertIn("WebView preview", text)
            self.assertIn(r"D:\Samples\Movie One.mkv", text)
            self.assertIn(r"\\SERVER\TV\Show\S01E01.mkv", text)
            self.assertIn("| 1 | D:\\Samples\\Movie One.mkv | h264-remux-safe | remux |", text)
            self.assertIn("| 2 | \\\\SERVER\\TV\\Show\\S01E01.mkv | subtitle-bearing | remux-plus-srt |", text)
            self.assertIn("WebView Pilot Evidence Packet Capture", text)
            self.assertIn("Use Home -> Sample Validation -> Preview Record", text)
            self.assertIn("| 1 | Movie One.mkv |", text)
            self.assertIn("| 2 | S01E01.mkv |", text)
            self.assertIn("Packet safe next action:", text)
            self.assertIn("Copyable Validation Commands", text)
            self.assertIn("```powershell", text)
            self.assertIn("Test-WebViewRealMediaEvidenceSmoke.ps1", text)
            self.assertIn("Record skipped browser smokes as environment skips, not proof.", text)

    def test_worksheet_creation_prefills_queue_evidence_from_snapshot(self) -> None:
        pwsh = _powershell_host()
        if not pwsh:
            raise unittest.SkipTest("PowerShell is required for worksheet helper execution.")

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            out_dir = tmp / "runs"
            snapshot = tmp / "queue_snapshot.json"
            sample_path = r"\\SERVER\Encode\TV\Show\S01E01.mkv"
            snapshot.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_queue_preview.v1",
                        "produced_at": "2026-05-17T10:00:00Z",
                        "rows": [
                            {
                                "source_path": sample_path,
                                "route": "REMUX (codec check pending)",
                                "route_reason": "source size is within threshold",
                                "route_reason_code": "size_within_threshold",
                                "blocked_reason": None,
                                "root_path": r"\\SERVER\Encode\TV",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            expected_snapshot_path = str(snapshot.resolve(strict=False))

            result = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(WORKSHEET_SCRIPT),
                    "-OutputDirectory",
                    str(out_dir),
                    "-RunId",
                    "unit-test-queue-create",
                    "-SamplePath",
                    sample_path,
                    "-SampleCategory",
                    "tv-remux-safe",
                    "-ExpectedRoute",
                    "remux",
                    "-QueueSnapshotPath",
                    str(snapshot),
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            path = Path(payload["output_path"])
            text = path.read_text(encoding="utf-8-sig")
            self.assertIn("| 1 | REMUX (codec check pending) | source size is within threshold (size_within_threshold) | No | No | \\\\SERVER\\Encode\\TV |", text)
            self.assertIn("Queue snapshot age: produced 2026-05-17T10:00:00.", text)
            self.assertIn("; age", text)
            self.assertIn(f"source {expected_snapshot_path}", text)
            self.assertIn("Snapshot still matches expected source files: Yes (1/1)", text)

    def test_release_builder_omits_generated_real_media_validation_runs(self) -> None:
        builder = RELEASE_BUILD_SCRIPT.read_text(encoding="utf-8")
        policy = (PROJECT_ROOT / "ops" / "scripts" / "release" / "release_policy.ps1").read_text(encoding="utf-8")

        self.assertIn("release_policy.ps1", builder)
        self.assertIn("Get-MediaPipelineReleaseExclusionReason", builder)
        self.assertIn("docs\\RealMediaValidationRuns\\*", policy)
        self.assertIn("operator real-media validation evidence omitted", policy)
        self.assertIn("$name -ne 'README.md'", policy)


if __name__ == "__main__":
    unittest.main()
