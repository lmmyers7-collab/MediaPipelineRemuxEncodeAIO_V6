[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$Id = "",
    [Parameter(Mandatory = $true)][string]$SourceFolder,
    [Parameter(Mandatory = $true)][string]$SourceFile,
    [Parameter(Mandatory = $true)][string]$ExpectedName,
    [string]$ExpectedShow = "",
    [string]$ExpectedCleanFolder = "",
    [int]$ExpectedSeason = -1,
    [int]$SeasonNumber = 1,
    [ValidateSet("active", "pending")]
    [string]$Status = "active",
    [string]$Notes = "",
    [string]$FixturePath = "tests/fixtures/rename/bad_rename_cases.jsonl",
    [switch]$AllowCurrentMismatch
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$python = Join-Path $projectRoot 'apps\desktop\runtime\Python\python.exe'
$runner = Join-Path $projectRoot 'ops\scripts\dev\run-python-tool.py'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Bundled Python was not found: $python"
}
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "Python tool runner was not found: $runner"
}

$arguments = @(
    $runner,
    'mediapipeline.tools.dev.add_rename_filter_case',
    '--source-folder', $SourceFolder,
    '--source-file', $SourceFile,
    '--expected-name', $ExpectedName,
    '--season-number', ([string]$SeasonNumber),
    '--status', $Status,
    '--fixture-path', $FixturePath
)

if ($Id) { $arguments += @('--id', $Id) }
if ($ExpectedShow) { $arguments += @('--expected-show', $ExpectedShow) }
if ($ExpectedCleanFolder) { $arguments += @('--expected-clean-folder', $ExpectedCleanFolder) }
if ($ExpectedSeason -ge 0) { $arguments += @('--expected-season', ([string]$ExpectedSeason)) }
if ($Notes) { $arguments += @('--notes', $Notes) }
if ($AllowCurrentMismatch) { $arguments += '--allow-current-mismatch' }

& $python @arguments
