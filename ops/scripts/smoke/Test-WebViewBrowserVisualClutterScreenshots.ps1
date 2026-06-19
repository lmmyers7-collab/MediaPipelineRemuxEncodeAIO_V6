param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser visual-clutter screenshot smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and captures every primary page and named subtab.'
Write-Host 'Boundary: saves screenshots and a manifest under LocalBase\UiScreenshots\validation-clutter-cleanup-<timestamp>.'
Write-Host 'Boundary: checks desktop screenshots plus 390px and 768px visible evidence-prose clutter and horizontal overflow.'
Write-Host 'Boundary: verifies no backend mutation routes are posted and media/sidecar/manifest fixture artifacts stay unchanged.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_visual_clutter_screenshots' -AllowSkippedTests:$AllowSkippedTests
