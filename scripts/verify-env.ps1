[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Write-Section {
    param([string]$Title)
    $bar = '=' * 72
    Write-Host ''
    Write-Host $bar -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host $bar -ForegroundColor Cyan
}

function Write-Ok   { param([string]$Message) Write-Host "[ OK ] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fail { param([string]$Message) Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Resolve-CommandPath {
    param(
        [string[]]$Candidates,
        [string[]]$RelativePreferred = @(),
        [switch]$RejectWindowsApps
    )

    foreach ($relative in $RelativePreferred) {
        $full = Join-Path $script:Root $relative
        if (Test-Path -LiteralPath $full) {
            return (Resolve-Path -LiteralPath $full).Path
        }
    }

    foreach ($candidate in $Candidates) {
        $commands = @(Get-Command $candidate -All -ErrorAction SilentlyContinue)
        foreach ($command in $commands) {
            if ($RejectWindowsApps -and $command.Source -match '\\WindowsApps\\') {
                continue
            }
            return $command.Source
        }
    }

    return $null
}

function Test-DirectoryWritable {
    param([Parameter(Mandatory = $true)][string]$DirectoryPath)

    if (-not (Test-Path -LiteralPath $DirectoryPath)) {
        return $false
    }

    $probe = Join-Path $DirectoryPath (".codex_write_probe_{0}.tmp" -f ([guid]::NewGuid().ToString('N')))
    try {
        [System.IO.File]::WriteAllText($probe, 'probe', [System.Text.Encoding]::UTF8)
        Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
        return $true
    } catch {
        if (Test-Path -LiteralPath $probe) {
            Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        }
        return $false
    }
}

function Get-ConfigValue {
    param(
        $Config,
        [Parameter(Mandatory = $true)][string]$Key,
        $Default = $null
    )

    if (-not $Config) { return $Default }
    if ($Config -is [System.Collections.IDictionary] -and $Config.Contains($Key)) {
        return $Config[$Key]
    }
    $property = $Config.PSObject.Properties[$Key]
    if ($property) { return $property.Value }
    return $Default
}

function Get-ConfigBoolValue {
    param(
        $Config,
        [Parameter(Mandatory = $true)][string]$Key,
        [bool]$Default = $false
    )

    $value = Get-ConfigValue -Config $Config -Key $Key -Default $Default
    if ($value -is [bool]) { return [bool]$value }
    if ($null -eq $value) { return $Default }
    $text = ([string]$value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes','y','on')) { return $true }
    if ($text -in @('false','0','no','n','off')) { return $false }
    return $Default
}

function Resolve-PipelineRelativePath {
    param([string]$PathValue)

    if ([string]::IsNullOrWhiteSpace($PathValue)) { return '' }
    $expanded = [Environment]::ExpandEnvironmentVariables($PathValue.Trim().Trim('"').Trim("'"))
    if ([System.IO.Path]::IsPathRooted($expanded)) { return $expanded }
    return (Join-Path $script:PipelineRoot $expanded)
}

function ConvertTo-EnvironmentProcessArgument {
    param([AllowNull()][string]$Value)

    if ($null -eq $Value) { return '""' }
    $text = [string]$Value
    if ($text.Length -eq 0) { return '""' }
    if ($text -notmatch '[\s"]') { return $text }
    return ('"' + ($text -replace '"', '\"') + '"')
}

function Invoke-EnvironmentProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [int]$TimeoutSeconds = 180
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = (($Arguments | ForEach-Object { ConvertTo-EnvironmentProcessArgument -Value $_ }) -join ' ')
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

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

        try { $stdout = $stdoutTask.GetAwaiter().GetResult() } catch { $stdout = "[environment-check stdout read failed] $($_.Exception.Message)" }
        try { $stderr = $stderrTask.GetAwaiter().GetResult() } catch { $stderr = "[environment-check stderr read failed] $($_.Exception.Message)" }

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

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$script:Root = [System.IO.Path]::GetFullPath((Split-Path -Parent $scriptRoot))
$desktopRoot = Join-Path $script:Root 'DesktopApp'
$pipelineRoot = Join-Path $script:Root 'Pipeline'
$script:PipelineRoot = $pipelineRoot

$desktopPackage = Join-Path $desktopRoot 'mediapipeline_desktop_app'
$pipelineSetup = Join-Path $pipelineRoot 'Setup-MediaPipeline.ps1'
$pipelineRun = Join-Path $script:Root 'scripts\dev\run.bat'
$pipelineScript = Join-Path $pipelineRoot 'MediaPipeline.ps1'
$pipelineConfig = @(
    Join-Path $pipelineRoot 'MediaPipeline_config.psd1'
    Join-Path $pipelineRoot 'MediaPipeline_config_chatgpt.psd1'
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pipelineConfig) {
    $pipelineConfig = Join-Path $pipelineRoot 'MediaPipeline_config.psd1'
}
$auditScript = Join-Path $pipelineRoot 'Audit-MediaLibrary.ps1'
$subtitleHelper = Join-Path $pipelineRoot 'ass_to_srt.py'

$pythonGui = Resolve-CommandPath -Candidates @('pythonw','pythonw.exe','python','python.exe') -RelativePreferred @('DesktopApp\Runtime\Python\pythonw.exe','DesktopApp\Runtime\Python\python.exe','Pipeline\Runtime\Python\python.exe') -RejectWindowsApps
$pythonCli = Resolve-CommandPath -Candidates @('python','python.exe') -RelativePreferred @('DesktopApp\Runtime\Python\python.exe','Pipeline\Runtime\Python\python.exe') -RejectWindowsApps
$pwsh = Resolve-CommandPath -Candidates @('pwsh','pwsh.exe') -RelativePreferred @('Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe')
$powershellBootstrap = Resolve-CommandPath -Candidates @('powershell','powershell.exe')
$ffmpeg = Resolve-CommandPath -Candidates @('ffmpeg','ffmpeg.exe') -RelativePreferred @('Pipeline\Tools\ffmpeg\bin\ffmpeg.exe')
$ffprobe = Resolve-CommandPath -Candidates @('ffprobe','ffprobe.exe') -RelativePreferred @('Pipeline\Tools\ffmpeg\bin\ffprobe.exe')
$mkvmerge = Resolve-CommandPath -Candidates @('mkvmerge','mkvmerge.exe') -RelativePreferred @('Pipeline\Tools\MKVToolNix\mkvmerge.exe')
$bundledPgsToSrt = Join-Path $pipelineRoot 'Tools\PgsToSrt\PgsToSrt.exe'
$bundledPgsTessdata = Join-Path $pipelineRoot 'Tools\PgsToSrt\tessdata'
$bundledPgsEnglishData = Join-Path $bundledPgsTessdata 'eng.traineddata'

$failed = $false
$configData = $null
$pythonPackages = @{}

Write-Section 'Release Layout'
foreach ($pair in @(
    @{ Label = 'DesktopApp folder'; Path = $desktopRoot },
    @{ Label = 'Pipeline folder'; Path = $pipelineRoot },
    @{ Label = 'Desktop package'; Path = $desktopPackage },
    @{ Label = 'Pipeline setup'; Path = $pipelineSetup },
    @{ Label = 'Canonical run launcher'; Path = $pipelineRun },
    @{ Label = 'Pipeline script'; Path = $pipelineScript },
    @{ Label = 'Audit script'; Path = $auditScript },
    @{ Label = 'Subtitle helper'; Path = $subtitleHelper }
)) {
    if (Test-Path -LiteralPath $pair.Path) {
        Write-Ok ("{0}: {1}" -f $pair.Label, $pair.Path)
    } else {
        Write-Fail ("{0}: missing ({1})" -f $pair.Label, $pair.Path)
        $failed = $true
    }
}

Write-Section 'Runtime Dependencies'
if ($pythonGui) { Write-Ok "Bundled Python host: $pythonGui" } else { Write-Warn "Bundled Python host not found. Preferred: DesktopApp\\Runtime\\Python\\pythonw.exe or Pipeline\\Runtime\\Python\\python.exe. Windows Store aliases are ignored." }
if ($pythonCli) { Write-Ok "CLI Python host: $pythonCli" } else { Write-Fail "CLI Python not found. The pipeline subtitle helper requires python.exe. Windows Store aliases are ignored."; $failed = $true }
if ($pwsh) {
    Write-Ok "PowerShell 7 host: $pwsh"
} else {
    Write-Fail "PowerShell 7 host not found. The pipeline requires pwsh."
    if ($powershellBootstrap) {
        Write-Warn "Windows PowerShell bootstrap is available: $powershellBootstrap"
        Write-Warn 'That is only sufficient to bootstrap a bundled pwsh, not to run the pipeline by itself.'
    }
    $failed = $true
}
if ($ffmpeg) { Write-Ok "ffmpeg: $ffmpeg" } else { Write-Fail "ffmpeg not found."; $failed = $true }
if ($ffprobe) { Write-Ok "ffprobe: $ffprobe" } else { Write-Fail "ffprobe not found."; $failed = $true }
if ($mkvmerge) { Write-Ok "mkvmerge: $mkvmerge" } else { Write-Fail "mkvmerge not found."; $failed = $true }

Write-Section 'Python Package Check'
if ($pythonCli) {
    $result = & $pythonCli -c "import importlib.util; names=['pysubs2','psutil','zeroconf']; [print(name + '=' + str(bool(importlib.util.find_spec(name)))) for name in names]" 2>$null
    foreach ($line in @($result)) {
        if ([string]$line -match '^([^=]+)=(True|False)$') {
            $pythonPackages[$matches[1]] = ($matches[2] -eq 'True')
        }
    }
    if ($pythonPackages['pysubs2']) {
        Write-Ok 'pysubs2 is available.'
    } else {
        Write-Fail 'pysubs2 is missing. Install with: python -m pip install pysubs2'
        $failed = $true
    }
    if ($pythonPackages['psutil']) {
        Write-Ok 'psutil is available.'
    } else {
        Write-Fail 'psutil is missing. The local API process and telemetry services require it.'
        $failed = $true
    }
}

Write-Section 'Pipeline Config'
$configParent = Split-Path -Parent $pipelineConfig
if (Test-Path -LiteralPath $configParent) {
    if (Test-DirectoryWritable -DirectoryPath $configParent) {
        Write-Ok "Config destination is writable: $configParent"
    } else {
        Write-Fail "Config destination is not writable: $configParent"
        Write-Warn 'Move the release out of a read-only location before running setup.'
        $failed = $true
    }
} else {
    Write-Fail "Config destination parent is missing: $configParent"
    $failed = $true
}

if (Test-Path -LiteralPath $pipelineConfig) {
    Write-Ok "Config found: $pipelineConfig"
    try {
        $configData = Import-PowerShellDataFile -LiteralPath $pipelineConfig
    } catch {
        Write-Fail "Config could not be imported: $($_.Exception.Message)"
        $failed = $true
    }
    if ($pwsh -and (Test-Path -LiteralPath $pipelineSetup)) {
        $setupValidatorTimeoutSeconds = 180
        Write-Host "Running setup validator (timeout ${setupValidatorTimeoutSeconds}s)..." -ForegroundColor DarkGray
        $originalPath = $env:PATH
        $prepend = @(
            (Join-Path $script:Root 'DesktopApp\Runtime\Python'),
            (Join-Path $script:Root 'Pipeline\Runtime\Python'),
            (Join-Path $script:Root 'Pipeline\Tools\ffmpeg\bin'),
            (Join-Path $script:Root 'Pipeline\Tools\MKVToolNix'),
            (Join-Path $script:Root 'Pipeline\PowerShell-7.6.0-win-x64')
        ) | Where-Object { Test-Path -LiteralPath $_ }
        if ($prepend) {
            $env:PATH = (($prepend -join ';') + ';' + $env:PATH)
        }
        try {
            $validateResult = Invoke-EnvironmentProcess -FilePath $pwsh -Arguments @(
                '-NoProfile',
                '-ExecutionPolicy',
                'Bypass',
                '-File',
                $pipelineSetup,
                '-ValidateOnly',
                '-ConfigPath',
                $pipelineConfig
            ) -TimeoutSeconds $setupValidatorTimeoutSeconds
        } finally {
            $env:PATH = $originalPath
        }

        if ($validateResult.StartError) {
            Write-Fail "Setup validator could not be started: $($validateResult.StartError)"
            $failed = $true
        } elseif ($validateResult.TimedOut) {
            Write-Fail "Setup validator timed out after $setupValidatorTimeoutSeconds second(s). Child process tree was terminated."
            $failed = $true
            $validateResult.Output | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
        } elseif ($validateResult.ExitCode -eq 0) {
            Write-Ok 'Setup validator completed successfully.'
        } else {
            Write-Fail "Setup validator reported issues with exit $($validateResult.ExitCode). Review output below."
            $failed = $true
            $validateResult.Output | ForEach-Object { Write-Host $_ }
        }
    }
} else {
    Write-Warn "Config not found yet: $pipelineConfig"
    Write-Host "Next step: run .\scripts\dev\setup.bat" -ForegroundColor DarkGray
}

Write-Section 'BDPGS OCR Readiness'
$convertBdpgs = Get-ConfigBoolValue -Config $configData -Key 'ConvertBdpgsToSrt' -Default $false
$configuredPgsTool = [string](Get-ConfigValue -Config $configData -Key 'BdpgsOcrToolPath' -Default 'Tools\PgsToSrt\PgsToSrt.exe')
$configuredPgsTessdata = [string](Get-ConfigValue -Config $configData -Key 'BdpgsOcrTessdataPath' -Default 'Tools\PgsToSrt\tessdata')
$resolvedPgsTool = Resolve-PipelineRelativePath -PathValue $configuredPgsTool
$resolvedPgsTessdata = Resolve-PipelineRelativePath -PathValue $configuredPgsTessdata
$resolvedPgsEnglishData = if ($resolvedPgsTessdata) { Join-Path $resolvedPgsTessdata 'eng.traineddata' } else { '' }

if ($convertBdpgs) {
    Write-Host 'BDPGS OCR is enabled in config.' -ForegroundColor DarkGray
    if ($resolvedPgsTool -and (Test-Path -LiteralPath $resolvedPgsTool -PathType Leaf)) {
        Write-Ok "PgsToSrt OCR tool: $resolvedPgsTool"
    } else {
        Write-Fail "BDPGS OCR is enabled, but PgsToSrt was not found: $configuredPgsTool"
        $failed = $true
    }

    if ([string]::IsNullOrWhiteSpace($configuredPgsTessdata)) {
        Write-Warn 'BDPGS OCR is enabled, but BdpgsOcrTessdataPath is blank. OCR will depend on tool/system defaults.'
    } elseif (Test-Path -LiteralPath $resolvedPgsTessdata -PathType Container) {
        Write-Ok "BDPGS tessdata folder: $resolvedPgsTessdata"
        if (Test-Path -LiteralPath $resolvedPgsEnglishData -PathType Leaf) {
            Write-Ok "BDPGS English language data: $resolvedPgsEnglishData"
        } else {
            Write-Fail "BDPGS tessdata is present, but eng.traineddata is missing: $resolvedPgsEnglishData"
            $failed = $true
        }
    } else {
        Write-Fail "BDPGS OCR is enabled, but tessdata was not found: $configuredPgsTessdata"
        $failed = $true
    }
} else {
    Write-Ok 'BDPGS OCR is disabled in config or no config exists; PgsToSrt is optional for this run mode.'
    if ((Test-Path -LiteralPath $bundledPgsToSrt -PathType Leaf) -and
        (Test-Path -LiteralPath $bundledPgsTessdata -PathType Container) -and
        (Test-Path -LiteralPath $bundledPgsEnglishData -PathType Leaf)) {
        Write-Ok "Bundled PgsToSrt and English tessdata are available: $bundledPgsToSrt"
    } else {
        Write-Warn 'Bundled PgsToSrt/tessdata are incomplete. This is only blocking if ConvertBdpgsToSrt is enabled.'
    }
}

Write-Section 'Optional Network Mode'
$networkRole = ([string](Get-ConfigValue -Config $configData -Key 'NetworkRole' -Default 'standalone')).Trim().ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($networkRole)) { $networkRole = 'standalone' }
$zeroconfAvailable = [bool]$pythonPackages['zeroconf']

if ($networkRole -eq 'standalone') {
    Write-Ok 'NetworkRole: standalone.'
    if ($zeroconfAvailable) {
        Write-Ok 'Optional zeroconf package is available.'
    } else {
        Write-Warn 'Optional zeroconf package is not installed. Standalone mode does not require it.'
    }
} elseif ($networkRole -in @('coordinator','worker')) {
    Write-Warn "NetworkRole is '$networkRole'. Network coordinator/worker mode is not part of the standalone release gate."
    if ($zeroconfAvailable) {
        Write-Ok 'zeroconf is available for experimental network discovery.'
    } else {
        Write-Fail "zeroconf is missing, but NetworkRole is '$networkRole'. Install it before testing network discovery."
        $failed = $true
    }
} else {
    Write-Fail "Unknown NetworkRole value: $networkRole"
    $failed = $true
}

Write-Section 'Summary'
if ($failed) {
    Write-Fail 'Release environment is not ready yet.'
    Write-Host 'Recommended order:' -ForegroundColor Yellow
    Write-Host '  1. Fix missing runtimes/tools above' -ForegroundColor Yellow
    Write-Host '  2. Run .\scripts\dev\setup.bat' -ForegroundColor Yellow
    Write-Host '  3. Re-run .\scripts\verify-env.bat' -ForegroundColor Yellow
    exit 1
}

Write-Ok 'Release environment looks ready.'
if (-not (Test-Path -LiteralPath $pipelineConfig)) {
    Write-Warn 'Config is still missing, so the pipeline itself is not fully ready until setup is run.'
}
