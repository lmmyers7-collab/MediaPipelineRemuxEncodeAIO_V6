# ==============================================================================
# ops\pipeline\engine\decide\encode_policy.ps1
# ==============================================================================
# Pure encode attempt policy helpers for GPU-first encode and CPU fallback.
#
# These helpers do not read shared state. Callers pass current config values in
# and receive explicit FFmpeg argument lists / attempt metadata back.
# ==============================================================================

$encodePolicyModuleRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $PSCommandPath }
$encoderDescriptorsModule = Join-Path $encodePolicyModuleRoot 'encoder_descriptors.ps1'
if (Test-Path -LiteralPath $encoderDescriptorsModule -PathType Leaf) {
    . $encoderDescriptorsModule
}

function Get-MediaEncodeLadderNames {
    if (Get-Command -Name Get-MediaPipelineEncodeLadderNames -ErrorAction SilentlyContinue) {
        return @(Get-MediaPipelineEncodeLadderNames)
    }
    return @('auto','tv_balanced','tv_space_saver','movie_balanced','movie_archive','plex_compat')
}

function Resolve-MediaEncodeLadderName {
    param(
        [string] $Ladder = 'auto',
        [bool] $IsTV = $false
    )

    $resolved = if (Get-Command -Name Resolve-MediaPipelineEncodeLadder -ErrorAction SilentlyContinue) {
        Resolve-MediaPipelineEncodeLadder -Ladder $Ladder
    } else {
        $text = if ($Ladder) { $Ladder.Trim().ToLowerInvariant() } else { 'auto' }
        if ($text -in (Get-MediaEncodeLadderNames)) { $text } else { 'auto' }
    }
    if ($resolved -eq 'auto') {
        return $(if ($IsTV) { 'tv_balanced' } else { 'movie_balanced' })
    }
    return $resolved
}

function Get-MediaEncodeLadderProfile {
    param(
        [string] $Ladder = 'auto',
        [bool] $IsTV = $false
    )

    $name = Resolve-MediaEncodeLadderName -Ladder $Ladder -IsTV:$IsTV
    switch ($name) {
        'tv_space_saver' {
            return [pscustomobject][ordered]@{
                name            = $name
                description     = 'TV space saver: smaller files for repeatable episodic content'
                quality_delta   = 2
                maxrate         = '80M'
                bufsize         = '160M'
                tuning_preset   = ''
            }
        }
        'movie_archive' {
            return [pscustomobject][ordered]@{
                name            = $name
                description     = 'Movie archive: cleaner encode with larger bitrate allowance'
                quality_delta   = -1
                maxrate         = '160M'
                bufsize         = '320M'
                tuning_preset   = ''
            }
        }
        'plex_compat' {
            return [pscustomobject][ordered]@{
                name            = $name
                description     = 'Plex compatibility: conservative bitrate and safer NVENC flags'
                quality_delta   = 1
                maxrate         = '80M'
                bufsize         = '160M'
                tuning_preset   = 'compatibility'
            }
        }
        'tv_balanced' {
            return [pscustomobject][ordered]@{
                name            = $name
                description     = 'TV balanced: moderate quality target and TV-sized bitrate ceiling'
                quality_delta   = 1
                maxrate         = '90M'
                bufsize         = '180M'
                tuning_preset   = ''
            }
        }
        default {
            return [pscustomobject][ordered]@{
                name            = 'movie_balanced'
                description     = 'Movie balanced: current default quality target and bitrate ceiling'
                quality_delta   = 0
                maxrate         = '120M'
                bufsize         = '240M'
                tuning_preset   = ''
            }
        }
    }
}

function Get-MediaEncodeOutputMuxerName {
    param([string] $OutputPath = '')

    $extension = ''
    if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
        $extension = [System.IO.Path]::GetExtension($OutputPath).TrimStart('.').ToLowerInvariant()
    }
    $mp4Family = if (Get-Command -Name Get-MediaContainerMp4FamilyNames -ErrorAction SilentlyContinue) {
        @(Get-MediaContainerMp4FamilyNames | ForEach-Object { ([string]$_).ToLowerInvariant() })
    } else {
        @('mp4','m4v','mov')
    }
    if (-not [string]::IsNullOrWhiteSpace($extension) -and $mp4Family -contains $extension) {
        return 'mp4'
    }
    return (Get-MediaContainerMuxerMatroskaName)
}

function Get-MediaEncodeBoundedQuality {
    param(
        [int] $Quality,
        [int] $Minimum = 14,
        [int] $Maximum = 32
    )

    return [int]([math]::Min($Maximum, [math]::Max($Minimum, $Quality)))
}

