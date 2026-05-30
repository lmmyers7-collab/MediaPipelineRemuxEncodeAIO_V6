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
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    if ($exitCode -ne 0) {
        throw "$Label failed with exit $exitCode."
    }
}

function Invoke-ArchitectureGuardrails {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
    $guardScript = Join-Path $repoRoot 'scripts\dev\check_architecture_guardrails.py'
    if (-not (Test-Path -LiteralPath $guardScript -PathType Leaf)) {
        throw "architecture guardrails script is missing: $guardScript"
    }

    $pythonCandidates = @(
        (Join-Path $repoRoot 'DesktopApp\Runtime\Python\python.exe'),
        (Get-Command python.exe -ErrorAction SilentlyContinue).Source,
        (Get-Command python -ErrorAction SilentlyContinue).Source
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -Unique

    if (-not $pythonCandidates -or $pythonCandidates.Count -eq 0) {
        throw "architecture guardrails require Python. Expected bundled runtime at DesktopApp\Runtime\Python\python.exe."
    }

    Write-Host 'Running architecture guardrails...'
    & $pythonCandidates[0] $guardScript
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

Write-Host 'Running active V6 reliability regression checks.'
Invoke-ArchitectureGuardrails
Invoke-RequiredReliabilityScript -RelativePath 'Invoke-V6WebViewReliabilityChecks.ps1' -Label 'V6 WebView/backend reliability gate'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-ContractSchemaChecks.ps1' -Label 'contract schema checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-ConfigKeyRegistryChecks.ps1' -Label 'config-key registry checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-FailureCodeRegistryChecks.ps1' -Label 'failure-code registry checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PipelineProcessingPreflightChecks.ps1' -Label 'pipeline processing preflight checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-SubtitleBuilderDecisionChecks.ps1' -Label 'subtitle builder decision checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PendingPublishSafetyChecks.ps1' -Label 'pending publish safety checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PendingPublishOwnershipChecks.ps1' -Label 'pending publish ownership checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-PortablePathChecks.ps1' -Label 'portable path checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-RepoHygieneChecks.ps1' -Label 'repo hygiene checks'
Invoke-RequiredReliabilityScript -RelativePath 'Unit\Invoke-ActiveDocsReferenceChecks.ps1' -Label 'active docs reference checks'

Write-Host 'Active V6 reliability regression checks passed.'
