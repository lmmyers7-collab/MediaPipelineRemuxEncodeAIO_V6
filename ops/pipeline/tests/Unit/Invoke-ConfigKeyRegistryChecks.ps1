$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Config-key registry checks resolved an invalid repo root: $repoRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Config-key registry checks resolved a repo root without ops\pipeline\engine: $repoRoot"
}
. (Join-Path $repoRoot 'ops\pipeline\engine\config\config_keys.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\config\config_schema.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\paths\output_path_planning.ps1')

$entrypointText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline.ps1') -Raw
$moduleLoaderText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\module_loader.ps1') -Raw
if (($entrypointText + "`n" + $moduleLoaderText) -notmatch "'ConfigKeys\.ps1'") {
    throw 'Pipeline entrypoint module load list must include ConfigKeys.ps1.'
}

$registry = Get-MediaPipelineConfigKeyRegistry
$knownKeys = @(Get-MediaPipelineKnownConfigKeys)
$keyOrder = @(Get-MediaPipelineConfigKeyOrder)
$schemaOrder = @(Get-MediaPipelineConfigOrderedKeys)
$networkKeys = @(Get-MediaPipelineNetworkConfigKeys)
$jsonSchema = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\config\schemas\media_pipeline_config.schema.json') -Raw | ConvertFrom-Json
$jsonSchemaKeys = @($jsonSchema.properties.PSObject.Properties.Name)

function Assert-StringSequenceEqual {
    param(
        [Parameter(Mandatory)] [array] $Actual,
        [Parameter(Mandatory)] [array] $Expected,
        [Parameter(Mandatory)] [string] $Label
    )

    if ($Actual.Count -ne $Expected.Count) {
        throw "$Label count mismatch. Actual=$($Actual.Count) Expected=$($Expected.Count)"
    }
    for ($i = 0; $i -lt $Expected.Count; $i++) {
        if ([string]$Actual[$i] -ne [string]$Expected[$i]) {
            throw "$Label sequence drift at index $i. Actual='$($Actual[$i])' Expected='$($Expected[$i])'"
        }
    }
}

function Assert-StringSetEqual {
    param(
        [Parameter(Mandatory)] [array] $Actual,
        [Parameter(Mandatory)] [array] $Expected,
        [Parameter(Mandatory)] [string] $Label
    )

    $missing = @($Expected | Where-Object { $_ -notin $Actual })
    $extra = @($Actual | Where-Object { $_ -notin $Expected })
    if ($missing.Count -gt 0 -or $extra.Count -gt 0) {
        throw "$Label set drift. Missing=[$($missing -join ', ')] Extra=[$($extra -join ', ')]"
    }
}

function Get-JsonSchemaProperty {
    param([Parameter(Mandatory)] [string] $Key)

    $property = $jsonSchema.properties.PSObject.Properties[$Key]
    if (-not $property) { return $null }
    return $property.Value
}

function Get-JsonSchemaEnum {
    param([Parameter(Mandatory)] [string] $Key)

    $property = Get-JsonSchemaProperty -Key $Key
    if (-not $property -or -not $property.PSObject.Properties['enum']) { return @() }
    return @($property.enum)
}

$projectionTestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mp-settings-projection-" + [guid]::NewGuid().ToString('N'))
$previousLocalAppData = $env:LOCALAPPDATA
try {
    New-Item -ItemType Directory -Path $projectionTestRoot -Force | Out-Null
    $env:LOCALAPPDATA = $projectionTestRoot
    $projectionConfigPath = Join-Path $projectionTestRoot 'MediaPipeline_config.psd1'
    $projectionConfigText = @"
@{
    ConfigSchemaVersion = 1
    SourceMovies = 'C:\Media\Movies'
    SourceTV = 'C:\Media\TV'
    Outsource = 'D:\MediaOut'
    LocalBase = 'E:\MediaScratch'
}
"@
    Set-Content -LiteralPath $projectionConfigPath -Value $projectionConfigText -Encoding UTF8
    $projectionManifestDir = Join-Path $projectionTestRoot 'MediaPipelineRemuxEncodeAIO'
    New-Item -ItemType Directory -Path $projectionManifestDir -Force | Out-Null
    $projectionManifestPath = Join-Path $projectionManifestDir 'settings_projection.v1.json'
    $projectionHash = ((Get-FileHash -Algorithm SHA256 -LiteralPath $projectionConfigPath).Hash).ToLowerInvariant()
    [ordered]@{
        schema_version = 'desktop_settings_projection.v1'
        psd1_path = $projectionConfigPath
        psd1_sha256 = $projectionHash
        generated_at_utc = '2026-06-23T00:00:00Z'
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $projectionManifestPath -Encoding UTF8

    $projectionOk = Test-MediaPipelineSettingsProjectionManifest -ConfigPath $projectionConfigPath
    if (-not [bool]$projectionOk.Ok -or [string]$projectionOk.Status -ne 'verified') {
        throw "Settings projection manifest check should verify fresh generated PSD1. Status=$($projectionOk.Status) Errors=$(@($projectionOk.Errors) -join '; ')"
    }

    Add-Content -LiteralPath $projectionConfigPath -Value '# manual drift'
    $projectionStale = Test-MediaPipelineSettingsProjectionManifest -ConfigPath $projectionConfigPath
    $projectionStaleErrors = @($projectionStale.Errors) -join "`n"
    if ([bool]$projectionStale.Ok -or $projectionStaleErrors -notmatch 'Settings PSD1 projection is stale') {
        throw 'Settings projection manifest check must fail closed when generated PSD1 hash drifts.'
    }
} finally {
    $env:LOCALAPPDATA = $previousLocalAppData
    if (Test-Path -LiteralPath $projectionTestRoot) {
        Remove-Item -LiteralPath $projectionTestRoot -Recurse -Force
    }
}

if ($registry.Count -ne $knownKeys.Count) {
    throw "Config-key registry count $($registry.Count) does not match known key count $($knownKeys.Count)."
}

$missingFromRegistry = @($schemaOrder | Where-Object { $_ -notin $knownKeys })
if ($missingFromRegistry.Count -gt 0) {
    throw "ConfigSchema ordered keys missing from ConfigKeys registry: $($missingFromRegistry -join ', ')"
}

$missingFromSchemaOrder = @($keyOrder | Where-Object { $_ -notin $schemaOrder })
if ($missingFromSchemaOrder.Count -gt 0) {
    throw "ConfigKeys non-network key order includes keys missing from ConfigSchema order: $($missingFromSchemaOrder -join ', ')"
}

for ($i = 0; $i -lt $schemaOrder.Count; $i++) {
    if ($schemaOrder[$i] -ne $keyOrder[$i]) {
        throw "Config key order drift at index $i. ConfigSchema='$($schemaOrder[$i])' ConfigKeys='$($keyOrder[$i])'"
    }
}

$networkMissing = @($networkKeys | Where-Object { $_ -notin $knownKeys })
if ($networkMissing.Count -gt 0) {
    throw "Network config keys missing from known registry: $($networkMissing -join ', ')"
}

$missingFromJsonSchema = @($schemaOrder | Where-Object { $_ -notin $jsonSchemaKeys })
if ($missingFromJsonSchema.Count -gt 0) {
    throw "JSON config schema missing ordered config keys: $($missingFromJsonSchema -join ', ')"
}

$unknownJsonSchemaKeys = @($jsonSchemaKeys | Where-Object { $_ -notin $knownKeys })
if ($unknownJsonSchemaKeys.Count -gt 0) {
    throw "JSON config schema includes unknown config keys: $($unknownJsonSchemaKeys -join ', ')"
}

$networkJsonSchemaKeys = @($jsonSchemaKeys | Where-Object { $_ -in $networkKeys })
if ($networkJsonSchemaKeys.Count -gt 0) {
    throw "Desktop JSON config schema should not include network-only keys: $($networkJsonSchemaKeys -join ', ')"
}

$templateConfig = Import-PowerShellDataFile -Path (Join-Path $repoRoot 'ops\pipeline\config\MediaPipeline_config_template.psd1')
$configDocuments = @(
    @{ Label = 'template'; Keys = @($templateConfig.Keys) }
)
$liveConfigPath = Join-Path $repoRoot 'ops\pipeline\config\MediaPipeline_config.psd1'
if (Test-Path -LiteralPath $liveConfigPath -PathType Leaf) {
    $liveConfig = Import-PowerShellDataFile -Path $liveConfigPath
    $configDocuments += @{ Label = 'live'; Keys = @($liveConfig.Keys) }
}
foreach ($pair in $configDocuments) {
    $unknown = @($pair.Keys | Where-Object { $_ -notin $knownKeys })
    if ($unknown.Count -gt 0) {
        throw "Unknown $($pair.Label) PSD1 config keys: $($unknown -join ', ')"
    }
}

if ((Get-MediaPipelineConfigKey -Name 'LocalBase') -ne 'LocalBase') {
    throw 'Get-MediaPipelineConfigKey did not resolve LocalBase.'
}
if (-not (Test-MediaPipelineKnownConfigKey -Key 'SourceMovies')) {
    throw 'Test-MediaPipelineKnownConfigKey rejected SourceMovies.'
}
if (Test-MediaPipelineKnownConfigKey -Key 'NotARealConfigKey') {
    throw 'Test-MediaPipelineKnownConfigKey accepted NotARealConfigKey.'
}

$libraryOverrideKeys = @(Get-MediaPipelineLibraryOverrideConfigKeys)
$missingVobSubLibraryOverrideKeys = @(
    'ConvertVobSubToSrt',
    'DropVobSubAfterConversion',
    'VobSubExtractLanguages',
    'VobSubOcrToolPath',
    'VobSubOcrTimeoutSeconds',
    'TreatVobSubSignsSongsAsForced'
) | Where-Object { $_ -notin $libraryOverrideKeys }
if ($missingVobSubLibraryOverrideKeys.Count -gt 0) {
    throw "Library override allowlist missing VobSub keys: $($missingVobSubLibraryOverrideKeys -join ', ')"
}

$unknownLibraryOverrideKeys = @($libraryOverrideKeys | Where-Object { $_ -notin $knownKeys })
if ($unknownLibraryOverrideKeys.Count -gt 0) {
    throw "Library override allowlist includes unknown config keys: $($unknownLibraryOverrideKeys -join ', ')"
}

$schemaLibraryOverrideKeys = @(Get-MediaPipelineConfigLibraryOverrideKeys)
Assert-StringSequenceEqual -Actual $libraryOverrideKeys -Expected $schemaLibraryOverrideKeys -Label 'PowerShell runtime/schema library override allowlist'

$globalOnlyOverrideKeys = @(
    'ConfigSchemaVersion',
    'SourceMovies',
    'SourceTV',
    'Outsource',
    'LibraryProfiles',
    'LocalBase',
    'DeferredPublish',
    'PendingPublishDrainMode',
    'PendingPublishDrainBatchSize',
    'AllowSubtitleHelperFallback',
    'PipelineDebugLogMaxBytes',
    'FinalLibraryPromotionEnabled',
    'FinalLibraryPromotionRules',
    'FinalLibraryPromotionVerificationMode',
    'FinalLibraryPromotionCleanupAfterVerified',
    'FinalLibraryPromotionOverwriteExisting',
    'ShowOverrides',
    'NetworkRole',
    'StateDbCompletedJobsMaxRows'
) | Where-Object { $_ -in $libraryOverrideKeys }
if ($globalOnlyOverrideKeys.Count -gt 0) {
    throw "Library override allowlist includes global-only/config-shape keys: $($globalOnlyOverrideKeys -join ', ')"
}

$friendlyLabelKeys = @(
    'ProcessingStrategy',
    'EnforcementMode',
    'OutputSizeCheck',
    'EncoderQualityPreset',
    'EncodeTargetMode',
    'Processing Strategy',
    'Enforcement Mode',
    'Output Size Check'
)
$friendlyKnown = @($friendlyLabelKeys | Where-Object { $_ -in $knownKeys })
$friendlyOverrides = @($friendlyLabelKeys | Where-Object { $_ -in $libraryOverrideKeys })
$friendlyJson = @($friendlyLabelKeys | Where-Object { $_ -in $jsonSchemaKeys })
if ($friendlyKnown.Count -gt 0 -or $friendlyOverrides.Count -gt 0 -or $friendlyJson.Count -gt 0) {
    throw "Friendly display labels must not be persisted config keys. Known=[$($friendlyKnown -join ', ')] Overrides=[$($friendlyOverrides -join ', ')] Json=[$($friendlyJson -join ', ')]"
}

$evidenceOnlyKeys = @(
    'library_effective_settings',
    'runtime_effective_settings'
)
$evidenceKnown = @($evidenceOnlyKeys | Where-Object { $_ -in $knownKeys })
$evidenceOverrides = @($evidenceOnlyKeys | Where-Object { $_ -in $libraryOverrideKeys })
$evidenceJson = @($evidenceOnlyKeys | Where-Object { $_ -in $jsonSchemaKeys })
if ($evidenceKnown.Count -gt 0 -or $evidenceOverrides.Count -gt 0 -or $evidenceJson.Count -gt 0) {
    throw "Runtime/library effective-settings evidence must not be persisted config keys. Known=[$($evidenceKnown -join ', ')] Overrides=[$($evidenceOverrides -join ', ')] Json=[$($evidenceJson -join ', ')]"
}

$vobSubKeys = @(
    'ConvertVobSubToSrt',
    'DropVobSubAfterConversion',
    'VobSubExtractLanguages',
    'VobSubOcrToolPath',
    'VobSubOcrTimeoutSeconds',
    'TreatVobSubSignsSongsAsForced'
)
$vobSubMissingKnown = @($vobSubKeys | Where-Object { $_ -notin $knownKeys })
$vobSubMissingJson = @($vobSubKeys | Where-Object { $_ -notin $jsonSchemaKeys })
$vobSubMissingOverride = @($vobSubKeys | Where-Object { $_ -notin $libraryOverrideKeys })
if ($vobSubMissingKnown.Count -gt 0 -or $vobSubMissingJson.Count -gt 0 -or $vobSubMissingOverride.Count -gt 0) {
    throw "VobSub config keys must stay registered, schema-covered, and library-overridable. KnownMissing=[$($vobSubMissingKnown -join ', ')] JsonMissing=[$($vobSubMissingJson -join ', ')] OverrideMissing=[$($vobSubMissingOverride -join ', ')]"
}

foreach ($enumPolicy in @(
    @{ Key = 'VideoCodec'; Values = @(Get-MediaPipelineVideoCodecNames) },
    @{ Key = 'VideoPreset'; Values = @(Get-MediaPipelineVideoPresetNames) },
    @{ Key = 'OutputContainer'; Values = @(Get-MediaPipelineOutputContainerNames) },
    @{ Key = 'DynamicHdrPolicy'; Values = @(Get-MediaPipelineDynamicHdrPolicyNames) },
    @{ Key = 'EncodeTuningPreset'; Values = @(Get-MediaPipelineEncodeTuningPresetNames) },
    @{ Key = 'EncodeLadder'; Values = @(Get-MediaPipelineEncodeLadderNames) },
    @{ Key = 'RoutingProfile'; Values = @(Get-MediaPipelineRoutingProfileNames) },
    @{ Key = 'RouteThresholdMode'; Values = @(Get-MediaPipelineRouteThresholdModeNames) },
    @{ Key = 'SizeGuardMode'; Values = @(Get-MediaPipelineSizeGuardModeNames) },
    @{ Key = 'AudioPassthroughProfile'; Values = @(Get-MediaPipelineAudioPassthroughProfileNames) },
    @{ Key = 'AudioTranscodeCodec'; Values = @(Get-MediaPipelineAudioTranscodeCodecNames) },
    @{ Key = 'AudioDownmixMode'; Values = @(Get-MediaPipelineAudioDownmixModeNames) },
    @{ Key = 'FinalLibraryPromotionVerificationMode'; Values = @(Get-MediaPipelineFinalLibraryPromotionVerificationModeNames) },
    @{ Key = 'PendingPublishDrainMode'; Values = @(Get-MediaPipelinePendingPublishDrainModeNames) },
    @{ Key = 'CpuEncodePreset'; Values = @(Get-MediaPipelineCpuEncodePresetNames) },
    @{ Key = 'CpuEncodeProcessPriority'; Values = @(Get-MediaPipelineCpuEncodeProcessPriorityNames) },
    @{ Key = 'ParallelEncodeMode'; Values = @(Get-MediaPipelineParallelEncodeModeNames) }
)) {
    $jsonEnum = @(Get-JsonSchemaEnum -Key ([string]$enumPolicy.Key))
    Assert-StringSetEqual -Actual @($enumPolicy.Values) -Expected $jsonEnum -Label "$($enumPolicy.Key) PowerShell/JSON enum"
}

$defaultSchemaCheck = Test-MediaPipelineConfigSchema -Config (Get-MediaPipelineConfigDefaultValues)
if (-not [bool]$defaultSchemaCheck.Ok) {
    throw "PowerShell default config failed schema validation: $(@($defaultSchemaCheck.Errors) -join '; ')"
}

$strictDefaultSchemaCheck = & {
    Set-StrictMode -Version 2.0
    Test-MediaPipelineConfigSchema -Config (Get-MediaPipelineConfigDefaultValues)
}
if (-not [bool]$strictDefaultSchemaCheck.Ok) {
    throw "PowerShell default config failed schema validation under StrictMode: $(@($strictDefaultSchemaCheck.Errors) -join '; ')"
}

foreach ($relativeRoot in @(
    @{ Key = 'SourceMovies'; Value = 'Movies' },
    @{ Key = 'SourceTV'; Value = 'TV' },
    @{ Key = 'Outsource'; Value = 'Out' },
    @{ Key = 'LocalBase'; Value = 'Scratch' }
)) {
    $relativeRootConfig = Get-MediaPipelineConfigDefaultValues
    $relativeRootConfig[[string]$relativeRoot.Key] = [string]$relativeRoot.Value
    $relativeRootCheck = Test-MediaPipelineConfigSchema -Config $relativeRootConfig
    $relativeRootErrors = @($relativeRootCheck.Errors) -join "`n"
    $expectedRelativeRootError = "$($relativeRoot.Key) must be an absolute path."
    if ([bool]$relativeRootCheck.Ok -or $relativeRootErrors -notmatch [regex]::Escape($expectedRelativeRootError)) {
        throw "PowerShell schema must reject relative $($relativeRoot.Key) root."
    }
}

$zeroAudioBitrateConfig = Get-MediaPipelineConfigDefaultValues
$zeroAudioBitrateConfig['AudioTranscodeBitrate'] = '0k'
$zeroAudioBitrateCheck = Test-MediaPipelineConfigSchema -Config $zeroAudioBitrateConfig
$zeroAudioBitrateErrors = @($zeroAudioBitrateCheck.Errors) -join "`n"
if ([bool]$zeroAudioBitrateCheck.Ok -or $zeroAudioBitrateErrors -notmatch 'AudioTranscodeBitrate') {
    throw 'PowerShell schema must reject zero audio transcode bitrate values.'
}
$audioBitrateSchema = Get-JsonSchemaProperty -Key 'AudioTranscodeBitrate'
if ([string]$audioBitrateSchema.pattern -ne '^[1-9]\d*k$') {
    throw "JSON config schema AudioTranscodeBitrate pattern drifted. Actual='$($audioBitrateSchema.pattern)'"
}

$vobSubOcrToolDefault = 'tools\SubtitleEditLegacy\SubtitleEdit.exe'
$powershellDefaults = Get-MediaPipelineConfigDefaultValues
$defaultProfileConfig = Import-PowerShellDataFile -Path (Join-Path $repoRoot 'ops\pipeline\config\profiles\Default.psd1')
$bdpgsSchemaDefault = [bool](Get-JsonSchemaProperty -Key 'ConvertBdpgsToSrt').default
if (-not [bool]$powershellDefaults['ConvertBdpgsToSrt'] -or -not [bool]$templateConfig['ConvertBdpgsToSrt'] -or -not [bool]$defaultProfileConfig['ConvertBdpgsToSrt'] -or -not $bdpgsSchemaDefault) {
    throw 'BDPGS OCR must default enabled across PowerShell defaults, template, default profile, and JSON schema.'
}
$config = @{}
function Add-StartupWarning { param([string]$Message) }
. (Join-Path $repoRoot 'ops\pipeline\engine\config\getters.ps1')
if (-not [bool](Get-ConfigBool 'ConvertBdpgsToSrt' $true)) {
    throw 'Missing ConvertBdpgsToSrt must use the new enabled default.'
}
$config = @{ ConvertBdpgsToSrt = $false }
if ([bool](Get-ConfigBool 'ConvertBdpgsToSrt' $true)) {
    throw 'An explicitly saved ConvertBdpgsToSrt=false must survive default resolution.'
}
$expectedAudioPassthroughProfile = Get-MediaPipelineAudioPassthroughProfileDefault
$expectedAudioPassthroughCodecs = @(Get-MediaPipelineAudioPassthroughProfileCodecs -Profile $expectedAudioPassthroughProfile)
if ([string]$defaultProfileConfig['AudioPassthroughProfile'] -ne $expectedAudioPassthroughProfile) {
    throw "Default profile AudioPassthroughProfile drifted. Actual='$($defaultProfileConfig['AudioPassthroughProfile'])' Expected='$expectedAudioPassthroughProfile'"
}
Assert-StringSequenceEqual -Actual @($defaultProfileConfig['CompatibleAudioCodecs']) -Expected $expectedAudioPassthroughCodecs -Label 'Default profile compatible audio codecs'
$expectedDefaultRoots = [ordered]@{
    SourceMovies = 'C:\MediaPipeline\Incoming\Movies'
    SourceTV = 'C:\MediaPipeline\Incoming\TV'
    Outsource = 'C:\MediaPipeline\Processed'
    LocalBase = 'C:\MediaPipeline\Scratch'
}
foreach ($rootPair in $expectedDefaultRoots.GetEnumerator()) {
    $key = [string]$rootPair.Key
    $expected = [string]$rootPair.Value
    $jsonDefault = [string](Get-JsonSchemaProperty -Key $key).default
    if ([string]$powershellDefaults[$key] -ne $expected) {
        throw "PowerShell default $key drifted. Actual='$($powershellDefaults[$key])' Expected='$expected'"
    }
    if ([string]$templateConfig[$key] -ne $expected) {
        throw "Template default $key drifted. Actual='$($templateConfig[$key])' Expected='$expected'"
    }
    if ([string]$defaultProfileConfig[$key] -ne $expected) {
        throw "Default profile $key drifted. Actual='$($defaultProfileConfig[$key])' Expected='$expected'"
    }
    if ($jsonDefault -ne $expected) {
        throw "JSON schema default $key drifted. Actual='$jsonDefault' Expected='$expected'"
    }
}
$expectedProfileDefaults = @{
    movies = @{ source_path = $expectedDefaultRoots['SourceMovies']; output_path = $expectedDefaultRoots['Outsource'] }
    tv = @{ source_path = $expectedDefaultRoots['SourceTV']; output_path = $expectedDefaultRoots['Outsource'] }
}
foreach ($profile in @($powershellDefaults['LibraryProfiles'])) {
    $profileId = [string]$profile['id']
    if (-not $expectedProfileDefaults.ContainsKey($profileId)) { continue }
    foreach ($fieldName in @('source_path', 'output_path')) {
        $actual = [string]$profile[$fieldName]
        $expected = [string]$expectedProfileDefaults[$profileId][$fieldName]
        if ($actual -ne $expected) {
            throw "PowerShell default LibraryProfiles[$profileId].$fieldName drifted. Actual='$actual' Expected='$expected'"
        }
    }
}
if ([string]$powershellDefaults['VobSubOcrToolPath'] -ne $vobSubOcrToolDefault) {
    throw "PowerShell VobSubOcrToolPath default drifted. Actual='$($powershellDefaults['VobSubOcrToolPath'])' Expected='$vobSubOcrToolDefault'"
}
if ([string]$templateConfig['VobSubOcrToolPath'] -ne $vobSubOcrToolDefault) {
    throw "Template VobSubOcrToolPath default drifted. Actual='$($templateConfig['VobSubOcrToolPath'])' Expected='$vobSubOcrToolDefault'"
}
if ([string]$powershellDefaults['VobSubOcrToolPath'] -match 'seconv\.exe') {
    throw 'VobSubOcrToolPath defaults must not point at seconv.exe; the VobSub OCR path requires SubtitleEdit.exe.'
}

$blankCustomOutputConfig = Get-MediaPipelineConfigDefaultValues
$blankCustomOutputConfig['LibraryProfiles'] = @(
    [ordered]@{ id = 'movies'; name = 'Movies'; enabled = $true; designation = 'movie'; source_path = 'C:\Incoming\Movies'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'tv'; name = 'TV'; enabled = $true; designation = 'tv'; source_path = 'C:\Incoming\TV'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'concerts'; name = 'Concerts'; enabled = $true; designation = 'auto'; source_path = 'C:\Incoming\Concerts'; output_path = ''; overrides = [ordered]@{} }
)
$blankCustomOutputCheck = Test-MediaPipelineConfigSchema -Config $blankCustomOutputConfig
if (-not [bool]$blankCustomOutputCheck.Ok) {
    throw "PowerShell schema must allow custom blank output_path inheritance: $(@($blankCustomOutputCheck.Errors) -join '; ')"
}

$promotionDestinationConfig = Get-MediaPipelineConfigDefaultValues
$promotionDestinationConfig['LibraryProfiles'] = @(
    [ordered]@{ id = 'movies'; name = 'Movies'; enabled = $true; designation = 'movie'; source_path = 'C:\Incoming\Movies'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'tv'; name = 'TV'; enabled = $true; designation = 'tv'; source_path = 'C:\Incoming\TV'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'concerts'; name = 'Concerts'; enabled = $true; designation = 'auto'; source_path = 'C:\Incoming\Concerts'; output_path = ''; promotion_enabled = $true; promotion_destination = ''; overrides = [ordered]@{} }
)
$promotionDestinationCheck = Test-MediaPipelineConfigSchema -Config $promotionDestinationConfig
$promotionDestinationErrors = @($promotionDestinationCheck.Errors) -join "`n"
if ([bool]$promotionDestinationCheck.Ok -or $promotionDestinationErrors -notmatch 'Concerts promotion_destination cannot be empty when promotion is enabled') {
    throw 'PowerShell schema must still require explicit promotion_destination when promotion is enabled.'
}

$unsafeProfileRootsConfig = Get-MediaPipelineConfigDefaultValues
$unsafeProfileRootsConfig['LibraryProfiles'] = @(
    [ordered]@{ id = 'movies'; name = 'Movies'; enabled = $true; designation = 'movie'; source_path = 'C:\Incoming\Movies'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'tv'; name = 'TV'; enabled = $true; designation = 'tv'; source_path = 'C:\Incoming\TV'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'concerts'; name = 'Concerts'; enabled = $true; designation = 'auto'; source_path = 'relative-source'; output_path = 'relative-output'; promotion_enabled = $true; promotion_destination = 'relative-final'; overrides = [ordered]@{} },
    [ordered]@{ id = 'extras'; name = 'Extras'; enabled = $true; designation = 'auto'; source_path = 'F:\Library'; output_path = 'F:\Library\Processed'; promotion_enabled = $true; promotion_destination = 'F:\Library\Final'; overrides = [ordered]@{} }
)
$unsafeProfileRootsCheck = Test-MediaPipelineConfigSchema -Config $unsafeProfileRootsConfig
$unsafeProfileRootsErrors = @($unsafeProfileRootsCheck.Errors) -join "`n"
foreach ($expectedProfileRootError in @(
    'Concerts source_path must be an absolute path.',
    'Concerts output_path must be an absolute path.',
    'Concerts promotion_destination must be an absolute path.',
    'Extras source_path and Extras output_path must not be nested inside each other.',
    'Extras source_path and Extras promotion_destination must not be nested inside each other.'
)) {
    if ([bool]$unsafeProfileRootsCheck.Ok -or $unsafeProfileRootsErrors -notmatch [regex]::Escape($expectedProfileRootError)) {
        throw "PowerShell schema must reject unsafe LibraryProfiles roots: $expectedProfileRootError"
    }
}

$friendlyOverrideConfig = Get-MediaPipelineConfigDefaultValues
$friendlyOverrideConfig['LibraryProfiles'] = @(
    [ordered]@{
        id = 'movies'
        name = 'Movies'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\Incoming\Movies'
        output_path = 'D:\Processed'
        overrides = [ordered]@{ editor = [ordered]@{ ProcessingStrategy = 'manual' } }
    },
    [ordered]@{ id = 'tv'; name = 'TV'; enabled = $true; designation = 'tv'; source_path = 'C:\Incoming\TV'; output_path = 'D:\Processed'; overrides = [ordered]@{} }
)
$friendlyOverrideCheck = Test-MediaPipelineConfigSchema -Config $friendlyOverrideConfig
$friendlyOverrideErrors = @($friendlyOverrideCheck.Errors) -join "`n"
if ([bool]$friendlyOverrideCheck.Ok -or $friendlyOverrideErrors -notmatch 'ProcessingStrategy is not a supported library override key') {
    throw 'PowerShell schema must reject friendly label aliases inside library overrides.'
}

foreach ($numericPolicy in @(
    @{ Key = 'MovieRoute1080pTargetSizeGB'; Below = 0 },
    @{ Key = 'MovieRoute1440pTargetSizeGB'; Below = 0 },
    @{ Key = 'MovieRoute4KTargetSizeGB'; Below = 0 },
    @{ Key = 'TVRoute1080pTargetSizeGB'; Below = 0 },
    @{ Key = 'TVRoute1440pTargetSizeGB'; Below = 0 },
    @{ Key = 'TVRoute4KTargetSizeGB'; Below = 0 },
    @{ Key = 'Route1080pUpperHeightTolerancePercent'; Below = -1; Above = 101 },
    @{ Key = 'Route1080pMaxVideoBitrateMbps'; Below = 0; Above = 501 },
    @{ Key = 'Route1440pLowerHeightTolerancePercent'; Below = -1; Above = 101 },
    @{ Key = 'Route1440pUpperHeightTolerancePercent'; Below = -1; Above = 101 },
    @{ Key = 'Route1440pMaxVideoBitrateMbps'; Below = 0; Above = 501 },
    @{ Key = 'Route4KLowerHeightTolerancePercent'; Below = -1; Above = 101 },
    @{ Key = 'Route4KMaxVideoBitrateMbps'; Below = 0; Above = 501 },
    @{ Key = 'H264RemuxMaxBitrateMbps'; Below = 0; Above = 501 },
    @{ Key = 'H264RemuxMaxHeight'; Below = 0; Above = 4321 },
    @{ Key = 'MaxEncodeGrowthPercent'; Below = -1; Above = 1001 },
    @{ Key = 'CompatibilityEncodeGrowthPercent'; Below = -1; Above = 1001 },
    @{ Key = 'VideoQuality'; Below = 0; Above = 52 },
    @{ Key = 'AudioMaxChannels'; Below = 0; Above = 17 },
    @{ Key = 'MergeThresholdMs'; Below = -1; Above = 5001 },
    @{ Key = 'SubtitleExtractTimeoutSeconds'; Below = 29; Above = 3601 },
    @{ Key = 'SubtitleProbeTimeoutSeconds'; Below = 4; Above = 601 },
    @{ Key = 'BdpgsOcrTimeoutSeconds'; Below = 59; Above = 14401 },
    @{ Key = 'VobSubOcrTimeoutSeconds'; Below = 59; Above = 14401 },
    @{ Key = 'TransientFailureRetryLimit'; Below = 0; Above = 101 },
    @{ Key = 'RobocopyTimeoutSeconds'; Below = 59; Above = 172801 },
    @{ Key = 'SourceScanTimeoutSeconds'; Below = 29; Above = 86401 },
    @{ Key = 'IndexScanTimeoutSeconds'; Below = 29; Above = 86401 },
    @{ Key = 'CleanupScanTimeoutSeconds'; Below = 29; Above = 7201 },
    @{ Key = 'CleanupStaleAgeHours'; Below = 0; Above = 721 },
    @{ Key = 'WatchScanTimeoutSeconds'; Below = 0; Above = 86401 },
    @{ Key = 'CpuEncodeMutexWaitSeconds'; Below = -1; Above = 86401 },
    @{ Key = 'CpuEncodeMaxThreads'; Below = -1; Above = 257 },
    @{ Key = 'PendingPublishDrainBatchSize'; Below = 0; Above = 1000001 },
    @{ Key = 'PipelineDebugLogMaxBytes'; Below = 1048575; Above = 2147483648 },
    @{ Key = 'StateDbCompletedJobsMaxRows'; Below = 999; Above = 10000001 },
    @{ Key = 'FallbackCpuQuality'; Below = 0; Above = 52 },
    @{ Key = 'OutputSizeMultiplier'; Below = 0.09; Above = 2.1 }
)) {
    foreach ($side in @('Below','Above')) {
        if (-not $numericPolicy.ContainsKey($side)) { continue }
        $badConfig = Get-MediaPipelineConfigDefaultValues
        $badConfig[[string]$numericPolicy.Key] = $numericPolicy[$side]
        $badResult = Test-MediaPipelineConfigSchema -Config $badConfig
        $badErrors = @($badResult.Errors) -join "`n"
        if ([bool]$badResult.Ok -or $badErrors -notmatch [regex]::Escape([string]$numericPolicy.Key)) {
            throw "PowerShell schema did not reject $($numericPolicy.Key) $side JSON/Python numeric range."
        }
    }
}

$badBucketBoundaryConfig = Get-MediaPipelineConfigDefaultValues
$badBucketBoundaryConfig['Route1080pUpperHeightTolerancePercent'] = 0
$badBucketBoundaryResult = Test-MediaPipelineConfigSchema -Config $badBucketBoundaryConfig
$badBucketBoundaryErrors = @($badBucketBoundaryResult.Errors) -join "`n"
if ([bool]$badBucketBoundaryResult.Ok -or $badBucketBoundaryErrors -notmatch 'Route height tolerance percents must create contiguous buckets') {
    throw 'PowerShell schema must reject invalid resolution-aware bitrate bucket boundaries.'
}

$scanFiles = @(
    Get-Item -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline.ps1')
    Get-ChildItem -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -Filter '*.ps1' -File -Recurse
)
$patterns = @(
    @{ Name = 'GetConfig'; Regex = 'Get-Config(?:Bool|Int|Double|Choice|LogLevel)\s+[''"](?<key>[^''"]+)[''"]' },
    @{ Name = 'ConfigIndex'; Regex = '\$config\[[''"](?<key>[^''"]+)[''"]\]' },
    @{ Name = 'ConfigContains'; Regex = '\$config\.ContainsKey\([''"](?<key>[^''"]+)[''"]\)' }
)

$unknownRefs = New-Object System.Collections.Generic.List[string]
foreach ($file in $scanFiles) {
    $text = Get-Content -LiteralPath $file.FullName -Raw
    foreach ($pattern in $patterns) {
        foreach ($match in [regex]::Matches($text, $pattern.Regex, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            $key = [string]$match.Groups['key'].Value
            if (-not (Test-MediaPipelineKnownConfigKey -Key $key)) {
                $unknownRefs.Add("$($file.FullName): $($pattern.Name) references unknown config key '$key'")
            }
        }
    }
}

if ($unknownRefs.Count -gt 0) {
    throw "Unknown PowerShell config key references:`n$($unknownRefs -join "`n")"
}

Write-Host "Config-key registry checks passed. Keys: $($knownKeys.Count); PowerShell config refs scanned: $($scanFiles.Count) files."
