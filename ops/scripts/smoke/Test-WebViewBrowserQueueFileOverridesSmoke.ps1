param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Queue file-overrides drawer smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the real backend-served Queue File Settings drawer.'
Write-Host 'Boundary: verifies action/status feedback, dirty-state discard guard, clear_fields save payload, full clear confirmation, and failed-save alert tone.'
Write-Host 'Boundary: intercepts file-overrides POST routes in the browser harness and does not persist queue/file override mutations.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_queue_file_overrides_smoke' -AllowSkippedTests:$AllowSkippedTests

