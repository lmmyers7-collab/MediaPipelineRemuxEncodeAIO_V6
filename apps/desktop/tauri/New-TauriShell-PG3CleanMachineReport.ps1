[CmdletBinding()]
param(
    [string]$OutputPath,
    [switch]$PrereqPassed,
    [switch]$LaunchPassed,
    [string]$PrereqTranscriptPath = '',
    [string]$LaunchTranscriptPath = '',
    [string]$Operator = '',
    [string]$Notes = '',
    [switch]$OperatorConfirmedNoDeveloperTools,
    [switch]$StrictCleanMachine
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function ConvertTo-MarkdownCell {
    param($Value)
    $text = if ($null -eq $Value) { '' } else { [string]$Value }
    return $text.Replace('|', '\|').Replace("`r", ' ').Replace("`n", ' ')
}

function Format-YesNo {
    param([bool]$Value)
    if ($Value) { return 'yes' }
    return 'no'
}

function Get-PathState {
    param([Parameter(Mandatory)][string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) { return 'present-file' }
    if (Test-Path -LiteralPath $Path -PathType Container) { return 'present-folder' }
    return 'absent'
}

function Test-IsUnderPath {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Root
    )
    try {
        $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
        $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
        return $fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            $fullPath.StartsWith($fullRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        return $false
    }
}

function Find-ExternalCommand {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$BundleRoot
    )

    $matches = @(
        Get-Command $Name -All -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Source -and
                $_.Source -notmatch '\\WindowsApps\\' -and
                -not (Test-IsUnderPath -Path $_.Source -Root $BundleRoot)
            } |
            Select-Object -ExpandProperty Source -Unique
    )
    return @($matches)
}

function Find-VisualStudioBuildTools {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
        return @()
    }
    $installations = @(
        & $vswhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null |
            Where-Object { $_ }
    )
    return @($installations)
}

function Read-ManifestValue {
    param(
        [object]$Manifest,
        [string]$Path,
        $Default = ''
    )
    $current = $Manifest
    foreach ($part in $Path.Split('.')) {
        if ($null -eq $current) { return $Default }
        $property = $current.PSObject.Properties[$part]
        if (-not $property) { return $Default }
        $current = $property.Value
    }
    if ($null -eq $current) { return $Default }
    return $current
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$shellRoot = [System.IO.Path]::GetFullPath($scriptRoot)
$desktopRoot = [System.IO.Path]::GetFullPath((Join-Path $shellRoot '..'))
$bundleRoot = [System.IO.Path]::GetFullPath((Join-Path $desktopRoot '..'))

if (-not $OutputPath) {
    $reportRoot = Join-Path $bundleRoot 'docs\PG3CleanMachineReports'
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $OutputPath = Join-Path $reportRoot "pg3_clean_machine_report_$stamp.md"
}
$outputFull = [System.IO.Path]::GetFullPath($OutputPath)
$outputParent = Split-Path -Parent $outputFull
if ($outputParent -and -not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
}

$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
$computer = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
$manifestPath = Join-Path $bundleRoot 'release_manifest.json'
$manifest = $null
$manifestError = ''
if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        $manifestError = $_.Exception.Message
    }
} else {
    $manifestError = 'release_manifest.json not found'
}

