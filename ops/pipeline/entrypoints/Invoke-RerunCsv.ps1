[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$CsvPath,
    [string]$ConfigPath = '',
    [ValidateSet('copy')] [string]$DefaultStageMode = 'copy',
    [ValidateSet('keep')] [string]$DefaultOriginalMode = 'keep',
    [ValidateSet('park','pending_publish','publish_non_overlap','replace_original')] [string]$DefaultReturnMode = 'park',
    [ValidateSet('one_at_a_time','windowed','batch_stage_all')] [string]$ExecutionMode = 'one_at_a_time',
    [ValidateSet('review_workspace','pending_publish','publish_non_overlap','publish_replace_final')] [string]$DestinationMode = 'review_workspace',
    [ValidateSet('keep','rename_after_publish','move_to_hold_after_publish','hold_then_delete_after_publish')] [string]$OriginalPolicy = 'keep',
    [ValidateSet('suffix','fail','replace_final')] [string]$CollisionPolicy = 'suffix',
    [ValidateRange(1,100)] [int]$WindowSize = 1,
    [switch]$ConfirmReplaceFinal,
    [switch]$ConfirmOriginalPolicy,
    [switch]$ConfirmDeleteOriginal,
    [switch]$DryRun,
    [switch]$PlanOnly,
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

Write-RerunLog "CSV rerun lifecycle policy: execution=$ExecutionMode destination=$DestinationMode original_policy=$OriginalPolicy collision=$CollisionPolicy window_size=$WindowSize. Source row mutation aliases remain rejected during planning." "INFO"
if ($DryRun -and $PlanOnly) {
    throw 'CSV rerun accepts either -DryRun or -PlanOnly, not both.'
}
if ($ExecutionMode -eq 'one_at_a_time') { $WindowSize = 1 }
if ($DestinationMode -eq 'publish_replace_final' -and -not $ConfirmReplaceFinal) {
    throw 'publish_replace_final requires -ConfirmReplaceFinal.'
}
if ($OriginalPolicy -ne 'keep') {
    throw 'CSV rerun original source policies are disabled until final-output proof is recorded by a separate cleanup flow.'
}
if ($OriginalPolicy -ne 'keep' -and -not $ConfirmOriginalPolicy) {
    throw "$OriginalPolicy requires -ConfirmOriginalPolicy."
}
if ($OriginalPolicy -eq 'hold_then_delete_after_publish' -and -not $ConfirmDeleteOriginal) {
    throw 'hold_then_delete_after_publish requires -ConfirmDeleteOriginal; actual deletion remains a separate cleanup flow.'
}

$script:PipelineRoot = Split-Path -Parent $PSScriptRoot

$rerunIdentityModule = Join-Path $script:PipelineRoot 'engine\audit\rerun_source_identity.ps1'
if (-not (Test-Path -LiteralPath $rerunIdentityModule)) { throw "Rerun source identity module not found: $rerunIdentityModule" }
. $rerunIdentityModule

$rerunVersioningModule = Join-Path $script:PipelineRoot 'engine\shared\versioning.ps1'
if (-not (Test-Path -LiteralPath $rerunVersioningModule)) { throw "Rerun versioning module not found: $rerunVersioningModule" }
. $rerunVersioningModule
$script:RerunProductVersion = Get-MediaPipelineProductVersion
$script:RerunPipelineVersion = Get-MediaPipelineSidecarVersion

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

function Get-RerunObjectValue {
    param($Object, [string]$Name, $Default = $null)
    if ($null -eq $Object) { return $Default }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) { return $Object[$Name] }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function Get-RerunObjectText {
    param($Object, [string]$Name, [string]$Default = '')
    $value = Get-RerunObjectValue -Object $Object -Name $Name -Default $Default
    if ($null -eq $value) { return $Default }
    return [string]$value
}

function Get-RerunArrayField {
    param($Object, [string]$Name)
    $value = Get-RerunObjectValue -Object $Object -Name $Name -Default @()
    if ($null -eq $value) { return @() }
    if ($value -is [array]) { return @($value) }
    if ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) { return @($value) }
    return @($value)
}

function Get-RerunBoolField {
    param($Object, [string]$Name)
    $value = Get-RerunObjectValue -Object $Object -Name $Name -Default $false
    if ($value -is [bool]) { return [bool]$value }
    return ([string]$value).Trim().ToLowerInvariant() -eq 'true'
}

function Get-RerunPipelineSidecarPath {
    param([Parameter(Mandatory)] [string]$OutputPath)
    $dir = Split-Path -Parent $OutputPath
    $base = [System.IO.Path]::GetFileNameWithoutExtension($OutputPath)
    return (Join-Path $dir ($base + '.pipeline.json'))
}

