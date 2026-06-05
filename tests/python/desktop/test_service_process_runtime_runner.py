from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.processes.runtime_runner import (
    clear_runtime_artifacts_for_service,
    prepare_audit_runtime_for_service,
    prepare_pipeline_runtime_for_service,
    runtime_artifact_specs_for_service,
    runtime_state_root_for_service,
    validate_runtime_artifact_target_for_service,
)


class DummyRuntimeRunnerService:
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_service_process_runtime_runner")
        self.logger.addHandler(logging.NullHandler())
        self.related_processes: list[object] = []

    def _state_root_for_local_base(self, local_base: Path) -> Path:
        return local_base / "State"

    def _normalized_path_key(self, path: Path) -> str:
        return str(path.resolve(strict=False)).casefold()

    def _runtime_artifact_specs(
        self,
        resolved: ResolvedPaths,
        *,
        include_pipeline: bool,
        include_audit: bool,
    ):
        return runtime_artifact_specs_for_service(
            self,
            resolved,
            include_pipeline=include_pipeline,
            include_audit=include_audit,
        )

    def _clear_pipeline_progress_artifacts(self, resolved: ResolvedPaths) -> list[str]:
        specs = [
            spec
            for spec in self._runtime_artifact_specs(resolved, include_pipeline=True, include_audit=False)
            if spec[0] in {"pipeline progress", "legacy pipeline progress"}
        ]
        from mediapipeline.core.processes.runtime_artifacts import clear_runtime_artifact_specs

        return clear_runtime_artifact_specs(specs, normalized_path_key=self._normalized_path_key)

    def _clear_audit_progress_artifacts(self, resolved: ResolvedPaths) -> list[str]:
        specs = [
            spec
            for spec in self._runtime_artifact_specs(resolved, include_pipeline=False, include_audit=True)
            if spec[0] == "audit progress"
        ]
        from mediapipeline.core.processes.runtime_artifacts import clear_runtime_artifact_specs

        return clear_runtime_artifact_specs(specs, normalized_path_key=self._normalized_path_key)

    def read_progress(self, _resolved: ResolvedPaths) -> dict[str, object]:
        return {"Status": "Processing"}

    def is_progress_stale(self, _progress: dict[str, object], *, stale_after_seconds: float) -> bool:
        return stale_after_seconds <= 1

    def read_audit_progress(self, _resolved: ResolvedPaths) -> dict[str, object]:
        return {"status": "scanning"}

    def is_audit_progress_stale(self, _progress: dict[str, object], *, stale_after_seconds: float) -> bool:
        return stale_after_seconds <= 1

    def find_related_pipeline_processes(self, _resolved: ResolvedPaths) -> list[object]:
        return self.related_processes


def _resolved(root: Path) -> ResolvedPaths:
    local_base = root / "LocalBase"
    state_root = local_base / "State"
    pipeline_state = state_root / "Pipeline"
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1",
        audit_script_path=root / "Pipeline" / "Audit-MediaLibrary.ps1",
        rerun_script_path=root / "Pipeline" / "Invoke-RerunCsv.ps1",
        powershell_host="pwsh",
        local_base=local_base,
        state_root=state_root,
        progress_file=state_root / "Progress" / "pipeline_progress.json",
        pause_flag=pipeline_state / "pipeline_pause.flag",
        stop_flag=pipeline_state / "pipeline_stop.flag",
        rescan_flag=pipeline_state / "pipeline_rescan.flag",
        audit_reports_path=local_base / "AuditReports",
    )


class ProcessRuntimeRunnerTests(unittest.TestCase):
    def test_runtime_root_prefers_local_base_state_store(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyRuntimeRunnerService()
            resolved = _resolved(root)

            state_root = runtime_state_root_for_service(service, resolved)

        self.assertEqual(state_root, root / "LocalBase" / "State")

    def test_runtime_artifact_specs_include_pipeline_audit_and_legacy_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyRuntimeRunnerService()
            resolved = _resolved(root)

            specs = runtime_artifact_specs_for_service(service, resolved, include_pipeline=True, include_audit=True)
            labels = [label for label, _path, _expected in specs]

        self.assertIn("pipeline progress", labels)
        self.assertIn("legacy pipeline progress", labels)
        self.assertIn("pause flag", labels)
        self.assertIn("audit progress", labels)

    def test_validate_runtime_artifact_target_uses_service_path_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyRuntimeRunnerService()
            expected = [root / "LocalBase" / "State" / "Progress" / "pipeline_progress.json"]

            with self.assertRaisesRegex(RuntimeError, "unexpected filename"):
                validate_runtime_artifact_target_for_service(
                    service,
                    "pipeline progress",
                    root / "LocalBase" / "State" / "Progress" / "wrong.json",
                    expected,
                )

    def test_clear_runtime_artifacts_removes_only_declared_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyRuntimeRunnerService()
            resolved = _resolved(root)
            assert resolved.progress_file is not None
            assert resolved.pause_flag is not None
            resolved.progress_file.parent.mkdir(parents=True, exist_ok=True)
            resolved.pause_flag.parent.mkdir(parents=True, exist_ok=True)
            resolved.progress_file.write_text(json.dumps({"Status": "Processing"}), encoding="utf-8")
            resolved.pause_flag.write_text("pause", encoding="utf-8")

            removed = clear_runtime_artifacts_for_service(
                service,
                resolved,
                include_pipeline=True,
                include_audit=False,
            )

        self.assertIn("pipeline progress", removed)
        self.assertIn("pause flag", removed)

    def test_prepare_pipeline_runtime_clears_stale_progress_when_no_related_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyRuntimeRunnerService()
            resolved = _resolved(root)
            assert resolved.progress_file is not None
            assert resolved.pause_flag is not None
            resolved.progress_file.parent.mkdir(parents=True, exist_ok=True)
            resolved.pause_flag.parent.mkdir(parents=True, exist_ok=True)
            resolved.progress_file.write_text(json.dumps({"Status": "Processing"}), encoding="utf-8")
            resolved.pause_flag.write_text("pause", encoding="utf-8")

            messages = prepare_pipeline_runtime_for_service(service, resolved, stale_after_seconds=1)

            self.assertFalse(resolved.progress_file.exists())
            self.assertTrue(resolved.pause_flag.exists())
            self.assertEqual(len(messages), 1)
            self.assertIn("Cleared stale pipeline progress before launch", messages[0])

    def test_prepare_audit_runtime_preserves_progress_when_related_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = DummyRuntimeRunnerService()
            service.related_processes = [type("Proc", (), {"pid": 1234})()]
            resolved = _resolved(root)
            assert resolved.audit_reports_path is not None
            audit_progress = resolved.audit_reports_path / "audit_progress.json"
            audit_progress.parent.mkdir(parents=True, exist_ok=True)
            audit_progress.write_text(json.dumps({"status": "scanning"}), encoding="utf-8")

            messages = prepare_audit_runtime_for_service(service, resolved, stale_after_seconds=1)

            self.assertTrue(audit_progress.exists())
            self.assertEqual(len(messages), 1)
            self.assertIn("PID(s) 1234", messages[0])


if __name__ == "__main__":
    unittest.main()
