<#
.SYNOPSIS
Rapid-deployment setup and validation wizard for the patched MediaPipeline bundle.

.DESCRIPTION
Creates or updates the active MediaPipeline_config.psd1, validates the
deployment surface, and keeps advanced keys from an existing config intact.
By default this uses the same durable per-user config location as the Local API
when %LOCALAPPDATA% is available, falling back to the bundle-local config path.

Designed for first-time setup on a new PC and for later re-validation after a
machine move, dependency change, or manual config edit.

.PARAMETER ValidateOnly
Loads the current config and runs validation without changing it.

.PARAMETER DryRun
Builds the config content and shows a preview without writing it to disk.

.PARAMETER AcceptDefaults
Runs non-interactively for any prompt that already has a default value. Useful
for rapid deployment when folder paths are preseeded on the command line.

.PARAMETER ConfigPath
Optional explicit path to the config file to read or write.

.PARAMETER SourceMovies
Optional preset for the movie source folder.

.PARAMETER SourceTV
Optional preset for the TV source folder.

.PARAMETER Outsource
Optional preset for the final output folder.

.PARAMETER LocalBase
Optional preset for the local scratch folder.

.PARAMETER OpenConfig
Opens the written config in the default editor after a successful write.

.PARAMETER ReportPath
Optional path for a text validation report. When omitted, no report file is written.

.PARAMETER ListDefaults
Prints the current default config template and exits.

.EXAMPLE
.\ops\scripts\dev\setup.bat

Runs the interactive setup wizard from the repository root.

.EXAMPLE
.\ops\scripts\dev\setup.bat -ValidateOnly

Validates the existing config and environment only.

