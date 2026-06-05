# ==============================================================================
# ops\pipeline\engine\publish\pending_sidecar_transactions.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\publish\pending_transactions.ps1. Keep function names
# stable; pending_transactions.ps1 dot-sources this file as the public surface.
# ==============================================================================

function Copy-PendingTx3gRecordWithStatus {
    param(
        $Record,
        [Parameter(Mandatory)] [string] $Status,
        [string] $Path,
        [int] $CueCount = 0,
        [bool] $PreservedExisting = $false
    )

    $map = [ordered]@{}
    if ($Record) {
        foreach ($prop in $Record.PSObject.Properties) {
            $map[$prop.Name] = $prop.Value
        }
    }
    $map['path'] = $Path
    $map['file_name'] = if ($Path) { Split-Path -Leaf $Path } else { '' }
    $map['status'] = $Status
    $map['cue_count'] = $CueCount
    $map['preserved_existing'] = $PreservedExisting
    return [pscustomobject]$map
}

function New-PendingTx3gPublishFailure {
    param(
        $Record,
        [Parameter(Mandatory)] [string] $Reason
    )

    $streamIndex = if ($Record -and $null -ne $Record.source_stream_index) { [int]$Record.source_stream_index } else { -1 }
    return New-StandardFailureRecord -Stage 'pending-tx3g-sidecar' -Operation 'pending-tx3g-sidecar' -Category 'publish' -Reason $Reason -ErrorCode 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED' -Tool 'filesystem' -Retryable $true -AdditionalProperties @{
        StreamIndex     = $streamIndex
        stream_index    = $streamIndex
        SubtitleOrdinal = if ($Record) { $Record.subtitle_ordinal } else { $null }
        subtitle_ordinal = if ($Record) { $Record.subtitle_ordinal } else { $null }
        Language        = if ($Record -and $Record.language) { [string]$Record.language } else { 'und' }
        Title           = if ($Record -and $Record.title) { [string]$Record.title } else { '' }
        SourceIsDefault = if ($Record -and $null -ne $Record.source_is_default) { [bool]$Record.source_is_default } else { $false }
        source_is_default = if ($Record -and $null -ne $Record.source_is_default) { [bool]$Record.source_is_default } else { $false }
        IsForced        = if ($Record -and $null -ne $Record.is_forced) { [bool]$Record.is_forced } else { $false }
        is_forced       = if ($Record -and $null -ne $Record.is_forced) { [bool]$Record.is_forced } else { $false }
        ErrorText       = $Reason
        error_text      = $Reason
    }
}

function New-PendingSidecarBackupPath {
    param(
        [Parameter(Mandatory)] [string] $SidecarPath,
        [Parameter(Mandatory)] [string] $PublishTransactionId
    )

    $dir = Split-Path -Parent $SidecarPath
    if ([string]::IsNullOrWhiteSpace($dir)) { $dir = (Get-Location).Path }
    $leaf = Split-Path -Leaf $SidecarPath
    return (Join-Path $dir (".{0}.mp-pending-sidecar-backup.{1}" -f $leaf, $PublishTransactionId))
}

function Restore-PendingSidecarBackupIntoPlace {
    param(
        [Parameter(Mandatory)] [string] $BackupPath,
        [Parameter(Mandatory)] [string] $DestinationPath,
        [string] $Context = ''
    )

    if (Test-Path -LiteralPath $DestinationPath -PathType Leaf -ErrorAction SilentlyContinue) {
        $rollbackBackup = "$BackupPath.rollback-target"
        try {
            [System.IO.File]::Replace($BackupPath, $DestinationPath, $rollbackBackup, $true)
            Remove-Item -LiteralPath $rollbackBackup -Force -ErrorAction SilentlyContinue
            return
        } catch {
            Remove-Item -LiteralPath $rollbackBackup -Force -ErrorAction SilentlyContinue
            Write-Log "${Context}pending sidecar restore replace failed for $DestinationPath (will use overwrite move): $($_.Exception.Message)" "WARN"
            [System.IO.File]::Move($BackupPath, $DestinationPath, $true)
            return
        }
    }

    [System.IO.File]::Move($BackupPath, $DestinationPath, $true)
}

