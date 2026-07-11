# Extracted from ops/scripts/release/test.ps1. Responsibility: release command execution, assertions, and primitive conversions

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

function Record-ReleaseGateSkip {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [switch]$Required
    )

    $script:SkippedGates += $Message
    if ($Required) {
        Write-Fail $Message
        $script:Failed = $true
    } else {
        Write-Warn $Message
    }
}

function Resolve-ReleasePowerShell {
    param([Parameter(Mandatory = $true)][string]$Root)

    $bundled = Join-Path $Root 'ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        return (Resolve-Path -LiteralPath $bundled).Path
    }

    $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }

    return $null
}

function Test-PowerShellParse {
    param([Parameter(Mandatory = $true)][string]$Path)

    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) {
        throw "PowerShell parse failed for ${Path}: $($errors[0])"
    }
}

function Invoke-ReleaseScriptProcess {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$Arguments = @(),
        [int]$TimeoutSeconds = 600
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $script:Pwsh
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    foreach ($argument in @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) + $Arguments) {
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

        try { $stdout = $stdoutTask.GetAwaiter().GetResult() } catch { $stdout = "[release-check stdout read failed] $($_.Exception.Message)" }
        try { $stderr = $stderrTask.GetAwaiter().GetResult() } catch { $stderr = "[release-check stderr read failed] $($_.Exception.Message)" }

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

function Invoke-ReleaseScriptCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$Arguments = @(),
        [switch]$Required,
        [switch]$ShowWarningsOnSuccess,
        [switch]$FailOnSkipOutput,
        [int]$TimeoutSeconds = 600
    )

    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
        if ($Required) {
            Write-Fail "$Label script is missing: $ScriptPath"
            $script:Failed = $true
        } else {
            Record-ReleaseGateSkip "$Label skipped; script is not present: $ScriptPath"
        }
        return
    }

    Write-Host "Running $Label (timeout ${TimeoutSeconds}s)..." -ForegroundColor DarkGray
    $result = Invoke-ReleaseScriptProcess -ScriptPath $ScriptPath -Arguments $Arguments -TimeoutSeconds $TimeoutSeconds
    $output = @($result.Output)

    if ($result.StartError) {
        Write-Fail "$Label could not be started: $($result.StartError)"
        $script:Failed = $true
        return
    }

    if ($result.TimedOut) {
        Write-Fail "$Label timed out after $TimeoutSeconds second(s). Child process tree was terminated."
        $script:Failed = $true
        $output | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
        return
    }

    $exitCode = $result.ExitCode
    if ($exitCode -eq 0) {
        $skipOutput = @($output | Where-Object {
            $_ -match '^SKIP:' -or
            $_ -match '\bskipped=\d+\b' -or
            $_ -match '^OK \(skipped=\d+\)'
        })
        if ($FailOnSkipOutput -and $skipOutput.Count -gt 0) {
            Write-Fail "$Label reported skipped coverage."
            $script:Failed = $true
            $skipOutput | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
            return
        }
        if ($ShowWarningsOnSuccess) {
            $output | Where-Object { $_ -match '^\[WARN\]' } | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
        }
        Write-Ok "$Label passed."
        return
    }

    Write-Fail "$Label failed with exit $exitCode."
    $script:Failed = $true
    $output | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
}

function Invoke-PythonModuleCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Module,
        [string[]]$Arguments = @(),
        [switch]$Required
    )

    if (-not (Test-Path -LiteralPath $script:Python -PathType Leaf)) {
        if ($Required) {
            Write-Fail "$Label requires bundled desktop Python: $script:Python"
            $script:Failed = $true
        } else {
            Record-ReleaseGateSkip "$Label skipped; bundled desktop Python is missing: $script:Python"
        }
        return
    }

    Write-Host "Running $Label..." -ForegroundColor DarkGray
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $script:BundleRoot 'src'
        Push-Location -LiteralPath $script:BundleRoot
        $output = & $script:Python -m $Module @Arguments 2>&1 | ForEach-Object { [string]$_ }
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0) {
            Write-Ok "$Label passed."
        } elseif ($Required) {
            Write-Fail "$Label failed with exit $exitCode."
            $script:Failed = $true
            $output | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
        } else {
            Record-ReleaseGateSkip "$Label reported issues (advisory in this context; exit $exitCode)."
            $output | Select-Object -Last 40 | ForEach-Object { Write-Host $_ }
        }
    } finally {
        Pop-Location
        $env:PYTHONPATH = $previousPythonPath
    }
}

