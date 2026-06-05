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
        if ($key -in $reservedConfigVariableNames) {
            Add-StartupWarning "Config key '$key' collides with a reserved PowerShell variable and was ignored."
            continue
        }
        $value = $Config[$key]
        if ($key -in $ArrayKeys) {
            if ($null -eq $value)          { $value = @() }
            elseif ($value -isnot [array]) { $value = @($value) }
        }
        try {
            Set-Variable -Name $key -Value $value -Scope Script
        } catch {
            Add-StartupWarning "Config key '$key' could not be applied as a variable: $($_.Exception.Message)"
        }
    }
}
