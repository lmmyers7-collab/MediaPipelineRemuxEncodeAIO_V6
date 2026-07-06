[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Rerun cooperative-stop checks require PowerShell 7. Install pwsh or use the bundled runtime."
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
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Match {
    param([string] $Text, [string] $Pattern, [string] $Message)
    if ($Text -notmatch $Pattern) { throw $Message }
}

Assert-True (Test-Path -LiteralPath $rerunScript -PathType Leaf) "Rerun script missing: $rerunScript"

$text = Get-Content -LiteralPath $rerunScript -Raw

Assert-Match $text 'function Get-RerunStopAfterCurrentRequest' 'Stop marker reader is missing.'
Assert-Match $text 'function Update-RerunManifestCounts' 'Manifest count helper is missing.'
Assert-Match $text 'Join-Path\s+\$localBase\s+''State\\Rerun\\Control''' 'Stop marker must live under LocalBase State\Rerun\Control.'
Assert-Match $text 'Join-Path\s+\$rerunControlRoot\s+''stop_after_current\.json''' 'Stop marker filename is not pinned.'
Assert-Match $text 'row_index = \$rowIndex' 'Rerun plans must preserve original CSV row indexes for pending-only continuation.'
Assert-Match $text "action.*stop_after_current" 'Stop marker action check is missing.'
Assert-Match $text "(?s)MarkerPath.*BatchId.*ManifestPath.*CsvPath.*StartedAtUtc" 'Stop marker check must compare batch, manifest, CSV, and start time.'
Assert-Match $text "(?s)markerBatchId.*-ne.*BatchId" 'Stale marker batch mismatch guard is missing.'
Assert-Match $text "(?s)markerManifestPath.*Get-RerunNormalizedPathKey.*ManifestPath" 'Stale marker manifest mismatch guard is missing.'
Assert-Match $text "(?s)markerCsvPath.*Get-RerunNormalizedPathKey.*CsvPath" 'Stale marker CSV mismatch guard is missing.'
Assert-Match $text "(?s)createdAt.*-lt.*StartedAtUtc\.AddSeconds" 'Stale marker timestamp guard is missing.'
Assert-Match $text "status = 'stopped_after_current'" 'Stopped-after-current manifest status is missing.'
Assert-Match $text "current_phase = 'stopped_after_current'" 'Stopped-after-current phase is missing.'
Assert-Match $text 'remaining_pending_count' 'Remaining pending count evidence is missing.'
Assert-Match $text 'stop_request_id' 'Stop request id evidence is missing.'
Assert-Match $text 'safe_next_action' 'Safe next action evidence is missing.'
Assert-Match $text 'Continue Pending Rows' 'Operator safe-next-action copy is missing.'
Assert-Match $text 'exit 0' 'Cooperative stop should exit successfully after writing terminal evidence.'

$chunkCompletePattern = "(?s)chunk_\$\{chunkIndex\}_complete.*?Write-RerunManifest.*?Get-RerunStopAfterCurrentRequest.*?status = 'stopped_after_current'"
Assert-Match $text $chunkCompletePattern 'Stop marker check must run only after chunk completion and manifest write.'

$noRunnableChunkPattern = "(?s)has no staged rows; skipping nested pipeline.*?chunk_\$\{chunkIndex\}_complete.*?Write-RerunManifest.*?Get-RerunStopAfterCurrentRequest"
Assert-Match $text $noRunnableChunkPattern 'No-runnable chunk path must still honor stop-after-current after writing manifest evidence.'

$planOnlyPattern = '(?s)if \(\$PlanOnly\).*?PLAN ONLY complete.*?exit 0.*?\$rerunStartedAtUtc'
Assert-Match $text $planOnlyPattern 'PlanOnly should exit before rerun control marker/workspace handling.'

Write-Host 'Rerun cooperative-stop checks passed.'
