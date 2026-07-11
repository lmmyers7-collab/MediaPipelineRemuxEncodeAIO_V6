# Extracted from ops/pipeline/entrypoints/Invoke-RerunCsv.ps1. Responsibility: command, file transfer, configuration, and journal support

function Write-RerunLog {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
}

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    Write-RerunLog -Message $Message -Level $Level
}

function DebugLog {
    param([string]$Message)
    Write-RerunLog -Message $Message -Level 'DEBUG'
}

function Get-RerunValue {
    param($Row, [string[]]$Names, [string]$Default = '')
    foreach ($name in $Names) {
        $prop = $Row.PSObject.Properties[$name]
        if ($prop -and -not [string]::IsNullOrWhiteSpace([string]$prop.Value)) {
            return ([string]$prop.Value).Trim()
        }
    }
    return $Default
}

function ConvertTo-RerunBool {
    param($Value, [bool]$Default = $false)
    if ($null -eq $Value) { return $Default }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($text)) { return $Default }
    return @('1','true','yes','y','on','enabled','run') -contains $text
}

function Resolve-RerunChoice {
    param(
        $Row,
        [string[]]$Names,
        [string]$Default,
        [string[]]$Allowed
    )
    $value = (Get-RerunValue -Row $Row -Names $Names -Default $Default).Trim().ToLowerInvariant()
    $value = $value -replace '\s+', '_'
    if ($Allowed -contains $value) { return $value }
    return $Default
}

function Normalize-RerunChoiceValue {
    param([string]$Value)
    return (([string]$Value).Trim().ToLowerInvariant() -replace '\s+', '_')
}

function Resolve-RerunPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if ([System.IO.Path]::IsPathRooted($expanded)) {
        return [System.IO.Path]::GetFullPath($expanded)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $expanded))
}

function Resolve-RerunSourcePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    if (-not (Test-RerunSourcePathFullyQualified $expanded)) { return '' }
    return [System.IO.Path]::GetFullPath($expanded)
}

function Test-RerunSourcePathFullyQualified {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path)
    try {
        return [System.IO.Path]::IsPathFullyQualified($expanded)
    } catch {
        if (-not [System.IO.Path]::IsPathRooted($expanded)) { return $false }
        return ($expanded -notmatch '^[A-Za-z]:[^\\/]')
    }
}

function Get-RerunValidExtensionSet {
    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($item in @($script:ValidExtensions)) {
        $text = ([string]$item).Trim()
        if ([string]::IsNullOrWhiteSpace($text)) { continue }
        if (-not $text.StartsWith('.')) { $text = ".$text" }
        [void]$set.Add($text.ToLowerInvariant())
    }
    return $set
}

function Test-RerunValidMediaExtension {
    param([string]$Path)
    $extension = [System.IO.Path]::GetExtension($Path)
    if ([string]::IsNullOrWhiteSpace($extension)) { return $false }
    $valid = Get-RerunValidExtensionSet
    if ($valid.Count -eq 0) { return $false }
    return $valid.Contains($extension.ToLowerInvariant())
}

function Test-RerunUncPath {
    param([string]$Path)
    return (-not [string]::IsNullOrWhiteSpace($Path) -and ($Path.StartsWith('\\') -or $Path.StartsWith('//')))
}

