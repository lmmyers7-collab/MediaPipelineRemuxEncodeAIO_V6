[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('beta', 'stable')]
    [string]$Channel,

    [Parameter(Mandatory)]
    [string]$ChannelJsonPath,

    [Parameter(Mandatory)]
    [string]$Repository,

    [Parameter(Mandatory)]
    [string]$ReleaseTag,

    [Parameter(Mandatory)]
    [string]$Version,

    [Parameter(Mandatory)]
    [string]$SourceCommit,

    [string]$GhPath,

    [string]$EndpointFetcherPath,

    [ValidateRange(1, 20)]
    [int]$EndpointVerificationAttempts = 6,

    [ValidateRange(0, 60)]
    [int]$EndpointVerificationDelaySeconds = 10,

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
        schema_version = 'tauri_updater_channel_pointer_publication.v1'
        ok = ($ExitCode -eq 0)
        channel = $Channel
        version = $Version
        release_tag = $ReleaseTag
        source_commit = $SourceCommit.ToLowerInvariant()
        repository = $Repository
        pointer_tag = $script:pointerTag
        endpoint = $script:endpoint
        endpoint_verified = [bool]$script:endpointVerified
        channel_json_sha256 = $script:channelJsonSha256
        pointer_release_existed = [bool]$script:pointerReleaseExists
        pointer_asset_replaced = [bool]$script:pointerAssetReplaced
        checks = @($checks)
        commands = @($commands)
    }
    if ($AsJson) {
        $result | ConvertTo-Json -Depth 12
    } else {
        if ($result.ok) {
            Write-Host "Updater channel pointer advanced and verified: $($script:endpoint)"
        } else {
            Write-Host "Updater channel pointer publication refused for $Repository $Channel."
        }
        foreach ($check in $checks) {
            $prefix = if ($check.ok) { 'PASS' } else { 'FAIL' }
            Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
        }
    }
    exit $ExitCode
}

$script:pointerTag = "updater-$Channel"
$script:pointerTitle = "MediaPipelineRemuxEncodeAIO updater channel ($Channel)"
$script:endpoint = "https://github.com/$Repository/releases/download/$($script:pointerTag)/latest-$Channel.json"
$script:endpointVerified = $false
$script:channelJsonSha256 = $null
$script:pointerReleaseExists = $false
$script:pointerAssetReplaced = $false
$expectedTag = "app-v$Version"
$expectedAssetName = "latest-$Channel.json"

Add-Check 'repository:format' ($Repository -match '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') 'Repository must be a safe owner/repo value.'
Add-Check 'version:format' ($Version -match '^\d+\.\d+\.\d+\+\d+$') 'Version must be Tauri-compatible semver with build metadata.'
Add-Check 'release_tag:version_identity' ($ReleaseTag -ceq $expectedTag) 'Release tag must equal app-v<version> exactly.'
Add-Check 'source_commit:format' ($SourceCommit -match '^[0-9a-fA-F]{40}$') 'Source commit must be a full 40-character Git SHA.'
Add-Check 'channel_json:leaf_name' ((Split-Path -Leaf $ChannelJsonPath) -ceq $expectedAssetName) 'Channel JSON must use the exact channel pointer asset name.'
Add-Check 'channel_json:exists' (Test-Path -LiteralPath $ChannelJsonPath -PathType Leaf) 'Channel JSON must exist before pointer publication.'

$channelPayload = $null
if (Test-Path -LiteralPath $ChannelJsonPath -PathType Leaf) {
    try {
        $channelPayload = Get-Content -LiteralPath $ChannelJsonPath -Raw | ConvertFrom-Json -Depth 20
        $script:channelJsonSha256 = (Get-FileHash -LiteralPath $ChannelJsonPath -Algorithm SHA256).Hash.ToLowerInvariant()
    } catch {
        Add-Check 'channel_json:json' $false 'Channel JSON must be valid JSON.'
    }
}

if ($null -ne $channelPayload) {
    $platforms = Get-PropertyValue -InputObject $channelPayload -Name 'platforms'
    $windowsPayload = Get-PropertyValue -InputObject $platforms -Name 'windows-x86_64'
    $installerUrl = [string](Get-PropertyValue -InputObject $windowsPayload -Name 'url')
    $signature = [string](Get-PropertyValue -InputObject $windowsPayload -Name 'signature')
    $expectedInstallerPrefix = "https://github.com/$Repository/releases/download/$ReleaseTag/"
    Add-Check 'channel_json:version_identity' ([string](Get-PropertyValue -InputObject $channelPayload -Name 'version') -ceq $Version) 'Channel JSON version must equal the release version.'
    Add-Check 'channel_json:installer_release_identity' ($installerUrl.StartsWith($expectedInstallerPrefix, [System.StringComparison]::Ordinal) -and $installerUrl.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) 'Channel JSON installer URL must target the immutable versioned release.'
    Add-Check 'channel_json:signature' (-not [string]::IsNullOrWhiteSpace($signature)) 'Channel JSON must carry a non-empty updater signature.'
}

if ($EndpointFetcherPath) {
    Add-Check 'endpoint_fetcher:exists' (Test-Path -LiteralPath $EndpointFetcherPath -PathType Leaf) 'The optional endpoint fetcher must be an existing file.'
}

if (@($checks | Where-Object { -not $_.ok }).Count -gt 0) {
    Write-ResultAndExit -ExitCode 1
}

if (-not $GhPath) {
    $ghCommand = Get-Command gh -ErrorAction SilentlyContinue
    if ($ghCommand) { $GhPath = $ghCommand.Source }
}
Add-Check 'gh:available' (-not [string]::IsNullOrWhiteSpace($GhPath) -and (Test-Path -LiteralPath $GhPath -PathType Leaf)) 'GitHub CLI must be available.'
if (@($checks | Where-Object { -not $_.ok }).Count -gt 0) {
    Write-ResultAndExit -ExitCode 1
}

