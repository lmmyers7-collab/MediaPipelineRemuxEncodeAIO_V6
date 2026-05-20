[CmdletBinding()]
param(
    [switch]$IncludePythonBytecode,
    [switch]$IncludeRunLogs,
    [switch]$IncludeBuildArtifacts
)

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Repo hygiene checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot
$findings = [System.Collections.Generic.List[object]]::new()

function Get-RepoRelativePath {
    param([Parameter(Mandatory)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    return [System.IO.Path]::GetRelativePath($repoRoot, $fullPath)
}

function Add-Finding {
    param(
        [Parameter(Mandatory)][string]$Category,
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Reason
    )

    $findings.Add([pscustomobject]@{
        Category = $Category
        Path     = Get-RepoRelativePath -Path $Path
        Reason   = $Reason
    }) | Out-Null
}

function Test-IgnoreEntry {
    param(
        [Parameter(Mandatory)][string[]]$Entries,
        [Parameter(Mandatory)][string]$Pattern
    )

    return $Entries -contains $Pattern
}

$gitignorePath = Join-Path $repoRoot '.gitignore'
if (-not (Test-Path -LiteralPath $gitignorePath -PathType Leaf)) {
    Add-Finding -Category 'IgnoreRules' -Path $gitignorePath -Reason 'Missing .gitignore; generated API captures and build artifacts can enter the repo.'
} else {
    $ignoreEntries = Get-Content -LiteralPath $gitignorePath |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') }

    $requiredIgnoreEntries = @(
        '.pytest_cache/',
        '/RunLogs/',
        '/*.log',
        '/*.out.log',
        '/*.err.log',
        '/*.stdout.log',
        '/*.stderr.log',
        '/*.jsonl',
        '/_codex_*.log',
        '/local_api_*.log',
        'DesktopApp/tauri_shell/node_modules/',
        'DesktopApp/tauri_shell/src-tauri/target/'
    )

    foreach ($entry in $requiredIgnoreEntries) {
        if (-not (Test-IgnoreEntry -Entries $ignoreEntries -Pattern $entry)) {
            Add-Finding -Category 'IgnoreRules' -Path $gitignorePath -Reason "Missing ignore entry: $entry"
        }
    }
}

Get-ChildItem -LiteralPath $repoRoot -Force -File |
    Where-Object {
        $_.Name -like '*.log' -or
        $_.Name -like '*.out.log' -or
        $_.Name -like '*.err.log' -or
        $_.Name -like '*.stdout.log' -or
        $_.Name -like '*.stderr.log' -or
        $_.Name -like '*.jsonl' -or
        $_.Name -like '_codex_*.log' -or
        $_.Name -like 'local_api_*.log'
    } |
    ForEach-Object {
        Add-Finding -Category 'RootLogCapture' -Path $_.FullName -Reason 'Root-level generated API/log capture should be under RunLogs or removed.'
    }

$desktopAppRoot = Join-Path $repoRoot 'DesktopApp'
if (Test-Path -LiteralPath $desktopAppRoot -PathType Container) {
    Get-ChildItem -LiteralPath $desktopAppRoot -Force -File |
        Where-Object {
            $_.Name -like 'local_api_*.log' -or
            $_.Name -like 'local_api_*.out.log' -or
            $_.Name -like 'local_api_*.err.log' -or
            $_.Name -like '_codex_*.log' -or
            $_.Name -like '_codex_*.out.log' -or
            $_.Name -like '_codex_*.err.log'
        } |
        ForEach-Object {
            Add-Finding -Category 'DesktopAppLogCapture' -Path $_.FullName -Reason 'DesktopApp root API validation captures should be under RunLogs or removed.'
        }
}

Get-ChildItem -LiteralPath $repoRoot -Force -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '.pytest_cache' } |
    ForEach-Object {
        Add-Finding -Category 'PytestCache' -Path $_.FullName -Reason 'Pytest cache is rebuildable and should not live in the working tree.'
    }

if ($IncludeBuildArtifacts) {
    $tauriArtifacts = @(
        (Join-Path $repoRoot 'DesktopApp\tauri_shell\node_modules'),
        (Join-Path $repoRoot 'DesktopApp\tauri_shell\src-tauri\target')
    )
    foreach ($artifactPath in $tauriArtifacts) {
        if (Test-Path -LiteralPath $artifactPath -PathType Container) {
            Add-Finding -Category 'TauriBuildArtifact' -Path $artifactPath -Reason 'Tauri dependency/build output is rebuildable and should stay out of the repo snapshot.'
        }
    }
}

if ($IncludePythonBytecode) {
    Get-ChildItem -LiteralPath $repoRoot -Force -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq '__pycache__' } |
        ForEach-Object {
            Add-Finding -Category 'PythonBytecode' -Path $_.FullName -Reason 'Python bytecode cache is rebuildable.'
        }
}

if ($IncludeRunLogs) {
    $runLogRoots = @(
        (Join-Path $repoRoot 'RunLogs'),
        (Join-Path $repoRoot 'DesktopApp\RunLogs')
    )
    foreach ($runLogRoot in $runLogRoots) {
        if (Test-Path -LiteralPath $runLogRoot -PathType Container) {
            Get-ChildItem -LiteralPath $runLogRoot -Force -File -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like '*.log' } |
                ForEach-Object {
                    Add-Finding -Category 'RunLogCapture' -Path $_.FullName -Reason 'Runtime log capture is useful locally but should not be committed.'
                }
        }
    }
}

if ($findings.Count -gt 0) {
    Write-Host "Repo hygiene checks found $($findings.Count) generated artifact or ignore-rule issue(s):"
    $findings |
        Sort-Object Category, Path |
        Format-Table -AutoSize
    exit 1
}

Write-Host 'Repo hygiene checks passed.'
