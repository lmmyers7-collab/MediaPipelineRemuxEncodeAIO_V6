[CmdletBinding()]
param(
    [ValidateSet('beta', 'stable')]
    [string]$Channel = $(if ($env:MEDIAPIPELINE_RELEASE_CHANNEL) { $env:MEDIAPIPELINE_RELEASE_CHANNEL } else { 'beta' }),

    [string]$Repository = $env:GITHUB_REPOSITORY,

    [string]$Version = $(if ($env:MEDIAPIPELINE_SEMVER_VERSION) { $env:MEDIAPIPELINE_SEMVER_VERSION } else { '2026.6.4+001' }),

    [string]$ReleaseTag,

    [string]$ConfigOutputPath,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$workflowPath = Join-Path $repoRoot '.github\workflows\private-beta-windows.yml'
$configGeneratorPath = Join-Path $repoRoot 'ops\scripts\release\New-TauriProductizationConfig.ps1'

if (-not $ReleaseTag) {
    $ReleaseTag = "app-v$Version"
}
if (-not $ConfigOutputPath) {
    $ConfigOutputPath = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-tauri-{0}-preflight.conf.json" -f $Channel)
}

$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message,
        [ValidateSet('error', 'warning')]
        [string]$Severity = 'error'
    )
    $checks.Add([pscustomobject][ordered]@{
        name = $Name
        ok = $Ok
        severity = $Severity
        message = $Message
    }) | Out-Null
}

function Test-RequiredEnv {
    param([string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name)
    return -not [string]::IsNullOrWhiteSpace($value)
}

Add-Check 'repository' ($Repository -match '^[^/\s]+/[^/\s]+$') `
    'Repository must be owner/repo, usually from GITHUB_REPOSITORY.'
Add-Check 'version' ($Version -match '^\d+\.\d+\.\d+\+\d+$') `
    'Version must be Tauri-compatible semver with build metadata, for example 2026.6.4+001.'
Add-Check 'release_tag' ($ReleaseTag -match '^app-v\d+\.\d+\.\d+\+\d+$') `
    'Release tag must use the app-v<version> shape expected by the beta workflow.'

$requiredSecretNames = @(
    'TAURI_SIGNING_PRIVATE_KEY',
    'TAURI_UPDATER_PUBLIC_KEY',
    'WINDOWS_CERTIFICATE_BASE64',
    'WINDOWS_CERTIFICATE_PASSWORD'
)
foreach ($secretName in $requiredSecretNames) {
    Add-Check "secret:$secretName" (Test-RequiredEnv $secretName) `
        "Required protected release secret is present: $secretName."
}
Add-Check 'secret:TAURI_SIGNING_PRIVATE_KEY_PASSWORD' (Test-RequiredEnv 'TAURI_SIGNING_PRIVATE_KEY_PASSWORD') `
    'Optional updater private-key password is present when the updater key is encrypted.' 'warning'

if (Test-Path -LiteralPath $workflowPath -PathType Leaf) {
    $workflowText = Get-Content -LiteralPath $workflowPath -Raw
    Add-Check 'workflow:dispatch' ($workflowText -match 'workflow_dispatch') `
        'Private beta workflow must be manually dispatched.'
    Add-Check 'workflow:environment' ($workflowText -match 'environment:\s*\$\{\{\s*inputs\.channel\s*\}\}-release') `
        'Private beta workflow must bind channel releases to beta-release/stable-release environments.'
    foreach ($secretName in $requiredSecretNames) {
        Add-Check "workflow:secret:$secretName" ($workflowText -match [regex]::Escape("secrets.$secretName")) `
            "Workflow must reference protected secret $secretName."
    }
    Add-Check 'workflow:config_generator' ($workflowText -match 'New-TauriProductizationConfig\.ps1') `
        'Workflow must generate updater-enabled Tauri config.'
    Add-Check 'workflow:channel_json' ($workflowText -match 'New-TauriUpdaterChannelJson\.ps1') `
        'Workflow must generate updater channel JSON and checksums.'
} else {
    Add-Check 'workflow:file' $false "Private beta workflow not found: $workflowPath"
}

