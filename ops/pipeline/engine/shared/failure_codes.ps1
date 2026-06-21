# ==============================================================================
# ops\pipeline\engine\shared\failure_codes.ps1
# ==============================================================================
# Pure stderr-text classifiers extracted from MediaPipeline.ps1.
#
# Every function in here takes plain strings/ints in and returns a stable
# uppercase-snake-case error code (or summary string). They have NO side
# effects, no logging, no $script:* references — which makes them the
# easiest tier of code in the pipeline to unit-test in isolation later.
#
# When ffmpeg fails mid-encode we use these to decide:
#   1. whether to retry with libx265 (Test-IsNvencError → NVENC-only failure)
#   2. how to label the failure in sidecars / failure markers
#   3. what suggested-action message to surface to the operator
# ==============================================================================

function Get-MediaPipelineKnownFailureCodes {
    return @(
        'ENCODER_UNAVAILABLE',
        'ENCODE_CPU_DISK_FULL',
        'ENCODE_CPU_FFMPEG_FAILED',
        'ENCODE_CPU_OOM',
        'ENCODE_CPU_TIMEOUT',
        'ENCODE_CPU_X265_INTERNAL',
        'ENCODE_FFMPEG_FAILED',
        'ENCODE_NVENC_FAILED',
        'ENCODE_TIMEOUT',
        'FFMPEG_FAILED',
        'FFMPEG_INVALID_ARGUMENT',
        'FFMPEG_STOPPED',
        'FFMPEG_TIMEOUT',
        'FILE_MISSING',
        'MEDIA_ACCESS_DENIED',
        'MEDIA_CONTAINER_INVALID',
        'MEDIA_PROBE_FAILED',
        'MEDIA_STREAM_UNSUPPORTED',
        'MEDIA_TIMESTAMP_ERROR',
        'MEDIA_TRUNCATED',
        'MKVMERGE_INPUT_INVALID',
        'MKVMERGE_INVALID_ARGUMENT',
        'MKVMERGE_STOPPED',
        'MKVMERGE_TIMEOUT',
        'OUTPUT_DISK_FULL',
        'REMUX_ATTACHED_PICTURE_MAPPED',
        'REMUX_FFMPEG_FAILED',
        'REMUX_HEVC_MKV_BITSTREAM_FAILED',
        'REMUX_MKVMERGE_FAILED',
        'REMUX_MKV_HEADER_WRITE_FAILED',
        'REMUX_TIMEOUT',
        'SOURCE_FILE_MISSING',
        'SOURCE_MEDIA_CONTAINER_INVALID',
        'SOURCE_MEDIA_DECODE_FAILED',
        'SOURCE_MEDIA_STREAM_UNSUPPORTED',
        'SOURCE_MEDIA_TRUNCATED',
        'SOURCE_MEDIA_VIDEO_MISSING',
        'SYSTEM_OUT_OF_MEMORY'
    )
}

