# ==============================================================================
# ops\pipeline\engine\paths\effective_settings.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\paths\output_path_planning.ps1. Keep function names
# stable; output_path_planning.ps1 dot-sources this file as the public surface.
# ==============================================================================

function Get-MediaPipelineLibraryOverrideConfigKeys {
    return @(
        'RoutingProfile',
        'RouteThresholdMode',
        'SizeGuardMode',
        'EncodeTuningPreset',
        'EncodeLadder',
        'VideoCodec',
        'OutputContainer',
        'EncodeThresholdGB',
        'TVEncodeThresholdGB',
        'MovieRoute1080pTargetSizeGB',
        'MovieRoute1440pTargetSizeGB',
        'MovieRoute4KTargetSizeGB',
        'TVRoute1080pTargetSizeGB',
        'TVRoute1440pTargetSizeGB',
        'TVRoute4KTargetSizeGB',
        'MovieRouteMaxVideoBitrateMbps',
        'TVRouteMaxVideoBitrateMbps',
        'Route1080pBucketMaxHeight',
        'Route1080pUpperHeightTolerancePercent',
        'Route1080pMaxVideoBitrateMbps',
        'Route1440pLowerHeightTolerancePercent',
        'Route1440pUpperHeightTolerancePercent',
        'Route1440pMaxVideoBitrateMbps',
        'Route4KLowerHeightTolerancePercent',
        'Route4KBucketMinHeight',
        'Route4KMaxVideoBitrateMbps',
        'MaxEncodeGrowthPercent',
        'CompatibilityEncodeGrowthPercent',
        'VideoPreset',
        'VideoQuality',
        'AllowH264RemuxIfPlexCompatible',
        'H264RemuxMaxBitrateMbps',
        'H264RemuxMaxHeight',
        'RemuxSafeVideoCodecs',
        'FallbackCpuQuality',
        'CpuEncodePreset',
        'CpuEncodeProcessPriority',
        'CpuEncodeMaxThreads',
        'ExtraVideoFlags',
        'SubKeepLanguages',
        'ConvertTx3gToSrt',
        'DropTx3gAfterConversion',
        'CreateExternalTx3gSrtSidecars',
        'Tx3gExtractLanguages',
        'Tx3gPreserveExistingSrt',
        'Tx3gTreatForcedAsSeparate',
        'ConvertBdpgsToSrt',
        'DropBdpgsAfterConversion',
        'BdpgsExtractLanguages',
        'BdpgsOcrToolPath',
        'BdpgsOcrTessdataPath',
        'ConvertVobSubToSrt',
        'DropVobSubAfterConversion',
        'VobSubExtractLanguages',
        'VobSubOcrToolPath',
        'SubtitleExtractTimeoutSeconds',
        'SubtitleProbeTimeoutSeconds',
        'BdpgsOcrTimeoutSeconds',
        'VobSubOcrTimeoutSeconds',
        'SubSDHTitleKeywords',
        'SubSupplementalKeywords',
        'DropAssAfterConversion',
        'StripFormatting',
        'RemoveKaraoke',
        'MergeAdjacent',
        'MergeThresholdMs',
        'KeepSignsAndSongs',
        'TreatAssSignsSongsAsForced',
        'TreatTx3gSignsSongsAsForced',
        'TreatBdpgsSignsSongsAsForced',
        'TreatVobSubSignsSongsAsForced',
        'ExcludeSubtitleStyles',
        'IncludeSubtitleStyles',
        'AudioPassthroughProfile',
        'CompatibleAudioCodecs',
        'PreferredDefaultAudioLanguages',
        'AudioTranscodeCodec',
        'AudioTranscodeBitrate',
        'AudioTranscodeAutoBitrateByChannels',
        'AudioDownmixMode',
        'AudioMaxChannels',
        'AllowNoAudio'
    )
}

function Add-MediaPipelineLibraryOverrideGroup {
    param(
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Target,
        $Values
    )

    $allowed = @{}
    foreach ($key in Get-MediaPipelineLibraryOverrideConfigKeys) { $allowed[$key] = $true }
    $map = ConvertTo-MediaPipelineProfileMap $Values
    foreach ($key in $map.Keys) {
        $name = [string]$key
        if (-not $allowed.ContainsKey($name)) { continue }
        $Target[$name] = $map[$key]
    }
}