function Get-RerunUncShareRoot {
    param([string]$Path)
    if (-not (Test-RerunUncPath $Path)) { return $null }
    $normalized = $Path -replace '/', '\'
    if ($normalized -match '^(\\\\[^\\]+\\[^\\]+)') {
        return ($Matches[1].TrimEnd('\') + '\')
    }
    return $null
}

function Get-RerunFreeSpaceGB {
    param([string]$Path, [int]$TimeoutSeconds = 10)
    if ([string]::IsNullOrWhiteSpace($Path)) { return -1 }
    if (Test-RerunUncPath $Path) {
        $probe = Get-RerunUncShareRoot $Path
        if ([string]::IsNullOrWhiteSpace($probe)) { return -1 }
        $job = Start-Job -ScriptBlock {
            param($ProbePath, $TypeDefinition)
            try {
                if (-not ('MediaPipeline.RerunDiskSpace' -as [type])) {
                    Add-Type -TypeDefinition $TypeDefinition -Language CSharp
                }
                [uint64]$freeAvail = 0
                [uint64]$totalBytes = 0
                [uint64]$totalFree = 0
                $ok = [MediaPipeline.RerunDiskSpace]::GetDiskFreeSpaceExW(
                    $ProbePath, [ref]$freeAvail, [ref]$totalBytes, [ref]$totalFree)
                if (-not $ok) { return -1 }
                return [math]::Round($freeAvail / 1GB, 2)
            } catch {
                return -1
            }
        } -ArgumentList $probe, $script:RerunDiskSpaceTypeDefinition
        try {
            if (Wait-Job $job -Timeout $TimeoutSeconds) {
                $result = Receive-Job $job -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($null -ne $result) { return [double]$result }
            }
            Stop-Job $job -ErrorAction SilentlyContinue
            return -1
        } finally {
            Remove-Job $job -Force -ErrorAction SilentlyContinue
        }
    }
    if ($Path -match '^([A-Za-z]):[/\\]?') {
        try {
            $di = [System.IO.DriveInfo]::new($Matches[1])
            return [math]::Round($di.AvailableFreeSpace / 1GB, 2)
        } catch {
            return -1
        }
    }
    return -1
}

function Resolve-RerunRobocopyPath {
    $systemRoot = if ($env:SystemRoot) { [string]$env:SystemRoot } else { [string]$env:windir }
    if ([string]::IsNullOrWhiteSpace($systemRoot)) { return '' }
    $candidate = Join-Path $systemRoot 'System32\robocopy.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    return ''
}

function Copy-RerunFileVerified {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Destination,
        [int]$MaxRetries = 3
    )
    $robocopy = Resolve-RerunRobocopyPath
    if ([string]::IsNullOrWhiteSpace($robocopy)) {
        throw 'robocopy.exe was not found at the expected System32 path'
    }
    $srcItem = Get-Item -LiteralPath $Source -ErrorAction Stop
    if (-not ($srcItem -is [System.IO.FileInfo])) { throw "source path is not a file: $Source" }

    $srcDir = Split-Path -Parent $Source
    $srcLeaf = Split-Path -Leaf $Source
    $dstDir = Split-Path -Parent $Destination
    $dstLeaf = Split-Path -Leaf $Destination
    if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
    if (Test-Path -LiteralPath $Destination) { throw "stage path already exists: $Destination" }

    $freeGB = Get-RerunFreeSpaceGB -Path $dstDir
    $requiredGB = ([double]$srcItem.Length / 1GB) + 0.5
    if ($freeGB -lt 0) {
        throw "unable to determine free space for rerun stage destination: $dstDir"
    }
    if ($freeGB -lt $requiredGB) {
        throw ("insufficient free space at rerun stage destination: {0:N2} GB free, need {1:N2} GB" -f $freeGB, $requiredGB)
    }

    $stagingRoot = Join-Path $dstDir '.mediapipeline-rerun-staging'
    if (-not (Test-Path -LiteralPath $stagingRoot)) { New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null }
    $flags = if ($script:RerunRobocopyFlags) { @($script:RerunRobocopyFlags) } else { @('/J', '/R:3', '/W:15', '/MT:2', '/NP', '/NDL', '/NFL') }
    $timeoutSeconds = if ($script:RerunRobocopyTimeoutSeconds -gt 0) { [int]$script:RerunRobocopyTimeoutSeconds } else { 14400 }

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $copyId = [guid]::NewGuid().ToString('N')
        $attemptDir = Join-Path $stagingRoot $copyId
        $landed = Join-Path $attemptDir $srcLeaf
        $partial = Join-Path $dstDir "$dstLeaf.rerun-partial.$copyId"
        try {
            New-Item -ItemType Directory -Path $attemptDir -Force | Out-Null
            Write-RerunLog "STAGE COPY attempt $attempt/${MaxRetries}: $srcLeaf -> $Destination" "INFO"
            $result = Invoke-RerunNativeCommand -FilePath $robocopy -ArgumentList (@($srcDir, $attemptDir, $srcLeaf) + $flags + @('/DCOPY:DA')) -TimeoutSeconds $timeoutSeconds -Label 'robocopy-rerun-stage'
            if ($result.TimedOut) {
                Write-RerunLog "Rerun stage robocopy timed out after ${timeoutSeconds}s for $Source" "ERROR"
            }
            if ([int]$result.ExitCode -in @(0, 1, 3)) {
                $dstSize = (Get-Item -LiteralPath $landed -ErrorAction Stop).Length
                if ([long]$dstSize -ne [long]$srcItem.Length) {
                    throw "staged copy size mismatch: source=$($srcItem.Length) staged=$dstSize"
                }
                [System.IO.File]::Move($landed, $partial)
                if (Test-Path -LiteralPath $Destination) {
                    throw "stage path appeared during copy: $Destination"
                }
                [System.IO.File]::Move($partial, $Destination)
                return $true
            }
            Write-RerunLog "Rerun stage robocopy failed with exit $($result.ExitCode): $($result.Error)" "WARN"
        } catch {
            Write-RerunLog "Rerun stage copy attempt $attempt failed: $($_.Exception.Message)" "WARN"
            Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
        } finally {
            Remove-Item -LiteralPath $attemptDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ($attempt -lt $MaxRetries) { Start-Sleep -Seconds 5 }
    }
    try {
        $children = @(Get-ChildItem -LiteralPath $stagingRoot -Force -ErrorAction SilentlyContinue)
        if ($children.Count -eq 0) { Remove-Item -LiteralPath $stagingRoot -Force -ErrorAction SilentlyContinue }
    } catch {}
    return $false
}

function Add-RerunCommandTail {
    param(
        [Parameter(Mandatory)] [System.Text.StringBuilder]$Builder,
        [AllowNull()] [string]$Text,
        [int]$MaxChars = 65536
    )
    if ($null -eq $Text) { return }
    [void]$Builder.AppendLine($Text)
    if ($Builder.Length -gt $MaxChars) {
        $remove = $Builder.Length - $MaxChars
        try { [void]$Builder.Remove(0, $remove) } catch {}
    }
}

function Invoke-RerunStreamingCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [array]$ArgumentList = @(),
        [int]$TimeoutSeconds = 0,
        [string]$Label = 'command'
    )
    $psi = [System.Diagnostics.ProcessStartInfo]@{
        FileName               = $FilePath
        UseShellExecute        = $false
        RedirectStandardError  = $true
        RedirectStandardOutput = $true
        CreateNoWindow         = $true
    }
    foreach ($arg in @($ArgumentList)) { [void]$psi.ArgumentList.Add([string]$arg) }

    $proc = $null
    $stdoutTask = $null
    $stderrTask = $null
    $stdoutTail = [System.Text.StringBuilder]::new()
    $stderrTail = [System.Text.StringBuilder]::new()
    $startedAt = Get-Date
    $timedOut = $false
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $stdoutTask = $proc.StandardOutput.ReadLineAsync()
        $stderrTask = $proc.StandardError.ReadLineAsync()
        while (-not $proc.HasExited) {
            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                Write-RerunLog "$Label timed out after ${TimeoutSeconds}s; killing process tree" "ERROR"
                Stop-RerunNativeProcessTree -Process $proc -Label $Label
                break
            }
            if ($stdoutTask -and $stdoutTask.IsCompleted) {
                $line = $stdoutTask.Result
                if ($null -ne $line) {
                    Add-RerunCommandTail -Builder $stdoutTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "INFO" }
                    $stdoutTask = $proc.StandardOutput.ReadLineAsync()
                }
            }
            if ($stderrTask -and $stderrTask.IsCompleted) {
                $line = $stderrTask.Result
                if ($null -ne $line) {
                    Add-RerunCommandTail -Builder $stderrTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "WARN" }
                    $stderrTask = $proc.StandardError.ReadLineAsync()
                }
            }
            Start-Sleep -Milliseconds 100
        }
        if ($timedOut) {
            try { $proc.WaitForExit(5000) | Out-Null } catch {}
        } else {
            try { $proc.WaitForExit() } catch {}
        }
        $drainUntil = (Get-Date).AddSeconds(2)
        foreach ($stream in @('stdout','stderr')) {
            $task = if ($stream -eq 'stdout') { $stdoutTask } else { $stderrTask }
            while ($task -and (Get-Date) -lt $drainUntil) {
                if (-not ($task.IsCompleted -or $task.Wait(100))) { continue }
                $line = $task.Result
                if ($null -eq $line) { break }
                if ($stream -eq 'stdout') {
                    Add-RerunCommandTail -Builder $stdoutTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "INFO" }
                    $task = $proc.StandardOutput.ReadLineAsync()
                    $stdoutTask = $task
                } else {
                    Add-RerunCommandTail -Builder $stderrTail -Text $line
                    if ($line.Trim()) { Write-RerunLog $line "WARN" }
                    $task = $proc.StandardError.ReadLineAsync()
                    $stderrTask = $task
                }
            }
        }
    } catch {
        return [pscustomobject]@{
            ExitCode = -2
            TimedOut = $false
            OutputTail = $stdoutTail.ToString()
            ErrorTail = "Failed to run ${Label}: $_"
        }
    }
    if ($timedOut) {
        Add-RerunCommandTail -Builder $stderrTail -Text "[KILLED: TIMEOUT after ${TimeoutSeconds}s]"
    }
    return [pscustomobject]@{
        ExitCode = if ($timedOut) { -1 } else { [int]$proc.ExitCode }
        TimedOut = $timedOut
        OutputTail = $stdoutTail.ToString()
        ErrorTail = $stderrTail.ToString()
    }
}

