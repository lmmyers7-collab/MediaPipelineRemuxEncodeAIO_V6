# CSV rerun final-library publication transaction and crash recovery.

function Invoke-RerunPublicationCheckpoint {
    param([Parameter(Mandatory)] [string]$Name, $Transaction)
    $injector = Get-Variable -Name RerunPublicationFaultInjector -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    if ($injector -is [scriptblock]) {
        & $injector $Name $Transaction
    }
}

function Get-RerunPublicationFileIdentity {
    param([Parameter(Mandatory)] [string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Publication artifact is unavailable: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    return [pscustomobject]@{
        size = [long]$item.Length
        sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    }
}

function Test-RerunPublicationFileIdentity {
    param([Parameter(Mandatory)] $Artifact, [string]$Path = '')
    if ([string]::IsNullOrWhiteSpace($Path)) { $Path = [string]$Artifact.destination }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
        $actual = Get-RerunPublicationFileIdentity -Path $Path
        return (
            [long]$actual.size -eq [long]$Artifact.size -and
            [string]$actual.sha256 -ceq [string]$Artifact.sha256
        )
    } catch {
        return $false
    }
}

function Set-RerunPublicationTransactionState {
    param(
        [Parameter(Mandatory)] $Transaction,
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$State,
        [string]$ErrorText = ''
    )
    Set-RerunRecoveryValue -Object $Transaction -Name 'state' -Value $State
    Set-RerunRecoveryValue -Object $Transaction -Name 'updated_at' -Value ([datetime]::UtcNow.ToString('o'))
    Set-RerunRecoveryValue -Object $Transaction -Name 'last_error' -Value $ErrorText
    Write-RerunManifest -Path $Path -Payload $Transaction
}

function Sync-RerunPublicationPlanEvidence {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] $Transaction,
        $ExecutionManifest = $null,
        [string]$ExecutionManifestPath = ''
    )
    Set-RerunRecoveryValue -Object $Plan -Name 'publication_transaction_id' -Value ([string]$Transaction.transaction_id)
    Set-RerunRecoveryValue -Object $Plan -Name 'publication_transaction_manifest_path' -Value ([string]$Transaction.transaction_path)
    Set-RerunRecoveryValue -Object $Plan -Name 'publication_transaction_state' -Value ([string]$Transaction.state)
    if ($null -ne $ExecutionManifest -and -not [string]::IsNullOrWhiteSpace($ExecutionManifestPath)) {
        Write-RerunManifest -Path $ExecutionManifestPath -Payload $ExecutionManifest
    }
}

function Get-RerunPublicationTransactionPath {
    param(
        [Parameter(Mandatory)] [string]$FinalHoldRoot,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string]$AttemptId
    )
    if ($BatchId -notmatch '^[A-Za-z0-9._-]+$') { throw "CSV rerun publication BatchId contains unsupported characters: $BatchId" }
    $rowIndex = 0
    try { $rowIndex = [int](Get-RerunRecoveryValue -Object $Plan -Name 'row_index' -Default 0) } catch {}
    $root = Join-Path (Join-Path $FinalHoldRoot $BatchId) 'PublicationTransactions'
    return (Join-Path $root ("row_{0:D6}.{1}.publication.json" -f $rowIndex, $AttemptId))
}

function New-RerunPublicationArtifact {
    param(
        [Parameter(Mandatory)] [string]$Role,
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Destination,
        [Parameter(Mandatory)] [string]$PathToken
    )
    $destinationDir = Split-Path -Parent $Destination
    $destinationLeaf = Split-Path -Leaf $Destination
    return [ordered]@{
        role = $Role
        source = $Source
        destination = $Destination
        stage = Join-Path $destinationDir (".$destinationLeaf.mediapipeline-rerun-$PathToken.stage")
        backup = Join-Path $destinationDir (".$destinationLeaf.mediapipeline-rerun-$PathToken.backup")
        original_exists = [bool](Test-Path -LiteralPath $Destination -PathType Leaf)
        size = 0
        sha256 = ''
    }
}

