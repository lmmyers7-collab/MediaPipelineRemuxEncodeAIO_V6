$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
. (Join-Path $repoRoot 'ops\pipeline\engine\storage\disk.ps1')

function Assert-Equal {
    param(
        [object]$Actual,
        [object]$Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

$total = 1000L

$preallocatedNoIo = Resolve-RobocopyActiveCopyProgressBytes `
    -LandedBytes $total `
    -TotalBytes $total `
    -LastProgressBytes 0
Assert-Equal $preallocatedNoIo 0L 'Preallocated active landed file must not report complete progress.'

$firstIoEstimate = Resolve-RobocopyActiveCopyProgressBytes `
    -LandedBytes $total `
    -TotalBytes $total `
    -LastProgressBytes 0 `
    -CurrentProcessWriteBytes 250
Assert-Equal $firstIoEstimate 250L 'First active process-write counter should seed estimated copy progress.'

$nextIoEstimate = Resolve-RobocopyActiveCopyProgressBytes `
    -LandedBytes $total `
    -TotalBytes $total `
    -LastProgressBytes 250 `
    -CurrentProcessWriteBytes 650 `
    -LastProcessWriteBytes 250
Assert-Equal $nextIoEstimate 650L 'Subsequent process-write counter delta should advance estimated copy progress.'

$clampedEstimate = Resolve-RobocopyActiveCopyProgressBytes `
    -LandedBytes $total `
    -TotalBytes $total `
    -LastProgressBytes 900 `
    -CurrentProcessWriteBytes 5000 `
    -LastProcessWriteBytes 900
Assert-Equal $clampedEstimate 999L 'Active copy estimate must stay below complete until Robocopy exits.'

$growingLength = Resolve-RobocopyActiveCopyProgressBytes `
    -LandedBytes 512 `
    -TotalBytes $total `
    -LastProgressBytes 128
Assert-Equal $growingLength 512L 'Non-preallocated landed file growth should still drive progress.'

Write-Host 'OK: robocopy progress telemetry checks passed.'
