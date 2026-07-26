param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView schedule smoke'
Write-Host 'Boundary: evaluates WebView Schedule assets in Node with mocked DOM state.'
Write-Host 'Boundary: verifies Schedule Coverage Review, selected day detail, table status legend, Schedule Editor preview/save routing, and app-state-write result copy.'
Write-Host 'Boundary: does not start pipeline commands, override schedule gates, mutate queue state, touch media files, or write app state from frontend code.'
Write-Host 'Boundary: fails when Node.js is missing or tests skip unless -AllowSkippedTests is explicit.'

Invoke-WebViewDirectSmokeUnittest `
    -ProjectRoot $projectRoot `
    -Module 'tests.webview.test_webview_schedule_smoke' `
    -AllowSkippedTests:$AllowSkippedTests
