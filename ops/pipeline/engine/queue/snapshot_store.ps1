# ==============================================================================
# ops\pipeline\engine\queue\snapshot_store.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\pipeline_engine.ps1. Keep function names stable;
# pipeline_engine.ps1 dot-sources this file as part of the queue engine surface.
# ==============================================================================

function Invoke-MediaPipelineQueueSnapshot {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex,
        [Parameter(Mandatory)] [string] $Path,
        [switch] $NonFatal
    )

    try {
        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $QueuePlan -ProcessedIndex $ProcessedIndex
        Write-QueuePlanSnapshot -Plan $snapshot -Path $Path
        return $snapshot
    } catch {
        if ($NonFatal) {
            Write-Log "Queue snapshot write failed (non-fatal): $_" "WARN"
            return $null
        }
        throw
    }
}

function Write-QueuePlanSnapshot {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $Path
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $target = [System.IO.Path]::GetFullPath($Path)
    $targetDir = Split-Path -Parent $target
    $leaf = Split-Path -Leaf $target
    $id = [guid]::NewGuid().ToString("N")
    $tmp = Join-Path $targetDir (".$leaf.$id.tmp")
    $backup = Join-Path $targetDir (".$leaf.$id.bak")
    try {
        $json = $Plan | ConvertTo-Json -Depth 8
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        if ([System.IO.File]::Exists($target)) {
            [System.IO.File]::Replace($tmp, $target, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, $target)
        }
    } catch {
        if ($tmp -and (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        if ($backup -and (Test-Path -LiteralPath $backup -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}
