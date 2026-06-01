# ==============================================================================
# engine\paths\output_path_planning.ps1
# ==============================================================================
# Output destination planning and path capability checks.
#
# Dot-sourced by the engine entrypoints and legacy compatibility loaders. These
# helpers read path and naming configuration from script scope at call time.
# ==============================================================================

function Get-MediaPipelineLibraryProfiles {
    $profiles = @()
    $configured = Get-Variable -Name LibraryProfiles -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    if ($configured) {
        $profiles = @($configured)
    }

    if (@($profiles).Count -le 0) {
        $profiles = @(
            [pscustomobject]@{
                id = 'movies'
                name = 'Movies'
                enabled = $true
                designation = 'movie'
                source_path = [string]$SourceMovies
                output_path = [string]$Outsource
                promotion_enabled = $false
                promotion_destination = ''
            },
            [pscustomobject]@{
                id = 'tv'
                name = 'TV'
                enabled = $true
                designation = 'tv'
                source_path = [string]$SourceTV
                output_path = [string]$Outsource
                promotion_enabled = $false
                promotion_destination = ''
            }
        )
    }

    return @($profiles)
}

function Get-MediaPipelineProfileProperty {
    param(
        [Parameter(Mandatory)] $Profile,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($Profile -is [System.Collections.IDictionary] -and $Profile.Contains($Name)) {
        return $Profile[$Name]
    }
    $prop = $Profile.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function ConvertTo-MediaPipelineProfileMap {
    param($Value)

    $map = [ordered]@{}
    if ($null -eq $Value) { return $map }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in $Value.Keys) {
            $map[[string]$key] = $Value[$key]
        }
        return $map
    }
    foreach ($prop in @($Value.PSObject.Properties)) {
        if (-not $prop) { continue }
        $map[[string]$prop.Name] = $prop.Value
    }
    return $map
}

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
        'MovieRouteMaxVideoBitrateMbps',
        'TVRouteMaxVideoBitrateMbps',
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
        'MovieRouteMaxVideoBitrateMbps',
        'TVRouteMaxVideoBitrateMbps',
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

function Get-MediaPipelineOutputContainerPlanningEvidence {
    param(
        $LibraryOverrides = $null,
        $RuntimeEffectiveSettings = $null,
        [string] $LibraryOutputRoot = '',
        [string] $LibrarySourceRoot = '',
        [string] $DefaultOutputContainer = ''
    )

    $overrideMap = ConvertTo-MediaPipelineProfileMap $LibraryOverrides
    $defaultContainer = if ([string]::IsNullOrWhiteSpace($DefaultOutputContainer)) { [string]$OutputContainer } else { [string]$DefaultOutputContainer }
    $containerValue = $defaultContainer
    $sourceLayer = 'global'
    $overrode = @()
    if ($overrideMap.Contains('OutputContainer')) {
        $containerValue = [string]$overrideMap['OutputContainer']
        $sourceLayer = 'library'
        $overrode = @('global')
    }
    $effectiveValues = [ordered]@{}
    if ($null -ne $RuntimeEffectiveSettings) {
        $effectiveValues = ConvertTo-MediaPipelineProfileMap (Get-MediaPipelineProfileProperty -Profile $RuntimeEffectiveSettings -Name 'effective_values' -Default $null)
    }
    if ($effectiveValues.Contains('OutputContainer')) {
        $entry = $effectiveValues['OutputContainer']
        $containerValue = [string](Get-MediaPipelineProfileProperty -Profile $entry -Name 'value' -Default $containerValue)
        $sourceLayer = [string](Get-MediaPipelineProfileProperty -Profile $entry -Name 'source_layer' -Default $sourceLayer)
        $overrode = @((Get-MediaPipelineProfileProperty -Profile $entry -Name 'overrode' -Default $overrode) | ForEach-Object { [string]$_ })
    }
    $folderFileSupported = ($sourceLayer -in @('folder','file'))

    return [ordered]@{
        schema                                         = 'runtime_consumer_settings.v1'
        consumer                                       = 'container_path_planning'
        diagnostic_only                                = $true
        evidence_source                                = 'path_planning'
        library_output_root                            = [string]$LibraryOutputRoot
        library_source_root                            = [string]$LibrarySourceRoot
        planned_output_root                            = [string]$LibraryOutputRoot
        planned_output_path_available                  = $false
        planned_output_path_note                       = 'Full output path is produced by Get-OutputPaths; this evidence records the selected container/root policy.'
        folder_file_output_container_override_supported = [bool]$folderFileSupported
        warning                                        = if ($folderFileSupported) { '' } else { 'OutputContainer path planning uses global/library state unless a runtime folder/file override is active.' }
        settings                                       = [ordered]@{
            OutputContainer = [ordered]@{
                value           = $containerValue
                source_layer    = $sourceLayer
                overrode        = @($overrode)
                decision_scope  = 'container_path_planning'
                decision_impact = if ($folderFileSupported) { 'sets planned output extension through active runtime overrides' } else { 'sets planned output extension before folder/file layers' }
                consequence     = 'planned output path extension'
                available       = $true
            }
        }
    }
}

