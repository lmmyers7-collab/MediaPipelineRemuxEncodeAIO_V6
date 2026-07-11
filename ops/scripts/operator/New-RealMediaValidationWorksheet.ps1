[CmdletBinding(SupportsShouldProcess = $true, PositionalBinding = $false)]
param(
    [string]$OutputDirectory,
    [string]$RunId,
    [string]$Operator = "",
    [ValidateSet("ApiAndBrowser", "WebView preview", "Tauri WebView2 shell", "Tauri preview")]
    [string]$Shell = "ApiAndBrowser",
    [string[]]$SamplePath = @(),
    [string[]]$SampleCategory = @(),
    [string[]]$ExpectedRoute = @(),
    [string]$QueueSnapshotPath = "",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AdditionalSamplePath = @(),
    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function ConvertTo-MarkdownCell {
    param([AllowNull()][object]$Value)
    if ($null -eq $Value) { return "" }
    $text = [string]$Value
    return (($text -replace '\r?\n', '<br>') -replace '\|', '\|').Trim()
}

function Get-IndexedValue {
    param(
        [AllowNull()][object[]]$Values,
        [int]$Index
    )

    if ($null -eq $Values) { return "" }
    if ($Index -lt 0 -or $Index -ge $Values.Count) { return "" }
    if ($null -eq $Values[$Index]) { return "" }
    return ([string]$Values[$Index]).Trim()
}

function Expand-ListValues {
    param([AllowNull()][object[]]$Values)

    $expanded = [System.Collections.Generic.List[string]]::new()
    foreach ($item in @($Values)) {
        if ($null -eq $item) { continue }
        foreach ($part in (([string]$item) -split ',')) {
            $text = $part.Trim()
            if ($text) { $expanded.Add($text) }
        }
    }
    return $expanded.ToArray()
}

function Get-ObjectPropertyValue {
    param(
        [AllowNull()][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][object]$Default = ""
    )

    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if (-not $property -or $null -eq $property.Value) { return $Default }
    return $property.Value
}

function Test-PathTextEqual {
    param(
        [AllowNull()][object]$Left,
        [AllowNull()][object]$Right
    )

    if ($null -eq $Left -or $null -eq $Right) { return $false }
    $leftText = ([string]$Left).Trim()
    $rightText = ([string]$Right).Trim()
    if (-not $leftText -or -not $rightText) { return $false }
    return $leftText.Equals($rightText, [System.StringComparison]::OrdinalIgnoreCase)
}

function Read-QueueSnapshotEvidence {
    param([string]$Path)

    if (-not $Path) {
        return [pscustomobject]@{
            provided = $false
            path = ""
            produced_at = ""
            rows = @()
        }
    }

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Queue snapshot path was provided but not found: $fullPath"
    }

    $payload = Get-Content -LiteralPath $fullPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
    return [pscustomobject]@{
        provided = $true
        path = $fullPath
        produced_at = [string](Get-ObjectPropertyValue -Object $payload -Name 'produced_at')
        rows = @(Get-ObjectPropertyValue -Object $payload -Name 'rows' -Default @())
    }
}

function Find-QueueSnapshotRow {
    param(
        [object[]]$Rows,
        [string]$SamplePath
    )

    foreach ($row in @($Rows)) {
        if (Test-PathTextEqual -Left (Get-ObjectPropertyValue -Object $row -Name 'source_path') -Right $SamplePath) {
            return $row
        }
        if (Test-PathTextEqual -Left (Get-ObjectPropertyValue -Object $row -Name 'relative_path') -Right $SamplePath) {
            return $row
        }
    }
    return $null
}

function Format-QueueBlockedValue {
    param([AllowNull()][object]$Row)

    if ($null -eq $Row) { return "" }
    $blockedReason = [string](Get-ObjectPropertyValue -Object $Row -Name 'blocked_reason')
    if ($blockedReason) { return "Yes - $blockedReason" }
    return "No"
}

function Format-QueueExcludedValue {
    param([AllowNull()][object]$Row)

    if ($null -eq $Row) { return "" }
    $excluded = Get-ObjectPropertyValue -Object $Row -Name 'excluded' -Default $null
    $isExcluded = Get-ObjectPropertyValue -Object $Row -Name 'is_excluded' -Default $null
    $excludedReason = [string](Get-ObjectPropertyValue -Object $Row -Name 'excluded_reason')
    if ($excluded -eq $true -or $isExcluded -eq $true) {
        if ($excludedReason) { return "Yes - $excludedReason" }
        return "Yes"
    }
    if ($excludedReason) { return "Yes - $excludedReason" }
    return "No"
}

