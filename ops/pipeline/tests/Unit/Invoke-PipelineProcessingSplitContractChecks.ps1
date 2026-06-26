[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Pipeline processing split contract checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

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
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-ContainsText {
    param([string] $Text, [string] $Needle, [string] $Message)
    if ($Text -notlike "*$Needle*") {
        throw "$Message Missing '$Needle'."
    }
}

function Assert-Matches {
    param([string] $Text, [string] $Pattern, [string] $Message)
    if ($Text -notmatch $Pattern) {
        throw "$Message Pattern '$Pattern' was not found."
    }
}

function Get-TextIndex {
    param([string] $Text, [string] $Needle, [string] $Message)
    $index = $Text.IndexOf($Needle, [System.StringComparison]::Ordinal)
    Assert-True ($index -ge 0) $Message
    return $index
}

$entrypointPath = Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline.ps1'
$loaderPath = Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\module_loader.ps1'
$encodePath = Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1'
$remuxPath = Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\remux.ps1'
$processingPath = Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_processing.ps1'

$entrypointText = Get-Content -LiteralPath $entrypointPath -Raw
$loaderText = Get-Content -LiteralPath $loaderPath -Raw
$encodeText = Get-Content -LiteralPath $encodePath -Raw
$remuxText = Get-Content -LiteralPath $remuxPath -Raw
$processingText = Get-Content -LiteralPath $processingPath -Raw
$encodeModuleRelativePaths = @(
    'ops\pipeline\engine\process\encode_context.ps1',
    'ops\pipeline\engine\process\encode_preflight.ps1',
    'ops\pipeline\engine\process\encode_attempt_plan.ps1',
    'ops\pipeline\engine\process\encode_command_builder.ps1',
    'ops\pipeline\engine\process\encode_execution.ps1',
    'ops\pipeline\engine\process\encode_fallback.ps1',
    'ops\pipeline\engine\process\encode_verification.ps1',
    'ops\pipeline\engine\process\encode_size_guard.ps1',
    'ops\pipeline\engine\process\encode_publish.ps1',
    'ops\pipeline\engine\process\encode_orchestrator.ps1'
)
$encodeModuleText = ($encodeModuleRelativePaths | ForEach-Object {
        $path = Join-Path $repoRoot $_
        if (Test-Path -LiteralPath $path -PathType Leaf) { Get-Content -LiteralPath $path -Raw }
    }) -join "`n"
$encodeContractText = $encodeText + "`n" + $encodeModuleText
$remuxModuleRelativePaths = @(
    'ops\pipeline\engine\process\remux_context.ps1',
    'ops\pipeline\engine\process\remux_preflight.ps1',
    'ops\pipeline\engine\process\remux_subtitle_plan.ps1',
    'ops\pipeline\engine\process\remux_ffmpeg_av_stage.ps1',
    'ops\pipeline\engine\process\remux_mkvmerge_args.ps1',
    'ops\pipeline\engine\process\remux_mkvmerge_stage.ps1',
    'ops\pipeline\engine\process\remux_verification.ps1',
    'ops\pipeline\engine\process\remux_publish.ps1',
    'ops\pipeline\engine\process\remux_orchestrator.ps1'
)
$remuxModuleText = ($remuxModuleRelativePaths | ForEach-Object {
        $path = Join-Path $repoRoot $_
        if (Test-Path -LiteralPath $path -PathType Leaf) { Get-Content -LiteralPath $path -Raw }
    }) -join "`n"
$remuxContractText = $remuxText + "`n" + $remuxModuleText

$repoRootForModules = $repoRoot
. $loaderPath

Assert-True ($engineModulePaths -is [hashtable]) 'module_loader.ps1 must define engineModulePaths as a hashtable.'
Assert-True ($engineModuleLoadOrder -is [array]) 'module_loader.ps1 must define engineModuleLoadOrder as an array.'
Assert-Equal $engineModuleLoadOrder.Count $engineModulePaths.Count 'Engine module manifest/load-order count drift.'
$duplicateModules = @($engineModuleLoadOrder | Group-Object | Where-Object { $_.Count -ne 1 })
Assert-Equal $duplicateModules.Count 0 "Engine module load order must not contain duplicates: $($duplicateModules.Name -join ', ')"
foreach ($module in $engineModuleLoadOrder) {
    Assert-True ($engineModulePaths.ContainsKey($module)) "Engine module '$module' is in load order but missing from manifest."
    Assert-True (Test-Path -LiteralPath $engineModulePaths[$module] -PathType Leaf) "Engine module path missing for '$module'."
}
foreach ($module in $engineModulePaths.Keys) {
    Assert-True ($engineModuleLoadOrder -contains $module) "Engine module '$module' is in manifest but missing from load order."
}

$pipelineProcessingIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, 'PipelineProcessing.ps1')
$fileProcessorIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, 'FileProcessor.ps1')
$workerResultIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, 'WorkerResult.ps1')
$pipelineEngineIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, 'PipelineEngine.ps1')
Assert-True ($pipelineProcessingIndex -ge 0) 'PipelineProcessing.ps1 must be runtime-loaded.'
Assert-True ($fileProcessorIndex -gt $pipelineProcessingIndex) 'FileProcessor.ps1 must load after PipelineProcessing.ps1.'
Assert-True ($workerResultIndex -gt $pipelineProcessingIndex) 'WorkerResult.ps1 must load after PipelineProcessing.ps1.'
Assert-True ($pipelineEngineIndex -gt $pipelineProcessingIndex) 'PipelineEngine.ps1 must load after PipelineProcessing.ps1.'

