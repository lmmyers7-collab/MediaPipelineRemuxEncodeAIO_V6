[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Run Monitor contract and persistence checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$contractModulePath = Join-Path $pipelineRoot 'engine\status\run_monitor_contract.ps1'
$persistenceModulePath = Join-Path $pipelineRoot 'engine\status\run_monitor_persistence.ps1'

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Get-MediaPipelineStableHash {
    param([Parameter(Mandatory)] [string] $Text)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
    return [System.Convert]::ToHexString($hash).ToLowerInvariant()
}

function Get-MediaPipelineWorkerMutexSuffix {
    return '_run_monitor_contract_checks'
}

Assert-True (Test-Path -LiteralPath $contractModulePath -PathType Leaf) 'Run Monitor contract module is missing.'
Assert-True (Test-Path -LiteralPath $persistenceModulePath -PathType Leaf) 'Run Monitor persistence module is missing.'
. $contractModulePath
. $persistenceModulePath

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-run-monitor-contract-tests-' + [guid]::NewGuid().ToString('N'))
try {
    $runMonitorRoot = Join-Path $tempRoot 'State\RunMonitor'
    New-Item -ItemType Directory -Path $runMonitorRoot -Force | Out-Null
    $script:LocalStateLayout = [pscustomobject]@{
        Root       = Join-Path $tempRoot 'State'
        RunMonitor = $runMonitorRoot
        Paths      = [pscustomobject]@{ RunMonitor = $runMonitorRoot }
    }
    $LocalBase = $tempRoot

    Assert-Equal (Assert-MediaPipelineRunMonitorSafeRunId -RunId ' focused-run ') 'focused-run' 'Safe Run Monitor IDs should be trimmed.'
    foreach ($unsafeRunId in @('latest', '..\escape', 'run/id', '')) {
        $rejected = $false
        try {
            Assert-MediaPipelineRunMonitorSafeRunId -RunId $unsafeRunId | Out-Null
        } catch {
            $rejected = $true
        }
        Assert-True $rejected "Unsafe Run Monitor ID '$unsafeRunId' must be rejected."
    }

    $determinate = New-MediaPipelineRunMonitorProgress -Numerator 3 -Denominator 4
    Assert-Equal $determinate.kind 'determinate' 'Complete numeric progress evidence should be determinate.'
    Assert-Equal ([double]$determinate.numerator) 3 'Determinate progress should preserve its numerator.'
    Assert-Equal ([double]$determinate.denominator) 4 'Determinate progress should preserve its denominator.'
    Assert-Equal (New-MediaPipelineRunMonitorProgress -Indeterminate).kind 'indeterminate' 'Explicit unknown progress should remain indeterminate.'
    $partialProgressRejected = $false
    try {
        New-MediaPipelineRunMonitorProgress -Numerator 1 | Out-Null
    } catch {
        $partialProgressRejected = $true
    }
    Assert-True $partialProgressRejected 'Partial determinate progress must fail closed.'

    $availableRoute = New-MediaPipelineRunMonitorRouteEvidence -State available -Route remux -Reason 'Container normalization' -ReasonCode 'container_only'
    Assert-Equal $availableRoute.route 'remux' 'Available route evidence should preserve the backend route.'
    $awaitingRoute = New-MediaPipelineRunMonitorRouteEvidence -State awaiting_evidence -Route encode -Reason 'stale' -ReasonCode 'stale'
    Assert-Equal $awaitingRoute.route '' 'Awaiting route evidence must not retain an unverified route.'
    Assert-Equal $awaitingRoute.reason '' 'Awaiting route evidence must not retain an unverified reason.'

    $runId = 'focused-run'
    $item = [pscustomobject]@{
        job_id               = "${runId}:item:1"
        source_identity      = [pscustomobject]@{ value = 'focused-source'; algorithm = 'source_identity_v2' }
        source_path          = 'C:\Media\Focused.mkv'
        display_name         = 'Focused.mkv'
        display_name_evidence = [pscustomobject]@{ source = 'plex_destination_plan.v1'; provenance = 'queue_plan' }
        parent_context       = 'C:\Media'
        position             = 1
        total                = 1
        lifecycle_state      = 'queued'
        stages               = @(New-MediaPipelineRunMonitorStageLedger)
        routes               = [pscustomobject]@{ planned = $availableRoute }
        output               = [pscustomobject]@{ intended_final_path = 'D:\Library\Focused.mkv' }
    }
    $payload = [pscustomobject]@{
        schema_version = 'pipeline_run_monitor.v1'
        write_sequence = 1
        run = [pscustomobject]@{
            run_id = $runId
            command_id = 'focused-command'
            lifecycle_state = 'starting'
            updated_at = '2026-07-20T12:00:00Z'
            ended_at = ''
            accepted_queue = [pscustomobject]@{
                schema_version = 'queue_plan_fingerprint.v1'
                fingerprint = 'focused-fingerprint'
                accepted_count = 1
            }
            counts = [pscustomobject]@{
                accepted = 1; queued = 1; active = 0; completed = 0; failed = 0
                skipped = 0; blocked = 0; review = 0; parked = 0; stopped = 0
            }
        }
        items = @($item)
        current_workers = @()
    }

    Assert-True (Assert-MediaPipelineRunMonitorPayload -Payload $payload -RunId $runId) 'A correlated Run Monitor payload should validate.'
    $signatureBefore = Get-MediaPipelineRunMonitorMembershipSignature -Payload $payload
    $signatureAfter = Get-MediaPipelineRunMonitorMembershipSignature -Payload $payload
    Assert-Equal $signatureAfter $signatureBefore 'Run Monitor membership signatures must be deterministic.'

    $monitorPath = Get-MediaPipelineRunMonitorPath -RunId $runId
    Write-MediaPipelineRunMonitorJsonAtomic -Path $monitorPath -InputObject $payload | Out-Null
    Assert-True (Test-Path -LiteralPath $monitorPath -PathType Leaf) 'Atomic Run Monitor persistence should create the target JSON file.'
    $monitorBytes = [System.IO.File]::ReadAllBytes($monitorPath)
    $hasUtf8Bom = $monitorBytes.Length -ge 3 -and $monitorBytes[0] -eq 0xEF -and $monitorBytes[1] -eq 0xBB -and $monitorBytes[2] -eq 0xBF
    Assert-True (-not $hasUtf8Bom) 'Run Monitor JSON persistence must remain UTF-8 without BOM.'
    $persisted = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $persisted.run.run_id $runId 'Atomic persistence should preserve the Run Monitor identity.'

    $acceptedRows = @(Get-MediaPipelineRunMonitorAcceptedSeedRows -RunId $runId -CommandId 'focused-command' -ExpectedFingerprint 'focused-fingerprint')
    Assert-Equal $acceptedRows.Count 1 'Accepted seed reads should preserve the accepted workload count.'
    Assert-Equal $acceptedRows[0].display_name 'Focused.mkv' 'Accepted seed reads should preserve immutable planned naming evidence.'
    Assert-Equal $acceptedRows[0].route 'remux' 'Accepted seed reads should preserve planned route evidence.'

    Write-MediaPipelineRunMonitorPointer -RunId $runId -UpdatedAt '2026-07-20T12:00:01Z'
    $pointerPath = Get-MediaPipelineRunMonitorPointerPath
    $pointer = Get-Content -LiteralPath $pointerPath -Raw | ConvertFrom-Json
    Assert-Equal $pointer.run_id $runId 'Run Monitor pointer writes should preserve the selected run identity.'
    Assert-Equal $pointer.schema_version 'pipeline_run_monitor_pointer.v1' 'Run Monitor pointer writes should preserve their schema.'

    $mutexName = Get-MediaPipelineRunMonitorMutexName -RunId $runId
    Assert-True ($mutexName -match '^Global\\MediaPipelineRunMonitor_v1_[a-f0-9]{64}_run_monitor_contract_checks$') 'Run Monitor mutex identity should be path-derived and worker-suffixed.'

    function Write-TerminalHistoryPayload {
        param([Parameter(Mandatory)] [string] $HistoryRunId, [Parameter(Mandatory)] [string] $UpdatedAt)
        $historyPayload = $payload | ConvertTo-Json -Depth 40 | ConvertFrom-Json -Depth 40
        $historyPayload.run.run_id = $HistoryRunId
        $historyPayload.run.command_id = "$HistoryRunId-command"
        $historyPayload.run.lifecycle_state = 'completed'
        $historyPayload.run.updated_at = $UpdatedAt
        $historyPayload.run.ended_at = $UpdatedAt
        $historyPayload.items[0].job_id = "${HistoryRunId}:item:1"
        $historyPayload.items[0].source_identity.value = "$HistoryRunId-source"
        $historyPayload.items[0].lifecycle_state = 'completed'
        $historyPath = Get-MediaPipelineRunMonitorPath -RunId $HistoryRunId
        Write-MediaPipelineRunMonitorJsonAtomic -Path $historyPath -InputObject $historyPayload | Out-Null
        return $historyPath
    }

    $oldHistoryPath = Write-TerminalHistoryPayload -HistoryRunId 'history-old' -UpdatedAt '2026-07-18T12:00:00Z'
    $newHistoryPath = Write-TerminalHistoryPayload -HistoryRunId 'history-new' -UpdatedAt '2026-07-19T12:00:00Z'
    Remove-MediaPipelineRunMonitorExpiredHistory -RetentionCount 1
    Assert-True (-not (Test-Path -LiteralPath $oldHistoryPath)) 'History retention should remove terminal records beyond the configured count.'
    Assert-True (Test-Path -LiteralPath $newHistoryPath -PathType Leaf) 'History retention should preserve the newest terminal record.'
    Assert-True (Test-Path -LiteralPath $monitorPath -PathType Leaf) 'History retention must not remove an active Run Monitor record.'

    Write-Host 'OK: Run Monitor contract and persistence checks passed.'
} finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