function Get-MediaPipelineKnownOutcomeCodes {
    $codes = [System.Collections.Generic.List[string]]::new()
    foreach ($code in @(Get-MediaPipelineKnownFailureCodes)) { $codes.Add($code) }
    foreach ($code in @(
        'ALREADY_PROCESSED',
        'AUDIO_ARGUMENT_BUILD_FAILED',
        'BAD_EXTENSION',
        'ENCODE_CPU_INSUFFICIENT_SPACE',
        'ENCODE_CPU_MUTEX_UNAVAILABLE',
        'ENCODE_DURATION_MISMATCH',
        'ENCODE_OUTPUT_MISSING',
        'ENCODE_QUALITY_BELOW_FLOOR',
        'ENCODE_QUALITY_REVIEW',
        'ENCODE_QUALITY_VERIFICATION_FAILED',
        'ENCODE_SIZE_GUARD_EXCEEDED',
        'ENCODE_UNEXPECTED_EXCEPTION',
        'DOVI_RPU_EXTRACT_FAILED',
        'DYNAMIC_HDR_HEVC_EXTRACT_FAILED',
        'DYNAMIC_HDR_EXTRACTION_RESULT_MISSING',
        'DYNAMIC_HDR_NATIVE_RUNNER_MISSING',
        'DYNAMIC_HDR_PLAN_MISSING',
        'DYNAMIC_HDR_SCRATCH_PATH_MISSING',
        'DYNAMIC_HDR_TOOL_MISSING',
        'DYNAMIC_HDR_UNPRESERVABLE',
        'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED',
        'DYNAMIC_HDR_WORKDIR_MISSING',
        'DYNAMIC_HDR_X265_PATH_BASE_MISSING',
        'DYNAMIC_HDR_X265_PATH_UNREPRESENTABLE',
        'FILE_PATH_EMPTY',
        'FILE_OVERRIDE_INVALID',
        'FILE_ZERO_BYTES',
        'HDR_DETECTION_UNKNOWN',
        'HDR10PLUS_EXTRACT_FAILED',
        'INTEGRITY_DISABLED',
        'MEDIA_DURATION_MISSING',
        'MEDIA_INTEGRITY_FAILED',
        'MEDIA_INTEGRITY_EXCEPTION',
        'MEDIA_PROBE_STOPPED',
        'MEDIA_PROBE_TIMEOUT',
        'MKVMERGE_WARNINGS',
        'MKVMERGE_WARNING_STREAM_LOSS',
        'NATIVE_ABORTED',
        'NATIVE_START_FAILED',
        'NATIVE_STOPPED',
        'NATIVE_TIMEOUT',
        'OK',
        'OPERATOR_REQUIRED',
        'OUTPUT_DESTINATION_LOW_SPACE',
        'OUTPUT_DESTINATION_SPACE_UNKNOWN',
        'OUTPUT_PATH_UNSUPPORTED',
        'OUTPUT_ROOT_MISSING',
        'OUTPUT_SIZE_INVALID',
        'OUTPUT_SIZE_MISSING',
        'PENDING_PARK_FAILED',
        'PERMANENT_FAILURE',
        'PROGRESS_PERSISTENCE_FAILED',
        'PUBLISH_COPY_FAILED',
        'REMUX_AUDIO_TID_MAPPING_FAILED',
        'REMUX_DURATION_MISMATCH',
        'REMUX_INSUFFICIENT_SPACE',
        'REMUX_OUTPUT_MISSING',
        'REMUX_UNEXPECTED_EXCEPTION',
        'SCRATCH_COPY_UNREADABLE',
        'SCRATCH_INTEGRITY_FAILED',
        'SIDECAR_ORIGINAL_MISSING',
        'SIDECAR_ORIGINAL_PAYLOAD_MISSING',
        'SIDECAR_REQUIRED_FIELD_MISSING',
        'SIDECAR_WRITE_FAILED',
        'SOURCE_FAILURE_MARKER',
        'SOURCE_FILE_PATH_EMPTY',
        'SOURCE_FILE_ZERO_BYTES',
        'SOURCE_MEDIA_ACCESS_DENIED',
        'SOURCE_MEDIA_AUDIO_INVALID',
        'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED',
        'SOURCE_MEDIA_AUDIO_MISSING',
        'SOURCE_MEDIA_AUDIO_OVERRIDE_STRIPPED',
        'SOURCE_MEDIA_AUDIO_PRESENCE_PROBE_FAILED',
        'SOURCE_MEDIA_DURATION_MISSING',
        'SOURCE_MEDIA_INTEGRITY_EXCEPTION',
        'SOURCE_MEDIA_PROBE_FAILED',
        'SOURCE_MEDIA_PROBE_STOPPED',
        'SOURCE_MEDIA_PROBE_TIMEOUT',
        'SOURCE_MEDIA_UNREADABLE',
        'SOURCE_MEDIA_VIDEO_MISSING',
        'SOURCE_STILL_WRITING',
        'SOURCE_TV_PARSE_FAILED',
        'SOURCE_VIDEO_STREAM_MISSING',
        'SOURCE_VIDEO_STREAM_PROBE_FAILED',
        'SOURCE_VIDEO_STREAMS_UNVETTED',
        'STOP_REQUESTED',
        'SUBTITLE_ASS_CONVERT_EXCEPTION',
        'SUBTITLE_ASS_CONVERT_FAILED',
        'SUBTITLE_ASS_CONVERT_STOPPED',
        'SUBTITLE_ASS_CONVERT_TIMEOUT',
        'SUBTITLE_ASS_SRT_EMPTY',
        'SUBTITLE_ASS_SRT_INVALID',
        'SUBTITLE_BDPGS_CONTAINER_UNSUPPORTED',
        'SUBTITLE_BDPGS_OCR_EMPTY',
        'SUBTITLE_BDPGS_OCR_EXCEPTION',
        'SUBTITLE_BDPGS_OCR_FAILED',
        'SUBTITLE_BDPGS_OCR_LANGUAGE_UNKNOWN',
        'SUBTITLE_BDPGS_OCR_TOOL_MISSING',
        'SUBTITLE_BDPGS_SUP_EMPTY',
        'SUBTITLE_BDPGS_SUP_EXTRACT_EXCEPTION',
        'SUBTITLE_BDPGS_SUP_EXTRACT_FAILED',
        'SUBTITLE_BDPGS_TESSDATA_MISSING',
        'SUBTITLE_BURN_MULTIPLE_TRACKS',
        'SUBTITLE_BURN_STREAM_UNRESOLVED',
        'SUBTITLE_BURN_UNSUPPORTED',
        'SUBTITLE_BURN_UNSUPPORTED_CODEC',
        'SUBTITLE_MP4_EXTERNAL_SRT_REQUIRED',
        'SUBTITLE_MP4_CONVERTED_SRT_REDUCTION_BLOCKED',
        'SUBTITLE_PROBE_FAILED',
        'SUBTITLE_PROBE_JSON_INVALID',
        'SUBTITLE_TX3G_CONTAINER_UNSUPPORTED',
        'SUBTITLE_TX3G_EXTRACT_FAILED',
        'SUBTITLE_TX3G_EXTRACT_STOPPED',
        'SUBTITLE_TX3G_EXTRACT_TIMEOUT',
        'SUBTITLE_TX3G_SRT_EMPTY',
        'SUBTITLE_TX3G_SRT_INVALID',
        'SUBTITLE_TX3G_SRT_PUBLISH_FAILED',
        'SUBTITLE_TX3G_UNKNOWN_FAILURE',
        'SUBTITLE_UNKNOWN_FAILURE',
        'SUBTITLE_VOBSUB_CONTAINER_UNSUPPORTED',
        'SUBTITLE_VOBSUB_EXTRACT_FAILED',
        'SUBTITLE_VOBSUB_EXTRACT_TOOL_MISSING',
        'SUBTITLE_VOBSUB_EXTRACT_UNSUPPORTED_CONTAINER',
        'SUBTITLE_VOBSUB_OCR_EMPTY',
        'SUBTITLE_VOBSUB_OCR_FAILED',
        'SUBTITLE_VOBSUB_OCR_LANGUAGE_UNKNOWN',
        'SUBTITLE_VOBSUB_OCR_TOOL_MISSING',
        'SUBTITLE_VOBSUB_OCR_TOOL_UNSUPPORTED',
        'SUBTITLE_VOBSUB_PAIR_MISSING',
        'SUBTITLE_VOBSUB_SIDECAR_PRESERVE_UNSUPPORTED',
        'SUBTITLE_VOBSUB_TESSDATA_MISSING',
        'SUBTITLE_VOBSUB_TESSERACT_MISSING',
        'TRANSIENT_FAILURE',
        'TV_PARSE_UNRELIABLE',
        'UNKNOWN_FAILURE'
    )) {
        $codes.Add($code)
    }
    return @($codes | Sort-Object -Unique)
}

