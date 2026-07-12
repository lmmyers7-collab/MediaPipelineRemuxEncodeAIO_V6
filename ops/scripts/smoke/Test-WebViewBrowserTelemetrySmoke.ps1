param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser telemetry smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Live telemetry rendering.'
Write-Host 'Boundary: validates zero-percent NVENC remains visible without duplicate idle wording and synthesizes a GPU detail row when only top-level GPU telemetry is present.'
Write-Host 'Boundary: validates CPU/RAM-only fallback wording keeps the GPU graph area explicit instead of empty.'
Write-Host 'Boundary: does not collect live GPU telemetry, process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_telemetry_smoke' -AllowSkippedTests:$AllowSkippedTests
