# PowerShell Host Expectations

Purpose: document which PowerShell runtime every entry point expects, how each resolves the correct host, what happens when the bundled runtime is absent, and what patterns are prohibited. This is a reference document for operators and contributors who run scripts or add new entry points.

---

## Host Requirement

**PowerShell 7 is required for all scripted operations.** Windows PowerShell 5.1 (the inbox `powershell.exe`) is not a supported host for pipeline, test, or build scripts. Scripts that detect they are running under PS5 re-invoke themselves under `pwsh` rather than failing silently — see the Re-Invocation Pattern section below.

The minimum tested version is **PowerShell 7.6.0**, which is the version bundled with the package.

---

## Bundled Runtime

The package includes a complete, portable PowerShell 7.6.0 distribution:

```
Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe
```

This directory is the **preferred runtime** for all scripted operations. The bundled runtime:
- Is resolved first by every runtime-resolver function in the codebase
- Is prepended to `PATH` by the Python service layer before subprocesses are launched
- Ensures a known PowerShell version regardless of the operator's system PATH

---

## Resolution Order (All Entry Points)

Every script that needs `pwsh` follows the same resolution order:

1. Check `Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe` relative to the bundle root
2. If bundled is absent, call `Get-Command pwsh` (or `Get-Command pwsh.exe`) against system PATH
3. If neither is found, throw with an explicit message that PowerShell 7 is required

This pattern is implemented in:
- `scripts\release\build.ps1` (`Resolve-ReleasePowerShell`)
- `scripts\release\test.ps1` (`Resolve-ReleasePowerShell`)
- `scripts\verify-env.ps1` (`Resolve-CommandPath` with `-RelativePreferred`)
- `Pipeline\Setup-MediaPipeline_chatgpt.ps1` (`Resolve-PwshPath`)
- `scripts\dev\start-tauri-preview.bat` (inline check before script invocation)

---

## Entry Point Inventory

### Batch Wrappers (`.bat`)

| Entry point | Shell chain | PowerShell used |
|---|---|---|
| `scripts\dev\start-tauri-preview.bat` | `.bat` → `pwsh.exe -File ...` | Bundled `Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe` (system fallback if absent) |
| `scripts\dev\start-local-api.bat` | `.bat` → `DesktopApp\Launch-*.bat` → Python | No PowerShell in this chain |

### Root PowerShell Wrappers (`.ps1`)

These wrappers are invoked by the operator from a terminal. They invoke Python (not PowerShell subprocesses) for test execution.

| Wrapper | Shell | What it invokes |
|---|---|---|
| `Test-WebView*.ps1` | Whatever the operator's `pwsh` is | `python -m unittest` via bundled Python |
| `scripts\release\test.ps1` | Requires `pwsh` 7 | Various Python checks and bundled `pwsh` for pipeline tests |
| `scripts\release\build.ps1` | Requires `pwsh` 7 | Builder and packager |

The operator wrapper scripts, including the `SmokeTests/` wrappers, do not check `$PSVersionTable` themselves; they are written in PS7 syntax and will fail at parse time on PS5 if PS5 is used. Run them with `pwsh` or the bundled runtime.

### Pipeline Test Scripts

| Script | Host requirement | Enforcement |
|---|---|---|
| `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` | PS7 | Checks `$PSVersionTable.PSVersion.Major -lt 7`, re-invokes under system `pwsh` if needed, and runs the active V6 WebView/backend reliability wrapper by default |
| `Pipeline\Tests\Invoke-ToolIntegrationChecks.ps1` | PS7 | Run by release self-test via bundled pwsh |
| `Pipeline\Tests\Invoke-UnitChecks.ps1` | PS7 | Run by release self-test via bundled pwsh |

### Python Service Layer (subprocess invocation)

The Python backend process helper (`app/processes/launch_env.py`) prepends the following directories to `PATH` before spawning any subprocess:

1. `DesktopApp\Runtime\Python` — bundled Python
2. `Pipeline\Tools\ffmpeg\bin` — FFmpeg
3. `Pipeline\Tools\MKVToolNix` — MKVToolNix
4. **`Pipeline\PowerShell-7.6.0-win-x64`** — bundled pwsh

