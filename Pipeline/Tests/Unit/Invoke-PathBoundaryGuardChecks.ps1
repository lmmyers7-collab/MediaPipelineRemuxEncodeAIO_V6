[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Path boundary guard checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot

. (Join-Path $repoRoot 'engine\shared\path_helpers.ps1')

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Invoke-WithTempRoot {
    param([Parameter(Mandatory)] [scriptblock] $Body)
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-path-boundary-" + [guid]::NewGuid().ToString("N"))
    try {
        [System.IO.Directory]::CreateDirectory($root) | Out-Null
        & $Body ([System.IO.DirectoryInfo]::new($root))
    } finally {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-WithTempRoot {
    param($Root)
    $safeRoot = Join-Path $Root.FullName 'root'
    $nested = Join-Path $safeRoot 'nested'
    [System.IO.Directory]::CreateDirectory($nested) | Out-Null
    $file = Join-Path $nested 'file.txt'
    [System.IO.File]::WriteAllText($file, 'ok')

    $ok = Test-MediaPipelinePathBoundarySafe -Path $file -Root $safeRoot
    Assert-True ([bool]$ok.Ok) 'Expected nested file to pass boundary guard.'

    $outside = Join-Path $Root.FullName 'outside.txt'
    [System.IO.File]::WriteAllText($outside, 'outside')
    $outsideResult = Test-MediaPipelinePathBoundarySafe -Path $outside -Root $safeRoot
    Assert-Equal $outsideResult.ReasonCode 'OUTSIDE_ALLOWED_ROOT' 'Outside file should be rejected.'

    $rootTarget = Test-MediaPipelinePathBoundarySafe -Path $safeRoot -Root $safeRoot
    Assert-Equal $rootTarget.ReasonCode 'ROOT_MUTATION_TARGET' 'Root mutation target should be rejected.'

    $missingLeaf = Test-MediaPipelinePathBoundarySafe -Path (Join-Path $nested 'missing.txt') -Root $safeRoot -AllowMissingLeaf
    Assert-True ([bool]$missingLeaf.Ok) 'Missing leaf under existing parent should pass with AllowMissingLeaf.'
}

Invoke-WithTempRoot {
    param($Root)
    $safeRoot = Join-Path $Root.FullName 'root'
    $target = Join-Path $Root.FullName 'target'
    $link = Join-Path $safeRoot 'link'
    [System.IO.Directory]::CreateDirectory($safeRoot) | Out-Null
    [System.IO.Directory]::CreateDirectory($target) | Out-Null

    $created = $false
    try {
        New-Item -ItemType SymbolicLink -Path $link -Target $target -ErrorAction Stop | Out-Null
        $created = $true
    } catch {
        try {
            cmd /c "mklink /J `"$link`" `"$target`"" | Out-Null
            if ($LASTEXITCODE -eq 0) { $created = $true }
        } catch {
            $created = $false
        }
    }

    if ($created) {
        $unsafe = Test-MediaPipelinePathBoundarySafe -Path (Join-Path $link 'file.txt') -Root $safeRoot -AllowMissingLeaf
        Assert-Equal $unsafe.ReasonCode 'REPARSE_POINT_COMPONENT' 'Symlink or junction component should be rejected.'
    } else {
        Write-Host 'Skipping symlink/junction assertion; creation was not permitted in this environment.'
    }
}

Write-Host 'Path boundary guard checks passed.'