$encodeModuleOrder = @(
    'EncodeContext.ps1',
    'EncodePreflight.ps1',
    'EncodeAttemptPlan.ps1',
    'EncodeCommandBuilder.ps1',
    'EncodeExecution.ps1',
    'EncodeFallback.ps1',
    'EncodeVerification.ps1',
    'EncodeSizeGuard.ps1',
    'EncodePublish.ps1',
    'EncodeOrchestrator.ps1'
)
for ($i = 0; $i -lt $encodeModuleOrder.Count; $i++) {
    $moduleName = $encodeModuleOrder[$i]
    Assert-True ($engineModulePaths.ContainsKey($moduleName)) "Encode split module '$moduleName' must be in module_loader.ps1."
    $moduleIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, $moduleName)
    Assert-True ($moduleIndex -ge 0) "Encode split module '$moduleName' must be in engineModuleLoadOrder."
    if ($i -gt 0) {
        $previousIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, $encodeModuleOrder[$i - 1])
        Assert-True ($moduleIndex -gt $previousIndex) "Encode split module '$moduleName' must load after '$($encodeModuleOrder[$i - 1])'."
    }
    Assert-True ($moduleIndex -lt $pipelineProcessingIndex) "Encode split module '$moduleName' must load before PipelineProcessing.ps1 dispatchers."
}

$remuxModuleOrder = @(
    'RemuxContext.ps1',
    'RemuxPreflight.ps1',
    'RemuxSubtitlePlan.ps1',
    'RemuxFfmpegAvStage.ps1',
    'RemuxMkvmergeArgs.ps1',
    'RemuxMkvmergeStage.ps1',
    'RemuxVerification.ps1',
    'RemuxPublish.ps1',
    'RemuxOrchestrator.ps1'
)
for ($i = 0; $i -lt $remuxModuleOrder.Count; $i++) {
    $moduleName = $remuxModuleOrder[$i]
    Assert-True ($engineModulePaths.ContainsKey($moduleName)) "Remux split module '$moduleName' must be in module_loader.ps1."
    $moduleIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, $moduleName)
    Assert-True ($moduleIndex -ge 0) "Remux split module '$moduleName' must be in engineModuleLoadOrder."
    if ($i -gt 0) {
        $previousIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, $remuxModuleOrder[$i - 1])
        Assert-True ($moduleIndex -gt $previousIndex) "Remux split module '$moduleName' must load after '$($remuxModuleOrder[$i - 1])'."
    }
    Assert-True ($moduleIndex -lt $pipelineProcessingIndex) "Remux split module '$moduleName' must load before PipelineProcessing.ps1 dispatchers."
}

$mediaPipelineSliceRoot = Join-Path (Split-Path -Parent $entrypointPath) 'MediaPipeline'
. (Join-Path $mediaPipelineSliceRoot 'tx3g_sidecars.ps1')
. (Join-Path $mediaPipelineSliceRoot 'remux.ps1')
. (Join-Path $mediaPipelineSliceRoot 'encode.ps1')

foreach ($requiredFunction in @('Do-Encode', 'Do-Remux', 'Invoke-MediaPipelineProcessFile', 'Invoke-MediaPipelineRun')) {
    Assert-True ($null -ne (Get-Command -Name $requiredFunction -CommandType Function -ErrorAction SilentlyContinue)) "Startup load path must expose $requiredFunction."
}
if (Get-Command -Name Invoke-MediaPipelineEncode -CommandType Function -ErrorAction SilentlyContinue) {
    Assert-Matches $encodeText 'function\s+Do-Encode[\s\S]+Invoke-MediaPipelineEncode' 'Do-Encode wrapper must delegate to Invoke-MediaPipelineEncode once that orchestrator exists.'
}
if (Get-Command -Name Invoke-MediaPipelineRemux -CommandType Function -ErrorAction SilentlyContinue) {
    Assert-Matches $remuxText 'function\s+Do-Remux[\s\S]+Invoke-MediaPipelineRemux' 'Do-Remux wrapper must delegate to Invoke-MediaPipelineRemux once that orchestrator exists.'
}