This ensures that any Python subprocess that calls `pwsh` or runs a `.ps1` file will find the bundled PS7 first, without relying on the operator's system PATH.

---

## Re-Invocation Pattern (PS5 Detected)

Scripts that are sensitive to running under PS5 use this guard at the top:

```powershell
if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "This script requires PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}
```

**When to use this pattern**: Add it to any script that uses PS7-only syntax (ternary operators, null-coalescing, pipeline chain operators `&&`/`||`, `foreach`/`ForEach-Object` parallelism, `using` statements, etc.) and that might be double-clicked or run by an operator who does not know to use `pwsh`.

**Do not add this guard to**: Scripts that are always invoked by other scripts that already guarantee the PS7 host (e.g., scripts launched from the release builder, which resolves pwsh before invoking subscripts).

---

## Prohibited Patterns

### `Invoke-Expression` (eval)

`Invoke-Expression` is prohibited in all build, test, and operator-facing scripts. It bypasses static analysis, makes code paths opaque, and can introduce injection risk when command strings are assembled from external input. The test scaffold actively asserts that new wrapper scripts do not contain `Invoke-Expression`.

### Cross-Version Subprocess With `powershell.exe`

Scripts must not spawn `powershell.exe` (Windows PowerShell 5) explicitly. If a subscript needs to be run in a separate process, use the resolved `pwsh` path. Exception: `.bat` launchers may use `cmd.exe` as an outer shell, but must not pass commands to `powershell.exe`.

### Hard-Coded Absolute `pwsh.exe` Paths

Scripts must not hard-code `C:\Program Files\PowerShell\7\pwsh.exe` or similar absolute paths. Always use the resolution order above (bundled first, system PATH second).

### `Start-Process` For Synchronous Script Invocation

`Start-Process` is asynchronous by nature and loses stdout/stderr unless redirect parameters are used. For invoking subscripts synchronously and capturing output, use the call operator `& $pwsh -File ...` rather than `Start-Process`. `Start-Process` is acceptable for launching external GUI processes or background jobs where return value and stdio are not needed.

---

## What Happens When The Bundled Runtime Is Absent

If `Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe` is missing (e.g., a partial release package):

- **Batch wrappers**: fall back to system `pwsh`; if system `pwsh` is also absent, the `.bat` will pass a bad path to the shell and exit nonzero.
- **Build/test resolvers**: fall back to system `pwsh`; if absent, throw an explicit error naming the missing runtime.
- **Python service layer**: the bundled pwsh directory is simply not prepended; system `pwsh` becomes the PATH-resolved host for subprocesses.
- **Reliability regression checks**: `$PSVersionTable` guard fires and attempts to find system `pwsh`; fails with a human-readable error if not found.

The `scripts\verify-env.ps1` script (invoked by the release self-test) explicitly probes for the bundled pwsh and reports its presence as a named health check row.

---

## Adding A New Script That Needs pwsh

1. Use the existing `Resolve-ReleasePowerShell` pattern (or equivalent) to find the runtime before invoking subprocesses.
2. If the script may be run directly by an operator who might use PS5: add the `$PSVersionTable.PSVersion.Major -lt 7` re-invocation guard at the top.
3. Do not use `Invoke-Expression`.
4. Do not hard-code paths to `pwsh.exe`.
5. If the script is an operator wrapper, including a `SmokeTests/` wrapper invoked from a PowerShell prompt: write it in PS7 syntax only. It will parse-fail on PS5, which is an acceptable failure mode for operator-facing scripts that have the bundled runtime available.

---

## See Also

- Bundled Python resolution: root WebView wrapper scripts (`Test-WebView*.ps1`) use the same resolver pattern for Python as this doc describes for pwsh
- Python service layer PATH setup: `app/processes/launch_env.py`
- Environment verification: `scripts\verify-env.ps1`
- Deployment requirements: `Pipeline/README_MediaPipelineRemuxEncodeAIO_Deployment.md`
