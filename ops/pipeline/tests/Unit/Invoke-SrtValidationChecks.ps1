[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "SRT validation checks require PowerShell 7. Install pwsh or use the bundled runtime."
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

# Exercise the real Test-SrtFileUsable, not a stub.
. (Join-Path $repoRoot 'ops\pipeline\engine\subtitles\srt.ps1')

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("srtcheck_" + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $tempDir -Force)

function New-TempSrt {
    param([string] $Body)
    $path = Join-Path $tempDir ((([guid]::NewGuid().ToString('N'))) + '.srt')
    [System.IO.File]::WriteAllText($path, $Body, [System.Text.UTF8Encoding]::new($false))
    return $path
}

try {
    # 1. Fully valid SRT.
    $valid = New-TempSrt @"
1
00:00:01,000 --> 00:00:04,000
Hello there

2
00:00:05,000 --> 00:00:08,000
Second cue
"@
    $r1 = Test-SrtFileUsable -Path $valid
    Assert-True ([bool]$r1.Ok) "Valid SRT should be usable: $($r1.Reason)"
    Assert-Equal $r1.CueCount 2 'Valid SRT should report two cues.'

    # 2. Regression: one empty-text cue among valid cues must stay usable.
    #    (PgsToSrt routinely emits empty cues for blank/sign frames.)
    $withEmpty = New-TempSrt @"
1
00:00:01,000 --> 00:00:04,000
Real text

2
00:00:05,000 --> 00:00:08,000

3
00:00:09,000 --> 00:00:12,000
More real text
"@
    $r2 = Test-SrtFileUsable -Path $withEmpty
    Assert-True ([bool]$r2.Ok) "SRT with a single empty cue among valid cues must remain usable: $($r2.Reason)"
    Assert-Equal $r2.CueCount 3 'Empty cue should still be counted structurally.'
    Assert-Equal $r2.TextLineCount 2 'Only non-empty cue lines should count toward text.'

    # 2b. Regression: a cue whose OCR text contains an embedded blank line
    #     (PgsToSrt emits one between separate on-screen text regions) must
    #     stay usable; the blank must not orphan the text after it.
    $embeddedBlank = New-TempSrt @"
1
00:00:01,000 --> 00:00:04,000
First region line one
First region line two

2
00:05:59,826 --> 00:06:01,870
-- became an evil spirit and decided to
use my powers for myself this time.
--Early yesterday, Mogami Keiji-san,

the famous psychic, was discovered dead.

3
00:06:02,120 --> 00:06:05,415
According to the MPD,
the cause of death was suicide.
"@
    $r2b = Test-SrtFileUsable -Path $embeddedBlank
    Assert-True ([bool]$r2b.Ok) "SRT with a blank line embedded in cue text must remain usable: $($r2b.Reason)"
    Assert-Equal $r2b.CueCount 3 'Embedded blank line must not split a cue into extra cues.'
    Assert-Equal $r2b.TextLineCount 8 'All non-blank text lines should count, including text after an embedded blank.'

    # 3. An SRT whose cues are ALL empty is still rejected.
    $allEmpty = New-TempSrt @"
1
00:00:01,000 --> 00:00:04,000

2
00:00:05,000 --> 00:00:08,000

"@
    $r3 = Test-SrtFileUsable -Path $allEmpty
    Assert-True (-not [bool]$r3.Ok) 'SRT with no cue text anywhere must be rejected.'

    # 4. Structural validations remain intact: invalid timing is rejected.
    $badTiming = New-TempSrt @"
1
00:00:08,000 --> 00:00:04,000
End before start
"@
    $r4 = Test-SrtFileUsable -Path $badTiming
    Assert-True (-not [bool]$r4.Ok) 'SRT with end <= start timing must be rejected.'
    Assert-Equal $r4.Reason 'SRT cue timing is invalid' 'Invalid timing should report the timing reason.'

    Write-Host 'SRT validation checks passed.'
} finally {
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
