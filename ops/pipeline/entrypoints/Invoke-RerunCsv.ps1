[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$CsvPath,
    [string]$ConfigPath = '',
    [ValidateSet('copy')] [string]$DefaultStageMode = 'copy',
    [ValidateSet('keep')] [string]$DefaultOriginalMode = 'keep',
    [ValidateSet('park','pending_publish','publish_non_overlap','replace_original')] [string]$DefaultReturnMode = 'replace_original',
    [ValidateSet('one_at_a_time','windowed','batch_stage_all')] [string]$ExecutionMode = 'one_at_a_time',
    [ValidateSet('auto_replace_clean_else_pending_review','review_workspace','pending_publish','publish_non_overlap','publish_replace_final')] [string]$DestinationMode = 'auto_replace_clean_else_pending_review',
    [ValidateSet('keep','rename_after_publish','move_to_hold_after_publish','hold_then_delete_after_publish')] [string]$OriginalPolicy = 'keep',
    [ValidateSet('suffix','fail','replace_final')] [string]$CollisionPolicy = 'replace_final',
    [ValidateRange(1,100)] [int]$WindowSize = 1,
    [switch]$ConfirmReplaceFinal,
    [switch]$ConfirmSourceOverwrite,
    [switch]$ConfirmOriginalPolicy,
    [switch]$ConfirmDeleteOriginal,
    [switch]$DryRun,
    [switch]$PlanOnly,
    [switch]$ShowConfig
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '..\engine\rerun\entry_support.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\evidence.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\planning.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\publish.ps1')







Write-RerunLog "CSV rerun request: csv_path=$CsvPath config_path=$ConfigPath dry_run=$([bool]$DryRun) plan_only=$([bool]$PlanOnly)" "INFO"
Write-RerunLog "CSV rerun lifecycle policy: execution=$ExecutionMode destination=$DestinationMode original_policy=$OriginalPolicy collision=$CollisionPolicy window_size=$WindowSize. Source row mutation aliases remain rejected during planning." "INFO"
if ($DryRun -and $PlanOnly) {
    throw 'CSV rerun accepts either -DryRun or -PlanOnly, not both.'
}
if ($ExecutionMode -eq 'one_at_a_time') { $WindowSize = 1 }
if ($DestinationMode -eq 'auto_replace_clean_else_pending_review' -and $CollisionPolicy -ne 'replace_final') {
    throw 'auto_replace_clean_else_pending_review requires -CollisionPolicy replace_final.'
}
if ($DestinationMode -in @('auto_replace_clean_else_pending_review','publish_replace_final') -and -not $ConfirmReplaceFinal) {
    throw "$DestinationMode requires -ConfirmReplaceFinal."
}
if ($ConfirmSourceOverwrite -and -not $ConfirmReplaceFinal) {
    throw 'ConfirmSourceOverwrite requires -ConfirmReplaceFinal.'
}
if ($ConfirmSourceOverwrite -and -not (
    $DestinationMode -in @('auto_replace_clean_else_pending_review','publish_replace_final') -or
    ($DestinationMode -eq 'pending_publish' -and $CollisionPolicy -eq 'replace_final')
)) {
    throw 'ConfirmSourceOverwrite requires replace-final destination behavior.'
}
if ($OriginalPolicy -ne 'keep') {
    throw 'CSV rerun original source policies are disabled until final-output proof is recorded by a separate cleanup flow.'
}
if ($OriginalPolicy -ne 'keep' -and -not $ConfirmOriginalPolicy) {
    throw "$OriginalPolicy requires -ConfirmOriginalPolicy."
}
if ($OriginalPolicy -eq 'hold_then_delete_after_publish' -and -not $ConfirmDeleteOriginal) {
    throw 'hold_then_delete_after_publish requires -ConfirmDeleteOriginal; actual deletion remains a separate cleanup flow.'
}

$script:PipelineRoot = Split-Path -Parent $PSScriptRoot

$rerunIdentityModule = Join-Path $script:PipelineRoot 'engine\audit\rerun_source_identity.ps1'
if (-not (Test-Path -LiteralPath $rerunIdentityModule)) { throw "Rerun source identity module not found: $rerunIdentityModule" }
. $rerunIdentityModule

