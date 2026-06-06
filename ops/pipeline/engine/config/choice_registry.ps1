# ==============================================================================
# ops\pipeline\engine\config\choice_registry.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\config\config_schema.ps1. Keep public function names
# and config key semantics stable; config_schema.ps1 dot-sources this file.
# ==============================================================================

function Get-MediaPipelineVideoCodecNames {
    return @('hevc_nvenc','libx265','h264_nvenc','libx264','av1_nvenc')
}

function Get-MediaPipelineVideoPresetNames {
    return @('p1','p2','p3','p4','p5','p6','p7')
}

function Get-MediaPipelineOutputContainerNames {
    return @('mkv','mp4')
}

function Get-MediaPipelineEncodeTuningPresetNames {
    return @(
        'balanced_nvenc',
        'quality_nvenc',
        'fast_nvenc',
        'compatibility',
        'custom_legacy_flags'
    )
}

function Get-MediaPipelineEncodeTuningPresetDefault {
    return 'balanced_nvenc'
}

function Get-MediaPipelineCpuEncodePresetNames {
    # libx265 preset slugs accepted by `-preset`. Ordered from fastest to slowest.
    return @(
        'ultrafast','superfast','veryfast','faster','fast',
        'medium','slow','slower','veryslow','placebo'
    )
}

function Get-MediaPipelineCpuEncodePresetDefault {
    return 'medium'
}

function Resolve-MediaPipelineCpuEncodePreset {
    param([string] $Preset)
    $normalized = if ($Preset) { $Preset.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return Get-MediaPipelineCpuEncodePresetDefault }
    if ($normalized -in (Get-MediaPipelineCpuEncodePresetNames)) { return $normalized }
    return Get-MediaPipelineCpuEncodePresetDefault
}

function Get-MediaPipelineCpuEncodeProcessPriorityNames {
    # Mirrors System.Diagnostics.ProcessPriorityClass with 'inherit' meaning leave alone.
    return @('inherit','idle','belownormal','normal','abovenormal','high')
}

function Get-MediaPipelineCpuEncodeProcessPriorityDefault {
    return 'belownormal'
}

function Resolve-MediaPipelineCpuEncodeProcessPriority {
    param([string] $Priority)
    $normalized = if ($Priority) { $Priority.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return Get-MediaPipelineCpuEncodeProcessPriorityDefault }
    if ($normalized -in (Get-MediaPipelineCpuEncodeProcessPriorityNames)) { return $normalized }
    return Get-MediaPipelineCpuEncodeProcessPriorityDefault
}

function Get-MediaPipelineEncodeLadderNames {
    return @(
        'auto',
        'tv_balanced',
        'tv_space_saver',
        'movie_balanced',
        'movie_archive',
        'plex_compat'
    )
}

function Get-MediaPipelineEncodeLadderDefault {
    return 'auto'
}

function Get-MediaPipelineRoutingProfileNames {
    return @(
        'plex_direct_stream',
        'plex_direct_play',
        'archive_shrink',
        'archive_quality',
        'manual'
    )
}

function Get-MediaPipelineRoutingProfileDefault {
    return 'plex_direct_stream'
}

function Get-MediaPipelineRouteThresholdModeNames {
    return @(
        'compatibility_advisory',
        'size',
        'bitrate',
        'size_or_bitrate'
    )
}

function Get-MediaPipelineRouteThresholdModeDefault {
    return 'compatibility_advisory'
}

function Get-MediaPipelineSizeGuardModeNames {
    return @(
        'advisory',
        'strict',
        'fallback_remux',
        'off'
    )
}

function Get-MediaPipelineSizeGuardModeDefault {
    return 'advisory'
}

function Get-MediaPipelineFinalLibraryPromotionVerificationModeNames {
    return @('fast','cautious')
}

function Get-MediaPipelineAudioPassthroughProfileNames {
    return @(
        'plex_balanced',
        'compatibility',
        'lossless_passthrough',
        'custom_codec_list'
    )
}

function Get-MediaPipelineAudioPassthroughProfileDefault {
    return 'plex_balanced'
}

