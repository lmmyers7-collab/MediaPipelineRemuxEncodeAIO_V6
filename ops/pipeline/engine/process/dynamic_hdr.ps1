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

function New-DynamicHdrMetadataExtractionPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string] $ScratchPath,
        [Parameter(Mandatory)] [string] $WorkDir,
        [bool] $DoviPresent = $false,
        [int] $DoviProfile = 0,
        [int] $DoviBlCompatId = -1,
        [bool] $DoviElPresent = $false,
        [bool] $Hdr10PlusPresent = $false,
        [string] $DoviToolPath = $(Get-Variable -Name DoviToolPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [string] $Hdr10PlusToolPath = $(Get-Variable -Name Hdr10PlusToolPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [string] $MkvExtractPath = $(Get-Variable -Name mkvextractPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [string] $FfmpegPath = $(Get-Variable -Name ffmpegPath -Scope Script -ValueOnly -ErrorAction SilentlyContinue),
        [int] $VideoTrackId = -1,
        [string] $PlanId = ''
    )

    $dynamicPresent = ([bool]$DoviPresent -or [bool]$Hdr10PlusPresent)
    $normalizedPlanId = if ([string]::IsNullOrWhiteSpace($PlanId)) {
        [guid]::NewGuid().ToString('N')
    } else {
        ([regex]::Replace($PlanId.Trim(), '[^A-Za-z0-9_-]', '_')).Trim('_')
    }
    if ([string]::IsNullOrWhiteSpace($normalizedPlanId)) {
        $normalizedPlanId = [guid]::NewGuid().ToString('N')
    }

    $base = [ordered]@{
        schema_version       = 'dynamic_hdr_metadata_extraction_plan.v1'
        ok                   = $false
        required             = [bool]$dynamicPresent
        reason               = ''
        error_code           = ''
        scratch_path         = [string]$ScratchPath
        work_dir             = [string]$WorkDir
        plan_id              = $normalizedPlanId
        hevc_path            = ''
        rpu_path             = ''
        hdr10plus_json_path  = ''
        rpu_summary_path     = ''
        rpu_frame_count      = 0
        target_dovi_profile  = ''
        dovi_conversion_mode = ''
        caveats              = @()
        temp_files           = @()
        commands             = [ordered]@{
            extract_hevc        = $null
            extract_dovi_rpu    = $null
            summarize_dovi_rpu  = $null
            extract_hdr10plus   = $null
        }
    }

    if (-not $dynamicPresent) {
        $base.ok = $true
        $base.reason = 'no dynamic HDR metadata detected'
        return [pscustomobject]$base
    }

    if ([string]::IsNullOrWhiteSpace($ScratchPath)) {
        $base.reason = 'scratch input path is required for dynamic HDR extraction planning'
        $base.error_code = 'DYNAMIC_HDR_SCRATCH_PATH_MISSING'
        return [pscustomobject]$base
    }
    if ([string]::IsNullOrWhiteSpace($WorkDir)) {
        $base.reason = 'work directory is required for dynamic HDR extraction planning'
        $base.error_code = 'DYNAMIC_HDR_WORKDIR_MISSING'
        return [pscustomobject]$base
    }
    if ($DoviPresent -and [string]::IsNullOrWhiteSpace($DoviToolPath)) {
        $base.reason = 'dovi_tool is required for Dolby Vision RPU extraction'
        $base.error_code = 'DYNAMIC_HDR_TOOL_MISSING'
        return [pscustomobject]$base
    }
    if ($Hdr10PlusPresent -and [string]::IsNullOrWhiteSpace($Hdr10PlusToolPath)) {
        $base.reason = 'hdr10plus_tool is required for HDR10+ metadata extraction'
        $base.error_code = 'DYNAMIC_HDR_TOOL_MISSING'
        return [pscustomobject]$base
    }
    if ($DoviPresent -and -not (($DoviProfile -eq 7) -or ($DoviProfile -eq 8 -and $DoviBlCompatId -eq 1))) {
        $base.reason = "dovi profile $DoviProfile is not supported for encode extraction planning"
        $base.error_code = 'DYNAMIC_HDR_UNPRESERVABLE'
        return [pscustomobject]$base
    }

    $hevcPath = Join-Path $WorkDir "dynamic_hdr_$normalizedPlanId.hevc"
    $rpuPath = if ($DoviPresent) { Join-Path $WorkDir "dynamic_hdr_$normalizedPlanId.rpu.bin" } else { '' }
    $hdr10PlusJsonPath = if ($Hdr10PlusPresent) { Join-Path $WorkDir "dynamic_hdr_$normalizedPlanId.hdr10plus.json" } else { '' }
    $rpuSummaryPath = if ($DoviPresent) { Join-Path $WorkDir "dynamic_hdr_$normalizedPlanId.rpu.summary.txt" } else { '' }
    $base.hevc_path = $hevcPath
    $base.rpu_path = $rpuPath
    $base.hdr10plus_json_path = $hdr10PlusJsonPath
    $base.rpu_summary_path = $rpuSummaryPath
    $base.temp_files = @(@($hevcPath, $rpuPath, $hdr10PlusJsonPath, $rpuSummaryPath) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })

    $extension = [System.IO.Path]::GetExtension($ScratchPath).TrimStart('.').ToLowerInvariant()
    if ($extension -eq 'mkv') {
        if ([string]::IsNullOrWhiteSpace($MkvExtractPath)) {
            $base.reason = 'mkvextract is required to extract the source HEVC stream from MKV input'
            $base.error_code = 'DYNAMIC_HDR_TOOL_MISSING'
            return [pscustomobject]$base
        }
        if ($VideoTrackId -lt 0) {
            $base.reason = 'MKV dynamic HDR extraction requires an explicit video track id; the planner must not assume track 0'
            $base.error_code = 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED'
            return [pscustomobject]$base
        }
        $base.commands.extract_hevc = New-DynamicHdrCommandSpec `
            -ToolPath $MkvExtractPath `
            -ArgumentList @('tracks', $ScratchPath, ("{0}:{1}" -f $VideoTrackId, $hevcPath)) `
            -Label 'dynamic HDR HEVC extraction'
    } else {
        if ([string]::IsNullOrWhiteSpace($FfmpegPath)) {
            $base.reason = 'ffmpeg is required to extract an Annex B HEVC stream from non-MKV input'
            $base.error_code = 'DYNAMIC_HDR_TOOL_MISSING'
            return [pscustomobject]$base
        }
        $base.commands.extract_hevc = New-DynamicHdrCommandSpec `
            -ToolPath $FfmpegPath `
            -ArgumentList @('-i', $ScratchPath, '-map', '0:v:0', '-c:v', 'copy', '-bsf:v', 'hevc_mp4toannexb', '-f', 'hevc', $hevcPath) `
            -Label 'dynamic HDR HEVC extraction'
    }

    if ($DoviPresent) {
        if ($DoviProfile -eq 7) {
            $base.target_dovi_profile = '8.1'
            $base.dovi_conversion_mode = 'profile7_to_81'
            if ($DoviElPresent) { $base.caveats = @($base.caveats) + @('dovi profile 7 enhancement layer is not preserved by encode') }
            $base.commands.extract_dovi_rpu = New-DynamicHdrCommandSpec `
                -ToolPath $DoviToolPath `
                -ArgumentList @('-m', '2', 'extract-rpu', '-i', $hevcPath, '-o', $rpuPath) `
                -Label 'Dolby Vision RPU extraction'
        } elseif ($DoviProfile -eq 8 -and $DoviBlCompatId -eq 1) {
            $base.target_dovi_profile = '8.1'
            $base.dovi_conversion_mode = 'profile81'
            $base.commands.extract_dovi_rpu = New-DynamicHdrCommandSpec `
                -ToolPath $DoviToolPath `
                -ArgumentList @('extract-rpu', '-i', $hevcPath, '-o', $rpuPath) `
                -Label 'Dolby Vision RPU extraction'
        }
        $base.commands.summarize_dovi_rpu = New-DynamicHdrCommandSpec `
            -ToolPath $DoviToolPath `
            -ArgumentList @('info', '-i', $rpuPath, '--summary') `
            -Label 'Dolby Vision RPU summary'
    }

    if ($Hdr10PlusPresent) {
        $base.commands.extract_hdr10plus = New-DynamicHdrCommandSpec `
            -ToolPath $Hdr10PlusToolPath `
            -ArgumentList @('extract', '-i', $hevcPath, '-o', $hdr10PlusJsonPath) `
            -Label 'HDR10+ metadata extraction'
    }

    $base.ok = $true
    $base.reason = 'dynamic HDR extraction command plan is ready'
    return [pscustomobject]$base
}