function Read-RerunPipelineSidecar {
    param([Parameter(Mandatory)] [string]$OutputPath)
    $sidecar = Get-RerunPipelineSidecarPath -OutputPath $OutputPath
    if (-not (Test-Path -LiteralPath $sidecar -PathType Leaf)) { return $null }
    try {
        return (Get-Content -LiteralPath $sidecar -Raw | ConvertFrom-Json -ErrorAction Stop)
    } catch {
        Write-RerunLog "CSV rerun could not read pipeline sidecar evidence $sidecar : $($_.Exception.Message)" "WARN"
        return $null
    }
}

function Get-RerunTrackSourcePath {
    param($Record)
    foreach ($key in @('local_file','path','Path','srt_path','SrtPath','LocalPath')) {
        $value = Get-RerunObjectText -Object $Record -Name $key -Default ''
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
    }
    return ''
}

function Test-RerunPathUnderRoot {
    param([string]$Path, [string]$Root)
    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) { return $false }
    try {
        $fullPath = [System.IO.Path]::GetFullPath($Path)
        $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
        return ($fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or $fullPath.StartsWith($fullRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or $fullPath.StartsWith($fullRoot + [System.IO.Path]::AltDirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase))
    } catch {
        return $false
    }
}

function Copy-RerunRecordProperties {
    param($Record)
    $map = [ordered]@{}
    if ($null -eq $Record) { return $map }
    foreach ($prop in $Record.PSObject.Properties) {
        $map[$prop.Name] = $prop.Value
    }
    return $map
}

function New-RerunPendingSidecarEntries {
    param(
        $PipelineSidecar,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$FinalOutput,
        [Parameter(Mandatory)] [string]$PendingRoot,
        [Parameter(Mandatory)] [string]$TransactionId
    )
    $entries = [System.Collections.Generic.List[object]]::new()
    $tracks = [System.Collections.Generic.List[object]]::new()
    $copied = [System.Collections.Generic.List[string]]::new()
    if ($null -eq $PipelineSidecar) {
        return [pscustomobject]@{ Entries = @(); Tracks = @(); Copied = @() }
    }

    $verifiedDir = Split-Path -Parent $VerifiedOutput
    $finalDir = Split-Path -Parent $FinalOutput
    $sidecarIndex = 0
    foreach ($record in @(Get-RerunArrayField -Object $PipelineSidecar -Name 'tx3g_srt_tracks')) {
        $source = Get-RerunTrackSourcePath -Record $record
        if ([string]::IsNullOrWhiteSpace($source)) { continue }
        if ([System.IO.Path]::GetExtension($source).ToLowerInvariant() -ne '.srt') { continue }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        if (-not (Test-RerunPathUnderRoot -Path $source -Root $verifiedDir)) { continue }

        $relative = [System.IO.Path]::GetRelativePath([System.IO.Path]::GetFullPath($verifiedDir), [System.IO.Path]::GetFullPath($source))
        if ([string]::IsNullOrWhiteSpace($relative) -or $relative.StartsWith('..')) { continue }
        $serverOut = Join-Path $finalDir $relative
        $parked = Join-Path $PendingRoot ("{0}.sidecar{1}{2}" -f $TransactionId, $sidecarIndex, [System.IO.Path]::GetExtension($source))
        if (Test-Path -LiteralPath $parked) { $parked = Get-RerunNonOverlapPath -Path $parked -Suffix $TransactionId }
        try {
            Copy-Item -LiteralPath $source -Destination $parked -Force -ErrorAction Stop
        } catch {
            foreach ($copiedSidecar in @($copied)) {
                Remove-Item -LiteralPath $copiedSidecar -Force -ErrorAction SilentlyContinue
            }
            throw
        }
        $copied.Add($parked) | Out-Null

        $pendingRecord = Copy-RerunRecordProperties -Record $record
        $pendingRecord['path'] = $serverOut
        $pendingRecord['file_name'] = Split-Path -Leaf $serverOut
        $pendingRecord['status'] = 'pending'
        $tracks.Add([pscustomobject]$pendingRecord) | Out-Null
        $entries.Add([pscustomobject][ordered]@{
            kind = 'converted_srt'
            local_file = $parked
            original_local_file = $source
            parked_file = $parked
            server_out = $serverOut
            output_size = [long](Get-Item -LiteralPath $parked -Force).Length
            preserve_existing = [bool](Get-RerunObjectValue -Object $record -Name 'preserved_existing' -Default $false)
            tx3g_record = [pscustomobject]$pendingRecord
        }) | Out-Null
        $sidecarIndex++
    }
    return [pscustomobject]@{ Entries = @($entries); Tracks = @($tracks); Copied = @($copied) }
}

