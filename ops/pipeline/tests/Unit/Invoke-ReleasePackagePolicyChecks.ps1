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
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$releasePolicyPath = Join-Path $repoRoot 'ops\scripts\release\release_policy.ps1'
$buildScriptPath = Join-Path $repoRoot 'ops\scripts\release\build.ps1'
$backupScriptPath = Join-Path $repoRoot 'ops\scripts\release\Backup-PreOverhaul.ps1'
$setupLauncherPath = Join-Path $repoRoot 'ops\scripts\dev\setup.bat'
$runLauncherPath = Join-Path $repoRoot 'ops\scripts\dev\run.bat'
$gitignorePath = Join-Path $repoRoot '.gitignore'
$rgignorePath = Join-Path $repoRoot '.rgignore'
$releaseManifestPath = Join-Path $repoRoot 'release_manifest.json'
$inReleasePackage = Test-Path -LiteralPath $releaseManifestPath -PathType Leaf

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

function Assert-ThrowsContaining {
    param(
        [scriptblock] $Action,
        [string] $ExpectedText,
        [string] $Message
    )
    try {
        & $Action
    } catch {
        $actual = [string]$_.Exception.Message
        Assert-True ($actual.Contains($ExpectedText)) "$Message Expected message containing '$ExpectedText'; got '$actual'."
        return
    }
    throw $Message
}

function Assert-ReleaseBuildRejectsDestination {
    param(
        [string] $DestinationRoot,
        [string] $ExpectedText
    )
    Assert-ThrowsContaining `
        -Action { & $buildScriptPath -DestinationRoot $DestinationRoot -DryRun } `
        -ExpectedText $ExpectedText `
        -Message "Release build should reject destination '$DestinationRoot'."
}

function Assert-ReleaseBuildRejectsReplacement {
    param(
        [string] $DestinationRoot,
        [string] $ExpectedText
    )
    Assert-ThrowsContaining `
        -Action { & $buildScriptPath -DestinationRoot $DestinationRoot -Force } `
        -ExpectedText $ExpectedText `
        -Message "Release build should reject replacement destination '$DestinationRoot'."
}

function Assert-NoLocalMachinePathLeaks {
    $changePacketRoot = Join-Path $repoRoot 'ops\release\changes\unreleased'
    $patterns = @(
        '(?i)[a-z]:[\\/]+users[\\/]+',
        '(?i)appdata[\\/]+local[\\/]+temp',
        '(?i)onedrive[\\/]+desktop'
    )
    foreach ($packet in @(Get-ChildItem -LiteralPath $changePacketRoot -Filter '*.json' -File)) {
        $text = Get-Content -LiteralPath $packet.FullName -Raw
        foreach ($pattern in $patterns) {
            Assert-True (-not [regex]::IsMatch($text, $pattern)) "Change packet contains a local workstation path that must be redacted: $($packet.Name)"
        }
    }
}

function ConvertTo-StringArray {
    param($Value)

    if ($null -eq $Value) { return @() }
    return @($Value | ForEach-Object { [string]$_ })
}

function Assert-SequenceEqual {
    param(
        $Actual,
        $Expected,
        [string] $Label
    )

    $actualValues = @(ConvertTo-StringArray -Value $Actual)
    $expectedValues = @(ConvertTo-StringArray -Value $Expected)
    Assert-True ($actualValues.Count -eq $expectedValues.Count) "$Label count drifted. Actual=$($actualValues.Count) Expected=$($expectedValues.Count)"
    for ($i = 0; $i -lt $expectedValues.Count; $i++) {
        Assert-True ([string]$actualValues[$i] -ceq [string]$expectedValues[$i]) "$Label drifted at index $i. Actual='$($actualValues[$i])' Expected='$($expectedValues[$i])'"
    }
}

function Assert-MapContainsKey {
    param(
        $Map,
        [string] $Key,
        [string] $Message
    )

    Assert-True ($null -ne $Map) $Message
    try {
        Assert-True ([bool]$Map.Contains($Key)) $Message
    } catch {
        throw $Message
    }
}

