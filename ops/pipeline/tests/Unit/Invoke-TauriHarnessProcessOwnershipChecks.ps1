[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..'))
$helperPath = Join-Path $repoRoot 'ops\scripts\smoke\tauri_harness_process_ownership.ps1'
. $helperPath

function Assert-True {
    param([bool]$Condition, [Parameter(Mandatory)][string]$Message)
    if (-not $Condition) { throw $Message }
}

function Wait-FixturePid {
    param([Parameter(Mandatory)][string]$Path)

    $deadline = (Get-Date).AddSeconds(10)
    do {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            $value = [int]([IO.File]::ReadAllText($Path))
            if ($value -gt 0) { return $value }
        }
        Start-Sleep -Milliseconds 50
    } while ((Get-Date) -lt $deadline)
    throw "Fixture child PID was not written: $Path"
}

function Start-FixtureProcessTree {
    param(
        [Parameter(Mandatory)][string]$PowerShellPath,
        [Parameter(Mandatory)][string]$PidFile
    )

    $escapedPowerShell = $PowerShellPath.Replace("'", "''")
    $escapedPidFile = $PidFile.Replace("'", "''")
    $childScript = @"
`$child = Start-Process -FilePath '$escapedPowerShell' -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 120') -WindowStyle Hidden -PassThru
[IO.File]::WriteAllText('$escapedPidFile', [string]`$child.Id)
try { Wait-Process -Id `$child.Id -Timeout 120 -ErrorAction SilentlyContinue } finally { if (-not `$child.HasExited) { `$child.Kill(`$true) } }
"@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($childScript))
    return Start-Process -FilePath $PowerShellPath -ArgumentList @('-NoProfile', '-EncodedCommand', $encoded) -WindowStyle Hidden -PassThru
}

$powerShellPath = (Get-Process -Id $PID).Path
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("mediapipeline-tauri-ownership-" + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($tempRoot) | Out-Null
$pidFileA = Join-Path $tempRoot 'tree-a.pid'
$pidFileB = Join-Path $tempRoot 'tree-b.pid'
$rootA = $null
$rootB = $null
$identityA = $null
$identityB = $null
$childIdentityA = $null
$childIdentityB = $null

try {
    $rootA = Start-FixtureProcessTree -PowerShellPath $powerShellPath -PidFile $pidFileA
    $rootB = Start-FixtureProcessTree -PowerShellPath $powerShellPath -PidFile $pidFileB
    $identityA = Get-TauriHarnessProcessIdentity -ProcessId $rootA.Id
    $identityB = Get-TauriHarnessProcessIdentity -ProcessId $rootB.Id
    $childPidA = Wait-FixturePid -Path $pidFileA
    $childPidB = Wait-FixturePid -Path $pidFileB

    $snapshot = @(Get-TauriHarnessProcessSnapshot)
    $ownedA = @(Get-TauriHarnessOwnedDescendants -RootIdentity $identityA -ProcessSnapshot $snapshot)
    $ownedB = @(Get-TauriHarnessOwnedDescendants -RootIdentity $identityB -ProcessSnapshot $snapshot)
    $childIdentityA = $ownedA | Where-Object { $_.ProcessId -eq $childPidA } | Select-Object -First 1
    $childIdentityB = $ownedB | Where-Object { $_.ProcessId -eq $childPidB } | Select-Object -First 1

    Assert-True -Condition ([bool]$childIdentityA) -Message 'Tree A child was not classified as launcher-owned.'
    Assert-True -Condition ([bool]$childIdentityB) -Message 'Tree B child was not classified as launcher-owned.'
    Assert-True -Condition ($ownedA.ProcessId -notcontains $childPidB) -Message 'Unrelated concurrent Tree B child leaked into Tree A ownership.'
    Assert-True -Condition ($ownedB.ProcessId -notcontains $childPidA) -Message 'Unrelated concurrent Tree A child leaked into Tree B ownership.'

    $mismatchedIdentity = [pscustomobject]@{
        ProcessId = $childIdentityB.ProcessId
        ParentProcessId = $childIdentityB.ParentProcessId
        CreationTimeUtcMs = $childIdentityB.CreationTimeUtcMs + 1
        Name = $childIdentityB.Name
        CommandLine = $childIdentityB.CommandLine
    }
    $previousWarningPreference = $WarningPreference
    $WarningPreference = 'SilentlyContinue'
    try {
        $mismatchStopped = Stop-TauriHarnessOwnedProcessTree -Identity $mismatchedIdentity -Label 'mismatched fixture'
    } finally {
        $WarningPreference = $previousWarningPreference
    }
    Assert-True -Condition (-not $mismatchStopped) -Message 'Creation-time mismatch unexpectedly authorized termination.'
    Assert-True -Condition (Test-TauriHarnessProcessIdentityCurrent -Identity $childIdentityB) -Message 'Unrelated Tree B child did not survive the mismatched cleanup attempt.'

    Assert-True -Condition (Stop-TauriHarnessOwnedProcessTree -Identity $childIdentityA -Label 'owned Tree A child') -Message 'Exact Tree A child identity was not stopped.'
    $remainingA = @(Wait-TauriHarnessProcessIdentitiesGone -Identities @($childIdentityA) -TimeoutSeconds 5 -Label 'Tree A child')
    Assert-True -Condition ($remainingA.Count -eq 0) -Message 'Exact Tree A child remained after owned cleanup.'
    Assert-True -Condition (Test-TauriHarnessProcessIdentityCurrent -Identity $childIdentityB) -Message 'Unrelated Tree B child was terminated by Tree A cleanup.'

    Write-Host 'PASS: concurrent process trees remain isolated by exact launcher ancestry.'
    Write-Host 'PASS: creation-time mismatch fails closed and preserves the live unrelated process.'
    Write-Host 'PASS: exact owned child cleanup does not terminate the concurrent tree.'
} finally {
    foreach ($identity in @($childIdentityA, $childIdentityB) | Where-Object { $_ }) {
        if (Test-TauriHarnessProcessIdentityCurrent -Identity $identity) {
            Stop-TauriHarnessOwnedProcessTree -Identity $identity -Label 'test fixture child' | Out-Null
        }
    }
    foreach ($root in @($rootA, $rootB) | Where-Object { $_ }) {
        if (-not $root.HasExited) {
            try { $root.Kill($true) } catch { try { $root.Kill() } catch { } }
        }
    }
    foreach ($path in @($pidFileA, $pidFileB)) {
        if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) }
    }
    if ([IO.Directory]::Exists($tempRoot)) { [IO.Directory]::Delete($tempRoot, $false) }
}

Write-Host 'Tauri harness process ownership checks passed.' -ForegroundColor Green
exit 0
