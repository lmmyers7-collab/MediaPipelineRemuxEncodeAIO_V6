[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$InstallRoot,

    [Parameter(Mandatory)]
    [string]$AppDataRoot,

    [ValidateSet('beta', 'stable')]
    [string]$Channel = 'beta',

    [string]$Version = $(if ($env:MEDIAPIPELINE_PRODUCT_VERSION) { $env:MEDIAPIPELINE_PRODUCT_VERSION } else { '2026.06.04.001' }),

    [string]$ProductizationJsonPath,

    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

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

function Convert-ToFullPath {
    param([string]$Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Test-ChildPath {
    param(
        [string]$Parent,
        [string]$Candidate
    )
    $parentFull = Convert-ToFullPath -Path $Parent
    $candidateFull = Convert-ToFullPath -Path $Candidate
    if ($parentFull -eq $candidateFull) {
        return $false
    }
    $parentWithSeparator = $parentFull + [System.IO.Path]::DirectorySeparatorChar
    return $candidateFull.StartsWith($parentWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-JsonProperty {
    param(
        [object]$Object,
        [string]$Name
    )
    if ($null -eq $Object) {
        return $null
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Get-NestedJsonProperty {
    param(
        [object]$Object,
        [string[]]$Path
    )
    $current = $Object
    foreach ($segment in $Path) {
        $current = Get-JsonProperty -Object $current -Name $segment
        if ($null -eq $current) {
            return $null
        }
    }
    return $current
}

function Read-JsonPayload {
    param(
        [string]$Path,
        [string]$CheckName,
        [string]$Description
    )
    Add-Check "${CheckName}:file" (Test-Path -LiteralPath $Path -PathType Leaf) $Description
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        $payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 30
        Add-Check "${CheckName}:parse" $true "$Description must be parseable JSON."
        return $payload
    } catch {
        Add-Check "${CheckName}:parse" $false "$Description could not be parsed: $($_.Exception.Message)"
        return $null
    }
}

function Add-NestedValueCheck {
    param(
        [object]$Payload,
        [string[]]$Path,
        [object]$Expected,
        [string]$Name,
        [string]$Message
    )
    $actual = Get-NestedJsonProperty -Object $Payload -Path $Path
    Add-Check $Name ($actual -eq $Expected) $Message
}

$installRootFull = Convert-ToFullPath -Path $InstallRoot
$appDataRootFull = Convert-ToFullPath -Path $AppDataRoot
$migrationEvidencePath = Join-Path (Join-Path $appDataRootFull 'State\Migration') 'localbase_import.json'
$releaseManifestPath = Join-Path $installRootFull 'release_manifest.json'

Add-Check 'install_root:exists' (Test-Path -LiteralPath $installRootFull -PathType Container) `
    'Installed app root must exist.'
Add-Check 'appdata_root:exists' (Test-Path -LiteralPath $appDataRootFull -PathType Container) `
    'Per-user AppData root must exist after first launch.'
Add-Check 'roots:distinct' ($installRootFull -ne $appDataRootFull) `
    'Installed app root and AppData root must be different directories.'
Add-Check 'roots:appdata_not_inside_install' (-not (Test-ChildPath -Parent $installRootFull -Candidate $appDataRootFull)) `
    'AppData runtime state must not live under the immutable install root.'
Add-Check 'roots:install_not_inside_appdata' (-not (Test-ChildPath -Parent $appDataRootFull -Candidate $installRootFull)) `
    'The immutable install root must not be nested inside the app runtime data root.'
Add-Check 'install_root:release_manifest' (Test-Path -LiteralPath $releaseManifestPath -PathType Leaf) `
    'Installed app should include release_manifest.json evidence.' 'warning'

$forbiddenInstallRuntime = @(
    'LocalBase',
    'State',
    'Logs',
    'RunLogs',
    'DiagnosticsExports',
    'UpdateState',
    'Backups'
)
foreach ($relative in $forbiddenInstallRuntime) {
    $path = Join-Path $installRootFull $relative
    Add-Check "install_root:no_mutable_$relative" (-not (Test-Path -LiteralPath $path)) `
        "Mutable runtime folder $relative must not be created under the installed app root."
}

$expectedAppDataRuntime = @(
    'State',
    'Logs',
    'RunLogs',
    'DiagnosticsExports',
    'UpdateState',
    'Backups',
    'State\Migration'
)
foreach ($relative in $expectedAppDataRuntime) {
    $path = Join-Path $appDataRootFull $relative
    $name = $relative.Replace('\', '_').Replace('/', '_')
    Add-Check "appdata_root:has_$name" (Test-Path -LiteralPath $path -PathType Container) `
        "AppData runtime folder $relative must exist after first launch."
}

$forbiddenAppDataPayloads = @(
    'SourceMovies',
    'SourceTV',
    'Outsource',
    'Scratch',
    'PendingPublish',
    'Completed',
    'FinalLibraryRoot'
)
foreach ($relative in $forbiddenAppDataPayloads) {
    $path = Join-Path $appDataRootFull $relative
    Add-Check "appdata_root:no_media_payload_$relative" (-not (Test-Path -LiteralPath $path)) `
        "Media payload folder $relative must not be imported into AppData runtime state."
}

$migrationPayload = Read-JsonPayload -Path $migrationEvidencePath -CheckName 'migration_evidence' `
    -Description 'Migration evidence State\Migration\localbase_import.json'
if ($migrationPayload) {
    Add-NestedValueCheck -Payload $migrationPayload -Path @('schema_version') -Expected 'desktop_appdata_migration.v1' `
        -Name 'migration:schema' -Message 'Migration evidence must use desktop_appdata_migration.v1.'
    Add-NestedValueCheck -Payload $migrationPayload -Path @('status') -Expected 'complete' `
        -Name 'migration:status' -Message 'Migration evidence must report complete status.'
    Add-NestedValueCheck -Payload $migrationPayload -Path @('appdata_available') -Expected $true `
        -Name 'migration:appdata_available' -Message 'Migration evidence must report AppData availability.'
    Add-NestedValueCheck -Payload $migrationPayload -Path @('writes_media') -Expected $false `
        -Name 'migration:writes_media' -Message 'Migration evidence must prove it did not write media payloads.'
    Add-NestedValueCheck -Payload $migrationPayload -Path @('deletes_media') -Expected $false `
        -Name 'migration:deletes_media' -Message 'Migration evidence must prove it did not delete media payloads.'

    $protectedBoundaryNames = @(
        'moved_source_media',
        'deleted_source_media',
        'copied_scratch_payloads',
        'copied_output_payloads',
        'copied_pending_publish_payloads',
        'copied_completed_media'
    )
    foreach ($boundaryName in $protectedBoundaryNames) {
        Add-NestedValueCheck -Payload $migrationPayload -Path @('protected_boundaries', $boundaryName) -Expected $false `
            -Name "migration:protected_$boundaryName" `
            -Message "Migration evidence must prove protected boundary $boundaryName stayed false."
    }
}

$productizationPayload = $null
if ($ProductizationJsonPath) {
    $productizationFull = Convert-ToFullPath -Path $ProductizationJsonPath
    $productizationPayload = Read-JsonPayload -Path $productizationFull -CheckName 'productization_json' `
        -Description 'Saved /api/maintenance/productization response'
} else {
    $productizationFull = $null
    Add-Check 'productization_json:not_provided' $false `
        'Pass -ProductizationJsonPath with a saved /api/maintenance/productization response for full installed-app verification.' 'warning'
}

if ($productizationPayload) {
    Add-NestedValueCheck -Payload $productizationPayload -Path @('schema_version') -Expected 'desktop_productization_status.v1' `
        -Name 'productization:schema' -Message 'Productization status must use desktop_productization_status.v1.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('release_channel') -Expected $Channel `
        -Name 'productization:release_channel' -Message 'Productization status release channel must match the selected verifier channel.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('installer', 'target') -Expected 'nsis' `
        -Name 'productization:installer_target' -Message 'Productization status must report NSIS as the installer target.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('installer', 'msi_enabled') -Expected $false `
        -Name 'productization:msi_disabled' -Message 'Productization status must report MSI disabled for the first beta lane.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('updater', 'mode') -Expected 'prompted' `
        -Name 'productization:updater_mode' -Message 'Productization status must report prompted updates.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('updater', 'active_channel') -Expected $Channel `
        -Name 'productization:updater_channel' -Message 'Productization updater channel must match the selected verifier channel.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('updater', 'close_readiness_required') -Expected $true `
        -Name 'productization:close_readiness_required' -Message 'Productization status must require backend close-readiness before update application.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('runtime_roots', 'appdata_available') -Expected $true `
        -Name 'productization:appdata_available' -Message 'Productization status must report AppData availability.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('migration', 'guarded_import_runs_in_productized_mode') -Expected $true `
        -Name 'productization:guarded_migration' -Message 'Productization status must report guarded migration for productized launches.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('migration', 'writes_media') -Expected $false `
        -Name 'productization:migration_writes_media' -Message 'Productization status must report migration does not write media payloads.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('migration', 'deletes_media') -Expected $false `
        -Name 'productization:migration_deletes_media' -Message 'Productization status must report migration does not delete media payloads.'
    Add-NestedValueCheck -Payload $productizationPayload -Path @('release_manifest', 'found') -Expected $true `
        -Name 'productization:release_manifest' -Message 'Productization status should find installed release manifest evidence.'

    $runtimeRootNames = @(
        'appdata_root',
        'config_root',
        'state_root',
        'logs_root',
        'run_logs_root',
        'diagnostics_exports_root',
        'update_state_root',
        'backups_root',
        'migration_root'
    )
    foreach ($rootName in $runtimeRootNames) {
        Add-NestedValueCheck -Payload $productizationPayload -Path @('runtime_roots', 'roots', $rootName, 'exists') -Expected $true `
            -Name "productization:runtime_root_$rootName" `
            -Message "Productization status must report runtime root $rootName exists."
    }
}

$errorCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'error' }).Count
$warningCount = @($checks | Where-Object { -not $_.ok -and $_.severity -eq 'warning' }).Count
$result = [pscustomobject][ordered]@{
    schema_version = 'private_beta_installed_layout_verification.v1'
    ok = ($errorCount -eq 0)
    channel = $Channel
    version = $Version
    install_root = $installRootFull
    appdata_root = $appDataRootFull
    migration_evidence_path = $migrationEvidencePath
    productization_json_path = $productizationFull
    error_count = $errorCount
    warning_count = $warningCount
    checks = @($checks)
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 12
} else {
    if ($result.ok) {
        Write-Host "Private beta installed layout verification passed for $Channel $Version."
    } else {
        Write-Host "Private beta installed layout verification failed for $Channel $Version."
    }
    foreach ($check in $checks) {
        $prefix = if ($check.ok) { 'PASS' } elseif ($check.severity -eq 'warning') { 'WARN' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $prefix, $check.name, $check.message)
    }
}

if (-not $result.ok) {
    exit 1
}
