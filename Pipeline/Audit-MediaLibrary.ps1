[CmdletBinding()]
param(
    [string]$LibraryRoot = '',
    [string]$ConfigPath = '',
    [string]$ReportRoot,
    [switch]$IncludeSidecars,
    [switch]$EmitText,
    [switch]$EmitJson,
    [switch]$EmitCsv,
    [switch]$RebuildProbeCache,
    [ValidateRange(5, 3600)]
    [int]$FfprobeTimeoutSeconds = 60,
    [ValidateRange(30, 86400)]
    [int]$AuditEnumerationTimeoutSeconds = 1800,
    [switch]$AllowSystemTools
)

$script:ProductVersion = 'v6.000'
$script:AuditVersion = '1.0'
$script:CurrentPipelineVersion = '1.0'
$script:AuditStartedAt = (Get-Date -Format 'o')
$script:AuditProgressPath = $null
$script:AuditProgressProcessed = 0
$script:AuditProgressTotal = 0
$script:AuditReportStage = ''
$script:AuditReportStepIndex = 0
$script:AuditReportStepTotal = 0
$script:AuditReportSteps = @()
$script:AuditReportCompletedSteps = @()
$script:AuditProgressLastWriteUtc = $null
$script:AuditProgressLastProcessed = -1
$script:AuditProgressMinIntervalMs = 1000
$script:AuditProgressMinFileDelta = 25
$script:AuditProgressWriteFailures = 0
$script:AuditProgressPersistenceHealthy = $true
$script:ProbeCacheSchemaVersion = '2'
$script:ProbeCacheFieldSetVersion = 'ffprobe-v2-format=format_name,duration-stream=index,codec_type,codec_name,codec_long_name,codec_tag_string,codec_tag,channels-tags=language,title-disposition=default,forced'
$script:ProbeCacheRoot = $null
$script:ProbeCacheHitCount = 0
$script:ProbeCacheMissCount = 0
$script:ProbeCacheWriteCount = 0
$script:AuditRebuildProbeCache = [bool]$RebuildProbeCache
$script:AuditAllowSystemTools = [bool]$AllowSystemTools

if (-not $PSBoundParameters.ContainsKey('IncludeSidecars')) { $IncludeSidecars = $false }
if (-not $PSBoundParameters.ContainsKey('EmitText')) { $EmitText = $false }
if (-not $PSBoundParameters.ContainsKey('EmitJson')) { $EmitJson = $true }
if (-not $PSBoundParameters.ContainsKey('EmitCsv')) { $EmitCsv = $true }

$script:AuditModuleRoot = Join-Path $PSScriptRoot 'Modules'
foreach ($auditModuleName in @(
    'MediaConstants.ps1',
    'Versioning.ps1',
    'QueuePlan.ps1',
    'Naming.ps1',
    'Audit.Progress.ps1',
    'Audit.Policy.ps1',
    'Audit.Probe.ps1',
    'Audit.Reports.ps1',
    'Audit.Scanner.ps1'
)) {
    $auditModulePath = switch ($auditModuleName) {
        'MediaConstants.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\shared\media_constants.ps1' }
        'Versioning.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\shared\versioning.ps1' }
        'Audit.Progress.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\audit\progress.ps1' }
        'Audit.Policy.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\audit\policy.ps1' }
        'Audit.Probe.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\audit\probe.ps1' }
        'Audit.Reports.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\audit\reports.ps1' }
        'Audit.Scanner.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\audit\scanner.ps1' }
        'Naming.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\naming\naming.ps1' }
        'QueuePlan.ps1' { Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\queue\queue_plan.ps1' }
        default { Join-Path $script:AuditModuleRoot $auditModuleName }
    }
    if (-not (Test-Path -LiteralPath $auditModulePath)) {
        throw "Required audit module was not found: $auditModulePath"
    }
    . $auditModulePath
}

foreach ($auditSliceName in @(
    'path_utilities.ps1',
    'scanner.ps1'
)) {
    $auditSlicePath = Join-Path (Join-Path $PSScriptRoot 'Audit-MediaLibrary') $auditSliceName
    if (-not (Test-Path -LiteralPath $auditSlicePath)) {
        throw "Required audit slice was not found: $auditSlicePath"
    }
    . $auditSlicePath
}

$script:ProductVersion = Get-MediaPipelineProductVersion
$script:AuditVersion = Get-MediaPipelineAuditSchemaVersion
$script:CurrentPipelineVersion = Get-MediaPipelineSidecarVersion

$script:SidecarIssueCodes = @(
    'missing-sidecar',
    'invalid-sidecar-json',
    'sidecar-missing-version',
    'sidecar-invalid-version',
    'sidecar-stale-version',
    'sidecar-output-mismatch',
    'sidecar-missing-route'
)

$script:HighPriorityIssueCodes = @(
    'ffprobe-open-failed',
    'missing-video-stream',
    'missing-audio-stream',
    'audio-multiple-defaults',
    'audio-default-policy-mismatch',
    'subtitle-multiple-defaults',
    'audio-missing-explicit-default',
    'commentary-default-audio',
    'tx3g-extraction-failed',
    'bdpgs-ocr-failed',
    'foreign-audio-no-subtitles',
    'foreign-audio-no-text-subtitles'
)

$script:MediumPriorityIssueCodes = @(
    'multiple-video-streams',
    'audio-track-titles-missing',
    'subtitle-track-titles-missing',
    'default-audio-language-unknown',
    'default-subtitle-language-unknown',
    'default-audio-may-transcode',
    'default-ass-subtitle',
    'ass-only-subtitles',
    'tx3g-only-subtitles',
    'tx3g-subtitles-extractable',
    'bdpgs-only-subtitles',
    'bdpgs-subtitles-ocr-candidate',
    'default-image-subtitle',
    'image-only-subtitles',
    'audio-language-tags-unknown',
    'subtitle-language-tags-unknown',
    'ambiguous-tv-naming'
)

function Write-AuditLog {
    param(
        [string]$Message,
        [ValidateSet('INFO','WARN','ERROR','DEBUG')] [string] $Level = 'INFO'
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "$timestamp [$Level] $Message"
    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        'DEBUG' { Write-Host $line -ForegroundColor Gray }
        default { Write-Host $line }
    }
}

function Resolve-ExecutablePath {
    param(
        [string]$Name,
        [string[]]$RelativeCandidates = @()
    )

    foreach ($relative in $RelativeCandidates) {
        $candidate = Join-Path $PSScriptRoot $relative
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    if (-not $script:AuditAllowSystemTools) {
        throw "Required bundled executable '$Name' was not found. Set AllowSystemTools=true only for development fallback."
    }

    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }

    throw "Required executable '$Name' was not found in the bundle or on PATH."
}

function Stop-AuditProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Label = "process"
    )
    if ($null -eq $Process) { return }
    try { if ($Process.HasExited) { return } } catch {}

    $pidText = try { [string]$Process.Id } catch { "" }
    try {
        $Process.Kill($true)
        return
    } catch {
        Write-AuditLog "Kill(true) failed for $Label PID $pidText : $($_.Exception.Message)" 'DEBUG'
    }
    if ($pidText -and (Get-Command taskkill.exe -ErrorAction SilentlyContinue)) {
        try {
            & taskkill.exe /PID $pidText /T /F 2>&1 | Out-Null
            return
        } catch {
            Write-AuditLog "taskkill fallback failed for $Label PID $pidText : $($_.Exception.Message)" 'DEBUG'
        }
    }
    try { $Process.Kill() } catch {}
}

function Get-CompletedAuditTaskText {
    param(
        [object]$Task,
        [int]$WaitMilliseconds = 1000
    )
    if ($null -eq $Task) { return "" }
    try {
        if ($Task.IsCompleted -or $Task.Wait($WaitMilliseconds)) {
            return [string]$Task.Result
        }
    } catch {}
    return ""
}

