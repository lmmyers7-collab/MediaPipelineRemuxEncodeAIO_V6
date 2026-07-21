# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux FFmpeg AV temp stage.

function Get-MediaPipelineRemuxStreamProperty {
    param(
        $Stream,
        [Parameter(Mandatory)] [string[]] $Names,
        $Default = $null
    )

    if ($null -eq $Stream) { return $Default }
    foreach ($name in $Names) {
        try {
            $prop = $Stream.PSObject.Properties[$name]
            if ($prop) { return $prop.Value }
        } catch {}
    }
    return $Default
}

function ConvertTo-MediaPipelineRemuxStreamBool {
    param($Value)

    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return [bool]$Value }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    return ($text -in @('1', 'true', 'yes'))
}

function Get-MediaPipelineRemuxInventoryVideoStreams {
    param([Parameter(Mandatory)] $Context)

    $inventory = $null
    if ($Context.VideoStreamPolicy -and $Context.VideoStreamPolicy.PSObject.Properties['Inventory']) {
        $inventory = $Context.VideoStreamPolicy.Inventory
    }
    if (-not $inventory) { return @() }

    $realStreams = @()
    $attachedStreams = @()
    if ($inventory.PSObject.Properties['RealVideoStreams']) {
        $realStreams = @($inventory.RealVideoStreams | Where-Object { $null -ne $_ })
    }
    if ($inventory.PSObject.Properties['AttachedPicStreams']) {
        $attachedStreams = @($inventory.AttachedPicStreams | Where-Object { $null -ne $_ })
    }
    if ($realStreams.Count -le 0) { return @() }

    $allStreams = @($realStreams) + @($attachedStreams)
    return @(
        $allStreams |
            Sort-Object {
                [int](Get-MediaPipelineRemuxStreamProperty -Stream $_ -Names @('Index', 'index') -Default 2147483647)
            }
    )
}

function New-MediaPipelineRemuxVideoArgumentList {
    param([Parameter(Mandatory)] $Context)

    $args = [System.Collections.Generic.List[string]]::new()
    $args.AddRange([string[]]@(
        "-fflags", "+genpts",
        "-i", $Context.LocalIn
    ))

    $hevcNames = @(Get-MediaVideoCodecHevcNames | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() })
    $videoStreams = @(Get-MediaPipelineRemuxInventoryVideoStreams -Context $Context)
    if ($videoStreams.Count -gt 0) {
        $hevcOutputOrdinals = [System.Collections.Generic.List[int]]::new()
        $outputOrdinal = 0
        foreach ($stream in $videoStreams) {
            $streamIndex = [int](Get-MediaPipelineRemuxStreamProperty -Stream $stream -Names @('Index', 'index') -Default -1)
            if ($streamIndex -lt 0) { continue }
            $args.AddRange([string[]]@("-map", "0:$streamIndex"))

            $attachedPicture = ConvertTo-MediaPipelineRemuxStreamBool -Value (Get-MediaPipelineRemuxStreamProperty -Stream $stream -Names @('AttachedPicture', 'attached_picture') -Default $false)
            $codec = ([string](Get-MediaPipelineRemuxStreamProperty -Stream $stream -Names @('Codec', 'codec', 'codec_name') -Default '')).Trim().ToLowerInvariant()
            if (-not $attachedPicture -and $codec -in $hevcNames) {
                $hevcOutputOrdinals.Add([int]$outputOrdinal) | Out-Null
            }
            $outputOrdinal++
        }

        if ($outputOrdinal -gt 0) {
            $args.AddRange([string[]]@("-c:v", "copy"))
            foreach ($ordinal in @($hevcOutputOrdinals.ToArray())) {
                $args.AddRange([string[]]@("-bsf:v:$ordinal", "hevc_mp4toannexb"))
            }
            if ($hevcOutputOrdinals.Count -gt 0) {
                Write-Log "REMUX: applying HEVC bitstream filter to video output ordinal(s) $($hevcOutputOrdinals.ToArray() -join ',')" "DEBUG"
            }
            return @($args.ToArray())
        }
    }

    $args.AddRange([string[]]@("-map", "0:V", "-c:v", "copy"))
    if (([string]$Context.SourceCodec).Trim().ToLowerInvariant() -in $hevcNames) {
        $args.AddRange([string[]]@("-bsf:v:0", "hevc_mp4toannexb"))
        Write-Log "REMUX: applying HEVC bitstream filter to first video output stream without stream inventory" "DEBUG"
    }
    return @($args.ToArray())
}

