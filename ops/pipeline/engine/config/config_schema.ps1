# ==============================================================================
# ops\pipeline\engine\config\config_schema.ps1
# ==============================================================================
# Compatibility metadata for the live PSD1 config format. This is intentionally
# small: it centralizes schema version, required keys, array coercion keys, and
# stable output order while preserving the current Import-PowerShellDataFile flow.
# ==============================================================================


. (Join-Path $PSScriptRoot 'schema_keys.ps1')
. (Join-Path $PSScriptRoot 'choice_registry.ps1')
. (Join-Path $PSScriptRoot 'default_values.ps1')
. (Join-Path $PSScriptRoot 'library_overrides.ps1')
. (Join-Path $PSScriptRoot 'schema_validation.ps1')
function Test-MediaPipelineConfigSchema {
    param([Parameter(Mandatory)] $Config)

    $errors = [System.Collections.Generic.List[string]]::new()
    $warnings = [System.Collections.Generic.List[string]]::new()
    $version = Resolve-MediaPipelineConfigSchemaVersion -Config $Config
    foreach ($warning in @($version.Warnings)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$warning)) {
            $warnings.Add([string]$warning)
        }
    }

    foreach ($key in @(Get-MediaPipelineConfigRequiredKeys)) {
        if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $key)) {
            $errors.Add("Config missing key: $key")
        }
    }
    Test-MediaPipelineConfigPathShape -Config $Config -Errors $errors -Warnings $warnings
    Test-MediaPipelineConfigSubtitleToggles -Config $Config -Errors $errors
    Test-MediaPipelineConfigEncodeAudioPolicy -Config $Config -Errors $errors -Warnings $warnings

    return [pscustomobject]@{
        Ok                     = ($errors.Count -eq 0)
        Errors                 = @($errors)
        Warnings               = @($warnings)
        EffectiveSchemaVersion = [int]$version.EffectiveSchemaVersion
        CurrentSchemaVersion   = [int]$version.CurrentSchemaVersion
        RequiredKeys           = @(Get-MediaPipelineConfigRequiredKeys)
        ArrayKeys              = @(Get-MediaPipelineConfigArrayKeys)
        OrderedKeys            = @(Get-MediaPipelineConfigOrderedKeys)
    }
}
