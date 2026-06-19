[CmdletBinding()]
param(
    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$WorkflowPath,

    [switch]$StaticOnly,

    [switch]$SkipGhApi,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
if (-not $WorkflowPath) {
    $WorkflowPath = Join-Path $repoRoot '.github\workflows\private-beta-windows.yml'
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
        stdout_tail = if ($stdout.Length -gt 2000) { $stdout.Substring($stdout.Length - 2000) } else { $stdout }
        stderr_tail = if ($stderr.Length -gt 2000) { $stderr.Substring($stderr.Length - 2000) } else { $stderr }
    }) | Out-Null
    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Stdout = $stdout
        Stderr = $stderr
    }
}

function ConvertFrom-GitHubRemote {
    param([string]$RemoteUrl)
    if ([string]::IsNullOrWhiteSpace($RemoteUrl)) {
        return $null
    }
    $trimmed = $RemoteUrl.Trim()
    if ($trimmed -match '^https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$') {
        return "$($Matches[1])/$($Matches[2])"
    }
    if ($trimmed -match '^git@github\.com:([^/\s]+)/([^/\s]+?)(?:\.git)?$') {
        return "$($Matches[1])/$($Matches[2])"
    }
    return $null
}

$git = Resolve-Tool 'git'
Add-Check 'git:available' ($null -ne $git) 'Git must be available to inspect the release checkout remote.'

$remoteUrl = $null
$remoteRepository = $null
if ($git) {
    $origin = Invoke-CapturedCommand -Name 'git_remote_origin' -FilePath $git -Arguments @('remote', 'get-url', 'origin')
    if ($origin.ExitCode -eq 0) {
        $remoteUrl = $origin.Stdout.Trim()
    } else {
        $remotes = Invoke-CapturedCommand -Name 'git_remote_list' -FilePath $git -Arguments @('remote', '-v')
        if ($remotes.ExitCode -eq 0) {
            $firstRemote = ($remotes.Stdout -split "`r?`n" | Where-Object { $_ -match '\(fetch\)' } | Select-Object -First 1)
            if ($firstRemote -match '^\S+\s+(\S+)\s+\(fetch\)$') {
                $remoteUrl = $Matches[1]
            }
        }
    }
    $remoteRepository = ConvertFrom-GitHubRemote -RemoteUrl $remoteUrl
}

if (-not $Repository -and $remoteRepository) {
    $Repository = $remoteRepository
}

Add-Check 'git:github_remote' ($null -ne $remoteRepository) `
    'A GitHub remote must be configured, for example origin https://github.com/owner/repo.git.' `
    $(if ($StaticOnly) { 'warning' } else { 'error' })
Add-Check 'repository:format' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo.'
if ($remoteRepository -and $Repository) {
    Add-Check 'repository:matches_remote' ($Repository -eq $remoteRepository) `
        'Repository input must match the configured GitHub remote.'
}

Add-Check 'workflow:file' (Test-Path -LiteralPath $WorkflowPath -PathType Leaf) `
    'Private beta workflow file must exist.'
if (Test-Path -LiteralPath $WorkflowPath -PathType Leaf) {
    $workflow = Get-Content -LiteralPath $WorkflowPath -Raw
    Add-Check 'workflow:dispatch' ($workflow -match 'workflow_dispatch') `
        'Private beta workflow must be manually dispatchable.'
    Add-Check 'workflow:publish_input' ($workflow -match 'publish_release') `
        'Private beta workflow must expose publish_release input.'
    Add-Check 'workflow:channel_environment' ($workflow -match 'environment:\s*\$\{\{\s*inputs\.channel\s*\}\}-release') `
        'Private beta workflow must use channel-scoped environments beta-release and stable-release.'
    foreach ($secretName in @(
        'TAURI_SIGNING_PRIVATE_KEY',
        'TAURI_UPDATER_PUBLIC_KEY',
        'WINDOWS_CERTIFICATE_BASE64',
        'WINDOWS_CERTIFICATE_PASSWORD'
    )) {
        Add-Check "workflow:secret:$secretName" ($workflow -match [regex]::Escape("secrets.$secretName")) `
            "Workflow must reference protected secret $secretName."
    }
    Add-Check 'workflow:preflight' ($workflow -match 'Test-PrivateBetaReleasePreflight\.ps1') `
        'Workflow must run the private beta release preflight.'
    Add-Check 'workflow:artifact_verifier' ($workflow -match 'Test-PrivateBetaReleaseArtifact\.ps1') `
        'Workflow must verify release artifacts before upload.'
}

$gh = Resolve-Tool 'gh'
if ($StaticOnly) {
    Add-Check 'gh:static_only' $true 'GitHub CLI checks were skipped by -StaticOnly.' 'warning'
} else {
    Add-Check 'gh:available' ($null -ne $gh) 'GitHub CLI must be installed and on PATH for workflow dispatch.'
    if ($gh) {
        $auth = Invoke-CapturedCommand -Name 'gh_auth_status' -FilePath $gh -Arguments @('auth', 'status')
        Add-Check 'gh:authenticated' ($auth.ExitCode -eq 0) 'GitHub CLI must be authenticated.'
        if ($auth.ExitCode -eq 0 -and -not $SkipGhApi -and $Repository -match '^[^/\s]+/[^/\s]+$') {
            $workflowApi = Invoke-CapturedCommand -Name 'gh_workflow_api' -FilePath $gh -Arguments @('api', "repos/$Repository/actions/workflows/private-beta-windows.yml")
            Add-Check 'github:workflow_exists' ($workflowApi.ExitCode -eq 0) `
                'GitHub must see .github/workflows/private-beta-windows.yml after push.'
            foreach ($environment in @('beta-release', 'stable-release')) {
                $envApi = Invoke-CapturedCommand -Name "gh_environment_$environment" -FilePath $gh -Arguments @('api', "repos/$Repository/environments/$environment")
                Add-Check "github:environment:$environment" ($envApi.ExitCode -eq 0) `
                    "GitHub environment must exist: $environment."
            }
        } elseif ($SkipGhApi) {
            Add-Check 'github:api_skipped' $true 'GitHub API environment checks were skipped by -SkipGhApi.' 'warning'
        }
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_github_setup_preflight.v1'
    ok = ($errorCount -eq 0)
    repository = $Repository
    remote_url = $remoteUrl
    remote_repository = $remoteRepository
    static_only = [bool]$StaticOnly
    skip_gh_api = [bool]$SkipGhApi
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
    commands = @($commands)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta GitHub setup preflight passed for $Repository."
    } else {
        Write-Host "Private beta GitHub setup preflight failed for $Repository."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
