[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Runtime state hygiene checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot
$desktopRoot = Join-Path $repoRoot 'DesktopApp'
$legacyEncodeHistory = Join-Path $desktopRoot 'encode_speed_history.json'
$legacyAppState = Join-Path $desktopRoot 'MediaPipelineRemuxEncodeAIO_DesktopApp.state.json'
$appStateMigrationPath = Join-Path $repoRoot 'app\storage\state_migration.py'
$pathResolutionRunnerPath = Join-Path $repoRoot 'app\paths\resolution_runner.py'
$appStateMigrationTestPath = Join-Path $desktopRoot 'tests\test_service_path_state_migration.py'
$pathResolutionRunnerTestPath = Join-Path $desktopRoot 'tests\test_service_path_resolution_runner.py'
$runtimeInventoryPath = Join-Path $repoRoot 'Docs\inventories\RUNTIME_ARTIFACT_INVENTORY.md'
$gitignorePath = Join-Path $repoRoot '.gitignore'
$releaseManifestPath = Join-Path $repoRoot 'release_manifest.json'
$releasePolicyPath = Join-Path $repoRoot 'scripts\release\release_policy.ps1'

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Contains {
    param(
        [string] $Text,
        [string] $Needle,
        [string] $Message
    )
    Assert-True ($Text.Contains($Needle)) $Message
}

Assert-True (-not (Test-Path -LiteralPath $legacyEncodeHistory -PathType Leaf)) 'DesktopApp\encode_speed_history.json is legacy runtime state; it must not live in the app source root.'
Assert-True (-not (Test-Path -LiteralPath $legacyAppState -PathType Leaf)) 'DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.state.json is legacy runtime state; it must not live in the app source root.'
Assert-True (Test-Path -LiteralPath $appStateMigrationPath -PathType Leaf) 'app/storage/state_migration.py is missing.'
Assert-True (Test-Path -LiteralPath $pathResolutionRunnerPath -PathType Leaf) 'app\paths\resolution_runner.py is missing.'
Assert-True (Test-Path -LiteralPath $appStateMigrationTestPath -PathType Leaf) 'test_service_path_state_migration.py is missing.'
Assert-True (Test-Path -LiteralPath $pathResolutionRunnerTestPath -PathType Leaf) 'test_service_path_resolution_runner.py is missing.'
Assert-True (Test-Path -LiteralPath $runtimeInventoryPath -PathType Leaf) 'RUNTIME_ARTIFACT_INVENTORY.md is missing.'
$isReleaseBundle = Test-Path -LiteralPath $releaseManifestPath -PathType Leaf
if (-not $isReleaseBundle) {
    Assert-True (Test-Path -LiteralPath $gitignorePath -PathType Leaf) '.gitignore is missing.'
} else {
    Assert-True (Test-Path -LiteralPath $releasePolicyPath -PathType Leaf) 'release_policy.ps1 is missing from release bundle.'
}

$appStateMigrationText = Get-Content -LiteralPath $appStateMigrationPath -Raw
$pathResolutionRunnerText = Get-Content -LiteralPath $pathResolutionRunnerPath -Raw
$appStateMigrationTestText = Get-Content -LiteralPath $appStateMigrationTestPath -Raw
$pathResolutionRunnerTestText = Get-Content -LiteralPath $pathResolutionRunnerTestPath -Raw
$runtimeInventoryText = Get-Content -LiteralPath $runtimeInventoryPath -Raw
$gitignoreText = if (Test-Path -LiteralPath $gitignorePath -PathType Leaf) {
    Get-Content -LiteralPath $gitignorePath -Raw
} else {
    ''
}
$releasePolicyText = if (Test-Path -LiteralPath $releasePolicyPath -PathType Leaf) {
    Get-Content -LiteralPath $releasePolicyPath -Raw
} else {
    ''
}

Assert-Contains $appStateMigrationText 'def app_state_path_for_state_root' 'App state migration must expose a state-root path helper.'
Assert-Contains $appStateMigrationText 'return state_root / "App" / APP_STATE_NAME' 'App state must live under LocalBase\State\App.'
Assert-Contains $appStateMigrationText 'legacy_path = app_root / APP_STATE_NAME' 'App state migration must recognize the legacy app-root state file.'
Assert-Contains $appStateMigrationText 'shutil.copy2' 'App state migration must copy legacy state rather than move/delete it.'

Assert-Contains $pathResolutionRunnerText 'resolved.state_root = service._state_root_for_local_base(resolved.local_base)' 'Path resolution must derive state_root from LocalBase.'
Assert-Contains $pathResolutionRunnerText 'resolved.app_state_path = app_state_path_for_state_root(resolved.state_root)' 'Path resolution must bind app_state_path to State\App.'
Assert-Contains $pathResolutionRunnerText 'completed_state = resolved.state_root / "Completed"' 'Path resolution must derive the completed state folder from LocalBase\State.'
Assert-Contains $pathResolutionRunnerText 'completed_state / "completed_jobs.jsonl"' 'Completed manifest must live under LocalBase\State\Completed.'

Assert-Contains $appStateMigrationTestText 'test_migrate_app_state_path_copies_legacy_state_when_preferred_missing' 'App state legacy migration test is missing.'
Assert-Contains $appStateMigrationTestText 'LocalBase" / "State" / "App" / APP_STATE_NAME' 'App state tests must assert State\App placement.'
Assert-Contains $pathResolutionRunnerTestText 'test_resolve_paths_with_local_base_populates_versioned_state_layout' 'Path resolution state-root test is missing.'
Assert-Contains $pathResolutionRunnerTestText 'local_base / "State" / "App" / APP_STATE_NAME' 'Path resolution tests must assert app state under State\App.'
Assert-Contains $pathResolutionRunnerTestText 'local_base / "State" / "Completed" / "completed_jobs.jsonl"' 'Path resolution tests must assert completed manifest under State\Completed.'

Assert-Contains $runtimeInventoryText 'Desktop app state' 'Runtime artifact inventory must document desktop app state.'
Assert-Contains $runtimeInventoryText 'State\App\MediaPipelineRemuxEncodeAIO_DesktopApp.state.json' 'Runtime artifact inventory must document app state under LocalBase\State\App.'
Assert-Contains $runtimeInventoryText 'State\Completed\completed_jobs.jsonl' 'Runtime artifact inventory must document completed jobs JSONL under LocalBase\State\Completed.'
if ($gitignoreText) {
    Assert-Contains $gitignoreText '/DesktopApp/encode_speed_history.json' '.gitignore must reject legacy app-root encode-speed history.'
    Assert-Contains $gitignoreText 'DesktopApp/*.state.json' '.gitignore must reject legacy app-root desktop state files.'
} else {
    Assert-Contains $releasePolicyText "DesktopApp\encode_speed_history.json" 'Release policy must reject legacy app-root encode-speed history.'
    Assert-Contains $releasePolicyText "DesktopApp\*.state.json" 'Release policy must reject legacy app-root desktop state files.'
}

Write-Host 'Runtime state hygiene checks passed.'
