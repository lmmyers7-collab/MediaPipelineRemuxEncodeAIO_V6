# ==============================================================================
# ops\pipeline\engine\process\dynamic_hdr.ps1
# ==============================================================================
# Dynamic HDR tool discovery and capability probes.
#
# This module intentionally does not enforce preservation policy yet. Phase 2
# makes tool resolution observable and testable while leaving Phase 1 warn-only
# media behavior unchanged until real-media remux evidence is recorded.
# ==============================================================================

function Get-DynamicHdrPolicyNames {
    return @('off','warn','preserve_or_remux','preserve_or_review')
}

function Get-DynamicHdrPolicyDefault {
    return 'warn'
}

function Resolve-DynamicHdrPolicy {
    param([string] $Policy)

    $normalized = if ($Policy) { $Policy.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return Get-DynamicHdrPolicyDefault }
    if ($normalized -in (Get-DynamicHdrPolicyNames)) { return $normalized }
    return Get-DynamicHdrPolicyDefault
}

function Resolve-DynamicHdrConfiguredPath {
    param([string] $ConfiguredPath)

    $text = if ($ConfiguredPath) { $ConfiguredPath.Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }

    $candidates = New-Object System.Collections.Generic.List[string]
    if ([System.IO.Path]::IsPathRooted($text)) {
        [void]$candidates.Add($text)
    } else {
        foreach ($base in @(
            (Get-Variable -Name scriptDir -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
            (Get-Variable -Name repoRootForModules -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
            (Get-Location).Path
        )) {
            if ([string]::IsNullOrWhiteSpace([string]$base)) { continue }
            [void]$candidates.Add((Join-Path ([string]$base) $text))
        }
    }

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Resolve-DynamicHdrToolPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string] $CommandName,
        [string] $ConfiguredPath = '',
        [string[]] $RelativeCandidates = @(),
        [switch] $AllowSystemTools
    )

    $reasons = New-Object System.Collections.Generic.List[string]
    $configuredText = if ($ConfiguredPath) { $ConfiguredPath.Trim() } else { '' }
    if (-not [string]::IsNullOrWhiteSpace($configuredText)) {
        $resolvedConfigured = Resolve-DynamicHdrConfiguredPath -ConfiguredPath $configuredText
        if ($resolvedConfigured) {
            return [pscustomobject][ordered]@{
                CommandName    = $CommandName
                Path           = $resolvedConfigured
                Source         = 'config'
                ConfiguredPath = $configuredText
                Reason         = ''
            }
        }
        [void]$reasons.Add("configured path not found: $configuredText")
    }

    $previousAllowSystemTools = Get-Variable -Name AllowSystemTools -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    try {
        $script:AllowSystemTools = [bool]$AllowSystemTools
        if (Get-Command Resolve-BundledExecutable -ErrorAction SilentlyContinue) {
            $resolved = Resolve-BundledExecutable -CommandName $CommandName -RelativeCandidates $RelativeCandidates
        } else {
            $resolved = $null
        }
    } finally {
        if ($null -ne $previousAllowSystemTools) {
            $script:AllowSystemTools = $previousAllowSystemTools
        }
    }

    if ($resolved) {
        $root = [string](Get-Variable -Name repoRootForModules -Scope Script -ValueOnly -ErrorAction SilentlyContinue)
        $source = 'bundled'
        if ($AllowSystemTools -and ($root -and -not ([string]$resolved).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase))) {
            $source = 'system'
        }
        return [pscustomobject][ordered]@{
            CommandName    = $CommandName
            Path           = [string]$resolved
            Source         = $source
            ConfiguredPath = $configuredText
            Reason         = ''
        }
    }

    [void]$reasons.Add("no bundled $CommandName executable found")
    if (-not $AllowSystemTools) {
        [void]$reasons.Add('AllowSystemTools is false')
    } else {
        [void]$reasons.Add("$CommandName was not found on PATH")
    }

    return [pscustomobject][ordered]@{
        CommandName    = $CommandName
        Path           = ''
        Source         = 'missing'
        ConfiguredPath = $configuredText
        Reason         = ($reasons -join '; ')
    }
}

function ConvertFrom-DynamicHdrToolVersionText {
    param([string] $Text)

    $normalized = if ($Text) { $Text.Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return '' }
    $match = [regex]::Match($normalized, '(?im)(?:^|\s)v?(\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z0-9_.-]+)?)')
    if ($match.Success) { return $match.Groups[1].Value }
    return ''
}

function Get-DynamicHdrResultValue {
    param(
        [Parameter(Mandatory = $true)] $Result,
        [Parameter(Mandatory = $true)] [string] $Name
    )

    if ($Result -is [System.Collections.IDictionary]) { return $Result[$Name] }
    $property = $Result.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $null
}