function New-MediaPipelineSizeGuardEvidence {
    param(
        $RuntimeEffectiveSettings = $null,
        $SizePolicyResult = $null,
        $RoutePlan = $null
    )

    $sizeKeys = @(
        'SizeGuardMode',
        'EncodeThresholdGB',
        'TVEncodeThresholdGB',
        'MaxEncodeGrowthPercent',
        'CompatibilityEncodeGrowthPercent'
    )
    $settingsEvidence = if ($null -ne $RuntimeEffectiveSettings) {
        New-MediaPipelineRuntimeConsumerSettingsEvidence `
            -RuntimeEffectiveSettings $RuntimeEffectiveSettings `
            -Consumer 'size_guard' `
            -Keys $sizeKeys `
            -DecisionScope 'post_encode_size_guard' `
            -ActionEvidence 'checked after encode; does not participate in direct-copy bitrate gates' `
            -DecisionImpact ([ordered]@{
                SizeGuardMode = 'post_encode_outcome_policy'
                EncodeThresholdGB = 'output_size_target_budget'
                TVEncodeThresholdGB = 'output_size_target_budget'
                MaxEncodeGrowthPercent = 'quality_encode_size_tolerance'
                CompatibilityEncodeGrowthPercent = 'compatibility_encode_size_tolerance'
            })
    } else {
        [ordered]@{
            schema          = 'runtime_consumer_settings.v1'
            consumer        = 'size_guard'
            diagnostic_only = $true
            evidence_source = 'runtime_effective_settings.v1'
            action_selected = ''
            action_evidence = 'runtime effective settings unavailable'
            settings        = [ordered]@{}
            unsupported_keys = @()
            ignored_keys     = @()
            warnings         = @('runtime effective settings unavailable')
        }
    }

    $policy = $SizePolicyResult
    if ($null -ne $policy -and $policy.PSObject.Properties['Metadata']) {
        $policy = $policy.Metadata
    }
    $hasPolicy = ($null -ne $policy)
    $mode = if ($hasPolicy) { [string](Get-MediaPipelineProfileProperty -Profile $policy -Name 'mode' -Default '') } else { '' }
    $exceeded = if ($hasPolicy) { [bool](Get-MediaPipelineProfileProperty -Profile $policy -Name 'exceeded' -Default $false) } else { $false }
    $enforced = if ($hasPolicy) { [bool](Get-MediaPipelineProfileProperty -Profile $policy -Name 'enforced' -Default $false) } else { $false }
    $outcome = if (-not $hasPolicy) {
        'not_available'
    } elseif ($exceeded -and $enforced) {
        'block'
    } elseif ($exceeded) {
        'warn'
    } else {
        'pass'
    }
    $strictness = if (-not $hasPolicy) {
        'computed'
    } elseif ($mode -eq 'strict') {
        'hard'
    } elseif ($mode -eq 'off') {
        'advisory'
    } else {
        'advisory'
    }

    $routeIsTV = if ($null -ne $RoutePlan) { [bool](Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'IsTV' -Default $false) } else { $false }
    $targetKey = if ($routeIsTV) { 'TVEncodeThresholdGB' } else { 'EncodeThresholdGB' }
    $targetSizeGB = $null
    $settingMap = ConvertTo-MediaPipelineProfileMap $settingsEvidence['settings']
    if ($settingMap.Contains($targetKey)) {
        $targetSizeGB = Get-MediaPipelineProfileProperty -Profile $settingMap[$targetKey] -Name 'value' -Default $null
    }

    return [ordered]@{
        schema                       = 'size_guard_evidence.v1'
        diagnostic_only              = $true
        available                    = $hasPolicy
        mode                         = $mode
        strictness                   = $strictness
        outcome                      = $outcome
        checked_after_encode         = $true
        settings                     = $settingsEvidence
        target_size_key              = $targetKey
        target_size_gb               = $targetSizeGB
        route_threshold_gb           = if ($null -ne $RoutePlan) { Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'ThresholdGB' -Default $null } else { $null }
        estimated_bitrate_mbps       = if ($null -ne $RoutePlan) { Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'EstimatedBitrateMbps' -Default $null } else { $null }
        bitrate_gate_mbps            = if ($null -ne $RoutePlan) { Get-MediaPipelineProfileProperty -Profile $RoutePlan -Name 'BitrateThresholdMbps' -Default $null } else { $null }
        source_size_bytes            = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'source_size_bytes' -Default 0L } else { 0L }
        output_size_bytes            = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'output_size_bytes' -Default 0L } else { 0L }
        growth_percent_used          = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'max_growth_percent' -Default $null } else { $null }
        limit_ratio                  = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'limit_ratio' -Default $null } else { $null }
        ratio                        = if ($hasPolicy) { Get-MediaPipelineProfileProperty -Profile $policy -Name 'ratio' -Default $null } else { $null }
        exceeded                     = $exceeded
        enforced                     = $enforced
        route_reason_code            = if ($hasPolicy) { [string](Get-MediaPipelineProfileProperty -Profile $policy -Name 'route_reason_code' -Default '') } else { '' }
        message                      = if ($hasPolicy) { [string](Get-MediaPipelineProfileProperty -Profile $policy -Name 'message' -Default '') } else { 'size guard evidence unavailable before encode output is checked' }
        distinction_note             = 'GB target settings are output size budgets checked after encode; Mbps values are routing bitrate gates used before processing.'
    }
}