function Get-MediaPipelineLibraryProfileOverrideMap {
    param($Profile)

    $merged = [ordered]@{}
    if (-not $Profile) { return $merged }

    $overrides = ConvertTo-MediaPipelineProfileMap (Get-MediaPipelineProfileProperty -Profile $Profile -Name 'overrides' -Default $null)
    foreach ($group in @('editor','video','subtitles','subtitle','audio')) {
        if ($overrides.Contains($group)) {
            Add-MediaPipelineLibraryOverrideGroup -Target $merged -Values $overrides[$group]
        }
    }

    Add-MediaPipelineLibraryOverrideGroup -Target $merged -Values (Get-MediaPipelineProfileProperty -Profile $Profile -Name 'editor_overrides' -Default $null)
    Add-MediaPipelineLibraryOverrideGroup -Target $merged -Values (Get-MediaPipelineProfileProperty -Profile $Profile -Name 'media_overrides' -Default $null)
    return $merged
}

function Resolve-MediaPipelineLibraryOverridesForPath {
    param(
        [string] $SourcePath,
        [string] $LibraryProfileId = ''
    )

    $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $SourcePath -LibraryProfileId $LibraryProfileId
    if (-not $profile) { return [ordered]@{} }
    return Get-MediaPipelineLibraryProfileOverrideMap -Profile $profile
}

function Get-MediaPipelineLibraryDefaultConfigMap {
    $defaults = [ordered]@{}
    foreach ($key in Get-MediaPipelineLibraryOverrideConfigKeys) {
        $existing = Get-Variable -Name $key -Scope Script -ErrorAction SilentlyContinue
        if ($null -ne $existing) {
            $defaults[$key] = $existing.Value
        }
    }
    return $defaults
}

function New-MediaPipelineRuntimeSettingsLayer {
    param(
        [Parameter(Mandatory)] [ValidateSet('global','library','show','folder','file','source')] [string] $Name,
        [Parameter(Mandatory)] [string] $Source,
        $Keys = $null,
        [bool] $Known = $true,
        [bool] $SavedConfig = $true,
        [string[]] $ExcludeKeys = @()
    )

    $excluded = @{}
    foreach ($key in @($ExcludeKeys)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$key)) {
            $excluded[[string]$key] = $true
        }
    }

    $keyMap = [ordered]@{}
    $rawMap = ConvertTo-MediaPipelineProfileMap $Keys
    foreach ($key in $rawMap.Keys) {
        $keyText = [string]$key
        if ($excluded.Contains($keyText)) { continue }
        $keyMap[$keyText] = $rawMap[$key]
    }

    return [ordered]@{
        name         = $Name
        source       = $Source
        keys         = $keyMap
        known        = [bool]$Known
        saved_config = [bool]$SavedConfig
    }
}

