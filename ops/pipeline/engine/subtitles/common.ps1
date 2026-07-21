# ==============================================================================
# ops\pipeline\engine\subtitles\common.ps1
# ==============================================================================
# Common subtitle policy, metadata normalization, config switches, and filter routing.
# Dot-sourced by ops\pipeline\engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

function Get-SubtitleOperationTimeoutSeconds {
    param(
        [Parameter(Mandatory)] [string]$ScriptVariableName,
        [Parameter(Mandatory)] [int]$DefaultSeconds
    )

    $configured = Get-Variable -Name $ScriptVariableName -Scope Script -ErrorAction SilentlyContinue
    if ($configured -and $null -ne $configured.Value) {
        try {
            $seconds = [int]$configured.Value
            if ($seconds -gt 0) { return $seconds }
        } catch {}
    }
    return $DefaultSeconds
}

function ConvertTo-SubtitleBool {
    param(
        $Value,
        [bool]$Default = $false
    )

    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }

    $text = ([string]$Value).Trim()
    if ($text -match '^(?i:true|1|yes|y)$') { return $true }
    if ($text -match '^(?i:false|0|no|n)$') { return $false }
    return $Default
}

function Get-EffectiveSubtitleSwitch {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [bool]$Default = $false
    )

    if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey($Name)) {
        return (ConvertTo-SubtitleBool -Value $script:ActiveOverrides[$Name] -Default $Default)
    }

    $configured = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
    if ($configured) {
        return (ConvertTo-SubtitleBool -Value $configured.Value -Default $Default)
    }

    return $Default
}

function Get-ConfiguredOutputContainerName {
    if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('OutputContainer')) {
        $activeContainer = ([string]$script:ActiveOverrides['OutputContainer']).Trim().TrimStart('.').ToLowerInvariant()
        if (-not [string]::IsNullOrWhiteSpace($activeContainer)) { return $activeContainer }
    }
    $configured = Get-Variable -Name 'OutputContainer' -Scope Script -ErrorAction SilentlyContinue
    if ($configured -and $configured.Value) {
        return ([string]$configured.Value).Trim().TrimStart('.').ToLowerInvariant()
    }
    return Get-MediaContainerMkvExtensionName
}

function Test-ConfiguredOutputContainerIsMp4 {
    $container = Get-ConfiguredOutputContainerName
    if (Get-Command -Name Get-MediaContainerMp4FamilyNames -ErrorAction SilentlyContinue) {
        return ($container -in (Get-MediaContainerMp4FamilyNames))
    }
    return ($container -in @('mp4','m4v','mov'))
}

function Get-ConvertedSrtCodecForFfmpegOutput {
    $container = Get-ConfiguredOutputContainerName
    if ($container -in (Get-MediaContainerMp4FamilyNames)) { return Get-MediaSubtitleCodecMovTextName }
    return 'copy'
}

