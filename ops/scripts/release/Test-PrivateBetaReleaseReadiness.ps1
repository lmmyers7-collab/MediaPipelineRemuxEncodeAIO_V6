[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $(if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { 'owner/repo' }),

    [string]$Version = $(if ($env:MEDIAPIPELINE_SEMVER_VERSION) { $env:MEDIAPIPELINE_SEMVER_VERSION } else { '2026.6.4+001' }),

    [string]$ReleaseTag,

    [string]$Ref = 'main',

    [switch]$SkipPythonTests,

    [switch]$SkipTauriCheck,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$workflowDryRun = Join-Path $repoRoot 'ops\scripts\release\Test-PrivateBetaWorkflowDryRun.ps1'
$githubSetup = Join-Path $repoRoot 'ops\scripts\release\Test-PrivateBetaGitHubSetup.ps1'
$workflowDispatch = Join-Path $repoRoot 'ops\scripts\release\Invoke-PrivateBetaWorkflowDispatch.ps1'

if (-not $ReleaseTag) {
    $ReleaseTag = "app-v$Version"
}

$checks = [System.Collections.Generic.List[object]]::new()
$commands = [System.Collections.Generic.List[object]]::new()
$phases = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message,
        [ValidateSet('error', 'warning')]
        [string]$Severity = 'error'
    )
    $checks.Add([pscustomobject][ordered]@{
        name = $Name
        ok = $Ok
        severity = $Severity
        message = $Message
    }) | Out-Null
}

function Resolve-PowerShellHost {
    $current = (Get-Process -Id $PID).Path
    if ($current -and (Test-Path -LiteralPath $current -PathType Leaf)) {
        return $current
    }
    foreach ($candidate in @('pwsh', 'powershell')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            return $command.Source
        }
    }
    throw 'No PowerShell host could be resolved for private beta release readiness.'
}

function Invoke-ReadinessPhase {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [string[]]$Arguments
    )
    $phaseArgs = [System.Collections.Generic.List[string]]::new()
    foreach ($arg in @(
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $ScriptPath
    )) {
        $phaseArgs.Add($arg) | Out-Null
    }
    foreach ($arg in $Arguments) {
        $phaseArgs.Add($arg) | Out-Null
    }
    $phaseArgs.Add('-AsJson') | Out-Null

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = Resolve-PowerShellHost
    foreach ($arg in $phaseArgs) {
        $psi.ArgumentList.Add($arg)
    }
    $psi.WorkingDirectory = $repoRoot
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $commands.Add([pscustomobject][ordered]@{
        name = $Name
        exit_code = $process.ExitCode
        stdout_tail = if ($stdout.Length -gt 3000) { $stdout.Substring($stdout.Length - 3000) } else { $stdout }
        stderr_tail = if ($stderr.Length -gt 3000) { $stderr.Substring($stderr.Length - 3000) } else { $stderr }
    }) | Out-Null

    $payload = $null
    if (-not [string]::IsNullOrWhiteSpace($stdout)) {
        try {
            $payload = $stdout | ConvertFrom-Json -Depth 20
        } catch {
            Add-Check "${Name}:json" $false "Readiness phase $Name did not return parseable JSON: $($_.Exception.Message)"
        }
    }

    $phaseOk = ($process.ExitCode -eq 0)
    if ($payload -and $payload.PSObject.Properties.Name -contains 'ok') {
        $phaseOk = $phaseOk -and [bool]$payload.ok
    }

    $phases.Add([pscustomobject][ordered]@{
        name = $Name
        ok = $phaseOk
        exit_code = $process.ExitCode
        schema_version = if ($payload) { [string]$payload.schema_version } else { $null }
        warning_count = if ($payload -and $payload.PSObject.Properties.Name -contains 'warning_count') { [int]$payload.warning_count } else { $null }
        error_count = if ($payload -and $payload.PSObject.Properties.Name -contains 'error_count') { [int]$payload.error_count } else { $null }
    }) | Out-Null

    Add-Check "${Name}:passed" $phaseOk "Readiness phase must pass: $Name."
}

Add-Check 'repository:format' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo.'
Add-Check 'version:format' ($Version -match '^\d+\.\d+\.\d+\+\d+$') `
    'Version must be Tauri-compatible semver with build metadata, for example 2026.6.4+001.'
Add-Check 'release_tag:format' ($ReleaseTag -match '^app-v\d+\.\d+\.\d+\+\d+$') `
    'Release tag must use app-v<version>.'
Add-Check 'phase:workflow_dry_run_script' (Test-Path -LiteralPath $workflowDryRun -PathType Leaf) `
    'Private beta workflow dry-run script must exist.'
Add-Check 'phase:github_setup_script' (Test-Path -LiteralPath $githubSetup -PathType Leaf) `
    'Private beta GitHub setup preflight script must exist.'
Add-Check 'phase:workflow_dispatch_script' (Test-Path -LiteralPath $workflowDispatch -PathType Leaf) `
    'Private beta workflow dispatch helper must exist.'

if (Test-Path -LiteralPath $workflowDryRun -PathType Leaf) {
    $dryRunArgs = @(
        '-Channel',
        $Channel,
        '-Repository',
        $Repository,
        '-Version',
        $Version,
        '-ReleaseTag',
        $ReleaseTag
    )
    if ($SkipPythonTests) {
        $dryRunArgs += '-SkipPythonTests'
    }
    if ($SkipTauriCheck) {
        $dryRunArgs += '-SkipTauriCheck'
    }
    Invoke-ReadinessPhase -Name 'workflow_dry_run' -ScriptPath $workflowDryRun -Arguments $dryRunArgs
}

if (Test-Path -LiteralPath $githubSetup -PathType Leaf) {
    Invoke-ReadinessPhase -Name 'github_setup_static' -ScriptPath $githubSetup -Arguments @(
        '-Repository',
        $Repository,
        '-StaticOnly'
    )
}

if (Test-Path -LiteralPath $workflowDispatch -PathType Leaf) {
    Invoke-ReadinessPhase -Name 'workflow_dispatch_dry_run' -ScriptPath $workflowDispatch -Arguments @(
        '-Channel',
        $Channel,
        '-Repository',
        $Repository,
        '-Version',
        $Version,
        '-ReleaseTag',
        $ReleaseTag,
        '-Ref',
        $Ref,
        '-DryRun'
    )
}

Add-Check 'readiness:read_only' $true `
    'Release-readiness runner uses workflow dry-run, static GitHub setup preflight, and dispatch dry-run only; it does not publish, upload, dispatch, or mutate GitHub state.'

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_release_readiness.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    ref = $Ref
    skip_python_tests = [bool]$SkipPythonTests
    skip_tauri_check = [bool]$SkipTauriCheck
    warning_count = $warningCount
    error_count = $errorCount
    phases = @($phases)
    checks = @($checks)
    commands = @($commands)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta release readiness passed for $Channel $Version."
    } else {
        Write-Host "Private beta release readiness failed for $Channel $Version."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
