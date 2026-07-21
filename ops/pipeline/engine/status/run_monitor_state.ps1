# ==============================================================================
# Backend-owned Run Once monitor state
# ==============================================================================
# This module persists one immutable accepted Backend Queue workload per run.
# Every read/modify/write occurs under a named cross-process mutex. Numeric-only
# heartbeats may be throttled by callers; semantic transitions are written at once.
# Legacy progress, filenames, log text, and route labels are never used to infer
# membership, stage completion, or terminal proof.
# ==============================================================================

$script:MediaPipelineRunMonitorStageIds = @(
    'accepted',
    'source_discovery',
    'copy_to_scratch',
    'probe',
    'route_decision',
    'audio',
    'subtitles',
    'transcode',
    'mux',
    'verification',
    'sidecar_writing',
    'publish',
    'final_evidence'
)
$script:MediaPipelineRunMonitorTerminalRunStates = @('completed','failed','blocked','review','stopped','force_stopped')
$script:MediaPipelineRunMonitorTerminalItemStates = @('completed','failed','skipped','blocked','review','parked','stopped')
$script:MediaPipelineRunMonitorLastNumericWrite = @{}

function Get-MediaPipelineRunMonitorTimestamp {
    return (Get-Date).ToUniversalTime().ToString('o')
}

function Get-MediaPipelineRunMonitorValue {
    param(
        $InputObject,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($null -eq $InputObject) { return $Default }
    if ($InputObject -is [System.Collections.IDictionary]) {
        if ($InputObject.Contains($Name)) { return $InputObject[$Name] }
        foreach ($key in @($InputObject.Keys)) {
            if ([string]$key -ieq $Name) { return $InputObject[$key] }
        }
        return $Default
    }
    $property = $InputObject.PSObject.Properties | Where-Object Name -ieq $Name | Select-Object -First 1
    if ($property) { return $property.Value }
    return $Default
}

function Set-MediaPipelineRunMonitorProperty {
    param(
        [Parameter(Mandatory)] $InputObject,
        [Parameter(Mandatory)] [string] $Name,
        $Value
    )

    if ($InputObject -is [System.Collections.IDictionary]) {
        $InputObject[$Name] = $Value
        return
    }
    $InputObject | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
}

function Assert-MediaPipelineRunMonitorSafeRunId {
    param([Parameter(Mandatory)] [string] $RunId)

    $normalized = $RunId.Trim()
    if ($normalized -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' -or $normalized -ieq 'latest') {
        throw 'Run Monitor run_id contains unsafe path characters.'
    }
    return $normalized
}

function Get-MediaPipelineRunMonitorRoot {
    $root = ''
    try {
        if ($script:LocalStateLayout -and $script:LocalStateLayout.PSObject.Properties['RunMonitor']) {
            $root = [string]$script:LocalStateLayout.RunMonitor
        }
        if ([string]::IsNullOrWhiteSpace($root) -and
            $script:LocalStateLayout -and $script:LocalStateLayout.Paths -and
            $script:LocalStateLayout.Paths.PSObject.Properties['RunMonitor']) {
            $root = [string]$script:LocalStateLayout.Paths.RunMonitor
        }
        if ([string]::IsNullOrWhiteSpace($root) -and $script:LocalStateLayout -and $script:LocalStateLayout.Root) {
            $root = Join-Path ([string]$script:LocalStateLayout.Root) 'RunMonitor'
        }
    } catch {}
    if ([string]::IsNullOrWhiteSpace($root)) {
        try {
            if (-not [string]::IsNullOrWhiteSpace([string]$LocalBase)) {
                $root = Join-Path (Join-Path ([string]$LocalBase) 'State') 'RunMonitor'
            }
        } catch {}
    }
    if ([string]::IsNullOrWhiteSpace($root)) {
        throw 'Run Monitor root is unavailable because LocalBase state has not been resolved.'
    }
    return [System.IO.Path]::GetFullPath($root)
}

function Get-MediaPipelineRunMonitorPath {
    param([Parameter(Mandatory)] [string] $RunId)
    $safeRunId = Assert-MediaPipelineRunMonitorSafeRunId -RunId $RunId
    return Join-Path (Get-MediaPipelineRunMonitorRoot) "$safeRunId.json"
}

function Get-MediaPipelineRunMonitorPointerPath {
    return Join-Path (Get-MediaPipelineRunMonitorRoot) 'latest.json'
}

function Get-MediaPipelineRunMonitorMutexName {
    param([Parameter(Mandatory)] [string] $RunId)
    $path = Get-MediaPipelineRunMonitorPath -RunId $RunId
    $canonical = [System.IO.Path]::GetFullPath($path).ToLowerInvariant()
    $hash = Get-MediaPipelineStableHash -Text $canonical
    return "Global\MediaPipelineRunMonitor_v1_${hash}$(Get-MediaPipelineWorkerMutexSuffix)"
}

function New-MediaPipelineRunMonitorEvidence {
    param(
        [string] $Source = 'pipeline_engine',
        [ValidateSet('backend_confirmed','queue_plan','engine_event','worker_heartbeat','terminal','inferred','unknown')]
        [string] $Provenance = 'backend_confirmed',
        [string] $RecordedAt = ''
    )
    if ([string]::IsNullOrWhiteSpace($RecordedAt)) { $RecordedAt = Get-MediaPipelineRunMonitorTimestamp }
    return [ordered]@{
        source      = if ([string]::IsNullOrWhiteSpace($Source)) { 'pipeline_engine' } else { $Source }
        provenance  = $Provenance
        recorded_at = $RecordedAt
    }
}

function New-MediaPipelineRunMonitorProgress {
    param(
        $Numerator = $null,
        $Denominator = $null,
        [switch] $Indeterminate
    )

    $hasNumerator = $null -ne $Numerator -and "${Numerator}" -ne ''
    $hasDenominator = $null -ne $Denominator -and "${Denominator}" -ne ''
    if ($hasNumerator -and $hasDenominator) {
        $number = [double]$Numerator
        $total = [double]$Denominator
        if ($number -lt 0 -or $total -le 0 -or $number -gt $total) {
            throw 'Determinate Run Monitor progress requires 0 <= numerator <= denominator and denominator > 0.'
        }
        return [ordered]@{ kind = 'determinate'; numerator = $number; denominator = $total }
    }
    if ($hasNumerator -or $hasDenominator) {
        throw 'Determinate Run Monitor progress requires both numerator and denominator.'
    }
    if ($Indeterminate) {
        return [ordered]@{ kind = 'indeterminate'; numerator = $null; denominator = $null }
    }
    return [ordered]@{ kind = 'none'; numerator = $null; denominator = $null }
}

function New-MediaPipelineRunMonitorRouteEvidence {
    param(
        [ValidateSet('available','awaiting_evidence','not_applicable','unknown')]
        [string] $State = 'awaiting_evidence',
        [string] $Route = '',
        [string] $Reason = '',
        [string] $ReasonCode = '',
        [string] $Source = 'pipeline_engine',
        [ValidateSet('backend_confirmed','queue_plan','engine_event','worker_heartbeat','terminal','inferred','unknown')]
        [string] $Provenance = 'backend_confirmed'
    )
    if ($State -eq 'available' -and [string]::IsNullOrWhiteSpace($Route)) {
        throw 'Available Run Monitor route evidence requires a route value.'
    } elseif ($State -ne 'available') {
        $Route = ''
        if ($State -eq 'awaiting_evidence') { $Reason = ''; $ReasonCode = '' }
    }
    return [ordered]@{
        state       = $State
        route       = $Route
        reason      = $Reason
        reason_code = $ReasonCode
        evidence    = New-MediaPipelineRunMonitorEvidence -Source $Source -Provenance $Provenance
    }
}

function New-MediaPipelineRunMonitorStageLedger {
    $now = Get-MediaPipelineRunMonitorTimestamp
    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($stageId in $script:MediaPipelineRunMonitorStageIds) {
        # Acceptance is the only stage that is intrinsically complete when a
        # monitor ledger is created. Source discovery is completed explicitly
        # by Write-MediaPipelineRunMonitorSeed only for the legacy/post-scan
        # seed path; pre-scan accepted workloads must begin at not_started.
        $completedAtSeed = $stageId -eq 'accepted'
        $rows.Add([ordered]@{
            stage_id    = $stageId
            state       = if ($completedAtSeed) { 'completed' } else { 'not_started' }
            started_at  = if ($completedAtSeed) { $now } else { '' }
            updated_at  = if ($completedAtSeed) { $now } else { '' }
            completed_at = if ($completedAtSeed) { $now } else { '' }
            detail      = if ($stageId -eq 'accepted') { 'Accepted into the backend-confirmed Run Once workload.' } elseif ($stageId -eq 'source_discovery') { 'Discovered and accepted by the backend Queue scan.' } else { '' }
            reason_code = ''
            progress    = New-MediaPipelineRunMonitorProgress
            evidence    = New-MediaPipelineRunMonitorEvidence -Source $(if ($completedAtSeed) { 'queue_snapshot' } else { 'pipeline_engine' }) -Provenance $(if ($completedAtSeed) { 'queue_plan' } else { 'backend_confirmed' }) -RecordedAt $now
        }) | Out-Null
    }
    return @($rows.ToArray())
}

function Write-MediaPipelineRunMonitorJsonAtomic {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] $InputObject,
        [int] $Depth = 40
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    }
    $leaf = Split-Path -Leaf $Path
    $token = [guid]::NewGuid().ToString('N')
    $temporary = Join-Path $directory ".$leaf.$token.tmp"
    $backup = Join-Path $directory ".$leaf.$token.bak"
    try {
        $json = ConvertTo-Json -InputObject $InputObject -Depth $Depth
        $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($json + "`n")
        $stream = [System.IO.FileStream]::new($temporary, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try {
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush($true)
        } finally {
            $stream.Dispose()
        }
        $null = Get-Content -LiteralPath $temporary -Raw -ErrorAction Stop | ConvertFrom-Json -Depth $Depth -ErrorAction Stop
        $delays = @(0, 50, 100, 200, 400, 800, 1000)
        $written = $false
        $lastError = $null
        foreach ($delay in $delays) {
            if ($delay -gt 0) { Start-Sleep -Milliseconds $delay }
            try {
                if ([System.IO.File]::Exists($Path)) {
                    [System.IO.File]::Replace($temporary, $Path, $backup, $true)
                    Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
                } else {
                    [System.IO.File]::Move($temporary, $Path)
                }
                $written = $true
                break
            } catch {
                $lastError = $_
            }
        }
        if (-not $written) {
            if ($lastError) { throw $lastError }
            throw "Run Monitor atomic write failed for $Path"
        }
        return $true
    } finally {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
    }
}

function Get-MediaPipelineRunMonitorMembershipSignature {
    param([Parameter(Mandatory)] $Payload)
    $rows = [System.Collections.Generic.List[string]]::new()
    $rows.Add(('{0}|{1}|{2}|{3}|{4}' -f `
        '__run__', ([string]$Payload.run.command_id), ([string]$Payload.run.accepted_queue.schema_version), `
        ([string]$Payload.run.accepted_queue.fingerprint), ([int]$Payload.run.accepted_queue.accepted_count))) | Out-Null
    foreach ($item in @($Payload.items)) {
        $rows.Add(('{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}|{9}|{10}|{11}|{12}|{13}' -f `
            ([string]$item.job_id), ([string]$item.source_identity.value), ([string]$item.source_identity.algorithm), `
            ([string]$item.source_path).ToLowerInvariant(), ([string]$item.display_name), `
            ([string]$item.display_name_evidence.source), ([string]$item.display_name_evidence.provenance), ([string]$item.parent_context), `
            ([int]$item.position), ([int]$item.total), ([string]$item.routes.planned.state), `
            ([string]$item.routes.planned.route), ([string]$item.routes.planned.reason), `
            ([string]$item.routes.planned.reason_code))) | Out-Null
    }
    return @($rows.ToArray()) -join "`n"
}

function Assert-MediaPipelineRunMonitorPayload {
    param(
        [Parameter(Mandatory)] $Payload,
        [Parameter(Mandatory)] [string] $RunId
    )

    if ([string]$Payload.schema_version -ne 'pipeline_run_monitor.v1') { throw 'Run Monitor schema_version is invalid.' }
    if ([string]$Payload.run.run_id -ne $RunId) { throw 'Run Monitor payload run_id does not match its file identity.' }
    if ([int]$Payload.write_sequence -lt 1) { throw 'Run Monitor write_sequence must be positive.' }
    $items = @($Payload.items)
    $acceptedCount = [int]$Payload.run.accepted_queue.accepted_count
    if ($items.Count -ne $acceptedCount) { throw 'Run Monitor accepted item count does not match accepted_queue.accepted_count.' }
    if ([int]$Payload.run.counts.accepted -ne $acceptedCount) { throw 'Run Monitor accepted count is not run-scoped.' }
    $jobIds = @($items | ForEach-Object { [string]$_.job_id })
    $sourceIds = @($items | ForEach-Object { [string]$_.source_identity.value })
    $positions = @($items | ForEach-Object { [int]$_.position })
    if (@($jobIds | Sort-Object -Unique).Count -ne $jobIds.Count) { throw 'Run Monitor contains duplicate job_id membership.' }
    if (@($sourceIds | Sort-Object -Unique).Count -ne $sourceIds.Count) { throw 'Run Monitor contains duplicate source identity membership.' }
    if (@($positions | Sort-Object -Unique).Count -ne $positions.Count) { throw 'Run Monitor contains duplicate run positions.' }
    for ($index = 0; $index -lt $items.Count; $index++) {
        $item = $items[$index]
        if ([int]$item.position -ne ($index + 1) -or [int]$item.total -ne $items.Count) {
            throw 'Run Monitor positions must be contiguous, ordered, one-based, and run-wide.'
        }
        $stageIds = @($item.stages | ForEach-Object { [string]$_.stage_id })
        if (($stageIds -join '|') -ne ($script:MediaPipelineRunMonitorStageIds -join '|')) {
            throw "Run Monitor item $($item.job_id) has an invalid stage ledger."
        }
        if (@($item.stages | Where-Object { [string]$_.state -eq 'active' }).Count -gt 1) {
            throw "Run Monitor item $($item.job_id) has more than one active stage."
        }
        if ([string]$item.lifecycle_state -in $script:MediaPipelineRunMonitorTerminalItemStates -and
            @($item.stages | Where-Object { [string]$_.state -eq 'active' }).Count -gt 0) {
            throw "Run Monitor terminal item $($item.job_id) retains an active stage."
        }
    }
    foreach ($worker in @($Payload.current_workers)) {
        if ([string]$worker.run_id -ne $RunId) { throw 'Run Monitor worker run_id is uncorrelated.' }
        if ([string]$worker.job_id -notin $jobIds) { throw 'Run Monitor worker job_id is uncorrelated.' }
    }
    if ([string]$Payload.run.lifecycle_state -in $script:MediaPipelineRunMonitorTerminalRunStates) {
        if (@($Payload.current_workers).Count -gt 0) { throw 'Terminal Run Monitor cannot retain current workers.' }
        if (@($items | Where-Object { [string]$_.lifecycle_state -notin $script:MediaPipelineRunMonitorTerminalItemStates }).Count -gt 0) {
            throw 'Terminal Run Monitor cannot retain nonterminal items.'
        }
        if ([string]::IsNullOrWhiteSpace([string]$Payload.run.ended_at)) { throw 'Terminal Run Monitor requires ended_at.' }
    }
    return $true
}