function Get-MediaPipelineOutcomeCodeFamily {
    param([string]$Code)

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    if ($codeText -match '^OK$|^ALREADY_PROCESSED$|^INTEGRITY_DISABLED$') { return 'non_failure_outcome' }
    if ($codeText -match '^ENCODE_CPU_') { return 'encode_cpu' }
    if ($codeText -match '^ENCODE_|^ENCODER_|^HDR_|^DYNAMIC_HDR_|^DOVI_|^HDR10PLUS_') { return 'encode' }
    if ($codeText -match '^REMUX_|^MKVMERGE_') { return 'remux' }
    if ($codeText -match '^SUBTITLE_') { return 'subtitle' }
    if ($codeText -match '^AUDIO_|^SOURCE_MEDIA_AUDIO_') { return 'audio' }
    if ($codeText -match '^SOURCE_|^MEDIA_|^FILE_|^SCRATCH_') { return 'source_media' }
    if ($codeText -match '^OUTPUT_|^PUBLISH_|^PENDING_|^SIDECAR_') { return 'publish' }
    if ($codeText -match '^PROGRESS_|^STOP_|^NATIVE_') { return 'process_lifecycle' }
    return 'generic_failure'
}

function Get-MediaPipelineFailureCodeFamily {
    param([string]$Code)

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    if ($codeText -match '^ENCODE_CPU_') { return 'encode_cpu' }
    if ($codeText -match '^ENCODE_') { return 'encode' }
    if ($codeText -match '^REMUX_|^MKVMERGE_') { return 'remux' }
    if ($codeText -match '^SOURCE_|^MEDIA_|^FILE_') { return 'source_media' }
    if ($codeText -match '^OUTPUT_') { return 'output' }
    return 'native_tool'
}

