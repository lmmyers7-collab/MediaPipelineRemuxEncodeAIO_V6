[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Rerun PlanOnly checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$rerunScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Invoke-RerunCsv.ps1'

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-False {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if ($Condition) { throw $Message }
}

function Assert-Match {
    param(
        [string] $Text,
        [string] $Pattern,
        [string] $Message
    )
    if ($Text -notmatch $Pattern) { throw $Message }
}

Assert-True (Test-Path -LiteralPath $rerunScript -PathType Leaf) "Rerun script missing: $rerunScript"

$rerunScriptText = Get-Content -LiteralPath $rerunScript -Raw
Assert-Match $rerunScriptText "planned output was not produced" 'Missing planned output check is missing.'
Assert-Match $rerunScriptText "planned output is empty" 'Empty planned output check is missing.'
Assert-False ($rerunScriptText -match "(?s)`$plan\.status = 'parked'\s+`$plan\.reason = `"planned output was not produced`"") 'Missing planned output must not be classified as parked.'
Assert-False ($rerunScriptText -match "(?s)`$plan\.status = 'parked'\s+`$plan\.reason = `"planned output is empty`"") 'Empty planned output must not be classified as parked.'
Assert-True ($rerunScriptText.Contains('if ($pipelineExitFailures -gt 0 -or $failed -gt 0) { exit 1 }')) 'Rerun process exit must fail when failed rows remain.'
Assert-Match $rerunScriptText 'function Resolve-RerunSourcePath' 'CSV source path resolver is missing.'
Assert-Match $rerunScriptText 'function Test-RerunSourcePathFullyQualified' 'CSV source path absolute-path guard is missing.'
Assert-Match $rerunScriptText 'relative source_path:' 'Relative CSV source_path failure text is missing.'
Assert-Match $rerunScriptText 'invalid media extension:' 'Invalid CSV source extension failure text is missing.'
Assert-Match $rerunScriptText 'auto_replace_clean_else_pending_review' 'Auto replace clean else pending review destination mode is missing.'
Assert-Match $rerunScriptText 'function Get-RerunAutoReviewIssues' 'Auto destination review classifier is missing.'
Assert-Match $rerunScriptText 'function Publish-RerunReplaceFinal' 'Final replacement helper is missing.'
Assert-Match $rerunScriptText 'function Publish-RerunPipelineSidecarToFinal' 'Final replacement sidecar publish helper is missing.'
Assert-Match $rerunScriptText 'function Get-RerunEffectiveFinalOutputRoot' 'Rerun final output root resolver is missing.'
Assert-Match $rerunScriptText 'final output destination.*outside configured output root' 'Rerun final output root violation guard is missing.'
Assert-Match $rerunScriptText '\[''DeferredPublish''\] = \$false' 'Rerun temp config must force DeferredPublish false.'
Assert-Match $rerunScriptText 'rerun_csv_auto_pending_review' 'Auto destination Pending Publish review reason code is missing.'
Assert-Match $rerunScriptText 'CSV rerun selected path:' 'CSV rerun selected path log line is missing.'
Assert-Match $rerunScriptText 'CSV rerun evidence:' 'CSV rerun evidence log line is missing.'
Assert-Match $rerunScriptText 'Rerun batch complete: csv=' 'CSV rerun completion log line does not include the selected CSV path.'

$pwshHost = (Get-Process -Id $PID).Path
if (-not $pwshHost) { $pwshHost = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source }
if (-not $pwshHost) { $pwshHost = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
Assert-True (-not [string]::IsNullOrWhiteSpace($pwshHost)) 'PowerShell host path is required for child-process rerun checks.'

function Invoke-RerunPlanOnlyCase {
    param(
        [string] $CsvPath,
        [string] $ConfigPath,
        [string] $DefaultReturnMode = 'park',
        [string] $DestinationMode = 'review_workspace',
        [string] $CollisionPolicy = 'suffix',
        [switch] $ConfirmReplaceFinal,
        [switch] $ConfirmSourceOverwrite,
        [string[]] $ExtraArgs = @()
    )
    $argsList = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $rerunScript,
        '-CsvPath', $CsvPath,
        '-ConfigPath', $ConfigPath,
        '-PlanOnly',
        '-DefaultReturnMode', $DefaultReturnMode,
        '-DestinationMode', $DestinationMode,
        '-CollisionPolicy', $CollisionPolicy
    )
    if ($ConfirmReplaceFinal) { $argsList += '-ConfirmReplaceFinal' }
    if ($ConfirmSourceOverwrite) { $argsList += '-ConfirmSourceOverwrite' }
    $argsList += @($ExtraArgs)
    $output = & $pwshHost @argsList *>&1 | Out-String
    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = $output
    }
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-rerun-planonly-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $source = Join-Path $root 'Movie Source 1080p HEVC.mkv'
    Set-Content -LiteralPath $source -Value 'media' -Encoding ASCII

    $config = Join-Path $root 'config.psd1'
    $escapedRoot = $root.Replace("'", "''")
    @"
@{
    LocalBase = '$escapedRoot\Local'
    Outsource = '$escapedRoot\Out'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
}
"@ | Set-Content -LiteralPath $config -Encoding UTF8

    $csv = Join-Path $root 'rerun.csv'
    @"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,"$source",Movie,copy,keep,park
"@ | Set-Content -LiteralPath $csv -Encoding UTF8

    $result = Invoke-RerunPlanOnlyCase -CsvPath $csv -ConfigPath $config
    $output = $result.Output
    if ($result.ExitCode -ne 0) { throw "Rerun PlanOnly check failed with exit $($result.ExitCode). Output: $output" }

    Assert-Match $output ([regex]::Escape("CSV rerun request: csv_path=$csv")) 'PlanOnly did not log the requested CSV path.'
    Assert-Match $output ([regex]::Escape("CSV rerun selected path: $csv")) 'PlanOnly did not log the resolved selected CSV path.'
    Assert-Match $output 'CSV rerun evidence: batch=rerun_.*manifest=.*RerunManifests.*workspace=.*Local_RerunWorkspace.*destination=review_workspace collision=suffix execution=one_at_a_time window=1 dry_run=False plan_only=True' 'PlanOnly did not log the rerun evidence summary.'
    Assert-True ($output -match 'PLAN ONLY complete') 'PlanOnly did not report a plan-only completion.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local') -PathType Container) 'PlanOnly created LocalBase.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Out') -PathType Container) 'PlanOnly created Outsource.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunManifests') -PathType Container) 'PlanOnly created RerunManifests.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunQueue') -PathType Container) 'PlanOnly created RerunQueue.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunParked') -PathType Container) 'PlanOnly created RerunParked.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local_RerunWorkspace') -PathType Container) 'PlanOnly created the isolated rerun workspace.'

    $autoResult = Invoke-RerunPlanOnlyCase -CsvPath $csv -ConfigPath $config -DefaultReturnMode 'replace_original' -DestinationMode 'auto_replace_clean_else_pending_review' -CollisionPolicy 'replace_final' -ConfirmReplaceFinal
    $autoOutput = $autoResult.Output
    if ($autoResult.ExitCode -ne 0) { throw "Auto destination PlanOnly check failed with exit $($autoResult.ExitCode). Output: $autoOutput" }
    Assert-Match $autoOutput 'CSV rerun evidence: batch=rerun_.*destination=auto_replace_clean_else_pending_review collision=replace_final execution=one_at_a_time window=1 dry_run=False plan_only=True' 'Auto destination PlanOnly did not log the strict default destination evidence summary.'
    Assert-True ($autoOutput -match 'PLAN ONLY complete') 'Auto destination PlanOnly did not report a plan-only completion.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local') -PathType Container) 'Auto destination PlanOnly created LocalBase.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Out') -PathType Container) 'Auto destination PlanOnly created Outsource.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local_RerunWorkspace') -PathType Container) 'Auto destination PlanOnly created the isolated rerun workspace.'

    $relativeCsv = Join-Path $root 'rerun-relative.csv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,relative-source.mkv,Movie,copy,keep,park
