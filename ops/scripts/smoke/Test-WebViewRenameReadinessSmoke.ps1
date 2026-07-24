param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView rename readiness smoke'
Write-Host 'Boundary: evaluates WebView Rename assets in Node with mocked DOM state.'
Write-Host 'Boundary: verifies Apply Readiness and Pipeline Handoff for a ready single-row scope and a blocked duplicate-target scope.'
Write-Host 'Boundary: verifies large-preview render cap text without calling rename.apply.'
Write-Host 'Boundary: verifies duplicate-target blocking does not call rename.apply.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or touch source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js is missing or tests skip unless -AllowSkippedTests is explicit.'

Invoke-WebViewDirectSmokeUnittest `
    -ProjectRoot $projectRoot `
    -Module 'tests.webview.test_webview_rename_readiness_smoke' `
    -AllowSkippedTests:$AllowSkippedTests
