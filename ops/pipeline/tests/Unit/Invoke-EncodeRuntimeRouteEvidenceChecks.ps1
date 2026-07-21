[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Encode runtime route evidence checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$mutexModulePath = Join-Path $pipelineRoot 'engine\queue\worker_mutex.ps1'
$monitorModulePath = Join-Path $pipelineRoot 'engine\status\run_monitor_state.ps1'
$encodeFallbackPath = Join-Path $pipelineRoot 'engine\process\encode_fallback.ps1'
$encodeSizeGuardPath = Join-Path $pipelineRoot 'engine\process\encode_size_guard.ps1'
$failureStatePath = Join-Path $pipelineRoot 'engine\failures\failure_state.ps1'

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

. $mutexModulePath
. $monitorModulePath
. $encodeFallbackPath
. $encodeSizeGuardPath
. $failureStatePath

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-encode-route-evidence-' + [guid]::NewGuid().ToString('N'))
$priorSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
$env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = 'encode_route_' + [guid]::NewGuid().ToString('N')

try {
    $runMonitorRoot = Join-Path $tempRoot 'State\RunMonitor'
    New-Item -ItemType Directory -Path $runMonitorRoot -Force | Out-Null
    $script:LocalStateLayout = [pscustomobject]@{
        Root       = (Join-Path $tempRoot 'State')
        RunMonitor = $runMonitorRoot
        Paths      = [pscustomobject]@{ RunMonitor = $runMonitorRoot }
    }
    $script:PipelineRunId = 'encode-route-run'
    $script:CurrentRunMonitorJobId = 'encode-route-run:item:1'
    $script:RunMonitorPersistenceHealthy = $true
    $script:currentRoute = 'encode'
    $script:CurrentRouteReasonCode = 'planned_video_policy'
    $script:CurrentRouteReason = 'Queue policy planned an encode.'
    $script:CurrentExecutedRoute = $null
    $script:CurrentExecutedRouteReasonCode = $null
    $script:CurrentExecutedRouteReason = $null

    $acceptedRows = @(
        [pscustomobject]@{
            run_queue_index = 1
            run_queue_total = 1
            job_id = $script:CurrentRunMonitorJobId
            source_identity = 'encode-route-source'
            source_identity_algorithm = 'source_identity_v2'
            source_path = 'C:\Media\Source.mkv'
            display_name = 'Source.mkv'
            parent_context = 'C:\Media'
            route = 'encode'
            route_reason_code = 'planned_video_policy'
            route_reason = 'Queue policy planned an encode.'
            intended_final_path = 'D:\Library\Source.mkv'
        }
    )
    Write-MediaPipelineRunMonitorSeed `
        -RunId $script:PipelineRunId `
        -CommandId 'encode-route-command' `
        -QueuePlanFingerprint 'encode-route-fingerprint' `
        -AcceptedRows $acceptedRows | Out-Null

    $hardwareRecorded = Set-MediaPipelineEncodeRuntimeRouteEvidence `
        -Route 'encode_hardware' `
        -ReasonCode 'hardware_encoder_selected' `
        -Reason "Runtime selected NVENC encoder 'hevc_nvenc' and began hardware encoding."
    Assert-True ([bool]$hardwareRecorded) 'Confirmed hardware selection must update exact run/job route evidence.'

    $monitorPath = Join-Path $runMonitorRoot 'encode-route-run.json'
    $hardwareMonitor = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $hardwareMonitor.items[0].routes.planned.route 'encode' 'Runtime hardware evidence must not overwrite the Queue-planned route.'
    Assert-Equal $hardwareMonitor.items[0].routes.executed.route 'encode_hardware' 'Confirmed hardware selection must become the executed route.'
    Assert-Equal $hardwareMonitor.items[0].routes.executed.reason_code 'hardware_encoder_selected' 'Hardware execution reason code mismatch.'
    Assert-Equal $hardwareMonitor.items[0].routes.final.state 'awaiting_evidence' 'Runtime hardware evidence must not manufacture terminal route proof.'

    $cpuRecorded = Set-MediaPipelineEncodeRuntimeRouteEvidence `
        -Route 'encode-cpu-fallback' `
        -ReasonCode 'hardware_encoder_cpu_fallback' `
        -Reason "Hardware encode attempts failed; CPU encoder 'libx265' was selected for fallback."
    Assert-True ([bool]$cpuRecorded) 'Confirmed CPU fallback selection must update exact run/job route evidence.'

    $cpuMonitor = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $cpuMonitor.items[0].routes.planned.route 'encode' 'CPU fallback evidence must preserve the Queue-planned route.'
    Assert-Equal $cpuMonitor.items[0].routes.executed.route 'encode-cpu-fallback' 'Confirmed CPU fallback must replace stale hardware execution evidence.'
    Assert-Equal $cpuMonitor.items[0].routes.executed.reason_code 'hardware_encoder_cpu_fallback' 'CPU fallback execution reason code mismatch.'
    Assert-Equal $cpuMonitor.items[0].routes.final.state 'awaiting_evidence' 'CPU fallback selection must remain runtime evidence, not terminal proof.'

    $remuxTriggerCases = @(
        [pscustomobject]@{ Trigger = 'preflight_projection'; Code = 'encode_waste_guard_preflight_remux_fallback' },
        [pscustomobject]@{ Trigger = 'live_projection'; Code = 'encode_waste_guard_live_remux_fallback' },
        [pscustomobject]@{ Trigger = 'live_projection_safe_retry'; Code = 'encode_waste_guard_safe_retry_remux_fallback' },
        [pscustomobject]@{ Trigger = 'post_encode_size_guard'; Code = 'encode_size_guard_remux_fallback' },
        [pscustomobject]@{ Trigger = 'dynamic_hdr_prefer_remux'; Code = 'dynamic_hdr_prefer_remux' }
    )
    foreach ($case in $remuxTriggerCases) {
        $remuxRecorded = Set-MediaPipelineEncodeRemuxFallbackRouteEvidence `
            -Trigger $case.Trigger `
            -Reason "Synthetic $($case.Trigger) selected remux before Do-Remux."
        Assert-True ([bool]$remuxRecorded) "Remux transition '$($case.Trigger)' must update exact run/job route evidence."
        $remuxMonitor = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
        Assert-Equal $remuxMonitor.items[0].routes.executed.route 'remux' "Remux transition '$($case.Trigger)' must replace stale encode execution evidence."
        Assert-Equal $remuxMonitor.items[0].routes.executed.reason_code $case.Code "Remux transition '$($case.Trigger)' reason code mismatch."
        Assert-Equal $script:CurrentExecutedRoute 'remux' "Remux transition '$($case.Trigger)' must update failure-artifact route evidence."
    }

    $remuxFailure = New-StandardFailureRecord `
        -SourcePath 'C:\Media\Source.mkv' `
        -Stage 'remux' `
        -Reason 'Synthetic remux fallback failed.' `
        -ErrorCode 'REMUX_SYNTHETIC_FAILURE'
    Assert-Equal $remuxFailure.final_route 'remux' 'Failure proof must follow the exact selected remux fallback route.'
    Assert-Equal $remuxFailure.final_reason_code 'dynamic_hdr_prefer_remux' 'Failure proof must preserve the exact remux transition reason.'

    Set-MediaPipelineEncodeRuntimeRouteEvidence `
        -Route 'encode-cpu-fallback' `
        -ReasonCode 'hardware_encoder_cpu_fallback' `
        -Reason "Hardware encode attempts failed; CPU encoder 'libx265' was selected for fallback." | Out-Null

    $cpuFailure = New-StandardFailureRecord `
        -SourcePath 'C:\Media\Source.mkv' `
        -Stage 'encode' `
        -Reason 'FFmpeg CPU encode failed: synthetic failure.' `
        -ErrorCode 'ENCODE_CPU_SYNTHETIC_FAILURE'
    Assert-Equal $cpuFailure.final_route 'encode-cpu-fallback' 'Failure proof must use the last exact executed route, not planned or progress text.'
    Assert-Equal $cpuFailure.final_reason_code 'hardware_encoder_cpu_fallback' 'Failure proof must use the last exact executed route reason code.'
    Assert-Equal $cpuFailure.final_reason "Hardware encode attempts failed; CPU encoder 'libx265' was selected for fallback." 'Failure proof must use the last exact executed route reason.'
    Assert-Equal $cpuFailure.reason 'FFmpeg CPU encode failed: synthetic failure.' 'The failure cause must remain separate from the final route reason.'

    Set-MediaPipelineRunMonitorFinalRoute `
        -RunId $script:PipelineRunId `
        -JobId $script:CurrentRunMonitorJobId `
        -Route 'encode-cpu-fallback' `
        -ReasonCode 'verified_cpu_output' `
        -Reason 'Verified CPU output was published.' `
        -EvidenceSource 'pipeline_sidecar' | Out-Null
    $terminalMonitor = Get-Content -LiteralPath $monitorPath -Raw | ConvertFrom-Json -Depth 40
    Assert-Equal $terminalMonitor.items[0].routes.planned.route 'encode' 'Terminal proof must preserve planned evidence.'
    Assert-Equal $terminalMonitor.items[0].routes.executed.reason_code 'hardware_encoder_cpu_fallback' 'Terminal proof must preserve the last runtime reason.'
    Assert-Equal $terminalMonitor.items[0].routes.final.reason_code 'verified_cpu_output' 'Final route must remain separately artifact-authored.'

    $encodeSource = Get-Content -LiteralPath $encodeFallbackPath -Raw
    $sizeGuardSource = Get-Content -LiteralPath $encodeSizeGuardPath -Raw
    $primaryExecutionIndex = $encodeSource.IndexOf('$success = Invoke-MediaPipelineEncodeAttemptExecution -Plan $encodePlan', [System.StringComparison]::Ordinal)
    $safeExecutionIndex = $encodeSource.IndexOf('$success    = Invoke-MediaPipelineEncodeAttemptExecution -Plan $encodePlan', [System.StringComparison]::Ordinal)
    $cpuExecutionIndex = $encodeSource.IndexOf('$success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label', [System.StringComparison]::Ordinal)
    Assert-True ($primaryExecutionIndex -gt 0) 'Primary hardware execution marker is missing.'
    Assert-True ($safeExecutionIndex -gt $primaryExecutionIndex) 'Safe-retry hardware execution marker is missing.'
    Assert-True ($cpuExecutionIndex -gt $safeExecutionIndex) 'CPU fallback execution marker is missing.'

    $primaryWindow = $encodeSource.Substring([Math]::Max(0, $primaryExecutionIndex - 900), [Math]::Min(900, $primaryExecutionIndex))
    $safeWindow = $encodeSource.Substring([Math]::Max(0, $safeExecutionIndex - 900), [Math]::Min(900, $safeExecutionIndex))
    $cpuWindow = $encodeSource.Substring([Math]::Max(0, $cpuExecutionIndex - 3600), [Math]::Min(3600, $cpuExecutionIndex))
    Assert-True ($primaryWindow -match "Set-MediaPipelineEncodeRuntimeRouteEvidence[\s\S]+-Route 'encode_hardware'") 'Primary hardware route evidence must be written before FFmpeg starts.'
    Assert-True ($safeWindow -match "Set-MediaPipelineEncodeRuntimeRouteEvidence[\s\S]+-Route 'encode_hardware'") 'Safe-retry hardware route evidence must be refreshed before FFmpeg starts.'
    Assert-True ($cpuWindow -match "Set-MediaPipelineEncodeRuntimeRouteEvidence[\s\S]+-Route 'encode-cpu-fallback'") 'CPU fallback route evidence must be written before CPU FFmpeg starts.'

    $wasteGuardFallbackIndex = $sizeGuardSource.IndexOf('$fallbackRemuxOk = Do-Remux $SourceFile', [System.StringComparison]::Ordinal)
    $postEncodeFallbackIndex = $sizeGuardSource.IndexOf('$fallbackRemuxOk = Do-Remux $file', [System.StringComparison]::Ordinal)
    $dynamicHdrFallbackIndex = $encodeSource.IndexOf('$dynamicHdrRemuxOk = Do-Remux $file', [System.StringComparison]::Ordinal)
    Assert-True ($wasteGuardFallbackIndex -gt 0) 'Waste-guard remux fallback marker is missing.'
    Assert-True ($postEncodeFallbackIndex -gt $wasteGuardFallbackIndex) 'Post-encode size-guard remux fallback marker is missing.'
    Assert-True ($dynamicHdrFallbackIndex -gt 0) 'Dynamic HDR remux fallback marker is missing.'
    $wasteGuardWindow = $sizeGuardSource.Substring([Math]::Max(0, $wasteGuardFallbackIndex - 900), [Math]::Min(900, $wasteGuardFallbackIndex))
    $postEncodeWindow = $sizeGuardSource.Substring([Math]::Max(0, $postEncodeFallbackIndex - 900), [Math]::Min(900, $postEncodeFallbackIndex))
    $dynamicHdrWindow = $encodeSource.Substring([Math]::Max(0, $dynamicHdrFallbackIndex - 1200), [Math]::Min(1200, $dynamicHdrFallbackIndex))
    Assert-True ($wasteGuardWindow -match 'Set-MediaPipelineEncodeRemuxFallbackRouteEvidence[\s\S]+-Trigger \$Trigger') 'Preflight/live/safe-retry waste-guard paths must author the exact remux transition before Do-Remux.'
    Assert-True ($postEncodeWindow -match "Set-MediaPipelineEncodeRemuxFallbackRouteEvidence[\s\S]+-Trigger 'post_encode_size_guard'") 'Post-encode size guard must author the exact remux transition before Do-Remux.'
    Assert-True ($dynamicHdrWindow -match "Set-MediaPipelineEncodeRemuxFallbackRouteEvidence[\s\S]+-Trigger 'dynamic_hdr_prefer_remux'") 'Dynamic HDR policy must author the exact remux transition before Do-Remux.'
} finally {
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $priorSuffix
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Encode runtime route evidence checks passed.'