function Assert-RerunPendingPublishManifestContract {
    param($Payload)

    foreach ($key in @(
        'pipeline_version',
        'publish_transaction_id',
        'manifest_state',
        'local_file',
        'server_out',
        'route',
        'source_identity_v2',
        'source_identity_v2_algorithm',
        'source_path'
    )) {
        if ([string]::IsNullOrWhiteSpace([string]$Payload[$key])) {
            throw "CSV rerun pending manifest field is required and cannot be blank: $key"
        }
    }
    foreach ($key in @(
        'sidecar_files',
        'tx3g_srt_tracks',
        'tx3g_srt_failures',
        'bdpgs_srt_failures',
        'vobsub_srt_failures',
        'tx3g_embedded_srt_tracks',
        'bdpgs_embedded_srt_tracks',
        'vobsub_embedded_srt_tracks'
    )) {
        if (-not $Payload.Contains($key)) {
            throw "CSV rerun pending manifest array field is required: $key"
        }
    }
    if ($null -eq $Payload['output_size']) {
        throw 'CSV rerun pending manifest output_size is required.'
    }
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
        [string]$FinalOutputRoot,
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
        $returnMode = Resolve-RerunChoice -Row $row -Names @('return_mode','ReturnMode') -Default $DefaultReturnMode -Allowed @('park','pending_publish','publish_non_overlap','replace_original')

        $plan = [ordered]@{
            source_path = $sourcePath
            media_kind = ''
            stage_mode = $stageMode
            original_mode = $originalMode
            return_mode = $returnMode
            stage_path = ''
            planned_output_path = ''
            final_output_path = ''
            verified_output_path = ''
            pending_publish_payload_path = ''
            pending_publish_manifest_path = ''
            published_path = ''
            replaced_final_hold_path = ''
            original_action = ''
            original_held_path = ''
            original_cleanup_ready = $false
            staged_input_cleanup = ''
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
        $returnMode = $DefaultReturnMode
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
            $plan.final_output_path = Join-Path $FinalOutputRoot $outputPlan.RelativePath
        } else {
            $stagePlan = New-PlexDestinationPlan -MediaKind 'Movie' -File $fileInfo -OriginalName $fileInfo.Name -Extension $extension
            $outputPlan = New-PlexDestinationPlan -MediaKind 'Movie' -File $fileInfo -OriginalName $fileInfo.Name -Extension ([string]$Config['OutputContainer'])
            $plan.stage_path = Join-Path $stageMoviesRoot $stagePlan.RelativePath
            $plan.planned_output_path = Join-Path $OutputRoot $outputPlan.RelativePath
            $plan.final_output_path = Join-Path $FinalOutputRoot $outputPlan.RelativePath
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
                final_output_path = [string]$plan.final_output_path
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
            $plan.status = 'failed'
            $plan.reason = "planned output was not produced"
            continue
        }
        $outItem = Get-Item -LiteralPath $outPath -Force
        if ($outItem.Length -le 0) {
            $plan.status = 'failed'
            $plan.reason = "planned output is empty"
            continue
        }

        $plan.status = 'complete'
        $plan.verified_output_path = $outPath
        $plan.reason = 'verified output exists'
    }
}

function Remove-RerunStagedInputs {
    param([array]$Plans)
    foreach ($plan in @($Plans)) {
        $stagePath = [string]$plan.stage_path
        if ([string]::IsNullOrWhiteSpace($stagePath)) { continue }
        try {
            if (Test-Path -LiteralPath $stagePath -PathType Leaf) {
                Remove-Item -LiteralPath $stagePath -Force
                $plan.staged_input_cleanup = 'removed'
            }
        } catch {
            $plan.staged_input_cleanup = "failed: $($_.Exception.Message)"
            Write-RerunLog "Staged input cleanup failed: $stagePath :: $($_.Exception.Message)" "WARN"
        }
    }
}

function Get-RerunNonOverlapPath {
    param([string]$Path, [string]$Suffix)
    if (-not (Test-Path -LiteralPath $Path)) { return $Path }
    $dir = Split-Path -Parent $Path
    $leaf = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    $ext = [System.IO.Path]::GetExtension($Path)
    $candidate = Join-Path $dir ("{0}.{1}{2}" -f $leaf, $Suffix, $ext)
    $counter = 1
    while (Test-Path -LiteralPath $candidate) {
        $candidate = Join-Path $dir ("{0}.{1}.{2}{3}" -f $leaf, $Suffix, $counter, $ext)
        $counter++
    }
    return $candidate
}

function Move-RerunVerifiedOutput {
    param([string]$Source, [string]$Destination)
    if ([string]::IsNullOrWhiteSpace($Source) -or -not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "verified output not found: $Source"
    }
    $destDir = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    Move-Item -LiteralPath $Source -Destination $Destination -Force
    return $Destination
}