function Add-SubtitleConfiguredPathBaseDirectory {
    param(
        [System.Collections.Generic.List[string]]$BaseDirectories,
        [string]$Candidate
    )

    if ([string]::IsNullOrWhiteSpace($Candidate)) { return }
    try {
        $fullPath = [System.IO.Path]::GetFullPath([string]$Candidate)
    } catch {
        $fullPath = [string]$Candidate
    }

    foreach ($existing in $BaseDirectories) {
        if ([string]::Equals([string]$existing, $fullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            return
        }
    }
    $BaseDirectories.Add($fullPath) | Out-Null
}

function Add-SubtitlePipelineDirectoryCandidates {
    param(
        [System.Collections.Generic.List[string]]$BaseDirectories,
        [string]$Candidate
    )

    if ([string]::IsNullOrWhiteSpace($Candidate)) { return }

    $leaf = Split-Path -Leaf $Candidate
    if ($leaf -ieq 'entrypoints') {
        $pipelineDir = Split-Path -Parent $Candidate
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $BaseDirectories -Candidate $pipelineDir
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $BaseDirectories -Candidate (Join-Path $pipelineDir 'tools')
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $BaseDirectories -Candidate $Candidate
    } elseif ($leaf -ieq 'pipeline') {
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $BaseDirectories -Candidate $Candidate
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $BaseDirectories -Candidate (Join-Path $Candidate 'tools')
    } else {
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $BaseDirectories -Candidate $Candidate
    }
}

function Get-SubtitleScriptScopedValue {
    param([Parameter(Mandatory)] [string]$Name)

    $variable = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
    if ($variable -and $null -ne $variable.Value) { return [string]$variable.Value }
    return ''
}

function Get-SubtitleConfiguredPathBaseDirectories {
    $baseDirectories = [System.Collections.Generic.List[string]]::new()

    Add-SubtitlePipelineDirectoryCandidates -BaseDirectories $baseDirectories -Candidate (Get-SubtitleScriptScopedValue -Name 'scriptDir')
    Add-SubtitlePipelineDirectoryCandidates -BaseDirectories $baseDirectories -Candidate (Get-SubtitleScriptScopedValue -Name 'pipelineRoot')

    $repoRootForModules = Get-SubtitleScriptScopedValue -Name 'repoRootForModules'
    if ($repoRootForModules) {
        Add-SubtitlePipelineDirectoryCandidates -BaseDirectories $baseDirectories -Candidate (Join-Path $repoRootForModules 'ops\pipeline')
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $baseDirectories -Candidate $repoRootForModules
    }

    if ($PSScriptRoot) {
        $subtitlesDir = $PSScriptRoot
        $engineDir = Split-Path -Parent $subtitlesDir
        $pipelineDir = Split-Path -Parent $engineDir
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $baseDirectories -Candidate $subtitlesDir
        Add-SubtitleConfiguredPathBaseDirectory -BaseDirectories $baseDirectories -Candidate $engineDir
        Add-SubtitlePipelineDirectoryCandidates -BaseDirectories $baseDirectories -Candidate $pipelineDir
    }

    Add-SubtitlePipelineDirectoryCandidates -BaseDirectories $baseDirectories -Candidate ((Get-Location).Path)
    return $baseDirectories.ToArray()
}

function Resolve-SubtitleConfiguredPath {
    param(
        [string]$PathValue,
        [switch]$AllowCommandLookup
    )

    $raw = if ($PathValue) { ([string]$PathValue).Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($raw)) { return '' }

    if ([System.IO.Path]::IsPathRooted($raw)) {
        try { return [System.IO.Path]::GetFullPath($raw) } catch { return $raw }
    }

    $baseDirectories = @(Get-SubtitleConfiguredPathBaseDirectories)
    $firstCandidate = $null
    foreach ($baseDir in $baseDirectories) {
        if ([string]::IsNullOrWhiteSpace([string]$baseDir)) { continue }
        $candidate = Join-Path ([string]$baseDir) $raw
        if (-not $firstCandidate) { $firstCandidate = $candidate }
        if (Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    if ($AllowCommandLookup -and $script:AllowSystemTools) {
        $cmd = Get-Command $raw -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd -and $cmd.Source) { return $cmd.Source }
    }

    if ($firstCandidate) {
        try { return [System.IO.Path]::GetFullPath($firstCandidate) } catch { return $firstCandidate }
    }
    return $raw
}

function Get-SafeSubtitleFileToken {
    param(
        [string]$Value,
        [int]$MaxLength = 40
    )

    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $token = $Value.ToLowerInvariant()
    $token = $token -replace '\[[^\]]+\]', ' '
    $token = $token -replace '[^a-z0-9]+', '-'
    $token = $token.Trim('-')
    if ($token.Length -gt $MaxLength) {
        $token = $token.Substring(0, $MaxLength).Trim('-')
    }
    return $token
}

function Write-SubtitleTrackProgress {
    param(
        [string]$Kind,
        [string]$TrackId = '',
        [int]$StreamIndex = -1,
        [string]$Stage,
        [string]$Status,
        [int]$StepIndex = 0,
        [int]$StepTotal = 4,
        [array]$Steps = @('extract','convert_ocr','validate','sidecar_write'),
        [string]$Detail = "",
        [object]$CueCount = $null,
        [object]$WorkNumerator = $null,
        [object]$WorkDenominator = $null,
        [string]$ProgressUnit = '',
        [string]$OutputCodec = '',
        [string]$OutputLocation = '',
        [string]$OutputPath = '',
        [string]$ParkedPath = '',
        [string]$IntendedFinalPath = '',
        [switch]$Completed,
        [switch]$Failed
    )

    if (Get-Command -Name Set-ProgressSubtitleTrack -ErrorAction SilentlyContinue) {
        $effectiveTrackId = $TrackId
        if ([string]::IsNullOrWhiteSpace($effectiveTrackId)) {
            $activeTrackId = Get-Variable -Name CurrentSubtitleEvidenceTrackId -Scope Script -ErrorAction SilentlyContinue
            if ($activeTrackId -and $activeTrackId.Value) { $effectiveTrackId = [string]$activeTrackId.Value }
        }
        Set-ProgressSubtitleTrack `
            -Kind $Kind `
            -TrackId $effectiveTrackId `
            -StreamIndex $StreamIndex `
            -Stage $Stage `
            -Status $Status `
            -StepIndex $StepIndex `
            -StepTotal $StepTotal `
            -Steps $Steps `
            -Detail $Detail `
            -CueCount $CueCount `
            -WorkNumerator $WorkNumerator `
            -WorkDenominator $WorkDenominator `
            -ProgressUnit $ProgressUnit `
            -OutputCodec $OutputCodec `
            -OutputLocation $OutputLocation `
            -OutputPath $OutputPath `
            -ParkedPath $ParkedPath `
            -IntendedFinalPath $IntendedFinalPath `
            -Completed:$Completed `
            -Failed:$Failed `
            -SaveNow
    }
}

function New-SubtitleTrackHeartbeatHandler {
    <#
    .SYNOPSIS
    Creates a throttled native poll callback for one exact subtitle track stage.

    .DESCRIPTION
    The handler captures the authoritative run, job, track, and stage identities at
    creation time. It stops emitting if the current run/job/track context changes,
    preventing a late native callback from refreshing a later file. Heartbeats are
    active and indeterminate; determinate progress remains reserved for tools that
    provide a truthful numerator and denominator.
    #>
    param(
        [Parameter(Mandatory)] [string] $Kind,
        [AllowEmptyString()] [string] $TrackId = '',
        [int] $StreamIndex = -1,
        [Parameter(Mandatory)] [string] $Stage,
        [Parameter(Mandatory)] [string] $Status,
        [int] $StepIndex = 0,
        [int] $StepTotal = 4,
        [array] $Steps = @('extract','convert_ocr','validate','sidecar_write'),
        [string] $Detail = '',
        [double] $MinimumIntervalSeconds = 5
    )

    $runVariable = Get-Variable -Name PipelineRunId -Scope Script -ErrorAction SilentlyContinue
    $jobVariable = Get-Variable -Name CurrentRunMonitorJobId -Scope Script -ErrorAction SilentlyContinue
    $trackVariable = Get-Variable -Name CurrentSubtitleEvidenceTrackId -Scope Script -ErrorAction SilentlyContinue
    $capturedRunId = if ($runVariable) { [string]$runVariable.Value } else { '' }
    $capturedJobId = if ($jobVariable) { [string]$jobVariable.Value } else { '' }
    $capturedTrackId = ([string]$TrackId).Trim()
    $heartbeatEvidenceSource = ('subtitle_{0}_{1}_heartbeat' -f ([string]$Kind).Trim().ToLowerInvariant(), ([string]$Stage).Trim().ToLowerInvariant()) -replace '[^a-z0-9_]+', '_'
    $activeTrackHeartbeatCommand = Get-Command -Name Update-MediaPipelineRunMonitorActiveTrackHeartbeat -ErrorAction SilentlyContinue
    $writeTrackProgressCommand = Get-Command -Name Write-SubtitleTrackProgress -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($capturedRunId) -or
        [string]::IsNullOrWhiteSpace($capturedJobId) -or
        [string]::IsNullOrWhiteSpace($capturedTrackId)) {
        return $null
    }

    $exactHandler = {
        param($ElapsedSeconds, $Process)

        # PSVariable objects retain a live reference to the caller's script-scope
        # identity slots even though this callback is closed over in a dynamic
        # module. Re-resolving `-Scope Script` here would inspect the closure's
        # module instead of the pipeline script and incorrectly suppress updates.
        $currentRunId = if ($runVariable) { [string]$runVariable.Value } else { '' }
        $currentJobId = if ($jobVariable) { [string]$jobVariable.Value } else { '' }
        $currentTrackId = if ($trackVariable) { [string]$trackVariable.Value } else { '' }
        if ($currentRunId -ne $capturedRunId -or
            $currentJobId -ne $capturedJobId -or
            $currentTrackId -ne $capturedTrackId) {
            return $null
        }

        if ($activeTrackHeartbeatCommand) {
            # Liveness refreshes only tracks/stage records that are still active;
            # it cannot reactivate terminal evidence or overwrite policy/results.
            & $activeTrackHeartbeatCommand `
                -Kind 'subtitles' `
                -RunId $capturedRunId `
                -JobId $capturedJobId `
                -TrackId $capturedTrackId `
                -EvidenceSource $heartbeatEvidenceSource `
                -EvidenceProvenance 'worker_heartbeat' | Out-Null
        } else {
            # Focused conversion harnesses do not load the run-monitor writer.
            & $writeTrackProgressCommand `
                -Kind $Kind `
                -TrackId $capturedTrackId `
                -StreamIndex $StreamIndex `
                -Stage $Stage `
                -Status $Status `
                -StepIndex $StepIndex `
                -StepTotal $StepTotal `
                -Steps $Steps `
                -Detail $Detail
        }
        return $null
    }.GetNewClosure()

    if (Get-Command -Name New-ThrottledNativePollHandler -ErrorAction SilentlyContinue) {
        return New-ThrottledNativePollHandler -Handler $exactHandler -MinimumIntervalSeconds $MinimumIntervalSeconds
    }

    # Focused subtitle harnesses may load this module without shared/native.ps1.
    # Preserve the same elapsed-time contract without inventing a second evidence path.
    $minimumInterval = [math]::Max(0.0, [double]$MinimumIntervalSeconds)
    $throttleState = [pscustomobject]@{
        HasInvoked = $false
        LastInvokedElapsed = 0.0
    }
    return {
        param($ElapsedSeconds, $Process)
        $elapsed = 0.0
        try { $elapsed = [double]$ElapsedSeconds } catch { $elapsed = 0.0 }
        if ([double]::IsNaN($elapsed) -or [double]::IsInfinity($elapsed) -or $elapsed -lt 0) { $elapsed = 0.0 }
        if ([bool]$throttleState.HasInvoked -and
            $elapsed -ge [double]$throttleState.LastInvokedElapsed -and
            ($elapsed - [double]$throttleState.LastInvokedElapsed) -lt $minimumInterval) {
            return $null
        }
        $throttleState.HasInvoked = $true
        $throttleState.LastInvokedElapsed = $elapsed
        return (& $exactHandler $ElapsedSeconds $Process)
    }.GetNewClosure()
}

function Write-SubtitleSidecarProgress {
    param(
        [string]$Status = 'Writing subtitle sidecar evidence',
        [string]$Detail = "",
        [switch]$Completed,
        [switch]$Failed
    )

    if (Get-Command -Name Set-ProgressSubtitleSidecarWrite -ErrorAction SilentlyContinue) {
        Set-ProgressSubtitleSidecarWrite `
            -Status $Status `
            -Detail $Detail `
            -Completed:$Completed `
            -Failed:$Failed `
            -SaveNow
    }
}


. (Join-Path $PSScriptRoot 'language_policy.ps1')
. (Join-Path $PSScriptRoot 'failure_records.ps1')
. (Join-Path $PSScriptRoot 'routing_decisions.ps1')
. (Join-Path $PSScriptRoot 'filtering.ps1')
