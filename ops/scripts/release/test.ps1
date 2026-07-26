[CmdletBinding()]
param(
    [string]$BundleRoot,
    [switch]$RequireTests,
    [switch]$SkipToolIntegration,
    [switch]$SkipEndToEndSmoke,
    [switch]$PackageAcceptance,
    [string]$PackageAcceptanceAppDataRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

. (Join-Path $PSScriptRoot 'test_support.ps1')
. (Join-Path $PSScriptRoot 'test_policy.ps1')
. (Join-Path $PSScriptRoot 'test_contracts.ps1')
. (Join-Path $PSScriptRoot 'test_acceptance.ps1')



























































$script:BundleRoot = if ($BundleRoot) {
    [System.IO.Path]::GetFullPath($BundleRoot)
} elseif ($PSScriptRoot) {
    [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))))
} else {
    [System.IO.Path]::GetFullPath((Get-Location).Path)
}

$script:Pwsh = Resolve-ReleasePowerShell -Root $script:BundleRoot
$script:Failed = $false
$script:SkippedGates = @()

$pipelineRoot = Join-Path $script:BundleRoot 'ops\pipeline'
$testsRoot = Join-Path $pipelineRoot 'tests'
$verifier = Join-Path $script:BundleRoot 'ops\scripts\dev\verify-env.ps1'
$tauriPrereqs = Join-Path $script:BundleRoot 'apps\desktop\tauri\Test-TauriShell-Prereqs.ps1'
$webviewReliability = Join-Path $testsRoot 'Invoke-WebViewReliabilityChecks.ps1'
$releasePolicyUnit = Join-Path $testsRoot 'Unit\Invoke-ReleasePackagePolicyChecks.ps1'
$toolIntegration = Join-Path $testsRoot 'Invoke-ToolIntegrationChecks.ps1'
$endToEndSmoke = Join-Path $testsRoot 'Invoke-EndToEndSmokeChecks.ps1'
$releaseManifest = Join-Path $script:BundleRoot 'release_manifest.json'

Write-Section 'Release Self-Test'
Write-Host "Bundle root : $script:BundleRoot"
if ($script:Pwsh) {
    Write-Ok "PowerShell host: $script:Pwsh"
} else {
    Write-Fail 'PowerShell 7 host not found. Cannot run release checks.'
    exit 1
}

