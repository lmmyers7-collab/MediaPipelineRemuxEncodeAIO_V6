# ==============================================================================
# ops\pipeline\engine\decide\encoder_descriptors.ps1
# ==============================================================================
# Data-first encoder descriptors. The active resolver intentionally routes only
# the existing HEVC/NVENC primary path and libx265 CPU fallback path through the
# descriptor builder. Dormant descriptors may describe future supported pairs
# before route selection is allowed to activate them.
# ==============================================================================

function Get-MediaEncoderDescriptor {
    param(
        [Parameter(Mandatory)] [string] $Family,
        [Parameter(Mandatory)] [string] $Backend
    )

    $normalizedFamily = if ($Family) { $Family.Trim().ToLowerInvariant() } else { '' }
    $normalizedBackend = if ($Backend) { $Backend.Trim().ToLowerInvariant() } else { '' }
    $qsvPresetMap = @{
        p1 = 'veryfast'
        p2 = 'faster'
        p3 = 'fast'
        p4 = 'medium'
        p5 = 'slow'
        p6 = 'slower'
        p7 = 'veryslow'
    }
    $amfQualityMap = @{
        p1 = 'speed'
        p2 = 'speed'
        p3 = 'speed'
        p4 = 'balanced'
        p5 = 'balanced'
        p6 = 'quality'
        p7 = 'quality'
    }
    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'nvenc') {
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

    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'cpu') {
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

    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'qsv') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'hevc_qsv'
            Family                 = 'hevc'
            Backend                = 'qsv'
            RateControlKind        = 'qsv_global_quality'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = $qsvPresetMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'hevc_qsv'
            FailurePatternKind     = 'qsv'
            ContainerNotes         = 'Dormant HEVC QSV descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'hevc' -and $normalizedBackend -eq 'amf') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'hevc_amf'
            Family                 = 'hevc'
            Backend                = 'amf'
            RateControlKind        = 'amf_cqp'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = $amfQualityMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'hevc_amf'
            FailurePatternKind     = 'amf'
            ContainerNotes         = 'Dormant HEVC AMF descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'nvenc') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'h264_nvenc'
            Family                 = 'h264'
            Backend                = 'nvenc'
            RateControlKind        = 'nvenc_cq'
            QualityOffset          = 0
            UsesVbv                = $true
            PresetMap              = @{}
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @('-profile:v', 'high')
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'h264_nvenc'
            FailurePatternKind     = 'nvenc'
            ContainerNotes         = 'Dormant H.264 NVENC descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'cpu') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'libx264'
            Family                 = 'h264'
            Backend                = 'cpu'
            RateControlKind        = 'x264_crf'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = @{}
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @('-profile:v', 'high')
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'libx264'
            FailurePatternKind     = 'none'
            ContainerNotes         = 'Dormant x264 CPU descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'qsv') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'h264_qsv'
            Family                 = 'h264'
            Backend                = 'qsv'
            RateControlKind        = 'qsv_global_quality'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = $qsvPresetMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'h264_qsv'
            FailurePatternKind     = 'qsv'
            ContainerNotes         = 'Dormant H.264 QSV descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'h264' -and $normalizedBackend -eq 'amf') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'h264_amf'
            Family                 = 'h264'
            Backend                = 'amf'
            RateControlKind        = 'amf_cqp'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = $amfQualityMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'h264_amf'
            FailurePatternKind     = 'amf'
            ContainerNotes         = 'Dormant H.264 AMF descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'nvenc') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'av1_nvenc'
            Family                 = 'av1'
            Backend                = 'nvenc'
            RateControlKind        = 'nvenc_cq'
            QualityOffset          = 0
            UsesVbv                = $true
            PresetMap              = @{}
            HdrHandlerKind         = 'libav_side_data'
            SupportsHdr10Metadata  = $true
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @(
                '-pix_fmt', 'p010le',
                '-color_primaries', 'bt2020',
                '-color_trc', 'smpte2084',
                '-colorspace', 'bt2020nc'
            )
            ProbeEncoderName       = 'av1_nvenc'
            FailurePatternKind     = 'nvenc'
            ContainerNotes         = 'Dormant AV1 NVENC descriptor; omits HEVC-style main10 profile flag.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'qsv') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'av1_qsv'
            Family                 = 'av1'
            Backend                = 'qsv'
            RateControlKind        = 'qsv_global_quality'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = $qsvPresetMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'av1_qsv'
            FailurePatternKind     = 'qsv'
            ContainerNotes         = 'Dormant AV1 QSV descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'amf') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'av1_amf'
            Family                 = 'av1'
            Backend                = 'amf'
            RateControlKind        = 'amf_cqp'
            QualityOffset          = 0
            UsesVbv                = $false
            PresetMap              = $amfQualityMap
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'av1_amf'
            FailurePatternKind     = 'amf'
            ContainerNotes         = 'Dormant AV1 AMF descriptor; not selected by the active parity resolver.'
        }
    }

    if ($normalizedFamily -eq 'av1' -and $normalizedBackend -eq 'cpu') {
        return [pscustomobject][ordered]@{
            EncoderName            = 'libaom-av1'
            Family                 = 'av1'
            Backend                = 'cpu'
            RateControlKind        = 'aom_crf'
            QualityOffset          = 2
            UsesVbv                = $false
            PresetMap              = @{
                p1 = '8'
                p2 = '7'
                p3 = '6'
                p4 = '5'
                p5 = '4'
                p6 = '2'
                p7 = '1'
            }
            HdrHandlerKind         = 'none'
            SupportsHdr10Metadata  = $false
            ProfileArgsSdr         = @()
            ProfileArgsHdr         = @()
            ProbeEncoderName       = 'libaom-av1'
            FailurePatternKind     = 'none'
            ContainerNotes         = 'Dormant libaom AV1 descriptor; not selected by the active parity resolver.'
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

function Resolve-MediaEncoderFamilyForCodec {
    param(
        [string] $VideoCodec = ''
    )

    $codec = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $libx265Name = if (Get-Command -Name Get-MediaVideoCodecLibx265Name -ErrorAction SilentlyContinue) {
        (Get-MediaVideoCodecLibx265Name).Trim().ToLowerInvariant()
    } else {
        'libx265'
    }
    if ($codec -eq $libx265Name) { return 'hevc' }
    $familyByCodec = @{
        hevc_nvenc = 'hevc'
        hevc_qsv   = 'hevc'
        hevc_amf   = 'hevc'
        h264_nvenc = 'h264'
        h264_qsv   = 'h264'
        h264_amf   = 'h264'
        libx264    = 'h264'
        av1_nvenc  = 'av1'
        av1_qsv    = 'av1'
        av1_amf    = 'av1'
        'libaom-av1' = 'av1'
        libsvtav1  = 'av1'
    }
    if ($familyByCodec.ContainsKey($codec)) { return [string]$familyByCodec[$codec] }
    return ''
}

function Resolve-MediaEncoderCpuFallbackDescriptor {
    param(
        [string] $VideoCodec = '',
        [bool] $IsHDR = $false
    )

    $family = Resolve-MediaEncoderFamilyForCodec -VideoCodec $VideoCodec
    $result = [pscustomobject][ordered]@{
        Resolved    = $false
        Reason      = ''
        InputCodec  = [string]$VideoCodec
        Family      = [string]$family
        Backend     = 'cpu'
        EncoderName = ''
        IsHDR       = [bool]$IsHDR
        HdrBlocked  = $false
        Descriptor  = $null
    }

    if ([string]::IsNullOrWhiteSpace($family)) {
        $result.Reason = "unsupported encoder family for codec '$VideoCodec'"
        return $result
    }

    $descriptor = Get-MediaEncoderDescriptor -Family $family -Backend 'cpu'
    if ($null -eq $descriptor) {
        $result.Reason = "missing CPU fallback descriptor for family '$family'"
        return $result
    }

    $result.Descriptor = $descriptor
    $result.EncoderName = [string]$descriptor.EncoderName
    if ($IsHDR -and -not [bool]$descriptor.SupportsHdr10Metadata) {
        $result.HdrBlocked = $true
        $result.Reason = "CPU fallback descriptor '$family/cpu' does not support HDR10 metadata preservation"
        return $result
    }

    $result.Resolved = $true
    $result.Reason = "resolved CPU fallback descriptor '$family/cpu'"
    return $result
}

function Get-MediaEncoderDescriptorProbeCacheKey {
    param(
        [Parameter(Mandatory)] $Descriptor,
        [string] $FfmpegPath = '',
        [bool] $SkipRuntimeProbe = $false
    )

    $pathKey = if ($FfmpegPath) { $FfmpegPath.Trim().ToLowerInvariant() } else { '' }
    $probeMode = if ($SkipRuntimeProbe) { 'list' } else { 'runtime' }
    return @(
        ([string]$Descriptor.Family).Trim().ToLowerInvariant(),
        ([string]$Descriptor.Backend).Trim().ToLowerInvariant(),
        ([string]$Descriptor.ProbeEncoderName).Trim().ToLowerInvariant(),
        $probeMode,
        $pathKey
    ) -join '|'
}

function Test-MediaEncoderDescriptorListMatch {
    param(
        [Parameter(Mandatory)] [string] $EncoderListText,
        [Parameter(Mandatory)] $Descriptor
    )

    $probeEncoder = ([string]$Descriptor.ProbeEncoderName).Trim()
    if ([string]::IsNullOrWhiteSpace($probeEncoder)) { return $false }
    $escaped = [regex]::Escape($probeEncoder)
    return ($EncoderListText -match "(?im)^\s*V[\.\w]+\s+$escaped\b")
}

function New-MediaEncoderDescriptorProbeArgumentList {
    param(
        [Parameter(Mandatory)] $Descriptor
    )

    return @(
        '-hide_banner', '-loglevel', 'error',
        '-f', 'lavfi', '-i', 'color=c=black:s=256x144:r=1',
        '-frames:v', '1',
        '-c:v', [string]$Descriptor.ProbeEncoderName,
        '-f', 'null', '-'
    )
}

function Test-MediaEncoderDescriptorAvailable {
    param(
        [Parameter(Mandatory)] $Descriptor,
        [string] $FfmpegPath = $(Get-Variable -Name ffmpegPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [int] $TimeoutSeconds = 15,
        [switch] $Force,
        [switch] $SkipRuntimeProbe
    )

    if (-not $script:EncoderDescriptorCapabilityProbeCache) {
        $script:EncoderDescriptorCapabilityProbeCache = @{}
    }
    $cacheKey = Get-MediaEncoderDescriptorProbeCacheKey -Descriptor $Descriptor -FfmpegPath $FfmpegPath -SkipRuntimeProbe ([bool]$SkipRuntimeProbe)
    if (-not $Force -and $script:EncoderDescriptorCapabilityProbeCache.ContainsKey($cacheKey)) {
        return $script:EncoderDescriptorCapabilityProbeCache[$cacheKey]
    }

    $result = [pscustomobject][ordered]@{
        Available           = $false
        Probed              = $false
        RuntimeProbeSkipped = $false
        Reason              = ''
        EncoderListMatch    = $false
        RuntimeOk           = $false
        EncoderName         = [string]$Descriptor.EncoderName
        Family              = [string]$Descriptor.Family
        Backend             = [string]$Descriptor.Backend
        ProbeEncoderName    = [string]$Descriptor.ProbeEncoderName
        ProbedAt            = (Get-Date).ToString('o')
    }

    if ([string]::IsNullOrWhiteSpace($FfmpegPath) -or -not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
        $result.Reason = "ffmpeg not found at '$FfmpegPath'"
        $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
        return $result
    }

    try {
        $listOut = & $FfmpegPath -hide_banner -encoders 2>&1
        if ($LASTEXITCODE -ne 0) {
            $result.Reason = "ffmpeg -encoders exited $LASTEXITCODE"
            $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
            return $result
        }
        $listText = ($listOut | Out-String)
        $result.EncoderListMatch = Test-MediaEncoderDescriptorListMatch -EncoderListText $listText -Descriptor $Descriptor
        if (-not $result.EncoderListMatch) {
            $result.Reason = "ffmpeg build does not list encoder '$($result.ProbeEncoderName)'"
            $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
            return $result
        }
    } catch {
        $result.Reason = "ffmpeg -encoders threw: $($_.Exception.Message)"
        $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
        return $result
    }

    if ($SkipRuntimeProbe) {
        $result.RuntimeProbeSkipped = $true
        $result.Reason = "encoder '$($result.ProbeEncoderName)' is listed; runtime availability not confirmed because probe was skipped"
        $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
        return $result
    }

    $result.Probed = $true
    try {
        $proc = [System.Diagnostics.Process]::new()
        $psi = [System.Diagnostics.ProcessStartInfo]@{
            FileName               = $FfmpegPath
            UseShellExecute        = $false
            RedirectStandardError  = $true
            RedirectStandardOutput = $true
            CreateNoWindow         = $true
        }
        foreach ($arg in (New-MediaEncoderDescriptorProbeArgumentList -Descriptor $Descriptor)) {
            $psi.ArgumentList.Add([string]$arg)
        }
        $proc.StartInfo = $psi
        [void]$proc.Start()
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        if (-not $proc.WaitForExit([int]([math]::Max(1, $TimeoutSeconds)) * 1000)) {
            try { $proc.Kill() } catch {}
            $result.Reason = "encoder '$($result.ProbeEncoderName)' probe timed out after ${TimeoutSeconds}s"
            $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
            return $result
        }
        $stderrText = ''
        try { $stderrText = $stderrTask.Result } catch {}
        if ($proc.ExitCode -eq 0) {
            $result.RuntimeOk = $true
            $result.Available = $true
            $result.Reason = "encoder '$($result.ProbeEncoderName)' probe succeeded"
        } else {
            $tail = ($stderrText -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
            $result.Reason = "encoder '$($result.ProbeEncoderName)' probe exit $($proc.ExitCode): $tail"
        }
    } catch {
        $result.Reason = "encoder '$($result.ProbeEncoderName)' probe threw: $($_.Exception.Message)"
    }

    $script:EncoderDescriptorCapabilityProbeCache[$cacheKey] = $result
    return $result
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

    if ($IsHDR -and -not [bool]$Descriptor.SupportsHdr10Metadata) {
        throw "Encoder descriptor '$($Descriptor.Family)/$($Descriptor.Backend)' does not support HDR10 metadata preservation."
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
