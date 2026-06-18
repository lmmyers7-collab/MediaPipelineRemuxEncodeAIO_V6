# ==============================================================================
# ops\pipeline\engine\probe\media_probe.ps1
# ==============================================================================
# ffprobe-driven media inspection helpers used by ops/pipeline/engine/probe/stage.ps1 and
# the legacy media-probe shim.
#
# Dot-sourced from the main script. Reads the following at call time:
#
#   $ffprobePath              — resolved at startup (Resolve-BundledExecutable)
#   $EnableIntegrityCheck     — config (Test-FileIntegrityDetailed gate)
#   $SkipStabilityCheck       — config (Test-FileStable gate)
#   $FileStabilityWait        — config (per-interval seconds)
#   Invoke-NativeCommand      — ops\pipeline\engine\shared\native.ps1
#   Start-StopAwareSleep      — ops\pipeline\engine\shared\native.ps1
#   Get-FFprobeFailureCode    — ops\pipeline\engine\shared\failure_codes.ps1
#   Write-Log                 — Modules\Logging.ps1
#
# Two functional groups live here:
#
#   Single-shot probes that return a scalar (codec name / lang / HDR flag /
#   duration). Each runs ffprobe with a 30 s timeout and degrades to a
#   sentinel value ("unknown" / "und" / 0.0 / $false) on failure rather
#   than throwing.
#
#   File-level integrity & stability tests used as gates before processing
#   a source file or accepting an output:
#     - Test-FileStable        — three-sample size check on the source
#     - Test-FileIntegrity*    — ffprobe-based "can we read this?" probe
#     - Test-DurationMatch     — post-encode "is the output the right length?"
#                                with the -AllowAVFallback heuristic for
#                                ASS-subtitle-tail container differences
#
#   Output logging used after processing or publish:
#     - Write-OutputSummary           — one-line final output stream summary
#     - Write-PlexCompatibilityReport — Plex/direct-play compatibility outlook
# ==============================================================================

# Constructor for the integrity-result pscustomobject. Every
# Test-FileIntegrityDetailed exit point routes through this so the schema
# (and the default ErrorCode of 'OK'/'MEDIA_INTEGRITY_FAILED') stays
# consistent. Failure-code callers downstream rely on the ErrorCode field.
function New-FileIntegrityResult {
    param(
        [bool]$Ok,
        [string]$Reason,
        [string]$ErrorCode = $null,
        [int]$ExitCode = 0,
        [string]$ErrorText = "",
        [string]$OutputText = "",
        [bool]$TimedOut = $false,
        [bool]$Stopped = $false
    )

    if ([string]::IsNullOrWhiteSpace($ErrorCode)) {
        $ErrorCode = if ($Ok) { 'OK' } else { 'MEDIA_INTEGRITY_FAILED' }
    }

    [pscustomobject]@{
        Ok        = $Ok
        ErrorCode = $ErrorCode
        Reason    = $Reason
        ExitCode  = $ExitCode
        Error     = $ErrorText
        Output    = $OutputText
        TimedOut  = $TimedOut
        Stopped   = $Stopped
    }
}

