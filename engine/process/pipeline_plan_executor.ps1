# ==============================================================================
# engine\process\pipeline_plan_executor.ps1
# ==============================================================================
# Phase 07B dry-run executor for abstract pipeline_plan.v1 records.
#
# This file is additive and is not loaded by the production pipeline path.
# Production route selection and execution remain with the existing PowerShell
# pipeline until a later, explicitly gated rollout phase.
# ==============================================================================

$repoRootForPipelinePlanExecutor = if ($PSScriptRoot) {
    Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
} else {
    (Get-Location).Path
}

. (Join-Path $repoRootForPipelinePlanExecutor 'engine\shared\media_constants.ps1')
. (Join-Path $repoRootForPipelinePlanExecutor 'engine\decide\encode_policy.ps1')
. (Join-Path $repoRootForPipelinePlanExecutor 'engine\process\pipeline_plan_executor\validation.ps1')

function ConvertTo-PipelinePlanInt {
    param($Value, [int] $Default)
    if ($null -eq $Value) { return $Default }
    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) { return $Default }
    $parsed = 0
    if ([int]::TryParse($text, [ref]$parsed)) { return $parsed }
    return $Default
}

function ConvertTo-PipelinePlanBool {
    param($Value, [bool] $Default = $false)
    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes','on')) { return $true }
    if ($text -in @('false','0','no','off')) { return $false }
    return $Default
}

function Get-PipelinePlanInputPath {
    param(
        [Parameter(Mandatory)] $Plan,
        [string] $InputPath = ''
    )
    if (-not [string]::IsNullOrWhiteSpace($InputPath)) { return $InputPath }
    $sourcePath = [string](Get-PipelinePlanProperty -Value $Plan -Name 'sourcePath' -Default '')
    if (-not [string]::IsNullOrWhiteSpace($sourcePath)) { return $sourcePath }
    return [string]$Plan.sourceId
}

function Get-PipelinePlanOutputPath {
    param(
        [Parameter(Mandatory)] $Plan,
        [string] $OutputPath = ''
    )
    if (-not [string]::IsNullOrWhiteSpace($OutputPath)) { return $OutputPath }
    return [string]$Plan.output.path
}

function Get-PipelinePlanGlobalTitle {
    param([Parameter(Mandatory)] $Plan)
    $sourceId = [string](Get-PipelinePlanProperty -Value $Plan -Name 'sourceId' -Default '')
    if (-not [string]::IsNullOrWhiteSpace($sourceId)) {
        return "MediaPipeline planned output: $sourceId"
    }
    return "MediaPipeline planned output: $($Plan.planId)"
}

function Get-PipelinePlanPresetVideoValue {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )
    $presetValue = Get-PipelinePlanNestedProperty -Value $Plan -Path @('effectivePresetSnapshot','presetV2','video',$Name) -Default $null
    if ($null -ne $presetValue) { return $presetValue }
    return $Default
}

function Get-PipelinePlanEffectivePolicyValue {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )
    return Get-PipelinePlanNestedProperty -Value $Plan -Path @('effectivePresetSnapshot','effectiveDecisionPolicy',$Name) -Default $Default
}

function Get-PipelinePlanTranscodeBitrate {
    param([Parameter(Mandatory)] $Plan)
    $bitrate = Get-PipelinePlanNestedProperty -Value $Plan -Path @('effectivePresetSnapshot','presetV2','audio','transcodeBitrate') -Default '640k'
    if ([string]::IsNullOrWhiteSpace([string]$bitrate)) { return '640k' }
    return [string]$bitrate
}

function Get-PipelinePlanAudioMaxChannels {
    param([Parameter(Mandatory)] $Plan)
    $channels = Get-PipelinePlanNestedProperty -Value $Plan -Path @('effectivePresetSnapshot','presetV2','audio','maxChannels') -Default $null
    if ($null -eq $channels) {
        $channels = Get-PipelinePlanEffectivePolicyValue -Plan $Plan -Name 'audio_max_channels' -Default 6
    }
    return ConvertTo-PipelinePlanInt -Value $channels -Default 6
}

