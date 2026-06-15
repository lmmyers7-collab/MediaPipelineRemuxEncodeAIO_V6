[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Sidecar write safety checks require PowerShell 7. Install pwsh or use the bundled runtime."
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
$sidecarModule = Join-Path $repoRoot 'ops\pipeline\engine\publish\sidecar.ps1'
$publishPartialModule = Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_partial.ps1'
$publishSidecarsModule = Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_sidecars.ps1'
$mediaConstantsModule = Join-Path $repoRoot 'ops\pipeline\engine\shared\media_constants.ps1'
$srtModule = Join-Path $repoRoot 'ops\pipeline\engine\subtitles\srt.ps1'
$tx3gModule = Join-Path $repoRoot 'ops\pipeline\engine\subtitles\tx3g.ps1'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = 'INFO'
    )
}

. $sidecarModule
. $publishPartialModule
. $publishSidecarsModule
. $mediaConstantsModule
. $srtModule
. $tx3gModule

$sidecarText = Get-Content -LiteralPath $sidecarModule -Raw
Assert-True ($sidecarText -match 'function Move-SidecarTempIntoPlace') 'Sidecar overwrite fallback helper is missing.'
Assert-True ($sidecarText -match '\[System\.IO\.File\]::Move\(\$TempPath,\s*\$DestinationPath,\s*\$true\)') 'Sidecar fallback must use overwrite move.'
Assert-True ($sidecarText -notmatch 'Remove-Item\s+-LiteralPath\s+\$sidecar\s+-Force') 'Sidecar fallback must not explicitly delete the existing sidecar before replacement.'
Assert-True ($sidecarText -notmatch 'delete\+rename') 'Sidecar fallback should not describe or depend on delete+rename.'

$publishPartialText = Get-Content -LiteralPath $publishPartialModule -Raw
Assert-True ($publishPartialText -match 'function Move-PublishSidecarBackupIntoPlace') 'Publish sidecar restore overwrite fallback helper is missing.'
Assert-True ($publishPartialText -match '\[System\.IO\.File\]::Move\(\$BackupPath,\s*\$SidecarPath,\s*\$true\)') 'Publish sidecar restore fallback must use overwrite move.'

$publishSidecarsText = Get-Content -LiteralPath $publishSidecarsModule -Raw
Assert-True ($publishSidecarsText -match 'function Undo-PublishedSidecarFiles') 'Immediate publish sidecar rollback helper is missing.'
Assert-True ($publishSidecarsText -match 'Published\s*=\s*@\(\$published\)') 'Immediate TX3G sidecar publish result must carry rollback metadata.'

$srtText = Get-Content -LiteralPath $srtModule -Raw
Assert-True ($srtText -match 'function Move-SrtTempIntoPlace') 'SRT overwrite fallback helper is missing.'
Assert-True ($srtText -match '\[System\.IO\.File\]::Move\(\$TempPath,\s*\$DestinationPath,\s*\$true\)') 'SRT fallback must use overwrite move.'

