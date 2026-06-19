# ==============================================================================
# ops\pipeline\engine\config\schema_validation.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\config\config_schema.ps1. Keep public function names
# and config key semantics stable; config_schema.ps1 dot-sources this file.
# ==============================================================================

function Test-MediaPipelineConfigHasKey {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key
    )

    if ($Config -is [System.Collections.IDictionary]) {
        return $Config.Contains($Key)
    }
    return $null -ne $Config.PSObject.Properties[$Key]
}

function ConvertTo-MediaPipelineConfigBool {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [bool] $Default = $false
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return $Default }
    $value = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    if ($value -is [bool]) { return [bool]$value }
    if ($null -eq $value) { return $Default }
    $text = ([string]$value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes','y','on')) { return $true }
    if ($text -in @('false','0','no','n','off')) { return $false }
    return $Default
}

function ConvertTo-MediaPipelineConfigMap {
    param($Value)

    $map = [ordered]@{}
    if ($null -eq $Value) { return $map }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in $Value.Keys) {
            if ($null -ne $key) { $map[[string]$key] = $Value[$key] }
        }
        return $map
    }
    foreach ($property in @($Value.PSObject.Properties)) {
        if ($property -and -not [string]::IsNullOrWhiteSpace([string]$property.Name)) {
            $map[[string]$property.Name] = $property.Value
        }
    }
    return $map
}

function Test-MediaPipelineConfigChoiceValue {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [Parameter(Mandatory)] [string] $Label,
        [Parameter(Mandatory)] [array] $AllowedValues,
        [switch] $AllowBlank,
        [System.Collections.Generic.List[string]] $Errors
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return }
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    $value = ([string]$raw).Trim().ToLowerInvariant()
    if ($AllowBlank -and [string]::IsNullOrWhiteSpace($value)) { return }
    $allowed = @($AllowedValues | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() })
    if ($value -notin $allowed) {
        $Errors.Add("$Label must be one of: $($allowed -join ', ').")
    }
}

function Test-MediaPipelineConfigIntegerRange {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [Parameter(Mandatory)] [string] $Label,
        [Nullable[int64]] $Minimum = $null,
        [Nullable[int64]] $Maximum = $null,
        [switch] $Optional,
        [System.Collections.Generic.List[string]] $Errors
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return }
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    if ($Optional -and ($null -eq $raw -or [string]::IsNullOrWhiteSpace([string]$raw))) { return }
    if (-not ($raw -is [byte] -or $raw -is [sbyte] -or $raw -is [int16] -or $raw -is [uint16] -or
              $raw -is [int] -or $raw -is [uint32] -or $raw -is [long] -or $raw -is [uint64])) {
        $Errors.Add("$Label must be an integer.")
        return
    }
    $number = [int64]$raw
    if ($null -ne $Minimum -and $number -lt [int64]$Minimum) {
        if ($null -ne $Maximum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at least $Minimum.")
        }
        return
    }
    if ($null -ne $Maximum -and $number -gt [int64]$Maximum) {
        if ($null -ne $Minimum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at most $Maximum.")
        }
    }
}

function Test-MediaPipelineConfigNumberRange {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [Parameter(Mandatory)] [string] $Label,
        [Nullable[double]] $Minimum = $null,
        [Nullable[double]] $Maximum = $null,
        [switch] $Optional,
        [System.Collections.Generic.List[string]] $Errors
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return }
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    if ($Optional -and ($null -eq $raw -or [string]::IsNullOrWhiteSpace([string]$raw))) { return }
    if (-not ($raw -is [byte] -or $raw -is [sbyte] -or $raw -is [int16] -or $raw -is [uint16] -or
              $raw -is [int] -or $raw -is [uint32] -or $raw -is [long] -or $raw -is [uint64] -or
              $raw -is [float] -or $raw -is [double] -or $raw -is [decimal])) {
        $Errors.Add("$Label must be numeric.")
        return
    }
    $number = [double]$raw
    if ($null -ne $Minimum -and $number -lt [double]$Minimum) {
        if ($null -ne $Maximum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at least $Minimum.")
        }
        return
    }
    if ($null -ne $Maximum -and $number -gt [double]$Maximum) {
        if ($null -ne $Minimum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at most $Maximum.")
        }
    }
}

