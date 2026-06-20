param()

$ErrorActionPreference = 'Stop'
$scriptPath = if ($PSCommandPath) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
$pipelineRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptPath))
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $scriptPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}
$failureCodesModule = Join-Path $repoRoot 'ops\pipeline\engine\shared\failure_codes.ps1'

. $failureCodesModule

$moduleText = Get-Content -LiteralPath $failureCodesModule -Raw
$returnCodes = @(
    [regex]::Matches($moduleText, "return '([A-Z0-9_]{4,})'") |
        ForEach-Object { $_.Groups[1].Value } |
        Sort-Object -Unique
)
$knownCodes = @(Get-MediaPipelineKnownFailureCodes | Sort-Object -Unique)
$registry = @(Get-MediaPipelineFailureCodeRegistry)
$outcomeCodes = @(Get-MediaPipelineKnownOutcomeCodes | Sort-Object -Unique)
$outcomeRegistry = @(Get-MediaPipelineOutcomeCodeRegistry)

$missingFromRegistry = @($returnCodes | Where-Object { $_ -notin $knownCodes })
if ($missingFromRegistry.Count -gt 0) {
    throw "Failure classifier returns codes missing from registry: $($missingFromRegistry -join ', ')"
}

$extraRegistryCodes = @($knownCodes | Where-Object { $_ -notin $returnCodes })
if ($extraRegistryCodes.Count -gt 0) {
    throw "Failure registry has codes not returned by classifiers: $($extraRegistryCodes -join ', ')"
}

$registryCodes = @($registry | ForEach-Object { [string]$_.Code } | Sort-Object -Unique)
if (@($registryCodes).Count -ne @($knownCodes).Count) {
    throw 'Failure registry must expose one unique metadata row per known failure code.'
}

foreach ($entry in $registry) {
    if ([string]::IsNullOrWhiteSpace([string]$entry.Code)) { throw 'Failure registry entry is missing Code.' }
    if ([string]::IsNullOrWhiteSpace([string]$entry.Family)) { throw "Failure registry entry $($entry.Code) is missing Family." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.Stage)) { throw "Failure registry entry $($entry.Code) is missing Stage." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.WhenFires)) { throw "Failure registry entry $($entry.Code) is missing WhenFires." }
    if ($null -eq $entry.Retryable -or $entry.Retryable -isnot [bool]) { throw "Failure registry entry $($entry.Code) must expose boolean Retryable metadata." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.OperatorSeverity)) { throw "Failure registry entry $($entry.Code) is missing OperatorSeverity." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.HandledBy)) { throw "Failure registry entry $($entry.Code) is missing HandledBy." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.OperatorAction)) { throw "Failure registry entry $($entry.Code) is missing OperatorAction." }
}

if (-not (Test-MediaPipelineKnownFailureCode -Code 'ENCODE_CPU_TIMEOUT')) {
    throw 'Known failure code lookup rejected ENCODE_CPU_TIMEOUT.'
}
if (Test-MediaPipelineKnownFailureCode -Code 'NOT_A_REAL_FAILURE_CODE') {
    throw 'Known failure code lookup accepted an unknown failure code.'
}
$cpuTimeout = Get-MediaPipelineFailureCodeMetadata -Code 'ENCODE_CPU_TIMEOUT'
if (-not $cpuTimeout -or $cpuTimeout.Stage -ne 'encode-cpu' -or -not [bool]$cpuTimeout.Retryable -or $cpuTimeout.OperatorSeverity -ne 'warning' -or $cpuTimeout.HandledBy -notmatch 'PipelineProcessing') {
    throw 'ENCODE_CPU_TIMEOUT metadata is not operator-useful.'
}
$truncated = Get-MediaPipelineFailureCodeMetadata -Code 'SOURCE_MEDIA_TRUNCATED'
if (-not $truncated -or [bool]$truncated.Retryable -or $truncated.OperatorSeverity -ne 'error' -or $truncated.WhenFires -notmatch 'source media') {
    throw 'SOURCE_MEDIA_TRUNCATED metadata is not conservative.'
}
$videoMissing = Get-MediaPipelineFailureCodeMetadata -Code 'SOURCE_MEDIA_VIDEO_MISSING'
if (-not $videoMissing -or $videoMissing.Family -ne 'source_media' -or [bool]$videoMissing.Retryable -or $videoMissing.OperatorSeverity -ne 'error' -or $videoMissing.Stage -ne 'source-intake' -or $videoMissing.HandledBy -notmatch 'MediaProbe' -or $videoMissing.OperatorAction -notmatch 'replace the source media') {
    throw 'SOURCE_MEDIA_VIDEO_MISSING metadata should be source-media, permanent, probe-handled, and source-repair oriented.'
}
if ($null -ne (Get-MediaPipelineFailureCodeMetadata -Code 'NOT_A_REAL_FAILURE_CODE')) {
    throw 'Failure metadata lookup returned metadata for an unknown failure code.'
}

