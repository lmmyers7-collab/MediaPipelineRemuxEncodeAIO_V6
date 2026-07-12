[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Current WebView reliability checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$pipelineRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$projectRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)

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
    Assert-True (-not (Test-Path -LiteralPath $Path)) "$Label should not exist in the current layout: $Path"
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
        throw "Unexpected active source match for pattern '$Pattern':`n$preview"
    }
}

$desktopRoot = Join-Path $projectRoot 'apps\desktop'
$packageRoot = Join-Path $projectRoot 'src\mediapipeline\desktop'
$apiRoot = Join-Path $packageRoot 'api'
$staticRoot = Join-Path $desktopRoot 'webview\static'
$assetsRoot = Join-Path $staticRoot 'assets'
$tauriRoot = Join-Path $desktopRoot 'tauri'
$tauriSrcRoot = Join-Path $tauriRoot 'src-tauri\src'
$nativeCleanupCheck = Join-Path $pipelineRoot 'tests\Unit\Invoke-NativeProcessCleanupChecks.ps1'
$runtimeStateHygieneCheck = Join-Path $pipelineRoot 'tests\Unit\Invoke-RuntimeStateHygieneChecks.ps1'
$sidecarWriteSafetyCheck = Join-Path $pipelineRoot 'tests\Unit\Invoke-SidecarWriteSafetyChecks.ps1'

Assert-Container -Path $packageRoot -Label 'Python package'
Assert-Container -Path $apiRoot -Label 'Local API package'
Assert-Container -Path $staticRoot -Label 'WebView static root'
Assert-Container -Path $assetsRoot -Label 'WebView asset root'
Assert-Container -Path $tauriSrcRoot -Label 'Tauri shell source root'

Assert-Absent -Path (Join-Path $packageRoot 'app.py') -Label 'Removed desktop shell entrypoint'
Assert-Absent -Path (Join-Path $packageRoot 'app_bootstrap.py') -Label 'Removed desktop shell bootstrap'
Assert-Absent -Path (Join-Path $packageRoot 'controllers') -Label 'Removed desktop controllers package'
Assert-Absent -Path (Join-Path $packageRoot 'views') -Label 'Removed desktop views package'

$requiredLeaves = @(
    'apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1',
    'apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat',
    'ops\scripts\dev\start-tauri-preview.bat',
    'apps\desktop\tauri\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1',
    'src\mediapipeline\desktop\local_api_main.py',
    'src\mediapipeline\desktop\backend_bootstrap.py',
    'src\mediapipeline\desktop\api\server.py',
    'src\mediapipeline\desktop\api\static_files_policy.py',
    'src\mediapipeline\desktop\api\routes_command.py',
    'src\mediapipeline\desktop\api\contract_command.py',
    'src\mediapipeline\core\api\commands.py',
    'src\mediapipeline\core\api\command_handlers.py',
    'src\mediapipeline\core\api\commands_process.py',
    'src\mediapipeline\core\api\commands_rename.py',
    'src\mediapipeline\core\api\commands_settings.py',
    'src\mediapipeline\core\api\commands_schedule.py',
    'src\mediapipeline\core\schedule\stop_watcher.py',
    'src\mediapipeline\desktop\application\schedule_stop_watcher.py',
    'apps\desktop\webview\static\index.html',
    'apps\desktop\webview\static\assets\apiClient.js',
    'apps\desktop\webview\static\assets\app.js',
    'apps\desktop\webview\static\assets\launchView.js',
    'apps\desktop\webview\static\assets\queueView.js',
    'apps\desktop\webview\static\assets\pendingPublishView.js',
    'apps\desktop\webview\static\assets\renameView.js',
    'apps\desktop\webview\static\assets\settingsView.js',
    'apps\desktop\webview\static\assets\scheduleView.js',
    'apps\desktop\webview\static\assets\networkView.js',
    'apps\desktop\tauri\src-tauri\src\lib.rs',
    'apps\desktop\tauri\src-tauri\src\backend_process.rs',
    'apps\desktop\tauri\src-tauri\src\backend_contract.rs',
    'apps\desktop\tauri\src-tauri\src\backend_contract\web_shell.rs',
    'apps\desktop\tauri\src-tauri\src\close_readiness.rs',
    'ops\scripts\release\build.ps1',
    'ops\scripts\release\test.ps1'
)
foreach ($relative in $requiredLeaves) {
    Assert-Leaf -Path (Join-Path $projectRoot $relative) -Label $relative
}