function Get-MediaPipelineCodeStage {
    param(
        [string]$Code,
        [string]$Family
    )

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    switch -Regex ($codeText) {
        '^SUBTITLE_BDPGS_' { return 'subtitle-bdpgs' }
        '^SUBTITLE_VOBSUB_' { return 'subtitle-vobsub' }
        '^SUBTITLE_TX3G_'  { return 'subtitle-tx3g' }
        '^SUBTITLE_ASS_'   { return 'subtitle-ass' }
        '^SUBTITLE_'       { return 'subtitle' }
        '^ENCODE_CPU_'     { return 'encode-cpu' }
        '^ENCODE_|^ENCODER_|^HDR_|^DYNAMIC_HDR_|^DOVI_|^HDR10PLUS_' { return 'encode' }
        '^REMUX_|^MKVMERGE_' { return 'remux' }
        '^SOURCE_MEDIA_AUDIO_|^AUDIO_' { return 'audio' }
        '^SOURCE_|^MEDIA_|^FILE_|^SCRATCH_' { return 'source-intake' }
        '^OUTPUT_|^PUBLISH_|^PENDING_|^SIDECAR_' { return 'publish' }
        '^PROGRESS_|^STOP_|^NATIVE_' { return 'process-lifecycle' }
        '^OK$|^ALREADY_PROCESSED$|^INTEGRITY_DISABLED$' { return 'non-failure' }
        default {
            if ($Family) { return ([string]$Family).Replace('_', '-') }
            return 'pipeline'
        }
    }
}

function Get-MediaPipelineCodeHandledBy {
    param(
        [string]$Code,
        [string]$Family
    )

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    switch -Regex ($codeText) {
        '^SUBTITLE_BDPGS_' { return 'Subtitles.Bdpgs.ps1' }
        '^SUBTITLE_VOBSUB_' { return 'Subtitles.VobSub.ps1' }
        '^SUBTITLE_TX3G_'  { return 'Subtitles.Tx3g.ps1' }
        '^SUBTITLE_ASS_'   { return 'Subtitles.Ass.ps1' }
        '^SUBTITLE_'       { return 'Subtitles.ps1' }
        '^SOURCE_MEDIA_AUDIO_|^AUDIO_' { return 'Audio.ps1' }
        '^OUTPUT_|^PUBLISH_|^PENDING_|^SIDECAR_' { return 'PublishCompletion.ps1 / PendingPush.ps1' }
        '^SOURCE_|^MEDIA_|^FILE_|^SCRATCH_' { return 'MediaProbe.ps1 / ScratchCopy.ps1 / FailureState.ps1' }
        '^REMUX_|^MKVMERGE_' { return 'PipelineProcessing.ps1 / Native.ps1' }
        '^ENCODE_|^ENCODER_|^HDR_|^DYNAMIC_HDR_|^DOVI_|^HDR10PLUS_' { return 'PipelineProcessing.ps1 / DynamicHdr.ps1 / FfmpegProgress.ps1' }
        '^PROGRESS_|^STOP_|^NATIVE_' { return 'PipelineProcessing.ps1 / Native.ps1' }
        '^OK$|^ALREADY_PROCESSED$|^INTEGRITY_DISABLED$' { return 'PipelineProcessing.ps1' }
        default {
            if ($Family -eq 'native_tool') { return 'FailureCodes.ps1 / NativeProcessContracts.ps1' }
            return 'FailureState.ps1'
        }
    }
}

function Get-MediaPipelineCodeRetryable {
    param(
        [string]$Code,
        [string]$Family
    )

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    if ($codeText -match '^OK$|^ALREADY_PROCESSED$|^BAD_EXTENSION$|^OPERATOR_REQUIRED$|^PERMANENT_FAILURE$|^TV_PARSE_UNRELIABLE$|^SOURCE_TV_PARSE_FAILED$|^OUTPUT_PATH_UNSUPPORTED$|^FILE_PATH_EMPTY$|^FILE_ZERO_BYTES$|^SOURCE_FILE_PATH_EMPTY$|^SOURCE_FILE_ZERO_BYTES$|QUALITY_BELOW_FLOOR') {
        return $false
    }
    if ($codeText -match 'TRUNCATED|CONTAINER_INVALID|DECODE_FAILED|STREAM_UNSUPPORTED|AUDIO_MISSING|VIDEO_MISSING|AUDIO_OVERRIDE_STRIPPED|INTEGRITY_FAILED|ACCESS_DENIED') {
        return $false
    }
    if ($codeText -match 'TIMEOUT|STOPPED|STILL_WRITING|LOW_SPACE|SPACE_UNKNOWN|DISK_FULL|PUBLISH|PENDING|SIDECAR|TRANSIENT|NATIVE_|PROGRESS_') {
        return $true
    }
    if ($Family -in @('non_failure_outcome')) { return $false }
    if ($Family -in @('publish', 'process_lifecycle')) { return $true }
    return $true
}

