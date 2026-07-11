# Extracted from ops/pipeline/engine/process/dynamic_hdr.ps1. Responsibility: policy normalization, tool discovery, and command specs

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

function ConvertTo-DynamicHdrInt {
    param(
        $Value,
        [int] $DefaultValue = -1
    )

    if ($null -eq $Value) { return $DefaultValue }
    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $DefaultValue }
    $parsed = 0
    if ([int]::TryParse($text, [ref]$parsed)) { return $parsed }
    return $DefaultValue
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

function New-DynamicHdrCommandSpec {
    param(
        [Parameter(Mandatory)] [string] $ToolPath,
        [Parameter(Mandatory)] [array] $ArgumentList,
        [Parameter(Mandatory)] [string] $Label
    )

    return [pscustomobject][ordered]@{
        tool_path = [string]$ToolPath
        arguments = @($ArgumentList)
        label     = [string]$Label
    }
}

function Resolve-DynamicHdrMkvVideoTrackId {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string] $SourceFile,
        [int] $FfprobeVideoStreamIndex = -1,
        [int] $TimeoutSeconds = 30
    )

    $base = [ordered]@{
        schema_version              = 'dynamic_hdr_mkv_video_track_id.v1'
        ok                          = $false
        track_id                    = -1
        reason                      = ''
        error_code                  = ''
        source_file                 = [string]$SourceFile
        ffprobe_video_stream_index  = [int]$FfprobeVideoStreamIndex
        candidates                  = @()
        repro_path                  = ''
        error_text                  = ''
    }

    if ([string]::IsNullOrWhiteSpace($SourceFile)) {
        $base.reason = 'source file is required to resolve an MKV video track id'
        $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
        return [pscustomobject]$base
    }
    if (-not (Get-Command Invoke-MkvmergeCommand -ErrorAction SilentlyContinue)) {
        $base.reason = 'mkvmerge command wrapper is unavailable for MKV video track identification'
        $base.error_code = 'DYNAMIC_HDR_TOOL_MISSING'
        return [pscustomobject]$base
    }

    try {
        $result = Invoke-MkvmergeCommand `
            -ArgumentList @('-J', $SourceFile) `
            -TimeoutSeconds $TimeoutSeconds `
            -Stage 'dynamic-hdr-mkv-video-identify' `
            -SaveReproOnFailure

        $exitCode = ConvertTo-DynamicHdrInt -Value (Get-DynamicHdrResultValue -Result $result -Name 'ExitCode') -DefaultValue -1
        $output = [string](Get-DynamicHdrResultValue -Result $result -Name 'Output')
        if ([string]::IsNullOrWhiteSpace($output)) { $output = [string](Get-DynamicHdrResultValue -Result $result -Name 'Stdout') }
        $errorText = [string](Get-DynamicHdrResultValue -Result $result -Name 'Error')
        if ([string]::IsNullOrWhiteSpace($errorText)) { $errorText = [string](Get-DynamicHdrResultValue -Result $result -Name 'Stderr') }
        $base.error_text = $errorText
        $base.repro_path = [string](Get-DynamicHdrResultValue -Result $result -Name 'ReproPath')

        if ($exitCode -ne 0) {
            $base.reason = if ([string]::IsNullOrWhiteSpace($errorText)) { "mkvmerge exited $exitCode while identifying MKV video tracks" } else { $errorText.Trim() }
            $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
            return [pscustomobject]$base
        }
        if ([string]::IsNullOrWhiteSpace($output)) {
            $base.reason = 'mkvmerge returned no JSON while identifying MKV video tracks'
            $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
            return [pscustomobject]$base
        }

        $json = $output | ConvertFrom-Json
        $videoTracks = @(
            foreach ($track in @($json.tracks)) {
                if ([string](Get-DynamicHdrResultValue -Result $track -Name 'type') -ne 'video') { continue }
                $props = Get-DynamicHdrResultValue -Result $track -Name 'properties'
                $number = ConvertTo-DynamicHdrInt -Value (Get-DynamicHdrResultValue -Result $props -Name 'number') -DefaultValue -1
                $candidate = [pscustomobject][ordered]@{
                    track_id              = ConvertTo-DynamicHdrInt -Value (Get-DynamicHdrResultValue -Result $track -Name 'id') -DefaultValue -1
                    number                = $number
                    ffprobe_stream_index  = if ($number -gt 0) { $number - 1 } else { -1 }
                    codec_id              = [string](Get-DynamicHdrResultValue -Result $props -Name 'codec_id')
                    codec                 = [string](Get-DynamicHdrResultValue -Result $props -Name 'codec')
                    language              = [string](Get-DynamicHdrResultValue -Result $props -Name 'language')
                    title                 = [string](Get-DynamicHdrResultValue -Result $props -Name 'track_name')
                }
                if ($candidate.track_id -ge 0) { $candidate }
            }
        )
        $base.candidates = @($videoTracks)

        if ($videoTracks.Count -le 0) {
            $base.reason = 'mkvmerge did not report a usable video track id'
            $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
            return [pscustomobject]$base
        }

        if ($FfprobeVideoStreamIndex -ge 0) {
            $numberMatches = @($videoTracks | Where-Object { [int]$_.ffprobe_stream_index -eq [int]$FfprobeVideoStreamIndex })
            if ($numberMatches.Count -eq 1) {
                $base.ok = $true
                $base.track_id = [int]$numberMatches[0].track_id
                $base.reason = 'resolved MKV video track id from mkvmerge track number and ffprobe stream index'
                return [pscustomobject]$base
            }
            if ($numberMatches.Count -gt 1) {
                $base.reason = "mkvmerge returned multiple video tracks matching ffprobe stream $FfprobeVideoStreamIndex"
                $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
                return [pscustomobject]$base
            }
        }

        if ($videoTracks.Count -eq 1) {
            $base.ok = $true
            $base.track_id = [int]$videoTracks[0].track_id
            $base.reason = 'resolved the only MKV video track id'
            return [pscustomobject]$base
        }

        $base.reason = if ($FfprobeVideoStreamIndex -ge 0) {
            "could not uniquely map ffprobe video stream $FfprobeVideoStreamIndex to an MKVToolNix video track id"
        } else {
            'mkvmerge reported multiple video tracks and no ffprobe video stream index was available'
        }
        $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
        return [pscustomobject]$base
    } catch {
        $base.reason = "mkvmerge JSON video track identification failed: $($_.Exception.Message)"
        $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
        return [pscustomobject]$base
    }
}