function New-RerunPendingPublishManifest {
    param(
        $Plan,
        [string]$PendingRoot,
        [string]$BatchId
    )
    $verified = [string]$Plan.verified_output_path
    if ([string]::IsNullOrWhiteSpace($verified)) { $verified = [string]$Plan.planned_output_path }
    $leaf = Split-Path -Leaf $verified
    $pendingFile = Join-Path $PendingRoot $leaf
    if (Test-Path -LiteralPath $pendingFile) {
        $pendingFile = Get-RerunNonOverlapPath -Path $pendingFile -Suffix $BatchId
    }
    if ([string]::IsNullOrWhiteSpace($verified) -or -not (Test-Path -LiteralPath $verified -PathType Leaf)) {
        throw "verified output not found: $verified"
    }
    $verifiedOutputSize = [long](Get-Item -LiteralPath $verified -Force).Length

    $manifestPath = Join-Path $PendingRoot (([System.IO.Path]::GetFileNameWithoutExtension($pendingFile)) + '.manifest.json')
    if (Test-Path -LiteralPath $manifestPath) {
        $manifestPath = Get-RerunNonOverlapPath -Path $manifestPath -Suffix $BatchId
    }
    $sourceIdentity = [string]$Plan.source_identity_v2
    if ([string]::IsNullOrWhiteSpace($sourceIdentity)) {
        $sourceIdentity = 'rerun_csv:' + ([guid]::NewGuid().ToString('N'))
    }
    $now = Get-Date -Format 'o'
    $transactionId = ('rerun-csv-{0}-{1}' -f $BatchId, [guid]::NewGuid().ToString('N'))
    $pipelineSidecar = Read-RerunPipelineSidecar -OutputPath $verified
    $pendingSidecars = New-RerunPendingSidecarEntries -PipelineSidecar $pipelineSidecar -VerifiedOutput $verified -FinalOutput ([string]$Plan.final_output_path) -PendingRoot $PendingRoot -TransactionId $transactionId
    $payload = [ordered]@{
        schema_version = 'pending_push_manifest.v1'
        parked_at = $now
        product_version = [string]$script:RerunProductVersion
        pipeline_version = [string]$script:RerunPipelineVersion
        publish_transaction_id = $transactionId
        manifest_state = 'pending_move'
        created_at = $now
        route = 'csv_rerun'
        route_reason_code = 'rerun_csv_pending_publish'
        route_reason = 'CSV rerun verified output promoted into Pending Publish.'
        media_type = [string]$Plan.media_kind
        local_file = $pendingFile
        original_local_file = $verified
        parked_file = $pendingFile
        server_out = [string]$Plan.final_output_path
        source_path = [string]$Plan.source_path
        source_size = [long]($Plan.source_size -as [long])
        source_mtime_utc = [string]$Plan.source_mtime_utc
        source_identity = $sourceIdentity
        source_identity_v2 = $sourceIdentity
        source_identity_v2_algorithm = 'rerun_csv_v2'
        output_size = $verifiedOutputSize
        publish_mode = 'pending_publish'
        sidecar_files = @($pendingSidecars.Entries)
        tx3g_srt_tracks = @($pendingSidecars.Tracks)
        tx3g_srt_failures = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'tx3g_srt_failures')
        bdpgs_srt_failures = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'bdpgs_srt_failures')
        vobsub_srt_failures = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'vobsub_srt_failures')
        converted_srt_sidecar_candidates = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'converted_srt_sidecar_candidates')
        subtitle_output_reduction = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'subtitle_output_reduction')
        tx3g_embedded_srt_tracks = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'tx3g_embedded_srt_tracks')
        bdpgs_embedded_srt_tracks = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'bdpgs_embedded_srt_tracks')
        vobsub_embedded_srt_tracks = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'vobsub_embedded_srt_tracks')
        tx3g_srt_conversion_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'tx3g_srt_conversion_enabled')
        tx3g_external_srt_sidecars_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'tx3g_external_srt_sidecars_enabled')
        drop_tx3g_after_conversion = (Get-RerunBoolField -Object $pipelineSidecar -Name 'drop_tx3g_after_conversion')
        bdpgs_srt_conversion_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'bdpgs_srt_conversion_enabled')
        drop_bdpgs_after_conversion = (Get-RerunBoolField -Object $pipelineSidecar -Name 'drop_bdpgs_after_conversion')
        vobsub_srt_conversion_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'vobsub_srt_conversion_enabled')
        drop_vobsub_after_conversion = (Get-RerunBoolField -Object $pipelineSidecar -Name 'drop_vobsub_after_conversion')
        original_subtitles_preserved = $true
        drop_ass_after_conversion = $false
        conversion_failed = $false
        source = @{
            rerun_batch_id = $BatchId
            rerun_audit_issue_codes = [string]$Plan.audit_issue_codes
        }
    }
    foreach ($evidenceKey in @('folder_policy','route_plan','route_explanation','library_profile','dynamic_hdr','quality_verification','audio_decisions','subtitle_decisions','encode_selected_attempt','encode_selected_encoder','encode_selected_encoder_kind','encode_selected_gpu_device')) {
        $evidenceValue = Get-RerunObjectValue -Object $pipelineSidecar -Name $evidenceKey -Default $null
        if ($null -ne $evidenceValue) {
            $payload[$evidenceKey] = $evidenceValue
        }
    }
    $manifestWritten = $false
    try {
        Assert-RerunPendingPublishManifestContract -Payload $payload
    } catch {
        foreach ($copiedSidecar in @($pendingSidecars.Copied)) {
            Remove-Item -LiteralPath $copiedSidecar -Force -ErrorAction SilentlyContinue
        }
        throw
    }
    try {
        Write-RerunManifest -Path $manifestPath -Payload $payload
        $manifestWritten = $true
        $roundTrip = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
        if ([string]$roundTrip.local_file -ne $pendingFile -or [string]$roundTrip.server_out -ne [string]$Plan.final_output_path -or [string]$roundTrip.manifest_state -ne 'pending_move') {
            throw 'CSV rerun pending manifest validation failed before park.'
        }
        Move-RerunVerifiedOutput -Source $verified -Destination $pendingFile | Out-Null
        try {
            $payload['manifest_state'] = 'parked'
            $payload['parked_at'] = (Get-Date -Format 'o')
            Write-RerunManifest -Path $manifestPath -Payload $payload
        } catch {
            Write-RerunLog "CSV rerun pending manifest state update failed after moving output; pending intent remains retryable: $manifestPath : $($_.Exception.Message)" "WARN"
        }
    } catch {
        if (-not $manifestWritten) {
            foreach ($copiedSidecar in @($pendingSidecars.Copied)) {
                Remove-Item -LiteralPath $copiedSidecar -Force -ErrorAction SilentlyContinue
            }
        }
        throw
    }
    $Plan.verified_output_path = $pendingFile
    $Plan.pending_publish_payload_path = $pendingFile
    $Plan.pending_publish_manifest_path = $manifestPath
    $Plan.status = 'pending_publish'
    $Plan.reason = 'verified output moved into Pending Publish manifest'
}

