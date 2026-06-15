param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser rename smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Rename controls.'
Write-Host 'Boundary: clicks actual Rename preview rows and Check Applicable Rows, then verifies Apply Readiness, Pipeline Handoff, and duplicate-target blocking.'
Write-Host 'Boundary: verifies large-preview render cap text without calling rename.apply.'
Write-Host 'Boundary: verifies blocked duplicate-target scope does not call rename.apply.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_rename_smoke' -AllowSkippedTests:$AllowSkippedTests