function Get-PipelinePlanIsTV {
    param([Parameter(Mandatory)] $Plan)
    $mediaType = [string](Get-PipelinePlanNestedProperty -Value $Plan -Path @('decisionSnapshot','sourceFactsUsed','media_type') -Default '')
    return ($mediaType.Trim().ToLowerInvariant() -eq 'tv')
}

function Get-PipelinePlanEncodeStep {
    param([Parameter(Mandatory)] $Plan)
    foreach ($commandPlan in @(Get-PipelinePlanArray -Value $Plan.commandPlans)) {
        foreach ($step in @(Get-PipelinePlanArray -Value $commandPlan.steps)) {
            if ([string]$step.operation -eq 'encode_video') { return $step }
        }
    }
    return $null
}

function Get-PipelinePlanEncodeCodec {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] $VideoAction
    )
    $encodeStep = Get-PipelinePlanEncodeStep -Plan $Plan
    $codec = Get-PipelinePlanNestedProperty -Value $encodeStep -Path @('details','codec') -Default $null
    if ($codec) { return [string]$codec }
    if (-not [string]::IsNullOrWhiteSpace([string]$VideoAction.outputCodec)) { return [string]$VideoAction.outputCodec }
    return [string](Get-PipelinePlanEffectivePolicyValue -Plan $Plan -Name 'video_output_codec' -Default 'hevc_nvenc')
}

function New-PipelinePlanExecutorAudioArgumentList {
    param([Parameter(Mandatory)] $Plan)

    $args = [System.Collections.Generic.List[string]]::new()
    $outOrdinal = 0
    $bitrate = Get-PipelinePlanTranscodeBitrate -Plan $Plan
    $maxChannels = Get-PipelinePlanAudioMaxChannels -Plan $Plan
    foreach ($action in @(Get-PipelinePlanStreamActions -Plan $Plan -StreamType 'audio' | Sort-Object { [int]$_.streamIndex })) {
        $sourceIndex = ConvertTo-PipelinePlanInt -Value $action.streamIndex -Default -1
        if ($sourceIndex -lt 0) {
            throw 'PipelinePlan validation failed: audio stream action requires a non-negative streamIndex.'
        }
        $actionName = ([string]$action.action).Trim().ToLowerInvariant()
        if ($actionName -eq 'drop') { continue }
        if ($actionName -eq 'unknown') {
            throw "PipelinePlan validation failed: audio stream $sourceIndex action is unknown."
        }

        $args.AddRange([string[]]@('-map', "0:$sourceIndex"))
        if ($actionName -eq 'copy') {
            $args.AddRange([string[]]@("-c:a:$outOrdinal", 'copy'))
        } elseif ($actionName -eq 'transcode') {
            $codec = [string]$action.outputCodec
            if ([string]::IsNullOrWhiteSpace($codec)) {
                $codec = [string](Get-PipelinePlanEffectivePolicyValue -Plan $Plan -Name 'audio_transcode_codec' -Default 'eac3')
            }
            $args.AddRange([string[]]@("-c:a:$outOrdinal", $codec, "-b:a:$outOrdinal", $bitrate, "-ac:$outOrdinal", [string]$maxChannels))
        } else {
            throw "PipelinePlan validation failed: unsupported audio action '$actionName'."
        }
        $outOrdinal++
    }
    if ($outOrdinal -eq 0 -and @(Get-PipelinePlanStreamActions -Plan $Plan -StreamType 'audio').Count -gt 0) {
        $args.Add('-an')
    }
    return @($args.ToArray())
}

