# ==============================================================================
# engine\subtitles\builders.ps1
# ==============================================================================
# Subtitle mux/encode argument builders for mkvmerge and FFmpeg.
# Dot-sourced by engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

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
    $tempFiles      = [System.Collections.Generic.List[string]]::new()
    $failures       = [System.Collections.Generic.List[object]]::new()
    $defaultSet     = $false
    $fallbackDefaultCandidates = [System.Collections.Generic.List[hashtable]]::new()

    # Default subtitle disposition follows the configured subtitle language
    # policy; undefined/blank tracks are only fallback candidates.
    $IsPreferredDefaultSub = {
        param($entry)
        return (Test-SubtitleEntryLanguageIsPreferredDefault -Entry $entry)
    }
    $IsFallbackDefaultSub = {
        param($entry)
        return (Test-SubtitleEntryLanguageIsFallbackDefault -Entry $entry)
    }

    # Per-show overrides may replace conversion preservation policy.
    $effectiveDropAss = Get-EffectiveSubtitleSwitch -Name 'DropAssAfterConversion' -Default $false
    $effectiveDropTx3g = Get-EffectiveSubtitleSwitch -Name 'DropTx3gAfterConversion' -Default $false
    $effectiveDropBdpgs = Get-EffectiveSubtitleSwitch -Name 'DropBdpgsAfterConversion' -Default $false

    foreach ($entry in $FilterResult.Convert) {
        $s      = $entry.Stream
        $mkvTid = if ($tidMap.ContainsKey($s.index)) { $tidMap[$s.index] } else { $s.index }
        $keptAssTrack = $null
        if (-not $effectiveDropAss) {
            $keptAssTrack = @{
                MkvTid    = $mkvTid
                Lang      = $entry.Lang
                Title     = "$($entry.Title) [ASS]"
                IsDefault = $false
                IsForced  = $entry.IsForced
            }
            $sourceTracks.Add($keptAssTrack)
        }

        $ass = Convert-AssToSrt $SourceFile $s.index $entry
        if (-not $ass.Ok) {
            if ($ass.Failure) { $failures.Add($ass.Failure) }
            if ($keptAssTrack -and -not $entry.IsSupplemental) {
                if ((& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
                    $keptAssTrack.IsDefault = $true
                    $defaultSet = $true
                } elseif (& $IsFallbackDefaultSub $entry) {
                    $fallbackDefaultCandidates.Add($keptAssTrack)
                }
            }
            Write-Log "${Context}ASS->SRT failed for stream $($s.index): $($ass.Reason)" "WARN"; continue
        }
        $srtPath = $ass.Path
        $tempFiles.Add($srtPath)

        # FIX: only set $defaultSet AFTER the SRT is confirmed to exist.
        # Previously this was set before Convert-AssToSrt ran, so a conversion
        # failure left all subsequent tracks with disposition "0".
        $isDefault = $false
        if (-not $entry.IsSupplemental) {
            if ((& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
                $isDefault = $true; $defaultSet = $true
            }
        }
        $externalTrack = @{
            SrtPath=$srtPath; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$isDefault; IsForced=$entry.IsForced
        }
        $externalTracks.Add($externalTrack)
        if (-not $entry.IsSupplemental -and -not $isDefault -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($externalTrack)
        }
    }

    foreach ($entry in @($FilterResult.Tx3gConvert)) {
        $s = $entry.Stream
        $tx3gPreserveReason = 'drop_original_tx3g_enabled'
        if (-not $effectiveDropTx3g) {
            $tx3gPreserveReason = 'container_does_not_preserve_tx3g'
            Write-Log "${Context}TX3G original stream $($s.index) cannot be preserved as tx3g in Matroska remux output; muxing converted SRT only" "DEBUG"
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

        $isDefault = $false
        if (-not $entry.IsSupplemental -and (& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
            $isDefault = $true; $defaultSet = $true
        }
        $entry.IsDefault = $isDefault
        $externalTrack = @{
            SrtPath=$extract.Path; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$isDefault; IsForced=$entry.IsForced
        }
        $externalTracks.Add($externalTrack)
        if (-not $entry.IsSupplemental -and -not $isDefault -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($externalTrack)
        }
        $tx3gTracks.Add(@{
            SrtPath    = $extract.Path
            StreamInfo = $entry
            CueCount   = $extract.CueCount
            OriginalPreserved = $false
            OriginalPreserveReason = $tx3gPreserveReason
        })
    }

    foreach ($entry in @($FilterResult.BdpgsConvert)) {
        $s = $entry.Stream
        $mkvTid = if ($tidMap.ContainsKey($s.index)) { $tidMap[$s.index] } else { $s.index }
        $keptBdpgsTrack = $null
        $bdpgsPreserveReason = 'drop_original_bdpgs_enabled'
        if (-not $effectiveDropBdpgs) {
            $bdpgsPreserveReason = 'preserved'
            $keptBdpgsTrack = @{
                MkvTid    = $mkvTid
                Lang      = $entry.Lang
                Title     = "$($entry.Title) [BDPGS]"
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
                if ((& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
                    $keptBdpgsTrack.IsDefault = $true
                    $defaultSet = $true
                } elseif (& $IsFallbackDefaultSub $entry) {
                    $fallbackDefaultCandidates.Add($keptBdpgsTrack)
                }
            }
            Write-Log "${Context}BDPGS->SRT failed for stream $($s.index): $($ocr.Reason)" "WARN"
            continue
        }
        $tempFiles.Add($ocr.Path)

        $isDefault = $false
        if (-not $entry.IsSupplemental -and (& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
            $isDefault = $true; $defaultSet = $true
        }
        $entry.IsDefault = $isDefault
        $externalTrack = @{
            SrtPath=$ocr.Path; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$isDefault; IsForced=$entry.IsForced
        }
        $externalTracks.Add($externalTrack)
        if (-not $entry.IsSupplemental -and -not $isDefault -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($externalTrack)
        }
        $bdpgsTracks.Add(@{
            SrtPath    = $ocr.Path
            StreamInfo = $entry
            CueCount   = $ocr.CueCount
            OriginalPreserved = ($null -ne $keptBdpgsTrack)
            OriginalPreserveReason = $bdpgsPreserveReason
        })
    }

    foreach ($entry in $FilterResult.Keep) {
        $s      = $entry.Stream
        if ($entry.IsTx3g) {
            $reason = "Matroska remux output cannot preserve TX3G stream $($s.index); enable ConvertTx3gToSrt to mux a converted SRT track."
            $failures.Add((New-Tx3gFailureRecord -Entry $entry -Reason $reason -ErrorCode 'SUBTITLE_TX3G_CONTAINER_UNSUPPORTED'))
            Write-Log "${Context}SUBTITLE FAILURE: $reason" "ERROR"
            continue
        }
        $mkvTid = if ($tidMap.ContainsKey($s.index)) { $tidMap[$s.index] } else { $s.index }

        $isDefault = $false
        if (-not $entry.IsSupplemental -and (& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
            $isDefault = $true; $defaultSet = $true
        }
        $sourceTrack = @{
            MkvTid=$mkvTid; Lang=$entry.Lang; Title=$entry.Title
            IsDefault=$isDefault; IsForced=$entry.IsForced
        }
        $sourceTracks.Add($sourceTrack)
        if (-not $entry.IsSupplemental -and -not $isDefault -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($sourceTrack)
        }
    }

    if (-not $defaultSet -and $fallbackDefaultCandidates.Count -gt 0) {
        $fallbackDefaultCandidates[0].IsDefault = $true
    }

    return @{
        SourceTracks   = @($sourceTracks)
        ExternalTracks = @($externalTracks)
        Tx3gTracks     = @($tx3gTracks)
        BdpgsTracks    = @($bdpgsTracks)
        TempFiles      = @($tempFiles)
        Failures       = @($failures)
    }
}

function Build-SubtitleArgsForFFmpeg {
    param($FilterResult, [string]$DefaultAudioLang, [string]$SourceFile, [string]$Context = "")

    # Default subtitle disposition follows the configured subtitle language
    # policy; undefined/blank tracks are only fallback candidates.
    $IsPreferredDefaultSub = {
        param($entry)
        return (Test-SubtitleEntryLanguageIsPreferredDefault -Entry $entry)
    }
    $IsFallbackDefaultSub = {
        param($entry)
        return (Test-SubtitleEntryLanguageIsFallbackDefault -Entry $entry)
    }

    $defaultSet = $false
    $tempFiles  = [System.Collections.Generic.List[string]]::new()
    $tx3gTracks = [System.Collections.Generic.List[hashtable]]::new()
    $bdpgsTracks = [System.Collections.Generic.List[hashtable]]::new()
    $failures   = [System.Collections.Generic.List[object]]::new()
    $fallbackDefaultCandidates = [System.Collections.Generic.List[hashtable]]::new()

    # Build a single ordered list of all output subtitle tracks.
    # ffmpeg assigns output subtitle indices 0,1,2... in -map order.
    # By building one flat list before emitting any arguments, the index N
    # we write in -c:s:N, -metadata:s:s:N, -disposition:s:N always matches
    # the actual output stream position. The old code split ASS and SRT args
    # into separate lists that were concatenated afterwards, causing the
    # -c:s:N and -disposition:s:N to reference the wrong output streams.
    $allTracks = [System.Collections.Generic.List[hashtable]]::new()

    # Per-show overrides may replace conversion preservation policy.
    $effectiveDropAss = Get-EffectiveSubtitleSwitch -Name 'DropAssAfterConversion' -Default $false
    $effectiveDropTx3g = Get-EffectiveSubtitleSwitch -Name 'DropTx3gAfterConversion' -Default $false
    $effectiveDropBdpgs = Get-EffectiveSubtitleSwitch -Name 'DropBdpgsAfterConversion' -Default $false
    $convertedSrtCodec = Get-ConvertedSrtCodecForFfmpegOutput
    $canPreserveTx3g = Test-CanPreserveTx3gInFfmpegOutput
    $canPreserveBdpgs = Test-CanPreserveBdpgsInFfmpegOutput

    foreach ($entry in $FilterResult.Convert) {
        $s = $entry.Stream
        $keptAssTrack = $null

        # Optionally keep the original ASS track
        if (-not $effectiveDropAss) {
            $keptAssTrack = @{
                MapArg  = "0:$($s.index)"
                Title   = "$($entry.Title) [ASS]"
                Lang    = $entry.Lang
                Disp    = if ($entry.IsForced) { "forced" } else { "0" }
                SrtPath = $null
                Codec   = "copy"
            }
            $allTracks.Add($keptAssTrack)
        }

        $ass = Convert-AssToSrt $SourceFile $s.index $entry
        if (-not $ass.Ok) {
            if ($ass.Failure) { $failures.Add($ass.Failure) }
            if ($keptAssTrack -and -not $entry.IsSupplemental) {
                if ((& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
                    $keptAssTrack.Disp = if ($entry.IsForced) { "default+forced" } else { "default" }
                    $defaultSet = $true
                } elseif (& $IsFallbackDefaultSub $entry) {
                    $fallbackDefaultCandidates.Add($keptAssTrack)
                }
            }
            Write-Log "${Context}SUB: ASS conversion failed for stream $($s.index): $($ass.Reason)" "WARN"
            continue
        }
        $srtPath = $ass.Path
        $tempFiles.Add($srtPath)

        # FIX: only update $defaultSet AFTER the SRT is confirmed to exist.
        $disp = "0"
        if (-not $entry.IsSupplemental -and (& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
            $disp = "default"; $defaultSet = $true
        }
        if ($entry.IsForced) { $disp = if ($disp -eq "default") { "default+forced" } else { "forced" } }

        $track = @{
            MapArg  = $null       # assigned below when SRT inputs are numbered
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $srtPath
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
        if (-not $entry.IsSupplemental -and $disp -eq "0" -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($track)
        }
    }

    foreach ($entry in @($FilterResult.Tx3gConvert)) {
        $s = $entry.Stream
        $keptTx3gTrack = $null
        $tx3gPreserveReason = 'drop_original_tx3g_enabled'

        if (-not $effectiveDropTx3g) {
            if ($canPreserveTx3g) {
                $tx3gPreserveReason = 'preserved'
                $keptTx3gTrack = @{
                    MapArg  = "0:$($s.index)"
                    Title   = "$($entry.Title) [TX3G]"
                    Lang    = $entry.Lang
                    Disp    = if ($entry.IsForced) { "forced" } else { "0" }
                    SrtPath = $null
                    Codec   = "copy"
                }
                $allTracks.Add($keptTx3gTrack)
            } else {
                $tx3gPreserveReason = 'container_does_not_preserve_tx3g'
                Write-Log "${Context}TX3G original stream $($s.index) cannot be preserved as tx3g in $((Get-ConfiguredOutputContainerName).ToUpperInvariant()) output; muxing converted SRT only" "DEBUG"
            }
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
                if ((& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
                    $keptTx3gTrack.Disp = if ($entry.IsForced) { "default+forced" } else { "default" }
                    $defaultSet = $true
                } elseif (& $IsFallbackDefaultSub $entry) {
                    $fallbackDefaultCandidates.Add($keptTx3gTrack)
                }
            }
            Write-Log "${Context}SUB: TX3G conversion failed for stream $($s.index)" "WARN"
            continue
        }
        $tempFiles.Add($extract.Path)

        $disp = "0"
        if (-not $entry.IsSupplemental -and (& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
            $disp = "default"; $defaultSet = $true
            $entry.IsDefault = $true
        } else {
            $entry.IsDefault = $false
        }
        if ($entry.IsForced) { $disp = if ($disp -eq "default") { "default+forced" } else { "forced" } }

        $track = @{
            MapArg  = $null
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $extract.Path
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
        if (-not $entry.IsSupplemental -and $disp -eq "0" -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($track)
        }
        $tx3gTracks.Add(@{
            SrtPath    = $extract.Path
            StreamInfo = $entry
            CueCount   = $extract.CueCount
            OriginalPreserved = ($null -ne $keptTx3gTrack)
            OriginalPreserveReason = $tx3gPreserveReason
        })
    }

    foreach ($entry in @($FilterResult.BdpgsConvert)) {
        $s = $entry.Stream
        $keptBdpgsTrack = $null
        $bdpgsPreserveReason = 'drop_original_bdpgs_enabled'

        if (-not $effectiveDropBdpgs) {
            if ($canPreserveBdpgs) {
                $bdpgsPreserveReason = 'preserved'
                $keptBdpgsTrack = @{
                    MapArg  = "0:$($s.index)"
                    Title   = "$($entry.Title) [BDPGS]"
                    Lang    = $entry.Lang
                    Disp    = if ($entry.IsForced) { "forced" } else { "0" }
                    SrtPath = $null
                    Codec   = "copy"
                }
                $allTracks.Add($keptBdpgsTrack)
            } else {
                $bdpgsPreserveReason = 'container_does_not_preserve_bdpgs'
                Write-Log "${Context}BDPGS original stream $($s.index) cannot be preserved in $((Get-ConfiguredOutputContainerName).ToUpperInvariant()) output; muxing OCR SRT only" "DEBUG"
            }
        }

        $tempSrt = Join-Path $script:processingDir "sub_bdpgs_$([guid]::NewGuid().ToString('N')).srt"
        $ocr = Convert-BdpgsToSrt -SourceFile $SourceFile -StreamIndex ([int]$s.index) -StreamInfo $entry -DestinationPath $tempSrt -Context $Context
        if (-not $ocr.Ok) {
            if ($ocr.Failure) { $failures.Add($ocr.Failure) }
            if ($keptBdpgsTrack -and -not $entry.IsSupplemental) {
                if ((& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
                    $keptBdpgsTrack.Disp = if ($entry.IsForced) { "default+forced" } else { "default" }
                    $defaultSet = $true
                } elseif (& $IsFallbackDefaultSub $entry) {
                    $fallbackDefaultCandidates.Add($keptBdpgsTrack)
                }
            }
            Write-Log "${Context}SUB: BDPGS OCR failed for stream $($s.index): $($ocr.Reason)" "WARN"
            continue
        }
        $tempFiles.Add($ocr.Path)

        $disp = "0"
        if (-not $entry.IsSupplemental -and (& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
            $disp = "default"; $defaultSet = $true
            $entry.IsDefault = $true
        } else {
            $entry.IsDefault = $false
        }
        if ($entry.IsForced) { $disp = if ($disp -eq "default") { "default+forced" } else { "forced" } }

        $track = @{
            MapArg  = $null
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $ocr.Path
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
        if (-not $entry.IsSupplemental -and $disp -eq "0" -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($track)
        }
        $bdpgsTracks.Add(@{
            SrtPath    = $ocr.Path
            StreamInfo = $entry
            CueCount   = $ocr.CueCount
            OriginalPreserved = ($null -ne $keptBdpgsTrack)
            OriginalPreserveReason = $bdpgsPreserveReason
        })
    }

    foreach ($entry in $FilterResult.Keep) {
        $s    = $entry.Stream
        if ($entry.IsTx3g -and -not $canPreserveTx3g) {
            $reason = "$((Get-ConfiguredOutputContainerName).ToUpperInvariant()) output cannot preserve TX3G stream $($s.index); enable ConvertTx3gToSrt for SRT conversion."
            $failures.Add((New-Tx3gFailureRecord -Entry $entry -Reason $reason -ErrorCode 'SUBTITLE_TX3G_CONTAINER_UNSUPPORTED'))
            Write-Log "${Context}SUBTITLE FAILURE: $reason" "ERROR"
            continue
        }
        if ($entry.IsBdpgs -and -not $canPreserveBdpgs) {
            $reason = "$((Get-ConfiguredOutputContainerName).ToUpperInvariant()) output cannot preserve BDPGS stream $($s.index); enable ConvertBdpgsToSrt for OCR conversion."
            $failures.Add((New-BdpgsFailureRecord -Entry $entry -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_CONTAINER_UNSUPPORTED'))
            Write-Log "${Context}SUBTITLE FAILURE: $reason" "ERROR"
            continue
        }
        $disp = "0"
        if (-not $entry.IsSupplemental -and (& $IsPreferredDefaultSub $entry) -and -not $defaultSet) {
            $disp = "default"; $defaultSet = $true
        }
        if ($entry.IsForced) { $disp = if ($disp -eq "default") { "default+forced" } else { "forced" } }
        $track = @{
            MapArg  = "0:$($s.index)"
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $null
            Codec   = "copy"
        }
        $allTracks.Add($track)
        if (-not $entry.IsSupplemental -and $disp -eq "0" -and (& $IsFallbackDefaultSub $entry)) {
            $fallbackDefaultCandidates.Add($track)
        }
    }

    if (-not $defaultSet -and $fallbackDefaultCandidates.Count -gt 0) {
        $fallback = $fallbackDefaultCandidates[0]
        $fallback.Disp = if ([string]$fallback.Disp -eq "forced") { "default+forced" } else { "default" }
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
        TempFiles   = @($tempFiles)
        Tx3gTracks  = @($tx3gTracks)
        BdpgsTracks = @($bdpgsTracks)
        Failures    = @($failures)
        TrackCount  = $allTracks.Count
    }
}