"@ | Set-Content -LiteralPath $relativeCsv -Encoding UTF8

    $relativeResult = Invoke-RerunPlanOnlyCase -CsvPath $relativeCsv -ConfigPath $config
    $relativeOutput = $relativeResult.Output
    if ($relativeResult.ExitCode -ne 0) { throw "Relative source PlanOnly check failed with exit $($relativeResult.ExitCode). Output: $relativeOutput" }

    Assert-Match $relativeOutput 'relative source_path: relative-source\.mkv' 'PlanOnly did not mark relative source_path as failed.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local') -PathType Container) 'Relative PlanOnly created LocalBase.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Out') -PathType Container) 'Relative PlanOnly created Outsource.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunManifests') -PathType Container) 'Relative PlanOnly created RerunManifests.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local_RerunWorkspace') -PathType Container) 'Relative PlanOnly created the isolated rerun workspace.'

    $invalidSource = Join-Path $root 'Not Media.txt'
    Set-Content -LiteralPath $invalidSource -Value 'not media' -Encoding ASCII
    $invalidCsv = Join-Path $root 'rerun-invalid-extension.csv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,"$invalidSource",Movie,copy,keep,park
"@ | Set-Content -LiteralPath $invalidCsv -Encoding UTF8
    $invalidResult = Invoke-RerunPlanOnlyCase -CsvPath $invalidCsv -ConfigPath $config
    if ($invalidResult.ExitCode -ne 0) { throw "Invalid-extension PlanOnly check failed with exit $($invalidResult.ExitCode). Output: $($invalidResult.Output)" }
    Assert-Match $invalidResult.Output 'invalid media extension: \.txt' 'PlanOnly did not mark invalid media extension as failed.'

    $missingCsv = Join-Path $root 'rerun-missing.csv'
    $missingSource = Join-Path $root 'Missing Source.mkv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,"$missingSource",Movie,copy,keep,park
