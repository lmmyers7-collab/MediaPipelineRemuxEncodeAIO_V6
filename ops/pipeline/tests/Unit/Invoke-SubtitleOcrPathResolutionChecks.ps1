[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..'))

. (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\common.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\bdpgs.ps1')
. (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\vobsub.ps1')

$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-subtitle-ocr-paths-" + [guid]::NewGuid().ToString("N"))
try {
    $fakeRepoRoot = Join-Path $workRoot 'repo'
    $fakePipelineRoot = Join-Path $fakeRepoRoot 'ops\pipeline'
    $fakeEntryPointRoot = Join-Path $fakePipelineRoot 'entrypoints'
    $fakePgsTool = Join-Path $fakePipelineRoot 'tools\PgsToSrt\PgsToSrt.exe'
    $fakeVobSubTool = Join-Path $fakePipelineRoot 'tools\SubtitleEditLegacy\SubtitleEdit.exe'

    New-Item -ItemType Directory -Path $fakeEntryPointRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $fakePgsTool) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $fakeVobSubTool) -Force | Out-Null
    Set-Content -LiteralPath $fakePgsTool -Value 'fake pgs tool' -Encoding ASCII
    Set-Content -LiteralPath $fakeVobSubTool -Value 'fake vobsub tool' -Encoding ASCII

    $scriptDir = $fakeEntryPointRoot
    $script:pipelineRoot = $fakePipelineRoot
    $script:repoRootForModules = $fakeRepoRoot
    $script:AllowSystemTools = $false

    $resolvedPgs = Resolve-SubtitleConfiguredPath -PathValue 'Tools\PgsToSrt\PgsToSrt.exe'
    Assert-True ([string]::Equals($resolvedPgs, (Resolve-Path -LiteralPath $fakePgsTool).Path, [System.StringComparison]::OrdinalIgnoreCase)) 'Saved BDPGS OCR path did not resolve from promoted pipeline tools.'

    $script:BdpgsOcrToolPath = 'Tools\PgsToSrt\PgsToSrt.exe'
    $bdpgs = Resolve-BdpgsOcrToolInvocation
    Assert-True ([bool]$bdpgs.Ok) ("BDPGS OCR tool invocation failed: {0}" -f $bdpgs.Reason)
    Assert-True ([string]::Equals([string]$bdpgs.FilePath, (Resolve-Path -LiteralPath $fakePgsTool).Path, [System.StringComparison]::OrdinalIgnoreCase)) 'BDPGS OCR invocation did not use the promoted bundled tool path.'

    $script:VobSubOcrToolPath = 'Tools\SubtitleEditLegacy\SubtitleEdit.exe'
    $vobsub = Resolve-VobSubOcrToolInvocation
    Assert-True ([bool]$vobsub.Ok) ("VobSub OCR tool invocation failed: {0}" -f $vobsub.Reason)
    Assert-True ([string]::Equals([string]$vobsub.FilePath, (Resolve-Path -LiteralPath $fakeVobSubTool).Path, [System.StringComparison]::OrdinalIgnoreCase)) 'VobSub OCR invocation did not use the promoted bundled tool path.'

    Write-Host 'Subtitle OCR promoted path resolution checks passed.'
} finally {
    if (Test-Path -LiteralPath $workRoot -ErrorAction SilentlyContinue) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
}
