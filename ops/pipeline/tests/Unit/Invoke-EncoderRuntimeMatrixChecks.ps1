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

function Assert-Throws {
    param(
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [Parameter(Mandatory)] [string] $Message,
        [string] $ExpectedPattern = ''
    )

    $didThrow = $false
    $errorText = ''
    try {
        & $ScriptBlock | Out-Null
    } catch {
        $didThrow = $true
        $errorText = [string]$_.Exception.Message
    }
    if (-not $didThrow) { throw $Message }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedPattern) -and $errorText -notmatch $ExpectedPattern) {
        throw "$Message Unexpected error text: $errorText"
    }
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
        '-show_entries', 'stream=codec_name,pix_fmt,color_space,color_transfer,color_primaries',
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

function Assert-Contains {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [array] $Items,
        [Parameter(Mandatory)] [string] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not (@($Items) -contains $Expected)) {
        throw "$Message Expected list to contain '$Expected'."
    }
}

function Get-FlagValue {
    param(
        [Parameter(Mandatory)] [array] $Flags,
        [Parameter(Mandatory)] [string] $Name
    )
    $index = [array]::IndexOf([object[]]$Flags, $Name)
    if ($index -lt 0 -or ($index + 1) -ge @($Flags).Count) { return '' }
    return [string]$Flags[$index + 1]
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
    @{ Family = 'hevc'; Backend = 'cpu';   Codec = 'libx265';   ExpectedCodec = 'hevc'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'h264'; Backend = 'cpu';   Codec = 'libx264';   ExpectedCodec = 'h264'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'av1';  Backend = 'cpu';   Codec = 'libaom-av1'; ExpectedCodec = 'av1';  Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'hevc'; Backend = 'nvenc'; Codec = 'hevc_nvenc'; ExpectedCodec = 'hevc'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'h264'; Backend = 'nvenc'; Codec = 'h264_nvenc'; ExpectedCodec = 'h264'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'av1';  Backend = 'nvenc'; Codec = 'av1_nvenc';  ExpectedCodec = 'av1';  Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'hevc'; Backend = 'qsv';   Codec = 'hevc_qsv';   ExpectedCodec = 'hevc'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'h264'; Backend = 'qsv';   Codec = 'h264_qsv';   ExpectedCodec = 'h264'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'av1';  Backend = 'qsv';   Codec = 'av1_qsv';    ExpectedCodec = 'av1';  Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'hevc'; Backend = 'amf';   Codec = 'hevc_amf';   ExpectedCodec = 'hevc'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'h264'; Backend = 'amf';   Codec = 'h264_amf';   ExpectedCodec = 'h264'; Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'av1';  Backend = 'amf';   Codec = 'av1_amf';    ExpectedCodec = 'av1';  Preset = 'p1'; Mode = 'sdr' },
    @{ Family = 'hevc'; Backend = 'cpu';   Codec = 'libx265';    ExpectedCodec = 'hevc'; Preset = 'p1'; Mode = 'hdr10' },
    @{ Family = 'hevc'; Backend = 'nvenc'; Codec = 'hevc_nvenc'; ExpectedCodec = 'hevc'; Preset = 'p1'; Mode = 'hdr10' },
    @{ Family = 'av1';  Backend = 'nvenc'; Codec = 'av1_nvenc';  ExpectedCodec = 'av1';  Preset = 'p1'; Mode = 'hdr10' }
)

$hardwareBackends = @('nvenc', 'qsv', 'amf')
$hardwareHdrBlockCases = @(
    @{ Family = 'h264'; Backend = 'nvenc'; Codec = 'h264_nvenc'; Preset = 'p1' },
    @{ Family = 'hevc'; Backend = 'qsv';   Codec = 'hevc_qsv';   Preset = 'p1' },
    @{ Family = 'h264'; Backend = 'qsv';   Codec = 'h264_qsv';   Preset = 'p1' },
    @{ Family = 'av1';  Backend = 'qsv';   Codec = 'av1_qsv';    Preset = 'p1' },
    @{ Family = 'hevc'; Backend = 'amf';   Codec = 'hevc_amf';   Preset = 'p1' },
    @{ Family = 'h264'; Backend = 'amf';   Codec = 'h264_amf';   Preset = 'p1' },
    @{ Family = 'av1';  Backend = 'amf';   Codec = 'av1_amf';    Preset = 'p1' }
)

