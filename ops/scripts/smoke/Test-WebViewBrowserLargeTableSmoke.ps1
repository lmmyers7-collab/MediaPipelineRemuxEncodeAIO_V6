param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser large daily-table smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Queue, Completed, and Pending Publish tables.'
Write-Host 'Boundary: verifies 260-row payloads disclose the 250-row render cap, filter warnings, and hidden selected-row detail.'
Write-Host 'Boundary: verifies no backend mutation routes are posted.'
Write-Host 'Boundary: does not process media, launch pipeline commands, drain pending publish, publish, rerun, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_large_table_smoke' -AllowSkippedTests:$AllowSkippedTests