function Get-MediaPipelineRunMonitorAcceptedSeedRows {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $CommandId,
        [Parameter(Mandatory)] [string] $ExpectedFingerprint
    )

    $safeRunId = Assert-MediaPipelineRunMonitorSafeRunId -RunId $RunId
    $path = Get-MediaPipelineRunMonitorPath -RunId $safeRunId
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'RUN_MONITOR_ACCEPTED_SEED_MISSING: backend acceptance evidence must exist before pipeline spawn.'
    }
    $payload = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json -Depth 40 -ErrorAction Stop
    Assert-MediaPipelineRunMonitorPayload -Payload $payload -RunId $safeRunId | Out-Null
    if ([string]$payload.run.lifecycle_state -ne 'starting' -or
        [string]$payload.run.command_id -ne $CommandId -or
        [string]$payload.run.accepted_queue.schema_version -ne 'queue_plan_fingerprint.v1' -or
        [string]$payload.run.accepted_queue.fingerprint -ne $ExpectedFingerprint) {
        throw 'RUN_MONITOR_ACCEPTED_SEED_MISMATCH: backend pre-spawn identity does not match this process launch.'
    }

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($item in @($payload.items)) {
        $planned = $item.routes.planned
        $displayNameSource = [string]$item.display_name_evidence.source
        if ($displayNameSource -ne 'plex_destination_plan.v1') {
            throw 'RUN_MONITOR_ACCEPTED_NAME_EVIDENCE_MISSING: persisted run predates verified production naming evidence; refresh Queue and launch a new run.'
        }
        $rows.Add([ordered]@{
            job_id                    = [string]$item.job_id
            source_identity           = [string]$item.source_identity.value
            source_identity_algorithm = [string]$item.source_identity.algorithm
            source_path               = [string]$item.source_path
            display_name              = [string]$item.display_name
            display_name_source       = $displayNameSource
            parent_context            = [string]$item.parent_context
            run_queue_index           = [int]$item.position
            run_queue_total           = [int]$item.total
            route                     = if ([string]$planned.state -eq 'available') { [string]$planned.route } else { '' }
            route_reason              = if ([string]$planned.state -eq 'available') { [string]$planned.reason } else { '' }
            route_reason_code         = if ([string]$planned.state -eq 'available') { [string]$planned.reason_code } else { '' }
            intended_final_path       = [string]$item.output.intended_final_path
        }) | Out-Null
    }
    return @($rows.ToArray())
}

function Update-MediaPipelineRunMonitorCounts {
    param([Parameter(Mandatory)] $Payload)
    $items = @($Payload.items)
    $Payload.run.counts.accepted = [int]$items.Count
    foreach ($state in @('queued','active','completed','failed','skipped','blocked','review','parked','stopped')) {
        $Payload.run.counts.$state = [int]@($items | Where-Object { [string]$_.lifecycle_state -eq $state }).Count
    }
}

function Write-MediaPipelineRunMonitorPointer {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $UpdatedAt
    )
    $pointer = [ordered]@{
        schema_version = 'pipeline_run_monitor_pointer.v1'
        run_id         = $RunId
        updated_at     = $UpdatedAt
    }
    Write-MediaPipelineRunMonitorJsonAtomic -Path (Get-MediaPipelineRunMonitorPointerPath) -InputObject $pointer -Depth 5 | Out-Null
}

function Remove-MediaPipelineRunMonitorExpiredHistory {
    param([int] $RetentionCount = 10)
    $root = Get-MediaPipelineRunMonitorRoot
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { return }
    $retention = [math]::Max(1, $RetentionCount)
    $terminal = [System.Collections.Generic.List[object]]::new()
    foreach ($file in @(Get-ChildItem -LiteralPath $root -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
        if ($file.Name -eq 'latest.json') { continue }
        try {
            $payload = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -Depth 40 -ErrorAction Stop
            Assert-MediaPipelineRunMonitorPayload -Payload $payload -RunId ([System.IO.Path]::GetFileNameWithoutExtension($file.Name)) | Out-Null
            if ([string]$payload.run.lifecycle_state -in $script:MediaPipelineRunMonitorTerminalRunStates) {
                $terminal.Add([pscustomobject]@{ File = $file; UpdatedAt = [datetime]$payload.run.updated_at }) | Out-Null
            }
        } catch {}
    }
    $expired = @($terminal | Sort-Object UpdatedAt -Descending | Select-Object -Skip $retention)
    foreach ($entry in $expired) {
        Remove-Item -LiteralPath $entry.File.FullName -Force -ErrorAction SilentlyContinue
    }
}

function Write-MediaPipelineRunMonitorSeed {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $CommandId,
        [Parameter(Mandatory)] [string] $QueuePlanFingerprint,
        [Parameter(Mandatory)] [AllowEmptyCollection()] [array] $AcceptedRows,
        [ValidateSet('starting','running')] [string] $InitialRunState = 'running',
        [ValidateSet('not_started','completed')] [string] $SourceDiscoveryState = 'completed'
    )

    $safeRunId = Assert-MediaPipelineRunMonitorSafeRunId -RunId $RunId
    if ([string]::IsNullOrWhiteSpace($CommandId)) { throw 'Run Monitor seed requires command_id.' }
    if ([string]::IsNullOrWhiteSpace($QueuePlanFingerprint)) { throw 'Run Monitor seed requires the accepted Queue plan fingerprint.' }
    $rows = @($AcceptedRows | Sort-Object { [int](Get-MediaPipelineRunMonitorValue $_ 'run_queue_index' 0) })
    $total = [int]$rows.Count
    $now = Get-MediaPipelineRunMonitorTimestamp
    $items = [System.Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $rows.Count; $index++) {
        $row = $rows[$index]
        $position = [int](Get-MediaPipelineRunMonitorValue $row 'run_queue_index' 0)
        $rowTotal = [int](Get-MediaPipelineRunMonitorValue $row 'run_queue_total' 0)
        if ($position -ne ($index + 1) -or $rowTotal -ne $total) {
            throw 'Run Monitor seed rows must have contiguous run-wide positions and totals.'
        }
        $jobId = [string](Get-MediaPipelineRunMonitorValue $row 'job_id' '')
        $sourceIdentity = [string](Get-MediaPipelineRunMonitorValue $row 'source_identity' '')
        $sourcePath = [string](Get-MediaPipelineRunMonitorValue $row 'source_path' '')
        if ([string]::IsNullOrWhiteSpace($jobId) -or [string]::IsNullOrWhiteSpace($sourceIdentity) -or [string]::IsNullOrWhiteSpace($sourcePath)) {
            throw 'Run Monitor seed rows require job_id, source_identity, and source_path.'
        }
        $plannedRoute = [string](Get-MediaPipelineRunMonitorValue $row 'route' '')
        $plannedReason = [string](Get-MediaPipelineRunMonitorValue $row 'route_reason' '')
        $plannedReasonCode = [string](Get-MediaPipelineRunMonitorValue $row 'route_reason_code' '')
        if ([string]::IsNullOrWhiteSpace($plannedRoute)) { $plannedRoute = 'unknown' }
        $parentContext = [string](Get-MediaPipelineRunMonitorValue $row 'parent_context' '')
        if ([string]::IsNullOrWhiteSpace($parentContext)) { $parentContext = Split-Path -Parent $sourcePath }
        $displayName = ([string](Get-MediaPipelineRunMonitorValue $row 'display_name' '')).Trim()
        if ([string]::IsNullOrWhiteSpace($displayName)) {
            throw 'Run Monitor seed rows require display_name backend naming-plan evidence.'
        }
        $intendedFinalPath = [string](Get-MediaPipelineRunMonitorValue $row 'intended_final_path' '')
        $displayNameSource = [string](Get-MediaPipelineRunMonitorValue $row 'display_name_source' '')
        $displayNameEvidenceSource = if ($displayNameSource -eq 'plex_destination_plan.v1') {
            $displayNameSource
        } else {
            'legacy_internal_seed'
        }
        $displayNameEvidenceProvenance = if ($displayNameSource -eq 'plex_destination_plan.v1') { 'queue_plan' } else { 'unknown' }
        $stageLedger = @(New-MediaPipelineRunMonitorStageLedger)
        $acceptedStage = @($stageLedger | Where-Object { [string]$_.stage_id -eq 'accepted' })[0]
        $acceptedStage.state = 'completed'
        $acceptedStage.started_at = $now
        $acceptedStage.updated_at = $now
        $acceptedStage.completed_at = $now
        $acceptedStage.detail = 'Accepted into the fingerprinted Backend Queue Run Once workload.'
        $acceptedStage.evidence = New-MediaPipelineRunMonitorEvidence -Source 'queue_plan_acceptance' -Provenance 'queue_plan' -RecordedAt $now
        $discoveryStage = @($stageLedger | Where-Object { [string]$_.stage_id -eq 'source_discovery' })[0]
        if ($SourceDiscoveryState -eq 'completed') {
            $discoveryStage.state = 'completed'
            $discoveryStage.started_at = $now
            $discoveryStage.updated_at = $now
            $discoveryStage.completed_at = $now
            $discoveryStage.detail = 'Source discovery and Queue preflight completed before accepted membership was frozen.'
            $discoveryStage.evidence = New-MediaPipelineRunMonitorEvidence -Source 'queue_discovery' -Provenance 'queue_plan' -RecordedAt $now
        } else {
            $discoveryStage.detail = 'Accepted dry-run membership is durable; active source discovery has not started.'
            $discoveryStage.evidence = New-MediaPipelineRunMonitorEvidence -Source 'queue_plan_acceptance' -Provenance 'queue_plan' -RecordedAt $now
        }
        $items.Add([ordered]@{
            job_id            = $jobId
            source_identity    = [ordered]@{
                value     = $sourceIdentity
                algorithm = [string](Get-MediaPipelineRunMonitorValue $row 'source_identity_algorithm' 'source_identity_v2')
            }
            source_path        = $sourcePath
            display_name       = $displayName
            display_name_evidence = New-MediaPipelineRunMonitorEvidence -Source $displayNameEvidenceSource -Provenance $displayNameEvidenceProvenance -RecordedAt $now
            parent_context     = $parentContext
            position           = $position
            total              = $total
            lifecycle_state    = 'queued'
            lifecycle_evidence = New-MediaPipelineRunMonitorEvidence -Source 'queue_snapshot' -Provenance 'queue_plan' -RecordedAt $now
            updated_at         = $now
            routes             = [ordered]@{
                planned  = New-MediaPipelineRunMonitorRouteEvidence -State 'available' -Route $plannedRoute -Reason $plannedReason -ReasonCode $plannedReasonCode -Source 'queue_snapshot' -Provenance 'queue_plan'
                executed = New-MediaPipelineRunMonitorRouteEvidence -State 'awaiting_evidence'
                final    = New-MediaPipelineRunMonitorRouteEvidence -State 'awaiting_evidence'
            }
            stages             = @($stageLedger)
            audio              = [ordered]@{
                state = 'awaiting_evidence'; policy_final = $false; tracks = @(); evidence = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy'
            }
            subtitles          = [ordered]@{
                state = 'awaiting_evidence'; policy_final = $false; tracks = @(); evidence = New-MediaPipelineRunMonitorEvidence -Source 'subtitle_policy'
            }
            output             = [ordered]@{
                state = 'awaiting_evidence'; scratch_path = ''; working_output_path = ''; published_path = ''; parked_path = ''
                intended_final_path = $intendedFinalPath; size_bytes = $null; verification_state = 'unknown'; sidecars = @()
                evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_engine'
            }
            terminal_references = @()
            failure = [ordered]@{
                state = 'none'; reason_code = ''; reason = ''; retryable = $null; reference = ''
                evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_engine'
            }
            recovery = [ordered]@{
                owner = 'pipeline'; next_action = 'Wait for backend evidence.'; retryable = $null
                evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_engine'
            }
        }) | Out-Null
    }
    $payload = [ordered]@{
        schema_version = 'pipeline_run_monitor.v1'
        write_sequence = 1
        run = [ordered]@{
            run_id     = $safeRunId
            command_id = $CommandId
            mode        = 'once'
            scope       = 'backend_queue'
            accepted_queue = [ordered]@{
                schema_version = 'queue_plan_fingerprint.v1'
                fingerprint    = $QueuePlanFingerprint
                accepted_count = $total
            }
            lifecycle_state = $InitialRunState
            started_at       = $now
            updated_at       = $now
            ended_at         = ''
            stop_after_current = [ordered]@{
                state = 'not_requested'; requested_at = ''; evidence = New-MediaPipelineRunMonitorEvidence -Source 'control_flags'
            }
            outcome = [ordered]@{
                state = 'pending'; reason_code = ''; reason = ''; retryable = $null; owner = 'pipeline'
                next_action = 'Monitor the accepted Backend Queue workload.'
                evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_engine'
            }
            counts = [ordered]@{
                accepted = $total; queued = $total; active = 0; completed = 0; failed = 0; skipped = 0
                blocked = 0; review = 0; parked = 0; stopped = 0
            }
            evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_engine' -RecordedAt $now
        }
        items = @($items.ToArray())
        current_workers = @()
    }
    Assert-MediaPipelineRunMonitorPayload -Payload ([pscustomobject]$payload) -RunId $safeRunId | Out-Null
    $path = Get-MediaPipelineRunMonitorPath -RunId $safeRunId
    $mutexName = Get-MediaPipelineRunMonitorMutexName -RunId $safeRunId
    $written = Invoke-MediaPipelineMutexProtected -MutexName $mutexName -TimeoutMs 30000 -ScriptBlock {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $existing = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json -Depth 40 -ErrorAction Stop
            Assert-MediaPipelineRunMonitorPayload -Payload $existing -RunId $safeRunId | Out-Null
            if ((Get-MediaPipelineRunMonitorMembershipSignature -Payload $existing) -ne (Get-MediaPipelineRunMonitorMembershipSignature -Payload ([pscustomobject]$payload))) {
                throw 'Refusing to replace an existing Run Monitor with different accepted membership.'
            }
            throw 'Refusing to reseed an existing Run Monitor run_id.'
        }
        Write-MediaPipelineRunMonitorJsonAtomic -Path $path -InputObject $payload -Depth 40 | Out-Null
        Write-MediaPipelineRunMonitorPointer -RunId $safeRunId -UpdatedAt $now
        return [pscustomobject]$payload
    }
    Remove-MediaPipelineRunMonitorExpiredHistory -RetentionCount 10
    return $written
}

