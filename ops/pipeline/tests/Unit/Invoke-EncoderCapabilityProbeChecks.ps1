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

Write-Host 'Encoder capability probe checks passed.'
