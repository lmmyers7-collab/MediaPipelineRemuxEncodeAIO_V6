[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Rerun PlanOnly checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$rerunScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Invoke-RerunCsv.ps1'

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-False {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if ($Condition) { throw $Message }
}

Assert-True (Test-Path -LiteralPath $rerunScript -PathType Leaf) "Rerun script missing: $rerunScript"

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-rerun-planonly-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $source = Join-Path $root 'Movie Source 1080p HEVC.mkv'
    Set-Content -LiteralPath $source -Value 'media' -Encoding ASCII

    $config = Join-Path $root 'config.psd1'
    $escapedRoot = $root.Replace("'", "''")
    @"
@{
    LocalBase = '$escapedRoot\Local'
    Outsource = '$escapedRoot\Out'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
}
"@ | Set-Content -LiteralPath $config -Encoding UTF8

    $csv = Join-Path $root 'rerun.csv'
    @"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,"$source",Movie,copy,keep,park
"@ | Set-Content -LiteralPath $csv -Encoding UTF8

    $output = & $rerunScript -CsvPath $csv -ConfigPath $config -PlanOnly -DefaultReturnMode park *>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Rerun PlanOnly check failed with exit $LASTEXITCODE. Output: $output" }

    Assert-True ($output -match 'PLAN ONLY complete') 'PlanOnly did not report a plan-only completion.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local') -PathType Container) 'PlanOnly created LocalBase.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Out') -PathType Container) 'PlanOnly created Outsource.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunManifests') -PathType Container) 'PlanOnly created RerunManifests.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunQueue') -PathType Container) 'PlanOnly created RerunQueue.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunParked') -PathType Container) 'PlanOnly created RerunParked.'
    Assert-True (Test-Path -LiteralPath $source -PathType Leaf) 'PlanOnly removed or moved the source media.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Rerun PlanOnly checks passed.'
