# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode high-level orchestrator.

function Invoke-MediaPipelineEncode {
    param($file, [bool]$isTV, $tvInfo)

    $encodeContext = New-MediaPipelineEncodeContext -File $file -IsTV:$isTV -TvInfo $tvInfo

    try {
        foreach ($stage in @(
            'Invoke-MediaPipelineEncodePreflight',
            'Invoke-MediaPipelineEncodeDynamicHdrPolicy',
            'Invoke-MediaPipelineEncodeStreamPreparation',
            'Invoke-MediaPipelineEncodeAttemptLadder',
            'Invoke-MediaPipelineEncodeVerification',
            'Invoke-MediaPipelineEncodeSizeGuard',
            'Complete-MediaPipelineEncodePublish'
        )) {
            $result = & $stage -Context $encodeContext
            if ($result.Terminal) {
                return [bool]$result.Value
            }
        }
        return $false
    } catch {
        Write-Log "Do-Encode unexpected error: $_" "ERROR"
        Write-Log "Stack: $($_.ScriptStackTrace)" "DEBUG"
        if ($file) {
            $reason = "Do-Encode unexpected error: $($_.Exception.Message)"
            $failureScratchPath = $encodeContext.LocalIn
            $retainCompletedTempOutput = $false
            if (-not [string]::IsNullOrWhiteSpace([string]$encodeContext.TempOut)) {
                $tempOutputItem = Get-Item -LiteralPath $encodeContext.TempOut -ErrorAction SilentlyContinue
                if ($tempOutputItem -and $tempOutputItem.Length -gt 0) {
                    $failureScratchPath = $tempOutputItem.FullName
                    $retainCompletedTempOutput = $true
                }
            }
            Register-SourceFailure -SourceFile $file -ScratchPath $failureScratchPath -Classification 'transient' -Reason $reason -Stage 'encode-exception' -ErrorCode 'ENCODE_UNEXPECTED_EXCEPTION' -SuggestedAction 'Inspect the pipeline log stack trace and failure artifact, then clear the marker after fixing the root cause.' | Out-Null
            if ($retainCompletedTempOutput) {
                $encodeContext.TempOut = $null
            } else {
                $encodeContext.LocalIn = $null
            }
        }
        return $false
    } finally {
        $subResult = $encodeContext.SubResult
        if ($subResult -and $subResult.TempFiles) {
            $subResult.TempFiles | ForEach-Object { Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue }
        }
        if ($encodeContext.DynamicHdrTempFiles) {
            $encodeContext.DynamicHdrTempFiles | ForEach-Object {
                if (-not [string]::IsNullOrWhiteSpace([string]$_)) {
                    Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if ($encodeContext.TempOut -and (Test-Path -LiteralPath $encodeContext.TempOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $encodeContext.TempOut -Force -ErrorAction SilentlyContinue
        }
        if ($encodeContext.LocalIn -and (Test-Path -LiteralPath $encodeContext.LocalIn -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $encodeContext.LocalIn -Force -ErrorAction SilentlyContinue
            Remove-ScratchFingerprint $encodeContext.LocalIn
            Remove-EmptyScratchContainer $encodeContext.LocalIn
        }
        # FIX#10: ONLY delete local encoded output when server push
        # succeeded. On failure Invoke-ParkPendingPush has already moved
        # the file to PendingServerPush; deleting here would destroy
        # hours of encode work.
        if ($encodeContext.PushOk -and $encodeContext.Paths -and $encodeContext.Paths.LocalOut -and
            (Test-Path -LiteralPath $encodeContext.Paths.LocalOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $encodeContext.Paths.LocalOut -Force -ErrorAction SilentlyContinue
        }
    }
}
