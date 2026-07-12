param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Pending Publish drain guard smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the real backend-served Pending Publish page.'
Write-Host 'Boundary: verifies active Pending Publish display filters are disclosed as local-only and do not narrow backend drain scope.'
Write-Host 'Boundary: injects a backend-shaped blocked recovery dry-run result and verifies Publish Button Guard refreshes immediately.'
Write-Host 'Boundary: verifies a blocked Publish Parked Outputs click records local frontend_guard evidence without posting /api/pipeline/start.'
Write-Host 'Boundary: does not process media, launch pipeline commands, drain pending publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_pending_drain_guard_smoke' -AllowSkippedTests:$AllowSkippedTests
