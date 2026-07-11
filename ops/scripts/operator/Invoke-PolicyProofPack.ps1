[CmdletBinding()]
param(
    [ValidateSet('verify', 'materialize', 'run')]
    [string]$Action = 'verify',
    [string]$RunId = '',
    [string]$FixtureRoot = '',
    [string]$Catalog = '',
    [string]$Ffprobe = '',
    [switch]$Rebuild,
    [switch]$ReportOnly
)

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$python = Join-Path $repoRoot 'apps\desktop\runtime\Python\python.exe'
$runner = Join-Path $repoRoot 'ops\scripts\dev\run-python-tool.py'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Bundled Python is missing: $python"
}
if (($Action -eq 'materialize' -or $Action -eq 'run') -and [string]::IsNullOrWhiteSpace($RunId)) {
    throw '-RunId is required for materialize and run actions.'
}

$arguments = @($runner, 'mediapipeline.tools.dev.policy_proof_pack', $Action)
if ($RunId) { $arguments += @('--run-id', $RunId) }
if ($FixtureRoot) { $arguments += @('--fixture-root', $FixtureRoot) }
if ($Catalog) { $arguments += @('--catalog', $Catalog) }
if ($Ffprobe) { $arguments += @('--ffprobe', $Ffprobe) }
if ($Rebuild) { $arguments += '--rebuild' }
if ($ReportOnly) { $arguments += '--report-only' }

& $python @arguments
exit $LASTEXITCODE
