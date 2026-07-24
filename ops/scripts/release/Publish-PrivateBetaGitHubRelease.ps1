[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('beta', 'stable')]
    [string]$Channel,

    [Parameter(Mandatory)]
    [string]$BundleRoot,

    [Parameter(Mandatory)]
    [string]$Repository,

    [Parameter(Mandatory)]
    [string]$ReleaseTag,

    [Parameter(Mandatory)]
    [string]$Version,

    [Parameter(Mandatory)]
    [string]$SourceCommit,

    [switch]$AllowSameCommitRebuild,

    [string]$ProtectedRebuildApproval = '',

    [string]$GhPath,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$checks = [System.Collections.Generic.List[object]]::new()
$commands = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message
    )
    $checks.Add([pscustomobject][ordered]@{
        name = $Name
        ok = $Ok
        severity = 'error'
        message = $Message
    }) | Out-Null
}

function Invoke-GhCaptured {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [bool]$Mutation = $false
    )
    $output = @(& $GhPath @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    $text = ($output | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    $commands.Add([pscustomobject][ordered]@{
        name = $Name
        mutation = $Mutation
        exit_code = $exitCode
        arguments = @($Arguments)
        output_tail = if ($text.Length -gt 2000) { $text.Substring($text.Length - 2000) } else { $text }
    }) | Out-Null
    return [pscustomobject]@{ exit_code = $exitCode; text = $text }
}

function Read-GhJsonOptional {
    param(
        [string]$Name,
        [string]$ApiPath
    )
    $response = Invoke-GhCaptured -Name $Name -Arguments @('api', $ApiPath)
    if ($response.exit_code -eq 0) {
        try {
            return [pscustomobject]@{
                ok = $true
                found = $true
                payload = ($response.text | ConvertFrom-Json -Depth 20)
            }
        } catch {
            Add-Check "$Name`:json" $false "GitHub returned invalid JSON for $ApiPath."
            return [pscustomobject]@{ ok = $false; found = $false; payload = $null }
        }
    }
    if ($response.text -match '(?i)(HTTP\s+404|not\s+found)') {
        return [pscustomobject]@{ ok = $true; found = $false; payload = $null }
    }
    Add-Check "$Name`:query" $false "GitHub query failed for $ApiPath."
    return [pscustomobject]@{ ok = $false; found = $false; payload = $null }
}

function Get-PropertyValue {
    param(
        [object]$InputObject,
        [string]$Name
    )
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Write-ResultAndExit {
    param([int]$ExitCode)
    $result = [pscustomobject][ordered]@{
        schema_version = 'private_beta_release_publication.v1'
        ok = ($ExitCode -eq 0)
        channel = $Channel
        version = $Version
        release_tag = $ReleaseTag
        source_commit = $SourceCommit.ToLowerInvariant()
        repository = $Repository
        release_existed = [bool]$script:releaseExists
        tag_existed = [bool]$script:tagExists
        resolved_tag_commit = $script:resolvedTagCommit
        rebuild_requested = [bool]$AllowSameCommitRebuild
        rebuild_authorized = [bool]$script:rebuildAuthorized
        clobber_used = [bool]$script:clobberUsed
        asset_names = @($script:assetNames)
        checks = @($checks)
        commands = @($commands)
    }
    if ($AsJson) {
        $result | ConvertTo-Json -Depth 12
    } else {
        if ($result.ok) {
            Write-Host "Private beta release publication completed for $Repository $ReleaseTag."
        } else {
            Write-Host "Private beta release publication refused for $Repository $ReleaseTag."
        }
        foreach ($check in $checks) {
            $prefix = if ($check.ok) { 'PASS' } else { 'FAIL' }
            Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
        }
    }
    exit $ExitCode
}

$script:releaseExists = $false
$script:tagExists = $false
$script:resolvedTagCommit = $null
$script:rebuildAuthorized = $false
$script:clobberUsed = $false
$script:assetNames = @()

$expectedTag = "app-v$Version"
$expectedTitle = "MediaPipelineRemuxEncodeAIO $Version ($Channel)"
$expectedPrerelease = ($Channel -ne 'stable')
$protectedApproval = $ProtectedRebuildApproval.Trim().ToLowerInvariant() -eq 'true'

Add-Check 'repository:format' ($Repository -match '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') 'Repository must be a safe owner/repo value.'
Add-Check 'version:format' ($Version -match '^\d+\.\d+\.\d+\+\d+$') 'Version must be Tauri-compatible semver with build metadata.'
Add-Check 'release_tag:format' ($ReleaseTag -match '^app-v\d+\.\d+\.\d+\+\d+$') 'Release tag must use app-v<version>.'
Add-Check 'release_tag:version_identity' ($ReleaseTag -ceq $expectedTag) 'Release tag must equal app-v<version> exactly.'
Add-Check 'source_commit:format' ($SourceCommit -match '^[0-9a-fA-F]{40}$') 'Source commit must be a full 40-character Git SHA.'
Add-Check 'bundle_root:exists' (Test-Path -LiteralPath $BundleRoot -PathType Container) 'Bundle root must exist.'
Add-Check 'rebuild:protected_approval' (-not $AllowSameCommitRebuild -or $protectedApproval) 'Same-commit rebuild requires protected environment approval in addition to the explicit dispatch input.'

if (@($checks | Where-Object { -not $_.ok }).Count -gt 0) {
    Write-ResultAndExit -ExitCode 1
}

if (-not $GhPath) {
    $ghCommand = Get-Command gh -ErrorAction SilentlyContinue
    if ($ghCommand) { $GhPath = $ghCommand.Source }
}
Add-Check 'gh:available' (-not [string]::IsNullOrWhiteSpace($GhPath) -and (Test-Path -LiteralPath $GhPath -PathType Leaf)) 'GitHub CLI must be available.'

$nsisRoot = Join-Path $BundleRoot 'nsis'
$installers = @(if (Test-Path -LiteralPath $nsisRoot -PathType Container) {
    Get-ChildItem -LiteralPath $nsisRoot -Filter '*.exe' -File
})
Add-Check 'assets:installer_count' ($installers.Count -eq 1) 'Bundle must contain exactly one NSIS installer.'
$assetPaths = [System.Collections.Generic.List[string]]::new()
if ($installers.Count -eq 1) {
    $assetPaths.Add($installers[0].FullName) | Out-Null
    $signaturePath = "$($installers[0].FullName).sig"
    Add-Check 'assets:signature' (Test-Path -LiteralPath $signaturePath -PathType Leaf) 'Updater signature must exist beside the installer.'
    if (Test-Path -LiteralPath $signaturePath -PathType Leaf) { $assetPaths.Add($signaturePath) | Out-Null }
}
foreach ($requiredName in @("latest-$Channel.json", 'SHA256SUMS.txt')) {
    $requiredPath = Join-Path $BundleRoot $requiredName
    Add-Check "assets:$requiredName" (Test-Path -LiteralPath $requiredPath -PathType Leaf) "Required release asset must exist: $requiredName."
    if (Test-Path -LiteralPath $requiredPath -PathType Leaf) { $assetPaths.Add($requiredPath) | Out-Null }
}
$script:assetNames = @($assetPaths | ForEach-Object { Split-Path -Leaf $_ })

if (@($checks | Where-Object { -not $_.ok }).Count -gt 0) {
    Write-ResultAndExit -ExitCode 1
}

$encodedTag = [uri]::EscapeDataString($ReleaseTag)
$releaseQuery = Read-GhJsonOptional -Name 'release_by_tag' -ApiPath "repos/$Repository/releases/tags/$encodedTag"
$refQuery = Read-GhJsonOptional -Name 'tag_ref' -ApiPath "repos/$Repository/git/ref/tags/$encodedTag"
$script:releaseExists = $releaseQuery.found
$script:tagExists = $refQuery.found

if ($releaseQuery.found -and -not $refQuery.found) {
    Add-Check 'remote:release_has_tag' $false 'An existing release must have a resolvable tag ref.'
}

if ($refQuery.found) {
    $tagObject = Get-PropertyValue -InputObject $refQuery.payload -Name 'object'
    $objectType = [string](Get-PropertyValue -InputObject $tagObject -Name 'type')
    $objectSha = [string](Get-PropertyValue -InputObject $tagObject -Name 'sha')
    for ($depth = 0; $depth -lt 4 -and $objectType -eq 'tag'; $depth++) {
        $tagObjectQuery = Read-GhJsonOptional -Name "annotated_tag_$depth" -ApiPath "repos/$Repository/git/tags/$objectSha"
        if (-not $tagObjectQuery.found) {
            Add-Check 'remote:annotated_tag' $false 'Annotated release tag could not be dereferenced to a commit.'
            break
        }
        $nestedObject = Get-PropertyValue -InputObject $tagObjectQuery.payload -Name 'object'
        $objectType = [string](Get-PropertyValue -InputObject $nestedObject -Name 'type')
        $objectSha = [string](Get-PropertyValue -InputObject $nestedObject -Name 'sha')
    }
    Add-Check 'remote:tag_resolves_commit' ($objectType -eq 'commit' -and $objectSha -match '^[0-9a-fA-F]{40}$') 'Release tag must resolve to a full commit SHA.'
    if ($objectType -eq 'commit') { $script:resolvedTagCommit = $objectSha.ToLowerInvariant() }
    Add-Check 'remote:tag_matches_source' ($script:resolvedTagCommit -eq $SourceCommit.ToLowerInvariant()) 'Existing release tag must resolve to the current workflow commit.'
}

$collisions = @()
if ($releaseQuery.found) {
    $payload = $releaseQuery.payload
    $remoteTag = [string](Get-PropertyValue -InputObject $payload -Name 'tag_name')
    $remoteTitle = [string](Get-PropertyValue -InputObject $payload -Name 'name')
    $remoteTarget = [string](Get-PropertyValue -InputObject $payload -Name 'target_commitish')
    $remoteDraft = [bool](Get-PropertyValue -InputObject $payload -Name 'draft')
    $remotePrerelease = [bool](Get-PropertyValue -InputObject $payload -Name 'prerelease')
    Add-Check 'remote:tag_identity' ($remoteTag -ceq $ReleaseTag) 'Existing release tag identity must match the requested tag.'
    Add-Check 'remote:title_identity' ($remoteTitle -ceq $expectedTitle) 'Existing release title must match product, version, and channel.'
    Add-Check 'remote:target_identity' ($remoteTarget.ToLowerInvariant() -eq $SourceCommit.ToLowerInvariant()) 'Existing release target_commitish must equal the current workflow commit.'
    Add-Check 'remote:not_draft' (-not $remoteDraft) 'Existing release must not be a draft.'
    Add-Check 'remote:channel_identity' ($remotePrerelease -eq $expectedPrerelease) 'Existing release prerelease state must match the selected channel.'
    $remoteAssets = @(Get-PropertyValue -InputObject $payload -Name 'assets')
    $remoteAssetNames = @($remoteAssets | ForEach-Object { [string](Get-PropertyValue -InputObject $_ -Name 'name') })
    $collisions = @($script:assetNames | Where-Object { $_ -in $remoteAssetNames })
    $script:rebuildAuthorized = ($AllowSameCommitRebuild -and $protectedApproval -and $script:resolvedTagCommit -eq $SourceCommit.ToLowerInvariant())
    Add-Check 'assets:immutable_default' ($collisions.Count -eq 0 -or $script:rebuildAuthorized) 'Existing versioned assets are immutable unless a protected same-commit rebuild is explicitly authorized.'
} else {
    Add-Check 'rebuild:existing_release' (-not $AllowSameCommitRebuild) 'Same-commit rebuild override is valid only for an existing release.'
}

if (@($checks | Where-Object { -not $_.ok }).Count -gt 0) {
    Write-ResultAndExit -ExitCode 1
}

if (-not $releaseQuery.found) {
    $createArgs = [System.Collections.Generic.List[string]]::new()
    foreach ($arg in @('release', 'create', $ReleaseTag, '--repo', $Repository, '--title', $expectedTitle, '--notes', "Signed NSIS $Channel release. Assets include updater channel JSON and SHA-256 checksums.")) {
        $createArgs.Add($arg) | Out-Null
    }
    if ($refQuery.found) {
        $createArgs.Add('--verify-tag') | Out-Null
    } else {
        $createArgs.Add('--target') | Out-Null
        $createArgs.Add($SourceCommit) | Out-Null
    }
    if ($expectedPrerelease) { $createArgs.Add('--prerelease') | Out-Null }
    $created = Invoke-GhCaptured -Name 'release_create' -Arguments $createArgs.ToArray() -Mutation $true
    Add-Check 'mutation:create' ($created.exit_code -eq 0) 'GitHub release creation must succeed before upload.'
    if ($created.exit_code -ne 0) { Write-ResultAndExit -ExitCode 1 }
}

$uploadArgs = [System.Collections.Generic.List[string]]::new()
foreach ($arg in @('release', 'upload', $ReleaseTag, '--repo', $Repository)) { $uploadArgs.Add($arg) | Out-Null }
foreach ($path in $assetPaths) { $uploadArgs.Add($path) | Out-Null }
if ($collisions.Count -gt 0) {
    $uploadArgs.Add('--clobber') | Out-Null
    $script:clobberUsed = $true
}
$uploaded = Invoke-GhCaptured -Name 'release_upload' -Arguments $uploadArgs.ToArray() -Mutation $true
Add-Check 'mutation:upload' ($uploaded.exit_code -eq 0) 'GitHub release asset upload must succeed.'

Write-ResultAndExit -ExitCode $(if ($uploaded.exit_code -eq 0) { 0 } else { 1 })