function New-EncodeVideoFlags {
    param(
        [bool] $IsHDR = $false,
        [bool] $IsTV = $false,
        [bool] $UseCpuFallback = $false,
        [bool] $UseSafeHardwareRetry = $false,
        [Parameter(Mandatory)] [string] $VideoCodec,
        [Parameter(Mandatory)] [string] $VideoPreset,
        [Parameter(Mandatory)] [int] $VideoQuality,
        [array] $ExtraVideoFlags = @(),
        [int] $FallbackCpuQuality = 20,
        [string] $EncodeLadder = 'auto',
        [string] $CpuPreset = 'medium',
        # E8 — caller's max thread budget for libx265. 0 = libav default
        # (autodetect, typically all logical cores). >0 = pass -threads N
        # to libav and pools=N:frame-threads=ceil(N/4) to libx265 so the
        # operator can leave headroom for the desktop GUI on small CPUs.
        [int] $CpuMaxThreads = 0,
        # Suggestion #1 — when the source carries HDR10 mastering metadata
        # the caller (Do-Encode) probes it via Get-SourceHdr10MasteringMetadata
        # and passes the formatted x265 strings here. Without these, x265
        # has no master-display / MaxCLL data to emit even with hdr10=1.
        # Empty strings = no metadata found / SDR source / probe failed.
        [string] $Hdr10MasterDisplay = '',
        [string] $Hdr10MaxCll = '',
        [string] $DolbyVisionRpuPath = '',
        [string] $DolbyVisionTargetProfile = '',
        [string] $Hdr10PlusJsonPath = ''
    )

    $dynamicHdrX265Requested = Test-DynamicHdrX265ParameterRequested -DolbyVisionRpuPath $DolbyVisionRpuPath -Hdr10PlusJsonPath $Hdr10PlusJsonPath
    if ($dynamicHdrX265Requested -and -not $UseCpuFallback) {
        throw 'Dynamic HDR x265 parameters are supported only on CPU libx265 encode plans.'
    }
    if ($dynamicHdrX265Requested -and -not $IsHDR) {
        throw 'Dynamic HDR x265 parameters require an HDR encode plan.'
    }

    $descriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec $VideoCodec -UseCpuFallback:$UseCpuFallback
    if ($null -ne $descriptor) {
        return @(New-EncoderVideoFlags `
            -Descriptor $descriptor `
            -IsHDR:$IsHDR `
            -IsTV:$IsTV `
            -UseSafeHardwareRetry:$UseSafeHardwareRetry `
            -VideoCodec $VideoCodec `
            -VideoPreset $VideoPreset `
            -VideoQuality $VideoQuality `
            -ExtraVideoFlags $ExtraVideoFlags `
            -FallbackCpuQuality $FallbackCpuQuality `
            -EncodeLadder $EncodeLadder `
            -CpuPreset $CpuPreset `
            -CpuMaxThreads $CpuMaxThreads `
            -Hdr10MasterDisplay $Hdr10MasterDisplay `
            -Hdr10MaxCll $Hdr10MaxCll `
            -DolbyVisionRpuPath $DolbyVisionRpuPath `
            -DolbyVisionTargetProfile $DolbyVisionTargetProfile `
            -Hdr10PlusJsonPath $Hdr10PlusJsonPath)
    }

    $ladderProfile = Get-MediaEncodeLadderProfile -Ladder $EncodeLadder -IsTV:$IsTV
    $effectiveVideoQuality = Get-MediaEncodeBoundedQuality -Quality ([int]$VideoQuality + [int]$ladderProfile.quality_delta)
    # CRF and CQ scales are not equivalent. Apply only half the NVENC ladder
    # delta to libx265 -crf so a "+1 quality_delta" doesn't shift bitrate ~15%
    # on CPU but only ~3% on NVENC.
    # D1 fix — Math::Round defaults to banker's rounding (ToEven), which maps
    # 0.5/-0.5 to 0 and would silently zero the delta for the +1/-1 ladders
    # (tv_balanced, plex_compat, movie_archive — i.e. 3 of the 5 named
    # ladders). Force AwayFromZero so 0.5 -> 1 and -0.5 -> -1.
    $cpuLadderDelta = [int][math]::Round([double]$ladderProfile.quality_delta / 2.0, [System.MidpointRounding]::AwayFromZero)
    $effectiveCpuQuality = Get-MediaEncodeBoundedQuality -Quality ([int]$FallbackCpuQuality + $cpuLadderDelta)
    $maxrate = [string]$ladderProfile.maxrate
    $bufsize = [string]$ladderProfile.bufsize
    $effectiveExtraVideoFlags = @($ExtraVideoFlags)
    if ($UseSafeHardwareRetry -or ([string]$ladderProfile.tuning_preset -eq 'compatibility')) {
        if (Get-Command -Name Get-MediaPipelineEncodeTuningFlags -ErrorAction SilentlyContinue) {
            $effectiveExtraVideoFlags = @(
                Get-MediaPipelineEncodeTuningFlags -Preset 'compatibility' -Codec $VideoCodec -LegacyExtraVideoFlags @()
            )
        }
    }

    if ($UseCpuFallback) {
        # libx265 -crf already implements rate control. Passing -maxrate /
        # -bufsize alongside -crf silently switches it into constrained-CRF and
        # emits a warning. Drop the VBV pair on CPU and keep only the quality
        # target. master-display / max-cll metadata is not extracted here; the
        # caller is responsible for appending a second -x265-params entry with
        # those values when ffprobe surfaces them.
        $resolvedCpuPreset = if (Get-Command -Name Resolve-MediaPipelineCpuEncodePreset -ErrorAction SilentlyContinue) {
            Resolve-MediaPipelineCpuEncodePreset -Preset $CpuPreset
        } else {
            $textPreset = if ($CpuPreset) { $CpuPreset.Trim().ToLowerInvariant() } else { '' }
            if ([string]::IsNullOrWhiteSpace($textPreset)) { 'medium' } else { $textPreset }
        }
        $x265ParamPairs = [System.Collections.Generic.List[string]]::new()
        $x265ParamPairs.Add('log-level=error')
        # E8 — bound libx265 thread pool when the operator asks for it.
        # Without this libx265 spawns one frame thread per (cores/4) and
        # one pool thread per logical core, which on an 8-core box pins
        # everything and starves the desktop GUI even at BelowNormal.
        if ($CpuMaxThreads -gt 0) {
            $frameThreads = [int][math]::Max(1, [math]::Ceiling([double]$CpuMaxThreads / 4.0))
            $x265ParamPairs.Add("pools=$CpuMaxThreads")
            $x265ParamPairs.Add("frame-threads=$frameThreads")
        }
        if ($IsHDR) {
            # Tell libx265 to emit HDR10 SEI/VUI consistent with the source's
            # transfer/colorspace and to repeat headers so segment-aware Plex
            # transcoders can still tone-map.
            $x265ParamPairs.Add('hdr10=1')
            $x265ParamPairs.Add('hdr10-opt=1')
            $x265ParamPairs.Add('repeat-headers=1')
            $x265ParamPairs.Add('colorprim=bt2020')
            $x265ParamPairs.Add('transfer=smpte2084')
            $x265ParamPairs.Add('colormatrix=bt2020nc')
            # Suggestion #1 — feed real source mastering display / MaxCLL
            # to x265. The bare hdr10=1 / hdr10-opt=1 / repeat-headers=1
            # only tells x265 to honor whatever side-data libav surfaces;
            # libav typically does NOT pass it through stream-copy or via
            # the encoder bridge for libx265. The result without these
            # explicit strings: BluRay HDR10 sources lose their
            # mastering metadata on CPU encode. Plex tone-maps to SDR or
            # falls back to transcode for HDR-capable clients.
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
        $flags = @(
            '-c:v', (Get-MediaVideoCodecLibx265Name),
            '-preset', $resolvedCpuPreset,
            '-crf', $effectiveCpuQuality
        )
        if ($IsHDR -and -not [string]::IsNullOrWhiteSpace($DolbyVisionRpuPath)) {
            $flags += @('-dolbyvision', 'true')
        }
        # libav side: also cap the global thread count when bounded.
        if ($CpuMaxThreads -gt 0) {
            $flags += @('-threads', [string]$CpuMaxThreads)
        }
        $flags += @('-x265-params', ($x265ParamPairs -join ':'))
    } else {
        $flags = @(
            '-c:v', $VideoCodec, '-preset', $VideoPreset, '-cq', $effectiveVideoQuality,
            '-maxrate', $maxrate, '-bufsize', $bufsize
        ) + @($effectiveExtraVideoFlags)
    }

    if ($IsHDR) {
        # D6 fix — On the CPU branch, libx265 already carries colorprim /
        # transfer / colormatrix in -x265-params, so the libav-side
        # -color_* flags are redundant (and risk drift if one is changed
        # without the other).  On the GPU branch NVENC consumes the libav
        # color metadata, so we still emit it there.
        if ($UseCpuFallback) {
            $flags += @('-profile:v', 'main10', '-pix_fmt', 'p010le')
        } else {
            $flags += @(
                '-profile:v', 'main10', '-pix_fmt', 'p010le',
                '-color_primaries', 'bt2020',
                '-color_trc', 'smpte2084',
                '-colorspace', 'bt2020nc'
            )
        }
    } else {
        $flags += @('-profile:v', 'main')
    }

    return @($flags)
}

function New-EncodeFfmpegArgumentList {
    param(
        [Parameter(Mandatory)] [string] $InputPath,
        [array] $ExtraInputs = @(),
        [Parameter(Mandatory)] [string] $GlobalTitle,
        [Parameter(Mandatory)] [array] $VideoFlags,
        [array] $VideoFilterArgs = @(),
        [array] $AudioArgs = @(),
        [array] $SubtitleMapArgs = @(),
        [Parameter(Mandatory)] [string] $OutputPath
    )

    $muxerName = Get-MediaEncodeOutputMuxerName -OutputPath $OutputPath
    $isMp4Output = ($muxerName -eq 'mp4')
    $videoMapArgs = if (@($VideoFilterArgs).Count -gt 0) {
        @($VideoFilterArgs)
    } else {
        @(
            # 0:V maps only non-attached-picture video streams. Lowercase 0:v
            # would include embedded cover art and can fail encoders.
            '-map', '0:V'
        )
    }
    $containerMetadataArgs = if ($isMp4Output) {
        @(
            '-map_chapters', '-1',
            '-map_metadata', '-1'
        )
    } else {
        @(
            '-map', '0:t?',
            '-map_chapters', '0',
            '-map_metadata', '0',
            '-metadata', "title=$GlobalTitle"
        )
    }
    $attachmentArgs = if ($isMp4Output) { @() } else { @('-c:t', 'copy') }
    $muxerArgs = @('-f', $muxerName)
    if ($isMp4Output) {
        $muxerArgs += @('-movflags', '+faststart')
    }
    return @('-i', $InputPath) + @($ExtraInputs) + @($videoMapArgs) + @($containerMetadataArgs) +
        @($VideoFlags) + @($AudioArgs) + @($SubtitleMapArgs) + @($attachmentArgs) + @($muxerArgs) + @(
            '-max_muxing_queue_size', '1024',
            '-y',
            $OutputPath
        )
}

function New-EncodeWasteGuardSampleArgumentList {
    param(
        [Parameter(Mandatory)] [string] $InputPath,
        [Parameter(Mandatory)] [array] $VideoFlags,
        [array] $VideoFilterArgs = @(),
        [Parameter(Mandatory)] [string] $OutputPath,
        [double] $StartSeconds = 0,
        [double] $SampleSeconds = 30
    )

    if ($StartSeconds -lt 0) { $StartSeconds = 0 }
    if ($SampleSeconds -le 0) { $SampleSeconds = 30 }
    $muxerName = Get-MediaEncodeOutputMuxerName -OutputPath $OutputPath
    $videoMapArgs = if (@($VideoFilterArgs).Count -gt 0) {
        @($VideoFilterArgs)
    } else {
        @('-map', '0:V')
    }
    $muxerArgs = @('-f', $muxerName)
    if ($muxerName -eq 'mp4') {
        $muxerArgs += @('-movflags', '+faststart')
    }
    return @(
        '-ss', ([string]([math]::Round([double]$StartSeconds, 3))),
        '-t', ([string]([math]::Round([double]$SampleSeconds, 3))),
        '-i', $InputPath
    ) + @($videoMapArgs) + @($VideoFlags) + @(
        '-an',
        '-sn',
        '-dn',
        '-map_chapters', '-1',
        '-map_metadata', '-1'
    ) + @($muxerArgs) + @(
        '-max_muxing_queue_size', '1024',
        '-y',
        $OutputPath
    )
}

function Get-EncodeArgumentValue {
    param(
        [array] $Arguments = @(),
        [Parameter(Mandatory)] [string] $Name
    )
    for ($i = 0; $i -lt @($Arguments).Count - 1; $i++) {
        if ([string]$Arguments[$i] -eq $Name) { return [string]$Arguments[$i + 1] }
    }
    return ''
}

function Get-EncodeEncoderKind {
    param(
        [string] $Encoder = '',
        [bool] $UseCpuFallback = $false
    )
    if ($UseCpuFallback) { return 'cpu' }
    $normalized = if ($Encoder) { $Encoder.Trim().ToLowerInvariant() } else { '' }
    if ($normalized -match 'nvenc') { return 'nvenc' }
    if ($normalized -match 'amf') { return 'amf' }
    if ($normalized -match 'qsv') { return 'qsv' }
    if ($normalized -match 'x26[45]|libx26[45]') { return 'cpu' }
    if ($normalized -match 'libaom|aom|svtav1|libsvtav1') { return 'cpu' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return 'unknown' }
    return 'software_or_unknown'
}

function Get-EncodeSelectedGpuDevice {
    param([array] $VideoFlags = @())
    $gpu = Get-EncodeArgumentValue -Arguments $VideoFlags -Name '-gpu'
    if (-not [string]::IsNullOrWhiteSpace($gpu)) { return $gpu }
    $hwDevice = Get-EncodeArgumentValue -Arguments $VideoFlags -Name '-hwaccel_device'
    if (-not [string]::IsNullOrWhiteSpace($hwDevice)) { return $hwDevice }
    return ''
}

function New-EncodeAttemptDescriptorSelectionEvidence {
    param(
        [string] $VideoCodec = '',
        [bool] $UseCpuFallback = $false,
        [bool] $IsHDR = $false,
        [string] $SelectedEncoder = ''
    )

    $role = if ($UseCpuFallback) { 'cpu_fallback' } else { 'primary' }
    $evidence = [ordered]@{
        Active             = $false
        Resolved           = $false
        Role               = $role
        VideoCodec         = [string]$VideoCodec
        SelectedEncoder    = [string]$SelectedEncoder
        Family             = ''
        PrimaryEncoder     = ''
        CpuFallbackEncoder = ''
        DescriptorBackend  = ''
        DescriptorEncoder  = ''
        Reason             = ''
        ResolutionTrace    = @()
    }

    if (-not (Get-Command -Name Resolve-MediaEncoderSelection -ErrorAction SilentlyContinue)) {
        $evidence.Reason = 'descriptor selection resolver unavailable'
        return [pscustomobject]$evidence
    }

    $selection = Resolve-MediaEncoderSelection -VideoCodec $VideoCodec -IsHDR:$IsHDR
    $evidence.Resolved = [bool]$selection.Resolved
    $evidence.Family = [string]$selection.Family
    $evidence.Reason = [string]$selection.Reason
    $evidence.ResolutionTrace = @($selection.ResolutionTrace)
    if ($selection.PrimaryDescriptor) {
        $evidence.PrimaryEncoder = [string]$selection.PrimaryDescriptor.EncoderName
    }
    if ($selection.CpuFallbackDescriptor) {
        $evidence.CpuFallbackEncoder = [string]$selection.CpuFallbackDescriptor.EncoderName
    }
    if (-not [bool]$selection.Resolved) {
        return [pscustomobject]$evidence
    }

    $attemptDescriptor = if ($UseCpuFallback) { $selection.CpuFallbackDescriptor } else { $selection.PrimaryDescriptor }
    if ($null -eq $attemptDescriptor) {
        $evidence.Reason = "descriptor selection did not provide a $role descriptor"
        return [pscustomobject]$evidence
    }
    $evidence.DescriptorBackend = [string]$attemptDescriptor.Backend
    $evidence.DescriptorEncoder = [string]$attemptDescriptor.EncoderName

    $activeFlagsDescriptor = $null
    if (Get-Command -Name Resolve-MediaEncoderDescriptorForFlags -ErrorAction SilentlyContinue) {
        $activeFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec $VideoCodec -UseCpuFallback:$UseCpuFallback
    }
    if ($null -eq $activeFlagsDescriptor) {
        $evidence.Reason = "descriptor flags are not active for $role attempt"
        return [pscustomobject]$evidence
    }

    $selected = if ($SelectedEncoder) { $SelectedEncoder.Trim().ToLowerInvariant() } else { '' }
    $attemptEncoder = ([string]$attemptDescriptor.EncoderName).Trim().ToLowerInvariant()
    $activeEncoder = ([string]$activeFlagsDescriptor.EncoderName).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($selected) -or $selected -ne $attemptEncoder -or $selected -ne $activeEncoder) {
        $evidence.Reason = "selected encoder '$SelectedEncoder' does not match descriptor-owned $role encoder '$($attemptDescriptor.EncoderName)'"
        return [pscustomobject]$evidence
    }

    $evidence.Active = $true
    $evidence.Reason = "attempt uses descriptor-owned $($attemptDescriptor.Family)/$($attemptDescriptor.Backend) selection"
    return [pscustomobject]$evidence
}

function Resolve-MediaEncoderActivationReadiness {
    param(
        [string] $VideoCodec = '',
        [bool] $UseCpuFallback = $false,
        [bool] $IsHDR = $false
    )

    $role = if ($UseCpuFallback) { 'cpu_fallback' } else { 'primary' }
    $result = [ordered]@{
        ok                    = $false
        schema_version        = 'encoder_activation_readiness.v1'
        video_codec           = [string]$VideoCodec
        role                  = $role
        is_hdr                = [bool]$IsHDR
        family                = ''
        primary_encoder       = ''
        cpu_fallback_encoder  = ''
        descriptor_backend    = ''
        descriptor_encoder    = ''
        active                = $false
        reason                = ''
        error_code            = ''
        resolution_trace      = @()
    }

    if (-not (Get-Command -Name Resolve-MediaEncoderSelection -ErrorAction SilentlyContinue)) {
        $result.reason = 'encoder descriptor selection resolver is unavailable'
        $result.error_code = 'ENCODE_ENCODER_UNSUPPORTED'
        return [pscustomobject]$result
    }

    $selection = Resolve-MediaEncoderSelection -VideoCodec $VideoCodec -IsHDR:$IsHDR
    $result.family = [string]$selection.Family
    $result.resolution_trace = @($selection.ResolutionTrace)
    if ($selection.PrimaryDescriptor) {
        $result.primary_encoder = [string]$selection.PrimaryDescriptor.EncoderName
    }
    if ($selection.CpuFallbackDescriptor) {
        $result.cpu_fallback_encoder = [string]$selection.CpuFallbackDescriptor.EncoderName
    }
    if (-not [bool]$selection.Resolved) {
        $result.reason = if ([string]::IsNullOrWhiteSpace([string]$selection.Reason)) {
            "encoder '$VideoCodec' is not supported by the descriptor resolver"
        } else {
            [string]$selection.Reason
        }
        $result.error_code = if ($IsHDR -and $result.reason -match 'HDR10|metadata preservation|does not support') {
            'ENCODE_ENCODER_HDR_UNSUPPORTED'
        } else {
            'ENCODE_ENCODER_UNSUPPORTED'
        }
        return [pscustomobject]$result
    }

    $attemptDescriptor = if ($UseCpuFallback) { $selection.CpuFallbackDescriptor } else { $selection.PrimaryDescriptor }
    if ($null -eq $attemptDescriptor) {
        $result.reason = "encoder descriptor selection did not provide a $role descriptor for '$VideoCodec'"
        $result.error_code = 'ENCODE_ENCODER_UNSUPPORTED'
        return [pscustomobject]$result
    }
    $result.descriptor_backend = [string]$attemptDescriptor.Backend
    $result.descriptor_encoder = [string]$attemptDescriptor.EncoderName

    $activeFlagsDescriptor = $null
    if (Get-Command -Name Resolve-MediaEncoderDescriptorForFlags -ErrorAction SilentlyContinue) {
        $activeFlagsDescriptor = Resolve-MediaEncoderDescriptorForFlags -VideoCodec $VideoCodec -UseCpuFallback:$UseCpuFallback
    }
    if ($null -eq $activeFlagsDescriptor) {
        $result.reason = "encoder '$VideoCodec' is cataloged as $($attemptDescriptor.Family)/$($attemptDescriptor.Backend), but descriptor-owned flags are not active for $role encode attempts"
        $result.error_code = 'ENCODE_ENCODER_NOT_ACTIVE'
        return [pscustomobject]$result
    }

    $attemptEncoder = ([string]$attemptDescriptor.EncoderName).Trim().ToLowerInvariant()
    $activeEncoder = ([string]$activeFlagsDescriptor.EncoderName).Trim().ToLowerInvariant()
    if ($attemptEncoder -ne $activeEncoder) {
        $result.reason = "active descriptor encoder '$($activeFlagsDescriptor.EncoderName)' does not match selected $role descriptor '$($attemptDescriptor.EncoderName)'"
        $result.error_code = 'ENCODE_ENCODER_UNSUPPORTED'
        return [pscustomobject]$result
    }

    $result.active = $true
    $result.ok = $true
    $result.reason = "encoder '$VideoCodec' is active for $role descriptor-owned flags"
    return [pscustomobject]$result
}

function New-EncodeAttemptPlan {
    param(
        [bool] $UseCpuFallback = $false,
        [bool] $UseSafeHardwareRetry = $false,
        [bool] $IsTV = $false,
        [bool] $IsHDR = $false,
        [Parameter(Mandatory)] [string] $InputPath,
        [array] $ExtraInputs = @(),
        [Parameter(Mandatory)] [string] $GlobalTitle,
        [array] $AudioArgs = @(),
        [array] $SubtitleMapArgs = @(),
        [array] $VideoFilterArgs = @(),
        [Parameter(Mandatory)] [string] $OutputPath,
        [Parameter(Mandatory)] [string] $VideoCodec,
        [Parameter(Mandatory)] [string] $VideoPreset,
        [Parameter(Mandatory)] [int] $VideoQuality,
        [array] $ExtraVideoFlags = @(),
        [int] $FallbackCpuQuality = 20,
        [string] $EncodeLadder = 'auto',
        [string] $CpuPreset = 'medium',
        [int] $CpuMaxThreads = 0,
        # Suggestion #1 — HDR10 mastering metadata extracted from the
        # source by Get-SourceHdr10MasteringMetadata. Forwarded to
        # New-EncodeVideoFlags only when UseCpuFallback (NVENC reads
        # mastering metadata from libav side-data on its own). Empty
        # strings are no-ops.
        [string] $Hdr10MasterDisplay = '',
        [string] $Hdr10MaxCll = '',
        # Dynamic HDR preservation artifacts are supplied only after a
        # backend-owned extraction step. They are no-ops when blank and are
        # guarded by New-EncodeVideoFlags so NVENC and non-HDR paths cannot
        # accidentally receive x265-only parameters.
        [string] $DolbyVisionRpuPath = '',
        [string] $DolbyVisionTargetProfile = '',
        [string] $Hdr10PlusJsonPath = ''
    )

    $ladderProfile = Get-MediaEncodeLadderProfile -Ladder $EncodeLadder -IsTV:$IsTV
    $videoFlags = New-EncodeVideoFlags `
        -IsHDR:$IsHDR `
        -IsTV:$IsTV `
        -UseCpuFallback:$UseCpuFallback `
        -UseSafeHardwareRetry:$UseSafeHardwareRetry `
        -VideoCodec $VideoCodec `
        -VideoPreset $VideoPreset `
        -VideoQuality $VideoQuality `
        -ExtraVideoFlags $ExtraVideoFlags `
        -FallbackCpuQuality $FallbackCpuQuality `
        -EncodeLadder $EncodeLadder `
        -CpuPreset $CpuPreset `
        -CpuMaxThreads $CpuMaxThreads `
        -Hdr10MasterDisplay $Hdr10MasterDisplay `
        -Hdr10MaxCll $Hdr10MaxCll `
        -DolbyVisionRpuPath $DolbyVisionRpuPath `
        -DolbyVisionTargetProfile $DolbyVisionTargetProfile `
        -Hdr10PlusJsonPath $Hdr10PlusJsonPath

    $argumentList = New-EncodeFfmpegArgumentList `
        -InputPath $InputPath `
        -ExtraInputs $ExtraInputs `
        -GlobalTitle $GlobalTitle `
        -VideoFlags $videoFlags `
        -VideoFilterArgs $VideoFilterArgs `
        -AudioArgs $AudioArgs `
        -SubtitleMapArgs $SubtitleMapArgs `
        -OutputPath $OutputPath

    $selectedEncoder = Get-EncodeArgumentValue -Arguments $videoFlags -Name '-c:v'
    if ([string]::IsNullOrWhiteSpace($selectedEncoder)) {
        $selectedEncoder = if ($UseCpuFallback) { Get-MediaVideoCodecLibx265Name } else { $VideoCodec }
    }
    $encoderKind = Get-EncodeEncoderKind -Encoder $selectedEncoder -UseCpuFallback:$UseCpuFallback
    # CPU encodes never bind to a GPU device. Force-clear so sidecar telemetry
    # does not falsely attribute a CPU encode to GPU 0 when an earlier hardware
    # attempt left -gpu/-hwaccel_device tokens in argv parsers' memory.
    $selectedGpuDevice = if ($UseCpuFallback) { '' } else { Get-EncodeSelectedGpuDevice -VideoFlags $videoFlags }
    $descriptorSelection = New-EncodeAttemptDescriptorSelectionEvidence `
        -VideoCodec $VideoCodec `
        -UseCpuFallback:$UseCpuFallback `
        -IsHDR:$IsHDR `
        -SelectedEncoder $selectedEncoder
    $resolvedCpuPreset = if (Get-Command -Name Resolve-MediaPipelineCpuEncodePreset -ErrorAction SilentlyContinue) {
        Resolve-MediaPipelineCpuEncodePreset -Preset $CpuPreset
    } else {
        $CpuPreset
    }

    if ($UseCpuFallback) {
        return [pscustomobject]@{
            Attempt        = 'cpu_fallback'
            UseCpuFallback = $true
            UseSafeHardwareRetry = $false
            Route          = Get-MediaRouteEncodeCpuFallbackName
            Label          = 'ENCODE-CPU'
            ProgressStage  = 'encode_cpu'
            ProgressRoute  = 'encode'
            ReproStage     = 'encode-cpu'
            EncodeLadder   = [string]$ladderProfile.name
            EncodeLadderProfile = $ladderProfile
            SelectedEncoder = $selectedEncoder
            EncoderKind     = $encoderKind
            SelectedGpuDevice = $selectedGpuDevice
            DescriptorSelection = $descriptorSelection
            VideoFlags     = @($videoFlags)
            ArgumentList   = @($argumentList)
            CpuPreset      = [string]$resolvedCpuPreset
        }
    }

    if ($UseSafeHardwareRetry) {
        return [pscustomobject]@{
            Attempt        = 'hardware_safe_retry'
            UseCpuFallback = $false
            UseSafeHardwareRetry = $true
            Route          = Get-MediaRouteEncodeName
            Label          = 'ENCODE-SAFE'
            ProgressStage  = 'encode_safe'
            ProgressRoute  = 'encode'
            ReproStage     = 'encode-safe'
            EncodeLadder   = [string]$ladderProfile.name
            EncodeLadderProfile = $ladderProfile
            SelectedEncoder = $selectedEncoder
            EncoderKind     = $encoderKind
            SelectedGpuDevice = $selectedGpuDevice
            DescriptorSelection = $descriptorSelection
            VideoFlags     = @($videoFlags)
            ArgumentList   = @($argumentList)
            # D4 fix — keep CpuPreset on every plan shape so consumers
            # iterating $plan.CpuPreset don't NRE on non-CPU rows.
            CpuPreset      = ''
        }
    }

    return [pscustomobject]@{
        Attempt        = 'primary'
        UseCpuFallback = $false
        UseSafeHardwareRetry = $false
        Route          = Get-MediaRouteEncodeName
        Label          = 'ENCODE'
        ProgressStage  = 'encode'
        ProgressRoute  = 'encode'
        ReproStage     = 'encode'
        EncodeLadder   = [string]$ladderProfile.name
        EncodeLadderProfile = $ladderProfile
        SelectedEncoder = $selectedEncoder
        EncoderKind     = $encoderKind
        SelectedGpuDevice = $selectedGpuDevice
        DescriptorSelection = $descriptorSelection
        VideoFlags     = @($videoFlags)
        ArgumentList   = @($argumentList)
        # D4 fix — keep CpuPreset on every plan shape so consumers iterating
        # $plan.CpuPreset don't NRE on non-CPU rows.
        CpuPreset      = ''
    }
}

function Test-NvencEncoderListMatch {
    param(
        [string] $EncoderListText = '',
        [string] $TestEncoder = 'hevc_nvenc'
    )

    $descriptor = Resolve-NvencProbeDescriptor -TestEncoder $TestEncoder
    if (Get-Command -Name Test-MediaEncoderDescriptorListMatch -ErrorAction SilentlyContinue) {
        return (Test-MediaEncoderDescriptorListMatch -EncoderListText ([string]$EncoderListText) -Descriptor $descriptor)
    }

    $escapedEncoder = [regex]::Escape(([string]$descriptor.ProbeEncoderName))
    return ([string]$EncoderListText -match "(?im)^\s*V[\.\w]+\s+$escapedEncoder\b")
}

function Resolve-NvencProbeDescriptor {
    param(
        [string] $TestEncoder = 'hevc_nvenc'
    )

    $encoder = if ($TestEncoder) { $TestEncoder.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($encoder)) { $encoder = 'hevc_nvenc' }

    $family = if (Get-Command -Name Resolve-MediaEncoderFamilyForCodec -ErrorAction SilentlyContinue) {
        Resolve-MediaEncoderFamilyForCodec -VideoCodec $encoder
    } else {
        ''
    }
    if ([string]::IsNullOrWhiteSpace($family)) {
        $family = 'unknown'
    }

    if ($family -ne 'unknown' -and (Get-Command -Name Get-MediaEncoderDescriptor -ErrorAction SilentlyContinue)) {
        $descriptor = Get-MediaEncoderDescriptor -Family $family -Backend 'nvenc'
        if ($descriptor -and ([string]$descriptor.ProbeEncoderName).Trim().ToLowerInvariant() -eq $encoder) {
            return $descriptor
        }
    }

    return [pscustomobject][ordered]@{
        EncoderName           = $encoder
        Family                = $family
        Backend               = 'nvenc'
        ProbeEncoderName      = $encoder
        SupportsHdr10Metadata = $false
    }
}

function Convert-DescriptorProbeToNvencProbeResult {
    param(
        [Parameter(Mandatory)] $ProbeResult,
        [Parameter(Mandatory)] $Descriptor,
        [string] $FfmpegPath = ''
    )

    return [pscustomobject][ordered]@{
        Available           = [bool]$ProbeResult.Available
        Probed              = [bool]$ProbeResult.Probed
        Reason              = [string]$ProbeResult.Reason
        EncoderListMatch    = [bool]$ProbeResult.EncoderListMatch
        RuntimeOk           = [bool]$ProbeResult.RuntimeOk
        ProbedAt            = if ($ProbeResult.PSObject.Properties['ProbedAt']) { [string]$ProbeResult.ProbedAt } else { (Get-Date).ToString('o') }
        RuntimeProbeSkipped = if ($ProbeResult.PSObject.Properties['RuntimeProbeSkipped']) { [bool]$ProbeResult.RuntimeProbeSkipped } else { $false }
        EncoderName         = if ($ProbeResult.PSObject.Properties['EncoderName']) { [string]$ProbeResult.EncoderName } else { [string]$Descriptor.EncoderName }
        Family              = if ($ProbeResult.PSObject.Properties['Family']) { [string]$ProbeResult.Family } else { [string]$Descriptor.Family }
        Backend             = if ($ProbeResult.PSObject.Properties['Backend']) { [string]$ProbeResult.Backend } else { [string]$Descriptor.Backend }
        ProbeEncoderName    = if ($ProbeResult.PSObject.Properties['ProbeEncoderName']) { [string]$ProbeResult.ProbeEncoderName } else { [string]$Descriptor.ProbeEncoderName }
        FfmpegPath          = [string]$FfmpegPath
        DescriptorProbeCache = $true
    }
}

function Test-NvencAvailable {
    <#
    .SYNOPSIS
    F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on
    this host, and cache the answer for the run.

    .DESCRIPTION
    Legacy wrapper over the descriptor-backed two-step probe: (1)
    `ffmpeg -encoders` must list the configured NVENC test encoder; (2)
    a 1-frame null encode with that descriptor verifies the driver and a
    usable GPU are present, which `-encoders` does not check.

    Returns a [pscustomobject] with:
      - Available  [bool]     final answer
      - Probed     [bool]     whether we reached the runtime probe
      - Reason     [string]   short human-readable cause
      - EncoderListMatch [bool]
      - RuntimeOk  [bool]

    The result is cached in `$script:NvencAvailableProbe` for the lifetime
    of the run. Pass -Force to re-probe.
    #>
    param(
        [string] $FfmpegPath = $script:ffmpegPath,
        [string] $TestEncoder = 'hevc_nvenc',
        [int]    $TimeoutSeconds = 15,
        [switch] $Force
    )

    $testEncoderName = if ($TestEncoder) { $TestEncoder.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($testEncoderName)) { $testEncoderName = 'hevc_nvenc' }
    $ffmpegPathKey = if ($FfmpegPath) { $FfmpegPath.Trim().ToLowerInvariant() } else { '' }

    if (-not $Force -and $script:NvencAvailableProbe) {
        if ($script:NvencAvailableProbe.PSObject.Properties['InvalidatedAt']) {
            return $script:NvencAvailableProbe
        }

        $cachedProbeEncoder = if ($script:NvencAvailableProbe.PSObject.Properties['ProbeEncoderName']) { ([string]$script:NvencAvailableProbe.ProbeEncoderName).Trim().ToLowerInvariant() } else { '' }
        $cachedFfmpegPath = if ($script:NvencAvailableProbe.PSObject.Properties['FfmpegPath']) { ([string]$script:NvencAvailableProbe.FfmpegPath).Trim().ToLowerInvariant() } else { '' }
        if ([string]::IsNullOrWhiteSpace($cachedProbeEncoder) -or ($cachedProbeEncoder -eq $testEncoderName -and $cachedFfmpegPath -eq $ffmpegPathKey)) {
            return $script:NvencAvailableProbe
        }
    }

    $descriptor = Resolve-NvencProbeDescriptor -TestEncoder $testEncoderName
    $probeArgs = @{
        Descriptor     = $descriptor
        FfmpegPath     = $FfmpegPath
        TimeoutSeconds = $TimeoutSeconds
    }
    if ($Force) { $probeArgs['Force'] = $true }

    $probeResult = Test-MediaEncoderDescriptorAvailable @probeArgs
    $script:NvencAvailableProbe = Convert-DescriptorProbeToNvencProbeResult -ProbeResult $probeResult -Descriptor $descriptor -FfmpegPath $FfmpegPath
    return $script:NvencAvailableProbe
}

function Invalidate-NvencAvailableProbe {
    <#
    .SYNOPSIS
    Mark the cached NVENC probe as unavailable after a runtime failure.

    .DESCRIPTION
    `Test-NvencAvailable` runs once at startup. Without this helper, a GPU
    that dies mid-run (driver crash, eGPU disconnect, Windows update) keeps
    causing every subsequent file to attempt NVENC primary + safe-retry
    before falling back. Once the second hardware-encoder failure has
    fired in `Do-Encode`, call this helper so the next file's
    `Do-Encode` sees `$script:NvencAvailableProbe.Available -eq $false`
    and goes directly to a CPU plan.

    The cache is in-memory ($script: scope) so a pipeline restart
    re-probes from scratch — operators who reboot to fix a flaky GPU
    don't need to clear anything by hand.
    #>
    param(
        [string] $Reason = '',
        [string] $SourcePath = ''
    )

    $previous = if ($script:NvencAvailableProbe) { [bool]$script:NvencAvailableProbe.Available } else { $true }
    $previousProbeEncoder = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.PSObject.Properties['ProbeEncoderName']) { [string]$script:NvencAvailableProbe.ProbeEncoderName } else { 'hevc_nvenc' }
    $previousFfmpegPath = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.PSObject.Properties['FfmpegPath']) { [string]$script:NvencAvailableProbe.FfmpegPath } else { '' }
    $previousFamily = if (Get-Command -Name Resolve-MediaEncoderFamilyForCodec -ErrorAction SilentlyContinue) {
        Resolve-MediaEncoderFamilyForCodec -VideoCodec $previousProbeEncoder
    } else {
        ''
    }
    $invalidationReason = if ([string]::IsNullOrWhiteSpace($Reason)) { 'NVENC failed at runtime; probe cache invalidated' } else { $Reason }
    $backendInvalidation = if (Get-Command -Name Invalidate-EncoderBackendProbe -ErrorAction SilentlyContinue) {
        Invalidate-EncoderBackendProbe -Backend 'nvenc' -Reason $invalidationReason -SourcePath $SourcePath -Trigger 'runtime_nvenc_failure'
    } else {
        $null
    }
    $script:NvencAvailableProbe = [pscustomobject]@{
        Available            = $false
        Probed               = $true
        Reason               = $invalidationReason
        EncoderListMatch     = $false
        RuntimeOk            = $false
        ProbedAt             = (Get-Date).ToString('o')
        RuntimeProbeSkipped  = $false
        EncoderName          = $previousProbeEncoder
        Family               = $previousFamily
        Backend              = 'nvenc'
        ProbeEncoderName     = $previousProbeEncoder
        FfmpegPath           = $previousFfmpegPath
        DescriptorProbeCache = $true
        BackendInvalidated   = $true
        InvalidatedAt        = if ($backendInvalidation -and $backendInvalidation.PSObject.Properties['InvalidatedAt']) { [string]$backendInvalidation.InvalidatedAt } else { (Get-Date).ToString('o') }
        Trigger              = 'runtime_nvenc_failure'
    }

    if ($previous -and -not $backendInvalidation) {
        Write-Log "NVENC probe cache invalidated: $($script:NvencAvailableProbe.Reason)" "WARN"
        if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
            Write-PipelineEvent -EventType 'gpu_unavailable' -Stage 'encode' -Status 'warn' -SourcePath $SourcePath -Data @{
                trigger = 'runtime_nvenc_failure'
                reason  = [string]$script:NvencAvailableProbe.Reason
                backend = 'nvenc'
            } | Out-Null
        }
    }
}