function Set-MediaPipelineRunMonitorSourceDiscoveryState {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [ValidateSet('active','completed')] [string] $State,
        [ValidateSet('','scanning','running')] [string] $RunState = '',
        [string] $ExpectedQueuePlanFingerprint = '',
        [string] $EvidenceSource = 'active_queue_rescan'
    )

    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        if (-not [string]::IsNullOrWhiteSpace($ExpectedQueuePlanFingerprint)) {
            $acceptedQueue = Get-MediaPipelineRunMonitorValue `
                (Get-MediaPipelineRunMonitorValue $payload 'run' $null) `
                'accepted_queue' `
                $null
            $actualFingerprint = [string](Get-MediaPipelineRunMonitorValue $acceptedQueue 'fingerprint' '')
            if (-not [string]::Equals($actualFingerprint, $ExpectedQueuePlanFingerprint, [System.StringComparison]::Ordinal)) {
                return $null
            }
        }
        $currentRunState = [string](Get-MediaPipelineRunMonitorValue (Get-MediaPipelineRunMonitorValue $payload 'run' $null) 'lifecycle_state' '')
        $sourceDiscoveryStages = @(
            foreach ($item in @($payload.items)) {
                @($item.stages | Where-Object { [string]$_.stage_id -eq 'source_discovery' })[0]
            }
        )
        if ($State -eq 'active') {
            if ($currentRunState -notin @('starting','scanning') -or
                @($sourceDiscoveryStages | Where-Object { [string]$_.state -notin @('not_started','active') }).Count -gt 0) {
                return $null
            }
        } elseif ($currentRunState -ne 'scanning' -or
            @($sourceDiscoveryStages | Where-Object { [string]$_.state -ne 'active' }).Count -gt 0) {
            return $null
        }
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        if (-not [string]::IsNullOrWhiteSpace($RunState)) {
            $payload.run.lifecycle_state = $RunState
        }
        foreach ($item in @($payload.items)) {
            $stage = @($item.stages | Where-Object { [string]$_.stage_id -eq 'source_discovery' })[0]
            if ($State -eq 'active') {
                $stage.state = 'active'
                if ([string]::IsNullOrWhiteSpace([string]$stage.started_at)) { $stage.started_at = $timestamp }
                $stage.updated_at = $timestamp
                $stage.completed_at = ''
                $stage.detail = 'Validating the accepted dry-run workload against active source discovery.'
            } else {
                $stage.state = 'completed'
                if ([string]::IsNullOrWhiteSpace([string]$stage.started_at)) { $stage.started_at = $timestamp }
                $stage.updated_at = $timestamp
                $stage.completed_at = $timestamp
                $stage.detail = 'Active source discovery completed and matched the accepted Queue workload.'
            }
            $stage.reason_code = ''
            $stage.progress = if ($State -eq 'active') {
                New-MediaPipelineRunMonitorProgress -Indeterminate
            } else {
                New-MediaPipelineRunMonitorProgress
            }
            $stage.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance 'backend_confirmed' -RecordedAt $timestamp
            $item.updated_at = $timestamp
        }
        return $payload
    } -SkipWriteWhenMutationReturnsNull
}

function New-MediaPipelineSourceDiscoveryPollHandler {
    <#
    Creates the pre-dispatch Run Once source-discovery heartbeat. This stage is
    run-wide: no per-file CurrentRunMonitorJobId exists until phase dispatch.
    Every poll therefore revalidates the exact ambient run ID and the immutable
    accepted Queue fingerprint before refreshing indeterminate discovery state.
    #>
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $AcceptedQueueFingerprint,
        [double] $MinimumIntervalSeconds = 15
    )

    $capturedRunId = Assert-MediaPipelineRunMonitorSafeRunId -RunId $RunId
    $capturedFingerprint = $AcceptedQueueFingerprint.Trim()
    if ([string]::IsNullOrWhiteSpace($capturedFingerprint)) {
        throw 'Source-discovery heartbeat requires the accepted Queue-plan fingerprint.'
    }
    if (-not (Get-Command -Name New-ThrottledNativePollHandler -ErrorAction SilentlyContinue)) {
        throw 'Source-discovery heartbeat throttling is unavailable.'
    }
    $pipelineRunVariable = Get-Variable -Name PipelineRunId -Scope Script -ErrorAction SilentlyContinue
    if ($null -eq $pipelineRunVariable -or
        -not [string]::Equals([string]$pipelineRunVariable.Value, $capturedRunId, [System.StringComparison]::Ordinal)) {
        return $null
    }
    $setDiscoveryStateCommand = Get-Command -Name Set-MediaPipelineRunMonitorSourceDiscoveryState -ErrorAction Stop
    $debugLogCommand = Get-Command -Name DebugLog -ErrorAction SilentlyContinue

    $writer = {
        param($ElapsedSeconds, $Process)

        # Capture the originating script-scope PSVariable and CommandInfo so
        # the nested throttling closure stays self-contained. Function-name or
        # $script: lookups inside GetNewClosure's dynamic module are not stable.
        if ($null -eq $pipelineRunVariable -or
            -not [string]::Equals([string]$pipelineRunVariable.Value, $capturedRunId, [System.StringComparison]::Ordinal)) {
            return $null
        }
        try {
            return & $setDiscoveryStateCommand `
                -RunId $capturedRunId `
                -State active `
                -RunState scanning `
                -ExpectedQueuePlanFingerprint $capturedFingerprint `
                -EvidenceSource 'source_discovery_heartbeat'
        } catch {
            if ($debugLogCommand) {
                & $debugLogCommand ("Source-discovery heartbeat unavailable: {0}" -f $_.Exception.Message)
            }
            return $null
        }
    }.GetNewClosure()

    return New-ThrottledNativePollHandler `
        -Handler $writer `
        -MinimumIntervalSeconds $MinimumIntervalSeconds
}

function Invoke-MediaPipelineRunMonitorUpdate {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [scriptblock] $Mutation,
        [switch] $NumericOnly,
        [switch] $SkipWriteWhenMutationReturnsNull,
        [int] $NumericThrottleMilliseconds = 750,
        [int] $TimeoutMs = 30000
    )

    $safeRunId = Assert-MediaPipelineRunMonitorSafeRunId -RunId $RunId
    if ($NumericOnly) {
        $last = $script:MediaPipelineRunMonitorLastNumericWrite[$safeRunId]
        $nowTicks = [System.Diagnostics.Stopwatch]::GetTimestamp()
        $frequency = [double][System.Diagnostics.Stopwatch]::Frequency
        if ($last) {
            $elapsedMs = (($nowTicks - [long]$last) / $frequency) * 1000.0
            if ($elapsedMs -lt [math]::Max(0, $NumericThrottleMilliseconds)) { return $null }
        }
        $script:MediaPipelineRunMonitorLastNumericWrite[$safeRunId] = $nowTicks
    }
    $path = Get-MediaPipelineRunMonitorPath -RunId $safeRunId
    $mutexName = Get-MediaPipelineRunMonitorMutexName -RunId $safeRunId
    return Invoke-MediaPipelineMutexProtected -MutexName $mutexName -TimeoutMs $TimeoutMs -ScriptBlock {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Run Monitor does not exist for run_id $safeRunId" }
        $payload = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json -Depth 40 -ErrorAction Stop
        Assert-MediaPipelineRunMonitorPayload -Payload $payload -RunId $safeRunId | Out-Null
        $beforeMembership = Get-MediaPipelineRunMonitorMembershipSignature -Payload $payload
        $beforeSequence = [int64]$payload.write_sequence
        $beforeRunState = [string]$payload.run.lifecycle_state
        $beforeItemStates = @{}
        foreach ($item in @($payload.items)) { $beforeItemStates[[string]$item.job_id] = [string]$item.lifecycle_state }
        $mutated = & $Mutation $payload
        if ($SkipWriteWhenMutationReturnsNull -and $null -eq $mutated) {
            return $payload
        }
        if ($null -ne $mutated) { $payload = $mutated }
        if ((Get-MediaPipelineRunMonitorMembershipSignature -Payload $payload) -ne $beforeMembership) {
            throw 'Run Monitor accepted membership is immutable after seeding.'
        }
        if ($beforeRunState -in $script:MediaPipelineRunMonitorTerminalRunStates -and
            [string]$payload.run.lifecycle_state -ne $beforeRunState) {
            throw 'Run Monitor terminal run state cannot change.'
        }
        foreach ($item in @($payload.items)) {
            $beforeState = [string]$beforeItemStates[[string]$item.job_id]
            if ($beforeState -in $script:MediaPipelineRunMonitorTerminalItemStates -and
                [string]$item.lifecycle_state -ne $beforeState) {
                throw "Run Monitor terminal item state cannot change for $($item.job_id)."
            }
        }
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $payload.write_sequence = $beforeSequence + 1
        $payload.run.updated_at = $timestamp
        $payload.run.evidence.recorded_at = $timestamp
        Update-MediaPipelineRunMonitorCounts -Payload $payload
        Assert-MediaPipelineRunMonitorPayload -Payload $payload -RunId $safeRunId | Out-Null
        Write-MediaPipelineRunMonitorJsonAtomic -Path $path -InputObject $payload -Depth 40 | Out-Null
        Write-MediaPipelineRunMonitorPointer -RunId $safeRunId -UpdatedAt $timestamp
        return $payload
    }
}

function Get-MediaPipelineRunMonitorItem {
    param(
        [Parameter(Mandatory)] $Payload,
        [Parameter(Mandatory)] [string] $JobId
    )
    $matches = @($Payload.items | Where-Object { [string]$_.job_id -eq $JobId })
    if ($matches.Count -ne 1) { throw "Run Monitor job_id is not accepted exactly once: $JobId" }
    return $matches[0]
}

function New-MediaPipelineAcceptedDestinationNameEvidenceResult {
    param(
        [bool] $Applies = $false,
        [bool] $Verified = $false,
        [bool] $LegacyCompatible = $false,
        [string] $RunId = '',
        [string] $JobId = '',
        [string] $SourcePath = '',
        [string] $ExpectedDisplayName = '',
        [string] $DisplayNameSource = '',
        [string] $DisplayNameProvenance = '',
        [string] $QueuePlanFingerprintSchema = '',
        [string] $QueuePlanFingerprint = '',
        [string] $IntendedFinalPath = '',
        [string] $Reason = '',
        [string] $ErrorCode = ''
    )

    return [pscustomobject][ordered]@{
        SchemaVersion              = 'accepted_destination_name_evidence.v1'
        Applies                    = [bool]$Applies
        Verified                   = [bool]$Verified
        LegacyCompatible           = [bool]$LegacyCompatible
        RunId                      = [string]$RunId
        JobId                      = [string]$JobId
        SourcePath                 = [string]$SourcePath
        ExpectedDisplayName        = [string]$ExpectedDisplayName
        DisplayNameSource          = [string]$DisplayNameSource
        DisplayNameProvenance      = [string]$DisplayNameProvenance
        QueuePlanFingerprintSchema = [string]$QueuePlanFingerprintSchema
        QueuePlanFingerprint       = [string]$QueuePlanFingerprint
        IntendedFinalPath          = [string]$IntendedFinalPath
        Reason                     = [string]$Reason
        ErrorCode                  = [string]$ErrorCode
    }
}