# Detailed source-integrity probe used for failure classification. Returns a
# rich result object (see New-FileIntegrityResult). Callers that only want
# a yes/no answer should use Test-FileIntegrity instead.
function Test-FileIntegrityDetailed {
    param([string]$FilePath)
    if (-not $EnableIntegrityCheck) {
        return New-FileIntegrityResult -Ok $true -ErrorCode 'INTEGRITY_DISABLED' -Reason "Integrity check disabled"
    }
    if ([string]::IsNullOrWhiteSpace($FilePath)) {
        return New-FileIntegrityResult -Ok $false -ErrorCode 'FILE_PATH_EMPTY' -Reason "File path is empty"
    }
    if (-not (Test-Path -LiteralPath $FilePath)) {
        return New-FileIntegrityResult -Ok $false -ErrorCode 'FILE_MISSING' -Reason "File does not exist: $FilePath"
    }
    try {
        $item = Get-Item -LiteralPath $FilePath -ErrorAction Stop
        if ($item.Length -eq 0) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'FILE_ZERO_BYTES' -Reason "File is zero bytes: $FilePath"
        }

        $r = Invoke-FFprobeCommand -ArgumentList @(
            "-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
        ) -TimeoutSeconds 60 -Stage 'integrity-ffprobe'
        $output = ([string]$r.Output).Trim()
        $stderr = ([string]$r.Error).Trim()
        $timedOut = [bool]$r.TimedOut
        $stopped = [bool]$r.Stopped
        if ($timedOut) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_PROBE_TIMEOUT' -Reason "ffprobe timed out after 60s: $stderr" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $true -Stopped $stopped
        }
        if ($stopped) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_PROBE_STOPPED' -Reason "ffprobe stopped by operator request: $stderr" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $true
        }
        if ([int]$r.ExitCode -ne 0) {
            $reason = if ([string]::IsNullOrWhiteSpace($stderr)) { "ffprobe failed with exit $($r.ExitCode)" } else { "ffprobe failed with exit $($r.ExitCode): $stderr" }
            $code = Get-FFprobeFailureCode -ErrorText $stderr
            return New-FileIntegrityResult -Ok $false -ErrorCode $code -Reason $reason -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $stopped
        }
        if ([string]::IsNullOrWhiteSpace($output)) {
            return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_DURATION_MISSING' -Reason "ffprobe succeeded but returned no duration" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $stopped
        }
        return New-FileIntegrityResult -Ok $true -ErrorCode 'OK' -Reason "ffprobe duration: $output" -ExitCode ([int]$r.ExitCode) -ErrorText $stderr -OutputText $output -TimedOut $timedOut -Stopped $stopped
    } catch {
        return New-FileIntegrityResult -Ok $false -ErrorCode 'MEDIA_INTEGRITY_EXCEPTION' -Reason "Integrity check threw: $_"
    }
}

# Convenience wrapper for callers that only want a Boolean.
function Test-FileIntegrity {
    param([string]$FilePath)
    $result = Test-FileIntegrityDetailed -FilePath $FilePath
    return [bool]$result.Ok
}

