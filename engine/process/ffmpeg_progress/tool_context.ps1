# ==============================================================================
# engine\process\ffmpeg_progress\tool_context.ps1
# ==============================================================================
# FFmpeg command/progress argument and priority context helpers.
# ==============================================================================

function New-FFmpegToolContext {
    param(
        [Parameter(Mandatory)] [array]$FFArgs,
        [Parameter(Mandatory)] [string]$Executable,
        [switch]$CpuEncode,
        [string]$ProcessPriority = 'inherit'
    )

    $ffmpegArgs = $FFArgs + @("-progress","pipe:2","-nostats")
    $commandLine = Format-NativeCommandLine -FilePath $Executable -ArgumentList $ffmpegArgs

    $script:LastFFmpegCommandLine = $commandLine
    $script:LastFFmpegErrorLog    = $null
    $script:LastFFmpegReproPath   = $null
    $script:LastFFmpegToolErrorCode = $null
    $script:LastFFmpegDurationSeconds = $null

    $priorityClassEnum = $null
    $priorityText = if ($ProcessPriority) { ([string]$ProcessPriority).Trim().ToLowerInvariant() } else { '' }
    if ($CpuEncode -and $priorityText -and $priorityText -ne 'inherit') {
        switch ($priorityText) {
            'idle'        { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::Idle }
            'belownormal' { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::BelowNormal }
            'normal'      { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::Normal }
            'abovenormal' { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::AboveNormal }
            'high'        { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::High }
            default       { $priorityClassEnum = $null }
        }
    }

    $script:LastFFmpegPriorityRequested = if ($priorityClassEnum) { [string]$priorityClassEnum } else { 'inherit' }
    $script:LastFFmpegPriorityApplied   = ($null -eq $priorityClassEnum)
    $script:LastFFmpegPriorityError     = ''

    return [pscustomobject]@{
        Arguments         = $ffmpegArgs
        CommandLine       = $commandLine
        PriorityClass     = $priorityClassEnum
        PriorityRequested = [string]$script:LastFFmpegPriorityRequested
        PriorityApplied   = [bool]$script:LastFFmpegPriorityApplied
        PriorityError     = [string]$script:LastFFmpegPriorityError
    }
}
