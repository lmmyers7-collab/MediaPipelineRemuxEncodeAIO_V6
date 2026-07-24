param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView row detail smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: evaluates backend-served WebView JavaScript with mocked DOM selected-row state.'
Write-Host 'Boundary: validates Queue, Completed, and Pending Publish row details plus diagnostics handoff text.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js is missing or tests skip unless -AllowSkippedTests is explicit.'

Invoke-WebViewDirectSmokeUnittest `
    -ProjectRoot $projectRoot `
    -Module 'tests.webview.test_webview_row_detail_smoke' `
    -AllowSkippedTests:$AllowSkippedTests
