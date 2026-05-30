# Dot-sourced helper slice for Setup-MediaPipeline.ps1. Keep CLI orchestration in the parent script.

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
