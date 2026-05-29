from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Iterable

HealthRow = tuple[str, bool, str]

TOOL_HEALTH_DEFINITIONS = (
    (
        "ffmpeg",
        "ffmpeg.exe",
        "ffmpeg",
        (
            "Pipeline/Tools/ffmpeg/bin/ffmpeg.exe",
            "Pipeline/Tools/ffmpeg/bin/ffmpeg",
        ),
    ),
    (
        "ffprobe",
        "ffprobe.exe",
        "ffprobe",
        (
            "Pipeline/Tools/ffmpeg/bin/ffprobe.exe",
            "Pipeline/Tools/ffmpeg/bin/ffprobe",
        ),
    ),
    (
        "mkvmerge",
        "mkvmerge.exe",
        "mkvmerge",
        (
            "Pipeline/Tools/MKVToolNix/mkvmerge.exe",
            "Pipeline/Tools/MKVToolNix/mkvmerge",
        ),
    ),
)


def powershell_health_row(pwsh: str | None) -> HealthRow:
    if pwsh:
        return ("PowerShell (pwsh)", True, pwsh)
    return ("PowerShell (pwsh)", False, "Not found in bundled path or system PATH")


def find_bundled_or_system_tool(
    workspace_root: Path,
    app_root: Path,
    win_name: str,
    unix_name: str,
    rel_paths: Iterable[str],
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> str | None:
    for rel in rel_paths:
        for base in (workspace_root, app_root):
            candidate = base / rel
            if candidate.exists():
                return str(candidate)
    return which(win_name) or which(unix_name)


def bundled_tool_health_rows(
    workspace_root: Path,
    app_root: Path,
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> list[HealthRow]:
    results: list[HealthRow] = []
    for tool_name, win_name, unix_name, rel_paths in TOOL_HEALTH_DEFINITIONS:
        found = find_bundled_or_system_tool(
            workspace_root,
            app_root,
            win_name,
            unix_name,
            rel_paths,
            which=which,
        )
        if found:
            results.append((tool_name, True, found))
        else:
            results.append((tool_name, False, "Not found in bundled Tools or system PATH"))
    return results


def nvidia_smi_health_row(nvidia_smi: str | None) -> HealthRow:
    if nvidia_smi:
        return ("nvidia-smi (optional)", True, nvidia_smi)
    return ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable")


def find_ass_to_srt_script(workspace_root: Path, app_root: Path) -> Path | None:
    for name in ("ass_to_srt_chatgpt.py", "ass_to_srt.py"):
        for base in (workspace_root, app_root):
            candidate = base / "Pipeline" / name
            if candidate.exists():
                return candidate
    return None


def ass_to_srt_missing_row() -> HealthRow:
    return ("ass_to_srt (subtitle converter)", False, "Script not found in Pipeline/")


def ass_to_srt_result_row(script_path: Path, returncode: int, stderr: str) -> HealthRow:
    # Exit 2 = script loaded OK (arg-count guard), anything else = broken imports.
    if int(returncode) == 2:
        return ("ass_to_srt (subtitle converter)", True, str(script_path))
    text = str(stderr or "").strip()
    snippet = text.split("\n")[0][:120] if text else f"exit {returncode}"
    return ("ass_to_srt (subtitle converter)", False, snippet)


def ass_to_srt_exception_row(exc: Exception) -> HealthRow:
    return ("ass_to_srt (subtitle converter)", False, str(exc))
