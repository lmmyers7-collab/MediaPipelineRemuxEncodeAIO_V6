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
    param([string] $SourcePath)

    $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $SourcePath
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
    param([string] $SourcePath)

    $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $SourcePath
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

function Get-MediaPipelineLibraryProfileForPath {
    param([string] $SourcePath)

    $matches = @()
    foreach ($profile in Get-MediaPipelineLibraryProfiles) {
        $enabled = Get-MediaPipelineProfileProperty -Profile $profile -Name 'enabled' -Default $true
        if ($enabled -is [string]) {
            $enabled = $enabled.Trim().ToLowerInvariant() -notin @('false','0','no','off','disabled')
        }
        if (-not [bool]$enabled) { continue }
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
    param([string] $SourcePath)

    $profile = Get-MediaPipelineLibraryProfileForPath -SourcePath $SourcePath
    if (-not $profile) {
        return [ordered]@{
            library_id = ''
            library_name = ''
            designation = ''
            source_root = ''
            output_root = [string]$Outsource
            settings_override_keys = @()
            settings_overrides = [ordered]@{}
            effective_settings = Get-MediaPipelineLibraryDefaultConfigMap
        }
    }
    $settingsOverrides = Get-MediaPipelineLibraryProfileOverrideMap -Profile $profile
    $effectiveSettings = Resolve-MediaPipelineLibraryEffectiveSettings -Profile $profile -Overrides $settingsOverrides
    return [ordered]@{
        library_id = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'id' -Default '')
        library_name = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'name' -Default '')
        designation = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'designation' -Default '')
        source_root = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'source_path' -Default '')
        output_root = [string](Get-MediaPipelineProfileProperty -Profile $profile -Name 'output_path' -Default $Outsource)
        settings_override_keys = @($settingsOverrides.Keys)
        settings_overrides = $settingsOverrides
        effective_settings = $effectiveSettings
    }
}

function Get-OutputPaths {
    param($File, [bool]$isTV, $tvInfo, [string]$SafeName)
    $libraryOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath ([string]$File.FullName)
    $effectiveOutputContainer = if ($libraryOverrides.Contains('OutputContainer')) { [string]$libraryOverrides['OutputContainer'] } else { [string]$OutputContainer }
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
