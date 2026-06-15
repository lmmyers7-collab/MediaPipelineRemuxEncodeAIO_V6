[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$SourceFile,

    [int]$TimeoutSeconds = 180,
    [int]$PromptTimeoutSeconds = 20,
    [int]$CloseTimeoutSeconds = 30,
    [int]$ActiveReadinessTimeoutSeconds = 30,
    [string]$WindowTitle = 'MediaPipelineRemuxEncodeAIO',
    [AllowEmptyString()]
    [string]$ActiveJobsDir = '',
    [switch]$LeavePromptOpen
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Assert-ExplicitPgRuntimeEvidencePath {
    param(
        [AllowEmptyString()]
        [string]$Path,
        [Parameter(Mandatory)][string]$ParameterName
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "Parameter -$ParameterName is required. Pass an explicit isolated runtime evidence path for this PG run."
    }
    if (-not [System.IO.Path]::IsPathFullyQualified($Path)) {
        throw "Parameter -$ParameterName must be a fully qualified path: $Path"
    }

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $legacyRoot = [System.IO.Path]::GetFullPath('E:\Videos\Scratch\State')
    if ($fullPath.StartsWith($legacyRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Parameter -$ParameterName must not use the legacy machine-specific runtime state root E:\Videos\Scratch\State. Pass a temp LocalBase\State path for this PG run."
    }
    return $fullPath
}

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

function Get-BackendUrlForProcessId {
    param(
        [Parameter(Mandatory)][int]$ProcessId,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $ports = @()
        try {
            $ports = @(Get-NetTCPConnection -State Listen -OwningProcess $ProcessId -ErrorAction Stop |
                Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::1', '::') } |
                ForEach-Object { [int]$_.LocalPort })
        } catch {
            $netstat = netstat -ano -p tcp 2>$null
            $ports = @($netstat |
                Select-String -Pattern "\s+(127\.0\.0\.1|0\.0\.0\.0):(\d+)\s+.*LISTENING\s+$ProcessId\s*$" |
                ForEach-Object { [int]$_.Matches[0].Groups[2].Value })
        }
        foreach ($port in ($ports | Sort-Object -Unique)) {
            $url = "http://127.0.0.1:$port"
            try {
                Invoke-WebRequest -UseBasicParsing -Uri "$url/api/health" -TimeoutSec 3 | Out-Null
                return $url
            } catch {
                continue
            }
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Could not determine local API URL for backend PID $ProcessId."
}

function Get-BackendBootstrapFromIndex {
    param([Parameter(Mandatory)][string]$BackendUrl)

    $html = (Invoke-WebRequest -UseBasicParsing -Uri "$BackendUrl/" -TimeoutSec 10).Content
    if ($html -match '(?s)window\.MEDIA_PIPELINE_BOOTSTRAP\s*=\s*Object\.assign\(\s*\{\}\s*,\s*(\{.*?\})\s*,\s*window\.MEDIA_PIPELINE_TAURI_BOOTSTRAP\s*\|\|\s*\{\}\s*\);') {
        return $Matches[1] | ConvertFrom-Json
    }
    if ($html -match '(?s)window\.MEDIA_PIPELINE_BOOTSTRAP\s*=\s*(\{.*?\});') {
        return $Matches[1] | ConvertFrom-Json
    }
    else {
        throw "Could not find MEDIA_PIPELINE_BOOTSTRAP in backend index."
    }
}

function Wait-BackendTokenCapture {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$BackendUrl,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = ''
    do {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            try {
                $payload = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json
                if ([string]$payload.schema_version -ne 'mediapipeline_tauri_test_auth_capture.v1') {
                    throw "unexpected schema_version=$($payload.schema_version)"
                }
                if ([string]$payload.url -ne $BackendUrl) {
                    throw "capture URL $($payload.url) did not match $BackendUrl"
                }
                $captured = [string]$payload.token
                if ([string]::IsNullOrWhiteSpace($captured)) {
                    throw "capture did not include a token"
                }
                return $captured
            } catch {
                $lastError = [string]$_.Exception.Message
            }
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for Tauri test auth capture at $Path. Last error: $lastError"
}

function Invoke-BackendJson {
    param(
        [Parameter(Mandatory)][string]$Method,
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][string]$Token,
        [object]$Body = $null
    )

    $headers = @{ Authorization = "Bearer $Token" }
    $parameters = @{
        Method = $Method
        Uri = $Uri
        Headers = $headers
        TimeoutSec = 30
    }
    if ($null -ne $Body) {
        $parameters['ContentType'] = 'application/json'
        $parameters['Body'] = ($Body | ConvertTo-Json -Depth 12 -Compress)
    }
    Invoke-RestMethod @parameters
}

function Get-LaunchPid {
    param([object]$LaunchResult)

    $data = $null
    if ($LaunchResult -and $LaunchResult.PSObject.Properties['data']) {
        $data = $LaunchResult.PSObject.Properties['data'].Value
    }
    $candidates = @()
    if ($data -and $data.PSObject.Properties['pid']) {
        $candidates += $data.PSObject.Properties['pid'].Value
    }
    if ($LaunchResult -and $LaunchResult.PSObject.Properties['pid']) {
        $candidates += $LaunchResult.PSObject.Properties['pid'].Value
    }
    foreach ($candidate in $candidates) {
        if ($null -ne $candidate) {
            try {
                $value = [int]$candidate
                if ($value -gt 0) { return $value }
            } catch { }
        }
    }
    $message = ''
    if ($LaunchResult -and $LaunchResult.PSObject.Properties['message']) {
        $message = [string]$LaunchResult.PSObject.Properties['message'].Value
    }
    if ($message -match 'PID\s+(\d+)') {
        return [int]$Matches[1]
    }
    return 0
}

function Wait-UnsafeCloseReadiness {
    param(
        [Parameter(Mandatory)][string]$BackendUrl,
        [Parameter(Mandatory)][string]$Token,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastReadiness = $null
    do {
        $lastReadiness = Invoke-BackendJson -Method GET -Uri "$BackendUrl/api/backend/close-readiness" -Token $Token
        if ($false -eq [bool]$lastReadiness.safe_to_close) {
            return $lastReadiness
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Close-readiness stayed safe for ${TimeoutSeconds}s. Last payload: $($lastReadiness | ConvertTo-Json -Depth 8 -Compress)"
}

function Get-LatestActiveJobForSource {
    param(
        [Parameter(Mandatory)][string]$Directory,
        [Parameter(Mandatory)][string]$Source
    )

    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        return $null
    }
    $files = Get-ChildItem -LiteralPath $Directory -Filter '*.json' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    foreach ($file in $files) {
        try {
            $payload = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop | ConvertFrom-Json
        } catch {
            continue
        }
        $metadata = $payload.metadata
        if ($metadata -and ([string]$metadata.single_file) -eq $Source) {
            return [pscustomobject]@{
                Path = $file.FullName
                Payload = $payload
            }
        }
    }
    return $null
}

if (-not ('Win32WindowText' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class Win32WindowText
{
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

    [DllImport("user32.dll")]
    private static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

    private const uint WM_COMMAND = 0x0111;
    private const int IDOK = 1;

    public static IntPtr FindTopLevelByTitle(string title)
    {
        IntPtr found = IntPtr.Zero;
        EnumWindows(delegate(IntPtr hWnd, IntPtr lParam)
        {
            if (!IsWindowVisible(hWnd)) { return true; }
            string text = TextOf(hWnd);
            if (String.Equals(text, title, StringComparison.Ordinal))
            {
                found = hWnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }

    public static string[] GetChildTexts(IntPtr parent)
    {
        List<string> lines = new List<string>();
        string parentText = TextOf(parent);
        if (!String.IsNullOrWhiteSpace(parentText))
        {
            lines.Add("Window: " + parentText);
        }
        EnumChildWindows(parent, delegate(IntPtr hWnd, IntPtr lParam)
        {
            string text = TextOf(hWnd);
            if (!String.IsNullOrWhiteSpace(text))
            {
                lines.Add(ClassOf(hWnd) + ": " + text);
            }
            return true;
        }, IntPtr.Zero);
        return lines.ToArray();
    }

    public static void ClickOk(IntPtr dialog)
    {
        SendMessage(dialog, WM_COMMAND, new IntPtr(IDOK), IntPtr.Zero);
    }

    private static string TextOf(IntPtr hWnd)
    {
        StringBuilder builder = new StringBuilder(8192);
        GetWindowText(hWnd, builder, builder.Capacity);
        return builder.ToString();
    }

    private static string ClassOf(IntPtr hWnd)
    {
        StringBuilder builder = new StringBuilder(256);
        GetClassName(hWnd, builder, builder.Capacity);
        return builder.ToString();
    }
}
'@
}

$resolvedSource = [System.IO.Path]::GetFullPath($SourceFile)
if (-not (Test-Path -LiteralPath $resolvedSource -PathType Leaf)) {
    throw "Source file does not exist: $resolvedSource"
}
$ActiveJobsDir = Assert-ExplicitPgRuntimeEvidencePath -Path $ActiveJobsDir -ParameterName 'ActiveJobsDir'

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
$baselineShellIds = @(Get-ProcessIdSet -Processes @(Get-TauriShellProcesses))
$logRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'mediapipeline-tauri-shell-pg1-active-close'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stdoutLog = Join-Path $logRoot "tauri_pg1_$stamp.stdout.log"
$stderrLog = Join-Path $logRoot "tauri_pg1_$stamp.stderr.log"
$tokenCapturePath = Join-Path $logRoot "tauri_pg1_$stamp.backend_auth.json"

$nodeDir = Split-Path -Parent $node
$cargoDir = Split-Path -Parent $cargo
$cmdLine = 'call "' + $vsDevCmd + '" -arch=x64 -host_arch=x64 >nul && set "PATH=' + $nodeDir + ';' + $cargoDir + ';%PATH%" && npm run dev'

Write-Host "Launching Tauri dev shell from $shellRoot"
Write-Host "Logs: $stdoutLog"
$previousTokenCapture = $env:MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE
$env:MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE = $tokenCapturePath
$devProcess = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/s', '/c', $cmdLine) -WorkingDirectory $shellRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru
$env:MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE = $previousTokenCapture
$newBackendIds = @()
$newShellIds = @()
$windowProcess = $null
$visibleWindowProcess = $null
$launchedPipelinePid = 0
$promptTranscript = ''
$result = $null
try {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($devProcess.HasExited) {
            $stderr = if (Test-Path -LiteralPath $stderrLog) { Get-Content -LiteralPath $stderrLog -Raw -ErrorAction SilentlyContinue } else { '' }
            throw "Tauri dev process exited before the window appeared. Exit=$($devProcess.ExitCode). stderr=$stderr"
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

    $backendPid = [int]$newBackendIds[0]
    $backendUrl = Get-BackendUrlForProcessId -ProcessId $backendPid
    $bootstrap = Get-BackendBootstrapFromIndex -BackendUrl $backendUrl
    if ([string]$bootstrap.token) {
        throw "Backend WebView bootstrap leaked the bearer token in Tauri mode."
    }
    if ([string]$bootstrap.tokenSource -ne 'tauri-initialization-script') {
        throw "Backend WebView bootstrap did not identify the Tauri token source. tokenSource=$($bootstrap.tokenSource)"
    }
    if ([string]$bootstrap.shellSurface -ne 'tauri') {
        throw "Backend WebView bootstrap did not identify the Tauri shell surface. shellSurface=$($bootstrap.shellSurface)"
    }
    $token = Wait-BackendTokenCapture -Path $tokenCapturePath -BackendUrl $backendUrl

    Write-Host "Detected Tauri shell PID $($windowProcess.Id), visible window PID $($visibleWindowProcess.Id), backend PID $backendPid, URL $backendUrl"
    Write-Host "Starting single-file pipeline work for PG-1 active-close validation."
    $launchRequest = @{
        mode = 'once'
        sleep_seconds = 30
        show_config = $false
        show_console = $false
        schedule_override = 'run_once'
        single_file = $resolvedSource
    }
    $launchResult = Invoke-BackendJson -Method POST -Uri "$backendUrl/api/pipeline/start" -Token $token -Body $launchRequest
    if ($false -eq [bool]$launchResult.ok) {
        throw "Pipeline start failed: $($launchResult | ConvertTo-Json -Depth 8 -Compress)"
    }
    $launchedPipelinePid = Get-LaunchPid -LaunchResult $launchResult
    if ($launchedPipelinePid -le 0) {
        throw "Pipeline start succeeded but no process PID was found: $($launchResult | ConvertTo-Json -Depth 8 -Compress)"
    }
    Write-Host "Started pipeline PID $launchedPipelinePid."

    $unsafeReadiness = Wait-UnsafeCloseReadiness -BackendUrl $backendUrl -Token $token -TimeoutSeconds $ActiveReadinessTimeoutSeconds
    Write-Host "Close-readiness is unsafe: $($unsafeReadiness.reason)"

    if (-not $windowProcess.CloseMainWindow()) {
        throw "Tauri window close request was not accepted by PID $($windowProcess.Id)."
    }

    $promptDeadline = (Get-Date).AddSeconds($PromptTimeoutSeconds)
    $dialog = [IntPtr]::Zero
    do {
        $dialog = [Win32WindowText]::FindTopLevelByTitle('MediaPipeline active work')
        if ($dialog -ne [IntPtr]::Zero) { break }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $promptDeadline)
    if ($dialog -eq [IntPtr]::Zero) {
        throw "Native active-work close prompt was not found within $PromptTimeoutSeconds seconds."
    }

    $promptTranscript = ([Win32WindowText]::GetChildTexts($dialog) | Select-Object -Unique) -join [Environment]::NewLine
    Write-Host "Captured native close prompt transcript:"
    Write-Host $promptTranscript
    foreach ($required in @(
        'Close the MediaPipeline shell anyway?',
        'The backend will be asked to stop app-owned pipeline work before shutdown'
    )) {
        if ($promptTranscript -notlike "*$required*") {
            throw "Native prompt transcript did not include required text: $required"
        }
    }

    if ($LeavePromptOpen) {
        throw "Prompt left open by request. Close it manually before rerunning validation."
    }
    [Win32WindowText]::ClickOk($dialog)

    if (-not $devProcess.WaitForExit($CloseTimeoutSeconds * 1000)) {
        throw "Tauri dev process did not exit within $CloseTimeoutSeconds seconds after confirming close. stdout_tail=$(Get-LogTail -Path $stdoutLog) stderr_tail=$(Get-LogTail -Path $stderrLog)"
    }

    $remainingShellIds = @(Wait-ProcessIdsGone -ProcessIds $newShellIds -TimeoutSeconds $CloseTimeoutSeconds -Label 'Tauri shell process(es)')
    if ($remainingShellIds.Count -gt 0) {
        throw "Tauri shell process(es) still running after confirmed active close: $($remainingShellIds -join ', ')"
    }

    $remainingBackendIds = @(Wait-ProcessIdsGone -ProcessIds $newBackendIds -TimeoutSeconds $CloseTimeoutSeconds -Label 'Backend process(es)')
    if ($remainingBackendIds.Count -gt 0) {
        throw "Backend process(es) still running after confirmed active close: $($remainingBackendIds -join ', ')"
    }

    $remainingPipeline = Get-Process -Id $launchedPipelinePid -ErrorAction SilentlyContinue
    if ($remainingPipeline) {
        throw "Pipeline process PID $launchedPipelinePid still running after confirmed active close."
    }

    $activeJob = Get-LatestActiveJobForSource -Directory $ActiveJobsDir -Source $resolvedSource
    if (-not $activeJob) {
        throw "No ActiveJobs record was found for source $resolvedSource under $ActiveJobsDir."
    }
    $activeJobStatus = [string]$activeJob.Payload.status
    if ($activeJobStatus -ne 'killed') {
        throw "ActiveJobs record did not record force-close cleanup as killed. Status=$activeJobStatus Path=$($activeJob.Path)"
    }

    $result = [ordered]@{
        ok = $true
        source_file = $resolvedSource
        shell_pid = [int]$windowProcess.Id
        backend_pid = $backendPid
        pipeline_pid = $launchedPipelinePid
        backend_url = $backendUrl
        close_readiness_reason = [string]$unsafeReadiness.reason
        close_readiness_state = [string]$unsafeReadiness.state
        prompt_transcript = $promptTranscript
        active_job_record = [string]$activeJob.Path
        active_job_status = $activeJobStatus
        active_job_return_code = $activeJob.Payload.return_code
        stdout_log = $stdoutLog
        stderr_log = $stderrLog
        auth_capture = $tokenCapturePath
    }
    Write-Host 'PG-1 active Tauri close validation passed.' -ForegroundColor Green
    $result | ConvertTo-Json -Depth 8
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
    if ($launchedPipelinePid -gt 0) {
        Stop-ProcessIdTree -ProcessId $launchedPipelinePid
    }
}