function Invoke-AuditNativeCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = 60
    )

    $psi = [System.Diagnostics.ProcessStartInfo]@{
        FileName               = $FilePath
        UseShellExecute        = $false
        RedirectStandardOutput = $true
        RedirectStandardError  = $true
        CreateNoWindow         = $true
    }
    foreach ($arg in $ArgumentList) { $psi.ArgumentList.Add([string]$arg) }

    $proc = $null
    $stdoutTask = $null
    $stderrTask = $null
    $timedOut = $false
    $startedAt = Get-Date
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
        $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        while (-not $proc.HasExited) {
            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                Stop-AuditProcessTree -Process $proc -Label (Split-Path $FilePath -Leaf)
                break
            }
            Start-Sleep -Milliseconds 100
        }
        if ($timedOut) { try { $proc.WaitForExit(5000) | Out-Null } catch {} }
        else           { try { $proc.WaitForExit() } catch {} }
    } catch {
        $stderr = "Failed to start ${FilePath}: $_"
        return @{
            ExitCode  = -2
            Output    = ""
            Error     = $stderr
            Stdout    = ""
            Stderr    = $stderr
            TimedOut  = $false
            Stopped   = $false
            ErrorCode = 'NATIVE_START_FAILED'
        }
    }

    $stdout = Get-CompletedAuditTaskText -Task $stdoutTask
    $stderr = Get-CompletedAuditTaskText -Task $stderrTask
    if ($timedOut) {
        $stderr = ($stderr + "`n[KILLED: TIMEOUT after ${TimeoutSeconds}s]").Trim()
        return @{
            ExitCode  = -1
            Output    = $stdout
            Error     = $stderr
            Stdout    = $stdout
            Stderr    = $stderr
            TimedOut  = $true
            Stopped   = $false
            ErrorCode = 'NATIVE_TIMEOUT'
        }
    }
    $exitCode = $proc.ExitCode
    $errorCode = if ($exitCode -eq 0) { 'OK' } else { "NATIVE_EXIT_$exitCode" }
    return @{
        ExitCode  = $exitCode
        Output    = $stdout
        Error     = $stderr
        Stdout    = $stdout
        Stderr    = $stderr
        TimedOut  = $false
        Stopped   = $false
        ErrorCode = $errorCode
    }
}

function Get-TagValue {
    param(
        $Object,
        [string]$Name
    )

    if ($null -eq $Object) { return '' }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return [string]$prop.Value }
    return ''
}

function Get-StreamTagValue {
    param(
        $Stream,
        [string]$Name
    )

    if ($null -eq $Stream -or $null -eq $Stream.tags) { return '' }
    return Get-TagValue -Object $Stream.tags -Name $Name
}

function Get-StreamDispositionValue {
    param(
        $Stream,
        [string]$Name
    )

    if ($null -eq $Stream -or $null -eq $Stream.disposition) { return 0 }
    $raw = Get-TagValue -Object $Stream.disposition -Name $Name
    $value = 0
    if ([int]::TryParse([string]$raw, [ref]$value)) { return $value }
    return 0
}

function Test-AuditTx3gSubtitleStream {
    param($Stream)

    if ($null -eq $Stream) { return $false }
    $codecName = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_name')
    $codecTag = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_tag_string')
    $codecLong = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_long_name')

    return (
        $codecName -eq (Get-MediaSubtitleCodecMovTextName) -or
        $codecTag -eq 'tx3g' -or
        $codecLong -match 'timed\s*text|mpeg-4\s*timed\s*text|mp4\s*timed\s*text'
    )
}

function Test-AuditBdpgsSubtitleStream {
    param($Stream)

    if ($null -eq $Stream) { return $false }
    $codecName = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_name')
    $codecTag = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_tag_string')
    $codecLong = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_long_name')

    return (
        $codecName -in (Get-MediaSubtitleCodecBdpgsNames) -or
        $codecTag -match 'pgs' -or
        $codecLong -match 'presentation\s+graphic|blu-?ray\s+pgs|hdmv\s+pgs'
    )
}

function Get-AuditTx3gGenericSrtSuffixes {
    param([array]$Tx3gSubtitleStreams)

    $suffixes = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($stream in @($Tx3gSubtitleStreams)) {
        $lang = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $stream -Name 'language')
        if ([string]::IsNullOrWhiteSpace($lang)) { $lang = 'und' }
        [void]$suffixes.Add($lang)
        if ((Get-StreamDispositionValue $stream 'forced') -eq 1) {
            [void]$suffixes.Add("$lang.forced")
        }
    }
    return @($suffixes | ForEach-Object { [string]$_ })
}

function Test-AuditSrtFileUsable {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction SilentlyContinue)) {
        return $false
    }

    try {
        $item = Get-Item -LiteralPath $Path -ErrorAction Stop
        if ($item.Length -le 0) { return $false }
        $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
        if ([string]::IsNullOrWhiteSpace($raw)) { return $false }
        $hasTiming = [regex]::IsMatch($raw, '(?m)^\s*\d{1,2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2},\d{3}')
        $hasText = @(
            $raw -split '\r?\n' |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object {
                    $_ -match '\S' -and
                    $_ -notmatch '^\d+$' -and
                    $_ -notmatch '^\d{1,2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2},\d{3}'
                }
        ).Count -gt 0
        return ($hasTiming -and $hasText)
    } catch {
        return $false
    }
}

function Get-AuditNormalizedPathKey {
    param(
        [string]$Path,
        [string]$BaseDirectory = ''
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    try {
        $candidate = $Path
        if (-not [System.IO.Path]::IsPathRooted($candidate) -and -not [string]::IsNullOrWhiteSpace($BaseDirectory)) {
            $candidate = Join-Path $BaseDirectory $candidate
        }
        return ([System.IO.Path]::GetFullPath($candidate)).ToLowerInvariant()
    } catch {
        return $Path.ToLowerInvariant()
    }
}

function Get-AuditSidecarSrtRecordPath {
    param(
        $Record,
        [string]$BaseDirectory = ''
    )

    $rawPath = [string](Get-TagValue -Object $Record -Name 'path')
    if ([string]::IsNullOrWhiteSpace($rawPath)) { return '' }
    if (-not [System.IO.Path]::IsPathRooted($rawPath) -and -not [string]::IsNullOrWhiteSpace($BaseDirectory)) {
        $rawPath = Join-Path $BaseDirectory $rawPath
    }
    try { return [System.IO.Path]::GetFullPath($rawPath) } catch { return $rawPath }
}

function Test-AuditTx3gSidecarSrtRecordUsable {
    param(
        $Record,
        [string]$BaseDirectory = ''
    )

    if ($null -eq $Record) { return $false }
    $status = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Record -Name 'status')
    if ($status -eq 'pending') { return $false }
    $path = Get-AuditSidecarSrtRecordPath -Record $Record -BaseDirectory $BaseDirectory
    if ([string]::IsNullOrWhiteSpace($path)) { return $false }
    return (Test-AuditSrtFileUsable -Path $path)
}

function Test-AuditEmbeddedSrtRecordMatchesStream {
    param(
        $Record,
        $Stream,
        [ValidateSet('tx3g','bdpgs')] [string]$SourceKind = 'tx3g'
    )

    if ($null -eq $Record -or $null -eq $Stream) { return $false }
    $codec = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Stream -Name 'codec_name')
    if ($codec -notin (Get-MediaSubtitleCodecTextNames)) { return $false }

    $recordLang = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Record -Name 'language')
    $streamLang = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $Stream -Name 'language')
    if ([string]::IsNullOrWhiteSpace($recordLang)) { $recordLang = 'und' }
    if ([string]::IsNullOrWhiteSpace($streamLang)) { $streamLang = 'und' }
    if ($recordLang -notin @('', 'und') -and $streamLang -notin @('', 'und') -and $recordLang -ne $streamLang) {
        return $false
    }

    $recordTitle = Convert-ToLowerInvariantSafe (Get-TagValue -Object $Record -Name 'title')
    $streamTitle = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $Stream -Name 'title')
    if (-not [string]::IsNullOrWhiteSpace($recordTitle)) {
        $recordTitle = $recordTitle.Trim()
        $streamTitle = $streamTitle.Trim()
        if ([string]::IsNullOrWhiteSpace($streamTitle)) { return $false }
        if ($streamTitle -ne $recordTitle -and -not $streamTitle.Contains($recordTitle)) { return $false }
    } elseif ($SourceKind -eq 'tx3g' -and $codec -eq (Get-MediaSubtitleCodecMovTextName)) {
        return $false
    }

    return $true
}

function Get-AuditValidatedEmbeddedSrtRecordCount {
    param(
        [array]$Records = @(),
        [array]$SubtitleStreams = @(),
        [ValidateSet('tx3g','bdpgs')] [string]$SourceKind = 'tx3g'
    )

    $usableTextStreams = @($SubtitleStreams | Where-Object {
        (Convert-ToLowerInvariantSafe (Get-TagValue -Object $_ -Name 'codec_name')) -in (Get-MediaSubtitleCodecTextNames)
    })
    if ($usableTextStreams.Count -eq 0) { return 0 }

    $used = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    $count = 0
    foreach ($record in @($Records | Where-Object { $null -ne $_ })) {
        foreach ($stream in $usableTextStreams) {
            $streamKey = [string](Get-TagValue -Object $stream -Name 'index')
            if ([string]::IsNullOrWhiteSpace($streamKey)) { $streamKey = [guid]::NewGuid().ToString('N') }
            if ($used.Contains($streamKey)) { continue }
            if (Test-AuditEmbeddedSrtRecordMatchesStream -Record $record -Stream $stream -SourceKind $SourceKind) {
                [void]$used.Add($streamKey)
                $count++
                break
            }
        }
    }
    return $count
}

