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
    [switch]$ShowConfig,
    [string]$CommandId = '',
    [string]$LaunchId = '',
    [string]$BatchId = '',
    [string]$EnrollmentPath = '',
    [string]$ManifestPath = '',
    [ValidateRange(1,20)] [int]$SourceRetryMaxAttempts = 3,
    [ValidateRange(0,3600)] [int[]]$SourceRetryBackoffSeconds = @(5,15,45)
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '..\engine\shared\path_helpers.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\entry_support.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\evidence.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\recovery.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\planning.ps1')
. (Join-Path $PSScriptRoot '..\engine\rerun\publish.ps1')







Write-RerunLog "CSV rerun request: csv_path=$CsvPath config_path=$ConfigPath dry_run=$([bool]$DryRun) plan_only=$([bool]$PlanOnly) command_id=$CommandId launch_id=$LaunchId batch_id=$BatchId" "INFO"
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
Assert-RerunRobocopyFlagsSafe -Flags $script:RerunRobocopyFlags
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
$batchId = if ([string]::IsNullOrWhiteSpace($BatchId)) { 'rerun_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0, 8) } else { $BatchId.Trim() }
if ($batchId -notmatch '^[A-Za-z0-9._-]+$') { throw "CSV rerun BatchId contains unsupported characters: $batchId" }
$rerunStartedAtUtc = [datetime]::UtcNow
$localBaseTrimmed = $localBase.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
$localBaseParent = Split-Path -Parent $localBaseTrimmed
$localBaseLeaf = Split-Path -Leaf $localBaseTrimmed
if ([string]::IsNullOrWhiteSpace($localBaseParent) -or [string]::IsNullOrWhiteSpace($localBaseLeaf)) {
    throw "LocalBase must not be a filesystem root for CSV rerun workspace isolation: $localBase"
}
if (-not (Test-Path -LiteralPath $localBaseParent -PathType Container)) {
    throw "LocalBase parent must already exist as the trusted CSV rerun workspace anchor: $localBaseParent"
}
Assert-RerunScratchTrustAnchor -Path $localBaseParent | Out-Null
$rerunWorkspaceRoot = Join-Path $localBaseParent ($localBaseLeaf + '_RerunWorkspace')
$stageRoot = Join-Path $rerunWorkspaceRoot (Join-RerunPathParts @('RerunQueue', $batchId))
$parkRoot = Join-Path $rerunWorkspaceRoot (Join-RerunPathParts @('RerunParked', $batchId))
$nestedRuntimeRoot = Join-Path $rerunWorkspaceRoot 'RuntimeState'
$manifestRoot = Join-Path $localBase 'RerunManifests'
$expectedManifestPath = Resolve-RerunPath (Join-Path $manifestRoot "$batchId.json")
$manifestPath = if ([string]::IsNullOrWhiteSpace($ManifestPath)) { $expectedManifestPath } else { Resolve-RerunPath $ManifestPath }
if (-not (Test-RerunSamePath -Left $manifestPath -Right $expectedManifestPath)) {
    throw "CSV rerun ManifestPath must equal LocalBase\RerunManifests\$batchId.json: $manifestPath"
}
$executionManifestExistedAtStart = Test-Path -LiteralPath $manifestPath -PathType Leaf
if (-not $PlanOnly -and -not $executionManifestExistedAtStart) {
    if ([string]::IsNullOrWhiteSpace($CommandId)) { $CommandId = 'rerun-command-' + [guid]::NewGuid().ToString('N') }
    if ([string]::IsNullOrWhiteSpace($LaunchId)) { $LaunchId = 'rerun-launch-' + [guid]::NewGuid().ToString('N') }
}
$resolvedEnrollmentPath = if ([string]::IsNullOrWhiteSpace($EnrollmentPath)) { '' } else { Resolve-RerunPath $EnrollmentPath }
if (-not [string]::IsNullOrWhiteSpace($resolvedEnrollmentPath)) {
    $expectedEnrollmentPath = Resolve-RerunPath (Join-Path $localBase "State\Rerun\Local\$batchId.json")
    if (-not (Test-RerunSamePath -Left $resolvedEnrollmentPath -Right $expectedEnrollmentPath)) {
        throw "CSV rerun EnrollmentPath must equal LocalBase\State\Rerun\Local\$batchId.json: $resolvedEnrollmentPath"
    }
}
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

$script:RerunSourceRowsByIndex = @{}
$manifest = $null
$plans = @()
$pipelineExitFailures = 0

try {
    $resumeManifest = $null
    if (-not $PlanOnly) {
        if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
            $resumeManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
            $existingBatchId = [string](Get-RerunRecoveryValue -Object $resumeManifest -Name 'batch_id' -Default '')
            $existingCommandId = [string](Get-RerunRecoveryValue -Object $resumeManifest -Name 'command_id' -Default '')
            $existingLaunchId = [string](Get-RerunRecoveryValue -Object $resumeManifest -Name 'launch_id' -Default '')
            $existingEnrollmentPath = [string](Get-RerunRecoveryValue -Object $resumeManifest -Name 'enrollment_path' -Default '')
            if ([string]::IsNullOrWhiteSpace($existingBatchId) -or -not $existingBatchId.Equals($batchId, [System.StringComparison]::Ordinal)) {
                throw "Existing execution manifest batch_id does not match: $existingBatchId"
            }
            if ([string]::IsNullOrWhiteSpace($existingCommandId) -or [string]::IsNullOrWhiteSpace($existingLaunchId)) {
                throw 'Existing execution manifest has unsafe blank v2 command_id or launch_id correlation.'
            }
            if (-not [string]::IsNullOrWhiteSpace($CommandId) -and -not $existingCommandId.Equals($CommandId, [System.StringComparison]::Ordinal)) {
                throw 'Existing execution manifest command_id does not match the accepted correlation.'
            }
            if (-not [string]::IsNullOrWhiteSpace($LaunchId) -and -not $existingLaunchId.Equals($LaunchId, [System.StringComparison]::Ordinal)) {
                throw 'Existing execution manifest launch_id does not match the accepted correlation.'
            }
            if (-not [string]::IsNullOrWhiteSpace($resolvedEnrollmentPath)) {
                if ([string]::IsNullOrWhiteSpace($existingEnrollmentPath) -or -not (Test-RerunSamePath -Left $existingEnrollmentPath -Right $resolvedEnrollmentPath)) {
                    throw 'Existing execution manifest enrollment_path does not match the accepted correlation.'
                }
            }
            $CommandId = $existingCommandId
            $LaunchId = $existingLaunchId
            $resolvedEnrollmentPath = $existingEnrollmentPath
            if ([string]$resumeManifest.lifecycle_state -eq 'terminal') { throw 'Existing execution manifest is terminal and cannot be resumed in place.' }
            $manifest = $resumeManifest
            Set-RerunRecoveryValue -Object $manifest -Name 'schema_version' -Value 'rerun_batch_manifest.v2'
            Set-RerunManifestLifecycle -Manifest $manifest -State 'accepted' -Status 'accepted' -Phase 'accepted' -What 'A correlated restart was accepted.' -Why 'The supplied batch and execution manifest correlation match.' -Next 'Replan only safe rows and verify any staged scratch.' -ReasonCode 'resume_accepted' -ManifestPath $manifestPath -Persist
        } else {
            $manifest = [ordered]@{
                schema_version = 'rerun_batch_manifest.v2'
                command_id = $CommandId
                launch_id = $LaunchId
                batch_id = $batchId
                enrollment_path = $resolvedEnrollmentPath
                manifest_path = $manifestPath
                created_at = [datetime]::UtcNow.ToString('o')
                started_at = ''
                last_transition_at = ''
                transition_sequence = 0
                write_sequence = 0
                lifecycle_state = ''
                current_phase = ''
                current_row_index = -1
                timeline = @()
                csv_path = $resolvedCsvPath
                config_path = $resolvedConfigPath
                dry_run = [bool]$DryRun
                plan_only = $false
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
                source_retry_max_attempts = [int]$SourceRetryMaxAttempts
                source_retry_backoff_seconds = @($SourceRetryBackoffSeconds)
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
                status = ''
                rows = @()
            }
            Set-RerunManifestLifecycle -Manifest $manifest -State 'requested' -Status 'requested' -Phase 'requested' -What 'The PowerShell execution manifest was requested.' -Why 'A correlated CSV rerun process reached its execution entrypoint.' -Next 'Accept the immutable correlation identifiers.' -ReasonCode 'execution_requested' -ManifestPath $manifestPath -Persist
            Set-RerunManifestLifecycle -Manifest $manifest -State 'accepted' -Status 'accepted' -Phase 'accepted' -What 'The correlated CSV rerun execution was accepted.' -Why 'Command, launch, batch, enrollment, and manifest paths passed validation.' -Next 'Create the durable execution manifest before CSV planning.' -ReasonCode 'request_accepted' -ManifestPath $manifestPath -Persist
            Set-RerunManifestLifecycle -Manifest $manifest -State 'manifest_created' -Status 'manifest_created' -Phase 'manifest_created' -What 'The durable execution manifest was created.' -Why 'Failures during CSV import or planning now have a terminal evidence target.' -Next 'Import the CSV and classify each source independently.' -ReasonCode 'manifest_created' -ManifestPath $manifestPath -Persist
        }
    }

    $rows = @(Import-Csv -LiteralPath $CsvPath)
    if ($rows.Count -eq 0) { throw "CSV contains no rows: $CsvPath" }
    for ($rowIndex = 0; $rowIndex -lt $rows.Count; $rowIndex++) { $script:RerunSourceRowsByIndex[$rowIndex] = $rows[$rowIndex] }

    $freshPlans = @(Resolve-RerunPlans -Rows $rows -Config $config -StageRoot $stageRoot -OutputRoot $outputRoot -FinalOutputRoot $mainOutsource -FfprobePath $ffprobePath)
    $plans = if ($null -ne $resumeManifest) {
        @(Merge-RerunResumePlans -FreshPlans $freshPlans -ExistingManifest $resumeManifest -BatchScratchRoot $stageRoot -FfprobePath $ffprobePath)
    } else {
        @($freshPlans)
    }

    Write-RerunLog "CSV rerun selected path: $resolvedCsvPath"
    Write-RerunLog "CSV rerun config path: $resolvedConfigPath"
    Write-RerunLog "CSV rerun evidence: batch=$batchId command=$CommandId launch=$LaunchId enrollment=$resolvedEnrollmentPath manifest=$manifestPath workspace=$rerunWorkspaceRoot operator_local_base=$localBase nested_runtime_root=$nestedRuntimeRoot destination=$DestinationMode collision=$CollisionPolicy execution=$ExecutionMode window=$WindowSize dry_run=$([bool]$DryRun) plan_only=$([bool]$PlanOnly)"
    Write-RerunLog "Rerun CSV rows listed: $($rows.Count); enabled/planned: $($plans.Count)"
    foreach ($plan in $plans) {
        Write-RerunLog ("PLAN [{0}] {1} -> {2}" -f $plan.status, $plan.source_path, $plan.planned_output_path)
        if ($plan.reason) { Write-RerunLog ("  reason: {0}" -f $plan.reason) 'WARN' }
    }

    if ($PlanOnly) {
        Write-RerunLog 'PLAN ONLY complete. No manifest, temp config, stage, park, output, or source paths were written.'
        exit 0
    }

    $manifest.rows = @($plans)
    if ($null -ne $resumeManifest) {
        Set-RerunManifestLifecycle -Manifest $manifest -State 'manifest_created' -Status 'manifest_created' -Phase 'manifest_created' -What 'The prior execution manifest was loaded and reconciled.' -Why 'Only waiting, retry, interrupted staging, or identity-verified staged boundaries were eligible.' -Next 'Process healthy rows before bounded source retries.' -ReasonCode 'resume_manifest_reconciled' -ManifestPath $manifestPath -Persist
    } else {
        Write-RerunManifest -Path $manifestPath -Payload $manifest
    }

    foreach ($workspacePath in @($parkRoot, $outputRoot, $nestedRuntimeRoot, $stageRoot)) {
        Assert-RerunScratchPathBoundary -Path $workspacePath -Root $localBaseParent -AllowMissingLeaf | Out-Null
    }
    New-RerunScratchDirectorySafe -Path $parkRoot -ScratchTrustRoot $localBaseParent | Out-Null
    New-RerunScratchDirectorySafe -Path $outputRoot -ScratchTrustRoot $localBaseParent | Out-Null
    New-RerunScratchDirectorySafe -Path $nestedRuntimeRoot -ScratchTrustRoot $localBaseParent | Out-Null
    foreach ($workspacePath in @($parkRoot, $outputRoot, $nestedRuntimeRoot)) {
        Assert-RerunScratchPathBoundary -Path $workspacePath -Root $localBaseParent | Out-Null
    }

    if ($DryRun) {
        Set-RerunManifestLifecycle -Manifest $manifest -State 'terminal' -Status 'dry_run_complete' -Phase 'terminal' -What 'Dry-run planning completed.' -Why 'No media was staged or processed.' -Next 'Review the plan or start a live correlated rerun.' -ReasonCode 'dry_run_complete' -ManifestPath $manifestPath -Persist
        Write-RerunLog "DRY RUN complete. Manifest: $manifestPath"
        exit 0
    }

    $stageMoviesRoot = Join-Path $stageRoot 'Movies'
    $stageTvRoot = Join-Path $stageRoot 'TV'
    foreach ($liveStageDirectory in @($stageRoot, $stageMoviesRoot, $stageTvRoot)) {
        Assert-RerunScratchPathBoundary -Path $liveStageDirectory -Root $localBaseParent -AllowMissingLeaf | Out-Null
        New-RerunScratchDirectorySafe -Path $liveStageDirectory -ScratchTrustRoot $localBaseParent | Out-Null
        Assert-RerunScratchPathBoundary -Path $liveStageDirectory -Root $localBaseParent | Out-Null
    }

    $pendingPlans = @(Get-RerunSourceWorkOrder -Plans @($plans | Where-Object { [string]$_.status -in @('pending','waiting','retry_scheduled','staging','staged') }))
    if ($pendingPlans.Count -eq 0) { throw 'No CSV rows are executable for rerun.' }

    $chunkSize = if ($ExecutionMode -eq 'batch_stage_all') { [math]::Max(1, $pendingPlans.Count) } elseif ($ExecutionMode -eq 'windowed') { [math]::Max(1, [int]$WindowSize) } else { 1 }
    for ($offset = 0; $offset -lt $pendingPlans.Count; $offset += $chunkSize) {
        $chunkAllocation = New-RerunChunkAllocation -Manifest $manifest -Plans $plans -BatchId $batchId -NestedRuntimeRoot $nestedRuntimeRoot -ManifestRoot $manifestRoot
        $chunkIndex = [int]$chunkAllocation.chunk_index
        $take = [math]::Min($chunkSize, $pendingPlans.Count - $offset)
        $chunk = @($pendingPlans[$offset..($offset + $take - 1)])
        Set-RerunManifestLifecycle -Manifest $manifest -State 'staging' -Status 'staging' -Phase 'staging' -What "Chunk $chunkIndex entered verified staging." -Why 'Healthy rows are ordered ahead of source-waiting rows.' -Next 'Accept only atomically promoted scratch with matching full identity.' -ReasonCode 'staging_started' -CurrentRowIndex ([int]$chunk[0].row_index) -ManifestPath $manifestPath -Persist
        Invoke-RerunStagePlans -Plans $chunk -Config $config -StageRoot $stageRoot -OutputRoot $outputRoot -FinalOutputRoot $mainOutsource -FfprobePath $ffprobePath -MaxAttempts $SourceRetryMaxAttempts -BackoffSeconds $SourceRetryBackoffSeconds -Manifest $manifest -ManifestPath $manifestPath -ScratchTrustRoot $localBaseParent
        $manifest.current_chunk = $chunkIndex
        $manifest.rows = @($plans)
        Write-RerunManifest -Path $manifestPath -Payload $manifest

        $runnable = @($chunk | Where-Object { $_.status -eq 'staged' })
        if ($runnable.Count -eq 0) {
            Write-RerunLog "Chunk $chunkIndex has no staged rows; skipping nested pipeline." 'WARN'
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
                Add-RerunLifecycleTransition -Target $manifest -State 'terminal' -What 'Cooperative stop reached a safe chunk boundary.' -Why 'No nested or destination operation is in flight.' -Next $manifest.safe_next_action -ReasonCode 'stopped_after_current'
                $manifest.rows = @($plans)
                Write-RerunManifest -Path $manifestPath -Payload $manifest
                Write-RerunLog "CSV rerun stopped after chunk $chunkIndex before staging the next row/window. pending=$($counts.pending) success=$($counts.success) failed=$($counts.failed) stop_request=$($manifest.stop_request_id)"
                exit 0
            }
            continue
        }

        $chunkLocalBase = [string]$chunkAllocation.nested_pipeline_local_base
        Assert-RerunScratchPathBoundary -Path $chunkLocalBase -Root $localBaseParent -AllowMissingLeaf | Out-Null
        New-RerunScratchDirectorySafe -Path $chunkLocalBase -ScratchTrustRoot $localBaseParent | Out-Null
        Assert-RerunScratchPathBoundary -Path $chunkLocalBase -Root $localBaseParent | Out-Null
        foreach ($plan in $runnable) {
            $priorNestedLaunches = [int](Get-RerunRecoveryValue -Object $plan -Name 'nested_launch_count' -Default 0)
            if ($priorNestedLaunches -gt 0) {
                Set-RerunPlanLifecycle -Plan $plan -State 'review' -Status 'review' -What 'Duplicate nested launch was blocked.' -Why 'The row already contains nested-launch evidence.' -Next 'Review prior processing/output evidence before any retry.' -ReasonCode 'rerun_duplicate_nested_launch_blocked' -Retryable $false -OperatorActionRequired $true -AvailableOperatorAction 'Review prior nested processing evidence.' -Manifest $manifest -ManifestPath $manifestPath -Persist
                throw "Duplicate nested launch blocked for row $($plan.row_index)."
            }
            Set-RerunRecoveryValue -Object $plan -Name 'nested_launch_count' -Value 1
            Set-RerunRecoveryValue -Object $plan -Name 'nested_launch_id' -Value ([string]$chunkAllocation.nested_launch_id)
            Set-RerunObjectValue -Object $plan -Name 'nested_pipeline_local_base' -Value $chunkLocalBase
            Set-RerunObjectValue -Object $plan -Name 'nested_pipeline_runtime_root' -Value $nestedRuntimeRoot
            Set-RerunObjectValue -Object $plan -Name 'rerun_workspace_root' -Value $rerunWorkspaceRoot
            Set-RerunObjectValue -Object $plan -Name 'rerun_chunk_index' -Value $chunkIndex
            Set-RerunPlanLifecycle -Plan $plan -State 'processing' -Status 'processing' -What 'Nested media processing started from verified scratch.' -Why 'The staged source identity was verified before launch.' -Next 'Resolve produced output with evidence before destination policy.' -ReasonCode 'processing_started' -Retryable $false -OperatorActionRequired $false -Manifest $manifest -ManifestPath $manifestPath -Persist
        }
        Set-RerunManifestLifecycle -Manifest $manifest -State 'processing' -Status 'processing' -Phase 'processing' -What "Chunk $chunkIndex entered nested processing." -Why 'All runnable inputs are verified scratch copies.' -Next 'Record nested exit and verify produced output.' -ReasonCode 'processing_started' -CurrentRowIndex ([int]$runnable[0].row_index) -ManifestPath $manifestPath -Persist

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
        $tempConfigPath = [string]$chunkAllocation.temp_config_path
        Write-RerunTempConfig -Config $tempConfig -Path $tempConfigPath

        $args = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$pipelinePath,'-ConfigPath',$tempConfigPath,'-Once','-SleepSeconds','1')
        if ($ShowConfig) { $args += '-ShowConfig' }

        Write-RerunLog "Launching nested pipeline for CSV-authoritative batch: $batchId chunk=$chunkIndex/$([math]::Ceiling($pendingPlans.Count / $chunkSize)) rows=$($runnable.Count)"
        Write-RerunLog "Operator LocalBase: $localBase"
        Write-RerunLog "Nested pipeline LocalBase: $chunkLocalBase"
        Write-RerunLog "Nested runtime root: $nestedRuntimeRoot"
        Write-RerunLog "CSV rerun workspace: $rerunWorkspaceRoot"
        if ($tempConfig.ContainsKey('LibraryProfiles')) { Write-RerunLog 'CSV rerun library profiles rewritten to staged roots.' }
        $pipelineRun = Invoke-RerunStreamingCommand -FilePath $pwsh -ArgumentList $args -TimeoutSeconds $script:RerunNestedPipelineTimeoutSeconds -Label "nested pipeline chunk $chunkIndex"
        $pipelineExit = [int]$pipelineRun.ExitCode
        if ($pipelineRun.TimedOut) { Write-RerunLog "Nested pipeline timed out after $($script:RerunNestedPipelineTimeoutSeconds)s" 'ERROR' }
        if ($pipelineExit -ne 0) { $pipelineExitFailures++ }
        Write-RerunLog "Nested pipeline chunk $chunkIndex exited with code $pipelineExit"

        Complete-RerunPlans -Plans $runnable
        Set-RerunManifestLifecycle -Manifest $manifest -State 'destination_policy' -Status 'destination_policy' -Phase 'destination_policy' -What "Chunk $chunkIndex entered destination policy." -Why 'Nested processing ended and produced-output evidence was evaluated.' -Next 'Apply the configured destination policy idempotently.' -ReasonCode 'destination_policy_started' -CurrentRowIndex ([int]$runnable[0].row_index) -ManifestPath $manifestPath -Persist
        foreach ($plan in @($runnable | Where-Object { $_.status -eq 'complete' })) {
            Set-RerunPlanLifecycle -Plan $plan -State 'destination_policy' -Status 'complete' -What 'Verified output is ready for destination policy.' -Why ([string]$plan.reason) -Next 'Publish, park, or route to review according to backend-owned policy.' -ReasonCode 'destination_policy_started' -Retryable $false -OperatorActionRequired $false -Manifest $manifest -ManifestPath $manifestPath -Persist
        }
        Invoke-RerunDestinationPolicy -Plans $runnable -BatchId $batchId -PendingRoot $pendingRoot -FinalHoldRoot $finalHoldRoot -OriginalHoldRoot $originalHoldRoot
        foreach ($plan in $runnable) {
            $terminalStatus = [string]$plan.status
            $terminalCode = [string](Get-RerunRecoveryValue -Object $plan -Name 'failure_code' -Default '')
            Set-RerunPlanLifecycle -Plan $plan -State 'terminal' -Status $terminalStatus -What 'The row reached a durable destination outcome.' -Why ([string]$plan.reason) -Next 'No automatic replay is allowed beyond this recorded outcome.' -ReasonCode $terminalCode -Retryable $false -OperatorActionRequired ($terminalStatus -in @('failed','review','review_workspace')) -Manifest $manifest -ManifestPath $manifestPath -Persist
        }
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
            Add-RerunLifecycleTransition -Target $manifest -State 'terminal' -What 'Cooperative stop reached a safe chunk boundary.' -Why 'No nested or destination operation is in flight.' -Next $manifest.safe_next_action -ReasonCode 'stopped_after_current'
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
    $terminalBlockers = $counts.terminal_blockers
    $finalStatus = if ($terminalBlockers -gt 0) { 'completed_with_failures' } else { 'complete' }
    $manifest.rows = @($plans)
    Set-RerunManifestLifecycle -Manifest $manifest -State 'terminal' -Status $finalStatus -Phase 'terminal' -What 'The CSV rerun batch reached a terminal outcome.' -Why "success=$success review=$review pending_publish=$pendingPublish published=$published failed=$failed pipeline_exit_failures=$pipelineExitFailures terminal_blockers=$terminalBlockers" -Next 'Review any failed or review rows; successful rows require no replay.' -ReasonCode $finalStatus -ManifestPath $manifestPath -Persist

    Write-RerunLog "Rerun batch complete: csv=$resolvedCsvPath batch=$batchId success=$success review=$review pending_publish=$pendingPublish published=$published failed=$failed pipeline_exit_failures=$pipelineExitFailures terminal_blockers=$terminalBlockers manifest=$manifestPath"
    if ($terminalBlockers -gt 0) { exit 1 }
    exit 0
} catch {
    $failureMessage = [string]$_.Exception.Message
    if (-not $PlanOnly -and $null -ne $manifest -and -not [string]::IsNullOrWhiteSpace($manifestPath)) {
        try {
            $manifest.rows = @($plans)
            if ([string](Get-RerunRecoveryValue -Object $manifest -Name 'lifecycle_state' -Default '') -ne 'terminal') {
                Set-RerunManifestLifecycle -Manifest $manifest -State 'terminal' -Status 'failed' -Phase 'terminal' -What 'The CSV rerun execution failed.' -Why $failureMessage -Next 'Use the manifest evidence to retry only waiting/retry rows or verified staged scratch; ambiguous later work requires review.' -ReasonCode 'rerun_execution_failed' -ManifestPath $manifestPath -Persist
            }
        } catch {
            Write-RerunLog "CSV rerun terminal manifest finalization failed: $($_.Exception.Message)" 'ERROR'
        }
    }
    throw
}
