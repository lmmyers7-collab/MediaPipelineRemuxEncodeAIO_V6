[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Sidecar write safety checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$sidecarModule = Join-Path $pipelineRoot 'Modules\Sidecar.ps1'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = 'INFO'
    )
}

. $sidecarModule

$sidecarText = Get-Content -LiteralPath $sidecarModule -Raw
Assert-True ($sidecarText -match 'function Move-SidecarTempIntoPlace') 'Sidecar overwrite fallback helper is missing.'
Assert-True ($sidecarText -match '\[System\.IO\.File\]::Move\(\$TempPath,\s*\$DestinationPath,\s*\$true\)') 'Sidecar fallback must use overwrite move.'
Assert-True ($sidecarText -notmatch 'Remove-Item\s+-LiteralPath\s+\$sidecar\s+-Force') 'Sidecar fallback must not explicitly delete the existing sidecar before replacement.'
Assert-True ($sidecarText -notmatch 'delete\+rename') 'Sidecar fallback should not describe or depend on delete+rename.'

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-sidecar-write-{0}" -f ([Guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $root -Force | Out-Null
try {
    $destination = Join-Path $root 'movie.pipeline.json'
    $tmp = Join-Path $root '.movie.pipeline.json.tmp'
    [System.IO.File]::WriteAllText($destination, 'old-sidecar', [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($tmp, 'new-sidecar', [System.Text.UTF8Encoding]::new($false))

    Move-SidecarTempIntoPlace -TempPath $tmp -DestinationPath $destination

    Assert-True (-not (Test-Path -LiteralPath $tmp -PathType Leaf)) 'Sidecar overwrite fallback left the temp file behind.'
    Assert-Equal ([System.IO.File]::ReadAllText($destination)) 'new-sidecar' 'Sidecar overwrite fallback did not replace the existing file.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Sidecar write safety checks passed.'