$encodedPointerTag = [uri]::EscapeDataString($script:pointerTag)
$pointerQuery = Read-GhJsonOptional -Name 'pointer_release_by_tag' -ApiPath "repos/$Repository/releases/tags/$encodedPointerTag"
$script:pointerReleaseExists = $pointerQuery.found
$pointerHasAsset = $false
if ($pointerQuery.found) {
    $payload = $pointerQuery.payload
    $remoteAssets = @(Get-PropertyValue -InputObject $payload -Name 'assets')
    $remoteAssetNames = @($remoteAssets | ForEach-Object { [string](Get-PropertyValue -InputObject $_ -Name 'name') })
    $unexpectedAssets = @($remoteAssetNames | Where-Object { $_ -cne $expectedAssetName })
    $pointerHasAsset = $expectedAssetName -cin $remoteAssetNames
    $immutableValue = Get-PropertyValue -InputObject $payload -Name 'immutable'
    Add-Check 'pointer_remote:tag_identity' ([string](Get-PropertyValue -InputObject $payload -Name 'tag_name') -ceq $script:pointerTag) 'Pointer release tag must match the selected channel.'
    Add-Check 'pointer_remote:title_identity' ([string](Get-PropertyValue -InputObject $payload -Name 'name') -ceq $script:pointerTitle) 'Pointer release title must match the selected channel.'
    Add-Check 'pointer_remote:not_draft' (-not [bool](Get-PropertyValue -InputObject $payload -Name 'draft')) 'Pointer release must not be a draft.'
    Add-Check 'pointer_remote:prerelease' ([bool](Get-PropertyValue -InputObject $payload -Name 'prerelease')) 'Pointer release must remain a prerelease so it cannot become the repository latest full release.'
    Add-Check 'pointer_remote:mutable' ($immutableValue -ne $true) 'Pointer release must permit intentional channel-asset replacement.'
    Add-Check 'pointer_remote:asset_scope' ($unexpectedAssets.Count -eq 0) 'Pointer release may contain only the selected channel JSON asset.'
}

if (@($checks | Where-Object { -not $_.ok }).Count -gt 0) {
    Write-ResultAndExit -ExitCode 1
}

if ($pointerQuery.found) {
    $uploadArgs = @('release', 'upload', $script:pointerTag, $ChannelJsonPath, '--repo', $Repository)
    if ($pointerHasAsset) {
        $uploadArgs += '--clobber'
        $script:pointerAssetReplaced = $true
    }
    $published = Invoke-GhCaptured -Name 'pointer_release_upload' -Arguments $uploadArgs -Mutation $true
    Add-Check 'pointer_mutation:upload' ($published.exit_code -eq 0) 'Pointer release asset upload must succeed.'
} else {
    $createArgs = @(
        'release', 'create', $script:pointerTag, $ChannelJsonPath,
        '--repo', $Repository,
        '--title', $script:pointerTitle,
        '--notes', "Mutable updater metadata pointer for the $Channel channel. Versioned installers remain on immutable app-v<version> releases.",
        '--prerelease', '--latest=false', '--target', $SourceCommit
    )
    $published = Invoke-GhCaptured -Name 'pointer_release_create' -Arguments $createArgs -Mutation $true
    Add-Check 'pointer_mutation:create' ($published.exit_code -eq 0) 'Pointer release creation and initial asset upload must succeed.'
}

if (-not $published -or $published.exit_code -ne 0) {
    Write-ResultAndExit -ExitCode 1
}

$verificationRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-updater-pointer-{0}" -f [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $verificationRoot -Force | Out-Null
try {
    for ($attempt = 1; $attempt -le $EndpointVerificationAttempts; $attempt++) {
        $downloadPath = Join-Path $verificationRoot $expectedAssetName
        if (Test-Path -LiteralPath $downloadPath -PathType Leaf) {
            Remove-Item -LiteralPath $downloadPath -Force
        }
        $cacheBustedEndpoint = "$($script:endpoint)?mediapipeline_source=$($SourceCommit.ToLowerInvariant())&attempt=$attempt"
        try {
            if ($EndpointFetcherPath) {
                & $EndpointFetcherPath -Uri $cacheBustedEndpoint -OutputPath $downloadPath
                if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
                    throw "Endpoint fetcher exited with code $LASTEXITCODE."
                }
            } else {
                Invoke-WebRequest -Uri $cacheBustedEndpoint -OutFile $downloadPath -Headers @{ 'Cache-Control' = 'no-cache' } -UseBasicParsing
            }
            if (Test-Path -LiteralPath $downloadPath -PathType Leaf) {
                $downloadHash = (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($downloadHash -eq $script:channelJsonSha256) {
                    $script:endpointVerified = $true
                    break
                }
            }
        } catch {
            # A just-replaced GitHub asset can take a short time to become visible.
        }
        if ($attempt -lt $EndpointVerificationAttempts -and $EndpointVerificationDelaySeconds -gt 0) {
            Start-Sleep -Seconds $EndpointVerificationDelaySeconds
        }
    }
} finally {
    if (Test-Path -LiteralPath $verificationRoot -PathType Container) {
        Remove-Item -LiteralPath $verificationRoot -Recurse -Force
    }
}

Add-Check 'pointer_endpoint:exact_content' $script:endpointVerified 'The exact configured updater endpoint must return the just-published channel JSON bytes.'
Write-ResultAndExit -ExitCode $(if ($script:endpointVerified) { 0 } else { 1 })
