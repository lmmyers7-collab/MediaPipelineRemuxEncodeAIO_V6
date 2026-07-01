from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


class ArchitectureBoundaryCompatibilityImportTests(unittest.TestCase):
    def test_command_result_legacy_imports_resolve_to_kernel_home(self) -> None:
        from mediapipeline.core.kernel.dto_commands import CommandResult as KernelCommandResult
        from mediapipeline.desktop.application import CommandResult as ApplicationCommandResult
        from mediapipeline.desktop.application.dto import CommandResult as DtoCommandResult
        from mediapipeline.desktop.application.dto_commands import CommandResult as DtoCommandsCommandResult

        self.assertIs(ApplicationCommandResult, KernelCommandResult)
        self.assertIs(DtoCommandResult, KernelCommandResult)
        self.assertIs(DtoCommandsCommandResult, KernelCommandResult)

    def test_dto_base_legacy_imports_resolve_to_kernel_home(self) -> None:
        from mediapipeline.core.kernel.dto_base import JsonMap, dto_mapping, json_safe, split_summary_lines
        from mediapipeline.desktop.application.dto_base import JsonMap as LegacyJsonMap
        from mediapipeline.desktop.application.dto_base import dto_mapping as legacy_dto_mapping
        from mediapipeline.desktop.application.dto_base import json_safe as legacy_json_safe
        from mediapipeline.desktop.application.dto_base import split_summary_lines as legacy_split_summary_lines

        self.assertIs(LegacyJsonMap, JsonMap)
        self.assertIs(legacy_dto_mapping, dto_mapping)
        self.assertIs(legacy_json_safe, json_safe)
        self.assertIs(legacy_split_summary_lines, split_summary_lines)

    def test_subprocess_runner_legacy_imports_resolve_to_kernel_home(self) -> None:
        from mediapipeline.core.kernel.runtime.subprocess_runner import CapturedCommandResult, KillTreeCallback, run_capture
        from mediapipeline.desktop.subprocess_runner import CapturedCommandResult as LegacyCapturedCommandResult
        from mediapipeline.desktop.subprocess_runner import KillTreeCallback as LegacyKillTreeCallback
        from mediapipeline.desktop.subprocess_runner import run_capture as legacy_run_capture

        self.assertIs(LegacyCapturedCommandResult, CapturedCommandResult)
        self.assertIs(LegacyKillTreeCallback, KillTreeCallback)
        self.assertIs(legacy_run_capture, run_capture)

    def test_models_core_legacy_imports_resolve_to_kernel_home(self) -> None:
        from mediapipeline.core.kernel.models_core import ConfigSaveResult, ResolvedPaths
        from mediapipeline.desktop.models_core import ConfigSaveResult as LegacyConfigSaveResult
        from mediapipeline.desktop.models_core import ResolvedPaths as LegacyResolvedPaths

        self.assertIs(LegacyConfigSaveResult, ConfigSaveResult)
        self.assertIs(LegacyResolvedPaths, ResolvedPaths)


if __name__ == "__main__":
    unittest.main()