function New-PipelinePlanExecutorSubtitleArgumentList {
    param([Parameter(Mandatory)] $Plan)

    $args = [System.Collections.Generic.List[string]]::new()
    $outOrdinal = 0
    foreach ($action in @(Get-PipelinePlanStreamActions -Plan $Plan -StreamType 'subtitle' | Sort-Object { [int]$_.streamIndex })) {
        $sourceIndex = ConvertTo-PipelinePlanInt -Value $action.streamIndex -Default -1
        if ($sourceIndex -lt 0) {
            throw 'PipelinePlan validation failed: subtitle stream action requires a non-negative streamIndex.'
        }
        $actionName = ([string]$action.action).Trim().ToLowerInvariant()
        if ($actionName -eq 'drop') { continue }
        if ($actionName -eq 'burn') {
            continue
        }
        if ($actionName -eq 'unknown') {
            throw "PipelinePlan validation failed: subtitle stream $sourceIndex action is unknown."
        }

        $args.AddRange([string[]]@('-map', "0:$sourceIndex"))
        if ($actionName -eq 'copy') {
            $args.AddRange([string[]]@("-c:s:$outOrdinal", 'copy'))
        } elseif ($actionName -eq 'convert') {
            $codec = [string]$action.outputCodec
            if ([string]::IsNullOrWhiteSpace($codec)) { $codec = 'subrip' }
            $args.AddRange([string[]]@("-c:s:$outOrdinal", $codec))
        } else {
            throw "PipelinePlan validation failed: unsupported subtitle action '$actionName'."
        }
        $outOrdinal++
    }
    return @($args.ToArray())
}

function ConvertTo-PipelinePlanFfmpegSubtitleFilterPath {
    param([Parameter(Mandatory)] [string] $Path)

    $resolved = try { [System.IO.Path]::GetFullPath($Path) } catch { [string]$Path }
    $text = $resolved.Replace('\', '/')
    $text = $text.Replace(':', '\:')
    $text = $text.Replace("'", "\'")
    $text = $text.Replace(',', '\,')
    $text = $text.Replace('[', '\[')
    $text = $text.Replace(']', '\]')
    return $text
}

function New-PipelinePlanExecutorSubtitleBurnVideoFilterArgs {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $InputPath
    )

    $burnActions = @(
        Get-PipelinePlanStreamActions -Plan $Plan -StreamType 'subtitle' |
            Where-Object { ([string]$_.action).Trim().ToLowerInvariant() -eq 'burn' }
    )
    if ($burnActions.Count -eq 0) { return @() }
    if ($burnActions.Count -gt 1) {
        throw 'PipelinePlan validation failed: subtitle burn plans must select exactly one subtitle stream.'
    }

    $action = $burnActions[0]
    $sourceIndex = ConvertTo-PipelinePlanInt -Value $action.streamIndex -Default -1
    if ($sourceIndex -lt 0) {
        throw 'PipelinePlan validation failed: subtitle burn action requires a non-negative streamIndex.'
    }
    $codec = ([string]$action.inputCodec).Trim().ToLowerInvariant()
    $imageCodecs = @(Get-MediaSubtitleCodecImageNames | ForEach-Object { ([string]$_).ToLowerInvariant() })
    $textCodecs = @((Get-MediaSubtitleCodecTextNames) + (Get-MediaSubtitleCodecAssNames) | ForEach-Object { ([string]$_).ToLowerInvariant() } | Select-Object -Unique)
    if ($codec -in $imageCodecs) {
        return @('-filter_complex', "[0:v:0][0:$sourceIndex]overlay=eof_action=pass:repeatlast=0[vout]", '-map', '[vout]')
    }
    if ($codec -in $textCodecs -or [string]::IsNullOrWhiteSpace($codec)) {
        $filterPath = ConvertTo-PipelinePlanFfmpegSubtitleFilterPath -Path $InputPath
        return @('-filter_complex', "[0:v:0]subtitles=filename='$filterPath':si=$sourceIndex[vout]", '-map', '[vout]')
    }
    throw "PipelinePlan validation failed: subtitle burn codec '$codec' is not supported by the PowerShell encode command builder."
}