foreach ($path in @(
    (Join-Path $projectRoot 'ops\scripts\release\build.ps1'),
    (Join-Path $projectRoot 'ops\scripts\release\test.ps1'),
    (Join-Path $projectRoot 'ops\scripts\operator\New-RealMediaValidationWorksheet.ps1')
)) {
    Test-PowerShellParse -Path $path
}
Get-ChildItem -LiteralPath (Join-Path $pipelineRoot 'engine') -Filter '*.ps1' -File -Recurse |
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
$contractCommandText = (@(
        Get-ChildItem -LiteralPath $apiRoot -Filter 'contract_command*.py' -File |
            Sort-Object -Property Name |
            ForEach-Object { Read-Text $_.FullName }
    )) -join "`n"
$contractPayloadText = Read-Text (Join-Path $apiRoot 'contract_payload.py')
$appApiRoot = Join-Path $projectRoot 'src\mediapipeline\core\api'
$appApiCommandsText = Read-Text (Join-Path $appApiRoot 'commands.py')
$commandRenameText = Read-Text (Join-Path $appApiRoot 'commands_rename.py')
$staticFilesText = Read-Text (Join-Path $apiRoot 'static_files.py')
$staticFilesPolicyText = Read-Text (Join-Path $apiRoot 'static_files_policy.py')
$indexText = Read-Text (Join-Path $staticRoot 'index.html')
$apiClientText = Read-Text (Join-Path $assetsRoot 'apiClient.js')
$appJsText = Read-Text (Join-Path $assetsRoot 'app.js')
$apiBrowserLauncherText = Read-Text (Join-Path $projectRoot 'apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1')
$facadeRenameText = Read-Text (Join-Path $projectRoot 'src\mediapipeline\core\rename\facade.py')
$facadeRenamePolicyText = Read-Text (Join-Path $projectRoot 'src\mediapipeline\core\rename\policy.py')
$facadeRenamePathAuthorityText = Read-Text (Join-Path $projectRoot 'src\mediapipeline\core\rename\path_authority.py')
$renameApplyRunnerText = Read-Text (Join-Path $projectRoot 'src\mediapipeline\core\rename\apply_runner.py')
$tauriLibText = Read-Text (Join-Path $tauriSrcRoot 'lib.rs')
$tauriBackendProcessText = Read-Text (Join-Path $tauriSrcRoot 'backend_process.rs')
$tauriBackendContractText = Read-Text (Join-Path $tauriSrcRoot 'backend_contract.rs')
$tauriBackendWebShellText = Read-Text (Join-Path $tauriSrcRoot 'backend_contract\web_shell.rs')
$scheduleWatcherText = Read-Text (Join-Path $projectRoot 'src\mediapipeline\core\schedule\stop_watcher.py')
$ffmpegProgressText = Read-Text (Join-Path $projectRoot 'ops\pipeline\engine\process\ffmpeg_progress.ps1')
$nativeText = Read-Text (Join-Path $projectRoot 'ops\pipeline\engine\shared\native.ps1')
$remuxText = (@(
        'entrypoints\MediaPipeline\remux.ps1',
        'engine\process\remux_context.ps1',
        'engine\process\remux_preflight.ps1',
        'engine\process\remux_subtitle_plan.ps1',
        'engine\process\remux_ffmpeg_av_stage.ps1',
        'engine\process\remux_mkvmerge_args.ps1',
        'engine\process\remux_mkvmerge_stage.ps1',
        'engine\process\remux_verification.ps1',
        'engine\process\remux_publish.ps1',
        'engine\process\remux_orchestrator.ps1'
    ) | ForEach-Object {
        Read-Text (Join-Path $pipelineRoot $_)
    }) -join "`n"
