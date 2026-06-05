# ==============================================================================
# Backfill-CompletedManifest.ps1
# ------------------------------------------------------------------------------
# One-time (or occasional) backfill of the local completed-jobs manifest from
# the .pipeline.json sidecars on the outsource share.
#
# The MediaPipeline normally appends to the manifest incrementally as each job
# finishes, but when the feature is first rolled out — or after the manifest is
# deleted/corrupted — the local log is empty even though dozens or hundreds of
# completed outputs exist on the outsource. This script walks the share, reads
# each sidecar, and writes a fresh JSONL manifest.
#
# Usage:
#   pwsh -File Backfill-CompletedManifest.ps1 \
#       -OutsourceRoot "\\server\share\outsource" \
#       -LocalBase     "E:\Videos\Scratch"
#
# The script always writes to "$LocalBase\State\Completed\completed_jobs.jsonl".
# A backup of the existing manifest (if any) is saved alongside before
# overwrite, so nothing is lost if the backfill is re-run.
# ==============================================================================

[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$OutsourceRoot,
    [Parameter(Mandatory)] [string]$LocalBase,
    [switch]$DryRun,
    [string]$CheckpointPath
)

$ErrorActionPreference = 'Stop'

$pipelineRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $pipelineRoot 'engine\storage\state_store.ps1')

