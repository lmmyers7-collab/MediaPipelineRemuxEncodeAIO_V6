# ==============================================================================
# Modules\FileOverrides.ps1
# ==============================================================================
# Per-file (and per-folder) à-la-carte processing overrides.
#
# Reads file_overrides.json from the pipeline state root and resolves the
# effective override object for any source path at processing time.
#
# Dot-sourced from MediaPipeline_chatgpt.ps1. Reads at call time:
#   $script:LocalStateLayout  (used for file_overrides.json path)
#
# Cross-module helpers (loaded before this module):
#   Write-Log
#
# Functions exported:
#   Get-FileOverridesManifest
#   Resolve-FileOverride
#   Get-FileOverrideAudioSettings
#   Get-FileOverrideSubtitleSettings
#   Test-AudioTrackKeptByOverride
#   Test-SubtitleTrackKeptByOverride
#   Get-AudioTrackTitleOverride
#   Get-SubtitleTrackTitleOverride
#   Merge-FileOverrideIntoActiveOverrides
# ==============================================================================

# Cached manifest — re-loaded per pipeline round; reset to $null at start of round.
$script:CachedFileOverridesManifest = $null

function Get-FileOverridesManifest {
    <#
    .SYNOPSIS
        Load file_overrides.json from the state root.
        Returns an empty manifest hashtable on any error.
    .DESCRIPTION
        The manifest is loaded once per use; the caller is responsible for
        clearing $script:CachedFileOverridesManifest between pipeline rounds
        if the file may have been updated.
    #>
    if ($null -ne $script:CachedFileOverridesManifest) {
        return $script:CachedFileOverridesManifest
    }

    $manifestPath = $null
    try {
        if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths) {
            $p = $script:LocalStateLayout.Paths
            if ($p.PSObject.Properties['FileOverrides']) {
                $manifestPath = [string]$p.FileOverrides
            }
        }
    } catch {}

    $empty = @{ version = 1; entries = @{} }

    if ([string]::IsNullOrWhiteSpace($manifestPath) -or -not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        $script:CachedFileOverridesManifest = $empty
        return $empty
    }

    try {
        $text = [System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8)
        $obj  = $text | ConvertFrom-Json
        if (-not $obj -or $obj.version -ne 1 -or -not $obj.entries) {
            $script:CachedFileOverridesManifest = $empty
            return $empty
        }
        # Convert PSObject entries to a plain hashtable for fast lookup
        $ht = @{}
        foreach ($prop in $obj.entries.PSObject.Properties) {
            $ht[$prop.Name] = $prop.Value
        }
        $result = @{ version = 1; entries = $ht }
        $script:CachedFileOverridesManifest = $result
        return $result
    } catch {
        Write-Log "Get-FileOverridesManifest: failed to read manifest: $_" "WARN"
        $script:CachedFileOverridesManifest = $empty
        return $empty
    }
}

function Resolve-FileOverride {
    <#
    .SYNOPSIS
        Return the effective override object for a source path.
    .DESCRIPTION
        Resolution order (first match wins):
          1. Exact file-level entry
          2. Deepest ancestor folder entry
          3. $null — no override
    .PARAMETER SourcePath
        The full source file path (string).
    .OUTPUTS
        PSObject | $null
    #>
    param([string]$SourcePath)

    $manifest = Get-FileOverridesManifest
    if ($null -eq $manifest -or $manifest.entries.Count -eq 0) { return $null }

    $norm    = $SourcePath.Replace('\', '/').ToLowerInvariant().TrimEnd('/')
    $entries = $manifest.entries

    # 1. Exact match
    if ($entries.ContainsKey($norm)) { return $entries[$norm] }

    # 2. Folder prefix match — deepest ancestor wins
    $bestLen   = -1
    $bestEntry = $null
    foreach ($key in $entries.Keys) {
        if ($norm.StartsWith($key + '/', [System.StringComparison]::OrdinalIgnoreCase) -and $key.Length -gt $bestLen) {
            $bestLen   = $key.Length
            $bestEntry = $entries[$key]
        }
    }
    return $bestEntry   # $null if no match
}

function Get-FileOverrideAudioSettings {
    <#
    .SYNOPSIS
        Extract the audio section from the active file override (stored in
        $script:ActiveOverrides under the '_FileOverride' key).
    .OUTPUTS
        PSObject | $null — the audio sub-object, or $null if no audio override.
    #>
    try {
        if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('_FileOverride')) {
            $fo = $script:ActiveOverrides['_FileOverride']
            if ($fo) {
                $audio = $null
                try {
                    $audio = $fo.audio
                } catch {}
                if ($null -eq $audio) {
                    try {
                        $prop = $fo.PSObject.Properties['audio']
                        if ($prop) { $audio = $prop.Value }
                    } catch {}
                }
                return $audio
            }
        }
    } catch {}
    return $null
}

