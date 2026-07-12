param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser backend lifecycle smoke'
Write-Host 'Boundary: starts temporary local API instances against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Diagnostics backend lifecycle controls.'
Write-Host 'Boundary: validates close-readiness blocked shutdown rejection while the continuous schedule-stop watcher is armed.'
Write-Host 'Boundary: validates terminal stop-requested watcher evidence stays visible without blocking safe close.'
Write-Host 'Boundary: validates safe close-readiness posts exactly through backend-owned /api/backend/shutdown after confirmation.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_lifecycle_smoke' -AllowSkippedTests:$AllowSkippedTests
