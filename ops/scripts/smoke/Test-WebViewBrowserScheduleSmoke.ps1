param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser schedule smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Schedule and Launch controls.'
Write-Host 'Boundary: validates Schedule Editor preview/save routing, confirmed backend app-state write, command history ownership, and refreshed Launch timing trust.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_schedule_smoke' -AllowSkippedTests:$AllowSkippedTests

