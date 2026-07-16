# ==============================================================================
# MediaPipeline startup filesystem prep  (dot-sourced by MediaPipeline.ps1)
# ==============================================================================
# Procedural slice: create local working dirs, migrate legacy state layout, rotate
# logs, repair local-worker claims, flush startup warnings. Reads $script:LocalStateLayout,
# the $Local* dirs, $WorkerChild, $ValidateOnly, $locklessDiagnostic, $ProgressFile,
# $script:PipelineRunId.
# ==============================================================================
Initialize-MediaPipelineStateLayout -Layout $script:LocalStateLayout -MigrateLegacy | Out-Null
foreach ($dir in @($LocalIncoming, $LocalEncoded, $LocalRemuxTemp, $script:processingDir)) {
    if (-not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
        Write-Host "Created directory: $dir"
    }
}

Invoke-LogRotation
if (-not $ValidateOnly -and -not $locklessDiagnostic) {
    $toolLogMaintenance = Invoke-MediaPipelineToolLogMaintenance `
        -ActiveDirectory $LocalActiveToolLogs `
        -InterruptedDirectory $LocalInterruptedToolLogs `
        -RetentionDays ([int]$script:InterruptedToolLogRetentionDays)
    if ([int]$toolLogMaintenance.OrphanedCount -gt 0 -or
        [int]$toolLogMaintenance.DeletedCount -gt 0 -or
        [int]$toolLogMaintenance.ErrorCount -gt 0) {
        Write-Log ("Native-tool diagnostic maintenance: reconciled={0}; expired_deleted={1}; errors={2}; retention_days={3}" -f `
            [int]$toolLogMaintenance.OrphanedCount,
            [int]$toolLogMaintenance.DeletedCount,
            [int]$toolLogMaintenance.ErrorCount,
            [int]$toolLogMaintenance.RetentionDays) $(if ([int]$toolLogMaintenance.ErrorCount -gt 0) { 'WARN' } else { 'INFO' })
    }
}
# Controller runs only: worker children must not rewrite the shared claim
# store/active-jobs files, and lockless diagnostic dump modes may run beside
# a live pipeline that owns them.
if (-not $WorkerChild -and -not $ValidateOnly -and -not $locklessDiagnostic) {
    Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -CurrentRunId $script:PipelineRunId | Out-Null
    Write-MediaPipelineLocalWorkerActiveJobs -ActiveJobsPath $script:LocalStateLayout.Paths.LocalWorkerActiveJobs -CompatibilityProgressPath $ProgressFile -ActiveJobs @() -WriteCompatibilityProgress | Out-Null
}
Write-StartupWarnings