function Invoke-RerunOriginalPolicy {
    param($Plan, [string]$BatchId, [string]$HoldRoot)
    if ($OriginalPolicy -eq 'keep') {
        $Plan.original_action = 'kept'
        return
    }
    if (-not $ConfirmOriginalPolicy) { throw "$OriginalPolicy requires -ConfirmOriginalPolicy." }
    $sourcePath = [string]$Plan.source_path
    if ([string]::IsNullOrWhiteSpace($sourcePath) -or -not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "original source not found for original policy: $sourcePath"
    }
    if ($OriginalPolicy -eq 'rename_after_publish') {
        $dir = Split-Path -Parent $sourcePath
        $leaf = [System.IO.Path]::GetFileNameWithoutExtension($sourcePath)
        $ext = [System.IO.Path]::GetExtension($sourcePath)
        $renamed = Join-Path $dir ("{0}.rerun-original-{1}{2}" -f $leaf, $BatchId, $ext)
        if (Test-Path -LiteralPath $renamed) { $renamed = Get-RerunNonOverlapPath -Path $renamed -Suffix $BatchId }
        Move-Item -LiteralPath $sourcePath -Destination $renamed
        $Plan.original_action = 'renamed_after_publish'
        $Plan.original_held_path = $renamed
        return
    }
    $holdDir = Join-Path $HoldRoot $BatchId
    New-Item -ItemType Directory -Path $holdDir -Force | Out-Null
    $held = Join-Path $holdDir (Split-Path -Leaf $sourcePath)
    if (Test-Path -LiteralPath $held) { $held = Get-RerunNonOverlapPath -Path $held -Suffix $BatchId }
    Move-Item -LiteralPath $sourcePath -Destination $held
    $Plan.original_action = if ($OriginalPolicy -eq 'hold_then_delete_after_publish') { 'held_cleanup_ready' } else { 'moved_to_hold_after_publish' }
    $Plan.original_held_path = $held
    if ($OriginalPolicy -eq 'hold_then_delete_after_publish') {
        $Plan.original_cleanup_ready = $true
    }
}

