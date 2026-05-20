[CmdletBinding()]
param(
    [switch]$InstallNodePackages,
    [switch]$CheckOnly,
    [switch]$SkipBuildToolsCheck
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Resolve-ToolPath {
    param([Parameter(Mandatory)][string]$Name)

    $cmd = Get-Command $Name -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and $_.Source -notmatch '\\WindowsApps\\' } |
        Select-Object -First 1
    if ($cmd -and $cmd.Source) { return [string]$cmd.Source }

    $extraCandidates = @()
    if ($Name -in @('cargo', 'rustc', 'rustup')) {
        $extraCandidates += Join-Path $env:USERPROFILE ".cargo\bin\$Name.exe"
    }
    if ($Name -eq 'node') {
        $extraCandidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter 'node.exe' -ErrorAction SilentlyContinue |
            ForEach-Object { $_.FullName }
    }
    if ($Name -eq 'npm') {
        $extraCandidates += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') -Recurse -Filter 'npm.cmd' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\node_modules\\corepack\\' } |
            ForEach-Object { $_.FullName }
    }
    foreach ($candidate in $extraCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return [string]$candidate
        }
    }
    return ''
}

function Resolve-VsDevCmd {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null | Select-Object -First 1
        if ($installPath) {
            $candidate = Join-Path $installPath 'Common7\Tools\VsDevCmd.bat'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                return [string]$candidate
            }
        }
    }
    return ''
}

function Add-ToolDirectoryToPath {
    param([string]$ToolPath)
    if (-not $ToolPath) { return }
    $dir = Split-Path -Parent $ToolPath
    if ($dir -and (($env:Path -split ';') -notcontains $dir)) {
        $env:Path = "$dir;$env:Path"
    }
}

function Resolve-TauriPython {
    param(
        [Parameter(Mandatory)][string]$DesktopRoot,
        [Parameter(Mandatory)][string]$ProjectRoot
    )

    foreach ($candidate in @(
        (Join-Path $DesktopRoot 'Runtime\Python\python.exe'),
        (Join-Path $ProjectRoot 'Pipeline\Runtime\Python\python.exe')
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [string]$candidate
        }
    }
    return ''
}

function Test-LocalApiBackendModule {
    param(
        [Parameter(Mandatory)][string]$PythonPath,
        [Parameter(Mandatory)][string]$DesktopRoot
    )

    Push-Location $DesktopRoot
    try {
        $helpOutput = & $PythonPath -m mediapipeline_desktop_app.local_api_main --help 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0 -or $helpOutput -notmatch 'Start the MediaPipeline local backend API') {
            throw 'python -m mediapipeline_desktop_app.local_api_main --help failed'
        }
    } finally {
        Pop-Location
    }
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$shellRoot = [System.IO.Path]::GetFullPath($scriptRoot)
$desktopRoot = [System.IO.Path]::GetFullPath((Join-Path $shellRoot '..'))
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $desktopRoot '..'))
$nodeModules = Join-Path $shellRoot 'node_modules'
$packageJson = Join-Path $shellRoot 'package.json'

if (-not (Test-Path -LiteralPath $packageJson -PathType Leaf)) {
    throw "Tauri shell package.json was not found: $packageJson"
}

$node = Resolve-ToolPath node
$npm = Resolve-ToolPath npm
$cargo = Resolve-ToolPath cargo
$vsDevCmd = Resolve-VsDevCmd
$python = Resolve-TauriPython -DesktopRoot $desktopRoot -ProjectRoot $projectRoot

foreach ($tool in @(
    @{ Name = 'node'; Path = $node },
    @{ Name = 'npm'; Path = $npm },
    @{ Name = 'cargo'; Path = $cargo }
)) {
    if (-not $tool.Path) {
        throw "$($tool.Name) was not found. Install Node.js LTS and Rustup, then rerun this launcher."
    }
    Add-ToolDirectoryToPath -ToolPath $tool.Path
}

if (-not $python) {
    throw 'Backend Python runtime was not found. Expected DesktopApp\Runtime\Python\python.exe or Pipeline\Runtime\Python\python.exe.'
}
Test-LocalApiBackendModule -PythonPath $python -DesktopRoot $desktopRoot

if (-not $SkipBuildToolsCheck -and -not $vsDevCmd) {
    throw 'Visual Studio developer environment was not found. Install Visual Studio 2022 Build Tools with Desktop development with C++ workload.'
}

Write-Host 'MediaPipelineRemuxEncodeAIO V6 Tauri/WebView2 Shell' -ForegroundColor Cyan
Write-Host 'V6 is the WebView-first workspace. V5 remains the external fallback if needed.' -ForegroundColor Yellow
Write-Host 'Shell boundary: the WebView calls backend-owned local API commands; it must not own filesystem mutation or media policy.' -ForegroundColor Yellow
Write-Host "Shell root: $shellRoot"
Write-Host "Backend  : $python"
Write-Host "Node     : $(& $node --version)"
Write-Host "npm      : $(& $npm --version)"
Write-Host "Cargo    : $(& $cargo --version)"
Write-Host 'Validation: use Test-TauriShell-Build.ps1 for JS/Rust checks and Test-TauriShell-Launch.ps1 for bounded launch/close smoke.' -ForegroundColor DarkCyan

Push-Location $shellRoot
try {
    if ($InstallNodePackages) {
        Write-Host 'Installing Tauri preview node packages...'
        & $npm install
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if (-not (Test-Path -LiteralPath $nodeModules -PathType Container)) {
        throw "node_modules was not found. Run this launcher with -InstallNodePackages once, or run npm install from $shellRoot."
    }

    if ($CheckOnly) {
        Write-Host 'Tauri/WebView prerequisites are available.' -ForegroundColor Green
        Write-Host 'CheckOnly verifies tool/runtime layout and the local API module import only; it does not launch WebView2, process media, validate FFmpeg, or prove pending-publish behavior.' -ForegroundColor Yellow
        exit 0
    }

    Write-Host 'Starting Tauri/WebView shell. Close the WebView window to request backend shutdown.' -ForegroundColor Green
    Write-Host 'Do not treat this shell as fully promoted until the launch smoke, release self-test, and real-media validation pass.' -ForegroundColor Yellow
    if ($vsDevCmd -and -not $SkipBuildToolsCheck) {
        $nodeDir = Split-Path -Parent $node
        $cargoDir = Split-Path -Parent $cargo
        $cmdLine = 'call "' + $vsDevCmd + '" -arch=x64 -host_arch=x64 >nul && set "PATH=' + $nodeDir + ';' + $cargoDir + ';%PATH%" && npm run dev'
        & cmd.exe /d /s /c $cmdLine
        exit $LASTEXITCODE
    }

    & $npm run dev
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
