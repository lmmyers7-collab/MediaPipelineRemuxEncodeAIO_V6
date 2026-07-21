# Extracted from ops/pipeline/engine/probe/media_probe.ps1. Responsibility: HDR, dynamic-HDR, and route-profile projection

function Get-DefaultAudioLang {
    param(
        [string]$FilePath,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","a",
        "-show_entries","stream=index,disposition:stream_tags=language",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'default-audio-language'
    if ($r.ExitCode -ne 0) { return "und" }
    try {
        $json = $r.Output | ConvertFrom-Json -ErrorAction Stop
        $streams = @($json.streams)
        if ($streams.Count -eq 0) { return "und" }

        # Prefer a stream explicitly marked default. Skip silently if the
        # `disposition` node is missing — that's the common case on lavfi /
        # remuxed sources where no default flag was ever written.
        foreach ($s in $streams) {
            if ($null -ne $s.disposition -and $s.disposition.default -eq 1) {
                if ($s.tags -and $s.tags.language) {
                    return ([string]$s.tags.language).ToLower()
                }
                return "und"
            }
        }

        # Fall back to the first audio stream's language.
        $first = $streams[0]
        if ($first -and $first.tags -and $first.tags.language) {
            return ([string]$first.tags.language).ToLower()
        }
        return "und"
    } catch { return "und" }
}

function Get-HDRState {
    param([string]$FilePath)
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","v:0",
        "-show_entries","stream=color_transfer",
        "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'hdr-detection'
    if ($r.ExitCode -ne 0 -or $r.TimedOut -or $r.Stopped) {
        $reason = if ($r.TimedOut) {
            'ffprobe timed out during HDR detection'
        } elseif ($r.Stopped) {
            'ffprobe stopped during HDR detection'
        } elseif (-not [string]::IsNullOrWhiteSpace([string]$r.Error)) {
            [string]$r.Error
        } else {
            "ffprobe exited with code $($r.ExitCode) during HDR detection"
        }
        return [pscustomobject][ordered]@{
            Known          = $false
            IsHDR          = $false
            Reason         = $reason
            ColorTransfer  = ''
            ExitCode       = $r.ExitCode
        }
    }
    $transfer = ([string]$r.Output).Trim().ToLowerInvariant()
    return [pscustomobject][ordered]@{
        Known          = $true
        IsHDR          = [bool]($transfer -match '^(smpte2084|arib-std-b67)$')
        Reason         = ''
        ColorTransfer  = $transfer
        ExitCode       = $r.ExitCode
    }
}

function Get-SourceHdr10MasteringMetadata {
    <#
    .SYNOPSIS
    Suggestion #1 — extract HDR10 mastering display metadata + MaxCLL/MaxFALL
    from the first video frame so libx265 can emit a complete HDR10 SEI.

    .DESCRIPTION
    Without this, the Tier A3 fix added `hdr10=1:hdr10-opt=1:repeat-headers=1`
    to -x265-params but x265 still has nothing to emit because libav doesn't
    surface the side-data automatically through its decoder->encoder pipe.
    BluRay HDR10 sources lose their mastering metadata on CPU encode.

    Runs `ffprobe -show_frames -read_intervals %+#1` against v:0 (one packet
    on the first video stream is enough to populate side_data_list when
    the metadata is at the bitstream front, which is how BluRay sources
    carry it). Parses the JSON, builds the x265 strings, returns:

        Known           [bool]
        Reason          [string]   (when not Known)
        HasMasterDisplay [bool]
        MasterDisplay    [string]   "G(x,y)B(x,y)R(x,y)WP(x,y)L(max,min)"
        HasMaxCll        [bool]
        MaxCll           [string]   "<max_content>,<max_average>"

    Returns Known=$false on probe failure (e.g. SDR source) so the caller
    can skip emitting -x265-params metadata strings without throwing.
    #>
    param([string]$FilePath)

    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","v:0",
        "-show_frames","-read_intervals","%+#1",
        "-show_entries","frame=side_data_list",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'hdr10-mastering-probe' -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds

    $base = [pscustomobject][ordered]@{
        Known            = $false
        Reason           = ''
        HasMasterDisplay = $false
        MasterDisplay    = ''
        HasMaxCll        = $false
        MaxCll           = ''
    }

    if ($r.ExitCode -ne 0 -or $r.TimedOut -or $r.Stopped) {
        $base.Reason = if ($r.TimedOut) { 'ffprobe timed out' }
                       elseif ($r.Stopped) { 'ffprobe stopped' }
                       elseif ($r.Error) { [string]$r.Error }
                       else { "ffprobe exited $($r.ExitCode)" }
        return $base
    }

    try {
        $json = $r.Output | ConvertFrom-Json
    } catch {
        $base.Reason = "side-data JSON parse failed: $($_.Exception.Message)"
        return $base
    }

    $frames = @($json.frames)
    if ($frames.Count -eq 0) {
        $base.Reason = 'ffprobe returned no frames'
        return $base
    }
    $sideData = @($frames[0].side_data_list)
    if ($sideData.Count -eq 0) {
        $base.Reason = 'no side_data_list on first frame (SDR or HDR10 metadata is mid-stream)'
        return $base
    }

    # ffprobe returns Mastering Display fields as "num/den". x265's
    # master-display syntax wants the integer numerator directly because
    # the denominators (50000 for chroma, 10000 for luminance) match the
    # x265 internal scale. So we just extract the numerator.
    $extractNum = {
        param($value)
        $text = [string]$value
        if ($text -match '^\s*(-?\d+)\s*/') { return [long]$Matches[1] }
        if ($text -match '^\s*(-?\d+)\s*$') { return [long]$Matches[1] }
        return $null
    }

    foreach ($entry in $sideData) {
        $type = [string]$entry.side_data_type
        if ($type -match '(?i)^Mastering display metadata') {
            $g_x = & $extractNum $entry.green_x
            $g_y = & $extractNum $entry.green_y
            $b_x = & $extractNum $entry.blue_x
            $b_y = & $extractNum $entry.blue_y
            $r_x = & $extractNum $entry.red_x
            $r_y = & $extractNum $entry.red_y
            $wp_x = & $extractNum $entry.white_point_x
            $wp_y = & $extractNum $entry.white_point_y
            $lmax = & $extractNum $entry.max_luminance
            $lmin = & $extractNum $entry.min_luminance
            if (@($g_x,$g_y,$b_x,$b_y,$r_x,$r_y,$wp_x,$wp_y,$lmax,$lmin) -notcontains $null) {
                $base.HasMasterDisplay = $true
                $base.MasterDisplay = "G($g_x,$g_y)B($b_x,$b_y)R($r_x,$r_y)WP($wp_x,$wp_y)L($lmax,$lmin)"
            }
        }
        elseif ($type -match '(?i)^Content light level metadata') {
            $maxContent = & $extractNum $entry.max_content
            $maxAverage = & $extractNum $entry.max_average
            if ($null -ne $maxContent -and $null -ne $maxAverage) {
                $base.HasMaxCll = $true
                $base.MaxCll = "$maxContent,$maxAverage"
            }
        }
    }

    $base.Known = ($base.HasMasterDisplay -or $base.HasMaxCll)
    if (-not $base.Known) {
        $base.Reason = 'side_data_list present but contained no mastering/CLL entries'
    }
    return $base
}

function ConvertTo-DynamicHdrInt {
    param($Value, [int] $Default = 0)

    if ($null -eq $Value) { return $Default }
    $result = 0
    if ([int]::TryParse([string]$Value, [ref]$result)) { return $result }
    return $Default
}

function Test-DynamicHdrFlag {
    param($Value)

    if ($null -eq $Value) { return $false }
    $text = ([string]$Value).Trim()
    return ($text -eq '1' -or $text -match '^(?i:true)$')
}

function Get-DynamicHdrProbeFailureReason {
    param($ProbeResult, [string] $Stage)

    if ($ProbeResult -and $ProbeResult.TimedOut) {
        return "ffprobe timed out during $Stage"
    }
    if ($ProbeResult -and $ProbeResult.Stopped) {
        return "ffprobe stopped during $Stage"
    }
    if ($ProbeResult -and -not [string]::IsNullOrWhiteSpace([string]$ProbeResult.Error)) {
        return [string]$ProbeResult.Error
    }
    if ($ProbeResult) {
        return "ffprobe exited with code $($ProbeResult.ExitCode) during $Stage"
    }
    return "ffprobe did not return a result during $Stage"
}

function Get-DynamicHdrObjectValue {
    param($Object, [Parameter(Mandatory)] [string] $Name, $Default = $null)

    if (-not $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) { return $Object[$Name] }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function Get-DolbyVisionState {
    param(
        [string]$FilePath,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

    $base = [pscustomobject][ordered]@{
        Known          = $false
        Reason         = ''
        DoviPresent    = $false
        DoviProfile    = 0
        DoviLevel      = 0
        DoviBlCompatId = -1
        DoviRpuPresent = $false
        DoviElPresent  = $false
    }

    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name:stream_side_data_list",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'dovi-detection' -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds

    if ($r.ExitCode -ne 0 -or $r.TimedOut -or $r.Stopped) {
        $base.Reason = Get-DynamicHdrProbeFailureReason -ProbeResult $r -Stage 'Dolby Vision detection'
        return $base
    }

    try {
        $json = $r.Output | ConvertFrom-Json -ErrorAction Stop
    } catch {
        $base.Reason = "Dolby Vision JSON parse failed: $($_.Exception.Message)"
        return $base
    }

    $streams = @($json.streams)
    if ($streams.Count -eq 0) {
        $base.Known = $true
        return $base
    }

    $sideData = @($streams[0].side_data_list)
    foreach ($entry in $sideData) {
        $type = [string]$entry.side_data_type
        if ($type -match '(?i)(dovi|dolby\s+vision).*configuration') {
            $base.Known = $true
            $base.DoviPresent = $true
            $base.DoviProfile = ConvertTo-DynamicHdrInt -Value $entry.dv_profile -Default 0
            $base.DoviLevel = ConvertTo-DynamicHdrInt -Value $entry.dv_level -Default 0
            $base.DoviBlCompatId = ConvertTo-DynamicHdrInt -Value $entry.dv_bl_signal_compatibility_id -Default -1
            $base.DoviRpuPresent = Test-DynamicHdrFlag -Value $entry.rpu_present_flag
            $base.DoviElPresent = Test-DynamicHdrFlag -Value $entry.el_present_flag
            return $base
        }
    }

    $base.Known = $true
    return $base
}

function Test-Hdr10PlusPresence {
    param(
        [string]$FilePath,
        [int]$FrameSampleCount = 24,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

    if ($FrameSampleCount -lt 1) { $FrameSampleCount = 24 }
    $base = [pscustomobject][ordered]@{
        Known            = $false
        Reason           = ''
        Hdr10PlusPresent = $false
        SampledFrames    = 0
    }

    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","v:0",
        "-read_intervals","%+#$FrameSampleCount",
        "-show_frames","-show_entries","frame=side_data_list",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 60 -Stage 'hdr10plus-detection' -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds

    if ($r.ExitCode -ne 0 -or $r.TimedOut -or $r.Stopped) {
        $base.Reason = Get-DynamicHdrProbeFailureReason -ProbeResult $r -Stage 'HDR10+ detection'
        return $base
    }

    try {
        $json = $r.Output | ConvertFrom-Json -ErrorAction Stop
    } catch {
        $base.Reason = "HDR10+ JSON parse failed: $($_.Exception.Message)"
        return $base
    }

    $frames = @($json.frames)
    $base.Known = $true
    $base.SampledFrames = [int]$frames.Count
    foreach ($frame in $frames) {
        foreach ($entry in @($frame.side_data_list)) {
            $type = [string]$entry.side_data_type
            # Require the -40 variant explicitly: SMPTE 2094-10 frame side data
            # (DoVi-flavored dynamic metadata) must not be reported as HDR10+.
            if ($type -match '(?i)SMPTE.?2094.?40|HDR.?10\+') {
                $base.Hdr10PlusPresent = $true
                return $base
            }
        }
    }

    return $base
}

function New-DynamicHdrEvidence {
    param(
        [Parameter(Mandatory)] [ValidateSet('encode','remux')] [string] $Route,
        $DoviState = $null,
        $Hdr10PlusState = $null,
        [string] $Policy = 'warn'
    )

    $doviKnown = [bool](Get-DynamicHdrObjectValue -Object $DoviState -Name 'Known' -Default $false)
    $hdr10PlusKnown = [bool](Get-DynamicHdrObjectValue -Object $Hdr10PlusState -Name 'Known' -Default $false)
    $doviReason = [string](Get-DynamicHdrObjectValue -Object $DoviState -Name 'Reason' -Default '')
    $hdr10PlusReason = [string](Get-DynamicHdrObjectValue -Object $Hdr10PlusState -Name 'Reason' -Default '')

    $doviPresent = $doviKnown -and [bool](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviPresent' -Default $false)
    $hdr10PlusPresent = $hdr10PlusKnown -and [bool](Get-DynamicHdrObjectValue -Object $Hdr10PlusState -Name 'Hdr10PlusPresent' -Default $false)
    $dynamicPresent = ($doviPresent -or $hdr10PlusPresent)
    $probeErrors = [System.Collections.Generic.List[string]]::new()
    if (-not $doviKnown -and -not [string]::IsNullOrWhiteSpace($doviReason)) {
        $probeErrors.Add("dovi: $doviReason")
    }
    if (-not $hdr10PlusKnown -and -not [string]::IsNullOrWhiteSpace($hdr10PlusReason)) {
        $probeErrors.Add("hdr10plus: $hdr10PlusReason")
    }
    $probed = ($doviKnown -and $hdr10PlusKnown)
    $probeError = ($probeErrors.ToArray() -join '; ')

    $summaryParts = [System.Collections.Generic.List[string]]::new()
    if ($doviPresent) {
        $doviProfile = [int](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviProfile' -Default 0)
        $doviCompat = [int](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviBlCompatId' -Default -1)
        $doviEl = [bool](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviElPresent' -Default $false)
        $doviSummary = "DoVi profile $doviProfile"
        if ($doviCompat -ge 0) { $doviSummary = "$doviSummary (BL compat $doviCompat)" }
        if ($doviEl) { $doviSummary = "$doviSummary (EL present)" }
        $summaryParts.Add($doviSummary)
    }
    if ($hdr10PlusPresent) {
        $summaryParts.Add('HDR10+')
    }

    $summary = if ($summaryParts.Count -gt 0) {
        $summaryParts.ToArray() -join ' + '
    } elseif (-not $probed) {
        'dynamic HDR probe failed'
    } else {
        'no dynamic HDR metadata detected'
    }

    $outcome = 'none_detected'
    $warning = ''
    if ($dynamicPresent -and $Route -eq 'encode') {
        $outcome = 'will_drop_encode'
        $warning = "Dynamic HDR metadata ($summary) will be dropped by encode; static HDR10 metadata is handled separately."
    } elseif ($dynamicPresent -and $Route -eq 'remux') {
        $outcome = 'expected_preserved_remux'
    } elseif (-not $probed) {
        $outcome = 'probe_failed'
    }

    return [pscustomobject][ordered]@{
        schema_version           = 'dynamic_hdr_evidence.v1'
        probed                   = [bool]$probed
        probe_error              = $probeError
        dovi_present             = [bool]$doviPresent
        dovi_profile             = [int](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviProfile' -Default 0)
        dovi_level               = [int](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviLevel' -Default 0)
        dovi_bl_compat_id        = [int](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviBlCompatId' -Default -1)
        dovi_el_present          = [bool](Get-DynamicHdrObjectValue -Object $DoviState -Name 'DoviElPresent' -Default $false)
        hdr10plus_present        = [bool]$hdr10PlusPresent
        dynamic_metadata_present = [bool]$dynamicPresent
        policy                   = if ([string]::IsNullOrWhiteSpace($Policy)) { 'warn' } else { [string]$Policy }
        route                    = [string]$Route
        outcome                  = $outcome
        summary                  = $summary
        warning                  = $warning
        tool_versions            = [ordered]@{
            dovi_tool       = ''
            hdr10plus_tool  = ''
        }
        verification             = [ordered]@{
            checked                  = $false
            output_dovi_present      = $false
            output_hdr10plus_present = $false
            rpu_frame_count          = 0
            expected_frame_count     = 0
        }
    }
}

function Test-IsHDR {
    param([string]$FilePath)
    $state = Get-HDRState $FilePath
    if (-not [bool]$state.Known) {
        throw "HDR_DETECTION_UNKNOWN: $($state.Reason)"
    }
    return [bool]$state.IsHDR
}

function Get-SourceMediaRouteProfile {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [long] $FileSizeBytes = -1,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

    if ([string]::IsNullOrWhiteSpace($FilePath)) {
        return [pscustomobject][ordered]@{
            schema_version          = 'source_media_profile.v1'
            probe_ok                = $false
            probe_error             = 'file_path_empty'
            video_codec             = 'unknown'
            width                   = 0
            height                  = 0
            is_hdr                  = $false
            color_transfer          = ''
            duration_seconds        = 0.0
            container_bitrate_mbps  = 0.0
            estimated_bitrate_mbps  = 0.0
            size_bytes              = 0
        }
    }

    $sizeBytes = [long]$FileSizeBytes
    if ($sizeBytes -lt 0) {
        try {
            $sizeBytes = [long](Get-Item -LiteralPath $FilePath -ErrorAction Stop).Length
        } catch {
            $sizeBytes = 0
        }
    }

    $emptyProfile = {
        param([string]$ErrorCode)
        [pscustomobject][ordered]@{
            schema_version          = 'source_media_profile.v1'
            probe_ok                = $false
            probe_error             = $ErrorCode
            video_codec             = 'unknown'
            width                   = 0
            height                  = 0
            is_hdr                  = $false
            color_transfer          = ''
            duration_seconds        = 0.0
            container_bitrate_mbps  = 0.0
            estimated_bitrate_mbps  = 0.0
            size_bytes              = $sizeBytes
        }
    }

    if (-not (Test-Path -LiteralPath $FilePath)) {
        return (& $emptyProfile 'file_missing')
    }

    $probe = Invoke-FFprobeCommand -ArgumentList @(
        '-v', 'error',
        '-show_entries', 'format=duration,bit_rate:stream=index,codec_type,codec_name,width,height,color_transfer,bit_rate',
        '-of', 'json',
        '--', $FilePath
    ) -TimeoutSeconds 45 -Stage 'source-route-profile' -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds

    if ($probe.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace([string]$probe.Output)) {
        return (& $emptyProfile 'ffprobe_failed')
    }

    try {
        $json = $probe.Output | ConvertFrom-Json -ErrorAction Stop
        $streams = @($json.streams)
        $video = $streams | Where-Object { [string]$_.codec_type -eq 'video' } | Select-Object -First 1
        $duration = 0.0
        $formatBitrate = 0.0
        $videoBitrate = 0.0
        $width = 0
        $height = 0

        if ($json.format -and $json.format.duration) {
            [void][double]::TryParse(
                [string]$json.format.duration,
                [System.Globalization.NumberStyles]::Float,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [ref]$duration
            )
        }
        if ($json.format -and $json.format.bit_rate) {
            [void][double]::TryParse(
                [string]$json.format.bit_rate,
                [System.Globalization.NumberStyles]::Float,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [ref]$formatBitrate
            )
        }
        if ($video -and $video.bit_rate) {
            [void][double]::TryParse(
                [string]$video.bit_rate,
                [System.Globalization.NumberStyles]::Float,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [ref]$videoBitrate
            )
        }
        if ($video -and $video.width) { try { $width = [int]$video.width } catch { $width = 0 } }
        if ($video -and $video.height) { try { $height = [int]$video.height } catch { $height = 0 } }

        $codec = if ($video -and $video.codec_name) { ([string]$video.codec_name).Trim().ToLowerInvariant() } else { 'unknown' }
        if ([string]::IsNullOrWhiteSpace($codec)) { $codec = 'unknown' }
        $transfer = if ($video -and $video.color_transfer) { ([string]$video.color_transfer).Trim().ToLowerInvariant() } else { '' }
        $isHdr = ($transfer -match '^(smpte2084|arib-std-b67)$')
        $estimatedBitrate = if ($duration -gt 0 -and $sizeBytes -gt 0) {
            [math]::Round((([double]$sizeBytes * 8.0) / $duration) / 1000000.0, 3)
        } elseif ($videoBitrate -gt 0) {
            [math]::Round($videoBitrate / 1000000.0, 3)
        } elseif ($formatBitrate -gt 0) {
            [math]::Round($formatBitrate / 1000000.0, 3)
        } else {
            0.0
        }

        # Detect a declared-but-empty video stream. Some malformed or partially
        # transferred sources carry a video stream header with zero decodable
        # packets: ffprobe lists the stream (so a presence-only check passes), but
        # ffmpeg later aborts the encode with "Cannot determine format of input
        # after EOF" and the failure is mis-classified as transient and retried.
        # A bounded packet read (first video packet only) lets us treat this like a
        # missing video stream up front, so preflight marks it permanent/non-
        # retryable and never routes it to a doomed, repeatedly-retried encode.
        $videoHasPackets = $true
        if ($null -ne $video) {
            $packetProbe = Invoke-FFprobeCommand -ArgumentList @(
                '-v', 'error',
                '-select_streams', 'v:0',
                '-read_intervals', '%+#1',
                '-count_packets',
                '-show_entries', 'stream=nb_read_packets',
                '-of', 'json',
                '--', $FilePath
            ) -TimeoutSeconds 30 -Stage 'source-video-packet-probe' -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
            if ($packetProbe.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace([string]$packetProbe.Output)) {
                try {
                    $packetJson = $packetProbe.Output | ConvertFrom-Json -ErrorAction Stop
                    $packetStream = @($packetJson.streams)[0]
                    [int]$readPackets = 0
                    if ($packetStream -and $packetStream.PSObject.Properties['nb_read_packets']) {
                        $packetCountKnown = [int]::TryParse([string]$packetStream.nb_read_packets, [ref]$readPackets)
                        if ($packetCountKnown) {
                            $videoHasPackets = ($readPackets -ge 1)
                        }
                    }
                } catch {
                    $videoHasPackets = $true
                }
            }
        }
        $hasUsableVideo = ($null -ne $video -and $videoHasPackets)

        return [pscustomobject][ordered]@{
            schema_version          = 'source_media_profile.v1'
            probe_ok                = $hasUsableVideo
            probe_error             = if ($hasUsableVideo) { '' } else { 'video_stream_missing' }
            video_codec             = $codec
            width                   = $width
            height                  = $height
            is_hdr                  = [bool]$isHdr
            color_transfer          = $transfer
            duration_seconds        = [double]$duration
            container_bitrate_mbps  = if ($formatBitrate -gt 0) { [math]::Round($formatBitrate / 1000000.0, 3) } else { 0.0 }
            estimated_bitrate_mbps  = [double]$estimatedBitrate
            size_bytes              = $sizeBytes
        }
    } catch {
        return (& $emptyProfile 'ffprobe_json_invalid')
    }
}
