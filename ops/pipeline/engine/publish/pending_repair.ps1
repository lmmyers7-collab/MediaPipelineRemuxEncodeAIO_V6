# ==============================================================================
# ops\pipeline\engine\publish\pending_repair.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\publish\pending_transactions.ps1. Keep function names
# stable; pending_transactions.ps1 dot-sources this file as the public surface.
# ==============================================================================

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
