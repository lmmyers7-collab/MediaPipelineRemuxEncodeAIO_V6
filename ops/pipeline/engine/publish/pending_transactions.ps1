# ==============================================================================
# Modules\PendingTransactions.ps1
# ==============================================================================
# Transaction helpers for PendingServerPush parking and draining.
#
# Public pending APIs stay in PendingPush.ps1. This module owns the durable
# park transaction mechanics so the wrapper can handle operator-facing logging,
# index refresh, and event emission without also owning manifest/move cleanup.
# ==============================================================================


. (Join-Path $PSScriptRoot 'pending_sidecar_transactions.ps1')
. (Join-Path $PSScriptRoot 'pending_repair.ps1')
. (Join-Path $PSScriptRoot 'pending_park_transaction.ps1')
. (Join-Path $PSScriptRoot 'pending_drain_transaction.ps1')

$script:PendingPublishFaultBoundaries = @(
    'manifest_preparation',
    'pending_copy',
    'byte_hash_verification',
    'sidecar_staging',
    'destination_availability',
    'final_placement',
    'atomic_reveal',
    'index_update',
    'completion_evidence_write',
    'pending_cleanup'
)

function Test-PendingPublishFaultBoundary {
    param([string] $Boundary)

    return (-not [string]::IsNullOrWhiteSpace($Boundary) -and $Boundary -in $script:PendingPublishFaultBoundaries)
}

# Test-only adapter seam. Production runs leave PendingPublishFaultInjector
# unset, making every call a no-op. A test injector may return 'exception' to
# exercise normal rollback or 'terminate' to emulate abrupt process loss. The
# latter is tagged so park's catch block deliberately skips in-process cleanup,
# matching the filesystem state a killed process would leave behind.
function Invoke-PendingPublishFaultPoint {
    param(
        [Parameter(Mandatory)] [string] $Boundary,
        [Parameter(Mandatory)]
        [ValidateSet('before','after')]
        [string] $Moment,
        [hashtable] $Context = @{}
    )

    if (-not (Test-PendingPublishFaultBoundary -Boundary $Boundary)) {
        throw "Unknown pending-publish fault boundary: $Boundary"
    }
    $injector = $script:PendingPublishFaultInjector
    if ($null -eq $injector -or $injector -isnot [scriptblock]) { return }

    $action = & $injector $Boundary $Moment $Context
    if ([string]::IsNullOrWhiteSpace([string]$action)) { return }
    if ([string]$action -notin @('exception', 'terminate')) {
        throw "Unsupported pending-publish fault action '$action' at $Boundary/$Moment."
    }
    $exception = [System.InvalidOperationException]::new("Injected pending-publish $action at $Boundary/$Moment")
    if ([string]$action -eq 'terminate') {
        $exception.Data['PendingPublishInjectedTermination'] = $true
    }
    throw $exception
}

function Test-PendingPublishInjectedTermination {
    param($ErrorRecord)

    try { return [bool]$ErrorRecord.Exception.Data['PendingPublishInjectedTermination'] } catch { return $false }
}

function Enter-PendingPublishTransactionLock {
    param([Parameter(Mandatory)] [string] $ManifestPath)

    $lockPath = "$ManifestPath.lock"
    try {
        $stream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
        return [pscustomobject]@{ Stream = $stream; Path = $lockPath }
    } catch {
        return $null
    }
}

function Exit-PendingPublishTransactionLock {
    param($Lock)

    if ($null -eq $Lock) { return }
    try { if ($Lock.Stream) { $Lock.Stream.Dispose() } } catch {}
    try {
        if ($Lock.Path -and (Test-Path -LiteralPath ([string]$Lock.Path) -PathType Leaf -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath ([string]$Lock.Path) -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}

function New-PublishTransactionId {
    return [guid]::NewGuid().ToString("N")
}

# Defensive Get-Item.Length wrapper - returns $null on any failure rather
# than throwing. Used throughout pending-publish checks where "couldn't
# determine size" must not abort a retry path.
function Get-FileLengthOrNull {
    param([string]$Path)
    try {
        if ($Path -and (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
            return [long](Get-Item -LiteralPath $Path -ErrorAction Stop).Length
        }
    } catch {}
    return $null
}

# A pending manifest stores this proof once when the verified local output is
# parked. Drain compares the staged partial and the revealed final file to this
# same value before it may discard the only parked copy.
function Get-PendingFileSha256OrNull {
    param(
        [string]$Path,
        [scriptblock] $PollHandler = $null
    )

    $stream = $null
    $sha256 = $null
    $stopwatch = $null
    try {
        if ($Path -and (Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction SilentlyContinue)) {
            # Get-FileHash is a single opaque blocking call. Verified media can
            # be hundreds of gigabytes, so compute the same SHA-256 proof in a
            # bounded streaming loop that lets the exact publish-stage callback
            # refresh worker/run evidence without inventing progress.
            $stream = [System.IO.File]::Open(
                $Path,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::Read
            )
            $sha256 = [System.Security.Cryptography.SHA256]::Create()
            $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
            $buffer = [byte[]]::new(1024 * 1024)
            if ($PollHandler) {
                try { & $PollHandler 0 $null | Out-Null } catch {}
            }
            while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                [void]$sha256.TransformBlock($buffer, 0, $read, $buffer, 0)
                if ($PollHandler) {
                    try { & $PollHandler ([double]$stopwatch.Elapsed.TotalSeconds) $null | Out-Null } catch {}
                }
            }
            [void]$sha256.TransformFinalBlock([byte[]]::new(0), 0, 0)
            return ([System.BitConverter]::ToString($sha256.Hash).Replace('-', '')).ToUpperInvariant()
        }
    } catch {
        Write-Log "Pending: SHA-256 proof failed for $Path : $_" 'WARN'
    } finally {
        if ($stopwatch) { $stopwatch.Stop() }
        if ($sha256) { $sha256.Dispose() }
        if ($stream) { $stream.Dispose() }
    }
    return $null
}
