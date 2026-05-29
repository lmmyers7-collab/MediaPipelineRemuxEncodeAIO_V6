[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Pending publish ownership checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot
$moduleMap = Join-Path $repoRoot 'Docs\architecture\MODULE_MAP.md'
$fixtureInventory = Join-Path $repoRoot 'Docs\inventories\PENDING_PUBLISH_FIXTURE_INVENTORY.md'
$serviceTest = Join-Path $repoRoot 'DesktopApp\tests\test_pending_publish_service.py'

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

function Assert-PowerShellParses {
    param([string] $Path)

    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($Path, [ref] $tokens, [ref] $errors) | Out-Null
    if ($errors -and $errors.Count -gt 0) {
        $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber):$($_.Message)" }) -join '; '
        throw "PowerShell parser errors in ${Path}: $details"
    }
}

$requiredModuleFiles = [ordered]@{
    'publish_completion.ps1'      = 'engine\publish\publish_completion.ps1'
    'publish_partial.ps1'         = 'engine\publish\publish_partial.ps1'
    'publish_sidecars.ps1'        = 'engine\publish\publish_sidecars.ps1'
    'pending_manifest_store.ps1'  = 'engine\publish\pending_manifest_store.ps1'
    'pending_transactions.ps1'    = 'engine\publish\pending_transactions.ps1'
    'pending_push.ps1'            = 'engine\publish\pending_push.ps1'
    'pending_publish_index.ps1'   = 'engine\publish\pending_publish_index.ps1'
}

$ownershipDocPaths = @{
    'publish_completion.ps1'      = 'engine/publish/publish_completion.ps1'
    'publish_partial.ps1'         = 'engine/publish/publish_partial.ps1'
    'publish_sidecars.ps1'        = 'engine/publish/publish_sidecars.ps1'
    'pending_manifest_store.ps1'  = 'engine/publish/pending_manifest_store.ps1'
    'pending_transactions.ps1'    = 'engine/publish/pending_transactions.ps1'
    'pending_push.ps1'            = 'engine/publish/pending_push.ps1'
    'pending_publish_index.ps1'   = 'engine/publish/pending_publish_index.ps1'
}

foreach ($name in $requiredModuleFiles.Keys) {
    $path = Join-Path $repoRoot $requiredModuleFiles[$name]
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "Missing pending-publish ownership module: $($requiredModuleFiles[$name])"
    Assert-PowerShellParses -Path $path
}

Assert-True (Test-Path -LiteralPath $moduleMap -PathType Leaf) 'MODULE_MAP.md is missing.'
Assert-True (Test-Path -LiteralPath $fixtureInventory -PathType Leaf) 'PENDING_PUBLISH_FIXTURE_INVENTORY.md is missing.'
Assert-True (Test-Path -LiteralPath $serviceTest -PathType Leaf) 'test_pending_publish_service.py is missing.'

$moduleMapText = Get-Content -LiteralPath $moduleMap -Raw
$fixtureText = Get-Content -LiteralPath $fixtureInventory -Raw
$serviceTestText = Get-Content -LiteralPath $serviceTest -Raw

Assert-Contains $moduleMapText 'Pending Publish Ownership Boundary' 'MODULE_MAP.md must document the pending-publish ownership boundary.'
Assert-Contains $moduleMapText 'Parked output is media plus sidecars' 'MODULE_MAP.md must state parked output is media plus sidecars.'
Assert-Contains $moduleMapText 'must not infer drain safety or move parked payloads' 'MODULE_MAP.md must keep WebView/Tauri out of pending drain safety decisions.'
foreach ($name in $requiredModuleFiles.Keys) {
    Assert-Contains $moduleMapText $ownershipDocPaths[$name] "MODULE_MAP.md must list ownership for $name."
}
Assert-Contains $moduleMapText 'app/publish/pending_*.py' 'MODULE_MAP.md must list pending-publish service ownership.'
Assert-Contains $moduleMapText 'Durable media-plus-sidecar park transaction' 'PendingTransactions ownership must include durable media-plus-sidecar transactions.'
Assert-Contains $moduleMapText 'low-space/unknown-space deferred parking decision' 'PublishCompletion ownership must include low-space deferred parking.'

Assert-Contains $fixtureText 'Module Ownership Guardrail' 'Pending fixture inventory must keep the ownership guardrail section.'
Assert-Contains $fixtureText 'must not infer drain safety or mutate parked payloads' 'Pending fixture inventory must keep frontend drain-safety boundary language.'
Assert-Contains $fixtureText 'Parked media plus tx3g SRT sidecars are visible as one media-plus-sidecars unit before drain' 'Pending fixture inventory must track media-plus-sidecar scan coverage.'
Assert-Contains $serviceTestText 'test_parked_manifest_reports_media_plus_sidecar_evidence' 'Pending publish service tests must keep parked media-plus-sidecar row coverage.'

Write-Host 'Pending publish ownership checks passed.'
