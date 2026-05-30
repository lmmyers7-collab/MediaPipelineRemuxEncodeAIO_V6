$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
. (Join-Path $repoRoot 'engine\config\config_keys.ps1')
. (Join-Path $repoRoot 'engine\config\config_schema.ps1')

$entrypointText = Get-Content -LiteralPath (Join-Path $repoRoot 'Pipeline\MediaPipeline.ps1') -Raw
if ($entrypointText -notmatch "'ConfigKeys\.ps1'") {
    throw 'Pipeline entrypoint module load list must include ConfigKeys.ps1.'
}

$registry = Get-MediaPipelineConfigKeyRegistry
$knownKeys = @(Get-MediaPipelineKnownConfigKeys)
$keyOrder = @(Get-MediaPipelineConfigKeyOrder)
$schemaOrder = @(Get-MediaPipelineConfigOrderedKeys)
$networkKeys = @(Get-MediaPipelineNetworkConfigKeys)

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

$templateConfig = Import-PowerShellDataFile -Path (Join-Path $repoRoot 'Pipeline\MediaPipeline_config_template.psd1')
# Prefer the V7 convention; fall back to the legacy `_chatgpt` operator file
# if the new file is absent on this machine.
$liveConfigPath = @(
    (Join-Path $repoRoot 'Pipeline\MediaPipeline_config.psd1'),
    (Join-Path $repoRoot 'Pipeline\MediaPipeline_config_chatgpt.psd1')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $liveConfigPath) {
    throw "No live config found at Pipeline\MediaPipeline_config.psd1 or Pipeline\MediaPipeline_config_chatgpt.psd1"
}
$liveConfig = Import-PowerShellDataFile -Path $liveConfigPath
foreach ($pair in @(
    @{ Label = 'template'; Keys = @($templateConfig.Keys) },
    @{ Label = 'live'; Keys = @($liveConfig.Keys) }
)) {
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

$scanFiles = @(
    Get-Item -LiteralPath (Join-Path $repoRoot 'Pipeline\MediaPipeline.ps1')
    Get-ChildItem -LiteralPath (Join-Path $repoRoot 'Pipeline\MediaPipeline') -Filter '*.ps1' -File -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath (Join-Path $repoRoot 'engine') -Filter '*.ps1' -File -Recurse
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
