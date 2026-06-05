[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$RequireToolchain,
    [switch]$RequireBuildTools
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Write-Check {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][bool]$Ok,
        [string]$Detail = ''
    )
    $prefix = if ($Ok) { '[ OK ]' } else { '[WARN]' }
    $color = if ($Ok) { 'Green' } else { 'Yellow' }
    if ($Detail) {
        Write-Host "$prefix $Label - $Detail" -ForegroundColor $color
    } else {
        Write-Host "$prefix $Label" -ForegroundColor $color
    }
}

function Resolve-CommandPath {
    param([Parameter(Mandatory)][string]$Name)
    $cmd = Get-Command $Name -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and $_.Source -notmatch '\\WindowsApps\\' } |
        Select-Object -First 1
    if ($cmd -and $cmd.Source) { return $cmd.Source }

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

function Resolve-TauriPython {
    param(
        [Parameter(Mandatory)][string]$DesktopRoot,
        [Parameter(Mandatory)][string]$ProjectRoot
    )

    foreach ($candidate in @(
        (Join-Path $DesktopRoot 'Runtime\Python\python.exe'),
        (Join-Path $ProjectRoot 'ops\pipeline\runtime\Python\python.exe')
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [string]$candidate
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return 'python'
    }
    return ''
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$shellRoot = [System.IO.Path]::GetFullPath($scriptRoot)
$desktopRoot = [System.IO.Path]::GetFullPath((Join-Path $shellRoot '..'))
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $desktopRoot '..\..'))
$failed = $false

Write-Host 'MediaPipeline Tauri/WebView2 preview prerequisite check'
Write-Host 'This check is non-mutating and does not replace the external rollback workspace.' -ForegroundColor Yellow
if ($CheckOnly) {
    Write-Host 'CheckOnly mode: verifying layout/runtime prerequisites only; no WebView window is opened and no media is processed.' -ForegroundColor DarkCyan
}
Write-Host "Shell root  : $shellRoot"
Write-Host "Desktop root: $desktopRoot"

$requiredFiles = @(
    'package.json',
    'package-lock.json',
    'Test-TauriShell-Build.ps1',
    'Test-TauriShell-Launch.ps1',
    'frontend\index.html',
    'src-tauri\Cargo.toml',
    'src-tauri\Cargo.lock',
    'src-tauri\icons\icon.ico',
    'src-tauri\tauri.conf.json',
    'src-tauri\src\lib.rs',
    '..\..\..\src\mediapipeline\desktop\local_api_main.py'
)
foreach ($relative in $requiredFiles) {
    $path = Join-Path $shellRoot $relative
    $ok = Test-Path -LiteralPath $path -PathType Leaf
    Write-Check -Label "Required file $relative" -Ok $ok
    if (-not $ok) { $failed = $true }
}

$python = Resolve-TauriPython -DesktopRoot $desktopRoot -ProjectRoot $projectRoot
if ($python) {
    Write-Check -Label 'Backend Python runtime' -Ok $true -Detail $python
    $oldPythonPath = $env:PYTHONPATH
    Push-Location $desktopRoot
    try {
        $srcRoot = Join-Path $projectRoot 'src'
        if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
            $env:PYTHONPATH = $srcRoot
        } else {
            $env:PYTHONPATH = "$srcRoot;$oldPythonPath"
        }
        $helpOutput = & $python -m mediapipeline.desktop.local_api_main --help 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -and $helpOutput -match 'Start the MediaPipeline local backend API') {
            Write-Check -Label 'Local API module import' -Ok $true
        } else {
            Write-Check -Label 'Local API module import' -Ok $false -Detail 'python -m mediapipeline.desktop.local_api_main --help failed'
            $failed = $true
        }
    } finally {
        Pop-Location
        $env:PYTHONPATH = $oldPythonPath
    }
} else {
    Write-Check -Label 'Backend Python runtime' -Ok $false -Detail 'apps\desktop\runtime\Python\python.exe, ops\pipeline\runtime\Python\python.exe, or python on PATH missing'
    $failed = $true
}

$node = Resolve-CommandPath node
$npm = Resolve-CommandPath npm
$cargo = Resolve-CommandPath cargo
$rustc = Resolve-CommandPath rustc
$link = Resolve-CommandPath link
Write-Check -Label 'Node.js' -Ok ([bool]$node) -Detail $(if ($node) { $node } else { 'not found on PATH' })
Write-Check -Label 'npm' -Ok ([bool]$npm) -Detail $(if ($npm) { $npm } else { 'not found on PATH' })
Write-Check -Label 'cargo' -Ok ([bool]$cargo) -Detail $(if ($cargo) { $cargo } else { 'not found on PATH' })
Write-Check -Label 'rustc' -Ok ([bool]$rustc) -Detail $(if ($rustc) { $rustc } else { 'not found on PATH' })
Write-Check -Label 'MSVC linker' -Ok ([bool]$link) -Detail $(if ($link) { $link } else { 'link.exe not found; install Visual Studio C++ Build Tools before cargo check/build' })

if ($RequireToolchain -and (-not $node -or -not $npm -or -not $cargo -or -not $rustc)) {
    $failed = $true
}
if ($RequireBuildTools -and (-not $link)) {
    $failed = $true
}

$webViewRuntime = $false
if ($env:OS -eq 'Windows_NT') {
    foreach ($root in @(
        'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients',
        'HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients'
    )) {
        foreach ($client in @(Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
            $props = Get-ItemProperty -LiteralPath $client.PSPath -ErrorAction SilentlyContinue
            $nameProperty = if ($props) { $props.PSObject.Properties['name'] } else { $null }
            $name = if ($nameProperty) { [string]$nameProperty.Value } else { '' }
            if ($name -match 'WebView2') {
                $webViewRuntime = $true
                break
            }
        }
        if ($webViewRuntime) { break }
    }
    Write-Check -Label 'WebView2 runtime registry hint' -Ok $webViewRuntime -Detail $(if ($webViewRuntime) { 'detected' } else { 'not detected; Tauri may still use an installed evergreen runtime' })
}

if ($failed) {
    Write-Host 'Tauri preview prerequisites are incomplete.' -ForegroundColor Yellow
    Write-Host 'Fix the missing required items before running the preview launcher or launch smoke.' -ForegroundColor Yellow
    exit 1
}

Write-Host 'Tauri preview prerequisites passed.' -ForegroundColor Green
Write-Host 'Next validation: run Test-TauriShell-Build.ps1 for WebView JavaScript, cargo check, and Rust shell unit tests.' -ForegroundColor DarkCyan
Write-Host 'For launch lifecycle validation, run Test-TauriShell-Launch.ps1. This prereq check does not open WebView2 or process media.' -ForegroundColor DarkCyan
exit 0
