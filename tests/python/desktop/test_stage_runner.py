from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__))))

from mediapipeline.contracts.stages import StageName
from mediapipeline.core.orchestration.runner import RunnerOptions, StageProcessResult, run_decide_stage, run_probe_stage, run_stage


def _stage_stdout(
    *,
    stage: str = "decide",
    ok: bool = True,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc).isoformat()
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


if __name__ == "__main__":
    unittest.main()

