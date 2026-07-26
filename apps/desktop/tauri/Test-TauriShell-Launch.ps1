[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 120,
    [int]$CloseTimeoutSeconds = 20,
    [string]$WindowTitle = 'MediaPipelineRemuxEncodeAIO',
    [ValidateSet('Auto', 'Dev', 'Packaged')]
    [string]$Mode = 'Auto',
    [string]$ExecutablePath,
    [switch]$OriginConfinementProbe
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [IO.Path]::GetFullPath((Join-Path $scriptRoot '..\..\..'))
. (Join-Path $repoRoot 'ops\scripts\smoke\tauri_harness_process_ownership.ps1')

function Resolve-ToolPath {
    param([Parameter(Mandatory)][string]$Name)

    $cmd = Get-Command $Name -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and $_.Source -notmatch '\\WindowsApps\\' } |
        Select-Object -First 1
    if ($cmd -and $cmd.Source) { return [string]$cmd.Source }

    $extraCandidates = @()
    if ($Name -in @('cargo', 'rustc', 'rustup')) {
        $extraCandidates += Join-Path $env:USERPROFILE ".cargo\bin\$Name.exe"
    }
    if ($Name -eq 'node') {
        $extraCandidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter 'node.exe' -ErrorAction SilentlyContinue |
            ForEach-Object { $_.FullName }
    }
    if ($Name -eq 'npm') {
        $extraCandidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter 'npm.cmd' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\node_modules\\corepack\\' } |
            ForEach-Object { $_.FullName }
    }
    foreach ($candidate in $extraCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return [string]$candidate
        }
    }
    return ''
}

function Resolve-VsDevCmd {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null | Select-Object -First 1
        if ($installPath) {
            $candidate = Join-Path $installPath 'Common7\Tools\VsDevCmd.bat'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return [string]$candidate
            }
        }
    }
    return ''
}

function Resolve-PackagedTauriExecutable {
    param(
        [Parameter(Mandatory)][string]$ShellRoot,
        [string]$ExplicitPath = ''
    )

    if ($ExplicitPath) {
        $resolved = [System.IO.Path]::GetFullPath($ExplicitPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "Packaged Tauri executable was not found: $resolved"
        }
        return $resolved
    }

    $candidates = @(
        (Join-Path $ShellRoot 'mediapipeline-tauri-shell.exe'),
        (Join-Path $ShellRoot 'MediaPipelineRemuxEncodeAIO.exe'),
        (Join-Path $ShellRoot '..\mediapipeline-tauri-shell.exe'),
        (Join-Path $ShellRoot '..\MediaPipelineRemuxEncodeAIO.exe')
    )
    foreach ($candidate in $candidates) {
        $full = [System.IO.Path]::GetFullPath($candidate)
        if (Test-Path -LiteralPath $full -PathType Leaf) {
            return $full
        }
    }
    return ''
}

function Get-TauriShellProcesses {
    Get-Process -Name 'mediapipeline-tauri-shell' -ErrorAction SilentlyContinue
}

function Get-LogTail {
    param(
        [string]$Path,
        [int]$LineCount = 80
    )

    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    try {
        return (Get-Content -LiteralPath $Path -Tail $LineCount -ErrorAction Stop) -join [Environment]::NewLine
    } catch {
        return "[could not read log tail: $($_.Exception.Message)]"
    }
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)
    if (-not $Process -or $Process.HasExited) { return }
    try {
        $Process.Kill($true)
    } catch {
        try { $Process.Kill() } catch { }
    }
}

$shellRoot = [System.IO.Path]::GetFullPath($scriptRoot)
$packagedExecutable = Resolve-PackagedTauriExecutable -ShellRoot $shellRoot -ExplicitPath $ExecutablePath
$launchMode = $Mode
if ($launchMode -eq 'Auto') {
    $launchMode = if ($packagedExecutable) { 'Packaged' } else { 'Dev' }
}
if ($launchMode -eq 'Packaged' -and -not $packagedExecutable) {
    throw "No packaged Tauri executable was found. Provide -ExecutablePath, place mediapipeline-tauri-shell.exe beside this script, or run the smoke in -Mode Dev on a development machine."
}

$node = ''
$npm = ''
$cargo = ''
$vsDevCmd = ''
if ($launchMode -eq 'Dev') {
    $node = Resolve-ToolPath node
    $npm = Resolve-ToolPath npm
    $cargo = Resolve-ToolPath cargo
    $vsDevCmd = Resolve-VsDevCmd
    foreach ($tool in @(
        @{ Name = 'node'; Path = $node },
        @{ Name = 'npm'; Path = $npm },
        @{ Name = 'cargo'; Path = $cargo },
        @{ Name = 'VsDevCmd.bat'; Path = $vsDevCmd }
    )) {
        if (-not $tool.Path) {
            throw "$($tool.Name) was not found. Run Test-TauriShell-Prereqs.ps1 -CheckOnly -RequireToolchain -RequireBuildTools first for dev-mode validation, or run this smoke with -Mode Packaged and a compiled executable."
        }
    }
}

