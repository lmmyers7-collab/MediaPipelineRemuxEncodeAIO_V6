from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone, UTC
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.diagnostics.tdarr_matrix_audit import (  # noqa: E402
    TDARR_MATRIX_AUDIT_ALLOWED_ACTIONS,
    TDARR_MATRIX_AUDIT_BUCKET_COUNT,
    TDARR_MATRIX_AUDIT_COMMAND,
    TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS,
    TdarrMatrixAuditServiceMixin,
    tdarr_matrix_audit_arguments,
    tdarr_matrix_default_library_root,
    tdarr_matrix_audit_invalid_action_result,
    tdarr_matrix_audit_preset,
    tdarr_matrix_audit_result,
    tdarr_matrix_audit_runner_timeout,
    tdarr_matrix_incomplete_full_run_evidence,
    tdarr_matrix_incomplete_full_run,
    tdarr_matrix_background_close_evidence,
)
from mediapipeline.core.diagnostics.tdarr_matrix_audit_facade import (  # noqa: E402
    DiagnosticsTdarrMatrixAuditFacadeMixin,
)
from mediapipeline.core.diagnostics.tdarr_matrix_console import (  # noqa: E402
    TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS,
    tdarr_matrix_compare_runs_payload,
    tdarr_matrix_console_payload,
    tdarr_matrix_evidence_open_result,
    tdarr_matrix_library_root,
    tdarr_matrix_rerun_case_keys,
    tdarr_matrix_runs_root,
)
from mediapipeline.core.diagnostics.tdarr_matrix_proof import (  # noqa: E402
    tdarr_case_keys_for_pack,
    tdarr_expected_manifest_count,
)


MANIFEST_FIELDNAMES = [
    "schema_version",
    "view",
    "case_id",
    "diagnostic_bucket",
    "generated_path",
    "source_path",
    "original_name",
    "source_url",
    "source_page",
    "medium",
    "container",
    "resolution",
    "video_codec",
    "audio_codec",
    "duration",
    "advertised_size_mb",
    "actual_size_bytes",
    "sha256",
    "link_mode",
]


def _successful_runner_payload() -> dict[str, object]:
    return {
        "success": True,
        "timed_out": False,
        "returncode": 0,
        "action": "report",
        "mode": "report",
        "label": "Prepare Tdarr Proof Pack Audit Report",
        "report_only": True,
        "manifest_count": 1,
        "finding_count": 0,
        "report_path": "r.json",
        "stdout": "{}",
        "stderr": "",
    }


class _FacadeHarness(DiagnosticsTdarrMatrixAuditFacadeMixin):
    def __init__(self, lock: threading.Lock, runner) -> None:
        self._diagnostics_command_lock = lock
        self.service = SimpleNamespace(run_tdarr_matrix_audit=runner, logger=None)


class _Harness(TdarrMatrixAuditServiceMixin):
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.app_root = workspace_root / "apps" / "desktop"
        self.logger = SimpleNamespace(info=lambda *_args, **_kwargs: None)

    def resolve_powershell_host(self) -> str:
        return "pwsh-test"

    def _build_launch_environment(self) -> dict[str, str]:
        return {"PYTHONPATH": "existing"}

    def _subprocess_kwargs_hidden(self) -> dict[str, object]:
        return {"creationflags": 0}


def _manifest_row(root: Path, *, case_id: str, view: str, bucket: str) -> dict[str, str]:
    source = root / "cache" / f"{case_id}-{view}.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("source", encoding="utf-8")
    generated = (
        f"source/Movies/Fake {case_id}.mkv"
        if view == "movies"
        else f"source/TV/Fake Series/Season 01/Fake Series - S01E01 - {case_id}.mkv"
    )
    return {
        "schema_version": "tdarr_matrix_materialized_library.v1",
        "view": view,
        "case_id": case_id,
        "diagnostic_bucket": bucket,
        "generated_path": generated,
        "source_path": str(source),
        "original_name": f"{case_id}.mkv",
        "source_url": "https://example.invalid/sample",
        "source_page": "https://example.invalid",
        "medium": "video",
        "container": "mkv",
        "resolution": "1080p",
        "video_codec": "h264",
        "audio_codec": "aac",
        "duration": "1",
        "advertised_size_mb": "1",
        "actual_size_bytes": "6",
        "sha256": "abc123",
        "link_mode": "hardlink",
    }


