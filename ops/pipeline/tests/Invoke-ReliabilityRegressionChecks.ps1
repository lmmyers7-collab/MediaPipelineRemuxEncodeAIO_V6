[CmdletBinding()]
param(
    [switch]$RunLegacyDesktopChecks
)

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Reliability regression checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$testsRoot = [System.IO.Path]::GetFullPath($testsRoot)

function Invoke-RequiredReliabilityScript {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $scriptPath = Join-Path $testsRoot $RelativePath
    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
        throw "$Label is missing: $scriptPath"
    }

    Write-Host "Running $Label..."
    & $scriptPath
    $invocationSucceeded = $?
    if (-not $invocationSucceeded) {
        throw "$Label reported an unsuccessful PowerShell invocation."
    }
}

function Invoke-ArchitectureGuardrails {
    $repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $testsRoot))
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
        throw "reliability regression checks resolved an invalid repo root: $repoRoot"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
        throw "reliability regression checks resolved a repo root without ops\pipeline\engine: $repoRoot"
    }
    $toolRunner = Join-Path $repoRoot 'ops\scripts\dev\run-python-tool.py'
    if (-not (Test-Path -LiteralPath $toolRunner -PathType Leaf)) {
        throw "python tool runner is missing: $toolRunner"
    }

    $pythonCandidates = @(
        (Join-Path $repoRoot 'apps\desktop\runtime\Python\python.exe'),
        (Get-Command python.exe -ErrorAction SilentlyContinue).Source,
        (Get-Command python -ErrorAction SilentlyContinue).Source
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique

    if (-not $pythonCandidates -or $pythonCandidates.Count -eq 0) {
        throw "architecture guardrails require Python. Expected bundled runtime at apps\desktop\runtime\Python\python.exe."
    }

    Write-Host 'Running architecture guardrails...'
    & $pythonCandidates[0] $toolRunner mediapipeline.tools.dev.check_architecture_guardrails
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    if ($exitCode -ne 0) {
        throw "architecture guardrails failed with exit $exitCode."
    }
}

if ($RunLegacyDesktopChecks) {
    Invoke-RequiredReliabilityScript `
        -RelativePath 'Legacy\Invoke-LegacyDesktopReliabilityRegressionChecks.ps1' `
        -Label 'archived legacy desktop-shell reliability checks'
    exit 0
}

Write-Host 'Running active reliability regression checks.'
Invoke-ArchitectureGuardrails
Invoke-RequiredReliabilityScript -RelativePath 'Invoke-WebViewReliabilityChecks.ps1' -Label 'current WebView/backend reliability gate'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-ContractSchemaChecks.ps1' -Label 'contract schema checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-ConfigKeyRegistryChecks.ps1' -Label 'config-key registry checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-CompletedManifestBackfillDryRunChecks.ps1' -Label 'completed manifest backfill dry-run checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-FailureCodeRegistryChecks.ps1' -Label 'failure-code registry checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-FailureStateIdentityChecks.ps1' -Label 'failure-state identity checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-FFmpegProgressChecks.ps1' -Label 'FFmpeg/mkvmerge progress checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-LoggingJsonLineChecks.ps1' -Label 'logging JSONL lock checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-MediaVerificationSafetyChecks.ps1' -Label 'media verification safety checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-MultiVideoTopologyChecks.ps1' -Label 'multi-video preserve-all topology checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-TdarrContainerStressChecks.ps1' -Label 'Tdarr container stress checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-MediaRouteSelectionChecks.ps1' -Label 'media route selection checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-NamingSupportChecks.ps1' -Label 'naming support checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-LocalWorkerClaimLifecycleChecks.ps1' -Label 'local worker claim lifecycle checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PipelineQueueEngineChecks.ps1' -Label 'pipeline queue engine checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PipelineProcessingPreflightChecks.ps1' -Label 'pipeline processing preflight checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-RerunPlanOnlyChecks.ps1' -Label 'rerun PlanOnly no-write checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-RerunSourceIdentityChecks.ps1' -Label 'rerun source identity checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-SubtitleBuilderDecisionChecks.ps1' -Label 'subtitle builder decision checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-VobSubSubtitleChecks.ps1' -Label 'VobSub subtitle checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PendingPublishSafetyChecks.ps1' -Label 'pending publish safety checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PendingPublishOwnershipChecks.ps1' -Label 'pending publish ownership checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PathBoundaryGuardChecks.ps1' -Label 'path boundary guard checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PortablePathChecks.ps1' -Label 'portable path checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-RepoHygieneChecks.ps1' -Label 'repo hygiene checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-ActiveDocsReferenceChecks.ps1' -Label 'active docs reference checks'

Write-Host 'Active reliability regression checks passed.'