function New-QueueEvidenceRows {
    param(
        [string[]]$Paths,
        [object]$QueueSnapshot
    )

    $rows = [System.Collections.Generic.List[string]]::new()
    $count = [Math]::Max(3, $Paths.Count)
    for ($index = 0; $index -lt $count; $index++) {
        $number = $index + 1
        $samplePath = if ($index -lt $Paths.Count) { $Paths[$index] } else { "" }
        $queueRow = if ($samplePath -and $QueueSnapshot.provided) {
            Find-QueueSnapshotRow -Rows @($QueueSnapshot.rows) -SamplePath $samplePath
        } else {
            $null
        }
        $route = [string](Get-ObjectPropertyValue -Object $queueRow -Name 'route')
        $reason = [string](Get-ObjectPropertyValue -Object $queueRow -Name 'route_reason')
        $reasonCode = [string](Get-ObjectPropertyValue -Object $queueRow -Name 'route_reason_code')
        if ($reasonCode) {
            $reason = if ($reason) { "$reason ($reasonCode)" } else { $reasonCode }
        }
        $blocked = Format-QueueBlockedValue -Row $queueRow
        $excluded = Format-QueueExcludedValue -Row $queueRow
        $sourceRoot = [string](Get-ObjectPropertyValue -Object $queueRow -Name 'root_path')
        $rows.Add("| $number | $(ConvertTo-MarkdownCell $route) | $(ConvertTo-MarkdownCell $reason) | $(ConvertTo-MarkdownCell $blocked) | $(ConvertTo-MarkdownCell $excluded) | $(ConvertTo-MarkdownCell $sourceRoot) |")
    }
    return ($rows -join [Environment]::NewLine)
}

function Get-QueueSnapshotMatchCount {
    param(
        [string[]]$Paths,
        [object]$QueueSnapshot
    )

    if (-not $QueueSnapshot.provided) { return 0 }
    $matches = 0
    foreach ($path in @($Paths)) {
        if ($path -and (Find-QueueSnapshotRow -Rows @($QueueSnapshot.rows) -SamplePath $path)) {
            $matches++
        }
    }
    return $matches
}

function Format-QueueSnapshotAgeLine {
    param([object]$QueueSnapshot)

    if (-not $QueueSnapshot.provided) { return "not provided" }
    $producedAt = [string]$QueueSnapshot.produced_at
    if (-not $producedAt) { return "unknown; source $($QueueSnapshot.path)" }
    try {
        $produced = [DateTimeOffset]::Parse($producedAt)
        $age = [DateTimeOffset]::Now - $produced
        return ("produced {0}; age {1:N1} hours; source {2}" -f $produced.ToString('o'), $age.TotalHours, $QueueSnapshot.path)
    } catch {
        return "produced $producedAt; source $($QueueSnapshot.path)"
    }
}

function Set-QueueEvidenceTable {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [string[]]$Paths,
        [object]$QueueSnapshot
    )

    $rows = New-QueueEvidenceRows -Paths $Paths -QueueSnapshot $QueueSnapshot
    $replacement = "| Sample # | Route shown | Route reason | Blocked? | Excluded? | Source root |`r`n|---|---|---|---|---|---|`r`n$rows"
    return [regex]::Replace(
        $Text,
        "(?s)\| Sample # \| Route shown \| Route reason \| Blocked\? \| Excluded\? \| Source root \|\r?\n\|---\|---\|---\|---\|---\|---\|\r?\n(?:\| \d+ \|.*?\|\r?\n)+",
        $replacement + [Environment]::NewLine,
        1
    )
}

function Set-QueueSnapshotLines {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [string[]]$Paths,
        [object]$QueueSnapshot
    )

    $matchCount = Get-QueueSnapshotMatchCount -Paths $Paths -QueueSnapshot $QueueSnapshot
    $expectedCount = @($Paths | Where-Object { $_ }).Count
    $matchText = if (-not $QueueSnapshot.provided) {
        "not captured"
    } elseif ($expectedCount -gt 0 -and $matchCount -eq $expectedCount) {
        "Yes ($matchCount/$expectedCount)"
    } else {
        "No ($matchCount/$expectedCount)"
    }

    $updated = $Text.Replace("Queue snapshot age: _______________", "Queue snapshot age: $(Format-QueueSnapshotAgeLine -QueueSnapshot $QueueSnapshot)")
    return $updated.Replace("Snapshot still matches expected source files: Yes / No", "Snapshot still matches expected source files: $matchText")
}

function New-SampleBatchRows {
    param(
        [string[]]$Paths,
        [string[]]$Categories,
        [string[]]$Routes
    )

    $rows = [System.Collections.Generic.List[string]]::new()
    $count = [Math]::Max(3, $Paths.Count)
    for ($index = 0; $index -lt $count; $index++) {
        $number = $index + 1
        $path = if ($index -lt $Paths.Count) { $Paths[$index] } else { "" }
        $category = Get-IndexedValue -Values $Categories -Index $index
        $route = Get-IndexedValue -Values $Routes -Index $index
        $rows.Add("| $number | $(ConvertTo-MarkdownCell $path) | $(ConvertTo-MarkdownCell $category) | $(ConvertTo-MarkdownCell $route) |")
    }
    return ($rows -join [Environment]::NewLine)
}

