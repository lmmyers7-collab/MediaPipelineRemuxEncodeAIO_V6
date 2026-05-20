[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "V6 WebView reliability checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$pipelineRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$projectRoot = Split-Path -Parent $pipelineRoot

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Leaf {
    param(
        [string]$Path,
        [string]$Label
    )
    Assert-True (Test-Path -LiteralPath $Path -PathType Leaf) "$Label is missing: $Path"
}

function Assert-Container {
    param(
        [string]$Path,
        [string]$Label
    )
    Assert-True (Test-Path -LiteralPath $Path -PathType Container) "$Label is missing: $Path"
}

function Assert-Absent {
    param(
        [string]$Path,
        [string]$Label
    )
    Assert-True (-not (Test-Path -LiteralPath $Path)) "$Label should not exist in V6: $Path"
}

function Read-Text {
    param([string]$Path)
    Assert-Leaf -Path $Path -Label "Text file"
    return (Get-Content -LiteralPath $Path -Raw)
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

function Assert-TreeNotMatch {
    param(
        [string]$Path,
        [string]$Pattern,
        [string[]]$Extensions = @('.py', '.ps1', '.js', '.html'),
        [string[]]$ExcludeLeaf = @()
    )
    $matches = @(
        Get-ChildItem -LiteralPath $Path -Recurse -File |
            Where-Object {
                $Extensions -contains $_.Extension -and
                $ExcludeLeaf -notcontains $_.Name -and
                $_.FullName -notmatch '\\Runtime\\|\\PowerShell-7\.6\.0-win-x64\\|\\Tools\\'
            } |
            Select-String -Pattern $Pattern -ErrorAction Stop
    )
    if ($matches.Count -gt 0) {
        $preview = @($matches | Select-Object -First 8 | ForEach-Object {
            $relative = $_.Path.Substring($projectRoot.Length + 1)
            "${relative}:$($_.LineNumber): $($_.Line.Trim())"
        }) -join "`n"
        throw "Unexpected active V6 source match for pattern '$Pattern':`n$preview"
    }
}

$desktopRoot = Join-Path $projectRoot 'DesktopApp'
$packageRoot = Join-Path $desktopRoot 'mediapipeline_desktop_app'
$apiRoot = Join-Path $packageRoot 'api'
$staticRoot = Join-Path $packageRoot 'ui_web\static'
$assetsRoot = Join-Path $staticRoot 'assets'
$tauriRoot = Join-Path $desktopRoot 'tauri_shell'
$tauriSrcRoot = Join-Path $tauriRoot 'src-tauri\src'
$nativeCleanupCheck = Join-Path $pipelineRoot 'Tests\Unit\Invoke-NativeProcessCleanupChecks.ps1'
$runtimeStateHygieneCheck = Join-Path $pipelineRoot 'Tests\Unit\Invoke-RuntimeStateHygieneChecks.ps1'
$sidecarWriteSafetyCheck = Join-Path $pipelineRoot 'Tests\Unit\Invoke-SidecarWriteSafetyChecks.ps1'

Assert-Container -Path $packageRoot -Label 'V6 Python package'
Assert-Container -Path $apiRoot -Label 'Local API package'
Assert-Container -Path $staticRoot -Label 'WebView static root'
Assert-Container -Path $assetsRoot -Label 'WebView asset root'
Assert-Container -Path $tauriSrcRoot -Label 'Tauri shell source root'

Assert-Absent -Path (Join-Path $packageRoot 'app.py') -Label 'Removed desktop shell entrypoint'
Assert-Absent -Path (Join-Path $packageRoot 'app_bootstrap.py') -Label 'Removed desktop shell bootstrap'
Assert-Absent -Path (Join-Path $packageRoot 'controllers') -Label 'Removed desktop controllers package'
Assert-Absent -Path (Join-Path $packageRoot 'views') -Label 'Removed desktop views package'

$requiredLeaves = @(
    'DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1',
    'DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat',
    'Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat',
    'DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1',
    'DesktopApp\mediapipeline_desktop_app\local_api_main.py',
    'DesktopApp\mediapipeline_desktop_app\backend_bootstrap.py',
    'DesktopApp\mediapipeline_desktop_app\api\server.py',
    'DesktopApp\mediapipeline_desktop_app\api\static_files_policy.py',
    'DesktopApp\mediapipeline_desktop_app\api\routes_command.py',
    'DesktopApp\mediapipeline_desktop_app\api\contract_command.py',
    'DesktopApp\mediapipeline_desktop_app\api\command_payloads.py',
    'DesktopApp\mediapipeline_desktop_app\api\command_payloads_process.py',
    'DesktopApp\mediapipeline_desktop_app\api\command_payloads_rename.py',
    'DesktopApp\mediapipeline_desktop_app\api\command_payloads_settings.py',
    'DesktopApp\mediapipeline_desktop_app\api\command_payloads_schedule.py',
    'DesktopApp\mediapipeline_desktop_app\application\schedule_stop_watcher.py',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\apiClient.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\renameView.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js',
    'DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\networkView.js',
    'DesktopApp\tauri_shell\src-tauri\src\lib.rs',
    'DesktopApp\tauri_shell\src-tauri\src\backend_process.rs',
    'DesktopApp\tauri_shell\src-tauri\src\backend_contract.rs',
    'DesktopApp\tauri_shell\src-tauri\src\close_readiness.rs',
    'Build-MediaPipelineRemuxEncodeAIO-Release.ps1',
    'Test-MediaPipelineRemuxEncodeAIO-Release.ps1'
)
foreach ($relative in $requiredLeaves) {
    Assert-Leaf -Path (Join-Path $projectRoot $relative) -Label $relative
}

foreach ($path in @(
    (Join-Path $projectRoot 'Build-MediaPipelineRemuxEncodeAIO-Release.ps1'),
    (Join-Path $projectRoot 'Test-MediaPipelineRemuxEncodeAIO-Release.ps1'),
    (Join-Path $projectRoot 'New-RealMediaValidationWorksheet.ps1')
)) {
    Test-PowerShellParse -Path $path
}
Get-ChildItem -LiteralPath (Join-Path $pipelineRoot 'Modules') -Filter '*.ps1' -File |
    ForEach-Object { Test-PowerShellParse -Path $_.FullName }

Assert-Leaf -Path $nativeCleanupCheck -Label 'Native process cleanup unit gate'
& $nativeCleanupCheck
Assert-Leaf -Path $runtimeStateHygieneCheck -Label 'Runtime state hygiene unit gate'
& $runtimeStateHygieneCheck
Assert-Leaf -Path $sidecarWriteSafetyCheck -Label 'Sidecar write safety unit gate'
& $sidecarWriteSafetyCheck

$serverText = Read-Text (Join-Path $apiRoot 'server.py')
$handlerText = Read-Text (Join-Path $apiRoot 'handler.py')
$httpHelpersText = Read-Text (Join-Path $apiRoot 'http_helpers.py')
$routesCommandText = Read-Text (Join-Path $apiRoot 'routes_command.py')
$contractCommandText = Read-Text (Join-Path $apiRoot 'contract_command.py')
$contractPayloadText = Read-Text (Join-Path $apiRoot 'contract_payload.py')
$commandPayloadsRenameText = Read-Text (Join-Path $apiRoot 'command_payloads_rename.py')
$staticFilesText = Read-Text (Join-Path $apiRoot 'static_files.py')
$staticFilesPolicyText = Read-Text (Join-Path $apiRoot 'static_files_policy.py')
$indexText = Read-Text (Join-Path $staticRoot 'index.html')
$apiClientText = Read-Text (Join-Path $assetsRoot 'apiClient.js')
$appJsText = Read-Text (Join-Path $assetsRoot 'app.js')
$apiBrowserLauncherText = Read-Text (Join-Path $projectRoot 'DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1')
$facadeRenameText = Read-Text (Join-Path $packageRoot 'application\facade_rename.py')
$facadeRenamePolicyText = Read-Text (Join-Path $packageRoot 'application\facade_rename_policy.py')
$renameApplyRunnerText = Read-Text (Join-Path $packageRoot 'service_rename_apply_runner.py')
$tauriLibText = Read-Text (Join-Path $tauriSrcRoot 'lib.rs')
$tauriBackendProcessText = Read-Text (Join-Path $tauriSrcRoot 'backend_process.rs')
$tauriBackendContractText = Read-Text (Join-Path $tauriSrcRoot 'backend_contract.rs')
$scheduleWatcherText = Read-Text (Join-Path $packageRoot 'application\schedule_stop_watcher.py')
$ffmpegProgressText = Read-Text (Join-Path $pipelineRoot 'Modules\FfmpegProgress.ps1')
$nativeText = Read-Text (Join-Path $pipelineRoot 'Modules\Native.ps1')
$sidecarText = Read-Text (Join-Path $pipelineRoot 'Modules\Sidecar.ps1')
$releasePolicyText = Read-Text (Join-Path $pipelineRoot 'Modules\ReleasePolicy.ps1')
$reliabilityWrapperText = Read-Text (Join-Path $pipelineRoot 'Tests\Invoke-ReliabilityRegressionChecks.ps1')
$repoHygieneText = Read-Text (Join-Path $pipelineRoot 'Tests\Unit\Invoke-RepoHygieneChecks.ps1')
$legacyReliabilityPath = Join-Path $pipelineRoot 'Tests\Legacy\Invoke-LegacyDesktopReliabilityRegressionChecks.ps1'
$releaseBuilderText = Read-Text (Join-Path $projectRoot 'Build-MediaPipelineRemuxEncodeAIO-Release.ps1')
$releaseVerifierText = Read-Text (Join-Path $projectRoot 'Test-MediaPipelineRemuxEncodeAIO-Release.ps1')
$worksheetHelperText = Read-Text (Join-Path $projectRoot 'New-RealMediaValidationWorksheet.ps1')

Assert-True ($serverText -match 'Read and command API\s+routes require a per-run token') "LocalApiServer docstring must describe the current token-protected read/command API surface."
Assert-True ($serverText -match 'CommandJournal' -and $serverText -match 'require_token') "LocalApiServer must keep token and command-journal wiring."
Assert-True ($httpHelpersText -notmatch 'query_value\(query,\s*"token"' -and $contractPayloadText -match 'not URL query parameters') "Local API auth must avoid query-string tokens and document header-only token use."
Assert-True ($httpHelpersText -match 'def discard_request_body' -and $handlerText -match 'discard_request_body' -and $handlerText -match 'if not owner\._request_authorized\(self\.headers, query\):\s+self\._discard_request_body\(\)\s+self\._send_json\(unauthorized_payload\(\), status=401\)') "Unauthorized POSTs must discard the raw body before sending 401 so token failures do not reset local clients or parse command JSON."
Assert-True ($staticFilesText -match 'resolve_asset_path' -and $staticFilesText -match 'render_static_includes' -and $staticFilesPolicyText -match 'surface\.casefold\(\) != "tauri"' -and $staticFilesPolicyText -match 'tauri-initialization-script' -and $indexText -match '__MEDIA_PIPELINE_BOOTSTRAP__' -and $indexText -match 'MEDIA_PIPELINE_TAURI_BOOTSTRAP' -and $tauriLibText -match 'tauri_bootstrap_initialization_script\(backend\.token\(\)\)' -and $tauriLibText -match '\.initialization_script\(initialization_script\)' -and $tauriBackendContractText -match 'Backend WebView index leaked the bearer token') "Static WebView assets must be rendered through backend helpers while Tauri injects the token outside public index HTML."
Assert-True ($apiClientText -match 'Authorization' -and $apiClientText -match 'Bearer' -and $apiClientText -match 'window\.apiGet' -and $apiClientText -match 'window\.apiPost') "WebView API client must attach the per-run token and expose shared request helpers."
Assert-True ($apiBrowserLauncherText -match '\[switch\]\$NoTokenDevMode' -and $apiBrowserLauncherText -match 'Token auth: enabled \(browser receives a per-run bootstrap token\)' -and $apiBrowserLauncherText -match 'Token auth: DISABLED by explicit -NoTokenDevMode' -and $apiBrowserLauncherText -match 'if \(\$NoTokenDevMode\)[\s\S]+?\$apiArgs \+= ''--no-token''') "API browser launcher must keep token auth enabled by default and require an explicit dev-only no-token switch."
Assert-True ($appJsText -match '/api/backend/shutdown' -and $appJsText -match 'Backend authority') "WebView close/shutdown path must call the backend-owned shutdown API and label backend authority."
Assert-True ($commandPayloadsRenameText -match 'backend_owned_keys = \{"_configured_media_roots", "_rename_undo_manifest_root"\}' -and $commandPayloadsRenameText -match 'rename_undo_manifest_root_from_resolved' -and $facadeRenameText -match 'undo_manifest_root=rename_undo_manifest_root_from_request\(request\)' -and $facadeRenameText -match 'rename_apply_outside_configured_roots_result' -and $facadeRenamePolicyText -match 'Path\(state_root\) / "RenameUndo"' -and $facadeRenamePolicyText -match 'allow_outside_configured_roots' -and $renameApplyRunnerText -match 'undo_manifest_root: Path \| None = None') "Rename apply must strip spoofable backend authority keys, require outside-root confirmation, and write undo manifests under the backend-resolved runtime state root when LocalBase/State is available."

foreach ($route in @(
    '/api/pipeline/start',
    '/api/pipeline/control',
    '/api/backend/shutdown',
    '/api/settings/preview-patch',
    '/api/settings/save-patch',
    '/api/schedule/preview',
    '/api/schedule/save',
    '/api/rename/preview',
    '/api/rename/apply',
    '/api/pending-publish/recovery-plan',
    '/api/sample-validation/append'
)) {
    Assert-True ($routesCommandText.Contains($route)) "Command route handler is missing active V6 route: $route"
    Assert-True ($contractCommandText.Contains($route)) "Command route contract is missing active V6 route: $route"
}
foreach ($effect in @('process-launch', 'control-flag-write', 'backend-lifecycle', 'config-write', 'app-state-write', 'filesystem-mutation', 'validation-log-write')) {
    Assert-True ($contractCommandText.Contains($effect)) "Command route contract is missing effect classification: $effect"
}

Assert-True ($tauriLibText -match 'start_backend' -and $tauriLibText -match 'WebviewUrl::External' -and $tauriLibText -match 'confirm_close_if_needed' -and $tauriLibText -match 'shutdown_backend_state') "Tauri shell must own backend process startup, WebView attachment, close readiness, and shutdown handoff."
Assert-True ($tauriBackendProcessText -match 'redact_bootstrap_stdout' -and $tauriBackendProcessText -match 'redact_json_string_field' -and $tauriBackendProcessText -match 'bounded_text\(&redacted_bootstrap_stdout, MAX_BOOTSTRAP_STDOUT_CHARS\)' -and $tauriBackendProcessText -match 'push_bootstrap_stdout_context') "Tauri backend startup diagnostics must redact token-like stdout before logging or surfacing bootstrap context."
Assert-True ($scheduleWatcherText -match '_generation' -and $scheduleWatcherText -match '"generation": self\.generation' -and $scheduleWatcherText -match 'generation != self\._generation') "Schedule-stop watcher must expose a generation id and guard against stale watcher threads overwriting current state."
Assert-True ($ffmpegProgressText -notmatch '\$lineTask' -and $ffmpegProgressText -match 'Map the user-facing priority string before emitting tool_started') "FFmpeg progress runner must not reference stale lineTask polling and must log effective priority in tool_started."
Assert-True ($nativeText -match 'Stop-NativeProcessTree -Process \$proc -Label \$Label' -and $nativeText -match 'Native process cleanup failed after start/run error') "Native process runner must clean up already-started children after start/run exceptions."
Assert-True ($sidecarText -match 'Move-SidecarTempIntoPlace' -and $sidecarText -match '\[System\.IO\.File\]::Move\(\$TempPath,\s*\$DestinationPath,\s*\$true\)' -and $sidecarText -notmatch 'Remove-Item\s+-LiteralPath\s+\$sidecar\s+-Force') "Sidecar Replace fallback must use overwrite move without explicitly deleting the current sidecar."
Assert-True ($worksheetHelperText -match 'Launch surface' -and $worksheetHelperText -match 'V6 workspace path' -and $worksheetHelperText -notmatch 'Tk supported') "Real-media worksheet helper must use V6 launch-surface wording."

Assert-True ($releaseBuilderText -match 'ReleasePolicy\.ps1' -and $releaseBuilderText -match 'Get-MediaPipelineReleaseExclusionReason' -and $releaseBuilderText -match 'Get-MediaPipelineReleasePolicyManifest') "Release builder must use the shared release policy module for exclusions and manifest metadata."
Assert-True ($releaseVerifierText -match 'Invoke-V6WebViewReliabilityChecks\.ps1') "Release self-test must run the active V6 WebView reliability gate."
Assert-True ($releaseVerifierText -match 'Import-MediaPipelineReleasePolicy' -and $releaseVerifierText -match 'Get-MediaPipelineReleaseHygieneRules') "Release self-test must verify hygiene through the shared release policy module."
Assert-True ($releaseVerifierText -notmatch 'legacyDesktopEntryPoint') "Release self-test must not branch on removed desktop-shell entrypoints."
Assert-True ($releaseVerifierText -notmatch 'Legacy desktop reliability regression checks skipped') "Release self-test must not skip reliability checks just because the removed desktop shell is absent."
Assert-True ($releasePolicyText -match 'mediapipeline_release_policy\.v1' -and $releasePolicyText -match 'CodexVerification\\\*' -and $releasePolicyText -match 'LocalBase\\\*' -and $releasePolicyText -match 'Docs\\archive\\docs-housekeeping\\\*') "Release policy must exclude local verification, runtime state, and docs housekeeping quarantine artifacts."
Assert-True ($releasePolicyText -match '\*_AUDIT\.md' -and $releasePolicyText -match '\*_REPORT\.md') "Release policy must exclude generated root audit/report documents by pattern."
Assert-Leaf -Path $legacyReliabilityPath -Label 'Archived legacy desktop-shell reliability checks'
Assert-True ($reliabilityWrapperText -match 'Invoke-V6WebViewReliabilityChecks\.ps1' -and $reliabilityWrapperText -match 'RunLegacyDesktopChecks' -and $reliabilityWrapperText -match 'Legacy\\Invoke-LegacyDesktopReliabilityRegressionChecks\.ps1' -and $reliabilityWrapperText -match 'Invoke-RepoHygieneChecks\.ps1') "Reliability regression compatibility entrypoint must run active V6 checks by default, include non-stale repo hygiene, and keep legacy desktop-shell checks behind an explicit switch."
Assert-True ($reliabilityWrapperText -notmatch 'app\.py|app_bootstrap\.py|controllers\\|legacyDesktopEntryPoint') "Reliability regression compatibility entrypoint must not depend on removed desktop-shell files."
Assert-True ($repoHygieneText -match 'IncludeBuildArtifacts' -and $repoHygieneText -match 'if \(\$IncludeBuildArtifacts\)' -and $repoHygieneText -match 'src-tauri\\target') "Repo hygiene must not fail the default V6 reliability gate just because ignored Tauri build artifacts exist; strict build-artifact scanning must be opt-in."

Assert-TreeNotMatch -Path $packageRoot -Pattern '\bTk\b|CustomTkinter|customtkinter|fallback_tk|Tk app|Tk shell|Tk Schedule'
Assert-TreeNotMatch -Path $assetsRoot -Pattern '\bfetch\s*\(' -Extensions @('.js') -ExcludeLeaf @('apiClient.js')

Write-Host 'V6 WebView reliability checks passed.'
