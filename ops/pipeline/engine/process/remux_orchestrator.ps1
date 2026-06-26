# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux route orchestrator.

function Invoke-MediaPipelineRemux {
    param(
        $File,
        [bool] $IsTV,
        $TvInfo,
        [switch] $FallbackFromOversizedEncode,
        [switch] $FallbackFromDynamicHdrEncode
    )

    $context = New-MediaPipelineRemuxContext -File $File -IsTV:$IsTV -TvInfo $TvInfo -FallbackFromOversizedEncode:([bool]$FallbackFromOversizedEncode) -FallbackFromDynamicHdrEncode:([bool]$FallbackFromDynamicHdrEncode)
    try {
        foreach ($stage in @(
            'Invoke-MediaPipelineRemuxPreflight',
            'New-MediaPipelineRemuxSubtitlePlan',
            'Invoke-MediaPipelineRemuxFfmpegAvStage',
            'Complete-MediaPipelineRemuxSubtitlePlan',
            'New-MediaPipelineRemuxMkvmergeArgumentList',
            'Invoke-MediaPipelineRemuxMkvmergeStage',
            'Invoke-MediaPipelineRemuxVerification',
            'Complete-MediaPipelineRemuxPublish'
        )) {
            $result = & $stage -Context $context
            if ($result.Terminal) {
                return [bool]$result.Value
            }
        }
        return $false
    } catch {
        Write-Log "Do-Remux unexpected error: $_" "ERROR"
        Write-Log "Stack: $($_.ScriptStackTrace)" "DEBUG"
        if ($File) {
            $reason = "Do-Remux unexpected error: $($_.Exception.Message)"
            Register-SourceFailure -SourceFile $File -ScratchPath $context.LocalIn -Classification 'transient' -Reason $reason -Stage 'remux-exception' -ErrorCode 'REMUX_UNEXPECTED_EXCEPTION' -SuggestedAction 'Inspect the pipeline log stack trace and failure artifact, then clear the marker after fixing the root cause.' | Out-Null
            $context.LocalIn = $null
        }
        return $false
    } finally {
        if ($context.TempAvFile)  { Remove-Item -LiteralPath $context.TempAvFile -Force -ErrorAction SilentlyContinue }
        if ($context.FallbackFromOversizedEncode) { $context.LocalIn = $null }
        if ($context.LocalIn)     {
            Remove-Item -LiteralPath $context.LocalIn -Force -ErrorAction SilentlyContinue
            Remove-ScratchFingerprint $context.LocalIn
            Remove-EmptyScratchContainer $context.LocalIn
        }
        if ($context.PushOk -and $context.Paths -and $context.Paths.LocalOut -and
            (Test-Path -LiteralPath $context.Paths.LocalOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $context.Paths.LocalOut -Force -ErrorAction SilentlyContinue
        }
        if ($context.SubTracks -and $context.SubTracks.TempFiles) {
            $context.SubTracks.TempFiles | ForEach-Object { Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue }
        }
    }
}