function New-MediaPipelinePublishEvidence {
    param(
        $PublishResult = $null,
        [string] $Route = ''
    )

    $hasPublishResult = ($null -ne $PublishResult)
    $publishState = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'PublishState' -Default '') } else { '' }
    $publishMode = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'PublishMode' -Default '') } else { '' }
    $ok = if ($hasPublishResult) { [bool](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'Ok' -Default $false) } else { $false }
    $reason = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'Reason' -Default '') } else { '' }
    $deferred = ($publishState -eq 'pending_publish' -or $publishMode -match 'deferred')
    $attempted = ($hasPublishResult -and (-not [string]::IsNullOrWhiteSpace($publishState) -or -not [string]::IsNullOrWhiteSpace($publishMode)))
    $outcome = if (-not $attempted) {
        'not_attempted'
    } elseif ($ok -and $deferred) {
        'deferred'
    } elseif ($ok) {
        'published'
    } else {
        'failed'
    }

    return [ordered]@{
        schema                  = 'publish_evidence.v1'
        diagnostic_only         = $true
        route                   = [string]$Route
        attempted               = $attempted
        allowed                 = ($attempted -and $ok)
        blocked                 = ($attempted -and -not $ok)
        deferred                = $deferred
        outcome                 = $outcome
        publish_state           = $publishState
        publish_mode            = $publishMode
        output_path             = if ($hasPublishResult) { [string](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'OutputPath' -Default '') } else { '' }
        output_size_bytes       = if ($hasPublishResult) { [long](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'OutputSizeBytes' -Default 0L) } else { 0L }
        reason                  = $reason
        parked_for_output_space = if ($hasPublishResult) { [bool](Get-MediaPipelineProfileProperty -Profile $PublishResult -Name 'ParkedForOutputSpace' -Default $false) } else { $false }
        pending_publish_status  = if ($deferred) { 'pending drain through existing pending-publish flow' } else { '' }
    }
}

