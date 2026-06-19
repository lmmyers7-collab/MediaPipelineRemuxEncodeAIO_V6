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

    $warnPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy warn `
        -DoviPresent:$true `
        -DoviProfile 8 `
        -DoviBlCompatId 1
    Assert-Equal $warnPlan.Action 'warn_only' 'Warn policy should not change encode routing.'
    Assert-Equal $warnPlan.recommended_route 'encode' 'Warn policy should keep encode route.'
    Assert-True (-not [bool]$warnPlan.can_preserve_encode) 'Warn policy should not claim encode preservation.'

    $remuxPlan = New-DynamicHdrPreservationPlan `
        -Route remux `
        -Policy preserve_or_review `
        -Hdr10PlusPresent:$true
    Assert-Equal $remuxPlan.Action 'preserve_by_remux' 'Remux should be the preservation path for dynamic HDR metadata.'
    Assert-Equal $remuxPlan.recommended_route 'remux' 'Remux preservation should recommend remux.'

    $profile5RemuxPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_remux `
        -DoviPresent:$true `
        -DoviProfile 5
    Assert-Equal $profile5RemuxPlan.Action 'prefer_remux' 'Unsupported DoVi encode profile should prefer remux under preserve_or_remux.'
    Assert-Equal $profile5RemuxPlan.recommended_route 'remux' 'Unsupported DoVi profile should recommend remux for preserve_or_remux.'
    Assert-True ((@($profile5RemuxPlan.Reasons) -join '; ') -match 'profile 5') 'Unsupported DoVi plan should name the profile.'

    $profile5ReviewPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_review `
        -DoviPresent:$true `
        -DoviProfile 5
    Assert-Equal $profile5ReviewPlan.Action 'hold_review' 'Unsupported DoVi encode profile should hold review under preserve_or_review.'
    Assert-Equal $profile5ReviewPlan.recommended_route 'review' 'Unsupported DoVi profile should recommend review for preserve_or_review.'

    $missingPrereqPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_review `
        -DoviPresent:$true `
        -DoviProfile 8 `
        -DoviBlCompatId 1 `
        -Hdr10PlusPresent:$true `
        -VideoCodec hevc_nvenc
    Assert-Equal $missingPrereqPlan.Action 'hold_review' 'Missing tools/capabilities should hold review for preserve_or_review.'
    $missingPrereqReasons = @($missingPrereqPlan.Reasons) -join '; '
    Assert-True ($missingPrereqReasons -match 'CPU x265') 'Missing prerequisite plan should require CPU x265.'
    Assert-True ($missingPrereqReasons -match 'dovi_tool') 'Missing prerequisite plan should require dovi_tool.'
    Assert-True ($missingPrereqReasons -match 'hdr10plus_tool') 'Missing prerequisite plan should require hdr10plus_tool.'

    $encodePreservePlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_review `
        -DoviPresent:$true `
        -DoviProfile 7 `
        -DoviElPresent:$true `
        -Hdr10PlusPresent:$true `
        -DoviToolAvailable:$true `
        -Hdr10PlusToolAvailable:$true `
        -X265DolbyVisionCapable:$true `
        -X265Hdr10PlusCapable:$true `
        -UseCpuFallback:$true
    Assert-Equal $encodePreservePlan.Action 'preserve_encode' 'Satisfied prerequisites should allow encode preservation planning.'
    Assert-True ([bool]$encodePreservePlan.can_preserve_encode) 'Satisfied prerequisites should mark encode preservation possible.'
    Assert-Equal $encodePreservePlan.target_dovi_profile '8.1' 'DoVi P7 encode preservation should target profile 8.1.'
    $artifactText = @($encodePreservePlan.required_artifacts) -join '; '
    Assert-True ($artifactText -match 'dovi_rpu_converted_profile_8_1') 'DoVi P7 plan should require converted RPU artifact.'
    Assert-True ($artifactText -match 'hdr10plus_json') 'HDR10+ plan should require metadata JSON artifact.'
} finally {
    $env:PATH = $oldPath
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'Dynamic HDR tooling checks passed.'