function New-RerunPublicationSidecarPayload {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] $PipelineSidecar,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$Destination,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] [string]$TransactionId,
        [Parameter(Mandatory)] [string]$DestinationPolicy,
        [Parameter(Mandatory)] [bool]$IsReplacement,
        [Parameter(Mandatory)] [array]$SrtArtifacts
    )
    $sidecarCopy = Copy-RerunRecordProperties -Record $PipelineSidecar
    $sidecarCopy['output_path'] = $Destination
    $sidecarCopy['output_file'] = Split-Path -Leaf $Destination
    $sidecarCopy['publish_state'] = 'published'
    if ([string]::IsNullOrWhiteSpace([string]$sidecarCopy['publish_mode'])) { $sidecarCopy['publish_mode'] = 'immediate' }
    $sidecarCopy['rerun_destination_policy'] = $DestinationPolicy
    $sidecarCopy['rerun_batch_id'] = $BatchId
    $sidecarCopy['rerun_source_path'] = [string]$Plan.source_path
    $sidecarCopy['rerun_verified_output_path'] = $VerifiedOutput
    $sidecarCopy['rerun_final_replacement'] = $IsReplacement
    $sidecarCopy['rerun_publication_transaction_id'] = $TransactionId

    $trackCopies = [System.Collections.Generic.List[object]]::new()
    foreach ($record in @(Get-RerunArrayField -Object $PipelineSidecar -Name 'tx3g_srt_tracks')) {
        $recordMap = Copy-RerunRecordProperties -Record $record
        $source = Get-RerunTrackSourcePath -Record $record
        if (-not [string]::IsNullOrWhiteSpace($source) -and [System.IO.Path]::GetExtension($source).ToLowerInvariant() -eq '.srt') {
            $matching = @($SrtArtifacts | Where-Object { [string]$_.source -ceq $source })
            if ($matching.Count -gt 0) {
                $artifact = $matching[0]
                $recordMap['path'] = [string]$artifact.destination
                $recordMap['file_name'] = Split-Path -Leaf ([string]$artifact.destination)
                $recordMap['status'] = 'written'
            }
        }
        $trackCopies.Add([pscustomobject]$recordMap) | Out-Null
    }
    if ($trackCopies.Count -gt 0) { $sidecarCopy['tx3g_srt_tracks'] = @($trackCopies) }
    return $sidecarCopy
}

