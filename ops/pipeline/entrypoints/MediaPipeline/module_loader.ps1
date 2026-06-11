# ==============================================================================
# MediaPipeline engine module loader  (dot-sourced by MediaPipeline.ps1)
# ==============================================================================
# Defines the engine module manifest ($engineModulePaths) and dot-sources every
# engine module, in dependency order, into the caller (entrypoint) scope so all
# modules share the entrypoint's $script: state. Reads $repoRootForModules from
# the caller (set in MediaPipeline.ps1 before this slice loads).
## Order matters slightly:
#   - Logging.ps1 defines Add-StartupWarning (called by the config-loader
#     helpers below), so it must be sourced first.
#   - PathHelpers.ps1 is listed before Native.ps1 for readability of the
#     dependency chain; Native.ps1 references Format-NativeCommandLine and
#     Test-IsUncPath at call time, not definition time.
#   - MediaConstants.ps1 owns shared route/codec/container names used by
#     routing, encode policy, probes, audio, subtitle, and failure helpers.
#   - FailureCodes.ps1, ConfigSchema.ps1, Routing.ps1, and EncodePolicy.ps1
#     are pure and mostly order-independent after constants are loaded.
#   - Native.ps1 references Write-Log/DebugLog (Logging) and
#     Format-NativeCommandLine/Test-IsUncPath (PathHelpers) at CALL time, so
#     it just needs both loaded before the main loop runs.
#   - NativeProcessContracts.ps1 loads before Native.ps1 and
#     FfmpegProgress.ps1 so all native runners share result metadata,
#     callback-safe stream draining, and timeout policy.
#   - Disk.ps1 loads after Native.ps1 because the robocopy helper uses the
#     bounded native-command runner and stop-aware sleep helper.
#   - ProgressState.ps1 loads before PendingPush.ps1 so pending-push retry
#     helpers can report progress.
#   - FfmpegProgress.ps1 loads after ProgressState.ps1 because the progress-aware
#     ffmpeg runner updates stage progress while it runs.
#   - PendingManifestStore.ps1 loads before PendingTransactions.ps1 and
#     PendingPush.ps1 so manifest read, write, validation, and retry-state
#     persistence stay isolated from the park/drain state machine.
#   - PendingTransactions.ps1 loads before PendingPush.ps1 so durable
#     pending-push park transactions stay isolated from operator-facing
#     logging, event emission, and drain/retry orchestration.
#   - PendingPublishIndex.ps1 loads after PendingPush.ps1 so index refresh can
#     call the existing pending_move repair helper without changing recovery
#     semantics.
#   - PublishCompletion.ps1 loads after PendingPush.ps1 because completed
#     output publish orchestration parks retry/deferred outputs.
# ==============================================================================
$engineModulePaths = @{
    'Audio.ps1'                 = Join-Path $repoRootForModules 'ops\pipeline\engine\audio\audio.ps1'
    'Logging.ps1'               = Join-Path $repoRootForModules 'ops\pipeline\engine\observability\logging.ps1'
    'ConfigGetters.ps1'          = Join-Path $repoRootForModules 'ops\pipeline\engine\config\getters.ps1'
    'RuntimeConfig.ps1'          = Join-Path $repoRootForModules 'ops\pipeline\engine\config\runtime_config.ps1'
    'ConfigKeys.ps1'             = Join-Path $repoRootForModules 'ops\pipeline\engine\config\config_keys.ps1'
    'ConfigSchema.ps1'           = Join-Path $repoRootForModules 'ops\pipeline\engine\config\config_schema.ps1'
    'Disk.ps1'                   = Join-Path $repoRootForModules 'ops\pipeline\engine\storage\disk.ps1'
    'EncodePolicy.ps1'           = Join-Path $repoRootForModules 'ops\pipeline\engine\decide\encode_policy.ps1'
    'ExecutableResolution.ps1'   = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\executable_resolution.ps1'
    'FailureCodes.ps1'           = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\failure_codes.ps1'
    'FailureState.ps1'           = Join-Path $repoRootForModules 'ops\pipeline\engine\failures\failure_state.ps1'
    'FfmpegProgress.ps1'         = Join-Path $repoRootForModules 'ops\pipeline\engine\process\ffmpeg_progress.ps1'
    'FileOverrides.ps1'          = Join-Path $repoRootForModules 'ops\pipeline\engine\queue\file_overrides.ps1'
    'FolderPolicy.ps1'           = Join-Path $repoRootForModules 'ops\pipeline\engine\policy\folder_policy.ps1'
    'LibraryIndex.ps1'           = Join-Path $repoRootForModules 'ops\pipeline\engine\library\library_index.ps1'
    'LocalWorkerSlots.ps1'       = Join-Path $repoRootForModules 'ops\pipeline\engine\queue\local_worker_slots.ps1'
    'MediaConstants.ps1'         = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\media_constants.ps1'
    'MediaProbe.ps1'             = Join-Path $repoRootForModules 'ops\pipeline\engine\probe\media_probe.ps1'
    'Naming.ps1'                 = Join-Path $repoRootForModules 'ops\pipeline\engine\naming\naming.ps1'
    'Native.ps1'                 = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\native.ps1'
    'NativeProcessContracts.ps1' = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\native_process_contracts.ps1'
    'OutputPathPlanning.ps1'     = Join-Path $repoRootForModules 'ops\pipeline\engine\paths\output_path_planning.ps1'
    'PathHelpers.ps1'            = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\path_helpers.ps1'
    'PendingManifestStore.ps1'   = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\pending_manifest_store.ps1'
    'PendingPublishIndex.ps1'    = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\pending_publish_index.ps1'
    'PendingPush.ps1'            = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\pending_push.ps1'
    'PendingTransactions.ps1'    = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\pending_transactions.ps1'
    'PipelineEngine.ps1'         = Join-Path $repoRootForModules 'ops\pipeline\engine\queue\pipeline_engine.ps1'
    'PipelineProcessing.ps1'     = Join-Path $repoRootForModules 'ops\pipeline\engine\process\pipeline_processing.ps1'
    'FileProcessor.ps1'          = Join-Path $repoRootForModules 'ops\pipeline\engine\process\file_processor.ps1'
    'WorkerResult.ps1'           = Join-Path $repoRootForModules 'ops\pipeline\engine\process\worker_result.ps1'
    'ProgressState.ps1'          = Join-Path $repoRootForModules 'ops\pipeline\engine\status\progress_state.ps1'
    'Publish.Partial.ps1'        = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\publish_partial.ps1'
    'Publish.Result.ps1'         = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\publish_result.ps1'
    'Publish.Sidecars.ps1'       = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\publish_sidecars.ps1'
    'PublishCompletion.ps1'      = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\publish_completion.ps1'
    'QueuePlan.ps1'              = Join-Path $repoRootForModules 'ops\pipeline\engine\queue\queue_plan.ps1'
    'Routing.ps1'                = Join-Path $repoRootForModules 'ops\pipeline\engine\decide\routing.ps1'
    'ScratchCopy.ps1'            = Join-Path $repoRootForModules 'ops\pipeline\engine\storage\scratch_copy.ps1'
    'ShowOverrides.ps1'          = Join-Path $repoRootForModules 'ops\pipeline\engine\decide\show_overrides.ps1'
    'Sidecar.ps1'                = Join-Path $repoRootForModules 'ops\pipeline\engine\publish\sidecar.ps1'
    'SourceIdentity.ps1'         = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\source_identity.ps1'
    'StateStore.ps1'             = Join-Path $repoRootForModules 'ops\pipeline\engine\storage\state_store.ps1'
    'Subtitles.ps1'              = Join-Path $repoRootForModules 'ops\pipeline\engine\subtitles\subtitles.ps1'
    'TempCleanup.ps1'            = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\temp_cleanup.ps1'
    'Versioning.ps1'             = Join-Path $repoRootForModules 'ops\pipeline\engine\shared\versioning.ps1'
}
# Documented topological load order. Must name exactly the modules in
# $engineModulePaths above; the contract check below fails fast on any drift.
$engineModuleLoadOrder = @('Logging.ps1', 'ConfigGetters.ps1', 'RuntimeConfig.ps1', 'ConfigKeys.ps1', 'ExecutableResolution.ps1', 'TempCleanup.ps1', 'PathHelpers.ps1', 'MediaConstants.ps1', 'ShowOverrides.ps1', 'Versioning.ps1', 'FailureCodes.ps1', 'ConfigSchema.ps1', 'StateStore.ps1', 'Routing.ps1', 'EncodePolicy.ps1', 'NativeProcessContracts.ps1', 'Native.ps1', 'Disk.ps1', 'MediaProbe.ps1', 'FolderPolicy.ps1', 'FileOverrides.ps1', 'Audio.ps1', 'Subtitles.ps1', 'ProgressState.ps1', 'FfmpegProgress.ps1', 'QueuePlan.ps1', 'Naming.ps1', 'OutputPathPlanning.ps1', 'SourceIdentity.ps1', 'ScratchCopy.ps1', 'LocalWorkerSlots.ps1', 'FailureState.ps1', 'Sidecar.ps1', 'Publish.Result.ps1', 'Publish.Partial.ps1', 'Publish.Sidecars.ps1', 'PendingManifestStore.ps1', 'PendingTransactions.ps1', 'PendingPush.ps1', 'PendingPublishIndex.ps1', 'PublishCompletion.ps1', 'LibraryIndex.ps1', 'PipelineProcessing.ps1', 'FileProcessor.ps1', 'WorkerResult.ps1', 'PipelineEngine.ps1')
$modulesMissingFromManifest = @($engineModuleLoadOrder | Where-Object { -not $engineModulePaths.ContainsKey($_) })
$modulesMissingFromLoadOrder = @($engineModulePaths.Keys | Where-Object { $engineModuleLoadOrder -notcontains $_ })
if ($modulesMissingFromManifest.Count -gt 0 -or
    $modulesMissingFromLoadOrder.Count -gt 0 -or
    $engineModuleLoadOrder.Count -ne $engineModulePaths.Count) {
    if ($modulesMissingFromManifest.Count -gt 0) {
        Write-Host "FATAL: engine modules in the load order but missing from the manifest: $($modulesMissingFromManifest -join ', ')" -ForegroundColor Red
    }
    if ($modulesMissingFromLoadOrder.Count -gt 0) {
        Write-Host "FATAL: engine modules in the manifest but missing from the load order: $($modulesMissingFromLoadOrder -join ', ')" -ForegroundColor Red
    }
    if ($engineModuleLoadOrder.Count -ne $engineModulePaths.Count) {
        Write-Host "FATAL: engine module load order lists $($engineModuleLoadOrder.Count) modules but the manifest defines $($engineModulePaths.Count) (duplicate or missing entry)." -ForegroundColor Red
    }
    # exit inside a dot-sourced slice only aborts this file, not the
    # entrypoint; the sentinel tells MediaPipeline.ps1 to exit for real.
    $startupFatalExitCode = 1
    exit 1
}
foreach ($module in $engineModuleLoadOrder) {
    $modulePath = $engineModulePaths[$module]
    if (-not (Test-Path -LiteralPath $modulePath)) {
        Write-Host "FATAL: required module not found: $modulePath" -ForegroundColor Red
        $startupFatalExitCode = 1
        exit 1
    }
    . $modulePath
}
