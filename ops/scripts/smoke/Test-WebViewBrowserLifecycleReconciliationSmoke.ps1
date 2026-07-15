param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser lifecycle abnormal-exit reconciliation smoke'
Write-Host 'Boundary: creates lifecycle evidence only under a temporary state root by using production lease and recovery APIs.'
Write-Host 'Boundary: proves a real live helper PID blocks preview without journaling, then terminates and waits for that helper before recovery.'
Write-Host 'Boundary: proves stale fingerprints are rejected, exact evidence is applied once, archived journal evidence survives reload, and close-readiness becomes safe.'
Write-Host 'Boundary: does not process media, start FFmpeg, use network workers, publish, rename, save settings, mutate queue state, or change source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_lifecycle_reconciliation_smoke' -AllowSkippedTests:$AllowSkippedTests
