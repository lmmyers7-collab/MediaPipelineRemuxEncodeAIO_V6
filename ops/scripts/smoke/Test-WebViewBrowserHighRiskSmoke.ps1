param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser high-risk row smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the real backend-served WebView page through Chrome DevTools Protocol.'
Write-Host 'Boundary: validates injected and backend-produced blocked Queue, broken Completed, and do-not-drain Pending Publish selected-row guidance.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_high_risk_smoke' -AllowSkippedTests:$AllowSkippedTests