function Invoke-RerunDestinationPolicy {
    param(
        [array]$Plans,
        [string]$BatchId,
        [string]$PendingRoot,
        [string]$FinalHoldRoot,
        [string]$OriginalHoldRoot
    )
    foreach ($plan in @($Plans | Where-Object { $_.status -eq 'complete' })) {
        try {
            $verified = [string]$plan.verified_output_path
            if ([string]::IsNullOrWhiteSpace($verified)) { $verified = [string]$plan.planned_output_path }
            if ($DestinationMode -eq 'review_workspace') {
                $plan.status = 'review_workspace'
                $plan.reason = 'verified output left in rerun review workspace'
                $plan.verified_output_path = $verified
                $plan.original_action = 'deferred_until_final_publish'
                continue
            }
            if ($DestinationMode -eq 'pending_publish') {
                New-Item -ItemType Directory -Path $PendingRoot -Force | Out-Null
                New-RerunPendingPublishManifest -Plan $plan -PendingRoot $PendingRoot -BatchId $BatchId
                $plan.original_action = 'deferred_until_pending_publish_drain'
                continue
            }
            $destination = [string]$plan.final_output_path
            if ([string]::IsNullOrWhiteSpace($destination)) { throw 'final output path is unavailable' }
            if ($DestinationMode -eq 'publish_non_overlap') {
                if ((Test-Path -LiteralPath $destination) -and $CollisionPolicy -eq 'fail') {
                    throw "final output exists and collision_policy=fail: $destination"
                }
                if (Test-Path -LiteralPath $destination) {
                    $destination = Get-RerunNonOverlapPath -Path $destination -Suffix $BatchId
                }
                Move-RerunVerifiedOutput -Source $verified -Destination $destination | Out-Null
                $plan.status = 'published_non_overlap'
                $plan.published_path = $destination
                $plan.reason = 'verified output published without overlapping existing final output'
                Invoke-RerunOriginalPolicy -Plan $plan -BatchId $BatchId -HoldRoot $OriginalHoldRoot
                continue
            }
            if ($DestinationMode -eq 'publish_replace_final') {
                if (-not $ConfirmReplaceFinal) { throw 'publish_replace_final requires -ConfirmReplaceFinal.' }
                if (Test-Path -LiteralPath $destination -PathType Leaf) {
                    $backupDir = Join-Path $FinalHoldRoot $BatchId
                    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
                    $backup = Join-Path $backupDir (Split-Path -Leaf $destination)
                    if (Test-Path -LiteralPath $backup) { $backup = Get-RerunNonOverlapPath -Path $backup -Suffix $BatchId }
                    Move-Item -LiteralPath $destination -Destination $backup
                    $plan.replaced_final_hold_path = $backup
                }
                Move-RerunVerifiedOutput -Source $verified -Destination $destination | Out-Null
                $plan.status = 'published_replace_final'
                $plan.published_path = $destination
                $plan.reason = 'verified output replaced backend-planned final output'
                Invoke-RerunOriginalPolicy -Plan $plan -BatchId $BatchId -HoldRoot $OriginalHoldRoot
                continue
            }
        } catch {
            $plan.status = 'failed'
            $plan.reason = "destination policy failed: $($_.Exception.Message)"
            Write-RerunLog $plan.reason "ERROR"
        }
    }
}

function Reset-RerunStageRoot {
    param([string]$StageRoot)
    foreach ($child in @('Movies','TV')) {
        $path = Join-Path $StageRoot $child
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $CsvPath -PathType Leaf)) {
    throw "CSV not found: $CsvPath"
}
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    # Default lookup: prefer current convention, fall back to legacy `_chatgpt` name.
    foreach ($candidate in @(
        (Join-Path $script:PipelineRoot 'config\MediaPipeline_config.psd1'),
        (Join-Path $script:PipelineRoot 'config\MediaPipeline_config_chatgpt.psd1'),
        (Join-Path $PSScriptRoot 'MediaPipeline_config.psd1'),
        (Join-Path $PSScriptRoot 'MediaPipeline_config_chatgpt.psd1')
    )) {
        $probe = $candidate
        if (Test-Path -LiteralPath $probe -PathType Leaf) { $ConfigPath = $probe; break }
    }
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

$queuePlanModule = Join-Path $script:PipelineRoot 'engine\queue\queue_plan.ps1'
if (-not (Test-Path -LiteralPath $queuePlanModule)) { throw "QueuePlan module not found: $queuePlanModule" }
. $queuePlanModule

$namingModule = Join-Path $script:PipelineRoot 'engine\naming\naming.ps1'
if (-not (Test-Path -LiteralPath $namingModule)) { throw "Naming module not found: $namingModule" }
. $namingModule

$pipelinePath = Join-Path $PSScriptRoot 'MediaPipeline.ps1'
if (-not (Test-Path -LiteralPath $pipelinePath)) { throw "Pipeline script not found: $pipelinePath" }
$pwsh = Join-Path $script:PipelineRoot 'runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
if (-not (Test-Path -LiteralPath $pwsh)) { $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source }
if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
if (-not $pwsh) { throw 'PowerShell 7 host not found for nested pipeline run.' }