"@ | Set-Content -LiteralPath $missingCsv -Encoding UTF8
    $missingResult = Invoke-RerunPlanOnlyCase -CsvPath $missingCsv -ConfigPath $config
    if ($missingResult.ExitCode -ne 0) { throw "Missing-source PlanOnly check failed with exit $($missingResult.ExitCode). Output: $($missingResult.Output)" }
    Assert-Match $missingResult.Output 'source file not found: .*Missing Source\.mkv' 'PlanOnly did not mark nonexistent source as failed.'

    $outsideFinalRoot = Join-Path $root 'OutsideFinal'
    $outsidePlexCsv = Join-Path $root 'rerun-outside-plex.csv'
    $outsidePlexFinal = Join-Path $outsideFinalRoot 'Movie Source 1080p HEVC.mkv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode,plex_planned_path
true,"$source",Movie,copy,keep,park,"$outsidePlexFinal"
"@ | Set-Content -LiteralPath $outsidePlexCsv -Encoding UTF8
    $outsidePlexResult = Invoke-RerunPlanOnlyCase -CsvPath $outsidePlexCsv -ConfigPath $config -DestinationMode 'pending_publish' -CollisionPolicy 'suffix'
    if ($outsidePlexResult.ExitCode -ne 0) { throw "Outside-root plex_planned_path PlanOnly check failed with exit $($outsidePlexResult.ExitCode). Output: $($outsidePlexResult.Output)" }
    Assert-Match $outsidePlexResult.Output 'final output destination from plex_planned_path resolves outside configured output root' 'PlanOnly did not block outside-root plex_planned_path.'
    Assert-False (Test-Path -LiteralPath $outsidePlexFinal -PathType Leaf) 'Outside-root plex_planned_path PlanOnly wrote a final output.'

    $outsideServerCsv = Join-Path $root 'rerun-outside-server-out.csv'
    $outsideServerFinal = Join-Path $outsideFinalRoot 'Server Out Movie.mkv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode,server_out
