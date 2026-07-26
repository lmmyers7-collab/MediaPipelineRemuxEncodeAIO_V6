# ==============================================================================
# ops\pipeline\engine\subtitles\builders\decisions.ps1
# ==============================================================================
# Shared subtitle builder decision records used before conversion/OCR temp files
# are written and before FFmpeg/mkvmerge arguments are emitted.
# ==============================================================================

function Test-SubtitleBuilderPreferredDefaultCandidate {
    param([Parameter(Mandatory)] $Entry)

    if ([bool]$Entry.IsSupplemental) { return $false }
    return (Test-SubtitleEntryLanguageIsPreferredDefault -Entry $Entry)
}

function Test-SubtitleBuilderFallbackDefaultCandidate {
    param([Parameter(Mandatory)] $Entry)

    if ([bool]$Entry.IsSupplemental) { return $false }
    return (Test-SubtitleEntryLanguageIsFallbackDefault -Entry $Entry)
}

if (-not (Get-Command -Name Test-ConfiguredOutputContainerIsMp4 -ErrorAction SilentlyContinue)) {
    function Test-ConfiguredOutputContainerIsMp4 {
        $container = if (Get-Command -Name Get-ConfiguredOutputContainerName -ErrorAction SilentlyContinue) {
            (Get-ConfiguredOutputContainerName)
        } else {
            ''
        }
        $normalized = ([string]$container).Trim().TrimStart('.').ToLowerInvariant()
        if (Get-Command -Name Get-MediaContainerMp4FamilyNames -ErrorAction SilentlyContinue) {
            return ($normalized -in (Get-MediaContainerMp4FamilyNames))
        }
        return ($normalized -in @('mp4','m4v','mov'))
    }
}