function Get-SortedMapKeys {
    param($Map)

    if ($null -eq $Map) { return @() }
    try {
        return @($Map.Keys | ForEach-Object { [string]$_ } | Sort-Object)
    } catch {
        return @()
    }
}

function Get-CustomRenameFilterBaseline {
    param(
        [string] $RelativePath,
        [string] $Label
    )

    $path = Join-Path $repoRoot $RelativePath
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "$Label must be present: $RelativePath"
    $config = Import-PowerShellDataFile -Path $path
    foreach ($key in @('RenameMovieFilterOptions', 'RenameMovieFilterTerms', 'RenameMovieRemoveTerms')) {
        Assert-MapContainsKey -Map $config -Key $key -Message "$Label must keep packaged custom rename filter key '$key'."
    }

    $options = $config['RenameMovieFilterOptions']
    $terms = $config['RenameMovieFilterTerms']
    $categories = @(Get-SortedMapKeys -Map $options)
    Assert-True ($categories.Count -gt 0) "$Label RenameMovieFilterOptions must include at least one packaged custom category."
    Assert-SequenceEqual -Actual (Get-SortedMapKeys -Map $terms) -Expected $categories -Label "$Label RenameMovieFilterTerms categories"
    foreach ($category in $categories) {
        Assert-True ($options[$category] -is [bool]) "$Label RenameMovieFilterOptions.$category must be a boolean."
        Assert-MapContainsKey -Map $terms -Key $category -Message "$Label RenameMovieFilterTerms missing category '$category'."
        Assert-True (@(ConvertTo-StringArray -Value $terms[$category]).Count -gt 0) "$Label RenameMovieFilterTerms.$category must keep the packaged custom term list."
    }

    return [pscustomobject]@{
        Categories = $categories
        Options = $options
        Terms = $terms
        RemoveTerms = @(ConvertTo-StringArray -Value $config['RenameMovieRemoveTerms'])
    }
}

function Assert-CustomRenameFilterConfig {
    param(
        [string] $RelativePath,
        [string] $Label,
        $ExpectedOptions,
        $ExpectedTerms,
        $ExpectedRemoveTerms,
        [string[]] $ExpectedCategories
    )

    $path = Join-Path $repoRoot $RelativePath
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "$Label must be present: $RelativePath"
    $config = Import-PowerShellDataFile -Path $path
    foreach ($key in @('RenameMovieFilterOptions', 'RenameMovieFilterTerms', 'RenameMovieRemoveTerms')) {
        Assert-MapContainsKey -Map $config -Key $key -Message "$Label must keep packaged custom rename filter key '$key'."
    }

    $options = $config['RenameMovieFilterOptions']
    $terms = $config['RenameMovieFilterTerms']
    Assert-SequenceEqual -Actual (Get-SortedMapKeys -Map $options) -Expected $ExpectedCategories -Label "$Label RenameMovieFilterOptions categories"
    Assert-SequenceEqual -Actual (Get-SortedMapKeys -Map $terms) -Expected $ExpectedCategories -Label "$Label RenameMovieFilterTerms categories"
    foreach ($category in $ExpectedCategories) {
        Assert-MapContainsKey -Map $options -Key $category -Message "$Label RenameMovieFilterOptions missing category '$category'."
        Assert-True ($options[$category] -is [bool]) "$Label RenameMovieFilterOptions.$category must be a boolean."
        Assert-True ([bool]$options[$category] -eq [bool]$ExpectedOptions[$category]) "$Label RenameMovieFilterOptions.$category drifted."

        Assert-MapContainsKey -Map $terms -Key $category -Message "$Label RenameMovieFilterTerms missing category '$category'."
        Assert-SequenceEqual -Actual $terms[$category] -Expected $ExpectedTerms[$category] -Label "$Label RenameMovieFilterTerms.$category"
    }

    Assert-SequenceEqual -Actual $config['RenameMovieRemoveTerms'] -Expected $ExpectedRemoveTerms -Label "$Label RenameMovieRemoveTerms"
}