$rerunVersioningModule = Join-Path $script:PipelineRoot 'engine\shared\versioning.ps1'
if (-not (Test-Path -LiteralPath $rerunVersioningModule)) { throw "Rerun versioning module not found: $rerunVersioningModule" }
. $rerunVersioningModule
$script:RerunProductVersion = Get-MediaPipelineProductVersion
$script:RerunPipelineVersion = Get-MediaPipelineSidecarVersion























$script:RerunDiskSpaceTypeDefinition = @"
using System;
using System.Runtime.InteropServices;
namespace MediaPipeline {
    public static class RerunDiskSpace {
        [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetDiskFreeSpaceExW(
            string lpDirectoryName,
            out ulong lpFreeBytesAvailable,
            out ulong lpTotalNumberOfBytes,
            out ulong lpTotalNumberOfFreeBytes);
    }
}
"@



























































































































if (-not (Test-Path -LiteralPath $CsvPath -PathType Leaf)) {
    throw "CSV not found: $CsvPath"
}
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    # Default lookup: prefer current convention, fall back to legacy `_chatgpt` name.
    foreach ($candidate in @(
        (Join-Path $script:PipelineRoot 'config\MediaPipeline_config.psd1'),
        (Join-Path $script:PipelineRoot 'config\MediaPipeline_config_chatgpt.psd1'),
        (Join-Path $PSScriptRoot 'MediaPipeline_config.psd1'),
        (Join-Path $PSScriptRoot 'MediaPipeline_config_chatgpt.psd1')
    )) {
        $probe = $candidate
        if (Test-Path -LiteralPath $probe -PathType Leaf) { $ConfigPath = $probe; break }
    }
}
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "Config not found: $ConfigPath"
}

$config = Import-PowerShellDataFile -LiteralPath $ConfigPath
foreach ($key in @('LocalBase','Outsource','OutputContainer')) {
    if (-not $config.ContainsKey($key) -or [string]::IsNullOrWhiteSpace([string]$config[$key])) {
        throw "Config is missing required key for rerun mode: $key"
    }
}
if (-not $config.ContainsKey('CreateTVSubfolder')) { $config['CreateTVSubfolder'] = $true }
if (-not $config.ContainsKey('AggressiveEpisodeParsing')) { $config['AggressiveEpisodeParsing'] = $true }
if (-not $config.ContainsKey('ValidExtensions')) { $config['ValidExtensions'] = @('.mkv','.mp4','.m4v','.avi','.mov','.ts','.m2ts') }
if (-not $config.ContainsKey('PriorityMarkers')) { $config['PriorityMarkers'] = @('!') }

$script:RerunRobocopyFlags = if ($config.ContainsKey('RobocopyFlags')) { @($config['RobocopyFlags']) } else { @('/J', '/R:3', '/W:15', '/MT:2', '/NP', '/NDL', '/NFL') }
$script:RerunRobocopyTimeoutSeconds = 14400
if ($config.ContainsKey('RobocopyTimeoutSeconds')) {
    try { $script:RerunRobocopyTimeoutSeconds = [math]::Max(60, [int]$config['RobocopyTimeoutSeconds']) } catch {}
}
$script:RerunNestedPipelineTimeoutSeconds = 604800
if ($config.ContainsKey('RerunNestedPipelineTimeoutSeconds')) {
    try { $script:RerunNestedPipelineTimeoutSeconds = [math]::Max(3600, [int]$config['RerunNestedPipelineTimeoutSeconds']) } catch {}
}

$script:PriorityMarkers = @($config['PriorityMarkers'])
$script:AggressiveEpisodeParsing = [bool]$config['AggressiveEpisodeParsing']
$script:ValidExtensions = @($config['ValidExtensions'])
$CreateTVSubfolder = [bool]$config['CreateTVSubfolder']

$queuePlanModule = Join-Path $script:PipelineRoot 'engine\queue\queue_plan.ps1'
if (-not (Test-Path -LiteralPath $queuePlanModule)) { throw "QueuePlan module not found: $queuePlanModule" }
. $queuePlanModule

