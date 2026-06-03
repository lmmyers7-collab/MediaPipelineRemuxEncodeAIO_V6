[CmdletBinding()]
param()

# ==============================================================================
# Invoke-RuntimeConfigResolutionChecks.ps1
# ------------------------------------------------------------------------------
# Regression coverage for config resolution after it was extracted into
# Initialize-MediaPipelineRuntimeConfig (engine\config\runtime_config.ps1).
# Drives MediaPipeline.ps1 -DumpEffectiveConfigPath against fixture configs and
# asserts the resolved values + the reserved-key guard. Locks in:
#   - HIGH-1  reserved PowerShell variable names are not published as config vars
#   - cross-key defaults (FFmpegCpuEncodeTimeoutSeconds = 2x; OutsourceMinFreeSpaceGB = MinFreeSpaceGB)
#   - MEDIUM-4 partial/field-missing progress file loads as 0 instead of crashing
# ==============================================================================

$ErrorActionPreference = 'Stop'

$testsRoot   = Split-Path -Parent $PSCommandPath
$unitRoot    = $testsRoot
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $unitRoot)
$projectRoot = Split-Path -Parent $pipelineRoot

$bundledPwshPath = Join-Path $pipelineRoot 'PowerShell-7.6.0-win-x64\pwsh.exe'
$ffmpegPath  = Join-Path $pipelineRoot 'Tools\ffmpeg\bin\ffmpeg.exe'
$ffprobePath = Join-Path $pipelineRoot 'Tools\ffmpeg\bin\ffprobe.exe'
$scriptPath  = Join-Path $pipelineRoot 'MediaPipeline.ps1'

$missing = @()
foreach ($tool in @(
    @{ Name = 'PowerShell'; Path = $bundledPwshPath },
    @{ Name = 'MediaPipeline.ps1'; Path = $scriptPath })) {
    if (-not (Test-Path -LiteralPath $tool.Path)) { $missing += "$($tool.Name) ($($tool.Path))" }
}
if ($missing.Count -gt 0) {
    Write-Host ("SKIP: runtime-config resolution checks require: {0}" -f ($missing -join ', '))
    return
}

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "ASSERT FAILED: $Message" }
}

function ConvertTo-Psd1Literal {
    param($Value)
    if ($null -eq $Value) { return '$null' }
    if ($Value -is [bool]) { return $(if ($Value) { '$true' } else { '$false' }) }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) { return ([string]$Value) }
    if ($Value -is [System.Collections.IDictionary]) {
        $items = foreach ($key in $Value.Keys) { "        $key = $(ConvertTo-Psd1Literal -Value $Value[$key])" }
        return "@{`n$($items -join [Environment]::NewLine)`n    }"
    }
    if ($Value -is [array]) {
        $items = @($Value | ForEach-Object { ConvertTo-Psd1Literal -Value $_ })
        return '@(' + ($items -join ', ') + ')'
    }
    $escaped = ([string]$Value) -replace "'", "''"
    return "'$escaped'"
}

