# ==============================================================================
# engine\publish\pending_manifest_store.ps1
# ==============================================================================
# Manifest accessors and persistence helpers for PendingServerPush.
#
# Dot-sourced before PendingPush.ps1. This module intentionally keeps the same
# function names that PendingPush.ps1 used internally, so the extraction is a
# locality/testability change and not a behavior change.
# ==============================================================================

function Get-PendingObjectProperty {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name
    )

    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.Specialized.OrderedDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $null
}

function Get-PendingSidecarEntries {
    param($Manifest)

    $value = Get-PendingObjectProperty -Object $Manifest -Name 'sidecar_files'
    if ($null -eq $value) { return @() }
    return @($value | Where-Object { $null -ne $_ })
}

# PSCustomObject (from ConvertFrom-Json) -> ordered hashtable. Lets callers
# round-trip a parsed manifest, tweak fields, and re-serialise without losing key
# ordering. ConvertTo-Json on an [ordered] preserves field order in the output
# JSON; on a plain PSCustomObject it does not.
function ConvertTo-PendingManifestMap {
    param($Manifest)
    $map = [ordered]@{}
    if ($Manifest) {
        foreach ($prop in $Manifest.PSObject.Properties) {
            $map[$prop.Name] = $prop.Value
        }
    }
    return $map
}

function Read-PendingManifestFile {
    param([Parameter(Mandatory)] [string] $Path)

    return (Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop)
}

function Update-PendingManifestTx3gFailures {
    param(
        [Parameter(Mandatory)] [string] $ManifestPath,
        [Parameter(Mandatory)] $Manifest,
        [array] $Failures = @()
    )

    $failureList = @($Failures | Where-Object { $null -ne $_ })
    if ($failureList.Count -eq 0) { return }

    try {
        $currentManifest = $Manifest
        if (Test-Path -LiteralPath $ManifestPath -ErrorAction SilentlyContinue) {
            try {
                $currentManifest = Read-PendingManifestFile -Path $ManifestPath
            } catch {}
        }
        $map = ConvertTo-PendingManifestMap $currentManifest
        $map['tx3g_srt_failures'] = @($failureList)
        $map['last_tx3g_sidecar_failure_at'] = (Get-Date -Format 'o')
        $map['last_tx3g_sidecar_failure_reason'] = [string]$failureList[0].Reason
        Write-PendingManifestFile -Path $ManifestPath -Manifest $map | Out-Null
    } catch {
        Write-Log "Pending: failed to persist tx3g sidecar failure details to manifest $ManifestPath : $_" "WARN"
    }
}

function Update-PendingManifestRetryState {
    param(
        [Parameter(Mandatory)] [string] $ManifestPath,
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] [string] $State,
        [string] $Reason = '',
        [string] $Stage = '',
        [array] $Tx3gFailures = @()
    )

    try {
        $map = ConvertTo-PendingManifestMap $Manifest
        $map['manifest_state'] = $State
        $map['last_retry_at'] = (Get-Date -Format 'o')
        if (-not [string]::IsNullOrWhiteSpace($Stage)) {
            $map['last_retry_stage'] = $Stage
        }
        if (-not [string]::IsNullOrWhiteSpace($Reason)) {
            $map['last_retry_error'] = $Reason
        }
        $tx3gFailureList = @($Tx3gFailures | Where-Object { $null -ne $_ })
        if ($tx3gFailureList.Count -gt 0) {
            $map['tx3g_srt_failures'] = @($tx3gFailureList)
            $map['last_tx3g_sidecar_failure_at'] = (Get-Date -Format 'o')
            $map['last_tx3g_sidecar_failure_reason'] = [string]$tx3gFailureList[0].Reason
        }
        $retryCount = 0
        try {
            if ($map.Contains('retry_count') -and $null -ne $map['retry_count']) {
                $retryCount = [int]$map['retry_count']
            }
        } catch {
            $retryCount = 0
        }
        $map['retry_count'] = $retryCount + 1
        Write-PendingManifestFile -Path $ManifestPath -Manifest $map | Out-Null
    } catch {
        Write-Log "Pending: failed to persist retry state '$State' to manifest $ManifestPath : $_" "WARN"
    }
}

