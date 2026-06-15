# ==============================================================================
# ops\pipeline\engine\subtitles\builders.ps1
# ==============================================================================
# Subtitle mux/encode argument builders for mkvmerge and FFmpeg.
# Dot-sourced by ops\pipeline\engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

$subtitleBuilderDecisionModulePath = Join-Path $PSScriptRoot 'builders\decisions.ps1'
if (-not (Test-Path -LiteralPath $subtitleBuilderDecisionModulePath -PathType Leaf)) {
    throw "Required subtitle builder helper not found: $subtitleBuilderDecisionModulePath"
}
. $subtitleBuilderDecisionModulePath

function Get-SubtitleBuilderObjectValue {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $Default
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop -and $null -ne $prop.Value) { return $prop.Value }
    return $Default
}

function Get-SubtitleBuilderObjectText {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name,
        [string] $Default = ''
    )

    $value = Get-SubtitleBuilderObjectValue -Object $Object -Name $Name -Default $null
    if ($null -eq $value) { return $Default }
    $text = [string]$value
    if ([string]::IsNullOrWhiteSpace($text)) { return $Default }
    return $text
}

function Get-SubtitleBuilderSourceSubtitleKind {
    param(
        [string] $ConversionKind,
        $Entry
    )

    switch ($ConversionKind) {
        'ass_to_srt' { return 'ass' }
        'tx3g_to_srt' { return 'tx3g' }
        'bdpgs_to_srt' { return 'bdpgs' }
        'vobsub_to_srt' { return 'vobsub' }
    }

    if ([bool](Get-SubtitleBuilderObjectValue -Object $Entry -Name 'IsTx3g' -Default $false)) { return 'tx3g' }
    if ([bool](Get-SubtitleBuilderObjectValue -Object $Entry -Name 'IsBdpgs' -Default $false)) { return 'bdpgs' }
    if ([bool](Get-SubtitleBuilderObjectValue -Object $Entry -Name 'IsVobSub' -Default $false)) { return 'vobsub' }
    $codec = Get-SubtitleBuilderObjectText -Object $Entry -Name 'Codec' -Default ''
    if (-not [string]::IsNullOrWhiteSpace($codec)) {
        switch ($codec.ToLowerInvariant()) {
            'mov_text' { return 'tx3g' }
            'hdmv_pgs_subtitle' { return 'bdpgs' }
            'dvd_subtitle' { return 'vobsub' }
            default { return $codec.ToLowerInvariant() }
        }
    }
    return 'subtitle'
}

function New-SubtitleBuilderConvertedSrtSidecarTrack {
    param(
        [Parameter(Mandatory)] [string] $SrtPath,
        [Parameter(Mandatory)] $Entry,
        $Decision,
        [int] $CueCount = 0,
        [bool] $OriginalPreserved = $false
    )

    $conversionKind = Get-SubtitleBuilderObjectText -Object $Decision -Name 'ConversionKind' -Default ''
    if ([string]::IsNullOrWhiteSpace($conversionKind)) {
        $sourceKind = Get-SubtitleBuilderSourceSubtitleKind -Entry $Entry
        $conversionKind = "${sourceKind}_to_srt"
    }
    $sourceSubtitleKind = Get-SubtitleBuilderSourceSubtitleKind -ConversionKind $conversionKind -Entry $Entry
    $sourceCodec = Get-SubtitleBuilderObjectText -Object $Entry -Name 'Codec' -Default $sourceSubtitleKind
    $entrySourceKind = Get-SubtitleBuilderObjectText -Object $Entry -Name 'SourceKind' -Default 'embedded'

    return @{
        SrtPath = $SrtPath
        StreamInfo = $Entry
        CueCount = $CueCount
        OriginalPreserved = $OriginalPreserved
        OriginalPreserveReason = (Get-SubtitleBuilderObjectText -Object $Decision -Name 'OriginalPreserveReason' -Default '')
        ConversionKind = $conversionKind
        SourceSubtitleKind = $sourceSubtitleKind
        SourceSubtitleCodec = $sourceCodec
        SourceKind = $entrySourceKind
        SidecarKind = 'converted_srt'
    }
}

function Get-MkvmergeTidMap {
    param([string]$FilePath, [string]$Context = "")
    $tidMap = @{}
    try {
        $probeTimeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleProbeTimeoutSeconds' -DefaultSeconds 30
        $r = Invoke-MkvmergeCommand -ArgumentList @("-J", $FilePath) -TimeoutSeconds $probeTimeoutSeconds -Stage 'subtitle-mkvmerge-identify'
        if ($r.ExitCode -ne 0) {
            Write-Log "${Context}mkvmerge -J failed (exit $($r.ExitCode)) — using ffprobe indices" "WARN"
            return $tidMap
        }
        $json = $r.Output | ConvertFrom-Json
        if (-not $json.tracks) { return $tidMap }
        foreach ($track in $json.tracks) {
            if ($track.type -ne "subtitles") { continue }
            $mkvTid = [int]$track.id
            $num    = $track.properties.number
            if ($null -ne $num) {
                $tidMap[[int]$num - 1] = $mkvTid
                DebugLog "${Context}TID map: ffprobe $([int]$num-1) -> mkvmerge TID $mkvTid"
            }
        }
        Write-Log "${Context}mkvmerge TID map: $($tidMap.Count) subtitle track(s)" "DEBUG"
    } catch { Write-Log "${Context}Get-MkvmergeTidMap error: $_ — using ffprobe indices" "WARN" }
    return $tidMap
}

