param(
    [string]$Path = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if ([string]::IsNullOrWhiteSpace($Path)) {
    $Path = Join-Path $RepoRoot "engine"
}

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Host "PSScriptAnalyzer skipped: path not found: $Path"
    exit 0
}

$Analyzer = Get-Module -ListAvailable -Name PSScriptAnalyzer | Select-Object -First 1
if ($null -eq $Analyzer) {
    Write-Warning "PSScriptAnalyzer is not installed; skipping engine PowerShell analysis."
    exit 0
}

Import-Module PSScriptAnalyzer -ErrorAction Stop
$Findings = Invoke-ScriptAnalyzer -Path $Path -Recurse -Severity Error
if ($Findings) {
    $Findings | Format-Table -AutoSize | Out-String | Write-Error
    exit 1
}

Write-Host "PSScriptAnalyzer passed for $Path"
