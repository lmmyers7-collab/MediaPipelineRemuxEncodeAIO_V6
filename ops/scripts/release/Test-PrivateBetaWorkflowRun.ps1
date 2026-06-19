[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$Version = $(if ($env:MEDIAPIPELINE_SEMVER_VERSION) { $env:MEDIAPIPELINE_SEMVER_VERSION } else { '2026.6.4+001' }),

    [string]$ReleaseTag,

    [string]$RunId,

    [string]$RunJsonPath,

    [string]$ArtifactsJsonPath,

    [switch]$SkipArtifactCheck,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$workflowFile = 'private-beta-windows.yml'

if (-not $ReleaseTag) {
    $ReleaseTag = "app-v$Version"
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
    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Stdout = $stdout
        Stderr = $stderr
    }
}

function Read-WorkflowRunJson {
    if ($RunJsonPath) {
        Add-Check 'run_json:file' (Test-Path -LiteralPath $RunJsonPath -PathType Leaf) `
            'Saved GitHub Actions workflow-run JSON fixture must exist.'
        if (-not (Test-Path -LiteralPath $RunJsonPath -PathType Leaf)) {
            return $null
        }
        return Get-Content -LiteralPath $RunJsonPath -Raw
    }

    $gh = Resolve-Tool 'gh'
    Add-Check 'gh:available' ($null -ne $gh) `
        'GitHub CLI must be installed and on PATH when -RunJsonPath is not provided.'
    if (-not $gh) {
        return $null
    }

    if ($RunId) {
        $api = Invoke-CapturedCommand -Name 'gh_workflow_run_by_id' -FilePath $gh -Arguments @(
            'api',
            "repos/$Repository/actions/runs/$RunId"
        )
        Add-Check 'github:run_json' ($api.ExitCode -eq 0) `
            'GitHub Actions workflow run metadata must be readable through gh api.'
        if ($api.ExitCode -ne 0) {
            return $null
        }
        return $api.Stdout
    }

    $listApi = Invoke-CapturedCommand -Name 'gh_latest_workflow_run' -FilePath $gh -Arguments @(
        'api',
        "repos/$Repository/actions/workflows/$workflowFile/runs?event=workflow_dispatch&per_page=1"
    )
    Add-Check 'github:latest_run_json' ($listApi.ExitCode -eq 0) `
        'Latest private beta workflow run metadata must be readable through gh api.'
    if ($listApi.ExitCode -ne 0) {
        return $null
    }
    try {
        $listPayload = $listApi.Stdout | ConvertFrom-Json -Depth 20
        $runs = @($listPayload.workflow_runs)
        Add-Check 'github:latest_run_present' ($runs.Count -gt 0) `
            'At least one workflow_dispatch private beta run must exist.'
        if ($runs.Count -eq 0) {
            return $null
        }
        return ($runs[0] | ConvertTo-Json -Depth 20)
    } catch {
        Add-Check 'github:latest_run_parse' $false "Latest workflow run list could not be parsed: $($_.Exception.Message)"
        return $null
    }
}

function Read-WorkflowArtifactsJson {
    param([string]$WorkflowRunId)

    if ($SkipArtifactCheck) {
        Add-Check 'artifacts:skipped' $true 'Workflow artifact verification was skipped by explicit request.' 'warning'
        return $null
    }

    if ($ArtifactsJsonPath) {
        Add-Check 'artifacts_json:file' (Test-Path -LiteralPath $ArtifactsJsonPath -PathType Leaf) `
            'Saved GitHub Actions workflow artifacts JSON fixture must exist.'
        if (-not (Test-Path -LiteralPath $ArtifactsJsonPath -PathType Leaf)) {
            return $null
        }
        return Get-Content -LiteralPath $ArtifactsJsonPath -Raw
    }

    Add-Check 'artifacts:run_id' (-not [string]::IsNullOrWhiteSpace($WorkflowRunId)) `
        'Workflow run id is required to verify uploaded workflow artifacts.'
    if ([string]::IsNullOrWhiteSpace($WorkflowRunId)) {
        return $null
    }

    $gh = Resolve-Tool 'gh'
    Add-Check 'artifacts:gh_available' ($null -ne $gh) `
        'GitHub CLI must be installed and on PATH when -ArtifactsJsonPath is not provided.'
    if (-not $gh) {
        return $null
    }

    $api = Invoke-CapturedCommand -Name 'gh_workflow_run_artifacts' -FilePath $gh -Arguments @(
        'api',
        "repos/$Repository/actions/runs/$WorkflowRunId/artifacts"
    )
    Add-Check 'github:artifacts_json' ($api.ExitCode -eq 0) `
        'GitHub Actions workflow artifacts metadata must be readable through gh api.'
    if ($api.ExitCode -ne 0) {
        return $null
    }
    return $api.Stdout
}

Add-Check 'repository:format' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo.'
Add-Check 'version:format' ($Version -match '^\d+\.\d+\.\d+\+\d+$') `
    'Version must be Tauri-compatible semver with build metadata, for example 2026.6.4+001.'
Add-Check 'release_tag:format' ($ReleaseTag -match '^app-v\d+\.\d+\.\d+\+\d+$') `
    'Release tag must use app-v<version>.'

$runPayload = $null
$runJson = Read-WorkflowRunJson
if ($runJson) {
    try {
        $runPayload = $runJson | ConvertFrom-Json -Depth 20
        Add-Check 'run_json:parse' $true 'GitHub Actions workflow-run JSON parsed.'
    } catch {
        Add-Check 'run_json:parse' $false "GitHub Actions workflow-run JSON could not be parsed: $($_.Exception.Message)"
    }
}

$runIdValue = $null
$runStatus = $null
$runConclusion = $null
$artifactNames = @()
if ($runPayload) {
    $runIdValue = [string]$runPayload.id
    if ([string]::IsNullOrWhiteSpace($runIdValue)) {
        $runIdValue = [string]$runPayload.databaseId
    }
    $runStatus = [string]$runPayload.status
    $runConclusion = [string]$runPayload.conclusion
    $event = [string]$runPayload.event
    $workflowName = [string]$runPayload.name
    if ([string]::IsNullOrWhiteSpace($workflowName)) {
        $workflowName = [string]$runPayload.workflowName
    }
    $path = [string]$runPayload.path
    $displayTitle = [string]$runPayload.display_title
    if ([string]::IsNullOrWhiteSpace($displayTitle)) {
        $displayTitle = [string]$runPayload.displayTitle
    }

    Add-Check 'run:id' (-not [string]::IsNullOrWhiteSpace($runIdValue)) `
        'Workflow run metadata must include an id.'
    Add-Check 'run:event' ($event -eq 'workflow_dispatch') `
        'Private beta release workflow run must be a manual workflow_dispatch run.'
    Add-Check 'run:status_completed' ($runStatus -eq 'completed') `
        'Private beta release workflow run must be completed before artifact or release verification.'
    Add-Check 'run:conclusion_success' ($runConclusion -eq 'success') `
        'Private beta release workflow run must conclude successfully.'
    Add-Check 'run:workflow_name' ($workflowName -eq 'Private Beta Windows Installer' -or [string]::IsNullOrWhiteSpace($workflowName)) `
        'Workflow run should be for the Private Beta Windows Installer workflow.' 'warning'
    Add-Check 'run:workflow_path' ($path -eq ".github/workflows/$workflowFile" -or [string]::IsNullOrWhiteSpace($path)) `
        'Workflow run should come from .github/workflows/private-beta-windows.yml.' 'warning'
    Add-Check 'run:html_url' (-not [string]::IsNullOrWhiteSpace([string]$runPayload.html_url) -or -not [string]::IsNullOrWhiteSpace([string]$runPayload.url)) `
        'Workflow run metadata should include a GitHub URL for audit evidence.' 'warning'
    if (-not [string]::IsNullOrWhiteSpace($displayTitle)) {
        Add-Check 'run:display_title_version' ($displayTitle -match [regex]::Escape($Version) -or $displayTitle -match [regex]::Escape($ReleaseTag)) `
            'Workflow display title should include the version or release tag when available.' 'warning'
    }
}

$artifactsPayload = $null
$artifactsJson = Read-WorkflowArtifactsJson -WorkflowRunId $runIdValue
if ($artifactsJson) {
    try {
        $artifactsPayload = $artifactsJson | ConvertFrom-Json -Depth 20
        Add-Check 'artifacts_json:parse' $true 'GitHub Actions workflow artifacts JSON parsed.'
    } catch {
        Add-Check 'artifacts_json:parse' $false "GitHub Actions workflow artifacts JSON could not be parsed: $($_.Exception.Message)"
    }
}

if ($artifactsPayload) {
    $artifacts = @($artifactsPayload.artifacts)
    if ($artifacts.Count -eq 0 -and $artifactsPayload -is [array]) {
        $artifacts = @($artifactsPayload)
    }
    $artifactNames = @($artifacts | ForEach-Object { [string]$_.name })
    $expectedArtifactName = "mediapipeline-$Channel-windows-x64"
    $matchingArtifacts = @($artifacts | Where-Object { [string]$_.name -eq $expectedArtifactName })
    Add-Check 'artifacts:expected_name' ($matchingArtifacts.Count -eq 1) `
        "Workflow run must upload exactly one $expectedArtifactName artifact."
    if ($matchingArtifacts.Count -eq 1) {
        Add-Check 'artifacts:not_expired' (-not [bool]$matchingArtifacts[0].expired) `
            'Workflow artifact must not be expired before installer validation or publication.'
        $size = [int64]($matchingArtifacts[0].size_in_bytes)
        Add-Check 'artifacts:size' ($size -gt 0) `
            'Workflow artifact size must be greater than zero.' 'warning'
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomObject][ordered]@{
    schema_version = 'private_beta_workflow_run_verification.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    run_id = $runIdValue
    run_status = $runStatus
    run_conclusion = $runConclusion
    artifact_names = @($artifactNames)
    skip_artifact_check = [bool]$SkipArtifactCheck
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
    commands = @($commands)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta workflow run verification passed for $Repository $ReleaseTag."
    } else {
        Write-Host "Private beta workflow run verification failed for $Repository $ReleaseTag."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
