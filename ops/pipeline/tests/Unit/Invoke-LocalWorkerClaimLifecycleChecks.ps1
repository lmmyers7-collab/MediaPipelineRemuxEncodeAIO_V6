[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Local worker claim lifecycle checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
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

$queueEngineRoot = Join-Path $repoRoot 'ops\pipeline\engine\queue'
$previousMutexSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
$env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = 'fb003_' + [guid]::NewGuid().ToString('N')

. (Join-Path $queueEngineRoot 'worker_mutex.ps1')
. (Join-Path $queueEngineRoot 'worker_process.ps1')
. (Join-Path $queueEngineRoot 'worker_progress.ps1')
. (Join-Path $queueEngineRoot 'worker_claim_store.ps1')

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

function New-LocalWorkerLifecycleEntry {
    param([Parameter(Mandatory)][string] $SourcePath)

    return [pscustomobject]@{
        SourcePath = $SourcePath
        File       = [pscustomobject]@{
            FullName = $SourcePath
            Name     = [System.IO.Path]::GetFileName($SourcePath)
        }
        IsTV       = $false
        IsPriority = $false
        QueuePhase = 'movie'
        QueueIndex = 1
        QueueTotal = 1
    }
}

function Invoke-StaleResultReadyClaimReleasesForRetryCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineLocalWorkerClaimTest_' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $claimStorePath = Join-Path $tempRoot 'claims.json'
        $resultPath = Join-Path $tempRoot 'worker_result.json'
        $sourcePath = Join-Path $tempRoot 'Movie.mkv'
        Set-Content -LiteralPath $sourcePath -Value 'not real media' -Encoding UTF8
        Set-Content -LiteralPath $resultPath -Value '{"SchemaVersion":"local_worker_result.v1","Status":"processed","Success":true}' -Encoding UTF8

        $store = New-MediaPipelineLocalWorkerClaimStore
        $store.claims = @([pscustomobject]@{
            schema_version = 'local_worker_claim.v1'
            claim_id       = 'old-claim'
            status         = 'result_ready'
            source_path    = $sourcePath
            source_key     = ConvertTo-MediaPipelineLocalWorkerPathKey -Path $sourcePath
            source_name    = 'Movie.mkv'
            media_kind     = 'movie'
            route_type     = ''
            slot_id        = 1
            owner_run_id   = 'previous-run'
            owner_pid      = 0
            worker_pid     = -999999
            queue_index    = 1
            queue_total    = 1
            queue_phase    = 'movie'
            priority       = $false
            result_path    = $resultPath
            claimed_at     = (Get-Date).AddMinutes(-5).ToString('o')
            updated_at     = (Get-Date).AddMinutes(-5).ToString('o')
        })
        Write-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $claimStorePath -Store $store | Out-Null

        Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $claimStorePath -CurrentRunId 'new-run' | Out-Null
        $repaired = Get-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $claimStorePath
        $oldClaim = @($repaired.claims)[0]
        Assert-Equal ([string]$oldClaim.status) 'released_stale_result' 'Dead result_ready claim should be released to a non-active status.'
        Assert-True ([string]$oldClaim.release_reason -like '*stale worker claim*') 'Released stale result should keep a diagnostic reason.'
        Assert-True ($null -ne $oldClaim.PSObject.Properties['stale_result_archive_path']) 'Released stale result should record an archived result path.'
        Assert-True (Test-Path -LiteralPath ([string]$oldClaim.stale_result_archive_path) -PathType Leaf) 'Archived stale result should remain readable after repair.'
        $archived = Read-MediaPipelineJsonFile -Path ([string]$oldClaim.stale_result_archive_path)
        Assert-Equal ([string]$archived.SchemaVersion) 'local_worker_result.v1' 'Archived stale result should preserve the worker result payload.'

        $newClaim = Invoke-MediaPipelineLocalWorkerClaim `
            -ClaimStorePath $claimStorePath `
            -Entry (New-LocalWorkerLifecycleEntry -SourcePath $sourcePath) `
            -SlotId 1 `
            -OwnerRunId 'new-run' `
            -ResultPath (Join-Path $tempRoot 'new_worker_result.json')
        Assert-True ($null -ne $newClaim) 'Source should be claimable after stale result_ready repair.'
        Assert-Equal ([string]$newClaim.status) 'claimed' 'New claim should use the normal claimed status.'
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-StaleClaimWithReusedPidReleasesCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineLocalWorkerPidReuseTest_' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $claimStorePath = Join-Path $tempRoot 'claims.json'
        $sourcePath = Join-Path $tempRoot 'Movie.mkv'
        Set-Content -LiteralPath $sourcePath -Value 'not real media' -Encoding UTF8

        $store = New-MediaPipelineLocalWorkerClaimStore
        $store.claims = @([pscustomobject]@{
            schema_version        = 'local_worker_claim.v1'
            claim_id              = 'pid-reuse-claim'
            status                = 'running'
            source_path           = $sourcePath
            source_key            = ConvertTo-MediaPipelineLocalWorkerPathKey -Path $sourcePath
            source_name           = 'Movie.mkv'
            media_kind            = 'movie'
            route_type            = ''
            slot_id               = 1
            owner_run_id          = 'previous-run'
            owner_pid             = 0
            worker_pid            = [int]$PID
            queue_index           = 1
            queue_total           = 1
            queue_phase           = 'movie'
            priority              = $false
            result_path           = ''
            worker_metadata_path  = Join-Path $tempRoot 'missing_worker_metadata.json'
            worker_start_time     = ''
            claimed_at            = (Get-Date).AddMinutes(-10).ToString('o')
            updated_at            = (Get-Date).AddMinutes(-10).ToString('o')
        })
        Write-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $claimStorePath -Store $store | Out-Null

        Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $claimStorePath -CurrentRunId 'new-run' -ClaimStaleSeconds 1 | Out-Null
        $repaired = Get-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $claimStorePath
        $oldClaim = @($repaired.claims)[0]
        Assert-Equal ([string]$oldClaim.status) 'released_stale' 'Stale claims must not stay active only because the worker_pid is alive.'
        Assert-True ([string]$oldClaim.recovery_note -like '*verified live worker process*') 'PID-reuse release should explain missing verified worker identity.'
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-VerifiedLiveWorkerClaimIsProtectedCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineLocalWorkerIdentityTest_' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $claimStorePath = Join-Path $tempRoot 'claims.json'
        $metadataPath = Join-Path $tempRoot 'worker_metadata.json'
        $resultPath = Join-Path $tempRoot 'worker_result.json'
        $sourcePath = Join-Path $tempRoot 'Movie.mkv'
        Set-Content -LiteralPath $sourcePath -Value 'not real media' -Encoding UTF8
        $workerStartTime = Get-MediaPipelineProcessStartTimeUtcText -ProcessId $PID

        $metadata = [ordered]@{
            schema_version    = 'local_worker_metadata.v1'
            slot_id           = 1
            claim_id          = 'verified-live-claim'
            source_path       = $sourcePath
            owner_run_id      = 'current-run'
            result_path       = $resultPath
            worker_pid        = [int]$PID
            worker_start_time = $workerStartTime
            created_at        = (Get-Date).AddMinutes(-10).ToString('o')
        }
        Write-MediaPipelineJsonAtomic -Path $metadataPath -InputObject $metadata -Depth 5 | Out-Null

        $store = New-MediaPipelineLocalWorkerClaimStore
        $store.claims = @([pscustomobject]@{
            schema_version        = 'local_worker_claim.v1'
            claim_id              = 'verified-live-claim'
            status                = 'running'
            source_path           = $sourcePath
            source_key            = ConvertTo-MediaPipelineLocalWorkerPathKey -Path $sourcePath
            source_name           = 'Movie.mkv'
            media_kind            = 'movie'
            route_type            = ''
            slot_id               = 1
            owner_run_id          = 'current-run'
            owner_pid             = [int]$PID
            worker_pid            = [int]$PID
            queue_index           = 1
            queue_total           = 1
            queue_phase           = 'movie'
            priority              = $false
            result_path           = $resultPath
            worker_metadata_path  = $metadataPath
            worker_start_time     = $workerStartTime
            claimed_at            = (Get-Date).AddMinutes(-10).ToString('o')
            updated_at            = (Get-Date).AddMinutes(-10).ToString('o')
        })
        Write-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $claimStorePath -Store $store | Out-Null

        Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $claimStorePath -CurrentRunId 'current-run' -ClaimStaleSeconds 1 | Out-Null
        $repaired = Get-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $claimStorePath
        $claim = @($repaired.claims)[0]
        Assert-Equal ([string]$claim.status) 'running' 'Verified live worker claim should remain active even when old enough to be stale.'
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-StaleResultReadyClaimReleasesForRetryCheck
Invoke-StaleClaimWithReusedPidReleasesCheck
Invoke-VerifiedLiveWorkerClaimIsProtectedCheck

. (Join-Path $queueEngineRoot 'local_worker_slots.ps1')

function Invoke-LocalWorkerPostSpawnClaimFailureStopsChildCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineLocalWorkerSlotTest_' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $sourcePath = Join-Path $tempRoot 'Movie.mkv'
        Set-Content -LiteralPath $sourcePath -Value 'not real media' -Encoding UTF8
        $entry = New-LocalWorkerLifecycleEntry -SourcePath $sourcePath
        $script:LocalStateLayout = [pscustomobject]@{
            Root    = $tempRoot
            Workers = Join-Path $tempRoot 'Workers'
            Paths   = [pscustomobject]@{
                LocalWorkerClaims     = Join-Path $tempRoot 'claims.json'
                LocalWorkerActiveJobs = Join-Path $tempRoot 'active_jobs.json'
            }
        }
        $script:PipelineRunId = 'run-post-spawn-failure'
        $script:StopRequested = $false
        $script:ProgressFile = Join-Path $tempRoot 'pipeline_progress.json'
        $script:SessionStartedAt = Get-Date
        $script:StoppedWorkerCount = 0
        $script:ReleasedClaims = @()
        $script:StartedProcess = $null
        $script:LogMessages = @()

        function Get-MediaPipelineQueuePlanRunnableEntries {
            param($QueuePlan)
            return @($QueuePlan.Entries)
        }
        function Check-ControlFlags {}
        function Write-Log {
            param([string] $Message, [string] $Level = 'INFO')
            $script:LogMessages += "$Level`:$Message"
        }
        function Repair-MediaPipelineLocalWorkerClaims { return $null }
        function Invoke-MediaPipelineLocalWorkerClaim {
            return [pscustomobject]@{
                claim_id    = 'claim-post-spawn-failure'
                source_path = $sourcePath
                source_name = 'Movie.mkv'
                media_kind  = 'movie'
                queue_index = 1
                queue_total = 1
            }
        }
        function Start-MediaPipelineLocalWorkerChild {
            $script:StartedProcess = [pscustomobject]@{ Id = 424242; HasExited = $false }
            return $script:StartedProcess
        }
        function Update-MediaPipelineLocalWorkerClaim {
            throw 'synthetic claim update failure'
        }
        function Stop-MediaPipelineLocalWorkerProcess {
            param($Job)
            $script:StoppedWorkerCount++
            $Job.Process.HasExited = $true
        }
        function Release-MediaPipelineLocalWorkerClaim {
            param(
                [string] $ClaimStorePath,
                [string] $ClaimId,
                [string] $Status,
                [string] $Reason
            )
            $script:ReleasedClaims += ,([pscustomobject]@{
                ClaimId = $ClaimId
                Status  = $Status
                Reason  = $Reason
            })
        }
        function Write-MediaPipelineLocalWorkerActiveJobs { return $null }

        Invoke-MediaQueuePhasePlanLocalWorkerSlots `
            -QueuePlan ([pscustomobject]@{ Entries = @($entry); HoldCount = 0; MoviePriorityCount = 0; TVPriorityCount = 0; MovieCount = 1; TVCount = 0; LowCount = 0 }) `
            -ProcessedIndex @{} `
            -ScriptPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline.ps1') `
            -ConfigPath (Join-Path $repoRoot 'ops\pipeline\config\MediaPipeline_config.psd1') `
            -PowerShellPath 'pwsh.exe' `
            -MaxParallelEncodes 1 | Out-Null

        Assert-Equal $script:StoppedWorkerCount 1 'Spawned child should be stopped when the post-spawn claim update fails.'
        Assert-True ($script:StartedProcess.HasExited) 'Stopped child process should be marked exited by the stop helper.'
        Assert-Equal ([string]$script:ReleasedClaims[0].Status) 'failed_start_child_stopped' 'Claim should record the post-spawn failure status.'
        Assert-True ([string]$script:ReleasedClaims[0].Reason -like '*claim update failure*') 'Release reason should preserve the claim update failure.'
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

try {
    Invoke-LocalWorkerPostSpawnClaimFailureStopsChildCheck
} finally {
    if ($null -eq $previousMutexSuffix) {
        Remove-Item Env:\MEDIA_PIPELINE_TEST_MUTEX_SUFFIX -ErrorAction SilentlyContinue
    } else {
        $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $previousMutexSuffix
    }
}

Write-Host 'Local worker claim lifecycle checks passed.'