$localBase = Resolve-RerunPath ([string]$config['LocalBase'])
$mainOutsource = Resolve-RerunPath ([string]$config['Outsource'])
$batchId = 'rerun_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$localBaseTrimmed = $localBase.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
$localBaseParent = Split-Path -Parent $localBaseTrimmed
$localBaseLeaf = Split-Path -Leaf $localBaseTrimmed
if ([string]::IsNullOrWhiteSpace($localBaseParent) -or [string]::IsNullOrWhiteSpace($localBaseLeaf)) {
    throw "LocalBase must not be a filesystem root for CSV rerun workspace isolation: $localBase"
}
$rerunWorkspaceRoot = Join-Path $localBaseParent ($localBaseLeaf + '_RerunWorkspace')
$stageRoot = Join-Path $rerunWorkspaceRoot (Join-RerunPathParts @('RerunQueue', $batchId))
$parkRoot = Join-Path $rerunWorkspaceRoot (Join-RerunPathParts @('RerunParked', $batchId))
$manifestRoot = Join-Path $localBase 'RerunManifests'
$manifestPath = Join-Path $manifestRoot "$batchId.json"
$outputRoot = Join-Path $parkRoot 'Output'
$pendingRoot = Join-Path $localBase 'State\PendingServerPush'
$finalHoldRoot = Join-Path $localBase 'State\Rerun\FinalReplaced'
$originalHoldRoot = Join-Path $localBase 'State\Rerun\OriginalHold'

$ffprobePath = Join-Path $script:PipelineRoot 'tools\ffmpeg\bin\ffprobe.exe'
if (-not (Test-Path -LiteralPath $ffprobePath)) { $ffprobePath = '' }

$rows = @(Import-Csv -LiteralPath $CsvPath)
if ($rows.Count -eq 0) { throw "CSV contains no rows: $CsvPath" }

$plans = @(Resolve-RerunPlans -Rows $rows -Config $config -StageRoot $stageRoot -OutputRoot $outputRoot -FinalOutputRoot $mainOutsource -FfprobePath $ffprobePath)
$manifest = [ordered]@{
    batch_id = $batchId
    created_at = (Get-Date -Format 'o')
    csv_path = (Resolve-RerunPath $CsvPath)
    config_path = (Resolve-RerunPath $ConfigPath)
    dry_run = [bool]$DryRun
    plan_only = [bool]$PlanOnly
    default_stage_mode = $DefaultStageMode
    default_original_mode = $DefaultOriginalMode
    default_return_mode = $DefaultReturnMode
    execution_mode = $ExecutionMode
    destination_mode = $DestinationMode
    original_policy = $OriginalPolicy
    collision_policy = $CollisionPolicy
    window_size = [int]$WindowSize
    confirm_replace_final = [bool]$ConfirmReplaceFinal
    confirm_original_policy = [bool]$ConfirmOriginalPolicy
    confirm_delete_original = [bool]$ConfirmDeleteOriginal
    pipeline_local_base = $localBase
    rerun_workspace_root = $rerunWorkspaceRoot
    library_profiles_rewritten = [bool]$config.ContainsKey('LibraryProfiles')
    stage_root = $stageRoot
    park_root = $parkRoot
    output_root = $outputRoot
    final_output_root = $mainOutsource
    pending_publish_root = $pendingRoot
    final_hold_root = $finalHoldRoot
    original_hold_root = $originalHoldRoot
    nested_pipeline_timeout_seconds = [int]$script:RerunNestedPipelineTimeoutSeconds
    status = 'planned'
    rows = @($plans)
}

Write-RerunLog "Rerun CSV rows listed: $($rows.Count); enabled/planned: $($plans.Count)"
foreach ($plan in $plans) {
    Write-RerunLog ("PLAN [{0}] {1} -> {2}" -f $plan.status, $plan.source_path, $plan.planned_output_path)
    if ($plan.reason) { Write-RerunLog ("  reason: {0}" -f $plan.reason) "WARN" }
}

if ($PlanOnly) {
    $manifest.status = 'plan_only_complete'
    $manifest.rows = @($plans)
    Write-RerunLog "PLAN ONLY complete. No manifest, temp config, stage, park, output, or source paths were written."
    exit 0
}

New-Item -ItemType Directory -Path $parkRoot -Force | Out-Null
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
Write-RerunManifest -Path $manifestPath -Payload $manifest

if ($DryRun) {
    $manifest.status = 'dry_run_complete'
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
    Write-RerunLog "DRY RUN complete. Manifest: $manifestPath"
    exit 0
}

$pendingPlans = @($plans | Where-Object { $_.status -eq 'pending' })
if ($pendingPlans.Count -eq 0) {
    $manifest.status = 'failed'
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
    throw 'No CSV rows are executable for rerun.'
}

