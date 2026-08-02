param(
    [string]$Path = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$RequirementsPath = Join-Path $RepoRoot "requirements\powershell-modules.psd1"
if (-not (Test-Path -LiteralPath $RequirementsPath -PathType Leaf)) {
    Write-Error "PowerShell module requirements not found: $RequirementsPath"
    exit 1
}
$Requirements = Import-PowerShellDataFile -LiteralPath $RequirementsPath
$RequiredVersionText = [string]$Requirements.Modules.PSScriptAnalyzer.RequiredVersion
$RequiredGuidText = [string]$Requirements.Modules.PSScriptAnalyzer.Guid
$RequiredVersion = $null
$RequiredGuid = [guid]::Empty
if (
    [string]::IsNullOrWhiteSpace($RequiredVersionText) -or
    -not [version]::TryParse($RequiredVersionText, [ref]$RequiredVersion) -or
    -not [guid]::TryParse($RequiredGuidText, [ref]$RequiredGuid)
) {
    Write-Error "Invalid PSScriptAnalyzer dependency metadata in $RequirementsPath"
    exit 1
}

if (-not [string]::IsNullOrWhiteSpace($env:MP_POWERSHELL_ANALYSIS_MODULE_ROOT)) {
    $ModuleRoot = $env:MP_POWERSHELL_ANALYSIS_MODULE_ROOT
} elseif (-not [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    $ModuleRoot = Join-Path $env:RUNNER_TEMP "mediapipeline-powershell-analysis"
} else {
    $ModuleRoot = Join-Path ([System.IO.Path]::GetTempPath()) "mediapipeline-powershell-analysis"
}
$ModuleRoot = [System.IO.Path]::GetFullPath($ModuleRoot)
$ModuleManifestPath = Join-Path $ModuleRoot "PSScriptAnalyzer\$RequiredVersionText\PSScriptAnalyzer.psd1"
if (-not (Test-Path -LiteralPath $ModuleManifestPath -PathType Leaf)) {
    Write-Error "Required isolated PSScriptAnalyzer $RequiredVersionText is not installed at $ModuleManifestPath."
    exit 1
}
$Analyzer = Test-ModuleManifest -Path $ModuleManifestPath -ErrorAction Stop
if (
    $Analyzer.Name -ne "PSScriptAnalyzer" -or
    $Analyzer.Version -ne $RequiredVersion -or
    $Analyzer.Guid -ne $RequiredGuid
) {
    Write-Error "Required PSScriptAnalyzer $RequiredVersionText identity is invalid at $ModuleManifestPath."
    exit 1
}

if ([string]::IsNullOrWhiteSpace($Path)) {
    $Path = Join-Path $RepoRoot "ops\pipeline\engine"
} elseif (-not [System.IO.Path]::IsPathRooted($Path)) {
    $Path = Join-Path $RepoRoot $Path
}

$ResolvedPath = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
if ($null -eq $ResolvedPath) {
    Write-Error "PSScriptAnalyzer target path not found: $Path"
    exit 1
}
$Path = $ResolvedPath.ProviderPath

Remove-Module -Name PSScriptAnalyzer -Force -ErrorAction SilentlyContinue
$LoadedAnalyzer = Import-Module -Name $ModuleManifestPath -Force -PassThru -ErrorAction Stop
$ExpectedModuleBase = (Resolve-Path -LiteralPath (Split-Path -Parent $ModuleManifestPath)).ProviderPath
$LoadedModuleBase = (Resolve-Path -LiteralPath $LoadedAnalyzer.ModuleBase).ProviderPath
$LoadedModulePath = (Resolve-Path -LiteralPath $LoadedAnalyzer.Path).ProviderPath
$AnalyzerCommand = @(
    Get-Command -Name Invoke-ScriptAnalyzer -All -ErrorAction Stop |
        Where-Object {
            $null -ne $_.Module -and
            (Resolve-Path -LiteralPath $_.Module.Path).ProviderPath -eq $LoadedModulePath
        }
) | Select-Object -First 1
if (
    $LoadedAnalyzer.Version -ne $RequiredVersion -or
    $LoadedAnalyzer.Guid -ne $RequiredGuid -or
    $LoadedModuleBase -ne $ExpectedModuleBase -or
    $null -eq $AnalyzerCommand
) {
    Write-Error "Required PSScriptAnalyzer $RequiredVersionText command origin is invalid."
    exit 1
}
$Findings = & $AnalyzerCommand -Path $Path -Recurse -Severity Error
if ($Findings) {
    $Findings | Format-Table -AutoSize | Out-String | Write-Error
    exit 1
}

Write-Host "PSScriptAnalyzer $RequiredVersionText passed for $Path"
