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

    $baseDir = if ($scriptDir) { $scriptDir } elseif ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
    $candidate = Join-Path $baseDir $raw
    if (Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue) {
        return (Resolve-Path -LiteralPath $candidate).Path
    }

    if ($AllowCommandLookup -and $script:AllowSystemTools) {
        $cmd = Get-Command $raw -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd -and $cmd.Source) { return $cmd.Source }
    }

    try { return [System.IO.Path]::GetFullPath($candidate) } catch { return $candidate }
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