$namingModule = Join-Path $script:PipelineRoot 'engine\naming\naming.ps1'
if (-not (Test-Path -LiteralPath $namingModule)) { throw "Naming module not found: $namingModule" }
. $namingModule

$pipelinePath = Join-Path $PSScriptRoot 'MediaPipeline.ps1'
if (-not (Test-Path -LiteralPath $pipelinePath)) { throw "Pipeline script not found: $pipelinePath" }
$pwsh = Join-Path $script:PipelineRoot 'runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
if (-not (Test-Path -LiteralPath $pwsh)) { $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source }
if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
if (-not $pwsh) { throw 'PowerShell 7 host not found for nested pipeline run.' }

$localBase = Resolve-RerunPath ([string]$config['LocalBase'])
$mainOutsource = Resolve-RerunPath ([string]$config['Outsource'])
$resolvedCsvPath = Resolve-RerunPath $CsvPath
$resolvedConfigPath = Resolve-RerunPath $ConfigPath
$batchId = 'rerun_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$rerunStartedAtUtc = [datetime]::UtcNow
$localBaseTrimmed = $localBase.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
$localBaseParent = Split-Path -Parent $localBaseTrimmed
$localBaseLeaf = Split-Path -Leaf $localBaseTrimmed
if ([string]::IsNullOrWhiteSpace($localBaseParent) -or [string]::IsNullOrWhiteSpace($localBaseLeaf)) {
    throw "LocalBase must not be a filesystem root for CSV rerun workspace isolation: $localBase"
}
$rerunWorkspaceRoot = Join-Path $localBaseParent ($localBaseLeaf + '_RerunWorkspace')
$stageRoot = Join-Path $rerunWorkspaceRoot (Join-RerunPathParts @('RerunQueue', $batchId))
$parkRoot = Join-Path $rerunWorkspaceRoot (Join-RerunPathParts @('RerunParked', $batchId))
$nestedRuntimeRoot = Join-Path $rerunWorkspaceRoot 'RuntimeState'
$manifestRoot = Join-Path $localBase 'RerunManifests'
$manifestPath = Join-Path $manifestRoot "$batchId.json"
$outputRoot = Join-Path $parkRoot 'Output'
$pendingRoot = Join-Path $localBase 'State\PendingServerPush'
$completedRoot = Join-Path $localBase 'State\Completed'
$completedJobsManifest = Join-Path $completedRoot 'completed_jobs.jsonl'
$script:RerunCompletedJobsManifest = $completedJobsManifest
$finalHoldRoot = Join-Path $localBase 'State\Rerun\FinalReplaced'
$originalHoldRoot = Join-Path $localBase 'State\Rerun\OriginalHold'
$rerunControlRoot = Join-Path $localBase 'State\Rerun\Control'
$rerunStopMarkerPath = Join-Path $rerunControlRoot 'stop_after_current.json'

$ffprobePath = Join-Path $script:PipelineRoot 'tools\ffmpeg\bin\ffprobe.exe'
if (-not (Test-Path -LiteralPath $ffprobePath)) { $ffprobePath = '' }

$rows = @(Import-Csv -LiteralPath $CsvPath)
if ($rows.Count -eq 0) { throw "CSV contains no rows: $CsvPath" }

