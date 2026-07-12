# ==============================================================================
# ops\pipeline\engine\queue\worker_mutex.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\local_worker_slots.ps1. Keep function names
# stable; local_worker_slots.ps1 dot-sources this file for compatibility.
# ==============================================================================

function Get-MediaPipelineLocalWorkerTimestamp {
    return (Get-Date).ToString('o')
}

function Get-MediaPipelineStableHash {
    param([string] $Text)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Text)
        $hash = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash) -replace '-', '').Substring(0, 16).ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-MediaPipelineWorkerMutexSuffix {
    $suffix = ''
    if (-not [string]::IsNullOrWhiteSpace($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX)) {
        $suffix = '_' + (($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX) -replace '[^A-Za-z0-9_.-]', '_')
    }
    return $suffix
}

function Get-MediaPipelineLocalWorkerMutexName {
    param(
        [Parameter(Mandatory)] [string] $Kind,
        [string] $LocalBase = '',
        [int] $SlotId = 0
    )

    $scopeText = if ([string]::IsNullOrWhiteSpace($LocalBase)) { 'global' } else { [string]$LocalBase }
    $hash = Get-MediaPipelineStableHash -Text $scopeText
    $slotPart = if ($SlotId -gt 0) { "_slot_$SlotId" } else { '' }
    return "Global\MediaPipeline_${Kind}_v1_${hash}${slotPart}$(Get-MediaPipelineWorkerMutexSuffix)"
}

function Invoke-MediaPipelineMutexProtected {
    param(
        [Parameter(Mandatory)] [string] $MutexName,
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [int] $TimeoutMs = 30000
    )

    $mutex = [System.Threading.Mutex]::new($false, $MutexName)
    $locked = $false
    try {
        try {
            $locked = $mutex.WaitOne($TimeoutMs)
        } catch [System.Threading.AbandonedMutexException] {
            $locked = $true
        }
        if (-not $locked) {
            throw "Timed out waiting for mutex $MutexName"
        }
        return (& $ScriptBlock)
    } finally {
        if ($locked) {
            try { $mutex.ReleaseMutex() } catch {}
        }
        $mutex.Dispose()
    }
}

function Invoke-MediaPipelineFinalStateWrite {
    param(
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [string] $OperationName = 'final-state',
        [int] $TimeoutMs = 600000
    )

    $localBaseForLock = ''
    try { if ($LocalBase) { $localBaseForLock = [string]$LocalBase } } catch {}
    $mutexName = Get-MediaPipelineLocalWorkerMutexName -Kind 'FinalStateWriter' -LocalBase $localBaseForLock
    return Invoke-MediaPipelineMutexProtected -MutexName $mutexName -TimeoutMs $TimeoutMs -ScriptBlock {
        if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
            Write-Log "Final-state writer lock acquired for $OperationName" 'DEBUG'
        }
        & $ScriptBlock
    }
}

function Write-MediaPipelineJsonAtomic {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] $InputObject,
        [int] $Depth = 8
    )

    $dir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($dir) -and -not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }
    $leaf = Split-Path -Leaf $Path
    $id = [guid]::NewGuid().ToString('N')
    $tmp = Join-Path $dir ".$leaf.$id.tmp"
    $backup = Join-Path $dir ".$leaf.$id.bak"
    try {
        $json = ConvertTo-Json -InputObject $InputObject -Depth $Depth
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        $null = Get-Content -LiteralPath $tmp -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
        return $true
    } catch {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        throw
    }
}

function Read-MediaPipelineJsonFile {
    param([Parameter(Mandatory)] [string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
}
