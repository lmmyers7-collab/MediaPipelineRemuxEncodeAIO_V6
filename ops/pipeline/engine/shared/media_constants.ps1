# ==============================================================================
# ops\pipeline\engine\shared\media_constants.ps1
# ==============================================================================
# Shared media route / codec / container constants used by engine stages and
# the legacy media-constants shim.
#
# Keep this module side-effect-light: it defines stable names used by policy
# modules so string ownership is explicit during refactors.
# ==============================================================================

$script:MediaRouteEncode = 'encode'
$script:MediaRouteRemux = 'remux'
$script:MediaRouteEncodeCpuFallback = 'encode-cpu-fallback'

$script:MediaVideoCodecLibx265 = 'libx265'
$script:MediaVideoCodecHevcAliases = @('hevc', 'h265')
$script:MediaVideoCodecPlexDirectPlay = @('hevc', 'h264', 'av1')
$script:MediaContainerMuxerMatroska = 'matroska'
$script:MediaContainerExtensionMkv = 'mkv'
$script:MediaContainerMp4Family = @('mp4', 'm4v', 'mov')
$script:MediaContainerMatroskaFamily = @('mkv', 'mka', 'webm')

$script:MediaSubtitleCodecMovText = 'mov_text'
$script:MediaSubtitleCodecAssAliases = @('ass', 'ssa')
$script:MediaSubtitleCodecSrtAliases = @('subrip', 'srt')
$script:MediaSubtitleCodecBdpgsAliases = @('hdmv_pgs_subtitle', 'pgs')
$script:MediaSubtitleCodecVobSubAliases = @('dvd_subtitle', 'dvdsub', 'vobsub')
$script:MediaSubtitleCodecWebVtt = 'webvtt'
$script:MediaSubtitleCodecExternalFriendlyTextAliases = @('subrip', 'srt', 'webvtt')
$script:MediaSubtitleCodecTextAliases = @('subrip', 'srt', 'mov_text', 'webvtt')
$script:MediaSubtitleCodecImageAliases = @('hdmv_pgs_subtitle', 'pgs', 'dvd_subtitle', 'dvdsub', 'vobsub', 'xsub')

$script:MediaAudioCodecFlac = 'flac'
$script:MediaAudioCodecPlexTranscodeRisk = @('truehd', 'dts', 'dts_hd_ma', 'dts-hd', 'flac')
$script:MediaAudioCodecFidelityRanks = @{
    truehd    = 130
    mlp       = 125
    'dts-hd'  = 120
    dts_hd_ma = 120
    flac      = 115
    alac      = 112
    pcm_s24le = 110
    pcm_s24be = 110
    pcm_s16le = 108
    pcm_s16be = 108
    dts       = 100
    eac3      = 90
    ac3       = 82
    opus      = 76
    aac       = 72
    vorbis    = 68
    mp3       = 60
}
$script:MediaAudioCodecDisplayLabels = @{
    truehd   = 'TrueHD'
    dts      = 'DTS'
    'dts-hd' = 'DTS-HD'
    flac     = 'FLAC'
    opus     = 'Opus'
}

function Get-MediaRouteEncodeName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaRouteEncode)) { return 'encode' }
    return [string]$script:MediaRouteEncode
}

function Get-MediaRouteRemuxName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaRouteRemux)) { return 'remux' }
    return [string]$script:MediaRouteRemux
}

function Get-MediaRouteEncodeCpuFallbackName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaRouteEncodeCpuFallback)) { return 'encode-cpu-fallback' }
    return [string]$script:MediaRouteEncodeCpuFallback
}

function Get-MediaVideoCodecLibx265Name {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaVideoCodecLibx265)) { return 'libx265' }
    return [string]$script:MediaVideoCodecLibx265
}

function Get-MediaVideoCodecHevcNames {
    $values = @($script:MediaVideoCodecHevcAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('hevc', 'h265') }
    return @($values)
}

function Get-MediaVideoCodecPlexDirectPlayNames {
    $values = @($script:MediaVideoCodecPlexDirectPlay | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('hevc', 'h264', 'av1') }
    return @($values)
}

function Get-MediaContainerMuxerMatroskaName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaContainerMuxerMatroska)) { return 'matroska' }
    return [string]$script:MediaContainerMuxerMatroska
}

