# Extracted from ops/pipeline/entrypoints/Audit-MediaLibrary.ps1. Responsibility: TV/movie library lookup and sidecar analysis

function Get-TVParseRenameSuggestion {
    param(
        $FileInfo,
        $TvInfo
    )

    $ext = [System.IO.Path]::GetExtension($FileInfo.Name)
    if ($TvInfo -and $TvInfo.Season -gt 0 -and $TvInfo.ShowName) {
        return ("{0} - S{1}E##_Episode Title{2}" -f $TvInfo.ShowName, $TvInfo.Season.ToString('00'), $ext)
    }
    return "Show Name - S01E01$ext"
}

function Test-LikelyTvLibraryItem {
    param($FileInfo)

    $path = $FileInfo.FullName
    $name = $FileInfo.Name
    if ($path -match '(?i)\\(tv|shows|series|anime)\\') { return $true }
    if ($name -match '[Ss]\d{1,2}[Ee]\d{1,2}' -or $name -match '\d{1,2}x\d{1,2}') { return $true }
    if ($name -match '(?i)\bEpisode[\s._-]*\d{1,3}\b' -or $name -match '(?i)\bEp[\s._-]*\d{1,3}\b') { return $true }
    if (Get-TVFolderSeasonInfo $FileInfo.DirectoryName) { return $true }
    return $false
}

function Normalize-LibraryLookupText {
    param(
        [string]$Text,
        [switch]$StripExtension
    )

    if ([string]::IsNullOrWhiteSpace($Text)) { return '' }

    $value = [string]$Text
    if ($StripExtension) {
        $value = [System.IO.Path]::GetFileNameWithoutExtension($value)
    }

    $value = Remove-PriorityMarkersFromName $value
    $value = $value -replace '\{[^}]+\}', ''
    $value = $value -replace '\[[^\]]+\]', ''
    $value = $value -replace '[\._]+', ' '
    $value = $value -replace '\s+', ' '
    return $value.Trim(' ', '-', '_', '.')
}

function Try-FormatMovieLookupTitle {
    param([string]$Candidate)

    $clean = Normalize-LibraryLookupText -Text $Candidate -StripExtension
    if ([string]::IsNullOrWhiteSpace($clean)) { return '' }

    if ($clean -match '^(?<title>.+?)\s*\((?<year>19\d{2}|20\d{2})\)\s*$') {
        return ("{0} ({1})" -f $Matches['title'].Trim(), $Matches['year'])
    }
    if ($clean -match '^(?<title>.+?)\s+(?<year>19\d{2}|20\d{2})\s*$') {
        return ("{0} ({1})" -f $Matches['title'].Trim(), $Matches['year'])
    }

    return $clean
}

function Get-LibraryLookupTitle {
    param(
        $FileInfo,
        [bool]$IsLikelyTv = $false,
        $TvInfo = $null
    )

    if ($IsLikelyTv) {
        if (-not $TvInfo) {
            $TvInfo = Get-TVInfoFromFile $FileInfo
        }

        $showName = if ($TvInfo -and $TvInfo.ShowName) {
            [string]$TvInfo.ShowName
        } else {
            Normalize-TVShowFolderName (Split-Path $FileInfo.DirectoryName -Leaf)
        }

        if ([string]::IsNullOrWhiteSpace($showName)) {
            $showName = Normalize-LibraryLookupText -Text (Split-Path $FileInfo.DirectoryName -Leaf)
        }
        if ([string]::IsNullOrWhiteSpace($showName)) {
            $showName = 'Unknown Show'
        }

        if ($TvInfo -and $TvInfo.Season -gt 0) {
            return ("{0} (Season {1})" -f $showName, $TvInfo.Season.ToString('00'))
        }
        return $showName
    }

    $candidates = @(
        (Split-Path $FileInfo.DirectoryName -Leaf),
        $FileInfo.Name
    )

    foreach ($candidate in $candidates) {
        $formatted = Try-FormatMovieLookupTitle -Candidate $candidate
        if ($formatted -match '\(\d{4}\)$') {
            return $formatted
        }
    }

    foreach ($candidate in $candidates) {
        $formatted = Try-FormatMovieLookupTitle -Candidate $candidate
        if (-not [string]::IsNullOrWhiteSpace($formatted)) {
            return $formatted
        }
    }

    return (Normalize-LibraryLookupText -Text $FileInfo.Name -StripExtension)
}

