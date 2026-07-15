param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Queue -> Launch -> Completed smoke'
Write-Host 'Boundary: starts a temporary Local API and real backend-served WebView against one runnable, one blocked, and one excluded temporary source row.'
Write-Host 'Boundary: the selected runnable row is staged as a single-file Launch request; the production duplicate-command and lifecycle guards reject a second start.'
Write-Host 'Boundary: a synchronized test-only runner writes only temporary Queue, progress, Completed Manifest, fake output, and sidecar evidence after duplicate rejection is durably journaled.'
Write-Host 'Boundary: does not launch FFmpeg, PowerShell pipeline children, media tools, network workers, Pending Publish work, or any source mutation.'
Write-Host 'Boundary: verifies persisted browser reload state, idle lifecycle evidence, safe close readiness, and unchanged source hashes.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_queue_launch_completed_smoke' -AllowSkippedTests:$AllowSkippedTests
