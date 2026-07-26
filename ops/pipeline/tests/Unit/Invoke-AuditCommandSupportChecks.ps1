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

. (Join-Path $projectRoot 'ops\pipeline\engine\audit\command_support.ps1')

$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-audit-command-support-" + [guid]::NewGuid().ToString('N'))
try {
    $fakePipelineRoot = Join-Path $workRoot 'ops\pipeline'
    $fakeFfprobe = Join-Path $fakePipelineRoot 'tools\ffmpeg\bin\ffprobe.exe'
    New-Item -ItemType Directory -Path (Split-Path -Parent $fakeFfprobe) -Force | Out-Null
    Set-Content -LiteralPath $fakeFfprobe -Value 'fake ffprobe' -Encoding ASCII

    $script:PipelineRoot = $fakePipelineRoot
    $script:AuditAllowSystemTools = $false

    $resolvedFfprobe = Resolve-ExecutablePath `
        -Name 'ffprobe' `
        -RelativeCandidates @('..\tools\ffmpeg\bin\ffprobe.exe', 'Tools\ffmpeg\bin\ffprobe.exe')

    Assert-True `
        ([string]::Equals($resolvedFfprobe, (Resolve-Path -LiteralPath $fakeFfprobe).Path, [System.StringComparison]::OrdinalIgnoreCase)) `
        'Audit executable resolution did not use the promoted pipeline root for the bundled ffprobe path.'

    Write-Host 'Audit command support checks passed.'
} finally {
    if (Test-Path -LiteralPath $workRoot -ErrorAction SilentlyContinue) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
}
