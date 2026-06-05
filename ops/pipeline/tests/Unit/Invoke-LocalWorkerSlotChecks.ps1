Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:TestRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$repoRoot = Split-Path -Parent $script:TestRoot

. (Join-Path $repoRoot 'ops\pipeline\engine\queue\local_worker_slots.ps1')

function Assert-True {
    param(
        [Parameter(Mandatory)] [bool] $Condition,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [Parameter(Mandatory)] [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

$previousMutexSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-local-worker-slot-checks-" + [guid]::NewGuid().ToString('N'))
try {
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = 'split-check'
    $state = Join-Path $root 'State'
    $workers = Join-Path $state 'Workers'
    [System.IO.Directory]::CreateDirectory($workers) | Out-Null

    $script:LocalBase = $root
    $script:LocalStateLayout = [pscustomobject]@{
        Root    = $state
        Workers = $workers
        Paths   = [pscustomobject]@{
            LocalWorkerClaims     = Join-Path $state 'local_worker_claims.json'
            LocalWorkerActiveJobs = Join-Path $state 'local_worker_active_jobs.json'
        }
    }
    $script:PipelineRunId = 'unit-run'
    $script:SessionStartedAt = Get-Date
    $script:PauseFlag = Join-Path $state 'pipeline_pause.flag'
    $script:StopFlag = Join-Path $state 'pipeline_stop.flag'
    $script:StopRequested = $false
    $script:totalProcessed = 0
    $script:totalEncoded = 0
    $script:totalRemuxed = 0
    $script:totalFailed = 0
    $script:totalMovies = 0
    $script:totalTVEpisodes = 0

    $hashA = Get-MediaPipelineStableHash -Text 'C:\Media\Source'
    $hashB = Get-MediaPipelineStableHash -Text 'C:\Media\Source'
    Assert-Equal $hashA $hashB 'Stable hash must be deterministic.'
    Assert-Equal $hashA.Length 16 'Stable hash must keep the existing 16-character key length.'
    Assert-True ((Get-MediaPipelineLocalWorkerMutexName -Kind 'ClaimStore' -LocalBase $root) -match 'split-check$') 'Worker mutex name must include the test suffix.'

    $source = Join-Path $root 'Movie.mkv'
    Set-Content -LiteralPath $source -Value 'media' -Encoding ASCII
    $file = Get-Item -LiteralPath $source
    $entry = [pscustomobject]@{
        File               = $file
        SourcePath         = $file.FullName
        IsTV               = $false
        QueueIndex         = 1
        QueueTotal         = 2
        RunQueueIndex      = 1
        RunQueueTotal      = 2
        LocalWorkerPhase   = 'movie'
        QueuePhase         = 'movie'
        IsPriority         = $false
    }

    $slot = Initialize-MediaPipelineWorkerSlotLayout -SlotLayout (New-MediaPipelineWorkerSlotLayout -StateLayout $script:LocalStateLayout -SlotId 1)
    Assert-True (Test-Path -LiteralPath $slot.Progress -PathType Container) 'Worker slot layout initialization must create progress directory.'

    $claim = Invoke-MediaPipelineLocalWorkerClaim -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -Entry $entry -SlotId 1 -OwnerRunId $script:PipelineRunId -ResultPath $slot.ResultFile
    Assert-True ($null -ne $claim) 'First local worker claim should succeed.'
    Assert-Equal ([string]$claim.status) 'claimed' 'Claim should start in claimed state.'
    Assert-Equal ([int]$claim.queue_index) 1 'Claim should preserve run queue index.'

    $duplicate = Invoke-MediaPipelineLocalWorkerClaim -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -Entry $entry -SlotId 2 -OwnerRunId $script:PipelineRunId -ResultPath $slot.ResultFile
    Assert-True ($null -eq $duplicate) 'Duplicate active claim for the same source must be rejected.'

    Release-MediaPipelineLocalWorkerClaim -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -ClaimId ([string]$claim.claim_id) -Status 'released' -Reason 'unit complete' | Out-Null
    $releasedStore = Get-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims
    Assert-Equal ([string]$releasedStore.claims[0].status) 'released' 'Released claim status should be persisted.'

    $staleStore = New-MediaPipelineLocalWorkerClaimStore
    $staleStore.claims = @([pscustomobject]@{
        schema_version = 'local_worker_claim.v1'
        claim_id       = 'stale'
        status         = 'running'
        source_path    = $file.FullName
        source_key     = ConvertTo-MediaPipelineLocalWorkerPathKey -Path $file.FullName
        worker_pid     = 999999
        result_path    = ''
        owner_run_id   = 'old-run'
        claimed_at     = (Get-Date).AddMinutes(-10).ToString('o')
        updated_at     = (Get-Date).AddMinutes(-10).ToString('o')
    })
    Write-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -Store $staleStore
    $repaired = Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -CurrentRunId $script:PipelineRunId -ClaimStaleSeconds 1
    Assert-Equal ([string]$repaired.claims[0].status) 'released_stale' 'Repair must release stale claims without a live worker process.'

    $progress = [ordered]@{
        CurrentStage = 'encoding'
        Status = 'Encoding'
        CurrentRoute = 'ENCODE'
        CurrentStagePercent = 42
        CurrentLibraryId = 'movies'
        CurrentLibraryName = 'Movies'
        CurrentLibraryDesignation = 'movie'
        CurrentLibrarySourceRoot = 'C:\Movies'
        CurrentLibraryOutputRoot = 'D:\Movies'
    }
    Write-MediaPipelineJsonAtomic -Path $slot.ProgressFile -InputObject $progress -Depth 5 | Out-Null
    $activePayload = Write-MediaPipelineLocalWorkerActiveJobs `
        -ActiveJobsPath $script:LocalStateLayout.Paths.LocalWorkerActiveJobs `
        -CompatibilityProgressPath (Join-Path $state 'pipeline_progress.json') `
        -ActiveJobs @([pscustomobject]@{
            SlotLayout = $slot
            Claim = [pscustomobject]@{
                claim_id = 'active'
                source_name = $file.Name
                source_path = $file.FullName
                media_kind = 'movie'
                queue_index = 1
                queue_total = 2
            }
            Process = [pscustomobject]@{ Id = 12345 }
            Status = 'running'
        }) `
        -WriteCompatibilityProgress
    Assert-Equal ([string]$activePayload.schema_version) 'local_worker_active_jobs.v1' 'Active jobs payload schema mismatch.'
    Assert-Equal ([int]$activePayload.job_count) 1 'Active jobs payload should include one job.'
    $persistedActiveJobs = Read-MediaPipelineJsonFile -Path $script:LocalStateLayout.Paths.LocalWorkerActiveJobs
    Assert-Equal ([int]$persistedActiveJobs.job_count) 1 'Active jobs JSON should persist one job.'

    Update-MediaPipelineParentCountersFromWorkerResult -Result ([pscustomobject]@{ Status = 'processed'; Success = $true; Route = 'encode' }) -IsTV:$true
    Assert-Equal $script:totalProcessed 1 'Processed counter should update from worker result.'
    Assert-Equal $script:totalEncoded 1 'Encoded counter should update from worker encode route.'
    Assert-Equal $script:totalTVEpisodes 1 'TV counter should update for TV worker result.'

    Assert-Equal (Join-MediaPipelineProcessArgument -Value 'C:\Path With Spaces\script.ps1') '"C:\Path With Spaces\script.ps1"' 'Process argument quoting should remain stable.'

    Write-Host 'Local worker slot checks passed.'
} finally {
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $previousMutexSuffix
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