function Get-MediaPipelineCodeOperatorSeverity {
    param(
        [string]$Code,
        [string]$Family,
        [bool]$Retryable
    )

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    if ($Family -eq 'non_failure_outcome' -or $codeText -eq 'OK' -or $codeText -eq 'ALREADY_PROCESSED') { return 'info' }
    if ($codeText -match 'STOPPED|STILL_WRITING|LOW_SPACE|SPACE_UNKNOWN|TIMEOUT|TRANSIENT') { return 'warning' }
    if ($Retryable) { return 'warning' }
    return 'error'
}

function Get-MediaPipelineCodeWhenFires {
    param(
        [string]$Code,
        [string]$Family
    )

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    switch -Regex ($codeText) {
        '^OK$' { return 'The pipeline step completed successfully or reported an accepted non-failure outcome.' }
        '^ALREADY_PROCESSED$' { return 'The source matched existing completed/published evidence and was skipped as already processed.' }
        'STILL_WRITING' { return 'The source appears to be growing or unstable and should be retried after the copy finishes.' }
        'TIMEOUT' { return 'A tool or pipeline step exceeded its configured timeout.' }
        'STOPPED' { return 'The operator or runtime requested that the in-flight process stop.' }
        'LOW_SPACE|SPACE_UNKNOWN|DISK_FULL|INSUFFICIENT_SPACE' { return 'The destination or scratch disk did not have enough verifiable free space.' }
        'TOOL_MISSING|ENCODER_UNAVAILABLE' { return 'A required encoder, OCR tool, or bundled/system executable was unavailable.' }
        'AUDIO_MISSING|AUDIO_INVALID|AUDIO_OVERRIDE_STRIPPED' { return 'Audio policy could not produce an acceptable output audio stream.' }
        'VIDEO_MISSING' { return 'Source probing found no usable video stream for a source being processed by the video media pipeline.' }
        'SUBTITLE' { return 'Subtitle probing, extraction, conversion, OCR, validation, or sidecar publish failed.' }
        'PUBLISH|PENDING|SIDECAR' { return 'Publishing, deferred publish parking, drain, manifest, or sidecar work failed.' }
        'TRUNCATED|CONTAINER_INVALID|DECODE_FAILED|STREAM_UNSUPPORTED|PROBE_FAILED|PROBE_TIMEOUT' { return 'The source media could not be probed, decoded, or validated as healthy media.' }
        'DURATION_MISMATCH|OUTPUT_MISSING|SIZE_GUARD|QUALITY_BELOW_FLOOR|QUALITY_REVIEW' { return 'Post-processing verification rejected the generated output.' }
        '^DYNAMIC_HDR_|^DOVI_|^HDR10PLUS_' { return 'Dynamic HDR metadata extraction, planning, or verification failed before preserve-mode output could be accepted.' }
        '^REMUX_|^MKVMERGE_' { return 'Remux or mkvmerge processing failed before an output could be accepted.' }
        '^ENCODE_' { return 'Encode processing failed before an output could be accepted.' }
        default {
            if ($Family) { return "The $Family pipeline surface emitted $codeText." }
            return "The pipeline emitted $codeText."
        }
    }
}