$scanFiles = @()
foreach ($scanRoot in @(
    (Join-Path $pipelineRoot 'entrypoints'),
    (Join-Path $pipelineRoot 'engine')
)) {
    if (Test-Path -LiteralPath $scanRoot -PathType Container) {
        $scanFiles += Get-ChildItem -LiteralPath $scanRoot -Filter '*.ps1' -File -Recurse
    }
}
$legacyModulesRoot = Join-Path $pipelineRoot 'Modules'
if (Test-Path -LiteralPath $legacyModulesRoot -PathType Container) {
    $scanFiles += Get-ChildItem -LiteralPath $legacyModulesRoot -Filter '*.ps1' -File -Recurse
}
$outcomeTokenPattern = '(?<![A-Z0-9_])(?<code>(?:ALREADY|AUDIO|BAD|ENCODE|ENCODER|FFMPEG|FILE|HDR|INTEGRITY|MEDIA|MKVMERGE|NATIVE|OPERATOR|OUTPUT|PENDING|PERMANENT|PROGRESS|PUBLISH|REMUX|SCRATCH|SIDECAR|SOURCE|STOP|SUBTITLE|SYSTEM|TRANSIENT|TV|UNKNOWN)[A-Z0-9]*_[A-Z0-9_]*[A-Z0-9]|OK)(?![A-Z0-9_])'
$emittedCodes = @(
    foreach ($file in $scanFiles) {
        foreach ($line in @(Get-Content -LiteralPath $file.FullName)) {
            if ($line -notmatch 'ErrorCode|errorCode|ReasonCode|Register-SourceFailure|New-MediaPipelineProcessFileResult|New-FileIntegrityResult|New-\w+FailureRecord|SOURCE_MEDIA_AUDIO_|OUTPUT_DESTINATION_') {
                continue
            }
            foreach ($match in [regex]::Matches($line, $outcomeTokenPattern)) {
                [string]$match.Groups['code'].Value
            }
        }
    }
) | Sort-Object -Unique

$unknownOutcomeCodes = @($emittedCodes | Where-Object { $_ -notin $outcomeCodes })
if ($unknownOutcomeCodes.Count -gt 0) {
    throw "Pipeline emits outcome/error codes missing from outcome registry: $($unknownOutcomeCodes -join ', ')"
}

$missingFailureCodesFromOutcomeRegistry = @($knownCodes | Where-Object { $_ -notin $outcomeCodes })
if ($missingFailureCodesFromOutcomeRegistry.Count -gt 0) {
    throw "Outcome registry is missing classifier failure codes: $($missingFailureCodesFromOutcomeRegistry -join ', ')"
}

$outcomeRegistryCodes = @($outcomeRegistry | ForEach-Object { [string]$_.Code } | Sort-Object -Unique)
if (@($outcomeRegistryCodes).Count -ne @($outcomeCodes).Count) {
    throw 'Outcome registry must expose one unique metadata row per known outcome code.'
}

foreach ($entry in $outcomeRegistry) {
    if ([string]::IsNullOrWhiteSpace([string]$entry.Code)) { throw 'Outcome registry entry is missing Code.' }
    if ([string]::IsNullOrWhiteSpace([string]$entry.Family)) { throw "Outcome registry entry $($entry.Code) is missing Family." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.Stage)) { throw "Outcome registry entry $($entry.Code) is missing Stage." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.WhenFires)) { throw "Outcome registry entry $($entry.Code) is missing WhenFires." }
    if ($null -eq $entry.Retryable -or $entry.Retryable -isnot [bool]) { throw "Outcome registry entry $($entry.Code) must expose boolean Retryable metadata." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.OperatorSeverity)) { throw "Outcome registry entry $($entry.Code) is missing OperatorSeverity." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.HandledBy)) { throw "Outcome registry entry $($entry.Code) is missing HandledBy." }
    if ([string]::IsNullOrWhiteSpace([string]$entry.OperatorAction)) { throw "Outcome registry entry $($entry.Code) is missing OperatorAction." }
}

if (-not (Test-MediaPipelineKnownOutcomeCode -Code 'SUBTITLE_BDPGS_OCR_FAILED')) {
    throw 'Known outcome code lookup rejected SUBTITLE_BDPGS_OCR_FAILED.'
}
if (Test-MediaPipelineKnownOutcomeCode -Code 'NOT_A_REAL_OUTCOME_CODE') {
    throw 'Known outcome code lookup accepted an unknown outcome code.'
}
$okMetadata = Get-MediaPipelineOutcomeCodeMetadata -Code 'OK'
if (-not $okMetadata -or $okMetadata.Family -ne 'non_failure_outcome' -or [bool]$okMetadata.Retryable -or $okMetadata.OperatorSeverity -ne 'info') {
    throw 'OK outcome metadata should be non-retryable informational metadata.'
}
$bdpgsTool = Get-MediaPipelineOutcomeCodeMetadata -Code 'SUBTITLE_BDPGS_OCR_TOOL_MISSING'
if (-not $bdpgsTool -or $bdpgsTool.Stage -ne 'subtitle-bdpgs' -or $bdpgsTool.HandledBy -notmatch 'Subtitles\.Bdpgs' -or $bdpgsTool.OperatorAction -notmatch 'OCR tool') {
    throw 'SUBTITLE_BDPGS_OCR_TOOL_MISSING metadata should point operators at OCR configuration.'
}
$nativeAborted = Get-MediaPipelineOutcomeCodeMetadata -Code 'NATIVE_ABORTED'
if (-not $nativeAborted -or $nativeAborted.Family -ne 'process_lifecycle' -or $nativeAborted.Stage -ne 'process-lifecycle' -or -not [bool]$nativeAborted.Retryable -or $nativeAborted.OperatorSeverity -ne 'warning' -or $nativeAborted.HandledBy -notmatch 'Native') {
    throw 'NATIVE_ABORTED metadata should be registered as a retryable native process-lifecycle outcome.'
}
if ($null -ne (Get-MediaPipelineOutcomeCodeMetadata -Code 'NOT_A_REAL_OUTCOME_CODE')) {
    throw 'Outcome metadata lookup returned metadata for an unknown outcome code.'
}

Write-Host "Failure code registry checks passed. Classifier codes: $($knownCodes.Count); outcome codes: $($outcomeCodes.Count); emitted codes scanned: $($emittedCodes.Count)"
