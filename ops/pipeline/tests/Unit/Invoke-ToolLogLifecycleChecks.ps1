[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected' but got '$Actual'." }
}

function Assert-PathUnderRoot {
    param([string] $Path, [string] $Root, [string] $Message)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Message Path '$fullPath' is outside '$fullRoot'."
    }
}

. (Join-Path $repoRoot 'ops\pipeline\engine\storage\state_store.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\queue\worker_claim_store.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\tool_log_lifecycle.ps1')

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-tool-log-lifecycle-{0}" -f ([guid]::NewGuid().ToString('N')))
$now = [datetime]'2026-07-15T12:00:00Z'

try {
    $layout = Initialize-MediaPipelineStateLayout -Layout (New-MediaPipelineStateLayout -LocalBase $tempRoot)
    Assert-PathUnderRoot -Path $layout.ToolLogs -Root $layout.Pipeline -Message 'Tool log root must remain pipeline-owned state.'
    Assert-True (Test-Path -LiteralPath $layout.ActiveToolLogs -PathType Container) 'Active tool-log directory was not initialized.'
    Assert-True (Test-Path -LiteralPath $layout.InterruptedToolLogs -PathType Container) 'Interrupted tool-log directory was not initialized.'

    $slot = Initialize-MediaPipelineWorkerSlotLayout -SlotLayout (New-MediaPipelineWorkerSlotLayout -StateLayout $layout -SlotId 1)
    Assert-True (Test-Path -LiteralPath $slot.ActiveToolLogs -PathType Container) 'Worker active tool-log directory was not initialized.'
    Assert-True (Test-Path -LiteralPath $slot.InterruptedToolLogs -PathType Container) 'Worker interrupted tool-log directory was not initialized.'

    $successCapture = New-MediaPipelineToolLogCapture -ToolName 'ffmpeg' -ActiveDirectory $layout.ActiveToolLogs -RunId 'run-success' -Now $now
    Set-Content -LiteralPath $successCapture -Value 'success output'
    $success = Complete-MediaPipelineToolLogCapture -Path $successCapture -Disposition 'success' -FailureDirectory $layout.FailureArtifacts -InterruptedDirectory $layout.InterruptedToolLogs -Now $now
    Assert-Equal ([string]$success.Disposition) 'deleted' 'Successful native-tool capture disposition changed.'
    Assert-True (-not (Test-Path -LiteralPath $successCapture)) 'Successful native-tool capture was not deleted.'

    $failureCapture = New-MediaPipelineToolLogCapture -ToolName 'ffmpeg' -ActiveDirectory $layout.ActiveToolLogs -RunId 'run-failure' -Now $now
    Set-Content -LiteralPath $failureCapture -Value 'failure output'
    $failure = Complete-MediaPipelineToolLogCapture -Path $failureCapture -Disposition 'failure' -FailureDirectory $layout.FailureArtifacts -InterruptedDirectory $layout.InterruptedToolLogs -Now $now
    Assert-Equal ([string]$failure.Disposition) 'failure' 'Failed native-tool capture disposition changed.'
    Assert-PathUnderRoot -Path $failure.Path -Root $layout.FailureArtifacts -Message 'Failed native-tool capture must be promoted into failure artifacts.'
    Assert-True (Test-Path -LiteralPath $failure.Path -PathType Leaf) 'Promoted native-tool failure capture is missing.'

    $stopCapture = New-MediaPipelineToolLogCapture -ToolName 'ffmpeg' -ActiveDirectory $layout.ActiveToolLogs -RunId 'run-stop' -Now $now
    Set-Content -LiteralPath $stopCapture -Value 'stopped output'
    $stopped = Complete-MediaPipelineToolLogCapture -Path $stopCapture -Disposition 'interrupted' -FailureDirectory $layout.FailureArtifacts -InterruptedDirectory $layout.InterruptedToolLogs -Now $now
    Assert-Equal ([string]$stopped.Disposition) 'interrupted' 'Interrupted native-tool capture disposition changed.'
    Assert-PathUnderRoot -Path $stopped.Path -Root $layout.InterruptedToolLogs -Message 'Interrupted native-tool capture must stay outside failure artifacts.'
    Assert-True (Test-Path -LiteralPath $stopped.Path -PathType Leaf) 'Interrupted native-tool capture is missing.'

    $orphan = New-MediaPipelineToolLogCapture -ToolName 'ffmpeg' -ActiveDirectory $layout.ActiveToolLogs -RunId 'run-orphan' -Now $now.AddDays(-1)
    Set-Content -LiteralPath $orphan -Value 'orphan output'
    (Get-Item -LiteralPath $orphan).LastWriteTimeUtc = $now.AddDays(-1)
    $expired = Join-Path $layout.InterruptedToolLogs 'ffmpeg_interrupted_expired.log'
    Set-Content -LiteralPath $expired -Value 'expired output'
    (Get-Item -LiteralPath $expired).LastWriteTimeUtc = $now.AddDays(-4)
    $recent = Join-Path $layout.InterruptedToolLogs 'ffmpeg_interrupted_recent.log'
    Set-Content -LiteralPath $recent -Value 'recent output'
    (Get-Item -LiteralPath $recent).LastWriteTimeUtc = $now.AddDays(-2)

    $maintenance = Invoke-MediaPipelineToolLogMaintenance -ActiveDirectory $layout.ActiveToolLogs -InterruptedDirectory $layout.InterruptedToolLogs -RetentionDays 3 -Now $now
    Assert-Equal ([int]$maintenance.OrphanedCount) 1 'Startup maintenance did not reconcile the orphaned active capture.'
    Assert-Equal ([int]$maintenance.DeletedCount) 1 'Three-day interrupted-log retention did not delete exactly one expired capture.'
    Assert-True (-not (Test-Path -LiteralPath $orphan)) 'Orphaned active capture remained in the active directory.'
    Assert-True (-not (Test-Path -LiteralPath $expired)) 'Expired interrupted capture was retained past three days.'
    Assert-True (Test-Path -LiteralPath $recent -PathType Leaf) 'Recent interrupted capture was deleted too early.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'Tool log lifecycle checks passed.'
