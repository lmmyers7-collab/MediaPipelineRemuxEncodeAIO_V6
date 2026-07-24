# Shared by the Tauri prerequisite entrypoint and focused provenance tests.
Set-StrictMode -Version 2.0

function New-MsvcBuildToolsProbeResult {
    param(
        [bool]$WorkloadFound = $false,
        [bool]$VsDevCmdFound = $false,
        [bool]$LinkerFound = $false,
        [bool]$MetadataValid = $false,
        [string]$InstallPath = '',
        [string]$VsDevCmdPath = '',
        [string]$LinkerPath = '',
        [string]$LinkerVersion = '',
        [string]$Detail = ''
    )

    return [pscustomobject]@{
        Valid = $WorkloadFound -and $VsDevCmdFound -and $LinkerFound -and $MetadataValid
        WorkloadFound = $WorkloadFound
        VsDevCmdFound = $VsDevCmdFound
        LinkerFound = $LinkerFound
        MetadataValid = $MetadataValid
        InstallPath = $InstallPath
        VsDevCmdPath = $VsDevCmdPath
        LinkerPath = $LinkerPath
        LinkerVersion = $LinkerVersion
        Detail = $Detail
    }
}

function Resolve-MsvcBuildTools {
    [CmdletBinding()]
    param(
        [string]$VsWherePath = (Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'),
        [scriptblock]$VsWhereRunner,
        [scriptblock]$VersionInfoReader
    )

    if (-not (Test-Path -LiteralPath $VsWherePath -PathType Leaf)) {
        return New-MsvcBuildToolsProbeResult -Detail 'vswhere.exe was not found'
    }
    if (-not $VsWhereRunner) {
        $VsWhereRunner = {
            param([string]$Path)
            $output = & $Path -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
            [pscustomobject]@{ ExitCode = $LASTEXITCODE; InstallationPath = [string](@($output)[0]) }
        }
    }
    if (-not $VersionInfoReader) {
        $VersionInfoReader = {
            param([string]$Path)
            (Get-Item -LiteralPath $Path -ErrorAction Stop).VersionInfo
        }
    }

    try {
        $discovery = & $VsWhereRunner $VsWherePath
    } catch {
        return New-MsvcBuildToolsProbeResult -Detail "vswhere VC workload query failed: $($_.Exception.Message)"
    }
    if ($null -eq $discovery -or [int]$discovery.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace([string]$discovery.InstallationPath)) {
        return New-MsvcBuildToolsProbeResult -Detail 'Visual Studio C++ x86/x64 workload was not found'
    }

    $installPath = [System.IO.Path]::GetFullPath([string]$discovery.InstallationPath).TrimEnd('\')
    if (-not (Test-Path -LiteralPath $installPath -PathType Container)) {
        return New-MsvcBuildToolsProbeResult -Detail 'vswhere returned a missing Visual Studio installation path'
    }
    $vsDevCmdPath = Join-Path $installPath 'Common7\Tools\VsDevCmd.bat'
    $vsDevCmdFound = Test-Path -LiteralPath $vsDevCmdPath -PathType Leaf
    if (-not $vsDevCmdFound) {
        return New-MsvcBuildToolsProbeResult -WorkloadFound $true -InstallPath $installPath -Detail 'Visual Studio C++ workload has no VsDevCmd.bat'
    }

    $toolsRoot = Join-Path $installPath 'VC\Tools\MSVC'
    $linker = Get-ChildItem -LiteralPath $toolsRoot -Recurse -File -Filter 'link.exe' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\bin\\Hostx64\\x64\\link\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $linker) {
        return New-MsvcBuildToolsProbeResult -WorkloadFound $true -VsDevCmdFound $true -InstallPath $installPath -VsDevCmdPath $vsDevCmdPath -Detail 'Visual Studio C++ workload has no Hostx64/x64 link.exe'
    }

    $linkerPath = [System.IO.Path]::GetFullPath($linker.FullName)
    $relativeLinker = [System.IO.Path]::GetRelativePath($installPath, $linkerPath)
    if ([System.IO.Path]::IsPathRooted($relativeLinker) -or $relativeLinker -eq '..' -or $relativeLinker.StartsWith("..\", [System.StringComparison]::Ordinal)) {
        return New-MsvcBuildToolsProbeResult -WorkloadFound $true -VsDevCmdFound $true -InstallPath $installPath -VsDevCmdPath $vsDevCmdPath -Detail 'Resolved linker escaped the Visual Studio installation root'
    }

    try {
        $versionInfo = & $VersionInfoReader $linkerPath
    } catch {
        return New-MsvcBuildToolsProbeResult -WorkloadFound $true -VsDevCmdFound $true -LinkerFound $true -InstallPath $installPath -VsDevCmdPath $vsDevCmdPath -LinkerPath $linkerPath -Detail "Unable to read linker version metadata: $($_.Exception.Message)"
    }
    $companyName = [string]$versionInfo.CompanyName
    $productName = [string]$versionInfo.ProductName
    $fileDescription = [string]$versionInfo.FileDescription
    $fileVersion = [string]$versionInfo.FileVersion
    $metadataValid = (
        $companyName -match '^Microsoft Corporation$' -and
        $productName -match 'Microsoft.*Visual Studio' -and
        $fileDescription -match 'Microsoft.*Incremental Linker' -and
        -not [string]::IsNullOrWhiteSpace($fileVersion)
    )
    $detail = if ($metadataValid) {
        "Microsoft x64 linker $fileVersion verified"
    } else {
        'link.exe version metadata does not identify the Microsoft Visual Studio incremental linker'
    }
    return New-MsvcBuildToolsProbeResult `
        -WorkloadFound $true `
        -VsDevCmdFound $true `
        -LinkerFound $true `
        -MetadataValid $metadataValid `
        -InstallPath $installPath `
        -VsDevCmdPath $vsDevCmdPath `
        -LinkerPath $linkerPath `
        -LinkerVersion $fileVersion `
        -Detail $detail
}
