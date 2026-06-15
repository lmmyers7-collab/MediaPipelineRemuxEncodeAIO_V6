# ==============================================================================
# ops\pipeline\engine\queue\priority_manifest.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\queue_plan.ps1. Keep function names stable;
# queue_plan.ps1 dot-sources this file as the compatibility import surface.
# ==============================================================================

function Test-StartsWithPriorityMarker {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    $trimmed = $Text.TrimStart()
    foreach ($marker in ($script:PriorityMarkers | Sort-Object Length -Descending)) {
        if ($trimmed.StartsWith($marker, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Remove-PriorityMarkersFromName {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $Text }

    $result = $Text
    for ($pass = 0; $pass -lt 6; $pass++) {
        $trimmed = $result.TrimStart()
        $matched = $false
        foreach ($marker in ($script:PriorityMarkers | Sort-Object Length -Descending)) {
            if ($trimmed.StartsWith($marker, [System.StringComparison]::OrdinalIgnoreCase)) {
                $trimmed = $trimmed.Substring($marker.Length).TrimStart(' ', '-', '_', '.')
                $result = $trimmed
                $matched = $true
                break
            }
        }
        if (-not $matched) { break }
    }

    return $result.Trim()
}

function Get-PriorityManifest {
    <#
    .SYNOPSIS
        Load priority_manifest.json from the state root.
        Returns an empty manifest hashtable on any error.
    .DESCRIPTION
        The manifest is a JSON file written by the DesktopApp API at:
          state_root / priority_manifest.json
        Format:
          { "version": 1, "entries": { "<norm-path>": { "level": "high"|"normal"|"low"|"hold", ... } } }
    #>
    $manifestPath = $null
    try {
        if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths -and $script:LocalStateLayout.Paths.PriorityManifest) {
            $manifestPath = [string]$script:LocalStateLayout.Paths.PriorityManifest
        }
    } catch {}

    $empty = @{ version = 1; entries = @{} }

    if ([string]::IsNullOrWhiteSpace($manifestPath) -or -not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return $empty
    }

    try {
        $text = [System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8)
        $obj  = $text | ConvertFrom-Json
        if (-not $obj -or $obj.version -ne 1 -or -not $obj.entries) { return $empty }
        # Convert PSObject entries to a plain hashtable for fast lookup
        $ht = @{}
        foreach ($prop in $obj.entries.PSObject.Properties) {
            $ht[$prop.Name] = $prop.Value
        }
        return @{ version = 1; entries = $ht }
    } catch {
        Write-Log "Get-PriorityManifest: failed to read manifest at '$manifestPath': $_" "WARN"
        return $empty
    }
}

function Get-ManifestPriorityLevel {
    <#
    .SYNOPSIS
        Resolve the effective manifest priority level for a source path.
    .PARAMETER Manifest
        The hashtable returned by Get-PriorityManifest.
    .PARAMETER SourcePath
        The full source file path (string).
    .OUTPUTS
        "high" | "normal" | "low" | "hold"
    .DESCRIPTION
        Resolution order (first match wins):
          1. Exact file-level entry
          2. Deepest ancestor folder entry
          3. "normal" (default — no manifest entry)
    #>
    param(
        [hashtable] $Manifest,
        [string]    $SourcePath
    )

    $validLevels = @('high', 'normal', 'low', 'hold')
    $default = 'normal'

    if (-not $Manifest -or -not $Manifest.entries -or $Manifest.entries.Count -eq 0) {
        return $default
    }

    # Normalise: lowercase, forward slashes, no trailing slash
    $norm = $SourcePath.Replace('\', '/').ToLowerInvariant().TrimEnd('/')

    $entries = $Manifest.entries

    # 1. Exact match
    if ($entries.ContainsKey($norm)) {
        $level = ([string]$entries[$norm].level).ToLowerInvariant()
        if ($level -in $validLevels) { return $level }
        return $default
    }

    # 2. Folder prefix match — deepest ancestor wins
    $bestLen = -1
    $bestLevel = $default
    foreach ($key in $entries.Keys) {
        $candidate = $norm + '/'
        if ($candidate.StartsWith($key + '/', [System.StringComparison]::OrdinalIgnoreCase) -and $key.Length -gt $bestLen) {
            $level = ([string]$entries[$key].level).ToLowerInvariant()
            if ($level -in $validLevels) {
                $bestLen   = $key.Length
                $bestLevel = $level
            }
        }
    }

    return $bestLevel
}

function Test-ManifestPriorityEntryApplies {
    <#
    .SYNOPSIS
        Return true when a valid exact or inherited manifest entry applies.
    .DESCRIPTION
        This distinguishes an explicit manifest level of "normal" from the
        default "normal" returned when no manifest entry exists.
    #>
    param(
        [hashtable] $Manifest,
        [string]    $SourcePath
    )

    $validLevels = @('high', 'normal', 'low', 'hold')
    $level = Get-ManifestEntryField -Manifest $Manifest -SourcePath $SourcePath -FieldName 'level'
    if ($null -eq $level) { return $false }
    return ([string]$level).ToLowerInvariant() -in $validLevels
}

function Get-ManifestEntryField {
    <#
    .SYNOPSIS
        Return a specific field from the manifest entry that applies to a source path.
    .DESCRIPTION
        Performs the same two-step lookup as Get-ManifestPriorityLevel (exact match then
        deepest ancestor folder) but returns an arbitrary named field from the entry
        object rather than just the "level" field.  Returns $null if the entry or field
        does not exist.
    .PARAMETER Manifest
        The hashtable returned by Get-PriorityManifest.
    .PARAMETER SourcePath
        The full source file path (string).
    .PARAMETER FieldName
        The name of the field to retrieve (e.g. "wanted_by", "position").
    #>
    param(
        [hashtable] $Manifest,
        [string]    $SourcePath,
        [string]    $FieldName
    )

    if (-not $Manifest -or -not $Manifest.entries -or $Manifest.entries.Count -eq 0) { return $null }
    if ([string]::IsNullOrWhiteSpace($SourcePath) -or [string]::IsNullOrWhiteSpace($FieldName)) { return $null }

    $norm    = $SourcePath.Replace('\', '/').ToLowerInvariant().TrimEnd('/')
    $entries = $Manifest.entries

    # Helper: extract named field from a PSObject or hashtable entry value
    $getField = {
        param($entry)
        if ($null -eq $entry) { return $null }
        try {
            # PSObject (from ConvertFrom-Json)
            $prop = $entry.PSObject.Properties[$FieldName]
            if ($prop) { return $prop.Value }
        } catch {}
        try {
            # Hashtable
            if ($entry -is [hashtable] -and $entry.ContainsKey($FieldName)) {
                return $entry[$FieldName]
            }
        } catch {}
        return $null
    }

    # 1. Exact match
    if ($entries.ContainsKey($norm)) {
        return (& $getField $entries[$norm])
    }

    # 2. Folder prefix match — deepest ancestor wins
    $bestLen   = -1
    $bestEntry = $null
    foreach ($key in $entries.Keys) {
        if ($norm.StartsWith($key + '/', [System.StringComparison]::OrdinalIgnoreCase) -and $key.Length -gt $bestLen) {
            $bestLen   = $key.Length
            $bestEntry = $entries[$key]
        }
    }
    if ($null -ne $bestEntry) { return (& $getField $bestEntry) }
    return $null
}