function Test-MediaPipelineConfigPathIsFullyQualified {
    param([AllowNull()] [string] $Path)

    $text = ([string]$Path).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    try {
        return [System.IO.Path]::IsPathFullyQualified($text)
    } catch {
        if ($text -match '^[A-Za-z]:[\\/]' -or $text -match '^\\\\[^\\\/]+[\\\/][^\\\/]+') {
            return $true
        }
        return $false
    }
}

function Test-MediaPipelineConfigPathShape {
    param(
        [Parameter(Mandatory)] $Config,
        [System.Collections.Generic.List[string]] $Errors,
        [System.Collections.Generic.List[string]] $Warnings
    )

    $pathKeys = @('SourceMovies','SourceTV','Outsource','LocalBase')
    $normalized = @{}
    foreach ($key in $pathKeys) {
        if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $key)) { continue }
        $raw = [string](Get-MediaPipelineConfigValue -Config $Config -Key $key)
        if ([string]::IsNullOrWhiteSpace($raw)) {
            $Errors.Add("$key cannot be empty.")
            continue
        }
        if (-not (Test-MediaPipelineConfigPathIsFullyQualified -Path $raw)) {
            $Errors.Add("$key must be an absolute path.")
            continue
        }
        $normalized[$key] = Normalize-MediaPipelineConfigPathForCompare -Path $raw
    }

    foreach ($pair in @(
        @('LocalBase','Outsource'),
        @('LocalBase','SourceMovies'),
        @('LocalBase','SourceTV'),
        @('Outsource','SourceMovies'),
        @('Outsource','SourceTV')
    )) {
        $leftKey = $pair[0]
        $rightKey = $pair[1]
        if (-not $normalized.ContainsKey($leftKey) -or -not $normalized.ContainsKey($rightKey)) { continue }
        $left = [string]$normalized[$leftKey]
        $right = [string]$normalized[$rightKey]
        if ([string]::IsNullOrWhiteSpace($left) -or [string]::IsNullOrWhiteSpace($right)) { continue }
        if ($left -eq $right) {
            $Errors.Add("$leftKey and $rightKey must not point to the same path.")
        } elseif ($left.StartsWith($right + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or
                  $right.StartsWith($left + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            $Errors.Add("$leftKey and $rightKey must not be nested inside each other.")
        }
    }

    if ($normalized.ContainsKey('SourceMovies') -and $normalized.ContainsKey('SourceTV') -and
        [string]$normalized['SourceMovies'] -eq [string]$normalized['SourceTV']) {
        $Warnings.Add('SourceMovies and SourceTV point to the same location.')
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'LibraryProfiles') {
        $profiles = @(Get-MediaPipelineConfigValue -Config $Config -Key 'LibraryProfiles')
        $profileIds = @{}
        $profileSourceRoots = @{}
        foreach ($profile in $profiles) {
            if ($null -eq $profile) { continue }
            $id = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'id')
            $name = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'name')
            $label = if (-not [string]::IsNullOrWhiteSpace($name)) { $name } elseif (-not [string]::IsNullOrWhiteSpace($id)) { $id } else { 'Library profile' }
            if ([string]::IsNullOrWhiteSpace($id)) {
                $Errors.Add("$label is missing id.")
            } elseif ($profileIds.ContainsKey($id.ToLowerInvariant())) {
                $Errors.Add("Library profile id is duplicated: $id.")
            } else {
                $profileIds[$id.ToLowerInvariant()] = $true
            }

            $enabled = ConvertTo-MediaPipelineConfigBool -Config $profile -Key 'enabled' -Default $true
            $promotionEnabled = ConvertTo-MediaPipelineConfigBool -Config $profile -Key 'promotion_enabled' -Default $false
            $designation = ([string](Get-MediaPipelineConfigValue -Config $profile -Key 'designation')).Trim().ToLowerInvariant()
            if ($designation -in @('mixed','custom')) {
                $Warnings.Add("$label designation '$designation' is legacy; use auto.")
                $designation = 'auto'
            }
            if ($designation -notin @('movie','tv','auto')) {
                $Errors.Add("$label designation must be movie, tv, or auto.")
            }
            if ($id -in @('movies','tv') -and -not $enabled) {
                $Errors.Add("$label is a required default library and cannot be disabled.")
            }
            $sourcePath = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'source_path')
            $outputPath = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'output_path')
            $promotionDestination = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'promotion_destination')
            if ($enabled -and [string]::IsNullOrWhiteSpace($sourcePath)) {
                $Errors.Add("$label source_path cannot be empty.")
            }
            if ($enabled -and $promotionEnabled -and [string]::IsNullOrWhiteSpace($promotionDestination)) {
                $Errors.Add("$label promotion_destination cannot be empty when promotion is enabled.")
            }
            if ($enabled -and -not [string]::IsNullOrWhiteSpace($sourcePath)) {
                $sourceKey = Normalize-MediaPipelineConfigPathForCompare -Path $sourcePath
                if (-not [string]::IsNullOrWhiteSpace($sourceKey)) {
                    if ($profileSourceRoots.ContainsKey($sourceKey)) {
                        $Errors.Add("$label shares an enabled source root with $($profileSourceRoots[$sourceKey]).")
                    } else {
                        $profileSourceRoots[$sourceKey] = $label
                    }
                }
            }
            Test-MediaPipelineLibraryProfileOverrides -Config $Config -Profile $profile -Label $label -Errors $Errors -Warnings $Warnings
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key (Get-MediaPipelineConfigSchemaKey)) {
        $sameVolumeGroups = @{}
        foreach ($key in $pathKeys) {
            if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $key)) { continue }
            $raw = [string](Get-MediaPipelineConfigValue -Config $Config -Key $key)
            if ([string]::IsNullOrWhiteSpace($raw)) { continue }
            try {
                $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($raw))
                if ([string]::IsNullOrWhiteSpace($root)) { continue }
                $rootKey = $root.ToLowerInvariant()
                if (-not $sameVolumeGroups.ContainsKey($rootKey)) {
                    $sameVolumeGroups[$rootKey] = [System.Collections.Generic.List[string]]::new()
                }
                [void]$sameVolumeGroups[$rootKey].Add($key)
            } catch {}
        }
        foreach ($rootKey in $sameVolumeGroups.Keys) {
            $keys = @($sameVolumeGroups[$rootKey])
            if ($keys.Count -gt 1 -and $keys -contains 'LocalBase') {
                $Warnings.Add("LocalBase shares volume $rootKey with $($keys -join ', '); this is supported, but large copy/encode/publish bursts can contend for the same free space and I/O.")
            }
        }
    }
}

