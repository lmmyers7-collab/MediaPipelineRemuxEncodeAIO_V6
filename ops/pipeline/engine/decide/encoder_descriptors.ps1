# ==============================================================================
# ops\pipeline\engine\decide\encoder_descriptors.ps1
# ==============================================================================
# Data-first encoder descriptors. Phase 1 intentionally covers only the existing
# supported HEVC/NVENC primary path and libx265 CPU fallback path.
# ==============================================================================

function Get-MediaEncoderDescriptor {
    param(
        [Parameter(Mandatory)] [string] $Family,
        [Parameter(Mandatory)] [string] $Backend
    )

    $normalizedFamily = if ($Family) { $Family.Trim().ToLowerInvariant() } else { '' }
    $normalizedBackend = if ($Backend) { $Backend.Trim().ToLowerInvariant() } else { '' }
    if ($normalizedFamily -ne 'hevc') { return $null }

    if ($normalizedBackend -eq 'nvenc') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'hevc_nvenc'
            Family                 = 'hevc'
            Backend                = 'nvenc'
            RateControlKind        = 'nvenc_cq'
            QualityOffset          = 0
            UsesVbv                = $true
            PresetMap              = @{}
            HdrHandlerKind         = 'libav_side_data'
            SupportsHdr10Metadata  = $true
            ProfileArgsSdr         = @('-profile:v', 'main')
            ProfileArgsHdr         = @(
                '-profile:v', 'main10',
                '-pix_fmt', 'p010le',
                '-color_primaries', 'bt2020',
                '-color_trc', 'smpte2084',
                '-colorspace', 'bt2020nc'
            )
            ProbeEncoderName       = 'hevc_nvenc'
            FailurePatternKind     = 'nvenc'
            ContainerNotes         = 'Existing HEVC NVENC behavior; descriptor path must remain argument-identical.'
        }
    }

    if ($normalizedBackend -eq 'cpu') {
        $encoderName = if (Get-Command -Name Get-MediaVideoCodecLibx265Name -ErrorAction SilentlyContinue) {
            Get-MediaVideoCodecLibx265Name
        } else {
            'libx265'
        }
        return [pscustomobject][ordered]@{
            EncoderName            = $encoderName
            Family                 = 'hevc'
            Backend                = 'cpu'
            RateControlKind        = 'x265_crf'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = @{}
            HdrHandlerKind         = 'x265_params'
            SupportsHdr10Metadata  = $true
            ProfileArgsSdr         = @('-profile:v', 'main')
            ProfileArgsHdr         = @('-profile:v', 'main10', '-pix_fmt', 'p010le')
            ProbeEncoderName       = 'libx265'
            FailurePatternKind     = 'none'
            ContainerNotes         = 'Existing libx265 CPU fallback behavior; descriptor path must remain argument-identical.'
        }
    }

    return $null
}

function Resolve-MediaEncoderDescriptorForFlags {
    param(
        [string] $VideoCodec = '',
        [bool] $UseCpuFallback = $false
    )

    $codec = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $libx265Name = if (Get-Command -Name Get-MediaVideoCodecLibx265Name -ErrorAction SilentlyContinue) {
        (Get-MediaVideoCodecLibx265Name).Trim().ToLowerInvariant()
    } else {
        'libx265'
    }

    if ($UseCpuFallback) {
        if ($codec -in @('hevc_nvenc', $libx265Name)) {
            return Get-MediaEncoderDescriptor -Family 'hevc' -Backend 'cpu'
        }
        return $null
    }

    if ($codec -eq 'hevc_nvenc') {
        return Get-MediaEncoderDescriptor -Family 'hevc' -Backend 'nvenc'
    }
    return $null
}

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
        [string] $Hdr10MaxCll = ''
    )

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
    if ($isCpuDescriptor) {
        $resolvedCpuPreset = if (Get-Command -Name Resolve-MediaPipelineCpuEncodePreset -ErrorAction SilentlyContinue) {
            Resolve-MediaPipelineCpuEncodePreset -Preset $CpuPreset
        } else {
            $textPreset = if ($CpuPreset) { $CpuPreset.Trim().ToLowerInvariant() } else { '' }
            if ([string]::IsNullOrWhiteSpace($textPreset)) { 'medium' } else { $textPreset }
        }
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
        }
        $flags = @(
            '-c:v', [string]$Descriptor.EncoderName,
            '-preset', $resolvedCpuPreset,
            '-crf', $effectiveCpuQuality
        )
        if ($CpuMaxThreads -gt 0) {
            $flags += @('-threads', [string]$CpuMaxThreads)
        }
        $flags += @('-x265-params', ($x265ParamPairs -join ':'))
    } else {
        $flags = @(
            '-c:v', [string]$Descriptor.EncoderName,
            '-preset', $VideoPreset,
            '-cq', $effectiveVideoQuality
        )
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
