param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser LibraryProfiles save smoke'
Write-Host 'Boundary: uses a temporary config and browser fixture; does not process media, launch pipeline commands, publish, rename files, mutate queue state, drain pending publish, or modify source/output/scratch media.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_library_profiles_save_smoke' -AllowSkippedTests:$AllowSkippedTests