$loaderIndex = Get-TextIndex $entrypointText '. $moduleLoaderSlice' 'MediaPipeline.ps1 must dot-source the engine module loader.'
$sliceIndex = Get-TextIndex $entrypointText "foreach (`$slice in @('tx3g_sidecars.ps1', 'remux.ps1', 'encode.ps1'))" 'MediaPipeline.ps1 must dot-source entrypoint slices in documented order.'
$drainMutationIndex = Get-TextIndex $entrypointText 'Invoke-RetryPendingPushes -Force' 'Drain path must still call Invoke-RetryPendingPushes only from the drain block.'
$singleFileDispatchIndex = Get-TextIndex $entrypointText 'Invoke-MediaPipelineProcessFile -file $sfItem' 'SingleFile worker path must dispatch through Invoke-MediaPipelineProcessFile.'
$runIndex = Get-TextIndex $entrypointText 'Invoke-MediaPipelineRun -EnginePlan $enginePlan' 'Default run path must dispatch through Invoke-MediaPipelineRun.'
Assert-True ($loaderIndex -lt $sliceIndex) 'Engine modules must load before entrypoint encode/remux slices.'
Assert-True ($sliceIndex -lt $drainMutationIndex) 'DrainPendingPushes must use the same module and slice graph before invoking drain mutation.'
Assert-True ($sliceIndex -lt $singleFileDispatchIndex) 'SingleFile worker-child mode must use the same module and slice graph before processing.'
Assert-True ($sliceIndex -lt $runIndex) 'Default run mode must use the same module and slice graph before queue processing.'

Assert-Matches $processingText '\$ok\s*=\s*Do-Encode\s+\$file\s+\$isTV\s+\$tvInfo' 'Invoke-MediaPipelineProcessFile must dispatch encode routes through Do-Encode.'
Assert-Matches $processingText '\$ok\s*=\s*Do-Remux\s+\$file\s+\$isTV\s+\$tvInfo' 'Invoke-MediaPipelineProcessFile must dispatch remux routes through Do-Remux.'

Assert-Matches $remuxText 'param\(\$file,\s*\[bool\]\$isTV,\s*\$tvInfo,\s*\[switch\]\s*\$FallbackFromOversizedEncode,\s*\[switch\]\s*\$FallbackFromDynamicHdrEncode\)' 'Do-Remux fallback switch signature changed.'
Assert-Matches $remuxContractText 'if\s*\(\$FallbackFromOversizedEncode\)\s*\{[\s\S]{0,160}\$script:LastRemuxFallbackRejection\s*=\s*\$null' 'Oversized encode remux fallback must clear prior rejection evidence before evaluation.'
Assert-Matches $remuxContractText 'if\s*\(\$FallbackFromDynamicHdrEncode\)\s*\{[\s\S]{0,180}\$script:LastDynamicHdrRemuxFallbackRejection\s*=\s*\$null' 'Dynamic HDR remux fallback must clear prior rejection evidence before evaluation.'
Assert-Matches $remuxContractText '\$script:LastDynamicHdrRemuxFallbackRejection\s*=\s*\[pscustomobject\]\[ordered\]@\{' 'Dynamic HDR remux fallback must record structured rejection evidence.'
Assert-Matches $remuxContractText '\$script:LastRemuxFallbackRejection\s*=\s*\[pscustomobject\]\[ordered\]@\{' 'Oversized encode remux fallback must record structured rejection evidence.'
Assert-Matches $remuxContractText '\$script:CurrentSizePolicyResult\s*=\s*\$fallbackSizePolicyResult' 'Oversized encode remux fallback must restore size-policy evidence on success.'
Assert-Matches $remuxContractText 'original_route_reason_code\s*=\s*(\$fallbackSourceRouteReasonCode|\$Context\.FallbackSourceRouteReasonCode)' 'Oversized encode remux fallback must preserve the original encode route reason code in trace evidence.'
Assert-Matches $remuxContractText '\$codecRoutePlan\.ReasonCode\s*=\s*''oversized_encode_remux_fallback''' 'Oversized encode remux fallback must publish with explicit fallback route reason code.'
Assert-Matches $remuxContractText '\$script:CurrentRouteReasonCode\s*=\s*\[string\]\$codecRoutePlan\.ReasonCode' 'Oversized encode remux fallback must restore script route reason code from the accepted fallback route plan.'
Assert-Matches $remuxContractText '\$script:LastPublishResult\s*=\s*New-ExistingOutputPublishResult' 'Existing-output remux branch must populate LastPublishResult.'
Assert-Matches $remuxContractText '\$script:LastPublishResult\s*=\s*\$publishResult' 'Remux publish handoff must populate LastPublishResult.'
Assert-Matches $remuxContractText 'if\s*\(\$publishResult\.KeepScratchInput\)\s*\{\s*\$Context\.LocalIn\s*=\s*\$null\s*\}' 'Remux publish handoff must honor KeepScratchInput.'
Assert-Matches $remuxContractText 'if\s*\(\$context\.FallbackFromOversizedEncode\)\s*\{\s*\$context\.LocalIn\s*=\s*\$null\s*\}' 'Oversized encode remux fallback must preserve scratch input on return to encode.'

