[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Release package policy checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot
$releasePolicyPath = Join-Path $repoRoot 'scripts\release\release_policy.ps1'
$backupScriptPath = Join-Path $repoRoot 'scripts\release\Backup-PreOverhaul.ps1'

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Contains {
    param(
        [string] $Text,
        [string] $Needle,
        [string] $Message
    )
    Assert-True ($Text.Contains($Needle)) $Message
}

function Assert-ReleaseExclusion {
    param(
        [string] $RelativePath,
        [string] $ExpectedReason
    )
    $actual = Get-MediaPipelineReleaseExclusionReason -RelativePath $RelativePath
    Assert-True ($actual -eq $ExpectedReason) "Expected '$RelativePath' exclusion reason '$ExpectedReason'; got '$actual'."
}

Assert-True (Test-Path -LiteralPath $releasePolicyPath -PathType Leaf) 'release_policy.ps1 is missing.'
Assert-True (Test-Path -LiteralPath $backupScriptPath -PathType Leaf) 'Backup-PreOverhaul.ps1 is missing.'

. $releasePolicyPath

Assert-ReleaseExclusion -RelativePath 'node_modules\eslint\bin\eslint.js' -ExpectedReason 'node modules omitted'
Assert-ReleaseExclusion -RelativePath 'tools\node_modules\package\index.js' -ExpectedReason 'node modules omitted'
Assert-ReleaseExclusion -RelativePath 'DesktopApp\tauri_shell\node_modules\package\index.js' -ExpectedReason 'tauri node modules omitted'
Assert-ReleaseExclusion -RelativePath 'DesktopApp\tauri_shell\src-tauri\target\release\app.exe' -ExpectedReason 'tauri rust build output omitted'
Assert-ReleaseExclusion -RelativePath 'CodexVerification\run.jsonl' -ExpectedReason 'local verification evidence'
Assert-ReleaseExclusion -RelativePath 'LocalBase\State\pipeline_progress.json' -ExpectedReason 'local runtime state'
Assert-ReleaseExclusion -RelativePath 'Pipeline\MediaPipeline_config.psd1' -ExpectedReason 'personal live config'

$hygieneRules = @(
    Get-MediaPipelineReleaseHygieneRules `
        -PersonalConfigIncluded:$false `
        -DevDocsIncluded:$false `
        -OptionalToolsIncluded:$false `
        -ToolDocsIncluded:$false `
        -TauriPreviewBinaryIncluded:$false
)
$rulePaths = @(
    $hygieneRules |
        Where-Object { $_.kind -in @('path_absent', 'path_present') } |
        ForEach-Object { $_.relative_path }
)
Assert-True ($rulePaths -contains 'node_modules') 'Release hygiene rules must reject root node_modules.'
Assert-True ($rulePaths -contains 'DesktopApp\tauri_shell\node_modules') 'Release hygiene rules must reject Tauri node_modules.'
Assert-True ($rulePaths -contains 'Pipeline\MediaPipeline_config.psd1') 'Release hygiene rules must reject the active live config by default.'

$policyManifest = Get-MediaPipelineReleasePolicyManifest
Assert-True ($policyManifest.schema_version -eq 'mediapipeline_release_policy.v1') 'Release policy manifest schema drifted.'
Assert-True ($policyManifest.hygiene_rule_count -eq $hygieneRules.Count) 'Release policy manifest hygiene rule count drifted.'

$backupScriptText = Get-Content -LiteralPath $backupScriptPath -Raw
Assert-Contains $backupScriptText '& $buildScript -DestinationRoot $ReleaseDir -Verify -Zip' 'Backup script must call the canonical release builder for the release copy.'
Assert-True (-not $backupScriptText.Contains('New-Item -ItemType Directory -Path $ReleaseDir')) 'Backup script must not pre-create the release destination before invoking build.ps1.'

Write-Host 'Release package policy checks passed.'
