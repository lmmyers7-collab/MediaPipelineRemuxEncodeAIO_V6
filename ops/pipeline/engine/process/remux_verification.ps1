# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux output verification before publish handoff.

function Invoke-MediaPipelineRemuxVerification {
    param([Parameter(Mandatory)] $Context)

    if (-not (Test-Path -LiteralPath $Context.Paths.LocalOut) -or
        (Get-Item -LiteralPath $Context.Paths.LocalOut).Length -eq 0) {
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason 'REMUX output missing or empty after mkvmerge' -Stage 'remux-mkvmerge'
        $Context.LocalIn = $null
        Write-Log "REMUX: output missing or empty after mkvmerge" "ERROR"
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-mkvmerge'
    }

    Set-ProgressStage -Stage 'remux_verify' -Status $script:pipelineStatus -Route 'remux' -Percent $null -SaveNow
    if (-not (Test-DurationMatch -SourcePath $Context.LocalIn -OutputPath $Context.Paths.LocalOut -Label "REMUX" -AllowAVFallback)) {
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.Paths.LocalOut -Classification 'transient' -Reason 'REMUX duration mismatch' -Stage 'remux-verify' -SuggestedAction 'Compare source and remuxed output A/V end times. Subtitle-tail container differences are tolerated now, so a remaining remux-verify failure usually indicates the output A/V is actually short.'
        Write-Log "REMUX: output duration mismatch - treating as failure" "ERROR"
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-verify'
    }

    $videoPreservation = Test-OutputVideoStreamPreservation -SourcePath $Context.LocalIn -OutputPath $Context.Paths.LocalOut -Route 'remux' -SourceInventory $Context.VideoStreamPolicy.Inventory
    if (-not [bool]$videoPreservation.Allowed) {
        $reason = [string]$videoPreservation.Reason
        $errorCode = [string]$videoPreservation.ErrorCode
        $failureProperties = [ordered]@{
            video_stream_preservation = $videoPreservation
            source_video_stream_count = [int]$videoPreservation.SourceCount
            output_video_stream_count = [int]$videoPreservation.OutputCount
            video_stream_evidence     = ConvertTo-VideoStreamFailureEvidence -SourceInventory $videoPreservation.SourceInventory -OutputInventory $videoPreservation.OutputInventory -Route 'remux' -Reason $reason -ErrorCode $errorCode
        }
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.Paths.LocalOut -Classification 'operator_required' -Reason $reason -Stage 'remux-video-stream-verify' -ErrorCode $errorCode -SuggestedAction 'Inspect source/output ffprobe stream inventories and saved FFmpeg/mkvmerge repro commands; publish remains blocked until every real source video stream is present in output.' -AdditionalProperties $failureProperties
        Write-Log "REMUX: $reason" "ERROR"
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-video-stream-verify'
    }

    Write-PlexCompatibilityReport -FilePath $Context.Paths.LocalOut -Context "REMUX: "
    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-verify'
}
