param(
    [ValidateSet('before', 'after')]
    [string]$Mode = 'after',

    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser prose-box audit'
Write-Host "Mode: $Mode"
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and captures every primary page and named subtab.'
Write-Host 'Boundary: saves screenshots and a manifest under LocalBase\UiScreenshots\prose-box-cleanup-<mode>-<timestamp>.'
Write-Host 'Boundary: inventories visible prose/status/diagnostic text boxes and fails after cleanup if any visible prose box is not explicitly defended.'
Write-Host 'Boundary: verifies no backend mutation routes are posted and media/sidecar/manifest fixture artifacts stay unchanged.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

$previousMode = $env:MEDIA_PIPELINE_PROSE_BOX_AUDIT_MODE
try {
    $env:MEDIA_PIPELINE_PROSE_BOX_AUDIT_MODE = $Mode
    Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_prose_box_audit' -AllowSkippedTests:$AllowSkippedTests
}
finally {
    if ($null -eq $previousMode) {
        Remove-Item Env:\MEDIA_PIPELINE_PROSE_BOX_AUDIT_MODE -ErrorAction SilentlyContinue
    }
    else {
        $env:MEDIA_PIPELINE_PROSE_BOX_AUDIT_MODE = $previousMode
    }
}
