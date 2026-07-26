function Resolve-WebViewBrowserSmokePython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot
    )

    $candidates = @(
        (Join-Path $ProjectRoot 'apps\desktop\runtime\Python\python.exe'),
        (Join-Path $ProjectRoot 'ops\pipeline\runtime\Python\python.exe')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pathPython = Get-Command python -ErrorAction SilentlyContinue
    if ($pathPython) {
        Write-Warning "Using python from PATH for WebView browser smoke because bundled Python runtimes were not found: $($pathPython.Source)"
        return $pathPython.Source
    }

    throw 'No Python runtime was found. Expected apps\desktop\runtime\Python\python.exe, ops\pipeline\runtime\Python\python.exe, or python on PATH.'
}

function Get-WebViewBrowserSmokePrerequisites {
    param(
        [AllowNull()]
        [string]$PythonPath
    )

    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue | Select-Object -First 1
    $browserPath = $null
    foreach ($commandName in @('chrome', 'msedge', 'chromium')) {
        $browserCommand = Get-Command $commandName -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($browserCommand) {
            $browserPath = $browserCommand.Source
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($browserPath)) {
        foreach ($candidate in @(
            'C:\Program Files\Google\Chrome\Application\chrome.exe',
            'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
        )) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $browserPath = (Resolve-Path -LiteralPath $candidate).Path
                break
            }
        }
    }

    return [ordered]@{
        python = [ordered]@{
            available = -not [string]::IsNullOrWhiteSpace($PythonPath)
            path = $PythonPath
        }
        node = [ordered]@{
            available = $null -ne $nodeCommand
            path = if ($nodeCommand) { $nodeCommand.Source } else { $null }
        }
        browser = [ordered]@{
            available = -not [string]::IsNullOrWhiteSpace($browserPath)
            path = $browserPath
        }
    }
}

function Get-WebViewDirectSmokePrerequisites {
    param(
        [AllowNull()]
        [string]$PythonPath
    )

    $allPrerequisites = Get-WebViewBrowserSmokePrerequisites -PythonPath $PythonPath
    return [ordered]@{
        python = $allPrerequisites.python
        node = $allPrerequisites.node
    }
}

function Write-WebViewBrowserSmokeResult {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Result
    )

    Write-Output ($Result | ConvertTo-Json -Depth 6 -Compress)
}

function Get-WebViewBrowserSmokeMissingPrerequisites {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Prerequisites
    )

    return @(
        $Prerequisites.Keys |
            Where-Object { -not [bool]$Prerequisites[$_].available } |
            ForEach-Object { [string]$_ }
    )
}