function Get-MatchingExternalSrtFilesForAudit {
    param(
        $FileInfo,
        [array]$Tx3gSubtitleStreams = @(),
        [array]$KnownTx3gSrtFiles = @()
    )

    if ($null -eq $FileInfo -or [string]::IsNullOrWhiteSpace($FileInfo.DirectoryName)) { return @() }
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FileInfo.Name)
    if ([string]::IsNullOrWhiteSpace($baseName)) { return @() }
    $genericSuffixes = @(Get-AuditTx3gGenericSrtSuffixes -Tx3gSubtitleStreams $Tx3gSubtitleStreams)
    $knownTx3gSrtKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($known in @($KnownTx3gSrtFiles)) {
        $key = Get-AuditNormalizedPathKey -Path ([string]$known) -BaseDirectory $FileInfo.DirectoryName
        if (-not [string]::IsNullOrWhiteSpace($key)) { [void]$knownTx3gSrtKeys.Add($key) }
    }

    return @(
        Get-ChildItem -LiteralPath $FileInfo.DirectoryName -Filter '*.srt' -File -ErrorAction SilentlyContinue |
            Where-Object {
                $stem = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
                if (-not $stem.StartsWith("$baseName.", [System.StringComparison]::OrdinalIgnoreCase)) {
                    $false
                } else {
                    $suffix = $stem.Substring($baseName.Length + 1).ToLowerInvariant()
                    $pathKey = Get-AuditNormalizedPathKey -Path $_.FullName
                    $isKnownTx3gSidecar = $knownTx3gSrtKeys.Contains($pathKey)
                    $isGeneratedTx3gName = ($suffix -match '(^|\.)tx3g($|\.)')
                    $isKnownGenericMatch = ($genericSuffixes -contains $suffix) -and $isKnownTx3gSidecar
                    ($isGeneratedTx3gName -or $isKnownGenericMatch) -and (Test-AuditSrtFileUsable -Path $_.FullName)
                }
            } |
            Sort-Object Name |
            ForEach-Object { $_.FullName }
    )
}

function Get-DefaultStream {
    param([array]$Streams)

    $explicit = @($Streams | Where-Object { (Get-StreamDispositionValue $_ 'default') -eq 1 } | Select-Object -First 1)
    if ($explicit.Count -gt 0) {
        return @{
            Stream      = $explicit[0]
            IsExplicit  = $true
        }
    }

    $first = @($Streams | Select-Object -First 1)
    if ($first.Count -gt 0) {
        return @{
            Stream      = $first[0]
            IsExplicit  = $false
        }
    }

    return @{
        Stream      = $null
        IsExplicit  = $false
    }
}

function Normalize-AudioLanguagePreferenceValue {
    param([string]$Value)

    $normalized = Convert-ToLowerInvariantSafe $Value
    switch -Regex ($normalized) {
        '^(|und|unknown|undefined)$' { return 'und' }
        '^(eng|en|english)$'         { return 'eng' }
        '^(jpn|ja|japanese)$'        { return 'jpn' }
        '^(spa|es|spanish)$'         { return 'spa' }
        '^(fre|fra|fr|french)$'      { return 'fra' }
        '^(ger|deu|de|german)$'      { return 'deu' }
        '^(ita|it|italian)$'         { return 'ita' }
        '^(por|pt|portuguese)$'      { return 'por' }
        '^(rus|ru|russian)$'         { return 'rus' }
        '^(kor|ko|korean)$'          { return 'kor' }
        '^(chi|zho|zh|chinese)$'     { return 'zho' }
        default                      { return $normalized }
    }
}

function Get-NormalizedPreferredAudioLanguages {
    $preferred = @(
        $script:PreferredDefaultAudioLanguages |
            ForEach-Object { Normalize-AudioLanguagePreferenceValue ([string]$_) } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -Unique
    )
    if ($preferred.Count -eq 0) { return @('eng') }
    return $preferred
}

function Test-AudioTitleLooksLikeCommentary {
    param([string]$Title)

    if ([string]::IsNullOrWhiteSpace($Title)) { return $false }
    return ($Title -match '(?i)commentary|director|cast|audio\s*description|descriptive|behind.the.scenes|isolated\s*score')
}

function Get-AudioCodecFidelityRank {
    param([string]$Codec)

    switch (Convert-ToLowerInvariantSafe $Codec) {
        'truehd'     { return 130 }
        'mlp'        { return 125 }
        'dts-hd'     { return 120 }
        'dts_hd_ma'  { return 120 }
        'flac'       { return 115 }
        'alac'       { return 112 }
        'pcm_s24le'  { return 110 }
        'pcm_s24be'  { return 110 }
        'pcm_s16le'  { return 108 }
        'pcm_s16be'  { return 108 }
        'dts'        { return 100 }
        'eac3'       { return 90 }
        'ac3'        { return 82 }
        'opus'       { return 76 }
        'aac'        { return 72 }
        'vorbis'     { return 68 }
        'mp3'        { return 60 }
        default      { return 50 }
    }
}

function Get-AudioStreamFidelityScore {
    param($Stream)

    $channels = 0
    [void][int]::TryParse([string](Get-TagValue -Object $Stream -Name 'channels'), [ref]$channels)
    if ($channels -lt 0) { $channels = 0 }
    $channels = [math]::Min($channels, 16)

    $codecRank = Get-AudioCodecFidelityRank (Get-TagValue -Object $Stream -Name 'codec_name')
    return (($codecRank * 1000) + ($channels * 10))
}