function Invoke-MediaPipelineRemuxFfmpegAvStage {
    param([Parameter(Mandatory)] $Context)

    $Context.TempAvFile = Join-Path $script:processingDir "temp_av_$([guid]::NewGuid().ToString('N')).mkv"
    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorOutput -ErrorAction SilentlyContinue) {
        Set-MediaPipelineCurrentRunMonitorOutput -State active -ScratchPath ([string]$Context.LocalIn) -WorkingOutputPath ([string]$Context.TempAvFile) -IntendedFinalPath ([string]$Context.Paths.ServerOut) -VerificationState not_started | Out-Null
    }
    $videoArgs = New-MediaPipelineRemuxVideoArgumentList -Context $Context

    $threadCapArgs = @()
    if ([bool]$script:LastAudioTranscodeActive -and [int]$script:CpuEncodeMaxThreads -gt 0) {
        $threadCapArgs = @('-threads', [string]$script:CpuEncodeMaxThreads)
    }
    $ffAvArgs = @($videoArgs) + @(
        "-map", "0:t?",
        "-map_chapters", "0",
        "-map_metadata", "0"
    ) + $threadCapArgs + @($Context.AudioArgs) + @("-y", $Context.TempAvFile)

    $remuxAvCpuLock = $null
    $remuxAvCpuEncode = [bool]$script:LastAudioTranscodeActive
    if ($remuxAvCpuEncode) {
        Write-Log "REMUX-AV: audio transcode active (priority $script:CpuEncodeProcessPriority, threads $(if ($script:CpuEncodeMaxThreads -gt 0) { $script:CpuEncodeMaxThreads } else { 'auto' }))" "DEBUG"
        $remuxAvCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
        if (-not $remuxAvCpuLock.Acquired) {
            Write-Log "REMUX-AV: another CPU-bound job is already in progress on this machine; waiting for it ($($remuxAvCpuLock.Reason))" "WARN"
            Set-ProgressStage -Stage 'remux_av' -Status "Waiting for CPU slot (audio transcode)" -Route 'remux' -Percent 0 -SaveNow
            $remuxAvMutexPollHandler = if (Get-Command -Name New-MediaPipelineCurrentStageNativePollHandler -ErrorAction SilentlyContinue) {
                New-MediaPipelineCurrentStageNativePollHandler `
                    -Stage 'remux_av' `
                    -Status 'Waiting for CPU slot (audio transcode)' `
                    -Route 'remux' `
                    -MinimumIntervalSeconds 15 `
                    -RefreshActiveAudioTracks `
                    -EvidenceSource 'remux_audio_cpu_mutex_heartbeat'
            } else {
                $null
            }
            $remuxAvCpuLock = Acquire-CpuEncodeMutex `
                -TimeoutSeconds $script:FFmpegRemuxTimeoutSeconds `
                -PollHandler $remuxAvMutexPollHandler `
                -PollMilliseconds 1000
        }
    }
    try {
        $remuxAvCallArgs = @{
            FFArgs          = $ffAvArgs
            Label           = 'REMUX-AV'
            InputFile       = $Context.LocalIn
            TimeoutSeconds  = $script:FFmpegRemuxTimeoutSeconds
            ProgressStage   = 'remux_av'
            ProgressRoute   = 'remux'
            ReproStage      = 'remux-av'
            TrackAudioWork  = $true
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
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason $reason -Stage 'remux-av' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-av'
    }

    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-av'
}
