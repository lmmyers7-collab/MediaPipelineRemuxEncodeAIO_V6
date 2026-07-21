# Publish-sidecar helpers shared by publish orchestration.

function Get-PublishedSidecarProperty {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name
    )
    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) { return $Object[$Name] }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $null
}

function New-PublishedSidecarBackupPath {
    param([Parameter(Mandatory)] [string] $SidecarPath)

    $dir = Split-Path -Parent $SidecarPath
    if ([string]::IsNullOrWhiteSpace($dir)) { $dir = (Get-Location).Path }
    $leaf = Split-Path -Leaf $SidecarPath
    return (Join-Path $dir (".{0}.mp-published-sidecar-backup.{1}" -f $leaf, [guid]::NewGuid().ToString('N')))
}

function Restore-PublishedSidecarBackupIntoPlace {
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
            Write-Log "${Context}published sidecar restore replace failed for $DestinationPath (will use overwrite move): $($_.Exception.Message)" "WARN"
            [System.IO.File]::Move($BackupPath, $DestinationPath, $true)
            return
        }
    }

    [System.IO.File]::Move($BackupPath, $DestinationPath, $true)
}

function Undo-PublishedSidecarFiles {
    param(
        [array] $PublishedSidecars = @(),
        [string] $Context = ''
    )

    foreach ($entry in @($PublishedSidecars)) {
        if ($null -eq $entry) { continue }
        $status = [string](Get-PublishedSidecarProperty -Object $entry -Name 'status')
        if ($status -ne 'written') { continue }
        $path = [string](Get-PublishedSidecarProperty -Object $entry -Name 'path')
        $backupPath = [string](Get-PublishedSidecarProperty -Object $entry -Name 'backup_path')
        $existedBefore = [bool](Get-PublishedSidecarProperty -Object $entry -Name 'existed_before')
        if ([string]::IsNullOrWhiteSpace($path)) { continue }

        try {
            if (-not [string]::IsNullOrWhiteSpace($backupPath) -and (Test-Path -LiteralPath $backupPath -PathType Leaf -ErrorAction SilentlyContinue)) {
                Restore-PublishedSidecarBackupIntoPlace -BackupPath $backupPath -DestinationPath $path -Context $Context
                Write-Log "${Context}published sidecar restored after failed media reveal: $path" "WARN"
                continue
            }
            if (-not $existedBefore -and (Test-Path -LiteralPath $path -PathType Leaf -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $path -Force -ErrorAction Stop
                Write-Log "${Context}published sidecar removed after failed media reveal: $path" "WARN"
            }
        } catch {
            Write-Log "${Context}published sidecar rollback failed for $path : $_" "ERROR"
        }
    }
}

function Complete-PublishedSidecarFiles {
    param([array] $PublishedSidecars = @())

    foreach ($entry in @($PublishedSidecars)) {
        if ($null -eq $entry) { continue }
        $backupPath = [string](Get-PublishedSidecarProperty -Object $entry -Name 'backup_path')
        if (-not [string]::IsNullOrWhiteSpace($backupPath)) {
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Publish-Tx3gSrtSidecarsFromPlan {
    param(
        [Parameter(Mandatory)] $Plan,
        [string] $Context = ''
    )
    $records = [System.Collections.Generic.List[object]]::new()
    $failures = [System.Collections.Generic.List[object]]::new()
    $published = [System.Collections.Generic.List[object]]::new()
    foreach ($failure in @($Plan.Failures)) {
        if ($failure) { $failures.Add($failure) }
    }
    foreach ($record in @($Plan.Tracks)) {
        if ($record -and [string]$record.status -eq 'existing') { $records.Add($record) }
    }
    foreach ($sidecar in @($Plan.SidecarFiles)) {
        if (-not $sidecar) { continue }
        $sourceSrt = [string]$sidecar.LocalPath
        $destination = [string]$sidecar.DestinationPath
        $record = $sidecar.Record
        $streamIndex = if ($record -and $record.PSObject.Properties['stream_index']) { [int]$record.stream_index } else { -1 }
        $trackId = [string](Get-PublishedSidecarProperty -Object $record -Name 'track_id')
        $sourceSubtitleKind = [string](Get-PublishedSidecarProperty -Object $record -Name 'source_subtitle_kind')
        if ([string]::IsNullOrWhiteSpace($sourceSubtitleKind)) { $sourceSubtitleKind = 'subtitle' }
        $sourceKind = [string](Get-PublishedSidecarProperty -Object $record -Name 'source_kind')
        $outputCodec = [string](Get-PublishedSidecarProperty -Object $record -Name 'output_codec')
        $outputLocation = [string](Get-PublishedSidecarProperty -Object $record -Name 'output_location')
        if (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue) {
            Write-SubtitleTrackProgress -Kind $sourceSubtitleKind -TrackId $trackId -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'Writing SRT sidecar' -StepIndex 4 -StepTotal 4 -Detail (Split-Path -Leaf $destination)
        }
        $backupPath = ''
        $existedBefore = Test-Path -LiteralPath $destination -PathType Leaf -ErrorAction SilentlyContinue
        if ($existedBefore) {
            $backupPath = New-PublishedSidecarBackupPath -SidecarPath $destination
            try {
                Copy-Item -LiteralPath $destination -Destination $backupPath -Force -ErrorAction Stop
            } catch {
                $entry = if ($record -and $record.PSObject.Properties['stream_index']) {
                    @{ TrackId = $trackId; Stream = @{ index = $record.stream_index }; Lang = $record.language; Title = $record.title }
                } else {
                    @{ TrackId = $trackId; Stream = @{ index = -1 }; Lang = ''; Title = '' }
                }
                $failure = New-Tx3gFailureRecord -Entry $entry -Reason "sidecar backup failed before publish: $($_.Exception.Message)" -ErrorCode 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED'
                $failures.Add($failure)
                Write-Log "${Context}TX3G->SRT: sidecar backup failed for $destination : $($_.Exception.Message)" "WARN"
                continue
            }
        }
        $copy = Copy-SrtAtomic -SourcePath $sourceSrt -DestinationPath $destination
        if (-not $copy.Ok) {
            if (-not [string]::IsNullOrWhiteSpace($backupPath) -and (Test-Path -LiteralPath $backupPath -PathType Leaf -ErrorAction SilentlyContinue)) {
                try {
                    Restore-PublishedSidecarBackupIntoPlace -BackupPath $backupPath -DestinationPath $destination -Context $Context
                } catch {
                    Write-Log "${Context}TX3G->SRT: sidecar backup restore failed after publish failure for $destination : $_" "ERROR"
                }
            } elseif (-not $existedBefore -and (Test-Path -LiteralPath $destination -PathType Leaf -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
            }
            $entry = if ($record -and $record.PSObject.Properties['stream_index']) {
                @{ TrackId = $trackId; Stream = @{ index = $record.stream_index }; Lang = $record.language; Title = $record.title }
            } else {
                @{ TrackId = $trackId; Stream = @{ index = -1 }; Lang = ''; Title = '' }
            }
            $failure = New-Tx3gFailureRecord -Entry $entry -Reason $copy.Reason -ErrorCode $copy.ErrorCode
            $failures.Add($failure)
            if (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue) {
                Write-SubtitleTrackProgress -Kind $sourceSubtitleKind -TrackId $trackId -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'SRT sidecar write failed' -StepIndex 4 -StepTotal 4 -Detail $copy.Reason -Failed
            }
            Write-Log "${Context}TX3G->SRT: sidecar publish failed for $destination : $($copy.Reason)" "WARN"
            continue
        }
        $published.Add([ordered]@{
            path = $destination
            status = 'written'
            existed_before = [bool]$existedBefore
            backup_path = $backupPath
            kind = 'tx3g_srt'
            track_id = $trackId
            source_kind = $sourceKind
            source_subtitle_kind = $sourceSubtitleKind
            output_codec = $outputCodec
            output_location = $outputLocation
            output_path = $destination
        }) | Out-Null
        if ($record) {
            if ($record.PSObject.Properties['status']) {
                $record.status = 'written'
            } else {
                Add-Member -InputObject $record -NotePropertyName 'status' -NotePropertyValue 'written' -Force
            }
            if ($record.PSObject.Properties['cue_count']) {
                $record.cue_count = $copy.CueCount
            } else {
                Add-Member -InputObject $record -NotePropertyName 'cue_count' -NotePropertyValue $copy.CueCount -Force
            }
            $records.Add($record)
        }
        if (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue) {
            Write-SubtitleTrackProgress -Kind $sourceSubtitleKind -TrackId $trackId -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'SRT sidecar written' -StepIndex 4 -StepTotal 4 -Detail (Split-Path -Leaf $destination) -CueCount $copy.CueCount -OutputCodec $outputCodec -OutputLocation $outputLocation -OutputPath $destination -Completed
        }
        Write-Log "${Context}TX3G->SRT: sidecar written $(Split-Path -Leaf $destination)"
    }
    return @{
        Tracks   = @($records)
        Failures = @($failures)
        Published = @($published)
    }
}
