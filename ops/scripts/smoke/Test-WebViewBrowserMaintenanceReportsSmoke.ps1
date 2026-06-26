param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Maintenance/Reports smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Maintenance and Reports pages.'
Write-Host 'Boundary: verifies Maintenance health, dry-run result rendering, dry-run history, Reports failure/audit triage, grouped failure resolution, More actions, lifecycle journal preview/confirm, marker clear preview/confirm, and evidence archive preview/confirm.'
Write-Host 'Boundary: verifies Reports failure-marker clear remains confined to /api/failures/clear, lifecycle journal state remains confined to /api/failures/lifecycle, evidence archive remains confined to /api/failures/archive-evidence, and all other backend mutation routes stay blocked.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_maintenance_reports_smoke' -AllowSkippedTests:$AllowSkippedTests