function New-SubtitleBuilderTrackDecisionRecord {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('FFmpeg','Mkvmerge')]
        [string] $Builder,

        [Parameter(Mandatory)]
        [ValidateSet('Keep','Drop','Burn','ConvertAss','ConvertTx3g','ConvertBdpgs','ConvertVobSub')]
        [string] $Action,

        [Parameter(Mandatory)]
        $Entry,

        [bool] $PreserveOriginal = $false,
        [string] $OriginalPreserveReason = '',
        [string] $OriginalTitleSuffix = '',
        [bool] $RoutesToReview = $false,
        [string] $ReviewErrorCode = '',
        [string] $ReviewReason = '',
        [string] $ReviewFailureKind = '',
        [string] $ContainerLogMessage = '',
        [string] $ConversionKind = '',
        [string] $PolicyReason = ''
    )

    $sourceKind = ''
    if ($Entry -is [System.Collections.IDictionary] -and $Entry.Contains('SourceKind')) {
        $sourceKind = [string]$Entry['SourceKind']
    } elseif ($Entry.PSObject.Properties['SourceKind']) {
        $sourceKind = [string]$Entry.SourceKind
    }
    if ([string]::IsNullOrWhiteSpace($sourceKind)) { $sourceKind = 'embedded' }
    $sourceKind = $sourceKind.Trim().ToLowerInvariant()
    $trackId = ''
    if ($Entry -is [System.Collections.IDictionary] -and $Entry.Contains('TrackId')) {
        $trackId = [string]$Entry['TrackId']
    } elseif ($Entry.PSObject.Properties['TrackId']) {
        $trackId = [string]$Entry.TrackId
    }
    if ([string]::IsNullOrWhiteSpace($trackId)) {
        $sourceOrdinal = $null
        if ($Entry -is [System.Collections.IDictionary] -and $Entry.Contains('SubtitleOrdinal')) {
            $sourceOrdinal = $Entry['SubtitleOrdinal']
        } elseif ($Entry.PSObject.Properties['SubtitleOrdinal']) {
            $sourceOrdinal = $Entry.SubtitleOrdinal
        }
        if ($null -eq $sourceOrdinal -or [string]::IsNullOrWhiteSpace([string]$sourceOrdinal)) {
            $stream = if ($Entry -is [System.Collections.IDictionary] -and $Entry.Contains('Stream')) { $Entry['Stream'] } elseif ($Entry.PSObject.Properties['Stream']) { $Entry.Stream } else { $null }
            $streamIndex = if ($stream -and $null -ne $stream.PSObject.Properties['index']) { $stream.index } else { $null }
            if ($sourceKind -eq 'embedded' -and $null -ne $streamIndex -and [int]$streamIndex -ge 0) {
                $sourceOrdinal = "stream-$([int]$streamIndex)"
            } else {
                throw "SUBTITLE_TRACK_IDENTITY_MISSING: subtitle source kind '$sourceKind' has no backend source ordinal"
            }
        }
        $trackId = "subtitle:$sourceKind`:$sourceOrdinal"
    }
    if ($Entry -is [System.Collections.IDictionary]) {
        $Entry['TrackId'] = $trackId
    } elseif ($Entry.PSObject.Properties['TrackId']) {
        $Entry.TrackId = $trackId
    } else {
        $Entry | Add-Member -NotePropertyName TrackId -NotePropertyValue $trackId
    }
    $isConversion = $Action -in @('ConvertAss','ConvertTx3g','ConvertBdpgs','ConvertVobSub')
    $isOcr = $Action -in @('ConvertBdpgs','ConvertVobSub')
    $isDrop = $Action -eq 'Drop'
    $isBurn = $Action -eq 'Burn'
    $sourceType = if ($Action -in @('ConvertBdpgs','ConvertVobSub') -or [bool]$Entry.IsBdpgs -or [bool]$Entry.IsVobSub) { 'image' } elseif (-not [string]::IsNullOrWhiteSpace([string]$Entry.Codec)) { 'text' } else { 'unknown' }
    $mp4CompatibilityMode = ($Builder -eq 'FFmpeg' -and (Test-ConfiguredOutputContainerIsMp4))
    $writeEmbedded = (-not $RoutesToReview -and -not $isDrop -and -not $isBurn -and -not $mp4CompatibilityMode)
    $plannedAction = switch ($Action) {
        'Keep' { 'preserve' }
        'Drop' { 'drop' }
        'Burn' { 'burn_in' }
        'ConvertAss' { 'convert_ass_to_srt' }
        'ConvertTx3g' { 'convert_tx3g_to_srt' }
        'ConvertBdpgs' { 'ocr_bdpgs_to_srt' }
        'ConvertVobSub' { 'ocr_vobsub_to_srt' }
    }

    [pscustomobject]@{
        Builder                          = $Builder
        Action                           = $Action
        Entry                            = $Entry
        PreserveOriginal                 = [bool]$PreserveOriginal
        OriginalPreserveReason           = [string]$OriginalPreserveReason
        OriginalTitleSuffix              = [string]$OriginalTitleSuffix
        RoutesToReview                   = [bool]$RoutesToReview
        ReviewErrorCode                  = [string]$ReviewErrorCode
        ReviewReason                     = [string]$ReviewReason
        ReviewFailureKind                = [string]$ReviewFailureKind
        ContainerLogMessage              = [string]$ContainerLogMessage
        ConversionKind                   = [string]$ConversionKind
        TrackId                          = $trackId
        track_id                         = $trackId
        SourceType                       = $sourceType
        SourceKind                       = $sourceKind
        Extract                          = [bool]$isConversion
        Convert                          = [bool]$isConversion
        Ocr                              = [bool]$isOcr
        Drop                             = [bool]$isDrop
        WriteEmbedded                    = [bool]$writeEmbedded
        WriteSidecar                     = $false
        PlannedAction                    = $plannedAction
        PolicyReason                     = [string]$PolicyReason
        ConversionFailureRoutesToReview  = ($Action -in @('ConvertAss','ConvertTx3g','ConvertBdpgs','ConvertVobSub'))
        IsPreferredDefaultCandidate      = (Test-SubtitleBuilderPreferredDefaultCandidate -Entry $Entry)
        IsFallbackDefaultCandidate       = (Test-SubtitleBuilderFallbackDefaultCandidate -Entry $Entry)
        IsForced                         = [bool]$Entry.IsForced
        IsSupplemental                   = [bool]$Entry.IsSupplemental
    }
}

function Get-SubtitleBuilderFfmpegBaseDisposition {
    param([Parameter(Mandatory)] $Decision)

    if ([bool]$Decision.IsForced) { return 'forced' }
    return '0'
}

function Set-SubtitleBuilderFfmpegDefaultDisposition {
    param([Parameter(Mandatory)] $Track)

    $Track.Disp = if ([string]$Track.Disp -eq 'forced') { 'default+forced' } else { 'default' }
}

function Get-SubtitleBuilderFfmpegConvertedDisposition {
    param(
        [Parameter(Mandatory)] $Decision,
        [Parameter(Mandatory)] $DefaultState
    )

    $disp = '0'
    if ([bool]$Decision.IsPreferredDefaultCandidate -and -not [bool]$DefaultState.DefaultSet) {
        $disp = 'default'
        $DefaultState.DefaultSet = $true
    }
    if ([bool]$Decision.IsForced) {
        $disp = if ($disp -eq 'default') { 'default+forced' } else { 'forced' }
    }
    return $disp
}

