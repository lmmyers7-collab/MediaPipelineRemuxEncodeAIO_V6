[CmdletBinding()]
param(
    [switch]$InstallNodePackages,
    [switch]$SkipLinkCheck
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
    if ($Name -eq 'link') {
        $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
        if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
            $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null | Select-Object -First 1
            if ($installPath) {
                $extraCandidates += Get-ChildItem -Path (Join-Path $installPath 'VC\Tools\MSVC') -Recurse -Filter 'link.exe' -ErrorAction SilentlyContinue |
                    Where-Object { $_.FullName -match '\\bin\\Hostx64\\x64\\link\.exe$' } |
                    ForEach-Object { $_.FullName }
            }
        }
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

function Test-JavaScriptSyntax {
    param(
        [Parameter(Mandatory)][string]$NodePath,
        [Parameter(Mandatory)][string]$StaticRoot
    )

    $assetRoot = Join-Path $StaticRoot 'assets'
    if (-not (Test-Path -LiteralPath $assetRoot -PathType Container)) {
        throw "WebView asset folder was not found: $assetRoot"
    }
    $scripts = Get-ChildItem -LiteralPath $assetRoot -Filter '*.js' -File -Recurse | Sort-Object FullName
    if (-not $scripts) {
        throw "No WebView JavaScript assets were found in $assetRoot"
    }
    Write-Host "Checking WebView JavaScript syntax..."
    foreach ($script in $scripts) {
        & $NodePath --check $script.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "JavaScript syntax check failed: $($script.FullName)"
        }
    }
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$shellRoot = [System.IO.Path]::GetFullPath($scriptRoot)
$desktopRoot = Split-Path -Parent $shellRoot
$staticRoot = Join-Path $desktopRoot 'webview\static'
$cargoToml = Join-Path $shellRoot 'src-tauri\Cargo.toml'

$node = Resolve-ToolPath node
$npm = Resolve-ToolPath npm
$cargo = Resolve-ToolPath cargo
$rustc = Resolve-ToolPath rustc
$link = Resolve-ToolPath link
$vsDevCmd = Resolve-VsDevCmd

foreach ($tool in @(
    @{ Name = 'node'; Path = $node },
    @{ Name = 'npm'; Path = $npm },
    @{ Name = 'cargo'; Path = $cargo },
    @{ Name = 'rustc'; Path = $rustc }
)) {
    if (-not $tool.Path) {
        throw "$($tool.Name) was not found. Install Node.js LTS and Rustup, then rerun this script."
    }
    Add-ToolDirectoryToPath -ToolPath $tool.Path
}

Write-Host "Node : $(& $node --version)"
Write-Host "npm  : $(& $npm --version)"
Write-Host "Cargo: $(& $cargo --version)"
Write-Host "rustc: $(& $rustc --version)"

if (-not $link -and -not $SkipLinkCheck) {
    Write-Host 'MSVC link.exe was not found.' -ForegroundColor Yellow
    Write-Host 'Install Visual Studio 2022 Build Tools with the Desktop development with C++ workload, then open a new terminal or developer shell.' -ForegroundColor Yellow
    exit 2
}
if (-not $vsDevCmd -and -not $SkipLinkCheck) {
    Write-Host 'Visual Studio developer environment script was not found.' -ForegroundColor Yellow
    Write-Host 'Install Visual Studio 2022 Build Tools with the Desktop development with C++ workload.' -ForegroundColor Yellow
    exit 2
}

Push-Location $shellRoot
try {
    if ($InstallNodePackages) {
        & $npm install
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Test-JavaScriptSyntax -NodePath $node -StaticRoot $staticRoot
    if ($vsDevCmd -and -not $SkipLinkCheck) {
        $nodeDir = Split-Path -Parent $node
        $cargoDir = Split-Path -Parent $cargo
        $cmdLine = 'call "' + $vsDevCmd + '" -arch=x64 -host_arch=x64 >nul && set "PATH=' + $nodeDir + ';' + $cargoDir + ';%PATH%" && npm run check && cargo test --manifest-path "' + $cargoToml + '" --lib'
        & cmd.exe /d /s /c $cmdLine
        exit $LASTEXITCODE
    } else {
        & $npm run check
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $cargo test --manifest-path $cargoToml --lib
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
