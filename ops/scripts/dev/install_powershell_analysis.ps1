param(
    [string]$DestinationPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$RequirementsPath = Join-Path $RepoRoot "requirements\powershell-modules.psd1"
if (-not (Test-Path -LiteralPath $RequirementsPath -PathType Leaf)) {
    throw "PowerShell module requirements not found: $RequirementsPath"
}

$Requirements = Import-PowerShellDataFile -LiteralPath $RequirementsPath
$AnalyzerRequirement = $Requirements.Modules.PSScriptAnalyzer
$RequiredVersionText = [string]$AnalyzerRequirement.RequiredVersion
$RequiredGuidText = [string]$AnalyzerRequirement.Guid
$Repository = [string]$AnalyzerRequirement.Repository
$RequiredVersion = $null
$RequiredGuid = [guid]::Empty
if (
    [string]::IsNullOrWhiteSpace($RequiredVersionText) -or
    -not [version]::TryParse($RequiredVersionText, [ref]$RequiredVersion) -or
    -not [guid]::TryParse($RequiredGuidText, [ref]$RequiredGuid) -or
    [string]::IsNullOrWhiteSpace($Repository)
) {
    throw "Invalid PSScriptAnalyzer dependency metadata in $RequirementsPath"
}

if ([string]::IsNullOrWhiteSpace($DestinationPath)) {
    if (-not [string]::IsNullOrWhiteSpace($env:MP_POWERSHELL_ANALYSIS_MODULE_ROOT)) {
        $DestinationPath = $env:MP_POWERSHELL_ANALYSIS_MODULE_ROOT
    } elseif (-not [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
        $DestinationPath = Join-Path $env:RUNNER_TEMP "mediapipeline-powershell-analysis"
    } else {
        $DestinationPath = Join-Path ([System.IO.Path]::GetTempPath()) "mediapipeline-powershell-analysis"
    }
}

$DestinationPath = [System.IO.Path]::GetFullPath($DestinationPath)
$ModuleManifestPath = Join-Path $DestinationPath "PSScriptAnalyzer\$RequiredVersionText\PSScriptAnalyzer.psd1"
if (-not (Test-Path -LiteralPath $ModuleManifestPath -PathType Leaf)) {
    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    Save-Module `
        -Name PSScriptAnalyzer `
        -RequiredVersion $RequiredVersionText `
        -Repository $Repository `
        -Path $DestinationPath `
        -ErrorAction Stop
}

$Analyzer = Test-ModuleManifest -Path $ModuleManifestPath -ErrorAction Stop
if (
    $Analyzer.Name -ne "PSScriptAnalyzer" -or
    $Analyzer.Version -ne $RequiredVersion -or
    $Analyzer.Guid -ne $RequiredGuid
) {
    throw "PSScriptAnalyzer $RequiredVersionText identity is invalid at $ModuleManifestPath"
}

Write-Host "PSScriptAnalyzer $RequiredVersionText is isolated at $ModuleManifestPath"
