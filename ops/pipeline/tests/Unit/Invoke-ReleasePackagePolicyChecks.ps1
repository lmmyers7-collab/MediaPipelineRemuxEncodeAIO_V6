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
$releaseAdminInventoryPath = Join-Path $repoRoot 'docs\inventories\RELEASE_PACKAGE_ADMIN_INVENTORY.md'
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
        [string] $ExpectedReason,
        [bool] $IncludeTests = $false
    )
    $actual = Get-MediaPipelineReleaseExclusionReason -RelativePath $RelativePath -IncludeTests:$IncludeTests
    Assert-True ([string]$actual -eq [string]$ExpectedReason) "Expected '$RelativePath' exclusion reason '$ExpectedReason'; got '$actual'."
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
    # Unreleased change packets are categorically excluded. Their contents are
    # intentionally not a package-content assertion and may document local
    # validation context needed by the maintainer.
    return
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
Assert-True (Test-Path -LiteralPath $releaseAdminInventoryPath -PathType Leaf) 'Release package admin inventory is missing.'
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
Assert-True (-not $buildScriptText.Contains('Get-ChildItem -LiteralPath $script:SourceRoot -Recurse -File -Force')) 'Release builder must not recurse through every source file before applying package exclusions.'

$releaseAdminInventoryText = Get-Content -LiteralPath $releaseAdminInventoryPath -Raw
Assert-True (-not $releaseAdminInventoryText.Contains('-Zip -KeepPersonalConfig')) 'Release package admin inventory must not recommend the rejected zipped personal-mirror combination.'
Assert-Contains $releaseAdminInventoryText '`-KeepPersonalConfig` is directory-only and cannot be combined with `-Zip`.' 'Release package admin inventory must document that personal mirrors are directory-only.'

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
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\src-tauri\src\lib_tests\mod.rs' -ExpectedReason 'Tauri Rust test module omitted'
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\src-tauri\src\lib_tests\python_runtime.rs' -ExpectedReason 'Tauri Rust test module omitted'
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\src-tauri\src\backend_process\tests.rs' -ExpectedReason 'Tauri Rust test module omitted'
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\src-tauri\src\lib_tests\mod.rs' -ExpectedReason $null -IncludeTests:$true
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\src-tauri\src\backend_process\tests.rs' -ExpectedReason $null -IncludeTests:$true
Assert-ReleaseExclusion -RelativePath 'apps\desktop\tauri\src-tauri\src\backend_process.rs' -ExpectedReason $null

$tauriRustSource = @(
    Get-ChildItem -LiteralPath (Join-Path $repoRoot 'apps\desktop\tauri\src-tauri\src') -Recurse -File -Filter '*.rs' |
        ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }
) -join "`n"
Assert-True (-not [regex]::IsMatch($tauriRustSource, '(?i)LAYNE-SERVER|[A-Z]:\\Users\\Layne')) 'Tauri Rust source must not contain the audited personal server or user-profile identifiers.'
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
Assert-ReleaseExclusion -RelativePath 'ops\release\changes\unreleased\MP-CHANGE-2026-0710-010.json' -ExpectedReason 'unreleased change record omitted'
Assert-ReleaseExclusion -RelativePath 'docs\generated\summaries\ops\release\changes\unreleased\MP-CHANGE-2026-0710-010.json.md' -ExpectedReason 'unreleased change record summary omitted'
Assert-ReleaseExclusion -RelativePath 'ops\release\changes\archived\2026-07\MP-CHANGE-2026-0710-010.json' -ExpectedReason 'archived unreleased change record omitted'
Assert-ReleaseExclusion -RelativePath 'docs\generated\summaries\ops\release\changes\archived\2026-07\MP-CHANGE-2026-0710-010.json.md' -ExpectedReason 'archived unreleased change record summary omitted'
Assert-ReleaseExclusion -RelativePath 'ops\release\evidence\operator-proof.png' -ExpectedReason 'raw release evidence screenshot omitted'
Assert-ReleaseExclusion -RelativePath 'ops\release\evidence\operator-proof.JPEG' -ExpectedReason 'raw release evidence screenshot omitted'
Assert-ReleaseExclusion -RelativePath 'docs\testing\operator-proof.md' -ExpectedReason $null
Assert-ReleaseExclusion -RelativePath 'docs\archive\remediation-changelog\entries-0001-0250.md' -ExpectedReason 'historical remediation ledger segment omitted'
Assert-ReleaseExclusion -RelativePath 'docs\REMEDIATION_CHANGELOG.md' -ExpectedReason 'historical remediation ledger omitted'
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
Assert-True ($rulePaths -contains 'apps\desktop\tauri\src-tauri\src\lib_tests') 'Default release hygiene rules must reject Tauri Rust test modules.'
Assert-True ($rulePaths -contains 'apps\desktop\tauri\src-tauri\src\backend_process\tests.rs') 'Default release hygiene rules must reject Tauri backend-process Rust tests.'
Assert-True ($rulePaths -contains 'ops\pipeline\config\MediaPipeline_config.psd1') 'Release hygiene rules must reject the active live config by default.'
Assert-True ($rulePaths -contains '.release_in_progress.json') 'Release hygiene rules must reject interrupted release markers.'
Assert-True ($rulePaths -contains 'docs\reviews') 'Release hygiene rules must reject active review ledgers.'
Assert-True ($rulePaths -contains 'docs\archive\root-artifacts') 'Release hygiene rules must reject local assistant root artifacts.'
Assert-True ($rulePaths -contains 'ops\pipeline\config\backups') 'Release hygiene rules must reject generated config backup folders.'
Assert-True ($rulePatterns -contains 'ops\pipeline\config\backups\*.psd1') 'Release hygiene rules must reject generated config backups in active backup folders.'
Assert-True ($rulePatterns -contains 'src\*.log') 'Release hygiene rules must reject source-tree runtime logs.'
Assert-True ($rulePatterns -contains 'src\*.egg-info\*') 'Release hygiene rules must reject Python packaging metadata.'
Assert-True ($rulePatterns -contains 'ops\release\evidence\*.png') 'Release hygiene rules must reject raw PNG release evidence.'
Assert-True ($rulePatterns -contains 'ops\release\evidence\*.jpeg') 'Release hygiene rules must reject raw JPEG release evidence.'

