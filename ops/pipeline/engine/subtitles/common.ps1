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
        [int]$StreamIndex = -1,
        [string]$Stage,
        [string]$Status,
        [int]$StepIndex = 0,
        [int]$StepTotal = 4,
        [array]$Steps = @('extract','convert_ocr','validate','sidecar_write'),
        [string]$Detail = "",
        [object]$CueCount = $null,
        [switch]$Completed,
        [switch]$Failed
    )

    if (Get-Command -Name Set-ProgressSubtitleTrack -ErrorAction SilentlyContinue) {
        Set-ProgressSubtitleTrack `
            -Kind $Kind `
            -StreamIndex $StreamIndex `
            -Stage $Stage `
            -Status $Status `
            -StepIndex $StepIndex `
            -StepTotal $StepTotal `
            -Steps $Steps `
            -Detail $Detail `
            -CueCount $CueCount `
            -Completed:$Completed `
            -Failed:$Failed `
            -SaveNow
    }
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
