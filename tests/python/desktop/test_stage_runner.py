from __future__ import annotations

import json
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone, UTC
from pathlib import Path
from typing import Any
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__))))

from mediapipeline.contracts.stages import StageName
from mediapipeline.core.orchestration.runner import (
    RunnerOptions,
    StageProcessResult,
    run_decide_stage,
    run_ingest_stage,
    run_probe_stage,
    run_rename_stage,
    run_stage,
)


def _stage_stdout(
    *,
    stage: str = "decide",
    ok: bool = True,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "schema_version": "v1",
        "stage": stage,
        "ok": ok,
        "started_at": now,
        "finished_at": now,
        "duration_ms": 0,
        "journal_event_type": f"pipeline.stage.{stage.replace('-', '_')}",
    }
    if ok:
        payload["data"] = data or {"route": "remux", "should_encode": False}
    else:
        payload["error"] = error or {"code": "stage.failed", "message": "failed"}
    return json.dumps(payload)


class StageRunnerTests(unittest.TestCase):
    def _payload(self) -> dict[str, Any]:
        return {"file_size_bytes": 1024, "duration_seconds": 60, "video_codec": "hevc"}

    def _existing_entrypoint(self) -> Path:
        return Path(__file__)

    def _rename_options(self, scratch: Path, source_root: Path, **kwargs: Any) -> RunnerOptions:
        return RunnerOptions(
            allowed_scratch_roots=(scratch,),
            protected_source_roots=(source_root,),
            **kwargs,
        )

    def test_run_stage_parses_success_json_with_stderr_noise(self) -> None:
        def fake_run(args, **kwargs):
            self.assertIn("-Stage", args)
            self.assertIn("decide", args)
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(), stderr="diagnostic noise")

        result = run_stage(
            StageName.decide,
            self._payload(),
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["route"], "remux")

    def test_run_stage_classifies_malformed_json(self) -> None:
        def fake_run(args, **kwargs):
            return StageProcessResult(args=args, returncode=0, stdout="{not json", stderr="")

        result = run_decide_stage(
            self._payload(),
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.result_json_invalid")

    def test_run_stage_rejects_result_for_wrong_stage(self) -> None:
        def fake_run(args, **kwargs):
            return StageProcessResult(
                args=args,
                returncode=0,
                stdout=_stage_stdout(
                    stage="probe",
                    data={"probe_ok": True, "tool_path": "C:/Tools/ffprobe.exe"},
                ),
                stderr="",
            )

        result = run_decide_stage(
            self._payload(),
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "decide")
        self.assertEqual(result.error.code if result.error else "", "stage.result_stage_mismatch")

    def test_run_stage_validates_stage_specific_success_data(self) -> None:
        def fake_run(args, **kwargs):
            return StageProcessResult(
                args=args,
                returncode=0,
                stdout=_stage_stdout(data={"probe_ok": True, "tool_path": "C:/Tools/ffprobe.exe"}),
                stderr="",
            )

        result = run_decide_stage(
            self._payload(),
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.result_contract_invalid")

    def test_run_stage_classifies_nonzero_without_json(self) -> None:
        def fake_run(args, **kwargs):
            return StageProcessResult(args=args, returncode=9, stdout="", stderr="boom")

        result = run_decide_stage(
            self._payload(),
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.process_nonzero")

    def test_run_stage_preserves_structured_nonzero_stage_error(self) -> None:
        def fake_run(args, **kwargs):
            return StageProcessResult(
                args=args,
                returncode=2,
                stdout=_stage_stdout(ok=False, error={"code": "stage.not_enabled", "message": "not enabled"}),
                stderr="",
            )

        result = run_decide_stage(
            self._payload(),
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.not_enabled")

    def test_run_stage_classifies_timeout(self) -> None:
        def fake_run(args, **kwargs):
            return StageProcessResult(
                args=args,
                returncode=None,
                stdout="",
                stderr="",
                timed_out=True,
                kill_message="process killed",
            )

        result = run_decide_stage(
            self._payload(),
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.timeout")

    def test_run_stage_classifies_missing_entrypoint_before_spawn(self) -> None:
        called = False

        def fake_run(args, **kwargs):
            nonlocal called
            called = True
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(), stderr="")

        result = run_decide_stage(
            self._payload(),
            RunnerOptions(entrypoint_path=Path("missing-entrypoint.ps1"), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.entrypoint_missing")
        self.assertFalse(called)

    def test_run_stage_classifies_invalid_payload_before_spawn(self) -> None:
        called = False

        def fake_run(args, **kwargs):
            nonlocal called
            called = True
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(), stderr="")

        result = run_decide_stage(
            {},
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")
        self.assertFalse(called)

    def test_run_stage_classifies_unknown_stage_before_spawn(self) -> None:
        called = False

        def fake_run(args, **kwargs):
            nonlocal called
            called = True
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(), stderr="")

        result = run_stage(
            "unknown-stage",
            {},
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "unknown-stage")
        self.assertEqual(result.error.code if result.error else "", "stage.unknown")
        self.assertFalse(called)

    def test_run_stage_records_command_journal_payload(self) -> None:
        journal: list[dict[str, Any]] = []

        def fake_run(args, **kwargs):
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(), stderr="")

        result = run_decide_stage(
            {**self._payload(), "job_id": "job-1"},
            RunnerOptions(
                entrypoint_path=self._existing_entrypoint(),
                powershell_path="pwsh",
                run_capture_func=fake_run,
                journal_record=journal.append,
            ),
        )

        self.assertTrue(result.ok)
        self.assertEqual(journal[0]["schema_version"], "desktop_command_result.v1")
        self.assertEqual(journal[0]["command"], "stage.decide")
        self.assertEqual(journal[0]["job_id"], "job-1")
        self.assertEqual(journal[0]["data"]["stage"], "decide")

    def test_run_probe_stage_uses_probe_stage_boundary(self) -> None:
        def fake_run(args, **kwargs):
            self.assertIn("-Stage", args)
            self.assertIn("probe", args)
            return StageProcessResult(
                args=args,
                returncode=0,
                stdout=_stage_stdout(
                    stage="probe",
                    data={
                        "probe_ok": False,
                        "probe_error": "file_missing",
                        "tool_path": "C:/Tools/ffprobe.exe",
                    },
                ),
                stderr="",
            )

        result = run_probe_stage(
            {"scratch_path": "missing.mkv"},
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.stage, "probe")
        self.assertFalse(result.data["probe_ok"])
        self.assertEqual(result.data["tool_path"], "C:/Tools/ffprobe.exe")

    def test_run_ingest_stage_records_evidence_paths_and_recovery_actions(self) -> None:
        journal: list[dict[str, Any]] = []
        operation_journal: list[dict[str, Any]] = []

        def fake_run(args, **kwargs):
            self.assertIn("-Stage", args)
            self.assertIn("ingest", args)
            return StageProcessResult(
                args=args,
                returncode=0,
                stdout=_stage_stdout(
                    stage="ingest",
                    data={
                        "scratch_path": "D:/Scratch/stage_ingest_job-1/source.mkv",
                        "size_bytes": 10,
                        "sha256": "abc",
                        "source_sha256": "abc",
                        "source_unchanged": True,
                        "evidence_path": "D:/Scratch/stage_ingest_job-1/source.mkv.ingest_evidence.json",
                        "rollback_actions": ["delete scratch_path"],
                        "recovery_actions": ["rerun ingest"],
                        "boundary_checks": ["scratch target is a child of scratch_root"],
                    },
                ),
                stderr="",
            )

        result = run_ingest_stage(
            {
                "source_path": "C:/Media/source.mkv",
                "scratch_root": "D:/Scratch",
                "intent": "execute",
                "confirm_ingest": True,
                "job_id": "job-1",
                "operation_id": str(uuid.uuid4()),
                "scratch_reservation_id": "stage_ingest_job-1",
                "dry_run_fingerprint": "a" * 64,
            },
            RunnerOptions(
                entrypoint_path=self._existing_entrypoint(),
                powershell_path="pwsh",
                run_capture_func=fake_run,
                journal_record=journal.append,
                operation_journal_record=lambda payload: operation_journal.append(dict(payload)) or None,
            ),
        )

        self.assertTrue(result.ok)
        self.assertEqual(journal[0]["command"], "stage.ingest")
        self.assertEqual(journal[0]["log_paths"]["stage_evidence"], "D:/Scratch/stage_ingest_job-1/source.mkv.ingest_evidence.json")
        self.assertTrue(journal[0]["data"]["source_unchanged"])
        self.assertEqual(journal[0]["data"]["rollback_actions"], ["delete scratch_path"])
        self.assertEqual(journal[0]["data"]["recovery_actions"], ["rerun ingest"])
        self.assertEqual(journal[0]["data"]["boundary_checks"], ["scratch target is a child of scratch_root"])
        self.assertEqual([event["event"] for event in operation_journal], ["accepted", "completed"])

    def test_run_ingest_stage_rejects_string_confirmation_before_spawn(self) -> None:
        called = False

        def fake_run(args, **kwargs):
            nonlocal called
            called = True
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(), stderr="")

        result = run_ingest_stage(
            {
                "source_path": "C:/Media/source.mkv",
                "scratch_root": "D:/Scratch",
                "intent": "execute",
                "confirm_ingest": "true",
            },
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")
        self.assertFalse(called)

    def test_disabled_mutation_stage_is_rejected_before_spawn(self) -> None:
        called = False

        def fake_run(args, **kwargs):
            nonlocal called
            called = True
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(stage="transcode"), stderr="")

        result = run_stage(
            StageName.transcode,
            {
                "scratch_path": "D:/Scratch/source.mkv",
                "output_path": "D:/Scratch/output.mkv",
                "decision": {"route": "encode", "should_encode": True},
                "intent": "dry_run",
            },
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.not_enabled")
        self.assertFalse(called)

    def test_ingest_execute_requires_strict_operation_journal_before_spawn(self) -> None:
        called = False

        def fake_run(args, **kwargs):
            nonlocal called
            called = True
            return StageProcessResult(args=args, returncode=0, stdout=_stage_stdout(stage="ingest"), stderr="")

        result = run_ingest_stage(
            {
                "source_path": "C:/Media/source.mkv",
                "scratch_root": "D:/Scratch",
                "intent": "execute",
                "confirm_ingest": True,
                "operation_id": str(uuid.uuid4()),
                "scratch_reservation_id": "stage_ingest_job-1",
                "dry_run_fingerprint": "a" * 64,
            },
            RunnerOptions(entrypoint_path=self._existing_entrypoint(), powershell_path="pwsh", run_capture_func=fake_run),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else "", "stage.operation_journal_required")
        self.assertFalse(called)

    def test_rename_stage_missing_confirmation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-confirm-") as tmp:
            root = Path(tmp)
            scratch = root / "Scratch"
            source_root = root / "Source"
            scratch.mkdir()
            source_root.mkdir()
            target = scratch / "Old.mkv"
            target.write_bytes(b"scratch fixture")

            result = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "execute",
                    "operation_id": str(uuid.uuid4()),
                    "dry_run_fingerprint": "a" * 64,
                },
                self._rename_options(scratch, source_root),
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.invalid_payload")
            self.assertTrue(target.exists())
            self.assertFalse((scratch / "New.mkv").exists())

    def test_rename_stage_rejects_source_root_overlap_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-source-boundary-") as tmp:
            root = Path(tmp)
            source_root = root / "Source"
            scratch = source_root / "Scratch"
            scratch.mkdir(parents=True)
            target = scratch / "Old.mkv"
            target.write_bytes(b"protected source fixture")

            result = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "dry_run",
                },
                self._rename_options(scratch, source_root),
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.source_boundary_violation")
            self.assertTrue(target.exists())
            self.assertFalse((scratch / "New.mkv").exists())

    def test_rename_stage_rejects_target_outside_scratch_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-path-boundary-") as tmp:
            root = Path(tmp)
            scratch = root / "Scratch"
            source_root = root / "Source"
            outside = root / "Outside"
            scratch.mkdir()
            source_root.mkdir()
            outside.mkdir()
            target = outside / "Old.mkv"
            target.write_bytes(b"outside fixture")

            result = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "dry_run",
                },
                self._rename_options(scratch, source_root),
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.path_boundary_violation")
            self.assertTrue(target.exists())
            self.assertFalse((outside / "New.mkv").exists())

    def test_rename_stage_rejects_untrusted_source_root_declaration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-source-config-") as tmp:
            root = Path(tmp)
            scratch = root / "Scratch"
            source_root = root / "Source"
            untrusted_root = root / "UntrustedDeclaration"
            scratch.mkdir()
            source_root.mkdir()
            untrusted_root.mkdir()
            target = scratch / "Old.mkv"
            target.write_bytes(b"scratch fixture")

            result = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(untrusted_root)],
                    "proposed_name": "New.mkv",
                    "intent": "dry_run",
                },
                self._rename_options(scratch, source_root),
            )

            self.assertFalse(result.ok)
            self.assertEqual(
                result.error.code if result.error else "",
                "stage.source_boundary_configuration_mismatch",
            )
            self.assertTrue(target.exists())
            self.assertFalse((scratch / "New.mkv").exists())

    def test_rename_stage_rejects_stale_dry_run_fingerprint_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-fingerprint-") as tmp:
            root = Path(tmp)
            scratch = root / "Scratch"
            source_root = root / "Source"
            scratch.mkdir()
            source_root.mkdir()
            target = scratch / "Old.mkv"
            target.write_bytes(b"scratch fixture")

            result = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "execute",
                    "confirm_apply": True,
                    "operation_id": str(uuid.uuid4()),
                    "dry_run_fingerprint": "0" * 64,
                },
                self._rename_options(
                    scratch,
                    source_root,
                    journal_record=lambda payload: None,
                    operation_journal_record=lambda payload: None,
                ),
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.dry_run_fingerprint_mismatch")
            self.assertTrue(target.exists())
            self.assertFalse((scratch / "New.mkv").exists())

    def test_rename_execute_requires_command_journal_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-journal-") as tmp:
            root = Path(tmp)
            scratch = root / "Scratch"
            source_root = root / "Source"
            scratch.mkdir()
            source_root.mkdir()
            target = scratch / "Old.mkv"
            target.write_bytes(b"scratch fixture")
            dry_run = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "dry_run",
                },
                self._rename_options(scratch, source_root),
            )

            result = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "execute",
                    "confirm_apply": True,
                    "operation_id": str(uuid.uuid4()),
                    "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
                },
                self._rename_options(scratch, source_root, operation_journal_record=lambda payload: None),
            )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.command_journal_required")
            self.assertTrue(target.exists())
            self.assertFalse((scratch / "New.mkv").exists())

    def test_rename_stage_executes_once_with_journal_and_undo_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-execute-") as tmp:
            root = Path(tmp)
            scratch = root / "Scratch"
            source_root = root / "Source"
            scratch.mkdir()
            source_root.mkdir()
            target = scratch / "Old.mkv"
            target.write_bytes(b"scratch fixture")
            journal: list[dict[str, Any]] = []
            operation_state: dict[str, dict[str, Any]] = {}

            def operation_journal(payload: dict[str, Any]) -> dict[str, Any] | None:
                operation_id = str(payload["operation_id"])
                if payload["event"] == "accepted":
                    previous = operation_state.get(operation_id)
                    if previous is not None:
                        return previous
                    operation_state[operation_id] = {}
                    return None
                operation_state[operation_id] = {"result": payload["result"]}
                return None

            dry_run = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "dry_run",
                },
                self._rename_options(scratch, source_root, journal_record=journal.append),
            )
            self.assertTrue(dry_run.ok, dry_run)
            operation_id = str(uuid.uuid4())
            execute_payload = {
                "target_path": str(target),
                "scratch_root": str(scratch),
                "source_roots": [str(source_root)],
                "proposed_name": "New.mkv",
                "intent": "execute",
                "confirm_apply": True,
                "operation_id": operation_id,
                "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
            }
            result = run_rename_stage(
                execute_payload,
                self._rename_options(
                    scratch,
                    source_root,
                    journal_record=journal.append,
                    operation_journal_record=operation_journal,
                ),
            )

            self.assertTrue(result.ok, result)
            destination = scratch / "New.mkv"
            self.assertFalse(target.exists())
            self.assertEqual(destination.read_bytes(), b"scratch fixture")
            undo_path = Path(result.data["undo_record_path"])
            self.assertTrue(undo_path.exists())
            undo = json.loads(undo_path.read_text(encoding="utf-8"))
            self.assertEqual(undo["status"], "completed")
            self.assertEqual(undo["source_media_mutation"], "forbidden")
            self.assertTrue(result.data["source_boundary_untouched"])
            self.assertEqual(journal[-1]["command"], "stage.rename")
            self.assertEqual(journal[-1]["data"]["undo_record_path"], str(undo_path))

            replay = run_rename_stage(
                execute_payload,
                self._rename_options(
                    scratch,
                    source_root,
                    journal_record=journal.append,
                    operation_journal_record=operation_journal,
                ),
            )
            self.assertTrue(replay.ok)
            self.assertEqual(replay.data["operation_id"], operation_id)
            self.assertEqual(destination.read_bytes(), b"scratch fixture")

    def test_rename_stage_rolls_back_when_terminal_evidence_write_fails(self) -> None:
        from mediapipeline.core.rename import stage as rename_stage

        with tempfile.TemporaryDirectory(prefix="mediapipeline-stage-rename-rollback-") as tmp:
            root = Path(tmp)
            scratch = root / "Scratch"
            source_root = root / "Source"
            scratch.mkdir()
            source_root.mkdir()
            target = scratch / "Old.mkv"
            target.write_bytes(b"scratch fixture")
            dry_run = run_rename_stage(
                {
                    "target_path": str(target),
                    "scratch_root": str(scratch),
                    "source_roots": [str(source_root)],
                    "proposed_name": "New.mkv",
                    "intent": "dry_run",
                },
                self._rename_options(scratch, source_root),
            )
            self.assertTrue(dry_run.ok)
            real_write = rename_stage._write_manifest
            write_count = 0

            def fail_terminal_write(path: Path, payload: dict[str, Any]) -> None:
                nonlocal write_count
                write_count += 1
                if write_count == 2:
                    raise OSError("terminal evidence denied")
                real_write(path, payload)

            with patch.object(rename_stage, "_write_manifest", side_effect=fail_terminal_write):
                result = run_rename_stage(
                    {
                        "target_path": str(target),
                        "scratch_root": str(scratch),
                        "source_roots": [str(source_root)],
                        "proposed_name": "New.mkv",
                        "intent": "execute",
                        "confirm_apply": True,
                        "operation_id": str(uuid.uuid4()),
                        "dry_run_fingerprint": dry_run.data["dry_run_fingerprint"],
                    },
                    self._rename_options(
                        scratch,
                        source_root,
                        journal_record=lambda payload: None,
                        operation_journal_record=lambda payload: None,
                    ),
                )

            self.assertFalse(result.ok)
            self.assertEqual(result.error.code if result.error else "", "stage.recovery_required")
            self.assertTrue(target.exists())
            self.assertEqual(target.read_bytes(), b"scratch fixture")
            self.assertFalse((scratch / "New.mkv").exists())


if __name__ == "__main__":
    unittest.main()