Write-Section 'Layout'
foreach ($entry in @(
    @{ Label = 'Desktop app assets'; Path = (Join-Path $script:BundleRoot 'apps\desktop'); Type = 'Container' },
    @{ Label = 'Docs'; Path = (Join-Path $script:BundleRoot 'docs'); Type = 'Container' },
    @{ Label = 'Pipeline ops'; Path = $pipelineRoot; Type = 'Container' },
    @{ Label = 'ops/scripts/smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke'); Type = 'Container' },
    @{ Label = 'Docs index'; Path = (Join-Path $script:BundleRoot 'docs\DOCS_INDEX.md'); Type = 'Leaf' },
    @{ Label = 'Bundle README'; Path = (Join-Path $script:BundleRoot 'docs\README_MediaPipelineRemuxEncodeAIO.md'); Type = 'Leaf' },
    @{ Label = 'Smoke test inventory'; Path = (Join-Path $script:BundleRoot 'docs\inventories\SMOKE_TEST_INVENTORY.md'); Type = 'Leaf' },
    @{ Label = 'Desktop/WebView docs README'; Path = (Join-Path $script:BundleRoot 'docs\desktop\README.md'); Type = 'Leaf' },
    @{ Label = 'Release package inventory'; Path = (Join-Path $script:BundleRoot 'docs\inventories\RELEASE_PACKAGE_ADMIN_INVENTORY.md'); Type = 'Leaf' },
    @{ Label = 'Canonical setup launcher'; Path = (Join-Path $script:BundleRoot 'ops\scripts\dev\setup.bat'); Type = 'Leaf' },
    @{ Label = 'Canonical run launcher'; Path = (Join-Path $script:BundleRoot 'ops\scripts\dev\run.bat'); Type = 'Leaf' },
    @{ Label = 'Canonical API and browser launcher'; Path = (Join-Path $script:BundleRoot 'ops\scripts\dev\start-api-and-browser.bat'); Type = 'Leaf' },
    @{ Label = 'Canonical local API launcher'; Path = (Join-Path $script:BundleRoot 'ops\scripts\dev\start-local-api.bat'); Type = 'Leaf' },
    @{ Label = 'Canonical Tauri preview launcher'; Path = (Join-Path $script:BundleRoot 'ops\scripts\dev\start-tauri-preview.bat'); Type = 'Leaf' },
    @{ Label = 'Canonical environment verifier'; Path = $verifier; Type = 'Leaf' },
    @{ Label = 'Canonical release build script'; Path = (Join-Path $script:BundleRoot 'ops\scripts\release\build.ps1'); Type = 'Leaf' },
    @{ Label = 'Canonical release self-test script'; Path = (Join-Path $script:BundleRoot 'ops\scripts\release\test.ps1'); Type = 'Leaf' },
    @{ Label = 'Canonical real-media validation worksheet helper'; Path = (Join-Path $script:BundleRoot 'ops\scripts\operator\New-RealMediaValidationWorksheet.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView evidence smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewRealMediaEvidenceSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView command evidence smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewCommandEvidenceSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView row detail smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView schedule smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewScheduleSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser schedule smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserScheduleSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser backend lifecycle smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserLifecycleSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser lifecycle reconciliation smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserLifecycleReconciliationSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke local API lifecycle contract smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke local API Maintenance dry-run contract smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-LocalApiMaintenanceDryRunContractSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke local API repair/reconcile dry-run contract smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-LocalApiRepairReconcileDryRunContractSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke local API sample validation contract smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-LocalApiSampleValidationContractSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser high-risk smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserHighRiskSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser diagnostics handoff smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser pending drain guard smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserPendingDrainGuardSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser completed pending proof smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserCompletedPendingProofSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser large daily-table smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserLargeTableSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser rename smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserRenameSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser network smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserNetworkSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser queue file-overrides smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserQueueFileOverridesSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser Queue/Launch/Completed smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserQueueLaunchCompletedSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser telemetry smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserTelemetrySmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser Maintenance/Reports smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserMaintenanceReportsSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser Maintenance change-ledger smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser Sample Validation smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserSampleValidationSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser safe operator commands smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserSafeOperatorCommandsSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser Home live-state smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserHomeLiveStateSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser Launch/Queue readiness smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser layout manager smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserLayoutManagerSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser prose-box audit'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserProseBoxAudit.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser visual-clutter screenshots'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserVisualClutterScreenshots.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView rename readiness smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewRenameReadinessSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser settings/launch smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserSettingsLaunchSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser Settings field-matrix smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserSettingsFieldMatrixSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView browser LibraryProfiles save smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewBrowserLibraryProfilesSaveSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView settings launch policy smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewSettingsLaunchPolicySmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView settings live-config smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'ops/scripts/smoke WebView settings patch evidence smoke'; Path = (Join-Path $script:BundleRoot 'ops/scripts/smoke\Test-WebViewSettingsPatchEvidenceSmoke.ps1'); Type = 'Leaf' },
    @{ Label = 'current reliability compatibility wrapper'; Path = (Join-Path $pipelineRoot 'tests\Invoke-ReliabilityRegressionChecks.ps1'); Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'current WebView reliability gate'; Path = $webviewReliability; Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'Release package policy unit gate'; Path = $releasePolicyUnit; Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'Native process cleanup unit gate'; Path = (Join-Path $pipelineRoot 'tests\Unit\Invoke-NativeProcessCleanupChecks.ps1'); Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'Runtime state hygiene unit gate'; Path = (Join-Path $pipelineRoot 'tests\Unit\Invoke-RuntimeStateHygieneChecks.ps1'); Type = 'Leaf'; Required = [bool]$RequireTests },
    @{ Label = 'Release policy module'; Path = (Join-Path $script:BundleRoot 'ops\scripts\release\release_policy.ps1'); Type = 'Leaf' },
    @{ Label = 'Desktop local API launcher'; Path = (Join-Path $script:BundleRoot 'apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat'); Type = 'Leaf' },
    @{ Label = 'Environment verifier'; Path = $verifier; Type = 'Leaf' },
    @{ Label = 'Config template'; Path = (Join-Path $pipelineRoot 'config\MediaPipeline_config_template.psd1'); Type = 'Leaf' },
    @{ Label = 'Default config profile'; Path = (Join-Path $pipelineRoot 'config\profiles\Default.psd1'); Type = 'Leaf' },
    @{ Label = 'ASS to SRT helper'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\pipeline\ass_to_srt_cli.py'); Type = 'Leaf' },
    @{ Label = 'Application DTO compatibility exports'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto.py'); Type = 'Leaf' },
    @{ Label = 'Application DTO base helpers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_base.py'); Type = 'Leaf' },
    @{ Label = 'Application command DTOs'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_commands.py'); Type = 'Leaf' },
    @{ Label = 'Application inventory DTOs'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_inventory.py'); Type = 'Leaf' },
    @{ Label = 'Application status DTOs'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_status.py'); Type = 'Leaf' },
    @{ Label = 'Application workspace DTOs'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_workspaces.py'); Type = 'Leaf' },
    @{ Label = 'Application facade'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade audit mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\audit\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade completed mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\completed\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade completed open mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\completed\open_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade diagnostics mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\diagnostics\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade failures mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\failures\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance backfill mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\backfill_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance commands mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\commands_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade maintenance release mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\release_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade pending-publish mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\publish\pending_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\preflight_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process audit launch mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\audit_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process control mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\control_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process guard mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\guard_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process pipeline launch mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\pipeline_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process rerun launch mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\rerun_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade process schedule mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\schedule_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade queue mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\queue\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade rename mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\rename\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade sample validation mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\sample_validation\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application sample validation policy'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\sample_validation\policy.py'); Type = 'Leaf' },
    @{ Label = 'Application facade schedule mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\schedule\facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings helpers mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_helpers_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings patch mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\orchestration\settings_patch_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings patch candidate mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_patch_candidate_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application facade settings risk mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_risk_facade.py'); Type = 'Leaf' },
    @{ Label = 'Application settings risk policy'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\settings_risk_policy.py'); Type = 'Leaf' },
    @{ Label = 'Application status policy'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\observability\status_policy.py'); Type = 'Leaf' },
    @{ Label = 'Application facade utilities mixin'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\application\utilities.py'); Type = 'Leaf' },
    @{ Label = 'Local API command handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\command_handlers.py'); Type = 'Leaf' },
    @{ Label = 'Local API command result helpers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\command_results.py'); Type = 'Leaf' },
    @{ Label = 'Local API file command handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_files.py'); Type = 'Leaf' },
    @{ Label = 'Local API maintenance command handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_maintenance.py'); Type = 'Leaf' },
    @{ Label = 'Local API process command handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_process.py'); Type = 'Leaf' },
    @{ Label = 'Local API rename command handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_rename.py'); Type = 'Leaf' },
    @{ Label = 'Local API sample validation command handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_sample_validation.py'); Type = 'Leaf' },
    @{ Label = 'Local API settings command handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_settings.py'); Type = 'Leaf' },
    @{ Label = 'Local API command journal'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\command_journal.py'); Type = 'Leaf' },
    @{ Label = 'Local API command journal policy'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\command_journal_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API command route contract'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_command.py'); Type = 'Leaf' },
    @{ Label = 'Local API route contract'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract.py'); Type = 'Leaf' },
    @{ Label = 'Local API route contract payload'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_payload.py'); Type = 'Leaf' },
    @{ Label = 'Local API read route contract'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_read.py'); Type = 'Leaf' },
    @{ Label = 'Local API route contract shared constants'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_shared.py'); Type = 'Leaf' },
    @{ Label = 'Local API HTTP handler'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\handler.py'); Type = 'Leaf' },
    @{ Label = 'Local API HTTP handler policy'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\handler_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API HTTP helpers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\http_helpers.py'); Type = 'Leaf' },
    @{ Label = 'Local API read payloads'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads.py'); Type = 'Leaf' },
    @{ Label = 'Local API read payload policy'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API inventory read payloads'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_inventory.py'); Type = 'Leaf' },
    @{ Label = 'Local API status read payloads'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_status.py'); Type = 'Leaf' },
    @{ Label = 'Local API workspace read payloads'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_workspace.py'); Type = 'Leaf' },
    @{ Label = 'Local API route handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes.py'); Type = 'Leaf' },
    @{ Label = 'Local API command route handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes_command.py'); Type = 'Leaf' },
    @{ Label = 'Local API read route handlers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes_read.py'); Type = 'Leaf' },
    @{ Label = 'Local API route handler shared spec'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes_shared.py'); Type = 'Leaf' },
    @{ Label = 'Local API static file helpers'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\static_files.py'); Type = 'Leaf' },
    @{ Label = 'Local API static file policy'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\static_files_policy.py'); Type = 'Leaf' },
    @{ Label = 'Local API server'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\server.py'); Type = 'Leaf' },
    @{ Label = 'Headless local API bootstrap helper'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\backend_bootstrap.py'); Type = 'Leaf' },
    @{ Label = 'Headless local API entrypoint'; Path = (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\local_api_main.py'); Type = 'Leaf' },
    @{ Label = 'Web prototype index'; Path = (Join-Path $script:BundleRoot 'apps\desktop\webview\static\index.html'); Type = 'Leaf' },
    @{ Label = 'Web prototype script'; Path = (Join-Path $script:BundleRoot 'apps\desktop\webview\static\assets\app.js'); Type = 'Leaf' },
    @{ Label = 'Web prototype styles'; Path = (Join-Path $script:BundleRoot 'apps\desktop\webview\static\assets\styles.css'); Type = 'Leaf' },
    @{ Label = 'Tauri shell package'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\package.json'); Type = 'Leaf' },
    @{ Label = 'Tauri shell package lock'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\package-lock.json'); Type = 'Leaf' },
    @{ Label = 'Tauri shell preview launcher'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell prereq checker'; Path = $tauriPrereqs; Type = 'Leaf' },
    @{ Label = 'Tauri shell build checker'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\Test-TauriShell-Build.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell launch checker'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\Test-TauriShell-Launch.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell PG-3 report helper'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\New-TauriShell-PG3CleanMachineReport.ps1'); Type = 'Leaf' },
    @{ Label = 'Tauri shell config'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\src-tauri\tauri.conf.json'); Type = 'Leaf' },
    @{ Label = 'Tauri shell Cargo manifest'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\src-tauri\Cargo.toml'); Type = 'Leaf' },
    @{ Label = 'Tauri shell Cargo lock'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\src-tauri\Cargo.lock'); Type = 'Leaf' },
    @{ Label = 'Tauri shell Windows icon'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\src-tauri\icons\icon.ico'); Type = 'Leaf' },
    @{ Label = 'Tauri shell launcher source'; Path = (Join-Path $script:BundleRoot 'apps\desktop\tauri\src-tauri\src\lib.rs'); Type = 'Leaf' }
)) {
    $entryRequired = $true
    if ($entry.ContainsKey('Required')) {
        $entryRequired = [bool]$entry.Required
    }
    if (Test-Path -LiteralPath $entry.Path -PathType $entry.Type) {
        Write-Ok "$($entry.Label): $($entry.Path)"
    } elseif ($entryRequired) {
        Write-Fail "$($entry.Label) missing: $($entry.Path)"
        $script:Failed = $true
    } else {
        Write-Warn "$($entry.Label) skipped; optional test file is not present in this package: $($entry.Path)"
    }
}

Test-ReleaseManifestHygiene -ManifestPath $releaseManifest
Test-ReleaseContentPrivacy -ManifestPath $releaseManifest
Test-ReleaseVersionConsistency
Invoke-DeployablePackageAcceptance -ManifestPath $releaseManifest
Test-ReleaseCustomRenameFilterRetention
Test-WebStaticAssetReferences -StaticRoot (Join-Path $script:BundleRoot 'apps\desktop\webview\static')
Test-ApiBrowserLauncherTokenPolicy

Write-Section 'Parser Checks'
$parseFiles = @(
    (Join-Path $script:BundleRoot 'ops\scripts\dev\verify-env.ps1'),
    (Join-Path $script:BundleRoot 'ops\scripts\release\build.ps1'),
    (Join-Path $script:BundleRoot 'ops\scripts\release\test.ps1'),
    (Join-Path $script:BundleRoot 'ops\scripts\operator\New-RealMediaValidationWorksheet.ps1'),
    (Join-Path $script:BundleRoot 'apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1'),
    (Join-Path $script:BundleRoot 'apps\desktop\tauri\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1'),
    (Join-Path $script:BundleRoot 'apps\desktop\tauri\Test-TauriShell-Prereqs.ps1'),
    (Join-Path $script:BundleRoot 'apps\desktop\tauri\Test-TauriShell-Build.ps1'),
    (Join-Path $script:BundleRoot 'apps\desktop\tauri\Test-TauriShell-Launch.ps1'),
    (Join-Path $script:BundleRoot 'apps\desktop\tauri\New-TauriShell-PG3CleanMachineReport.ps1'),
    (Join-Path $pipelineRoot 'entrypoints\Setup-MediaPipeline.ps1'),
    (Join-Path $pipelineRoot 'entrypoints\MediaPipeline.ps1'),
    (Join-Path $pipelineRoot 'entrypoints\Audit-MediaLibrary.ps1'),
    (Join-Path $pipelineRoot 'entrypoints\Invoke-RerunCsv.ps1'),
    (Join-Path $pipelineRoot 'entrypoints\Backfill-CompletedManifest.ps1')
)
$moduleRoot = Join-Path $pipelineRoot 'engine'
if (Test-Path -LiteralPath $moduleRoot -PathType Container) {
    $parseFiles += @(Get-ChildItem -LiteralPath $moduleRoot -Filter '*.ps1' -File -Recurse | ForEach-Object { $_.FullName })
}

foreach ($file in @($parseFiles)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
    try {
        Test-PowerShellParse -Path $file
    } catch {
        Write-Fail $_.Exception.Message
        $script:Failed = $true
    }
}
if (-not $script:Failed) {
    Write-Ok 'Core PowerShell scripts parse cleanly.'
}

Write-Section 'Python Syntax Checks'
$pythonSyntaxFiles = @(
    (Join-Path $script:BundleRoot 'src\mediapipeline\pipeline\ass_to_srt_cli.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_base.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_commands.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_inventory.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_status.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\dto_workspaces.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\audit\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\completed\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\completed\open_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\diagnostics\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\failures\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\backfill_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\commands_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\maintenance\release_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\publish\pending_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\preflight_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\audit_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\control_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\guard_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\pipeline_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\rerun_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\processes\schedule_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\queue\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\rename\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\schedule\facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_helpers_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\orchestration\settings_patch_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_patch_candidate_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\config\settings_risk_facade.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\application\settings_risk_policy.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\observability\status_policy.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\application\utilities.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\command_handlers.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\command_results.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_files.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_maintenance.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_process.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_rename.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\core\api\commands_settings.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\command_journal.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\command_journal_policy.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_command.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_payload.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_read.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\contract_shared.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\handler.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\handler_policy.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\http_helpers.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_policy.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_inventory.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_status.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\read_payloads_workspace.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes_command.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes_read.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\routes_shared.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\static_files.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\static_files_policy.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\api\server.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\backend_bootstrap.py'),
    (Join-Path $script:BundleRoot 'src\mediapipeline\desktop\local_api_main.py')
)
$desktopPackageRoot = Join-Path $script:BundleRoot 'src\mediapipeline\desktop'
if (Test-Path -LiteralPath $desktopPackageRoot -PathType Container) {
    $pythonSyntaxFiles += @(
        Get-ChildItem -LiteralPath $desktopPackageRoot -Filter '*.py' -File -Recurse |
            ForEach-Object { $_.FullName }
    )
}
$corePackageRoot = Join-Path $script:BundleRoot 'src\mediapipeline\core'
if (Test-Path -LiteralPath $corePackageRoot -PathType Container) {
    $pythonSyntaxFiles += @(
        Get-ChildItem -LiteralPath $corePackageRoot -Filter '*.py' -File -Recurse |
            ForEach-Object { $_.FullName }
    )
}
$pipelinePackageRoot = Join-Path $script:BundleRoot 'src\mediapipeline\pipeline'
if (Test-Path -LiteralPath $pipelinePackageRoot -PathType Container) {
    $pythonSyntaxFiles += @(
        Get-ChildItem -LiteralPath $pipelinePackageRoot -Filter '*.py' -File -Recurse |
            ForEach-Object { $_.FullName }
    )
}
$pythonSyntaxFiles = @($pythonSyntaxFiles | Sort-Object -Unique)
$script:Python = Join-Path $script:BundleRoot 'apps\desktop\runtime\Python\python.exe'
$pythonForSyntax = $script:Python
if (-not (Test-Path -LiteralPath $pythonForSyntax -PathType Leaf)) {
    Write-Fail "Bundled desktop Python missing for syntax checks: $pythonForSyntax"
    $script:Failed = $true
} else {
    $existingPythonSyntaxFiles = @($pythonSyntaxFiles | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    $pythonSyntaxCode = @'
import ast
import pathlib
import sys

failed = False
for raw in sys.stdin.read().splitlines():
    raw = raw.strip()
    if not raw:
        continue
    path = pathlib.Path(raw)
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        failed = True
    except OSError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        failed = True
raise SystemExit(1 if failed else 0)
'@
    $existingPythonSyntaxFiles | & $pythonForSyntax -c $pythonSyntaxCode
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'Core Python syntax checks failed.'
        $script:Failed = $true
    } else {
        Write-Ok 'Core Python files parse cleanly.'
    }
}

Write-Section 'Python Unit Tests'
foreach ($suite in @(
    @{ Label = 'desktop Python'; Path = 'tests\python\desktop' },
    @{ Label = 'core Python'; Path = 'tests\python\core' },
    @{ Label = 'tooling Python'; Path = 'tests\python\tooling' }
)) {
    Invoke-PythonUnittestDiscovery -Label $suite.Label -RelativePath $suite.Path -Required:([bool]$RequireTests)
}
Invoke-PythonPytestStyleTests -Required:([bool]$RequireTests)

Write-Section 'Generated and Tooling Guards'
# Some audit checks compare generated artifacts against the FULL source tree, and the Python lint gate
# checks both src and tests. A shipped release package intentionally strips parts of that tree (tests, dev
# docs), and is a frozen snapshot taken from a possibly-in-flight working tree, so source-tree-only checks
# cannot be guaranteed against it. In a release package (release_manifest.json present) they run as advisory
# warnings; the checks that validate the shipped code/contracts/boundaries themselves stay required.
# Outside a package (source/CI) every check remains required.
$inReleasePackage = Test-Path -LiteralPath $releaseManifest -PathType Leaf
$auditCheckManifest = $null
if (-not (Test-Path -LiteralPath $script:Python -PathType Leaf)) {
    Write-Fail "Audit check manifest requires bundled desktop Python: $script:Python"
    $script:Failed = $true
} else {
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $script:BundleRoot 'src'
        Push-Location -LiteralPath $script:BundleRoot
        $manifestOutput = & $script:Python -m mediapipeline.tools.dev.audit_checks emit release-self-test 2>&1 | ForEach-Object { [string]$_ }
        $manifestExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
        $env:PYTHONPATH = $previousPythonPath
    }

    if ($manifestExitCode -ne 0) {
        Write-Fail "Audit check manifest could not be loaded (exit $manifestExitCode)."
        $script:Failed = $true
        $manifestOutput | Select-Object -Last 40 | ForEach-Object { Write-Host $_ }
    } else {
        try {
            $auditCheckManifest = ($manifestOutput -join "`n") | ConvertFrom-Json
        } catch {
            Write-Fail "Audit check manifest emitted invalid JSON: $($_.Exception.Message)"
            $script:Failed = $true
        }
    }

}



if ($auditCheckManifest) {
    foreach ($check in @($auditCheckManifest.checks)) {
        $arguments = @()
        if ($check.arguments) {
            $arguments = @($check.arguments | ForEach-Object { [string]$_ })
        }
        $checkRequired = -not ([bool]$check.source_tree_only -and $inReleasePackage)
        Invoke-PythonModuleCheck -Label ([string]$check.label) -Module ([string]$check.module) -Arguments $arguments -Required:$checkRequired
    }
}

Write-Section 'Environment'
$environmentVerifierArgs = @('-AllowMissingConfig')
if ($inReleasePackage) {
    $environmentVerifierArgs += '-ReleasePackageVerification'
}
Invoke-ReleaseScriptCheck -Label 'environment verifier' -ScriptPath $verifier -Arguments $environmentVerifierArgs -Required -TimeoutSeconds 300

Write-Section 'Tauri Preview Gate'
Invoke-ReleaseScriptCheck -Label 'Tauri shell preview prerequisites' -ScriptPath $tauriPrereqs -Required -ShowWarningsOnSuccess -TimeoutSeconds 120

Write-Section 'Regression Gates'
$testsPresent = Test-Path -LiteralPath $testsRoot -PathType Container
if (-not $testsPresent) {
    if ($RequireTests) {
        Write-Fail "Tests are required but missing: $testsRoot"
        $script:Failed = $true
    } else {
        Record-ReleaseGateSkip "Pipeline tests are not present in this package. Build with -IncludeTests for the full release gate."
    }
} else {
    Invoke-ReleaseScriptCheck -Label 'release package policy checks' -ScriptPath $releasePolicyUnit -Required:([bool]$RequireTests) -TimeoutSeconds 120
    Invoke-ReleaseScriptCheck -Label 'current WebView reliability checks' -ScriptPath $webviewReliability -Required:([bool]$RequireTests) -TimeoutSeconds 600

    if ($SkipToolIntegration) {
        Record-ReleaseGateSkip 'Tool integration checks skipped by request.' -Required:([bool]$RequireTests)
    } else {
        Invoke-ReleaseScriptCheck -Label 'tool integration checks' -ScriptPath $toolIntegration -Required:([bool]$RequireTests) -FailOnSkipOutput:([bool]$RequireTests) -TimeoutSeconds 600
    }

    if ($SkipEndToEndSmoke) {
        Record-ReleaseGateSkip 'End-to-end smoke checks skipped by request.' -Required:([bool]$RequireTests)
    } else {
        Invoke-ReleaseScriptCheck -Label 'end-to-end smoke checks' -ScriptPath $endToEndSmoke -Required:([bool]$RequireTests) -FailOnSkipOutput:([bool]$RequireTests) -TimeoutSeconds 900
    }
}

Write-Section 'Summary'
if ($RequireTests) {
    Write-Ok 'Required test gate mode: enabled (-RequireTests).'
} else {
    Write-Warn 'Required test gate mode: disabled; source/dev convenience skips can be reported.'
}
if (Test-Path -LiteralPath $releaseManifest -PathType Leaf) {
    Write-Ok 'Release manifest present; package hygiene checks ran in package mode.'
} else {
    Write-Warn 'Release manifest absent; source/dev-only manifest hygiene mode.'
}
if ($script:SkippedGates.Count -gt 0) {
    Write-Warn ("Skipped or downshifted validation gates: {0}" -f ($script:SkippedGates -join ' | '))
} else {
    Write-Ok 'No validation gates were skipped.'
}
if ($script:Failed) {
    Write-Fail 'Release self-test failed.'
    exit 1
}

Write-Ok 'Release self-test passed.'
