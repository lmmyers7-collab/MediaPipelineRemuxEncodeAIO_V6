# Dot-sourced by Pipeline/MediaPipeline.ps1.
# Encode route implementation and command construction.

# ==============================================================================
# ENCODE
# ==============================================================================
function Do-Encode {
    param($file, [bool]$isTV, $tvInfo)
    $safeName  = Get-SafeLocalName $file.Name
    $localIn   = $null
    $paths     = $null
    $tempOut   = $null
    $subResult = $null
    # FIX#10: same push-tracking flag pattern as Do-Remux.
    $pushOk    = $false
    $script:CurrentEncodeAttempts = @()
    $script:LastPublishResult = $null
    $script:CurrentSizePolicyResult = $null

    try {
        Set-ProgressStage -Stage 'copy_to_scratch' -Status $script:pipelineStatus -Route 'encode' -CopyState 'starting' -Percent $null -SaveNow
        $localIn = Ensure-ScratchCopy $file $safeName
        if (-not $localIn) { return $false }

        $paths = Get-OutputPaths $file $isTV $tvInfo $safeName
        if (Test-Path -LiteralPath $paths.ServerOut) {
            if (-not (Test-OutputNeedsReprocess -OutputPath $paths.ServerOut -SourceFile $file)) {
                if (-not (Invoke-Tx3gSidecarExportForExistingOutput -SourceFile $file -ScratchPath $localIn -MediaOutputPath $paths.ServerOut -Context "ENCODE: ")) {
                    $localIn = $null
                    return $false
                }
                Write-Log "SKIP ENCODE (exists on server): $(Split-Path $paths.ServerOut -Leaf)"
                Clear-SourceFailureState $file
                return $true
            }
            Write-Log "ENCODE: reprocess mode - existing output will remain in place until the replacement is verified" "WARN"
        }
        if (-not (Test-DiskSpace $LocalBase -MinGB $MinFreeSpaceGB -Label "LOCAL")) { return $false }

        # Pre-encode estimated output-size check. Fails fast if the scratch
        # drive can't hold the estimated output plus configured headroom,
        # instead of crashing mid-encode at 80%.
        if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "ENCODE")) {
            return $false
        }

        try {
            $hdrState = Get-HDRState $localIn
            if (-not [bool]$hdrState.Known) {
                throw "HDR_DETECTION_UNKNOWN: $($hdrState.Reason)"
            }
            $isHDR = [bool]$hdrState.IsHDR
        } catch {
            $reason = [string]$_.Exception.Message
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'hdr-detection' -ErrorCode 'HDR_DETECTION_UNKNOWN' -SuggestedAction 'Inspect ffprobe video stream metadata and confirm the source file is complete; retry after replacing or repairing the source.' | Out-Null
            $localIn = $null
            return $false
        }
        # Suggestion #1 — extract HDR10 mastering display + MaxCLL once per
        # file so any CPU-fallback x265 invocation can emit a complete
        # HDR10 SEI. Probe is best-effort: SDR sources / probes that fail
        # return Known=$false and we leave the metadata strings empty.
        $hdr10MasterDisplay = ''
        $hdr10MaxCll = ''
        if ($isHDR) {
            $hdr10Meta = Get-SourceHdr10MasteringMetadata -FilePath $localIn
            if ($hdr10Meta.Known) {
                if ($hdr10Meta.HasMasterDisplay) { $hdr10MasterDisplay = [string]$hdr10Meta.MasterDisplay }
                if ($hdr10Meta.HasMaxCll)        { $hdr10MaxCll        = [string]$hdr10Meta.MaxCll }
                Write-Log "ENCODE: HDR10 metadata found — master-display='$hdr10MasterDisplay' max-cll='$hdr10MaxCll'" "DEBUG"
            } else {
                Write-Log "ENCODE: HDR source but no HDR10 mastering metadata in side_data ($($hdr10Meta.Reason)); CPU-encoded HDR output will lack master-display/MaxCLL SEI" "WARN"
            }
        }
        $usingCpu    = $false
        $usingSafeRetry = $false
        $globalTitle = "Encoded by MediaPipeline $($script:ProductVersion) (pipeline $($script:PipelineVersion))"
        $recordEncodeAttempt = {
            param($Plan, [bool]$Succeeded)
            # D3 fix — record CPU-specific context per attempt so sidecar
            # consumers (analytics, diagnostics drawer) can correlate preset
            # / timeout / priority with success rate and elapsed time.
            # cpu_* fields are only meaningful for CPU attempts; GPU / safe
            # rows get empty/zero defaults so the schema stays uniform.
            $cpuPresetField = if ($Plan.PSObject.Properties['CpuPreset']) { [string]$Plan.CpuPreset } else { '' }
            $cpuTimeoutField = if ([bool]$Plan.UseCpuFallback) { [int]$script:FFmpegCpuEncodeTimeoutSeconds } else { 0 }
            $cpuPriorityField = if ([bool]$Plan.UseCpuFallback) { [string]$script:CpuEncodeProcessPriority } else { '' }
            $script:CurrentEncodeAttempts = @(@($script:CurrentEncodeAttempts) + ([ordered]@{
                attempt              = [string]$Plan.Attempt
                route                = [string]$Plan.Route
                label                = [string]$Plan.Label
                success              = [bool]$Succeeded
                used_cpu             = [bool]$Plan.UseCpuFallback
                safe_retry           = [bool]$Plan.UseSafeHardwareRetry
                repro_stage          = [string]$Plan.ReproStage
                encode_ladder        = [string]$Plan.EncodeLadder
                selected_encoder     = [string]$Plan.SelectedEncoder
                encoder_kind         = [string]$Plan.EncoderKind
                selected_gpu_device  = [string]$Plan.SelectedGpuDevice
                cpu_preset           = $cpuPresetField
                cpu_timeout_seconds  = $cpuTimeoutField
                cpu_process_priority = $cpuPriorityField
            }))
        }

        if ($isHDR) { Write-Log "ENCODE: HDR detected - Main10 / BT.2020" }
        else        { Write-Log "ENCODE: SDR - Main profile" }

        Set-ProgressStage -Stage 'encode_prepare' -Status $script:pipelineStatus -Route 'encode' -CopyState 'complete' -Percent 0 -SaveNow
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
        $defaultAudioLang = Get-DefaultAudioLang $localIn
        $subFilter        = Filter-SubtitleStreams $localIn "ENCODE: " -OriginalSourcePath $file.FullName
        if ($subFilter.ProbeFailed) {
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently encode with unknown subtitle state.' | Out-Null
            $localIn = $null
            return $false
        }
        $subResult        = Build-SubtitleArgsForFFmpeg $subFilter $defaultAudioLang $localIn "ENCODE: "
        if ($subResult.Failures -and @($subResult.Failures).Count -gt 0) {
            Register-SubtitleExtractionFailure -SourceFile $file -ScratchPath $localIn -Failures @($subResult.Failures) -Stage 'subtitle-extract'
            $localIn = $null
            return $false
        }

        # Attempt 1 uses the configured GPU-first encoder. Retry policy and
        # CPU fallback command construction live in engine\decide\encode_policy.ps1.
        # Suggestion #2 — when the cached NVENC probe says GPU is
        # unavailable (set by Invalidate-NvencAvailableProbe after an
        # earlier runtime NVENC failure), skip the primary AND safe-retry
        # attempts entirely. Saves ~10–60 s per file on a no-GPU machine.
        $skipGpuDueToProbe = -not (Test-NvencProbeReportsAvailable)
        if ($skipGpuDueToProbe) {
            $probeReason = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.Reason) { [string]$script:NvencAvailableProbe.Reason } else { 'NVENC probe cache reports unavailable' }
            Write-Log "ENCODE: NVENC unavailable per cached probe ($probeReason); skipping GPU-first ladder and going straight to CPU" "WARN"
            Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                from_encoder = 'cached_unavailable'
                to_encoder   = (Get-MediaVideoCodecLibx265Name)
                reason       = $probeReason
                trigger      = 'nvenc_probe_unavailable'
                cpu_preset   = [string]$script:CpuEncodePreset
                is_hdr       = [bool]$isHDR
            } | Out-Null
        }

        $tempOut    = Join-Path $script:processingDir "encode_temp_$([guid]::NewGuid().ToString('N')).$OutputContainer"
        $encodePlan = New-EncodeAttemptPlan `
            -UseCpuFallback:$false `
            -IsTV:$isTV `
            -IsHDR:$isHDR `
            -InputPath $localIn `
            -ExtraInputs $subResult.ExtraInputs `
            -GlobalTitle $globalTitle `
            -AudioArgs $audioArgs `
            -SubtitleMapArgs $subResult.MapArgs `
            -OutputPath $tempOut `
            -VideoCodec $VideoCodec `
            -VideoPreset $VideoPreset `
            -VideoQuality $VideoQuality `
            -ExtraVideoFlags $ExtraVideoFlags `
            -FallbackCpuQuality $script:FallbackCpuQuality `
            -EncodeLadder $script:EncodeLadder `
            -CpuPreset $script:CpuEncodePreset `
                -CpuMaxThreads $script:CpuEncodeMaxThreads `
                -Hdr10MasterDisplay $hdr10MasterDisplay `
                -Hdr10MaxCll $hdr10MaxCll
        $ffArgs     = @($encodePlan.ArgumentList)

        $nullCount = @($ffArgs | Where-Object { $null -eq $_ }).Count
        if ($nullCount -gt 0) {
            Write-Log "ENCODE: $nullCount null element(s) in FFmpeg args - aborting" "ERROR"
            return $false
        }

        if ($skipGpuDueToProbe) {
            # Don't burn an ffmpeg launch for the primary GPU attempt;
            # synthesize the failure state so the existing fallback
            # branch fires and falls into the CPU path below.
            $success = $false
            $script:LastFFmpegStderr = "NVENC probe cache reports unavailable; primary GPU attempt skipped"
            $script:LastFFmpegExit = 1
        } else {
            $success = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage
            & $recordEncodeAttempt $encodePlan ([bool]$success)
        }

        if (Test-ShouldRetryEncodeWithCpuFallback -Success:$success -StopRequested:$script:StopRequested -VideoCodec $VideoCodec -ErrorText $script:LastFFmpegStderr -ForceCpu:$skipGpuDueToProbe) {
            if (-not $skipGpuDueToProbe) {
                Write-Log "ENCODE: hardware encoder failure detected - retrying once with compatibility flags before CPU fallback" "WARN"
            }
            if (Test-Path -LiteralPath $tempOut) {
                Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
            }
            $tempOut    = Join-Path $script:processingDir "encode_temp_safe_$([guid]::NewGuid().ToString('N')).$OutputContainer"
            if (-not $skipGpuDueToProbe) {
                $encodePlan = New-EncodeAttemptPlan `
                    -UseCpuFallback:$false `
                    -UseSafeHardwareRetry:$true `
                    -IsTV:$isTV `
                    -IsHDR:$isHDR `
                    -InputPath $localIn `
                    -ExtraInputs $subResult.ExtraInputs `
                    -GlobalTitle $globalTitle `
                    -AudioArgs $audioArgs `
                    -SubtitleMapArgs $subResult.MapArgs `
                    -OutputPath $tempOut `
                    -VideoCodec $VideoCodec `
                    -VideoPreset $VideoPreset `
                    -VideoQuality $VideoQuality `
                    -ExtraVideoFlags $ExtraVideoFlags `
                    -FallbackCpuQuality $script:FallbackCpuQuality `
                    -EncodeLadder $script:EncodeLadder `
                    -CpuPreset $script:CpuEncodePreset `
                    -CpuMaxThreads $script:CpuEncodeMaxThreads `
                    -Hdr10MasterDisplay $hdr10MasterDisplay `
                    -Hdr10MaxCll $hdr10MaxCll
                $ffArgs     = @($encodePlan.ArgumentList)
                $success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage
                & $recordEncodeAttempt $encodePlan ([bool]$success)
            } else {
                # GPU is already known unavailable; don't even build the
                # safe-retry plan. Force the inner gate to fall straight
                # into the CPU branch.
                $success = $false
                $script:LastFFmpegStderr = "NVENC probe cache reports unavailable; safe-retry skipped"
                $script:LastFFmpegExit = 1
            }
            if ($success) {
                $usingSafeRetry = $true
                $script:CurrentRouteReasonCode = 'hardware_encoder_safe_retry_succeeded'
                $script:CurrentRouteReason = 'hardware encoder failed with primary flags; compatibility retry succeeded'
            } elseif (Test-ShouldRetryEncodeWithCpuFallback -Success:$success -StopRequested:$script:StopRequested -VideoCodec $VideoCodec -ErrorText $script:LastFFmpegStderr -ForceCpu:$skipGpuDueToProbe) {
                # Suggestion #2 — second NVENC failure in this file means
                # the GPU is genuinely sick (driver hang, eGPU disconnect,
                # VRAM exhausted, etc.). Invalidate the probe cache so
                # the NEXT file goes straight to CPU instead of repeating
                # primary + safe-retry just to fail twice more. Skip when
                # we already came in via $skipGpuDueToProbe.
                if (-not $skipGpuDueToProbe) {
                    $invalidateReason = if ($script:LastFFmpegStderr) {
                        $tail = ($script:LastFFmpegStderr -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
                        "GPU primary + safe-retry both failed: $tail"
                    } else {
                        'GPU primary + safe-retry both failed'
                    }
                    Invalidate-NvencAvailableProbe -Reason $invalidateReason -SourcePath $file.FullName
                }
                Write-Log "ENCODE: compatibility retry also failed - falling back to $(Get-MediaVideoCodecLibx265Name) (CRF $($script:FallbackCpuQuality), preset $script:CpuEncodePreset, timeout $($script:FFmpegCpuEncodeTimeoutSeconds)s, priority $script:CpuEncodeProcessPriority)" "WARN"
                # Emit a structured event so the desktop diagnostics drawer
                # and the Live tab can light up a CPU-fallback indicator
                # instead of the operator only seeing a log line.
                Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                    from_encoder         = [string]$VideoCodec
                    to_encoder           = (Get-MediaVideoCodecLibx265Name)
                    cpu_preset           = [string]$script:CpuEncodePreset
                    cpu_quality_crf      = [int]$script:FallbackCpuQuality
                    cpu_timeout_seconds  = [int]$script:FFmpegCpuEncodeTimeoutSeconds
                    cpu_process_priority = [string]$script:CpuEncodeProcessPriority
                    is_hdr               = [bool]$isHDR
                } | Out-Null
                if (Test-Path -LiteralPath $tempOut) {
                    Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
                }
                $tempOut    = Join-Path $script:processingDir "encode_temp_cpu_$([guid]::NewGuid().ToString('N')).$OutputContainer"
                # F-new-1 — re-validate scratch space with the CPU-aware
                # multiplier *before* the (potentially multi-hour) libx265
                # run. The original pre-flight at the top of Do-Encode used
                # the default 0.7x NVENC ratio, which can green-light an
                # encode that would actually fill the scratch volume at
                # 95% with libx265 output.
                if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "ENCODE-CPU" -IsCpuEncode)) {
                    Write-Log "ENCODE-CPU: insufficient scratch space for CPU-fallback encode — aborting before libx265 starts" "ERROR"
                    Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'Insufficient scratch space for CPU-fallback encode' -Stage 'encode' -ErrorCode 'ENCODE_CPU_INSUFFICIENT_SPACE' -SuggestedAction 'Free additional space on the scratch volume or lower CpuEncodePreset/FallbackCpuQuality before retrying. CPU encodes need 1:1 source-size headroom because libx265 output is typically larger than NVENC.' | Out-Null
                    $localIn = $null
                    return $false
                }
                $encodePlan = New-EncodeAttemptPlan `
                    -UseCpuFallback:$true `
                    -IsTV:$isTV `
                    -IsHDR:$isHDR `
                    -InputPath $localIn `
                    -ExtraInputs $subResult.ExtraInputs `
                    -GlobalTitle $globalTitle `
                    -AudioArgs $audioArgs `
                    -SubtitleMapArgs $subResult.MapArgs `
                    -OutputPath $tempOut `
                    -VideoCodec $VideoCodec `
                    -VideoPreset $VideoPreset `
                    -VideoQuality $VideoQuality `
                    -ExtraVideoFlags $ExtraVideoFlags `
                    -FallbackCpuQuality $script:FallbackCpuQuality `
                    -EncodeLadder $script:EncodeLadder `
                    -CpuPreset $script:CpuEncodePreset `
                -CpuMaxThreads $script:CpuEncodeMaxThreads `
                -Hdr10MasterDisplay $hdr10MasterDisplay `
                -Hdr10MaxCll $hdr10MaxCll
                $ffArgs     = @($encodePlan.ArgumentList)
                # Differentiate the GUI status string. app/status/service.py renders
                # `encode_cpu` with its own label, but the user-facing status
                # text (currentStatus) is also surfaced verbatim in the live
                # tile and the taskbar tooltip; keep it explicit so the
                # operator immediately knows this is a multi-hour CPU run.
                $cpuStatusText = if ($isTV) { "Encoding TV (CPU fallback)" } else { "Encoding Movie (CPU fallback)" }
                # F-new-4 — serialize CPU encodes machine-wide. If another
                # pipeline process on this box is already running libx265,
                # show the operator that we're queued behind it instead of
                # silently double-saturating the cores.
                $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
                if (-not $cpuMutexLock.Acquired) {
                    Write-Log "ENCODE-CPU: another CPU encode is already in progress on this machine; waiting for it to finish ($($cpuMutexLock.Reason))" "WARN"
                    Set-ProgressStage -Stage 'encode_cpu' -Status "Waiting for CPU encode slot" -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
                    $script:pipelineStatus = "Waiting for CPU encode slot"
                    # Wait up to the CPU encode timeout for the slot. Worst
                    # case the prior holder times out and releases.
                    $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds $script:FFmpegCpuEncodeTimeoutSeconds
                }
                Set-ProgressStage -Stage 'encode_cpu' -Status $cpuStatusText -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
                $script:pipelineStatus = $cpuStatusText
                try {
                    # CPU encodes get their own (typically larger) timeout
                    # so a slow libx265 run is not killed at the 6-hour
                    # GPU ceiling.
                    $success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegCpuEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage -CpuEncode -ProcessPriority $script:CpuEncodeProcessPriority
                } finally {
                    if ($cpuMutexLock -and $cpuMutexLock.Acquired) { & $cpuMutexLock.Release }
                }
                & $recordEncodeAttempt $encodePlan ([bool]$success)
                if ($success) {
                    $usingCpu = $true
                    # E1 fix — keep the script-scope route state in sync with
                    # the actual encoder used. The size-policy guard (and any
                    # other consumer that reads CurrentRouteReasonCode during
                    # verify) needs to see the correct reason so CPU outputs
                    # receive the compatibility growth budget, not the strict 5%.
                    # Suggestion #2 — distinguish "GPU known unavailable per
                    # cached probe" from "GPU was actually attempted and
                    # failed for this file".  Both still use the
                    # encode-cpu-fallback route, but the reason code lets
                    # diagnostics show why GPU was skipped.
                    if ($skipGpuDueToProbe) {
                        $script:CurrentRouteReasonCode = 'gpu_unavailable_cpu_only'
                        $script:CurrentRouteReason     = 'NVENC unavailable per cached probe; CPU encode without trying GPU'
                    } else {
                        $script:CurrentRouteReasonCode = 'hardware_encoder_cpu_fallback'
                        $script:CurrentRouteReason     = 'hardware encoder failed; CPU fallback succeeded'
                    }
                    # E3 fix — mutate route_actions.video to 'encode_software'
                    # immediately on CPU success.  If a later verify/size-guard
                    # step rejects this output, the failure sidecar still has
                    # the correct encoder kind instead of the stale planned
                    # 'encode_hardware' label.
                    if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['Actions']) {
                        $actions = $script:CurrentRoutePlan.Actions
                        if ($actions -is [System.Collections.IDictionary]) {
                            $actions['video'] = 'encode_software'
                        } else {
                            $videoProp = $actions.PSObject.Properties['video']
                            if ($videoProp) { $videoProp.Value = 'encode_software' }
                        }
                    }
                    # E5 paired event — operators correlating fallback start
                    # with completion get an explicit success record instead
                    # of inferring it from a later tool_completed.
                    Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'succeeded' -SourcePath $file.FullName -Data @{
                        from_encoder    = [string]$VideoCodec
                        to_encoder      = (Get-MediaVideoCodecLibx265Name)
                        cpu_preset      = [string]$encodePlan.CpuPreset
                        cpu_quality_crf = [int]$script:FallbackCpuQuality
                    } | Out-Null
                }
            }
        }

        if (-not $success) {
            $reproStage = if ($encodePlan -and $encodePlan.ReproStage) { [string]$encodePlan.ReproStage } elseif ($usingCpu) { 'encode-cpu' } else { 'encode' }
            $reproPath = $script:LastFFmpegReproPath
            $ffmpegErrorSummary = Get-ErrorTextSummary -ErrorText $script:LastFFmpegStderr
            $errorCode = Get-FFmpegFailureCode -Stage $reproStage -ErrorText $script:LastFFmpegStderr -ExitCode ([int]$script:LastFFmpegExit)
            # Encoder-aware reason / suggestion text. The previous text always
            # blamed NVENC even when the failed attempt was the CPU fallback,
            # which sent operators chasing the wrong root cause.
            $failedEncoderKind = if ($encodePlan -and $encodePlan.EncoderKind) { [string]$encodePlan.EncoderKind } elseif ($usingCpu) { 'cpu' } else { 'unknown' }
            $reasonPrefix = switch ($failedEncoderKind) {
                'cpu'   { 'FFmpeg CPU encode failed' }
                'nvenc' { 'FFmpeg NVENC encode failed' }
                default { 'FFmpeg encode failed' }
            }
            $reason = if ($ffmpegErrorSummary) { "${reasonPrefix}: $ffmpegErrorSummary" } else { $reasonPrefix }
            $suggestedAction = if ($failedEncoderKind -eq 'cpu') {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. The libx265 CPU fallback failed, so re-tuning NVENC will not help; check for source corruption, libx265 OOM (lower the preset or quality), or an x265 build issue."
            } else {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. If NVENC was unstable, compare against the CPU fallback behavior."
            }
            # D2 fix — CPU failures are recorded as 'transient' just like
            # NVENC failures. Register-SourceFailure already escalates to
            # 'operator_required' after $TransientFailureRetryLimit repeated
            # same-(stage,error_code) failures (see engine\failures\failure_state.ps1
            # ~line 670). That gives a CPU job N retry chances for
            # genuinely transient errors (antivirus locks, transient OOM,
            # disk full near end), then escalates exactly once instead of
            # the previous "first failure is permanent" behavior.
            # Emit the matching encoder_fallback_completed event so the
            # diagnostics drawer can pair start with end (E5).
            if ($failedEncoderKind -eq 'cpu') {
                Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'failed' -SourcePath $file.FullName -Data @{
                    from_encoder    = [string]$VideoCodec
                    to_encoder      = (Get-MediaVideoCodecLibx265Name)
                    cpu_preset      = if ($encodePlan -and $encodePlan.PSObject.Properties['CpuPreset']) { [string]$encodePlan.CpuPreset } else { '' }
                    cpu_quality_crf = [int]$script:FallbackCpuQuality
                    error_code      = [string]$errorCode
                } | Out-Null
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
            $localIn = $null
            Write-Log "ENCODE failed - recorded as transient and scheduled for retry: $safeName" "ERROR"
            return $false
        }

        if (-not (Test-Path -LiteralPath $tempOut) -or (Get-Item -LiteralPath $tempOut).Length -eq 0) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE output missing or empty after ffmpeg' -Stage 'encode'
            $localIn = $null
            Write-Log "ENCODE: output missing or empty after ffmpeg" "ERROR"; return $false
        }

        # Duration sanity check — catches silent truncations.
        # AllowAVFallback tolerates the common case where an ASS subtitle cue
        # extends past the actual A/V end, inflating the source container duration.
        # D5 fix — preserve the encode-cpu-fallback route badge through the
        # verify stage so the GUI doesn't briefly drop the CPU label between
        # encode_cpu (100%) and the publish step.
        $verifyRoute = if ($usingCpu) { 'encode-cpu-fallback' } elseif ($usingSafeRetry) { 'encode-safe-retry' } else { 'encode' }
        Set-ProgressStage -Stage 'encode_verify' -Status $script:pipelineStatus -Route $verifyRoute -Percent $null -SaveNow
        if (-not (Test-DurationMatch -SourcePath $localIn -OutputPath $tempOut -Label "ENCODE" -AllowAVFallback)) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE duration mismatch' -Stage 'encode-verify' -SuggestedAction 'Compare source and encoded output A/V end times. Container-duration differences caused by subtitle tails are tolerated, so a remaining encode-verify failure usually means the output A/V is genuinely shorter than the source.'
            $localIn = $null
            Write-Log "ENCODE: duration mismatch - recorded as transient and scheduled for retry: $safeName" "ERROR"
            return $false
        }

        $sizePolicy = Test-MediaEncodeOutputSizePolicy `
            -SourcePath $localIn `
            -OutputPath $tempOut `
            -RoutingProfile $script:RoutingProfile `
            -SizeGuardMode $script:SizeGuardMode `
            -MaxGrowthPercent $script:MaxEncodeGrowthPercent `
            -CompatibilityGrowthPercent $script:CompatibilityEncodeGrowthPercent `
            -RouteReasonCode ([string]$script:CurrentRouteReasonCode)
        $script:CurrentSizePolicyResult = $sizePolicy.Metadata
        if ($sizePolicy.Exceeded) {
            $sizePolicySeverity = ([string]$sizePolicy.Severity).ToUpperInvariant()
            Write-Log "ENCODE SIZE: $($sizePolicy.Message)" $sizePolicySeverity
        } else {
            Write-Log "ENCODE SIZE: $($sizePolicy.Message)" "DEBUG"
        }
        if (-not $sizePolicy.Ok) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$sizePolicy.Message) -Stage 'encode-size-policy' -ErrorCode 'ENCODE_SIZE_GUARD_EXCEEDED' -SuggestedAction 'Review the source and routing policy. Use advisory/off size guard, force remux for a compatible source, or adjust encode quality/ladder before retrying.'
            $localIn = $null
            Write-Log "ENCODE: output rejected by strict size policy: $safeName" "ERROR"
            return $false
        }

        [System.IO.Directory]::CreateDirectory($paths.LocalDir) | Out-Null
        [System.IO.Directory]::CreateDirectory($paths.ServerDir) | Out-Null

        [System.IO.File]::Move($tempOut, $paths.LocalOut, $true)
        $tempOut = $null

        Write-PlexCompatibilityReport -FilePath $paths.LocalOut -Context "ENCODE: "

        # CurrentRouteReasonCode/Reason and route_actions.video are already
        # synchronized at the point $usingCpu / $usingSafeRetry was set. The
        # locals below are derived for the publish call only; do not re-mutate
        # script-scope state here (see E1 / E3 fixes).
        $route = if ($usingCpu) { "encode-cpu-fallback" } elseif ($usingSafeRetry) { "encode-safe-retry" } else { "encode" }
        $routeReasonCode = [string]$script:CurrentRouteReasonCode
        $routeReason     = [string]$script:CurrentRouteReason
        $publishResult = Complete-PipelineOutputPublish -SourceFile $file -ScratchPath $localIn -Paths $paths -Route $route -ProgressRoute 'encode' -StagePrefix 'encode' -Context "ENCODE: " -RouteReasonCode $routeReasonCode -RouteReason $routeReason -Tx3gTracks @($subResult.Tx3gTracks) -BdpgsTracks @($subResult.BdpgsTracks) -VobSubTracks @($subResult.VobSubTracks)
        $script:LastPublishResult = $publishResult
        if ($publishResult.DeleteLocalOutput) { $pushOk = $true }
        if ($publishResult.KeepScratchInput) { $localIn = $null }
        return [bool]$publishResult.Ok

    } catch {
        Write-Log "Do-Encode unexpected error: $_" "ERROR"
        Write-Log "Stack: $($_.ScriptStackTrace)" "DEBUG"
        if ($file) {
            $reason = "Do-Encode unexpected error: $($_.Exception.Message)"
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode-exception' -ErrorCode 'ENCODE_UNEXPECTED_EXCEPTION' -SuggestedAction 'Inspect the pipeline log stack trace and failure artifact, then clear the marker after fixing the root cause.' | Out-Null
            $localIn = $null
        }
        return $false
    } finally {
        if ($subResult -and $subResult.TempFiles) {
            $subResult.TempFiles | ForEach-Object { Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue }
        }
        if ($tempOut -and (Test-Path -LiteralPath $tempOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
        }
        if ($localIn -and (Test-Path -LiteralPath $localIn -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
            Remove-ScratchFingerprint $localIn
            Remove-EmptyScratchContainer $localIn
        }
        # FIX#10: ONLY delete local encoded output when server push
        # succeeded. On failure Invoke-ParkPendingPush has already moved
        # the file to PendingServerPush; deleting here would destroy
        # hours of encode work.
        if ($pushOk -and $paths -and $paths.LocalOut -and
            (Test-Path -LiteralPath $paths.LocalOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $paths.LocalOut -Force -ErrorAction SilentlyContinue
        }
    }
}
