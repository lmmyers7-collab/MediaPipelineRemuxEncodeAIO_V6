# ==============================================================================
# engine\subtitles\bdpgs.ps1
# ==============================================================================
# BDPGS/PGS detection, SUP extraction, OCR tool resolution, and OCR conversion.
# Dot-sourced by engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

if (-not (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue)) {
    function Write-SubtitleTrackProgress {
        param(
            [string]$Kind,
            [int]$StreamIndex = -1,
            [string]$Stage,
            [string]$Status,
            [int]$StepIndex = 0,
            [int]$StepTotal = 4,
            [array]$Steps = @(),
            [string]$Detail = "",
            [object]$CueCount = $null,
            [switch]$Completed,
            [switch]$Failed
        )
    }
}

function Test-IsBdpgsSubtitleStream {
    param($Stream)

    if (-not $Stream) { return $false }
    $codec = if ($Stream.codec_name) { ([string]$Stream.codec_name).ToLowerInvariant() } else { "" }
    $tag   = if ($Stream.codec_tag_string) { ([string]$Stream.codec_tag_string).ToLowerInvariant() } else { "" }
    $long  = if ($Stream.codec_long_name) { ([string]$Stream.codec_long_name).ToLowerInvariant() } else { "" }

    if ($codec -in (Get-MediaSubtitleCodecBdpgsNames)) { return $true }
    if ($tag -match 'pgs') { return $true }
    if ($long -match 'presentation\s+graphic|blu-?ray\s+pgs|hdmv\s+pgs') { return $true }
    return $false
}

function Test-CanPreserveBdpgsInFfmpegOutput {
    $container = Get-ConfiguredOutputContainerName
    return ($container -in (Get-MediaContainerMatroskaFamilyNames))
}

function Resolve-BdpgsOcrLanguage {
    param([string]$Language)

    $normalized = Get-NormalizedSubtitleLanguage $Language
    $map = @{
        'eng' = 'eng'; 'en' = 'eng'; 'und' = 'eng'; '' = 'eng'
        'jpn' = 'jpn'; 'ja' = 'jpn'
        'spa' = 'spa'; 'es' = 'spa'
        'fre' = 'fra'; 'fra' = 'fra'; 'fr' = 'fra'
        'ger' = 'deu'; 'deu' = 'deu'; 'de' = 'deu'
        'ita' = 'ita'; 'it' = 'ita'
        'por' = 'por'; 'pt' = 'por'
        'rus' = 'rus'; 'ru' = 'rus'
        'chi' = 'chi_sim'; 'zho' = 'chi_sim'; 'zh' = 'chi_sim'
        'kor' = 'kor'; 'ko' = 'kor'
    }
    if ($map.ContainsKey($normalized)) { return $map[$normalized] }
    return $normalized
}

function Resolve-BdpgsOcrToolInvocation {
    $toolPath = if ($script:BdpgsOcrToolPath) { ([string]$script:BdpgsOcrToolPath).Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($toolPath)) {
        return [pscustomobject]@{ Ok = $false; FilePath = ''; PrefixArgs = @(); Reason = 'BdpgsOcrToolPath is not configured' }
    }

    $resolved = $toolPath
    if (-not [System.IO.Path]::IsPathRooted($resolved)) {
        $baseDir = if ($scriptDir) { $scriptDir } elseif ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
        $candidate = Join-Path $baseDir $resolved
        if (Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue) {
            $resolved = (Resolve-Path -LiteralPath $candidate).Path
        } elseif ($script:AllowSystemTools) {
            $cmd = Get-Command $resolved -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($cmd -and $cmd.Source) { $resolved = $cmd.Source }
        }
    }

    if (-not (Test-Path -LiteralPath $resolved -ErrorAction SilentlyContinue) -and -not (Get-Command $resolved -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Ok = $false; FilePath = ''; PrefixArgs = @(); Reason = "BDPGS OCR tool not found: $toolPath" }
    }

    if ([System.IO.Path]::GetExtension($resolved).Equals('.dll', [System.StringComparison]::OrdinalIgnoreCase)) {
        $dotnet = Get-Command dotnet -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not ($dotnet -and $dotnet.Source)) {
            return [pscustomobject]@{ Ok = $false; FilePath = ''; PrefixArgs = @(); Reason = 'BdpgsOcrToolPath points to a .dll but dotnet was not found on PATH' }
        }
        return [pscustomobject]@{ Ok = $true; FilePath = $dotnet.Source; PrefixArgs = @($resolved); Reason = 'ok' }
    }

    return [pscustomobject]@{ Ok = $true; FilePath = $resolved; PrefixArgs = @(); Reason = 'ok' }
}

