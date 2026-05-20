[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 120,
    [int]$CloseTimeoutSeconds = 20,
    [string]$WindowTitle = 'MediaPipelineRemuxEncodeAIO V6',
    [int]$MaxElements = 220
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

function Get-LocalApiBackendProcesses {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { [string]$_.CommandLine -match 'mediapipeline_desktop_app\.local_api_main' }
}

function Get-TauriShellProcesses {
    Get-Process -Name 'mediapipeline-tauri-shell' -ErrorAction SilentlyContinue
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
        [int]$TimeoutSeconds
    )

    $ids = @($ProcessIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)
    if ($ids.Count -eq 0) { return @() }
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $remaining = @($ids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        if ($remaining.Count -eq 0) { return @() }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $remaining
}

function Get-LogTail {
    param([string]$Path, [int]$LineCount = 80)

    if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    try {
        return (Get-Content -LiteralPath $Path -Tail $LineCount -ErrorAction Stop) -join [Environment]::NewLine
    } catch {
        return "[could not read log tail: $($_.Exception.Message)]"
    }
}

function Get-UiAutomationRows {
    param(
        [Parameter(Mandatory)][IntPtr]$WindowHandle,
        [int]$Limit
    )

    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($WindowHandle)
    if (-not $root) { throw "UI Automation could not read window handle $WindowHandle." }
    $all = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $rows = New-Object System.Collections.Generic.List[object]
    for ($idx = 0; $idx -lt $all.Count -and $rows.Count -lt $Limit; $idx++) {
        $item = $all.Item($idx)
        $name = [string]$item.Current.Name
        $automationId = [string]$item.Current.AutomationId
        $controlType = [string]$item.Current.ControlType.ProgrammaticName
        $className = [string]$item.Current.ClassName
        if (-not $name -and -not $automationId -and -not $className) { continue }
        $rows.Add([pscustomobject]@{
            Index = $idx
            ControlType = $controlType
            AutomationId = $automationId
            Name = $name
            ClassName = $className
            IsEnabled = [bool]$item.Current.IsEnabled
            IsOffscreen = [bool]$item.Current.IsOffscreen
        }) | Out-Null
    }
    return $rows
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$shellRoot = [System.IO.Path]::GetFullPath($scriptRoot)
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
        throw "$($tool.Name) was not found. Run Test-TauriShell-Prereqs.ps1 -RequireToolchain -RequireBuildTools first."
    }
}

$baselineBackendIds = @(Get-LocalApiBackendProcesses | ForEach-Object { [int]$_.ProcessId })
$baselineShellIds = @(Get-TauriShellProcesses | ForEach-Object { [int]$_.Id })
$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'mediapipeline-tauri-shell-uia-probe'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stdoutLog = Join-Path $logRoot "tauri_uia_$stamp.stdout.log"
$stderrLog = Join-Path $logRoot "tauri_uia_$stamp.stderr.log"

$nodeDir = Split-Path -Parent $node
$cargoDir = Split-Path -Parent $cargo
$cmdLine = 'call "' + $vsDevCmd + '" -arch=x64 -host_arch=x64 >nul && set "PATH=' + $nodeDir + ';' + $cargoDir + ';%PATH%" && npm run dev'

Write-Host "Launching Tauri dev shell from $shellRoot"
Write-Host "Logs: $stdoutLog"
$devProcess = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/s', '/c', $cmdLine) -WorkingDirectory $shellRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru
$newBackendIds = @()
$newShellIds = @()
$visibleWindowProcess = $null
try {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($devProcess.HasExited) {
            throw "Tauri dev process exited before the window appeared. Exit=$($devProcess.ExitCode). stderr=$(Get-LogTail -Path $stderrLog)"
        }
        $shellProcesses = @(Get-TauriShellProcesses | Where-Object { $baselineShellIds -notcontains [int]$_.Id })
        $newShellIds = @($shellProcesses | ForEach-Object { [int]$_.Id })
        $visibleWindowProcess = $shellProcesses |
            Where-Object { $_.MainWindowTitle -eq $WindowTitle } |
            Select-Object -First 1
        $backendProcesses = @(Get-LocalApiBackendProcesses)
        $newBackendIds = @($backendProcesses | Where-Object { $baselineBackendIds -notcontains [int]$_.ProcessId } | ForEach-Object { [int]$_.ProcessId })
        if ($visibleWindowProcess -and $newBackendIds.Count -gt 0) { break }
        Start-Sleep -Milliseconds 500
    }

    if (-not $visibleWindowProcess) {
        throw "Tauri window '$WindowTitle' was not detected within $TimeoutSeconds seconds. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }

    Write-Host "Detected Tauri window PID $($visibleWindowProcess.Id), backend PID(s): $($newBackendIds -join ', ')"
    $rows = @(Get-UiAutomationRows -WindowHandle $visibleWindowProcess.MainWindowHandle -Limit $MaxElements)
    $interesting = @($rows | Where-Object {
        $_.AutomationId -or
        $_.Name -match 'Launch|Start Pipeline|Single File|Mode|Schedule|Dashboard|Sample Validation|Append Validation'
    })
    [pscustomobject]@{
        ok = $true
        shell_pid = [int]$visibleWindowProcess.Id
        backend_pids = $newBackendIds
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
        inspected_count = $rows.Count
        interesting = $interesting
    } | ConvertTo-Json -Depth 6

    if (-not $visibleWindowProcess.CloseMainWindow()) {
        Write-Warning "Tauri window close request was not accepted by PID $($visibleWindowProcess.Id)."
    }
    if (-not $devProcess.WaitForExit($CloseTimeoutSeconds * 1000)) {
        Write-Warning "Tauri dev process did not exit within $CloseTimeoutSeconds seconds."
    }
    $remainingShellIds = @(Wait-ProcessIdsGone -ProcessIds $newShellIds -TimeoutSeconds $CloseTimeoutSeconds)
    $remainingBackendIds = @(Wait-ProcessIdsGone -ProcessIds $newBackendIds -TimeoutSeconds $CloseTimeoutSeconds)
    if ($remainingShellIds.Count -gt 0 -or $remainingBackendIds.Count -gt 0) {
        throw "Probe cleanup left processes running. shell=$($remainingShellIds -join ', ') backend=$($remainingBackendIds -join ', ')"
    }
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
