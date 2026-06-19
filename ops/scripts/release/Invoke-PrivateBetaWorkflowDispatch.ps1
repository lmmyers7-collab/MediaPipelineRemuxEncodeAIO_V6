[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$Version = $(if ($env:MEDIAPIPELINE_SEMVER_VERSION) { $env:MEDIAPIPELINE_SEMVER_VERSION } else { '2026.6.4+001' }),

    [string]$ReleaseTag,

    [string]$Ref,

    [switch]$PublishRelease,

    [switch]$SkipSetupPreflight,

    [switch]$DryRun,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$setupPreflight = Join-Path $repoRoot 'ops\scripts\release\Test-PrivateBetaGitHubSetup.ps1'
$workflowFile = 'private-beta-windows.yml'

if (-not $ReleaseTag) {
    $ReleaseTag = "app-v$Version"
}
if (-not $Ref) {
    $Ref = 'main'
}

$checks = [System.Collections.Generic.List[object]]::new()
$commands = [System.Collections.Generic.List[object]]::new()

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

function Resolve-Tool {
    param([string]$Name)
    foreach ($candidate in @("$Name.exe", "$Name.cmd", $Name)) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            if ([System.IO.Path]::GetExtension($command.Source) -ieq '.ps1') {
                $siblingCmd = [System.IO.Path]::ChangeExtension($command.Source, '.cmd')
                if (Test-Path -LiteralPath $siblingCmd -PathType Leaf) {
                    return $siblingCmd
                }
            }
            return $command.Source
        }
    }
    return $null
}

function Invoke-CapturedCommand {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $repoRoot
    )
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    foreach ($arg in $Arguments) {
        $psi.ArgumentList.Add($arg)
    }
    $psi.WorkingDirectory = $WorkingDirectory
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
    return $process.ExitCode
}

function Resolve-PowerShellHost {
    $current = (Get-Process -Id $PID).Path
    if ($current -and (Test-Path -LiteralPath $current -PathType Leaf)) {
        return $current
    }
    foreach ($name in @('pwsh', 'powershell')) {
        $resolved = Resolve-Tool $name
        if ($resolved) {
            return $resolved
        }
    }
    throw 'No PowerShell host could be resolved for setup preflight.'
}

Add-Check 'repository:format' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo.'
Add-Check 'version:format' ($Version -match '^\d+\.\d+\.\d+\+\d+$') `
    'Version must be Tauri-compatible semver with build metadata, for example 2026.6.4+001.'
Add-Check 'release_tag:format' ($ReleaseTag -match '^app-v\d+\.\d+\.\d+\+\d+$') `
    'Release tag must use app-v<version>.'
Add-Check 'publish_default:safe' (-not $PublishRelease -or $Channel -in @('beta', 'stable')) `
    'Workflow dispatch defaults to publish_release=false; publication requires explicit -PublishRelease.'

$ghArgs = [System.Collections.Generic.List[string]]::new()
foreach ($arg in @(
    'workflow',
    'run',
    $workflowFile,
    '--repo',
    $Repository,
    '--ref',
    $Ref,
    '-f',
    "channel=$Channel",
    '-f',
    "version=$Version",
    '-f',
    "release_tag=$ReleaseTag",
    '-f',
    ("publish_release={0}" -f ($(if ($PublishRelease) { 'true' } else { 'false' })))
)) {
    $ghArgs.Add($arg) | Out-Null
}

if ($DryRun) {
    Add-Check 'dispatch:dry_run' $true 'Dry-run only; workflow was not dispatched.' 'warning'
} else {
    if (-not $SkipSetupPreflight) {
        Add-Check 'setup_preflight:file' (Test-Path -LiteralPath $setupPreflight -PathType Leaf) `
            'GitHub setup preflight script must exist before dispatch.'
        if (Test-Path -LiteralPath $setupPreflight -PathType Leaf) {
            $preflightArgs = @(
                '-NoProfile',
                '-NonInteractive',
                '-ExecutionPolicy',
                'Bypass',
                '-File',
                $setupPreflight,
                '-Repository',
                $Repository,
                '-AsJson'
            )
            $preflightExit = Invoke-CapturedCommand -Name 'github_setup_preflight' -FilePath (Resolve-PowerShellHost) -Arguments $preflightArgs
            Add-Check 'setup_preflight:passed' ($preflightExit -eq 0) `
                'GitHub setup preflight must pass before workflow dispatch.'
        }
    } else {
        Add-Check 'setup_preflight:skipped' $true 'Setup preflight was skipped by explicit request.' 'warning'
    }

    $gh = Resolve-Tool 'gh'
    Add-Check 'gh:available' ($null -ne $gh) 'GitHub CLI must be installed and on PATH for workflow dispatch.'
    if ($gh) {
        $dispatchExit = Invoke-CapturedCommand -Name 'gh_workflow_dispatch' -FilePath $gh -Arguments $ghArgs.ToArray()
        Add-Check 'dispatch:submitted' ($dispatchExit -eq 0) `
            'GitHub Actions private beta workflow dispatch must submit successfully.'
        if ($dispatchExit -eq 0) {
            $listArgs = @(
                'run',
                'list',
                '--repo',
                $Repository,
                '--workflow',
                $workflowFile,
                '--limit',
                '1'
            )
            [void](Invoke-CapturedCommand -Name 'gh_run_list_latest' -FilePath $gh -Arguments $listArgs)
        }
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_workflow_dispatch.v1'
    ok = ($errorCount -eq 0)
    dry_run = [bool]$DryRun
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    ref = $Ref
    publish_release = [bool]$PublishRelease
    workflow = $workflowFile
    gh_args = @($ghArgs)
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
    commands = @($commands)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        if ($DryRun) {
            Write-Host "Private beta workflow dispatch dry-run passed for $Repository."
        } else {
            Write-Host "Private beta workflow dispatch submitted for $Repository."
        }
    } else {
        Write-Host "Private beta workflow dispatch failed for $Repository."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
    if ($DryRun) {
        Write-Host ("Dry-run gh args: gh {0}" -f ($ghArgs -join ' '))
    }
}

if (-not $result.ok) {
    exit 1
}