function Resolve-BdpgsOcrTessdataPath {
    $configured = if ($script:BdpgsOcrTessdataPath) { ([string]$script:BdpgsOcrTessdataPath).Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($configured)) {
        return [pscustomobject]@{ Ok = $true; Path = ''; Reason = 'not configured' }
    }

    $resolved = Resolve-SubtitleConfiguredPath -PathValue $configured
    if (Test-Path -LiteralPath $resolved -PathType Container -ErrorAction SilentlyContinue) {
        return [pscustomobject]@{ Ok = $true; Path = $resolved; Reason = 'ok' }
    }

    return [pscustomobject]@{
        Ok     = $false
        Path   = $resolved
        Reason = "BDPGS OCR tessdata path not found: $configured"
    }
}

function New-BdpgsFailureRecord {
    param(
        [hashtable]$Entry,
        [string]$Reason,
        [string]$ErrorCode = 'SUBTITLE_BDPGS_OCR_FAILED',
        [string]$ReproPath = $null,
        [string]$ErrorText = $null
    )

    $streamIndex = if ($Entry -and $Entry.Stream) { [int]$Entry.Stream.index } else { -1 }
    $category = if ($ErrorCode -match 'TOOL_MISSING|TESSDATA_MISSING') { 'tool_missing' } else { 'subtitle_conversion' }
    $operation = if ($ErrorCode -match 'SUP_') { 'subtitle-bdpgs-sup-extract' } else { 'subtitle-bdpgs-ocr' }
    return New-StandardFailureRecord -Stage $operation -Operation $operation -Category $category -Reason $Reason -ErrorCode $ErrorCode -Tool 'bdpgs-ocr' -ReproPath $ReproPath -Retryable $true -AdditionalProperties @{
        StreamIndex     = $streamIndex
        stream_index    = $streamIndex
        SubtitleOrdinal = if ($Entry -and $Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        subtitle_ordinal = if ($Entry -and $Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        Language        = if ($Entry -and $Entry.ContainsKey('Lang')) { $Entry.Lang } else { 'und' }
        Title           = if ($Entry -and $Entry.ContainsKey('Title')) { $Entry.Title } else { '' }
        SourceIsDefault = if ($Entry -and $Entry.ContainsKey('SourceIsDefault')) { [bool]$Entry.SourceIsDefault } else { $false }
        source_is_default = if ($Entry -and $Entry.ContainsKey('SourceIsDefault')) { [bool]$Entry.SourceIsDefault } else { $false }
        IsForced        = if ($Entry -and $Entry.ContainsKey('IsForced')) { [bool]$Entry.IsForced } else { $false }
        is_forced       = if ($Entry -and $Entry.ContainsKey('IsForced')) { [bool]$Entry.IsForced } else { $false }
        ErrorText       = $ErrorText
        error_text      = $ErrorText
    }
}

function ConvertTo-BdpgsEmbeddedSrtTrackRecords {
    param([array] $BdpgsTracks)

    $records = [System.Collections.Generic.List[object]]::new()
    foreach ($track in @($BdpgsTracks)) {
        if (-not $track) { continue }
        $entry = if ($track.StreamInfo) { $track.StreamInfo } else { $track }
        if (-not $entry) { continue }

        $records.Add([pscustomobject]@{
            source_stream_index      = if ($entry.Stream) { [int]$entry.Stream.index } else { -1 }
            subtitle_ordinal         = if ($entry.ContainsKey('SubtitleOrdinal')) { $entry.SubtitleOrdinal } else { $null }
            language                 = if ($entry.ContainsKey('Lang')) { $entry.Lang } else { 'und' }
            title                    = if ($entry.ContainsKey('Title')) { $entry.Title } else { '' }
            raw_title                = if ($entry.ContainsKey('RawTitle')) { $entry.RawTitle } else { '' }
            cue_count                = if ($track.CueCount) { [int]$track.CueCount } else { 0 }
            is_default               = if ($entry.ContainsKey('IsDefault')) { [bool]$entry.IsDefault } else { $false }
            is_forced                = if ($entry.ContainsKey('IsForced')) { [bool]$entry.IsForced } else { $false }
            is_sdh                   = if ($entry.ContainsKey('IsSdh')) { [bool]$entry.IsSdh } else { $false }
            is_supplemental          = if ($entry.ContainsKey('IsSupplemental')) { [bool]$entry.IsSupplemental } else { $false }
            supplemental_forced      = if ($entry.ContainsKey('SupplementalForced')) { [bool]$entry.SupplementalForced } else { $false }
            original_preserved       = if ($track.ContainsKey('OriginalPreserved')) { [bool]$track.OriginalPreserved } else { $false }
            original_preserve_reason = if ($track.ContainsKey('OriginalPreserveReason')) { [string]$track.OriginalPreserveReason } else { '' }
        })
    }

    return @($records)
}

function Extract-BdpgsToSup {
    param(
        [Parameter(Mandatory)] [string]$SourceFile,
        [Parameter(Mandatory)] [int]$StreamIndex,
        [Parameter(Mandatory)] [string]$DestinationPath,
        [hashtable]$StreamInfo = @{},
        [string]$Context = ""
    )

    if (-not (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue)) {
        function Write-SubtitleTrackProgress {
            param(
                [string]$Kind,
                [int]$StreamIndex = -1,
                [string]$Stage,
                [string]$Status,
                [int]$StepIndex = 0,
                [int]$StepTotal = 4,
                [array]$Steps = @(),
                [string]$Detail = "",
                [object]$CueCount = $null,
                [switch]$Completed,
                [switch]$Failed
            )
        }
    }

    $ffArgs = @(
        "-v", "error",
        "-y",
        "-i", $SourceFile,
        "-map", "0:$StreamIndex",
        "-c:s", "copy",
        "-f", "sup",
        $DestinationPath
    )

    try {
        $subtitleProgressSteps = @('extract','convert_ocr','validate','sidecar_write')
        Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'extract' -Status 'Extracting BDPGS subtitle SUP' -StepIndex 1 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($SourceFile))
        $timeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleExtractTimeoutSeconds' -DefaultSeconds 180
        $result = Invoke-FFmpegCommand -ArgumentList $ffArgs -TimeoutSeconds $timeoutSeconds -Stage 'subtitle-bdpgs-sup-extract' -SaveReproOnFailure
        if ($result.ExitCode -ne 0) {
            $reproPath = $result.ReproPath
            $reason = if ($result.Error) { Get-ErrorTextSummary -ErrorText $result.Error } else { "ffmpeg exited $($result.ExitCode)" }
            Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'extract' -Status 'BDPGS subtitle extraction failed' -StepIndex 1 -StepTotal 4 -Steps $subtitleProgressSteps -Detail $reason -Failed
            return [pscustomobject]@{
                Ok = $false; Path = $null; Reason = $reason
                Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_SUP_EXTRACT_FAILED' -ReproPath $reproPath -ErrorText $result.Error)
            }
        }
        if (-not (Test-Path -LiteralPath $DestinationPath -ErrorAction SilentlyContinue) -or (Get-Item -LiteralPath $DestinationPath).Length -le 0) {
            $reason = 'BDPGS SUP extraction produced no output'
            Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'extract' -Status 'BDPGS subtitle extraction failed' -StepIndex 1 -StepTotal 4 -Steps $subtitleProgressSteps -Detail $reason -Failed
            return [pscustomobject]@{
                Ok = $false; Path = $null; Reason = $reason
                Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_SUP_EMPTY')
            }
        }
        Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'extract' -Status 'BDPGS subtitle SUP extracted' -StepIndex 1 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($DestinationPath))
        return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; Reason = 'ok'; Failure = $null }
    } catch {
        $reason = "BDPGS SUP extraction error: $($_.Exception.Message)"
        Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'extract' -Status 'BDPGS subtitle extraction failed' -StepIndex 1 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
        return [pscustomobject]@{
            Ok = $false; Path = $null; Reason = $reason
            Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_SUP_EXTRACT_EXCEPTION')
        }
    }
}

