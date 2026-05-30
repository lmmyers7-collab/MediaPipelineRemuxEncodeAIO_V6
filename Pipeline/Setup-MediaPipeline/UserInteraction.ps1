# Dot-sourced helper slice for Setup-MediaPipeline.ps1. Keep CLI orchestration in the parent script.

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