function Set-SubtitleBuilderBoolDefaultDisposition {
    param(
        [Parameter(Mandatory)] $Track,
        [Parameter(Mandatory)] $DefaultState,
        [Parameter(Mandatory)] $Decision
    )

    $isDefault = $false
    if ([bool]$Decision.IsPreferredDefaultCandidate -and -not [bool]$DefaultState.DefaultSet) {
        $isDefault = $true
        $DefaultState.DefaultSet = $true
    }
    $Track.IsDefault = [bool]$isDefault
    return [bool]$isDefault
}

function Add-SubtitleBuilderFallbackDefaultCandidate {
    param(
        [Parameter(Mandatory)] $DefaultState,
        [Parameter(Mandatory)] $Decision,
        [Parameter(Mandatory)] $Track
    )

    if ([bool]$Decision.IsFallbackDefaultCandidate) {
        $DefaultState.FallbackCandidates.Add($Track)
    }
}

function Set-SubtitleBuilderFallbackDefault {
    param(
        [Parameter(Mandatory)] $DefaultState,
        [ValidateSet('FFmpeg','Mkvmerge')]
        [string] $Builder
    )

    if ([bool]$DefaultState.DefaultSet -or $DefaultState.FallbackCandidates.Count -le 0) {
        return
    }

    $fallback = $DefaultState.FallbackCandidates[0]
    if ($Builder -eq 'FFmpeg') {
        Set-SubtitleBuilderFfmpegDefaultDisposition -Track $fallback
    } else {
        $fallback.IsDefault = $true
    }
}

function New-SubtitleBuilderDefaultState {
    return @{
        DefaultSet         = $false
        FallbackCandidates = [System.Collections.Generic.List[hashtable]]::new()
    }
}

