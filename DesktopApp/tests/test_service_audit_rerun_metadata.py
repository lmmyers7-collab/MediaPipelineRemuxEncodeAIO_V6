from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.audit.rerun_metadata import (
    deduplicate_source_paths,
    load_rerun_source_metadata_for_service,
    rerun_source_metadata_script_path_for_service,
)


class DummyLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, *args: object) -> None:
        self.warnings.append(message % args)


class DummyMetadataService:
    def __init__(self, app_root: Path, workspace_root: Path) -> None:
        self.app_root = app_root
        self.workspace_root = workspace_root
        self.logger = DummyLogger()
        self.hidden_kwargs_called = False
        self.environment_called = False

    def _first_existing(self, *paths: Path) -> Path:
        for path in paths:
            if path.exists():
                return path
        return paths[0]

    def _rerun_source_metadata_script_path(self, resolved: ResolvedPaths) -> Path:
        return rerun_source_metadata_script_path_for_service(self, resolved)

    def _build_launch_environment(self) -> dict[str, str]:
        self.environment_called = True
        return {"TEST_ENV": "1"}

    def _subprocess_kwargs_hidden(self) -> dict[str, Any]:
        self.hidden_kwargs_called = True
        return {"hidden": True}


class ServiceAuditRerunMetadataTests(unittest.TestCase):
    def test_deduplicate_source_paths_preserves_first_case_insensitive_occurrence(self) -> None:
        paths = [Path("C:/Media/Movie.mkv"), Path("c:/media/movie.mkv"), Path("D:/Other.mkv")]

        self.assertEqual(deduplicate_source_paths(paths), [paths[0], paths[2]])

    def test_rerun_source_metadata_script_path_prefers_rerun_script_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            script = workspace_root / "Pipeline" / "Get-RerunSourceMetadata.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("", encoding="utf-8")
            service = DummyMetadataService(app_root, workspace_root)
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=workspace_root,
                pipeline_path=workspace_root / "Pipeline.ps1",
                config_path=workspace_root / "Config.psd1",
                audit_script_path=workspace_root / "Audit.ps1",
                rerun_script_path=workspace_root / "Pipeline" / "Invoke-RerunCsv.ps1",
                powershell_host="pwsh",
            )

            self.assertEqual(rerun_source_metadata_script_path_for_service(service, resolved), script)

    def test_load_rerun_source_metadata_invokes_helper_and_indexes_rows_by_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            script = workspace_root / "Pipeline" / "Get-RerunSourceMetadata.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("", encoding="utf-8")
            service = DummyMetadataService(app_root, workspace_root)
            first = root / "Movie.mkv"
            duplicate = Path(str(first).swapcase())
            second = root / "Other.mkv"
            calls: list[dict[str, Any]] = []
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=workspace_root,
                pipeline_path=workspace_root / "Pipeline.ps1",
                config_path=workspace_root / "Config.psd1",
                audit_script_path=workspace_root / "Audit.ps1",
                rerun_script_path=workspace_root / "Pipeline" / "Invoke-RerunCsv.ps1",
                powershell_host="pwsh",
            )

            def fake_run_capture(args: list[str], **kwargs: Any) -> Any:
                request_path = Path(args[args.index("-InputJsonPath") + 1])
                output_path = Path(args[args.index("-OutputJsonPath") + 1])
                request = json.loads(request_path.read_text(encoding="utf-8"))
                calls.append({"request": request, "kwargs": kwargs})
                output_path.write_text(
                    json.dumps(
                        {
                            "rows": [
                                {"source_path": str(first), "source_size": 100},
                                {"source_path": str(second), "source_size": 200},
                                {"source_path": "", "ignored": True},
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                return SimpleNamespace(timed_out=False, returncode=0, stdout="", stderr="", kill_message="")

            metadata = load_rerun_source_metadata_for_service(
                service,
                resolved,
                [first, duplicate, second],
                run_capture_func=fake_run_capture,
            )

            self.assertEqual(calls[0]["request"]["source_paths"], [str(first), str(second)])
            self.assertEqual(calls[0]["kwargs"]["label"], "rerun source metadata")
            self.assertEqual(calls[0]["kwargs"]["timeout_seconds"], 30.0)
            self.assertTrue(service.environment_called)
            self.assertTrue(service.hidden_kwargs_called)
            self.assertEqual(metadata[str(first).casefold()]["source_size"], 100)
            self.assertEqual(metadata[str(second).casefold()]["source_size"], 200)

    def test_load_rerun_source_metadata_warns_when_helper_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            service = DummyMetadataService(app_root, workspace_root)
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=workspace_root,
                pipeline_path=workspace_root / "Pipeline.ps1",
                config_path=workspace_root / "Config.psd1",
                audit_script_path=workspace_root / "Audit.ps1",
                rerun_script_path=workspace_root / "Pipeline" / "Invoke-RerunCsv.ps1",
                powershell_host=None,
            )

            metadata = load_rerun_source_metadata_for_service(service, resolved, [root / "Movie.mkv"])

            self.assertEqual(metadata, {})
            self.assertEqual(
                service.logger.warnings,
                ["Rerun source metadata helper unavailable; exported CSV will rely on source size/mtime only."],
            )

    def test_load_rerun_source_metadata_reports_timeout_and_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            script = workspace_root / "Pipeline" / "Get-RerunSourceMetadata.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("", encoding="utf-8")
            service = DummyMetadataService(app_root, workspace_root)
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=workspace_root,
                pipeline_path=workspace_root / "Pipeline.ps1",
                config_path=workspace_root / "Config.psd1",
                audit_script_path=workspace_root / "Audit.ps1",
                rerun_script_path=workspace_root / "Pipeline" / "Invoke-RerunCsv.ps1",
                powershell_host="pwsh",
            )

            timeout_metadata = load_rerun_source_metadata_for_service(
                service,
                resolved,
                [root / "Movie.mkv"],
                run_capture_func=lambda *_args, **_kwargs: SimpleNamespace(
                    timed_out=True,
                    returncode=None,
                    stdout="",
                    stderr="",
                    kill_message="killed",
                ),
            )
            failed_metadata = load_rerun_source_metadata_for_service(
                service,
                resolved,
                [root / "Movie.mkv"],
                run_capture_func=lambda *_args, **_kwargs: SimpleNamespace(
                    timed_out=False,
                    returncode=2,
                    stdout="",
                    stderr="bad\nlast line",
                    kill_message="",
                ),
            )

            self.assertEqual(timeout_metadata, {})
            self.assertEqual(failed_metadata, {})
            self.assertIn("Rerun source metadata helper timed out: killed", service.logger.warnings)
            self.assertIn("Rerun source metadata helper failed: last line", service.logger.warnings)

    def test_load_rerun_source_metadata_warns_when_subprocess_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            workspace_root = root
            script = workspace_root / "Pipeline" / "Get-RerunSourceMetadata.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("", encoding="utf-8")
            service = DummyMetadataService(app_root, workspace_root)
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=workspace_root,
                pipeline_path=workspace_root / "Pipeline.ps1",
                config_path=workspace_root / "Config.psd1",
                audit_script_path=workspace_root / "Audit.ps1",
                rerun_script_path=workspace_root / "Pipeline" / "Invoke-RerunCsv.ps1",
                powershell_host="pwsh",
            )

            def failing_run_capture(*_args: Any, **_kwargs: Any) -> Any:
                raise RuntimeError("spawn failed")

            metadata = load_rerun_source_metadata_for_service(
                service,
                resolved,
                [root / "Movie.mkv"],
                run_capture_func=failing_run_capture,
            )

            self.assertEqual(metadata, {})
            self.assertIn("Rerun source metadata helper failed: spawn failed", service.logger.warnings)


if __name__ == "__main__":
    unittest.main()