function Get-MediaPipelineCodeOperatorAction {
    param(
        [string]$Code,
        [string]$Family,
        [bool]$Retryable
    )

    $codeText = if ($Code) { ([string]$Code).Trim().ToUpperInvariant() } else { '' }
    switch -Regex ($codeText) {
        '^OK$|^ALREADY_PROCESSED$|^INTEGRITY_DISABLED$' {
            return 'No repair action is implied by this code; inspect surrounding status before treating it as a failure.'
        }
        'LOW_SPACE|SPACE_UNKNOWN|DISK_FULL|INSUFFICIENT_SPACE' {
            return 'Free disk space, verify the destination path, then rerun or drain only after parked artifacts are accounted for.'
        }
        'SUBTITLE_BDPGS_OCR_TOOL_MISSING|SUBTITLE_BDPGS_TESSDATA_MISSING|SUBTITLE_BDPGS_OCR_LANGUAGE_UNKNOWN' {
            return 'Fix the BDPGS OCR tool/tessdata/language setting or disable BDPGS OCR before retrying the source.'
        }
        'SUBTITLE_VOBSUB_SIDECAR_PRESERVE_UNSUPPORTED' {
            return 'Enable VobSub OCR, keep the output format/path able to preserve the original VobSub, or handle the external IDX/SUB sidecar manually before retrying.'
        }
        'SUBTITLE_VOBSUB_OCR_TOOL_MISSING|SUBTITLE_VOBSUB_OCR_TOOL_UNSUPPORTED|SUBTITLE_VOBSUB_TESSERACT_MISSING|SUBTITLE_VOBSUB_TESSDATA_MISSING|SUBTITLE_VOBSUB_OCR_LANGUAGE_UNKNOWN|SUBTITLE_VOBSUB_EXTRACT_TOOL_MISSING' {
            return 'Fix the VobSub OCR/extraction tool and language settings, ensure bundled Tesseract is available, or disable VobSub OCR before retrying the source.'
        }
        'AUDIO_MISSING|AUDIO_OVERRIDE_STRIPPED|AUDIO_INVALID' {
            return 'Review source audio streams and per-file audio overrides before retrying or accepting no-audio output.'
        }
        'VIDEO_MISSING' {
            return 'Inspect or replace the source media; do not clear the failure marker until source health is understood.'
        }
        'TRUNCATED|CONTAINER_INVALID|DECODE_FAILED|STREAM_UNSUPPORTED|PROBE_FAILED|PROBE_TIMEOUT' {
            return 'Inspect or replace the source media; do not clear the failure marker until source health is understood.'
        }
        'PUBLISH|PENDING|SIDECAR' {
            return 'Inspect pending publish manifests, parked media plus sidecars, share availability, and drain summaries before retry or cleanup.'
        }
        'QUALITY_BELOW_FLOOR|QUALITY_REVIEW' {
            return 'Compare the recorded quality score and metric against the configured thresholds; review the encode settings or thresholds before re-encoding or accepting the output.'
        }
        default {
            if ($Retryable) {
                return 'Inspect logs, failure artifacts, source health, and output/pending state before retrying.'
            }
            return 'Inspect the failure marker, run logs, source health, output state, and pending publish state before retry or cleanup.'
        }
    }
}

function New-MediaPipelineCodeMetadata {
    param(
        [Parameter(Mandatory)] [string]$Code,
        [string]$Family = $null
    )

    $codeText = ([string]$Code).Trim().ToUpperInvariant()
    $resolvedFamily = if ($Family) { $Family } else { Get-MediaPipelineOutcomeCodeFamily -Code $codeText }
    $retryable = Get-MediaPipelineCodeRetryable -Code $codeText -Family $resolvedFamily
    [pscustomobject]@{
        Code             = $codeText
        Family           = $resolvedFamily
        Stage            = Get-MediaPipelineCodeStage -Code $codeText -Family $resolvedFamily
        WhenFires        = Get-MediaPipelineCodeWhenFires -Code $codeText -Family $resolvedFamily
        Retryable        = [bool]$retryable
        OperatorSeverity = Get-MediaPipelineCodeOperatorSeverity -Code $codeText -Family $resolvedFamily -Retryable ([bool]$retryable)
        HandledBy        = Get-MediaPipelineCodeHandledBy -Code $codeText -Family $resolvedFamily
        OperatorAction   = Get-MediaPipelineCodeOperatorAction -Code $codeText -Family $resolvedFamily -Retryable ([bool]$retryable)
    }
}

function Get-MediaPipelineFailureCodeRegistry {
    foreach ($code in @(Get-MediaPipelineKnownFailureCodes)) {
        New-MediaPipelineCodeMetadata -Code $code -Family (Get-MediaPipelineFailureCodeFamily -Code $code)
    }
}

function Get-MediaPipelineOutcomeCodeRegistry {
    foreach ($code in @(Get-MediaPipelineKnownOutcomeCodes)) {
        New-MediaPipelineCodeMetadata -Code $code -Family (Get-MediaPipelineOutcomeCodeFamily -Code $code)
    }
}

function Get-MediaPipelineFailureCodeMetadata {
    param([string]$Code)
    if (-not (Test-MediaPipelineKnownFailureCode -Code $Code)) { return $null }
    $codeText = ([string]$Code).Trim().ToUpperInvariant()
    return New-MediaPipelineCodeMetadata -Code $codeText -Family (Get-MediaPipelineFailureCodeFamily -Code $codeText)
}

function Get-MediaPipelineOutcomeCodeMetadata {
    param([string]$Code)
    if (-not (Test-MediaPipelineKnownOutcomeCode -Code $Code)) { return $null }
    $codeText = ([string]$Code).Trim().ToUpperInvariant()
    return New-MediaPipelineCodeMetadata -Code $codeText -Family (Get-MediaPipelineOutcomeCodeFamily -Code $codeText)
}

function Test-MediaPipelineKnownFailureCode {
    param([string]$Code)
    if ([string]::IsNullOrWhiteSpace($Code)) { return $false }
    return ([string]$Code) -in @(Get-MediaPipelineKnownFailureCodes)
}