function Get-SubtitleBuilderTrackDecisionRecords {
    param(
        [Parameter(Mandatory)] $FilterResult,
        [Parameter(Mandatory)]
        [ValidateSet('FFmpeg','Mkvmerge')]
        [string] $Builder,
        [bool] $CanPreserveTx3g = $false,
        [bool] $CanPreserveBdpgs = $false,
        [bool] $CanPreserveVobSub = $false
    )

    $records = [System.Collections.Generic.List[object]]::new()
    $effectiveDropAss = Get-EffectiveSubtitleSwitch -Name 'DropAssAfterConversion' -Default $false
    $effectiveDropTx3g = Get-EffectiveSubtitleSwitch -Name 'DropTx3gAfterConversion' -Default $false
    $effectiveDropBdpgs = Get-EffectiveSubtitleSwitch -Name 'DropBdpgsAfterConversion' -Default $false
    $effectiveDropVobSub = Get-EffectiveSubtitleSwitch -Name 'DropVobSubAfterConversion' -Default $false
    $containerName = (Get-ConfiguredOutputContainerName).ToUpperInvariant()
    $mp4CompatibilityMode = ($Builder -eq 'FFmpeg' -and (Test-ConfiguredOutputContainerIsMp4))
    if ($mp4CompatibilityMode) {
        $effectiveDropAss = $true
        $CanPreserveTx3g = $false
        $CanPreserveBdpgs = $false
        $CanPreserveVobSub = $false
    }

    foreach ($entry in @($FilterResult.Convert | Where-Object { $null -ne $_ })) {
        $preserveAssOriginal = -not $effectiveDropAss
        $assPreserveReason = if ($effectiveDropAss) { 'drop_original_ass_enabled' } else { 'preserved' }
        $records.Add((New-SubtitleBuilderTrackDecisionRecord `
            -Builder $Builder `
            -Action 'ConvertAss' `
            -Entry $entry `
            -PreserveOriginal:$preserveAssOriginal `
            -OriginalPreserveReason $assPreserveReason `
            -OriginalTitleSuffix '[ASS]' `
            -ConversionKind 'ass_to_srt')) | Out-Null
    }

    foreach ($entry in @($FilterResult.Tx3gConvert | Where-Object { $null -ne $_ })) {
        $preserveOriginal = $false
        $preserveReason = 'drop_original_tx3g_enabled'
        $containerLogMessage = ''
        if (-not $effectiveDropTx3g) {
            if ($Builder -eq 'FFmpeg' -and $CanPreserveTx3g) {
                $preserveOriginal = $true
                $preserveReason = 'preserved'
            } else {
                $preserveReason = 'container_does_not_preserve_tx3g'
                if ($Builder -eq 'FFmpeg') {
                    $containerLogMessage = "TX3G original stream $($entry.Stream.index) cannot be preserved as tx3g in $containerName output; muxing converted SRT only"
                } else {
                    $containerLogMessage = "TX3G original stream $($entry.Stream.index) cannot be preserved as tx3g in Matroska remux output; muxing converted SRT only"
                }
            }
        }

        $records.Add((New-SubtitleBuilderTrackDecisionRecord `
            -Builder $Builder `
            -Action 'ConvertTx3g' `
            -Entry $entry `
            -PreserveOriginal:$preserveOriginal `
            -OriginalPreserveReason $preserveReason `
            -OriginalTitleSuffix '[TX3G]' `
            -ContainerLogMessage $containerLogMessage `
            -ConversionKind 'tx3g_to_srt')) | Out-Null
    }

    foreach ($entry in @($FilterResult.BdpgsConvert | Where-Object { $null -ne $_ })) {
        $preserveOriginal = $false
        $preserveReason = 'drop_original_bdpgs_enabled'
        $containerLogMessage = ''
        if (-not $effectiveDropBdpgs) {
            if ($Builder -eq 'Mkvmerge' -or $CanPreserveBdpgs) {
                $preserveOriginal = $true
                $preserveReason = 'preserved'
            } else {
                $preserveReason = 'container_does_not_preserve_bdpgs'
                $containerLogMessage = "BDPGS original stream $($entry.Stream.index) cannot be preserved in $containerName output; muxing OCR SRT only"
            }
        }

        $records.Add((New-SubtitleBuilderTrackDecisionRecord `
            -Builder $Builder `
            -Action 'ConvertBdpgs' `
            -Entry $entry `
            -PreserveOriginal:$preserveOriginal `
            -OriginalPreserveReason $preserveReason `
            -OriginalTitleSuffix '[BDPGS]' `
            -ContainerLogMessage $containerLogMessage `
            -ConversionKind 'bdpgs_to_srt')) | Out-Null
    }

    foreach ($entry in @($FilterResult.VobSubConvert | Where-Object { $null -ne $_ })) {
        $preserveOriginal = $false
        $sourceKind = if ($entry -is [hashtable] -and $entry.ContainsKey('SourceKind')) {
            [string]$entry.SourceKind
        } elseif ($entry.PSObject.Properties['SourceKind']) {
            [string]$entry.SourceKind
        } else {
            'embedded'
        }
        $preserveReason = if ($sourceKind -eq 'sidecar') { 'external_sidecar_preserved_outside_output' } else { 'drop_original_vobsub_enabled' }
        $containerLogMessage = ''
        if ($sourceKind -ne 'sidecar' -and -not $effectiveDropVobSub) {
            if ($Builder -eq 'Mkvmerge' -or $CanPreserveVobSub) {
                $preserveOriginal = $true
                $preserveReason = 'preserved'
            } else {
                $preserveReason = 'container_does_not_preserve_vobsub'
                $containerLogMessage = "VobSub original stream $($entry.Stream.index) cannot be preserved in $containerName output; muxing OCR SRT only"
            }
        }

        $records.Add((New-SubtitleBuilderTrackDecisionRecord `
            -Builder $Builder `
            -Action 'ConvertVobSub' `
            -Entry $entry `
            -PreserveOriginal:$preserveOriginal `
            -OriginalPreserveReason $preserveReason `
            -OriginalTitleSuffix '[VobSub]' `
            -ContainerLogMessage $containerLogMessage `
            -ConversionKind 'vobsub_to_srt')) | Out-Null
    }

    foreach ($entry in @($FilterResult.Keep | Where-Object { $null -ne $_ })) {
        $routesToReview = $false
        $reviewErrorCode = ''
        $reviewReason = ''
        $reviewKind = ''
        $sourceKind = if ($entry -is [hashtable] -and $entry.ContainsKey('SourceKind')) {
            [string]$entry.SourceKind
        } elseif ($entry.PSObject.Properties['SourceKind']) {
            [string]$entry.SourceKind
        } else {
            'embedded'
        }

        if ([bool]$entry.IsTx3g) {
            $tx3gSupported = ($Builder -eq 'FFmpeg' -and $CanPreserveTx3g)
            if (-not $tx3gSupported) {
                $routesToReview = $true
                $reviewErrorCode = 'SUBTITLE_TX3G_CONTAINER_UNSUPPORTED'
                $reviewKind = 'tx3g'
                if ($Builder -eq 'FFmpeg') {
                    $reviewReason = "$containerName output cannot preserve TX3G stream $($entry.Stream.index); enable ConvertTx3gToSrt for SRT conversion."
                } else {
                    $reviewReason = "Matroska remux output cannot preserve TX3G stream $($entry.Stream.index); enable ConvertTx3gToSrt to mux a converted SRT track."
                }
            }
        } elseif ([bool]$entry.IsBdpgs -and $Builder -eq 'FFmpeg' -and -not $CanPreserveBdpgs) {
            $routesToReview = $true
            $reviewErrorCode = 'SUBTITLE_BDPGS_CONTAINER_UNSUPPORTED'
            $reviewKind = 'bdpgs'
            $reviewReason = "$containerName output cannot preserve BDPGS stream $($entry.Stream.index); enable ConvertBdpgsToSrt for OCR conversion."
        } elseif ([bool]$entry.IsVobSub) {
            if ($sourceKind -eq 'sidecar') {
                $routesToReview = $true
                $reviewErrorCode = 'SUBTITLE_VOBSUB_SIDECAR_PRESERVE_UNSUPPORTED'
                $reviewKind = 'vobsub'
                $idxPath = if ($entry -is [hashtable] -and $entry.ContainsKey('IdxPath')) {
                    [string]$entry.IdxPath
                } elseif ($entry.PSObject.Properties['IdxPath']) {
                    [string]$entry.IdxPath
                } else {
                    ''
                }
                $idxLeaf = if ([string]::IsNullOrWhiteSpace($idxPath)) { 'external IDX/SUB sidecar' } else { [System.IO.Path]::GetFileName($idxPath) }
                $reviewReason = "External VobSub sidecar $idxLeaf cannot be preserved in the current output path; enable ConvertVobSubToSrt for OCR conversion or handle the sidecar manually before publish."
            } elseif ($Builder -eq 'FFmpeg' -and -not $CanPreserveVobSub) {
                $routesToReview = $true
                $reviewErrorCode = 'SUBTITLE_VOBSUB_CONTAINER_UNSUPPORTED'
                $reviewKind = 'vobsub'
                $reviewReason = "$containerName output cannot preserve VobSub stream $($entry.Stream.index); enable ConvertVobSubToSrt for OCR conversion."
            }
        }
        if ($mp4CompatibilityMode -and -not $routesToReview) {
            $routesToReview = $true
            $reviewErrorCode = 'SUBTITLE_MP4_EXTERNAL_SRT_REQUIRED'
            $reviewKind = 'tx3g'
            $reviewReason = "$containerName compatibility output does not embed subtitle stream $($entry.Stream.index); route through an SRT conversion sidecar path or review manually."
        }

        $preserveKeepOriginal = -not $routesToReview
        $records.Add((New-SubtitleBuilderTrackDecisionRecord `
            -Builder $Builder `
            -Action 'Keep' `
            -Entry $entry `
            -PreserveOriginal:$preserveKeepOriginal `
            -RoutesToReview:$routesToReview `
            -ReviewErrorCode $reviewErrorCode `
            -ReviewReason $reviewReason `
            -ReviewFailureKind $reviewKind)) | Out-Null
    }

    foreach ($entry in @($FilterResult.Burn | Where-Object { $null -ne $_ })) {
        $records.Add((New-SubtitleBuilderTrackDecisionRecord `
            -Builder $Builder `
            -Action 'Burn' `
            -Entry $entry `
            -PolicyReason 'file_override_burn_in')) | Out-Null
    }

    foreach ($entry in @($FilterResult.Drop | Where-Object { $null -ne $_ })) {
        $entryStreamIndex = if ($entry.Stream -and $null -ne $entry.Stream.index -and [int]$entry.Stream.index -ge 0) { [int]$entry.Stream.index } else { $null }
        $entrySubtitleOrdinal = if ($entry.ContainsKey('SubtitleOrdinal')) { [int]$entry.SubtitleOrdinal } else { $null }
        $matchingDecision = @($FilterResult.Decisions | Where-Object {
            if ($null -ne $entryStreamIndex) {
                $null -ne $_.source_stream_index -and [int]$_.source_stream_index -eq $entryStreamIndex
            } else {
                [string]$_.source_kind -eq 'sidecar' -and $null -ne $_.subtitle_ordinal -and [int]$_.subtitle_ordinal -eq $entrySubtitleOrdinal
            }
        } | Select-Object -First 1)
        $policyReason = if ($matchingDecision.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace([string]$matchingDecision[0].reason)) { [string]$matchingDecision[0].reason } else { 'backend_subtitle_policy_drop' }
        $records.Add((New-SubtitleBuilderTrackDecisionRecord `
            -Builder $Builder `
            -Action 'Drop' `
            -Entry $entry `
            -PolicyReason $policyReason)) | Out-Null
    }

    return @($records.ToArray())
}
