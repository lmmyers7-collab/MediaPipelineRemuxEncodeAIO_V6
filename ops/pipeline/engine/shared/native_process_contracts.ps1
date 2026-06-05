# ==============================================================================
# ops\pipeline\engine\shared\native_process_contracts.ps1
# ==============================================================================
# Shared result/metadata contracts for native tool execution.
#
# This is deliberately smaller than a full process-runner merge. Native.ps1 and
# FfmpegProgress.ps1 can still use different IO loops where needed, but they now
# share timeout policy, failure-code classification, and result metadata shape.
# ==============================================================================

function New-NativeCommandResult {
    param(
        [int] $ExitCode,
        [string] $Stdout = '',
        [string] $Stderr = '',
        [bool] $TimedOut = $false,
        [bool] $Stopped = $false,
        [string] $ErrorCode = ''
    )

    if ([string]::IsNullOrWhiteSpace($ErrorCode)) {
        $ErrorCode = if ($ExitCode -eq 0) { 'OK' } else { "NATIVE_EXIT_$ExitCode" }
    }

    return @{
        ExitCode  = $ExitCode
        Output    = $Stdout
        Error     = $Stderr
        Stdout    = $Stdout
        Stderr    = $Stderr
        TimedOut  = $TimedOut
        Stopped   = $Stopped
        ErrorCode = $ErrorCode
    }
}

function Get-ExternalToolFailureCode {
    param(
        [Parameter(Mandatory)] [string]$ToolName,
        [Parameter(Mandatory)] $Result
    )

    $prefix = (($ToolName -replace '[^A-Za-z0-9]+', '_').Trim('_')).ToUpperInvariant()
    if ([string]::IsNullOrWhiteSpace($prefix)) { $prefix = 'TOOL' }

    if ([int]$Result.ExitCode -eq 0) { return 'OK' }
    if ([bool]$Result.TimedOut) { return "${prefix}_TIMEOUT" }
    if ([bool]$Result.Stopped) { return "${prefix}_STOPPED" }
    if ([int]$Result.ExitCode -eq -2) { return "${prefix}_START_FAILED" }
    return "${prefix}_FAILED"
}

function Set-ExternalToolResultProperty {
    param(
        [Parameter(Mandatory)] $Result,
        [Parameter(Mandatory)] [string]$Name,
        $Value
    )

    if ($Result -is [System.Collections.IDictionary]) {
        $Result[$Name] = $Value
        return
    }

    $prop = $Result.PSObject.Properties[$Name]
    if ($prop) {
        $prop.Value = $Value
    } else {
        Add-Member -InputObject $Result -NotePropertyName $Name -NotePropertyValue $Value -Force
    }
}

function Get-NativeToolDefaultTimeoutSeconds {
    param([Parameter(Mandatory)] [string]$ToolName)

    switch ($ToolName.ToLowerInvariant()) {
        'ffprobe' { return 30 }
        'ffmpeg' { return 86400 }
        'mkvmerge' { return 21600 }
        'python' { return 3600 }
        'bdpgs-ocr' { return 1800 }
        default { return 3600 }
    }
}