function Get-MediaPipelineRunMonitorAcceptedNamingEvidence {
    <#
    .SYNOPSIS
    Reads immutable accepted destination-name evidence for one executing job.

    .DESCRIPTION
    This is a mutex-protected read only. It never increments write_sequence or
    rewrites the latest pointer. Direct/manual runs and persisted pre-fingerprint
    legacy rows remain compatible and return Applies=false. Once a Backend Queue
    run claims queue_plan_fingerprint.v1, missing, malformed, non-production, or
    mis-correlated accepted-name evidence fails closed.
    #>
    param(
        [string] $RunId = '',
        [string] $JobId = '',
        [string] $SourcePath = '',
        [int] $TimeoutMs = 30000
    )

    $runIdText = ([string]$RunId).Trim()
    $jobIdText = ([string]$JobId).Trim()
    if ([string]::IsNullOrWhiteSpace($runIdText) -or [string]::IsNullOrWhiteSpace($jobIdText)) {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -LegacyCompatible:$true `
            -RunId $runIdText `
            -JobId $jobIdText `
            -SourcePath $SourcePath `
            -Reason 'No exact Run Monitor run/job correlation is present; destination-name enforcement is not applicable.'
    }

    $safeRunId = ''
    $path = ''
    try {
        $safeRunId = Assert-MediaPipelineRunMonitorSafeRunId -RunId $runIdText
        $path = Get-MediaPipelineRunMonitorPath -RunId $safeRunId
    } catch {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -Applies:$true `
            -RunId $runIdText `
            -JobId $jobIdText `
            -SourcePath $SourcePath `
            -Reason "Accepted destination-name evidence could not be located: $($_.Exception.Message)" `
            -ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING'
    }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -Applies:$true `
            -RunId $safeRunId `
            -JobId $jobIdText `
            -SourcePath $SourcePath `
            -Reason "Accepted destination-name evidence is missing for run_id $safeRunId." `
            -ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING'
    }

    try {
        $mutexName = Get-MediaPipelineRunMonitorMutexName -RunId $safeRunId
        $payload = Invoke-MediaPipelineMutexProtected -MutexName $mutexName -TimeoutMs $TimeoutMs -ScriptBlock {
            $current = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json -Depth 40 -ErrorAction Stop
            Assert-MediaPipelineRunMonitorPayload -Payload $current -RunId $safeRunId | Out-Null
            return $current
        }
    } catch {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -Applies:$true `
            -RunId $safeRunId `
            -JobId $jobIdText `
            -SourcePath $SourcePath `
            -Reason "Accepted destination-name evidence could not be read or validated: $($_.Exception.Message)" `
            -ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING'
    }

    $mode = [string](Get-MediaPipelineRunMonitorValue $payload.run 'mode' '')
    $scope = [string](Get-MediaPipelineRunMonitorValue $payload.run 'scope' '')
    if ($mode -ne 'once' -or $scope -ne 'backend_queue') {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -LegacyCompatible:$true `
            -RunId $safeRunId `
            -JobId $jobIdText `
            -SourcePath $SourcePath `
            -Reason 'The correlated Run Monitor is not a verified Backend Queue Run Once workload.'
    }

    $acceptedQueue = Get-MediaPipelineRunMonitorValue $payload.run 'accepted_queue' $null
    $fingerprintSchema = [string](Get-MediaPipelineRunMonitorValue $acceptedQueue 'schema_version' '')
    $fingerprint = [string](Get-MediaPipelineRunMonitorValue $acceptedQueue 'fingerprint' '')
    try {
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $jobIdText
    } catch {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -Applies:$true `
            -RunId $safeRunId `
            -JobId $jobIdText `
            -SourcePath $SourcePath `
            -QueuePlanFingerprintSchema $fingerprintSchema `
            -QueuePlanFingerprint $fingerprint `
            -Reason "Accepted destination-name evidence is not correlated to this job: $($_.Exception.Message)" `
            -ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING'
    }

    $runClaimsVerifiedNaming = @($payload.items | Where-Object {
        $candidateEvidence = Get-MediaPipelineRunMonitorValue $_ 'display_name_evidence' $null
        [string](Get-MediaPipelineRunMonitorValue $candidateEvidence 'source' '') -eq 'plex_destination_plan.v1'
    }).Count -gt 0
    if ($fingerprintSchema -ne 'queue_plan_fingerprint.v1' -or [string]::IsNullOrWhiteSpace($fingerprint)) {
        if ($runClaimsVerifiedNaming) {
            return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
                -Applies:$true `
                -RunId $safeRunId `
                -JobId $jobIdText `
                -SourcePath ([string](Get-MediaPipelineRunMonitorValue $item 'source_path' $SourcePath)) `
                -ExpectedDisplayName ([string](Get-MediaPipelineRunMonitorValue $item 'display_name' '')) `
                -QueuePlanFingerprintSchema $fingerprintSchema `
                -QueuePlanFingerprint $fingerprint `
                -Reason 'A run that claims verified production naming evidence is missing its queue_plan_fingerprint.v1 authority.' `
                -ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING'
        }
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -LegacyCompatible:$true `
            -RunId $safeRunId `
            -JobId $jobIdText `
            -SourcePath $SourcePath `
            -QueuePlanFingerprintSchema $fingerprintSchema `
            -QueuePlanFingerprint $fingerprint `
            -Reason 'The correlated Backend Queue run predates fingerprinted accepted-name enforcement and contains no verified naming claim.'
    }

    $acceptedSourcePath = [string](Get-MediaPipelineRunMonitorValue $item 'source_path' '')
    $displayEvidence = Get-MediaPipelineRunMonitorValue $item 'display_name_evidence' $null
    $displayNameSource = [string](Get-MediaPipelineRunMonitorValue $displayEvidence 'source' '')
    $displayNameProvenance = [string](Get-MediaPipelineRunMonitorValue $displayEvidence 'provenance' '')
    $expectedDisplayName = [string](Get-MediaPipelineRunMonitorValue $item 'display_name' '')
    $outputEvidence = Get-MediaPipelineRunMonitorValue $item 'output' $null
    $intendedFinalPath = [string](Get-MediaPipelineRunMonitorValue $outputEvidence 'intended_final_path' '')

    if ($displayNameSource -ne 'plex_destination_plan.v1') {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -Applies:$true `
            -RunId $safeRunId `
            -JobId $jobIdText `
            -SourcePath $acceptedSourcePath `
            -ExpectedDisplayName $expectedDisplayName `
            -DisplayNameSource $displayNameSource `
            -DisplayNameProvenance $displayNameProvenance `
            -QueuePlanFingerprintSchema $fingerprintSchema `
            -QueuePlanFingerprint $fingerprint `
            -IntendedFinalPath $intendedFinalPath `
            -Reason "Fingerprint-backed accepted display-name source is '$displayNameSource', not plex_destination_plan.v1." `
            -ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING'
    }

    $missingReason = ''
    if ($displayNameProvenance -ne 'queue_plan') {
        $missingReason = "Accepted display-name provenance is '$displayNameProvenance', not queue_plan."
    } elseif ([string]::IsNullOrWhiteSpace($expectedDisplayName)) {
        $missingReason = 'Accepted production display name is blank.'
    } elseif ([string]::IsNullOrWhiteSpace($acceptedSourcePath)) {
        $missingReason = 'Accepted source path is blank.'
    } elseif (-not [string]::IsNullOrWhiteSpace([string]$SourcePath)) {
        $acceptedPathKey = try { [System.IO.Path]::GetFullPath($acceptedSourcePath) } catch { $acceptedSourcePath }
        $executingPathKey = try { [System.IO.Path]::GetFullPath([string]$SourcePath) } catch { [string]$SourcePath }
        if (-not [string]::Equals($acceptedPathKey, $executingPathKey, [System.StringComparison]::OrdinalIgnoreCase)) {
            $missingReason = "Accepted source path '$acceptedSourcePath' does not match executing source path '$SourcePath'."
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($missingReason)) {
        return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
            -Applies:$true `
            -RunId $safeRunId `
            -JobId $jobIdText `
            -SourcePath $acceptedSourcePath `
            -ExpectedDisplayName $expectedDisplayName `
            -DisplayNameSource $displayNameSource `
            -DisplayNameProvenance $displayNameProvenance `
            -QueuePlanFingerprintSchema $fingerprintSchema `
            -QueuePlanFingerprint $fingerprint `
            -IntendedFinalPath $intendedFinalPath `
            -Reason $missingReason `
            -ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING'
    }

    return New-MediaPipelineAcceptedDestinationNameEvidenceResult `
        -Applies:$true `
        -Verified:$true `
        -RunId $safeRunId `
        -JobId $jobIdText `
        -SourcePath $acceptedSourcePath `
        -ExpectedDisplayName $expectedDisplayName `
        -DisplayNameSource $displayNameSource `
        -DisplayNameProvenance $displayNameProvenance `
        -QueuePlanFingerprintSchema $fingerprintSchema `
        -QueuePlanFingerprint $fingerprint `
        -IntendedFinalPath $intendedFinalPath `
        -Reason 'Accepted production destination-name evidence is verified for execution.'
}

function ConvertTo-MediaPipelineRunMonitorStageId {
    param([string] $PipelineStage)
    $stage = ([string]$PipelineStage).Trim().ToLowerInvariant()
    switch -Regex ($stage) {
        '^(accepted)$' { return 'accepted' }
        '^(scan|scanning|source_discovery|discovery)$' { return 'source_discovery' }
        '^(copy|copying|copy_to_local|copy_to_scratch|scratch_copy)$' { return 'copy_to_scratch' }
        '^(probe|probing|source_probe|media_probe)$' { return 'probe' }
        '^(route|route_decision|decide|routing)$' { return 'route_decision' }
        '^(audio|audio_policy|audio_work)$' { return 'audio' }
        '^(subtitle|subtitles|subtitle_policy|subtitle_convert|subtitle_ocr|ass_convert|tx3g_convert|bdpgs_ocr|vobsub_ocr)$' { return 'subtitles' }
        '^(encode|encoding|encode_prepare|encode_safe|encode_cpu|encode_video|cpu_encode|hardware_encode|transcode)$' { return 'transcode' }
        '^(mux|muxing|encode_mux|remux_av|remux_prepare|remux_mux|remux_ffmpeg|remux_mkvmerge)$' { return 'mux' }
        '^(verify|verification|quality_verify|encode_verify|remux_verify)$' { return 'verification' }
        '^(sidecar|sidecars|sidecar_write|sidecar_writing)$' { return 'sidecar_writing' }
        '^(publish|publishing|push|pushing|pending_push|park)$' { return 'publish' }
        '^(complete|completed|final|final_evidence)$' { return 'final_evidence' }
        default { return '' }
    }
}

function Set-MediaPipelineRunMonitorStage {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)]
        [ValidateSet('accepted','source_discovery','copy_to_scratch','probe','route_decision','audio','subtitles','transcode','mux','verification','sidecar_writing','publish','final_evidence')]
        [string] $StageId,
        [Parameter(Mandatory)]
        [ValidateSet('not_started','active','completed','skipped','not_applicable','unknown','blocked','review','failed')]
        [string] $State,
        [string] $Detail = '',
        [string] $ReasonCode = '',
        $Numerator = $null,
        $Denominator = $null,
        [switch] $Indeterminate,
        [string] $EvidenceSource = 'pipeline_stage',
        [switch] $NumericOnly
    )

    $workerChildValue = $false
    try { $workerChildValue = [bool]$WorkerChild } catch {}
    $currentMonitorJobId = ''
    try { $currentMonitorJobId = [string]$script:CurrentRunMonitorJobId } catch {}
    $projectControllerWorker = (-not $workerChildValue -and
        [string]::Equals($currentMonitorJobId, $JobId, [System.StringComparison]::Ordinal))
    $controllerWorkerId = "controller:$PID"
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -NumericOnly:$NumericOnly -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        if ($State -eq 'active') {
            foreach ($other in @($item.stages | Where-Object { [string]$_.stage_id -ne $StageId -and [string]$_.state -eq 'active' })) {
                $other.state = 'unknown'
                $other.updated_at = $timestamp
                $other.detail = 'Superseded without explicit completion evidence.'
                $other.reason_code = 'completion_evidence_missing'
                $other.progress = New-MediaPipelineRunMonitorProgress
                $other.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_stage' -Provenance 'unknown' -RecordedAt $timestamp
            }
        }
        $stage = @($item.stages | Where-Object { [string]$_.stage_id -eq $StageId })[0]
        if ($State -eq 'active' -and [string]::IsNullOrWhiteSpace([string]$stage.started_at)) { $stage.started_at = $timestamp }
        $stage.state = $State
        $stage.updated_at = $timestamp
        $stage.completed_at = if ($State -in @('completed','skipped','not_applicable','blocked','review','failed')) { $timestamp } else { '' }
        $stage.detail = $Detail
        $stage.reason_code = $ReasonCode
        $stage.progress = New-MediaPipelineRunMonitorProgress -Numerator $Numerator -Denominator $Denominator -Indeterminate:$Indeterminate
        $stage.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -RecordedAt $timestamp
        $item.updated_at = $timestamp
        if ($State -eq 'active' -and [string]$item.lifecycle_state -notin $script:MediaPipelineRunMonitorTerminalItemStates) {
            $item.lifecycle_state = 'active'
            $item.lifecycle_evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -RecordedAt $timestamp
        }
        if ($projectControllerWorker) {
            $retainedWorkers = @($payload.current_workers | Where-Object {
                -not ([string]$_.job_id -eq $JobId -and [string]$_.worker_id -like 'controller:*')
            })
            if ($State -eq 'active') {
                $controllerRoute = if ([string]$item.routes.executed.state -eq 'available') { [string]$item.routes.executed.route } else { '' }
                $controllerWorker = [ordered]@{
                    worker_id = $controllerWorkerId
                    run_id = $RunId
                    job_id = $JobId
                    state = 'active'
                    stage_id = $StageId
                    route = $controllerRoute
                    progress = $stage.progress
                    updated_at = $timestamp
                    evidence = New-MediaPipelineRunMonitorEvidence -Source 'controller_worker' -Provenance 'worker_heartbeat' -RecordedAt $timestamp
                }
                $payload.current_workers = @($retainedWorkers + @($controllerWorker))
            } else {
                $payload.current_workers = @($retainedWorkers)
            }
        }
        return $payload
    }
}

function Set-MediaPipelineCurrentRunMonitorStage {
    param(
        [Parameter(Mandatory)] [string] $StageId,
        [Parameter(Mandatory)] [string] $State,
        [string] $Detail = '',
        [string] $ReasonCode = '',
        [string] $EvidenceSource = 'pipeline_stage',
        $Numerator = $null,
        $Denominator = $null,
        [switch] $Indeterminate,
        [switch] $NumericOnly
    )
    if ([string]::IsNullOrWhiteSpace([string]$script:PipelineRunId) -or
        [string]::IsNullOrWhiteSpace([string]$script:CurrentRunMonitorJobId)) {
        return $null
    }
    try {
        return Set-MediaPipelineRunMonitorStage `
            -RunId ([string]$script:PipelineRunId) `
            -JobId ([string]$script:CurrentRunMonitorJobId) `
            -StageId $StageId `
            -State $State `
            -Detail $Detail `
            -ReasonCode $ReasonCode `
            -EvidenceSource $EvidenceSource `
            -Numerator $Numerator `
            -Denominator $Denominator `
            -Indeterminate:$Indeterminate `
            -NumericOnly:$NumericOnly
    } catch {
        $script:RunMonitorPersistenceHealthy = $false
        Write-Log "Run Monitor stage evidence failed for ${StageId}: $($_.Exception.Message)" 'WARN'
        return $null
    }
}

function Set-MediaPipelineRunMonitorRouteEvidence {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] [ValidateSet('executed','final')] [string] $Authority,
        [ValidateSet('available','awaiting_evidence','not_applicable','unknown')] [string] $State = 'available',
        [string] $Route = '',
        [string] $ReasonCode = '',
        [string] $Reason = '',
        [string] $EvidenceSource = '',
        [switch] $OnlyIfAwaiting
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        if ($OnlyIfAwaiting -and [string]$item.routes.$Authority.state -ne 'awaiting_evidence') {
            return $payload
        }
        $provenance = if ($Authority -eq 'final') { 'terminal' } else { 'engine_event' }
        if ($Authority -eq 'final' -and [string]::IsNullOrWhiteSpace($EvidenceSource)) {
            throw 'Final route requires an exactly correlated terminal evidence source.'
        }
        $source = if ($Authority -eq 'final') { $EvidenceSource } else { 'route_selected_event' }
        $item.routes.$Authority = New-MediaPipelineRunMonitorRouteEvidence -State $State -Route $Route -Reason $Reason -ReasonCode $ReasonCode -Source $source -Provenance $provenance
        $item.updated_at = Get-MediaPipelineRunMonitorTimestamp
        return $payload
    }
}

function Set-MediaPipelineRunMonitorExecutedRoute {
    param(
        [string] $RunId,
        [string] $JobId,
        [string] $Route,
        [string] $ReasonCode = '',
        [string] $Reason = '',
        [switch] $OnlyIfAwaiting
    )
    return Set-MediaPipelineRunMonitorRouteEvidence -RunId $RunId -JobId $JobId -Authority executed -State available -Route $Route -ReasonCode $ReasonCode -Reason $Reason -OnlyIfAwaiting:$OnlyIfAwaiting
}

function Set-MediaPipelineRunMonitorFinalRoute {
    param([string] $RunId, [string] $JobId, [string] $Route, [string] $ReasonCode = '', [string] $Reason = '', [Parameter(Mandatory)] [string] $EvidenceSource)
    return Set-MediaPipelineRunMonitorRouteEvidence -RunId $RunId -JobId $JobId -Authority final -State available -Route $Route -ReasonCode $ReasonCode -Reason $Reason -EvidenceSource $EvidenceSource
}

function Set-MediaPipelineRunMonitorFinalRouteState {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] [ValidateSet('not_applicable','unknown')] [string] $State,
        [string] $ReasonCode = '',
        [string] $Reason = '',
        [Parameter(Mandatory)] [string] $EvidenceSource
    )
    return Set-MediaPipelineRunMonitorRouteEvidence `
        -RunId $RunId `
        -JobId $JobId `
        -Authority final `
        -State $State `
        -ReasonCode $ReasonCode `
        -Reason $Reason `
        -EvidenceSource $EvidenceSource
}

function Set-MediaPipelineRunMonitorAudioRecords {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [AllowEmptyCollection()] [array] $Records = @(),
        [switch] $FinalPolicy
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $recordsArray = @($Records | Where-Object { $null -ne $_ })
        $omitAll = @($recordsArray | Where-Object { [string](Get-MediaPipelineRunMonitorValue $_ 'action' '') -eq 'omit_all' }).Count -gt 0
        $tracks = [System.Collections.Generic.List[object]]::new()
        $policyTimestamp = Get-MediaPipelineRunMonitorTimestamp
        if (-not $omitAll) {
            $ordinal = 0
            foreach ($record in $recordsArray) {
                $action = ([string](Get-MediaPipelineRunMonitorValue $record 'action' '')).Trim().ToLowerInvariant()
                $streamIndexValue = Get-MediaPipelineRunMonitorValue $record 'source_stream_index' $ordinal
                $streamIndex = if ($null -eq $streamIndexValue -or "${streamIndexValue}" -eq '') { $ordinal } else { [int]$streamIndexValue }
                $sourceChannels = [int](Get-MediaPipelineRunMonitorValue $record 'source_channels' 0)
                $outputChannels = [int](Get-MediaPipelineRunMonitorValue $record 'output_channels' 0)
                $plannedAction = [string](Get-MediaPipelineRunMonitorValue $record 'planned_action' '')
                if ([string]::IsNullOrWhiteSpace($plannedAction)) {
                    $plannedAction = switch ($action) { 'copy' { 'passthrough' } 'drop' { 'drop' } default { $action } }
                }
                $trackState = if ($action -eq 'drop') { 'dropped' } else { 'awaiting_evidence' }
                $tracks.Add([ordered]@{
                    track_id       = "audio:$streamIndex"
                    stream_index   = $streamIndex
                    language       = [string](Get-MediaPipelineRunMonitorValue $record 'language' 'und')
                    source_codec   = [string](Get-MediaPipelineRunMonitorValue $record 'source_codec' '')
                    source_channels = $sourceChannels
                    source_layout  = [string](Get-MediaPipelineRunMonitorValue $record 'source_layout' '')
                    planned_action = $plannedAction
                    current_action = if ($action -eq 'drop') { 'drop' } else { '' }
                    state          = $trackState
                    started_at     = if ($action -eq 'drop') { $policyTimestamp } else { '' }
                    updated_at     = if ($action -eq 'drop') { $policyTimestamp } else { '' }
                    completed_at   = if ($action -eq 'drop') { $policyTimestamp } else { '' }
                    output_codec   = [string](Get-MediaPipelineRunMonitorValue $record 'output_codec' '')
                    output_channels = $outputChannels
                    output_layout  = [string](Get-MediaPipelineRunMonitorValue $record 'output_layout' '')
                    is_default     = [bool](Get-MediaPipelineRunMonitorValue $record 'is_default' $false)
                    reason_code    = [string](Get-MediaPipelineRunMonitorValue $record 'reason_code' '')
                    reason         = [string](Get-MediaPipelineRunMonitorValue $record 'reason' '')
                    progress       = New-MediaPipelineRunMonitorProgress
                    result         = if ($action -eq 'drop') { 'dropped' } else { '' }
                    evidence       = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy'
                }) | Out-Null
                $ordinal++
            }
        }
        $allAudioDropped = ($FinalPolicy -and $tracks.Count -gt 0 -and
            @($tracks.ToArray() | Where-Object { [string]$_.state -ne 'dropped' }).Count -eq 0)
        $item.audio = [ordered]@{
            state = if ($omitAll -or ($FinalPolicy -and $tracks.Count -eq 0)) { 'not_applicable' } elseif ($allAudioDropped) { 'completed' } else { 'awaiting_evidence' }
            policy_final = [bool]$FinalPolicy
            tracks = @($tracks.ToArray())
            evidence = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy'
        }
        if ($omitAll -or ($FinalPolicy -and $tracks.Count -eq 0) -or $allAudioDropped) {
            $audioStage = @($item.stages | Where-Object { [string]$_.stage_id -eq 'audio' })[0]
            $timestamp = Get-MediaPipelineRunMonitorTimestamp
            $audioStage.state = if ($allAudioDropped) { 'completed' } else { 'not_applicable' }
            $audioStage.started_at = if ([string]::IsNullOrWhiteSpace([string]$audioStage.started_at)) { $timestamp } else { $audioStage.started_at }
            $audioStage.updated_at = $timestamp
            $audioStage.completed_at = $timestamp
            $audioStage.detail = if ($allAudioDropped) { 'Backend audio policy explicitly dropped every source audio track.' } else { 'No audio tracks apply.' }
            $audioStage.progress = New-MediaPipelineRunMonitorProgress
            $audioStage.evidence = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy'
        }
        $item.updated_at = Get-MediaPipelineRunMonitorTimestamp
        return $payload
    }
}