def _write_fake_tdarr_run(
    workspace_root: Path,
    run_id: str,
    *,
    findings: list[dict[str, object]],
    rows: list[dict[str, str]] | None = None,
) -> Path:
    run_root = tdarr_matrix_runs_root(workspace_root) / run_id
    manifest_dir = run_root / "manifests"
    audit_dir = manifest_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (run_root / ".tdarr-matrix-audit-run.json").write_text(
        json.dumps({"schema_version": "tdarr_matrix_audit.v1", "run_root": str(run_root)}),
        encoding="utf-8",
    )
    materialized_rows = rows or [
        _manifest_row(workspace_root, case_id="tdarr-0001", view="movies", bucket="audio-only"),
        _manifest_row(workspace_root, case_id="tdarr-0002", view="tv", bucket="audio-only"),
    ]
    with (manifest_dir / "materialized_library.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDNAMES)
        writer.writeheader()
        writer.writerows(materialized_rows)
    for row in materialized_rows:
        artifact_dir = audit_dir / "files" / f"{row['case_id']}-{row['view']}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "stdout.log").write_text(f"stdout {row['case_id']}", encoding="utf-8")
        (artifact_dir / "stderr.log").write_text(f"stderr {row['case_id']}", encoding="utf-8")
        (artifact_dir / "worker_result.json").write_text(
            json.dumps({"Status": "failed", "Route": "encode", "SourceName": Path(row["generated_path"]).name}),
            encoding="utf-8",
        )
        (artifact_dir / "source_hashes.json").write_text(
            json.dumps({"case_id": row["case_id"], "pre_sha256": "abc123", "post_sha256": "abc123"}),
            encoding="utf-8",
        )
    report = {
        "schema_version": "tdarr_matrix_audit.v1",
        "generated_at_utc": "2026-06-08T00:00:00+00:00",
        "mode": "run-samples",
        "library_root": str(run_root),
        "manifest_count": len(materialized_rows),
        "severity_counts": {},
        "code_counts": {},
        "findings": findings,
    }
    (audit_dir / "tdarr_matrix_audit_report.json").write_text(json.dumps(report), encoding="utf-8")
    return run_root


def _write_proof_manifest(workspace_root: Path, rows: list[dict[str, str]]) -> Path:
    proof_root = tdarr_matrix_library_root(workspace_root)
    manifest_path = proof_root / "manifests" / "materialized_library.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return manifest_path


def _finding(
    *,
    case_id: str = "tdarr-0001",
    view: str = "movies",
    severity: str = "warning",
    code: str = "classified_processing_failure",
    message: str = "Processing failed with structured evidence.",
    bucket: str = "audio-only",
) -> dict[str, object]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "case_id": case_id,
        "view": view,
        "diagnostic_bucket": bucket,
        "generated_path": "source/Movies/Fake tdarr-0001.mkv",
        "source_path": "C:/cache/tdarr-0001.mkv",
        "evidence": {
            "worker_result": {
                "Status": "failed",
                "Route": "encode",
                "RouteReasonCode": "test_failure",
                "Reason": "Unit fixture",
                "SourceName": "Fake tdarr-0001.mkv",
            }
        },
    }


