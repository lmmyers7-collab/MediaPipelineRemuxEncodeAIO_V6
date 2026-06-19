[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSScriptRoot."
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\routing.ps1')

function Assert-Equal {
    param(
        [Parameter(Mandatory)] $Actual,
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory)] [bool] $Condition,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-size-guard-inspection-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $sourcePath = Join-Path $root 'source.bin'
    $outputPath = Join-Path $root 'output.bin'
    [System.IO.File]::WriteAllBytes($sourcePath, [byte[]](0..99))
    [System.IO.File]::WriteAllBytes($outputPath, [byte[]](0..109))

    $strictMissingPath = Test-MediaEncodeOutputSizePolicy `
        -SourcePath (Join-Path $root 'missing-source.bin') `
        -OutputPath $outputPath `
        -SizeGuardMode 'strict' `
        -MaxGrowthPercent 5 `
        -CompatibilityGrowthPercent 15
    Assert-Equal ([bool]$strictMissingPath.Ok) $false 'Strict size guard must block when source or output path is unavailable.'
    Assert-Equal ([bool]$strictMissingPath.ShouldBlock) $true 'Strict missing-path inspection failure should use block semantics.'
    Assert-Equal ([string]$strictMissingPath.Severity) 'error' 'Strict missing-path inspection failure should be an error.'
    Assert-True ([string]$strictMissingPath.Message -match 'could not verify') 'Strict missing-path message should say the guard could not verify.'

    $fallbackMissingPath = Test-MediaEncodeOutputSizePolicy `
        -SourcePath $sourcePath `
        -OutputPath (Join-Path $root 'missing-output.bin') `
        -SizeGuardMode 'fallback_remux' `
        -MaxGrowthPercent 5 `
        -CompatibilityGrowthPercent 15 `
        -RouteReasonCode 'size_over_threshold'
    Assert-Equal ([bool]$fallbackMissingPath.Ok) $false 'Fallback-remux size guard must block when inspection cannot verify output size.'
    Assert-Equal ([bool]$fallbackMissingPath.ShouldBlock) $true 'Fallback-remux inspection failure should block publish.'
    Assert-Equal ([bool]$fallbackMissingPath.ShouldFallbackRemux) $false 'Fallback-remux inspection failure must not attempt a blind remux fallback.'
    Assert-Equal ([string]$fallbackMissingPath.Severity) 'error' 'Fallback-remux inspection failure should be an error.'

    $zeroOutputPath = Join-Path $root 'zero-output.bin'
    [System.IO.File]::WriteAllBytes($zeroOutputPath, [byte[]]@())
    $strictZeroOutput = Test-MediaEncodeOutputSizePolicy `
        -SourcePath $sourcePath `
        -OutputPath $zeroOutputPath `
        -SizeGuardMode 'strict' `
        -MaxGrowthPercent 5 `
        -CompatibilityGrowthPercent 15
    Assert-Equal ([bool]$strictZeroOutput.Ok) $false 'Strict size guard must block zero-byte output inspection failures.'
    Assert-Equal ([bool]$strictZeroOutput.ShouldBlock) $true 'Strict zero-byte output should block publish.'

    $advisoryMissingPath = Test-MediaEncodeOutputSizePolicy `
        -SourcePath (Join-Path $root 'missing-advisory-source.bin') `
        -OutputPath $outputPath `
        -SizeGuardMode 'advisory' `
        -MaxGrowthPercent 5 `
        -CompatibilityGrowthPercent 15
    Assert-Equal ([bool]$advisoryMissingPath.Ok) $true 'Advisory size guard should remain warning-only on inspection failure.'
    Assert-Equal ([bool]$advisoryMissingPath.ShouldBlock) $false 'Advisory inspection failure must not block publish.'
    Assert-Equal ([string]$advisoryMissingPath.Severity) 'warn' 'Advisory inspection failure should stay warn severity.'

    $eligibleWasteGuard = Test-MediaEncodeWasteGuardEligibility `
        -WasteGuardMode 'enforce' `
        -SizeGuardMode 'fallback_remux' `
        -RouteReasonCode 'size_over_threshold' `
        -RouteIntentReasonCode 'size_over_threshold' `
        -UseCpuFallback:$false
    Assert-Equal ([bool]$eligibleWasteGuard.Eligible) $true 'Waste guard should be eligible only for automatic fallback-remux threshold encodes.'
    Assert-Equal ([bool]$eligibleWasteGuard.Enforce) $true 'Waste guard enforce mode should mark decisions as enforceable.'
    Assert-Equal ([string]$eligibleWasteGuard.Reason) 'eligible' 'Eligible waste guard should use the eligible reason.'

    $forcedWasteGuard = Test-MediaEncodeWasteGuardEligibility `
        -WasteGuardMode 'enforce' `
        -SizeGuardMode 'fallback_remux' `
        -RouteReasonCode 'folder_policy_force_encode' `
        -RouteIntentReasonCode 'folder_policy_force_encode' `
        -UseCpuFallback:$false
    Assert-Equal ([bool]$forcedWasteGuard.Eligible) $false 'Waste guard must not override explicit forced encode decisions.'
    Assert-Equal ([string]$forcedWasteGuard.Reason) 'forced_route_override' 'Forced encode decisions should retain a specific ineligible reason.'

    $cpuWasteGuard = Test-MediaEncodeWasteGuardEligibility `
        -WasteGuardMode 'enforce' `
        -SizeGuardMode 'fallback_remux' `
        -RouteReasonCode 'size_over_threshold' `
        -RouteIntentReasonCode 'size_over_threshold' `
        -UseCpuFallback:$true
    Assert-Equal ([bool]$cpuWasteGuard.Eligible) $false 'Waste guard should not abort CPU fallback encodes.'
    Assert-Equal ([string]$cpuWasteGuard.Reason) 'cpu_encode_not_guarded' 'CPU fallback ineligibility should be explicit.'

    $projection = Measure-MediaEncodeWasteGuardProjection `
        -SourceSizeBytes 1000 `
        -OutputSizeBytes 700 `
        -ProgressPercent 25 `
        -LimitRatio 1.05 `
        -OversizeMarginPercent 20 `
        -MinProgressPercent 15 `
        -ElapsedSeconds 180 `
        -MinElapsedSeconds 120 `
        -PreviousConsecutiveHits 1 `
        -ConsecutiveSamples 2
    Assert-Equal ([bool]$projection.ShouldAbort) $true 'Projection should abort after enough consecutive oversized samples.'
    Assert-Equal ([int]$projection.ConsecutiveHits) 2 'Projection should increment consecutive oversized samples.'
    Assert-True ([double]$projection.ProjectedOutputBytes -gt [double]$projection.AbortThresholdBytes) 'Projected output should exceed abort threshold.'

    $earlyProjection = Measure-MediaEncodeWasteGuardProjection `
        -SourceSizeBytes 1000 `
        -OutputSizeBytes 700 `
        -ProgressPercent 5 `
        -LimitRatio 1.05 `
        -OversizeMarginPercent 20 `
        -MinProgressPercent 15 `
        -ElapsedSeconds 180 `
        -MinElapsedSeconds 120 `
        -PreviousConsecutiveHits 1 `
        -ConsecutiveSamples 2
    Assert-Equal ([bool]$earlyProjection.ShouldAbort) $false 'Projection should wait for the minimum progress floor before aborting.'
    Assert-Equal ([string]$earlyProjection.Reason) 'below_min_progress' 'Early projections should carry a below-min-progress reason.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Encode size guard inspection checks passed.'
