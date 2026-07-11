# Audit media-file scanning loop.

function Invoke-AuditProbeBatch {
    param(
        [array] $MediaFiles = @(),
        [Parameter(Mandatory)] [string] $FfprobePath,
        [ValidateRange(1, 8)] [int] $Concurrency = 2,
        [ValidateRange(5, 3600)] [int] $TimeoutSeconds = 60
    )

    $probeByPath = @{}
    $missFileByPath = @{}
    $misses = [System.Collections.Generic.List[object]]::new()
    foreach ($file in @($MediaFiles)) {
        $identity = Get-ProbeCacheIdentity -FileInfo $file
        $cached = Get-ProbeCacheEntry -FileInfo $file -Identity $identity
        if ($null -ne $cached) {
            $probeByPath[[string]$file.FullName] = $cached
            continue
        }
        $misses.Add([pscustomobject]@{ FileInfo = $file; Identity = $identity }) | Out-Null
        $missFileByPath[[string]$file.FullName] = $file
    }
    if ($misses.Count -eq 0) { return $probeByPath }

    Write-AuditProgress -Status 'scanning' -ProcessedFiles 0 -TotalFiles $MediaFiles.Count -CurrentOperation "Probing $($misses.Count) uncached media file(s) with $Concurrency worker(s)."
    $rawResults = @(
        $misses | ForEach-Object -ThrottleLimit $Concurrency -Parallel {
            $entry = $_
            $filePath = [string]$entry.FileInfo.FullName
            $result = [ordered]@{
                Path = $filePath
                Identity = [string]$entry.Identity
                Success = $false
                Error = ''
                Json = ''
                TimedOut = $false
            }
            $process = $null
            try {
                $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
                $startInfo.FileName = $using:FfprobePath
                $startInfo.UseShellExecute = $false
                $startInfo.CreateNoWindow = $true
                $startInfo.RedirectStandardOutput = $true
                $startInfo.RedirectStandardError = $true
                foreach ($argument in @(
                    '-v', 'error',
                    '-show_entries', 'format=format_name,duration:stream=index,codec_type,codec_name,codec_long_name,codec_tag_string,codec_tag,channels:stream_tags=language,title:stream_disposition=default,forced',
                    '-of', 'json',
                    '--', $filePath
                )) {
                    [void]$startInfo.ArgumentList.Add([string]$argument)
                }
                $process = [System.Diagnostics.Process]::new()
                $process.StartInfo = $startInfo
                if (-not $process.Start()) { throw 'ffprobe did not start' }
                $stdoutTask = $process.StandardOutput.ReadToEndAsync()
                $stderrTask = $process.StandardError.ReadToEndAsync()
                if (-not $process.WaitForExit($using:TimeoutSeconds * 1000)) {
                    $result.TimedOut = $true
                    try { $process.Kill($true) } catch {}
                    try { $process.WaitForExit(5000) | Out-Null } catch {}
                    $result.Error = "ffprobe timed out after $($using:TimeoutSeconds)s"
                } else {
                    $stdout = $stdoutTask.GetAwaiter().GetResult()
                    $stderr = $stderrTask.GetAwaiter().GetResult()
                    if ($process.ExitCode -eq 0) {
                        $result.Success = $true
                        $result.Json = [string]$stdout
                    } else {
                        $result.Error = if ([string]::IsNullOrWhiteSpace($stderr)) { "ffprobe exited with code $($process.ExitCode)" } else { [string]$stderr }
                    }
                }
            } catch {
                $result.Error = [string]$_.Exception.Message
            } finally {
                if ($null -ne $process) { $process.Dispose() }
            }
            [pscustomobject]$result
        }
    )

    foreach ($raw in $rawResults) {
        $probe = $null
        if ([bool]$raw.Success) {
            try {
                $data = ([string]$raw.Json | ConvertFrom-Json -ErrorAction Stop)
                $probe = @{ Success = $true; Error = ''; Data = $data; CacheHit = $false }
                $file = $missFileByPath[[string]$raw.Path]
                Save-ProbeCacheEntry -FileInfo $file -ProbeData $data -Identity ([string]$raw.Identity)
            } catch {
                $probe = @{ Success = $false; Error = "ffprobe returned invalid JSON: $($_.Exception.Message)"; Data = $null; CacheHit = $false }
            }
        } else {
            $probe = @{ Success = $false; Error = [string]$raw.Error; Data = $null; CacheHit = $false }
        }
        $probeByPath[[string]$raw.Path] = $probe
    }
    return $probeByPath
}

function Invoke-AuditFileScan {
    param(
        [array]$MediaFiles = @(),
        [Parameter(Mandatory)] [string]$LibraryRoot
    )

    $results = [System.Collections.Generic.List[object]]::new()
    $total = $MediaFiles.Count
    $index = 0
    $script:AuditProgressTotal = $total
    $script:AuditProgressProcessed = 0
    $prefetchedProbes = if ($total -gt 0 -and [int]$script:AuditProbeConcurrency -gt 1) {
        Invoke-AuditProbeBatch -MediaFiles $MediaFiles -FfprobePath $script:FfprobePath -Concurrency $script:AuditProbeConcurrency -TimeoutSeconds $FfprobeTimeoutSeconds
    } else {
        @{}
    }

    foreach ($file in $MediaFiles) {
        $index++
        Write-AuditScanProgress -Index $index -Total $total -FileInfo $file
        try {
            $prefetchedProbe = if ($prefetchedProbes.ContainsKey([string]$file.FullName)) { $prefetchedProbes[[string]$file.FullName] } else { $null }
            $results.Add((Get-AuditResultForFile -FileInfo $file -ProbeResult $prefetchedProbe)) | Out-Null
        } catch {
            $failedResult = New-AuditResult -FileInfo $file -RelativePath (Get-RelativePathSafe -RootPath $LibraryRoot -FullPath $file.FullName)
            $lineNumber = $null
            if ($_.InvocationInfo -and $_.InvocationInfo.ScriptLineNumber) {
                $lineNumber = $_.InvocationInfo.ScriptLineNumber
            }
            $detail = if ($lineNumber) {
                "Audit failed while processing '$($file.FullName)' at line ${lineNumber}: $($_.Exception.Message)"
            } else {
                "Audit failed while processing '$($file.FullName)': $($_.Exception.Message)"
            }
            Write-AuditLog $detail 'ERROR'
            Add-AuditIssue -Result $failedResult -Bucket 'REVIEW' -Code 'audit-internal-error' -Message $detail -SuggestedAction 'Keep the file for review and inspect the audit script or rerun against this file after the next patch.'
            $results.Add($failedResult) | Out-Null
        }
        $script:AuditProgressProcessed = $index
    }

    Complete-AuditConsoleProgress
    return @($results)
}
