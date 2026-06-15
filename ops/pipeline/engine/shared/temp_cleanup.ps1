# ==============================================================================
# ops\pipeline\engine\shared\temp_cleanup.ps1
# ==============================================================================
# Startup cleanup for stale pipeline scratch artifacts.
#
# Dot-sourced by callers. Clear-OldTempFiles reads $script:processingDir at
# call time and only removes the existing temp-name patterns that the main
# script has used historically.
# ==============================================================================

function Write-TempCleanupBoundaryLog {
    param([string]$Message, [string]$Level = 'WARN')

    if (Get-Command -Name Write-Log -ErrorAction SilentlyContinue) {
        Write-Log $Message $Level
    }
}

function Test-TempCleanupProcessingBoundary {
    if ([string]::IsNullOrWhiteSpace([string]$script:processingDir)) {
        Write-TempCleanupBoundaryLog 'Startup temp cleanup skipped: processingDir is not set.' 'ERROR'
        return $false
    }
    if (-not (Get-Command -Name Test-MediaPipelinePathBoundarySafe -ErrorAction SilentlyContinue)) {
        Write-TempCleanupBoundaryLog 'Startup temp cleanup skipped: path boundary helper is unavailable.' 'ERROR'
        return $false
    }

    $localBaseVariable = Get-Variable -Name 'LocalBase' -Scope Script -ErrorAction SilentlyContinue
    $localBase = if ($localBaseVariable -and -not [string]::IsNullOrWhiteSpace([string]$localBaseVariable.Value)) {
        [string]$localBaseVariable.Value
    } else {
        ''
    }
    if ([string]::IsNullOrWhiteSpace($localBase)) {
        Write-TempCleanupBoundaryLog 'Startup temp cleanup skipped: LocalBase is not set.' 'ERROR'
        return $false
    }

    $processingBoundary = Test-MediaPipelinePathBoundarySafe -Path ([string]$script:processingDir) -Root $localBase
    if (-not $processingBoundary.Ok) {
        Write-TempCleanupBoundaryLog "Startup temp cleanup skipped: processingDir failed LocalBase boundary guard ($($processingBoundary.ReasonCode)): $($script:processingDir)" 'ERROR'
        return $false
    }
    return $true
}

function Remove-TempCleanupCandidate {
    param(
        [Parameter(Mandatory)] $Item,
        [switch] $Recurse
    )

    $boundary = Test-MediaPipelinePathBoundarySafe -Path ([string]$Item.FullName) -Root ([string]$script:processingDir)
    if (-not $boundary.Ok) {
        Write-TempCleanupBoundaryLog "Startup temp cleanup skipped unsafe candidate ($($boundary.ReasonCode)): $($Item.FullName)" 'ERROR'
        return
    }
    Remove-Item -LiteralPath $Item.FullName -Force -Recurse:$Recurse -ErrorAction SilentlyContinue
}

function Clear-OldTempFiles {
    if (-not (Test-TempCleanupProcessingBoundary)) { return }

    $cutoff = (Get-Date).AddHours(-24)
    Get-ChildItem -Path $script:processingDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff -and
                       $_.Name -match '^(sub_|temp_av_|ffmpeg_stderr_|encode_temp_|sub_ass_|sub_final_|sub_bdpgs_)' } |
        ForEach-Object { Remove-TempCleanupCandidate -Item $_ }
    Get-ChildItem -Path $script:processingDir -Directory -Filter 'src_*' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { Remove-TempCleanupCandidate -Item $_ -Recurse }
    Write-Log "Cleaned orphaned temp files older than 24h"
}
