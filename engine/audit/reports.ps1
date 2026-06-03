# Audit report serialization and writers.

function Export-CsvAtomic {
    param(
        [string]$Path,
        [array]$Rows,
        [string[]]$Header = @()
    )

    $tempPath = New-AtomicTempPath -Path $Path
    try {
        $rowList = if ($null -eq $Rows) { @() } else { @($Rows) }
        if ($rowList.Count -gt 0) {
            $rowList | Export-Csv -LiteralPath $tempPath -NoTypeInformation -Encoding UTF8 -ErrorAction Stop
        } else {
            $headerLine = if (@($Header).Count -gt 0) { ($Header -join ',') } else { '' }
            [System.IO.File]::WriteAllText($tempPath, $headerLine, [System.Text.UTF8Encoding]::new($false))
        }
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    } catch {
        try {
            if (Test-Path -LiteralPath $tempPath) {
                Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
            }
        } catch {}
        throw
    }
}

function Convert-ResultForSerialization {
    param($Result)

    $nonSidecarIssues = @(Get-NonSidecarIssues -Issues $Result.Issues)
    $primaryIssue = Get-PrimaryIssue -Issues $Result.Issues
    $ignoreEntry = Get-AuditIgnoreEntry -Path $Result.Path
    $auditIgnored = $null -ne $ignoreEntry
    $priorityFixLevel = if ($auditIgnored) { 'NONE' } else { Get-PriorityFixLevel -Issues $Result.Issues }
    $priorityScore = if ($auditIgnored) { 0 } else { Get-PriorityScore -Issues $Result.Issues }
    $effectiveBucket = if ($auditIgnored) { 'IGNORED' } else { Get-IssueEffectiveBucket -Issues $Result.Issues }

    return [pscustomobject]@{
        Path                    = $Result.Path
        RelativePath            = $Result.RelativePath
        FileName                = $Result.FileName
        MediaType               = $Result.MediaType
        LookupTitle             = $Result.LookupTitle
        SizeBytes               = $Result.SizeBytes
        SizeGB                  = $Result.SizeGB
        Extension               = $Result.Extension
        Bucket                  = $Result.Bucket
        DurationSeconds         = $Result.DurationSeconds
        Container               = $Result.Container
        VideoCodecs             = @($Result.VideoCodecs)
        AudioCodecs             = @($Result.AudioCodecs)
        SubtitleCodecs          = @($Result.SubtitleCodecs)
        AudioCount              = $Result.AudioCount
        SubtitleCount           = $Result.SubtitleCount
        Tx3gSubtitleCount       = $Result.Tx3gSubtitleCount
        Tx3gEmbeddedSrtCount    = $Result.Tx3gEmbeddedSrtCount
        Tx3gExternalSrtCount    = $Result.Tx3gExternalSrtCount
        Tx3gExternalSrtFiles    = @($Result.Tx3gExternalSrtFiles)
        Tx3gSidecarSrtInvalidCount = $Result.Tx3gSidecarSrtInvalidCount
        Tx3gSidecarFailureCount = $Result.Tx3gSidecarFailureCount
        BdpgsSubtitleCount      = $Result.BdpgsSubtitleCount
        BdpgsEmbeddedSrtCount   = $Result.BdpgsEmbeddedSrtCount
        BdpgsEmbeddedSrtInvalidCount = $Result.BdpgsEmbeddedSrtInvalidCount
        BdpgsSidecarFailureCount = $Result.BdpgsSidecarFailureCount
        VobSubSubtitleCount     = $Result.VobSubSubtitleCount
        VobSubEmbeddedSrtCount  = $Result.VobSubEmbeddedSrtCount
        VobSubEmbeddedSrtInvalidCount = $Result.VobSubEmbeddedSrtInvalidCount
        VobSubSidecarFailureCount = $Result.VobSubSidecarFailureCount
        DefaultAudioCodec       = $Result.DefaultAudioCodec
        DefaultAudioLanguage    = $Result.DefaultAudioLanguage
        DefaultAudioTitle       = $Result.DefaultAudioTitle
        DefaultSubtitleCodec    = $Result.DefaultSubtitleCodec
        DefaultSubtitleLanguage = $Result.DefaultSubtitleLanguage
        DefaultSubtitleTitle    = $Result.DefaultSubtitleTitle
        HasEnglishAudio         = $Result.HasEnglishAudio
        HasEnglishSubtitle      = $Result.HasEnglishSubtitle
        HasTextSubtitle         = $Result.HasTextSubtitle
        SidecarPath             = $Result.SidecarPath
        SidecarVersion          = $Result.SidecarVersion
        SidecarRoute            = $Result.SidecarRoute
        IssueCount              = $Result.Issues.Count
        IssueCodes              = @($Result.Issues | ForEach-Object { $_.Code })
        NonSidecarIssueCount    = $nonSidecarIssues.Count
        NonSidecarIssueCodes    = @($nonSidecarIssues | ForEach-Object { $_.Code })
        EffectiveBucket         = $effectiveBucket
        PriorityFixLevel        = $priorityFixLevel
        PriorityScore           = $priorityScore
        AuditIgnored            = [bool]$auditIgnored
        AuditIgnoreReason       = if ($auditIgnored -and $ignoreEntry.PSObject.Properties.Name -contains 'reason') { $ignoreEntry.reason } else { '' }
        AuditIgnoreSetAt        = if ($auditIgnored -and $ignoreEntry.PSObject.Properties.Name -contains 'set_at') { $ignoreEntry.set_at } else { '' }
        PrimaryIssueCode        = if ($primaryIssue) { $primaryIssue.Code } else { '' }
        PrimaryIssueBucket      = if ($primaryIssue) { $primaryIssue.Bucket } else { '' }
        PrimarySuggestedAction  = if ($primaryIssue) { $primaryIssue.SuggestedAction } else { '' }
        Issues                  = @($Result.Issues)
    }
}