function Test-DynamicHdrArtifactPresent {
    param([string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    return ($null -ne $item -and -not $item.PSIsContainer -and [int64]$item.Length -gt 0)
}

function ConvertFrom-DynamicHdrRpuSummaryFrameCount {
    param([string] $Text)

    $summary = if ($Text) { [string]$Text } else { '' }
    if ([string]::IsNullOrWhiteSpace($summary)) { return 0 }
    foreach ($pattern in @(
        '(?im)\bRPU\s+frames?\s*[:=]\s*(\d+)',
        '(?im)\bframes?\s*[:=]\s*(\d+)',
        '(?im)\b(\d+)\s+RPU\s+frames?\b'
    )) {
        $match = [regex]::Match($summary, $pattern)
        if ($match.Success) { return [int]$match.Groups[1].Value }
    }
    return 0
}

function Invoke-DynamicHdrExtractionCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] $CommandSpec,
        [Parameter(Mandatory)] [string] $Name,
        [int] $TimeoutSeconds = 0,
        [string] $ProcessPriority = 'belownormal'
    )

    $toolPath = [string](Get-DynamicHdrResultValue -Result $CommandSpec -Name 'tool_path')
    $arguments = @((Get-DynamicHdrResultValue -Result $CommandSpec -Name 'arguments'))
    $label = [string](Get-DynamicHdrResultValue -Result $CommandSpec -Name 'label')
    if ([string]::IsNullOrWhiteSpace($label)) { $label = $Name }

    if (Get-Command Invoke-ExternalToolCommand -ErrorAction SilentlyContinue) {
        return Invoke-ExternalToolCommand `
            -ToolName $Name `
            -FilePath $toolPath `
            -ArgumentList $arguments `
            -Stage "dynamic-hdr-$Name" `
            -TimeoutSeconds $TimeoutSeconds `
            -ProcessPriority $ProcessPriority
    }

    return Invoke-NativeProcess `
        -FilePath $toolPath `
        -ArgumentList $arguments `
        -TimeoutSeconds $TimeoutSeconds `
        -Label $label `
        -MaxStdoutChars 8192 `
        -MaxStderrChars 8192 `
        -ProcessPriority $ProcessPriority
}

function Export-DynamicHdrMetadata {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] $Plan,
        [int] $TimeoutSeconds = 0,
        [string] $ProcessPriority = 'belownormal'
    )

    $planId = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'plan_id')
    $base = [ordered]@{
        schema_version       = 'dynamic_hdr_metadata_extraction_result.v1'
        ok                   = $false
        required             = [bool](Get-DynamicHdrResultValue -Result $Plan -Name 'required')
        reason               = ''
        error_code           = ''
        plan_id              = $planId
        hevc_path            = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'hevc_path')
        rpu_path             = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'rpu_path')
        hdr10plus_json_path  = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'hdr10plus_json_path')
        rpu_summary_path     = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'rpu_summary_path')
        rpu_frame_count      = 0
        target_dovi_profile  = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'target_dovi_profile')
        dovi_conversion_mode = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'dovi_conversion_mode')
        caveats              = @((Get-DynamicHdrResultValue -Result $Plan -Name 'caveats'))
        temp_files           = @((Get-DynamicHdrResultValue -Result $Plan -Name 'temp_files'))
        command_results      = @()
    }

    if ($null -eq $Plan) {
        $base.reason = 'dynamic HDR extraction plan is required'
        $base.error_code = 'DYNAMIC_HDR_PLAN_MISSING'
        return [pscustomobject]$base
    }

    if (-not [bool](Get-DynamicHdrResultValue -Result $Plan -Name 'ok')) {
        $base.reason = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'reason')
        $base.error_code = [string](Get-DynamicHdrResultValue -Result $Plan -Name 'error_code')
        return [pscustomobject]$base
    }

    if (-not [bool]$base.required) {
        $base.ok = $true
        $base.reason = 'no dynamic HDR metadata detected'
        return [pscustomobject]$base
    }

    if (-not (Get-Command Invoke-NativeProcess -ErrorAction SilentlyContinue) -and
        -not (Get-Command Invoke-ExternalToolCommand -ErrorAction SilentlyContinue)) {
        $base.reason = 'native process runner is not loaded'
        $base.error_code = 'DYNAMIC_HDR_NATIVE_RUNNER_MISSING'
        return [pscustomobject]$base
    }

    $commands = Get-DynamicHdrResultValue -Result $Plan -Name 'commands'
    foreach ($step in @(
        @{ Name = 'extract_hevc';       ErrorCode = 'DYNAMIC_HDR_HEVC_EXTRACT_FAILED'; ArtifactPath = [string]$base.hevc_path },
        @{ Name = 'extract_dovi_rpu';   ErrorCode = 'DOVI_RPU_EXTRACT_FAILED';         ArtifactPath = [string]$base.rpu_path },
        @{ Name = 'summarize_dovi_rpu'; ErrorCode = 'DOVI_RPU_EXTRACT_FAILED';         ArtifactPath = '' },
        @{ Name = 'extract_hdr10plus';  ErrorCode = 'HDR10PLUS_EXTRACT_FAILED';        ArtifactPath = [string]$base.hdr10plus_json_path }
    )) {
        $commandSpec = Get-DynamicHdrResultValue -Result $commands -Name $step.Name
        if ($null -eq $commandSpec) { continue }

        $nativeResult = Invoke-DynamicHdrExtractionCommand `
            -CommandSpec $commandSpec `
            -Name $step.Name `
            -TimeoutSeconds $TimeoutSeconds `
            -ProcessPriority $ProcessPriority
        $exitCode = [int](Get-DynamicHdrResultValue -Result $nativeResult -Name 'ExitCode')
        $timedOut = [bool](Get-DynamicHdrResultValue -Result $nativeResult -Name 'TimedOut')
        $stopped = [bool](Get-DynamicHdrResultValue -Result $nativeResult -Name 'Stopped')
        $aborted = [bool](Get-DynamicHdrResultValue -Result $nativeResult -Name 'Aborted')
        $stdout = [string](Get-DynamicHdrResultValue -Result $nativeResult -Name 'Stdout')
        $stderr = [string](Get-DynamicHdrResultValue -Result $nativeResult -Name 'Stderr')

        $base.command_results = @($base.command_results) + @([pscustomobject][ordered]@{
            name      = [string]$step.Name
            label     = [string](Get-DynamicHdrResultValue -Result $commandSpec -Name 'label')
            tool_path = [string](Get-DynamicHdrResultValue -Result $commandSpec -Name 'tool_path')
            exit_code = $exitCode
            timed_out = $timedOut
            stopped   = $stopped
            aborted   = $aborted
            stdout    = $stdout
            stderr    = $stderr
        })

        if ($exitCode -ne 0 -or $timedOut -or $stopped -or $aborted) {
            $base.reason = "dynamic HDR command '$($step.Name)' failed"
            $base.error_code = [string]$step.ErrorCode
            return [pscustomobject]$base
        }

        if ($step.Name -eq 'summarize_dovi_rpu') {
            $summaryText = (@($stdout, $stderr) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }) -join "`n"
            if ([string]::IsNullOrWhiteSpace($summaryText)) {
                $base.reason = 'Dolby Vision RPU summary command produced no frame-count evidence'
                $base.error_code = [string]$step.ErrorCode
                return [pscustomobject]$base
            }
            if (-not [string]::IsNullOrWhiteSpace([string]$base.rpu_summary_path)) {
                Set-Content -LiteralPath $base.rpu_summary_path -Value $summaryText -Encoding UTF8
            }
            $base.rpu_frame_count = ConvertFrom-DynamicHdrRpuSummaryFrameCount -Text $summaryText
            if ([int]$base.rpu_frame_count -le 0) {
                $base.reason = 'Dolby Vision RPU summary did not include a positive frame count'
                $base.error_code = [string]$step.ErrorCode
                return [pscustomobject]$base
            }
        } elseif (-not [string]::IsNullOrWhiteSpace([string]$step.ArtifactPath) -and
            -not (Test-DynamicHdrArtifactPresent -Path ([string]$step.ArtifactPath))) {
            $base.reason = "dynamic HDR command '$($step.Name)' did not create a non-empty artifact"
            $base.error_code = [string]$step.ErrorCode
            return [pscustomobject]$base
        }
    }

    $base.ok = $true
    $base.reason = 'dynamic HDR metadata extraction completed'
    return [pscustomobject]$base
}

