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
$repoRoot = Split-Path -Parent $pipelineRoot

. (Join-Path $repoRoot 'engine\process\pipeline_processing\preflight.ps1')

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
    param($File)
    return [pscustomobject]@{
        IsReliable = $false
        ParseError = 'ambiguous season episode'
    }
}
function Get-TVParseRenameSuggestion {
    param($File, $TvInfo)
    return 'Sample.S01E01.mkv'
}

$tvFailure = Get-MediaPipelineTvParsePreflight -File (New-TestFile -Name 'Ambiguous.mkv') -IsTV:$true
Assert-True ([bool]$tvFailure.Terminal) 'Unreliable TV parse should terminally skip.'
Assert-Equal $tvFailure.ErrorCode 'TV_PARSE_UNRELIABLE' 'TV parse error code mismatch.'
Assert-Equal $tvFailure.Effects[0].Kind 'register_failure' 'TV parse should register failure before skip stat.'
Assert-Equal $tvFailure.Effects[0].FailureRegistration.SuggestedRename 'Sample.S01E01.mkv' 'TV parse suggested rename mismatch.'
Assert-Equal $tvFailure.Effects[1].SkipStat 'AmbiguousTV' 'TV parse skip stat mismatch.'

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

Write-Host 'Pipeline processing preflight checks passed.'
