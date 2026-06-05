[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot

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
        $Data = $null
    )
    $script:CapturedEvents += ,([pscustomobject]@{
        EventType = $EventType
        Stage = $Stage
        Route = $Route
        Status = $Status
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
} finally {
    Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
}

Write-Host 'FFmpeg/mkvmerge progress checks passed.'