function New-RerunFinalPublicationTransaction {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$Destination,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] [string]$FinalHoldRoot,
        [Parameter(Mandatory)] [string]$DestinationPolicy,
        [Parameter(Mandatory)] [string]$SuccessStatus,
        [Parameter(Mandatory)] [string]$SuccessReason,
        [Parameter(Mandatory)] [bool]$IsReplacement
    )
    if (-not (Test-Path -LiteralPath $VerifiedOutput -PathType Leaf)) { throw "verified output not found: $VerifiedOutput" }
    if (Test-RerunSamePath -Left $VerifiedOutput -Right $Destination) {
        throw 'verified output and final publication destination must be different paths'
    }
    $allowSourceOutputRoot = ([bool]$Plan.source_overwrite_confirmed -and (Test-RerunSamePath -Left $Destination -Right ([string]$Plan.source_path)))
    if (-not $allowSourceOutputRoot -and -not [string]::IsNullOrWhiteSpace([string]$Plan.final_output_root) -and -not (Test-RerunPathUnderRoot -Path $Destination -Root ([string]$Plan.final_output_root))) {
        throw "final publication destination resolves outside configured output root: $Destination"
    }
    $sourceSidecarPath = Get-RerunPipelineSidecarPath -OutputPath $VerifiedOutput
    if (-not (Test-Path -LiteralPath $sourceSidecarPath -PathType Leaf)) {
        throw "verified output pipeline sidecar not found: $sourceSidecarPath"
    }
    $pipelineSidecar = Read-RerunPipelineSidecar -OutputPath $VerifiedOutput
    if ($null -eq $pipelineSidecar) { throw "verified output pipeline sidecar is unreadable: $sourceSidecarPath" }

    $rowIndex = 0
    try { $rowIndex = [int](Get-RerunRecoveryValue -Object $Plan -Name 'row_index' -Default 0) } catch {}
    $attemptId = [guid]::NewGuid().ToString('N').Substring(0, 12)
    $transactionPath = Get-RerunPublicationTransactionPath -FinalHoldRoot $FinalHoldRoot -BatchId $BatchId -Plan $Plan -AttemptId $attemptId
    $transactionId = "$BatchId.row_$rowIndex.$attemptId"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $pathTokenBytes = [System.Text.Encoding]::UTF8.GetBytes($transactionId)
        $pathToken = [System.BitConverter]::ToString($sha.ComputeHash($pathTokenBytes)).Replace('-', '').Substring(0, 16).ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }

    $artifacts = [System.Collections.Generic.List[object]]::new()
    $mediaArtifact = New-RerunPublicationArtifact -Role 'media' -Source $VerifiedOutput -Destination $Destination -PathToken $pathToken
    $artifacts.Add([pscustomobject]$mediaArtifact) | Out-Null
    $verifiedDir = Split-Path -Parent $VerifiedOutput
    $finalDir = Split-Path -Parent $Destination
    $destinationKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    [void]$destinationKeys.Add([System.IO.Path]::GetFullPath($Destination))
    $srtArtifacts = [System.Collections.Generic.List[object]]::new()
    foreach ($record in @(Get-RerunArrayField -Object $pipelineSidecar -Name 'tx3g_srt_tracks')) {
        $source = Get-RerunTrackSourcePath -Record $record
        if ([string]::IsNullOrWhiteSpace($source) -or [System.IO.Path]::GetExtension($source).ToLowerInvariant() -ne '.srt') { continue }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or -not (Test-RerunPathUnderRoot -Path $source -Root $verifiedDir)) {
            throw "declared rerun SRT companion is unavailable or outside verified output root: $source"
        }
        $srtDestination = Get-RerunFinalCompanionPath -SourcePath $source -VerifiedOutput $VerifiedOutput -FinalOutput $Destination
        if ([string]::IsNullOrWhiteSpace($srtDestination) -or -not (Test-RerunPathUnderRoot -Path $srtDestination -Root $finalDir)) {
            throw "sidecar destination resolves outside final output folder: $srtDestination"
        }
        if (-not $allowSourceOutputRoot -and -not [string]::IsNullOrWhiteSpace([string]$Plan.final_output_root) -and -not (Test-RerunPathUnderRoot -Path $srtDestination -Root ([string]$Plan.final_output_root))) {
            throw "sidecar destination resolves outside configured output root: $srtDestination"
        }
        if (-not $destinationKeys.Add([System.IO.Path]::GetFullPath($srtDestination))) {
            throw "duplicate rerun publication destination: $srtDestination"
        }
        $artifact = New-RerunPublicationArtifact -Role 'srt' -Source $source -Destination $srtDestination -PathToken $pathToken
        $srtArtifacts.Add([pscustomobject]$artifact) | Out-Null
        $artifacts.Add([pscustomobject]$artifact) | Out-Null
    }

    $destinationSidecarPath = Get-RerunPipelineSidecarPath -OutputPath $Destination
    if (-not $destinationKeys.Add([System.IO.Path]::GetFullPath($destinationSidecarPath))) {
        throw "duplicate rerun publication destination: $destinationSidecarPath"
    }
    $sidecarArtifact = New-RerunPublicationArtifact -Role 'pipeline_sidecar' -Source $sourceSidecarPath -Destination $destinationSidecarPath -PathToken $pathToken
    $sidecarPayload = New-RerunPublicationSidecarPayload -Plan $Plan -PipelineSidecar $pipelineSidecar -VerifiedOutput $VerifiedOutput -Destination $Destination -BatchId $BatchId -TransactionId $transactionId -DestinationPolicy $DestinationPolicy -IsReplacement $IsReplacement -SrtArtifacts @($srtArtifacts)
    $artifacts.Add([pscustomobject]$sidecarArtifact) | Out-Null

    return [ordered]@{
        schema_version = 'rerun_publication_transaction.v1'
        transaction_id = $transactionId
        transaction_path = $transactionPath
        batch_id = $BatchId
        row_index = $rowIndex
        state = 'prepared'
        created_at = [datetime]::UtcNow.ToString('o')
        updated_at = [datetime]::UtcNow.ToString('o')
        last_error = ''
        destination_policy = $DestinationPolicy
        success_status = $SuccessStatus
        success_reason = $SuccessReason
        is_replacement = $IsReplacement
        verified_output = $VerifiedOutput
        destination = $Destination
        completed_manifest_path = [string]$script:RerunCompletedJobsManifest
        completed_manifest_append = 'pending'
        sidecar_payload = $sidecarPayload
        artifacts = @($artifacts)
        backup_hold_paths = @()
    }
}

