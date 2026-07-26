[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Pending-publish backpressure checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSCommandPath))))
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
. (Join-Path $repoRoot 'ops\pipeline\engine\queue\pipeline_engine.ps1')

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:CapturedLogs += "$Level`:$Message"
}

function Write-PipelineEvent {
    param([string] $EventType, [string] $Stage, [string] $Status, [hashtable] $Data)
    $script:CapturedEvents += ,([pscustomobject]@{ EventType = $EventType; Stage = $Stage; Status = $Status; Data = $Data })
}

function Set-ProgressStage {
    param([string] $Stage, [string] $Status, $Percent, $Route, $CopyState, $PushState, $SidecarState, [switch] $SaveNow)
    $script:CapturedStages += ,([pscustomobject]@{ Stage = $Stage; Status = $Status; PushState = $PushState })
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('MediaPipelinePendingReadHealth_' + [guid]::NewGuid().ToString('N'))
$previousPendingRoot = $script:PendingPushRoot
$previousDeferred = $script:DeferredPublish
$previousNormalThreshold = $script:PendingPublishBacklogBlockThreshold
$previousDeferredThreshold = $script:PendingPublishDeferredBlockThreshold
try {
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    $script:PendingPushRoot = $tempRoot
    $script:DeferredPublish = $false
    $script:PendingPublishBacklogBlockThreshold = 100
    $script:PendingPublishDeferredBlockThreshold = 25
    $script:CapturedLogs = @()
    $script:CapturedEvents = @()
    $script:CapturedStages = @()

    function Get-ChildItem {
        [CmdletBinding()]
        param([string] $LiteralPath, [string] $Filter, [switch] $File)
        throw 'synthetic pending root enumeration failure'
    }
    $enumerationFailure = Get-MediaPipelinePendingPublishBackpressure
    Remove-Item -LiteralPath Function:\Get-ChildItem

    Assert-True ([bool]$enumerationFailure.Blocked) 'Enumeration failure must block queue admission.'
    Assert-Equal ([string]$enumerationFailure.BlockReason) 'pending_publish_state_unavailable' 'Enumeration failure must use a stable block reason.'
    Assert-Equal ([string]$enumerationFailure.ReadHealth) 'unavailable' 'Enumeration failure must expose unavailable read health.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$enumerationFailure.ReadError)) 'Enumeration failure must expose actionable error evidence.'

    Set-Content -LiteralPath (Join-Path $tempRoot 'corrupt.manifest.json') -Value '{not-json' -Encoding UTF8
    $malformed = Get-MediaPipelinePendingPublishBackpressure
    Assert-True ([bool]$malformed.Blocked) 'Malformed discovered manifest must block queue admission.'
    Assert-Equal ([string]$malformed.ReadHealth) 'unavailable' 'Malformed manifest must mark read health unavailable.'
    Assert-Equal ([int]$malformed.InvalidManifestCount) 1 'Malformed manifest count must be explicit.'
    Assert-Equal ([int]$malformed.ManifestCount) 1 'Discovered manifest count must not disappear after parse failure.'

    Write-MediaPipelinePendingPublishBackpressure -Backpressure $malformed
    Assert-Equal ([string]$script:CapturedEvents[0].Data.read_health) 'unavailable' 'Blocked event must propagate read health.'
    Assert-Equal ([int]$script:CapturedEvents[0].Data.invalid_manifest_count) 1 'Blocked event must propagate invalid manifest count.'
    Assert-True (@($script:CapturedStages | Where-Object Stage -eq 'pending_publish_backpressure').Count -eq 1) 'Blocked read health must publish progress evidence.'

    Remove-Item -LiteralPath (Join-Path $tempRoot 'corrupt.manifest.json') -Force
    $healthy = Get-MediaPipelinePendingPublishBackpressure
    Assert-True (-not [bool]$healthy.Blocked) 'A healthy empty pending root must remain non-blocking.'
    Assert-Equal ([string]$healthy.ReadHealth) 'healthy' 'Healthy empty scan must expose healthy read evidence.'
    Assert-Equal ([int]$healthy.InvalidManifestCount) 0 'Healthy empty scan must have no invalid manifests.'
} finally {
    Remove-Item -LiteralPath Function:\Get-ChildItem -ErrorAction SilentlyContinue
    $script:PendingPushRoot = $previousPendingRoot
    $script:DeferredPublish = $previousDeferred
    $script:PendingPublishBacklogBlockThreshold = $previousNormalThreshold
    $script:PendingPublishDeferredBlockThreshold = $previousDeferredThreshold
    if (Test-Path -LiteralPath $tempRoot -PathType Container) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'Pending-publish backpressure read-health checks passed.'