function Invoke-PythonUnittestDiscovery {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [switch]$Required
    )

    $testRoot = Join-Path $script:BundleRoot $RelativePath
    if (-not (Test-Path -LiteralPath $testRoot -PathType Container)) {
        if ($Required) {
            Write-Fail "$Label tests are required but missing: $testRoot"
            $script:Failed = $true
        } else {
            Record-ReleaseGateSkip "$Label tests skipped; tests are not present: $testRoot"
        }
        return
    }

    Invoke-PythonModuleCheck -Label "$Label unit tests" -Module 'unittest' -Arguments @('discover', '-s', $RelativePath, '-p', 'test_*.py') -Required:$Required
}

function Get-ObjectPropertyValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name,
        $Default = $null
    )

    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $Default
}

function ConvertTo-ReleaseBool {
    param(
        $Value,
        [bool]$Default = $false
    )

    if ($Value -is [bool]) { return [bool]$Value }
    if ($null -eq $Value) { return $Default }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes','y','on')) { return $true }
    if ($text -in @('false','0','no','n','off')) { return $false }
    return $Default
}

function Import-MediaPipelineReleasePolicy {
    $policyPath = Join-Path $script:BundleRoot 'ops\scripts\release\release_policy.ps1'
    if (-not (Test-Path -LiteralPath $policyPath -PathType Leaf)) {
        Write-Fail "Release policy module missing: $policyPath"
        $script:Failed = $true
        return $false
    }

    try {
        . $policyPath
        return $true
    } catch {
        Write-Fail "Release policy module could not be loaded: $($_.Exception.Message)"
        $script:Failed = $true
        return $false
    }
}

function Assert-ReleasePathAbsent {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $full = Join-Path $script:BundleRoot $RelativePath
    if (Test-Path -LiteralPath $full) {
        Write-Fail "$Label should be absent from a clean release: $RelativePath"
        $script:Failed = $true
    } else {
        Write-Ok "$Label absent: $RelativePath"
    }
}

function Assert-ReleasePathPresent {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $full = Join-Path $script:BundleRoot $RelativePath
    if (Test-Path -LiteralPath $full -PathType Leaf) {
        Write-Ok "$Label present: $RelativePath"
    } else {
        Write-Fail "$Label should be present in this release: $RelativePath"
        $script:Failed = $true
    }
}

function Assert-ReleasePatternAbsent {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePattern,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $pattern = Join-Path $script:BundleRoot $RelativePattern
    $matches = @(Get-ChildItem -Path $pattern -Force -ErrorAction SilentlyContinue)
    if ($matches.Count -gt 0) {
        Write-Fail "$Label should be absent from a clean release: $RelativePattern"
        $matches | Select-Object -First 8 | ForEach-Object { Write-Host "  $($_.FullName)" }
        if ($matches.Count -gt 8) { Write-Host ("  ...and {0} more" -f ($matches.Count - 8)) }
        $script:Failed = $true
    } else {
        Write-Ok "$Label absent: $RelativePattern"
    }
}

function Test-ReleaseMapContainsKey {
    param(
        $Map,
        [Parameter(Mandatory = $true)][string]$Key
    )

    if ($null -eq $Map) { return $false }
    try { return [bool]$Map.Contains($Key) } catch { return $false }
}

function ConvertTo-ReleaseStringArray {
    param($Value)

    if ($null -eq $Value) { return @() }
    return @($Value | ForEach-Object { [string]$_ })
}

function Test-ReleaseStringArrayEquals {
    param(
        $Actual,
        $Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $actualValues = @(ConvertTo-ReleaseStringArray -Value $Actual)
    $expectedValues = @(ConvertTo-ReleaseStringArray -Value $Expected)
    if ($actualValues.Count -ne $expectedValues.Count) {
        Write-Fail "$Label count drifted. Actual=$($actualValues.Count) Expected=$($expectedValues.Count)"
        $script:Failed = $true
        return $false
    }

    for ($i = 0; $i -lt $expectedValues.Count; $i++) {
        if ([string]$actualValues[$i] -cne [string]$expectedValues[$i]) {
            Write-Fail "$Label drifted at index $i. Actual='$($actualValues[$i])' Expected='$($expectedValues[$i])'"
            $script:Failed = $true
            return $false
        }
    }

    return $true
}