function Write-FixtureConfig {
    param([hashtable]$Config, [string]$Path)
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('@{')
    foreach ($key in @($Config.Keys | Sort-Object)) {
        $lines.Add("    $key = $(ConvertTo-Psd1Literal -Value $Config[$key])")
    }
    $lines.Add('}')
    [System.IO.File]::WriteAllText($Path, ($lines -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
}

. (Join-Path $projectRoot 'engine\config\config_schema.ps1')

function New-FixtureConfig {
    param([string]$WorkRoot)
    $sourceMovies = Join-Path $WorkRoot 'SourceMovies'
    $sourceTv     = Join-Path $WorkRoot 'SourceTV'
    $outsource    = Join-Path $WorkRoot 'Outsource'
    $localBase    = Join-Path $WorkRoot 'LocalBase'
    New-Item -ItemType Directory -Path $sourceMovies, $sourceTv, $outsource, $localBase -Force | Out-Null

    $config = [hashtable](Get-MediaPipelineConfigDefaultValues)
    $config['SourceMovies'] = $sourceMovies
    $config['SourceTV']     = $sourceTv
    $config['Outsource']    = $outsource
    $config['LocalBase']    = $localBase
    foreach ($profile in @($config['LibraryProfiles'])) {
        if (-not ($profile -is [System.Collections.IDictionary])) { continue }
        $designation = [string]$profile['designation']; $id = [string]$profile['id']
        if ($designation -eq 'movie' -or $id -eq 'movies') { $profile['source_path'] = $sourceMovies; $profile['output_path'] = $outsource }
        elseif ($designation -eq 'tv' -or $id -eq 'tv')     { $profile['source_path'] = $sourceTv;     $profile['output_path'] = $outsource }
    }
    return @{ Config = $config; LocalBase = $localBase }
}

function Invoke-DumpRun {
    param([string]$ConfigPath, [string]$DumpPath, [string[]]$ExtraArgs = @())
    $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = [guid]::NewGuid().ToString('N')
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $scriptPath,
                 '-ConfigPath', $ConfigPath, '-DumpEffectiveConfigPath', $DumpPath) + $ExtraArgs
    $output = & $bundledPwshPath @argList 2>&1 | ForEach-Object { [string]$_ }
    return @{ ExitCode = $LASTEXITCODE; Output = ($output -join [Environment]::NewLine) }
}

$failures = 0
$workRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-cfgres-" + [guid]::NewGuid().ToString('N'))
$prevMutexSuffix = $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX
New-Item -ItemType Directory -Path $workRoot -Force | Out-Null
try {
    # ---- Scenario A: reserved-key guard + cross-key defaults -----------------
    $a = New-FixtureConfig -WorkRoot (Join-Path $workRoot 'A')
    $cfgA = $a.Config
    $cfgA['ErrorActionPreference'] = 'Continue'   # reserved name - must be ignored
    $cfgA['FFmpegEncodeTimeoutSeconds'] = 1000     # CPU default should derive to 2000
    $cfgA.Remove('FFmpegCpuEncodeTimeoutSeconds') | Out-Null
    $cfgA['MinFreeSpaceGB'] = 7
    $cfgA['OutsourceMinFreeSpaceGB'] = 0           # should fall back to MinFreeSpaceGB (7)
    $cfgPathA = Join-Path $workRoot 'configA.psd1'
    $dumpA    = Join-Path $workRoot 'dumpA.json'
    Write-FixtureConfig -Config $cfgA -Path $cfgPathA
    $runA = Invoke-DumpRun -ConfigPath $cfgPathA -DumpPath $dumpA

    if ($runA.ExitCode -ne 0) { Write-Host "FAIL [A] dump run exit $($runA.ExitCode)`n$($runA.Output)"; $failures++ }
    elseif (-not (Test-Path -LiteralPath $dumpA)) { Write-Host "FAIL [A] dump not written"; $failures++ }
    else {
        $d = Get-Content -LiteralPath $dumpA -Raw | ConvertFrom-Json
        try {
            Assert-True ($runA.Output -match 'collides with a reserved PowerShell variable') 'reserved-key warning not emitted'
            Assert-True ([int]$d.FFmpegCpuEncodeTimeoutSeconds -eq 2000) "FFmpegCpuEncodeTimeoutSeconds expected 2000, got $($d.FFmpegCpuEncodeTimeoutSeconds)"
            Assert-True ([int]$d.OutsourceMinFreeSpaceGB -eq 7) "OutsourceMinFreeSpaceGB expected 7, got $($d.OutsourceMinFreeSpaceGB)"
            Assert-True ([int]$d.FFmpegEncodeTimeoutSeconds -eq 1000) "FFmpegEncodeTimeoutSeconds expected 1000, got $($d.FFmpegEncodeTimeoutSeconds)"
            Assert-True (@($d.PSObject.Properties.Name).Count -ge 99) "dump field count too low: $(@($d.PSObject.Properties.Name).Count)"
            Write-Host "PASS [A] reserved-key guard + cross-key defaults"
        } catch { Write-Host "FAIL [A] $_"; $failures++ }
    }

    # ---- Scenario B: partial progress file loads as 0, no crash --------------
    $b = New-FixtureConfig -WorkRoot (Join-Path $workRoot 'B')
    $cfgB = $b.Config
    $cfgPathB = Join-Path $workRoot 'configB.psd1'
    $dumpB    = Join-Path $workRoot 'dumpB.json'
    Write-FixtureConfig -Config $cfgB -Path $cfgPathB
    # Pre-seed a truncated/field-missing progress file at the canonical path.
    $progressDir = Join-Path $b.LocalBase 'State\Progress'
    New-Item -ItemType Directory -Path $progressDir -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $progressDir 'pipeline_progress.json'), '{"Encoded":5}', [System.Text.UTF8Encoding]::new($false))
    $runB = Invoke-DumpRun -ConfigPath $cfgPathB -DumpPath $dumpB

    if ($runB.ExitCode -ne 0) { Write-Host "FAIL [B] dump run exit $($runB.ExitCode)`n$($runB.Output)"; $failures++ }
    else {
        try {
            Assert-True ($runB.Output -match 'Loaded previous progress: 0 files') 'partial progress did not load counters as 0'
            Assert-True (-not ($runB.Output -match 'Could not load progress file')) 'partial progress incorrectly reported as unreadable'
            Write-Host "PASS [B] partial progress file recovery"
        } catch { Write-Host "FAIL [B] $_"; $failures++ }
    }
} finally {
    if ($null -eq $prevMutexSuffix) { Remove-Item Env:\MEDIA_PIPELINE_TEST_MUTEX_SUFFIX -ErrorAction SilentlyContinue }
    else { $env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX = $prevMutexSuffix }
    Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures -gt 0) { throw "Runtime-config resolution checks FAILED ($failures)" }
Write-Host "Runtime-config resolution checks passed."