function New-MediaPipelineVerificationEvidence {
    param(
        $SizeGuardEvidence = $null,
        $PublishEvidence = $null
    )

    $checks = New-Object System.Collections.Generic.List[string]
    $warnings = New-Object System.Collections.Generic.List[string]
    $blockingFailures = New-Object System.Collections.Generic.List[string]
    if ($null -ne $SizeGuardEvidence -and [bool]$SizeGuardEvidence['available']) {
        [void]$checks.Add('size_guard')
        $sizeOutcome = [string]$SizeGuardEvidence['outcome']
        if ($sizeOutcome -eq 'warn') { [void]$warnings.Add('size_guard_warning') }
        if ($sizeOutcome -eq 'block') { [void]$blockingFailures.Add('size_guard_block') }
    }
    if ($null -ne $PublishEvidence -and [bool]$PublishEvidence['attempted']) {
        [void]$checks.Add('publish_result')
        if ([bool]$PublishEvidence['blocked']) { [void]$blockingFailures.Add('publish_failed_or_blocked') }
        if ([bool]$PublishEvidence['deferred']) { [void]$warnings.Add('publish_deferred_pending_drain') }
    }
    $result = if ($blockingFailures.Count -gt 0) {
        'failed'
    } elseif ($warnings.Count -gt 0) {
        'warning'
    } elseif ($checks.Count -gt 0) {
        'passed'
    } else {
        'not_available'
    }

    return [ordered]@{
        schema            = 'verification_evidence.v1'
        diagnostic_only   = $true
        checks_run        = @($checks)
        result            = $result
        warnings          = @($warnings)
        blocking_failures = @($blockingFailures)
        size_guard_ref    = if ($null -ne $SizeGuardEvidence) { [string]$SizeGuardEvidence['schema'] } else { '' }
        publish_ref       = if ($null -ne $PublishEvidence) { [string]$PublishEvidence['schema'] } else { '' }
        note              = 'Diagnostic summary only; verification, size guard, publish, and drain logic remain owned by existing runtime code.'
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

function Test-MediaPipelinePathUnderRoot {
    param(
        [string] $Path,
        [string] $Root
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) { return $false }
    if (Get-Command -Name Test-MediaPipelinePathIsEqualOrChild -ErrorAction SilentlyContinue) {
        return Test-MediaPipelinePathIsEqualOrChild -Path $Path -Root $Root
    }
    try {
        $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\','/')
        $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\','/')
        if ($pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        return $pathFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        return $false
    }
}

function Test-MediaPipelineLibraryProfileEnabled {
    param($Profile)

    $enabled = Get-MediaPipelineProfileProperty -Profile $Profile -Name 'enabled' -Default $true
    if ($enabled -is [string]) {
        $enabled = $enabled.Trim().ToLowerInvariant() -notin @('false','0','no','off','disabled')
    }
    return [bool]$enabled
}

function Get-MediaPipelineLibraryProfileById {
    param([string] $LibraryProfileId)

    if ([string]::IsNullOrWhiteSpace($LibraryProfileId)) { return $null }
    $target = $LibraryProfileId.Trim().ToLowerInvariant()
    foreach ($profile in Get-MediaPipelineLibraryProfiles) {
        $profileId = ([string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'id' -Default '')).Trim().ToLowerInvariant()
        if ($profileId -eq $target) { return $profile }
    }
    return $null
}

function Get-MediaPipelineSelectedLibraryProfileId {
    $selected = Get-Variable -Name CurrentLibraryProfileId -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    if ($null -eq $selected) { return '' }
    return [string]$selected
}

function Get-MediaPipelineLibraryProfileForPath {
    param(
        [string] $SourcePath,
        [string] $LibraryProfileId = ''
    )

    $selectedId = if ([string]::IsNullOrWhiteSpace($LibraryProfileId)) { Get-MediaPipelineSelectedLibraryProfileId } else { $LibraryProfileId }
    if (-not [string]::IsNullOrWhiteSpace($selectedId)) {
        $selectedProfile = Get-MediaPipelineLibraryProfileById -LibraryProfileId $selectedId
        if ($selectedProfile -and (Test-MediaPipelineLibraryProfileEnabled -Profile $selectedProfile)) {
            $selectedRoot = [string](Get-MediaPipelineProfileProperty -Profile $selectedProfile -Name 'source_path' -Default '')
            if (-not [string]::IsNullOrWhiteSpace($selectedRoot) -and (Test-MediaPipelinePathUnderRoot -Path $SourcePath -Root $selectedRoot)) {
                return $selectedProfile
            }
        }
    }

    $matches = @()
    foreach ($profile in Get-MediaPipelineLibraryProfiles) {
        if (-not (Test-MediaPipelineLibraryProfileEnabled -Profile $profile)) { continue }
        $sourceRoot = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'source_path' -Default '')
        if ([string]::IsNullOrWhiteSpace($sourceRoot)) { continue }
        if (Test-MediaPipelinePathUnderRoot -Path $SourcePath -Root $sourceRoot) {
            $matches += [pscustomobject]@{ Profile = $profile; SourceRoot = $sourceRoot }
        }
    }
    if (@($matches).Count -le 0) { return $null }
    return (@($matches) | Sort-Object @{ Expression = { ([string]$_.SourceRoot).Length }; Descending = $true } | Select-Object -First 1).Profile
}

function Get-MediaPipelineLibraryOutputRootForPath {
    param([string] $SourcePath)

    $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $SourcePath
    if ($profile) {
        $outputRoot = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'output_path' -Default '')
        if (-not [string]::IsNullOrWhiteSpace($outputRoot)) { return $outputRoot }
    }
    return [string]$Outsource
}

function Get-MediaPipelineLibraryProfileEvidenceForPath {
    param(
        [string] $SourcePath,
        [string] $LibraryProfileId = ''
    )

    $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $SourcePath -LibraryProfileId $LibraryProfileId
    if (-not $profile) {
        return [ordered]@{
            library_id = ''
            library_name = ''
            designation = ''
            source_root = ''
            output_root = [string]$Outsource
            promotion_enabled = $false
            promotion_destination_root = ''
            promotion_rule_id = ''
            promotion_rule_source = 'disabled'
            settings_override_keys = @()
            settings_overrides = [ordered]@{}
            effective_settings = Get-MediaPipelineLibraryDefaultConfigMap
        }
    }
    $settingsOverrides = Get-MediaPipelineLibraryProfileOverrideMap -Profile $profile
    $effectiveSettings = Resolve-MediaPipelineLibraryEffectiveSettings -Profile $profile -Overrides $settingsOverrides
    $profileId = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'id' -Default '')
    $promotionEnabledValue = Get-MediaPipelineProfileProperty -Profile $profile -Name 'promotion_enabled' -Default $false
    if ($promotionEnabledValue -is [string]) {
        $promotionEnabledValue = $promotionEnabledValue.Trim().ToLowerInvariant() -in @('true','1','yes','on','enabled')
    }
    $promotionEnabled = [bool]$promotionEnabledValue
    $promotionDestinationRoot = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'promotion_destination' -Default '')
    $promotionRuleId = ''
    $promotionRuleSource = 'disabled'
    if ($promotionEnabled) {
        if (-not [string]::IsNullOrWhiteSpace($promotionDestinationRoot)) {
            $promotionRuleId = "library-profile-$profileId"
            $promotionRuleSource = 'profile_derived'
        } else {
            $promotionRuleSource = 'missing_destination'
        }
    }
    return [ordered]@{
        library_id = $profileId
        library_name = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'name' -Default '')
        designation = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'designation' -Default '')
        source_root = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'source_path' -Default '')
        output_root = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'output_path' -Default $Outsource)
        promotion_enabled = $promotionEnabled
        promotion_destination_root = $promotionDestinationRoot
        promotion_rule_id = $promotionRuleId
        promotion_rule_source = $promotionRuleSource
        settings_override_keys = @($settingsOverrides.Keys)
        settings_overrides = $settingsOverrides
        effective_settings = $effectiveSettings
    }
}

