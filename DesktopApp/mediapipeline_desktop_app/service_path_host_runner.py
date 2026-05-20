from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import Any

from .service_runner_protocols import PowerShellHostServiceProtocol


def resolve_powershell_host_for_service(
    service: PowerShellHostServiceProtocol,
    *,
    which_func: Callable[[str], str | None],
) -> str | None:
    for candidate in (
        service.workspace_root / "Pipeline" / "PowerShell-7.6.0-win-x64" / "pwsh.exe",
        service.app_root / "Pipeline" / "PowerShell-7.6.0-win-x64" / "pwsh.exe",
        service.workspace_root / "PowerShell-7.6.0-win-x64" / "pwsh.exe",
        service.app_root / "PowerShell-7.6.0-win-x64" / "pwsh.exe",
    ):
        if candidate.exists():
            return str(candidate)
    for name in ("pwsh.exe", "pwsh"):
        candidate = which_func(name)
        if candidate:
            return candidate
    return None


def subprocess_kwargs_hidden() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if creationflags:
            kwargs["creationflags"] = creationflags
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startupinfo
    return kwargs