function Get-ExpectedDefaultAudioCandidate {
    param([array]$Streams)

    if ($null -eq $Streams -or $Streams.Count -eq 0) { return $null }

    $preferred = Get-NormalizedPreferredAudioLanguages
    $candidates = [System.Collections.Generic.List[object]]::new()

    for ($i = 0; $i -lt $Streams.Count; $i++) {
        $stream = $Streams[$i]
        $lang = Normalize-AudioLanguagePreferenceValue (Get-StreamTagValue -Stream $stream -Name 'language')
        $title = Get-StreamTagValue -Stream $stream -Name 'title'
        $preferenceRank = $preferred.IndexOf($lang)
        if ($preferenceRank -lt 0) { $preferenceRank = [int]::MaxValue }

        $candidates.Add([pscustomobject]@{
            Stream         = $stream
            Index          = $i
            NormalizedLang = $lang
            Title          = $title
            IsCommentary   = (Test-AudioTitleLooksLikeCommentary $title)
            FidelityScore  = Get-AudioStreamFidelityScore $stream
            PreferenceRank = $preferenceRank
        }) | Out-Null
    }

    $pool = @($candidates | Where-Object { -not $_.IsCommentary })
    if ($pool.Count -eq 0) {
        $pool = @($candidates)
    }

    $preferredPool = @($pool | Where-Object { $_.PreferenceRank -lt [int]::MaxValue })
    if ($preferredPool.Count -gt 0) {
        $pool = $preferredPool
    }

    return ($pool | Sort-Object `
        @{ Expression = { $_.PreferenceRank } }, `
        @{ Expression = { $_.FidelityScore }; Descending = $true }, `
        @{ Expression = { $_.Index } } |
        Select-Object -First 1)
}

function Format-AudioCandidateLabel {
    param($Candidate)

    if (-not $Candidate) { return 'unknown audio track' }

    $stream = $Candidate.Stream
    $lang = if ($Candidate.NormalizedLang) { $Candidate.NormalizedLang } else { 'und' }
    $codec = Convert-ToLowerInvariantSafe (Get-TagValue -Object $stream -Name 'codec_name')
    $channels = Get-TagValue -Object $stream -Name 'channels'
    $title = $Candidate.Title

    $parts = @($lang)
    if ($codec) { $parts += $codec }
    if ($channels) { $parts += "$channels" + 'ch' }
    if (-not [string]::IsNullOrWhiteSpace($title)) {
        $parts += "'$title'"
    }
    return ($parts -join ' | ')
}

function New-AuditResult {
    param(
        $FileInfo,
        [string]$RelativePath
    )

    return [pscustomobject]@{
        Path                    = $FileInfo.FullName
        RelativePath            = $RelativePath
        FileName                = $FileInfo.Name
        MediaType               = ''
        LookupTitle             = ''
        SizeBytes               = [int64]$FileInfo.Length
        SizeGB                  = [math]::Round(($FileInfo.Length / 1GB), 3)
        Extension               = $FileInfo.Extension
        Bucket                  = 'OK'
        BucketRank              = 0
        DurationSeconds         = 0.0
        Container               = ''
        VideoCodecs             = @()
        AudioCodecs             = @()
        SubtitleCodecs          = @()
        AudioCount              = 0
        SubtitleCount           = 0
        Tx3gSubtitleCount       = 0
        Tx3gEmbeddedSrtCount    = 0
        Tx3gEmbeddedSrtRecords  = @()
        Tx3gExternalSrtCount    = 0
        Tx3gExternalSrtFiles    = @()
        Tx3gSidecarSrtFiles     = @()
        Tx3gSidecarSrtInvalidCount = 0
        Tx3gSidecarFailureCount = 0
        BdpgsSubtitleCount      = 0
        BdpgsEmbeddedSrtCount   = 0
        BdpgsEmbeddedSrtRecords = @()
        BdpgsEmbeddedSrtInvalidCount = 0
        BdpgsSidecarFailureCount = 0
        DefaultAudioCodec       = 'none'
        DefaultAudioLanguage    = 'none'
        DefaultAudioTitle       = ''
        DefaultSubtitleCodec    = 'none'
        DefaultSubtitleLanguage = 'none'
        DefaultSubtitleTitle    = ''
        HasEnglishAudio         = $false
        HasEnglishSubtitle      = $false
        HasTextSubtitle         = $false
        SidecarPath             = ''
        SidecarVersion          = ''
        SidecarRoute            = ''
        Issues                  = [System.Collections.Generic.List[object]]::new()
    }
}

function Add-AuditIssue {
    param(
        $Result,
        [ValidateSet('REVIEW','RERUN_PIPELINE','REDOWNLOAD_CANDIDATE')] [string] $Bucket,
        [string] $Code,
        [string] $Message,
        [string] $SuggestedAction = ''
    )

    $Result.Issues.Add([pscustomobject]@{
        Bucket          = $Bucket
        Code            = $Code
        Message         = $Message
        SuggestedAction = $SuggestedAction
    }) | Out-Null

    $newRank = Get-BucketRank $Bucket
    if ($newRank -gt $Result.BucketRank) {
        $Result.Bucket = $Bucket
        $Result.BucketRank = $newRank
    }
}

# Remove-PriorityMarkersFromName, Normalize-TVShowFolderName,
# Get-TVEpisodeFromFilename, Get-TVFolderSeasonInfo, and Get-TVInfoFromFile
# are provided by engine\queue\queue_plan.ps1 and engine\naming\naming.ps1, which are
# loaded in the module-loading loop above.  The inline copies that used to
# live here were removed to eliminate drift; the canonical versions in those
# modules now handle ordinal-season folders, extras-container detection,
# multi-episode filenames, and stripped-name episode extraction.

function Get-TVParseRenameSuggestion {
    param(
        $FileInfo,
        $TvInfo
    )

    $ext = [System.IO.Path]::GetExtension($FileInfo.Name)
    if ($TvInfo -and $TvInfo.Season -gt 0 -and $TvInfo.ShowName) {
        return ("{0} - S{1}E##_Episode Title{2}" -f $TvInfo.ShowName, $TvInfo.Season.ToString('00'), $ext)
    }
    return "Show Name - S01E01$ext"
}

function Test-LikelyTvLibraryItem {
    param($FileInfo)

    $path = $FileInfo.FullName
    $name = $FileInfo.Name
    if ($path -match '(?i)\\(tv|shows|series|anime)\\') { return $true }
    if ($name -match '[Ss]\d{1,2}[Ee]\d{1,2}' -or $name -match '\d{1,2}x\d{1,2}') { return $true }
    if ($name -match '(?i)\bEpisode[\s._-]*\d{1,3}\b' -or $name -match '(?i)\bEp[\s._-]*\d{1,3}\b') { return $true }
    if (Get-TVFolderSeasonInfo $FileInfo.DirectoryName) { return $true }
    return $false
}

function Normalize-LibraryLookupText {
    param(
        [string]$Text,
        [switch]$StripExtension
    )

    if ([string]::IsNullOrWhiteSpace($Text)) { return '' }

    $value = [string]$Text
    if ($StripExtension) {
        $value = [System.IO.Path]::GetFileNameWithoutExtension($value)
    }

    $value = Remove-PriorityMarkersFromName $value
    $value = $value -replace '\{[^}]+\}', ''
    $value = $value -replace '\[[^\]]+\]', ''
    $value = $value -replace '[\._]+', ' '
    $value = $value -replace '\s+', ' '
    return $value.Trim(' ', '-', '_', '.')
}

function Try-FormatMovieLookupTitle {
    param([string]$Candidate)

    $clean = Normalize-LibraryLookupText -Text $Candidate -StripExtension
    if ([string]::IsNullOrWhiteSpace($clean)) { return '' }

    if ($clean -match '^(?<title>.+?)\s*\((?<year>19\d{2}|20\d{2})\)\s*$') {
        return ("{0} ({1})" -f $Matches['title'].Trim(), $Matches['year'])
    }
    if ($clean -match '^(?<title>.+?)\s+(?<year>19\d{2}|20\d{2})\s*$') {
        return ("{0} ({1})" -f $Matches['title'].Trim(), $Matches['year'])
    }

    return $clean
}

function Get-LibraryLookupTitle {
    param(
        $FileInfo,
        [bool]$IsLikelyTv = $false,
        $TvInfo = $null
    )

    if ($IsLikelyTv) {
        if (-not $TvInfo) {
            $TvInfo = Get-TVInfoFromFile $FileInfo
        }

        $showName = if ($TvInfo -and $TvInfo.ShowName) {
            [string]$TvInfo.ShowName
        } else {
            Normalize-TVShowFolderName (Split-Path $FileInfo.DirectoryName -Leaf)
        }

        if ([string]::IsNullOrWhiteSpace($showName)) {
            $showName = Normalize-LibraryLookupText -Text (Split-Path $FileInfo.DirectoryName -Leaf)
        }
        if ([string]::IsNullOrWhiteSpace($showName)) {
            $showName = 'Unknown Show'
        }

        if ($TvInfo -and $TvInfo.Season -gt 0) {
            return ("{0} (Season {1})" -f $showName, $TvInfo.Season.ToString('00'))
        }
        return $showName
    }

    $candidates = @(
        (Split-Path $FileInfo.DirectoryName -Leaf),
        $FileInfo.Name
    )

    foreach ($candidate in $candidates) {
        $formatted = Try-FormatMovieLookupTitle -Candidate $candidate
        if ($formatted -match '\(\d{4}\)$') {
            return $formatted
        }
    }

    foreach ($candidate in $candidates) {
        $formatted = Try-FormatMovieLookupTitle -Candidate $candidate
        if (-not [string]::IsNullOrWhiteSpace($formatted)) {
            return $formatted
        }
    }

    return (Normalize-LibraryLookupText -Text $FileInfo.Name -StripExtension)
}

function Analyze-Sidecar {
    param(
        $Result,
        $FileInfo
    )

    $sidecarPath = Get-SidecarPath $FileInfo.FullName
    $Result.SidecarPath = $sidecarPath

    if (-not (Test-Path -LiteralPath $sidecarPath)) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'missing-sidecar' -Message 'No .pipeline.json sidecar was found next to this library file.' -SuggestedAction 'Rerun the file through MediaPipeline if you want current sidecar metadata and normalization.'
        return
    }

    try {
        $sidecar = Get-Content -LiteralPath $sidecarPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'invalid-sidecar-json' -Message "The sidecar could not be parsed: $($_.Exception.Message)" -SuggestedAction 'Rewrite the output through MediaPipeline or repair the sidecar JSON.'
        return
    }

    $sidecarVersion = [string](Get-TagValue -Object $sidecar -Name 'pipeline_version')
    $Result.SidecarVersion = $sidecarVersion
    $Result.SidecarRoute = [string](Get-TagValue -Object $sidecar -Name 'route')

    $rawTx3gFailureValues = @()
    $tx3gFailureProp = $sidecar.PSObject.Properties['tx3g_srt_failures']
    if ($tx3gFailureProp) {
        $rawTx3gFailureValues = @($tx3gFailureProp.Value | Where-Object { $null -ne $_ })
    }
    $legacyBdpgsFailures = @($rawTx3gFailureValues | Where-Object { [string]$_.ErrorCode -like 'SUBTITLE_BDPGS_*' })
    $tx3gFailures = @($rawTx3gFailureValues | Where-Object { [string]$_.ErrorCode -notlike 'SUBTITLE_BDPGS_*' })
    $Result.Tx3gSidecarFailureCount = $tx3gFailures.Count
    if ($tx3gFailures.Count -gt 0) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'tx3g-extraction-failed' -Message "The pipeline sidecar records $($tx3gFailures.Count) failed tx3g-to-SRT extraction attempt(s)." -SuggestedAction 'Rerun this file after reviewing the subtitle extraction failure report/repro command.'
    }

    $bdpgsEmbeddedProp = $sidecar.PSObject.Properties['bdpgs_embedded_srt_tracks']
    if ($bdpgsEmbeddedProp) {
        $Result.BdpgsEmbeddedSrtRecords = @($bdpgsEmbeddedProp.Value | Where-Object { $null -ne $_ })
    }
    $bdpgsFailures = @()
    $bdpgsFailureProp = $sidecar.PSObject.Properties['bdpgs_srt_failures']
    if ($bdpgsFailureProp) {
        $bdpgsFailures = @($bdpgsFailureProp.Value | Where-Object { $null -ne $_ })
    } else {
        $bdpgsFailures = @($legacyBdpgsFailures)
    }
    $Result.BdpgsSidecarFailureCount = $bdpgsFailures.Count
    if ($bdpgsFailures.Count -gt 0) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'bdpgs-ocr-failed' -Message "The pipeline sidecar records $($bdpgsFailures.Count) failed BDPGS OCR attempt(s)." -SuggestedAction 'Configure the BDPGS OCR tool/Tesseract data, inspect the saved repro command, or disable ConvertBdpgsToSrt to keep image subtitles without OCR.'
    }

    $tx3gTrackProp = $sidecar.PSObject.Properties['tx3g_srt_tracks']
    if ($tx3gTrackProp) {
        $validTx3gSidecarSrtFiles = [System.Collections.Generic.List[string]]::new()
        $invalidTx3gSidecarSrtRecords = 0
        $baseDirectory = $FileInfo.DirectoryName
        foreach ($trackRecord in @($tx3gTrackProp.Value | Where-Object { $null -ne $_ })) {
            if (Test-AuditTx3gSidecarSrtRecordUsable -Record $trackRecord -BaseDirectory $baseDirectory) {
                $path = Get-AuditSidecarSrtRecordPath -Record $trackRecord -BaseDirectory $baseDirectory
                if (-not [string]::IsNullOrWhiteSpace($path)) { $validTx3gSidecarSrtFiles.Add($path) }
            } else {
                $invalidTx3gSidecarSrtRecords++
            }
        }
        $Result.Tx3gSidecarSrtFiles = @(
            $validTx3gSidecarSrtFiles |
                Sort-Object -Unique
        )
        $Result.Tx3gSidecarSrtInvalidCount = $invalidTx3gSidecarSrtRecords
        if ($invalidTx3gSidecarSrtRecords -gt 0) {
            Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'tx3g-srt-sidecar-stale' -Message "The pipeline sidecar lists $invalidTx3gSidecarSrtRecords tx3g SRT sidecar record(s) that are missing, pending, empty, or not parseable." -SuggestedAction 'Rerun this file or regenerate tx3g SRT sidecars so audit can verify usable subtitle output.'
        }
    }

    $tx3gEmbeddedProp = $sidecar.PSObject.Properties['tx3g_embedded_srt_tracks']
    if ($tx3gEmbeddedProp) {
        $Result.Tx3gEmbeddedSrtRecords = @($tx3gEmbeddedProp.Value | Where-Object { $null -ne $_ })
    }

    if (-not $sidecarVersion) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'sidecar-missing-version' -Message 'The sidecar is present but has no pipeline_version field.' -SuggestedAction 'Rerun the file through MediaPipeline to refresh provenance metadata.'
    } elseif (-not (Test-PipelineVersionString $sidecarVersion)) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'sidecar-invalid-version' -Message "The sidecar pipeline_version '$sidecarVersion' is not a valid semantic version." -SuggestedAction 'Rerun the file through MediaPipeline to refresh provenance metadata.'
    } elseif (Compare-PipelineVersion $sidecarVersion $script:MinPipelineVersion) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'sidecar-stale-version' -Message "The sidecar pipeline version '$sidecarVersion' is older than the current minimum '$($script:MinPipelineVersion)'." -SuggestedAction 'Rerun the file through MediaPipeline if you want it standardized to the current release.'
    }

    $outputFile = [string](Get-TagValue -Object $sidecar -Name 'output_file')
    if ($outputFile -and $outputFile -ne $FileInfo.Name) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'sidecar-output-mismatch' -Message "The sidecar output_file '$outputFile' does not match the current file name '$($FileInfo.Name)'." -SuggestedAction 'Verify the file was not renamed independently of its sidecar.'
    }

    if (-not $Result.SidecarRoute) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'sidecar-missing-route' -Message 'The sidecar is present but has no route field.' -SuggestedAction 'If you rerun the file through MediaPipeline, the sidecar will include the current route metadata.'
    }
}

function Add-AuditSubtitleCompatibilityIssues {
    param(
        $Result,
        [array]$SubtitleStreams = @(),
        [array]$Tx3gSubtitleStreams = @(),
        [array]$BdpgsSubtitleStreams = @(),
        $DefaultSubtitle = $null
    )

    if (@($SubtitleStreams).Count -eq 0) { return }

    $subtitleLangs = @($SubtitleStreams | ForEach-Object {
        $lang = (Get-StreamTagValue -Stream $_ -Name 'language')
        if ($lang) { Convert-ToLowerInvariantSafe $lang } else { 'und' }
    } | Select-Object -Unique)
    $textSubtitleCodecs = Get-MediaSubtitleCodecTextNames
    $externalFriendlyTextCodecs = Get-MediaSubtitleCodecExternalFriendlyTextNames
    $assSubtitleCodecs = Get-MediaSubtitleCodecAssNames
    $imageSubtitleCodecs = Get-MediaSubtitleCodecImageNames

    $hasTextSubs = @($Result.SubtitleCodecs | Where-Object { $_ -in $textSubtitleCodecs }).Count -gt 0
    $hasExternalFriendlyTextSubs = @($Result.SubtitleCodecs | Where-Object { $_ -in $externalFriendlyTextCodecs }).Count -gt 0
    $hasTx3gSubs = @($Tx3gSubtitleStreams).Count -gt 0
    $hasBdpgsSubs = @($BdpgsSubtitleStreams).Count -gt 0
    $hasAssSubs  = @($Result.SubtitleCodecs | Where-Object { $_ -in $assSubtitleCodecs }).Count -gt 0
    $hasImageSubs = @($Result.SubtitleCodecs | Where-Object { $_ -in $imageSubtitleCodecs }).Count -gt 0
    $Result.HasTextSubtitle = $hasTextSubs

    if ($hasTx3gSubs -and -not $hasExternalFriendlyTextSubs -and -not $hasAssSubs -and -not $hasImageSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'tx3g-only-subtitles' -Message 'This file only has embedded MP4 Timed Text / tx3g subtitles and no embedded SRT/WebVTT-style subtitle track.' -SuggestedAction 'Run MediaPipeline with ConvertTx3gToSrt enabled to mux a more compatible subtitle track; enable CreateExternalTx3gSrtSidecars only if you also want external SRT files.'
    }

    $tx3gValidatedSrtCount = $Result.Tx3gExternalSrtCount + $Result.Tx3gEmbeddedSrtCount
    if ($hasTx3gSubs -and $tx3gValidatedSrtCount -lt @($Tx3gSubtitleStreams).Count) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'tx3g-subtitles-extractable' -Message ("ffprobe found {0} embedded tx3g subtitle track(s); {1} validated converted SRT output(s) were found ({2} external, {3} embedded)." -f @($Tx3gSubtitleStreams).Count, $tx3gValidatedSrtCount, $Result.Tx3gExternalSrtCount, $Result.Tx3gEmbeddedSrtCount) -SuggestedAction 'Run MediaPipeline with ConvertTx3gToSrt enabled to mux converted subtitles without re-encoding video; enable CreateExternalTx3gSrtSidecars when external SRT files are desired.'
    }

    if ($hasBdpgsSubs -and -not $hasExternalFriendlyTextSubs -and -not $hasAssSubs -and -not $hasTx3gSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'bdpgs-only-subtitles' -Message 'This file only has embedded Blu-ray PGS image subtitles and no embedded SRT/WebVTT-style subtitle track.' -SuggestedAction 'Keep BDPGS for MKV playback, or enable ConvertBdpgsToSrt with a configured OCR tool when text subtitles are required.'
    }

    if ($hasBdpgsSubs -and $Result.BdpgsEmbeddedSrtCount -lt @($BdpgsSubtitleStreams).Count) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'bdpgs-subtitles-ocr-candidate' -Message ("ffprobe found {0} embedded BDPGS subtitle track(s); {1} pipeline OCR SRT track record(s) were found." -f @($BdpgsSubtitleStreams).Count, $Result.BdpgsEmbeddedSrtCount) -SuggestedAction 'Enable ConvertBdpgsToSrt only after configuring a PGS/SUP OCR tool such as PgsToSrt with Tesseract language data.'
    }

    if ($hasAssSubs -and -not $hasTextSubs -and -not $hasImageSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'ass-only-subtitles' -Message 'This file only has ASS/SSA subtitles and no SRT-style text track.' -SuggestedAction 'Review on target Plex clients if subtitle compatibility matters.'
    }

    if ($hasImageSubs -and -not $hasTextSubs -and -not $hasAssSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'image-only-subtitles' -Message 'This file only has image-based subtitles and no text subtitle track.' -SuggestedAction 'Review on target Plex clients if subtitle compatibility matters.'
    }

    if ($subtitleLangs.Count -gt 0 -and @($subtitleLangs | Where-Object { $_ -notin @('', 'und') }).Count -eq 0) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'subtitle-language-tags-unknown' -Message 'All subtitle tracks are missing language tags or are tagged as und.' -SuggestedAction 'Review subtitle metadata if Plex language selection matters.'
    }
    if (@($SubtitleStreams).Count -gt 1) {
        $untitledSubtitleCount = @($SubtitleStreams | Where-Object { [string]::IsNullOrWhiteSpace((Get-StreamTagValue -Stream $_ -Name 'title')) }).Count
        if ($untitledSubtitleCount -gt 0) {
            Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'subtitle-track-titles-missing' -Message "$untitledSubtitleCount subtitle track(s) are missing title metadata in a multi-subtitle file." -SuggestedAction 'Consider rerunning or retagging so Plex subtitle selection is clearer.'
        }
    }

    if ($DefaultSubtitle -and $Result.DefaultSubtitleCodec -in $assSubtitleCodecs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'default-ass-subtitle' -Message "Default subtitle codec '$($Result.DefaultSubtitleCodec)' is less Plex-friendly than SRT." -SuggestedAction 'Review subtitle behavior on your target clients.'
    }

    if ($DefaultSubtitle -and $Result.DefaultSubtitleCodec -in $imageSubtitleCodecs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'default-image-subtitle' -Message "Default subtitle codec '$($Result.DefaultSubtitleCodec)' is image-based." -SuggestedAction 'Review subtitle behavior on your target clients.'
    }
    if ($DefaultSubtitle -and $Result.DefaultSubtitleLanguage -eq 'und') {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'default-subtitle-language-unknown' -Message 'Default subtitle is tagged as und / unknown language.' -SuggestedAction 'Review or retag the default subtitle language if Plex language selection matters.'
    }
}

function Get-AuditResultForFile {
    param($FileInfo)

    $result = New-AuditResult -FileInfo $FileInfo -RelativePath (Get-RelativePathSafe -RootPath $script:LibraryRootResolved -FullPath $FileInfo.FullName)
    $isLikelyTv = Test-LikelyTvLibraryItem $FileInfo
    $tvInfo = $null
    if ($isLikelyTv) {
        $tvInfo = Get-TVInfoFromFile $FileInfo
        $result.MediaType = 'TV'
    } else {
        $result.MediaType = 'Movie'
    }
    $result.LookupTitle = Get-LibraryLookupTitle -FileInfo $FileInfo -IsLikelyTv $isLikelyTv -TvInfo $tvInfo

    if ($IncludeSidecars) {
        Analyze-Sidecar -Result $result -FileInfo $FileInfo
    }

    $probe = Invoke-FfprobeJsonCached -FileInfo $FileInfo
    if (-not $probe.Success) {
        Add-AuditIssue -Result $result -Bucket 'REDOWNLOAD_CANDIDATE' -Code 'ffprobe-open-failed' -Message $probe.Error -SuggestedAction 'Redownload or replace the file if it does not open cleanly in ffprobe/Plex.'
        return $result
    }

    $data = $probe.Data
    $streams = @($data.streams | Where-Object { $null -ne $_ })
    $videoStreams = @($streams | Where-Object { $_.codec_type -eq 'video' })
    $audioStreams = @($streams | Where-Object { $_.codec_type -eq 'audio' })
    $subtitleStreams = @($streams | Where-Object { $_.codec_type -eq 'subtitle' })
    $tx3gSubtitleStreams = @($subtitleStreams | Where-Object { Test-AuditTx3gSubtitleStream $_ })
    $bdpgsSubtitleStreams = @($subtitleStreams | Where-Object { Test-AuditBdpgsSubtitleStream $_ })
    if (@($result.Tx3gEmbeddedSrtRecords).Count -gt 0) {
        $result.Tx3gEmbeddedSrtCount = Get-AuditValidatedEmbeddedSrtRecordCount -Records @($result.Tx3gEmbeddedSrtRecords) -SubtitleStreams $subtitleStreams -SourceKind 'tx3g'
        $result.Tx3gEmbeddedSrtInvalidCount = @($result.Tx3gEmbeddedSrtRecords).Count - $result.Tx3gEmbeddedSrtCount
        if ($result.Tx3gEmbeddedSrtInvalidCount -gt 0) {
            Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'tx3g-embedded-srt-stale' -Message "The pipeline sidecar lists $($result.Tx3gEmbeddedSrtInvalidCount) tx3g embedded SRT conversion record(s) that do not match a current text subtitle stream." -SuggestedAction 'Rerun this file through MediaPipeline or refresh the sidecar if the file was modified outside the pipeline.'
        }
    }
    if (@($result.BdpgsEmbeddedSrtRecords).Count -gt 0) {
        $result.BdpgsEmbeddedSrtCount = Get-AuditValidatedEmbeddedSrtRecordCount -Records @($result.BdpgsEmbeddedSrtRecords) -SubtitleStreams $subtitleStreams -SourceKind 'bdpgs'
        $result.BdpgsEmbeddedSrtInvalidCount = @($result.BdpgsEmbeddedSrtRecords).Count - $result.BdpgsEmbeddedSrtCount
        if ($result.BdpgsEmbeddedSrtInvalidCount -gt 0) {
            Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'bdpgs-embedded-srt-stale' -Message "The pipeline sidecar lists $($result.BdpgsEmbeddedSrtInvalidCount) BDPGS OCR SRT record(s) that do not match a current text subtitle stream." -SuggestedAction 'Rerun this file through MediaPipeline or refresh the sidecar if the file was modified outside the pipeline.'
        }
    }

    $result.Container = [string](Get-TagValue -Object $data.format -Name 'format_name')
    $result.DurationSeconds = [math]::Round((Try-ParseDoubleInvariant (Get-TagValue -Object $data.format -Name 'duration')), 3)
    $result.VideoCodecs = @($videoStreams | ForEach-Object { Convert-ToLowerInvariantSafe $_.codec_name } | Where-Object { $_ } | Select-Object -Unique)
    $result.AudioCodecs = @($audioStreams | ForEach-Object { Convert-ToLowerInvariantSafe $_.codec_name } | Where-Object { $_ } | Select-Object -Unique)
    $result.SubtitleCodecs = @($subtitleStreams | ForEach-Object { Convert-ToLowerInvariantSafe $_.codec_name } | Where-Object { $_ } | Select-Object -Unique)
    $result.AudioCount = $audioStreams.Count
    $result.SubtitleCount = $subtitleStreams.Count
    $result.Tx3gSubtitleCount = $tx3gSubtitleStreams.Count
    $result.BdpgsSubtitleCount = $bdpgsSubtitleStreams.Count
    if ($tx3gSubtitleStreams.Count -gt 0) {
        $matchingExternalSrts = @(Get-MatchingExternalSrtFilesForAudit -FileInfo $FileInfo -Tx3gSubtitleStreams $tx3gSubtitleStreams -KnownTx3gSrtFiles @($result.Tx3gSidecarSrtFiles))
        $result.Tx3gExternalSrtFiles = @($matchingExternalSrts)
        $result.Tx3gExternalSrtCount = $matchingExternalSrts.Count
    }

    if ($videoStreams.Count -eq 0) {
        Add-AuditIssue -Result $result -Bucket 'REDOWNLOAD_CANDIDATE' -Code 'missing-video-stream' -Message 'ffprobe found no video streams in this file.' -SuggestedAction 'Redownload or replace the file.'
    }
    if ($videoStreams.Count -gt 1) {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'multiple-video-streams' -Message "ffprobe found $($videoStreams.Count) video streams in this file." -SuggestedAction 'Review whether the extra video streams are intentional.'
    }

    if ($audioStreams.Count -eq 0) {
        Add-AuditIssue -Result $result -Bucket 'REDOWNLOAD_CANDIDATE' -Code 'missing-audio-stream' -Message 'ffprobe found no audio streams in this file.' -SuggestedAction 'Redownload or replace the file.'
    }

    if ($result.DurationSeconds -le 0) {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'missing-duration' -Message 'Container duration could not be read from ffprobe.' -SuggestedAction 'Play-test the file or rerun it through the pipeline if other issues are present.'
    }

    $defaultAudioInfo = Get-DefaultStream -Streams $audioStreams
    $defaultAudio = $defaultAudioInfo.Stream
    $expectedDefaultAudioCandidate = Get-ExpectedDefaultAudioCandidate -Streams $audioStreams
    $explicitDefaultAudioCount = @($audioStreams | Where-Object { (Get-StreamDispositionValue $_ 'default') -eq 1 }).Count
    if ($explicitDefaultAudioCount -gt 1) {
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'audio-multiple-defaults' -Message "Multiple audio tracks ($explicitDefaultAudioCount) are marked default." -SuggestedAction 'Rerun the file through MediaPipeline or clear the extra default audio flags.'
    }
    if ($defaultAudio) {
        $result.DefaultAudioCodec = Convert-ToLowerInvariantSafe $defaultAudio.codec_name
        $audioLang = (Get-StreamTagValue -Stream $defaultAudio -Name 'language')
        $result.DefaultAudioLanguage = if ($audioLang) { Convert-ToLowerInvariantSafe $audioLang } else { 'und' }
        $result.DefaultAudioTitle = Get-StreamTagValue -Stream $defaultAudio -Name 'title'
    }

    $defaultSubtitleInfo = Get-DefaultStream -Streams $subtitleStreams
    $defaultSubtitle = $defaultSubtitleInfo.Stream
    $explicitDefaultSubtitleCount = @($subtitleStreams | Where-Object { (Get-StreamDispositionValue $_ 'default') -eq 1 }).Count
    if ($explicitDefaultSubtitleCount -gt 1) {
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'subtitle-multiple-defaults' -Message "Multiple subtitle tracks ($explicitDefaultSubtitleCount) are marked default." -SuggestedAction 'Rerun the file through MediaPipeline or clear the extra default subtitle flags.'
    }
    if ($defaultSubtitle) {
        $result.DefaultSubtitleCodec = Convert-ToLowerInvariantSafe $defaultSubtitle.codec_name
        $subLang = (Get-StreamTagValue -Stream $defaultSubtitle -Name 'language')
        $result.DefaultSubtitleLanguage = if ($subLang) { Convert-ToLowerInvariantSafe $subLang } else { 'und' }
        $result.DefaultSubtitleTitle = Get-StreamTagValue -Stream $defaultSubtitle -Name 'title'
    }

    if ($audioStreams.Count -gt 1 -and -not $defaultAudioInfo.IsExplicit) {
        $expectedLabel = if ($expectedDefaultAudioCandidate) { Format-AudioCandidateLabel $expectedDefaultAudioCandidate } else { 'the preferred non-commentary track' }
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'audio-missing-explicit-default' -Message "Multiple audio tracks are present, but none is marked default. Expected default: $expectedLabel." -SuggestedAction 'Rerun the file through MediaPipeline to normalize audio defaults.'
    }
    if ($explicitDefaultAudioCount -eq 1 -and $defaultAudio -and $expectedDefaultAudioCandidate) {
        $actualIndex = [string](Get-TagValue -Object $defaultAudio -Name 'index')
        $expectedIndex = [string](Get-TagValue -Object $expectedDefaultAudioCandidate.Stream -Name 'index')
        if ($actualIndex -ne $expectedIndex) {
            Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'audio-default-policy-mismatch' -Message ("Default audio track '{0}' does not match the configured preferred-language / highest-fidelity policy. Expected: {1}." -f (Format-AudioCandidateLabel ([pscustomobject]@{
                Stream         = $defaultAudio
                NormalizedLang = Normalize-AudioLanguagePreferenceValue (Get-StreamTagValue -Stream $defaultAudio -Name 'language')
                Title          = Get-StreamTagValue -Stream $defaultAudio -Name 'title'
            })), (Format-AudioCandidateLabel $expectedDefaultAudioCandidate)) -SuggestedAction 'Rerun the file through MediaPipeline or retag the default audio track to match the configured policy.'
        }
    }
    if ($audioStreams.Count -gt 1) {
        $untitledAudioCount = @($audioStreams | Where-Object { [string]::IsNullOrWhiteSpace((Get-StreamTagValue -Stream $_ -Name 'title')) }).Count
        if ($untitledAudioCount -gt 0) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'audio-track-titles-missing' -Message "$untitledAudioCount audio track(s) are missing title metadata in a multi-audio file." -SuggestedAction 'Consider rerunning or retagging so Plex track selection is clearer.'
        }
    }

    if ($defaultAudio -and $result.DefaultAudioTitle -match '(?i)commentary') {
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'commentary-default-audio' -Message "Default audio title '$($result.DefaultAudioTitle)' looks like commentary." -SuggestedAction 'Rerun the file or manually clear the commentary track as default.'
    }
    if ($defaultAudio -and $result.DefaultAudioLanguage -eq 'und') {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'default-audio-language-unknown' -Message 'Default audio is tagged as und / unknown language.' -SuggestedAction 'Review or retag the default audio language if Plex language selection matters.'
    }

    if ($defaultAudio -and $result.DefaultAudioCodec -and $result.DefaultAudioCodec -notin $script:CompatibleAudioCodecs) {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'default-audio-may-transcode' -Message "Default audio codec '$($result.DefaultAudioCodec)' is outside the current compatible-audio list." -SuggestedAction 'Play-test this file on Plex/Shield if direct play matters.'
    }

    $audioLangs = @()
    if ($audioStreams.Count -gt 0) {
        $audioLangs = @($audioStreams | ForEach-Object {
            $lang = (Get-StreamTagValue -Stream $_ -Name 'language')
            if ($lang) { Convert-ToLowerInvariantSafe $lang } else { 'und' }
        } | Select-Object -Unique)
        if ($audioLangs.Count -gt 0 -and @($audioLangs | Where-Object { $_ -notin @('', 'und') }).Count -eq 0) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'audio-language-tags-unknown' -Message 'All audio tracks are missing language tags or are tagged as und.' -SuggestedAction 'Review metadata if language selection matters in Plex.'
        }
    }

    if ($subtitleStreams.Count -gt 0) {
        Add-AuditSubtitleCompatibilityIssues -Result $result -SubtitleStreams $subtitleStreams -Tx3gSubtitleStreams $tx3gSubtitleStreams -BdpgsSubtitleStreams $bdpgsSubtitleStreams -DefaultSubtitle $defaultSubtitle
    }

    $englishAudioLangs = @('eng', 'en')
    $englishSubtitleLangs = @('eng', 'en')
    $result.HasEnglishAudio = @($audioLangs | Where-Object { $_ -in $englishAudioLangs }).Count -gt 0
    $result.HasEnglishSubtitle = @($subtitleStreams | Where-Object {
        $codec = Convert-ToLowerInvariantSafe $_.codec_name
        $lang = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $_ -Name 'language')
        $codec -in (Get-MediaSubtitleCodecTextNames) -and $lang -in $englishSubtitleLangs
    }).Count -gt 0

    $knownAudioLangs = @($audioLangs | Where-Object { $_ -notin @('', 'und') })
    $hasKnownNonEnglishAudio = @($knownAudioLangs | Where-Object { $_ -notin $englishAudioLangs }).Count -gt 0
    if ($hasKnownNonEnglishAudio -and -not $result.HasEnglishAudio) {
        if ($subtitleStreams.Count -eq 0) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'foreign-audio-no-subtitles' -Message 'This file has non-English audio and no subtitle tracks.' -SuggestedAction 'Review whether this needs subtitles for normal playback.'
        } elseif (-not $result.HasTextSubtitle) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'foreign-audio-no-text-subtitles' -Message 'This file has non-English audio but no text subtitle track.' -SuggestedAction 'Review whether you want a text subtitle track for easier Plex playback.'
        }
    }

    if ($isLikelyTv) {
        if (-not $tvInfo.IsReliable) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'ambiguous-tv-naming' -Message $tvInfo.ParseError -SuggestedAction ("Suggested rename: {0}" -f (Get-TVParseRenameSuggestion -FileInfo $FileInfo -TvInfo $tvInfo))
        }
    }

    return $result
}

try {
    $script:ConfigPathResolved = $null
    $config = $null
    if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
        # Default lookup: prefer V7 convention, fall back to legacy `_chatgpt` name.
        foreach ($candidate in @('MediaPipeline_config.psd1', 'MediaPipeline_config_chatgpt.psd1')) {
            $probe = Join-Path $PSScriptRoot $candidate
            if (Test-Path -LiteralPath $probe) { $ConfigPath = $probe; break }
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($ConfigPath) -and (Test-Path -LiteralPath $ConfigPath)) {
        $script:ConfigPathResolved = Resolve-ExistingPath $ConfigPath
        $config = Import-PowerShellDataFile -LiteralPath $script:ConfigPathResolved
    }

    if ([string]::IsNullOrWhiteSpace($LibraryRoot)) {
        $LibraryRoot = Get-AuditDefaultLibraryRootFromConfig -Config $config
    }
    if ([string]::IsNullOrWhiteSpace($LibraryRoot)) {
        throw "LibraryRoot was not provided. Pass -LibraryRoot explicitly or set SourceMovies/SourceTV in the config with a shared parent root."
    }

    $script:LibraryRootResolved = Resolve-ExistingPath $LibraryRoot
    if (-not (Test-IsUncPath $script:LibraryRootResolved) -and -not (Test-Path -LiteralPath $script:LibraryRootResolved)) {
        throw "Library root was not found: $LibraryRoot"
    }

    if ($config -and $config.ContainsKey('AllowSystemTools')) {
        try {
            $script:AuditAllowSystemTools = [bool]$config.AllowSystemTools -or [bool]$AllowSystemTools
        } catch {
            $script:AuditAllowSystemTools = [bool]$AllowSystemTools
        }
    }

    $script:PriorityMarkers = @('!', '[NOW]')
    if ($config -and $config.ContainsKey('PriorityMarkers') -and @($config.PriorityMarkers).Count -gt 0) {
        $script:PriorityMarkers = @($config.PriorityMarkers | ForEach-Object { [string]$_ })
    }

    $script:CompatibleAudioCodecs = @('aac','ac3','eac3','mp3','opus','vorbis','flac','truehd','mlp')
    if ($config -and $config.ContainsKey('CompatibleAudioCodecs') -and @($config.CompatibleAudioCodecs).Count -gt 0) {
        $script:CompatibleAudioCodecs = @($config.CompatibleAudioCodecs | ForEach-Object { ([string]$_).ToLowerInvariant() })
    }

    $script:PreferredDefaultAudioLanguages = @('english')
    if ($config -and $config.ContainsKey('PreferredDefaultAudioLanguages') -and @($config.PreferredDefaultAudioLanguages).Count -gt 0) {
        $script:PreferredDefaultAudioLanguages = @($config.PreferredDefaultAudioLanguages | ForEach-Object { [string]$_ })
    }

    $script:ValidExtensions = @('.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts', '.m2ts')
    if ($config -and $config.ContainsKey('ValidExtensions') -and @($config.ValidExtensions).Count -gt 0) {
        $script:ValidExtensions = @($config.ValidExtensions | ForEach-Object { ([string]$_).ToLowerInvariant() })
    }

    $script:MinPipelineVersion = $script:CurrentPipelineVersion
    if ($config -and $config.ContainsKey('MinPipelineVersion') -and $config.MinPipelineVersion) {
        $candidate = [string]$config.MinPipelineVersion
        if (Test-PipelineVersionString $candidate) {
            if (Compare-PipelineVersion $script:CurrentPipelineVersion $candidate) {
                $script:MinPipelineVersion = $script:CurrentPipelineVersion
            } else {
                $script:MinPipelineVersion = $candidate
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($ReportRoot)) {
        if ($config -and $config.ContainsKey('LocalBase') -and $config.LocalBase) {
            $ReportRoot = Join-Path ([string]$config.LocalBase) 'AuditReports'
        } else {
            $ReportRoot = Join-Path $PSScriptRoot 'AuditReports'
        }
    }
    $script:ReportRootResolved = Resolve-ExistingPath $ReportRoot
    if (-not (Test-Path -LiteralPath $script:ReportRootResolved)) {
        New-Item -ItemType Directory -Path $script:ReportRootResolved -Force | Out-Null
    }
    $script:AuditProgressPath = Join-Path $script:ReportRootResolved 'audit_progress.json'
    $script:ProbeCacheRoot = Join-Path $script:ReportRootResolved 'ProbeCache'
    if (-not (Test-Path -LiteralPath $script:ProbeCacheRoot)) {
        New-Item -ItemType Directory -Path $script:ProbeCacheRoot -Force | Out-Null
    }
    Test-AuditProgressPersistence | Out-Null
    if ($script:AuditRebuildProbeCache) {
        Clear-ProbeCache
        if (-not (Test-Path -LiteralPath $script:ProbeCacheRoot)) {
            New-Item -ItemType Directory -Path $script:ProbeCacheRoot -Force | Out-Null
        }
    }

    $script:FfprobePath = Resolve-ExecutablePath -Name 'ffprobe' -RelativeCandidates @('Tools\ffmpeg\bin\ffprobe.exe')

    Write-AuditLog "===== LIBRARY AUDIT START $($script:ProductVersion) (audit $($script:AuditVersion)) ====="
    Write-AuditLog "Library root       : $($script:LibraryRootResolved)"
    Write-AuditLog "Report root        : $($script:ReportRootResolved)"
    Write-AuditLog "Product ver        : $($script:ProductVersion)"
    Write-AuditLog "Probe cache root   : $($script:ProbeCacheRoot)"
    Write-AuditLog "Config path        : $(if ($script:ConfigPathResolved) { $script:ConfigPathResolved } else { '(none)' })"
    Write-AuditLog "ffprobe            : $($script:FfprobePath)"
    Write-AuditLog "Enumeration timeout: $($AuditEnumerationTimeoutSeconds)s"
    Write-AuditLog "Progress health    : $(if ($script:AuditProgressPersistenceHealthy) { 'healthy' } else { 'unavailable' })"
    Write-AuditLog "Include sidecars   : $IncludeSidecars"
    Write-AuditLog "Rebuild probe cache: $($script:AuditRebuildProbeCache)"
    Write-AuditLog "Min pipeline ver   : $($script:MinPipelineVersion)"
    Write-AuditProgress -Status 'starting' -ProcessedFiles 0 -TotalFiles 0 -CurrentOperation 'Initializing audit run.'

    Write-AuditProgress -Status 'starting' -ProcessedFiles 0 -TotalFiles 0 -CurrentOperation 'Enumerating media files.'
    $mediaFiles = @(Get-AuditMediaFilesBounded -RootPath $script:LibraryRootResolved -TimeoutSeconds $AuditEnumerationTimeoutSeconds)

    Write-AuditLog "Media files found  : $($mediaFiles.Count)"
    Write-AuditProgress -Status 'scanning' -ProcessedFiles 0 -TotalFiles $mediaFiles.Count -CurrentOperation 'Enumerated media files.'

    $total = $mediaFiles.Count
    $results = Invoke-AuditFileScan -MediaFiles $mediaFiles -LibraryRoot $script:LibraryRootResolved
    Write-AuditProgress -Status 'writing-reports' -ProcessedFiles $total -TotalFiles $total -CurrentOperation 'Writing report files.'

    $reportBundle = Write-AuditReportBundle -Results @($results) -EmitText ([bool]$EmitText) -EmitJson ([bool]$EmitJson) -EmitCsv ([bool]$EmitCsv)
    $bucketCounts = $reportBundle.BucketCounts

    Write-AuditLog "Probe cache stats  : hits $($script:ProbeCacheHitCount) | misses $($script:ProbeCacheMissCount) | writes $($script:ProbeCacheWriteCount)"

    Write-AuditProgress `
        -Status 'completed' `
        -ProcessedFiles $total `
        -TotalFiles $total `
        -CurrentOperation 'Audit complete.' `
        -Completed $true `
        -LatestCsvPath $reportBundle.CsvPath `
        -LatestPriorityCsvPath $reportBundle.PriorityCsvPath `
        -LatestJsonPath $reportBundle.JsonPath `
        -LatestTextPath $reportBundle.TextPath
    Write-AuditLog ("Scan complete: OK={0}, REVIEW={1}, RERUN_PIPELINE={2}, REDOWNLOAD_CANDIDATE={3}" -f $bucketCounts.OK, $bucketCounts.REVIEW, $bucketCounts.RERUN_PIPELINE, $bucketCounts.REDOWNLOAD_CANDIDATE)
    Write-AuditLog "===== LIBRARY AUDIT END ====="
} catch {
    Complete-AuditConsoleProgress
    Write-AuditProgress -Status 'failed' -ProcessedFiles $script:AuditProgressProcessed -TotalFiles $script:AuditProgressTotal -CurrentOperation $_.Exception.Message -Completed $true -Failed $true
    Write-AuditLog $_.Exception.Message 'ERROR'
    exit 1
}
