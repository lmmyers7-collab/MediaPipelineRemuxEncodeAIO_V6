[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Tdarr container stress checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSScriptRoot."
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-ContainsSubsequence {
    param(
        [Parameter(Mandatory)] [array] $Actual,
        [Parameter(Mandatory)] [array] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    for ($idx = 0; $idx -le ($Actual.Count - $Expected.Count); $idx++) {
        $matched = $true
        for ($offset = 0; $offset -lt $Expected.Count; $offset++) {
            if ([string]$Actual[$idx + $offset] -ne [string]$Expected[$offset]) {
                $matched = $false
                break
            }
        }
        if ($matched) { return }
    }
    throw "$Message Missing subsequence '$($Expected -join ' ')'. Actual: $($Actual -join ' ')"
}

function New-StubProbeResult {
    param(
        [string] $Output = '',
        [int] $ExitCode = 0,
        [string] $ErrorText = '',
        [bool] $TimedOut = $false,
        [bool] $Stopped = $false
    )

    return [pscustomobject]@{
        Output   = $Output
        Error    = $ErrorText
        ExitCode = $ExitCode
        TimedOut = $TimedOut
        Stopped  = $Stopped
    }
}

$script:StubProbeQueue = @()
$script:StubProbeStages = @()

function Set-StubProbeResults {
    param([array] $Results)
    $script:StubProbeQueue = @($Results)
    $script:StubProbeStages = @()
}

function Invoke-FFprobeCommand {
    param(
        [array] $ArgumentList,
        [int] $TimeoutSeconds = 30,
        [string] $Stage = ''
    )

    $script:StubProbeStages = @($script:StubProbeStages) + @([pscustomobject]@{
        Stage          = $Stage
        TimeoutSeconds = $TimeoutSeconds
        Arguments      = @($ArgumentList)
    })
    if ($script:StubProbeQueue.Count -eq 0) {
        throw "No stub ffprobe result queued for stage '$Stage'."
    }
    $result = $script:StubProbeQueue[0]
    $script:StubProbeQueue = @($script:StubProbeQueue | Select-Object -Skip 1)
    return $result
}

. (Join-Path $repoRoot 'ops\pipeline\engine\probe\media_probe.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_plan_executor.ps1')

$routeProfileWithVideo = @'
{
  "format": {
    "duration": "30.023",
    "bit_rate": "305694"
  },
  "streams": [
    {
      "index": 0,
      "codec_type": "video",
      "codec_name": "msmpeg4v3",
      "width": 1920,
      "height": 1080
    }
  ]
}
'@

$packetCountMissing = @'
{
  "streams": [
    {}
  ]
}
'@

$packetCountZero = @'
{
  "streams": [
    {
      "nb_read_packets": "0"
    }
  ]
}
'@

$tempSource = [System.IO.Path]::GetTempFileName()
try {
    Set-StubProbeResults @(
        (New-StubProbeResult -Output $routeProfileWithVideo),
        (New-StubProbeResult -Output $packetCountMissing)
    )
    $profile = Get-SourceMediaRouteProfile -FilePath $tempSource -FileSizeBytes 1147233
    Assert-Equal ([bool]$profile.probe_ok) $true 'Missing nb_read_packets should be treated as an ambiguous packet probe, not a missing video stream.'
    Assert-Equal ([string]$profile.probe_error) '' 'Ambiguous packet probe should keep source eligible.'
    Assert-Equal ([string]$profile.video_codec) 'msmpeg4v3' 'Route profile should preserve the source video codec.'
    Assert-Equal ([string]$script:StubProbeStages[1].Stage) 'source-video-packet-probe' 'Packet probe stage mismatch.'

    Set-StubProbeResults @(
        (New-StubProbeResult -Output $routeProfileWithVideo),
        (New-StubProbeResult -Output $packetCountZero)
    )
    $emptyPacketProfile = Get-SourceMediaRouteProfile -FilePath $tempSource -FileSizeBytes 1147233
    Assert-Equal ([bool]$emptyPacketProfile.probe_ok) $false 'Explicit zero video packets should still fail source route probing.'
    Assert-Equal ([string]$emptyPacketProfile.probe_error) 'video_stream_missing' 'Explicit zero packets should remain a video-missing source error.'
} finally {
    if (Test-Path -LiteralPath $tempSource) {
        Remove-Item -LiteralPath $tempSource -Force
    }
}

$remuxText = (@(
        'ops\pipeline\entrypoints\MediaPipeline\remux.ps1',
        'ops\pipeline\engine\process\remux_ffmpeg_av_stage.ps1'
    ) | ForEach-Object {
        Get-Content -LiteralPath (Join-Path $repoRoot $_) -Raw
    }) -join "`n"
Assert-True ($remuxText -match '"-fflags",\s*"\+genpts",\s*"-i",\s*(\$localIn|\$Context\.LocalIn)') 'Production REMUX-AV must synthesize packet timestamps before reading the scratch input.'

$encodePaths = @(
    (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1')
) + @(Get-ChildItem -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process') -Filter 'encode_*.ps1' | ForEach-Object { $_.FullName })
$encodeText = ($encodePaths | ForEach-Object { Get-Content -LiteralPath $_ -Raw }) -join "`n"
Assert-True ($encodeText -match 'Get-MediaPipelineCodeRetryable[\s\S]+-Classification \$failureClassification[\s\S]+Register-SourceFailure') 'Encode failures must classify non-retryable source-media FFmpeg codes as permanent before recording source failure state.'

$processingText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_processing.ps1') -Raw
Assert-True ($processingText -match '\$routeFailureState\s*=\s*Get-SourceFailureState \$file') 'Route failure results must read the source-failure marker before writing worker_result.json.'
Assert-True ($processingText -match '-ErrorCode \$failureErrorCode') 'Route failure worker_result.json must include the recorded source-failure error code.'
Assert-True ($processingText -match '-Retryable:\(\[bool\]\$failureRetryable\)') 'Route failure worker_result.json must project retryability from source-failure state.'
Assert-True ($processingText -match '-QueueTerminal:\(\[bool\]\$failureQueueTerminal\)') 'Route failure worker_result.json must make non-retryable source failures queue-terminal.'

$remuxPlan = [pscustomobject]@{
    routeSummary = 'REMUX'
    streamActions = @(
        [pscustomobject]@{
            streamType = 'video'
            action = 'copy'
            inputCodec = 'h264'
        },
        [pscustomobject]@{
            streamType = 'audio'
            streamIndex = 1
            action = 'copy'
            inputCodec = 'aac'
        }
    )
}
$dryRunRemuxArgs = @(New-PipelinePlanExecutorRemuxAvArgumentList -Plan $remuxPlan -InputPath 'C:\In\source.wmv' -TempAvPath 'C:\Scratch\temp_av.mkv')
Assert-ContainsSubsequence $dryRunRemuxArgs @('-fflags', '+genpts', '-i', 'C:\In\source.wmv') 'Dry-run REMUX-AV command must expose timestamp synthesis before the input path.'

Write-Host 'Tdarr container stress checks passed.'
