from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.paths.host import (
    resolve_powershell_host_for_service,
    subprocess_kwargs_hidden,
)


class ServicePathHostRunnerTests(unittest.TestCase):
    def test_resolve_powershell_host_prefers_workspace_bundled_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundled = root / "Pipeline" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
            bundled.parent.mkdir(parents=True)
            bundled.write_text("", encoding="utf-8")
            service = SimpleNamespace(workspace_root=root, app_root=root / "DesktopApp")

            host = resolve_powershell_host_for_service(service, which_func=lambda _name: None)

        self.assertEqual(host, str(bundled))

    def test_resolve_powershell_host_uses_injected_pwsh_lookup_only(self) -> None:
        service = SimpleNamespace(workspace_root=Path("missing-workspace"), app_root=Path("missing-app"))
        calls: list[str] = []

        def fake_which(name: str) -> str | None:
            calls.append(name)
            return "C:/Tools/pwsh.exe" if name == "pwsh" else None

        host = resolve_powershell_host_for_service(service, which_func=fake_which)

        self.assertEqual(host, "C:/Tools/pwsh.exe")
        self.assertEqual(calls, ["pwsh.exe", "pwsh"])

    def test_subprocess_kwargs_hidden_returns_empty_on_non_windows(self) -> None:
        with patch("app.paths.host.os.name", "posix"):
            self.assertEqual(subprocess_kwargs_hidden(), {})


if __name__ == "__main__":
    unittest.main()