# R9 support — return the mkvmerge TIDs for AUDIO tracks in $FilePath in
# their input order (ordinal 0 -> first audio TID, etc.). Empty array on
# probe failure; the caller should treat that as "skip emitting explicit
# default-track flags and rely on inherited disposition from temp_av".
function Get-MkvmergeAudioTids {
    param([string]$FilePath, [string]$Context = "")
    $tids = [System.Collections.Generic.List[int]]::new()
    try {
        $probeTimeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleProbeTimeoutSeconds' -DefaultSeconds 30
        $r = Invoke-MkvmergeCommand -ArgumentList @("-J", $FilePath) -TimeoutSeconds $probeTimeoutSeconds -Stage 'remux-audio-mkvmerge-identify'
        if ($r.ExitCode -ne 0) {
            Write-Log "${Context}mkvmerge -J failed (exit $($r.ExitCode)) — audio default-track flags will be left implicit" "WARN"
            return @()
        }
        $json = $r.Output | ConvertFrom-Json
        if (-not $json.tracks) { return @() }
        foreach ($track in $json.tracks) {
            if ($track.type -ne 'audio') { continue }
            $tids.Add([int]$track.id)
        }
    } catch {
        Write-Log "${Context}Get-MkvmergeAudioTids error: $_ — audio default-track flags will be left implicit" "WARN"
        return @()
    }
    return @($tids)
}

