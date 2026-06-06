# ==============================================================================
# ops\pipeline\engine\publish\pending_publish_index.ps1
# ==============================================================================
# In-memory index and health report for PendingServerPush manifests.
#
# Dot-sourced after PendingTransactions.ps1/PendingPush.ps1. Crash-recovery
# mechanics live in the transaction module, while index refresh owns when
# repaired manifests become visible to duplicate-detection and diagnostics.
# ==============================================================================

# Empty index template used by Refresh-PendingPublishIndex. The four maps index
# by different keys so Test-PendingPublishMatch can do O(1) lookups from any of:
# server destination path, source identity v1, or source identity v2.
function New-PendingPublishIndex {
    return @{
        Count                   = 0
        BySourceIdentity        = @{}
        BySourceIdentityV2      = @{}
        ByServerOut             = @{}
        HasSourceIdentityV2     = $false
        MissingPayloadCount     = 0
        UnreadableManifestCount = 0
        HealthRows              = [System.Collections.Generic.List[object]]::new()
    }
}

function Add-PendingPublishHealthRow {
    param(
        [Parameter(Mandatory)] $Index,
        [Parameter(Mandatory)] [string] $Code,
        [Parameter(Mandatory)] [string] $Severity,
        [Parameter(Mandatory)] [string] $ManifestPath,
        [string] $LocalFile = '',
        [string] $ServerOut = '',
        [string] $SourcePath = '',
        [string] $Message = ''
    )

    if (-not $Index.ContainsKey('HealthRows') -or $null -eq $Index.HealthRows) {
        $Index.HealthRows = [System.Collections.Generic.List[object]]::new()
    }
    $Index.HealthRows.Add([pscustomobject]@{
        code          = $Code
        severity      = $Severity
        manifest_path = $ManifestPath
        local_file    = $LocalFile
        server_out    = $ServerOut
        source_path   = $SourcePath
        message       = $Message
        observed_at   = (Get-Date -Format 'o')
    }) | Out-Null
}