$assEntry = @{
    Stream = [pscustomobject]@{ index = 10 }
    Lang = 'eng'
    Title = 'English ASS'
    RawTitle = 'English ASS'
    Codec = 'ass'
    SourceKind = 'embedded'
}
$assTrack = @{
    StreamInfo = $assEntry
    ConversionKind = 'ass_to_srt'
    SourceSubtitleKind = 'ass'
    SourceSubtitleCodec = 'ass'
    SourceKind = 'embedded'
}
$assRecord = New-Tx3gSrtRecord -Entry $assEntry -Track $assTrack -Path 'movie.eng.ass.srt' -Status 'pending' -CueCount 2
Assert-Equal $assRecord.conversion_kind 'ass_to_srt' 'TX3G sidecar record should preserve the actual conversion kind for non-TX3G SRT sidecars.'
Assert-Equal $assRecord.source_subtitle_kind 'ass' 'TX3G sidecar record should preserve the source subtitle kind for non-TX3G SRT sidecars.'
Assert-Equal $assRecord.source_subtitle_codec 'ass' 'TX3G sidecar record should preserve the source subtitle codec for non-TX3G SRT sidecars.'
Assert-Equal $assRecord.source_kind 'embedded' 'TX3G sidecar record should preserve embedded-vs-sidecar provenance.'
$legacyTx3gEntry = @{
    Stream = [pscustomobject]@{ index = 11 }
    Lang = 'eng'
    Title = 'English TX3G'
    RawTitle = 'English TX3G'
    Codec = 'mov_text'
}
$legacyTx3gRecord = New-Tx3gSrtRecord -Entry $legacyTx3gEntry -Path 'movie.eng.tx3g.srt' -Status 'pending' -CueCount 1
Assert-Equal $legacyTx3gRecord.source_subtitle_kind 'tx3g' 'Legacy TX3G sidecar records should keep tx3g source metadata without an explicit track wrapper.'
Assert-Equal $legacyTx3gRecord.conversion_kind 'tx3g_to_srt' 'Legacy TX3G sidecar records should keep tx3g conversion metadata without an explicit track wrapper.'

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-sidecar-write-{0}" -f ([Guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $root -Force | Out-Null
try {
    $destination = Join-Path $root 'movie.pipeline.json'
    $tmp = Join-Path $root '.movie.pipeline.json.tmp'
    [System.IO.File]::WriteAllText($destination, 'old-sidecar', [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($tmp, 'new-sidecar', [System.Text.UTF8Encoding]::new($false))

    Move-SidecarTempIntoPlace -TempPath $tmp -DestinationPath $destination

    Assert-True (-not (Test-Path -LiteralPath $tmp -PathType Leaf)) 'Sidecar overwrite fallback left the temp file behind.'
    Assert-Equal ([System.IO.File]::ReadAllText($destination)) 'new-sidecar' 'Sidecar overwrite fallback did not replace the existing file.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-publish-sidecar-restore-{0}" -f ([Guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $root -Force | Out-Null
try {
    $destination = Join-Path $root 'movie.pipeline.json'
    $backup = Join-Path $root '.movie.pipeline.json.backup'
    [System.IO.File]::WriteAllText($destination, 'new-sidecar', [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($backup, 'old-sidecar', [System.Text.UTF8Encoding]::new($false))

    Move-PublishSidecarBackupIntoPlace -BackupPath $backup -SidecarPath $destination -Context 'test: '

    Assert-Equal ([System.IO.File]::ReadAllText($destination)) 'old-sidecar' 'Publish sidecar restore did not replace the current sidecar.'
    Assert-True (-not (Test-Path -LiteralPath $backup -PathType Leaf)) 'Publish sidecar restore left the backup file behind.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

function New-Tx3gFailureRecord {
    param(
        [hashtable]$Entry,
        [string]$Reason,
        [string]$ErrorCode = 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED'
    )
    return [pscustomobject]@{ StreamIndex = if ($Entry.Stream) { [int]$Entry.Stream.index } else { -1 }; Reason = $Reason; ErrorCode = $ErrorCode }
}

function Copy-SrtAtomic {
    param(
        [Parameter(Mandatory)] [string]$SourcePath,
        [Parameter(Mandatory)] [string]$DestinationPath
    )
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
    return [pscustomobject]@{ Ok = $true; CueCount = 1; Reason = 'ok'; ErrorCode = 'OK' }
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-tx3g-sidecar-rollback-{0}" -f ([Guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $root -Force | Out-Null
try {
    $sourceSrt = Join-Path $root 'source.srt'
    $destinationSrt = Join-Path $root 'movie.eng.tx3g.srt'
    [System.IO.File]::WriteAllText($sourceSrt, 'new srt', [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($destinationSrt, 'old srt', [System.Text.UTF8Encoding]::new($false))
    $record = [pscustomobject]@{ stream_index = 2; language = 'eng'; title = 'English'; status = 'pending' }
    $plan = [pscustomobject]@{
        Failures = @()
        Tracks = @()
        SidecarFiles = @([pscustomobject]@{ LocalPath = $sourceSrt; DestinationPath = $destinationSrt; Record = $record })
    }

    $result = Publish-Tx3gSrtSidecarsFromPlan -Plan $plan -Context 'test: '

    Assert-Equal (@($result.Published).Count) 1 'TX3G sidecar publish did not record rollback metadata.'
    Assert-Equal ([System.IO.File]::ReadAllText($destinationSrt)) 'new srt' 'TX3G sidecar publish did not write the replacement SRT.'
    Undo-PublishedSidecarFiles -PublishedSidecars @($result.Published) -Context 'test: '
    Assert-Equal ([System.IO.File]::ReadAllText($destinationSrt)) 'old srt' 'TX3G sidecar rollback did not restore the previous SRT.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-srt-write-{0}" -f ([Guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $root -Force | Out-Null
try {
    $destination = Join-Path $root 'subtitle.srt'
    $tmp = Join-Path $root '.subtitle.tmp.srt'
    [System.IO.File]::WriteAllText($destination, 'old-srt', [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($tmp, 'new-srt', [System.Text.UTF8Encoding]::new($false))

    Move-SrtTempIntoPlace -TempPath $tmp -DestinationPath $destination

    Assert-True (-not (Test-Path -LiteralPath $tmp -PathType Leaf)) 'SRT overwrite fallback left the temp file behind.'
    Assert-Equal ([System.IO.File]::ReadAllText($destination)) 'new-srt' 'SRT overwrite fallback did not replace the existing file.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Sidecar write safety checks passed.'
