from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.paths.service import PathResolutionServiceMixin
from mediapipeline.core.processes.runtime_artifacts import (
    clear_runtime_artifact_specs,
    filter_runtime_artifact_specs,
    runtime_artifact_specs,
    validate_runtime_artifact_target,
)
from mediapipeline.core.processes.lifecycle import ProcessLifecycleServiceMixin


def _normalized_path_key(path: Path) -> str:
    return str(path.resolve(strict=False)).casefold()


def _state_root_for_local_base(local_base: Path) -> Path:
    return local_base / "State"


class DummyRuntimeArtifactService(PathResolutionServiceMixin, ProcessLifecycleServiceMixin):
    def __init__(self, root: Path) -> None:
        self.app_root = root
        self.workspace_root = root
        self.logger = logging.getLogger("test_service_process_runtime_artifacts")
        self.logger.addHandler(logging.NullHandler())


class ProcessRuntimeArtifactHelperTests(unittest.TestCase):
    def _resolved(self, root: Path) -> ResolvedPaths:
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

    def _specs(self, resolved: ResolvedPaths, *, include_pipeline: bool = True, include_audit: bool = True):
        return runtime_artifact_specs(
            resolved,
            include_pipeline=include_pipeline,
            include_audit=include_audit,
            state_root_for_local_base=_state_root_for_local_base,
            normalized_path_key=_normalized_path_key,
        )

    def test_runtime_specs_include_state_and_legacy_paths_once(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            resolved = self._resolved(Path(td))

            specs = self._specs(resolved)
            labels = [label for label, _path, _expected in specs]

        self.assertIn("pipeline progress", labels)
        self.assertIn("legacy pipeline progress", labels)
        self.assertIn("pause flag", labels)
        self.assertIn("legacy pause flag", labels)
        self.assertIn("audit progress", labels)
        self.assertEqual(len(specs), len({str(path).casefold() for _label, path, _expected in specs if path is not None}))

    def test_clear_runtime_specs_removes_only_valid_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            assert resolved.progress_file is not None
            assert resolved.pause_flag is not None
            resolved.progress_file.parent.mkdir(parents=True, exist_ok=True)
            resolved.pause_flag.parent.mkdir(parents=True, exist_ok=True)
            resolved.progress_file.write_text("{}", encoding="utf-8")
            resolved.pause_flag.write_text("pause", encoding="utf-8")
            specs = filter_runtime_artifact_specs(self._specs(resolved, include_audit=False), labels={"pipeline progress"})

            removed = clear_runtime_artifact_specs(specs, normalized_path_key=_normalized_path_key)

            self.assertEqual(removed, ["pipeline progress"])
            self.assertFalse(resolved.progress_file.exists())
            self.assertTrue(resolved.pause_flag.exists())

    def test_validate_runtime_target_rejects_wrong_name_and_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = [root / "State" / "Progress" / "pipeline_progress.json"]

            with self.assertRaisesRegex(RuntimeError, "unexpected filename"):
                validate_runtime_artifact_target(
                    "pipeline progress",
                    root / "State" / "Progress" / "not_pipeline_progress.json",
                    expected,
                    normalized_path_key=_normalized_path_key,
                )

            with self.assertRaisesRegex(RuntimeError, "outside expected runtime state paths"):
                validate_runtime_artifact_target(
                    "pipeline progress",
                    root / "Other" / "pipeline_progress.json",
                    expected,
                    normalized_path_key=_normalized_path_key,
                )

    def test_process_service_runtime_wrappers_match_helper_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            service = DummyRuntimeArtifactService(root)

            wrapper_specs = service._runtime_artifact_specs(resolved, include_pipeline=True, include_audit=True)
            helper_specs = self._specs(resolved)

        self.assertEqual(wrapper_specs, helper_specs)


if __name__ == "__main__":
    unittest.main()
