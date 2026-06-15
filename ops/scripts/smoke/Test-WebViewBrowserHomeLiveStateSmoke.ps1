param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Home live-state smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state and a generated command journal.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and renders real backend-served WebView Home panels.'
Write-Host 'Boundary: verifies Daily-Driver Checklist, Operator Readiness, Active Work, Live Progress Details/Evidence, Diagnostics runtime progress, Command Results, Sample Validation posture, and Real-Media Validation Worksheet handoff.'
Write-Host 'Boundary: verifies no POST routes are sent during Home live-state rendering.'
Write-Host 'Boundary: does not append validation records, does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_home_live_state_smoke' -AllowSkippedTests:$AllowSkippedTests

