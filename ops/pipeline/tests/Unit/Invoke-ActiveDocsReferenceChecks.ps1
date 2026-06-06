[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Active docs reference checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)

$versionPathPrefix = 'V' + '5'
$movedDocs = [ordered]@{
    'docs/API_ROUTE_INVENTORY.md' = 'docs/inventories/API_ROUTE_INVENTORY.md'
    'docs/COMMAND_OWNERSHIP_MATRIX.md' = 'docs/inventories/COMMAND_OWNERSHIP_MATRIX.md'
    'docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md' = 'docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md'
    'docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md' = 'docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md'
    'docs/FAILURE_TRIAGE_WORKSHEET.md' = 'docs/operator/FAILURE_TRIAGE_WORKSHEET.md'
    'docs/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md' = 'docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md'
    'docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md' = 'docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md'
    'docs/LOG_ARTIFACT_CATALOG.md' = 'docs/inventories/LOG_ARTIFACT_CATALOG.md'
    'docs/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md' = 'docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md'
    'docs/NETWORK_UX_IMPROVEMENTS.md' = 'docs/ARCHIVED_MD_INDEX.md'
    'docs/NO_TOUCH_BOUNDARY_REGISTER.md' = 'docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md'
    'docs/OPERATOR_GLOSSARY.md' = 'docs/operator/OPERATOR_GLOSSARY.md'
    'docs/POWERSHELL_HOST_EXPECTATIONS.md' = 'docs/operator/POWERSHELL_HOST_EXPECTATIONS.md'
    'docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md' = 'docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md'
    'docs/RUNTIME_ARTIFACT_INVENTORY.md' = 'docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md'
    'docs/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md' = 'docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md'
    'docs/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md' = 'docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md'
    'docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md' = 'docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md'
    'docs/SETTINGS_KEY_OWNERSHIP_MAP.md' = 'docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md'
    'docs/SETTINGS_RAW_KEY_TRIAGE.md' = 'docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md'
    'docs/SMOKE_TEST_INVENTORY.md' = 'docs/inventories/SMOKE_TEST_INVENTORY.md'
    'docs/STATE_FILE_SCHEMA_REFERENCE.md' = 'docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md'
    'docs/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md' = 'docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md'
    'docs/TAURI_WEBVIEW_PARITY_MATRIX.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/docs/architecture/TAURI_WEBVIEW_PARITY_MATRIX.md'
    'docs/TERMINOLOGY_CONSISTENCY_GUIDE.md' = 'docs/operator/TERMINOLOGY_CONSISTENCY_GUIDE.md'
    'docs/TEST_COVERAGE_MATRIX.md' = 'docs/testing/TEST_COVERAGE_MATRIX.md'
    'docs/UI_IMPROVEMENT_CHECKLIST.md' = 'docs/ARCHIVED_MD_INDEX.md'
    "docs/$($versionPathPrefix)_TAURI_TRANSITION_CURRENT_PLAN.md" = 'docs/ARCHIVED_MD_INDEX.md'
    "docs/$($versionPathPrefix)_TRANSITION_STATUS_BOARD.md" = 'docs/ARCHIVED_MD_INDEX.md'
    'docs/VALIDATION_LADDER_RUNBOOK.md' = 'docs/testing/VALIDATION_LADDER_RUNBOOK.md'
    'docs/WEBVIEW_DOM_ID_INVENTORY.md' = 'docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md'
    'docs/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md' = 'docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md'
    'docs/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md' = 'docs/operator/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md'
    'docs/WEBVIEW_SMOKE_RESULT_TEMPLATE.md' = 'docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md'
    'docs/WEBVIEW_SMOKE_TEST_CATALOG.md' = 'docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md'
    'docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md' = 'docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md'
    'docs/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md' = 'docs/testing/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md'
    'docs/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md' = 'docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md'
    'docs/BROWSER_SMOKE_TEST_RUNBOOK.md' = 'docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md'
    'docs/COMMAND_HISTORY_CONSISTENCY_AUDIT.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/COMMAND_HISTORY_CONSISTENCY_AUDIT.md'
    'docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md'
    'docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/FRONTEND_MODULE_SIZE_COHESION_REPORT.md'
    'docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md'
    'docs/RELEASE_PACKAGE_ADMIN_INVENTORY.md' = 'docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md'
    'docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md'
    'docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md' = 'docs/operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md'
    "docs/$($versionPathPrefix)_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md" = "docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/$($versionPathPrefix)_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md"
    'docs/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md'
    'docs/proposals/GOD_FILE_SPLIT_WAVE6_PLAN.md' = 'docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-checklists/GOD_FILE_SPLIT_WAVE6_PLAN.md'
}

$missingTargets = [System.Collections.Generic.List[string]]::new()
foreach ($target in $movedDocs.Values) {
    if ([string]$target -like 'docs/archive/docs-housekeeping/*') { continue }
    $targetPath = Join-Path $repoRoot ($target -replace '/', '\')
    if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
        $missingTargets.Add($target) | Out-Null
    }
}
if ($missingTargets.Count -gt 0) {
    throw "Mapped active-doc target paths are missing: $($missingTargets -join ', ')"
}