$plans = @(Resolve-RerunPlans -Rows $rows -Config $config -StageRoot $stageRoot -OutputRoot $outputRoot -FinalOutputRoot $mainOutsource -FfprobePath $ffprobePath)
$manifest = [ordered]@{
    batch_id = $batchId
    created_at = (Get-Date -Format 'o')
    csv_path = $resolvedCsvPath
    config_path = $resolvedConfigPath
    dry_run = [bool]$DryRun
    plan_only = [bool]$PlanOnly
    default_stage_mode = $DefaultStageMode
    default_original_mode = $DefaultOriginalMode
    default_return_mode = $DefaultReturnMode
    execution_mode = $ExecutionMode
    destination_mode = $DestinationMode
    original_policy = $OriginalPolicy
    collision_policy = $CollisionPolicy
    window_size = [int]$WindowSize
    confirm_replace_final = [bool]$ConfirmReplaceFinal
    confirm_source_overwrite = [bool]$ConfirmSourceOverwrite
    confirm_original_policy = [bool]$ConfirmOriginalPolicy
    confirm_delete_original = [bool]$ConfirmDeleteOriginal
    pipeline_local_base = $localBase
    nested_pipeline_local_base = $nestedRuntimeRoot
    nested_pipeline_local_base_mode = 'per_chunk_children'
    nested_pipeline_runtime_root = $nestedRuntimeRoot
    rerun_workspace_root = $rerunWorkspaceRoot
    library_profiles_rewritten = [bool]$config.ContainsKey('LibraryProfiles')
    stage_root = $stageRoot
    park_root = $parkRoot
    output_root = $outputRoot
    final_output_root = $mainOutsource
    pending_publish_root = $pendingRoot
    completed_jobs_manifest = $completedJobsManifest
    final_hold_root = $finalHoldRoot
    original_hold_root = $originalHoldRoot
    nested_pipeline_deferred_publish = $false
    nested_pipeline_deferred_publish_forced = $true
    stop_control_marker_path = $rerunStopMarkerPath
    nested_pipeline_timeout_seconds = [int]$script:RerunNestedPipelineTimeoutSeconds
    status = 'planned'
    rows = @($plans)
}

Write-RerunLog "CSV rerun selected path: $resolvedCsvPath"
Write-RerunLog "CSV rerun config path: $resolvedConfigPath"
Write-RerunLog "CSV rerun evidence: batch=$batchId manifest=$manifestPath workspace=$rerunWorkspaceRoot operator_local_base=$localBase nested_runtime_root=$nestedRuntimeRoot destination=$DestinationMode collision=$CollisionPolicy execution=$ExecutionMode window=$WindowSize dry_run=$([bool]$DryRun) plan_only=$([bool]$PlanOnly)"
Write-RerunLog "Rerun CSV rows listed: $($rows.Count); enabled/planned: $($plans.Count)"
foreach ($plan in $plans) {
    Write-RerunLog ("PLAN [{0}] {1} -> {2}" -f $plan.status, $plan.source_path, $plan.planned_output_path)
    if ($plan.reason) { Write-RerunLog ("  reason: {0}" -f $plan.reason) "WARN" }
}

if ($PlanOnly) {
    $manifest.status = 'plan_only_complete'
    $manifest.rows = @($plans)
    Write-RerunLog "PLAN ONLY complete. No manifest, temp config, stage, park, output, or source paths were written."
    exit 0
}

New-Item -ItemType Directory -Path $parkRoot -Force | Out-Null
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $nestedRuntimeRoot -Force | Out-Null
Write-RerunManifest -Path $manifestPath -Payload $manifest

if ($DryRun) {
    $manifest.status = 'dry_run_complete'
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
    Write-RerunLog "DRY RUN complete. Manifest: $manifestPath"
    exit 0
}

$pendingPlans = @($plans | Where-Object { $_.status -eq 'pending' })
if ($pendingPlans.Count -eq 0) {
    $manifest.status = 'failed'
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
    throw 'No CSV rows are executable for rerun.'
}