Assert-True (Test-Path -LiteralPath $releasePolicyPath -PathType Leaf) 'release_policy.ps1 is missing.'
Assert-True (Test-Path -LiteralPath $buildScriptPath -PathType Leaf) 'build.ps1 is missing.'
Assert-True (Test-Path -LiteralPath $backupScriptPath -PathType Leaf) 'Backup-PreOverhaul.ps1 is missing.'
Assert-True (Test-Path -LiteralPath $setupLauncherPath -PathType Leaf) 'ops\scripts\dev\setup.bat is missing.'
Assert-True (Test-Path -LiteralPath $runLauncherPath -PathType Leaf) 'ops\scripts\dev\run.bat is missing.'
if ($inReleasePackage) {
    Assert-True (-not (Test-Path -LiteralPath $gitignorePath -PathType Leaf)) '.gitignore must be omitted from release packages as source-control metadata.'
} else {
    Assert-True (Test-Path -LiteralPath $gitignorePath -PathType Leaf) '.gitignore is missing.'
}
Assert-True (Test-Path -LiteralPath $rgignorePath -PathType Leaf) '.rgignore is missing.'

$buildScriptText = Get-Content -LiteralPath $buildScriptPath -Raw
Assert-Contains $buildScriptText 'Test-ReleaseDestinationHasInProgressMarker' 'Release builder must recognize interrupted package destinations.'
Assert-Contains $buildScriptText 'mediapipeline_release_in_progress.v1' 'Release builder must write a schema-versioned in-progress marker.'
Assert-Contains $buildScriptText 'Remove-Item -LiteralPath $inProgressMarkerPath' 'Release builder must remove the in-progress marker after writing the final manifest.'
Assert-Contains $buildScriptText 'KeepPersonalConfig cannot be combined with -Zip' 'Release builder must reject zipped personal mirrors.'
Assert-Contains $buildScriptText '[switch]$AllowTestlessVerify' 'Release builder must expose an explicit dev-only testless verify escape hatch.'
Assert-Contains $buildScriptText 'Release verification requires -IncludeTests' 'Release builder must require included tests for verified release packages by default.'
Assert-Contains $buildScriptText 'This is not release acceptance.' 'Release builder must label testless verification as non-release acceptance.'
Assert-Contains $buildScriptText 'Test-ReleaseTraversalDirectoryPruned' 'Release builder must prune known excluded directories before recursive package traversal.'
Assert-Contains $buildScriptText 'Get-ReleaseSourceFileItems' 'Release builder must use the pruned release source traversal helper.'
Assert-Contains $buildScriptText 'function Update-ReleasePackageGeneratedIndexes' 'Release builder must refresh package-specific generated indexes after exclusions are applied.'
Assert-Contains $buildScriptText 'mediapipeline.tools.dev.generate_project_index' 'Release builder must regenerate the package project index through the bundled tool runner.'
Assert-Contains $buildScriptText 'mediapipeline.tools.dev.generate_feature_file_map' 'Release builder must regenerate the package feature map after refreshing the project index.'
Assert-Contains $buildScriptText 'Update-ReleasePackageGeneratedIndexes -ReleaseRoot $destinationFull' 'Release builder must refresh package-specific generated indexes before verification.'
Assert-True (-not $buildScriptText.Contains('Get-ChildItem -LiteralPath $script:SourceRoot -Recurse -File -Force')) 'Release builder must not recurse through every source file before applying package exclusions.'

$rgignoreText = Get-Content -LiteralPath $rgignorePath -Raw
if (-not $inReleasePackage) {
    $gitignoreText = Get-Content -LiteralPath $gitignorePath -Raw
    Assert-Contains $gitignoreText 'docs/PG3CleanMachineReports/' 'Git ignore rules must exclude generated PG-3 clean-machine reports.'
}
Assert-Contains $rgignoreText 'docs/PG3CleanMachineReports/' 'Search ignore rules must exclude generated PG-3 clean-machine reports.'