function Complete-MediaPipelineRunMonitorAudioPolicy {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [string] $Detail = 'Audio policy complete'
    )

    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -SkipWriteWhenMutationReturnsNull -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $collection = $item.audio
        if (-not $collection -or -not [bool]$collection.policy_final) {
            # An aggregate legacy progress record cannot close policy evidence
            # until the backend has seeded the exact, final per-track plan.
            return $null
        }

        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $tracks = @($collection.tracks | Where-Object { $null -ne $_ })
        foreach ($track in $tracks) {
            $trackState = [string]$track.state
            if ($trackState -eq 'dropped') {
                # Drop is itself a terminal backend policy decision. It is not
                # long-running work and therefore never carries progress.
                $track.current_action = 'drop'
                if ([string]::IsNullOrWhiteSpace([string]$track.started_at)) { $track.started_at = $timestamp }
                $track.updated_at = $timestamp
                $track.completed_at = $timestamp
                $track.progress = New-MediaPipelineRunMonitorProgress
                if ([string]::IsNullOrWhiteSpace([string]$track.result)) { $track.result = 'dropped' }
                $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy' -RecordedAt $timestamp
                continue
            }

            if ($trackState -in @('active','awaiting_evidence')) {
                # Build-AudioArgs has selected policy, but copy/transcode has
                # not executed yet. Remove transient policy-loop claims while
                # preserving the profile-owned planned action and reason.
                $track.state = 'awaiting_evidence'
                $track.current_action = ''
                $track.started_at = ''
                $track.updated_at = $timestamp
                $track.completed_at = ''
                $track.progress = New-MediaPipelineRunMonitorProgress
                $track.result = ''
                $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy' -RecordedAt $timestamp
            } elseif ($trackState -eq 'unknown') {
                # Policy completion cannot repair an earlier correlation gap.
                # It can only ensure the unknown track is not presented as
                # current work or with a fabricated percentage.
                $track.current_action = ''
                $track.progress = New-MediaPipelineRunMonitorProgress
            }
        }

        $collection.state = if ($tracks.Count -eq 0 -or [string]$collection.state -eq 'not_applicable') {
            'not_applicable'
        } elseif (@($tracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) {
            'review'
        } elseif (@($tracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) {
            'failed'
        } elseif (@($tracks | Where-Object { [string]$_.state -eq 'unknown' }).Count -gt 0) {
            'unknown'
        } elseif (@($tracks | Where-Object { [string]$_.state -eq 'awaiting_evidence' }).Count -gt 0) {
            'awaiting_evidence'
        } else {
            'completed'
        }
        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy' -RecordedAt $timestamp

        $stage = @($item.stages | Where-Object { [string]$_.stage_id -eq 'audio' })[0]
        if ($stage -and [string]$stage.state -notin @('blocked','review','failed')) {
            if ([string]::IsNullOrWhiteSpace([string]$stage.started_at)) { $stage.started_at = $timestamp }
            $stage.state = if ($collection.state -eq 'not_applicable') { 'not_applicable' } else { 'completed' }
            $stage.updated_at = $timestamp
            $stage.completed_at = $timestamp
            $stage.detail = if ([string]::IsNullOrWhiteSpace($Detail)) { 'Audio policy complete' } else { $Detail }
            $stage.reason_code = ''
            $stage.progress = New-MediaPipelineRunMonitorProgress
            $stage.evidence = New-MediaPipelineRunMonitorEvidence -Source 'audio_policy' -RecordedAt $timestamp
        }

        $payload.current_workers = @($payload.current_workers | Where-Object {
            -not ([string]$_.job_id -eq $JobId -and [string]$_.stage_id -eq 'audio')
        })
        $item.updated_at = $timestamp
        return $payload
    }
}

function Start-MediaPipelineRunMonitorAudioWork {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] [string] $EvidenceSource,
        [string] $Detail = 'Correlated media-process audio work started.'
    )

    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -SkipWriteWhenMutationReturnsNull -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $collection = $item.audio
        if (-not $collection -or -not [bool]$collection.policy_final) { return $null }

        $primaryStages = @($item.stages | Where-Object { [string]$_.state -eq 'active' })
        if ($primaryStages.Count -ne 1 -or [string]$primaryStages[0].stage_id -notin @('transcode','mux')) {
            # Per-track audio work is concurrent evidence inside one exact
            # media process. It never creates a second canonical active stage.
            return $null
        }

        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $started = $false
        foreach ($track in @($collection.tracks | Where-Object { $null -ne $_ })) {
            if ([string]$track.state -notin @('awaiting_evidence','active','unknown')) { continue }
            $plannedAction = ([string]$track.planned_action).Trim().ToLowerInvariant()
            if ([string]::IsNullOrWhiteSpace($plannedAction)) {
                $track.state = 'unknown'
                $track.current_action = ''
                $track.updated_at = $timestamp
                $track.completed_at = ''
                $track.progress = New-MediaPipelineRunMonitorProgress
                $track.result = 'Correlated media work began without an exact backend-planned audio action.'
                $track.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance 'unknown' -RecordedAt $timestamp
                continue
            }

            $track.state = 'active'
            $track.current_action = $plannedAction
            if ([string]::IsNullOrWhiteSpace([string]$track.started_at)) { $track.started_at = $timestamp }
            $track.updated_at = $timestamp
            $track.completed_at = ''
            $track.progress = New-MediaPipelineRunMonitorProgress -Indeterminate
            $track.result = ''
            $track.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance 'backend_confirmed' -RecordedAt $timestamp
            $started = $true
        }
        if (-not $started -and
            @($collection.tracks | Where-Object { [string]$_.state -eq 'unknown' }).Count -eq 0) {
            return $null
        }

        $collection.state = if (@($collection.tracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) {
            'review'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) {
            'failed'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'active' }).Count -gt 0) {
            'active'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'awaiting_evidence' }).Count -gt 0) {
            'awaiting_evidence'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'unknown' }).Count -gt 0) {
            'unknown'
        } else {
            'completed'
        }
        $collection.evidence = New-MediaPipelineRunMonitorEvidence `
            -Source $EvidenceSource `
            -Provenance $(if ($collection.state -eq 'unknown') { 'unknown' } else { 'backend_confirmed' }) `
            -RecordedAt $timestamp

        $item.updated_at = $timestamp
        return $payload
    }
}

function End-MediaPipelineRunMonitorAudioWorkAttempt {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] [string] $EvidenceSource,
        [string] $ReasonCode = '',
        [string] $Detail = 'Correlated media-process audio work ended without successful completion.'
    )

    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -SkipWriteWhenMutationReturnsNull -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $collection = $item.audio
        if (-not $collection -or -not [bool]$collection.policy_final) { return $null }

        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $changed = $false
        foreach ($track in @($collection.tracks | Where-Object { $null -ne $_ })) {
            if ([string]$track.state -ne 'active') { continue }
            # A stopped, failed, timed-out, or policy-aborted native process is
            # no longer current work. Preserve the backend plan, but clear all
            # runtime action/timing/progress until another exact Process.Start
            # reactivates the track or terminal reconciliation authors proof.
            $track.state = 'unknown'
            $track.current_action = ''
            $track.started_at = ''
            $track.updated_at = $timestamp
            $track.completed_at = ''
            $track.progress = New-MediaPipelineRunMonitorProgress
            $attemptDetails = @($ReasonCode, $Detail) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }
            $track.result = $attemptDetails -join ': '
            $track.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance 'backend_confirmed' -RecordedAt $timestamp
            $changed = $true
        }
        if (-not $changed) { return $null }

        $collection.state = if (@($collection.tracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) {
            'review'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) {
            'failed'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'active' }).Count -gt 0) {
            'active'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'awaiting_evidence' }).Count -gt 0) {
            'awaiting_evidence'
        } else {
            'unknown'
        }
        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance 'backend_confirmed' -RecordedAt $timestamp
        $item.updated_at = $timestamp
        return $payload
    }
}

function Complete-MediaPipelineRunMonitorAudioWork {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] [string] $EvidenceSource,
        [string] $Detail = 'Correlated media-process audio work completed.'
    )

    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -SkipWriteWhenMutationReturnsNull -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $collection = $item.audio
        if (-not $collection -or -not [bool]$collection.policy_final) { return $null }
        $primaryStages = @($item.stages | Where-Object { [string]$_.state -eq 'active' })
        if ($primaryStages.Count -ne 1 -or [string]$primaryStages[0].stage_id -notin @('transcode','mux')) {
            return $null
        }

        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $changed = $false
        foreach ($track in @($collection.tracks | Where-Object { $null -ne $_ })) {
            if ([string]$track.state -eq 'active') {
                $track.state = 'completed'
                $track.updated_at = $timestamp
                $track.completed_at = $timestamp
                $track.progress = New-MediaPipelineRunMonitorProgress
                $track.result = $Detail
                $track.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance 'backend_confirmed' -RecordedAt $timestamp
                $changed = $true
            } elseif ([string]$track.state -eq 'awaiting_evidence') {
                # A successful process exit cannot prove a track that was never
                # correlated to its process start. Preserve that evidence gap.
                $track.state = 'unknown'
                $track.current_action = ''
                $track.updated_at = $timestamp
                $track.completed_at = ''
                $track.progress = New-MediaPipelineRunMonitorProgress
                $track.result = 'Media work completed without correlated runtime start evidence for this track.'
                $track.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance 'unknown' -RecordedAt $timestamp
                $changed = $true
            }
        }
        if (-not $changed) { return $null }

        $collection.state = if (@($collection.tracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) {
            'review'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) {
            'failed'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'active' }).Count -gt 0) {
            'active'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'awaiting_evidence' }).Count -gt 0) {
            'awaiting_evidence'
        } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'unknown' }).Count -gt 0) {
            'unknown'
        } else {
            'completed'
        }
        $collection.evidence = New-MediaPipelineRunMonitorEvidence `
            -Source $EvidenceSource `
            -Provenance $(if ($collection.state -eq 'completed') { 'backend_confirmed' } else { 'unknown' }) `
            -RecordedAt $timestamp

        $item.updated_at = $timestamp
        return $payload
    }
}