function Analyze-Sidecar {
    param(
        $Result,
        $FileInfo
    )

    $sidecarPath = Get-SidecarPath $FileInfo.FullName
    $Result.SidecarPath = $sidecarPath

    if (-not (Test-Path -LiteralPath $sidecarPath)) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'missing-sidecar' -Message 'No .pipeline.json sidecar was found next to this library file.' -SuggestedAction 'Rerun the file through MediaPipeline if you want current sidecar metadata and normalization.'
        return
    }

    try {
        $sidecar = Get-Content -LiteralPath $sidecarPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'invalid-sidecar-json' -Message "The sidecar could not be parsed: $($_.Exception.Message)" -SuggestedAction 'Rewrite the output through MediaPipeline or repair the sidecar JSON.'
        return
    }

    $sidecarVersion = [string](Get-TagValue -Object $sidecar -Name 'pipeline_version')
    $Result.SidecarVersion = $sidecarVersion
    $Result.SidecarRoute = [string](Get-TagValue -Object $sidecar -Name 'route')

    $rawTx3gFailureValues = @()
    $tx3gFailureProp = $sidecar.PSObject.Properties['tx3g_srt_failures']
    if ($tx3gFailureProp) {
        $rawTx3gFailureValues = @($tx3gFailureProp.Value | Where-Object { $null -ne $_ })
    }
    $legacyBdpgsFailures = @($rawTx3gFailureValues | Where-Object { [string]$_.ErrorCode -like 'SUBTITLE_BDPGS_*' })
    $tx3gFailures = @($rawTx3gFailureValues | Where-Object { [string]$_.ErrorCode -notlike 'SUBTITLE_BDPGS_*' })
    $Result.Tx3gSidecarFailureCount = $tx3gFailures.Count
    if ($tx3gFailures.Count -gt 0) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'tx3g-extraction-failed' -Message "The pipeline sidecar records $($tx3gFailures.Count) failed tx3g-to-SRT extraction attempt(s)." -SuggestedAction 'Rerun this file after reviewing the subtitle extraction failure report/repro command.'
    }

    $bdpgsEmbeddedProp = $sidecar.PSObject.Properties['bdpgs_embedded_srt_tracks']
    if ($bdpgsEmbeddedProp) {
        $Result.BdpgsEmbeddedSrtRecords = @($bdpgsEmbeddedProp.Value | Where-Object { $null -ne $_ })
    }
    $bdpgsFailures = @()
    $bdpgsFailureProp = $sidecar.PSObject.Properties['bdpgs_srt_failures']
    if ($bdpgsFailureProp) {
        $bdpgsFailures = @($bdpgsFailureProp.Value | Where-Object { $null -ne $_ })
    } else {
        $bdpgsFailures = @($legacyBdpgsFailures)
    }
    $Result.BdpgsSidecarFailureCount = $bdpgsFailures.Count
    if ($bdpgsFailures.Count -gt 0) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'bdpgs-ocr-failed' -Message "The pipeline sidecar records $($bdpgsFailures.Count) failed BDPGS OCR attempt(s)." -SuggestedAction 'Configure the BDPGS OCR tool/Tesseract data, inspect the saved repro command, or disable ConvertBdpgsToSrt to keep image subtitles without OCR.'
    }

    $vobSubEmbeddedProp = $sidecar.PSObject.Properties['vobsub_embedded_srt_tracks']
    if ($vobSubEmbeddedProp) {
        $Result.VobSubEmbeddedSrtRecords = @($vobSubEmbeddedProp.Value | Where-Object { $null -ne $_ })
    }
    $vobSubFailures = @()
    $vobSubFailureProp = $sidecar.PSObject.Properties['vobsub_srt_failures']
    if ($vobSubFailureProp) {
        $vobSubFailures = @($vobSubFailureProp.Value | Where-Object { $null -ne $_ })
    }
    $Result.VobSubSidecarFailureCount = $vobSubFailures.Count
    if ($vobSubFailures.Count -gt 0) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'vobsub-ocr-failed' -Message "The pipeline sidecar records $($vobSubFailures.Count) failed VobSub OCR attempt(s)." -SuggestedAction 'Configure Subtitle Edit 4.x SubtitleEdit.exe and Tesseract, inspect the saved repro command, or disable ConvertVobSubToSrt to preserve supported embedded VobSub tracks without OCR.'
    }

    $tx3gTrackProp = $sidecar.PSObject.Properties['tx3g_srt_tracks']
    if ($tx3gTrackProp) {
        $validTx3gSidecarSrtFiles = [System.Collections.Generic.List[string]]::new()
        $invalidTx3gSidecarSrtRecords = 0
        $baseDirectory = $FileInfo.DirectoryName
        foreach ($trackRecord in @($tx3gTrackProp.Value | Where-Object { $null -ne $_ })) {
            if (Test-AuditTx3gSidecarSrtRecordUsable -Record $trackRecord -BaseDirectory $baseDirectory) {
                $path = Get-AuditSidecarSrtRecordPath -Record $trackRecord -BaseDirectory $baseDirectory
                if (-not [string]::IsNullOrWhiteSpace($path)) { $validTx3gSidecarSrtFiles.Add($path) }
            } else {
                $invalidTx3gSidecarSrtRecords++
            }
        }
        $Result.Tx3gSidecarSrtFiles = @(
            $validTx3gSidecarSrtFiles |
                Sort-Object -Unique
        )
        $Result.Tx3gSidecarSrtInvalidCount = $invalidTx3gSidecarSrtRecords
        if ($invalidTx3gSidecarSrtRecords -gt 0) {
            Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'tx3g-srt-sidecar-stale' -Message "The pipeline sidecar lists $invalidTx3gSidecarSrtRecords tx3g SRT sidecar record(s) that are missing, pending, empty, or not parseable." -SuggestedAction 'Rerun this file or regenerate tx3g SRT sidecars so audit can verify usable subtitle output.'
        }
    }

    $tx3gEmbeddedProp = $sidecar.PSObject.Properties['tx3g_embedded_srt_tracks']
    if ($tx3gEmbeddedProp) {
        $Result.Tx3gEmbeddedSrtRecords = @($tx3gEmbeddedProp.Value | Where-Object { $null -ne $_ })
    }

    if (-not $sidecarVersion) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'sidecar-missing-version' -Message 'The sidecar is present but has no pipeline_version field.' -SuggestedAction 'Rerun the file through MediaPipeline to refresh provenance metadata.'
    } elseif (-not (Test-PipelineVersionString $sidecarVersion)) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'sidecar-invalid-version' -Message "The sidecar pipeline_version '$sidecarVersion' is not a valid semantic version." -SuggestedAction 'Rerun the file through MediaPipeline to refresh provenance metadata.'
    } elseif (Compare-PipelineVersion $sidecarVersion $script:MinPipelineVersion) {
        Add-AuditIssue -Result $Result -Bucket 'RERUN_PIPELINE' -Code 'sidecar-stale-version' -Message "The sidecar pipeline version '$sidecarVersion' is older than the current minimum '$($script:MinPipelineVersion)'." -SuggestedAction 'Rerun the file through MediaPipeline if you want it standardized to the current release.'
    }

    $outputFile = [string](Get-TagValue -Object $sidecar -Name 'output_file')
    if ($outputFile -and $outputFile -ne $FileInfo.Name) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'sidecar-output-mismatch' -Message "The sidecar output_file '$outputFile' does not match the current file name '$($FileInfo.Name)'." -SuggestedAction 'Verify the file was not renamed independently of its sidecar.'
    }

    if (-not $Result.SidecarRoute) {
        Add-AuditIssue -Result $Result -Bucket 'REVIEW' -Code 'sidecar-missing-route' -Message 'The sidecar is present but has no route field.' -SuggestedAction 'If you rerun the file through MediaPipeline, the sidecar will include the current route metadata.'
    }
}
