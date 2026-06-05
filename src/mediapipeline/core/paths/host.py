from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import Any

from mediapipeline.core.paths.contracts import PowerShellHostServiceProtocol


def resolve_powershell_host_for_service(
    service: PowerShellHostServiceProtocol,
    *,
    which_func: Callable[[str], str | None],
) -> str | None:
    for candidate in (
        service.workspace_root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe",
        service.app_root / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe",
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