$backupScriptText = Get-Content -LiteralPath $backupScriptPath -Raw
Assert-Contains $backupScriptText '-Verify -Zip -IncludeTests' 'Backup helper release build must include tests when verification is requested.'
Assert-Contains $backupScriptText 'GetFullPath($Destination)' 'Backup helper must resolve Destination with System.IO.Path.GetFullPath.'
foreach ($needle in @(
    'Test-Path -LiteralPath $Destination',
    'Get-ChildItem -LiteralPath $Destination -Recurse -File',
    'Set-Content -LiteralPath $ManifestPath',
    'Get-FileHash -Algorithm SHA256 -LiteralPath $Path',
    'Push-Location -LiteralPath $RepoRoot',
    'Get-ChildItem -LiteralPath $stateSource',
    'Copy-Item -LiteralPath $_.FullName'
)) {
    Assert-Contains $backupScriptText $needle "Backup helper must use literal path form: $needle"
}
Assert-True (-not $backupScriptText.Contains('Get-ChildItem -Path $Destination')) 'Backup helper must not enumerate Destination through wildcard-aware -Path.'
Assert-True (-not $backupScriptText.Contains('Set-Content -Path $ManifestPath')) 'Backup helper must not write manifest through wildcard-aware -Path.'
$literalBackupDestination = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-backup-[literal]-' + [guid]::NewGuid().ToString('N'))
try {
    & $backupScriptPath -Destination $literalBackupDestination -Tag 'HEAD' -SkipReleaseBuild -SkipStateSnapshot -DryRun | Out-Null
    Assert-True (-not (Test-Path -LiteralPath $literalBackupDestination)) 'Backup dry-run must not create the literal bracket destination.'
} finally {
    Remove-Item -LiteralPath $literalBackupDestination -Recurse -Force -ErrorAction SilentlyContinue
}

. $releasePolicyPath

$customRenameFilterBaseline = Get-CustomRenameFilterBaseline `
    -RelativePath 'ops\pipeline\config\MediaPipeline_config_template.psd1' `
    -Label 'Config template'
Assert-CustomRenameFilterConfig `
    -RelativePath 'ops\pipeline\config\MediaPipeline_config_template.psd1' `
    -Label 'Config template' `
    -ExpectedOptions $customRenameFilterBaseline.Options `
    -ExpectedTerms $customRenameFilterBaseline.Terms `
    -ExpectedRemoveTerms $customRenameFilterBaseline.RemoveTerms `
    -ExpectedCategories $customRenameFilterBaseline.Categories
Assert-CustomRenameFilterConfig `
    -RelativePath 'ops\pipeline\config\profiles\Default.psd1' `
    -Label 'Default config profile' `
    -ExpectedOptions $customRenameFilterBaseline.Options `
    -ExpectedTerms $customRenameFilterBaseline.Terms `
    -ExpectedRemoveTerms $customRenameFilterBaseline.RemoveTerms `
    -ExpectedCategories $customRenameFilterBaseline.Categories

