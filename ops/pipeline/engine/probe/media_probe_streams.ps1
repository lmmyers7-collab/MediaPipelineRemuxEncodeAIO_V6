# Extracted from ops/pipeline/engine/probe/media_probe.ps1. Responsibility: video stream inventory and preservation evidence

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
    param(
        [string]$FilePath,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

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
        "-show_entries","stream=index,codec_name,width,height,pix_fmt,color_primaries,color_transfer,color_space,disposition:stream_tags=filename,mimetype",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'source-video-stream-inventory' -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
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
                PixFmt          = ([string]$stream.pix_fmt).Trim().ToLowerInvariant()
                ColorPrimaries  = ([string]$stream.color_primaries).Trim().ToLowerInvariant()
                ColorTransfer   = ([string]$stream.color_transfer).Trim().ToLowerInvariant()
                ColorSpace      = ([string]$stream.color_space).Trim().ToLowerInvariant()
                IsDefault       = ([int]$stream.disposition.default -eq 1)
                IsForced        = ([int]$stream.disposition.forced -eq 1)
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

function Get-VideoStreamEvidenceProperty {
    param(
        $Value,
        [Parameter(Mandatory)] [string[]] $Names,
        $Default = $null
    )

    if ($null -eq $Value) { return $Default }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($name in $Names) {
            if ($Value.Contains($name)) { return $Value[$name] }
        }
    }
    foreach ($name in $Names) {
        try {
            $prop = $Value.PSObject.Properties[$name]
            if ($prop) { return $prop.Value }
        } catch {}
    }
    return $Default
}

function ConvertTo-VideoStreamEvidenceInt {
    param($Value, [int] $Default = 0)
    if ($null -eq $Value) { return $Default }
    try { return [int]$Value } catch { return $Default }
}

function ConvertTo-VideoStreamEvidenceBool {
    param($Value, [bool] $Default = $false)
    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ($text -in @('1','true','yes')) { return $true }
    if ($text -in @('0','false','no')) { return $false }
    return $Default
}

function ConvertTo-VideoStreamEvidenceRows {
    param(
        $Streams,
        [Parameter(Mandatory)] [string] $Source,
        [bool] $DefaultAttachedPicture = $false,
        [int] $Limit = 16
    )

    $rows = @()
    foreach ($stream in @($Streams | Where-Object { $null -ne $_ } | Select-Object -First $Limit)) {
        $attached = ConvertTo-VideoStreamEvidenceBool `
            -Value (Get-VideoStreamEvidenceProperty -Value $stream -Names @('AttachedPicture','attached_picture') -Default $DefaultAttachedPicture) `
            -Default:$DefaultAttachedPicture
        $rows += [pscustomobject][ordered]@{
            source           = $Source
            kind             = "${Source}_video"
            index            = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $stream -Names @('Index','index') -Default -1) -Default -1
            ordinal          = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $stream -Names @('VideoOrdinal','video_ordinal','ordinal') -Default -1) -Default -1
            codec            = ([string](Get-VideoStreamEvidenceProperty -Value $stream -Names @('Codec','codec','codec_name') -Default '')).Trim().ToLowerInvariant()
            width            = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $stream -Names @('Width','width') -Default 0) -Default 0
            height           = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $stream -Names @('Height','height') -Default 0) -Default 0
            pix_fmt          = ([string](Get-VideoStreamEvidenceProperty -Value $stream -Names @('PixFmt','pix_fmt') -Default '')).Trim().ToLowerInvariant()
            color_primaries  = ([string](Get-VideoStreamEvidenceProperty -Value $stream -Names @('ColorPrimaries','color_primaries') -Default '')).Trim().ToLowerInvariant()
            color_transfer   = ([string](Get-VideoStreamEvidenceProperty -Value $stream -Names @('ColorTransfer','color_transfer') -Default '')).Trim().ToLowerInvariant()
            color_space      = ([string](Get-VideoStreamEvidenceProperty -Value $stream -Names @('ColorSpace','color_space') -Default '')).Trim().ToLowerInvariant()
            is_default       = ConvertTo-VideoStreamEvidenceBool -Value (Get-VideoStreamEvidenceProperty -Value $stream -Names @('IsDefault','is_default') -Default $false)
            is_forced        = ConvertTo-VideoStreamEvidenceBool -Value (Get-VideoStreamEvidenceProperty -Value $stream -Names @('IsForced','is_forced') -Default $false)
            attached_picture = [bool]$attached
        }
    }
    return @($rows)
}