$bundleChecks = @(
    [pscustomobject]@{ Item = 'Release manifest'; Path = $manifestPath; State = Get-PathState -Path $manifestPath; Expected = 'present-file' },
    [pscustomobject]@{ Item = 'Packaged Tauri executable'; Path = (Join-Path $shellRoot 'mediapipeline-tauri-shell.exe'); State = Get-PathState -Path (Join-Path $shellRoot 'mediapipeline-tauri-shell.exe'); Expected = 'present-file' },
    [pscustomobject]@{ Item = 'Bundled Python'; Path = (Join-Path $desktopRoot 'Runtime\Python\python.exe'); State = Get-PathState -Path (Join-Path $desktopRoot 'Runtime\Python\python.exe'); Expected = 'present-file' },
    [pscustomobject]@{ Item = 'Bundled PowerShell'; Path = (Join-Path $bundleRoot 'ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe'); State = Get-PathState -Path (Join-Path $bundleRoot 'ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe'); Expected = 'present-file' },
    [pscustomobject]@{ Item = 'Bundled ffmpeg'; Path = (Join-Path $bundleRoot 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'); State = Get-PathState -Path (Join-Path $bundleRoot 'ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe'); Expected = 'present-file' },
    [pscustomobject]@{ Item = 'Bundled ffprobe'; Path = (Join-Path $bundleRoot 'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe'); State = Get-PathState -Path (Join-Path $bundleRoot 'ops\pipeline\tools\ffmpeg\bin\ffprobe.exe'); Expected = 'present-file' },
    [pscustomobject]@{ Item = 'Bundled mkvmerge'; Path = (Join-Path $bundleRoot 'ops\pipeline\tools\MKVToolNix\mkvmerge.exe'); State = Get-PathState -Path (Join-Path $bundleRoot 'ops\pipeline\tools\MKVToolNix\mkvmerge.exe'); Expected = 'present-file' },
    [pscustomobject]@{ Item = 'Tauri node_modules'; Path = (Join-Path $shellRoot 'node_modules'); State = Get-PathState -Path (Join-Path $shellRoot 'node_modules'); Expected = 'absent' },
    [pscustomobject]@{ Item = 'Tauri generated target tree'; Path = (Join-Path $shellRoot 'src-tauri\target'); State = Get-PathState -Path (Join-Path $shellRoot 'src-tauri\target'); Expected = 'absent' },
    [pscustomobject]@{ Item = 'Desktop Python tests'; Path = (Join-Path $desktopRoot 'tests'); State = Get-PathState -Path (Join-Path $desktopRoot 'tests'); Expected = 'absent' },
    [pscustomobject]@{ Item = 'Pipeline tests'; Path = (Join-Path $bundleRoot 'ops\pipeline\tests'); State = Get-PathState -Path (Join-Path $bundleRoot 'ops\pipeline\tests'); Expected = 'absent' },
    [pscustomobject]@{ Item = 'Git metadata'; Path = (Join-Path $bundleRoot '.git'); State = Get-PathState -Path (Join-Path $bundleRoot '.git'); Expected = 'absent' },
    [pscustomobject]@{ Item = 'Claude workspace metadata'; Path = (Join-Path $bundleRoot '.claude'); State = Get-PathState -Path (Join-Path $bundleRoot '.claude'); Expected = 'absent' }
)

$developerCommandNames = @('node', 'npm', 'cargo', 'rustc', 'rustup', 'poetry', 'git', 'code', 'devenv', 'msbuild', 'cl', 'link', 'claude')
$developerToolRows = foreach ($name in $developerCommandNames) {
    $paths = @(Find-ExternalCommand -Name $name -BundleRoot $bundleRoot)
    [pscustomobject]@{
        Tool = $name
        Found = $paths.Count -gt 0
        Path = if ($paths.Count -gt 0) { ($paths -join '; ') } else { '' }
    }
}
$visualStudioInstallations = @(Find-VisualStudioBuildTools)
$developerToolRows += [pscustomobject]@{
    Tool = 'Visual Studio C++ Build Tools'
    Found = $visualStudioInstallations.Count -gt 0
    Path = if ($visualStudioInstallations.Count -gt 0) { ($visualStudioInstallations -join '; ') } else { '' }
}

$bundleMismatchCount = @($bundleChecks | Where-Object { $_.State -ne $_.Expected }).Count
$developerToolCount = @($developerToolRows | Where-Object { $_.Found }).Count
$prereqTranscriptState = if ($PrereqTranscriptPath) { Get-PathState -Path $PrereqTranscriptPath } else { 'not-provided' }
$launchTranscriptState = if ($LaunchTranscriptPath) { Get-PathState -Path $LaunchTranscriptPath } else { 'not-provided' }

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('# PG-3 Clean-Machine Validation Report')
$lines.Add('')
$lines.Add('Generated by `New-TauriShell-PG3CleanMachineReport.ps1`.')
$lines.Add('')
$lines.Add('## Verdict')
$lines.Add('')
$lines.Add('| Check | Value |')
$lines.Add('|---|---|')
$lines.Add("| Prereq command passed | $(ConvertTo-MarkdownCell (Format-YesNo ([bool]$PrereqPassed))) |")
$lines.Add("| Package-mode launch command passed | $(ConvertTo-MarkdownCell (Format-YesNo ([bool]$LaunchPassed))) |")
$lines.Add("| Operator confirmed no developer tools | $(ConvertTo-MarkdownCell (Format-YesNo ([bool]$OperatorConfirmedNoDeveloperTools))) |")
$lines.Add("| Developer tools detected outside bundle | $(ConvertTo-MarkdownCell $developerToolCount) |")
$lines.Add("| Bundle layout mismatches | $(ConvertTo-MarkdownCell $bundleMismatchCount) |")
$lines.Add("| PG-3 can be marked proven from this report alone | no |")
$lines.Add('')
$lines.Add('PG-3 can be marked proven only when this report was generated on a separate clean Windows machine and the prereq plus package-mode launch commands passed there.')
$lines.Add('')
$lines.Add('## Machine')
$lines.Add('')
$lines.Add('| Field | Value |')
$lines.Add('|---|---|')
$lines.Add("| Generated at | $(ConvertTo-MarkdownCell ((Get-Date).ToString('o'))) |")
$lines.Add("| Operator | $(ConvertTo-MarkdownCell $Operator) |")
$lines.Add("| Computer name | $(ConvertTo-MarkdownCell $env:COMPUTERNAME) |")
$lines.Add("| User | $(ConvertTo-MarkdownCell ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)) |")
$lines.Add("| Manufacturer | $(ConvertTo-MarkdownCell $(if ($computer) { $computer.Manufacturer } else { '' })) |")
$lines.Add("| Model | $(ConvertTo-MarkdownCell $(if ($computer) { $computer.Model } else { '' })) |")
$lines.Add("| OS caption | $(ConvertTo-MarkdownCell $(if ($os) { $os.Caption } else { '' })) |")
$lines.Add("| OS version | $(ConvertTo-MarkdownCell $(if ($os) { $os.Version } else { '' })) |")
$lines.Add("| OS build | $(ConvertTo-MarkdownCell $(if ($os) { $os.BuildNumber } else { '' })) |")
$lines.Add('')
$lines.Add('## Bundle')
$lines.Add('')
$lines.Add('| Field | Value |')
$lines.Add('|---|---|')
$lines.Add("| Bundle root | $(ConvertTo-MarkdownCell $bundleRoot) |")
$lines.Add("| Shell root | $(ConvertTo-MarkdownCell $shellRoot) |")
$lines.Add("| Release manifest | $(ConvertTo-MarkdownCell $manifestPath) |")
$lines.Add("| Manifest error | $(ConvertTo-MarkdownCell $manifestError) |")
$lines.Add("| Manifest schema | $(ConvertTo-MarkdownCell $(Read-ManifestValue -Manifest $manifest -Path 'schema_version')) |")
$lines.Add("| Tauri preview binary included | $(ConvertTo-MarkdownCell $(Read-ManifestValue -Manifest $manifest -Path 'summary.tauri_preview_binary_included')) |")
$lines.Add("| Tests included | $(ConvertTo-MarkdownCell $(Read-ManifestValue -Manifest $manifest -Path 'summary.tests_included')) |")
$lines.Add("| Personal config included | $(ConvertTo-MarkdownCell $(Read-ManifestValue -Manifest $manifest -Path 'summary.personal_config_included')) |")
$lines.Add('')
$lines.Add('## Bundle Layout Checks')
$lines.Add('')
$lines.Add('| Item | Expected | State | Path |')
$lines.Add('|---|---|---|---|')
foreach ($row in $bundleChecks) {
    $lines.Add("| $(ConvertTo-MarkdownCell $row.Item) | $(ConvertTo-MarkdownCell $row.Expected) | $(ConvertTo-MarkdownCell $row.State) | $(ConvertTo-MarkdownCell $row.Path) |")
}
$lines.Add('')
$lines.Add('## Developer Tool Scan')
$lines.Add('')
$lines.Add('The scan ignores tools inside the copied bundle and WindowsApps aliases. Any found row should be explained before PG-3 is accepted.')
$lines.Add('')
$lines.Add('| Tool | Found outside bundle | Path |')
$lines.Add('|---|---|---|')
foreach ($row in $developerToolRows) {
    $lines.Add("| $(ConvertTo-MarkdownCell $row.Tool) | $(ConvertTo-MarkdownCell (Format-YesNo ([bool]$row.Found))) | $(ConvertTo-MarkdownCell $row.Path) |")
}
$lines.Add('')
$lines.Add('## Command Evidence')
$lines.Add('')
$lines.Add('| Command | Passed | Transcript | Transcript state |')
$lines.Add('|---|---|---|---|')
$lines.Add("| `Test-TauriShell-Prereqs.ps1 -CheckOnly` | $(ConvertTo-MarkdownCell (Format-YesNo ([bool]$PrereqPassed))) | $(ConvertTo-MarkdownCell $PrereqTranscriptPath) | $(ConvertTo-MarkdownCell $prereqTranscriptState) |")
$lines.Add("| `Test-TauriShell-Launch.ps1 -Mode Packaged` | $(ConvertTo-MarkdownCell (Format-YesNo ([bool]$LaunchPassed))) | $(ConvertTo-MarkdownCell $LaunchTranscriptPath) | $(ConvertTo-MarkdownCell $launchTranscriptState) |")
$lines.Add('')
$lines.Add('## Operator Notes')
$lines.Add('')
if ($Notes) {
    $lines.Add($Notes)
} else {
    $lines.Add('_No notes provided._')
}
$lines.Add('')
$lines.Add('## Required Follow-Up')
$lines.Add('')
$lines.Add('- Attach or preserve the prereq and package-mode launch transcripts when possible.')
$lines.Add('- Do not use this report to prove FFmpeg routing, subtitle/audio handling, Pending Publish behavior, PG-1 active-close behavior, or PG-2 real-media acceptance.')
$lines.Add('- Do not mark PG-3 proven if this report was generated on the development workstation.')

$lines | Set-Content -LiteralPath $outputFull -Encoding UTF8

Write-Host "PG-3 clean-machine report written: $outputFull"
Write-Host "Developer tools detected outside bundle: $developerToolCount"
Write-Host "Bundle layout mismatches: $bundleMismatchCount"

if ($StrictCleanMachine) {
    if (-not $PrereqPassed -or -not $LaunchPassed -or -not $OperatorConfirmedNoDeveloperTools -or $developerToolCount -gt 0 -or $bundleMismatchCount -gt 0) {
        Write-Host 'Strict clean-machine report check failed.' -ForegroundColor Yellow
        exit 1
    }
}

exit 0