function Get-OutputPaths {
    param($File, [bool]$isTV, $tvInfo, [string]$SafeName)
    $libraryOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath ([string]$File.FullName)
    $activeOutputContainer = Get-MediaPipelineActiveOverrideValue -Name 'OutputContainer' -Default $null
    $effectiveOutputContainer = if (-not [string]::IsNullOrWhiteSpace([string]$activeOutputContainer)) {
        [string]$activeOutputContainer
    } elseif ($libraryOverrides.Contains('OutputContainer')) {
        [string]$libraryOverrides['OutputContainer']
    } else {
        [string]$OutputContainer
    }
    if ($isTV) {
        $plan = New-PlexDestinationPlan -MediaKind 'TV' -File $File -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension $effectiveOutputContainer -IncludeLibraryFolder:$CreateTVSubfolder
    } else {
        $plan = New-PlexDestinationPlan -MediaKind 'Movie' -File $File -OriginalName $File.Name -Extension $effectiveOutputContainer
    }

    $localDir  = Join-Path $LocalEncoded $plan.RelativeDirectory
    $libraryEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath ([string]$File.FullName)
    $outputRoot = [string]$libraryEvidence['output_root']
    if ([string]::IsNullOrWhiteSpace($outputRoot)) { $outputRoot = [string]$Outsource }
    $serverDir = Join-Path $outputRoot $plan.RelativeDirectory
    return @{
        LocalDir=$localDir; LocalOut=Join-Path $localDir $plan.FileName
        ServerDir=$serverDir; ServerOut=Join-Path $serverDir $plan.FileName
        PlexPlan=$plan; RelativePath=$plan.RelativePath; OutputRoot=$outputRoot
        LibraryProfileId=$libraryEvidence['library_id']; LibraryName=$libraryEvidence['library_name']
        LibraryDesignation=$libraryEvidence['designation']; LibrarySourceRoot=$libraryEvidence['source_root']
        LibrarySettingsOverrideKeys=$libraryEvidence['settings_override_keys']
        LibrarySettingsOverrides=$libraryEvidence['settings_overrides']
        LibraryEffectiveSettings=$libraryEvidence['effective_settings']
    }
}