function Set-MediaPipelineRunMonitorSubtitleRecords {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [AllowEmptyCollection()] [array] $Records = @(),
        [switch] $FinalPolicy
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $tracks = [System.Collections.Generic.List[object]]::new()
        $hasReview = $false
        $ordinal = 0
        $policyTimestamp = Get-MediaPipelineRunMonitorTimestamp
        foreach ($record in @($Records | Where-Object { $null -ne $_ })) {
            $entry = Get-MediaPipelineRunMonitorValue $record 'Entry' $null
            $stream = Get-MediaPipelineRunMonitorValue $entry 'Stream' $null
            $streamIndexValue = Get-MediaPipelineRunMonitorValue $stream 'index' (Get-MediaPipelineRunMonitorValue $record 'source_stream_index' $null)
            $streamIndex = if ($null -eq $streamIndexValue -or "${streamIndexValue}" -eq '' -or [int]$streamIndexValue -lt 0) { $null } else { [int]$streamIndexValue }
            $sourceOrdinalValue = Get-MediaPipelineRunMonitorValue $entry 'SubtitleOrdinal' (Get-MediaPipelineRunMonitorValue $record 'subtitle_ordinal' $ordinal)
            $sourceOrdinal = if ($null -eq $sourceOrdinalValue -or "${sourceOrdinalValue}" -eq '') { $ordinal } else { [int]$sourceOrdinalValue }
            $language = [string](Get-MediaPipelineRunMonitorValue $entry 'Lang' (Get-MediaPipelineRunMonitorValue $record 'language' 'und'))
            $codec = ([string](Get-MediaPipelineRunMonitorValue $entry 'Codec' (Get-MediaPipelineRunMonitorValue $record 'source_codec' ''))).ToLowerInvariant()
            $action = ([string](Get-MediaPipelineRunMonitorValue $record 'Action' (Get-MediaPipelineRunMonitorValue $record 'action' ''))).ToLowerInvariant()
            $routesToReview = [bool](Get-MediaPipelineRunMonitorValue $record 'RoutesToReview' $false)
            $preserve = [bool](Get-MediaPipelineRunMonitorValue $record 'PreserveOriginal' (Get-MediaPipelineRunMonitorValue $record 'preserve' $false))
            $extract = [bool](Get-MediaPipelineRunMonitorValue $record 'Extract' (Get-MediaPipelineRunMonitorValue $record 'extract' $false))
            $convert = [bool](Get-MediaPipelineRunMonitorValue $record 'Convert' (Get-MediaPipelineRunMonitorValue $record 'convert' $false))
            $ocr = [bool](Get-MediaPipelineRunMonitorValue $record 'Ocr' (Get-MediaPipelineRunMonitorValue $record 'ocr' $false))
            $drop = [bool](Get-MediaPipelineRunMonitorValue $record 'Drop' (Get-MediaPipelineRunMonitorValue $record 'drop' ($action -eq 'drop')))
            $sourceType = [string](Get-MediaPipelineRunMonitorValue $record 'SourceType' (Get-MediaPipelineRunMonitorValue $record 'source_type' 'unknown'))
            $sourceKind = [string](Get-MediaPipelineRunMonitorValue $record 'SourceKind' (Get-MediaPipelineRunMonitorValue $record 'source_kind' 'unknown'))
            $plannedAction = [string](Get-MediaPipelineRunMonitorValue $record 'PlannedAction' (Get-MediaPipelineRunMonitorValue $record 'planned_action' ''))
            if ([string]::IsNullOrWhiteSpace($plannedAction)) {
                $plannedAction = if ($routesToReview) { 'review' } elseif ($drop) { 'drop' } elseif ($action) { $action } else { 'unknown' }
            }
            $trackState = if ($routesToReview) { 'review' } elseif ($drop) { 'dropped' } else { 'awaiting_evidence' }
            $trackId = [string](Get-MediaPipelineRunMonitorValue $record 'TrackId' (Get-MediaPipelineRunMonitorValue $record 'track_id' ''))
            if ([string]::IsNullOrWhiteSpace($trackId)) { $trackId = "subtitle:$sourceKind`:$sourceOrdinal" }
            if ($routesToReview) { $hasReview = $true }
            $tracks.Add([ordered]@{
                track_id       = $trackId
                stream_index   = $streamIndex
                source_ordinal = $sourceOrdinal
                language       = $language
                source_codec   = $codec
                source_type    = $sourceType
                source_kind    = $sourceKind
                preserve       = [bool]$preserve
                extract        = [bool]$extract
                convert        = [bool]$convert
                ocr            = [bool]$ocr
                write_embedded = [bool](Get-MediaPipelineRunMonitorValue $record 'WriteEmbedded' (Get-MediaPipelineRunMonitorValue $record 'write_embedded' $false))
                write_sidecar  = [bool](Get-MediaPipelineRunMonitorValue $record 'WriteSidecar' (Get-MediaPipelineRunMonitorValue $record 'write_sidecar' $false))
                planned_action = $plannedAction
                current_action = if ($routesToReview) { 'review' } elseif ($drop) { 'drop' } else { '' }
                state          = $trackState
                started_at     = if ($routesToReview -or $drop) { $policyTimestamp } else { '' }
                updated_at     = if ($routesToReview -or $drop) { $policyTimestamp } else { '' }
                completed_at   = if ($routesToReview -or $drop) { $policyTimestamp } else { '' }
                output_codec   = [string](Get-MediaPipelineRunMonitorValue $record 'OutputCodec' (Get-MediaPipelineRunMonitorValue $record 'output_codec' ''))
                output_location = [string](Get-MediaPipelineRunMonitorValue $record 'OutputLocation' (Get-MediaPipelineRunMonitorValue $record 'output_location' $(if ($drop) { 'dropped' } else { 'unknown' })))
                output_path    = [string](Get-MediaPipelineRunMonitorValue $record 'OutputPath' (Get-MediaPipelineRunMonitorValue $record 'output_path' ''))
                parked_path    = [string](Get-MediaPipelineRunMonitorValue $record 'ParkedPath' (Get-MediaPipelineRunMonitorValue $record 'parked_path' ''))
                intended_final_path = [string](Get-MediaPipelineRunMonitorValue $record 'IntendedFinalPath' (Get-MediaPipelineRunMonitorValue $record 'intended_final_path' ''))
                reason_code    = [string](Get-MediaPipelineRunMonitorValue $record 'ReviewErrorCode' '')
                reason         = if ($routesToReview) { [string](Get-MediaPipelineRunMonitorValue $record 'ReviewReason' '') } else { [string](Get-MediaPipelineRunMonitorValue $record 'PolicyReason' (Get-MediaPipelineRunMonitorValue $record 'reason' (Get-MediaPipelineRunMonitorValue $record 'OriginalPreserveReason' ''))) }
                step_index     = 0
                step_total     = 0
                step_name      = ''
                progress_unit  = ''
                cue_count      = $null
                progress       = New-MediaPipelineRunMonitorProgress
                result         = if ($drop) { 'dropped' } elseif ($routesToReview) { 'review_required' } else { '' }
                evidence       = New-MediaPipelineRunMonitorEvidence -Source 'subtitle_policy'
            }) | Out-Null
            $ordinal++
        }
        $allSubtitlesDropped = ($FinalPolicy -and $tracks.Count -gt 0 -and
            @($tracks.ToArray() | Where-Object { [string]$_.state -ne 'dropped' }).Count -eq 0)
        $item.subtitles = [ordered]@{
            state = if ($hasReview) { 'review' } elseif ($FinalPolicy -and $tracks.Count -eq 0) { 'not_applicable' } elseif ($allSubtitlesDropped) { 'completed' } else { 'awaiting_evidence' }
            policy_final = [bool]$FinalPolicy
            tracks = @($tracks.ToArray())
            evidence = New-MediaPipelineRunMonitorEvidence -Source 'subtitle_policy'
        }
        $subtitleStage = @($item.stages | Where-Object { [string]$_.stage_id -eq 'subtitles' })[0]
        if ($hasReview -or ($FinalPolicy -and $tracks.Count -eq 0) -or $allSubtitlesDropped) {
            $stageState = if ($hasReview) { 'review' } elseif ($allSubtitlesDropped) { 'completed' } else { 'not_applicable' }
            $timestamp = Get-MediaPipelineRunMonitorTimestamp
            $subtitleStage.state = $stageState
            $subtitleStage.started_at = if ([string]::IsNullOrWhiteSpace([string]$subtitleStage.started_at)) { $timestamp } else { $subtitleStage.started_at }
            $subtitleStage.updated_at = $timestamp
            $subtitleStage.completed_at = $timestamp
            $subtitleStage.detail = if ($hasReview) { 'Subtitle policy requires review.' } elseif ($allSubtitlesDropped) { 'Backend subtitle policy explicitly dropped every source subtitle track.' } else { 'No subtitle tracks apply.' }
            $subtitleStage.progress = New-MediaPipelineRunMonitorProgress
            $subtitleStage.evidence = New-MediaPipelineRunMonitorEvidence -Source 'subtitle_policy'
        }
        $item.updated_at = Get-MediaPipelineRunMonitorTimestamp
        return $payload
    }
}

function Set-MediaPipelineRunMonitorTrackProgress {
    param(
        [Parameter(Mandatory)] [ValidateSet('audio','subtitles')] [string] $Kind,
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [string] $TrackId = '',
        [int] $StreamIndex = -1,
        [string] $CurrentAction = '',
        [ValidateSet('awaiting_evidence','not_applicable','active','completed','failed','review','skipped','dropped','unknown')]
        [string] $State = 'active',
        $Numerator = $null,
        $Denominator = $null,
        [switch] $Indeterminate,
        [string] $Result = '',
        [string] $Reason = '',
        [string] $ReasonCode = '',
        [string] $OutputCodec = '',
        $OutputChannels = $null,
        [string] $OutputLayout = '',
        $IsDefault = $null,
        [ValidateSet('','embedded','external_sidecar','burned_into_video','dropped','not_applicable','unknown')]
        [string] $OutputLocation = '',
        [string] $OutputPath = '',
        [string] $ParkedPath = '',
        [string] $IntendedFinalPath = '',
        [int] $StepIndex = 0,
        [int] $StepTotal = 0,
        [string] $StepName = '',
        [ValidateSet('','items','pages','cues','frames','seconds','bytes','percent','unknown')]
        [string] $ProgressUnit = '',
        $CueCount = $null,
        [string] $EvidenceSource = '',
        [ValidateSet('','backend_confirmed','worker_heartbeat','terminal','unknown')]
        [string] $EvidenceProvenance = '',
        [switch] $NumericOnly
    )
    if ($StepIndex -lt 0 -or $StepTotal -lt 0 -or $StepIndex -gt $StepTotal) {
        throw 'Run Monitor subtitle step metadata requires 0 <= step_index <= step_total.'
    }
    $normalizedCueCount = $null
    if ($null -ne $CueCount -and "${CueCount}" -ne '') {
        try {
            $normalizedCueCount = [int]$CueCount
        } catch {
            throw 'Run Monitor subtitle cue_count must be a non-negative integer when provided.'
        }
        if ($normalizedCueCount -lt 0) {
            throw 'Run Monitor subtitle cue_count must be a non-negative integer when provided.'
        }
    }
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -NumericOnly:$NumericOnly -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $collection = $item.$Kind
        $matches = if (-not [string]::IsNullOrWhiteSpace($TrackId)) {
            @($collection.tracks | Where-Object { [string]$_.track_id -eq $TrackId })
        } elseif ($StreamIndex -ge 0) {
            @($collection.tracks | Where-Object { $null -ne $_.stream_index -and [int]$_.stream_index -eq $StreamIndex })
        } else {
            @()
        }
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        if ($matches.Count -ne 1) {
            $unknownEvidence = New-MediaPipelineRunMonitorEvidence -Source "${Kind}_progress" -Provenance 'unknown' -RecordedAt $timestamp
            foreach ($activeTrack in @($collection.tracks | Where-Object { [string]$_.state -eq 'active' })) {
                $activeTrack.state = 'unknown'
                $activeTrack.updated_at = $timestamp
                $activeTrack.completed_at = ''
                $activeTrack.progress = New-MediaPipelineRunMonitorProgress
                $activeTrack.result = 'Uncorrelated track progress was suppressed.'
                $activeTrack.evidence = $unknownEvidence
            }
            $collection.state = 'unknown'
            $collection.evidence = $unknownEvidence
            $stage = @($item.stages | Where-Object { [string]$_.stage_id -eq $Kind })[0]
            if ($stage -and [string]$stage.state -eq 'active') {
                $stage.state = 'unknown'
                $stage.updated_at = $timestamp
                $stage.completed_at = ''
                $stage.detail = 'Uncorrelated per-track progress was suppressed; current track work is unknown.'
                $stage.reason_code = 'track_progress_correlation_unknown'
                $stage.progress = New-MediaPipelineRunMonitorProgress
                $stage.evidence = $unknownEvidence
            }
            $payload.current_workers = @($payload.current_workers | Where-Object {
                -not ([string]$_.job_id -eq $JobId -and [string]$_.stage_id -eq $Kind)
            })
            $item.updated_at = $timestamp
            return $payload
        }
        $track = $matches[0]
        if (-not [string]::IsNullOrWhiteSpace($CurrentAction)) { $track.current_action = $CurrentAction }
        $track.state = $State
        if ($State -in @('active','not_applicable','completed','failed','review','skipped','dropped') -and
            [string]::IsNullOrWhiteSpace([string]$track.started_at)) { $track.started_at = $timestamp }
        $track.updated_at = $timestamp
        $track.completed_at = if ($State -in @('not_applicable','completed','failed','review','skipped','dropped')) { $timestamp } else { '' }
        $track.progress = New-MediaPipelineRunMonitorProgress -Numerator $Numerator -Denominator $Denominator -Indeterminate:$Indeterminate
        $track.result = $Result
        if (-not [string]::IsNullOrWhiteSpace($Reason)) { $track.reason = $Reason }
        if (-not [string]::IsNullOrWhiteSpace($ReasonCode)) { $track.reason_code = $ReasonCode }
        if ($Kind -eq 'audio') {
            if (-not [string]::IsNullOrWhiteSpace($OutputCodec)) { $track.output_codec = $OutputCodec }
            if ($null -ne $OutputChannels) { $track.output_channels = [math]::Max(0, [int]$OutputChannels) }
            if (-not [string]::IsNullOrWhiteSpace($OutputLayout)) { $track.output_layout = $OutputLayout }
            if ($null -ne $IsDefault) { $track.is_default = [bool]$IsDefault }
        }
        if ($Kind -eq 'subtitles') {
            if (-not [string]::IsNullOrWhiteSpace($OutputCodec)) { $track.output_codec = $OutputCodec }
            if (-not [string]::IsNullOrWhiteSpace($OutputLocation)) { $track.output_location = $OutputLocation }
            if (-not [string]::IsNullOrWhiteSpace($OutputPath)) { $track.output_path = $OutputPath }
            if (-not [string]::IsNullOrWhiteSpace($ParkedPath)) { $track.parked_path = $ParkedPath }
            if (-not [string]::IsNullOrWhiteSpace($IntendedFinalPath)) { $track.intended_final_path = $IntendedFinalPath }
            Set-MediaPipelineRunMonitorProperty -InputObject $track -Name 'step_index' -Value ([int]$StepIndex)
            Set-MediaPipelineRunMonitorProperty -InputObject $track -Name 'step_total' -Value ([int]$StepTotal)
            Set-MediaPipelineRunMonitorProperty -InputObject $track -Name 'step_name' -Value ([string]$StepName)
            Set-MediaPipelineRunMonitorProperty -InputObject $track -Name 'progress_unit' -Value ([string]$ProgressUnit)
            Set-MediaPipelineRunMonitorProperty -InputObject $track -Name 'cue_count' -Value $normalizedCueCount
        }
        $effectiveEvidenceSource = if ([string]::IsNullOrWhiteSpace($EvidenceSource)) { "${Kind}_progress" } else { $EvidenceSource }
        $effectiveEvidenceProvenance = if ([string]::IsNullOrWhiteSpace($EvidenceProvenance)) {
            if ($State -in @('completed','failed','review','skipped','dropped')) { 'backend_confirmed' } else { 'backend_confirmed' }
        } else { $EvidenceProvenance }
        $track.evidence = New-MediaPipelineRunMonitorEvidence -Source $effectiveEvidenceSource -Provenance $effectiveEvidenceProvenance -RecordedAt $timestamp
        $collection.state = if (@($collection.tracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) { 'review' } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) { 'failed' } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'active' }).Count -gt 0) { 'active' } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'awaiting_evidence' }).Count -gt 0) { 'awaiting_evidence' } elseif (@($collection.tracks | Where-Object { [string]$_.state -eq 'unknown' }).Count -gt 0) { 'unknown' } else { 'completed' }
        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source $effectiveEvidenceSource -Provenance $effectiveEvidenceProvenance -RecordedAt $timestamp
        $item.updated_at = $timestamp
        return $payload
    }
}

