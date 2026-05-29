<#
.SYNOPSIS
Rapid-deployment setup and validation wizard for the patched MediaPipeline bundle.

.DESCRIPTION
Creates or updates MediaPipeline_config_chatgpt.psd1 next to the patched
pipeline files, validates the deployment surface, and keeps advanced keys from
an existing config intact.

Designed for first-time setup on a new PC and for later re-validation after a
machine move, dependency change, or manual config edit.

.PARAMETER ValidateOnly
Loads the current config and runs validation without changing it.

.PARAMETER DryRun
Builds the config content and shows a preview without writing it to disk.

.PARAMETER AcceptDefaults
Runs non-interactively for any prompt that already has a default value. Useful
for rapid deployment when folder paths are preseeded on the command line.

.PARAMETER ConfigPath
Optional explicit path to the config file to read or write.

.PARAMETER SourceMovies
Optional preset for the movie source folder.

.PARAMETER SourceTV
Optional preset for the TV source folder.

.PARAMETER Outsource
Optional preset for the final output folder.

.PARAMETER LocalBase
Optional preset for the local scratch folder.

.PARAMETER OpenConfig
Opens the written config in the default editor after a successful write.

.PARAMETER ReportPath
Optional path for a text validation report. When omitted, no report file is written.

.PARAMETER ListDefaults
Prints the current default config template and exits.

.EXAMPLE
.\Setup-MediaPipeline_chatgpt.ps1

Runs the interactive setup wizard.

.EXAMPLE
.\Setup-MediaPipeline_chatgpt.ps1 -ValidateOnly

Validates the existing config and environment only.

.EXAMPLE
.\Setup-MediaPipeline_chatgpt.ps1 `
    -SourceMovies 'D:\Incoming\Movies' `
    -SourceTV 'D:\Incoming\TV' `
    -Outsource '\\NAS\Plex\Library' `
    -LocalBase 'E:\MediaScratch' `
    -AcceptDefaults

Runs a fast first-pass deployment using the recommended defaults for everything
except the key folder paths.
#>
[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$DryRun,
    [switch]$AcceptDefaults,
    [switch]$OpenConfig,
    [switch]$ListDefaults,
    [string]$ReportPath,
    [string]$ConfigPath,
    [string]$SourceMovies,
    [string]$SourceTV,
    [string]$Outsource,
    [string]$LocalBase
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Normalize-UserPath {
    param(
        [Parameter(Mandatory = $false)]
        [string]$Path,
        [string]$BasePath = (Get-Location).Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return $Path }

    $trimmed = $Path.Trim().Trim('"').Trim("'")
    $expanded = [Environment]::ExpandEnvironmentVariables($trimmed)

    if ($expanded.StartsWith('\\')) {
        return $expanded.TrimEnd('\','/')
    }

    try {
        return [System.IO.Path]::GetFullPath($expanded, $BasePath).TrimEnd('\','/')
    } catch {
        try {
            return [System.IO.Path]::GetFullPath($expanded).TrimEnd('\','/')
        } catch {
            return $expanded.TrimEnd('\','/')
        }
    }
}

$script:InvariantCulture = [System.Globalization.CultureInfo]::InvariantCulture
$script:ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$script:ConfigPath = if ($ConfigPath) {
    Normalize-UserPath -Path $ConfigPath -BasePath $script:ScriptDir
} else {
    Join-Path $script:ScriptDir 'MediaPipeline_config_chatgpt.psd1'
}
$script:PipelinePath = Join-Path $script:ScriptDir 'MediaPipeline_chatgpt.ps1'
$script:SubtitlePath = Join-Path $script:ScriptDir 'ass_to_srt_chatgpt.py'
$script:UseAcceptDefaults = [bool]$AcceptDefaults

$configSchemaModule = Join-Path (Split-Path -Parent $script:ScriptDir) 'engine\config\config_schema.ps1'
if (-not (Test-Path -LiteralPath $configSchemaModule)) {
    throw "Required config schema module not found: $configSchemaModule"
}
. $configSchemaModule

$script:RequiredKeys = @(Get-MediaPipelineConfigRequiredKeys)
$script:ConfigOrder = @(Get-MediaPipelineConfigOrderedKeys)

function Write-Header {
    param([string]$Text)
    $bar = '=' * 68
    Write-Host ''
    Write-Host $bar -ForegroundColor Cyan
    Write-Host " $Text" -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor Cyan
}

function Write-Ok   { param([string]$Message) Write-Host "[ OK ] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fail { param([string]$Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }
function Write-Info { param([string]$Message) Write-Host "       $Message" }
function Write-Step {
    param([int]$Number, [int]$Total, [string]$Name)
    Write-Host ("[{0}/{1}] {2}" -f $Number, $Total, $Name) -ForegroundColor Cyan
}

function Read-WithDefault {
    param([string]$Prompt, [string]$Default = '')
    $hasDefault = -not [string]::IsNullOrWhiteSpace($Default)
    if ($script:UseAcceptDefaults -and $hasDefault) {
        Write-Host "$Prompt [$Default]" -ForegroundColor DarkGray
        return $Default
    }

    if ($hasDefault) {
        $answer = Read-Host "$Prompt [$Default]"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        return $answer.Trim()
    }

    while ($true) {
        $answer = Read-Host $Prompt
        if (-not [string]::IsNullOrWhiteSpace($answer)) {
            return $answer.Trim()
        }
    }
}

function Read-YesNo {
    param([string]$Prompt, [bool]$DefaultYes = $true)
    if ($script:UseAcceptDefaults) {
        $suffix = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
        Write-Host "$Prompt $suffix" -ForegroundColor DarkGray
        return $DefaultYes
    }

    $suffix = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $answer = (Read-Host "$Prompt $suffix").Trim().ToLowerInvariant()
        if ($answer -eq '') { return $DefaultYes }
        if ($answer -in @('y','yes')) { return $true }
        if ($answer -in @('n','no'))  { return $false }
        Write-Warn "Please answer y or n."
    }
}

function Read-Choice {
    param(
        [string]$Prompt,
        [string[]]$Options,
        [int]$Default = 1
    )
    if ($Default -lt 1 -or $Default -gt $Options.Count) { $Default = 1 }

    if ($script:UseAcceptDefaults) {
        Write-Host "$Prompt [$Default]" -ForegroundColor DarkGray
        return $Default
    }

    while ($true) {
        $answer = (Read-Host "$Prompt [$Default]").Trim()
        if ($answer -eq '') { return $Default }
        if ($answer -match '^\d+$') {
            $n = [int]$answer
            if ($n -ge 1 -and $n -le $Options.Count) {
                return $n
            }
        }
        Write-Warn "Please enter a number from 1 to $($Options.Count)."
    }
}

function Read-PositiveNumber {
    param([string]$Prompt, [string]$Default)
    while ($true) {
        $raw = Read-WithDefault $Prompt $Default
        $parsed = 0.0
        if ([double]::TryParse(
                $raw,
                [System.Globalization.NumberStyles]::Float,
                $script:InvariantCulture,
                [ref]$parsed) -and $parsed -gt 0) {
            return $parsed
        }
        Write-Warn "Enter a positive number using '.' as the decimal separator."
    }
}

function Test-IsRealPython {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $false }
    if ($Path -match '\\WindowsApps\\') { return $false }
    try {
        $out = & $Path -c "import sys; print(sys.version_info[0])" 2>&1
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -match '^\d+$')
    } catch {
        return $false
    }
}

function Get-BundleSearchRoots {
    $roots = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
            $script:ScriptDir,
            $PSScriptRoot
        )) {
        if (-not $candidate) { continue }
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        if (-not $roots.Contains($resolved)) {
            [void]$roots.Add($resolved)
        }
    }
    return @($roots)
}

function Resolve-BundledPath {
    param([string[]]$RelativeCandidates)
    foreach ($root in Get-BundleSearchRoots) {
        foreach ($relative in $RelativeCandidates) {
            $candidate = Join-Path $root $relative
            if (Test-Path -LiteralPath $candidate) {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
    }
    return $null
}

function Resolve-ToolPath {
    param(
        [Parameter(Mandatory = $true)][string]$ToolName,
        [string[]]$RelativeCandidates = @()
    )

    $bundled = Resolve-BundledPath -RelativeCandidates $RelativeCandidates
    if ($bundled) { return $bundled }

    $cmd = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    return $null
}

function Resolve-PythonPath {
    $bundledCandidates = @(
        'Runtime\Python\python.exe',
        'Tools\Python\python.exe',
        '..\DesktopApp\Runtime\Python\python.exe'
    )
    foreach ($candidate in $bundledCandidates) {
        $resolved = Resolve-BundledPath -RelativeCandidates @($candidate)
        if ($resolved -and (Test-IsRealPython $resolved)) {
            return $resolved
        }
    }
    foreach ($candidate in @('python3','python')) {
        foreach ($cmd in @(Get-Command $candidate -All -ErrorAction SilentlyContinue)) {
            if ($cmd -and (Test-IsRealPython $cmd.Source)) {
                return $cmd.Source
            }
        }
    }
    return $null
}

function Test-Pysubs2Import {
    param([string]$PythonPath)
    if (-not $PythonPath) { return $false }
    try {
        $null = & $PythonPath -c "import pysubs2" 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PwshPath {
    if ($PSVersionTable.PSVersion.Major -ge 7) {
        return (Get-Process -Id $PID).Path
    }

    $candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
            (Join-Path $script:ScriptDir 'pwsh.exe'),
            (Join-Path $script:ScriptDir 'PowerShell-7.6.0-win-x64\pwsh.exe')
        )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            [void]$candidates.Add($candidate)
        }
    }

    Get-ChildItem -LiteralPath $script:ScriptDir -Directory -Filter 'PowerShell-*' -ErrorAction SilentlyContinue |
        ForEach-Object {
            $candidate = Join-Path $_.FullName 'pwsh.exe'
            if (Test-Path -LiteralPath $candidate) {
                [void]$candidates.Add($candidate)
            }
        }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        [void]$candidates.Add($cmd.Source)
    }

    return ($candidates | Select-Object -Unique | Select-Object -First 1)
}

function Test-PathWritable {
    param([string]$Path)
    $probe = Join-Path $Path ".__mp_write_test_$([guid]::NewGuid().ToString('N')).tmp"
    try {
        Set-Content -LiteralPath $probe -Value 'probe' -Encoding UTF8 -ErrorAction Stop
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        return $true
    } catch {
        return $false
    }
}

function ConvertTo-PowerShellLiteralString {
    param([AllowNull()][string]$Value)

    if ($null -eq $Value) { return '$null' }
    return "'" + ([string]$Value -replace "'", "''") + "'"
}

function Resolve-CurrentPowerShellPath {
    try {
        $currentProcess = Get-Process -Id $PID -ErrorAction Stop
        if ($currentProcess.Path) { return $currentProcess.Path }
    } catch { }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    return $null
}

function Invoke-SetupValidationProbe {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [int]$TimeoutSeconds = 12
    )

    $pwshPath = Resolve-CurrentPowerShellPath
    if (-not $pwshPath) {
        return [pscustomobject]@{
            ExitCode = $null
            TimedOut = $false
            Output = @()
            StartError = 'PowerShell host could not be resolved for validation probe.'
        }
    }

    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Command))
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $pwshPath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded)) {
        [void]$startInfo.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $timedOut = $false
    $stdout = ''
    $stderr = ''

    try {
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $waitMilliseconds = [Math]::Max(1, $TimeoutSeconds) * 1000
        $exited = $process.WaitForExit($waitMilliseconds)
        if (-not $exited) {
            $timedOut = $true
            try {
                $process.Kill($true)
            } catch {
                try { $process.Kill() } catch { }
            }
            try { [void]$process.WaitForExit(5000) } catch { }
        } else {
            $process.WaitForExit()
        }

        try { $stdout = $stdoutTask.GetAwaiter().GetResult() } catch { $stdout = "[setup-validation stdout read failed] $($_.Exception.Message)" }
        try { $stderr = $stderrTask.GetAwaiter().GetResult() } catch { $stderr = "[setup-validation stderr read failed] $($_.Exception.Message)" }

        $output = @()
        foreach ($text in @($stdout, $stderr)) {
            if (-not [string]::IsNullOrEmpty($text)) {
                $output += @($text -split "\r?\n" | Where-Object { $_ -ne '' })
            }
        }

        $exitCode = $null
        if (-not $timedOut -and $process.HasExited) {
            $exitCode = $process.ExitCode
        }

        return [pscustomobject]@{
            ExitCode = $exitCode
            TimedOut = $timedOut
            Output = $output
            StartError = $null
        }
    } catch {
        return [pscustomobject]@{
            ExitCode = $null
            TimedOut = $false
            Output = @()
            StartError = $_.Exception.Message
        }
    } finally {
        if ($process) { $process.Dispose() }
    }
}

function Test-ValidationPathExists {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$TimeoutSeconds = 12
    )

    $pathLiteral = ConvertTo-PowerShellLiteralString -Value $Path
    $command = @"
`$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $pathLiteral) { exit 0 }
exit 2
"@
    $result = Invoke-SetupValidationProbe -Command $command -TimeoutSeconds $TimeoutSeconds
    return [pscustomobject]@{
        Exists = ($result.ExitCode -eq 0)
        TimedOut = $result.TimedOut
        StartError = $result.StartError
        Output = $result.Output
    }
}