$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'mediapipeline-tauri-shell-smoke'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stdoutLog = Join-Path $logRoot "tauri_dev_$stamp.stdout.log"
$stderrLog = Join-Path $logRoot "tauri_dev_$stamp.stderr.log"
$probeEvidence = Join-Path $logRoot "tauri_dev_$stamp.navigation_denials.jsonl"
$probeDeniedUrl = 'http://127.0.0.1:9/redirect-target'
$previousAutomation = [Environment]::GetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_AUTOMATION', 'Process')
$previousDenialFile = [Environment]::GetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_NAVIGATION_DENIAL_FILE', 'Process')
$previousDeniedUrl = [Environment]::GetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_DENIED_NAVIGATION_URL', 'Process')

if ($OriginConfinementProbe) {
    if ($launchMode -ne 'Dev') {
        throw '-OriginConfinementProbe requires -Mode Dev because its evidence hook is excluded from release builds.'
    }
    $env:MEDIA_PIPELINE_TAURI_TEST_AUTOMATION = 'origin-confinement-probe'
    $env:MEDIA_PIPELINE_TAURI_TEST_NAVIGATION_DENIAL_FILE = $probeEvidence
    $env:MEDIA_PIPELINE_TAURI_TEST_DENIED_NAVIGATION_URL = $probeDeniedUrl
}

if ($launchMode -eq 'Dev') {
    $nodeDir = Split-Path -Parent $node
    $cargoDir = Split-Path -Parent $cargo
    $cmdLine = 'call "' + $vsDevCmd + '" -arch=x64 -host_arch=x64 >nul && set "PATH=' + $nodeDir + ';' + $cargoDir + ';%PATH%" && npm run dev'
} else {
    $cmdLine = ''
}