true,"$source",Movie,copy,keep,park,"$outsideServerFinal"
"@ | Set-Content -LiteralPath $outsideServerCsv -Encoding UTF8
    $outsideServerResult = Invoke-RerunPlanOnlyCase -CsvPath $outsideServerCsv -ConfigPath $config -DestinationMode 'pending_publish' -CollisionPolicy 'suffix'
    if ($outsideServerResult.ExitCode -ne 0) { throw "Outside-root server_out PlanOnly check failed with exit $($outsideServerResult.ExitCode). Output: $($outsideServerResult.Output)" }
    Assert-Match $outsideServerResult.Output 'final output destination from server_out resolves outside configured output root' 'PlanOnly did not block outside-root server_out.'
    Assert-False (Test-Path -LiteralPath $outsideServerFinal -PathType Leaf) 'Outside-root server_out PlanOnly wrote a final output.'

    $profileSourceRoot = Join-Path $root 'ProfileSource'
    $profileOutputRoot = Join-Path $root 'ProfileOutput'
    New-Item -ItemType Directory -Path $profileSourceRoot -Force | Out-Null
    $profileSource = Join-Path $profileSourceRoot 'Profile Movie.mkv'
    Set-Content -LiteralPath $profileSource -Value 'media' -Encoding ASCII
    $profileConfig = Join-Path $root 'config-library-profile.psd1'
    $escapedProfileSource = $profileSourceRoot.Replace("'", "''")
    $escapedProfileOutput = $profileOutputRoot.Replace("'", "''")
    $escapedProfileLocal = (Join-Path $root 'ProfileLocal').Replace("'", "''")