function New-PilotEvidencePacketRows {
    param([string[]]$Paths)

    $rows = [System.Collections.Generic.List[string]]::new()
    $count = [Math]::Max(3, $Paths.Count)
    for ($index = 0; $index -lt $count; $index++) {
        $number = $index + 1
        $path = if ($index -lt $Paths.Count) { Split-Path -Leaf $Paths[$index] } else { "" }
        $rows.Add("| $number | $(ConvertTo-MarkdownCell $path) |  |  |  |  |  |  | |")
    }
    return ($rows -join [Environment]::NewLine)
}

function New-SamplePlanObjects {
    param(
        [string[]]$Paths,
        [string[]]$Categories,
        [string[]]$Routes
    )

    $samples = [System.Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $Paths.Count; $index++) {
        $samples.Add([ordered]@{
            index = $index + 1
            source_path = $Paths[$index]
            category = Get-IndexedValue -Values $Categories -Index $index
            expected_route = Get-IndexedValue -Values $Routes -Index $index
        })
    }
    return $samples.ToArray()
}

function Set-TemplateLineValue {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Field,
        [AllowNull()][object]$Value
    )

    $escapedField = [regex]::Escape($Field)
    $valueText = ConvertTo-MarkdownCell $Value
    return [regex]::Replace($Text, "(?m)^\| $escapedField \|.*\|(?=\r?$)", "| $Field | $valueText |", 1)
}

function Set-SampleBatchTable {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [string[]]$Paths,
        [string[]]$Categories,
        [string[]]$Routes
    )

    $rows = New-SampleBatchRows -Paths $Paths -Categories $Categories -Routes $Routes
    $replacement = "| # | Source file | Category | Expected route |`r`n|---|---|---|---|`r`n$rows"
    return [regex]::Replace(
        $Text,
        "(?s)\| # \| Source file \| Category \| Expected route \|\r?\n\|---\|---\|---\|---\|\r?\n(?:\| \d+ \|.*?\|\r?\n)+",
        $replacement + [Environment]::NewLine,
        1
    )
}

function Set-PilotEvidencePacketTable {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [string[]]$Paths
    )

    $rows = New-PilotEvidencePacketRows -Paths $Paths
    $replacement = "| Sample # | Sample label | Packet status | Queue route proof | Completed output/sidecar proof | Diagnostics/run-log proof | Pending Publish posture | Playback/subtitle/audio/size proof | Stop condition hit? |`r`n|---|---|---|---|---|---|---|---|---|`r`n$rows"
    return [regex]::Replace(
        $Text,
        "(?s)\| Sample # \| Sample label \| Packet status \| Queue route proof \| Completed output/sidecar proof \| Diagnostics/run-log proof \| Pending Publish posture \| Playback/subtitle/audio/size proof \| Stop condition hit\? \|\r?\n\|---\|---\|---\|---\|---\|---\|---\|---\|---\|\r?\n(?:\| \d+ \|.*?\|\r?\n)+",
        $replacement + [Environment]::NewLine,
        1
    )
}

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$projectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))))
$templateCandidates = @(
    (Join-Path $projectRoot 'docs\sample-validation\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md'),
    (Join-Path $projectRoot 'docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md')
)
$templatePath = @($templateCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1)[0]

if (-not $templatePath) {
    throw "Real-media validation evidence template was not found. Checked: $($templateCandidates -join '; ')"
}

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot 'docs\RealMediaValidationRuns'
}
$outputDirectoryFull = [System.IO.Path]::GetFullPath($OutputDirectory)

if (-not $RunId) {
    $RunId = Get-Date -Format 'yyyyMMdd_HHmmss'
}
$safeRunId = ($RunId -replace '[^A-Za-z0-9_.-]', '_').Trim(' ', '.', '_')
if (-not $safeRunId) {
    throw 'RunId must contain at least one filename-safe character.'
}

