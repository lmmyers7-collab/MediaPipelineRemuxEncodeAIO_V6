param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser diagnostics handoff smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView diagnostics handoff controls.'
Write-Host 'Boundary: clicks actual Queue, Completed, and Pending Publish table rows before exercising read-only diagnostics bridge, tail, and allowlisted open controls.'
Write-Host 'Boundary: verifies selected-row investigation signals, current-filter visibility, clear-filter buttons, and text/status/investigation guardrails before launch, rerun, cleanup, or publish decisions.'
Write-Host 'Boundary: verifies Diagnostics Go To Owner Row navigation for Queue, Completed, and Pending Publish without backend commands.'
Write-Host 'Boundary: renders Diagnostics State Artifact Summary, selects backend read-order/artifact rows, then validates bounded backend tail output and diagnostics.open command-result feedback.'
Write-Host 'Boundary: renders Diagnostics ActiveJobs detail rows, including active and malformed records, plus stale runtime-progress guidance.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_diagnostics_handoff_smoke' -AllowSkippedTests:$AllowSkippedTests
