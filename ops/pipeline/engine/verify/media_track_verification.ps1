# Output audio/subtitle topology verification before publish.
# This module verifies only the resolved output plan. It never treats source
# tracks excluded by language or per-file policy as required output tracks.

function Get-MediaTrackVerificationValue {
    param($Value, [Parameter(Mandatory)] [string] $Name, $Default = $null)

    if ($null -eq $Value) { return $Default }
    if ($Value -is [System.Collections.IDictionary] -and $Value.Contains($Name)) {
        return $Value[$Name]
    }
    try {
        $property = $Value.PSObject.Properties[$Name]
        if ($property) { return $property.Value }
    } catch {}
    return $Default
}

function ConvertTo-MediaTrackVerificationBool {
    param($Value, [bool] $Default = $false)

    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }
    return (([string]$Value).Trim().ToLowerInvariant() -in @('1', 'true', 'yes', 'y'))
}

function Get-NormalizedMediaTrackVerificationCodec {
    param([string] $Codec)

    $normalized = ([string]$Codec).Trim().ToLowerInvariant()
    switch ($normalized) {
        'srt' { return 'subrip' }
        'ass' { return 'ass' }
        'ssa' { return 'ass' }
        'h264' { return 'h264' }
        'avc' { return 'h264' }
        'h265' { return 'hevc' }
        'x265' { return 'hevc' }
        default { return $normalized }
    }
}

function New-MediaTrackOutputVerificationPlan {
    param(
        [array] $AudioDecisions = @(),
        [array] $SubtitleTracks = @()
    )

    $audio = [System.Collections.Generic.List[object]]::new()
    foreach ($decision in @($AudioDecisions)) {
        $ordinal = Get-MediaTrackVerificationValue -Value $decision -Name 'audio_ordinal' -Default $null
        if ($null -eq $ordinal) { continue }
        $action = ([string](Get-MediaTrackVerificationValue -Value $decision -Name 'action' -Default '')).Trim().ToLowerInvariant()
        if ($action -notin @('copy', 'transcode')) { continue }
        $audio.Add([pscustomobject][ordered]@{
            ordinal     = [int]$ordinal
            codec       = Get-NormalizedMediaTrackVerificationCodec ([string](Get-MediaTrackVerificationValue -Value $decision -Name 'output_codec' -Default ''))
            language    = ([string](Get-MediaTrackVerificationValue -Value $decision -Name 'language' -Default 'und')).Trim().ToLowerInvariant()
            channels    = [int](Get-MediaTrackVerificationValue -Value $decision -Name 'output_channels' -Default 0)
            verify_channels = ($action -eq 'transcode')
            is_default = ConvertTo-MediaTrackVerificationBool (Get-MediaTrackVerificationValue -Value $decision -Name 'is_default' -Default $false)
            is_forced  = ConvertTo-MediaTrackVerificationBool (Get-MediaTrackVerificationValue -Value $decision -Name 'is_forced' -Default $false)
            action     = $action
        }) | Out-Null
    }

    $embedded = [System.Collections.Generic.List[object]]::new()
    $external = [System.Collections.Generic.List[object]]::new()
    foreach ($track in @($SubtitleTracks)) {
        $location = ([string](Get-MediaTrackVerificationValue -Value $track -Name 'output_location' -Default 'embedded')).Trim().ToLowerInvariant()
        $record = [pscustomobject][ordered]@{
            ordinal             = [int](Get-MediaTrackVerificationValue -Value $track -Name 'ordinal' -Default $embedded.Count)
            codec               = Get-NormalizedMediaTrackVerificationCodec ([string](Get-MediaTrackVerificationValue -Value $track -Name 'output_codec' -Default ''))
            language            = ([string](Get-MediaTrackVerificationValue -Value $track -Name 'language' -Default 'und')).Trim().ToLowerInvariant()
            is_default          = ConvertTo-MediaTrackVerificationBool (Get-MediaTrackVerificationValue -Value $track -Name 'is_default' -Default $false)
            is_forced           = ConvertTo-MediaTrackVerificationBool (Get-MediaTrackVerificationValue -Value $track -Name 'is_forced' -Default $false)
            source_stream_index = Get-MediaTrackVerificationValue -Value $track -Name 'source_stream_index' -Default $null
            action              = ([string](Get-MediaTrackVerificationValue -Value $track -Name 'action' -Default '')).Trim().ToLowerInvariant()
            output_location     = $location
        }
        if ($location -eq 'external_sidecar') { $external.Add($record) | Out-Null } else { $embedded.Add($record) | Out-Null }
    }

    return [pscustomobject][ordered]@{
        schema_version                     = 'media_track_verification_plan.v1'
        expected_audio_tracks               = @($audio | Sort-Object ordinal)
        expected_embedded_subtitle_tracks   = @($embedded | Sort-Object ordinal)
        expected_external_subtitle_tracks   = @($external)
    }
}

