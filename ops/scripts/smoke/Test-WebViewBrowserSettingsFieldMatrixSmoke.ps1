param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser Settings field matrix smoke'
Write-Host 'Boundary: starts a temporary local API, config, browser profile, and media sentinels.'
Write-Host 'Boundary: derives every field from backend field_definitions and the WebView metadata groups; no duplicate field list is maintained.'
Write-Host 'Boundary: covers all ten Settings panes, builder stage/reset behavior, library override semantics, and one confirmed temp-only save/reload.'
Write-Host 'Boundary: does not open native path dialogs, launch media tools, process media, use network workers, or mutate production settings/state.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_settings_field_matrix_smoke' -AllowSkippedTests:$AllowSkippedTests
