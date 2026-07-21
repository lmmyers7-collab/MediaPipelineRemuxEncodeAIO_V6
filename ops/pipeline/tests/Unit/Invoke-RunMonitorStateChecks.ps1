[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Run Monitor state checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$mutexPath = Join-Path $pipelineRoot 'engine\queue\worker_mutex.ps1'
$nativePath = Join-Path $pipelineRoot 'engine\shared\native.ps1'
$sourceIdentityPath = Join-Path $pipelineRoot 'engine\shared\source_identity.ps1'
$failureStatePath = Join-Path $pipelineRoot 'engine\failures\failure_state.ps1'
$monitorModulePath = Join-Path $pipelineRoot 'engine\status\run_monitor_state.ps1'
$progressModulePath = Join-Path $pipelineRoot 'engine\status\progress_state.ps1'
$phaseExecutorPath = Join-Path $pipelineRoot 'engine\queue\phase_executor.ps1'
$encodeVerificationPath = Join-Path $pipelineRoot 'engine\process\encode_verification.ps1'
$remuxVerificationPath = Join-Path $pipelineRoot 'engine\process\remux_verification.ps1'

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Assert-RunMonitorPythonContract {
    param([Parameter(Mandatory)] [string] $Path)

    $pythonRuntime = Join-Path $repoRoot 'apps\desktop\runtime\Python\python.exe'
    Assert-True (Test-Path -LiteralPath $pythonRuntime -PathType Leaf) 'Bundled Python runtime is missing.'
    $priorPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $repoRoot 'src'
        $validationOutput = @(& $pythonRuntime -c @'
import sys
from pathlib import Path
from mediapipeline.contracts.run_monitor import RunMonitorRecord

RunMonitorRecord.model_validate_json(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
'@ $Path 2>&1)
        $validationExitCode = $LASTEXITCODE
        if ($validationExitCode -ne 0) {
            throw "Serialized Run Monitor failed the Python contract: $($validationOutput -join [Environment]::NewLine)"
        }
    } finally {
        if ($null -eq $priorPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        } else {
            $env:PYTHONPATH = $priorPythonPath
        }
    }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

$script:RunMonitorDebugMessages = [System.Collections.Generic.List[string]]::new()
function DebugLog {
    param([string] $Message)
    $script:RunMonitorDebugMessages.Add([string]$Message)
}

Assert-True (Test-Path -LiteralPath $monitorModulePath -PathType Leaf) 'Run Monitor state module is missing.'
. $mutexPath
. $nativePath
. $sourceIdentityPath
. $failureStatePath
. $monitorModulePath
. $progressModulePath
. $phaseExecutorPath
. $encodeVerificationPath
. $remuxVerificationPath

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-run-monitor-tests-' + [guid]::NewGuid().ToString('N'))
$priorSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
$env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = 'run_monitor_' + [guid]::NewGuid().ToString('N')
try {
    $stateRoot = Join-Path $tempRoot 'State'
    $runMonitorRoot = Join-Path $stateRoot 'RunMonitor'
    $activeJobsRoot = Join-Path $stateRoot 'ActiveJobs'
    $pipelineStateRoot = Join-Path $stateRoot 'Pipeline'
    $LocalFailureMarkers = Join-Path $stateRoot 'FailureMarkers'
    $LocalFailureArtifacts = Join-Path $stateRoot 'FailureArtifacts'
    New-Item -ItemType Directory -Path $runMonitorRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $activeJobsRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $pipelineStateRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $LocalFailureMarkers -Force | Out-Null
    New-Item -ItemType Directory -Path $LocalFailureArtifacts -Force | Out-Null
    $script:LocalStateLayout = [pscustomobject]@{
        Root       = $stateRoot
        RunMonitor = $runMonitorRoot
        ActiveJobs = $activeJobsRoot
        Paths      = [pscustomobject]@{
            RunMonitor = $runMonitorRoot
            StopAfterCurrentFlag = Join-Path $pipelineStateRoot 'pipeline_stop_after_current.flag'
        }
    }
    $LocalBase = $tempRoot
    $script:PipelineRunId = 'run-monitor-test'
    $script:BackendQueueRunMonitorSeedContext = [pscustomobject]@{
        RunId = 'run-monitor-test'
        QueuePlanFingerprint = 'accepted-fingerprint'
    }
    $script:CurrentJobId = ''
    $StopAfterCurrentFlag = [string]$script:LocalStateLayout.Paths.StopAfterCurrentFlag

    $acceptedRows = @(
        [pscustomobject]@{
            run_queue_index = 1
            run_queue_total = 2
            job_id = 'run-monitor-test:item:1'
            source_identity = 'source-a'
            source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\A\Episode.mkv'
            display_name = 'Episode.mkv'
            parent_context = 'C:\Media\A'
            route = 'remux'
            route_reason_code = 'container_only'
            route_reason = 'Container normalization only'
            intended_final_path = 'D:\Library\A\Episode.mkv'
        },
        [pscustomobject]@{
            run_queue_index = 2
            run_queue_total = 2
            job_id = 'run-monitor-test:item:2'
            source_identity = 'source-b'
            source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\B\Episode.mkv'
            display_name = 'Episode.mkv'
            parent_context = 'C:\Media\B'
            route = 'encode'
            route_reason_code = 'video_policy'
            route_reason = 'Video codec requires encode'
            intended_final_path = 'D:\Library\B\Episode.mkv'
        }
    )

    $blankDisplayNameRejected = $false
    try {
        Write-MediaPipelineRunMonitorSeed `
            -RunId 'run-monitor-blank-display-name' `
            -CommandId 'blank-display-name-command' `
            -QueuePlanFingerprint 'blank-display-name-plan' `
            -AcceptedRows @([pscustomobject]@{
                run_queue_index = 1; run_queue_total = 1; job_id = 'run-monitor-blank-display-name:item:1'
                source_identity = 'blank-display-name-source'; source_identity_algorithm = 'source_identity_v2'
                source_path = 'C:\Media\Raw.Release.Name.mkv'; display_name = ''; parent_context = 'C:\Media'
                route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'
            }) | Out-Null
    } catch {
        $blankDisplayNameRejected = ([string]$_ -match 'display_name')
    }
    Assert-True $blankDisplayNameRejected 'Run Monitor seed must reject blank planned display-name evidence instead of substituting the raw source leaf.'

    $seed = Write-MediaPipelineRunMonitorSeed `
        -RunId 'run-monitor-test' `
        -CommandId 'command-test' `
        -QueuePlanFingerprint 'accepted-fingerprint' `
        -AcceptedRows $acceptedRows

    $monitorPath = Join-Path $runMonitorRoot 'run-monitor-test.json'
    $pointerPath = Join-Path $runMonitorRoot 'latest.json'
    Assert-True (Test-Path -LiteralPath $monitorPath -PathType Leaf) 'Run Monitor seed file was not written.'
    Assert-True (Test-Path -LiteralPath $pointerPath -PathType Leaf) 'Run Monitor latest pointer was not written.'
    Assert-Equal $seed.schema_version 'pipeline_run_monitor.v1' 'Run Monitor schema mismatch.'

    $fingerprintedLegacyName = Get-MediaPipelineRunMonitorAcceptedNamingEvidence `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -SourcePath 'C:\Media\A\Episode.mkv'
    Assert-True ([bool]$fingerprintedLegacyName.Applies) 'A fingerprint-backed Backend Queue item must activate accepted-name enforcement.'
    Assert-True (-not [bool]$fingerprintedLegacyName.Verified) 'A fingerprint-backed item without plex_destination_plan.v1 evidence must not be treated as legacy-compatible.'
    Assert-Equal $fingerprintedLegacyName.ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING' 'Missing accepted display-name source must use the stable evidence code.'

    $namingGuardRun = 'run-monitor-naming-guard'
    $namingGuardJob = "$namingGuardRun-item-00000001"
    $namingGuardSource = 'C:\Media\Movies\Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv'
    Write-MediaPipelineRunMonitorSeed `
        -RunId $namingGuardRun `
        -CommandId 'naming-guard-command' `
        -QueuePlanFingerprint 'naming-guard-fingerprint' `
        -AcceptedRows @([pscustomobject]@{
            run_queue_index = 1; run_queue_total = 1; job_id = $namingGuardJob
            source_identity = 'naming-guard-source'; source_identity_algorithm = 'path_size_mtime_sha256.v1'
            source_path = $namingGuardSource; display_name = 'Edge of Tomorrow (2014).mkv'
            display_name_source = 'plex_destination_plan.v1'; parent_context = 'C:\Media\Movies'
            route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'
            intended_final_path = 'D:\Library\Edge of Tomorrow (2014)\Edge of Tomorrow (2014).mkv'
        }) | Out-Null
    $namingGuardPath = Join-Path $runMonitorRoot "$namingGuardRun.json"
    $namingGuardBeforeRead = Get-Content -LiteralPath $namingGuardPath -Raw
    $verifiedNamingEvidence = Get-MediaPipelineRunMonitorAcceptedNamingEvidence `
        -RunId $namingGuardRun `
        -JobId $namingGuardJob `
        -SourcePath $namingGuardSource
    $namingGuardAfterRead = Get-Content -LiteralPath $namingGuardPath -Raw
    Assert-True ([bool]$verifiedNamingEvidence.Applies -and [bool]$verifiedNamingEvidence.Verified) 'Verified Backend Queue accepted-name evidence should apply to execution.'
    Assert-Equal $verifiedNamingEvidence.ExpectedDisplayName 'Edge of Tomorrow (2014).mkv' 'Accepted-name reader returned the wrong immutable filename.'
    Assert-Equal $verifiedNamingEvidence.DisplayNameSource 'plex_destination_plan.v1' 'Accepted-name reader returned the wrong planner source.'
    Assert-Equal $verifiedNamingEvidence.DisplayNameProvenance 'queue_plan' 'Accepted-name reader returned the wrong evidence provenance.'
    Assert-Equal $verifiedNamingEvidence.QueuePlanFingerprint 'naming-guard-fingerprint' 'Accepted-name reader lost the Queue plan fingerprint.'
    Assert-Equal $namingGuardAfterRead $namingGuardBeforeRead 'Accepted-name evidence reader must not rewrite Run Monitor state.'

    $misCorrelatedNamingEvidence = Get-MediaPipelineRunMonitorAcceptedNamingEvidence `
        -RunId $namingGuardRun `
        -JobId $namingGuardJob `
        -SourcePath 'C:\Media\Movies\Different.Source.mkv'
    Assert-True ([bool]$misCorrelatedNamingEvidence.Applies -and -not [bool]$misCorrelatedNamingEvidence.Verified) 'A source-path mismatch must invalidate accepted-name evidence.'
    Assert-Equal $misCorrelatedNamingEvidence.ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING' 'Mis-correlated accepted-name evidence code mismatch.'

    $fingerprintErasedPayload = Get-Content -LiteralPath $namingGuardPath -Raw | ConvertFrom-Json -Depth 40
    $fingerprintErasedPayload.run.accepted_queue.fingerprint = ''
    Set-Content -LiteralPath $namingGuardPath -Value ($fingerprintErasedPayload | ConvertTo-Json -Depth 40) -Encoding UTF8
    $fingerprintErasedEvidence = Get-MediaPipelineRunMonitorAcceptedNamingEvidence `
        -RunId $namingGuardRun `
        -JobId $namingGuardJob `
        -SourcePath $namingGuardSource
    Assert-True ([bool]$fingerprintErasedEvidence.Applies -and -not [bool]$fingerprintErasedEvidence.Verified) 'Erasing a verified accepted Queue fingerprint must fail closed.'
    Assert-True (-not [bool]$fingerprintErasedEvidence.LegacyCompatible) 'An item that still claims plex_destination_plan.v1 evidence must not become legacy-compatible when its fingerprint is erased.'
    Assert-Equal $fingerprintErasedEvidence.ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING' 'Fingerprint erasure must use the stable naming-evidence code.'

    $legacyNamingRun = 'run-monitor-pre-fingerprint-naming'
    $legacyNamingJob = "$legacyNamingRun-item-00000001"
    Write-MediaPipelineRunMonitorSeed `
        -RunId $legacyNamingRun `
        -CommandId 'legacy-naming-command' `
        -QueuePlanFingerprint 'legacy-naming-fingerprint' `
        -AcceptedRows @([pscustomobject]@{
            run_queue_index = 1; run_queue_total = 1; job_id = $legacyNamingJob
            source_identity = 'legacy-naming-source'; source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\Legacy\Movie.mkv'; display_name = 'Movie.mkv'; parent_context = 'C:\Media\Legacy'
            route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'
        }) | Out-Null
    $legacyNamingPath = Join-Path $runMonitorRoot "$legacyNamingRun.json"
    $legacyNamingPayload = Get-Content -LiteralPath $legacyNamingPath -Raw | ConvertFrom-Json -Depth 40
    $legacyNamingPayload.run.accepted_queue.schema_version = 'legacy_queue_plan.v0'
    $legacyNamingPayload.run.accepted_queue.fingerprint = ''
    Set-Content -LiteralPath $legacyNamingPath -Value ($legacyNamingPayload | ConvertTo-Json -Depth 40) -Encoding UTF8
    $legacyNamingEvidence = Get-MediaPipelineRunMonitorAcceptedNamingEvidence `
        -RunId $legacyNamingRun `
        -JobId $legacyNamingJob `
        -SourcePath 'C:\Media\Legacy\Movie.mkv'
    Assert-True (-not [bool]$legacyNamingEvidence.Applies -and [bool]$legacyNamingEvidence.LegacyCompatible) 'Only a pre-fingerprint legacy run may bypass accepted-name enforcement.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$legacyNamingEvidence.ErrorCode)) 'Legacy compatibility must not claim a verified naming failure.'

    # Stop After Current is a separate, correlated dispatch-boundary request.
    # It must never latch the immediate/native-process StopRequested state.
    $launchId = 'run-monitor-launch'
    @{
        schema_version = 'desktop_active_job.v1'; launch_id = $launchId; job_kind = 'pipeline'
        mode = 'once'; status = 'active'; pid = $PID; metadata = @{ run_id = $script:PipelineRunId }
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $activeJobsRoot "$launchId.json") -Encoding UTF8
    $script:StopAfterCurrentRequested = $false
    $script:StopAfterCurrentRequestId = ''
    $script:StopAfterCurrentRequestedAt = ''
    $script:StopRequested = $false
    @{
        schema_version = 'pipeline_control_flag.v1'; action = 'stop_after_current'; label = 'Stop After Current'
        request_id = 'wrong-run-request'; created_at = (Get-Date).ToUniversalTime().ToString('o')
        run_id = 'another-run'; target_pid = $PID; target_launch_id = $launchId
    } | ConvertTo-Json | Set-Content -LiteralPath $StopAfterCurrentFlag -Encoding UTF8
    Assert-True (-not (Test-MediaPipelineStopAfterCurrentBoundary)) 'A mismatched run ID must not stop Queue dispatch.'
    Assert-True (Test-Path -LiteralPath $StopAfterCurrentFlag -PathType Leaf) 'An uncorrelated graceful marker must remain for backend/operator diagnosis.'
    Assert-True (-not [bool]$script:StopAfterCurrentRequested) 'An uncorrelated graceful marker must not latch request state.'

    foreach ($identityCase in @(
        @{ Name = 'blank run ID'; RunId = ''; TargetPid = $PID; TargetLaunchId = $launchId },
        @{ Name = 'blank target PID'; RunId = $script:PipelineRunId; TargetPid = ''; TargetLaunchId = $launchId },
        @{ Name = 'blank launch ID'; RunId = $script:PipelineRunId; TargetPid = $PID; TargetLaunchId = '' }
    )) {
        @{
            schema_version = 'pipeline_control_flag.v1'; action = 'stop_after_current'; label = 'Stop After Current'
            request_id = "incomplete-$($identityCase.Name -replace ' ', '-')"; created_at = (Get-Date).ToUniversalTime().ToString('o')
            run_id = $identityCase.RunId; target_pid = $identityCase.TargetPid; target_launch_id = $identityCase.TargetLaunchId
        } | ConvertTo-Json | Set-Content -LiteralPath $StopAfterCurrentFlag -Encoding UTF8
        Assert-True (-not (Test-MediaPipelineStopAfterCurrentBoundary)) "A monitored Run Once marker with $($identityCase.Name) must not stop Queue dispatch."
        Assert-True (-not [bool]$script:StopAfterCurrentRequested) "A monitored Run Once marker with $($identityCase.Name) must not latch request state."
    }

    @{
        schema_version = 'pipeline_control_flag.v1'; action = 'stop_after_current'; label = 'Stop After Current'
        request_id = 'exact-run-request'; created_at = (Get-Date).ToUniversalTime().ToString('o')
        run_id = $script:PipelineRunId; target_pid = $PID; target_launch_id = $launchId
    } | ConvertTo-Json | Set-Content -LiteralPath $StopAfterCurrentFlag -Encoding UTF8
    Assert-True (Test-MediaPipelineStopAfterCurrentBoundary) 'An exact run/PID/launch marker must stop the next Queue dispatch.'
    Assert-True (-not (Test-Path -LiteralPath $StopAfterCurrentFlag)) 'The exact graceful marker must be removed when its dispatch boundary is acknowledged.'
    Assert-True ([bool]$script:StopAfterCurrentRequested) 'The engine must latch graceful-stop state after exact acknowledgement.'
    Assert-True (-not [bool]$script:StopRequested) 'Stop After Current must never become immediate/native-process interruption.'
    $acknowledged = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $acknowledged.run.lifecycle_state 'stopping' 'The run monitor must expose backend-confirmed graceful stopping.'
    Assert-Equal $acknowledged.run.stop_after_current.state 'acknowledged' 'The run monitor must expose exact dispatch-boundary acknowledgement.'

    # Continuous and Single File runs intentionally have no accepted Backend
    # Queue Run Monitor seed context. They still have a process-local run ID,
    # but their graceful marker must still require exact PID + ActiveJobs
    # launch identity. This preserves those workflows without weakening the
    # three-field correlation required by monitored Backend Queue Run Once.
    $script:StopAfterCurrentRequested = $false
    $script:StopAfterCurrentAcknowledged = $false
    $script:StopAfterCurrentRequestId = ''
    $script:StopAfterCurrentRequestedAt = ''
    $script:PipelineRunId = 'non-monitor-process-run-id'
    $script:BackendQueueRunMonitorSeedContext = $null
    @{
        schema_version = 'pipeline_control_flag.v1'; action = 'stop_after_current'; label = 'Stop After Current'
        request_id = 'exact-process-request'; created_at = (Get-Date).ToUniversalTime().ToString('o')
        run_id = ''; target_pid = $PID; target_launch_id = $launchId
    } | ConvertTo-Json | Set-Content -LiteralPath $StopAfterCurrentFlag -Encoding UTF8
    Assert-True (Test-MediaPipelineStopAfterCurrentBoundary) 'A non-monitor pipeline must honor exact PID/launch Stop After Current evidence.'
    Assert-True (-not (Test-Path -LiteralPath $StopAfterCurrentFlag)) 'The exact non-monitor graceful marker must be acknowledged and removed.'
    $script:PipelineRunId = 'run-monitor-test'
    $script:BackendQueueRunMonitorSeedContext = [pscustomobject]@{
        RunId = 'run-monitor-test'
        QueuePlanFingerprint = 'accepted-fingerprint'
    }
    $script:StopAfterCurrentRequested = $false
    $script:StopAfterCurrentAcknowledged = $false
    $script:StopAfterCurrentRequestId = ''
    $script:StopAfterCurrentRequestedAt = ''

    Set-MediaPipelineRunMonitorRunState -RunId 'run-monitor-test' -State paused | Out-Null
    $pausedRun = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $pausedRun.run.lifecycle_state 'paused' 'Pause control must expose a backend-authored Paused run state.'
    Assert-Equal $pausedRun.run.stop_after_current.state 'acknowledged' 'Pause/resume must not reset an existing Stop After Current acknowledgement.'
    Set-MediaPipelineRunMonitorRunState -RunId 'run-monitor-test' -State running | Out-Null
    $resumedRun = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $resumedRun.run.lifecycle_state 'running' 'Resume control must restore a backend-authored Running run state.'
    Assert-Equal $resumedRun.run.stop_after_current.state 'acknowledged' 'Resume must preserve Stop After Current evidence.'
    Assert-Equal $seed.write_sequence 1 'Initial write sequence mismatch.'
    Assert-Equal @($seed.items).Count 2 'Accepted workload count mismatch.'
    Assert-Equal $seed.run.accepted_queue.schema_version 'queue_plan_fingerprint.v1' 'Queue fingerprint schema mismatch.'
    Assert-Equal $seed.run.accepted_queue.fingerprint 'accepted-fingerprint' 'Accepted fingerprint mismatch.'
    Assert-Equal $seed.items[0].position 1 'Run position 1 mismatch.'
    Assert-Equal $seed.items[1].position 2 'Run position 2 mismatch.'
    Assert-Equal $seed.items[0].total 2 'Run total mismatch.'
    Assert-True ($seed.items[0].job_id -ne $seed.items[1].job_id) 'Duplicate leaf names must retain different job IDs.'
    Assert-Equal @($seed.items[0].stages).Count 13 'Canonical stage ledger must contain 13 stages.'
    Assert-Equal $seed.items[0].stages[0].stage_id 'accepted' 'First stage must be accepted.'
    Assert-Equal $seed.items[0].stages[1].stage_id 'source_discovery' 'Second stage must be source discovery.'
    Assert-Equal $seed.items[0].stages[0].state 'completed' 'Every accepted item must have exact Queue-plan acceptance evidence at seed time.'
    Assert-Equal $seed.items[0].stages[0].evidence.source 'queue_plan_acceptance' 'Accepted-stage authority must name the accepted Queue plan.'
    Assert-Equal $seed.items[0].stages[1].state 'completed' 'Every accepted item must retain completed source-discovery evidence before dispatch.'
    Assert-Equal $seed.items[0].stages[1].evidence.source 'queue_discovery' 'Source-discovery authority must name backend Queue discovery.'
    Assert-Equal $seed.items[1].stages[0].state 'completed' 'Queued items must retain acceptance evidence before they become current.'
    Assert-Equal $seed.items[1].stages[1].state 'completed' 'Queued items must retain source-discovery evidence before they become current.'
    Assert-Equal $seed.items[0].routes.planned.route 'remux' 'Planned route was not preserved.'
    Assert-Equal $seed.items[0].routes.executed.state 'awaiting_evidence' 'Runtime route must not copy planned evidence.'

    $preScanRun = 'run-monitor-pre-scan'
    $preScanRows = @([pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; job_id = "${preScanRun}-item-00000001"
        source_identity = 'pre-scan-source'; source_identity_algorithm = 'path_size_mtime_sha256.v1'
        source_path = 'C:\Media\PreScan.mkv'; display_name = 'PreScan.mkv'; parent_context = 'C:\Media'
        route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'
    })
    Write-MediaPipelineRunMonitorSeed `
        -RunId $preScanRun `
        -CommandId 'pre-scan-command' `
        -QueuePlanFingerprint 'pre-scan-plan' `
        -AcceptedRows $preScanRows `
        -InitialRunState starting `
        -SourceDiscoveryState not_started | Out-Null
    $preScanPath = Join-Path $runMonitorRoot "$preScanRun.json"
    $preScanStarting = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $preScanStarting.run.lifecycle_state 'starting' 'Accepted pre-scan membership must expose Starting before discovery.'
    Assert-Equal $preScanStarting.items[0].stages[1].state 'not_started' 'Starting must not claim source discovery evidence.'
    Set-MediaPipelineRunMonitorSourceDiscoveryState -RunId $preScanRun -State active -RunState scanning | Out-Null
    $preScanScanning = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $preScanScanning.run.lifecycle_state 'scanning' 'Active source discovery must expose Scanning.'
    Assert-Equal $preScanScanning.items[0].stages[1].state 'active' 'Scanning must be backend-authored in the canonical per-file ledger.'

    # Source discovery runs before per-file dispatch, so no CurrentRunMonitorJobId
    # exists yet. Its liveness evidence must instead bind to the exact accepted run
    # and Queue-plan fingerprint, throttle repeated polls, and fail closed after the
    # ambient run changes or a mismatched fingerprint is supplied.
    $script:PipelineRunId = $preScanRun
    $script:CurrentRunMonitorJobId = ''
    $sourceDiscoveryPollHandler = New-MediaPipelineSourceDiscoveryPollHandler `
        -RunId $preScanRun `
        -AcceptedQueueFingerprint 'pre-scan-plan' `
        -MinimumIntervalSeconds 15
    Assert-True ($null -ne $sourceDiscoveryPollHandler) 'Pre-dispatch source discovery must create a run-scoped heartbeat without a job ID.'
    $beforeDiscoveryHeartbeat = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    & $sourceDiscoveryPollHandler 0 $null | Out-Null
    $firstDiscoveryHeartbeat = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $firstDiscoveryHeartbeat.write_sequence ($beforeDiscoveryHeartbeat.write_sequence + 1) 'The first source-discovery poll must persist exact run evidence.'
    Assert-Equal $firstDiscoveryHeartbeat.items[0].stages[1].evidence.source 'source_discovery_heartbeat' 'Source-discovery heartbeat authority mismatch.'
    Assert-Equal $firstDiscoveryHeartbeat.items[0].stages[1].progress.kind 'indeterminate' 'Source discovery must not manufacture numeric progress.'
    Assert-Equal $firstDiscoveryHeartbeat.items[0].stages[1].progress.numerator $null 'Source discovery must not manufacture a numerator.'
    Assert-Equal $firstDiscoveryHeartbeat.items[0].stages[1].progress.denominator $null 'Source discovery must not manufacture a denominator.'
    & $sourceDiscoveryPollHandler 1 $null | Out-Null
    $throttledDiscoveryHeartbeat = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $throttledDiscoveryHeartbeat.write_sequence $firstDiscoveryHeartbeat.write_sequence 'Source-discovery polls inside the interval must be throttled.'
    & $sourceDiscoveryPollHandler 16 $null | Out-Null
    $secondDiscoveryHeartbeat = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $secondDiscoveryHeartbeat.write_sequence ($firstDiscoveryHeartbeat.write_sequence + 1) 'Source-discovery evidence must refresh after the throttle interval.'

    # GetNewClosure creates a dynamic module that cannot resolve functions from
    # this entrypoint-style caller script scope by name. A caught persistence
    # failure must invoke the DebugLog CommandInfo captured by the factory.
    $originalDiscoveryWriter = (Get-Command -Name Set-MediaPipelineRunMonitorSourceDiscoveryState -ErrorAction Stop).ScriptBlock
    $originalDebugLog = (Get-Command -Name DebugLog -ErrorAction Stop).ScriptBlock
    $debugCountBeforeDiscoveryFailure = $script:RunMonitorDebugMessages.Count
    try {
        Set-Item -LiteralPath Function:\Set-MediaPipelineRunMonitorSourceDiscoveryState -Value {
            param($RunId, $State, $RunState, $ExpectedQueuePlanFingerprint, $EvidenceSource)
            throw 'forced source-discovery persistence failure'
        }
        $failingDiscoveryPollHandler = New-MediaPipelineSourceDiscoveryPollHandler `
            -RunId $preScanRun `
            -AcceptedQueueFingerprint 'pre-scan-plan' `
            -MinimumIntervalSeconds 0
        Remove-Item -LiteralPath Function:\DebugLog
        & $failingDiscoveryPollHandler 0 $null | Out-Null
    } finally {
        Set-Item -LiteralPath Function:\DebugLog -Value $originalDebugLog
        Set-Item -LiteralPath Function:\Set-MediaPipelineRunMonitorSourceDiscoveryState -Value $originalDiscoveryWriter
    }
    Assert-Equal $script:RunMonitorDebugMessages.Count ($debugCountBeforeDiscoveryFailure + 1) 'A source-discovery persistence failure must remain observable from a closed callback.'
    Assert-True ($script:RunMonitorDebugMessages[-1] -match 'forced source-discovery persistence failure') 'Source-discovery callback diagnostics must preserve the writer failure reason.'

    $mismatchedFingerprintHandler = New-MediaPipelineSourceDiscoveryPollHandler `
        -RunId $preScanRun `
        -AcceptedQueueFingerprint 'wrong-plan' `
        -MinimumIntervalSeconds 0
    & $mismatchedFingerprintHandler 0 $null | Out-Null
    $afterFingerprintMismatch = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $afterFingerprintMismatch.write_sequence $secondDiscoveryHeartbeat.write_sequence 'A mismatched accepted Queue fingerprint must not write discovery evidence.'

    $script:PipelineRunId = 'another-run'
    & $sourceDiscoveryPollHandler 32 $null | Out-Null
    $afterRunMismatch = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $afterRunMismatch.write_sequence $secondDiscoveryHeartbeat.write_sequence 'A late source-discovery callback must fail closed after the current run changes.'
    $script:PipelineRunId = $preScanRun
    Set-MediaPipelineRunMonitorSourceDiscoveryState -RunId $preScanRun -State completed -RunState running | Out-Null
    $preScanRunning = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $preScanRunning.run.lifecycle_state 'running' 'A matching active rescan must advance the accepted run to Running.'
    Assert-Equal $preScanRunning.items[0].stages[1].state 'completed' 'A matching active rescan must explicitly complete source discovery.'
    & $sourceDiscoveryPollHandler 48 $null | Out-Null
    $afterCompletedDiscoveryCallback = Get-Content -LiteralPath $preScanPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $afterCompletedDiscoveryCallback.write_sequence $preScanRunning.write_sequence 'A same-run late heartbeat must not reopen completed source discovery.'
    Assert-Equal $afterCompletedDiscoveryCallback.run.lifecycle_state 'running' 'A same-run late heartbeat must not move a running workload back to Scanning.'
    Assert-Equal $afterCompletedDiscoveryCallback.items[0].stages[1].state 'completed' 'A same-run late heartbeat must preserve terminal source-discovery evidence.'
    $script:PipelineRunId = 'run-monitor-test'
    $script:CurrentRunMonitorJobId = 'run-monitor-test:item:1'
    Set-MediaPipelineCurrentRunMonitorOutput `
        -State active `
        -ScratchPath 'C:\Scratch\RunMonitor\Episode.mkv' `
        -WorkingOutputPath 'C:\Scratch\RunMonitor\Episode.work.mkv' `
        -IntendedFinalPath 'D:\Library\A\Episode.mkv' `
        -VerificationState not_started | Out-Null
    $activePathEvidence = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[0].output
    Assert-Equal $activePathEvidence.state 'active' 'Current output evidence must expose an active backend-owned path state.'
    Assert-Equal $activePathEvidence.scratch_path 'C:\Scratch\RunMonitor\Episode.mkv' 'Current scratch path must come from exact backend runtime evidence.'
    Assert-Equal $activePathEvidence.working_output_path 'C:\Scratch\RunMonitor\Episode.work.mkv' 'Current working output path must come from exact backend runtime evidence.'
    Assert-Equal $activePathEvidence.intended_final_path 'D:\Library\A\Episode.mkv' 'Intended final path must remain distinct from the current working output.'

    $allDropRun = 'run-monitor-all-drop-policy'
    Write-MediaPipelineRunMonitorSeed -RunId $allDropRun -CommandId 'all-drop-command' -QueuePlanFingerprint 'all-drop-plan' -AcceptedRows @([pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; job_id = "${allDropRun}:item:1"
        source_identity = 'all-drop-source'; source_identity_algorithm = 'source_identity_v2'
        source_path = 'C:\Media\AllDrop.mkv'; display_name = 'AllDrop.mkv'; parent_context = 'C:\Media'
        route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'; intended_final_path = 'D:\Library\AllDrop.mkv'
    }) | Out-Null
    Set-MediaPipelineRunMonitorAudioRecords -RunId $allDropRun -JobId "${allDropRun}:item:1" -FinalPolicy -Records @([pscustomobject]@{
        source_stream_index = 1; action = 'drop'; planned_action = 'drop'; language = 'eng'; source_codec = 'aac'
        source_channels = 2; source_layout = 'stereo'; reason = 'file override'; reason_code = 'file_override_drop'
    }) | Out-Null
    Set-MediaPipelineRunMonitorSubtitleRecords -RunId $allDropRun -JobId "${allDropRun}:item:1" -FinalPolicy -Records @([pscustomobject]@{
        TrackId = 'subtitle:embedded:2'; Action = 'Drop'; PlannedAction = 'drop'; Drop = $true
        Entry = @{ Lang = 'eng'; Codec = 'subrip'; Stream = [pscustomobject]@{ index = 2 }; SubtitleOrdinal = 0; SourceKind = 'embedded' }
        PreserveOriginal = $false; SourceType = 'text'; SourceKind = 'embedded'; PolicyReason = 'explicit backend drop policy'
    }) | Out-Null
    $allDropItem = (Get-Content -LiteralPath (Join-Path $runMonitorRoot "$allDropRun.json") -Raw | ConvertFrom-Json -Depth 40).items[0]
    Assert-Equal $allDropItem.audio.state 'completed' 'A final all-drop audio policy must be explicit, not awaiting evidence.'
    Assert-Equal $allDropItem.audio.tracks[0].state 'dropped' 'An explicitly dropped audio track must retain dropped state.'
    Assert-Equal (@($allDropItem.stages | Where-Object stage_id -eq audio)[0]).state 'completed' 'A final all-drop audio policy must close the canonical Audio stage.'
    Assert-Equal $allDropItem.subtitles.state 'completed' 'A final all-drop subtitle policy must be explicit, not awaiting evidence.'
    Assert-Equal $allDropItem.subtitles.tracks[0].state 'dropped' 'An explicitly dropped subtitle track must retain dropped state.'
    Assert-Equal (@($allDropItem.stages | Where-Object stage_id -eq subtitles)[0]).state 'completed' 'A final all-drop subtitle policy must close the canonical Subtitles stage.'

    # Mirror Build-AudioArgs policy progress for a normal mixed workload. The
    # policy pass decides planned actions; it does not prove copy/transcode
    # execution. Its aggregate completion must close only the Audio policy
    # stage and leave runtime outcomes awaiting correlated evidence.
    $mixedAudioRun = 'run-monitor-mixed-audio-policy'
    $mixedAudioJob = "${mixedAudioRun}:item:1"
    Write-MediaPipelineRunMonitorSeed -RunId $mixedAudioRun -CommandId 'mixed-audio-command' -QueuePlanFingerprint 'mixed-audio-plan' -AcceptedRows @([pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; job_id = $mixedAudioJob
        source_identity = 'mixed-audio-source'; source_identity_algorithm = 'source_identity_v2'
        source_path = 'C:\Media\MixedAudio.mkv'; display_name = 'MixedAudio.mkv'; parent_context = 'C:\Media'
        route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'; intended_final_path = 'D:\Library\MixedAudio.mkv'
    }) | Out-Null
    $script:PipelineRunId = $mixedAudioRun
    $script:CurrentRunMonitorJobId = $mixedAudioJob
    Set-MediaPipelineRunMonitorAudioRecords -RunId $mixedAudioRun -JobId $mixedAudioJob -FinalPolicy -Records @(
        [pscustomobject]@{
            source_stream_index = 0; action = 'drop'; language = 'jpn'; source_codec = 'aac'
            source_channels = 2; source_layout = 'stereo'; reason = 'file override'; reason_code = 'file_override_drop'
        }
        [pscustomobject]@{
            source_stream_index = 1; action = 'copy'; language = 'eng'; source_codec = 'eac3'
            source_channels = 6; source_layout = '5.1'; output_codec = 'eac3'; output_channels = 6; output_layout = '5.1'
            reason = 'compatible codec'; reason_code = 'codec_passthrough'
        }
        [pscustomobject]@{
            source_stream_index = 2; action = 'transcode'; language = 'spa'; source_codec = 'truehd'
            source_channels = 8; source_layout = '7.1'; output_codec = 'eac3'; output_channels = 6; output_layout = '5.1'
            reason = 'profile transcode policy'; reason_code = 'profile_transcode'
        }
    ) | Out-Null
    Set-ProgressAudioTrack -StreamIndex 0 -Stage 'audio_policy' -Status 'Audio stream 0 dropped by backend policy' -AudioAction drop -SourceCodec aac -SourceChannels 2 -Language jpn -Reason 'file override' -StepIndex 1 -StepTotal 3
    Set-ProgressAudioTrack -StreamIndex 1 -Stage 'audio_policy' -Status 'Audio stream 1 will be passed through' -AudioAction copy -SourceCodec eac3 -SourceChannels 6 -OutputCodec eac3 -OutputChannels 6 -Language eng -Reason 'compatible codec' -StepIndex 2 -StepTotal 3
    Set-ProgressAudioTrack -StreamIndex 2 -Stage 'audio_policy' -Status 'Audio stream 2 will be transcoded' -AudioAction transcode -SourceCodec truehd -SourceChannels 8 -OutputCodec eac3 -OutputChannels 6 -Language spa -Reason 'profile transcode policy' -StepIndex 3 -StepTotal 3

    $mixedAudioPath = Join-Path $runMonitorRoot "$mixedAudioRun.json"
    Assert-RunMonitorPythonContract -Path $mixedAudioPath
    $policyInProgress = Get-Content -LiteralPath $mixedAudioPath -Raw | ConvertFrom-Json -Depth 40
    $policyTracks = @($policyInProgress.items[0].audio.tracks)
    Assert-Equal $policyTracks[0].state 'dropped' 'A policy-authored drop must be terminal without claiming track work.'
    Assert-Equal $policyTracks[0].progress.kind 'none' 'A policy-authored drop must not be indeterminate.'
    Assert-Equal $policyTracks[1].state 'awaiting_evidence' 'A policy-authored passthrough decision must not claim execution.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$policyTracks[1].current_action)) 'A policy-authored passthrough decision must not claim a current action.'
    Assert-Equal $policyTracks[1].progress.kind 'none' 'A policy-authored passthrough decision must not claim progress.'
    Assert-Equal $policyTracks[2].state 'awaiting_evidence' 'A policy-authored transcode decision must not claim execution.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$policyTracks[2].current_action)) 'A policy-authored transcode decision must not claim a current action.'
    Assert-Equal $policyTracks[2].progress.kind 'none' 'A policy-authored transcode decision must not claim progress.'
    Assert-Equal (@($policyInProgress.items[0].stages | Where-Object stage_id -eq audio)[0]).state 'active' 'The canonical Audio stage may show backend policy evaluation as active.'
    Set-ProgressAudioTrack -Stage 'audio_policy' -Status 'Audio policy complete' -AudioAction transcode -StepIndex 3 -StepTotal 3 -Detail 'tracks 2; default stream 0' -Completed

    Assert-RunMonitorPythonContract -Path $mixedAudioPath
    $mixedAudioMonitor = Get-Content -LiteralPath $mixedAudioPath -Raw | ConvertFrom-Json -Depth 40
    $mixedAudioItem = $mixedAudioMonitor.items[0]
    $mixedAudioTracks = @($mixedAudioItem.audio.tracks)
    Assert-Equal $mixedAudioItem.audio.state 'awaiting_evidence' 'Policy completion must not claim runtime audio completion.'
    Assert-Equal $mixedAudioTracks[0].state 'dropped' 'Backend policy must retain the explicitly dropped track.'
    Assert-Equal $mixedAudioTracks[0].current_action 'drop' 'The explicit drop action must remain visible.'
    Assert-Equal $mixedAudioTracks[0].progress.kind 'none' 'A dropped track must not retain indeterminate progress.'
    Assert-Equal $mixedAudioTracks[1].planned_action 'passthrough' 'Copy policy must retain its planned passthrough action.'
    Assert-Equal $mixedAudioTracks[1].state 'awaiting_evidence' 'Passthrough must await runtime or terminal evidence after policy completion.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$mixedAudioTracks[1].current_action)) 'Policy-only passthrough must not claim a current runtime action.'
    Assert-Equal $mixedAudioTracks[1].progress.kind 'none' 'Policy-only passthrough must not manufacture progress.'
    Assert-Equal $mixedAudioTracks[2].planned_action 'transcode' 'Transcode policy must retain its planned action.'
    Assert-Equal $mixedAudioTracks[2].state 'awaiting_evidence' 'Transcode must await runtime or terminal evidence after policy completion.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$mixedAudioTracks[2].current_action)) 'Policy-only transcode must not claim a current runtime action.'
    Assert-Equal $mixedAudioTracks[2].progress.kind 'none' 'Policy-only transcode must not manufacture progress.'
    $mixedAudioStage = @($mixedAudioItem.stages | Where-Object stage_id -eq audio)[0]
    Assert-Equal $mixedAudioStage.state 'completed' 'Aggregate policy completion must close the canonical Audio stage.'
    Assert-Equal $mixedAudioStage.progress.kind 'none' 'Completed Audio policy must not retain determinate or indeterminate progress.'
    Assert-Equal @($mixedAudioMonitor.current_workers | Where-Object job_id -eq $mixedAudioJob).Count 0 'Completed Audio policy must not retain a current worker claim.'

    # The correlated media process, not policy text, owns runtime audio work.
    # All non-drop tracks execute in the same FFmpeg media-time domain, so a
    # truthful FFmpeg numerator/denominator applies to each active track.
    Set-MediaPipelineRunMonitorStage `
        -RunId $mixedAudioRun `
        -JobId $mixedAudioJob `
        -StageId transcode `
        -State active `
        -Detail 'Correlated FFmpeg transcode is active.' `
        -EvidenceSource 'ffmpeg_process' `
        -Indeterminate | Out-Null
    Start-MediaPipelineRunMonitorAudioWork `
        -RunId $mixedAudioRun `
        -JobId $mixedAudioJob `
        -EvidenceSource 'ffmpeg_process_start' `
        -Detail 'Correlated FFmpeg audio work started.' | Out-Null
    Assert-RunMonitorPythonContract -Path $mixedAudioPath
    $audioWorkStarted = Get-Content -LiteralPath $mixedAudioPath -Raw | ConvertFrom-Json -Depth 40
    $activeAudioTracks = @($audioWorkStarted.items[0].audio.tracks)
    Assert-Equal $audioWorkStarted.items[0].audio.state 'active' 'Correlated FFmpeg start must activate the audio collection.'
    Assert-Equal $activeAudioTracks[0].state 'dropped' 'Runtime audio start must not reopen a policy-terminal drop.'
    Assert-Equal $activeAudioTracks[1].state 'active' 'Passthrough must become current only when correlated media work starts.'
    Assert-Equal $activeAudioTracks[1].current_action 'passthrough' 'Runtime passthrough must expose the backend-planned action.'
    Assert-Equal $activeAudioTracks[1].progress.kind 'indeterminate' 'Newly started passthrough work must be indeterminate before tool progress.'
    Assert-Equal $activeAudioTracks[2].state 'active' 'Transcode must become current only when correlated media work starts.'
    Assert-Equal $activeAudioTracks[2].current_action 'transcode' 'Runtime transcode must expose the backend-planned action.'
    Assert-Equal $activeAudioTracks[2].progress.kind 'indeterminate' 'Newly started transcode work must be indeterminate before tool progress.'
    Assert-Equal (@($audioWorkStarted.items[0].stages | Where-Object stage_id -eq audio)[0]).state 'completed' 'Runtime stream work must not reopen the completed Audio policy stage.'
    Assert-Equal @($audioWorkStarted.items[0].stages | Where-Object state -eq active).Count 1 'Concurrent per-track evidence must retain exactly one canonical active stage.'
    Assert-Equal @($audioWorkStarted.items[0].stages | Where-Object state -eq active)[0].stage_id 'transcode' 'The correlated media process must remain the canonical current stage.'

    Update-MediaPipelineRunMonitorActiveTrackHeartbeat `
        -Kind audio `
        -RunId $mixedAudioRun `
        -JobId $mixedAudioJob `
        -EvidenceSource 'ffmpeg_progress' `
        -EvidenceProvenance backend_confirmed `
        -Numerator 35 `
        -Denominator 100 | Out-Null
    Assert-RunMonitorPythonContract -Path $mixedAudioPath
    $audioWorkProgress = Get-Content -LiteralPath $mixedAudioPath -Raw | ConvertFrom-Json -Depth 40
    foreach ($activeTrack in @($audioWorkProgress.items[0].audio.tracks | Where-Object state -eq active)) {
        Assert-Equal $activeTrack.progress.kind 'determinate' 'FFmpeg media-time progress must remain determinate for each active audio track.'
        Assert-Equal $activeTrack.progress.numerator 35 'Active audio track progress numerator changed.'
        Assert-Equal $activeTrack.progress.denominator 100 'Active audio track progress denominator changed.'
    }

    End-MediaPipelineRunMonitorAudioWorkAttempt `
        -RunId $mixedAudioRun `
        -JobId $mixedAudioJob `
        -EvidenceSource 'ffmpeg_process_exit' `
        -ReasonCode 'NVENC_SESSION_FAILED' `
        -Detail 'Hardware attempt ended before the backend entered CPU fallback wait.' | Out-Null
    Assert-RunMonitorPythonContract -Path $mixedAudioPath
    $audioAttemptEnded = Get-Content -LiteralPath $mixedAudioPath -Raw | ConvertFrom-Json -Depth 40
    $endedAudioTracks = @($audioAttemptEnded.items[0].audio.tracks)
    Assert-Equal $audioAttemptEnded.items[0].audio.state 'unknown' 'A failed native attempt must clear active audio collection state before fallback wait.'
    foreach ($endedTrack in @($endedAudioTracks | Where-Object state -ne dropped)) {
        Assert-Equal $endedTrack.state 'unknown' 'A failed native attempt must leave nonterminal audio work explicitly unknown between processes.'
        Assert-True ([string]::IsNullOrWhiteSpace([string]$endedTrack.current_action)) 'A process that has exited must not remain the current audio action.'
        Assert-True ([string]::IsNullOrWhiteSpace([string]$endedTrack.started_at)) 'A process that has exited must not retain a live elapsed-time origin.'
        Assert-Equal $endedTrack.progress.kind 'none' 'A process that has exited must not retain active audio progress.'
        Assert-True ([string]$endedTrack.result -like 'NVENC_SESSION_FAILED:*') 'Attempt-end evidence must retain the exact backend reason without becoming terminal policy proof.'
    }
    Assert-Equal @($audioAttemptEnded.items[0].stages | Where-Object state -eq active).Count 1 'Attempt cleanup must not manufacture or replace a canonical active stage.'

    Start-MediaPipelineRunMonitorAudioWork `
        -RunId $mixedAudioRun `
        -JobId $mixedAudioJob `
        -EvidenceSource 'ffmpeg_cpu_process_start' `
        -Detail 'Correlated CPU fallback audio work started.' | Out-Null
    Assert-RunMonitorPythonContract -Path $mixedAudioPath
    $audioFallbackStarted = Get-Content -LiteralPath $mixedAudioPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $audioFallbackStarted.items[0].audio.state 'active' 'A later exact Process.Start must reactivate unknown retryable audio work.'
    Assert-Equal @($audioFallbackStarted.items[0].audio.tracks | Where-Object state -eq active).Count 2 'CPU fallback must reactivate every nonterminal backend-planned audio track exactly once.'

    Complete-MediaPipelineRunMonitorAudioWork `
        -RunId $mixedAudioRun `
        -JobId $mixedAudioJob `
        -EvidenceSource 'ffmpeg_process_exit' `
        -Detail 'Correlated FFmpeg audio work completed.' | Out-Null
    Assert-RunMonitorPythonContract -Path $mixedAudioPath
    $audioWorkCompleted = Get-Content -LiteralPath $mixedAudioPath -Raw | ConvertFrom-Json -Depth 40
    $completedAudioTracks = @($audioWorkCompleted.items[0].audio.tracks)
    Assert-Equal $audioWorkCompleted.items[0].audio.state 'completed' 'Successful correlated FFmpeg exit must complete the audio collection.'
    Assert-Equal $completedAudioTracks[0].state 'dropped' 'Runtime completion must preserve a policy-terminal drop.'
    Assert-Equal $completedAudioTracks[1].state 'completed' 'Successful FFmpeg exit must complete passthrough work.'
    Assert-Equal $completedAudioTracks[1].current_action 'passthrough' 'Completed passthrough must retain its executed action.'
    Assert-Equal $completedAudioTracks[1].progress.kind 'none' 'Completed passthrough must not retain a stale percentage.'
    Assert-Equal $completedAudioTracks[2].state 'completed' 'Successful FFmpeg exit must complete transcode work.'
    Assert-Equal $completedAudioTracks[2].current_action 'transcode' 'Completed transcode must retain its executed action.'
    Assert-Equal $completedAudioTracks[2].progress.kind 'none' 'Completed transcode must not retain a stale percentage.'
    Assert-Equal (@($audioWorkCompleted.items[0].stages | Where-Object stage_id -eq audio)[0]).state 'completed' 'Runtime completion must preserve the completed Audio policy stage.'
    Assert-Equal @($audioWorkCompleted.items[0].stages | Where-Object state -eq active).Count 1 'Audio completion must not supersede the still-active media process stage.'

    $script:PipelineRunId = 'run-monitor-test'
    $script:CurrentRunMonitorJobId = 'run-monitor-test:item:1'

    # Terminal route/output claims must come from an artifact whose durable
    # run and job identities both match the accepted monitor item exactly.
    $completedProofPath = Join-Path $tempRoot 'completed-a.pipeline.json'
    @{
        schema_version = 'pipeline_sidecar.v1'; correlation_id = 'run-monitor-test'
        run_monitor_job_id = 'run-monitor-test:item:1'; route = 'encode_cpu_fallback'
        route_reason_code = 'hardware_unavailable'; route_reason = 'CPU fallback completed.'
        output_path = 'D:\Library\A\Episode.mkv'
    } | ConvertTo-Json | Set-Content -LiteralPath $completedProofPath -Encoding UTF8
    $completedProof = Resolve-MediaPipelineRunMonitorTerminalArtifact `
        -Lifecycle completed `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -PipelineSidecarPath $completedProofPath
    Assert-True ([bool]$completedProof.Verified) 'An exactly correlated Completed sidecar must be accepted as terminal proof.'
    Assert-Equal $completedProof.Kind 'completed' 'Completed terminal proof kind mismatch.'
    Assert-Equal $completedProof.Route 'encode_cpu_fallback' 'Completed final route must come from the sidecar.'
    Assert-Equal $completedProof.PublishedPath 'D:\Library\A\Episode.mkv' 'Completed output path must come from the sidecar.'

    $mismatchedProofPath = Join-Path $tempRoot 'mismatched.pipeline.json'
    @{
        schema_version = 'pipeline_sidecar.v1'; correlation_id = 'another-run'
        run_monitor_job_id = 'run-monitor-test:item:1'; route = 'remux'
        output_path = 'D:\Library\Wrong.mkv'
    } | ConvertTo-Json | Set-Content -LiteralPath $mismatchedProofPath -Encoding UTF8
    $mismatchedProof = Resolve-MediaPipelineRunMonitorTerminalArtifact `
        -Lifecycle completed `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -PipelineSidecarPath $mismatchedProofPath
    Assert-True (-not [bool]$mismatchedProof.Verified) 'A sidecar from a different run must not prove terminal state.'
    Assert-Equal $mismatchedProof.ReasonCode 'terminal_artifact_correlation_mismatch' 'Correlation mismatch must fail honestly.'

    $pendingProofPath = Join-Path $tempRoot 'pending-a.manifest.json'
    @{
        schema_version = 'pending_push_manifest.v1'; run_id = 'run-monitor-test'
        run_monitor_job_id = 'run-monitor-test:item:1'; manifest_state = 'parked'
        route = 'encode_cpu_fallback'; route_reason_code = 'destination_unavailable'
        route_reason = 'Destination unavailable; verified output parked.'
        local_file = 'C:\Scratch\Pending\Episode.mkv'; server_out = 'D:\Library\A\Episode.mkv'
    } | ConvertTo-Json | Set-Content -LiteralPath $pendingProofPath -Encoding UTF8
    $pendingProof = Resolve-MediaPipelineRunMonitorTerminalArtifact `
        -Lifecycle parked `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -ManifestPath $pendingProofPath
    Assert-True ([bool]$pendingProof.Verified) 'An exactly correlated Pending Publish manifest must be accepted.'
    Assert-Equal $pendingProof.ParkedPath 'C:\Scratch\Pending\Episode.mkv' 'Parked path must come from the manifest.'
    Assert-Equal $pendingProof.IntendedFinalPath 'D:\Library\A\Episode.mkv' 'Intended final path must come from the manifest.'

    $failureProofPath = Join-Path $tempRoot 'failure-a.json'
    @{
        schema_version = 'failure_record.v1'; correlation_id = 'run-monitor-test'
        run_monitor_job_id = 'run-monitor-test:item:1'; final_route = 'encode_hardware'
        final_reason_code = 'verification_failed'; final_reason = 'Output verification failed.'
        suggested_action = 'Inspect verification evidence and retry.'
    } | ConvertTo-Json | Set-Content -LiteralPath $failureProofPath -Encoding UTF8
    $failureProof = Resolve-MediaPipelineRunMonitorTerminalArtifact `
        -Lifecycle failed `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -FailureArtifactPath $failureProofPath
    Assert-True ([bool]$failureProof.Verified) 'An exactly correlated failure record must be accepted.'
    Assert-Equal $failureProof.Route 'encode_hardware' 'Failure final route must come from the failure artifact.'
    Assert-Equal $failureProof.NextAction 'Inspect verification evidence and retry.' 'Failure recovery guidance must come from terminal evidence.'

    $preRouteRun = 'run-monitor-pre-route-failure'
    $preRouteSourcePath = Join-Path $tempRoot 'pre-route-failure.mkv'
    Set-Content -LiteralPath $preRouteSourcePath -Value 'not real media' -Encoding UTF8
    $preRouteJobId = "${preRouteRun}:item:1"
    Write-MediaPipelineRunMonitorSeed -RunId $preRouteRun -CommandId 'pre-route-command' -QueuePlanFingerprint 'pre-route-plan' -AcceptedRows @(
        [pscustomobject]@{
            run_queue_index = 1; run_queue_total = 1; job_id = $preRouteJobId
            source_identity = 'pre-route-source'; source_identity_algorithm = 'source_identity_v2'
            source_path = $preRouteSourcePath; display_name = 'pre-route-failure.mkv'; parent_context = $tempRoot
            route = 'encode'; route_reason_code = 'planned'; route_reason = 'Planned encode'; intended_final_path = 'D:\Library\pre-route-failure.mkv'
        }
    ) | Out-Null
    $preRouteSourceFile = Get-Item -LiteralPath $preRouteSourcePath
    $preRouteFailurePath = Get-SourceFailureMarkerPath -SourceFile $preRouteSourceFile
    @{
        schema_version = 'failure_record.v1'; correlation_id = $preRouteRun; run_monitor_job_id = $preRouteJobId
        reason = 'Source probe failed before a runtime route could be selected.'; error_code = 'SOURCE_PROBE_FAILED'
        suggested_action = 'Inspect the source probe failure and retry.'
    } | ConvertTo-Json | Set-Content -LiteralPath $preRouteFailurePath -Encoding UTF8
    $previousPipelineRunId = [string]$script:PipelineRunId
    $script:PipelineRunId = $preRouteRun
    try {
        Complete-MediaPipelineRunMonitorQueueEntry `
            -Entry ([pscustomobject]@{ RunMonitorJobId = $preRouteJobId; File = $preRouteSourceFile }) `
            -Result ([pscustomobject]@{
                Status = 'failed'; Success = $false; PublishState = ''; Route = ''; RouteReasonCode = ''; RouteReason = ''
                Reason = 'Source probe failed.'; ErrorCode = 'SOURCE_PROBE_FAILED'; OutputPath = ''; OutputSizeBytes = 0
                SidecarPaths = @('C:\Scratch\unproven-result-sidecar.srt')
            })
    } finally {
        $script:PipelineRunId = $previousPipelineRunId
    }
    $preRouteMonitor = Get-Content -LiteralPath (Join-Path $runMonitorRoot "$preRouteRun.json") -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $preRouteMonitor.items[0].lifecycle_state 'failed' 'An exactly correlated pre-route failure artifact must terminalize the item.'
    Assert-Equal $preRouteMonitor.items[0].routes.final.state 'unknown' 'A verified pre-route failure must explicitly close Final route as unknown.'
    Assert-Equal $preRouteMonitor.items[0].routes.final.reason_code 'SOURCE_PROBE_FAILED' 'Unknown Final route must preserve the terminal artifact reason code.'
    Assert-Equal $preRouteMonitor.items[0].routes.final.evidence.source 'failure_artifact' 'Unknown Final route must name the exact terminal authority.'
    Assert-Equal @($preRouteMonitor.items[0].output.sidecars).Count 0 'Unproven ProcessResult sidecar paths must not inherit failure-artifact terminal provenance.'
    Assert-True `
        (@($preRouteMonitor.items[0].terminal_references | Where-Object { $_.kind -eq 'failure' -and $_.path -eq $preRouteFailurePath }).Count -eq 1) `
        ("Failed terminal proof must link the exact production failure marker JSON path. Expected '{0}', actual: {1}" -f $preRouteFailurePath, ($preRouteMonitor.items[0].terminal_references | ConvertTo-Json -Compress -Depth 8))

    $reviewRun = 'run-monitor-production-review-marker'
    $reviewSourcePath = Join-Path $tempRoot 'subtitle-review.mkv'
    Set-Content -LiteralPath $reviewSourcePath -Value 'not real media' -Encoding UTF8
    $reviewSourceFile = Get-Item -LiteralPath $reviewSourcePath
    $reviewJobId = "${reviewRun}:item:1"
    Write-MediaPipelineRunMonitorSeed -RunId $reviewRun -CommandId 'review-command' -QueuePlanFingerprint 'review-plan' -AcceptedRows @(
        [pscustomobject]@{
            run_queue_index = 1; run_queue_total = 1; job_id = $reviewJobId
            source_identity = 'review-source'; source_identity_algorithm = 'source_identity_v2'
            source_path = $reviewSourcePath; display_name = 'subtitle-review.mkv'; parent_context = $tempRoot
            route = 'remux'; route_reason_code = 'planned'; route_reason = 'Planned remux'; intended_final_path = 'D:\Library\subtitle-review.mkv'
        }
    ) | Out-Null
    $reviewFailurePath = Get-SourceFailureMarkerPath -SourceFile $reviewSourceFile
    @{
        schema_version = 'failure_record.v1'; correlation_id = $reviewRun; run_monitor_job_id = $reviewJobId
        reason = 'Subtitle OCR requires operator review.'; error_code = 'SUBTITLE_PGS_OCR_FAILED'
        suggested_action = 'Inspect OCR evidence before retrying.'
    } | ConvertTo-Json | Set-Content -LiteralPath $reviewFailurePath -Encoding UTF8
    $script:PipelineRunId = $reviewRun
    try {
        Complete-MediaPipelineRunMonitorQueueEntry `
            -Entry ([pscustomobject]@{ RunMonitorJobId = $reviewJobId; File = $reviewSourceFile }) `
            -Result ([pscustomobject]@{
                Status = 'failed'; Success = $false; PublishState = ''; Route = ''; RouteReasonCode = ''; RouteReason = ''
                Reason = 'Subtitle OCR failed.'; ErrorCode = 'SUBTITLE_PGS_OCR_FAILED'; OutputPath = ''; OutputSizeBytes = 0
            })
    } finally {
        $script:PipelineRunId = $previousPipelineRunId
    }
    $reviewMonitor = Get-Content -LiteralPath (Join-Path $runMonitorRoot "$reviewRun.json") -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $reviewMonitor.items[0].lifecycle_state 'review' 'An exactly correlated production failure marker must terminalize subtitle conversion as Review.'
    Assert-True (@($reviewMonitor.items[0].terminal_references | Where-Object { $_.kind -eq 'review' -and $_.path -eq $reviewFailurePath }).Count -eq 1) 'Review terminal proof must link the exact production failure marker JSON path.'

    $artifactRun = 'run-monitor-terminal-artifact-integration'
    $artifactRows = @(
        [pscustomobject]@{
            run_queue_index = 1; run_queue_total = 2; job_id = "${artifactRun}:item:1"
            source_identity = 'artifact-source-1'; source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\Artifact\A.mkv'; display_name = 'A.mkv'; parent_context = 'C:\Media\Artifact'
            route = 'encode'; route_reason_code = 'planned'; route_reason = 'Planned encode'; intended_final_path = 'D:\Library\A.mkv'
        },
        [pscustomobject]@{
            run_queue_index = 2; run_queue_total = 2; job_id = "${artifactRun}:item:2"
            source_identity = 'artifact-source-2'; source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\Artifact\B.mkv'; display_name = 'B.mkv'; parent_context = 'C:\Media\Artifact'
            route = 'remux'; route_reason_code = 'planned'; route_reason = 'Planned remux'; intended_final_path = 'D:\Library\B.mkv'
        }
    )
    Write-MediaPipelineRunMonitorSeed -RunId $artifactRun -CommandId 'artifact-command' -QueuePlanFingerprint 'artifact-plan' -AcceptedRows $artifactRows | Out-Null
    Set-MediaPipelineRunMonitorAudioRecords -RunId $artifactRun -JobId "${artifactRun}:item:1" -FinalPolicy -Records @([pscustomobject]@{
        source_stream_index = 1; action = 'transcode'; planned_action = 'transcode_downmix'; language = 'eng'
        source_codec = 'truehd'; source_channels = 8; source_layout = '7.1'; output_codec = 'aac'; output_channels = 2
        output_layout = 'stereo'; reason = 'codec outside compatibility list'; reason_code = 'incompatible_codec'; is_default = $true
    }) | Out-Null
    Set-MediaPipelineRunMonitorSubtitleRecords -RunId $artifactRun -JobId "${artifactRun}:item:1" -FinalPolicy -Records @([pscustomobject]@{
        TrackId = 'subtitle:embedded:4'; track_id = 'subtitle:embedded:4'; Action = 'ConvertBdpgs'; PlannedAction = 'ocr_bdpgs_to_srt'
        Entry = @{ Lang = 'eng'; Codec = 'hdmv_pgs_subtitle'; Stream = [pscustomobject]@{ index = 4 }; SubtitleOrdinal = 0; SourceKind = 'embedded' }
        PreserveOriginal = $true; Extract = $true; Convert = $true; Ocr = $true; WriteEmbedded = $false; WriteSidecar = $true
        SourceType = 'image'; SourceKind = 'embedded'; RoutesToReview = $false; PolicyReason = 'preferred-language OCR policy'
    }) | Out-Null
    Set-MediaPipelineRunMonitorAudioRecords -RunId $artifactRun -JobId "${artifactRun}:item:2" -FinalPolicy -Records @([pscustomobject]@{
        source_stream_index = 2; action = 'copy'; planned_action = 'passthrough'; language = 'eng'; source_codec = 'aac'
        source_channels = 2; source_layout = 'stereo'; output_codec = 'aac'; output_channels = 2; output_layout = 'stereo'
        reason = 'codec compatible'; reason_code = 'compatible_passthrough'; is_default = $true
    }) | Out-Null
    $exactIntegrationSidecar = Join-Path $tempRoot 'artifact-integration-exact.pipeline.json'
    @{
        schema_version = 'pipeline_sidecar.v1'; correlation_id = $artifactRun
        run_monitor_job_id = "${artifactRun}:item:1"; route = 'encode_cpu_fallback'
        route_reason_code = 'terminal_cpu_fallback'; route_reason = 'Terminal sidecar proves CPU fallback.'
        output_path = 'D:\Library\Artifact\A.mkv'
        sidecar_paths = @('D:\Library\Artifact\A.eng.srt')
        audio_decisions = @(@{
            source_stream_index = 1; action = 'transcode'; planned_action = 'transcode_downmix'; language = 'eng'
            source_codec = 'truehd'; source_channels = 8; source_layout = '7.1'; output_codec = 'aac'; output_channels = 2
            output_layout = 'stereo'; reason = 'codec outside compatibility list'; reason_code = 'incompatible_codec'; is_default = $true
        })
        subtitle_decisions = @(@{
            track_id = 'subtitle:embedded:4'; action = 'ConvertBdpgs'; planned_action = 'ocr_bdpgs_to_srt'
            preserve_original = $true; routes_to_review = $false; policy_reason = 'preferred-language OCR policy'
        })
        subtitle_conversion_results = @(@{
            track_id = 'subtitle:embedded:4'; action = 'ocr_bdpgs_to_srt'; output_codec = 'subrip'
            expected_output_location = 'external_sidecar'; output_path = 'D:\Library\Artifact\A.eng.srt'
        })
    } | ConvertTo-Json | Set-Content -LiteralPath $exactIntegrationSidecar -Encoding UTF8
    $mismatchIntegrationSidecar = Join-Path $tempRoot 'artifact-integration-mismatch.pipeline.json'
    @{
        schema_version = 'pipeline_sidecar.v1'; correlation_id = 'some-other-run'
        run_monitor_job_id = "${artifactRun}:item:2"; route = 'remux'
        route_reason_code = 'wrong_run'; route_reason = 'This must never become terminal proof.'
        output_path = 'D:\Library\Artifact\Wrong.mkv'
        audio_decisions = @(@{
            source_stream_index = 2; action = 'copy'; planned_action = 'passthrough'; output_codec = 'aac'; output_channels = 2
        })
    } | ConvertTo-Json | Set-Content -LiteralPath $mismatchIntegrationSidecar -Encoding UTF8
    $previousPipelineRunId = [string]$script:PipelineRunId
    $script:PipelineRunId = $artifactRun
    try {
        # Production route selection writes the exact runtime route before the
        # generic Process-File result is created. Completion must never replace
        # encode_hardware / encode_cpu_fallback with the generic "encode" family.
        Set-MediaPipelineRunMonitorExecutedRoute `
            -RunId $artifactRun `
            -JobId "${artifactRun}:item:1" `
            -Route 'encode_cpu_fallback' `
            -ReasonCode 'runtime_cpu_fallback' `
            -Reason 'Hardware failed; the engine selected CPU fallback.' | Out-Null
        Complete-MediaPipelineRunMonitorQueueEntry `
            -Entry ([pscustomobject]@{ RunMonitorJobId = "${artifactRun}:item:1"; File = $null }) `
            -Result ([pscustomobject]@{
                Status = 'completed'; Success = $true; PublishState = 'published'; Route = 'encode'
                RouteReasonCode = 'video_policy'; RouteReason = 'Generic encode-family process result.'
                PipelineSidecarPath = $exactIntegrationSidecar; OutputPath = 'C:\Scratch\A.mkv'; OutputSizeBytes = 1234
                SidecarPaths = @('C:\Scratch\unproven-result-sidecar.srt')
            })
        Complete-MediaPipelineRunMonitorQueueEntry `
            -Entry ([pscustomobject]@{ RunMonitorJobId = "${artifactRun}:item:2"; File = $null }) `
            -Result ([pscustomobject]@{
                Status = 'completed'; Success = $true; PublishState = 'published'; Route = 'remux'
                RouteReasonCode = 'runtime_remux'; RouteReason = 'Runtime engine selected remux.'
                PipelineSidecarPath = $mismatchIntegrationSidecar; OutputPath = 'C:\Scratch\B.mkv'; OutputSizeBytes = 5678
            })
    } finally {
        $script:PipelineRunId = $previousPipelineRunId
    }
    $artifactMonitor = Get-Content -LiteralPath (Join-Path $runMonitorRoot "$artifactRun.json") -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $artifactMonitor.items[0].routes.executed.route 'encode_cpu_fallback' 'A generic terminal result must not overwrite the exact runtime route.'
    Assert-Equal $artifactMonitor.items[0].routes.executed.reason_code 'runtime_cpu_fallback' 'The exact runtime route reason must survive terminal result handling.'
    Assert-Equal $artifactMonitor.items[0].routes.final.route 'encode_cpu_fallback' 'Exact sidecar route must author final route.'
    Assert-Equal $artifactMonitor.items[0].routes.final.evidence.source 'completed_sidecar' 'Final route source must identify the correlated sidecar.'
    Assert-Equal $artifactMonitor.items[0].output.published_path 'D:\Library\Artifact\A.mkv' 'Exact sidecar output path must author publication evidence.'
    Assert-Equal @($artifactMonitor.items[0].output.sidecars).Count 1 'Only terminal-artifact sidecar paths may receive terminal provenance.'
    Assert-Equal $artifactMonitor.items[0].output.sidecars[0].path 'D:\Library\Artifact\A.eng.srt' 'ProcessResult-only sidecar paths must be replaced by exact artifact evidence.'
    Assert-Equal $artifactMonitor.items[0].output.sidecars[0].evidence.source 'completed_sidecar' 'Terminal sidecar path evidence must name its exact artifact authority.'
    Assert-Equal @($artifactMonitor.items[0].terminal_references).Count 3 'Completed proof must link output, its canonical evidence sidecar, and the exact artifact-listed media sidecar.'
    Assert-Equal $artifactMonitor.items[0].audio.tracks[0].state 'completed' 'Exact terminal audio decisions must finalize the matching source track.'
    Assert-Equal $artifactMonitor.items[0].audio.tracks[0].current_action 'transcode_downmix' 'Terminal audio action must retain the exact policy action.'
    Assert-Equal $artifactMonitor.items[0].audio.tracks[0].output_channels 2 'Terminal audio output channels must come from the correlated sidecar.'
    Assert-Equal $artifactMonitor.items[0].audio.tracks[0].evidence.source 'completed_sidecar' 'Terminal audio evidence must name its exact authority.'
    Assert-Equal $artifactMonitor.items[0].subtitles.tracks[0].state 'completed' 'Exact terminal subtitle decisions must finalize the matching source track.'
    Assert-Equal $artifactMonitor.items[0].subtitles.tracks[0].current_action 'ocr_bdpgs_to_srt' 'Terminal subtitle action must retain the exact policy action.'
    Assert-Equal $artifactMonitor.items[0].subtitles.tracks[0].output_location 'external_sidecar' 'Terminal subtitle location must come from correlated conversion evidence.'
    Assert-Equal $artifactMonitor.items[0].subtitles.tracks[0].evidence.source 'completed_sidecar' 'Terminal subtitle evidence must name its exact authority.'
    $artifactAudioStage = @($artifactMonitor.items[0].stages | Where-Object stage_id -eq audio)[0]
    $artifactSubtitleStage = @($artifactMonitor.items[0].stages | Where-Object stage_id -eq subtitles)[0]
    Assert-Equal $artifactAudioStage.state 'completed' 'All exactly reconciled audio tracks must close the canonical Audio stage.'
    Assert-Equal $artifactAudioStage.evidence.source 'completed_sidecar' 'Terminal Audio stage must retain exact artifact authority.'
    Assert-Equal $artifactSubtitleStage.state 'completed' 'All exactly reconciled subtitle tracks must close the canonical Subtitles stage.'
    Assert-Equal $artifactSubtitleStage.evidence.source 'completed_sidecar' 'Terminal Subtitles stage must retain exact artifact authority.'
    Assert-Equal $artifactMonitor.items[1].routes.executed.route 'remux' 'Mismatched terminal proof must not suppress exact runtime route evidence.'
    Assert-Equal $artifactMonitor.items[1].routes.final.state 'awaiting_evidence' 'Mismatched sidecar must not populate final route.'
    Assert-Equal $artifactMonitor.items[1].output.state 'unknown' 'Mismatched sidecar must not claim publication.'
    Assert-Equal $artifactMonitor.items[1].lifecycle_state 'unknown' 'A success result without exact terminal proof must remain nonterminal until run finalization.'
    Assert-Equal @($artifactMonitor.items[1].terminal_references).Count 0 'Mismatched sidecar must not create terminal references.'
    Assert-Equal $artifactMonitor.items[1].audio.tracks[0].state 'unknown' 'A mismatched sidecar must not finalize per-track evidence.'
    $mismatchedFinalStage = @($artifactMonitor.items[1].stages | Where-Object stage_id -eq 'final_evidence')[0]
    Assert-Equal $mismatchedFinalStage.state 'unknown' 'Mismatched terminal proof must remain explicitly unknown.'
    Assert-Equal $mismatchedFinalStage.reason_code 'terminal_artifact_correlation_mismatch' 'Mismatched terminal proof must retain an actionable reason code.'
    $artifactCompletionRejected = $false
    try {
        Complete-MediaPipelineRunMonitor -RunId $artifactRun -State completed | Out-Null
    } catch {
        $artifactCompletionRejected = ([string]$_ -match 'RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE')
    }
    Assert-True $artifactCompletionRejected 'A run must not report clean completion when an item lacks exact terminal artifact proof.'
    Complete-MediaPipelineRunMonitor `
        -RunId $artifactRun `
        -State failed `
        -RemainingItemState failed `
        -Reason 'A completed item lacked exact terminal artifact proof.' `
        -ReasonCode 'RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE' | Out-Null
    $failedArtifactMonitor = Get-Content -LiteralPath (Join-Path $runMonitorRoot "$artifactRun.json") -Raw | ConvertFrom-Json -Depth 40
    $failedMissingProofFinal = @($failedArtifactMonitor.items[1].stages | Where-Object stage_id -eq 'final_evidence')[0]
    Assert-Equal $failedArtifactMonitor.run.lifecycle_state 'failed' 'Missing terminal proof must produce a failed run outcome.'
    Assert-Equal $failedArtifactMonitor.items[1].lifecycle_state 'failed' 'Run finalization must honestly fail the still-nonterminal item without rewriting a false success state.'
    Assert-Equal $failedMissingProofFinal.state 'failed' 'Run finalization must explicitly fail the unresolved final-evidence stage.'
    Assert-Equal $failedMissingProofFinal.reason_code 'RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE' 'Run finalization must identify missing terminal proof as the run failure reason.'
    Assert-Equal $failedMissingProofFinal.evidence.source 'run_completion' 'The failed final-evidence stage must name run finalization, not a nonexistent failure artifact.'

    # A correlated terminal artifact proves only actions that the production
    # policy vocabulary explicitly defines. Durable identity alone must never
    # turn blank or future/unsupported action text into a completed track.
    $terminalActionRun = 'run-monitor-terminal-track-actions'
    $terminalActionJob = "${terminalActionRun}:item:1"
    Write-MediaPipelineRunMonitorSeed -RunId $terminalActionRun -CommandId 'terminal-track-actions-command' -QueuePlanFingerprint 'terminal-track-actions-plan' -AcceptedRows @(
        [pscustomobject]@{
            run_queue_index = 1; run_queue_total = 1; job_id = $terminalActionJob
            source_identity = 'terminal-track-actions-source'; source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\TerminalTrackActions.mkv'; display_name = 'TerminalTrackActions.mkv'; parent_context = 'C:\Media'
            route = 'remux'; route_reason_code = 'planned'; route_reason = 'Planned remux'; intended_final_path = 'D:\Library\TerminalTrackActions.mkv'
        }
    ) | Out-Null
    Set-MediaPipelineRunMonitorAudioRecords -RunId $terminalActionRun -JobId $terminalActionJob -FinalPolicy -Records @(
        [pscustomobject]@{ source_stream_index = 0; action = 'copy'; planned_action = 'passthrough'; language = 'eng'; source_codec = 'aac'; source_channels = 2; source_layout = 'stereo' },
        [pscustomobject]@{ source_stream_index = 1; action = ''; planned_action = ''; language = 'eng'; source_codec = 'ac3'; source_channels = 6; source_layout = '5.1' },
        [pscustomobject]@{ source_stream_index = 2; action = 'future_audio_action'; planned_action = 'future_audio_action'; language = 'jpn'; source_codec = 'aac'; source_channels = 2; source_layout = 'stereo' }
    ) | Out-Null
    Set-MediaPipelineRunMonitorSubtitleRecords -RunId $terminalActionRun -JobId $terminalActionJob -FinalPolicy -Records @(
        [pscustomobject]@{
            TrackId = 'subtitle:embedded:0'; Action = 'Keep'; PlannedAction = 'preserve_original'
            Entry = @{ Lang = 'eng'; Codec = 'subrip'; Stream = [pscustomobject]@{ index = 3 }; SubtitleOrdinal = 0; SourceKind = 'embedded' }
            PreserveOriginal = $true; SourceType = 'text'; SourceKind = 'embedded'; PolicyReason = 'preserve supported text subtitle'
        },
        [pscustomobject]@{
            TrackId = 'subtitle:embedded:1'; Action = ''; PlannedAction = ''
            Entry = @{ Lang = 'eng'; Codec = 'ass'; Stream = [pscustomobject]@{ index = 4 }; SubtitleOrdinal = 1; SourceKind = 'embedded' }
            PreserveOriginal = $true; SourceType = 'text'; SourceKind = 'embedded'; PolicyReason = 'terminal action missing'
        },
        [pscustomobject]@{
            TrackId = 'subtitle:embedded:2'; Action = 'FutureSubtitleAction'; PlannedAction = 'future_subtitle_action'
            Entry = @{ Lang = 'jpn'; Codec = 'ass'; Stream = [pscustomobject]@{ index = 5 }; SubtitleOrdinal = 2; SourceKind = 'embedded' }
            PreserveOriginal = $true; SourceType = 'text'; SourceKind = 'embedded'; PolicyReason = 'terminal action unsupported'
        }
    ) | Out-Null
    Sync-MediaPipelineRunMonitorTerminalTracks `
        -RunId $terminalActionRun `
        -JobId $terminalActionJob `
        -TerminalProof ([pscustomobject]@{
            Verified = $true
            EvidenceSource = 'completed_sidecar'
            Payload = [pscustomobject]@{
                audio_decisions = @(
                    [pscustomobject]@{ source_stream_index = 1; action = ''; planned_action = ''; reason = 'terminal action absent'; output_codec = 'eac3'; output_channels = 6 },
                    [pscustomobject]@{ source_stream_index = 2; action = 'future_audio_action'; planned_action = 'future_audio_action'; reason = 'terminal action unsupported'; output_codec = 'opus'; output_channels = 2 },
                    [pscustomobject]@{ source_stream_index = 0; action = 'copy'; planned_action = 'passthrough'; reason = 'codec compatible' }
                )
                subtitle_decisions = @(
                    [pscustomobject]@{ track_id = 'subtitle:embedded:1'; action = ''; planned_action = ''; reason = 'terminal action absent' },
                    [pscustomobject]@{ track_id = 'subtitle:embedded:2'; action = 'FutureSubtitleAction'; planned_action = 'future_subtitle_action'; reason = 'terminal action unsupported' },
                    [pscustomobject]@{ track_id = 'subtitle:embedded:0'; action = 'Keep'; planned_action = 'preserve_original'; reason = 'preserve supported text subtitle' }
                )
                subtitle_conversion_results = @(
                    [pscustomobject]@{ track_id = 'subtitle:embedded:1'; action = 'convert_ass'; output_codec = 'subrip'; expected_output_location = 'external_sidecar'; output_path = 'D:\Library\TerminalTrackActions.eng.srt' },
                    [pscustomobject]@{ track_id = 'subtitle:embedded:2'; action = 'convert_ass'; output_codec = 'subrip'; expected_output_location = 'external_sidecar'; output_path = 'D:\Library\TerminalTrackActions.jpn.srt' }
                )
            }
        })
    $terminalActionPath = Join-Path $runMonitorRoot "$terminalActionRun.json"
    Assert-RunMonitorPythonContract -Path $terminalActionPath
    $terminalActionMonitor = Get-Content -LiteralPath $terminalActionPath -Raw | ConvertFrom-Json -Depth 40
    $terminalActionAudio = @($terminalActionMonitor.items[0].audio.tracks)
    $terminalActionSubtitles = @($terminalActionMonitor.items[0].subtitles.tracks)
    Assert-Equal $terminalActionAudio[0].state 'completed' 'Recognized production passthrough must retain terminal completion.'
    Assert-Equal $terminalActionAudio[0].current_action 'passthrough' 'Recognized production passthrough must retain its normalized action.'
    Assert-Equal $terminalActionAudio[0].evidence.provenance 'terminal' 'Recognized audio actions must retain terminal provenance.'
    Assert-Equal $terminalActionAudio[1].state 'unknown' 'A blank terminal audio action must fail closed as unknown.'
    Assert-Equal $terminalActionAudio[1].current_action 'unknown' 'A blank terminal audio action must suppress any stale runtime action.'
    Assert-Equal $terminalActionAudio[1].evidence.provenance 'unknown' 'A blank terminal audio action must not claim terminal provenance.'
    Assert-Equal $terminalActionAudio[1].reason_code 'terminal_audio_action_missing' 'A blank terminal audio action must expose the fail-closed reason.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$terminalActionAudio[1].output_codec)) 'A blank terminal audio action must not attach unsupported terminal output details.'
    Assert-Equal $terminalActionAudio[2].state 'unknown' 'An unsupported terminal audio action must fail closed as unknown.'
    Assert-Equal $terminalActionAudio[2].evidence.provenance 'unknown' 'An unsupported terminal audio action must not claim terminal provenance.'
    Assert-Equal $terminalActionAudio[2].reason_code 'terminal_audio_action_unsupported' 'An unsupported terminal audio action must expose the fail-closed reason.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$terminalActionAudio[2].output_codec)) 'An unsupported terminal audio action must not attach terminal output details.'
    Assert-Equal $terminalActionSubtitles[0].state 'completed' 'Recognized production subtitle preservation must retain terminal completion.'
    Assert-Equal $terminalActionSubtitles[0].current_action 'preserve_original' 'Recognized production subtitle preservation must retain its exact action.'
    Assert-Equal $terminalActionSubtitles[0].evidence.provenance 'terminal' 'Recognized subtitle actions must retain terminal provenance.'
    Assert-Equal $terminalActionSubtitles[1].state 'unknown' 'A blank terminal subtitle action must fail closed as unknown.'
    Assert-Equal $terminalActionSubtitles[1].current_action 'unknown' 'A blank terminal subtitle action must suppress any stale runtime action.'
    Assert-Equal $terminalActionSubtitles[1].evidence.provenance 'unknown' 'A blank terminal subtitle action must not claim terminal provenance.'
    Assert-Equal $terminalActionSubtitles[1].reason_code 'terminal_subtitle_action_missing' 'A blank terminal subtitle action must expose the fail-closed reason.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$terminalActionSubtitles[1].output_path)) 'A blank terminal subtitle action must not attach a conversion output path.'
    Assert-Equal $terminalActionSubtitles[2].state 'unknown' 'An unsupported terminal subtitle action must fail closed as unknown.'
    Assert-Equal $terminalActionSubtitles[2].evidence.provenance 'unknown' 'An unsupported terminal subtitle action must not claim terminal provenance.'
    Assert-Equal $terminalActionSubtitles[2].reason_code 'terminal_subtitle_action_unsupported' 'An unsupported terminal subtitle action must expose the fail-closed reason.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$terminalActionSubtitles[2].output_path)) 'An unsupported terminal subtitle action must not attach a conversion output path.'
    Assert-Equal $terminalActionMonitor.items[0].audio.state 'unknown' 'Unresolved terminal audio actions must keep the aggregate collection unknown.'
    Assert-Equal $terminalActionMonitor.items[0].subtitles.state 'unknown' 'Unresolved terminal subtitle actions must keep the aggregate collection unknown.'
    Assert-Equal $terminalActionMonitor.items[0].audio.evidence.provenance 'unknown' 'Recognized audio records later in artifact order must not upgrade an unresolved aggregate to terminal provenance.'
    Assert-Equal $terminalActionMonitor.items[0].subtitles.evidence.provenance 'unknown' 'Recognized subtitle records later in artifact order must not upgrade an unresolved aggregate to terminal provenance.'
    Assert-True ((@($terminalActionMonitor.items[0].stages | Where-Object stage_id -eq audio)[0]).state -ne 'completed') 'Unresolved terminal audio actions must not close the canonical Audio stage.'
    Assert-True ((@($terminalActionMonitor.items[0].stages | Where-Object stage_id -eq subtitles)[0]).state -ne 'completed') 'Unresolved terminal subtitle actions must not close the canonical Subtitles stage.'

    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'encode_verify') 'verification' 'encode_verify must map to verification.'
    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'remux_verify') 'verification' 'remux_verify must map to verification.'
    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'encode') 'transcode' 'encode must map to transcode.'
    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'encode_safe') 'transcode' 'encode_safe must map to transcode.'
    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'encode_cpu') 'transcode' 'encode_cpu must map to transcode.'
    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'remux_av') 'mux' 'remux_av must map to mux.'
    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'remux') '' 'A bare route label must not become stage authority.'
    Assert-Equal (ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage 'remux_mux') 'mux' 'remux_mux must map to mux.'

    Set-MediaPipelineRunMonitorRouteEvidence `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:2' `
        -Authority executed `
        -State not_applicable `
        -Reason 'This accepted item has no runtime media route.' `
        -ReasonCode 'RUNTIME_ROUTE_NOT_APPLICABLE' | Out-Null
    Set-MediaPipelineRunMonitorExecutedRoute `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:2' `
        -Route 'encode' `
        -Reason 'Generic completion family.' `
        -OnlyIfAwaiting | Out-Null
    $notApplicableRoute = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[1].routes.executed
    Assert-Equal $notApplicableRoute.state 'not_applicable' 'OnlyIfAwaiting must not overwrite explicit not-applicable runtime route evidence.'
    Assert-Equal $notApplicableRoute.reason_code 'RUNTIME_ROUTE_NOT_APPLICABLE' 'Explicit runtime route reason must survive generic completion evidence.'
    Set-MediaPipelineRunMonitorRouteEvidence `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:2' `
        -Authority executed `
        -State awaiting_evidence | Out-Null

    $script:CurrentRunMonitorJobId = 'run-monitor-test:item:2'
    Set-MediaPipelineRunMonitorStage -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -StageId verification -State active -EvidenceSource verification_result | Out-Null
    Set-MediaPipelineEncodeVerificationMonitorOutcome -State completed -Detail 'Encoded verification passed.'
    $encodeVerificationOutcome = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[1].stages | Where-Object stage_id -eq verification
    Assert-Equal $encodeVerificationOutcome.state 'completed' 'Successful encode verification must explicitly close the canonical Verification stage.'
    Assert-Equal $encodeVerificationOutcome.evidence.source 'verification_result' 'Encode verification must expose its backend result authority.'
    Set-MediaPipelineRunMonitorStage -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -StageId verification -State active -EvidenceSource verification_result | Out-Null
    Set-MediaPipelineRemuxVerificationMonitorOutcome -State review -Detail 'Track verification requires review.' -ReasonCode 'TRACK_VERIFY_REVIEW'
    $remuxVerificationOutcome = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[1].stages | Where-Object stage_id -eq verification
    Assert-Equal $remuxVerificationOutcome.state 'review' 'Failed remux policy verification must explicitly close Verification as review.'
    Assert-Equal $remuxVerificationOutcome.reason_code 'TRACK_VERIFY_REVIEW' 'Verification review must preserve its exact reason code.'

    Set-MediaPipelineRunMonitorExecutedRoute `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -Route 'encode_cpu_fallback' `
        -ReasonCode 'hardware_unavailable' `
        -Reason 'Hardware encoder unavailable; CPU fallback selected.' | Out-Null
    $script:CurrentRunMonitorJobId = 'run-monitor-test:item:1'
    $WorkerChild = $false
    Set-MediaPipelineRunMonitorStage `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -StageId 'verification' `
        -State 'active' `
        -Detail 'Verifying output' `
        -Numerator 25 `
        -Denominator 100 | Out-Null
    $serialWorkerMonitor = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal @($serialWorkerMonitor.current_workers).Count 1 'Serial Backend Queue processing must expose its controller worker.'
    Assert-Equal $serialWorkerMonitor.current_workers[0].job_id 'run-monitor-test:item:1' 'Serial worker must use the exact accepted job ID.'
    Assert-Equal $serialWorkerMonitor.current_workers[0].stage_id 'verification' 'Serial worker stage must match exact backend stage evidence.'
    Set-MediaPipelineRunMonitorStage -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:1' -StageId 'verification' -State completed -EvidenceSource 'verification_result' | Out-Null
    $serialStageComplete = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal @($serialStageComplete.current_workers).Count 0 'A serial worker must clear while no backend stage is active.'
    Set-MediaPipelineRunMonitorStage -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:1' -StageId 'verification' -State active -Numerator 25 -Denominator 100 | Out-Null

    $audioRecords = @(
        [pscustomobject]@{
            source_stream_index = 1; action = 'transcode'; reason = 'codec outside compatibility list'; language = 'jpn'
            source_codec = 'truehd'; source_channels = 8; source_layout = '7.1'; output_codec = 'aac'; output_channels = 2; output_layout = 'stereo'; is_default = $true
            reason_code = 'incompatible_codec'
        },
        [pscustomobject]@{
            source_stream_index = 2; action = 'copy'; reason = 'codec compatible'; language = 'eng'
            source_codec = 'aac'; source_channels = 2; source_layout = 'stereo'; output_codec = 'aac'; output_channels = 2; output_layout = 'stereo'; is_default = $false
            reason_code = 'compatible_passthrough'
        }
    )
    Set-MediaPipelineRunMonitorAudioRecords -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:1' -Records $audioRecords -FinalPolicy | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress `
        -Kind audio `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -TrackId 'audio:1' `
        -CurrentAction 'downmix' `
        -State active `
        -Indeterminate `
        -Result 'Waiting for the shared CPU slot.' `
        -Reason 'Profile requires stereo output.' | Out-Null
    Update-MediaPipelineRunMonitorActiveTrackHeartbeat `
        -Kind audio `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -EvidenceSource 'cpu_mutex_wait' | Out-Null
    $singleAudioHeartbeat = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[0].audio
    Assert-Equal $singleAudioHeartbeat.tracks[1].state 'awaiting_evidence' 'Aggregate heartbeat must leave a non-active audio track untouched.'
    Set-MediaPipelineRunMonitorTrackProgress `
        -Kind audio `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -TrackId 'audio:2' `
        -CurrentAction 'passthrough' `
        -State active `
        -Indeterminate `
        -Result 'Waiting for the shared CPU slot.' `
        -Reason 'The aggregate FFmpeg audio operation includes this passthrough track.' | Out-Null
    Update-MediaPipelineRunMonitorActiveTrackHeartbeat `
        -Kind audio `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -EvidenceSource 'cpu_mutex_wait' | Out-Null
    $audioHeartbeat = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[0].audio
    Assert-Equal $audioHeartbeat.tracks[0].state 'active' 'Exact active audio track heartbeat must retain active state.'
    Assert-Equal $audioHeartbeat.tracks[0].current_action 'downmix' 'Audio heartbeat must not overwrite the backend-selected track action.'
    Assert-Equal $audioHeartbeat.tracks[0].result 'Waiting for the shared CPU slot.' 'Audio heartbeat must preserve existing track result/detail.'
    Assert-Equal $audioHeartbeat.tracks[0].reason 'Profile requires stereo output.' 'Audio heartbeat must preserve profile-owned track reason.'
    Assert-Equal $audioHeartbeat.tracks[0].progress.kind 'indeterminate' 'CPU-slot wait heartbeat must never fabricate audio progress.'
    Assert-Equal $audioHeartbeat.tracks[0].evidence.source 'cpu_mutex_wait' 'Audio heartbeat must identify its exact wait authority.'
    Assert-Equal $audioHeartbeat.tracks[1].state 'active' 'Aggregate remux CPU wait must refresh every exact audio track already active in the shared FFmpeg operation.'
    Assert-Equal $audioHeartbeat.tracks[1].current_action 'passthrough' 'Aggregate CPU wait heartbeat must preserve each backend-selected audio action.'
    Assert-Equal $audioHeartbeat.tracks[1].evidence.source 'cpu_mutex_wait' 'Second active audio track must share the exact aggregate wait authority.'

    $subtitleEntry = @{
        Lang = 'eng'; Codec = 'hdmv_pgs_subtitle'; IsForced = $false; IsSupplemental = $false
        Stream = [pscustomobject]@{ index = 4 }; SubtitleOrdinal = 0; SourceKind = 'embedded'
    }
    $subtitleRecords = @(
        [pscustomobject]@{
            Action = 'ConvertBdpgs'; Entry = $subtitleEntry; PreserveOriginal = $true
            OriginalPreserveReason = 'preserved'; RoutesToReview = $false; ReviewErrorCode = ''
            ReviewReason = ''; ConversionKind = 'bdpgs_to_srt'; Extract = $true; Convert = $true; Ocr = $true
            WriteEmbedded = $true; WriteSidecar = $true; SourceType = 'image'; SourceKind = 'embedded'; PlannedAction = 'preserve_and_ocr'
        }
    )
    Set-MediaPipelineRunMonitorSubtitleRecords -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:1' -Records $subtitleRecords -FinalPolicy | Out-Null

    $sidecarSubtitleRecords = @(
        [pscustomobject]@{
            TrackId = 'subtitle:sidecar:0'; Action = 'ConvertAss'; Entry = @{ Lang = 'eng'; Codec = 'ass'; SubtitleOrdinal = 0; SourceKind = 'sidecar' }
            PreserveOriginal = $true; Convert = $true; SourceType = 'text'; SourceKind = 'sidecar'; PlannedAction = 'convert_ass_to_srt'
        },
        [pscustomobject]@{
            TrackId = 'subtitle:sidecar:1'; Action = 'ConvertAss'; Entry = @{ Lang = 'jpn'; Codec = 'ass'; SubtitleOrdinal = 1; SourceKind = 'sidecar' }
            PreserveOriginal = $true; Convert = $true; SourceType = 'text'; SourceKind = 'sidecar'; PlannedAction = 'convert_ass_to_srt'
        }
    )
    Set-MediaPipelineRunMonitorSubtitleRecords -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -Records $sidecarSubtitleRecords -FinalPolicy | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress `
        -Kind subtitles `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:2' `
        -TrackId 'subtitle:sidecar:1' `
        -CurrentAction 'convert_ass_to_srt' `
        -State active `
        -Indeterminate | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress `
        -Kind subtitles `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:2' `
        -TrackId 'subtitle:sidecar:0' `
        -CurrentAction 'convert_ass_to_srt' `
        -State active `
        -Indeterminate | Out-Null
    Update-MediaPipelineRunMonitorActiveTrackHeartbeat `
        -Kind subtitles `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:2' `
        -TrackId 'subtitle:sidecar:1' `
        -EvidenceSource 'subtitle_exact_track_heartbeat' `
        -EvidenceProvenance worker_heartbeat | Out-Null
    $exactSubtitleHeartbeat = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[1].subtitles
    Assert-Equal $exactSubtitleHeartbeat.tracks[0].evidence.source 'subtitles_progress' 'Exact heartbeat must not refresh a different active subtitle track.'
    Assert-Equal $exactSubtitleHeartbeat.tracks[1].evidence.source 'subtitle_exact_track_heartbeat' 'Exact heartbeat must refresh only the selected active subtitle track.'
    Assert-Equal $exactSubtitleHeartbeat.tracks[1].evidence.provenance 'worker_heartbeat' 'Exact heartbeat must identify liveness provenance.'
    Set-MediaPipelineRunMonitorTrackProgress -Kind subtitles -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -TrackId 'subtitle:sidecar:1' -State completed -Result 'terminal fixture' | Out-Null
    $beforeLateTerminalHeartbeatSequence = [int64](Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).write_sequence
    Update-MediaPipelineRunMonitorActiveTrackHeartbeat -Kind subtitles -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -TrackId 'subtitle:sidecar:1' -EvidenceSource 'late_terminal_heartbeat' | Out-Null
    $afterLateTerminalHeartbeatPayload = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    $terminalSubtitleHeartbeat = $afterLateTerminalHeartbeatPayload.items[1].subtitles.tracks[1]
    Assert-Equal $terminalSubtitleHeartbeat.state 'completed' 'Late heartbeat must not reactivate terminal subtitle evidence.'
    Assert-Equal $terminalSubtitleHeartbeat.evidence.source 'subtitles_progress' 'Late heartbeat must not overwrite terminal subtitle evidence.'
    Assert-Equal ([int64]$afterLateTerminalHeartbeatPayload.write_sequence) $beforeLateTerminalHeartbeatSequence 'Late terminal heartbeat must not refresh run-level freshness or persist a no-op write.'
    $beforeMissingTrackHeartbeatSequence = [int64]$afterLateTerminalHeartbeatPayload.write_sequence
    Update-MediaPipelineRunMonitorActiveTrackHeartbeat -Kind subtitles -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -TrackId 'subtitle:missing' -EvidenceSource 'missing_track_heartbeat' | Out-Null
    $afterMissingTrackHeartbeatPayload = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    $missingSubtitleHeartbeat = $afterMissingTrackHeartbeatPayload.items[1].subtitles
    Assert-Equal $missingSubtitleHeartbeat.tracks[0].evidence.source 'subtitles_progress' 'Missing TrackId heartbeat must preserve unrelated active evidence.'
    Assert-Equal $missingSubtitleHeartbeat.tracks[1].evidence.source 'subtitles_progress' 'Missing TrackId heartbeat must preserve terminal evidence.'
    Assert-Equal ([int64]$afterMissingTrackHeartbeatPayload.write_sequence) $beforeMissingTrackHeartbeatSequence 'Missing TrackId heartbeat must not refresh run-level freshness or persist a no-op write.'
    Set-MediaPipelineRunMonitorTrackProgress -Kind subtitles -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -TrackId 'subtitle:sidecar:0' -State awaiting_evidence | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress -Kind subtitles -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -TrackId 'subtitle:sidecar:1' -CurrentAction 'convert_ass_to_srt' -State active -Indeterminate | Out-Null

    $workers = @(
        [pscustomobject]@{
            worker_id = 'local-worker-1'; job_id = 'run-monitor-test:item:1'; state = 'active'; stage_id = 'verification'
            route = 'encode_cpu_fallback'; updated_at = (Get-Date).ToUniversalTime().ToString('o'); numerator = 25; denominator = 100
        },
        [pscustomobject]@{
            worker_id = 'local-worker-2'; job_id = 'run-monitor-test:item:2'; state = 'active'; stage_id = 'transcode'
            route = 'encode_hardware'; updated_at = (Get-Date).ToUniversalTime().ToString('o'); numerator = $null; denominator = $null
        }
    )
    Set-MediaPipelineRunMonitorWorkers -RunId 'run-monitor-test' -Workers $workers | Out-Null

    $current = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $current.items[0].routes.planned.route 'remux' 'Planned route changed after runtime route evidence.'
    Assert-Equal $current.items[0].routes.executed.route 'encode_cpu_fallback' 'Executed route was not recorded.'
    Assert-Equal $current.items[0].routes.final.state 'awaiting_evidence' 'Final route must remain unproven.'
    $verification = @($current.items[0].stages | Where-Object stage_id -eq 'verification')[0]
    Assert-Equal $verification.state 'active' 'Verification stage was not made active.'
    Assert-Equal $verification.progress.kind 'determinate' 'Truthful stage progress was not determinate.'
    Assert-Equal $verification.progress.numerator 25 'Stage progress numerator mismatch.'
    Assert-Equal @($current.items[0].audio.tracks).Count 2 'All audio tracks were not retained.'
    Assert-Equal $current.items[0].audio.tracks[0].language 'jpn' 'Audio language evidence missing.'
    Assert-Equal $current.items[0].audio.tracks[0].planned_action 'transcode' 'Audio action evidence mismatch.'
    Assert-Equal $current.items[0].audio.tracks[1].planned_action 'passthrough' 'Audio copy must be labeled passthrough.'
    Assert-Equal @($current.items[0].subtitles.tracks).Count 1 'Subtitle track evidence missing.'
    Assert-Equal $current.items[0].subtitles.tracks[0].language 'eng' 'Subtitle language evidence missing.'
    Assert-True ([bool]$current.items[0].subtitles.tracks[0].preserve) 'Original subtitle preservation evidence missing.'
    Assert-True ([bool]$current.items[0].subtitles.tracks[0].ocr) 'PGS OCR evidence missing.'
    Assert-Equal $current.items[0].subtitles.tracks[0].source_kind 'embedded' 'Subtitle embedded-vs-sidecar provenance missing.'
    Assert-Equal @($current.items[1].subtitles.tracks).Count 2 'Distinct external sidecars must both remain in the monitor.'
    Assert-Equal $current.items[1].subtitles.tracks[0].state 'awaiting_evidence' 'TrackId progress must not mutate a different external sidecar.'
    Assert-Equal $current.items[1].subtitles.tracks[1].state 'active' 'TrackId progress must correlate the exact external sidecar.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$current.items[1].subtitles.tracks[1].started_at)) 'Active subtitle work must expose a backend start timestamp.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$current.items[1].subtitles.tracks[1].completed_at)) 'Active subtitle work must not expose a completion timestamp.'
    Assert-Equal @($current.current_workers).Count 2 'All active workers were not retained.'
    Assert-Equal $current.current_workers[0].route 'encode_cpu_fallback' 'Worker route must come from exact item executed-route evidence.'
    Assert-Equal $current.current_workers[1].route '' 'Worker route must remain blank while exact item executed-route evidence is awaiting.'
    Assert-True ($null -eq $current.current_workers[1].progress.numerator) 'Indeterminate worker progress must not manufacture a numerator.'

    Set-MediaPipelineRunMonitorTrackProgress -Kind subtitles -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:2' -TrackId 'subtitle:sidecar:0' -State unknown -Result 'Backend evidence unavailable.' | Out-Null
    $unknownCollectionEvidence = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[1].subtitles
    Assert-Equal $unknownCollectionEvidence.state 'active' 'A different exact active subtitle track must keep the collection active while another track is unknown.'

    Set-MediaPipelineRunMonitorTrackProgress -Kind audio -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:1' -TrackId 'audio:1' -CurrentAction 'downmix' -State completed -Result 'transcoded to stereo AAC' | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress -Kind audio -RunId 'run-monitor-test' -JobId 'run-monitor-test:item:1' -TrackId 'audio:2' -CurrentAction 'passthrough' -State completed -Result 'copied unchanged' | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress `
        -Kind subtitles `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -TrackId 'subtitle:embedded:0' `
        -CurrentAction 'ocr_bdpgs_to_srt' `
        -State completed `
        -Result 'preferred-language SRT written' `
        -OutputCodec 'subrip' `
        -OutputLocation 'external_sidecar' `
        -OutputPath 'C:\Scratch\Pending\Episode.eng.srt' `
        -ParkedPath 'C:\Scratch\Pending\Episode.eng.srt' `
        -IntendedFinalPath 'D:\Library\A\Episode.eng.srt' | Out-Null
    Set-MediaPipelineRunMonitorItemLifecycle `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -State 'parked' `
        -Reason 'Destination unavailable; output parked.' | Out-Null
    Set-MediaPipelineRunMonitorOutput `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -State 'parked' `
        -ParkedPath 'C:\Scratch\Pending\Episode.mkv' `
        -IntendedFinalPath 'D:\Library\A\Episode.mkv' `
        -VerificationState 'completed' | Out-Null
    Add-MediaPipelineRunMonitorTerminalReference `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -Kind 'pending_publish' `
        -Reference 'pending-a.manifest.json' `
        -Path 'C:\Scratch\Pending\Episode.mkv' | Out-Null
    Set-MediaPipelineRunMonitorFinalRoute `
        -RunId 'run-monitor-test' `
        -JobId 'run-monitor-test:item:1' `
        -Route 'encode_cpu_fallback' `
        -ReasonCode 'parked_destination_unavailable' `
        -Reason 'Verified output parked for later publication.' `
        -EvidenceSource 'pending_publish_manifest' | Out-Null

    $terminalItem = (Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40).items[0]
    Assert-Equal $terminalItem.lifecycle_state 'parked' 'Parked lifecycle was not retained.'
    Assert-Equal $terminalItem.output.parked_path 'C:\Scratch\Pending\Episode.mkv' 'Parked path missing.'
    Assert-Equal $terminalItem.terminal_references[0].kind 'pending_publish' 'Pending terminal reference missing.'
    Assert-Equal $terminalItem.routes.final.route 'encode_cpu_fallback' 'Final route proof missing.'
    Assert-Equal $terminalItem.audio.state 'completed' 'Terminal pipeline evidence should complete planned audio tracks.'
    Assert-Equal $terminalItem.audio.tracks[0].state 'completed' 'Terminal pipeline evidence should retain per-track audio completion.'
    Assert-Equal $terminalItem.audio.tracks[0].current_action 'downmix' 'Terminal lifecycle must retain the last exact audio action.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$terminalItem.audio.tracks[0].completed_at)) 'Completed audio evidence must expose a completion timestamp.'
    Assert-Equal $terminalItem.subtitles.state 'completed' 'Terminal pipeline evidence should complete planned subtitle tracks.'
    Assert-Equal $terminalItem.subtitles.tracks[0].state 'completed' 'Terminal pipeline evidence should retain per-track subtitle completion.'
    Assert-Equal $terminalItem.subtitles.tracks[0].current_action 'ocr_bdpgs_to_srt' 'Terminal lifecycle must retain the last exact subtitle action.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$terminalItem.subtitles.tracks[0].started_at)) 'Subtitle OCR evidence must expose a backend start timestamp.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$terminalItem.subtitles.tracks[0].completed_at)) 'Completed subtitle OCR evidence must expose a completion timestamp.'
    Assert-Equal $terminalItem.subtitles.tracks[0].output_location 'external_sidecar' 'Subtitle terminal location evidence missing.'
    Assert-Equal $terminalItem.subtitles.tracks[0].parked_path 'C:\Scratch\Pending\Episode.eng.srt' 'Subtitle parked path evidence missing.'
    Assert-Equal $terminalItem.routes.final.evidence.source 'pending_publish_manifest' 'Final route must name the exact correlated terminal authority.'

    $terminalRewriteRejected = $false
    try {
        Set-MediaPipelineRunMonitorItemLifecycle `
            -RunId 'run-monitor-test' `
            -JobId 'run-monitor-test:item:1' `
            -State 'completed' | Out-Null
    } catch {
        $terminalRewriteRejected = ([string]$_ -match 'terminal item state cannot change')
    }
    Assert-True $terminalRewriteRejected 'A terminal item lifecycle must not be rewritten to a different terminal state.'

    $unknownTrackRun = 'run-monitor-unknown-track-terminal'
    $unknownTrackRows = @([pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; job_id = "${unknownTrackRun}:item:1"
        source_identity = 'unknown-track-source'; source_identity_algorithm = 'source_identity_v2'
        source_path = 'C:\Media\UnknownTrack.mkv'; display_name = 'UnknownTrack.mkv'; parent_context = 'C:\Media'
        route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'; intended_final_path = 'D:\Library\UnknownTrack.mkv'
    })
    Write-MediaPipelineRunMonitorSeed -RunId $unknownTrackRun -CommandId 'unknown-track-command' -QueuePlanFingerprint 'unknown-track-plan' -AcceptedRows $unknownTrackRows | Out-Null
    Set-MediaPipelineRunMonitorAudioRecords -RunId $unknownTrackRun -JobId "${unknownTrackRun}:item:1" -Records @([pscustomobject]@{
        source_stream_index = 7; action = 'transcode'; source_codec = 'dts'; language = 'eng'; planned_action = 'transcode'
    }) -FinalPolicy | Out-Null
    Set-MediaPipelineRunMonitorItemLifecycle -RunId $unknownTrackRun -JobId "${unknownTrackRun}:item:1" -State 'completed' | Out-Null
    $unknownTrackTerminal = (Get-Content -LiteralPath (Join-Path $runMonitorRoot "$unknownTrackRun.json") -Raw | ConvertFrom-Json -Depth 40).items[0]
    Assert-Equal $unknownTrackTerminal.audio.tracks[0].state 'unknown' 'Item completion without exact per-track proof must not invent track success.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$unknownTrackTerminal.audio.tracks[0].completed_at)) 'Unknown terminal track evidence must not claim a completion timestamp.'
    Assert-Equal $unknownTrackTerminal.audio.tracks[0].current_action '' 'Item completion must not replace a missing action with a lifecycle adjective.'
    Assert-Equal $unknownTrackTerminal.audio.state 'unknown' 'A collection with unproven terminal tracks must remain unknown.'
    Assert-RunMonitorPythonContract -Path (Join-Path $runMonitorRoot "$unknownTrackRun.json")

    $wrongTrackRun = 'run-monitor-wrong-track-correlation'
    Write-MediaPipelineRunMonitorSeed -RunId $wrongTrackRun -CommandId 'wrong-track-command' -QueuePlanFingerprint 'wrong-track-plan' -AcceptedRows @([pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; job_id = "${wrongTrackRun}:item:1"
        source_identity = 'wrong-track-source'; source_identity_algorithm = 'source_identity_v2'
        source_path = 'C:\Media\WrongTrack.mkv'; display_name = 'WrongTrack.mkv'; parent_context = 'C:\Media'
        route = 'encode'; route_reason_code = 'policy'; route_reason = 'Encode policy'; intended_final_path = 'D:\Library\WrongTrack.mkv'
    }) | Out-Null
    Set-MediaPipelineRunMonitorAudioRecords -RunId $wrongTrackRun -JobId "${wrongTrackRun}:item:1" -FinalPolicy -Records @(
        [pscustomobject]@{ source_stream_index = 1; action = 'transcode'; planned_action = 'transcode'; source_codec = 'dts'; language = 'eng' }
    ) | Out-Null
    Set-MediaPipelineRunMonitorItemLifecycle -RunId $wrongTrackRun -JobId "${wrongTrackRun}:item:1" -State active | Out-Null
    Set-MediaPipelineRunMonitorStage -RunId $wrongTrackRun -JobId "${wrongTrackRun}:item:1" -StageId audio -State active -Indeterminate | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress -Kind audio -RunId $wrongTrackRun -JobId "${wrongTrackRun}:item:1" -TrackId 'audio:1' -State active -Indeterminate | Out-Null
    Set-MediaPipelineRunMonitorWorkers -RunId $wrongTrackRun -Workers @([pscustomobject]@{
        worker_id = 'wrong-track-worker'; job_id = "${wrongTrackRun}:item:1"; state = 'active'; stage_id = 'audio'
        route = 'encode'; updated_at = (Get-Date).ToUniversalTime().ToString('o'); numerator = $null; denominator = $null
    }) | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress -Kind audio -RunId $wrongTrackRun -JobId "${wrongTrackRun}:item:1" -TrackId 'audio:999' -State active -Indeterminate | Out-Null
    $wrongTrackPayload = Get-Content -LiteralPath (Join-Path $runMonitorRoot "$wrongTrackRun.json") -Raw | ConvertFrom-Json -Depth 40
    $wrongTrackItem = $wrongTrackPayload.items[0]
    $wrongTrackStage = @($wrongTrackItem.stages | Where-Object stage_id -eq audio)[0]
    Assert-Equal $wrongTrackItem.audio.state 'unknown' 'An uncorrelated track update must suppress collection current state.'
    Assert-Equal $wrongTrackItem.audio.tracks[0].state 'unknown' 'An uncorrelated track update must suppress the prior active track claim.'
    Assert-Equal $wrongTrackItem.audio.tracks[0].progress.kind 'none' 'A suppressed active track must not retain indeterminate progress.'
    Assert-Equal $wrongTrackStage.state 'unknown' 'An uncorrelated track update must suppress the canonical active stage claim.'
    Assert-Equal $wrongTrackStage.progress.kind 'none' 'A suppressed canonical stage must not retain indeterminate progress.'
    Assert-Equal @($wrongTrackPayload.current_workers).Count 0 'An uncorrelated track update must remove the correlated controller worker claim.'
    Set-MediaPipelineRunMonitorStage -RunId $wrongTrackRun -JobId "${wrongTrackRun}:item:1" -StageId transcode -State active -Indeterminate | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress -Kind audio -RunId $wrongTrackRun -JobId "${wrongTrackRun}:item:1" -TrackId 'audio:missing' -State active -Indeterminate | Out-Null
    $laterStageItem = (Get-Content -LiteralPath (Join-Path $runMonitorRoot "$wrongTrackRun.json") -Raw | ConvertFrom-Json -Depth 40).items[0]
    Assert-Equal @($laterStageItem.stages | Where-Object state -eq active)[0].stage_id 'transcode' 'A late uncorrelated audio update must not overwrite a later exact backend stage.'

    $unclosedStageRun = 'run-monitor-unclosed-stage-terminal'
    Write-MediaPipelineRunMonitorSeed -RunId $unclosedStageRun -CommandId 'unclosed-stage-command' -QueuePlanFingerprint 'unclosed-stage-plan' -AcceptedRows @([pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; job_id = "${unclosedStageRun}:item:1"
        source_identity = 'unclosed-stage-source'; source_identity_algorithm = 'source_identity_v2'
        source_path = 'C:\Media\UnclosedStage.mkv'; display_name = 'UnclosedStage.mkv'; parent_context = 'C:\Media'
        route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'; intended_final_path = 'D:\Library\UnclosedStage.mkv'
    }) | Out-Null
    Set-MediaPipelineRunMonitorStage -RunId $unclosedStageRun -JobId "${unclosedStageRun}:item:1" -StageId copy_to_scratch -State active -Detail 'Copying with unknown total.' -Indeterminate | Out-Null
    Set-MediaPipelineRunMonitorItemLifecycle -RunId $unclosedStageRun -JobId "${unclosedStageRun}:item:1" -State completed -Reason 'Exact terminal item proof arrived.' | Out-Null
    $unclosedTerminalItem = (Get-Content -LiteralPath (Join-Path $runMonitorRoot "$unclosedStageRun.json") -Raw | ConvertFrom-Json -Depth 40).items[0]
    $unclosedCopyStage = @($unclosedTerminalItem.stages | Where-Object stage_id -eq copy_to_scratch)[0]
    Assert-Equal $unclosedCopyStage.state 'unknown' 'Terminal item success must not infer completion of a still-active stage.'
    Assert-Equal $unclosedCopyStage.evidence.provenance 'unknown' 'An unclosed stage must disclose unknown terminal provenance.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$unclosedCopyStage.completed_at)) 'An unproven stage must not receive a completion timestamp.'

    $failedTrackRun = 'run-monitor-failed-track-terminal'
    Write-MediaPipelineRunMonitorSeed -RunId $failedTrackRun -CommandId 'failed-track-command' -QueuePlanFingerprint 'failed-track-plan' -AcceptedRows @([pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; job_id = "${failedTrackRun}:item:1"
        source_identity = 'failed-track-source'; source_identity_algorithm = 'source_identity_v2'
        source_path = 'C:\Media\FailedTrack.mkv'; display_name = 'FailedTrack.mkv'; parent_context = 'C:\Media'
        route = 'encode'; route_reason_code = 'policy'; route_reason = 'Encode policy'; intended_final_path = 'D:\Library\FailedTrack.mkv'
    }) | Out-Null
    Set-MediaPipelineRunMonitorAudioRecords -RunId $failedTrackRun -JobId "${failedTrackRun}:item:1" -FinalPolicy -Records @(
        [pscustomobject]@{ source_stream_index = 1; action = 'transcode'; planned_action = 'transcode'; source_codec = 'dts'; language = 'eng' },
        [pscustomobject]@{ source_stream_index = 2; action = 'copy'; planned_action = 'passthrough'; source_codec = 'aac'; language = 'jpn' }
    ) | Out-Null
    Set-MediaPipelineRunMonitorTrackProgress -Kind audio -RunId $failedTrackRun -JobId "${failedTrackRun}:item:1" -TrackId 'audio:1' -CurrentAction transcode -State active -Indeterminate | Out-Null
    Set-MediaPipelineRunMonitorItemLifecycle -RunId $failedTrackRun -JobId "${failedTrackRun}:item:1" -State failed -Reason 'Encoder failed.' -ReasonCode 'ENCODER_FAILED' -Retryable $true | Out-Null
    $failedTrackItem = (Get-Content -LiteralPath (Join-Path $runMonitorRoot "$failedTrackRun.json") -Raw | ConvertFrom-Json -Depth 40).items[0]
    Assert-Equal $failedTrackItem.audio.tracks[0].state 'failed' 'An active track must become failed when exact item failure evidence arrives.'
    Assert-Equal $failedTrackItem.audio.tracks[1].state 'unknown' 'A terminal item must not leave a track labeled awaiting evidence.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$failedTrackItem.audio.tracks[1].completed_at)) 'Unknown failed-item track evidence must not claim a completion timestamp.'
    Assert-Equal $failedTrackItem.audio.state 'failed' 'A collection with an exact failed track must expose failed state.'
    Assert-True (@($failedTrackItem.audio.tracks | Where-Object state -eq awaiting_evidence).Count -eq 0) 'Terminal track collections must never retain awaiting-evidence labels.'
    Assert-RunMonitorPythonContract -Path (Join-Path $runMonitorRoot "$failedTrackRun.json")

    $completionRun = 'run-monitor-completion'
    $completionRows = @(
        [pscustomobject]@{
            run_queue_index = 1; run_queue_total = 2; job_id = "${completionRun}:item:1"
            source_identity = 'completion-source-1'; source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\Completion\A.mkv'; display_name = 'A.mkv'; parent_context = 'C:\Media\Completion'
            route = 'remux'; route_reason_code = 'compatible'; route_reason = 'Compatible'; intended_final_path = 'D:\Library\A.mkv'
        },
        [pscustomobject]@{
            run_queue_index = 2; run_queue_total = 2; job_id = "${completionRun}:item:2"
            source_identity = 'completion-source-2'; source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\Completion\B.mkv'; display_name = 'B.mkv'; parent_context = 'C:\Media\Completion'
            route = 'encode'; route_reason_code = 'policy'; route_reason = 'Encode policy'; intended_final_path = 'D:\Library\B.mkv'
        }
    )
    Write-MediaPipelineRunMonitorSeed -RunId $completionRun -CommandId 'completion-command' -QueuePlanFingerprint 'completion-plan' -AcceptedRows $completionRows | Out-Null
    Set-MediaPipelineRunMonitorItemLifecycle -RunId $completionRun -JobId "${completionRun}:item:1" -State 'completed' | Out-Null
    Set-MediaPipelineRunMonitorStage -RunId $completionRun -JobId "${completionRun}:item:1" -StageId 'final_evidence' -State 'completed' -Detail 'Exact item result' -ReasonCode 'exact_terminal' -EvidenceSource 'process_file_result' | Out-Null

    $prematureCompletionRejected = $false
    try {
        Complete-MediaPipelineRunMonitor -RunId $completionRun -State 'completed' | Out-Null
    } catch {
        $prematureCompletionRejected = ([string]$_ -match 'nonterminal accepted item')
    }
    Assert-True $prematureCompletionRejected 'Run completion must fail closed while an accepted item lacks terminal evidence.'

    Complete-MediaPipelineRunMonitor `
        -RunId $completionRun `
        -State 'stopped' `
        -RemainingItemState 'stopped' `
        -Reason 'Stop After Current acknowledged at the dispatch boundary.' `
        -ReasonCode 'stop_after_current' | Out-Null
    $stoppedRun = Get-Content -LiteralPath (Join-Path $runMonitorRoot "$completionRun.json") -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $stoppedRun.run.lifecycle_state 'stopped' 'A partially dispatched graceful stop must terminate the run as stopped.'
    Assert-Equal $stoppedRun.items[0].lifecycle_state 'completed' 'Existing terminal item proof must survive run finalization.'
    Assert-Equal $stoppedRun.items[1].lifecycle_state 'stopped' 'Undispatched accepted item must remain visible as stopped.'
    Assert-Equal $stoppedRun.items[1].routes.final.state 'not_applicable' 'An undispatched stopped item must close Final route as not applicable.'
    Assert-Equal $stoppedRun.items[1].routes.final.reason_code 'stop_after_current' 'The non-applicable Final route must preserve the exact run completion reason.'
    Assert-Equal $stoppedRun.items[1].routes.final.evidence.source 'run_completion' 'The non-applicable Final route must name run completion as its terminal authority.'
    $preservedFinal = @($stoppedRun.items[0].stages | Where-Object stage_id -eq 'final_evidence')[0]
    Assert-Equal $preservedFinal.reason_code 'exact_terminal' 'Run finalization must not overwrite exact per-item final evidence.'

    # Cross-process writers must not overwrite one another. Each job updates a
    # distinct accepted item while sharing the same run file and named mutex.
    $concurrentRun = 'run-monitor-concurrent'
    $concurrentRows = for ($index = 1; $index -le 4; $index++) {
        [pscustomobject]@{
            run_queue_index = $index; run_queue_total = 4; job_id = "$concurrentRun:item:$index"
            source_identity = "concurrent-source-$index"; source_identity_algorithm = 'source_identity_v2'
            source_path = "C:\Media\Concurrent$index\Movie.mkv"; display_name = 'Movie.mkv'
            parent_context = "C:\Media\Concurrent$index"; route = 'encode'; route_reason_code = 'policy'
            route_reason = 'Encode policy'; intended_final_path = "D:\Library\Concurrent$index\Movie.mkv"
        }
    }
    Write-MediaPipelineRunMonitorSeed -RunId $concurrentRun -CommandId 'concurrent-command' -QueuePlanFingerprint 'concurrent-plan' -AcceptedRows $concurrentRows | Out-Null
    $jobs = for ($writer = 1; $writer -le 4; $writer++) {
        Start-Job -ScriptBlock {
            param($MutexPath, $ModulePath, $StateRoot, $LocalBasePath, $Suffix, $RunId, $Writer)
            $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $Suffix
            . $MutexPath
            . $ModulePath
            $script:LocalStateLayout = [pscustomobject]@{
                Root = $StateRoot
                RunMonitor = (Join-Path $StateRoot 'RunMonitor')
                Paths = [pscustomobject]@{ RunMonitor = (Join-Path $StateRoot 'RunMonitor') }
            }
            $LocalBase = $LocalBasePath
            for ($iteration = 1; $iteration -le 50; $iteration++) {
                Set-MediaPipelineRunMonitorStage `
                    -RunId $RunId `
                    -JobId "$RunId:item:$Writer" `
                    -StageId 'transcode' `
                    -State 'active' `
                    -Detail "writer-$Writer-update-$iteration" | Out-Null
            }
        } -ArgumentList $mutexPath, $monitorModulePath, $stateRoot, $tempRoot, $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX, $concurrentRun, $writer
    }
    $null = $jobs | Wait-Job -Timeout 120
    $jobErrors = @($jobs | Receive-Job -ErrorAction SilentlyContinue 2>&1 | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] })
    Assert-Equal $jobErrors.Count 0 'Concurrent Run Monitor writers reported errors.'
    Assert-True (@($jobs | Where-Object State -ne 'Completed').Count -eq 0) 'Concurrent Run Monitor writers did not complete.'
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue

    $concurrentPath = Join-Path $runMonitorRoot "$concurrentRun.json"
    $concurrent = Get-Content -LiteralPath $concurrentPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal @($concurrent.items).Count 4 'Concurrent updates changed accepted membership.'
    Assert-Equal $concurrent.write_sequence 201 'Concurrent updates lost one or more writes.'
    for ($writer = 1; $writer -le 4; $writer++) {
        $item = @($concurrent.items | Where-Object job_id -eq "$concurrentRun:item:$writer")[0]
        $transcode = @($item.stages | Where-Object stage_id -eq 'transcode')[0]
        Assert-Equal $transcode.detail "writer-$writer-update-50" "Writer $writer final update was lost."
    }
    Assert-Equal @(Get-ChildItem -LiteralPath $runMonitorRoot -Filter '*.tmp' -Force -ErrorAction SilentlyContinue).Count 0 'Temporary Run Monitor files were left behind.'
    Assert-Equal @(Get-ChildItem -LiteralPath $runMonitorRoot -Filter '*.bak' -Force -ErrorAction SilentlyContinue).Count 0 'Backup Run Monitor files were left behind.'

    Write-Host 'OK: Run Monitor state checks passed.'
} finally {
    if ($null -eq $priorSuffix) {
        Remove-Item Env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX -ErrorAction SilentlyContinue
    } else {
        $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $priorSuffix
    }
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