$runHardwareRows = ([string]$env:MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE).Trim() -eq '1'
$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$tempRoot = Join-Path $tempBase ('mediapipeline-encoder-runtime-matrix-' + [guid]::NewGuid().ToString('N'))
$passed = 0
$hdrPassed = 0
$skipped = 0
$hardwareRows = 0
$hardwareRowsSkippedByDefault = 0
$dormantHardwareRowsSkipped = 0
$activeHardwareRowsExecuted = 0
$activeAv1NvencRowsExecuted = 0
$hardwareHdrTopologyRows = 0
$hardwareHdrBlockedRows = 0

foreach ($blockCase in $hardwareHdrBlockCases) {
    $descriptor = Get-MediaEncoderDescriptor -Family ([string]$blockCase.Family) -Backend ([string]$blockCase.Backend)
    $caseLabel = "$($blockCase.Family)/$($blockCase.Backend)/hdr10-blocked"
    Assert-True ($null -ne $descriptor) "HDR-block descriptor missing for $caseLabel."
    Assert-True ($hardwareBackends -contains ([string]$blockCase.Backend)) "HDR-block case must cover a hardware backend: $caseLabel."
    Assert-Equal ([bool]$descriptor.SupportsHdr10Metadata) $false "HDR-block case must advertise unsupported HDR metadata: $caseLabel."
    Assert-Throws {
        New-EncoderVideoFlags `
            -Descriptor $descriptor `
            -IsHDR:$true `
            -VideoCodec ([string]$blockCase.Codec) `
            -VideoPreset ([string]$blockCase.Preset) `
            -VideoQuality 22
    } "HDR-block case must fail closed before FFmpeg flag construction: $caseLabel." 'does not support HDR10 metadata preservation'
    $hardwareHdrBlockedRows += 1
}

try {
    [void](New-Item -ItemType Directory -Path $tempRoot -Force)

    foreach ($case in $matrixCases) {
        $descriptor = Get-MediaEncoderDescriptor -Family ([string]$case.Family) -Backend ([string]$case.Backend)
        Assert-True ($null -ne $descriptor) "Descriptor missing for $($case.Family)/$($case.Backend)."
        $mode = if ($case.ContainsKey('Mode')) { [string]$case.Mode } else { 'sdr' }
        $isHdr = $mode -eq 'hdr10'
        $caseLabel = "$($case.Family)/$($case.Backend)/$mode"
        $isHardware = $hardwareBackends -contains ([string]$case.Backend)
        if ($isHardware) { $hardwareRows += 1 }
        $activeFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec ([string]$case.Codec)
        $descriptorFlagsActive = $null -ne $activeFlagsDescriptor -and
            ([string]$activeFlagsDescriptor.EncoderName).Trim().ToLowerInvariant() -eq ([string]$descriptor.EncoderName).Trim().ToLowerInvariant()
        if ($isHdr) {
            Assert-True ([bool]$descriptor.SupportsHdr10Metadata) "HDR runtime matrix case requires an HDR-capable descriptor: $caseLabel."
        }

        $flagArgs = @{
            Descriptor         = $descriptor
            IsHDR              = $isHdr
            VideoCodec         = [string]$case.Codec
            VideoPreset        = [string]$case.Preset
            VideoQuality       = 22
            FallbackCpuQuality = 20
            CpuPreset          = 'medium'
            CpuMaxThreads      = 2
        }
        if ($isHdr) {
            $flagArgs.Hdr10MasterDisplay = 'G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)'
            $flagArgs.Hdr10MaxCll = '1000,400'
        }
        $videoFlags = @(New-EncoderVideoFlags @flagArgs)
        Assert-Contains -Items $videoFlags -Expected '-c:v' -Message "Descriptor flags for $caseLabel must include -c:v."
        Assert-Contains -Items $videoFlags -Expected ([string]$case.Codec) -Message "Descriptor flags for $caseLabel must include codec $($case.Codec)."
        if ($isHdr) {
            Assert-Contains -Items $videoFlags -Expected '-pix_fmt' -Message "HDR descriptor flags for $caseLabel must choose a 10-bit pixel format."
            Assert-Contains -Items $videoFlags -Expected 'p010le' -Message "HDR descriptor flags for $caseLabel must use p010le before encode."
            if ([string]$descriptor.RateControlKind -eq 'x265_crf') {
                $x265Params = Get-FlagValue -Flags $videoFlags -Name '-x265-params'
                Assert-True ($x265Params.Contains('hdr10=1')) "HDR x265 params for $caseLabel must enable hdr10=1."
                Assert-True ($x265Params.Contains('hdr10-opt=1')) "HDR x265 params for $caseLabel must enable hdr10-opt=1."
                Assert-True ($x265Params.Contains('repeat-headers=1')) "HDR x265 params for $caseLabel must repeat headers."
                Assert-True ($x265Params.Contains('colorprim=bt2020')) "HDR x265 params for $caseLabel must carry BT.2020 primaries."
                Assert-True ($x265Params.Contains('transfer=smpte2084')) "HDR x265 params for $caseLabel must carry SMPTE 2084 transfer."
                Assert-True ($x265Params.Contains('colormatrix=bt2020nc')) "HDR x265 params for $caseLabel must carry BT.2020 non-constant matrix."
                Assert-True ($x265Params.Contains('master-display=')) "HDR x265 params for $caseLabel must carry mastering display metadata."
                Assert-True ($x265Params.Contains('max-cll=')) "HDR x265 params for $caseLabel must carry MaxCLL metadata."
            } elseif ([string]$descriptor.HdrHandlerKind -eq 'libav_side_data') {
                Assert-Contains -Items $videoFlags -Expected '-color_primaries' -Message "HDR libav-side-data flags for $caseLabel must set color primaries."
                Assert-Contains -Items $videoFlags -Expected 'bt2020' -Message "HDR libav-side-data flags for $caseLabel must carry BT.2020 primaries."
                Assert-Contains -Items $videoFlags -Expected '-color_trc' -Message "HDR libav-side-data flags for $caseLabel must set color transfer."
                Assert-Contains -Items $videoFlags -Expected 'smpte2084' -Message "HDR libav-side-data flags for $caseLabel must carry SMPTE 2084 transfer."
                Assert-Contains -Items $videoFlags -Expected '-colorspace' -Message "HDR libav-side-data flags for $caseLabel must set color space."
                Assert-Contains -Items $videoFlags -Expected 'bt2020nc' -Message "HDR libav-side-data flags for $caseLabel must carry BT.2020 non-constant matrix."
            }
            if ($isHardware) { $hardwareHdrTopologyRows += 1 }
        }

        if ($isHardware -and -not $descriptorFlagsActive) {
            $skipped += 1
            $dormantHardwareRowsSkipped += 1
            Write-Host "Skipping $caseLabel dormant hardware descriptor row; descriptor-owned flags are not active."
            continue
        }

        if ($isHardware -and -not $runHardwareRows) {
            $listed = Test-MediaEncoderDescriptorAvailable `
                -Descriptor $descriptor `
                -FfmpegPath $ffmpegPath `
                -SkipRuntimeProbe `
                -Force
            $skipped += 1
            $hardwareRowsSkippedByDefault += 1
            Write-Host "Skipping $caseLabel hardware runtime topology row by default. EncoderListMatch=$($listed.EncoderListMatch). Set MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE=1 to require host hardware execution."
            continue
        }

        $probe = Test-MediaEncoderDescriptorAvailable `
            -Descriptor $descriptor `
            -FfmpegPath $ffmpegPath `
            -TimeoutSeconds 20 `
            -Force
        if (-not [bool]$probe.Available) {
            $skipped += 1
            Write-Host "Skipping $caseLabel runtime matrix row: $($probe.Reason)"
            continue
        }

        $outputPath = Join-Path $tempRoot ("$($case.Family)-$($case.Backend)-$mode.mkv")
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
            throw "Runtime matrix encode failed for $caseLabel using $($case.Codec): $($encode.Output)"
        }
        Assert-True (Test-Path -LiteralPath $outputPath -PathType Leaf) "Runtime matrix output missing for $caseLabel."

        $stream = Read-VideoStreamInfo -FfprobePath $ffprobePath -MediaPath $outputPath
        Assert-Equal ([string]$stream.codec_name) ([string]$case.ExpectedCodec) "Runtime matrix codec mismatch for $caseLabel."
        if ($isHdr) {
            Assert-True ([string]$stream.pix_fmt -match '10') "HDR runtime matrix output for $caseLabel must be 10-bit; got pix_fmt=$($stream.pix_fmt)."
            if ($isHardware) {
                # Synthetic lavfi input has no HDR side data. The active hardware
                # rows prove descriptor flag topology, 10-bit execution, and
                # encoder availability, but must not be promoted to metadata
                # preservation evidence. That requires representative HDR media.
                Write-Host "Executed $caseLabel hardware HDR topology row; representative-media side-data preservation remains unproven."
            } else {
                Assert-Equal ([string]$stream.color_primaries) 'bt2020' "HDR runtime matrix output for $caseLabel must preserve BT.2020 primaries."
                Assert-Equal ([string]$stream.color_transfer) 'smpte2084' "HDR runtime matrix output for $caseLabel must preserve SMPTE 2084 transfer."
                Assert-Equal ([string]$stream.color_space) 'bt2020nc' "HDR runtime matrix output for $caseLabel must preserve BT.2020 non-constant color space."
            }
            $hdrPassed += 1
        }
        if ($isHardware) {
            $activeHardwareRowsExecuted += 1
            if ([string]$case.Family -eq 'av1' -and [string]$case.Backend -eq 'nvenc') {
                $activeAv1NvencRowsExecuted += 1
            }
        }
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
Assert-True ($hdrPassed -gt 0) 'Encoder runtime matrix must execute at least one HDR descriptor row on this toolchain.'
Assert-True ($hardwareRows -gt 0) 'Encoder runtime matrix must include hardware descriptor rows.'
Assert-True ($hardwareHdrTopologyRows -gt 0) 'Encoder runtime matrix must verify at least one HDR-capable hardware descriptor topology row before execution or skip.'
Assert-True ($hardwareHdrBlockedRows -gt 0) 'Encoder runtime matrix must verify HDR-unsafe hardware descriptors fail closed.'
if (-not $runHardwareRows) {
    $hardwareRowsSkippedWithoutExecution = $hardwareRowsSkippedByDefault + $dormantHardwareRowsSkipped
    Assert-Equal $hardwareRowsSkippedWithoutExecution $hardwareRows 'Default encoder runtime matrix must skip every hardware row unless MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE=1 is set.'
}
Write-Host "Encoder runtime matrix checks passed. Rows passed: $passed. HDR rows passed: $hdrPassed. Rows skipped: $skipped. Hardware rows: $hardwareRows. Default hardware skips: $hardwareRowsSkippedByDefault. Dormant hardware skips: $dormantHardwareRowsSkipped. Active hardware rows executed: $activeHardwareRowsExecuted. Active AV1/NVENC rows executed: $activeAv1NvencRowsExecuted. Hardware HDR topology rows: $hardwareHdrTopologyRows. Hardware HDR-blocked rows: $hardwareHdrBlockedRows."
