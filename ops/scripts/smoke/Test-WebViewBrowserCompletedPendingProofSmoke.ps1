param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Completed/Pending proof smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the real backend-served Completed/Pending proof board.'
Write-Host 'Boundary: verifies the Completed Real-Media Output Proof ladder, including route/size/media, saved-policy reconciliation, Sample Validation handoff, and missing-output blocker detail.'
Write-Host 'Boundary: verifies exact completed-output to pending-destination overlap and missing-output-without-proof detail.'
Write-Host 'Boundary: verifies selected Pending row Completed Manifest correlation remains read-only.'
Write-Host 'Boundary: verifies same-leaf proof wording remains a duplicate-title hint, not publish proof.'
Write-Host 'Boundary: does not append validation records, does not process media, launch pipeline commands, drain pending publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_completed_pending_proof_smoke' -AllowSkippedTests:$AllowSkippedTests
