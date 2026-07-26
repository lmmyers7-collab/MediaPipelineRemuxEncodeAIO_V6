[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Pipeline processing preflight checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

. (Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_processing\preflight.ps1')

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function New-TestFile {
    param(
        [string] $Name = 'Sample.mkv',
        [string] $Extension = '.mkv',
        [string] $FullName = 'C:\Media\Sample.mkv',
        [long] $Length = 1024
    )

    return [pscustomobject]@{
        Name      = $Name
        Extension = $Extension
        FullName  = $FullName
        Length    = $Length
    }
}

$badExtension = Test-MediaPipelineExtensionPreflight -File (New-TestFile -Name 'notes.txt' -Extension '.txt') -ValidExtensions @('.mkv', '.mp4')
Assert-True ([bool]$badExtension.Terminal) 'Bad extension should terminally skip.'
Assert-Equal $badExtension.ErrorCode 'BAD_EXTENSION' 'Bad extension error code mismatch.'
Assert-Equal $badExtension.Effects[0].Kind 'skip_stat' 'Bad extension should record skip stat first.'
Assert-Equal $badExtension.Effects[0].SkipStat 'BadExtension' 'Bad extension skip stat mismatch.'
Assert-Equal $badExtension.Checks[0].Name 'extension' 'Bad extension check name mismatch.'

function Get-SourceFailureState {
    param($File)
    return [pscustomobject]@{
        classification = 'operator_required'
        reason         = 'manual review required'
        stage          = 'probe'
        error_code     = 'needs_operator'
        retry_count    = 2
        retry_limit    = 3
    }
}
function Normalize-FailureCode {
    param([string] $Code)
    return $Code.ToUpperInvariant()
}

$operatorFailure = Get-MediaPipelineFailureStatePreflight -File (New-TestFile)
Assert-True ([bool]$operatorFailure.Terminal) 'Operator-required failure state should terminally skip.'
Assert-Equal $operatorFailure.ErrorCode 'NEEDS_OPERATOR' 'Failure-state normalized error code mismatch.'
Assert-Equal $operatorFailure.Effects[0].SkipStat 'OperatorRequired' 'Operator-required skip stat mismatch.'
Assert-True ($operatorFailure.Effects[1].Message -match 'retry=2/3') 'Failure-state retry suffix should be preserved in log instruction.'

function Get-SourceFailureState {
    param($File)
    return [pscustomobject]@{
        classification = 'transient'
        reason         = 'temporary lock'
        stage          = 'source-open'
        retry_count    = 1
        retry_limit    = 5
    }
}
function Get-MediaFailureCode {
    param([string] $Stage, [string] $Reason, [string] $Classification)
    return 'SOURCE_TEMPORARY_LOCK'
}

$transientFailure = Get-MediaPipelineFailureStatePreflight -File (New-TestFile)
Assert-True (-not [bool]$transientFailure.Terminal) 'Transient failure state should continue.'
Assert-Equal $transientFailure.Effects[0].Kind 'retry_notice' 'Transient failure should queue retry notice first.'
Assert-Equal $transientFailure.Effects[1].Kind 'log' 'Transient failure should log after retry notice.'
Assert-True ($transientFailure.Effects[1].Message -match 'SOURCE_TEMPORARY_LOCK') 'Transient failure log should carry computed failure code.'

function Get-TVInfoFromFile {
    param(
        $File,
        [string] $SourceRootPath = '',
        [string] $LibraryName = '',
        [string] $LibraryId = '',
        [string] $LibraryDesignation = ''
    )
    $script:LastTvParserArgs = [pscustomobject]@{
        SourceRootPath     = $SourceRootPath
        LibraryName        = $LibraryName
        LibraryId          = $LibraryId
        LibraryDesignation = $LibraryDesignation
    }
    return [pscustomobject]@{
        IsReliable = $false
        ParseError = 'ambiguous season episode'
    }
}
function Get-MediaPipelineLibraryProfileEvidenceForPath {
    param([string] $SourcePath, [string] $LibraryProfileId = '')
    $script:LastLibraryEvidenceRequest = [pscustomobject]@{
        SourcePath       = $SourcePath
        LibraryProfileId = $LibraryProfileId
    }
    return [ordered]@{
        source_root = 'C:\Media\TV'
        library_name = 'TV'
        library_id = 'tv'
        designation = 'tv'
    }
}
function Get-TVParseRenameSuggestion {
    param($File, $TvInfo)
    return 'Sample.S01E01.mkv'
}

$tvFailure = Get-MediaPipelineTvParsePreflight -File (New-TestFile -Name 'Ambiguous.mkv' -FullName 'C:\Media\TV\Ambiguous.mkv') -IsTV:$true -LibraryProfileId 'tv'
Assert-True ([bool]$tvFailure.Terminal) 'Unreliable TV parse should terminally skip.'
Assert-Equal $tvFailure.ErrorCode 'TV_PARSE_UNRELIABLE' 'TV parse error code mismatch.'
Assert-Equal $tvFailure.Effects[0].Kind 'register_failure' 'TV parse should register failure before skip stat.'
Assert-Equal $tvFailure.Effects[0].FailureRegistration.SuggestedRename 'Sample.S01E01.mkv' 'TV parse suggested rename mismatch.'
Assert-Equal $tvFailure.Effects[1].SkipStat 'AmbiguousTV' 'TV parse skip stat mismatch.'
Assert-Equal $script:LastLibraryEvidenceRequest.LibraryProfileId 'tv' 'TV parse should resolve evidence for the selected library profile.'
Assert-Equal $script:LastTvParserArgs.SourceRootPath 'C:\Media\TV' 'TV parser should receive the active TV source root.'
Assert-Equal $script:LastTvParserArgs.LibraryName 'TV' 'TV parser should receive the active library name.'
Assert-Equal $script:LastTvParserArgs.LibraryId 'tv' 'TV parser should receive the active library id.'
Assert-Equal $script:LastTvParserArgs.LibraryDesignation 'tv' 'TV parser should receive the active library designation.'

function Resolve-ShowOverrides {
    param([string] $ShowName)
    return [pscustomobject]@{ ShowName = 'Canonical Show' }
}

$tvInfo = [pscustomobject]@{
    IsReliable = $true
    ShowName   = 'Raw Show'
}
$showOverride = Resolve-MediaPipelineTvShowNameOverridePreflight -IsTV:$true -TvInfo $tvInfo
Assert-Equal $showOverride.TvInfo.ShowName 'Canonical Show' 'Show-name override should mutate the shared TV info object.'
Assert-Equal $showOverride.Checks[0].State 'applied' 'Show-name override state mismatch.'
Assert-True ($showOverride.Effects[0].Message -match 'Raw Show') 'Show-name override log should name original show.'

function Already-Processed {
    param($File, [bool] $IsTV, $TvInfo, $ProcessedIndex)
    return $true
}

$already = Test-MediaPipelineAlreadyProcessedPreflight -File (New-TestFile) -IsTV:$false -ProcessedIndex @{} -MediaType 'movie'
Assert-True ([bool]$already.Terminal) 'Already-processed check should terminally skip.'
Assert-True ([bool]$already.Success) 'Already-processed skip should be a successful terminal queue result.'
Assert-Equal $already.Effects[0].SkipStat 'AlreadyProcessed' 'Already-processed skip stat mismatch.'
Assert-Equal $already.Effects[1].Kind 'clear_failure_state' 'Already-processed check should clear prior failure state.'

function Test-FileStable {
    param([string] $Path)
    return $false
}

$unstable = Test-MediaPipelineStabilityPreflight -File (New-TestFile) -MediaType 'movie'
Assert-True ([bool]$unstable.Terminal) 'Unstable source should terminally skip this pass.'
Assert-True ([bool]$unstable.Retryable) 'Unstable source should remain retryable.'
Assert-Equal $unstable.ErrorCode 'SOURCE_STILL_WRITING' 'Unstable source error code mismatch.'
Assert-Equal $unstable.Effects[0].SkipStat 'StillWriting' 'Unstable source skip stat mismatch.'

function Get-SafeLocalName {
    param([string] $Name)
    return "safe-$Name"
}
function Get-OutputPaths {
    param($File, [bool] $IsTV, $TvInfo, [string] $SafeName)
    return [pscustomobject]@{
        ServerOut = "C:\Out\$SafeName"
    }
}
function Test-OutputPathCapability {
    param($Paths)
    return [pscustomobject]@{
        Ok     = $false
        Reason = 'component too long'
        Path   = $Paths.ServerOut
    }
}
function Get-FailureSuggestedAction {
    param([string] $Stage, [string] $Reason)
    return 'rename the output'
}

$outputUnsupported = Test-MediaPipelineOutputPathPreflight -File (New-TestFile -Name 'LongName.mkv') -MediaType 'movie'
Assert-True ([bool]$outputUnsupported.Terminal) 'Unsupported output path should terminally skip.'
Assert-Equal $outputUnsupported.SafeName 'safe-LongName.mkv' 'Output path check should expose safe name.'
Assert-Equal $outputUnsupported.ErrorCode 'OUTPUT_PATH_UNSUPPORTED' 'Unsupported output path error code mismatch.'
Assert-Equal $outputUnsupported.Effects[0].SkipStat 'PathUnsupported' 'Unsupported output path skip stat mismatch.'
Assert-Equal $outputUnsupported.Effects[1].FailureRegistration.SuggestedAction 'rename the output' 'Unsupported output path suggested action mismatch.'
Assert-Equal $outputUnsupported.Effects[1].FailureRegistration.SuggestedRename 'safe-LongName.mkv' 'Unsupported output path suggested rename mismatch.'

$script:AcceptedNamingReaderCalls = 0
$script:ExecutionPlannerCalls = 0
$script:AcceptedNamingEvidence = $null
$script:ExecutionPlannedName = 'Edge of Tomorrow (2014).mkv'
function Get-MediaPipelineRunMonitorAcceptedNamingEvidence {
    param([string] $RunId, [string] $JobId, [string] $SourcePath)
    $script:AcceptedNamingReaderCalls++
    return $script:AcceptedNamingEvidence
}
function Get-OutputPaths {
    param($File, [bool] $IsTV, $TvInfo, [string] $SafeName)
    $script:ExecutionPlannerCalls++
    return [pscustomobject]@{
        PlexPlan = [pscustomobject]@{ FileName = [string]$script:ExecutionPlannedName }
        ServerOut = Join-Path 'C:\Out' ([string]$script:ExecutionPlannedName)
    }
}

$script:PipelineRunId = ''
$script:CurrentRunMonitorJobId = ''
$directNaming = Test-MediaPipelineAcceptedDestinationNamePreflight -File (New-TestFile) -MediaType 'movie'
Assert-True (-not [bool]$directNaming.Terminal) 'Direct/manual processing without Run Monitor correlation must remain compatible.'
Assert-Equal $directNaming.Checks[0].State 'not_applicable' 'Direct/manual naming guard state mismatch.'
Assert-Equal $script:AcceptedNamingReaderCalls 0 'Direct/manual processing must not read accepted Queue naming evidence.'
Assert-Equal $script:ExecutionPlannerCalls 0 'Direct/manual processing must not add a redundant destination-plan call.'

$script:PipelineRunId = 'legacy-run'
$script:CurrentRunMonitorJobId = 'legacy-run-item-00000001'
$script:AcceptedNamingEvidence = [pscustomobject]@{
    Applies = $false; Verified = $false; LegacyCompatible = $true
    Reason = 'The correlated run predates fingerprinted accepted-name enforcement.'
    QueuePlanFingerprint = ''
}
$legacyNaming = Test-MediaPipelineAcceptedDestinationNamePreflight -File (New-TestFile) -MediaType 'movie'
Assert-True (-not [bool]$legacyNaming.Terminal) 'A pre-fingerprint legacy run must remain compatible.'
Assert-Equal $legacyNaming.Checks[0].State 'legacy_compatible' 'Legacy naming guard state mismatch.'
Assert-Equal $script:ExecutionPlannerCalls 0 'Legacy compatibility must not claim a newly verified execution plan.'

$script:PipelineRunId = 'verified-run'
$script:CurrentRunMonitorJobId = 'verified-run-item-00000001'
$script:AcceptedNamingEvidence = [pscustomobject]@{
    Applies = $true; Verified = $true; LegacyCompatible = $false
    ExpectedDisplayName = 'Edge of Tomorrow (2014).mkv'
    QueuePlanFingerprint = 'verified-queue-plan'
    Reason = 'Accepted production destination-name evidence is verified for execution.'
}
$script:ExecutionPlannedName = 'Edge of Tomorrow (2014).mkv'
$matchedNaming = Test-MediaPipelineAcceptedDestinationNamePreflight -File (New-TestFile -Name 'Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv') -MediaType 'movie'
Assert-True (-not [bool]$matchedNaming.Terminal) 'A matching verified destination name must continue.'
Assert-Equal $matchedNaming.Checks[0].State 'matched' 'Verified destination-name match state mismatch.'
Assert-Equal $matchedNaming.Checks[0].Data.queue_plan_fingerprint 'verified-queue-plan' 'Matched destination-name evidence must retain the accepted Queue fingerprint.'

$script:ExecutionPlannedName = 'Edge of Tomorrow GalaxyRG265 (2014).mkv'
$driftedNaming = Test-MediaPipelineAcceptedDestinationNamePreflight -File (New-TestFile -Name 'Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv') -MediaType 'movie'
Assert-True ([bool]$driftedNaming.Terminal) 'A verified accepted/execution destination-name mismatch must fail closed.'
Assert-Equal $driftedNaming.Status 'skipped' 'Destination-name drift must terminally skip the stale accepted item without creating a sticky source failure.'
Assert-Equal $driftedNaming.ErrorCode 'DESTINATION_NAMING_PLAN_MISMATCH' 'Destination-name drift error code mismatch.'
Assert-True (-not [bool]$driftedNaming.Retryable) 'Destination-name drift must not retry inside the stale accepted run.'
Assert-True ([bool]$driftedNaming.QueueTerminal) 'Destination-name drift must terminate the accepted queue item.'
Assert-True ($driftedNaming.Reason -match 'Edge of Tomorrow \(2014\)\.mkv' -and $driftedNaming.Reason -match 'GalaxyRG265') 'Destination-name drift reason must expose accepted and execution filenames.'
Assert-Equal @($driftedNaming.Effects | Where-Object Kind -eq 'register_failure').Count 0 'Destination-name drift must not create a sticky per-source failure marker.'

$plannerCallsBeforeMissing = $script:ExecutionPlannerCalls
$script:AcceptedNamingEvidence = [pscustomobject]@{
    Applies = $true; Verified = $false; LegacyCompatible = $false
    ExpectedDisplayName = ''; QueuePlanFingerprint = 'verified-queue-plan'
    Reason = "Fingerprint-backed accepted display-name source is 'legacy_internal_seed', not plex_destination_plan.v1."
    ErrorCode = 'DESTINATION_NAMING_EVIDENCE_MISSING'
}
$missingNaming = Test-MediaPipelineAcceptedDestinationNamePreflight -File (New-TestFile) -MediaType 'movie'
Assert-True ([bool]$missingNaming.Terminal) 'Missing naming evidence in a fingerprint-backed Backend Queue job must fail closed.'
Assert-Equal $missingNaming.ErrorCode 'DESTINATION_NAMING_EVIDENCE_MISSING' 'Missing naming evidence error code mismatch.'
Assert-Equal $script:ExecutionPlannerCalls $plannerCallsBeforeMissing 'Missing accepted evidence must block before recomputing an execution destination.'

$processingPath = Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_processing.ps1'
$processingText = Get-Content -LiteralPath $processingPath -Raw
$overridePushIndex = $processingText.IndexOf('$activeConfigOverrideSnapshot = Push-MediaPipelineActiveConfigOverrides', [System.StringComparison]::Ordinal)
$destinationGuardIndex = $processingText.IndexOf('$destinationNameDecision = Test-MediaPipelineAcceptedDestinationNamePreflight', [System.StringComparison]::Ordinal)
$probeIndex = $processingText.IndexOf('$routeHints = Get-ActiveMediaRouteHints', [System.StringComparison]::Ordinal)
Assert-True ($overridePushIndex -ge 0 -and $destinationGuardIndex -gt $overridePushIndex) 'Destination-name guard must run only after effective config overrides are active.'
Assert-True ($probeIndex -gt $destinationGuardIndex) 'Destination-name guard must run before probe and downstream media work.'
Assert-True ($processingText -match '\$script:CurrentAcceptedOutputPaths\s*=\s*\$destinationNameDecision\.OutputPaths') 'The verified destination plan must be retained for downstream encode/remux stages.'
Assert-True ($processingText -match '\$script:CurrentAcceptedOutputPaths\s*=\s*\$null[\s\S]+finally\s*\{[\s\S]+\$script:CurrentAcceptedOutputPaths\s*=\s*\$null') 'The accepted destination-plan runtime slot must be initialized and cleared per file.'

$encodeOrchestratorText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process\encode_orchestrator.ps1') -Raw
$remuxOrchestratorText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process\remux_orchestrator.ps1') -Raw
$encodePreflightText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process\encode_preflight.ps1') -Raw
$remuxPreflightText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process\remux_preflight.ps1') -Raw
Assert-True ($encodeOrchestratorText -match 'CurrentAcceptedOutputPaths[\s\S]+New-MediaPipelineEncodeContext[\s\S]+-OutputPaths \$acceptedOutputPaths') 'Encode must receive the verified destination plan.'
Assert-True ($remuxOrchestratorText -match 'CurrentAcceptedOutputPaths[\s\S]+New-MediaPipelineRemuxContext[\s\S]+-OutputPaths \$acceptedOutputPaths') 'Remux and remux fallbacks must receive the verified destination plan.'
Assert-True ($encodePreflightText -match 'if \(-not \$Context\.Paths\)\s*\{\s*\$Context\.Paths = Get-OutputPaths') 'Encode preflight may plan output paths only when no verified plan was supplied.'
Assert-True ($remuxPreflightText -match 'if \(-not \$Context\.Paths\)\s*\{\s*\$Context\.Paths = Get-OutputPaths') 'Remux preflight may plan output paths only when no verified plan was supplied.'

Write-Host 'Pipeline processing preflight checks passed.'
