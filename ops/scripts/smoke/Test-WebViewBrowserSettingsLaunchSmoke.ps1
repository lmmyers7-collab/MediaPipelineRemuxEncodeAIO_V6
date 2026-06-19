param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser settings/launch smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Settings and Launch controls.'
Write-Host 'Boundary: validates unsaved Settings changes handoff, Settings-to-Launch intent status, and backend Save result visibility.'
Write-Host 'Boundary: validates Launch Active Media Policy Boundary separates saved launch-active policy from staged subtitle/audio/pending-publish candidates.'
Write-Host 'Boundary: validates selectable Launch Risk Handoff proof-chain detail for saved-settings risk rows.'
Write-Host 'Boundary: verifies the Save Settings review dialog, cancelled Save Settings remains visible, and Save Settings is not posted by the browser smoke.'
Write-Host 'Boundary: does not save settings, process media, launch pipeline commands, publish, rename files, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_settings_launch_smoke' -AllowSkippedTests:$AllowSkippedTests