function Test-MediaPipelineKnownOutcomeCode {
    param([string]$Code)
    if ([string]::IsNullOrWhiteSpace($Code)) { return $false }
    return ([string]$Code) -in @(Get-MediaPipelineKnownOutcomeCodes)
}

function Get-FFprobeFailureCode {
    param([string]$ErrorText)

    $text = if ($ErrorText) { $ErrorText } else { "" }
    if ($text -match 'EBML header parsing failed|invalid as first byte of an EBML|moov atom not found|Invalid data found when processing input|Invalid data') {
        return 'MEDIA_CONTAINER_INVALID'
    }
    if ($text -match 'End of file|truncat|Packet corrupt|partial file') {
        return 'MEDIA_TRUNCATED'
    }
    if ($text -match 'Permission denied|Access is denied|denied') {
        return 'MEDIA_ACCESS_DENIED'
    }
    if ($text -match 'No such file or directory|cannot find the file') {
        return 'FILE_MISSING'
    }
    if ($text -match 'could not find codec parameters|unspecified pixel format|unsupported codec') {
        return 'MEDIA_STREAM_UNSUPPORTED'
    }
    return 'MEDIA_PROBE_FAILED'
}

function Get-ErrorTextSummary {
    param(
        [string]$ErrorText,
        [int]$MaxLines = 3
    )

    if ([string]::IsNullOrWhiteSpace($ErrorText)) { return "" }
    $noisePattern = '^(frame=|fps=|stream_|bitrate=|total_size=|out_time_us=|out_time_ms=|out_time=|dup_frames=|drop_frames=|speed=|progress=|video:|audio:|subtitle:)'
    $lines = @(
        $ErrorText -split '\r?\n' |
            ForEach-Object { ([string]$_).Trim() } |
            Where-Object { $_ -match '\S' -and $_ -notmatch $noisePattern }
    )
    if ($lines.Count -eq 0) { return "" }
    return (($lines | Select-Object -Last $MaxLines) -join ' | ')
}

function Get-FFmpegFailureCode {
    param(
        [string]$Stage,
        [string]$ErrorText,
        [int]$ExitCode = 1
    )

    $stageText = if ($Stage) { $Stage.ToLowerInvariant() } else { "" }
    $text = if ($ErrorText) { $ErrorText } else { "" }
    $ffprobeCode = Get-FFprobeFailureCode -ErrorText $text
    $isEncode = $stageText -match 'encode'
    $isRemux = $stageText -match 'remux'
    # E2 fix — distinguish CPU-fallback failures from NVENC failures.
    # The repro stage is 'encode-cpu' for the libx265 fallback (and
    # 'encode-cpu-*' for any future variants), so any consumer that
    # routes by error_code can show CPU-specific guidance.
    $isCpuEncode = $stageText -match '^encode-cpu(\b|-)'

    if ($text -match '\[KILLED:\s*TIMEOUT|timed out|timeout after') {
        if ($isCpuEncode) { return 'ENCODE_CPU_TIMEOUT' }
        if ($isEncode) { return 'ENCODE_TIMEOUT' }
        if ($isRemux) { return 'REMUX_TIMEOUT' }
        return 'FFMPEG_TIMEOUT'
    }
    if ($text -match 'video_stream_missing|no usable video stream|Stream map .*0:V.*matches no streams') {
        return 'SOURCE_MEDIA_VIDEO_MISSING'
    }
    if ($text -match '\[KILLED:\s*STOP|stop requested') { return 'FFMPEG_STOPPED' }
    if ($text -match 'No space left on device|not enough space|disk full') {
        if ($isCpuEncode) { return 'ENCODE_CPU_DISK_FULL' }
        return 'OUTPUT_DISK_FULL'
    }
    if ($text -match 'Permission denied|Access is denied|UnauthorizedAccess') { return 'MEDIA_ACCESS_DENIED' }
    # NVENC-only signatures must be tested first — InitializeEncoder /
    # NV_ENC_ERR / nvcuda strings only come from the NVENC path. Anything
    # that still reaches the libx265 stage and uses the word "memory"
    # gets the CPU-OOM bucket below.
    if ($text -match 'Cannot load nvcuda|Cannot load libcuda|No NVENC capable devices|OpenEncodeSessionEx failed|Driver does not support the required nvenc API|No capable devices found|InitializeEncoder failed|NV_ENC_ERR') {
        return 'ENCODE_NVENC_FAILED'
    }
    if ($text -match 'x265 \[error\]|x265: assertion|x265 \[fatal\]') {
        return 'ENCODE_CPU_X265_INTERNAL'
    }
    if ($text -match 'Cannot allocate memory|out of memory') {
        if ($isCpuEncode) { return 'ENCODE_CPU_OOM' }
        return 'SYSTEM_OUT_OF_MEMORY'
    }
    if ($text -match 'Unknown encoder|Encoder .* not found|codec .* not found') { return 'ENCODER_UNAVAILABLE' }
    if ($text -match 'Decoder .* not found|unsupported codec|Could not find codec parameters|Could not open codec') {
        return 'SOURCE_MEDIA_STREAM_UNSUPPORTED'
    }
    if ($isRemux -and
        $text -match 'Could not write header' -and
        $text -match ([regex]::Escape((Get-MediaContainerMuxerMatroskaName))) -and
        $text -match 'Invalid data found when processing input') {
        if ($text -match 'Video:\s*hevc|HEVC|H\.265') {
            return 'REMUX_HEVC_MKV_BITSTREAM_FAILED'
        }
        if ($text -match 'attached pic|Video:\s*mjpeg') {
            return 'REMUX_ATTACHED_PICTURE_MAPPED'
        }
        return 'REMUX_MKV_HEADER_WRITE_FAILED'
    }
    if ($ffprobeCode -eq 'MEDIA_CONTAINER_INVALID') { return 'SOURCE_MEDIA_CONTAINER_INVALID' }
    if ($text -match 'partial file|truncat|End of file|Packet corrupt') { return 'SOURCE_MEDIA_TRUNCATED' }
    if ($text -match 'error while decoding|Invalid NAL unit|corrupt decoded frame|concealing .* errors|Invalid data found when processing input') {
        return 'SOURCE_MEDIA_DECODE_FAILED'
    }
    if ($text -match 'Non-monotonous DTS|Application provided invalid|timestamp|Invalid DTS') { return 'MEDIA_TIMESTAMP_ERROR' }
    if ($ffprobeCode -eq 'FILE_MISSING') { return 'SOURCE_FILE_MISSING' }
    if ($text -match 'Invalid argument') { return 'FFMPEG_INVALID_ARGUMENT' }

    if ($isCpuEncode) { return 'ENCODE_CPU_FFMPEG_FAILED' }
    if ($isEncode) { return 'ENCODE_FFMPEG_FAILED' }
    if ($isRemux) { return 'REMUX_FFMPEG_FAILED' }
    return 'FFMPEG_FAILED'
}