$files = @(
    Get-ChildItem -Path (Join-Path $repoRoot 'Docs') -Recurse -File -Include '*.md' |
        Where-Object {
            $_.FullName -notmatch '\\docs\\archive\\' -and
            $_.FullName -notmatch '\\docs\\REMEDIATION_CHANGELOG\.md$'
        }
    Get-ChildItem -Path (Join-Path $repoRoot 'apps\desktop\tauri\*') -File -Include '*.md', 'README*' -ErrorAction SilentlyContinue
    Get-ChildItem -Path (Join-Path $repoRoot '*') -File -Include '*.md', 'README*' -ErrorAction SilentlyContinue
) | Where-Object { $null -ne $_ }

$stale = [System.Collections.Generic.List[string]]::new()
$staleHousekeepingRoots = [System.Collections.Generic.List[string]]::new()
$staleHandoffPaths = [System.Collections.Generic.List[string]]::new()
$staleRemovedShellReferences = [System.Collections.Generic.List[string]]::new()
$handoffPathRestrictedRelatives = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    'docs\CURRENT_PROJECT_STATE.md',
    'docs\ACTIVE_FIX_CHECKLIST.md',
    "docs\active-plans\$($versionPathPrefix)_TRANSITION_STATUS_BOARD.md",
    'docs\architecture\DEPLOYABILITY_CHECKLIST.md',
    "$($versionPathPrefix)_TRANSITION_REVIEW_FIX_CHECKLIST.md"
) | ForEach-Object { $handoffPathRestrictedRelatives.Add($_) | Out-Null }
$archivedHousekeepingDocs = @(
    'HOUSEKEEPING_AUDIT_REPORT.md',
    'HOUSEKEEPING_EXECUTION_CHECKLIST.md'
)
$removedShellScanExclusions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    'docs\DOC_TOUCH_LOG.md',
    'CODE_REVIEW_WEBVIEW_TAURI_AUDIT.md',
    'DOCS_HOUSEKEEPING_AUDIT.md',
    'DOCS_HOUSEKEEPING_MOVE_PLAN_BLOCKED.md',
    'DOCS_HOUSEKEEPING_POST_MOVE_REPORT.md'
) | ForEach-Object { $removedShellScanExclusions.Add($_) | Out-Null }
$removedShellPattern = 'CustomTkinter|customtkinter|tkinter|\bTk\b|Tk-owned|Tk fallback|Tk replacement|replace Tk|Tk as|Tk app|Tk shell|Tk main'
foreach ($file in $files) {
    $text = Get-Content -LiteralPath $file.FullName -Raw
    foreach ($old in $movedDocs.Keys) {
        foreach ($variant in @($old, ($old -replace '/', '\'))) {
            if ($text.Contains($variant)) {
                $relative = $file.FullName.Substring($repoRoot.Length + 1)
                $stale.Add("${relative}: $variant") | Out-Null
            }
        }
    }

    $relative = $file.FullName.Substring($repoRoot.Length + 1)
    $lineNumber = 0
    foreach ($line in ($text -split "`r?`n")) {
        $lineNumber += 1
        foreach ($docName in $archivedHousekeepingDocs) {
            if ($relative -eq 'docs\ARCHIVED_MD_INDEX.md') { continue }
            $allowedHousekeepingArchive = "(((Docs[\\/])?archive[\\/]admin-audits[\\/])|(delete-candidates[\\/]Docs[\\/]archive[\\/]admin-audits[\\/]))$([regex]::Escape($docName))"
            if ($line.Contains($docName) -and $line -notmatch $allowedHousekeepingArchive) {
                $staleHousekeepingRoots.Add("${relative}:${lineNumber}: $docName") | Out-Null
            }
        }

        if ($handoffPathRestrictedRelatives.Contains($relative) -and $line -match 'C:\\Users\\lmmye\\.*CurrentHandoff') {
            $staleHandoffPaths.Add("${relative}:${lineNumber}: absolute current-handoff path") | Out-Null
        }

        if (-not $removedShellScanExclusions.Contains($relative) -and $line -match $removedShellPattern) {
            $staleRemovedShellReferences.Add("${relative}:${lineNumber}: removed legacy desktop-shell wording") | Out-Null
        }
    }
}

if ($stale.Count -gt 0) {
    throw "Active docs still reference moved root docs:`n$($stale -join "`n")"
}

if ($staleHousekeepingRoots.Count -gt 0) {
    throw "Active docs still reference root-level housekeeping report names instead of archived paths:`n$($staleHousekeepingRoots -join "`n")"
}

if ($staleHandoffPaths.Count -gt 0) {
    throw "High-level active docs still embed absolute local current-handoff paths:`n$($staleHandoffPaths -join "`n")"
}

if ($staleRemovedShellReferences.Count -gt 0) {
    throw "Active docs still reference the removed legacy desktop-shell framework by its old UI name:`n$($staleRemovedShellReferences -join "`n")"
}

Write-Host 'Active docs reference checks passed.'
