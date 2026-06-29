[CmdletBinding()]
param(
    [string] $RepoRoot,
    [string] $PythonExe,
    [switch] $InstallDependencies,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    param([string] $Candidate)

    if ($Candidate) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    $scriptPath = $PSCommandPath
    if (-not $scriptPath) {
        throw 'Unable to resolve script path for repository root discovery.'
    }

    return (Resolve-Path -LiteralPath (Join-Path (Split-Path -Parent $scriptPath) '..\..\..')).Path
}

function Resolve-PythonExe {
    param([string] $Candidate)

    if ($Candidate) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    $command = Get-Command python -ErrorAction Stop
    return $command.Source
}

function Invoke-CheckedCommand {
    param(
        [string] $FilePath,
        [string[]] $Arguments,
        [string] $FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Copy-PythonRuntime {
    param(
        [string] $SourceRoot,
        [string] $TargetRoot
    )

    $targetPython = Join-Path $TargetRoot 'python.exe'
    if ((Test-Path -LiteralPath $targetPython) -and -not $Force) {
        Write-Host "CI Python runtime already present: $targetPython"
        return
    }

    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null

    $targetResolved = (Resolve-Path -LiteralPath $TargetRoot).Path
    $sourceResolved = (Resolve-Path -LiteralPath $SourceRoot).Path
    if ($sourceResolved -ieq $targetResolved) {
        Write-Host "CI Python runtime source already matches target: $TargetRoot"
        return
    }

    foreach ($item in Get-ChildItem -LiteralPath $SourceRoot -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $TargetRoot $item.Name) -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $targetPython)) {
        throw "CI Python runtime copy did not produce $targetPython"
    }

    & $targetPython -c "import sys; print(sys.version)"
    if ($LASTEXITCODE -ne 0) {
        throw "CI Python runtime failed validation: $targetPython"
    }
}

function Install-PythonRuntimeDependencies {
    param(
        [string] $TargetRoot,
        [string] $RepoRootPath
    )

    $targetPython = Join-Path $TargetRoot 'python.exe'
    if (-not (Test-Path -LiteralPath $targetPython)) {
        throw "CI Python runtime is missing python.exe: $targetPython"
    }

    $requirementsPath = Join-Path $RepoRootPath 'requirements\dev.txt'
    if (-not (Test-Path -LiteralPath $requirementsPath)) {
        throw "CI dependency requirements file is missing: $requirementsPath"
    }

    Write-Host "Installing CI Python dependencies into $targetPython"
    Invoke-CheckedCommand `
        -FilePath $targetPython `
        -Arguments @('-m', 'pip', 'install', '-r', $requirementsPath, '-e', $RepoRootPath) `
        -FailureMessage "CI Python dependency install failed for $targetPython"

    Invoke-CheckedCommand `
        -FilePath $targetPython `
        -Arguments @('-c', 'import pydantic, psutil, pysubs2, zeroconf; print("CI Python runtime dependencies validated")') `
        -FailureMessage "CI Python dependency import validation failed for $targetPython"
}

$repoRootPath = Resolve-RepoRoot -Candidate $RepoRoot
$pythonPath = Resolve-PythonExe -Candidate $PythonExe
$sourceRoot = Split-Path -Parent $pythonPath

if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot 'python.exe'))) {
    throw "Python source root is missing python.exe: $sourceRoot"
}

$runtimeRoots = @(
    (Join-Path $repoRootPath 'apps\desktop\runtime\Python'),
    (Join-Path $repoRootPath 'ops\pipeline\runtime\Python')
)

foreach ($runtimeRoot in $runtimeRoots) {
    Copy-PythonRuntime -SourceRoot $sourceRoot -TargetRoot $runtimeRoot
}

if ($InstallDependencies) {
    foreach ($runtimeRoot in $runtimeRoots) {
        Install-PythonRuntimeDependencies -TargetRoot $runtimeRoot -RepoRootPath $repoRootPath
    }
}