function Write-TextReport {
    param(
        [string]$Path,
        [array]$Entries,
        [hashtable]$BucketCounts,
        [array]$IssueCountRows
    )

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('Media library audit summary')
    $lines.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    $lines.Add('')
    $lines.Add("Audit version       : $($script:AuditVersion)")
    $lines.Add("Library root        : $($script:LibraryRootResolved)")
    $lines.Add("Report root         : $($script:ReportRootResolved)")
    $lines.Add("Config path         : $(if ($script:ConfigPathResolved) { $script:ConfigPathResolved } else { '(none)' })")
    $lines.Add("ffprobe             : $($script:FfprobePath)")
    $lines.Add("Include sidecars    : $IncludeSidecars")
    $lines.Add("Min pipeline ver    : $($script:MinPipelineVersion)")
    $lines.Add("Files scanned       : $($Entries.Count)")
    $lines.Add('')
    $lines.Add('Bucket counts')
    $lines.Add('-------------')
    foreach ($bucket in @('OK','REVIEW','RERUN_PIPELINE','REDOWNLOAD_CANDIDATE')) {
        $lines.Add(('{0,-22}: {1}' -f $bucket, $BucketCounts[$bucket]))
    }

    if ($IssueCountRows.Count -gt 0) {
        $lines.Add('')
        $lines.Add('Top issue types')
        $lines.Add('---------------')
        foreach ($row in $IssueCountRows | Select-Object -First 20) {
            $lines.Add(('{0,-30}: {1}' -f $row.Code, $row.Count))
        }
    }

    $problemEntries = @($Entries | Where-Object { $_.Bucket -ne 'OK' } | Sort-Object @{ Expression = { Get-BucketRank $_.Bucket }; Descending = $true }, RelativePath)
    if ($problemEntries.Count -eq 0) {
        $lines.Add('')
        $lines.Add('No REVIEW / RERUN_PIPELINE / REDOWNLOAD_CANDIDATE items were found.')
    } else {
        $index = 0
        foreach ($entry in $problemEntries) {
            $index++
            $durationText = if ($entry.DurationSeconds -gt 0) { "{0:N2}s" -f $entry.DurationSeconds } else { 'unknown' }
            $videoText = if ($entry.VideoCodecs.Count -gt 0) { $entry.VideoCodecs -join ', ' } else { 'none' }
            $sidecarPathText = if ($entry.SidecarPath) { $entry.SidecarPath } else { '(not checked)' }
            $sidecarVersionText = if ($entry.SidecarVersion) { $entry.SidecarVersion } else { '(missing)' }
            $lines.Add('')
            $lines.Add(('{0}. {1}' -f $index, $entry.Path))
            $lines.Add(('{0,-15}: {1}' -f 'Bucket', $entry.Bucket))
            $lines.Add(('{0,-15}: {1}' -f 'Duration', $durationText))
            $lines.Add(('{0,-15}: {1}' -f 'Video', $videoText))
            $lines.Add(('{0,-15}: {1}/{2}' -f 'Default audio', $entry.DefaultAudioLanguage, $entry.DefaultAudioCodec))
            $lines.Add(('{0,-15}: {1}/{2}' -f 'Default subs', $entry.DefaultSubtitleLanguage, $entry.DefaultSubtitleCodec))
            if ($entry.Tx3gSubtitleCount -gt 0) {
                $lines.Add(('{0,-15}: {1} embedded, {2} matching SRT(s)' -f 'TX3G', $entry.Tx3gSubtitleCount, $entry.Tx3gExternalSrtCount))
            }
            if ($entry.BdpgsSubtitleCount -gt 0) {
                $lines.Add(('{0,-15}: {1} embedded, {2} OCR SRT record(s)' -f 'BDPGS', $entry.BdpgsSubtitleCount, $entry.BdpgsEmbeddedSrtCount))
            }
            if ($entry.VobSubSubtitleCount -gt 0) {
                $lines.Add(('{0,-15}: {1} embedded, {2} OCR SRT record(s)' -f 'VobSub', $entry.VobSubSubtitleCount, $entry.VobSubEmbeddedSrtCount))
            }
            if ($IncludeSidecars) {
                $lines.Add(('{0,-15}: {1}' -f 'Sidecar', $sidecarPathText))
                $lines.Add(('{0,-15}: {1}' -f 'Sidecar ver', $sidecarVersionText))
            }
            $lines.Add(('{0,-15}: {1}' -f 'Issues', $entry.IssueCount))
            foreach ($issue in $entry.Issues) {
                $lines.Add("  - [$($issue.Bucket)] [$($issue.Code)] $($issue.Message)")
                if ($issue.SuggestedAction) {
                    $lines.Add("    Action: $($issue.SuggestedAction)")
                }
            }
        }
    }

    Write-AtomicTextFile -Path $Path -Lines @($lines)
}

