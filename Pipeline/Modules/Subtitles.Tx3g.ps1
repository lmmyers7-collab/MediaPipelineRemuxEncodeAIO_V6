# ==============================================================================
# Modules\Subtitles.Tx3g.ps1
# ==============================================================================
# MP4 Timed Text / tx3g detection, extraction, naming, and sidecar publishing.
# Dot-sourced by Modules\Subtitles.ps1; preserves script-scope configuration.
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

function Test-IsTx3gSubtitleStream {
    param($Stream)

    if (-not $Stream) { return $false }
    $codec = if ($Stream.codec_name) { ([string]$Stream.codec_name).Trim().ToLowerInvariant() } else { "" }
    $tag   = if ($Stream.codec_tag_string) { ([string]$Stream.codec_tag_string).Trim().ToLowerInvariant() } else { "" }
    $codecTag = if ($Stream.codec_tag) { ([string]$Stream.codec_tag).Trim().ToLowerInvariant() } else { "" }
    $long  = if ($Stream.codec_long_name) { ([string]$Stream.codec_long_name).Trim().ToLowerInvariant() } else { "" }

    if ($codec -eq (Get-MediaSubtitleCodecMovTextName)) { return $true }
    if ($tag -in @('tx3g', 'text', 'sbtl')) { return $true }
    if ($codecTag -in @('0x67337874', '0x74786574', '0x6c746273')) { return $true }
    if ($long -match 'mp4 timed text|timed text') { return $true }
    return $false
}

function Test-CanPreserveTx3gInFfmpegOutput {
    $container = Get-ConfiguredOutputContainerName
    return ($container -in (Get-MediaContainerMp4FamilyNames))
}

