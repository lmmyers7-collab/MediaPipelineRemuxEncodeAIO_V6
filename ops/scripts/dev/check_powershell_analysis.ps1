param(
    [string]$Path = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if ([string]::IsNullOrWhiteSpace($Path)) {
    $Path = Join-Path $RepoRoot "ops\pipeline\engine"
} elseif (-not [System.IO.Path]::IsPathRooted($Path)) {
    $Path = Join-Path $RepoRoot $Path
}

$ResolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
if ($null -eq $ResolvedPath) {
    Write-Error "PSScriptAnalyzer target path not found: $Path"
    exit 1
}
$Path = $ResolvedPath.ProviderPath

$Analyzer = Get-Module -ListAvailable -Name PSScriptAnalyzer | Select-Object -First 1
if ($null -eq $Analyzer) {
    Write-Warning "PSScriptAnalyzer is not installed; skipping PowerShell analysis for $Path."
    exit 0
}

Import-Module PSScriptAnalyzer -ErrorAction Stop
$Findings = Invoke-ScriptAnalyzer -Path $Path -Recurse -Severity Error
if ($Findings) {
    $Findings | Format-Table -AutoSize | Out-String | Write-Error
    exit 1
}

Write-Host "PSScriptAnalyzer passed for $Path"
