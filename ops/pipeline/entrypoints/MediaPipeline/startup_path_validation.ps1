# ==============================================================================
# MediaPipeline startup path validation  (dot-sourced by MediaPipeline.ps1)
# ==============================================================================
# Procedural slice: bounded reachability probes for LocalBase (hard fail / exit 2)
# and the source/outsource shares (soft warnings). Reads $LocalBase, $DrainPendingPushes,
# $SourceMovies, $SourceTV, $Outsource from the caller. No behaviour change.
# ==============================================================================
$localBaseReachable = Test-PathAccessibleBounded -Path $LocalBase -TimeoutSeconds 10
if ($localBaseReachable -ne $true) {
    $reachability = if ($null -eq $localBaseReachable) { 'timed out while checking' } else { 'does not exist or is not accessible' }
    Write-Log "FATAL: LocalBase does not exist or is not accessible: $LocalBase" "ERROR"
    Write-Log "       Path check result: $reachability" "ERROR"
    Write-Log "       Check the LocalBase setting in your config file." "ERROR"
    Write-Log "PIPELINE ABORTED"
    exit 2
}
if ($DrainPendingPushes) {
    Write-Log "DRAIN PENDING PUSHES: publish-only mode skips SourceMovies/SourceTV/Outsource startup reachability probes; pending manifest copy attempts validate their destinations."
} else {
    foreach ($pair in @(
        @{ Label = 'SourceMovies'; Path = $SourceMovies },
        @{ Label = 'SourceTV';     Path = $SourceTV },
        @{ Label = 'Outsource';    Path = $Outsource }
    )) {
        if (Test-IsUncPath ([string]$pair.Path)) {
            Write-Log "STARTUP WARNING: $($pair.Label) is a network path; startup reachability probe skipped: $($pair.Path)" "WARN"
            Write-Log "                 Scan/copy phases remain bounded by SourceScanTimeoutSeconds/IndexScanTimeoutSeconds and will report unreachable shares during real work." "WARN"
            continue
        }
        $reachable = Test-PathAccessibleBounded -Path ([string]$pair.Path) -TimeoutSeconds 10
        if ($reachable -ne $true) {
            $reachability = if ($null -eq $reachable) { 'check timed out' } else { 'path is not accessible' }
            Write-Log "STARTUP WARNING: $($pair.Label) is not accessible: $($pair.Path)" "WARN"
            Write-Log "                 Path check result: $reachability." "WARN"
            Write-Log "                 Scans for this location will return 0 files until it is reachable." "WARN"
        }
    }
}