$sidecarText = Read-Text (Join-Path $projectRoot 'ops\pipeline\engine\publish\sidecar.ps1')
$releasePolicyText = Read-Text (Join-Path $projectRoot 'ops\scripts\release\release_policy.ps1')
$reliabilityWrapperText = Read-Text (Join-Path $pipelineRoot 'tests\Invoke-ReliabilityRegressionChecks.ps1')
$toolIntegrationText = Read-Text (Join-Path $pipelineRoot 'tests\Invoke-ToolIntegrationChecks.ps1')
$endToEndSmokeText = Read-Text (Join-Path $pipelineRoot 'tests\Invoke-EndToEndSmokeChecks.ps1')
$repoHygieneText = Read-Text (Join-Path $pipelineRoot 'tests\Unit\Invoke-RepoHygieneChecks.ps1')
$legacyReliabilityPath = Join-Path $pipelineRoot 'tests\Legacy\Invoke-LegacyDesktopReliabilityRegressionChecks.ps1'
$releaseBuilderText = Read-Text (Join-Path $projectRoot 'ops\scripts\release\build.ps1')
$releaseVerifierText = (@(
        'test.ps1',
        'test_acceptance.ps1',
        'test_contracts.ps1',
        'test_policy.ps1',
        'test_support.ps1'
    ) | ForEach-Object {
        Read-Text (Join-Path $projectRoot "ops\scripts\release\$_")
    }) -join "`n"
$browserSmokeCommonText = Read-Text (Join-Path $projectRoot 'ops\scripts\smoke\webview_browser_smoke_common.ps1')
$worksheetHelperText = Read-Text (Join-Path $projectRoot 'ops\scripts\operator\New-RealMediaValidationWorksheet.ps1')
$auditChecksText = Read-Text (Join-Path $projectRoot 'src\mediapipeline\tools\dev\audit_checks.py')

Assert-True ($serverText -match 'Read and command API\s+routes require a per-run token') "LocalApiServer docstring must describe the current token-protected read/command API surface."
Assert-True ($serverText -match 'CommandJournal' -and $serverText -match 'require_token') "LocalApiServer must keep token and command-journal wiring."
Assert-True ($httpHelpersText -notmatch 'query_value\(query,\s*"token"' -and $contractPayloadText -match 'not URL query parameters') "Local API auth must avoid query-string tokens and document non-query token use."
Assert-True ($httpHelpersText -match 'def discard_request_body' -and $handlerText -match 'discard_request_body' -and $handlerText -match 'if not owner\._request_authorized\(self\.headers, query\):\s+self\._discard_request_body\(\)\s+self\._send_json\(unauthorized_payload\(\), status=401\)') "Unauthorized POSTs must discard the raw body before sending 401 so token failures do not reset local clients or parse command JSON."
Assert-True ($staticFilesText -match 'resolve_asset_path' -and $staticFilesText -match 'render_static_includes' -and $staticFilesPolicyText -match 'http-only-cookie' -and $staticFilesPolicyText -match 'tauri-initialization-script' -and $indexText -match '__MEDIA_PIPELINE_BOOTSTRAP__' -and $indexText -match 'media-pipeline-bootstrap' -and $httpHelpersText -match 'MediaPipelineAuth' -and $tauriLibText -match 'tauri_bootstrap_initialization_script\(\s*backend\.token\(\)\s*,\s*backend\.startup_warnings\(\)\s*\)' -and $tauriLibText -match '\.initialization_script\(initialization_script\)' -and $tauriBackendContractText -match 'web_shell::validate_web_shell\(backend_url, token\)' -and $tauriBackendWebShellText -match 'Backend WebView index leaked the bearer token') "Static WebView assets must be rendered through backend helpers while browser mode uses an HttpOnly cookie and Tauri injects the token outside public index HTML."
Assert-True ($apiClientText -match 'Authorization' -and $apiClientText -match 'Bearer' -and $apiClientText -match 'window\.apiGet' -and $apiClientText -match 'window\.apiPost') "WebView API client must attach the per-run token and expose shared request helpers."
Assert-True ($apiBrowserLauncherText -match '\[switch\]\$NoTokenDevMode' -and $apiBrowserLauncherText -match 'Token auth: enabled \(browser receives a same-origin HttpOnly auth cookie\)' -and $apiBrowserLauncherText -match 'Token auth: DISABLED by explicit -NoTokenDevMode' -and $apiBrowserLauncherText -match 'if \(\$NoTokenDevMode\)[\s\S]+?\$apiArgs \+= ''--no-token''') "API browser launcher must keep token auth enabled by default and require an explicit dev-only no-token switch."
Assert-True ($appJsText -match '/api/backend/shutdown' -and $appJsText -match 'Backend authority') "WebView close/shutdown path must call the backend-owned shutdown API and label backend authority."
Assert-True ($reliabilityWrapperText -match 'Unit\\Invoke-NamingSupportChecks\.ps1' -and $reliabilityWrapperText -match 'naming support checks') "Active reliability wrapper must include the focused naming support guard."
Assert-True ($commandRenameText -match 'backend_owned_keys\s*=\s*\{[\s\S]*"_configured_media_roots"[\s\S]*"_rename_undo_manifest_root"[\s\S]*\}' -and $commandRenameText -match 'rename_undo_manifest_root_from_resolved' -and $facadeRenameText -match 'undo_manifest_root=rename_undo_manifest_root_from_request\(request\)' -and $facadeRenameText -match 'rename_apply_outside_configured_roots_result' -and $facadeRenamePathAuthorityText -match 'Path\(state_root\) / "RenameUndo"' -and $facadeRenamePathAuthorityText -match 'allow_outside_configured_roots' -and $renameApplyRunnerText -match 'undo_manifest_root: Path \| None = None') "Rename apply must strip spoofable backend authority keys, require outside-root confirmation, and write undo manifests under the backend-resolved runtime state root when LocalBase/State is available."

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
    Assert-True ($routesCommandText.Contains($route) -or $appApiCommandsText.Contains($route)) "Command route registry/handler is missing active route: $route"
    Assert-True ($contractCommandText.Contains($route)) "Command route contract is missing active route: $route"
}
foreach ($effect in @('process-launch', 'control-flag-write', 'backend-lifecycle', 'config-write', 'app-state-write', 'filesystem-mutation', 'validation-log-write')) {
    Assert-True ($contractCommandText.Contains($effect)) "Command route contract is missing effect classification: $effect"
}

