# Extracted from ops/scripts/release/test.ps1. Responsibility: deployable package acceptance orchestration

function Get-NewReleaseTrackedProcessIds {
    param(
        [Parameter(Mandatory)][string[]]$TrackedProcessNames,
        [Parameter(Mandatory)][int[]]$BaselineProcessIds
    )

    $newProcessIds = @(@(
        foreach ($name in $TrackedProcessNames) {
            Get-Process -Name $name -ErrorAction SilentlyContinue |
                Where-Object { $BaselineProcessIds -notcontains [int]$_.Id } |
                ForEach-Object { [int]$_.Id }
        }
    ) | Sort-Object -Unique)
    return $newProcessIds
}

function Wait-ReleaseTrackedProcessExit {
    param(
        [Parameter(Mandatory)][string[]]$TrackedProcessNames,
        [Parameter(Mandatory)][int[]]$BaselineProcessIds,
        [int]$TimeoutSeconds = 10
    )

    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    while ($true) {
        $remaining = @(Get-NewReleaseTrackedProcessIds `
            -TrackedProcessNames $TrackedProcessNames `
            -BaselineProcessIds $BaselineProcessIds)
        if ($remaining.Count -eq 0) { return @() }
        if ([DateTimeOffset]::UtcNow -ge $deadline) { return $remaining }
        Start-Sleep -Milliseconds 250
    }
}

function Invoke-DeployablePackageAcceptance {
    param([Parameter(Mandatory)][string]$ManifestPath)

    if (-not $PackageAcceptance) { return }
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        Write-Fail 'Package acceptance requires release_manifest.json.'
        $script:Failed = $true
        return
    }
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if (-not (ConvertTo-ReleaseBool -Value (Get-ObjectPropertyValue -Object $manifest.summary -Name 'deployable') -Default $false)) {
        Write-Fail 'Package acceptance requires a deployable release manifest.'
        $script:Failed = $true
        return
    }
    $tauriRoot = Join-Path $script:BundleRoot 'apps\desktop\tauri'
    $tauriExe = Join-Path $tauriRoot 'mediapipeline-tauri-shell.exe'
    if (-not (Test-Path -LiteralPath $tauriExe -PathType Leaf)) {
        Write-Fail 'Deployable package is missing the Tauri executable.'
        $script:Failed = $true
        return
    }
    Invoke-ReleaseScriptCheck -Label 'Tauri production surface audit' -ScriptPath (Join-Path $tauriRoot 'Test-TauriShell-ProductionSurface.ps1') -Required -TimeoutSeconds 120
    $before = @(Get-ChildItem -LiteralPath $script:BundleRoot -Force -Recurse -File | ForEach-Object { $_.FullName.Substring($script:BundleRoot.Length) }) | Sort-Object
    $trackedProcessNames = @('ffmpeg', 'ffprobe', 'mkvmerge', 'pwsh', 'powershell')
    $baselineProcessIds = @(@(
        foreach ($name in $trackedProcessNames) {
            Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.Id }
        }
    ) | Sort-Object -Unique)
    $previousAppDataRoot = $env:MEDIAPIPELINE_APPDATA_ROOT
    $previousLocalAppData = $env:LOCALAPPDATA
    $acceptanceAppDataRoot = if ($PackageAcceptanceAppDataRoot) { [System.IO.Path]::GetFullPath($PackageAcceptanceAppDataRoot) } else { Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-package-acceptance-" + [guid]::NewGuid().ToString('N')) }
    $env:MEDIAPIPELINE_APPDATA_ROOT = $acceptanceAppDataRoot
    $env:LOCALAPPDATA = Split-Path -Parent $acceptanceAppDataRoot
    try {
        Invoke-ReleaseScriptCheck -Label 'packaged Tauri launch and close' -ScriptPath (Join-Path $tauriRoot 'Test-TauriShell-Launch.ps1') -Arguments @('-Mode', 'Packaged', '-TimeoutSeconds', '180', '-CloseTimeoutSeconds', '30') -Required -TimeoutSeconds 240
    } finally {
        $env:MEDIAPIPELINE_APPDATA_ROOT = $previousAppDataRoot
        $env:LOCALAPPDATA = $previousLocalAppData
    }
    $after = @(Get-ChildItem -LiteralPath $script:BundleRoot -Force -Recurse -File | ForEach-Object { $_.FullName.Substring($script:BundleRoot.Length) }) | Sort-Object
    $added = @($after | Where-Object { $_ -notin $before })
    if ($added.Count -gt 0) {
        Write-Fail ("Package acceptance found mutable package-root artifacts: " + ($added -join ', '))
        $script:Failed = $true
    } else {
        Write-Ok 'Package acceptance left the bundle immutable after launch and close.'
    }
    foreach ($relative in @('Config', 'State', 'Logs', 'RunLogs', 'DiagnosticsExports', 'UpdateState', 'Backups', 'State\Migration')) {
        if (-not (Test-Path -LiteralPath (Join-Path $acceptanceAppDataRoot $relative) -PathType Container)) {
            Write-Fail "Package acceptance did not create product runtime root: $relative"
            $script:Failed = $true
        }
    }
    $newProcessIds = @(Wait-ReleaseTrackedProcessExit `
        -TrackedProcessNames $trackedProcessNames `
        -BaselineProcessIds $baselineProcessIds)
    if ($newProcessIds.Count -gt 0) {
        Write-Fail ('Package acceptance left runtime child process(es): ' + ($newProcessIds -join ', '))
        $script:Failed = $true
    } else {
        Write-Ok 'Package acceptance left no Tauri, Local API, PowerShell, or media-tool process.'
    }
}