function Get-MediaPipelineRuntimeGlobalSettingsLayer {
    return New-MediaPipelineRuntimeSettingsLayer `
        -Name 'global' `
        -Source 'active_config' `
        -Keys (Get-MediaPipelineLibraryDefaultConfigMap)
}

function New-MediaPipelineRuntimeEffectiveSettingsEvidence {
    param(
        [object[]] $Layers = @(),
        [string[]] $UnsupportedKeys = @(),
        [string[]] $IgnoredKeys = @(),
        [string[]] $Warnings = @()
    )

    $normalizedLayers = @()
    $effectiveValues = [ordered]@{}
    $sourceHistory = @{}
    foreach ($layer in @($Layers)) {
        if (-not $layer) { continue }
        $name = [string](Get-MediaPipelineProfileProperty -Profile $layer -Name 'name' -Default '')
        if ([string]::IsNullOrWhiteSpace($name)) { continue }
        $keys = ConvertTo-MediaPipelineProfileMap (Get-MediaPipelineProfileProperty -Profile $layer -Name 'keys' -Default $null)
        $normalizedLayer = [ordered]@{
            name         = $name
            source       = [string](Get-MediaPipelineProfileProperty -Profile $layer -Name 'source' -Default '')
            keys         = $keys
            known        = [bool](Get-MediaPipelineProfileProperty -Profile $layer -Name 'known' -Default $true)
            saved_config = [bool](Get-MediaPipelineProfileProperty -Profile $layer -Name 'saved_config' -Default $true)
        }
        $normalizedLayers += $normalizedLayer

        foreach ($key in $keys.Keys) {
            $keyText = [string]$key
            $priorLayers = [System.Collections.Generic.List[string]]::new()
            if ($sourceHistory.Contains($keyText)) {
                foreach ($priorLayer in @([object[]]$sourceHistory[$keyText])) {
                    if (-not [string]::IsNullOrWhiteSpace([string]$priorLayer)) {
                        $priorLayers.Add([string]$priorLayer)
                    }
                }
            }
            $effectiveValues[$keyText] = [ordered]@{
                value        = $keys[$key]
                source_layer = $name
                overrode     = @($priorLayers.ToArray())
            }
            $updatedLayers = [System.Collections.Generic.List[string]]::new()
            foreach ($priorLayer in $priorLayers) { $updatedLayers.Add($priorLayer) }
            $updatedLayers.Add($name)
            $sourceHistory[$keyText] = $updatedLayers.ToArray()
        }
    }

    return [ordered]@{
        schema                         = 'runtime_effective_settings.v1'
        scope                          = 'job'
        library_effective_settings_ref = 'library-only'
        layers                         = @($normalizedLayers)
        effective_values               = $effectiveValues
        unsupported_keys               = @($UnsupportedKeys | ForEach-Object { [string]$_ })
        ignored_keys                   = @($IgnoredKeys | ForEach-Object { [string]$_ })
        warnings                       = @($Warnings | ForEach-Object { [string]$_ })
    }
}

function Get-MediaPipelineRuntimeLayerNames {
    param($RuntimeEffectiveSettings)

    $layers = Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'layers' -Default @()
    return @($layers | ForEach-Object {
        [string](Get-MediaPipelineProfileProperty -Profile $_ -Name 'name' -Default '')
    } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Get-MediaPipelineRuntimeEffectiveSettingSources {
    param(
        $RuntimeEffectiveSettings,
        [string[]] $Keys = @()
    )

    $result = [ordered]@{}
    $effectiveValues = [ordered]@{}
    if ($null -ne $RuntimeEffectiveSettings) {
        $effectiveValues = ConvertTo-MediaPipelineProfileMap (Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'effective_values' -Default $null)
    }
    foreach ($key in @($Keys)) {
        $keyText = [string]$key
        if ([string]::IsNullOrWhiteSpace($keyText) -or -not $effectiveValues.Contains($keyText)) { continue }
        $entry = $effectiveValues[$keyText]
        $result[$keyText] = [ordered]@{
            source_layer = [string](Get-MediaPipelineProfileProperty -Profile $entry -Name 'source_layer' -Default '')
            overrode     = @((Get-MediaPipelineProfileProperty -Profile $entry -Name 'overrode' -Default @()) | ForEach-Object { [string]$_ })
        }
    }
    return $result
}

function Get-MediaPipelineRuntimeRoutingConsumerKeys {
    return @(
        'RouteForce',
        'RoutePrefer',
        'RoutePolicyReason',
        'RoutingProfile',
        'RouteThresholdMode',
        'SizeGuardMode',
        'EncodeTuningPreset',
        'EncodeLadder',
        'VideoCodec',
        'OutputContainer',
        'EncodeThresholdGB',
        'TVEncodeThresholdGB',
        'MovieRoute1080pTargetSizeGB',
        'MovieRoute1440pTargetSizeGB',
        'MovieRoute4KTargetSizeGB',
        'TVRoute1080pTargetSizeGB',
        'TVRoute1440pTargetSizeGB',
        'TVRoute4KTargetSizeGB',
        'MovieRouteMaxVideoBitrateMbps',
        'TVRouteMaxVideoBitrateMbps',
        'Route1080pBucketMaxHeight',
        'Route1080pUpperHeightTolerancePercent',
        'Route1080pMaxVideoBitrateMbps',
        'Route1440pLowerHeightTolerancePercent',
        'Route1440pUpperHeightTolerancePercent',
        'Route1440pMaxVideoBitrateMbps',
        'Route4KLowerHeightTolerancePercent',
        'Route4KBucketMinHeight',
        'Route4KMaxVideoBitrateMbps',
        'MaxEncodeGrowthPercent',
        'CompatibilityEncodeGrowthPercent',
        'AllowH264RemuxIfPlexCompatible',
        'H264RemuxMaxBitrateMbps',
        'H264RemuxMaxHeight',
        'RemuxSafeVideoCodecs'
    )
}

function Get-MediaPipelineRuntimeAudioConsumerKeys {
    return @(
        'AudioPassthroughProfile',
        'CompatibleAudioCodecs',
        'PreferredDefaultAudioLanguages',
        'AudioTranscodeCodec',
        'AudioTranscodeBitrate',
        'AudioTranscodeAutoBitrateByChannels',
        'AudioDownmixMode',
        'AudioMaxChannels',
        'AllowNoAudio'
    )
}

function Get-MediaPipelineRuntimeSubtitleConsumerKeys {
    return @(
        'SubKeepLanguages',
        'ConvertTx3gToSrt',
        'DropTx3gAfterConversion',
        'CreateExternalTx3gSrtSidecars',
        'Tx3gExtractLanguages',
        'Tx3gPreserveExistingSrt',
        'Tx3gTreatForcedAsSeparate',
        'ConvertBdpgsToSrt',
        'DropBdpgsAfterConversion',
        'BdpgsExtractLanguages',
        'BdpgsOcrToolPath',
        'BdpgsOcrTessdataPath',
        'ConvertVobSubToSrt',
        'DropVobSubAfterConversion',
        'VobSubExtractLanguages',
        'VobSubOcrToolPath',
        'VobSubOcrTimeoutSeconds',
        'TreatVobSubSignsSongsAsForced',
        'SubtitleExtractTimeoutSeconds',
        'SubtitleProbeTimeoutSeconds',
        'BdpgsOcrTimeoutSeconds',
        'SubSDHTitleKeywords',
        'SubSupplementalKeywords',
        'DropAssAfterConversion',
        'StripFormatting',
        'RemoveKaraoke',
        'MergeAdjacent',
        'MergeThresholdMs',
        'KeepSignsAndSongs',
        'TreatAssSignsSongsAsForced',
        'TreatTx3gSignsSongsAsForced',
        'TreatBdpgsSignsSongsAsForced',
        'ExcludeSubtitleStyles',
        'IncludeSubtitleStyles'
    )
}

function New-MediaPipelineRuntimeConsumerSettingsEvidence {
    param(
        [Parameter(Mandatory)] $RuntimeEffectiveSettings,
        [Parameter(Mandatory)] [string] $Consumer,
        [string[]] $Keys = @(),
        [string] $DecisionScope = '',
        [string] $ActionSelected = '',
        [string] $ActionEvidence = '',
        $DecisionImpact = $null,
        $Consequences = $null
    )

    $impactMap = ConvertTo-MediaPipelineProfileMap $DecisionImpact
    $consequenceMap = ConvertTo-MediaPipelineProfileMap $Consequences
    $effectiveValues = [ordered]@{}
    if ($null -ne $RuntimeEffectiveSettings) {
        $effectiveValues = ConvertTo-MediaPipelineProfileMap (Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'effective_values' -Default $null)
    }
    $settings = [ordered]@{}
    foreach ($key in @($Keys)) {
        $keyText = [string]$key
        if ([string]::IsNullOrWhiteSpace($keyText)) { continue }
        if ($effectiveValues.Contains($keyText)) {
            $entry = $effectiveValues[$keyText]
            $settings[$keyText] = [ordered]@{
                value             = Get-MediaPipelineProfileProperty -Profile $entry -Name 'value' -Default $null
                source_layer      = [string](Get-MediaPipelineProfileProperty -Profile $entry -Name 'source_layer' -Default '')
                overrode          = @((Get-MediaPipelineProfileProperty -Profile $entry -Name 'overrode' -Default @()) | ForEach-Object { [string]$_ })
                decision_scope    = [string]$DecisionScope
                decision_impact   = if ($impactMap.Contains($keyText)) { $impactMap[$keyText] } else { 'consumer_input' }
                consequence       = if ($consequenceMap.Contains($keyText)) { [string]$consequenceMap[$keyText] } else { '' }
                available         = $true
            }
        } else {
            $settings[$keyText] = [ordered]@{
                value             = $null
                source_layer      = 'unresolved'
                overrode          = @()
                decision_scope    = [string]$DecisionScope
                decision_impact   = if ($impactMap.Contains($keyText)) { $impactMap[$keyText] } else { 'consumer_input' }
                consequence       = if ($consequenceMap.Contains($keyText)) { [string]$consequenceMap[$keyText] } else { 'not present in runtime evidence' }
                available         = $false
            }
        }
    }

    return [ordered]@{
        schema          = 'runtime_consumer_settings.v1'
        consumer        = [string]$Consumer
        diagnostic_only = $true
        evidence_source = 'runtime_effective_settings.v1'
        action_selected = [string]$ActionSelected
        action_evidence = [string]$ActionEvidence
        settings        = $settings
        unsupported_keys = @((Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'unsupported_keys' -Default @()) | ForEach-Object { [string]$_ })
        ignored_keys     = @((Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'ignored_keys' -Default @()) | ForEach-Object { [string]$_ })
        warnings         = @((Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'warnings' -Default @()) | ForEach-Object { [string]$_ })
    }
}

function Resolve-MediaPipelineLibraryEffectiveSettings {
    param(
        $Profile = $null,
        $Overrides = $null
    )

    $effective = Get-MediaPipelineLibraryDefaultConfigMap
    $overrideMap = if ($null -ne $Overrides) {
        ConvertTo-MediaPipelineProfileMap $Overrides
    } elseif ($null -ne $Profile) {
        Get-MediaPipelineLibraryProfileOverrideMap -Profile $Profile
    } else {
        [ordered]@{}
    }
    foreach ($key in $overrideMap.Keys) {
        $effective[[string]$key] = $overrideMap[$key]
    }
    return $effective
}

function Resolve-MediaPipelineLibraryEffectiveSettingsForPath {
    param(
        [string] $SourcePath,
        [string] $LibraryProfileId = ''
    )

    $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $SourcePath -LibraryProfileId $LibraryProfileId
    if (-not $profile) { return Get-MediaPipelineLibraryDefaultConfigMap }
    $overrides = Get-MediaPipelineLibraryProfileOverrideMap -Profile $profile
    return Resolve-MediaPipelineLibraryEffectiveSettings -Profile $profile -Overrides $overrides
}

function Get-MediaPipelineActiveOverrideValue {
    param(
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    $active = ConvertTo-MediaPipelineProfileMap (Get-Variable -Name ActiveOverrides -Scope Script -ValueOnly -ErrorAction SilentlyContinue)
    if ($active.Contains($Name)) { return $active[$Name] }
    return $Default
}

function Push-MediaPipelineActiveConfigOverrides {
    param($Overrides)

    $map = ConvertTo-MediaPipelineProfileMap $Overrides
    $snapshot = [ordered]@{}
    foreach ($key in Get-MediaPipelineLibraryOverrideConfigKeys) {
        if (-not $map.Contains($key)) { continue }
        $existing = Get-Variable -Name $key -Scope Script -ErrorAction SilentlyContinue
        $snapshot[$key] = [ordered]@{
            Exists = ($null -ne $existing)
            Value = if ($null -ne $existing) { $existing.Value } else { $null }
        }
        Set-Variable -Name $key -Scope Script -Value $map[$key]
    }
    return $snapshot
}

function Pop-MediaPipelineActiveConfigOverrides {
    param($Snapshot)

    $map = ConvertTo-MediaPipelineProfileMap $Snapshot
    foreach ($key in $map.Keys) {
        $state = $map[$key]
        $exists = [bool](Get-MediaPipelineProfileProperty -Profile $state -Name 'Exists' -Default $false)
        if ($exists) {
            Set-Variable -Name ([string]$key) -Scope Script -Value (Get-MediaPipelineProfileProperty -Profile $state -Name 'Value')
        } else {
            Remove-Variable -Name ([string]$key) -Scope Script -ErrorAction SilentlyContinue
        }
    }
}