function Copy-RerunPublicationArtifactToStage {
    param([Parameter(Mandatory)] $Artifact)
    $stage = [string]$Artifact.stage
    $stageDir = Split-Path -Parent $stage
    if (-not (Test-Path -LiteralPath $stageDir)) { New-Item -ItemType Directory -Path $stageDir -Force | Out-Null }
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Force -ErrorAction Stop }
    Copy-Item -LiteralPath ([string]$Artifact.source) -Destination $stage -Force -ErrorAction Stop
    $sourceIdentity = Get-RerunPublicationFileIdentity -Path ([string]$Artifact.source)
    $stageIdentity = Get-RerunPublicationFileIdentity -Path $stage
    if ([long]$sourceIdentity.size -ne [long]$stageIdentity.size -or [string]$sourceIdentity.sha256 -cne [string]$stageIdentity.sha256) {
        throw "Staged publication artifact identity mismatch: $stage"
    }
    Set-RerunRecoveryValue -Object $Artifact -Name 'size' -Value ([long]$stageIdentity.size)
    Set-RerunRecoveryValue -Object $Artifact -Name 'sha256' -Value ([string]$stageIdentity.sha256)
}

function Test-RerunCompletedPublicationEntry {
    param([Parameter(Mandatory)] $Transaction)
    $path = [string]$Transaction.completed_manifest_path
    if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [pscustomobject]@{ Readable = $true; Found = $false }
    }
    try {
        foreach ($line in @(Get-Content -LiteralPath $path -ErrorAction Stop)) {
            if ([string]::IsNullOrWhiteSpace([string]$line)) { continue }
            $row = $line | ConvertFrom-Json -ErrorAction Stop
            if ([string]$row.rerun_publication_transaction_id -ceq [string]$Transaction.transaction_id) {
                return [pscustomobject]@{ Readable = $true; Found = $true }
            }
        }
        return [pscustomobject]@{ Readable = $true; Found = $false }
    } catch {
        return [pscustomobject]@{ Readable = $false; Found = $false }
    }
}

function Test-RerunPublicationDestinationsCommitted {
    param([Parameter(Mandatory)] $Transaction)
    foreach ($artifact in @($Transaction.artifacts)) {
        if (-not (Test-RerunPublicationFileIdentity -Artifact $artifact)) { return $false }
    }
    return $true
}