function Test-PathComponentSupport {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [int] $MaxComponentLength = 255
    )

    try {
        [System.IO.Path]::GetFullPath($Path) | Out-Null
        $root = [System.IO.Path]::GetPathRoot($Path)
        $rest = if ($root -and $Path.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
            $Path.Substring($root.Length)
        } else {
            $Path
        }
        foreach ($segment in ($rest -split '[\\/]+')) {
            if ([string]::IsNullOrWhiteSpace($segment)) { continue }
            if ($segment.Length -gt $MaxComponentLength) {
                $preview = if ($segment.Length -gt 80) { $segment.Substring(0, 80) + '...' } else { $segment }
                return "path component is $($segment.Length) characters (limit $MaxComponentLength): $preview"
            }
        }
        return $null
    } catch {
        return "path is not valid: $($_.Exception.Message)"
    }
}

function Test-OutputPathCapability {
    param(
        [Parameter(Mandatory)] $Paths
    )

    foreach ($target in @(
        @{ Label = 'local output';  Path = [string]$Paths.LocalOut;  Required = $true },
        @{ Label = 'server output'; Path = [string]$Paths.ServerOut; Required = $false }
    )) {
        $label = [string]$target.Label
        $path = [string]$target.Path
        $required = [bool]$target.Required
        if ([string]::IsNullOrWhiteSpace($path)) {
            return @{ Ok = $false; Reason = "$label path is empty"; Path = $path }
        }

        $componentError = Test-PathComponentSupport -Path $path
        if ($componentError) {
            return @{ Ok = $false; Reason = "$label $componentError"; Path = $path }
        }

        $dir = Split-Path $path -Parent
        if ([string]::IsNullOrWhiteSpace($dir)) {
            return @{ Ok = $false; Reason = "$label has no parent directory"; Path = $path }
        }

        $createdDir = $false
        $probe = $null
        try {
            if (-not (Test-Path -LiteralPath $dir -ErrorAction SilentlyContinue)) {
                New-Item -ItemType Directory -Path $dir -Force -ErrorAction Stop | Out-Null
                $createdDir = $true
            }
            $probe = Join-Path $dir (".mediapipeline-pathprobe." + [guid]::NewGuid().ToString("N") + ".tmp")
            [System.IO.File]::WriteAllText($probe, "probe", [System.Text.UTF8Encoding]::new($false))
            Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
            $probe = $null
            if ($createdDir) {
                Remove-Item -LiteralPath $dir -Force -ErrorAction SilentlyContinue
            }
        } catch {
            if ($probe -and (Test-Path -LiteralPath $probe -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
            }
            if ($createdDir) {
                Remove-Item -LiteralPath $dir -Force -ErrorAction SilentlyContinue
            }
            $reason = "$label path is not writable/creatable now: $($_.Exception.Message)"
            if (-not $required) {
                Write-Log "Output path preflight: $reason. Publish/parking will handle this later." "WARN"
                continue
            }
            return @{ Ok = $false; Reason = $reason; Path = $path }
        }
    }

    return @{ Ok = $true; Reason = ''; Path = '' }
}