function Test-MediaPipelineConfigSubtitleToggles {
    param(
        [Parameter(Mandatory)] $Config,
        [System.Collections.Generic.List[string]] $Errors
    )

    $convertTx3g = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'ConvertTx3gToSrt' -Default $true
    $dropTx3g = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'DropTx3gAfterConversion' -Default $false
    $externalTx3g = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'CreateExternalTx3gSrtSidecars' -Default $false
    if (-not $convertTx3g -and $dropTx3g) {
        $Errors.Add('DropTx3gAfterConversion requires ConvertTx3gToSrt.')
    }
    if (-not $convertTx3g -and $externalTx3g) {
        $Errors.Add('CreateExternalTx3gSrtSidecars requires ConvertTx3gToSrt.')
    }

    $convertBdpgs = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'ConvertBdpgsToSrt' -Default $false
    $dropBdpgs = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'DropBdpgsAfterConversion' -Default $false
    if (-not $convertBdpgs -and $dropBdpgs) {
        $Errors.Add('DropBdpgsAfterConversion requires ConvertBdpgsToSrt.')
    }
    if ($convertBdpgs) {
        $toolPath = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'BdpgsOcrToolPath')
        if ([string]::IsNullOrWhiteSpace($toolPath)) {
            $Errors.Add('ConvertBdpgsToSrt requires BdpgsOcrToolPath.')
        }
    }

    $convertVobSub = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'ConvertVobSubToSrt' -Default $false
    $dropVobSub = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'DropVobSubAfterConversion' -Default $false
    if (-not $convertVobSub -and $dropVobSub) {
        $Errors.Add('DropVobSubAfterConversion requires ConvertVobSubToSrt.')
    }
    if ($convertVobSub) {
        $toolPath = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'VobSubOcrToolPath')
        if ([string]::IsNullOrWhiteSpace($toolPath)) {
            $Errors.Add('ConvertVobSubToSrt requires VobSubOcrToolPath.')
        }
    }
}

