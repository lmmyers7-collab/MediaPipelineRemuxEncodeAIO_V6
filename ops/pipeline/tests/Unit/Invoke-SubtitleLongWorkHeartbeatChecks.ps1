[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Subtitle long-work heartbeat checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function DebugLog {
    param([string] $Message)
}

$script:HeartbeatProgressCalls = [System.Collections.Generic.List[object]]::new()
function Set-ProgressSubtitleTrack {
    param(
        [string] $Kind,
        [string] $TrackId,
        [int] $StreamIndex,
        [string] $Stage,
        [string] $Status,
        [int] $StepIndex,
        [int] $StepTotal,
        [array] $Steps,
        [string] $Detail,
        $CueCount,
        $WorkNumerator,
        $WorkDenominator,
        [string] $ProgressUnit,
        [string] $OutputCodec,
        [string] $OutputLocation,
        [string] $OutputPath,
        [string] $ParkedPath,
        [string] $IntendedFinalPath,
        [switch] $Completed,
        [switch] $Failed,
        [switch] $SaveNow
    )
    $script:HeartbeatProgressCalls.Add([pscustomobject]@{
        Kind = $Kind
        TrackId = $TrackId
        StreamIndex = $StreamIndex
        Stage = $Stage
        Status = $Status
        Detail = $Detail
        WorkNumerator = $WorkNumerator
        WorkDenominator = $WorkDenominator
        Completed = [bool]$Completed
        Failed = [bool]$Failed
    }) | Out-Null
}

. (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\common.ps1')

$script:PipelineRunId = 'subtitle-heartbeat-run'
$script:CurrentRunMonitorJobId = 'subtitle-heartbeat-run-item-00000001'
$script:CurrentSubtitleEvidenceTrackId = 'subtitle:embedded:2'
$heartbeat = New-SubtitleTrackHeartbeatHandler `
    -Kind 'ass' `
    -TrackId 'subtitle:embedded:2' `
    -StreamIndex 2 `
    -Stage 'convert' `
    -Status 'Converting ASS subtitle to SRT' `
    -StepIndex 2 `
    -StepTotal 4 `
    -Steps @('extract','convert','validate','sidecar_write') `
    -Detail 'English.ass' `
    -MinimumIntervalSeconds 5

Assert-True ($null -ne $heartbeat) 'Exact run/job/track context should create a subtitle heartbeat handler.'
& $heartbeat 0 $null
& $heartbeat 1 $null
& $heartbeat 5 $null
Assert-Equal $script:HeartbeatProgressCalls.Count 2 'Heartbeat writes must be throttled by elapsed tool time.'
Assert-Equal $script:HeartbeatProgressCalls[0].TrackId 'subtitle:embedded:2' 'Heartbeat writes must retain the exact backend track identity.'
Assert-Equal $script:HeartbeatProgressCalls[0].Stage 'convert' 'Heartbeat writes must retain the exact backend stage.'
Assert-True ($null -eq $script:HeartbeatProgressCalls[0].WorkNumerator -and $null -eq $script:HeartbeatProgressCalls[0].WorkDenominator) 'Indeterminate heartbeat writes must not fabricate a numerator or denominator.'
Assert-True (-not $script:HeartbeatProgressCalls[0].Completed -and -not $script:HeartbeatProgressCalls[0].Failed) 'Heartbeat writes must remain active rather than terminal.'

$script:CurrentRunMonitorJobId = 'subtitle-heartbeat-run-item-00000002'
& $heartbeat 10 $null
Assert-Equal $script:HeartbeatProgressCalls.Count 2 'A stale handler must not write after the current backend job identity changes.'
$script:CurrentRunMonitorJobId = 'subtitle-heartbeat-run-item-00000001'

$missingIdentityHeartbeat = New-SubtitleTrackHeartbeatHandler -Kind 'ass' -TrackId '' -StreamIndex 2 -Stage 'convert' -Status 'Working'
Assert-True ($null -eq $missingIdentityHeartbeat) 'Heartbeat creation must fail closed without an exact track identity.'

$script:ActiveOnlyHeartbeatCalls = [System.Collections.Generic.List[object]]::new()
function Update-MediaPipelineRunMonitorActiveTrackHeartbeat {
    param(
        [string] $Kind,
        [string] $RunId,
        [string] $JobId,
        [string] $TrackId,
        [string] $EvidenceSource,
        [string] $EvidenceProvenance
    )
    $script:ActiveOnlyHeartbeatCalls.Add([pscustomobject]@{
        Kind = $Kind
        RunId = $RunId
        JobId = $JobId
        TrackId = $TrackId
        EvidenceSource = $EvidenceSource
        EvidenceProvenance = $EvidenceProvenance
    }) | Out-Null
}
$activeOnlyHeartbeat = New-SubtitleTrackHeartbeatHandler `
    -Kind 'tx3g' `
    -TrackId 'subtitle:embedded:2' `
    -StreamIndex 2 `
    -Stage 'convert' `
    -Status 'Converting TX3G subtitle to SRT' `
    -MinimumIntervalSeconds 5
& $activeOnlyHeartbeat 0 $null
& $activeOnlyHeartbeat 1 $null
& $activeOnlyHeartbeat 5 $null
Assert-Equal $script:ActiveOnlyHeartbeatCalls.Count 2 'Production heartbeat path must retain the same throttle contract.'
Assert-Equal $script:ActiveOnlyHeartbeatCalls[0].Kind 'subtitles' 'Production heartbeat must target the backend subtitle collection.'
Assert-Equal $script:ActiveOnlyHeartbeatCalls[0].RunId 'subtitle-heartbeat-run' 'Production heartbeat must use the captured exact run identity.'
Assert-Equal $script:ActiveOnlyHeartbeatCalls[0].JobId 'subtitle-heartbeat-run-item-00000001' 'Production heartbeat must use the captured exact job identity.'
Assert-Equal $script:ActiveOnlyHeartbeatCalls[0].TrackId 'subtitle:embedded:2' 'Production heartbeat must use the captured exact track identity.'
Assert-Equal $script:ActiveOnlyHeartbeatCalls[0].EvidenceProvenance 'worker_heartbeat' 'Production heartbeat must identify itself as liveness rather than terminal proof.'
Assert-True ($script:ActiveOnlyHeartbeatCalls[0].EvidenceSource -like 'subtitle_tx3g_convert_heartbeat*') 'Production heartbeat evidence must retain its backend subtitle kind/stage context.'
Assert-Equal $script:HeartbeatProgressCalls.Count 2 'Production active-only heartbeat must not rewrite the legacy track action/result payload.'
Remove-Item Function:\Update-MediaPipelineRunMonitorActiveTrackHeartbeat -ErrorAction SilentlyContinue

. (Join-Path $repoRoot 'ops\pipeline\engine\decide\encode_policy_retry.ps1')
$mutexName = 'Local\MediaPipelineSubtitleHeartbeatTest-' + [guid]::NewGuid().ToString('N')
$mutexReady = [System.Threading.ManualResetEventSlim]::new($false)
$mutexRelease = [System.Threading.ManualResetEventSlim]::new($false)
$holder = [powershell]::Create()
$holder.Runspace.SessionStateProxy.SetVariable('MutexName', $mutexName)
$holder.Runspace.SessionStateProxy.SetVariable('MutexReady', $mutexReady)
$holder.Runspace.SessionStateProxy.SetVariable('MutexRelease', $mutexRelease)
$null = $holder.AddScript({
    $heldMutex = [System.Threading.Mutex]::new($false, $MutexName)
    $null = $heldMutex.WaitOne()
    $MutexReady.Set()
    $null = $MutexRelease.Wait(10000)
    $heldMutex.ReleaseMutex()
    $heldMutex.Dispose()
})
$holderAsync = $holder.BeginInvoke()

try {
    Assert-True ($mutexReady.Wait(5000)) 'CPU mutex test holder did not acquire the named mutex.'
    $beforeMutexHeartbeatCount = $script:HeartbeatProgressCalls.Count
    $mutexHeartbeat = New-SubtitleTrackHeartbeatHandler `
        -Kind 'bdpgs' `
        -TrackId 'subtitle:embedded:2' `
        -StreamIndex 2 `
        -Stage 'convert_ocr' `
        -Status 'Waiting for CPU slot for BDPGS OCR' `
        -StepIndex 2 `
        -StepTotal 4 `
        -Steps @('extract','convert_ocr','validate','sidecar_write') `
        -Detail 'English.sup' `
        -MinimumIntervalSeconds 0.05
    $mutexResult = Acquire-CpuEncodeMutex -Name $mutexName -TimeoutSeconds 1 -PollHandler $mutexHeartbeat -PollMilliseconds 50
    Assert-True (-not [bool]$mutexResult.Acquired) 'Held CPU mutex should time out without starting concurrent OCR work.'
    Assert-True ($script:HeartbeatProgressCalls.Count -gt $beforeMutexHeartbeatCount) 'CPU-slot wait must refresh exact active subtitle evidence while blocked.'
    $mutexHeartbeatRows = @($script:HeartbeatProgressCalls | Select-Object -Skip $beforeMutexHeartbeatCount)
    Assert-True (@($mutexHeartbeatRows | Where-Object { $_.Status -eq 'Waiting for CPU slot for BDPGS OCR' }).Count -gt 0) 'CPU-slot heartbeat must identify the wait state without inventing OCR progress.'
    Assert-True (@($mutexHeartbeatRows | Where-Object { $null -ne $_.WorkNumerator -or $null -ne $_.WorkDenominator }).Count -eq 0) 'CPU-slot heartbeats must remain indeterminate.'
} finally {
    $mutexRelease.Set()
    try { $holder.EndInvoke($holderAsync) | Out-Null } catch {}
    $holder.Dispose()
    $mutexReady.Dispose()
    $mutexRelease.Dispose()
}

$script:processingDir = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-subtitle-heartbeat-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $script:processingDir -Force | Out-Null
$script:RemoveKaraoke = $false
$script:ExcludeSubtitleStyles = @()
$script:IncludeSubtitleStyles = @()
$script:ActiveOverrides = $null
$script:MergeAdjacent = $false
$script:MergeThresholdMs = 100
$script:assToSrtScript = 'fake-ass-to-srt.py'
$script:ffmpegPath = 'fake-ffmpeg.exe'

function Get-EffectiveSubtitleSwitch {
    param([string] $Name, [bool] $Default)
    return $Default
}

function New-SrtAtomicTempPath {
    param([string] $DestinationPath)
    return "$DestinationPath.tmp"
}

function Test-SrtFileUsable {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return [pscustomobject]@{ Ok = $false; CueCount = 0; Reason = 'missing' } }
    return [pscustomobject]@{ Ok = $true; CueCount = 1; Reason = 'ok' }
}

function Complete-AtomicSrtWrite {
    param([string] $TempPath, [string] $DestinationPath)
    Move-Item -LiteralPath $TempPath -Destination $DestinationPath -Force
    return [pscustomobject]@{ Ok = $true; CueCount = 1; Reason = 'ok'; Path = $DestinationPath }
}

$script:AssPollCalls = 0
function Invoke-PythonToolCommand {
    param(
        [array] $ArgumentList,
        [int] $TimeoutSeconds,
        [string] $Stage,
        [switch] $SaveReproOnFailure,
        [scriptblock] $PollHandler,
        [int] $PollMilliseconds
    )
    Assert-True ($null -ne $PollHandler) 'ASS conversion must pass its exact heartbeat through the Python wrapper.'
    $script:AssPollMilliseconds = $PollMilliseconds
    & $PollHandler 0 $null
    & $PollHandler 6 $null
    $script:AssPollCalls += 2
    [System.IO.File]::WriteAllText([string]$ArgumentList[3], "1`r`n00:00:00,000 --> 00:00:01,000`r`nASS heartbeat`r`n", [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{ ExitCode = 0; Error = ''; TimedOut = $false; Stopped = $false; ReproPath = '' }
}

function Invoke-FFmpegCommand {
    param(
        [array] $ArgumentList,
        [int] $TimeoutSeconds,
        [string] $Stage,
        [switch] $SaveReproOnFailure,
        [scriptblock] $PollHandler,
        [int] $PollMilliseconds
    )
    Assert-True ($null -ne $PollHandler) 'TX3G conversion must pass its exact heartbeat through the FFmpeg wrapper.'
    $script:Tx3gPollMilliseconds = $PollMilliseconds
    & $PollHandler 0 $null
    & $PollHandler 6 $null
    $script:Tx3gPollCalls += 2
    [System.IO.File]::WriteAllText([string]$ArgumentList[-1], "1`r`n00:00:00,000 --> 00:00:01,000`r`nTX3G heartbeat`r`n", [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{ ExitCode = 0; Error = ''; TimedOut = $false; Stopped = $false; ReproPath = '' }
}

try {
    . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\ass.ps1')
    $assResult = Convert-AssToSrt -SourceFile (Join-Path $script:processingDir 'source.mkv') -StreamIndex 2 -StreamInfo @{ TrackId = 'subtitle:embedded:2'; Stream = [pscustomobject]@{ index = 2 } } -TrackId 'subtitle:embedded:2'
    Assert-True ([bool]$assResult.Ok) "Fake long ASS conversion failed: $($assResult.Reason)"
    Assert-Equal $script:AssPollCalls 2 'ASS fake long-work wrapper must execute the supplied heartbeat handler.'
    Assert-Equal $script:AssPollMilliseconds 250 'ASS conversion must use an explicit bounded native polling cadence.'

    . (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\tx3g.ps1')
    $script:Tx3gPollCalls = 0
    $tx3gDestination = Join-Path $script:processingDir 'tx3g.srt'
    $tx3gResult = Convert-Tx3gToSrt -SourceFile (Join-Path $script:processingDir 'source.mp4') -StreamIndex 3 -StreamInfo @{ TrackId = 'subtitle:embedded:3'; Stream = [pscustomobject]@{ index = 3 } } -DestinationPath $tx3gDestination -TrackId 'subtitle:embedded:3'
    Assert-True ([bool]$tx3gResult.Ok) "Fake long TX3G conversion failed: $($tx3gResult.Reason)"
    Assert-Equal $script:Tx3gPollCalls 2 'TX3G fake long-work wrapper must execute the supplied heartbeat handler.'
    Assert-Equal $script:Tx3gPollMilliseconds 250 'TX3G conversion must use an explicit bounded native polling cadence.'
} finally {
    Remove-Item -LiteralPath $script:processingDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Subtitle long-work heartbeat checks passed.'
