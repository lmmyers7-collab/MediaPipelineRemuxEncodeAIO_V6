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
  # Prefer WPF for the folder dialog so we get the modern Windows
  # Explorer-style picker (Microsoft.Win32.OpenFolderDialog, .NET 8+).
  $wpfLoaded = $false
  try {{
    Add-Type -AssemblyName PresentationFramework
    $wpfLoaded = $true
  }} catch {{
    $wpfLoaded = $false
  }}
  $payload = @'
{payload_json}
'@ | ConvertFrom-Json
  $selectionMode = [string]$payload.selection_mode
  if ($selectionMode -notin @('folder', 'folder_files', 'files')) {{ $selectionMode = 'files' }}
  $initialPath = [string]$payload.initial_path
  $folderDescription = [string]$payload.dialog_description
  if (-not $folderDescription) {{ $folderDescription = 'Select a folder to add to Rename source paths' }}
  $fileTitle = [string]$payload.dialog_title
  if (-not $fileTitle) {{ $fileTitle = 'Select files to add to Rename source paths' }}
  $fileFilter = [string]$payload.file_filter
  if (-not $fileFilter) {{ $fileFilter = 'All files (*.*)|*.*' }}
  $initialDirectory = ''
  if ($initialPath -and [System.IO.File]::Exists($initialPath)) {{
    $initialDirectory = [System.IO.Path]::GetDirectoryName($initialPath)
  }} elseif ($initialPath -and [System.IO.Directory]::Exists($initialPath)) {{
    $initialDirectory = $initialPath
  }}

  function Invoke-FolderDialog([string]$Description, [string]$InitialDir, [bool]$WpfReady) {{
    # Try the modern WPF Microsoft.Win32.OpenFolderDialog first (Vista-style
    # Explorer picker). Fall back to the legacy FolderBrowserDialog only when
    # the WPF type is unavailable (older PowerShell hosts).
    if ($WpfReady) {{
      try {{
        $modernType = [Type]::GetType('Microsoft.Win32.OpenFolderDialog, PresentationFramework')
        if ($modernType) {{
          $dlg = [Activator]::CreateInstance($modernType)
          $dlg.Title = $Description
          if ($InitialDir) {{ $dlg.InitialDirectory = $InitialDir }}
          $result = $dlg.ShowDialog()
          if ($result -and $dlg.FolderName) {{
            return @{{ ok = $true; canceled = $false; path = [string]$dlg.FolderName }}
          }}
          return @{{ ok = $true; canceled = $true; path = '' }}
        }}
      }} catch {{
        # fall through to legacy dialog
      }}
    }}
    $legacy = New-Object System.Windows.Forms.FolderBrowserDialog
    $legacy.Description = $Description
    $legacy.ShowNewFolderButton = $false
    if ($InitialDir) {{ $legacy.SelectedPath = $InitialDir }}
    $legacyResult = $legacy.ShowDialog()
    if ($legacyResult -eq [System.Windows.Forms.DialogResult]::OK -and $legacy.SelectedPath) {{
      return @{{ ok = $true; canceled = $false; path = [string]$legacy.SelectedPath }}
    }}
    return @{{ ok = $true; canceled = $true; path = '' }}
  }}

  if ($selectionMode -eq 'folder' -or $selectionMode -eq 'folder_files') {{
    $folderPick = Invoke-FolderDialog $folderDescription $initialDirectory $wpfLoaded
    if ($folderPick.canceled -or -not $folderPick.path) {{
      Write-DialogResult ([ordered]@{{
        ok = $true
        canceled = $true
        selection_mode = $selectionMode
        paths = @()
        message = 'Folder selection canceled.'
        errors = @()
      }})
    }} elseif ($selectionMode -eq 'folder_files') {{
      # Return only files directly inside the folder. No recursion.
      $children = @()
      try {{
        $children = @(Get-ChildItem -LiteralPath $folderPick.path -File -Force -ErrorAction SilentlyContinue |
                      Sort-Object Name | ForEach-Object {{ [string]$_.FullName }})
      }} catch {{ $children = @() }}
      $count = $children.Count
      Write-DialogResult ([ordered]@{{
        ok = $true
        canceled = $false
        selection_mode = $selectionMode
        paths = $children
        message = ('Selected folder ' + $folderPick.path + ' with ' + $count + ' direct child file(s).')
        errors = @()
      }})
    }} else {{
      Write-DialogResult ([ordered]@{{
        ok = $true
        canceled = $false
        selection_mode = $selectionMode
        paths = @([string]$folderPick.path)
        message = 'Selected 1 folder.'
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


def _bundled_pwsh_candidates() -> list[str]:
    """Look for the bundled PowerShell 7 binary that ships in-repo.

    The repo ships `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe`. That binary
    is .NET 8-based and exposes `Microsoft.Win32.OpenFolderDialog` (the
    modern Windows Explorer-style folder picker). When present, it is the
    correct host for the dialog script, regardless of whether the operator
    machine has `pwsh.exe` installed system-wide.
    """
    # path_dialogs.py lives at DesktopApp/mediapipeline_desktop_app/api/path_dialogs.py
    repo_root = Path(__file__).resolve().parents[3]
    candidates: list[str] = []
    for pattern in (
        "Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe",
        "Pipeline/PowerShell-*/pwsh.exe",
    ):
        for match in repo_root.glob(pattern):
            candidates.append(str(match))
    return candidates


def _windows_powershell_candidates() -> list[str]:
    """Return candidate PowerShell hosts in preference order.

    PowerShell 7+ (`pwsh.exe`) is preferred over Windows PowerShell 5.1
    (`powershell.exe`) because the dialog script needs `.NET 8`'s
    `Microsoft.Win32.OpenFolderDialog` to render the modern Explorer-style
    folder picker. Windows PowerShell 5.1 only ships .NET Framework 4.x,
    which lacks `OpenFolderDialog` and falls back to the legacy tree
    dialog. The bundled `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe` is
    tried first so the operator's machine does not need pwsh installed
    system-wide.

    Older Windows PowerShell paths are still listed last so an
    operator machine without pwsh.exe at all still gets a working
    (legacy) dialog rather than a hard failure.
    """
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    candidates: list[str] = []
    # 1. Repo-bundled pwsh 7.x first.
    candidates.extend(_bundled_pwsh_candidates())
    # 2. Any system pwsh.exe on PATH.
    path_pwsh = shutil.which("pwsh.exe")
    if path_pwsh:
        candidates.append(path_pwsh)
    # 3. Well-known install locations for system pwsh.
    program_files = os.environ.get("ProgramFiles") or r"C:\Program Files"
    program_files_x86 = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    for base in (program_files, program_files_x86):
        for version in ("7", "8"):
            candidates.append(str(Path(base) / "PowerShell" / version / "pwsh.exe"))
    # 4. Windows PowerShell 5.1 as legacy fallback (lacks the modern picker but
    #    keeps file selection working on bare machines without pwsh).
    candidates.extend([
        str(Path(system_root) / "Sysnative" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
        str(Path(system_root) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
    ])
    path_powershell = shutil.which("powershell.exe")
    if path_powershell:
        candidates.append(path_powershell)
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
    raw_mode = str(selection_mode or "").strip().lower()
    if raw_mode in ("folder", "folder_files"):
        mode = raw_mode
    else:
        mode = "files"
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