function Build-SubtitleTracksForMkvmerge {
    param($FilterResult, [string]$DefaultAudioLang, [string]$SourceFile, [string]$Context = "")

    # mkvmerge needs its own TID numbers to copy ASS tracks from the source.
    $tidMap         = Get-MkvmergeTidMap $SourceFile $Context
    $sourceTracks   = [System.Collections.Generic.List[hashtable]]::new()
    $externalTracks = [System.Collections.Generic.List[hashtable]]::new()
    $tx3gTracks     = [System.Collections.Generic.List[hashtable]]::new()
    $bdpgsTracks    = [System.Collections.Generic.List[hashtable]]::new()
    $vobSubTracks   = [System.Collections.Generic.List[hashtable]]::new()
    $tempFiles      = [System.Collections.Generic.List[string]]::new()
    $failures       = [System.Collections.Generic.List[object]]::new()
    $defaultState  = New-SubtitleBuilderDefaultState
    $trackDecisions = Get-SubtitleBuilderTrackDecisionRecords -FilterResult $FilterResult -Builder 'Mkvmerge'

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertAss' })) {
        $entry  = $decision.Entry
        $s      = $entry.Stream
        $mkvTid = if ($tidMap.ContainsKey($s.index)) { $tidMap[$s.index] } else { $s.index }
        $keptAssTrack = $null
        if ([bool]$decision.PreserveOriginal) {
            $keptAssTrack = @{
                MkvTid    = $mkvTid
                Lang      = $entry.Lang
                Title     = "$($entry.Title) $($decision.OriginalTitleSuffix)"
                IsDefault = $false
                IsForced  = $entry.IsForced
            }
            $sourceTracks.Add($keptAssTrack)
        }

        $ass = Convert-AssToSrt $SourceFile $s.index $entry
        if (-not $ass.Ok) {
            if ($ass.Failure) { $failures.Add($ass.Failure) }
            if ($keptAssTrack -and -not $entry.IsSupplemental) {
                if ([bool]$decision.IsPreferredDefaultCandidate -and -not [bool]$defaultState.DefaultSet) {
                    $keptAssTrack.IsDefault = $true
                    $defaultState.DefaultSet = $true
                } else {
                    Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $keptAssTrack
                }
            }
            Write-Log "${Context}ASS->SRT failed for stream $($s.index): $($ass.Reason)" "WARN"; continue
        }
        $srtPath = $ass.Path
        $tempFiles.Add($srtPath)

        # FIX: only set $defaultSet AFTER the SRT is confirmed to exist.
        # Previously this was set before Convert-AssToSrt ran, so a conversion
        # failure left all subsequent tracks with disposition "0".
        $externalTrack = @{
            SrtPath=$srtPath; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$false; IsForced=$entry.IsForced
        }
        $isDefault = Set-SubtitleBuilderBoolDefaultDisposition -Track $externalTrack -DefaultState $defaultState -Decision $decision
        $externalTracks.Add($externalTrack)
        if (-not $isDefault) {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $externalTrack
        }
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertTx3g' })) {
        $entry = $decision.Entry
        $s = $entry.Stream
        if (-not [string]::IsNullOrWhiteSpace($decision.ContainerLogMessage)) {
            Write-Log "${Context}$($decision.ContainerLogMessage)" "DEBUG"
        }
        $tempSrt = Join-Path $script:processingDir "sub_tx3g_$([guid]::NewGuid().ToString('N')).srt"
        $extract = Convert-Tx3gToSrt -SourceFile $SourceFile -StreamIndex ([int]$s.index) -StreamInfo $entry -DestinationPath $tempSrt -Context $Context
        if (-not $extract.Ok) {
            if ($extract.Failure) {
                $failures.Add($extract.Failure)
            } else {
                $failures.Add((New-Tx3gFailureRecord -Entry $entry -Reason $extract.Reason -ErrorCode $extract.ErrorCode -ReproPath $extract.ReproPath -ErrorText $extract.ErrorText))
            }
            Write-Log "${Context}TX3G->SRT failed for stream $($s.index)" "WARN"
            continue
        }
        $tempFiles.Add($extract.Path)

        $externalTrack = @{
            SrtPath=$extract.Path; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$false; IsForced=$entry.IsForced
        }
        $isDefault = Set-SubtitleBuilderBoolDefaultDisposition -Track $externalTrack -DefaultState $defaultState -Decision $decision
        $entry.IsDefault = $isDefault
        $externalTracks.Add($externalTrack)
        if (-not $isDefault) {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $externalTrack
        }
        $tx3gTracks.Add((New-SubtitleBuilderConvertedSrtSidecarTrack -SrtPath $extract.Path -Entry $entry -Decision $decision -CueCount $extract.CueCount -OriginalPreserved:$false))
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertBdpgs' })) {
        $entry = $decision.Entry
        $s = $entry.Stream
        $mkvTid = if ($tidMap.ContainsKey($s.index)) { $tidMap[$s.index] } else { $s.index }
        $keptBdpgsTrack = $null
        if ([bool]$decision.PreserveOriginal) {
            $keptBdpgsTrack = @{
                MkvTid    = $mkvTid
                Lang      = $entry.Lang
                Title     = "$($entry.Title) $($decision.OriginalTitleSuffix)"
                IsDefault = $false
                IsForced  = $entry.IsForced
            }
            $sourceTracks.Add($keptBdpgsTrack)
        }

        $tempSrt = Join-Path $script:processingDir "sub_bdpgs_$([guid]::NewGuid().ToString('N')).srt"
        $ocr = Convert-BdpgsToSrt -SourceFile $SourceFile -StreamIndex ([int]$s.index) -StreamInfo $entry -DestinationPath $tempSrt -Context $Context
        if (-not $ocr.Ok) {
            if ($ocr.Failure) { $failures.Add($ocr.Failure) }
            if ($keptBdpgsTrack -and -not $entry.IsSupplemental) {
                if ([bool]$decision.IsPreferredDefaultCandidate -and -not [bool]$defaultState.DefaultSet) {
                    $keptBdpgsTrack.IsDefault = $true
                    $defaultState.DefaultSet = $true
                } else {
                    Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $keptBdpgsTrack
                }
            }
            Write-Log "${Context}BDPGS->SRT failed for stream $($s.index): $($ocr.Reason)" "WARN"
            continue
        }
        $tempFiles.Add($ocr.Path)

        $externalTrack = @{
            SrtPath=$ocr.Path; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$false; IsForced=$entry.IsForced
        }
        $isDefault = Set-SubtitleBuilderBoolDefaultDisposition -Track $externalTrack -DefaultState $defaultState -Decision $decision
        $entry.IsDefault = $isDefault
        $externalTracks.Add($externalTrack)
        if (-not $isDefault) {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $externalTrack
        }
        $bdpgsTracks.Add((New-SubtitleBuilderConvertedSrtSidecarTrack -SrtPath $ocr.Path -Entry $entry -Decision $decision -CueCount $ocr.CueCount -OriginalPreserved:($null -ne $keptBdpgsTrack)))
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertVobSub' })) {
        $entry = $decision.Entry
        $s = $entry.Stream
        $sourceKind = if ($entry.ContainsKey('SourceKind')) { [string]$entry.SourceKind } else { 'embedded' }
        $keptVobSubTrack = $null
        if ($sourceKind -ne 'sidecar' -and $s) {
            $mkvTid = if ($tidMap.ContainsKey($s.index)) { $tidMap[$s.index] } else { $s.index }
            if ([bool]$decision.PreserveOriginal) {
                $keptVobSubTrack = @{
                    MkvTid    = $mkvTid
                    Lang      = $entry.Lang
                    Title     = "$($entry.Title) $($decision.OriginalTitleSuffix)"
                    IsDefault = $false
                    IsForced  = $entry.IsForced
                }
                $sourceTracks.Add($keptVobSubTrack)
            }
        }

        $tempSrt = Join-Path $script:processingDir "sub_vobsub_$([guid]::NewGuid().ToString('N')).srt"
        $ocr = Convert-VobSubToSrt -SourceFile $SourceFile -StreamIndex $(if ($s) { [int]$s.index } else { -1 }) -StreamInfo $entry -DestinationPath $tempSrt -Context $Context
        if (-not $ocr.Ok) {
            if ($ocr.Failure) { $failures.Add($ocr.Failure) }
            if ($keptVobSubTrack -and -not $entry.IsSupplemental) {
                if ([bool]$decision.IsPreferredDefaultCandidate -and -not [bool]$defaultState.DefaultSet) {
                    $keptVobSubTrack.IsDefault = $true
                    $defaultState.DefaultSet = $true
                } else {
                    Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $keptVobSubTrack
                }
            }
            $sourceText = if ($s) { "stream $($s.index)" } else { "sidecar $([System.IO.Path]::GetFileName([string]$entry.IdxPath))" }
            Write-Log "${Context}VobSub->SRT failed for ${sourceText}: $($ocr.Reason)" "WARN"
            continue
        }
        $tempFiles.Add($ocr.Path)

        $externalTrack = @{
            SrtPath=$ocr.Path; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$false; IsForced=$entry.IsForced
        }
        $isDefault = Set-SubtitleBuilderBoolDefaultDisposition -Track $externalTrack -DefaultState $defaultState -Decision $decision
        $entry.IsDefault = $isDefault
        $externalTracks.Add($externalTrack)
        if (-not $isDefault) {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $externalTrack
        }
        $vobSubTracks.Add((New-SubtitleBuilderConvertedSrtSidecarTrack -SrtPath $ocr.Path -Entry $entry -Decision $decision -CueCount $ocr.CueCount -OriginalPreserved:($null -ne $keptVobSubTrack)))
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'Keep' })) {
        $entry = $decision.Entry
        $s      = $entry.Stream
        if ([bool]$decision.RoutesToReview) {
            if ($decision.ReviewFailureKind -eq 'bdpgs') {
                $failures.Add((New-BdpgsFailureRecord -Entry $entry -Reason $decision.ReviewReason -ErrorCode $decision.ReviewErrorCode))
            } elseif ($decision.ReviewFailureKind -eq 'vobsub') {
                $failures.Add((New-VobSubFailureRecord -Entry $entry -Reason $decision.ReviewReason -ErrorCode $decision.ReviewErrorCode))
            } else {
                $failures.Add((New-Tx3gFailureRecord -Entry $entry -Reason $decision.ReviewReason -ErrorCode $decision.ReviewErrorCode))
            }
            Write-Log "${Context}SUBTITLE FAILURE: $($decision.ReviewReason)" "ERROR"
            continue
        }
        $mkvTid = if ($tidMap.ContainsKey($s.index)) { $tidMap[$s.index] } else { $s.index }

        $sourceTrack = @{
            MkvTid=$mkvTid; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$false; IsForced=$entry.IsForced
        }
        $isDefault = Set-SubtitleBuilderBoolDefaultDisposition -Track $sourceTrack -DefaultState $defaultState -Decision $decision
        $sourceTracks.Add($sourceTrack)
        if (-not $isDefault) {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $sourceTrack
        }
    }

    Set-SubtitleBuilderFallbackDefault -DefaultState $defaultState -Builder 'Mkvmerge'

    return @{
        SourceTracks   = @($sourceTracks)
        ExternalTracks = @($externalTracks)
        Tx3gTracks     = @($tx3gTracks)
        BdpgsTracks    = @($bdpgsTracks)
        VobSubTracks   = @($vobSubTracks)
        TempFiles      = @($tempFiles)
        Failures       = @($failures)
    }
}

