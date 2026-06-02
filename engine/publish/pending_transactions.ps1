# ==============================================================================
# Modules\PendingTransactions.ps1
# ==============================================================================
# Transaction helpers for PendingServerPush parking and draining.
#
# Public pending APIs stay in PendingPush.ps1. This module owns the durable
# park transaction mechanics so the wrapper can handle operator-facing logging,
# index refresh, and event emission without also owning manifest/move cleanup.
# ==============================================================================

function New-PublishTransactionId {
    return [guid]::NewGuid().ToString("N")
}

# Defensive Get-Item.Length wrapper - returns $null on any failure rather
# than throwing. Used throughout pending-publish checks where "couldn't
# determine size" must not abort a retry path.
function Get-FileLengthOrNull {
    param([string]$Path)
    try {
        if ($Path -and (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
            return [long](Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        }
    } catch {}
    return $null
}

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

function Repair-PendingSidecarArtifacts {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        $Manifest
    )

    foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
        $localFile = [string](Get-PendingObjectProperty -Object $sidecar -Name 'local_file')
        $originalFile = [string](Get-PendingObjectProperty -Object $sidecar -Name 'original_local_file')
        if ([string]::IsNullOrWhiteSpace($localFile) -or
            (Test-Path -LiteralPath $localFile -ErrorAction SilentlyContinue)) {
            continue
        }
        if ([string]::IsNullOrWhiteSpace($originalFile) -or
            -not (Test-Path -LiteralPath $originalFile -ErrorAction SilentlyContinue)) {
            continue
        }

        try {
            $localDir = Split-Path $localFile -Parent
            if ($localDir -and -not (Test-Path -LiteralPath $localDir)) {
                [System.IO.Directory]::CreateDirectory($localDir) | Out-Null
            }
            [System.IO.File]::Move($originalFile, $localFile, $true)
            Write-Log "Pending publish index: recovered parked sidecar from pending_move manifest: $($ManifestFile.Name)" "WARN"
        } catch {
            Write-Log "Pending publish index: failed to recover sidecar for $($ManifestFile.Name) : $_" "WARN"
        }
    }
    return $Manifest
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
            if (-not [string]::IsNullOrWhiteSpace($backupPath)) {
                Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
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

function New-PendingParkSidecarEntries {
    param(
        [array] $SidecarFiles = @(),
        [Parameter(Mandatory)] [string] $LocalPendingPushPath,
        [Parameter(Mandatory)] [string] $Timestamp,
        [Parameter(Mandatory)] [string] $TransactionFileId
    )

    $entries = [System.Collections.Generic.List[object]]::new()
    $sidecarOrdinal = 0
    foreach ($sidecar in @($SidecarFiles)) {
        $sidecarLocal = [string](Get-PendingObjectProperty -Object $sidecar -Name 'LocalPath')
        $sidecarServer = [string](Get-PendingObjectProperty -Object $sidecar -Name 'DestinationPath')
        if ([string]::IsNullOrWhiteSpace($sidecarServer)) {
            $sidecarServer = [string](Get-PendingObjectProperty -Object $sidecar -Name 'ServerOut')
        }
        if ([string]::IsNullOrWhiteSpace($sidecarLocal) -or [string]::IsNullOrWhiteSpace($sidecarServer)) {
            continue
        }
        if (-not (Test-Path -LiteralPath $sidecarLocal -ErrorAction SilentlyContinue)) {
            throw "pending sidecar source is missing: $sidecarLocal"
        }
        $sidecarLeaf = Split-Path $sidecarServer -Leaf
        if ([string]::IsNullOrWhiteSpace($sidecarLeaf)) { $sidecarLeaf = "sidecar$sidecarOrdinal.srt" }
        $sidecarParked = Join-Path $LocalPendingPushPath "${Timestamp}__${TransactionFileId}__sidecar${sidecarOrdinal}__${sidecarLeaf}"
        $entries.Add([ordered]@{
            kind                = if (Get-PendingObjectProperty -Object $sidecar -Name 'Kind') { [string](Get-PendingObjectProperty -Object $sidecar -Name 'Kind') } else { 'sidecar' }
            local_file          = $sidecarParked
            original_local_file = $sidecarLocal
            parked_file         = $sidecarParked
            server_out          = $sidecarServer
            output_size         = Get-FileLengthOrNull $sidecarLocal
            preserve_existing   = [bool](Get-PendingObjectProperty -Object $sidecar -Name 'PreserveExisting')
            tx3g_record         = Get-PendingObjectProperty -Object $sidecar -Name 'Record'
        })
        $sidecarOrdinal++
    }
    return $entries
}

function New-PendingParkManifest {
    param(
        [Parameter(Mandatory)] [string] $LocalOut,
        [Parameter(Mandatory)] [string] $ParkedPath,
        [Parameter(Mandatory)] [string] $ServerOut,
        [Parameter(Mandatory)] [string] $Route,
        [string] $RouteReasonCode = '',
        [string] $RouteReason = '',
        [string] $SourceIdentity,
        [string] $SourceIdentityV2,
        [string] $SourcePath,
        [object] $SourceSize,
        [string] $SourceMTimeUtc,
        [Parameter(Mandatory)] [string] $PublishTransactionId,
        [string] $PublishMode = 'retry',
        [array] $SidecarManifestEntries = @(),
        [array] $Tx3gSrtTracks = @(),
        [array] $Tx3gSrtFailures = @(),
        [array] $BdpgsSrtFailures = @(),
        [array] $VobSubSrtFailures = @(),
        [array] $Tx3gEmbeddedSrtTracks = @(),
        [array] $BdpgsEmbeddedSrtTracks = @(),
        [array] $VobSubEmbeddedSrtTracks = @(),
        [bool] $Tx3gSrtConversionEnabled = $false,
        [bool] $Tx3gExternalSrtSidecarsEnabled = $false,
        [bool] $DropTx3gAfterConversion = $false,
        [bool] $BdpgsSrtConversionEnabled = $false,
        [bool] $DropBdpgsAfterConversion = $false,
        [bool] $VobSubSrtConversionEnabled = $false,
        [bool] $DropVobSubAfterConversion = $false,
        [object] $FolderPolicyMetadata = $null,
        [object] $RoutePlanMetadata = $null,
        # S9 — carry MediaType through park so the deferred-publish
        # sidecar can stamp the same media_type field that immediate
        # publish does.  Without this, movies parked-and-drained come
        # back blank in the Completed tab on the desktop UI.  Lower-cased
        # 'movie' / 'tv' to match Complete-PipelineOutputPublish.
        [string] $MediaType = ''
    )

    $manifest = [ordered]@{
        schema_version         = 'pending_push_manifest.v1'
        parked_at              = (Get-Date -Format 'o')
        product_version         = if ($script:ProductVersion) { [string]$script:ProductVersion } else { '' }
        pipeline_version       = $script:PipelineVersion
        publish_transaction_id = $PublishTransactionId
        manifest_state         = 'pending_move'
        local_file             = $ParkedPath
        original_local_file    = $LocalOut
        parked_file            = $ParkedPath
        server_out             = $ServerOut
        route                  = $Route
        route_reason_code      = $RouteReasonCode
        route_reason           = $RouteReason
        media_type             = if ([string]::IsNullOrWhiteSpace($MediaType)) { '' } else { $MediaType.Trim().ToLowerInvariant() }
        source_identity        = $SourceIdentity
        source_identity_v2     = $SourceIdentityV2
        source_identity_v2_algorithm = $script:SourceIdentityV2Algorithm
        source_path            = $SourcePath
        source_size            = $SourceSize
        source_mtime_utc       = $SourceMTimeUtc
        output_size            = Get-FileLengthOrNull $LocalOut
        publish_mode           = $PublishMode
        sidecar_files          = @($SidecarManifestEntries)
        tx3g_srt_tracks        = @($Tx3gSrtTracks)
        tx3g_srt_failures      = @($Tx3gSrtFailures)
        bdpgs_srt_failures     = @($BdpgsSrtFailures)
        vobsub_srt_failures    = @($VobSubSrtFailures)
        tx3g_embedded_srt_tracks = @($Tx3gEmbeddedSrtTracks)
        bdpgs_embedded_srt_tracks = @($BdpgsEmbeddedSrtTracks)
        vobsub_embedded_srt_tracks = @($VobSubEmbeddedSrtTracks)
        tx3g_srt_conversion_enabled = [bool]$Tx3gSrtConversionEnabled
        tx3g_external_srt_sidecars_enabled = [bool]$Tx3gExternalSrtSidecarsEnabled
        drop_tx3g_after_conversion = [bool]$DropTx3gAfterConversion
        bdpgs_srt_conversion_enabled = [bool]$BdpgsSrtConversionEnabled
        drop_bdpgs_after_conversion = [bool]$DropBdpgsAfterConversion
        vobsub_srt_conversion_enabled = [bool]$VobSubSrtConversionEnabled
        drop_vobsub_after_conversion = [bool]$DropVobSubAfterConversion
    }
    if ($FolderPolicyMetadata) {
        $manifest['folder_policy'] = $FolderPolicyMetadata
    }
    if ($RoutePlanMetadata) {
        $manifest['route_plan'] = $RoutePlanMetadata
    }
    return $manifest
}

function Invoke-PendingParkTransaction {
    param(
        [Parameter(Mandatory)] [string] $LocalOut,
        [Parameter(Mandatory)] [string] $ServerOut,
        [Parameter(Mandatory)] [string] $Route,
        [string] $RouteReasonCode = '',
        [string] $RouteReason = '',
        [string] $SourceIdentity,
        [string] $SourceIdentityV2,
        [string] $SourcePath,
        [object] $SourceSize,
        [string] $SourceMTimeUtc,
        [string] $PublishTransactionId,
        [string] $PublishMode = 'retry',
        [array] $SidecarFiles = @(),
        [array] $Tx3gSrtTracks = @(),
        [array] $Tx3gSrtFailures = @(),
        [array] $BdpgsSrtFailures = @(),
        [array] $VobSubSrtFailures = @(),
        [array] $Tx3gEmbeddedSrtTracks = @(),
        [array] $BdpgsEmbeddedSrtTracks = @(),
        [array] $VobSubEmbeddedSrtTracks = @(),
        [bool] $Tx3gSrtConversionEnabled = $false,
        [bool] $Tx3gExternalSrtSidecarsEnabled = $false,
        [bool] $DropTx3gAfterConversion = $false,
        [bool] $BdpgsSrtConversionEnabled = $false,
        [bool] $DropBdpgsAfterConversion = $false,
        [bool] $VobSubSrtConversionEnabled = $false,
        [bool] $DropVobSubAfterConversion = $false,
        [object] $FolderPolicyMetadata = $null,
        [object] $RoutePlanMetadata = $null,
        [string] $MediaType = ''
    )

    $parked = ''
    $manifestPath = ''
    $sidecarManifestEntries = @()
    $leaf = Split-Path $LocalOut -Leaf
    try {
        if (-not (Test-Path -LiteralPath $LocalOut)) {
            return [pscustomobject]@{
                Ok = $false; Error = "local output vanished at $LocalOut"; LocalFile = ''; OriginalLocalFile = $LocalOut
                ServerOut = $ServerOut; ManifestPath = ''; PublishTransactionId = $PublishTransactionId; SidecarEntries = @()
                OutputSize = $null; Leaf = $leaf; MediaMoved = $false
            }
        }
        if (-not (Test-Path -LiteralPath $LocalPendingPush)) {
            [System.IO.Directory]::CreateDirectory($LocalPendingPush) | Out-Null
        }
        $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
        $id = [guid]::NewGuid().ToString("N")
        $parked = Join-Path $LocalPendingPush "${ts}__${id}__${leaf}"
        if ([string]::IsNullOrWhiteSpace($PublishTransactionId)) { $PublishTransactionId = New-PublishTransactionId }
        $sidecarManifestEntries = @(New-PendingParkSidecarEntries -SidecarFiles $SidecarFiles -LocalPendingPushPath $LocalPendingPush -Timestamp $ts -TransactionFileId $id)

        foreach ($sidecar in @($sidecarManifestEntries)) {
            $sidecarOriginal = [string]$sidecar.original_local_file
            $sidecarParked = [string]$sidecar.local_file
            $sidecarDir = Split-Path $sidecarParked -Parent
            if ($sidecarDir -and -not (Test-Path -LiteralPath $sidecarDir)) {
                [System.IO.Directory]::CreateDirectory($sidecarDir) | Out-Null
            }
            $sidecarCopy = Copy-SrtAtomic -SourcePath $sidecarOriginal -DestinationPath $sidecarParked
            if (-not $sidecarCopy.Ok) {
                throw "pending sidecar park failed for $sidecarOriginal : $($sidecarCopy.Reason)"
            }
        }

        $manifest = New-PendingParkManifest `
            -LocalOut $LocalOut `
            -ParkedPath $parked `
            -ServerOut $ServerOut `
            -Route $Route `
            -RouteReasonCode $RouteReasonCode `
            -RouteReason $RouteReason `
            -SourceIdentity $SourceIdentity `
            -SourceIdentityV2 $SourceIdentityV2 `
            -SourcePath $SourcePath `
            -SourceSize $SourceSize `
            -SourceMTimeUtc $SourceMTimeUtc `
            -PublishTransactionId $PublishTransactionId `
            -PublishMode $PublishMode `
            -SidecarManifestEntries @($sidecarManifestEntries) `
            -Tx3gSrtTracks @($Tx3gSrtTracks) `
            -Tx3gSrtFailures @($Tx3gSrtFailures) `
            -BdpgsSrtFailures @($BdpgsSrtFailures) `
            -VobSubSrtFailures @($VobSubSrtFailures) `
            -Tx3gEmbeddedSrtTracks @($Tx3gEmbeddedSrtTracks) `
            -BdpgsEmbeddedSrtTracks @($BdpgsEmbeddedSrtTracks) `
            -VobSubEmbeddedSrtTracks @($VobSubEmbeddedSrtTracks) `
            -Tx3gSrtConversionEnabled:$Tx3gSrtConversionEnabled `
            -Tx3gExternalSrtSidecarsEnabled:$Tx3gExternalSrtSidecarsEnabled `
            -DropTx3gAfterConversion:$DropTx3gAfterConversion `
            -BdpgsSrtConversionEnabled:$BdpgsSrtConversionEnabled `
            -DropBdpgsAfterConversion:$DropBdpgsAfterConversion `
            -VobSubSrtConversionEnabled:$VobSubSrtConversionEnabled `
            -DropVobSubAfterConversion:$DropVobSubAfterConversion `
            -FolderPolicyMetadata $FolderPolicyMetadata `
            -RoutePlanMetadata $RoutePlanMetadata `
            -MediaType $MediaType

        $manifestPath = "$parked.manifest.json"
        Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null
        $roundTrip = Read-PendingManifestFile -Path $manifestPath
        if ([string]$roundTrip.local_file -ne $parked -or [string]$roundTrip.server_out -ne $ServerOut -or [string]$roundTrip.manifest_state -ne 'pending_move') {
            throw "pending manifest validation failed before park"
        }

        [System.IO.File]::Move($LocalOut, $parked, $true)
        $stateUpdateOk = $true
        try {
            $manifest['manifest_state'] = 'parked'
            $manifest['parked_at'] = (Get-Date -Format 'o')
            Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null
        } catch {
            $stateUpdateOk = $false
            Write-Log "Park: manifest state update failed after moving output; pending intent remains retryable: $manifestPath : $_" "WARN"
        }

        return [pscustomobject]@{
            Ok = $true; Error = ''; LocalFile = $parked; OriginalLocalFile = $LocalOut; ServerOut = $ServerOut
            ManifestPath = $manifestPath; PublishTransactionId = $PublishTransactionId; SidecarEntries = @($sidecarManifestEntries)
            OutputSize = Get-FileLengthOrNull $parked; Leaf = $leaf; MediaMoved = $true; ManifestStateUpdateOk = $stateUpdateOk
        }
    } catch {
        $mediaParked = $parked -and (Test-Path -LiteralPath $parked -ErrorAction SilentlyContinue)
        if (-not $mediaParked) {
            foreach ($sidecar in @($sidecarManifestEntries)) {
                $sidecarParked = [string]$sidecar.local_file
                if ($sidecarParked -and (Test-Path -LiteralPath $sidecarParked -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $sidecarParked -Force -ErrorAction SilentlyContinue
                }
            }
            if ($manifestPath -and (Test-Path -LiteralPath $manifestPath -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $manifestPath -Force -ErrorAction SilentlyContinue
            }
        }
        return [pscustomobject]@{
            Ok = $false; Error = [string]$_; LocalFile = $parked; OriginalLocalFile = $LocalOut; ServerOut = $ServerOut
            ManifestPath = $manifestPath; PublishTransactionId = $PublishTransactionId; SidecarEntries = @($sidecarManifestEntries)
            OutputSize = Get-FileLengthOrNull $LocalOut; Leaf = $leaf; MediaMoved = $mediaParked
        }
    }
}

# Crash recovery for manifest_state='pending_move'. If the manifest exists
# but local_file doesn't, recover sidecars first and then complete the media move
# from original_local_file when possible.
function Repair-PendingManifestState {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        [Parameter(Mandatory)] $Manifest
    )

    $Manifest = Repair-PendingSidecarArtifacts -ManifestFile $ManifestFile -Manifest $Manifest
    $localFile = [string]$Manifest.local_file
    if (-not [string]::IsNullOrWhiteSpace($localFile) -and (Test-Path -LiteralPath $localFile -ErrorAction SilentlyContinue)) {
        return $Manifest
    }

    $state = [string]$Manifest.manifest_state
    $original = [string]$Manifest.original_local_file
    if ($state -ne 'pending_move' -or [string]::IsNullOrWhiteSpace($original) -or
        [string]::IsNullOrWhiteSpace($localFile) -or -not (Test-Path -LiteralPath $original -ErrorAction SilentlyContinue)) {
        return $Manifest
    }

    try {
        $localDir = Split-Path $localFile -Parent
        if ($localDir -and -not (Test-Path -LiteralPath $localDir)) {
            [System.IO.Directory]::CreateDirectory($localDir) | Out-Null
        }
        [System.IO.File]::Move($original, $localFile, $true)
        $map = ConvertTo-PendingManifestMap $Manifest
        $map['manifest_state'] = 'parked_recovered'
        $map['recovered_at'] = (Get-Date -Format 'o')
        Write-PendingManifestFile -Path $ManifestFile.FullName -Manifest $map | Out-Null
        Write-Log "Pending publish index: recovered parked output from pending_move manifest: $($ManifestFile.Name)" "WARN"
        return (Read-PendingManifestFile -Path $ManifestFile.FullName)
    } catch {
        Write-Log "Pending publish index: failed to recover pending_move manifest $($ManifestFile.Name) : $_" "WARN"
        return $Manifest
    }
}

function New-PendingDrainSidecarExtra {
    param(
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] [string] $ServerPath,
        [Parameter(Mandatory)] [string] $PublishMode,
        [Parameter(Mandatory)] [string] $PublishTransactionId,
        $OutputSize
    )

    # S9 — propagate media_type from the parked manifest to the
    # deferred-publish sidecar so movies parked-and-drained match
    # the immediate-publish path. Defaults to '' for legacy manifests
    # parked before this fix; the desktop's CompletedJobRecord falls
    # back to path heuristics in that case.
    $manifestMediaType = ''
    $mediaTypeProp = $Manifest.PSObject.Properties['media_type']
    if ($mediaTypeProp -and -not [string]::IsNullOrWhiteSpace([string]$mediaTypeProp.Value)) {
        $manifestMediaType = [string]$mediaTypeProp.Value
    }

    $sidecarExtra = [ordered]@{
        output_path            = $ServerPath
        media_type             = $manifestMediaType
        route_reason_code      = if ($Manifest.PSObject.Properties['route_reason_code']) { [string]$Manifest.route_reason_code } else { '' }
        route_reason           = if ($Manifest.PSObject.Properties['route_reason']) { [string]$Manifest.route_reason } else { '' }
        publish_state          = 'published'
        publish_mode           = $PublishMode
        publish_transaction_id = $PublishTransactionId
        source_identity        = [string]$Manifest.source_identity
        source_identity_v2     = [string]$Manifest.source_identity_v2
        source_identity_v2_algorithm = if ([string]::IsNullOrWhiteSpace([string]$Manifest.source_identity_v2_algorithm)) { $script:SourceIdentityV2Algorithm } else { [string]$Manifest.source_identity_v2_algorithm }
        source_path            = [string]$Manifest.source_path
        source_size            = $Manifest.source_size
        source_mtime_utc       = [string]$Manifest.source_mtime_utc
        output_size            = $OutputSize
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$Manifest.parked_at)) {
        $sidecarExtra['encoded_at'] = [string]$Manifest.parked_at
    }
    $bdpgsFailureProp = $Manifest.PSObject.Properties['bdpgs_srt_failures']
    if ($bdpgsFailureProp) {
        $sidecarExtra['bdpgs_srt_failures'] = @($bdpgsFailureProp.Value)
    }
    $vobSubFailureProp = $Manifest.PSObject.Properties['vobsub_srt_failures']
    if ($vobSubFailureProp) {
        $sidecarExtra['vobsub_srt_failures'] = @($vobSubFailureProp.Value)
    }
    $embeddedTx3gProp = $Manifest.PSObject.Properties['tx3g_embedded_srt_tracks']
    if ($embeddedTx3gProp) {
        $sidecarExtra['tx3g_embedded_srt_tracks'] = @($embeddedTx3gProp.Value)
    }
    $embeddedBdpgsProp = $Manifest.PSObject.Properties['bdpgs_embedded_srt_tracks']
    if ($embeddedBdpgsProp) {
        $sidecarExtra['bdpgs_embedded_srt_tracks'] = @($embeddedBdpgsProp.Value)
    }
    $embeddedVobSubProp = $Manifest.PSObject.Properties['vobsub_embedded_srt_tracks']
    if ($embeddedVobSubProp) {
        $sidecarExtra['vobsub_embedded_srt_tracks'] = @($embeddedVobSubProp.Value)
    }
    foreach ($policyKey in @('tx3g_srt_conversion_enabled', 'tx3g_external_srt_sidecars_enabled', 'drop_tx3g_after_conversion', 'bdpgs_srt_conversion_enabled', 'drop_bdpgs_after_conversion', 'vobsub_srt_conversion_enabled', 'drop_vobsub_after_conversion')) {
        $policyProp = $Manifest.PSObject.Properties[$policyKey]
        if ($policyProp) {
            $sidecarExtra[$policyKey] = [bool]$policyProp.Value
        }
    }
    $folderPolicyProp = $Manifest.PSObject.Properties['folder_policy']
    if ($folderPolicyProp) {
        $sidecarExtra['folder_policy'] = $folderPolicyProp.Value
    }
    $routePlanProp = $Manifest.PSObject.Properties['route_plan']
    if ($routePlanProp) {
        if (Get-Command -Name Add-MediaRoutePlanMetadataToMap -ErrorAction SilentlyContinue) {
            Add-MediaRoutePlanMetadataToMap -Map $sidecarExtra -Metadata $routePlanProp.Value | Out-Null
        } else {
            $sidecarExtra['route_plan'] = $routePlanProp.Value
        }
    }
    return $sidecarExtra
}

function Remove-PendingDrainLocalArtifacts {
    param(
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] [string] $LocalPath,
        [Parameter(Mandatory)] [string] $ManifestPath
    )

    $artifactRoot = Split-Path -Parent $ManifestPath
    if ([string]::IsNullOrWhiteSpace($artifactRoot)) {
        Write-Log "Pending: refusing local cleanup because manifest root is empty: $ManifestPath" "ERROR"
        return
    }

    $removeIfSafe = {
        param([string]$Path, [string]$Label)
        if ([string]::IsNullOrWhiteSpace($Path)) { return }
        $boundary = Test-MediaPipelinePathBoundarySafe -Path $Path -Root $artifactRoot
        if (-not $boundary.Ok) {
            Write-Log "Pending: refusing cleanup for unsafe $Label path ($($boundary.ReasonCode)): $Path" "ERROR"
            return
        }
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }

    foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
        $sidecarLocal = [string](Get-PendingObjectProperty -Object $sidecar -Name 'local_file')
        if ($sidecarLocal) {
            & $removeIfSafe $sidecarLocal 'sidecar'
        }
    }
    & $removeIfSafe $LocalPath 'local media'
    & $removeIfSafe $ManifestPath 'manifest'
}

function Invoke-PendingDrainTransaction {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        [Parameter(Mandatory)] $Manifest
    )

    $local = [string]$Manifest.local_file
    $server = [string]$Manifest.server_out
    $route = [string]$Manifest.route
    $publishMode = if ([string]::IsNullOrWhiteSpace([string]$Manifest.publish_mode)) { 'retry' } else { [string]$Manifest.publish_mode }
    $manifestPath = $ManifestFile.FullName

    $result = [ordered]@{
        Status = 'failed'
        Recovered = $false
        LocalFile = $local
        ServerOut = $server
        Route = $route
        PublishMode = $publishMode
        SourcePath = [string]$Manifest.source_path
        ManifestPath = $manifestPath
        PublishTransactionId = [string]$Manifest.publish_transaction_id
        SidecarCount = 0
        Error = ''
    }

    if (-not (Test-Path -LiteralPath $local)) {
        $reason = "Pending parked local file is missing: $local"
        Write-Log "Pending: $reason; leaving manifest queued as missing_payload: $($ManifestFile.Name)" "ERROR"
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'missing_payload' -Reason $reason -Stage 'retry_pending_push'
        $result.Status = 'missing_payload'
        $result.Error = $reason
        return [pscustomobject]$result
    }

    if (Test-Path -LiteralPath $server) {
        if (Test-PendingPublishedServerCopy -Manifest $Manifest -LocalPath $local -ServerPath $server) {
            Write-Log "Pending: server already has a validated published copy for $server - discarding local parked copy"
            Remove-PendingDrainLocalArtifacts -Manifest $Manifest -LocalPath $local -ManifestPath $manifestPath
            $result.Status = 'already_published'
            return [pscustomobject]$result
        }
        Write-Log "Pending: server path exists but is not a validated publish; replacing via transactional copy" "WARN"
    }

    $srvDir = Split-Path $server -Parent
    if ($srvDir -and -not (Test-Path -LiteralPath $srvDir)) {
        try { [System.IO.Directory]::CreateDirectory($srvDir) | Out-Null } catch {}
    }
    $publishTxn = if ([string]::IsNullOrWhiteSpace([string]$Manifest.publish_transaction_id)) { New-PublishTransactionId } else { [string]$Manifest.publish_transaction_id }
    $result.PublishTransactionId = $publishTxn
    $serverPartial = New-PublishPartialMediaPath -ServerOut $server -PublishTransactionId $publishTxn
    Remove-PublishPartialMedia -Path $serverPartial

    Write-Log "Pending: retrying push $(Split-Path $local -Leaf) -> $server via publish partial"
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'copying' -Percent 0 -SaveNow
    if (-not (Copy-FileRobocopy $local $serverPartial)) {
        Remove-PublishPartialMedia -Path $serverPartial
        $copyReason = Get-PublishCopyFailureReason
        if ([string]::IsNullOrWhiteSpace($copyReason)) { $copyReason = 'Pending media partial copy failed' }
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_copy_failed' -Reason $copyReason -Stage 'retry_pending_push'
        Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: still cannot push $(Split-Path $local -Leaf) - will retry next round" "WARN"
        $result.Status = 'copy_failed'
        $result.Error = $copyReason
        return [pscustomobject]$result
    }

    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'copied_pending_reveal' -Percent 95 -SaveNow
    $serverSize = Get-FileLengthOrNull $serverPartial
    $sidecarExtra = New-PendingDrainSidecarExtra -Manifest $Manifest -ServerPath $server -PublishMode $publishMode -PublishTransactionId $publishTxn -OutputSize $serverSize
    $pendingSidecars = Publish-PendingSidecarFiles -Manifest $Manifest -PublishTransactionId $publishTxn
    if ($pendingSidecars.Failures -and @($pendingSidecars.Failures).Count -gt 0) {
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        $failureList = @($pendingSidecars.Failures | Where-Object { $null -ne $_ })
        $firstFailure = $failureList[0]
        $reason = if ($firstFailure -and $firstFailure.Reason) {
            "Pending tx3g SRT sidecar publish failed: $($firstFailure.Reason)"
        } else {
            'Pending tx3g SRT sidecar publish failed'
        }
        $failureSourcePath = if ([string]::IsNullOrWhiteSpace([string]$Manifest.source_path)) { $local } else { [string]$Manifest.source_path }
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_sidecar_file_failed' -Reason $reason -Stage 'pending-tx3g-sidecar' -Tx3gFailures $failureList
        Add-RoundFailureRecord -SourcePath $failureSourcePath -Stage 'pending-tx3g-sidecar' -Reason $reason -Classification 'transient' -ErrorCode 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED' -ArtifactPath $local -SuggestedAction 'Inspect the PendingServerPush manifest and parked tx3g SRT files. Restore missing sidecar files or rerun the source so tx3g extraction can recreate them.'
        Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'failed' -Percent $null -SaveNow
        Remove-PublishPartialMedia -Path $serverPartial
        Write-Log "Pending: partial media copy ok but tx3g sidecar publish failed - removed partial and left manifest/local copy for next retry" "WARN"
        $result.Status = 'sidecar_file_failed'
        $result.Error = $reason
        return [pscustomobject]$result
    }

    $sidecarExtra['tx3g_srt_tracks'] = @($pendingSidecars.Tracks)
    $sidecarExtra['tx3g_srt_failures'] = @($pendingSidecars.Failures)

    Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'writing' -Percent $null -SaveNow
    $publishSidecarBackup = Backup-PublishSidecarForReveal -OutputPath $server -PublishTransactionId $publishTxn -Context 'Pending: '
    if (-not (Write-Sidecar -OutputPath $server -Route $route -Extra $sidecarExtra -SkipCompletedManifest)) {
        Restore-PublishSidecarAfterRevealFailure -OutputPath $server -BackupPath $publishSidecarBackup -Context 'Pending: '
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Remove-PublishPartialMedia -Path $serverPartial
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_sidecar_failed' -Reason 'Pending sidecar write failed before final media reveal' -Stage 'sidecar'
        Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: partial media copy ok but sidecar failed - removed partial and left manifest/local copy for next retry" "WARN"
        $result.Status = 'sidecar_failed'
        $result.Error = 'Pending sidecar write failed before final media reveal'
        return [pscustomobject]$result
    }

    Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'complete' -Percent 100 -SaveNow
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'revealing' -Percent 99 -SaveNow
    if (-not (Complete-PublishMediaReveal -PartialPath $serverPartial -FinalPath $server -PublishTransactionId $publishTxn -Context 'Pending: ')) {
        Restore-PublishSidecarAfterRevealFailure -OutputPath $server -BackupPath $publishSidecarBackup -Context 'Pending: '
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Remove-PublishPartialMedia -Path $serverPartial
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_reveal_failed' -Reason 'Server partial copy and sidecar write succeeded but final media reveal failed' -Stage 'retry_pending_push'
        Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: reveal failed - restored/removed sidecar, removed partial, and left manifest/local copy for next retry" "WARN"
        $result.Status = 'reveal_failed'
        $result.Error = 'Server partial copy and sidecar write succeeded but final media reveal failed'
        return [pscustomobject]$result
    }

    Remove-PublishSidecarBackup -BackupPath $publishSidecarBackup
    Complete-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published)
    Add-CompletedJobsManifestEntryFromSidecar -OutputPath $server | Out-Null
    Write-OutputSummary -FilePath $server -Route $route
    Remove-PendingDrainLocalArtifacts -Manifest $Manifest -LocalPath $local -ManifestPath $manifestPath
    Write-Log "Pending: successfully pushed $(Split-Path $server -Leaf)"
    $result.Status = 'succeeded'
    $result.Recovered = $true
    $result.SidecarCount = @($pendingSidecars.Tracks).Count
    return [pscustomobject]$result
}
