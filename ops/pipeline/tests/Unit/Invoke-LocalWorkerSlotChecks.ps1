Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:TestRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $script:TestRoot)

. (Join-Path $repoRoot 'ops\pipeline\engine\queue\local_worker_slots.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\worker_result.ps1')

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

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $null = $Message
    $null = $Level
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
    $script:WorkerChild = $false
    $script:WorkerHeartbeatPath = ''
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

    $resultClaim = [pscustomobject]@{ claim_id = 'claim-1' }
    $validWorkerResult = [pscustomobject]@{
        SchemaVersion = 'local_worker_result.v1'
        Success       = $true
        Status        = 'processed'
        Reason        = 'ok'
        WorkerClaimId = 'claim-1'
        WorkerRunId   = 'unit-run'
        QueueTerminal = $false
        Retryable     = $true
    }

    $missingResult = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result $null -ResultFileExists:$false -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$missingResult.Status) 'failed_result_missing' 'Exit 0 with missing worker_result.json must not complete the claim.'
    Assert-True ([bool]$missingResult.CountSyntheticFailure) 'Missing worker result should count as a synthetic failure.'

    $unreadableResult = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result $null -ResultFileExists:$true -ResultReadError 'bad json' -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$unreadableResult.Status) 'failed_result_invalid' 'Exit 0 with unreadable worker_result.json must not complete the claim.'
    Assert-True ([string]$unreadableResult.Reason -like '*bad json*') 'Unreadable result reason should include the parse failure.'

    $badSchemaResult = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result ([pscustomobject]@{ SchemaVersion = 'other'; Success = $true; WorkerClaimId = 'claim-1'; WorkerRunId = 'unit-run' }) -ResultFileExists:$true -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$badSchemaResult.Status) 'failed_result_invalid' 'Exit 0 with a wrong worker result schema must not complete the claim.'

    $wrongClaimResult = $validWorkerResult.PSObject.Copy()
    $wrongClaimResult.WorkerClaimId = 'claim-2'
    $claimMismatch = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result $wrongClaimResult -ResultFileExists:$true -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$claimMismatch.Status) 'failed_result_invalid' 'Exit 0 with another claim id must not complete the claim.'

    $wrongRunResult = $validWorkerResult.PSObject.Copy()
    $wrongRunResult.WorkerRunId = 'other-run'
    $runMismatch = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result $wrongRunResult -ResultFileExists:$true -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$runMismatch.Status) 'failed_result_invalid' 'Exit 0 with another run id must not complete the claim.'

    $stringSuccessResult = $validWorkerResult.PSObject.Copy()
    $stringSuccessResult.Success = 'true'
    $badSuccessType = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result $stringSuccessResult -ResultFileExists:$true -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$badSuccessType.Status) 'failed_result_invalid' 'Exit 0 with a non-boolean Success field must not complete the claim.'

    $failedWorkerResult = $validWorkerResult.PSObject.Copy()
    $failedWorkerResult.Success = $false
    $failedWorkerResult.Status = 'processed'
    $failedWorkerResult.Reason = 'child reported failure'
    $successFalse = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result $failedWorkerResult -ResultFileExists:$true -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$successFalse.Status) 'failed' 'Exit 0 with Success=false must release the claim as failed.'
    Assert-True ([bool]$successFalse.CountSyntheticFailure) 'Success=false with a non-failed status should count as a failure.'

    $validCompletion = Resolve-MediaPipelineLocalWorkerSlotCompletion -ExitCode 0 -Result $validWorkerResult -ResultFileExists:$true -Claim $resultClaim -OwnerRunId 'unit-run'
    Assert-Equal ([string]$validCompletion.Status) 'completed' 'Exit 0 with matching successful worker result should complete the claim.'
    Assert-True ([bool]$validCompletion.ApplyCounters) 'Valid worker result should update parent counters.'
    Assert-True (-not [bool]$validCompletion.CountSyntheticFailure) 'Valid worker result should not add a synthetic failure.'

    $script:WorkerChild = $true
    $script:WorkerSlotId = 1
    $script:WorkerRunId = 'unit-run'
    $script:WorkerClaimId = 'claim-1'
    $script:WorkerResultPath = Join-Path $root 'worker_result_schema.json'
    Write-MediaPipelineWorkerChildResult `
        -SourcePath $file.FullName `
        -ProcessResult ([pscustomobject]@{
            Success = $false
            Status = 'failed'
            Reason = 'terminal'
            ErrorCode = 'ENCODE_ERROR'
            QueueTerminal = $true
            Retryable = $false
        }) | Out-Null
    $schemaResult = Read-MediaPipelineJsonFile -Path $script:WorkerResultPath
    Assert-True ($schemaResult.PSObject.Properties['QueueTerminal'] -and $schemaResult.QueueTerminal -is [bool]) 'Worker result schema must emit boolean QueueTerminal.'
    Assert-True ($schemaResult.PSObject.Properties['Retryable'] -and $schemaResult.Retryable -is [bool]) 'Worker result schema must emit boolean Retryable.'
    Assert-True ([bool]$schemaResult.QueueTerminal) 'Worker result should preserve QueueTerminal=true.'
    Assert-True (-not [bool]$schemaResult.Retryable) 'Worker result should preserve Retryable=false.'

    $reuseSlot = Initialize-MediaPipelineWorkerSlotLayout -SlotLayout (New-MediaPipelineWorkerSlotLayout -StateLayout $script:LocalStateLayout -SlotId 2)
    Set-Content -LiteralPath $reuseSlot.ResultFile -Value '{"SchemaVersion":"local_worker_result.v1","Success":true,"Status":"processed","WorkerClaimId":"old-claim","WorkerRunId":"old-run","QueueTerminal":false,"Retryable":true}' -Encoding UTF8
    $reuseClaim = [pscustomobject]@{
        claim_id    = 'claim-reuse'
        source_path = $file.FullName
    }
    $script:CapturedStartProcess = $null
    function Start-Process {
        param(
            [string] $FilePath,
            [string] $ArgumentList,
            [string] $WorkingDirectory,
            [string] $RedirectStandardOutput,
            [string] $RedirectStandardError,
            [object] $WindowStyle,
            [switch] $PassThru
        )
        $script:CapturedStartProcess = [pscustomobject]@{
            FilePath = $FilePath
            ArgumentList = $ArgumentList
            WorkingDirectory = $WorkingDirectory
            RedirectStandardOutput = $RedirectStandardOutput
            RedirectStandardError = $RedirectStandardError
        }
        return [pscustomobject]@{ Id = 4242; HasExited = $false }
    }
    $spawnedWorker = Start-MediaPipelineLocalWorkerChild `
        -Entry $entry `
        -Claim $reuseClaim `
        -SlotLayout $reuseSlot `
        -ScriptPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline.ps1') `
        -ConfigPath (Join-Path $repoRoot 'ops\pipeline\config\MediaPipeline_config.psd1') `
        -PowerShellPath 'pwsh.exe' `
        -OwnerRunId 'unit-run'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$spawnedWorker.MediaPipelineSpawnRequestedAt)) 'Worker child should expose spawn-request timing evidence.'
    Assert-True ([double]$spawnedWorker.MediaPipelineSpawnDurationMs -ge 0) 'Worker child should expose non-negative spawn duration evidence.'
    Assert-True (-not (Test-Path -LiteralPath $reuseSlot.ResultFile -PathType Leaf)) 'Slot reuse should clear the fixed result file before the new child starts.'
    $archivedResults = @(Get-ChildItem -LiteralPath $reuseSlot.ResultArchive -Filter '*worker_result.json' -File)
    Assert-Equal $archivedResults.Count 1 'Slot reuse should archive the stale worker result before deleting it.'
    $archivedResult = Read-MediaPipelineJsonFile -Path $archivedResults[0].FullName
    Assert-Equal ([string]$archivedResult.WorkerClaimId) 'old-claim' 'Archived stale result should preserve the previous claim id.'

    Assert-Equal (Join-MediaPipelineProcessArgument -Value 'C:\Path With Spaces\script.ps1') '"C:\Path With Spaces\script.ps1"' 'Process argument quoting should remain stable.'

    Write-Host 'Local worker slot checks passed.'
} finally {
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $previousMutexSuffix
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