$chunkSize = if ($ExecutionMode -eq 'batch_stage_all') { [math]::Max(1, $pendingPlans.Count) } elseif ($ExecutionMode -eq 'windowed') { [math]::Max(1, [int]$WindowSize) } else { 1 }
$chunkIndex = 0
$pipelineExitFailures = 0
for ($offset = 0; $offset -lt $pendingPlans.Count; $offset += $chunkSize) {
    $chunkIndex++
    $take = [math]::Min($chunkSize, $pendingPlans.Count - $offset)
    $chunk = @($pendingPlans[$offset..($offset + $take - 1)])
    Reset-RerunStageRoot -StageRoot $stageRoot
    Invoke-RerunStagePlans -Plans $chunk
    $manifest.status = "staged_chunk_$chunkIndex"
    $manifest.current_phase = 'staged'
    $manifest.current_chunk = $chunkIndex
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest

    $runnable = @($chunk | Where-Object { $_.status -eq 'staged' })
    if ($runnable.Count -eq 0) {
        Write-RerunLog "Chunk $chunkIndex has no staged rows; skipping nested pipeline." "WARN"
        continue
    }

    $tempConfig = [hashtable]::new($config)
    $tempConfig['LocalBase'] = $localBase
    $tempConfig['SourceMovies'] = Join-Path $stageRoot 'Movies'
    $tempConfig['SourceTV'] = Join-Path $stageRoot 'TV'
    $tempConfig['Outsource'] = $outputRoot
    $tempConfig['ReprocessAll'] = $true
    $tempConfig['SkipStabilityCheck'] = $true
    if ($tempConfig.ContainsKey('LibraryProfiles')) {
        $tempConfig['LibraryProfiles'] = New-RerunLibraryProfiles -Profiles $config['LibraryProfiles'] -StageRoot $stageRoot -OutputRoot $outputRoot
    }
    $tempConfigPath = Join-Path $manifestRoot ("{0}.chunk_{1:D4}.config.psd1" -f $batchId, $chunkIndex)
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

    Write-RerunLog "Launching nested pipeline for CSV-authoritative batch: $batchId chunk=$chunkIndex/$([math]::Ceiling($pendingPlans.Count / $chunkSize)) rows=$($runnable.Count)"
    Write-RerunLog "Nested pipeline LocalBase: $localBase"
    Write-RerunLog "CSV rerun workspace: $rerunWorkspaceRoot"
    if ($tempConfig.ContainsKey('LibraryProfiles')) { Write-RerunLog "CSV rerun library profiles rewritten to staged roots." }
    $pipelineRun = Invoke-RerunStreamingCommand -FilePath $pwsh -ArgumentList $args -TimeoutSeconds $script:RerunNestedPipelineTimeoutSeconds -Label "nested pipeline chunk $chunkIndex"
    $pipelineExit = [int]$pipelineRun.ExitCode
    if ($pipelineRun.TimedOut) {
        Write-RerunLog "Nested pipeline timed out after $($script:RerunNestedPipelineTimeoutSeconds)s" "ERROR"
    }
    if ($pipelineExit -ne 0) { $pipelineExitFailures++ }
    Write-RerunLog "Nested pipeline chunk $chunkIndex exited with code $pipelineExit"

    Complete-RerunPlans -Plans $runnable
    Invoke-RerunDestinationPolicy -Plans $runnable -BatchId $batchId -PendingRoot $pendingRoot -FinalHoldRoot $finalHoldRoot -OriginalHoldRoot $originalHoldRoot
    Remove-RerunStagedInputs -Plans $runnable
    $manifest.status = "chunk_${chunkIndex}_complete"
    $manifest.current_phase = 'chunk_complete'
    $manifest.current_chunk = $chunkIndex
    $manifest.rows = @($plans)
    Write-RerunManifest -Path $manifestPath -Payload $manifest
}

$review = @($plans | Where-Object { $_.status -eq 'review_workspace' }).Count
$pendingPublish = @($plans | Where-Object { $_.status -eq 'pending_publish' }).Count
$published = @($plans | Where-Object { $_.status -in @('published_non_overlap','published_replace_final') }).Count
$failed = @($plans | Where-Object { $_.status -eq 'failed' }).Count
$success = $review + $pendingPublish + $published
$manifest.status = if ($failed -gt 0 -or $pipelineExitFailures -gt 0) { 'completed_with_failed_rows' } else { 'complete' }
$manifest.completed_at = (Get-Date -Format 'o')
$manifest.pipeline_exit_failures = $pipelineExitFailures
$manifest.success_count = $success
$manifest.review_workspace_count = $review
$manifest.pending_publish_count = $pendingPublish
$manifest.published_count = $published
$manifest.failed_count = $failed
$manifest.rows = @($plans)
Write-RerunManifest -Path $manifestPath -Payload $manifest

Write-RerunLog "Rerun batch complete: success=$success review=$review pending_publish=$pendingPublish published=$published failed=$failed pipeline_exit_failures=$pipelineExitFailures manifest=$manifestPath"
if ($pipelineExitFailures -gt 0 -or $failed -gt 0) { exit 1 }
exit 0
