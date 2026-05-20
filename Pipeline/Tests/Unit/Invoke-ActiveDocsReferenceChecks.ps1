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
$repoRoot = Split-Path -Parent $pipelineRoot

$movedDocs = [ordered]@{
    'Docs/API_ROUTE_INVENTORY.md' = 'Docs/inventories/API_ROUTE_INVENTORY.md'
    'Docs/COMMAND_OWNERSHIP_MATRIX.md' = 'Docs/inventories/COMMAND_OWNERSHIP_MATRIX.md'
    'Docs/COMPLETED_PENDING_FAILURE_PLAYBOOK.md' = 'Docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md'
    'Docs/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md' = 'Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md'
    'Docs/FAILURE_TRIAGE_WORKSHEET.md' = 'Docs/operator/FAILURE_TRIAGE_WORKSHEET.md'
    'Docs/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md' = 'Docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md'
    'Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md' = 'Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md'
    'Docs/LOG_ARTIFACT_CATALOG.md' = 'Docs/inventories/LOG_ARTIFACT_CATALOG.md'
    'Docs/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md' = 'Docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md'
    'Docs/NETWORK_UX_IMPROVEMENTS.md' = 'Docs/ARCHIVED_MD_INDEX.md'
    'Docs/NO_TOUCH_BOUNDARY_REGISTER.md' = 'Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md'
    'Docs/OPERATOR_GLOSSARY.md' = 'Docs/operator/OPERATOR_GLOSSARY.md'
    'Docs/POWERSHELL_HOST_EXPECTATIONS.md' = 'Docs/operator/POWERSHELL_HOST_EXPECTATIONS.md'
    'Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md' = 'Docs/sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md'
    'Docs/RUNTIME_ARTIFACT_INVENTORY.md' = 'Docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md'
    'Docs/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md' = 'Docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md'
    'Docs/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md' = 'Docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md'
    'Docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md' = 'Docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md'
    'Docs/SETTINGS_KEY_OWNERSHIP_MAP.md' = 'Docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md'
    'Docs/SETTINGS_RAW_KEY_TRIAGE.md' = 'Docs/architecture/SETTINGS_RAW_KEY_TRIAGE.md'
    'Docs/SMOKE_TEST_INVENTORY.md' = 'Docs/inventories/SMOKE_TEST_INVENTORY.md'
    'Docs/STATE_FILE_SCHEMA_REFERENCE.md' = 'Docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md'
    'Docs/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md' = 'Docs/architecture/TAURI_BACKEND_LIFECYCLE_BOUNDARY.md'
    'Docs/TAURI_WEBVIEW_PARITY_MATRIX.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/consolidated-after-extraction/Docs/architecture/TAURI_WEBVIEW_PARITY_MATRIX.md'
    'Docs/TERMINOLOGY_CONSISTENCY_GUIDE.md' = 'Docs/operator/TERMINOLOGY_CONSISTENCY_GUIDE.md'
    'Docs/TEST_COVERAGE_MATRIX.md' = 'Docs/testing/TEST_COVERAGE_MATRIX.md'
    'Docs/UI_IMPROVEMENT_CHECKLIST.md' = 'Docs/ARCHIVED_MD_INDEX.md'
    'Docs/V5_MIGRATION_RISK_REGISTER.md' = 'Docs/architecture/V5_MIGRATION_RISK_REGISTER.md'
    'Docs/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md' = 'Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md'
    'Docs/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md' = 'Docs/sample-validation/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md'
    'Docs/V5_TAURI_TRANSITION_CURRENT_PLAN.md' = 'Docs/ARCHIVED_MD_INDEX.md'
    'Docs/V5_TRANSITION_STATUS_BOARD.md' = 'Docs/ARCHIVED_MD_INDEX.md'
    'Docs/VALIDATION_LADDER_RUNBOOK.md' = 'Docs/testing/VALIDATION_LADDER_RUNBOOK.md'
    'Docs/WEBVIEW_DOM_ID_INVENTORY.md' = 'Docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md'
    'Docs/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md' = 'Docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md'
    'Docs/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md' = 'Docs/operator/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md'
    'Docs/WEBVIEW_SMOKE_RESULT_TEMPLATE.md' = 'Docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md'
    'Docs/WEBVIEW_SMOKE_TEST_CATALOG.md' = 'Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md'
    'Docs/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md' = 'Docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md'
    'Docs/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md' = 'Docs/testing/BROWSER_SMOKE_FAILURE_TRIAGE_CHEATSHEET.md'
    'Docs/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md' = 'Docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md'
    'Docs/BROWSER_SMOKE_TEST_RUNBOOK.md' = 'Docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md'
    'Docs/COMMAND_HISTORY_CONSISTENCY_AUDIT.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/COMMAND_HISTORY_CONSISTENCY_AUDIT.md'
    'Docs/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md'
    'Docs/FRONTEND_MODULE_SIZE_COHESION_REPORT.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/FRONTEND_MODULE_SIZE_COHESION_REPORT.md'
    'Docs/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE_REVIEW.md'
    'Docs/RELEASE_PACKAGE_ADMIN_INVENTORY.md' = 'Docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md'
    'Docs/WEBVIEW_APIPOST_MUTATION_REVIEW.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md'
    'Docs/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md' = 'Docs/operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md'
    'Docs/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md'
    'Docs/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/Docs/archive/old-ai-directives/CLAUDE_HANDOFF_TRANSITION_SUPPORT_20_TASKS.md'
    'Docs/proposals/GOD_FILE_SPLIT_WAVE6_PLAN.md' = 'Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-checklists/GOD_FILE_SPLIT_WAVE6_PLAN.md'
}

$missingTargets = [System.Collections.Generic.List[string]]::new()
foreach ($target in $movedDocs.Values) {
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
            $_.FullName -notmatch '\\Docs\\archive\\' -and
            $_.FullName -notmatch '\\Docs\\REMEDIATION_CHANGELOG\.md$'
        }
    Get-ChildItem -Path (Join-Path $repoRoot 'DesktopApp\tauri_shell\*') -File -Include '*.md', 'README*' -ErrorAction SilentlyContinue
    Get-ChildItem -Path (Join-Path $repoRoot '*') -File -Include '*.md', 'README*' -ErrorAction SilentlyContinue
) | Where-Object { $null -ne $_ }

$stale = [System.Collections.Generic.List[string]]::new()
$staleHousekeepingRoots = [System.Collections.Generic.List[string]]::new()
$staleHandoffPaths = [System.Collections.Generic.List[string]]::new()
$staleRemovedShellReferences = [System.Collections.Generic.List[string]]::new()
$handoffPathRestrictedRelatives = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    'Docs\CURRENT_PROJECT_STATE.md',
    'Docs\ACTIVE_FIX_CHECKLIST.md',
    'Docs\active-plans\V5_TRANSITION_STATUS_BOARD.md',
    'Docs\architecture\DEPLOYABILITY_CHECKLIST.md',
    'V5_TRANSITION_REVIEW_FIX_CHECKLIST.md'
) | ForEach-Object { $handoffPathRestrictedRelatives.Add($_) | Out-Null }
$archivedHousekeepingDocs = @(
    'HOUSEKEEPING_AUDIT_REPORT.md',
    'HOUSEKEEPING_EXECUTION_CHECKLIST.md'
)
$removedShellScanExclusions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    'Docs\DOC_TOUCH_LOG.md',
    'CODE_REVIEW_V5_WEBVIEW_TAURI_AUDIT.md',
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
            if ($relative -eq 'Docs\ARCHIVED_MD_INDEX.md') { continue }
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
