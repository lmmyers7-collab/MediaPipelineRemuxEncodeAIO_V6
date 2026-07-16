[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected' but got '$Actual'." }
}

. (Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_processing.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\encode_context.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\encode_preflight.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_result.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_completion.ps1')

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-transient-retry-lifecycle-{0}" -f ([guid]::NewGuid().ToString('N')))
$script:RetryNoticeCount = 0
$script:ClearFailureCount = 0
$script:RoundFailureCodes = [System.Collections.Generic.List[string]]::new()
$script:RegisteredFailureCodes = [System.Collections.Generic.List[string]]::new()
$script:ParkResult = $null
$script:DeferredPublish = $true
$script:pipelineStatus = 'Processing'

function Normalize-FailureCode { param([string] $Code) return ([string]$Code).Trim().ToUpperInvariant() }
function Get-SourceFailureState {
    param($SourceFile)
    if (-not (Test-Path -LiteralPath $script:MarkerPath -PathType Leaf)) { return $null }
    return [pscustomobject][ordered]@{
        classification = 'transient'
        reason = 'old transient encode failure'
        stage = 'encode'
        error_code = 'ENCODE_TEST_TRANSIENT'
        retry_count = 1
        retry_limit = 3
    }
}
function Add-RetryNotice { $script:RetryNoticeCount++ }
function Write-Log { param([string] $Message, [string] $Level = 'INFO') }
function Clear-SourceFailureState {
    param($SourceFile)
    $script:ClearFailureCount++
    Remove-Item -LiteralPath $script:MarkerPath -Force -ErrorAction SilentlyContinue
}
function Register-SourceFailure {
    param($SourceFile, [string] $ErrorCode)
    $script:RegisteredFailureCodes.Add([string]$ErrorCode) | Out-Null
}
function Set-ProgressStage {
    param([string] $Stage, [string] $Status, [string] $Route, [string] $PushState, $Percent, [switch] $SaveNow)
}
function Test-OutputNeedsReprocess { param([string] $OutputPath, $SourceFile) return $false }
function Ensure-ScratchCopy { param($File, [string] $SafeName) return [string]$File.FullName }
function Get-OutputPaths { param($File, [bool] $IsTV, $TvInfo, [string] $SafeName) return [pscustomobject]@{ ServerOut = $script:PublishedOutputPath } }
function Invoke-Tx3gSidecarExportForExistingOutput { param($SourceFile, [string] $ScratchPath, [string] $MediaOutputPath, [string] $Context) return $true }
function New-PublishEvidenceContext {
    param($SourceFile, $Paths, [string] $StagePrefix, [string] $RouteReasonCode, [string] $RouteReason)
    return [pscustomobject][ordered]@{
        SourceIdentity = 'source-v1'
        SourceIdentityV2 = 'source-v2'
        SourceMTimeUtc = '2026-07-15T00:00:00Z'
        PublishTransactionId = 'publish-test'
        StageName = $StagePrefix
        LogPrefix = $StagePrefix.ToUpperInvariant()
        RouteReasonCode = $RouteReasonCode
        RouteReason = $RouteReason
        FolderPolicyMetadata = $null
        RoutePlanMetadata = $null
        MediaType = 'movie'
        LibraryProfileEvidence = $null
    }
}
function New-PendingParkArguments { param($EvidenceContext, $SourceFile, $Paths, [string] $Route, [string] $PublishMode, $Extra) return @{} }
function Invoke-ParkPendingPushWithTx3gSidecars {
    param($SourceFile, [string] $ScratchPath, [array] $Tx3gTracks, [array] $BdpgsTracks, [array] $VobSubTracks, [array] $ConvertedSrtSidecarCandidates, [array] $SubtitleOutputReduction, [string] $MediaOutputPath, $ParkArgs, [string] $Context)
    return $script:ParkResult
}
function Add-RoundFailureRecord {
    param([string] $SourcePath, [string] $Stage, [string] $Reason, [string] $Classification, [string] $ErrorCode, [string] $ArtifactPath, [string] $SuggestedAction)
    $script:RoundFailureCodes.Add([string]$ErrorCode) | Out-Null
}

try {
    [System.IO.Directory]::CreateDirectory($tempRoot) | Out-Null
    $sourcePath = Join-Path $tempRoot 'source.mkv'
    $serverPath = Join-Path $tempRoot 'published.mkv'
    $script:PublishedOutputPath = $serverPath
    $localPath = Join-Path $tempRoot 'local.mkv'
    $script:MarkerPath = Join-Path $tempRoot 'transient-marker.json'
    Set-Content -LiteralPath $sourcePath -Value 'source'
    Set-Content -LiteralPath $serverPath -Value 'published'
    Set-Content -LiteralPath $localPath -Value 'local'
    Set-Content -LiteralPath $script:MarkerPath -Value '{"classification":"transient"}'
    $source = Get-Item -LiteralPath $sourcePath

    $decision = Get-MediaPipelineFailureStatePreflight -File $source
    $checks = [System.Collections.Generic.List[object]]::new()
    $preflightResult = Invoke-MediaPipelineProcessPreflightDecision -Decision $decision -File $source -CollectedChecks $checks
    Assert-True ($null -eq $preflightResult) 'Transient marker must not terminate the retry before media work.'
    Assert-Equal $script:RetryNoticeCount 1 'One old transient marker must emit exactly one retry notice.'
    Assert-True (Test-Path -LiteralPath $script:MarkerPath -PathType Leaf) 'Retry notice must not clear the marker before a successful outcome.'

    $existingContext = [pscustomobject][ordered]@{
        File = $source
        IsTV = $false
        TvInfo = $null
        SafeName = $source.Name
        LocalIn = $sourcePath
        Paths = [pscustomobject]@{ ServerOut = $serverPath }
    }
    $existingResult = Invoke-MediaPipelineEncodePreflight -Context $existingContext
    Assert-True ([bool]$existingResult.Ok -and [bool]$existingResult.Terminal) 'Accepted existing output should complete successfully.'
    Assert-True (-not (Test-Path -LiteralPath $script:MarkerPath)) 'Successful existing-output publish did not clear the old transient marker.'

    Set-Content -LiteralPath $script:MarkerPath -Value '{"classification":"transient"}'
    $script:ParkResult = [pscustomobject]@{ OutputSize = 5L }
    $paths = [pscustomobject]@{ ServerOut = $serverPath; LocalOut = $localPath }
    $pendingResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths $paths -Route 'encode' -ProgressRoute 'encode' -StagePrefix 'encode' -Context 'ENCODE: '
    Assert-True ([bool]$pendingResult.Ok) 'Successful pending park should be a successful processing outcome.'
    Assert-Equal ([string]$pendingResult.PublishState) 'pending_publish' 'Successful pending park publish state changed.'
    Assert-True (-not (Test-Path -LiteralPath $script:MarkerPath)) 'Successful pending park did not clear the old transient marker.'

    Set-Content -LiteralPath $script:MarkerPath -Value '{"classification":"transient"}'
    $script:ParkResult = $null
    $failedResult = Complete-PipelineOutputPublish -SourceFile $source -ScratchPath $sourcePath -Paths $paths -Route 'encode' -ProgressRoute 'encode' -StagePrefix 'encode' -Context 'ENCODE: '
    Assert-True (-not [bool]$failedResult.Ok) 'Failed pending park should remain a failed processing outcome.'
    Assert-True (Test-Path -LiteralPath $script:MarkerPath -PathType Leaf) 'Failed publish must retain the transient marker for retry evidence.'
    Assert-Equal $script:ClearFailureCount 2 'Only successful publish outcomes should clear the transient marker.'
    Assert-True (-not (@($script:RegisteredFailureCodes) -contains 'ENCODE_UNEXPECTED_EXCEPTION')) 'Retry lifecycle registered a new ENCODE_UNEXPECTED_EXCEPTION marker.'
    Assert-True (-not (@($script:RoundFailureCodes) -contains 'ENCODE_UNEXPECTED_EXCEPTION')) 'Retry lifecycle emitted an ENCODE_UNEXPECTED_EXCEPTION round failure.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'Transient retry lifecycle checks passed.'