function New-Tx3gFailureRecord {
    param(
        [hashtable]$Entry,
        [string]$Reason,
        [string]$ErrorCode = 'SUBTITLE_TX3G_EXTRACT_FAILED',
        [string]$ReproPath = $null,
        [string]$ErrorText = $null
    )

    $streamIndex = if ($Entry -and $Entry.Stream) { [int]$Entry.Stream.index } else { -1 }
    $operation = if ($ErrorCode -match 'PUBLISH') { 'subtitle-tx3g-publish' } else { 'subtitle-tx3g-extract' }
    $category = if ($ErrorCode -match 'PUBLISH') { 'publish' } else { 'subtitle_conversion' }
    return New-StandardFailureRecord -Stage $operation -Operation $operation -Category $category -Reason $Reason -ErrorCode $ErrorCode -Tool 'ffmpeg' -ReproPath $ReproPath -Retryable $true -AdditionalProperties @{
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

function Convert-Tx3gToSrt {
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

    $tempSrt = New-SrtAtomicTempPath -DestinationPath $DestinationPath
    $subtitleProgressSteps = @('extract','convert','validate','sidecar_write')
    $ffArgs = @(
        "-v", "error",
        "-y",
        "-i", $SourceFile,
        "-map", "0:$StreamIndex",
        "-c:s", "srt",
        "-f", "srt",
        $tempSrt
    )

    try {
        Write-Log "${Context}TX3G->SRT: extracting stream $StreamIndex to $(Split-Path -Leaf $DestinationPath)" "DEBUG"
        Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $StreamIndex -Stage 'extract' -Status 'Extracting TX3G subtitle' -StepIndex 1 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($SourceFile))
        $timeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleExtractTimeoutSeconds' -DefaultSeconds 180
        Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $StreamIndex -Stage 'convert' -Status 'Converting TX3G subtitle to SRT' -StepIndex 2 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($DestinationPath))
        $result = Invoke-FFmpegCommand -ArgumentList $ffArgs -TimeoutSeconds $timeoutSeconds -Stage 'subtitle-tx3g-extract' -SaveReproOnFailure
        if ($result.ExitCode -ne 0) {
            $summary = if (Get-Command -Name Get-ErrorTextSummary -ErrorAction SilentlyContinue) {
                Get-ErrorTextSummary -ErrorText $result.Error
            } else {
                ([string]$result.Error)
            }
            $reproPath = $result.ReproPath
            $code = if ($result.TimedOut) {
                'SUBTITLE_TX3G_EXTRACT_TIMEOUT'
            } elseif ($result.Stopped) {
                'SUBTITLE_TX3G_EXTRACT_STOPPED'
            } else {
                'SUBTITLE_TX3G_EXTRACT_FAILED'
            }
            if ([string]::IsNullOrWhiteSpace($summary)) { $summary = "ffmpeg exited with code $($result.ExitCode)" }
            Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $StreamIndex -Stage 'convert' -Status 'TX3G subtitle conversion failed' -StepIndex 2 -StepTotal 4 -Steps $subtitleProgressSteps -Detail $summary -Failed
            Write-Log "${Context}TX3G->SRT: extraction failed for stream $StreamIndex`: $summary" "WARN"
            return [pscustomobject]@{
                Ok        = $false
                Path      = $null
                CueCount  = 0
                Reason    = $summary
                ErrorCode = $code
                ReproPath = $reproPath
                ErrorText = $result.Error
                Failure   = (New-Tx3gFailureRecord -Entry $StreamInfo -Reason $summary -ErrorCode $code -ReproPath $reproPath -ErrorText $result.Error)
            }
        }

        Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $StreamIndex -Stage 'validate' -Status 'Validating TX3G subtitle SRT' -StepIndex 3 -StepTotal 4 -Steps $subtitleProgressSteps -Detail ([System.IO.Path]::GetFileName($tempSrt))
        $validation = Complete-AtomicSrtWrite -TempPath $tempSrt -DestinationPath $DestinationPath
        Write-Log "${Context}TX3G->SRT: stream $StreamIndex -> $($validation.CueCount) cue(s)" "DEBUG"
        Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $StreamIndex -Stage 'validate' -Status 'TX3G subtitle SRT validated' -StepIndex 3 -StepTotal 4 -Steps $subtitleProgressSteps -Detail "$($validation.CueCount) cue(s)" -CueCount $validation.CueCount
        return [pscustomobject]@{
            Ok        = $true
            Path      = $DestinationPath
            CueCount  = $validation.CueCount
            Reason    = 'ok'
            ErrorCode = 'OK'
            ReproPath = $null
            ErrorText = $null
            Failure   = $null
        }
    } catch {
        $message = $_.Exception.Message
        $code = if ($message -match 'empty|blank') { 'SUBTITLE_TX3G_SRT_EMPTY' } else { 'SUBTITLE_TX3G_SRT_INVALID' }
        Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $StreamIndex -Stage 'validate' -Status 'TX3G subtitle validation failed' -StepIndex 3 -StepTotal 4 -Steps $subtitleProgressSteps -Detail $message -Failed
        Write-Log "${Context}TX3G->SRT: validation/write failed for stream $StreamIndex`: $message" "WARN"
        return [pscustomobject]@{
            Ok        = $false
            Path      = $null
            CueCount  = 0
            Reason    = $message
            ErrorCode = $code
            ReproPath = $null
            ErrorText = $message
            Failure   = (New-Tx3gFailureRecord -Entry $StreamInfo -Reason $message -ErrorCode $code -ErrorText $message)
        }
    } finally {
        if ($tempSrt -and (Test-Path -LiteralPath $tempSrt -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tempSrt -Force -ErrorAction SilentlyContinue
        }
    }
}

function Resolve-Tx3gSrtDestination {
    param(
        [Parameter(Mandatory)] [string]$MediaOutputPath,
        [Parameter(Mandatory)] [hashtable]$Entry,
        [hashtable]$UsedPaths = @{}
    )

    $mediaDir = Split-Path -Parent $MediaOutputPath
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($MediaOutputPath)
    $lang = Get-NormalizedSubtitleLanguage $Entry.Lang
    $titleSlug = Get-SafeSubtitleFileToken -Value $Entry.RawTitle
    if ($titleSlug -in @('english','undefined','und',$lang)) { $titleSlug = "" }

    $components = [System.Collections.Generic.List[string]]::new()
    $components.Add((Get-SafeSubtitleFileToken -Value $lang -MaxLength 12))
    if ($script:Tx3gTreatForcedAsSeparate -and $Entry.IsForced) { $components.Add('forced') }
    if ($Entry.IsSdh) { $components.Add('sdh') }
    if (-not [string]::IsNullOrWhiteSpace($titleSlug)) { $components.Add($titleSlug) }
    $components.Add('tx3g')

    $primary = Join-Path $mediaDir ("{0}.{1}.srt" -f $baseName, ($components -join '.'))

    $generic = $null
    $genericComponents = [System.Collections.Generic.List[string]]::new()
    $genericComponents.Add((Get-SafeSubtitleFileToken -Value $lang -MaxLength 12))
    if ($script:Tx3gTreatForcedAsSeparate -and $Entry.IsForced) { $genericComponents.Add('forced') }
    $generic = Join-Path $mediaDir ("{0}.{1}.srt" -f $baseName, ($genericComponents -join '.'))

    $preserveExisting = $script:Tx3gPreserveExistingSrt -and -not $script:ReprocessAll
    if ($preserveExisting) {
        foreach ($candidate in @($primary, $generic)) {
            if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
            $key = $candidate.ToLowerInvariant()
            if ($UsedPaths.ContainsKey($key)) { continue }
            $validation = Test-SrtFileUsable -Path $candidate
            if ($validation.Ok) {
                $UsedPaths[$key] = $true
                return [pscustomobject]@{
                    Path             = $candidate
                    Status           = 'existing'
                    CueCount         = $validation.CueCount
                    PreserveExisting = $true
                    Reason           = 'existing usable SRT preserved'
                }
            }
        }
    }

    $candidatePath = $primary
    $suffix = 0
    while ($true) {
        $key = $candidatePath.ToLowerInvariant()
        $exists = Test-Path -LiteralPath $candidatePath -ErrorAction SilentlyContinue
        if (-not $UsedPaths.ContainsKey($key) -and (-not $exists -or -not $preserveExisting)) {
            $UsedPaths[$key] = $true
            return [pscustomobject]@{
                Path             = $candidatePath
                Status           = 'write'
                CueCount         = 0
                PreserveExisting = $false
                Reason           = ''
            }
        }

        $suffix++
        $streamSuffix = if ($suffix -eq 1) { "s$($Entry.Stream.index)" } else { "s$($Entry.Stream.index)-$suffix" }
        $candidatePath = Join-Path $mediaDir ("{0}.{1}.{2}.srt" -f $baseName, ($components -join '.'), $streamSuffix)
    }
}

function New-Tx3gSrtRecord {
    param(
        [hashtable]$Entry,
        [string]$Path,
        [string]$Status,
        [int]$CueCount,
        [bool]$PreservedExisting = $false
    )

    return [pscustomobject]@{
        path               = $Path
        file_name          = if ($Path) { Split-Path -Leaf $Path } else { '' }
        status             = $Status
        cue_count          = $CueCount
        preserved_existing = $PreservedExisting
        source_stream_index = if ($Entry.Stream) { [int]$Entry.Stream.index } else { -1 }
        subtitle_ordinal   = if ($Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        language           = if ($Entry.ContainsKey('Lang')) { $Entry.Lang } else { 'und' }
        title              = if ($Entry.ContainsKey('Title')) { $Entry.Title } else { '' }
        raw_title          = if ($Entry.ContainsKey('RawTitle')) { $Entry.RawTitle } else { '' }
        codec              = if ($Entry.ContainsKey('Codec')) { $Entry.Codec } else { Get-MediaSubtitleCodecMovTextName }
        codec_tag_string   = if ($Entry.ContainsKey('CodecTagString')) { $Entry.CodecTagString } else { '' }
        source_is_default  = if ($Entry.ContainsKey('SourceIsDefault')) { [bool]$Entry.SourceIsDefault } else { $false }
        is_default         = if ($Entry.ContainsKey('IsDefault')) { [bool]$Entry.IsDefault } else { $false }
        is_forced          = if ($Entry.ContainsKey('IsForced')) { [bool]$Entry.IsForced } else { $false }
        is_sdh             = if ($Entry.ContainsKey('IsSdh')) { [bool]$Entry.IsSdh } else { $false }
        is_supplemental    = if ($Entry.ContainsKey('IsSupplemental')) { [bool]$Entry.IsSupplemental } else { $false }
        supplemental_forced = if ($Entry.ContainsKey('SupplementalForced')) { [bool]$Entry.SupplementalForced } else { $false }
    }
}

function ConvertTo-Tx3gEmbeddedSrtTrackRecords {
    param([array] $Tx3gTracks)

    $records = [System.Collections.Generic.List[object]]::new()
    foreach ($track in @($Tx3gTracks)) {
        if (-not $track) { continue }
        $entry = if ($track.StreamInfo) { $track.StreamInfo } else { $track }
        if (-not $entry) { continue }

        $records.Add([pscustomobject]@{
            source_stream_index     = if ($entry.Stream) { [int]$entry.Stream.index } else { -1 }
            subtitle_ordinal        = if ($entry.ContainsKey('SubtitleOrdinal')) { $entry.SubtitleOrdinal } else { $null }
            language                = if ($entry.ContainsKey('Lang')) { $entry.Lang } else { 'und' }
            title                   = if ($entry.ContainsKey('Title')) { $entry.Title } else { '' }
            raw_title               = if ($entry.ContainsKey('RawTitle')) { $entry.RawTitle } else { '' }
            cue_count               = if ($track.CueCount) { [int]$track.CueCount } else { 0 }
            is_default              = if ($entry.ContainsKey('IsDefault')) { [bool]$entry.IsDefault } else { $false }
            is_forced               = if ($entry.ContainsKey('IsForced')) { [bool]$entry.IsForced } else { $false }
            is_sdh                  = if ($entry.ContainsKey('IsSdh')) { [bool]$entry.IsSdh } else { $false }
            is_supplemental         = if ($entry.ContainsKey('IsSupplemental')) { [bool]$entry.IsSupplemental } else { $false }
            supplemental_forced     = if ($entry.ContainsKey('SupplementalForced')) { [bool]$entry.SupplementalForced } else { $false }
            original_preserved      = if ($track.ContainsKey('OriginalPreserved')) { [bool]$track.OriginalPreserved } else { $false }
            original_preserve_reason = if ($track.ContainsKey('OriginalPreserveReason')) { [string]$track.OriginalPreserveReason } else { '' }
        })
    }

    return @($records)
}

function New-Tx3gSrtSidecarPublishPlan {
    param(
        [array]$Tx3gTracks,
        [Parameter(Mandatory)] [string]$MediaOutputPath,
        [string]$Context = ""
    )

    $records = [System.Collections.Generic.List[object]]::new()
    $failures = [System.Collections.Generic.List[object]]::new()
    $sidecarFiles = [System.Collections.Generic.List[object]]::new()

    if (-not (Get-EffectiveSubtitleSwitch -Name 'CreateExternalTx3gSrtSidecars' -Default $false)) {
        return @{
            Tracks       = @($records)
            Failures     = @($failures)
            SidecarFiles = @($sidecarFiles)
        }
    }

    $used = @{}

    foreach ($track in @($Tx3gTracks)) {
        if (-not $track) { continue }
        $entry = if ($track.StreamInfo) { $track.StreamInfo } else { $track }
        $resolved = Resolve-Tx3gSrtDestination -MediaOutputPath $MediaOutputPath -Entry $entry -UsedPaths $used
        if ($resolved.Status -eq 'existing') {
            $records.Add((New-Tx3gSrtRecord -Entry $entry -Path $resolved.Path -Status 'existing' -CueCount $resolved.CueCount -PreservedExisting:$true))
            continue
        }

        $sourceSrt = if ($track.SrtPath) { [string]$track.SrtPath } else { "" }
        $validation = Test-SrtFileUsable -Path $sourceSrt
        if (-not $validation.Ok) {
            $failure = New-Tx3gFailureRecord -Entry $entry -Reason "source SRT is not usable: $($validation.Reason)" -ErrorCode 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED'
            $failures.Add($failure)
            Write-Log "${Context}TX3G->SRT: cannot queue sidecar for stream $($failure.StreamIndex): $($failure.Reason)" "WARN"
            continue
        }

        $record = New-Tx3gSrtRecord -Entry $entry -Path $resolved.Path -Status 'pending' -CueCount $validation.CueCount
        $records.Add($record)
        $sidecarFiles.Add([pscustomobject]@{
            Kind            = 'tx3g_srt'
            LocalPath       = $sourceSrt
            DestinationPath = $resolved.Path
            Record          = $record
            PreserveExisting = [bool]($script:Tx3gPreserveExistingSrt -and -not $script:ReprocessAll)
        })
    }

    return @{
        Tracks       = @($records)
        Failures     = @($failures)
        SidecarFiles = @($sidecarFiles)
    }
}

function Publish-Tx3gSrtSidecars {
    param(
        [array]$Tx3gTracks,
        [Parameter(Mandatory)] [string]$MediaOutputPath,
        [string]$Context = ""
    )

    $records = [System.Collections.Generic.List[object]]::new()
    $failures = [System.Collections.Generic.List[object]]::new()
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

    if (-not (Get-EffectiveSubtitleSwitch -Name 'CreateExternalTx3gSrtSidecars' -Default $false)) {
        return @{
            Tracks   = @($records)
            Failures = @($failures)
        }
    }

    $used = @{}

    foreach ($track in @($Tx3gTracks)) {
        if (-not $track) { continue }
        $entry = if ($track.StreamInfo) { $track.StreamInfo } else { $track }
        $resolved = Resolve-Tx3gSrtDestination -MediaOutputPath $MediaOutputPath -Entry $entry -UsedPaths $used
        if ($resolved.Status -eq 'existing') {
            Write-Log "${Context}TX3G->SRT: preserving existing sidecar $(Split-Path -Leaf $resolved.Path)" "DEBUG"
            $records.Add((New-Tx3gSrtRecord -Entry $entry -Path $resolved.Path -Status 'existing' -CueCount $resolved.CueCount -PreservedExisting:$true))
            continue
        }

        $sourceSrt = if ($track.SrtPath) { [string]$track.SrtPath } else { "" }
        $streamIndex = if ($entry.Stream -and $null -ne $entry.Stream.index) { [int]$entry.Stream.index } else { -1 }
        Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'Writing TX3G SRT sidecar' -StepIndex 4 -StepTotal 4 -Detail (Split-Path -Leaf $resolved.Path)
        $copy = Copy-SrtAtomic -SourcePath $sourceSrt -DestinationPath $resolved.Path
        if (-not $copy.Ok) {
            $failure = New-Tx3gFailureRecord -Entry $entry -Reason $copy.Reason -ErrorCode $copy.ErrorCode
            $failures.Add($failure)
            Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'TX3G SRT sidecar write failed' -StepIndex 4 -StepTotal 4 -Detail $copy.Reason -Failed
            Write-Log "${Context}TX3G->SRT: sidecar publish failed for stream $($failure.StreamIndex): $($copy.Reason)" "WARN"
            continue
        }

        Write-Log "${Context}TX3G->SRT: sidecar written $(Split-Path -Leaf $resolved.Path)"
        Write-SubtitleTrackProgress -Kind 'tx3g' -StreamIndex $streamIndex -Stage 'sidecar_write' -Status 'TX3G SRT sidecar written' -StepIndex 4 -StepTotal 4 -Detail (Split-Path -Leaf $resolved.Path) -CueCount $copy.CueCount -Completed
        $records.Add((New-Tx3gSrtRecord -Entry $entry -Path $resolved.Path -Status 'written' -CueCount $copy.CueCount))
    }

    return @{
        Tracks   = @($records)
        Failures = @($failures)
    }
}

function Export-Tx3gSrtSidecarsFromSource {
    param(
        $FilterResult,
        [Parameter(Mandatory)] [string]$SourceFile,
        [Parameter(Mandatory)] [string]$MediaOutputPath,
        [string]$Context = ""
    )

    $records = [System.Collections.Generic.List[object]]::new()
    $failures = [System.Collections.Generic.List[object]]::new()

    if (-not (Get-EffectiveSubtitleSwitch -Name 'CreateExternalTx3gSrtSidecars' -Default $false)) {
        return @{
            Tracks   = @($records)
            Failures = @($failures)
        }
    }

    $used = @{}

    foreach ($entry in @($FilterResult.Tx3gConvert)) {
        $resolved = Resolve-Tx3gSrtDestination -MediaOutputPath $MediaOutputPath -Entry $entry -UsedPaths $used
        if ($resolved.Status -eq 'existing') {
            Write-Log "${Context}TX3G->SRT: existing sidecar already matches stream $($entry.Stream.index)" "DEBUG"
            $records.Add((New-Tx3gSrtRecord -Entry $entry -Path $resolved.Path -Status 'existing' -CueCount $resolved.CueCount -PreservedExisting:$true))
            continue
        }

        $extract = Convert-Tx3gToSrt -SourceFile $SourceFile -StreamIndex ([int]$entry.Stream.index) -StreamInfo $entry -DestinationPath $resolved.Path -Context $Context
        if (-not $extract.Ok) {
            if ($extract.Failure) {
                $failures.Add($extract.Failure)
            } else {
                $failures.Add((New-Tx3gFailureRecord -Entry $entry -Reason $extract.Reason -ErrorCode $extract.ErrorCode -ReproPath $extract.ReproPath -ErrorText $extract.ErrorText))
            }
            continue
        }

        $records.Add((New-Tx3gSrtRecord -Entry $entry -Path $extract.Path -Status 'written' -CueCount $extract.CueCount))
    }

    return @{
        Tracks   = @($records)
        Failures = @($failures)
    }
}
