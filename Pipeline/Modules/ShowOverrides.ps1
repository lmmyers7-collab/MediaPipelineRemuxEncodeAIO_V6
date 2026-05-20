# Modules\ShowOverrides.ps1
# Resolve per-show policy overrides against the runtime script-scope config.

function Resolve-ShowOverrides {
    param([string]$ShowName)

    $effective = @{
        DropAssAfterConversion = $script:DropAssAfterConversion
        DropTx3gAfterConversion = $script:DropTx3gAfterConversion
        DropBdpgsAfterConversion = $script:DropBdpgsAfterConversion
        RemoveKaraoke          = $script:RemoveKaraoke
        KeepSignsAndSongs      = $script:KeepSignsAndSongs
        TreatAssSignsSongsAsForced = $script:TreatAssSignsSongsAsForced
        TreatTx3gSignsSongsAsForced = $script:TreatTx3gSignsSongsAsForced
        TreatBdpgsSignsSongsAsForced = $script:TreatBdpgsSignsSongsAsForced
        ExcludeSubtitleStyles  = $script:ExcludeSubtitleStyles
        IncludeSubtitleStyles  = $script:IncludeSubtitleStyles
        FlacAsCompatible       = ($script:CompatibleAudioCodecs -contains (Get-MediaAudioCodecFlacName))
        MatchedPattern         = $null
        ShowName               = $null   # canonical show-name override; applied before Already-Processed
    }
    if (-not $ShowName -or $script:ShowOverrides.Count -eq 0) { return $effective }

    $bestPattern = $null
    foreach ($pat in $script:ShowOverrides.Keys) {
        if ($ShowName -like $pat) {
            if ($null -eq $bestPattern -or $pat.Length -gt $bestPattern.Length) {
                $bestPattern = $pat
            }
        }
    }
    if ($null -eq $bestPattern) { return $effective }

    $overrides = $script:ShowOverrides[$bestPattern]
    if ($overrides -isnot [hashtable]) { return $effective }

    foreach ($k in $overrides.Keys) {
        if ($effective.ContainsKey($k)) { $effective[$k] = $overrides[$k] }
    }
    $effective.MatchedPattern = $bestPattern
    Write-Log "SHOW OVERRIDE: '$ShowName' matched pattern '$bestPattern'" "DEBUG"
    return $effective
}
