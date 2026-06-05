[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 120,
    [int]$CloseTimeoutSeconds = 20,
    [string]$WindowTitle = 'MediaPipelineRemuxEncodeAIO',
    [ValidateSet('Auto', 'Dev', 'Packaged')]
    [string]$Mode = 'Auto',
    [string]$ExecutablePath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

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

function Get-LocalApiBackendProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            [string]$_.Name -match '^python(\d+(\.\d+)*)?\.exe$' -and
            [string]$_.CommandLine -match 'mediapipeline.desktop\.local_api_main'
        }
}

function Get-TauriShellProcesses {
    Get-Process -Name 'mediapipeline-tauri-shell' -ErrorAction SilentlyContinue
}

function Get-ProcessIdSet {
    param([object[]]$Processes)

    @($Processes | ForEach-Object { [int]$_.Id })
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

function Stop-ProcessIdTree {
    param([int]$ProcessId)

    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) { return }
    Stop-ProcessTree -Process $proc
}

function Wait-ProcessIdsGone {
    param(
        [int[]]$ProcessIds,
        [int]$TimeoutSeconds,
        [string]$Label
    )

    $ids = @($ProcessIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)
    if ($ids.Count -eq 0) { return @() }
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $remaining = @($ids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        if ($remaining.Count -eq 0) { return @() }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    Write-Host "$Label still running after ${TimeoutSeconds}s: $($remaining -join ', ')" -ForegroundColor Yellow
    return $remaining
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
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

$baselineBackendIds = @(Get-LocalApiBackendProcesses | ForEach-Object { [int]$_.ProcessId })
$baselineShellIds = @(Get-ProcessIdSet -Processes @(Get-TauriShellProcesses))
$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'mediapipeline-tauri-shell-smoke'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stdoutLog = Join-Path $logRoot "tauri_dev_$stamp.stdout.log"
$stderrLog = Join-Path $logRoot "tauri_dev_$stamp.stderr.log"

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
if ($launchMode -eq 'Dev') {
    $devProcess = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/s', '/c', $cmdLine) -WorkingDirectory $shellRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru
} else {
    $devProcess = Start-Process -FilePath $packagedExecutable -WorkingDirectory $shellRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
}
$newBackendIds = @()
$newShellIds = @()
$windowProcess = $null
$visibleWindowProcess = $null
try {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($devProcess.HasExited) {
            $stderr = if (Test-Path -LiteralPath $stderrLog) { Get-Content -LiteralPath $stderrLog -Raw -ErrorAction SilentlyContinue } else { '' }
            throw "Tauri launcher process exited before the window appeared. Exit=$($devProcess.ExitCode). stderr=$stderr"
        }
        $shellProcesses = @(Get-TauriShellProcesses | Where-Object { $baselineShellIds -notcontains [int]$_.Id })
        $newShellIds = @(Get-ProcessIdSet -Processes $shellProcesses)
        $visibleWindowProcess = $shellProcesses |
            Where-Object { $_.MainWindowTitle -eq $WindowTitle } |
            Select-Object -First 1
        $windowProcess = $shellProcesses |
            Where-Object { $_.MainWindowTitle -eq $WindowTitle -or $_.MainWindowHandle -ne 0 } |
            Select-Object -First 1
        if (-not $windowProcess) {
            $windowProcess = $shellProcesses | Select-Object -First 1
        }
        $backendProcesses = @(Get-LocalApiBackendProcesses)
        $newBackendIds = @($backendProcesses | Where-Object { $baselineBackendIds -notcontains [int]$_.ProcessId } | ForEach-Object { [int]$_.ProcessId })
        if ($visibleWindowProcess -and $windowProcess -and $newBackendIds.Count -gt 0) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $visibleWindowProcess) {
        throw "Tauri window '$WindowTitle' was not detected within $TimeoutSeconds seconds. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }
    if (-not $windowProcess) {
        throw "New Tauri shell process was not detected within $TimeoutSeconds seconds. Baseline shell PID(s): $($baselineShellIds -join ', ')"
    }
    if ($newBackendIds.Count -eq 0) {
        throw "New Python local API backend process was not detected within $TimeoutSeconds seconds. Baseline backend PID(s): $($baselineBackendIds -join ', ') stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }

    Write-Host "Detected Tauri shell PID $($windowProcess.Id), visible window PID $($visibleWindowProcess.Id), and backend PID(s): $($newBackendIds -join ', ')"
    if (-not $windowProcess.CloseMainWindow()) {
        throw "Tauri window close request was not accepted by PID $($windowProcess.Id). stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }

    if (-not $devProcess.WaitForExit($CloseTimeoutSeconds * 1000)) {
        throw "Tauri launcher process did not exit within $CloseTimeoutSeconds seconds after window close. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }

    $remainingShellIds = @(Wait-ProcessIdsGone -ProcessIds $newShellIds -TimeoutSeconds $CloseTimeoutSeconds -Label 'Tauri shell process(es)')
    if ($remainingShellIds.Count -gt 0) {
        throw "Tauri shell process(es) still running after window close: $($remainingShellIds -join ', ')"
    }

    $remainingBackendIds = @(Wait-ProcessIdsGone -ProcessIds $newBackendIds -TimeoutSeconds $CloseTimeoutSeconds -Label 'Backend process(es)')
    if ($remainingBackendIds.Count -gt 0) {
        throw "Backend process(es) still running after Tauri window close: $($remainingBackendIds -join ', ')"
    }

    Write-Host 'Tauri shell launch/close smoke passed.' -ForegroundColor Green
    Write-Host "Shell PID: $($windowProcess.Id)"
    Write-Host "Visible window PID: $($visibleWindowProcess.Id)"
    Write-Host "Backend PID(s): $($newBackendIds -join ', ')"
    exit 0
} finally {
    if ($devProcess -and -not $devProcess.HasExited) {
        Stop-ProcessTree -Process $devProcess
    }
    foreach ($shellPid in $newShellIds) {
        Stop-ProcessIdTree -ProcessId $shellPid
    }
    foreach ($backendPid in $newBackendIds) {
        Stop-ProcessIdTree -ProcessId $backendPid
    }
}