$targetPath = Join-Path $outputDirectoryFull ("real_media_validation_{0}.md" -f $safeRunId)
$now = Get-Date
$additionalSamplePathsClean = [System.Collections.Generic.List[string]]::new()
$additionalCategories = [System.Collections.Generic.List[string]]::new()
$additionalRoutes = [System.Collections.Generic.List[string]]::new()
$remainingMode = 'sample'
$effectivePlanOnly = [bool]$PlanOnly
foreach ($item in @($AdditionalSamplePath)) {
    if ($null -eq $item) { continue }
    $text = ([string]$item).Trim()
    if (-not $text) { continue }
    if ($text -eq '-SampleCategory') {
        $remainingMode = 'category'
        continue
    }
    if ($text -eq '-ExpectedRoute') {
        $remainingMode = 'route'
        continue
    }
    if ($text -eq '-PlanOnly') {
        $effectivePlanOnly = $true
        $remainingMode = 'sample'
        continue
    }
    if ($remainingMode -eq 'category') {
        $additionalCategories.Add($text)
    } elseif ($remainingMode -eq 'route') {
        $additionalRoutes.Add($text)
    } else {
        $additionalSamplePathsClean.Add($text)
    }
}

$samplePaths = @($SamplePath + $additionalSamplePathsClean.ToArray() | Where-Object { $_ -and $_.Trim() } | ForEach-Object { $_.Trim() })
$sampleCategories = @(Expand-ListValues -Values @($SampleCategory + $additionalCategories.ToArray()))
$expectedRoutes = @(Expand-ListValues -Values @($ExpectedRoute + $additionalRoutes.ToArray()))
$queueSnapshot = Read-QueueSnapshotEvidence -Path $QueueSnapshotPath

$template = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8
$body = $template
$body = Set-TemplateLineValue -Text $body -Field 'Date / Time' -Value $now.ToString('o')
$body = Set-TemplateLineValue -Text $body -Field 'Operator' -Value $Operator
$body = Set-TemplateLineValue -Text $body -Field 'Machine' -Value $env:COMPUTERNAME
$body = Set-TemplateLineValue -Text $body -Field 'Workspace path' -Value $projectRoot
$body = Set-TemplateLineValue -Text $body -Field 'Launch surface' -Value $Shell
$body = Set-SampleBatchTable -Text $body -Paths $samplePaths -Categories $sampleCategories -Routes $expectedRoutes
$body = Set-PilotEvidencePacketTable -Text $body -Paths $samplePaths
$body = Set-QueueEvidenceTable -Text $body -Paths $samplePaths -QueueSnapshot $queueSnapshot
$body = Set-QueueSnapshotLines -Text $body -Paths $samplePaths -QueueSnapshot $queueSnapshot

$header = @"
<!--
Generated by New-RealMediaValidationWorksheet.ps1.
Boundary: this worksheet generator writes Markdown evidence only.
It does not launch the app, process media, probe FFmpeg, rename files, save settings, publish outputs, drain pending publish, mutate queue state, or touch source/output/scratch media.
-->

"@

$commands = @'

---

## Copyable Validation Commands

Run these from the workspace root as appropriate. These commands are validation gates only; they do not replace the real-media sample run evidence above.

```powershell
.\ops/scripts/smoke\Test-WebViewRealMediaEvidenceSmoke.ps1
.\ops/scripts/smoke\Test-WebViewCommandEvidenceSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRenameReadinessSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserHighRiskSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserCompletedPendingProofSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserLargeTableSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserRenameSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserSettingsLaunchSmoke.ps1
.\ops\scripts\release\test.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Record skipped browser smokes as environment skips, not proof. Real-media proof still requires matching Queue, Completed, Diagnostics, Pending Publish, subtitle, audio, size, and output evidence for the sample files.
'@

$content = $header + $body.TrimEnd() + $commands

$summary = [ordered]@{
    schema = 'real_media_validation_worksheet_plan.v1'
    run_id = $safeRunId
    output_path = $targetPath
    output_directory = $outputDirectoryFull
    template_path = $templatePath
    queue_snapshot_path = if ($queueSnapshot.provided) { $queueSnapshot.path } else { "" }
    queue_snapshot_rows = @($queueSnapshot.rows).Count
    queue_snapshot_sample_matches = Get-QueueSnapshotMatchCount -Paths $samplePaths -QueueSnapshot $queueSnapshot
    sample_count = $samplePaths.Count
    samples = @(New-SamplePlanObjects -Paths $samplePaths -Categories $sampleCategories -Routes $expectedRoutes)
    shell = $Shell
    plan_only = [bool]$effectivePlanOnly
    boundary = 'Markdown evidence worksheet only; does not process media or mutate source/output/scratch paths.'
}

if ($effectivePlanOnly) {
    $summary | ConvertTo-Json -Depth 4
    return
}

if ($PSCmdlet.ShouldProcess($targetPath, 'Create real-media validation worksheet')) {
    New-Item -ItemType Directory -Path $outputDirectoryFull -Force | Out-Null
    $tempPath = Join-Path $outputDirectoryFull (".{0}.tmp" -f ([System.IO.Path]::GetFileName($targetPath)))
    Set-Content -LiteralPath $tempPath -Value $content -Encoding UTF8
    Move-Item -LiteralPath $tempPath -Destination $targetPath -Force
    $summary | ConvertTo-Json -Depth 4
}
