# ==============================================================================
# Backend-owned Run Once monitor persistence
# ==============================================================================
# Owns Run Monitor path identity, atomic JSON persistence, accepted seed reads,
# latest-pointer writes, and bounded terminal-history retention. Payload shape
# and validation remain owned by run_monitor_contract.ps1.
# ==============================================================================

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
