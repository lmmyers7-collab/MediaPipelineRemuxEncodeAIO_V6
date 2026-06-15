# Publish partial-file and reveal helpers.
# Shared by immediate publish and pending-push retry flows.

function New-PublishPartialMediaPath {
    param(
        [Parameter(Mandatory)] [string] $ServerOut,
        [Parameter(Mandatory)] [string] $PublishTransactionId
    )
    $dir = Split-Path -Parent $ServerOut
    $leaf = Split-Path -Leaf $ServerOut
    return (Join-Path $dir (".{0}.mp-publish-partial.{1}" -f $leaf, $PublishTransactionId))
}

function Remove-PublishPartialMedia {
    param([string] $Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    try {
        if (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function New-PublishSidecarBackupResult {
    param(
        [bool] $HadExistingSidecar = $false,
        [bool] $BackupOk = $true,
        [string] $SidecarPath = '',
        [string] $BackupPath = '',
        [string] $Error = ''
    )

    return [pscustomobject]([ordered]@{
        HadExistingSidecar = [bool]$HadExistingSidecar
        BackupOk           = [bool]$BackupOk
        SidecarPath         = [string]$SidecarPath
        BackupPath          = [string]$BackupPath
        Error               = [string]$Error
    })
}

function Get-PublishSidecarBackupPath {
    param($Backup)

    if ($null -eq $Backup) { return '' }
    if ($Backup -is [string]) { return [string]$Backup }
    if ($Backup.PSObject.Properties['BackupPath']) { return [string]$Backup.BackupPath }
    return ''
}

function Test-PublishSidecarBackupReadyForReveal {
    param($Backup)

    if ($null -eq $Backup -or $Backup -is [string]) { return $true }
    $hadExisting = $Backup.PSObject.Properties['HadExistingSidecar'] -and [bool]$Backup.HadExistingSidecar
    $backupOk = (-not $Backup.PSObject.Properties['BackupOk']) -or [bool]$Backup.BackupOk
    return (-not $hadExisting) -or $backupOk
}

function Backup-PublishSidecarForReveal {
    param(
        [Parameter(Mandatory)] [string] $OutputPath,
        [Parameter(Mandatory)] [string] $PublishTransactionId,
        [string] $Context = ''
    )
    if (-not (Get-Command -Name Get-SidecarPath -ErrorAction SilentlyContinue)) {
        return (New-PublishSidecarBackupResult)
    }
    $sidecar = Get-SidecarPath $OutputPath
    if (-not (Test-Path -LiteralPath $sidecar -PathType Leaf -ErrorAction SilentlyContinue)) {
        return (New-PublishSidecarBackupResult -SidecarPath $sidecar)
    }
    $dir = Split-Path -Parent $sidecar
    $backup = Join-Path $dir (".{0}.mp-publish-sidecar-backup.{1}" -f (Split-Path -Leaf $sidecar), $PublishTransactionId)
    try {
        Copy-Item -LiteralPath $sidecar -Destination $backup -Force -ErrorAction Stop
        return (New-PublishSidecarBackupResult -HadExistingSidecar:$true -BackupOk:$true -SidecarPath $sidecar -BackupPath $backup)
    } catch {
        Write-Log "${Context}publish sidecar backup failed for $sidecar : $_" "WARN"
        return (New-PublishSidecarBackupResult -HadExistingSidecar:$true -BackupOk:$false -SidecarPath $sidecar -Error ([string]$_))
    }
}

function Remove-PublishSidecarBackup {
    param($BackupPath)
    $BackupPath = Get-PublishSidecarBackupPath -Backup $BackupPath
    if ([string]::IsNullOrWhiteSpace($BackupPath)) { return }
    Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
}

function Move-PublishSidecarBackupIntoPlace {
    param(
        [Parameter(Mandatory)] [string] $BackupPath,
        [Parameter(Mandatory)] [string] $SidecarPath,
        [string] $Context = ''
    )

    if (Test-Path -LiteralPath $SidecarPath -PathType Leaf -ErrorAction SilentlyContinue) {
        try {
            [System.IO.File]::Replace($BackupPath, $SidecarPath, $null, $true)
            return
        } catch {
            Write-Log "${Context}publish sidecar restore replace failed for $SidecarPath (will use overwrite move): $($_.Exception.Message)" "WARN"
            [System.IO.File]::Move($BackupPath, $SidecarPath, $true)
            return
        }
    }

    [System.IO.File]::Move($BackupPath, $SidecarPath, $true)
}

function Restore-PublishSidecarAfterRevealFailure {
    param(
        [Parameter(Mandatory)] [string] $OutputPath,
        $Backup = $null,
        [string] $BackupPath = '',
        [string] $Context = ''
    )
    if (-not (Get-Command -Name Get-SidecarPath -ErrorAction SilentlyContinue)) { return }
    $sidecar = Get-SidecarPath $OutputPath
    if ($null -ne $Backup -and $Backup -isnot [string]) {
        if ($Backup.PSObject.Properties['SidecarPath'] -and -not [string]::IsNullOrWhiteSpace([string]$Backup.SidecarPath)) {
            $sidecar = [string]$Backup.SidecarPath
        }
        if (-not (Test-PublishSidecarBackupReadyForReveal -Backup $Backup)) {
            Write-Log "${Context}publish sidecar cleanup skipped after reveal failure because existing sidecar backup was unavailable: $sidecar" "ERROR"
            return
        }
    }
    $resolvedBackupPath = if (-not [string]::IsNullOrWhiteSpace($BackupPath)) { $BackupPath } else { Get-PublishSidecarBackupPath -Backup $Backup }
    try {
        if (-not [string]::IsNullOrWhiteSpace($resolvedBackupPath) -and (Test-Path -LiteralPath $resolvedBackupPath -PathType Leaf -ErrorAction SilentlyContinue)) {
            Move-PublishSidecarBackupIntoPlace -BackupPath $resolvedBackupPath -SidecarPath $sidecar -Context $Context
            Write-Log "${Context}publish sidecar restored after reveal failure: $sidecar" "WARN"
            return
        }
        if (Test-Path -LiteralPath $sidecar -PathType Leaf -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $sidecar -Force -ErrorAction Stop
            Write-Log "${Context}publish sidecar removed after reveal failure because final media was not committed: $sidecar" "WARN"
        }
    } catch {
        Write-Log "${Context}publish sidecar cleanup failed after reveal failure for $sidecar : $_" "ERROR"
    }
}

function Complete-PublishMediaReveal {
    param(
        [Parameter(Mandatory)] [string] $PartialPath,
        [Parameter(Mandatory)] [string] $FinalPath,
        [Parameter(Mandatory)] [string] $PublishTransactionId,
        [string] $Context = ''
    )
    if (-not (Test-Path -LiteralPath $PartialPath -PathType Leaf -ErrorAction SilentlyContinue)) {
        Write-Log "${Context}publish reveal failed: partial media is missing at $PartialPath" "ERROR"
        return $false
    }
    $dir = Split-Path -Parent $FinalPath
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $backupPath = Join-Path $dir (".{0}.mp-publish-backup.{1}" -f (Split-Path -Leaf $FinalPath), $PublishTransactionId)
    try {
        if (Test-Path -LiteralPath $FinalPath -PathType Leaf -ErrorAction SilentlyContinue) {
            [System.IO.File]::Replace($PartialPath, $FinalPath, $backupPath, $true)
            Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($PartialPath, $FinalPath)
        }
        return $true
    } catch {
        Write-Log "${Context}publish reveal failed for $FinalPath : $_" "ERROR"
        Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
        return $false
    }
}
