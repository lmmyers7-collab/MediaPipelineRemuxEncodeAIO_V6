# Extracted from ops/pipeline/engine/process/dynamic_hdr.ps1. Responsibility: metadata extraction planning and execution

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
