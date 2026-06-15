[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Completed manifest backfill dry-run checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$backfillScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Backfill-CompletedManifest.ps1'

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

function Assert-FileTextContains {
    param(
        [string] $Path,
        [string] $Needle,
        [string] $Message
    )
    Assert-True (Test-Path -LiteralPath $Path -PathType Leaf) "$Message Missing file: $Path"
    $text = Get-Content -LiteralPath $Path -Raw
    Assert-True ($text.Contains($Needle)) $Message
}

function New-BackfillFixture {
    param([Parameter(Mandatory = $true)][string] $Root)

    $outsource = Join-Path $Root 'outsource'
    $local = Join-Path $Root 'local'
    $movieDir = Join-Path $outsource 'Movies\Example Movie'
    New-Item -ItemType Directory -Path $movieDir, $local -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $movieDir 'Example Movie.mkv') -Value 'media' -Encoding UTF8
    [ordered]@{
        route = 'remux'
        source_path = 'E:\Incoming\Example Movie.mkv'
        output_file = 'Example Movie.mkv'
        output_size = 5
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $movieDir 'Example Movie.pipeline.json') -Encoding UTF8

    New-Item -ItemType Directory -Path `
        (Join-Path $local 'Progress'), `
        (Join-Path $local 'Completed'), `
        (Join-Path $local 'Failed\Markers'), `
        (Join-Path $local 'PendingServerPush') `
        -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $local 'Progress\queue_snapshot.json') -Value '{"schema_version":"queue_plan_snapshot.v1"}' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $local 'Completed\completed_jobs.jsonl') -Value 'legacy-completed' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $local 'Failed\Markers\failure.json') -Value '{"schema_version":"source_failure.v1"}' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $local 'PendingServerPush\parked.manifest.json') -Value '{"manifest_state":"parked"}' -Encoding UTF8

    return [pscustomobject]@{
        Outsource = $outsource
        Local = $local
    }
}

Assert-True (Test-Path -LiteralPath $backfillScript -PathType Leaf) "Backfill script missing: $backfillScript"

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-backfill-dryrun-' + [guid]::NewGuid().ToString('N'))
try {
    $fixture = New-BackfillFixture -Root $root

    & $backfillScript -OutsourceRoot $fixture.Outsource -LocalBase $fixture.Local -DryRun | Out-Null

    Assert-False (Test-Path -LiteralPath (Join-Path $fixture.Local 'State')) 'Dry run without explicit checkpoint created LocalBase\State.'
    Assert-True (Test-Path -LiteralPath (Join-Path $fixture.Local 'Progress\queue_snapshot.json') -PathType Leaf) 'Dry run moved legacy Progress state.'
    Assert-FileTextContains -Path (Join-Path $fixture.Local 'Completed\completed_jobs.jsonl') -Needle 'legacy-completed' -Message 'Dry run modified or moved legacy completed manifest.'
    Assert-True (Test-Path -LiteralPath (Join-Path $fixture.Local 'Failed\Markers\failure.json') -PathType Leaf) 'Dry run moved legacy Failed state.'
    Assert-True (Test-Path -LiteralPath (Join-Path $fixture.Local 'PendingServerPush\parked.manifest.json') -PathType Leaf) 'Dry run moved legacy PendingServerPush state.'
    Assert-False (Test-Path -LiteralPath (Join-Path $fixture.Local 'State\Completed\completed_manifest_backfill_progress.json')) 'Dry run wrote the default state checkpoint.'

    $checkpoint = Join-Path $root 'RunLogs\backfill_checkpoint.json'
    & $backfillScript -OutsourceRoot $fixture.Outsource -LocalBase $fixture.Local -DryRun -CheckpointPath $checkpoint | Out-Null
    Assert-True (Test-Path -LiteralPath $checkpoint -PathType Leaf) 'Dry run did not write explicit checkpoint.'
    $checkpointPayload = Get-Content -LiteralPath $checkpoint -Raw | ConvertFrom-Json
    Assert-True ($checkpointPayload.status -eq 'dry_run_completed') 'Explicit checkpoint status is not dry_run_completed.'
    Assert-True ([bool]$checkpointPayload.dry_run) 'Explicit checkpoint did not record dry_run=true.'
    Assert-False (Test-Path -LiteralPath (Join-Path $fixture.Local 'State')) 'Dry run with external checkpoint created LocalBase\State.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Completed manifest backfill dry-run checks passed.'
