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
$repoRoot = Split-Path -Parent $pipelineRoot

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
    }
    if ([string]::IsNullOrWhiteSpace($folder) -or [string]::IsNullOrWhiteSpace($file)) {
        return [pscustomobject]@{ ExitCode = 2; Output = ''; Error = 'missing output args'; ReproPath = '' }
    }
    $target = Join-Path $folder $file
    [System.IO.File]::WriteAllText($target, "1`r`n00:00:00,000 --> 00:00:01,000`r`nHello VobSub`r`n", [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{ ExitCode = 0; Output = '{"ok":true}'; Error = ''; ReproPath = '' }
}

. (Join-Path $repoRoot 'engine\shared\media_constants.ps1')
. (Join-Path $repoRoot 'engine\subtitles\vobsub.ps1')

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-vobsub-tests-' + [guid]::NewGuid().ToString('N'))
$oldPath = $env:PATH
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $script:processingDir = $root
    $script:VobSubOcrToolPath = Join-Path $root 'seconv.exe'
    $script:AllowSystemTools = $false
    Set-Content -LiteralPath $script:VobSubOcrToolPath -Value 'fake seconv' -Encoding ASCII
    $fakeTesseractDir = Join-Path $root 'Tesseract550'
    New-Item -ItemType Directory -Path $fakeTesseractDir -Force | Out-Null
    $fakeTesseract = Join-Path $fakeTesseractDir 'tesseract.exe'
    Set-Content -LiteralPath $fakeTesseract -Value 'fake tesseract' -Encoding ASCII

    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'dvd_subtitle' })) 'dvd_subtitle should be detected as VobSub.'
    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'dvdsub' })) 'dvdsub should be detected as VobSub.'
    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'vobsub' })) 'vobsub should be detected as VobSub.'
    Assert-True (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'unknown'; codec_tag_string = 'S_VOBSUB' })) 'S_VOBSUB tag should be detected as VobSub.'
    Assert-True (-not (Test-IsVobSubSubtitleStream ([pscustomobject]@{ codec_name = 'hdmv_pgs_subtitle' }))) 'BDPGS should not be detected as VobSub.'
    Assert-Equal (Resolve-VobSubOcrLanguage 'en') 'eng' 'VobSub OCR language mapping for en failed.'

    $media = Join-Path $root 'Movie.mkv'
    Set-Content -LiteralPath $media -Value 'fake media' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.idx') -Value 'id: en, index: 0' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.sub') -Value 'bitmap' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.eng.idx') -Value 'id: en, index: 0' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.eng.sub') -Value 'bitmap' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.missing.idx') -Value 'id: en, index: 0' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $root 'Movie.orphan.sub') -Value 'not a vobsub pair' -Encoding ASCII

    $pairs = @(Find-VobSubSidecarPairs -MediaPath $media)
    Assert-Equal @($pairs | Where-Object { $_.Ok }).Count 2 'VobSub sidecar pairing should accept only complete IDX/SUB pairs.'
    Assert-Equal @($pairs | Where-Object { -not $_.Ok }).Count 1 'VobSub sidecar pairing should retain missing-SUB evidence for review.'

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
    Assert-True ([bool]$converted.Ok) "Fake seconv VobSub conversion failed: $($converted.Reason)"
    Assert-Equal $converted.CueCount 1 'Fake seconv VobSub conversion should report one cue.'
    Assert-True ((Test-Path -LiteralPath $out -PathType Leaf) -and ((Get-Content -LiteralPath $out -Raw) -match 'Hello VobSub')) 'Fake seconv VobSub conversion did not write expected SRT.'

    $missingEntry = $entry.Clone()
    $missingEntry.SubPath = Join-Path $root 'Movie.absent.sub'
    $missing = Extract-VobSubToIdxSub -SourceFile $media -StreamInfo $missingEntry
    Assert-True (-not [bool]$missing.Ok) 'Missing VobSub .sub sidecar should not extract successfully.'
    Assert-Equal $missing.Failure.ErrorCode 'SUBTITLE_VOBSUB_PAIR_MISSING' 'Missing VobSub sidecar pair should use the pair-missing failure code.'
} finally {
    $env:PATH = $oldPath
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'VobSub subtitle checks passed.'
