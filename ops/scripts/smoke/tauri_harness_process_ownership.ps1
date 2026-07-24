# Shared exact-identity process ownership support for native Tauri validation harnesses.
function ConvertTo-TauriHarnessCreationTimeUtcMs {
    param([Parameter(Mandatory)]$Value)

    $dateTime = if ($Value -is [datetime]) {
        [datetime]$Value
    } else {
        [datetime]::Parse(
            [string]$Value,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeLocal
        )
    }
    return [DateTimeOffset]::new($dateTime.ToUniversalTime()).ToUnixTimeMilliseconds()
}

function ConvertTo-TauriHarnessProcessIdentity {
    param([Parameter(Mandatory)]$Process)

    $creationTimeUtcMs = ConvertTo-TauriHarnessCreationTimeUtcMs -Value $Process.CreationDate
    if ($creationTimeUtcMs -le 0) {
        throw "Process $($Process.ProcessId) has no usable creation-time identity."
    }
    return [pscustomobject]@{
        ProcessId = [int]$Process.ProcessId
        ParentProcessId = [int]$Process.ParentProcessId
        CreationTimeUtcMs = [long]$creationTimeUtcMs
        Name = [string]$Process.Name
        CommandLine = [string]$Process.CommandLine
    }
}

function Get-TauriHarnessProcessSnapshot {
    $rows = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    return @($rows | ForEach-Object { ConvertTo-TauriHarnessProcessIdentity -Process $_ })
}

function Get-TauriHarnessProcessIdentity {
    param(
        [Parameter(Mandatory)][int]$ProcessId,
        [int]$TimeoutMilliseconds = 5000
    )

    $deadline = [Diagnostics.Stopwatch]::StartNew()
    do {
        $identity = Get-TauriHarnessProcessSnapshot |
            Where-Object { $_.ProcessId -eq $ProcessId } |
            Select-Object -First 1
        if ($identity) { return $identity }
        Start-Sleep -Milliseconds 50
    } while ($deadline.ElapsedMilliseconds -lt $TimeoutMilliseconds)
    throw "Could not capture exact process identity for PID $ProcessId within $TimeoutMilliseconds ms."
}

function Test-TauriHarnessProcessIdentityEqual {
    param(
        [Parameter(Mandatory)]$Expected,
        [Parameter(Mandatory)]$Actual
    )

    return (
        [int]$Expected.ProcessId -eq [int]$Actual.ProcessId -and
        [long]$Expected.CreationTimeUtcMs -eq [long]$Actual.CreationTimeUtcMs
    )
}

function Get-TauriHarnessOwnedDescendants {
    param(
        [Parameter(Mandatory)]$RootIdentity,
        [Parameter(Mandatory)][object[]]$ProcessSnapshot,
        [switch]$IncludeRoot
    )

    $byId = @{}
    foreach ($row in $ProcessSnapshot) {
        $processId = [int]$row.ProcessId
        if ($byId.ContainsKey($processId)) {
            throw "Process snapshot contains duplicate PID $processId."
        }
        $byId[$processId] = $row
    }

    $rootId = [int]$RootIdentity.ProcessId
    if (-not $byId.ContainsKey($rootId)) { return @() }
    if (-not (Test-TauriHarnessProcessIdentityEqual -Expected $RootIdentity -Actual $byId[$rootId])) {
        return @()
    }

    $owned = @{ $rootId = $byId[$rootId] }
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($row in $ProcessSnapshot) {
            $processId = [int]$row.ProcessId
            $parentId = [int]$row.ParentProcessId
            if ($owned.ContainsKey($processId) -or -not $owned.ContainsKey($parentId)) { continue }
            $parent = $owned[$parentId]
            if ([long]$row.CreationTimeUtcMs -lt [long]$parent.CreationTimeUtcMs) { continue }
            $owned[$processId] = $row
            $changed = $true
        }
    }

    return @(
        $owned.Values |
            Where-Object { $IncludeRoot -or [int]$_.ProcessId -ne $rootId } |
            Sort-Object CreationTimeUtcMs, ProcessId
    )
}

