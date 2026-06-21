[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = 'INFO'
    )
    $script:CapturedLogs += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}

function DebugLog {
    param([string]$Message)
}

function Set-ProgressStage {
    param(
        [string]$Stage,
        [string]$Status,
        [string]$Route,
        $Percent,
        [switch]$SaveNow
    )
    $script:CapturedProgress += ,([pscustomobject]@{
        Stage = $Stage
        Route = $Route
        Percent = $Percent
        SaveNow = [bool]$SaveNow
    })
}

function Write-PipelineEvent {
    param(
        [string]$EventType,
        [string]$Stage = '',
        [string]$Route = '',
        [string]$Status = '',
        [string]$SourcePath = '',
        $Data = $null
    )
    $script:CapturedEvents += ,([pscustomobject]@{
        EventType = $EventType
        Stage = $Stage
        Route = $Route
        Status = $Status
        SourcePath = $SourcePath
        Data = $Data
    })
    return $true
}

function Format-NativeCommandLine {
    param(
        [string]$FilePath,
        [array]$ArgumentList = @()
    )
    return (@($FilePath) + @($ArgumentList | ForEach-Object { [string]$_ })) -join ' '
}

function Save-ReproCommand {
    param(
        [string]$ToolName,
        [string]$Executable,
        [array]$ArgumentList,
        [string]$Stage
    )
    $script:ReproSaves++
    return "repro-$Stage.cmd"
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\native_process_contracts.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\size_policy.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\ffmpeg_progress.ps1')

$script:CapturedLogs = @()
$script:CapturedProgress = @()
$script:CapturedEvents = @()
$script:ReproSaves = 0
$script:FFmpegProgressWriteStepPercent = 25
$mkvmergePath = 'mkvmerge.exe'
$StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-mkvmerge-warning-{0}.stop" -f ([Guid]::NewGuid().ToString('N')))

function Invoke-NativeProcess {
    param(
        [string]$FilePath,
        [array]$ArgumentList,
        [int]$TimeoutSeconds = 0,
        [string]$StopFlagPath = '',
        [string]$Label = '',
        [int]$MaxStdoutChars = 0,
        [int]$MaxStderrChars = 0,
        [scriptblock]$StdoutLineHandler
    )
    if ($StdoutLineHandler) {
        & $StdoutLineHandler '#GUI#progress 33%' 'stdout'
        & $StdoutLineHandler 'Progress: 100%' 'stdout'
    }
    return New-NativeCommandResult -ExitCode 1 -Stdout '#GUI#progress 33%' -Stderr 'mkvmerge warning text' -TimedOut:$false -Stopped:$false -ErrorCode 'NATIVE_EXIT_1'
}

try {
    Assert-Equal (Get-MkvmergeProgressPercentFromLine -Line '#GUI#progress 42%') 42 'GUI mkvmerge progress parsing changed.'
    Assert-Equal (Get-MkvmergeProgressPercentFromLine -Line 'Progress: 125%') 100 'mkvmerge progress clamp changed.'

    $result = Invoke-MkvmergeWithProgress `
        -ArgumentList @('--output', 'out.mkv', 'in.mkv') `
        -Label 'TEST-MKVMERGE-WARN' `
        -TimeoutSeconds 30 `
        -Stage 'remux-mkvmerge' `
        -ProgressStage 'remux_mux' `
        -ProgressRoute 'remux' `
        -SaveReproOnFailure

    Assert-Equal ([int]$result.ExitCode) 1 'mkvmerge warning exit code changed.'
    Assert-Equal ([string]$result.ToolErrorCode) 'MKVMERGE_WARNINGS' 'mkvmerge warning exit must not be classified as failure.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$result.ReproPath)) 'mkvmerge warning exit must not save a repro command.'
    Assert-Equal $script:ReproSaves 0 'mkvmerge warning exit should not invoke Save-ReproCommand.'

    $completed = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' })[-1]
    Assert-Equal ([string]$completed.Status) 'succeeded' 'mkvmerge warning exit should emit succeeded tool status.'
    Assert-Equal ([string]$completed.Data.error_code) 'MKVMERGE_WARNINGS' 'mkvmerge warning event should carry warning classification.'

    $progressValues = @($script:CapturedProgress | Where-Object { $_.Stage -eq 'remux_mux' } | ForEach-Object { $_.Percent })
    Assert-True ($progressValues -contains 0) 'mkvmerge wrapper did not publish initial progress.'
    Assert-True ($progressValues -contains 100) 'mkvmerge warning exit should publish final 100 percent.'

    $script:CapturedProgress = @()
    $script:CapturedEvents = @()
    $script:ReproSaves = 0
    function Invoke-NativeProcess {
        param(
            [string]$FilePath,
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$StopFlagPath = '',
            [string]$Label = '',
            [int]$MaxStdoutChars = 0,
            [int]$MaxStderrChars = 0,
            [scriptblock]$StdoutLineHandler
        )
        return New-NativeCommandResult -ExitCode 1 -Stdout 'Warning: Skipping track ID 2 because the codec is unsupported.' -Stderr '' -TimedOut:$false -Stopped:$false -ErrorCode 'NATIVE_EXIT_1'
    }

    $blocked = Invoke-MkvmergeWithProgress `
        -ArgumentList @('--output', 'out.mkv', 'in.mkv') `
        -Label 'TEST-MKVMERGE-BLOCKING-WARN' `
        -TimeoutSeconds 30 `
        -Stage 'remux-mkvmerge' `
        -ProgressStage 'remux_mux' `
        -ProgressRoute 'remux' `
        -SaveReproOnFailure

    Assert-Equal ([int]$blocked.ExitCode) 1 'blocking mkvmerge warning should preserve native exit code evidence.'
    Assert-Equal ([string]$blocked.ToolErrorCode) 'MKVMERGE_WARNING_STREAM_LOSS' 'risky mkvmerge warning text must block with a stream-loss code.'
    Assert-True ([bool]$blocked.MkvmergeWarningBlocking) 'risky mkvmerge warning should be marked blocking.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$blocked.MkvmergeWarningMatchedText)) 'blocking warning should retain matched warning text.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$blocked.ReproPath)) 'blocking warning should save a repro command.'
    Assert-Equal $script:ReproSaves 1 'blocking warning should invoke Save-ReproCommand.'

    $blockedCompleted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' })[-1]
    Assert-Equal ([string]$blockedCompleted.Status) 'failed' 'blocking mkvmerge warning should emit failed tool status.'
    Assert-Equal ([string]$blockedCompleted.Data.error_code) 'MKVMERGE_WARNING_STREAM_LOSS' 'blocking mkvmerge warning event should carry stream-loss classification.'

    $blockedProgressValues = @($script:CapturedProgress | Where-Object { $_.Stage -eq 'remux_mux' } | ForEach-Object { $_.Percent })
    Assert-True ($blockedProgressValues -contains 0) 'blocking mkvmerge warning should still publish initial progress.'
    Assert-True (-not ($blockedProgressValues -contains 100)) 'blocking mkvmerge warning must not publish final 100 percent.'

    $script:CapturedProgress = @()
    $script:CapturedEvents = @()
    $script:ReproSaves = 0
    $script:FFmpegProgressWriteStepPercent = 25
    $script:StopRequested = $false
    $script:LastFFmpegAbortCode = ''
    $script:LastFFmpegAbortReason = ''
    $script:LastEncodeWasteGuardProjection = $null
    $script:CapturedFFmpegWorkingDirectory = ''

    $ffmpegPath = 'ffmpeg.exe'
    $LocalFailed = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-ffmpeg-waste-guard-{0}" -f ([Guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $LocalFailed | Out-Null
    $PauseFlag = Join-Path $LocalFailed 'pause.flag'
    $StopFlag = Join-Path $LocalFailed 'stop.flag'
    $sourcePath = Join-Path $LocalFailed 'source.bin'
    $outputPath = Join-Path $LocalFailed 'encode-temp.mkv'
    [System.IO.File]::WriteAllBytes($sourcePath, (New-Object byte[] 1000))
    $script:WasteGuardOutputPath = $outputPath

    function Invoke-FFprobeCommand {
        param(
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$Stage = ''
        )
        return New-NativeCommandResult -ExitCode 0 -Stdout '100' -Stderr '' -ErrorCode 'OK'
    }

    function Invoke-NativeProcess {
        param(
            [string]$FilePath,
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$StopFlagPath = '',
            [string]$Label = '',
            [int]$MaxStdoutChars = 0,
            [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler,
            [scriptblock]$PollHandler,
            [scriptblock]$ProcessStartedHandler,
            [string]$WorkingDirectory = ''
        )
        $script:CapturedFFmpegWorkingDirectory = $WorkingDirectory
        [System.IO.File]::WriteAllBytes($script:WasteGuardOutputPath, (New-Object byte[] 700))
        if ($StderrLineHandler) {
            & $StderrLineHandler 'out_time_us=25000000' 'stderr'
        }
        $abort = if ($PollHandler) { & $PollHandler 180 $null } else { $null }
        if ($abort -and [bool]$abort.Abort) {
            $result = New-NativeCommandResult -ExitCode -1 -Stdout '' -Stderr '[KILLED: waste guard projection]' -TimedOut:$false -Stopped:$false -ErrorCode ([string]$abort.AbortCode)
            Set-ExternalToolResultProperty -Result $result -Name 'Aborted' -Value $true
            Set-ExternalToolResultProperty -Result $result -Name 'AbortCode' -Value ([string]$abort.AbortCode)
            Set-ExternalToolResultProperty -Result $result -Name 'AbortReason' -Value ([string]$abort.AbortReason)
            Set-ExternalToolResultProperty -Result $result -Name 'DurationSeconds' -Value 180
            return $result
        }
        return New-NativeCommandResult -ExitCode 0 -Stdout '' -Stderr '' -ErrorCode 'OK'
    }

    $wasteGuardContext = [pscustomobject][ordered]@{
        Enabled = $true
        Mode = 'enforce'
        Enforce = $true
        DryRun = $false
        SourceSizeBytes = 1000L
        OutputPath = $outputPath
        LimitRatio = 1.05
        OversizeMarginPercent = 20
        MinProgressPercent = 15
        MinElapsedSeconds = 120
        ConsecutiveSamples = 1
        ConsecutiveHits = 0
        PollSeconds = 0
    }

    $ffmpegOk = Invoke-FFmpegWithProgress `
        -FFArgs @('-i', $sourcePath, $outputPath) `
        -Label 'TEST-FFMPEG-WASTE-GUARD' `
        -InputFile $sourcePath `
        -TimeoutSeconds 30 `
        -ProgressStage 'encode' `
        -ProgressRoute 'encode' `
        -ReproStage 'encode' `
        -OutputPath $outputPath `
        -WasteGuardContext $wasteGuardContext `
        -WorkingDirectory $LocalFailed

    Assert-Equal ([bool]$ffmpegOk) $false 'FFmpeg wrapper should return false when the waste guard aborts.'
    Assert-Equal ([string]$script:LastFFmpegAbortCode) 'ENCODE_WASTE_GUARD_PROJECTED_OVERSIZE' 'FFmpeg waste guard abort code was not exposed.'
    Assert-True ($script:LastEncodeWasteGuardProjection -ne $null) 'FFmpeg waste guard abort should expose projection metadata.'
    Assert-Equal ([bool]$script:LastEncodeWasteGuardProjection.ShouldAbort) $true 'Projection metadata should record an abort decision.'
    Assert-Equal ([string]$script:CapturedFFmpegWorkingDirectory) $LocalFailed 'FFmpeg wrapper did not pass the requested working directory to the native runner.'
    $ffmpegStarted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_started' -and $_.Data.tool_name -eq 'ffmpeg' })[-1]
    $ffmpegCompleted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Data.tool_name -eq 'ffmpeg' })[-1]
    Assert-Equal ([string]$ffmpegStarted.Data.working_directory) $LocalFailed 'FFmpeg started event did not retain the requested working directory.'
    Assert-Equal ([string]$ffmpegCompleted.Data.working_directory) $LocalFailed 'FFmpeg completed event did not retain the requested working directory.'

    Remove-Item -LiteralPath $LocalFailed -Recurse -Force -ErrorAction SilentlyContinue
} finally {
    Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
}

Write-Host 'FFmpeg/mkvmerge progress checks passed.'