function Restore-RerunPublicationTransaction {
    param([Parameter(Mandatory)] $Transaction)
    $errors = [System.Collections.Generic.List[string]]::new()
    $reverseArtifacts = @($Transaction.artifacts)
    [array]::Reverse($reverseArtifacts)
    foreach ($artifact in $reverseArtifacts) {
        $destination = [string]$artifact.destination
        $backup = [string]$artifact.backup
        $stage = [string]$artifact.stage
        try {
            if (Test-Path -LiteralPath $backup -PathType Leaf) {
                if (Test-Path -LiteralPath $destination) {
                    if (-not (Test-RerunPublicationFileIdentity -Artifact $artifact -Path $destination)) {
                        throw "destination contains unrecognized bytes during rollback: $destination"
                    }
                    Remove-Item -LiteralPath $destination -Force -ErrorAction Stop
                }
                Move-Item -LiteralPath $backup -Destination $destination -Force -ErrorAction Stop
            } elseif ([bool]$artifact.original_exists) {
                if (-not (Test-Path -LiteralPath $destination -PathType Leaf)) {
                    throw "original artifact backup is missing during rollback: $backup"
                }
                if (Test-RerunPublicationFileIdentity -Artifact $artifact -Path $destination) {
                    throw "original artifact was replaced but its backup is missing: $destination"
                }
            } elseif (Test-Path -LiteralPath $destination -PathType Leaf) {
                if (-not (Test-RerunPublicationFileIdentity -Artifact $artifact -Path $destination)) {
                    throw "destination contains unrecognized bytes during rollback: $destination"
                }
                Remove-Item -LiteralPath $destination -Force -ErrorAction Stop
            }
            if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Force -ErrorAction Stop }
        } catch {
            $errors.Add($_.Exception.Message) | Out-Null
        }
    }
    return @($errors)
}

function Repair-RerunFinalPublicationTransaction {
    param([Parameter(Mandatory)] [string]$TransactionPath)
    if (-not (Test-Path -LiteralPath $TransactionPath -PathType Leaf)) {
        return [pscustomobject]@{ Status = 'missing'; Transaction = $null; Errors = @("Publication transaction manifest is missing: $TransactionPath") }
    }
    $transaction = Get-Content -LiteralPath $TransactionPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $state = [string]$transaction.state
    if ($state -eq 'committed') {
        $completion = Test-RerunCompletedPublicationEntry -Transaction $transaction
        if (-not [bool]$completion.Readable -or -not [bool]$completion.Found -or -not (Test-RerunPublicationDestinationsCommitted -Transaction $transaction)) {
            Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'rollback_required' -ErrorText 'Committed publication evidence no longer matches completion and final artifact identities.'
            return [pscustomobject]@{ Status = 'rollback_required'; Transaction = $transaction; Errors = @('Committed publication evidence no longer matches completion and final artifact identities.') }
        }
        $transactionDirectory = Split-Path -Parent $TransactionPath
        $batchHoldRoot = Split-Path -Parent $transactionDirectory
        $finalHoldRoot = Split-Path -Parent $batchHoldRoot
        Move-RerunPublicationBackupsToHold -Transaction $transaction -FinalHoldRoot $finalHoldRoot
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'committed'
        $verifiedOutput = [string]$transaction.verified_output
        if (-not [string]::IsNullOrWhiteSpace($verifiedOutput) -and (Test-Path -LiteralPath $verifiedOutput -PathType Leaf)) {
            Remove-Item -LiteralPath $verifiedOutput -Force -ErrorAction SilentlyContinue
        }
        return [pscustomobject]@{ Status = 'committed'; Transaction = $transaction; Errors = @() }
    }
    $completion = Test-RerunCompletedPublicationEntry -Transaction $transaction
    if (-not [bool]$completion.Readable) {
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'rollback_required' -ErrorText 'Completed-jobs evidence is unreadable; automatic rollback is unsafe.'
        return [pscustomobject]@{ Status = 'rollback_required'; Transaction = $transaction; Errors = @('Completed-jobs evidence is unreadable; automatic rollback is unsafe.') }
    }
    if ([bool]$completion.Found) {
        if (Test-RerunPublicationDestinationsCommitted -Transaction $transaction) {
            Set-RerunRecoveryValue -Object $transaction -Name 'completed_manifest_append' -Value 'appended'
            Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'committed'
            $transactionDirectory = Split-Path -Parent $TransactionPath
            $batchHoldRoot = Split-Path -Parent $transactionDirectory
            $finalHoldRoot = Split-Path -Parent $batchHoldRoot
            Move-RerunPublicationBackupsToHold -Transaction $transaction -FinalHoldRoot $finalHoldRoot
            Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'committed'
            $verifiedOutput = [string]$transaction.verified_output
            if (-not [string]::IsNullOrWhiteSpace($verifiedOutput) -and (Test-Path -LiteralPath $verifiedOutput -PathType Leaf)) {
                Remove-Item -LiteralPath $verifiedOutput -Force -ErrorAction SilentlyContinue
            }
            return [pscustomobject]@{ Status = 'committed'; Transaction = $transaction; Errors = @() }
        }
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'rollback_required' -ErrorText 'Completion evidence exists but final artifact identities do not match.'
        return [pscustomobject]@{ Status = 'rollback_required'; Transaction = $transaction; Errors = @('Completion evidence exists but final artifact identities do not match.') }
    }
    $rollbackErrors = @(Restore-RerunPublicationTransaction -Transaction $transaction)
    if ($rollbackErrors.Count -gt 0) {
        $message = $rollbackErrors -join ' | '
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'rollback_required' -ErrorText $message
        return [pscustomobject]@{ Status = 'rollback_required'; Transaction = $transaction; Errors = @($rollbackErrors) }
    }
    Set-RerunPublicationTransactionState -Transaction $transaction -Path $TransactionPath -State 'rolled_back'
    return [pscustomobject]@{ Status = 'rolled_back'; Transaction = $transaction; Errors = @() }
}