# Three-sample size check. Returns $true only when three Get-Item.Length
# reads spaced FileStabilityWait/2 seconds apart all match. Two-sample
# would catch most mid-write cases but bursty network shares can produce
# false-stable readings; the third sample mostly eliminates that.
# Returns $false on stop-flag interrupt as well as on actual size churn.
function Test-FileStable {
    param([string]$Path)
    if ($SkipStabilityCheck) { return $true }
    try {
        $half = [math]::Max(1, [int]($FileStabilityWait / 2))
        $s1 = (Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        if (-not (Start-StopAwareSleep $half)) { return $false }
        $s2 = (Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        if ($s1 -ne $s2) {
            Write-Log "File size changed in stability check ($s1 -> $s2): $Path" "DEBUG"
            return $false
        }
        if (-not (Start-StopAwareSleep $half)) { return $false }
        $s3 = (Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        if ($s2 -ne $s3) {
            Write-Log "File size changed in second stability interval ($s2 -> $s3): $Path" "DEBUG"
            return $false
        }
        return $true
    } catch {
        Write-Log "Stability check failed: $Path : $_" "DEBUG"
        return $false
    }
}

# ============================================================================
# SCALAR PROBES — each returns a single value, sentinel on failure
# ============================================================================

# Returns the source's container-level title tag (format.tags.title) trimmed,
# or '' when absent / probe-failure. Plex and other library managers fall
# back to this title when filename parsing is ambiguous, so the remux path
# uses it to seed mkvmerge --title instead of always overwriting with the
# generic "Encoded by MediaPipeline ..." string.  R8 fix.
function Get-SourceTitleTag {
    param([string]$FilePath)
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error",
        "-show_entries","format_tags=title",
        "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'source-title-tag'
    if ($r.ExitCode -eq 0) {
        $value = ([string]$r.Output).Trim()
        return $value
    }
    return ''
}

# Returns the v:0 codec name lower-cased ('hevc', 'h264', 'av1', 'mpeg2video',
# 'vc1', etc.) or 'unknown' on probe failure. Used to decide remux vs encode.
function Get-SourceVideoCodec {
    param([string]$FilePath)
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","v:0",
        "-show_entries","stream=codec_name",
        "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'source-video-codec'
    if ($r.ExitCode -eq 0) { return $r.Output.Trim().ToLower() }
    return "unknown"
}

function Test-SourceVideoStreamAttachedPicture {
    param([Parameter(Mandatory)] $Stream)

    $disposition = $Stream.disposition
    if ($null -ne $disposition -and @($disposition.PSObject.Properties.Name) -contains 'attached_pic') {
        $attachedPicValue = ([string]$disposition.attached_pic).Trim()
        if ($attachedPicValue -eq '1' -or $attachedPicValue -eq 'True') {
            return $true
        }
    }

    $tags = $Stream.tags
    if ($null -eq $tags) {
        return $false
    }

    $tagNames = @($tags.PSObject.Properties.Name)
    $mimetype = ''
    if ($tagNames -contains 'mimetype') {
        $mimetype = ([string]$tags.mimetype).Trim().ToLowerInvariant()
    }
    if ($mimetype.StartsWith('image/')) {
        return $true
    }

    $filename = ''
    if ($tagNames -contains 'filename') {
        $filename = ([string]$tags.filename).Trim().ToLowerInvariant()
    }
    if ([string]::IsNullOrWhiteSpace($filename)) {
        return $false
    }

    $imageExtensions = @('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff')
    $imageCodecs = @('mjpeg', 'png', 'webp', 'gif', 'bmp', 'tiff', 'jpeg2000')
    $extension = [System.IO.Path]::GetExtension($filename).ToLowerInvariant()
    $codec = ([string]$Stream.codec_name).Trim().ToLowerInvariant()
    return (($imageExtensions -contains $extension) -and ($imageCodecs -contains $codec))
}

function Get-SourceVideoStreamInventory {
    param([string]$FilePath)

    $empty = {
        param(
            [bool]$Ok,
            [string]$ErrorCode,
            [string]$Reason
        )
        return [pscustomobject][ordered]@{
            Ok                   = [bool]$Ok
            ErrorCode            = [string]$ErrorCode
            Reason               = [string]$Reason
            RealVideoStreams     = @()
            AttachedPicStreams   = @()
            RealVideoStreamCount = 0
            AttachedPicCount     = 0
        }
    }

    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","v",
        "-show_entries","stream=index,codec_name,width,height,disposition:stream_tags=filename,mimetype",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'source-video-stream-inventory'
    if ([int]$r.ExitCode -ne 0 -or [bool]$r.TimedOut -or [bool]$r.Stopped) {
        $reason = if (-not [string]::IsNullOrWhiteSpace([string]$r.Error)) { [string]$r.Error } else { "ffprobe exited with code $([int]$r.ExitCode)" }
        return & $empty $false 'SOURCE_VIDEO_STREAM_PROBE_FAILED' $reason
    }

    try {
        $json = $r.Output | ConvertFrom-Json -ErrorAction Stop
        $streams = @($json.streams)
        $realVideo = @()
        $attachedPics = @()
        $videoOrdinal = 0

        foreach ($stream in $streams) {
            $attached = Test-SourceVideoStreamAttachedPicture -Stream $stream
            $ordinal = if ($attached) { -1 } else { [int]$videoOrdinal }
            $record = [pscustomobject][ordered]@{
                Index           = [int]$stream.index
                VideoOrdinal    = [int]$ordinal
                Codec           = ([string]$stream.codec_name).Trim().ToLowerInvariant()
                Width           = [int]$stream.width
                Height          = [int]$stream.height
                AttachedPicture = [bool]$attached
            }
            if ($attached) {
                $attachedPics = @($attachedPics) + @($record)
            } else {
                $realVideo = @($realVideo) + @($record)
                $videoOrdinal++
            }
        }

        return [pscustomobject][ordered]@{
            Ok                   = $true
            ErrorCode            = ''
            Reason               = ''
            RealVideoStreams     = @($realVideo)
            AttachedPicStreams   = @($attachedPics)
            RealVideoStreamCount = [int]$realVideo.Count
            AttachedPicCount     = [int]$attachedPics.Count
        }
    } catch {
        return & $empty $false 'SOURCE_VIDEO_STREAM_PROBE_FAILED' ([string]$_.Exception.Message)
    }
}

function Test-SourceVideoStreamPublishPolicy {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [string] $Route = ''
    )

    $inventory = Get-SourceVideoStreamInventory -FilePath $FilePath
    if (-not [bool]$inventory.Ok) {
        return [pscustomobject][ordered]@{
            Allowed   = $false
            ErrorCode = [string]$inventory.ErrorCode
            Reason    = "could not verify source video stream inventory before $Route publish: $($inventory.Reason)"
            Inventory = $inventory
        }
    }

    $count = [int]$inventory.RealVideoStreamCount
    if ($count -le 0) {
        return [pscustomobject][ordered]@{
            Allowed   = $false
            ErrorCode = 'SOURCE_VIDEO_STREAM_MISSING'
            Reason    = "source has no probeable real video stream; refusing $Route publish"
            Inventory = $inventory
        }
    }
    if ($count -gt 1) {
        $details = (@($inventory.RealVideoStreams) | ForEach-Object { "index $($_.Index) codec $($_.Codec)" }) -join '; '
        return [pscustomobject][ordered]@{
            Allowed   = $false
            ErrorCode = 'SOURCE_VIDEO_STREAMS_UNVETTED'
            Reason    = "source has $count real video streams ($details); current routing validates only the primary stream, so $Route is blocked until per-stream routing and output validation exist"
            Inventory = $inventory
        }
    }

    return [pscustomobject][ordered]@{
        Allowed   = $true
        ErrorCode = ''
        Reason    = 'exactly one real video stream is eligible for current publish validation'
        Inventory = $inventory
    }
}

# Returns the language tag of the audio stream marked default, falling back
# to the first audio stream, then to "und". Lower-cased ISO-639-2/B code.
#
# Defensive notes (post-extraction fix; addresses v1.0-review item #11):
#
#   1. `$json.streams` is array-wrapped via @(...) so single-stream JSON
#      doesn't unwrap to a bare PSCustomObject — `[0]` indexing on a
#      non-array PSCustomObject silently returns $null in PS7.
#
#   2. Newer ffprobe builds OMIT the `disposition` node from JSON output
#      when no flags are set on the stream. The previous code wrote
#      `$s.disposition.default -eq 1` which is fine when disposition is
#      missing (dereferencing $null returns $null, $null -eq 1 is $false),
#      but the surrounding logic could silently drop into the catch block
#      via the `return if (...) {...} else {...}` chain when the .Trim()
#      cast failed on a PSCustomObject deserialization quirk.
#
#   3. tags.language is now explicitly [string]-cast before .ToLower() so
#      a PSCustomObject value (which can happen with malformed nested
#      tags) doesn't NoMethod-throw into the catch.
function Get-DefaultAudioLang {
    param([string]$FilePath)
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

# Cheap HDR detection by color_transfer. Only PQ (smpte2084) and HLG
# (arib-std-b67) are recognized -- that covers all HDR10/HDR10+/HLG content.
# Dolby Vision metadata is layered on top of one of those transfers, so it's
# implicitly handled. Probe failures are explicit so encode routing does not
# silently flatten unknown HDR content through the SDR profile.
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
    ) -TimeoutSeconds 30 -Stage 'hdr10-mastering-probe'

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
    param([string]$FilePath)

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
    ) -TimeoutSeconds 30 -Stage 'dovi-detection'

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
    param([string]$FilePath, [int]$FrameSampleCount = 24)

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
    ) -TimeoutSeconds 60 -Stage 'hdr10plus-detection'

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
        [long] $FileSizeBytes = -1
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
    ) -TimeoutSeconds 45 -Stage 'source-route-profile'

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
            ) -TimeoutSeconds 30 -Stage 'source-video-packet-probe'
            if ($packetProbe.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace([string]$packetProbe.Output)) {
                try {
                    $packetJson = $packetProbe.Output | ConvertFrom-Json -ErrorAction Stop
                    $packetStream = @($packetJson.streams)[0]
                    [int]$readPackets = 0
                    if ($packetStream -and $packetStream.PSObject.Properties['nb_read_packets']) {
                        [void][int]::TryParse([string]$packetStream.nb_read_packets, [ref]$readPackets)
                    }
                    # Only flag empty when we positively determine zero packets;
                    # ambiguous probes leave the source eligible (no false rejects).
                    $videoHasPackets = ($readPackets -ge 1)
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

# ============================================================================
# DURATION HELPERS
# ============================================================================

# Container duration in seconds. Returns 0.0 on probe failure or unparseable
# output — callers use 0.0 as the sentinel for "could not determine".
function Get-MediaDuration {
    param([string]$FilePath)
    if (-not (Test-Path -LiteralPath $FilePath)) { return 0.0 }
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'media-duration'
    if ($r.ExitCode -ne 0) { return 0.0 }
    $d = 0.0
    if ([double]::TryParse($r.Output.Trim(), [ref]$d)) { return $d }
    return 0.0
}

# Last-packet pts_time across the primary video and audio streams. Used as a
# fallback in Test-DurationMatch when the container duration disagrees: an
# ASS subtitle cue extending past actual A/V end inflates the container
# duration even though the encoded A/V is identical end-to-end. Returns 0.0
# when neither v:0 nor a:0 produced parseable packet timestamps.
#
# Default 180s timeout is generous because packet enumeration is O(file
# length) — for 4K films the probe can take 30-60s.
function Get-PrimaryAVEndTime {
    param(
        [string]$FilePath,
        [int]$TimeoutSeconds = 180
    )

    if (-not (Test-Path -LiteralPath $FilePath)) { return 0.0 }

    $maxEnd = 0.0
    $found  = $false
    foreach ($selector in @('v:0', 'a:0')) {
        $probe = Invoke-FFprobeCommand -ArgumentList @(
            '-v', 'error',
            '-select_streams', $selector,
            '-show_entries', 'packet=pts_time',
            '-of', 'csv=p=0',
            '--', $FilePath
        ) -TimeoutSeconds $TimeoutSeconds -Stage 'primary-av-end-time'

        if ($probe.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($probe.Output)) {
            continue
        }

        $lines = $probe.Output -split '\r?\n' | Where-Object { $_ -match '\S' }
        if (-not $lines -or $lines.Count -eq 0) {
            continue
        }

        $lastLine = $lines[-1].Trim()
        $match = [regex]::Match($lastLine, '[-+]?\d+(?:\.\d+)?')
        if (-not $match.Success) {
            continue
        }

        try {
            $end = [double]::Parse($match.Value, [System.Globalization.CultureInfo]::InvariantCulture)
            if ($end -gt $maxEnd) { $maxEnd = $end }
            $found = $true
        } catch {}
    }

    if ($found) { return $maxEnd }
    return 0.0
}

# Post-encode duration sanity check. Catches silent truncations where ffmpeg
# exits 0 but the output is shorter than the source.
#
# Source-probe-failure policy: returns $false. Publish verification cannot
# accept an output when the source duration cannot be measured. Output-probe-
# failure policy: returns $false (the output is unreadable — treat as corrupt).
#
# -AllowAVFallback (used by encode/remux paths but not by integrity checks):
# when the container durations disagree by more than -ToleranceSeconds, fall
# back to comparing primary-A/V end times (Get-PrimaryAVEndTime). This
# tolerates the common case where a stray subtitle cue at the end of an ASS
# track inflates the source container duration; the encoded output is
# correct but Test-DurationMatch would otherwise reject it.
function Test-DurationMatch {
    param(
        [string]$SourcePath,
        [string]$OutputPath,
        [double]$ToleranceSeconds = 1.0,
        [string]$Label = "ENCODE",
        [switch]$AllowAVFallback
    )
    $srcDur = Get-MediaDuration $SourcePath
    $outDur = Get-MediaDuration $OutputPath
    if ($srcDur -le 0) {
        Write-Log "${Label}: source duration probe failed - treating verification as failed" "ERROR"
        return $false
    }
    if ($outDur -le 0) {
        Write-Log "${Label}: output duration probe failed — treating as corrupt" "ERROR"
        return $false
    }
    $delta = [math]::Abs($srcDur - $outDur)
    if ($delta -gt $ToleranceSeconds) {
        if ($AllowAVFallback) {
            $srcAvEnd = Get-PrimaryAVEndTime -FilePath $SourcePath
            $outAvEnd = Get-PrimaryAVEndTime -FilePath $OutputPath

            if ($srcAvEnd -gt 0 -and $outAvEnd -gt 0) {
                $avDelta = [math]::Abs($srcAvEnd - $outAvEnd)
                if ($avDelta -le $ToleranceSeconds) {
                    Write-Log ("{0}: container duration mismatch accepted because primary A/V end times match " +
                        "(source container {1:N2}s, output container {2:N2}s, source A/V {3:N2}s, output A/V {4:N2}s, A/V delta {5:N2}s)" `
                        -f $Label, $srcDur, $outDur, $srcAvEnd, $outAvEnd, $avDelta) "WARN"
                    return $true
                }

                Write-Log ("{0}: DURATION MISMATCH — source container {1:N2}s, output container {2:N2}s, delta {3:N2}s " +
                    "(tolerance {4}s); primary A/V end times also differ (source A/V {5:N2}s, output A/V {6:N2}s, A/V delta {7:N2}s)" `
                    -f $Label, $srcDur, $outDur, $delta, $ToleranceSeconds, $srcAvEnd, $outAvEnd, $avDelta) "ERROR"
                return $false
            }

            Write-Log ("{0}: DURATION MISMATCH — source {1:N2}s, output {2:N2}s, delta {3:N2}s (tolerance {4}s); " +
                "primary A/V fallback probe failed" `
                -f $Label, $srcDur, $outDur, $delta, $ToleranceSeconds) "ERROR"
            return $false
        }

        Write-Log ("{0}: DURATION MISMATCH — source {1:N2}s, output {2:N2}s, delta {3:N2}s (tolerance {4}s)" `
            -f $Label, $srcDur, $outDur, $delta, $ToleranceSeconds) "ERROR"
        return $false
    }
    Write-Log ("{0}: duration verified (source {1:N2}s, output {2:N2}s, delta {3:N2}s)" `
        -f $Label, $srcDur, $outDur, $delta) "DEBUG"
    return $true
}

# ==============================================================================
# OUTPUT SUMMARY — one-line description of the final MKV's tracks
# ==============================================================================

# Probes $FilePath and writes one INFO log line summarising its streams.
# Format:
#   OUTPUT: 1.23GB | HEVC 1080p | JPN 2.0 FLAC, ENG 2.0 FLAC [def] | ENG ASS, ENG SRT [def], ENG ASS [signs]
function Write-OutputSummary {
    param([string]$FilePath, [string]$Route)
    if (-not (Test-Path -LiteralPath $FilePath)) { return }
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error",
        "-show_entries","stream=index,codec_type,codec_name,width,height,channels,disposition:stream_tags=language,title",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'output-summary-probe'
    if ($r.ExitCode -ne 0) { return }

    try {
        $json    = $r.Output | ConvertFrom-Json
        $sizeGB  = (Get-Item -LiteralPath $FilePath).Length / 1GB
        $parts   = [System.Collections.Generic.List[string]]::new()
        $parts.Add(("{0:N2}GB" -f $sizeGB))

        $vid     = $json.streams | Where-Object { $_.codec_type -eq 'video' } | Select-Object -First 1
        if ($vid) {
            $res  = if ($vid.height -ge 2000) { '4K' } elseif ($vid.height -ge 1000) { '1080p' } elseif ($vid.height -ge 700) { '720p' } else { "$($vid.height)p" }
            $parts.Add(("{0} {1}" -f $vid.codec_name.ToUpper(), $res))
        }

        $auds = @($json.streams | Where-Object { $_.codec_type -eq 'audio' })
        if ($auds.Count -gt 0) {
            $aParts = foreach ($a in $auds) {
                $lang = if ($a.tags.language) { $a.tags.language.ToUpper() } else { 'UND' }
                $ch   = if ($a.channels) { $a.channels } else { '?' }
                $layout = switch ([int]$ch) {
                    1 {'1.0'} 2 {'2.0'} 3 {'2.1'} 4 {'4.0'} 5 {'4.1'} 6 {'5.1'} 7 {'6.1'} 8 {'7.1'}
                    default { "${ch}ch" }
                }
                $def  = if ($a.disposition.default -eq 1) { ' [def]' } else { '' }
                "$lang $layout $($a.codec_name.ToUpper())$def"
            }
            $parts.Add(($aParts -join ', '))
        }

        $subs = @($json.streams | Where-Object { $_.codec_type -eq 'subtitle' })
        if ($subs.Count -gt 0) {
            $sParts = foreach ($s in $subs) {
                $lang = if ($s.tags.language) { $s.tags.language.ToUpper() } else { 'UND' }
                $subtitleCodec = if ($s.codec_name) { ([string]$s.codec_name).ToLowerInvariant() } else { '' }
                $codec = if ($subtitleCodec -in (Get-MediaSubtitleCodecSrtNames)) {
                    'SRT'
                } elseif ($subtitleCodec -in (Get-MediaSubtitleCodecAssNames)) {
                    'ASS'
                } else {
                    $subtitleCodec.ToUpperInvariant()
                }
                $flags = @()
                if ($s.disposition.default -eq 1) { $flags += 'def' }
                if ($s.disposition.forced  -eq 1) { $flags += 'forced' }
                $title = if ($s.tags.title) { $s.tags.title.ToLower() } else { '' }
                if ($title -match 'sign|song|karaoke') { $flags += 'signs' }
                $flagStr = if ($flags.Count) { ' [' + ($flags -join ',') + ']' } else { '' }
                "$lang $codec$flagStr"
            }
            $parts.Add(($sParts -join ', '))
        }

        $routeLabel = if ($Route -eq (Get-MediaRouteRemuxName)) {
            '(remux)'
        } elseif ($Route -eq (Get-MediaRouteEncodeName)) {
            '(encode)'
        } elseif ($Route -eq (Get-MediaRouteEncodeCpuFallbackName)) {
            '(encode, CPU)'
        } else {
            ''
        }
        Write-Log ("OUTPUT: " + ($parts -join ' | ') + " $routeLabel").Trim()
    } catch {
        Write-Log "Output summary failed for $FilePath : $_" "WARN"
    }
}

function Write-PlexCompatibilityReport {
    param(
        [string]$FilePath,
        [string]$Context = ''
    )

    $probe = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error",
        "-show_entries","stream=index,codec_name,codec_type,disposition:stream_tags=language,title",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 45 -Stage 'plex-compatibility-probe'
    if ($probe.ExitCode -ne 0) {
        Write-Log "${Context}PLEX CHECK: ffprobe failed for compatibility summary" "WARN"
        return
    }

    try {
        $json = $probe.Output | ConvertFrom-Json
    } catch {
        Write-Log "${Context}PLEX CHECK: could not parse ffprobe output" "WARN"
        return
    }

    if (-not $json.streams) {
        Write-Log "${Context}PLEX CHECK: no streams found in output" "WARN"
        return
    }

    $video = @($json.streams | Where-Object { $_.codec_type -eq 'video' } | Select-Object -First 1)[0]
    $audio = @($json.streams | Where-Object { $_.codec_type -eq 'audio' })
    $subs  = @($json.streams | Where-Object { $_.codec_type -eq 'subtitle' })

    $defaultAudio = @($audio | Where-Object { $_.disposition.default -eq 1 } | Select-Object -First 1)[0]
    if (-not $defaultAudio) { $defaultAudio = @($audio | Select-Object -First 1)[0] }
    $defaultSub = @($subs | Where-Object { $_.disposition.default -eq 1 } | Select-Object -First 1)[0]

    $videoCodec = if ($video -and $video.codec_name) { $video.codec_name.ToLower() } else { 'unknown' }
    $audioCodec = if ($defaultAudio -and $defaultAudio.codec_name) { $defaultAudio.codec_name.ToLower() } else { 'none' }
    $audioLang  = if ($defaultAudio -and $defaultAudio.tags.language) { $defaultAudio.tags.language.ToLower() } else { 'und' }
    $subCodec   = if ($defaultSub -and $defaultSub.codec_name) { $defaultSub.codec_name.ToLower() } else { 'none' }
    $subLang    = if ($defaultSub -and $defaultSub.tags.language) { $defaultSub.tags.language.ToLower() } else { 'none' }
    $hasTextSubs = @($subs | Where-Object { $_.codec_name -in (Get-MediaSubtitleCodecSrtNames) }).Count -gt 0

    $outlook = 'high'
    $notes = [System.Collections.Generic.List[string]]::new()

    if ($audioCodec -in (Get-MediaAudioCodecPlexTranscodeRiskNames)) {
        $outlook = 'mixed'
        $notes.Add("default audio codec '$audioCodec' may force Plex transcode on some clients")
    }
    if ($subCodec -in (Get-MediaSubtitleCodecAssNames)) {
        $outlook = 'mixed'
        $notes.Add("default subtitle codec '$subCodec' is less Plex-friendly than SRT")
    }
    if ($subCodec -in (Get-MediaSubtitleCodecBdpgsNames)) {
        $outlook = 'low'
        $notes.Add("default subtitle codec '$subCodec' usually forces image-based subtitle handling")
    }
    if ($subs.Count -gt 0 -and -not $hasTextSubs) {
        if ($outlook -eq 'high') { $outlook = 'mixed' }
        $notes.Add('no SRT text subtitle track present in the output')
    }
    if ($videoCodec -notin (Get-MediaVideoCodecPlexDirectPlayNames)) {
        if ($outlook -eq 'high') { $outlook = 'mixed' }
        $notes.Add("video codec '$videoCodec' may not direct play broadly")
    }

    Write-Log ("{0}PLEX CHECK: video={1} | default audio={2}/{3} | default subtitles={4}/{5} | outlook={6}" -f $Context, $videoCodec, $audioLang, $audioCodec, $subLang, $subCodec, $outlook.ToUpperInvariant())
    foreach ($note in $notes) {
        Write-Log "${Context}PLEX CHECK: $note" "WARN"
    }
}