function New-DynamicHdrPreservationPlan {
    [CmdletBinding()]
    param(
        [ValidateSet('encode','remux')] [string] $Route = 'encode',
        [string] $Policy = '',
        [bool] $DoviPresent = $false,
        [int] $DoviProfile = 0,
        [int] $DoviBlCompatId = -1,
        [bool] $DoviElPresent = $false,
        [bool] $Hdr10PlusPresent = $false,
        [bool] $DoviToolAvailable = $false,
        [bool] $Hdr10PlusToolAvailable = $false,
        [bool] $X265DolbyVisionCapable = $false,
        [bool] $X265Hdr10PlusCapable = $false,
        [string] $VideoCodec = '',
        [bool] $UseCpuFallback = $false
    )

    $resolvedPolicy = Resolve-DynamicHdrPolicy -Policy $Policy
    $dynamicPresent = ([bool]$DoviPresent -or [bool]$Hdr10PlusPresent)
    $codecText = if ($VideoCodec) { $VideoCodec.Trim().ToLowerInvariant() } else { '' }
    $usingX265 = ([bool]$UseCpuFallback -or $codecText -in @('libx265','x265'))
    $reasons = [System.Collections.Generic.List[string]]::new()
    $caveats = [System.Collections.Generic.List[string]]::new()
    $requiredArtifacts = [System.Collections.Generic.List[string]]::new()
    $targetDoviProfile = ''
    $canEncodeDoviProfile = $true

    if ($DoviPresent) {
        if ($DoviProfile -eq 7) {
            $targetDoviProfile = '8.1'
            $requiredArtifacts.Add('dovi_rpu_converted_profile_8_1')
            if ($DoviElPresent) { $caveats.Add('dovi profile 7 enhancement layer is not preserved by encode') }
        } elseif ($DoviProfile -eq 8 -and $DoviBlCompatId -eq 1) {
            $targetDoviProfile = '8.1'
            $requiredArtifacts.Add('dovi_rpu_profile_8_1')
        } else {
            $canEncodeDoviProfile = $false
            $reasons.Add("dovi profile $DoviProfile is not supported for encode preservation")
        }
    }
    if ($Hdr10PlusPresent) {
        $requiredArtifacts.Add('hdr10plus_json')
    }

    if (-not $dynamicPresent) {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'none'
            recommended_route    = $Route
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @()
            caveats              = @($caveats.ToArray())
            reasons              = @('no dynamic HDR metadata detected')
        }
    }

    if ($resolvedPolicy -eq 'off') {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'off'
            recommended_route    = $Route
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @('dynamic HDR preservation policy is off')
        }
    }

    if ($Route -eq 'remux') {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'preserve_by_remux'
            recommended_route    = 'remux'
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @()
            caveats              = @($caveats.ToArray())
            reasons              = @('remux is expected to preserve in-band dynamic HDR metadata')
        }
    }

    if ($resolvedPolicy -eq 'warn') {
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = 'warn_only'
            recommended_route    = 'encode'
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @('warn policy records expected dynamic HDR loss without changing routing')
        }
    }

    if (-not $canEncodeDoviProfile) {
        $action = if ($resolvedPolicy -eq 'preserve_or_review') { 'hold_review' } else { 'prefer_remux' }
        $recommended = if ($resolvedPolicy -eq 'preserve_or_review') { 'review' } else { 'remux' }
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = $action
            recommended_route    = $recommended
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @($reasons.ToArray())
        }
    }

    if (-not $usingX265) { $reasons.Add('dynamic HDR encode preservation requires CPU x265') }
    if ($DoviPresent -and -not $DoviToolAvailable) { $reasons.Add('dovi_tool is required for Dolby Vision RPU extraction') }
    if ($DoviPresent -and -not $X265DolbyVisionCapable) { $reasons.Add('x265 Dolby Vision RPU capability is not verified') }
    if ($Hdr10PlusPresent -and -not $Hdr10PlusToolAvailable) { $reasons.Add('hdr10plus_tool is required for HDR10+ metadata extraction') }
    if ($Hdr10PlusPresent -and -not $X265Hdr10PlusCapable) { $reasons.Add('x265 HDR10+ metadata capability is not verified') }

    if ($reasons.Count -gt 0) {
        $action = if ($resolvedPolicy -eq 'preserve_or_review') { 'hold_review' } else { 'prefer_remux' }
        $recommended = if ($resolvedPolicy -eq 'preserve_or_review') { 'review' } else { 'remux' }
        return [pscustomobject][ordered]@{
            schema_version       = 'dynamic_hdr_preservation_plan.v1'
            policy               = $resolvedPolicy
            route                = $Route
            action               = $action
            recommended_route    = $recommended
            can_preserve_encode  = $false
            target_dovi_profile  = $targetDoviProfile
            required_artifacts   = @($requiredArtifacts.ToArray())
            caveats              = @($caveats.ToArray())
            reasons              = @($reasons.ToArray())
        }
    }

    return [pscustomobject][ordered]@{
        schema_version       = 'dynamic_hdr_preservation_plan.v1'
        policy               = $resolvedPolicy
        route                = $Route
        action               = 'preserve_encode'
        recommended_route    = 'encode'
        can_preserve_encode  = $true
        target_dovi_profile  = $targetDoviProfile
        required_artifacts   = @($requiredArtifacts.ToArray())
        caveats              = @($caveats.ToArray())
        reasons              = @('encode preservation prerequisites are satisfied')
    }
}