function ConvertTo-Psd1KeyLiteral {
    param([object]$Key)
    $text = [string]$Key
    $escaped = $text -replace "'", "''"
    return "'$escaped'"
}

function ConvertTo-Psd1Literal {
    param($Value, [int]$Indent = 0)
    $pad = ' ' * $Indent
    if ($null -eq $Value) { return '$null' }
    if ($Value -is [bool]) { return $(if ($Value) { '$true' } else { '$false' }) }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) {
        return ([string]$Value)
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $lines = [System.Collections.Generic.List[string]]::new()
        $lines.Add('@{')
        foreach ($key in $Value.Keys) {
            $safeKey = ConvertTo-Psd1KeyLiteral -Key $key
            $lines.Add(('{0}    {1} = {2}' -f $pad, $safeKey, (ConvertTo-Psd1Literal -Value $Value[$key] -Indent ($Indent + 4))))
        }
        $lines.Add("$pad}")
        return ($lines -join [Environment]::NewLine)
    }
    if ($Value -is [array]) {
        $items = @($Value | ForEach-Object { ConvertTo-Psd1Literal -Value $_ -Indent $Indent })
        return '@(' + ($items -join ', ') + ')'
    }
    $escaped = ([string]$Value) -replace "'", "''"
    return "'$escaped'"
}