function Test-ValidationPathWritable {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$TimeoutSeconds = 12
    )

    $pathLiteral = ConvertTo-PowerShellLiteralString -Value $Path
    $command = @"
`$ErrorActionPreference = 'Stop'
`$path = $pathLiteral
if (-not (Test-Path -LiteralPath `$path -PathType Container)) { exit 2 }
`$probe = Join-Path `$path ('.__mp_write_test_' + [guid]::NewGuid().ToString('N') + '.tmp')
try {
    Set-Content -LiteralPath `$probe -Value 'probe' -Encoding UTF8 -ErrorAction Stop
    Remove-Item -LiteralPath `$probe -Force -ErrorAction SilentlyContinue
    exit 0
} catch {
    Write-Output `$_.Exception.Message
    if (Test-Path -LiteralPath `$probe) {
        Remove-Item -LiteralPath `$probe -Force -ErrorAction SilentlyContinue
    }
    exit 1
}
"@
    $result = Invoke-SetupValidationProbe -Command $command -TimeoutSeconds $TimeoutSeconds
    return [pscustomobject]@{
        Writable = ($result.ExitCode -eq 0)
        Missing = ($result.ExitCode -eq 2)
        TimedOut = $result.TimedOut
        StartError = $result.StartError
        Output = $result.Output
    }
}

function Read-Path {
    param(
        [string]$Prompt,
        [string]$Default,
        [switch]$CreateIfMissing,
        [switch]$MustBeWritable,
        [bool]$CreateDefaultYes = $true
    )

    while ($true) {
        $rawPath = Read-WithDefault $Prompt $Default
        $path = Normalize-UserPath -Path $rawPath -BasePath $script:ScriptDir
        if ([string]::IsNullOrWhiteSpace($path)) {
            Write-Warn "Path cannot be empty."
            continue
        }

        $exists = Test-Path -LiteralPath $path -ErrorAction SilentlyContinue
        if (-not $exists -and $CreateIfMissing) {
            if (Read-YesNo "Create missing folder '$path' now?" -DefaultYes $CreateDefaultYes) {
                try {
                    New-Item -ItemType Directory -Path $path -Force | Out-Null
                    Write-Ok "Created $path"
                    $exists = $true
                } catch {
                    Write-Fail "Could not create $path : $_"
                    continue
                }
            } else {
                Write-Warn "Folder must exist before deployment can use it."
                continue
            }
        }

        if (-not $exists) {
            Write-Warn "Path does not exist yet: $path"
            if ($script:UseAcceptDefaults) {
                return $path
            }
            if (-not (Read-YesNo "Keep this path anyway?" -DefaultYes $false)) {
                continue
            }
        }

        if ($MustBeWritable -and $exists -and -not (Test-PathWritable $path)) {
            Write-Fail "Path is not writable: $path"
            continue
        }

        if ($path -ne $rawPath.Trim().Trim('"').Trim("'")) {
            Write-Info "Normalized path: $path"
        }

        return $path
    }
}