function Get-MkvmergeFailureCode {
    param(
        [string]$ErrorText,
        [int]$ExitCode = 1,
        [bool]$TimedOut = $false,
        [bool]$Stopped = $false
    )

    $text = if ($ErrorText) { $ErrorText } else { "" }
    $ffprobeCode = Get-FFprobeFailureCode -ErrorText $text
    if ($TimedOut -or $text -match '\[KILLED:\s*TIMEOUT|timed out|timeout after') { return 'MKVMERGE_TIMEOUT' }
    if ($Stopped -or $text -match '\[KILLED:\s*STOP|stop requested') { return 'MKVMERGE_STOPPED' }
    if ($text -match 'No space left on device|not enough space|disk full') { return 'OUTPUT_DISK_FULL' }
    if ($text -match 'Permission denied|Access is denied|UnauthorizedAccess') { return 'MEDIA_ACCESS_DENIED' }
    if ($ffprobeCode -eq 'FILE_MISSING' -or $text -match 'could not be opened for reading|cannot open file') { return 'SOURCE_FILE_MISSING' }
    if ($ffprobeCode -eq 'MEDIA_CONTAINER_INVALID' -or $text -match 'EBML|not a Matroska file|No segment') { return 'MKVMERGE_INPUT_INVALID' }
    if ($text -match 'Invalid argument') { return 'MKVMERGE_INVALID_ARGUMENT' }
    return 'REMUX_MKVMERGE_FAILED'
}

# When ffmpeg fails mid-encode, we want to distinguish NVENC-specific
# problems (session init, driver OOM, concurrent-session limits, etc.)
# from generic failures that libx265 won't fix either. Only NVENC-specific
# failures trigger a libx265 fallback.
function Test-IsNvencError {
    param([string]$ErrorText)
    if ([string]::IsNullOrEmpty($ErrorText)) { return $false }
    $patterns = @(
        'No NVENC capable devices found',
        'Cannot load nvcuda\.dll|Cannot load libcuda',
        'OpenEncodeSessionEx failed',
        'Driver does not support the required nvenc API',
        'No capable devices found',
        'out of memory',
        'InitializeEncoder failed',
        'Generic error in an external library',
        'Provided device doesn''t support',
        'CUDA_ERROR_',
        'EncodePicture failed'
    )
    foreach ($p in $patterns) {
        if ($ErrorText -match $p) { return $true }
    }
    return $false
}