function Get-DynamicHdrToolVersion {
    [CmdletBinding()]
    param(
        [string] $ToolPath,
        [string] $ToolName = '',
        [int] $TimeoutSeconds = 10
    )

    $label = if ($ToolName) { $ToolName } elseif ($ToolPath) { Split-Path $ToolPath -Leaf } else { 'dynamic-hdr-tool' }
    if ([string]::IsNullOrWhiteSpace($ToolPath) -or -not (Test-Path -LiteralPath $ToolPath -PathType Leaf)) {
        return [pscustomobject][ordered]@{
            ToolName  = $label
            Available = $false
            Path      = [string]$ToolPath
            Version   = ''
            RawText   = ''
            Reason    = 'tool executable not found'
        }
    }
    if (-not (Get-Command Invoke-NativeProcess -ErrorAction SilentlyContinue)) {
        return [pscustomobject][ordered]@{
            ToolName  = $label
            Available = $false
            Path      = [string]$ToolPath
            Version   = ''
            RawText   = ''
            Reason    = 'native process runner is not loaded'
        }
    }

    $result = Invoke-NativeProcess `
        -FilePath $ToolPath `
        -ArgumentList @('--version') `
        -TimeoutSeconds $TimeoutSeconds `
        -Label "$label version" `
        -MaxStdoutChars 4096 `
        -MaxStderrChars 4096
    $stdout = [string](Get-DynamicHdrResultValue -Result $result -Name 'Stdout')
    $stderr = [string](Get-DynamicHdrResultValue -Result $result -Name 'Stderr')
    $raw = (@($stdout, $stderr) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join "`n"
    $exitCode = [int](Get-DynamicHdrResultValue -Result $result -Name 'ExitCode')
    $timedOut = [bool](Get-DynamicHdrResultValue -Result $result -Name 'TimedOut')
    $version = ConvertFrom-DynamicHdrToolVersionText -Text $raw

    return [pscustomobject][ordered]@{
        ToolName  = $label
        Available = ($exitCode -eq 0 -and -not $timedOut)
        Path      = [string]$ToolPath
        Version   = $version
        RawText   = $raw
        Reason    = if ($exitCode -eq 0 -and -not $timedOut) { '' } elseif ($timedOut) { 'version command timed out' } else { "version command exited $exitCode" }
    }
}

function Test-DynamicHdrToolsAvailable {
    [CmdletBinding()]
    param(
        [string] $DoviToolPath = $(Get-Variable -Name DoviToolPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [string] $Hdr10PlusToolPath = $(Get-Variable -Name Hdr10PlusToolPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [int] $TimeoutSeconds = 10
    )

    $dovi = Get-DynamicHdrToolVersion -ToolPath $DoviToolPath -ToolName 'dovi_tool' -TimeoutSeconds $TimeoutSeconds
    $hdr10Plus = Get-DynamicHdrToolVersion -ToolPath $Hdr10PlusToolPath -ToolName 'hdr10plus_tool' -TimeoutSeconds $TimeoutSeconds

    return [pscustomobject][ordered]@{
        DoviToolAvailable      = [bool]$dovi.Available
        DoviToolPath           = [string]$dovi.Path
        DoviToolVersion        = [string]$dovi.Version
        Hdr10PlusToolAvailable = [bool]$hdr10Plus.Available
        Hdr10PlusToolPath      = [string]$hdr10Plus.Path
        Hdr10PlusToolVersion   = [string]$hdr10Plus.Version
        AnyToolAvailable       = ([bool]$dovi.Available -or [bool]$hdr10Plus.Available)
        AllToolsAvailable      = ([bool]$dovi.Available -and [bool]$hdr10Plus.Available)
        Details                = [ordered]@{
            dovi_tool      = $dovi
            hdr10plus_tool = $hdr10Plus
        }
    }
}

function Clear-DynamicHdrCapabilityProbe {
    $script:X265DynamicHdrCapabilityCache = $null
}

function Test-X265DynamicHdrCapability {
    [CmdletBinding()]
    param(
        [string] $FfmpegPath = $(Get-Variable -Name ffmpegPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [string] $DoviRpuFixturePath = '',
        [string] $Hdr10PlusJsonFixturePath = '',
        [switch] $Force
    )

    if (-not $Force -and $script:X265DynamicHdrCapabilityCache) {
        return $script:X265DynamicHdrCapabilityCache
    }

    $reason = ''
    $probed = $false
    if ([string]::IsNullOrWhiteSpace($FfmpegPath) -or -not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
        $reason = "ffmpeg not found: $FfmpegPath"
    } elseif ([string]::IsNullOrWhiteSpace($DoviRpuFixturePath) -and [string]::IsNullOrWhiteSpace($Hdr10PlusJsonFixturePath)) {
        $reason = 'dynamic HDR x265 capability probe fixtures were not supplied'
    } else {
        $reason = 'dynamic HDR x265 capability probe execution is pending representative fixture validation'
    }

    $script:X265DynamicHdrCapabilityCache = [pscustomobject][ordered]@{
        Probed      = $probed
        DolbyVision = $false
        Hdr10Plus   = $false
        FfmpegPath  = [string]$FfmpegPath
        Reason      = $reason
        CheckedAt   = (Get-Date).ToString('o')
    }
    return $script:X265DynamicHdrCapabilityCache
}
