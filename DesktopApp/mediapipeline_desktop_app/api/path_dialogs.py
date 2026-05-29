from __future__ import annotations

import base64
import json
import locale
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _decode_process_output(value: bytes) -> str:
    encodings = ["utf-8-sig", "utf-16", locale.getpreferredencoding(False)]
    if sys.platform == "win32":
        encodings.append("mbcs")
    for encoding in encodings:
        try:
            return value.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return value.decode("utf-8", errors="replace")


def _powershell_dialog_script(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-DialogResult($Payload) {{
  $Payload | ConvertTo-Json -Depth 5 -Compress
}}

try {{
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.Application]::EnableVisualStyles()
  $payload = @'
{payload_json}
'@ | ConvertFrom-Json
  $selectionMode = [string]$payload.selection_mode
  if ($selectionMode -ne 'folder') {{ $selectionMode = 'files' }}
  $initialPath = [string]$payload.initial_path
  $folderDescription = [string]$payload.dialog_description
  if (-not $folderDescription) {{ $folderDescription = 'Select a folder to add to Rename source paths' }}
  $fileTitle = [string]$payload.dialog_title
  if (-not $fileTitle) {{ $fileTitle = 'Select media files to add to Rename source paths' }}
  $fileFilter = [string]$payload.file_filter
  if (-not $fileFilter) {{ $fileFilter = 'Media files (*.mkv;*.mp4;*.m4v;*.avi;*.mov;*.wmv)|*.mkv;*.mp4;*.m4v;*.avi;*.mov;*.wmv|All files (*.*)|*.*' }}
  $initialDirectory = ''
  if ($initialPath -and [System.IO.File]::Exists($initialPath)) {{
    $initialDirectory = [System.IO.Path]::GetDirectoryName($initialPath)
  }} elseif ($initialPath -and [System.IO.Directory]::Exists($initialPath)) {{
    $initialDirectory = $initialPath
  }}

  if ($selectionMode -eq 'folder') {{
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = $folderDescription
    $dialog.ShowNewFolderButton = $false
    if ($initialDirectory) {{ $dialog.SelectedPath = $initialDirectory }}
    $dialogResult = $dialog.ShowDialog()
    if ($dialogResult -eq [System.Windows.Forms.DialogResult]::OK -and $dialog.SelectedPath) {{
      Write-DialogResult ([ordered]@{{
        ok = $true
        canceled = $false
        selection_mode = $selectionMode
        paths = @([string]$dialog.SelectedPath)
        message = 'Selected 1 folder.'
        errors = @()
      }})
    }} else {{
      Write-DialogResult ([ordered]@{{
        ok = $true
        canceled = $true
        selection_mode = $selectionMode
        paths = @()
        message = 'Folder selection canceled.'
        errors = @()
      }})
    }}
  }} else {{
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = $fileTitle
    $dialog.Filter = $fileFilter
    $dialog.Multiselect = $true
    $dialog.CheckFileExists = $true
    $dialog.RestoreDirectory = $true
    if ($initialDirectory) {{ $dialog.InitialDirectory = $initialDirectory }}
    $dialogResult = $dialog.ShowDialog()
    if ($dialogResult -eq [System.Windows.Forms.DialogResult]::OK) {{
      $selectedPaths = @($dialog.FileNames | ForEach-Object {{ [string]$_ }})
      Write-DialogResult ([ordered]@{{
        ok = $true
        canceled = $false
        selection_mode = $selectionMode
        paths = $selectedPaths
        message = ('Selected ' + $selectedPaths.Count + ' file(s).')
        errors = @()
      }})
    }} else {{
      Write-DialogResult ([ordered]@{{
        ok = $true
        canceled = $true
        selection_mode = $selectionMode
        paths = @()
        message = 'File selection canceled.'
        errors = @()
      }})
    }}
  }}
}} catch {{
  Write-DialogResult ([ordered]@{{
    ok = $false
    canceled = $false
    selection_mode = 'files'
    paths = @()
    message = ('Windows file browser failed: ' + $_.Exception.Message)
    errors = @([string]$_.Exception.Message)
  }})
}}
"""


def _dedupe_existing_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_path in paths:
        path = str(raw_path or "").strip()
        if not path:
            continue
        key = path.casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            if not Path(path).exists():
                continue
        except OSError:
            continue
        result.append(path)
    return result


def _windows_powershell_candidates() -> list[str]:
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    candidates = [
        str(Path(system_root) / "Sysnative" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        str(Path(system_root) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
    ]
    path_powershell = shutil.which("powershell.exe")
    if path_powershell:
        candidates.append(path_powershell)
    path_pwsh = shutil.which("pwsh.exe")
    if path_pwsh:
        candidates.append(path_pwsh)
    return _dedupe_existing_paths(candidates)


def _select_windows_dialog_host() -> str | None:
    candidates = _windows_powershell_candidates()
    return candidates[0] if candidates else None


def select_windows_paths_with_dialog(
    *,
    selection_mode: str = "files",
    initial_path: str = "",
    dialog_title: str = "",
    dialog_description: str = "",
    file_filter: str = "",
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    mode = "folder" if str(selection_mode or "").strip().lower() == "folder" else "files"
    if sys.platform != "win32":
        return {
            "ok": False,
            "canceled": False,
            "selection_mode": mode,
            "paths": [],
            "message": "Native Windows file browser is only available on Windows.",
            "errors": ["unsupported_platform"],
        }

    powershell = _select_windows_dialog_host()
    if not powershell:
        return {
            "ok": False,
            "canceled": False,
            "selection_mode": mode,
            "paths": [],
            "message": "Could not find Windows PowerShell to open the Windows file browser.",
            "errors": ["powershell_not_found"],
        }

    script = _powershell_dialog_script(
        {
            "selection_mode": mode,
            "initial_path": str(initial_path or ""),
            "dialog_title": str(dialog_title or ""),
            "dialog_description": str(dialog_description or ""),
            "file_filter": str(file_filter or ""),
        }
    )
    encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    command = [
        powershell,
        "-NoProfile",
        "-STA",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encoded_script,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=max(30, int(timeout_seconds)),
            creationflags=creationflags,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "canceled": False,
            "selection_mode": mode,
            "paths": [],
            "message": "Windows file browser timed out before a selection was made.",
            "errors": ["dialog_timeout"],
        }

    stdout = _decode_process_output(completed.stdout).strip()
    stderr = _decode_process_output(completed.stderr).strip()
    if completed.returncode != 0:
        detail = stderr or stdout or "dialog_process_failed"
        return {
            "ok": False,
            "canceled": False,
            "selection_mode": mode,
            "paths": [],
            "message": f"Windows file browser process exited with code {completed.returncode} using {Path(powershell).name}.",
            "errors": [detail],
        }
    if not stdout:
        return {
            "ok": False,
            "canceled": False,
            "selection_mode": mode,
            "paths": [],
            "message": "Windows file browser returned no selection payload.",
            "errors": [stderr or "empty_dialog_payload"],
        }
    try:
        result = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "canceled": False,
            "selection_mode": mode,
            "paths": [],
            "message": f"Windows file browser returned invalid JSON: {exc}",
            "errors": [stdout[:1000]],
        }
    paths = [str(path).strip() for path in result.get("paths", []) if str(path).strip()]
    return {
        "ok": bool(result.get("ok", False)),
        "canceled": bool(result.get("canceled", False)),
        "selection_mode": str(result.get("selection_mode") or mode),
        "paths": paths,
        "message": str(result.get("message") or ""),
        "errors": [str(error) for error in result.get("errors", [])],
    }


__all__ = ["select_windows_paths_with_dialog"]