function Get-FileOverrideSubtitleSettings {
    <#
    .SYNOPSIS
        Extract the subtitles section from the active file override.
    .OUTPUTS
        PSObject | $null
    #>
    try {
        if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('_FileOverride')) {
            $fo = $script:ActiveOverrides['_FileOverride']
            if ($fo) {
                $subs = $null
                try {
                    $subs = $fo.subtitles
                } catch {}
                if ($null -eq $subs) {
                    try {
                        $prop = $fo.PSObject.Properties['subtitles']
                        if ($prop) { $subs = $prop.Value }
                    } catch {}
                }
                return $subs
            }
        }
    } catch {}
    return $null
}

function Test-AudioTrackKeptByOverride {
    <#
    .SYNOPSIS
        Test whether an audio track passes the per-file keepTracks/dropTracks filter.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase), e.g. "eng", "jpn", "und".
    .PARAMETER Channels
        Number of audio channels (integer).
    .PARAMETER Title
        Raw title tag from the source file (may be empty).
    .PARAMETER AudioOverride
        The audio sub-object from Resolve-FileOverride (or Get-FileOverrideAudioSettings).
        If $null, no filtering is applied and the track is always kept.
    .OUTPUTS
        [bool]  $true = keep the track, $false = drop it.
    .DESCRIPTION
        Resolution:
          1. If dropTracks rules exist and the track matches ANY drop rule → drop.
          2. If keepTracks rules exist and the track matches NONE of them → drop.
          3. Otherwise → keep.

        A rule matches a track when ALL non-null fields in the rule match the
        corresponding track property:
          language  — case-insensitive ISO 639-2 match (also handles "und")
          channels  — exact integer match
          title     — glob pattern (wildcards: * ? [...])
    #>
    param(
        [string] $Language,
        [int]    $Channels,
        [string] $Title,
        $AudioOverride
    )

    if ($null -eq $AudioOverride) { return $true }

    $lang  = if ([string]::IsNullOrWhiteSpace($Language)) { 'und' } else { $Language.Trim().ToLowerInvariant() }
    $title = if ($null -eq $Title) { '' } else { [string]$Title }

    # Helper: does a single rule match the track?
    $ruleMatches = {
        param($rule)
        # language check
        $ruleLang = $null
        try { $ruleLang = [string]$rule.language } catch {}
        if ($null -ne $ruleLang -and -not [string]::IsNullOrWhiteSpace($ruleLang)) {
            if (-not ($lang -eq $ruleLang.Trim().ToLowerInvariant())) { return $false }
        }
        # channels check
        $ruleChannels = $null
        try { $ruleChannels = [int]$rule.channels } catch {}
        if ($null -ne $ruleChannels -and $ruleChannels -gt 0) {
            if ($Channels -ne $ruleChannels) { return $false }
        }
        # title check (glob)
        $ruleTitle = $null
        try { $ruleTitle = [string]$rule.title } catch {}
        if (-not [string]::IsNullOrWhiteSpace($ruleTitle)) {
            if (-not ($title -like $ruleTitle)) { return $false }
        }
        return $true
    }

    # Get dropTracks and keepTracks lists
    $dropRules = $null
    $keepRules = $null
    try {
        $drProp = $AudioOverride.PSObject.Properties['dropTracks']
        if ($drProp -and $drProp.Value) { $dropRules = @($drProp.Value) }
    } catch {}
    try {
        $krProp = $AudioOverride.PSObject.Properties['keepTracks']
        if ($krProp -and $krProp.Value) { $keepRules = @($krProp.Value) }
    } catch {}

    # 1. Drop rule match → always drop
    if ($null -ne $dropRules -and $dropRules.Count -gt 0) {
        foreach ($rule in $dropRules) {
            if ($null -ne $rule -and (& $ruleMatches $rule)) { return $false }
        }
    }

    # 2. keepTracks exists but track doesn't match any rule → drop
    if ($null -ne $keepRules -and $keepRules.Count -gt 0) {
        $matched = $false
        foreach ($rule in $keepRules) {
            if ($null -ne $rule -and (& $ruleMatches $rule)) { $matched = $true; break }
        }
        if (-not $matched) { return $false }
    }

    return $true
}

