param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Queue -> Launch -> Completed smoke'
Write-Host 'Boundary: starts a temporary Local API and real backend-served WebView against two accepted Backend Queue rows, one blocked row, and one excluded temporary source row.'
Write-Host 'Boundary: verifies Queue loaded but idle before Start, with uncapped accepted-run membership and no active Run Monitor claims.'
Write-Host 'Boundary: submits mode=once with Backend Queue scope and a blank Single File; the production duplicate-command and lifecycle guards reject a second start.'
Write-Host 'Boundary: exposes correlated durable Run Monitor states through the real GET /api/run-monitor route, including all workers, terminal handoff, review, run completion, and reload persistence.'
Write-Host 'Boundary: a synchronized test-only runner writes only temporary Queue, progress, Run Monitor, Completed Manifest, failure, fake output, and sidecar evidence after duplicate rejection is durably journaled.'
Write-Host 'Boundary: does not launch FFmpeg, PowerShell pipeline children, media tools, network workers, Pending Publish work, or any source mutation.'
Write-Host 'Boundary: verifies accepted fingerprint/identity, route authority labels, focus/keyboard retention, non-color cues, live announcements, visible terminal deep links, fresh idle, safe close readiness, and unchanged source hashes.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_queue_launch_completed_smoke' -AllowSkippedTests:$AllowSkippedTests