function Update-MediaPipelineRunMonitorActiveTrackHeartbeat {
    param(
        [Parameter(Mandatory)] [ValidateSet('audio','subtitles')] [string] $Kind,
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [string] $TrackId = '',
        [Parameter(Mandatory)] [string] $EvidenceSource,
        [ValidateSet('backend_confirmed','worker_heartbeat')] [string] $EvidenceProvenance = 'backend_confirmed',
        $Numerator = $null,
        $Denominator = $null
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -SkipWriteWhenMutationReturnsNull -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $collection = $item.$Kind
        $hasExactTrackId = -not [string]::IsNullOrWhiteSpace($TrackId)
        $activeTracks = if (-not $hasExactTrackId) {
            @($collection.tracks | Where-Object { [string]$_.state -eq 'active' })
        } else {
            @($collection.tracks | Where-Object {
                [string]$_.track_id -eq $TrackId -and [string]$_.state -eq 'active'
            })
        }
        if (($hasExactTrackId -and $activeTracks.Count -ne 1) -or $activeTracks.Count -eq 0) {
            # A late, missing, duplicate, or terminal exact-track heartbeat is
            # liveness-only noise. Preserve every existing track/stage claim.
            return $null
        }

        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $heartbeatEvidence = New-MediaPipelineRunMonitorEvidence `
            -Source $EvidenceSource `
            -Provenance $EvidenceProvenance `
            -RecordedAt $timestamp
        $progress = New-MediaPipelineRunMonitorProgress -Indeterminate
        if ($null -ne $Numerator -and $null -ne $Denominator) {
            try {
                $numericNumerator = [double]$Numerator
                $numericDenominator = [double]$Denominator
                if ([double]::IsFinite($numericNumerator) -and [double]::IsFinite($numericDenominator) -and
                    $numericDenominator -gt 0 -and $numericNumerator -ge 0 -and $numericNumerator -le $numericDenominator) {
                    $progress = New-MediaPipelineRunMonitorProgress -Numerator $numericNumerator -Denominator $numericDenominator
                }
            } catch {
                $progress = New-MediaPipelineRunMonitorProgress -Indeterminate
            }
        }
        foreach ($track in $activeTracks) {
            # This is liveness only. Keep backend policy/action/result fields
            # untouched. Determinate progress is accepted only when the caller
            # supplies a valid correlated numerator and denominator.
            $track.updated_at = $timestamp
            $track.completed_at = ''
            $track.progress = $progress
            $track.evidence = $heartbeatEvidence
        }
        $collection.evidence = $heartbeatEvidence
        $stage = @($item.stages | Where-Object { [string]$_.stage_id -eq $Kind })[0]
        if ($stage -and [string]$stage.state -eq 'active') {
            $stage.updated_at = $timestamp
            $stage.completed_at = ''
            $stage.progress = $progress
            $stage.evidence = $heartbeatEvidence
        }
        $item.updated_at = $timestamp
        return $payload
    }
}

function Complete-MediaPipelineRunMonitorTrackStageFromEvidence {
    param(
        [Parameter(Mandatory)] [ValidateSet('audio','subtitles')] [string] $Kind,
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] [string] $EvidenceSource
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $collection = $item.$Kind
        if (-not [bool]$collection.policy_final) { return $payload }

        $tracks = @($collection.tracks)
        $unresolved = @($tracks | Where-Object { [string]$_.state -in @('awaiting_evidence','active','unknown') })
        if ($unresolved.Count -gt 0) { return $payload }

        $stage = @($item.stages | Where-Object { [string]$_.stage_id -eq $Kind })[0]
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $stageState = if ([string]$collection.state -eq 'not_applicable' -or $tracks.Count -eq 0) {
            'not_applicable'
        } elseif (@($tracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) {
            'review'
        } elseif (@($tracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) {
            'failed'
        } else {
            'completed'
        }
        if ([string]::IsNullOrWhiteSpace([string]$stage.started_at)) { $stage.started_at = $timestamp }
        $stage.state = $stageState
        $stage.updated_at = $timestamp
        $stage.completed_at = $timestamp
        $stage.detail = if ($stageState -eq 'not_applicable') {
            "No $Kind tracks apply."
        } elseif ($stageState -eq 'review') {
            "$Kind track evidence requires review."
        } elseif ($stageState -eq 'failed') {
            "$Kind track evidence failed."
        } else {
            "All $Kind track outcomes are proven by correlated terminal evidence."
        }
        $stage.progress = New-MediaPipelineRunMonitorProgress
        $stage.evidence = New-MediaPipelineRunMonitorEvidence -Source $EvidenceSource -Provenance terminal -RecordedAt $timestamp
        $item.updated_at = $timestamp
        return $payload
    }
}

function Set-MediaPipelineRunMonitorWorkers {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [AllowEmptyCollection()] [array] $Workers
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $acceptedJobIds = @($payload.items | ForEach-Object { [string]$_.job_id })
        $projected = [System.Collections.Generic.List[object]]::new()
        foreach ($worker in @($Workers | Where-Object { $null -ne $_ })) {
            $jobId = [string](Get-MediaPipelineRunMonitorValue $worker 'job_id' '')
            if ($jobId -notin $acceptedJobIds) { throw "Run Monitor worker is not correlated to an accepted job_id: $jobId" }
            $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $jobId
            $stageId = [string](Get-MediaPipelineRunMonitorValue $worker 'stage_id' '')
            if ($stageId -notin $script:MediaPipelineRunMonitorStageIds) { throw "Run Monitor worker stage is not canonical: $stageId" }
            $workerState = [string](Get-MediaPipelineRunMonitorValue $worker 'state' 'unknown')
            $numerator = Get-MediaPipelineRunMonitorValue $worker 'numerator' $null
            $denominator = Get-MediaPipelineRunMonitorValue $worker 'denominator' $null
            $indeterminate = $workerState -eq 'active' -and $null -eq $numerator -and $null -eq $denominator
            $updatedAt = [string](Get-MediaPipelineRunMonitorValue $worker 'updated_at' '')
            if ([string]::IsNullOrWhiteSpace($updatedAt)) { $updatedAt = Get-MediaPipelineRunMonitorTimestamp }
            $executedRoute = ''
            if ($item.routes -and $item.routes.executed -and
                [string](Get-MediaPipelineRunMonitorValue $item.routes.executed 'state' '') -eq 'available') {
                $executedRoute = [string](Get-MediaPipelineRunMonitorValue $item.routes.executed 'route' '')
            }
            $evidenceSource = [string](Get-MediaPipelineRunMonitorValue $worker 'evidence_source' 'worker_heartbeat')
            $evidenceProvenance = [string](Get-MediaPipelineRunMonitorValue $worker 'evidence_provenance' 'worker_heartbeat')
            $projected.Add([ordered]@{
                worker_id = [string](Get-MediaPipelineRunMonitorValue $worker 'worker_id' '')
                run_id    = $RunId
                job_id    = $jobId
                state     = $workerState
                stage_id  = $stageId
                route     = $executedRoute
                progress  = New-MediaPipelineRunMonitorProgress -Numerator $numerator -Denominator $denominator -Indeterminate:$indeterminate
                updated_at = $updatedAt
                evidence  = New-MediaPipelineRunMonitorEvidence -Source $evidenceSource -Provenance $evidenceProvenance -RecordedAt $updatedAt
            }) | Out-Null
        }
        $payload.current_workers = @($projected.ToArray())
        return $payload
    }
}

function Set-MediaPipelineRunMonitorItemLifecycle {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)]
        [ValidateSet('accepted','queued','active','completed','failed','skipped','blocked','review','parked','stopped','unknown')]
        [string] $State,
        [string] $Reason = '',
        [string] $ReasonCode = '',
        $Retryable = $null,
        [string] $RecoveryOwner = 'pipeline',
        [string] $NextAction = ''
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $item.lifecycle_state = $State
        $item.lifecycle_evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance $(if ($State -in $script:MediaPipelineRunMonitorTerminalItemStates) { 'terminal' } else { 'backend_confirmed' }) -RecordedAt $timestamp
        $item.updated_at = $timestamp
        if ($State -in @('failed','blocked','review')) {
            $item.failure.state = if ($State -eq 'failed') { $(if ($Retryable -eq $true) { 'recoverable' } else { 'fatal' }) } else { $State }
            $item.failure.reason = $Reason
            $item.failure.reason_code = $ReasonCode
            $item.failure.retryable = $Retryable
            $item.failure.evidence = New-MediaPipelineRunMonitorEvidence -Source 'failure_artifact' -Provenance 'terminal' -RecordedAt $timestamp
        }
        $item.recovery.owner = $RecoveryOwner
        $item.recovery.next_action = $NextAction
        $item.recovery.retryable = $Retryable
        $item.recovery.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance $(if ($State -in $script:MediaPipelineRunMonitorTerminalItemStates) { 'terminal' } else { 'backend_confirmed' }) -RecordedAt $timestamp
        if ($State -eq 'unknown') {
            # A correlated process result arrived without the durable artifact
            # required to prove its terminal outcome. Remove every current or
            # awaiting claim, but deliberately keep the lifecycle nonterminal
            # so the run finalizer can author one honest failed outcome.
            foreach ($active in @($item.stages | Where-Object { [string]$_.state -eq 'active' })) {
                $active.state = 'unknown'
                $active.updated_at = $timestamp
                $active.completed_at = ''
                $active.detail = $Reason
                $active.reason_code = $ReasonCode
                $active.progress = New-MediaPipelineRunMonitorProgress
                $active.evidence = New-MediaPipelineRunMonitorEvidence -Source 'process_file_result' -Provenance 'unknown' -RecordedAt $timestamp
            }
            foreach ($collectionName in @('audio','subtitles')) {
                $collection = $item.$collectionName
                foreach ($track in @($collection.tracks | Where-Object { [string]$_.state -in @('awaiting_evidence','active') })) {
                    $track.state = 'unknown'
                    $track.updated_at = $timestamp
                    $track.completed_at = ''
                    $track.progress = New-MediaPipelineRunMonitorProgress
                    $track.result = $Reason
                    $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'process_file_result' -Provenance 'unknown' -RecordedAt $timestamp
                }
                if ([string]$collection.state -in @('awaiting_evidence','active')) {
                    $collection.state = 'unknown'
                    $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'process_file_result' -Provenance 'unknown' -RecordedAt $timestamp
                }
            }
            $payload.current_workers = @($payload.current_workers | Where-Object { [string]$_.job_id -ne $JobId })
        }
        if ($State -in $script:MediaPipelineRunMonitorTerminalItemStates) {
            # Exact item-level success proves the item outcome, not the
            # completion of a stage whose own backend transition never closed.
            # Preserve that distinction instead of inferring stage completion
            # from a later terminal artifact.
            $terminalStageState = switch ($State) {
                'failed' { 'failed' }
                'blocked' { 'blocked' }
                'review' { 'review' }
                'skipped' { 'skipped' }
                'stopped' { 'skipped' }
                default { 'unknown' }
            }
            foreach ($active in @($item.stages | Where-Object { [string]$_.state -eq 'active' })) {
                $active.state = $terminalStageState
                $active.updated_at = $timestamp
                $active.completed_at = if ($terminalStageState -eq 'unknown') { '' } else { $timestamp }
                $active.detail = if ($terminalStageState -eq 'unknown') {
                    'The item reached terminal evidence without an explicit completion transition for this stage.'
                } else { $Reason }
                $active.reason_code = if ($terminalStageState -eq 'unknown') { 'stage_completion_evidence_missing' } else { $ReasonCode }
                $active.progress = New-MediaPipelineRunMonitorProgress
                $active.evidence = New-MediaPipelineRunMonitorEvidence `
                    -Source 'pipeline_result' `
                    -Provenance $(if ($terminalStageState -eq 'unknown') { 'unknown' } else { 'terminal' }) `
                    -RecordedAt $timestamp
            }
            foreach ($collectionName in @('audio','subtitles')) {
                $collection = $item.$collectionName
                $tracks = @($collection.tracks)
                if ($State -in @('completed','parked')) {
                    if ($tracks.Count -gt 0) {
                        $hasUnprovenTrack = $false
                        foreach ($track in $tracks) {
                            if ([string]$track.state -in @('awaiting_evidence','active','unknown')) {
                                $track.state = 'unknown'
                                $track.updated_at = $timestamp
                                $track.completed_at = ''
                                $track.progress = New-MediaPipelineRunMonitorProgress
                                $track.result = 'Terminal per-track result was not present in correlated backend evidence.'
                                $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'unknown' -RecordedAt $timestamp
                                $hasUnprovenTrack = $true
                            }
                        }
                        if ([string]$collection.state -notin @('review','failed','not_applicable')) {
                            $collection.state = if ($hasUnprovenTrack) { 'unknown' } else { 'completed' }
                            $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance $(if ($hasUnprovenTrack) { 'unknown' } else { 'terminal' }) -RecordedAt $timestamp
                        }
                    } elseif ([string]$collection.state -eq 'awaiting_evidence') {
                        $collection.state = 'unknown'
                        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'unknown' -RecordedAt $timestamp
                    }
                } elseif ($State -in @('failed','blocked','review')) {
                    foreach ($track in $tracks) {
                        if ([string]$track.state -eq 'active') {
                            $track.state = if ($State -eq 'review') { 'review' } else { 'failed' }
                            if ([string]::IsNullOrWhiteSpace([string]$track.started_at)) { $track.started_at = $timestamp }
                            $track.updated_at = $timestamp
                            $track.completed_at = $timestamp
                            $track.progress = New-MediaPipelineRunMonitorProgress
                            $track.result = $Reason
                            $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'terminal' -RecordedAt $timestamp
                        } elseif ([string]$track.state -eq 'awaiting_evidence') {
                            $track.state = 'unknown'
                            $track.updated_at = $timestamp
                            $track.completed_at = ''
                            $track.progress = New-MediaPipelineRunMonitorProgress
                            $track.result = 'The item ended before correlated per-track runtime evidence was recorded.'
                            $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'unknown' -RecordedAt $timestamp
                        }
                    }
                    if (@($tracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) {
                        $collection.state = 'review'
                        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'terminal' -RecordedAt $timestamp
                    } elseif (@($tracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) {
                        $collection.state = 'failed'
                        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'terminal' -RecordedAt $timestamp
                    } elseif (@($tracks | Where-Object { [string]$_.state -eq 'unknown' }).Count -gt 0 -or
                        ([string]$collection.state -eq 'awaiting_evidence' -and $tracks.Count -eq 0)) {
                        $collection.state = 'unknown'
                        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'unknown' -RecordedAt $timestamp
                    }
                } elseif ($State -in @('skipped','stopped')) {
                    foreach ($track in $tracks) {
                        if ([string]$track.state -in @('active','awaiting_evidence')) {
                            $track.state = 'skipped'
                            if ([string]::IsNullOrWhiteSpace([string]$track.started_at)) { $track.started_at = $timestamp }
                            $track.updated_at = $timestamp
                            $track.completed_at = $timestamp
                            $track.progress = New-MediaPipelineRunMonitorProgress
                            $track.result = $Reason
                            $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance 'terminal' -RecordedAt $timestamp
                        }
                    }
                    $collection.state = if ($tracks.Count -gt 0) { 'completed' } else { 'unknown' }
                    $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'pipeline_result' -Provenance $(if ($tracks.Count -gt 0) { 'terminal' } else { 'unknown' }) -RecordedAt $timestamp
                }
            }
        }
        return $payload
    }
}