function ConvertTo-FfmpegSubtitleFilterPath {
    param([Parameter(Mandatory)] [string] $Path)

    $resolved = try { [System.IO.Path]::GetFullPath($Path) } catch { [string]$Path }
    $text = $resolved.Replace('\', '/')
    $text = $text.Replace('\', '\\')
    $text = $text.Replace(':', '\:')
    $text = $text.Replace("'", "\'")
    $text = $text.Replace(',', '\,')
    $text = $text.Replace('[', '\[')
    $text = $text.Replace(']', '\]')
    return $text
}

function New-SubtitleBurnFailureRecord {
    param(
        $Entry,
        [Parameter(Mandatory)] [string] $Reason,
        [string] $ErrorCode = 'SUBTITLE_BURN_UNSUPPORTED'
    )

    $streamIndex = -1
    try {
        if ($Entry -and $Entry.ContainsKey('Stream') -and $Entry.Stream -and $Entry.Stream.PSObject.Properties['index']) {
            $streamIndex = [int]$Entry.Stream.index
        }
    } catch {}
    [pscustomobject]@{
        Reason     = $Reason
        ErrorCode  = $ErrorCode
        StreamIndex = $streamIndex
        ReproPath  = ''
        ErrorText  = ''
    }
}

function New-SubtitleBurnVideoFilterArgsForFFmpeg {
    param(
        $FilterResult,
        [Parameter(Mandatory)] [string] $SourceFile,
        [string] $Context = ''
    )

    $burnEntries = @($FilterResult.Burn | Where-Object { $null -ne $_ })
    if ($burnEntries.Count -eq 0) {
        return @{ VideoFilterArgs=@(); Failures=@(); BurnTrack=$null }
    }
    if ($burnEntries.Count -ne 1) {
        return @{
            VideoFilterArgs = @()
            Failures = @([pscustomobject]@{
                Reason = "Subtitle burn-in requires exactly one selected subtitle track; found $($burnEntries.Count)."
                ErrorCode = 'SUBTITLE_BURN_MULTIPLE_TRACKS'
                StreamIndex = -1
                ReproPath = ''
                ErrorText = ''
            })
            BurnTrack = $null
        }
    }

    $entry = $burnEntries[0]
    $codec = ''
    try { $codec = ([string]$entry.Codec).Trim().ToLowerInvariant() } catch {}
    $streamIndex = -1
    try {
        if ($entry.ContainsKey('Stream') -and $entry.Stream -and $entry.Stream.PSObject.Properties['index']) {
            $streamIndex = [int]$entry.Stream.index
        }
    } catch {}
    $subtitleInputOrdinal = $null
    try {
        if ($entry.ContainsKey('SubtitleInputOrdinal')) { $subtitleInputOrdinal = [int]$entry.SubtitleInputOrdinal }
        elseif ($entry.ContainsKey('SubtitleOrdinal')) { $subtitleInputOrdinal = [int]$entry.SubtitleOrdinal }
    } catch {}
    if ($null -eq $subtitleInputOrdinal -or $subtitleInputOrdinal -lt 0) {
        return @{
            VideoFilterArgs = @()
            Failures = @((New-SubtitleBurnFailureRecord -Entry $entry -Reason "Subtitle burn-in could not resolve FFmpeg subtitle input ordinal for stream $streamIndex." -ErrorCode 'SUBTITLE_BURN_STREAM_UNRESOLVED'))
            BurnTrack = $entry
        }
    }

    $textCodecs = @(@(Get-MediaSubtitleCodecTextNames) + @(Get-MediaSubtitleCodecAssNames) | ForEach-Object { ([string]$_).ToLowerInvariant() } | Select-Object -Unique)
    $imageCodecs = @(Get-MediaSubtitleCodecImageNames | ForEach-Object { ([string]$_).ToLowerInvariant() } | Select-Object -Unique)
    if ($codec -in $textCodecs) {
        $filterPath = ConvertTo-FfmpegSubtitleFilterPath -Path $SourceFile
        $graph = "[0:v:0]subtitles=filename='$filterPath':si=$subtitleInputOrdinal[vout]"
    } elseif ($codec -in $imageCodecs) {
        $graph = "[0:v:0][0:s:$subtitleInputOrdinal]overlay=eof_action=pass:repeatlast=0[vout]"
    } else {
        return @{
            VideoFilterArgs = @()
            Failures = @((New-SubtitleBurnFailureRecord -Entry $entry -Reason "Subtitle burn-in does not support codec '$codec' for stream $streamIndex." -ErrorCode 'SUBTITLE_BURN_UNSUPPORTED_CODEC'))
            BurnTrack = $entry
        }
    }

    Write-Log "${Context}SUBTITLE BURN: stream $streamIndex codec=$codec subtitle_ordinal=$subtitleInputOrdinal via subtitle-burn encode profile current_encode_style" "WARN"
    return @{
        VideoFilterArgs = @('-filter_complex', $graph, '-map', '[vout]')
        Failures = @()
        BurnTrack = $entry
    }
}

function Build-SubtitleArgsForFFmpeg {
    param($FilterResult, [string]$DefaultAudioLang, [string]$SourceFile, [string]$Context = "")

    $burnGraph = New-SubtitleBurnVideoFilterArgsForFFmpeg -FilterResult $FilterResult -SourceFile $SourceFile -Context $Context
    if (@($burnGraph.VideoFilterArgs).Count -gt 0 -or @($burnGraph.Failures).Count -gt 0) {
        return @{
            ExtraInputs = @()
            MapArgs     = @()
            VideoFilterArgs = @($burnGraph.VideoFilterArgs)
            TempFiles   = @()
            Tx3gTracks  = @()
            BdpgsTracks = @()
            VobSubTracks = @()
            ConvertedSrtSidecarTracks = @()
            BurnTrack   = $burnGraph.BurnTrack
            Failures    = @($burnGraph.Failures)
            TrackCount  = 0
        }
    }

    $defaultState = New-SubtitleBuilderDefaultState
    $tempFiles  = [System.Collections.Generic.List[string]]::new()
    $tx3gTracks = [System.Collections.Generic.List[hashtable]]::new()
    $bdpgsTracks = [System.Collections.Generic.List[hashtable]]::new()
    $vobSubTracks = [System.Collections.Generic.List[hashtable]]::new()
    $failures   = [System.Collections.Generic.List[object]]::new()

    # Build a single ordered list of all output subtitle tracks.
    # ffmpeg assigns output subtitle indices 0,1,2... in -map order.
    # By building one flat list before emitting any arguments, the index N
    # we write in -c:s:N, -metadata:s:s:N, -disposition:s:N always matches
    # the actual output stream position. The old code split ASS and SRT args
    # into separate lists that were concatenated afterwards, causing the
    # -c:s:N and -disposition:s:N to reference the wrong output streams.
    $allTracks = [System.Collections.Generic.List[hashtable]]::new()

    $convertedSrtCodec = Get-ConvertedSrtCodecForFfmpegOutput
    $canPreserveTx3g = Test-CanPreserveTx3gInFfmpegOutput
    $canPreserveBdpgs = Test-CanPreserveBdpgsInFfmpegOutput
    $canPreserveVobSub = if (Get-Command -Name Test-CanPreserveVobSubInFfmpegOutput -ErrorAction SilentlyContinue) {
        Test-CanPreserveVobSubInFfmpegOutput
    } else {
        $false
    }
    $trackDecisions = Get-SubtitleBuilderTrackDecisionRecords -FilterResult $FilterResult -Builder 'FFmpeg' -CanPreserveTx3g:$canPreserveTx3g -CanPreserveBdpgs:$canPreserveBdpgs -CanPreserveVobSub:$canPreserveVobSub

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertAss' })) {
        $entry = $decision.Entry
        $s = $entry.Stream
        $keptAssTrack = $null

        # Optionally keep the original ASS track
        if ([bool]$decision.PreserveOriginal) {
            $keptAssTrack = @{
                MapArg  = "0:$($s.index)"
                Title   = "$($entry.Title) $($decision.OriginalTitleSuffix)"
                Lang    = $entry.Lang
                Disp    = Get-SubtitleBuilderFfmpegBaseDisposition -Decision $decision
                SrtPath = $null
                Codec   = "copy"
            }
            $allTracks.Add($keptAssTrack)
        }

        $ass = Convert-AssToSrt $SourceFile $s.index $entry
        if (-not $ass.Ok) {
            if ($ass.Failure) { $failures.Add($ass.Failure) }
            if ($keptAssTrack -and -not $entry.IsSupplemental) {
                if ([bool]$decision.IsPreferredDefaultCandidate -and -not [bool]$defaultState.DefaultSet) {
                    Set-SubtitleBuilderFfmpegDefaultDisposition -Track $keptAssTrack
                    $defaultState.DefaultSet = $true
                } else {
                    Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $keptAssTrack
                }
            }
            Write-Log "${Context}SUB: ASS conversion failed for stream $($s.index): $($ass.Reason)" "WARN"
            continue
        }
        $srtPath = $ass.Path
        $tempFiles.Add($srtPath)

        # FIX: only update $defaultSet AFTER the SRT is confirmed to exist.
        $disp = Get-SubtitleBuilderFfmpegConvertedDisposition -Decision $decision -DefaultState $defaultState
        $entry.IsDefault = ($disp -eq 'default' -or $disp -eq 'default+forced')

        $track = @{
            MapArg  = $null       # assigned below when SRT inputs are numbered
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $srtPath
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
        if (Test-ConfiguredOutputContainerIsMp4) {
            $tx3gTracks.Add((New-SubtitleBuilderConvertedSrtSidecarTrack -SrtPath $srtPath -Entry $entry -Decision $decision -CueCount $ass.CueCount -OriginalPreserved:($null -ne $keptAssTrack)))
        }
        if ($disp -eq "0") {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $track
        }
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertTx3g' })) {
        $entry = $decision.Entry
        $s = $entry.Stream
        $keptTx3gTrack = $null

        if ([bool]$decision.PreserveOriginal) {
            $keptTx3gTrack = @{
                MapArg  = "0:$($s.index)"
                Title   = "$($entry.Title) $($decision.OriginalTitleSuffix)"
                Lang    = $entry.Lang
                Disp    = Get-SubtitleBuilderFfmpegBaseDisposition -Decision $decision
                SrtPath = $null
                Codec   = "copy"
            }
            $allTracks.Add($keptTx3gTrack)
        } elseif (-not [string]::IsNullOrWhiteSpace($decision.ContainerLogMessage)) {
            Write-Log "${Context}$($decision.ContainerLogMessage)" "DEBUG"
        }

        $tempSrt = Join-Path $script:processingDir "sub_tx3g_$([guid]::NewGuid().ToString('N')).srt"
        $extract = Convert-Tx3gToSrt -SourceFile $SourceFile -StreamIndex ([int]$s.index) -StreamInfo $entry -DestinationPath $tempSrt -Context $Context
        if (-not $extract.Ok) {
            if ($extract.Failure) {
                $failures.Add($extract.Failure)
            } else {
                $failures.Add((New-Tx3gFailureRecord -Entry $entry -Reason $extract.Reason -ErrorCode $extract.ErrorCode -ReproPath $extract.ReproPath -ErrorText $extract.ErrorText))
            }
            if ($keptTx3gTrack -and -not $entry.IsSupplemental) {
                if ([bool]$decision.IsPreferredDefaultCandidate -and -not [bool]$defaultState.DefaultSet) {
                    Set-SubtitleBuilderFfmpegDefaultDisposition -Track $keptTx3gTrack
                    $defaultState.DefaultSet = $true
                } else {
                    Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $keptTx3gTrack
                }
            }
            Write-Log "${Context}SUB: TX3G conversion failed for stream $($s.index)" "WARN"
            continue
        }
        $tempFiles.Add($extract.Path)

        $disp = Get-SubtitleBuilderFfmpegConvertedDisposition -Decision $decision -DefaultState $defaultState
        $entry.IsDefault = ($disp -eq 'default' -or $disp -eq 'default+forced')

        $track = @{
            MapArg  = $null
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $extract.Path
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
        if ($disp -eq "0") {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $track
        }
        $tx3gTracks.Add((New-SubtitleBuilderConvertedSrtSidecarTrack -SrtPath $extract.Path -Entry $entry -Decision $decision -CueCount $extract.CueCount -OriginalPreserved:($null -ne $keptTx3gTrack)))
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertBdpgs' })) {
        $entry = $decision.Entry
        $s = $entry.Stream
        $keptBdpgsTrack = $null

        if ([bool]$decision.PreserveOriginal) {
            $keptBdpgsTrack = @{
                MapArg  = "0:$($s.index)"
                Title   = "$($entry.Title) $($decision.OriginalTitleSuffix)"
                Lang    = $entry.Lang
                Disp    = Get-SubtitleBuilderFfmpegBaseDisposition -Decision $decision
                SrtPath = $null
                Codec   = "copy"
            }
            $allTracks.Add($keptBdpgsTrack)
        } elseif (-not [string]::IsNullOrWhiteSpace($decision.ContainerLogMessage)) {
            Write-Log "${Context}$($decision.ContainerLogMessage)" "DEBUG"
        }

        $tempSrt = Join-Path $script:processingDir "sub_bdpgs_$([guid]::NewGuid().ToString('N')).srt"
        $ocr = Convert-BdpgsToSrt -SourceFile $SourceFile -StreamIndex ([int]$s.index) -StreamInfo $entry -DestinationPath $tempSrt -Context $Context
        if (-not $ocr.Ok) {
            if ($ocr.Failure) { $failures.Add($ocr.Failure) }
            if ($keptBdpgsTrack -and -not $entry.IsSupplemental) {
                if ([bool]$decision.IsPreferredDefaultCandidate -and -not [bool]$defaultState.DefaultSet) {
                    Set-SubtitleBuilderFfmpegDefaultDisposition -Track $keptBdpgsTrack
                    $defaultState.DefaultSet = $true
                } else {
                    Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $keptBdpgsTrack
                }
            }
            Write-Log "${Context}SUB: BDPGS OCR failed for stream $($s.index): $($ocr.Reason)" "WARN"
            continue
        }
        $tempFiles.Add($ocr.Path)

        $disp = Get-SubtitleBuilderFfmpegConvertedDisposition -Decision $decision -DefaultState $defaultState
        $entry.IsDefault = ($disp -eq 'default' -or $disp -eq 'default+forced')

        $track = @{
            MapArg  = $null
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $ocr.Path
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
        if ($disp -eq "0") {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $track
        }
        $bdpgsTracks.Add((New-SubtitleBuilderConvertedSrtSidecarTrack -SrtPath $ocr.Path -Entry $entry -Decision $decision -CueCount $ocr.CueCount -OriginalPreserved:($null -ne $keptBdpgsTrack)))
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'ConvertVobSub' })) {
        $entry = $decision.Entry
        $s = $entry.Stream
        $sourceKind = if ($entry.ContainsKey('SourceKind')) { [string]$entry.SourceKind } else { 'embedded' }
        $keptVobSubTrack = $null

        if ($sourceKind -ne 'sidecar' -and $s -and [bool]$decision.PreserveOriginal) {
            $keptVobSubTrack = @{
                MapArg  = "0:$($s.index)"
                Title   = "$($entry.Title) $($decision.OriginalTitleSuffix)"
                Lang    = $entry.Lang
                Disp    = Get-SubtitleBuilderFfmpegBaseDisposition -Decision $decision
                SrtPath = $null
                Codec   = "copy"
            }
            $allTracks.Add($keptVobSubTrack)
        } elseif (-not [string]::IsNullOrWhiteSpace($decision.ContainerLogMessage)) {
            Write-Log "${Context}$($decision.ContainerLogMessage)" "DEBUG"
        }

        $tempSrt = Join-Path $script:processingDir "sub_vobsub_$([guid]::NewGuid().ToString('N')).srt"
        $ocr = Convert-VobSubToSrt -SourceFile $SourceFile -StreamIndex $(if ($s) { [int]$s.index } else { -1 }) -StreamInfo $entry -DestinationPath $tempSrt -Context $Context
        if (-not $ocr.Ok) {
            if ($ocr.Failure) { $failures.Add($ocr.Failure) }
            if ($keptVobSubTrack -and -not $entry.IsSupplemental) {
                if ([bool]$decision.IsPreferredDefaultCandidate -and -not [bool]$defaultState.DefaultSet) {
                    Set-SubtitleBuilderFfmpegDefaultDisposition -Track $keptVobSubTrack
                    $defaultState.DefaultSet = $true
                } else {
                    Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $keptVobSubTrack
                }
            }
            $sourceText = if ($s) { "stream $($s.index)" } else { "sidecar $([System.IO.Path]::GetFileName([string]$entry.IdxPath))" }
            Write-Log "${Context}SUB: VobSub OCR failed for ${sourceText}: $($ocr.Reason)" "WARN"
            continue
        }
        $tempFiles.Add($ocr.Path)

        $disp = Get-SubtitleBuilderFfmpegConvertedDisposition -Decision $decision -DefaultState $defaultState
        $entry.IsDefault = ($disp -eq 'default' -or $disp -eq 'default+forced')

        $track = @{
            MapArg  = $null
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $ocr.Path
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
        if ($disp -eq "0") {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $track
        }
        $vobSubTracks.Add((New-SubtitleBuilderConvertedSrtSidecarTrack -SrtPath $ocr.Path -Entry $entry -Decision $decision -CueCount $ocr.CueCount -OriginalPreserved:($null -ne $keptVobSubTrack)))
    }

    foreach ($decision in @($trackDecisions | Where-Object { $_.Action -eq 'Keep' })) {
        $entry = $decision.Entry
        $s    = $entry.Stream
        if ([bool]$decision.RoutesToReview) {
            if ($decision.ReviewFailureKind -eq 'bdpgs') {
                $failures.Add((New-BdpgsFailureRecord -Entry $entry -Reason $decision.ReviewReason -ErrorCode $decision.ReviewErrorCode))
            } elseif ($decision.ReviewFailureKind -eq 'vobsub') {
                $failures.Add((New-VobSubFailureRecord -Entry $entry -Reason $decision.ReviewReason -ErrorCode $decision.ReviewErrorCode))
            } else {
                $failures.Add((New-Tx3gFailureRecord -Entry $entry -Reason $decision.ReviewReason -ErrorCode $decision.ReviewErrorCode))
            }
            Write-Log "${Context}SUBTITLE FAILURE: $($decision.ReviewReason)" "ERROR"
            continue
        }
        $disp = Get-SubtitleBuilderFfmpegConvertedDisposition -Decision $decision -DefaultState $defaultState
        $track = @{
            MapArg  = "0:$($s.index)"
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $null
            Codec   = "copy"
        }
        $allTracks.Add($track)
        if ($disp -eq "0") {
            Add-SubtitleBuilderFallbackDefaultCandidate -DefaultState $defaultState -Decision $decision -Track $track
        }
    }

    Set-SubtitleBuilderFallbackDefault -DefaultState $defaultState -Builder 'FFmpeg'

    if (Test-ConfiguredOutputContainerIsMp4) {
        $sidecarCandidates = @($tx3gTracks) + @($bdpgsTracks) + @($vobSubTracks)
        $selectedSidecar = @(
            $sidecarCandidates |
                Where-Object { $_ -and $_.SrtPath } |
                Sort-Object `
                    @{ Expression = { if ($_.StreamInfo -and $_.StreamInfo.ContainsKey('IsDefault') -and [bool]$_.StreamInfo.IsDefault) { 0 } else { 1 } } }, `
                    @{ Expression = { if ($_.StreamInfo -and $_.StreamInfo.ContainsKey('IsSupplemental') -and [bool]$_.StreamInfo.IsSupplemental) { 1 } else { 0 } } }, `
                    @{ Expression = { if ($_.StreamInfo -and $_.StreamInfo.ContainsKey('SubtitleOrdinal')) { [int]$_.StreamInfo.SubtitleOrdinal } else { [int]::MaxValue } } }
        )
        $selectedConvertedSrtSidecarTracks = if ($selectedSidecar.Count -gt 0) { @($selectedSidecar[0]) } else { @() }
        if ($sidecarCandidates.Count -gt 1) {
            Write-Log "${Context}SUB: MP4 compatibility selected one external SRT sidecar and dropped $($sidecarCandidates.Count - 1) additional converted SRT candidate(s)." "WARN"
        } else {
            Write-Log "${Context}SUB: MP4 compatibility emits no embedded subtitle tracks." "DEBUG"
        }
        return @{
            ExtraInputs = @()
            MapArgs     = @()
            VideoFilterArgs = @()
            TempFiles   = @($tempFiles)
            Tx3gTracks  = @($selectedConvertedSrtSidecarTracks)
            BdpgsTracks = @()
            VobSubTracks = @()
            ConvertedSrtSidecarTracks = @($selectedConvertedSrtSidecarTracks)
            Failures    = @($failures)
            TrackCount  = 0
            DroppedEmbeddedTrackCount = $allTracks.Count
        }
    }

    # Number the SRT extra inputs (1, 2, 3...) and back-fill their MapArg
    $extraInputs = [System.Collections.Generic.List[string]]::new()
    $inputIndex  = 1
    foreach ($t in $allTracks) {
        if ($t.SrtPath) {
            $extraInputs.AddRange([string[]]@("-i", $t.SrtPath))
            $t.MapArg = "${inputIndex}:s:0"
            $inputIndex++
        }
    }

    # Emit all subtitle args in insertion order so -c:s:N matches output position N
    $mapArgs = [System.Collections.Generic.List[string]]::new()
    for ($n = 0; $n -lt $allTracks.Count; $n++) {
        $t = $allTracks[$n]
        $codec = if ($t.ContainsKey('Codec') -and $t.Codec) { [string]$t.Codec } else { "copy" }
        $mapArgs.AddRange([string[]]@("-map",       $t.MapArg))
        $mapArgs.AddRange([string[]]@("-c:s:$n",    $codec))
        $mapArgs.AddRange([string[]]@("-metadata:s:s:$n", "title=$($t.Title)"))
        $mapArgs.AddRange([string[]]@("-metadata:s:s:$n", "language=$($t.Lang)"))
        $mapArgs.AddRange([string[]]@("-disposition:s:$n", $t.Disp))
        Write-Log "${Context}SUB track $n : $($t.Title) [$($t.Lang)] codec=$codec disp=$($t.Disp)" "DEBUG"
    }

    return @{
        ExtraInputs = @($extraInputs)
        MapArgs     = @($mapArgs)
        VideoFilterArgs = @()
        TempFiles   = @($tempFiles)
        Tx3gTracks  = @($tx3gTracks)
        BdpgsTracks = @($bdpgsTracks)
        VobSubTracks = @($vobSubTracks)
        ConvertedSrtSidecarTracks = @(@($tx3gTracks) + @($bdpgsTracks) + @($vobSubTracks))
        Failures    = @($failures)
        TrackCount  = $allTracks.Count
    }
}