Assert-ReleaseExclusion -RelativePath '.github\workflows\ci.yml' -ExpectedReason 'source-control metadata'
Assert-ReleaseExclusion -RelativePath '.gitattributes' -ExpectedReason 'source-control metadata'
Assert-ReleaseExclusion -RelativePath '.codex\state.json' -ExpectedReason 'local assistant metadata'
Assert-ReleaseExclusion -RelativePath '.codex-plugin\plugin.json' -ExpectedReason 'local assistant metadata'
Assert-ReleaseExclusion -RelativePath 'node_modules\eslint\bin\eslint.js' -ExpectedReason 'node modules omitted'
Assert-ReleaseExclusion -RelativePath 'tools\node_modules\package\index.js' -ExpectedReason 'node modules omitted'
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\node_modules\package\index.js' -ExpectedReason 'tauri node modules omitted'
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\src-tauri\target\release\app.exe' -ExpectedReason 'tauri rust build output omitted'
Assert-ReleaseExclusion -RelativePath 'CodexVerification\run.jsonl' -ExpectedReason 'local verification evidence'
Assert-ReleaseExclusion -RelativePath 'LocalBase\State\pipeline_progress.json' -ExpectedReason 'local runtime state'
Assert-ReleaseExclusion -RelativePath '.release_in_progress.json' -ExpectedReason 'partial release build marker'
Assert-ReleaseExclusion -RelativePath 'ops\pipeline\config\MediaPipeline_config.psd1' -ExpectedReason 'personal live config'
Assert-ReleaseExclusion -RelativePath 'ops\pipeline\config\MediaPipeline_config.backup_20260604_120000_000000.psd1' -ExpectedReason 'generated config backup'
Assert-ReleaseExclusion -RelativePath 'ops\pipeline\config\MediaPipeline_config_chatgpt.backup_20260604_120000_000000.psd1' -ExpectedReason 'generated config backup (legacy)'
Assert-ReleaseExclusion -RelativePath 'ops\pipeline\config\backups\MediaPipeline_config_chatgpt.backup_20260604_120000_000000.psd1' -ExpectedReason 'generated config backup'
Assert-ReleaseExclusion -RelativePath 'src\MediaPipelineRemuxEncodeAIO_DesktopApp.log' -ExpectedReason 'python source-tree runtime log'
Assert-ReleaseExclusion -RelativePath 'src\mediapipeline.egg-info\PKG-INFO' -ExpectedReason 'python packaging metadata'
Assert-ReleaseExclusion -RelativePath 'docs\archive\root-artifacts\codex-config.toml' -ExpectedReason 'local assistant root artifact'
Assert-ReleaseExclusion -RelativePath 'docs\reviews\function-module-audit-2026-06-11\workers\worker-08-webview-pages.md' -ExpectedReason 'active review/audit ledger omitted'
Assert-ReleaseExclusion -RelativePath 'CON' -ExpectedReason 'windows reserved device name'
Assert-ReleaseExclusion -RelativePath 'notes\AUX.txt' -ExpectedReason 'windows reserved device name'
Assert-ReleaseExclusion -RelativePath 'artifacts\LPT1\capture.txt' -ExpectedReason 'windows reserved device name'

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
$rulePatterns = @(
    $hygieneRules |
        Where-Object { $_.kind -eq 'pattern_absent' } |
        ForEach-Object { $_.relative_pattern }
)
Assert-True ($rulePaths -contains 'node_modules') 'Release hygiene rules must reject root node_modules.'
Assert-True ($rulePaths -contains '.github') 'Release hygiene rules must reject source-control workflow metadata.'
Assert-True ($rulePaths -contains '.codex') 'Release hygiene rules must reject local Codex metadata.'
Assert-True ($rulePaths -contains 'apps\desktop\tauri\node_modules') 'Release hygiene rules must reject Tauri node_modules.'
Assert-True ($rulePaths -contains 'ops\pipeline\config\MediaPipeline_config.psd1') 'Release hygiene rules must reject the active live config by default.'
Assert-True ($rulePaths -contains '.release_in_progress.json') 'Release hygiene rules must reject interrupted release markers.'
Assert-True ($rulePaths -contains 'docs\reviews') 'Release hygiene rules must reject active review ledgers.'
Assert-True ($rulePaths -contains 'docs\archive\root-artifacts') 'Release hygiene rules must reject local assistant root artifacts.'
Assert-True ($rulePaths -contains 'ops\pipeline\config\backups') 'Release hygiene rules must reject generated config backup folders.'
Assert-True ($rulePatterns -contains 'ops\pipeline\config\backups\*.psd1') 'Release hygiene rules must reject generated config backups in active backup folders.'
Assert-True ($rulePatterns -contains 'src\*.log') 'Release hygiene rules must reject source-tree runtime logs.'
Assert-True ($rulePatterns -contains 'src\*.egg-info\*') 'Release hygiene rules must reject Python packaging metadata.'