function Resolve-DynamicHdrEncodePreservationDecision {
    [CmdletBinding()]
    param(
        $Evidence,
        [string] $Policy = '',
        [string] $OutputContainer = 'mkv',
        [string] $VideoCodec = '',
        [bool] $DoviToolAvailable = $false,
        [bool] $Hdr10PlusToolAvailable = $false,
        [bool] $X265DolbyVisionCapable = $false,
        [bool] $X265Hdr10PlusCapable = $false
    )

    $resolvedPolicy = Resolve-DynamicHdrPolicy -Policy $Policy
    if ($null -eq $Evidence) {
        return [pscustomobject][ordered]@{
            schema_version           = 'dynamic_hdr_encode_preservation_decision.v1'
            policy                   = $resolvedPolicy
            route                    = 'encode'
            action                   = 'none'
            recommended_route        = 'encode'
            dynamic_metadata_present = $false
            should_extract           = $false
            should_force_cpu         = $false
            should_attempt_gpu       = $true
            should_prefer_remux      = $false
            should_hold_review       = $false
            output_container         = if ($OutputContainer) { $OutputContainer.Trim().ToLowerInvariant() } else { 'mkv' }
            target_dovi_profile      = ''
            required_artifacts       = @()
            caveats                  = @()
            reasons                  = @('dynamic HDR evidence is not available')
            reason                   = 'dynamic HDR evidence is not available'
            reason_code              = 'dynamic_hdr_evidence_missing'
            error_code               = ''
            evidence_summary         = ''
            preservation_plan        = $null
        }
    }

    $dynamicPresent = [bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'dynamic_metadata_present')
    $doviPresent = [bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_present')
    $hdr10PlusPresent = [bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'hdr10plus_present')
    $summary = [string](Get-DynamicHdrResultValue -Result $Evidence -Name 'summary')
    $container = if ($OutputContainer) { $OutputContainer.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($container)) { $container = 'mkv' }

    $base = [ordered]@{
        schema_version           = 'dynamic_hdr_encode_preservation_decision.v1'
        policy                   = $resolvedPolicy
        route                    = 'encode'
        action                   = 'none'
        recommended_route        = 'encode'
        dynamic_metadata_present = $dynamicPresent
        should_extract           = $false
        should_force_cpu         = $false
        should_attempt_gpu       = $true
        should_prefer_remux      = $false
        should_hold_review       = $false
        output_container         = $container
        target_dovi_profile      = ''
        required_artifacts       = @()
        caveats                  = @()
        reasons                  = @()
        reason                   = ''
        reason_code              = ''
        error_code               = ''
        evidence_summary         = $summary
        preservation_plan        = $null
    }

    if (-not $dynamicPresent) {
        $base.reason = 'no dynamic HDR metadata detected'
        $base.reason_code = 'no_dynamic_hdr_metadata'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    if ($resolvedPolicy -eq 'off') {
        $base.action = 'off'
        $base.reason = 'dynamic HDR preservation policy is off'
        $base.reason_code = 'dynamic_hdr_policy_off'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    if ($resolvedPolicy -eq 'warn') {
        $base.action = 'warn_only'
        $base.reason = 'warn policy records expected dynamic HDR loss without changing routing'
        $base.reason_code = 'dynamic_hdr_warn_only'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    if ($container -ne 'mkv') {
        $base.action = if ($resolvedPolicy -eq 'preserve_or_review') { 'hold_review' } else { 'prefer_remux' }
        $base.recommended_route = if ($resolvedPolicy -eq 'preserve_or_review') { 'review' } else { 'remux' }
        $base.should_hold_review = ($base.action -eq 'hold_review')
        $base.should_prefer_remux = ($base.action -eq 'prefer_remux')
        $base.reason = "dynamic HDR encode preservation requires MKV output; configured container is '$container'"
        $base.reason_code = 'dynamic_hdr_output_container_unsupported'
        $base.error_code = 'DYNAMIC_HDR_UNPRESERVABLE'
        $base.reasons = @($base.reason)
        return [pscustomobject]$base
    }

    $plan = New-DynamicHdrPreservationPlan `
        -Route 'encode' `
        -Policy $resolvedPolicy `
        -DoviPresent:$doviPresent `
        -DoviProfile ([int](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_profile')) `
        -DoviBlCompatId ([int](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_bl_compat_id')) `
        -DoviElPresent:([bool](Get-DynamicHdrResultValue -Result $Evidence -Name 'dovi_el_present')) `
        -Hdr10PlusPresent:$hdr10PlusPresent `
        -DoviToolAvailable:$DoviToolAvailable `
        -Hdr10PlusToolAvailable:$Hdr10PlusToolAvailable `
        -X265DolbyVisionCapable:$X265DolbyVisionCapable `
        -X265Hdr10PlusCapable:$X265Hdr10PlusCapable `
        -VideoCodec $VideoCodec `
        -UseCpuFallback:$true

    $base.preservation_plan = $plan
    $base.action = [string]$plan.action
    $base.recommended_route = [string]$plan.recommended_route
    $base.target_dovi_profile = [string]$plan.target_dovi_profile
    $base.required_artifacts = @($plan.required_artifacts)
    $base.caveats = @($plan.caveats)
    $base.reasons = @($plan.reasons)
    $base.reason = (@($plan.reasons) -join '; ')

    switch ([string]$plan.action) {
        'preserve_encode' {
            $base.should_extract = $true
            $base.should_force_cpu = $true
            $base.should_attempt_gpu = $false
            $base.reason_code = 'dynamic_hdr_preserve_encode_cpu'
        }
        'prefer_remux' {
            $base.should_prefer_remux = $true
            $base.reason_code = 'dynamic_hdr_prefer_remux'
        }
        'hold_review' {
            $base.should_hold_review = $true
            $base.reason_code = 'dynamic_hdr_hold_review'
            $base.error_code = 'DYNAMIC_HDR_UNPRESERVABLE'
        }
        default {
            $base.reason_code = "dynamic_hdr_$([string]$plan.action)"
        }
    }

    return [pscustomobject]$base
}

function ConvertTo-DynamicHdrX265RelativePath {
    param(
        [string] $ArtifactPath,
        [string] $BaseDirectory
    )

    if ([string]::IsNullOrWhiteSpace($ArtifactPath)) { return '' }
    if ([string]::IsNullOrWhiteSpace($BaseDirectory)) { return '' }

    $baseFull = [System.IO.Path]::GetFullPath($BaseDirectory)
    $artifactFull = [System.IO.Path]::GetFullPath($ArtifactPath)
    $relative = [System.IO.Path]::GetRelativePath($baseFull, $artifactFull)
    if ([string]::IsNullOrWhiteSpace($relative)) { return '' }
    return [string]$relative
}

function Resolve-DynamicHdrX265ArtifactPaths {
    [CmdletBinding()]
    param(
        $ExtractionResult,
        [string] $BaseDirectory = $(Get-Location).Path
    )

    $base = [ordered]@{
        schema_version          = 'dynamic_hdr_x265_artifact_paths.v1'
        ok                      = $false
        required                = $false
        reason                  = ''
        error_code              = ''
        base_directory          = [string]$BaseDirectory
        rpu_source_path         = ''
        hdr10plus_source_path   = ''
        dolby_vision_rpu_path   = ''
        hdr10plus_json_path     = ''
        target_dovi_profile     = ''
        rpu_frame_count         = 0
    }

    if ($null -eq $ExtractionResult) {
        $base.reason = 'dynamic HDR extraction result is required before x265 artifact path resolution'
        $base.error_code = 'DYNAMIC_HDR_EXTRACTION_RESULT_MISSING'
        return [pscustomobject]$base
    }

    if (-not [bool](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'ok')) {
        $base.reason = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'reason')
        $base.error_code = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'error_code')
        return [pscustomobject]$base
    }

    if ([string]::IsNullOrWhiteSpace($BaseDirectory)) {
        $base.reason = 'base directory is required to convert dynamic HDR artifact paths for x265'
        $base.error_code = 'DYNAMIC_HDR_X265_PATH_BASE_MISSING'
        return [pscustomobject]$base
    }

    $base.target_dovi_profile = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'target_dovi_profile')
    $base.rpu_frame_count = [int](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'rpu_frame_count')
    $base.rpu_source_path = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'rpu_path')
    $base.hdr10plus_source_path = [string](Get-DynamicHdrResultValue -Result $ExtractionResult -Name 'hdr10plus_json_path')

    $artifactSpecs = @(
        @{ Kind = 'dolby_vision_rpu'; Source = [string]$base.rpu_source_path; MissingCode = 'DOVI_RPU_EXTRACT_FAILED' },
        @{ Kind = 'hdr10plus_json'; Source = [string]$base.hdr10plus_source_path; MissingCode = 'HDR10PLUS_EXTRACT_FAILED' }
    )
    $requiredCount = 0
    foreach ($artifact in $artifactSpecs) {
        if ([string]::IsNullOrWhiteSpace([string]$artifact.Source)) { continue }
        $requiredCount++

        try {
            $relativePath = ConvertTo-DynamicHdrX265RelativePath -ArtifactPath ([string]$artifact.Source) -BaseDirectory $BaseDirectory
        } catch {
            $base.reason = "dynamic HDR artifact path '$($artifact.Source)' cannot be converted to a relative x265 path: $($_.Exception.Message)"
            $base.error_code = 'DYNAMIC_HDR_X265_PATH_UNREPRESENTABLE'
            return [pscustomobject]$base
        }

        if ([string]::IsNullOrWhiteSpace($relativePath) -or
            [System.IO.Path]::IsPathRooted($relativePath) -or
            $relativePath.Contains(':')) {
            $base.reason = "dynamic HDR artifact path '$($artifact.Source)' is not representable as a relative, colon-free x265 parameter path from '$BaseDirectory'"
            $base.error_code = 'DYNAMIC_HDR_X265_PATH_UNREPRESENTABLE'
            return [pscustomobject]$base
        }

        if (-not (Test-DynamicHdrArtifactPresent -Path ([string]$artifact.Source))) {
            $base.reason = "dynamic HDR artifact '$($artifact.Source)' is missing or empty before x265 path resolution"
            $base.error_code = [string]$artifact.MissingCode
            return [pscustomobject]$base
        }

        if ([string]$artifact.Kind -eq 'dolby_vision_rpu') {
            $base.dolby_vision_rpu_path = $relativePath
        } elseif ([string]$artifact.Kind -eq 'hdr10plus_json') {
            $base.hdr10plus_json_path = $relativePath
        }
    }

    $base.required = ($requiredCount -gt 0)
    $base.ok = $true
    $base.reason = if ($base.required) { 'dynamic HDR x265 artifact paths are ready' } else { 'no dynamic HDR x265 artifact paths are required' }
    return [pscustomobject]$base
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