function Test-NvencProbeReportsAvailable {
    <#
    .SYNOPSIS
    Returns $true when the cached NVENC probe believes NVENC is usable.

    Default ($null cache) is $true so the first encode attempt still
    runs the normal GPU-first ladder. Once `Invalidate-NvencAvailableProbe`
    has been called, this returns $false and `Do-Encode` skips the
    GPU/safe-retry attempts entirely.
    #>
    if (-not $script:NvencAvailableProbe) { return $true }
    return [bool]$script:NvencAvailableProbe.Available
}

function Acquire-CpuEncodeMutex {
    <#
    .SYNOPSIS
    F-new-4 — Hold a machine-wide mutex while a CPU encode is running.

    .DESCRIPTION
    A single libx265 job already saturates every logical core on most
    hardware. If two pipeline workers (e.g. coordinator + remote worker
    on the same box) both pick up CPU-routed jobs concurrently, the box
    will thrash, the desktop GUI's main loop will starve, and both
    encodes will run slower than serialized. This helper takes a Win32
    mutex (`Global\MediaPipelineCpuEncodeMutex` by default) before the
    libx265 invocation and releases it afterwards. The mutex is opened
    by name so any process on the same machine sees the same handle.

    The TimeoutSeconds parameter is the maximum time we'll block waiting
    for another CPU encode to finish. -1 = wait forever. 0 = give up
    immediately. Returns a [pscustomobject] with `Acquired: $true|$false`
    and a `Release` scriptblock that the caller invokes in `finally`.
    #>
    param(
        [string] $Name = 'Global\MediaPipelineCpuEncodeMutex',
        [int]    $TimeoutSeconds = -1
    )

    try {
        $mutex = [System.Threading.Mutex]::new($false, $Name)
    } catch {
        # OpenExisting/named-mutex creation can fail on locked-down
        # systems (Group Policy, AppContainer). Fail open so a single
        # broken environment doesn't strand the encode entirely; we
        # log a warning and let the encode proceed without the lock.
        Write-Log "CPU-encode mutex unavailable ($($_.Exception.Message)); continuing without serialization" "WARN"
        return [pscustomobject]@{
            Acquired = $false
            Reason   = "mutex creation failed: $($_.Exception.Message)"
            Release  = { }
        }
    }

    $waitMs = if ($TimeoutSeconds -lt 0) { -1 } else { [int]([math]::Min([int]::MaxValue, [double]$TimeoutSeconds * 1000)) }
    $acquired = $false
    try {
        $acquired = $mutex.WaitOne($waitMs)
    } catch [System.Threading.AbandonedMutexException] {
        # An earlier holder exited without releasing (process killed mid-
        # encode). WaitOne returns true after this exception, so we own
        # the mutex now.
        $acquired = $true
        Write-Log "CPU-encode mutex was abandoned by a previous holder; recovered ownership" "WARN"
    } catch {
        Write-Log "CPU-encode mutex wait failed: $($_.Exception.Message)" "WARN"
        $acquired = $false
    }

    if (-not $acquired) {
        try { $mutex.Dispose() } catch {}
        return [pscustomobject]@{
            Acquired = $false
            Reason   = "wait timed out after ${TimeoutSeconds}s"
            Release  = { }
        }
    }

    $release = {
        try { $mutex.ReleaseMutex() } catch {}
        try { $mutex.Dispose() } catch {}
    }.GetNewClosure()
    return [pscustomobject]@{
        Acquired = $true
        Reason   = ''
        Release  = $release
    }
}

