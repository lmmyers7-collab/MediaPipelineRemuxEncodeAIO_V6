# ==============================================================================
# engine\subtitles\ass.ps1
# ==============================================================================
# ASS/SSA-only conversion through the Python helper.
# Dot-sourced by engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

if (-not (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue)) {
    function Write-SubtitleTrackProgress {
        param(
            [string]$Kind,
            [int]$StreamIndex = -1,
            [string]$Stage,
            [string]$Status,
            [int]$StepIndex = 0,
            [int]$StepTotal = 4,
            [array]$Steps = @(),
            [string]$Detail = "",
            [object]$CueCount = $null,
            [switch]$Completed,
            [switch]$Failed
        )
    }
}

function New-AssFailureRecord {
    param(
        [hashtable]$Entry,
        [string]$Reason,
        [string]$ErrorCode = 'SUBTITLE_ASS_CONVERT_FAILED',
        [string]$ReproPath = $null,
        [string]$ErrorText = $null
    )

    $streamIndex = if ($Entry -and $Entry.Stream) { [int]$Entry.Stream.index } else { -1 }
    return New-StandardFailureRecord -Stage 'subtitle-ass-convert' -Operation 'subtitle-ass-convert' -Category 'subtitle_conversion' -Reason $Reason -ErrorCode $ErrorCode -Tool 'python' -ReproPath $ReproPath -Retryable $true -AdditionalProperties @{
        StreamIndex     = $streamIndex
        stream_index    = $streamIndex
        SubtitleOrdinal = if ($Entry -and $Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        subtitle_ordinal = if ($Entry -and $Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        Language        = if ($Entry -and $Entry.ContainsKey('Lang')) { $Entry.Lang } else { 'und' }
        Title           = if ($Entry -and $Entry.ContainsKey('Title')) { $Entry.Title } else { '' }
        SourceIsDefault = if ($Entry -and $Entry.ContainsKey('SourceIsDefault')) { [bool]$Entry.SourceIsDefault } else { $false }
        source_is_default = if ($Entry -and $Entry.ContainsKey('SourceIsDefault')) { [bool]$Entry.SourceIsDefault } else { $false }
        IsForced        = if ($Entry -and $Entry.ContainsKey('IsForced')) { [bool]$Entry.IsForced } else { $false }
        is_forced       = if ($Entry -and $Entry.ContainsKey('IsForced')) { [bool]$Entry.IsForced } else { $false }
        ErrorText       = $ErrorText
        error_text      = $ErrorText
    }
}

function Convert-AssToSrt {
    param(
        [string]$SourceFile,
        [int]$StreamIndex,
        [hashtable]$StreamInfo = @{}
    )

    if (-not (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue)) {
        function Write-SubtitleTrackProgress {
            param(
                [string]$Kind,
                [int]$StreamIndex = -1,
                [string]$Stage,
                [string]$Status,
                [int]$StepIndex = 0,
                [int]$StepTotal = 4,
                [array]$Steps = @(),
                [string]$Detail = "",
                [object]$CueCount = $null,
                [switch]$Completed,
                [switch]$Failed
            )
        }
    }

    $finalSrt = Join-Path $script:processingDir "sub_final_$([System.IO.Path]::GetRandomFileName()).srt"
    $helperSrt = New-SrtAtomicTempPath -DestinationPath $finalSrt

    try {
        Write-Log "SUB CONVERT: stream $StreamIndex from $([System.IO.Path]::GetFileName($SourceFile))" "DEBUG"
        $subtitleProgressSteps = @('extract','convert','validate','sidecar_write')
        Write-SubtitleTrackProgress -Kind 'ass' -StreamIndex $StreamIndex -Stage 'extract' -Status 'Extracting ASS subtitle' -StepIndex 1 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($SourceFile))

        # Per-show overrides may replace RemoveKaraoke / ExcludeSubtitleStyles.
        $effectiveRemoveKara = if ($script:ActiveOverrides) {
            $script:ActiveOverrides.RemoveKaraoke
        } else { $script:RemoveKaraoke }
        $effectiveExcludeStyles = if ($script:ActiveOverrides -and
                                      $script:ActiveOverrides.ExcludeSubtitleStyles -and
                                      $script:ActiveOverrides.ExcludeSubtitleStyles.Count -gt 0) {
            $script:ActiveOverrides.ExcludeSubtitleStyles
        } else { $script:ExcludeSubtitleStyles }
        # FIX#14: whitelist — events matching these ALWAYS survive filtering.
        $effectiveIncludeStyles = if ($script:ActiveOverrides -and
                                      $script:ActiveOverrides.IncludeSubtitleStyles -and
                                      $script:ActiveOverrides.IncludeSubtitleStyles.Count -gt 0) {
            $script:ActiveOverrides.IncludeSubtitleStyles
        } else { $script:IncludeSubtitleStyles }

        $karaokeArg = if ($effectiveRemoveKara) { "1" } else { "0" }
        # Pass exclude-style patterns as pipe-separated list. Empty string =
        # use ass_to_srt.py's built-in defaults.
        $excludeArg = if ($effectiveExcludeStyles -and $effectiveExcludeStyles.Count -gt 0) {
            ($effectiveExcludeStyles -join '|')
        } else { "" }
        # FIX#14: new 6th argv — include-style patterns (whitelist).
        $includeArg = if ($effectiveIncludeStyles -and $effectiveIncludeStyles.Count -gt 0) {
            ($effectiveIncludeStyles -join '|')
        } else { "" }
        $timeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleExtractTimeoutSeconds' -DefaultSeconds 180
        $formattingArg = if (Get-EffectiveSubtitleSwitch -Name 'StripFormatting' -Default $true) { "--strip-formatting" } else { "--keep-formatting" }
        $helperArgs = @(
            $assToSrtScript, $SourceFile, $StreamIndex.ToString(), $helperSrt,
            $karaokeArg, $excludeArg, $includeArg,
            "--ffmpeg-bin", $ffmpegPath,
            "--extract-timeout-seconds", $timeoutSeconds.ToString(),
            $formattingArg
        )
        Write-SubtitleTrackProgress -Kind 'ass' -StreamIndex $StreamIndex -Stage 'convert' -Status 'Converting ASS subtitle to SRT' -StepIndex 2 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($SourceFile))
        $result = Invoke-PythonToolCommand -ArgumentList $helperArgs -TimeoutSeconds $timeoutSeconds -Stage 'subtitle-ass-convert' -SaveReproOnFailure

        $subtitleDiagLines = @()
        if ($result.Error) {
            $subtitleDiagLines = $result.Error -split '\r?\n' | Where-Object { $_.Trim() }
            $subtitleDiagLines | ForEach-Object { Write-Log "  pysubs2: $_" "DEBUG" }
        }

        $subtitleSummary = $subtitleDiagLines |
            Where-Object {
                $_ -match '^INFO: (Resolved overlaps|Applied 1ms gap|.+cues written|Kept styles:|Whitelisted styles that survived exclude-filter:|Dropped styles:)'
            } |
            ForEach-Object { $_ -replace '^INFO:\s*', '' } |
            Select-Object -First 4
        if ($subtitleSummary) {
            Write-Log "SUB CONVERT: $(($subtitleSummary -join ' | '))"
        }

        if ($result.ExitCode -ne 0) {
            $summary = if (Get-Command -Name Get-ErrorTextSummary -ErrorAction SilentlyContinue) {
                Get-ErrorTextSummary -ErrorText $result.Error
            } else {
                ([string]$result.Error)
            }
            if ([string]::IsNullOrWhiteSpace($summary)) { $summary = "ass_to_srt.py exited with code $($result.ExitCode)" }
            $reproPath = $result.ReproPath
            $code = if ($result.TimedOut) {
                'SUBTITLE_ASS_CONVERT_TIMEOUT'
            } elseif ($result.Stopped) {
                'SUBTITLE_ASS_CONVERT_STOPPED'
            } else {
                'SUBTITLE_ASS_CONVERT_FAILED'
            }
            Write-SubtitleTrackProgress -Kind 'ass' -StreamIndex $StreamIndex -Stage 'convert' -Status 'ASS subtitle conversion failed' -StepIndex 2 -StepTotal 4 -Steps $subtitleProgressSteps -Detail $summary -Failed
            Write-Log "SUB CONVERT: ass_to_srt.py failed (exit $($result.ExitCode)) for stream $StreamIndex`: $summary" "WARN"
            if ($result.Error) {
                $result.Error -split "`n" | Where-Object { $_ -match 'ERROR' } |
                    ForEach-Object { Write-Log "  reason: $_" "WARN" }
            }
            if ($helperSrt -and (Test-Path -LiteralPath $helperSrt)) {
                Remove-Item -LiteralPath $helperSrt -Force -ErrorAction SilentlyContinue
            }
            if ($finalSrt -and (Test-Path -LiteralPath $finalSrt)) {
                Remove-Item -LiteralPath $finalSrt -Force -ErrorAction SilentlyContinue
            }
            return [pscustomobject]@{
                Ok       = $false
                Path     = $null
                CueCount = 0
                Reason   = $summary
                Failure  = (New-AssFailureRecord -Entry $StreamInfo -Reason $summary -ErrorCode $code -ReproPath $reproPath -ErrorText $result.Error)
            }
        }

        Write-SubtitleTrackProgress -Kind 'ass' -StreamIndex $StreamIndex -Stage 'validate' -Status 'Validating ASS subtitle SRT' -StepIndex 3 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($helperSrt))
        $preMoveValidation = Test-SrtFileUsable -Path $helperSrt
        if (-not $preMoveValidation.Ok) {
            $reason = "ASS conversion output is not usable for stream $StreamIndex`: $($preMoveValidation.Reason)"
            $code = if ($preMoveValidation.Reason -match 'empty|blank|missing') { 'SUBTITLE_ASS_SRT_EMPTY' } else { 'SUBTITLE_ASS_SRT_INVALID' }
            Write-SubtitleTrackProgress -Kind 'ass' -StreamIndex $StreamIndex -Stage 'validate' -Status 'ASS subtitle validation failed' -StepIndex 3 -StepTotal 4 -Steps $subtitleProgressSteps -Detail $reason -Failed
            Write-Log "SUB CONVERT: $reason" "WARN"
            return [pscustomobject]@{
                Ok       = $false
                Path     = $null
                CueCount = 0
                Reason   = $reason
                Failure  = (New-AssFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode $code)
            }
        }

        $validation = Complete-AtomicSrtWrite -TempPath $helperSrt -DestinationPath $finalSrt
        $cueCount = $validation.CueCount
        Write-Log "SUB CONVERT: Stream $StreamIndex -> $cueCount raw cues" "DEBUG"

        # Post-process: merge adjacent identical cues to collapse karaoke animation frames
        if ($script:MergeAdjacent -and $cueCount -gt 1) {
            Merge-AdjacentIdenticalCues -SrtPath $finalSrt -ThresholdMs $script:MergeThresholdMs
            $postMergeValidation = Test-SrtFileUsable -Path $finalSrt
            if (-not $postMergeValidation.Ok) {
                throw "ASS SRT failed validation after cue merge: $($postMergeValidation.Reason)"
            }
            $cueCount = $postMergeValidation.CueCount
        }

        Write-Log "SUB CONVERT: Stream $StreamIndex -> $cueCount cues written"
        Write-SubtitleTrackProgress -Kind 'ass' -StreamIndex $StreamIndex -Stage 'validate' -Status 'ASS subtitle SRT validated' -StepIndex 3 -StepTotal 4 -Steps $subtitleProgressSteps -Detail "$cueCount cue(s)" -CueCount $cueCount
        return [pscustomobject]@{
            Ok       = $true
            Path     = $finalSrt
            CueCount = $cueCount
            Reason   = 'ok'
            Failure  = $null
        }

    } catch {
        $reason = "ASS conversion error for stream $StreamIndex`: $($_.Exception.Message)"
        Write-SubtitleTrackProgress -Kind 'ass' -StreamIndex $StreamIndex -Stage 'convert' -Status 'ASS subtitle conversion failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert','validate','sidecar_write') -Detail $reason -Failed
        Write-Log "SUB CONVERT: Unexpected error for stream $StreamIndex`: $_" "ERROR"
        if ($finalSrt -and (Test-Path -LiteralPath $finalSrt)) {
            Remove-Item -LiteralPath $finalSrt -Force -ErrorAction SilentlyContinue
        }
        if ($helperSrt -and (Test-Path -LiteralPath $helperSrt)) {
            Remove-Item -LiteralPath $helperSrt -Force -ErrorAction SilentlyContinue
        }
        return [pscustomobject]@{
            Ok       = $false
            Path     = $null
            CueCount = 0
            Reason   = $reason
            Failure  = (New-AssFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_ASS_CONVERT_EXCEPTION' -ErrorText $reason)
        }
    } finally {
        if ($helperSrt -and (Test-Path -LiteralPath $helperSrt)) {
            Remove-Item -LiteralPath $helperSrt -Force -ErrorAction SilentlyContinue
        }
    }
}
