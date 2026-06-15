[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Pipeline processing source-probe checks require PowerShell 7. Install pwsh or use the bundled runtime."
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

. (Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_processing.ps1')

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

$script:RegisteredFailures = @()
$script:PipelineEvents = @()
$script:RouteSelectionCalled = $false
$script:EncodeCalled = $false
$script:ProgressWriteFailures = 0
$script:StopRequested = $false
$script:ValidExtensions = @('.mkv', '.mov', '.mp2')
$script:ProbeError = 'video_stream_missing'

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function Write-PipelineEvent {
    param(
        [string] $EventType,
        [string] $Stage,
        [string] $Route,
        [string] $Status,
        [string] $SourcePath,
        $Data
    )
    $script:PipelineEvents += [pscustomobject]@{
        EventType  = $EventType
        Stage      = $Stage
        Route      = $Route
        Status     = $Status
        SourcePath = $SourcePath
        Data       = $Data
    }
}

function Register-SourceFailure {
    param(
        $SourceFile,
        [string] $Classification,
        [string] $Reason,
        [string] $Stage,
        [string] $ErrorCode,
        [string] $SuggestedAction
    )
    $script:RegisteredFailures += [pscustomobject]@{
        SourceFile      = $SourceFile
        Classification  = $Classification
        Reason          = $Reason
        Stage           = $Stage
        ErrorCode       = $ErrorCode
        SuggestedAction = $SuggestedAction
    }
}

function Get-SourcePriorityInfo { param($File) return [pscustomobject]@{ IsPriority = $false } }
function Get-SourceIdentityKeyV2 { param($File) return "source:$($File.Name):$($File.Length)" }
function Get-SourceIdentityKey { param($File) return "legacy:$($File.Name):$($File.Length)" }
function Get-MediaPipelineLibraryProfileEvidenceForPath {
    param([string] $SourcePath, [string] $LibraryProfileId)
    return @{
        library_id = 'test-library'
        library_name = 'Test Library'
        designation = 'movies'
        source_root = 'C:\Media'
        output_root = 'C:\Out'
        promotion_enabled = $false
        promotion_destination_root = ''
        promotion_rule_id = ''
        promotion_rule_source = ''
        settings_override_keys = @()
        settings_overrides = @{}
        effective_settings = @{}
    }
}
function Set-ProgressItemContext {
    param(
        [string] $DisplayName,
        [string] $FilePath,
        [string] $MediaType,
        [string] $LibraryId,
        [string] $LibraryName,
        [string] $LibraryDesignation,
        [string] $LibrarySourceRoot,
        [string] $LibraryOutputRoot,
        [string] $QueuePhase,
        [int] $QueueIndex,
        [int] $QueueTotal
    )
}
function Set-ProgressStage {
    param(
        [string] $Stage,
        [string] $Status,
        $Percent,
        $CopyState,
        $PushState,
        $SidecarState,
        [switch] $SaveNow
    )
}
function Get-SourceFailureState { param($File) return $null }
function Normalize-FailureCode { param([string] $Code) return $Code.ToUpperInvariant() }
function Get-MediaFailureCode { param([string] $Stage, [string] $Reason, [string] $Classification) return 'SOURCE_FAILURE_MARKER' }
function Already-Processed { param($File, [bool] $IsTV, $TvInfo, $ProcessedIndex) return $false }
function Test-FileStable { param([string] $Path) return $true }
function Get-SafeLocalName { param([string] $Name) return $Name }
function Get-OutputPaths { param($File, [bool] $IsTV, $TvInfo, [string] $SafeName) return [pscustomobject]@{ ServerOut = "C:\Out\$SafeName" } }
function Test-OutputPathCapability { param($Paths) return [pscustomobject]@{ Ok = $true; Reason = ''; Path = '' } }
function Resolve-ShowOverrides { param([string] $ShowName) return $null }
function Resolve-FolderPolicyOverrides { param($SourceFile) return @{} }
function Resolve-MediaPipelineLibraryOverridesForPath { param([string] $SourcePath, [string] $LibraryProfileId) return @{} }
function Merge-MediaPipelineActiveOverrides {
    param($Base, $Override)
    if ($Base) { return $Base }
    return @{}
}
function Merge-FileOverrideIntoActiveOverrides { param([string] $SourcePath) }
function ConvertTo-MediaPipelineProfileMap { param($Value) return @{} }
function Resolve-MediaPipelineLibraryEffectiveSettings { param($Overrides) return @{} }
function Get-MediaPipelineRuntimeGlobalSettingsLayer { return [ordered]@{ name = 'global'; keys = @{} } }
function New-MediaPipelineRuntimeSettingsLayer {
    param(
        [string] $Name,
        [string] $Source,
        $Keys,
        [string[]] $ExcludeKeys = @(),
        [bool] $SavedConfig = $true
    )
    return [ordered]@{ name = $Name; source = $Source; keys = $Keys; saved = $SavedConfig }
}
function Push-MediaPipelineActiveConfigOverrides { param($Overrides) return @{} }
function Pop-MediaPipelineActiveConfigOverrides { param($Snapshot) }
function Get-ActiveMediaRouteHints { return @{} }
function Reset-ProgressItemContext {}
function Get-SourceMediaRouteProfile {
    param([string] $FilePath, [long] $FileSizeBytes)
    return [pscustomobject]@{
        probe_ok    = $false
        probe_error = $script:ProbeError
        video_codec = 'unknown'
    }
}
function Resolve-InitialMediaRoutePlan {
    param($File, [bool] $IsTV, $MediaProfile, $RouteHints)
    $script:RouteSelectionCalled = $true
    throw 'Route selection should not run for a failed source probe.'
}
function Do-Encode {
    $script:EncodeCalled = $true
    throw 'Encode should not run for a failed source probe.'
}

function Invoke-FailedSourceProbeCase {
    param(
        [Parameter(Mandatory)] [string] $ProbeError,
        [Parameter(Mandatory)] [string] $ExpectedErrorCode,
        [Parameter(Mandatory)] [string] $ExpectedRouteReasonCode,
        [Parameter(Mandatory)] [string] $ExpectedClassification,
        [Parameter(Mandatory)] [bool] $ExpectedRetryable,
        [Parameter(Mandatory)] [bool] $ExpectedQueueTerminal,
        [Parameter(Mandatory)] [string] $SuggestedActionPattern
    )

    $script:RegisteredFailures = @()
    $script:PipelineEvents = @()
    $script:RouteSelectionCalled = $false
    $script:EncodeCalled = $false
    $script:ProbeError = $ProbeError

    $file = [pscustomobject]@{
        Name      = "$ProbeError.mkv"
        Extension = '.mkv'
        FullName  = "C:\Media\$ProbeError.mkv"
        Length    = 1024
    }

    $result = Invoke-MediaPipelineProcessFile -file $file -isTV:$false -idx @{}

    Assert-Equal $result.Status 'failed' "$ProbeError source should fail."
    Assert-True (-not [bool]$result.Success) "$ProbeError source should not succeed."
    Assert-Equal ([bool]$result.QueueTerminal) $ExpectedQueueTerminal "$ProbeError queue-terminal flag mismatch."
    Assert-Equal ([bool]$result.Retryable) $ExpectedRetryable "$ProbeError retryable flag mismatch."
    Assert-Equal $result.ErrorCode $ExpectedErrorCode "$ProbeError source error code mismatch."
    Assert-Equal $result.RouteReasonCode $ExpectedRouteReasonCode "$ProbeError route reason code mismatch."
    Assert-True (-not $script:RouteSelectionCalled) "Route selection should not run for $ProbeError."
    Assert-True (-not $script:EncodeCalled) "Encode command should not launch for $ProbeError."

    Assert-Equal @($script:RegisteredFailures).Count 1 "$ProbeError source should record one failure marker."
    $failure = $script:RegisteredFailures[0]
    Assert-Equal $failure.Classification $ExpectedClassification "$ProbeError source failure classification mismatch."
    Assert-Equal $failure.Stage 'source-probe' "$ProbeError source failure stage mismatch."
    Assert-Equal $failure.ErrorCode $ExpectedErrorCode "$ProbeError source failure marker code mismatch."
    Assert-True ($failure.SuggestedAction -match $SuggestedActionPattern) "$ProbeError suggested action mismatch."

    Assert-Equal @($script:PipelineEvents).Count 2 "$ProbeError source should emit start and completion events."
    $event = @($script:PipelineEvents | Where-Object { $_.EventType -eq 'job_completed' })[0]
    Assert-True ($null -ne $event) "$ProbeError source should emit a completion event."
    Assert-Equal $event.Stage 'source-probe' "$ProbeError event stage mismatch."
    Assert-Equal $event.Status 'failed' "$ProbeError event status mismatch."
    Assert-Equal $event.Data.error_code $ExpectedErrorCode "$ProbeError event code mismatch."
    Assert-Equal ([bool]$event.Data.retryable) $ExpectedRetryable "$ProbeError event retryable mismatch."
}

Invoke-FailedSourceProbeCase `
    -ProbeError 'video_stream_missing' `
    -ExpectedErrorCode 'SOURCE_MEDIA_VIDEO_MISSING' `
    -ExpectedRouteReasonCode 'source_video_missing' `
    -ExpectedClassification 'permanent' `
    -ExpectedRetryable:$false `
    -ExpectedQueueTerminal:$true `
    -SuggestedActionPattern 'replace the source'

foreach ($probeError in @('ffprobe_failed','ffprobe_json_invalid')) {
    Invoke-FailedSourceProbeCase `
        -ProbeError $probeError `
        -ExpectedErrorCode 'SOURCE_MEDIA_PROBE_FAILED' `
        -ExpectedRouteReasonCode 'source_probe_failed' `
        -ExpectedClassification 'transient' `
        -ExpectedRetryable:$true `
        -ExpectedQueueTerminal:$false `
        -SuggestedActionPattern 'ffprobe|probe problem'
}

Invoke-FailedSourceProbeCase `
    -ProbeError 'file_missing' `
    -ExpectedErrorCode 'SOURCE_FILE_MISSING' `
    -ExpectedRouteReasonCode 'source_probe_file_missing' `
    -ExpectedClassification 'operator_required' `
    -ExpectedRetryable:$true `
    -ExpectedQueueTerminal:$false `
    -SuggestedActionPattern 'source path'

Invoke-FailedSourceProbeCase `
    -ProbeError 'file_path_empty' `
    -ExpectedErrorCode 'SOURCE_FILE_PATH_EMPTY' `
    -ExpectedRouteReasonCode 'source_probe_file_path_empty' `
    -ExpectedClassification 'operator_required' `
    -ExpectedRetryable:$true `
    -ExpectedQueueTerminal:$false `
    -SuggestedActionPattern 'source path'

Write-Host 'Pipeline processing source-probe checks passed.'