$chunkSize = if ($ExecutionMode -eq 'batch_stage_all') { [math]::Max(1, $pendingPlans.Count) } elseif ($ExecutionMode -eq 'windowed') { [math]::Max(1, [int]$WindowSize) } else { 1 }
$chunkIndex = 0
$pipelineExitFailures = 0
for ($offset = 0; $offset -lt $pendingPlans.Count; $offset += $chunkSize) {
    $chunkIndex++
    $take = [math]::Min($chunkSize, $pendingPlans.Count - $offset)
    $chunk = @($pendingPlans[$offset..($offset + $take - 1)])
    Reset-RerunStageRoot -StageRoot $stageRoot
    Invoke-RerunStagePlans -Plans $chunk
    $manifest.status = "staged_chunk_$chunkIndex"
    $manifest.current_phase = 'staged'
    $manifest.current_chunk = $chunkIndex
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest

    $runnable = @($chunk | Where-Object { $_.status -eq 'staged' })
    if ($runnable.Count -eq 0) {
        Write-RerunLog "Chunk $chunkIndex has no staged rows; skipping nested pipeline." "WARN"
        $manifest.status = "chunk_${chunkIndex}_complete"
        $manifest.current_phase = 'chunk_complete'
        $manifest.current_chunk = $chunkIndex
        $manifest.rows = @($plans)
        Write-RerunManifest -Path $manifestPath -Payload $manifest
        $stopRequest = Get-RerunStopAfterCurrentRequest -MarkerPath $rerunStopMarkerPath -BatchId $batchId -ManifestPath $manifestPath -CsvPath $resolvedCsvPath -StartedAtUtc $rerunStartedAtUtc
        if ($null -ne $stopRequest) {
            $counts = Update-RerunManifestCounts -Manifest $manifest -Plans $plans -PipelineExitFailures $pipelineExitFailures
            $manifest.status = 'stopped_after_current'
            $manifest.current_phase = 'stopped_after_current'
            $manifest.stopped_at = (Get-Date -Format 'o')
            $manifest.stop_request_id = Get-RerunObjectText -Object $stopRequest -Name 'request_id' -Default ''
            $manifest.stop_requested_at = Get-RerunObjectText -Object $stopRequest -Name 'created_at' -Default ''
            $manifest.stop_request_marker_path = $rerunStopMarkerPath
            $manifest.safe_next_action = 'Use Continue Pending Rows to start a new CSV rerun for rows still marked pending; failed and review rows require manual review.'
            $manifest.rows = @($plans)
            Write-RerunManifest -Path $manifestPath -Payload $manifest
            Write-RerunLog "CSV rerun stopped after chunk $chunkIndex before staging the next row/window. pending=$($counts.pending) success=$($counts.success) failed=$($counts.failed) stop_request=$($manifest.stop_request_id)"
            exit 0
        }
        continue
    }

    $chunkLocalBase = Join-Path $nestedRuntimeRoot ("{0}.chunk_{1:D4}" -f $batchId, $chunkIndex)
    New-Item -ItemType Directory -Path $chunkLocalBase -Force | Out-Null
    foreach ($plan in $runnable) {
        Set-RerunObjectValue -Object $plan -Name 'nested_pipeline_local_base' -Value $chunkLocalBase
        Set-RerunObjectValue -Object $plan -Name 'nested_pipeline_runtime_root' -Value $nestedRuntimeRoot
        Set-RerunObjectValue -Object $plan -Name 'rerun_workspace_root' -Value $rerunWorkspaceRoot
        Set-RerunObjectValue -Object $plan -Name 'rerun_chunk_index' -Value $chunkIndex
    }

    $tempConfig = [hashtable]::new($config)
    $tempConfig['LocalBase'] = $chunkLocalBase
    $tempConfig['SourceMovies'] = Join-Path $stageRoot 'Movies'
    $tempConfig['SourceTV'] = Join-Path $stageRoot 'TV'
    $tempConfig['Outsource'] = $outputRoot
    $tempConfig['ReprocessAll'] = $true
    $tempConfig['SkipStabilityCheck'] = $true
    $tempConfig['DeferredPublish'] = $false
    if ($tempConfig.ContainsKey('LibraryProfiles')) {
        $tempConfig['LibraryProfiles'] = New-RerunLibraryProfiles -Profiles $config['LibraryProfiles'] -StageRoot $stageRoot -OutputRoot $outputRoot
    }
    $tempConfigPath = Join-Path $manifestRoot ("{0}.chunk_{1:D4}.config.psd1" -f $batchId, $chunkIndex)
    Write-RerunTempConfig -Config $tempConfig -Path $tempConfigPath

    $args = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $pipelinePath,
        '-ConfigPath', $tempConfigPath,
        '-Once',
        '-SleepSeconds', '1'
    )
    if ($ShowConfig) { $args += '-ShowConfig' }

    Write-RerunLog "Launching nested pipeline for CSV-authoritative batch: $batchId chunk=$chunkIndex/$([math]::Ceiling($pendingPlans.Count / $chunkSize)) rows=$($runnable.Count)"
    Write-RerunLog "Operator LocalBase: $localBase"
    Write-RerunLog "Nested pipeline LocalBase: $chunkLocalBase"
    Write-RerunLog "Nested runtime root: $nestedRuntimeRoot"
    Write-RerunLog "CSV rerun workspace: $rerunWorkspaceRoot"
    if ($tempConfig.ContainsKey('LibraryProfiles')) { Write-RerunLog "CSV rerun library profiles rewritten to staged roots." }
    $pipelineRun = Invoke-RerunStreamingCommand -FilePath $pwsh -ArgumentList $args -TimeoutSeconds $script:RerunNestedPipelineTimeoutSeconds -Label "nested pipeline chunk $chunkIndex"
    $pipelineExit = [int]$pipelineRun.ExitCode
    if ($pipelineRun.TimedOut) {
        Write-RerunLog "Nested pipeline timed out after $($script:RerunNestedPipelineTimeoutSeconds)s" "ERROR"
    }
    if ($pipelineExit -ne 0) { $pipelineExitFailures++ }
    Write-RerunLog "Nested pipeline chunk $chunkIndex exited with code $pipelineExit"

    Complete-RerunPlans -Plans $runnable
    Invoke-RerunDestinationPolicy -Plans $runnable -BatchId $batchId -PendingRoot $pendingRoot -FinalHoldRoot $finalHoldRoot -OriginalHoldRoot $originalHoldRoot
    Remove-RerunStagedInputs -Plans $runnable
    $manifest.status = "chunk_${chunkIndex}_complete"
    $manifest.current_phase = 'chunk_complete'
    $manifest.current_chunk = $chunkIndex
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
    $stopRequest = Get-RerunStopAfterCurrentRequest -MarkerPath $rerunStopMarkerPath -BatchId $batchId -ManifestPath $manifestPath -CsvPath $resolvedCsvPath -StartedAtUtc $rerunStartedAtUtc
    if ($null -ne $stopRequest) {
        $counts = Update-RerunManifestCounts -Manifest $manifest -Plans $plans -PipelineExitFailures $pipelineExitFailures
        $manifest.status = 'stopped_after_current'
        $manifest.current_phase = 'stopped_after_current'
        $manifest.stopped_at = (Get-Date -Format 'o')
        $manifest.stop_request_id = Get-RerunObjectText -Object $stopRequest -Name 'request_id' -Default ''
        $manifest.stop_requested_at = Get-RerunObjectText -Object $stopRequest -Name 'created_at' -Default ''
        $manifest.stop_request_marker_path = $rerunStopMarkerPath
        $manifest.safe_next_action = 'Use Continue Pending Rows to start a new CSV rerun for rows still marked pending; failed and review rows require manual review.'
        $manifest.rows = @($plans)
        Write-RerunManifest -Path $manifestPath -Payload $manifest
        Write-RerunLog "CSV rerun stopped after chunk $chunkIndex before staging the next row/window. pending=$($counts.pending) success=$($counts.success) failed=$($counts.failed) stop_request=$($manifest.stop_request_id)"
        exit 0
    }
}

$counts = Update-RerunManifestCounts -Manifest $manifest -Plans $plans -PipelineExitFailures $pipelineExitFailures
$review = $counts.review
$pendingPublish = $counts.pending_publish
$published = $counts.published
$failed = $counts.failed
$success = $counts.success
$manifest.status = if ($failed -gt 0 -or $pipelineExitFailures -gt 0) { 'completed_with_failed_rows' } else { 'complete' }
$manifest.completed_at = (Get-Date -Format 'o')
$manifest.rows = @($plans)
Write-RerunManifest -Path $manifestPath -Payload $manifest

Write-RerunLog "Rerun batch complete: csv=$resolvedCsvPath batch=$batchId success=$success review=$review pending_publish=$pendingPublish published=$published failed=$failed pipeline_exit_failures=$pipelineExitFailures manifest=$manifestPath"
if ($pipelineExitFailures -gt 0 -or $failed -gt 0) { exit 1 }
exit 0