function New-AuditCsvRows {
    param([array]$Entries = @())

    $csvRows = $Entries | ForEach-Object {
        [pscustomobject]@{
            Bucket                  = $_.Bucket
            EffectiveBucket         = $_.EffectiveBucket
            PriorityFixLevel        = $_.PriorityFixLevel
            PriorityScore           = $_.PriorityScore
            AuditIgnored            = $_.AuditIgnored
            AuditIgnoreReason       = $_.AuditIgnoreReason
            AuditIgnoreSetAt        = $_.AuditIgnoreSetAt
            PrimaryIssueCode        = $_.PrimaryIssueCode
            PrimaryIssueBucket      = $_.PrimaryIssueBucket
            PrimarySuggestedAction  = $_.PrimarySuggestedAction
            MediaType               = $_.MediaType
            LookupTitle             = $_.LookupTitle
            RelativePath            = $_.RelativePath
            Path                    = $_.Path
            SizeGB                  = $_.SizeGB
            DurationSeconds         = $_.DurationSeconds
            VideoCodecs             = ($_.VideoCodecs -join '; ')
            AudioCodecs             = ($_.AudioCodecs -join '; ')
            SubtitleCodecs          = ($_.SubtitleCodecs -join '; ')
            Tx3gSubtitleCount       = $_.Tx3gSubtitleCount
            Tx3gEmbeddedSrtCount    = $_.Tx3gEmbeddedSrtCount
            Tx3gExternalSrtCount    = $_.Tx3gExternalSrtCount
            Tx3gExternalSrtFiles    = ($_.Tx3gExternalSrtFiles -join '; ')
            Tx3gSidecarSrtInvalidCount = $_.Tx3gSidecarSrtInvalidCount
            Tx3gSidecarFailureCount = $_.Tx3gSidecarFailureCount
            BdpgsSubtitleCount      = $_.BdpgsSubtitleCount
            BdpgsEmbeddedSrtCount   = $_.BdpgsEmbeddedSrtCount
            BdpgsEmbeddedSrtInvalidCount = $_.BdpgsEmbeddedSrtInvalidCount
            BdpgsSidecarFailureCount = $_.BdpgsSidecarFailureCount
            VobSubSubtitleCount     = $_.VobSubSubtitleCount
            VobSubEmbeddedSrtCount  = $_.VobSubEmbeddedSrtCount
            VobSubEmbeddedSrtInvalidCount = $_.VobSubEmbeddedSrtInvalidCount
            VobSubSidecarFailureCount = $_.VobSubSidecarFailureCount
            HasEnglishAudio         = $_.HasEnglishAudio
            HasEnglishSubtitle      = $_.HasEnglishSubtitle
            HasTextSubtitle         = $_.HasTextSubtitle
            DefaultAudioLanguage    = $_.DefaultAudioLanguage
            DefaultAudioCodec       = $_.DefaultAudioCodec
            DefaultSubtitleLanguage = $_.DefaultSubtitleLanguage
            DefaultSubtitleCodec    = $_.DefaultSubtitleCodec
            SidecarVersion          = $_.SidecarVersion
            SidecarRoute            = $_.SidecarRoute
            IssueCount              = $_.IssueCount
            NonSidecarIssueCount    = $_.NonSidecarIssueCount
            IssueCodes              = ($_.IssueCodes -join '; ')
            NonSidecarIssueCodes    = ($_.NonSidecarIssueCodes -join '; ')
            IssueMessages           = (($_.Issues | ForEach-Object { $_.Message }) -join ' | ')
        }
    }

    return @(
        $csvRows |
            Sort-Object `
                @{ Expression = { [int]$_.PriorityScore }; Descending = $true }, `
                @{ Expression = { Get-PriorityLevelRank $_.PriorityFixLevel }; Descending = $true }, `
                @{ Expression = { Get-BucketRank $_.EffectiveBucket }; Descending = $true }, `
                LookupTitle, `
                Path
    )
}

function New-AuditReportModel {
    param([array]$Results = @())

    $serializedResults = @($Results | ForEach-Object { Convert-ResultForSerialization -Result $_ })
    $bucketCounts = @{
        OK                    = @($serializedResults | Where-Object { $_.Bucket -eq 'OK' }).Count
        REVIEW                = @($serializedResults | Where-Object { $_.Bucket -eq 'REVIEW' }).Count
        RERUN_PIPELINE        = @($serializedResults | Where-Object { $_.Bucket -eq 'RERUN_PIPELINE' }).Count
        REDOWNLOAD_CANDIDATE  = @($serializedResults | Where-Object { $_.Bucket -eq 'REDOWNLOAD_CANDIDATE' }).Count
    }

    $issueCountRows = @(
        $serializedResults |
            ForEach-Object { $_.Issues } |
            Group-Object Code |
            Sort-Object -Property @{ Expression = { $_.Count }; Descending = $true }, @{ Expression = { $_.Name }; Descending = $false } |
            ForEach-Object {
                [pscustomobject]@{
                    Code  = $_.Name
                    Count = $_.Count
                }
            }
    )

    return [pscustomobject]@{
        Entries        = $serializedResults
        BucketCounts   = $bucketCounts
        IssueCountRows = $issueCountRows
    }
}

function Get-AuditCsvColumnNames {
    return @(
        'Bucket',
        'EffectiveBucket',
        'PriorityFixLevel',
        'PriorityScore',
        'AuditIgnored',
        'AuditIgnoreReason',
        'AuditIgnoreSetAt',
        'PrimaryIssueCode',
        'PrimaryIssueBucket',
        'PrimarySuggestedAction',
        'MediaType',
        'LookupTitle',
        'RelativePath',
        'Path',
        'SizeGB',
        'DurationSeconds',
        'VideoCodecs',
        'AudioCodecs',
        'SubtitleCodecs',
        'Tx3gSubtitleCount',
        'Tx3gEmbeddedSrtCount',
        'Tx3gExternalSrtCount',
        'Tx3gExternalSrtFiles',
        'Tx3gSidecarSrtInvalidCount',
        'Tx3gSidecarFailureCount',
        'BdpgsSubtitleCount',
        'BdpgsEmbeddedSrtCount',
        'BdpgsEmbeddedSrtInvalidCount',
        'BdpgsSidecarFailureCount',
        'VobSubSubtitleCount',
        'VobSubEmbeddedSrtCount',
        'VobSubEmbeddedSrtInvalidCount',
        'VobSubSidecarFailureCount',
        'HasEnglishAudio',
        'HasEnglishSubtitle',
        'HasTextSubtitle',
        'DefaultAudioLanguage',
        'DefaultAudioCodec',
        'DefaultSubtitleLanguage',
        'DefaultSubtitleCodec',
        'SidecarVersion',
        'SidecarRoute',
        'IssueCount',
        'NonSidecarIssueCount',
        'IssueCodes',
        'NonSidecarIssueCodes',
        'IssueMessages'
    )
}

function Write-AuditReportBundle {
    param(
        [array]$Results = @(),
        [bool]$EmitText = $false,
        [bool]$EmitJson = $true,
        [bool]$EmitCsv = $true
    )

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $baseReportPath = Join-Path $script:ReportRootResolved "audit_summary_$stamp"
    $txtPath = "$baseReportPath.txt"
    $jsonPath = "$baseReportPath.json"
    $csvPath = "$baseReportPath.csv"
    $priorityCsvPath = "$baseReportPath.priority.csv"
    $wrotePriorityCsv = $false
    $latestTextPath = ''
    $latestJsonPath = ''
    $latestCsvPath = ''
    $latestPriorityCsvPath = ''
    $reportSteps = @('classify', 'write_json', 'write_csv', 'write_priority_csv', 'write_text_summary')
    $writeReportProgress = {
        param(
            [string]$Stage,
            [int]$CompletedStepCount,
            [string]$Operation
        )
        $completed = @()
        $boundedCount = [math]::Max(0, [math]::Min([int]$CompletedStepCount, $reportSteps.Count))
        for ($i = 0; $i -lt $boundedCount; $i++) {
            $completed += $reportSteps[$i]
        }
        Write-AuditProgress `
            -Status 'writing-reports' `
            -ProcessedFiles $script:AuditProgressProcessed `
            -TotalFiles $script:AuditProgressTotal `
            -CurrentOperation $Operation `
            -LatestCsvPath $latestCsvPath `
            -LatestPriorityCsvPath $latestPriorityCsvPath `
            -LatestJsonPath $latestJsonPath `
            -LatestTextPath $latestTextPath `
            -ReportStage $Stage `
            -ReportStepIndex $boundedCount `
            -ReportStepTotal $reportSteps.Count `
            -ReportSteps $reportSteps `
            -ReportCompletedSteps $completed
    }

    & $writeReportProgress 'classify' 0 'Classifying audit results for report outputs.'
    $model = New-AuditReportModel -Results $Results

    if ($EmitJson) {
        & $writeReportProgress 'write_json' 1 'Writing JSON audit summary.'
        $jsonPayload = [pscustomobject]@{
            audit_version        = $script:AuditVersion
            generated_at         = (Get-Date -Format 'o')
            library_root         = $script:LibraryRootResolved
            report_root          = $script:ReportRootResolved
            config_path          = $script:ConfigPathResolved
            ffprobe_path         = $script:FfprobePath
            include_sidecars     = [bool]$IncludeSidecars
            min_pipeline_version = $script:MinPipelineVersion
            totals               = [pscustomobject]@{
                scanned              = $model.Entries.Count
                ok                   = $model.BucketCounts.OK
                review               = $model.BucketCounts.REVIEW
                rerun_pipeline       = $model.BucketCounts.RERUN_PIPELINE
                redownload_candidate = $model.BucketCounts.REDOWNLOAD_CANDIDATE
            }
            issue_counts         = $model.IssueCountRows
            entries              = $model.Entries
        }
        Write-AtomicJsonFile -Path $jsonPath -InputObject $jsonPayload -Depth 8
        $latestJsonPath = $jsonPath
        Write-AuditLog "Wrote JSON report  : $jsonPath"
    } else {
        & $writeReportProgress 'write_json' 1 'JSON audit summary disabled for this run.'
    }
    & $writeReportProgress 'write_csv' 2 'JSON audit summary step complete.'

    if ($EmitCsv) {
        & $writeReportProgress 'write_csv' 2 'Writing CSV audit summary.'
        $csvRows = New-AuditCsvRows -Entries $model.Entries
        Export-CsvAtomic -Path $csvPath -Rows $csvRows -Header (Get-AuditCsvColumnNames)
        $latestCsvPath = $csvPath
        Write-AuditLog "Wrote CSV report   : $csvPath"

        $priorityRows = @($csvRows | Where-Object { $_.PriorityFixLevel -in @('HIGH', 'MEDIUM') })
        & $writeReportProgress 'write_priority_csv' 3 'Evaluating priority CSV audit rows.'
        if ($priorityRows.Count -gt 0) {
            $priorityRows = @(
                $priorityRows |
                    Sort-Object `
                        @{ Expression = { [int]$_.PriorityScore }; Descending = $true }, `
                        @{ Expression = { Get-PriorityLevelRank $_.PriorityFixLevel }; Descending = $true }, `
                        @{ Expression = { Get-BucketRank $_.EffectiveBucket }; Descending = $true }, `
                        LookupTitle, `
                        Path
            )
            Export-CsvAtomic -Path $priorityCsvPath -Rows $priorityRows -Header (Get-AuditCsvColumnNames)
            $wrotePriorityCsv = $true
            $latestPriorityCsvPath = $priorityCsvPath
            Write-AuditLog "Wrote priority CSV : $priorityCsvPath"
        }
    } else {
        & $writeReportProgress 'write_csv' 2 'CSV audit summary disabled for this run.'
        & $writeReportProgress 'write_priority_csv' 3 'Priority CSV disabled because CSV output is disabled.'
    }
    & $writeReportProgress 'write_text_summary' 4 'Priority CSV step complete.'

    if ($EmitText) {
        & $writeReportProgress 'write_text_summary' 4 'Writing text audit summary.'
        Write-TextReport -Path $txtPath -Entries $model.Entries -BucketCounts $model.BucketCounts -IssueCountRows $model.IssueCountRows
        $latestTextPath = $txtPath
        Write-AuditLog "Wrote text report  : $txtPath"
    } else {
        & $writeReportProgress 'write_text_summary' 4 'Text audit summary disabled for this run.'
    }
    & $writeReportProgress 'complete' 5 'Audit report generation complete.'

    return [pscustomobject]@{
        Entries              = $model.Entries
        BucketCounts         = $model.BucketCounts
        IssueCountRows       = $model.IssueCountRows
        TextPath             = if ($EmitText) { $txtPath } else { '' }
        JsonPath             = if ($EmitJson) { $jsonPath } else { '' }
        CsvPath              = if ($EmitCsv) { $csvPath } else { '' }
        PriorityCsvPath      = if ($wrotePriorityCsv) { $priorityCsvPath } else { '' }
        WroteText            = [bool]$EmitText
        WroteJson            = [bool]$EmitJson
        WroteCsv             = [bool]$EmitCsv
        WrotePriorityCsv     = [bool]$wrotePriorityCsv
    }
}

