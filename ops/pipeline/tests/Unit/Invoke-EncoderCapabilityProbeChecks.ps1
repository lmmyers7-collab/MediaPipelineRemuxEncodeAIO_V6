param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSScriptRoot."
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\choice_registry.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\default_values.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encoder_descriptors.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encode_policy.ps1')

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

$ffmpegPath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'
if (-not (Test-Path -LiteralPath $ffmpegPath -PathType Leaf)) {
    Write-Host "Encoder capability probe checks skipped: bundled ffmpeg missing at $ffmpegPath"
    exit 0
}

$av1CpuDescriptor = Get-MediaEncoderDescriptor -Family 'av1' -Backend 'cpu'
Assert-True ($null -ne $av1CpuDescriptor) 'AV1/CPU descriptor is required for capability probe checks.'

$fakeEncoderList = @'
 V..... libaom-av1            libaom AV1 (codec av1)
 V....D av1_nvenc            NVIDIA NVENC av1 encoder (codec av1)
'@
Assert-Equal (Test-MediaEncoderDescriptorListMatch -EncoderListText $fakeEncoderList -Descriptor $av1CpuDescriptor) $true 'Exact encoder list match should find libaom-av1.'
Assert-Equal (Test-MediaEncoderDescriptorListMatch -EncoderListText ' V..... xlibaom-av1' -Descriptor $av1CpuDescriptor) $false 'Encoder list match must not accept suffix-only names.'

$missingResult = Test-MediaEncoderDescriptorAvailable `
    -Descriptor $av1CpuDescriptor `
    -FfmpegPath (Join-Path $repoRoot 'LocalBase\missing-ffmpeg.exe') `
    -Force
Assert-Equal ([bool]$missingResult.Available) $false 'Missing ffmpeg must not be available.'
Assert-Equal ([bool]$missingResult.EncoderListMatch) $false 'Missing ffmpeg must not report encoder list match.'
Assert-Equal ([bool]$missingResult.Probed) $false 'Missing ffmpeg must not attempt runtime probing.'
Assert-True ([string]$missingResult.Reason -match 'ffmpeg not found') 'Missing ffmpeg result should explain the missing executable.'

$listedResult = Test-MediaEncoderDescriptorAvailable `
    -Descriptor $av1CpuDescriptor `
    -FfmpegPath $ffmpegPath `
    -SkipRuntimeProbe `
    -Force
Assert-Equal ([bool]$listedResult.EncoderListMatch) $true 'Bundled ffmpeg should list libaom-av1.'
Assert-Equal ([bool]$listedResult.Available) $false 'List-only probe must not claim runtime availability.'
Assert-Equal ([bool]$listedResult.RuntimeProbeSkipped) $true 'List-only probe must mark runtime probe as skipped.'
Assert-Equal ([bool]$listedResult.Probed) $false 'List-only probe must not mark runtime probe as executed.'

$runtimeResult = Test-MediaEncoderDescriptorAvailable `
    -Descriptor $av1CpuDescriptor `
    -FfmpegPath $ffmpegPath `
    -TimeoutSeconds 30
Assert-Equal ([bool]$runtimeResult.EncoderListMatch) $true 'Runtime probe should first prove libaom-av1 is listed.'
Assert-Equal ([bool]$runtimeResult.Probed) $true 'Runtime probe must still execute after a list-only cache entry exists.'
Assert-Equal ([bool]$runtimeResult.RuntimeOk) $true "Runtime probe should succeed for bundled libaom-av1. Reason: $($runtimeResult.Reason)"
Assert-Equal ([bool]$runtimeResult.Available) $true 'Runtime probe should mark bundled libaom-av1 as available.'

$av1NvencDescriptor = Get-MediaEncoderDescriptor -Family 'av1' -Backend 'nvenc'
Assert-True ($null -ne $av1NvencDescriptor) 'AV1/NVENC descriptor is required for list-only hardware probe checks.'
$hardwareListOnly = Test-MediaEncoderDescriptorAvailable `
    -Descriptor $av1NvencDescriptor `
    -FfmpegPath $ffmpegPath `
    -SkipRuntimeProbe `
    -Force
Assert-Equal ([bool]$hardwareListOnly.EncoderListMatch) $true 'Bundled ffmpeg should list av1_nvenc even when this host may not support runtime NVENC.'
Assert-Equal ([bool]$hardwareListOnly.Available) $false 'Hardware list-only probe must stay fail-closed until runtime probing succeeds.'
Assert-Equal ([bool]$hardwareListOnly.RuntimeProbeSkipped) $true 'Hardware list-only probe must not claim runtime validation.'

$script:ProbeInvalidationEvents = @()
$script:ProbeInvalidationLogs = @()
function Write-PipelineEvent {
    param(
        [string] $EventType,
        [string] $Stage = '',
        [string] $Status = '',
        [string] $SourcePath = '',
        $Data = $null
    )
    $script:ProbeInvalidationEvents += ,([pscustomobject]@{
        EventType  = $EventType
        Stage      = $Stage
        Status     = $Status
        SourcePath = $SourcePath
        Data       = $Data
    })
    return $true
}
function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:ProbeInvalidationLogs += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}

