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

function Get-OutcomeTokenPattern {
    param([Parameter(Mandatory)] [string[]]$KnownCodes)

    $prefixes = @(
        $KnownCodes |
            Where-Object { $_ -ne 'OK' -and $_ -match '_' } |
            ForEach-Object { ([string]$_ -split '_', 2)[0] } |
            Sort-Object -Unique
    )
    if ($prefixes.Count -eq 0) { throw 'Outcome registry exposes no token prefixes.' }
    $prefixAlternation = (($prefixes | ForEach-Object { [regex]::Escape($_) }) -join '|')
    return "(?<![A-Z0-9_])(?<code>(?:(?:$prefixAlternation)[A-Z0-9]*_[A-Z0-9_]*[A-Z0-9]|OK))(?![A-Z0-9_])"
}

function Get-EmittedOutcomeCodesFromLines {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [AllowEmptyString()] [string[]]$Lines,
        [Parameter(Mandatory)] [string]$TokenPattern
    )

    $emissionSignalPattern = 'ErrorCode|errorCode|error_code|ReasonCode|reasonCode|reason_code|Register-SourceFailure|New-MediaPipelineProcessFileResult|New-FileIntegrityResult|New-\w+FailureRecord|SOURCE_MEDIA_AUDIO_|OUTPUT_DESTINATION_'
    return @(
        foreach ($line in $Lines) {
            if ($line -notmatch $emissionSignalPattern) { continue }
            foreach ($match in [regex]::Matches($line, $TokenPattern)) {
                [string]$match.Groups['code'].Value
            }
        }
    )
}

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

