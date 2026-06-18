[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Reliability regression checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $PSCommandPath
$root = if ((Split-Path -Leaf $scriptDir) -eq 'Legacy') {
    Split-Path -Parent (Split-Path -Parent $scriptDir)
} else {
    Split-Path -Parent $scriptDir
}
$projectRoot = Split-Path -Parent $root

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Test-PowerShellParse {
    param([string]$Path)
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) {
        throw "PowerShell parse failed for ${Path}: $($errors[0])"
    }
}

function Get-FunctionText {
    param(
        [Parameter(Mandatory)] [string[]] $Path,
        [Parameter(Mandatory)] [string[]] $Names
    )
    foreach ($name in $Names) {
        $fn = $null
        $foundPath = $null
        foreach ($candidate in $Path) {
            $tokens = $null
            $errors = $null
            $ast = [System.Management.Automation.Language.Parser]::ParseFile($candidate, [ref]$tokens, [ref]$errors)
            if ($errors.Count -gt 0) {
                throw "PowerShell parse failed for ${candidate}: $($errors[0])"
            }
            $fn = $ast.Find({
                param($node)
                $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
                    $node.Name -eq $name
            }, $true)
            if ($fn) {
                $foundPath = $candidate
                break
            }
        }
        if (-not $fn) { throw "Function not found in pipeline files: $name" }
        $fn.Extent.Text
    }
}

function Invoke-PowerShellBehaviorCheck {
    param([Parameter(Mandatory)] [string] $ScriptText)
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-behavior-" + [guid]::NewGuid().ToString("N") + ".ps1")
    try {
        Set-Content -LiteralPath $tmp -Value $ScriptText -Encoding UTF8 -Force
        & (Get-Command pwsh).Source -NoProfile -ExecutionPolicy Bypass -File $tmp
        if ($LASTEXITCODE -ne 0) {
            throw "Behavior check failed with exit $LASTEXITCODE"
        }
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

$main = Join-Path $root 'MediaPipeline.ps1'
$moduleFiles = @(Get-ChildItem -Path (Join-Path $root 'Modules') -Filter '*.ps1' -File -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object { $_.FullName })
$mediaPipelineSliceFiles = @(Get-ChildItem -Path (Join-Path $root 'MediaPipeline') -Filter '*.ps1' -File -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object { $_.FullName })
$engineFiles = @(Get-ChildItem -Path (Join-Path $projectRoot 'engine') -Filter '*.ps1' -File -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName | ForEach-Object { $_.FullName })
$pipelineFiles = @($main) + $mediaPipelineSliceFiles + $moduleFiles + $engineFiles
$audit = Join-Path $root 'Audit-MediaLibrary.ps1'
$rerun = Join-Path $root 'Invoke-RerunCsv.ps1'
$rerunMetadata = Join-Path $root 'Get-RerunSourceMetadata.ps1'
$namingPreview = Join-Path $root 'Get-NamingPreview.ps1'
$rerunIdentity = Join-Path $projectRoot 'ops\pipeline\engine\audit\rerun_source_identity.ps1'
$backfill = Join-Path $root 'Backfill-CompletedManifest.ps1'
$subtitle = Join-Path $root 'ass_to_srt.py'
$setup = Join-Path $root 'Setup-MediaPipeline.ps1'
$services = Join-Path $projectRoot 'src\mediapipeline\desktop\services.py'
$serviceAppState = Join-Path $projectRoot 'app\schedule\app_state.py'
$serviceAppSchedule = Join-Path $projectRoot 'app\schedule\grid.py'
$serviceAuditRerun = Join-Path $projectRoot 'app\audit\rerun_service.py'
$serviceAuditRerunCsv = Join-Path $projectRoot 'app\audit\rerun_csv.py'
$serviceAuditRerunExport = Join-Path $projectRoot 'app\audit\rerun_export.py'
$serviceAuditRerunIo = Join-Path $projectRoot 'app\audit\rerun_io.py'
$serviceAuditRerunMetadata = Join-Path $projectRoot 'app\audit\rerun_metadata.py'
$serviceAuditRerunRecords = Join-Path $projectRoot 'app\audit\rerun_records.py'
$serviceCompleted = Join-Path $projectRoot 'app\completed\service.py'
$serviceCompletedBackfill = Join-Path $projectRoot 'app\completed\backfill.py'
$serviceCompletedManifest = Join-Path $projectRoot 'app\completed\manifest.py'
$serviceConfig = Join-Path $projectRoot 'app\config\service.py'
$serviceConfigDocumentRunner = Join-Path $projectRoot 'app\config\document_runner.py'
$serviceConfigSaveRunner = Join-Path $projectRoot 'app\config\save_runner.py'
$serviceConfigNumericPolicy = Join-Path $projectRoot 'app\config\numeric_policy.py'
$serviceConfigOptionPolicy = Join-Path $projectRoot 'app\config\option_policy.py'
$serviceConfigPathWarnings = Join-Path $projectRoot 'app\config\path_warnings.py'
$serviceConfigPreview = Join-Path $projectRoot 'app\config\preview.py'
$serviceConfigValidation = Join-Path $projectRoot 'app\config\validation.py'
$serviceConfigValueChecks = Join-Path $projectRoot 'app\config\value_checks.py'
$serviceConstants = Join-Path $projectRoot 'app\shared\constants.py'
$serviceFailureCleanup = Join-Path $projectRoot 'app\failures\cleanup_service.py'
$serviceFailureMarkers = Join-Path $projectRoot 'app\failures\markers.py'
$serviceFileOpen = Join-Path $projectRoot 'app\files\opening.py'
$serviceFileOpenPlan = Join-Path $projectRoot 'app\files\open_plan.py'
$serviceFolderPolicy = Join-Path $projectRoot 'app\folder_policy\service.py'
$serviceFolderPolicyContracts = Join-Path $projectRoot 'app\folder_policy\contracts.py'
$serviceFolderPolicyIo = Join-Path $projectRoot 'app\folder_policy\io.py'
$serviceFolderPolicyProbe = Join-Path $projectRoot 'app\folder_policy\probe.py'
$servicePendingPublish = Join-Path $projectRoot 'app\publish\pending_service.py'
$servicePendingPublishFormat = Join-Path $projectRoot 'app\publish\pending_format.py'
$servicePendingPublishManifest = Join-Path $projectRoot 'app\publish\pending_manifest.py'
$servicePendingPublishManifestRows = Join-Path $projectRoot 'app\publish\pending_manifest_rows.py'
$servicePendingPublishPaths = Join-Path $projectRoot 'app\publish\pending_paths.py'
$servicePathDefaults = Join-Path $projectRoot 'app\paths\defaults.py'
$servicePathHostRunner = Join-Path $projectRoot 'app\paths\host.py'
$servicePathLayout = Join-Path $projectRoot 'app\paths\layout.py'
$servicePathResolutionRunner = Join-Path $projectRoot 'app\paths\resolution_runner.py'
$servicePathStateMigration = Join-Path $projectRoot 'app\storage\state_migration.py'
$servicePaths = Join-Path $projectRoot 'app\paths\service.py'
$serviceProcesses = Join-Path $projectRoot 'app\processes\lifecycle.py'
$serviceProcessActiveJobs = Join-Path $projectRoot 'app\processes\active_jobs.py'
$serviceProcessActiveJobRunner = Join-Path $projectRoot 'app\processes\active_job_runner.py'
$serviceProcessControlFlags = Join-Path $projectRoot 'app\processes\control_flags.py'
$serviceProcessControlRunner = Join-Path $projectRoot 'app\processes\control_runner.py'
$serviceProcessKill = Join-Path $projectRoot 'app\processes\kill.py'
$serviceProcessLaunchCleanup = Join-Path $projectRoot 'app\processes\launch_cleanup.py'
$serviceProcessLaunchPlans = Join-Path $projectRoot 'app\processes\launch_plans.py'
$serviceProcessLaunchRunner = Join-Path $projectRoot 'app\processes\launch_runner.py'
$serviceProcessReadiness = Join-Path $projectRoot 'app\processes\readiness.py'
$serviceProcessRuntimeArtifacts = Join-Path $projectRoot 'app\processes\runtime_artifacts.py'
$serviceProcessRuntimeRunner = Join-Path $projectRoot 'app\processes\runtime_runner.py'
$serviceProcessSpawn = Join-Path $projectRoot 'app\processes\spawn.py'
$serviceProcessSpawnRunner = Join-Path $projectRoot 'app\processes\spawn_runner.py'
$serviceQueue = Join-Path $projectRoot 'app\queue\service.py'
$serviceQueueDryRun = Join-Path $projectRoot 'app\queue\dry_run.py'
$serviceQueueDryRunRunner = Join-Path $projectRoot 'app\queue\dry_run_runner.py'
$serviceQueuePreviewBuilder = Join-Path $projectRoot 'app\queue\preview_builder.py'
$serviceQueuePriority = Join-Path $projectRoot 'app\queue\priority_markers.py'
$serviceQueueSnapshot = Join-Path $projectRoot 'app\queue\snapshot.py'
$serviceRelease = Join-Path $projectRoot 'app\maintenance\release.py'
$serviceReleasePlan = Join-Path $projectRoot 'app\maintenance\release_plan.py'
$serviceReleaseResult = Join-Path $projectRoot 'app\maintenance\release_result.py'
$serviceRename = Join-Path $projectRoot 'app\rename\service.py'
$serviceRenameApply = Join-Path $projectRoot 'app\rename\apply.py'
$serviceRenameApplyRunner = Join-Path $projectRoot 'app\rename\apply_runner.py'
$serviceRenameDiscovery = Join-Path $projectRoot 'app\rename\discovery.py'
$serviceRenamePlanPolicy = Join-Path $projectRoot 'app\rename\plan_policy.py'
$serviceRenamePlanner = Join-Path $projectRoot 'app\rename\planner.py'
$serviceRenamePreview = Join-Path $projectRoot 'app\rename\preview.py'
$serviceRenamePreviewRunner = Join-Path $projectRoot 'app\rename\preview_runner.py'
$serviceRenameTv = Join-Path $projectRoot 'app\rename\tv.py'
$serviceRenameTvFolder = Join-Path $projectRoot 'app\rename\tv_folder.py'
$serviceStatus = Join-Path $projectRoot 'app\status\service.py'
$serviceStatusActiveJobs = Join-Path $projectRoot 'app\status\active_jobs.py'
$serviceStatusEvents = Join-Path $projectRoot 'app\status\events.py'
$serviceStatusFiles = Join-Path $projectRoot 'app\observability\status_files.py'
$serviceStatusPresentation = Join-Path $projectRoot 'app\status\presentation.py'
$serviceStatusProgress = Join-Path $projectRoot 'app\status\progress.py'
$serviceStatusReaders = Join-Path $projectRoot 'app\status\readers.py'
$serviceStatusSnapshotRunner = Join-Path $projectRoot 'app\status\snapshot_runner.py'
$serviceStatusSummary = Join-Path $projectRoot 'app\status\summary.py'
$serviceStatusSummarySections = Join-Path $projectRoot 'app\status\summary_sections.py'
$serviceTelemetry = Join-Path $projectRoot 'app\telemetry\service.py'
$serviceTelemetryHealth = Join-Path $projectRoot 'app\telemetry\health.py'
$serviceTelemetryNvidia = Join-Path $projectRoot 'app\telemetry\nvidia.py'
$serviceTelemetrySystem = Join-Path $projectRoot 'app\observability\system_metrics.py'
$subprocessRunner = Join-Path $projectRoot 'src\mediapipeline\desktop\subprocess_runner.py'
$settingsRiskPolicy = Join-Path $projectRoot 'src\mediapipeline\desktop\application\settings_risk_policy.py'
$settingsRiskPolicyRules = Join-Path $projectRoot 'src\mediapipeline\desktop\application\settings_risk_policy_rules.py'
$facadeCompleted = Join-Path $projectRoot 'app\completed\facade.py'
$facadeCompletedPolicy = Join-Path $projectRoot 'app\completed\policy.py'
$facadeCompletedOpen = Join-Path $projectRoot 'app\completed\open_facade.py'
$facadeCompletedOpenPolicy = Join-Path $projectRoot 'app\completed\open_policy.py'
$facadeMaintenance = Join-Path $projectRoot 'app\maintenance\facade.py'
$facadeMaintenanceBackfill = Join-Path $projectRoot 'app\maintenance\backfill_facade.py'
$facadeMaintenanceCommands = Join-Path $projectRoot 'app\maintenance\commands_facade.py'
$facadeMaintenanceCommandPolicy = Join-Path $projectRoot 'app\maintenance\command_policy.py'
$facadeMaintenancePolicy = Join-Path $projectRoot 'app\maintenance\policy.py'
$facadeMaintenanceRelease = Join-Path $projectRoot 'app\maintenance\release_facade.py'
$facadeFailures = Join-Path $projectRoot 'app\failures\facade.py'
$facadeFailuresPolicy = Join-Path $projectRoot 'app\failures\policy.py'
$facadeAudit = Join-Path $projectRoot 'app\audit\facade.py'
$facadeAuditPolicy = Join-Path $projectRoot 'app\audit\preview_policy.py'
$facadePendingPublish = Join-Path $projectRoot 'app\publish\pending_facade.py'
$facadePendingPublishPolicy = Join-Path $projectRoot 'app\publish\pending_policy.py'
$facadeQueue = Join-Path $projectRoot 'app\queue\facade.py'
$facadeQueuePolicy = Join-Path $projectRoot 'app\queue\policy.py'
$facadeSchedule = Join-Path $projectRoot 'app\schedule\facade.py'
$facadeSchedulePolicy = Join-Path $projectRoot 'app\schedule\policy.py'
$facadeSettings = Join-Path $projectRoot 'app\config\settings_facade.py'
$facadeSettingsPatch = Join-Path $projectRoot 'app\config\settings_patch_facade.py'
$facadeSettingsPatchCandidate = Join-Path $projectRoot 'app\config\settings_patch_candidate_facade.py'
$facadeSettingsPatchPolicy = Join-Path $projectRoot 'app\config\settings_patch_policy.py'
$facadeSettingsPolicy = Join-Path $projectRoot 'app\config\settings_policy.py'
$facadeProcessPipeline = Join-Path $projectRoot 'app\processes\pipeline_facade.py'
$facadeProcessPipelinePolicy = Join-Path $projectRoot 'app\processes\pipeline_policy.py'
$facadeProcessAudit = Join-Path $projectRoot 'app\processes\audit_facade.py'
$facadeProcessAuditPolicy = Join-Path $projectRoot 'app\processes\audit_policy.py'
$facadeProcessRerun = Join-Path $projectRoot 'app\processes\rerun_facade.py'
$facadeProcessRerunPolicy = Join-Path $projectRoot 'app\processes\rerun_policy.py'
$facadeProcessControl = Join-Path $projectRoot 'app\processes\control_facade.py'
$facadeProcessControlPolicy = Join-Path $projectRoot 'app\processes\control_policy.py'
$facadeProcessSchedule = Join-Path $projectRoot 'app\processes\schedule_facade.py'
$facadeProcessSchedulePolicy = Join-Path $projectRoot 'app\processes\schedule_policy.py'
$facadeProcessGuard = Join-Path $projectRoot 'app\processes\guard_facade.py'
$facadeProcessGuardPolicy = Join-Path $projectRoot 'app\processes\guard_policy.py'
$facadeDiagnostics = Join-Path $projectRoot 'app\diagnostics\facade.py'
$facadeDiagnosticsPolicy = Join-Path $projectRoot 'app\diagnostics\policy.py'
$facadeDiagnosticsOpenPolicy = Join-Path $projectRoot 'app\diagnostics\open_policy.py'
$facadeStatus = Join-Path $projectRoot 'app\observability\status_facade.py'
$facadeStatusPolicy = Join-Path $projectRoot 'app\observability\status_policy.py'
$facadeRename = Join-Path $projectRoot 'app\rename\facade.py'
$facadeRenamePolicy = Join-Path $projectRoot 'app\rename\policy.py'
$app = Join-Path $projectRoot 'src\mediapipeline\desktop\app.py'
$appBootstrap = Join-Path $projectRoot 'src\mediapipeline\desktop\app_bootstrap.py'
$controllersInit = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\__init__.py'
$appStateController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\app_state_controller.py'
$auditActionsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\audit_actions_controller.py'
$auditController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\audit_controller.py'
$auditTableController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\audit_table_controller.py'
$completedActionsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\completed_actions_controller.py'
$completedAnalyticsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\completed_analytics_controller.py'
$completedController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\completed_controller.py'
$completedTableController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\completed_table_controller.py'
$diagnosticsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\diagnostics_controller.py'
$failureActionsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\failure_actions_controller.py'
$failureController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\failure_controller.py'
$failureTableController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\failure_table_controller.py'
$feedbackController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\feedback_controller.py'
$fileActionsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\file_actions_controller.py'
$folderPolicyController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\folder_policy_controller.py'
$homeController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\home_controller.py'
$homeSummaryController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\home_summary_controller.py'
$maintenanceController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\maintenance_controller.py'
$navigationController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\navigation_controller.py'
$navigationSidebarController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\navigation_sidebar_controller.py'
$networkController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\network_controller.py'
$notificationController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\notification_controller.py'
$pendingPublishController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\pending_publish_controller.py'
$pipelineController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\pipeline_controller.py'
$processLifecycleController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\process_lifecycle_controller.py'
$queueController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_controller.py'
$queueDragController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_drag_controller.py'
$queueFileActionsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_file_actions_controller.py'
$queueMetricsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_metrics_controller.py'
$queuePriorityController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_priority_controller.py'
$queueRefreshController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_refresh_controller.py'
$queueTableController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_table_controller.py'
$queueThumbnailController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\queue_thumbnail_controller.py'
$releaseController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\release_controller.py'
$renameController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\rename_controller.py'
$renameTableController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\rename_table_controller.py'
$rerunController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\rerun_controller.py'
$scheduleController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\schedule_controller.py'
$settingsController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\settings_controller.py'
$settingsFormController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\settings_form_controller.py'
$settingsPersistenceController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\settings_persistence_controller.py'
$settingsProfileController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\settings_profile_controller.py'
$statusPresentationController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\status_presentation_controller.py'
$statusServerController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\status_server_controller.py'
$telemetryController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\telemetry_controller.py'
$workGuardController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\work_guard_controller.py'
$workerController = Join-Path $projectRoot 'src\mediapipeline\desktop\controllers\worker_controller.py'
$workers = Join-Path $projectRoot 'src\mediapipeline\desktop\workers.py'
$priorityMarkers = Join-Path $projectRoot 'src\mediapipeline\desktop\priority_markers.py'
$configSchema = Join-Path $projectRoot 'app\config\metadata.py'
$pipelineEventsContract = Join-Path $projectRoot 'src\mediapipeline\desktop\contracts\pipeline_events.py'
$progressContract = Join-Path $projectRoot 'src\mediapipeline\desktop\contracts\progress.py'
$activeJobContract = Join-Path $projectRoot 'src\mediapipeline\desktop\contracts\active_job.py'
$controlFlagContract = Join-Path $projectRoot 'src\mediapipeline\desktop\contracts\control_flag.py'
$pendingPublishContract = Join-Path $projectRoot 'src\mediapipeline\desktop\contracts\pending_publish.py'
$appShellView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\app_shell.py'
$homeView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\home.py'
$liveView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\live.py'
$queueView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\queue.py'
$libraryView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\library.py'
$diagnosticsView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\diagnostics.py'
$diagnosticsDrawerView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\diagnostics_drawer.py'
$maintenanceView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\maintenance.py'
$renameView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\rename.py'
$rerunView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\rerun.py'
$scheduleView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\schedule.py'
$settingsView = Join-Path $projectRoot 'src\mediapipeline\desktop\views\settings.py'
$viewsInit = Join-Path $projectRoot 'src\mediapipeline\desktop\views\__init__.py'
$toolIntegration = Join-Path $root 'Tests\Invoke-ToolIntegrationChecks.ps1'
$endToEndSmoke = Join-Path $root 'Tests\Invoke-EndToEndSmokeChecks.ps1'
$configJsonSchema = Join-Path $root 'Schemas\media_pipeline_config.schema.json'
$progressJsonSchema = Join-Path $root 'Schemas\media_pipeline_progress.schema.json'
$controlFlagJsonSchema = Join-Path $root 'Schemas\media_pipeline_control_flag.schema.json'
$pendingManifestJsonSchema = Join-Path $root 'Schemas\media_pipeline_pending_push_manifest.schema.json'
$folderPolicyExample = Join-Path $root 'Schemas\media_pipeline_folder_policy.example.json'
$releaseBuilder = Join-Path $projectRoot 'ops\scripts\ops\release\metadata\build.ps1'
$environmentVerifier = Join-Path $projectRoot 'ops\scripts\dev\verify-env.ps1'
$releaseVerifier = Join-Path $projectRoot 'ops\scripts\ops\release\metadata\test.ps1'
$deployabilityChecklistCandidates = @(
    (Join-Path $projectRoot 'docs\architecture\DEPLOYABILITY_CHECKLIST.md'),
    (Join-Path $projectRoot 'docs\DEPLOYABILITY_CHECKLIST.md'),
    (Join-Path $projectRoot 'docs\archive\docs-housekeeping\2026-05-20-review\consolidated-after-extraction\docs\architecture\DEPLOYABILITY_CHECKLIST.md')
)
$deployabilityChecklist = @($deployabilityChecklistCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1)[0]
if (-not $deployabilityChecklist) {
    throw "Deployability checklist was not found. Checked: $($deployabilityChecklistCandidates -join '; ')"
}
$configTemplate = Join-Path $root 'MediaPipeline_config_template.psd1'

Test-PowerShellParse $main
foreach ($mediaPipelineSliceFile in $mediaPipelineSliceFiles) {
    Test-PowerShellParse $mediaPipelineSliceFile
}
foreach ($moduleFile in $moduleFiles) {
    Test-PowerShellParse $moduleFile
}
Test-PowerShellParse $audit
Test-PowerShellParse $rerun
Test-PowerShellParse $rerunMetadata
Test-PowerShellParse $namingPreview
Test-PowerShellParse $setup
Test-PowerShellParse $endToEndSmoke
Test-PowerShellParse $releaseBuilder
Test-PowerShellParse $environmentVerifier
Test-PowerShellParse $releaseVerifier

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $pythonCompileTargets = @($subtitle) + @(
        Get-ChildItem -LiteralPath (Join-Path $projectRoot 'src\mediapipeline\desktop') -Filter '*.py' -File -Recurse |
            Select-Object -ExpandProperty FullName
    )
    foreach ($pythonCompileTarget in $pythonCompileTargets) {
        & $python.Source -m py_compile $pythonCompileTarget
        if ($LASTEXITCODE -ne 0) { throw "Python compile checks failed for $pythonCompileTarget." }
    }
} else {
    Write-Warning "python not found on PATH; skipped Python compile checks."
}

$mainFileText = Get-Content -LiteralPath $main -Raw
$mediaPipelineSliceTexts = @($mediaPipelineSliceFiles | ForEach-Object { Get-Content -LiteralPath $_ -Raw })
$mainText = (@($mainFileText) + $mediaPipelineSliceTexts) -join [Environment]::NewLine
$moduleTexts = @($moduleFiles | ForEach-Object { Get-Content -LiteralPath $_ -Raw })
$engineTexts = @($engineFiles | ForEach-Object { Get-Content -LiteralPath $_ -Raw })
$pipelineText = (@($mainText) + $moduleTexts + $engineTexts) -join [Environment]::NewLine
$auditText = Get-Content -LiteralPath $audit -Raw
$rerunText = Get-Content -LiteralPath $rerun -Raw
$rerunMetadataText = Get-Content -LiteralPath $rerunMetadata -Raw
$namingPreviewText = Get-Content -LiteralPath $namingPreview -Raw
$rerunIdentityText = Get-Content -LiteralPath $rerunIdentity -Raw
$subtitleText = Get-Content -LiteralPath $subtitle -Raw
$setupText = Get-Content -LiteralPath $setup -Raw
$servicesText = Get-Content -LiteralPath $services -Raw
$serviceAppStateText = Get-Content -LiteralPath $serviceAppState -Raw
$serviceAppScheduleText = Get-Content -LiteralPath $serviceAppSchedule -Raw
$serviceAuditRerunText = Get-Content -LiteralPath $serviceAuditRerun -Raw
$serviceAuditRerunCsvText = Get-Content -LiteralPath $serviceAuditRerunCsv -Raw
$serviceAuditRerunExportText = Get-Content -LiteralPath $serviceAuditRerunExport -Raw
$serviceAuditRerunIoText = Get-Content -LiteralPath $serviceAuditRerunIo -Raw
$serviceAuditRerunMetadataText = Get-Content -LiteralPath $serviceAuditRerunMetadata -Raw
$serviceAuditRerunRecordsText = Get-Content -LiteralPath $serviceAuditRerunRecords -Raw
$serviceCompletedText = Get-Content -LiteralPath $serviceCompleted -Raw
$serviceCompletedBackfillText = Get-Content -LiteralPath $serviceCompletedBackfill -Raw
$serviceCompletedManifestText = Get-Content -LiteralPath $serviceCompletedManifest -Raw
$completedServiceText = $serviceCompletedText + $serviceCompletedBackfillText + $serviceCompletedManifestText
$serviceConfigText = Get-Content -LiteralPath $serviceConfig -Raw
$serviceConfigDocumentRunnerText = Get-Content -LiteralPath $serviceConfigDocumentRunner -Raw
$serviceConfigSaveRunnerText = Get-Content -LiteralPath $serviceConfigSaveRunner -Raw
$serviceConfigNumericPolicyText = Get-Content -LiteralPath $serviceConfigNumericPolicy -Raw
$serviceConfigOptionPolicyText = Get-Content -LiteralPath $serviceConfigOptionPolicy -Raw
$serviceConfigPathWarningsText = Get-Content -LiteralPath $serviceConfigPathWarnings -Raw
$serviceConfigPreviewText = Get-Content -LiteralPath $serviceConfigPreview -Raw
$serviceConfigValidationText = Get-Content -LiteralPath $serviceConfigValidation -Raw
$serviceConfigValueChecksText = Get-Content -LiteralPath $serviceConfigValueChecks -Raw
$serviceConstantsText = Get-Content -LiteralPath $serviceConstants -Raw
$serviceFailureCleanupText = Get-Content -LiteralPath $serviceFailureCleanup -Raw
$serviceFailureMarkersText = Get-Content -LiteralPath $serviceFailureMarkers -Raw
$serviceFileOpenText = Get-Content -LiteralPath $serviceFileOpen -Raw
$serviceFileOpenPlanText = Get-Content -LiteralPath $serviceFileOpenPlan -Raw
$serviceFolderPolicyText = Get-Content -LiteralPath $serviceFolderPolicy -Raw
$serviceFolderPolicyContractsText = Get-Content -LiteralPath $serviceFolderPolicyContracts -Raw
$serviceFolderPolicyIoText = Get-Content -LiteralPath $serviceFolderPolicyIo -Raw
$serviceFolderPolicyProbeText = Get-Content -LiteralPath $serviceFolderPolicyProbe -Raw
$servicePendingPublishText = Get-Content -LiteralPath $servicePendingPublish -Raw
$servicePendingPublishFormatText = Get-Content -LiteralPath $servicePendingPublishFormat -Raw
$servicePendingPublishManifestText = Get-Content -LiteralPath $servicePendingPublishManifest -Raw
$servicePendingPublishManifestRowsText = Get-Content -LiteralPath $servicePendingPublishManifestRows -Raw
$servicePendingPublishPathsText = Get-Content -LiteralPath $servicePendingPublishPaths -Raw
$servicePathDefaultsText = Get-Content -LiteralPath $servicePathDefaults -Raw
$servicePathHostRunnerText = Get-Content -LiteralPath $servicePathHostRunner -Raw
$servicePathLayoutText = Get-Content -LiteralPath $servicePathLayout -Raw
$servicePathResolutionRunnerText = Get-Content -LiteralPath $servicePathResolutionRunner -Raw
$servicePathStateMigrationText = Get-Content -LiteralPath $servicePathStateMigration -Raw
$servicePathsText = Get-Content -LiteralPath $servicePaths -Raw
$serviceProcessesText = Get-Content -LiteralPath $serviceProcesses -Raw
$serviceProcessActiveJobsText = Get-Content -LiteralPath $serviceProcessActiveJobs -Raw
$serviceProcessActiveJobRunnerText = Get-Content -LiteralPath $serviceProcessActiveJobRunner -Raw
$serviceProcessControlFlagsText = Get-Content -LiteralPath $serviceProcessControlFlags -Raw
$serviceProcessControlRunnerText = Get-Content -LiteralPath $serviceProcessControlRunner -Raw
$serviceProcessLaunchCleanupText = Get-Content -LiteralPath $serviceProcessLaunchCleanup -Raw
$controlFlagServiceText = $serviceProcessesText + $serviceProcessControlFlagsText + $serviceProcessControlRunnerText + $serviceProcessLaunchCleanupText + $serviceConstantsText
$serviceProcessKillText = Get-Content -LiteralPath $serviceProcessKill -Raw
$processKillServiceText = $serviceProcessesText + $serviceProcessKillText
$serviceProcessLaunchPlansText = Get-Content -LiteralPath $serviceProcessLaunchPlans -Raw
$serviceProcessLaunchRunnerText = Get-Content -LiteralPath $serviceProcessLaunchRunner -Raw
$processLaunchPlanServiceText = $serviceProcessesText + $serviceProcessLaunchPlansText + $serviceProcessLaunchRunnerText
$activeJobServiceText = $serviceProcessesText + $serviceProcessActiveJobsText + $serviceProcessActiveJobRunnerText + $serviceProcessLaunchPlansText + $serviceProcessLaunchRunnerText + $serviceConstantsText
$serviceProcessReadinessText = Get-Content -LiteralPath $serviceProcessReadiness -Raw
$processReadinessServiceText = $serviceProcessesText + $serviceProcessReadinessText + $serviceConstantsText
$serviceProcessRuntimeArtifactsText = Get-Content -LiteralPath $serviceProcessRuntimeArtifacts -Raw
$serviceProcessRuntimeRunnerText = Get-Content -LiteralPath $serviceProcessRuntimeRunner -Raw
$runtimeArtifactServiceText = $serviceProcessesText + $serviceProcessRuntimeArtifactsText + $serviceProcessRuntimeRunnerText + $serviceProcessLaunchCleanupText + $serviceConstantsText
$serviceProcessSpawnText = Get-Content -LiteralPath $serviceProcessSpawn -Raw
$serviceProcessSpawnRunnerText = Get-Content -LiteralPath $serviceProcessSpawnRunner -Raw
$processSpawnServiceText = $serviceProcessesText + $serviceProcessSpawnText + $serviceProcessSpawnRunnerText
$serviceQueueText = Get-Content -LiteralPath $serviceQueue -Raw
$serviceQueueDryRunText = Get-Content -LiteralPath $serviceQueueDryRun -Raw
$serviceQueueDryRunRunnerText = Get-Content -LiteralPath $serviceQueueDryRunRunner -Raw
$serviceQueuePreviewBuilderText = Get-Content -LiteralPath $serviceQueuePreviewBuilder -Raw
$serviceQueuePriorityText = Get-Content -LiteralPath $serviceQueuePriority -Raw
$serviceQueueSnapshotText = Get-Content -LiteralPath $serviceQueueSnapshot -Raw
$serviceReleaseText = Get-Content -LiteralPath $serviceRelease -Raw
$serviceReleasePlanText = Get-Content -LiteralPath $serviceReleasePlan -Raw
$serviceReleaseResultText = Get-Content -LiteralPath $serviceReleaseResult -Raw
$serviceRenameText = Get-Content -LiteralPath $serviceRename -Raw
$serviceRenameApplyText = Get-Content -LiteralPath $serviceRenameApply -Raw
$serviceRenameApplyRunnerText = Get-Content -LiteralPath $serviceRenameApplyRunner -Raw
$serviceRenameDiscoveryText = Get-Content -LiteralPath $serviceRenameDiscovery -Raw
$serviceRenamePlanPolicyText = Get-Content -LiteralPath $serviceRenamePlanPolicy -Raw
$serviceRenamePlannerText = Get-Content -LiteralPath $serviceRenamePlanner -Raw
$serviceRenamePreviewText = Get-Content -LiteralPath $serviceRenamePreview -Raw
$serviceRenamePreviewRunnerText = Get-Content -LiteralPath $serviceRenamePreviewRunner -Raw
$serviceRenameTvText = Get-Content -LiteralPath $serviceRenameTv -Raw
$serviceRenameTvFolderText = Get-Content -LiteralPath $serviceRenameTvFolder -Raw
$serviceStatusText = Get-Content -LiteralPath $serviceStatus -Raw
$serviceStatusActiveJobsText = Get-Content -LiteralPath $serviceStatusActiveJobs -Raw
$serviceStatusEventsText = Get-Content -LiteralPath $serviceStatusEvents -Raw
$serviceStatusFilesText = Get-Content -LiteralPath $serviceStatusFiles -Raw
$serviceStatusPresentationText = Get-Content -LiteralPath $serviceStatusPresentation -Raw
$serviceStatusProgressText = Get-Content -LiteralPath $serviceStatusProgress -Raw
$serviceStatusReadersText = Get-Content -LiteralPath $serviceStatusReaders -Raw
$serviceStatusSnapshotRunnerText = Get-Content -LiteralPath $serviceStatusSnapshotRunner -Raw
$serviceStatusSummaryText = Get-Content -LiteralPath $serviceStatusSummary -Raw
$serviceStatusSummarySectionsText = Get-Content -LiteralPath $serviceStatusSummarySections -Raw
$serviceTelemetryText = Get-Content -LiteralPath $serviceTelemetry -Raw
$serviceTelemetryHealthText = Get-Content -LiteralPath $serviceTelemetryHealth -Raw
$serviceTelemetryNvidiaText = Get-Content -LiteralPath $serviceTelemetryNvidia -Raw
$serviceTelemetrySystemText = Get-Content -LiteralPath $serviceTelemetrySystem -Raw
$subprocessRunnerText = Get-Content -LiteralPath $subprocessRunner -Raw
$settingsRiskPolicyText = Get-Content -LiteralPath $settingsRiskPolicy -Raw
$settingsRiskPolicyRulesText = Get-Content -LiteralPath $settingsRiskPolicyRules -Raw
$facadeCompletedText = Get-Content -LiteralPath $facadeCompleted -Raw
$facadeCompletedPolicyText = Get-Content -LiteralPath $facadeCompletedPolicy -Raw
$facadeCompletedOpenText = Get-Content -LiteralPath $facadeCompletedOpen -Raw
$facadeCompletedOpenPolicyText = Get-Content -LiteralPath $facadeCompletedOpenPolicy -Raw
$facadeMaintenanceText = Get-Content -LiteralPath $facadeMaintenance -Raw
$facadeMaintenanceBackfillText = Get-Content -LiteralPath $facadeMaintenanceBackfill -Raw
$facadeMaintenanceCommandsText = Get-Content -LiteralPath $facadeMaintenanceCommands -Raw
$facadeMaintenanceCommandPolicyText = Get-Content -LiteralPath $facadeMaintenanceCommandPolicy -Raw
$facadeMaintenancePolicyText = Get-Content -LiteralPath $facadeMaintenancePolicy -Raw
$facadeMaintenanceReleaseText = Get-Content -LiteralPath $facadeMaintenanceRelease -Raw
$facadeFailuresText = Get-Content -LiteralPath $facadeFailures -Raw
$facadeFailuresPolicyText = Get-Content -LiteralPath $facadeFailuresPolicy -Raw
$facadeAuditText = Get-Content -LiteralPath $facadeAudit -Raw
$facadeAuditPolicyText = Get-Content -LiteralPath $facadeAuditPolicy -Raw
$facadePendingPublishText = Get-Content -LiteralPath $facadePendingPublish -Raw
$facadePendingPublishPolicyText = Get-Content -LiteralPath $facadePendingPublishPolicy -Raw
$facadeQueueText = Get-Content -LiteralPath $facadeQueue -Raw
$facadeQueuePolicyText = Get-Content -LiteralPath $facadeQueuePolicy -Raw
$facadeScheduleText = Get-Content -LiteralPath $facadeSchedule -Raw
$facadeSchedulePolicyText = Get-Content -LiteralPath $facadeSchedulePolicy -Raw
$facadeSettingsText = Get-Content -LiteralPath $facadeSettings -Raw
$facadeSettingsPatchText = Get-Content -LiteralPath $facadeSettingsPatch -Raw
$facadeSettingsPatchCandidateText = Get-Content -LiteralPath $facadeSettingsPatchCandidate -Raw
$facadeSettingsPatchPolicyText = Get-Content -LiteralPath $facadeSettingsPatchPolicy -Raw
$facadeSettingsPolicyText = Get-Content -LiteralPath $facadeSettingsPolicy -Raw
$facadeProcessPipelineText = Get-Content -LiteralPath $facadeProcessPipeline -Raw
$facadeProcessPipelinePolicyText = Get-Content -LiteralPath $facadeProcessPipelinePolicy -Raw
$facadeProcessAuditText = Get-Content -LiteralPath $facadeProcessAudit -Raw
$facadeProcessAuditPolicyText = Get-Content -LiteralPath $facadeProcessAuditPolicy -Raw
$facadeProcessRerunText = Get-Content -LiteralPath $facadeProcessRerun -Raw
$facadeProcessRerunPolicyText = Get-Content -LiteralPath $facadeProcessRerunPolicy -Raw
$facadeProcessControlText = Get-Content -LiteralPath $facadeProcessControl -Raw
$facadeProcessControlPolicyText = Get-Content -LiteralPath $facadeProcessControlPolicy -Raw
$facadeProcessScheduleText = Get-Content -LiteralPath $facadeProcessSchedule -Raw
$facadeProcessSchedulePolicyText = Get-Content -LiteralPath $facadeProcessSchedulePolicy -Raw
$facadeProcessGuardText = Get-Content -LiteralPath $facadeProcessGuard -Raw
$facadeProcessGuardPolicyText = Get-Content -LiteralPath $facadeProcessGuardPolicy -Raw
$facadeDiagnosticsText = Get-Content -LiteralPath $facadeDiagnostics -Raw
$facadeDiagnosticsPolicyText = Get-Content -LiteralPath $facadeDiagnosticsPolicy -Raw
$facadeDiagnosticsOpenPolicyText = Get-Content -LiteralPath $facadeDiagnosticsOpenPolicy -Raw
$facadeStatusText = Get-Content -LiteralPath $facadeStatus -Raw
$facadeStatusPolicyText = Get-Content -LiteralPath $facadeStatusPolicy -Raw
$facadeRenameText = Get-Content -LiteralPath $facadeRename -Raw
$facadeRenamePolicyText = Get-Content -LiteralPath $facadeRenamePolicy -Raw
$appText = Get-Content -LiteralPath $app -Raw
$auditControllerText = Get-Content -LiteralPath $auditController -Raw
$auditTableControllerText = Get-Content -LiteralPath $auditTableController -Raw
$completedControllerText = Get-Content -LiteralPath $completedController -Raw
$diagnosticsControllerText = Get-Content -LiteralPath $diagnosticsController -Raw
$failureControllerText = Get-Content -LiteralPath $failureController -Raw
$failureTableControllerText = Get-Content -LiteralPath $failureTableController -Raw
$fileActionsControllerText = Get-Content -LiteralPath $fileActionsController -Raw
$folderPolicyControllerText = Get-Content -LiteralPath $folderPolicyController -Raw
$maintenanceControllerText = Get-Content -LiteralPath $maintenanceController -Raw
$pendingPublishControllerText = Get-Content -LiteralPath $pendingPublishController -Raw
$processLifecycleControllerText = Get-Content -LiteralPath $processLifecycleController -Raw
$queueControllerText = Get-Content -LiteralPath $queueController -Raw
$queueRefreshControllerText = Get-Content -LiteralPath $queueRefreshController -Raw
$releaseControllerText = Get-Content -LiteralPath $releaseController -Raw
$renameControllerText = Get-Content -LiteralPath $renameController -Raw
$rerunControllerText = Get-Content -LiteralPath $rerunController -Raw
$settingsControllerText = Get-Content -LiteralPath $settingsController -Raw
$settingsPersistenceControllerText = Get-Content -LiteralPath $settingsPersistenceController -Raw
$settingsProfileControllerText = Get-Content -LiteralPath $settingsProfileController -Raw
$statusServerControllerText = Get-Content -LiteralPath $statusServerController -Raw
$telemetryControllerText = Get-Content -LiteralPath $telemetryController -Raw
$workGuardControllerText = Get-Content -LiteralPath $workGuardController -Raw
$workerControllerText = Get-Content -LiteralPath $workerController -Raw
$modelsText = Get-Content -LiteralPath (Join-Path $projectRoot 'src\mediapipeline\desktop\models.py') -Raw
$modelsCoreText = Get-Content -LiteralPath (Join-Path $projectRoot 'src\mediapipeline\desktop\models_core.py') -Raw
$workersText = Get-Content -LiteralPath $workers -Raw
$priorityMarkersText = Get-Content -LiteralPath $priorityMarkers -Raw
$configSchemaText = Get-Content -LiteralPath $configSchema -Raw
$pipelineEventsContractText = Get-Content -LiteralPath $pipelineEventsContract -Raw
$progressContractText = Get-Content -LiteralPath $progressContract -Raw
$activeJobContractText = Get-Content -LiteralPath $activeJobContract -Raw
$controlFlagContractText = Get-Content -LiteralPath $controlFlagContract -Raw
$pendingPublishContractText = Get-Content -LiteralPath $pendingPublishContract -Raw
$appShellViewText = Get-Content -LiteralPath $appShellView -Raw
$homeViewText = Get-Content -LiteralPath $homeView -Raw
$liveViewText = Get-Content -LiteralPath $liveView -Raw
$queueViewText = Get-Content -LiteralPath $queueView -Raw
$libraryViewText = Get-Content -LiteralPath $libraryView -Raw
$diagnosticsViewText = Get-Content -LiteralPath $diagnosticsView -Raw
$diagnosticsDrawerViewText = Get-Content -LiteralPath $diagnosticsDrawerView -Raw
$maintenanceViewText = Get-Content -LiteralPath $maintenanceView -Raw
$renameViewText = Get-Content -LiteralPath $renameView -Raw
$rerunViewText = Get-Content -LiteralPath $rerunView -Raw
$scheduleViewText = Get-Content -LiteralPath $scheduleView -Raw
$settingsViewText = Get-Content -LiteralPath $settingsView -Raw
$viewsInitText = Get-Content -LiteralPath $viewsInit -Raw
$desktopViewsText = @($appShellViewText, $homeViewText, $liveViewText, $queueViewText, $libraryViewText, $diagnosticsViewText, $diagnosticsDrawerViewText, $maintenanceViewText, $rerunViewText, $scheduleViewText, $settingsViewText) -join [Environment]::NewLine
$toolIntegrationText = Get-Content -LiteralPath $toolIntegration -Raw
$endToEndSmokeText = Get-Content -LiteralPath $endToEndSmoke -Raw
$configJsonSchemaText = Get-Content -LiteralPath $configJsonSchema -Raw
$configJsonSchemaModel = $configJsonSchemaText | ConvertFrom-Json -ErrorAction Stop
$progressJsonSchemaText = Get-Content -LiteralPath $progressJsonSchema -Raw
$progressJsonSchemaModel = $progressJsonSchemaText | ConvertFrom-Json -ErrorAction Stop
$controlFlagJsonSchemaText = Get-Content -LiteralPath $controlFlagJsonSchema -Raw
$controlFlagJsonSchemaModel = $controlFlagJsonSchemaText | ConvertFrom-Json -ErrorAction Stop
$pendingManifestJsonSchemaText = Get-Content -LiteralPath $pendingManifestJsonSchema -Raw
$pendingManifestJsonSchemaModel = $pendingManifestJsonSchemaText | ConvertFrom-Json -ErrorAction Stop
$folderPolicyExampleText = Get-Content -LiteralPath $folderPolicyExample -Raw
$folderPolicyExampleModel = $folderPolicyExampleText | ConvertFrom-Json -ErrorAction Stop
$releaseBuilderText = Get-Content -LiteralPath $releaseBuilder -Raw
$environmentVerifierText = Get-Content -LiteralPath $environmentVerifier -Raw
$releaseVerifierText = Get-Content -LiteralPath $releaseVerifier -Raw
$deployabilityChecklistText = Get-Content -LiteralPath $deployabilityChecklist -Raw
$configTemplateText = Get-Content -LiteralPath $configTemplate -Raw
$configTemplateData = Import-PowerShellDataFile -LiteralPath $configTemplate
$subtitleFacadeText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\subtitles.ps1') -Raw
$subtitleCommonText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\common.ps1') -Raw
$subtitleSrtText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\srt.ps1') -Raw
$subtitleAssModuleText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\ass.ps1') -Raw
$subtitleTx3gText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\tx3g.ps1') -Raw
$subtitleBdpgsText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\bdpgs.ps1') -Raw
$subtitleBuildersText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\subtitles\builders.ps1') -Raw
$pendingManifestStoreText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\publish\pending_manifest_store.ps1') -Raw
$pendingTransactionsText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\publish\pending_transactions.ps1') -Raw
$pendingPublishIndexText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\publish\pending_publish_index.ps1') -Raw
$pendingPushText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\publish\pending_push.ps1') -Raw
$publishCompletionText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\publish\publish_completion.ps1') -Raw
$sidecarText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\publish\sidecar.ps1') -Raw
$pathHelpersText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\shared\path_helpers.ps1') -Raw
$diskText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\storage\disk.ps1') -Raw
$mediaProbeText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\probe\media_probe.ps1') -Raw
$folderPolicyText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\policy\folder_policy.ps1') -Raw
$audioText = @(
    Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\audio\audio.ps1') -Raw
    Get-ChildItem -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\audio\audio') -Filter '*.ps1' -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName |
        ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }
) -join [Environment]::NewLine
$nativeProcessContractsText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\shared\native_process_contracts.ps1') -Raw
$nativeText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\shared\native.ps1') -Raw
$ffmpegProgressText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\process\ffmpeg_progress.ps1') -Raw
$failureCodesText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\shared\failure_codes.ps1') -Raw
$failureStateText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\failures\failure_state.ps1') -Raw
$routingText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\decide\routing.ps1') -Raw
$encodePolicyText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\decide\encode_policy.ps1') -Raw
$mediaConstantsText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\shared\media_constants.ps1') -Raw
$pipelineEngineText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\queue\pipeline_engine.ps1') -Raw
$pipelineProcessingText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\process\pipeline_processing.ps1') -Raw
$outputPathPlanningText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\paths\output_path_planning.ps1') -Raw
$queuePlanText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\queue\queue_plan.ps1') -Raw
$configSchemaModuleText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\config\config_schema.ps1') -Raw
$stateStoreText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\storage\state_store.ps1') -Raw
$progressStateText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\status\progress_state.ps1') -Raw
$libraryIndexText = Get-Content -LiteralPath (Join-Path $projectRoot 'ops\pipeline\engine\library\library_index.ps1') -Raw
$regressionText = Get-Content -LiteralPath $PSCommandPath -Raw

Assert-True ($diskText -match 'function Copy-FileRobocopy' -and $diskText -match '\.mediapipeline-staging' -and $mainText -notmatch 'function Copy-FileRobocopy') "Copy-FileRobocopy must live in Modules\\Disk.ps1 and copy through a staging directory."
Assert-True ($pathHelpersText -match 'function Test-MediaPipelinePathIsEqualOrChild' -and $pathHelpersText -match 'function Get-MediaPipelineRelativePath' -and $diskText -match 'Test-MediaPipelinePathIsEqualOrChild -Path \$Destination -Root \$Outsource' -and $queuePlanText -match 'Get-MediaPipelineRelativePath' -and $folderPolicyText -match 'Test-MediaPipelinePathIsEqualOrChild') "Path containment, output reserve checks, queue relative paths, and folder-policy search must use boundary-aware path helpers instead of raw string prefixes."
Assert-True ($diskText -match 'LastCopyFileRobocopyResult' -and $diskText -match 'OUTPUT_DESTINATION_LOW_SPACE' -and $diskText -match 'OUTPUT_DESTINATION_SPACE_UNKNOWN' -and $publishCompletionText -match 'output-space-deferred') "Publish completion must distinguish output destination low-space/unknown-space parking from real publish failures."
Assert-True ($diskText -match 'function Clear-StalePartialFiles' -and $diskText -match 'function Test-MediaPipelineStalePartialArtifactName' -and $diskText -match '\.mp-partial\\\.' -and $diskText -match '\.mp-publish-\(partial\|backup\)' -and $diskText -match '\.mediapipeline-staging' -and $mainText -notmatch 'function Clear-StalePartialFiles') "Stale publish partial/staging cleanup must live in Modules\\Disk.ps1 and use exact generated artifact-name checks."
Assert-True ($mainText -notmatch 'Get-Random' -and $mainText -match "NewGuid\(\)\.ToString\('N'\)") "Scratch fingerprints and media temp outputs must use GUID-based names instead of collision-prone Get-Random names."
Assert-True ($pipelineText -notmatch '\@\(\\?\$srcDir,\s*\\?\$dstDir,\s*\\?\$srcFile\)') "Robocopy must not target the final destination directory directly."
Assert-True ($pipelineText -match 'RobocopyTimeoutSeconds' -and $diskText -match 'function Resolve-RobocopyPath' -and $diskText -match 'System32\\robocopy\.exe' -and $diskText -match 'Invoke-NativeCommand -FilePath \$robocopyPath -ArgumentList \$rcArgs -TimeoutSeconds \$script:RobocopyTimeoutSeconds') "Robocopy must resolve to System32 and run through a bounded timeout."
Assert-True ($nativeText -match '\[scriptblock\]\$PollHandler' -and $diskText -match 'Set-ProgressCopyTelemetry' -and $progressStateText -match 'function Set-ProgressCopyTelemetry' -and $progressStateText -match 'CopyBytesCopied' -and $progressStateText -match 'CopyPercent' -and $pendingTransactionsText -match "PushState 'copying'" -and $pendingPushText -match 'QueuePhase ''pending_push'' -QueueIndex \$visitedCount -QueueTotal \$manifests\.Count') "Robocopy publish/drain copies must emit backend-owned byte progress while preserving pending-publish transaction boundaries."
Assert-True ($nativeProcessContractsText -match 'function New-NativeCommandResult' -and $nativeProcessContractsText -match 'Stdout' -and $nativeProcessContractsText -match 'Stderr' -and $nativeProcessContractsText -match 'ErrorCode' -and $nativeText -match 'function Invoke-NativeProcess' -and $nativeText -match 'Receive-NativeProcessLine' -and $nativeText -notmatch 'function Get-ExternalToolFailureCode' -and $mainText -match 'NativeProcessContracts\.ps1') "Native process result shape, callback-capable runner, failure-code classification, and timeout policy must live in Modules\\NativeProcessContracts.ps1/Modules\\Native.ps1."
Assert-True ($ffmpegProgressText -match 'function Invoke-FFmpegWithProgress' -and $ffmpegProgressText -match 'function Get-FFmpegProgressPercentFromLine' -and $mainText -notmatch 'function Invoke-FFmpegWithProgress' -and $mainText -notmatch 'function Get-FFmpegProgressPercentFromLine' -and $mainText -match 'FfmpegProgress\.ps1') "FFmpeg progress parsing and progress-aware execution must live in Modules\\FfmpegProgress.ps1, not the main pipeline script."
Assert-True ($ffmpegProgressText -match 'function Add-FFmpegErrorTail' -and $ffmpegProgressText -match '262144' -and $ffmpegProgressText -notmatch 'StandardError\.ReadToEndAsync\(\)' -and $ffmpegProgressText -match 'Invoke-NativeProcess' -and $ffmpegProgressText -match '-StopFlagPath \$StopFlag') "FFmpeg progress runner must keep bounded stderr diagnostics and use the shared native process runner with literal stop-flag paths."
Assert-True ($pipelineText -match 'Write-PipelineEvent' -and $pipelineText -match 'pipeline_events\.jsonl' -and $pipelineText -match 'job_started' -and $pipelineText -match 'route_selected' -and $pipelineText -match 'tool_started' -and $pipelineText -match 'tool_completed' -and $pipelineText -match 'publish_parked' -and $pipelineText -match 'publish_drained' -and $pipelineText -match 'failure_recorded' -and $pipelineText -match 'job_completed') "Pipeline must emit structured JSONL events for jobs, route selection, tools, pending publish, failures, and completion."
Assert-True (($servicesText + $servicePathsText + $servicePathResolutionRunnerText + $serviceStatusText + $serviceStatusReadersText) -match 'def read_pipeline_events_tail' -and ($servicesText + $servicePathsText + $servicePathResolutionRunnerText + $serviceStatusText + $serviceStatusReadersText) -match 'pipeline_events\.jsonl' -and ($servicesText + $servicePathsText + $servicePathResolutionRunnerText + $serviceStatusText + $serviceStatusReadersText) -match '_tail_jsonl_file' -and ($servicesText + $servicePathsText + $servicePathResolutionRunnerText + $serviceStatusText + $serviceStatusReadersText) -match '_status_from_pipeline_events' -and ($servicesText + $servicePathsText + $servicePathResolutionRunnerText + $serviceStatusText + $serviceStatusReadersText) -match '_format_pipeline_event_summary' -and ($servicesText + $servicePathsText + $servicePathResolutionRunnerText + $serviceStatusText + $serviceStatusReadersText) -notmatch 'def _status_from_log') "Desktop service must expose a tolerant structured pipeline-event JSONL reader and feed Live/diagnostics from structured events without log-derived live status."
Assert-True ($servicePathsText -match 'app\.paths\.host' -and $servicePathsText -match 'resolve_powershell_host_for_service' -and $servicePathsText -match 'which_func=shutil\.which' -and $servicePathsText -match 'subprocess_kwargs_hidden' -and $servicePathHostRunnerText -match 'def resolve_powershell_host_for_service' -and $servicePathHostRunnerText -match 'PowerShell-7\.6\.0-win-x64' -and $servicePathHostRunnerText -match 'def subprocess_kwargs_hidden' -and $servicePathHostRunnerText -match 'CREATE_NO_WINDOW') "PowerShell host discovery and hidden-window subprocess kwargs must live in app/paths while preserving shutil.which compatibility injection."
Assert-True ($servicePathsText -match 'app\.paths\.defaults' -and $servicePathsText -match 'default_pipeline_path_for_roots' -and $servicePathsText -match 'default_config_path_for_roots' -and $servicePathsText -match 'default_audit_script_path_for_roots' -and $servicePathsText -match 'default_rerun_script_path_for_roots' -and $servicePathDefaultsText -match 'def default_pipeline_path_for_roots' -and $servicePathDefaultsText -match 'MediaPipeline_chatgpt\.ps1' -and $servicePathDefaultsText -match 'MediaPipeline_config_chatgpt\.psd1' -and $servicePathDefaultsText -match 'Audit-MediaLibrary_chatgpt\.ps1' -and $servicePathDefaultsText -match 'Invoke-RerunCsv\.ps1') "Desktop default pipeline/config/audit/rerun path candidate selection must live in app/paths behind PathResolutionService compatibility wrappers."
Assert-True ($servicePathsText -match 'app\.paths\.layout' -and $servicePathsText -match 'first_existing' -and $servicePathsText -match 'path_within_root' -and $servicePathLayoutText -match 'def first_existing' -and $servicePathLayoutText -match 'def state_root_for_local_base' -and $servicePathLayoutText -match 'def valid_extensions_from_config' -and $servicePathLayoutText -match 'def normalized_path_key' -and $servicePathLayoutText -match 'def path_within_root') "Desktop pure path selection, extension defaults, normalized path keys, and root-containment helpers must live in app/paths behind PathResolutionService compatibility wrappers."
Assert-True ($servicePathsText -match 'app\.storage\.state_migration' -and ($servicePathsText + $servicePathResolutionRunnerText) -match 'app_state_path_for_state_root' -and $servicePathsText -match 'migrate_app_state_path_for_service' -and $servicePathStateMigrationText -match 'def app_state_path_for_state_root' -and $servicePathStateMigrationText -match 'def migrate_app_state_path' -and $servicePathStateMigrationText -match 'shutil\.copy2' -and $servicePathStateMigrationText -match 'App state migration failed') "Desktop app-state migration from legacy app root into LocalBase\\State\\App must live in app/storage behind PathResolutionService compatibility wrappers."
Assert-True ($servicePathsText -match 'app\.paths\.resolution_runner' -and $servicePathsText -match 'resolve_paths_for_service' -and $servicePathResolutionRunnerText -match 'def resolve_paths_for_service' -and $servicePathResolutionRunnerText -match 'load_config_data' -and $servicePathResolutionRunnerText -match 'active_jobs_path = resolved\.state_root / "ActiveJobs"' -and $servicePathResolutionRunnerText -match 'queue_snapshot_path = service\._first_existing' -and $servicePathResolutionRunnerText -match 'completed_manifest_path = service\._first_existing' -and $servicePathResolutionRunnerText -match 'KEY_PRIORITY_MARKERS|PriorityMarkers') "Desktop path-resolution orchestration and versioned LocalBase state path assembly must live in a focused runner behind PathResolutionService compatibility wrappers."
Assert-True ($pipelineEventsContractText -match 'class PipelineEvent' -and $pipelineEventsContractText -match 'PIPELINE_EVENT_SCHEMA_VERSION = "pipeline_event\.v1"' -and $pipelineEventsContractText -match 'def to_mapping' -and ($serviceStatusText + $serviceStatusReadersText) -match 'PipelineEvent\.from_mapping' -and ($serviceStatusText + $serviceStatusReadersText) -match 'Skipped .* invalid pipeline event' -and $progressContractText -match 'class ProgressState' -and $progressContractText -match 'ProgressVersion' -and $progressContractText -match 'CurrentStagePercent' -and ($serviceStatusText + $serviceStatusReadersText) -match 'ProgressState\.from_mapping' -and ($serviceStatusText + $serviceStatusReadersText) -match 'Progress contract invalid' -and @($progressJsonSchemaModel.required) -contains 'ProgressVersion') "Desktop status service must validate pipeline_events.jsonl and pipeline_progress.json through explicit Python contracts while preserving controller-facing dicts."
Assert-True ($pipelineText -match 'function Write-JsonLineAppend' -and $pipelineText -match "schema_version\s+=\s+'pipeline_event.v1'" -and $pipelineText -match "schema_version\s+=\s+'pipeline_sidecar.v1'" -and $pipelineText -match 'completed_job\.v1' -and $pipelineText -match 'CurrentJobId = Get-SourceIdentityKeyV2') "Append-only history records must include schema, job, and correlation identifiers."
Assert-True ($regressionText -match "Write-PipelineEvent -EventType 'job_started'" -and $regressionText -match "Write-PipelineEvent -EventType 'tool_completed'" -and $regressionText -match 'source_path was not written' -and $regressionText -match 'hashtable data did not round-trip' -and $regressionText -match 'pipeline_event.v1') "Regression checks must make job lifecycle events structured and testable."
Assert-True ($appText -match 'UiBackgroundWorker' -and $workersText -match 'class UiBackgroundWorker' -and $appText -notmatch 'threading\.Thread' -and $appText -notmatch 'root\.after\(0') "Desktop app blocking refresh/load work must use the UI background worker queue instead of direct ad-hoc worker-to-UI callbacks."
Assert-True (($servicesText + $processLaunchPlanServiceText) -match 'def start_pipeline' -and ($servicesText + $processLaunchPlanServiceText) -match 'def start_audit' -and ($servicesText + $processLaunchPlanServiceText) -match 'def start_rerun_csv' -and $processLaunchPlanServiceText -match 'elif mode == "drain_pending_pushes"' -and ($servicesText + $serviceTelemetryText) -match 'def check_environment_health' -and ($appText + $processLifecycleControllerText) -match '(self|app)\.service\.start_pipeline' -and ($appText + $processLifecycleControllerText) -match '(self|app)\.service\.start_audit' -and ($appText + $rerunControllerText) -match 'self\.service\.start_rerun_csv|app\.service\.start_rerun_csv' -and ($appText + $maintenanceControllerText) -match 'self\.service\.check_environment_health|app\.service\.check_environment_health') "Desktop views must launch pipeline, audit, CSV rerun, pending-drain, and diagnostics work through the backend service API."
Assert-True ($serviceProcessesText -match 'app\.processes\.launch_runner' -and $serviceProcessesText -match 'start_pipeline_for_service' -and $serviceProcessesText -match 'start_audit_for_service' -and $serviceProcessesText -match 'start_rerun_csv_for_service' -and $serviceProcessLaunchRunnerText -match 'def start_pipeline_for_service' -and $serviceProcessLaunchRunnerText -match 'def start_audit_for_service' -and $serviceProcessLaunchRunnerText -match 'def start_rerun_csv_for_service' -and $serviceProcessLaunchRunnerText -match 'build_pipeline_launch_plan' -and $serviceProcessLaunchRunnerText -match 'service\._spawn') "Desktop process launch start-method orchestration must live in a focused runner behind ProcessLifecycleService compatibility wrappers."
Assert-True (($servicesText + $serviceReleaseText) -match 'def build_release_package' -and ($servicesText + $serviceReleaseText + $serviceReleasePlanText) -match 'scripts.*release.*build\.ps1' -and ($servicesText + $servicePendingPublishText) -match 'def scan_pending_publish' -and ($appText + $appShellViewText) -match 'MaintenanceView' -and ($appText + $releaseControllerText) -match 'self\.service\.build_release_package|app\.service\.build_release_package' -and ($appText + $pendingPublishControllerText) -match 'self\.service\.scan_pending_publish|app\.service\.scan_pending_publish' -and $maintenanceViewText -match 'Release Package' -and $maintenanceViewText -match 'Pending Publish') "Desktop maintenance tools must expose release packaging and pending publish inventory through service-owned backends."
Assert-True ($serviceReleaseText -match 'release_plan' -and $serviceReleaseText -match 'build_release_command_args' -and $serviceReleasePlanText -match 'def build_release_command_args' -and $serviceReleasePlanText -match 'def release_artifact_paths' -and $serviceReleasePlanText -match 'KeepPersonalConfig') "Release package argument planning and artifact-path policy must live in a focused helper while the service keeps subprocess execution and manifest reads."
Assert-True ($serviceReleaseText -match 'release_result' -and $serviceReleaseText -match 'release_result_payload' -and $serviceReleaseResultText -match 'def release_capture_fields' -and $serviceReleaseResultText -match 'def release_result_payload' -and $serviceReleaseResultText -match 'kill_message' -and $serviceReleaseResultText -match 'manifest_exists') "Release package subprocess result normalization and operator payload shaping must live in a focused helper while the service keeps manifest file IO."
Assert-True ($viewsInitText -match 'DiagnosticsView' -and ($appText + $appShellViewText) -match 'diagnostics_view = DiagnosticsView' -and ($appText + $appShellViewText) -match '"diagnostics": .*diagnostics_view' -and $diagnosticsViewText -match 'Recent Errors' -and $diagnosticsViewText -match 'Pipeline Events' -and $serviceStatusText -match 'format_diagnostics_error_summary' -and $serviceStatusText -match 'format_diagnostics_event_summary') "Desktop diagnostics must be available as a first-class left navigation view with recent errors, events, logs, and pipeline state fed from snapshot data."
Assert-True ($completedServiceText -match '_diagnostics_output_exists' -and $completedServiceText -match 'completed metadata without media' -and $modelsText -match 'def output_health' -and ($appText + $completedControllerText) -match 'missing final media' -and $libraryViewText -match 'missing_output') "Completed-job diagnostics must flag metadata rows whose final media is missing."
Assert-True ($serviceCompletedText -match 'app\.completed\.manifest' -and $serviceCompletedText -match 'read_completed_manifest_records' -and $serviceCompletedManifestText -match 'def read_completed_manifest_records' -and $serviceCompletedManifestText -match 'def annotate_completed_output_health' -and $serviceCompletedManifestText -match 'lstrip\("\\ufeff"\)') "Completed manifest JSONL parsing and output-health annotation must live in a focused helper while the service keeps cache and backfill subprocess ownership."
Assert-True ($facadeCompletedText -match 'app\.completed\.policy' -and $facadeCompletedText -match 'completed_preview_from_records' -and $facadeCompletedText -match 'completed_record_key' -and $facadeCompletedPolicyText -match 'def completed_record_to_row' -and $facadeCompletedPolicyText -match 'def completed_preview_fields' -and $facadeCompletedPolicyText -match 'def completed_preview_from_records' -and $facadeCompletedPolicyText -match 'def completed_history_read_error_result' -and $facadeCompletedPolicyText -match 'def format_bytes_compact') "Completed preview row-key, row-shaping, count, byte-formatting, DTO warning policy, and read-error result policy must live in a focused helper while manifest loading stays facade/service-owned."
Assert-True ($facadeCompletedOpenText -match 'app\.completed\.open_policy' -and $facadeCompletedOpenText -match 'find_completed_record_by_key' -and $facadeCompletedOpenText -match 'completed_open_success_result' -and $facadeCompletedOpenPolicyText -match 'COMPLETED_OPEN_TARGETS' -and $facadeCompletedOpenPolicyText -match 'def completed_open_path' -and $facadeCompletedOpenPolicyText -match 'def find_completed_record_by_key' -and $facadeCompletedOpenPolicyText -match 'def completed_open_success_result') "Completed-job open command target allowlisting, row lookup, manifest-owned path selection, and command-result policy must live in a focused policy helper behind the application facade."
Assert-True ($facadeMaintenanceText -match 'app\.maintenance\.policy' -and $facadeMaintenanceText -match 'maintenance_health_rows' -and $facadeMaintenanceText -match 'maintenance_workspace_counts' -and $facadeMaintenancePolicyText -match 'def maintenance_health_row' -and $facadeMaintenancePolicyText -match 'def maintenance_health_rows' -and $facadeMaintenancePolicyText -match 'def maintenance_workspace_counts') "Maintenance workspace health-row shaping and count policy must live in a focused helper while environment-health service execution stays facade/service-owned."
Assert-True ($facadeMaintenanceReleaseText -match 'app\.maintenance\.command_policy' -and $facadeMaintenanceReleaseText -match 'release_dry_run_builder_kwargs' -and $facadeMaintenanceReleaseText -match 'release_dry_run_result' -and $facadeMaintenanceBackfillText -match 'completed_backfill_dry_run_result' -and $facadeMaintenanceCommandsText -match 'release_stdout_value' -and $facadeMaintenanceCommandPolicyText -match 'def release_dry_run_builder_kwargs' -and $facadeMaintenanceCommandPolicyText -match 'def release_dry_run_result' -and $facadeMaintenanceCommandPolicyText -match 'def completed_backfill_dry_run_result') "Maintenance ops/release/metadata/backfill dry-run request, stdout parsing, and command-result policy must live in focused helpers while service/subprocess execution stays backend-owned."
Assert-True ($facadeFailuresText -match 'app\.failures\.policy' -and $facadeFailuresText -match 'failure_preview_from_records' -and $facadeFailuresText -match 'normalize_failure_source_kind' -and $facadeFailuresPolicyText -match 'def failure_record_to_row' -and $facadeFailuresPolicyText -match 'def failure_preview_fields' -and $facadeFailuresPolicyText -match 'def failure_preview_from_records' -and $facadeFailuresPolicyText -match 'def failure_json_read_error_result' -and $facadeFailuresPolicyText -match 'def bounded_failure_limit') "Failure preview source-kind normalization, row-shaping, count, DTO warning policy, and read-error result policy must live in a focused helper while report and marker loading stays facade/service-owned."
Assert-True ($facadeAuditText -match 'app\.audit\.preview_policy' -and $facadeAuditText -match 'audit_preview_from_records' -and $facadeAuditText -match 'bounded_audit_limit' -and $facadeAuditPolicyText -match 'def audit_record_to_row' -and $facadeAuditPolicyText -match 'def audit_preview_fields' -and $facadeAuditPolicyText -match 'def audit_preview_from_records' -and $facadeAuditPolicyText -match 'def audit_csv_read_error_result' -and $facadeAuditPolicyText -match 'def audit_duplicate_group_count') "Audit preview row-shaping, bucket/priority counts, duplicate-group counts, DTO warning policy, and read-error result policy must live in a focused helper while CSV discovery and loading stays facade/service-owned."
Assert-True ($facadePendingPublishText -match 'pending_policy' -and $facadePendingPublishText -match 'pending_publish_preview_result' -and $facadePendingPublishPolicyText -match 'def pending_publish_preview_fields' -and $facadePendingPublishPolicyText -match 'def pending_publish_preview_result' -and $facadePendingPublishPolicyText -match 'def pending_publish_invalid_result' -and $facadePendingPublishPolicyText -match 'def pending_publish_rows' -and $facadePendingPublishPolicyText -match 'def pending_publish_scan_exception_result') "Pending-publish facade raw scan-result normalization, row filtering, invalid-result, and scan-exception DTO policy must live in a focused helper while pending folder scanning stays service-owned."
Assert-True ($facadeQueueText -match '\.policy' -and $facadeQueueText -match 'queue_preview_rows' -and $facadeQueueText -match 'queue_preview_warnings' -and $facadeQueuePolicyText -match 'def queue_record_to_row' -and $facadeQueuePolicyText -match 'def queue_preview_rows' -and $facadeQueuePolicyText -match 'EMPTY_QUEUE_SNAPSHOT_WARNING') "Queue preview row-shaping, invalid-row shaping, and empty-snapshot warning policy must live in a focused helper while snapshot reads stay facade/service-owned."
Assert-True ($facadeScheduleText -match '\.policy' -and $facadeScheduleText -match 'schedule_day_summaries' -and $facadeScheduleText -match 'schedule_grid_rows' -and $facadeSchedulePolicyText -match 'def schedule_block_label' -and $facadeSchedulePolicyText -match 'def schedule_day_windows' -and $facadeSchedulePolicyText -match 'def schedule_day_summaries') "Schedule workspace grid shaping, day-window grouping, and day-summary policy must live in a focused helper while app-state reads and schedule evaluation stay facade/service-owned."
Assert-True ($facadeSettingsText -match 'app\.config\.settings_policy' -and $facadeSettingsText -match 'settings_workspace_paths' -and $facadeSettingsText -match 'settings_validation_result' -and $facadeSettingsPolicyText -match 'def settings_workspace_paths' -and $facadeSettingsPolicyText -match 'def settings_validation_result' -and $facadeSettingsPolicyText -match 'SETTINGS_VALIDATE_COMMAND') "Settings workspace path shaping and validation command-result policy must live in a focused helper while config validation and profile loading stay facade/service-owned."
Assert-True ($facadeSettingsPatchText -match 'app\.config\.settings_patch_policy' -and $facadeSettingsPatchText -match 'settings_patch_preview_result' -and $facadeSettingsPatchText -match 'settings_save_success_result' -and $facadeSettingsPatchCandidateText -match 'settings_patch_changes_from_request' -and $facadeSettingsPatchCandidateText -match 'settings_patch_remove_keys_from_request' -and $facadeSettingsPatchPolicyText -match 'def settings_patch_preview_result' -and $facadeSettingsPatchPolicyText -match 'def settings_save_success_result' -and $facadeSettingsPatchPolicyText -match 'def settings_patch_changes_from_request' -and $facadeSettingsPatchPolicyText -match 'SETTINGS_DIFF_LINE_LIMIT') "Settings patch request-shape validation, preview/save command-result, and truncation policy must live in a focused helper while candidate merging and PSD1 persistence stay facade/service-owned."
Assert-True ($facadeProcessPipelineText -match 'app\.processes\.pipeline_policy' -and $facadeProcessPipelineText -match 'pipeline_start_success_result' -and $facadeProcessPipelinePolicyText -match 'PIPELINE_START_MODES' -and $facadeProcessPipelinePolicyText -match 'def parse_pipeline_sleep_seconds' -and $facadeProcessPipelinePolicyText -match 'def pipeline_start_exception_result' -and $facadeProcessPipelinePolicyText -match 'drain_pending_pushes') "Pipeline launch mode, sleep, extra-args, and command-result policy must live in a focused helper behind the application facade."
Assert-True ($facadeProcessAuditText -match 'app\.processes\.audit_policy' -and $facadeProcessAuditText -match 'audit_start_success_result' -and $facadeProcessAuditPolicyText -match 'def resolve_audit_library_root' -and $facadeProcessAuditPolicyText -match 'def audit_start_exception_result' -and $facadeProcessAuditPolicyText -match 'AUDIT_LIBRARY_ROOT_ERROR') "Audit launch library-root resolution and command-result policy must live in a focused helper behind the application facade."
Assert-True ($facadeProcessRerunText -match 'app\.processes\.rerun_policy' -and $facadeProcessRerunText -match 'rerun_start_success_result' -and $facadeProcessRerunPolicyText -match 'def rerun_csv_path_from_request' -and $facadeProcessRerunPolicyText -match 'def rerun_modes_are_supported' -and $facadeProcessRerunPolicyText -match 'def rerun_start_exception_result' -and $facadeProcessRerunPolicyText -match 'CSV_RERUN_MODE_ERROR') "CSV rerun launch path, copy/keep/park mode gate, and command-result policy must live in a focused helper behind the application facade."
Assert-True ($facadeProcessControlText -match 'app\.processes\.control_policy' -and $facadeProcessControlText -match 'pipeline_control_success_data' -and $facadeProcessControlPolicyText -match 'PIPELINE_CONTROL_ACTIONS' -and $facadeProcessControlPolicyText -match 'def normalize_pipeline_control_action' -and $facadeProcessControlPolicyText -match 'def pipeline_control_command') "Pipeline pause/stop/rescan control action allowlisting and result payload policy must live in app/processes behind the application facade."
Assert-True ($facadeProcessScheduleText -match 'app\.processes\.schedule_policy|\.schedule_policy' -and $facadeProcessScheduleText -match 'resolve_pipeline_start_schedule_gate' -and $facadeProcessSchedulePolicyText -match 'SCHEDULE_UNWATCHED_MODES' -and $facadeProcessSchedulePolicyText -match 'def normalize_schedule_override' -and $facadeProcessSchedulePolicyText -match 'SCHEDULE_CONTINUOUS_BLOCK_MESSAGE') "Pipeline start schedule gate calculation must live in app/processes while workspace loading stays facade-owned."
Assert-True ($facadeProcessGuardText -match 'app\.processes\.guard_policy' -and $facadeProcessGuardText -match 'close_readiness_fields' -and $facadeProcessGuardPolicyText -match 'ACTIVE_CLOSE_STATES' -and $facadeProcessGuardPolicyText -match 'def pipeline_progress_indicates_active_work' -and $facadeProcessGuardPolicyText -match 'def audit_progress_indicates_active_work') "Process close-readiness and progress-active interpretation policy must live in a focused helper while service-owned process/progress reads stay facade-owned."
Assert-True ($facadeDiagnosticsText -match 'app\.diagnostics\.policy' -and $facadeDiagnosticsText -match 'diagnostics_active_job_rows' -and $facadeDiagnosticsText -match 'diagnostics_launch_log_summary' -and $facadeDiagnosticsPolicyText -match 'def diagnostics_active_job_rows' -and $facadeDiagnosticsPolicyText -match 'def diagnostics_summary_lines' -and $facadeDiagnosticsPolicyText -match 'def diagnostics_warnings') "Diagnostics read-side active-job, summary-line, launch-log, and warning policy must live in a focused helper while snapshot construction stays facade/service-owned."
Assert-True ($facadeDiagnosticsText -match 'app\.diagnostics\.open_policy' -and $facadeDiagnosticsText -match 'diagnostics_open_path' -and $facadeDiagnosticsText -match 'diagnostics_open_success_result' -and $facadeDiagnosticsOpenPolicyText -match 'DIAGNOSTICS_OPEN_TARGETS' -and $facadeDiagnosticsOpenPolicyText -match 'def normalize_diagnostics_open_target' -and $facadeDiagnosticsOpenPolicyText -match 'def diagnostics_open_path' -and $facadeDiagnosticsOpenPolicyText -match 'def diagnostics_open_success_result') "Diagnostics open target allowlisting, path selection, and command-result policy must live in a focused helper behind the application facade while OS opening stays service-owned."
Assert-True ($facadeStatusText -match 'app\.observability\.status_policy' -and $facadeStatusText -match 'application_capabilities' -and $facadeStatusText -match 'telemetry_fields' -and $facadeStatusPolicyText -match 'APP_CAPABILITIES' -and $facadeStatusPolicyText -match 'def snapshot_counts' -and $facadeStatusPolicyText -match 'def telemetry_gpu_present') "Status health capabilities, snapshot count/path shaping, and telemetry field policy must live in a focused helper while service reads stay facade-owned."
Assert-True ($facadeRenameText -match 'app\.rename\.policy' -and $facadeRenameText -match 'rename_plan_kwargs_from_request' -and $facadeRenameText -match 'select_rename_plan_rows' -and $facadeRenameText -match 'rename_apply_success_result' -and $facadeRenamePolicyText -match 'def rename_preview_counts' -and $facadeRenamePolicyText -match 'def selected_rename_sources' -and $facadeRenamePolicyText -match 'def rename_apply_blockers_result' -and $facadeRenamePolicyText -match 'def rename_apply_success_result') "Rename preview counts, request parsing, selected-row matching, blocker message policy, and apply command-result policy must live in a focused helper while the facade keeps service planning and mutation ownership."
Assert-True ($serviceCompletedText -match 'app\.completed\.backfill' -and $serviceCompletedText -match 'build_completed_backfill_args' -and $serviceCompletedBackfillText -match 'def validate_completed_backfill_request' -and $serviceCompletedBackfillText -match 'def build_completed_backfill_args' -and $serviceCompletedBackfillText -match 'def completed_backfill_result_message' -and $serviceCompletedText -match 'run_capture') "Completed manifest backfill validation, argument shaping, and result policy must live in a focused helper while the service keeps subprocess execution and cache invalidation."
Assert-True ($regressionText -match 'release service dry-run should succeed' -and $regressionText -match 'pending publish scanner should expose parked manifest rows') "Reliability regression checks must exercise release package dry-run and PendingServerPush manifest inventory behavior."
Assert-True (
    $mainText -match 'DRAIN PENDING PUSHES: skipping startup stale-partial cleanup scans' -and
    $mainText -match 'publish-only mode skips SourceMovies/SourceTV/Outsource startup reachability probes' -and
    $mainText -match 'DRAIN PENDING PUSHES: skipping subtitle helper self-check' -and
    $mainText -match "Status 'Publishing parked outputs'" -and
    $mainText -match 'same single-instance lock' -and
    ($appText + $pendingPublishControllerText) -match 'Pending publish: reading manifests' -and
    $appText -notmatch 'Pending publish: scanning'
) "Drain-pending publish mode must avoid source-oriented startup scans/probes and the desktop Pending Publish dashboard must not label manifest inventory as scanning."
Assert-True ($desktopViewsText -notmatch '\bsubprocess\b|\bPopen\b|Start-Process|-File\s+|MediaPipeline_chatgpt\.ps1|Audit-MediaLibrary_chatgpt\.ps1|Invoke-RerunCsv\.ps1') "Desktop presentation views must stay free of direct process launching and pipeline script orchestration."
Assert-True (($servicesText + $serviceQueueText + $serviceQueueDryRunText + $serviceQueueDryRunRunnerText) -match '-EmitQueuePlan' -and ($servicesText + $serviceAuditRerunText + $serviceAuditRerunMetadataText) -match 'Get-RerunSourceMetadata\.ps1' -and $servicesText -notmatch 'Resolve-InitialMediaRoutePlan|Resolve-RemuxCodecRoutePlan|Do-Encode|Do-Remux|Process-File|Convert-Tx3gToSrt|Convert-BdpgsToSrt') "Desktop service must consume pipeline-authored queue/source metadata instead of reimplementing processing decisions."
Assert-True ($appText -notmatch 'Resolve-InitialMediaRoutePlan|Resolve-RemuxCodecRoutePlan|Do-Encode|Do-Remux|Process-File|Convert-Tx3gToSrt|Convert-BdpgsToSrt' -and ($servicesText + $serviceProcessesText + $serviceProcessSpawnRunnerText) -match 'subprocess\.Popen' -and ($servicesText + $serviceAuditRerunText) -match 'def save_rerun_records_csv' -and $appText -match '_load_thumbnail') "Python desktop code must stay focused on UI, CSV/table handling, presentation state, and process supervision."
Assert-True ($processKillServiceText -match 'def find_related_pipeline_processes' -and $processKillServiceText -match 'def kill_related_pipeline_processes' -and $processKillServiceText -match 'Unable to verify .* process.* exited' -and $processKillServiceText -match 'taskkill' -and ($appText + $processLifecycleControllerText) -match 'def _schedule_force_exit|def schedule_force_exit' -and ($appText + $processLifecycleControllerText) -match 'os\._exit\(0\)' -and ($appText + $processLifecycleControllerText) -match '_destroy_app\(force_exit=True\)|destroy_app\(force_exit=True\)') "Kill + Quit must verify process-tree termination, sweep related bundle processes after lost handles, clear runtime state, and force-exit the desktop app."
Assert-True ($processReadinessServiceText -match 'def _verify_spawn_readiness' -and $processReadinessServiceText -match 'PROCESS_LAUNCH_READY_CHECK_SECONDS' -and $processReadinessServiceText -match 'exited immediately with code' -and $processReadinessServiceText -match 'stderr tail' -and $activeJobServiceText -match 'ACTIVE_JOB_SCHEMA_VERSION' -and $serviceProcessesText -match 'def _write_active_job_launch_record' -and ($servicesText + $servicePathsText + $servicePathResolutionRunnerText) -match 'active_jobs_path = resolved\.state_root / "ActiveJobs"' -and $activeJobServiceText -match 'job_kind="pipeline"' -and $activeJobServiceText -match 'job_kind="audit"' -and $activeJobServiceText -match 'job_kind="rerun_csv"' -and ($modelsText + $modelsCoreText) -match 'active_jobs_path') "Desktop process launches must detect immediate nonzero exits, report run-log tails, and persist ActiveJobs launch records for pipeline, audit, and CSV rerun modes."
Assert-True ($activeJobContractText -match 'class ActiveJobRecord' -and $activeJobContractText -match 'ACTIVE_JOB_SCHEMA_VERSION = "desktop_active_job\.v1"' -and $activeJobContractText -match 'ACTIVE_JOB_STATUSES' -and $activeJobContractText -match 'orphaned' -and $activeJobContractText -match 'def to_mapping' -and $activeJobServiceText -match 'ActiveJobRecord\.from_mapping' -and $serviceProcessesText -match 'def reconcile_active_job_records' -and $activeJobServiceText -match 'Marked ActiveJobs record .* orphaned' -and ($serviceStatusText + $serviceStatusActiveJobsText) -match 'ActiveJobRecord\.from_mapping' -and ($serviceStatusText + $serviceStatusActiveJobsText) -match 'invalid active job contract' -and ($serviceStatusText + $serviceStatusSnapshotRunnerText) -match 'reconcile_active_job_records') "ActiveJobs launch/crash-recovery records must be validated by an explicit desktop contract at write/read boundaries and reconciled when tracked PIDs are definitely gone."
Assert-True ($serviceProcessesText -match 'app\.processes\.active_job_runner' -and $serviceProcessesText -match 'write_active_job_launch_record_for_service' -and $serviceProcessesText -match 'reconcile_active_job_records_for_service' -and $serviceProcessesText -match 'update_active_job_record_for_service' -and $serviceProcessActiveJobRunnerText -match 'def write_active_job_launch_record_for_service' -and $serviceProcessActiveJobRunnerText -match 'stdout_log=service\._last_spawn_stdout_log' -and $serviceProcessActiveJobRunnerText -match 'def reconcile_active_job_records_for_service' -and $serviceProcessActiveJobRunnerText -match 'psutil_module=psutil_module' -and $serviceProcessActiveJobRunnerText -match 'def update_active_job_record_for_service') "Desktop ActiveJobs service glue must live in a focused app/processes runner behind ProcessLifecycleService compatibility wrappers."
Assert-True ($serviceStatusText -match 'app\.status\.active_jobs' -and $serviceStatusText -match 'def _format_active_job_summary' -and $serviceStatusActiveJobsText -match 'def format_active_job_summary' -and $serviceStatusActiveJobsText -match 'ActiveJobRecord\.from_mapping' -and $serviceStatusActiveJobsText -match 'invalid active job contract') "Status diagnostics ActiveJobs formatting must live in a focused helper behind the StatusService compatibility wrapper."
Assert-True ($serviceStatusText -match 'app\.status\.snapshot_runner' -and $serviceStatusText -match 'build_snapshot_for_service' -and $serviceStatusSnapshotRunnerText -match 'def build_snapshot_for_service' -and $serviceStatusSnapshotRunnerText -match 'reconcile_active_job_records' -and $serviceStatusSnapshotRunnerText -match 'Stale progress from previous run' -and $serviceStatusSnapshotRunnerText -match 'Snapshot\(') "Status snapshot reconciliation, reader orchestration, stale-progress current-activity handling, and Snapshot construction must live in a focused runner behind the StatusService compatibility wrapper."
Assert-True ($serviceStatusText -match 'app\.observability\.status_files' -and $serviceStatusText -match 'latest_matching_report_file' -and $serviceStatusFilesText -match 'def latest_matching_file' -and $serviceStatusFilesText -match 'def latest_audit_csv' -and $serviceStatusFilesText -match 'def latest_failure_json') "Status diagnostics latest report/audit/failure file selection must live in app/observability behind StatusService compatibility wrappers."
Assert-True ($serviceStatusText -match 'app\.status\.readers' -and $serviceStatusText -match 'def read_progress' -and $serviceStatusText -match 'read_pipeline_events_tail_file' -and $serviceStatusReadersText -match 'def read_progress_file' -and $serviceStatusReadersText -match 'def read_audit_progress_file' -and $serviceStatusReadersText -match 'def read_log_tail_file' -and $serviceStatusReadersText -match 'def read_pipeline_events_tail_file') "Status diagnostics progress/audit/log/event file readers must live in a focused helper behind StatusService compatibility wrappers."
Assert-True ($serviceStatusText -match 'app\.status\.summary' -and $serviceStatusText -match 'def _build_status_summary' -and $serviceStatusText -match 'build_status_summary_text' -and $serviceStatusSummaryText -match 'def build_status_summary' -and $serviceStatusSummaryText -match 'app\.status\.summary_sections' -and ($serviceStatusSummaryText + $serviceStatusSummarySectionsText) -match 'Latest priority audit CSV' -and $serviceStatusSummarySectionsText -match 'Progress health  : STALE') "Status diagnostics summary text assembly must live in a focused helper behind the StatusService compatibility wrapper."
Assert-True ($serviceStatusSummarySectionsText -match 'def append_environment_section' -and $serviceStatusSummarySectionsText -match 'def append_progress_section' -and $serviceStatusSummarySectionsText -match 'def append_audit_progress_section' -and $serviceStatusSummarySectionsText -match 'def append_latest_path_section') "Status diagnostics summary section formatting must live in focused section helpers while the summary entry point preserves text ordering."
Assert-True ($serviceStatusText -match 'build_current_activity_text' -and $serviceStatusText -match 'def _build_current_activity' -and $serviceStatusPresentationText -match 'def build_current_activity' -and $serviceStatusPresentationText -match 'No active work reported' -and $serviceStatusPresentationText -match 'structured_status_from_progress') "Status current-activity composition must live in the presentation helper behind the StatusService compatibility wrapper."
Assert-True ($serviceStatusPresentationText -match 'app\.status\.events' -and $serviceStatusEventsText -match 'def format_pipeline_event_summary' -and $serviceStatusEventsText -match 'def structured_status_from_pipeline_event' -and $serviceStatusEventsText -match 'def pipeline_event_stage_label' -and $serviceStatusEventsText -match 'priority_requested') "Pipeline-event status labels and diagnostic summary rows must live in a focused status-events helper behind the status presentation compatibility exports."
Assert-True ($serviceAuditRerunText -match 'app\.audit\.rerun_records' -and $serviceAuditRerunText -match 'def correlate_audit_record' -and $serviceAuditRerunText -match 'correlate_audit_record_helper' -and $serviceAuditRerunRecordsText -match 'def audit_correlation_lookup_key' -and $serviceAuditRerunRecordsText -match 'def correlate_audit_record' -and $serviceAuditRerunRecordsText -match 'def rerun_media_kind_from_audit') "Audit rerun correlation and media-kind policy must live in a focused helper behind AuditRerunService compatibility wrappers."
Assert-True ($serviceAuditRerunExportText -match 'app\.audit\.rerun_csv' -and $serviceAuditRerunExportText -match 'build_rerun_csv_row' -and $serviceAuditRerunExportText -match 'source_stat_to_rerun_values' -and $serviceAuditRerunCsvText -match 'def build_rerun_csv_row' -and $serviceAuditRerunCsvText -match 'def apply_rerun_source_metadata' -and $serviceAuditRerunCsvText -match 'def source_stat_to_rerun_values') "Audit rerun CSV row policy must live in a focused helper behind the rerun export runner."
Assert-True ($serviceAuditRerunText -match 'app\.audit\.rerun_export' -and $serviceAuditRerunText -match 'save_rerun_records_csv_for_service' -and $serviceAuditRerunExportText -match 'def save_rerun_records_csv_for_service' -and $serviceAuditRerunExportText -match 'stage_mode = "copy"' -and $serviceAuditRerunExportText -match 'original_mode = "keep"' -and $serviceAuditRerunExportText -match 'return_mode = "park"' -and $serviceAuditRerunExportText -match '_atomic_write_text') "Audit rerun CSV export orchestration, safe default modes, source-stat fallback, and atomic write must live in a focused export runner behind AuditRerunService compatibility wrappers."
Assert-True ($serviceAuditRerunText -match 'app\.audit\.rerun_metadata' -and $serviceAuditRerunText -match 'load_rerun_source_metadata_for_service' -and $serviceAuditRerunMetadataText -match 'def rerun_source_metadata_script_path_for_service' -and $serviceAuditRerunMetadataText -match 'def deduplicate_source_paths' -and $serviceAuditRerunMetadataText -match 'def load_rerun_source_metadata_for_service' -and $serviceAuditRerunMetadataText -match 'TemporaryDirectory' -and $serviceAuditRerunMetadataText -match 'run_capture_func' -and $serviceAuditRerunMetadataText -match 'Rerun source metadata helper timed out') "Audit rerun source-metadata helper script selection, temp JSON exchange, subprocess execution, timeout handling, and result indexing must live in a focused metadata helper behind AuditRerunService compatibility wrappers."
Assert-True ($serviceAuditRerunText -match 'app\.audit\.rerun_io' -and $serviceAuditRerunIoText -match 'def load_audit_records' -and $serviceAuditRerunIoText -match 'def save_audit_records_csv' -and $serviceAuditRerunIoText -match 'def load_failure_records' -and $serviceAuditRerunIoText -match 'def load_failure_marker_records') "Audit/rerun CSV and failure JSON file IO must live in a focused helper behind AuditRerunService compatibility wrappers."
Assert-True (($serviceAuditRerunText + $serviceAuditRerunIoText) -match 'app\.failures\.markers' -and ($serviceAuditRerunText + $serviceAuditRerunIoText) -match 'failure_record_from_marker_payload' -and $serviceFailureMarkersText -match 'FAILURE_MARKER_KEY_MAP' -and $serviceFailureMarkersText -match 'def normalize_failure_marker_payload' -and $serviceFailureMarkersText -match 'def failure_record_from_marker_payload') "Failure marker payload normalization must live in app/failures while marker-store scanning uses that shared normalization path."
Assert-True ($servicePendingPublishText -match 'app\.publish\.pending_format' -and $servicePendingPublishText -match 'format_bytes_compact' -and $servicePendingPublishText -match 'parse_pending_datetime' -and $servicePendingPublishFormatText -match 'def format_bytes_compact' -and $servicePendingPublishFormatText -match 'def format_pending_datetime_text' -and $servicePendingPublishFormatText -match 'def pending_age_text') "Pending publish presentation formatting must live in a focused helper while the service keeps manifest scanning and row construction."
Assert-True ($servicePendingPublishText -match 'app\.publish\.pending_manifest' -and $servicePendingPublishText -match 'pending_manifest_row' -and $servicePendingPublishManifestText -match 'def pending_manifest_row' -and $servicePendingPublishManifestText -match 'app\.publish\.pending_manifest_rows' -and $servicePendingPublishManifestText -match 'PendingPushManifest\.from_mapping' -and ($servicePendingPublishManifestText + $servicePendingPublishManifestRowsText) -match 'invalid_contract' -and $servicePendingPublishManifestRowsText -match 'Manifest local_file payload is missing') "Pending publish manifest contract parsing and health-row shaping must live in a focused helper while the service keeps directory scanning and aggregate counts."
Assert-True ($servicePendingPublishManifestRowsText -match 'def unreadable_pending_manifest_row' -and $servicePendingPublishManifestRowsText -match 'def invalid_contract_pending_manifest_row' -and $servicePendingPublishManifestRowsText -match 'def pending_sidecar_status' -and $servicePendingPublishManifestRowsText -match 'def readable_pending_manifest_row') "Pending publish manifest error rows, sidecar health, output size, and final row shaping must live in focused row helpers."
Assert-True ($servicePendingPublishText -match 'app\.publish\.pending_paths' -and $servicePendingPublishText -match 'build_pending_orphan_payload_row' -and $servicePendingPublishText -match 'path_from_manifest' -and $servicePendingPublishPathsText -match 'def path_from_manifest' -and $servicePendingPublishPathsText -match 'def path_from_texts' -and $servicePendingPublishPathsText -match 'def build_pending_orphan_payload_row') "Pending publish path and orphan-payload row helpers must live in a focused helper while the service keeps pending-folder scan orchestration."
Assert-True ($serviceTelemetryText -match 'app\.telemetry\.health' -and $serviceTelemetryText -match 'bundled_tool_health_rows' -and $serviceTelemetryText -match 'ass_to_srt_result_row' -and $serviceTelemetryHealthText -match 'TOOL_HEALTH_DEFINITIONS' -and $serviceTelemetryHealthText -match 'def bundled_tool_health_rows' -and $serviceTelemetryHealthText -match 'def ass_to_srt_result_row') "Telemetry environment-health row and tool-discovery policy must live in a focused helper while the service keeps subprocess checks."
Assert-True ($serviceTelemetryText -match 'app\.telemetry\.nvidia' -and $serviceTelemetryText -match 'parse_nvidia_smi_encoder_rows' -and $serviceTelemetryText -match 'apply_nvidia_smi_rows_to_snapshot' -and $serviceTelemetryNvidiaText -match 'def parse_nvidia_smi_encoder_rows' -and $serviceTelemetryNvidiaText -match 'def apply_nvidia_smi_rows_to_snapshot' -and $serviceTelemetryNvidiaText -match 'N/A when NVENC is idle') "NVENC telemetry parsing and 0-percent row visibility must live in a focused helper behind the telemetry sampler."
Assert-True ($serviceTelemetryText -match 'app\.observability\.system_metrics' -and $serviceTelemetryText -match 'apply_system_metrics_to_snapshot' -and $serviceTelemetryText -match 'prime_cpu_sampler' -and $serviceTelemetrySystemText -match 'def apply_system_metrics_to_snapshot' -and $serviceTelemetrySystemText -match 'def prime_cpu_sampler' -and $serviceTelemetrySystemText -match 'psutil unavailable') "Telemetry CPU/memory snapshot policy must live in app/observability while the service keeps the sampler loop and subprocess checks."
Assert-True ($controlFlagServiceText -match 'CONTROL_FLAG_SCHEMA_VERSION' -and $controlFlagServiceText -match 'request_id' -and $serviceProcessesText -match '_write_control_flag' -and $serviceProcessControlFlagsText -match 'write_control_flag' -and $serviceProcessLaunchCleanupText -match 'def prepare_control_flags_for_launch' -and $serviceProcessesText -match 'prepare_pipeline_control_flags_for_launch' -and ($appText + $processLifecycleControllerText) -match 'prepare_pipeline_control_flags_for_launch' -and $progressStateText -match 'function Get-ControlFlagInfo' -and $progressStateText -match 'ControlRequests' -and $libraryIndexText -match 'Register-ControlFlagObservation -Kind rescan') "Pause/stop/rescan controls must use atomic structured flag writes, launch-time stale cleanup, and backend observation in progress JSON."
Assert-True ($serviceProcessesText -match 'app\.processes\.control_runner' -and $serviceProcessesText -match 'prepare_pipeline_control_flags_for_service' -and $serviceProcessesText -match 'toggle_pause_flag_for_service' -and $serviceProcessesText -match 'write_flag_for_service' -and $serviceProcessControlRunnerText -match 'def prepare_pipeline_control_flags_for_service' -and $serviceProcessControlRunnerText -match 'prepare_control_flags_for_launch_helper' -and $serviceProcessControlRunnerText -match 'def toggle_pause_flag_for_service' -and $serviceProcessControlRunnerText -match 'def write_flag_for_service' -and $serviceProcessControlRunnerText -match 'read_control_flag_payload\(flag_path, logger=service\.logger\)') "Desktop pause/stop/rescan service orchestration must live in a focused runner behind ProcessLifecycleService compatibility wrappers."
Assert-True (($controlFlagServiceText + $runtimeArtifactServiceText) -match 'app\.processes\.launch_cleanup' -and $serviceProcessLaunchCleanupText -match 'def prepare_stale_progress_cleanup' -and $serviceProcessLaunchCleanupText -match 'Stale \{progress_label\} progress was not cleared' -and $serviceProcessLaunchCleanupText -match 'Cleared stale \{progress_label\} progress before launch') "Desktop launch-time stale progress and control-flag cleanup policy must live in a focused helper while process service keeps process ownership."
Assert-True ($controlFlagContractText -match 'class ControlFlagRecord' -and $controlFlagContractText -match 'CONTROL_FLAG_SCHEMA_VERSION = "pipeline_control_flag\.v1"' -and $controlFlagContractText -match 'CONTROL_FLAG_ACTIONS' -and $controlFlagServiceText -match 'ControlFlagRecord\.from_mapping' -and $controlFlagServiceText -match 'Control flag contract invalid' -and @($controlFlagJsonSchemaModel.required) -contains 'request_id' -and @($controlFlagJsonSchemaModel.properties.action.enum) -contains 'pause' -and @($controlFlagJsonSchemaModel.properties.action.enum) -contains 'stop' -and @($controlFlagJsonSchemaModel.properties.action.enum) -contains 'rescan') "Pause/stop/rescan flag payloads must be pinned by a Python contract and JSON schema while preserving legacy file-exists semantics for pipeline readers."
Assert-True ($pipelineText -match 'Resolve-BundledExecutable' -and $mainText -match 'ExecutableResolution\.ps1' -and $mainText -match '\$moduleRoot\s*=\s*if \(\$PSScriptRoot\)' -and $mainText -match '\[System.Threading.Mutex\]::new' -and $diskText -match 'function Copy-FileRobocopy' -and $diskText -match 'function Resolve-RobocopyPath' -and $pipelineText -match 'Invoke-ExternalToolCommand' -and $pipelineText -match 'Invoke-FFmpegCommand' -and $pipelineText -match 'Invoke-MkvmergeCommand' -and $pipelineText -match 'Invoke-RecursivePathScan' -and ($servicesText + $serviceProcessesText + $serviceProcessSpawnRunnerText) -match 'subprocess\.Popen' -and $servicesText -notmatch 'Resolve-InitialMediaRoutePlan|Resolve-RemuxCodecRoutePlan|Do-Encode|Do-Remux|Process-File|Convert-Tx3gToSrt|Convert-BdpgsToSrt') "PowerShell must own portable startup, path resolution, process/tool launching, and Windows filesystem operations while Python remains a UI/process-supervision boundary."
Assert-True ($progressStateText -notmatch 'Pause flag stale|TotalHours\s+-gt\s+1') "Manual pause flags must remain paused until explicit operator removal or stop request."
Assert-True ($auditText -match 'Audit\.Progress\.ps1' -and $auditText -match 'Audit\.Policy\.ps1' -and $auditText -match 'Audit\.Probe\.ps1' -and $auditText -match 'Audit\.Reports\.ps1' -and $auditText -match 'Audit\.Scanner\.ps1') "Audit script must load focused audit modules for progress, policy, probe cache, reporting, and scanning."
Assert-True ($auditText -match 'Invoke-AuditFileScan' -and $auditText -notmatch 'Write-Progress -Activity') "Audit scanner orchestration must be decoupled from direct console/UI progress rendering."
Assert-True ($auditText -match 'Write-AuditReportBundle' -and $auditText -notmatch 'Export-CsvAtomic -Path' -and $pipelineText -match 'New-AuditReportModel') "Audit report writing must flow through the report module and shared report model."
Assert-True ($pipelineText -match 'function Get-PriorityScore' -and $pipelineText -match 'function Invoke-FfprobeJsonCached') "Audit issue policy and probe-cache logic must live in focused modules."
Assert-True ($mainText -notmatch 'now live in Modules|module-extraction transition|Future cleanup') "Main pipeline must not retain obsolete module-extraction scaffolding comments."
Assert-True ($configSchemaModuleText -match 'Get-MediaPipelineConfigCurrentSchemaVersion' -and $configSchemaModuleText -match 'Test-MediaPipelineConfigSchema' -and $configSchemaModuleText -match 'Get-MediaPipelineConfigDefaultValues' -and $pipelineText -match 'ConfigSchema.ps1' -and $pipelineText -match 'Test-MediaPipelineConfigSchema' -and $setupText -match 'Get-MediaPipelineConfigDefaultValues' -and ($servicesText + $serviceConfigText + $serviceConstantsText) -match 'CONFIG_SCHEMA_VERSION') "PSD1 config loading must use a schema-versioned compatibility layer shared by the pipeline, setup, and desktop app."
Assert-True ($serviceConfigText -match 'app\.config\.document_runner' -and $serviceConfigText -match 'load_config_data_for_service' -and $serviceConfigText -match 'validate_config_document_for_save_for_service' -and $serviceConfigText -match 'run_capture' -and $serviceConfigDocumentRunnerText -match 'def load_config_data_for_service' -and $serviceConfigDocumentRunnerText -match 'label="config import"' -and $serviceConfigDocumentRunnerText -match 'def validate_config_document_for_save_for_service' -and $serviceConfigDocumentRunnerText -match 'config syntax validation' -and $serviceConfigDocumentRunnerText -match 'Import-PowerShellDataFile') "Desktop config document import and PSD1 syntax validation subprocess orchestration must live in a focused runner while preserving the service run_capture compatibility patch point."
Assert-True ($serviceConfigText -match 'app\.config\.save_runner' -and $serviceConfigText -match 'save_config_document_for_service' -and $serviceConfigText -match 'save_config_profile_for_service' -and $serviceConfigText -match 'load_config_profile_for_service' -and $serviceConfigSaveRunnerText -match 'def save_config_document_for_service' -and $serviceConfigSaveRunnerText -match 'def list_config_profiles_for_service' -and $serviceConfigSaveRunnerText -match 'def save_config_profile_for_service' -and $serviceConfigSaveRunnerText -match 'def load_config_profile_for_service' -and $serviceConfigSaveRunnerText -match '_atomic_write_text') "Desktop config document save, profile listing, path normalization, and profile save/load file I/O must live in a focused runner behind ConfigProfileService compatibility wrappers."
Assert-True ($serviceConfigText -match 'app\.config\.preview' -and $serviceConfigText -match 'build_config_preview_helper' -and $serviceConfigPreviewText -match 'def build_config_preview' -and $serviceConfigPreviewText -match 'ExtraVideoFlags' -and $serviceConfigPreviewText -match 'AudioPassthroughProfile' -and $serviceConfigPreviewText -match 'CompatibleAudioCodecs') "Desktop config preview merge, encoder tuning, and audio-profile codec policy must live in a focused helper behind config service compatibility wrappers."
Assert-True ($serviceConfigText -match 'app\.config\.validation' -and $serviceConfigText -match 'def validate_config_values' -and $serviceConfigText -match 'def _config_path_overlap_warning' -and $serviceConfigValidationText -match 'def validate_config_values' -and $serviceConfigValidationText -match 'def config_path_overlap_warning' -and $serviceConfigOptionPolicyText -match 'AudioTranscodeBitrate must be a positive ffmpeg bitrate like 640k') "Desktop config value validation and root-overlap warnings must live in focused helpers behind ConfigProfileService compatibility wrappers."
Assert-True ($serviceConfigValidationText -match 'app\.config\.numeric_policy' -and $serviceConfigValidationText -match 'validate_required_and_numeric_config' -and $serviceConfigNumericPolicyText -match 'def validate_required_and_numeric_config' -and $serviceConfigNumericPolicyText -match 'IndexScanTimeoutSeconds' -and $serviceConfigNumericPolicyText -match 'TransientFailureRetryLimit') "Desktop required-field and numeric config bounds must live in a focused policy helper behind config validation."
Assert-True ($serviceConfigValidationText -match 'app\.config\.option_policy' -and $serviceConfigValidationText -match 'validate_option_config' -and $serviceConfigOptionPolicyText -match 'def validate_option_config' -and $serviceConfigOptionPolicyText -match 'EncodeTuningPreset must be one of' -and $serviceConfigOptionPolicyText -match 'CompatibleAudioCodecs are controlled by AudioPassthroughProfile') "Desktop config enum, structured encoding, audio, log-level, and required-list policy must live in a focused option helper behind config validation."
Assert-True ($serviceConfigValidationText -match 'app\.config\.path_warnings' -and $serviceConfigValidationText -match 'config_root_path_warnings' -and $serviceConfigPathWarningsText -match 'def config_path_overlap_warning' -and $serviceConfigPathWarningsText -match 'def config_root_path_warnings' -and $serviceConfigPathWarningsText -match 'LocalBase and Outsource are identical') "Desktop config root path overlap warning policy must live in a focused helper behind config validation compatibility wrappers."
Assert-True ($serviceConfigNumericPolicyText -match 'app\.config\.value_checks' -and $serviceConfigNumericPolicyText -match 'validate_optional_float' -and $serviceConfigValueChecksText -match 'def require_non_empty' -and $serviceConfigValueChecksText -match 'def validate_int' -and $serviceConfigValueChecksText -match 'def add_unique_warning') "Desktop primitive config value checks must live in focused helpers behind the config validation policy."
Assert-True ($settingsRiskPolicyText -match 'settings_risk_policy_rules' -and $settingsRiskPolicyText -match 'changed_key_risk_item' -and $settingsRiskPolicyRulesText -match 'def changed_key_risk_item' -and $settingsRiskPolicyRulesText -match 'source_mutation_policy' -and $settingsRiskPolicyRulesText -match 'SizeGuardMode is off') "Desktop settings patch risk classification must live in focused rules behind the application risk-summary entry point."
Assert-True ($setupText -match 'function Get-DefaultConfig\s*\{[\s\r\n]*Get-MediaPipelineConfigDefaultValues[\s\r\n]*\}') "Setup bootstrap defaults must be delegated to the shared config schema module."
Assert-True ([int]$configJsonSchemaModel.'x-config-schema-version' -eq 1 -and @($configJsonSchemaModel.required) -contains 'SourceMovies' -and @($configJsonSchemaModel.properties.PSObject.Properties.Name) -contains 'ConfigSchemaVersion' -and @($configJsonSchemaModel.properties.PSObject.Properties.Name) -contains 'BdpgsOcrTimeoutSeconds') "Config contract must include a versioned JSON schema with required and optional pipeline keys."
Assert-True (
    $releaseBuilderText -match 'KeepPersonalConfig' -and
    $releaseBuilderText -match 'MediaPipeline_config_chatgpt\.psd1' -and
    $releaseBuilderText -match 'MediaPipeline_config_template\.psd1' -and
    $releaseBuilderText -match 'release_manifest\.json' -and
    $releaseBuilderText -match 'DesktopApp\\RunLogs' -and
    $releaseBuilderText -match '__pycache__' -and
    $releaseBuilderText -match 'local Office working document' -and
    $releaseBuilderText -match 'personal live config' -and
    $releaseBuilderText -match 'tauri node modules omitted' -and
    $releaseBuilderText -match 'tauri generated schema output omitted' -and
    $releaseBuilderText -match 'tauri rust build output omitted' -and
    $releaseBuilderText -match '\[switch\]\$IncludeOptionalTools' -and
    $releaseBuilderText -match '\[switch\]\$IncludeToolDocs' -and
    $releaseBuilderText -match 'ffplay\.exe' -and
    $releaseBuilderText -match 'mkvtoolnix-gui' -and
    $releaseBuilderText -match 'mkvextract' -and
    $releaseBuilderText -match 'optional_tools_included' -and
    $releaseBuilderText -match 'tool_docs_policy' -and
    $deployabilityChecklistText -match 'scripts\\ops\release\metadata\\build\.ps1'
) "Deployability boundary must provide a release builder that strips live personal config, runtime clutter, and optional tool bulk while producing a manifest."
Assert-True (
    $environmentVerifierText -match 'PgsToSrt' -and
    $environmentVerifierText -match 'tessdata' -and
    $environmentVerifierText -match 'eng\.traineddata' -and
    $environmentVerifierText -match 'zeroconf' -and
    $environmentVerifierText -match 'NetworkRole' -and
    $releaseVerifierText -match 'Invoke-ReliabilityRegressionChecks\.ps1' -and
    $releaseVerifierText -match 'Invoke-ToolIntegrationChecks\.ps1' -and
    $releaseVerifierText -match 'Invoke-EndToEndSmokeChecks\.ps1' -and
    $releaseVerifierText -match 'release_manifest\.json' -and
    $releaseVerifierText -match 'Test-ReleaseManifestHygiene' -and
    $releaseVerifierText -match 'personal_config_included' -and
    $releaseVerifierText -match 'optional_tools_included' -and
    $releaseVerifierText -match 'tool_docs_included' -and
    $releaseVerifierText -match 'DesktopApp\\RunLogs' -and
    $releaseVerifierText -match 'Tauri node modules' -and
    $releaseVerifierText -match 'Tauri generated schemas' -and
    $releaseVerifierText -match 'Tauri Rust build output' -and
    $releaseVerifierText -match 'Pipeline\\\*\.log' -and
    $releaseVerifierText -match 'local Office working documents' -and
    $releaseVerifierText -match 'MediaPipeline_config_chatgpt\.psd1' -and
    $releaseVerifierText -match 'ffplay\.exe' -and
    $releaseVerifierText -match 'mkvtoolnix-gui\.exe' -and
    $releaseVerifierText -match 'Build with -IncludeTests' -and
    $releaseBuilderText -match '\[switch\]\$Verify' -and
    $releaseBuilderText -match 'if \(\$IncludeTests -and \$name -eq ''DEPLOYABILITY_CHECKLIST\.md''\)' -and
    $releaseBuilderText -match 'scripts\\ops\release\metadata\\test\.ps1'
) "Deployability verification must check OCR/network readiness, manifest hygiene, and provide a one-command release self-test wired to the release builder."
Assert-True (
    [int]$configTemplateData.ConfigSchemaVersion -eq 1 -and
    $configTemplateData.SourceMovies -match 'C:\\MediaPipeline\\Incoming\\Movies' -and
    $configTemplateText -notmatch 'LAYNE|Layne|LAYNE-SERVER|E:/Videos|//LAYNE|Users/Layne'
) "New-user config template must be parseable and free of operator-specific paths."
Assert-True ($configSchemaModuleText -match 'Test-MediaPipelineConfigPathShape' -and $configSchemaModuleText -match 'Test-MediaPipelineConfigSubtitleToggles' -and $configSchemaModuleText -match 'ConvertBdpgsToSrt requires BdpgsOcrToolPath') "Schema validation must cover path shape, conflicting subtitle toggles, and OCR tool settings."
Assert-True ($stateStoreText -match 'media_pipeline_state_layout\.v1' -and $stateStoreText -match 'New-MediaPipelineStateLayout' -and $stateStoreText -match 'Initialize-MediaPipelineStateLayout' -and $mainText -match 'StateStore\.ps1' -and $mainText -match '\$script:LocalStateLayout\.Paths\.ProgressFile' -and $mainText -match '\$script:LocalStateLayout\.Paths\.CompletedJobsManifest' -and ($servicesText + $servicePathsText) -match '_state_root_for_local_base' -and ($servicesText + $servicePathsText + $servicePathResolutionRunnerText + $serviceQueueText + $serviceQueueSnapshotText) -match 'resolved\.state_root / "Progress" / "queue_snapshot\.json"') "Pipeline and desktop state paths must flow through a versioned LocalBase\\State layout."
Assert-True ($pipelineText -match 'Invoke-ExternalToolCommand' -and $pipelineText -match 'Invoke-FFprobeCommand' -and $pipelineText -match 'Invoke-FFmpegCommand' -and $pipelineText -match 'Invoke-MkvmergeCommand' -and $pipelineText -match 'Invoke-BdpgsOcrCommand') "External FFprobe/FFmpeg/MKVToolNix/BDPGS OCR execution must flow through named wrappers."
Assert-True ($pipelineText -match 'ToolErrorCode' -and $pipelineText -match 'DurationSeconds' -and $pipelineText -match 'CommandLine' -and $pipelineText -match 'SaveReproOnFailure') "External tool wrapper results must include command, duration, classification, and repro metadata."
Assert-True ($mainText -match '\$moduleRoot\s*=\s*if \(\$PSScriptRoot\) \{ Join-Path \$PSScriptRoot ''Modules'' \}' -and $subtitleFacadeText -match '\$PSScriptRoot' -and $subtitleCommonText -match 'Resolve-SubtitleConfiguredPath[\s\S]+\$scriptDir[\s\S]+\$PSScriptRoot') "Refactored modules must resolve paths from the portable bundle script root before falling back to process cwd."
Assert-True ($pipelineText -match 'Resolve-BundledExecutable[\s\S]+Join-Path \$scriptDir \$relative[\s\S]+if \(-not \$script:AllowSystemTools\)\s*\{[\s\r\n]+return \$null' -and $mainText -match 'FATAL: bundled ffmpeg/ffprobe not found' -and $mainText -match 'FATAL: bundled mkvmerge not found' -and $mainText -match 'FATAL: bundled python not found') "Runtime tool resolution must prefer bundled tools and fail fast unless AllowSystemTools is explicitly enabled."
Assert-True ($regressionText -match 'missing required config key should fail schema validation' -and $regressionText -match 'Runtime tool resolution must prefer bundled tools and fail fast') "Regression checks must cover invalid-config and missing-tool fail-fast behavior."
Assert-True ($pipelineText -notmatch 'C:\\Users\\|[A-Z]:\\Videos|\\\\\?\\[A-Z]:' -and $diskText -notmatch '[A-Z]:\\Videos') "Reusable pipeline code must not embed user-specific paths or concrete media drive examples."
Assert-True ($pipelineText -match 'Invoke-RecursivePathScan' -and $pipelineText -match 'SourceScanTimeoutSeconds') "Recursive source/outsource scans must be timeout bounded."
Assert-True ($pipelineText -match 'Test-PathAccessibleBounded' -and $pipelineText -notmatch 'foreach \(\$pair[\s\S]{0,300}Test-Path -LiteralPath \$pair\.Path') "Startup path validation must not use unbounded Test-Path against source/share paths."
Assert-True ($pipelineText -match 'Test-IsUncPath \(\[string\]\$pair\.Path\)' -and $pipelineText -match 'startup reachability probe skipped') "Startup path validation must skip UNC source/output reachability probes and leave network validation to bounded scan/copy phases."
Assert-True ($pipelineText -match 'Test-OutputNeedsReprocess[\s\S]+source_identity' -and $pipelineText -match 'SourceFile') "Existing output skip checks must validate source identity."
Assert-True ($pipelineText -match 'Test-FileIntegrityDetailed' -and $pipelineText -match 'scratch-integrity' -and $pipelineText -match 'ErrorCode') "Scratch integrity failures must expose ffprobe diagnostics and source-failure error codes."
Assert-True ($pipelineText -match '"-map",\s*"0:V"' -and $pipelineText -match 'hevc_mp4toannexb' -and $pipelineText -match 'REMUX_HEVC_MKV_BITSTREAM_FAILED' -and $mainText -match '"-map",\s*"0:t\?"' -and $mainText -match '"-map_metadata",\s*"0"') "Remux AV stage must map all real video streams (-map 0:V, R4), preserve attachments (-map 0:t?, R3), keep source metadata (-map_metadata 0, R12), normalize HEVC for Matroska, and classify HEVC header failures."

# TR1 + TR2 + TR3 — remux pre-flight, configurable mkvmerge timeout, and
# the new mkvmerge-with-progress wrapper.
Assert-True ($mainText -match 'Test-EstimatedOutputSpace -SourcePath \$localIn -Label "REMUX" -RemuxTwoStage' -and $mainText -match 'Test-EstimatedOutputSpace -SourcePath \$localIn -Label "REMUX-MUX" -RemuxFinalStage') "Remux must run a 2.5x source-size pre-flight before the AV stage and a final-stage check before mkvmerge so the scratch volume cannot fill mid-mux (R1/R10)."
Assert-True ($mainText -match '\$script:MkvmergeRemuxTimeoutSeconds = Get-ConfigInt ''MkvmergeRemuxTimeoutSeconds''' -and $mainText -match '-TimeoutSeconds \$script:MkvmergeRemuxTimeoutSeconds' -and $mainText -notmatch '-TimeoutSeconds 600 -Stage ''remux-mkvmerge''') "Mkvmerge remux step must use the configurable MkvmergeRemuxTimeoutSeconds (default 7200), not the previous hard-coded 600s ceiling (R2)."
Assert-True ($ffmpegProgressText -match 'function Invoke-MkvmergeWithProgress' -and $ffmpegProgressText -match 'function Get-MkvmergeProgressPercentFromLine' -and $ffmpegProgressText -match '#GUI#progress' -and $mainText -match 'Invoke-MkvmergeWithProgress -ArgumentList @\(\$mkvArgs\) -Label ''REMUX-MUX''') "Mkvmerge final-mux step must run through Invoke-MkvmergeWithProgress so the GUI shows per-percent progress during multi-minute muxes (R5)."

# TR4 + TR5 — source title preservation and codec-fallback scratch reuse.
Assert-True ($mediaProbeText -match 'function Get-SourceTitleTag' -and $mainText -match '\$sourceTitle = Get-SourceTitleTag' -and $mainText -match 'preserving source title') "Remux must preserve the source's container title tag when present instead of always overwriting with the generic pipeline title (R8)."
Assert-True ($mainText -notmatch 'Clean up the scratch copy we made so Do-Encode starts fresh' -and $mainText -match 'leave the scratch copy in place' -and $mainText -match 'Ensure-ScratchCopy which is idempotent') "Codec-fallback path from Do-Remux into Do-Encode must reuse the existing scratch copy instead of deleting and re-copying from the network share (R7)."

# TR6 — subtitle extraction order: AV stage validates the source first,
# THEN expensive BDPGS OCR / TX3G / ASS conversion runs. Without this,
# minutes of OCR work are wasted whenever the AV stage exits corrupt.
Assert-True ($mainText -match '(?s)Label\s*=\s*''REMUX-AV''.*?Invoke-FFmpegWithProgress @remuxAvCallArgs.*?Build-SubtitleTracksForMkvmerge') "Remux must run subtitle extraction (Build-SubtitleTracksForMkvmerge) AFTER the AV ffmpeg stage succeeds so OCR/conversion work is not wasted on corrupt sources (R6)."

# TR7 — explicit audio default-track flags emitted to mkvmerge so the
# disposition is not at the mercy of cross-version disposition translation.
Assert-True ($audioText -match '\$script:LastAudioDefaultIndex' -and $audioText -match '\$script:LastAudioTrackCount' -and $subtitleBuildersText -match 'function Get-MkvmergeAudioTids' -and $mainText -match 'Get-MkvmergeAudioTids -FilePath \$tempAvFile' -and $mainText -match '"--default-track"') "mkvmerge step must emit explicit numeric --default-track TID flags for audio tracks based on Build-AudioArgs's chosen default index (R9)."

# CPU-A regressions — audio transcode awareness on the remux path,
# priority/mutex/threads plumbed into all CPU-bound external work.
# CPU-A1: Build-AudioArgs surfaces transcode-active flag.
Assert-True ($audioText -match '\$script:LastAudioTranscodeActive' -and $audioText -match '\$transcodeActive\s*=\s*\$true' -and $audioText -match 'AV stage will run as CPU-bound work') "Build-AudioArgs must surface LastAudioTranscodeActive so the remux AV stage can detect it is no longer pure stream-copy (CPU-A1)."

# CPU-A2: -ProcessPriority threaded through Invoke-NativeProcess +
# Invoke-ExternalToolCommand + per-tool wrappers.
Assert-True ($nativeText -match 'function Invoke-NativeProcess[\s\S]+?\[string\]\$ProcessPriority\s*=\s*''inherit''' -and $nativeText -match 'priorityClassEnum\s*=\s*\[System\.Diagnostics\.ProcessPriorityClass\]::BelowNormal' -and $nativeText -match 'function Invoke-ExternalToolCommand[\s\S]+?\[string\]\$ProcessPriority\s*=\s*''inherit''' -and $nativeText -match 'function Invoke-FFmpegCommand[\s\S]+?\[string\]\$ProcessPriority\s*=\s*''inherit''' -and $nativeText -match 'function Invoke-BdpgsOcrCommand[\s\S]+?\[string\]\$ProcessPriority\s*=\s*''inherit''') "Native command stack must accept -ProcessPriority and apply it via ProcessPriorityClass on the spawned child (CPU-A2)."

# CPU-A3: Remux AV stage opts into CPU encode mode + CPU mutex when
# audio transcode is active. Pure stream-copy AV (no transcode) keeps
# default priority since it is I/O bound.
Assert-True ($mainText -match '\$remuxAvCpuEncode\s*=\s*\[bool\]\$script:LastAudioTranscodeActive' -and $mainText -match 'Acquire-CpuEncodeMutex' -and $mainText -match "remuxAvCallArgs\['CpuEncode'\]\s*=\s*\`$true" -and $mainText -match "remuxAvCallArgs\['ProcessPriority'\]\s*=\s*\`$script:CpuEncodeProcessPriority") "Remux AV stage must run as CPU-bound work (priority + mutex + Invoke-FFmpegWithProgress -CpuEncode) when audio transcode is active (CPU-A3)."

# CPU-A4: BDPGS OCR runs at CpuEncodeProcessPriority and holds the
# machine-wide CPU mutex so it doesn't race with libx265 fallback or
# transcode-active remux AV stages.
Assert-True ($subtitleBdpgsText -match 'Acquire-CpuEncodeMutex' -and $subtitleBdpgsText -match '-ProcessPriority \$ocrPriority' -and $subtitleBdpgsText -match '\$script:CpuEncodeProcessPriority') "BDPGS OCR must hold the CPU mutex and run at the configured CPU encode priority (CPU-A4)."

# CPU-A6: When transcode is active AND CpuEncodeMaxThreads > 0, the
# remux AV stage emits -threads N to cap the audio encoder pool.
Assert-True ($mainText -match '\$threadCapArgs\s*=\s*@\(\)' -and $mainText -match '\$script:LastAudioTranscodeActive\s*-and\s*\[int\]\$script:CpuEncodeMaxThreads\s*-gt\s*0' -and $mainText -match '''-threads'',\s*\[string\]\$script:CpuEncodeMaxThreads') "Remux AV stage must emit -threads N when audio transcode is active and CpuEncodeMaxThreads > 0 (CPU-A6)."

# Suggestion #2 — NVENC probe cache invalidation after runtime failure.
Assert-True ($encodePolicyText -match 'function Invalidate-NvencAvailableProbe' -and $encodePolicyText -match 'function Test-NvencProbeReportsAvailable') "EncodePolicy must expose Invalidate-NvencAvailableProbe and Test-NvencProbeReportsAvailable so Do-Encode can short-circuit GPU attempts after a cached failure (Suggestion #2)."
Assert-True ($encodePolicyText -match 'function Test-ShouldRetryEncodeWithCpuFallback[\s\S]+?\[bool\]\s*\$ForceCpu') "Test-ShouldRetryEncodeWithCpuFallback must accept -ForceCpu so Do-Encode can fire the CPU branch when the probe is invalidated (Suggestion #2)."
Assert-True ($mainText -match '\$skipGpuDueToProbe\s*=\s*-not \(Test-NvencProbeReportsAvailable\)' -and $mainText -match 'NVENC unavailable per cached probe' -and $mainText -match 'NVENC probe cache reports unavailable; primary GPU attempt skipped' -and $mainText -match 'NVENC probe cache reports unavailable; safe-retry skipped') "Do-Encode must skip the primary AND safe-retry attempts entirely when the cached NVENC probe reports unavailable (Suggestion #2)."
Assert-True ($mainText -match 'Invalidate-NvencAvailableProbe -Reason \$invalidateReason -SourcePath \$file\.FullName') "Do-Encode must invalidate the NVENC probe cache after the second hardware failure so subsequent files skip the GPU ladder (Suggestion #2)."
Assert-True ($mainText -match "(?s)if \(\`$skipGpuDueToProbe\)[^{]*\{[^}]*'gpu_unavailable_cpu_only'") "CPU success block must set 'gpu_unavailable_cpu_only' when the probe-skip path took us to CPU (Suggestion #2)."
Assert-True ($mainText -match "'hardware_encoder_cpu_fallback'") "CPU success block must still emit 'hardware_encoder_cpu_fallback' for the real-GPU-failure path (Suggestion #2)."
Assert-True ($routingText -match "'gpu_unavailable_cpu_only'") "Test-MediaEncodeOutputSizePolicy compatibility-reason list must include 'gpu_unavailable_cpu_only' so probe-skipped CPU encodes still receive the 15%% growth budget (Suggestion #2)."

# Suggestion #1 — HDR10 mastering display / MaxCLL extraction reaches the
# CPU x265 -x265-params string so BluRay HDR sources keep their HDR10 SEI.
Assert-True ($mediaProbeText -match 'function Get-SourceHdr10MasteringMetadata' -and $mediaProbeText -match 'side_data_list' -and $mediaProbeText -match 'master-display' -or $mediaProbeText -match 'MasterDisplay') "MediaProbe must expose Get-SourceHdr10MasteringMetadata that ffprobes the source's first-frame side_data_list and returns x265-formatted strings (Suggestion #1)."
Assert-True ($encodePolicyText -match 'function New-EncodeVideoFlags[\s\S]+?\[string\]\s*\$Hdr10MasterDisplay\s*=\s*''''[\s\S]+?\[string\]\s*\$Hdr10MaxCll\s*=\s*''''') "New-EncodeVideoFlags must accept Hdr10MasterDisplay / Hdr10MaxCll string params for CPU+HDR (Suggestion #1)."
Assert-True ($encodePolicyText -match 'master-display=\$Hdr10MasterDisplay' -and $encodePolicyText -match 'max-cll=\$Hdr10MaxCll') "CPU+HDR x265-params builder must append master-display= and max-cll= when the metadata strings are non-empty (Suggestion #1)."
Assert-True ($encodePolicyText -match 'function New-EncodeAttemptPlan[\s\S]+?\[string\]\s*\$Hdr10MasterDisplay\s*=\s*''''[\s\S]+?\[string\]\s*\$Hdr10MaxCll\s*=\s*''''[\s\S]+?-Hdr10MasterDisplay \$Hdr10MasterDisplay') "New-EncodeAttemptPlan must forward the HDR10 strings to New-EncodeVideoFlags (Suggestion #1)."
Assert-True ($mainText -match 'Get-SourceHdr10MasteringMetadata -FilePath \$localIn' -and $mainText -match '-Hdr10MasterDisplay \$hdr10MasterDisplay' -and $mainText -match '-Hdr10MaxCll \$hdr10MaxCll' -and $mainText -match 'CPU-encoded HDR output will lack master-display/MaxCLL SEI') "Do-Encode must probe HDR10 metadata once after Get-HDRState and forward the strings to every plan-build call (Suggestion #1)."

# Suggestion #6 — priority application result surfaces on tool_completed.
Assert-True ($nativeText -match '\$priorityApplied\s*=\s*\$true' -and $nativeText -match 'PriorityRequested' -and $nativeText -match 'PriorityApplied' -and $nativeText -match 'priority_requested\s*=' -and $nativeText -match 'priority_applied\s*=') "Native tool_completed events must carry priority_requested/priority_applied so the diagnostics drawer can show 'requested but not applied' (Suggestion #6)."
Assert-True ($ffmpegProgressText -match '\$script:LastFFmpegPriorityRequested' -and $ffmpegProgressText -match '\$script:LastFFmpegPriorityApplied' -and $ffmpegProgressText -match 'priority_requested\s*=' -and $ffmpegProgressText -match 'priority_applied\s*=') "Invoke-FFmpegWithProgress tool_completed must include priority_requested/priority_applied/priority_error fields (Suggestion #6)."

# Suggestion #7 — channel-aware audio transcode bitrate.
Assert-True ($audioText -match 'function Get-AudioTranscodeBitrateForChannels' -and $audioText -match 'function Get-EffectiveAudioTranscodeAutoBitrateByChannels' -and $audioText -match "1 = '96k';\s*2 = '192k'" -and $audioText -match "6 = '448k'") "Audio module must expose channel-aware bitrate helpers with codec-specific tables (Suggestion #7)."
Assert-True ($audioText -match '\$autoScaleBitrate\s*=\s*Get-EffectiveAudioTranscodeAutoBitrateByChannels' -and $audioText -match 'if \(\$autoScaleBitrate\)\s*\{[\s\S]+?Get-AudioTranscodeBitrateForChannels') "Build-AudioArgs must use Get-AudioTranscodeBitrateForChannels when auto-scale is on, otherwise honor the static bitrate (Suggestion #7)."
Assert-True ($mainText -match '\$script:AudioTranscodeAutoBitrateByChannels = Get-ConfigBool ''AudioTranscodeAutoBitrateByChannels'' \$false') "Main pipeline must load AudioTranscodeAutoBitrateByChannels (default off) (Suggestion #7)."
Assert-True ($pipelineText -match 'AggressiveEpisodeParsing' -and $pipelineText -match 'Get-TVLooseSeasonEpisodeFromName' -and $pipelineText -match 'aggressive-default-season') "Aggressive TV episode parsing must be configurable and include default-season fallback."
Assert-True ($pipelineText -match 'TransientFailureRetryLimit' -and $pipelineText -match 'operator_required') "Transient failures must persist retry counts and escalate to operator_required."
Assert-True ($pipelineText -match 'Test-PendingPublishedServerCopy') "Pending-push validation helper is missing."
Assert-True ($pipelineText -match 'publish_transaction_id') "Publish transaction metadata is missing."
Assert-True ($pipelineText -match 'manifest_state\s+=\s+''pending_move''' -and $pipelineText -match 'Repair-PendingManifestState' -and $pipelineText -match 'original_local_file') "Pending-push parking must create a durable intent manifest before moving the output and recover pending_move manifests."
Assert-True ($pipelineText -match 'source identity v2 mismatch' -and $pipelineText -match 'legacy existing server copy lacks enough source proof') "Pending-push recovery must strictly validate legacy/source identity before discarding local output."
Assert-True ($pipelineText -notmatch 'Remove-Item\s+-LiteralPath\s+\$paths\.ServerOut') "Sidecar failure must not delete the published server output."
Assert-True ($publishCompletionText -match 'Backup-PublishSidecarForReveal' -and $publishCompletionText -match 'Restore-PublishSidecarAfterRevealFailure' -and $publishCompletionText -match 'Write-Sidecar -OutputPath \$Paths\.ServerOut -Route \$Route -Extra \$sidecarExtra -SkipCompletedManifest' -and $publishCompletionText -match 'Add-CompletedJobsManifestEntryFromSidecar -OutputPath \$Paths\.ServerOut' -and $pipelineText -match 'SkipCompletedManifest') "Immediate publish must defer completed-manifest append until after final media reveal and restore/remove pre-reveal sidecars on reveal failure."
Assert-True ($pipelineText -notmatch 'ServerOut\.Length\s+-gt\s+240') "Output path preflight must not use a fixed 240-character cutoff."
Assert-True ($pipelineText -match 'Test-OutputPathCapability' -and $pipelineText -match 'PathUnsupported') "Capability-based output path validation is missing."
Assert-True ($auditText -match 'FfprobeTimeoutSeconds') "Audit ffprobe timeout parameter is missing."
Assert-True ($auditText -match 'AuditEnumerationTimeoutSeconds' -and $auditText -match 'Get-AuditMediaFilesBounded') "Audit media enumeration must be timeout bounded."
Assert-True ($auditText -match "RelativeCandidates\s+@\('Tools\\ffmpeg\\bin\\ffprobe\.exe'\)") "Audit must prefer the bundled ffprobe binary."
Assert-True ($pipelineText -match 'Test-AuditProgressPersistence' -and $pipelineText -match 'progress_persistence_healthy') "Audit progress persistence health fields are missing."
Assert-True ($rerunText -match 'DefaultStageMode' -and $rerunText -match 'DefaultReturnMode' -and $rerunText -match 'DryRun' -and $rerunText -match 'RerunManifests' -and $rerunText -match 'source_identity_v2') "CSV rerun runner must support stage/return policy, dry run, manifests, and source identity validation."
Assert-True ($rerunText -match 'function Copy-RerunFileVerified' -and $rerunText -match 'Invoke-RerunNativeCommand' -and $rerunText -notmatch 'Copy-Item -LiteralPath \(\[string\]\$plan\.source_path\)') "CSV rerun staging must use verified, timeout-aware staging copy instead of plain Copy-Item for media files."
Assert-True ($rerunText -match 'function Invoke-RerunStreamingCommand' -and $rerunText -match 'RerunNestedPipelineTimeoutSeconds' -and $rerunText -notmatch '&\s*\$pwsh\s+@args') "CSV rerun nested pipeline launch must be streaming, timeout-aware, and process-tree-controlled instead of a raw synchronous PowerShell call."
Assert-True ($rerunIdentityText -match 'function Invoke-RerunNativeCommand' -and $rerunIdentityText -match 'TimeoutSeconds' -and $rerunIdentityText -notmatch '&\s*\$FfprobePath') "Rerun source identity ffprobe calls must be timeout-aware and process-tree-safe."
Assert-True ($namingPreviewText -match 'New-PlexMovieDestinationPlan' -and $namingPreviewText -match 'naming_preview\.v1' -and $namingPreviewText -match 'Write-JsonAtomic' -and $namingPreviewText -match 'QueuePlan\.ps1' -and $namingPreviewText -match 'Naming\.ps1') "Standalone rename tool movie previews must call the authoritative PowerShell movie destination planner."
Assert-True (($serviceRenameText + $serviceRenamePreviewText) -match 'Get-NamingPreview\.ps1' -and ($serviceRenameText + $serviceRenamePreviewText) -match 'powershell_host' -and (($serviceRenameText + $serviceRenamePreviewText) -match 'timeout=max\(1, int\(timeout_seconds\)\)' -or ($serviceRenameText + $serviceRenamePreviewText) -match 'timeout_seconds=max\(1, int\(timeout_seconds\)\)') -and $serviceRenameText -match '_clean_pipeline_movie_name') "Desktop rename service must bridge to PowerShell naming preview with bounded subprocess fallback to the local cleaner."
Assert-True ($serviceRenameText -match 'app\.rename\.preview' -and $serviceRenameText -match 'load_pipeline_name_previews' -and $serviceRenamePreviewText -match 'def load_pipeline_name_previews' -and $serviceRenamePreviewText -match 'def parse_naming_preview_rows' -and $serviceRenamePreviewText -match 'naming_preview_request\.v1') "Rename pipeline naming-preview script discovery, subprocess execution, and output parsing must live in a focused helper behind RenameService compatibility wrappers."
Assert-True ($serviceRenameText -match 'app\.rename\.preview_runner' -and $serviceRenameText -match 'load_pipeline_name_previews_for_service' -and $serviceRenameText -match 'run_capture' -and $serviceRenamePreviewRunnerText -match 'def naming_preview_script_path_for_service' -and $serviceRenamePreviewRunnerText -match 'def load_pipeline_name_previews_for_service' -and $serviceRenamePreviewRunnerText -match '_subprocess_kwargs_hidden' -and $serviceRenamePreviewRunnerText -match 'run_capture_func=run_capture_func') "Rename pipeline naming-preview service orchestration must live in a focused runner while preserving the service run_capture compatibility patch point."
Assert-True ($serviceRenameText -match 'app\.rename\.discovery' -and $serviceRenameText -match 'discover_rename_media_files_helper' -and $serviceRenameDiscoveryText -match 'def discover_rename_media_files' -and $serviceRenameDiscoveryText -match 'MEDIA_FILE_SUFFIXES' -and $serviceRenameDiscoveryText -match 'natural_sort_key') "Standalone rename media discovery must live in a focused helper behind RenameService compatibility wrappers."
Assert-True ($serviceRenameText -match 'app\.rename\.plan_policy' -and ($serviceRenameText + $serviceRenamePlannerText) -match 'rename_row_status' -and $serviceRenamePlanPolicyText -match 'def rename_row_status' -and $serviceRenamePlanPolicyText -match 'return "match"' -and $serviceRenamePlanPolicyText -match 'def normalise_manual_final_name' -and $serviceRenamePlanPolicyText -match 'def build_movie_rename_name') "Standalone rename manual override, movie target, and row status policy must live in a focused helper behind RenameService compatibility wrappers."
Assert-True ($serviceRenameText -match 'app\.rename\.planner' -and $serviceRenameText -match 'plan_rename_paths_for_service' -and $serviceRenamePlannerText -match 'def plan_rename_paths_for_service' -and $serviceRenamePlannerText -match 'MEDIA_FILE_SUFFIXES' -and $serviceRenamePlannerText -match 'VLC_LONG_PATH_THRESHOLD' -and $serviceRenamePlannerText -match 'rename_row_status') "Standalone rename TV/movie preview planning must live in a focused planner helper behind RenameService compatibility wrappers."
Assert-True ($serviceRenameText -match 'resolve_tv_folder_season_info' -and $serviceRenameTvText -match 'app\.rename\.tv_folder' -and $serviceRenameTvText -match 'resolve_tv_folder_season_info_with_cleaner' -and $serviceRenameTvFolderText -match 'def resolve_tv_folder_season_info' -and $serviceRenameTvFolderText -match 'TV_SPECIALS_FOLDER_PATTERN' -and $serviceRenameTvFolderText -match 'TV_ORDINAL_WORDS' -and $serviceRenameTvFolderText -match 'specials-folder' -and $serviceRenameTvFolderText -match 'show-season-folder') "Standalone TV rename folder season/specials inference must live in a focused helper while app.rename.tv preserves its public function and constants."
Assert-True ($serviceConstantsText -match 'RENAME_MOVIE_FILTER_OPTIONS' -and $renameViewText -match 'Built-in movie scrub filters' -and $renameViewText -match 'Clear Built-ins' -and $renameControllerText -match 'movie_filter_options') "Rename tab must expose selectable built-in movie negative filters plus custom terms."
Assert-True (($serviceRenameText + $serviceRenamePlanPolicyText) -match 'rename_row_status' -and $serviceRenamePlanPolicyText -match 'return "match"' -and $serviceRenameText -notmatch 'already has target name') "Rename preview must classify already-correct target names as match instead of warning."
Assert-True ($serviceRenameText -match 'app\.rename\.apply' -and $serviceRenameText -match 'def _rename_path_case_safe' -and $serviceRenameText -match 'def _build_rename_operations' -and $serviceRenameApplyText -match 'def rename_path_case_safe' -and $serviceRenameApplyText -match 'def update_pipeline_sidecar_after_rename' -and $serviceRenameApplyText -match 'def rollback_rename_operations') "Standalone rename apply, sidecar metadata, duplicate-target planning, and rollback helpers must stay extracted behind RenameService compatibility wrappers."
Assert-True ($serviceRenameText -match 'app\.rename\.apply_runner' -and $serviceRenameText -match 'apply_rename_path_plan_for_service' -and $serviceRenameApplyRunnerText -match 'def apply_rename_path_plan_for_service' -and $serviceRenameApplyRunnerText -match 'rename_undo\.v1' -and $serviceRenameApplyRunnerText -match 'rollback_started' -and $serviceRenameApplyRunnerText -match 'metadata_backups') "Standalone rename transaction orchestration must live in a focused apply runner behind RenameService compatibility wrappers."
Assert-True (($servicesText + $serviceAuditRerunText + $serviceAuditRerunCsvText + $serviceConstantsText) -match 'RERUN_CSV_COLUMNS' -and ($servicesText + $serviceAuditRerunText) -match 'save_rerun_records_csv' -and ($servicesText + $serviceProcessesText) -match 'start_rerun_csv' -and ($servicesText + $serviceAuditRerunText + $serviceAuditRerunCsvText) -match 'source_identity_v2') "Desktop service must export rerun CSVs and launch CSV-authoritative reruns."
Assert-True (($appText + $appShellViewText) -match 'RerunView' -and $appText -match 'export_rerun_csv_from_audit' -and $appText -match 'start_rerun_csv' -and $rerunViewText -match 'CSV Rerun') "Desktop app must expose a separate CSV Rerun tab with export and start controls."
Assert-True ($subtitleFacadeText -match 'Subtitles.Common.ps1' -and $subtitleFacadeText -match 'Subtitles.Srt.ps1' -and $subtitleFacadeText -match 'Subtitles.Ass.ps1' -and $subtitleFacadeText -match 'Subtitles.Tx3g.ps1' -and $subtitleFacadeText -match 'Subtitles.Bdpgs.ps1' -and $subtitleFacadeText -match 'Subtitles.Builders.ps1') "Subtitle module facade must load focused subtitle modules."
Assert-True ($subtitleCommonText -match 'Resolve-SubtitleStreamPolicy' -and $subtitleCommonText -match 'New-SubtitleFilterEntry' -and $subtitleCommonText -match 'Get-SubtitleSupplementalForcedSwitchName' -and $subtitleCommonText -match 'Get-SubtitleRoutingPolicyChain' -and $subtitleCommonText -match 'Resolve-SubtitleRoutingDecision' -and $subtitleCommonText -match 'Add-SubtitleRoutingDecision') "Common subtitle policy and routing decisions must be extracted from stream routing."
Assert-True ($subtitleCommonText -match 'Set-LastSubtitleDecisionRecords' -and $subtitleCommonText -match 'Get-LastSubtitleDecisionRecords' -and $subtitleCommonText -match 'New-SubtitleDecisionRecord' -and $subtitleCommonText -match 'Decisions=@\(\$decisions\)' -and $publishCompletionText -match 'subtitle_decisions') "Subtitle keep/convert/drop decisions must be captured for sidecar diagnostics."
Assert-True ($subtitleCommonText -match 'function Filter-SubtitleStreams[\s\S]+Resolve-SubtitleRoutingDecision' -and $subtitleCommonText -notmatch 'elseif\s*\(\$isTx3g\)' -and $subtitleCommonText -notmatch 'elseif\s*\(\$isBdpgs\)') "Filter-SubtitleStreams must delegate codec routing to the subtitle routing policy chain instead of owning tx3g/BDPGS conditionals."
Assert-True ($subtitleCommonText -match 'ProbeFailed=\$true' -and $mainText -match 'subtitle-probe' -and $failureStateText -match 'SUBTITLE_PROBE_FAILED') "Subtitle probe failures must surface as explicit pipeline failures instead of silently dropping subtitle tracks."
Assert-True ($subtitleAssModuleText -match 'IncludeSubtitleStyles' -and $subtitleAssModuleText -match 'ExcludeSubtitleStyles' -and $subtitleAssModuleText -match 'RemoveKaraoke') "ASS adapter must own ASS style and karaoke filtering settings."
Assert-True ($subtitleTx3gText -notmatch 'IncludeSubtitleStyles|ExcludeSubtitleStyles|RemoveKaraoke' -and $subtitleBdpgsText -notmatch 'IncludeSubtitleStyles|ExcludeSubtitleStyles|RemoveKaraoke') "TX3G and BDPGS adapters must not read ASS-only style or karaoke settings."
Assert-True ($subtitleBdpgsText -match 'BdpgsOcrToolPath' -and $subtitleBdpgsText -match 'BdpgsOcrTessdataPath' -and $subtitleTx3gText -notmatch 'BdpgsOcrToolPath|BdpgsOcrTessdataPath') "BDPGS OCR tool/tessdata handling must stay isolated from TX3G extraction."
Assert-True ($subtitleAssModuleText -match 'Complete-AtomicSrtWrite' -and $subtitleSrtText -match 'Merge-AdjacentIdenticalCues[\s\S]+Complete-AtomicSrtWrite') "ASS conversion and SRT cue merging must use validated atomic SRT writes."
Assert-True ($pipelineText -match 'Test-IsTx3gSubtitleStream' -and $pipelineText -match 'Convert-Tx3gToSrt' -and $pipelineText -match '"-map",\s*"0:\$StreamIndex"' -and $pipelineText -match 'codec_tag_string') "Pipeline must detect tx3g/mov_text streams and extract them by exact ffmpeg stream index."
Assert-True ($pipelineText -match 'Test-IsBdpgsSubtitleStream' -and $pipelineText -match 'Convert-BdpgsToSrt' -and $pipelineText -match 'Extract-BdpgsToSup' -and $pipelineText -match 'SUBTITLE_BDPGS_OCR_FAILED') "Pipeline must detect BDPGS/PGS streams and support opt-in OCR conversion through an external tool."
Assert-True ($pipelineText -match 'Test-IsPcmAudioCodec' -and $pipelineText -match 'Get-EffectiveAudioTranscodeCodec' -and $pipelineText -match 'PCM standardization' -and $pipelineText -match 'default\+forced') "PCM audio codecs must be explicitly standardized through the structured audio transcode policy while preserving forced audio disposition."
Assert-True ($audioText -match 'Set-LastAudioDecisionRecords' -and $audioText -match 'Get-LastAudioDecisionRecords' -and $audioText -match 'audio_ordinal' -and $audioText -match 'source_stream_index' -and $publishCompletionText -match 'audio_decisions') "Audio stream copy/transcode/default decisions must be captured for sidecar diagnostics."

# S1 — sidecar JSON depth must cover route_plan.decision_trace[].data
# and folder_policy nested fields. Depth 5 silently truncated to
# "System.Collections.Hashtable" strings; bumped to 10.
Assert-True ($sidecarText -match 'ConvertTo-Json -Depth 10' -and $sidecarText -notmatch 'ConvertTo-Json -Depth 5\b' -and $sidecarText -match 'Write-JsonLineAppend\s+-Path \$CompletedJobsManifest -Payload \$entry -Depth 10' -and $pendingManifestStoreText -match 'ConvertTo-Json -Depth 10') "Sidecar payload, completed-jobs manifest, and parking manifest must serialize at Depth 10 to avoid truncating nested route_plan / folder_policy / decision_trace fields (S1)."

# S2 — output_size value comparison, not just presence.
Assert-True ($sidecarText -match 'output_size mismatch' -and $sidecarText -match 'payloadLong\s*-ne\s*\$roundTripLong') "Test-SidecarRoundTripValid must compare output_size value between payload and round-trip, not just verify presence (S2)."

# S9 — media_type plumbed through deferred-publish manifest.
Assert-True ($pendingTransactionsText -match 'function New-PendingParkManifest[\s\S]+?\[string\] \$MediaType\s*=\s*''''' -and $pendingTransactionsText -match "media_type\s*=\s*if \(\[string\]::IsNullOrWhiteSpace\(\`$MediaType\)\)" -and $pendingTransactionsText -match 'function Invoke-PendingParkTransaction[\s\S]+?\[string\] \$MediaType\s*=\s*''''' -and $pendingTransactionsText -match '-MediaType \$MediaType') "Pending park manifest must carry media_type so deferred-publish sidecars match the immediate-publish path (S9)."
Assert-True ($pendingTransactionsText -match '\$manifestMediaType\s*=\s*''''' -and $pendingTransactionsText -match "media_type\s*=\s*\`$manifestMediaType") "New-PendingDrainSidecarExtra must read media_type back from the parked manifest into the drained sidecar (S9)."
Assert-True ($pendingPushText -match 'function Invoke-ParkPendingPush[\s\S]+?\[string\] \$MediaType\s*=\s*''''' -and $pendingPushText -match '-MediaType \$MediaType') "Invoke-ParkPendingPush must accept and forward MediaType to the park transaction (S9)."
Assert-True ((($publishCompletionText -split "`n" | Where-Object { $_ -match 'MediaType\s*=\s*\$sidecarMediaType' }).Count) -ge 6) "Every parkArgs hashtable in Complete-PipelineOutputPublish must populate MediaType (deferred publish + 5 error-recovery branches), six total (S9)."

# S5 — Replace fallback for SMB / FAT32 volumes that reject
# System.IO.File.Replace.
Assert-True ($sidecarText -match '\$skipReplace\s*=\s*\$false' -and $sidecarText -match 'Volume rejected Replace last attempt' -and $sidecarText -match '\$skipReplace\s*=\s*\$true' -and $sidecarText -match 'will use overwrite move on retry' -and $sidecarText -match 'Move-SidecarTempIntoPlace' -and $sidecarText -notmatch 'Remove-Item\s+-LiteralPath\s+\$sidecar\s+-Force') "Write-Sidecar must detect Replace failure and fall back to overwrite move on the next retry without explicitly deleting the current sidecar first (S5)."
Assert-True ($routingText -match 'Resolve-MediaRouteBySize' -and $routingText -match 'Resolve-InitialMediaRoutePlan' -and $routingText -match 'Resolve-RemuxCodecRoutePlan' -and $routingText -match 'Get-ActiveMediaRoutePlanMetadata' -and $pipelineText -match 'Resolve-InitialMediaRoutePlan' -and $pipelineText -match 'Resolve-RemuxCodecRoutePlan' -and $pipelineProcessingText -match 'Get-SourceMediaRouteProfile') "Initial route selection, media-profile routing, remux codec fallback, and persisted route metadata must flow through the routing/probe policy modules."
Assert-True ($encodePolicyText -match 'function New-EncodeAttemptPlan' -and $encodePolicyText -match 'function Test-ShouldRetryEncodeWithCpuFallback' -and $encodePolicyText -match 'function New-EncodeVideoFlags' -and $encodePolicyText -match 'function Get-MediaEncodeLadderProfile' -and $encodePolicyText -match 'function Get-EncodeSelectedGpuDevice' -and $encodePolicyText -match 'SelectedEncoder' -and $mainText -match 'EncodePolicy\.ps1' -and $mainText -match 'UseSafeHardwareRetry' -and $mainText -match 'selected_encoder' -and $publishCompletionText -match 'encode_selected_encoder' -and $appText -match '_configured_encoder_selection_text' -and $modelsText -match 'encode_selected_gpu_device' -and $mainText -notmatch 'function Build-EncodeVideoFlags') "GPU-first encode, hardware-safe retry, encode ladders, CPU fallback, and selected encoder/GPU attempt metadata must live in Modules\\EncodePolicy.ps1 and surface through sidecars/UI."
Assert-True ($routingText -match 'Resolve-InitialMediaRoutePlan' -and $subtitleCommonText -match 'Resolve-SubtitleStreamPolicy' -and $subtitleFacadeText -match 'Subtitles\.Common\.ps1' -and $pipelineText -match 'function New-PlexDestinationPlan' -and $publishCompletionText -match 'function Complete-PipelineOutputPublish' -and $pendingPushText -match 'function Invoke-ParkPendingPush' -and $auditText -match 'Audit\.Policy\.ps1') "Routing, subtitle, naming, publish, and audit rule sets must each have one authoritative module owner."
Assert-True (
    $mediaConstantsText -match 'MediaRouteEncodeCpuFallback' -and
    $mediaConstantsText -match 'MediaVideoCodecLibx265' -and
    $mediaConstantsText -match 'MediaVideoCodecHevcAliases' -and
    $mediaConstantsText -match 'MediaContainerMuxerMatroska' -and
    $mediaConstantsText -match 'MediaContainerMp4Family' -and
    $mediaConstantsText -match 'MediaSubtitleCodecMovText' -and
    $mediaConstantsText -match 'MediaSubtitleCodecAssAliases' -and
    $mediaConstantsText -match 'MediaSubtitleCodecSrtAliases' -and
    $mediaConstantsText -match 'MediaSubtitleCodecBdpgsAliases' -and
    $mediaConstantsText -match 'MediaSubtitleCodecTextAliases' -and
    $mediaConstantsText -match 'MediaSubtitleCodecExternalFriendlyTextAliases' -and
    $mediaConstantsText -match 'MediaSubtitleCodecImageAliases' -and
    $mediaConstantsText -match 'MediaAudioCodecPlexTranscodeRisk' -and
    $mainText -match 'MediaConstants\.ps1' -and
    $auditText -match 'MediaConstants\.ps1' -and
    $mainText -match 'Get-MediaVideoCodecHevcNames' -and
    $encodePolicyText -match 'Get-MediaVideoCodecLibx265Name' -and
    $encodePolicyText -match 'Get-MediaContainerMuxerMatroskaName' -and
    $mediaProbeText -match 'Get-MediaVideoCodecPlexDirectPlayNames' -and
    $mediaProbeText -match 'Get-MediaSubtitleCodecSrtNames' -and
    $mediaProbeText -match 'Get-MediaAudioCodecPlexTranscodeRiskNames' -and
    $subtitleCommonText -match 'Get-MediaContainerMp4FamilyNames' -and
    $subtitleCommonText -match 'Get-MediaSubtitleCodecAssNames' -and
    $subtitleTx3gText -match 'Get-MediaSubtitleCodecMovTextName' -and
    $subtitleBdpgsText -match 'Get-MediaContainerMatroskaFamilyNames' -and
    $audioText -match 'Get-MediaAudioCodecFidelityRankValue' -and
    $audioText -match 'Get-MediaAudioCodecDisplayLabel' -and
    $failureCodesText -match 'Get-MediaContainerMuxerMatroskaName' -and
    $auditText -match 'Get-MediaSubtitleCodecTextNames' -and
    $auditText -match 'Get-MediaSubtitleCodecImageNames'
) "Shared route, codec, and container literals must be centralized in Modules\\MediaConstants.ps1 for routing, encode, probe, audio, subtitle, and failure policy."
Assert-True ($regressionText -match 'small movie should route to remux' -and $regressionText -match 'large movie should route to encode' -and $regressionText -match 'PCM track should be standardized to 2\.0 EAC3 640k' -and $regressionText -match 'tx3g stream should be routed to conversion' -and $regressionText -match 'BDPGS signs/songs forced policy should retain OCR candidate' -and $regressionText -match 'mp4 output should not preserve BDPGS image subtitles') "Regression tests must cover remux-safe routing, video encode fallback, audio transcode, subtitle conversion, and container-incompatible subtitle cases."
Assert-True ($mainText -match 'FolderPolicy\.ps1' -and $folderPolicyText -match 'mediapipeline\.folder\.json' -and $folderPolicyText -match 'function Resolve-FolderPolicyOverrides' -and $folderPolicyText -match 'RouteMaxVideoBitrateMbps' -and $folderPolicyText -match 'function Merge-MediaPipelineActiveOverrides' -and $folderPolicyText -match 'function Get-ActiveFolderPolicyMetadata' -and $pipelineProcessingText -match 'Resolve-FolderPolicyOverrides' -and $pipelineProcessingText -match 'Merge-MediaPipelineActiveOverrides' -and $publishCompletionText -match 'folder_policy' -and $pendingPushText -match 'FolderPolicyMetadata') "Folder-level mediapipeline.folder.json policy sidecars must load audio, subtitle, and routing hints, merge into active per-job overrides, and stamp output sidecars/pending-push manifests."
Assert-True ($folderPolicyExampleModel.schema_version -eq 'folder_policy.v1' -and $folderPolicyExampleModel.audio.passthrough_profile -eq 'plex_balanced' -and $folderPolicyExampleModel.subtitles.ass -and $folderPolicyExampleModel.subtitles.tx3g -and $folderPolicyExampleModel.subtitles.bdpgs -and $folderPolicyExampleModel.validation.sample_file -and $folderPolicyExampleText -match 'require_uniform_stream_topology') "Folder policy example must be valid JSON and document audio profile, ASS/TX3G/BDPGS blocks, and sample-file validation."
Assert-True ($serviceFolderPolicyText -match 'app\.folder_policy\.contracts' -and $serviceFolderPolicyText -match 'default_folder_policy_payload' -and $serviceFolderPolicyText -match 'stream_topology' -and $serviceFolderPolicyContractsText -match 'def default_folder_policy' -and $serviceFolderPolicyContractsText -match 'def stream_signature' -and $serviceFolderPolicyContractsText -match 'def stream_topology') "Desktop folder-policy default payload and stream topology contracts must live in app/folder_policy helpers behind FolderPolicyService compatibility wrappers."
Assert-True ($serviceFolderPolicyText -match 'app\.folder_policy\.io' -and $serviceFolderPolicyText -match 'load_folder_policy_file' -and $serviceFolderPolicyText -match 'save_folder_policy_file' -and $serviceFolderPolicyIoText -match 'def folder_policy_path' -and $serviceFolderPolicyIoText -match 'def load_folder_policy_file' -and $serviceFolderPolicyIoText -match 'def save_folder_policy_file' -and $serviceFolderPolicyIoText -match 'json\.dumps' -and $serviceFolderPolicyIoText -match '_atomic_write_text') "Desktop folder-policy sidecar path, JSON load/shape validation, schema defaults, and atomic JSON writes must live in app/folder_policy IO helpers behind FolderPolicyService compatibility wrappers."
Assert-True ($serviceFolderPolicyText -match 'app\.folder_policy\.probe' -and $serviceFolderPolicyText -match 'parse_ffprobe_stream_signature' -and $serviceFolderPolicyProbeText -match 'def parse_ffprobe_stream_signature' -and $serviceFolderPolicyProbeText -match 'json\.loads' -and $serviceFolderPolicyProbeText -match 'stream_signature') "Desktop folder-policy ffprobe JSON parsing must live in an app/folder_policy parser behind the FolderPolicyService probe wrapper."
Assert-True ($audioText -match 'PreferredDefaultAudioLanguages' -and $audioText -match 'CompatibleAudioCodecs' -and $audioText -match 'AudioTranscodeCodec' -and $audioText -match 'ActiveOverrides' -and $subtitleCommonText -match 'ConvertAssToSrt' -and $subtitleCommonText -match 'AssKeepLanguages' -and $subtitleCommonText -match 'ConvertTx3gToSrt' -and $subtitleCommonText -match 'ConvertBdpgsToSrt' -and $regressionText -match 'folder policy sidecar should override audio and subtitle policy') "Folder-level sidecar overrides must affect audio defaults/encoding and ASS, TX3G, and BDPGS subtitle routing at runtime."
Assert-True ($audioText -match 'SOURCE_MEDIA_AUDIO_INVALID' -and $audioText -match 'Do not emit channel_layout for streamcopy') "Audio argument building must fail predictably on incomplete ffprobe metadata and avoid channel-layout rewrites on copied audio streams."
Assert-True ($pipelineText -match 'ConvertTx3gToSrt' -and $pipelineText -match 'DropTx3gAfterConversion' -and $pipelineText -match 'CreateExternalTx3gSrtSidecars' -and $pipelineText -match 'Tx3gExtractLanguages' -and $pipelineText -match 'Tx3gPreserveExistingSrt' -and $pipelineText -match 'Tx3gTreatForcedAsSeparate') "TX3G extraction/config preservation keys must be wired through the pipeline."
Assert-True ($pipelineText -match 'ConvertBdpgsToSrt' -and $pipelineText -match 'DropBdpgsAfterConversion' -and $pipelineText -match 'BdpgsExtractLanguages' -and $pipelineText -match 'BdpgsOcrToolPath' -and $pipelineText -match 'BdpgsOcrTimeoutSeconds') "BDPGS OCR config keys must be wired through the pipeline."
Assert-True ($pipelineText -match 'TreatAssSignsSongsAsForced' -and $pipelineText -match 'TreatTx3gSignsSongsAsForced' -and $pipelineText -match 'TreatBdpgsSignsSongsAsForced' -and $pipelineText -match 'SupplementalForced') "Signs/Songs forced-subtitle policy must be wired for ASS, TX3G, and BDPGS tracks."
Assert-True ($pipelineText -match 'tx3g_srt_tracks' -and $pipelineText -match 'tx3g_srt_failures' -and $pipelineText -match 'Invoke-Tx3gSidecarExportForExistingOutput') "TX3G sidecar exports must be represented in sidecars and existing-output skip handling."
Assert-True ($pipelineText -match 'tx3g_embedded_srt_tracks' -and $pipelineText -match 'tx3g_external_srt_sidecars_enabled' -and $pipelineText -match 'drop_tx3g_after_conversion') "TX3G embedded conversion and external sidecar policy must be recorded in sidecar/pending metadata."
Assert-True ($pipelineText -match 'bdpgs_embedded_srt_tracks' -and $pipelineText -match 'bdpgs_srt_failures' -and $pipelineText -match 'bdpgs_srt_conversion_enabled' -and $pipelineText -match 'drop_bdpgs_after_conversion') "BDPGS embedded OCR policy and failures must be recorded in sidecar/pending metadata."
Assert-True ($subtitleTx3gText -match 'function ConvertTo-Tx3gEmbeddedSrtTrackRecords' -and $subtitleBdpgsText -match 'function ConvertTo-BdpgsEmbeddedSrtTrackRecords' -and $mainText -notmatch 'function ConvertTo-(Tx3g|Bdpgs)EmbeddedSrtTrackRecords') "Embedded subtitle sidecar metadata builders must live in subtitle adapter modules, not the main pipeline script."
Assert-True ($pipelineText -match 'Invoke-ParkPendingPushWithTx3gSidecars' -and $pipelineText -match 'SidecarFiles' -and $pipelineText -match 'Publish-PendingSidecarFiles') "Pending-push parking must carry tx3g SRT sidecars through deferred/retry publish."
Assert-True ($pendingPushText -match 'function Invoke-ParkPendingPushWithTx3gSidecars' -and $pendingPushText -match 'function Invoke-ParkPendingPush' -and $pendingPushText -match 'RoutePlanMetadata' -and $pendingPushText -match 'function Invoke-RetryPendingPushes' -and $pendingPushText -match 'Invoke-PendingDrainTransaction' -and $pendingPushText -notmatch 'function Publish-PendingSidecarFiles' -and $mainText -notmatch 'function Invoke-ParkPendingPushWithTx3gSidecars') "Pending publish public park/drain APIs must live in Modules\\PendingPush.ps1, while sidecar copy and drain transaction mechanics stay out of the wrapper."
Assert-True ($pendingManifestStoreText -match 'function Read-PendingManifestFile' -and $pendingManifestStoreText -match 'function Write-PendingManifestFile' -and $pendingManifestStoreText -match 'function Update-PendingManifestRetryState' -and $pendingPushText -notmatch 'function Write-PendingManifestFile' -and $mainText -match 'PendingManifestStore\.ps1') "Pending manifest read/write/validation/retry-state helpers must live in ops\pipeline\engine\\publish\\pending_manifest_store.ps1 behind the PendingManifestStore.ps1 shim and load before PendingPush.ps1."
Assert-True ($pendingTransactionsText -match 'function Invoke-PendingParkTransaction' -and $pendingTransactionsText -match 'function New-PendingParkManifest' -and $pendingTransactionsText -match "manifest_state\s+=\s+'pending_move'" -and $pendingPushText -notmatch 'function New-PendingParkManifest' -and $mainText -match 'PendingTransactions\.ps1') "Pending publish park transactions must live in Modules\\PendingTransactions.ps1 and load between manifest storage and the pending-push wrapper."
Assert-True ($pendingTransactionsText -match 'function Invoke-PendingDrainTransaction' -and $pendingTransactionsText -match 'function Test-PendingPublishedServerCopy' -and $pendingTransactionsText -match 'function Publish-PendingSidecarFiles' -and $pendingTransactionsText -match 'function Repair-PendingManifestState' -and $pendingTransactionsText -match 'function Remove-PendingDrainLocalArtifacts' -and $pendingPushText -notmatch 'function Invoke-PendingDrainTransaction' -and $pendingPushText -notmatch 'function Test-PendingPublishedServerCopy' -and $pendingPushText -notmatch 'function Repair-PendingManifestState') "Pending publish drain/retry transaction, validation, sidecar publish, and crash-recovery helpers must live in Modules\\PendingTransactions.ps1, not the public PendingPush wrapper."
Assert-True (@($pendingManifestJsonSchemaModel.properties.manifest_state.enum) -contains 'parked_recovered' -and @($pendingManifestJsonSchemaModel.properties.manifest_state.enum) -contains 'retry_sidecar_failed' -and $pendingPublishContractText -match 'PENDING_PUSH_MANIFEST_STATES' -and $pendingPublishContractText -match 'parked_recovered' -and $pendingPublishContractText -match 'retry_sidecar_failed' -and $servicePendingPublishManifestText -match 'PendingPushManifest\.from_mapping' -and $servicePendingPublishManifestText -match 'invalid_contract') "Pending publish manifest states must stay aligned across PowerShell writers, JSON schema, Python contracts, and desktop manifest inventory."
Assert-True ($pendingPublishIndexText -match 'function Refresh-PendingPublishIndex' -and $pendingPublishIndexText -match 'function Test-PendingPublishMatch' -and $pendingPublishIndexText -match 'function Get-PendingPublishHealthReport' -and $pendingPushText -notmatch 'function Refresh-PendingPublishIndex' -and $mainText -match 'PendingPublishIndex\.ps1') "Pending publish indexing, health reporting, and duplicate-detection must live in ops\pipeline\engine\\publish\\pending_publish_index.ps1 behind the PendingPublishIndex.ps1 shim."
Assert-True ($pipelineText -match 'Get-PendingSidecarEntries' -and $pipelineText -match 'Update-PendingManifestTx3gFailures' -and $pipelineText -match 'pending-tx3g-sidecar') "Pending tx3g sidecar drain must be backward-compatible and persist/classify sidecar publish failures."
Assert-True ($publishCompletionText -match 'function Complete-PipelineOutputPublish' -and $mainText -notmatch 'function Complete-PipelineOutputPublish' -and $mainText -match 'PublishCompletion\.ps1' -and $mainText -match 'Complete-PipelineOutputPublish') "Remux and encode publish completion must flow through Modules\\PublishCompletion.ps1."
Assert-True ($mediaProbeText -match 'function Write-OutputSummary' -and $mediaProbeText -match 'output-summary-probe' -and $mainText -notmatch 'function Write-OutputSummary') "Output summary probing must live in Modules\\MediaProbe.ps1, not the main pipeline script."
Assert-True ($mediaProbeText -match 'function Write-PlexCompatibilityReport' -and $mediaProbeText -match 'plex-compatibility-probe' -and $mainText -notmatch 'function Write-PlexCompatibilityReport') "Plex compatibility probing must live in Modules\\MediaProbe.ps1, not the main pipeline script."
Assert-True ($regressionText -match 'legacy manifest without sidecar_files did not drain' -and $regressionText -match 'partial sidecar park removed original temp sidecars' -and $regressionText -match 'missing parked sidecar failure was not persisted to manifest' -and $regressionText -match 'reveal failure should leave parked media, sidecar, and manifest' -and $regressionText -match 'network copy failure should leave parked media and manifest' -and $regressionText -match 'output destination full should park without failure' -and $regressionText -match 'output destination unknown should park without failure') "Regression checks must cover old pending manifests, transactional sidecar park, missing parked sidecars, media-reveal rollback, network-copy retry loops, and output-space/unknown-space parking."
Assert-True ($pipelineText -match 'SUBTITLE_TX3G_UNKNOWN_FAILURE' -and $pipelineText -match 'failure reported without details') "TX3G failure reporting must tolerate empty failure lists."
Assert-True ($subtitleCommonText -match 'function Register-Tx3gSubtitleFailure' -and $subtitleCommonText -match 'function Register-SubtitleExtractionFailure' -and $subtitleCommonText -match 'function Get-SubtitleFailureText' -and $mainText -notmatch 'function Register-(Tx3gSubtitleFailure|SubtitleExtractionFailure)' -and $mainText -notmatch 'function Get-SubtitleFailure') "Subtitle failure registration and tolerant failure parsing must live in Modules\\Subtitles.Common.ps1."
Assert-True ($pipelineText -match 'SubtitleExtractTimeoutSeconds' -and $pipelineText -match 'SubtitleProbeTimeoutSeconds' -and $configSchemaModuleText -match 'SubtitleExtractTimeoutSeconds\s+=\s+180' -and $configSchemaText -match 'Subtitle Probe Timeout') "Subtitle extraction/probe timeouts must be named config settings."
Assert-True ($pipelineText -match 'SUBTITLE_TX3G_EXTRACT_FAILED' -and $pipelineText -match 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED') "TX3G extraction and sidecar publish failures must be classified."
Assert-True ($pipelineText -match 'SUBTITLE_BDPGS_SUP_EXTRACT_FAILED' -and $pipelineText -match 'SUBTITLE_BDPGS_OCR_TOOL_MISSING' -and $pipelineText -match 'Register-SubtitleExtractionFailure') "BDPGS SUP extraction/OCR failures must be classified."
Assert-True ($subtitleBuildersText -match 'SUBTITLE_TX3G_CONTAINER_UNSUPPORTED' -and $subtitleBuildersText -match 'SUBTITLE_BDPGS_CONTAINER_UNSUPPORTED' -and $subtitleBuildersText -match 'SUBTITLE FAILURE') "Container-incompatible kept subtitles must be failure records, not warning-only drops."
Assert-True ($toolIntegrationText -match 'Hello BDPGS integration' -and $toolIntegrationText -match 'SUBTITLE_BDPGS_OCR_TOOL_MISSING' -and $toolIntegrationText -match 'Convert-BdpgsToSrt') "Tool integration checks must cover BDPGS OCR success and missing-tool conversion paths."
Assert-True ($endToEndSmokeText -match 'Smoke\.Movie\.2026' -and $endToEndSmokeText -match 'Smoke\.Show\.S01E02' -and $endToEndSmokeText -match 'Audio\.Transcode\.2026' -and $endToEndSmokeText -match 'DeferredPublish' -and $endToEndSmokeText -match 'DrainPendingPushes' -and $endToEndSmokeText -match 'Invoke-RerunCsv\.ps1' -and $endToEndSmokeText -match 'Test-ShouldRetryEncodeWithCpuFallback' -and $endToEndSmokeText -match 'eac3') "End-to-end smoke checks must cover movie remux, TV episode planning, audio transcode, GPU fallback policy, CSV rerun dry-run, and deferred publish drain."
Assert-True ($pipelineText -match 'SUBTITLE_ASS_CONVERT_FAILED' -and $pipelineText -match 'New-AssFailureRecord' -and $pipelineText -match 'ASS subtitle conversion failed') "ASS conversion failures must be structured and classified instead of silently dropping converted subtitles."
Assert-True ($auditText -match 'Test-AuditTx3gSubtitleStream' -and $auditText -match 'tx3g-only-subtitles' -and $auditText -match 'tx3g-subtitles-extractable' -and $auditText -match 'tx3g-extraction-failed' -and $auditText -match 'Tx3gExternalSrtFiles' -and $auditText -match 'Get-AuditTx3gGenericSrtSuffixes' -and $auditText -match 'Test-AuditSrtFileUsable') "Audit must report tx3g-only, extractable, failed, and matching usable external SRT cases without broad Base*.srt matching."
Assert-True ($auditText -match 'Test-AuditBdpgsSubtitleStream' -and $auditText -match 'bdpgs-only-subtitles' -and $auditText -match 'bdpgs-subtitles-ocr-candidate' -and $auditText -match 'bdpgs-ocr-failed' -and $auditText -match 'BdpgsSubtitleCount') "Audit must report BDPGS-only, OCR-candidate, failed, and count metadata."
Assert-True ($auditText -match 'Test-AuditTx3gSidecarSrtRecordUsable' -and $auditText -match 'Get-AuditValidatedEmbeddedSrtRecordCount' -and $auditText -match 'tx3g-srt-sidecar-stale' -and $auditText -match 'bdpgs-embedded-srt-stale') "Audit subtitle success must be based on usable generated SRT output or matched embedded text streams, not filename/sidecar record existence alone."
Assert-True ($pipelineText -notmatch '\[System\.IO\.File\]::Replace\(\$tmp,\s*\$ProgressFile,\s*\$null' -and $pipelineText -match '\[System\.IO\.File\]::Replace\(\$tmp,\s*\$ProgressFile,\s*\$backup,\s*\$true\)') "Pipeline progress replace must use a real backup path, not null."
Assert-True ($subtitleText -match '--ffmpeg-bin' -and $subtitleText -match '--extract-timeout-seconds' -and $subtitleText -match '--keep-formatting') "Subtitle converter must accept ffmpeg, timeout, and formatting-control CLI options."
Assert-True ($configSchemaModuleText -match 'IndexScanTimeoutSeconds\s+=\s+1800' -and $configSchemaModuleText -notmatch 'IndexScanTimeoutSeconds\s+=\s+0') "Shared defaults must not recreate unbounded processed-index scans."
Assert-True ($configSchemaModuleText -match 'TransientFailureRetryLimit\s+=\s+3') "Shared defaults must include transient failure retry limit."
Assert-True ($configSchemaModuleText -match 'AggressiveEpisodeParsing\s+=\s+\$false') "Shared defaults must include aggressive episode parsing in strict-off mode."
Assert-True ($configSchemaModuleText -match 'ConvertTx3gToSrt\s+=\s+\$true' -and $configSchemaModuleText -match 'DropTx3gAfterConversion\s+=\s+\$false' -and $configSchemaModuleText -match 'CreateExternalTx3gSrtSidecars\s+=\s+\$false' -and $configSchemaModuleText -match "Tx3gExtractLanguages\s+=\s+@\('eng','en','und'\)" -and $configSchemaModuleText -match 'Tx3gPreserveExistingSrt\s+=\s+\$true') "Shared defaults must enable embedded tx3g conversion, preserve originals when safe, and keep external SRT sidecars opt-in."
Assert-True ($configSchemaModuleText -match 'ConvertBdpgsToSrt\s+=\s+\$false' -and $configSchemaModuleText -match 'DropBdpgsAfterConversion\s+=\s+\$false' -and $configSchemaModuleText -match "BdpgsExtractLanguages\s+=\s+@\('eng','en','und'\)" -and $configSchemaModuleText -match 'BdpgsOcrTimeoutSeconds\s+=\s+1800') "Shared defaults must preserve BDPGS by default and keep OCR opt-in."
Assert-True ($pipelineText -match 'AllowSystemTools' -and $configSchemaModuleText -match 'AllowSystemTools\s+=\s+\$false') "Bundled tools must be required by default with an explicit AllowSystemTools override."
Assert-True (($servicesText + $serviceQueueText + $serviceQueueDryRunText) -match 'Queue plan source:' -and ($servicesText + $serviceQueueText + $serviceQueueDryRunText) -match 'filtered \(already-processed / blocked\)' -and ($servicesText + $serviceQueueText + $completedServiceText) -match 'lstrip\("\\ufeff"\)') "Queue preview health reporting or BOM handling is missing."
Assert-True ($serviceQueueText -match 'app\.queue\.dry_run_runner' -and $serviceQueueText -match 'app\.queue\.preview_builder' -and $serviceQueueText -match 'run_queue_dry_run_for_service' -and $serviceQueueText -match 'build_queue_preview_for_service' -and $serviceQueueDryRunText -match 'def build_queue_dry_run_command' -and $serviceQueueDryRunText -match 'def queue_snapshot_file_is_fresh' -and $serviceQueueDryRunText -match 'Queue plan source:' -and $serviceQueuePreviewBuilderText -match 'format_queue_plan_source_status' -and $serviceQueueDryRunRunnerText -match 'def run_queue_dry_run_for_service' -and $serviceQueueDryRunRunnerText -match 'run_capture' -and $serviceQueueDryRunRunnerText -match '_atomic_write_text') "Queue dry-run command, freshness, status policy, subprocess execution, and snapshot promotion must live in focused helpers behind QueueService compatibility wrappers."
$queueDryRunKillGuard = (
    (($servicesText + $serviceQueueText + $serviceProcessesText + $serviceQueueDryRunRunnerText) -match 'kill_process_tree\(proc, "queue dry-run"\)') -or
    (($serviceQueueText + $serviceQueueDryRunRunnerText) -match 'kill_tree=getattr\(.*"kill_process_tree", None\)' -and $subprocessRunnerText -match 'kill_tree\(proc, label\)')
)
Assert-True (($servicesText + $serviceQueueText + $serviceQueueSnapshotText) -match '_read_queue_snapshot' -and ($servicesText + $serviceQueueText) -match '_run_queue_dry_run' -and ($servicesText + $serviceQueueText + $serviceQueueDryRunText + $serviceQueueDryRunRunnerText) -match '-EmitQueuePlan' -and ($servicesText + $serviceQueueText + $serviceAuditRerunText + $serviceAuditRerunCsvText + $serviceQueueSnapshotText) -match 'source_identity_v2' -and ($servicesText + $serviceQueueText + $serviceQueueDryRunRunnerText) -match 'desktop_queue_preview_request_id' -and ($servicesText + $serviceQueueText + $serviceQueueDryRunRunnerText) -match 'Queue dry-run timed out' -and $queueDryRunKillGuard -and ($appText + $queueControllerText + $queueRefreshControllerText) -match '_queue_refresh_running' -and ($appText + $queueControllerText + $queueRefreshControllerText) -match '(self|app)\.queue_records = \[\]') "Queue preview must be pipeline-snapshot authoritative, preserve source identity metadata, serialize refreshes, and clear stale UI state on dry-run failure."
Assert-True ($serviceQueueText -match 'app\.queue\.snapshot' -and $serviceQueueText -match 'def _queue_record_from_snapshot_row' -and $serviceQueueSnapshotText -match 'QueuePlanSnapshot\.from_mapping' -and $serviceQueueSnapshotText -match 'def queue_record_from_snapshot_row' -and $serviceQueueSnapshotText -match 'def queue_snapshot_is_current_for_request' -and $serviceQueueSnapshotText -match 'def queue_dry_run_tail') "Desktop queue snapshot contract reads, stale dry-run checks, tail formatting, and snapshot-row mapping must live in a focused helper behind QueueService compatibility wrappers."
Assert-True ($serviceQueueText -match 'app\.queue\.preview_builder' -and $serviceQueueText -match 'build_queue_preview_for_service' -and $serviceQueuePreviewBuilderText -match 'def build_queue_preview_for_service' -and $serviceQueuePreviewBuilderText -match 'queue_snapshot_file_is_fresh' -and $serviceQueuePreviewBuilderText -match '_run_queue_dry_run' -and $serviceQueuePreviewBuilderText -match '_queue_record_from_snapshot_row' -and $serviceQueuePreviewBuilderText -match 'format_queue_plan_source_status') "Desktop queue preview assembly, snapshot-vs-dry-run selection, record mapping, and source-status construction must live in a focused helper behind QueueService compatibility wrappers."
Assert-True ($pipelineEngineText -match 'Get-SourceMediaRouteProfile' -and $pipelineEngineText -match 'Get-ActiveMediaRouteHints' -and $pipelineEngineText -match 'route_reason_code' -and $pipelineEngineText -match 'route_decision_trace') "Queue preview route rows must use the same media profile and route hints as processing and expose the route deciding factor."
Assert-True (($appText + $telemetryControllerText) -notmatch 'gpu_history\.clear\(\)' -and ($appText + $telemetryControllerText) -match 'append_history_value\(app\.gpu_history, telemetry\.gpu_encoder_percent\)|_append_history_value\(self\.gpu_history, telemetry\.gpu_encoder_percent\)') "NVENC telemetry gaps must not clear the graph history; the UI should keep a stable zero/held baseline."
Assert-True (
    $servicesText -notmatch 'def _planned_rerun_path_preview' -and
    $servicesText -notmatch 'def _compute_source_identity_v2_for_preview' -and
    $servicesText -notmatch 'import hashlib' -and
    ($servicesText + $serviceAuditRerunText + $serviceAuditRerunMetadataText) -match 'Get-RerunSourceMetadata\.ps1' -and
    ($servicesText + $serviceAuditRerunText) -match 'def _load_rerun_source_metadata' -and
    $rerunText -match 'RerunSourceIdentity\.ps1' -and
    $rerunText -notmatch 'function Get-RerunSourceIdentityV2' -and
    $rerunMetadataText -match 'RerunSourceIdentity\.ps1' -and
    $rerunText -match 'function Resolve-RerunPlans' -and
    $rerunText -match 'function Test-RerunSourceMatchesCsv'
) "Desktop rerun CSV export must preserve the schema without duplicating backend destination planning or source-identity policy."
Assert-True ($priorityMarkersText -match 'def starts_with_priority_marker' -and $priorityMarkersText -match 'def remove_priority_markers_from_name' -and ($servicesText + $serviceQueueText) -match 'from \.priority_markers import remove_priority_markers_from_name, starts_with_priority_marker') "Desktop priority marker parsing must live in the shared priority_markers utility."
Assert-True ($serviceQueueText -match 'app\.queue\.priority_markers' -and $serviceQueueText -match 'def apply_priority_marker' -and $serviceQueuePriorityText -match 'def get_source_priority_info' -and $serviceQueuePriorityText -match 'def apply_priority_marker' -and $serviceQueuePriorityText -match 'os\.utime' -and $serviceQueuePriorityText -match 'Cannot rename because the destination already exists') "Queue priority ranking and file/folder marker rename operations must live in a focused helper behind QueueService compatibility wrappers."
Assert-True ($pipelineText -match 'function New-MediaQueueItem' -and $pipelineText -match 'media_queue_item\.v1' -and $pipelineText -match 'function ConvertTo-MediaQueueItemRecord' -and $pipelineText -match 'function New-MediaQueuePhasePlan' -and $pipelineText -match 'function Get-MediaQueueDiscoveryPlan' -and $rerunText -match 'queue_item') "Priority, movie, TV, and CSV rerun queues must share the versioned media_queue_item contract."
Assert-True ($pipelineEngineText -match 'function New-MediaPipelineEnginePlan' -and $pipelineEngineText -match 'function Invoke-MediaPipelineRound' -and $pipelineEngineText -match 'function Invoke-MediaPipelineRun' -and $pipelineEngineText -match 'function Invoke-MediaPipelineEmitQueuePlan' -and $pipelineEngineText -match 'function Invoke-MediaQueuePhasePlan' -and $mainText -match 'PipelineEngine\.ps1' -and $mainText -match 'New-MediaPipelineEnginePlan' -and $mainText -match 'Invoke-MediaPipelineRun' -and $mainText -match 'Invoke-MediaPipelineEmitQueuePlan' -and $mainText -notmatch 'while\s*\(-not\s+\$script:StopRequested\)[\s\S]{0,5000}Get-MediaQueueDiscoveryPlan') "Pipeline scan, queue snapshot, single-pass, continuous mode, and queue phase execution must flow through the engine helpers."
Assert-True ($mainText -match 'PipelineProcessing\.ps1' -and $pipelineProcessingText -match 'function Invoke-MediaPipelineProcessFile' -and $mainText -match 'function Process-File' -and $mainText -notmatch 'function Invoke-MediaPipelineProcessFile' -and $pipelineEngineText -match 'function Build-QueuePlanSnapshotRows' -and $pipelineEngineText -match 'function Write-QueuePlanSnapshot' -and $mainText -notmatch 'function Build-QueuePlanSnapshotRows' -and $mainText -notmatch 'function Write-QueuePlanSnapshot') "Job processing and queue snapshot helpers must live in reusable modules, with only the legacy Process-File wrapper left in the main script."
Assert-True ($pipelineText -match 'function New-PlexMovieDestinationPlan' -and $pipelineText -match 'function New-PlexDestinationPlan' -and $outputPathPlanningText -match 'function Get-OutputPaths[\s\S]+New-PlexDestinationPlan' -and $mainText -match 'Get-OutputPaths' -and $rerunText -match 'New-PlexDestinationPlan' -and $mainText -notmatch '\$cleanBase\s*=\s*Get-CleanMovieName \$File\.Name' -and $rerunText -notmatch '\$cleanBase\s*=\s*Get-CleanMovieName \$fileInfo\.Name') "Main pipeline and CSV rerun destination paths must flow through the shared Plex destination planner API."
Assert-True ($regressionText -match 'priority queue ordering should put marked files first' -and $regressionText -match 'queue snapshot should expose runnable records' -and $regressionText -match 'missing source root should produce an empty queue preview') "Regression checks must cover queue snapshot loading, priority ordering, and missing source roots."
Assert-True (($servicesText + $serviceFileOpenText + $serviceReleaseText) -match 'list2cmdline') "Desktop launch logging must use Windows-safe command quoting."
Assert-True (($servicesText + $serviceFileOpenText + $serviceFileOpenPlanText) -match '_open_media_with_vlc' -and ($servicesText + $serviceFileOpenText) -match '_normalize_open_path_text' -and ($servicesText + $serviceFileOpenText) -match '_vlc_launch_path_for_media' -and ($servicesText + $serviceFileOpenText + $serviceFileOpenPlanText) -match 'VLC_LONG_PATH_THRESHOLD' -and ($servicesText + $serviceFileOpenText) -match 'mklink' -and ($servicesText + $serviceFileOpenText + $serviceFileOpenPlanText) -match '--no-one-instance-when-started-from-file' -and ($servicesText + $serviceFileOpenText) -match '_strip_windows_extended_path_prefix' -and ($servicesText + $serviceFileOpenText) -match 'MEDIA_FILE_SUFFIXES') "Desktop file opening must avoid handing VLC malformed extended-path file URIs or overlong media paths."
Assert-True ($serviceFileOpenText -match 'app\.files\.open_plan|\.open_plan' -and $serviceFileOpenText -match 'vlc_candidate_paths' -and $serviceFileOpenText -match 'build_vlc_launch_args' -and $serviceFileOpenText -match 'explorer_select_args' -and $serviceFileOpenPlanText -match 'def vlc_needs_short_path' -and $serviceFileOpenPlanText -match 'def vlc_creation_flags') "Desktop file-open VLC discovery, long-path decision, creation flags, and shell argument planning must live in a focused helper while the service keeps OS process launching."
Assert-True ($processSpawnServiceText -match 'launch_cwd_for_roots' -and $processSpawnServiceText -match 'workspace_root if workspace_root\.exists\(\) else app_root' -and $processSpawnServiceText -match '"cwd": str\(launch_cwd\)' -and $serviceProcessesText -match '_iter_bundled_launch_dirs' -and $serviceProcessesText -match '_build_launch_environment') "Desktop launches must use an explicit portable-bundle cwd and bundled-tool PATH prefix."
Assert-True ($serviceProcessesText -match 'app\.processes\.spawn_runner' -and $serviceProcessesText -match 'spawn_process_for_service' -and $serviceProcessSpawnRunnerText -match 'def spawn_process_for_service' -and $serviceProcessSpawnRunnerText -match 'subprocess\.Popen' -and $serviceProcessSpawnRunnerText -match '_write_active_job_launch_record' -and $serviceProcessSpawnRunnerText -match '_verify_spawn_readiness') "Desktop process spawn orchestration must live in a focused app/processes runner behind ProcessLifecycleService compatibility wrappers."
Assert-True ($regressionText -match 'bad ffprobe from PATH' -and $regressionText -match 'Audit should prefer bundled ffprobe even when PATH contains another ffprobe') "Regression checks must exercise bundled Windows-first tool preference with a hostile PATH entry."
Assert-True (($servicesText + $serviceFileOpenText) -match 'Launching VLC media path' -and ($servicesText + $serviceFileOpenText) -match 'list2cmdline\(args\)') "Desktop VLC launches must log their resolved executable, long-path junction status, and command line."
Assert-True (($servicesText + $serviceFileOpenText) -match 'Open path requested' -and ($servicesText + $serviceFileOpenText) -match 'Opening Windows path with shell') "Desktop file opening must log normalized open-path routing and shell fallbacks."
Assert-True (($servicesText + $serviceAppStateText) -match 'schema_version": "desktop_app_state\.v1' -and $regressionText -match 'corrupt app state should fall back to defaults') "Desktop app state must be schema-versioned and have corrupt-state recovery coverage."
Assert-True ($serviceAppStateText -match 'app\.schedule\.grid' -and $serviceAppStateText -match 'evaluate_schedule_helper' -and $serviceAppScheduleText -match 'def normalize_schedule_grid' -and $serviceAppScheduleText -match 'def evaluate_schedule' -and $serviceAppScheduleText -match 'def next_scheduled_stop' -and $serviceAppScheduleText -match 'Schedule: Waiting') "Desktop schedule grid normalization and window evaluation policy must live in a focused helper while app-state service keeps JSON load/save ownership."
Assert-True (($servicesText + $serviceAuditRerunText) -match 'def correlate_audit_record' -and ($servicesText + $serviceAuditRerunText) -match 'def format_audit_correlation' -and ($appText + $auditControllerText + $auditTableControllerText) -match 'Pipeline Correlation' -and $regressionText -match 'audit correlation should count completed and failed matches') "Audit findings must correlate with completed-job history and failure records."
Assert-True (($servicesText + $serviceConfigText + $serviceConfigValidationText + $serviceConfigNumericPolicyText) -match 'validate_int\(values, errors, (KEY_INDEX_SCAN_TIMEOUT_SECONDS|"IndexScanTimeoutSeconds"), "IndexScanTimeoutSeconds", minimum=30') "Desktop validation must reject unbounded index scan timeouts."
Assert-True (($servicesText + $serviceConfigText + $serviceConfigValidationText + $serviceConfigNumericPolicyText) -match 'validate_int\(values, errors, (KEY_TRANSIENT_FAILURE_RETRY_LIMIT|"TransientFailureRetryLimit"), "TransientFailureRetryLimit", minimum=1, maximum=100') "Desktop validation must bound transient failure retry limit."
Assert-True (($servicesText + $serviceStatusText + $serviceStatusProgressText) -match 'is_audit_progress_stale' -and $serviceStatusText -match 'app\.status\.progress' -and $serviceStatusProgressText -match 'def parse_progress_datetime' -and $serviceStatusProgressText -match 'def is_progress_stale' -and $serviceStatusProgressText -match 'def format_audit_progress') "Desktop pipeline/audit stale detection and audit progress formatting must live in a focused helper behind StatusService compatibility wrappers."
Assert-True (($appText + $workGuardControllerText) -match '_active_work_block_message|def active_work_block_message' -and ($appText + $workGuardControllerText) -match '_external_audit_progress_active|def external_audit_progress_active' -and ($appText + $workGuardControllerText) -match 'find_related_pipeline_processes' -and ($appText + $workGuardControllerText) -match 'MediaPipeline process PID\(s\)' -and ($appText + $processLifecycleControllerText) -match 'Publish parked outputs') "Desktop launch overlap guards must block app-owned work, fresh external progress, and lost-handle MediaPipeline processes before starting publish/drain runs."
Assert-True (($appText + $failureControllerText + $failureTableControllerText) -match 'operator_required' -and $configSchemaText -match 'TransientFailureRetryLimit' -and $configSchemaText -match 'AggressiveEpisodeParsing') "Desktop UI must expose operator_required failures, retry-limit config, and aggressive episode parsing config."
Assert-True ($configSchemaText -match 'ConvertTx3gToSrt' -and $configSchemaText -match 'DropTx3gAfterConversion' -and $configSchemaText -match 'CreateExternalTx3gSrtSidecars' -and $configSchemaText -match 'TreatAssSignsSongsAsForced' -and $configSchemaText -match 'TreatTx3gSignsSongsAsForced' -and ($servicesText + $serviceConstantsText) -match 'Tx3gPreserveExistingSrt' -and ($servicesText + $serviceConstantsText) -match 'Tx3gTreatForcedAsSeparate') "Desktop settings must expose tx3g extraction, external sidecar, preservation, and signs/songs forced controls."
Assert-True ($configSchemaText -match 'ConvertBdpgsToSrt' -and $configSchemaText -match 'DropBdpgsAfterConversion' -and $configSchemaText -match 'BdpgsOcrToolPath' -and $configSchemaText -match 'TreatBdpgsSignsSongsAsForced' -and ($servicesText + $serviceConstantsText) -match 'BdpgsOcrTimeoutSeconds') "Desktop settings must expose BDPGS OCR, preservation, OCR tool, timeout, and signs/songs forced controls."
Assert-True ($configSchemaText -match '"section": "Shared Subtitle Policy"' -and $configSchemaText -match '"section": "ASS / SSA Subtitles"' -and $configSchemaText -match '"section": "TX3G Subtitles"' -and $configSchemaText -match '"section": "BDPGS Subtitles"' -and $configSchemaText -notmatch '"section": "Subtitle Logic"' -and $configSchemaText -notmatch '"section": "ASS Filters"') "Desktop subtitle settings must separate shared, ASS/SSA, TX3G, and BDPGS controls instead of mixing them under generic legacy sections."
Assert-True ($libraryViewText -match 'Clear Failure Errors' -and $homeViewText -match 'Clear Failure Errors') "Clear Failure Errors buttons must be visible in the failures workspace and home recovery card."
Assert-True ($homeViewText -match 'Publish Parked Outputs' -and $homeViewText -match '_build_status_strip' -and $homeViewText -notmatch 'self\.audit_card') "Home dashboard must keep parked-output publishing visible and remove the oversized audit card."
Assert-True ($homeViewText -match 'Parked Outputs' -and $appText -match '_queue_preview_health_text' -and $servicesText -match '_queue_source_candidates') "Home dashboard must summarize parked outputs and label queue preview cache health."
Assert-True (($appText + $workGuardControllerText) -match '_failure_clear_block_message|def failure_clear_block_message' -and ($appText + $workGuardControllerText) -match 'Clear failures allowed while app-owned process handle exists because progress is idle or stale') "Clear failures must not be blocked by idle or stale app-owned process handles."
Assert-True (($servicesText + $serviceFailureCleanupText + $serviceConstantsText) -match 'FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION' -and ($servicesText + $serviceFailureCleanupText) -match 'def _failure_workspace_roots' -and ($servicesText + $serviceFailureCleanupText) -match 'def _validate_failure_cleanup_folder' -and ($servicesText + $serviceFailureCleanupText) -match 'def _write_failure_clear_manifest' -and ($servicesText + $serviceFailureCleanupText) -match 'dry_run' -and ($appText + $failureControllerText) -match 'Clear manifest') "Clear Failure Workspace must enforce path containment and write a clear manifest."
Assert-True ($runtimeArtifactServiceText -match 'def _runtime_artifact_specs' -and $runtimeArtifactServiceText -match 'def validate_runtime_artifact_target' -and $runtimeArtifactServiceText -match 'pipeline_progress\.json' -and $runtimeArtifactServiceText -match 'pipeline_pause\.flag' -and $runtimeArtifactServiceText -match 'audit_progress\.json' -and $runtimeArtifactServiceText -match 'legacy pipeline progress') "Runtime artifact cleanup must validate expected state-store and legacy paths before deleting progress or flag files."
Assert-True ($runtimeArtifactServiceText -match 'def prepare_pipeline_runtime_for_launch' -and $runtimeArtifactServiceText -match 'def _clear_pipeline_progress_artifacts' -and ($runtimeArtifactServiceText + $serviceConstantsText) -match 'PIPELINE_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS' -and $runtimeArtifactServiceText -match 'prepare_stale_progress_cleanup' -and $runtimeArtifactServiceText -match 'Cleared stale \{progress_label\} progress before launch' -and $runtimeArtifactServiceText -match 'related MediaPipeline process PID\(s\)' -and $processLifecycleControllerText -match 'prepare_pipeline_runtime_for_launch') "Pipeline launch preparation must clear only stale previous-run progress artifacts after overlap guards pass, while preserving pause/stop/rescan flags and related-process safety."
Assert-True ($runtimeArtifactServiceText -match 'def prepare_audit_runtime_for_launch' -and $runtimeArtifactServiceText -match 'def _clear_audit_progress_artifacts' -and ($runtimeArtifactServiceText + $serviceConstantsText) -match 'AUDIT_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS' -and $runtimeArtifactServiceText -match 'prepare_stale_progress_cleanup' -and $runtimeArtifactServiceText -match 'Stale \{progress_label\} progress was not cleared because related MediaPipeline process PID\(s\)' -and $processLifecycleControllerText -match 'prepare_audit_runtime_for_launch') "Audit launch preparation must clear only stale previous-run audit progress after overlap guards pass, while preserving pipeline runtime state and related-process safety."
Assert-True ($serviceProcessesText -match 'app\.processes\.runtime_runner' -and $serviceProcessesText -match 'prepare_pipeline_runtime_for_service' -and $serviceProcessesText -match 'prepare_audit_runtime_for_service' -and $serviceProcessRuntimeRunnerText -match 'def prepare_pipeline_runtime_for_service' -and $serviceProcessRuntimeRunnerText -match 'clear_pipeline_progress_artifacts_for_service' -and $serviceProcessRuntimeRunnerText -match 'def prepare_audit_runtime_for_service' -and $serviceProcessRuntimeRunnerText -match 'clear_audit_progress_artifacts_for_service' -and $serviceProcessRuntimeRunnerText -match 'prepare_stale_progress_cleanup') "Desktop pipeline/audit runtime cleanup orchestration must live in a focused runner behind ProcessLifecycleService compatibility wrappers."
Assert-True ($serviceConfigText -match 'def validate_config_document_for_save' -and ($serviceConfigText + $serviceConfigDocumentRunnerText) -match 'Import-PowerShellDataFile' -and $serviceConfigText -match 'def _config_backup_path' -and ($appText + $settingsControllerText + $settingsPersistenceControllerText) -match 'config_values=preview\.merged_config' -and ($appText + $settingsControllerText + $settingsPersistenceControllerText) -match 'Config saved and reloaded' -and ($appText + $settingsControllerText + $settingsPersistenceControllerText) -match '(self|app)\.service\.resolve_paths\(' -and $appText -notmatch '_save_config_in_place_core[\s\S]{0,1800}_reload_paths_async') "Config save-in-place and save-copy must validate PSD1 syntax and merged values before atomic writes, and Save In Place must reload the workspace before clearing dirty/start state."
$structuredSettingsControlGate = (
    (($appText + $settingsControllerText) -match 'flags_widget\.configure\(state="normal" if custom_enabled else "disabled"\)') -or
    (
        $settingsControllerText -match 'def _configure_widget_state' -and
        $settingsControllerText -match '_configure_widget_state\(flags_widget, "normal" if custom_enabled else "disabled", "ExtraVideoFlags"\)' -and
        $settingsControllerText -match '_configure_widget_state\(codecs_widget, state, "CompatibleAudioCodecs"\)'
    )
)
Assert-True (
    $configSchemaText -match 'ENCODE_TUNING_PRESET_DESCRIPTIONS' -and
    $configSchemaText -match 'ENCODE_LADDER_DESCRIPTIONS' -and
    $configSchemaText -match 'AUDIO_PASSTHROUGH_PROFILE_DESCRIPTIONS' -and
    $configSchemaText -match '"choice_help": ENCODE_TUNING_PRESET_DESCRIPTIONS' -and
    $configSchemaText -match '"choice_help": ENCODE_LADDER_DESCRIPTIONS' -and
    $configSchemaText -match '"choice_help": AUDIO_PASSTHROUGH_PROFILE_DESCRIPTIONS' -and
    $settingsViewText -match 'choice_help' -and
    $settingsViewText -match 'description_var' -and
    $settingsViewText -match 'refresh_encoding_flag_controls' -and
    $settingsViewText -match 'refresh_audio_passthrough_controls' -and
    $appText -match 'def refresh_encoding_flag_controls' -and
    $appText -match 'def refresh_audio_passthrough_controls' -and
    ($appText + $settingsControllerText) -match 'custom_legacy_flags' -and
    ($appText + $settingsControllerText) -match 'custom_codec_list' -and
    $structuredSettingsControlGate -and
    ($serviceConfigText + $serviceConfigValidationText + $serviceConfigOptionPolicyText) -match 'ExtraVideoFlags are ignored unless EncodeTuningPreset is custom_legacy_flags' -and
    ($serviceConfigText + $serviceConfigValidationText + $serviceConfigOptionPolicyText) -match 'CompatibleAudioCodecs are controlled by AudioPassthroughProfile' -and
    $serviceConfigPreviewText -match 'merged\["ExtraVideoFlags"\] = \[\]'
) "Encoding and audio settings must expose structured descriptions and keep raw escape-hatch fields disabled/reconciled unless custom modes are selected."
Assert-True (($servicesText + $serviceConfigText + $serviceConfigSaveRunnerText + $serviceConstantsText) -match 'PROFILE_NAME_PATTERN' -and $serviceConfigText -match 'def save_config_profile' -and $serviceConfigText -match 'def load_config_profile' -and $serviceConfigText -match 'def normalize_config_path_value' -and $serviceConfigSaveRunnerText -match 'save_config_profile_for_service' -and $serviceConfigSaveRunnerText -match 'load_config_profile_for_service' -and $serviceConfigSaveRunnerText -match 'normalize_config_path_value' -and ($appText + $settingsControllerText + $settingsProfileControllerText) -match 'save_config_profile' -and ($appText + $settingsControllerText + $settingsProfileControllerText) -match 'load_config_profile' -and ($appText + $settingsControllerText) -match 'normalize_config_path_value') "Config profiles and settings path browsing must validate profile names, validate profile content before load, and normalize selected path values behind focused save/profile runners."
$statusServerSafetyText = $appText + $statusServerControllerText + $diagnosticsDrawerViewText
Assert-True ($statusServerSafetyText -match 'Local status server' -and $statusServerSafetyText -match 'ThreadingHTTPServer' -and $statusServerSafetyText -match '\("127\.0\.0\.1", port\)' -and $statusServerSafetyText -match '_redact_status_server_text|def redact_text' -and $statusServerSafetyText -match 'server\.server_close\(\)' -and $statusServerSafetyText -notmatch 'Access-Control-Allow-Origin') "Status server must bind localhost only, redact path-heavy status text, close the socket during shutdown, and avoid broad CORS exposure."
$backfillText = Get-Content -LiteralPath $backfill -Raw
Assert-True ($backfillText -match '\[switch\]\$DryRun' -and $backfillText -match 'completed_manifest_backfill_checkpoint\.v1' -and $backfillText -match 'Write-CompletedManifestAtomic' -and $backfillText -match 'New-BackfillBackupPath' -and ($servicesText + $completedServiceText) -match 'dry_run: bool = False' -and ($servicesText + $completedServiceText) -match 'args\.append\("-DryRun"\)') "Completed manifest backfill must support dry-run checkpoints, unique backups, and atomic manifest replacement."

$pathBoundaryFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Normalize-MediaPipelinePathForBoundary',
    'Test-MediaPipelinePathIsEqualOrChild',
    'Get-MediaPipelineRelativePath',
    'Resolve-SingleFileMediaKind',
    'Get-QueueRelativePath',
    'Get-FolderPolicyFullPath',
    'Test-FolderPolicyPathWithinRoot'
)) -join [Environment]::NewLine
$pathBoundaryCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-path-boundary-' + [guid]::NewGuid().ToString('N'))
try {
    $sourceRoot = Join-Path $root 'Source'
    $siblingRoot = Join-Path $root 'Source2'
    $childDir = Join-Path $sourceRoot 'Show\Season 01'
    New-Item -ItemType Directory -Path $childDir -Force | Out-Null
    New-Item -ItemType Directory -Path $siblingRoot -Force | Out-Null
    $childFile = Join-Path $childDir 'Show - S01E01.mkv'
    $siblingFile = Join-Path $siblingRoot 'Not Under Source.mkv'
    Set-Content -LiteralPath $childFile -Value 'child' -Encoding ASCII
    Set-Content -LiteralPath $siblingFile -Value 'sibling' -Encoding ASCII

    if (-not (Test-MediaPipelinePathIsEqualOrChild -Path $childFile -Root $sourceRoot)) { throw 'child path was not recognized as under root' }
    if (-not (Test-MediaPipelinePathIsEqualOrChild -Path $sourceRoot -Root $sourceRoot)) { throw 'root path was not recognized as equal to itself' }
    if (Test-MediaPipelinePathIsEqualOrChild -Path $siblingFile -Root $sourceRoot) { throw 'sibling prefix path was misclassified as under root' }
    if (-not (Test-FolderPolicyPathWithinRoot -Path $childFile -Root $sourceRoot)) { throw 'folder-policy boundary check rejected child path' }
    if (Test-FolderPolicyPathWithinRoot -Path $siblingFile -Root $sourceRoot) { throw 'folder-policy boundary check accepted sibling-prefix path' }

    $relative = Get-MediaPipelineRelativePath -Path $childFile -Root $sourceRoot
    if ($relative -ne 'Show\Season 01\Show - S01E01.mkv') { throw ('relative path changed: ' + $relative) }
    $queueRelative = Get-QueueRelativePath -FileInfo (Get-Item -LiteralPath $childFile) -RootPath $sourceRoot
    if ($queueRelative -ne 'Show\Season 01\Show - S01E01.mkv') { throw ('queue relative path changed: ' + $queueRelative) }
    $siblingQueueRelative = Get-QueueRelativePath -FileInfo (Get-Item -LiteralPath $siblingFile) -RootPath $sourceRoot
    if ($siblingQueueRelative -ne $siblingFile) { throw ('queue relative path accepted sibling-prefix path: ' + $siblingQueueRelative) }

    $sourceTvRoot = Join-Path $root 'Encode\TV'
    $sourceMoviesRoot = Join-Path $root 'Encode\Movies'
    $tvShowDir = Join-Path $sourceTvRoot '[Anime Time] Trigun (1998)'
    New-Item -ItemType Directory -Path $tvShowDir, $sourceMoviesRoot -Force | Out-Null
    $tvRootBareEpisode = Join-Path $tvShowDir '[Anime Time] Trigun - 002 - Truth of Mistake.mkv'
    $movieRootPatternName = Join-Path $sourceMoviesRoot 'Movie.S01E02.mkv'
    Set-Content -LiteralPath $tvRootBareEpisode -Value 'tv' -Encoding ASCII
    Set-Content -LiteralPath $movieRootPatternName -Value 'movie' -Encoding ASCII

    $tvKind = Resolve-SingleFileMediaKind -Path $tvRootBareEpisode -SourceMovies $sourceMoviesRoot -SourceTV $sourceTvRoot
    if (-not $tvKind.IsTV -or $tvKind.MediaKind -ne 'tv' -or $tvKind.Reason -ne 'source_tv_root') {
        throw ('single-file TV root classification changed: ' + ($tvKind | ConvertTo-Json -Compress))
    }

    $movieKind = Resolve-SingleFileMediaKind -Path $movieRootPatternName -SourceMovies $sourceMoviesRoot -SourceTV $sourceTvRoot
    if ($movieKind.IsTV -or $movieKind.MediaKind -ne 'movie' -or $movieKind.Reason -ne 'source_movies_root') {
        throw ('single-file movie root classification should outrank TV-looking filename: ' + ($movieKind | ConvertTo-Json -Compress))
    }

    $patternKind = Resolve-SingleFileMediaKind -Path (Join-Path $root 'Loose\Show.S01E02.mkv') -SourceMovies $sourceMoviesRoot -SourceTV $sourceTvRoot
    if (-not $patternKind.IsTV -or $patternKind.Reason -ne 'tv_path_pattern') {
        throw ('single-file TV fallback pattern classification changed: ' + ($patternKind | ConvertTo-Json -Compress))
    }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
'@.Replace('__FUNCTIONS__', $pathBoundaryFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $pathBoundaryCheck

foreach ($failureBuilderName in @('New-AssFailureRecord','New-Tx3gFailureRecord','New-BdpgsFailureRecord','New-PendingTx3gPublishFailure','Add-RoundFailureRecord','Write-SourceFailureState')) {
    $failureBuilderText = (Get-FunctionText -Path $pipelineFiles -Names @($failureBuilderName)) -join [Environment]::NewLine
Assert-True ($failureBuilderText -match 'New-StandardFailureRecord') "$failureBuilderName must build records through New-StandardFailureRecord."
}
Assert-True ($failureStateText -notmatch 'return\s+if\s*\(') "Failure suggested-action fallback must not use invalid return-if syntax."
Assert-True ($failureStateText -match 'schema_version\s*=\s*\$standardFailure\.schema_version' -and $failureStateText -match 'category\s*=\s*\$standardFailure\.category' -and $failureStateText -match 'operation\s*=\s*\$standardFailure\.operation') "Persisted source-failure markers must carry the standard failure schema fields."
Assert-True ($failureStateText -match 'function Write-FailureJsonAtomic' -and $failureStateText -match 'Write-RoundFailureSummary[\s\S]+Write-FailureJsonAtomic' -and $failureStateText -match 'Write-SourceFailureState[\s\S]+Write-FailureJsonAtomic') "Failure summaries and source-failure markers must use atomic validated JSON writes."

$rerunDryRunRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-rerun-regression-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $rerunDryRunRoot -Force | Out-Null
    $rerunSource = Join-Path $rerunDryRunRoot 'Movie Source 1080p HEVC.mkv'
    Set-Content -LiteralPath $rerunSource -Value 'x' -Encoding ASCII
    $unlistedSource = Join-Path $rerunDryRunRoot 'Unlisted Movie 1080p HEVC.mkv'
    Set-Content -LiteralPath $unlistedSource -Value 'x' -Encoding ASCII
    $rerunConfig = Join-Path $rerunDryRunRoot 'config.psd1'
    $escapedRoot = $rerunDryRunRoot.Replace("'", "''")
    @"
@{
    LocalBase = '$escapedRoot\Local'
    Outsource = '$escapedRoot\Out'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
}
"@ | Set-Content -LiteralPath $rerunConfig -Encoding UTF8
    $rerunCsv = Join-Path $rerunDryRunRoot 'rerun.csv'
    $missingRerunSource = Join-Path $rerunDryRunRoot 'missing-listed-source.mkv'
    $metadataInput = Join-Path $rerunDryRunRoot 'metadata-input.json'
    $metadataOutput = Join-Path $rerunDryRunRoot 'metadata-output.json'
    @{
        schema_version = 'rerun_source_metadata_request.v1'
        source_paths = @($rerunSource, $missingRerunSource)
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metadataInput -Encoding UTF8
    & (Get-Command pwsh).Source -NoProfile -ExecutionPolicy Bypass -File $rerunMetadata -InputJsonPath $metadataInput -OutputJsonPath $metadataOutput | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Rerun source metadata helper failed with exit $LASTEXITCODE" }
    $metadataPayload = Get-Content -LiteralPath $metadataOutput -Raw | ConvertFrom-Json
    $metadataRows = @($metadataPayload.rows)
    if ($metadataPayload.schema_version -ne 'rerun_source_metadata.v1' -or $metadataRows.Count -ne 2) { throw 'Rerun source metadata helper wrote an unexpected payload.' }
    $existingMetadata = @($metadataRows | Where-Object { $_.source_path -eq $rerunSource })[0]
    if (-not $existingMetadata.exists -or [string]$existingMetadata.source_size -ne [string]((Get-Item -LiteralPath $rerunSource).Length)) { throw 'Rerun source metadata helper did not report source size.' }
    if (-not ($existingMetadata.PSObject.Properties.Name -contains 'source_identity_v2')) { throw 'Rerun source metadata helper did not expose source identity v2.' }
    if (@($metadataRows | Where-Object { $_.source_path -eq $missingRerunSource -and -not $_.exists -and $_.error }).Count -ne 1) { throw 'Rerun source metadata helper did not report missing sources.' }
    @"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,"$rerunSource",Movie,copy,keep,park
false,"$missingRerunSource",Movie,copy,keep,park
true,"$missingRerunSource",Movie,copy,keep,park
true,"$rerunSource",Movie,copy,keep,park
"@ | Set-Content -LiteralPath $rerunCsv -Encoding UTF8
    & (Get-Command pwsh).Source -NoProfile -ExecutionPolicy Bypass -File $rerun -CsvPath $rerunCsv -ConfigPath $rerunConfig -DryRun -DefaultReturnMode park | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Rerun dry-run check failed with exit $LASTEXITCODE" }
    $manifest = Get-ChildItem -LiteralPath (Join-Path $rerunDryRunRoot 'Local\RerunManifests') -Filter '*.json' -File | Select-Object -First 1
    if (-not $manifest) { throw 'Rerun dry-run did not write a manifest.' }
    $payload = Get-Content -LiteralPath $manifest.FullName -Raw | ConvertFrom-Json
    if ($payload.status -ne 'dry_run_complete') { throw ('Unexpected rerun dry-run status: ' + $payload.status) }
    if (@($payload.rows).Count -ne 3) { throw 'Rerun dry-run manifest should contain only enabled CSV-authoritative rows.' }
    if (@($payload.rows | Where-Object { $_.source_path -eq $unlistedSource }).Count -ne 0) { throw 'Rerun dry-run included a file that was not listed in the CSV.' }
    if (@($payload.rows | Where-Object { $_.source_path -eq $rerunSource -and $_.status -eq 'pending' }).Count -ne 1) { throw 'Rerun dry-run did not preserve the listed source row.' }
    if (@($payload.rows | Where-Object { $_.source_path -eq $rerunSource -and $_.status -eq 'failed' -and $_.reason -match 'duplicate planned output path in CSV' }).Count -ne 1) { throw 'Rerun dry-run should classify duplicate planned output rows.' }
    if (@($payload.rows | Where-Object { $_.status -eq 'failed' -and $_.reason -match 'source file not found' }).Count -ne 1) { throw 'Rerun dry-run should surface missing enabled source rows.' }
    $pendingRerunRow = @($payload.rows | Where-Object { $_.source_path -eq $rerunSource -and $_.status -eq 'pending' })[0]
    if ($pendingRerunRow.queue_item.schema_version -ne 'media_queue_item.v1' -or $pendingRerunRow.queue_item.queue_source -ne 'csv_rerun' -or $pendingRerunRow.queue_item.media_kind -ne 'movie') { throw 'Rerun dry-run row did not carry the shared queue item record.' }
    if ($pendingRerunRow.queue_item.metadata.stage_path -ne $pendingRerunRow.stage_path -or $pendingRerunRow.queue_item.metadata.planned_output_path -ne $pendingRerunRow.planned_output_path) { throw 'Rerun queue item record did not preserve stage/output planning metadata.' }
} finally {
    Remove-Item -LiteralPath $rerunDryRunRoot -Recurse -Force -ErrorAction SilentlyContinue
}

$progressFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-ControlFlagProperty',
    'Get-ControlFlagInfo',
    'Get-ProgressIsoTimestamp',
    'New-ControlRequestProgressState',
    'Save-Progress'
)) -join [Environment]::NewLine
$progressReplaceCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
`$td = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-progress-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$td -Force | Out-Null
try {
    `$ProgressFile = Join-Path `$td 'pipeline_progress.json'
    Set-Content -LiteralPath `$ProgressFile -Value '{}' -Encoding UTF8
    `$PauseFlag = Join-Path `$td 'pause.flag'
    `$StopFlag = Join-Path `$td 'stop.flag'
    `$RescanFlag = Join-Path `$td 'rescan.flag'
    `$script:ProgressVersion = 2
    `$script:SessionStartedAt = Get-Date
    `$script:currentFile = 'Episode 04.mkv'
    `$script:currentFileDisplay = 'Episode 04.mkv'
    `$script:currentFilePath = 'C:\Media\Episode 04.mkv'
    `$script:currentMediaType = 'tv'
    `$script:currentQueuePhase = 'TV'
    `$script:currentQueueIndex = 4
    `$script:currentQueueTotal = 10
    `$script:currentRoute = 'encode'
    `$script:currentStage = 'encode'
    `$script:currentStagePercent = 12.5
    `$script:currentItemStartedAt = Get-Date
    `$script:currentStageStartedAt = Get-Date
    `$script:currentCopyState = 'complete'
    `$script:currentPushState = `$null
    `$script:currentSidecarState = `$null
    `$script:StopRequested = `$false
    `$script:totalProcessed = 3
    `$script:totalEncoded = 1
    `$script:totalRemuxed = 2
    `$script:totalFailed = 0
    `$script:totalMovies = 0
    `$script:totalTVEpisodes = 3
    `$script:pipelineStatus = 'Processing'
$progressFunctions
    if (-not (Save-Progress 'Processing')) { throw 'Save-Progress returned false' }
    `$saved = Get-Content -LiteralPath `$ProgressFile -Raw | ConvertFrom-Json
    if (`$saved.CurrentFileDisplay -ne 'Episode 04.mkv') { throw 'progress current file was not persisted' }
    if (`$saved.CurrentStage -ne 'encode') { throw 'progress stage was not persisted' }
    if (`$null -eq `$saved.ControlRequests -or `$saved.ControlRequests.Pause.Requested) { throw 'progress control request state was not persisted correctly' }
    if ((Get-ChildItem -LiteralPath `$td -Filter '*.bak' -ErrorAction SilentlyContinue).Count -ne 0) { throw 'progress backup was not cleaned up' }
} finally {
    Remove-Item -LiteralPath `$td -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $progressReplaceCheck

$controlFlagFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-ControlFlagProperty',
    'Get-ControlFlagInfo',
    'Get-ProgressIsoTimestamp',
    'Register-ControlFlagObservation',
    'New-ControlRequestProgressState',
    'Save-Progress',
    'Check-ControlFlags',
    'Consume-RescanFlag'
)) -join [Environment]::NewLine
$controlFlagCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function Set-ProgressStage {
    param([string]`$Stage, [string]`$Status, `$Percent, [switch]`$SaveNow)
    `$script:currentStage = `$Stage
    `$script:pipelineStatus = `$Status
    if (`$SaveNow) {
        if (-not (Save-Progress `$Status)) { throw 'Set-ProgressStage failed to save progress' }
    }
}
`$td = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-control-flags-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$td -Force | Out-Null
try {
    `$ProgressFile = Join-Path `$td 'pipeline_progress.json'
    `$PauseFlag = Join-Path `$td 'pause.flag'
    `$StopFlag = Join-Path `$td 'stop.flag'
    `$RescanFlag = Join-Path `$td 'rescan.flag'
    `$script:ProgressVersion = 2
    `$script:SessionStartedAt = Get-Date
    `$script:currentFile = 'None'
    `$script:currentFileDisplay = `$null
    `$script:currentFilePath = `$null
    `$script:currentMediaType = `$null
    `$script:currentQueuePhase = `$null
    `$script:currentQueueIndex = 0
    `$script:currentQueueTotal = 0
    `$script:currentRoute = `$null
    `$script:currentStage = 'processing'
    `$script:currentStagePercent = `$null
    `$script:currentItemStartedAt = `$null
    `$script:currentStageStartedAt = Get-Date
    `$script:currentCopyState = `$null
    `$script:currentPushState = `$null
    `$script:currentSidecarState = `$null
    `$script:StopRequested = `$false
    `$script:LastPauseRequestId = `$null
    `$script:LastPauseRequestCreatedAt = `$null
    `$script:LastPauseRequestObservedAt = `$null
    `$script:LastStopRequestId = `$null
    `$script:LastStopRequestCreatedAt = `$null
    `$script:LastStopRequestObservedAt = `$null
    `$script:LastRescanRequestId = `$null
    `$script:LastRescanRequestCreatedAt = `$null
    `$script:LastRescanRequestObservedAt = `$null
    `$script:totalProcessed = 0
    `$script:totalEncoded = 0
    `$script:totalRemuxed = 0
    `$script:totalFailed = 0
    `$script:totalMovies = 0
    `$script:totalTVEpisodes = 0
    `$script:pipelineStatus = 'Processing'
$controlFlagFunctions
    Set-Content -LiteralPath `$StopFlag -Encoding UTF8 -Value '{"schema_version":"pipeline_control_flag.v1","action":"stop","label":"Stop","request_id":"stop-1","created_at":"2026-05-01T08:00:00-04:00"}'
    Check-ControlFlags
    if (-not `$script:StopRequested) { throw 'stop flag did not set StopRequested' }
    `$saved = Get-Content -LiteralPath `$ProgressFile -Raw | ConvertFrom-Json
    if (-not `$saved.StopRequested) { throw 'stop request was not persisted' }
    if (`$saved.ControlRequests.Stop.LastObservedRequestId -ne 'stop-1') { throw 'stop request id was not observed in progress JSON' }

    Remove-Item -LiteralPath `$StopFlag -Force
    `$script:StopRequested = `$false
    Set-Content -LiteralPath `$RescanFlag -Encoding UTF8 -Value '{"schema_version":"pipeline_control_flag.v1","action":"rescan","label":"Rescan","request_id":"rescan-1","created_at":"2026-05-01T08:01:00-04:00"}'
    if (-not (Consume-RescanFlag)) { throw 'rescan flag was not consumed' }
    if (Test-Path -LiteralPath `$RescanFlag) { throw 'rescan flag was not removed after consumption' }
    if (-not (Save-Progress 'After rescan')) { throw 'Save-Progress after rescan returned false' }
    `$saved = Get-Content -LiteralPath `$ProgressFile -Raw | ConvertFrom-Json
    if (`$saved.ControlRequests.Rescan.LastObservedRequestId -ne 'rescan-1') { throw 'rescan request id was not observed in progress JSON' }

    Set-Content -LiteralPath `$PauseFlag -Encoding UTF8 -Value ''
    `$legacyPause = Get-ControlFlagInfo -Path `$PauseFlag
    if (-not `$legacyPause.Exists -or `$legacyPause.RawValid) { throw 'legacy empty pause flag should still be treated as an existing control flag' }
} finally {
    Remove-Item -LiteralPath `$td -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $controlFlagCheck

$eventLoggingFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'ConvertTo-PipelineEventData',
    'Write-JsonLineAppend',
    'Write-PipelineEvent'
)) -join [Environment]::NewLine
$eventLoggingCheck = @"
`$ErrorActionPreference = 'Stop'
$eventLoggingFunctions
`$td = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-events-' + [guid]::NewGuid().ToString('N'))
`$script:PipelineEventLogFile = Join-Path `$td 'pipeline_events.jsonl'
`$script:PipelineRunId = 'run-test'
`$script:CurrentJobId = 'job-test'
`$script:ProductVersion = 'v4.000-test'
`$script:PipelineVersion = 'test-version'
`$logLock = [System.Threading.Mutex]::new(`$false, 'MediaPipelineEventTest_' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path `$td -Force | Out-Null
    if (-not (Write-PipelineEvent -EventType 'job_started' -Stage 'processing' -Status 'started' -SourcePath 'source.mkv' -Route 'encode' -Data @{ media_type = 'movie'; queue_index = 1 })) { throw 'Write-PipelineEvent returned false' }
    if (-not (Write-PipelineEvent -EventType 'tool_completed' -Stage 'encode' -Status 'succeeded' -Data ([pscustomobject]@{ tool_name = 'ffmpeg'; exit_code = 0 }))) { throw 'Write-PipelineEvent returned false for object data' }
    `$lines = @(Get-Content -LiteralPath `$script:PipelineEventLogFile)
    if (`$lines.Count -ne 2) { throw ('expected 2 event lines, got ' + `$lines.Count) }
    `$first = `$lines[0] | ConvertFrom-Json
    if (`$first.schema_version -ne 'pipeline_event.v1') { throw 'event schema version was not written' }
    if (`$first.event_type -ne 'job_started') { throw 'event_type was not written' }
    if ([string]::IsNullOrWhiteSpace([string]`$first.created_at)) { throw 'event created_at was not written' }
    if (`$first.run_id -ne 'run-test') { throw 'run_id was not written' }
    if (`$first.correlation_id -ne 'run-test') { throw 'correlation_id was not written' }
    if (`$first.job_id -ne 'job-test') { throw 'job_id was not written from current job context' }
    if (`$first.product_version -ne 'v4.000-test') { throw 'product_version was not written' }
    if (`$first.pipeline_version -ne 'test-version') { throw 'pipeline_version was not written' }
    if (`$first.source_path -ne 'source.mkv') { throw 'source_path was not written' }
    if (`$first.data.media_type -ne 'movie' -or [int]`$first.data.queue_index -ne 1) { throw 'hashtable data did not round-trip' }
    `$second = `$lines[1] | ConvertFrom-Json
    if (`$second.data.tool_name -ne 'ffmpeg' -or [int]`$second.data.exit_code -ne 0) { throw 'object data did not round-trip' }
} finally {
    `$logLock.Dispose()
    Remove-Item -LiteralPath `$td -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $eventLoggingCheck

$queuePlanFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'New-MediaQueueItem',
    'ConvertTo-MediaQueueItemRecord',
    'Set-QueueEntryRuntimeMetadata',
    'Copy-QueueEntriesForLegacyPriorityPhase',
    'Get-PriorityManifest',
    'Get-ManifestEntryField',
    'Get-EffectiveQueueStrategy',
    'Invoke-QueueStrategySort',
    'New-MediaQueuePhasePlan',
    'Get-MediaQueueDiscoveryPlan'
)) -join [Environment]::NewLine
$queuePlanCheck = @"
`$ErrorActionPreference = 'Stop'
$queuePlanFunctions
function New-TestQueueEntry {
    param([string]`$Name, [bool]`$IsPriority, [bool]`$IsTV = `$false)
    `$kind = if (`$IsTV) { 'tv' } else { 'movie' }
    return New-MediaQueueItem -File ([pscustomobject]@{ Name = `$Name; FullName = "C:\Queue\`$Name"; LastWriteTimeUtc = [datetime]'2026-01-01T00:00:00Z' }) -MediaKind `$kind -QueueSource 'discovery' -SortName ([System.IO.Path]::GetFileNameWithoutExtension(`$Name)) -ShowSortKey ([System.IO.Path]::GetFileNameWithoutExtension(`$Name)) -PriorityInfo ([pscustomobject]@{ IsPriority = `$IsPriority; PriorityOrderTicks = if (`$IsPriority) { 100L } else { 0L } })
}
`$moviePriority = New-TestQueueEntry '!Movie A.mkv' `$true
`$movieNormal   = New-TestQueueEntry 'Movie B.mkv' `$false
`$tvNormal      = New-TestQueueEntry 'Show - S01E01.mkv' `$false
`$tvPriority    = New-TestQueueEntry '!Show - S01E02.mkv' `$true `$true
`$plan = New-MediaQueuePhasePlan -MovieEntries @(`$moviePriority, `$null, `$movieNormal) -TVEntries @(`$tvNormal, `$tvPriority)
if ([int]`$plan.MovieCount -ne 2 -or [int]`$plan.TVCount -ne 2) { throw 'queue phase plan should count valid movie and TV entries only' }
if ([int]`$plan.MoviePriorityCount -ne 1 -or [int]`$plan.TVPriorityCount -ne 1) { throw 'queue phase plan priority counts are wrong' }
if ((@(`$plan.PriorityEntries).File.Name -join '|') -ne '!Movie A.mkv|!Show - S01E02.mkv') { throw 'queue phase plan should keep priority movies ahead of priority TV' }
if ([int]`$plan.PriorityEntries[0].QueueIndex -ne 1 -or [int]`$plan.PriorityEntries[0].QueueTotal -ne 2 -or [bool]`$plan.PriorityEntries[0].IsTV) { throw 'priority movie queue metadata changed' }
if ([int]`$plan.PriorityEntries[1].QueueIndex -ne 2 -or [int]`$plan.PriorityEntries[1].QueueTotal -ne 2 -or -not [bool]`$plan.PriorityEntries[1].IsTV) { throw 'priority TV queue metadata changed' }
if (`$plan.PriorityEntries[0].QueueItemType -ne 'media_queue_item.v1' -or `$plan.PriorityEntries[0].QueuePhase -ne 'priority') { throw 'priority queue item contract changed' }
if ((@(`$plan.NormalMovieEntries).File.Name -join '|') -ne 'Movie B.mkv') { throw 'normal movie phase changed' }
if ((@(`$plan.NormalTVEntries).File.Name -join '|') -ne 'Show - S01E01.mkv') { throw 'normal TV phase changed' }
`$record = ConvertTo-MediaQueueItemRecord `$plan.NormalMovieEntries[0]
if (`$record.schema_version -ne 'media_queue_item.v1' -or `$record.media_kind -ne 'movie') { throw 'queue item record conversion changed' }

`$script:CacheCalls = @()
function Get-CachedSourceFiles {
    param([string]`$Kind, [string]`$Path, [bool]`$ForceRefresh = `$false)
    `$script:CacheCalls += ,([pscustomobject]@{ Kind = `$Kind; Path = `$Path; ForceRefresh = `$ForceRefresh })
    if (`$Kind -eq 'movies') { return @([pscustomobject]@{ Name = '!Movie A.mkv'; FullName = 'C:\Movies\!Movie A.mkv'; LastWriteTimeUtc = [datetime]'2026-01-01T00:00:00Z' }) }
    return @([pscustomobject]@{ Name = 'Show - S01E01.mkv'; FullName = 'C:\TV\Show - S01E01.mkv'; LastWriteTimeUtc = [datetime]'2026-01-01T00:00:00Z' })
}
function Get-QueuedEntries {
    param([array]`$Files, [string]`$RootPath, [switch]`$IsTV)
    `$mediaKind = if (`$IsTV) { 'tv' } else { 'movie' }
    return @(
        `$Files | ForEach-Object {
            New-MediaQueueItem -File `$_ -MediaKind `$mediaKind -QueueSource 'discovery' -RootPath `$RootPath -SortName ([System.IO.Path]::GetFileNameWithoutExtension(`$_.Name)) -ShowSortKey ([System.IO.Path]::GetFileNameWithoutExtension(`$_.Name)) -PriorityInfo ([pscustomobject]@{ IsPriority = `$_.Name.StartsWith('!'); PriorityOrderTicks = if (`$_.Name.StartsWith('!')) { 100L } else { 0L } })
        }
    )
}
`$discovered = Get-MediaQueueDiscoveryPlan -MovieRoot 'C:\Movies' -TVRoot 'C:\TV' -ForceRefresh:`$true
if ([int]`$discovered.MovieCount -ne 1 -or [int]`$discovered.TVCount -ne 1) { throw 'queue discovery should build movie and TV entries' }
if (`$script:CacheCalls.Count -ne 2 -or `$script:CacheCalls[0].Kind -ne 'movies' -or `$script:CacheCalls[1].Kind -ne 'tv') { throw 'queue discovery should scan movies then TV through cached source files' }
if (-not `$script:CacheCalls[0].ForceRefresh -or -not `$script:CacheCalls[1].ForceRefresh) { throw 'queue discovery should pass rescan force refresh to both source caches' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $queuePlanCheck

$queueSnapshotFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Write-QueuePlanSnapshot'
)) -join [Environment]::NewLine
$queueSnapshotCheck = @"
`$ErrorActionPreference = 'Stop'
$queueSnapshotFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-queue-snapshot-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$path = Join-Path `$root 'queue_snapshot.json'
    Write-QueuePlanSnapshot -Plan ([pscustomobject]@{ schema_version = 'queue_plan_snapshot.v1'; runnable_count = 1; rows = @() }) -Path `$path
    `$payload = Get-Content -LiteralPath `$path -Raw | ConvertFrom-Json
    if ([int]`$payload.runnable_count -ne 1) { throw 'queue snapshot first write did not round-trip' }
    if (Test-Path -LiteralPath "`$path.tmp" -ErrorAction SilentlyContinue) { throw 'queue snapshot used fixed temp path' }
    if (@(Get-ChildItem -LiteralPath `$root -Filter '*.tmp' -Force -ErrorAction SilentlyContinue).Count -ne 0) { throw 'queue snapshot write left temp files' }

    Write-QueuePlanSnapshot -Plan ([pscustomobject]@{ schema_version = 'queue_plan_snapshot.v1'; runnable_count = 2; rows = @() }) -Path `$path
    `$updated = Get-Content -LiteralPath `$path -Raw | ConvertFrom-Json
    if ([int]`$updated.runnable_count -ne 2) { throw 'queue snapshot replace did not publish updated payload' }
    if (@(Get-ChildItem -LiteralPath `$root -Filter '*.bak' -Force -ErrorAction SilentlyContinue).Count -ne 0) { throw 'queue snapshot replace left backup files' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $queueSnapshotCheck

$queueSnapshotRowsFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-QueuePlanPreflightBlock',
    'Build-QueuePlanSnapshotRows'
)) -join [Environment]::NewLine
$queueSnapshotRowsCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__

$script:PriorityMarkers = @()
$script:NvencAvailableProbe = $null
$configPath = 'config.psd1'
$LocalBase = 'local'
$SourceMovies = 'movies'
$SourceTV = 'tv'
$Outsource = 'out'
$ValidExtensions = @('.mkv')
$script:TvInfoCalls = 0

function Get-TVInfoFromFile {
    param($File)
    $script:TvInfoCalls++
    return [pscustomobject]@{
        ShowName = 'Trigun (1998)'
        Season = 1
        Episode = 2
        IsReliable = $true
        ParseError = $null
    }
}
function Get-SourceFailureState { param($File) return $null }
function Already-Processed {
    param($File, [bool]$IsTV, $TvInfo, $ProcessedIndex)
    if ($IsTV -and -not $TvInfo) { throw 'TvInfo missing for TV already-processed check' }
    return $false
}
function Resolve-ShowOverrides { param([string]$ShowName) return $null }
function Resolve-FolderPolicyOverrides { param($SourceFile) return $null }
function Merge-MediaPipelineActiveOverrides { param($Base, $Override) return $Override }
function Get-ActiveMediaRouteHints { return $null }
function Get-SourceMediaRouteProfile { param([string]$FilePath, [long]$FileSizeBytes) return $null }
function Resolve-InitialMediaRoutePlan {
    param($File, [bool]$IsTV, $MediaProfile, $RouteHints)
    return [pscustomobject]@{
        DisplayRoute = 'REMUX (codec check pending)'
        Route = 'remux'
        Reason = 'source size 0.42 GB is within TV threshold; codec probe still required'
        ReasonCode = 'size_within_threshold'
        DecisionTrace = @()
    }
}

$file = [pscustomobject]@{
    Name = '[Anime Time] Trigun - 002 - Truth of Mistake.mkv'
    Extension = '.mkv'
    FullName = '\\SERVER\Encode\TV\[Anime Time] Trigun (1998)\[Anime Time] Trigun - 002 - Truth of Mistake.mkv'
    Length = 448893613L
    LastWriteTimeUtc = [datetime]'2026-05-17T14:00:00Z'
}
$entry = [pscustomobject]@{
    File = $file
    IsTV = $true
    IsPriority = $false
    QueueIndex = 1
    QueueTotal = 1
    PriorityInfo = [pscustomobject]@{ IsPriority = $false; Reasons = @(); PriorityOrderTicks = 0L }
    PriorityOrderTicks = 0L
    SourcePath = $file.FullName
    RootPath = '\\SERVER\Encode\TV'
    RelativePathSort = '[Anime Time] Trigun (1998)\[Anime Time] Trigun - 002 - Truth of Mistake.mkv'
    SortName = '[Anime Time] Trigun - 002 - Truth of Mistake'
    ShowSortKey = 'Trigun (1998)'
    SeasonSortKey = 'Trigun (1998)|S01'
    SeasonSortOrder = 1
    EpisodeSortOrder = 2
    LastWriteUtc = [datetime]'2026-05-17T14:00:00Z'
    MediaKind = 'tv'
    QueuePhase = 'tv'
}
$plan = [pscustomobject]@{
    PriorityEntries = @()
    NormalMovieEntries = @()
    NormalTVEntries = @($entry)
    MovieCount = 0
    TVCount = 1
}

$snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}
if ([int]$snapshot.runnable_count -ne 1) { throw 'TV queue row should remain runnable' }
$row = $snapshot.rows | Select-Object -First 1
if ($null -eq $row) { throw 'TV queue row was missing from snapshot rows' }
if ([string]$row.route_reason_code -ne 'size_within_threshold') { throw ('route preview did not run: ' + [string]$row.route_reason_code) }
if (-not [string]::IsNullOrWhiteSpace([string]$row.blocked_reason)) { throw ('TV queue row was blocked: ' + [string]$row.blocked_reason) }
if ($script:TvInfoCalls -ne 1) { throw ('TV info should be parsed once for queue snapshot row, got ' + $script:TvInfoCalls) }
'@
$queueSnapshotRowsCheck = $queueSnapshotRowsCheck.Replace('__FUNCTIONS__', $queueSnapshotRowsFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $queueSnapshotRowsCheck

$queueEngineFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Invoke-MediaQueuePhasePlan'
)) -join [Environment]::NewLine
$queueEngineCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__
$script:StopRequested = $false
$script:Processed = @()
$script:Logs = @()

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:Logs += ,$Message
}
function Check-ControlFlags {}
function Process-File {
    param($File, [bool]$IsTV, $ProcessedIndex, [int]$QueueIndex = 0, [int]$QueueTotal = 0, $PriorityInfo = $null)
    $script:Processed += ,([pscustomobject]@{
        Name = $File.Name
        IsTV = $IsTV
        QueueIndex = $QueueIndex
        QueueTotal = $QueueTotal
        Priority = [bool]$PriorityInfo.IsPriority
    })
}
function New-TestEntry {
    param([string]$Name, [bool]$IsTV, [bool]$Priority, [int]$Index, [int]$Total)
    return [pscustomobject]@{
        File = [pscustomobject]@{ Name = $Name }
        IsTV = $IsTV
        IsPriority = $Priority
        QueueIndex = $Index
        QueueTotal = $Total
        PriorityInfo = [pscustomobject]@{ IsPriority = $Priority }
    }
}

$plan = [pscustomobject]@{
    PriorityEntries = @(
        (New-TestEntry '!Movie.mkv' $false $true 1 2),
        (New-TestEntry '!Show.mkv' $true $true 2 2)
    )
    NormalMovieEntries = @((New-TestEntry 'Movie.mkv' $false $false 1 1))
    NormalTVEntries = @((New-TestEntry 'Show.mkv' $true $false 1 1))
    MovieCount = 2
    TVCount = 2
    PriorityMovieCount = 1
    PriorityTVCount = 1
}
$result = Invoke-MediaQueuePhasePlan -QueuePlan $plan -ProcessedIndex @{ Done = $true }
if ($result.Stopped) { throw 'queue phase engine should not report stopped on normal run' }
if (($script:Processed.Name -join '|') -ne '!Movie.mkv|!Show.mkv|Movie.mkv|Show.mkv') { throw 'queue phase engine processing order changed' }
if ($script:Processed[0].IsTV -or -not $script:Processed[1].IsTV -or $script:Processed[2].IsTV -or -not $script:Processed[3].IsTV) { throw 'queue phase engine media type routing changed' }
if ($script:Logs -notmatch 'PRIORITY PHASE') { throw 'queue phase engine should log priority phase summary' }
'@.Replace('__FUNCTIONS__', $queueEngineFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $queueEngineCheck

$pipelineRunFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'New-MediaPipelineEnginePlan',
    'Invoke-MediaQueuePhasePlan',
    'Invoke-MediaPipelineQueueSnapshot',
    'Invoke-MediaPipelineRound',
    'Invoke-MediaPipelineRun',
    'Invoke-MediaPipelineEmitQueuePlan'
)) -join [Environment]::NewLine
$pipelineRunCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__

$script:StopRequested = $false
$script:Events = @()
$script:Logs = @()
$script:SnapshotThrows = $false
$script:PendingPushes = 1
$script:ReprocessAll = $true

function Add-TestEvent {
    param([string]$Name)
    $script:Events += ,$Name
}
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:Logs += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}
function Check-ControlFlags { Add-TestEvent 'check' }
function Consume-RescanFlag { Add-TestEvent 'consume-rescan'; return $true }
function Invoke-RetryPendingPushes { Add-TestEvent 'retry-pending'; return $script:PendingPushes }
function Refresh-PendingPublishIndex { Add-TestEvent 'refresh-pending' }
function Invalidate-ProcessedIndexCache { Add-TestEvent 'invalidate-index' }
function Reset-ProgressItemContext { Add-TestEvent 'reset-progress' }
function Set-ProgressStage {
    param([string]$Stage, [string]$Status, $Percent, [string]$Route, [string]$CopyState, [string]$PushState, [string]$SidecarState, [switch]$SaveNow)
    Add-TestEvent "stage:$Stage"
}
function Reset-RoundTracking { Add-TestEvent 'reset-round' }
function Get-ProcessedIndexCached {
    param([bool]$ForceRefresh = $false)
    Add-TestEvent "index:$ForceRefresh"
    return @{ Indexed = $true }
}
function New-TestQueuePlan {
    return [pscustomobject]@{
        PriorityEntries = @()
        NormalMovieEntries = @([pscustomobject]@{
            File = [pscustomobject]@{ Name = 'Movie.mkv' }
            IsTV = $false
            IsPriority = $false
            QueueIndex = 1
            QueueTotal = 1
            PriorityInfo = [pscustomobject]@{ IsPriority = $false }
        })
        NormalTVEntries = @()
        MovieCount = 1
        TVCount = 1
        MoviePriorityCount = 0
        TVPriorityCount = 0
        PriorityMovieCount = 0
        PriorityTVCount = 0
    }
}
function Get-MediaQueueDiscoveryPlan {
    param([string]$MovieRoot, [string]$TVRoot, [bool]$ForceRefresh = $false)
    Add-TestEvent "discover:$MovieRoot|$TVRoot|$ForceRefresh"
    return New-TestQueuePlan
}
function Build-QueuePlanSnapshotRows {
    param($QueuePlan, $ProcessedIndex)
    Add-TestEvent 'snapshot-build'
    return [pscustomobject]@{ runnable_count = 1 }
}
function Write-QueuePlanSnapshot {
    param($Plan, [string]$Path)
    Add-TestEvent "snapshot-write:$Path"
    if ($script:SnapshotThrows) { throw 'snapshot failed' }
}
function Process-File {
    param($File, [bool]$IsTV, $ProcessedIndex, [int]$QueueIndex = 0, [int]$QueueTotal = 0, $PriorityInfo = $null)
    Add-TestEvent "process:$($File.Name):$IsTV"
}
function Get-ProcessingStats { Add-TestEvent 'stats'; return 'stats text' }
function Write-RoundFailureSummary {
    Add-TestEvent 'summary'
    return [pscustomobject]@{ TextPath = 'round.txt'; JsonPath = 'round.json' }
}
function Start-StopAwareSleep {
    param([int]$Seconds)
    $script:Sleeps += ,$Seconds
    return $true
}

$plan = New-MediaPipelineEnginePlan -SourceMovies 'MoviesRoot' -SourceTV 'TVRoot' -QueueSnapshotPath 'snapshot.json' -Once:$false -SleepSeconds 9
$round = Invoke-MediaPipelineRound -EnginePlan $plan
if (-not $round.Completed -or $round.StopRequested) { throw 'round should complete when stop was not requested' }
if (-not $round.RescanRequested -or [int]$round.PendingPushesRecovered -ne 1) { throw 'round should report rescan and pending-push recovery state' }
if ($script:RoundMovieFilesFound -ne 1 -or $script:RoundTVFilesFound -ne 1) { throw 'round should update discovered movie/TV counts' }
if ($script:ReprocessAll) { throw 'round should auto-disable ReprocessAll after a complete uninterrupted round' }
$order = $script:Events -join '>'
if ($order -notmatch 'check>consume-rescan>retry-pending>refresh-pending>invalidate-index>reset-progress>stage:scanning>reset-round>index:True>discover:MoviesRoot\|TVRoot\|True>snapshot-build>snapshot-write:snapshot\.json>stage:processing>check>process:Movie\.mkv:False>stats>summary') {
    throw "round call order changed: $order"
}
if (($script:Logs.Message -join '|') -notmatch 'MOVIES FOUND: 1' -or ($script:Logs.Message -join '|') -notmatch 'Round failure summary JSON') {
    throw 'round should log discovery and round failure summary information'
}

$script:Events = @()
$script:Logs = @()
$script:SnapshotThrows = $true
$script:PendingPushes = 0
$script:ReprocessAll = $false
$snapshotFailureRound = Invoke-MediaPipelineRound -EnginePlan $plan
if (-not $snapshotFailureRound.Completed) { throw 'non-fatal snapshot failure should not stop the round' }
if (($script:Logs.Message -join '|') -notmatch 'Queue snapshot write failed \(non-fatal\)') { throw 'snapshot write failure should be logged as non-fatal' }
if (($script:Events -join '>') -notmatch 'process:Movie\.mkv:False') { throw 'snapshot write failure should not prevent queue execution' }

$script:Events = @()
$script:Logs = @()
$script:SnapshotThrows = $false
$script:PendingPushes = 99
$emit = Invoke-MediaPipelineEmitQueuePlan -EnginePlan $plan
if ([int]$emit.runnable_count -ne 1) { throw 'emit queue plan should return the written snapshot' }
if (($script:Events -join '>') -match 'retry-pending') { throw 'emit queue plan must not retry pending pushes' }
if (($script:Events -join '>') -notmatch 'stage:scanning>index:True>discover:MoviesRoot\|TVRoot\|True>snapshot-build>snapshot-write:snapshot\.json' -or ($script:Events -join '>') -notmatch 'stage:idle') {
    throw 'emit queue plan should perform one dry scan, write snapshot, and return to idle'
}

function Invoke-MediaPipelineRound {
    param($EnginePlan)
    $script:RunRounds++
    if ($script:RunRounds -ge $script:StopAfterRound) { $script:StopRequested = $true }
    return [pscustomobject]@{ Completed = $true; StopRequested = [bool]$script:StopRequested }
}

$script:RunRounds = 0
$script:StopAfterRound = 100
$script:StopRequested = $false
$script:Sleeps = @()
$script:Logs = @()
$oncePlan = New-MediaPipelineEnginePlan -SourceMovies 'MoviesRoot' -SourceTV 'TVRoot' -QueueSnapshotPath 'snapshot.json' -Once:$true -SleepSeconds 5
$onceRun = Invoke-MediaPipelineRun -EnginePlan $oncePlan
if ([int]$onceRun.RoundsCompleted -ne 1 -or [int]$script:RunRounds -ne 1) { throw 'once mode should run exactly one round through the engine' }
if ($script:Sleeps.Count -ne 0) { throw 'once mode should not sleep after the round' }
if (($script:Logs.Message -join '|') -notmatch 'Single-pass mode complete') { throw 'once mode should preserve completion log message' }

$script:RunRounds = 0
$script:StopAfterRound = 2
$script:StopRequested = $false
$script:Sleeps = @()
$continuousPlan = New-MediaPipelineEnginePlan -SourceMovies 'MoviesRoot' -SourceTV 'TVRoot' -QueueSnapshotPath 'snapshot.json' -Once:$false -SleepSeconds 5
$continuousRun = Invoke-MediaPipelineRun -EnginePlan $continuousPlan
if ([int]$continuousRun.RoundsCompleted -ne 2 -or [int]$script:RunRounds -ne 2) { throw 'continuous mode should keep running rounds until stop is requested' }
if ($script:Sleeps.Count -ne 1 -or [int]$script:Sleeps[0] -ne 5) { throw 'continuous mode should sleep between completed rounds' }
'@.Replace('__FUNCTIONS__', $pipelineRunFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $pipelineRunCheck

$diskCleanupFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Clear-StalePartialFiles'
)) -join [Environment]::NewLine
$diskCleanupCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__
function Write-Log { param([string]$Message, [string]$Level = 'INFO') }
function Test-IsUncPath { param([string]$Path) return ([string]$Path).StartsWith('\\') }
function Invoke-RecursivePathScan {
    param(
        [string]$Path,
        [string]$ItemType = 'File',
        [int]$TimeoutSeconds = 300,
        [string]$Label = 'scan'
    )
    if ($ItemType -eq 'Directory') {
        return @(Get-ChildItem -LiteralPath $Path -Directory -Recurse -Force | ForEach-Object { $_.FullName })
    }
    return @(Get-ChildItem -LiteralPath $Path -File -Recurse -Force | ForEach-Object { $_.FullName })
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-cleanup-" + [guid]::NewGuid().ToString("N"))
$script:CleanupStaleAgeHours = 1
$script:CleanupScanTimeoutSeconds = 30
$script:CleanupRemoteStaging = $true
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $oldPartial = Join-Path $root ('movie.mkv.mp-partial.' + ('a' * 32))
    $oldPublishPartial = Join-Path $root ('.movie.mkv.mp-publish-partial.' + ('b' * 32))
    $oldPublishBackup = Join-Path $root ('.movie.mkv.mp-publish-backup.' + ('c' * 32))
    $oldUserMatchingName = Join-Path $root 'movie.mp-partial-cut.mkv'
    $oldUncertainPublishPartial = Join-Path $root '.movie.mkv.mp-publish-partial.tx-test'
    $freshPartial = Join-Path $root ('movie.mkv.mp-partial.' + ('d' * 32))
    $unrelated = Join-Path $root 'old-but-unrelated.tmp'
    Set-Content -LiteralPath $oldPartial -Value 'old' -Encoding UTF8
    Set-Content -LiteralPath $oldPublishPartial -Value 'old' -Encoding UTF8
    Set-Content -LiteralPath $oldPublishBackup -Value 'old' -Encoding UTF8
    Set-Content -LiteralPath $oldUserMatchingName -Value 'user' -Encoding UTF8
    Set-Content -LiteralPath $oldUncertainPublishPartial -Value 'uncertain' -Encoding UTF8
    Set-Content -LiteralPath $freshPartial -Value 'fresh' -Encoding UTF8
    Set-Content -LiteralPath $unrelated -Value 'keep' -Encoding UTF8
    (Get-Item -LiteralPath $oldPartial).LastWriteTime = (Get-Date).AddHours(-3)
    (Get-Item -LiteralPath $oldPublishPartial).LastWriteTime = (Get-Date).AddHours(-3)
    (Get-Item -LiteralPath $oldPublishBackup).LastWriteTime = (Get-Date).AddHours(-3)
    (Get-Item -LiteralPath $oldUserMatchingName).LastWriteTime = (Get-Date).AddHours(-3)
    (Get-Item -LiteralPath $oldUncertainPublishPartial).LastWriteTime = (Get-Date).AddHours(-3)
    (Get-Item -LiteralPath $freshPartial).LastWriteTime = Get-Date
    (Get-Item -LiteralPath $unrelated).LastWriteTime = (Get-Date).AddHours(-3)

    $oldStageParent = Join-Path $root 'old-stage'
    $freshStageParent = Join-Path $root 'fresh-stage'
    $oldStaging = Join-Path $oldStageParent '.mediapipeline-staging'
    $freshStaging = Join-Path $freshStageParent '.mediapipeline-staging'
    New-Item -ItemType Directory -Path $oldStaging -Force | Out-Null
    New-Item -ItemType Directory -Path $freshStaging -Force | Out-Null
    (Get-Item -LiteralPath $oldStaging).LastWriteTime = (Get-Date).AddHours(-3)
    (Get-Item -LiteralPath $freshStaging).LastWriteTime = Get-Date

    Clear-StalePartialFiles -Roots @($root)
    if (Test-Path -LiteralPath $oldPartial) { throw 'stale partial file was not removed' }
    if (Test-Path -LiteralPath $oldPublishPartial) { throw 'stale publish partial file was not removed' }
    if (Test-Path -LiteralPath $oldPublishBackup) { throw 'stale publish backup file was not removed' }
    if (-not (Test-Path -LiteralPath $oldUserMatchingName)) { throw 'old user-owned matching filename should not be removed' }
    if (-not (Test-Path -LiteralPath $oldUncertainPublishPartial)) { throw 'old uncertain publish-looking filename should not be removed' }
    if (-not (Test-Path -LiteralPath $freshPartial)) { throw 'fresh partial file should not be removed' }
    if (-not (Test-Path -LiteralPath $unrelated)) { throw 'unrelated stale file should not be removed' }
    if (Test-Path -LiteralPath $oldStaging) { throw 'stale publish staging directory was not removed' }
    if (-not (Test-Path -LiteralPath $freshStaging)) { throw 'fresh publish staging directory should not be removed' }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
'@.Replace('__FUNCTIONS__', $diskCleanupFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $diskCleanupCheck

$diskSpaceFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Test-DiskSpace'
)) -join [Environment]::NewLine
$diskSpaceCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__
$script:MinFreeSpaceGB = 10
$script:LoggedMessages = @()
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:LoggedMessages += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}
function Get-FreeSpaceGBAny {
    param([string]$Path)
    if ($script:ProbeMode -eq 'throw') { throw 'probe failed' }
    if ($script:ProbeMode -eq 'low') { return 1 }
    return -1
}
$script:ProbeMode = 'indeterminate'
if (Test-DiskSpace -Path '\\server\share\out' -MinGB 10 -Label 'SERVER') { throw 'indeterminate disk space should fail closed' }
$script:ProbeMode = 'throw'
if (Test-DiskSpace -Path 'C:\scratch' -MinGB 10 -Label 'LOCAL') { throw 'disk probe exception should fail closed' }
$script:ProbeMode = 'low'
if (Test-DiskSpace -Path 'C:\scratch' -MinGB 10 -Label 'LOCAL') { throw 'low disk space should fail closed' }
$errors = @($script:LoggedMessages | Where-Object { $_.Level -eq 'ERROR' })
if ($errors.Count -lt 3) { throw 'fail-closed disk-space paths should log errors' }
'@.Replace('__FUNCTIONS__', $diskSpaceFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $diskSpaceCheck

$copyRobocopyPreflightFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Copy-FileRobocopy'
)) -join [Environment]::NewLine
$copyRobocopyPreflightCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__
$script:LoggedMessages = @()
$script:RobocopyTimeoutSeconds = 5
$script:OutsourceMinFreeSpaceGB = 50
$script:StopRequested = $false
$script:RobocopyInvoked = $false
$RobocopyFlags = @()
$StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-stop-' + [guid]::NewGuid().ToString('N') + '.flag')
$Outsource = ''
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:LoggedMessages += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}
function Resolve-RobocopyPath { return 'robocopy.exe' }
function Get-FreeSpaceGBAny { param([string]$Path) return -1 }
function Test-MediaPipelinePathIsEqualOrChild { param([string]$Path, [string]$Root) return $false }
function Invoke-NativeCommand {
    $script:RobocopyInvoked = $true
    throw 'robocopy should not run when destination free space is unknown'
}
function Start-StopAwareSleep { param([int]$Seconds) return $false }

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-copy-space-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $source = Join-Path $root 'source.mkv'
    $dest = Join-Path $root 'out\movie.mkv'
    [System.IO.File]::WriteAllBytes($source, (New-Object byte[] 1024))
    if (Copy-FileRobocopy -Source $source -Destination $dest -MaxRetries 1) { throw 'unknown destination free space should fail closed' }
    if ($script:RobocopyInvoked) { throw 'robocopy was invoked despite unknown destination free space' }
    if ($script:LastCopyFileRobocopyResult.ReasonCode -ne 'OUTPUT_DESTINATION_SPACE_UNKNOWN') { throw "unexpected reason code: $($script:LastCopyFileRobocopyResult.ReasonCode)" }
    if ([double]$script:LastCopyFileRobocopyResult.DestinationFreeGB -ne -1) { throw 'unknown destination free space should be recorded as -1' }
    if (-not ([double]$script:LastCopyFileRobocopyResult.RequiredGB -gt 0)) { throw 'required free-space estimate should be recorded' }
    if (Test-Path -LiteralPath (Join-Path (Split-Path $dest -Parent) '.mediapipeline-staging')) { throw 'unknown-space preflight should not leave staging directories' }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
}
'@.Replace('__FUNCTIONS__', $copyRobocopyPreflightFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $copyRobocopyPreflightCheck

$outputSummaryFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-MediaRouteEncodeName',
    'Get-MediaRouteRemuxName',
    'Get-MediaRouteEncodeCpuFallbackName',
    'Get-MediaSubtitleCodecAssNames',
    'Get-MediaSubtitleCodecSrtNames',
    'Write-OutputSummary'
)) -join [Environment]::NewLine
$outputSummaryCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__
$script:LoggedMessages = @()
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:LoggedMessages += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}
function Invoke-FFprobeCommand {
    param([array]$ArgumentList, [int]$TimeoutSeconds, [string]$Stage)
    if ($Stage -ne 'output-summary-probe') { throw 'output summary used the wrong ffprobe stage' }
    if ($TimeoutSeconds -ne 30) { throw 'output summary ffprobe timeout changed' }
    $payload = @{
        streams = @(
            @{ codec_type = 'video'; codec_name = 'hevc'; width = 1920; height = 1080 },
            @{ codec_type = 'audio'; codec_name = 'eac3'; channels = 6; disposition = @{ default = 1 }; tags = @{ language = 'eng' } },
            @{ codec_type = 'subtitle'; codec_name = 'subrip'; disposition = @{ default = 1; forced = 1 }; tags = @{ language = 'eng'; title = 'Signs and Songs' } }
        )
    } | ConvertTo-Json -Depth 6
    return [pscustomobject]@{ ExitCode = 0; Output = $payload; Error = ''; TimedOut = $false; Stopped = $false }
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-output-summary-" + [guid]::NewGuid().ToString("N"))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $file = Join-Path $root 'output.mkv'
    [System.IO.File]::WriteAllBytes($file, (New-Object byte[] 1048576))
    Write-OutputSummary -FilePath $file -Route 'encode-cpu-fallback'
    if (@($script:LoggedMessages).Count -ne 1) { throw 'output summary did not log exactly once' }
    $message = [string]$script:LoggedMessages[0].Message
    if ($message -notmatch '^OUTPUT: 0\.00GB \| HEVC 1080p \| ENG 5\.1 EAC3 \[def\] \| ENG SRT \[def,forced,signs\] \(encode, CPU\)$') {
        throw "output summary format changed: $message"
    }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
'@.Replace('__FUNCTIONS__', $outputSummaryFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $outputSummaryCheck

$plexCompatibilityFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-MediaVideoCodecPlexDirectPlayNames',
    'Get-MediaSubtitleCodecAssNames',
    'Get-MediaSubtitleCodecSrtNames',
    'Get-MediaSubtitleCodecBdpgsNames',
    'Get-MediaAudioCodecPlexTranscodeRiskNames',
    'Write-PlexCompatibilityReport'
)) -join [Environment]::NewLine
$plexCompatibilityCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__
$script:LoggedMessages = @()
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:LoggedMessages += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}
function Invoke-FFprobeCommand {
    param([array]$ArgumentList, [int]$TimeoutSeconds, [string]$Stage)
    if ($Stage -ne 'plex-compatibility-probe') { throw 'Plex compatibility used the wrong ffprobe stage' }
    if ($TimeoutSeconds -ne 45) { throw 'Plex compatibility ffprobe timeout changed' }
    $payload = @{
        streams = @(
            @{ codec_type = 'video'; codec_name = 'mpeg2video'; disposition = @{}; tags = @{} },
            @{ codec_type = 'audio'; codec_name = 'flac'; disposition = @{ default = 1 }; tags = @{ language = 'jpn' } },
            @{ codec_type = 'subtitle'; codec_name = 'hdmv_pgs_subtitle'; disposition = @{ default = 1 }; tags = @{ language = 'eng'; title = 'English PGS' } }
        )
    } | ConvertTo-Json -Depth 6
    return [pscustomobject]@{ ExitCode = 0; Output = $payload; Error = ''; TimedOut = $false; Stopped = $false }
}

Write-PlexCompatibilityReport -FilePath 'output.mkv' -Context 'ENCODE: '
if (@($script:LoggedMessages).Count -ne 5) { throw ('expected 5 Plex compatibility log lines, got ' + @($script:LoggedMessages).Count) }
$summary = [string]$script:LoggedMessages[0].Message
if ($summary -ne 'ENCODE: PLEX CHECK: video=mpeg2video | default audio=jpn/flac | default subtitles=eng/hdmv_pgs_subtitle | outlook=LOW') {
    throw "Plex compatibility summary changed: $summary"
}
$warningText = (@($script:LoggedMessages | Where-Object { $_.Level -eq 'WARN' }).Message -join '|')
foreach ($expected in @(
    "default audio codec 'flac' may force Plex transcode",
    "default subtitle codec 'hdmv_pgs_subtitle' usually forces image-based subtitle handling",
    'no SRT text subtitle track present',
    "video codec 'mpeg2video' may not direct play broadly"
)) {
    if ($warningText -notmatch [regex]::Escape($expected)) { throw "missing Plex warning: $expected" }
}
'@.Replace('__FUNCTIONS__', $plexCompatibilityFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $plexCompatibilityCheck

$publishCompletionFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Test-PublishCopyFailureIsOutputSpace',
    'Test-PublishCopyFailureIsOutputSpaceUnknown',
    'Get-PublishCopyFailureReason',
    'New-PipelinePublishResult',
    'New-PublishPartialMediaPath',
    'Remove-PublishPartialMedia',
    'Backup-PublishSidecarForReveal',
    'Remove-PublishSidecarBackup',
    'Restore-PublishSidecarAfterRevealFailure',
    'Complete-PublishMediaReveal',
    'Publish-Tx3gSrtSidecarsFromPlan',
    'Get-ActiveFolderPolicyMetadata',
    'Complete-PipelineOutputPublish'
)) -join [Environment]::NewLine
$publishCompletionCheck = @'
$ErrorActionPreference = 'Stop'
function Write-Log { param([string]$Message, [string]$Level = 'INFO') }
function Set-ProgressStage {
    param([string]$Stage, [string]$Status, [string]$Route, [string]$PushState, [string]$SidecarState, $Percent, [switch]$SaveNow)
    $script:ProgressCalls += ,([pscustomobject]@{ Stage = $Stage; Route = $Route; PushState = $PushState; SidecarState = $SidecarState; Percent = $Percent })
}
function Copy-FileRobocopy {
    param([string]$Source, [string]$Destination)
    $script:CopyCalls++
    if ($script:CopyMode -eq 'fail') { return $false }
    if ($script:CopyMode -eq 'space') {
        $script:LastCopyFileRobocopyResult = [pscustomobject]@{
            Ok = $false
            ReasonCode = 'OUTPUT_DESTINATION_LOW_SPACE'
            Reason = 'Destination has insufficient free space: 1.00 GB free, need 99.00 GB+. Path: server'
            DestinationFreeGB = 1.0
            RequiredGB = 99.0
        }
        return $false
    }
    if ($script:CopyMode -eq 'unknown_space') {
        $script:LastCopyFileRobocopyResult = [pscustomobject]@{
            Ok = $false
            ReasonCode = 'OUTPUT_DESTINATION_SPACE_UNKNOWN'
            Reason = 'Unable to determine destination free space; refusing copy before mutation. Need 99.00 GB+. Path: server'
            DestinationFreeGB = -1.0
            RequiredGB = 99.0
        }
        return $false
    }
    $dir = Split-Path $Destination -Parent
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    return $true
}
function New-Tx3gFailureRecord {
    param($Entry, [string]$Reason, [string]$ErrorCode)
    return [pscustomobject]@{ Reason = $Reason; ErrorCode = $ErrorCode; StreamIndex = 2 }
}
function New-Tx3gSrtSidecarPublishPlan {
    param([array]$Tx3gTracks, [string]$MediaOutputPath, [string]$Context = '')
    $script:PublishTx3gCalls++
    if ($script:Tx3gMode -eq 'fail') {
        return @{ Tracks = @(); Failures = @([pscustomobject]@{ Reason = 'tx3g publish failed'; ErrorCode = 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED'; StreamIndex = 2 }); SidecarFiles = @() }
    }
    if (@($Tx3gTracks).Count -eq 0) { return @{ Tracks = @(); Failures = @(); SidecarFiles = @() } }
    $record = [pscustomobject]@{ status = 'pending'; path = "$MediaOutputPath.eng.tx3g.srt"; stream_index = 2; language = 'eng'; title = 'English' }
    return @{
        Tracks = @($record)
        Failures = @()
        SidecarFiles = @([pscustomobject]@{ LocalPath = 'local-tx3g.srt'; DestinationPath = "$MediaOutputPath.eng.tx3g.srt"; Record = $record })
    }
}
function Copy-SrtAtomic {
    param([string]$SourcePath, [string]$DestinationPath)
    $dir = Split-Path $DestinationPath -Parent
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
    Set-Content -LiteralPath $DestinationPath -Value '1`n00:00:00,000 --> 00:00:01,000`nsubtitle' -Encoding UTF8
    return [pscustomobject]@{ Ok = $true; CueCount = 1; Reason = ''; ErrorCode = '' }
}
function Register-Tx3gSubtitleFailure {
    param($SourceFile, [string]$ScratchPath, [array]$Failures, [string]$Stage)
    $script:RegisteredTx3g += ,([pscustomobject]@{ Stage = $Stage; Count = @($Failures).Count; ScratchPath = $ScratchPath })
}
function Add-RoundFailureRecord {
    param([string]$SourcePath, [string]$Stage, [string]$Reason, [string]$Classification, [string]$ErrorCode, [string]$ArtifactPath, [string]$SuggestedAction)
    $script:RoundFailures += ,([pscustomobject]@{ Stage = $Stage; Reason = $Reason; Classification = $Classification; ErrorCode = $ErrorCode; ArtifactPath = $ArtifactPath; SuggestedAction = $SuggestedAction })
}
function Invoke-ParkPendingPushWithTx3gSidecars {
    param($SourceFile, [string]$ScratchPath, [array]$Tx3gTracks, [array]$BdpgsTracks, [string]$MediaOutputPath, [hashtable]$ParkArgs, [string]$Context = '')
    $script:ParkCalls += ,([pscustomobject]@{ ParkArgs = $ParkArgs.Clone(); ScratchPath = $ScratchPath; MediaOutputPath = $MediaOutputPath; Context = $Context; Tx3gCount = @($Tx3gTracks).Count; BdpgsCount = @($BdpgsTracks).Count })
    return ($script:ParkMode -ne 'fail')
}
function Invoke-ParkPendingPush {
    param(
        [string]$LocalOut,
        [string]$ServerOut,
        [string]$Route,
        [string]$RouteReasonCode,
        [string]$RouteReason,
        [string]$SourceIdentity,
        [string]$SourceIdentityV2,
        [string]$SourcePath,
        [long]$SourceSize,
        [string]$SourceMTimeUtc,
        [string]$PublishTransactionId,
        [string]$PublishMode,
        $FolderPolicyMetadata,
        $RoutePlanMetadata,
        [array]$Tx3gSrtTracks = @(),
        [array]$Tx3gSrtFailures = @(),
        [array]$BdpgsSrtFailures = @(),
        [array]$Tx3gEmbeddedSrtTracks = @(),
        [array]$BdpgsEmbeddedSrtTracks = @(),
        [bool]$Tx3gSrtConversionEnabled = $false,
        [bool]$Tx3gExternalSrtSidecarsEnabled = $false,
        [bool]$DropTx3gAfterConversion = $false,
        [bool]$BdpgsSrtConversionEnabled = $false,
        [bool]$DropBdpgsAfterConversion = $false
    )
    $script:ParkCalls += ,([pscustomobject]@{
        ParkArgs = @{
            LocalOut = $LocalOut; ServerOut = $ServerOut; Route = $Route
            PublishMode = $PublishMode; PublishTransactionId = $PublishTransactionId
            Tx3gSrtFailures = @($Tx3gSrtFailures)
        }
        ScratchPath = ''
        MediaOutputPath = $ServerOut
        Context = 'direct'
        Tx3gCount = @($Tx3gSrtTracks).Count
        BdpgsCount = 0
    })
    return ($script:ParkMode -ne 'fail')
}
function Get-SidecarPath {
    param([string]$OutputPath)
    $dir = Split-Path $OutputPath -Parent
    $base = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
    return (Join-Path $dir ($base + '.pipeline.json'))
}
function Write-Sidecar {
    param([string]$OutputPath, [string]$Route, $Extra, [switch]$SkipCompletedManifest)
    $script:SidecarWrites += ,([pscustomobject]@{ OutputPath = $OutputPath; Route = $Route; Extra = $Extra; SkipCompletedManifest = [bool]$SkipCompletedManifest })
    if ($script:SidecarMode -ne 'fail') {
        $sidecar = Get-SidecarPath $OutputPath
        $sidecarDir = Split-Path $sidecar -Parent
        if ($sidecarDir -and -not (Test-Path -LiteralPath $sidecarDir)) { [System.IO.Directory]::CreateDirectory($sidecarDir) | Out-Null }
        @{ schema_version = 'pipeline_sidecar.v1'; output_path = $OutputPath; route = $Route; publish_transaction_id = $Extra.publish_transaction_id } |
            ConvertTo-Json -Depth 5 |
            Set-Content -LiteralPath $sidecar -Encoding UTF8
    }
    return ($script:SidecarMode -ne 'fail')
}
function Add-CompletedJobsManifestEntryFromSidecar {
    param([string]$OutputPath)
    $script:CompletedManifestAdds += ,$OutputPath
    return $true
}
function Get-LastAudioDecisionRecords {
    return @([pscustomobject]@{ audio_ordinal = 0; action = 'copy'; source_codec = 'ac3' })
}
function Get-LastSubtitleDecisionRecords {
    return @([pscustomobject]@{ subtitle_ordinal = 0; action = 'keep'; source_codec = 'subrip' })
}
function Write-OutputSummary { param([string]$FilePath, [string]$Route) $script:Summaries += ,([pscustomobject]@{ FilePath = $FilePath; Route = $Route }) }
function Clear-SourceFailureState { param($SourceFile) $script:ClearFailureCalls++ }
function Invalidate-ProcessedIndexCache { $script:InvalidateCalls++ }
function Get-SourceIdentityKey { param($File) return "sid:$($File.Name):$($File.Length)" }
function Get-SourceIdentityKeyV2 { param($File) return "sid2:$($File.Name):$($File.Length)" }
function New-PublishTransactionId { return 'txn-test' }
function ConvertTo-Tx3gEmbeddedSrtTrackRecords { param([array]$Tx3gTracks) return @([pscustomobject]@{ kind = 'tx3g-embedded'; count = @($Tx3gTracks).Count }) }
function ConvertTo-BdpgsEmbeddedSrtTrackRecords { param([array]$BdpgsTracks) return @([pscustomobject]@{ kind = 'bdpgs-embedded'; count = @($BdpgsTracks).Count }) }
function Reset-TestPublishState {
    $script:ProgressCalls = @()
    $script:CopyCalls = 0
    $script:PublishTx3gCalls = 0
    $script:RegisteredTx3g = @()
    $script:RoundFailures = @()
    $script:ParkCalls = @()
    $script:SidecarWrites = @()
    $script:CompletedManifestAdds = @()
    $script:Summaries = @()
    $script:ClearFailureCalls = 0
    $script:InvalidateCalls = 0
    $script:CopyMode = 'success'
    $script:Tx3gMode = 'success'
    $script:ParkMode = 'success'
    $script:SidecarMode = 'success'
    $script:DeferredPublish = $false
    $script:LastCopyFileRobocopyResult = $null
    $script:CurrentEncodeAttempts = $null
}
'@ + $publishCompletionFunctions + @'

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-publish-completion-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $script:pipelineStatus = 'Processing'
    $script:PipelineVersion = 'test-version'
    $script:SourceIdentityV2Algorithm = 'identity-v2-test'
    $script:ConvertTx3gToSrt = $true
    $script:CreateExternalTx3gSrtSidecars = $true
    $script:DropTx3gAfterConversion = $false
    $script:ConvertBdpgsToSrt = $false
    $script:DropBdpgsAfterConversion = $false
    $script:currentItemStartedAt = (Get-Date).AddSeconds(-5)
    $script:FolderPolicySchemaVersion = 'folder_policy.v1'
    $script:ActiveOverrides = @{
        FolderPolicyPath = 'C:\Media\TVSHOWSAMPLE\mediapipeline.folder.json'
        FolderPolicyFolder = 'C:\Media\TVSHOWSAMPLE'
        FolderPolicyKeys = @('AudioTranscodeCodec', 'ConvertTx3gToSrt')
        AudioTranscodeCodec = 'aac'
        ConvertTx3gToSrt = $false
    }
    $sourcePath = Join-Path $root 'source.mkv'
    Set-Content -LiteralPath $sourcePath -Value 'source-content' -Encoding UTF8
    $source = Get-Item -LiteralPath $sourcePath

    Reset-TestPublishState
    $localOut = Join-Path $root 'local-success.mkv'
    $serverOut = Join-Path $root 'server\success.mkv'
    Set-Content -LiteralPath $localOut -Value 'verified-output' -Encoding UTF8
    $paths = @{ LocalOut = $localOut; ServerOut = $serverOut; PlexPlan = [pscustomobject]@{ MediaKind = 'TV' } }
    $script:CurrentEncodeAttempts = @([ordered]@{ attempt = 'primary'; success = $true; selected_encoder = 'hevc_nvenc'; encoder_kind = 'nvenc'; selected_gpu_device = '1' })
    $result = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths $paths -Route 'encode-cpu-fallback' -ProgressRoute 'encode' -StagePrefix 'encode' -Context 'ENCODE: ' -Tx3gTracks @('tx') -BdpgsTracks @('bd')
    if (-not $result.Ok -or -not $result.DeleteLocalOutput -or $result.KeepScratchInput) { throw 'immediate publish success result flags changed' }
    if (-not (Test-Path -LiteralPath $serverOut)) { throw 'immediate publish did not copy output to server' }
    if (@($script:SidecarWrites).Count -ne 1 -or $script:SidecarWrites[0].Route -ne 'encode-cpu-fallback') { throw 'immediate publish did not write sidecar with final route' }
    if (-not [bool]$script:SidecarWrites[0].SkipCompletedManifest) { throw 'immediate publish sidecar should skip completed manifest until media reveal succeeds' }
    if (@($script:CompletedManifestAdds).Count -ne 1 -or [string]$script:CompletedManifestAdds[0] -ne $serverOut) { throw 'completed manifest should append only after final media reveal succeeds' }
    if ([string]$script:SidecarWrites[0].Extra.publish_mode -ne 'immediate' -or [string]$script:SidecarWrites[0].Extra.publish_transaction_id -ne 'txn-test') { throw 'sidecar publish metadata changed' }
    if ([string]$script:SidecarWrites[0].Extra.media_type -ne 'tv') { throw 'sidecar media_type should be derived from hashtable PlexPlan' }
    if (@($script:SidecarWrites[0].Extra.audio_decisions).Count -ne 1 -or [string]$script:SidecarWrites[0].Extra.audio_decisions[0].action -ne 'copy') { throw 'sidecar did not include audio decision records' }
    if (@($script:SidecarWrites[0].Extra.subtitle_decisions).Count -ne 1 -or [string]$script:SidecarWrites[0].Extra.subtitle_decisions[0].action -ne 'keep') { throw 'sidecar did not include subtitle decision records' }
    if ([string]$script:SidecarWrites[0].Extra.encode_selected_encoder -ne 'hevc_nvenc' -or [string]$script:SidecarWrites[0].Extra.encode_selected_encoder_kind -ne 'nvenc' -or [string]$script:SidecarWrites[0].Extra.encode_selected_gpu_device -ne '1') { throw 'sidecar did not include selected encode encoder/GPU metadata' }
    if ([string]$script:SidecarWrites[0].Extra.encode_selected_attempt.attempt -ne 'primary') { throw 'sidecar did not include selected encode attempt metadata' }
    if ([string]$script:SidecarWrites[0].Extra.source_identity_v2_algorithm -ne 'identity-v2-test') { throw 'sidecar source identity v2 algorithm missing' }
    if (-not [bool]$script:SidecarWrites[0].Extra.folder_policy.applied -or [string]$script:SidecarWrites[0].Extra.folder_policy.path -notmatch 'mediapipeline\.folder\.json') { throw 'sidecar folder policy metadata missing' }
    if (@($script:ProgressCalls | Where-Object { $_.Stage -eq 'push' -and $_.Route -eq 'encode' -and $_.PushState -eq 'complete' }).Count -ne 1) { throw 'immediate publish should report encode push completion' }
    if ($script:ClearFailureCalls -ne 1 -or $script:InvalidateCalls -ne 1) { throw 'immediate publish should clear failure state and invalidate processed cache' }

    Reset-TestPublishState
    $script:DeferredPublish = $true
    $localDeferred = Join-Path $root 'local-deferred.mkv'
    $serverDeferred = Join-Path $root 'server\deferred.mkv'
    Set-Content -LiteralPath $localDeferred -Value 'verified-output' -Encoding UTF8
    $deferredResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths ([pscustomobject]@{ LocalOut = $localDeferred; ServerOut = $serverDeferred }) -Route 'remux' -ProgressRoute 'remux' -StagePrefix 'remux' -Context 'REMUX: ' -Tx3gTracks @('tx')
    if (-not $deferredResult.Ok -or $deferredResult.DeleteLocalOutput -or $deferredResult.KeepScratchInput) { throw 'deferred publish result flags changed' }
    if ($script:CopyCalls -ne 0 -or @($script:SidecarWrites).Count -ne 0) { throw 'deferred publish should park without copy or sidecar write' }
    if (@($script:ParkCalls).Count -ne 1 -or [string]$script:ParkCalls[0].ParkArgs.PublishMode -ne 'deferred' -or [string]$script:ParkCalls[0].ParkArgs.Route -ne 'remux') { throw 'deferred publish did not park with deferred remux metadata' }
    if (-not [bool]$script:ParkCalls[0].ParkArgs.FolderPolicyMetadata.applied) { throw 'deferred publish did not park folder policy metadata' }

    Reset-TestPublishState
    $script:CopyMode = 'space'
    $localOutputSpace = Join-Path $root 'local-output-space.mkv'
    $serverOutputSpace = Join-Path $root 'server\output-space.mkv'
    Set-Content -LiteralPath $localOutputSpace -Value 'verified-output' -Encoding UTF8
    $outputSpaceResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths ([pscustomobject]@{ LocalOut = $localOutputSpace; ServerOut = $serverOutputSpace }) -Route 'encode' -ProgressRoute 'encode' -StagePrefix 'encode' -Context 'ENCODE: '
    if (-not $outputSpaceResult.Ok -or $outputSpaceResult.DeleteLocalOutput -or $outputSpaceResult.KeepScratchInput) { throw 'output destination full should park without failure result flags changed' }
    if (@($script:RoundFailures).Count -ne 0) { throw 'output destination full should park without failure notification' }
    if (@($script:ParkCalls).Count -ne 1 -or [string]$script:ParkCalls[0].ParkArgs.PublishMode -ne 'output-space-deferred') { throw 'output destination full should use output-space deferred pending publish mode' }
    if ($script:ClearFailureCalls -ne 1) { throw 'output destination full should clear stale source failure state after safe park' }
    if (@($script:ProgressCalls | Where-Object { $_.Stage -eq 'push' -and $_.Route -eq 'encode' -and $_.PushState -eq 'deferred' }).Count -ne 1) { throw 'output destination full should report deferred push progress state' }

    Reset-TestPublishState
    $script:CopyMode = 'unknown_space'
    $localUnknownSpace = Join-Path $root 'local-output-space-unknown.mkv'
    $serverUnknownSpace = Join-Path $root 'server\output-space-unknown.mkv'
    Set-Content -LiteralPath $localUnknownSpace -Value 'verified-output' -Encoding UTF8
    $unknownSpaceResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths ([pscustomobject]@{ LocalOut = $localUnknownSpace; ServerOut = $serverUnknownSpace }) -Route 'encode' -ProgressRoute 'encode' -StagePrefix 'encode' -Context 'ENCODE: '
    if (-not $unknownSpaceResult.Ok -or $unknownSpaceResult.DeleteLocalOutput -or $unknownSpaceResult.KeepScratchInput) { throw 'output destination unknown should park without failure result flags changed' }
    if (@($script:RoundFailures).Count -ne 0) { throw 'output destination unknown should park without failure notification' }
    if (@($script:ParkCalls).Count -ne 1 -or [string]$script:ParkCalls[0].ParkArgs.PublishMode -ne 'output-space-deferred') { throw 'output destination unknown should use output-space deferred pending publish mode' }
    if ($script:ClearFailureCalls -ne 1) { throw 'output destination unknown should clear stale source failure state after safe park' }
    if (@($script:ProgressCalls | Where-Object { $_.Stage -eq 'push' -and $_.Route -eq 'encode' -and $_.PushState -eq 'deferred' }).Count -ne 1) { throw 'output destination unknown should report deferred push progress state' }

    Reset-TestPublishState
    $script:CopyMode = 'fail'
    $localPushFail = Join-Path $root 'local-push-fail.mkv'
    $serverPushFail = Join-Path $root 'server\push-fail.mkv'
    Set-Content -LiteralPath $localPushFail -Value 'verified-output' -Encoding UTF8
    $pushFailResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths ([pscustomobject]@{ LocalOut = $localPushFail; ServerOut = $serverPushFail }) -Route 'encode' -ProgressRoute 'encode' -StagePrefix 'encode' -Context 'ENCODE: '
    if ($pushFailResult.Ok -or $pushFailResult.DeleteLocalOutput -or $pushFailResult.KeepScratchInput) { throw 'push failure result flags changed' }
    if (@($script:RoundFailures).Count -ne 1 -or [string]$script:RoundFailures[0].Stage -ne 'encode-push') { throw 'push failure should record encode-push failure' }
    if (@($script:ParkCalls).Count -ne 1 -or [string]$script:ParkCalls[0].ParkArgs.PublishMode -ne 'retry') { throw 'push failure should park for retry' }

    Reset-TestPublishState
    $script:SidecarMode = 'fail'
    $localSidecarFail = Join-Path $root 'local-sidecar-fail.mkv'
    $serverSidecarFail = Join-Path $root 'server\sidecar-fail.mkv'
    Set-Content -LiteralPath $localSidecarFail -Value 'verified-output' -Encoding UTF8
    $sidecarFailResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths ([pscustomobject]@{ LocalOut = $localSidecarFail; ServerOut = $serverSidecarFail }) -Route 'encode' -ProgressRoute 'encode' -StagePrefix 'encode' -Context 'ENCODE: '
    if ($sidecarFailResult.Ok -or $sidecarFailResult.DeleteLocalOutput -or $sidecarFailResult.KeepScratchInput) { throw 'sidecar write failure result flags changed' }
    if (Test-Path -LiteralPath $serverSidecarFail) { throw 'sidecar write failure should not reveal final server output before metadata succeeds' }
    if (Test-Path -LiteralPath (Get-SidecarPath $serverSidecarFail)) { throw 'sidecar write failure should not leave metadata without final media' }
    if (@($script:CompletedManifestAdds).Count -ne 0) { throw 'sidecar write failure must not append completed manifest' }
    if (@($script:RoundFailures).Count -ne 1 -or [string]$script:RoundFailures[0].Stage -ne 'encode-sidecar') { throw 'sidecar write failure should record encode-sidecar failure' }
    if (@($script:ParkCalls).Count -ne 1 -or [string]$script:ParkCalls[0].ParkArgs.PublishMode -ne 'retry') { throw 'sidecar write failure should park local output for retry' }
    if (@($script:ProgressCalls | Where-Object { $_.Stage -eq 'sidecar' -and $_.Route -eq 'encode' -and $_.SidecarState -eq 'failed' }).Count -ne 1) { throw 'sidecar write failure should report sidecar failed progress state' }

    Reset-TestPublishState
    $script:Tx3gMode = 'fail'
    $localTx3gFail = Join-Path $root 'local-tx3g-fail.mkv'
    $serverTx3gFail = Join-Path $root 'server\tx3g-fail.mkv'
    Set-Content -LiteralPath $localTx3gFail -Value 'verified-output' -Encoding UTF8
    $tx3gFailResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths ([pscustomobject]@{ LocalOut = $localTx3gFail; ServerOut = $serverTx3gFail }) -Route 'remux' -ProgressRoute 'remux' -StagePrefix 'remux' -Context 'REMUX: ' -Tx3gTracks @('tx')
    if ($tx3gFailResult.Ok -or $tx3gFailResult.DeleteLocalOutput -or -not $tx3gFailResult.KeepScratchInput) { throw 'tx3g sidecar failure result flags changed' }
    if (@($script:RegisteredTx3g).Count -ne 1 -or [string]$script:RegisteredTx3g[0].Stage -ne 'subtitle-tx3g-publish') { throw 'tx3g sidecar failure should register subtitle publish failure' }
    if (@($script:RoundFailures).Count -ne 1 -or [string]$script:RoundFailures[0].Stage -ne 'remux-tx3g-sidecar') { throw 'tx3g sidecar failure should record route-specific round failure' }
    if (@($script:ParkCalls).Count -ne 1 -or [string]$script:ParkCalls[0].ParkArgs.PublishMode -ne 'retry') { throw 'tx3g sidecar failure should park local output for retry' }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
'@
Invoke-PowerShellBehaviorCheck -ScriptText $publishCompletionCheck

$sidecarValidationFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Test-SidecarRoundTripValid'
)) -join [Environment]::NewLine
$sidecarValidationCheck = @"
`$ErrorActionPreference = 'Stop'
$sidecarValidationFunctions
`$payload = [ordered]@{
    schema_version = 'pipeline_sidecar.v1'
    pipeline_version = '1.0'
    route = 'encode'
    output_file = 'episode.mkv'
    output_path = 'C:\Media\episode.mkv'
    publish_state = 'published'
    publish_transaction_id = 'txn-good'
    source_identity_v2 = 'sid2'
    output_size = 123
    tx3g_srt_tracks = @()
    tx3g_srt_failures = @()
    bdpgs_srt_failures = @()
    tx3g_embedded_srt_tracks = @()
    bdpgs_embedded_srt_tracks = @()
}
`$roundTrip = `$payload | ConvertTo-Json -Depth 5 | ConvertFrom-Json
`$good = Test-SidecarRoundTripValid -RoundTrip `$roundTrip -Payload `$payload
if (-not `$good.Ok) { throw ('valid sidecar rejected: ' + `$good.Reason) }
`$missingIdentity = [ordered]@{}
foreach (`$key in `$payload.Keys) { `$missingIdentity[`$key] = `$payload[`$key] }
`$missingIdentity.Remove('source_identity_v2')
`$badRoundTrip = `$missingIdentity | ConvertTo-Json -Depth 5 | ConvertFrom-Json
`$bad = Test-SidecarRoundTripValid -RoundTrip `$badRoundTrip -Payload `$payload
if (`$bad.Ok -or `$bad.Reason -notmatch 'source_identity_v2') { throw 'sidecar validation accepted missing source_identity_v2' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $sidecarValidationCheck

$ffmpegProgressFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Convert-FFmpegProgressTimestampToSeconds',
    'Get-FFmpegProgressPercentFromLine'
)) -join [Environment]::NewLine
$ffmpegProgressParserCheck = @"
`$ErrorActionPreference = 'Stop'
$ffmpegProgressFunctions
function Assert-Near {
    param([double]`$Actual, [double]`$Expected, [string]`$Label)
    if ([math]::Abs(`$Actual - `$Expected) -gt 0.01) { throw "`$Label expected `$Expected but got `$Actual" }
}
Assert-Near (Get-FFmpegProgressPercentFromLine -Line 'out_time_us=5000000' -DurationSeconds 20) 25 'out_time_us progress'
Assert-Near (Get-FFmpegProgressPercentFromLine -Line 'out_time_ms=10000000' -DurationSeconds 20) 50 'out_time_ms progress'
Assert-Near (Get-FFmpegProgressPercentFromLine -Line 'out_time=00:00:15.500000' -DurationSeconds 31) 50 'out_time timestamp progress'
Assert-Near (Get-FFmpegProgressPercentFromLine -Line 'time=00:01:00.000' -DurationSeconds 120) 50 'stats time progress'
Assert-Near (Get-FFmpegProgressPercentFromLine -Line 'out_time_us=30000000' -DurationSeconds 10) 100 'progress clamp'
if (`$null -ne (Get-FFmpegProgressPercentFromLine -Line 'speed=2.0x' -DurationSeconds 10)) { throw 'non-progress line returned a percent' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $ffmpegProgressParserCheck

$ffmpegProgressRunnerFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'New-NativeCommandResult',
    'Set-ExternalToolResultProperty',
    'Get-NativeToolDefaultTimeoutSeconds',
    'Add-NativeProcessText',
    'Test-NativeProcessStopRequested',
    'Receive-NativeProcessLine',
    'Invoke-NativeProcess',
    'Convert-FFmpegProgressTimestampToSeconds',
    'Get-FFmpegProgressPercentFromLine',
    'Invoke-FFmpegWithProgress'
)) -join [Environment]::NewLine
$ffmpegProgressRunnerCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__
$script:LoggedMessages = @()
$script:ProgressCalls = @()
$script:PipelineEvents = @()
$script:SavedProgress = @()
$script:FFmpegProgressWriteStepPercent = 25
$script:pipelineStatus = 'Processing'
$script:StopRequested = $false
$Global:ffmpegProcess = $null
$StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-ffmpeg-stop-" + [guid]::NewGuid().ToString("N") + ".flag")
$PauseFlag = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-ffmpeg-pause-" + [guid]::NewGuid().ToString("N") + ".flag")
$LocalFailed = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-ffmpeg-failed-" + [guid]::NewGuid().ToString("N"))
$ffmpegPath = (Get-Command cmd.exe).Source

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $script:LoggedMessages += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}
function Set-ProgressStage {
    param([string]$Stage, [string]$Status, [string]$Route, $Percent, [switch]$SaveNow)
    $script:ProgressCalls += ,([pscustomobject]@{ Stage = $Stage; Route = $Route; Percent = $Percent; SaveNow = [bool]$SaveNow })
}
function Save-Progress {
    param($Status)
    $script:SavedProgress += ,$Status
    return $true
}
function Write-PipelineEvent {
    param([string]$EventType, [string]$Stage, [string]$Route, [string]$Status, [string]$SourcePath, $Data)
    $script:PipelineEvents += ,([pscustomobject]@{
        EventType = $EventType
        Stage = $Stage
        Route = $Route
        Status = $Status
        SourcePath = $SourcePath
        Data = $Data
    })
    return $true
}
function Format-NativeCommandLine {
    param([string]$FilePath, [array]$ArgumentList)
    return (($FilePath) + ' ' + (@($ArgumentList) -join ' '))
}
function Invoke-FFprobeCommand {
    param([array]$ArgumentList, [int]$TimeoutSeconds, [string]$Stage)
    if ($Stage -ne 'ffmpeg-progress-duration-probe') { throw "unexpected ffprobe stage: $Stage" }
    if ($TimeoutSeconds -ne 30) { throw 'ffmpeg progress duration probe timeout changed' }
    return [pscustomobject]@{ ExitCode = 0; Output = '20.0'; Error = ''; TimedOut = $false; Stopped = $false }
}
function Stop-NativeProcessTree {
    param([System.Diagnostics.Process]$Process, [string]$Label = 'process')
    try {
        if ($Process -and -not $Process.HasExited) { $Process.Kill($true) }
    } catch {}
}
function Get-CompletedTaskText {
    param($Task, [int]$WaitMilliseconds = 1000)
    if ($null -eq $Task) { return '' }
    try {
        if ($Task.IsCompleted -or $Task.Wait($WaitMilliseconds)) { return [string]$Task.Result }
    } catch {}
    return ''
}
function Get-ExternalToolFailureCode {
    param([string]$ToolName, $Result)
    if ($Result.TimedOut) { return 'FFMPEG_TIMEOUT' }
    if ($Result.Stopped) { return 'FFMPEG_STOPPED' }
    if ([int]$Result.ExitCode -eq 0) { return 'OK' }
    return 'FFMPEG_FAILED'
}
function Save-ReproCommand {
    param([string]$ToolName, [string]$Executable, [array]$ArgumentList, [string]$Stage)
    $script:SavedRepro = [pscustomobject]@{ ToolName = $ToolName; Executable = $Executable; ArgumentList = @($ArgumentList); Stage = $Stage }
    $path = Join-Path $LocalFailed "repro-$Stage.cmd.txt"
    Set-Content -LiteralPath $path -Value 'repro' -Encoding UTF8
    return $path
}

try {
    New-Item -ItemType Directory -Path $LocalFailed -Force | Out-Null
    $fakeFfmpeg = Join-Path $LocalFailed 'fake-ffmpeg.cmd'
    [System.IO.File]::WriteAllLines($fakeFfmpeg, @(
        '@echo off',
        'if "%~1"=="success" (',
        '  1>&2 echo out_time_us=5000000',
        '  ping -n 2 127.0.0.1 >NUL',
        '  1>&2 echo out_time_us=10000000',
        '  ping -n 2 127.0.0.1 >NUL',
        '  exit /b 0',
        ')',
        'if "%~1"=="fail" (',
        '  1>&2 echo out_time_us=1000000',
        '  ping -n 2 127.0.0.1 >NUL',
        '  1>&2 echo simulated encoder failure',
        '  ping -n 2 127.0.0.1 >NUL',
        '  exit /b 7',
        ')',
        'if "%~1"=="timeout" (',
        '  1>&2 echo out_time_us=1000000',
        '  ping -n 30 127.0.0.1 >NUL',
        '  exit /b 0',
        ')',
        'exit /b 2'
    ), [System.Text.UTF8Encoding]::new($false))

    $ok = Invoke-FFmpegWithProgress -FFArgs @('/c', $fakeFfmpeg, 'success') -Label 'TEST-FFMPEG' -InputFile 'input-success.mkv' -TimeoutSeconds 10 -ProgressStage 'encode' -ProgressRoute 'encode' -ReproStage 'encode'
    if (-not $ok) { throw 'successful fake ffmpeg run returned false' }
    if ([int]$script:LastFFmpegExit -ne 0 -or [string]$script:LastFFmpegToolErrorCode -ne 'OK') { throw 'successful fake ffmpeg did not expose OK state' }
    if ($Global:ffmpegProcess) { throw 'global ffmpeg process handle was not cleared after success' }
    $progressValues = @($script:ProgressCalls | Where-Object { $_.Stage -eq 'encode' } | ForEach-Object { $_.Percent })
    foreach ($expectedPercent in @(0, 25, 50, 100)) {
        if ($progressValues -notcontains $expectedPercent) { throw "missing success progress percent $expectedPercent" }
    }
    if (@($script:PipelineEvents | Where-Object { $_.EventType -eq 'tool_started' -and $_.Status -eq 'started' }).Count -ne 1) { throw 'tool_started event missing for success path' }
    if (@($script:PipelineEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Status -eq 'succeeded' -and $_.Data.error_code -eq 'OK' }).Count -ne 1) { throw 'tool_completed succeeded event missing for success path' }
    if ([string]$script:LastFFmpegCommandLine -notmatch [regex]::Escape('-progress pipe:2 -nostats')) { throw 'ffmpeg progress arguments missing from command line' }

    $script:ProgressCalls = @()
    $script:PipelineEvents = @()
    $script:SavedRepro = $null
    $failed = Invoke-FFmpegWithProgress -FFArgs @('/c', $fakeFfmpeg, 'fail') -Label 'TEST-FFMPEG-FAIL' -InputFile 'input-fail.mkv' -TimeoutSeconds 10 -ProgressStage 'encode' -ProgressRoute 'encode' -ReproStage 'encode-fail'
    if ($failed) { throw 'failing fake ffmpeg run returned true' }
    if ([int]$script:LastFFmpegExit -ne 7 -or [string]$script:LastFFmpegToolErrorCode -ne 'FFMPEG_FAILED') { throw 'failing fake ffmpeg did not expose failure state' }
    if ([string]$script:LastFFmpegStderr -notmatch 'simulated encoder failure') { throw 'failing fake ffmpeg stderr was not captured' }
    if (-not $script:LastFFmpegErrorLog -or -not (Test-Path -LiteralPath $script:LastFFmpegErrorLog)) { throw 'failing fake ffmpeg did not write an error log' }
    if (-not $script:LastFFmpegReproPath -or -not (Test-Path -LiteralPath $script:LastFFmpegReproPath)) { throw 'failing fake ffmpeg did not write a repro command' }
    if (-not $script:SavedRepro -or [string]$script:SavedRepro.Stage -ne 'encode-fail') { throw 'failing fake ffmpeg repro stage was not preserved' }
    if (@($script:PipelineEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Status -eq 'failed' -and $_.Data.error_code -eq 'FFMPEG_FAILED' }).Count -ne 1) { throw 'tool_completed failed event missing for failure path' }
    if (@($script:ProgressCalls | Where-Object { $_.Stage -eq 'encode' -and $null -eq $_.Percent }).Count -lt 1) { throw 'failing fake ffmpeg did not clear progress percent' }

    $script:ProgressCalls = @()
    $script:PipelineEvents = @()
    $script:SavedRepro = $null
    $timedOut = Invoke-FFmpegWithProgress -FFArgs @('/c', $fakeFfmpeg, 'timeout') -Label 'TEST-FFMPEG-TIMEOUT' -InputFile 'input-timeout.mkv' -TimeoutSeconds 1 -ProgressStage 'encode' -ProgressRoute 'encode' -ReproStage 'encode-timeout'
    if ($timedOut) { throw 'timed-out fake ffmpeg run returned true' }
    if ([int]$script:LastFFmpegExit -ne -1 -or [string]$script:LastFFmpegToolErrorCode -ne 'FFMPEG_TIMEOUT') { throw 'timed-out fake ffmpeg did not expose timeout state' }
    if ([string]$script:LastFFmpegStderr -notmatch 'KILLED: TIMEOUT after 1s') { throw 'timed-out fake ffmpeg stderr did not record timeout kill' }
    if ($Global:ffmpegProcess) { throw 'global ffmpeg process handle was not cleared after timeout' }
    if (-not $script:LastFFmpegErrorLog -or -not (Test-Path -LiteralPath $script:LastFFmpegErrorLog)) { throw 'timed-out fake ffmpeg did not write an error log' }
    if (-not $script:LastFFmpegReproPath -or -not (Test-Path -LiteralPath $script:LastFFmpegReproPath)) { throw 'timed-out fake ffmpeg did not write a repro command' }
    if (-not $script:SavedRepro -or [string]$script:SavedRepro.Stage -ne 'encode-timeout') { throw 'timed-out fake ffmpeg repro stage was not preserved' }
    if (@($script:PipelineEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Status -eq 'failed' -and $_.Data.error_code -eq 'FFMPEG_TIMEOUT' -and $_.Data.timed_out -eq $true }).Count -ne 1) { throw 'tool_completed failed event missing for timeout path' }
    if (@($script:ProgressCalls | Where-Object { $_.Stage -eq 'encode' -and $null -eq $_.Percent }).Count -lt 1) { throw 'timed-out fake ffmpeg did not clear progress percent' }

    $script:PipelineEvents = @()
    $script:SavedRepro = $null
    $ffmpegPath = Join-Path $LocalFailed 'missing-ffmpeg.exe'
    $runnerFailed = Invoke-FFmpegWithProgress -FFArgs @('-version') -Label 'TEST-FFMPEG-RUNNER-FAIL' -InputFile 'input-runner-fail.mkv' -TimeoutSeconds 10 -ProgressStage 'encode' -ProgressRoute 'encode' -ReproStage 'encode-runner-fail'
    if ($runnerFailed) { throw 'ffmpeg runner exception returned true' }
    if ($Global:ffmpegProcess) { throw 'global ffmpeg process handle was not cleared after runner exception' }
    if ([string]$script:LastFFmpegStderr -notmatch 'RUNNER EXCEPTION') { throw 'runner exception was not captured in stderr state' }
    if ([string]$script:LastFFmpegToolErrorCode -ne 'FFMPEG_FAILED') { throw 'runner exception did not expose failed tool state' }
    if (@($script:PipelineEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Status -eq 'failed' -and $_.Data.runner_exception }).Count -ne 1) { throw 'tool_completed failed event missing for runner exception path' }
    if (-not $script:SavedRepro -or [string]$script:SavedRepro.Stage -ne 'encode-runner-fail') { throw 'runner exception repro stage was not preserved' }
} finally {
    Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PauseFlag -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $LocalFailed -Recurse -Force -ErrorAction SilentlyContinue
}
'@.Replace('__FUNCTIONS__', $ffmpegProgressRunnerFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $ffmpegProgressRunnerCheck

$nativeFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'New-NativeCommandResult',
    'Set-ExternalToolResultProperty',
    'Stop-NativeProcessTree',
    'Add-NativeProcessText',
    'Test-NativeProcessStopRequested',
    'Receive-NativeProcessLine',
    'Invoke-NativeProcess',
    'Invoke-NativeCommand'
)) -join [Environment]::NewLine
$nativeTimeoutCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function DebugLog { param([string]`$Message) }
`$script:StopRequested = `$false
`$StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-stop-' + [guid]::NewGuid().ToString('N') + '.flag')
$nativeFunctions
`$result = Invoke-NativeCommand -FilePath 'cmd.exe' -ArgumentList @('/c', 'ping -n 30 127.0.0.1 >NUL') -TimeoutSeconds 1
if (-not `$result.TimedOut) { throw 'native timeout did not set TimedOut' }
if (`$result.ErrorCode -ne 'NATIVE_TIMEOUT') { throw ('native timeout wrong ErrorCode: ' + `$result.ErrorCode) }
if (`$null -eq `$result.Stdout -or `$null -eq `$result.Stderr) { throw 'native result missing Stdout/Stderr aliases' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $nativeTimeoutCheck

$externalToolFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Format-CommandArgument',
    'Format-NativeCommandLine',
    'Stop-NativeProcessTree',
    'New-NativeCommandResult',
    'Set-ExternalToolResultProperty',
    'Add-NativeProcessText',
    'Test-NativeProcessStopRequested',
    'Receive-NativeProcessLine',
    'Invoke-NativeProcess',
    'Invoke-NativeCommand',
    'Save-ReproCommand',
    'Get-ExternalToolFailureCode',
    'Set-ExternalToolResultProperty',
    'Get-NativeToolDefaultTimeoutSeconds',
    'Invoke-ExternalToolCommand',
    'Invoke-FFprobeCommand'
)) -join [Environment]::NewLine
$externalToolWrapperCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function DebugLog { param([string]`$Message) }
`$script:StopRequested = `$false
`$StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-stop-' + [guid]::NewGuid().ToString('N') + '.flag')
`$td = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-wrapper-' + [guid]::NewGuid().ToString('N'))
`$LocalFailureReports = Join-Path `$td 'reports'
$externalToolFunctions
try {
    New-Item -ItemType Directory -Path `$LocalFailureReports -Force | Out-Null
    `$failed = Invoke-ExternalToolCommand -ToolName 'ffmpeg' -FilePath 'cmd.exe' -ArgumentList @('/c', 'exit 7') -TimeoutSeconds 5 -Stage 'wrapper-failure' -SaveReproOnFailure
    if (`$failed.ExitCode -ne 7) { throw ('wrapper failure exit changed: ' + `$failed.ExitCode) }
    if (`$failed.ToolName -ne 'ffmpeg') { throw 'wrapper did not attach ToolName' }
    if (`$failed.Stage -ne 'wrapper-failure') { throw 'wrapper did not attach Stage' }
    if (`$failed.ToolErrorCode -ne 'FFMPEG_FAILED') { throw ('wrapper failure classification changed: ' + `$failed.ToolErrorCode) }
    if ([string]::IsNullOrWhiteSpace(`$failed.CommandLine) -or `$failed.CommandLine -notmatch 'cmd\.exe') { throw 'wrapper did not attach command line' }
    if (`$null -eq `$failed.DurationSeconds -or [double]`$failed.DurationSeconds -lt 0) { throw 'wrapper did not attach duration' }
    if ([string]::IsNullOrWhiteSpace(`$failed.ReproPath) -or -not (Test-Path -LiteralPath `$failed.ReproPath)) { throw 'wrapper did not save repro command' }

    `$ffprobePath = 'cmd.exe'
    `$ok = Invoke-FFprobeCommand -ArgumentList @('/c', 'exit 0') -TimeoutSeconds 5 -Stage 'wrapper-success'
    if (`$ok.ExitCode -ne 0 -or `$ok.ToolName -ne 'ffprobe' -or `$ok.ToolErrorCode -ne 'OK') { throw 'ffprobe wrapper success metadata changed' }

    `$timeout = Invoke-ExternalToolCommand -ToolName 'ffprobe' -FilePath 'cmd.exe' -ArgumentList @('/c', 'ping -n 30 127.0.0.1 >NUL') -TimeoutSeconds 1 -Stage 'wrapper-timeout'
    if (-not `$timeout.TimedOut) { throw 'external wrapper timeout did not set TimedOut' }
    if (`$timeout.ToolErrorCode -ne 'FFPROBE_TIMEOUT') { throw ('external wrapper timeout classification changed: ' + `$timeout.ToolErrorCode) }
    if ((Get-NativeToolDefaultTimeoutSeconds -ToolName 'ffmpeg') -le 0 -or (Get-NativeToolDefaultTimeoutSeconds -ToolName 'mkvmerge') -le 0 -or (Get-NativeToolDefaultTimeoutSeconds -ToolName 'python') -le 0) { throw 'native tool default timeouts must be explicit nonzero values' }
} finally {
    Remove-Item -LiteralPath `$td -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $externalToolWrapperCheck

$audioFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'New-NativeCommandResult',
    'Get-ExternalToolFailureCode',
    'Set-ExternalToolResultProperty',
    'Invoke-ExternalToolCommand',
    'Invoke-FFprobeCommand',
    'Get-FileOverrideAudioSettings',
    'Test-AudioTrackKeptByOverride',
    'Get-AudioTrackTitleOverride',
    'Get-MediaAudioCodecFlacName',
    'Get-MediaAudioCodecFidelityRankValue',
    'Get-MediaAudioCodecDisplayLabel',
    'Get-MediaPipelineAudioPassthroughProfileNames',
    'Get-MediaPipelineAudioPassthroughProfileDefault',
    'Resolve-MediaPipelineAudioPassthroughProfile',
    'Get-MediaPipelineAudioPassthroughProfileCodecs',
    'Get-AudioDecisionOutputChannelCount',
    'Get-AudioDecisionPreferredDefaultIndex',
    'New-AudioOmitAllDecisionRecord',
    'Build-AudioStreamDecisionPlan',
    'Normalize-AudioLanguagePreferenceValue',
    'Get-NormalizedPreferredAudioLanguages',
    'Get-AudioCodecFidelityRank',
    'Get-AudioFidelityScore',
    'Test-IsPcmAudioCodec',
    'Get-EffectiveAudioTranscodeCodec',
    'Get-EffectiveAudioTranscodeBitrate',
    'Get-EffectiveAudioTranscodeAutoBitrateByChannels',
    'Get-AudioTranscodeBitrateForChannels',
    'Get-EffectiveAudioDownmixMode',
    'Get-EffectiveAudioMaxChannels',
    'Get-EffectiveAllowNoAudio',
    'Get-EffectiveAudioPassthroughProfile',
    'Get-EffectiveCompatibleAudioCodecs',
    'Get-TranscodedAudioChannelCount',
    'Get-PreferredDefaultAudioIndex',
    'Set-LastAudioDecisionRecords',
    'Get-LastAudioDecisionRecords',
    'Build-AudioArgs'
)) -join [Environment]::NewLine
$audioCodecCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function DebugLog { param([string]`$Message) }
$audioFunctions
if (-not (Test-IsPcmAudioCodec 'pcm_s16le')) { throw 'pcm_s16le was not detected as PCM audio' }
if (-not (Test-IsPcmAudioCodec 'A_PCM/INT/LIT')) { throw 'A_PCM/INT/LIT was not detected as PCM audio' }
if (Test-IsPcmAudioCodec 'eac3') { throw 'EAC3 was incorrectly detected as PCM audio' }
`$script:PreferredDefaultAudioLanguages = @('jpn', 'eng')
`$PreferredDefaultAudioLanguages = `$script:PreferredDefaultAudioLanguages
`$script:AudioPassthroughProfile = 'custom_codec_list'
`$CompatibleAudioCodecs = @('ac3', 'eac3', 'aac', 'truehd', 'flac')
`$ffprobePath = 'stub-ffprobe.exe'
function Invoke-NativeCommand {
    param([string]`$FilePath, [string[]]`$ArgumentList, [int]`$TimeoutSeconds)
    `$payload = @{
        streams = @(
            @{ index = 0; codec_name = 'ac3'; channels = 6; channel_layout = '5.1(side)'; tags = @{ language = 'eng'; title = 'Director Commentary' }; disposition = @{ forced = 0; default = 1 } },
            @{ index = 1; codec_name = 'pcm_s16le'; channels = 2; channel_layout = 'stereo'; tags = @{ language = 'jpn'; title = '' }; disposition = @{ forced = 1; default = 0 } },
            @{ index = 2; codec_name = 'truehd'; channels = 8; channel_layout = '7.1'; tags = @{ language = 'eng'; title = 'Main Audio' }; disposition = @{ forced = 0; default = 0 } }
        )
    }
    return [pscustomobject]@{ ExitCode = 0; Output = (`$payload | ConvertTo-Json -Depth 8); Error = ''; TimedOut = `$false; Stopped = `$false }
}
`$audioArgsResult = @(Build-AudioArgs 'source.mkv')
`$joined = `$audioArgsResult -join '|'
foreach (`$expected in @('-map|0:a:0', '-map|0:a:1', '-map|0:a:2')) {
    if (`$joined -notmatch [regex]::Escape(`$expected)) { throw ('audio map missing: ' + `$expected) }
}
if (`$joined -notmatch [regex]::Escape('-c:a:0|copy')) { throw 'compatible AC3 commentary track should be copied' }
if (`$joined -notmatch [regex]::Escape('-c:a:1|eac3|-b:a:1|640k|-ac:1|2')) { throw 'PCM track should be standardized to 2.0 EAC3 640k' }
if (`$joined -notmatch [regex]::Escape('-c:a:2|copy')) { throw 'compatible TrueHD track should be copied' }
if (`$joined -notmatch [regex]::Escape('-metadata:s:a:0|title=English - 5.1 AC3 [Commentary]')) { throw 'commentary title metadata changed' }
if (`$joined -notmatch [regex]::Escape('-metadata:s:a:1|title=Japanese - 2.0 EAC3')) { throw 'PCM standardized title metadata changed' }
if (`$joined -notmatch [regex]::Escape('-metadata:s:a:2|title=English - 7.1 TrueHD')) { throw 'TrueHD title metadata changed' }
if (`$joined -notmatch [regex]::Escape('-disposition:a:1|default+forced')) { throw 'preferred forced Japanese track should become default+forced' }
if (`$joined -match [regex]::Escape('-disposition:a:0|default')) { throw 'commentary track should not become default' }
`$audioDecisions = @(Get-LastAudioDecisionRecords)
if (`$audioDecisions.Count -ne 3) { throw ('expected 3 audio decision records, got ' + `$audioDecisions.Count) }
if (`$audioDecisions[0].action -ne 'copy' -or -not `$audioDecisions[0].is_commentary) { throw 'copied commentary audio decision not recorded' }
if (`$audioDecisions[1].action -ne 'transcode' -or `$audioDecisions[1].reason -ne 'PCM standardization' -or -not `$audioDecisions[1].is_default) { throw 'PCM/default audio decision not recorded' }
if (`$audioDecisions[2].output_codec -ne 'truehd') { throw 'copied TrueHD output codec decision not recorded' }
if (`$audioDecisions[2].passthrough_profile -ne 'custom_codec_list') { throw 'audio passthrough profile was not recorded in decision output' }
`$script:AudioPassthroughProfile = 'compatibility'
`$compatProfileCodecs = @(Get-EffectiveCompatibleAudioCodecs)
if (`$compatProfileCodecs -contains 'truehd' -or `$compatProfileCodecs -contains 'flac') { throw 'compatibility audio passthrough profile should exclude lossless/high-transcode-risk codecs' }
if (`$compatProfileCodecs -notcontains 'ac3' -or `$compatProfileCodecs -notcontains 'eac3') { throw 'compatibility audio passthrough profile should include AC3/EAC3' }
`$script:AudioPassthroughProfile = 'lossless_passthrough'
`$losslessProfileCodecs = @(Get-EffectiveCompatibleAudioCodecs)
if (`$losslessProfileCodecs -notcontains 'truehd' -or `$losslessProfileCodecs -notcontains 'flac' -or `$losslessProfileCodecs -notcontains 'dts') { throw 'lossless audio passthrough profile should include TrueHD/FLAC/DTS' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $audioCodecCheck

$audioMissingCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function DebugLog { param([string]`$Message) }
$audioFunctions
`$script:PreferredDefaultAudioLanguages = @('eng')
`$PreferredDefaultAudioLanguages = `$script:PreferredDefaultAudioLanguages
`$CompatibleAudioCodecs = @('ac3', 'eac3', 'aac')
`$ffprobePath = 'stub-ffprobe.exe'
function Invoke-NativeCommand {
    param([string]`$FilePath, [string[]]`$ArgumentList, [int]`$TimeoutSeconds)
    if ((`$ArgumentList -join '|') -match 'default=noprint_wrappers') {
        return [pscustomobject]@{ ExitCode = 0; Output = ''; Error = ''; TimedOut = `$false; Stopped = `$false }
    }
    `$payload = @{ streams = @() }
    return [pscustomobject]@{ ExitCode = 0; Output = (`$payload | ConvertTo-Json -Depth 4); Error = ''; TimedOut = `$false; Stopped = `$false }
}
try {
    `$null = @(Build-AudioArgs 'silent.mkv')
    throw 'Build-AudioArgs did not fail for no-audio input'
} catch {
    if ([string]`$_.Exception.Message -notmatch 'SOURCE_MEDIA_AUDIO_MISSING') {
        throw ('unexpected no-audio failure: ' + `$_.Exception.Message)
    }
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $audioMissingCheck

$audioMetadataProbeFailureCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function DebugLog { param([string]`$Message) }
$audioFunctions
`$script:PreferredDefaultAudioLanguages = @('eng')
`$PreferredDefaultAudioLanguages = `$script:PreferredDefaultAudioLanguages
`$CompatibleAudioCodecs = @('ac3', 'eac3', 'aac')
`$ffprobePath = 'stub-ffprobe.exe'
function Invoke-NativeCommand {
    param([string]`$FilePath, [string[]]`$ArgumentList, [int]`$TimeoutSeconds)
    `$joined = `$ArgumentList -join '|'
    if (`$joined -match 'stream=index,codec_name') {
        return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'metadata probe failed'; TimedOut = `$false; Stopped = `$false }
    }
    if (`$joined -match 'stream=codec_type') {
        return [pscustomobject]@{ ExitCode = 0; Output = 'audio'; Error = ''; TimedOut = `$false; Stopped = `$false }
    }
    throw ('unexpected ffprobe args: ' + `$joined)
}
try {
    `$null = @(Build-AudioArgs 'metadata-failed.mkv')
    throw 'Build-AudioArgs did not fail when audio metadata probe failed'
} catch {
    if ([string]`$_.Exception.Message -notmatch 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') {
        throw ('unexpected metadata-probe failure: ' + `$_.Exception.Message)
    }
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $audioMetadataProbeFailureCheck

$hdrProbeFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-HDRState',
    'Test-IsHDR'
)) -join [Environment]::NewLine
$hdrProbeCheck = @"
`$ErrorActionPreference = 'Stop'
$hdrProbeFunctions
function Invoke-FFprobeCommand {
    param([string[]]`$ArgumentList, [int]`$TimeoutSeconds, [string]`$Stage)
    return `$script:HdrProbeResult
}
`$script:HdrProbeResult = [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'probe failed'; TimedOut = `$false; Stopped = `$false }
`$failedState = Get-HDRState 'broken.mkv'
if ([bool]`$failedState.Known) { throw 'HDR ffprobe failure should produce an unknown state' }
try {
    `$null = Test-IsHDR 'broken.mkv'
    throw 'Test-IsHDR did not fail for unknown HDR state'
} catch {
    if ([string]`$_.Exception.Message -notmatch 'HDR_DETECTION_UNKNOWN') { throw ('unexpected HDR failure: ' + `$_.Exception.Message) }
}
`$script:HdrProbeResult = [pscustomobject]@{ ExitCode = 0; Output = "smpte2084`n"; Error = ''; TimedOut = `$false; Stopped = `$false }
if (-not (Test-IsHDR 'hdr.mkv')) { throw 'HDR color_transfer smpte2084 should be detected as HDR' }
`$script:HdrProbeResult = [pscustomobject]@{ ExitCode = 0; Output = "bt709`n"; Error = ''; TimedOut = `$false; Stopped = `$false }
if (Test-IsHDR 'sdr.mkv') { throw 'SDR color_transfer bt709 should not be detected as HDR' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $hdrProbeCheck

$folderPolicyFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-FolderPolicyProperty',
    'ConvertTo-FolderPolicyBool',
    'ConvertTo-FolderPolicyStringArray',
    'ConvertTo-FolderPolicyLanguageArray',
    'Get-FolderPolicyFullPath',
    'Test-FolderPolicyPathWithinRoot',
    'Get-FolderPolicySearchRoots',
    'Find-MediaPipelineFolderPolicy',
    'Read-MediaPipelineFolderPolicy',
    'ConvertTo-MediaPipelineFolderPolicyOverrides',
    'ConvertTo-FolderPolicyTopologyItemKey',
    'Get-FolderPolicyTopologyItems',
    'ConvertTo-FolderPolicyTopologyKey',
    'Get-FolderPolicyRuntimeStreamTopology',
    'Test-FolderPolicyTopologyMatches',
    'Test-FolderPolicyValidationAllowsSource',
    'Resolve-FolderPolicyOverrides',
    'Merge-MediaPipelineActiveOverrides',
    'Get-ActiveFolderPolicyMetadata'
)) -join [Environment]::NewLine
$folderPolicySubtitleFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-MediaSubtitleCodecAssNames',
    'Get-MediaSubtitleCodecSrtNames',
    'ConvertTo-SubtitleBool',
    'Get-EffectiveSubtitleSwitch',
    'Get-SubtitleLanguagePolicy',
    'New-SubtitleRoutingDecision',
    'Set-LastSubtitleDecisionRecords',
    'Get-LastSubtitleDecisionRecords',
    'New-SubtitleDecisionRecord',
    'Get-SubtitleRoutingPolicyChain',
    'Resolve-SubtitleRoutingDecision'
)) -join [Environment]::NewLine
$folderPolicyOverrideCheck = @'
$ErrorActionPreference = 'Stop'
function Write-Log { param([string]$Message, [string]$Level = 'INFO') }
function DebugLog { param([string]$Message) }
__FOLDER_POLICY_FUNCTIONS__
__AUDIO_FUNCTIONS__
__SUBTITLE_FUNCTIONS__

$script:FolderPolicySidecarName = 'mediapipeline.folder.json'
$script:FolderPolicySchemaVersion = 'folder_policy.v1'
$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-folder-policy-' + [guid]::NewGuid().ToString('N'))
try {
    $script:SourceTV = Join-Path $root 'SourceTV'
    $episodeDir = Join-Path $script:SourceTV 'TVSHOWSAMPLE\Season 01'
    New-Item -ItemType Directory -Path $episodeDir -Force | Out-Null
    $media = Join-Path $episodeDir 'TVSHOWSAMPLE - S01E22.mkv'
    Set-Content -LiteralPath $media -Value 'media-placeholder' -Encoding ASCII
    $policyPath = Join-Path $episodeDir $script:FolderPolicySidecarName
    $policy = [ordered]@{
        schema_version = 'folder_policy.v1'
        folder = $episodeDir
        audio = [ordered]@{
            passthrough_codecs = @('truehd')
            preferred_default_languages = @('jpn')
            transcode_codec = 'aac'
            transcode_bitrate = '192k'
            downmix_mode = 'stereo'
            max_channels = 2
        }
        subtitles = [ordered]@{
            ass = [ordered]@{ enabled = $false; languages = @('eng'); drop_after_conversion = $false }
            tx3g = [ordered]@{ enabled = $false; languages = @('jpn'); drop_after_conversion = $true }
            bdpgs = [ordered]@{ enabled = $true; languages = @('eng'); drop_after_conversion = $true }
        }
        routing = [ordered]@{
            prefer_route = 'encode'
            max_video_bitrate_mbps = 12
            max_resolution_height = 1080
            allowed_video_codecs = @('h264', 'hevc')
            plex_strict_mode = $true
            allow_unsafe_forced_remux = $true
            reason = 'folder policy test route hint'
        }
        validation = [ordered]@{
            sample_file = 'TVSHOWSAMPLE - S01E22.mkv'
            require_uniform_stream_topology = $true
        }
    }
    $policy | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $policyPath -Encoding UTF8

    $folderOverrides = Resolve-FolderPolicyOverrides -SourceFile (Get-Item -LiteralPath $media)
    if (-not $folderOverrides) { throw 'folder policy sidecar should override audio and subtitle policy' }
    if ($folderOverrides['FolderPolicyPath'] -ne $policyPath) { throw 'folder policy path was not preserved' }
    if ($folderOverrides['PreferredDefaultAudioLanguages'][0] -ne 'jpn') { throw 'folder policy preferred audio language not loaded' }
    if ($folderOverrides['CompatibleAudioCodecs'][0] -ne 'truehd') { throw 'folder policy compatible audio codecs not loaded' }
    if ($folderOverrides['AudioTranscodeCodec'] -ne 'aac' -or $folderOverrides['AudioTranscodeBitrate'] -ne '192k' -or $folderOverrides['AudioDownmixMode'] -ne 'stereo' -or $folderOverrides['AudioMaxChannels'] -ne 2) {
        throw 'folder policy audio transcode settings not loaded'
    }
    if ([bool]$folderOverrides['ConvertAssToSrt'] -or [bool]$folderOverrides['ConvertTx3gToSrt'] -or -not [bool]$folderOverrides['ConvertBdpgsToSrt']) {
        throw 'folder policy subtitle conversion switches not loaded'
    }
    if (-not [bool]$folderOverrides['DropTx3gAfterConversion'] -or -not [bool]$folderOverrides['DropBdpgsAfterConversion']) {
        throw 'folder policy subtitle drop switches not loaded'
    }
    if ($folderOverrides['RoutePrefer'] -ne 'encode' -or [double]$folderOverrides['RouteMaxVideoBitrateMbps'] -ne 12 -or [int]$folderOverrides['RouteMaxResolutionHeight'] -ne 1080 -or -not [bool]$folderOverrides['RoutePlexStrictMode'] -or -not [bool]$folderOverrides['RouteAllowUnsafeForcedRemux']) {
        throw 'folder policy routing hints not loaded'
    }
    if (@($folderOverrides['RouteAllowedVideoCodecs']) -notcontains 'hevc' -or $folderOverrides['RoutePolicyReason'] -ne 'folder policy test route hint') {
        throw 'folder policy routing codec/reason hints not loaded'
    }

    $showOverrides = @{
        ShowName = 'Canonical Show'
        PreferredDefaultAudioLanguages = @('eng')
        ConvertTx3gToSrt = $true
        ConvertBdpgsToSrt = $false
        FlacAsCompatible = $true
    }
    $script:ActiveOverrides = Merge-MediaPipelineActiveOverrides -Base $showOverrides -Override $folderOverrides
    if ($script:ActiveOverrides['ShowName'] -ne 'Canonical Show') { throw 'show override metadata should survive folder policy merge' }
    if ($script:ActiveOverrides['PreferredDefaultAudioLanguages'][0] -ne 'jpn') { throw 'folder policy should win over show audio language override' }
    if (@($script:ActiveOverrides['CompatibleAudioCodecs']) -notcontains 'truehd') { throw ('folder policy compatible codec override missing after merge: ' + (@($script:ActiveOverrides['CompatibleAudioCodecs']) -join ',')) }
    if ([bool]$script:ActiveOverrides['ConvertTx3gToSrt']) { throw 'folder policy should win over show tx3g override' }
    if (-not [bool]$script:ActiveOverrides['ConvertBdpgsToSrt']) { throw 'folder policy should win over show bdpgs override' }
    $folderPolicyMetadata = Get-ActiveFolderPolicyMetadata
    if (-not $folderPolicyMetadata.applied -or [string]$folderPolicyMetadata.path -ne $policyPath) { throw 'active folder policy metadata did not preserve policy path' }
    if (@($folderPolicyMetadata.keys) -notcontains 'AudioTranscodeCodec' -or @($folderPolicyMetadata.keys) -notcontains 'ConvertBdpgsToSrt' -or @($folderPolicyMetadata.keys) -notcontains 'RoutePrefer') { throw 'active folder policy metadata did not preserve applied keys' }
    if ([string]$folderPolicyMetadata.overrides.audio_transcode_codec -ne 'aac' -or -not [bool]$folderPolicyMetadata.overrides.convert_bdpgs_to_srt) { throw 'active folder policy metadata did not preserve effective override values' }
    if ([string]$folderPolicyMetadata.overrides.routing_prefer_route -ne 'encode' -or @($folderPolicyMetadata.overrides.routing_allowed_video_codecs) -notcontains 'hevc' -or -not [bool]$folderPolicyMetadata.overrides.routing_allow_unsafe_forced_remux) { throw 'active folder policy metadata did not preserve routing override values' }

    $script:PreferredDefaultAudioLanguages = @('eng')
    $script:AudioTranscodeCodec = 'eac3'
    $script:AudioTranscodeBitrate = '640k'
    $script:AudioDownmixMode = 'max_channels'
    $script:AudioMaxChannels = 6
    $script:ConvertTx3gToSrt = $true
    $script:ConvertBdpgsToSrt = $false
    $script:SubKeepLanguages = @('eng')
    $SubKeepLanguages = $script:SubKeepLanguages
    $preferred = @(Get-NormalizedPreferredAudioLanguages)
    if ($preferred.Count -ne 1 -or $preferred[0] -ne 'jpn') { throw 'folder policy preferred audio language did not drive runtime audio selection' }
    if ((Get-EffectiveAudioTranscodeCodec) -ne 'aac') { throw 'folder policy audio codec did not drive runtime audio settings' }
    if ((Get-EffectiveAudioTranscodeBitrate) -ne '192k') { throw 'folder policy bitrate did not drive runtime audio settings' }
    if ((Get-EffectiveAudioDownmixMode) -ne 'stereo') { throw 'folder policy downmix did not drive runtime audio settings' }
    if ((Get-EffectiveAudioMaxChannels) -ne 2) { throw 'folder policy max channels did not drive runtime audio settings' }
    $effectiveCompat = @(Get-EffectiveCompatibleAudioCodecs)
    if ($effectiveCompat -notcontains 'truehd') { throw ('folder policy compatible codec list did not drive runtime audio settings: ' + ($effectiveCompat -join ',')) }
    if ($effectiveCompat -contains 'ac3') { throw ('folder policy compatible codec list should narrow global passthrough behavior: ' + ($effectiveCompat -join ',')) }

    $CompatibleAudioCodecs = @('ac3', 'eac3', 'aac')
    $ffprobePath = 'stub-ffprobe.exe'
    function Invoke-NativeCommand {
        param([string]$FilePath, [string[]]$ArgumentList, [int]$TimeoutSeconds)
        $payload = @{
            streams = @(
                @{ index = 0; codec_name = 'truehd'; channels = 8; channel_layout = '7.1'; tags = @{ language = 'eng'; title = 'Main' }; disposition = @{ forced = 0; default = 1 } },
                @{ index = 1; codec_name = 'dts'; channels = 6; channel_layout = '5.1'; tags = @{ language = 'jpn'; title = '' }; disposition = @{ forced = 0; default = 0 } }
            )
        }
        return [pscustomobject]@{ ExitCode = 0; Output = ($payload | ConvertTo-Json -Depth 8); Error = ''; TimedOut = $false; Stopped = $false }
    }
    $audioArgs = @(Build-AudioArgs 'source.mkv')
    $joinedAudio = $audioArgs -join '|'
    if ($joinedAudio -notmatch [regex]::Escape('-c:a:0|copy')) { throw ('folder policy compatible codec list should copy TrueHD; got: ' + $joinedAudio) }
    if ($joinedAudio -notmatch [regex]::Escape('-c:a:1|aac|-b:a:1|192k|-ac:1|2')) { throw ('folder policy audio transcode settings should apply to incompatible audio; got: ' + $joinedAudio) }

    $tx3gLanguages = @(Get-SubtitleLanguagePolicy -IsTx3g:$true)
    if ($tx3gLanguages.Count -ne 1 -or $tx3gLanguages[0] -ne 'jpn') { throw 'folder policy tx3g language list did not drive subtitle policy' }
    $assLanguages = @(Get-SubtitleLanguagePolicy -IsAss:$true)
    if ($assLanguages.Count -ne 1 -or $assLanguages[0] -ne 'eng') { throw 'folder policy ASS language list did not drive subtitle policy' }
    $tx3gDecision = Resolve-SubtitleRoutingDecision -Entry @{
        Codec = 'mov_text'; IsTx3g = $true; IsBdpgs = $false; Stream = [pscustomobject]@{ index = 2 }; Lang = 'jpn'; Title = 'Japanese'; IsSupplemental = $false
    }
    if ($tx3gDecision.Action -ne 'Drop') { throw 'folder policy disabled tx3g conversion with drop-after-conversion should drop tx3g stream' }
    $bdpgsDecision = Resolve-SubtitleRoutingDecision -Entry @{
        Codec = 'hdmv_pgs_subtitle'; IsTx3g = $false; IsBdpgs = $true; Stream = [pscustomobject]@{ index = 3 }; Lang = 'eng'; Title = 'English'; IsSupplemental = $false
    }
    if ($bdpgsDecision.Action -ne 'ConvertBdpgs') { throw 'folder policy enabled bdpgs conversion should route BDPGS to OCR' }
    $assDecision = Resolve-SubtitleRoutingDecision -Entry @{
        Codec = 'ass'; IsTx3g = $false; IsBdpgs = $false; Stream = [pscustomobject]@{ index = 4 }; Lang = 'eng'; Title = 'English'; IsSupplemental = $false
    }
    if ($assDecision.Action -ne 'Keep') { throw 'folder policy disabled ASS conversion should keep ASS stream' }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
'@
$folderPolicyOverrideCheck = $folderPolicyOverrideCheck.Replace('__FOLDER_POLICY_FUNCTIONS__', $folderPolicyFunctions)
$folderPolicyOverrideCheck = $folderPolicyOverrideCheck.Replace('__AUDIO_FUNCTIONS__', $audioFunctions)
$folderPolicyOverrideCheck = $folderPolicyOverrideCheck.Replace('__SUBTITLE_FUNCTIONS__', $folderPolicySubtitleFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $folderPolicyOverrideCheck

$folderPolicyTopologyRuntimeCheck = @'
$ErrorActionPreference = 'Stop'
function Write-Log { param([string]$Message, [string]$Level = 'INFO') $script:FolderPolicyLogs += ,([pscustomobject]@{ Message = $Message; Level = $Level }) }
function DebugLog { param([string]$Message) }
__FOLDER_POLICY_FUNCTIONS__

function Invoke-FFprobeCommand {
    param([string[]]$ArgumentList, [int]$TimeoutSeconds, [string]$Stage)
    $sourcePath = [string]$ArgumentList[-1]
    $audioCodec = if ($sourcePath -match 'mismatch') { 'aac' } else { 'ac3' }
    $payload = @{
        streams = @(
            @{ index = 0; codec_type = 'video'; codec_name = 'hevc' },
            @{ index = 1; codec_type = 'audio'; codec_name = $audioCodec; channels = 6; tags = @{ language = 'eng' } },
            @{ index = 2; codec_type = 'subtitle'; codec_name = 'mov_text'; tags = @{ language = 'eng' } }
        )
    }
    return [pscustomobject]@{ ExitCode = 0; Output = ($payload | ConvertTo-Json -Depth 8); Error = ''; TimedOut = $false; Stopped = $false }
}

$script:FolderPolicySidecarName = 'mediapipeline.folder.json'
$script:FolderPolicySchemaVersion = 'folder_policy.v1'
$script:FolderPolicyLogs = @()
$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-folder-policy-runtime-' + [guid]::NewGuid().ToString('N'))
try {
    $script:SourceTV = Join-Path $root 'SourceTV'
    $episodeDir = Join-Path $script:SourceTV 'Show\Season 01'
    New-Item -ItemType Directory -Path $episodeDir -Force | Out-Null
    $matchMedia = Join-Path $episodeDir 'match.mkv'
    $mismatchMedia = Join-Path $episodeDir 'mismatch.mkv'
    Set-Content -LiteralPath $matchMedia -Value 'x' -Encoding ASCII
    Set-Content -LiteralPath $mismatchMedia -Value 'x' -Encoding ASCII
    [ordered]@{
        schema_version = 'folder_policy.v1'
        folder = $episodeDir
        routing = [ordered]@{ prefer_route = 'encode'; reason = 'runtime topology test' }
        validation = [ordered]@{
            sample_file = 'match.mkv'
            require_uniform_stream_topology = $true
            expected_topology = [ordered]@{
                audio = @(@('ac3', 'eng', 6))
                subtitles = @(@('mov_text', 'eng'))
            }
        }
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $episodeDir $script:FolderPolicySidecarName) -Encoding UTF8

    $matchOverrides = Resolve-FolderPolicyOverrides -SourceFile (Get-Item -LiteralPath $matchMedia)
    if (-not $matchOverrides -or [string]$matchOverrides['RoutePrefer'] -ne 'encode') { throw 'matching runtime topology should allow folder policy overrides' }
    $mismatchOverrides = Resolve-FolderPolicyOverrides -SourceFile (Get-Item -LiteralPath $mismatchMedia)
    if ($mismatchOverrides) { throw 'mismatched runtime topology should suppress folder policy overrides' }
    if (@($script:FolderPolicyLogs | Where-Object { $_.Message -match 'stream topology differs' }).Count -lt 1) { throw 'runtime topology mismatch should be logged for diagnostics' }
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
'@
$folderPolicyTopologyRuntimeCheck = $folderPolicyTopologyRuntimeCheck.Replace('__FOLDER_POLICY_FUNCTIONS__', $folderPolicyFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $folderPolicyTopologyRuntimeCheck

$tx3gFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-MediaContainerMkvExtensionName',
    'Get-MediaContainerMp4FamilyNames',
    'Get-MediaContainerMatroskaFamilyNames',
    'Get-MediaSubtitleCodecMovTextName',
    'Get-MediaSubtitleCodecBdpgsNames',
    'Test-IsTx3gSubtitleStream',
    'Test-IsBdpgsSubtitleStream',
    'Resolve-SubtitleConfiguredPath',
    'Resolve-BdpgsOcrTessdataPath',
    'Get-NormalizedSubtitleLanguage',
    'Get-SafeSubtitleFileToken',
    'Get-ConfiguredOutputContainerName',
    'Test-CanPreserveTx3gInFfmpegOutput',
    'Test-CanPreserveBdpgsInFfmpegOutput',
    'Get-ConvertedSrtCodecForFfmpegOutput',
    'Resolve-BdpgsOcrLanguage',
    'Test-SrtFileUsable',
    'Resolve-Tx3gSrtDestination'
)) -join [Environment]::NewLine
$tx3gSubtitleCheck = @"
`$ErrorActionPreference = 'Stop'
$tx3gFunctions
`$movText = [pscustomobject]@{ codec_name = 'mov_text'; codec_tag_string = ''; codec_long_name = '' }
`$tx3gTag = [pscustomobject]@{ codec_name = 'unknown'; codec_tag_string = 'tx3g'; codec_long_name = '' }
`$textTag = [pscustomobject]@{ codec_name = 'unknown'; codec_tag_string = 'text'; codec_tag = ''; codec_long_name = '' }
`$sbtlTag = [pscustomobject]@{ codec_name = 'unknown'; codec_tag_string = 'sbtl'; codec_tag = ''; codec_long_name = '' }
`$textHexTag = [pscustomobject]@{ codec_name = 'unknown'; codec_tag_string = ''; codec_tag = '0x74786574'; codec_long_name = '' }
`$timedText = [pscustomobject]@{ codec_name = 'unknown'; codec_tag_string = ''; codec_long_name = 'MPEG-4 Timed Text subtitle' }
`$bdpgs = [pscustomobject]@{ codec_name = 'hdmv_pgs_subtitle'; codec_tag_string = ''; codec_long_name = 'HDMV Presentation Graphic Stream subtitles' }
`$ass = [pscustomobject]@{ codec_name = 'ass'; codec_tag_string = ''; codec_long_name = 'ASS subtitle' }
if (-not (Test-IsTx3gSubtitleStream `$movText)) { throw 'mov_text stream was not detected as tx3g' }
if (-not (Test-IsTx3gSubtitleStream `$tx3gTag)) { throw 'tx3g codec tag was not detected' }
if (-not (Test-IsTx3gSubtitleStream `$textTag)) { throw 'text codec tag was not detected as tx3g/timed text' }
if (-not (Test-IsTx3gSubtitleStream `$sbtlTag)) { throw 'sbtl codec tag was not detected as tx3g/timed text' }
if (-not (Test-IsTx3gSubtitleStream `$textHexTag)) { throw 'text codec_tag hex was not detected as tx3g/timed text' }
if (-not (Test-IsTx3gSubtitleStream `$timedText)) { throw 'timed text long name was not detected' }
if (Test-IsTx3gSubtitleStream `$ass) { throw 'ASS stream was incorrectly detected as tx3g' }
if (-not (Test-IsBdpgsSubtitleStream `$bdpgs)) { throw 'HDMV PGS stream was not detected as BDPGS' }
if (Test-IsBdpgsSubtitleStream `$ass) { throw 'ASS stream was incorrectly detected as BDPGS' }
`$script:OutputContainer = 'mp4'
if (-not (Test-CanPreserveTx3gInFfmpegOutput)) { throw 'mp4 output should allow original tx3g preservation' }
if (Test-CanPreserveBdpgsInFfmpegOutput) { throw 'mp4 output should not preserve BDPGS image subtitles' }
if ((Get-ConvertedSrtCodecForFfmpegOutput) -ne 'mov_text') { throw 'mp4 converted SRT subtitles should be encoded as mov_text' }
`$script:OutputContainer = 'mkv'
if (Test-CanPreserveTx3gInFfmpegOutput) { throw 'mkv output should not claim original tx3g preservation' }
if (-not (Test-CanPreserveBdpgsInFfmpegOutput)) { throw 'mkv output should preserve BDPGS image subtitles' }
if ((Get-ConvertedSrtCodecForFfmpegOutput) -ne 'copy') { throw 'mkv converted SRT subtitles should be copied as SRT' }
if ((Resolve-BdpgsOcrLanguage 'en') -ne 'eng') { throw 'BDPGS OCR language mapping for en failed' }

`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-tx3g-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$scriptDir = `$root
    `$tessdataDir = Join-Path `$root 'Tools\PgsToSrt\tessdata'
    New-Item -ItemType Directory -Path `$tessdataDir -Force | Out-Null
    `$script:BdpgsOcrTessdataPath = 'Tools\PgsToSrt\tessdata'
    `$tessdata = Resolve-BdpgsOcrTessdataPath
    if (-not `$tessdata.Ok) { throw ('relative tessdata did not resolve: ' + `$tessdata.Reason) }
    if (-not [System.IO.Path]::IsPathRooted(`$tessdata.Path)) { throw 'relative tessdata path was not converted to an absolute path' }

    `$mediaPath = Join-Path `$root 'Movie.mkv'
    Set-Content -LiteralPath `$mediaPath -Value 'placeholder' -Encoding UTF8
    `$script:Tx3gTreatForcedAsSeparate = `$true
    `$script:Tx3gPreserveExistingSrt = `$true
    `$script:ReprocessAll = `$false
    `$entry = @{
        Lang = ''
        RawTitle = 'English'
        Stream = [pscustomobject]@{ index = 5 }
        IsForced = `$true
        IsSdh = `$false
    }
    `$resolved = Resolve-Tx3gSrtDestination -MediaOutputPath `$mediaPath -Entry `$entry -UsedPaths @{}
    if ((Split-Path -Leaf `$resolved.Path) -ne 'Movie.und.forced.tx3g.srt') { throw ('unexpected tx3g SRT name: ' + (Split-Path -Leaf `$resolved.Path)) }

    `$goodSrt = "1`r`n00:00:01,000 --> 00:00:02,000`r`nhello`r`n"
    `$existing = Join-Path `$root 'Movie.und.forced.srt'
    [System.IO.File]::WriteAllText(`$existing, `$goodSrt, [System.Text.Encoding]::UTF8)
    `$resolvedExisting = Resolve-Tx3gSrtDestination -MediaOutputPath `$mediaPath -Entry `$entry -UsedPaths @{}
    if (`$resolvedExisting.Status -ne 'existing') { throw 'existing generic SRT was not preserved' }
    if (`$resolvedExisting.Path -ne `$existing) { throw 'wrong existing SRT was selected' }

    `$valid = Test-SrtFileUsable -Path `$existing
    if (-not `$valid.Ok -or `$valid.CueCount -ne 1) { throw 'valid SRT did not pass validation' }
    `$empty = Join-Path `$root 'empty.srt'
    Set-Content -LiteralPath `$empty -Value '' -Encoding UTF8
    if ((Test-SrtFileUsable -Path `$empty).Ok) { throw 'empty SRT passed validation' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $tx3gSubtitleCheck

$subtitleCleanupFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'ConvertTo-Milliseconds',
    'New-NativeCommandResult',
    'Get-ExternalToolFailureCode',
    'Set-ExternalToolResultProperty',
    'Invoke-ExternalToolCommand',
    'Invoke-FFprobeCommand',
    'Invoke-FFmpegCommand',
    'Invoke-PythonToolCommand',
    'Invoke-BdpgsOcrCommand',
    'Get-MediaContainerMkvExtensionName',
    'Get-MediaContainerMp4FamilyNames',
    'Get-MediaContainerMatroskaFamilyNames',
    'Get-MediaSubtitleCodecMovTextName',
    'Get-MediaSubtitleCodecAssNames',
    'Get-MediaSubtitleCodecSrtNames',
    'Get-MediaSubtitleCodecBdpgsNames',
    'Get-SubtitleOperationTimeoutSeconds',
    'Get-FileOverrideSubtitleSettings',
    'Test-SubtitleTrackKeptByOverride',
    'Get-SubtitleTrackTitleOverride',
    'Normalize-FailureCode',
    'Get-FailureCategory',
    'New-StandardFailureRecord',
    'ConvertTo-SubtitleBool',
    'Get-EffectiveSubtitleSwitch',
    'Get-ConfiguredOutputContainerName',
    'Get-ConvertedSrtCodecForFfmpegOutput',
    'Resolve-SubtitleConfiguredPath',
    'Get-NormalizedSubtitleLanguage',
    'Get-SubtitleEntryPropertyValue',
    'Get-SubtitlePreferredDefaultLanguages',
    'Test-SubtitleLanguageIsPreferredDefault',
    'Test-SubtitleLanguageIsFallbackDefault',
    'Test-SubtitleEntryLanguageIsPreferredDefault',
    'Test-SubtitleEntryLanguageIsFallbackDefault',
    'Get-SafeSubtitleFileToken',
    'Get-SubtitleLanguageDisplayMap',
    'Test-SubtitleTitleMatchesAnyKeyword',
    'Get-SubtitleLanguagePolicy',
    'Get-SubtitleSupplementalForcedSwitchName',
    'New-SubtitleEnrichedTitle',
    'Resolve-SubtitleStreamPolicy',
    'New-SubtitleFilterEntry',
    'New-SubtitleRoutingDecision',
    'Set-LastSubtitleDecisionRecords',
    'Get-LastSubtitleDecisionRecords',
    'New-SubtitleDecisionRecord',
    'Get-SubtitleRoutingPolicyChain',
    'Resolve-SubtitleRoutingDecision',
    'Add-SubtitleRoutingDecision',
    'Filter-SubtitleStreams',
    'Test-SrtFileUsable',
    'New-SrtAtomicTempPath',
    'Complete-AtomicSrtWrite',
    'Merge-AdjacentIdenticalCues',
    'New-AssFailureRecord',
    'Convert-AssToSrt',
    'Test-IsTx3gSubtitleStream',
    'Test-CanPreserveTx3gInFfmpegOutput',
    'New-Tx3gFailureRecord',
    'Convert-Tx3gToSrt',
    'Test-IsBdpgsSubtitleStream',
    'Test-CanPreserveBdpgsInFfmpegOutput',
    'Resolve-BdpgsOcrLanguage',
    'Resolve-BdpgsOcrToolInvocation',
    'Resolve-BdpgsOcrTessdataPath',
    'New-BdpgsFailureRecord',
    'Extract-BdpgsToSup',
    'Convert-BdpgsToSrt',
    'Test-SubtitleBuilderPreferredDefaultCandidate',
    'Test-SubtitleBuilderFallbackDefaultCandidate',
    'New-SubtitleBuilderTrackDecisionRecord',
    'Get-SubtitleBuilderFfmpegBaseDisposition',
    'Set-SubtitleBuilderFfmpegDefaultDisposition',
    'Get-SubtitleBuilderFfmpegConvertedDisposition',
    'Set-SubtitleBuilderBoolDefaultDisposition',
    'Add-SubtitleBuilderFallbackDefaultCandidate',
    'Set-SubtitleBuilderFallbackDefault',
    'New-SubtitleBuilderDefaultState',
    'Get-SubtitleBuilderTrackDecisionRecords',
    'Get-MkvmergeTidMap',
    'Build-SubtitleTracksForMkvmerge',
    'Build-SubtitleArgsForFFmpeg'
)) -join [Environment]::NewLine
$subtitleCleanupCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function DebugLog { param([string]`$Message) }
function Save-ReproCommand { param([string]`$ToolName, [string]`$Executable, [string[]]`$ArgumentList, [string]`$Stage) return "repro-`$Stage.cmd" }
function Get-ErrorTextSummary { param([string]`$ErrorText) return `$ErrorText }
$subtitleCleanupFunctions

`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-subtitle-cleanup-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$script:processingDir = `$root
    `$script:ffprobePath = Join-Path `$root 'ffprobe.exe'
    `$script:ffmpegPath = Join-Path `$root 'ffmpeg.exe'
    `$script:pythonPath = Join-Path `$root 'python.exe'
    `$script:assToSrtScript = Join-Path `$root 'ass_to_srt.py'
    `$ffprobePath = `$script:ffprobePath
    `$ffmpegPath = `$script:ffmpegPath
    `$pythonPath = `$script:pythonPath
    `$assToSrtScript = `$script:assToSrtScript
    Set-Content -LiteralPath `$script:ffprobePath -Value 'fake' -Encoding ASCII
    Set-Content -LiteralPath `$script:ffmpegPath -Value 'fake' -Encoding ASCII
    Set-Content -LiteralPath `$script:pythonPath -Value 'fake' -Encoding ASCII
    Set-Content -LiteralPath `$script:assToSrtScript -Value 'fake' -Encoding ASCII
    `$goodSrt = "1`r`n00:00:01,000 --> 00:00:02,000`r`nhello`r`n"

    `$script:NativeMode = 'probe'
    `$script:NativeCalls = @()
    function Invoke-NativeCommand {
        param([string]`$FilePath, [string[]]`$ArgumentList, [int]`$TimeoutSeconds)
        `$script:NativeCalls += ,([pscustomobject]@{ FilePath = `$FilePath; ArgumentList = @(`$ArgumentList); TimeoutSeconds = `$TimeoutSeconds })
        if (`$script:NativeMode -eq 'probe') {
            `$payload = @{
                streams = @(
                    @{ index = 0; codec_name = 'subrip'; codec_long_name = 'SubRip'; codec_tag_string = ''; tags = @{ language = 'spa'; title = 'Spanish Forced' }; disposition = @{ forced = 1; default = 0 } },
                    @{ index = 1; codec_name = 'ass'; codec_long_name = 'ASS'; codec_tag_string = ''; tags = @{ language = 'eng'; title = 'Signs' }; disposition = @{ forced = 0; default = 0 } },
                    @{ index = 2; codec_name = 'mov_text'; codec_long_name = 'MPEG-4 Timed Text subtitle'; codec_tag_string = 'tx3g'; tags = @{ language = ''; title = 'English SDH' }; disposition = @{ forced = 0; default = 0 } },
                    @{ index = 3; codec_name = 'hdmv_pgs_subtitle'; codec_long_name = 'HDMV Presentation Graphic Stream subtitles'; codec_tag_string = ''; tags = @{ language = 'jpn'; title = 'Song' }; disposition = @{ forced = 0; default = 0 } },
                    @{ index = 4; codec_name = 'ass'; codec_long_name = 'ASS'; codec_tag_string = ''; tags = @{ language = 'fre'; title = 'French Dialogue' }; disposition = @{ forced = 0; default = 0 } }
                )
            }
            return [pscustomobject]@{ ExitCode = 0; Output = (`$payload | ConvertTo-Json -Depth 8); Error = ''; TimedOut = `$false; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'ass_success') {
            [System.IO.File]::WriteAllText([string]`$ArgumentList[3], `$goodSrt, [System.Text.UTF8Encoding]::new(`$false))
            return [pscustomobject]@{ ExitCode = 0; Output = ''; Error = 'INFO: 1 cues written'; TimedOut = `$false; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'ass_empty') {
            [System.IO.File]::WriteAllText([string]`$ArgumentList[3], '', [System.Text.UTF8Encoding]::new(`$false))
            return [pscustomobject]@{ ExitCode = 0; Output = ''; Error = ''; TimedOut = `$false; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'ass_fail') {
            return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'helper failed'; TimedOut = `$false; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'tx3g_success') {
            [System.IO.File]::WriteAllText([string]`$ArgumentList[-1], `$goodSrt, [System.Text.UTF8Encoding]::new(`$false))
            return [pscustomobject]@{ ExitCode = 0; Output = ''; Error = ''; TimedOut = `$false; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'tx3g_empty') {
            [System.IO.File]::WriteAllText([string]`$ArgumentList[-1], '', [System.Text.UTF8Encoding]::new(`$false))
            return [pscustomobject]@{ ExitCode = 0; Output = ''; Error = ''; TimedOut = `$false; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'tx3g_timeout') {
            return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'timed out'; TimedOut = `$true; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'bdpgs_success') {
            if (`$FilePath -eq `$script:ffmpegPath) {
                [System.IO.File]::WriteAllText([string]`$ArgumentList[-1], 'sup', [System.Text.UTF8Encoding]::new(`$false))
            } else {
                `$outIndex = [array]::IndexOf(`$ArgumentList, '--output')
                [System.IO.File]::WriteAllText([string]`$ArgumentList[`$outIndex + 1], `$goodSrt, [System.Text.UTF8Encoding]::new(`$false))
            }
            return [pscustomobject]@{ ExitCode = 0; Output = ''; Error = ''; TimedOut = `$false; Stopped = `$false }
        }
        if (`$script:NativeMode -eq 'bdpgs_sup_fail') {
            return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = 'sup extract failed'; TimedOut = `$false; Stopped = `$false }
        }
        throw "unexpected NativeMode `$(`$script:NativeMode)"
    }

    `$script:SubKeepLanguages = @('eng')
    `$SubKeepLanguages = `$script:SubKeepLanguages
    `$script:SubSDHTitleKeywords = @('sdh', 'hearing')
    `$SubSDHTitleKeywords = `$script:SubSDHTitleKeywords
    `$script:SubSupplementalKeywords = @('sign', 'song', 'karaoke')
    `$SubSupplementalKeywords = `$script:SubSupplementalKeywords
    `$script:Tx3gExtractLanguages = @('eng', 'und')
    `$script:BdpgsExtractLanguages = @('eng')
    `$script:ConvertTx3gToSrt = `$true
    `$script:ConvertBdpgsToSrt = `$true
    `$script:TreatAssSignsSongsAsForced = `$true
    `$script:TreatTx3gSignsSongsAsForced = `$true
    `$script:TreatBdpgsSignsSongsAsForced = `$true
    `$script:KeepSignsAndSongs = `$true

    `$forcedPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 0 -Stream ([pscustomobject]@{
        index = 40; codec_name = 'subrip'; codec_long_name = 'SubRip'; codec_tag_string = ''
        tags = @{ language = 'spa'; title = 'Spanish Forced' }
        disposition = @{ forced = 1; default = 0 }
    })
    if (-not `$forcedPolicy.Retain -or -not `$forcedPolicy.IsForced -or `$forcedPolicy.Lang -ne 'spa') { throw 'subtitle policy helper did not retain forced non-preferred subtitle' }

    `$sdhPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 1 -Stream ([pscustomobject]@{
        index = 41; codec_name = 'subrip'; codec_long_name = 'SubRip'; codec_tag_string = ''
        tags = @{ language = 'fre'; title = 'French SDH' }
        disposition = @{ forced = 0; default = 0 }
    })
    if (-not `$sdhPolicy.Retain -or -not `$sdhPolicy.IsSdh) { throw 'subtitle policy helper did not retain SDH subtitle outside preferred languages' }

    `$tx3gSongPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 2 -Stream ([pscustomobject]@{
        index = 42; codec_name = 'mov_text'; codec_long_name = 'MPEG-4 Timed Text subtitle'; codec_tag_string = 'tx3g'
        tags = @{ language = 'jpn'; title = 'Song' }
        disposition = @{ forced = 0; default = 0 }
    })
    if (-not `$tx3gSongPolicy.Retain -or -not `$tx3gSongPolicy.IsForced -or -not `$tx3gSongPolicy.SupplementalForced -or -not `$tx3gSongPolicy.IsTx3g) { throw 'subtitle policy helper did not apply tx3g signs/songs forced policy' }
    `$tx3gEntry = New-SubtitleFilterEntry -Policy `$tx3gSongPolicy
    if (-not `$tx3gEntry.IsTx3g -or -not `$tx3gEntry.SupplementalForced) { throw 'subtitle filter entry did not preserve common policy metadata' }

    `$srtDecision = Resolve-SubtitleRoutingDecision -Entry (New-SubtitleFilterEntry -Policy `$forcedPolicy)
    if (`$srtDecision.Action -ne 'Keep') { throw 'SRT routing decision should keep subtitle stream' }

    `$assSupplementalPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 3 -Stream ([pscustomobject]@{
        index = 43; codec_name = 'ass'; codec_long_name = 'ASS'; codec_tag_string = ''
        tags = @{ language = 'eng'; title = 'Signs' }
        disposition = @{ forced = 0; default = 0 }
    })
    `$assSupplementalDecision = Resolve-SubtitleRoutingDecision -Entry (New-SubtitleFilterEntry -Policy `$assSupplementalPolicy)
    if (`$assSupplementalDecision.Action -ne 'Keep') { throw 'supplemental ASS routing decision should keep when KeepSignsAndSongs is true' }

    `$assNormalPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 4 -Stream ([pscustomobject]@{
        index = 44; codec_name = 'ass'; codec_long_name = 'ASS'; codec_tag_string = ''
        tags = @{ language = 'eng'; title = 'English Dialogue' }
        disposition = @{ forced = 0; default = 0 }
    })
    `$assNormalDecision = Resolve-SubtitleRoutingDecision -Entry (New-SubtitleFilterEntry -Policy `$assNormalPolicy)
    if (`$assNormalDecision.Action -ne 'ConvertAss') { throw 'normal retained ASS routing decision should convert to SRT' }

    `$tx3gDecision = Resolve-SubtitleRoutingDecision -Entry `$tx3gEntry
    if (`$tx3gDecision.Action -ne 'ConvertTx3g') { throw 'tx3g routing decision should convert when ConvertTx3gToSrt is true' }
    `$script:ConvertTx3gToSrt = `$false
    `$script:DropTx3gAfterConversion = `$true
    `$tx3gDropDecision = Resolve-SubtitleRoutingDecision -Entry `$tx3gEntry
    if (`$tx3gDropDecision.Action -ne 'Drop') { throw 'tx3g routing decision should drop when conversion is disabled and drop is enabled' }
    `$script:ConvertTx3gToSrt = `$true
    `$script:DropTx3gAfterConversion = `$false

    `$bdpgsSongPolicy = Resolve-SubtitleStreamPolicy -SubtitleOrdinal 5 -Stream ([pscustomobject]@{
        index = 45; codec_name = 'hdmv_pgs_subtitle'; codec_long_name = 'HDMV Presentation Graphic Stream subtitles'; codec_tag_string = ''
        tags = @{ language = 'jpn'; title = 'Song' }
        disposition = @{ forced = 0; default = 0 }
    })
    `$bdpgsDecision = Resolve-SubtitleRoutingDecision -Entry (New-SubtitleFilterEntry -Policy `$bdpgsSongPolicy)
    if (`$bdpgsDecision.Action -ne 'ConvertBdpgs') { throw 'BDPGS routing decision should convert when ConvertBdpgsToSrt is true' }

    `$unsupportedDecision = Resolve-SubtitleRoutingDecision -Entry @{
        Stream = [pscustomobject]@{ index = 46 }
        Codec = 'dvd_subtitle'
        Lang = 'eng'
        Title = 'Unsupported'
        IsTx3g = `$false
        IsBdpgs = `$false
        IsSupplemental = `$false
    }
    if (`$unsupportedDecision.Action -ne 'Drop') { throw 'unsupported subtitle codec should route to drop' }

    `$filter = Filter-SubtitleStreams -FilePath (Join-Path `$root 'source.mkv') -Context 'TEST: '
    if (@(`$filter.Keep).Count -ne 2) { throw ('expected forced SRT and supplemental ASS keep entries, got ' + @(`$filter.Keep).Count) }
    if (@(`$filter.Convert).Count -ne 0) { throw 'supplemental ASS should be kept when KeepSignsAndSongs is true' }
    if (@(`$filter.Tx3gConvert).Count -ne 1) { throw 'tx3g stream should be routed to conversion' }
    if (@(`$filter.BdpgsConvert).Count -ne 1) { throw 'BDPGS signs/songs forced policy should retain OCR candidate outside preferred language' }
    if (@(`$filter.Drop).Count -ne 1) { throw 'non-preferred non-forced ASS stream should be dropped' }
    if (-not [bool]@(`$filter.Keep | Where-Object { `$_.Lang -eq 'spa' })[0].IsForced) { throw 'forced non-preferred subtitle was not retained as forced' }
    if (-not [bool]@(`$filter.BdpgsConvert)[0].IsForced) { throw 'BDPGS signs/songs-as-forced did not mark the stream forced' }
    `$subtitleDecisions = @(Get-LastSubtitleDecisionRecords)
    if (`$subtitleDecisions.Count -ne 5 -or @(`$filter.Decisions).Count -ne 5) { throw 'subtitle decision records were not persisted for every probed stream' }
    if (@(`$subtitleDecisions | Where-Object { `$_.action -eq 'converttx3g' -and `$_.is_tx3g }).Count -ne 1) { throw 'tx3g conversion decision record missing' }
    if (@(`$subtitleDecisions | Where-Object { `$_.action -eq 'convertbdpgs' -and `$_.is_bdpgs -and `$_.is_forced }).Count -ne 1) { throw 'BDPGS conversion/forced decision record missing' }
    if (@(`$subtitleDecisions | Where-Object { `$_.action -eq 'drop' -and `$_.reason -eq 'language_or_title_policy' }).Count -ne 1) { throw 'subtitle policy drop decision record missing' }

    `$script:RemoveKaraoke = `$true
    `$script:ExcludeSubtitleStyles = @('signs', 'karaoke')
    `$script:IncludeSubtitleStyles = @('dialogue')
    `$script:StripFormatting = `$false
    `$script:MergeAdjacent = `$false
    `$script:NativeMode = 'ass_success'
    `$ass = Convert-AssToSrt -SourceFile (Join-Path `$root 'source.mkv') -StreamIndex 4 -StreamInfo @{ Stream = [pscustomobject]@{ index = 4 }; Lang = 'eng'; Title = 'English' }
    if (-not `$ass.Ok -or -not (Test-Path -LiteralPath `$ass.Path)) { throw 'ASS conversion success did not produce a validated SRT' }
    `$assCall = `$script:NativeCalls[-1]
    if (`$assCall.ArgumentList[4] -ne '1') { throw 'ASS karaoke flag was not passed to helper' }
    if (`$assCall.ArgumentList[5] -ne 'signs|karaoke' -or `$assCall.ArgumentList[6] -ne 'dialogue') { throw 'ASS style include/exclude args were not passed correctly' }
    if (`$assCall.ArgumentList -notcontains '--keep-formatting') { throw 'ASS formatting toggle was not passed' }
    `$script:NativeMode = 'ass_fail'
    `$assFail = Convert-AssToSrt -SourceFile (Join-Path `$root 'source.mkv') -StreamIndex 5 -StreamInfo @{ Stream = [pscustomobject]@{ index = 5 }; Lang = 'eng'; Title = 'English' }
    if (`$assFail.Ok -or `$assFail.Failure.ErrorCode -ne 'SUBTITLE_ASS_CONVERT_FAILED') { throw 'ASS helper failure was not classified' }
    `$script:NativeMode = 'ass_empty'
    `$assEmpty = Convert-AssToSrt -SourceFile (Join-Path `$root 'source.mkv') -StreamIndex 6 -StreamInfo @{ Stream = [pscustomobject]@{ index = 6 }; Lang = 'eng'; Title = 'English' }
    if (`$assEmpty.Ok -or `$assEmpty.Failure.ErrorCode -ne 'SUBTITLE_ASS_SRT_EMPTY') { throw 'ASS empty output was not classified as empty' }

    `$script:NativeMode = 'tx3g_success'
    `$tx3gOut = Join-Path `$root 'tx3g.srt'
    `$tx3g = Convert-Tx3gToSrt -SourceFile (Join-Path `$root 'source.mp4') -StreamIndex 7 -StreamInfo @{ Stream = [pscustomobject]@{ index = 7 }; Lang = 'und'; Title = 'Timed Text' } -DestinationPath `$tx3gOut
    if (-not `$tx3g.Ok -or `$tx3g.Failure) { throw 'tx3g success should return Ok with no failure' }
    `$tx3gCall = `$script:NativeCalls[-1]
    `$mapIndex = [array]::IndexOf(`$tx3gCall.ArgumentList, '-map')
    if (`$mapIndex -lt 0 -or `$tx3gCall.ArgumentList[`$mapIndex + 1] -ne '0:7') { throw 'tx3g extraction did not map the exact stream index' }
    `$script:NativeMode = 'tx3g_timeout'
    `$tx3gFail = Convert-Tx3gToSrt -SourceFile (Join-Path `$root 'source.mp4') -StreamIndex 8 -StreamInfo @{ Stream = [pscustomobject]@{ index = 8 }; Lang = 'eng'; Title = 'Timed Text' } -DestinationPath (Join-Path `$root 'tx3g-fail.srt')
    if (`$tx3gFail.Ok -or `$tx3gFail.Failure.ErrorCode -ne 'SUBTITLE_TX3G_EXTRACT_TIMEOUT') { throw 'tx3g timeout was not classified' }
    `$script:NativeMode = 'tx3g_empty'
    `$tx3gEmpty = Convert-Tx3gToSrt -SourceFile (Join-Path `$root 'source.mp4') -StreamIndex 9 -StreamInfo @{ Stream = [pscustomobject]@{ index = 9 }; Lang = 'eng'; Title = 'Timed Text' } -DestinationPath (Join-Path `$root 'tx3g-empty.srt')
    if (`$tx3gEmpty.Ok -or `$tx3gEmpty.Failure.ErrorCode -ne 'SUBTITLE_TX3G_SRT_EMPTY') { throw 'tx3g empty output was not classified' }

    `$tool = Join-Path `$root 'PgsToSrt.exe'
    `$tess = Join-Path `$root 'tessdata'
    Set-Content -LiteralPath `$tool -Value 'fake' -Encoding ASCII
    New-Item -ItemType Directory -Path `$tess -Force | Out-Null
    `$script:BdpgsOcrToolPath = `$tool
    `$script:BdpgsOcrTessdataPath = `$tess
    `$script:NativeMode = 'bdpgs_success'
    `$bdpgs = Convert-BdpgsToSrt -SourceFile (Join-Path `$root 'source.mkv') -StreamIndex 10 -StreamInfo @{ Stream = [pscustomobject]@{ index = 10 }; Lang = 'eng'; Title = 'PGS' } -DestinationPath (Join-Path `$root 'bdpgs.srt')
    if (-not `$bdpgs.Ok -or `$bdpgs.CueCount -ne 1) { throw 'BDPGS OCR success did not produce validated SRT' }
    `$ocrCall = `$script:NativeCalls[-1]
    if (`$ocrCall.ArgumentList -notcontains '--tesseractdata') { throw 'BDPGS OCR did not pass tessdata argument' }
    `$script:BdpgsOcrToolPath = Join-Path `$root 'missing.exe'
    `$missingTool = Convert-BdpgsToSrt -SourceFile (Join-Path `$root 'source.mkv') -StreamIndex 11 -StreamInfo @{ Stream = [pscustomobject]@{ index = 11 }; Lang = 'eng'; Title = 'PGS' } -DestinationPath (Join-Path `$root 'bdpgs-missing-tool.srt')
    if (`$missingTool.Ok -or `$missingTool.Failure.ErrorCode -ne 'SUBTITLE_BDPGS_OCR_TOOL_MISSING') { throw 'BDPGS missing OCR tool was not classified' }
    if (@(Get-ChildItem -LiteralPath `$root -Filter 'sub_bdpgs_*.sup' -File -ErrorAction SilentlyContinue).Count -ne 0) { throw 'BDPGS missing OCR tool leaked SUP temp file' }
    `$script:BdpgsOcrToolPath = `$tool
    `$script:BdpgsOcrTessdataPath = Join-Path `$root 'missing-tessdata'
    `$missingTess = Convert-BdpgsToSrt -SourceFile (Join-Path `$root 'source.mkv') -StreamIndex 12 -StreamInfo @{ Stream = [pscustomobject]@{ index = 12 }; Lang = 'eng'; Title = 'PGS' } -DestinationPath (Join-Path `$root 'bdpgs-missing-tess.srt')
    if (`$missingTess.Ok -or `$missingTess.Failure.ErrorCode -ne 'SUBTITLE_BDPGS_TESSDATA_MISSING') { throw 'BDPGS missing tessdata was not classified' }
    if (@(Get-ChildItem -LiteralPath `$root -Filter 'sub_bdpgs_*.sup' -File -ErrorAction SilentlyContinue).Count -ne 0) { throw 'BDPGS missing tessdata leaked SUP temp file' }
    `$script:BdpgsOcrTessdataPath = `$tess
    `$script:NativeMode = 'bdpgs_sup_fail'
    `$supFail = Convert-BdpgsToSrt -SourceFile (Join-Path `$root 'source.mkv') -StreamIndex 13 -StreamInfo @{ Stream = [pscustomobject]@{ index = 13 }; Lang = 'eng'; Title = 'PGS' } -DestinationPath (Join-Path `$root 'bdpgs-sup-fail.srt')
    if (`$supFail.Ok -or `$supFail.Failure.ErrorCode -ne 'SUBTITLE_BDPGS_SUP_EXTRACT_FAILED') { throw 'BDPGS SUP extraction failure was not classified' }

    `$validPath = Join-Path `$root 'valid.srt'
    [System.IO.File]::WriteAllText(`$validPath, `$goodSrt, [System.Text.UTF8Encoding]::new(`$false))
    if (-not (Test-SrtFileUsable -Path `$validPath).Ok) { throw 'valid SRT failed validation' }
    `$timingOnly = Join-Path `$root 'timing-only.srt'
    [System.IO.File]::WriteAllText(`$timingOnly, "1`r`n00:00:01,000 --> 00:00:02,000`r`n`r`n", [System.Text.UTF8Encoding]::new(`$false))
    if ((Test-SrtFileUsable -Path `$timingOnly).Ok) { throw 'timing-only SRT passed validation' }
    `$existing = Join-Path `$root 'existing.srt'
    [System.IO.File]::WriteAllText(`$existing, `$goodSrt, [System.Text.UTF8Encoding]::new(`$false))
    `$badTemp = New-SrtAtomicTempPath -DestinationPath `$existing
    [System.IO.File]::WriteAllText(`$badTemp, 'bad', [System.Text.UTF8Encoding]::new(`$false))
    try { Complete-AtomicSrtWrite -TempPath `$badTemp -DestinationPath `$existing | Out-Null; throw 'bad atomic write unexpectedly succeeded' } catch {}
    if (-not (Test-SrtFileUsable -Path `$existing).Ok) { throw 'failed atomic write damaged existing SRT' }
    `$mergePath = Join-Path `$root 'merge.srt'
    [System.IO.File]::WriteAllText(`$mergePath, "1`r`n00:00:01,000 --> 00:00:02,000`r`nsame`r`n`r`n2`r`n00:00:02,100 --> 00:00:03,000`r`nsame`r`n", [System.Text.UTF8Encoding]::new(`$false))
    Merge-AdjacentIdenticalCues -SrtPath `$mergePath -ThresholdMs 150
    `$mergedValidation = Test-SrtFileUsable -Path `$mergePath
    if (-not `$mergedValidation.Ok -or `$mergedValidation.CueCount -ne 1) { throw 'atomic cue merge did not preserve a valid one-cue SRT' }

    `$script:OutputContainer = 'mkv'
    `$builderFilter = @{
        Keep = @(
            @{ Stream = [pscustomobject]@{ index = 20 }; Lang = 'eng'; Title = 'English Signs'; IsSupplemental = `$true; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$false },
            @{ Stream = [pscustomobject]@{ index = 21 }; Lang = 'eng'; Title = 'English'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$false }
        )
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        Drop = @()
    }
    `$build = Build-SubtitleArgsForFFmpeg -FilterResult `$builderFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path `$root 'source.mkv')
    `$disp0 = [array]::IndexOf(`$build.MapArgs, '-disposition:s:0')
    `$disp1 = [array]::IndexOf(`$build.MapArgs, '-disposition:s:1')
    if (`$build.MapArgs[`$disp0 + 1] -ne '0') { throw 'supplemental subtitle should not receive default disposition' }
    if (`$build.MapArgs[`$disp1 + 1] -ne 'default') { throw 'default subtitle assignment should prefer non-supplemental English track' }

    `$undBeforeEnglishFilter = @{
        Keep = @(
            @{ Stream = [pscustomobject]@{ index = 30 }; Lang = 'und'; Title = 'Undefined'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$false },
            @{ Stream = [pscustomobject]@{ index = 31 }; Lang = 'eng'; Title = 'English'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$false }
        )
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        Drop = @()
    }
    `$undFfmpegBuild = Build-SubtitleArgsForFFmpeg -FilterResult `$undBeforeEnglishFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path `$root 'source.mkv')
    `$undDisp0 = [array]::IndexOf(`$undFfmpegBuild.MapArgs, '-disposition:s:0')
    `$undDisp1 = [array]::IndexOf(`$undFfmpegBuild.MapArgs, '-disposition:s:1')
    if (`$undFfmpegBuild.MapArgs[`$undDisp0 + 1] -ne '0' -or `$undFfmpegBuild.MapArgs[`$undDisp1 + 1] -ne 'default') { throw 'explicit English subtitle should beat earlier undefined subtitle for FFmpeg output' }
    `$undMkvmergeBuild = Build-SubtitleTracksForMkvmerge -FilterResult `$undBeforeEnglishFilter -DefaultAudioLang 'jpn' -SourceFile (Join-Path `$root 'source.mkv')
    `$mkvDefaults = @(`$undMkvmergeBuild.SourceTracks | Where-Object { `$_.IsDefault })
    if (`$mkvDefaults.Count -ne 1 -or `$mkvDefaults[0].Lang -ne 'eng') { throw 'explicit English subtitle should beat earlier undefined subtitle for mkvmerge output' }

    `$script:SubKeepLanguages = @('spa', 'es', 'und', '')
    `$SubKeepLanguages = `$script:SubKeepLanguages
    `$preferredDefaults = @(Get-SubtitlePreferredDefaultLanguages)
    if (`$preferredDefaults.Count -ne 2 -or `$preferredDefaults[0] -ne 'spa' -or `$preferredDefaults[1] -ne 'es') { throw ('preferred subtitle default languages should exclude undefined fallback entries: ' + (`$preferredDefaults -join ',')) }
    `$configuredLanguageFilter = @{
        Keep = @(
            @{ Stream = [pscustomobject]@{ index = 32 }; Lang = 'und'; Title = 'Undefined'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$false; Codec = 'subrip' },
            @{ Stream = [pscustomobject]@{ index = 33 }; Lang = 'eng'; Title = 'English'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$false; Codec = 'subrip' },
            @{ Stream = [pscustomobject]@{ index = 34 }; Lang = 'spa'; Title = 'Spanish'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$false; Codec = 'subrip' }
        )
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        Drop = @()
    }
    `$configuredFfmpegBuild = Build-SubtitleArgsForFFmpeg -FilterResult `$configuredLanguageFilter -DefaultAudioLang 'eng' -SourceFile (Join-Path `$root 'source.mkv')
    `$configuredDisp0 = [array]::IndexOf(`$configuredFfmpegBuild.MapArgs, '-disposition:s:0')
    `$configuredDisp1 = [array]::IndexOf(`$configuredFfmpegBuild.MapArgs, '-disposition:s:1')
    `$configuredDisp2 = [array]::IndexOf(`$configuredFfmpegBuild.MapArgs, '-disposition:s:2')
    if (`$configuredFfmpegBuild.MapArgs[`$configuredDisp0 + 1] -ne '0' -or `$configuredFfmpegBuild.MapArgs[`$configuredDisp1 + 1] -ne '0' -or `$configuredFfmpegBuild.MapArgs[`$configuredDisp2 + 1] -ne 'default') {
        throw 'configured preferred subtitle language should beat earlier undefined and English tracks for FFmpeg output'
    }
    `$configuredMkvmergeBuild = Build-SubtitleTracksForMkvmerge -FilterResult `$configuredLanguageFilter -DefaultAudioLang 'eng' -SourceFile (Join-Path `$root 'source.mkv')
    `$configuredMkvDefaults = @(`$configuredMkvmergeBuild.SourceTracks | Where-Object { `$_.IsDefault })
    if (`$configuredMkvDefaults.Count -ne 1 -or `$configuredMkvDefaults[0].Lang -ne 'spa') { throw 'configured preferred subtitle language should beat earlier undefined and English tracks for mkvmerge output' }
    `$script:SubKeepLanguages = @('eng')
    `$SubKeepLanguages = `$script:SubKeepLanguages

    `$script:NativeMode = 'probe'
    `$tx3gKeepFilter = @{
        Keep = @(
            @{ Stream = [pscustomobject]@{ index = 22 }; Lang = 'eng'; Title = 'Timed Text'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$true; IsBdpgs = `$false }
        )
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        Drop = @()
    }
    `$tx3gRemuxBuild = Build-SubtitleTracksForMkvmerge -FilterResult `$tx3gKeepFilter -DefaultAudioLang 'eng' -SourceFile (Join-Path `$root 'source.mkv')
    if (@(`$tx3gRemuxBuild.Failures | Where-Object { `$_.error_code -eq 'SUBTITLE_TX3G_CONTAINER_UNSUPPORTED' }).Count -ne 1) { throw 'Matroska-incompatible kept TX3G should be a subtitle failure, not a warning-only drop' }

    `$script:OutputContainer = 'mp4'
    `$bdpgsKeepFilter = @{
        Keep = @(
            @{ Stream = [pscustomobject]@{ index = 23 }; Lang = 'eng'; Title = 'PGS'; IsSupplemental = `$false; IsForced = `$false; IsTx3g = `$false; IsBdpgs = `$true }
        )
        Convert = @()
        Tx3gConvert = @()
        BdpgsConvert = @()
        Drop = @()
    }
    `$bdpgsEncodeBuild = Build-SubtitleArgsForFFmpeg -FilterResult `$bdpgsKeepFilter -DefaultAudioLang 'eng' -SourceFile (Join-Path `$root 'source.mp4')
    if (@(`$bdpgsEncodeBuild.Failures | Where-Object { `$_.error_code -eq 'SUBTITLE_BDPGS_CONTAINER_UNSUPPORTED' }).Count -ne 1) { throw 'MP4-incompatible kept BDPGS should be a subtitle failure, not a warning-only drop' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $subtitleCleanupCheck

$tx3gAuditFunctions = (Get-FunctionText -Path (@($audit) + $moduleFiles) -Names @(
    'Get-MediaSubtitleCodecMovTextName',
    'Get-MediaSubtitleCodecAssNames',
    'Get-MediaSubtitleCodecBdpgsNames',
    'Get-MediaSubtitleCodecTextNames',
    'Get-MediaSubtitleCodecExternalFriendlyTextNames',
    'Get-MediaSubtitleCodecImageNames',
    'Convert-ToLowerInvariantSafe',
    'Get-BucketRank',
    'Get-TagValue',
    'Get-StreamTagValue',
    'Get-StreamDispositionValue',
    'Get-SidecarPath',
    'Compare-PipelineVersion',
    'Test-PipelineVersionString',
    'Add-AuditIssue',
    'Get-AuditTx3gGenericSrtSuffixes',
    'Test-AuditSrtFileUsable',
    'Get-AuditNormalizedPathKey',
    'Get-AuditSidecarSrtRecordPath',
    'Test-AuditTx3gSidecarSrtRecordUsable',
    'Test-AuditEmbeddedSrtRecordMatchesStream',
    'Get-AuditValidatedEmbeddedSrtRecordCount',
    'Get-MatchingExternalSrtFilesForAudit',
    'Analyze-Sidecar',
    'Add-AuditSubtitleCompatibilityIssues'
)) -join [Environment]::NewLine
$tx3gAuditCheck = @"
`$ErrorActionPreference = 'Stop'
$tx3gAuditFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-tx3g-audit-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$media = Join-Path `$root 'Movie.m4v'
    Set-Content -LiteralPath `$media -Value 'placeholder' -Encoding UTF8
    `$validSrt = "1`r`n00:00:01,000 --> 00:00:02,000`r`nhello`r`n"
    `$generated = Join-Path `$root 'Movie.eng.tx3g.srt'
    `$generic = Join-Path `$root 'Movie.eng.srt'
    `$commentary = Join-Path `$root 'Movie.commentary.srt'
    `$emptyGenerated = Join-Path `$root 'Movie.spa.tx3g.srt'
    `$emptyGeneric = Join-Path `$root 'Movie.spa.srt'
    [System.IO.File]::WriteAllText(`$generated, `$validSrt, [System.Text.UTF8Encoding]::new(`$false))
    [System.IO.File]::WriteAllText(`$generic, `$validSrt, [System.Text.UTF8Encoding]::new(`$false))
    [System.IO.File]::WriteAllText(`$commentary, `$validSrt, [System.Text.UTF8Encoding]::new(`$false))
    Set-Content -LiteralPath `$emptyGenerated -Value '' -Encoding UTF8
    Set-Content -LiteralPath `$emptyGeneric -Value '' -Encoding UTF8
    `$stream = [pscustomobject]@{
        tags = [pscustomobject]@{ language = 'eng' }
        disposition = [pscustomobject]@{ forced = 0 }
    }
    `$fileInfo = Get-Item -LiteralPath `$media
    `$withoutSidecar = @(Get-MatchingExternalSrtFilesForAudit -FileInfo `$fileInfo -Tx3gSubtitleStreams @(`$stream))
    if (`$withoutSidecar.Count -ne 1 -or `$withoutSidecar[0] -ne `$generated) { throw 'audit should count only usable generated .tx3g SRT without sidecar metadata' }
    `$withSidecar = @(Get-MatchingExternalSrtFilesForAudit -FileInfo `$fileInfo -Tx3gSubtitleStreams @(`$stream) -KnownTx3gSrtFiles @(`$generic))
    if (`$withSidecar.Count -ne 2) { throw ('audit should count generated plus known sidecar generic SRT, got ' + `$withSidecar.Count) }
    `$withInvalidKnownSidecar = @(Get-MatchingExternalSrtFilesForAudit -FileInfo `$fileInfo -Tx3gSubtitleStreams @(`$stream) -KnownTx3gSrtFiles @(`$emptyGeneric))
    if (`$withInvalidKnownSidecar.Count -ne 1 -or `$withInvalidKnownSidecar[0] -ne `$generated) { throw 'audit counted an unusable known generic sidecar SRT as successful' }
    if (`$withSidecar -contains `$commentary) { throw 'audit counted unrelated commentary SRT' }
    if (`$withSidecar -contains `$emptyGenerated) { throw 'audit counted unusable empty SRT' }
    `$usableRecord = [pscustomobject]@{ path = `$generic; status = 'written' }
    if (-not (Test-AuditTx3gSidecarSrtRecordUsable -Record `$usableRecord -BaseDirectory `$root)) { throw 'usable tx3g sidecar SRT record was not accepted' }
    `$pendingRecord = [pscustomobject]@{ path = `$generic; status = 'pending' }
    if (Test-AuditTx3gSidecarSrtRecordUsable -Record `$pendingRecord -BaseDirectory `$root) { throw 'pending tx3g sidecar SRT record should not be accepted as success' }
    `$embeddedRecords = @(
        [pscustomobject]@{ language = 'eng'; title = 'English' },
        [pscustomobject]@{ language = 'jpn'; title = 'Japanese OCR' }
    )
    `$subtitleStreams = @(
        [pscustomobject]@{ index = 3; codec_name = 'subrip'; tags = [pscustomobject]@{ language = 'eng'; title = 'English' } },
        [pscustomobject]@{ index = 4; codec_name = 'hdmv_pgs_subtitle'; tags = [pscustomobject]@{ language = 'jpn'; title = 'Japanese OCR' } }
    )
    `$embeddedCount = Get-AuditValidatedEmbeddedSrtRecordCount -Records `$embeddedRecords -SubtitleStreams `$subtitleStreams -SourceKind 'bdpgs'
    if (`$embeddedCount -ne 1) { throw ('audit should only validate embedded OCR records against text subtitle streams, got ' + `$embeddedCount) }
    `$tx3gUntitledRecord = [pscustomobject]@{ language = 'eng'; title = '' }
    `$originalMovText = [pscustomobject]@{ index = 5; codec_name = 'mov_text'; tags = [pscustomobject]@{ language = 'eng'; title = '' } }
    if ((Get-AuditValidatedEmbeddedSrtRecordCount -Records @(`$tx3gUntitledRecord) -SubtitleStreams @(`$originalMovText) -SourceKind 'tx3g') -ne 0) { throw 'audit should not treat untitled original mov_text as validated converted tx3g SRT' }

    function New-TestAuditResult {
        param([string[]]`$SubtitleCodecs = @())
        return [pscustomobject]@{
            Bucket = 'OK'
            BucketRank = 0
            Issues = [System.Collections.Generic.List[object]]::new()
            SubtitleCodecs = @(`$SubtitleCodecs)
            Tx3gExternalSrtCount = 0
            Tx3gEmbeddedSrtCount = 0
            Tx3gSidecarSrtFiles = @()
            Tx3gSidecarSrtInvalidCount = 0
            Tx3gSidecarFailureCount = 0
            BdpgsEmbeddedSrtCount = 0
            BdpgsEmbeddedSrtRecords = @()
            BdpgsEmbeddedSrtInvalidCount = 0
            BdpgsSidecarFailureCount = 0
            DefaultSubtitleCodec = 'none'
            DefaultSubtitleLanguage = 'none'
            HasTextSubtitle = `$false
            SidecarPath = ''
            SidecarVersion = ''
            SidecarRoute = ''
        }
    }
    function Get-TestIssueCodes { param(`$Result) return @(`$Result.Issues | ForEach-Object { [string]`$_.Code }) }
    `$tx3gStream = [pscustomobject]@{ codec_name = 'mov_text'; tags = [pscustomobject]@{ language = 'eng'; title = 'English' }; disposition = [pscustomobject]@{ forced = 0 } }
    `$bdpgsStream = [pscustomobject]@{ codec_name = 'hdmv_pgs_subtitle'; tags = [pscustomobject]@{ language = 'eng'; title = 'English PGS' }; disposition = [pscustomobject]@{ forced = 0 } }
    `$assStream = [pscustomobject]@{ codec_name = 'ass'; tags = [pscustomobject]@{ language = 'eng'; title = 'English ASS' }; disposition = [pscustomobject]@{ forced = 0 } }

    `$tx3gOnly = New-TestAuditResult -SubtitleCodecs @('mov_text')
    Add-AuditSubtitleCompatibilityIssues -Result `$tx3gOnly -SubtitleStreams @(`$tx3gStream) -Tx3gSubtitleStreams @(`$tx3gStream)
    `$tx3gOnlyCodes = Get-TestIssueCodes `$tx3gOnly
    if (`$tx3gOnlyCodes -notcontains 'tx3g-only-subtitles' -or `$tx3gOnlyCodes -notcontains 'tx3g-subtitles-extractable') { throw 'tx3g-only audit case did not report tx3g-only/extractable issues' }

    `$existingSrt = New-TestAuditResult -SubtitleCodecs @('mov_text')
    `$existingSrt.Tx3gExternalSrtCount = 1
    Add-AuditSubtitleCompatibilityIssues -Result `$existingSrt -SubtitleStreams @(`$tx3gStream) -Tx3gSubtitleStreams @(`$tx3gStream)
    `$existingSrtCodes = Get-TestIssueCodes `$existingSrt
    if (`$existingSrtCodes -contains 'tx3g-subtitles-extractable') { throw 'existing validated tx3g SRT should suppress extractable audit issue' }

    `$bdpgsOnly = New-TestAuditResult -SubtitleCodecs @('hdmv_pgs_subtitle')
    Add-AuditSubtitleCompatibilityIssues -Result `$bdpgsOnly -SubtitleStreams @(`$bdpgsStream) -BdpgsSubtitleStreams @(`$bdpgsStream)
    `$bdpgsOnlyCodes = Get-TestIssueCodes `$bdpgsOnly
    if (`$bdpgsOnlyCodes -notcontains 'bdpgs-only-subtitles' -or `$bdpgsOnlyCodes -notcontains 'bdpgs-subtitles-ocr-candidate') { throw 'BDPGS-only audit case did not report only/OCR-candidate issues' }

    `$assOnly = New-TestAuditResult -SubtitleCodecs @('ass')
    Add-AuditSubtitleCompatibilityIssues -Result `$assOnly -SubtitleStreams @(`$assStream)
    if ((Get-TestIssueCodes `$assOnly) -notcontains 'ass-only-subtitles') { throw 'ASS-only audit case did not report ass-only-subtitles' }

    `$script:MinPipelineVersion = '1.0'
    `$sidecarResult = New-TestAuditResult -SubtitleCodecs @('mov_text')
    `$sidecarPath = Get-SidecarPath `$media
    [ordered]@{
        pipeline_version = '1.0'
        route = 'encode'
        tx3g_srt_failures = @([ordered]@{ ErrorCode = 'SUBTITLE_TX3G_EXTRACT_FAILED'; Reason = 'extract failed' })
        bdpgs_srt_failures = @([ordered]@{ ErrorCode = 'SUBTITLE_BDPGS_OCR_FAILED'; Reason = 'ocr failed' })
        tx3g_srt_tracks = @([ordered]@{ path = Join-Path `$root 'missing.tx3g.srt'; status = 'written'; source_stream_index = 2 })
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath `$sidecarPath -Encoding UTF8
    Analyze-Sidecar -Result `$sidecarResult -FileInfo `$fileInfo
    `$sidecarCodes = Get-TestIssueCodes `$sidecarResult
    if (`$sidecarCodes -notcontains 'tx3g-extraction-failed' -or `$sidecarCodes -notcontains 'bdpgs-ocr-failed') { throw 'failed subtitle conversion sidecar case did not report failure issues' }
    if (`$sidecarCodes -notcontains 'tx3g-srt-sidecar-stale') { throw 'stale tx3g sidecar case did not report stale sidecar issue' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $tx3gAuditCheck

$auditProbeFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-ProbeCacheSampleHash',
    'Get-ProbeCacheIdentity'
)) -join [Environment]::NewLine
Assert-True ($auditProbeFunctions.Contains('[math]::Max([int64]0, [int64]$stream.Length - [int64]$SampleBytes)')) "Probe cache sample hash must use Int64 tail offsets for files larger than Int32.MaxValue."
$auditProbeCheck = @"
`$ErrorActionPreference = 'Stop'
function Convert-ToLowerInvariantSafe { param([object]`$Value) if (`$null -eq `$Value) { return '' }; return ([string]`$Value).ToLowerInvariant() }
function Write-AuditLog { param([string]`$Message, [string]`$Level = 'INFO') }
$auditProbeFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-audit-probe-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$path = Join-Path `$root 'same-size.mkv'
    [System.IO.File]::WriteAllBytes(`$path, [byte[]](1,2,3,4,5,6,7,8))
    `$firstFile = Get-Item -LiteralPath `$path
    `$stableMtime = `$firstFile.LastWriteTimeUtc
    `$firstIdentity = Get-ProbeCacheIdentity `$firstFile
    if ([string]::IsNullOrWhiteSpace(`$firstIdentity) -or `$firstIdentity -notmatch 'sample_sha256=') { throw 'probe cache identity did not include sample hash' }

    [System.IO.File]::WriteAllBytes(`$path, [byte[]](8,7,6,5,4,3,2,1))
    (Get-Item -LiteralPath `$path).LastWriteTimeUtc = `$stableMtime
    `$secondFile = Get-Item -LiteralPath `$path
    if ([int64]`$secondFile.Length -ne [int64]`$firstFile.Length -or `$secondFile.LastWriteTimeUtc.ToString('o') -ne `$stableMtime.ToString('o')) { throw 'test fixture did not preserve size and mtime' }
    `$secondIdentity = Get-ProbeCacheIdentity `$secondFile
    if (`$firstIdentity -eq `$secondIdentity) { throw 'same-size same-mtime content replacement reused probe cache identity' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $auditProbeCheck

$sourceIdentityFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Compare-PipelineVersion',
    'Get-SourceIdentityKey',
    'Get-SourceSampleHash',
    'Get-SourceIdentityKeyV2',
    'Get-SidecarPath',
    'Test-OutputNeedsReprocess'
)) -join [Environment]::NewLine
Assert-True ($sourceIdentityFunctions.Contains('[math]::Max([int64]0, [int64]$stream.Length - [int64]$SampleBytes)')) "Source identity sample hash must use Int64 tail offsets for files larger than Int32.MaxValue."
Assert-True ($rerunIdentityText.Contains('[math]::Max([int64]0, [int64]$Size - [int64]$SampleBytes)')) "Rerun source identity sample hash must use Int64 tail offsets for files larger than Int32.MaxValue."
$sourceIdentityCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function Get-MediaDuration { param([string]`$FilePath) return 0.0 }
function Get-SourceVideoCodec { param([string]`$FilePath) return 'h264' }
`$script:ReprocessAll = `$false
`$script:PipelineVersion = '1.0'
`$script:MinPipelineVersion = '1.0'
$sourceIdentityFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-source-identity-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$sourcePath = Join-Path `$root 'source.mkv'
    `$outputPath = Join-Path `$root 'output.mkv'
    Set-Content -LiteralPath `$sourcePath -Value 'one' -Encoding UTF8
    Set-Content -LiteralPath `$outputPath -Value 'out' -Encoding UTF8
    `$source = Get-Item -LiteralPath `$sourcePath
    `$sidecar = Get-SidecarPath `$outputPath
    [ordered]@{
        pipeline_version = '1.0'
        source_identity = Get-SourceIdentityKey `$source
        source_path = `$source.FullName
        source_size = `$source.Length
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath `$sidecar -Encoding UTF8
    if (Test-OutputNeedsReprocess -OutputPath `$outputPath -SourceFile `$source) { throw 'matching source should not reprocess' }
    Set-Content -LiteralPath `$sourcePath -Value 'changed-content' -Encoding UTF8
    `$source = Get-Item -LiteralPath `$sourcePath
    if (-not (Test-OutputNeedsReprocess -OutputPath `$outputPath -SourceFile `$source)) { throw 'changed source should reprocess' }

    `$stableSourcePath = Join-Path `$root 'stable-source.mkv'
    `$stableOutputPath = Join-Path `$root 'stable-output.mkv'
    [System.IO.File]::WriteAllText(`$stableSourcePath, 'one', [System.Text.Encoding]::UTF8)
    [System.IO.File]::WriteAllText(`$stableOutputPath, 'out', [System.Text.Encoding]::UTF8)
    `$stableSource = Get-Item -LiteralPath `$stableSourcePath
    `$stableSidecar = Get-SidecarPath `$stableOutputPath
    [ordered]@{
        pipeline_version = '1.0'
        source_identity_v2 = Get-SourceIdentityKeyV2 `$stableSource
        source_path = `$stableSource.FullName
        source_size = `$stableSource.Length
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath `$stableSidecar -Encoding UTF8
    `$stableSource.LastWriteTimeUtc = `$stableSource.LastWriteTimeUtc.AddMinutes(5)
    `$stableSource = Get-Item -LiteralPath `$stableSourcePath
    if (Test-OutputNeedsReprocess -OutputPath `$stableOutputPath -SourceFile `$stableSource) { throw 'mtime-only source drift should not reprocess with v2 identity' }
    `$movedDir = Join-Path `$root 'renamed-show'
    New-Item -ItemType Directory -Path `$movedDir -Force | Out-Null
    `$movedSourcePath = Join-Path `$movedDir 'stable-source.mkv'
    Move-Item -LiteralPath `$stableSourcePath -Destination `$movedSourcePath -Force
    `$stableSource = Get-Item -LiteralPath `$movedSourcePath
    if (Test-OutputNeedsReprocess -OutputPath `$stableOutputPath -SourceFile `$stableSource) { throw 'path-only source drift should not reprocess with v2 identity' }
    [System.IO.File]::WriteAllText(`$movedSourcePath, 'two', [System.Text.Encoding]::UTF8)
    `$stableSource = Get-Item -LiteralPath `$movedSourcePath
    if (-not (Test-OutputNeedsReprocess -OutputPath `$stableOutputPath -SourceFile `$stableSource)) { throw 'same-size content replacement should reprocess with v2 sample hash' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $sourceIdentityCheck

$tvParseFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Remove-PriorityMarkersFromName',
    'Normalize-TVShowFolderName',
    'Get-TVEpisodeFromFilename',
    'Resolve-OrdinalSeason',
    'Test-TVSpecialSeasonFolderName',
    'Get-TVFolderSeasonInfo',
    'Get-TVEpisodeFromStrippedName',
    'Get-TVLooseParseText',
    'Get-TVLooseSeasonEpisodeFromName',
    'Get-TVLooseBareEpisodeNumber',
    'Get-TVShowNameBeforeSeasonEpisodeTokens',
    'Get-TVShowNameBeforeExplicitEpisodeToken',
    'Test-TVFolderEpisodeSequenceSupportsCandidate',
    'Get-TVAggressiveEpisodeFromName',
    'Get-TVInfoFromFile',
    'Get-EpisodeTitle',
    'Get-CleanTVOutputNamePart',
    'Get-CleanTVEpisodeTitle',
    'Get-TVInfoField',
    'Join-PlexRelativePathParts',
    'Get-RenameOverrideSidecarPath',
    'Get-RenameOverrideFinalName',
    'Apply-RenameOverrideToDestinationPlan',
    'New-PlexMovieDestinationPlan',
    'New-PlexTVDestinationPlan',
    'New-PlexDestinationPlan',
    'Get-CleanTVFilename',
    'Get-OutputPaths'
)) -join [Environment]::NewLine
$tvParseCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
`$script:PriorityMarkers = @('!', '[NOW]')
`$script:AggressiveEpisodeParsing = `$true
`$script:ValidExtensions = @('.mkv', '.mp4')
$tvParseFunctions
function Assert-TV {
    param([string]`$Path, [string]`$Show, [int]`$Season, [int]`$Episode, [string]`$ModeLike = '')
    `$info = Get-TVInfoFromFile (Get-Item -LiteralPath `$Path)
    if (-not `$info.IsReliable) { throw ("TV parse was not reliable for " + `$Path + ": " + `$info.ParseError) }
    if (`$info.ShowName -ne `$Show) { throw ("show mismatch for " + `$Path + ": " + `$info.ShowName) }
    if ([int]`$info.Season -ne `$Season) { throw ("season mismatch for " + `$Path + ": " + `$info.Season) }
    if ([int]`$info.Episode -ne `$Episode) { throw ("episode mismatch for " + `$Path + ": " + `$info.Episode) }
    if (`$ModeLike -and [string]`$info.ParseMode -notmatch `$ModeLike) { throw ("parse mode mismatch for " + `$Path + ": " + `$info.ParseMode) }
}
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-tv-parse-' + [guid]::NewGuid().ToString('N'))
try {
    `$goldenS1 = Join-Path `$root 'Golden Kamuy\S01'
    `$goldenS2 = Join-Path `$root 'Golden Kamuy\S02'
    `$kaiji = Join-Path `$root 'Gyakkyou Burai Kaiji Ultimate Survivor'
    `$showSeason = Join-Path `$root 'Some Show Season 2'
    `$showSeasonDotted = Join-Path `$root 'Some Show.Season.2'
    `$showSeasonSpacedS = Join-Path `$root 'Some Show S 2'
    `$showSeasonDotS = Join-Path `$root 'Some Show.S02'
    `$showSeasonBracketed = Join-Path `$root '[Group] Some Show Season 2 [1080p]'
    `$showSeasonComplete = Join-Path `$root 'Some Show Season 2 Complete'
    `$showOrdinalSeason = Join-Path `$root 'Some Show - 2nd Season'
    `$lainReleaseSeason = Join-Path `$root 'Serial Experiments Lain 1998 Season 02 1080p BluRay FLAC 2.0 x264-Chotab'
    `$defaultSeason = Join-Path `$root 'No Season Show'
    `$numericTitle = Join-Path `$root 'Studio 60'
    `$valkyrie = Join-Path `$root '[Judas] Valkyrie Drive Mermaid (Season 1 + Specials) [UNCENSORED BD 1080p][HEVC x265 10bit][Dual-Audio][Eng-Subs]\Season 01'
    `$specials = Join-Path `$root 'Serial Experiments Lain\Specials'
    `$ova = Join-Path `$root 'Serial Experiments Lain\OVA'
    `$seasonZero = Join-Path `$root 'Serial Experiments Lain\Season 00'
    foreach (`$dir in @(`$goldenS1, `$goldenS2, `$kaiji, `$showSeason, `$showSeasonDotted, `$showSeasonSpacedS, `$showSeasonDotS, `$showSeasonBracketed, `$showSeasonComplete, `$showOrdinalSeason, `$lainReleaseSeason, `$defaultSeason, `$numericTitle, `$valkyrie, `$specials, `$ova, `$seasonZero)) {
        New-Item -ItemType Directory -Path `$dir -Force | Out-Null
    }
    `$p1 = Join-Path `$goldenS1 '[Judas] Golden Kamuy S1  01.mp4'
    `$p2 = Join-Path `$goldenS2 '[Judas] Golden Kamuy S2 - 13.mkv'
    `$p3 = Join-Path `$kaiji '[DB]Gyakkyou Burai Kaiji Ultimate Survivor_-_01_(10bit_BD1080p_x265).mkv'
    `$p4 = Join-Path `$showSeason 'Release - 03.mkv'
    `$p5 = Join-Path `$defaultSeason '01.mkv'
    `$p6 = Join-Path `$numericTitle 'Studio 60.mkv'
    `$p7 = Join-Path `$valkyrie '[Judas] Valkyrie Drive Mermaid (Season 1 + Specials) [UNCENSORED BD 1080p][HEVC x265 10bit][Dual-Audio][Eng-Subs] - S01E01.mkv'
    `$p8 = Join-Path `$root 'Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p9 = Join-Path `$specials 'E01 Weird Special 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p10 = Join-Path `$ova 'Episode 2 Extra Layer 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p11 = Join-Path `$seasonZero 'E03 Bonus Layer 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p12 = Join-Path `$specials 'Serial Experiments Lain S01E04 Religion 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p13 = Join-Path `$root 'Serial Experiments Lain S02 E03 Reset 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p14 = Join-Path `$showSeasonDotted 'E04 Reboot 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p15 = Join-Path `$showSeasonSpacedS 'E05 Reset 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p16 = Join-Path `$showSeasonDotS 'E06 Protocol 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p17 = Join-Path `$showSeasonBracketed 'E07 Society 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p18 = Join-Path `$showSeasonComplete 'E08 Rumors 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p19 = Join-Path `$showOrdinalSeason 'E09 Protocol 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    `$p20 = Join-Path `$lainReleaseSeason 'Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv'
    foreach (`$path in @(`$p1, `$p2, `$p3, `$p4, `$p5, `$p6, `$p7, `$p8, `$p9, `$p10, `$p11, `$p12, `$p13, `$p14, `$p15, `$p16, `$p17, `$p18, `$p19, `$p20)) {
        Set-Content -LiteralPath `$path -Value 'x' -Encoding ASCII
    }

    Assert-TV -Path `$p1 -Show 'Golden Kamuy' -Season 1 -Episode 1
    Assert-TV -Path `$p2 -Show 'Golden Kamuy' -Season 2 -Episode 13
    Assert-TV -Path `$p3 -Show 'Gyakkyou Burai Kaiji Ultimate Survivor' -Season 1 -Episode 1 -ModeLike 'aggressive-default-season'
    Assert-TV -Path `$p4 -Show 'Some Show' -Season 2 -Episode 3
    Assert-TV -Path `$p5 -Show 'No Season Show' -Season 1 -Episode 1 -ModeLike 'aggressive-default-season'
    Assert-TV -Path `$p8 -Show 'Serial Experiments Lain' -Season 1 -Episode 1 -ModeLike 'aggressive-default-season'
    Assert-TV -Path `$p9 -Show 'Serial Experiments Lain' -Season 0 -Episode 1 -ModeLike 'folder-season'
    Assert-TV -Path `$p10 -Show 'Serial Experiments Lain' -Season 0 -Episode 2 -ModeLike 'folder-season'
    Assert-TV -Path `$p11 -Show 'Serial Experiments Lain' -Season 0 -Episode 3 -ModeLike 'folder-season'
    Assert-TV -Path `$p12 -Show 'Serial Experiments Lain' -Season 1 -Episode 4 -ModeLike 'sxxexx'
    Assert-TV -Path `$p13 -Show 'Serial Experiments Lain' -Season 2 -Episode 3 -ModeLike 'filename-loose-season-episode'
    Assert-TV -Path `$p14 -Show 'Some Show' -Season 2 -Episode 4 -ModeLike 'folder-season'
    Assert-TV -Path `$p15 -Show 'Some Show' -Season 2 -Episode 5 -ModeLike 'folder-season'
    Assert-TV -Path `$p16 -Show 'Some Show' -Season 2 -Episode 6 -ModeLike 'folder-season'
    Assert-TV -Path `$p17 -Show 'Some Show' -Season 2 -Episode 7 -ModeLike 'folder-season'
    Assert-TV -Path `$p18 -Show 'Some Show' -Season 2 -Episode 8 -ModeLike 'folder-season'
    Assert-TV -Path `$p19 -Show 'Some Show' -Season 2 -Episode 9 -ModeLike 'folder-season'
    Assert-TV -Path `$p20 -Show 'Serial Experiments Lain' -Season 2 -Episode 1 -ModeLike 'folder-season'
    `$numericTitleInfo = Get-TVInfoFromFile (Get-Item -LiteralPath `$p6)
    if (`$numericTitleInfo.IsReliable) { throw 'numeric show title should not become a default-season episode' }

    `$valkyrieInfo = Get-TVInfoFromFile (Get-Item -LiteralPath `$p7)
    if (-not `$valkyrieInfo.IsReliable) { throw ('Valkyrie parse was not reliable: ' + `$valkyrieInfo.ParseError) }
    `$plan = New-PlexTVDestinationPlan -TvInfo `$valkyrieInfo -OriginalName `$valkyrieInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    if (`$plan.ShowTitle -ne 'Valkyrie Drive Mermaid') { throw ('unexpected planner show title: ' + `$plan.ShowTitle) }
    if (`$plan.SeasonFolder -ne 'Season 01') { throw ('unexpected planner season folder: ' + `$plan.SeasonFolder) }
    if (`$plan.EpisodeCode -ne 'S01E01') { throw ('unexpected planner episode code: ' + `$plan.EpisodeCode) }
    if (`$plan.HasEpisodeTitle) { throw ('release metadata should not become an episode title: ' + `$plan.EpisodeTitle) }
    if (`$plan.RelativePath -ne 'TV\Valkyrie Drive Mermaid\Season 01\Valkyrie Drive Mermaid - S01E01.mkv') { throw ('unexpected planner relative path: ' + `$plan.RelativePath) }
    `$cleanLeaf = Get-CleanTVFilename `$valkyrieInfo `$valkyrieInfo.OriginalName
    if (`$cleanLeaf -ne 'Valkyrie Drive Mermaid - S01E01') { throw ('unexpected clean TV filename: ' + `$cleanLeaf) }
    `$yearInfo = @{ ShowName = 'Doctor Who (2005) [1080p HEVC]'; Season = 1; Episode = 1; OriginalName = 'Doctor Who (2005) - S01E01 - Rose.mkv'; EpisodeEnd = `$null; ParseMode = 'test' }
    `$yearPlan = New-PlexTVDestinationPlan -TvInfo `$yearInfo -OriginalName `$yearInfo.OriginalName -Extension '.mkv' -IncludeLibraryFolder
    if (`$yearPlan.RelativePath -ne 'TV\Doctor Who (2005)\Season 01\Doctor Who (2005) - S01E01 - Rose.mkv') { throw ('year-bearing show title was not preserved for Plex: ' + `$yearPlan.RelativePath) }
    `$multiInfo = @{ ShowName = 'Clean Show [BD 1080p]'; Season = 1; Episode = 1; EpisodeEnd = 2; OriginalName = 'Clean Show - S01E01-E02 [BD 1080p].mkv'; ParseMode = 'test' }
    `$multiPlan = New-PlexTVDestinationPlan -TvInfo `$multiInfo -OriginalName `$multiInfo.OriginalName -Extension '.mkv' -IncludeLibraryFolder
    if (`$multiPlan.FileName -ne 'Clean Show - S01E01-E02.mkv') { throw ('multi-episode planner filename mismatch: ' + `$multiPlan.FileName) }
    `$lainInfo = Get-TVInfoFromFile (Get-Item -LiteralPath `$p8)
    `$lainPlan = New-PlexTVDestinationPlan -TvInfo `$lainInfo -OriginalName `$lainInfo.OriginalName -Extension '.mkv'
    if (`$lainPlan.FileName -ne 'Serial Experiments Lain - S01E01 - Weird.mkv') { throw ('explicit E-token TV title prediction failed: ' + `$lainPlan.FileName) }
    `$lainReleaseInfo = Get-TVInfoFromFile (Get-Item -LiteralPath `$p20)
    `$lainReleasePlan = New-PlexTVDestinationPlan -TvInfo `$lainReleaseInfo -OriginalName `$lainReleaseInfo.OriginalName -Extension '.mkv'
    if (`$lainReleasePlan.FileName -ne 'Serial Experiments Lain - S02E01 - Weird.mkv') { throw ('release-tagged folder season prediction failed: ' + `$lainReleasePlan.FileName) }
    `$specialInfo = Get-TVInfoFromFile (Get-Item -LiteralPath `$p9)
    `$specialPlan = New-PlexTVDestinationPlan -TvInfo `$specialInfo -OriginalName `$specialInfo.OriginalName -Extension '.mkv' -IncludeLibraryFolder
    if (`$specialPlan.RelativePath -ne 'TV\Serial Experiments Lain\Season 00\Serial Experiments Lain - S00E01 - Weird.mkv') { throw ('specials folder did not plan as S00: ' + `$specialPlan.RelativePath) }
    `$script:LocalEncoded = Join-Path `$root 'local'
    `$script:Outsource = Join-Path `$root 'out'
    `$script:OutputContainer = 'mkv'
    `$script:CreateTVSubfolder = `$true
    `$paths = Get-OutputPaths (Get-Item -LiteralPath `$p7) `$true `$valkyrieInfo ''
    `$expectedOut = Join-Path `$script:Outsource 'TV\Valkyrie Drive Mermaid\Season 01\Valkyrie Drive Mermaid - S01E01.mkv'
    if (`$paths.ServerOut -ne `$expectedOut) { throw ("unexpected clean TV output path: " + `$paths.ServerOut) }
    if (-not `$paths.ContainsKey('PlexPlan') -or `$paths.PlexPlan.IdentityKey -ne 'Valkyrie Drive Mermaid_S01E01') { throw 'Get-OutputPaths did not expose the Plex destination plan identity key' }
    if (`$paths.ServerOut -match '\[|1080p|HEVC|x265|Dual|Subs|Season 1 \+ Specials|UNCENSORED') { throw ('release metadata leaked into TV output path: ' + `$paths.ServerOut) }
    `$genericTvPlan = New-PlexDestinationPlan -MediaKind TV -File (Get-Item -LiteralPath `$p7) -TvInfo `$valkyrieInfo -OriginalName `$valkyrieInfo.OriginalName -Extension 'mkv' -IncludeLibraryFolder
    if (`$genericTvPlan.RelativePath -ne `$plan.RelativePath) { throw ('generic TV destination planner diverged: ' + `$genericTvPlan.RelativePath) }

    `$script:AggressiveEpisodeParsing = `$false
    `$strict = Get-TVInfoFromFile (Get-Item -LiteralPath `$p3)
    if (`$strict.IsReliable) { throw 'default-season fallback should require AggressiveEpisodeParsing' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $tvParseCheck

$movieNamingFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Remove-PriorityMarkersFromName',
    'Get-CleanMovieName',
    'ConvertTo-MediaPipelineMovieTitleCase',
    'Normalize-MovieName',
    'Join-PlexRelativePathParts',
    'Get-RenameOverrideSidecarPath',
    'Get-RenameOverrideFinalName',
    'Apply-RenameOverrideToDestinationPlan',
    'New-PlexMovieDestinationPlan',
    'New-PlexDestinationPlan',
    'Get-OutputPaths'
)) -join [Environment]::NewLine
$movieNamingCheck = @"
`$ErrorActionPreference = 'Stop'
$movieNamingFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-movie-naming-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$script:PriorityMarkers = @('!', '[NOW]')
    `$LocalEncoded = Join-Path `$root 'local'
    `$Outsource = Join-Path `$root 'out'
    `$OutputContainer = 'mkv'
    `$CreateTVSubfolder = `$true
    `$moviePath = Join-Path `$root '[RARBG] The.Matrix.(1999).1080p.BluRay.x265.TrueHD.Atmos.mkv'
    Set-Content -LiteralPath `$moviePath -Value 'x' -Encoding ASCII
    `$clean = Get-CleanMovieName (Split-Path -Leaf `$moviePath)
    if (`$clean -ne 'The Matrix (1999)') { throw ('movie clean name changed: ' + `$clean) }
    `$movieCleanCases = [ordered]@{
        'Devil Wears Prada (2006) (1080p BluRay x265 8bit AAC 5.1) [Kris].mkv' = 'Devil Wears Prada (2006)'
        'Airplane 1980 REMASTERED 1080p BluRay HEVC x265 5.1 BONE.mkv' = 'Airplane (1980)'
        'Young Frankenstein 1974 1080p BluRay x265 5.1-RARBG.mkv' = 'Young Frankenstein (1974)'
        'The.Blues.Brothers.1980.EXTENDED.1080p.BluRay.x265.AAC5.1-RBG.mkv' = 'The Blues Brothers (1980)'
        'The Prince of Egypt (1998) (1080p BluRay x265 10bit Tigole).mkv' = 'The Prince of Egypt (1998)'
        'Team.America.World.Police.2004.1080p.BluRay.x264-[YTS.LT].mkv' = 'Team America World Police (2004)'
        'Sinbad Legend Of The Seven Seas 2003.mkv' = 'Sinbad Legend of the Seven Seas (2003)'
        'Monty.Pythons.The.Meaning.of.Life.1983.1080p.WEBRip.1400MB.DD5.1.x264-GalaxyRG.mkv' = 'Monty Pythons The Meaning of Life (1983)'
        'Life of Brian (1979).mkv' = 'Life of Brian (1979)'
        'History.of.the.World.Part.I.1981.1080p.10bit.BluRay.6CH.x265.HEVC-PSA.mkv' = 'History of the World Part I (1981)'
        'Annie.Hall.1977.1080p.BluRay.x264.YIFY.mkv' = 'Annie Hall (1977)'
    }
    foreach (`$case in `$movieCleanCases.GetEnumerator()) {
        `$actual = Get-CleanMovieName `$case.Key
        if (`$actual -ne `$case.Value) { throw ("movie scrubber failed for {0}: got '{1}', expected '{2}'" -f `$case.Key, `$actual, `$case.Value) }
    }
    if ((Normalize-MovieName (Split-Path -Leaf `$moviePath)) -ne 'the matrix (1999)') { throw 'movie normalized index key changed' }
    `$moviePlan = New-PlexDestinationPlan -MediaKind Movie -File (Get-Item -LiteralPath `$moviePath) -OriginalName (Split-Path -Leaf `$moviePath) -Extension 'mkv'
    if (`$moviePlan.RelativePath -ne 'The Matrix (1999)\The Matrix (1999).mkv') { throw ('generic movie destination planner diverged: ' + `$moviePlan.RelativePath) }
    `$overridePath = Get-RenameOverrideSidecarPath -File (Get-Item -LiteralPath `$moviePath)
    @{
        SchemaVersion = 'rename_tool.v1'
        RenameTool = @{
            ForcePipelineName = `$true
            FinalName = 'Forced Matrix Name.mkv'
        }
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath `$overridePath -Encoding UTF8
    `$forcedPlan = New-PlexDestinationPlan -MediaKind Movie -File (Get-Item -LiteralPath `$moviePath) -OriginalName (Split-Path -Leaf `$moviePath) -Extension 'mkv'
    if (-not `$forcedPlan.RenameOverrideApplied -or `$forcedPlan.FileName -ne 'Forced Matrix Name.mkv') { throw ('rename override was not applied: ' + (`$forcedPlan | ConvertTo-Json -Compress)) }
    if (`$forcedPlan.RelativePath -ne 'Forced Matrix Name\Forced Matrix Name.mkv' -or `$forcedPlan.FolderName -ne 'Forced Matrix Name' -or `$forcedPlan.IdentityKey -ne 'Forced Matrix Name') { throw ('movie rename override did not force folder identity: ' + (`$forcedPlan | ConvertTo-Json -Compress)) }
    Remove-Item -LiteralPath `$overridePath -Force
    `$paths = Get-OutputPaths (Get-Item -LiteralPath `$moviePath) `$false `$null ''
    `$expectedServer = Join-Path `$Outsource 'The Matrix (1999)\The Matrix (1999).mkv'
    `$expectedLocal = Join-Path `$LocalEncoded 'The Matrix (1999)\The Matrix (1999).mkv'
    if (`$paths.ServerOut -ne `$expectedServer) { throw ('movie ServerOut changed: ' + `$paths.ServerOut) }
    if (`$paths.LocalOut -ne `$expectedLocal) { throw ('movie LocalOut changed: ' + `$paths.LocalOut) }
    if (-not `$paths.ContainsKey('PlexPlan') -or `$paths.PlexPlan.RelativePath -ne `$moviePlan.RelativePath) { throw 'Get-OutputPaths did not expose the movie Plex destination plan' }
    if (`$paths.ServerOut -match '\[|RARBG|1080p|BluRay|x265|TrueHD|Atmos') { throw ('movie release metadata leaked into output path: ' + `$paths.ServerOut) }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $movieNamingCheck

$namingPreviewLiteral = $namingPreview.Replace("'", "''")
$namingPreviewCheck = @"
`$ErrorActionPreference = 'Stop'
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-naming-preview-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$input = Join-Path `$root 'input.json'
    `$output = Join-Path `$root 'output.json'
    @{
        schema_version = 'naming_preview_request.v1'
        items = @(
            @{
                path = (Join-Path `$root '[RARBG] The.Matrix.(1999).1080p.BluRay.x265.TrueHD.Atmos.mkv')
                original_name = '[RARBG] The.Matrix.(1999).1080p.BluRay.x265.TrueHD.Atmos.mkv'
                extension = '.mkv'
                media_kind = 'Movie'
            },
            @{
                path = (Join-Path `$root 'Airplane 1980 REMASTERED 1080p BluRay HEVC x265 5.1 BONE.mkv')
                original_name = 'Airplane 1980 REMASTERED 1080p BluRay HEVC x265 5.1 BONE.mkv'
                extension = '.mkv'
                media_kind = 'Movie'
            }
        )
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath `$input -Encoding UTF8
    & '$namingPreviewLiteral' -InputJsonPath `$input -OutputJsonPath `$output
    `$data = Get-Content -LiteralPath `$output -Raw | ConvertFrom-Json -ErrorAction Stop
    if (`$data.schema_version -ne 'naming_preview.v1') { throw ('unexpected naming preview schema: ' + `$data.schema_version) }
    if (`$data.rows[0].file_name -ne 'The Matrix (1999).mkv') { throw ('pipeline naming preview diverged: ' + `$data.rows[0].file_name) }
    if (`$data.rows[0].relative_path -ne 'The Matrix (1999)\The Matrix (1999).mkv') { throw ('pipeline naming preview relative path diverged: ' + `$data.rows[0].relative_path) }
    if (`$data.rows[1].file_name -ne 'Airplane (1980).mkv') { throw ('pipeline naming preview movie scrubber diverged: ' + `$data.rows[1].file_name) }
    if (`$data.rows[1].relative_path -ne 'Airplane (1980)\Airplane (1980).mkv') { throw ('pipeline naming preview scrubbed relative path diverged: ' + `$data.rows[1].relative_path) }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $namingPreviewCheck

$routingFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-MediaRouteEncodeName',
    'Get-MediaRouteRemuxName',
    'Normalize-MediaRouteCodecName',
    'New-MediaRouteDecisionTraceEntry',
    'New-MediaRouteActionSet',
    'ConvertTo-MediaRouteHintMap',
    'Get-ActiveMediaRouteHints',
    'Get-MediaRouteDefaultMaxBitrateMbps',
    'Resolve-MediaRouteRoutingProfileName',
    'Resolve-MediaRouteSizeGuardModeName',
    'Test-MediaRouteCodecIsPlexCopyCandidate',
    'Test-MediaRouteH264PlexCompatible',
    'Test-MediaRoutePlexCopyCandidate',
    'Test-MediaEncodeOutputSizePolicy',
    'Get-MediaRouteProfileValue',
    'Get-MediaRoutePlexCompatibilityScore',
    'New-MediaRoutePlan',
    'Resolve-MediaRouteBySize',
    'Resolve-InitialMediaRoutePlan',
    'Test-IsRemuxSafeVideoCodec',
    'Resolve-RemuxCodecRoutePlan',
    'Get-ActiveMediaRoutePlanMetadata',
    'Add-MediaRoutePlanMetadataToMap'
)) -join [Environment]::NewLine
$routingPolicyCheck = @"
`$ErrorActionPreference = 'Stop'
$routingFunctions
`$smallMovie = Resolve-MediaRouteBySize -FileSizeBytes ([long](4 * 1GB)) -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3
if (`$smallMovie.Route -ne 'remux' -or -not `$smallMovie.RequiresCodecProbe) { throw 'small movie should route to remux with codec probe pending' }
if (`$smallMovie.ReasonCode -ne 'size_within_threshold') { throw ('small movie reason changed: ' + `$smallMovie.ReasonCode) }
`$largeMovie = Resolve-MediaRouteBySize -FileSizeBytes ([long](9 * 1GB)) -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3
if (`$largeMovie.Route -ne 'encode' -or -not `$largeMovie.ShouldEncode) { throw 'large movie should route to encode' }
`$largeTv = Resolve-MediaRouteBySize -FileSizeBytes ([long](4 * 1GB)) -IsTV:`$true -MovieThresholdGB 8 -TVThresholdGB 3
if (`$largeTv.Route -ne 'encode' -or `$largeTv.ThresholdGB -ne 3) { throw 'TV threshold route changed' }
`$bitrateTv = Resolve-MediaRouteBySize -FileSizeBytes ([long](12 * 1GB)) -DurationSeconds (22 * 60) -VideoCodec 'hevc' -VideoHeight 1080 -IsTV:`$true -MovieThresholdGB 20 -TVThresholdGB 20
if (`$bitrateTv.Route -ne 'encode' -or `$bitrateTv.ReasonCode -ne 'bitrate_over_threshold' -or `$bitrateTv.EstimatedBitrateMbps -le 18) { throw 'duration-adjusted bitrate route did not encode high-bitrate TV' }
if (@(`$bitrateTv.DecisionTrace | Where-Object { `$_.code -eq 'plex_compatibility_scored' }).Count -ne 1) { throw 'route decision trace should include Plex score' }
`$h264LowBitrate = Resolve-MediaRouteBySize -FileSizeBytes ([long](1400MB)) -DurationSeconds 5400 -VideoCodec 'h264' -VideoHeight 1080 -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3 -RoutingProfile 'plex_direct_stream' -AllowH264RemuxIfPlexCompatible:`$true
if (`$h264LowBitrate.Route -ne 'remux' -or `$h264LowBitrate.ReasonCode -ne 'plex_compatible_h264_remux') { throw 'low-bitrate Plex-compatible H.264 should route to remux/copy by default' }
`$largeCompatibleHevc = Resolve-MediaRouteBySize -FileSizeBytes ([long](10 * 1GB)) -DurationSeconds 7200 -VideoCodec 'hevc' -VideoHeight 1080 -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3 -RoutingProfile 'plex_direct_stream' -SizeGuardMode 'advisory'
if (`$largeCompatibleHevc.Route -ne 'remux' -or `$largeCompatibleHevc.ReasonCode -ne 'plex_compatible_size_advisory') { throw 'large Plex-compatible HEVC should not encode solely due to advisory size threshold' }
`$largeStrictHevc = Resolve-MediaRouteBySize -FileSizeBytes ([long](10 * 1GB)) -DurationSeconds 7200 -VideoCodec 'hevc' -VideoHeight 1080 -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3 -RoutingProfile 'archive_shrink' -SizeGuardMode 'strict'
if (`$largeStrictHevc.Route -ne 'encode' -or `$largeStrictHevc.ReasonCode -ne 'size_over_threshold') { throw 'archive_shrink strict routing should still encode over-threshold compatible files' }
`$forcedRemux = Resolve-MediaRouteBySize -FileSizeBytes ([long](40 * 1GB)) -DurationSeconds 7200 -VideoCodec 'vp9' -VideoHeight 2160 -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3 -RouteHints @{ force_route = 'remux'; reason = 'archive folder keeps original streams' }
if (`$forcedRemux.Route -ne 'remux' -or `$forcedRemux.ReasonCode -ne 'folder_policy_force_remux' -or -not `$forcedRemux.RequiresCodecProbe) { throw 'folder policy force_remux should request remux but still require codec probe' }
`$forcedRemuxRejected = Resolve-RemuxCodecRoutePlan -SourceCodec 'vp9' -RemuxSafeVideoCodecs @('h264', 'hevc') -BasePlan `$forcedRemux
if (`$forcedRemuxRejected.Route -ne 'encode' -or `$forcedRemuxRejected.ReasonCode -ne 'forced_remux_rejected_unsafe_codec' -or -not `$forcedRemuxRejected.FallbackFromRemux) { throw 'unsafe forced remux should fall back to encode unless explicitly allowed' }
`$forcedRemuxUnsafe = Resolve-MediaRouteBySize -FileSizeBytes ([long](40 * 1GB)) -DurationSeconds 7200 -VideoCodec 'vp9' -VideoHeight 2160 -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3 -RouteHints @{ force_route = 'remux'; allow_unsafe_forced_remux = `$true; reason = 'archive folder keeps original streams' }
`$forcedRemuxUnsafePlan = Resolve-RemuxCodecRoutePlan -SourceCodec 'vp9' -RemuxSafeVideoCodecs @('h264', 'hevc') -BasePlan `$forcedRemuxUnsafe
if (`$forcedRemuxUnsafePlan.Route -ne 'remux' -or `$forcedRemuxUnsafePlan.ReasonCode -ne 'folder_policy_force_remux_unsafe') { throw 'explicit unsafe forced remux override should allow stream copy with clear reason code' }
`$allowedCodecRoute = Resolve-MediaRouteBySize -FileSizeBytes ([long](1 * 1GB)) -DurationSeconds 3600 -VideoCodec 'vp9' -VideoHeight 1080 -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3 -RouteHints @{ allowed_video_codecs = @('h264','hevc') }
if (`$allowedCodecRoute.Route -ne 'encode' -or `$allowedCodecRoute.ReasonCode -ne 'codec_outside_policy') { throw 'folder allowed_video_codecs should force encode for unsupported codecs' }
`$strictRoute = Resolve-MediaRouteBySize -FileSizeBytes ([long](1 * 1GB)) -DurationSeconds 3600 -VideoCodec 'vp9' -VideoHeight 1080 -IsTV:`$false -MovieThresholdGB 8 -TVThresholdGB 3 -RouteHints @{ plex_strict_mode = `$true }
if (`$strictRoute.Route -ne 'encode' -or `$strictRoute.ReasonCode -ne 'plex_strict_score_below_threshold') { throw 'Plex strict mode should encode low-score sources' }
`$script:CurrentRoutePlan = `$bitrateTv
`$script:CurrentEncodeAttempts = @([ordered]@{ attempt = 'primary'; success = `$true })
`$routeMeta = Get-ActiveMediaRoutePlanMetadata
if (`$routeMeta.route_reason_code -ne 'bitrate_over_threshold' -or `$routeMeta.estimated_bitrate_mbps -le 18 -or @(`$routeMeta.decision_trace).Count -lt 2 -or @(`$routeMeta.encode_attempts).Count -ne 1) { throw 'active route plan metadata did not preserve route trace and encode attempts' }
`$routeMap = [ordered]@{}
Add-MediaRoutePlanMetadataToMap -Map `$routeMap -Metadata `$routeMeta | Out-Null
if (-not `$routeMap.Contains('route_plan') -or -not `$routeMap.Contains('route_decision_trace') -or -not `$routeMap.Contains('encode_attempts')) { throw 'route plan metadata map did not expose route_plan, decision trace, and encode attempts' }
`$routeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-route-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$routeRoot -Force | Out-Null
try {
    `$routeFile = Join-Path `$routeRoot 'small.mkv'
    Set-Content -LiteralPath `$routeFile -Value 'x' -Encoding ASCII
    `$EncodeThresholdGB = 1
    `$TVEncodeThresholdGB = 1
    `$initialRemux = Resolve-InitialMediaRoutePlan -File (Get-Item -LiteralPath `$routeFile) -IsTV:`$false
    if (`$initialRemux.Route -ne 'remux' -or -not `$initialRemux.RequiresCodecProbe) { throw 'initial route should remux small sources and require codec probe' }
    `$EncodeThresholdGB = 0
    `$initialEncode = Resolve-InitialMediaRoutePlan -File (Get-Item -LiteralPath `$routeFile) -IsTV:`$false
    if (`$initialEncode.Route -ne 'encode' -or -not `$initialEncode.ShouldEncode) { throw 'initial route should encode sources over threshold' }
} finally {
    Remove-Item -LiteralPath `$routeRoot -Recurse -Force -ErrorAction SilentlyContinue
}
if ((Normalize-MediaRouteCodecName '  HEVC  ') -ne 'hevc') { throw 'codec normalization should trim and lowercase' }
if ((Normalize-MediaRouteCodecName '') -ne 'unknown') { throw 'empty codec should normalize to unknown' }
if (-not (Test-IsRemuxSafeVideoCodec -CodecName 'HEVC' -SafeCodecs @('h264', 'hevc'))) { throw 'HEVC should be remux safe when configured' }
if (Test-IsRemuxSafeVideoCodec -CodecName 'vp9' -SafeCodecs @('h264', 'hevc')) { throw 'VP9 should not be remux safe when absent from config' }
`$safeCodec = Resolve-RemuxCodecRoutePlan -SourceCodec 'HEVC' -RemuxSafeVideoCodecs @('h264', 'hevc')
if (`$safeCodec.Route -ne 'remux' -or `$safeCodec.ReasonCode -ne 'codec_remux_safe') { throw 'safe codec remux plan changed' }
`$unsafeCodec = Resolve-RemuxCodecRoutePlan -SourceCodec 'vp9' -RemuxSafeVideoCodecs @('h264', 'hevc')
if (`$unsafeCodec.Route -ne 'encode' -or -not `$unsafeCodec.FallbackFromRemux -or `$unsafeCodec.ReasonCode -ne 'codec_not_remux_safe') { throw 'unsafe codec fallback plan changed' }
# E1 — Test-MediaEncodeOutputSizePolicy must give CPU-fallback outputs
# the compatibility growth budget (15%), not the strict default (5%).
# Without this, CPU encodes are silently rejected by 'strict' size guard
# even though they are inherently a compatibility-mode fallback.
`$sizeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-size-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$sizeRoot -Force | Out-Null
try {
    `$srcPath = Join-Path `$sizeRoot 'src.mkv'
    `$outPath = Join-Path `$sizeRoot 'out.mkv'
    # Source 1000 bytes, output 1100 bytes -> 1.10x growth.
    [System.IO.File]::WriteAllBytes(`$srcPath, (New-Object byte[] 1000))
    [System.IO.File]::WriteAllBytes(`$outPath, (New-Object byte[] 1100))
    `$strictNoCpu = Test-MediaEncodeOutputSizePolicy -SourcePath `$srcPath -OutputPath `$outPath -SizeGuardMode 'strict' -MaxGrowthPercent 5 -CompatibilityGrowthPercent 15
    if (`$strictNoCpu.Ok -or -not `$strictNoCpu.ShouldBlock -or -not `$strictNoCpu.Exceeded) { throw '1.10x source growth must be blocked under strict mode with 5% max-growth (E1 baseline)' }
    `$strictCpu = Test-MediaEncodeOutputSizePolicy -SourcePath `$srcPath -OutputPath `$outPath -SizeGuardMode 'strict' -MaxGrowthPercent 5 -CompatibilityGrowthPercent 15 -RouteReasonCode 'hardware_encoder_cpu_fallback'
    if (-not `$strictCpu.Ok -or `$strictCpu.ShouldBlock -or `$strictCpu.Exceeded) { throw '1.10x source growth must be allowed for hardware_encoder_cpu_fallback under 15% compatibility budget (E1)' }
    if ([string]`$strictCpu.Metadata.route_reason_code -ne 'hardware_encoder_cpu_fallback') { throw 'size policy metadata did not surface CPU fallback reason code (E1)' }
    if ([double]`$strictCpu.Metadata.max_growth_percent -ne 15) { throw 'size policy must use 15% compatibility growth for CPU fallback (E1)' }
} finally {
    Remove-Item -LiteralPath `$sizeRoot -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $routingPolicyCheck

$encodePolicyFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Test-IsNvencError',
    'Get-MediaPipelineConfigExtraVideoFlagsDefault',
    'Get-MediaPipelineEncodeTuningPresetNames',
    'Get-MediaPipelineEncodeTuningPresetDefault',
    'Get-MediaPipelineCpuEncodePresetNames',
    'Get-MediaPipelineCpuEncodePresetDefault',
    'Resolve-MediaPipelineCpuEncodePreset',
    'Get-MediaPipelineCpuEncodeProcessPriorityNames',
    'Get-MediaPipelineCpuEncodeProcessPriorityDefault',
    'Resolve-MediaPipelineCpuEncodeProcessPriority',
    'Get-MediaPipelineEncodeLadderNames',
    'Get-MediaPipelineEncodeLadderDefault',
    'Get-MediaPipelineRoutingProfileNames',
    'Get-MediaPipelineRoutingProfileDefault',
    'Get-MediaPipelineSizeGuardModeNames',
    'Get-MediaPipelineSizeGuardModeDefault',
    'Get-MediaPipelineAudioPassthroughProfileNames',
    'Get-MediaPipelineAudioPassthroughProfileDefault',
    'Resolve-MediaPipelineAudioPassthroughProfile',
    'Get-MediaPipelineAudioPassthroughProfileCodecs',
    'Resolve-MediaPipelineEncodeLadder',
    'Resolve-MediaPipelineRoutingProfile',
    'Resolve-MediaPipelineSizeGuardMode',
    'Resolve-MediaPipelineEncodeTuningPreset',
    'Get-MediaPipelineEncodeTuningFlags',
    'Get-MediaPipelineEncodeLadderNames',
    'Get-MediaPipelineEncodeLadderDefault',
    'Get-MediaPipelineAudioPassthroughProfileNames',
    'Get-MediaPipelineAudioPassthroughProfileDefault',
    'Resolve-MediaPipelineAudioPassthroughProfile',
    'Get-MediaPipelineAudioPassthroughProfileCodecs',
    'Resolve-MediaPipelineEncodeLadder',
    'Get-MediaRouteEncodeName',
    'Get-MediaRouteEncodeCpuFallbackName',
    'Get-MediaVideoCodecLibx265Name',
    'Get-MediaContainerMuxerMatroskaName',
    'Get-MediaEncodeLadderNames',
    'Resolve-MediaEncodeLadderName',
    'Get-MediaEncodeLadderProfile',
    'Get-MediaEncodeBoundedQuality',
    'New-EncodeVideoFlags',
    'New-EncodeFfmpegArgumentList',
    'Get-EncodeArgumentValue',
    'Get-EncodeEncoderKind',
    'Get-EncodeSelectedGpuDevice',
    'New-EncodeAttemptPlan',
    'Test-IsHardwareEncoderFailure',
    'Test-ShouldRetryEncodeWithCpuFallback'
)) -join [Environment]::NewLine
$encodePolicyCheck = @'
$ErrorActionPreference = 'Stop'
__FUNCTIONS__

$gpuFlags = @(New-EncodeVideoFlags -IsHDR:$false -UseCpuFallback:$false -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-spatial_aq', '1') -FallbackCpuQuality 20)
$gpuText = $gpuFlags -join ' '
if ($gpuText -notmatch '-c:v hevc_nvenc -preset p7 -cq 21') { throw 'GPU encode flags changed' }
if ($gpuText -notmatch '-spatial_aq 1') { throw 'GPU extra video flags were not preserved' }
if ($gpuText -notmatch '-profile:v main') { throw 'SDR encode profile changed' }

$tvAutoFlags = @(New-EncodeVideoFlags -IsTV:$true -IsHDR:$false -UseCpuFallback:$false -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-spatial_aq', '1') -FallbackCpuQuality 20 -EncodeLadder 'auto')
$tvAutoText = $tvAutoFlags -join ' '
if ($tvAutoText -notmatch '-cq 22' -or $tvAutoText -notmatch '-maxrate 90M -bufsize 180M') { throw 'TV auto encode ladder should select tv_balanced quality and bitrate limits' }

$archiveFlags = @(New-EncodeVideoFlags -IsHDR:$false -UseCpuFallback:$false -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-spatial_aq', '1') -FallbackCpuQuality 20 -EncodeLadder 'movie_archive')
$archiveText = $archiveFlags -join ' '
if ($archiveText -notmatch '-cq 20' -or $archiveText -notmatch '-maxrate 160M -bufsize 320M') { throw 'movie_archive ladder should improve quality and raise bitrate limits' }

$safeFlags = @(New-EncodeVideoFlags -IsHDR:$false -UseCpuFallback:$false -UseSafeHardwareRetry:$true -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-rc-lookahead', '60', '-multipass', 'fullres') -FallbackCpuQuality 20)
$safeText = $safeFlags -join ' '
if ($safeText -notmatch '-c:v hevc_nvenc' -or $safeText -notmatch '-aq-strength 6' -or $safeText -match '-rc-lookahead 60' -or $safeText -match '-multipass fullres') { throw 'hardware safe retry should use compatibility NVENC flags instead of fragile primary flags' }

$cpuHdrFlags = @(New-EncodeVideoFlags -IsHDR:$true -UseCpuFallback:$true -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-spatial_aq', '1') -FallbackCpuQuality 20)
$cpuText = $cpuHdrFlags -join ' '
if ($cpuText -notmatch '-c:v libx265 -preset medium -crf 20') { throw 'CPU fallback flags changed' }
if ($cpuText -match '-spatial_aq') { throw 'CPU fallback should not inherit NVENC-only extra flags' }
# F2 — CPU branch must not pass -maxrate / -bufsize alongside -crf (they
# would silently switch libx265 into constrained-CRF mode and emit a
# warning).
if ($cpuText -match '-maxrate|-bufsize') { throw 'CPU fallback must not emit -maxrate/-bufsize alongside -crf' }
# F3 — HDR10 SEI / VUI signalling lives in -x265-params, not in libav-side
# -color_* flags (D6).
if ($cpuText -notmatch '-profile:v main10' -or $cpuText -notmatch '-pix_fmt p010le') { throw 'HDR encode profile/pix_fmt changed' }
if ($cpuText -notmatch 'hdr10=1' -or $cpuText -notmatch 'hdr10-opt=1' -or $cpuText -notmatch 'repeat-headers=1' -or $cpuText -notmatch 'colorprim=bt2020' -or $cpuText -notmatch 'transfer=smpte2084' -or $cpuText -notmatch 'colormatrix=bt2020nc') {
    throw 'CPU+HDR x265-params must include hdr10/colorprim/transfer/colormatrix metadata'
}
if ($cpuText -match '-color_primaries|-color_trc|-colorspace ') { throw 'CPU+HDR must not duplicate libav -color_* flags when libx265 already carries them in -x265-params (D6)' }
$cpuSdrFlags = @(New-EncodeVideoFlags -IsHDR:$false -UseCpuFallback:$true -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -FallbackCpuQuality 20)
if (($cpuSdrFlags -join ' ') -notmatch '-profile:v main') { throw 'SDR CPU fallback profile changed' }
# Verify GPU+HDR path still carries the libav -color_* flags so NVENC sees them.
$gpuHdrFlags = @(New-EncodeVideoFlags -IsHDR:$true -UseCpuFallback:$false -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @() -FallbackCpuQuality 20)
$gpuHdrText = $gpuHdrFlags -join ' '
if ($gpuHdrText -notmatch '-color_primaries bt2020' -or $gpuHdrText -notmatch '-color_trc smpte2084' -or $gpuHdrText -notmatch '-colorspace bt2020nc') {
    throw 'GPU+HDR must still carry libav -color_* flags (NVENC consumes them)'
}

# D1 regression — half-delta CRF math must respond to every named ladder
# delta. With banker's rounding this used to silently zero out the ±1
# ladders (tv_balanced, plex_compat, movie_archive). With AwayFromZero
# rounding all five named ladders produce distinct CRF values from base 20.
function script:_ExtractCpuCrf {
    param([array]$Flags)
    $joined = ($Flags -join ' ')
    if ($joined -match '-crf\s+(\d+)') { return [int]$Matches[1] }
    return -1
}
$ladderCrf = @{}
foreach ($ladder in 'movie_balanced','tv_balanced','plex_compat','movie_archive','tv_space_saver') {
    $isTv = $ladder -like 'tv_*'
    $f = @(New-EncodeVideoFlags -IsHDR:$false -IsTV:$isTv -UseCpuFallback:$true -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -FallbackCpuQuality 20 -EncodeLadder $ladder)
    $ladderCrf[$ladder] = script:_ExtractCpuCrf -Flags $f
}
if ($ladderCrf['movie_balanced'] -ne 20) { throw "movie_balanced CPU CRF = $($ladderCrf['movie_balanced']), expected 20" }
if ($ladderCrf['tv_balanced']    -ne 21) { throw "tv_balanced CPU CRF = $($ladderCrf['tv_balanced']), expected 21 (D1 banker rounding regression)" }
if ($ladderCrf['plex_compat']    -ne 21) { throw "plex_compat CPU CRF = $($ladderCrf['plex_compat']), expected 21 (D1 banker rounding regression)" }
if ($ladderCrf['movie_archive']  -ne 19) { throw "movie_archive CPU CRF = $($ladderCrf['movie_archive']), expected 19 (D1 banker rounding regression)" }
if ($ladderCrf['tv_space_saver'] -ne 21) { throw "tv_space_saver CPU CRF = $($ladderCrf['tv_space_saver']), expected 21" }

# CpuPreset must reach the CPU branch.
$customPresetFlags = @(New-EncodeVideoFlags -IsHDR:$false -UseCpuFallback:$true -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -FallbackCpuQuality 20 -CpuPreset 'veryfast')
if (($customPresetFlags -join ' ') -notmatch '-preset veryfast') { throw 'CpuPreset parameter not honored on CPU branch' }
$invalidPresetFlags = @(New-EncodeVideoFlags -IsHDR:$false -UseCpuFallback:$true -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -FallbackCpuQuality 20 -CpuPreset 'evil; rm -rf /')
if (($invalidPresetFlags -join ' ') -notmatch '-preset medium') { throw 'invalid CpuPreset must fall back to default medium, not pass through unvalidated' }

$args = @(New-EncodeFfmpegArgumentList -InputPath 'input.mkv' -ExtraInputs @('-i', 'sub.srt') -GlobalTitle 'Encoded by Test' -VideoFlags @('-c:v', 'hevc_nvenc') -AudioArgs @('-c:a', 'aac') -SubtitleMapArgs @('-map', '1:0') -OutputPath 'output.mkv')
$expectedArgs = @('-i', 'input.mkv', '-i', 'sub.srt', '-map', '0:V', '-map', '0:t?', '-map_chapters', '0', '-map_metadata', '0', '-metadata', 'title=Encoded by Test', '-c:v', 'hevc_nvenc', '-c:a', 'aac', '-map', '1:0', '-c:t', 'copy', '-f', 'matroska', '-max_muxing_queue_size', '1024', '-y', 'output.mkv')
if (($args -join ([char]0)) -ne ($expectedArgs -join ([char]0))) { throw 'common encode FFmpeg argument layout changed' }

$primaryPlan = New-EncodeAttemptPlan -UseCpuFallback:$false -IsHDR:$false -InputPath 'input.mkv' -GlobalTitle 'Encoded by Test' -OutputPath 'primary.mkv' -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-spatial_aq', '1') -FallbackCpuQuality 20
if ($primaryPlan.Attempt -ne 'primary' -or $primaryPlan.Route -ne 'encode' -or $primaryPlan.Label -ne 'ENCODE' -or $primaryPlan.ProgressStage -ne 'encode' -or $primaryPlan.ReproStage -ne 'encode') { throw 'primary encode attempt metadata changed' }
if (@($primaryPlan.ArgumentList) -notcontains 'primary.mkv') { throw 'primary encode attempt did not include output path' }
if ($primaryPlan.SelectedEncoder -ne 'hevc_nvenc' -or $primaryPlan.EncoderKind -ne 'nvenc' -or $primaryPlan.SelectedGpuDevice -ne '') { throw 'primary encode selected encoder/GPU metadata changed' }

$gpuPinnedPlan = New-EncodeAttemptPlan -UseCpuFallback:$false -IsHDR:$false -InputPath 'input.mkv' -GlobalTitle 'Encoded by Test' -OutputPath 'primary-gpu1.mkv' -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-gpu', '1', '-spatial_aq', '1') -FallbackCpuQuality 20
if ($gpuPinnedPlan.SelectedEncoder -ne 'hevc_nvenc' -or $gpuPinnedPlan.EncoderKind -ne 'nvenc' -or $gpuPinnedPlan.SelectedGpuDevice -ne '1') { throw 'pinned GPU encode selected encoder/GPU metadata changed' }

$safePlan = New-EncodeAttemptPlan -UseSafeHardwareRetry:$true -IsHDR:$false -InputPath 'input.mkv' -GlobalTitle 'Encoded by Test' -OutputPath 'safe.mkv' -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-rc-lookahead', '60') -FallbackCpuQuality 20
if ($safePlan.Attempt -ne 'hardware_safe_retry' -or $safePlan.Label -ne 'ENCODE-SAFE' -or $safePlan.ProgressStage -ne 'encode_safe' -or $safePlan.ReproStage -ne 'encode-safe' -or -not $safePlan.UseSafeHardwareRetry) { throw 'hardware safe retry attempt metadata changed' }
if ((@($safePlan.VideoFlags) -join ' ') -match '-rc-lookahead 60') { throw 'hardware safe retry plan retained fragile lookahead flag' }
if ($safePlan.SelectedEncoder -ne 'hevc_nvenc' -or $safePlan.EncoderKind -ne 'nvenc') { throw 'hardware safe retry selected encoder metadata changed' }

$fallbackPlan = New-EncodeAttemptPlan -UseCpuFallback:$true -IsHDR:$true -InputPath 'input.mkv' -GlobalTitle 'Encoded by Test' -OutputPath 'fallback.mkv' -VideoCodec 'hevc_nvenc' -VideoPreset 'p7' -VideoQuality 21 -ExtraVideoFlags @('-spatial_aq', '1') -FallbackCpuQuality 20
if ($fallbackPlan.Attempt -ne 'cpu_fallback' -or $fallbackPlan.Route -ne 'encode-cpu-fallback' -or $fallbackPlan.Label -ne 'ENCODE-CPU' -or $fallbackPlan.ProgressStage -ne 'encode_cpu' -or $fallbackPlan.ReproStage -ne 'encode-cpu') { throw 'CPU fallback encode attempt metadata changed' }
if ((@($fallbackPlan.VideoFlags) -join ' ') -notmatch '-c:v libx265') { throw 'CPU fallback plan did not use libx265' }
if ($fallbackPlan.SelectedEncoder -ne 'libx265' -or $fallbackPlan.EncoderKind -ne 'cpu' -or $fallbackPlan.SelectedGpuDevice -ne '') { throw 'CPU fallback selected encoder/GPU metadata changed' }
# D4 — every plan shape must expose CpuPreset so consumers iterating
# encode_attempts[] don't NRE on non-CPU rows.
if (-not $fallbackPlan.PSObject.Properties['CpuPreset']) { throw 'CPU fallback plan missing CpuPreset field' }
if ([string]$fallbackPlan.CpuPreset -ne 'medium') { throw "CPU fallback plan CpuPreset = '$($fallbackPlan.CpuPreset)', expected 'medium'" }
if (-not $primaryPlan.PSObject.Properties['CpuPreset']) { throw 'primary plan must include CpuPreset (= '''') for schema parity (D4)' }
if ([string]$primaryPlan.CpuPreset -ne '') { throw "primary plan CpuPreset = '$($primaryPlan.CpuPreset)', expected '' (D4)" }
if (-not $safePlan.PSObject.Properties['CpuPreset']) { throw 'safe-retry plan must include CpuPreset (= '''') for schema parity (D4)' }
if ([string]$safePlan.CpuPreset -ne '') { throw "safe-retry plan CpuPreset = '$($safePlan.CpuPreset)', expected '' (D4)" }

if (-not (Test-ShouldRetryEncodeWithCpuFallback -Success:$false -StopRequested:$false -ErrorText 'No NVENC capable devices found')) { throw 'NVENC failure should trigger CPU fallback' }
if (-not (Test-ShouldRetryEncodeWithCpuFallback -Success:$false -StopRequested:$false -VideoCodec 'hevc_amf' -ErrorText 'AMF encoder initialization failed')) { throw 'AMF hardware failure should trigger CPU fallback' }
if (-not (Test-ShouldRetryEncodeWithCpuFallback -Success:$false -StopRequested:$false -VideoCodec 'hevc_qsv' -ErrorText 'Error initializing an MFX session')) { throw 'QSV hardware failure should trigger CPU fallback' }
if (Test-ShouldRetryEncodeWithCpuFallback -Success:$false -StopRequested:$false -VideoCodec 'libx265' -ErrorText 'AMF encoder initialization failed') { throw 'software encoder failure should not trigger hardware fallback' }
if (Test-ShouldRetryEncodeWithCpuFallback -Success:$true -StopRequested:$false -ErrorText 'No NVENC capable devices found') { throw 'successful encode should not trigger CPU fallback' }
if (Test-ShouldRetryEncodeWithCpuFallback -Success:$false -StopRequested:$true -ErrorText 'No NVENC capable devices found') { throw 'operator stop should not trigger CPU fallback' }
if (Test-ShouldRetryEncodeWithCpuFallback -Success:$false -StopRequested:$false -ErrorText 'Invalid data found when processing input') { throw 'generic FFmpeg failure should not trigger CPU fallback' }
'@.Replace('__FUNCTIONS__', $encodePolicyFunctions)
Invoke-PowerShellBehaviorCheck -ScriptText $encodePolicyCheck

$configSchemaFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-MediaPipelineConfigCurrentSchemaVersion',
    'Get-MediaPipelineConfigSchemaKey',
    'Get-MediaPipelineConfigRequiredKeys',
    'Get-MediaPipelineConfigArrayKeys',
    'Get-MediaPipelineConfigOrderedKeys',
    'Get-MediaPipelineConfigExtraVideoFlagsDefault',
    'Get-MediaPipelineEncodeTuningPresetNames',
    'Get-MediaPipelineEncodeTuningPresetDefault',
    'Get-MediaPipelineCpuEncodePresetNames',
    'Get-MediaPipelineCpuEncodePresetDefault',
    'Resolve-MediaPipelineCpuEncodePreset',
    'Get-MediaPipelineCpuEncodeProcessPriorityNames',
    'Get-MediaPipelineCpuEncodeProcessPriorityDefault',
    'Resolve-MediaPipelineCpuEncodeProcessPriority',
    'Get-MediaPipelineEncodeLadderNames',
    'Get-MediaPipelineEncodeLadderDefault',
    'Get-MediaPipelineRoutingProfileNames',
    'Get-MediaPipelineRoutingProfileDefault',
    'Get-MediaPipelineSizeGuardModeNames',
    'Get-MediaPipelineSizeGuardModeDefault',
    'Get-MediaPipelineAudioPassthroughProfileNames',
    'Get-MediaPipelineAudioPassthroughProfileDefault',
    'Resolve-MediaPipelineAudioPassthroughProfile',
    'Get-MediaPipelineAudioPassthroughProfileCodecs',
    'Resolve-MediaPipelineEncodeLadder',
    'Resolve-MediaPipelineRoutingProfile',
    'Resolve-MediaPipelineSizeGuardMode',
    'Resolve-MediaPipelineEncodeTuningPreset',
    'Get-MediaPipelineEncodeTuningFlags',
    'Get-MediaPipelineConfigDefaultValues',
    'Get-MediaPipelineConfigValue',
    'Test-MediaPipelineConfigHasKey',
    'ConvertTo-MediaPipelineConfigBool',
    'Normalize-MediaPipelineConfigPathForCompare',
    'Test-MediaPipelineConfigPathShape',
    'Test-MediaPipelineConfigSubtitleToggles',
    'Test-MediaPipelineConfigEncodeAudioPolicy',
    'Resolve-MediaPipelineConfigSchemaVersion',
    'Test-MediaPipelineConfigSchema'
)) -join [Environment]::NewLine
$configSchemaCheck = @"
`$ErrorActionPreference = 'Stop'
$configSchemaFunctions
`$base = @{
    SourceMovies = 'movies'
    SourceTV = 'tv'
    Outsource = 'out'
    LocalBase = 'local'
    EncodeThresholdGB = 8
    TVEncodeThresholdGB = 3
    MinFreeSpaceGB = 50
    VideoCodec = 'hevc_nvenc'
    VideoPreset = 'p7'
    VideoQuality = 22
    OutputContainer = 'mkv'
    CompatibleAudioCodecs = @('aac')
    SubKeepLanguages = @('eng')
    SubSDHTitleKeywords = @('sdh')
    SubSupplementalKeywords = @('sign')
    DropAssAfterConversion = `$false
    RemuxSafeVideoCodecs = @('hevc')
    ValidExtensions = @('.mkv')
    FileStabilityWait = 15
    EnableIntegrityCheck = `$true
    CreateTVSubfolder = `$true
    RobocopyFlags = @('/J')
    DebugMode = `$false
    SkipStabilityCheck = `$false
}
`$missingVersion = Test-MediaPipelineConfigSchema -Config `$base
if (-not `$missingVersion.Ok) { throw 'missing schema version should remain PSD1-compatible' }
if (`$missingVersion.EffectiveSchemaVersion -ne 1) { throw 'missing schema version did not use current schema' }
if (`$missingVersion.Warnings.Count -ne 0) { throw 'missing schema version should not warn during compatibility load' }
if ((Get-MediaPipelineConfigOrderedKeys)[0] -ne 'ConfigSchemaVersion') { throw 'schema version must be first in generated config order' }
if ((Get-MediaPipelineConfigOrderedKeys) -notcontains 'EncodeLadder') { throw 'schema ordered keys missing EncodeLadder' }
if ((Get-MediaPipelineConfigOrderedKeys) -notcontains 'AudioPassthroughProfile') { throw 'schema ordered keys missing AudioPassthroughProfile' }
if ((Get-MediaPipelineConfigArrayKeys) -notcontains 'Tx3gExtractLanguages') { throw 'schema array keys missing tx3g languages' }
if ((Resolve-MediaPipelineEncodeLadder -Ladder 'movie_archive') -ne 'movie_archive') { throw 'valid encode ladder should resolve unchanged' }
if ((Resolve-MediaPipelineEncodeLadder -Ladder 'bad-ladder') -ne 'auto') { throw 'invalid encode ladder should fall back to auto' }
if ((Resolve-MediaPipelineAudioPassthroughProfile -Profile 'lossless_passthrough') -ne 'lossless_passthrough') { throw 'valid audio passthrough profile should resolve unchanged' }
if ((Resolve-MediaPipelineAudioPassthroughProfile -Profile '' -LegacyCompatibleAudioCodecs @('aac')) -ne 'custom_codec_list') { throw 'legacy audio codec lists should resolve to custom_codec_list' }
if (@(Get-MediaPipelineAudioPassthroughProfileCodecs -Profile 'compatibility') -contains 'truehd') { throw 'compatibility audio profile should not include TrueHD' }
`$schemaDoc = @'
$configJsonSchemaText
'@ | ConvertFrom-Json
if ([int]`$schemaDoc.'x-config-schema-version' -ne (Get-MediaPipelineConfigCurrentSchemaVersion)) { throw 'json config schema version does not match current PowerShell schema version' }
`$schemaProps = @(`$schemaDoc.properties.PSObject.Properties.Name)
foreach (`$key in @(Get-MediaPipelineConfigOrderedKeys)) {
    if (`$schemaProps -notcontains `$key) { throw "json config schema missing ordered key `$key" }
}
foreach (`$key in @(Get-MediaPipelineConfigRequiredKeys)) {
    if (@(`$schemaDoc.required) -notcontains `$key) { throw "json config schema missing required key `$key" }
}
foreach (`$key in @(Get-MediaPipelineConfigArrayKeys)) {
    `$prop = `$schemaDoc.properties.PSObject.Properties[`$key]
    if (-not `$prop -or `$prop.Value.type -ne 'array') { throw "json config schema did not mark `$key as an array" }
}
`$defaults = Get-MediaPipelineConfigDefaultValues
if (`$defaults['ConfigSchemaVersion'] -ne (Get-MediaPipelineConfigCurrentSchemaVersion)) { throw 'default config schema version does not match current schema version' }
if (@(`$defaults.Keys)[0] -ne 'ConfigSchemaVersion') { throw 'default config schema version must be first' }
`$defaultCheck = Test-MediaPipelineConfigSchema -Config `$defaults
if (-not `$defaultCheck.Ok) { throw "default config did not satisfy schema: `$(`$defaultCheck.Errors -join '; ')" }
if (`$defaults['SourceMovies'] -ne 'C:\Videos\Incoming\Movies') { throw 'default SourceMovies changed unexpectedly' }
if (`$defaults['AllowSystemTools'] -ne `$false) { throw 'AllowSystemTools default must stay false' }
if (`$defaults['ConvertTx3gToSrt'] -ne `$true) { throw 'ConvertTx3gToSrt default must stay true' }
if (`$defaults['EncodeLadder'] -ne 'auto') { throw 'EncodeLadder default must stay auto' }
if (`$defaults['IndexScanTimeoutSeconds'] -ne 1800) { throw 'IndexScanTimeoutSeconds default changed unexpectedly' }
if (((Get-MediaPipelineConfigExtraVideoFlagsDefault -Codec 'hevc_nvenc') -join ' ') -notmatch '-rc-lookahead 60') { throw 'hevc_nvenc default extra video flags changed unexpectedly' }
if (@(Get-MediaPipelineConfigExtraVideoFlagsDefault -Codec 'libx265').Count -ne 0) { throw 'non-nvenc codec should not get extra video flags by default' }
`$newer = `$base.Clone()
`$newer['ConfigSchemaVersion'] = 999
`$newerCheck = Test-MediaPipelineConfigSchema -Config `$newer
if (-not `$newerCheck.Ok -or `$newerCheck.EffectiveSchemaVersion -ne 1) { throw 'newer schema should load through current compatibility checks' }
if (`$newerCheck.Warnings.Count -eq 0) { throw 'newer schema should produce a compatibility warning' }
`$bad = `$base.Clone()
`$bad.Remove('SourceMovies')
`$badCheck = Test-MediaPipelineConfigSchema -Config `$bad
if (`$badCheck.Ok) { throw 'missing required config key should fail schema validation' }
if ((`$badCheck.Errors -join '|') -notmatch 'SourceMovies') { throw 'missing SourceMovies error not reported' }
`$emptyPath = `$base.Clone()
`$emptyPath['LocalBase'] = ' '
`$emptyPathCheck = Test-MediaPipelineConfigSchema -Config `$emptyPath
if (`$emptyPathCheck.Ok -or (`$emptyPathCheck.Errors -join '|') -notmatch 'LocalBase cannot be empty') { throw 'empty LocalBase should fail path-shape validation' }
`$samePath = `$base.Clone()
`$samePath['LocalBase'] = 'out'
`$samePathCheck = Test-MediaPipelineConfigSchema -Config `$samePath
if (`$samePathCheck.Ok -or (`$samePathCheck.Errors -join '|') -notmatch 'LocalBase and Outsource') { throw 'LocalBase and Outsource overlap should fail schema validation' }
`$badTx3gDrop = `$base.Clone()
`$badTx3gDrop['ConvertTx3gToSrt'] = `$false
`$badTx3gDrop['DropTx3gAfterConversion'] = `$true
`$badTx3gDropCheck = Test-MediaPipelineConfigSchema -Config `$badTx3gDrop
if (`$badTx3gDropCheck.Ok -or (`$badTx3gDropCheck.Errors -join '|') -notmatch 'DropTx3gAfterConversion requires ConvertTx3gToSrt') { throw 'tx3g drop-without-convert should fail schema validation' }
`$badTx3gSidecar = `$base.Clone()
`$badTx3gSidecar['ConvertTx3gToSrt'] = `$false
`$badTx3gSidecar['CreateExternalTx3gSrtSidecars'] = `$true
`$badTx3gSidecarCheck = Test-MediaPipelineConfigSchema -Config `$badTx3gSidecar
if (`$badTx3gSidecarCheck.Ok -or (`$badTx3gSidecarCheck.Errors -join '|') -notmatch 'CreateExternalTx3gSrtSidecars requires ConvertTx3gToSrt') { throw 'tx3g sidecar-without-convert should fail schema validation' }
`$badBdpgsDrop = `$base.Clone()
`$badBdpgsDrop['ConvertBdpgsToSrt'] = `$false
`$badBdpgsDrop['DropBdpgsAfterConversion'] = `$true
`$badBdpgsDropCheck = Test-MediaPipelineConfigSchema -Config `$badBdpgsDrop
if (`$badBdpgsDropCheck.Ok -or (`$badBdpgsDropCheck.Errors -join '|') -notmatch 'DropBdpgsAfterConversion requires ConvertBdpgsToSrt') { throw 'BDPGS drop-without-convert should fail schema validation' }
`$badEncodeLadder = `$base.Clone()
`$badEncodeLadder['EncodeLadder'] = 'raw-freeform-ladder'
`$badEncodeLadderCheck = Test-MediaPipelineConfigSchema -Config `$badEncodeLadder
if (`$badEncodeLadderCheck.Ok -or (`$badEncodeLadderCheck.Errors -join '|') -notmatch 'EncodeLadder must be one of') { throw 'invalid EncodeLadder should fail schema validation' }
`$missingOcrTool = `$base.Clone()
`$missingOcrTool['ConvertBdpgsToSrt'] = `$true
`$missingOcrTool['BdpgsOcrToolPath'] = ''
`$missingOcrToolCheck = Test-MediaPipelineConfigSchema -Config `$missingOcrTool
if (`$missingOcrToolCheck.Ok -or (`$missingOcrToolCheck.Errors -join '|') -notmatch 'ConvertBdpgsToSrt requires BdpgsOcrToolPath') { throw 'BDPGS OCR conversion should require an OCR tool path' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $configSchemaCheck

$stateStoreFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Write-MediaPipelineStateStoreLog',
    'New-MediaPipelineStateLayout',
    'Get-MediaPipelineStateDirectories',
    'Move-MediaPipelineLegacyStateFile',
    'Move-MediaPipelineLegacyStateDirectory',
    'Initialize-MediaPipelineStateLayout'
)) -join [Environment]::NewLine
$stateStoreCheck = @"
`$ErrorActionPreference = 'Stop'
$stateStoreFunctions
`$td = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-state-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path `$td -Force | Out-Null
    `$legacyProgress = Join-Path `$td 'Progress'
    `$legacyCompleted = Join-Path `$td 'Completed'
    `$legacyFailed = Join-Path `$td 'Failed'
    `$legacyPending = Join-Path `$td 'PendingServerPush'
    foreach (`$dir in @(`$legacyProgress, `$legacyCompleted, (Join-Path `$legacyFailed 'Markers'), (Join-Path `$legacyFailed 'Reports'), `$legacyPending)) {
        New-Item -ItemType Directory -Path `$dir -Force | Out-Null
    }
    Set-Content -LiteralPath (Join-Path `$td 'pipeline_progress.json') -Value '{"TotalProcessed":7}' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path `$td 'pipeline_events.jsonl') -Value '{"event_type":"job_completed"}' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path `$td 'pipeline_pause.flag') -Value 'pause' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path `$legacyProgress 'queue_snapshot.json') -Value '{"schema_version":"queue_plan_snapshot.v1"}' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path `$legacyCompleted 'completed_jobs.jsonl') -Value '{"schema_version":"completed_job.v1"}' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path `$legacyFailed 'Markers\failure.json') -Value '{"schema_version":"source_failure.v1"}' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path `$legacyPending 'parked.manifest.json') -Value '{"manifest_state":"parked"}' -Encoding UTF8

    `$layout = New-MediaPipelineStateLayout -LocalBase `$td
    if (`$layout.SchemaVersion -ne 'media_pipeline_state_layout.v1') { throw 'state layout schema version changed' }
    if (`$layout.Root -ne (Join-Path `$td 'State')) { throw 'state layout root is not under LocalBase\State' }
    if (`$layout.Paths.ProgressFile -ne (Join-Path `$layout.Progress 'pipeline_progress.json')) { throw 'progress path not under state progress folder' }
    if (`$layout.Paths.CompletedJobsManifest -ne (Join-Path `$layout.Completed 'completed_jobs.jsonl')) { throw 'completed manifest path not under state completed folder' }
    if (@(Get-MediaPipelineStateDirectories -Layout `$layout) -notcontains `$layout.PendingPush) { throw 'state directory list missing pending push folder' }

    Initialize-MediaPipelineStateLayout -Layout `$layout -MigrateLegacy | Out-Null
    foreach (`$dir in @(Get-MediaPipelineStateDirectories -Layout `$layout)) {
        if (-not (Test-Path -LiteralPath `$dir -PathType Container)) { throw "state directory not created: `$dir" }
    }
    if (-not (Test-Path -LiteralPath `$layout.Paths.ProgressFile)) { throw 'legacy root progress file did not migrate to state store' }
    if (-not (Test-Path -LiteralPath `$layout.Paths.PipelineEventLogFile)) { throw 'legacy event log did not migrate to state store' }
    if (-not (Test-Path -LiteralPath `$layout.Paths.PauseFlag)) { throw 'legacy pause flag did not migrate to state store' }
    if (-not (Test-Path -LiteralPath `$layout.Paths.QueueSnapshot)) { throw 'legacy queue snapshot did not migrate to state store' }
    if (-not (Test-Path -LiteralPath `$layout.Paths.CompletedJobsManifest)) { throw 'legacy completed manifest did not migrate to state store' }
    if (-not (Test-Path -LiteralPath (Join-Path `$layout.FailureMarkers 'failure.json'))) { throw 'legacy failure marker did not migrate to state store' }
    if (-not (Test-Path -LiteralPath (Join-Path `$layout.PendingPush 'parked.manifest.json'))) { throw 'legacy pending manifest did not migrate to state store' }
} finally {
    Remove-Item -LiteralPath `$td -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $stateStoreCheck

$backfillCheck = @"
`$ErrorActionPreference = 'Stop'
`$scriptPath = '$($backfill.Replace("'", "''"))'
`$td = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-backfill-' + [guid]::NewGuid().ToString('N'))
try {
    `$outsource = Join-Path `$td 'outsource'
    `$local = Join-Path `$td 'local'
    `$movieDir = Join-Path `$outsource 'Movies\Example Movie'
    New-Item -ItemType Directory -Path `$movieDir, `$local -Force | Out-Null
    Set-Content -LiteralPath (Join-Path `$movieDir 'Example Movie.mp4') -Value 'media' -Encoding UTF8
    [ordered]@{
        route = 'remux'
        source_path = 'E:\Incoming\Example Movie.mkv'
        output_file = 'Example Movie.mp4'
        output_size = 5
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path `$movieDir 'Example Movie.pipeline.json') -Encoding UTF8
    Set-Content -LiteralPath (Join-Path `$movieDir 'Bad.pipeline.json') -Value '{bad json' -Encoding UTF8

    `$completed = Join-Path `$local 'State\Completed'
    New-Item -ItemType Directory -Path `$completed -Force | Out-Null
    `$manifest = Join-Path `$completed 'completed_jobs.jsonl'
    Set-Content -LiteralPath `$manifest -Value 'old-manifest' -Encoding UTF8
    `$checkpoint = Join-Path `$completed 'completed_manifest_backfill_progress.json'

    `$dryOutput = & (Get-Command pwsh).Source -NoProfile -ExecutionPolicy Bypass -File `$scriptPath -OutsourceRoot `$outsource -LocalBase `$local -DryRun 2>&1 | Out-String
    if (`$LASTEXITCODE -ne 0) { throw "backfill dry run failed: `$dryOutput" }
    if ((Get-Content -LiteralPath `$manifest -Raw) -notmatch 'old-manifest') { throw 'dry run modified existing manifest' }
    if (@(Get-ChildItem -LiteralPath `$completed -Filter 'completed_jobs.jsonl.bak.*' -ErrorAction SilentlyContinue).Count -ne 0) { throw 'dry run created a backup' }
    `$dryCheckpoint = Get-Content -LiteralPath `$checkpoint -Raw | ConvertFrom-Json
    if (`$dryCheckpoint.schema_version -ne 'completed_manifest_backfill_checkpoint.v1') { throw 'dry-run checkpoint schema missing' }
    if (`$dryCheckpoint.status -ne 'dry_run_completed' -or -not `$dryCheckpoint.dry_run) { throw 'dry-run checkpoint status missing' }
    if ([int]`$dryCheckpoint.ingested -ne 1 -or [int]`$dryCheckpoint.skipped -ne 1) { throw 'dry-run checkpoint counts wrong' }

    `$runOutput = & (Get-Command pwsh).Source -NoProfile -ExecutionPolicy Bypass -File `$scriptPath -OutsourceRoot `$outsource -LocalBase `$local 2>&1 | Out-String
    if (`$LASTEXITCODE -ne 0) { throw "backfill run failed: `$runOutput" }
    `$lines = @(Get-Content -LiteralPath `$manifest)
    if (`$lines.Count -ne 1) { throw ('manifest should contain one valid sidecar entry, got ' + `$lines.Count) }
    `$row = `$lines[0] | ConvertFrom-Json
    if ([string]`$row.output_path -notmatch 'Example Movie\.mp4') { throw 'backfill did not infer output path from output_file' }
    if ([string]::IsNullOrWhiteSpace([string]`$row.logged_at)) { throw 'backfill entry missing logged_at' }
    `$backups = @(Get-ChildItem -LiteralPath `$completed -Filter 'completed_jobs.jsonl.bak.*' -ErrorAction SilentlyContinue)
    if (`$backups.Count -ne 1) { throw ('expected one manifest backup, got ' + `$backups.Count) }
    if ((Get-Content -LiteralPath `$backups[0].FullName -Raw) -notmatch 'old-manifest') { throw 'backfill backup did not preserve previous manifest' }
    `$checkpointPayload = Get-Content -LiteralPath `$checkpoint -Raw | ConvertFrom-Json
    if (`$checkpointPayload.status -ne 'completed' -or `$checkpointPayload.dry_run) { throw 'completed checkpoint status wrong' }
    if ([int]`$checkpointPayload.ingested -ne 1 -or [int]`$checkpointPayload.skipped -ne 1) { throw 'completed checkpoint counts wrong' }
    if (@(Get-ChildItem -LiteralPath `$completed -Filter '.*.tmp' -Force -ErrorAction SilentlyContinue).Count -ne 0) { throw 'backfill left atomic temp files' }
} finally {
    Remove-Item -LiteralPath `$td -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $backfillCheck

$integrityFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-ExternalToolFailureCode',
    'Set-ExternalToolResultProperty',
    'Invoke-ExternalToolCommand',
    'Invoke-FFprobeCommand',
    'Get-FFprobeFailureCode',
    'New-FileIntegrityResult',
    'Test-FileIntegrityDetailed',
    'Test-FileIntegrity'
)) -join [Environment]::NewLine
$integrityCheck = @"
`$ErrorActionPreference = 'Stop'
`$EnableIntegrityCheck = `$true
`$ffprobePath = 'stub-ffprobe.exe'
$integrityFunctions
function Invoke-NativeCommand {
    param([string]`$FilePath, [array]`$ArgumentList, [int]`$TimeoutSeconds = 0)
    return @{ ExitCode = 1; Output = ''; Error = 'EBML header parsing failed'; TimedOut = `$false; Stopped = `$false }
}
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-integrity-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$missing = Test-FileIntegrityDetailed -FilePath (Join-Path `$root 'missing.mkv')
    if (`$missing.Ok -or `$missing.Reason -notmatch 'does not exist') { throw 'missing file should fail with explicit reason' }
    if (`$missing.ErrorCode -ne 'FILE_MISSING') { throw ('missing file has wrong code: ' + `$missing.ErrorCode) }

    `$zero = Join-Path `$root 'zero.mkv'
    New-Item -ItemType File -Path `$zero -Force | Out-Null
    `$zeroResult = Test-FileIntegrityDetailed -FilePath `$zero
    if (`$zeroResult.Ok -or `$zeroResult.Reason -notmatch 'zero bytes') { throw 'zero-byte file should fail with explicit reason' }
    if (`$zeroResult.ErrorCode -ne 'FILE_ZERO_BYTES') { throw ('zero-byte file has wrong code: ' + `$zeroResult.ErrorCode) }

    `$bad = Join-Path `$root 'bad.mkv'
    Set-Content -LiteralPath `$bad -Value 'not a matroska file' -Encoding ASCII
    `$badResult = Test-FileIntegrityDetailed -FilePath `$bad
    if (`$badResult.Ok) { throw 'ffprobe failure should fail integrity' }
    if (`$badResult.Reason -notmatch 'EBML header parsing failed') { throw ('ffprobe stderr missing from reason: ' + `$badResult.Reason) }
    if (`$badResult.ErrorCode -ne 'MEDIA_CONTAINER_INVALID') { throw ('ffprobe EBML failure has wrong code: ' + `$badResult.ErrorCode) }
    if (Test-FileIntegrity -FilePath `$bad) { throw 'boolean wrapper should preserve failed detailed result' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $integrityCheck

$failureCodeFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-MediaContainerMuxerMatroskaName',
    'Get-FFprobeFailureCode',
    'Get-ErrorTextSummary',
    'Get-FFmpegFailureCode',
    'Get-MkvmergeFailureCode',
    'Normalize-FailureCode',
    'Get-SourceIntegrityFailureCode',
    'Get-MediaFailureCode',
    'Get-FailureCategory',
    'New-StandardFailureRecord',
    'Add-RoundFailureRecord',
    'Write-FailureJsonAtomic',
    'Write-RoundFailureSummary'
)) -join [Environment]::NewLine
$failureCodeCheck = @"
`$ErrorActionPreference = 'Stop'
function Get-FailureSuggestedAction { param([string]`$Stage, [string]`$Reason) return 'action' }
$failureCodeFunctions
`$sourceFailure = [pscustomobject]@{ ErrorCode = 'MEDIA_CONTAINER_INVALID' }
if ((Get-SourceIntegrityFailureCode -IntegrityResult `$sourceFailure) -ne 'SOURCE_MEDIA_CONTAINER_INVALID') { throw 'source integrity code mapping failed' }
if ((Get-MediaFailureCode -Stage 'remux-av' -Reason 'FFmpeg remux AV stage failed') -ne 'REMUX_FFMPEG_FAILED') { throw 'remux failure code mapping failed' }
if ((Get-FFmpegFailureCode -Stage 'encode' -ErrorText 'No NVENC capable devices found') -ne 'ENCODE_NVENC_FAILED') { throw 'NVENC code mapping failed' }
if ((Get-FFmpegFailureCode -Stage 'encode' -ErrorText 'Error while decoding stream #0:0: Invalid NAL unit') -ne 'SOURCE_MEDIA_DECODE_FAILED') { throw 'decode-failure code mapping failed' }
if ((Get-FFmpegFailureCode -Stage 'remux-av' -ErrorText 'Packet corrupt and partial file') -ne 'SOURCE_MEDIA_TRUNCATED') { throw 'truncated media code mapping failed' }
# E2 — CPU-fallback failures must land in CPU-specific buckets so triage
# can show CPU-relevant guidance instead of NVENC remediation.
if ((Get-FFmpegFailureCode -Stage 'encode-cpu' -ErrorText '[KILLED: TIMEOUT after 21600s]') -ne 'ENCODE_CPU_TIMEOUT') { throw 'CPU encode timeout did not map to ENCODE_CPU_TIMEOUT (E2)' }
if ((Get-FFmpegFailureCode -Stage 'encode-cpu' -ErrorText 'Cannot allocate memory') -ne 'ENCODE_CPU_OOM') { throw 'CPU encode OOM did not map to ENCODE_CPU_OOM (E2)' }
if ((Get-FFmpegFailureCode -Stage 'encode-cpu' -ErrorText 'No space left on device') -ne 'ENCODE_CPU_DISK_FULL') { throw 'CPU encode disk-full did not map to ENCODE_CPU_DISK_FULL (E2)' }
if ((Get-FFmpegFailureCode -Stage 'encode-cpu' -ErrorText 'x265 [error]: failed to write frame') -ne 'ENCODE_CPU_X265_INTERNAL') { throw 'x265 internal error did not map to ENCODE_CPU_X265_INTERNAL (E2)' }
if ((Get-FFmpegFailureCode -Stage 'encode-cpu' -ErrorText 'something went wrong') -ne 'ENCODE_CPU_FFMPEG_FAILED') { throw 'generic CPU encode failure did not map to ENCODE_CPU_FFMPEG_FAILED (E2)' }
# A CPU-stage failure that happens to mention NVENC text (extremely rare)
# still routes to NVENC bucket because that signature is unambiguous.
if ((Get-FFmpegFailureCode -Stage 'encode-cpu' -ErrorText 'Cannot load nvcuda.dll') -ne 'ENCODE_NVENC_FAILED') { throw 'NVENC-signature error must override CPU stage (E2 ordering)' }
if ((Get-MkvmergeFailureCode -ErrorText 'EBML header parsing failed') -ne 'MKVMERGE_INPUT_INVALID') { throw 'mkvmerge input-invalid code mapping failed' }
if ((Get-ErrorTextSummary -ErrorText "frame=1`nout_time_ms=1000`nError while decoding stream #0:0") -ne 'Error while decoding stream #0:0') { throw 'error summary did not filter progress noise' }
if ((Get-MediaFailureCode -Stage 'encode-verify' -Reason 'ENCODE duration mismatch') -ne 'ENCODE_DURATION_MISMATCH') { throw 'encode verify code mapping failed' }
if ((Get-MediaFailureCode -Stage 'retry-limit' -Reason 'same failing source' -Classification 'operator_required') -ne 'OPERATOR_REQUIRED') { throw 'operator_required code mapping failed' }
`$standard = New-StandardFailureRecord -SourcePath 'source.mkv' -Stage 'encode' -Reason 'No NVENC capable devices found' -Tool 'ffmpeg' -ExitCode 1 -ReproPath 'repro.cmd' -JobId 'job-1' -CorrelationId 'run-1'
if (`$standard.schema_version -ne 'failure_record.v1') { throw 'standard failure schema version missing' }
if (`$standard.Category -ne 'encode' -or `$standard.category -ne 'encode') { throw ('standard failure category wrong: ' + `$standard.Category) }
if (`$standard.Operation -ne 'encode' -or `$standard.operation -ne 'encode') { throw 'standard failure operation missing' }
if (`$standard.SourcePath -ne 'source.mkv' -or `$standard.source_path -ne 'source.mkv') { throw 'standard failure source path missing' }
if (`$standard.JobId -ne 'job-1' -or `$standard.CorrelationId -ne 'run-1') { throw 'standard failure job/correlation IDs missing' }
if (`$standard.Tool -ne 'ffmpeg' -or [int]`$standard.ExitCode -ne 1) { throw 'standard failure tool/exit code missing' }
if (-not [bool]`$standard.Retryable) { throw 'transient standard failure should be retryable' }
if (`$standard.ReproductionPath -ne 'repro.cmd' -or `$standard.reproduction_path -ne 'repro.cmd') { throw 'standard failure reproduction path missing' }
`$standardJson = `$standard | ConvertTo-Json -Compress
if (`$standardJson -notmatch '"category":"encode"' -or `$standardJson -notmatch '"operation":"encode"' -or `$standardJson -notmatch '"stage":"encode"' -or `$standardJson -notmatch '"retryable":true') { throw ('standard failure JSON does not expose canonical schema fields: ' + `$standardJson) }
if (`$standardJson -cmatch '"Category"\s*:|\"Operation\"\s*:|\"Stage\"\s*:|\"Retryable\"\s*:') { throw ('standard failure JSON should not serialize PascalCase duplicates for canonical schema fields: ' + `$standardJson) }
Add-RoundFailureRecord -SourcePath 'source.mkv' -Stage 'scratch-integrity' -Reason 'Source integrity failed: EBML header parsing failed' -Classification 'permanent'
if (`$script:RoundFailureRecords[0].ErrorCode -ne 'SOURCE_MEDIA_CONTAINER_INVALID') { throw ('round failure missing source media code: ' + `$script:RoundFailureRecords[0].ErrorCode) }
if (`$script:RoundFailureRecords[0].schema_version -ne 'failure_record.v1' -or `$script:RoundFailureRecords[0].category -ne 'validation') { throw 'round failure did not use standard record schema/category' }
`$roundRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-round-failures-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$roundRoot -Force | Out-Null
try {
    `$script:LocalFailureReports = `$roundRoot
    `$summary = Write-RoundFailureSummary
    if (-not `$summary -or -not (Test-Path -LiteralPath `$summary.JsonPath)) { throw 'round failure summary JSON was not written' }
    `$roundTrip = Get-Content -LiteralPath `$summary.JsonPath -Raw | ConvertFrom-Json
    if (@(`$roundTrip).Count -lt 1 -or `$roundTrip[0].schema_version -ne 'failure_record.v1') { throw 'round failure summary JSON did not round-trip' }
    if ((Get-ChildItem -LiteralPath `$roundRoot -Filter '*.tmp' -Force -ErrorAction SilentlyContinue).Count -ne 0) { throw 'round failure atomic JSON temp file was not cleaned up' }
} finally {
    Remove-Item -LiteralPath `$roundRoot -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $failureCodeCheck

$failureRetryFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Normalize-FailureCode',
    'Get-MediaFailureCode',
    'Get-FailureCategory',
    'New-StandardFailureRecord',
    'Add-RoundFailureRecord',
    'Get-SourceIdentityKey',
    'Get-SourceSampleHash',
    'Get-SourceIdentityKeyV2',
    'Get-SourceFailureMarkerPath',
    'Get-SourceFailureMarkerPathV2',
    'Test-FailureMarkerMatchesCurrentSource',
    'Invalidate-FailureMarkerIndex',
    'Get-FailureMarkerIndex',
    'Get-SourceFailureState',
    'Write-FailureJsonAtomic',
    'Write-SourceFailureState',
    'Register-SourceFailure'
)) -join [Environment]::NewLine
$failureRetryCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function Get-FailureSuggestedAction { param([string]`$Stage, [string]`$Reason) return 'action' }
function Get-FFprobeFailureCode { param([string]`$ErrorText) return 'MEDIA_PROBE_FAILED' }
function Get-FFmpegFailureCode { param([string]`$Stage, [string]`$ErrorText) return 'FFMPEG_FAILED' }
function Get-MkvmergeFailureCode { param([string]`$ErrorText) return 'MKVMERGE_FAILED' }
function Get-MediaDuration { param([string]`$FilePath) return 10.0 }
function Get-SourceVideoCodec { param([string]`$FilePath) return 'h264' }
`$script:TransientFailureRetryLimit = 2
`$script:RoundFailureRecords = [System.Collections.Generic.List[psobject]]::new()
$failureRetryFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-failure-retry-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$script:LocalFailureMarkers = Join-Path `$root 'markers'
    `$script:LocalFailureArtifacts = Join-Path `$root 'artifacts'
    `$sourcePath = Join-Path `$root 'source.mkv'
    Set-Content -LiteralPath `$sourcePath -Value 'source-bytes' -Encoding UTF8
    `$source = Get-Item -LiteralPath `$sourcePath

    Register-SourceFailure -SourceFile `$source -Classification 'transient' -Reason 'same failing source' -Stage 'encode' -ErrorCode 'ENCODE_TEST_FAILURE' | Out-Null
    `$markerPath = Get-SourceFailureMarkerPath `$source
    `$first = Get-Content -LiteralPath `$markerPath -Raw | ConvertFrom-Json
    if (`$first.classification -ne 'transient') { throw ('first failure should remain transient: ' + `$first.classification) }
    if ([int]`$first.retry_count -ne 1 -or [int]`$first.retry_limit -ne 2) { throw 'first failure retry count is wrong' }

    Register-SourceFailure -SourceFile `$source -Classification 'transient' -Reason 'same failing source' -Stage 'encode' -ErrorCode 'ENCODE_TEST_FAILURE' | Out-Null
    `$second = Get-Content -LiteralPath `$markerPath -Raw | ConvertFrom-Json
    if (`$second.classification -ne 'operator_required') { throw ('second failure should escalate: ' + `$second.classification) }
    if ([int]`$second.retry_count -ne 2 -or [int]`$second.retry_limit -ne 2) { throw 'escalated retry count is wrong' }
    if (-not [bool]`$second.escalated) { throw 'escalated marker did not set escalated=true' }
    if (`$second.suggested_action -notmatch 'Retry limit 2 reached') { throw 'escalated marker missing operator action text' }
    `$last = `$script:RoundFailureRecords[`$script:RoundFailureRecords.Count - 1]
    if (`$last.Classification -ne 'operator_required' -or -not `$last.Escalated) { throw 'round failure did not record escalation' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $failureRetryCheck

$failureReportingFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-SubtitleFailureProperty',
    'Get-SubtitleFailureText',
    'Get-SubtitleFailureStreamIndex',
    'Get-SubtitleFailureStreamText',
    'Register-Tx3gSubtitleFailure',
    'Register-SubtitleExtractionFailure'
)) -join [Environment]::NewLine
$failureReportingCheck = @"
`$ErrorActionPreference = 'Stop'
`$script:RegisteredFailures = @()
function Register-SourceFailure {
    param(
        `$SourceFile,
        [string]`$ScratchPath,
        [string]`$Classification,
        [string]`$Reason,
        [string]`$Stage,
        [string]`$ErrorCode,
        [string]`$SuggestedAction,
        [string]`$SuggestedRename,
        [string]`$ReproPath
    )
    `$script:RegisteredFailures += ,([pscustomobject]@{
        SourceFile = `$SourceFile
        ScratchPath = `$ScratchPath
        Classification = `$Classification
        Reason = `$Reason
        Stage = `$Stage
        ErrorCode = `$ErrorCode
        SuggestedAction = `$SuggestedAction
        ReproPath = `$ReproPath
    })
    return `$null
}
$failureReportingFunctions
`$source = [pscustomobject]@{ FullName = 'C:\Media\source.mkv'; Length = 123 }

Register-Tx3gSubtitleFailure -SourceFile `$source -Failures @() -Stage 'subtitle-tx3g-extract'
if (`$script:RegisteredFailures[-1].ErrorCode -ne 'SUBTITLE_TX3G_UNKNOWN_FAILURE') { throw 'empty tx3g failure list did not produce fallback code' }

Register-Tx3gSubtitleFailure -SourceFile `$source -Failures @([pscustomobject]@{ ErrorCode = 'SUBTITLE_TX3G_EXTRACT_FAILED'; StreamIndex = 'not-an-int'; ReproPath = 'repro-tx3g.cmd' }) -Stage 'subtitle-tx3g-extract'
if (`$script:RegisteredFailures[-1].Reason -notmatch 'a tx3g subtitle stream' -or `$script:RegisteredFailures[-1].Reason -notmatch 'failure record was malformed') { throw 'malformed tx3g failure did not use safe fallback reason/stream text' }
if (`$script:RegisteredFailures[-1].ReproPath -ne 'repro-tx3g.cmd') { throw 'tx3g malformed failure lost repro path' }

Register-SubtitleExtractionFailure -SourceFile `$source -Failures @(@{ ErrorCode = 'SUBTITLE_ASS_CONVERT_FAILED'; StreamIndex = 'bad-index' }) -Stage 'subtitle-extract'
if (`$script:RegisteredFailures[-1].ErrorCode -ne 'SUBTITLE_ASS_CONVERT_FAILED') { throw 'malformed ASS failure did not keep error code' }
if (`$script:RegisteredFailures[-1].Reason -notmatch 'an ASS subtitle stream' -or `$script:RegisteredFailures[-1].Reason -notmatch 'failure record was malformed') { throw 'malformed ASS failure did not use safe fallback text' }

Register-SubtitleExtractionFailure -SourceFile `$source -Failures @(@{ ErrorCode = 'SUBTITLE_BDPGS_OCR_FAILED'; StreamIndex = '7'; Reason = 'ocr failed'; ReproPath = 'repro-pgs.cmd' }) -Stage 'subtitle-extract'
if (`$script:RegisteredFailures[-1].Reason -notmatch 'stream 7' -or `$script:RegisteredFailures[-1].ReproPath -ne 'repro-pgs.cmd') { throw 'BDPGS failure did not preserve stream/repro metadata' }

Register-SubtitleExtractionFailure -SourceFile `$source -Failures @('malformed-string-failure') -Stage 'subtitle-extract'
if (`$script:RegisteredFailures[-1].ErrorCode -ne 'SUBTITLE_UNKNOWN_FAILURE') { throw 'unknown malformed failure did not use fallback subtitle error code' }
if (`$script:RegisteredFailures[-1].Reason -notmatch 'failure record was malformed') { throw 'unknown malformed failure did not use fallback reason' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $failureReportingCheck

$pendingFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'New-PublishTransactionId',
    'Get-FileLengthOrNull',
    'Get-PendingObjectProperty',
    'Get-PendingSidecarEntries',
    'Test-SrtFileUsable',
    'New-SrtAtomicTempPath',
    'Complete-AtomicSrtWrite',
    'Copy-SrtAtomic',
    'ConvertTo-PendingManifestMap',
    'Read-PendingManifestFile',
    'Test-PendingManifestRoundTripValid',
    'Write-PendingManifestFile',
    'New-PendingParkSidecarEntries',
    'New-PendingParkManifest',
    'Invoke-PendingParkTransaction',
    'Invoke-ParkPendingPush'
)) -join [Environment]::NewLine
$pendingCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function Refresh-PendingPublishIndex { return @{} }
`$script:PipelineVersion = '1.0'
`$script:SourceIdentityV2Algorithm = 'identity-v2-test'
$pendingFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-pending-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$legacyManifest = [pscustomobject]@{ local_file = 'old.mkv'; server_out = 'server.mkv' }
    if (@(Get-PendingSidecarEntries -Manifest `$legacyManifest).Count -ne 0) { throw 'legacy pending manifest without sidecar_files should have zero sidecar entries' }

    `$script:LocalPendingPush = Join-Path `$root 'pending'
    `$local = Join-Path `$root 'out.mkv'
    `$sidecar = Join-Path `$root 'out.eng.tx3g.srt'
    `$sidecarDest = Join-Path `$root 'server.eng.tx3g.srt'
    Set-Content -LiteralPath `$local -Value 'verified-output' -Encoding UTF8
    [System.IO.File]::WriteAllText(`$sidecar, "1`r`n00:00:01,000 --> 00:00:02,000`r`nhello`r`n", [System.Text.UTF8Encoding]::new(`$false))
    `$tx3gRecord = [pscustomobject]@{ path = `$sidecarDest; status = 'pending'; cue_count = 1; source_stream_index = 2 }
    `$tx3gSidecar = [pscustomobject]@{ Kind = 'tx3g_srt'; LocalPath = `$sidecar; DestinationPath = `$sidecarDest; Record = `$tx3gRecord; PreserveExisting = `$true }
    `$folderPolicyMetadata = [ordered]@{ applied = `$true; schema_version = 'folder_policy.v1'; path = 'C:\Media\Show\mediapipeline.folder.json'; folder = 'C:\Media\Show'; keys = @('AudioTranscodeCodec'); overrides = [ordered]@{ audio_transcode_codec = 'aac' } }
    `$routePlanMetadata = [ordered]@{ route = 'encode'; route_reason_code = 'bitrate_over_threshold'; estimated_bitrate_mbps = 42.5; decision_trace = @([ordered]@{ code = 'bitrate_over_threshold'; message = 'test trace' }); encode_attempts = @([ordered]@{ attempt = 'primary'; success = `$true }) }
    if (-not (Invoke-ParkPendingPush -LocalOut `$local -ServerOut (Join-Path `$root 'server.mkv') -Route 'encode' -SourceIdentity 'sid' -SourceIdentityV2 'sid2' -SourcePath 'source.mkv' -SourceSize 15 -PublishTransactionId 'txn' -PublishMode 'retry' -SidecarFiles @(`$tx3gSidecar) -Tx3gSrtTracks @(`$tx3gRecord) -FolderPolicyMetadata `$folderPolicyMetadata -RoutePlanMetadata `$routePlanMetadata)) { throw 'park should succeed' }
    if (Test-Path -LiteralPath `$local) { throw 'successful park should move local output' }
    if (-not (Test-Path -LiteralPath `$sidecar)) { throw 'successful park should preserve original tx3g sidecar for caller cleanup' }
    `$manifest = Get-ChildItem -LiteralPath `$script:LocalPendingPush -Filter '*.manifest.json' -File | Select-Object -First 1
    if (-not `$manifest) { throw 'manifest missing after park' }
    `$payload = Get-Content -LiteralPath `$manifest.FullName -Raw | ConvertFrom-Json
    if (-not (Test-Path -LiteralPath ([string]`$payload.local_file))) { throw 'parked local file missing' }
    if (@(`$payload.sidecar_files).Count -ne 1) { throw 'parked tx3g sidecar manifest entry missing' }
    if (-not (Test-Path -LiteralPath ([string]`$payload.sidecar_files[0].local_file))) { throw 'parked tx3g sidecar file missing' }
    if (@(`$payload.tx3g_srt_tracks).Count -ne 1) { throw 'tx3g sidecar metadata missing from pending manifest' }
    if (-not [bool]`$payload.folder_policy.applied -or [string]`$payload.folder_policy.overrides.audio_transcode_codec -ne 'aac') { throw 'folder policy metadata missing from pending manifest' }
    if ([string]`$payload.route_plan.route_reason_code -ne 'bitrate_over_threshold' -or @(`$payload.route_plan.decision_trace).Count -ne 1) { throw 'route plan metadata missing from pending manifest' }
    if ([string]`$payload.schema_version -ne 'pending_push_manifest.v1') { throw 'pending manifest schema version missing' }
    `$payloadValidation = Test-PendingManifestRoundTripValid -RoundTrip `$payload
    if (-not `$payloadValidation.Ok) { throw ('parked current-schema manifest failed validation: ' + `$payloadValidation.Reason) }

    `$badManifestPath = Join-Path `$root 'bad-current.manifest.json'
    `$badCurrent = [ordered]@{
        schema_version = 'pending_push_manifest.v1'
        pipeline_version = '1.0'
        publish_transaction_id = 'txn-bad'
        manifest_state = 'parked'
        route = 'encode'
        local_file = Join-Path `$root 'bad.mkv'
        server_out = Join-Path `$root 'bad-server.mkv'
        source_identity_v2 = ''
        source_identity_v2_algorithm = 'identity-v2-test'
        source_path = 'source-bad.mkv'
        output_size = 1
        sidecar_files = @()
        tx3g_srt_tracks = @()
        tx3g_srt_failures = @()
        bdpgs_srt_failures = @()
        tx3g_embedded_srt_tracks = @()
        bdpgs_embedded_srt_tracks = @()
    }
    try {
        Write-PendingManifestFile -Path `$badManifestPath -Manifest `$badCurrent | Out-Null
        throw 'current-schema pending manifest without source_identity_v2 was accepted'
    } catch {
        if (`$_ -notmatch 'source_identity_v2 missing') { throw }
    }
    if (Test-Path -LiteralPath `$badManifestPath -ErrorAction SilentlyContinue) { throw 'invalid current-schema manifest was written' }

    `$blockedPending = Join-Path `$root 'pending-is-file'
    Set-Content -LiteralPath `$blockedPending -Value 'not a directory' -Encoding UTF8
    `$script:LocalPendingPush = `$blockedPending
    `$local2 = Join-Path `$root 'out2.mkv'
    Set-Content -LiteralPath `$local2 -Value 'verified-output-2' -Encoding UTF8
    if (Invoke-ParkPendingPush -LocalOut `$local2 -ServerOut (Join-Path `$root 'server2.mkv') -Route 'encode' -SourceIdentity 'sid' -SourceIdentityV2 'sid2' -SourcePath 'source.mkv' -SourceSize 15 -PublishTransactionId 'txn2' -PublishMode 'retry') { throw 'park should fail when manifest cannot be written' }
    if (-not (Test-Path -LiteralPath `$local2)) { throw 'local output moved even though manifest write failed' }

    `$script:LocalPendingPush = Join-Path `$root 'pending-partial-sidecar'
    `$local3 = Join-Path `$root 'out3.mkv'
    `$validSidecar = Join-Path `$root 'valid-sidecar.srt'
    `$invalidSidecar = Join-Path `$root 'invalid-sidecar.srt'
    Set-Content -LiteralPath `$local3 -Value 'verified-output-3' -Encoding UTF8
    [System.IO.File]::WriteAllText(`$validSidecar, "1`r`n00:00:01,000 --> 00:00:02,000`r`nhello`r`n", [System.Text.UTF8Encoding]::new(`$false))
    [System.IO.File]::WriteAllText(`$invalidSidecar, "not an srt", [System.Text.UTF8Encoding]::new(`$false))
    `$validSidecarEntry = [pscustomobject]@{ Kind = 'tx3g_srt'; LocalPath = `$validSidecar; DestinationPath = (Join-Path `$root 'server.valid.srt'); Record = [pscustomobject]@{ path = Join-Path `$root 'server.valid.srt'; status = 'pending'; cue_count = 1; source_stream_index = 3 }; PreserveExisting = `$true }
    `$invalidSidecarEntry = [pscustomobject]@{ Kind = 'tx3g_srt'; LocalPath = `$invalidSidecar; DestinationPath = (Join-Path `$root 'server.invalid.srt'); Record = [pscustomobject]@{ path = Join-Path `$root 'server.invalid.srt'; status = 'pending'; cue_count = 0; source_stream_index = 4 }; PreserveExisting = `$true }
    if (Invoke-ParkPendingPush -LocalOut `$local3 -ServerOut (Join-Path `$root 'server3.mkv') -Route 'encode' -SourceIdentity 'sid3' -SourceIdentityV2 'sid3v2' -SourcePath 'source3.mkv' -SourceSize 16 -PublishTransactionId 'txn3' -PublishMode 'retry' -SidecarFiles @(`$validSidecarEntry, `$invalidSidecarEntry)) { throw 'park should fail when one sidecar cannot be validated/copied' }
    if (-not (Test-Path -LiteralPath `$local3)) { throw 'partial sidecar park moved media output despite failure' }
    if (-not (Test-Path -LiteralPath `$validSidecar) -or -not (Test-Path -LiteralPath `$invalidSidecar)) { throw 'partial sidecar park removed original temp sidecars' }
    if ((Test-Path -LiteralPath `$script:LocalPendingPush -ErrorAction SilentlyContinue) -and @(Get-ChildItem -LiteralPath `$script:LocalPendingPush -File -ErrorAction SilentlyContinue).Count -ne 0) { throw 'partial sidecar park left parked sidecar or manifest artifacts behind' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $pendingCheck

$pendingDrainFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'New-PublishTransactionId',
    'Compare-PipelineVersion',
    'Get-FileLengthOrNull',
    'Get-PendingObjectProperty',
    'Get-PendingSidecarEntries',
    'Copy-PendingTx3gRecordWithStatus',
    'Normalize-FailureCode',
    'Get-FailureCategory',
    'New-StandardFailureRecord',
    'New-PendingTx3gPublishFailure',
    'New-PendingSidecarBackupPath',
    'Undo-PendingPublishedSidecarFiles',
    'Complete-PendingPublishedSidecarFiles',
    'Test-SrtFileUsable',
    'New-SrtAtomicTempPath',
    'Complete-AtomicSrtWrite',
    'Copy-SrtAtomic',
    'ConvertTo-PendingManifestMap',
    'Read-PendingManifestFile',
    'Test-PendingManifestRoundTripValid',
    'Write-PendingManifestFile',
    'Publish-PendingSidecarFiles',
    'Update-PendingManifestTx3gFailures',
    'Update-PendingManifestRetryState',
    'Test-PendingPublishedServerCopy',
    'New-PendingPublishIndex',
    'Add-PendingPublishHealthRow',
    'Repair-PendingSidecarArtifacts',
    'Repair-PendingManifestState',
    'Refresh-PendingPublishIndex',
    'Get-PendingPublishHealthReport',
    'Add-RoundFailureRecord',
    'Get-PublishCopyFailureReason',
    'New-PublishPartialMediaPath',
    'Remove-PublishPartialMedia',
    'Backup-PublishSidecarForReveal',
    'Remove-PublishSidecarBackup',
    'Restore-PublishSidecarAfterRevealFailure',
    'Complete-PublishMediaReveal',
    'Get-PendingDrainSummaryPath',
    'Write-PendingDrainSummary',
    'Add-PendingDrainSummaryCount',
    'New-PendingDrainSummaryItem',
    'Complete-PendingDrainSummary',
    'New-PendingDrainSidecarExtra',
    'Remove-PendingDrainLocalArtifacts',
    'Invoke-PendingDrainTransaction',
    'Invoke-RetryPendingPushes'
)) -join [Environment]::NewLine
$pendingDrainCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
function DebugLog { param([string]`$Message) }
function Get-SidecarPath { param([string]`$OutputPath) return "`$OutputPath.mediapipeline.json" }
function Write-OutputSummary { param([string]`$FilePath, [string]`$Route) }
function Write-PipelineEvent { param([string]`$EventType, [string]`$Stage = '', [string]`$SourcePath = '', [string]`$Route = '', [string]`$Status = '', `$Data = `$null) return `$true }
function Get-FailureSuggestedAction { param([string]`$Stage, [string]`$Reason) return 'action' }
function Get-MediaFailureCode { param([string]`$Stage, [string]`$Reason, [string]`$Classification = 'transient') return 'TRANSIENT_FAILURE' }
function Set-ProgressStage { param([string]`$Stage, [string]`$Status, [string]`$PushState, `$Percent, [switch]`$SaveNow, [string]`$Route, [string]`$SidecarState) }
function Set-ProgressItemContext { param([string]`$DisplayName, [string]`$FilePath, [string]`$MediaType, [string]`$LibraryId, [string]`$LibraryName, [string]`$LibraryDesignation, [string]`$LibrarySourceRoot, [string]`$LibraryOutputRoot, [string]`$QueuePhase, [int]`$QueueIndex, [int]`$QueueTotal) }
function Reset-ProgressItemContext {}
`$script:WrittenSidecars = @()
`$script:CompletedManifestAdds = @()
function Write-Sidecar {
    param([string]`$OutputPath, [string]`$Route, `$Extra, [switch]`$SkipCompletedManifest)
    `$script:WrittenSidecars += ,([pscustomobject]@{ OutputPath = `$OutputPath; Route = `$Route; Extra = `$Extra; SkipCompletedManifest = [bool]`$SkipCompletedManifest })
    `$sidecarPath = Get-SidecarPath `$OutputPath
    `$sidecarDir = Split-Path `$sidecarPath -Parent
    if (`$sidecarDir -and -not (Test-Path -LiteralPath `$sidecarDir)) { [System.IO.Directory]::CreateDirectory(`$sidecarDir) | Out-Null }
    [System.IO.File]::WriteAllText(`$sidecarPath, (`$Extra | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new(`$false))
    return `$true
}
function Add-CompletedJobsManifestEntryFromSidecar {
    param([string]`$OutputPath)
    `$script:CompletedManifestAdds += ,`$OutputPath
    return `$true
}
`$script:CopyMode = 'success'
function Copy-FileRobocopy {
    param([string]`$Source, [string]`$Destination)
    if (`$script:CopyMode -eq 'fail') { return `$false }
    `$dir = Split-Path `$Destination -Parent
    if (`$dir -and -not (Test-Path -LiteralPath `$dir)) { [System.IO.Directory]::CreateDirectory(`$dir) | Out-Null }
    Copy-Item -LiteralPath `$Source -Destination `$Destination -Force
    return `$true
}
`$script:RevealMode = 'success'
function Complete-PublishMediaReveal {
    param(
        [Parameter(Mandatory)] [string] `$PartialPath,
        [Parameter(Mandatory)] [string] `$FinalPath,
        [Parameter(Mandatory)] [string] `$PublishTransactionId,
        [string] `$Context = ''
    )
    if (`$script:RevealMode -eq 'fail') { return `$false }
    if (-not (Test-Path -LiteralPath `$PartialPath -PathType Leaf -ErrorAction SilentlyContinue)) { return `$false }
    `$dir = Split-Path `$FinalPath -Parent
    if (`$dir -and -not (Test-Path -LiteralPath `$dir)) { [System.IO.Directory]::CreateDirectory(`$dir) | Out-Null }
    [System.IO.File]::Move(`$PartialPath, `$FinalPath, `$true)
    return `$true
}
$pendingDrainFunctions
function Complete-PublishMediaReveal {
    param(
        [Parameter(Mandatory)] [string] `$PartialPath,
        [Parameter(Mandatory)] [string] `$FinalPath,
        [Parameter(Mandatory)] [string] `$PublishTransactionId,
        [string] `$Context = ''
    )
    if (`$script:RevealMode -eq 'fail') { return `$false }
    if (-not (Test-Path -LiteralPath `$PartialPath -PathType Leaf -ErrorAction SilentlyContinue)) { return `$false }
    `$dir = Split-Path `$FinalPath -Parent
    if (`$dir -and -not (Test-Path -LiteralPath `$dir)) { [System.IO.Directory]::CreateDirectory(`$dir) | Out-Null }
    [System.IO.File]::Move(`$PartialPath, `$FinalPath, `$true)
    return `$true
}

`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-pending-drain-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$script:PipelineVersion = '1.0'
    `$script:MinPipelineVersion = '1.0'
    `$script:SourceIdentityV2Algorithm = 'test'
    `$script:DeferredPublish = `$false
    `$script:StopRequested = `$false
    `$script:RoundFailureRecords = [System.Collections.Generic.List[psobject]]::new()
    `$StopFlag = Join-Path `$root 'stop.flag'
    `$script:LocalPendingPush = Join-Path `$root 'pending'
    New-Item -ItemType Directory -Path `$script:LocalPendingPush -Force | Out-Null

    `$legacyLocal = Join-Path `$script:LocalPendingPush 'legacy.mkv'
    `$legacyServer = Join-Path `$root 'server\legacy.mkv'
    Set-Content -LiteralPath `$legacyLocal -Value 'legacy-output' -Encoding UTF8
    `$legacyManifestPath = "`$legacyLocal.manifest.json"
    [ordered]@{
        local_file = `$legacyLocal
        server_out = `$legacyServer
        route = 'remux'
        source_path = 'legacy-source.mkv'
        output_size = (Get-Item -LiteralPath `$legacyLocal).Length
        publish_transaction_id = 'legacy-txn'
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath `$legacyManifestPath -Encoding UTF8
    `$legacyRecovered = Invoke-RetryPendingPushes -Force
    if ([int]`$legacyRecovered -ne 1) { throw ('legacy manifest without sidecar_files did not drain: ' + `$legacyRecovered) }
    if (-not (Test-Path -LiteralPath `$legacyServer)) { throw 'legacy drain did not publish server output' }
    if (Test-Path -LiteralPath `$legacyLocal) { throw 'legacy drain left parked local file' }
    if (Test-Path -LiteralPath `$legacyManifestPath) { throw 'legacy drain left manifest' }

    `$script:WrittenSidecars = @()
    `$sidecarLocal = Join-Path `$script:LocalPendingPush 'episode.eng.tx3g.srt'
    `$mediaLocal = Join-Path `$script:LocalPendingPush 'episode.mkv'
    `$mediaServer = Join-Path `$root 'server\episode.mkv'
    `$sidecarServer = Join-Path `$root 'server\episode.eng.tx3g.srt'
    Set-Content -LiteralPath `$mediaLocal -Value 'episode-output' -Encoding UTF8
    [System.IO.File]::WriteAllText(`$sidecarLocal, "1`r`n00:00:01,000 --> 00:00:02,000`r`nhello`r`n", [System.Text.UTF8Encoding]::new(`$false))
    `$trackRecord = [pscustomobject]@{ path = `$sidecarServer; status = 'pending'; cue_count = 1; source_stream_index = 2; language = 'eng'; title = 'English' }
    `$sidecarManifestPath = "`$mediaLocal.manifest.json"
    [ordered]@{
        local_file = `$mediaLocal
        server_out = `$mediaServer
        route = 'encode'
        source_path = 'episode-source.mkv'
        output_size = (Get-Item -LiteralPath `$mediaLocal).Length
        publish_transaction_id = 'sidecar-txn'
        sidecar_files = @([ordered]@{ kind = 'tx3g_srt'; local_file = `$sidecarLocal; server_out = `$sidecarServer; preserve_existing = `$true; tx3g_record = `$trackRecord })
        tx3g_srt_tracks = @(`$trackRecord)
        folder_policy = [ordered]@{ applied = `$true; schema_version = 'folder_policy.v1'; path = 'C:\Media\Show\mediapipeline.folder.json'; folder = 'C:\Media\Show'; keys = @('ConvertTx3gToSrt'); overrides = [ordered]@{ convert_tx3g_to_srt = `$false } }
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath `$sidecarManifestPath -Encoding UTF8
    `$sidecarRecovered = Invoke-RetryPendingPushes -Force
    if ([int]`$sidecarRecovered -ne 1) { throw ('sidecar manifest did not drain: ' + `$sidecarRecovered) }
    if (-not (Test-Path -LiteralPath `$mediaServer) -or -not (Test-Path -LiteralPath `$sidecarServer)) { throw 'sidecar drain did not publish media and SRT' }
    if (Test-Path -LiteralPath `$mediaLocal -ErrorAction SilentlyContinue) { throw 'sidecar drain left parked media' }
    if (Test-Path -LiteralPath `$sidecarLocal -ErrorAction SilentlyContinue) { throw 'sidecar drain left parked SRT' }
    if (@(`$script:WrittenSidecars).Count -lt 1) { throw 'sidecar drain did not write media sidecar metadata' }
    if (-not [bool]`$script:WrittenSidecars[-1].SkipCompletedManifest) { throw 'pending retry sidecar should skip completed manifest until media reveal succeeds' }
    if (@(`$script:CompletedManifestAdds).Count -lt 1 -or [string]`$script:CompletedManifestAdds[-1] -ne `$mediaServer) { throw 'pending retry should append completed manifest only after media reveal succeeds' }
    if (-not (Test-Path -LiteralPath (Get-SidecarPath `$mediaServer) -PathType Leaf -ErrorAction SilentlyContinue)) { throw 'sidecar drain did not leave media sidecar metadata after reveal success' }
    `$lastExtra = `$script:WrittenSidecars[-1].Extra
    if (@(`$lastExtra['tx3g_srt_tracks']).Count -ne 1 -or [string]@(`$lastExtra['tx3g_srt_tracks'])[0].status -ne 'written') { throw 'sidecar drain did not record written tx3g SRT metadata' }
    if (-not [bool]`$lastExtra['folder_policy'].applied -or [string]`$lastExtra['folder_policy'].overrides.convert_tx3g_to_srt -ne 'False') { throw 'sidecar drain did not preserve folder policy metadata' }
    `$sidecarSummary = Get-Content -LiteralPath (Get-PendingDrainSummaryPath) -Raw | ConvertFrom-Json
    if ([int]`$sidecarSummary.succeeded_count -ne 1 -or [int]@(`$sidecarSummary.items)[-1].sidecar_count -ne 1) { throw 'sidecar drain summary did not record successful media-plus-sidecar drain' }

    `$missingSidecarLocal = Join-Path `$script:LocalPendingPush 'missing-sidecar.srt'
    `$missingMediaLocal = Join-Path `$script:LocalPendingPush 'missing-sidecar.mkv'
    `$missingMediaServer = Join-Path `$root 'server\missing-sidecar.mkv'
    `$missingSidecarServer = Join-Path `$root 'server\missing-sidecar.eng.tx3g.srt'
    Set-Content -LiteralPath `$missingMediaLocal -Value 'missing-sidecar-output' -Encoding UTF8
    `$missingRecord = [pscustomobject]@{ path = `$missingSidecarServer; status = 'pending'; cue_count = 1; source_stream_index = 5; language = 'eng' }
    `$missingManifestPath = "`$missingMediaLocal.manifest.json"
    [ordered]@{
        local_file = `$missingMediaLocal
        server_out = `$missingMediaServer
        route = 'encode'
        source_path = 'missing-sidecar-source.mkv'
        output_size = (Get-Item -LiteralPath `$missingMediaLocal).Length
        publish_transaction_id = 'missing-sidecar-txn'
        sidecar_files = @([ordered]@{ kind = 'tx3g_srt'; local_file = `$missingSidecarLocal; server_out = `$missingSidecarServer; preserve_existing = `$true; tx3g_record = `$missingRecord })
        tx3g_srt_tracks = @(`$missingRecord)
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath `$missingManifestPath -Encoding UTF8
    `$missingRecovered = Invoke-RetryPendingPushes -Force
    if ([int]`$missingRecovered -ne 0) { throw 'missing parked sidecar should not count as a recovered pending publish' }
    if (-not (Test-Path -LiteralPath `$missingMediaLocal) -or -not (Test-Path -LiteralPath `$missingManifestPath)) { throw 'missing parked sidecar should leave parked media and manifest for retry' }
    `$missingPayload = Get-Content -LiteralPath `$missingManifestPath -Raw | ConvertFrom-Json
    `$missingFailures = @(`$missingPayload.tx3g_srt_failures | Where-Object { `$null -ne `$_ })
    if (`$missingFailures.Count -lt 1) { throw 'missing parked sidecar failure was not persisted to manifest' }
    `$missingFailureCode = if (`$missingFailures[0].PSObject.Properties['ErrorCode']) { [string]`$missingFailures[0].ErrorCode } else { [string]`$missingFailures[0].error_code }
    if (`$missingFailureCode -ne 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED') { throw ('missing parked sidecar failure code changed: ' + `$missingFailureCode) }
    if (`$script:RoundFailureRecords.Count -lt 1 -or `$script:RoundFailureRecords[-1].category -ne 'publish') { throw 'missing parked sidecar was not classified into round failures' }
    Remove-Item -LiteralPath `$missingMediaLocal -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath `$missingManifestPath -Force -ErrorAction SilentlyContinue

    `$missingPayloadLocal = Join-Path `$script:LocalPendingPush 'missing-payload.mkv'
    `$missingPayloadServer = Join-Path `$root 'server\missing-payload.mkv'
    `$missingPayloadManifest = "`$missingPayloadLocal.manifest.json"
    [ordered]@{
        schema_version = 'pending_push_manifest.v1'
        pipeline_version = '1.0'
        manifest_state = 'parked'
        local_file = `$missingPayloadLocal
        original_local_file = `$missingPayloadLocal
        server_out = `$missingPayloadServer
        route = 'encode'
        source_path = 'missing-payload-source.mkv'
        source_identity_v2 = 'missing-payload-sid2'
        source_identity_v2_algorithm = 'test'
        source_identity = 'missing-payload-sid1'
        output_size = 123
        publish_transaction_id = 'missing-payload-txn'
        sidecar_files = @()
        tx3g_srt_tracks = @()
        tx3g_srt_failures = @()
        bdpgs_srt_failures = @()
        tx3g_embedded_srt_tracks = @()
        bdpgs_embedded_srt_tracks = @()
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath `$missingPayloadManifest -Encoding UTF8
    `$missingPayloadRecovered = Invoke-RetryPendingPushes -Force
    if ([int]`$missingPayloadRecovered -ne 0) { throw 'missing parked media payload should not count as recovered' }
    if (-not (Test-Path -LiteralPath `$missingPayloadManifest)) { throw 'missing parked media payload should preserve its manifest for operator recovery' }
    `$missingPayloadRoundTrip = Get-Content -LiteralPath `$missingPayloadManifest -Raw | ConvertFrom-Json
    if ([string]`$missingPayloadRoundTrip.manifest_state -ne 'missing_payload') { throw ('missing parked media payload should be tagged missing_payload, got: ' + `$missingPayloadRoundTrip.manifest_state) }
    if ([int]`$missingPayloadRoundTrip.retry_count -lt 1 -or [string]`$missingPayloadRoundTrip.last_retry_stage -ne 'retry_pending_push') { throw 'missing parked media payload retry metadata missing' }
    Remove-Item -LiteralPath `$missingPayloadManifest -Force -ErrorAction SilentlyContinue

    `$revealMediaLocal = Join-Path `$script:LocalPendingPush 'reveal-fail.mkv'
    `$revealMediaServer = Join-Path `$root 'server\reveal-fail.mkv'
    `$revealSidecarLocal = Join-Path `$script:LocalPendingPush 'reveal-fail.eng.tx3g.srt'
    `$revealSidecarServer = Join-Path `$root 'server\reveal-fail.eng.tx3g.srt'
    `$revealManifestPath = "`$revealMediaLocal.manifest.json"
    Set-Content -LiteralPath `$revealMediaLocal -Value 'reveal-failure-output' -Encoding UTF8
    [System.IO.File]::WriteAllText(`$revealSidecarLocal, "1`r`n00:00:01,000 --> 00:00:02,000`r`nhello`r`n", [System.Text.UTF8Encoding]::new(`$false))
    `$revealRecord = [pscustomobject]@{ path = `$revealSidecarServer; status = 'pending'; cue_count = 1; source_stream_index = 6; language = 'eng' }
    [ordered]@{
        schema_version = 'pending_push_manifest.v1'
        pipeline_version = '1.0'
        manifest_state = 'parked'
        local_file = `$revealMediaLocal
        original_local_file = `$revealMediaLocal
        server_out = `$revealMediaServer
        route = 'encode'
        source_path = 'reveal-fail-source.mkv'
        source_identity_v2 = 'reveal-fail-sid2'
        source_identity_v2_algorithm = 'test'
        source_identity = 'reveal-fail-sid1'
        output_size = (Get-Item -LiteralPath `$revealMediaLocal).Length
        publish_transaction_id = 'reveal-fail-txn'
        sidecar_files = @([ordered]@{ kind = 'tx3g_srt'; local_file = `$revealSidecarLocal; server_out = `$revealSidecarServer; preserve_existing = `$true; tx3g_record = `$revealRecord })
        tx3g_srt_tracks = @(`$revealRecord)
        tx3g_srt_failures = @()
        bdpgs_srt_failures = @()
        tx3g_embedded_srt_tracks = @()
        bdpgs_embedded_srt_tracks = @()
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath `$revealManifestPath -Encoding UTF8
    `$script:RevealMode = 'fail'
    `$revealRecovered = Invoke-RetryPendingPushes -Force
    if ([int]`$revealRecovered -ne 0) { throw 'reveal failure should not count as recovered' }
    if (-not (Test-Path -LiteralPath `$revealMediaLocal) -or -not (Test-Path -LiteralPath `$revealSidecarLocal) -or -not (Test-Path -LiteralPath `$revealManifestPath)) { throw 'reveal failure should leave parked media, sidecar, and manifest' }
    `$revealPartial = New-PublishPartialMediaPath -ServerOut `$revealMediaServer -PublishTransactionId 'reveal-fail-txn'
    if (Test-Path -LiteralPath `$revealMediaServer -ErrorAction SilentlyContinue) { throw 'reveal failure unexpectedly committed final media' }
    if (Test-Path -LiteralPath `$revealPartial -ErrorAction SilentlyContinue) { throw 'reveal failure left partial media behind' }
    if (Test-Path -LiteralPath `$revealSidecarServer -ErrorAction SilentlyContinue) { throw 'reveal failure left published tx3g sidecar without committed media' }
    if (Test-Path -LiteralPath (Get-SidecarPath `$revealMediaServer) -ErrorAction SilentlyContinue) { throw 'reveal failure left media sidecar without committed media' }
    `$revealManifest = Get-Content -LiteralPath `$revealManifestPath -Raw | ConvertFrom-Json
    if ([string]`$revealManifest.manifest_state -ne 'retry_reveal_failed') { throw ('reveal failure should persist retry_reveal_failed, got: ' + `$revealManifest.manifest_state) }
    `$revealSummary = Get-Content -LiteralPath (Get-PendingDrainSummaryPath) -Raw | ConvertFrom-Json
    if ([string]@(`$revealSummary.items)[-1].status -ne 'reveal_failed' -or [int]`$revealSummary.error_count -lt 1) { throw 'reveal failure summary did not record retryable drain failure' }
    `$script:RevealMode = 'success'
    `$revealRetryRecovered = Invoke-RetryPendingPushes -Force
    if ([int]`$revealRetryRecovered -ne 1) { throw 'reveal failure retry did not recover after reveal path became available' }
    if (-not (Test-Path -LiteralPath `$revealMediaServer) -or -not (Test-Path -LiteralPath `$revealSidecarServer)) { throw 'reveal failure retry did not publish media plus sidecar' }
    if (Test-Path -LiteralPath `$revealMediaLocal -ErrorAction SilentlyContinue) { throw 'reveal failure retry left parked media' }
    if (Test-Path -LiteralPath `$revealSidecarLocal -ErrorAction SilentlyContinue) { throw 'reveal failure retry left parked sidecar' }
    if (Test-Path -LiteralPath `$revealManifestPath -ErrorAction SilentlyContinue) { throw 'reveal failure retry left manifest' }

    `$retryLocal = Join-Path `$script:LocalPendingPush 'retry.mkv'
    `$retryServer = Join-Path `$root 'server\retry.mkv'
    `$retryManifestPath = "`$retryLocal.manifest.json"
    Set-Content -LiteralPath `$retryLocal -Value 'retry-output' -Encoding UTF8
    [ordered]@{
        local_file = `$retryLocal
        server_out = `$retryServer
        route = 'encode'
        source_path = 'retry-source.mkv'
        output_size = (Get-Item -LiteralPath `$retryLocal).Length
        publish_transaction_id = 'retry-txn'
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath `$retryManifestPath -Encoding UTF8
    `$script:CopyMode = 'fail'
    `$failedRetry = Invoke-RetryPendingPushes -Force
    if ([int]`$failedRetry -ne 0) { throw 'network copy failure should not count as recovered' }
    if (-not (Test-Path -LiteralPath `$retryLocal) -or -not (Test-Path -LiteralPath `$retryManifestPath)) { throw 'network copy failure should leave parked media and manifest' }
    if (Test-Path -LiteralPath `$retryServer -ErrorAction SilentlyContinue) { throw 'network copy failure unexpectedly created server output' }
    `$script:CopyMode = 'success'
    `$successfulRetry = Invoke-RetryPendingPushes -Force
    if ([int]`$successfulRetry -ne 1) { throw ('retry success did not recover failed network copy: ' + `$successfulRetry) }
    if (-not (Test-Path -LiteralPath `$retryServer)) { throw 'retry success did not publish server output' }
    if (Test-Path -LiteralPath `$retryLocal -ErrorAction SilentlyContinue) { throw 'retry success left parked local media' }
    if (Test-Path -LiteralPath `$retryManifestPath -ErrorAction SilentlyContinue) { throw 'retry success left manifest' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $pendingDrainCheck

$pipelineScriptJson = $main | ConvertTo-Json -Compress
$configTemplateJson = $configTemplate | ConvertTo-Json -Compress
$pendingDrainSingleInstanceCheck = @"
`$ErrorActionPreference = 'Stop'
`$scriptPath = '$pipelineScriptJson' | ConvertFrom-Json
`$templatePath = '$configTemplateJson' | ConvertFrom-Json
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-drain-lock-' + [guid]::NewGuid().ToString('N'))
`$local = Join-Path `$root 'LocalBase'
`$configPath = Join-Path `$root 'MediaPipeline_config_test.psd1'
`$mutex = `$null
`$locked = `$false
`$hadOldSuffix = Test-Path Env:\MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
`$oldSuffix = `$env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
try {
    New-Item -ItemType Directory -Path `$local -Force | Out-Null
    `$configText = Get-Content -LiteralPath `$templatePath -Raw
    `$configText = `$configText.Replace("SourceMovies = 'C:\MediaPipeline\Incoming\Movies'", "SourceMovies = '`$(Join-Path `$root 'MissingMovies')'")
    `$configText = `$configText.Replace("SourceTV = 'C:\MediaPipeline\Incoming\TV'", "SourceTV = '`$(Join-Path `$root 'MissingTV')'")
    `$configText = `$configText.Replace("Outsource = 'C:\MediaPipeline\Processed'", "Outsource = '`$(Join-Path `$root 'MissingOutsource')'")
    `$configText = `$configText.Replace("LocalBase = 'C:\MediaPipeline\Scratch'", "LocalBase = '`$local'")
    Set-Content -LiteralPath `$configPath -Value `$configText -Encoding UTF8

    `$suffix = [guid]::NewGuid().ToString('N')
    `$mutex = [System.Threading.Mutex]::new(`$false, "Global\MediaPipelineSingleInstance_`$suffix")
    `$locked = `$mutex.WaitOne(0)
    if (-not `$locked) { throw 'test could not acquire drain mutex' }

    `$env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = `$suffix
    `$outputLines = & (Get-Command pwsh).Source -NoProfile -ExecutionPolicy Bypass -File `$scriptPath -ConfigPath `$configPath -DrainPendingPushes -SleepSeconds 1 2>&1
    `$exit = `$LASTEXITCODE
    `$output = `$outputLines | Out-String
    if (`$exit -ne 73) { throw "drain lock conflict should exit 73, got `$exit. Output: `$output" }
    if (`$output -notmatch 'same single-instance lock' -or `$output -notmatch 'Kill \+ Quit') { throw "drain lock conflict did not explain publish lock recovery. Output: `$output" }
} finally {
    if (`$hadOldSuffix) { `$env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = `$oldSuffix } else { Remove-Item Env:\MEDIA_PIPELINE_TEST_MUTEX_SUFFIX -ErrorAction SilentlyContinue }
    if (`$mutex) {
        if (`$locked) { try { `$mutex.ReleaseMutex() } catch {} }
        try { `$mutex.Dispose() } catch {}
    }
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $pendingDrainSingleInstanceCheck

$pendingMatchFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Test-PendingPublishMatch'
)) -join [Environment]::NewLine
$pendingEmptyIndexCheck = @"
`$ErrorActionPreference = 'Stop'
function Get-SourceIdentityKey { throw 'v1 identity should not be computed for an empty pending index' }
function Get-SourceIdentityKeyV2 { throw 'v2 identity should not be computed for an empty pending index' }
`$script:PendingPublishIndex = @{
    Count = 0
    BySourceIdentity = @{}
    BySourceIdentityV2 = @{}
    ByServerOut = @{}
    HasSourceIdentityV2 = `$true
}
$pendingMatchFunctions
`$result = Test-PendingPublishMatch -SourceFile ([pscustomobject]@{ FullName = 'C:\Media\source.mkv' }) -ServerOut 'C:\Media\server.mkv'
if (`$result) { throw 'empty pending index should not match' }
"@
Invoke-PowerShellBehaviorCheck -ScriptText $pendingEmptyIndexCheck

$pendingRecoveryFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Get-PendingObjectProperty',
    'Get-PendingSidecarEntries',
    'Repair-PendingSidecarArtifacts',
    'ConvertTo-PendingManifestMap',
    'Read-PendingManifestFile',
    'Test-PendingManifestRoundTripValid',
    'Write-PendingManifestFile',
    'New-PendingPublishIndex',
    'Add-PendingPublishHealthRow',
    'Repair-PendingManifestState',
    'Refresh-PendingPublishIndex',
    'Get-PendingPublishHealthReport'
)) -join [Environment]::NewLine
$pendingRecoveryCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
$pendingRecoveryFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-pending-recover-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$LocalPendingPush = Join-Path `$root 'pending'
    New-Item -ItemType Directory -Path `$LocalPendingPush -Force | Out-Null
    `$original = Join-Path `$root 'verified-output.mkv'
    `$parked = Join-Path `$LocalPendingPush 'parked-output.mkv'
    Set-Content -LiteralPath `$original -Value 'verified-output' -Encoding UTF8
    `$manifestPath = "`$parked.manifest.json"
    `$manifest = [ordered]@{
        manifest_state = 'pending_move'
        local_file = `$parked
        original_local_file = `$original
        server_out = Join-Path `$root 'server-output.mkv'
        source_identity = 'sid1'
        source_identity_v2 = 'sid2'
    }
    Write-PendingManifestFile -Path `$manifestPath -Manifest `$manifest | Out-Null
    `$index = Refresh-PendingPublishIndex
    if ([int]`$index.Count -ne 1) { throw ('recovered pending index count wrong: ' + `$index.Count) }
    if (Test-Path -LiteralPath `$original) { throw 'original local output should have been moved during recovery' }
    if (-not (Test-Path -LiteralPath `$parked)) { throw 'parked local output missing after recovery' }
    `$roundTrip = Get-Content -LiteralPath `$manifestPath -Raw | ConvertFrom-Json
    if ([string]`$roundTrip.manifest_state -ne 'parked_recovered') { throw ('manifest state not recovered: ' + `$roundTrip.manifest_state) }

    Remove-Item -LiteralPath `$parked -Force -ErrorAction Stop
    `$missingIndex = Refresh-PendingPublishIndex
    if ([int]`$missingIndex.Count -ne 0) { throw 'missing pending payload should not enter active pending publish match index' }
    if ([int]`$missingIndex.MissingPayloadCount -ne 1) { throw 'missing pending payload was not counted in pending health report' }
    `$healthRows = @(Get-PendingPublishHealthReport)
    if (`$healthRows.Count -ne 1 -or `$healthRows[0].code -ne 'missing_payload' -or `$healthRows[0].local_file -ne `$parked) { throw 'missing pending payload health row was not exposed' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $pendingRecoveryCheck

$pendingValidationFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Compare-PipelineVersion',
    'Get-SidecarPath',
    'Get-FileLengthOrNull',
    'Get-PendingObjectProperty',
    'Get-PendingSidecarEntries',
    'Test-SrtFileUsable',
    'Test-PendingPublishedServerCopy'
)) -join [Environment]::NewLine
$pendingValidationCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
`$script:MinPipelineVersion = '1.0'
$pendingValidationFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-pending-validation-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$local = Join-Path `$root 'parked.mkv'
    `$server = Join-Path `$root 'server.mkv'
    [System.IO.File]::WriteAllBytes(`$local, [byte[]](97, 98, 99))
    New-Item -ItemType File -Path `$server -Force | Out-Null
    `$manifest = [pscustomobject]@{
        output_size = 3
        publish_transaction_id = 'txn-good'
        source_identity_v2 = 'sid2'
        source_identity = 'sid1'
        source_path = 'source.mkv'
        source_size = 123
    }
    if (Test-PendingPublishedServerCopy -Manifest `$manifest -LocalPath `$local -ServerPath `$server) { throw 'server file without sidecar must not validate' }

    [System.IO.File]::WriteAllBytes(`$server, [byte[]](97, 98, 99))
    [ordered]@{
        pipeline_version = '1.0'
        publish_transaction_id = 'txn-good'
        source_identity_v2 = 'sid2'
        source_identity = 'sid1'
        source_path = 'source.mkv'
        source_size = 123
        output_size = 3
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Get-SidecarPath `$server) -Encoding UTF8
    if (-not (Test-PendingPublishedServerCopy -Manifest `$manifest -LocalPath `$local -ServerPath `$server)) { throw 'matching pending server copy should validate' }

    `$mismatch = [pscustomobject]@{
        output_size = 3
        publish_transaction_id = 'txn-other'
        source_identity_v2 = 'sid2'
        source_identity = 'sid1'
        source_path = 'source.mkv'
        source_size = 123
    }
    if (Test-PendingPublishedServerCopy -Manifest `$mismatch -LocalPath `$local -ServerPath `$server) { throw 'transaction mismatch must not validate' }

    `$weakLegacy = [pscustomobject]@{
        output_size = 3
        publish_transaction_id = ''
        source_identity_v2 = ''
        source_identity = ''
        source_path = ''
        source_size = `$null
    }
    if (Test-PendingPublishedServerCopy -Manifest `$weakLegacy -LocalPath `$local -ServerPath `$server) { throw 'weak legacy manifest must not discard parked local output' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $pendingValidationCheck

$pathFunctions = (Get-FunctionText -Path $pipelineFiles -Names @(
    'Test-PathComponentSupport',
    'Test-OutputPathCapability'
)) -join [Environment]::NewLine
$pathCheck = @"
`$ErrorActionPreference = 'Stop'
function Write-Log { param([string]`$Message, [string]`$Level = 'INFO') }
$pathFunctions
`$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-path-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path `$root -Force | Out-Null
try {
    `$ok = Test-OutputPathCapability -Paths @{ LocalOut = (Join-Path `$root 'local\ok.mkv'); ServerOut = (Join-Path `$root 'server\ok.mkv') }
    if (-not `$ok.Ok) { throw ('expected normal path to pass: ' + `$ok.Reason) }
    `$badLeaf = ('a' * 260) + '.mkv'
    `$bad = Test-OutputPathCapability -Paths @{ LocalOut = (Join-Path `$root `$badLeaf); ServerOut = (Join-Path `$root 'server\ok.mkv') }
    if (`$bad.Ok) { throw 'component longer than 255 should fail' }
} finally {
    Remove-Item -LiteralPath `$root -Recurse -Force -ErrorAction SilentlyContinue
}
"@
Invoke-PowerShellBehaviorCheck -ScriptText $pathCheck

$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-regression-" + [guid]::NewGuid().ToString("N"))
$oldPath = $env:PATH
try {
    $libRoot = Join-Path $testRoot "library"
    $reportRoot = Join-Path $testRoot "reports"
    $badBin = Join-Path $testRoot "bad-bin"
    New-Item -ItemType Directory -Path $libRoot, $reportRoot, $badBin -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $badBin "ffprobe.cmd") -Value "@echo bad ffprobe from PATH& exit /b 99" -Encoding ASCII
    $env:PATH = "$badBin;$oldPath"
    $auditOutput = & (Get-Command pwsh).Source -NoProfile -ExecutionPolicy Bypass -File $audit -LibraryRoot $libRoot -ReportRoot $reportRoot 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Audit empty-library check failed with exit ${LASTEXITCODE}: $auditOutput" }
    $bundledFfprobe = [regex]::Escape((Join-Path $root 'Tools\ffmpeg\bin\ffprobe.exe'))
    Assert-True ($auditOutput -match $bundledFfprobe) "Audit should prefer bundled ffprobe even when PATH contains another ffprobe."

    if ($python) {
        $pythonTest = @"
import sys
import tempfile
import logging
import json
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, r"$($projectRoot)\DesktopApp")
from mediapipeline.desktop.services import APP_STATE_NAME, DesktopAppService, _normalize_open_path_text, _strip_windows_extended_path_prefix
from mediapipeline.desktop.models import AuditRecord, CompletedJobRecord, FailureRecord, ResolvedPaths
from mediapipeline.desktop.priority_markers import remove_priority_markers_from_name, starts_with_priority_marker
from mediapipeline.desktop.workers import UiBackgroundWorker

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    assert _strip_windows_extended_path_prefix(r"\\?\E:\Videos\file.mkv") == r"E:\Videos\file.mkv"
    assert _strip_windows_extended_path_prefix(r"\\?\UNC\server\share\file.mkv") == r"\\server\share\file.mkv"
    assert _normalize_open_path_text("file://?/E%3A/Videos/Testing%20Space/file.mkv") == r"E:\Videos\Testing Space\file.mkv"
    assert _normalize_open_path_text(r"file:\?\E%3A\Videos\Testing%20Space\file.mkv") == r"E:\Videos\Testing Space\file.mkv"
    assert _normalize_open_path_text("file:///E:/Videos/Testing%20Space/file.mkv") == r"E:\Videos\Testing Space\file.mkv"
    assert _normalize_open_path_text("file://server/share/Testing%20Space/file.mkv") == r"\\server\share\Testing Space\file.mkv"
    service = DesktopAppService(Path(td))
    try:
        service.open_path(Path(td) / "missing-folder")
        raise AssertionError("open_path should reject missing targets before launching an opener")
    except FileNotFoundError:
        pass
    try:
        service.open_parent(Path(td) / "missing-folder" / "missing-file.mkv")
        raise AssertionError("open_parent should reject missing parent targets before launching an opener")
    except FileNotFoundError:
        pass
    active_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=Path(td) / "active-local",
        state_root=Path(td) / "active-local" / "State",
        active_jobs_path=Path(td) / "active-local" / "State" / "ActiveJobs",
    )
    bundle_root = Path(r"$projectRoot")
    bundle_service = DesktopAppService(bundle_root / "DesktopApp")
    release_dest = Path(td) / "release-dry-run" / "package"
    release_result = bundle_service.build_release_package(
        destination_root=release_dest,
        zip_package=False,
        verify=False,
        include_tests=False,
        include_dev_docs=False,
        include_optional_tools=False,
        include_tool_docs=False,
        keep_personal_config=False,
        force=False,
        dry_run=True,
        timeout_seconds=120,
    )
    assert release_result["success"] is True, "release service dry-run should succeed"
    assert release_result["dry_run"] is True, "release service dry-run should preserve dry_run in result"
    assert "Dry run only" in release_result["stdout"], "release service dry-run should capture stdout"
    assert not release_dest.exists(), "release service dry-run should not create the destination folder"
    assert release_result["manifest_exists"] is False, "release service dry-run should not report a manifest"

    pending_root = Path(td) / "pending-publish"
    pending_root.mkdir()
    parked = pending_root / "movie.mkv"
    sidecar = pending_root / "movie.en.srt"
    orphan = pending_root / "orphan.mkv"
    parked.write_bytes(b"movie")
    sidecar.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    orphan.write_bytes(b"orphan")
    manifest_payload = {
        "parked_at": datetime.now().isoformat(),
        "manifest_state": "parked",
        "local_file": str(parked),
        "server_out": str(Path(td) / "outsource" / "Movies" / "movie.mkv"),
        "route": "encode",
        "source_path": str(Path(td) / "source" / "movie.mkv"),
        "output_size": parked.stat().st_size,
        "publish_mode": "deferred",
        "sidecar_files": [
            {
                "local_file": str(sidecar),
                "server_out": str(Path(td) / "outsource" / "Movies" / "movie.en.srt"),
                "output_size": sidecar.stat().st_size,
            }
        ],
    }
    (pending_root / "movie.mkv.manifest.json").write_text(json.dumps(manifest_payload), encoding="utf-8")
    pending_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        pending_push_path=pending_root,
    )
    pending_summary = service.scan_pending_publish(pending_resolved)
    assert pending_summary["count"] == 1, "pending publish scanner should count manifests"
    assert pending_summary["payload_count"] == 3, "pending publish scanner should count payload files"
    assert len(pending_summary["rows"]) == 2, "pending publish scanner should expose parked manifest rows and orphan payload rows"
    manifest_row = next(row for row in pending_summary["rows"] if row["manifest_path"])
    orphan_row = next(row for row in pending_summary["rows"] if row["state"] == "orphan_payload")
    assert manifest_row["publish_mode"] == "deferred" and manifest_row["route"] == "encode", "pending publish scanner should preserve publish mode and route"
    assert manifest_row["sidecar_count"] == 1 and manifest_row["missing_sidecar_count"] == 0, "pending publish scanner should summarize sidecars"
    assert manifest_row["local_exists"] is True, "pending publish scanner should verify parked payload existence"
    assert orphan_row["local_file"].endswith("orphan.mkv"), "pending publish scanner should expose orphan payloads"

    try:
        service._spawn(
            [sys.executable, "-c", "import sys; sys.stderr.write('launch boom\\n'); sys.exit(7)"],
            show_console=False,
            resolved=active_resolved,
            job_kind="pipeline",
            mode="once",
            metadata={"test_case": "immediate_failure"},
        )
        raise AssertionError("immediate nonzero launch should raise")
    except RuntimeError as exc:
        assert "exited immediately with code 7" in str(exc), "immediate launch failure should report exit code"
        assert "launch boom" in str(exc), "immediate launch failure should include stderr tail"
    failed_records = list(active_resolved.active_jobs_path.glob("*.json"))
    assert len(failed_records) == 1, "immediate launch failure should write one active job record"
    failed_record = json.loads(failed_records[0].read_text(encoding="utf-8"))
    assert failed_record["schema_version"] == "desktop_active_job.v1", "active job schema missing"
    assert failed_record["status"] == "failed_immediate", "immediate failure status missing from active job record"
    assert failed_record["return_code"] == 7, "immediate failure return code missing from active job record"
    assert failed_record["job_kind"] == "pipeline" and failed_record["mode"] == "once", "active job kind/mode missing"
    assert failed_record["stdout_log"] and failed_record["stderr_log"], "active job log paths missing"
    ready_proc = service._spawn(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        show_console=False,
        resolved=active_resolved,
        job_kind="pipeline",
        mode="continuous",
        metadata={"test_case": "active_then_kill"},
    )
    try:
        assert ready_proc.poll() is None, "ready process should still be running after readiness check"
        ready_record_path = Path(getattr(ready_proc, "_mediapipeline_active_job_record"))
        ready_record = json.loads(ready_record_path.read_text(encoding="utf-8"))
        assert ready_record["status"] == "active", "active process should update active job record to active"
        assert ready_record["pid"] == ready_proc.pid, "active job record PID mismatch"
    finally:
        service.kill_process_tree(ready_proc, "ready-test")
    killed_record = json.loads(ready_record_path.read_text(encoding="utf-8"))
    assert killed_record["status"] == "killed", "killed process should update active job record"
    assert killed_record.get("completed_at"), "terminal active job record should include completed_at"
    control_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=Path(td) / "control-local",
        pause_flag=Path(td) / "control-local" / "State" / "Pipeline" / "pipeline_pause.flag",
        stop_flag=Path(td) / "control-local" / "State" / "Pipeline" / "pipeline_stop.flag",
        rescan_flag=Path(td) / "control-local" / "State" / "Pipeline" / "pipeline_rescan.flag",
    )
    assert service.toggle_pause_flag(control_resolved) == "Pause requested."
    pause_payload = json.loads(control_resolved.pause_flag.read_text(encoding="utf-8"))
    assert pause_payload["schema_version"] == "pipeline_control_flag.v1", "pause flag schema missing"
    assert pause_payload["action"] == "pause", "pause flag action missing"
    assert pause_payload["request_id"], "pause flag request id missing"
    assert pause_payload["created_at"], "pause flag timestamp missing"
    assert not list(control_resolved.pause_flag.parent.glob("*.tmp")), "control flag atomic write left temp files"
    assert service.toggle_pause_flag(control_resolved) == "Pause flag cleared."
    assert not control_resolved.pause_flag.exists(), "pause flag clear did not remove the flag"
    assert service.write_flag(control_resolved.stop_flag, "Stop") == "Stop requested."
    stop_payload = json.loads(control_resolved.stop_flag.read_text(encoding="utf-8"))
    assert stop_payload["action"] == "stop" and stop_payload["request_id"] != pause_payload["request_id"], "stop flag did not get a unique request payload"
    assert service.write_flag(control_resolved.rescan_flag, "Rescan") == "Rescan requested."
    rescan_payload = json.loads(control_resolved.rescan_flag.read_text(encoding="utf-8"))
    assert rescan_payload["action"] == "rescan", "rescan flag action missing"
    control_resolved.pause_flag.write_text("", encoding="utf-8")
    old_mtime = time.time() - 7200
    os.utime(control_resolved.pause_flag, (old_mtime, old_mtime))
    cleanup_messages = service.prepare_pipeline_control_flags_for_launch(control_resolved, stale_after_seconds=3600)
    assert not control_resolved.pause_flag.exists(), "stale legacy pause flag should be removed before launch"
    assert not control_resolved.stop_flag.exists(), "pre-existing stop flag should be removed before launch"
    assert control_resolved.rescan_flag.exists(), "fresh rescan flag should remain available for launch"
    assert any("stale pause" in message for message in cleanup_messages), "stale pause cleanup should be reported"
    assert any("pre-existing stop" in message for message in cleanup_messages), "stop cleanup should be reported"
    assert any("rescan flag remains active" in message for message in cleanup_messages), "fresh rescan retention should be reported"
    runtime_local = Path(td) / "runtime-local"
    runtime_state = runtime_local / "State"
    runtime_targets = [
        runtime_state / "Progress" / "pipeline_progress.json",
        runtime_local / "pipeline_progress.json",
        runtime_state / "Pipeline" / "pipeline_pause.flag",
        runtime_local / "pipeline_pause.flag",
        runtime_state / "Pipeline" / "pipeline_stop.flag",
        runtime_local / "pipeline_stop.flag",
        runtime_state / "Pipeline" / "pipeline_rescan.flag",
        runtime_local / "pipeline_rescan.flag",
        runtime_local / "AuditReports" / "audit_progress.json",
    ]
    for target in runtime_targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("runtime", encoding="utf-8")
    runtime_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=runtime_local,
        state_root=runtime_state,
        progress_file=runtime_state / "Progress" / "pipeline_progress.json",
        pause_flag=runtime_state / "Pipeline" / "pipeline_pause.flag",
        stop_flag=runtime_state / "Pipeline" / "pipeline_stop.flag",
        rescan_flag=runtime_state / "Pipeline" / "pipeline_rescan.flag",
        audit_reports_path=runtime_local / "AuditReports",
    )
    removed_runtime = set(service.clear_runtime_artifacts(runtime_resolved, include_pipeline=True, include_audit=True))
    expected_runtime = {
        "pipeline progress",
        "legacy pipeline progress",
        "pause flag",
        "legacy pause flag",
        "stop flag",
        "legacy stop flag",
        "rescan flag",
        "legacy rescan flag",
        "audit progress",
    }
    assert expected_runtime.issubset(removed_runtime), f"runtime cleanup removed labels mismatch: {removed_runtime}"
    assert all(not target.exists() for target in runtime_targets), "runtime cleanup should remove state-store and legacy progress/control files"
    unsafe_progress = Path(td) / "outside-runtime" / "pipeline_progress.json"
    unsafe_progress.parent.mkdir(parents=True, exist_ok=True)
    unsafe_progress.write_text("unsafe", encoding="utf-8")
    unsafe_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=runtime_local,
        state_root=runtime_state,
        progress_file=unsafe_progress,
        pause_flag=runtime_state / "Pipeline" / "pipeline_pause.flag",
        stop_flag=runtime_state / "Pipeline" / "pipeline_stop.flag",
        rescan_flag=runtime_state / "Pipeline" / "pipeline_rescan.flag",
        audit_reports_path=runtime_local / "AuditReports",
    )
    try:
        service.clear_runtime_artifacts(unsafe_resolved, include_pipeline=True, include_audit=False)
        raise AssertionError("runtime cleanup should reject progress files outside expected state paths")
    except RuntimeError as exc:
        assert "outside expected runtime state paths" in str(exc), "unsafe runtime cleanup should report path containment failure"
    assert unsafe_progress.exists(), "unsafe runtime cleanup target must not be deleted"
    wrong_name = runtime_state / "Progress" / "not_pipeline_progress.json"
    wrong_name.parent.mkdir(parents=True, exist_ok=True)
    wrong_name.write_text("wrong", encoding="utf-8")
    wrong_name_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=runtime_local,
        state_root=runtime_state,
        progress_file=wrong_name,
        pause_flag=runtime_state / "Pipeline" / "pipeline_pause.flag",
        stop_flag=runtime_state / "Pipeline" / "pipeline_stop.flag",
        rescan_flag=runtime_state / "Pipeline" / "pipeline_rescan.flag",
        audit_reports_path=runtime_local / "AuditReports",
    )
    try:
        service.clear_runtime_artifacts(wrong_name_resolved, include_pipeline=True, include_audit=False)
        raise AssertionError("runtime cleanup should reject unexpected artifact filenames")
    except RuntimeError as exc:
        assert "unexpected filename" in str(exc), "wrong-name runtime cleanup should report filename validation failure"
    assert wrong_name.exists(), "wrong-name runtime cleanup target must not be deleted"
    unsafe_audit_root = Path(td) / "outside-audit"
    unsafe_audit_file = unsafe_audit_root / "audit_progress.json"
    unsafe_audit_root.mkdir(parents=True, exist_ok=True)
    unsafe_audit_file.write_text("unsafe", encoding="utf-8")
    unsafe_audit_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=runtime_local,
        state_root=runtime_state,
        progress_file=runtime_state / "Progress" / "pipeline_progress.json",
        pause_flag=runtime_state / "Pipeline" / "pipeline_pause.flag",
        stop_flag=runtime_state / "Pipeline" / "pipeline_stop.flag",
        rescan_flag=runtime_state / "Pipeline" / "pipeline_rescan.flag",
        audit_reports_path=unsafe_audit_root,
    )
    try:
        service.clear_runtime_artifacts(unsafe_audit_resolved, include_pipeline=False, include_audit=True)
        raise AssertionError("runtime cleanup should reject audit progress outside LocalBase AuditReports")
    except RuntimeError as exc:
        assert "outside expected runtime state paths" in str(exc), "unsafe audit cleanup should report path containment failure"
    assert unsafe_audit_file.exists(), "unsafe audit progress target must not be deleted"
    event_file = Path(td) / "local-events" / "pipeline_events.jsonl"
    event_file.parent.mkdir(parents=True)
    event_rows = [
        json.dumps({"event_type": "old", "status": "ignored"}),
        "not json yet",
        "[]",
        json.dumps({
            "schema_version": "pipeline_event.v1",
            "event_id": "event-job-started",
            "event_type": "job_started",
            "timestamp": "2026-05-06T12:00:00Z",
            "created_at": "2026-05-06T12:00:00Z",
            "job_id": "job-1",
            "source_path": str(Path(td) / "Movies" / "Example Movie.mkv"),
            "data": {"nested": True},
        }),
        json.dumps({
            "schema_version": "pipeline_event.v1",
            "event_id": "event-tool-completed",
            "event_type": "tool_completed",
            "timestamp": "2026-05-06T12:01:00Z",
            "created_at": "2026-05-06T12:01:00Z",
            "stage": "encode",
            "route": "encode",
            "status": "failed",
            "job_id": "job-1",
            "source_path": str(Path(td) / "Movies" / "Example Movie.mkv"),
            "data": {"tool_name": "ffmpeg", "exit_code": 1},
        }),
    ]
    event_file.write_text("\n".join(event_rows) + "\n", encoding="utf-8")
    event_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=event_file.parent,
        event_file=event_file,
    )
    events = service.read_pipeline_events_tail(event_resolved, line_count=4)
    assert [event["event_type"] for event in events] == ["job_started", "tool_completed"], "event reader should skip corrupt and non-object JSONL rows"
    assert events[0]["data"]["nested"] is True, "event reader should preserve nested event data"
    assert service.read_pipeline_events_tail(event_resolved, line_count=1)[0]["event_type"] == "tool_completed", "event tail should honor requested line count"
    assert service.read_pipeline_events_tail(event_resolved, line_count=0) == [], "zero-line event tail should be empty"
    assert service._build_current_activity(event_resolved, None, "", events) == "Example Movie.mkv | encode failed", "event fallback should describe latest structured activity"
    assert service._build_current_activity(event_resolved, {"CurrentStage": "encode", "CurrentStagePercent": 25, "CurrentFile": "Progress Movie.mkv"}, "encode: 1%", events) == "Progress Movie | encode 25%", "progress JSON should stay authoritative over event fallback"
    assert service._build_current_activity(event_resolved, None, "2026-04-30 12:00:00 [INFO] encode: 44%", []) == "No active work reported.", "plain log text must not drive live activity when no structured event is available"
    snapshot = service.build_snapshot(event_resolved, "")
    assert snapshot.pipeline_events[-1]["event_type"] == "tool_completed", "snapshot should carry structured pipeline events for Live diagnostics"
    assert "Recent pipeline events" in snapshot.status_summary and "tool_completed | failed | encode | ffmpeg | Example Movie.mkv" in snapshot.status_summary, "diagnostics summary should be fed from structured pipeline events"
    service.save_app_state({
        "schedule_enabled": True,
        "queue_quick_view": "Priority",
        "audit_quick_view": "Rerun Pipeline",
    })
    saved_state = service.load_app_state()
    assert saved_state["schedule_enabled"] is True, "saved app state did not reload"
    assert saved_state["queue_quick_view"] == "Priority", "queue quick view did not round-trip"
    raw_state = json.loads(service.app_state_path.read_text(encoding="utf-8"))
    assert raw_state["schema_version"] == "desktop_app_state.v1", "app state schema version missing"
    assert raw_state.get("created_at"), "app state created_at missing"
    assert not list(Path(td).glob(f".{service.app_state_path.name}.*")), "atomic app state write left temp files"
    state_app_path = Path(td) / "state-local" / "State" / "App" / APP_STATE_NAME
    service._migrate_app_state_path(state_app_path)
    assert service.app_state_path == state_app_path, "app state path should move under LocalBase state store after resolution"
    assert state_app_path.exists(), "legacy app state was not copied to the state store"
    service.save_app_state({"schedule_enabled": False, "queue_quick_view": "Movies Only"})
    assert json.loads(state_app_path.read_text(encoding="utf-8"))["queue_quick_view"] == "Movies Only", "state-store app state did not save"
    service.app_state_path.write_text("{bad json", encoding="utf-8")
    recovered_state = service.load_app_state()
    assert recovered_state["schedule_enabled"] is False, "corrupt app state should fall back to defaults"
    assert recovered_state["queue_quick_view"] == "All Items", "corrupt app state did not restore default queue quick view"
    config_values = {
        "SourceMovies": str(Path(td) / "movies"),
        "SourceTV": str(Path(td) / "tv"),
        "Outsource": str(Path(td) / "plex"),
        "LocalBase": str(Path(td) / "scratch"),
        "VideoCodec": "hevc_nvenc",
        "VideoPreset": "p5",
        "OutputContainer": "mkv",
        "EncodeTuningPreset": "balanced_nvenc",
        "EncodeLadder": "auto",
        "ExtraVideoFlags": ["-rc-lookahead", "60"],
        "AudioPassthroughProfile": "compatibility",
        "CompatibleAudioCodecs": ["aac"],
        "AudioTranscodeCodec": "eac3",
        "AudioTranscodeBitrate": "640k",
        "AudioDownmixMode": "max_channels",
        "AudioMaxChannels": 6,
        "PriorityMarkers": ["!"],
        "ValidExtensions": [".mkv", ".mp4"],
        "RemuxSafeVideoCodecs": ["h264", "hevc"],
        "SubKeepLanguages": ["eng"],
        "EncodeThresholdGB": 12,
        "TVEncodeThresholdGB": 8,
        "MinFreeSpaceGB": 10,
        "OutsourceMinFreeSpaceGB": 20,
        "VideoQuality": 23,
        "MergeThresholdMs": 250,
        "FFmpegEncodeTimeoutSeconds": 3600,
        "FFmpegRemuxTimeoutSeconds": 1200,
        "SubtitleExtractTimeoutSeconds": 300,
        "SubtitleProbeTimeoutSeconds": 60,
        "BdpgsOcrTimeoutSeconds": 900,
        "TransientFailureRetryLimit": 3,
        "SourceScanIntervalSeconds": 5,
        "ProcessedIndexRefreshSeconds": 60,
        "RobocopyFlags": ["/J", "/R:2", "/W:2"],
        "RobocopyTimeoutSeconds": 300,
        "SourceScanTimeoutSeconds": 300,
        "IndexScanTimeoutSeconds": 300,
        "CleanupScanTimeoutSeconds": 120,
        "CleanupStaleAgeHours": 24,
    }
    config_preview = service.build_config_preview({}, config_values, list(config_values.keys()))
    assert not config_preview.errors, f"valid config preview unexpectedly failed: {config_preview.errors}"
    assert config_preview.merged_config["ExtraVideoFlags"] == [], "structured encode presets should clear raw ExtraVideoFlags before saving"
    assert any("ExtraVideoFlags are ignored" in warning for warning in config_preview.warnings), "structured encode presets should warn when raw flags are ignored"
    assert config_preview.merged_config["CompatibleAudioCodecs"] == ["aac", "ac3", "eac3", "mp3", "opus", "vorbis"], "structured audio profiles should write their codec list before saving"
    assert any("CompatibleAudioCodecs are controlled by AudioPassthroughProfile" in warning for warning in config_preview.warnings), "structured audio profiles should warn when raw codec lists are replaced"
    legacy_flag_values = dict(config_values)
    legacy_flag_values["EncodeTuningPreset"] = "custom_legacy_flags"
    legacy_preview = service.build_config_preview({}, legacy_flag_values, list(legacy_flag_values.keys()))
    assert not legacy_preview.errors, f"custom legacy encode preview unexpectedly failed: {legacy_preview.errors}"
    assert legacy_preview.merged_config["ExtraVideoFlags"] == ["-rc-lookahead", "60"], "custom legacy encode preset should preserve explicit raw flags"
    custom_audio_values = dict(config_values)
    custom_audio_values["AudioPassthroughProfile"] = "custom_codec_list"
    custom_audio_values["CompatibleAudioCodecs"] = ["aac", "flac"]
    custom_audio_preview = service.build_config_preview({}, custom_audio_values, list(custom_audio_values.keys()))
    assert not custom_audio_preview.errors, f"custom audio passthrough preview unexpectedly failed: {custom_audio_preview.errors}"
    assert custom_audio_preview.merged_config["CompatibleAudioCodecs"] == ["aac", "flac"], "custom audio passthrough profile should preserve explicit codec lists"
    config_host = service.resolve_powershell_host()
    save_config_path = Path(td) / "config-save" / "MediaPipeline_config_chatgpt.psd1"
    save_config_path.parent.mkdir(parents=True, exist_ok=True)
    save_config_path.write_text("@{ OldValue = 'keep-in-backup' }\n", encoding="utf-8")
    save_result = service.save_config_document(
        save_config_path,
        config_preview.preview_text,
        create_backup=True,
        config_values=config_preview.merged_config,
        powershell_host=config_host,
    )
    assert save_result.backup_path and save_result.backup_path.exists(), "config save-in-place should keep a backup"
    assert save_result.backup_path.parent.name == "ConfigBackups", "config backups should be isolated from the active config directory"
    assert "keep-in-backup" in save_result.backup_path.read_text(encoding="utf-8"), "config backup should preserve previous content"
    assert "SourceMovies" in save_config_path.read_text(encoding="utf-8"), "config save did not write preview text"
    assert not list(save_config_path.parent.glob(f".{save_config_path.name}.*")), "config atomic save left temp files"
    backup_dir = save_config_path.parent / "ConfigBackups"
    backup_count = len(list(backup_dir.glob("*.backup_*.psd1")))
    invalid_values = dict(config_values)
    invalid_values["LocalBase"] = ""
    invalid_preview = service.build_config_preview({}, invalid_values, list(invalid_values.keys()))
    before_invalid_save = save_config_path.read_text(encoding="utf-8")
    try:
        service.save_config_document(
            save_config_path,
            invalid_preview.preview_text,
            create_backup=True,
            config_values=invalid_preview.merged_config,
            powershell_host=config_host,
        )
        raise AssertionError("invalid config values should be rejected before save")
    except ValueError as exc:
        assert "LocalBase is required" in str(exc), "invalid config save should report value validation errors"
    assert save_config_path.read_text(encoding="utf-8") == before_invalid_save, "invalid config save should not modify the target"
    assert len(list(backup_dir.glob("*.backup_*.psd1"))) == backup_count, "invalid config save should not create a backup"
    try:
        service.save_config_document(
            save_config_path,
            "@{\nBroken =\n",
            create_backup=True,
            config_values=config_preview.merged_config,
            powershell_host=config_host,
        )
        raise AssertionError("invalid PSD1 syntax should be rejected before save")
    except ValueError as exc:
        assert "Config syntax validation failed" in str(exc), "invalid PSD1 syntax should be reported"
    assert save_config_path.read_text(encoding="utf-8") == before_invalid_save, "syntax-invalid config save should not modify the target"
    overlap_values = dict(config_values)
    overlap_values["LocalBase"] = str(Path(overlap_values["SourceMovies"]) / "scratch")
    _, overlap_warnings = service.validate_config_values(overlap_values)
    assert any("LocalBase is inside SourceMovies" in warning for warning in overlap_warnings), "config validation should warn when scratch is inside source"
    same_source_values = dict(config_values)
    same_source_values["SourceTV"] = same_source_values["SourceMovies"]
    _, same_source_warnings = service.validate_config_values(same_source_values)
    assert "SourceMovies and SourceTV point to the same location." in same_source_warnings, "config validation should preserve same-source warning"
    profile_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=save_config_path,
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=config_host,
    )
    safe_profile_name, profile_path = service.save_config_profile(profile_resolved, "Night Run")
    assert safe_profile_name == "Night_Run", "profile save should preserve existing space-to-underscore behavior"
    assert profile_path.exists(), "profile save should write a profile file"
    assert not list(profile_path.parent.glob(f".{profile_path.name}.*")), "profile save should not leave atomic temp files"
    try:
        service.save_config_profile(profile_resolved, "..\\bad")
        raise AssertionError("unsafe profile names should be rejected")
    except ValueError as exc:
        assert "letters, digits, hyphens, and underscores" in str(exc), "unsafe profile name should explain accepted characters"
    unsafe_profile_name = profile_path.parent / "bad name.psd1"
    unsafe_profile_name.write_text(config_preview.preview_text, encoding="utf-8")
    listed_profiles = service.list_config_profiles(save_config_path)
    assert "Night_Run" in listed_profiles, "safe profile should be listed"
    assert "bad name" not in listed_profiles, "unsafe profile filenames should be ignored"
    invalid_profile_path = profile_path.parent / "InvalidProfile.psd1"
    invalid_profile_path.write_text(invalid_preview.preview_text, encoding="utf-8")
    before_invalid_profile_load = save_config_path.read_text(encoding="utf-8")
    try:
        service.load_config_profile(profile_resolved, "InvalidProfile")
        raise AssertionError("invalid profile values should be rejected before load")
    except ValueError as exc:
        assert "LocalBase is required" in str(exc), "invalid profile load should report value validation errors"
    assert save_config_path.read_text(encoding="utf-8") == before_invalid_profile_load, "invalid profile load should not overwrite active config"
    save_config_path.write_text("@{ ActiveValue = 'before-profile-load' }\n", encoding="utf-8")
    loaded_profile_name, loaded_profile_path, loaded_result = service.load_config_profile(profile_resolved, "Night_Run")
    assert loaded_profile_name == "Night_Run" and loaded_profile_path == profile_path, "profile load should return the validated profile identity"
    assert loaded_result.backup_path and "before-profile-load" in loaded_result.backup_path.read_text(encoding="utf-8"), "profile load should back up the replaced active config"
    assert "SourceMovies" in save_config_path.read_text(encoding="utf-8"), "profile load should apply the validated profile content"
    assert service.normalize_config_path_value("file:///C:/Media/Test Folder").endswith(r"C:\Media\Test Folder"), "settings path normalization should handle file URIs"
    assert starts_with_priority_marker("  [NOW] Movie.mkv", ["!", "[NOW]"]), "priority utility should detect sorted marker"
    assert remove_priority_markers_from_name("  [NOW] ! Movie.mkv", ["!", "[NOW]"]) == "Movie.mkv", "priority utility should strip repeated markers"

    old = (datetime.now() - timedelta(seconds=30)).isoformat()
    fresh = datetime.now().isoformat()
    stale_pipeline_progress = {
        "ProgressVersion": 2,
        "CurrentStage": "scanning",
        "Status": "Scanning sources",
        "LastUpdate": old,
        "CurrentFile": "None",
        "CurrentQueueIndex": 0,
        "CurrentQueueTotal": 0,
        "CurrentStagePercent": None,
        "PauseRequested": False,
        "StopRequested": False,
        "ControlRequests": {},
        "TotalProcessed": 0,
        "Encoded": 0,
        "Remuxed": 0,
        "Failed": 0,
        "Movies": 0,
        "TVEpisodes": 0,
    }
    assert service.is_progress_stale(stale_pipeline_progress), "active pipeline progress should be stale when LastUpdate stops moving"
    event_resolved.progress_file = Path(td) / "local-events" / "pipeline_progress.json"
    event_resolved.progress_file.write_text(json.dumps(stale_pipeline_progress), encoding="utf-8")
    stale_snapshot = service.build_snapshot(event_resolved, "")
    assert stale_snapshot.current_activity.startswith("Stale progress from previous run"), "stale active progress should be labeled as previous-run state"
    assert "scanning sources" not in stale_snapshot.current_activity.lower(), "stale progress must not keep reporting an active source scan"
    assert service.is_audit_progress_stale({"status": "scanning", "completed": False, "failed": False, "last_update": old})
    assert not service.is_audit_progress_stale({"status": "scanning", "completed": False, "failed": False, "last_update": fresh})
    assert not service.is_audit_progress_stale({"status": "completed", "completed": True, "failed": False, "last_update": old})
    text = service.format_audit_progress({
        "status": "scanning",
        "processed_files": 1,
        "total_files": 2,
        "percent_complete": 50,
        "last_update": old,
        "progress_persistence_healthy": False,
        "progress_write_failures": 3,
    })
    assert "STALE" in text
    assert "progress writes failing (3)" in text
    sleep_proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        kill_message = service.kill_process_tree(sleep_proc, "test-sleeper")
        assert "Force-killed test-sleeper" in kill_message, "kill_process_tree should report a verified kill"
        assert sleep_proc.poll() is not None, "kill_process_tree must verify the child process is gone"
    finally:
        if sleep_proc.poll() is None:
            sleep_proc.kill()

    def write_queue_snapshot(local_base: Path, rows: list[dict], movie_count: int, tv_count: int = 0) -> Path:
        snap = local_base / "State" / "Progress" / "queue_snapshot.json"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(json.dumps({
            "schema_version": "queue_plan_snapshot.v1",
            "produced_at": datetime.now().isoformat(),
            "movie_count_total": movie_count,
            "tv_count_total": tv_count,
            "runnable_count": len(rows),
            "rows": rows,
        }), encoding="utf-8")
        return snap

    queue_root = Path(td) / "queue-src"
    queue_root.mkdir()
    source = queue_root / "same-size-replacement.mkv"
    source.write_bytes(b"abc")
    local_base = Path(td) / "queue-local"
    stat = source.stat()
    queue_snapshot = write_queue_snapshot(local_base, [{
        "global_order": 1,
        "phase": "movie",
        "media_kind": "movie",
        "queue_index": 1,
        "queue_total": 1,
        "is_priority": False,
        "priority_reasons": [],
        "priority_rank": 0,
        "source_path": str(source),
        "root_path": str(queue_root),
        "relative_path": source.name,
        "display_name": "same-size-replacement",
        "last_write_utc": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size_gb": 0.0,
        "route": "Remux",
        "route_reason": "snapshot test",
    }], movie_count=1)
    queue_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=local_base,
        state_root=local_base / "State",
        queue_snapshot_path=queue_snapshot,
        source_movies=queue_root,
        config_data={"ValidExtensions": [".mkv"]},
    )
    records = service.build_queue_preview(queue_resolved)
    assert len(records) == 1, "queue snapshot should expose runnable records"
    assert records[0].source_path == source
    assert records[0].phase == "MOVIE"
    assert "Queue plan source:" in service._queue_completed_cache_status

    def make_fake_pwsh(name: str, python_code: str) -> Path:
        helper = Path(td) / f"{name}.py"
        helper.write_text(python_code, encoding="utf-8")
        if os.name == "nt":
            script = Path(td) / f"{name}.cmd"
            script.write_text(
                f"@echo off\r\n\"{sys.executable}\" \"{helper}\" %*\r\nexit /b %ERRORLEVEL%\r\n",
                encoding="utf-8",
            )
        else:
            script = Path(td) / name
            script.write_text(f"#!/bin/sh\nexec \"{sys.executable}\" \"{helper}\" \"$@\"\n", encoding="utf-8")
            os.chmod(script, 0o755)
        return script

    def fake_pwsh_write_snapshot_code(payload: dict) -> str:
        payload_text = json.dumps(payload)
        return f"""
import json
import sys

out = None
for index, arg in enumerate(sys.argv):
    if arg.lower() == "-queueplanoutpath" and index + 1 < len(sys.argv):
        out = sys.argv[index + 1]
        break
if not out:
    sys.exit(9)
with open(out, "w", encoding="utf-8") as handle:
    handle.write({payload_text!r})
sys.exit(0)
"""

    dryrun_local = Path(td) / "dryrun-local"
    dryrun_snapshot = dryrun_local / "State" / "Progress" / "queue_snapshot.json"
    dryrun_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "ignored-pipeline.ps1",
        config_path=Path(td) / "ignored-config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=dryrun_local,
        state_root=dryrun_local / "State",
        queue_snapshot_path=dryrun_snapshot,
    )
    future_produced_at = (datetime.now().astimezone() + timedelta(seconds=5)).isoformat()
    fake_success = make_fake_pwsh("fake-queue-success", fake_pwsh_write_snapshot_code({
        "schema_version": "queue_plan_snapshot.v1",
        "produced_at": future_produced_at,
        "movie_count_total": 0,
        "tv_count_total": 0,
        "runnable_count": 0,
        "rows": [],
    }))
    dryrun_resolved.powershell_host = str(fake_success)
    records = service.build_queue_preview(dryrun_resolved, force_refresh=True)
    assert records == [], "empty successful dry-run snapshot should produce an empty queue"
    promoted = json.loads(dryrun_snapshot.read_text(encoding="utf-8"))
    assert promoted.get("desktop_queue_preview_request_id"), "dry-run snapshot should carry a desktop request id"
    assert not list(dryrun_snapshot.parent.glob("*.dryrun.json")), "dry-run temp snapshot should be cleaned up"
    assert "live (dry run" in service._queue_completed_cache_status, "dry-run queue health should identify live source"

    stale_snapshot = write_queue_snapshot(dryrun_local, [{
        "global_order": 1,
        "phase": "movie",
        "media_kind": "movie",
        "queue_index": 1,
        "queue_total": 1,
        "is_priority": False,
        "priority_reasons": [],
        "priority_rank": 0,
        "source_path": str(source),
        "root_path": str(queue_root),
        "relative_path": source.name,
        "display_name": "stale-cached",
        "last_write_utc": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size_gb": 0.0,
        "route": "Remux",
        "route_reason": "stale fallback",
    }], movie_count=1)
    old_mtime = time.time() - 7200
    os.utime(stale_snapshot, (old_mtime, old_mtime))
    fake_fail = make_fake_pwsh("fake-queue-fail", "import sys\nsys.stderr.write('queue dry-run failed\\n')\nsys.exit(12)\n")
    dryrun_resolved.powershell_host = str(fake_fail)
    try:
        service.build_queue_preview(dryrun_resolved, force_refresh=True)
        raise AssertionError("explicit queue refresh should not fall back to stale snapshot after dry-run failure")
    except RuntimeError as exc:
        assert "Queue dry-run exited 12" in str(exc), "dry-run failure should report exit code"
    fallback_records = service.build_queue_preview(dryrun_resolved, force_refresh=False)
    assert len(fallback_records) == 1 and fallback_records[0].display_name == "stale-cached", "non-forced queue preview may fall back to cached snapshot"
    assert "Showing last cached snapshot" in service._queue_completed_cache_status, "cached fallback should be disclosed"

    fake_slow = make_fake_pwsh("fake-queue-slow", "import time\ntime.sleep(5)\n")
    dryrun_resolved.powershell_host = str(fake_slow)
    original_queue_timeout = service.QUEUE_DRY_RUN_TIMEOUT_SECONDS
    service.QUEUE_DRY_RUN_TIMEOUT_SECONDS = 0.2
    try:
        try:
            service.build_queue_preview(dryrun_resolved, force_refresh=True)
            raise AssertionError("timed-out queue dry-run should raise for explicit refresh")
        except RuntimeError as exc:
            assert "Queue dry-run timed out" in str(exc), "queue dry-run timeout should be surfaced"
    finally:
        service.QUEUE_DRY_RUN_TIMEOUT_SECONDS = original_queue_timeout
    assert not list(dryrun_snapshot.parent.glob("*.dryrun.json")), "timed-out dry-run temp snapshot should be cleaned up"

    audit_record = AuditRecord(
        source_csv=Path(td) / "audit.csv",
        row={
            "Path": str(source),
            "LookupTitle": "Same Size Replacement",
            "MediaType": "Movie",
            "EffectiveBucket": "RERUN_PIPELINE",
            "PrimaryIssueCode": "test-issue",
        },
    )
    completed_record = CompletedJobRecord(
        sidecar_path=Path(td) / "same-size-replacement.pipeline.json",
        payload={
            "source_path": str(source),
            "route": "remux",
            "encoded_at": datetime.now().isoformat(),
            "output_path": str(Path(td) / "out" / "same-size-replacement.mkv"),
        },
    )
    failure_record = FailureRecord(
        source_json=Path(td) / "failure.json",
        payload={
            "SourcePath": str(source),
            "LookupTitle": "Same Size Replacement",
            "Stage": "encode",
            "ErrorCode": "ENCODE_TEST_FAILED",
        },
    )
    correlation = service.correlate_audit_record(audit_record, [completed_record], [failure_record])
    assert correlation["completed_count"] == 1 and correlation["failure_count"] == 1, "audit correlation should count completed and failed matches"
    correlation_lines = service.format_audit_correlation(audit_record, [completed_record], [failure_record])
    assert "REMUX" in correlation_lines[0] and "ENCODE_TEST_FAILED" in correlation_lines[1], "audit correlation summary should include completed route and failure code"

    completed_local = Path(td) / "completed-local"
    completed_manifest = completed_local / "State" / "Completed" / "completed_jobs.jsonl"
    completed_manifest.parent.mkdir(parents=True)
    existing_output = Path(td) / "out" / "existing.mkv"
    existing_output.parent.mkdir(parents=True)
    existing_output.write_bytes(b"media")
    missing_output = Path(td) / "out" / "missing.mkv"
    completed_manifest.write_text(
        json.dumps({"schema_version": "completed_job.v1", "output_path": str(existing_output), "route": "remux"}) + "\n"
        + json.dumps({"schema_version": "completed_job.v1", "output_path": str(missing_output), "route": "encode"}) + "\n",
        encoding="utf-8",
    )
    completed_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=completed_local,
        state_root=completed_local / "State",
        completed_manifest_path=completed_manifest,
    )
    completed_records = service.load_recent_completed_jobs(completed_resolved, force_refresh=True)
    assert len(completed_records) == 2, "completed diagnostics test should load both records"
    missing_record = completed_records[0]
    assert not missing_record.output_exists, "missing completed output should be cached as not existing"
    assert missing_record.output_health == "completed metadata without media", "missing output should expose metadata-without-media diagnostic"
    assert completed_records[1].output_exists and completed_records[1].output_health == "ok", "existing output should be marked healthy"

    priority_root = Path(td) / "priority-src"
    priority_root.mkdir()
    regular = priority_root / "Regular Movie.mkv"
    priority = priority_root / "!Urgent Movie.mkv"
    regular.write_bytes(b"regular")
    priority.write_bytes(b"priority")
    priority_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=Path(td) / "priority-local",
        state_root=Path(td) / "priority-local" / "State",
        source_movies=priority_root,
        completed_manifest_path=Path(td) / "priority-local" / "State" / "Completed" / "completed_jobs.jsonl",
        priority_markers=["!"],
        config_data={"ValidExtensions": [".mkv"]},
    )
    priority_resolved.queue_snapshot_path = write_queue_snapshot(priority_resolved.local_base, [
        {
            "global_order": 1,
            "phase": "priority",
            "media_kind": "movie",
            "queue_index": 1,
            "queue_total": 1,
            "is_priority": True,
            "priority_reasons": ["file"],
            "priority_rank": 2,
            "source_path": str(priority),
            "root_path": str(priority_root),
            "relative_path": priority.name,
            "display_name": "Urgent Movie",
            "last_write_utc": datetime.fromtimestamp(priority.stat().st_mtime).isoformat(),
            "size_gb": 0.0,
            "route": "Remux",
            "route_reason": "snapshot test",
        },
        {
            "global_order": 2,
            "phase": "movie",
            "media_kind": "movie",
            "queue_index": 1,
            "queue_total": 1,
            "is_priority": False,
            "priority_reasons": [],
            "priority_rank": 0,
            "source_path": str(regular),
            "root_path": str(priority_root),
            "relative_path": regular.name,
            "display_name": "Regular Movie",
            "last_write_utc": datetime.fromtimestamp(regular.stat().st_mtime).isoformat(),
            "size_gb": 0.0,
            "route": "Remux",
            "route_reason": "snapshot test",
        },
    ], movie_count=2)
    records = service.build_queue_preview(priority_resolved)
    assert len(records) == 2, "priority queue test should discover both files"
    assert records[0].is_priority and records[0].phase == "PRIORITY", "priority queue ordering should put marked files first"
    assert records[0].display_name == "Urgent Movie", "priority marker should be removed from display name"
    assert records[1].phase == "MOVIE" and not records[1].is_priority, "non-priority movie should follow priority files"

    missing_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=Path(td) / "missing-local",
        state_root=Path(td) / "missing-local" / "State",
        source_movies=Path(td) / "missing-source-root",
        completed_manifest_path=Path(td) / "missing-local" / "State" / "Completed" / "completed_jobs.jsonl",
        queue_snapshot_path=Path(td) / "missing-local" / "State" / "Progress" / "queue_snapshot.json",
        config_data={"ValidExtensions": [".mkv"]},
    )
    assert service.build_queue_preview(missing_resolved) == [], "missing source root should produce an empty queue preview"

    scheduled = []
    callbacks = []
    worker = UiBackgroundWorker(
        schedule_ui=lambda delay_ms, callback: scheduled.append(callback),
        is_ui_alive=lambda: True,
        logger=service.logger,
        poll_ms=10,
    )
    worker.start()
    worker.submit("sample", lambda: "ok", lambda value, error: callbacks.append((value, error)))
    deadline = time.time() + 2.0
    while not callbacks and time.time() < deadline:
        if scheduled:
            scheduled.pop(0)()
        else:
            time.sleep(0.01)
    worker.close()
    assert callbacks and callbacks[0][0] == "ok" and callbacks[0][1] is None, "UI worker must return background results through callback queue"

    local_base = Path(td) / "local"
    markers = local_base / "State" / "Failures" / "Markers"
    reports = local_base / "State" / "Failures" / "Reports"
    artifacts = local_base / "State" / "Failures" / "Artifacts"
    markers.mkdir(parents=True)
    reports.mkdir(parents=True)
    artifacts.mkdir(parents=True)
    marker = markers / "source-marker.json"
    report_json = reports / "round_failures_20260425_120000.json"
    report_txt = reports / "round_failures_20260425_120000.txt"
    repro = reports / "ffmpeg_encode_20260425_120000.cmd.txt"
    artifact = artifacts / "failed-output.mkv"
    marker.write_text("{}", encoding="utf-8")
    report_json.write_text("[]", encoding="utf-8")
    report_txt.write_text("failure report", encoding="utf-8")
    repro.write_text("ffmpeg repro", encoding="utf-8")
    artifact.write_bytes(b"artifact")
    resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=local_base,
        state_root=local_base / "State",
        failed_markers_path=markers,
        failed_reports_path=reports,
    )
    dry_run_summary = service.clear_failure_workspace(resolved, dry_run=True)
    dry_run_manifest = json.loads(Path(dry_run_summary["manifest_path"]).read_text(encoding="utf-8"))
    assert dry_run_summary["markers"] == 0 and dry_run_summary["reports"] == 0, "dry-run clear should not remove files"
    assert dry_run_manifest["status"] == "dry_run", "dry-run manifest should be labeled"
    assert len(dry_run_manifest["planned"]) == 3, "dry-run manifest should include planned marker/report removals"
    assert marker.exists() and report_json.exists() and report_txt.exists(), "dry-run clear removed files"
    summary = service.clear_failure_workspace(resolved)
    assert summary["markers"] == 1
    assert summary["reports"] == 2
    assert summary["manifest_path"], "clear failure workspace should return a manifest path"
    assert not marker.exists()
    assert not report_json.exists()
    assert not report_txt.exists()
    assert repro.exists()
    assert artifact.exists()
    clear_manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))
    assert clear_manifest["schema_version"] == "failure_workspace_clear_manifest.v1", "failure clear manifest schema missing"
    assert clear_manifest["status"] == "completed", "failure clear manifest status should be completed"
    assert len(clear_manifest["planned"]) == 3 and len(clear_manifest["removed"]) == 3, "failure clear manifest should record planned and removed files"
    removed_paths = {Path(item["path"]).name for item in clear_manifest["removed"]}
    assert marker.name in removed_paths and report_json.name in removed_paths and report_txt.name in removed_paths, "failure clear manifest missing removed file paths"
    assert repro.name not in removed_paths and artifact.name not in removed_paths, "failure clear manifest should not include repro/artifact files"

    outside = Path(td) / "outside-failure-markers"
    outside.mkdir()
    outside_marker = outside / "source-marker.json"
    outside_marker.write_text("{}", encoding="utf-8")
    unsafe_resolved = ResolvedPaths(
        app_root=Path(td),
        workspace_root=Path(td),
        pipeline_path=Path(td) / "pipeline.ps1",
        config_path=Path(td) / "config.psd1",
        audit_script_path=Path(td) / "audit.ps1",
        rerun_script_path=Path(td) / "rerun.ps1",
        powershell_host=None,
        local_base=local_base,
        state_root=local_base / "State",
        failed_markers_path=outside,
        failed_reports_path=reports,
    )
    try:
        service.clear_failure_workspace(unsafe_resolved)
        raise AssertionError("clear failure workspace should reject marker paths outside failure roots")
    except RuntimeError as exc:
        assert "outside failure workspace" in str(exc), "unsafe failure cleanup should report path containment refusal"
    assert outside_marker.exists(), "unsafe failure cleanup removed a file outside failure roots"

    for handler in list(service.logger.handlers):
        handler.close()
        service.logger.removeHandler(handler)
    logging.shutdown()
"@
        $pythonTest | & $python.Source -
        if ($LASTEXITCODE -ne 0) { throw "Desktop audit progress behavioral checks failed." }
    }
} finally {
    $env:PATH = $oldPath
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Reliability regression checks passed."