foreach ($stage in @(
        'copy_to_scratch',
        'encode_prepare',
        'encode_cpu',
        'encode_verify',
        'remux_prepare',
        'remux_av',
        'remux_mux',
        'remux_verify',
        'processing',
        'completed',
        'failed'
    )) {
    Assert-ContainsText ($encodeContractText + $remuxContractText + $processingText) $stage "Expected progress/evidence stage '$stage' to remain present."
}

foreach ($failureStage in @(
        'remux-av',
        'remux-mkvmerge',
        'remux-verify',
        'remux-video-stream-verify',
        'encode',
        'encode-verify',
        'dynamic-hdr-output-verify',
        'encode-quality-verify',
        'encode-size-policy',
        'encode-exception'
    )) {
    Assert-ContainsText ($encodeContractText + $remuxContractText) $failureStage "Expected failure stage '$failureStage' to remain present."
}

foreach ($eventType in @(
        'job_started',
        'job_completed',
        'route_selected',
        'encoder_fallback_started',
        'encoder_fallback_completed'
    )) {
    Assert-ContainsText ($encodeContractText + $processingText) $eventType "Expected event type '$eventType' to remain present."
}

foreach ($commandStage in @('encode', 'encode-safe-retry', 'encode-cpu-fallback', 'remux-av', 'remux-mkvmerge')) {
    Assert-ContainsText ($encodeContractText + $remuxContractText) $commandStage "Expected repro/progress command stage '$commandStage' to remain present."
}

foreach ($helperFunction in @(
        'Invoke-MediaPipelineEncodeDynamicHdrPolicy',
        'Invoke-MediaPipelineEncodeStreamPreparation',
        'Invoke-MediaPipelineEncodeAttemptLadder',
        'Invoke-MediaPipelineEncodeVerification',
        'Invoke-MediaPipelineEncodeSizeGuard',
        'Complete-MediaPipelineEncodePublish'
    )) {
    Assert-Matches $encodeModuleText "function\s+$helperFunction\b" "Encode split must define helper $helperFunction before the orchestrator is reduced."
}

foreach ($candidate in @(
        @{ Name = 'EncodeCommandBuilder.ps1'; Path = 'ops\pipeline\engine\process\encode_command_builder.ps1' },
        @{ Name = 'RemuxMkvmergeArgs.ps1'; Path = 'ops\pipeline\engine\process\remux_mkvmerge_args.ps1' }
    )) {
    $path = Join-Path $repoRoot $candidate.Path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $text = Get-Content -LiteralPath $path -Raw
    if ($text -notmatch 'New-PipelinePlanExecutor') { continue }

    Assert-True ($engineModulePaths.ContainsKey('PipelinePlanExecutor.ps1')) "Live $($candidate.Name) delegates to pipeline_plan_executor.ps1, but PipelinePlanExecutor.ps1 is not in module_loader.ps1."
    Assert-True ($engineModulePaths.ContainsKey($candidate.Name)) "Live $($candidate.Name) is missing from module_loader.ps1."
    $executorIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, 'PipelinePlanExecutor.ps1')
    $callerIndex = [array]::IndexOf([object[]]$engineModuleLoadOrder, $candidate.Name)
    Assert-True ($executorIndex -ge 0 -and $executorIndex -lt $callerIndex) "PipelinePlanExecutor.ps1 must load before $($candidate.Name)."
}

Write-Host 'Pipeline processing split contract checks passed.'