Assert-True ($tauriLibText -match 'start_backend' -and $tauriLibText -match 'WebviewUrl::External' -and $tauriLibText -match 'close_request_decision' -and $tauriLibText -match 'shutdown_backend_state' -and $tauriLibText -match 'BackendShutdownMode::SafeOnly' -and $tauriLibText -match 'BackendShutdownMode::ConfirmedForceActiveWork') "Tauri shell must own backend process startup, WebView attachment, close readiness, and shutdown handoff."
Assert-True ($tauriBackendProcessText -match 'redact_bootstrap_stdout' -and $tauriBackendProcessText -match 'redact_json_string_field' -and $tauriBackendProcessText -match 'bounded_text\(&redacted_bootstrap_stdout, MAX_BOOTSTRAP_STDOUT_CHARS\)' -and $tauriBackendProcessText -match 'push_bootstrap_stdout_context') "Tauri backend startup diagnostics must redact token-like stdout before logging or surfacing bootstrap context."
Assert-True ($scheduleWatcherText -match '_generation' -and $scheduleWatcherText -match '"generation": self\.generation' -and $scheduleWatcherText -match 'generation != self\._generation') "Schedule-stop watcher must expose a generation id and guard against stale watcher threads overwriting current state."
Assert-True ($ffmpegProgressText -notmatch '\$lineTask' -and $ffmpegProgressText -match 'Map the user-facing priority string before emitting tool_started') "FFmpeg progress runner must not reference stale lineTask polling and must log effective priority in tool_started."
Assert-True ($ffmpegProgressText -match '\$baseMkvmergeFailed\s*=\s*\(\[bool\]\$result\.TimedOut\s+-or\s+\[bool\]\$result\.Stopped\s+-or\s+\$exitCode -lt 0\s+-or\s+\$exitCode -ge 2\)' -and $ffmpegProgressText -match '\$mkvmergeWarning\s*=\s*\(-not \$baseMkvmergeFailed -and \$exitCode -eq 1\)' -and $ffmpegProgressText -match 'Get-MkvmergeWarningClassification' -and $ffmpegProgressText -match 'MKVMERGE_WARNINGS' -and $ffmpegProgressText -match 'MKVMERGE_WARNING_STREAM_LOSS' -and $ffmpegProgressText -match 'if \(-not \$mkvmergeFailed\)' -and $remuxText -match '\$mkvFailed\s*=\s*\(\[bool\]\$mkv\.TimedOut\s+-or\s+\[bool\]\$mkv\.Stopped\s+-or\s+\$mkvExitCode -lt 0\s+-or\s+\$mkvExitCode -ge 2\s+-or\s+\[bool\]\$mkv\.MkvmergeWarningBlocking\)' -and $remuxText -notmatch 'if \(\$mkv\.ExitCode -ge 2\)') "mkvmerge timeout/stop/negative exits and classified stream-loss warnings must fail, while benign exit 1 remains warning-success evidence."
Assert-True ($nativeText -match 'Stop-NativeProcessTree -Process \$proc -Label \$Label' -and $nativeText -match 'Native process cleanup failed after start/run error') "Native process runner must clean up already-started children after start/run exceptions."
Assert-True ($sidecarText -match 'Move-SidecarTempIntoPlace' -and $sidecarText -match '\[System\.IO\.File\]::Move\(\$TempPath,\s*\$DestinationPath,\s*\$true\)' -and $sidecarText -notmatch 'Remove-Item\s+-LiteralPath\s+\$sidecar\s+-Force') "Sidecar Replace fallback must use overwrite move without explicitly deleting the current sidecar."
Assert-True ($worksheetHelperText -match 'Launch surface' -and $worksheetHelperText -match 'Workspace path' -and $worksheetHelperText -notmatch 'Tk supported') "Real-media worksheet helper must use current launch-surface wording."