function Get-TauriHarnessOwnedShellIdentities {
    param(
        [Parameter(Mandatory)]$RootIdentity,
        [Parameter(Mandatory)][object[]]$ProcessSnapshot
    )

    return @(
        Get-TauriHarnessOwnedDescendants -RootIdentity $RootIdentity -ProcessSnapshot $ProcessSnapshot -IncludeRoot |
            Where-Object { [string]$_.Name -ieq 'mediapipeline-tauri-shell.exe' }
    )
}

function Get-TauriHarnessOwnedBackendIdentities {
    param(
        [Parameter(Mandatory)]$RootIdentity,
        [Parameter(Mandatory)][object[]]$ProcessSnapshot
    )

    return @(
        Get-TauriHarnessOwnedDescendants -RootIdentity $RootIdentity -ProcessSnapshot $ProcessSnapshot -IncludeRoot |
            Where-Object {
                [string]$_.Name -match '^python(\d+(\.\d+)*)?\.exe$' -and
                [string]$_.CommandLine -match 'mediapipeline.desktop\.local_api_main'
            }
    )
}

function Get-TauriHarnessOwnedWebView2Identities {
    param(
        [Parameter(Mandatory)]$RootIdentity,
        [Parameter(Mandatory)][object[]]$ProcessSnapshot
    )

    $owned = @(Get-TauriHarnessOwnedDescendants -RootIdentity $RootIdentity -ProcessSnapshot $ProcessSnapshot -IncludeRoot)
    $ownedWebViewIds = @{}
    foreach ($row in $owned) {
        if ([string]$row.Name -ieq 'msedgewebview2.exe') {
            $ownedWebViewIds[[int]$row.ProcessId] = $true
        }
    }
    return @($owned | Where-Object {
        [string]$_.Name -ieq 'msedgewebview2.exe' -and
        -not $ownedWebViewIds.ContainsKey([int]$_.ParentProcessId)
    })
}

function Test-TauriHarnessProcessIdentityCurrent {
    param([Parameter(Mandatory)]$Identity)

    try {
        $current = Get-TauriHarnessProcessSnapshot |
            Where-Object { $_.ProcessId -eq [int]$Identity.ProcessId } |
            Select-Object -First 1
        return [bool]($current -and (Test-TauriHarnessProcessIdentityEqual -Expected $Identity -Actual $current))
    } catch {
        Write-Warning "Could not revalidate PID $($Identity.ProcessId); refusing to treat it as owned: $($_.Exception.Message)"
        return $false
    }
}

function Stop-TauriHarnessOwnedProcessTree {
    param(
        [Parameter(Mandatory)]$Identity,
        [string]$Label = 'harness-owned process'
    )

    if (-not (Test-TauriHarnessProcessIdentityCurrent -Identity $Identity)) {
        Write-Warning "Refusing to stop $Label PID $($Identity.ProcessId): exact creation-time identity is absent or changed."
        return $false
    }
    $process = Get-Process -Id ([int]$Identity.ProcessId) -ErrorAction SilentlyContinue
    if (-not $process) { return $true }
    $processStartUtcMs = [DateTimeOffset]::new($process.StartTime.ToUniversalTime()).ToUnixTimeMilliseconds()
    if ($processStartUtcMs -ne [long]$Identity.CreationTimeUtcMs) {
        Write-Warning "Refusing to stop $Label PID $($Identity.ProcessId): process-handle creation time changed."
        return $false
    }
    try {
        $process.Kill($true)
    } catch {
        try {
            $process.Kill()
        } catch {
            Write-Warning "Could not stop exact $Label PID $($Identity.ProcessId): $($_.Exception.Message)"
            return $false
        }
    }
    return $true
}

function Wait-TauriHarnessProcessIdentitiesGone {
    param(
        [Parameter(Mandatory)][object[]]$Identities,
        [Parameter(Mandatory)][int]$TimeoutSeconds,
        [string]$Label = 'harness-owned process(es)'
    )

    $expected = @($Identities | Group-Object ProcessId | ForEach-Object { $_.Group[0] })
    if ($expected.Count -eq 0) { return @() }
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $remaining = @($expected | Where-Object { Test-TauriHarnessProcessIdentityCurrent -Identity $_ })
        if ($remaining.Count -eq 0) { return @() }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    Write-Host "$Label still running after ${TimeoutSeconds}s: $(@($remaining.ProcessId) -join ', ')" -ForegroundColor Yellow
    return $remaining
}