if (Test-Path -LiteralPath $configGeneratorPath -PathType Leaf) {
    try {
        $generatorArgs = @{
            Channel = $Channel
            Repository = $Repository
            UpdaterPublicKey = [Environment]::GetEnvironmentVariable('TAURI_UPDATER_PUBLIC_KEY')
            Version = $Version
            OutputPath = $ConfigOutputPath
        }
        $thumbprint = [Environment]::GetEnvironmentVariable('WINDOWS_CERTIFICATE_THUMBPRINT')
        if ($thumbprint) {
            $generatorArgs['WindowsCertificateThumbprint'] = $thumbprint
        }
        & $configGeneratorPath @generatorArgs 6>$null | Out-Null
        Add-Check 'generated_config:writable' (Test-Path -LiteralPath $ConfigOutputPath -PathType Leaf) `
            'Updater-enabled Tauri config was generated at the requested path.'
    } catch {
        Add-Check 'generated_config:writable' $false "Updater config generation failed: $($_.Exception.Message)"
    }
} else {
    Add-Check 'config_generator:file' $false "Config generator not found: $configGeneratorPath"
}

$generatedConfigEvidence = [ordered]@{
    path = $ConfigOutputPath
    exists = $false
    updater_endpoint = $null
    windows_install_mode = $null
    create_updater_artifacts = $false
    nsis_only = $false
    digest_algorithm = $null
    timestamp_url_present = $false
    certificate_thumbprint_present = $false
}

if (Test-Path -LiteralPath $ConfigOutputPath -PathType Leaf) {
    try {
        $generatedConfig = Get-Content -LiteralPath $ConfigOutputPath -Raw | ConvertFrom-Json -Depth 100
        $targets = @($generatedConfig.bundle.targets)
        $endpoint = @($generatedConfig.plugins.updater.endpoints) | Select-Object -First 1
        $generatedConfigEvidence.exists = $true
        $generatedConfigEvidence.updater_endpoint = $endpoint
        $generatedConfigEvidence.windows_install_mode = [string]$generatedConfig.plugins.updater.windows.installMode
        $generatedConfigEvidence.create_updater_artifacts = [bool]$generatedConfig.bundle.createUpdaterArtifacts
        $generatedConfigEvidence.nsis_only = ($targets.Count -eq 1 -and $targets[0] -eq 'nsis')
        $generatedConfigEvidence.digest_algorithm = [string]$generatedConfig.bundle.windows.digestAlgorithm
        $generatedConfigEvidence.timestamp_url_present = -not [string]::IsNullOrWhiteSpace([string]$generatedConfig.bundle.windows.timestampUrl)
        $generatedConfigEvidence.certificate_thumbprint_present = -not [string]::IsNullOrWhiteSpace([string]$generatedConfig.bundle.windows.certificateThumbprint)

        Add-Check 'generated_config:nsis_only' $generatedConfigEvidence.nsis_only `
            'Generated Tauri config must target only NSIS for the first beta lane.'
        Add-Check 'generated_config:updater_artifacts' $generatedConfigEvidence.create_updater_artifacts `
            'Generated Tauri config must enable updater artifact creation.'
        Add-Check 'generated_config:endpoint' ($endpoint -eq "https://github.com/$Repository/releases/latest/download/latest-$Channel.json") `
            'Generated updater endpoint must match the selected channel and GitHub repository.'
        Add-Check 'generated_config:install_mode' ($generatedConfigEvidence.windows_install_mode -eq 'passive') `
            'Windows updater install mode must remain passive.'
        Add-Check 'generated_config:digest' ($generatedConfigEvidence.digest_algorithm -eq 'sha256') `
            'Windows signing digest must be sha256.'
        Add-Check 'generated_config:timestamp' $generatedConfigEvidence.timestamp_url_present `
            'Windows signing timestamp URL must be configured.'
        Add-Check 'generated_config:certificate_thumbprint' $generatedConfigEvidence.certificate_thumbprint_present `
            'Certificate thumbprint is expected after the CI certificate import step.' 'warning'
    } catch {
        Add-Check 'generated_config:parse' $false "Generated Tauri config could not be parsed: $($_.Exception.Message)"
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_release_preflight.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    release_tag = $ReleaseTag
    repository = $Repository
    generated_config = $generatedConfigEvidence
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta release preflight passed for $Channel $Version."
    } else {
        Write-Host "Private beta release preflight failed for $Channel $Version."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