function Test-PathsDisjoint {
    param([hashtable]$Paths)
    $normalized = @{}
    foreach ($key in $Paths.Keys) {
        $raw = $Paths[$key]
        if ([string]::IsNullOrWhiteSpace($raw)) { continue }
        try {
            $full = [System.IO.Path]::GetFullPath($raw).TrimEnd('\','/').ToLowerInvariant()
        } catch {
            $full = $raw.TrimEnd('\','/').ToLowerInvariant()
        }
        $normalized[$key] = $full
    }

    $keys = @($normalized.Keys)
    for ($i = 0; $i -lt $keys.Count; $i++) {
        for ($j = $i + 1; $j -lt $keys.Count; $j++) {
            $a = $keys[$i]
            $b = $keys[$j]
            if ($normalized[$a] -eq $normalized[$b]) {
                throw "$a and $b resolve to the same path."
            }
            $ap = $normalized[$a] + [IO.Path]::DirectorySeparatorChar
            $bp = $normalized[$b] + [IO.Path]::DirectorySeparatorChar
            if ($ap.StartsWith($bp) -or $bp.StartsWith($ap)) {
                throw "$a and $b are nested. Keep source, scratch, and outsource folders separate."
            }
        }
    }
}

function Get-DetectedGpu {
    $result = @{ Vendor = 'None'; Name = 'Unknown' }

    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($nvidiaSmi) {
        try {
            $out = & $nvidiaSmi.Source --query-gpu=name --format=csv,noheader 2>&1 | Select-Object -First 1
            if ($LASTEXITCODE -eq 0 -and $out) {
                return @{ Vendor = 'NVIDIA'; Name = "$out".Trim() }
            }
        } catch { }
    }

    try {
        $gpus = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue)
        foreach ($gpu in $gpus) {
            if (-not $gpu.Name) { continue }
            if ($gpu.Name -match 'NVIDIA|GeForce|\bRTX\b|\bGTX\b|Quadro') {
                return @{ Vendor = 'NVIDIA'; Name = $gpu.Name }
            }
            if ($gpu.Name -match 'AMD|Radeon|\bRX\s*\d') {
                return @{ Vendor = 'AMD'; Name = $gpu.Name }
            }
            if ($gpu.Name -match 'Intel|\bArc\b|Iris|\bUHD\b|\bHD Graphics\b') {
                return @{ Vendor = 'Intel'; Name = $gpu.Name }
            }
        }
        if ($gpus.Count -gt 0 -and $gpus[0].Name) {
            $result.Name = $gpus[0].Name
        }
    } catch { }

    return $result
}

function Get-ExtraVideoFlagsForCodec {
    param([string]$Codec)
    Get-MediaPipelineConfigExtraVideoFlagsDefault -Codec $Codec
}

function Get-DefaultConfig {
    Get-MediaPipelineConfigDefaultValues
}

function Read-ExistingConfig {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return @{ Result = @{}; ParseFailed = $false } }
    try {
        $config = Import-PowerShellDataFile -LiteralPath $Path
        if ($null -eq $config) { $config = @{} }
        return @{ Result = $config; ParseFailed = $false }
    } catch {
        Write-Warn "Existing config could not be parsed: $_"
        return @{ Result = @{}; ParseFailed = $true }
    }
}

function Invoke-ConfigBackup {
    param([string]$Path, [int]$Keep = 5)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupPath = "$Path.bak.$timestamp"
    Copy-Item -LiteralPath $Path -Destination $backupPath -Force

    $parent = Split-Path -Parent $Path
    $pattern = (Split-Path -Leaf $Path) + '.bak.*'
    $backups = @(Get-ChildItem -LiteralPath $parent -Filter $pattern -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending)
    if ($backups.Count -gt $Keep) {
        $backups | Select-Object -Skip $Keep | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }

    return $backupPath
}

function Format-PsdKey {
    param([string]$Key)
    if ($Key -match '^[A-Za-z_][A-Za-z0-9_]*$') { return $Key }
    return "'" + ($Key -replace "'", "''") + "'"
}

function Format-PsdValue {
    param(
        [Parameter(Mandatory = $false)]$Value,
        [int]$Indent = 0
    )

    if ($null -eq $Value) { return '$null' }
    if ($Value -is [bool]) { return $(if ($Value) { '$true' } else { '$false' }) }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [byte] -or $Value -is [System.Int16]) {
        return ([int64]$Value).ToString($script:InvariantCulture)
    }
    if ($Value -is [double] -or $Value -is [float] -or $Value -is [decimal]) {
        return ([double]$Value).ToString('R', $script:InvariantCulture)
    }

    if ($Value -is [hashtable] -or $Value -is [System.Collections.IDictionary]) {
        if ($Value.Count -eq 0) { return '@{}' }
        $innerIndent = ' ' * ($Indent + 4)
        $closingIndent = ' ' * $Indent
        $builder = [System.Text.StringBuilder]::new()
        [void]$builder.Append("@{`r`n")
        foreach ($key in $Value.Keys) {
            $line = "{0}{1} = {2}" -f $innerIndent, (Format-PsdKey $key), (Format-PsdValue -Value $Value[$key] -Indent ($Indent + 4))
            [void]$builder.AppendLine($line)
        }
        [void]$builder.Append("$closingIndent}")
        return $builder.ToString()
    }

    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = @($Value)
        if ($items.Count -eq 0) { return '@()' }
        $parts = foreach ($item in $items) {
            Format-PsdValue -Value $item -Indent $Indent
        }
        return '@(' + ($parts -join ', ') + ')'
    }

    return "'" + (([string]$Value) -replace "'", "''") + "'"
}

