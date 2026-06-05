from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from mediapipeline.core.maintenance.release_plan import (
    build_release_command_args,
    default_release_destination,
    release_artifact_paths,
    release_command_line,
    resolve_release_destination,
)


class ReleasePlanTests(unittest.TestCase):
    def test_default_release_destination_uses_workspace_name_and_timestamp(self) -> None:
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "MediaPipelineRemuxEncodeAIO_previous"
            (workspace / "ops" / "release" / "metadata").mkdir(parents=True)
            (workspace / "ops" / "release" / "metadata" / "VERSION").write_text("2026.06.04.001\n", encoding="utf-8")

            destination = default_release_destination(workspace, now=datetime(2026, 5, 8, 1, 2, 3))

        self.assertEqual(destination.name, "MediaPipelineRemuxEncodeAIO_2026.06.04.001_Portable_20260508_010203")

    def test_resolve_release_destination_prefers_explicit_destination(self) -> None:
        workspace = Path(r"C:\bundle\MediaPipelineRemuxEncodeAIO_previous")
        self.assertEqual(resolve_release_destination(workspace, r"D:\release out"), Path(r"D:\release out"))

    def test_build_release_command_args_preserves_switch_order(self) -> None:
        args = build_release_command_args(
            powershell_host=r"C:\pwsh\pwsh.exe",
            builder=Path(r"C:\bundle\Build.ps1"),
            destination=Path(r"D:\release out"),
            zip_package=True,
            verify=True,
            include_tests=True,
            include_dev_docs=True,
            include_optional_tools=True,
            include_tool_docs=True,
            keep_personal_config=True,
            force=True,
            dry_run=True,
        )
        self.assertEqual(
            args,
            [
                r"C:\pwsh\pwsh.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(Path(r"C:\bundle\Build.ps1")),
                "-DestinationRoot",
                str(Path(r"D:\release out")),
                "-Force",
                "-Zip",
                "-Verify",
                "-IncludeTests",
                "-IncludeDevDocs",
                "-IncludeOptionalTools",
                "-IncludeToolDocs",
                "-KeepPersonalConfig",
                "-DryRun",
            ],
        )

    def test_release_command_line_and_artifact_paths_are_predictable(self) -> None:
        command_line = release_command_line(["pwsh", "-File", r"D:\release out\Build.ps1"])
        self.assertIn("pwsh", command_line)
        self.assertIn("-File", command_line)
        manifest_path, zip_path = release_artifact_paths(Path(r"D:\release out"))
        self.assertEqual(manifest_path, Path(r"D:\release out\release_manifest.json"))
        self.assertEqual(zip_path, Path(r"D:\release out.zip"))


if __name__ == "__main__":
    unittest.main()