# Walk PendingServerPush\ and rebuild $script:PendingPublishIndex. Cheap enough
# to run after every Invoke-ParkPendingPush / successful retry, so
# Test-PendingPublishMatch always sees current state.
function Refresh-PendingPublishIndex {
    $index = New-PendingPublishIndex
    if (-not (Test-Path -LiteralPath $LocalPendingPush)) {
        $script:PendingPublishIndex = $index
        return $index
    }

    $manifests = @(Get-ChildItem -LiteralPath $LocalPendingPush -File -Filter '*.manifest.json' -ErrorAction SilentlyContinue)
    foreach ($manifestFile in $manifests) {
        try {
            $manifest = Read-PendingManifestFile -Path $manifestFile.FullName
            $preRepairState = [string]$manifest.manifest_state
            if ($preRepairState -eq 'pending_move') {
                $repairTrust = Test-PendingManifestTrustedForRepair -ManifestFile $manifestFile -Manifest $manifest
                if (-not $repairTrust.Ok) {
                    $index.UnreadableManifestCount++
                    Add-PendingPublishHealthRow -Index $index -Code $repairTrust.Status -Severity 'error' -ManifestPath $manifestFile.FullName -LocalFile $repairTrust.LocalFile -ServerOut $repairTrust.ServerOut -SourcePath $repairTrust.SourcePath -Message $repairTrust.Reason
                    Write-Log "Pending publish index: refusing repair/index for untrusted manifest $($manifestFile.Name): $($repairTrust.Reason)" "ERROR"
                    continue
                }
            }
            $manifest = Repair-PendingManifestState -ManifestFile $manifestFile -Manifest $manifest
            $drainTrust = Test-PendingManifestTrustedForDrain -ManifestFile $manifestFile -Manifest $manifest
            if (-not $drainTrust.Ok) {
                if ($drainTrust.Status -eq 'missing_payload') {
                    $index.MissingPayloadCount++
                } else {
                    $index.UnreadableManifestCount++
                }
                Add-PendingPublishHealthRow -Index $index -Code $drainTrust.Status -Severity 'error' -ManifestPath $manifestFile.FullName -LocalFile $drainTrust.LocalFile -ServerOut $drainTrust.ServerOut -SourcePath $drainTrust.SourcePath -Message $drainTrust.Reason
                Write-Log "Pending publish index: refusing index for untrusted manifest $($manifestFile.Name): $($drainTrust.Reason)" "ERROR"
                continue
            }
            $localFile = [string]$manifest.local_file
            $serverOut = [string]$manifest.server_out
            $sourceIdentity = [string]$manifest.source_identity
            $sourceIdentityV2 = [string]$manifest.source_identity_v2
            if ([string]::IsNullOrWhiteSpace($localFile) -or -not (Test-Path -LiteralPath $localFile)) {
                $index.MissingPayloadCount++
                Add-PendingPublishHealthRow -Index $index -Code 'missing_payload' -Severity 'error' -ManifestPath $manifestFile.FullName -LocalFile $localFile -ServerOut $serverOut -SourcePath ([string]$manifest.source_path) -Message 'Pending publish manifest points to a missing local payload; retry/drain will leave this manifest for manual recovery.'
                continue
            }

            $index.Count++
            if (-not [string]::IsNullOrWhiteSpace($sourceIdentity)) {
                $index.BySourceIdentity[$sourceIdentity] = $localFile
            }
            if (-not [string]::IsNullOrWhiteSpace($sourceIdentityV2)) {
                $index.BySourceIdentity[$sourceIdentityV2] = $localFile
                $index.BySourceIdentityV2[$sourceIdentityV2] = $localFile
                $index.HasSourceIdentityV2 = $true
            }
            if (-not [string]::IsNullOrWhiteSpace($serverOut)) {
                $index.ByServerOut[$serverOut.ToLowerInvariant()] = $localFile
            }
        } catch {
            $index.UnreadableManifestCount++
            Add-PendingPublishHealthRow -Index $index -Code 'unreadable_manifest' -Severity 'error' -ManifestPath $manifestFile.FullName -Message ([string]$_)
            Write-Log "Pending publish index: failed to read $($manifestFile.Name) : $_" "WARN"
        }
    }

    $script:PendingPublishIndex = $index
    return $index
}

function Get-PendingPublishHealthReport {
    param([switch]$Refresh)

    $index = if ($Refresh -or -not $script:PendingPublishIndex) { Refresh-PendingPublishIndex } else { $script:PendingPublishIndex }
    if (-not $index -or -not $index.ContainsKey('HealthRows') -or $null -eq $index.HealthRows) {
        return @()
    }
    return @($index.HealthRows)
}

# Cheap "is this source already parked?" probe used by the main loop's
# Already-Processed gate. Hits the in-memory index, so normal matching does not
# re-read manifests.
function Test-PendingPublishMatch {
    param(
        $SourceFile,
        [string] $ServerOut
    )

    $index = if ($script:PendingPublishIndex) { $script:PendingPublishIndex } else { Refresh-PendingPublishIndex }
    if (-not $index -or [int]$index.Count -le 0) {
        return $false
    }
    if (-not [string]::IsNullOrWhiteSpace($ServerOut) -and $index.ByServerOut.ContainsKey($ServerOut.ToLowerInvariant())) {
        return $true
    }
    $sourceIdentity = Get-SourceIdentityKey $SourceFile
    if ($sourceIdentity -and $index.BySourceIdentity.ContainsKey($sourceIdentity)) {
        return $true
    }
    if (-not [bool]$index.HasSourceIdentityV2) {
        return $false
    }
    $sourceIdentityV2 = Get-SourceIdentityKeyV2 $SourceFile
    if ($sourceIdentityV2 -and $index.BySourceIdentityV2.ContainsKey($sourceIdentityV2)) {
        return $true
    }
    return $false
}
