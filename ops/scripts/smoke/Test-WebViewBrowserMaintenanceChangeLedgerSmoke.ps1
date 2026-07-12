param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Maintenance change-ledger smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the backend-served WebView Maintenance tab.'
Write-Host 'Boundary: verifies ledger rows, selected detail, filters, empty state, hygiene copy, and read-only GET usage.'
Write-Host 'Boundary: verifies no media, queue, settings, pending-publish, rename, or other mutation POST is issued.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_maintenance_change_ledger_smoke' -AllowSkippedTests:$AllowSkippedTests