function Invoke-WebViewBrowserSmokeUnittest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string]$Module,

        [switch]$AllowSkippedTests,

        [switch]$NodeOnly,

        [ValidateRange(1, 3600)]
        [int]$TimeoutSeconds = 600
    )

    try {
        $python = Resolve-WebViewBrowserSmokePython -ProjectRoot $ProjectRoot
    }
    catch {
        $failedPrerequisites = if ($NodeOnly) {
            Get-WebViewDirectSmokePrerequisites -PythonPath $null
        } else {
            Get-WebViewBrowserSmokePrerequisites -PythonPath $null
        }
        Write-WebViewBrowserSmokeResult -Result ([ordered]@{
            schema_version = 1
            kind = if ($NodeOnly) { 'webview_smoke' } else { 'webview_browser_smoke' }
            module = $Module
            outcome = 'prerequisite_failed'
            wrapper_exit_code = 1
            test_exit_code = $null
            tests_run = 0
            skipped_count = 0
            allow_skipped_tests = [bool]$AllowSkippedTests
            reason_category = if ($NodeOnly) { 'missing_node_prerequisite' } else { 'missing_browser_prerequisite' }
            reason = [string]$_.Exception.Message
            missing_prerequisites = (Get-WebViewBrowserSmokeMissingPrerequisites -Prerequisites $failedPrerequisites)
            prerequisites = $failedPrerequisites
        })
        Write-Error $_
        exit 1
    }
    $prerequisites = if ($NodeOnly) {
        Get-WebViewDirectSmokePrerequisites -PythonPath $python
    } else {
        Get-WebViewBrowserSmokePrerequisites -PythonPath $python
    }
    $missingPrerequisites = Get-WebViewBrowserSmokeMissingPrerequisites -Prerequisites $prerequisites
    Write-Host "Python: $python"

    Push-Location -LiteralPath $ProjectRoot
    $previousPythonPath = $env:PYTHONPATH
    $previousDontWriteBytecode = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $srcPath = Join-Path $ProjectRoot 'src'
        $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($previousPythonPath)) { $srcPath } else { "$srcPath;$previousPythonPath" }
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = $python
        $processInfo.Arguments = "-m unittest $Module -q"
        $processInfo.WorkingDirectory = $ProjectRoot
        $processInfo.UseShellExecute = $false
        $processInfo.RedirectStandardOutput = $true
        $processInfo.RedirectStandardError = $true
        $processInfo.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = $env:PYTHONDONTWRITEBYTECODE
        $processInfo.EnvironmentVariables['PYTHONPATH'] = $env:PYTHONPATH

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        [void]$process.Start()
        # Drain both redirected streams concurrently. Reading stdout to EOF before
        # stderr can deadlock whenever a chatty browser/backend fills the stderr
        # pipe while the parent is still waiting on stdout.
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
        if ($timedOut) {
            try {
                $process.Kill($true)
            }
            catch {
                try { $process.Kill() } catch { }
            }
            $process.WaitForExit()
        }
        else {
            # Ensure asynchronous stream readers have observed process closure.
            $process.WaitForExit()
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        if ($timedOut) {
            $stderr = "$stderr`nBrowser smoke process timed out after $TimeoutSeconds seconds."
        }
        $exitCode = if ($timedOut) { 124 } else { $process.ExitCode }

        $output = @()
        foreach ($streamText in @($stdout, $stderr)) {
            if (-not [string]::IsNullOrWhiteSpace($streamText)) {
                $output += @($streamText -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
            }
        }
        $output | ForEach-Object { Write-Host $_ }
        $testsRun = 0
        $skippedCount = 0
        foreach ($line in $output) {
            if ($line -match '\bRan\s+(\d+)\s+tests?\b') {
                $testsRun = [int]$Matches[1]
            }
            if ($line -match '\bskipped=(\d+)\b') {
                $skippedCount = [Math]::Max($skippedCount, [int]$Matches[1])
            }
        }

        $wrapperExitCode = 0
        $outcome = 'passed'
        if ($timedOut) {
            $wrapperExitCode = 124
            $outcome = 'timed_out'
        }
        elseif ($exitCode -ne 0) {
            $wrapperExitCode = $exitCode
            $outcome = 'failed'
        }
        elseif ($testsRun -eq 0) {
            $wrapperExitCode = 1
            $outcome = 'no_tests'
        }
        elseif ($skippedCount -gt 0 -and -not $AllowSkippedTests) {
            $wrapperExitCode = 1
            $outcome = 'skipped_disallowed'
        }
        elseif ($skippedCount -gt 0) {
            $outcome = 'skipped_allowed'
        }

        $reasonCategory = $null
        $reason = $null
        if ($missingPrerequisites.Count -gt 0) {
            $reasonCategory = if ($NodeOnly) { 'missing_node_prerequisite' } else { 'missing_browser_prerequisite' }
            $reason = 'Required WebView smoke prerequisites were unavailable: ' + ($missingPrerequisites -join ', ')
        }
        elseif ($outcome -eq 'skipped_disallowed' -or $outcome -eq 'skipped_allowed') {
            $reasonCategory = 'test_reported_skip'
            $reason = "The browser test reported $skippedCount skipped test(s); this is not passing evidence."
        }
        elseif ($outcome -eq 'no_tests') {
            $reasonCategory = 'no_tests_discovered'
            $reason = 'The browser smoke discovered zero tests.'
        }
        elseif ($outcome -eq 'timed_out') {
            $reasonCategory = 'harness_timeout'
            $reason = "The browser test process exceeded its bounded $TimeoutSeconds-second timeout and was terminated."
        }
        elseif ($outcome -eq 'failed') {
            $reasonCategory = 'test_failure'
            $reason = "The browser test process exited with code $exitCode."
        }

        Write-WebViewBrowserSmokeResult -Result ([ordered]@{
            schema_version = 1
            kind = if ($NodeOnly) { 'webview_smoke' } else { 'webview_browser_smoke' }
            module = $Module
            outcome = $outcome
            wrapper_exit_code = $wrapperExitCode
            test_exit_code = $exitCode
            tests_run = $testsRun
            skipped_count = $skippedCount
            allow_skipped_tests = [bool]$AllowSkippedTests
            timeout_seconds = $TimeoutSeconds
            process_timed_out = $timedOut
            reason_category = $reasonCategory
            reason = $reason
            missing_prerequisites = $missingPrerequisites
            prerequisites = $prerequisites
        })

        if ($exitCode -ne 0) {
            exit $exitCode
        }
        if ($testsRun -eq 0) {
            Write-Error 'Browser smoke discovered zero tests.'
            exit 1
        }
        if (-not $AllowSkippedTests -and $skippedCount -gt 0) {
            $installGuidance = if ($NodeOnly) { 'Install Node.js' } else { 'Install Node.js and Chrome/Edge' }
            Write-Error ("WebView smoke reported $skippedCount skipped test(s). $installGuidance, or rerun with -AllowSkippedTests for local diagnostics.")
            exit 1
        }
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousDontWriteBytecode
        Pop-Location
    }
}

function Invoke-WebViewDirectSmokeUnittest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string]$Module,

        [switch]$AllowSkippedTests,

        [ValidateRange(1, 3600)]
        [int]$TimeoutSeconds = 600
    )

    Invoke-WebViewBrowserSmokeUnittest `
        -ProjectRoot $ProjectRoot `
        -Module $Module `
        -AllowSkippedTests:$AllowSkippedTests `
        -NodeOnly `
        -TimeoutSeconds $TimeoutSeconds
}