function ConvertTo-VideoStreamFailureEvidence {
    param(
        $SourceInventory = $null,
        $OutputInventory = $null,
        [string] $Route = '',
        [string] $Reason = '',
        [string] $ErrorCode = ''
    )

    $sourceReal = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $SourceInventory -Names @('RealVideoStreamCount','real_video_stream_count','source_real_video_stream_count') -Default 0) -Default 0
    $sourceAttached = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $SourceInventory -Names @('AttachedPicCount','attached_pic_count','source_attached_picture_stream_count') -Default 0) -Default 0
    $outputReal = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $OutputInventory -Names @('RealVideoStreamCount','real_video_stream_count','output_real_video_stream_count') -Default 0) -Default 0
    $outputAttached = ConvertTo-VideoStreamEvidenceInt (Get-VideoStreamEvidenceProperty -Value $OutputInventory -Names @('AttachedPicCount','attached_pic_count','output_attached_picture_stream_count') -Default 0) -Default 0

    $sourceRealStreams = Get-VideoStreamEvidenceProperty -Value $SourceInventory -Names @('RealVideoStreams','real_video_streams','source_streams') -Default @()
    $sourceAttachedStreams = Get-VideoStreamEvidenceProperty -Value $SourceInventory -Names @('AttachedPicStreams','attached_pic_streams','attached_picture_streams') -Default @()
    $outputRealStreams = Get-VideoStreamEvidenceProperty -Value $OutputInventory -Names @('RealVideoStreams','real_video_streams','output_streams') -Default @()
    $outputAttachedStreams = Get-VideoStreamEvidenceProperty -Value $OutputInventory -Names @('AttachedPicStreams','attached_pic_streams','attached_picture_streams') -Default @()

    $sourceStreams = @(
        @(ConvertTo-VideoStreamEvidenceRows -Streams $sourceRealStreams -Source 'source' -DefaultAttachedPicture:$false)
        @(ConvertTo-VideoStreamEvidenceRows -Streams $sourceAttachedStreams -Source 'source' -DefaultAttachedPicture:$true)
    )
    $outputStreams = @(
        @(ConvertTo-VideoStreamEvidenceRows -Streams $outputRealStreams -Source 'output' -DefaultAttachedPicture:$false)
        @(ConvertTo-VideoStreamEvidenceRows -Streams $outputAttachedStreams -Source 'output' -DefaultAttachedPicture:$true)
    )

    $summaryLines = @()
    if ($null -ne $SourceInventory) {
        $summaryLines += "Video streams: source real=$sourceReal, attached=$sourceAttached"
    }
    if ($null -ne $OutputInventory) {
        $summaryLines += "Video streams: output real=$outputReal, attached=$outputAttached"
    }

    return [pscustomobject][ordered]@{
        schema_version                       = 'pipeline_failure_video_stream_evidence.v1'
        route                                = ([string]$Route).Trim()
        error_code                           = ([string]$ErrorCode).Trim()
        reason                               = ([string]$Reason).Trim()
        source_real_video_stream_count       = [int]$sourceReal
        source_attached_picture_stream_count = [int]$sourceAttached
        output_real_video_stream_count       = [int]$outputReal
        output_attached_picture_stream_count = [int]$outputAttached
        source_streams                       = @($sourceStreams)
        output_streams                       = @($outputStreams)
        summary_lines                        = @($summaryLines)
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
    return [pscustomobject][ordered]@{
        Allowed   = $true
        ErrorCode = ''
        Reason    = if ($count -eq 1) {
            'one real video stream is eligible for preserve-all publish validation'
        } else {
            $details = (@($inventory.RealVideoStreams) | ForEach-Object { "index $($_.Index) codec $($_.Codec)" }) -join '; '
            "source has $count real video streams ($details); preserve-all stream topology and output verification are required before publish"
        }
        Inventory = $inventory
    }
}

