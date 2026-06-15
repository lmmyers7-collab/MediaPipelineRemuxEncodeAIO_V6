[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\executable_resolution.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\dynamic_hdr.ps1')

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-dynamic-hdr-tools-" + [guid]::NewGuid().ToString('N'))
$oldPath = [string]$env:PATH
try {
    $repoRootForModules = Join-Path $tempRoot 'repo'
    $scriptDir = Join-Path $repoRootForModules 'ops\pipeline\entrypoints'
    $bundledDoviDir = Join-Path $repoRootForModules 'ops\pipeline\tools\dovi_tool'
    $bundledHdr10PlusDir = Join-Path $repoRootForModules 'ops\pipeline\tools\hdr10plus_tool'
    $customDir = Join-Path $tempRoot 'custom'
    $systemDir = Join-Path $tempRoot 'system'
    New-Item -ItemType Directory -Force -Path $scriptDir, $bundledDoviDir, $bundledHdr10PlusDir, $customDir, $systemDir | Out-Null

    $customDovi = Join-Path $customDir 'dovi_tool.exe'
    $bundledDovi = Join-Path $bundledDoviDir 'dovi_tool.exe'
    $bundledHdr10Plus = Join-Path $bundledHdr10PlusDir 'hdr10plus_tool.exe'
    $systemHdr10Plus = Join-Path $systemDir 'hdr10plus_tool.cmd'
    Set-Content -LiteralPath $customDovi -Value 'custom dovi tool' -Encoding ASCII
    Set-Content -LiteralPath $bundledDovi -Value 'bundled dovi tool' -Encoding ASCII
    Set-Content -LiteralPath $bundledHdr10Plus -Value 'bundled hdr10plus tool' -Encoding ASCII
    Set-Content -LiteralPath $systemHdr10Plus -Value '@echo off' -Encoding ASCII

    $script:AllowSystemTools = $false

    $configResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'dovi_tool' `
        -ConfiguredPath $customDovi `
        -RelativeCandidates @('..\tools\dovi_tool\dovi_tool.exe')
    Assert-Equal $configResolution.Source 'config' 'Configured dovi_tool path should win over bundled path.'
    Assert-Equal $configResolution.Path (Resolve-Path -LiteralPath $customDovi).Path 'Configured dovi_tool path mismatch.'

    $bundledResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'dovi_tool' `
        -ConfiguredPath '' `
        -RelativeCandidates @('..\tools\dovi_tool\dovi_tool.exe')
    Assert-Equal $bundledResolution.Source 'bundled' 'Bundled dovi_tool should win when no config override exists.'
    Assert-Equal $bundledResolution.Path (Resolve-Path -LiteralPath $bundledDovi).Path 'Bundled dovi_tool path mismatch.'

    Remove-Item -LiteralPath $bundledHdr10Plus -Force
    $env:PATH = "$systemDir$([System.IO.Path]::PathSeparator)$oldPath"
    $systemResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'hdr10plus_tool' `
        -ConfiguredPath '' `
        -RelativeCandidates @('..\tools\hdr10plus_tool\hdr10plus_tool.exe') `
        -AllowSystemTools
    Assert-Equal $systemResolution.Source 'system' 'AllowSystemTools should allow PATH fallback after bundled lookup.'
    Assert-True ([string]$systemResolution.Path -like '*hdr10plus_tool.cmd') 'System hdr10plus_tool path should resolve to the PATH command.'

    $env:PATH = $oldPath
    $missingResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'hdr10plus_tool' `
        -ConfiguredPath '' `
        -RelativeCandidates @('..\tools\hdr10plus_tool\hdr10plus_tool.exe')
    Assert-Equal $missingResolution.Source 'missing' 'Missing hdr10plus_tool should be nonfatal and marked missing.'
    Assert-True ([string]$missingResolution.Reason -match 'AllowSystemTools is false') 'Missing-tool reason should mention disabled PATH fallback.'

    Assert-Equal (ConvertFrom-DynamicHdrToolVersionText -Text 'dovi_tool 2.3.2') '2.3.2' 'dovi_tool version parsing failed.'
    Assert-Equal (ConvertFrom-DynamicHdrToolVersionText -Text "hdr10plus_tool v1.7.2`n") '1.7.2' 'hdr10plus_tool version parsing failed.'
    Assert-Equal (ConvertFrom-DynamicHdrToolVersionText -Text 'not a version') '' 'Unversioned output should return blank version.'

    $availability = Test-DynamicHdrToolsAvailable -DoviToolPath '' -Hdr10PlusToolPath ''
    Assert-True (-not [bool]$availability.AnyToolAvailable) 'Missing dynamic HDR tools should not report availability.'

    Clear-DynamicHdrCapabilityProbe
    $missingFfmpegA = Join-Path $tempRoot 'missing-a\ffmpeg.exe'
    $missingFfmpegB = Join-Path $tempRoot 'missing-b\ffmpeg.exe'
    $firstCapability = Test-X265DynamicHdrCapability -FfmpegPath $missingFfmpegA
    $cachedCapability = Test-X265DynamicHdrCapability -FfmpegPath $missingFfmpegB
    Assert-Equal $cachedCapability.FfmpegPath $missingFfmpegA 'Capability probe should return cached answer without Force.'
    Assert-True ([string]$cachedCapability.Reason -match 'ffmpeg not found') 'Capability cache should keep missing-ffmpeg reason.'
    $forcedCapability = Test-X265DynamicHdrCapability -FfmpegPath $missingFfmpegB -Force
    Assert-Equal $forcedCapability.FfmpegPath $missingFfmpegB 'Capability probe should refresh when Force is supplied.'
} finally {
    $env:PATH = $oldPath
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'Dynamic HDR tooling checks passed.'