function Test-SubtitleTrackKeptByOverride {
    <#
    .SYNOPSIS
        Test whether a subtitle track passes the per-file keepTracks/dropTracks filter.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase).
    .PARAMETER IsForced
        $true if the track has the forced flag set.
    .PARAMETER Title
        Raw title tag from the source file.
    .PARAMETER SubtitleOverride
        The subtitles sub-object from Resolve-FileOverride (or Get-FileOverrideSubtitleSettings).
    .OUTPUTS
        [bool]  $true = keep the track, $false = drop it.
    #>
    param(
        [string] $Language,
        [bool]   $IsForced,
        [string] $Title,
        $SubtitleOverride
    )

    if ($null -eq $SubtitleOverride) { return $true }

    # stripAll shortcut
    $stripAll = $false
    try { $stripAll = [bool]$SubtitleOverride.stripAll } catch {}
    if ($stripAll) { return $false }

    $lang  = if ([string]::IsNullOrWhiteSpace($Language)) { 'und' } else { $Language.Trim().ToLowerInvariant() }
    $title = if ($null -eq $Title) { '' } else { [string]$Title }

    $ruleMatchesSub = {
        param($rule)
        # language
        $ruleLang = $null
        try { $ruleLang = [string]$rule.language } catch {}
        if (-not [string]::IsNullOrWhiteSpace($ruleLang)) {
            if ($lang -ne $ruleLang.Trim().ToLowerInvariant()) { return $false }
        }
        # forced flag — only check if the rule explicitly specifies it
        $ruleForced = $null
        try {
            $fp = $rule.PSObject.Properties['forced']
            if ($fp) { $ruleForced = [bool]$fp.Value }
        } catch {}
        if ($null -ne $ruleForced -and $ruleForced -ne $IsForced) { return $false }
        # title glob
        $ruleTitle = $null
        try { $ruleTitle = [string]$rule.title } catch {}
        if (-not [string]::IsNullOrWhiteSpace($ruleTitle)) {
            if (-not ($title -like $ruleTitle)) { return $false }
        }
        return $true
    }

    $dropRules = $null
    $keepRules = $null
    try {
        $drProp = $SubtitleOverride.PSObject.Properties['dropTracks']
        if ($drProp -and $drProp.Value) { $dropRules = @($drProp.Value) }
    } catch {}
    try {
        $krProp = $SubtitleOverride.PSObject.Properties['keepTracks']
        if ($krProp -and $krProp.Value) { $keepRules = @($krProp.Value) }
    } catch {}

    # Drop rule wins
    if ($null -ne $dropRules -and $dropRules.Count -gt 0) {
        foreach ($rule in $dropRules) {
            if ($null -ne $rule -and (& $ruleMatchesSub $rule)) { return $false }
        }
    }
    # Not in keepTracks → drop
    if ($null -ne $keepRules -and $keepRules.Count -gt 0) {
        $matched = $false
        foreach ($rule in $keepRules) {
            if ($null -ne $rule -and (& $ruleMatchesSub $rule)) { $matched = $true; break }
        }
        if (-not $matched) { return $false }
    }
    return $true
}

function Get-AudioTrackTitleOverride {
    <#
    .SYNOPSIS
        Return the newTitle string from a matching renameTracks rule, or $null.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase).
    .PARAMETER Channels
        Output channel count (after downmix).
    .PARAMETER AudioOverride
        The audio sub-object.
    .OUTPUTS
        [string] | $null
    #>
    param(
        [string] $Language,
        [int]    $Channels,
        $AudioOverride
    )

    if ($null -eq $AudioOverride) { return $null }

    $renameRules = $null
    try {
        $rp = $AudioOverride.PSObject.Properties['renameTracks']
        if ($rp -and $rp.Value) { $renameRules = @($rp.Value) }
    } catch {}

    if ($null -eq $renameRules -or $renameRules.Count -eq 0) { return $null }

    $lang = if ([string]::IsNullOrWhiteSpace($Language)) { 'und' } else { $Language.Trim().ToLowerInvariant() }

    foreach ($rule in $renameRules) {
        if ($null -eq $rule) { continue }
        # language match
        $ruleLang = $null
        try { $ruleLang = [string]$rule.language } catch {}
        if (-not [string]::IsNullOrWhiteSpace($ruleLang)) {
            if ($lang -ne $ruleLang.Trim().ToLowerInvariant()) { continue }
        }
        # channels match
        $ruleChannels = $null
        try { $ruleChannels = [int]$rule.channels } catch {}
        if ($null -ne $ruleChannels -and $ruleChannels -gt 0 -and $Channels -ne $ruleChannels) { continue }
        # matched — return newTitle
        $newTitle = $null
        try { $newTitle = [string]$rule.newTitle } catch {}
        if (-not [string]::IsNullOrWhiteSpace($newTitle)) { return $newTitle }
    }
    return $null
}