function Move-RerunPublicationBackupsToHold {
    param(
        [Parameter(Mandatory)] $Transaction,
        [Parameter(Mandatory)] [string]$FinalHoldRoot
    )
    $holdRoot = Join-Path (Join-Path (Join-Path $FinalHoldRoot ([string]$Transaction.batch_id)) 'CommittedBackups') ([string]$Transaction.transaction_id)
    $held = [System.Collections.Generic.List[string]]::new()
    foreach ($artifact in @($Transaction.artifacts)) {
        $backup = [string]$artifact.backup
        $roleHoldRoot = Join-Path $holdRoot ([string]$artifact.role)
        $heldPath = Join-Path $roleHoldRoot (Split-Path -Leaf ([string]$artifact.destination))
        if ((Test-Path -LiteralPath $backup -PathType Leaf) -and (Test-RerunSamePath -Left $backup -Right $heldPath)) {
            $held.Add($heldPath) | Out-Null
            continue
        }
        if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
            if (Test-Path -LiteralPath $heldPath -PathType Leaf) {
                Set-RerunRecoveryValue -Object $artifact -Name 'backup' -Value $heldPath
                $held.Add($heldPath) | Out-Null
            }
            continue
        }
        try {
            New-Item -ItemType Directory -Path $roleHoldRoot -Force | Out-Null
            if (Test-Path -LiteralPath $heldPath) { throw "committed backup hold path already exists: $heldPath" }
            Move-Item -LiteralPath $backup -Destination $heldPath -Force -ErrorAction Stop
            Set-RerunRecoveryValue -Object $artifact -Name 'backup' -Value $heldPath
            $held.Add($heldPath) | Out-Null
        } catch {
            Write-RerunLog "Committed rerun publication backup remains beside final output: $backup : $($_.Exception.Message)" 'WARN'
            $held.Add($backup) | Out-Null
        }
    }
    Set-RerunRecoveryValue -Object $Transaction -Name 'backup_hold_paths' -Value @($held)
}