function Copy-RerunConfigValue {
    param($Value)
    if ($null -eq $Value) { return $null }
    if ($Value -is [System.Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $copy[[string]$key] = Copy-RerunConfigValue -Value $Value[$key]
        }
        return $copy
    }
    if ($Value -is [array]) {
        return @($Value | ForEach-Object { Copy-RerunConfigValue -Value $_ })
    }
    return $Value
}

function Get-RerunProfileField {
    param($Profile, [string]$Name, [string]$Default = '')
    if ($Profile -is [System.Collections.IDictionary] -and $Profile.Contains($Name)) {
        return [string]$Profile[$Name]
    }
    $prop = $Profile.PSObject.Properties[$Name]
    if ($prop) { return [string]$prop.Value }
    return $Default
}

function Set-RerunProfileField {
    param($Profile, [string]$Name, $Value)
    if ($Profile -is [System.Collections.IDictionary]) {
        $Profile[$Name] = $Value
    }
}

function New-RerunLibraryProfiles {
    param(
        $Profiles,
        [string]$StageRoot,
        [string]$OutputRoot
    )

    $stageMoviesRoot = Join-Path $StageRoot 'Movies'
    $stageTvRoot = Join-Path $StageRoot 'TV'
    $rewritten = [System.Collections.Generic.List[object]]::new()
    foreach ($profile in @($Profiles)) {
        $copy = Copy-RerunConfigValue -Value $profile
        $id = (Get-RerunProfileField -Profile $copy -Name 'id').Trim().ToLowerInvariant()
        $designation = (Get-RerunProfileField -Profile $copy -Name 'designation').Trim().ToLowerInvariant()
        if ($designation -in @('mixed','custom','')) { $designation = 'auto' }

        if ($designation -eq 'movie' -or $id -eq 'movies') {
            Set-RerunProfileField -Profile $copy -Name 'source_path' -Value $stageMoviesRoot
            Set-RerunProfileField -Profile $copy -Name 'output_path' -Value $OutputRoot
            Set-RerunProfileField -Profile $copy -Name 'enabled' -Value $true
        } elseif ($designation -eq 'tv' -or $id -eq 'tv') {
            Set-RerunProfileField -Profile $copy -Name 'source_path' -Value $stageTvRoot
            Set-RerunProfileField -Profile $copy -Name 'output_path' -Value $OutputRoot
            Set-RerunProfileField -Profile $copy -Name 'enabled' -Value $true
        } else {
            Set-RerunProfileField -Profile $copy -Name 'enabled' -Value $false
        }
        Set-RerunProfileField -Profile $copy -Name 'promotion_enabled' -Value $false
        Set-RerunProfileField -Profile $copy -Name 'promotion_destination' -Value ''
        [void]$rewritten.Add($copy)
    }
    return @($rewritten)
}

