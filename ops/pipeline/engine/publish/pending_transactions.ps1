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
    param([string]$Path)
    try {
        if ($Path -and (Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction SilentlyContinue)) {
            return ([string](Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash).ToUpperInvariant()
        }
    } catch {
        Write-Log "Pending: SHA-256 proof failed for $Path : $_" 'WARN'
    }
    return $null
}
