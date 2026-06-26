# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux mkvmerge execution and result classification.

function Invoke-MediaPipelineRemuxMkvmergeStage {
    param([Parameter(Mandatory)] $Context)

    Set-ProgressStage -Stage 'remux_mux' -Status $script:pipelineStatus -Route 'remux' -Percent 0 -SaveNow
    $mkv = Invoke-MkvmergeWithProgress -ArgumentList @($Context.MkvArgs) -Label 'REMUX-MUX' -TimeoutSeconds $script:MkvmergeRemuxTimeoutSeconds -Stage 'remux-mkvmerge' -ProgressStage 'remux_mux' -ProgressRoute 'remux' -SaveReproOnFailure
    $Context.MkvmergeResult = $mkv
    $mkvExitCode = [int]$mkv.ExitCode
    $mkvFailed = ([bool]$mkv.TimedOut -or [bool]$mkv.Stopped -or $mkvExitCode -lt 0 -or $mkvExitCode -ge 2 -or [bool]$mkv.MkvmergeWarningBlocking)
    if ($mkvFailed) {
        $reproPath = $mkv.ReproPath
        $mkvLog = $null
        $mkvErrorSummary = Get-ErrorTextSummary -ErrorText $mkv.Error
        $errorCode = Get-MkvmergeFailureCode -ErrorText $mkv.Error -ExitCode $mkvExitCode -TimedOut ([bool]$mkv.TimedOut) -Stopped ([bool]$mkv.Stopped)
        if ([bool]$mkv.MkvmergeWarningBlocking) {
            $errorCode = [string]$mkv.ToolErrorCode
            if ([string]::IsNullOrWhiteSpace($mkvErrorSummary)) {
                $mkvErrorSummary = [string]$mkv.MkvmergeWarningMatchedText
            }
        }
        $reason = if ([bool]$mkv.TimedOut) {
            if ($mkvErrorSummary) { "mkvmerge timed out after $($script:MkvmergeRemuxTimeoutSeconds)s: $mkvErrorSummary" } else { "mkvmerge timed out after $($script:MkvmergeRemuxTimeoutSeconds)s" }
        } elseif ([bool]$mkv.Stopped) {
            if ($mkvErrorSummary) { "mkvmerge stopped by operator request: $mkvErrorSummary" } else { "mkvmerge stopped by operator request" }
        } elseif ([bool]$mkv.MkvmergeWarningBlocking) {
            if ($mkvErrorSummary) { "mkvmerge warning blocked publish: $mkvErrorSummary" } else { "mkvmerge warning blocked publish" }
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
            'MKVMERGE_WARNING_STREAM_LOSS' { "mkvmerge reported warning text that implies skipped, unsupported, dropped, unreadable, or invalid stream content. Inspect the warning text and saved repro command $reproPath before retrying."; break }
            default {
                if ($mkvLog) {
                    "Inspect mkvmerge stderr log $mkvLog and repro command $reproPath, then retry after fixing the subtitle/container issue."
                } else {
                    "Inspect the saved mkvmerge repro command $reproPath, then retry after fixing the subtitle/container issue."
                }
            }
        }
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason $reason -Stage 'remux-mkvmerge' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-mkvmerge'
    }
    if ($mkvExitCode -eq 1) {
        Write-Log "mkvmerge completed with warnings" "WARN"
        $mkvWarnText = if (-not [string]::IsNullOrWhiteSpace([string]$mkv.Output)) { [string]$mkv.Output } else { [string]$mkv.Error }
        if ($mkvWarnText) {
            $mkvWarnText -split '\r?\n' | Where-Object { $_ -match '\S' } |
                Select-Object -Last 8 | ForEach-Object { Write-Log "  mkvmerge: $_" "WARN" }
        }
    }

    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-mkvmerge'
}
