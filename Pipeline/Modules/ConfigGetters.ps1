# ==============================================================================
# Modules\ConfigGetters.ps1
# ==============================================================================
# Pure config getter helpers extracted from MediaPipeline_chatgpt.ps1.
#
# Dot-sourced by the main script so the functions continue to read $config and
# call Add-StartupWarning from the script scope at call time.
# ==============================================================================

function Get-ConfigBool {
    param([string]$Key, [bool]$Default)
    if (-not $config.ContainsKey($Key)) { return $Default }
    $v = $config[$Key]
    if ($v -is [bool]) { return $v }
    Add-StartupWarning "Config key '$Key' should be `$true or `$false; using default $Default"
    return $Default
}

function Get-ConfigInt {
    param([string]$Key, [int]$Default, [int]$Min = [int]::MinValue, [int]$Max = [int]::MaxValue)
    if (-not $config.ContainsKey($Key)) { return $Default }
    $v = $config[$Key]
    try {
        $n = [int]$v
        if ($n -lt $Min -or $n -gt $Max) {
            Add-StartupWarning "Config key '$Key' value $n out of range [$Min..$Max]; using default $Default"
            return $Default
        }
        return $n
    } catch {
        Add-StartupWarning "Config key '$Key' is not an integer; using default $Default"
        return $Default
    }
}

function Get-ConfigDouble {
    param([string]$Key, [double]$Default, [double]$Min = [double]::MinValue, [double]$Max = [double]::MaxValue)
    if (-not $config.ContainsKey($Key)) { return $Default }
    $v = $config[$Key]
    try {
        $n = [double]$v
        if ($n -lt $Min -or $n -gt $Max) {
            Add-StartupWarning "Config key '$Key' value $n out of range [$Min..$Max]; using default $Default"
            return $Default
        }
        return $n
    } catch {
        Add-StartupWarning "Config key '$Key' is not a number; using default $Default"
        return $Default
    }
}

function Get-ConfigLogLevel {
    param([string]$Key, [string]$Default)
    if (-not $config.ContainsKey($Key)) { return $Default }
    $value = [string]$config[$Key]
    $normalized = $value.Trim().ToUpperInvariant()
    if ($normalized -in @('ERROR', 'WARN', 'INFO', 'DEBUG')) {
        return $normalized
    }
    Add-StartupWarning "Config key '$Key' should be one of ERROR, WARN, INFO, DEBUG; using default $Default"
    return $Default
}

function Get-ConfigChoice {
    param(
        [string]$Key,
        [string]$Default,
        [string[]]$AllowedValues
    )
    if (-not $config.ContainsKey($Key)) { return $Default }
    $value = [string]$config[$Key]
    $normalized = $value.Trim().ToLowerInvariant()
    if ($normalized -in $AllowedValues) { return $normalized }
    Add-StartupWarning "Config key '$Key' should be one of $($AllowedValues -join ', '); using default $Default"
    return $Default
}