function Test-PendingManifestRoundTripValid {
    param([Parameter(Mandatory)] $RoundTrip)

    foreach ($key in @('local_file', 'server_out')) {
        $value = Get-PendingObjectProperty -Object $RoundTrip -Name $key
        if ([string]::IsNullOrWhiteSpace([string]$value)) {
            return [pscustomobject]@{ Ok = $false; Reason = "$key missing" }
        }
    }

    $schemaVersion = [string](Get-PendingObjectProperty -Object $RoundTrip -Name 'schema_version')
    if ([string]::IsNullOrWhiteSpace($schemaVersion)) {
        return [pscustomobject]@{ Ok = $true; Reason = 'legacy manifest' }
    }
    if ($schemaVersion -ne 'pending_push_manifest.v1') {
        return [pscustomobject]@{ Ok = $false; Reason = 'schema_version mismatch' }
    }

    $requiredText = @(
        'pipeline_version',
        'publish_transaction_id',
        'manifest_state',
        'route',
        'local_file',
        'server_out',
        'source_identity_v2',
        'source_identity_v2_algorithm',
        'source_path'
    )
    foreach ($key in $requiredText) {
        $value = Get-PendingObjectProperty -Object $RoundTrip -Name $key
        if ([string]::IsNullOrWhiteSpace([string]$value)) {
            return [pscustomobject]@{ Ok = $false; Reason = "$key missing" }
        }
    }

    $outputSize = Get-PendingObjectProperty -Object $RoundTrip -Name 'output_size'
    if ($null -eq $outputSize) {
        return [pscustomobject]@{ Ok = $false; Reason = 'output_size missing' }
    }
    try {
        if ([long]$outputSize -lt 0) {
            return [pscustomobject]@{ Ok = $false; Reason = 'output_size negative' }
        }
    } catch {
        return [pscustomobject]@{ Ok = $false; Reason = 'output_size invalid' }
    }

    $requiredArrays = @(
        'sidecar_files',
        'tx3g_srt_tracks',
        'tx3g_srt_failures',
        'bdpgs_srt_failures',
        'tx3g_embedded_srt_tracks',
        'bdpgs_embedded_srt_tracks'
    )
    foreach ($key in $requiredArrays) {
        if ($null -eq $RoundTrip.PSObject.Properties[$key]) {
            return [pscustomobject]@{ Ok = $false; Reason = "$key missing" }
        }
    }

    return [pscustomobject]@{ Ok = $true; Reason = 'ok' }
}

# Atomic manifest write with round-trip validation. Same temp-file-then-Replace
# dance as Write-Sidecar but with stricter post-write validation: the manifest
# is only valid if local_file and server_out both round-trip non-empty. Current
# schema manifests also must preserve transaction, identity, output-size, and
# sidecar/subtitle state fields; legacy manifests remain writable so existing
# parked jobs can still be recovered and drained. On any failure the temp/backup
# files are cleaned up and the original exception is re-thrown so callers can
# decide whether to retry.
function Write-PendingManifestFile {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] $Manifest
    )

    $dir = Split-Path $Path -Parent
    if (-not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }
    $leaf = Split-Path $Path -Leaf
    $id = [guid]::NewGuid().ToString("N")
    $tmp = Join-Path $dir ".$leaf.$id.tmp"
    $backup = Join-Path $dir ".$leaf.$id.bak"
    try {
        # S1 — Depth 5 truncated route_plan.decision_trace[].data and other
        # nested fields the deferred-publish sidecar then inherits.  Match
        # the sidecar Depth 10 so a parked-then-drained job carries the
        # same metadata as an immediate publish.
        $json = $Manifest | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        $roundTrip = Read-PendingManifestFile -Path $tmp
        $validation = Test-PendingManifestRoundTripValid -RoundTrip $roundTrip
        if (-not $validation.Ok) {
            throw "pending manifest validation failed: $($validation.Reason)"
        }

        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
        return $true
    } catch {
        if ($tmp -and (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        if ($backup -and (Test-Path -LiteralPath $backup -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}
