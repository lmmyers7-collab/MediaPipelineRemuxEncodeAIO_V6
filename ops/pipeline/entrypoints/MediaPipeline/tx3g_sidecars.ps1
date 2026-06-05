# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline.ps1.
# TX3G external sidecar export for existing output skip paths.

function Invoke-Tx3gSidecarExportForExistingOutput {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] [string] $MediaOutputPath,
        [string] $Context = ''
    )

    if (-not $script:ConvertTx3gToSrt -or -not $script:CreateExternalTx3gSrtSidecars) { return $true }
    $subFilter = Filter-SubtitleStreams $ScratchPath $Context
    if ($subFilter.ProbeFailed) {
        Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently publish an output with unknown subtitle state.' | Out-Null
        return $false
    }
    if (-not $subFilter.Tx3gConvert -or @($subFilter.Tx3gConvert).Count -eq 0) {
        return $true
    }

    $export = Export-Tx3gSrtSidecarsFromSource -FilterResult $subFilter -SourceFile $ScratchPath -MediaOutputPath $MediaOutputPath -Context $Context
    if ($export.Failures -and @($export.Failures).Count -gt 0) {
        Register-Tx3gSubtitleFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Failures @($export.Failures) -Stage 'subtitle-tx3g-extract'
        return $false
    }
    $written = @($export.Tracks | Where-Object { $_.status -eq 'written' }).Count
    $existing = @($export.Tracks | Where-Object { $_.status -eq 'existing' }).Count
    if (($written + $existing) -gt 0) {
        Write-Log "${Context}TX3G sidecars: $written written, $existing existing"
    }
    return $true
}