function Move-RerunFileReplaceWithRetry {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Destination,
        [string]$Label = 'file replace',
        [int]$Attempts = 20,
        [int]$DelayMilliseconds = 250
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            [System.IO.File]::Move($Source, $Destination, $true)
            return
        } catch {
            if ($attempt -ge $Attempts) { throw }
            $message = if ($_.Exception -and $_.Exception.Message) { [string]$_.Exception.Message } else { [string]$_ }
            Write-RerunLog "$Label replace attempt $attempt/$Attempts failed; retrying: $message" "WARN"
            Start-Sleep -Milliseconds $DelayMilliseconds
        }
    }
}

function Write-RerunTempConfig {
    param(
        [hashtable]$Config,
        [string]$Path
    )
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('@{')
    foreach ($key in ($Config.Keys | Sort-Object)) {
        $safeKey = ConvertTo-Psd1KeyLiteral -Key $key
        $lines.Add(('    {0} = {1}' -f $safeKey, (ConvertTo-Psd1Literal -Value $Config[$key] -Indent 4)))
    }
    $lines.Add('}')

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    [System.IO.File]::WriteAllText($tmp, ($lines -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
    Move-RerunFileReplaceWithRetry -Source $tmp -Destination $Path -Label 'CSV rerun temp config'
}

function Write-RerunManifest {
    param(
        [string]$Path,
        $Payload
    )
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    $json = $Payload | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
    Move-RerunFileReplaceWithRetry -Source $tmp -Destination $Path -Label 'CSV rerun manifest'
}

function Get-RerunJsonLineMutexName {
    param([Parameter(Mandatory)] [string]$Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes([System.IO.Path]::GetFullPath($Path).ToLowerInvariant())
        $hash = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '').Substring(0, 16)
        return "Global\MediaPipelineRerunCompletedManifest_$hash"
    } finally {
        if ($sha) { $sha.Dispose() }
    }
}

function Write-RerunJsonLineAppend {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] $Payload,
        [int]$Depth = 10
    )
    $mutex = $null
    $acquired = $false
    try {
        $dir = Split-Path -Parent $Path
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $mutex = [System.Threading.Mutex]::new($false, (Get-RerunJsonLineMutexName -Path $Path))
        $acquired = $mutex.WaitOne(2000)
        if (-not $acquired) { return $false }
        $line = $Payload | ConvertTo-Json -Depth $Depth -Compress
        [System.IO.File]::AppendAllText($Path, $line + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
        return $true
    } catch {
        Write-RerunLog "CSV rerun JSONL append failed for $Path : $($_.Exception.Message)" "WARN"
        return $false
    } finally {
        if ($acquired -and $null -ne $mutex) {
            try { $mutex.ReleaseMutex() } catch {}
        }
        if ($null -ne $mutex) { $mutex.Dispose() }
    }
}

function Add-RerunCompletedJobsManifestEntry {
    param(
        [Parameter(Mandatory)] [string]$OutputPath,
        [Parameter(Mandatory)] $Payload
    )
    if ([string]::IsNullOrWhiteSpace([string]$script:RerunCompletedJobsManifest)) {
        Write-RerunLog "Completed-jobs manifest append skipped; manifest path is unavailable for $OutputPath" "WARN"
        return $false
    }
    try {
        $entry = [ordered]@{}
        if ($Payload -is [System.Collections.IDictionary]) {
            foreach ($k in $Payload.Keys) { $entry[[string]$k] = $Payload[$k] }
        } else {
            foreach ($prop in @($Payload.PSObject.Properties)) { $entry[$prop.Name] = $prop.Value }
        }
        if (-not $entry.Contains('schema_version')) { $entry['schema_version'] = 'completed_job.v1' }
        $entry['output_path'] = $OutputPath
        $entry['output_file'] = Split-Path -Leaf $OutputPath
        if (-not $entry.Contains('job_id')) { $entry['job_id'] = '' }
        if (-not $entry.Contains('correlation_id')) { $entry['correlation_id'] = '' }
        $loggedAt = Get-Date -Format 'o'
        $entry['logged_at'] = $loggedAt
        if (-not $entry.Contains('created_at')) { $entry['created_at'] = $loggedAt }
        $entry['completed_manifest_source'] = 'csv_rerun_replace_final'
        $written = [bool](Write-RerunJsonLineAppend -Path ([string]$script:RerunCompletedJobsManifest) -Payload $entry -Depth 12)
        if (-not $written) {
            Write-RerunLog "Completed-jobs manifest append failed for $OutputPath : JSONL append lock unavailable or write failed" "WARN"
        }
        return $written
    } catch {
        Write-RerunLog "Completed-jobs manifest append failed for $OutputPath : $($_.Exception.Message)" "WARN"
        return $false
    }
}
