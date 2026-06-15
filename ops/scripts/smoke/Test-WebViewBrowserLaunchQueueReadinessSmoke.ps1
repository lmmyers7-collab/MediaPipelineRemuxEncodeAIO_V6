param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Launch/Queue readiness smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state, a generated launch command journal, and a temporary sample-validation record.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and renders real backend-served WebView Launch, Queue, and Schedule readiness panels.'
Write-Host 'Boundary: verifies Launch preflight, Queue-to-Launch handoff, Schedule guidance, close-readiness, and launch command-review evidence align.'
Write-Host 'Boundary: verifies Launch real-media sample proof handoff mirrors Home worksheet evidence without starting work.'
Write-Host 'Boundary: verifies Launch Sample Validation record evidence mirrors Home record/reconciliation evidence without appending records.'
Write-Host 'Boundary: verifies Pilot category coverage is visible at Launch without turning category evidence into acceptance state.'
Write-Host 'Boundary: verifies saved policy vs Queue route evidence is visible at Launch without changing Start scope or media policy.'
Write-Host 'Boundary: verifies Launch sample execution checklist mirrors Home sample-validation execution guidance without starting work.'
Write-Host 'Boundary: verifies no POST routes are sent while reading launch readiness evidence.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_launch_queue_readiness_smoke' -AllowSkippedTests:$AllowSkippedTests

