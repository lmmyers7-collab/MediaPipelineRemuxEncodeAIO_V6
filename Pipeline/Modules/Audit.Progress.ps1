# Audit progress and UI-facing status helpers.

function Write-AuditProgress {
    param(
        [string]$Status,
        [int]$ProcessedFiles = 0,
        [int]$TotalFiles = 0,
        [string]$CurrentFile = '',
        [string]$CurrentOperation = '',
        [bool]$Completed = $false,
        [bool]$Failed = $false,
        [string]$LatestCsvPath = '',
        [string]$LatestPriorityCsvPath = '',
        [string]$LatestJsonPath = '',
        [string]$LatestTextPath = '',
        [string]$ReportStage = '',
        [int]$ReportStepIndex = 0,
        [int]$ReportStepTotal = 0,
        [string[]]$ReportSteps = @(),
        [string[]]$ReportCompletedSteps = @()
    )

    if (-not $script:AuditProgressPath) { return }

    $nowUtc = [datetime]::UtcNow
    if (-not $Completed -and -not $Failed -and $Status -eq 'scanning') {
        $lastWriteUtc = $script:AuditProgressLastWriteUtc
        $lastProcessed = [int]$script:AuditProgressLastProcessed
        $fileDelta = [math]::Abs($ProcessedFiles - $lastProcessed)
        $elapsedMs = if ($lastWriteUtc) { ($nowUtc - $lastWriteUtc).TotalMilliseconds } else { [double]::PositiveInfinity }
        $isFirstTick = ($lastProcessed -lt 0)
        $isFinalScanTick = ($TotalFiles -gt 0 -and $ProcessedFiles -ge ($TotalFiles - 1))
        if (-not $isFirstTick -and -not $isFinalScanTick -and $fileDelta -lt $script:AuditProgressMinFileDelta -and $elapsedMs -lt $script:AuditProgressMinIntervalMs) {
            return
        }
    }

    $percent = if ($TotalFiles -gt 0) {
        [math]::Max(0, [math]::Min(100, [int](($ProcessedFiles / $TotalFiles) * 100)))
    } elseif ($Completed) {
        100
    } else {
        0
    }

    $effectiveReportStage = if (-not [string]::IsNullOrWhiteSpace($ReportStage)) { $ReportStage } else { [string]$script:AuditReportStage }
    $effectiveReportStepTotal = if ($ReportStepTotal -gt 0) { [int]$ReportStepTotal } else { [int]$script:AuditReportStepTotal }
    $effectiveReportStepIndex = if ($ReportStepIndex -gt 0) { [int]$ReportStepIndex } else { [int]$script:AuditReportStepIndex }
    $effectiveReportSteps = if (@($ReportSteps).Count -gt 0) { @($ReportSteps) } elseif ($script:AuditReportSteps) { @($script:AuditReportSteps) } else { @() }
    $effectiveReportCompletedSteps = if (@($ReportCompletedSteps).Count -gt 0) { @($ReportCompletedSteps) } elseif ($script:AuditReportCompletedSteps) { @($script:AuditReportCompletedSteps) } else { @() }
    if ($effectiveReportStepTotal -gt 0) {
        $effectiveReportStepIndex = [math]::Max(0, [math]::Min($effectiveReportStepIndex, $effectiveReportStepTotal))
    }
    $script:AuditReportStage = $effectiveReportStage
    $script:AuditReportStepIndex = $effectiveReportStepIndex
    $script:AuditReportStepTotal = $effectiveReportStepTotal
    $script:AuditReportSteps = @($effectiveReportSteps)
    $script:AuditReportCompletedSteps = @($effectiveReportCompletedSteps)

    $payload = [pscustomobject]@{
        audit_version            = $script:AuditVersion
        started_at               = $script:AuditStartedAt
        last_update              = $nowUtc.ToString('o')
        status                   = $Status
        completed                = [bool]$Completed
        failed                   = [bool]$Failed
        processed_files          = [int]$ProcessedFiles
        total_files              = [int]$TotalFiles
        percent_complete         = [int]$percent
        current_file             = $CurrentFile
        current_operation        = $CurrentOperation
        library_root             = $script:LibraryRootResolved
        report_root              = $script:ReportRootResolved
        include_sidecars         = [bool]$IncludeSidecars
        progress_persistence_healthy = [bool]$script:AuditProgressPersistenceHealthy
        progress_write_failures  = [int]$script:AuditProgressWriteFailures
        latest_csv_path          = $LatestCsvPath
        latest_priority_csv_path = $LatestPriorityCsvPath
        latest_json_path         = $LatestJsonPath
        latest_text_path         = $LatestTextPath
        report_stage             = $effectiveReportStage
        report_step_index        = [int]$effectiveReportStepIndex
        report_step_total        = [int]$effectiveReportStepTotal
        report_steps             = @($effectiveReportSteps)
        report_completed_steps   = @($effectiveReportCompletedSteps)
    }

    try {
        Write-AtomicJsonFile -Path $script:AuditProgressPath -InputObject $payload -Depth 6
        $script:AuditProgressLastWriteUtc = $nowUtc
        $script:AuditProgressLastProcessed = [int]$ProcessedFiles
        $script:AuditProgressWriteFailures = 0
        $script:AuditProgressPersistenceHealthy = $true
        return
    } catch {
        $script:AuditProgressWriteFailures++
        $script:AuditProgressPersistenceHealthy = $false
        try {
            Write-AuditLog "Failed to update audit progress: $($_.Exception.Message)" 'WARN'
        } catch {}
        return
    }
}

function Test-AuditProgressPersistence {
    if (-not $script:AuditProgressPath) { return $false }
    try {
        $progressDir = Split-Path -Parent $script:AuditProgressPath
        if (-not [string]::IsNullOrWhiteSpace($progressDir) -and -not (Test-Path -LiteralPath $progressDir)) {
            New-Item -ItemType Directory -Path $progressDir -Force | Out-Null
        }
        $probe = Join-Path $progressDir ("audit_progress.probe." + [guid]::NewGuid().ToString("N") + ".json")
        $payload = @{ probe = $true; at = (Get-Date -Format 'o') } | ConvertTo-Json -Compress
        [System.IO.File]::WriteAllText($probe, $payload, [System.Text.UTF8Encoding]::new($false))
        $roundTrip = Get-Content -LiteralPath $probe -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        if (-not $roundTrip.probe) { throw "audit progress probe round-trip failed" }
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        $script:AuditProgressPersistenceHealthy = $true
        $script:AuditProgressWriteFailures = 0
        return $true
    } catch {
        $script:AuditProgressPersistenceHealthy = $false
        $script:AuditProgressWriteFailures++
        Write-AuditLog "Audit progress persistence probe failed: $($_.Exception.Message)" 'WARN'
        return $false
    }
}

function Write-AuditScanProgress {
    param(
        [Parameter(Mandatory)] [int]$Index,
        [Parameter(Mandatory)] [int]$Total,
        [Parameter(Mandatory)] $FileInfo
    )

    $percent = if ($Total -gt 0) { [int](($Index / $Total) * 100) } else { 100 }
    Write-Progress -Activity 'Audit Media Library' -Status "$Index / $Total" -PercentComplete $percent -CurrentOperation $FileInfo.FullName
    Write-AuditProgress -Status 'scanning' -ProcessedFiles ($Index - 1) -TotalFiles $Total -CurrentFile $FileInfo.FullName -CurrentOperation "Scanning $Index / $Total"
}

function Complete-AuditConsoleProgress {
    Write-Progress -Activity 'Audit Media Library' -Completed
}