class TdarrMatrixAuditServiceTests(unittest.TestCase):
    def test_background_close_evidence_is_active_and_unreadable_metadata_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs_root = tdarr_matrix_runs_root(root)
            metadata_root = runs_root / "_background"
            metadata_root.mkdir(parents=True)
            process_start = datetime.fromtimestamp(12345.0, UTC).isoformat()
            metadata_path = metadata_root / "run-proof.process.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "schema_version": "tdarr_matrix_background_process.v1",
                        "run_id": "run-proof",
                        "pid": 4321,
                        "process_start_time": process_start,
                    }
                ),
                encoding="utf-8",
            )

            class FakeProcess:
                def is_running(self) -> bool:
                    return True

                def status(self) -> str:
                    return "running"

                def create_time(self) -> float:
                    return 12345.0

            class FakePsutil:
                STATUS_ZOMBIE = "zombie"

                class NoSuchProcess(Exception):
                    pass

                @staticmethod
                def Process(pid: int) -> FakeProcess:
                    if pid != 4321:
                        raise FakePsutil.NoSuchProcess(pid)
                    return FakeProcess()

            active = tdarr_matrix_background_close_evidence(root, psutil_module=FakePsutil)
            metadata_path.write_text("{not-json", encoding="utf-8")
            invalid = tdarr_matrix_background_close_evidence(root, psutil_module=FakePsutil)

        self.assertEqual(active["status"], "active")
        self.assertTrue(active["active_work"])
        self.assertEqual(active["pid"], 4321)
        self.assertEqual(invalid["status"], "unavailable")
        self.assertTrue(invalid["active_work"])

    def test_argument_presets_are_backend_owned(self) -> None:
        library_root = Path("C:/Repo/LocalBase/Scratch/TestLibraries/TdarrProofPack")
        runs_root = Path("C:/Repo/LocalBase/Scratch/TestLibraries/TdarrProofPack/runs")
        entrypoint = Path("C:/Repo/ops/pipeline/entrypoints/MediaPipeline.ps1")

        prepare = tdarr_matrix_audit_arguments(
            action="prepare-proof-pack",
            library_root=library_root,
            powershell="pwsh",
            entrypoint=entrypoint,
        )
        report = tdarr_matrix_audit_arguments(
            action="report",
            library_root=library_root,
            powershell="pwsh",
            entrypoint=entrypoint,
        )
        smoke = tdarr_matrix_audit_arguments(
            action="smoke-pack",
            library_root=library_root,
            runs_root=runs_root,
            powershell="pwsh",
            entrypoint=entrypoint,
        )
        proof = tdarr_matrix_audit_arguments(
            action="proof-pack",
            library_root=library_root,
            runs_root=runs_root,
            powershell="pwsh",
            entrypoint=entrypoint,
            run_id="run-20260608-000000-proof-pack",
        )
        strict = tdarr_matrix_audit_arguments(
            action="strict-report",
            library_root=library_root,
            powershell="pwsh",
            entrypoint=entrypoint,
        )
        cleanup_delete = tdarr_matrix_audit_arguments(
            action="cleanup-delete",
            library_root=library_root,
            powershell="pwsh",
            entrypoint=entrypoint,
            confirm_delete_full_matrix=True,
        )

        self.assertEqual(prepare, ["materialize", "--proof-root", str(library_root)])
        self.assertEqual(report[0], "report")
        self.assertIn("--prepare-evidence", report)
        self.assertIn("--report-only", report)
        self.assertEqual(smoke[0], "run-samples")
        self.assertEqual(smoke.count("--case-key"), tdarr_expected_manifest_count("smoke-pack"))
        self.assertIn("tdarr-0002:movies", smoke)
        self.assertIn("tdarr-0063:tv", smoke)
        self.assertIn(str(runs_root), smoke)
        self.assertNotIn("--samples-per-bucket", smoke)
        self.assertEqual(smoke[smoke.index("--sample-timeout-seconds") + 1], "900")
        self.assertIn("--report-only", smoke)
        self.assertEqual(proof.count("--case-key"), tdarr_expected_manifest_count("proof-pack"))
        self.assertIn("tdarr-2125:tv", proof)
        self.assertNotIn("--all-samples", proof)
        self.assertNotIn("--samples-per-bucket", proof)
        self.assertEqual(proof[proof.index("--run-id") + 1], "run-20260608-000000-proof-pack")
        self.assertEqual(proof[proof.index("--sample-timeout-seconds") + 1], "1800")
        self.assertEqual(cleanup_delete, ["cleanup", "--proof-root", str(library_root), "--action", "delete", "--confirm-delete-full-matrix"])
        self.assertNotIn("--report-only", strict)
        self.assertIn("--hash-sources", report)
        self.assertIn("--hash-sources", strict)
        self.assertNotIn("--hash-sources", smoke)
        self.assertNotIn("--hash-sources", proof)

    def test_report_service_invokes_run_python_tool_with_fixed_proof_library(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "ops" / "scripts" / "dev" / "run-python-tool.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("# runner\n", encoding="utf-8")
            (root / "src").mkdir()
            library_root = tdarr_matrix_default_library_root(root)
            _write_proof_manifest(root, [_manifest_row(root, case_id="tdarr-0002", view="movies", bucket="audio-only")])
            harness = _Harness(root)
            calls: list[dict[str, object]] = []

            def fake_run_capture(args: list[str], **kwargs: object) -> SimpleNamespace:
                calls.append({"args": args, "kwargs": kwargs})
                return SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "manifest_count": 1,
                            "finding_count": 0,
                            "report_path": str(root / "report.json"),
                        }
                    ),
                    stderr="",
                    timed_out=False,
                    kill_message="",
                )

            with patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.run_capture", fake_run_capture):
                result = harness.run_tdarr_matrix_audit(action="report")

        self.assertEqual(result["manifest_count"], 1)
        call = calls[0]
        args = call["args"]
        kwargs = call["kwargs"]
        self.assertIsInstance(args, list)
        self.assertEqual(Path(args[1]), runner)
        self.assertEqual(args[2], "mediapipeline.tools.dev.tdarr_matrix_audit")
        self.assertIn("report", args)
        self.assertIn("--report-only", args)
        self.assertIn(str(library_root), args)
        self.assertEqual(kwargs["cwd"], str(root))
        self.assertEqual(kwargs["timeout_seconds"], 5700)
        self.assertTrue(str(root / "src") in str(kwargs["env"]["PYTHONPATH"]))

    def test_proof_pack_service_starts_background_run_without_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "ops" / "scripts" / "dev" / "run-python-tool.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("# runner\n", encoding="utf-8")
            (root / "src").mkdir()
            _write_proof_manifest(root, [_manifest_row(root, case_id="tdarr-0002", view="movies", bucket="audio-only")])
            harness = _Harness(root)
            calls: list[dict[str, object]] = []

            class FakeProc:
                pid = 4321

            def fake_popen(args: list[str], **kwargs: object) -> FakeProc:
                calls.append({"args": args, "kwargs": kwargs})
                return FakeProc()

            with (
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.run_capture") as mock_capture,
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.subprocess.Popen", fake_popen),
            ):
                result = harness.run_tdarr_matrix_audit(action="proof-pack")

        mock_capture.assert_not_called()
        self.assertTrue(result["success"])
        self.assertTrue(result["background_started"])
        self.assertEqual(result["pid"], 4321)
        self.assertEqual(result["selected_count"], tdarr_expected_manifest_count("proof-pack"))
        self.assertIn("-proof-pack", result["run_id"])
        call = calls[0]
        args = call["args"]
        kwargs = call["kwargs"]
        self.assertNotIn("--all-samples", args)
        self.assertEqual(args.count("--case-key"), tdarr_expected_manifest_count("proof-pack"))
        self.assertIn("--run-id", args)
        self.assertEqual(args[args.index("--run-id") + 1], result["run_id"])
        self.assertEqual(kwargs["cwd"], str(root))
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(str(root / "src") in str(kwargs["env"]["PYTHONPATH"]))

    def test_proof_pack_service_blocks_stale_incomplete_run_without_pid_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "ops" / "scripts" / "dev" / "run-python-tool.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("# runner\n", encoding="utf-8")
            (root / "src").mkdir()
            _write_proof_manifest(root, [_manifest_row(root, case_id="tdarr-0002", view="movies", bucket="audio-only")])
            run_root = tdarr_matrix_runs_root(root) / "run-existing-proof-pack"
            run_root.mkdir(parents=True)
            (run_root / ".tdarr-matrix-audit-run.json").write_text(
                json.dumps({"schema_version": "tdarr_matrix_audit.v1", "selected_count": tdarr_expected_manifest_count("proof-pack")}),
                encoding="utf-8",
            )
            harness = _Harness(root)

            with (
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.run_capture") as mock_capture,
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.subprocess.Popen") as mock_popen,
            ):
                result = harness.run_tdarr_matrix_audit(action="proof-pack")

            detected = tdarr_matrix_incomplete_full_run(run_root.parent, selected_count=tdarr_expected_manifest_count("proof-pack"))
            evidence = tdarr_matrix_incomplete_full_run_evidence(run_root.parent, selected_count=tdarr_expected_manifest_count("proof-pack"))

        mock_capture.assert_not_called()
        mock_popen.assert_not_called()
        self.assertIsNone(detected)
        self.assertEqual(evidence["stale"], run_root)
        self.assertFalse(result["success"])
        self.assertFalse(result["already_running"])
        self.assertTrue(result["stale_incomplete_run"])
        self.assertEqual(result["stale_reason"], "missing_background_pid")
        self.assertEqual(result["run_id"], "run-existing-proof-pack")
        from mediapipeline.core.diagnostics.tdarr_matrix_audit import tdarr_matrix_audit_progress_payload

        self.assertEqual(tdarr_matrix_audit_progress_payload(result)["status"], "blocked")

    def test_proof_pack_service_reuses_live_incomplete_run_without_duplicate_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "ops" / "scripts" / "dev" / "run-python-tool.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("# runner\n", encoding="utf-8")
            (root / "src").mkdir()
            _write_proof_manifest(root, [_manifest_row(root, case_id="tdarr-0002", view="movies", bucket="audio-only")])
            runs_root = tdarr_matrix_runs_root(root)
            run_root = runs_root / "run-existing-proof-pack"
            run_root.mkdir(parents=True)
            (run_root / ".tdarr-matrix-audit-run.json").write_text(
                json.dumps({"schema_version": "tdarr_matrix_audit.v1", "selected_count": tdarr_expected_manifest_count("proof-pack")}),
                encoding="utf-8",
            )
            process_start = datetime.fromtimestamp(12345.0, UTC).isoformat()
            metadata_dir = runs_root / "_background"
            metadata_dir.mkdir()
            (metadata_dir / "run-existing-proof-pack.process.json").write_text(
                json.dumps(
                    {
                        "schema_version": "tdarr_matrix_background_process.v1",
                        "run_id": "run-existing-proof-pack",
                        "pid": 4321,
                        "process_start_time": process_start,
                    }
                ),
                encoding="utf-8",
            )
            harness = _Harness(root)

            class FakeProcess:
                def is_running(self) -> bool:
                    return True

                def status(self) -> str:
                    return "running"

                def create_time(self) -> float:
                    return 12345.0

            class FakePsutil:
                STATUS_ZOMBIE = "zombie"

                class NoSuchProcess(Exception):
                    pass

                @staticmethod
                def Process(pid: int) -> FakeProcess:
                    if pid != 4321:
                        raise FakePsutil.NoSuchProcess(pid)
                    return FakeProcess()

            with (
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.run_capture") as mock_capture,
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.subprocess.Popen") as mock_popen,
                patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.psutil", FakePsutil),
            ):
                result = harness.run_tdarr_matrix_audit(action="proof-pack")
                detected = tdarr_matrix_incomplete_full_run(run_root.parent, selected_count=tdarr_expected_manifest_count("proof-pack"))
                evidence = tdarr_matrix_incomplete_full_run_evidence(run_root.parent, selected_count=tdarr_expected_manifest_count("proof-pack"))

        mock_capture.assert_not_called()
        mock_popen.assert_not_called()
        self.assertEqual(detected, run_root)
        self.assertEqual(evidence["active"], run_root)
        self.assertTrue(result["success"])
        self.assertTrue(result["already_running"])
        self.assertEqual(result["pid"], 4321)
        self.assertEqual(result["run_id"], "run-existing-proof-pack")

    def test_service_reports_missing_library_without_launching(self) -> None:
        # G5: with no materialized base library, return an actionable result and do not
        # launch the subprocess (which would otherwise fail with a cryptic error).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / "ops" / "scripts" / "dev" / "run-python-tool.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("# runner\n", encoding="utf-8")
            (root / "src").mkdir()
            harness = _Harness(root)
            with patch("mediapipeline.core.diagnostics.tdarr_matrix_audit.run_capture") as mock_run:
                result = harness.run_tdarr_matrix_audit(action="report")
            mock_run.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], 2)
        self.assertIn("not materialized", result["stderr"])
        self.assertIn("tdarr_proof_pack", result["stderr"])

    def test_result_policy_shapes_success_warning_and_invalid_action(self) -> None:
        clean = tdarr_matrix_audit_result(
            {
                "success": True,
                "timed_out": False,
                "returncode": 0,
                "action": "report",
                "mode": "report",
                "label": "Prepare Tdarr Proof Pack Audit Report",
                "report_only": True,
                "manifest_count": tdarr_expected_manifest_count("proof-pack"),
                "finding_count": 0,
                "report_path": "C:/Scratch/report.json",
                "library_root": "C:/Scratch/TdarrMatrix",
                "stdout": "{}",
                "stderr": "",
            }
        )
        warning = tdarr_matrix_audit_result(
            {
                "success": True,
                "timed_out": False,
                "returncode": 0,
                "action": "smoke-pack",
                "mode": "run-samples",
                "label": "Run Tdarr Smoke Pack",
                "report_only": True,
                "selected_count": tdarr_expected_manifest_count("smoke-pack"),
                "finding_count": 2,
                "report_path": "C:/Scratch/run/report.json",
                "run_root": "C:/Scratch/TdarrMatrixRuns/run-1",
                "stdout": "{}",
                "stderr": "",
            }
        )
        background = tdarr_matrix_audit_result(
            {
                "success": True,
                "timed_out": False,
                "background_started": True,
                "returncode": 0,
                "pid": 4321,
                "run_id": "run-20260608-000000-proof-pack",
                "action": "proof-pack",
                "mode": "run-samples",
                "label": "Run Tdarr Proof Pack",
                "report_only": True,
                "selected_count": tdarr_expected_manifest_count("proof-pack"),
                "finding_count": 0,
                "run_root": "C:/Scratch/run",
                "report_path": "C:/Scratch/run/report.json",
                "stdout": "",
                "stderr": "",
            }
        )
        existing = tdarr_matrix_audit_result(
            {
                "success": True,
                "timed_out": False,
                "already_running": True,
                "returncode": 0,
                "run_id": "run-existing-proof-pack",
                "action": "proof-pack",
                "mode": "run-samples",
                "label": "Run Tdarr Proof Pack",
                "report_only": True,
                "selected_count": tdarr_expected_manifest_count("proof-pack"),
                "finding_count": 0,
                "run_root": "C:/Scratch/run",
                "report_path": "C:/Scratch/run/report.json",
                "stdout": "",
                "stderr": "",
            }
        )
        invalid = tdarr_matrix_audit_invalid_action_result("delete-everything")

        self.assertTrue(clean.ok)
        self.assertEqual(clean.command, TDARR_MATRIX_AUDIT_COMMAND)
        self.assertEqual(clean.data["schema_version"], "desktop_tdarr_matrix_audit_result.v1")
        self.assertEqual(clean.data["manifest_count"], tdarr_expected_manifest_count("proof-pack"))
        self.assertFalse(clean.data["writes_canonical_tdarr_cache"])
        self.assertEqual(clean.data["tdarr_matrix_audit_progress"]["schema_version"], "desktop_tdarr_matrix_audit_progress.v1")
        self.assertTrue(warning.ok)
        self.assertEqual(warning.severity, "warning")
        self.assertTrue(warning.data["writes_tdarr_matrix_run_root"])
        self.assertTrue(background.ok)
        self.assertTrue(background.data["background_started"])
        self.assertEqual(background.data["tdarr_matrix_audit_progress"]["status"], "active")
        self.assertIn("started in background", background.message)
        self.assertTrue(existing.ok)
        self.assertTrue(existing.data["already_running"])
        self.assertEqual(existing.severity, "warning")
        self.assertEqual(existing.data["tdarr_matrix_audit_progress"]["status"], "active")
        self.assertFalse(invalid.ok)
        self.assertIn("Allowed actions", invalid.errors[1])

    def test_result_includes_findings_preview_from_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "tdarr_matrix_audit_report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "severity": "warning",
                                "code": "classified_processing_failure",
                                "message": "SingleFile processing failed with structured evidence.",
                                "case_id": "tdarr-0003",
                                "view": "movies",
                                "diagnostic_bucket": "audio-only",
                                "generated_path": "source/Movies/audio-only/Fake Title.mkv",
                                "source_path": "C:/cache/source.mkv",
                                "evidence": {
                                    "worker_result": {
                                        "MediaKind": "movie",
                                        "Route": "remux",
                                        "RouteReasonCode": "codec_not_remux_safe",
                                        "Status": "failed",
                                        "Reason": "Processing failed",
                                        "SourceName": "Fake Title.mkv",
                                    }
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = tdarr_matrix_audit_result(
                {
                    "success": True,
                    "timed_out": False,
                    "returncode": 0,
                    "action": "smoke-pack",
                    "mode": "run-samples",
                    "label": "Run Tdarr Smoke Pack",
                    "report_only": True,
                    "selected_count": tdarr_expected_manifest_count("smoke-pack"),
                    "finding_count": 1,
                    "report_path": str(report_path),
                    "run_root": str(Path(tmp) / "run"),
                    "stdout": "{}",
                    "stderr": "",
                }
            )

        self.assertEqual(result.data["findings_preview_total"], 1)
        self.assertFalse(result.data["findings_preview_truncated"])
        self.assertEqual(result.data["findings_preview_error"], "")
        row = result.data["findings_preview"][0]
        self.assertEqual(row["case_id"], "tdarr-0003")
        self.assertEqual(row["diagnostic_bucket"], "audio-only")
        self.assertEqual(row["route"], "remux")
        self.assertEqual(row["route_reason_code"], "codec_not_remux_safe")
        self.assertEqual(row["source_name"], "Fake Title.mkv")

    def test_runner_timeout_covers_prepare_and_sample_worst_case(self) -> None:
        # G1: the outer process timeout must not fire before prepare-evidence
        # (three pipeline commands) plus every sample can finish.
        for action in TDARR_MATRIX_AUDIT_ALLOWED_ACTIONS:
            preset = tdarr_matrix_audit_preset(action)
            assert preset is not None
            sample_count = 0
            if preset.get("mode") == "run-samples":
                sample_count = (
                    int(preset.get("sample_count_hint", 0))
                    if preset.get("sample_count_hint") or preset.get("case_pack") or preset.get("all_samples")
                    else int(preset["samples_per_bucket"]) * TDARR_MATRIX_AUDIT_BUCKET_COUNT
                )
            worst_case = (
                3 * int(preset["prepare_timeout_seconds"])
                + sample_count * int(preset["sample_timeout_seconds"])
            )
            timeout = tdarr_matrix_audit_runner_timeout(preset)
            self.assertGreaterEqual(
                timeout,
                worst_case + TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS,
                msg=f"{action} runner timeout {timeout} below worst case {worst_case}",
            )
            # Never lower than the originally configured floor.
            self.assertGreaterEqual(timeout, int(preset["runner_timeout_seconds"]))

    def test_runner_timeout_raises_report_floor_for_prepare_evidence(self) -> None:
        # report/strict have a 900s floor but prepare-evidence alone can take 3*1800s.
        report = tdarr_matrix_audit_preset("report")
        assert report is not None
        self.assertEqual(int(report["runner_timeout_seconds"]), 900)
        self.assertEqual(tdarr_matrix_audit_runner_timeout(report), 3 * 1800 + TDARR_MATRIX_AUDIT_RUNNER_TIMEOUT_MARGIN_SECONDS)

    def test_progress_payload_status_transitions(self) -> None:
        from mediapipeline.core.diagnostics.tdarr_matrix_audit import tdarr_matrix_audit_progress_payload

        clean = tdarr_matrix_audit_progress_payload({"success": True, "mode": "report", "finding_count": 0, "report_path": "r.json"})
        self.assertEqual(clean["status"], "complete")
        self.assertEqual(len(clean["progress_bars"]), 1)
        warn = tdarr_matrix_audit_progress_payload(
            {"success": True, "mode": "run-samples", "finding_count": 3, "report_path": "r.json", "selected_count": 6}
        )
        self.assertEqual(warn["status"], "warning")
        blocked = tdarr_matrix_audit_progress_payload({"success": False, "timed_out": True, "mode": "report"})
        self.assertEqual(blocked["status"], "blocked")
        error = tdarr_matrix_audit_progress_payload({"success": False, "timed_out": False, "mode": "report", "returncode": 2})
        self.assertEqual(error["status"], "error")

    def test_bucket_count_matches_tool_and_generator(self) -> None:
        # G2: the run-samples harness iterates BUCKET_ORDER; the generator names
        # series per bucket; the core timeout sizing uses BUCKET_COUNT. Drift here
        # would silently drop a whole bucket from smoke/matrix sampling.
        from mediapipeline.tools.dev import materialize_tdarr_test_library as generator
        from mediapipeline.tools.dev import tdarr_matrix_audit as tool

        self.assertEqual(set(tool.BUCKET_ORDER), set(generator.BUCKET_SERIES))
        self.assertEqual(len(tool.BUCKET_ORDER), TDARR_MATRIX_AUDIT_BUCKET_COUNT)

    def test_console_payload_discovers_latest_run_and_enriches_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_proof_manifest(root, [_manifest_row(root, case_id="tdarr-0002", view="tv", bucket="audio-only")])
            _write_fake_tdarr_run(root, "run-20260608-000001", findings=[])
            _write_fake_tdarr_run(root, "run-20260608-000002", findings=[_finding()])

            payload = tdarr_matrix_console_payload(root)

        self.assertEqual(payload["schema_version"], "desktop_tdarr_matrix_console.v1")
        self.assertEqual(payload["latest_run_id"], "run-20260608-000002")
        self.assertEqual(payload["finding_count"], 1)
        self.assertEqual(payload["severity_counts"], {"warning": 1})
        self.assertEqual(payload["sample_summary"]["selected_count"], 2)
        self.assertEqual(payload["sample_summary"]["movie_count"], 1)
        self.assertEqual(payload["sample_summary"]["tv_count"], 1)
        self.assertEqual(payload["run"]["worker_result_count"], 2)
        self.assertEqual(payload["run"]["progress_percent"], 100.0)
        self.assertEqual(payload["bucket_summary"][0]["diagnostic_bucket"], "audio-only")
        self.assertEqual(payload["bucket_summary"][0]["selected_count"], 2)
        self.assertEqual(payload["bucket_summary"][0]["finding_count"], 1)
        finding = payload["findings"][0]
        self.assertIn("run-20260608-000002:tdarr-0001:movies:classified_processing_failure", finding["finding_key"])
        self.assertEqual(finding["available_evidence_targets"], ["stdout", "stderr", "worker_result", "source_hashes", "report_folder"])

    def test_console_payload_returns_planned_proof_pack_rows_before_any_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_proof_manifest(
                root,
                [
                    _manifest_row(root, case_id="tdarr-0002", view="movies", bucket="audio-only"),
                    _manifest_row(root, case_id="tdarr-0258", view="tv", bucket="h264-h265-direct"),
                ],
            )

            payload = tdarr_matrix_console_payload(root)

        self.assertEqual(payload["latest_run_id"], "")
        self.assertEqual([row["case_key"] for row in payload["smoke_pack_rows"]], ["tdarr-0002:movies"])
        self.assertEqual({row["case_key"] for row in payload["proof_pack_rows"]}, {"tdarr-0002:movies", "tdarr-0258:tv"})
        self.assertEqual({row["status"] for row in payload["proof_pack_rows"]}, {"not run"})

    def test_console_payload_warns_without_parsing_oversized_report_or_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = _write_fake_tdarr_run(root, "run-20260608-oversized", findings=[_finding()])
            report_path = run_root / "manifests" / "audit" / "tdarr_matrix_audit_report.json"
            manifest_path = run_root / "manifests" / "materialized_library.csv"
            report_path.write_text('{"findings":[],' + (" " * 128) + "}", encoding="utf-8")
            manifest_path.write_text("case_id,view\n" + ("x" * 128), encoding="utf-8")

            with (
                patch("mediapipeline.core.diagnostics.tdarr_matrix_console.TDARR_MATRIX_REPORT_MAX_BYTES", 32),
                patch("mediapipeline.core.diagnostics.tdarr_matrix_console.TDARR_MATRIX_MANIFEST_MAX_BYTES", 32),
            ):
                payload = tdarr_matrix_console_payload(root, run_id="run-20260608-oversized")

        self.assertEqual(payload["schema_version"], "desktop_tdarr_matrix_console.v1")
        self.assertEqual(payload["finding_count"], 0)
        self.assertEqual(payload["sample_summary"]["selected_count"], 0)
        self.assertEqual(payload["artifact_warning_count"], 2)
        self.assertIn("too large for bounded diagnostics parsing", "\n".join(payload["artifact_warnings"]))
        self.assertEqual(payload["run"]["artifact_warning_count"], 2)

    def test_console_payload_reports_requested_run_before_report_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = tdarr_matrix_console_payload(root, run_id="run-20260608-000099-full")

        self.assertEqual(payload["latest_run_id"], "run-20260608-000099-full")
        self.assertEqual(payload["run"]["status"], "starting")
        self.assertFalse(payload["run"]["sentinel_exists"])
        self.assertEqual(payload["finding_count"], 0)
        self.assertIn("has been requested", payload["message"])

    def test_console_payload_marks_incomplete_run_with_worker_results_as_processing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = _write_fake_tdarr_run(root, "run-20260608-000100-full", findings=[])
            (run_root / "manifests" / "audit" / "tdarr_matrix_audit_report.json").unlink()
            payload = tdarr_matrix_console_payload(root, run_id="run-20260608-000100-full")

        self.assertEqual(payload["run"]["status"], "processing")
        self.assertEqual(payload["run"]["worker_result_count"], 2)

    def test_evidence_open_resolves_allowlisted_target_inside_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = _write_fake_tdarr_run(root, "run-20260608-000003", findings=[_finding()])
            payload = tdarr_matrix_console_payload(root, run_id="run-20260608-000003")
            finding_key = payload["findings"][0]["finding_key"]
            opened: list[Path] = []

            result = tdarr_matrix_evidence_open_result(
                root,
                {"run_id": "run-20260608-000003", "finding_key": finding_key, "target": "stdout"},
                opener=opened.append,
            )
            rejected = tdarr_matrix_evidence_open_result(
                root,
                {"run_id": "run-20260608-000003", "finding_key": finding_key, "target": str(root / "secret.txt")},
                opener=opened.append,
            )

        self.assertTrue(result.ok)
        self.assertEqual(opened, [run_root / "manifests" / "audit" / "files" / "tdarr-0001-movies" / "stdout.log"])
        self.assertFalse(rejected.ok)
        self.assertIn("Allowed targets", " ".join(rejected.errors))
        self.assertEqual(set(TDARR_MATRIX_CONSOLE_EVIDENCE_TARGETS), {"stdout", "stderr", "worker_result", "source_hashes", "failure_artifact", "output", "report_folder"})

    def test_console_compare_identifies_new_resolved_repeated_and_changed_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fake_tdarr_run(
                root,
                "run-left",
                findings=[
                    _finding(case_id="tdarr-0001", view="movies", code="same", message="old message"),
                    _finding(case_id="tdarr-0002", view="tv", code="resolved", message="resolved"),
                ],
            )
            _write_fake_tdarr_run(
                root,
                "run-right",
                findings=[
                    _finding(case_id="tdarr-0001", view="movies", code="same", message="new message"),
                    _finding(case_id="tdarr-0003", view="movies", code="new", message="new"),
                ],
            )

            comparison = tdarr_matrix_compare_runs_payload(root, left_run_id="run-left", right_run_id="run-right")

        self.assertEqual(comparison["schema_version"], "desktop_tdarr_matrix_compare.v1")
        self.assertEqual(comparison["left_run_id"], "run-left")
        self.assertEqual(comparison["right_run_id"], "run-right")
        self.assertEqual(comparison["counts"], {"new": 1, "resolved": 1, "repeated": 1, "changed": 1})
        self.assertEqual(comparison["new_findings"][0]["code"], "new")
        self.assertEqual(comparison["resolved_findings"][0]["code"], "resolved")
        self.assertEqual(comparison["changed_findings"][0]["left_message"], "old message")
        self.assertEqual(comparison["changed_findings"][0]["right_message"], "new message")

    def test_rerun_case_keys_use_finding_keys_not_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_fake_tdarr_run(root, "run-20260608-000004", findings=[_finding()])
            payload = tdarr_matrix_console_payload(root, run_id="run-20260608-000004")
            finding_key = payload["findings"][0]["finding_key"]

            selected_keys = tdarr_matrix_rerun_case_keys(
                root,
                {
                    "source_run_id": "run-20260608-000004",
                    "selection": "selected",
                    "finding_keys": [finding_key],
                },
            )
            latest_failure_keys = tdarr_matrix_rerun_case_keys(
                root,
                {
                    "source_run_id": "run-20260608-000004",
                    "selection": "latest_failures",
                    "finding_keys": [],
                },
            )
            args = tdarr_matrix_audit_arguments(
                action="proof-pack",
                library_root=tdarr_matrix_library_root(root),
                powershell="pwsh",
                entrypoint=root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
                case_keys=selected_keys,
            )

        self.assertEqual(selected_keys, ["tdarr-0001:movies"])
        self.assertEqual(latest_failure_keys, ["tdarr-0001:movies"])
        self.assertEqual(args.count("--case-key"), 1)
        self.assertIn("tdarr-0001:movies", args)
        self.assertNotIn("generated_path", " ".join(args))
        self.assertNotIn("source_path", " ".join(args))


class TdarrMatrixAuditFacadeConcurrencyTests(unittest.TestCase):
    def test_facade_blocks_when_diagnostics_lock_is_held(self) -> None:
        # G3 regression: a second concurrent run is rejected with a clean result, not raced.
        lock = threading.Lock()
        lock.acquire()
        calls: list[dict] = []
        harness = _FacadeHarness(lock, lambda **kw: calls.append(kw) or _successful_runner_payload())
        result = harness.run_tdarr_matrix_audit({"action": "report"})
        self.assertFalse(result.ok)
        self.assertIn("already in progress", " ".join(result.errors).lower())
        self.assertEqual(calls, [])  # runner never invoked while busy
        lock.release()

    def test_facade_runs_and_releases_lock_when_free(self) -> None:
        lock = threading.Lock()
        calls: list[dict] = []
        harness = _FacadeHarness(lock, lambda **kw: calls.append(kw) or _successful_runner_payload())
        result = harness.run_tdarr_matrix_audit({"action": "report"})
        self.assertTrue(result.ok)
        self.assertEqual(calls[0]["action"], "report")
        # Lock must be released after a successful run so the next run can proceed.
        self.assertTrue(lock.acquire(blocking=False))
        lock.release()


if __name__ == "__main__":
    unittest.main()