function Write-BackfillJsonAtomic {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [object]$Payload,
        [int]$Depth = 8
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $leaf = Split-Path -Leaf $Path
    $tmp = Join-Path $parent (".${leaf}.$PID.$([guid]::NewGuid().ToString('N')).tmp")
    try {
        $json = $Payload | ConvertTo-Json -Depth $Depth
        [System.IO.File]::WriteAllText($tmp, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::Move($tmp, $Path, $true)
    } finally {
        if (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }
}

function Write-BackfillCheckpoint {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Status,
        [Parameter(Mandatory)] [string]$ManifestPath,
        [Parameter(Mandatory)] [bool]$DryRun,
        [int]$Ingested = 0,
        [int]$Skipped = 0,
        [string]$CurrentSidecar = '',
        [string]$Message = ''
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $payload = [ordered]@{
        schema_version  = 'completed_manifest_backfill_checkpoint.v1'
        status          = $Status
        dry_run         = $DryRun
        updated_at      = (Get-Date).ToUniversalTime().ToString('o')
        manifest_path   = $ManifestPath
        ingested        = $Ingested
        skipped         = $Skipped
        scanned         = $Ingested + $Skipped
        current_sidecar = $CurrentSidecar
        message         = $Message
    }
    Write-BackfillJsonAtomic -Path $Path -Payload $payload
}

function New-BackfillBackupPath {
    param([Parameter(Mandatory)] [string]$ManifestPath)

    for ($i = 0; $i -lt 20; $i++) {
        $candidate = "$ManifestPath.bak.$((Get-Date).ToString('yyyyMMdd_HHmmss_ffffff'))"
        if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
        Start-Sleep -Milliseconds 1
    }
    throw "Unable to choose a unique backup path for $ManifestPath"
}

function Write-CompletedManifestAtomic {
    param(
        [Parameter(Mandatory)] [string]$ManifestPath,
        [Parameter(Mandatory)] [System.Collections.Generic.List[string]]$Entries
    )

    $parent = Split-Path -Parent $ManifestPath
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $leaf = Split-Path -Leaf $ManifestPath
    $tmp = Join-Path $parent (".${leaf}.$PID.$([guid]::NewGuid().ToString('N')).tmp")
    try {
        [System.IO.File]::WriteAllLines(
            $tmp,
            $Entries,
            [System.Text.UTF8Encoding]::new($false)
        )
        [System.IO.File]::Move($tmp, $ManifestPath, $true)
    } finally {
        if (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not (Test-Path -LiteralPath $OutsourceRoot)) {
    Write-Error "OutsourceRoot not found: $OutsourceRoot"
    exit 2
}
if (-not (Test-Path -LiteralPath $LocalBase)) {
    Write-Error "LocalBase not found: $LocalBase"
    exit 2
}

$stateLayout = Initialize-MediaPipelineStateLayout -Layout (New-MediaPipelineStateLayout -LocalBase $LocalBase) -MigrateLegacy
$localCompleted = $stateLayout.Completed
$manifestPath   = $stateLayout.Paths.CompletedJobsManifest
if (-not (Test-Path -LiteralPath $localCompleted)) {
    New-Item -ItemType Directory -Path $localCompleted -Force | Out-Null
}
if ([string]::IsNullOrWhiteSpace($CheckpointPath)) {
    $CheckpointPath = Join-Path $localCompleted 'completed_manifest_backfill_progress.json'
}

Write-BackfillCheckpoint -Path $CheckpointPath -Status 'starting' -ManifestPath $manifestPath -DryRun ([bool]$DryRun)
Write-Host "Scanning outsource for .pipeline.json sidecars..."
if ($DryRun) {
    Write-Host "Dry run: manifest and backups will not be modified."
}
$t0 = Get-Date

$entries = [System.Collections.Generic.List[string]]::new()
$count = 0
$skipped = 0
$terminalCheckpointWritten = $false
try {
    # [System.IO.Directory]::EnumerateFiles is dramatically faster on SMB than
    # Get-ChildItem -Recurse because it skips FileInfo object construction.
    # AllDirectories recurses fully; depth isn't a concern since the outsource
    # tree is bounded by library structure.
    $sidecars = [System.IO.Directory]::EnumerateFiles(
        $OutsourceRoot,
        '*.pipeline.json',
        [System.IO.SearchOption]::AllDirectories
    )

    foreach ($path in $sidecars) {
        try {
            $raw = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
            $obj = $raw | ConvertFrom-Json -ErrorAction Stop
        } catch {
            Write-Warning "Skipping unreadable sidecar: $path — $_"
            $skipped++
            if ((($count + $skipped) % 100) -eq 0) {
                Write-BackfillCheckpoint -Path $CheckpointPath -Status 'scanning' -ManifestPath $manifestPath -DryRun ([bool]$DryRun) -Ingested $count -Skipped $skipped -CurrentSidecar $path
            }
            continue
        }

        # Convert PSCustomObject to hashtable we can mutate, then add the same
        # fields the pipeline's Add-CompletedJobsManifestEntry writes at runtime.
        $entry = [ordered]@{}
        foreach ($prop in $obj.PSObject.Properties) {
            $entry[$prop.Name] = $prop.Value
        }
        if (-not $entry.Contains('output_path')) {
            # Infer output from the sidecar path (sidecar lives next to the output).
            $dir  = Split-Path $path -Parent
            $base = [System.IO.Path]::GetFileNameWithoutExtension($path)
            # GetFileNameWithoutExtension on "Foo.pipeline.json" returns "Foo.pipeline"
            if ($base.EndsWith('.pipeline')) {
                $base = $base.Substring(0, $base.Length - '.pipeline'.Length)
            }

            # Prefer the filename the pipeline recorded in the sidecar itself
            # (Write-Sidecar stores output_file = Split-Path $OutputPath -Leaf,
            # which carries the correct extension for both .mkv and .mp4 configs).
            if (-not [string]::IsNullOrWhiteSpace([string]$obj.output_file)) {
                $entry['output_path'] = Join-Path $dir ([string]$obj.output_file)
            } else {
                # Sidecar pre-dates the output_file field: probe for the actual
                # file so we pick the right container extension rather than
                # hardcoding .mkv (which would be wrong for mp4 OutputContainer).
                $found = $null
                foreach ($ext in @('.mkv', '.mp4')) {
                    $candidate = Join-Path $dir ($base + $ext)
                    if ([System.IO.File]::Exists($candidate)) {
                        $found = $candidate
                        break
                    }
                }
                $entry['output_path'] = if ($null -ne $found) { $found } else {
                    Join-Path $dir ($base + '.mkv')   # last-resort fallback
                }
            }
        }
        # Use the sidecar's file mtime as the backfill logged_at — it's the best
        # available timestamp when the pipeline didn't record it in the payload.
        $entry['logged_at'] = [System.IO.File]::GetLastWriteTimeUtc($path).ToString('o')

        $line = $entry | ConvertTo-Json -Depth 5 -Compress
        $entries.Add($line)
        $count++
        if ((($count + $skipped) % 100) -eq 0) {
            Write-BackfillCheckpoint -Path $CheckpointPath -Status 'scanning' -ManifestPath $manifestPath -DryRun ([bool]$DryRun) -Ingested $count -Skipped $skipped -CurrentSidecar $path
        }
    }

    if ($DryRun) {
        Write-BackfillCheckpoint -Path $CheckpointPath -Status 'dry_run_completed' -ManifestPath $manifestPath -DryRun $true -Ingested $count -Skipped $skipped -Message 'Dry run completed without modifying the manifest.'
        $terminalCheckpointWritten = $true
    } else {
        # Preserve the existing manifest before overwrite.
        if (Test-Path -LiteralPath $manifestPath) {
            $backup = New-BackfillBackupPath -ManifestPath $manifestPath
            Copy-Item -LiteralPath $manifestPath -Destination $backup -Force
            Write-Host "Backed up existing manifest to: $backup"
        }
        Write-CompletedManifestAtomic -ManifestPath $manifestPath -Entries $entries
        Write-BackfillCheckpoint -Path $CheckpointPath -Status 'completed' -ManifestPath $manifestPath -DryRun $false -Ingested $count -Skipped $skipped
        $terminalCheckpointWritten = $true
    }
} catch {
    Write-BackfillCheckpoint -Path $CheckpointPath -Status 'failed' -ManifestPath $manifestPath -DryRun ([bool]$DryRun) -Ingested $count -Skipped $skipped -Message ([string]$_)
    $terminalCheckpointWritten = $true
    throw
} finally {
    if (-not $terminalCheckpointWritten) {
        Write-BackfillCheckpoint -Path $CheckpointPath -Status 'interrupted' -ManifestPath $manifestPath -DryRun ([bool]$DryRun) -Ingested $count -Skipped $skipped -Message 'Backfill stopped before completion.'
    }
}

$elapsed = (Get-Date) - $t0
Write-Host ""
Write-Host ($(if ($DryRun) { "Backfill dry run complete." } else { "Backfill complete." }))
Write-Host ("  Sidecars ingested : {0}" -f $count)
Write-Host ("  Skipped (bad JSON): {0}" -f $skipped)
Write-Host ("  Elapsed           : {0:F1}s" -f $elapsed.TotalSeconds)
Write-Host ("  Manifest          : {0}" -f $manifestPath)
Write-Host ("  Checkpoint        : {0}" -f $CheckpointPath)
