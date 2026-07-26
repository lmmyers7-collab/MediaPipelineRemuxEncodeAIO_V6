# ==============================================================================
# ops\pipeline\engine\config\runtime_merge.ps1
# ==============================================================================
# Runtime config application and merge helpers.
# ==============================================================================

function Set-MediaPipelineRuntimeConfigVariables {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [hashtable] $Config,
        [Parameter(Mandatory)] [string[]] $ArrayKeys
    )

    $registryCommand = Get-Command -Name 'Get-MediaPipelineKnownConfigKeys' -CommandType Function -ErrorAction SilentlyContinue
    if (-not $registryCommand) {
        throw 'Canonical MediaPipeline config-key registry is unavailable; runtime config initialization was blocked.'
    }
    $knownConfigKeys = @(Get-MediaPipelineKnownConfigKeys)
    if ($knownConfigKeys.Count -eq 0) {
        throw 'Canonical MediaPipeline config-key registry is empty; runtime config initialization was blocked.'
    }

    # Reserved names a config key must never overwrite: PowerShell preference
    # variables (they control error handling / progress / confirmation) and
    # automatic variables. Without this guard a config typo such as
    # 'ErrorActionPreference = "Continue"' silently disables the pipeline's
    # fail-fast behaviour, and a key colliding with a read-only automatic
    # variable (e.g. 'PID', 'true') throws and aborts startup under Stop.
    $reservedConfigVariableNames = @(
        'ErrorActionPreference','ProgressPreference','VerbosePreference','DebugPreference',
        'WarningPreference','InformationPreference','ConfirmPreference','WhatIfPreference',
        'PSDefaultParameterValues','PSModuleAutoLoadingPreference','OutputEncoding','ErrorView',
        'PSScriptRoot','PSCommandPath','MyInvocation','PSBoundParameters','PSCmdlet','PSItem',
        'args','input','this','Host','ExecutionContext','PWD','HOME','PID','LASTEXITCODE',
        'true','false','null','Error','StackTrace'
    )
    foreach ($key in $Config.Keys) {
        $keyName = [string]$key
        if ($keyName -in $reservedConfigVariableNames) {
            Add-StartupWarning "Config key '$keyName' collides with a reserved PowerShell variable and was ignored."
            continue
        }
        if ($knownConfigKeys -cnotcontains $keyName) {
            Add-StartupWarning "Unregistered config key '$keyName' was ignored and cannot become a runtime variable."
            continue
        }
        $value = $Config[$key]
        if ($ArrayKeys -ccontains $keyName) {
            if ($null -eq $value)          { $value = @() }
            elseif ($value -isnot [array]) { $value = @($value) }
        }
        try {
            Set-Variable -Name $keyName -Value $value -Scope Script
        } catch {
            Add-StartupWarning "Config key '$keyName' could not be applied as a variable: $($_.Exception.Message)"
        }
    }
}