function New-PipelinePlanExecutorRemuxAvArgumentList {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $InputPath,
        [Parameter(Mandatory)] [string] $TempAvPath
    )

    $videoAction = Get-PipelinePlanSingleStreamAction -Plan $Plan -StreamType 'video'
    if ([string]$videoAction.action -ne 'copy') {
        throw 'PipelinePlan validation failed: remux AV command requires video copy action.'
    }

    $args = [System.Collections.Generic.List[string]]::new()
    $args.AddRange([string[]]@('-i', $InputPath, '-map', '0:V', '-c:v', 'copy'))
    $codec = ([string]$videoAction.inputCodec).Trim().ToLowerInvariant()
    if ($codec -in (Get-MediaVideoCodecHevcNames)) {
        $args.AddRange([string[]]@('-bsf:v', 'hevc_mp4toannexb'))
    }
    $args.AddRange([string[]]@('-map', '0:t?', '-map_chapters', '0', '-map_metadata', '0'))
    $args.AddRange([string[]](New-PipelinePlanExecutorAudioArgumentList -Plan $Plan))
    $args.AddRange([string[]]@('-y', $TempAvPath))
    return @($args.ToArray())
}

function New-PipelinePlanExecutorMkvmergeArgumentList {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $InputPath,
        [Parameter(Mandatory)] [string] $TempAvPath,
        [Parameter(Mandatory)] [string] $OutputPath
    )

    $args = [System.Collections.Generic.List[string]]::new()
    $args.AddRange([string[]]@('--output', $OutputPath, '--title', (Get-PipelinePlanGlobalTitle -Plan $Plan), $TempAvPath))

    $subtitleSourceIndexes = [System.Collections.Generic.List[string]]::new()
    foreach ($action in @(Get-PipelinePlanStreamActions -Plan $Plan -StreamType 'subtitle' | Sort-Object { [int]$_.streamIndex })) {
        $actionName = ([string]$action.action).Trim().ToLowerInvariant()
        if ($actionName -eq 'drop') { continue }
        if ($actionName -eq 'burn') {
            throw 'PipelinePlan validation failed: subtitle burn plans are not supported by the existing remux command builders.'
        }
        if ($actionName -eq 'unknown') {
            throw "PipelinePlan validation failed: subtitle stream $($action.streamIndex) action is unknown."
        }
        $subtitleSourceIndexes.Add([string]$action.streamIndex)
    }

    if ($subtitleSourceIndexes.Count -gt 0) {
        $args.AddRange([string[]]@('--no-video', '--no-audio', '--subtitle-tracks', ($subtitleSourceIndexes.ToArray() -join ','), $InputPath))
    }
    return @($args.ToArray())
}

function New-PipelinePlanExecutorEncodeCommand {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $InputPath,
        [Parameter(Mandatory)] [string] $OutputPath
    )

    $videoAction = Get-PipelinePlanSingleStreamAction -Plan $Plan -StreamType 'video'
    $codec = Get-PipelinePlanEncodeCodec -Plan $Plan -VideoAction $videoAction
    $preset = [string](Get-PipelinePlanPresetVideoValue -Plan $Plan -Name 'encoderSpeedPreset' -Default 'p7')
    $quality = ConvertTo-PipelinePlanInt -Value (Get-PipelinePlanPresetVideoValue -Plan $Plan -Name 'qualityTarget' -Default $null) -Default 22
    $ladder = [string](Get-PipelinePlanPresetVideoValue -Plan $Plan -Name 'targetSelection' -Default 'auto')
    $cpuPreset = [string](Get-PipelinePlanNestedProperty -Value $Plan -Path @('effectivePresetSnapshot','presetV2','advanced','cpuEncoderSpeedPreset') -Default 'medium')
    $fallbackQuality = ConvertTo-PipelinePlanInt -Value (Get-PipelinePlanNestedProperty -Value $Plan -Path @('effectivePresetSnapshot','presetV2','advanced','cpuFallbackQualityTarget') -Default $null) -Default 20
    $cpuThreads = ConvertTo-PipelinePlanInt -Value (Get-PipelinePlanNestedProperty -Value $Plan -Path @('effectivePresetSnapshot','presetV2','advanced','cpuEncodeMaxThreads') -Default $null) -Default 0

    $attemptPlan = New-EncodeAttemptPlan `
        -UseCpuFallback:$false `
        -IsTV:(Get-PipelinePlanIsTV -Plan $Plan) `
        -IsHDR:$false `
        -InputPath $InputPath `
        -ExtraInputs @() `
        -GlobalTitle (Get-PipelinePlanGlobalTitle -Plan $Plan) `
        -AudioArgs (New-PipelinePlanExecutorAudioArgumentList -Plan $Plan) `
        -SubtitleMapArgs (New-PipelinePlanExecutorSubtitleArgumentList -Plan $Plan) `
        -VideoFilterArgs (New-PipelinePlanExecutorSubtitleBurnVideoFilterArgs -Plan $Plan -InputPath $InputPath) `
        -OutputPath $OutputPath `
        -VideoCodec $codec `
        -VideoPreset $preset `
        -VideoQuality $quality `
        -ExtraVideoFlags @() `
        -FallbackCpuQuality $fallbackQuality `
        -EncodeLadder $ladder `
        -CpuPreset $cpuPreset `
        -CpuMaxThreads $cpuThreads

    return $attemptPlan
}

