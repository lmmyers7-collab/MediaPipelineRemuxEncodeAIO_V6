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

function Invoke-Tool {
    param(
        [Parameter(Mandatory)] [string] $ExePath,
        [Parameter(Mandatory)] [array] $ArgumentList
    )

    $output = & $ExePath @ArgumentList 2>&1
    return [pscustomobject][ordered]@{
        ExitCode = $LASTEXITCODE
        Output   = ($output | Out-String)
    }
}

function Read-VideoStreamInfo {
    param(
        [Parameter(Mandatory)] [string] $FfprobePath,
        [Parameter(Mandatory)] [string] $MediaPath
    )

    $result = Invoke-Tool -ExePath $FfprobePath -ArgumentList @(
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,pix_fmt',
        '-of', 'json',
        $MediaPath
    )
    if ($result.ExitCode -ne 0) {
        throw "ffprobe failed for '$MediaPath': $($result.Output)"
    }
    $json = $result.Output | ConvertFrom-Json
    if (-not $json.streams -or @($json.streams).Count -lt 1) {
        throw "ffprobe did not report a video stream for '$MediaPath'."
    }
    return @($json.streams)[0]
}

$ffmpegPath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'
$ffprobePath = Join-Path $repoRoot 'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe'
if (-not (Test-Path -LiteralPath $ffmpegPath -PathType Leaf)) {
    Write-Host "Encoder runtime matrix checks skipped: bundled ffmpeg missing at $ffmpegPath"
    exit 0
}
if (-not (Test-Path -LiteralPath $ffprobePath -PathType Leaf)) {
    Write-Host "Encoder runtime matrix checks skipped: bundled ffprobe missing at $ffprobePath"
    exit 0
}

$matrixCases = @(
    @{ Family = 'hevc'; Backend = 'cpu';   Codec = 'libx265';   ExpectedCodec = 'hevc'; Preset = 'p1' },
    @{ Family = 'h264'; Backend = 'cpu';   Codec = 'libx264';   ExpectedCodec = 'h264'; Preset = 'p1' },
    @{ Family = 'av1';  Backend = 'cpu';   Codec = 'libaom-av1'; ExpectedCodec = 'av1';  Preset = 'p1' },
    @{ Family = 'hevc'; Backend = 'nvenc'; Codec = 'hevc_nvenc'; ExpectedCodec = 'hevc'; Preset = 'p1' },
    @{ Family = 'h264'; Backend = 'nvenc'; Codec = 'h264_nvenc'; ExpectedCodec = 'h264'; Preset = 'p1' },
    @{ Family = 'av1';  Backend = 'nvenc'; Codec = 'av1_nvenc';  ExpectedCodec = 'av1';  Preset = 'p1' },
    @{ Family = 'hevc'; Backend = 'qsv';   Codec = 'hevc_qsv';   ExpectedCodec = 'hevc'; Preset = 'p1' },
    @{ Family = 'h264'; Backend = 'qsv';   Codec = 'h264_qsv';   ExpectedCodec = 'h264'; Preset = 'p1' },
    @{ Family = 'av1';  Backend = 'qsv';   Codec = 'av1_qsv';    ExpectedCodec = 'av1';  Preset = 'p1' },
    @{ Family = 'hevc'; Backend = 'amf';   Codec = 'hevc_amf';   ExpectedCodec = 'hevc'; Preset = 'p1' },
    @{ Family = 'h264'; Backend = 'amf';   Codec = 'h264_amf';   ExpectedCodec = 'h264'; Preset = 'p1' },
    @{ Family = 'av1';  Backend = 'amf';   Codec = 'av1_amf';    ExpectedCodec = 'av1';  Preset = 'p1' }
)

$runHardwareRows = ([string]$env:MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE).Trim() -eq '1'
$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$tempRoot = Join-Path $tempBase ('mediapipeline-encoder-runtime-matrix-' + [guid]::NewGuid().ToString('N'))
$passed = 0
$skipped = 0
try {
    [void](New-Item -ItemType Directory -Path $tempRoot -Force)

    foreach ($case in $matrixCases) {
        $descriptor = Get-MediaEncoderDescriptor -Family ([string]$case.Family) -Backend ([string]$case.Backend)
        Assert-True ($null -ne $descriptor) "Descriptor missing for $($case.Family)/$($case.Backend)."

        $isHardware = @('nvenc', 'qsv', 'amf') -contains ([string]$case.Backend)
        if ($isHardware -and -not $runHardwareRows) {
            $listed = Test-MediaEncoderDescriptorAvailable `
                -Descriptor $descriptor `
                -FfmpegPath $ffmpegPath `
                -SkipRuntimeProbe `
                -Force
            $skipped += 1
            Write-Host "Skipping $($case.Family)/$($case.Backend) hardware runtime topology row by default. EncoderListMatch=$($listed.EncoderListMatch). Set MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE=1 to require host hardware execution."
            continue
        }

        $probe = Test-MediaEncoderDescriptorAvailable `
            -Descriptor $descriptor `
            -FfmpegPath $ffmpegPath `
            -TimeoutSeconds 20 `
            -Force
        if (-not [bool]$probe.Available) {
            $skipped += 1
            Write-Host "Skipping $($case.Family)/$($case.Backend) runtime matrix row: $($probe.Reason)"
            continue
        }

        $videoFlags = @(New-EncoderVideoFlags `
            -Descriptor $descriptor `
            -VideoCodec ([string]$case.Codec) `
            -VideoPreset ([string]$case.Preset) `
            -VideoQuality 22 `
            -FallbackCpuQuality 20 `
            -CpuPreset 'medium' `
            -CpuMaxThreads 2)
        Assert-True (@($videoFlags) -contains '-c:v') "Descriptor flags for $($case.Family)/$($case.Backend) must include -c:v."
        Assert-True (@($videoFlags) -contains ([string]$case.Codec)) "Descriptor flags for $($case.Family)/$($case.Backend) must include codec $($case.Codec)."

        $outputPath = Join-Path $tempRoot ("$($case.Family)-$($case.Backend).mkv")
        $encodeArgs = @(
            '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=1:duration=1',
            '-frames:v', '1'
        ) + $videoFlags + @(
            '-an', '-sn', '-dn',
            '-f', 'matroska',
            '-y', $outputPath
        )

        $encode = Invoke-Tool -ExePath $ffmpegPath -ArgumentList $encodeArgs
        if ($encode.ExitCode -ne 0) {
            throw "Runtime matrix encode failed for $($case.Family)/$($case.Backend) using $($case.Codec): $($encode.Output)"
        }
        Assert-True (Test-Path -LiteralPath $outputPath -PathType Leaf) "Runtime matrix output missing for $($case.Family)/$($case.Backend)."

        $stream = Read-VideoStreamInfo -FfprobePath $ffprobePath -MediaPath $outputPath
        Assert-Equal ([string]$stream.codec_name) ([string]$case.ExpectedCodec) "Runtime matrix codec mismatch for $($case.Family)/$($case.Backend)."
        $passed += 1
    }
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        $resolvedTempRoot = [System.IO.Path]::GetFullPath($tempRoot)
        $tempLeaf = Split-Path -Leaf $resolvedTempRoot
        if ($resolvedTempRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase) -and
            $tempLeaf.StartsWith('mediapipeline-encoder-runtime-matrix-', [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Assert-True ($passed -gt 0) 'Encoder runtime matrix must execute at least one descriptor row on this toolchain.'
Write-Host "Encoder runtime matrix checks passed. Rows passed: $passed. Rows skipped: $skipped."
