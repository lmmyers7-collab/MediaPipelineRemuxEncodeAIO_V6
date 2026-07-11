# Extracted from ops/pipeline/entrypoints/Audit-MediaLibrary.ps1. Responsibility: compatibility findings and per-file audit results

function Add-AuditSubtitleCompatibilityIssues {
    param(
        $Result,
        [array]$SubtitleStreams = @(),
        [array]$Tx3gSubtitleStreams = @(),
        [array]$BdpgsSubtitleStreams = @(),
        [array]$VobSubSubtitleStreams = @(),
        $DefaultSubtitle = $null
    )

    if (@($SubtitleStreams).Count -eq 0) { return }

    $subtitleLangs = @($SubtitleStreams | ForEach-Object {
        $lang = (Get-StreamTagValue -Stream $_ -Name 'language')
        if ($lang) { Convert-ToLowerInvariantSafe $lang } else { 'und' }
    } | Select-Object -Unique)
    $textSubtitleCodecs = Get-MediaSubtitleCodecTextNames
    $externalFriendlyTextCodecs = Get-MediaSubtitleCodecExternalFriendlyTextNames
    $assSubtitleCodecs = Get-MediaSubtitleCodecAssNames
    $imageSubtitleCodecs = Get-MediaSubtitleCodecImageNames

    $hasTextSubs = @($Result.SubtitleCodecs | Where-Object { $_ -in $textSubtitleCodecs }).Count -gt 0
    $hasExternalFriendlyTextSubs = @($Result.SubtitleCodecs | Where-Object { $_ -in $externalFriendlyTextCodecs }).Count -gt 0
    $hasTx3gSubs = @($Tx3gSubtitleStreams).Count -gt 0
    $hasBdpgsSubs = @($BdpgsSubtitleStreams).Count -gt 0
    $hasVobSubSubs = @($VobSubSubtitleStreams).Count -gt 0
    $hasAssSubs  = @($Result.SubtitleCodecs | Where-Object { $_ -in $assSubtitleCodecs }).Count -gt 0
    $hasImageSubs = @($Result.SubtitleCodecs | Where-Object { $_ -in $imageSubtitleCodecs }).Count -gt 0
    $Result.HasTextSubtitle = $hasTextSubs

    if ($hasTx3gSubs -and -not $hasExternalFriendlyTextSubs -and -not $hasAssSubs -and -not $hasImageSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'tx3g-only-subtitles' -Message 'This file only has embedded MP4 Timed Text / tx3g subtitles and no embedded SRT/WebVTT-style subtitle track.' -SuggestedAction 'Run MediaPipeline with ConvertTx3gToSrt enabled to mux a more compatible subtitle track; enable CreateExternalTx3gSrtSidecars only if you also want external SRT files.'
    }

    $tx3gValidatedSrtCount = $Result.Tx3gExternalSrtCount + $Result.Tx3gEmbeddedSrtCount
    if ($hasTx3gSubs -and $tx3gValidatedSrtCount -lt @($Tx3gSubtitleStreams).Count) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'tx3g-subtitles-extractable' -Message ("ffprobe found {0} embedded tx3g subtitle track(s); {1} validated converted SRT output(s) were found ({2} external, {3} embedded)." -f @($Tx3gSubtitleStreams).Count, $tx3gValidatedSrtCount, $Result.Tx3gExternalSrtCount, $Result.Tx3gEmbeddedSrtCount) -SuggestedAction 'Run MediaPipeline with ConvertTx3gToSrt enabled to mux converted subtitles without re-encoding video; enable CreateExternalTx3gSrtSidecars when external SRT files are desired.'
    }

    if ($hasBdpgsSubs -and -not $hasExternalFriendlyTextSubs -and -not $hasAssSubs -and -not $hasTx3gSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'bdpgs-only-subtitles' -Message 'This file only has embedded Blu-ray PGS image subtitles and no embedded SRT/WebVTT-style subtitle track.' -SuggestedAction 'Keep BDPGS for MKV playback, or enable ConvertBdpgsToSrt with a configured OCR tool when text subtitles are required.'
    }

    if ($hasBdpgsSubs -and $Result.BdpgsEmbeddedSrtCount -lt @($BdpgsSubtitleStreams).Count) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'bdpgs-subtitles-ocr-candidate' -Message ("ffprobe found {0} embedded BDPGS subtitle track(s); {1} pipeline OCR SRT track record(s) were found." -f @($BdpgsSubtitleStreams).Count, $Result.BdpgsEmbeddedSrtCount) -SuggestedAction 'Enable ConvertBdpgsToSrt only after configuring a PGS/SUP OCR tool such as PgsToSrt with Tesseract language data.'
    }

    if ($hasVobSubSubs -and -not $hasExternalFriendlyTextSubs -and -not $hasAssSubs -and -not $hasTx3gSubs -and -not $hasBdpgsSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'vobsub-only-subtitles' -Message 'This file only has embedded VobSub/DVD bitmap subtitles and no embedded SRT/WebVTT-style subtitle track.' -SuggestedAction 'Keep VobSub for MKV playback, or enable ConvertVobSubToSrt with Subtitle Edit 4.x SubtitleEdit.exe and Tesseract when text subtitles are required.'
    }

    if ($hasVobSubSubs -and $Result.VobSubEmbeddedSrtCount -lt @($VobSubSubtitleStreams).Count) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'vobsub-subtitles-ocr-candidate' -Message ("ffprobe found {0} embedded VobSub subtitle track(s); {1} pipeline OCR SRT track record(s) were found." -f @($VobSubSubtitleStreams).Count, $Result.VobSubEmbeddedSrtCount) -SuggestedAction 'Enable ConvertVobSubToSrt only after configuring Subtitle Edit 4.x SubtitleEdit.exe and bundled Tesseract.'
    }

    if ($hasAssSubs -and -not $hasTextSubs -and -not $hasImageSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'ass-only-subtitles' -Message 'This file only has ASS/SSA subtitles and no SRT-style text track.' -SuggestedAction 'Review on target Plex clients if subtitle compatibility matters.'
    }

    if ($hasImageSubs -and -not $hasTextSubs -and -not $hasAssSubs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'image-only-subtitles' -Message 'This file only has image-based subtitles and no text subtitle track.' -SuggestedAction 'Review on target Plex clients if subtitle compatibility matters.'
    }

    if ($subtitleLangs.Count -gt 0 -and @($subtitleLangs | Where-Object { $_ -notin @('', 'und') }).Count -eq 0) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'subtitle-language-tags-unknown' -Message 'All subtitle tracks are missing language tags or are tagged as und.' -SuggestedAction 'Review subtitle metadata if Plex language selection matters.'
    }
    if (@($SubtitleStreams).Count -gt 1) {
        $untitledSubtitleCount = @($SubtitleStreams | Where-Object { [string]::IsNullOrWhiteSpace((Get-StreamTagValue -Stream $_ -Name 'title')) }).Count
        if ($untitledSubtitleCount -gt 0) {
            Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'subtitle-track-titles-missing' -Message "$untitledSubtitleCount subtitle track(s) are missing title metadata in a multi-subtitle file." -SuggestedAction 'Consider rerunning or retagging so Plex subtitle selection is clearer.'
        }
    }

    if ($DefaultSubtitle -and $Result.DefaultSubtitleCodec -in $assSubtitleCodecs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'default-ass-subtitle' -Message "Default subtitle codec '$($Result.DefaultSubtitleCodec)' is less Plex-friendly than SRT." -SuggestedAction 'Review subtitle behavior on your target clients.'
    }

    if ($DefaultSubtitle -and $Result.DefaultSubtitleCodec -in $imageSubtitleCodecs) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'default-image-subtitle' -Message "Default subtitle codec '$($Result.DefaultSubtitleCodec)' is image-based." -SuggestedAction 'Review subtitle behavior on your target clients.'
    }
    if ($DefaultSubtitle -and $Result.DefaultSubtitleLanguage -eq 'und') {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'default-subtitle-language-unknown' -Message 'Default subtitle is tagged as und / unknown language.' -SuggestedAction 'Review or retag the default subtitle language if Plex language selection matters.'
    }
}