.EXAMPLE
.\ops\scripts\dev\setup.bat `
    -SourceMovies 'D:\Incoming\Movies' `
    -SourceTV 'D:\Incoming\TV' `
    -Outsource '\\NAS\Plex\Library' `
    -LocalBase 'E:\MediaScratch' `
    -AcceptDefaults

Runs a fast first-pass deployment using the recommended defaults for everything
except the key folder paths.
#>
[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$DryRun,
    [switch]$AcceptDefaults,
    [switch]$OpenConfig,
    [switch]$ListDefaults,
    [string]$ReportPath,
    [string]$ConfigPath,
    [string]$SourceMovies,
    [string]$SourceTV,
    [string]$Outsource,
    [string]$LocalBase
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Normalize-UserPath {
    param(
        [Parameter(Mandatory = $false)]
        [string]$Path,
        [string]$BasePath = (Get-Location).Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }

    $trimmed = $Path.Trim().Trim('"').Trim("'")
    $expanded = [Environment]::ExpandEnvironmentVariables($trimmed)

    if ($expanded.StartsWith('\\')) {
        return $expanded.TrimEnd('\','/')
    }

    try {
        return [System.IO.Path]::GetFullPath($expanded, $BasePath).TrimEnd('\','/')
    } catch {
        try {
            return [System.IO.Path]::GetFullPath($expanded).TrimEnd('\','/')
        } catch {
            return $expanded.TrimEnd('\','/')
        }
    }
}

function Get-SetupConfigCandidatePaths {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigDir,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $candidates = [System.Collections.Generic.List[string]]::new()
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $userConfigDir = Join-Path $env:LOCALAPPDATA 'MediaPipelineRemuxEncodeAIO'
        [void]$candidates.Add((Join-Path $userConfigDir 'MediaPipeline_config.psd1'))
        [void]$candidates.Add((Join-Path $userConfigDir 'MediaPipeline_config_chatgpt.psd1'))
    }

    [void]$candidates.Add((Join-Path $ConfigDir 'MediaPipeline_config.psd1'))

    $desktopConfigDir = Join-Path $RepoRoot 'apps\desktop\config'
    [void]$candidates.Add((Join-Path $desktopConfigDir 'MediaPipeline_config.psd1'))

    [void]$candidates.Add((Join-Path $ConfigDir 'MediaPipeline_config_chatgpt.psd1'))
    [void]$candidates.Add((Join-Path $desktopConfigDir 'MediaPipeline_config_chatgpt.psd1'))

    $unique = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $normalized = Normalize-UserPath -Path $candidate -BasePath $RepoRoot
        $alreadySeen = $false
        foreach ($item in $unique) {
            if ([string]::Equals($item, $normalized, [System.StringComparison]::OrdinalIgnoreCase)) {
                $alreadySeen = $true
                break
            }
        }
        if (-not $alreadySeen) {
            [void]$unique.Add($normalized)
        }
    }
    return @($unique)
}

function Resolve-SetupDefaultConfigPath {
    param(
        [Parameter(Mandatory = $true)][string]$ConfigDir,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $candidates = @(Get-SetupConfigCandidatePaths -ConfigDir $ConfigDir -RepoRoot $RepoRoot)
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $candidates[0]
}

$script:InvariantCulture = [System.Globalization.CultureInfo]::InvariantCulture
$script:ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$script:PipelineRoot = Split-Path -Parent $script:ScriptDir
$script:RepoRoot = Split-Path -Parent (Split-Path -Parent $script:PipelineRoot)
$script:ConfigDir = Join-Path $script:PipelineRoot 'config'
$script:ConfigPath = if ($ConfigPath) {
    Normalize-UserPath -Path $ConfigPath -BasePath $script:ScriptDir
} else {
    Resolve-SetupDefaultConfigPath -ConfigDir $script:ConfigDir -RepoRoot $script:RepoRoot
}
$script:PipelinePath = Join-Path $script:ScriptDir 'MediaPipeline.ps1'
$script:SubtitlePath = Join-Path $script:RepoRoot 'src\mediapipeline\pipeline\ass_to_srt_cli.py'
$script:UseAcceptDefaults = [bool]$AcceptDefaults

$configSchemaModule = Join-Path $script:PipelineRoot 'engine\config\config_schema.ps1'
if (-not (Test-Path -LiteralPath $configSchemaModule)) {
    throw "Required config schema module not found: $configSchemaModule"
}
. $configSchemaModule

$script:RequiredKeys = @(Get-MediaPipelineConfigRequiredKeys)
$script:ConfigOrder = @(Get-MediaPipelineConfigOrderedKeys)

$script:SetupSliceDir = Join-Path $script:ConfigDir 'setup'
$script:SetupSlices = @(
    'UserInteraction.ps1',
    'Dependencies.ps1',
    'PathValidation.ps1',
    'ConfigFile.ps1',
    'Validation.ps1'
)
foreach ($setupSlice in $script:SetupSlices) {
    $setupSlicePath = Join-Path $script:SetupSliceDir $setupSlice
    if (-not (Test-Path -LiteralPath $setupSlicePath)) {
        throw "Required setup helper slice not found: $setupSlicePath"
    }
    . $setupSlicePath
}

function Invoke-Main {
Write-Header 'MediaPipelineRemuxEncodeAIO Deployment'
    Write-Info 'This setup script writes the active operator config using the same per-user-first location order as the Local API.'
    Write-Info "Selected config path: $script:ConfigPath"

    if ($ListDefaults) {
        Write-Header 'Default Config'
        Write-Host (Format-ConfigFile -Config (Get-DefaultConfig))
        return 0
    }

    $readResult = Read-ExistingConfig -Path $script:ConfigPath
    $existing = $readResult.Result
    if ($readResult.ParseFailed) {
        Write-Warn 'Existing config could not be parsed cleanly. Running the wizard will rebuild it from known values and keep any remaining manual keys only if they were parseable.'
    }

    if ($ValidateOnly) {
        if (-not (Test-Path -LiteralPath $script:ConfigPath)) {
            Write-Fail "Config file not found: $script:ConfigPath"
            Write-Info 'Checked config candidates:'
            foreach ($candidate in @(Get-SetupConfigCandidatePaths -ConfigDir $script:ConfigDir -RepoRoot $script:RepoRoot)) {
                Write-Info "  $candidate"
            }
            Write-Info "Run ops\scripts\dev\setup.bat from the repository root to create it."
            return 1
        }
        $result = Invoke-Validation -Config $existing
        if ($ReportPath) {
            Write-ValidationReport -Path $ReportPath -Result $result -Config $existing
        }
        return $(if ($result.Ok) { 0 } else { 1 })
    }

    if ($existing.Count -gt 0 -and -not $script:UseAcceptDefaults) {
        Write-Host ''
        Write-Host "Existing config found: $script:ConfigPath" -ForegroundColor Yellow
        Write-Host '  1. Edit and rewrite the config'
        Write-Host '  2. Validate only'
        $mode = Read-Choice -Prompt 'Choice' -Options @('Edit','Validate') -Default 1
        if ($mode -eq 2) {
            $result = Invoke-Validation -Config $existing
            return $(if ($result.Ok) { 0 } else { 1 })
        }
    }

    $config = Invoke-ConfigWizard -Existing $existing
    $content = Format-ConfigFile -Config $config

    if ($DryRun) {
        Write-Header 'Dry Run Preview'
        ($content -split "`r?`n") | Select-Object -First 60 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
        Write-Host '...'
        $previewResult = Invoke-Validation -Config $config
        if ($ReportPath) {
            Write-ValidationReport -Path $ReportPath -Result $previewResult -Config $config
        }
        return $(if ($previewResult.Ok) { 0 } else { 1 })
    }

    $backupPath = Invoke-ConfigBackup -Path $script:ConfigPath -Keep 5
    if ($backupPath) {
        Write-Ok "Backed up existing config to $backupPath"
    }
    Write-ConfigFile -Path $script:ConfigPath -Content $content
    Write-Ok "Wrote $script:ConfigPath"
    $writtenConfig = (Import-PowerShellDataFile -LiteralPath $script:ConfigPath)
    $result = Invoke-Validation -Config $writtenConfig
    if ($ReportPath) {
        Write-ValidationReport -Path $ReportPath -Result $result -Config $writtenConfig
    }
    Initialize-ProgressSkeleton -Config $writtenConfig
    if ($OpenConfig) {
        Open-ConfigFile -Path $script:ConfigPath
    }
    Show-Closing -ConfigPathValue $script:ConfigPath -BackupPath $backupPath -ReportPathValue $ReportPath
    return $(if ($result.Ok) { 0 } else { 1 })
}

try {
    exit (Invoke-Main)
} catch {
    Write-Host ''
    Write-Fail "Setup failed: $_"
    if ($_.ScriptStackTrace) {
        Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
    }
    exit 1
}
