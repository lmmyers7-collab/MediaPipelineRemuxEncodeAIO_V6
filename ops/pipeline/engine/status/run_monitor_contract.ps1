# ==============================================================================
# Backend-owned Run Once monitor contract helpers
# ==============================================================================
# Owns the immutable schema vocabulary, evidence constructors, membership
# signature, and payload validation shared by Run Monitor persistence and state
# orchestration. This module does not read or write Run Monitor files.
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

function Update-MediaPipelineRunMonitorCounts {
    param([Parameter(Mandatory)] $Payload)
    $items = @($Payload.items)
    $Payload.run.counts.accepted = [int]$items.Count
    foreach ($state in @('queued','active','completed','failed','skipped','blocked','review','parked','stopped')) {
        $Payload.run.counts.$state = [int]@($items | Where-Object { [string]$_.lifecycle_state -eq $state }).Count
    }
}
