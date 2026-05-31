# ==============================================================================
# engine\subtitles\builders.ps1
# ==============================================================================
# Subtitle mux/encode argument builders for mkvmerge and FFmpeg.
# Dot-sourced by engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

$subtitleBuilderDecisionModulePath = Join-Path $PSScriptRoot 'builders\decisions.ps1'
if (-not (Test-Path -LiteralPath $subtitleBuilderDecisionModulePath -PathType Leaf)) {
    throw "Required subtitle builder helper not found: $subtitleBuilderDecisionModulePath"
}
. $subtitleBuilderDecisionModulePath

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
        $tx3gTracks.Add(@{
            SrtPath    = $extract.Path
            StreamInfo = $entry
            CueCount   = $extract.CueCount
            OriginalPreserved = $false
            OriginalPreserveReason = $decision.OriginalPreserveReason
        })
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
        $bdpgsTracks.Add(@{
            SrtPath    = $ocr.Path
            StreamInfo = $entry
            CueCount   = $ocr.CueCount
            OriginalPreserved = ($null -ne $keptBdpgsTrack)
            OriginalPreserveReason = $decision.OriginalPreserveReason
        })
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
        $vobSubTracks.Add(@{
            SrtPath    = $ocr.Path
            StreamInfo = $entry
            CueCount   = $ocr.CueCount
            OriginalPreserved = ($null -ne $keptVobSubTrack)
            OriginalPreserveReason = $decision.OriginalPreserveReason
        })
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

function Build-SubtitleArgsForFFmpeg {
    param($FilterResult, [string]$DefaultAudioLang, [string]$SourceFile, [string]$Context = "")

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

        $track = @{
            MapArg  = $null       # assigned below when SRT inputs are numbered
            Title   = $entry.Title
            Lang    = $entry.Lang
            Disp    = $disp
            SrtPath = $srtPath
            Codec   = $convertedSrtCodec
        }
        $allTracks.Add($track)
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
        $tx3gTracks.Add(@{
            SrtPath    = $extract.Path
            StreamInfo = $entry
            CueCount   = $extract.CueCount
            OriginalPreserved = ($null -ne $keptTx3gTrack)
            OriginalPreserveReason = $decision.OriginalPreserveReason
        })
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
        $bdpgsTracks.Add(@{
            SrtPath    = $ocr.Path
            StreamInfo = $entry
            CueCount   = $ocr.CueCount
            OriginalPreserved = ($null -ne $keptBdpgsTrack)
            OriginalPreserveReason = $decision.OriginalPreserveReason
        })
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
        $vobSubTracks.Add(@{
            SrtPath    = $ocr.Path
            StreamInfo = $entry
            CueCount   = $ocr.CueCount
            OriginalPreserved = ($null -ne $keptVobSubTrack)
            OriginalPreserveReason = $decision.OriginalPreserveReason
        })
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
        VobSubTracks = @($vobSubTracks)
        Failures    = @($failures)
        TrackCount  = $allTracks.Count
    }
}