function Set-MediaPipelineRunMonitorOutput {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)]
        [ValidateSet('awaiting_evidence','not_applicable','active','verified','published','parked','failed','review','unknown')]
        [string] $State,
        [string] $ScratchPath = '',
        [string] $WorkingOutputPath = '',
        [string] $PublishedPath = '',
        [string] $ParkedPath = '',
        [string] $IntendedFinalPath = '',
        $SizeBytes = $null,
        [ValidateSet('not_started','active','completed','not_applicable','failed','blocked','review','unknown')]
        [string] $VerificationState = 'unknown',
        [array] $Sidecars = @()
    )
    $setScratchPath = $PSBoundParameters.ContainsKey('ScratchPath')
    $setWorkingOutputPath = $PSBoundParameters.ContainsKey('WorkingOutputPath')
    $setPublishedPath = $PSBoundParameters.ContainsKey('PublishedPath')
    $setParkedPath = $PSBoundParameters.ContainsKey('ParkedPath')
    $setIntendedFinalPath = $PSBoundParameters.ContainsKey('IntendedFinalPath')
    $setSizeBytes = $PSBoundParameters.ContainsKey('SizeBytes')
    $setSidecars = $PSBoundParameters.ContainsKey('Sidecars')
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $item.output.state = $State
        if ($setScratchPath) { $item.output.scratch_path = $ScratchPath }
        if ($setWorkingOutputPath) { $item.output.working_output_path = $WorkingOutputPath }
        if ($setPublishedPath) { $item.output.published_path = $PublishedPath }
        if ($setParkedPath) { $item.output.parked_path = $ParkedPath }
        if ($setIntendedFinalPath -and -not [string]::IsNullOrWhiteSpace($IntendedFinalPath)) { $item.output.intended_final_path = $IntendedFinalPath }
        if ($setSizeBytes) { $item.output.size_bytes = $SizeBytes }
        $item.output.verification_state = $VerificationState
        if ($setSidecars) { $item.output.sidecars = @($Sidecars) }
        $item.output.evidence = New-MediaPipelineRunMonitorEvidence -Source 'output_evidence' -Provenance $(if ($State -in @('published','parked','failed','review')) { 'terminal' } else { 'backend_confirmed' })
        $item.updated_at = Get-MediaPipelineRunMonitorTimestamp
        return $payload
    }
}

function Set-MediaPipelineCurrentRunMonitorOutput {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('awaiting_evidence','not_applicable','active','verified','published','parked','failed','review','unknown')]
        [string] $State,
        [string] $ScratchPath = '',
        [string] $WorkingOutputPath = '',
        [string] $PublishedPath = '',
        [string] $ParkedPath = '',
        [string] $IntendedFinalPath = '',
        $SizeBytes = $null,
        [ValidateSet('not_started','active','completed','not_applicable','failed','blocked','review','unknown')]
        [string] $VerificationState = 'unknown'
    )
    if ([string]::IsNullOrWhiteSpace([string]$script:PipelineRunId) -or
        [string]::IsNullOrWhiteSpace([string]$script:CurrentRunMonitorJobId)) {
        return $null
    }
    $arguments = @{
        RunId = [string]$script:PipelineRunId
        JobId = [string]$script:CurrentRunMonitorJobId
        State = $State
        VerificationState = $VerificationState
    }
    foreach ($name in @('ScratchPath','WorkingOutputPath','PublishedPath','ParkedPath','IntendedFinalPath','SizeBytes')) {
        if ($PSBoundParameters.ContainsKey($name)) { $arguments[$name] = $PSBoundParameters[$name] }
    }
    try {
        return Set-MediaPipelineRunMonitorOutput @arguments
    } catch {
        $script:RunMonitorPersistenceHealthy = $false
        Write-Log "Run Monitor output-path evidence failed: $($_.Exception.Message)" 'WARN'
        return $null
    }
}

function Add-MediaPipelineRunMonitorTerminalReference {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [string] $JobId,
        [Parameter(Mandatory)] [ValidateSet('completed','pending_publish','failure','review','report','manifest','sidecar')]
        [string] $Kind,
        [Parameter(Mandatory)] [string] $Reference,
        [string] $Path = ''
    )
    # Use distinct captured names: Invoke-MediaPipelineRunMonitorUpdate owns a
    # local $path for the monitor JSON itself, and PowerShell dynamic scoping
    # must never substitute that path for the referenced terminal artifact.
    $referenceKind = [string]$Kind
    $referenceValue = [string]$Reference
    $referencePath = [string]$Path
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $item = Get-MediaPipelineRunMonitorItem -Payload $payload -JobId $JobId
        $existing = @($item.terminal_references | Where-Object { [string]$_.kind -eq $referenceKind -and [string]$_.reference -eq $referenceValue })
        if ($existing.Count -eq 0) {
            $item.terminal_references = @(@($item.terminal_references) + @([ordered]@{
                kind = $referenceKind; reference = $referenceValue; path = $referencePath
                evidence = New-MediaPipelineRunMonitorEvidence -Source "${referenceKind}_artifact" -Provenance 'terminal'
            }))
        }
        $item.updated_at = Get-MediaPipelineRunMonitorTimestamp
        return $payload
    }
}

function Set-MediaPipelineRunMonitorRunState {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)]
        [ValidateSet('starting','scanning','running','paused','stop_requested','stopping','completed','failed','blocked','review','stopped','force_stopped','unknown')]
        [string] $State,
        [ValidateSet('','not_requested','requested','acknowledged','stopping','completed','unavailable')]
        [string] $StopAfterCurrentState = '',
        [string] $RequestedAt = ''
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $payload.run.lifecycle_state = $State
        if (-not [string]::IsNullOrWhiteSpace($StopAfterCurrentState)) {
            $payload.run.stop_after_current.state = $StopAfterCurrentState
        }
        if (-not [string]::IsNullOrWhiteSpace($RequestedAt)) { $payload.run.stop_after_current.requested_at = $RequestedAt }
        if (-not [string]::IsNullOrWhiteSpace($StopAfterCurrentState) -or -not [string]::IsNullOrWhiteSpace($RequestedAt)) {
            $payload.run.stop_after_current.evidence = New-MediaPipelineRunMonitorEvidence -Source 'control_flags' -RecordedAt $timestamp
        }
        if ($State -in $script:MediaPipelineRunMonitorTerminalRunStates) { $payload.run.ended_at = $timestamp }
        return $payload
    }
}

function Complete-MediaPipelineRunMonitor {
    param(
        [Parameter(Mandatory)] [string] $RunId,
        [Parameter(Mandatory)] [ValidateSet('completed','failed','blocked','review','stopped','force_stopped')]
        [string] $State,
        [ValidateSet('skipped','stopped','failed','blocked','review')]
        [string] $RemainingItemState = 'skipped',
        [string] $Reason = 'Run ended before this accepted item was dispatched.',
        [string] $ReasonCode = 'not_dispatched',
        $Retryable = $true,
        [string] $RecoveryOwner = 'pipeline',
        [string] $NextAction = 'Review the run outcome before retrying.'
    )
    return Invoke-MediaPipelineRunMonitorUpdate -RunId $RunId -Mutation {
        param($payload)
        $timestamp = Get-MediaPipelineRunMonitorTimestamp
        $unresolved = @($payload.items | Where-Object { [string]$_.lifecycle_state -notin $script:MediaPipelineRunMonitorTerminalItemStates })
        $effectiveState = if ($State -eq 'stopped' -and $unresolved.Count -eq 0) { 'completed' } else { $State }
        if ($effectiveState -eq 'completed' -and $unresolved.Count -gt 0) {
            throw "RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE: completed run retains $($unresolved.Count) nonterminal accepted item(s)."
        }
        if ($effectiveState -eq 'completed') {
            $missingTerminalProof = @(
                foreach ($item in @($payload.items)) {
                    $expectedState = ''
                    $expectedSource = ''
                    switch ([string]$item.lifecycle_state) {
                        'completed' { $expectedState = 'completed'; $expectedSource = 'completed_sidecar' }
                        'parked' { $expectedState = 'completed'; $expectedSource = 'pending_publish_manifest' }
                        'failed' { $expectedState = 'failed'; $expectedSource = 'failure_artifact' }
                        'blocked' { $expectedState = 'blocked'; $expectedSource = 'failure_artifact' }
                        'review' { $expectedState = 'review'; $expectedSource = 'failure_artifact' }
                        default { continue }
                    }
                    $terminalStage = @($item.stages | Where-Object { [string]$_.stage_id -eq 'final_evidence' })[0]
                    if ([string]$terminalStage.state -ne $expectedState -or
                        [string]$terminalStage.evidence.source -ne $expectedSource) {
                        $item
                    }
                }
            )
            if ($missingTerminalProof.Count -gt 0) {
                $missingIds = @($missingTerminalProof | ForEach-Object { [string]$_.job_id }) -join ', '
                throw "RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE: $($missingTerminalProof.Count) terminal item(s) lack exact artifact proof ($missingIds)."
            }
        }
        foreach ($item in @($payload.items)) {
            $newlyTerminalized = $false
            if ([string]$item.lifecycle_state -notin $script:MediaPipelineRunMonitorTerminalItemStates) {
                $item.lifecycle_state = $RemainingItemState
                $item.lifecycle_evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                $item.recovery.owner = $RecoveryOwner
                $item.recovery.next_action = $NextAction
                $item.recovery.retryable = $Retryable
                $item.recovery.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                if ($RemainingItemState -in @('failed','blocked','review')) {
                    $item.failure.state = switch ($RemainingItemState) { 'failed' { if ($Retryable -eq $true) { 'recoverable' } else { 'fatal' } } 'blocked' { 'blocked' } default { 'review' } }
                    $item.failure.reason = $Reason
                    $item.failure.reason_code = $ReasonCode
                    $item.failure.retryable = $Retryable
                    $item.failure.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                }
                foreach ($active in @($item.stages | Where-Object { [string]$_.state -eq 'active' })) {
                    $active.state = if ($RemainingItemState -in @('failed','blocked','review')) { $RemainingItemState } else { 'skipped' }
                    $active.updated_at = $timestamp
                    $active.completed_at = $timestamp
                    $active.detail = $Reason
                    $active.reason_code = $ReasonCode
                    $active.progress = New-MediaPipelineRunMonitorProgress
                    $active.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                }
                foreach ($collectionName in @('audio','subtitles')) {
                    $collection = $item.$collectionName
                    foreach ($track in @($collection.tracks | Where-Object { [string]$_.state -in @('awaiting_evidence','active') })) {
                        $track.state = switch ($RemainingItemState) { 'review' { 'review' } { $_ -in @('failed','blocked') } { 'failed' } default { 'skipped' } }
                        if ([string]$track.state -ne 'skipped' -and [string]::IsNullOrWhiteSpace([string]$track.started_at)) { $track.started_at = $timestamp }
                        $track.updated_at = $timestamp
                        $track.completed_at = $timestamp
                        $track.progress = New-MediaPipelineRunMonitorProgress
                        $track.result = $Reason
                        $track.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                    }
                    if ([string]$collection.state -in @('awaiting_evidence','active')) {
                        $collection.state = switch ($RemainingItemState) { 'review' { 'review' } { $_ -in @('failed','blocked') } { 'failed' } default { 'unknown' } }
                        $collection.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                    }
                }
                if ([string]$item.output.state -in @('awaiting_evidence','active')) {
                    $item.output.state = 'unknown'
                    $item.output.verification_state = 'unknown'
                    $item.output.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                }
                if ([string]$item.routes.final.state -eq 'awaiting_evidence') {
                    $executedRouteAvailable = [string]$item.routes.executed.state -eq 'available'
                    $item.routes.final.state = if (
                        [string]$item.lifecycle_state -in @('skipped','stopped') -and
                        -not $executedRouteAvailable
                    ) { 'not_applicable' } else { 'unknown' }
                    $item.routes.final.route = ''
                    $item.routes.final.reason = $Reason
                    $item.routes.final.reason_code = $ReasonCode
                    $item.routes.final.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                }
                $newlyTerminalized = $true
            }
            $finalStage = @($item.stages | Where-Object { [string]$_.stage_id -eq 'final_evidence' })[0]
            if ($newlyTerminalized) {
                $finalStage.state = switch ([string]$item.lifecycle_state) { 'failed' { 'failed' } 'blocked' { 'blocked' } 'review' { 'review' } { $_ -in @('skipped','stopped') } { 'skipped' } default { 'completed' } }
                $finalStage.started_at = if ([string]::IsNullOrWhiteSpace([string]$finalStage.started_at)) { $timestamp } else { $finalStage.started_at }
                $finalStage.updated_at = $timestamp
                $finalStage.completed_at = $timestamp
                $finalStage.detail = $Reason
                $finalStage.reason_code = $ReasonCode
                $finalStage.progress = New-MediaPipelineRunMonitorProgress
                $finalStage.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
                $item.updated_at = $timestamp
            }
        }
        $payload.current_workers = @()
        $payload.run.lifecycle_state = $effectiveState
        $payload.run.ended_at = $timestamp
        $payload.run.evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
        Set-MediaPipelineRunMonitorProperty -InputObject $payload.run -Name 'outcome' -Value ([ordered]@{
            state = $effectiveState; reason_code = $ReasonCode; reason = $Reason; retryable = $Retryable
            owner = $RecoveryOwner; next_action = $NextAction
            evidence = New-MediaPipelineRunMonitorEvidence -Source 'run_completion' -Provenance 'terminal' -RecordedAt $timestamp
        })
        if ([string]$payload.run.stop_after_current.state -ne 'not_requested') {
            $payload.run.stop_after_current.state = 'completed'
            $payload.run.stop_after_current.evidence = New-MediaPipelineRunMonitorEvidence -Source 'control_flags' -Provenance 'terminal' -RecordedAt $timestamp
        }
        return $payload
    }
}
