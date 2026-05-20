from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_paths import PathResolutionServiceMixin


class DummyPathService(PathResolutionServiceMixin):
    def __init__(self, app_root: Path) -> None:
        self.app_root = app_root
        self.workspace_root = app_root.parent


class PathResolutionServiceTests(unittest.TestCase):
    def test_resolve_powershell_host_prefers_bundled_pwsh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "DesktopApp"
            bundled = root / "Pipeline" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
            bundled.parent.mkdir(parents=True)
            bundled.write_text("", encoding="utf-8")
            service = DummyPathService(app_root)

            with patch("mediapipeline_desktop_app.service_paths.shutil.which", return_value=None):
                self.assertEqual(service.resolve_powershell_host(), str(bundled))

    def test_resolve_powershell_host_does_not_fall_back_to_windows_powershell(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_root = root / "DesktopApp"
            service = DummyPathService(app_root)

            def fake_which(name: str) -> str | None:
                if name == "powershell.exe":
                    return r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
                return None

            with patch("mediapipeline_desktop_app.service_paths.shutil.which", fake_which):
                self.assertIsNone(service.resolve_powershell_host())


if __name__ == "__main__":
    unittest.main()
