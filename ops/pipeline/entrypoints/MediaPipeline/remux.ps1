# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline.ps1.
# Remux route implementation and command construction.

# ==============================================================================
# REMUX
# ==============================================================================

function Do-Remux {
    param($file, [bool]$isTV, $tvInfo)
    $safeName   = Get-SafeLocalName $file.Name
    $localIn    = $null
    $paths      = $null
    $tempAvFile = $null
    $subTracks  = $null
    # FIX#10: track successful server push. The finally block below only
    # deletes the local encoded output when $pushOk -eq $true, so a
    # network failure preserves the completed mkvmerge output in
    # PendingServerPush for the next run to retry.
    $pushOk     = $false
    $script:LastPublishResult = $null
    $script:CurrentSizePolicyResult = $null

    try {
        Set-ProgressStage -Stage 'copy_to_scratch' -Status $script:pipelineStatus -Route 'remux' -CopyState 'starting' -Percent $null -SaveNow
        $localIn = Ensure-ScratchCopy $file $safeName
        if (-not $localIn) { return $false }

        $paths = Get-OutputPaths $file $isTV $tvInfo $safeName
        if (Test-Path -LiteralPath $paths.ServerOut) {
            if (-not (Test-OutputNeedsReprocess -OutputPath $paths.ServerOut -SourceFile $file)) {
                if (-not (Invoke-Tx3gSidecarExportForExistingOutput -SourceFile $file -ScratchPath $localIn -MediaOutputPath $paths.ServerOut -Context "REMUX: ")) {
                    $localIn = $null
                    return $false
                }
                Write-Log "SKIP REMUX (exists on server): $(Split-Path $paths.ServerOut -Leaf)"
                Clear-SourceFailureState $file
                return $true
            }
            Write-Log "REMUX: reprocess mode - existing output will remain in place until the replacement is verified" "WARN"
        }
        if (-not (Test-DiskSpace $LocalBase -MinGB $MinFreeSpaceGB -Label "LOCAL")) { return $false }

        # R1 fix — remux peak scratch usage is ~2.5x source (input copy +
        # temp_av MKV + final MKV).  The headroom check above only checks
        # absolute MinFreeSpaceGB; without a source-scaled check, a 50 GB
        # UHD source on a 50 GB-free volume passes and then mkvmerge
        # exhausts the disk at 90% complete.
        if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "REMUX" -RemuxTwoStage)) {
            return $false
        }

        # R7 fix — Resolve-InitialMediaRoutePlan already populated
        # $script:CurrentRoutePlan.SourceCodec from the source-side ffprobe
        # in Get-SourceMediaRouteProfile.  Re-running ffprobe on the local
        # scratch copy here is redundant and adds 1-30s on slow disks.
        # Fall through to a probe only if the route plan didn't set the
        # codec (legacy / probe-failure path).
        $srcCodec = ''
        if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['SourceCodec']) {
            $srcCodec = [string]$script:CurrentRoutePlan.SourceCodec
        }
        if ([string]::IsNullOrWhiteSpace($srcCodec) -or $srcCodec -eq 'unknown') {
            $srcCodec = Get-SourceVideoCodec $localIn
        }
        $codecRoutePlan = Resolve-RemuxCodecRoutePlan -SourceCodec $srcCodec -RemuxSafeVideoCodecs $RemuxSafeVideoCodecs -BasePlan $script:CurrentRoutePlan
        $script:CurrentRoutePlan = $codecRoutePlan
        $script:CurrentRouteReasonCode = [string]$codecRoutePlan.ReasonCode
        $script:CurrentRouteReason = [string]$codecRoutePlan.Reason
        if ($codecRoutePlan.Route -eq 'encode') {
            Write-Log "REMUX: $($codecRoutePlan.Reason)"
            # R7 fix — leave the scratch copy in place. Do-Encode calls
            # Ensure-ScratchCopy which is idempotent: it verifies the
            # fingerprint and integrity of the existing file and reuses
            # it (ops\pipeline\engine\storage\scratch_copy.ps1 — see the "Fingerprint matched and integrity
            # passed - reuse." branch in Ensure-ScratchCopy). Deleting it
            # here forced a second multi-GB copy from the network share
            # for every codec-fallback file.
            #
            # Suppress the local cleanup in our finally block so the
            # scratch survives the return into Do-Encode.
            $localIn = $null
            return Do-Encode $file $isTV $tvInfo
        }

        Set-ProgressStage -Stage 'remux_prepare' -Status $script:pipelineStatus -Route 'remux' -CopyState 'complete' -Percent 0 -SaveNow
        try {
            $audioArgs = Build-AudioArgs $localIn
        } catch {
            $reason = [string]$_.Exception.Message
            $errorCode = if ($reason -match 'SOURCE_MEDIA_AUDIO_MISSING') { 'SOURCE_MEDIA_AUDIO_MISSING' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_INVALID') { 'SOURCE_MEDIA_AUDIO_INVALID' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') { 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED' } else { 'AUDIO_ARGUMENT_BUILD_FAILED' }
            $classification = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') { 'permanent' } else { 'transient' }
            $suggestedAction = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') {
                'Replace the source with a media file that contains at least one audio stream, or add an explicit no-audio workflow before retrying.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_INVALID') {
                'Inspect ffprobe audio stream metadata and confirm the source file is complete; retry after replacing or repairing the source.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') {
                'Inspect ffprobe audio stream JSON and confirm the source is fully copied/unlocked; retry after repairing or replacing the source.'
            } else {
                'Inspect ffprobe audio output and the pipeline log; retry after correcting the source or tool failure.'
            }
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification $classification -Reason $reason -Stage 'audio-probe' -ErrorCode $errorCode -SuggestedAction $suggestedAction | Out-Null
            $localIn = $null
            return $false
        }
        # R6 fix — only the AV stage needs the source to be readable. We
        # do a quick subtitle-presence probe here (cheap), then run the
        # AV stage, and ONLY THEN run the expensive subtitle conversion
        # (TX3G->SRT, BDPGS OCR, ASS->SRT). Previously the OCR ran first
        # and was wasted whenever the AV stage exited corrupt.
        $defaultAudioLang = Get-DefaultAudioLang $localIn
        $subFilter        = Filter-SubtitleStreams $localIn "REMUX: " -OriginalSourcePath $file.FullName
        if ($subFilter.ProbeFailed) {
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently remux with unknown subtitle state.' | Out-Null
            $localIn = $null
            return $false
        }

        $tempAvFile = Join-Path $script:processingDir "temp_av_$([guid]::NewGuid().ToString('N')).mkv"
        # R4 fix — switch from "-map 0:v:0" (first video stream only) to
        # "-map 0:V" (all real video streams, excluding attached pictures
        # like cover art). Multi-angle Blu-ray and PiP commentary sources
        # used to lose alternate streams silently on remux while encode
        # would have kept them.
        # R3 fix — add "-map 0:t?" so embedded attachments (typeset fonts
        # for anime ASS rendering, cover art, etc.) survive the AV stage
        # into temp_av and through the final mkvmerge step. Encoded
        # outputs already preserved attachments; remuxed outputs did not.
        # R12 fix — switch "-map_metadata -1" to "-map_metadata 0" so
        # source provenance (encoder string, creation_time, custom user
        # tags) survives. mkvmerge's --title still overrides the title
        # field downstream.
        $videoArgs = [System.Collections.Generic.List[string]]::new()
        $videoArgs.AddRange([string[]]@(
            "-i", $localIn,
            "-map", "0:V", "-c:v", "copy"
        ))
        if ($srcCodec -in (Get-MediaVideoCodecHevcNames)) {
            # FFmpeg can reject HEVC stream-copy back into Matroska unless the
            # bitstream is normalized to Annex B. Apply to ALL HEVC video
            # output streams (the broader -map 0:V may produce more than
            # one) by using -bsf:v without an output-stream specifier.
            $videoArgs.AddRange([string[]]@("-bsf:v", "hevc_mp4toannexb"))
            Write-Log "REMUX: applying HEVC bitstream filter for Matroska stream-copy compatibility" "DEBUG"
        }

        # CPU-A6 — when audio transcode is active in the AV stage, cap
        # ffmpeg's libav thread budget too. -threads on a stream-copy-only
        # AV is harmless; on a transcode-active AV it prevents the audio
        # encoder from saturating cores.
        $threadCapArgs = @()
        if ([bool]$script:LastAudioTranscodeActive -and [int]$script:CpuEncodeMaxThreads -gt 0) {
            $threadCapArgs = @('-threads', [string]$script:CpuEncodeMaxThreads)
        }
        $ffAvArgs = @($videoArgs.ToArray()) + @(
            "-map", "0:t?",
            "-map_chapters", "0",
            "-map_metadata", "0"
        ) + $threadCapArgs + $audioArgs + @("-y", $tempAvFile)

        # CPU-A3 — when audio transcode is active the AV stage is no
        # longer pure stream-copy I/O — it's running an audio encoder
        # at full priority. Lower priority + acquire the machine-wide
        # CPU mutex (shared with libx265 fallback) so two concurrent
        # transcode-active remuxes can't both saturate the CPU.
        $remuxAvCpuLock = $null
        $remuxAvCpuEncode = [bool]$script:LastAudioTranscodeActive
        if ($remuxAvCpuEncode) {
            Write-Log "REMUX-AV: audio transcode active (priority $script:CpuEncodeProcessPriority, threads $(if ($script:CpuEncodeMaxThreads -gt 0) { $script:CpuEncodeMaxThreads } else { 'auto' }))" "DEBUG"
            $remuxAvCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
            if (-not $remuxAvCpuLock.Acquired) {
                Write-Log "REMUX-AV: another CPU-bound job is already in progress on this machine; waiting for it ($($remuxAvCpuLock.Reason))" "WARN"
                Set-ProgressStage -Stage 'remux_av' -Status "Waiting for CPU slot (audio transcode)" -Route 'remux' -Percent 0 -SaveNow
                $remuxAvCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds $script:FFmpegRemuxTimeoutSeconds
            }
        }
        try {
            $remuxAvCallArgs = @{
                FFArgs          = $ffAvArgs
                Label           = 'REMUX-AV'
                InputFile       = $localIn
                TimeoutSeconds  = $script:FFmpegRemuxTimeoutSeconds
                ProgressStage   = 'remux_av'
                ProgressRoute   = 'remux'
                ReproStage      = 'remux-av'
            }
            if ($remuxAvCpuEncode) {
                $remuxAvCallArgs['CpuEncode']       = $true
                $remuxAvCallArgs['ProcessPriority'] = $script:CpuEncodeProcessPriority
            }
            $remuxAvSuccess = Invoke-FFmpegWithProgress @remuxAvCallArgs
        } finally {
            if ($remuxAvCpuLock -and $remuxAvCpuLock.Acquired) { & $remuxAvCpuLock.Release }
        }
        if (-not $remuxAvSuccess) {
            $reproPath = $script:LastFFmpegReproPath
            $ffmpegErrorSummary = Get-ErrorTextSummary -ErrorText $script:LastFFmpegStderr
            $errorCode = Get-FFmpegFailureCode -Stage 'remux-av' -ErrorText $script:LastFFmpegStderr -ExitCode ([int]$script:LastFFmpegExit)
            $reason = if ($ffmpegErrorSummary) { "FFmpeg remux AV stage failed: $ffmpegErrorSummary" } else { 'FFmpeg remux AV stage failed' }
            $suggestedAction = if ($errorCode -eq 'REMUX_HEVC_MKV_BITSTREAM_FAILED') {
                "This looks like an HEVC stream-copy to Matroska header failure. Retry with the updated pipeline so the primary video stream is mapped explicitly and hevc_mp4toannexb is applied."
            } elseif ($errorCode -eq 'REMUX_ATTACHED_PICTURE_MAPPED') {
                "This looks like attached cover art was mapped as video. Retry with the updated pipeline so only the primary video stream is selected."
            } else {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath, then retry once the source/share issue is fixed."
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'remux-av' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
            $localIn = $null
            return $false
        }

        # R6 fix — AV stage succeeded, source is known good. NOW run the
        # expensive subtitle conversion (BDPGS OCR can take many minutes
        # per language). Doing this earlier wasted that work whenever
        # the AV stage exited corrupt.
        $subTracks = Build-SubtitleTracksForMkvmerge $subFilter $defaultAudioLang $localIn "REMUX: "
        if ($subTracks.Failures -and @($subTracks.Failures).Count -gt 0) {
            Register-SubtitleExtractionFailure -SourceFile $file -ScratchPath $localIn -Failures @($subTracks.Failures) -Stage 'subtitle-extract'
            $localIn = $null
            return $false
        }

        [System.IO.Directory]::CreateDirectory($paths.LocalDir) | Out-Null
        [System.IO.Directory]::CreateDirectory($paths.ServerDir) | Out-Null

        # R10 fix — temp_av is now on disk and still ~1.0x source.
        # mkvmerge is about to write the third copy. Re-check before we
        # start, so we fail fast instead of half-way through a 50 GB mux.
        if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "REMUX-MUX" -RemuxFinalStage)) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'Insufficient scratch space for mkvmerge final mux' -Stage 'remux-mkvmerge' -ErrorCode 'REMUX_INSUFFICIENT_SPACE' -SuggestedAction 'Free space on the scratch volume or move LocalBase to a larger disk before retrying. The temp_av file is still consuming source-equivalent space and mkvmerge needs room for the final output.'
            return $false
        }

        $mkvArgs = [System.Collections.Generic.List[string]]::new()
        # FIX: removed --no-chapters so chapter data from tempAvFile is retained
        # R8 fix — Remux is content-preserving, so keep the source's title
        # tag when it has one (movie name, episode title, etc.). Only
        # stamp the generic "Encoded by MediaPipeline ..." title when the
        # source had no title.  Plex / Jellyfin fall back to this tag
        # when filename parsing is ambiguous.
        $sourceTitle = Get-SourceTitleTag -FilePath $localIn
        $effectiveTitle = if (-not [string]::IsNullOrWhiteSpace($sourceTitle)) {
            Write-Log "REMUX: preserving source title '$sourceTitle'" "DEBUG"
            $sourceTitle
        } else {
            "Encoded by MediaPipeline $($script:ProductVersion) (pipeline $($script:PipelineVersion))"
        }
        $mkvArgs.AddRange([string[]]@(
            "--output", $paths.LocalOut,
            "--title",  $effectiveTitle
        ))
        # R9 fix — emit explicit per-audio default-track flags. mkvmerge
        # needs absolute numeric TIDs (the global ID space across video,
        # audio, and subtitle tracks) — not audio-ordinal "aN". Probe
        # temp_av to translate Build-AudioArgs's audio ordinals to
        # mkvmerge TIDs. Without this, mkvmerge falls back to whatever
        # disposition ffmpeg stamped on the temp_av streams; in cross-
        # version cases that can leave more than one audio default.
        # mkvmerge `--default-track` flags must precede their input file.
        $audioTids = @(Get-MkvmergeAudioTids -FilePath $tempAvFile -Context "REMUX: ")
        if ($script:LastAudioTrackCount -gt 0 -and $audioTids.Count -ge $script:LastAudioTrackCount) {
            for ($aIdx = 0; $aIdx -lt $script:LastAudioTrackCount; $aIdx++) {
                $tid = [int]$audioTids[$aIdx]
                $isDefault = if ($aIdx -eq $script:LastAudioDefaultIndex) { 'yes' } else { 'no' }
                $mkvArgs.AddRange([string[]]@("--default-track", "$($tid):$isDefault"))
            }
        } elseif ($script:LastAudioTrackCount -gt 0) {
            Write-Log "REMUX: probed $($audioTids.Count) audio TIDs in temp_av but expected $($script:LastAudioTrackCount); skipping explicit default-track flags" "WARN"
        }
        $mkvArgs.Add($tempAvFile)
        if ($subTracks.SourceTracks.Count -gt 0) {
            foreach ($track in $subTracks.SourceTracks) {
                $mkvArgs.AddRange([string[]]@(
                    "--language",      "$($track.MkvTid):$($track.Lang)",
                    "--track-name",    "$($track.MkvTid):$($track.Title)",
                    "--default-track", "$($track.MkvTid):$(if ($track.IsDefault) { 'yes' } else { 'no' })"
                ))
                if ($track.IsForced) {
                    $mkvArgs.AddRange([string[]]@("--forced-track", "$($track.MkvTid):yes"))
                }
            }
            $mkvArgs.AddRange([string[]]@("--no-video","--no-audio","--subtitle-tracks",
                (($subTracks.SourceTracks | ForEach-Object { $_.MkvTid }) -join ","),$localIn))
        }
        foreach ($srt in $subTracks.ExternalTracks) {
            if (-not $srt.SrtPath) { continue }
            $mkvArgs.AddRange([string[]]@("--language","0:$($srt.Lang)","--track-name","0:$($srt.Title)",
                "--default-track","0:$(if ($srt.IsDefault) { 'yes' } else { 'no' })"))
            if ($srt.IsForced) { $mkvArgs.AddRange([string[]]@("--forced-track","0:yes")) }
            $mkvArgs.Add($srt.SrtPath)
        }

        Set-ProgressStage -Stage 'remux_mux' -Status $script:pipelineStatus -Route 'remux' -Percent 0 -SaveNow
        # R2 + R5 — use the configurable MkvmergeRemuxTimeoutSeconds (default
        # 7200 s, was a hard-coded 600 s) and the new --gui-mode-aware
        # progress wrapper so the GUI gets per-percent updates instead of
        # a frozen "remux mux" tile during multi-minute muxes.
        $mkv = Invoke-MkvmergeWithProgress -ArgumentList @($mkvArgs) -Label 'REMUX-MUX' -TimeoutSeconds $script:MkvmergeRemuxTimeoutSeconds -Stage 'remux-mkvmerge' -ProgressStage 'remux_mux' -ProgressRoute 'remux' -SaveReproOnFailure
        $mkvExitCode = [int]$mkv.ExitCode
        $mkvFailed = ([bool]$mkv.TimedOut -or [bool]$mkv.Stopped -or $mkvExitCode -lt 0 -or $mkvExitCode -ge 2)
        if ($mkvFailed) {
            $reproPath = $mkv.ReproPath
            $mkvLog = $null
            $mkvErrorSummary = Get-ErrorTextSummary -ErrorText $mkv.Error
            $errorCode = Get-MkvmergeFailureCode -ErrorText $mkv.Error -ExitCode $mkvExitCode -TimedOut ([bool]$mkv.TimedOut) -Stopped ([bool]$mkv.Stopped)
            $reason = if ([bool]$mkv.TimedOut) {
                if ($mkvErrorSummary) { "mkvmerge timed out after $($script:MkvmergeRemuxTimeoutSeconds)s: $mkvErrorSummary" } else { "mkvmerge timed out after $($script:MkvmergeRemuxTimeoutSeconds)s" }
            } elseif ([bool]$mkv.Stopped) {
                if ($mkvErrorSummary) { "mkvmerge stopped by operator request: $mkvErrorSummary" } else { "mkvmerge stopped by operator request" }
            } elseif ($mkvErrorSummary) {
                "mkvmerge failed with exit ${mkvExitCode}: $mkvErrorSummary"
            } else {
                "mkvmerge failed with exit ${mkvExitCode}"
            }
            Write-Log "mkvmerge failed (exit $mkvExitCode, code $errorCode)" "ERROR"
            if ($mkv.Error) {
                $mkvLog = Join-Path $LocalFailed "mkvmerge_error_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
                try { $mkv.Error | Out-File -LiteralPath $mkvLog -Force } catch {}
                Write-Log "mkvmerge error log: $mkvLog" "ERROR"
                $mkv.Error -split '\r?\n' | Where-Object { $_ -match '\S' } |
                    Select-Object -Last 8 | ForEach-Object { Write-Log "  mkvmerge: $_" "ERROR" }
            }
            $suggestedAction = switch ($errorCode) {
                'MKVMERGE_TIMEOUT' { "mkvmerge exceeded MkvmergeRemuxTimeoutSeconds=$($script:MkvmergeRemuxTimeoutSeconds). Inspect scratch/output disk speed and the saved repro command $reproPath, then retry or raise the timeout if the mux is legitimately slow."; break }
                'MKVMERGE_STOPPED' { "mkvmerge was stopped by operator request. Confirm the pipeline is idle and retry the source if the stop was intentional."; break }
                default {
                    if ($mkvLog) {
                        "Inspect mkvmerge stderr log $mkvLog and repro command $reproPath, then retry after fixing the subtitle/container issue."
                    } else {
                        "Inspect the saved mkvmerge repro command $reproPath, then retry after fixing the subtitle/container issue."
                    }
                }
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'remux-mkvmerge' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
            $localIn = $null
            return $false
        }
        if ($mkvExitCode -eq 1) {
            Write-Log "mkvmerge completed with warnings" "WARN"
            # mkvmerge writes warning text to stdout (Output). Surface the tail
            # so a dropped/unsupported track is visible instead of a bare
            # "completed with warnings" line that is easy to miss in the log.
            $mkvWarnText = if (-not [string]::IsNullOrWhiteSpace([string]$mkv.Output)) { [string]$mkv.Output } else { [string]$mkv.Error }
            if ($mkvWarnText) {
                $mkvWarnText -split '\r?\n' | Where-Object { $_ -match '\S' } |
                    Select-Object -Last 8 | ForEach-Object { Write-Log "  mkvmerge: $_" "WARN" }
            }
        }

        if (-not (Test-Path -LiteralPath $paths.LocalOut) -or
            (Get-Item -LiteralPath $paths.LocalOut).Length -eq 0) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'REMUX output missing or empty after mkvmerge' -Stage 'remux-mkvmerge'
            $localIn = $null
            Write-Log "REMUX: output missing or empty after mkvmerge" "ERROR"; return $false
        }

        # Duration sanity check — catches silent truncations while tolerating
        # subtitle-tail container-duration differences on remuxed outputs.
        Set-ProgressStage -Stage 'remux_verify' -Status $script:pipelineStatus -Route 'remux' -Percent $null -SaveNow
        if (-not (Test-DurationMatch -SourcePath $localIn -OutputPath $paths.LocalOut -Label "REMUX" -AllowAVFallback)) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $paths.LocalOut -Classification 'transient' -Reason 'REMUX duration mismatch' -Stage 'remux-verify' -SuggestedAction 'Compare source and remuxed output A/V end times. Subtitle-tail container differences are tolerated now, so a remaining remux-verify failure usually indicates the output A/V is actually short.'
            Write-Log "REMUX: output duration mismatch - treating as failure" "ERROR"
            return $false
        }

        Write-PlexCompatibilityReport -FilePath $paths.LocalOut -Context "REMUX: "

        $publishResult = Complete-PipelineOutputPublish -SourceFile $file -ScratchPath $localIn -Paths $paths -Route 'remux' -ProgressRoute 'remux' -StagePrefix 'remux' -Context "REMUX: " -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -Tx3gTracks @($subTracks.Tx3gTracks) -BdpgsTracks @($subTracks.BdpgsTracks) -VobSubTracks @($subTracks.VobSubTracks)
        $script:LastPublishResult = $publishResult
        if ($publishResult.DeleteLocalOutput) { $pushOk = $true }
        if ($publishResult.KeepScratchInput) { $localIn = $null }
        return [bool]$publishResult.Ok

    } catch {
        Write-Log "Do-Remux unexpected error: $_" "ERROR"
        Write-Log "Stack: $($_.ScriptStackTrace)" "DEBUG"
        if ($file) {
            $reason = "Do-Remux unexpected error: $($_.Exception.Message)"
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'remux-exception' -ErrorCode 'REMUX_UNEXPECTED_EXCEPTION' -SuggestedAction 'Inspect the pipeline log stack trace and failure artifact, then clear the marker after fixing the root cause.' | Out-Null
            $localIn = $null
        }
        return $false
    } finally {
        if ($tempAvFile)  { Remove-Item -LiteralPath $tempAvFile -Force -ErrorAction SilentlyContinue }
        if ($localIn)     {
            Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
            Remove-ScratchFingerprint $localIn
            Remove-EmptyScratchContainer $localIn
        }
        # FIX#10: ONLY delete the local output when the server push
        # succeeded. On failure the output is already parked in
        # PendingServerPush by Invoke-ParkPendingPush.
        if ($pushOk -and $paths -and $paths.LocalOut -and
            (Test-Path -LiteralPath $paths.LocalOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $paths.LocalOut -Force -ErrorAction SilentlyContinue
        }
        if ($subTracks -and $subTracks.TempFiles) {
            $subTracks.TempFiles | ForEach-Object { Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue }
        }
    }
}
