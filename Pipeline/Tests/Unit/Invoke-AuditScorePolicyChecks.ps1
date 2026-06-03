[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Audit score policy checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot

. (Join-Path $repoRoot 'engine\audit\policy.ps1')
. (Join-Path $repoRoot 'engine\audit\reports.ps1')

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

function Assert-SequenceEqual {
    param(
        [array] $Actual,
        [array] $Expected,
        [string] $Message
    )

    if ($Actual.Count -ne $Expected.Count) {
        throw "$Message Expected $($Expected.Count) items but got $($Actual.Count). Actual: $($Actual -join '|')"
    }
    for ($i = 0; $i -lt $Expected.Count; $i++) {
        if ([string]$Actual[$i] -ne [string]$Expected[$i]) {
            throw "$Message Difference at index $i. Expected '$($Expected[$i])' but got '$($Actual[$i])'. Actual: $($Actual -join '|')"
        }
    }
}

function New-AuditIssue {
    param(
        [string] $Bucket,
        [string] $Code
    )

    return [pscustomobject]@{
        Bucket          = $Bucket
        Code            = $Code
        Message         = "Issue $Code"
        SuggestedAction = "Review $Code"
    }
}

function New-AuditResult {
    param(
        [string] $Path,
        [string] $Title,
        [string] $Bucket,
        [array] $Issues
    )

    return [pscustomobject]@{
        Path                    = $Path
        RelativePath            = Split-Path -Leaf $Path
        FileName                = Split-Path -Leaf $Path
        MediaType               = 'Movie'
        LookupTitle             = $Title
        SizeBytes               = 0
        SizeGB                  = 0
        Extension               = '.mkv'
        Bucket                  = $Bucket
        DurationSeconds         = 0
        Container               = 'matroska'
        VideoCodecs             = @('h264')
        AudioCodecs             = @('aac')
        SubtitleCodecs          = @()
        AudioCount              = 1
        SubtitleCount           = 0
        Tx3gSubtitleCount       = 0
        Tx3gEmbeddedSrtCount    = 0
        Tx3gExternalSrtCount    = 0
        Tx3gExternalSrtFiles    = @()
        Tx3gSidecarSrtInvalidCount = 0
        Tx3gSidecarFailureCount = 0
        BdpgsSubtitleCount      = 0
        BdpgsEmbeddedSrtCount   = 0
        BdpgsEmbeddedSrtInvalidCount = 0
        BdpgsSidecarFailureCount = 0
        VobSubSubtitleCount     = 0
        VobSubEmbeddedSrtCount  = 0
        VobSubEmbeddedSrtInvalidCount = 0
        VobSubSidecarFailureCount = 0
        DefaultAudioCodec       = 'aac'
        DefaultAudioLanguage    = 'eng'
        DefaultAudioTitle       = ''
        DefaultSubtitleCodec    = ''
        DefaultSubtitleLanguage = ''
        DefaultSubtitleTitle    = ''
        HasEnglishAudio         = $true
        HasEnglishSubtitle      = $false
        HasTextSubtitle         = $false
        SidecarPath             = ''
        SidecarVersion          = ''
        SidecarRoute            = ''
        Issues                  = @($Issues)
    }
}

$script:HighPriorityIssueCodes = @('audio-default-policy-mismatch')
$script:MediumPriorityIssueCodes = @('audio-track-titles-missing')
$script:SidecarIssueCodes = @('sidecar-missing')
$script:AuditIgnoreEntries = @{}

$highIssue = New-AuditIssue -Bucket 'REVIEW' -Code 'audio-default-policy-mismatch'
$highRerunIssue = New-AuditIssue -Bucket 'RERUN_PIPELINE' -Code 'audio-default-policy-mismatch'
$rerunIssue = New-AuditIssue -Bucket 'RERUN_PIPELINE' -Code 'audio-language-tags-unknown'
$mediumIssue = New-AuditIssue -Bucket 'REVIEW' -Code 'audio-track-titles-missing'
$redownloadIssue = New-AuditIssue -Bucket 'REDOWNLOAD_CANDIDATE' -Code 'foreign-audio-no-text-subtitles'
$fallbackIssue = New-AuditIssue -Bucket 'UNKNOWN' -Code 'unknown-review'

$script:AuditScorePolicy = ConvertTo-AuditScorePolicy -Policy $null
Assert-Equal (Get-PriorityScore -Issues @($highRerunIssue)) 130 'Default high rerun score changed.'
Assert-Equal (Get-PriorityScore -Issues @($rerunIssue)) 100 'Default rerun bucket score changed.'
Assert-Equal (Get-PriorityScore -Issues @($mediumIssue)) 40 'Default medium issue score changed.'
Assert-Equal (Get-PriorityScore -Issues @($fallbackIssue)) 10 'Default fallback issue score changed.'
Assert-Equal (Get-PriorityScore -Issues @($redownloadIssue, $highIssue)) 290 'Default redownload-plus-high score changed.'

$script:AuditScorePolicy = ConvertTo-AuditScorePolicy -Policy @{
    redownload_bucket = 11
    high_issue        = 9
    rerun_bucket      = 7
    medium_issue      = 500
    review_bucket     = 4
    fallback_issue    = 2
    redownload_bonus  = 5
    rerun_bonus       = 3
}
Assert-Equal (Get-PriorityScore -Issues @($highRerunIssue)) 12 'Custom high rerun score was not applied.'
Assert-Equal (Get-PriorityScore -Issues @($redownloadIssue, $highIssue)) 25 'Custom redownload-plus-high score was not applied.'

$lowCustomResult = Convert-ResultForSerialization -Result (New-AuditResult -Path 'C:\Media\LowCustom.mkv' -Title 'High Rerun' -Bucket 'RERUN_PIPELINE' -Issues @($highRerunIssue))
$highCustomResult = Convert-ResultForSerialization -Result (New-AuditResult -Path 'C:\Media\HighCustom.mkv' -Title 'Medium Review' -Bucket 'REVIEW' -Issues @($mediumIssue))
$orderedRows = @(New-AuditCsvRows -Entries @($lowCustomResult, $highCustomResult))
Assert-SequenceEqual @($orderedRows | ForEach-Object { $_.LookupTitle }) @('Medium Review', 'High Rerun') 'Custom score weights did not control priority CSV ordering.'

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-audit-score-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
try {
    $policyPath = Join-Path $tempRoot 'audit_score_policy.json'
    @{
        version = 1
        policy = @{
            high_issue       = 17
            fallback_issue   = -20
            redownload_bonus = 5000
        }
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $policyPath -Encoding UTF8

    $importedPolicy = Import-AuditScorePolicy -Path $policyPath
    Assert-Equal $importedPolicy['high_issue'] 17 'Imported policy did not use saved score weight.'
    Assert-Equal $importedPolicy['fallback_issue'] 0 'Imported policy did not clamp low score weight.'
    Assert-Equal $importedPolicy['redownload_bonus'] 1000 'Imported policy did not clamp high score weight.'
    Assert-Equal $importedPolicy['rerun_bonus'] 40 'Imported policy did not preserve missing default score weight.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$script:AuditScorePolicy = ConvertTo-AuditScorePolicy -Policy $null
$ignoredPath = 'C:\Media\Ignored.mkv'
$script:AuditIgnoreEntries = @{
    (ConvertTo-AuditIgnoreKey -Path $ignoredPath) = [pscustomobject]@{
        reason = 'operator audit-only ignore'
        set_at = '2026-06-03T00:00:00Z'
    }
}
$ignoredResult = Convert-ResultForSerialization -Result (New-AuditResult -Path $ignoredPath -Title 'Ignored' -Bucket 'RERUN_PIPELINE' -Issues @($highRerunIssue))
Assert-True $ignoredResult.AuditIgnored 'Ignored audit row was not marked ignored.'
Assert-Equal $ignoredResult.PriorityFixLevel 'NONE' 'Ignored audit row should not remain priority actionable.'
Assert-Equal $ignoredResult.PriorityScore 0 'Ignored audit row should have zero priority score.'
Assert-Equal $ignoredResult.EffectiveBucket 'IGNORED' 'Ignored audit row should publish ignored effective bucket.'
Assert-Equal $ignoredResult.AuditIgnoreReason 'operator audit-only ignore' 'Ignored audit row did not carry ignore reason.'

$activeResult = Convert-ResultForSerialization -Result (New-AuditResult -Path 'C:\Media\Active.mkv' -Title 'Active' -Bucket 'RERUN_PIPELINE' -Issues @($highRerunIssue))
$priorityRows = @(New-AuditCsvRows -Entries @($ignoredResult, $activeResult) | Where-Object { $_.PriorityFixLevel -in @('HIGH', 'MEDIUM') })
Assert-SequenceEqual @($priorityRows | ForEach-Object { $_.LookupTitle }) @('Active') 'Ignored audit row was not suppressed from priority rows.'

Write-Host 'Audit score policy checks passed.'