function Format-ConfigFile {
    param([hashtable]$Config)

    $builder = [System.Text.StringBuilder]::new()
    [void]$builder.AppendLine("# Generated by Setup-MediaPipeline_chatgpt.ps1 (MediaPipeline 1.0) on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    [void]$builder.AppendLine("# Edit directly if you need advanced keys such as ShowOverrides.")
    [void]$builder.AppendLine('@{')

    foreach ($key in $script:ConfigOrder) {
        if (-not $Config.ContainsKey($key)) { continue }
        if ($null -eq $Config[$key]) { continue }
        [void]$builder.AppendLine("    $key = $(Format-PsdValue -Value $Config[$key] -Indent 4)")
    }

    $extraKeys = @($Config.Keys | Where-Object { $script:ConfigOrder -notcontains $_ } | Sort-Object)
    if ($extraKeys.Count -gt 0) {
        [void]$builder.AppendLine('')
        [void]$builder.AppendLine('    # Preserved keys')
        foreach ($key in $extraKeys) {
            [void]$builder.AppendLine("    $(Format-PsdKey $key) = $(Format-PsdValue -Value $Config[$key] -Indent 4)")
        }
    }

    [void]$builder.AppendLine('}')
    return $builder.ToString()
}

function Write-ConfigFile {
    param([string]$Path, [string]$Content)
    $tempPath = "$Path.tmp.$([guid]::NewGuid().ToString('N'))"
    try {
        [System.IO.File]::WriteAllText($tempPath, $Content, [System.Text.UTF8Encoding]::new($false))
        $null = Import-PowerShellDataFile -LiteralPath $tempPath
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
        $tempPath = $null
    } finally {
        if ($tempPath -and (Test-Path -LiteralPath $tempPath)) {
            Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-DependencyStatus {
    $statuses = [System.Collections.Generic.List[pscustomobject]]::new()

    $pwshPath = Resolve-PwshPath
    $statuses.Add([pscustomobject]@{
        Name    = 'PowerShell 7'
        Ok      = [bool]$pwshPath
        Details = if ($pwshPath) { $pwshPath } else { 'Not found next to the bundle or on PATH.' }
        Suggest = 'Bundle PowerShell 7 or install it so pwsh is available.'
    })

    $toolCandidates = @{
        ffmpeg   = @('Tools\ffmpeg\bin\ffmpeg.exe')
        ffprobe  = @('Tools\ffmpeg\bin\ffprobe.exe')
        mkvmerge = @('Tools\MKVToolNix\mkvmerge.exe')
    }
    foreach ($toolName in @('ffmpeg','ffprobe','mkvmerge')) {
        $toolPath = Resolve-ToolPath -ToolName $toolName -RelativeCandidates $toolCandidates[$toolName]
        $statuses.Add([pscustomobject]@{
            Name    = $toolName
            Ok      = [bool]$toolPath
            Details = if ($toolPath) { $toolPath } else { 'Not found in bundle drop-in folders or on PATH.' }
            Suggest = switch ($toolName) {
                'mkvmerge' { 'Install MKVToolNix or place mkvmerge.exe under Tools\MKVToolNix.' }
                default    { 'Install ffmpeg or place ffmpeg.exe and ffprobe.exe under Tools\ffmpeg\bin.' }
            }
        })
    }

    $pythonPath = Resolve-PythonPath
    $statuses.Add([pscustomobject]@{
        Name    = 'Python'
        Ok      = [bool]$pythonPath
        Details = if ($pythonPath) { $pythonPath } else { 'A real Python interpreter was not found.' }
        Suggest = 'Install Python 3 or place python.exe under Runtime\Python or DesktopApp\Runtime\Python.'
    })
    $statuses.Add([pscustomobject]@{
        Name    = 'pysubs2'
        Ok      = [bool]($pythonPath -and (Test-Pysubs2Import $pythonPath))
        Details = if ($pythonPath) {
            if (Test-Pysubs2Import $pythonPath) { 'Import succeeded.' } else { 'Python found, but pysubs2 is missing.' }
        } else {
            'Python is missing, so pysubs2 could not be checked.'
        }
        Suggest = 'Run: python -m pip install pysubs2'
    })
    $statuses.Add([pscustomobject]@{
        Name    = 'Pipeline script'
        Ok      = (Test-Path -LiteralPath $script:PipelinePath)
        Details = $script:PipelinePath
        Suggest = 'Keep MediaPipeline_chatgpt.ps1 in the same deployment folder.'
    })
    $statuses.Add([pscustomobject]@{
        Name    = 'Subtitle converter'
        Ok      = (Test-Path -LiteralPath $script:SubtitlePath)
        Details = $script:SubtitlePath
        Suggest = 'Keep ass_to_srt_chatgpt.py in the same deployment folder.'
    })

    return @($statuses)
}

function Test-VideoPresetCompatibility {
    param([hashtable]$Config)

    if (-not $Config.ContainsKey('VideoCodec') -or -not $Config.ContainsKey('VideoPreset')) {
        return $true
    }

    $codec = [string]$Config['VideoCodec']
    $preset = [string]$Config['VideoPreset']
    $allowed = if ($codec -eq 'libx265') {
        @('ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow','placebo')
    } else {
        @('p1','p2','p3','p4','p5','p6','p7')
    }

    return ($allowed -contains $preset)
}

function Write-ConfigHighlights {
    param([hashtable]$Config)

    Write-Header 'Config Summary'
    Write-Host ("Movies source : {0}" -f $Config['SourceMovies'])
    Write-Host ("TV source     : {0}" -f $Config['SourceTV'])
    Write-Host ("Outsource     : {0}" -f $Config['Outsource'])
    Write-Host ("Scratch       : {0}" -f $Config['LocalBase'])
    Write-Host ("Video         : {0} / preset {1} / quality {2}" -f $Config['VideoCodec'], $Config['VideoPreset'], $Config['VideoQuality'])
    Write-Host ("Thresholds    : Movies {0} GB, TV {1} GB" -f $Config['EncodeThresholdGB'], $Config['TVEncodeThresholdGB'])
    Write-Host ("Disk reserve  : Scratch {0} GB, Outsource {1} GB" -f $Config['MinFreeSpaceGB'], $Config['OutsourceMinFreeSpaceGB'])
    Write-Host ("Deferred push : {0}" -f $(if ($Config['DeferredPublish']) { 'Enabled' } else { 'Disabled' }))
    Write-Host ("TV folders    : {0}" -f $(if ($Config['CreateTVSubfolder']) { 'Enabled' } else { 'Disabled' }))
    Write-Host ("Debug logging : {0}" -f $(if ($Config['DebugMode']) { 'Enabled' } else { 'Disabled' }))
    if ($Config.ContainsKey('PriorityMarkers')) {
        Write-Host ("Priority tags : {0}" -f ((@($Config['PriorityMarkers'])) -join ', '))
    }
    if ($Config.ContainsKey('SourceScanIntervalSeconds') -and $Config.ContainsKey('ProcessedIndexRefreshSeconds')) {
        Write-Host ("Scan refresh  : source {0}s / index {1}s" -f $Config['SourceScanIntervalSeconds'], $Config['ProcessedIndexRefreshSeconds'])
    }
}

function Write-ValidationReport {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)]$Result,
        [Parameter(Mandatory)][hashtable]$Config
    )

    $builder = [System.Text.StringBuilder]::new()
[void]$builder.AppendLine("MediaPipelineRemuxEncodeAIO Deployment Report")
    [void]$builder.AppendLine("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    [void]$builder.AppendLine("Config   : $script:ConfigPath")
    [void]$builder.AppendLine('')
    [void]$builder.AppendLine('Configuration Summary')
    [void]$builder.AppendLine("---------------------")
    foreach ($line in @(
            "Movies source : $($Config['SourceMovies'])",
            "TV source     : $($Config['SourceTV'])",
            "Outsource     : $($Config['Outsource'])",
            "Scratch       : $($Config['LocalBase'])",
            "Video         : $($Config['VideoCodec']) / $($Config['VideoPreset']) / quality $($Config['VideoQuality'])",
            "Deferred push : $(if ($Config['DeferredPublish']) { 'Enabled' } else { 'Disabled' })",
            "Priority tags : $((@($Config['PriorityMarkers'])) -join ', ')",
            "Scan refresh  : source $($Config['SourceScanIntervalSeconds'])s / index $($Config['ProcessedIndexRefreshSeconds'])s"
        )) {
        [void]$builder.AppendLine($line)
    }
    [void]$builder.AppendLine('')
    [void]$builder.AppendLine('Validation Status')
    [void]$builder.AppendLine("-----------------")
    [void]$builder.AppendLine("Result: $(if ($Result.Ok) { 'PASS' } else { 'FAIL' })")
    [void]$builder.AppendLine("Warnings: $($Result.Warnings.Count)")
    [void]$builder.AppendLine("Failures: $($Result.Failures.Count)")
    [void]$builder.AppendLine('')

    if ($Result.Failures.Count -gt 0) {
        [void]$builder.AppendLine('Failures')
        [void]$builder.AppendLine('--------')
        foreach ($failure in $Result.Failures) {
            [void]$builder.AppendLine("- $failure")
        }
        [void]$builder.AppendLine('')
    }

    if ($Result.Warnings.Count -gt 0) {
        [void]$builder.AppendLine('Warnings')
        [void]$builder.AppendLine('--------')
        foreach ($warning in $Result.Warnings) {
            [void]$builder.AppendLine("- $warning")
        }
        [void]$builder.AppendLine('')
    }

    $reportTarget = Normalize-UserPath -Path $Path -BasePath $script:ScriptDir
    $reportDir = Split-Path -Parent $reportTarget
    if ($reportDir -and -not (Test-Path -LiteralPath $reportDir)) {
        New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($reportTarget, $builder.ToString(), [System.Text.UTF8Encoding]::new($false))
    Write-Ok "Wrote validation report: $reportTarget"
}

function Open-ConfigFile {
    param([string]$Path)
    try {
        Start-Process -FilePath $Path | Out-Null
        Write-Ok "Opened config: $Path"
    } catch {
        Write-Warn "Could not open config automatically: $_"
    }
}

function Invoke-Validation {
    param([hashtable]$Config)

    Write-Header 'Validation'
    $failures = [System.Collections.Generic.List[string]]::new()
    $warnings = [System.Collections.Generic.List[string]]::new()

    foreach ($key in $script:RequiredKeys) {
        if (-not $Config.ContainsKey($key)) {
            $failures.Add("Missing required config key: $key")
        }
    }
    $schemaCheck = Test-MediaPipelineConfigSchema -Config $Config
    foreach ($warning in @($schemaCheck.Warnings)) {
        $warnings.Add($warning)
    }
    foreach ($errorText in @($schemaCheck.Errors)) {
        if ($failures -notcontains $errorText) {
            $failures.Add($errorText)
        }
    }

    if ($Config.ContainsKey('VideoCodec')) {
        $allowedCodecs = @('hevc_nvenc','hevc_amf','hevc_qsv','libx265')
        if ($allowedCodecs -notcontains [string]$Config['VideoCodec']) {
            $failures.Add("VideoCodec '$($Config['VideoCodec'])' is not supported by the deployment tool.")
        }
    }
    if (-not (Test-VideoPresetCompatibility -Config $Config)) {
        $failures.Add("VideoPreset '$($Config['VideoPreset'])' is not valid for codec '$($Config['VideoCodec'])'.")
    }

    foreach ($key in @('EncodeThresholdGB','TVEncodeThresholdGB','MinFreeSpaceGB','OutsourceMinFreeSpaceGB','VideoQuality','FFmpegEncodeTimeoutSeconds','FFmpegRemuxTimeoutSeconds','LogRetentionDays','FallbackCpuQuality','SourceScanIntervalSeconds','ProcessedIndexRefreshSeconds')) {
        if ($Config.ContainsKey($key)) {
            try {
                if ([double]$Config[$key] -le 0) {
                    $failures.Add("$key must be greater than 0.")
                }
            } catch {
                $failures.Add("$key must be numeric.")
            }
        }
    }
    if ($Config.ContainsKey('OutputSizeMultiplier')) {
        try {
            $multiplier = [double]$Config['OutputSizeMultiplier']
            if ($multiplier -lt 0.1 -or $multiplier -gt 2.0) {
                $failures.Add("OutputSizeMultiplier must be between 0.1 and 2.0.")
            }
        } catch {
            $failures.Add('OutputSizeMultiplier must be numeric.')
        }
    }
    if ($Config.ContainsKey('MergeThresholdMs')) {
        try {
            $mergeThreshold = [int]$Config['MergeThresholdMs']
            if ($mergeThreshold -lt 0 -or $mergeThreshold -gt 5000) {
                $failures.Add('MergeThresholdMs must be between 0 and 5000.')
            }
        } catch {
            $failures.Add('MergeThresholdMs must be an integer.')
        }
    }
    foreach ($timeoutSpec in @(
        @{ Key = 'RobocopyTimeoutSeconds';    Min = 60; Max = 172800 },
        @{ Key = 'SubtitleExtractTimeoutSeconds'; Min = 30; Max = 3600 },
        @{ Key = 'SubtitleProbeTimeoutSeconds';   Min = 5;  Max = 600  },
        @{ Key = 'BdpgsOcrTimeoutSeconds';         Min = 60; Max = 14400 },
        @{ Key = 'SourceScanTimeoutSeconds';  Min = 30; Max = 86400  },
        @{ Key = 'IndexScanTimeoutSeconds';   Min = 30; Max = 86400  },
        @{ Key = 'CleanupScanTimeoutSeconds'; Min = 30; Max = 7200   },
        @{ Key = 'CleanupStaleAgeHours';      Min = 1;  Max = 720    }
    )) {
        $key = [string]$timeoutSpec.Key
        if ($Config.ContainsKey($key)) {
            try {
                $scanTimeout = [int]$Config[$key]
                if ($scanTimeout -lt [int]$timeoutSpec.Min -or $scanTimeout -gt [int]$timeoutSpec.Max) {
                    $failures.Add("$key must be between $($timeoutSpec.Min) and $($timeoutSpec.Max).")
                }
            } catch {
                $failures.Add("$key must be an integer.")
            }
        }
    }
    if ($Config.ContainsKey('TransientFailureRetryLimit')) {
        try {
            $retryLimit = [int]$Config['TransientFailureRetryLimit']
            if ($retryLimit -lt 1 -or $retryLimit -gt 100) {
                $failures.Add('TransientFailureRetryLimit must be between 1 and 100.')
            }
        } catch {
            $failures.Add('TransientFailureRetryLimit must be an integer.')
        }
    }
    foreach ($boolKey in @(
        'AggressiveEpisodeParsing','AllowSystemTools','CleanupRemoteStaging',
        'ConvertTx3gToSrt','DropTx3gAfterConversion','CreateExternalTx3gSrtSidecars',
        'ConvertBdpgsToSrt','DropBdpgsAfterConversion',
        'Tx3gPreserveExistingSrt','Tx3gTreatForcedAsSeparate',
        'TreatAssSignsSongsAsForced','TreatTx3gSignsSongsAsForced','TreatBdpgsSignsSongsAsForced'
    )) {
        if ($Config.ContainsKey($boolKey) -and $Config[$boolKey] -isnot [bool]) {
            $failures.Add("$boolKey must be `$true or `$false.")
        }
    }
    if ($Config.ContainsKey('PriorityMarkers')) {
        $markers = @($Config['PriorityMarkers'])
        if ($markers.Count -eq 0) {
            $warnings.Add('PriorityMarkers is empty. Priority filename/folder tags will be disabled.')
        } else {
            foreach ($marker in $markers) {
                if ([string]::IsNullOrWhiteSpace([string]$marker)) {
                    $failures.Add('PriorityMarkers cannot contain empty values.')
                    break
                }
            }
        }
    }

    if ($Config.ContainsKey('MinFreeSpaceGB') -and $Config.ContainsKey('EncodeThresholdGB')) {
        try {
            if ([double]$Config['MinFreeSpaceGB'] -lt [double]$Config['EncodeThresholdGB']) {
                $warnings.Add("MinFreeSpaceGB is lower than EncodeThresholdGB. Large encodes may still run out of scratch space.")
            }
        } catch { }
    }

    $pathMap = @{}
    $pathStatusMap = @{}
    $validationPathTimeoutSeconds = 12
    foreach ($key in @('SourceMovies','SourceTV','Outsource','LocalBase')) {
        if (-not $Config.ContainsKey($key)) { continue }
        $path = Normalize-UserPath -Path ([string]$Config[$key]) -BasePath $script:ScriptDir
        $pathMap[$key] = $path

        $pathStatus = Test-ValidationPathExists -Path $path -TimeoutSeconds $validationPathTimeoutSeconds
        $pathStatusMap[$key] = $pathStatus
        if ($pathStatus.StartError) {
            $failures.Add("$key could not be checked: $($pathStatus.StartError)")
        } elseif ($pathStatus.TimedOut) {
            $failures.Add("$key timed out after $validationPathTimeoutSeconds second(s) while checking path availability: $path")
        } elseif ($pathStatus.Exists) {
            Write-Ok "$key exists: $path"
        } else {
            $failures.Add("$key does not exist: $path")
        }
    }

    try {
        if ($pathMap.Count -ge 2) {
            Test-PathsDisjoint -Paths $pathMap
            Write-Ok 'Source, scratch, and outsource paths are disjoint.'
        }
    } catch {
        $failures.Add($_.Exception.Message)
    }

    foreach ($key in @('LocalBase','Outsource')) {
        if ($pathMap.ContainsKey($key) -and $pathStatusMap.ContainsKey($key) -and $pathStatusMap[$key].Exists) {
            $writableStatus = Test-ValidationPathWritable -Path $pathMap[$key] -TimeoutSeconds $validationPathTimeoutSeconds
            if ($writableStatus.StartError) {
                $failures.Add("$key writability could not be checked: $($writableStatus.StartError)")
            } elseif ($writableStatus.TimedOut) {
                $failures.Add("$key timed out after $validationPathTimeoutSeconds second(s) while checking writability: $($pathMap[$key])")
            } elseif ($writableStatus.Writable) {
                Write-Ok "$key is writable."
            } else {
                $detail = ''
                if ($writableStatus.Output.Count -gt 0) {
                    $detail = " $($writableStatus.Output[0])"
                }
                $failures.Add("$key is not writable: $($pathMap[$key])$detail")
            }
        }
    }

    $dependencyStatus = @(Get-DependencyStatus)
    Write-Host ''
    Write-Host 'Dependency check:' -ForegroundColor Cyan
    foreach ($dep in $dependencyStatus) {
        if ($dep.Ok) {
            Write-Ok "$($dep.Name): $($dep.Details)"
        } else {
            $message = "$($dep.Name): $($dep.Details) Suggested fix: $($dep.Suggest)"
            $failures.Add($message)
        }
    }

    if ($failures.Count -eq 0 -and $warnings.Count -eq 0) {
        Write-Host ''
        Write-Host 'Deployment validation passed.' -ForegroundColor Green
    } elseif ($failures.Count -eq 0) {
        Write-Host ''
        Write-Host "Validation passed with $($warnings.Count) warning(s)." -ForegroundColor Yellow
        foreach ($warning in $warnings) { Write-Warn $warning }
    } else {
        Write-Host ''
        Write-Host "Validation found $($failures.Count) error(s)." -ForegroundColor Red
        foreach ($warning in $warnings) { Write-Warn $warning }
        foreach ($failure in $failures) { Write-Fail $failure }
    }

    return @{
        Ok           = ($failures.Count -eq 0)
        Failures     = @($failures)
        Warnings     = @($warnings)
        Dependencies = $dependencyStatus
        PathMap      = $pathMap
    }
}

function Get-ConfigSeed {
    param([hashtable]$Existing)
    $seed = Get-DefaultConfig
    foreach ($key in $Existing.Keys) {
        if ($key -in @('SourceMovies','SourceTV','Outsource','LocalBase')) {
            $seed[$key] = Normalize-UserPath -Path ([string]$Existing[$key]) -BasePath $script:ScriptDir
        } else {
            $seed[$key] = $Existing[$key]
        }
    }
    if ($SourceMovies) { $seed['SourceMovies'] = Normalize-UserPath -Path $SourceMovies -BasePath $script:ScriptDir }
    if ($SourceTV)     { $seed['SourceTV']     = Normalize-UserPath -Path $SourceTV -BasePath $script:ScriptDir }
    if ($Outsource)    { $seed['Outsource']    = Normalize-UserPath -Path $Outsource -BasePath $script:ScriptDir }
    if ($LocalBase)    { $seed['LocalBase']    = Normalize-UserPath -Path $LocalBase -BasePath $script:ScriptDir }
    return $seed
}

function Invoke-ConfigWizard {
    param([hashtable]$Existing)

    $config = Get-ConfigSeed -Existing $Existing

    Write-Step 1 4 'Folders'
    Write-Header 'Step 1 of 4: Folders'
    Write-Info 'Choose the incoming, scratch, and final-output folders.'
    $config['SourceMovies'] = Read-Path -Prompt 'Movies source folder' -Default ([string]$config['SourceMovies']) -CreateIfMissing -CreateDefaultYes $false
    $config['SourceTV']     = Read-Path -Prompt 'TV source folder'     -Default ([string]$config['SourceTV'])     -CreateIfMissing -CreateDefaultYes $false
    $config['LocalBase']    = Read-Path -Prompt 'Local scratch folder' -Default ([string]$config['LocalBase'])    -CreateIfMissing -MustBeWritable
    $config['Outsource']    = Read-Path -Prompt 'Final output folder'  -Default ([string]$config['Outsource'])    -CreateIfMissing -MustBeWritable
    Test-PathsDisjoint -Paths @{
        SourceMovies = $config['SourceMovies']
        SourceTV     = $config['SourceTV']
        LocalBase    = $config['LocalBase']
        Outsource    = $config['Outsource']
    }

    Write-Step 2 4 'Video'
    Write-Header 'Step 2 of 4: Video'
    $gpu = Get-DetectedGpu
    if ($gpu.Vendor -ne 'None') {
        Write-Ok "Detected $($gpu.Vendor): $($gpu.Name)"
    } else {
        Write-Warn 'No supported GPU was detected. CPU defaults are safest.'
    }

    $videoProfiles = @(
        @{ Codec = 'hevc_nvenc'; Preset = 'p7';    Quality = 22; Label = 'NVIDIA / NVENC (recommended when available)' }
        @{ Codec = 'hevc_amf';   Preset = 'p7';    Quality = 22; Label = 'AMD / AMF' }
        @{ Codec = 'hevc_qsv';   Preset = 'p7';    Quality = 22; Label = 'Intel / QSV' }
        @{ Codec = 'libx265';    Preset = 'medium'; Quality = 20; Label = 'CPU / libx265' }
    )
    $videoDefault = switch -Regex ($config['VideoCodec']) {
        '^hevc_nvenc$' { 1; break }
        '^hevc_amf$'   { 2; break }
        '^hevc_qsv$'   { 3; break }
        '^libx265$'    { 4; break }
        default {
            switch ($gpu.Vendor) {
                'NVIDIA' { 1 }
                'AMD'    { 2 }
                'Intel'  { 3 }
                default  { 4 }
            }
        }
    }
    for ($i = 0; $i -lt $videoProfiles.Count; $i++) {
        Write-Host ("  {0}. {1}" -f ($i + 1), $videoProfiles[$i].Label)
    }
    $videoPick = Read-Choice -Prompt 'Video profile' -Options ($videoProfiles | ForEach-Object { $_.Label }) -Default $videoDefault
    $video = $videoProfiles[$videoPick - 1]

    $config['VideoCodec']      = $video.Codec
    $config['VideoPreset']     = $video.Preset
    $config['VideoQuality']    = $video.Quality
    $config['ExtraVideoFlags'] = Get-ExtraVideoFlagsForCodec $video.Codec

    if (Read-YesNo 'Tune the video quality or preset manually?' -DefaultYes $false) {
        $defaultQuality = [string]$config['VideoQuality']
        $config['VideoQuality'] = [int](Read-PositiveNumber -Prompt 'Video quality (18-28 is the usual range)' -Default $defaultQuality)

        $presetOptions = if ($config['VideoCodec'] -eq 'libx265') {
            @('ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow')
        } else {
            @('p1','p2','p3','p4','p5','p6','p7')
        }
        $presetDefault = [array]::IndexOf($presetOptions, [string]$config['VideoPreset']) + 1
        if ($presetDefault -lt 1) { $presetDefault = $presetOptions.Count }
        for ($i = 0; $i -lt $presetOptions.Count; $i++) {
            Write-Host ("  {0}. {1}" -f ($i + 1), $presetOptions[$i])
        }
        $presetPick = Read-Choice -Prompt 'Video preset' -Options $presetOptions -Default $presetDefault
        $config['VideoPreset'] = $presetOptions[$presetPick - 1]
    }

    Write-Step 3 4 'Playback and subtitles'
    Write-Header 'Step 3 of 4: Playback and subtitles'
    $playbackProfiles = @(
        @{
            Label                    = 'Plex smart TV friendly (recommended)'
            CompatibleAudioCodecs    = @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp')
            DropAssAfterConversion   = $false
            DropTx3gAfterConversion  = $false
            DropBdpgsAfterConversion = $false
            RemoveKaraoke            = $true
            KeepSignsAndSongs        = $true
            TreatAssSignsSongsAsForced = $false
            TreatTx3gSignsSongsAsForced = $false
            TreatBdpgsSignsSongsAsForced = $false
        }
        @{
            Label                    = 'AV passthrough / preserve FLAC and DTS'
            CompatibleAudioCodecs    = @('aac','ac3','eac3','mp3','opus','vorbis','flac','truehd','mlp','dts','dts-hd')
            DropAssAfterConversion   = $false
            DropTx3gAfterConversion  = $false
            DropBdpgsAfterConversion = $false
            RemoveKaraoke            = $true
            KeepSignsAndSongs        = $true
            TreatAssSignsSongsAsForced = $false
            TreatTx3gSignsSongsAsForced = $false
            TreatBdpgsSignsSongsAsForced = $false
        }
        @{
            Label                    = 'Custom audio and subtitle choices'
            CompatibleAudioCodecs    = @()
            DropAssAfterConversion   = $false
            DropTx3gAfterConversion  = $false
            DropBdpgsAfterConversion = $false
            RemoveKaraoke            = $true
            KeepSignsAndSongs        = $true
            TreatAssSignsSongsAsForced = $false
            TreatTx3gSignsSongsAsForced = $false
            TreatBdpgsSignsSongsAsForced = $false
        }
    )

    $playbackDefault = 1
    $currentCompat = @($config['CompatibleAudioCodecs'])
    if ($currentCompat -contains 'dts' -or $currentCompat -contains 'dts-hd' -or $currentCompat -contains 'flac') {
        $playbackDefault = 2
    }
    for ($i = 0; $i -lt $playbackProfiles.Count; $i++) {
        Write-Host ("  {0}. {1}" -f ($i + 1), $playbackProfiles[$i].Label)
    }
    $playbackPick = Read-Choice -Prompt 'Playback profile' -Options ($playbackProfiles | ForEach-Object { $_.Label }) -Default $playbackDefault
    $playback = $playbackProfiles[$playbackPick - 1]

    if ($playbackPick -eq 3) {
        $compat = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($codec in @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp')) {
            [void]$compat.Add($codec)
        }
        if (Read-YesNo 'Preserve FLAC audio untouched?' -DefaultYes ($currentCompat -contains 'flac')) {
            [void]$compat.Add('flac')
        }
        if (Read-YesNo 'Preserve DTS / DTS-HD audio untouched?' -DefaultYes (($currentCompat -contains 'dts') -or ($currentCompat -contains 'dts-hd'))) {
            [void]$compat.Add('dts')
            [void]$compat.Add('dts-hd')
        }
        $config['CompatibleAudioCodecs'] = @($compat)
        $config['DropAssAfterConversion'] = Read-YesNo 'Drop original ASS tracks after SRT conversion?' -DefaultYes ([bool]$config['DropAssAfterConversion'])
        $config['DropTx3gAfterConversion'] = Read-YesNo 'Drop original TX3G tracks after SRT conversion when the output container can preserve them?' -DefaultYes ([bool]$config['DropTx3gAfterConversion'])
        $config['DropBdpgsAfterConversion'] = Read-YesNo 'Drop original BDPGS tracks after OCR conversion when the output container can preserve them?' -DefaultYes ([bool]$config['DropBdpgsAfterConversion'])
        $config['CreateExternalTx3gSrtSidecars'] = Read-YesNo 'Write external TX3G-derived SRT sidecar files next to the output?' -DefaultYes ([bool]$config['CreateExternalTx3gSrtSidecars'])
        $config['RemoveKaraoke']          = Read-YesNo 'Filter karaoke-style subtitle events during ASS to SRT conversion?' -DefaultYes ([bool]$config['RemoveKaraoke'])
        $config['KeepSignsAndSongs']      = Read-YesNo 'Keep Signs and Songs ASS tracks as separate subtitle tracks?' -DefaultYes ([bool]$config['KeepSignsAndSongs'])
        $config['TreatAssSignsSongsAsForced'] = Read-YesNo 'Mark ASS Signs and Songs tracks as forced subtitles?' -DefaultYes ([bool]$config['TreatAssSignsSongsAsForced'])
        $config['TreatTx3gSignsSongsAsForced'] = Read-YesNo 'Mark TX3G Signs and Songs tracks as forced subtitles?' -DefaultYes ([bool]$config['TreatTx3gSignsSongsAsForced'])
        $config['TreatBdpgsSignsSongsAsForced'] = Read-YesNo 'Mark BDPGS Signs and Songs tracks as forced subtitles?' -DefaultYes ([bool]$config['TreatBdpgsSignsSongsAsForced'])
    } else {
        $config['CompatibleAudioCodecs']  = @($playback.CompatibleAudioCodecs)
        $config['DropAssAfterConversion'] = $playback.DropAssAfterConversion
        $config['DropTx3gAfterConversion'] = $playback.DropTx3gAfterConversion
        $config['DropBdpgsAfterConversion'] = $playback.DropBdpgsAfterConversion
        $config['RemoveKaraoke']          = $playback.RemoveKaraoke
        $config['KeepSignsAndSongs']      = $playback.KeepSignsAndSongs
        $config['TreatAssSignsSongsAsForced'] = $playback.TreatAssSignsSongsAsForced
        $config['TreatTx3gSignsSongsAsForced'] = $playback.TreatTx3gSignsSongsAsForced
        $config['TreatBdpgsSignsSongsAsForced'] = $playback.TreatBdpgsSignsSongsAsForced
    }

    Write-Step 4 4 'Routing and safety'
    Write-Header 'Step 4 of 4: Routing and safety'
    $config['EncodeThresholdGB'] = Read-PositiveNumber -Prompt 'Movie encode threshold in GB' -Default ([string]$config['EncodeThresholdGB'])
    $config['TVEncodeThresholdGB'] = Read-PositiveNumber -Prompt 'TV encode threshold in GB' -Default ([string]$config['TVEncodeThresholdGB'])
    $config['MinFreeSpaceGB'] = Read-PositiveNumber -Prompt 'Minimum free space on the scratch disk in GB' -Default ([string]$config['MinFreeSpaceGB'])
    if (Read-YesNo 'Use the same minimum free-space reserve for the outsource path?' -DefaultYes $true) {
        $config['OutsourceMinFreeSpaceGB'] = $config['MinFreeSpaceGB']
    } else {
        $config['OutsourceMinFreeSpaceGB'] = Read-PositiveNumber -Prompt 'Minimum free space on the outsource path in GB' -Default ([string]$config['OutsourceMinFreeSpaceGB'])
    }
    $config['DeferredPublish'] = Read-YesNo 'Defer publishing completed outputs to the share and park them locally?' -DefaultYes ([bool]$config['DeferredPublish'])
    $config['CreateTVSubfolder']  = Read-YesNo 'Store TV files under TV\<Show>\Season NN\' -DefaultYes ([bool]$config['CreateTVSubfolder'])
    $config['AggressiveEpisodeParsing'] = Read-YesNo 'Use aggressive TV episode parsing for anime/import filenames?' -DefaultYes ([bool]$config['AggressiveEpisodeParsing'])
    $config['SkipStabilityCheck'] = -not (Read-YesNo 'Keep the file-stability check enabled?' -DefaultYes (-not [bool]$config['SkipStabilityCheck']))
    $config['DebugMode']          = Read-YesNo 'Enable verbose debug logging?' -DefaultYes ([bool]$config['DebugMode'])

    Write-ConfigHighlights -Config $config
    return $config
}

function Initialize-ProgressSkeleton {
    <#
    .SYNOPSIS
    Seeds pipeline_progress.json with a zeroed-out Idle skeleton if the file
    does not already exist.  Called automatically after a successful config write
    so that the desktop app can display an Idle state immediately on first launch.
    #>
    param([hashtable]$Config)

    $localBase = $Config['LocalBase']
    if ([string]::IsNullOrWhiteSpace($localBase)) {
        Write-Warn 'Skipping progress skeleton: LocalBase is not configured.'
        return
    }

    $progressDir  = Join-Path $localBase 'State\Progress'
    $progressFile = Join-Path $progressDir 'pipeline_progress.json'

    if (Test-Path -LiteralPath $progressFile) {
        Write-Ok "Progress file already exists, skeleton skipped."
        return
    }

    try {
        if (-not (Test-Path -LiteralPath $progressDir)) {
            New-Item -ItemType Directory -Path $progressDir -Force | Out-Null
        }

        $emptyControl = [ordered]@{
            Requested             = $false
            RequestId             = $null
            CreatedAt             = $null
            LastObservedRequestId = $null
            LastObservedCreatedAt = $null
            LastObservedAt        = $null
        }

        $skeleton = [ordered]@{
            ProgressVersion       = 2
            LastUpdate            = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
            SessionStartedAt      = $null
            CurrentFile           = $null
            CurrentFileDisplay    = $null
            CurrentFilePath       = $null
            CurrentMediaType      = $null
            CurrentQueuePhase     = $null
            CurrentQueueIndex     = 0
            CurrentQueueTotal     = 0
            CurrentRoute          = $null
            CurrentStage          = 'idle'
            CurrentStagePercent   = 0.0
            CurrentItemStartedAt  = $null
            CurrentStageStartedAt = $null
            CopyState             = $null
            PushState             = $null
            SidecarState          = $null
            PauseRequested        = $false
            StopRequested         = $false
            ControlRequests       = [ordered]@{
                Pause  = $emptyControl
                Stop   = $emptyControl
                Rescan = $emptyControl
            }
            Status                = 'Idle'
            TotalProcessed        = 0
            Encoded               = 0
            Remuxed               = 0
            Failed                = 0
            Movies                = 0
            TVEpisodes            = 0
        }

        $json = $skeleton | ConvertTo-Json -Depth 4
        [System.IO.File]::WriteAllText($progressFile, $json, [System.Text.UTF8Encoding]::new($false))
        Write-Ok "Wrote progress skeleton: $progressFile"
    } catch {
        Write-Warn "Could not write progress skeleton: $_"
    }
}

function Show-Closing {
    param(
        [string]$ConfigPathValue,
        [string]$BackupPath = $null,
        [string]$ReportPathValue = $null
    )
    Write-Header 'Rapid Deployment Complete'
    Write-Host "Config file: $ConfigPathValue" -ForegroundColor Green
    if ($BackupPath) {
        Write-Host "Backup made: $BackupPath" -ForegroundColor Green
    }
    if ($ReportPathValue) {
        Write-Host "Report file: $ReportPathValue" -ForegroundColor Green
    }
Write-Host "Setup launcher: $($script:ScriptDir)\Setup-MediaPipelineRemuxEncodeAIO.bat" -ForegroundColor Green
Write-Host "Run launcher  : $($script:ScriptDir)\Run-MediaPipelineRemuxEncodeAIO.bat" -ForegroundColor Green
    Write-Host ''
    Write-Host 'Next steps:' -ForegroundColor Cyan
    Write-Host '  1. Review the validation output above.'
Write-Host '  2. If dependencies are installed, run Run-MediaPipelineRemuxEncodeAIO.bat.'
Write-Host '  3. Re-run Setup-MediaPipelineRemuxEncodeAIO.bat any time to edit or validate the config.'
}

function Invoke-Main {
Write-Header 'MediaPipelineRemuxEncodeAIO Deployment'
    Write-Info 'This setup script writes MediaPipeline_config_chatgpt.psd1 next to the patched pipeline files.'

    if ($ListDefaults) {
        Write-Header 'Default Config'
        Write-Host (Format-ConfigFile -Config (Get-DefaultConfig))
        return 0
    }

    $readResult = Read-ExistingConfig -Path $script:ConfigPath
    $existing = $readResult.Result
    if ($readResult.ParseFailed) {
        Write-Warn 'Existing config could not be parsed cleanly. Running the wizard will rebuild it from known values and keep any remaining manual keys only if they were parseable.'
    }

    if ($ValidateOnly) {
        if (-not (Test-Path -LiteralPath $script:ConfigPath)) {
            Write-Fail "Config file not found: $script:ConfigPath"
Write-Info "Run Setup-MediaPipelineRemuxEncodeAIO.bat to create it."
            return 1
        }
        $result = Invoke-Validation -Config $existing
        if ($ReportPath) {
            Write-ValidationReport -Path $ReportPath -Result $result -Config $existing
        }
        return $(if ($result.Ok) { 0 } else { 1 })
    }

    if ($existing.Count -gt 0 -and -not $script:UseAcceptDefaults) {
        Write-Host ''
        Write-Host "Existing config found: $script:ConfigPath" -ForegroundColor Yellow
        Write-Host '  1. Edit and rewrite the config'
        Write-Host '  2. Validate only'
        $mode = Read-Choice -Prompt 'Choice' -Options @('Edit','Validate') -Default 1
        if ($mode -eq 2) {
            $result = Invoke-Validation -Config $existing
            return $(if ($result.Ok) { 0 } else { 1 })
        }
    }

    $config = Invoke-ConfigWizard -Existing $existing
    $content = Format-ConfigFile -Config $config

    if ($DryRun) {
        Write-Header 'Dry Run Preview'
        ($content -split "`r?`n") | Select-Object -First 60 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
        Write-Host '...'
        $previewResult = Invoke-Validation -Config $config
        if ($ReportPath) {
            Write-ValidationReport -Path $ReportPath -Result $previewResult -Config $config
        }
        return 0
    }

    $backupPath = Invoke-ConfigBackup -Path $script:ConfigPath -Keep 5
    if ($backupPath) {
        Write-Ok "Backed up existing config to $backupPath"
    }
    Write-ConfigFile -Path $script:ConfigPath -Content $content
    Write-Ok "Wrote $script:ConfigPath"
    $writtenConfig = (Import-PowerShellDataFile -LiteralPath $script:ConfigPath)
    $result = Invoke-Validation -Config $writtenConfig
    if ($ReportPath) {
        Write-ValidationReport -Path $ReportPath -Result $result -Config $writtenConfig
    }
    Initialize-ProgressSkeleton -Config $writtenConfig
    if ($OpenConfig) {
        Open-ConfigFile -Path $script:ConfigPath
    }
    Show-Closing -ConfigPathValue $script:ConfigPath -BackupPath $backupPath -ReportPathValue $ReportPath
    return $(if ($result.Ok) { 0 } else { 1 })
}

try {
    exit (Invoke-Main)
} catch {
    Write-Host ''
    Write-Fail "Setup failed: $_"
    if ($_.ScriptStackTrace) {
        Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
    }
    exit 1
}