$policyManifest = Get-MediaPipelineReleasePolicyManifest
Assert-True ($policyManifest.schema_version -eq 'mediapipeline_release_policy.v1') 'Release policy manifest schema drifted.'
Assert-True ($policyManifest.hygiene_rule_count -eq $hygieneRules.Count) 'Release policy manifest hygiene rule count drifted.'

$repoParent = Split-Path -Parent $repoRoot
$personalZipDestination = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-release-policy-personal-zip-{0}' -f ([guid]::NewGuid().ToString('N')))
Assert-ThrowsContaining `
    -Action { & $buildScriptPath -DestinationRoot $personalZipDestination -KeepPersonalConfig -Zip -DryRun } `
    -ExpectedText 'KeepPersonalConfig cannot be combined with -Zip' `
    -Message 'Release builder should reject personal-config zip packages.'
Assert-ReleaseBuildRejectsDestination -DestinationRoot $repoRoot -ExpectedText 'source folder or a child'
Assert-ReleaseBuildRejectsDestination -DestinationRoot (Join-Path $repoRoot 'release-test') -ExpectedText 'source folder or a child'
Assert-ReleaseBuildRejectsDestination -DestinationRoot $repoParent -ExpectedText 'ancestor of the source folder'
Assert-ReleaseBuildRejectsDestination -DestinationRoot ([System.IO.Path]::GetPathRoot($repoRoot)) -ExpectedText 'filesystem root'
if ($env:USERPROFILE) {
    Assert-ReleaseBuildRejectsDestination -DestinationRoot $env:USERPROFILE -ExpectedText 'user profile root'
}
$validDryRunDestination = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-release-policy-valid-{0}' -f ([guid]::NewGuid().ToString('N')))
& $buildScriptPath -DestinationRoot $validDryRunDestination -DryRun | Out-Null

$unsafeReplacement = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-release-policy-unsafe-{0}' -f ([guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $unsafeReplacement -Force | Out-Null
Set-Content -LiteralPath (Join-Path $unsafeReplacement 'not-a-release.txt') -Value 'do not delete' -Encoding UTF8
try {
    Assert-ReleaseBuildRejectsReplacement -DestinationRoot $unsafeReplacement -ExpectedText 'without a MediaPipeline release manifest marker'
    Assert-True (Test-Path -LiteralPath (Join-Path $unsafeReplacement 'not-a-release.txt') -PathType Leaf) 'Unsafe replacement marker file should not be removed.'
} finally {
    Remove-Item -LiteralPath $unsafeReplacement -Recurse -Force -ErrorAction SilentlyContinue
}
Assert-NoLocalMachinePathLeaks

$backupScriptText = Get-Content -LiteralPath $backupScriptPath -Raw
Assert-Contains $backupScriptText '& $buildScript -DestinationRoot $ReleaseDir -Verify -Zip' 'Backup script must call the canonical release builder for the release copy.'
Assert-True (-not $backupScriptText.Contains('New-Item -ItemType Directory -Path $ReleaseDir')) 'Backup script must not pre-create the release destination before invoking build.ps1.'
Assert-Contains $backupScriptText "repo_root         = '<repo-root>'" 'Backup manifest must not persist the absolute repository root.'

$setupLauncherText = Get-Content -LiteralPath $setupLauncherPath -Raw
$runLauncherText = Get-Content -LiteralPath $runLauncherPath -Raw
foreach ($launcher in @(
    @{ Label = 'setup.bat'; Text = $setupLauncherText },
    @{ Label = 'run.bat'; Text = $runLauncherText }
)) {
    Assert-Contains $launcher.Text 'where pwsh.exe' "$($launcher.Label) must use cmd-native pwsh discovery."
    Assert-Contains $launcher.Text 'ERROR: PowerShell 7 was not found.' "$($launcher.Label) must fail explicitly when PS7 is unavailable."
    Assert-True (-not $launcher.Text.Contains('powershell.exe')) "$($launcher.Label) must not fall back to Windows PowerShell."
}

Write-Host 'Release package policy checks passed.'