Assert-True ($releaseBuilderText -match 'release_policy\.ps1' -and $releaseBuilderText -match 'Get-MediaPipelineReleaseExclusionReason' -and $releaseBuilderText -match 'Get-MediaPipelineReleasePolicyManifest') "Release builder must use the shared release policy module for exclusions and manifest metadata."
Assert-True ($releaseBuilderText -match '\[switch\]\$AllowTestlessVerify' -and $releaseBuilderText -match 'Release verification requires -IncludeTests' -and $releaseBuilderText -match 'This is not release acceptance\.' -and $releaseBuilderText.Contains('$verifyArgs.Add(''-RequireTests'')')) "Release builder must make verified release packages run the required test gate unless an explicit dev-only testless bypass is used."
Assert-True ($releaseVerifierText -match 'Invoke-WebViewReliabilityChecks\.ps1') "Release self-test must run the active WebView reliability gate."
Assert-True ($releaseVerifierText -match 'tests\\python\\desktop' -and $releaseVerifierText -match 'tests\\python\\core' -and $releaseVerifierText -match 'tests\\python\\tooling') "Release self-test must run desktop, core, and tooling Python test suites when tests are required."
Assert-True ($releaseVerifierText -match 'mediapipeline\.tools\.dev\.audit_checks emit release-self-test' -and $releaseVerifierText -match '\$auditCheckManifest\.checks' -and $releaseVerifierText -match 'Invoke-PythonModuleCheck' -and $releaseVerifierText -match 'source_tree_only' -and $auditChecksText -match '"release-self-test"' -and $auditChecksText -match 'mediapipeline\.tools\.dev\.refresh_summaries' -and $auditChecksText -match 'mediapipeline\.tools\.dev\.generate_project_index' -and $auditChecksText -match 'mediapipeline\.tools\.dev\.generate_config_schema' -and $auditChecksText -match 'mediapipeline\.tools\.dev\.check_active_doc_references' -and $auditChecksText -match 'mediapipeline\.tools\.dev\.check_dependency_boundaries') "Release self-test must run package-safe generated-artifact, active-doc, schema, and dependency guardrails."
Assert-True ($releaseVerifierText -match 'Import-MediaPipelineReleasePolicy' -and $releaseVerifierText -match 'Get-MediaPipelineReleaseHygieneRules') "Release self-test must verify hygiene through the shared release policy module."
Assert-True ($releaseVerifierText -match 'Record-ReleaseGateSkip' -and $releaseVerifierText -match 'Tool integration checks skipped by request.'' -Required:\(\[bool\]\$RequireTests\)' -and $releaseVerifierText -match 'End-to-end smoke checks skipped by request.'' -Required:\(\[bool\]\$RequireTests\)' -and $releaseVerifierText -match 'FailOnSkipOutput:\(\[bool\]\$RequireTests\)' -and $releaseVerifierText -match 'Required test gate mode: enabled') "Release self-test must fail requested skips in -RequireTests mode and report skipped/downshifted gate evidence."
Assert-True ($releaseVerifierText -notmatch 'legacyDesktopEntryPoint') "Release self-test must not branch on removed desktop-shell entrypoints."
Assert-True ($releaseVerifierText -notmatch 'Legacy desktop reliability regression checks skipped') "Release self-test must not skip reliability checks just because the removed desktop shell is absent."
Assert-True ($toolIntegrationText -match 'runtime\\PowerShell-7\.6\.0-win-x64\\pwsh\.exe' -and $toolIntegrationText -match 'tools\\ffmpeg\\bin\\ffmpeg\.exe' -and $toolIntegrationText -match 'apps\\desktop\\runtime\\Python\\python\.exe' -and $toolIntegrationText -match 'src\\mediapipeline\\pipeline\\ass_to_srt_cli\.py' -and $toolIntegrationText -match 'throw \$missingMessage' -and $toolIntegrationText -match '\[switch\]\$AllowMissingTools') "Tool integration gate must use promoted runtime/tool/helper paths and fail on missing tools unless -AllowMissingTools is explicit."
Assert-True ($endToEndSmokeText -match 'tools\\ffmpeg\\bin\\ffmpeg\.exe' -and $endToEndSmokeText -match 'throw \$missingMessage' -and $endToEndSmokeText -match '\[switch\]\$AllowMissingTools') "End-to-end smoke gate must fail on missing bundled tools unless -AllowMissingTools is explicit."
Assert-True ($browserSmokeCommonText -match 'skipped=\\d\+' -and $browserSmokeCommonText -match 'AllowSkippedTests' -and $browserSmokeCommonText -match 'Install Node\.js and Chrome/Edge') "Shared WebView browser smoke runner must fail skipped unittest coverage unless -AllowSkippedTests is explicit."
Assert-True ($browserSmokeCommonText -match 'Using python from PATH for WebView browser smoke' -and $browserSmokeCommonText -match 'bundled Python runtimes were not found') "Shared WebView browser smoke runner must make PATH Python fallback prominent in release evidence."
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'ops\scripts\smoke') -Filter 'Test-WebViewBrowser*.ps1' -File |
    ForEach-Object {
        $wrapperText = Read-Text $_.FullName
        Assert-True ($wrapperText -match 'webview_browser_smoke_common\.ps1' -and $wrapperText -match 'Invoke-WebViewBrowserSmokeUnittest' -and $wrapperText -match '\[switch\]\$AllowSkippedTests' -and $wrapperText -notmatch 'skips cleanly when Chrome/Edge is not installed') "WebView browser smoke wrapper must use the shared no-skip runner: $($_.Name)"
    }