function New-MediaTrackOutputVerificationPlanFromFfmpegSubtitleArgs {
    param(
        [array] $AudioDecisions = @(),
        [array] $SubtitleMapArgs = @()
    )

    $tracks = [System.Collections.Generic.List[object]]::new()
    $args = @($SubtitleMapArgs)
    for ($index = 0; $index -lt $args.Count - 1; $index++) {
        $token = [string]$args[$index]
        if ($token -notmatch '^-c:s:(\d+)$') { continue }
        $ordinal = [int]$Matches[1]
        $codec = Get-NormalizedMediaTrackVerificationCodec ([string]$args[$index + 1])
        $language = 'und'; $disposition = '0'
        for ($cursor = $index + 2; $cursor -lt $args.Count - 1; $cursor += 2) {
            if ([string]$args[$cursor] -eq "-metadata:s:s:$ordinal") {
                $value = [string]$args[$cursor + 1]
                if ($value -match '^language=(.*)$') { $language = $Matches[1].Trim().ToLowerInvariant() }
            }
            if ([string]$args[$cursor] -eq "-disposition:s:$ordinal") { $disposition = [string]$args[$cursor + 1]; break }
        }
        $tracks.Add([pscustomobject]@{
            ordinal = $ordinal; output_codec = $codec; language = $language
            is_default = ($disposition -match 'default'); is_forced = ($disposition -match 'forced')
            output_location = 'embedded'; action = 'ffmpeg_map'
        }) | Out-Null
    }
    return New-MediaTrackOutputVerificationPlan -AudioDecisions $AudioDecisions -SubtitleTracks @($tracks)
}

