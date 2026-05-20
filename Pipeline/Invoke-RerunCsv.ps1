[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$CsvPath,
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'MediaPipeline_config_chatgpt.psd1'),
    [ValidateSet('copy')] [string]$DefaultStageMode = 'copy',
    [ValidateSet('keep')] [string]$DefaultOriginalMode = 'keep',
    [ValidateSet('park')] [string]$DefaultReturnMode = 'park',
    [switch]$DryRun,
    [switch]$ShowConfig
)

$ErrorActionPreference = 'Stop'

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

Write-RerunLog "CSV rerun safety policy: copy-only staging, keep originals, and park outputs. Source-mutating row policies are rejected during planning." "INFO"

$rerunIdentityModule = Join-Path $PSScriptRoot 'Modules\RerunSourceIdentity.ps1'
if (-not (Test-Path -LiteralPath $rerunIdentityModule)) { throw "Rerun source identity module not found: $rerunIdentityModule" }
. $rerunIdentityModule

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

$script:RerunDiskSpaceTypeDefinition = @"
using System;
using System.Runtime.InteropServices;
namespace MediaPipeline {
    public static class RerunDiskSpace {
        [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool GetDiskFreeSpaceExW(
            string lpDirectoryName,
            out ulong lpFreeBytesAvailable,
            out ulong lpTotalNumberOfBytes,
            out ulong lpTotalNumberOfFreeBytes);
    }
}
"@

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
            $safeKey = [string]$key
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

function Write-RerunTempConfig {
    param(
        [hashtable]$Config,
        [string]$Path
    )
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('@{')
    foreach ($key in ($Config.Keys | Sort-Object)) {
        $lines.Add(('    {0} = {1}' -f $key, (ConvertTo-Psd1Literal -Value $Config[$key] -Indent 4)))
    }
    $lines.Add('}')

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    [System.IO.File]::WriteAllText($tmp, ($lines -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::Move($tmp, $Path, $true)
}

function Write-RerunManifest {
    param(
        [string]$Path,
        $Payload
    )
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    $Payload | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $tmp -Encoding UTF8
    [System.IO.File]::Move($tmp, $Path, $true)
}

function Test-RerunSourceMatchesCsv {
    param(
        [System.IO.FileInfo]$FileInfo,
        $Row,
        [string]$FfprobePath
    )
    $expectedSize = Get-RerunValue -Row $Row -Names @('source_size','SourceSizeBytes','SizeBytes') -Default ''
    if ($expectedSize -match '^\d+$' -and [long]$expectedSize -ne [long]$FileInfo.Length) {
        return "source size changed: CSV=$expectedSize current=$($FileInfo.Length)"
    }

    $expectedMtime = Get-RerunValue -Row $Row -Names @('source_mtime_utc','SourceLastWriteUtc','LastWriteTimeUtc') -Default ''
    if ($expectedMtime) {
        try {
            $parsed = [datetimeoffset]::Parse($expectedMtime, [System.Globalization.CultureInfo]::InvariantCulture)
            $delta = [math]::Abs(($FileInfo.LastWriteTimeUtc - $parsed.UtcDateTime).TotalSeconds)
            if ($delta -gt 2) {
                return "source mtime changed: CSV=$expectedMtime current=$($FileInfo.LastWriteTimeUtc.ToString('o'))"
            }
        } catch {
            Write-RerunLog "Could not parse CSV source_mtime_utc '$expectedMtime' for $($FileInfo.FullName)" "WARN"
        }
    }

    $expectedIdentity = Get-RerunValue -Row $Row -Names @('source_identity_v2','SourceIdentityV2') -Default ''
    if ($expectedIdentity) {
        $currentIdentity = Get-RerunSourceIdentityV2 -FileInfo $FileInfo -FfprobePath $FfprobePath
        if (-not $currentIdentity) {
            return 'source identity v2 could not be recomputed'
        }
        if ($currentIdentity -ne $expectedIdentity) {
            return 'source identity v2 changed'
        }
    }
    return ''
}

function Get-RerunMediaKind {
    param($Row, [string]$Path)
    $kind = (Get-RerunValue -Row $Row -Names @('media_kind','MediaType') -Default '').Trim().ToLowerInvariant()
    if ($kind -in @('tv','show','episode')) { return 'TV' }
    if ($kind -in @('movie','movies','film')) { return 'Movie' }
    $parts = @($Path -split '[\\/]+') | ForEach-Object { $_.ToLowerInvariant() }
    if ($parts -contains 'tv') { return 'TV' }
    return 'Movie'
}

function Join-RerunPathParts {
    param([string[]]$Parts)
    $clean = @($Parts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($clean.Count -eq 0) { return '' }
    $path = [string]$clean[0]
    for ($i = 1; $i -lt $clean.Count; $i++) { $path = Join-Path $path ([string]$clean[$i]) }
    return $path
}

function Resolve-RerunPlans {
    param(
        [array]$Rows,
        [hashtable]$Config,
        [string]$StageRoot,
        [string]$OutputRoot,
        [string]$FfprobePath
    )

    $stageMoviesRoot = Join-Path $StageRoot 'Movies'
    $stageTvRoot = Join-Path $StageRoot 'TV'
    $plans = [System.Collections.Generic.List[object]]::new()
    $destinationKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    foreach ($row in $Rows) {
        $enabled = ConvertTo-RerunBool (Get-RerunValue -Row $row -Names @('enabled','rerun_enabled','Enabled') -Default 'true') $true
        if (-not $enabled) { continue }

        $sourceText = Get-RerunValue -Row $row -Names @('source_path','Path','SourcePath') -Default ''
        $sourcePath = Resolve-RerunPath $sourceText
        $rowStageOverride = Normalize-RerunChoiceValue (Get-RerunValue -Row $row -Names @('stage_mode','StageMode') -Default '')
        $rowOriginalOverride = Normalize-RerunChoiceValue (Get-RerunValue -Row $row -Names @('post_success_original','original_mode','OriginalMode') -Default '')
        $rowReturnOverride = Normalize-RerunChoiceValue (Get-RerunValue -Row $row -Names @('return_mode','ReturnMode') -Default '')
        $stageMode = Resolve-RerunChoice -Row $row -Names @('stage_mode','StageMode') -Default $DefaultStageMode -Allowed @('copy','move')
        $originalMode = Resolve-RerunChoice -Row $row -Names @('post_success_original','original_mode','OriginalMode') -Default $DefaultOriginalMode -Allowed @('keep','delete')
        $returnMode = Resolve-RerunChoice -Row $row -Names @('return_mode','ReturnMode') -Default $DefaultReturnMode -Allowed @('park','replace_original')

        $plan = [ordered]@{
            source_path = $sourcePath
            media_kind = ''
            stage_mode = $stageMode
            original_mode = $originalMode
            return_mode = $returnMode
            stage_path = ''
            planned_output_path = ''
            status = 'pending'
            reason = ''
            source_size = $null
            source_mtime_utc = ''
            source_identity_v2 = Get-RerunValue -Row $row -Names @('source_identity_v2','SourceIdentityV2') -Default ''
            audit_issue_codes = Get-RerunValue -Row $row -Names @('audit_issue_codes','IssueCodes','NonSidecarIssueCodes','PrimaryIssueCode') -Default ''
            queue_item = $null
        }

        if ([string]::IsNullOrWhiteSpace($sourcePath) -or -not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            $plan.status = 'failed'
            $plan.reason = "source file not found: $sourceText"
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $unsafePolicy = [System.Collections.Generic.List[string]]::new()
        if (-not [string]::IsNullOrWhiteSpace($rowStageOverride) -and $rowStageOverride -ne 'copy') {
            $unsafePolicy.Add("stage_mode=$rowStageOverride")
        }
        if (-not [string]::IsNullOrWhiteSpace($rowOriginalOverride) -and $rowOriginalOverride -ne 'keep') {
            $unsafePolicy.Add("post_success_original=$rowOriginalOverride")
        }
        if (-not [string]::IsNullOrWhiteSpace($rowReturnOverride) -and $rowReturnOverride -ne 'park') {
            $unsafePolicy.Add("return_mode=$rowReturnOverride")
        }
        if ($unsafePolicy.Count -gt 0) {
            $plan.status = 'failed'
            $plan.reason = "source-mutating or in-place CSV rerun policy is disabled: $($unsafePolicy -join ', ')"
            $plans.Add([pscustomobject]$plan)
            continue
        }
        $stageMode = 'copy'
        $originalMode = 'keep'
        $returnMode = 'park'
        $plan.stage_mode = $stageMode
        $plan.original_mode = $originalMode
        $plan.return_mode = $returnMode
        if ($returnMode -ne $DefaultReturnMode) {
            $plan.status = 'failed'
            $plan.reason = "mixed return_mode values are not supported in one rerun batch; row=$returnMode batch=$DefaultReturnMode"
            $plans.Add([pscustomobject]$plan)
            continue
        }

        $fileInfo = Get-Item -LiteralPath $sourcePath -Force
        $plan.source_size = [long]$fileInfo.Length
        $plan.source_mtime_utc = $fileInfo.LastWriteTimeUtc.ToString('o')
        $identityFailure = Test-RerunSourceMatchesCsv -FileInfo $fileInfo -Row $row -FfprobePath $FfprobePath
        if ($identityFailure) {
            $plan.status = 'failed'
            $plan.reason = $identityFailure
            $plans.Add([pscustomobject]$plan)
            continue
        }

        $kind = Get-RerunMediaKind -Row $row -Path $sourcePath
        $plan.media_kind = $kind
        $extension = $fileInfo.Extension
        if ($kind -eq 'TV') {
            $tvInfo = Get-TVInfoFromFile $fileInfo
            if (-not $tvInfo.IsReliable) {
                $plan.status = 'failed'
                $plan.reason = "TV parse failed: $($tvInfo.ParseError)"
                $plans.Add([pscustomobject]$plan)
                continue
            }
            $stagePlan = New-PlexDestinationPlan -MediaKind 'TV' -File $fileInfo -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension $extension
            $outputPlan = New-PlexDestinationPlan -MediaKind 'TV' -File $fileInfo -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension ([string]$Config['OutputContainer']) -IncludeLibraryFolder:([bool]$Config['CreateTVSubfolder'])
            $plan.stage_path = Join-Path $stageTvRoot $stagePlan.RelativePath
            $plan.planned_output_path = Join-Path $OutputRoot $outputPlan.RelativePath
        } else {
            $stagePlan = New-PlexDestinationPlan -MediaKind 'Movie' -File $fileInfo -OriginalName $fileInfo.Name -Extension $extension
            $outputPlan = New-PlexDestinationPlan -MediaKind 'Movie' -File $fileInfo -OriginalName $fileInfo.Name -Extension ([string]$Config['OutputContainer'])
            $plan.stage_path = Join-Path $stageMoviesRoot $stagePlan.RelativePath
            $plan.planned_output_path = Join-Path $OutputRoot $outputPlan.RelativePath
        }

        $destinationKey = ([string]$plan.planned_output_path).ToLowerInvariant()
        if (-not $destinationKeys.Add($destinationKey)) {
            $plan.status = 'failed'
            $plan.reason = "duplicate planned output path in CSV: $($plan.planned_output_path)"
        }
        $queueMediaKind = ([string]$kind).ToLowerInvariant()
        $queueItem = New-MediaQueueItem `
            -File $fileInfo `
            -MediaKind $queueMediaKind `
            -QueueSource 'csv_rerun' `
            -SourcePath $sourcePath `
            -Metadata @{
                stage_path = [string]$plan.stage_path
                planned_output_path = [string]$plan.planned_output_path
                stage_mode = [string]$plan.stage_mode
                original_mode = [string]$plan.original_mode
                return_mode = [string]$plan.return_mode
                status = [string]$plan.status
                audit_issue_codes = [string]$plan.audit_issue_codes
            }
        $plan.queue_item = ConvertTo-MediaQueueItemRecord -QueueItem $queueItem
        $plans.Add([pscustomobject]$plan)
    }
    return @($plans)
}

function Invoke-RerunStagePlans {
    param([array]$Plans)
    foreach ($plan in @($Plans | Where-Object { $_.status -eq 'pending' })) {
        try {
            $stageDir = Split-Path -Parent ([string]$plan.stage_path)
            if (-not (Test-Path -LiteralPath $stageDir)) { New-Item -ItemType Directory -Path $stageDir -Force | Out-Null }
            if (Test-Path -LiteralPath ([string]$plan.stage_path)) {
                throw "stage path already exists: $($plan.stage_path)"
            }
            if (-not (Copy-RerunFileVerified -Source ([string]$plan.source_path) -Destination ([string]$plan.stage_path))) {
                throw "verified rerun stage copy failed"
            }
            $plan.status = 'staged'
            Write-RerunLog ("STAGED {0}: {1}" -f $plan.stage_mode, $plan.source_path)
        } catch {
            $plan.status = 'failed'
            $plan.reason = "stage failed: $($_.Exception.Message)"
            Write-RerunLog $plan.reason "ERROR"
        }
    }
}

function Complete-RerunPlans {
    param([array]$Plans)
    foreach ($plan in @($Plans | Where-Object { $_.status -eq 'staged' })) {
        $outPath = [string]$plan.planned_output_path
        if (-not (Test-Path -LiteralPath $outPath -PathType Leaf)) {
            $plan.status = 'parked'
            $plan.reason = "planned output was not produced"
            continue
        }
        $outItem = Get-Item -LiteralPath $outPath -Force
        if ($outItem.Length -le 0) {
            $plan.status = 'parked'
            $plan.reason = "planned output is empty"
            continue
        }

        $plan.status = 'complete'
        $plan.reason = 'verified output exists'
    }
}

if (-not (Test-Path -LiteralPath $CsvPath -PathType Leaf)) {
    throw "CSV not found: $CsvPath"
}
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "Config not found: $ConfigPath"
}

$config = Import-PowerShellDataFile -LiteralPath $ConfigPath
foreach ($key in @('LocalBase','Outsource','OutputContainer')) {
    if (-not $config.ContainsKey($key) -or [string]::IsNullOrWhiteSpace([string]$config[$key])) {
        throw "Config is missing required key for rerun mode: $key"
    }
}
if (-not $config.ContainsKey('CreateTVSubfolder')) { $config['CreateTVSubfolder'] = $true }
if (-not $config.ContainsKey('AggressiveEpisodeParsing')) { $config['AggressiveEpisodeParsing'] = $true }
if (-not $config.ContainsKey('ValidExtensions')) { $config['ValidExtensions'] = @('.mkv','.mp4','.m4v','.avi','.mov','.ts','.m2ts') }
if (-not $config.ContainsKey('PriorityMarkers')) { $config['PriorityMarkers'] = @('!') }

$script:RerunRobocopyFlags = if ($config.ContainsKey('RobocopyFlags')) { @($config['RobocopyFlags']) } else { @('/J', '/R:3', '/W:15', '/MT:2', '/NP', '/NDL', '/NFL') }
$script:RerunRobocopyTimeoutSeconds = 14400
if ($config.ContainsKey('RobocopyTimeoutSeconds')) {
    try { $script:RerunRobocopyTimeoutSeconds = [math]::Max(60, [int]$config['RobocopyTimeoutSeconds']) } catch {}
}
$script:RerunNestedPipelineTimeoutSeconds = 604800
if ($config.ContainsKey('RerunNestedPipelineTimeoutSeconds')) {
    try { $script:RerunNestedPipelineTimeoutSeconds = [math]::Max(3600, [int]$config['RerunNestedPipelineTimeoutSeconds']) } catch {}
}

$script:PriorityMarkers = @($config['PriorityMarkers'])
$script:AggressiveEpisodeParsing = [bool]$config['AggressiveEpisodeParsing']
$script:ValidExtensions = @($config['ValidExtensions'])
$CreateTVSubfolder = [bool]$config['CreateTVSubfolder']

$queuePlanModule = Join-Path $PSScriptRoot 'Modules\QueuePlan.ps1'
if (-not (Test-Path -LiteralPath $queuePlanModule)) { throw "QueuePlan module not found: $queuePlanModule" }
. $queuePlanModule

$namingModule = Join-Path $PSScriptRoot 'Modules\Naming.ps1'
if (-not (Test-Path -LiteralPath $namingModule)) { throw "Naming module not found: $namingModule" }
. $namingModule

$pipelinePath = Join-Path $PSScriptRoot 'MediaPipeline_chatgpt.ps1'
if (-not (Test-Path -LiteralPath $pipelinePath)) { throw "Pipeline script not found: $pipelinePath" }
$pwsh = Join-Path $PSScriptRoot 'PowerShell-7.6.0-win-x64\pwsh.exe'
if (-not (Test-Path -LiteralPath $pwsh)) { $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source }
if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
if (-not $pwsh) { throw 'PowerShell 7 host not found for nested pipeline run.' }

$localBase = Resolve-RerunPath ([string]$config['LocalBase'])
$mainOutsource = Resolve-RerunPath ([string]$config['Outsource'])
$batchId = 'rerun_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$stageRoot = Join-Path $localBase (Join-RerunPathParts @('RerunQueue', $batchId))
$parkRoot = Join-Path $localBase (Join-RerunPathParts @('RerunParked', $batchId))
$manifestRoot = Join-Path $localBase 'RerunManifests'
$manifestPath = Join-Path $manifestRoot "$batchId.json"
$outputRoot = if ($DefaultReturnMode -eq 'park') { Join-Path $parkRoot 'Output' } else { $mainOutsource }

$ffprobePath = Join-Path $PSScriptRoot 'Tools\ffmpeg\bin\ffprobe.exe'
if (-not (Test-Path -LiteralPath $ffprobePath)) { $ffprobePath = '' }

$rows = @(Import-Csv -LiteralPath $CsvPath)
if ($rows.Count -eq 0) { throw "CSV contains no rows: $CsvPath" }

New-Item -ItemType Directory -Path (Join-Path $stageRoot 'Movies') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stageRoot 'TV') -Force | Out-Null
New-Item -ItemType Directory -Path $parkRoot -Force | Out-Null

$plans = @(Resolve-RerunPlans -Rows $rows -Config $config -StageRoot $stageRoot -OutputRoot $outputRoot -FfprobePath $ffprobePath)
$manifest = [ordered]@{
    batch_id = $batchId
    created_at = (Get-Date -Format 'o')
    csv_path = (Resolve-RerunPath $CsvPath)
    config_path = (Resolve-RerunPath $ConfigPath)
    dry_run = [bool]$DryRun
    default_stage_mode = $DefaultStageMode
    default_original_mode = $DefaultOriginalMode
    default_return_mode = $DefaultReturnMode
    stage_root = $stageRoot
    park_root = $parkRoot
    output_root = $outputRoot
    nested_pipeline_timeout_seconds = [int]$script:RerunNestedPipelineTimeoutSeconds
    status = 'planned'
    rows = @($plans)
}
Write-RerunManifest -Path $manifestPath -Payload $manifest

Write-RerunLog "Rerun CSV rows listed: $($rows.Count); enabled/planned: $($plans.Count)"
foreach ($plan in $plans) {
    Write-RerunLog ("PLAN [{0}] {1} -> {2}" -f $plan.status, $plan.source_path, $plan.planned_output_path)
    if ($plan.reason) { Write-RerunLog ("  reason: {0}" -f $plan.reason) "WARN" }
}

if ($DryRun) {
    $manifest.status = 'dry_run_complete'
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
    Write-RerunLog "DRY RUN complete. Manifest: $manifestPath"
    exit 0
}

Invoke-RerunStagePlans -Plans $plans
$manifest.status = 'staged'
$manifest.rows = @($plans)
Write-RerunManifest -Path $manifestPath -Payload $manifest

$runnable = @($plans | Where-Object { $_.status -eq 'staged' })
if ($runnable.Count -eq 0) {
    $manifest.status = 'failed'
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
    throw 'No CSV rows could be staged for rerun.'
}

$tempConfig = [hashtable]::new($config)
$tempConfig['SourceMovies'] = Join-Path $stageRoot 'Movies'
$tempConfig['SourceTV'] = Join-Path $stageRoot 'TV'
$tempConfig['Outsource'] = $outputRoot
$tempConfig['ReprocessAll'] = $true
$tempConfig['SkipStabilityCheck'] = $true
$tempConfigPath = Join-Path $manifestRoot "$batchId.config.psd1"
Write-RerunTempConfig -Config $tempConfig -Path $tempConfigPath

$args = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $pipelinePath,
    '-ConfigPath', $tempConfigPath,
    '-Once',
    '-SleepSeconds', '1'
)
if ($ShowConfig) { $args += '-ShowConfig' }

Write-RerunLog "Launching nested pipeline for CSV-authoritative batch: $batchId"
$pipelineRun = Invoke-RerunStreamingCommand -FilePath $pwsh -ArgumentList $args -TimeoutSeconds $script:RerunNestedPipelineTimeoutSeconds -Label 'nested pipeline'
$pipelineExit = [int]$pipelineRun.ExitCode
if ($pipelineRun.TimedOut) {
    Write-RerunLog "Nested pipeline timed out after $($script:RerunNestedPipelineTimeoutSeconds)s" "ERROR"
}
Write-RerunLog "Nested pipeline exited with code $pipelineExit"

Complete-RerunPlans -Plans $plans
$complete = @($plans | Where-Object { $_.status -eq 'complete' }).Count
$parked = @($plans | Where-Object { $_.status -eq 'parked' }).Count
$failed = @($plans | Where-Object { $_.status -eq 'failed' }).Count
$manifest.status = if ($failed -gt 0 -or $parked -gt 0 -or $pipelineExit -ne 0) { 'completed_with_parked_or_failed_rows' } else { 'complete' }
$manifest.completed_at = (Get-Date -Format 'o')
$manifest.pipeline_exit_code = $pipelineExit
$manifest.rows = @($plans)
Write-RerunManifest -Path $manifestPath -Payload $manifest

Write-RerunLog "Rerun batch complete: complete=$complete parked=$parked failed=$failed manifest=$manifestPath"
if ($pipelineExit -ne 0 -or $failed -gt 0) { exit 1 }
exit 0