Assert-True ($releasePolicyText -match 'mediapipeline_release_policy\.v1' -and $releasePolicyText -match 'CodexVerification\\\*' -and $releasePolicyText -match 'LocalBase\\\*' -and $releasePolicyText -match 'docs\\archive\\docs-housekeeping\\\*') "Release policy must exclude local verification, runtime state, and docs housekeeping quarantine artifacts."
Assert-True ($releasePolicyText -match '\*_AUDIT\.md' -and $releasePolicyText -match '\*_REPORT\.md') "Release policy must exclude generated root audit/report documents by pattern."
Assert-Leaf -Path $legacyReliabilityPath -Label 'Archived legacy desktop-shell reliability checks'
Assert-True ($reliabilityWrapperText -match 'Invoke-WebViewReliabilityChecks\.ps1' -and $reliabilityWrapperText -match 'RunLegacyDesktopChecks' -and $reliabilityWrapperText -match 'Legacy\\Invoke-LegacyDesktopReliabilityRegressionChecks\.ps1' -and $reliabilityWrapperText -match 'Invoke-RepoHygieneChecks\.ps1') "Reliability regression compatibility entrypoint must run active checks by default, include non-stale repo hygiene, and keep legacy desktop-shell checks behind an explicit switch."
Assert-True ($reliabilityWrapperText -notmatch 'app\.py|app_bootstrap\.py|controllers\\|legacyDesktopEntryPoint') "Reliability regression compatibility entrypoint must not depend on removed desktop-shell files."
Assert-True ($repoHygieneText -match 'IncludeBuildArtifacts' -and $repoHygieneText -match 'if \(\$IncludeBuildArtifacts\)' -and $repoHygieneText -match 'src-tauri\\target') "Repo hygiene must not fail the default reliability gate just because ignored Tauri build artifacts exist; strict build-artifact scanning must be opt-in."

Assert-TreeNotMatch -Path $packageRoot -Pattern '\bTk\b|CustomTkinter|customtkinter|fallback_tk|Tk app|Tk shell|Tk Schedule'
Assert-TreeNotMatch -Path $assetsRoot -Pattern '\bfetch\s*\(' -Extensions @('.js') -ExcludeLeaf @('apiClient.js')

Write-Host 'Current WebView reliability checks passed.'