function Get-MediaTrackOutputInventory {
    param(
        [Parameter(Mandatory)] [string] $OutputPath,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

    $result = Invoke-FFprobeCommand -ArgumentList @(
        '-v', 'error',
        # ffprobe emits disposition fields only through the stream_disposition
        # section.  Requesting a plain `disposition` stream field silently
        # omits default/forced on current builds, which would falsely park a
        # valid output as an audio/subtitle policy mismatch.
        '-show_entries', 'stream=index,codec_type,codec_name,channels:stream_tags=language,title:stream_disposition=default,forced',
        '-of', 'json', '--', $OutputPath
    ) -TimeoutSeconds 60 -Stage 'media-track-output-verify' -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
    if ($result.ExitCode -ne 0 -or [bool]$result.TimedOut -or [bool]$result.Stopped) {
        return [pscustomobject]@{
            Ok = $false; ErrorCode = 'OUTPUT_MEDIA_TRACK_PROBE_FAILED'
            Reason = "could not probe output audio/subtitle streams: $([string]$result.Error)"; Audio = @(); Subtitles = @()
        }
    }
    try { $probe = $result.Output | ConvertFrom-Json } catch {
        return [pscustomobject]@{
            Ok = $false; ErrorCode = 'OUTPUT_MEDIA_TRACK_PROBE_INVALID'
            Reason = "output audio/subtitle ffprobe JSON is invalid: $($_.Exception.Message)"; Audio = @(); Subtitles = @()
        }
    }
    $audio = @($probe.streams | Where-Object { $_.codec_type -eq 'audio' })
    $subtitles = @($probe.streams | Where-Object { $_.codec_type -eq 'subtitle' })
    return [pscustomobject]@{ Ok = $true; ErrorCode = ''; Reason = ''; Audio = $audio; Subtitles = $subtitles }
}

function Add-MediaTrackVerificationMismatch {
    param(
        [Parameter(Mandatory)] $Mismatches,
        [Parameter(Mandatory)] [string] $Kind,
        [Parameter(Mandatory)] [int] $Ordinal,
        [Parameter(Mandatory)] [string] $Property,
        $Expected,
        $Actual
    )

    $Mismatches.Add([pscustomobject][ordered]@{
        kind = $Kind; ordinal = $Ordinal; property = $Property; expected = $Expected; actual = $Actual
    }) | Out-Null
}

function Get-MediaTrackVerificationFacet {
    param(
        [Parameter(Mandatory)] $Verification,
        [Parameter(Mandatory)] [ValidateSet('audio','subtitle')] [string] $Kind
    )

    $facetMismatches = @($Verification.mismatches | Where-Object { $_.kind -eq $Kind })
    $probeFailed = ([string]$Verification.error_code -like 'OUTPUT_MEDIA_TRACK_PROBE_*')
    return [pscustomobject][ordered]@{
        schema_version = "${Kind}_verification.v2"
        ok = ([bool]$Verification.allowed -and $facetMismatches.Count -eq 0)
        reason = [string]$Verification.reason
        error_code = if ($probeFailed -or $facetMismatches.Count -gt 0) { [string]$Verification.error_code } else { '' }
        mismatches = $facetMismatches
    }
}

function Test-MediaTrackOutputVerification {
    param(
        [Parameter(Mandatory)] [string] $OutputPath,
        [Parameter(Mandatory)] $Plan,
        [scriptblock] $PollHandler = $null,
        [int] $PollMilliseconds = 100
    )

    $inventory = Get-MediaTrackOutputInventory -OutputPath $OutputPath -PollHandler $PollHandler -PollMilliseconds $PollMilliseconds
    if (-not [bool]$inventory.Ok) {
        return [pscustomobject][ordered]@{
            schema_version = 'media_track_verification_result.v1'; allowed = $false
            error_code = [string]$inventory.ErrorCode; reason = [string]$inventory.Reason
            mismatches = @(); expected_external_subtitle_count = @($Plan.expected_external_subtitle_tracks).Count
        }
    }

    $mismatches = [System.Collections.Generic.List[object]]::new()
    $expectedAudio = @($Plan.expected_audio_tracks)
    $expectedSubtitles = @($Plan.expected_embedded_subtitle_tracks)
    if (@($inventory.Audio).Count -ne $expectedAudio.Count) {
        Add-MediaTrackVerificationMismatch -Mismatches $mismatches -Kind 'audio' -Ordinal -1 -Property 'count' -Expected $expectedAudio.Count -Actual @($inventory.Audio).Count
    }
    if (@($inventory.Subtitles).Count -ne $expectedSubtitles.Count) {
        Add-MediaTrackVerificationMismatch -Mismatches $mismatches -Kind 'subtitle' -Ordinal -1 -Property 'count' -Expected $expectedSubtitles.Count -Actual @($inventory.Subtitles).Count
    }

    foreach ($expected in $expectedAudio) {
        $ordinal = [int]$expected.ordinal
        if ($ordinal -ge @($inventory.Audio).Count) { continue }
        $actual = @($inventory.Audio)[$ordinal]
        $actualCodec = Get-NormalizedMediaTrackVerificationCodec ([string]$actual.codec_name)
        $actualLanguage = if ($actual.tags -and $actual.tags.language) { ([string]$actual.tags.language).Trim().ToLowerInvariant() } else { 'und' }
        $actualDefault = ConvertTo-MediaTrackVerificationBool $actual.disposition.default
        $actualForced = ConvertTo-MediaTrackVerificationBool $actual.disposition.forced
        if (-not [string]::IsNullOrWhiteSpace([string]$expected.codec) -and $actualCodec -ne $expected.codec) { Add-MediaTrackVerificationMismatch $mismatches 'audio' $ordinal 'codec' $expected.codec $actualCodec }
        if ($actualLanguage -ne $expected.language) { Add-MediaTrackVerificationMismatch $mismatches 'audio' $ordinal 'language' $expected.language $actualLanguage }
        if ([bool]$expected.verify_channels -and [int]$actual.channels -ne [int]$expected.channels) { Add-MediaTrackVerificationMismatch $mismatches 'audio' $ordinal 'channels' $expected.channels $actual.channels }
        if ($actualDefault -ne [bool]$expected.is_default) { Add-MediaTrackVerificationMismatch $mismatches 'audio' $ordinal 'default' $expected.is_default $actualDefault }
        if ($actualForced -ne [bool]$expected.is_forced) { Add-MediaTrackVerificationMismatch $mismatches 'audio' $ordinal 'forced' $expected.is_forced $actualForced }
    }

    foreach ($expected in $expectedSubtitles) {
        $ordinal = [int]$expected.ordinal
        if ($ordinal -ge @($inventory.Subtitles).Count) { continue }
        $actual = @($inventory.Subtitles)[$ordinal]
        $actualCodec = Get-NormalizedMediaTrackVerificationCodec ([string]$actual.codec_name)
        $actualLanguage = if ($actual.tags -and $actual.tags.language) { ([string]$actual.tags.language).Trim().ToLowerInvariant() } else { 'und' }
        $actualDefault = ConvertTo-MediaTrackVerificationBool $actual.disposition.default
        $actualForced = ConvertTo-MediaTrackVerificationBool $actual.disposition.forced
        if (-not [string]::IsNullOrWhiteSpace([string]$expected.codec) -and $actualCodec -ne $expected.codec) { Add-MediaTrackVerificationMismatch $mismatches 'subtitle' $ordinal 'codec' $expected.codec $actualCodec }
        if ($actualLanguage -ne $expected.language) { Add-MediaTrackVerificationMismatch $mismatches 'subtitle' $ordinal 'language' $expected.language $actualLanguage }
        if ($actualDefault -ne [bool]$expected.is_default) { Add-MediaTrackVerificationMismatch $mismatches 'subtitle' $ordinal 'default' $expected.is_default $actualDefault }
        if ($actualForced -ne [bool]$expected.is_forced) { Add-MediaTrackVerificationMismatch $mismatches 'subtitle' $ordinal 'forced' $expected.is_forced $actualForced }
    }

    $allowed = ($mismatches.Count -eq 0)
    return [pscustomobject][ordered]@{
        schema_version = 'media_track_verification_result.v1'; allowed = $allowed
        error_code = if ($allowed) { '' } else { 'OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED' }
        reason = if ($allowed) { 'output audio/subtitle topology matches the resolved policy plan' } else { "output audio/subtitle topology differs from the resolved policy plan ($($mismatches.Count) mismatch(es))" }
        mismatches = @($mismatches)
        expected_audio_count = $expectedAudio.Count
        output_audio_count = @($inventory.Audio).Count
        expected_embedded_subtitle_count = $expectedSubtitles.Count
        output_embedded_subtitle_count = @($inventory.Subtitles).Count
        expected_external_subtitle_count = @($Plan.expected_external_subtitle_tracks).Count
    }
}
