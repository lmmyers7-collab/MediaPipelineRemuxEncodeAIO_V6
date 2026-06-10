# ==============================================================================
# ops\pipeline\engine\paths\library_profiles.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\paths\output_path_planning.ps1. Keep function names
# stable; output_path_planning.ps1 dot-sources this file as the public surface.
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

function Test-MediaPipelineLibraryProfileEnabled {
    param($Profile)

    $enabled = Get-MediaPipelineProfileProperty -Profile $Profile -Name 'enabled' -Default $true
    if ($enabled -is [string]) {
        $enabled = $enabled.Trim().ToLowerInvariant() -notin @('false','0','no','off','disabled','disable')
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
        $promotionEnabledValue = $promotionEnabledValue.Trim().ToLowerInvariant() -in @('true','1','yes','on','enabled','enable')
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