function Test-OutputVideoStreamPreservation {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputPath,
        [string] $Route = '',
        $SourceInventory = $null,
        [string] $ExpectedVideoCodec = '',
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

    $sourceInventoryForCompare = $SourceInventory
    if (-not $sourceInventoryForCompare -or -not $sourceInventoryForCompare.PSObject.Properties['Ok'] -or -not [bool]$sourceInventoryForCompare.Ok) {
        $sourceInventoryForCompare = Get-SourceVideoStreamInventory -FilePath $SourcePath -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
    }
    if (-not [bool]$sourceInventoryForCompare.Ok) {
        return [pscustomobject][ordered]@{
            Allowed         = $false
            ErrorCode       = [string]$sourceInventoryForCompare.ErrorCode
            Reason          = "could not verify source video stream inventory before $Route output preservation check: $($sourceInventoryForCompare.Reason)"
            SourceCount     = 0
            OutputCount     = 0
            SourceInventory = $sourceInventoryForCompare
            OutputInventory = $null
        }
    }

    $outputInventory = Get-SourceVideoStreamInventory -FilePath $OutputPath -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
    if (-not [bool]$outputInventory.Ok) {
        return [pscustomobject][ordered]@{
            Allowed         = $false
            ErrorCode       = 'OUTPUT_VIDEO_STREAM_PROBE_FAILED'
            Reason          = "could not verify $Route output video stream inventory before publish: $($outputInventory.Reason)"
            SourceCount     = [int]$sourceInventoryForCompare.RealVideoStreamCount
            OutputCount     = 0
            SourceInventory = $sourceInventoryForCompare
            OutputInventory = $outputInventory
        }
    }

    $sourceCount = [int]$sourceInventoryForCompare.RealVideoStreamCount
    $outputCount = [int]$outputInventory.RealVideoStreamCount
    if ($sourceCount -le 0) {
        return [pscustomobject][ordered]@{
            Allowed         = $false
            ErrorCode       = 'SOURCE_VIDEO_STREAM_MISSING'
            Reason          = "source has no probeable real video stream; refusing $Route publish"
            SourceCount     = $sourceCount
            OutputCount     = $outputCount
            SourceInventory = $sourceInventoryForCompare
            OutputInventory = $outputInventory
        }
    }
    if ($outputCount -ne $sourceCount) {
        return [pscustomobject][ordered]@{
            Allowed         = $false
            ErrorCode       = 'OUTPUT_VIDEO_STREAM_COUNT_MISMATCH'
            Reason          = "source has $sourceCount real video stream(s) but $Route output has $outputCount; refusing publish because preserve-all video stream topology did not hold"
            SourceCount     = $sourceCount
            OutputCount     = $outputCount
            SourceInventory = $sourceInventoryForCompare
            OutputInventory = $outputInventory
        }
    }

    $mismatches = [System.Collections.Generic.List[object]]::new()
    $normalizedExpectedCodec = ([string]$ExpectedVideoCodec).Trim().ToLowerInvariant()
    if ($normalizedExpectedCodec -match 'hevc|h265|x265') { $normalizedExpectedCodec = 'hevc' }
    elseif ($normalizedExpectedCodec -match 'h264|x264|avc') { $normalizedExpectedCodec = 'h264' }
    elseif ($normalizedExpectedCodec -match 'av1|aom') { $normalizedExpectedCodec = 'av1' }

    for ($ordinal = 0; $ordinal -lt $sourceCount; $ordinal++) {
        $sourceStream = @($sourceInventoryForCompare.RealVideoStreams)[$ordinal]
        $outputStream = @($outputInventory.RealVideoStreams)[$ordinal]
        foreach ($propertyName in @('Width','Height')) {
            if ([int]$sourceStream.$propertyName -ne [int]$outputStream.$propertyName) {
                $mismatches.Add([pscustomobject]@{ ordinal = $ordinal; property = $propertyName.ToLowerInvariant(); expected = [int]$sourceStream.$propertyName; actual = [int]$outputStream.$propertyName }) | Out-Null
            }
        }
        if ($Route -eq 'remux') {
            foreach ($propertyName in @('Codec','PixFmt','ColorPrimaries','ColorTransfer','ColorSpace','IsDefault','IsForced')) {
                $expected = [string]$sourceStream.$propertyName
                $actual = [string]$outputStream.$propertyName
                if ($expected -ne $actual) {
                    $mismatches.Add([pscustomobject]@{ ordinal = $ordinal; property = $propertyName.ToLowerInvariant(); expected = $expected; actual = $actual }) | Out-Null
                }
            }
        } else {
            if (-not [string]::IsNullOrWhiteSpace($normalizedExpectedCodec) -and [string]$outputStream.Codec -ne $normalizedExpectedCodec) {
                $mismatches.Add([pscustomobject]@{ ordinal = $ordinal; property = 'codec'; expected = $normalizedExpectedCodec; actual = [string]$outputStream.Codec }) | Out-Null
            }
            # Re-encode verification protects known HDR signalling.  SDR colour
            # tags are not an encode invariant because FFmpeg can legitimately
            # omit equivalent SDR metadata while retaining the selected codec.
            if ([string]$sourceStream.ColorTransfer -in @('smpte2084', 'arib-std-b67')) {
                foreach ($propertyName in @('ColorPrimaries','ColorTransfer','ColorSpace')) {
                    $expected = [string]$sourceStream.$propertyName
                    $actual = [string]$outputStream.$propertyName
                    if (-not [string]::IsNullOrWhiteSpace($expected) -and $expected -ne $actual) {
                        $mismatches.Add([pscustomobject]@{ ordinal = $ordinal; property = $propertyName.ToLowerInvariant(); expected = $expected; actual = $actual }) | Out-Null
                    }
                }
            }
        }
    }
    if ($mismatches.Count -gt 0) {
        return [pscustomobject][ordered]@{
            Allowed         = $false
            ErrorCode       = 'OUTPUT_VIDEO_STREAM_TOPOLOGY_MISMATCH'
            Reason          = "$Route output video topology differs from source/route expectations; refusing publish"
            SourceCount     = $sourceCount
            OutputCount     = $outputCount
            SourceInventory = $sourceInventoryForCompare
            OutputInventory = $outputInventory
            Mismatches      = @($mismatches.ToArray())
            schema_version  = 'media_verification.v1'
        }
    }

    return [pscustomobject][ordered]@{
        Allowed         = $true
        ErrorCode       = ''
        Reason          = "$Route output preserves $outputCount real video stream(s)"
        SourceCount     = $sourceCount
        OutputCount     = $outputCount
        SourceInventory = $sourceInventoryForCompare
        OutputInventory = $outputInventory
        Mismatches      = @()
        schema_version  = 'media_verification.v1'
    }
}

