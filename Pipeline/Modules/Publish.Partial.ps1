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

function Backup-PublishSidecarForReveal {
    param(
        [Parameter(Mandatory)] [string] $OutputPath,
        [Parameter(Mandatory)] [string] $PublishTransactionId,
        [string] $Context = ''
    )
    if (-not (Get-Command -Name Get-SidecarPath -ErrorAction SilentlyContinue)) { return '' }
    $sidecar = Get-SidecarPath $OutputPath
    if (-not (Test-Path -LiteralPath $sidecar -PathType Leaf -ErrorAction SilentlyContinue)) { return '' }
    $dir = Split-Path -Parent $sidecar
    $backup = Join-Path $dir (".{0}.mp-publish-sidecar-backup.{1}" -f (Split-Path -Leaf $sidecar), $PublishTransactionId)
    try {
        Copy-Item -LiteralPath $sidecar -Destination $backup -Force -ErrorAction Stop
        return $backup
    } catch {
        Write-Log "${Context}publish sidecar backup failed for $sidecar : $_" "WARN"
        return ''
    }
}

function Remove-PublishSidecarBackup {
    param([string] $BackupPath)
    if ([string]::IsNullOrWhiteSpace($BackupPath)) { return }
    Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
}

function Restore-PublishSidecarAfterRevealFailure {
    param(
        [Parameter(Mandatory)] [string] $OutputPath,
        [string] $BackupPath = '',
        [string] $Context = ''
    )
    if (-not (Get-Command -Name Get-SidecarPath -ErrorAction SilentlyContinue)) { return }
    $sidecar = Get-SidecarPath $OutputPath
    try {
        if (-not [string]::IsNullOrWhiteSpace($BackupPath) -and (Test-Path -LiteralPath $BackupPath -PathType Leaf -ErrorAction SilentlyContinue)) {
            if (Test-Path -LiteralPath $sidecar -PathType Leaf -ErrorAction SilentlyContinue) {
                [System.IO.File]::Replace($BackupPath, $sidecar, $null, $true)
            } else {
                [System.IO.File]::Move($BackupPath, $sidecar)
            }
            Write-Log "${Context}publish sidecar restored after reveal failure: $sidecar" "WARN"
            return
        }
        if (Test-Path -LiteralPath $sidecar -PathType Leaf -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $sidecar -Force -ErrorAction Stop
            Write-Log "${Context}publish sidecar removed after reveal failure because final media was not committed: $sidecar" "WARN"
        }
    } catch {
        Write-Log "${Context}publish sidecar cleanup failed after reveal failure for $sidecar : $_" "ERROR"
    } finally {
        Remove-PublishSidecarBackup -BackupPath $BackupPath
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