function Test-IsHardwareEncoderFailure {
    param(
        [string] $Encoder = '',
        [string] $ErrorText = ''
    )

    if ([string]::IsNullOrWhiteSpace($ErrorText)) { return $false }
    $encoderText = ([string]$Encoder).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($encoderText) -or $encoderText -match 'nvenc') {
        return (Test-IsNvencError $ErrorText)
    }

    $patterns = @()
    if ($encoderText -match 'amf') {
        $patterns = @(
            'AMF',
            'Advanced Media Framework',
            'CreateComponent.*failed',
            'failed to (initialise|initialize).*amf',
            'encoder initialization failed',
            'No device available',
            'device.*failed',
            'hardware.*(unavailable|failed)'
        )
    } elseif ($encoderText -match 'qsv') {
        $patterns = @(
            'qsv',
            'MFX_ERR',
            'Error initializing (an )?(internal )?MFX session',
            'unsupported device',
            'No device available',
            'device.*failed',
            'hardware.*(unavailable|failed)'
        )
    } else {
        return $false
    }

    foreach ($pattern in $patterns) {
        if ($ErrorText -match $pattern) { return $true }
    }
    return $false
}

function Test-ShouldRetryEncodeWithCpuFallback {
    param(
        [bool] $Success = $false,
        [bool] $StopRequested = $false,
        [string] $VideoCodec = '',
        [string] $ErrorText = '',
        # When set, the gate fires regardless of the stderr pattern.
        # Used by Do-Encode to short-circuit the primary GPU attempt when
        # the cached NVENC probe (Test-NvencProbeReportsAvailable) has
        # been invalidated by a previous file's runtime failure.
        [bool] $ForceCpu = $false
    )

    if ($Success) { return $false }
    if ($StopRequested) { return $false }
    if ($ForceCpu) { return $true }
    return (Test-IsHardwareEncoderFailure -Encoder $VideoCodec -ErrorText $ErrorText)
}