$previousDescriptorInvalidations = $script:EncoderDescriptorBackendInvalidations
$previousDescriptorProbeCache = $script:EncoderDescriptorCapabilityProbeCache
try {
    $script:EncoderDescriptorBackendInvalidations = @{}
    $script:EncoderDescriptorCapabilityProbeCache = @{}
    $backendInvalidation = Invalidate-EncoderBackendProbe `
        -Backend 'nvenc' `
        -Reason 'unit backend invalidation' `
        -SourcePath 'unit-source.mkv'
    Assert-Equal ([bool]$backendInvalidation.BackendInvalidated) $true 'Generic backend invalidation should mark descriptor probes invalidated.'
    Assert-Equal ([string]$backendInvalidation.Backend) 'nvenc' 'Generic backend invalidation should normalize backend evidence.'
    Assert-Equal ([string]$backendInvalidation.Trigger) 'runtime_encoder_failure' 'Generic backend invalidation should default the trigger evidence.'

    $blockedHardwareProbe = Test-MediaEncoderDescriptorAvailable `
        -Descriptor $av1NvencDescriptor `
        -FfmpegPath $ffmpegPath `
        -SkipRuntimeProbe
    Assert-Equal ([bool]$blockedHardwareProbe.Available) $false 'Backend invalidation must keep later descriptor probes unavailable.'
    Assert-Equal ([bool]$blockedHardwareProbe.BackendInvalidated) $true 'Backend invalidation should be visible on later descriptor probe results.'
    Assert-Equal ([string]$blockedHardwareProbe.Reason) 'unit backend invalidation' 'Backend invalidation reason should carry to later descriptor probe results.'
    Assert-Equal ([string]$blockedHardwareProbe.ProbeEncoderName) 'av1_nvenc' 'Invalidated descriptor result should preserve the requested probe encoder.'

    $forcedHardwareListProbe = Test-MediaEncoderDescriptorAvailable `
        -Descriptor $av1NvencDescriptor `
        -FfmpegPath $ffmpegPath `
        -SkipRuntimeProbe `
        -Force
    Assert-Equal ([bool]$forcedHardwareListProbe.EncoderListMatch) $true 'Forced descriptor probe should bypass backend invalidation for explicit rechecks.'
    Assert-Equal ([bool]$forcedHardwareListProbe.RuntimeProbeSkipped) $true 'Forced list-only descriptor probe should still avoid hardware runtime execution.'
    Assert-Equal ($null -eq $forcedHardwareListProbe.PSObject.Properties['BackendInvalidated']) $true 'Forced descriptor probe should not report backend invalidation when it bypasses the invalidated cache.'

    $invalidationEvent = @($script:ProbeInvalidationEvents | Where-Object { $_.EventType -eq 'gpu_unavailable' } | Select-Object -First 1)
    Assert-True ($invalidationEvent.Count -eq 1) 'Generic backend invalidation should emit one gpu_unavailable event.'
    Assert-Equal ([string]$invalidationEvent[0].Data.backend) 'nvenc' 'Generic backend invalidation event should carry backend evidence.'
    Assert-Equal ([string]$invalidationEvent[0].Data.trigger) 'runtime_encoder_failure' 'Generic backend invalidation event should carry trigger evidence.'
} finally {
    $script:EncoderDescriptorBackendInvalidations = $previousDescriptorInvalidations
    $script:EncoderDescriptorCapabilityProbeCache = $previousDescriptorProbeCache
}

$previousNvencProbe = $script:NvencAvailableProbe
$previousDescriptorInvalidations = $script:EncoderDescriptorBackendInvalidations
try {
    $script:NvencAvailableProbe = $null
    $script:EncoderDescriptorBackendInvalidations = @{}
    $missingFfmpegPath = Join-Path $repoRoot 'LocalBase\missing-ffmpeg.exe'
    $hevcMissingProbe = Test-NvencAvailable `
        -FfmpegPath $missingFfmpegPath `
        -TestEncoder 'hevc_nvenc' `
        -Force
    Assert-Equal ([bool]$hevcMissingProbe.DescriptorProbeCache) $true 'Legacy NVENC probe should be backed by the descriptor probe cache.'
    Assert-Equal ([string]$hevcMissingProbe.ProbeEncoderName) 'hevc_nvenc' 'Legacy NVENC probe should preserve the HEVC probe encoder name.'
    Assert-Equal ([bool]$hevcMissingProbe.Available) $false 'Missing ffmpeg should keep the bridged NVENC probe unavailable.'

    $av1MissingProbe = Test-NvencAvailable `
        -FfmpegPath $missingFfmpegPath `
        -TestEncoder 'av1_nvenc'
    Assert-Equal ([string]$av1MissingProbe.ProbeEncoderName) 'av1_nvenc' 'Legacy NVENC cache must not reuse a HEVC probe result for AV1/NVENC.'
    Assert-Equal ([string]$av1MissingProbe.Backend) 'nvenc' 'Legacy NVENC probe should preserve descriptor backend evidence.'
    Assert-Equal ([bool]$av1MissingProbe.Available) $false 'Missing ffmpeg should keep the AV1/NVENC bridge unavailable.'

    Invalidate-NvencAvailableProbe -Reason 'unit invalidation'
    $invalidatedProbe = Test-NvencAvailable `
        -FfmpegPath $missingFfmpegPath `
        -TestEncoder 'hevc_nvenc'
    Assert-Equal ([string]$invalidatedProbe.Reason) 'unit invalidation' 'Runtime invalidation should still short-circuit later legacy NVENC probe calls.'
    Assert-Equal ([bool]$invalidatedProbe.DescriptorProbeCache) $true 'Runtime invalidation should preserve descriptor-backed NVENC probe evidence.'
    Assert-Equal ([bool]$invalidatedProbe.BackendInvalidated) $true 'Runtime invalidation should also mark the descriptor backend invalidated.'
} finally {
    $script:NvencAvailableProbe = $previousNvencProbe
    $script:EncoderDescriptorBackendInvalidations = $previousDescriptorInvalidations
}

Write-Host 'Encoder capability probe checks passed.'
