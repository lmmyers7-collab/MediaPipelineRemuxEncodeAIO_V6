[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Encode publish-order split checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Get-RequiredIndex {
    param([string] $Text, [string] $Needle, [string] $Message)
    $index = $Text.IndexOf($Needle, [System.StringComparison]::Ordinal)
    Assert-True ($index -ge 0) $Message
    return $index
}

$encodePaths = @(
    'ops\pipeline\entrypoints\MediaPipeline\encode.ps1',
    'ops\pipeline\engine\process\encode_context.ps1',
    'ops\pipeline\engine\process\encode_preflight.ps1',
    'ops\pipeline\engine\process\encode_attempt_plan.ps1',
    'ops\pipeline\engine\process\encode_command_builder.ps1',
    'ops\pipeline\engine\process\encode_execution.ps1',
    'ops\pipeline\engine\process\encode_fallback.ps1',
    'ops\pipeline\engine\process\encode_verification.ps1',
    'ops\pipeline\engine\process\encode_size_guard.ps1',
    'ops\pipeline\engine\process\encode_publish.ps1',
    'ops\pipeline\engine\process\encode_orchestrator.ps1'
)
$encodeText = ($encodePaths | ForEach-Object {
        Get-Content -LiteralPath (Join-Path $repoRoot $_) -Raw
    }) -join "`n"

$outputExistsIndex = Get-RequiredIndex $encodeText 'ENCODE output missing or empty after ffmpeg' 'Encode publish-order check must find output existence gate.'
$durationIndex = Get-RequiredIndex $encodeText 'Test-DurationMatch -SourcePath $localIn -OutputPath $tempOut -Label "ENCODE" -AllowAVFallback' 'Encode publish-order check must find duration verification gate.'
$videoIndex = Get-RequiredIndex $encodeText 'Test-OutputVideoStreamPreservation -SourcePath $localIn -OutputPath $tempOut' 'Encode publish-order check must find video-stream preservation gate.'
$qualityIndex = Get-RequiredIndex $encodeText 'Invoke-MediaQualityVerification' 'Encode publish-order check must find quality verification gate.'
$sizeIndex = Get-RequiredIndex $encodeText 'Test-MediaEncodeOutputSizePolicy' 'Encode publish-order check must find size policy gate.'
$publishIndex = Get-RequiredIndex $encodeText 'Complete-PipelineOutputPublish -SourceFile $file' 'Encode publish-order check must find publish handoff.'

Assert-True ($outputExistsIndex -lt $publishIndex) 'Encode publish must remain after output existence/non-empty check.'
Assert-True ($durationIndex -lt $publishIndex) 'Encode publish must remain after duration verification.'
Assert-True ($videoIndex -lt $publishIndex) 'Encode publish must remain after video-stream preservation verification.'
Assert-True ($qualityIndex -lt $publishIndex) 'Encode publish must remain after quality verification handling.'
Assert-True ($sizeIndex -lt $publishIndex) 'Encode publish must remain after size/waste guard handling.'

Assert-True ($encodeText -match '\$route\s*=\s*if \(\$usingCpu\) \{ "encode-cpu-fallback" \} elseif \(\$usingSafeRetry\) \{ "encode-safe-retry" \} else \{ "encode" \}') 'Encode publish route label must preserve CPU and safe-retry outcomes.'
Assert-True ($encodeText -match '-ProgressRoute ''encode'' -StagePrefix ''encode'' -Context "ENCODE: "') 'Encode publish handoff must preserve progress route, stage prefix, and context.'
Assert-True ($encodeText -match '-Tx3gTracks @\(\$subResult\.Tx3gTracks\).*?-ConvertedSrtSidecarCandidates @\(\$subResult\.ConvertedSrtSidecarCandidates\)' ) 'Encode publish handoff must continue forwarding subtitle/sidecar candidates.'

Write-Host 'Encode publish-order split checks passed.'
