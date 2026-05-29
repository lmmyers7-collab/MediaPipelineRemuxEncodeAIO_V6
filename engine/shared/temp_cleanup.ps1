# ==============================================================================
# engine\shared\temp_cleanup.ps1
# ==============================================================================
# Startup cleanup for stale pipeline scratch artifacts.
#
# Dot-sourced by callers. Clear-OldTempFiles reads $script:processingDir at
# call time and only removes the existing temp-name patterns that the main
# script has used historically.
# ==============================================================================

function Clear-OldTempFiles {
    $cutoff = (Get-Date).AddHours(-24)
    Get-ChildItem -Path $script:processingDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff -and
                       $_.Name -match '^(sub_|temp_av_|ffmpeg_stderr_|encode_temp_|sub_ass_|sub_final_|sub_bdpgs_)' } |
        Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $script:processingDir -Directory -Filter 'src_*' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Log "Cleaned orphaned temp files older than 24h"
}
