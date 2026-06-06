[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "VobSub subtitle checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function Get-NormalizedSubtitleLanguage {
    param([string] $Language)
    $text = if ($Language) { ([string]$Language).Trim().ToLowerInvariant() } else { '' }
    switch ($text) {
        'english' { return 'eng' }
        'en' { return 'eng' }
        'japanese' { return 'jpn' }
        'ja' { return 'jpn' }
        default { if ($text) { return $text }; return 'und' }
    }
}

function Resolve-SubtitleConfiguredPath {
    param(
        [string] $PathValue,
        [switch] $AllowCommandLookup
    )
    return [string]$PathValue
}

function Get-SubtitleConfiguredPathBaseDirectories {
    return @()
}

function New-StandardFailureRecord {
    param(
        [string] $Stage,
        [string] $Operation,
        [string] $Category,
        [string] $Reason,
        [string] $ErrorCode,
        [string] $Tool,
        [string] $ReproPath,
        [bool] $Retryable,
        [hashtable] $AdditionalProperties = @{}
    )
    $record = [ordered]@{
        Stage = $Stage
        Operation = $Operation
        Category = $Category
        Reason = $Reason
        ErrorCode = $ErrorCode
        error_code = $ErrorCode
        Tool = $Tool
        ReproPath = $ReproPath
        Retryable = $Retryable
    }
    foreach ($key in $AdditionalProperties.Keys) { $record[$key] = $AdditionalProperties[$key] }
    [pscustomobject]$record
}

function Get-SubtitleOperationTimeoutSeconds {
    param([string] $ScriptVariableName, [int] $DefaultSeconds)
    return $DefaultSeconds
}

function New-SrtAtomicTempPath {
    param([string] $DestinationPath)
    return "$DestinationPath.tmp"
}

function Test-SrtFileUsable {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Ok = $false; CueCount = 0; Reason = 'missing' }
    }
    $text = Get-Content -LiteralPath $Path -Raw
    if ($text -notmatch '-->') {
        return [pscustomobject]@{ Ok = $false; CueCount = 0; Reason = 'no cues' }
    }
    return [pscustomobject]@{ Ok = $true; CueCount = 1; Reason = 'ok' }
}

function Complete-AtomicSrtWrite {
    param([string] $TempPath, [string] $DestinationPath)
    Move-Item -LiteralPath $TempPath -Destination $DestinationPath -Force
    return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; CueCount = 1; Reason = 'ok' }
}

function Get-ErrorTextSummary {
    param([string] $ErrorText)
    if ([string]::IsNullOrWhiteSpace($ErrorText)) { return '' }
    return $ErrorText.Trim()
}