Write-Host "Launching Tauri shell from $shellRoot"
Write-Host "Launch mode: $launchMode"
if ($launchMode -eq 'Packaged') {
    Write-Host "Executable : $packagedExecutable"
}
Write-Host "Logs: $stdoutLog"
try {
    if ($launchMode -eq 'Dev') {
        $devProcess = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/s', '/c', $cmdLine) -WorkingDirectory $shellRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru
    } else {
        $devProcess = Start-Process -FilePath $packagedExecutable -WorkingDirectory $shellRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
    }
} catch {
    [Environment]::SetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_AUTOMATION', $previousAutomation, 'Process')
    [Environment]::SetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_NAVIGATION_DENIAL_FILE', $previousDenialFile, 'Process')
    [Environment]::SetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_DENIED_NAVIGATION_URL', $previousDeniedUrl, 'Process')
    throw
}
$launcherIdentity = $null
$ownedBackendIdentities = @()
$ownedShellIdentities = @()
$newBackendIds = @()
$newShellIds = @()
$windowProcess = $null
$visibleWindowProcess = $null
try {
    $launcherIdentity = Get-TauriHarnessProcessIdentity -ProcessId $devProcess.Id
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($devProcess.HasExited) {
            $stderr = if (Test-Path -LiteralPath $stderrLog) { Get-Content -LiteralPath $stderrLog -Raw -ErrorAction SilentlyContinue } else { '' }
            throw "Tauri launcher process exited before the window appeared. Exit=$($devProcess.ExitCode). stderr=$stderr"
        }
        $processSnapshot = @(Get-TauriHarnessProcessSnapshot)
        $ownedShellIdentities = @(Get-TauriHarnessOwnedShellIdentities -RootIdentity $launcherIdentity -ProcessSnapshot $processSnapshot)
        $ownedBackendIdentities = @(Get-TauriHarnessOwnedBackendIdentities -RootIdentity $launcherIdentity -ProcessSnapshot $processSnapshot)
        $newShellIds = @($ownedShellIdentities | ForEach-Object { [int]$_.ProcessId })
        $newBackendIds = @($ownedBackendIdentities | ForEach-Object { [int]$_.ProcessId })
        $shellProcesses = @(Get-TauriShellProcesses | Where-Object { $newShellIds -contains [int]$_.Id })
        $visibleWindowProcess = $shellProcesses |
            Where-Object { $_.MainWindowTitle -eq $WindowTitle } |
            Select-Object -First 1
        $windowProcess = $shellProcesses |
            Where-Object { $_.MainWindowTitle -eq $WindowTitle -or $_.MainWindowHandle -ne 0 } |
            Select-Object -First 1
        if (-not $windowProcess) {
            $windowProcess = $shellProcesses | Select-Object -First 1
        }
        if ($visibleWindowProcess -and $windowProcess -and $newBackendIds.Count -gt 0) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $visibleWindowProcess) {
        throw "Tauri window '$WindowTitle' was not detected within $TimeoutSeconds seconds. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }
    if (-not $windowProcess) {
        throw "A Tauri shell in launcher PID $($launcherIdentity.ProcessId)'s exact process tree was not detected within $TimeoutSeconds seconds."
    }
    if ($newBackendIds.Count -eq 0) {
        throw "A Python local API backend in launcher PID $($launcherIdentity.ProcessId)'s exact process tree was not detected within $TimeoutSeconds seconds. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }
    if ($ownedBackendIdentities.Count -ne 1) {
        throw "Expected exactly one launcher-owned Local API backend; found $($ownedBackendIdentities.Count): $($newBackendIds -join ', ')."
    }

    Write-Host "Detected Tauri shell PID $($windowProcess.Id), visible window PID $($visibleWindowProcess.Id), and backend PID(s): $($newBackendIds -join ', ')"
    if ($OriginConfinementProbe) {
        $probeDeadline = (Get-Date).AddSeconds(20)
        $probeRows = @()
        while ((Get-Date) -lt $probeDeadline) {
            if (Test-Path -LiteralPath $probeEvidence -PathType Leaf) {
                $probeRows = @(
                    Get-Content -LiteralPath $probeEvidence -ErrorAction Stop |
                        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                        ForEach-Object { $_ | ConvertFrom-Json -ErrorAction Stop }
                )
                if (@($probeRows | Select-Object -ExpandProperty window_label -Unique).Count -ge 2) {
                    break
                }
            }
            Start-Sleep -Milliseconds 250
        }
        foreach ($requiredLabel in @('main', 'pipeline-log')) {
            $row = $probeRows | Where-Object { $_.window_label -eq $requiredLabel } | Select-Object -First 1
            if (-not $row) {
                throw "Origin-confinement probe did not record denied navigation for '$requiredLabel'. stderr_tail=$(Get-LogTail -Path $stderrLog)"
            }
            if ($row.schema_version -ne 'mediapipeline_tauri_navigation_denial.v1' -or $row.candidate_origin -ne 'http://127.0.0.1:9') {
                throw "Origin-confinement probe evidence was invalid for '$requiredLabel': $($row | ConvertTo-Json -Compress)"
            }
            if ($row.PSObject.Properties.Name -contains 'token') {
                throw "Origin-confinement probe evidence unexpectedly contained a token field for '$requiredLabel'."
            }
        }
        Write-Host "Origin-confinement probe passed for main and Pipeline Log windows: $probeEvidence" -ForegroundColor Green
    }
    if (-not $windowProcess.CloseMainWindow()) {
        throw "Tauri window close request was not accepted by PID $($windowProcess.Id). stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }

    if (-not $devProcess.WaitForExit($CloseTimeoutSeconds * 1000)) {
        throw "Tauri launcher process did not exit within $CloseTimeoutSeconds seconds after window close. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }

    $remainingShellIdentities = @(Wait-TauriHarnessProcessIdentitiesGone -Identities $ownedShellIdentities -TimeoutSeconds $CloseTimeoutSeconds -Label 'Tauri shell process(es)')
    if ($remainingShellIdentities.Count -gt 0) {
        throw "Tauri shell process(es) still running after window close: $(@($remainingShellIdentities.ProcessId) -join ', ')"
    }

    $remainingBackendIdentities = @(Wait-TauriHarnessProcessIdentitiesGone -Identities $ownedBackendIdentities -TimeoutSeconds $CloseTimeoutSeconds -Label 'Backend process(es)')
    if ($remainingBackendIdentities.Count -gt 0) {
        throw "Backend process(es) still running after Tauri window close: $(@($remainingBackendIdentities.ProcessId) -join ', ')"
    }

    Write-Host 'Tauri shell launch/close smoke passed.' -ForegroundColor Green
    Write-Host "Shell PID: $($windowProcess.Id)"
    Write-Host "Visible window PID: $($visibleWindowProcess.Id)"
    Write-Host "Backend PID(s): $($newBackendIds -join ', ')"
    exit 0
} finally {
    [Environment]::SetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_AUTOMATION', $previousAutomation, 'Process')
    [Environment]::SetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_NAVIGATION_DENIAL_FILE', $previousDenialFile, 'Process')
    [Environment]::SetEnvironmentVariable('MEDIA_PIPELINE_TAURI_TEST_DENIED_NAVIGATION_URL', $previousDeniedUrl, 'Process')
    foreach ($backendIdentity in $ownedBackendIdentities) {
        if (Test-TauriHarnessProcessIdentityCurrent -Identity $backendIdentity) {
            Stop-TauriHarnessOwnedProcessTree -Identity $backendIdentity -Label 'launcher-owned backend' | Out-Null
        }
    }
    foreach ($shellIdentity in $ownedShellIdentities) {
        if (Test-TauriHarnessProcessIdentityCurrent -Identity $shellIdentity) {
            Stop-TauriHarnessOwnedProcessTree -Identity $shellIdentity -Label 'launcher-owned Tauri shell' | Out-Null
        }
    }
    if ($devProcess -and -not $devProcess.HasExited) {
        Stop-ProcessTree -Process $devProcess
    }
}
