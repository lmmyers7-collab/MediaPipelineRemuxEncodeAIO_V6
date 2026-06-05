# ==============================================================================
# MediaPipeline startup filesystem prep  (dot-sourced by MediaPipeline.ps1)
# ==============================================================================
# Procedural slice: create local working dirs, migrate legacy state layout, rotate
# logs, repair local-worker claims, flush startup warnings. Reads $script:LocalStateLayout,
# the $Local* dirs, $WorkerChild, $ValidateOnly, $ProgressFile, $script:PipelineRunId.
# ==============================================================================
Initialize-MediaPipelineStateLayout -Layout $script:LocalStateLayout -MigrateLegacy | Out-Null
foreach ($dir in @($LocalIncoming, $LocalEncoded, $LocalRemuxTemp, $script:processingDir)) {
    if (-not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
        Write-Host "Created directory: $dir"
    }
}

Invoke-LogRotation
if (-not $WorkerChild -and -not $ValidateOnly) {
    Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $script:LocalStateLayout.Paths.LocalWorkerClaims -CurrentRunId $script:PipelineRunId | Out-Null
    Write-MediaPipelineLocalWorkerActiveJobs -ActiveJobsPath $script:LocalStateLayout.Paths.LocalWorkerActiveJobs -CompatibilityProgressPath $ProgressFile -ActiveJobs @() -WriteCompatibilityProgress | Out-Null
}
Write-StartupWarnings