function Test-Hdr10OutputMetadataPreservation {
    <#
    Fail-closed HDR10 publish gate. This is intentionally separate from generic
    video topology verification so an output cannot be published merely because
    it has the right codec and stream count while losing 10-bit signalling or
    source mastering/CLL side data.
    #>
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputPath,
        $SourceInventory = $null,
        $OutputInventory = $null,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

    $source = if ($SourceInventory) { $SourceInventory } else { Get-SourceVideoStreamInventory -FilePath $SourcePath -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds }
    $output = if ($OutputInventory) { $OutputInventory } else { Get-SourceVideoStreamInventory -FilePath $OutputPath -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds }
    $base = [ordered]@{
        Allowed = $false; Applicable = $false; ErrorCode = ''; Reason = ''
        SourceHdr10 = $null; OutputHdr10 = $null; Mismatches = @(); schema_version = 'hdr10_output_verification.v1'
    }
    if (-not $source -or -not [bool]$source.Ok -or -not $output -or -not [bool]$output.Ok) {
        $base.ErrorCode = 'HDR10_OUTPUT_PROBE_FAILED'
        $base.Reason = 'source or output video inventory could not be inspected for HDR10 verification'
        return [pscustomobject]$base
    }
    $sourceStreams = @($source.RealVideoStreams)
    $outputStreams = @($output.RealVideoStreams)
    $hdrSourceStreams = @($sourceStreams | Where-Object { ([string]$_.ColorTransfer).Trim().ToLowerInvariant() -eq 'smpte2084' })
    if ($hdrSourceStreams.Count -eq 0) {
        $base.Allowed = $true
        $base.Applicable = $false
        $base.Reason = 'source is not HDR10/PQ; generic HDR10 gate is not applicable'
        return [pscustomobject]$base
    }
    $base.Applicable = $true
    $mismatches = [System.Collections.Generic.List[object]]::new()
    for ($ordinal = 0; $ordinal -lt $hdrSourceStreams.Count; $ordinal++) {
        $sourceStream = $hdrSourceStreams[$ordinal]
        $outputStream = if ($ordinal -lt $outputStreams.Count) { $outputStreams[$ordinal] } else { $null }
        if ($null -eq $outputStream) {
            $mismatches.Add([pscustomobject]@{ ordinal = $ordinal; property = 'stream'; expected = 'HDR10 video stream'; actual = 'missing' }) | Out-Null
            continue
        }
        $outputPixFmt = ([string]$outputStream.PixFmt).Trim().ToLowerInvariant()
        if ($outputPixFmt -notmatch '10|p010|p210|p410') {
            $mismatches.Add([pscustomobject]@{ ordinal = $ordinal; property = 'pix_fmt'; expected = '10-bit'; actual = $outputPixFmt }) | Out-Null
        }
        foreach ($property in @('ColorPrimaries','ColorTransfer','ColorSpace')) {
            $expected = ([string]$sourceStream.$property).Trim().ToLowerInvariant()
            $actual = ([string]$outputStream.$property).Trim().ToLowerInvariant()
            if ([string]::IsNullOrWhiteSpace($actual) -or $actual -ne $expected) {
                $mismatches.Add([pscustomobject]@{ ordinal = $ordinal; property = $property.ToLowerInvariant(); expected = $expected; actual = $actual }) | Out-Null
            }
        }
    }
    $sourceHdr10 = Get-SourceHdr10MasteringMetadata -FilePath $SourcePath -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
    $outputHdr10 = Get-SourceHdr10MasteringMetadata -FilePath $OutputPath -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
    $base.SourceHdr10 = $sourceHdr10
    $base.OutputHdr10 = $outputHdr10
    $sourceMetadataReason = ([string]$sourceHdr10.Reason).Trim()
    if (-not [bool]$sourceHdr10.Known -and $sourceMetadataReason -and $sourceMetadataReason -notmatch '^(no side_data_list|side_data_list present but contained no)') {
        $mismatches.Add([pscustomobject]@{ ordinal = 0; property = 'source_hdr10_metadata_evidence'; expected = 'probeable or explicitly absent'; actual = $sourceMetadataReason }) | Out-Null
    }
    if ([bool]$sourceHdr10.HasMasterDisplay -and (-not [bool]$outputHdr10.HasMasterDisplay -or [string]$sourceHdr10.MasterDisplay -ne [string]$outputHdr10.MasterDisplay)) {
        $mismatches.Add([pscustomobject]@{ ordinal = 0; property = 'master_display'; expected = [string]$sourceHdr10.MasterDisplay; actual = [string]$outputHdr10.MasterDisplay }) | Out-Null
    }
    if ([bool]$sourceHdr10.HasMaxCll -and (-not [bool]$outputHdr10.HasMaxCll -or [string]$sourceHdr10.MaxCll -ne [string]$outputHdr10.MaxCll)) {
        $mismatches.Add([pscustomobject]@{ ordinal = 0; property = 'max_cll'; expected = [string]$sourceHdr10.MaxCll; actual = [string]$outputHdr10.MaxCll }) | Out-Null
    }
    $base.Mismatches = @($mismatches.ToArray())
    if (@($base.Mismatches).Count -gt 0) {
        $base.ErrorCode = 'HDR10_OUTPUT_METADATA_MISMATCH'
        $base.Reason = 'HDR10 output metadata differs from source facts; publish is blocked'
        return [pscustomobject]$base
    }
    $base.Allowed = $true
    $base.Reason = 'HDR10 output preserves 10-bit PQ/BT.2020 signalling and source mastering/CLL metadata when present'
    return [pscustomobject]$base
}