function Test-MediaPipelineConfigEncodeAudioPolicy {
    param(
        [Parameter(Mandatory)] $Config,
        [System.Collections.Generic.List[string]] $Errors,
        [System.Collections.Generic.List[string]] $Warnings
    )

    foreach ($optionPolicy in @(
        @{ Key = 'VideoCodec'; Label = 'VideoCodec'; Allowed = @(Get-MediaPipelineVideoCodecNames) },
        @{ Key = 'VideoPreset'; Label = 'VideoPreset'; Allowed = @(Get-MediaPipelineVideoPresetNames) },
        @{ Key = 'OutputContainer'; Label = 'OutputContainer'; Allowed = @(Get-MediaPipelineOutputContainerNames) },
        @{ Key = 'DynamicHdrPolicy'; Label = 'DynamicHdrPolicy'; Allowed = @(Get-MediaPipelineDynamicHdrPolicyNames); AllowBlank = $true },
        @{ Key = 'FinalLibraryPromotionVerificationMode'; Label = 'FinalLibraryPromotionVerificationMode'; Allowed = @(Get-MediaPipelineFinalLibraryPromotionVerificationModeNames); AllowBlank = $true },
        @{ Key = 'CpuEncodePreset'; Label = 'CpuEncodePreset'; Allowed = @(Get-MediaPipelineCpuEncodePresetNames); AllowBlank = $true },
        @{ Key = 'CpuEncodeProcessPriority'; Label = 'CpuEncodeProcessPriority'; Allowed = @(Get-MediaPipelineCpuEncodeProcessPriorityNames); AllowBlank = $true },
        @{ Key = 'ParallelEncodeMode'; Label = 'ParallelEncodeMode'; Allowed = @(Get-MediaPipelineParallelEncodeModeNames); AllowBlank = $true },
        @{ Key = 'EncodeWasteGuardMode'; Label = 'EncodeWasteGuardMode'; Allowed = @(Get-MediaPipelineEncodeWasteGuardModeNames); AllowBlank = $true }
    )) {
        $allowBlank = $false
        if ($optionPolicy.ContainsKey('AllowBlank')) {
            $allowBlank = [bool]$optionPolicy['AllowBlank']
        }
        Test-MediaPipelineConfigChoiceValue -Config $Config -Key ([string]$optionPolicy['Key']) -Label ([string]$optionPolicy['Label']) -AllowedValues @($optionPolicy['Allowed']) -AllowBlank:$allowBlank -Errors $Errors
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'EncodeTuningPreset') {
        $preset = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'EncodeTuningPreset')
        if ((Resolve-MediaPipelineEncodeTuningPreset -Preset $preset) -ne $preset.Trim().ToLowerInvariant()) {
            $Errors.Add("EncodeTuningPreset must be one of: $((Get-MediaPipelineEncodeTuningPresetNames) -join ', ').")
        }
    } elseif (Test-MediaPipelineConfigHasKey -Config $Config -Key 'ExtraVideoFlags') {
        $extra = @(Get-MediaPipelineConfigValue -Config $Config -Key 'ExtraVideoFlags')
        if ($extra.Count -gt 0) {
            $Warnings.Add('ExtraVideoFlags is present without EncodeTuningPreset; runtime will preserve it as custom_legacy_flags.')
        }
    }
    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'EncodeLadder') {
        $ladder = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'EncodeLadder')
        if ((Resolve-MediaPipelineEncodeLadder -Ladder $ladder) -ne $ladder.Trim().ToLowerInvariant()) {
            $Errors.Add("EncodeLadder must be one of: $((Get-MediaPipelineEncodeLadderNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'RoutingProfile') {
        $routingProfile = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'RoutingProfile')
        if ((Resolve-MediaPipelineRoutingProfile -Profile $routingProfile) -ne $routingProfile.Trim().ToLowerInvariant()) {
            $Errors.Add("RoutingProfile must be one of: $((Get-MediaPipelineRoutingProfileNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'RouteThresholdMode') {
        $routeThresholdMode = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'RouteThresholdMode')
        if ((Resolve-MediaPipelineRouteThresholdMode -Mode $routeThresholdMode) -ne $routeThresholdMode.Trim().ToLowerInvariant()) {
            $Errors.Add("RouteThresholdMode must be one of: $((Get-MediaPipelineRouteThresholdModeNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'SizeGuardMode') {
        $sizeGuardMode = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'SizeGuardMode')
        if ((Resolve-MediaPipelineSizeGuardMode -Mode $sizeGuardMode) -ne $sizeGuardMode.Trim().ToLowerInvariant()) {
            $Errors.Add("SizeGuardMode must be one of: $((Get-MediaPipelineSizeGuardModeNames) -join ', ').")
        }
    }

    foreach ($numericPolicy in @(
        @{ Kind = 'int'; Key = 'MovieRoute1080pTargetSizeGB'; Label = 'MovieRoute1080pTargetSizeGB'; Min = 1 },
        @{ Kind = 'int'; Key = 'MovieRoute1440pTargetSizeGB'; Label = 'MovieRoute1440pTargetSizeGB'; Min = 1 },
        @{ Kind = 'int'; Key = 'MovieRoute4KTargetSizeGB'; Label = 'MovieRoute4KTargetSizeGB'; Min = 1 },
        @{ Kind = 'int'; Key = 'TVRoute1080pTargetSizeGB'; Label = 'TVRoute1080pTargetSizeGB'; Min = 1 },
        @{ Kind = 'int'; Key = 'TVRoute1440pTargetSizeGB'; Label = 'TVRoute1440pTargetSizeGB'; Min = 1 },
        @{ Kind = 'int'; Key = 'TVRoute4KTargetSizeGB'; Label = 'TVRoute4KTargetSizeGB'; Min = 1 },
        @{ Kind = 'number'; Key = 'Route1080pUpperHeightTolerancePercent'; Label = 'Route1080pUpperHeightTolerancePercent'; Min = 0; Max = 100 },
        @{ Kind = 'int'; Key = 'Route1080pMaxVideoBitrateMbps'; Label = 'Route1080pMaxVideoBitrateMbps'; Min = 1; Max = 500 },
        @{ Kind = 'number'; Key = 'Route1440pLowerHeightTolerancePercent'; Label = 'Route1440pLowerHeightTolerancePercent'; Min = 0; Max = 100 },
        @{ Kind = 'number'; Key = 'Route1440pUpperHeightTolerancePercent'; Label = 'Route1440pUpperHeightTolerancePercent'; Min = 0; Max = 100 },
        @{ Kind = 'int'; Key = 'Route1440pMaxVideoBitrateMbps'; Label = 'Route1440pMaxVideoBitrateMbps'; Min = 1; Max = 500 },
        @{ Kind = 'number'; Key = 'Route4KLowerHeightTolerancePercent'; Label = 'Route4KLowerHeightTolerancePercent'; Min = 0; Max = 100 },
        @{ Kind = 'int'; Key = 'Route4KMaxVideoBitrateMbps'; Label = 'Route4KMaxVideoBitrateMbps'; Min = 1; Max = 500 },
        @{ Kind = 'int'; Key = 'H264RemuxMaxBitrateMbps'; Label = 'H264RemuxMaxBitrateMbps'; Min = 1; Max = 500 },
        @{ Kind = 'int'; Key = 'H264RemuxMaxHeight'; Label = 'H264RemuxMaxHeight'; Min = 1; Max = 4320 },
        @{ Kind = 'int'; Key = 'MaxEncodeGrowthPercent'; Label = 'MaxEncodeGrowthPercent'; Min = 0; Max = 1000 },
        @{ Kind = 'int'; Key = 'CompatibilityEncodeGrowthPercent'; Label = 'CompatibilityEncodeGrowthPercent'; Min = 0; Max = 1000 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardMinProgressPercent'; Label = 'EncodeWasteGuardMinProgressPercent'; Min = 0; Max = 95 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardMinElapsedSeconds'; Label = 'EncodeWasteGuardMinElapsedSeconds'; Min = 0; Max = 86400 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardOversizeMarginPercent'; Label = 'EncodeWasteGuardOversizeMarginPercent'; Min = 0; Max = 1000 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardConsecutiveSamples'; Label = 'EncodeWasteGuardConsecutiveSamples'; Min = 1; Max = 10 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardPollSeconds'; Label = 'EncodeWasteGuardPollSeconds'; Min = 1; Max = 600 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardPreflightSampleSeconds'; Label = 'EncodeWasteGuardPreflightSampleSeconds'; Min = 5; Max = 600 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardPreflightSampleCount'; Label = 'EncodeWasteGuardPreflightSampleCount'; Min = 1; Max = 10 },
        @{ Kind = 'int'; Key = 'EncodeWasteGuardPreflightTimeoutSeconds'; Label = 'EncodeWasteGuardPreflightTimeoutSeconds'; Min = 30; Max = 86400 },
        @{ Kind = 'int'; Key = 'MinFreeSpaceGB'; Label = 'MinFreeSpaceGB'; Min = 0 },
        @{ Kind = 'int'; Key = 'OutsourceMinFreeSpaceGB'; Label = 'OutsourceMinFreeSpaceGB'; Min = 0 },
        @{ Kind = 'int'; Key = 'VideoQuality'; Label = 'VideoQuality'; Min = 1; Max = 51 },
        @{ Kind = 'int'; Key = 'MergeThresholdMs'; Label = 'MergeThresholdMs'; Min = 0; Max = 5000 },
        @{ Kind = 'int'; Key = 'FFmpegEncodeTimeoutSeconds'; Label = 'FFmpegEncodeTimeoutSeconds'; Min = 1 },
        @{ Kind = 'int'; Key = 'FFmpegCpuEncodeTimeoutSeconds'; Label = 'FFmpegCpuEncodeTimeoutSeconds'; Min = 1 },
        @{ Kind = 'int'; Key = 'FFmpegRemuxTimeoutSeconds'; Label = 'FFmpegRemuxTimeoutSeconds'; Min = 1 },
        @{ Kind = 'int'; Key = 'MkvmergeRemuxTimeoutSeconds'; Label = 'MkvmergeRemuxTimeoutSeconds'; Min = 60; Max = 86400 },
        @{ Kind = 'int'; Key = 'SubtitleExtractTimeoutSeconds'; Label = 'SubtitleExtractTimeoutSeconds'; Min = 30; Max = 3600 },
        @{ Kind = 'int'; Key = 'SubtitleProbeTimeoutSeconds'; Label = 'SubtitleProbeTimeoutSeconds'; Min = 5; Max = 600 },
        @{ Kind = 'int'; Key = 'BdpgsOcrTimeoutSeconds'; Label = 'BdpgsOcrTimeoutSeconds'; Min = 60; Max = 14400 },
        @{ Kind = 'int'; Key = 'VobSubOcrTimeoutSeconds'; Label = 'VobSubOcrTimeoutSeconds'; Min = 60; Max = 14400 },
        @{ Kind = 'int'; Key = 'TransientFailureRetryLimit'; Label = 'TransientFailureRetryLimit'; Min = 1; Max = 100 },
        @{ Kind = 'int'; Key = 'SourceScanIntervalSeconds'; Label = 'SourceScanIntervalSeconds'; Min = 0 },
        @{ Kind = 'int'; Key = 'ProcessedIndexRefreshSeconds'; Label = 'ProcessedIndexRefreshSeconds'; Min = 0 },
        @{ Kind = 'int'; Key = 'RobocopyTimeoutSeconds'; Label = 'RobocopyTimeoutSeconds'; Min = 60; Max = 172800 },
        @{ Kind = 'int'; Key = 'SourceScanTimeoutSeconds'; Label = 'SourceScanTimeoutSeconds'; Min = 30; Max = 86400 },
        @{ Kind = 'int'; Key = 'IndexScanTimeoutSeconds'; Label = 'IndexScanTimeoutSeconds'; Min = 30; Max = 86400 },
        @{ Kind = 'int'; Key = 'CleanupScanTimeoutSeconds'; Label = 'CleanupScanTimeoutSeconds'; Min = 30; Max = 7200 },
        @{ Kind = 'int'; Key = 'CleanupStaleAgeHours'; Label = 'CleanupStaleAgeHours'; Min = 1; Max = 720 },
        @{ Kind = 'int'; Key = 'CpuEncodeMaxThreads'; Label = 'CpuEncodeMaxThreads'; Min = 0; Max = 256 },
        @{ Kind = 'int'; Key = 'FallbackCpuQuality'; Label = 'FallbackCpuQuality'; Min = 1; Max = 51; Optional = $true },
        @{ Kind = 'number'; Key = 'OutputSizeMultiplier'; Label = 'OutputSizeMultiplier'; Min = 0.1; Max = 2.0; Optional = $true }
    )) {
        $minimum = $null
        $maximum = $null
        $optional = $false
        if ($numericPolicy.ContainsKey('Min')) { $minimum = $numericPolicy['Min'] }
        if ($numericPolicy.ContainsKey('Max')) { $maximum = $numericPolicy['Max'] }
        if ($numericPolicy.ContainsKey('Optional')) { $optional = [bool]$numericPolicy['Optional'] }

        if ([string]$numericPolicy['Kind'] -eq 'number') {
            Test-MediaPipelineConfigNumberRange -Config $Config -Key ([string]$numericPolicy['Key']) -Label ([string]$numericPolicy['Label']) -Minimum $minimum -Maximum $maximum -Optional:$optional -Errors $Errors
        } else {
            Test-MediaPipelineConfigIntegerRange -Config $Config -Key ([string]$numericPolicy['Key']) -Label ([string]$numericPolicy['Label']) -Minimum $minimum -Maximum $maximum -Optional:$optional -Errors $Errors
        }
    }

    $heightTolerancePercentKeys = @(
        'Route1080pUpperHeightTolerancePercent',
        'Route1440pLowerHeightTolerancePercent',
        'Route1440pUpperHeightTolerancePercent',
        'Route4KLowerHeightTolerancePercent'
    )
    $hasHeightTolerancePercents = $false
    foreach ($key in $heightTolerancePercentKeys) {
        if (Test-MediaPipelineConfigHasKey -Config $Config -Key $key) {
            $hasHeightTolerancePercents = $true
            break
        }
    }

    if ($hasHeightTolerancePercents) {
        try {
            $route1080pUpperPct = if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'Route1080pUpperHeightTolerancePercent') { [double](Get-MediaPipelineConfigValue -Config $Config -Key 'Route1080pUpperHeightTolerancePercent') } else { 11.111111 }
            $route1440pLowerPct = if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'Route1440pLowerHeightTolerancePercent') { [double](Get-MediaPipelineConfigValue -Config $Config -Key 'Route1440pLowerHeightTolerancePercent') } else { 16.597222 }
            $route1440pUpperPct = if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'Route1440pUpperHeightTolerancePercent') { [double](Get-MediaPipelineConfigValue -Config $Config -Key 'Route1440pUpperHeightTolerancePercent') } else { 24.930556 }
            $route4kLowerPct = if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'Route4KLowerHeightTolerancePercent') { [double](Get-MediaPipelineConfigValue -Config $Config -Key 'Route4KLowerHeightTolerancePercent') } else { 16.666667 }
            $boundaries = Get-MediaPipelineConfigRouteHeightToleranceBoundaries `
                -Route1080pUpperHeightTolerancePercent $route1080pUpperPct `
                -Route1440pLowerHeightTolerancePercent $route1440pLowerPct `
                -Route1440pUpperHeightTolerancePercent $route1440pUpperPct `
                -Route4KLowerHeightTolerancePercent $route4kLowerPct
            if (-not $boundaries.IsContiguous) {
                $Errors.Add("Route height tolerance percents must create contiguous buckets: 1080p <= $($boundaries.Route1080pMaxHeight), 1440p $($boundaries.Route1440pMinHeight)-$($boundaries.Route1440pMaxHeight), 4K >= $($boundaries.Route4KMinHeight).")
            }
        } catch {
            # The numeric validator above reports malformed values.
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioPassthroughProfile') {
        $audioProfile = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioPassthroughProfile')
        if ((Resolve-MediaPipelineAudioPassthroughProfile -Profile $audioProfile) -ne $audioProfile.Trim().ToLowerInvariant()) {
            $Errors.Add("AudioPassthroughProfile must be one of: $((Get-MediaPipelineAudioPassthroughProfileNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioTranscodeCodec') {
        $codec = ([string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioTranscodeCodec')).Trim().ToLowerInvariant()
        if ($codec -notin @(Get-MediaPipelineAudioTranscodeCodecNames)) {
            $Errors.Add("AudioTranscodeCodec must be one of: $((Get-MediaPipelineAudioTranscodeCodecNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioTranscodeBitrate') {
        $bitrate = ([string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioTranscodeBitrate')).Trim().ToLowerInvariant()
        if ($bitrate -notmatch '^[1-9]\d*k$') {
            $Errors.Add('AudioTranscodeBitrate must use a positive ffmpeg bitrate value like 640k.')
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioDownmixMode') {
        $mode = ([string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioDownmixMode')).Trim().ToLowerInvariant()
        if ($mode -notin @(Get-MediaPipelineAudioDownmixModeNames)) {
            $Errors.Add("AudioDownmixMode must be one of: $((Get-MediaPipelineAudioDownmixModeNames) -join ', ').")
        }
    }

    Test-MediaPipelineConfigIntegerRange -Config $Config -Key 'AudioMaxChannels' -Label 'AudioMaxChannels' -Minimum 1 -Maximum 16 -Errors $Errors
}

function Resolve-MediaPipelineConfigSchemaVersion {
    param([Parameter(Mandatory)] $Config)

    $current = Get-MediaPipelineConfigCurrentSchemaVersion
    $schemaKey = Get-MediaPipelineConfigSchemaKey
    $warnings = [System.Collections.Generic.List[string]]::new()
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $schemaKey
    if ($null -eq $raw -or [string]::IsNullOrWhiteSpace([string]$raw)) {
        return [pscustomobject]@{
            EffectiveSchemaVersion = $current
            DeclaredSchemaVersion  = $null
            CurrentSchemaVersion   = $current
            Warnings               = @()
        }
    }

    try {
        $declared = [int]$raw
    } catch {
        $warnings.Add("ConfigSchemaVersion '$raw' is not an integer; using schema $current compatibility.")
        return [pscustomobject]@{
            EffectiveSchemaVersion = $current
            DeclaredSchemaVersion  = $raw
            CurrentSchemaVersion   = $current
            Warnings               = @($warnings)
        }
    }

    if ($declared -lt 1) {
        $warnings.Add("ConfigSchemaVersion $declared is invalid; using schema $current compatibility.")
        $declared = $current
    } elseif ($declared -lt $current) {
        $warnings.Add("ConfigSchemaVersion $declared is older than current schema $current; loading through compatibility mode.")
    } elseif ($declared -gt $current) {
        $warnings.Add("ConfigSchemaVersion $declared is newer than this pipeline understands ($current); loading with current compatibility checks.")
        $declared = $current
    }

    return [pscustomobject]@{
        EffectiveSchemaVersion = $declared
        DeclaredSchemaVersion  = $raw
        CurrentSchemaVersion   = $current
        Warnings               = @($warnings)
    }
}
