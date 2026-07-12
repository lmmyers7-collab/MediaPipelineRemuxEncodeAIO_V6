param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser layout-manager smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the real backend-served Layout Editor drawer.'
Write-Host 'Boundary: verifies Queue, Completed, Settings, Diagnostics, Launch, and Reports tab/subtab/subsection boxes are listed in the drawer.'
Write-Host 'Boundary: verifies inactive Settings-family subtabs stay hidden while the drawer is open.'
Write-Host 'Boundary: verifies no backend mutation routes are posted and media/sidecar/manifest fixture artifacts stay unchanged.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_layout_manager_smoke' -AllowSkippedTests:$AllowSkippedTests
