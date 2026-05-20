param(
    [string]$TauriRoot = $PSScriptRoot
)

$ErrorActionPreference = 'Stop'

function Add-Failure {
    param(
        [System.Collections.Generic.List[string]]$Failures,
        [string]$Message
    )
    $Failures.Add($Message) | Out-Null
}

$failures = [System.Collections.Generic.List[string]]::new()
$srcRoot = Join-Path $TauriRoot 'src-tauri\src'
$webAssets = Join-Path (Split-Path -Parent $TauriRoot) 'mediapipeline_desktop_app\ui_web\static\assets'
$webIndex = Join-Path (Split-Path -Parent $TauriRoot) 'mediapipeline_desktop_app\ui_web\static\index.html'
$configPath = Join-Path $TauriRoot 'src-tauri\tauri.conf.json'

$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if (@($config.app.windows).Count -ne 0) {
    Add-Failure $failures 'tauri.conf.json must keep app.windows empty; lib.rs owns the single dynamic main window.'
}
$csp = [string]$config.app.security.csp
if ([string]::IsNullOrWhiteSpace($csp)) {
    Add-Failure $failures 'tauri.conf.json must define a Content Security Policy instead of leaving csp null.'
}
foreach ($requiredCspFragment in @(
    "default-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
    "form-action 'none'"
)) {
    if ($csp -notmatch [regex]::Escape($requiredCspFragment)) {
        Add-Failure $failures "tauri.conf.json CSP is missing expected fragment: $requiredCspFragment"
    }
}

$runtimeRust = foreach ($path in Get-ChildItem -LiteralPath $srcRoot -Filter '*.rs') {
    $text = Get-Content -LiteralPath $path.FullName -Raw
    if ($path.Name -eq 'lib.rs') {
        $text = ($text -split '#\[cfg\(test\)\]\s*mod tests', 2)[0]
    }
    [pscustomobject]@{ Name = $path.Name; Text = $text }
}

foreach ($entry in $runtimeRust) {
    if ($entry.Text -match '\b(open_devtools|with_devtools|remote-debugging-port|--inspect|--remote-debugging-port)\b') {
        Add-Failure $failures "$($entry.Name) exposes a production developer-tool/debugging surface."
    }
    foreach ($line in ($entry.Text -split "`r?`n")) {
        if ($line -match '\b(e?println!)' -and $line -match 'token') {
            Add-Failure $failures "$($entry.Name) logs a token-adjacent line: $line"
        }
    }
}

$singleInstance = Join-Path $srcRoot 'single_instance_guard.rs'
$singleInstanceText = Get-Content -LiteralPath $singleInstance -Raw
foreach ($required in @(
    'Local\\MediaPipelineRemuxEncodeAIO_V6_TauriShell',
    'ERROR_ALREADY_EXISTS',
    'Another MediaPipeline Tauri/WebView2 shell instance is already running'
)) {
    if ($singleInstanceText -notmatch [regex]::Escape($required)) {
        Add-Failure $failures "single_instance_guard.rs is missing expected guard text: $required"
    }
}

$bridgePath = Join-Path $webAssets 'tauriLifecycleBridge.js'
$bridge = Get-Content -LiteralPath $bridgePath -Raw
foreach ($required in @(
    'mediapipeline://backend-lifecycle',
    'mediapipeline:backend-lifecycle',
    'window.__TAURI__',
    'eventApi.listen',
    'window.dispatchEvent(new CustomEvent'
)) {
    if ($bridge -notmatch [regex]::Escape($required)) {
        Add-Failure $failures "tauriLifecycleBridge.js is missing expected bridge text: $required"
    }
}
if ($bridge -match '\b(invoke|shell|fs|path|Command|process)\b') {
    Add-Failure $failures 'tauriLifecycleBridge.js must stay event-listener only; command, shell, filesystem, path, or process APIs are forbidden.'
}

$index = Get-Content -LiteralPath $webIndex -Raw
if ($index -notmatch '/assets/tauriLifecycleBridge\.js') {
    Add-Failure $failures 'index.html must load tauriLifecycleBridge.js before app.js.'
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Tauri production surface audit failed with $($failures.Count) issue(s)."
}

Write-Host 'Tauri production surface audit passed.'
Write-Host 'Verified: CSP configured, no static production devtools flags, no token-adjacent runtime logging, dynamic single main window, per-user single-instance mutex, and read-only Tauri lifecycle event bridge.'