function Set-RerunPlanFromCommittedPublication {
    param([Parameter(Mandatory)] $Plan, [Parameter(Mandatory)] $Transaction)
    $artifacts = @($Transaction.artifacts)
    $sidecar = @($artifacts | Where-Object { [string]$_.role -eq 'pipeline_sidecar' })
    $srt = @($artifacts | Where-Object { [string]$_.role -eq 'srt' })
    $media = @($artifacts | Where-Object { [string]$_.role -eq 'media' })
    $Plan.status = [string]$Transaction.success_status
    $Plan.published_path = [string]$Transaction.destination
    $Plan.reason = [string]$Transaction.success_reason
    $Plan.pipeline_sidecar_publish = 'published'
    $Plan.pipeline_sidecar_path = if ($sidecar.Count -gt 0) { [string]$sidecar[0].destination } else { '' }
    $Plan.published_sidecar_paths = @($sidecar | ForEach-Object { [string]$_.destination }) + @($srt | ForEach-Object { [string]$_.destination })
    $Plan.replaced_sidecar_hold_paths = @(
        $artifacts |
            Where-Object { [string]$_.role -ne 'media' -and [bool]$_.original_exists -and -not [string]::IsNullOrWhiteSpace([string]$_.backup) } |
            ForEach-Object { [string]$_.backup }
    )
    if ([bool]$Transaction.is_replacement -and $media.Count -gt 0 -and [bool]$media[0].original_exists) {
        $Plan.replaced_final_hold_path = [string]$media[0].backup
    }
    $Plan.completed_manifest_path = [string]$Transaction.completed_manifest_path
    $Plan.completed_manifest_append = 'appended'
    $Plan.publication_transaction_id = [string]$Transaction.transaction_id
    $Plan.publication_transaction_manifest_path = [string]$Transaction.transaction_path
    $Plan.publication_transaction_state = 'committed'
}