$mjpegHevcBsfText = @"
[vost#0:1/copy @ 000001749185b4c0] Codec 'mjpeg' (7) is not supported by the bitstream filter 'hevc_mp4toannexb'. Supported codecs are: hevc
Error initializing bitstream filter: hevc_mp4toannexb
Error opening output files: Invalid argument
"@
$mjpegHevcBsfCode = Get-FFmpegFailureCode -Stage 'remux-av' -ErrorText $mjpegHevcBsfText -ExitCode 234
if ($mjpegHevcBsfCode -ne 'REMUX_ATTACHED_PICTURE_MAPPED') {
    throw "MJPEG cover-art HEVC bitstream-filter failure should classify as REMUX_ATTACHED_PICTURE_MAPPED, got $mjpegHevcBsfCode."
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
$outcomeTokenPattern = Get-OutcomeTokenPattern -KnownCodes $outcomeCodes
$scannerFixtures = @(
    [pscustomobject]@{ Code = 'DYNAMIC_NEW_UNREGISTERED'; Line = "ErrorCode = 'DYNAMIC_NEW_UNREGISTERED'" },
    [pscustomobject]@{ Code = 'DOVI_NEW_UNREGISTERED'; Line = "errorCode = 'DOVI_NEW_UNREGISTERED'" },
    [pscustomobject]@{ Code = 'DESTINATION_NEW_UNREGISTERED'; Line = "error_code = 'DESTINATION_NEW_UNREGISTERED'" },
    [pscustomobject]@{ Code = 'LOCAL_NEW_UNREGISTERED'; Line = "ReasonCode = 'LOCAL_NEW_UNREGISTERED'" },
    [pscustomobject]@{ Code = 'OUTPUT_NEW_UNREGISTERED'; Line = "reasonCode = 'OUTPUT_NEW_UNREGISTERED'" },
    [pscustomobject]@{ Code = 'SIDECAR_NEW_UNREGISTERED'; Line = "reason_code = 'SIDECAR_NEW_UNREGISTERED'" }
)
foreach ($fixture in $scannerFixtures) {
    if ($fixture.Code -in $outcomeCodes) { throw "Scanner fixture unexpectedly became registered: $($fixture.Code)" }
    $detectedFixtureCodes = @(Get-EmittedOutcomeCodesFromLines -Lines @($fixture.Line) -TokenPattern $outcomeTokenPattern)
    if ($fixture.Code -notin $detectedFixtureCodes) {
        throw "Emitted-code scanner missed $($fixture.Code) through fixture line: $($fixture.Line)"
    }
}
$emittedCodes = @(
    foreach ($file in $scanFiles) {
        Get-EmittedOutcomeCodesFromLines -Lines @(Get-Content -LiteralPath $file.FullName) -TokenPattern $outcomeTokenPattern
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

$metadataFields = @('Family', 'Stage', 'WhenFires', 'Retryable', 'OperatorSeverity', 'HandledBy', 'OperatorAction')
foreach ($code in $knownCodes) {
    $failureMetadata = Get-MediaPipelineFailureCodeMetadata -Code $code
    $outcomeMetadata = Get-MediaPipelineOutcomeCodeMetadata -Code $code
    foreach ($field in $metadataFields) {
        if ($failureMetadata.$field -ne $outcomeMetadata.$field) {
            throw "Shared code $code has namespace-dependent $field metadata: failure='$($failureMetadata.$field)' outcome='$($outcomeMetadata.$field)'."
        }
    }
}
$canonicalSharedFamilies = @{
    ENCODER_UNAVAILABLE      = 'encode'
    FFMPEG_FAILED            = 'native_tool'
    FFMPEG_INVALID_ARGUMENT  = 'native_tool'
    FFMPEG_STOPPED           = 'native_tool'
    FFMPEG_TIMEOUT           = 'native_tool'
    OUTPUT_DISK_FULL         = 'publish'
    SYSTEM_OUT_OF_MEMORY     = 'native_tool'
}
foreach ($code in $canonicalSharedFamilies.Keys) {
    $metadata = Get-MediaPipelineOutcomeCodeMetadata -Code $code
    if ($metadata.Family -ne $canonicalSharedFamilies[$code]) {
        throw "$code canonical family must be $($canonicalSharedFamilies[$code]), got $($metadata.Family)."
    }
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
$scratchReuse = Get-MediaPipelineOutcomeCodeMetadata -Code 'SCRATCH_COPY_REUSED'
if (-not $scratchReuse -or $scratchReuse.Family -ne 'non_failure_outcome' -or $scratchReuse.Stage -ne 'source-intake' -or [bool]$scratchReuse.Retryable -or $scratchReuse.OperatorSeverity -ne 'info' -or $scratchReuse.HandledBy -notmatch 'ScratchCopy' -or $scratchReuse.OperatorAction -notmatch 'No repair action') {
    throw 'SCRATCH_COPY_REUSED metadata should remain a non-retryable informational source-intake outcome.'
}
$scratchUnsafe = Get-MediaPipelineOutcomeCodeMetadata -Code 'SCRATCH_SAFE_NAME_UNSAFE'
if (-not $scratchUnsafe -or $scratchUnsafe.Family -ne 'source_media' -or $scratchUnsafe.Stage -ne 'source-intake' -or [bool]$scratchUnsafe.Retryable -or $scratchUnsafe.OperatorSeverity -ne 'error' -or $scratchUnsafe.OperatorAction -notmatch 'Do not bypass the scratch boundary') {
    throw 'SCRATCH_SAFE_NAME_UNSAFE metadata should fail closed with boundary-repair guidance.'
}
$pendingBackpressure = Get-MediaPipelineOutcomeCodeMetadata -Code 'PENDING_PUBLISH_BACKPRESSURE_BLOCKED'
if (-not $pendingBackpressure -or $pendingBackpressure.Family -ne 'publish' -or $pendingBackpressure.Stage -ne 'publish' -or -not [bool]$pendingBackpressure.Retryable -or $pendingBackpressure.OperatorSeverity -ne 'warning' -or $pendingBackpressure.HandledBy -notmatch 'PendingPush' -or $pendingBackpressure.OperatorAction -notmatch 'pending publish manifests') {
    throw 'PENDING_PUBLISH_BACKPRESSURE_BLOCKED metadata should direct the operator to manifest-backed publish recovery.'
}
$pendingTrustCodes = @('OUTPUT_HASH_INVALID', 'OUTPUT_HASH_MISSING', 'SIDECAR_HASH_INVALID', 'SIDECAR_SIZE_INVALID')
foreach ($code in $pendingTrustCodes) {
    $metadata = Get-MediaPipelineOutcomeCodeMetadata -Code $code
    if (-not $metadata -or $metadata.Family -ne 'publish' -or $metadata.Stage -ne 'publish' -or [bool]$metadata.Retryable -or $metadata.OperatorSeverity -ne 'error' -or $metadata.HandledBy -notmatch 'Pending' -or $metadata.OperatorAction -notmatch 'Do not drain') {
        throw "$code metadata must fail closed and direct the operator through trusted pending-manifest repair."
    }
}
$trackVerification = Get-MediaPipelineOutcomeCodeMetadata -Code 'OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED'
if (-not $trackVerification -or $trackVerification.Family -ne 'publish' -or $trackVerification.Stage -ne 'publish' -or $trackVerification.HandledBy -notmatch 'MediaTrackVerification' -or $trackVerification.OperatorAction -notmatch 'Do not publish') {
    throw 'OUTPUT_MEDIA_TRACK_VERIFICATION_FAILED metadata must preserve fail-closed publish guidance.'
}
$localWorkerCodes = @('LOCAL_WORKER_CHILD_STALE_HEARTBEAT', 'LOCAL_WORKER_DUPLICATE_CLAIM', 'LOCAL_WORKER_FAILED', 'LOCAL_WORKER_RESULT_INVALID', 'LOCAL_WORKER_START_FAILED', 'LOCAL_WORKER_STOPPED')
foreach ($code in $localWorkerCodes) {
    $metadata = Get-MediaPipelineOutcomeCodeMetadata -Code $code
    if (-not $metadata -or $metadata.Family -ne 'process_lifecycle' -or $metadata.Stage -ne 'process-lifecycle' -or $metadata.HandledBy -notmatch 'LocalWorker' -or $metadata.OperatorAction -notmatch 'claim') {
        throw "$code metadata must route operators through local-worker lifecycle evidence."
    }
}
$subtitleHelper = Get-MediaPipelineOutcomeCodeMetadata -Code 'SUBTITLE_HELPER_SELFCHECK_FAILED'
if (-not $subtitleHelper -or $subtitleHelper.Family -ne 'subtitle' -or $subtitleHelper.Stage -ne 'subtitle' -or $subtitleHelper.HandledBy -notmatch 'Subtitles') {
    throw 'SUBTITLE_HELPER_SELFCHECK_FAILED metadata must identify the subtitle startup surface.'
}
$destinationEvidenceMissing = Get-MediaPipelineOutcomeCodeMetadata -Code 'DESTINATION_NAMING_EVIDENCE_MISSING'
if (-not $destinationEvidenceMissing -or $destinationEvidenceMissing.Family -ne 'destination_naming' -or $destinationEvidenceMissing.Stage -ne 'destination-naming' -or [bool]$destinationEvidenceMissing.Retryable -or $destinationEvidenceMissing.OperatorSeverity -ne 'error' -or $destinationEvidenceMissing.HandledBy -notmatch 'RunMonitorState' -or $destinationEvidenceMissing.OperatorAction -notmatch 'Refresh Queue') {
    throw 'DESTINATION_NAMING_EVIDENCE_MISSING metadata should fail closed and direct the operator to refresh Queue.'
}
$destinationPlanMismatch = Get-MediaPipelineOutcomeCodeMetadata -Code 'DESTINATION_NAMING_PLAN_MISMATCH'
if (-not $destinationPlanMismatch -or $destinationPlanMismatch.Family -ne 'destination_naming' -or $destinationPlanMismatch.Stage -ne 'destination-naming' -or [bool]$destinationPlanMismatch.Retryable -or $destinationPlanMismatch.OperatorSeverity -ne 'error' -or $destinationPlanMismatch.HandledBy -notmatch 'PipelineProcessing' -or $destinationPlanMismatch.OperatorAction -notmatch 'one-off cleanup filter') {
    throw 'DESTINATION_NAMING_PLAN_MISMATCH metadata should fail closed without directing the operator to add another rename filter.'
}
if ($null -ne (Get-MediaPipelineOutcomeCodeMetadata -Code 'NOT_A_REAL_OUTCOME_CODE')) {
    throw 'Outcome metadata lookup returned metadata for an unknown outcome code.'
}

Write-Host "Failure code registry checks passed. Classifier codes: $($knownCodes.Count); outcome codes: $($outcomeCodes.Count); emitted codes scanned: $($emittedCodes.Count)"