function Format-PipelinePlanExecutorCommandLine {
    param(
        [Parameter(Mandatory)] [string] $Executable,
        [array] $ArgumentList = @()
    )
    $parts = [System.Collections.Generic.List[string]]::new()
    $parts.Add($Executable)
    foreach ($arg in @($ArgumentList)) {
        $text = [string]$arg
        if ($text -match '[\s"`]') {
            $escaped = $text.Replace('"', '\"')
            $parts.Add('"' + $escaped + '"')
        } else {
            $parts.Add($text)
        }
    }
    return ($parts.ToArray() -join ' ')
}

function New-PipelinePlanExecutorNativeCommand {
    param(
        [Parameter(Mandatory)] [string] $Tool,
        [Parameter(Mandatory)] [string] $Label,
        [Parameter(Mandatory)] [string] $Stage,
        [array] $ArgumentList = @(),
        [string[]] $BuiltWith = @()
    )

    return [pscustomobject][ordered]@{
        tool         = $Tool
        label        = $Label
        stage        = $Stage
        builtWith    = @($BuiltWith)
        argumentList = @($ArgumentList)
        commandLine  = Format-PipelinePlanExecutorCommandLine -Executable $Tool -ArgumentList $ArgumentList
    }
}

function New-PipelinePlanExecutorDryRun {
    param(
        [Parameter(Mandatory)] $Plan,
        [string] $InputPath = '',
        [string] $OutputPath = ''
    )

    if ($Plan -is [string]) {
        $Plan = ConvertFrom-PipelinePlanJson -Json $Plan
    } else {
        Assert-PipelinePlanValid -Plan $Plan | Out-Null
    }

    $resolvedInput = Get-PipelinePlanInputPath -Plan $Plan -InputPath $InputPath
    $resolvedOutput = Get-PipelinePlanOutputPath -Plan $Plan -OutputPath $OutputPath
    $route = [string]$Plan.routeSummary
    $commands = [System.Collections.Generic.List[object]]::new()
    $notes = [System.Collections.Generic.List[string]]::new()
    $notes.Add('Phase 07B dry-run only: production execution remains on the existing PowerShell path.')

    switch ($route) {
        'COPY' {
            $commands.Add([pscustomobject][ordered]@{
                tool         = 'copy_source'
                label        = 'COPY-SOURCE'
                stage        = 'copy-source'
                builtWith    = @('existing scratch/publish safety path')
                argumentList = @($resolvedInput, $resolvedOutput)
                commandLine  = "copy_source `"$resolvedInput`" `"$resolvedOutput`""
            }) | Out-Null
        }
        'REMUX' {
            $container = ([string]$Plan.output.container).Trim().ToLowerInvariant()
            if ($container -notin @('mkv','matroska')) {
                throw "PipelinePlan validation failed: Phase 07B remux command parity is currently limited to MKV/Matroska outputs; got '$($Plan.output.container)'."
            }
            $tempAvPath = [System.IO.Path]::ChangeExtension($resolvedOutput, '.temp_av.mkv')
            $commands.Add((New-PipelinePlanExecutorNativeCommand `
                -Tool 'ffmpeg' `
                -Label 'REMUX-AV' `
                -Stage 'remux-av' `
                -BuiltWith @('Do-Remux AV-stage command shape', 'plan stream action mapping') `
                -ArgumentList (New-PipelinePlanExecutorRemuxAvArgumentList -Plan $Plan -InputPath $resolvedInput -TempAvPath $tempAvPath))) | Out-Null
            $commands.Add((New-PipelinePlanExecutorNativeCommand `
                -Tool 'mkvmerge' `
                -Label 'REMUX-MUX' `
                -Stage 'remux-mkvmerge' `
                -BuiltWith @('Do-Remux mkvmerge-stage command shape', 'plan stream action mapping') `
                -ArgumentList (New-PipelinePlanExecutorMkvmergeArgumentList -Plan $Plan -InputPath $resolvedInput -TempAvPath $tempAvPath -OutputPath $resolvedOutput))) | Out-Null
        }
        'ENCODE' {
            $container = ([string]$Plan.output.container).Trim().ToLowerInvariant()
            if ($container -notin @('mkv','matroska')) {
                throw "PipelinePlan validation failed: Phase 07B encode command parity is currently limited to the existing Matroska FFmpeg builder; got '$($Plan.output.container)'."
            }
            $attemptPlan = New-PipelinePlanExecutorEncodeCommand -Plan $Plan -InputPath $resolvedInput -OutputPath $resolvedOutput
            $commands.Add((New-PipelinePlanExecutorNativeCommand `
                -Tool 'ffmpeg' `
                -Label ([string]$attemptPlan.Label) `
                -Stage ([string]$attemptPlan.ReproStage) `
                -BuiltWith @('New-EncodeAttemptPlan', 'New-EncodeFfmpegArgumentList', 'plan stream action mapping') `
                -ArgumentList @($attemptPlan.ArgumentList))) | Out-Null
        }
        'REJECT' {
            $notes.Add('Rejected plan has no native command.')
        }
        default {
            throw "PipelinePlan validation failed: unsupported route '$route'."
        }
    }

    return [pscustomobject][ordered]@{
        schemaVersion    = 'pipeline_plan_executor_dry_run.v1'
        planId           = [string]$Plan.planId
        routeSummary     = $route
        dryRunOnly       = $true
        wouldExecute     = $false
        inputPath        = $resolvedInput
        outputPath       = $resolvedOutput
        commands         = @($commands.ToArray())
        runtimeFallbacks = @(Get-PipelinePlanArray -Value $Plan.runtimeFallbacks)
        notes            = @($notes.ToArray())
    }
}

function ConvertTo-PipelinePlanExecutorJson {
    param([Parameter(Mandatory)] $DryRun)
    return ($DryRun | ConvertTo-Json -Depth 100)
}

function Invoke-PipelinePlanExecutorDryRun {
    param(
        [string] $PlanJsonPath = '',
        [string] $PlanJson = '',
        [switch] $AsJson
    )

    if ([string]::IsNullOrWhiteSpace($PlanJson) -and [string]::IsNullOrWhiteSpace($PlanJsonPath)) {
        throw 'Provide -PlanJson or -PlanJsonPath.'
    }

    $plan = if (-not [string]::IsNullOrWhiteSpace($PlanJsonPath)) {
        Read-PipelinePlanJson -Path $PlanJsonPath
    } else {
        ConvertFrom-PipelinePlanJson -Json $PlanJson
    }
    $dryRun = New-PipelinePlanExecutorDryRun -Plan $plan
    if ($AsJson) {
        ConvertTo-PipelinePlanExecutorJson -DryRun $dryRun
    } else {
        foreach ($command in @($dryRun.commands)) {
            Write-Output ([string]$command.commandLine)
        }
    }
}
