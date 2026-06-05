# ==============================================================================
# ops\pipeline\engine\config\library_overrides.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\config\config_schema.ps1. Keep public function names
# and config key semantics stable; config_schema.ps1 dot-sources this file.
# ==============================================================================

function Normalize-MediaPipelineConfigPathForCompare {
    param([string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $trimmed = $Path.Trim().Trim('"').Trim("'").TrimEnd('\','/')
    if ([string]::IsNullOrWhiteSpace($trimmed)) { return '' }
    try {
        return [System.IO.Path]::GetFullPath($trimmed).TrimEnd('\','/').ToLowerInvariant()
    } catch {
        return $trimmed.ToLowerInvariant()
    }
}

function Add-MediaPipelineLibraryOverrideValuesToMap {
    param(
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Target,
        $Values
    )

    if ($null -eq $Values) { return }
    if ($Values -is [System.Collections.IDictionary]) {
        foreach ($key in $Values.Keys) {
            if ($null -ne $key) { $Target[[string]$key] = $Values[$key] }
        }
        return
    }
    foreach ($property in @($Values.PSObject.Properties)) {
        if ($property -and -not [string]::IsNullOrWhiteSpace([string]$property.Name)) {
            $Target[[string]$property.Name] = $property.Value
        }
    }
}

function Get-MediaPipelineLibraryProfileOverrideValues {
    param($Profile)

    $values = [ordered]@{}
    $overrides = Get-MediaPipelineConfigValue -Config $Profile -Key 'overrides'
    foreach ($group in @('editor','video','subtitles','subtitle','audio')) {
        if ($overrides) {
            Add-MediaPipelineLibraryOverrideValuesToMap -Target $values -Values (Get-MediaPipelineConfigValue -Config $overrides -Key $group)
        }
    }
    Add-MediaPipelineLibraryOverrideValuesToMap -Target $values -Values (Get-MediaPipelineConfigValue -Config $Profile -Key 'editor_overrides')
    Add-MediaPipelineLibraryOverrideValuesToMap -Target $values -Values (Get-MediaPipelineConfigValue -Config $Profile -Key 'media_overrides')
    return $values
}

function Get-MediaPipelineLibraryProfileOverrideKeyErrors {
    param(
        [Parameter(Mandatory)] $Profile,
        [Parameter(Mandatory)] [string] $Label
    )

    $errors = New-Object System.Collections.Generic.List[string]
    $keysByGroup = Get-MediaPipelineConfigLibraryOverrideKeysByGroup
    $allKeys = @(Get-MediaPipelineConfigLibraryOverrideKeys)
    $rawOverrides = Get-MediaPipelineConfigValue -Config $Profile -Key 'overrides'
    if ($rawOverrides) {
        $overrideMap = ConvertTo-MediaPipelineConfigMap -Value $rawOverrides
        foreach ($rawGroup in $overrideMap.Keys) {
            $group = if ([string]$rawGroup -eq 'subtitle') { 'subtitles' } else { [string]$rawGroup }
            if (-not $keysByGroup.Contains($group)) {
                $errors.Add("Library profile $Label override group is unsupported: $rawGroup.")
                continue
            }
            $values = ConvertTo-MediaPipelineConfigMap -Value $overrideMap[$rawGroup]
            foreach ($key in $values.Keys) {
                $keyText = [string]$key
                if ($keyText -notin @($keysByGroup[$group])) {
                    $errors.Add("Library profile $Label override $group.$keyText is not a supported library override key.")
                }
            }
        }
    }

    foreach ($legacyField in @('editor_overrides','media_overrides')) {
        $legacyValues = ConvertTo-MediaPipelineConfigMap -Value (Get-MediaPipelineConfigValue -Config $Profile -Key $legacyField)
        foreach ($key in $legacyValues.Keys) {
            $keyText = [string]$key
            if ($keyText -notin $allKeys) {
                $errors.Add("Library profile $Label $legacyField.$keyText is not a supported library override key.")
            }
        }
    }
    return @($errors)
}

function Test-MediaPipelineLibraryProfileOverrides {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] $Profile,
        [Parameter(Mandatory)] [string] $Label,
        [System.Collections.Generic.List[string]] $Errors,
        [System.Collections.Generic.List[string]] $Warnings
    )

    $keyErrors = @(Get-MediaPipelineLibraryProfileOverrideKeyErrors -Profile $Profile -Label $Label)
    foreach ($message in $keyErrors) {
        $Errors.Add($message)
    }
    if ($keyErrors.Count -gt 0) { return }

    $overrides = Get-MediaPipelineLibraryProfileOverrideValues -Profile $Profile
    if ($overrides.Count -le 0) { return }

    $candidate = Get-MediaPipelineConfigDefaultValues
    foreach ($key in @(Get-MediaPipelineConfigOrderedKeys)) {
        if (Test-MediaPipelineConfigHasKey -Config $Config -Key $key) {
            $candidate[$key] = Get-MediaPipelineConfigValue -Config $Config -Key $key
        }
    }
    foreach ($key in $overrides.Keys) {
        $candidate[$key] = $overrides[$key]
    }

    $overrideErrors = [System.Collections.Generic.List[string]]::new()
    $overrideWarnings = [System.Collections.Generic.List[string]]::new()
    Test-MediaPipelineConfigEncodeAudioPolicy -Config $candidate -Errors $overrideErrors -Warnings $overrideWarnings

    foreach ($message in @($overrideErrors)) {
        $Errors.Add("Library profile $Label override is invalid: $message")
    }
    foreach ($message in @($overrideWarnings)) {
        $Warnings.Add("Library profile $Label override review: $message")
    }
}
