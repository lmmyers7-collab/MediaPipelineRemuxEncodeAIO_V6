param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser network smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Network controls.'
Write-Host 'Boundary: validates backend-owned network lifecycle controls, runtime readiness, lifecycle handoff, runtime state-file evidence, persisted worker rows, worker detail, and local worker filters.'
Write-Host 'Boundary: verifies filters warn when active/problem worker rows are hidden.'
Write-Host 'Boundary: verifies confirmed network lifecycle commands are not executed; Distributed Mode Settings save is not exercised by this smoke.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename, save settings, mutate queue state, confirm start/stop coordinator/workers, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_network_smoke' -AllowSkippedTests:$AllowSkippedTests

