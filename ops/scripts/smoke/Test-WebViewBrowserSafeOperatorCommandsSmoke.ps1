param(
    [switch]$AllowSkippedTests
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
. (Join-Path $PSScriptRoot 'webview_browser_smoke_common.ps1')

Write-Host 'WebView browser safe operator command smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary media and state fixtures.'
Write-Host 'Boundary: redirects app data, runtime state, command journal, Metrics state, support exports, deployment destination, and dependency-atlas paths beneath disposable roots.'
Write-Host 'Boundary: drives real backend-served Home, Metrics, and Maintenance controls in installed Chrome/Edge headless.'
Write-Host 'Boundary: appends one evidence-only sample record, mutates only temporary Metrics registry/cache state, creates one redacted temporary support export, and uses fixture release/atlas services.'
Write-Host 'Boundary: verifies source/output media hashes remain unchanged and never starts pipeline, audit, rerun, pending-drain, publish, rename, repair, or network lifecycle work.'
Write-Host 'Boundary: fails when Node.js or Chrome/Edge prerequisites are missing unless -AllowSkippedTests is explicit.'

Invoke-WebViewBrowserSmokeUnittest -ProjectRoot $projectRoot -Module 'tests.webview.test_webview_browser_safe_operator_commands_smoke' -AllowSkippedTests:$AllowSkippedTests
