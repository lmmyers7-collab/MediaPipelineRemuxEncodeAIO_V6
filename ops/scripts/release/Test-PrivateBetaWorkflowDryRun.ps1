[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $(if ($env:GITHUB_REPOSITORY) { $env:GITHUB_REPOSITORY } else { 'owner/repo' }),

    [string]$Version = $(if ($env:MEDIAPIPELINE_SEMVER_VERSION) { $env:MEDIAPIPELINE_SEMVER_VERSION } else { '2026.6.4+001' }),

    [string]$ReleaseTag,

    [switch]$SkipPythonTests,

    [switch]$SkipTauriCheck,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$preflightScript = Join-Path $repoRoot 'ops\scripts\release\Test-PrivateBetaReleasePreflight.ps1'
$pythonExe = Join-Path $repoRoot 'apps\desktop\runtime\Python\python.exe'
$tauriRoot = Join-Path $repoRoot 'apps\desktop\tauri'

if (-not $ReleaseTag) {
    $ReleaseTag = "app-v$Version"
}

$checks = [System.Collections.Generic.List[object]]::new()
$commands = [System.Collections.Generic.List[object]]::new()
$placeholderSecrets = [System.Collections.Generic.List[string]]::new()

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

function Set-PlaceholderEnv {
    param(
        [string]$Name,
        [string]$Value
    )
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name))) {
        [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
        $placeholderSecrets.Add($Name) | Out-Null
    }
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
        stdout_tail = if ($stdout.Length -gt 4000) { $stdout.Substring($stdout.Length - 4000) } else { $stdout }
        stderr_tail = if ($stderr.Length -gt 4000) { $stderr.Substring($stderr.Length - 4000) } else { $stderr }
    }) | Out-Null
    return $process.ExitCode
}

function Resolve-PowerShellHost {
    $current = (Get-Process -Id $PID).Path
    if ($current -and (Test-Path -LiteralPath $current -PathType Leaf)) {
        return $current
    }
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($pwsh -and $pwsh.Source) {
        return $pwsh.Source
    }
    $windowsPowerShell = Get-Command powershell -ErrorAction SilentlyContinue
    if ($windowsPowerShell -and $windowsPowerShell.Source) {
        return $windowsPowerShell.Source
    }
    throw 'No PowerShell host could be resolved for the dry-run preflight.'
}

function Resolve-Tool {
    param([string]$Name)
    $cmdCommand = Get-Command "$Name.cmd" -ErrorAction SilentlyContinue
    if ($cmdCommand -and $cmdCommand.Source) {
        return $cmdCommand.Source
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command -and $command.Source) {
        if ([System.IO.Path]::GetExtension($command.Source) -ieq '.ps1') {
            $siblingCmd = [System.IO.Path]::ChangeExtension($command.Source, '.cmd')
            if (Test-Path -LiteralPath $siblingCmd -PathType Leaf) {
                return $siblingCmd
            }
        }
        return $command.Source
    }
    throw "Required command not found on PATH: $Name"
}

Set-PlaceholderEnv 'TAURI_SIGNING_PRIVATE_KEY' 'local-dry-run-placeholder-private-updater-key'
Set-PlaceholderEnv 'TAURI_SIGNING_PRIVATE_KEY_PASSWORD' 'local-dry-run-placeholder-private-updater-key-password'
Set-PlaceholderEnv 'TAURI_UPDATER_PUBLIC_KEY' 'local-dry-run-placeholder-public-updater-key'
Set-PlaceholderEnv 'WINDOWS_CERTIFICATE_BASE64' 'bG9jYWwtZHJ5LXJ1bi1wbGFjZWhvbGRlci1jZXJ0'
Set-PlaceholderEnv 'WINDOWS_CERTIFICATE_PASSWORD' 'local-dry-run-placeholder-certificate-password'
Set-PlaceholderEnv 'WINDOWS_CERTIFICATE_THUMBPRINT' '0123456789ABCDEF0123456789ABCDEF01234567'
Set-PlaceholderEnv 'GITHUB_REPOSITORY' $Repository
Set-PlaceholderEnv 'MEDIAPIPELINE_RELEASE_CHANNEL' $Channel
Set-PlaceholderEnv 'MEDIAPIPELINE_SEMVER_VERSION' $Version

Add-Check 'placeholder_secrets:local_only' ($placeholderSecrets.Count -ge 0) `
    'Placeholder release secrets are local dry-run values only and do not prove GitHub protected secrets exist.' 'warning'
Add-Check 'preflight_script' (Test-Path -LiteralPath $preflightScript -PathType Leaf) `
    'Private beta preflight script must exist.'
Add-Check 'python_runtime' (Test-Path -LiteralPath $pythonExe -PathType Leaf) `
    'Bundled Python runtime must exist for scoped release tests.'
Add-Check 'tauri_root' (Test-Path -LiteralPath $tauriRoot -PathType Container) `
    'Tauri app root must exist for cargo check.'

$tempConfigPath = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-tauri-{0}-workflow-dry-run.conf.json" -f $Channel)
if (Test-Path -LiteralPath $preflightScript -PathType Leaf) {
    $preflightArgs = @(
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $preflightScript,
        '-Channel',
        $Channel,
        '-Repository',
        $Repository,
        '-Version',
        $Version,
        '-ReleaseTag',
        $ReleaseTag,
        '-ConfigOutputPath',
        $tempConfigPath,
        '-AsJson'
    )
    $preflightExit = Invoke-CapturedCommand -Name 'private_beta_preflight' -FilePath (Resolve-PowerShellHost) -Arguments $preflightArgs
    Add-Check 'preflight:passed' ($preflightExit -eq 0) `
        'Private beta preflight must pass with local dry-run placeholder release inputs.'
}

if ($SkipPythonTests) {
    Add-Check 'python_tests:skipped' $true 'Scoped Python release/productization tests were skipped by request.' 'warning'
} elseif (Test-Path -LiteralPath $pythonExe -PathType Leaf) {
    $testArgs = @(
        '-m',
        'pytest',
        'tests\python\tooling\test_private_beta_release_artifact.py',
        'tests\python\tooling\test_private_beta_release_preflight.py',
        'tests\python\desktop\test_productization_support.py',
        'tests\python\desktop\test_tauri_shell_scaffold.py',
        '-q'
    )
    $env:PYTHONPATH = 'src'
    $pythonExit = Invoke-CapturedCommand -Name 'scoped_release_productization_tests' -FilePath $pythonExe -Arguments $testArgs
    Add-Check 'python_tests:passed' ($pythonExit -eq 0) `
        'Scoped private beta release/productization tests must pass.'
}

if ($SkipTauriCheck) {
    Add-Check 'tauri_check:skipped' $true 'Tauri cargo check was skipped by request.' 'warning'
} elseif (Test-Path -LiteralPath $tauriRoot -PathType Container) {
    $npmExit = Invoke-CapturedCommand -Name 'tauri_npm_check' -FilePath (Resolve-Tool 'npm') -Arguments @('run', 'check') -WorkingDirectory $tauriRoot
    Add-Check 'tauri_check:passed' ($npmExit -eq 0) `
        'npm run check in apps/desktop/tauri must pass.'
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_workflow_dry_run.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    used_placeholder_secrets = @($placeholderSecrets)
    warning_count = $warningCount
    error_count = $errorCount
    checks = @($checks)
    commands = @($commands)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta workflow dry-run passed for $Channel $Version."
    } else {
        Write-Host "Private beta workflow dry-run failed for $Channel $Version."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