$testPackageRulePaths = @(
    Get-MediaPipelineReleaseHygieneRules -TestsIncluded:$true |
        Where-Object { $_.kind -in @('path_absent', 'path_present') } |
        ForEach-Object { $_.relative_path }
)
Assert-True ($testPackageRulePaths -notcontains 'apps\desktop\tauri\src-tauri\src\lib_tests') 'IncludeTests package hygiene must retain Tauri Rust test modules.'
Assert-True ($testPackageRulePaths -notcontains 'apps\desktop\tauri\src-tauri\src\backend_process\tests.rs') 'IncludeTests package hygiene must retain Tauri backend-process Rust tests.'

$policyManifest = Get-MediaPipelineReleasePolicyManifest
Assert-True ($policyManifest.schema_version -eq 'mediapipeline_release_policy.v1') 'Release policy manifest schema drifted.'
Assert-True ($policyManifest.hygiene_rule_count -eq $hygieneRules.Count) 'Release policy manifest hygiene rule count drifted.'
Assert-True (Test-MediaPipelineReleaseContentAllowed -RelativePath 'docs\README.md' -Content 'Use C:\MediaPipeline\Incoming as the deployment template path.') 'Stable deployment template paths should remain package-safe.'
Assert-True (-not (Test-MediaPipelineReleaseContentAllowed -RelativePath 'docs\README.md' -Content 'Source path: C:\Users\operator\Videos')) 'User-profile paths must be rejected from package content.'
Assert-True (-not (Test-MediaPipelineReleaseContentAllowed -RelativePath 'docs\README.md' -Content 'Source path: \\private-server\media')) 'UNC paths must be rejected from package content.'
Assert-True (Test-MediaPipelineReleaseContentAllowed -RelativePath 'docs\README.md' -Content 'Parser fixture: r"\\\\?\\E:\\Videos\\file.mkv"') 'Escaped Windows extended drive-path fixtures must not be misclassified as UNC privacy leaks.'
Assert-True (Test-MediaPipelineReleaseContentAllowed -RelativePath 'docs\inventory.json' -Content '{"anchor":"assert path r\"\\\\?\\E:\\Videos\\file.mkv\""}') 'JSON-escaped Windows extended drive-path fixtures must not be misclassified as UNC privacy leaks.'
Assert-True (-not (Test-MediaPipelineReleaseContentAllowed -RelativePath 'docs\inventory.json' -Content '{"source":"\\\\private-server\\media"}')) 'JSON string values containing UNC paths must still be rejected.'
Assert-True (-not (Test-MediaPipelineReleaseContentAllowed -RelativePath 'docs\README.md' -Content 'Authorization: Bearer secret-value-should-not-ship')) 'Bearer values must be rejected from package content.'
Assert-True (Test-MediaPipelineReleaseContentScanEligible -RelativePath 'docs\testing\operator-proof.md') 'Sanitized text evidence must remain content-scanned.'
Assert-True (-not (Test-MediaPipelineReleaseContentScanEligible -RelativePath 'ops\release\evidence\operator-proof.png')) 'Raw screenshot evidence must not rely on the text content scanner.'
Assert-True (Test-MediaPipelineReleaseContentScanEligible -RelativePath 'ops\pipeline\config\MediaPipeline_config_template.psd1') 'Packaged configuration templates must be content-scanned.'
Assert-True (-not (Test-MediaPipelineReleaseContentScanEligible -RelativePath 'apps\desktop\runtime\Python\Lib\tempfile.py')) 'Bundled third-party runtime source must not produce privacy false positives.'

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

$replacementTestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-release-replacement-{0}' -f ([guid]::NewGuid().ToString('N')))
$fixtureSource = Join-Path $replacementTestRoot 'source'
$fixtureBuild = Join-Path $fixtureSource 'ops\scripts\release\build.ps1'
$fixturePolicy = Join-Path $fixtureSource 'ops\scripts\release\release_policy.ps1'
$fixtureVersion = Join-Path $fixtureSource 'ops\release\metadata\VERSION'
$fixtureDestination = Join-Path $replacementTestRoot 'destination'
try {
    New-Item -ItemType Directory -Path (Split-Path -Parent $fixtureBuild) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $fixtureVersion) -Force | Out-Null
    Copy-Item -LiteralPath $buildScriptPath -Destination $fixtureBuild
    Copy-Item -LiteralPath $releasePolicyPath -Destination $fixturePolicy
    Copy-Item -LiteralPath (Join-Path $repoRoot 'ops\release\metadata\VERSION') -Destination $fixtureVersion
    Set-Content -LiteralPath (Join-Path $fixtureSource 'payload.txt') -Value 'fixture payload' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $fixtureSource '.gitignore') -Value 'fixture exclusion' -Encoding UTF8

    $schemaOnlyManifest = Join-Path $replacementTestRoot 'schema-only-manifest'
    New-Item -ItemType Directory -Path $schemaOnlyManifest -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $schemaOnlyManifest 'keep-important.txt') -Value 'preserve me' -Encoding UTF8
    @{ schema_version = 'mediapipeline_release_manifest.v1' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $schemaOnlyManifest 'release_manifest.json') -Encoding UTF8
    Assert-ThrowsContaining `
        -Action { & $fixtureBuild -DestinationRoot $schemaOnlyManifest -Force } `
        -ExpectedText 'without a destination-bound MediaPipeline release identity' `
        -Message 'A schema-only completed marker must not authorize replacement.'
    Assert-True (Test-Path -LiteralPath (Join-Path $schemaOnlyManifest 'keep-important.txt') -PathType Leaf) 'Schema-only completed marker must preserve unrelated contents.'

    $schemaOnlyPartial = Join-Path $replacementTestRoot 'schema-only-partial'
    New-Item -ItemType Directory -Path $schemaOnlyPartial -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $schemaOnlyPartial 'keep-important.txt') -Value 'preserve me' -Encoding UTF8
    @{ schema_version = 'mediapipeline_release_in_progress.v1' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $schemaOnlyPartial '.release_in_progress.json') -Encoding UTF8
    Assert-ThrowsContaining `
        -Action { & $fixtureBuild -DestinationRoot $schemaOnlyPartial -Force } `
        -ExpectedText 'without a destination-bound MediaPipeline release identity' `
        -Message 'A schema-only partial marker must not authorize replacement.'
    Assert-True (Test-Path -LiteralPath (Join-Path $schemaOnlyPartial 'keep-important.txt') -PathType Leaf) 'Schema-only partial marker must preserve unrelated contents.'

    & $fixtureBuild -DestinationRoot $fixtureDestination | Out-Null
    $firstManifest = Get-Content -LiteralPath (Join-Path $fixtureDestination 'release_manifest.json') -Raw | ConvertFrom-Json
    Assert-True ([string]$firstManifest.replacement_identity.schema_version -eq 'mediapipeline_release_destination_identity.v1') 'Completed release marker must carry destination identity schema.'
    Assert-True ([string]$firstManifest.replacement_identity.destination_path_sha256 -match '^[0-9a-f]{64}$') 'Destination identity must carry a SHA-256 path binding.'
    Assert-True ([guid]::Parse([string]$firstManifest.replacement_identity.build_nonce) -ne [guid]::Empty) 'Destination identity must carry a valid build nonce.'

    Set-Content -LiteralPath (Join-Path $fixtureDestination 'old-only.txt') -Value 'recoverable prior output' -Encoding UTF8
    & $fixtureBuild -DestinationRoot $fixtureDestination -Force | Out-Null
    $successfulQuarantines = @(Get-ChildItem -LiteralPath $replacementTestRoot -Directory -Filter 'destination.replaced.*')
    Assert-True ($successfulQuarantines.Count -eq 1) 'Successful replacement must retain exactly one recoverable sibling quarantine.'
    Assert-True (Test-Path -LiteralPath (Join-Path $successfulQuarantines[0].FullName 'old-only.txt') -PathType Leaf) 'Successful replacement quarantine must retain prior contents.'

    $mismatchedDestination = Join-Path $replacementTestRoot 'copied-marker-destination'
    Copy-Item -LiteralPath $fixtureDestination -Destination $mismatchedDestination -Recurse
    Set-Content -LiteralPath (Join-Path $mismatchedDestination 'keep-important.txt') -Value 'preserve copied marker target' -Encoding UTF8
    Assert-ThrowsContaining `
        -Action { & $fixtureBuild -DestinationRoot $mismatchedDestination -Force } `
        -ExpectedText 'without a destination-bound MediaPipeline release identity' `
        -Message 'A marker copied from another destination must not authorize replacement.'
    Assert-True (Test-Path -LiteralPath (Join-Path $mismatchedDestination 'keep-important.txt') -PathType Leaf) 'Destination-mismatched marker must preserve unrelated contents.'

    $identityMismatchDestination = Join-Path $replacementTestRoot 'identity-mismatch-destination'
    & $fixtureBuild -DestinationRoot $identityMismatchDestination | Out-Null
    $identityManifestPath = Join-Path $identityMismatchDestination 'release_manifest.json'
    $identityManifestBaseline = Get-Content -LiteralPath $identityManifestPath -Raw
    Set-Content -LiteralPath (Join-Path $identityMismatchDestination 'keep-important.txt') -Value 'preserve identity mismatch target' -Encoding UTF8
    foreach ($mismatch in @(
        @{ Property = 'source_root_sha256'; Value = ('0' * 64); Label = 'source-root hash' },
        @{ Property = 'normalized_version'; Value = '0.0.0+000'; Label = 'normalized version' },
        @{ Property = 'source_revision'; Value = ('0' * 40); Label = 'source revision' }
    )) {
        $mismatchedManifest = $identityManifestBaseline | ConvertFrom-Json
        $mismatchedManifest.replacement_identity.($mismatch.Property) = $mismatch.Value
        $mismatchedManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $identityManifestPath -Encoding UTF8
        Assert-ThrowsContaining `
            -Action { & $fixtureBuild -DestinationRoot $identityMismatchDestination -Force } `
            -ExpectedText 'without a destination-bound MediaPipeline release identity' `
            -Message "A mismatched $($mismatch.Label) must not authorize replacement."
        Assert-True (Test-Path -LiteralPath (Join-Path $identityMismatchDestination 'keep-important.txt') -PathType Leaf) "Mismatched $($mismatch.Label) must preserve unrelated contents."
        Set-Content -LiteralPath $identityManifestPath -Value $identityManifestBaseline -Encoding UTF8
    }

    Set-Content -LiteralPath (Join-Path $fixtureDestination 'restore-me.txt') -Value 'restore prior destination' -Encoding UTF8
    $lockedPayload = Join-Path $fixtureSource 'locked-payload.txt'
    Set-Content -LiteralPath $lockedPayload -Value 'force copy failure after quarantine' -Encoding UTF8
    $lockedStream = [System.IO.File]::Open($lockedPayload, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::None)
    try {
        $replacementFailed = $false
        try {
            & $fixtureBuild -DestinationRoot $fixtureDestination -Force | Out-Null
        } catch {
            $replacementFailed = $true
        }
        Assert-True $replacementFailed 'A locked source fixture must fail after destination quarantine.'
    } finally {
        $lockedStream.Dispose()
    }
    Assert-True (Test-Path -LiteralPath (Join-Path $fixtureDestination 'restore-me.txt') -PathType Leaf) 'Failed replacement must restore the prior destination exactly.'
    Assert-True (@(Get-ChildItem -LiteralPath $replacementTestRoot -Directory -Filter 'destination.failed.*').Count -eq 1) 'Failed replacement must preserve partial output in one sibling quarantine.'

    $junctionTarget = Join-Path $replacementTestRoot 'junction-target'
    $junctionPath = Join-Path $replacementTestRoot 'junction-destination'
    New-Item -ItemType Directory -Path $junctionTarget -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $junctionTarget 'keep-important.txt') -Value 'preserve junction target' -Encoding UTF8
    New-Item -ItemType Junction -Path $junctionPath -Target $junctionTarget | Out-Null
    Assert-ThrowsContaining `
        -Action { & $fixtureBuild -DestinationRoot $junctionPath -Force } `
        -ExpectedText 'reparse-point path component' `
        -Message 'A reparse-point destination must not authorize replacement.'
    Assert-True (Test-Path -LiteralPath (Join-Path $junctionTarget 'keep-important.txt') -PathType Leaf) 'Rejected reparse destination must preserve target contents.'
} finally {
    if (Test-Path -LiteralPath $replacementTestRoot) {
        Remove-Item -LiteralPath $replacementTestRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
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