@"
@{
    LocalBase = '$escapedProfileLocal'
    Outsource = '$escapedRoot\Out'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
    LibraryProfiles = @(
        @{ id = 'profile'; enabled = `$true; designation = 'movie'; source_path = '$escapedProfileSource'; output_path = '$escapedProfileOutput'; overrides = @{} }
    )
}
"@ | Set-Content -LiteralPath $profileConfig -Encoding UTF8
    $profileCsv = Join-Path $root 'rerun-library-profile-output.csv'
    $profileFinal = Join-Path $profileOutputRoot 'Profile Movie\Profile Movie.mkv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode,plex_planned_path
true,"$profileSource",Movie,copy,keep,park,"$profileFinal"
"@ | Set-Content -LiteralPath $profileCsv -Encoding UTF8
    $profileResult = Invoke-RerunPlanOnlyCase -CsvPath $profileCsv -ConfigPath $profileConfig -DestinationMode 'pending_publish' -CollisionPolicy 'suffix'
    if ($profileResult.ExitCode -ne 0) { throw "Library-profile output-root PlanOnly check failed with exit $($profileResult.ExitCode). Output: $($profileResult.Output)" }
    Assert-Match $profileResult.Output 'PLAN \[pending\].*Profile Movie\.mkv' 'PlanOnly did not allow CSV final output under the matching library-profile output root.'

    $replaceOut = Join-Path $root 'ReplaceOut'
    $replaceMovieDir = Join-Path $replaceOut 'Movie Title'
    New-Item -ItemType Directory -Path $replaceMovieDir -Force | Out-Null
    $replaceSource = Join-Path $replaceMovieDir 'Movie Title.mkv'
    Set-Content -LiteralPath $replaceSource -Value 'media' -Encoding ASCII
    $replaceConfig = Join-Path $root 'config-source-overwrite.psd1'
    $escapedReplaceOut = $replaceOut.Replace("'", "''")
    $escapedReplaceLocal = (Join-Path $root 'ReplaceLocal').Replace("'", "''")
@"
@{
    LocalBase = '$escapedReplaceLocal'
    Outsource = '$escapedReplaceOut'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
}
"@ | Set-Content -LiteralPath $replaceConfig -Encoding UTF8
    $replaceCsv = Join-Path $root 'rerun-source-overwrite.csv'
@"
enabled,source_path,media_kind,stage_mode,post_success_original,return_mode
true,"$replaceSource",Movie,copy,keep,park
"@ | Set-Content -LiteralPath $replaceCsv -Encoding UTF8

    $replaceResult = Invoke-RerunPlanOnlyCase -CsvPath $replaceCsv -ConfigPath $replaceConfig -DestinationMode 'publish_replace_final' -CollisionPolicy 'replace_final' -ConfirmReplaceFinal
    if ($replaceResult.ExitCode -ne 0) { throw "Source-overwrite replacement PlanOnly check failed with exit $($replaceResult.ExitCode). Output: $($replaceResult.Output)" }
    Assert-Match $replaceResult.Output 'final output resolves to source_path; set confirm_source_overwrite=true to allow CSV rerun source overwrite' 'PlanOnly did not require explicit source-overwrite confirmation for direct final replacement.'

    $replaceConfirmedResult = Invoke-RerunPlanOnlyCase -CsvPath $replaceCsv -ConfigPath $replaceConfig -DestinationMode 'publish_replace_final' -CollisionPolicy 'replace_final' -ConfirmReplaceFinal -ConfirmSourceOverwrite
    if ($replaceConfirmedResult.ExitCode -ne 0) { throw "Confirmed source-overwrite replacement PlanOnly check failed with exit $($replaceConfirmedResult.ExitCode). Output: $($replaceConfirmedResult.Output)" }
    Assert-Match $replaceConfirmedResult.Output 'PLAN \[pending\].*Movie Title\.mkv' 'PlanOnly did not allow direct final replacement when source-overwrite was explicitly confirmed.'

    $pendingReplaceResult = Invoke-RerunPlanOnlyCase -CsvPath $replaceCsv -ConfigPath $replaceConfig -DestinationMode 'pending_publish' -CollisionPolicy 'replace_final' -ConfirmReplaceFinal
    if ($pendingReplaceResult.ExitCode -ne 0) { throw "Source-overwrite pending replacement PlanOnly check failed with exit $($pendingReplaceResult.ExitCode). Output: $($pendingReplaceResult.Output)" }
    Assert-Match $pendingReplaceResult.Output 'final output resolves to source_path; set confirm_source_overwrite=true to allow CSV rerun source overwrite' 'PlanOnly did not require explicit source-overwrite confirmation for pending-publish final replacement.'

    $pendingReplaceConfirmedResult = Invoke-RerunPlanOnlyCase -CsvPath $replaceCsv -ConfigPath $replaceConfig -DestinationMode 'pending_publish' -CollisionPolicy 'replace_final' -ConfirmReplaceFinal -ConfirmSourceOverwrite
    if ($pendingReplaceConfirmedResult.ExitCode -ne 0) { throw "Confirmed source-overwrite pending replacement PlanOnly check failed with exit $($pendingReplaceConfirmedResult.ExitCode). Output: $($pendingReplaceConfirmedResult.Output)" }
    Assert-Match $pendingReplaceConfirmedResult.Output 'PLAN \[pending\].*Movie Title\.mkv' 'PlanOnly did not allow pending-publish final replacement when source-overwrite was explicitly confirmed.'
    Assert-True (Test-Path -LiteralPath $replaceSource -PathType Leaf) 'PlanOnly source-overwrite guard moved or removed source media.'

    $emptyCsv = Join-Path $root 'rerun-empty.csv'
    Set-Content -LiteralPath $emptyCsv -Value 'enabled,source_path' -Encoding UTF8
    $emptyResult = Invoke-RerunPlanOnlyCase -CsvPath $emptyCsv -ConfigPath $config
    Assert-True ($emptyResult.ExitCode -ne 0) 'Empty CSV should fail PlanOnly before planning rows.'
    Assert-Match $emptyResult.Output 'CSV contains no rows' 'Empty CSV did not report no rows.'

    $malformedCsv = Join-Path $root 'rerun-malformed.csv'
    Set-Content -LiteralPath $malformedCsv -Value "enabled,source_path,source_path`ntrue,a,b" -Encoding UTF8
    $malformedResult = Invoke-RerunPlanOnlyCase -CsvPath $malformedCsv -ConfigPath $config
    Assert-True ($malformedResult.ExitCode -ne 0) 'Malformed CSV should fail PlanOnly before planning rows.'
    Assert-Match $malformedResult.Output 'Import-Csv|CSV|member|already present|source_path' 'Malformed CSV did not report a CSV parser error.'

    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local') -PathType Container) 'Blocked PlanOnly cases created LocalBase.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Out') -PathType Container) 'Blocked PlanOnly cases created Outsource.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local\RerunManifests') -PathType Container) 'Blocked PlanOnly cases created RerunManifests.'
    Assert-False (Test-Path -LiteralPath (Join-Path $root 'Local_RerunWorkspace') -PathType Container) 'Blocked PlanOnly cases created the isolated rerun workspace.'
    Assert-True (Test-Path -LiteralPath $source -PathType Leaf) 'PlanOnly removed or moved the source media.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Rerun PlanOnly checks passed.'
