from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.services import DesktopAppService
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


def _get_json(url: str, token: str) -> tuple[int, dict]:
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _fake_health_run(args, **_kwargs):
    arg_text = " ".join(str(item) for item in args)
    if "ass_to_srt.py" in arg_text:
        return CapturedCommandResult(args=list(args), returncode=2, stdout="", stderr="")
    if "-encoders" in arg_text:
        return CapturedCommandResult(args=list(args), returncode=0, stdout=" V..... hevc_nvenc\n", stderr="")
    return CapturedCommandResult(args=list(args), returncode=0, stdout="probe ok", stderr="")


class MaintenanceHealthExpansionLocalApiTests(unittest.TestCase):
    def test_local_api_maintenance_returns_expanded_backend_health_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "DesktopApp"
            for rel in (
                "Pipeline/Tools/ffmpeg/bin/ffmpeg.exe",
                "Pipeline/Tools/ffmpeg/bin/ffprobe.exe",
                "Pipeline/Tools/MKVToolNix/mkvmerge.exe",
                "Pipeline/Tools/MKVToolNix/mkvextract.exe",
                "Pipeline/Tools/PgsToSrt/PgsToSrt.exe",
                "Pipeline/Tools/PgsToSrt/tessdata/eng.traineddata",
                "Pipeline/Tools/SubtitleEditLegacy/SubtitleEdit.exe",
                "Pipeline/Tools/SubtitleEditLegacy/Tesseract302/tesseract.exe",
                "Pipeline/Tools/SubtitleEditLegacy/Tesseract302/tessdata/eng.traineddata",
                "Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe",
                "Pipeline/ass_to_srt.py",
                "scripts/dev/start-local-api.bat",
                "scripts/dev/start-tauri-preview.bat",
                "scripts/dev/start-api-and-browser.bat",
                "scripts/dev/run.bat",
                "scripts/verify-env.bat",
                "scripts/verify-env.ps1",
                "DesktopApp/Runtime/Python/python.exe",
                "DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html",
            ):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            for directory in (
                app_root,
                root / "Movies",
                root / "TV",
                root / "Outsource",
                root / "LocalBase" / "State" / "ActiveJobs",
                root / "LibraryOut",
            ):
                directory.mkdir(parents=True, exist_ok=True)
            config_path = root / "Pipeline" / "MediaPipeline_config.psd1"
            config_path.write_text("@{}\n", encoding="utf-8")
            config = {
                "SourceMovies": str(root / "Movies"),
                "SourceTV": str(root / "TV"),
                "Outsource": str(root / "Outsource"),
                "LocalBase": str(root / "LocalBase"),
                "VideoCodec": "hevc_nvenc",
                "ConvertBdpgsToSrt": True,
                "ConvertVobSubToSrt": True,
                "BdpgsExtractLanguages": ["eng"],
                "VobSubExtractLanguages": ["eng"],
                "LibraryProfiles": [
                    {
                        "id": "custom",
                        "name": "Custom",
                        "enabled": True,
                        "source_path": str(root / "Movies"),
                        "output_path": str(root / "LibraryOut"),
                    }
                ],
            }
            resolved = ResolvedPaths(
                app_root=app_root,
                workspace_root=root,
                pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
                config_path=config_path,
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host=str(root / "Pipeline" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"),
                local_base=root / "LocalBase",
                state_root=root / "LocalBase" / "State",
                active_jobs_path=root / "LocalBase" / "State" / "ActiveJobs",
                config_data=config,
            )
            service = DesktopAppService(app_root)
            service._nvidia_smi_checked = True
            service._nvidia_smi_path = None
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            with patch("app.telemetry.service.run_capture", _fake_health_run):
                try:
                    server.start()
                    status, payload = _get_json(f"{server.url}/api/maintenance", "test-token")
                    progress_status, progress = _get_json(f"{server.url}/api/maintenance/progress", "test-token")
                finally:
                    server.stop()

            for handler in list(service.logger.handlers):
                base_filename = getattr(handler, "baseFilename", "")
                if base_filename and str(base_filename).startswith(str(app_root)):
                    service.logger.removeHandler(handler)
                    handler.close()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_maintenance_workspace.v1")
        row_names = {row["name"] for row in payload["rows"]}
        for expected in (
            "Config schema",
            "Configured root: SourceMovies",
            "Library output root: Custom",
            "Runtime state files",
            "API contract",
            "Process guard",
            "Bundle layout",
        ):
            self.assertIn(expected, row_names)
        self.assertEqual(progress_status, 200)
        step_ids = {step["id"] for step in progress["steps"]}
        self.assertIn("api_contract", step_ids)
        self.assertIn("process_guard", step_ids)
        self.assertIn("bundle_layout", step_ids)


if __name__ == "__main__":
    unittest.main()