function Get-SubtitleTrackTitleOverride {
    <#
    .SYNOPSIS
        Return the newTitle string from a matching subtitle renameTracks rule, or $null.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase).
    .PARAMETER IsForced
        $true if the track has the forced flag.
    .PARAMETER SubtitleOverride
        The subtitles sub-object.
    .OUTPUTS
        [string] | $null
    #>
    param(
        [string] $Language,
        [bool]   $IsForced,
        $SubtitleOverride
    )

    if ($null -eq $SubtitleOverride) { return $null }

    $renameRules = $null
    try {
        $rp = $SubtitleOverride.PSObject.Properties['renameTracks']
        if ($rp -and $rp.Value) { $renameRules = @($rp.Value) }
    } catch {}

    if ($null -eq $renameRules -or $renameRules.Count -eq 0) { return $null }

    $lang = if ([string]::IsNullOrWhiteSpace($Language)) { 'und' } else { $Language.Trim().ToLowerInvariant() }

    foreach ($rule in $renameRules) {
        if ($null -eq $rule) { continue }
        $ruleLang = $null
        try { $ruleLang = [string]$rule.language } catch {}
        if (-not [string]::IsNullOrWhiteSpace($ruleLang)) {
            if ($lang -ne $ruleLang.Trim().ToLowerInvariant()) { continue }
        }
        $ruleForced = $null
        try {
            $fp = $rule.PSObject.Properties['forced']
            if ($fp) { $ruleForced = [bool]$fp.Value }
        } catch {}
        if ($null -ne $ruleForced -and $ruleForced -ne $IsForced) { continue }
        $newTitle = $null
        try { $newTitle = [string]$rule.newTitle } catch {}
        if (-not [string]::IsNullOrWhiteSpace($newTitle)) { return $newTitle }
    }
    return $null
}

function Merge-FileOverrideIntoActiveOverrides {
    <#
    .SYNOPSIS
        Inject the per-file override for $SourcePath into $script:ActiveOverrides.
    .DESCRIPTION
        Reads file_overrides.json (cached), resolves the entry for $SourcePath,
        and stores it under the '_FileOverride' key in $script:ActiveOverrides.
        Flat config-style fields (maxChannels, downmixMode, etc.) are also
        promoted to top-level ActiveOverrides keys so existing Get-Effective*
        functions pick them up without modification.
    .PARAMETER SourcePath
        The full source file path.
    #>
    param([string]$SourcePath)

    # Invalidate the manifest cache on every new file so edits made during
    # a long pipeline run are picked up.
    $script:CachedFileOverridesManifest = $null

    $override = Resolve-FileOverride -SourcePath $SourcePath
    if ($null -eq $override) {
        # Ensure any previous file's _FileOverride is cleared
        if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('_FileOverride')) {
            $script:ActiveOverrides.Remove('_FileOverride')
        }
        return
    }

    if ($null -eq $script:ActiveOverrides) { $script:ActiveOverrides = @{} }

    # Store the full structured override for track-filter functions
    $script:ActiveOverrides['_FileOverride'] = $override

    # Promote flat audio config fields into top-level ActiveOverrides so that
    # existing Get-EffectiveAudio* functions work without modification.
    $audioFieldMap = @{
        maxChannels          = 'AudioMaxChannels'
        downmixMode          = 'AudioDownmixMode'
        transcodeCodec       = 'AudioTranscodeCodec'
        transcodeBitrate     = 'AudioTranscodeBitrate'
        preferDefaultLanguage = 'PreferredDefaultAudioLanguages'
    }
    try {
        $audioProp = $override.PSObject.Properties['audio']
        if ($audioProp -and $audioProp.Value) {
            $audio = $audioProp.Value
            foreach ($srcKey in $audioFieldMap.Keys) {
                $destKey = $audioFieldMap[$srcKey]
                $vProp = $audio.PSObject.Properties[$srcKey]
                if ($vProp -and $null -ne $vProp.Value) {
                    # preferDefaultLanguage → single value wrapped in array
                    if ($srcKey -eq 'preferDefaultLanguage') {
                        $script:ActiveOverrides[$destKey] = @([string]$vProp.Value)
                    } else {
                        $script:ActiveOverrides[$destKey] = $vProp.Value
                    }
                }
            }
        }
    } catch {}
}