function Undo-PendingPublishedSidecarFiles {
    param(
        [array] $PublishedSidecars = @(),
        [string] $Context = ''
    )

    foreach ($entry in @($PublishedSidecars)) {
        if ($null -eq $entry) { continue }
        $status = [string](Get-PendingObjectProperty -Object $entry -Name 'status')
        if ($status -ne 'written') { continue }
        $path = [string](Get-PendingObjectProperty -Object $entry -Name 'path')
        $backupPath = [string](Get-PendingObjectProperty -Object $entry -Name 'backup_path')
        $existedBefore = [bool](Get-PendingObjectProperty -Object $entry -Name 'existed_before')
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        try {
            if (-not [string]::IsNullOrWhiteSpace($backupPath) -and (Test-Path -LiteralPath $backupPath -PathType Leaf -ErrorAction SilentlyContinue)) {
                Restore-PendingSidecarBackupIntoPlace -BackupPath $backupPath -DestinationPath $path -Context $Context
                Write-Log "${Context}pending sidecar restored after failed drain reveal: $path" "WARN"
                continue
            }
            if (-not $existedBefore -and (Test-Path -LiteralPath $path -PathType Leaf -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $path -Force -ErrorAction Stop
                Write-Log "${Context}pending sidecar removed after failed drain reveal: $path" "WARN"
            }
        } catch {
            Write-Log "${Context}pending sidecar rollback failed for $path : $_" "ERROR"
        }
    }
}

function Complete-PendingPublishedSidecarFiles {
    param([array] $PublishedSidecars = @())

    foreach ($entry in @($PublishedSidecars)) {
        if ($null -eq $entry) { continue }
        $backupPath = [string](Get-PendingObjectProperty -Object $entry -Name 'backup_path')
        if (-not [string]::IsNullOrWhiteSpace($backupPath)) {
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Publish-PendingSidecarFiles {
    param(
        $Manifest,
        [string] $PublishTransactionId = ''
    )

    $records = [System.Collections.Generic.List[object]]::new()
    $failures = [System.Collections.Generic.List[object]]::new()
    $published = [System.Collections.Generic.List[object]]::new()
    $pendingKeys = @{}

    foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
        $localFile = [string](Get-PendingObjectProperty -Object $sidecar -Name 'local_file')
        $serverOut = [string](Get-PendingObjectProperty -Object $sidecar -Name 'server_out')
        $record = Get-PendingObjectProperty -Object $sidecar -Name 'tx3g_record'
        $preserveExisting = [bool](Get-PendingObjectProperty -Object $sidecar -Name 'preserve_existing')
        if (-not [string]::IsNullOrWhiteSpace($serverOut)) {
            $pendingKeys[$serverOut.ToLowerInvariant()] = $true
        }

        if ([string]::IsNullOrWhiteSpace($localFile) -or [string]::IsNullOrWhiteSpace($serverOut)) {
            $failures.Add((New-PendingTx3gPublishFailure -Record $record -Reason 'pending sidecar manifest is missing local_file or server_out'))
            continue
        }

        if ($preserveExisting -and (Test-Path -LiteralPath $serverOut -ErrorAction SilentlyContinue)) {
            $existingValidation = Test-SrtFileUsable -Path $serverOut
            if ($existingValidation.Ok) {
                $records.Add((Copy-PendingTx3gRecordWithStatus -Record $record -Status 'existing' -Path $serverOut -CueCount $existingValidation.CueCount -PreservedExisting:$true))
                $published.Add([ordered]@{ path = $serverOut; status = 'existing'; existed_before = $true; backup_path = '' }) | Out-Null
                continue
            }
        }

        $backupPath = ''
        $existedBefore = Test-Path -LiteralPath $serverOut -PathType Leaf -ErrorAction SilentlyContinue
        if ($existedBefore) {
            if ([string]::IsNullOrWhiteSpace($PublishTransactionId)) { $PublishTransactionId = New-PublishTransactionId }
            $backupPath = New-PendingSidecarBackupPath -SidecarPath $serverOut -PublishTransactionId $PublishTransactionId
            try {
                Copy-Item -LiteralPath $serverOut -Destination $backupPath -Force -ErrorAction Stop
            } catch {
                $failures.Add((New-PendingTx3gPublishFailure -Record $record -Reason "pending sidecar backup failed before publish: $($_.Exception.Message)"))
                continue
            }
        }

        $copy = Copy-SrtAtomic -SourcePath $localFile -DestinationPath $serverOut
        if (-not $copy.Ok) {
            if (-not [string]::IsNullOrWhiteSpace($backupPath) -and (Test-Path -LiteralPath $backupPath -PathType Leaf -ErrorAction SilentlyContinue)) {
                try {
                    Restore-PendingSidecarBackupIntoPlace -BackupPath $backupPath -DestinationPath $serverOut -Context 'Pending: '
                    Write-Log "Pending: restored existing sidecar after failed pending sidecar publish: $serverOut" "WARN"
                } catch {
                    Write-Log "Pending: sidecar backup restore failed after pending sidecar publish failure for $serverOut : $_" "ERROR"
                }
            } elseif (-not $existedBefore -and (Test-Path -LiteralPath $serverOut -PathType Leaf -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $serverOut -Force -ErrorAction SilentlyContinue
            }
            $failures.Add((New-PendingTx3gPublishFailure -Record $record -Reason $copy.Reason))
            continue
        }
        $published.Add([ordered]@{ path = $serverOut; status = 'written'; existed_before = [bool]$existedBefore; backup_path = $backupPath }) | Out-Null
        $records.Add((Copy-PendingTx3gRecordWithStatus -Record $record -Status 'written' -Path $serverOut -CueCount $copy.CueCount))
    }

    foreach ($record in @($Manifest.tx3g_srt_tracks)) {
        if ($null -eq $record) { continue }
        $path = [string]$record.path
        $status = [string]$record.status
        if ($status -eq 'pending' -and -not [string]::IsNullOrWhiteSpace($path) -and $pendingKeys.ContainsKey($path.ToLowerInvariant())) {
            continue
        }
        $records.Add($record)
    }
    foreach ($failure in @($Manifest.tx3g_srt_failures)) {
        if ($null -ne $failure) { $failures.Add($failure) }
    }

    return @{
        Tracks    = @($records)
        Failures  = @($failures)
        Published = @($published)
    }
}

# Decide whether an existing file on the server is a VALID published copy
# (i.e. matches the parked local file's intended publish). Used to detect
# "someone or something else already pushed this" before we overwrite.
#
# A server copy is accepted only if ALL of the following:
#   - sidecar exists and has a fresh enough pipeline_version
#   - file size matches manifest.output_size (or local file's size)
#   - if manifest has a publish_transaction_id, sidecar's matches
#   - source identity proven via v2 OR v1 OR (path + size) match
#
# Returns $false on any uncertainty. The conservative bias is intentional:
# false-negative means we re-push; false-positive could discard a parked encode.
function Test-PendingPublishedServerCopy {
    param(
        $Manifest,
        [string]$LocalPath,
        [string]$ServerPath
    )

    if ([string]::IsNullOrWhiteSpace($ServerPath) -or -not (Test-Path -LiteralPath $ServerPath -ErrorAction SilentlyContinue)) {
        return $false
    }
    $sidecarPath = Get-SidecarPath $ServerPath
    if (-not (Test-Path -LiteralPath $sidecarPath -ErrorAction SilentlyContinue)) {
        Write-Log "Pending: existing server file has no sidecar: $ServerPath" "WARN"
        return $false
    }

    try {
        $sidecar = Get-Content -LiteralPath $sidecarPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $sidecarVersion = [string]$sidecar.pipeline_version
        if ([string]::IsNullOrWhiteSpace($sidecarVersion) -or (Compare-PipelineVersion $sidecarVersion $script:MinPipelineVersion)) {
            Write-Log "Pending: existing server sidecar is stale or missing version: $sidecarPath" "WARN"
            return $false
        }

        $expectedSize = $null
        if ($Manifest -and $null -ne $Manifest.output_size) {
            try { $expectedSize = [long]$Manifest.output_size } catch {}
        }
        if ($null -eq $expectedSize) { $expectedSize = Get-FileLengthOrNull $LocalPath }
        $serverSize = Get-FileLengthOrNull $ServerPath
        if ($null -eq $expectedSize -or $null -eq $serverSize) {
            Write-Log "Pending: cannot validate existing server size for $ServerPath" "WARN"
            return $false
        }
        if ($expectedSize -ne $serverSize) {
            Write-Log "Pending: existing server size mismatch ($serverSize vs expected $expectedSize): $ServerPath" "WARN"
            return $false
        }

        $manifestTxn = if ($Manifest) { [string]$Manifest.publish_transaction_id } else { "" }
        if (-not [string]::IsNullOrWhiteSpace($manifestTxn) -and $manifestTxn -ne [string]$sidecar.publish_transaction_id) {
            Write-Log "Pending: existing server transaction mismatch for $ServerPath" "WARN"
            return $false
        }

        $provedSource = $false
        $manifestSourceV2 = if ($Manifest) { [string]$Manifest.source_identity_v2 } else { "" }
        $sidecarSourceV2 = [string]$sidecar.source_identity_v2
        if (-not [string]::IsNullOrWhiteSpace($manifestSourceV2)) {
            if ([string]::IsNullOrWhiteSpace($sidecarSourceV2) -or $manifestSourceV2 -ne $sidecarSourceV2) {
                Write-Log "Pending: existing server source identity v2 mismatch for $ServerPath" "WARN"
                return $false
            }
            $provedSource = $true
        }

        $manifestSource = if ($Manifest) { [string]$Manifest.source_identity } else { "" }
        $sidecarSource = [string]$sidecar.source_identity
        if (-not $provedSource -and -not [string]::IsNullOrWhiteSpace($manifestSource)) {
            if ([string]::IsNullOrWhiteSpace($sidecarSource) -or $manifestSource -ne $sidecarSource) {
                Write-Log "Pending: existing server source identity mismatch for $ServerPath" "WARN"
                return $false
            }
            $provedSource = $true
        }

        if (-not $provedSource) {
            $manifestSourcePath = if ($Manifest) { [string]$Manifest.source_path } else { "" }
            $sidecarSourcePath = [string]$sidecar.source_path
            $manifestSourceSize = $null
            $sidecarSourceSize = $null
            try { if ($Manifest -and $null -ne $Manifest.source_size) { $manifestSourceSize = [long]$Manifest.source_size } } catch {}
            try { if ($null -ne $sidecar.source_size) { $sidecarSourceSize = [long]$sidecar.source_size } } catch {}
            if (-not [string]::IsNullOrWhiteSpace($manifestSourcePath) -and
                -not [string]::IsNullOrWhiteSpace($sidecarSourcePath) -and
                $manifestSourcePath -eq $sidecarSourcePath -and
                $null -ne $manifestSourceSize -and
                $null -ne $sidecarSourceSize -and
                $manifestSourceSize -eq $sidecarSourceSize) {
                $provedSource = $true
            }
        }

        if (-not $provedSource -and [string]::IsNullOrWhiteSpace($manifestTxn)) {
            Write-Log "Pending: legacy existing server copy lacks enough source proof; keeping parked local file" "WARN"
            return $false
        }
        if (-not $provedSource -and -not [string]::IsNullOrWhiteSpace($manifestTxn)) {
            Write-Log "Pending: transaction matched but source proof is missing for $ServerPath" "WARN"
            return $false
        }
        foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
            $sidecarServer = [string](Get-PendingObjectProperty -Object $sidecar -Name 'server_out')
            if ([string]::IsNullOrWhiteSpace($sidecarServer)) { continue }
            $sidecarValidation = Test-SrtFileUsable -Path $sidecarServer
            if (-not $sidecarValidation.Ok) {
                Write-Log "Pending: existing server copy is missing usable pending sidecar $sidecarServer : $($sidecarValidation.Reason)" "WARN"
                return $false
            }
        }
        foreach ($record in @($Manifest.tx3g_srt_tracks)) {
            $status = [string](Get-PendingObjectProperty -Object $record -Name 'status')
            $recordPath = [string](Get-PendingObjectProperty -Object $record -Name 'path')
            if ($status -eq 'pending' -or [string]::IsNullOrWhiteSpace($recordPath)) { continue }
            $recordValidation = Test-SrtFileUsable -Path $recordPath
            if (-not $recordValidation.Ok) {
                Write-Log "Pending: existing server copy is missing usable tx3g SRT $recordPath : $($recordValidation.Reason)" "WARN"
                return $false
            }
        }
        return $true
    } catch {
        Write-Log "Pending: existing server sidecar validation failed for $ServerPath : $_" "WARN"
        return $false
    }
}