function Get-AuditResultForFile {
    param(
        $FileInfo,
        $ProbeResult = $null
    )

    $result = New-AuditResult -FileInfo $FileInfo -RelativePath (Get-RelativePathSafe -RootPath $script:LibraryRootResolved -FullPath $FileInfo.FullName)
    $isLikelyTv = Test-LikelyTvLibraryItem $FileInfo
    $tvInfo = $null
    if ($isLikelyTv) {
        $tvInfo = Get-TVInfoFromFile $FileInfo
        $result.MediaType = 'TV'
    } else {
        $result.MediaType = 'Movie'
    }
    $result.LookupTitle = Get-LibraryLookupTitle -FileInfo $FileInfo -IsLikelyTv $isLikelyTv -TvInfo $tvInfo

    if ($IncludeSidecars) {
        Analyze-Sidecar -Result $result -FileInfo $FileInfo
    }

    $probe = if ($null -ne $ProbeResult) { $ProbeResult } else { Invoke-FfprobeJsonCached -FileInfo $FileInfo }
    if (-not $probe.Success) {
        Add-AuditIssue -Result $result -Bucket 'REDOWNLOAD_CANDIDATE' -Code 'ffprobe-open-failed' -Message $probe.Error -SuggestedAction 'Redownload or replace the file if it does not open cleanly in ffprobe/Plex.'
        return $result
    }

    $data = $probe.Data
    $streams = @($data.streams | Where-Object { $null -ne $_ })
    $videoStreams = @($streams | Where-Object { $_.codec_type -eq 'video' })
    $audioStreams = @($streams | Where-Object { $_.codec_type -eq 'audio' })
    $subtitleStreams = @($streams | Where-Object { $_.codec_type -eq 'subtitle' })
    $tx3gSubtitleStreams = @($subtitleStreams | Where-Object { Test-AuditTx3gSubtitleStream $_ })
    $bdpgsSubtitleStreams = @($subtitleStreams | Where-Object { Test-AuditBdpgsSubtitleStream $_ })
    $vobSubSubtitleStreams = @($subtitleStreams | Where-Object { Test-AuditVobSubSubtitleStream $_ })
    if ($null -eq $result.PSObject.Properties['Tx3gEmbeddedSrtInvalidCount']) {
        Add-Member -InputObject $result -MemberType NoteProperty -Name Tx3gEmbeddedSrtInvalidCount -Value 0 -Force
        Write-AuditLog 'AUDIT_TX3G_RESULT_REPAIRED: The audit record was missing a TX3G subtitle count. It was repaired and the audit continued.' 'WARN'
    }
    if (@($result.Tx3gEmbeddedSrtRecords).Count -gt 0) {
        $result.Tx3gEmbeddedSrtCount = Get-AuditValidatedEmbeddedSrtRecordCount -Records @($result.Tx3gEmbeddedSrtRecords) -SubtitleStreams $subtitleStreams -SourceKind 'tx3g'
        $result.Tx3gEmbeddedSrtInvalidCount = @($result.Tx3gEmbeddedSrtRecords).Count - $result.Tx3gEmbeddedSrtCount
        if ($result.Tx3gEmbeddedSrtInvalidCount -gt 0) {
            Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'tx3g-embedded-srt-stale' -Message "The pipeline sidecar lists $($result.Tx3gEmbeddedSrtInvalidCount) tx3g embedded SRT conversion record(s) that do not match a current text subtitle stream." -SuggestedAction 'Rerun this file through MediaPipeline or refresh the sidecar if the file was modified outside the pipeline.'
        }
    }
    if (@($result.BdpgsEmbeddedSrtRecords).Count -gt 0) {
        $result.BdpgsEmbeddedSrtCount = Get-AuditValidatedEmbeddedSrtRecordCount -Records @($result.BdpgsEmbeddedSrtRecords) -SubtitleStreams $subtitleStreams -SourceKind 'bdpgs'
        $result.BdpgsEmbeddedSrtInvalidCount = @($result.BdpgsEmbeddedSrtRecords).Count - $result.BdpgsEmbeddedSrtCount
        if ($result.BdpgsEmbeddedSrtInvalidCount -gt 0) {
            Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'bdpgs-embedded-srt-stale' -Message "The pipeline sidecar lists $($result.BdpgsEmbeddedSrtInvalidCount) BDPGS OCR SRT record(s) that do not match a current text subtitle stream." -SuggestedAction 'Rerun this file through MediaPipeline or refresh the sidecar if the file was modified outside the pipeline.'
        }
    }
    if (@($result.VobSubEmbeddedSrtRecords).Count -gt 0) {
        $result.VobSubEmbeddedSrtCount = Get-AuditValidatedEmbeddedSrtRecordCount -Records @($result.VobSubEmbeddedSrtRecords) -SubtitleStreams $subtitleStreams -SourceKind 'vobsub'
        $result.VobSubEmbeddedSrtInvalidCount = @($result.VobSubEmbeddedSrtRecords).Count - $result.VobSubEmbeddedSrtCount
        if ($result.VobSubEmbeddedSrtInvalidCount -gt 0) {
            Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'vobsub-embedded-srt-stale' -Message "The pipeline sidecar lists $($result.VobSubEmbeddedSrtInvalidCount) VobSub OCR SRT record(s) that do not match a current text subtitle stream." -SuggestedAction 'Rerun this file through MediaPipeline or refresh the sidecar if the file was modified outside the pipeline.'
        }
    }

    $result.Container = [string](Get-TagValue -Object $data.format -Name 'format_name')
    $result.DurationSeconds = [math]::Round((Try-ParseDoubleInvariant (Get-TagValue -Object $data.format -Name 'duration')), 3)
    $result.VideoCodecs = @($videoStreams | ForEach-Object { Convert-ToLowerInvariantSafe $_.codec_name } | Where-Object { $_ } | Select-Object -Unique)
    $result.AudioCodecs = @($audioStreams | ForEach-Object { Convert-ToLowerInvariantSafe $_.codec_name } | Where-Object { $_ } | Select-Object -Unique)
    $result.SubtitleCodecs = @($subtitleStreams | ForEach-Object { Convert-ToLowerInvariantSafe $_.codec_name } | Where-Object { $_ } | Select-Object -Unique)
    $result.AudioCount = $audioStreams.Count
    $result.SubtitleCount = $subtitleStreams.Count
    $result.Tx3gSubtitleCount = $tx3gSubtitleStreams.Count
    $result.BdpgsSubtitleCount = $bdpgsSubtitleStreams.Count
    $result.VobSubSubtitleCount = $vobSubSubtitleStreams.Count
    if ($tx3gSubtitleStreams.Count -gt 0) {
        $matchingExternalSrts = @(Get-MatchingExternalSrtFilesForAudit -FileInfo $FileInfo -Tx3gSubtitleStreams $tx3gSubtitleStreams -KnownTx3gSrtFiles @($result.Tx3gSidecarSrtFiles))
        $result.Tx3gExternalSrtFiles = @($matchingExternalSrts)
        $result.Tx3gExternalSrtCount = $matchingExternalSrts.Count
    }

    if ($videoStreams.Count -eq 0) {
        Add-AuditIssue -Result $result -Bucket 'REDOWNLOAD_CANDIDATE' -Code 'missing-video-stream' -Message 'ffprobe found no video streams in this file.' -SuggestedAction 'Redownload or replace the file.'
    }
    if ($videoStreams.Count -gt 1) {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'multiple-video-streams' -Message "ffprobe found $($videoStreams.Count) video streams in this file." -SuggestedAction 'Review whether the extra video streams are intentional.'
    }

    if ($audioStreams.Count -eq 0) {
        Add-AuditIssue -Result $result -Bucket 'REDOWNLOAD_CANDIDATE' -Code 'missing-audio-stream' -Message 'ffprobe found no audio streams in this file.' -SuggestedAction 'Redownload or replace the file.'
    }

    if ($result.DurationSeconds -le 0) {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'missing-duration' -Message 'Container duration could not be read from ffprobe.' -SuggestedAction 'Play-test the file or rerun it through the pipeline if other issues are present.'
    }

    $defaultAudioInfo = Get-DefaultStream -Streams $audioStreams
    $defaultAudio = $defaultAudioInfo.Stream
    $expectedDefaultAudioCandidate = Get-ExpectedDefaultAudioCandidate -Streams $audioStreams
    $explicitDefaultAudioCount = @($audioStreams | Where-Object { (Get-StreamDispositionValue $_ 'default') -eq 1 }).Count
    if ($explicitDefaultAudioCount -gt 1) {
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'audio-multiple-defaults' -Message "Multiple audio tracks ($explicitDefaultAudioCount) are marked default." -SuggestedAction 'Rerun the file through MediaPipeline or clear the extra default audio flags.'
    }
    if ($defaultAudio) {
        $result.DefaultAudioCodec = Convert-ToLowerInvariantSafe $defaultAudio.codec_name
        $audioLang = (Get-StreamTagValue -Stream $defaultAudio -Name 'language')
        $result.DefaultAudioLanguage = if ($audioLang) { Convert-ToLowerInvariantSafe $audioLang } else { 'und' }
        $result.DefaultAudioTitle = Get-StreamTagValue -Stream $defaultAudio -Name 'title'
    }

    $defaultSubtitleInfo = Get-DefaultStream -Streams $subtitleStreams
    $defaultSubtitle = $defaultSubtitleInfo.Stream
    $explicitDefaultSubtitleCount = @($subtitleStreams | Where-Object { (Get-StreamDispositionValue $_ 'default') -eq 1 }).Count
    if ($explicitDefaultSubtitleCount -gt 1) {
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'subtitle-multiple-defaults' -Message "Multiple subtitle tracks ($explicitDefaultSubtitleCount) are marked default." -SuggestedAction 'Rerun the file through MediaPipeline or clear the extra default subtitle flags.'
    }
    if ($defaultSubtitle) {
        $result.DefaultSubtitleCodec = Convert-ToLowerInvariantSafe $defaultSubtitle.codec_name
        $subLang = (Get-StreamTagValue -Stream $defaultSubtitle -Name 'language')
        $result.DefaultSubtitleLanguage = if ($subLang) { Convert-ToLowerInvariantSafe $subLang } else { 'und' }
        $result.DefaultSubtitleTitle = Get-StreamTagValue -Stream $defaultSubtitle -Name 'title'
    }

    if ($audioStreams.Count -gt 1 -and -not $defaultAudioInfo.IsExplicit) {
        $expectedLabel = if ($expectedDefaultAudioCandidate) { Format-AudioCandidateLabel $expectedDefaultAudioCandidate } else { 'the preferred non-commentary track' }
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'audio-missing-explicit-default' -Message "Multiple audio tracks are present, but none is marked default. Expected default: $expectedLabel." -SuggestedAction 'Rerun the file through MediaPipeline to normalize audio defaults.'
    }
    if ($explicitDefaultAudioCount -eq 1 -and $defaultAudio -and $expectedDefaultAudioCandidate) {
        $actualIndex = [string](Get-TagValue -Object $defaultAudio -Name 'index')
        $expectedIndex = [string](Get-TagValue -Object $expectedDefaultAudioCandidate.Stream -Name 'index')
        if ($actualIndex -ne $expectedIndex) {
            Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'audio-default-policy-mismatch' -Message ("Default audio track '{0}' does not match the configured preferred-language / highest-fidelity policy. Expected: {1}." -f (Format-AudioCandidateLabel ([pscustomobject]@{
                Stream         = $defaultAudio
                NormalizedLang = Normalize-AudioLanguagePreferenceValue (Get-StreamTagValue -Stream $defaultAudio -Name 'language')
                Title          = Get-StreamTagValue -Stream $defaultAudio -Name 'title'
            })), (Format-AudioCandidateLabel $expectedDefaultAudioCandidate)) -SuggestedAction 'Rerun the file through MediaPipeline or retag the default audio track to match the configured policy.'
        }
    }
    if ($audioStreams.Count -gt 1) {
        $untitledAudioCount = @($audioStreams | Where-Object { [string]::IsNullOrWhiteSpace((Get-StreamTagValue -Stream $_ -Name 'title')) }).Count
        if ($untitledAudioCount -gt 0) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'audio-track-titles-missing' -Message "$untitledAudioCount audio track(s) are missing title metadata in a multi-audio file." -SuggestedAction 'Consider rerunning or retagging so Plex track selection is clearer.'
        }
    }

    if ($defaultAudio -and $result.DefaultAudioTitle -match '(?i)commentary') {
        Add-AuditIssue -Result $result -Bucket 'RERUN_PIPELINE' -Code 'commentary-default-audio' -Message "Default audio title '$($result.DefaultAudioTitle)' looks like commentary." -SuggestedAction 'Rerun the file or manually clear the commentary track as default.'
    }
    if ($defaultAudio -and $result.DefaultAudioLanguage -eq 'und') {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'default-audio-language-unknown' -Message 'Default audio is tagged as und / unknown language.' -SuggestedAction 'Review or retag the default audio language if Plex language selection matters.'
    }

    if ($defaultAudio -and $result.DefaultAudioCodec -and $result.DefaultAudioCodec -notin $script:CompatibleAudioCodecs) {
        Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'default-audio-may-transcode' -Message "Default audio codec '$($result.DefaultAudioCodec)' is outside the current compatible-audio list." -SuggestedAction 'Play-test this file on Plex/Shield if direct play matters.'
    }

    $audioLangs = @()
    if ($audioStreams.Count -gt 0) {
        $audioLangs = @($audioStreams | ForEach-Object {
            $lang = (Get-StreamTagValue -Stream $_ -Name 'language')
            if ($lang) { Convert-ToLowerInvariantSafe $lang } else { 'und' }
        } | Select-Object -Unique)
        if ($audioLangs.Count -gt 0 -and @($audioLangs | Where-Object { $_ -notin @('', 'und') }).Count -eq 0) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'audio-language-tags-unknown' -Message 'All audio tracks are missing language tags or are tagged as und.' -SuggestedAction 'Review metadata if language selection matters in Plex.'
        }
    }

    if ($subtitleStreams.Count -gt 0) {
        Add-AuditSubtitleCompatibilityIssues -Result $result -SubtitleStreams $subtitleStreams -Tx3gSubtitleStreams $tx3gSubtitleStreams -BdpgsSubtitleStreams $bdpgsSubtitleStreams -VobSubSubtitleStreams $vobSubSubtitleStreams -DefaultSubtitle $defaultSubtitle
    }

    $englishAudioLangs = @('eng', 'en')
    $englishSubtitleLangs = @('eng', 'en')
    $result.HasEnglishAudio = @($audioLangs | Where-Object { $_ -in $englishAudioLangs }).Count -gt 0
    $result.HasEnglishSubtitle = @($subtitleStreams | Where-Object {
        $codec = Convert-ToLowerInvariantSafe $_.codec_name
        $lang = Convert-ToLowerInvariantSafe (Get-StreamTagValue -Stream $_ -Name 'language')
        $codec -in (Get-MediaSubtitleCodecTextNames) -and $lang -in $englishSubtitleLangs
    }).Count -gt 0

    $knownAudioLangs = @($audioLangs | Where-Object { $_ -notin @('', 'und') })
    $hasKnownNonEnglishAudio = @($knownAudioLangs | Where-Object { $_ -notin $englishAudioLangs }).Count -gt 0
    if ($hasKnownNonEnglishAudio -and -not $result.HasEnglishAudio) {
        if ($subtitleStreams.Count -eq 0) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'foreign-audio-no-subtitles' -Message 'This file has non-English audio and no subtitle tracks.' -SuggestedAction 'Review whether this needs subtitles for normal playback.'
        } elseif (-not $result.HasTextSubtitle) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'foreign-audio-no-text-subtitles' -Message 'This file has non-English audio but no text subtitle track.' -SuggestedAction 'Review whether you want a text subtitle track for easier Plex playback.'
        }
    }

    if ($isLikelyTv) {
        if (-not $tvInfo.IsReliable) {
            Add-AuditIssue -Result $result -Bucket 'REVIEW' -Code 'ambiguous-tv-naming' -Message $tvInfo.ParseError -SuggestedAction ("Suggested rename: {0}" -f (Get-TVParseRenameSuggestion -FileInfo $FileInfo -TvInfo $tvInfo))
        }
    }

    return $result
}
