# Extracted from ops/pipeline/engine/decide/encoder_descriptors.ps1. Responsibility: final encoder video flag construction

function New-EncoderVideoFlags {
    param(
        [Parameter(Mandatory)] $Descriptor,
        [bool] $IsHDR = $false,
        [bool] $IsTV = $false,
        [bool] $UseSafeHardwareRetry = $false,
        [Parameter(Mandatory)] [string] $VideoCodec,
        [Parameter(Mandatory)] [string] $VideoPreset,
        [Parameter(Mandatory)] [int] $VideoQuality,
        [array] $ExtraVideoFlags = @(),
        [int] $FallbackCpuQuality = 20,
        [string] $EncodeLadder = 'auto',
        [string] $CpuPreset = 'medium',
        [int] $CpuMaxThreads = 0,
        [string] $Hdr10MasterDisplay = '',
        [string] $Hdr10MaxCll = '',
        [string] $DolbyVisionRpuPath = '',
        [string] $DolbyVisionTargetProfile = '',
        [string] $Hdr10PlusJsonPath = ''
    )

    if ($IsHDR -and -not [bool]$Descriptor.SupportsHdr10Metadata) {
        throw "Encoder descriptor '$($Descriptor.Family)/$($Descriptor.Backend)' does not support HDR10 metadata preservation."
    }
    $dynamicHdrX265Requested = Test-DynamicHdrX265ParameterRequested -DolbyVisionRpuPath $DolbyVisionRpuPath -Hdr10PlusJsonPath $Hdr10PlusJsonPath
    if ($dynamicHdrX265Requested -and -not $IsHDR) {
        throw 'Dynamic HDR x265 parameters require an HDR encode plan.'
    }

    $ladderProfile = Get-MediaEncodeLadderProfile -Ladder $EncodeLadder -IsTV:$IsTV
    $effectiveVideoQuality = Get-MediaEncodeBoundedQuality -Quality ([int]$VideoQuality + [int]$ladderProfile.quality_delta + [int]$Descriptor.QualityOffset)
    $cpuLadderDelta = [int][math]::Round([double]$ladderProfile.quality_delta / 2.0, [System.MidpointRounding]::AwayFromZero)
    $effectiveCpuQuality = Get-MediaEncodeBoundedQuality -Quality ([int]$FallbackCpuQuality + $cpuLadderDelta + [int]$Descriptor.QualityOffset)
    $effectiveExtraVideoFlags = @($ExtraVideoFlags)
    if ($UseSafeHardwareRetry -or ([string]$ladderProfile.tuning_preset -eq 'compatibility')) {
        if (Get-Command -Name Get-MediaPipelineEncodeTuningFlags -ErrorAction SilentlyContinue) {
            $effectiveExtraVideoFlags = @(
                Get-MediaPipelineEncodeTuningFlags -Preset 'compatibility' -Codec $VideoCodec -LegacyExtraVideoFlags @()
            )
        }
    }

    $isCpuDescriptor = ([string]$Descriptor.Backend -eq 'cpu')
    if ($dynamicHdrX265Requested -and (-not $isCpuDescriptor -or [string]$Descriptor.RateControlKind -ne 'x265_crf')) {
        throw 'Dynamic HDR x265 parameters are supported only on CPU libx265 encode descriptors.'
    }
    $presetMap = $Descriptor.PresetMap
    $mappedVideoPreset = if ($presetMap -and $presetMap.ContainsKey($VideoPreset)) {
        [string]$presetMap[$VideoPreset]
    } else {
        [string]$VideoPreset
    }
    if ($isCpuDescriptor) {
        $resolvedCpuPreset = if (Get-Command -Name Resolve-MediaPipelineCpuEncodePreset -ErrorAction SilentlyContinue) {
            Resolve-MediaPipelineCpuEncodePreset -Preset $CpuPreset
        } else {
            $textPreset = if ($CpuPreset) { $CpuPreset.Trim().ToLowerInvariant() } else { '' }
            if ([string]::IsNullOrWhiteSpace($textPreset)) { 'medium' } else { $textPreset }
        }
        $flags = @(
            '-c:v', [string]$Descriptor.EncoderName,
            '-preset', $resolvedCpuPreset,
            '-crf', $effectiveCpuQuality
        )
        if ($IsHDR -and -not [string]::IsNullOrWhiteSpace($DolbyVisionRpuPath)) {
            $flags += @('-dolbyvision', 'true')
        }
        if ($CpuMaxThreads -gt 0) {
            $flags += @('-threads', [string]$CpuMaxThreads)
        }
        if ([string]$Descriptor.RateControlKind -eq 'x265_crf') {
            $x265ParamPairs = [System.Collections.Generic.List[string]]::new()
            $x265ParamPairs.Add('log-level=error')
            if ($CpuMaxThreads -gt 0) {
                $frameThreads = [int][math]::Max(1, [math]::Ceiling([double]$CpuMaxThreads / 4.0))
                $x265ParamPairs.Add("pools=$CpuMaxThreads")
                $x265ParamPairs.Add("frame-threads=$frameThreads")
            }
            if ($IsHDR) {
                $x265ParamPairs.Add('hdr10=1')
                $x265ParamPairs.Add('hdr10-opt=1')
                $x265ParamPairs.Add('repeat-headers=1')
                $x265ParamPairs.Add('colorprim=bt2020')
                $x265ParamPairs.Add('transfer=smpte2084')
                $x265ParamPairs.Add('colormatrix=bt2020nc')
                if (-not [string]::IsNullOrWhiteSpace($Hdr10MasterDisplay)) {
                    $x265ParamPairs.Add("master-display=$Hdr10MasterDisplay")
                }
                if (-not [string]::IsNullOrWhiteSpace($Hdr10MaxCll)) {
                    $x265ParamPairs.Add("max-cll=$Hdr10MaxCll")
                }
                Add-DynamicHdrX265ParameterPairs `
                    -ParamPairs $x265ParamPairs `
                    -DolbyVisionRpuPath $DolbyVisionRpuPath `
                    -DolbyVisionTargetProfile $DolbyVisionTargetProfile `
                    -Hdr10PlusJsonPath $Hdr10PlusJsonPath
            }
            $flags += @('-x265-params', ($x265ParamPairs -join ':'))
        } elseif ([string]$Descriptor.RateControlKind -eq 'aom_crf') {
            $flags = @(
                '-c:v', [string]$Descriptor.EncoderName,
                '-crf', $effectiveCpuQuality,
                '-b:v', '0',
                '-cpu-used', $mappedVideoPreset
            )
            if ($CpuMaxThreads -gt 0) {
                $flags += @('-threads', [string]$CpuMaxThreads)
            }
        } elseif ([string]$Descriptor.RateControlKind -ne 'x264_crf') {
            throw "Unsupported CPU encoder rate-control kind '$($Descriptor.RateControlKind)'."
        }
    } else {
        if ([string]$Descriptor.RateControlKind -eq 'qsv_global_quality') {
            $flags = @(
                '-c:v', [string]$Descriptor.EncoderName,
                '-preset', $mappedVideoPreset,
                '-global_quality', $effectiveVideoQuality
            )
        } elseif ([string]$Descriptor.RateControlKind -eq 'amf_cqp') {
            $flags = @(
                '-c:v', [string]$Descriptor.EncoderName,
                '-quality', $mappedVideoPreset,
                '-rc', 'cqp',
                '-qp_i', $effectiveVideoQuality,
                '-qp_p', $effectiveVideoQuality
            )
        } elseif ([string]$Descriptor.RateControlKind -eq 'nvenc_cq') {
            $flags = @(
                '-c:v', [string]$Descriptor.EncoderName,
                '-preset', $mappedVideoPreset,
                '-cq', $effectiveVideoQuality
            )
        } else {
            throw "Unsupported hardware encoder rate-control kind '$($Descriptor.RateControlKind)'."
        }
        if ($Descriptor.UsesVbv) {
            $flags += @('-maxrate', [string]$ladderProfile.maxrate, '-bufsize', [string]$ladderProfile.bufsize)
        }
        $flags += @($effectiveExtraVideoFlags)
    }

    if ($IsHDR) {
        $flags += @($Descriptor.ProfileArgsHdr)
    } else {
        $flags += @($Descriptor.ProfileArgsSdr)
    }

    return @($flags)
}