function Invoke-RerunFinalPublicationTransaction {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$Destination,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] [string]$FinalHoldRoot,
        [Parameter(Mandatory)] [string]$DestinationPolicy,
        [Parameter(Mandatory)] [string]$SuccessStatus,
        [Parameter(Mandatory)] [string]$SuccessReason,
        [Parameter(Mandatory)] [bool]$IsReplacement,
        $ExecutionManifest = $null,
        [string]$ExecutionManifestPath = ''
    )
    $transaction = New-RerunFinalPublicationTransaction -Plan $Plan -VerifiedOutput $VerifiedOutput -Destination $Destination -BatchId $BatchId -FinalHoldRoot $FinalHoldRoot -DestinationPolicy $DestinationPolicy -SuccessStatus $SuccessStatus -SuccessReason $SuccessReason -IsReplacement $IsReplacement
    $transactionPath = [string]$transaction.transaction_path
    Set-RerunPublicationTransactionState -Transaction $transaction -Path $transactionPath -State 'prepared'
    Sync-RerunPublicationPlanEvidence -Plan $Plan -Transaction $transaction -ExecutionManifest $ExecutionManifest -ExecutionManifestPath $ExecutionManifestPath
    Invoke-RerunPublicationCheckpoint -Name 'prepared' -Transaction $transaction
    try {
        $media = @($transaction.artifacts | Where-Object { [string]$_.role -eq 'media' })[0]
        Copy-RerunPublicationArtifactToStage -Artifact $media
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $transactionPath -State 'media_staged'
        Sync-RerunPublicationPlanEvidence -Plan $Plan -Transaction $transaction -ExecutionManifest $ExecutionManifest -ExecutionManifestPath $ExecutionManifestPath
        Invoke-RerunPublicationCheckpoint -Name 'media_staged' -Transaction $transaction

        foreach ($artifact in @($transaction.artifacts | Where-Object { [string]$_.role -eq 'srt' })) {
            Copy-RerunPublicationArtifactToStage -Artifact $artifact
            Invoke-RerunPublicationCheckpoint -Name 'srt_staged' -Transaction $transaction
        }
        $sidecar = @($transaction.artifacts | Where-Object { [string]$_.role -eq 'pipeline_sidecar' })[0]
        $sidecarDir = Split-Path -Parent ([string]$sidecar.stage)
        if (-not (Test-Path -LiteralPath $sidecarDir)) { New-Item -ItemType Directory -Path $sidecarDir -Force | Out-Null }
        Write-RerunManifest -Path ([string]$sidecar.stage) -Payload $transaction.sidecar_payload
        $sidecarIdentity = Get-RerunPublicationFileIdentity -Path ([string]$sidecar.stage)
        Set-RerunRecoveryValue -Object $sidecar -Name 'size' -Value ([long]$sidecarIdentity.size)
        Set-RerunRecoveryValue -Object $sidecar -Name 'sha256' -Value ([string]$sidecarIdentity.sha256)
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $transactionPath -State 'companions_staged'
        Sync-RerunPublicationPlanEvidence -Plan $Plan -Transaction $transaction -ExecutionManifest $ExecutionManifest -ExecutionManifestPath $ExecutionManifestPath
        Invoke-RerunPublicationCheckpoint -Name 'companions_staged' -Transaction $transaction

        Set-RerunPublicationTransactionState -Transaction $transaction -Path $transactionPath -State 'commit_started'
        Sync-RerunPublicationPlanEvidence -Plan $Plan -Transaction $transaction -ExecutionManifest $ExecutionManifest -ExecutionManifestPath $ExecutionManifestPath
        Invoke-RerunPublicationCheckpoint -Name 'commit_started' -Transaction $transaction
        foreach ($artifact in @($transaction.artifacts)) {
            $destinationPath = [string]$artifact.destination
            $backupPath = [string]$artifact.backup
            if (Test-Path -LiteralPath $backupPath) { throw "publication backup path already exists: $backupPath" }
            if (Test-Path -LiteralPath $destinationPath -PathType Leaf) {
                Move-Item -LiteralPath $destinationPath -Destination $backupPath -Force -ErrorAction Stop
            }
            Move-Item -LiteralPath ([string]$artifact.stage) -Destination $destinationPath -Force -ErrorAction Stop
            Invoke-RerunPublicationCheckpoint -Name ("artifact_committed:" + [string]$artifact.role) -Transaction $transaction
        }
        if (-not (Test-RerunPublicationDestinationsCommitted -Transaction $transaction)) {
            throw 'Final publication artifact verification failed after same-volume commit.'
        }
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $transactionPath -State 'artifacts_committed'
        Invoke-RerunPublicationCheckpoint -Name 'artifacts_committed' -Transaction $transaction
        $completed = Add-RerunCompletedJobsManifestEntry -OutputPath $Destination -Payload $transaction.sidecar_payload
        if (-not $completed) { throw 'Completed-jobs manifest append failed for final publication transaction.' }
        Set-RerunRecoveryValue -Object $transaction -Name 'completed_manifest_append' -Value 'appended'
        Invoke-RerunPublicationCheckpoint -Name 'completion_appended' -Transaction $transaction
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $transactionPath -State 'committed'
        Move-RerunPublicationBackupsToHold -Transaction $transaction -FinalHoldRoot $FinalHoldRoot
        Set-RerunPublicationTransactionState -Transaction $transaction -Path $transactionPath -State 'committed'
        Set-RerunPlanFromCommittedPublication -Plan $Plan -Transaction $transaction
        Sync-RerunPublicationPlanEvidence -Plan $Plan -Transaction $transaction -ExecutionManifest $ExecutionManifest -ExecutionManifestPath $ExecutionManifestPath
        if (Test-Path -LiteralPath $VerifiedOutput -PathType Leaf) {
            Remove-Item -LiteralPath $VerifiedOutput -Force -ErrorAction SilentlyContinue
        }
        return $transaction
    } catch {
        $failure = $_.Exception.Message
        try {
            Set-RerunRecoveryValue -Object $transaction -Name 'last_error' -Value $failure
            $repair = Repair-RerunFinalPublicationTransaction -TransactionPath $transactionPath
            $transaction = $repair.Transaction
            Sync-RerunPublicationPlanEvidence -Plan $Plan -Transaction $transaction -ExecutionManifest $ExecutionManifest -ExecutionManifestPath $ExecutionManifestPath
            if ([string]$repair.Status -eq 'committed') {
                Set-RerunPlanFromCommittedPublication -Plan $Plan -Transaction $transaction
                return $transaction
            }
            if ([string]$repair.Status -eq 'rollback_required') {
                throw "$failure Automatic rollback requires review: $(@($repair.Errors) -join ' | ')"
            }
        } catch {
            if ($_.Exception.Message -like "$failure Automatic rollback requires review:*") { throw }
            throw "$failure Automatic publication recovery failed: $($_.Exception.Message)"
        }
        throw "$failure Publication transaction rolled back; verified output remains retryable."
    }
}