function Get-MediaPipelineAudioTranscodeCodecNames {
    return @('eac3','ac3','aac')
}

function Get-MediaPipelineAudioDownmixModeNames {
    return @('preserve','max_channels','stereo')
}

function Resolve-MediaPipelineAudioPassthroughProfile {
    param(
        [string] $Profile,
        [array] $LegacyCompatibleAudioCodecs = @()
    )

    $normalized = if ($Profile) { $Profile.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        if (@($LegacyCompatibleAudioCodecs).Count -gt 0) { return 'custom_codec_list' }
        return Get-MediaPipelineAudioPassthroughProfileDefault
    }
    if ($normalized -in (Get-MediaPipelineAudioPassthroughProfileNames)) {
        return $normalized
    }
    return Get-MediaPipelineAudioPassthroughProfileDefault
}

function Get-MediaPipelineAudioPassthroughProfileCodecs {
    param([string] $Profile)

    switch (Resolve-MediaPipelineAudioPassthroughProfile -Profile $Profile) {
        'compatibility' {
            return @('aac','ac3','eac3','mp3','opus','vorbis')
        }
        'lossless_passthrough' {
            return @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp','dts','dts_hd_ma','dts-hd','flac','alac')
        }
        'custom_codec_list' {
            return @()
        }
        default {
            return @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp')
        }
    }
}

function Resolve-MediaPipelineEncodeLadder {
    param([string] $Ladder)

    $normalized = if ($Ladder) { $Ladder.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineEncodeLadderDefault
    }
    if ($normalized -in (Get-MediaPipelineEncodeLadderNames)) {
        return $normalized
    }
    return Get-MediaPipelineEncodeLadderDefault
}

function Resolve-MediaPipelineRoutingProfile {
    param([string] $Profile)

    $normalized = if ($Profile) { $Profile.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineRoutingProfileDefault
    }
    if ($normalized -in (Get-MediaPipelineRoutingProfileNames)) {
        return $normalized
    }
    return Get-MediaPipelineRoutingProfileDefault
}

function Resolve-MediaPipelineRouteThresholdMode {
    param([string] $Mode)

    $normalized = if ($Mode) { $Mode.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineRouteThresholdModeDefault
    }
    if ($normalized -in (Get-MediaPipelineRouteThresholdModeNames)) {
        return $normalized
    }
    return Get-MediaPipelineRouteThresholdModeDefault
}

function Resolve-MediaPipelineSizeGuardMode {
    param([string] $Mode)

    $normalized = if ($Mode) { $Mode.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineSizeGuardModeDefault
    }
    if ($normalized -in (Get-MediaPipelineSizeGuardModeNames)) {
        return $normalized
    }
    return Get-MediaPipelineSizeGuardModeDefault
}

function Get-MediaPipelineParallelEncodeModeNames {
    return @('single','local_worker_slots')
}

function Get-MediaPipelineParallelEncodeModeDefault {
    return 'single'
}

function Resolve-MediaPipelineParallelEncodeMode {
    param([string] $Mode)

    $normalized = if ($Mode) { $Mode.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineParallelEncodeModeDefault
    }
    if ($normalized -in (Get-MediaPipelineParallelEncodeModeNames)) {
        return $normalized
    }
    return Get-MediaPipelineParallelEncodeModeDefault
}

function Resolve-MediaPipelineEncodeTuningPreset {
    param(
        [string] $Preset,
        [array] $LegacyExtraVideoFlags = @()
    )

    $normalized = if ($Preset) { $Preset.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        if (@($LegacyExtraVideoFlags).Count -gt 0) { return 'custom_legacy_flags' }
        return Get-MediaPipelineEncodeTuningPresetDefault
    }

    if ($normalized -in (Get-MediaPipelineEncodeTuningPresetNames)) {
        return $normalized
    }
    return Get-MediaPipelineEncodeTuningPresetDefault
}

function Get-MediaPipelineRenameMovieFilterCategoryNames {
    return @(
        'video_source',
        'audio_channels',
        'editions',
        'file_size',
        'services_containers',
        'release_groups'
    )
}
