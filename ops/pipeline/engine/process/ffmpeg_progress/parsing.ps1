# ==============================================================================
# ops\pipeline\engine\process\ffmpeg_progress\parsing.ps1
# ==============================================================================
# FFmpeg stderr/progress parsing helpers for ffmpeg_progress.ps1.
# ==============================================================================

function Convert-FFmpegProgressTimestampToSeconds {
    param([string]$Value)

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    if ($text -match '^(\d+):(\d{2}):(\d{2}(?:\.\d+)?)$') {
        return ([double]$Matches[1] * 3600) + ([double]$Matches[2] * 60) + [double]$Matches[3]
    }
    return $null
}

function Get-FFmpegProgressPercentFromLine {
    param(
        [string]$Line,
        [double]$DurationSeconds
    )

    if ($DurationSeconds -le 0 -or [string]::IsNullOrWhiteSpace($Line)) { return $null }

    $seconds = $null
    if ($Line -match '^out_time_(?:us|ms)=(\d+)\s*$') {
        # FFmpeg progress reports both out_time_us and historical out_time_ms
        # as microseconds on current bundled builds.
        $seconds = [double]$Matches[1] / 1000000.0
    } elseif ($Line -match '^out_time=(.+?)\s*$') {
        $seconds = Convert-FFmpegProgressTimestampToSeconds $Matches[1]
    } elseif ($Line -match '^time=(\d+:\d{2}:\d{2}(?:\.\d+)?)') {
        $seconds = Convert-FFmpegProgressTimestampToSeconds $Matches[1]
    }

    if ($null -eq $seconds) { return $null }
    return [math]::Min(100, [math]::Max(0, [math]::Round(([double]$seconds / $DurationSeconds) * 100, 1)))
}

function Add-FFmpegErrorTail {
    param(
        [Parameter(Mandatory)] [System.Text.StringBuilder]$Builder,
        [AllowNull()] [string]$Text,
        [int]$MaxChars = 262144
    )
    if ($null -eq $Text) { return }
    [void]$Builder.AppendLine($Text)
    if ($Builder.Length -gt $MaxChars) {
        $remove = $Builder.Length - $MaxChars
        try { [void]$Builder.Remove(0, $remove) } catch {}
    }
}