function Invoke-VobSubOcrCommand {
    param(
        [string] $FilePath,
        [array] $ArgumentList,
        [int] $TimeoutSeconds,
        [string] $Stage,
        [switch] $SaveReproOnFailure,
        [string] $ProcessPriority
    )
    $script:LastVobSubOcrArguments = @($ArgumentList)
    $folder = ''
    $file = ''
    foreach ($arg in @($ArgumentList)) {
        $text = [string]$arg
        if ($text.StartsWith('--output-folder:', [System.StringComparison]::OrdinalIgnoreCase)) {
            $folder = $text.Substring('--output-folder:'.Length)
        }
        if ($text.StartsWith('--output-filename:', [System.StringComparison]::OrdinalIgnoreCase)) {
            $file = $text.Substring('--output-filename:'.Length)
        }
        if ($text.StartsWith('/outputfolder:', [System.StringComparison]::OrdinalIgnoreCase)) {
            $folder = $text.Substring('/outputfolder:'.Length)
        }
        if ($text.StartsWith('/outputfilename:', [System.StringComparison]::OrdinalIgnoreCase)) {
            $file = $text.Substring('/outputfilename:'.Length)
        }
    }
    if ([string]::IsNullOrWhiteSpace($folder) -or [string]::IsNullOrWhiteSpace($file)) {
        return [pscustomobject]@{ ExitCode = 2; Output = ''; Error = 'missing output args'; ReproPath = '' }
    }
    $target = Join-Path $folder $file
    [System.IO.File]::WriteAllText($target, "1`r`n00:00:00,000 --> 00:00:01,000`r`nHello VobSub`r`n", [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{ ExitCode = 0; Output = '{"ok":true}'; Error = ''; ReproPath = '' }
}

function Invoke-MkvmergeCommand {
    param(
        [array] $ArgumentList,
        [int] $TimeoutSeconds,
        [string] $Stage,
        [switch] $SaveReproOnFailure
    )
    return [pscustomobject]@{ ExitCode = 0; Output = $script:MkvmergeJson; Error = ''; ReproPath = '' }
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\vobsub.ps1')

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-vobsub-tests-' + [guid]::NewGuid().ToString('N'))
$oldPath = $env:PATH
$oldTessdataPrefix = $env:TESSDATA_PREFIX
try {
    Remove-Item Env:\TESSDATA_PREFIX -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $script:processingDir = $root
    $script:VobSubOcrToolPath = Join-Path $root 'SubtitleEdit.exe'
    $script:AllowSystemTools = $false
    Set-Content -LiteralPath $script:VobSubOcrToolPath -Value 'fake Subtitle Edit' -Encoding ASCII
    $fakeTesseractDir = Join-Path $root 'Tesseract550'
    New-Item -ItemType Directory -Path $fakeTesseractDir -Force | Out-Null
    $fakeTesseract = Join-Path $fakeTesseractDir 'tesseract.exe'
    Set-Content -LiteralPath $fakeTesseract -Value 'fake tesseract' -Encoding ASCII
    $fakeTessdataDir = Join-Path $fakeTesseractDir 'tessdata'
    New-Item -ItemType Directory -Path $fakeTessdataDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $fakeTessdataDir 'eng.traineddata') -Value 'fake eng data' -Encoding ASCII

    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'dvd_subtitle' })) 'dvd_subtitle should be detected as VobSub.'
    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'dvdsub' })) 'dvdsub should be detected as VobSub.'
    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'vobsub' })) 'vobsub should be detected as VobSub.'
    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'unknown'; codec_tag_string = 'S_VOBSUB' })) 'S_VOBSUB tag should be detected as VobSub.'
    Assert-True (-not (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'hdmv_pgs_subtitle' }))) 'BDPGS should not be detected as VobSub.'
    Assert-Equal (Resolve-VobSubOcrLanguage 'en') 'eng' 'VobSub OCR language mapping for en failed.'

    $multiLanguageIdx = Join-Path $root 'LangOnly.idx'
    Set-Content -LiteralPath $multiLanguageIdx -Value @('langidx: 1', 'id: en, index: 0', 'id: ja, index: 1') -Encoding ASCII
    Assert-Equal (Get-VobSubIdxLanguage $multiLanguageIdx) 'jpn' 'VobSub IDX langidx should select the matching indexed language.'

    $media = Join-Path $root 'Movie.mkv'
    Set-Content -LiteralPath $media -Value 'fake media' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.idx') -Value 'id: en, index: 0' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.sub') -Value 'bitmap' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.eng.idx') -Value 'id: en, index: 0' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.eng.sub') -Value 'bitmap' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.missing.idx') -Value 'id: en, index: 0' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.empty.idx') -Value 'id: en, index: 0' -Encoding ASCII
    [System.IO.File]::WriteAllBytes((Join-Path $root 'Movie.empty.sub'), [byte[]]::new(0))
    Set-Content -LiteralPath (Join-Path $root 'Movie.orphan.sub') -Value 'not a vobsub pair' -Encoding ASCII

    $pairs = @(Find-VobSubSidecarPairs -MediaPath $media)
    Assert-Equal @($pairs | Where-Object { $_.Ok }).Count 2 'VobSub sidecar pairing should accept only complete IDX/SUB pairs.'
    Assert-Equal @($pairs | Where-Object { -not $_.Ok }).Count 2 'VobSub sidecar pairing should retain missing or empty SUB evidence for review.'
    Assert-True (@($pairs | Where-Object { -not $_.Ok -and $_.Reason -like '*empty*' }).Count -eq 1) 'VobSub sidecar pairing should flag empty SUB files distinctly.'

    $script:MkvmergeJson = '{"tracks":[{"id":7,"type":"subtitles","codec":"VobSub subtitles","properties":{"number":99,"language":"eng","track_name":"Movie VobSub","codec_id":"S_VOBSUB"}}]}'
    $mappedTrack = Resolve-VobSubMkvTrackId -SourceFile $media -StreamInfo @{ Stream = [pscustomobject]@{ index = 5 }; Lang = 'eng'; Title = 'Movie VobSub'; RawTitle = 'Movie VobSub' }
    Assert-True ([bool]$mappedTrack.Ok) "VobSub track id mapping should fall back to exact metadata when mkvmerge track number does not match ffprobe stream index: $($mappedTrack.Reason)"
    Assert-Equal $mappedTrack.TrackId 7 'VobSub track id mapping should return the mkvmerge track id, not the track number.'

    $script:MkvmergeJson = '{"tracks":[{"id":7,"type":"subtitles","codec":"VobSub subtitles","properties":{"language":"eng","codec_id":"S_VOBSUB"}},{"id":8,"type":"subtitles","codec":"VobSub subtitles","properties":{"language":"eng","codec_id":"S_VOBSUB"}}]}'
    $ambiguousTrack = Resolve-VobSubMkvTrackId -SourceFile $media -StreamInfo @{ Stream = [pscustomobject]@{ index = 5 }; Lang = 'eng'; Title = ''; RawTitle = '' }
    Assert-True (-not [bool]$ambiguousTrack.Ok) 'VobSub track id mapping should fail closed when multiple same-language VobSub tracks cannot be distinguished.'

    $entry = @{
        SourceKind = 'sidecar'
        IdxPath = Join-Path $root 'Movie.idx'
        SubPath = Join-Path $root 'Movie.sub'
        Stream = [pscustomobject]@{ index = -1 }
        Lang = 'eng'
        Title = 'Movie VobSub'
        IsForced = $false
        IsSupplemental = $false
    }
    $out = Join-Path $root 'Movie.vobsub.srt'
    $converted = Convert-VobSubToSrt -SourceFile $media -StreamIndex -1 -StreamInfo $entry -DestinationPath $out
    Assert-True ([bool]$converted.Ok) "Fake Subtitle Edit VobSub conversion failed: $($converted.Reason)"
    Assert-Equal $converted.CueCount 1 'Fake Subtitle Edit VobSub conversion should report one cue.'
    Assert-True ((Test-Path -LiteralPath $out -PathType Leaf) -and ((Get-Content -LiteralPath $out -Raw) -match 'Hello VobSub')) 'Fake Subtitle Edit VobSub conversion did not write expected SRT.'
    Assert-True (@($script:LastVobSubOcrArguments) -contains '/ocrdb:eng') 'Subtitle Edit VobSub OCR should pass the resolved Tesseract language via /ocrdb.'

    $missingLanguageEntry = $entry.Clone()
    $missingLanguageEntry.Lang = 'jpn'
    $missingLanguage = Convert-VobSubToSrt -SourceFile $media -StreamIndex -1 -StreamInfo $missingLanguageEntry -DestinationPath (Join-Path $root 'Movie.jpn.vobsub.srt')
    Assert-True (-not [bool]$missingLanguage.Ok) 'VobSub conversion should fail before OCR when requested Tesseract language data is missing.'
    Assert-Equal $missingLanguage.Failure.ErrorCode 'SUBTITLE_VOBSUB_TESSDATA_MISSING' 'Missing VobSub Tesseract language data should use a distinct failure code.'

    $unknownTool = Join-Path $root 'CustomOcr.exe'
    Set-Content -LiteralPath $unknownTool -Value 'fake custom ocr' -Encoding ASCII
    $script:VobSubOcrToolPath = $unknownTool
    $unsupportedTool = Convert-VobSubToSrt -SourceFile $media -StreamIndex -1 -StreamInfo $entry -DestinationPath (Join-Path $root 'Movie.unsupported-tool.srt')
    Assert-True (-not [bool]$unsupportedTool.Ok) 'VobSub conversion should reject unknown OCR tool shapes before attempting OCR.'
    Assert-Equal $unsupportedTool.Failure.ErrorCode 'SUBTITLE_VOBSUB_OCR_TOOL_UNSUPPORTED' 'Unsupported VobSub OCR tools should use a distinct failure code.'
    $script:VobSubOcrToolPath = Join-Path $root 'SubtitleEdit.exe'

    $missingEntry = $entry.Clone()
    $missingEntry.SubPath = Join-Path $root 'Movie.absent.sub'
    $missing = Extract-VobSubToIdxSub -SourceFile $media -StreamInfo $missingEntry
    Assert-True (-not [bool]$missing.Ok) 'Missing VobSub .sub sidecar should not extract successfully.'
    Assert-Equal $missing.Failure.ErrorCode 'SUBTITLE_VOBSUB_PAIR_MISSING' 'Missing VobSub sidecar pair should use the pair-missing failure code.'
} finally {
    $env:PATH = $oldPath
    if ($null -eq $oldTessdataPrefix) {
        Remove-Item Env:\TESSDATA_PREFIX -ErrorAction SilentlyContinue
    } else {
        $env:TESSDATA_PREFIX = $oldTessdataPrefix
    }
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'VobSub subtitle checks passed.'