function Get-MediaContainerMkvExtensionName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaContainerExtensionMkv)) { return 'mkv' }
    return [string]$script:MediaContainerExtensionMkv
}

function Get-MediaContainerMp4FamilyNames {
    $values = @($script:MediaContainerMp4Family | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('mp4', 'm4v', 'mov') }
    return @($values)
}

function Get-MediaContainerMatroskaFamilyNames {
    $values = @($script:MediaContainerMatroskaFamily | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('mkv', 'mka', 'webm') }
    return @($values)
}

function Get-MediaSubtitleCodecMovTextName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaSubtitleCodecMovText)) { return 'mov_text' }
    return [string]$script:MediaSubtitleCodecMovText
}

function Get-MediaSubtitleCodecAssNames {
    $values = @($script:MediaSubtitleCodecAssAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('ass', 'ssa') }
    return @($values)
}

function Get-MediaSubtitleCodecSrtNames {
    $values = @($script:MediaSubtitleCodecSrtAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('subrip', 'srt') }
    return @($values)
}

function Get-MediaSubtitleCodecBdpgsNames {
    $values = @($script:MediaSubtitleCodecBdpgsAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('hdmv_pgs_subtitle', 'pgs') }
    return @($values)
}

function Get-MediaSubtitleCodecVobSubNames {
    $values = @($script:MediaSubtitleCodecVobSubAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('dvd_subtitle', 'dvdsub', 'vobsub') }
    return @($values)
}

function Get-MediaSubtitleCodecWebVttName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaSubtitleCodecWebVtt)) { return 'webvtt' }
    return [string]$script:MediaSubtitleCodecWebVtt
}

function Get-MediaSubtitleCodecExternalFriendlyTextNames {
    $values = @($script:MediaSubtitleCodecExternalFriendlyTextAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('subrip', 'srt', 'webvtt') }
    return @($values)
}

function Get-MediaSubtitleCodecTextNames {
    $values = @($script:MediaSubtitleCodecTextAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('subrip', 'srt', 'mov_text', 'webvtt') }
    return @($values)
}

function Get-MediaSubtitleCodecImageNames {
    $values = @($script:MediaSubtitleCodecImageAliases | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('hdmv_pgs_subtitle', 'pgs', 'dvd_subtitle', 'dvdsub', 'vobsub', 'xsub') }
    return @($values)
}

function Get-MediaAudioCodecFlacName {
    if ([string]::IsNullOrWhiteSpace([string]$script:MediaAudioCodecFlac)) { return 'flac' }
    return [string]$script:MediaAudioCodecFlac
}

function Get-MediaAudioCodecPlexTranscodeRiskNames {
    $values = @($script:MediaAudioCodecPlexTranscodeRisk | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($values.Count -eq 0) { return @('truehd', 'dts', 'dts_hd_ma', 'dts-hd', 'flac') }
    return @($values)
}

function Get-MediaAudioCodecFidelityRankValue {
    param([string]$Codec)

    $normalized = ([string]($Codec ?? '')).ToLowerInvariant()
    $ranks = $script:MediaAudioCodecFidelityRanks
    if ($ranks -is [hashtable] -and $ranks.ContainsKey($normalized)) {
        return [int]$ranks[$normalized]
    }

    switch ($normalized) {
        'truehd'     { return 130 }
        'mlp'        { return 125 }
        'dts-hd'     { return 120 }
        'dts_hd_ma'  { return 120 }
        'flac'       { return 115 }
        'alac'       { return 112 }
        'pcm_s24le'  { return 110 }
        'pcm_s24be'  { return 110 }
        'pcm_s16le'  { return 108 }
        'pcm_s16be'  { return 108 }
        'dts'        { return 100 }
        'eac3'       { return 90 }
        'ac3'        { return 82 }
        'opus'       { return 76 }
        'aac'        { return 72 }
        'vorbis'     { return 68 }
        'mp3'        { return 60 }
        default      { return 50 }
    }
}

function Get-MediaAudioCodecDisplayLabel {
    param([string]$Codec)

    $normalized = ([string]($Codec ?? '')).ToLowerInvariant()
    $labels = $script:MediaAudioCodecDisplayLabels
    if ($labels -is [hashtable] -and $labels.ContainsKey($normalized)) {
        return [string]$labels[$normalized]
    }
    return $normalized.ToUpperInvariant()
}