function Convert-BdpgsToSrt {
    param(
        [Parameter(Mandatory)] [string]$SourceFile,
        [Parameter(Mandatory)] [int]$StreamIndex,
        [hashtable]$StreamInfo = @{},
        [Parameter(Mandatory)] [string]$DestinationPath,
        [string]$Context = ""
    )

    if (-not (Get-Command -Name Write-SubtitleTrackProgress -ErrorAction SilentlyContinue)) {
        function Write-SubtitleTrackProgress {
            param(
                [string]$Kind,
                [int]$StreamIndex = -1,
                [string]$Stage,
                [string]$Status,
                [int]$StepIndex = 0,
                [int]$StepTotal = 4,
                [array]$Steps = @(),
                [string]$Detail = "",
                [object]$CueCount = $null,
                [switch]$Completed,
                [switch]$Failed
            )
        }
    }

    $supPath = Join-Path $script:processingDir "sub_bdpgs_$([guid]::NewGuid().ToString('N')).sup"
    $ocrTempSrt = $null
    try {
        $sup = Extract-BdpgsToSup -SourceFile $SourceFile -StreamIndex $StreamIndex -DestinationPath $supPath -StreamInfo $StreamInfo -Context $Context
        if (-not $sup.Ok) { return $sup }

        $tool = Resolve-BdpgsOcrToolInvocation
        if (-not $tool.Ok) {
            Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'BDPGS OCR setup failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $tool.Reason -Failed
            return [pscustomobject]@{
                Ok = $false; Path = $null; CueCount = 0; Reason = $tool.Reason
                Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $tool.Reason -ErrorCode 'SUBTITLE_BDPGS_OCR_TOOL_MISSING')
            }
        }

        $ocrLanguage = Resolve-BdpgsOcrLanguage -Language $StreamInfo.Lang
        $tessdata = Resolve-BdpgsOcrTessdataPath
        if (-not $tessdata.Ok) {
            Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'BDPGS OCR setup failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $tessdata.Reason -Failed
            return [pscustomobject]@{
                Ok = $false; Path = $null; CueCount = 0; Reason = $tessdata.Reason
                Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $tessdata.Reason -ErrorCode 'SUBTITLE_BDPGS_TESSDATA_MISSING')
            }
        }

        $ocrTempSrt = New-SrtAtomicTempPath -DestinationPath $DestinationPath
        $ocrArgs = [System.Collections.Generic.List[string]]::new()
        $ocrArgs.AddRange([string[]]@($tool.PrefixArgs))
        $ocrArgs.AddRange([string[]]@("--input", $sup.Path, "--output", $ocrTempSrt, "--tesseractlanguage", $ocrLanguage))
        if (-not [string]::IsNullOrWhiteSpace([string]$tessdata.Path)) {
            $ocrArgs.AddRange([string[]]@("--tesseractdata", [string]$tessdata.Path))
        }

        try {
            $timeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'BdpgsOcrTimeoutSeconds' -DefaultSeconds 1800
            # CPU-A4 — BDPGS OCR is CPU-heavy (Tesseract image OCR per
            # subtitle frame). Run it at the configured CPU encode
            # priority and hold the machine-wide CPU mutex so it doesn't
            # race with concurrent libx265 fallback / audio-transcode-
            # active remuxes. Mutex is best-effort; if creation fails we
            # log and continue rather than block OCR forever.
            $ocrPriority = if (Get-Variable -Name CpuEncodeProcessPriority -Scope Script -ErrorAction SilentlyContinue) {
                [string]$script:CpuEncodeProcessPriority
            } else { 'belownormal' }
            $ocrCpuLock = $null
            if (Get-Command -Name Acquire-CpuEncodeMutex -ErrorAction SilentlyContinue) {
                $ocrCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
                if (-not $ocrCpuLock.Acquired) {
                    Write-Log "${Context}BDPGS OCR: another CPU-bound job is running; waiting for slot ($($ocrCpuLock.Reason))" "WARN"
                    $ocrCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds $timeoutSeconds
                }
            }
            try {
                Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'Running BDPGS OCR' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail ([System.IO.Path]::GetFileName($sup.Path))
                $result = Invoke-BdpgsOcrCommand -FilePath $tool.FilePath -ArgumentList @($ocrArgs.ToArray()) -TimeoutSeconds $timeoutSeconds -Stage 'subtitle-bdpgs-ocr' -SaveReproOnFailure -ProcessPriority $ocrPriority
            } finally {
                if ($ocrCpuLock -and $ocrCpuLock.Acquired) { & $ocrCpuLock.Release }
            }
            if ($result.ExitCode -ne 0) {
                $reproPath = $result.ReproPath
                $reason = if ($result.Error) { Get-ErrorTextSummary -ErrorText $result.Error } else { "OCR tool exited $($result.ExitCode)" }
                Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'BDPGS OCR failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
                return [pscustomobject]@{
                    Ok = $false; Path = $null; CueCount = 0; Reason = $reason
                    Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_OCR_FAILED' -ReproPath $reproPath -ErrorText $result.Error)
                }
            }

            Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'validate' -Status 'Validating BDPGS OCR SRT' -StepIndex 3 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail ([System.IO.Path]::GetFileName($ocrTempSrt))
            $preMoveValidation = Test-SrtFileUsable -Path $ocrTempSrt
            if (-not $preMoveValidation.Ok) {
                $reason = "BDPGS OCR SRT is not usable: $($preMoveValidation.Reason)"
                Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'validate' -Status 'BDPGS OCR validation failed' -StepIndex 3 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
                return [pscustomobject]@{
                    Ok = $false; Path = $null; CueCount = 0; Reason = $reason
                    Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_OCR_EMPTY')
                }
            }
            $validation = Complete-AtomicSrtWrite -TempPath $ocrTempSrt -DestinationPath $DestinationPath

            Write-Log "${Context}BDPGS->SRT: stream $StreamIndex -> $($validation.CueCount) cue(s)"
            Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'validate' -Status 'BDPGS OCR SRT validated' -StepIndex 3 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail "$($validation.CueCount) cue(s)" -CueCount $validation.CueCount
            return [pscustomobject]@{ Ok = $true; Path = $DestinationPath; CueCount = $validation.CueCount; Reason = 'ok'; Failure = $null }
        } catch {
            $reason = "BDPGS OCR error: $($_.Exception.Message)"
            Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'BDPGS OCR failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
            return [pscustomobject]@{
                Ok = $false; Path = $null; CueCount = 0; Reason = $reason
                Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_OCR_EXCEPTION')
            }
        }
    } catch {
        $reason = "BDPGS conversion error: $($_.Exception.Message)"
        Write-SubtitleTrackProgress -Kind 'bdpgs' -StreamIndex $StreamIndex -Stage 'convert_ocr' -Status 'BDPGS conversion failed' -StepIndex 2 -StepTotal 4 -Steps @('extract','convert_ocr','validate','sidecar_write') -Detail $reason -Failed
        return [pscustomobject]@{
            Ok = $false; Path = $null; CueCount = 0; Reason = $reason
            Failure = (New-BdpgsFailureRecord -Entry $StreamInfo -Reason $reason -ErrorCode 'SUBTITLE_BDPGS_OCR_EXCEPTION')
        }
    } finally {
        if ($supPath -and (Test-Path -LiteralPath $supPath -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $supPath -Force -ErrorAction SilentlyContinue
        }
        if ($ocrTempSrt -and (Test-Path -LiteralPath $ocrTempSrt -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $ocrTempSrt -Force -ErrorAction SilentlyContinue
        }
    }
}
