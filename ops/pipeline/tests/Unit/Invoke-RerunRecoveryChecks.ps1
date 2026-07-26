[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Rerun recovery checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
$rerunScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Invoke-RerunCsv.ps1'
$entrySupport = Join-Path $repoRoot 'ops\pipeline\engine\rerun\entry_support.ps1'
$pathHelpers = Join-Path $repoRoot 'ops\pipeline\engine\shared\path_helpers.ps1'
$evidenceModule = Join-Path $repoRoot 'ops\pipeline\engine\rerun\evidence.ps1'
$recoveryModule = Join-Path $repoRoot 'ops\pipeline\engine\rerun\recovery.ps1'
$planningModule = Join-Path $repoRoot 'ops\pipeline\engine\rerun\planning.ps1'
$identityModule = Join-Path $repoRoot 'ops\pipeline\engine\audit\rerun_source_identity.ps1'

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-False {
    param([bool]$Condition, [string]$Message)
    if ($Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}

function Invoke-RerunChild {
    param([string[]]$Arguments)
    $hostPath = (Get-Process -Id $PID).Path
    $output = @(& $hostPath @Arguments 2>&1 | ForEach-Object { [string]$_ })
    return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = ($output -join "`n") }
}

function New-RerunFixtureConfig {
    param([string]$Path, [string]$LocalBase, [string]$Outsource)
    $escapedLocal = $LocalBase.Replace("'", "''")
    $escapedOut = $Outsource.Replace("'", "''")
    @"
@{
    LocalBase = '$escapedLocal'
    Outsource = '$escapedOut'
    OutputContainer = 'mkv'
    CreateTVSubfolder = `$true
    AggressiveEpisodeParsing = `$true
    ValidExtensions = @('.mkv')
    PriorityMarkers = @('!')
}
"@ | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-UnusedDriveName {
    foreach ($candidate in @('Z','Y','X','W','V','U','T')) {
        if (-not (Test-Path -LiteralPath "${candidate}:\" -ErrorAction SilentlyContinue)) { return $candidate }
    }
    throw 'No disposable drive letter was available for the offline-root fixture.'
}

function Set-RerunFixtureDriveOffline {
    param(
        [Parameter(Mandatory)] [string]$DriveName,
        [Parameter(Mandatory)] [string]$ReservationPath
    )

    & subst.exe "${DriveName}:" /D 2>$null | Out-Null
    if (Test-Path -LiteralPath $ReservationPath) {
        Remove-Item -LiteralPath $ReservationPath -Force -ErrorAction Stop
    }
    New-Item -ItemType Directory -Path $ReservationPath -Force | Out-Null
    & subst.exe "${DriveName}:" $ReservationPath | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Unable to reserve disposable subst drive ${DriveName}: for the offline-root fixture." }
    Remove-Item -LiteralPath $ReservationPath -Force -ErrorAction Stop
    if (Test-Path -LiteralPath "${DriveName}:\" -ErrorAction SilentlyContinue) {
        throw "Disposable subst drive ${DriveName}: remained reachable after its reservation target was removed."
    }
}

function Set-RerunFixtureDriveOnline {
    param(
        [Parameter(Mandatory)] [string]$DriveName,
        [Parameter(Mandatory)] [string]$BackingPath
    )

    if (-not (Test-Path -LiteralPath $BackingPath -PathType Container)) {
        throw "Disposable subst backing path is unavailable: $BackingPath"
    }
    & subst.exe "${DriveName}:" /D 2>$null | Out-Null
    & subst.exe "${DriveName}:" $BackingPath | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Unable to connect disposable subst drive ${DriveName}: to its fixture backing path." }
    if (-not (Test-Path -LiteralPath "${DriveName}:\" -PathType Container)) {
        throw "Disposable subst drive ${DriveName}: did not expose its fixture backing path."
    }
}

function New-RerunFixtureDirectoryJunction {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Target
    )
    try {
        New-Item -ItemType Junction -Path $Path -Target $Target -ErrorAction Stop | Out-Null
        return $true
    } catch {
        try {
            & cmd.exe /d /c "mklink /J `"$Path`" `"$Target`"" | Out-Null
            return ($LASTEXITCODE -eq 0)
        } catch {
            return $false
        }
    }
}

Assert-True (Test-Path -LiteralPath $rerunScript -PathType Leaf) "Rerun entrypoint missing: $rerunScript"
Assert-True (Test-Path -LiteralPath $pathHelpers -PathType Leaf) "Shared path-boundary helper missing: $pathHelpers"
Assert-True (Test-Path -LiteralPath $recoveryModule -PathType Leaf) "Rerun recovery module missing: $recoveryModule"
Assert-True (Test-Path -LiteralPath $planningModule -PathType Leaf) "Rerun planning module missing: $planningModule"
. $pathHelpers
. $entrySupport
. $evidenceModule
. $identityModule
. $recoveryModule
. $planningModule

foreach ($mutationHelperName in @(
    'Clear-RerunCopyAttemptArtifacts',
    'Move-RerunStageAttemptToDestination',
    'Copy-RerunFileVerified',
    'Invoke-RerunStagePlans'
)) {
    $mutationHelper = Get-Command -Name $mutationHelperName -CommandType Function -ErrorAction Stop
    $scratchTrustParameter = $mutationHelper.Parameters['ScratchTrustRoot']
    $mandatoryAttribute = @($scratchTrustParameter.Attributes | Where-Object { $_ -is [System.Management.Automation.ParameterAttribute] } | Select-Object -First 1)
    Assert-True ($mandatoryAttribute.Count -eq 1 -and [bool]$mandatoryAttribute[0].Mandatory) "$mutationHelperName must require an explicit, proven ScratchTrustRoot."
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-rerun-recovery-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root -Force | Out-Null
$driveName = Get-UnusedDriveName
$driveReservationPath = Join-Path $root 'OfflineDriveReservation'
try {
    Set-RerunFixtureDriveOffline -DriveName $driveName -ReservationPath $driveReservationPath

    # A missing drive/share is recoverable; a missing leaf on a healthy root is not.
    $offlineSource = "${driveName}:\Library\Offline Movie.mkv"
    $offline = Get-RerunSourceHealth -SourcePath $offlineSource -ExpectedIdentityV2 ('a' * 64) -FfprobePath ''
    Assert-Equal $offline.Code 'source_location_unavailable' 'Offline root was not typed as a location outage.'
    Assert-True $offline.Retryable 'Offline root should be eligible for bounded retry.'

    $healthyRoot = Join-Path $root 'HealthyRoot'
    New-Item -ItemType Directory -Path $healthyRoot -Force | Out-Null
    $missingSource = Join-Path $healthyRoot 'Missing Movie.mkv'
    $missing = Get-RerunSourceHealth -SourcePath $missingSource -ExpectedIdentityV2 ('b' * 64) -FfprobePath ''
    Assert-Equal $missing.Code 'source_missing' 'Missing leaf under a healthy root was not typed as missing.'
    Assert-False $missing.Retryable 'A genuinely missing leaf must not loop as a location outage.'

    $accessCode = Get-RerunSourceExceptionCode -Exception ([System.UnauthorizedAccessException]::new('denied'))
    Assert-Equal $accessCode 'source_access_failed' 'Access failures need their own stable reason code.'
    $ioCode = Get-RerunSourceExceptionCode -Exception ([System.IO.IOException]::new('SMB I/O stalled'))
    Assert-Equal $ioCode 'source_access_failed' 'Source I/O failures must use the bounded access-failure path.'
    $uncRoot = Get-RerunSourceRootPath -SourcePath '\\fixture-server\fixture-share\Library\Movie.mkv'
    Assert-Equal $uncRoot '\\fixture-server\fixture-share\' 'UNC source-root parsing did not stop at the share boundary.'

    # Configured source roots, not merely the hosting volume/share, define outage versus missing-leaf semantics.
    $configuredParent = Join-Path $root 'ConfiguredRoots'
    $configuredMovies = Join-Path $configuredParent 'Movies'
    $configuredMissingSource = Join-Path $configuredMovies 'Configured Missing.mkv'
    New-Item -ItemType Directory -Path $configuredParent -Force | Out-Null
    $configuredUnavailable = Get-RerunSourceHealth -SourcePath $configuredMissingSource -ConfiguredRootPath $configuredMovies -ExpectedContentSha256 ('9' * 64) -FfprobePath ''
    Assert-Equal $configuredUnavailable.Code 'source_location_unavailable' 'An absent configured library root was flattened into a missing leaf.'
    Assert-True $configuredUnavailable.Retryable 'An absent configured library root should enter bounded recovery.'
    New-Item -ItemType Directory -Path $configuredMovies -Force | Out-Null
    $configuredLeafMissing = Get-RerunSourceHealth -SourcePath $configuredMissingSource -ConfiguredRootPath $configuredMovies -ExpectedContentSha256 ('9' * 64) -FfprobePath ''
    Assert-Equal $configuredLeafMissing.Code 'source_missing' 'A missing leaf under a reachable configured root was not terminally classified.'
    Assert-False $configuredLeafMissing.Retryable 'A missing leaf under a reachable configured root must not enter outage retries.'

    $nestedConfiguredRoot = Join-Path $configuredMovies 'Priority'
    $configuredRootConfig = @{
        SourceMovies = $configuredMovies
        SourceTV = (Join-Path $configuredParent 'TV')
        LibraryProfiles = @(
            @{ id = 'broad'; source_path = $configuredParent }
            @{ id = 'priority'; source_path = $nestedConfiguredRoot }
        )
    }
    $longestConfiguredRoot = Resolve-RerunConfiguredSourceRoot -Config $configuredRootConfig -SourcePath (Join-Path $nestedConfiguredRoot 'Movie.mkv')
    Assert-Equal $longestConfiguredRoot ([System.IO.Path]::GetFullPath($nestedConfiguredRoot)) 'Configured-root resolution did not choose the longest matching LibraryProfile root.'

    $timeoutSource = Join-Path $healthyRoot 'Timeout Probe.mkv'
    [System.IO.File]::WriteAllBytes($timeoutSource, [System.Text.Encoding]::UTF8.GetBytes('timeout-probe'))
    $timeoutIdentity = Get-RerunSourceIdentityV2 -FileInfo (Get-Item -LiteralPath $timeoutSource) -FfprobePath ''
    $timeoutContentSha256 = Get-RerunContentSha256 -Path $timeoutSource
    $timeoutStarted = [datetime]::UtcNow
    $timeoutHealth = Get-RerunSourceHealth -SourcePath $timeoutSource -ExpectedIdentityV2 $timeoutIdentity -FfprobePath '' -ProbeTimeoutSeconds 1 -IdentityTimeoutSeconds 2 -SimulatedProbeDelayMilliseconds 2500
    $timeoutElapsed = ([datetime]::UtcNow - $timeoutStarted).TotalSeconds
    Assert-Equal $timeoutHealth.Code 'source_access_failed' 'Timed-out source probe was not typed as a bounded access failure.'
    Assert-True $timeoutHealth.Retryable 'Timed-out source access should enter bounded retry.'
    Assert-True ($timeoutElapsed -lt 5) "Timed-out source probe exceeded its hard bound: $timeoutElapsed seconds."

    $accessRetryPlan = [pscustomobject][ordered]@{
        row_index = 9
        source_path = $timeoutSource
        source_identity_v2 = $timeoutIdentity
        planned_source_identity_v2 = $timeoutIdentity
        source_content_sha256 = $timeoutContentSha256
        planned_source_content_sha256 = $timeoutContentSha256
        source_content_sha256_algorithm = 'sha256-full-file'
        status = 'waiting'
        lifecycle_state = 'waiting'
        attempt_count = 0
        timeline = @()
    }
    $accessRetry = Invoke-RerunSourceAvailabilityRecovery -Plan $accessRetryPlan -MaxAttempts 2 -BackoffSeconds @(0) -FfprobePath '' -ProbeTimeoutSeconds 1 -IdentityTimeoutSeconds 2 -SimulatedProbeDelayMilliseconds 2500 -SleepAction { param([int]$Seconds) }
    Assert-False $accessRetry.Ready 'Simulated access timeout unexpectedly became ready.'
    Assert-Equal $accessRetryPlan.status 'retry_exhausted' 'Timed-out access did not exhaust bounded retries.'
    Assert-Equal $accessRetryPlan.reason_code 'source_access_failed' 'Timed-out access lost its stable reason code.'
    Assert-Equal $accessRetryPlan.attempt_count 2 'Timed-out access did not persist every bounded attempt.'
    Assert-True $accessRetryPlan.operator_action_required 'Exhausted permission/access failure must require operator action.'
    Assert-True ([string]$accessRetryPlan.available_operator_action -match 'Retry') 'Exhausted access failure omitted durable retry guidance.'

    $missingAlgorithmPlan = [pscustomobject][ordered]@{
        row_index = 10
        source_path = $timeoutSource
        source_identity_v2 = $timeoutIdentity
        planned_source_identity_v2 = $timeoutIdentity
        source_content_sha256 = $timeoutContentSha256
        planned_source_content_sha256 = $timeoutContentSha256
        status = 'waiting'
        lifecycle_state = 'waiting'
        attempt_count = 0
        timeline = @()
    }
    $missingAlgorithmRecovery = Invoke-RerunSourceAvailabilityRecovery -Plan $missingAlgorithmPlan -MaxAttempts 1 -BackoffSeconds @(0) -FfprobePath '' -SleepAction { param([int]$Seconds) }
    Assert-False $missingAlgorithmRecovery.Ready 'A row without an authoritative hash algorithm unexpectedly became recoverable.'
    Assert-Equal $missingAlgorithmPlan.status 'review' 'A row without source_content_sha256_algorithm did not fail closed to review.'
    Assert-Equal $missingAlgorithmPlan.reason_code 'source_content_sha256_algorithm_invalid' 'Missing hash-algorithm evidence lost its stable reason code.'
    Assert-Equal $missingAlgorithmPlan.attempt_count 0 'A row without authoritative hash-algorithm evidence consumed source retries.'

    # Reconnect accepts only the same full v2 identity; same-size changed bytes are rejected.
    $driveBacking = Join-Path $root 'DriveBacking'
    New-Item -ItemType Directory -Path (Join-Path $driveBacking 'Library') -Force | Out-Null
    $backingSource = Join-Path $driveBacking 'Library\Reconnect Movie.mkv'
    [System.IO.File]::WriteAllBytes($backingSource, [System.Text.Encoding]::UTF8.GetBytes('same-size-a'))
    $expectedIdentity = Get-RerunSourceIdentityV2 -FileInfo (Get-Item -LiteralPath $backingSource) -FfprobePath ''
    Set-RerunFixtureDriveOnline -DriveName $driveName -BackingPath $driveBacking
    try {
        $reconnectedPath = "${driveName}:\Library\Reconnect Movie.mkv"
        $same = Get-RerunSourceHealth -SourcePath $reconnectedPath -ExpectedIdentityV2 $expectedIdentity -FfprobePath ''
        Assert-Equal $same.Code 'available' 'Reconnect with the original identity should be accepted.'
        Assert-Equal $same.IdentityV2 $expectedIdentity 'Reconnect did not recompute the expected full identity.'

        [System.IO.File]::WriteAllBytes($backingSource, [System.Text.Encoding]::UTF8.GetBytes('same-size-b'))
        $changed = Get-RerunSourceHealth -SourcePath $reconnectedPath -ExpectedIdentityV2 $expectedIdentity -FfprobePath ''
        Assert-Equal $changed.Code 'source_identity_changed' 'Same-size replacement was not rejected on reconnect.'
        Assert-False $changed.Retryable 'Identity changes must route to review rather than automatic retry.'
    } finally {
        Set-RerunFixtureDriveOffline -DriveName $driveName -ReservationPath $driveReservationPath
    }

    # The additive full-content hash must detect changed middle bytes that the legacy sampled fingerprint cannot see.
    $middleChangedSource = Join-Path $root 'Middle Changed.mkv'
    $middleBytes = [byte[]]::new(4MB)
    for ($byteIndex = 0; $byteIndex -lt $middleBytes.Length; $byteIndex += 65537) {
        $middleBytes[$byteIndex] = [byte]($byteIndex % 251)
    }
    [System.IO.File]::WriteAllBytes($middleChangedSource, $middleBytes)
    $middleItem = Get-Item -LiteralPath $middleChangedSource
    $middleMtime = $middleItem.LastWriteTimeUtc
    $middleSampleIdentity = Get-RerunSourceIdentityV2 -FileInfo $middleItem -FfprobePath ''
    $middleContentSha256 = Get-RerunContentSha256 -Path $middleChangedSource
    $middleFullHashBefore = (Get-FileHash -LiteralPath $middleChangedSource -Algorithm SHA256).Hash
    $middleStream = [System.IO.File]::Open($middleChangedSource, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::Read)
    try {
        $middleStream.Position = 2MB
        $priorMiddleByte = $middleStream.ReadByte()
        $middleStream.Position = 2MB
        $middleStream.WriteByte([byte](($priorMiddleByte + 1) % 256))
    } finally {
        $middleStream.Dispose()
    }
    [System.IO.File]::SetLastWriteTimeUtc($middleChangedSource, $middleMtime)
    $middleChangedItem = Get-Item -LiteralPath $middleChangedSource
    Assert-Equal (Get-RerunSourceIdentityV2 -FileInfo $middleChangedItem -FfprobePath '') $middleSampleIdentity 'Middle-byte fixture unexpectedly changed the legacy sampled v2 fingerprint.'
    Assert-True ((Get-FileHash -LiteralPath $middleChangedSource -Algorithm SHA256).Hash -ne $middleFullHashBefore) 'Middle-byte fixture did not change the full source hash.'
    $middleChangedHealth = Get-RerunSourceHealth -SourcePath $middleChangedSource -ExpectedIdentityV2 $middleSampleIdentity -ExpectedContentSha256 $middleContentSha256 -ExpectedSize $middleChangedItem.Length -ExpectedMtimeUtc $middleMtime.ToString('o') -FfprobePath ''
    Assert-Equal $middleChangedHealth.Code 'source_identity_changed' 'Same-size/same-mtime middle-byte replacement bypassed strong reconnect identity.'
    Assert-False $middleChangedHealth.Retryable 'Strong content-hash mismatch must route to review.'

    # Interrupted copy cleanup is attempt-scoped and cannot escape the batch scratch root.
    $batchScratch = Join-Path $root 'BatchScratch'
    $anchorRoute = Join-Path $root 'AnchorRoute'
    $anchorOutside = Join-Path $root 'AnchorOutside'
    $anchorLink = Join-Path $anchorRoute 'redirected-parent'
    $anchorCandidateTarget = Join-Path $anchorOutside 'candidate'
    New-Item -ItemType Directory -Path $anchorRoute, $anchorCandidateTarget -Force | Out-Null
    Assert-True (New-RerunFixtureDirectoryJunction -Path $anchorLink -Target $anchorOutside) 'Unable to create the trusted-anchor ancestor-junction fixture.'
    $anchorCandidate = Join-Path $anchorLink 'candidate'
    $anchorRejected = $false
    $anchorError = ''
    try {
        Assert-RerunScratchTrustAnchor -Path $anchorCandidate | Out-Null
    } catch {
        $anchorRejected = $true
        $anchorError = [string]$_.Exception.Message
    }
    Assert-True ($anchorRejected -and $anchorError -match 'scratch path boundary rejected') "Trusted-anchor derivation did not reject an ancestor junction: $anchorError"

    $attemptId = 'attempt-1234'
    $attemptDir = Join-Path $batchScratch ".mediapipeline-rerun-staging\$attemptId"
    $partial = Join-Path $batchScratch "Movies\Movie.mkv.rerun-partial.$attemptId"
    New-Item -ItemType Directory -Path $attemptDir -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $partial) -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $attemptDir 'Movie.mkv') -Value 'partial' -Encoding ASCII
    Set-Content -LiteralPath $partial -Value 'partial' -Encoding ASCII
    $outside = Join-Path $root "outside.rerun-partial.$attemptId"
    Set-Content -LiteralPath $outside -Value 'must survive' -Encoding ASCII

    Clear-RerunStageAttemptArtifacts -BatchScratchRoot $batchScratch -AttemptId $attemptId
    Assert-False (Test-Path -LiteralPath $attemptDir) 'Interrupted attempt directory was not cleaned.'
    Assert-False (Test-Path -LiteralPath $partial) 'Interrupted attempt partial was not cleaned.'
    Assert-True (Test-Path -LiteralPath $outside -PathType Leaf) 'Attempt cleanup escaped the batch scratch boundary.'

    # Bounded outage recovery records waiting/retry/exhaustion and never spins forever.
    $retryPlan = [pscustomobject][ordered]@{
        row_index = 0
        source_path = $offlineSource
        source_identity_v2 = ('c' * 64)
        source_content_sha256 = ('d' * 64)
        planned_source_content_sha256 = ('d' * 64)
        source_content_sha256_algorithm = 'sha256-full-file'
        status = 'waiting'
        lifecycle_state = 'waiting'
        attempt_count = 0
        max_attempts = 2
        timeline = @()
    }
    $retryResult = Invoke-RerunSourceAvailabilityRecovery `
        -Plan $retryPlan `
        -MaxAttempts 2 `
        -BackoffSeconds @(0) `
        -FfprobePath '' `
        -SleepAction { param([int]$Seconds) }
    Assert-False $retryResult.Ready 'Permanently offline fixture unexpectedly became ready.'
    Assert-Equal $retryPlan.status 'retry_exhausted' 'Bounded retry did not end in retry_exhausted.'
    Assert-Equal $retryPlan.attempt_count 2 'Retry attempt count was not persisted.'
    Assert-Equal $retryPlan.reason_code 'source_location_unavailable' 'Retry exhaustion lost the underlying reason code.'
    Assert-True $retryPlan.operator_action_required 'Retry exhaustion must require an explicit operator action.'
    Assert-True (@($retryPlan.timeline | Where-Object { $_.state -eq 'retry_scheduled' }).Count -ge 1) 'Retry schedule transition was not recorded.'

    $legacyOfflinePlan = [pscustomobject][ordered]@{
        row_index = 11
        source_path = $offlineSource
        source_identity_v2 = ('e' * 64)
        planned_source_identity_v2 = ('e' * 64)
        status = 'waiting'
        lifecycle_state = 'waiting'
        attempt_count = 0
        timeline = @()
    }
    $legacyOfflineRecovery = Invoke-RerunSourceAvailabilityRecovery -Plan $legacyOfflinePlan -MaxAttempts 1 -BackoffSeconds @(0) -FfprobePath '' -SleepAction { param([int]$Seconds) }
    Assert-False $legacyOfflineRecovery.Ready 'Legacy offline row without a strong hash unexpectedly became recoverable.'
    Assert-Equal $legacyOfflinePlan.status 'review' 'Legacy offline row without source_content_sha256 did not fail closed to review.'
    Assert-Equal $legacyOfflinePlan.attempt_count 0 'Legacy offline row consumed retries without provable full-content identity.'

    $legacyReconnectInfo = Get-Item -LiteralPath $timeoutSource
    $legacyReconnectIdentity = Get-RerunSourceIdentityV2 -FileInfo $legacyReconnectInfo -FfprobePath ''
    $legacyReconnectPlan = [pscustomobject][ordered]@{
        row_index = 12
        source_path = $timeoutSource
        source_root = (Split-Path -Parent $timeoutSource)
        source_identity_v2 = $legacyReconnectIdentity
        planned_source_identity_v2 = $legacyReconnectIdentity
        source_size = [long]$legacyReconnectInfo.Length
        source_mtime_utc = $legacyReconnectInfo.LastWriteTimeUtc.ToString('o')
        status = 'waiting'
        lifecycle_state = 'waiting'
        attempt_count = 1
        transition_sequence = 1
        timeline = @([pscustomobject]@{ sequence = 1; state = 'waiting' })
    }
    $legacyReconnectRecovery = Invoke-RerunSourceAvailabilityRecovery -Plan $legacyReconnectPlan -MaxAttempts 1 -BackoffSeconds @(0) -FfprobePath '' -SleepAction { param([int]$Seconds) }
    Assert-False $legacyReconnectRecovery.Ready 'Legacy waiting row established a new strong-hash baseline after the source reconnected.'
    Assert-Equal $legacyReconnectPlan.status 'review' 'Legacy reconnect without a pre-outage full hash did not fail closed to review.'
    Assert-Equal $legacyReconnectPlan.reason_code 'source_content_sha256_missing' 'Legacy reconnect lost the missing-strong-identity reason code.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$legacyReconnectPlan.source_content_sha256)) 'Legacy reconnect synthesized source_content_sha256 after the outage.'

    # A verified staged copy remains runnable after the original source drops.
    $stagePath = Join-Path $batchScratch 'Movies\Verified Stage.mkv'
    New-Item -ItemType Directory -Path (Split-Path -Parent $stagePath) -Force | Out-Null
    [System.IO.File]::WriteAllBytes($stagePath, [System.Text.Encoding]::UTF8.GetBytes('verified-stage'))
    $stageIdentity = Get-RerunSourceIdentityV2 -FileInfo (Get-Item -LiteralPath $stagePath) -FfprobePath ''
    $stageContentSha256 = Get-RerunContentSha256 -Path $stagePath
    $stagedPlan = [pscustomobject][ordered]@{
        row_index = 1
        source_path = (Join-Path $root 'now-offline\Original.mkv')
        stage_path = $stagePath
        status = 'staged'
        lifecycle_state = 'staged'
        source_size = (Get-Item -LiteralPath $stagePath).Length
        planned_source_identity_v2 = $stageIdentity
        staged_source_identity_v2 = $stageIdentity
        source_content_sha256 = $stageContentSha256
        planned_source_content_sha256 = $stageContentSha256
        staged_source_content_sha256 = $stageContentSha256
        source_content_sha256_algorithm = 'sha256-full-file'
    }
    $stagedDisposition = Get-RerunResumeDisposition -Plan $stagedPlan -BatchScratchRoot $batchScratch -FfprobePath ''
    Assert-Equal $stagedDisposition.Action 'resume_staged' 'Verified staged scratch should continue without the source root.'

    # A hard kill can occur after atomic promotion but before the staged transition is persisted.
    $promotedCrashPath = Join-Path $batchScratch 'Movies\Promoted Before Manifest.mkv'
    [System.IO.File]::WriteAllBytes($promotedCrashPath, [System.Text.Encoding]::UTF8.GetBytes('promoted-before-manifest'))
    $promotedCrashIdentity = Get-RerunSourceIdentityV2 -FileInfo (Get-Item -LiteralPath $promotedCrashPath) -FfprobePath ''
    $promotedCrashContentSha256 = Get-RerunContentSha256 -Path $promotedCrashPath
    $promotedCrashPlan = [pscustomobject][ordered]@{
        row_index = 6
        source_path = $offlineSource
        stage_path = $promotedCrashPath
        status = 'staging'
        lifecycle_state = 'staging'
        stage_attempt_id = [guid]::NewGuid().ToString('N')
        source_size = (Get-Item -LiteralPath $promotedCrashPath).Length
        planned_source_identity_v2 = $promotedCrashIdentity
        staged_source_identity_v2 = ''
        source_content_sha256 = $promotedCrashContentSha256
        planned_source_content_sha256 = $promotedCrashContentSha256
        staged_source_content_sha256 = ''
        source_content_sha256_algorithm = 'sha256-full-file'
        nested_launch_count = 0
        transition_sequence = 2
        timeline = @([pscustomobject]@{ sequence = 2; state = 'staging' })
    }
    $promotedCrashDisposition = Get-RerunResumeDisposition -Plan $promotedCrashPlan -BatchScratchRoot $batchScratch -FfprobePath ''
    Assert-Equal $promotedCrashDisposition.Action 'resume_staged' 'A verified final stage file was discarded as an interrupted staging attempt.'
    Assert-True (Test-Path -LiteralPath $promotedCrashPath -PathType Leaf) 'Recovery removed the atomically promoted final stage file.'

    $promotedCrashFresh = [pscustomobject]@{ row_index = 6; source_path = $offlineSource; source_identity_v2 = $promotedCrashIdentity; planned_source_identity_v2 = $promotedCrashIdentity; source_content_sha256 = $promotedCrashContentSha256; planned_source_content_sha256 = $promotedCrashContentSha256; source_content_sha256_algorithm = 'sha256-full-file'; status = 'waiting'; lifecycle_state = 'waiting'; nested_launch_count = 0; timeline = @() }
    $promotedCrashMerged = @(Merge-RerunResumePlans -FreshPlans @($promotedCrashFresh) -ExistingManifest ([pscustomobject]@{ rows = @($promotedCrashPlan) }) -BatchScratchRoot $batchScratch -FfprobePath '')[0]
    Assert-Equal $promotedCrashMerged.status 'staged' 'Verified post-promotion recovery did not bypass the offline source.'
    Assert-Equal $promotedCrashMerged.lifecycle_state 'staged' 'Verified post-promotion recovery did not restore staged lifecycle evidence.'
    Assert-Equal $promotedCrashMerged.nested_launch_count 0 'Post-promotion recovery invented prior nested-launch evidence.'
    Assert-True (Test-Path -LiteralPath $promotedCrashMerged.stage_path -PathType Leaf) 'Post-promotion recovery lost the verified final stage path.'

    $processingPlan = [pscustomobject]@{ row_index = 2; status = 'processing'; lifecycle_state = 'processing' }
    $processingDisposition = Get-RerunResumeDisposition -Plan $processingPlan -BatchScratchRoot $batchScratch -FfprobePath ''
    Assert-Equal $processingDisposition.Action 'review' 'Ambiguous post-launch processing state must route to review.'

    $staleStagedPlan = $stagedPlan | Select-Object *
    $staleStagedPlan | Add-Member -NotePropertyName nested_launch_count -NotePropertyValue 1 -Force
    $staleStagedDisposition = Get-RerunResumeDisposition -Plan $staleStagedPlan -BatchScratchRoot $batchScratch -FfprobePath ''
    Assert-Equal $staleStagedDisposition.Action 'review' 'Stale staged progress with prior nested-launch evidence must not launch twice.'

    $existingWaiting = [pscustomobject]@{ row_index = 7; source_path = $offlineSource; source_identity_v2 = ('7' * 64); planned_source_identity_v2 = ('7' * 64); status = 'waiting'; lifecycle_state = 'waiting'; transition_sequence = 1; timeline = @([pscustomobject]@{ sequence = 1; state = 'waiting' }) }
    $freshReview = [pscustomobject]@{ row_index = 7; source_path = $offlineSource; source_identity_v2 = ('7' * 64); planned_source_identity_v2 = ''; status = 'review'; lifecycle_state = 'review'; reason_code = 'source_access_failed'; what = 'Current planning requires review.'; why = 'Current source evidence is not safely recoverable.'; next = 'Review current source evidence.'; timeline = @() }
    $reviewMerge = @(Merge-RerunResumePlans -FreshPlans @($freshReview) -ExistingManifest ([pscustomobject]@{ rows = @($existingWaiting) }) -BatchScratchRoot $batchScratch -FfprobePath '')[0]
    Assert-Equal $reviewMerge.status 'review' 'Resume merge overwrote the current planning review status.'
    Assert-Equal $reviewMerge.lifecycle_state 'review' 'Resume merge lifecycle did not retain the current planning state.'
    Assert-Equal $reviewMerge.timeline[-1].state 'review' 'Resume merge timeline does not match its current lifecycle state.'

    $legacyMergeExisting = [pscustomobject]@{ row_index = 13; source_path = $timeoutSource; source_identity_v2 = $legacyReconnectIdentity; planned_source_identity_v2 = $legacyReconnectIdentity; status = 'waiting'; lifecycle_state = 'waiting'; transition_sequence = 1; timeline = @([pscustomobject]@{ sequence = 1; state = 'waiting' }) }
    $legacyMergeFresh = [pscustomobject]@{ row_index = 13; source_path = $timeoutSource; source_identity_v2 = $legacyReconnectIdentity; planned_source_identity_v2 = $legacyReconnectIdentity; source_content_sha256 = $timeoutContentSha256; planned_source_content_sha256 = $timeoutContentSha256; source_content_sha256_algorithm = 'sha256-full-file'; status = 'pending'; lifecycle_state = 'accepted'; what = 'Current source is available.'; why = 'Current bytes were hashed after reconnect.'; next = 'Stage the source.'; reason_code = ''; transition_sequence = 1; timeline = @() }
    $legacyReconnectMerge = @(Merge-RerunResumePlans -FreshPlans @($legacyMergeFresh) -ExistingManifest ([pscustomobject]@{ rows = @($legacyMergeExisting) }) -BatchScratchRoot $batchScratch -FfprobePath '')[0]
    Assert-Equal $legacyReconnectMerge.status 'review' 'Restart merge adopted a new full hash for a legacy waiting row.'
    Assert-Equal $legacyReconnectMerge.reason_code 'source_content_sha256_missing' 'Restart merge did not disclose the missing pre-outage strong identity.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$legacyReconnectMerge.source_content_sha256)) 'Restart merge synthesized source_content_sha256 for a legacy waiting row.'

    $rowTerminalBatch = [pscustomobject]@{ lifecycle_state = 'destination_policy'; status = 'destination_policy'; transition_sequence = 1; timeline = @([pscustomobject]@{ sequence = 1; state = 'destination_policy' }) }
    $rowTerminalPlan = [pscustomobject]@{ row_index = 8; lifecycle_state = 'destination_policy'; status = 'complete'; transition_sequence = 1; timeline = @([pscustomobject]@{ sequence = 1; state = 'destination_policy' }) }
    Set-RerunPlanLifecycle -Plan $rowTerminalPlan -State 'terminal' -Status 'complete' -What 'Row completed.' -Why 'Destination evidence is durable.' -Next 'Continue the batch.' -ReasonCode 'complete' -Manifest $rowTerminalBatch
    Assert-Equal $rowTerminalPlan.lifecycle_state 'terminal' 'Row terminal transition was not retained at row scope.'
    Assert-Equal $rowTerminalBatch.lifecycle_state 'destination_policy' 'A row terminal transition incorrectly finalized the whole batch.'
    Assert-Equal $rowTerminalBatch.timeline[-1].state 'destination_policy' 'Batch timeline recorded a premature terminal state.'

    # Planning evidence remains authoritative when a mapped source disappears before staging.
    $dropBackingSource = Join-Path $driveBacking 'Library\Drop Before Stage.mkv'
    [System.IO.File]::WriteAllBytes($dropBackingSource, [System.Text.Encoding]::UTF8.GetBytes('drop-before-stage'))
    $dropIdentity = Get-RerunSourceIdentityV2 -FileInfo (Get-Item -LiteralPath $dropBackingSource) -FfprobePath ''
    $dropHashBefore = (Get-FileHash -LiteralPath $dropBackingSource -Algorithm SHA256).Hash
    Set-RerunFixtureDriveOnline -DriveName $driveName -BackingPath $driveBacking
    $dropSource = "${driveName}:\Library\Drop Before Stage.mkv"
    $plannedHealth = Get-RerunSourceHealth -SourcePath $dropSource -ExpectedIdentityV2 $dropIdentity -FfprobePath ''
    Assert-Equal $plannedHealth.Code 'available' 'Drop-before-stage fixture did not first reach a valid planned identity.'
    $dropStagePath = Join-Path $batchScratch 'Movies\Drop Before Stage.mkv'
    $dropPlan = [pscustomobject][ordered]@{
        row_index = 3
        source_path = $dropSource
        stage_path = $dropStagePath
        status = 'pending'
        lifecycle_state = 'accepted'
        source_size = [long]$plannedHealth.FileInfo.Length
        source_mtime_utc = $plannedHealth.FileInfo.LastWriteTimeUtc.ToString('o')
        source_identity_v2 = $dropIdentity
        planned_source_identity_v2 = $dropIdentity
        source_content_sha256 = $plannedHealth.ContentSha256
        planned_source_content_sha256 = $plannedHealth.ContentSha256
        source_content_sha256_algorithm = 'sha256-full-file'
        attempt_count = 0
        timeline = @([pscustomobject]@{ sequence = 1; state = 'accepted'; at = [datetime]::UtcNow.ToString('o') })
        transition_sequence = 1
    }
    Set-RerunFixtureDriveOffline -DriveName $driveName -ReservationPath $driveReservationPath
    $dropRecovery = Invoke-RerunSourceAvailabilityRecovery -Plan $dropPlan -MaxAttempts 1 -BackoffSeconds @(0) -FfprobePath '' -SleepAction { param([int]$Seconds) }
    Assert-False $dropRecovery.Ready 'Source removal after planning unexpectedly remained stageable.'
    Assert-Equal $dropPlan.status 'retry_exhausted' 'Source drop before staging did not persist bounded recovery evidence.'
    Assert-Equal $dropPlan.reason_code 'source_location_unavailable' 'Mapped-drive removal lost its location-outage classification.'
    Assert-False (Test-Path -LiteralPath $dropStagePath) 'Source drop before staging left an accepted staged file.'
    Assert-Equal (Get-FileHash -LiteralPath $dropBackingSource -Algorithm SHA256).Hash $dropHashBefore 'Source changed during drop-before-stage recovery.'

    # A real attempt promotion interruption cleans its own partial and cannot touch source/outside files.
    $promotionSource = Join-Path $root 'Promotion Source.mkv'
    [System.IO.File]::WriteAllBytes($promotionSource, [System.Text.Encoding]::UTF8.GetBytes('promotion-source-bytes'))
    $promotionHash = (Get-FileHash -LiteralPath $promotionSource -Algorithm SHA256).Hash
    $promotionAttempt = 'promotion-interrupt'
    $promotionAttemptDir = Join-Path $batchScratch ".mediapipeline-rerun-staging\$promotionAttempt"
    New-Item -ItemType Directory -Path $promotionAttemptDir -Force | Out-Null
    $landed = Join-Path $promotionAttemptDir 'Promotion Source.mkv'
    [System.IO.File]::Copy($promotionSource, $landed)
    $promotionDestination = Join-Path $batchScratch 'Movies\Promotion Source.mkv'
    $promotionPartial = "$promotionDestination.rerun-partial.$promotionAttempt"
    $promotionInterrupted = $false
    try {
        Move-RerunStageAttemptToDestination -LandedPath $landed -PartialPath $promotionPartial -Destination $promotionDestination -BatchScratchRoot $batchScratch -ScratchTrustRoot $root -BeforeFinalMove {
            param($PartialPath, $DestinationPath)
            throw 'simulated interruption after partial promotion'
        }
    } catch {
        $promotionInterrupted = ($_.Exception.Message -match 'simulated interruption')
    }
    Assert-True $promotionInterrupted 'Real attempt-promotion interruption was not exercised.'
    Assert-False (Test-Path -LiteralPath $promotionPartial) 'Interrupted promotion left its attempt partial behind.'
    Assert-False (Test-Path -LiteralPath $promotionDestination) 'Interrupted promotion exposed an unverified final staged file.'
    Assert-True (Test-Path -LiteralPath $outside -PathType Leaf) 'Interrupted promotion removed an outside sentinel.'
    Assert-Equal (Get-FileHash -LiteralPath $promotionSource -Algorithm SHA256).Hash $promotionHash 'Interrupted promotion mutated the source fixture.'

    # Losing boundary proof after the first move must preserve the real partial
    # and must never follow the swapped parent to delete an outside sentinel.
    $swapAttempt = 'promotion-boundary-swap'
    $swapAttemptDir = Join-Path $batchScratch ".mediapipeline-rerun-staging\$swapAttempt"
    New-Item -ItemType Directory -Path $swapAttemptDir -Force | Out-Null
    $swapLanded = Join-Path $swapAttemptDir 'Promotion Source.mkv'
    [System.IO.File]::Copy($promotionSource, $swapLanded)
    $swapParent = Join-Path $batchScratch 'BoundarySwapMovies'
    New-Item -ItemType Directory -Path $swapParent -Force | Out-Null
    $swapDestination = Join-Path $swapParent 'Promotion Source.mkv'
    $swapPartial = "$swapDestination.rerun-partial.$swapAttempt"
    $swapDisplacedParent = "$swapParent.displaced"
    $swapOutside = Join-Path $root 'BoundarySwapOutside'
    New-Item -ItemType Directory -Path $swapOutside -Force | Out-Null
    $swapOutsideSentinel = Join-Path $swapOutside (Split-Path -Leaf $swapPartial)
    $script:RerunRecoverySwapParent = $swapParent
    $script:RerunRecoverySwapDisplacedParent = $swapDisplacedParent
    $script:RerunRecoverySwapOutside = $swapOutside
    $script:RerunRecoverySwapOutsideSentinel = $swapOutsideSentinel
    $swapError = ''
    try {
        Move-RerunStageAttemptToDestination `
            -LandedPath $swapLanded `
            -PartialPath $swapPartial `
            -Destination $swapDestination `
            -BatchScratchRoot $batchScratch `
            -ScratchTrustRoot $root `
            -BeforeFinalMove {
                param($PartialPath, $DestinationPath)
                Move-Item -LiteralPath $script:RerunRecoverySwapParent -Destination $script:RerunRecoverySwapDisplacedParent -ErrorAction Stop
                if (-not (New-RerunFixtureDirectoryJunction -Path $script:RerunRecoverySwapParent -Target $script:RerunRecoverySwapOutside)) {
                    throw 'unable to create post-move boundary-swap junction'
                }
                [System.IO.File]::WriteAllText($script:RerunRecoverySwapOutsideSentinel, 'outside partial sentinel must survive', [System.Text.UTF8Encoding]::new($false))
            }
    } catch {
        $swapError = [string]$_.Exception.Message
    }
    $swapOutsideSurvived = Test-Path -LiteralPath $swapOutsideSentinel -PathType Leaf
    $swapDisplacedPartial = Join-Path $swapDisplacedParent (Split-Path -Leaf $swapPartial)
    $swapPartialPreserved = Test-Path -LiteralPath $swapDisplacedPartial -PathType Leaf
    if (Test-Path -LiteralPath $swapParent) { Remove-Item -LiteralPath $swapParent -Force -ErrorAction Stop }
    if (Test-Path -LiteralPath $swapDisplacedParent -PathType Container) {
        Move-Item -LiteralPath $swapDisplacedParent -Destination $swapParent -ErrorAction Stop
    }
    Assert-True ($swapError -match '^rerun_scratch_cleanup_ambiguous:') "Post-move boundary loss did not emit typed cleanup ambiguity: $swapError"
    Assert-True $swapOutsideSurvived 'Post-move boundary-loss cleanup followed the junction and removed the outside sentinel.'
    Assert-True $swapPartialPreserved 'Post-move boundary-loss cleanup removed the real attempt partial instead of preserving evidence.'
    Assert-Equal (Get-FileHash -LiteralPath $promotionSource -Algorithm SHA256).Hash $promotionHash 'Post-move boundary-loss handling mutated the source fixture.'

    $unexpectedAttemptDir = Join-Path $batchScratch '.mediapipeline-rerun-staging\unexpected-content'
    $unexpectedLanded = Join-Path $unexpectedAttemptDir 'Promotion Source.mkv'
    $unexpectedSentinel = Join-Path $unexpectedAttemptDir 'operator-evidence.txt'
    $unexpectedPartial = Join-Path $batchScratch 'Movies\Promotion Source.mkv.rerun-partial.unexpected-content'
    New-Item -ItemType Directory -Path $unexpectedAttemptDir -Force | Out-Null
    [System.IO.File]::Copy($promotionSource, $unexpectedLanded)
    [System.IO.File]::WriteAllText($unexpectedSentinel, 'unexpected evidence must survive', [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($unexpectedPartial, 'attempt partial must survive ambiguous cleanup', [System.Text.UTF8Encoding]::new($false))
    $unexpectedCleanupError = ''
    try {
        Clear-RerunCopyAttemptArtifacts `
            -AttemptDirectory $unexpectedAttemptDir `
            -ExpectedLandedPath $unexpectedLanded `
            -PartialPath $unexpectedPartial `
            -BatchScratchRoot $batchScratch `
            -ScratchTrustRoot $root
    } catch {
        $unexpectedCleanupError = [string]$_.Exception.Message
    }
    Assert-True ($unexpectedCleanupError -match '^rerun_scratch_cleanup_ambiguous:') "Unexpected attempt contents were not classified as cleanup ambiguity: $unexpectedCleanupError"
    Assert-True (Test-Path -LiteralPath $unexpectedLanded -PathType Leaf) 'Ambiguous cleanup removed the expected landed evidence.'
    Assert-True (Test-Path -LiteralPath $unexpectedSentinel -PathType Leaf) 'Ambiguous cleanup recursively removed unexpected attempt evidence.'
    Assert-True (Test-Path -LiteralPath $unexpectedPartial -PathType Leaf) 'Ambiguous cleanup partially mutated attempt evidence before validation completed.'
    Remove-Item -LiteralPath $unexpectedPartial -Force
    Remove-Item -LiteralPath $unexpectedAttemptDir -Recurse -Force

    # Caller-supplied attempt tokens cannot traverse outside staging or trigger recursive cleanup there.
    $unsafeAttemptStageRoot = Join-Path $batchScratch 'UnsafeAttempt'
    $unsafeAttemptDestination = Join-Path $unsafeAttemptStageRoot 'Movies\Promotion Source.mkv'
    $unsafeAttemptId = '..\..\..\AttemptEscapeVictim'
    $unsafeAttemptVictim = Join-Path $root 'AttemptEscapeVictim'
    $unsafeAttemptSentinel = Join-Path $unsafeAttemptVictim 'must-survive.txt'
    New-Item -ItemType Directory -Path $unsafeAttemptVictim -Force | Out-Null
    [System.IO.File]::WriteAllText($unsafeAttemptSentinel, 'bounded cleanup sentinel', [System.Text.UTF8Encoding]::new($false))
    $unsafeAttemptSourceInfo = Get-Item -LiteralPath $promotionSource
    $unsafeAttemptIdentity = Get-RerunSourceIdentityV2 -FileInfo $unsafeAttemptSourceInfo -FfprobePath ''
    $unsafeAttemptContentSha256 = Get-RerunContentSha256 -Path $promotionSource
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryUnsafeAttemptHookFired = $false
    $unsafeAttemptRejected = $false
    $unsafeAttemptError = ''
    try {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $script:RerunRecoveryUnsafeAttemptHookFired = $true
            return [pscustomobject]@{ ExitCode = 8; Output = ''; Error = 'unsafe attempt token reached native copy'; TimedOut = $false }
        }
        try {
            Copy-RerunFileVerified `
                -Source $promotionSource `
                -Destination $unsafeAttemptDestination `
                -MaxRetries 1 `
                -ExpectedSize $unsafeAttemptSourceInfo.Length `
                -ExpectedMtimeUtc $unsafeAttemptSourceInfo.LastWriteTimeUtc.ToString('o') `
                -ExpectedIdentityV2 $unsafeAttemptIdentity `
                -ExpectedContentSha256 $unsafeAttemptContentSha256 `
                -SourceRootPath (Split-Path -Parent $promotionSource) `
                -FfprobePath '' `
                -BatchScratchRoot $unsafeAttemptStageRoot `
                -ScratchTrustRoot $root `
                -AttemptId $unsafeAttemptId | Out-Null
        } catch {
            $unsafeAttemptRejected = $true
            $unsafeAttemptError = [string]$_.Exception.Message
        }
    } finally {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }
    $unsafeAttemptProtected = (
        $unsafeAttemptRejected -and
        $unsafeAttemptError -match 'attempt id' -and
        (-not $script:RerunRecoveryUnsafeAttemptHookFired) -and
        (Test-Path -LiteralPath $unsafeAttemptSentinel -PathType Leaf) -and
        (-not (Test-Path -LiteralPath $unsafeAttemptStageRoot))
    )
    Assert-True $unsafeAttemptProtected "Unsafe attempt ID was not rejected before filesystem/native-copy mutation: error='$unsafeAttemptError'; native_called=$($script:RerunRecoveryUnsafeAttemptHookFired); sentinel_exists=$(Test-Path -LiteralPath $unsafeAttemptSentinel); stage_root_exists=$(Test-Path -LiteralPath $unsafeAttemptStageRoot)."
    Assert-Equal (Get-FileHash -LiteralPath $promotionSource -Algorithm SHA256).Hash $promotionHash 'Unsafe attempt-ID rejection mutated the source fixture.'

    # Destructive robocopy switches are rejected before destination mutation or native invocation.
    $destructiveFlagResults = [System.Collections.Generic.List[object]]::new()
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryDestructiveNativeCalled = $false
    $promotionAttributesBeforeFlagChecks = [System.IO.File]::GetAttributes($promotionSource)
    $promotionAttributesProtected = $promotionAttributesBeforeFlagChecks -bor [System.IO.FileAttributes]::Archive
    [System.IO.File]::SetAttributes($promotionSource, $promotionAttributesProtected)
    try {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $script:RerunRecoveryDestructiveNativeCalled = $true
            $sourceCandidate = Join-Path ([string]$ArgumentList[0]) ([string]$ArgumentList[2])
            $hasArchiveResetFlag = @($ArgumentList | Where-Object { ([string]$_).Trim() -match '(?i)^/M(?:\s|:|$)' }).Count -gt 0
            if ($hasArchiveResetFlag -and (Test-Path -LiteralPath $sourceCandidate -PathType Leaf)) {
                $attributes = [System.IO.File]::GetAttributes($sourceCandidate)
                [System.IO.File]::SetAttributes($sourceCandidate, ($attributes -band (-bnot [System.IO.FileAttributes]::Archive)))
            }
            return [pscustomobject]@{ ExitCode = 8; Output = ''; Error = 'destructive flag reached native copy'; TimedOut = $false }
        }
        $destructiveIndex = 0
        foreach ($destructiveFlag in @('/M', '  /m  ', '/M:archive', '/MOV', '/move', '  /MoVe  ', '/MOV:files', " /MOVE`t:all ")) {
            $destructiveIndex++
            $destructiveRoot = Join-Path $batchScratch "DestructiveFlag$destructiveIndex"
            New-Item -ItemType Directory -Path $destructiveRoot -Force | Out-Null
            $destructiveDestination = Join-Path $destructiveRoot 'Movies\Promotion Source.mkv'
            $script:RerunRobocopyFlags = @('/J', $destructiveFlag, '/R:0', '/W:0')
            $script:RerunRecoveryDestructiveNativeCalled = $false
            $destructiveError = ''
            try {
                Copy-RerunFileVerified `
                    -Source $promotionSource `
                    -Destination $destructiveDestination `
                    -MaxRetries 1 `
                    -ExpectedSize $unsafeAttemptSourceInfo.Length `
                    -ExpectedMtimeUtc $unsafeAttemptSourceInfo.LastWriteTimeUtc.ToString('o') `
                    -ExpectedIdentityV2 $unsafeAttemptIdentity `
                    -ExpectedContentSha256 $unsafeAttemptContentSha256 `
                    -SourceRootPath (Split-Path -Parent $promotionSource) `
                    -FfprobePath '' `
                    -BatchScratchRoot $destructiveRoot `
                    -ScratchTrustRoot $root `
                    -AttemptId "destructive-$destructiveIndex" | Out-Null
            } catch {
                $destructiveError = [string]$_.Exception.Message
            }
            $destructiveFlagResults.Add([pscustomobject]@{
                Flag = $destructiveFlag
                Error = $destructiveError
                NativeCalled = [bool]$script:RerunRecoveryDestructiveNativeCalled
                DestinationParentExists = (Test-Path -LiteralPath (Split-Path -Parent $destructiveDestination))
            }) | Out-Null
        }
    } finally {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
        $script:RerunRobocopyFlags = @('/J','/R:0','/W:0','/NP','/NDL','/NFL')
    }
    $destructiveFlagsProtected = @($destructiveFlagResults | Where-Object {
        [string]$_.Error -notmatch 'destructive robocopy flag' -or $_.NativeCalled -or $_.DestinationParentExists
    }).Count -eq 0
    $destructiveFlagsProtected = (
        $destructiveFlagsProtected -and
        [System.IO.File]::GetAttributes($promotionSource) -eq $promotionAttributesProtected
    )

    # Missing boundary proof fails closed before destination mutation or native invocation.
    $boundaryUnavailableRoot = Join-Path $batchScratch 'BoundaryUnavailable'
    New-Item -ItemType Directory -Path $boundaryUnavailableRoot -Force | Out-Null
    $boundaryUnavailableDestination = Join-Path $boundaryUnavailableRoot 'Movies\Promotion Source.mkv'
    $script:RerunRecoveryOriginalBoundaryHelper = (Get-Command Test-MediaPipelinePathBoundarySafe -CommandType Function).ScriptBlock
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryBoundaryUnavailableNativeCalled = $false
    $boundaryUnavailableError = ''
    try {
        Remove-Item -LiteralPath Function:\Test-MediaPipelinePathBoundarySafe -Force
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $script:RerunRecoveryBoundaryUnavailableNativeCalled = $true
            return [pscustomobject]@{ ExitCode = 8; Output = ''; Error = 'missing boundary helper reached native copy'; TimedOut = $false }
        }
        try {
            Copy-RerunFileVerified `
                -Source $promotionSource `
                -Destination $boundaryUnavailableDestination `
                -MaxRetries 1 `
                -ExpectedSize $unsafeAttemptSourceInfo.Length `
                -ExpectedMtimeUtc $unsafeAttemptSourceInfo.LastWriteTimeUtc.ToString('o') `
                -ExpectedIdentityV2 $unsafeAttemptIdentity `
                -ExpectedContentSha256 $unsafeAttemptContentSha256 `
                -SourceRootPath (Split-Path -Parent $promotionSource) `
                -FfprobePath '' `
                -BatchScratchRoot $boundaryUnavailableRoot `
                -ScratchTrustRoot $root `
                -AttemptId 'boundary-unavailable' | Out-Null
        } catch {
            $boundaryUnavailableError = [string]$_.Exception.Message
        }
    } finally {
        Set-Item -LiteralPath Function:\Test-MediaPipelinePathBoundarySafe -Value $script:RerunRecoveryOriginalBoundaryHelper
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }
    $boundaryUnavailableProtected = (
        $boundaryUnavailableError -match 'boundary helper is unavailable' -and
        (-not $script:RerunRecoveryBoundaryUnavailableNativeCalled) -and
        (-not (Test-Path -LiteralPath (Split-Path -Parent $boundaryUnavailableDestination)))
    )

    # Every mutation-bearing copy path is submitted to the shared reparse-aware boundary helper.
    $boundaryRecordingRoot = Join-Path $batchScratch 'BoundaryRecording'
    New-Item -ItemType Directory -Path $boundaryRecordingRoot -Force | Out-Null
    $boundaryRecordingDestination = Join-Path $boundaryRecordingRoot 'Movies\Promotion Source.mkv'
    $boundaryRecordingAttempt = 'boundary-recording'
    $boundaryRecordingAttemptDir = Join-Path $boundaryRecordingRoot ".mediapipeline-rerun-staging\$boundaryRecordingAttempt"
    $boundaryRecordingLanded = Join-Path $boundaryRecordingAttemptDir 'Promotion Source.mkv'
    $boundaryRecordingPartial = "$boundaryRecordingDestination.rerun-partial.$boundaryRecordingAttempt"
    $script:RerunRecoveryOriginalBoundaryHelper = (Get-Command Test-MediaPipelinePathBoundarySafe -CommandType Function).ScriptBlock
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryBoundaryPaths = [System.Collections.Generic.List[string]]::new()
    try {
        Set-Item -LiteralPath Function:\Test-MediaPipelinePathBoundarySafe -Value {
            param(
                [Parameter(Mandatory)] [string]$Path,
                [Parameter(Mandatory)] [string]$Root,
                [switch]$AllowMissingLeaf,
                [switch]$AllowRootTarget
            )
            $script:RerunRecoveryBoundaryPaths.Add([System.IO.Path]::GetFullPath($Path)) | Out-Null
            return & $script:RerunRecoveryOriginalBoundaryHelper @PSBoundParameters
        }
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            return [pscustomobject]@{ ExitCode = 8; Output = ''; Error = 'record boundary paths'; TimedOut = $false }
        }
        Copy-RerunFileVerified `
            -Source $promotionSource `
            -Destination $boundaryRecordingDestination `
            -MaxRetries 1 `
            -ExpectedSize $unsafeAttemptSourceInfo.Length `
            -ExpectedMtimeUtc $unsafeAttemptSourceInfo.LastWriteTimeUtc.ToString('o') `
            -ExpectedIdentityV2 $unsafeAttemptIdentity `
            -ExpectedContentSha256 $unsafeAttemptContentSha256 `
            -SourceRootPath (Split-Path -Parent $promotionSource) `
            -FfprobePath '' `
            -BatchScratchRoot $boundaryRecordingRoot `
            -ScratchTrustRoot $root `
            -AttemptId $boundaryRecordingAttempt | Out-Null
    } finally {
        Set-Item -LiteralPath Function:\Test-MediaPipelinePathBoundarySafe -Value $script:RerunRecoveryOriginalBoundaryHelper
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }
    $boundaryPathsProtected = @(
        $boundaryRecordingAttemptDir,
        $boundaryRecordingLanded,
        $boundaryRecordingPartial,
        $boundaryRecordingDestination
    ) | Where-Object { $script:RerunRecoveryBoundaryPaths -notcontains [System.IO.Path]::GetFullPath($_) }
    $boundaryPathsProtected = @($boundaryPathsProtected).Count -eq 0

    # A real junction/symlink destination must be rejected before any write through its target.
    $reparseStageRoot = Join-Path $batchScratch 'ReparseStage'
    $reparseOutsideRoot = Join-Path $root 'ReparseOutside'
    $reparseLink = Join-Path $reparseStageRoot 'Movies'
    New-Item -ItemType Directory -Path $reparseStageRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $reparseOutsideRoot -Force | Out-Null
    $reparseCreated = $false
    try {
        New-Item -ItemType SymbolicLink -Path $reparseLink -Target $reparseOutsideRoot -ErrorAction Stop | Out-Null
        $reparseCreated = $true
    } catch {
        try {
            & cmd.exe /d /c "mklink /J `"$reparseLink`" `"$reparseOutsideRoot`"" | Out-Null
            $reparseCreated = ($LASTEXITCODE -eq 0)
        } catch {
            $reparseCreated = $false
        }
    }
    $reparseDestination = if ($reparseCreated) { Join-Path $reparseLink 'Promotion Source.mkv' } else { Join-Path $reparseStageRoot 'Movies\Promotion Source.mkv' }
    $reparseOutsideProduced = Join-Path $reparseOutsideRoot 'Promotion Source.mkv'
    $script:RerunRecoveryOriginalBoundaryHelper = (Get-Command Test-MediaPipelinePathBoundarySafe -CommandType Function).ScriptBlock
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryReparseNativeCalled = $false
    $script:RerunRecoveryReparseSource = $promotionSource
    $reparseError = ''
    try {
        if (-not $reparseCreated) {
            Set-Item -LiteralPath Function:\Test-MediaPipelinePathBoundarySafe -Value {
                param(
                    [Parameter(Mandatory)] [string]$Path,
                    [Parameter(Mandatory)] [string]$Root,
                    [switch]$AllowMissingLeaf,
                    [switch]$AllowRootTarget
                )
                return [pscustomobject]@{ Ok = $false; ReasonCode = 'REPARSE_POINT_COMPONENT'; Reason = 'deterministic reparse fixture'; Path = $Path; Root = $Root; ReparsePath = $Path }
            }
        }
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $script:RerunRecoveryReparseNativeCalled = $true
            $landedPath = Join-Path ([string]$ArgumentList[1]) ([string]$ArgumentList[2])
            [System.IO.File]::Copy($script:RerunRecoveryReparseSource, $landedPath, $true)
            return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = ''; TimedOut = $false }
        }
        try {
            Copy-RerunFileVerified `
                -Source $promotionSource `
                -Destination $reparseDestination `
                -MaxRetries 1 `
                -ExpectedSize $unsafeAttemptSourceInfo.Length `
                -ExpectedMtimeUtc $unsafeAttemptSourceInfo.LastWriteTimeUtc.ToString('o') `
                -ExpectedIdentityV2 $unsafeAttemptIdentity `
                -ExpectedContentSha256 $unsafeAttemptContentSha256 `
                -SourceRootPath (Split-Path -Parent $promotionSource) `
                -FfprobePath '' `
                -BatchScratchRoot $reparseStageRoot `
                -ScratchTrustRoot $root `
                -AttemptId 'reparse-copy' | Out-Null
        } catch {
            $reparseError = [string]$_.Exception.Message
        }
    } finally {
        Set-Item -LiteralPath Function:\Test-MediaPipelinePathBoundarySafe -Value $script:RerunRecoveryOriginalBoundaryHelper
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }
    $reparseProtected = (
        $reparseError -match 'scratch path boundary rejected' -and
        (-not $script:RerunRecoveryReparseNativeCalled) -and
        (-not (Test-Path -LiteralPath $reparseOutsideProduced))
    )

    # Exercise the production staging caller: it must not create a missing title
    # directory through a Movies junction before verified-copy boundary proof.
    $callerReparseStageRoot = Join-Path $batchScratch 'CallerReparseStage'
    $callerReparseOutsideRoot = Join-Path $root 'CallerReparseOutside'
    $callerReparseLink = Join-Path $callerReparseStageRoot 'Movies'
    New-Item -ItemType Directory -Path $callerReparseStageRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $callerReparseOutsideRoot -Force | Out-Null
    Assert-True (New-RerunFixtureDirectoryJunction -Path $callerReparseLink -Target $callerReparseOutsideRoot) 'Unable to create the production caller junction fixture.'
    $callerReparseOutsideTitle = Join-Path $callerReparseOutsideRoot 'Missing Title (2026)'
    $callerReparseDestination = Join-Path $callerReparseLink 'Missing Title (2026)\Promotion Source.mkv'
    $callerReparsePlan = [pscustomobject][ordered]@{
        row_index = 16
        source_path = $promotionSource
        source_root = (Split-Path -Parent $promotionSource)
        source_size = [long]$unsafeAttemptSourceInfo.Length
        source_mtime_utc = $unsafeAttemptSourceInfo.LastWriteTimeUtc.ToString('o')
        source_identity_v2 = $unsafeAttemptIdentity
        planned_source_identity_v2 = $unsafeAttemptIdentity
        source_content_sha256 = $unsafeAttemptContentSha256
        planned_source_content_sha256 = $unsafeAttemptContentSha256
        source_content_sha256_algorithm = 'sha256-full-file'
        stage_path = $callerReparseDestination
        stage_mode = 'copy'
        status = 'pending'
        lifecycle_state = 'accepted'
        attempt_count = 0
        stage_attempt_count = 0
        timeline = @()
    }
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryCallerReparseNativeCalled = $false
    try {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $script:RerunRecoveryCallerReparseNativeCalled = $true
            return [pscustomobject]@{ ExitCode = 8; Output = ''; Error = 'caller reparse reached native copy'; TimedOut = $false }
        }
        Invoke-RerunStagePlans -Plans @($callerReparsePlan) -Config @{} -StageRoot $callerReparseStageRoot -OutputRoot $root -FinalOutputRoot $root -FfprobePath '' -MaxAttempts 1 -BackoffSeconds @(0) -ScratchTrustRoot $root -SleepAction { param([int]$Seconds) }
    } finally {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }
    $callerReparseProtected = (
        (-not $script:RerunRecoveryCallerReparseNativeCalled) -and
        (-not (Test-Path -LiteralPath $callerReparseOutsideTitle)) -and
        [string]$callerReparsePlan.status -eq 'review' -and
        [string]$callerReparsePlan.reason_code -eq 'rerun_scratch_boundary_rejected'
    )

    # A junction above BatchScratchRoot is invisible to a root=self check. The
    # trusted ancestor must bind the entire route before any attempt directory exists.
    $ancestorTrustRoot = Join-Path $batchScratch 'AncestorTrust'
    $ancestorOutsideRoot = Join-Path $root 'AncestorOutside'
    $ancestorQueueLink = Join-Path $ancestorTrustRoot 'RerunQueue'
    New-Item -ItemType Directory -Path $ancestorTrustRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $ancestorOutsideRoot -Force | Out-Null
    Assert-True (New-RerunFixtureDirectoryJunction -Path $ancestorQueueLink -Target $ancestorOutsideRoot) 'Unable to create the trusted-ancestor junction fixture.'
    $ancestorBatchRoot = Join-Path $ancestorQueueLink 'batch-ancestor'
    $ancestorDestination = Join-Path $ancestorBatchRoot 'Movies\Nested\Promotion Source.mkv'
    $ancestorOutsideBatch = Join-Path $ancestorOutsideRoot 'batch-ancestor'
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryAncestorNativeCalled = $false
    $ancestorError = ''
    try {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $script:RerunRecoveryAncestorNativeCalled = $true
            return [pscustomobject]@{ ExitCode = 8; Output = ''; Error = 'ancestor junction reached native copy'; TimedOut = $false }
        }
        try {
            Copy-RerunFileVerified `
                -Source $promotionSource `
                -Destination $ancestorDestination `
                -MaxRetries 1 `
                -ExpectedSize $unsafeAttemptSourceInfo.Length `
                -ExpectedMtimeUtc $unsafeAttemptSourceInfo.LastWriteTimeUtc.ToString('o') `
                -ExpectedIdentityV2 $unsafeAttemptIdentity `
                -ExpectedContentSha256 $unsafeAttemptContentSha256 `
                -SourceRootPath (Split-Path -Parent $promotionSource) `
                -FfprobePath '' `
                -BatchScratchRoot $ancestorBatchRoot `
                -ScratchTrustRoot $ancestorTrustRoot `
                -AttemptId 'ancestor-copy' | Out-Null
        } catch {
            $ancestorError = [string]$_.Exception.Message
        }
    } finally {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }
    $ancestorReparseProtected = (
        $ancestorError -match 'scratch path boundary rejected' -and
        (-not $script:RerunRecoveryAncestorNativeCalled) -and
        (-not (Test-Path -LiteralPath $ancestorOutsideBatch))
    )

    # A mid-copy source outage is reclassified after cleanup and persisted as source recovery evidence.
    $midCopyBackingSource = Join-Path $driveBacking 'Library\Mid Copy Offline.mkv'
    [System.IO.File]::WriteAllBytes($midCopyBackingSource, [System.Text.Encoding]::UTF8.GetBytes('mid-copy-offline-source-bytes'))
    $midCopySourceHash = (Get-FileHash -LiteralPath $midCopyBackingSource -Algorithm SHA256).Hash
    Set-RerunFixtureDriveOnline -DriveName $driveName -BackingPath $driveBacking
    $midCopySource = "${driveName}:\Library\Mid Copy Offline.mkv"
    $midCopyHealth = Get-RerunSourceHealth -SourcePath $midCopySource -ConfiguredRootPath "${driveName}:\Library" -FfprobePath ''
    $midCopyStageRoot = Join-Path $batchScratch 'MidCopyOffline'
    New-Item -ItemType Directory -Path $midCopyStageRoot -Force | Out-Null
    $midCopyDestination = Join-Path $midCopyStageRoot 'Movies\Mid Copy Offline.mkv'
    $midCopyPlan = [pscustomobject][ordered]@{
        row_index = 15
        source_path = $midCopySource
        source_root = "${driveName}:\Library"
        source_size = [long]$midCopyHealth.FileInfo.Length
        source_mtime_utc = $midCopyHealth.FileInfo.LastWriteTimeUtc.ToString('o')
        source_identity_v2 = [string]$midCopyHealth.IdentityV2
        planned_source_identity_v2 = [string]$midCopyHealth.IdentityV2
        source_content_sha256 = [string]$midCopyHealth.ContentSha256
        planned_source_content_sha256 = [string]$midCopyHealth.ContentSha256
        source_content_sha256_algorithm = 'sha256-full-file'
        stage_path = $midCopyDestination
        stage_mode = 'copy'
        status = 'pending'
        lifecycle_state = 'accepted'
        attempt_count = 0
        stage_attempt_count = 0
        timeline = @()
    }
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryMidCopyDriveName = $driveName
    $script:RerunRecoveryMidCopyReservationPath = $driveReservationPath
    $script:RerunRecoveryMidCopyHookFired = $false
    try {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $landedPath = Join-Path ([string]$ArgumentList[1]) ([string]$ArgumentList[2])
            [System.IO.File]::WriteAllBytes($landedPath, [byte[]](1, 2, 3, 4))
            Set-RerunFixtureDriveOffline -DriveName $script:RerunRecoveryMidCopyDriveName -ReservationPath $script:RerunRecoveryMidCopyReservationPath
            $script:RerunRecoveryMidCopyHookFired = $true
            return [pscustomobject]@{ ExitCode = -1; Output = ''; Error = 'simulated mapped-source timeout during copy'; TimedOut = $true }
        }
        Invoke-RerunStagePlans -Plans @($midCopyPlan) -Config @{} -StageRoot $midCopyStageRoot -OutputRoot $root -FinalOutputRoot $root -FfprobePath '' -MaxAttempts 1 -BackoffSeconds @(0) -ScratchTrustRoot $root -SleepAction { param([int]$Seconds) }
    } finally {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }
    $midCopyClassified = (
        $script:RerunRecoveryMidCopyHookFired -and
        [string]$midCopyPlan.status -eq 'retry_exhausted' -and
        [string]$midCopyPlan.reason_code -eq 'source_location_unavailable' -and
        [string]$midCopyPlan.why -notmatch 'stage_copy_failed' -and
        (-not (Test-Path -LiteralPath $midCopyDestination)) -and
        @(Get-ChildItem -LiteralPath $midCopyStageRoot -Force -Recurse -Filter '*.rerun-partial.*' -ErrorAction SilentlyContinue).Count -eq 0 -and
        @(Get-ChildItem -LiteralPath $midCopyStageRoot -Force -Recurse -Directory -Filter '.mediapipeline-rerun-staging' -ErrorAction SilentlyContinue).Count -eq 0
    )

    function Invoke-RerunUntypedCopyOutageFixture {
        param(
            [Parameter(Mandatory)] [ValidateSet('native_throw','landed_access')] [string]$Mode,
            [Parameter(Mandatory)] [int]$RowIndex
        )
        $leaf = if ($Mode -eq 'native_throw') { 'Native Throw Offline.mkv' } else { 'Landed Access Offline.mkv' }
        $backingSource = Join-Path $driveBacking "Library\$leaf"
        [System.IO.File]::WriteAllBytes($backingSource, [System.Text.Encoding]::UTF8.GetBytes("$Mode-source-bytes"))
        $backingHash = (Get-FileHash -LiteralPath $backingSource -Algorithm SHA256).Hash
        Set-RerunFixtureDriveOnline -DriveName $driveName -BackingPath $driveBacking
        $sourcePath = "${driveName}:\Library\$leaf"
        $health = Get-RerunSourceHealth -SourcePath $sourcePath -ConfiguredRootPath "${driveName}:\Library" -FfprobePath ''
        $stageRoot = Join-Path $batchScratch ("UntypedOutage-$Mode")
        New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
        $destination = Join-Path $stageRoot "Movies\$leaf"
        $plan = [pscustomobject][ordered]@{
            row_index = $RowIndex
            source_path = $sourcePath
            source_root = "${driveName}:\Library"
            source_size = [long]$health.FileInfo.Length
            source_mtime_utc = $health.FileInfo.LastWriteTimeUtc.ToString('o')
            source_identity_v2 = [string]$health.IdentityV2
            planned_source_identity_v2 = [string]$health.IdentityV2
            source_content_sha256 = [string]$health.ContentSha256
            planned_source_content_sha256 = [string]$health.ContentSha256
            source_content_sha256_algorithm = 'sha256-full-file'
            stage_path = $destination
            stage_mode = 'copy'
            status = 'pending'
            lifecycle_state = 'accepted'
            attempt_count = 0
            stage_attempt_count = 0
            timeline = @()
        }
        $originalNative = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
        $script:RerunRecoveryUntypedMode = $Mode
        $script:RerunRecoveryUntypedDriveName = $driveName
        $script:RerunRecoveryUntypedReservationPath = $driveReservationPath
        try {
            Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
                param(
                    [Parameter(Mandatory)] [string]$FilePath,
                    [array]$ArgumentList = @(),
                    [int]$TimeoutSeconds = 0,
                    [string]$Label = ''
                )
                if ($script:RerunRecoveryUntypedMode -eq 'native_throw') {
                    $landedPath = Join-Path ([string]$ArgumentList[1]) ([string]$ArgumentList[2])
                    [System.IO.File]::WriteAllBytes($landedPath, [byte[]](9, 8, 7, 6))
                }
                Set-RerunFixtureDriveOffline -DriveName $script:RerunRecoveryUntypedDriveName -ReservationPath $script:RerunRecoveryUntypedReservationPath
                if ($script:RerunRecoveryUntypedMode -eq 'native_throw') {
                    throw 'simulated native wrapper throw after source disconnect'
                }
                return [pscustomobject]@{ ExitCode = 1; Output = ''; Error = ''; TimedOut = $false }
            }
            Invoke-RerunStagePlans -Plans @($plan) -Config @{} -StageRoot $stageRoot -OutputRoot $root -FinalOutputRoot $root -FfprobePath '' -MaxAttempts 1 -BackoffSeconds @(0) -ScratchTrustRoot $root -SleepAction { param([int]$Seconds) }
        } finally {
            Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $originalNative
        }
        return [pscustomobject]@{
            Mode = $Mode
            Plan = $plan
            StageRoot = $stageRoot
            Destination = $destination
            BackingSource = $backingSource
            BackingHash = $backingHash
        }
    }

    $nativeThrowOutage = Invoke-RerunUntypedCopyOutageFixture -Mode native_throw -RowIndex 17
    $landedAccessOutage = Invoke-RerunUntypedCopyOutageFixture -Mode landed_access -RowIndex 18
    $untypedOutagesClassified = @(@($nativeThrowOutage, $landedAccessOutage) | Where-Object {
        [string]$_.Plan.status -eq 'retry_exhausted' -and
        [string]$_.Plan.reason_code -eq 'source_location_unavailable' -and
        [string]$_.Plan.why -notmatch 'stage_copy_failed' -and
        (-not (Test-Path -LiteralPath $_.Destination)) -and
        @(Get-ChildItem -LiteralPath $_.StageRoot -Force -Recurse -Filter '*.rerun-partial.*' -ErrorAction SilentlyContinue).Count -eq 0 -and
        @(Get-ChildItem -LiteralPath $_.StageRoot -Force -Recurse -Directory -Filter '.mediapipeline-rerun-staging' -ErrorAction SilentlyContinue).Count -eq 0 -and
        (Get-FileHash -LiteralPath $_.BackingSource -Algorithm SHA256).Hash -eq $_.BackingHash
    }).Count -eq 2
    Remove-Item -LiteralPath Function:\Invoke-RerunUntypedCopyOutageFixture -ErrorAction SilentlyContinue

    $safetyFollowupPassed = (
        $destructiveFlagsProtected -and
        $boundaryUnavailableProtected -and
        $boundaryPathsProtected -and
        $reparseProtected -and
        $callerReparseProtected -and
        $ancestorReparseProtected -and
        $midCopyClassified -and
        $untypedOutagesClassified
    )
    Assert-True $safetyFollowupPassed "Rerun copy safety regressions failed: destructive_flags=$destructiveFlagsProtected details=$($destructiveFlagResults | ConvertTo-Json -Compress); boundary_unavailable=$boundaryUnavailableProtected error='$boundaryUnavailableError'; boundary_paths=$boundaryPathsProtected recorded=$($script:RerunRecoveryBoundaryPaths -join ','); reparse=$reparseProtected fixture_created=$reparseCreated error='$reparseError' native_called=$($script:RerunRecoveryReparseNativeCalled) outside_written=$(Test-Path -LiteralPath $reparseOutsideProduced); caller_reparse=$callerReparseProtected outside_title=$(Test-Path -LiteralPath $callerReparseOutsideTitle) caller_reason=$($callerReparsePlan.reason_code); ancestor_reparse=$ancestorReparseProtected error='$ancestorError' outside_batch=$(Test-Path -LiteralPath $ancestorOutsideBatch); mid_copy=$midCopyClassified status=$($midCopyPlan.status) reason=$($midCopyPlan.reason_code) why='$($midCopyPlan.why)'; untyped_outages=$untypedOutagesClassified native_throw_reason=$($nativeThrowOutage.Plan.reason_code) landed_access_reason=$($landedAccessOutage.Plan.reason_code)."
    Assert-True (Test-Path -LiteralPath $promotionSource -PathType Leaf) 'Safety flag/boundary checks removed the source fixture.'
    Assert-Equal (Get-FileHash -LiteralPath $promotionSource -Algorithm SHA256).Hash $promotionHash 'Safety flag/boundary checks changed the source fixture.'
    Assert-Equal (Get-FileHash -LiteralPath $midCopyBackingSource -Algorithm SHA256).Hash $midCopySourceHash 'Mid-copy outage handling changed the source fixture.'

    # The real verified-copy path preserves source bytes and refuses duplicate stage promotion.
    $actualStageRoot = Join-Path $batchScratch 'ActualCopy'
    New-Item -ItemType Directory -Path $actualStageRoot -Force | Out-Null
    $actualDestination = Join-Path $actualStageRoot 'Movies\Promotion Source.mkv'
    $promotionInfo = Get-Item -LiteralPath $promotionSource
    $promotionIdentity = Get-RerunSourceIdentityV2 -FileInfo $promotionInfo -FfprobePath ''
    $script:RerunRobocopyFlags = @('/J','/R:0','/W:0','/NP','/NDL','/NFL')
    $script:RerunRobocopyTimeoutSeconds = 30
    $actualCopied = Copy-RerunFileVerified -Source $promotionSource -Destination $actualDestination -MaxRetries 1 -ExpectedSize $promotionInfo.Length -ExpectedMtimeUtc $promotionInfo.LastWriteTimeUtc.ToString('o') -ExpectedIdentityV2 $promotionIdentity -FfprobePath '' -BatchScratchRoot $actualStageRoot -ScratchTrustRoot $root -AttemptId 'actual-copy'
    Assert-True $actualCopied 'Real verified fixture copy did not complete.'
    Assert-Equal (Get-FileHash -LiteralPath $promotionSource -Algorithm SHA256).Hash $promotionHash 'Verified copy mutated the source fixture.'
    Assert-Equal (Get-FileHash -LiteralPath $actualDestination -Algorithm SHA256).Hash $promotionHash 'Verified staged copy bytes differ from the source.'
    $duplicateBlocked = $false
    try {
        Copy-RerunFileVerified -Source $promotionSource -Destination $actualDestination -MaxRetries 1 -ExpectedSize $promotionInfo.Length -ExpectedMtimeUtc $promotionInfo.LastWriteTimeUtc.ToString('o') -ExpectedIdentityV2 $promotionIdentity -FfprobePath '' -BatchScratchRoot $actualStageRoot -ScratchTrustRoot $root -AttemptId 'duplicate-copy' | Out-Null
    } catch {
        $duplicateBlocked = ($_.Exception.Message -match 'stage path already exists')
    }
    Assert-True $duplicateBlocked 'Duplicate verified stage promotion was not blocked.'
    Assert-Equal @(Get-ChildItem -LiteralPath (Split-Path -Parent $actualDestination) -File).Count 1 'Duplicate copy created more than one staged output.'
    Assert-Equal @(Get-ChildItem -LiteralPath $actualStageRoot -File -Recurse -Filter '*.rerun-partial.*' -ErrorAction SilentlyContinue).Count 0 'Verified copy left attempt partials.'

    # Backend lifecycle evidence must describe landed-scratch verification, not a post-copy source probe.
    $lifecycleStageRoot = Join-Path $batchScratch 'LifecycleText'
    New-Item -ItemType Directory -Path $lifecycleStageRoot -Force | Out-Null
    $lifecycleStagePath = Join-Path $lifecycleStageRoot 'Movies\Promotion Source.mkv'
    $promotionContentSha256 = Get-RerunContentSha256 -Path $promotionSource
    $lifecyclePlan = [pscustomobject][ordered]@{
        row_index = 14
        source_path = $promotionSource
        source_root = (Split-Path -Parent $promotionSource)
        source_size = [long]$promotionInfo.Length
        source_mtime_utc = $promotionInfo.LastWriteTimeUtc.ToString('o')
        source_identity_v2 = $promotionIdentity
        planned_source_identity_v2 = $promotionIdentity
        source_content_sha256 = $promotionContentSha256
        planned_source_content_sha256 = $promotionContentSha256
        source_content_sha256_algorithm = 'sha256-full-file'
        stage_path = $lifecycleStagePath
        stage_mode = 'copy'
        status = 'pending'
        lifecycle_state = 'accepted'
        attempt_count = 0
        stage_attempt_count = 0
        timeline = @()
    }
    Invoke-RerunStagePlans -Plans @($lifecyclePlan) -Config @{} -StageRoot $lifecycleStageRoot -OutputRoot $root -FinalOutputRoot $root -FfprobePath '' -MaxAttempts 1 -BackoffSeconds @(0) -ScratchTrustRoot $root -SleepAction { param([int]$Seconds) }
    Assert-Equal $lifecyclePlan.status 'staged' 'Focused lifecycle-text fixture did not complete verified staging.'
    Assert-Equal $lifecyclePlan.why 'The landed scratch size, sampled fingerprint, and full SHA-256 match the durable source identity validated immediately before copy.' 'Staged lifecycle evidence still claims a post-copy source probe.'

    # The production copy path must trust a fully verified landed copy when the mapped source drops after robocopy.
    $postCopyBackingSource = Join-Path $driveBacking 'Library\Drop After Copy.mkv'
    [System.IO.File]::WriteAllBytes($postCopyBackingSource, [System.Text.Encoding]::UTF8.GetBytes('drop-after-copy-with-durable-full-hash'))
    $postCopySourceHash = (Get-FileHash -LiteralPath $postCopyBackingSource -Algorithm SHA256).Hash
    Set-RerunFixtureDriveOnline -DriveName $driveName -BackingPath $driveBacking
    $postCopySource = "${driveName}:\Library\Drop After Copy.mkv"
    $postCopyHealth = Get-RerunSourceHealth -SourcePath $postCopySource -ConfiguredRootPath "${driveName}:\Library" -FfprobePath ''
    Assert-Equal $postCopyHealth.Code 'available' 'Post-copy outage fixture did not establish authoritative source evidence.'
    $postCopyStageRoot = Join-Path $batchScratch 'PostCopyOutage'
    New-Item -ItemType Directory -Path $postCopyStageRoot -Force | Out-Null
    $postCopyDestination = Join-Path $postCopyStageRoot 'Movies\Drop After Copy.mkv'
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryPostCopyHookFired = $false
    $script:RerunRecoveryHookDriveName = $driveName
    $script:RerunRecoveryHookReservationPath = $driveReservationPath
    $postCopySucceeded = $false
    $postCopyError = ''
    try {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            $result = & $script:RerunRecoveryOriginalNativeCommand @PSBoundParameters
            if ($Label -eq 'robocopy-rerun-stage') {
                Set-RerunFixtureDriveOffline -DriveName $script:RerunRecoveryHookDriveName -ReservationPath $script:RerunRecoveryHookReservationPath
                $script:RerunRecoveryPostCopyHookFired = $true
            }
            return $result
        }
        try {
            $postCopySucceeded = Copy-RerunFileVerified `
                -Source $postCopySource `
                -Destination $postCopyDestination `
                -MaxRetries 1 `
                -ExpectedSize $postCopyHealth.FileInfo.Length `
                -ExpectedMtimeUtc $postCopyHealth.FileInfo.LastWriteTimeUtc.ToString('o') `
                -ExpectedIdentityV2 $postCopyHealth.IdentityV2 `
                -ExpectedContentSha256 $postCopyHealth.ContentSha256 `
                -SourceRootPath "${driveName}:\Library" `
                -FfprobePath '' `
                -BatchScratchRoot $postCopyStageRoot `
                -ScratchTrustRoot $root `
                -AttemptId 'post-copy-outage'
        } catch {
            $postCopyError = [string]$_.Exception.Message
        }
    } finally {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }

    # A failed production copy cleans both landed and promotion-partial artifacts without escaping batch scratch.
    $failedCopyBackingSource = Join-Path $driveBacking 'Library\Interrupted Copy.mkv'
    [System.IO.File]::WriteAllBytes($failedCopyBackingSource, [System.Text.Encoding]::UTF8.GetBytes('interrupted-copy-source-must-remain-unchanged'))
    $failedCopySourceHash = (Get-FileHash -LiteralPath $failedCopyBackingSource -Algorithm SHA256).Hash
    Set-RerunFixtureDriveOnline -DriveName $driveName -BackingPath $driveBacking
    $failedCopySource = "${driveName}:\Library\Interrupted Copy.mkv"
    $failedCopyHealth = Get-RerunSourceHealth -SourcePath $failedCopySource -ConfiguredRootPath "${driveName}:\Library" -FfprobePath ''
    Assert-Equal $failedCopyHealth.Code 'available' 'Interrupted-copy fixture did not establish authoritative source evidence.'
    $failedCopyStageRoot = Join-Path $batchScratch 'FailedCopyOutage'
    New-Item -ItemType Directory -Path $failedCopyStageRoot -Force | Out-Null
    $failedCopyDestination = Join-Path $failedCopyStageRoot 'Movies\Interrupted Copy.mkv'
    $failedCopyAttempt = 'failed-copy-outage'
    $failedCopyAttemptDir = Join-Path $failedCopyStageRoot ".mediapipeline-rerun-staging\$failedCopyAttempt"
    $failedCopyPartial = "$failedCopyDestination.rerun-partial.$failedCopyAttempt"
    $failedCopyOutside = Join-Path $root "outside.rerun-partial.$failedCopyAttempt"
    [System.IO.File]::WriteAllText($failedCopyOutside, 'must survive failed production copy', [System.Text.UTF8Encoding]::new($false))
    $script:RerunRecoveryOriginalNativeCommand = (Get-Command Invoke-RerunNativeCommand -CommandType Function).ScriptBlock
    $script:RerunRecoveryFailedCopyPartial = $failedCopyPartial
    $script:RerunRecoveryFailedCopyHookFired = $false
    $failedCopyResult = $true
    $failedCopyError = ''
    try {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value {
            param(
                [Parameter(Mandatory)] [string]$FilePath,
                [array]$ArgumentList = @(),
                [int]$TimeoutSeconds = 0,
                [string]$Label = ''
            )
            if ($Label -ne 'robocopy-rerun-stage') {
                return & $script:RerunRecoveryOriginalNativeCommand @PSBoundParameters
            }
            $landedPath = Join-Path ([string]$ArgumentList[1]) ([string]$ArgumentList[2])
            [System.IO.File]::WriteAllBytes($landedPath, [byte[]](1, 2, 3, 4))
            [System.IO.File]::WriteAllBytes($script:RerunRecoveryFailedCopyPartial, [byte[]](5, 6, 7, 8))
            Set-RerunFixtureDriveOffline -DriveName $script:RerunRecoveryHookDriveName -ReservationPath $script:RerunRecoveryHookReservationPath
            $script:RerunRecoveryFailedCopyHookFired = $true
            return [pscustomobject]@{ ExitCode = 8; Output = ''; Error = 'simulated source outage during copy'; TimedOut = $false }
        }
        try {
            $failedCopyResult = Copy-RerunFileVerified `
                -Source $failedCopySource `
                -Destination $failedCopyDestination `
                -MaxRetries 1 `
                -ExpectedSize $failedCopyHealth.FileInfo.Length `
                -ExpectedMtimeUtc $failedCopyHealth.FileInfo.LastWriteTimeUtc.ToString('o') `
                -ExpectedIdentityV2 $failedCopyHealth.IdentityV2 `
                -ExpectedContentSha256 $failedCopyHealth.ContentSha256 `
                -SourceRootPath "${driveName}:\Library" `
                -FfprobePath '' `
                -BatchScratchRoot $failedCopyStageRoot `
                -ScratchTrustRoot $root `
                -AttemptId $failedCopyAttempt
        } catch {
            $failedCopyResult = $false
            $failedCopyError = [string]$_.Exception.Message
        }
    } finally {
        Set-Item -LiteralPath Function:\Invoke-RerunNativeCommand -Value $script:RerunRecoveryOriginalNativeCommand
    }

    $postCopyStageVerified = (
        $postCopySucceeded -and
        $script:RerunRecoveryPostCopyHookFired -and
        (Test-Path -LiteralPath $postCopyDestination -PathType Leaf) -and
        ((Get-FileHash -LiteralPath $postCopyDestination -Algorithm SHA256).Hash -eq $postCopySourceHash)
    )
    $failedCopyClean = (
        (-not $failedCopyResult) -and
        $failedCopyError -match '^source_location_unavailable:' -and
        $script:RerunRecoveryFailedCopyHookFired -and
        (-not (Test-Path -LiteralPath $failedCopyAttemptDir)) -and
        (-not (Test-Path -LiteralPath $failedCopyPartial)) -and
        (-not (Test-Path -LiteralPath $failedCopyDestination)) -and
        (Test-Path -LiteralPath $failedCopyOutside -PathType Leaf)
    )
    Assert-True ($postCopyStageVerified -and $failedCopyClean) "Production verified-copy outage regressions failed: post_copy_verified=$postCopyStageVerified error='$postCopyError'; failed_copy_clean=$failedCopyClean error='$failedCopyError' partial_exists=$(Test-Path -LiteralPath $failedCopyPartial)."
    Assert-Equal (Get-FileHash -LiteralPath $postCopyBackingSource -Algorithm SHA256).Hash $postCopySourceHash 'Post-copy source outage mutated the source fixture.'
    Assert-Equal (Get-FileHash -LiteralPath $failedCopyBackingSource -Algorithm SHA256).Hash $failedCopySourceHash 'Interrupted copy mutated the source fixture.'
    Assert-True (Test-Path -LiteralPath $failedCopyOutside -PathType Leaf) 'Failed copy cleanup escaped the batch scratch root.'

    # Manifest writes use a per-path CAS mutex: the second equal-base writer is stale.
    $casManifestPath = Join-Path $root 'cas\execution.json'
    $casPayload = [ordered]@{
        schema_version = 'rerun_batch_manifest.v2'
        batch_id = 'cas-batch'
        lifecycle_state = 'accepted'
        status = 'accepted'
        transition_sequence = 1
        write_sequence = 0
        timeline = @([pscustomobject]@{ sequence = 1; state = 'accepted' })
        rows = @()
    }
    Write-RerunManifest -Path $casManifestPath -Payload $casPayload
    $writerOne = ($casPayload | ConvertTo-Json -Depth 12 | ConvertFrom-Json)
    $writerTwo = ($casPayload | ConvertTo-Json -Depth 12 | ConvertFrom-Json)
    $writerOne.lifecycle_state = 'waiting'
    $writerOne.status = 'retry_scheduled'
    Write-RerunManifest -Path $casManifestPath -Payload $writerOne
    $staleRejected = $false
    try { Write-RerunManifest -Path $casManifestPath -Payload $writerTwo } catch { $staleRejected = ($_.Exception.Message -match 'stale CSV rerun manifest write rejected') }
    Assert-True $staleRejected 'Second writer from the same base sequence overwrote newer waiting state.'
    $casOnDisk = Get-Content -LiteralPath $casManifestPath -Raw | ConvertFrom-Json
    Assert-Equal $casOnDisk.lifecycle_state 'waiting' 'Stale writer replaced newer waiting state.'
    $terminalWriter = ($casOnDisk | ConvertTo-Json -Depth 12 | ConvertFrom-Json)
    $nonterminalEqualBase = ($casOnDisk | ConvertTo-Json -Depth 12 | ConvertFrom-Json)
    $terminalWriter.lifecycle_state = 'terminal'
    $terminalWriter.status = 'failed'
    Write-RerunManifest -Path $casManifestPath -Payload $terminalWriter
    $terminalRegressionBlocked = $false
    try { Write-RerunManifest -Path $casManifestPath -Payload $nonterminalEqualBase } catch { $terminalRegressionBlocked = ($_.Exception.Message -match 'stale CSV rerun manifest write rejected') }
    Assert-True $terminalRegressionBlocked 'Stale nonterminal writer regressed a terminal manifest.'

    $batchMismatchPath = Join-Path $root 'cas\batch-mismatch.json'
    $batchOnePayload = [ordered]@{ schema_version = 'rerun_batch_manifest.v2'; batch_id = 'batch-one'; lifecycle_state = 'accepted'; status = 'accepted'; write_sequence = 0; transition_sequence = 1; timeline = @(); rows = @() }
    Write-RerunManifest -Path $batchMismatchPath -Payload $batchOnePayload
    $batchMismatchBytes = [System.IO.File]::ReadAllBytes($batchMismatchPath)
    $batchTwoPayload = [ordered]@{ schema_version = 'rerun_batch_manifest.v2'; batch_id = 'batch-two'; lifecycle_state = 'accepted'; status = 'accepted'; write_sequence = 0; transition_sequence = 1; timeline = @(); rows = @() }
    $differentBatchRejected = $false
    try { Write-RerunManifest -Path $batchMismatchPath -Payload $batchTwoPayload } catch { $differentBatchRejected = ($_.Exception.Message -match 'batch_id') }
    Assert-True $differentBatchRejected 'Sequential writer replaced a v2 execution manifest with a different batch_id.'
    Assert-Equal ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($batchMismatchPath))) ([Convert]::ToBase64String($batchMismatchBytes)) 'Different-batch CAS rejection changed manifest bytes.'

    $futureSequencePath = Join-Path $root 'cas\future-sequence.json'
    $futureSequenceBase = [ordered]@{ schema_version = 'rerun_batch_manifest.v2'; batch_id = 'future-sequence'; lifecycle_state = 'accepted'; status = 'accepted'; write_sequence = 0; transition_sequence = 1; timeline = @(); rows = @() }
    Write-RerunManifest -Path $futureSequencePath -Payload $futureSequenceBase
    $futureSequenceBytes = [System.IO.File]::ReadAllBytes($futureSequencePath)
    $futureSequenceWriter = ($futureSequenceBase | ConvertTo-Json -Depth 12 | ConvertFrom-Json)
    $futureSequenceWriter.write_sequence = 99
    $futureSequenceRejected = $false
    try { Write-RerunManifest -Path $futureSequencePath -Payload $futureSequenceWriter } catch { $futureSequenceRejected = ($_.Exception.Message -match 'sequence') }
    Assert-True $futureSequenceRejected 'Future manifest sequence skipped the compare-and-swap base.'
    Assert-Equal ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($futureSequencePath))) ([Convert]::ToBase64String($futureSequenceBytes)) 'Future-sequence CAS rejection changed manifest bytes.'

    # A failed atomic replace must not consume the in-memory compare-and-swap sequence.
    $replaceFailurePath = Join-Path $root 'cas\replace-failure.json'
    $replaceFailurePayload = [ordered]@{ schema_version = 'rerun_batch_manifest.v2'; batch_id = 'replace-failure'; lifecycle_state = 'accepted'; status = 'accepted'; write_sequence = 0; transition_sequence = 1; timeline = @(); rows = @() }
    Write-RerunManifest -Path $replaceFailurePath -Payload $replaceFailurePayload
    $replaceFailureDiskSequence = [int](Get-Content -LiteralPath $replaceFailurePath -Raw | ConvertFrom-Json).write_sequence
    $moveReplaceScript = (Get-Command Move-RerunFileReplaceWithRetry -CommandType Function).ScriptBlock
    try {
        Set-Item -LiteralPath Function:\Move-RerunFileReplaceWithRetry -Value {
            param([string]$Source, [string]$Destination, [string]$Label, [int]$Attempts, [int]$DelayMilliseconds)
            throw 'simulated persistent manifest replace failure'
        }
        $replaceFailed = $false
        try { Write-RerunManifest -Path $replaceFailurePath -Payload $replaceFailurePayload } catch { $replaceFailed = ($_.Exception.Message -match 'simulated persistent') }
        Assert-True $replaceFailed 'Manifest atomic-replace failure injection did not execute.'
        Assert-Equal $replaceFailurePayload.write_sequence $replaceFailureDiskSequence 'Failed manifest replace advanced the in-memory CAS sequence.'
        Assert-Equal ([int](Get-Content -LiteralPath $replaceFailurePath -Raw | ConvertFrom-Json).write_sequence) $replaceFailureDiskSequence 'Failed manifest replace changed durable sequence evidence.'
    } finally {
        Set-Item -LiteralPath Function:\Move-RerunFileReplaceWithRetry -Value $moveReplaceScript
    }
    Write-RerunManifest -Path $replaceFailurePath -Payload $replaceFailurePayload
    Assert-Equal $replaceFailurePayload.write_sequence ($replaceFailureDiskSequence + 1) 'Manifest payload was not retryable after atomic-replace recovery.'

    $concurrentBatchPath = Join-Path $root 'cas\concurrent-batches.json'
    $concurrentWriter = {
        param($EntrySupportPath, $ManifestFile, $WriterBatch)
        . $EntrySupportPath
        Start-Sleep -Milliseconds 300
        $payload = [ordered]@{ schema_version = 'rerun_batch_manifest.v2'; batch_id = $WriterBatch; lifecycle_state = 'accepted'; status = 'accepted'; write_sequence = 0; transition_sequence = 1; timeline = @(); rows = @() }
        try {
            Write-RerunManifest -Path $ManifestFile -Payload $payload
            [pscustomobject]@{ batch_id = $WriterBatch; succeeded = $true; message = '' }
        } catch {
            [pscustomobject]@{ batch_id = $WriterBatch; succeeded = $false; message = [string]$_.Exception.Message }
        }
    }
    $concurrentJobs = @(
        Start-Job -ScriptBlock $concurrentWriter -ArgumentList $entrySupport,$concurrentBatchPath,'concurrent-one'
        Start-Job -ScriptBlock $concurrentWriter -ArgumentList $entrySupport,$concurrentBatchPath,'concurrent-two'
    )
    try {
        Wait-Job -Job $concurrentJobs | Out-Null
        $concurrentResults = @($concurrentJobs | ForEach-Object { Receive-Job -Job $_ } | Where-Object { $null -ne $_.PSObject.Properties['succeeded'] })
    } finally {
        $concurrentJobs | Remove-Job -Force -ErrorAction SilentlyContinue
    }
    Assert-Equal @($concurrentResults | Where-Object { $_.succeeded }).Count 1 'Concurrent different-batch writers did not produce exactly one winner.'
    Assert-Equal @($concurrentResults | Where-Object { -not $_.succeeded }).Count 1 'Concurrent different-batch writer was not rejected.'
    $concurrentOnDisk = Get-Content -LiteralPath $concurrentBatchPath -Raw | ConvertFrom-Json
    Assert-Equal $concurrentOnDisk.batch_id @($concurrentResults | Where-Object { $_.succeeded })[0].batch_id 'Concurrent manifest winner does not match durable bytes.'

    $mixedOutcomeManifest = [pscustomobject]@{
        pipeline_exit_failures = 0; success_count = 0; review_workspace_count = 0; manual_review_count = 0
        pending_publish_count = 0; published_count = 0; failed_count = 0; remaining_pending_count = 0
        waiting_count = 0; terminal_blocker_count = 0
    }
    $mixedOutcomePlans = @(
        [pscustomobject]@{ status = 'failed' }
        [pscustomobject]@{ status = 'retry_exhausted' }
        [pscustomobject]@{ status = 'review' }
        [pscustomobject]@{ status = 'review_workspace' }
        [pscustomobject]@{ status = 'pending_publish' }
        [pscustomobject]@{ status = 'published_non_overlap' }
        [pscustomobject]@{ status = 'pending' }
    )
    $mixedOutcomeCounts = Update-RerunManifestCounts -Manifest $mixedOutcomeManifest -Plans $mixedOutcomePlans -PipelineExitFailures 1
    Assert-Equal $mixedOutcomeCounts.failed 2 'Standard failed count overlapped manual review rows.'
    Assert-Equal $mixedOutcomeCounts.review 1 'Standard review count overlapped successful review-workspace outcomes.'
    Assert-Equal $mixedOutcomeCounts.success 3 'Successful destination counts were not disjoint.'
    Assert-Equal $mixedOutcomeCounts.terminal_blockers 5 'Terminal blockers did not separately combine failures, manual review, unfinished work, and pipeline exit failures.'
    Assert-Equal $mixedOutcomeManifest.failed_count 2 'Manifest failed_count overlapped review.'
    Assert-Equal $mixedOutcomeManifest.manual_review_count 1 'Manifest manual_review_count was not standardized.'
    Assert-Equal $mixedOutcomeManifest.terminal_blocker_count 5 'Manifest terminal blocker count was not persisted.'

    $unfinishedOutcomeManifest = [pscustomobject]@{}
    $unfinishedOutcomeCounts = Update-RerunManifestCounts -Manifest $unfinishedOutcomeManifest -Plans @([pscustomobject]@{ status = 'retry_scheduled' })
    Assert-Equal $unfinishedOutcomeCounts.unfinished 1 'Nonterminal retry work was not counted as unfinished.'
    Assert-Equal $unfinishedOutcomeCounts.terminal_blockers 1 'Nonterminal retry work could still terminalize as a successful batch.'

    # A restart after the final allowed stage attempt must exhaust, never skip the loop and report success.
    $finalAttemptStageRoot = Join-Path $batchScratch 'FinalAttempt'
    $finalAttemptPlan = [pscustomobject][ordered]@{
        row_index = 10
        source_path = $promotionSource
        source_root = (Split-Path -Parent $promotionSource)
        stage_path = (Join-Path $finalAttemptStageRoot 'Movies\Promotion Source.mkv')
        status = 'retry_scheduled'
        lifecycle_state = 'retry_scheduled'
        source_size = [long]$promotionInfo.Length
        source_mtime_utc = $promotionInfo.LastWriteTimeUtc.ToString('o')
        source_identity_v2 = $promotionIdentity
        planned_source_identity_v2 = $promotionIdentity
        source_content_sha256 = $promotionHash.ToLowerInvariant()
        planned_source_content_sha256 = $promotionHash.ToLowerInvariant()
        source_content_sha256_algorithm = 'sha256-full-file'
        stage_attempt_count = 1
        attempt_count = 0
        transition_sequence = 1
        timeline = @([pscustomobject]@{ sequence = 1; state = 'retry_scheduled' })
    }
    Invoke-RerunStagePlans -Plans @($finalAttemptPlan) -Config @{} -StageRoot $finalAttemptStageRoot -OutputRoot (Join-Path $root 'FinalAttemptOut') -FinalOutputRoot (Join-Path $root 'FinalAttemptFinal') -FfprobePath '' -MaxAttempts 1 -BackoffSeconds @(0) -ScratchTrustRoot $root -SleepAction { param([int]$Seconds) }
    Assert-Equal $finalAttemptPlan.status 'retry_exhausted' 'Final-attempt restart skipped staging without exhausting the row.'
    Assert-False (Test-Path -LiteralPath $finalAttemptPlan.stage_path -PathType Leaf) 'Final-attempt restart invented a staged file.'
    $finalAttemptCounts = Update-RerunManifestCounts -Manifest ([pscustomobject]@{}) -Plans @($finalAttemptPlan)
    Assert-True ($finalAttemptCounts.terminal_blockers -gt 0) 'Final-attempt restart could still produce a successful terminal batch.'

    # Resumed batches allocate beyond every durable chunk identity and never reuse nested runtime state.
    $allocatorManifest = [pscustomobject]@{ current_chunk = 1 }
    $allocatorPlans = @(
        [pscustomobject]@{ row_index = 0; status = 'complete'; lifecycle_state = 'terminal'; rerun_chunk_index = 1; nested_launch_count = 1; nested_launch_id = 'allocator-batch.chunk_0001' }
        [pscustomobject]@{ row_index = 1; status = 'retry_scheduled'; lifecycle_state = 'retry_scheduled'; nested_launch_count = 0 }
    )
    $allocatorRuntimeRoot = Join-Path $root 'AllocatorRuntime'
    $allocatorManifestRoot = Join-Path $root 'AllocatorManifests'
    $nextAllocation = New-RerunChunkAllocation -Manifest $allocatorManifest -Plans $allocatorPlans -BatchId 'allocator-batch' -NestedRuntimeRoot $allocatorRuntimeRoot -ManifestRoot $allocatorManifestRoot
    Assert-Equal $nextAllocation.chunk_index 2 'Resume allocator reused a completed chunk index.'
    Assert-Equal $nextAllocation.nested_launch_id 'allocator-batch.chunk_0002' 'Resume allocator reused prior nested-launch evidence.'
    Assert-False (Test-RerunSamePath -Left $nextAllocation.nested_pipeline_local_base -Right (Join-Path $allocatorRuntimeRoot 'allocator-batch.chunk_0001')) 'Resume allocator reused prior nested runtime state.'
    Assert-True ($nextAllocation.temp_config_path -match 'chunk_0002\.config\.psd1$') 'Resume allocator reused the prior chunk temp config.'

    # A between-chunk waiting row survives JSON reload, resumes once, and terminal rows do not relaunch.
    $resumeOutputRoot = Join-Path $root 'ResumeOutputs'
    New-Item -ItemType Directory -Path $resumeOutputRoot -Force | Out-Null
    $firstOutput = Join-Path $resumeOutputRoot 'First.mkv'
    $secondOutput = Join-Path $resumeOutputRoot 'Second.mkv'
    Set-Content -LiteralPath $firstOutput -Value 'first-output' -Encoding ASCII
    $firstRow = [pscustomobject][ordered]@{
        row_index = 0; source_path = $promotionSource; source_identity_v2 = $promotionIdentity; planned_source_identity_v2 = $promotionIdentity; source_content_sha256 = $promotionHash.ToLowerInvariant(); planned_source_content_sha256 = $promotionHash.ToLowerInvariant(); source_content_sha256_algorithm = 'sha256-full-file'
        status = 'complete'; lifecycle_state = 'terminal'; nested_launch_count = 1; nested_launch_id = 'resume.chunk_0001'; verified_output_path = $firstOutput
        transition_sequence = 4; timeline = @([pscustomobject]@{ sequence = 4; state = 'terminal' })
    }
    $waitingRow = [pscustomobject][ordered]@{
        row_index = 1; source_path = $dropBackingSource; source_identity_v2 = $dropIdentity; planned_source_identity_v2 = $dropIdentity; source_content_sha256 = $dropHashBefore.ToLowerInvariant(); planned_source_content_sha256 = $dropHashBefore.ToLowerInvariant(); source_content_sha256_algorithm = 'sha256-full-file'
        status = 'retry_scheduled'; lifecycle_state = 'retry_scheduled'; attempt_count = 1; max_attempts = 3; next_retry_at = [datetime]::UtcNow.AddMinutes(1).ToString('o')
        nested_launch_count = 0; nested_launch_id = ''; transition_sequence = 3; timeline = @([pscustomobject]@{ sequence = 3; state = 'retry_scheduled' })
    }
    $betweenManifestPath = Join-Path $root 'between-chunks\execution.json'
    $betweenManifest = [ordered]@{ schema_version = 'rerun_batch_manifest.v2'; batch_id = 'between-chunks'; lifecycle_state = 'retry_scheduled'; status = 'retry_scheduled'; write_sequence = 0; transition_sequence = 3; rows = @($firstRow,$waitingRow) }
    Write-RerunManifest -Path $betweenManifestPath -Payload $betweenManifest
    $reloadedBetween = Get-Content -LiteralPath $betweenManifestPath -Raw | ConvertFrom-Json
    Assert-Equal $reloadedBetween.rows[1].status 'retry_scheduled' 'Between-chunk waiting state did not survive manifest reload.'
    Assert-Equal $reloadedBetween.rows[1].attempt_count 1 'Between-chunk retry attempt count did not survive reload.'
    $freshFirst = [pscustomobject]@{ row_index = 0; source_path = $promotionSource; source_identity_v2 = $promotionIdentity; planned_source_identity_v2 = $promotionIdentity; source_content_sha256 = $promotionHash.ToLowerInvariant(); planned_source_content_sha256 = $promotionHash.ToLowerInvariant(); source_content_sha256_algorithm = 'sha256-full-file'; status = 'pending'; lifecycle_state = 'accepted'; nested_launch_count = 0; timeline = @() }
    $freshSecond = [pscustomobject]@{ row_index = 1; source_path = $dropBackingSource; source_identity_v2 = $dropIdentity; planned_source_identity_v2 = $dropIdentity; source_content_sha256 = $dropHashBefore.ToLowerInvariant(); planned_source_content_sha256 = $dropHashBefore.ToLowerInvariant(); source_content_sha256_algorithm = 'sha256-full-file'; status = 'pending'; lifecycle_state = 'accepted'; nested_launch_count = 0; timeline = @() }
    $firstResume = @(Merge-RerunResumePlans -FreshPlans @($freshFirst,$freshSecond) -ExistingManifest $reloadedBetween -BatchScratchRoot $batchScratch -FfprobePath '')
    $firstResumeWork = @($firstResume | Where-Object { $_.status -in @('pending','waiting','retry_scheduled','staging','staged') })
    Assert-Equal $firstResumeWork.Count 1 'Reload scheduled a terminal first chunk or duplicated the waiting row.'
    Assert-Equal $firstResumeWork[0].row_index 1 'Reload did not isolate the waiting second chunk.'
    Assert-Equal $firstResumeWork[0].attempt_count 1 'Reload lost waiting-row retry history.'
    Set-Content -LiteralPath $secondOutput -Value 'second-output' -Encoding ASCII
    $firstResumeWork[0].status = 'complete'
    $firstResumeWork[0].lifecycle_state = 'terminal'
    $firstResumeWork[0].nested_launch_count = 1
    $firstResumeWork[0] | Add-Member -NotePropertyName nested_launch_id -NotePropertyValue 'resume.chunk_0002' -Force
    $firstResumeWork[0] | Add-Member -NotePropertyName verified_output_path -NotePropertyValue $secondOutput -Force
    $completedReloadManifest = [pscustomobject]@{ rows = @($firstResume); lifecycle_state = 'terminal'; status = 'complete' }
    $secondResume = @(Merge-RerunResumePlans -FreshPlans @($freshFirst,$freshSecond) -ExistingManifest $completedReloadManifest -BatchScratchRoot $batchScratch -FfprobePath '')
    $secondResumeWork = @($secondResume | Where-Object { $_.status -in @('pending','waiting','retry_scheduled','staging','staged') })
    Assert-Equal $secondResumeWork.Count 0 'A second reload attempted to relaunch already-terminal work.'
    Assert-Equal (@($secondResume | Measure-Object -Property nested_launch_count -Sum).Sum) 2 'Nested launch evidence is not exactly once per completed row.'
    Assert-Equal @($secondResume | Select-Object -ExpandProperty verified_output_path -Unique).Count 2 'Reload collapsed or duplicated output evidence.'

    # Correlation is written to the supplied execution manifest without mutating enrollment.
    $localBase = Join-Path $root 'CorrelationLocal'
    $outsource = Join-Path $root 'CorrelationOut'
    $config = Join-Path $root 'correlation.psd1'
    New-RerunFixtureConfig -Path $config -LocalBase $localBase -Outsource $outsource
    $csv = Join-Path $root 'correlation.csv'
    @"
enabled,source_path,media_kind,source_identity_v2
true,"$missingSource",Movie,$('d' * 64)
"@ | Set-Content -LiteralPath $csv -Encoding UTF8
    $batchId = 'rerun-correlation-fixture'
    $manifestPath = Join-Path $localBase "RerunManifests\$batchId.json"
    $enrollmentPath = Join-Path $localBase "State\Rerun\Local\$batchId.json"
    New-Item -ItemType Directory -Path (Split-Path -Parent $enrollmentPath) -Force | Out-Null
    $enrollmentSentinel = '{"authority":"python-enrollment","unchanged":true}'
    [System.IO.File]::WriteAllText($enrollmentPath, $enrollmentSentinel, [System.Text.UTF8Encoding]::new($false))
    $correlation = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript,
        '-CsvPath', $csv, '-ConfigPath', $config,
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-CommandId', 'command-fixture', '-LaunchId', 'launch-fixture', '-BatchId', $batchId,
        '-EnrollmentPath', $enrollmentPath, '-ManifestPath', $manifestPath,
        '-SourceRetryMaxAttempts', '1', '-SourceRetryBackoffSeconds', '0'
    )
    Assert-True ($correlation.ExitCode -ne 0) 'Missing leaf live run should fail after writing terminal evidence.'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Supplied execution manifest was not created.'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Assert-Equal $manifest.schema_version 'rerun_batch_manifest.v2' 'Execution manifest schema was not upgraded.'
    Assert-Equal $manifest.command_id 'command-fixture' 'Command correlation was not persisted.'
    Assert-Equal $manifest.launch_id 'launch-fixture' 'Launch correlation was not persisted.'
    Assert-Equal $manifest.batch_id $batchId 'Batch correlation was not persisted.'
    Assert-Equal $manifest.enrollment_path $enrollmentPath 'Enrollment reference was not persisted.'
    Assert-Equal ([System.IO.File]::ReadAllText($enrollmentPath)) $enrollmentSentinel 'PowerShell mutated the Python enrollment authority.'
    Assert-Equal $manifest.lifecycle_state $manifest.timeline[-1].state 'Manifest current lifecycle state differs from its latest transition.'
    foreach ($manifestRow in @($manifest.rows)) {
        if (@($manifestRow.timeline).Count -gt 0) {
            Assert-Equal $manifestRow.lifecycle_state $manifestRow.timeline[-1].state "Row $($manifestRow.row_index) lifecycle state differs from its latest transition."
        }
    }
    $states = @($manifest.timeline | ForEach-Object { [string]$_.state })
    foreach ($requiredState in @('requested','accepted','manifest_created','terminal')) {
        Assert-True ($states -contains $requiredState) "Execution manifest omitted the $requiredState transition."
    }
    $sequences = @($manifest.timeline | ForEach-Object { [int]$_.sequence })
    for ($index = 1; $index -lt $sequences.Count; $index++) {
        Assert-True ($sequences[$index] -gt $sequences[$index - 1]) 'Manifest transition sequence is not strictly monotonic.'
    }
    foreach ($timelineEvent in @($manifest.timeline)) {
        foreach ($field in @('what','why','when','next')) {
            Assert-True ($null -ne $timelineEvent.PSObject.Properties[$field]) "Lifecycle event omitted '$field'."
        }
    }

    $generatedCorrelationBatch = 'rerun-generated-correlation'
    $generatedCorrelationManifestPath = Join-Path $localBase "RerunManifests\$generatedCorrelationBatch.json"
    $generatedCorrelationRun = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript,
        '-CsvPath', $csv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-BatchId', $generatedCorrelationBatch, '-ManifestPath', $generatedCorrelationManifestPath
    )
    Assert-Equal $generatedCorrelationRun.ExitCode 0 'Direct non-PlanOnly invocation without IDs should generate stable correlation.'
    $generatedCorrelationManifest = Get-Content -LiteralPath $generatedCorrelationManifestPath -Raw | ConvertFrom-Json
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$generatedCorrelationManifest.command_id)) 'Direct live manifest retained a blank command_id.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$generatedCorrelationManifest.launch_id)) 'Direct live manifest retained a blank launch_id.'

    $resumeCorrelationBatch = 'rerun-resume-correlation'
    $resumeCorrelationManifestPath = Join-Path $localBase "RerunManifests\$resumeCorrelationBatch.json"
    $resumeCorrelationEnrollmentPath = Join-Path $localBase "State\Rerun\Local\$resumeCorrelationBatch.json"
    $resumeEnrollmentSentinel = '{"authority":"python-enrollment","resume":true}'
    [System.IO.File]::WriteAllText($resumeCorrelationEnrollmentPath, $resumeEnrollmentSentinel, [System.Text.UTF8Encoding]::new($false))
    $resumeCorrelationPayload = [ordered]@{
        schema_version = 'rerun_batch_manifest.v2'
        command_id = 'resume-command'
        launch_id = 'resume-launch'
        batch_id = $resumeCorrelationBatch
        enrollment_path = $resumeCorrelationEnrollmentPath
        manifest_path = $resumeCorrelationManifestPath
        lifecycle_state = 'accepted'
        status = 'accepted'
        transition_sequence = 1
        write_sequence = 0
        timeline = @([pscustomobject]@{ sequence = 1; state = 'accepted'; what = 'Accepted.'; why = 'Fixture.'; when = [datetime]::UtcNow.ToString('o'); next = 'Resume.' })
        rows = @()
    }
    Write-RerunManifest -Path $resumeCorrelationManifestPath -Payload $resumeCorrelationPayload
    $resumeWithoutIds = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript,
        '-CsvPath', $csv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-BatchId', $resumeCorrelationBatch, '-EnrollmentPath', $resumeCorrelationEnrollmentPath, '-ManifestPath', $resumeCorrelationManifestPath
    )
    Assert-Equal $resumeWithoutIds.ExitCode 0 'Resume with omitted IDs should preserve accepted correlation.'
    $resumedCorrelationManifest = Get-Content -LiteralPath $resumeCorrelationManifestPath -Raw | ConvertFrom-Json
    Assert-Equal $resumedCorrelationManifest.command_id 'resume-command' 'Resume overwrote command_id with a blank or generated value.'
    Assert-Equal $resumedCorrelationManifest.launch_id 'resume-launch' 'Resume overwrote launch_id with a blank or generated value.'
    Assert-Equal $resumedCorrelationManifest.enrollment_path $resumeCorrelationEnrollmentPath 'Resume changed the Python enrollment reference.'
    Assert-Equal ([System.IO.File]::ReadAllText($resumeCorrelationEnrollmentPath)) $resumeEnrollmentSentinel 'Resume mutated Python enrollment authority.'

    $mismatchBatch = 'rerun-mismatched-correlation'
    $mismatchManifestPath = Join-Path $localBase "RerunManifests\$mismatchBatch.json"
    $mismatchEnrollmentPath = Join-Path $localBase "State\Rerun\Local\$mismatchBatch.json"
    [System.IO.File]::WriteAllText($mismatchEnrollmentPath, '{"authority":"python-enrollment","mismatch":false}', [System.Text.UTF8Encoding]::new($false))
    $mismatchPayload = [ordered]@{
        schema_version = 'rerun_batch_manifest.v2'; command_id = 'mismatch-command'; launch_id = 'mismatch-launch'; batch_id = $mismatchBatch
        enrollment_path = $mismatchEnrollmentPath; manifest_path = $mismatchManifestPath; lifecycle_state = 'accepted'; status = 'accepted'
        transition_sequence = 1; write_sequence = 0; timeline = @([pscustomobject]@{ sequence = 1; state = 'accepted' }); rows = @()
    }
    Write-RerunManifest -Path $mismatchManifestPath -Payload $mismatchPayload
    $mismatchBytes = [System.IO.File]::ReadAllBytes($mismatchManifestPath)
    $commandMismatch = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript, '-CsvPath', $csv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-CommandId', 'different-command', '-LaunchId', 'mismatch-launch', '-BatchId', $mismatchBatch,
        '-EnrollmentPath', $mismatchEnrollmentPath, '-ManifestPath', $mismatchManifestPath
    )
    Assert-True ($commandMismatch.ExitCode -ne 0) 'Supplied command_id mismatch was accepted.'
    Assert-Equal ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($mismatchManifestPath))) ([Convert]::ToBase64String($mismatchBytes)) 'Command mismatch changed manifest bytes.'
    $launchMismatch = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript, '-CsvPath', $csv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-CommandId', 'mismatch-command', '-LaunchId', 'different-launch', '-BatchId', $mismatchBatch,
        '-EnrollmentPath', $mismatchEnrollmentPath, '-ManifestPath', $mismatchManifestPath
    )
    Assert-True ($launchMismatch.ExitCode -ne 0) 'Supplied launch_id mismatch was accepted.'
    Assert-Equal ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($mismatchManifestPath))) ([Convert]::ToBase64String($mismatchBytes)) 'Launch mismatch changed manifest bytes.'

    $blankCorrelationBatch = 'rerun-blank-v2-correlation'
    $blankCorrelationManifestPath = Join-Path $localBase "RerunManifests\$blankCorrelationBatch.json"
    $blankCorrelationEnrollmentPath = Join-Path $localBase "State\Rerun\Local\$blankCorrelationBatch.json"
    [System.IO.File]::WriteAllText($blankCorrelationEnrollmentPath, '{"authority":"python-enrollment","blank":true}', [System.Text.UTF8Encoding]::new($false))
    $blankCorrelationPayload = [ordered]@{
        schema_version = 'rerun_batch_manifest.v2'; command_id = ''; launch_id = ''; batch_id = $blankCorrelationBatch
        enrollment_path = $blankCorrelationEnrollmentPath; manifest_path = $blankCorrelationManifestPath; lifecycle_state = 'accepted'; status = 'accepted'
        transition_sequence = 1; write_sequence = 1; timeline = @([pscustomobject]@{ sequence = 1; state = 'accepted' }); rows = @()
    }
    [System.IO.File]::WriteAllText($blankCorrelationManifestPath, ($blankCorrelationPayload | ConvertTo-Json -Depth 12), [System.Text.UTF8Encoding]::new($false))
    $blankCorrelationBytes = [System.IO.File]::ReadAllBytes($blankCorrelationManifestPath)
    $blankCorrelationResume = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript, '-CsvPath', $csv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-CommandId', 'replacement-command', '-LaunchId', 'replacement-launch', '-BatchId', $blankCorrelationBatch,
        '-EnrollmentPath', $blankCorrelationEnrollmentPath, '-ManifestPath', $blankCorrelationManifestPath
    )
    Assert-True ($blankCorrelationResume.ExitCode -ne 0) 'Unsafe blank v2 correlation was silently replaced during resume.'
    Assert-Equal ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($blankCorrelationManifestPath))) ([Convert]::ToBase64String($blankCorrelationBytes)) 'Rejected blank v2 correlation changed manifest bytes.'

    $pathBindingBatch = 'rerun-path-binding'
    $wrongManifestPath = Join-Path $localBase 'RerunManifests\wrong-manifest-name.json'
    $wrongManifestRun = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript, '-CsvPath', $csv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-BatchId', $pathBindingBatch, '-ManifestPath', $wrongManifestPath
    )
    Assert-True ($wrongManifestRun.ExitCode -ne 0) 'ManifestPath basename was not bound to BatchId.'
    Assert-False (Test-Path -LiteralPath $wrongManifestPath) 'Rejected mismatched ManifestPath was written.'

    $enrollmentBindingBatch = 'rerun-enrollment-binding'
    $enrollmentBindingManifestPath = Join-Path $localBase "RerunManifests\$enrollmentBindingBatch.json"
    $wrongEnrollmentPath = Join-Path $localBase 'State\Rerun\Local\wrong-enrollment-name.json'
    $wrongEnrollmentSentinel = '{"authority":"python-enrollment","wrong-path":true}'
    [System.IO.File]::WriteAllText($wrongEnrollmentPath, $wrongEnrollmentSentinel, [System.Text.UTF8Encoding]::new($false))
    $wrongEnrollmentRun = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript, '-CsvPath', $csv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-BatchId', $enrollmentBindingBatch, '-EnrollmentPath', $wrongEnrollmentPath, '-ManifestPath', $enrollmentBindingManifestPath
    )
    Assert-True ($wrongEnrollmentRun.ExitCode -ne 0) 'EnrollmentPath basename was not bound to BatchId.'
    Assert-False (Test-Path -LiteralPath $enrollmentBindingManifestPath) 'Rejected mismatched EnrollmentPath still created an execution manifest.'
    Assert-Equal ([System.IO.File]::ReadAllText($wrongEnrollmentPath)) $wrongEnrollmentSentinel 'Rejected EnrollmentPath was mutated.'

    # Exhausted transient rows retain the canonical terminal batch token used by backend manual recovery.
    $exhaustedPrecondition = Get-RerunSourceHealth -SourcePath $offlineSource -ExpectedIdentityV2 ('f' * 64) -FfprobePath ''
    Assert-Equal $exhaustedPrecondition.Code 'source_location_unavailable' 'Retry-exhaustion fixture drive was not durably reserved as offline.'
    $exhaustedCsv = Join-Path $root 'exhausted.csv'
    @"
enabled,source_path,media_kind,source_identity_v2,source_content_sha256,source_content_sha256_algorithm
true,"$offlineSource",Movie,$('f' * 64),$('a' * 64),sha256-full-file
"@ | Set-Content -LiteralPath $exhaustedCsv -Encoding UTF8
    $exhaustedBatch = 'rerun-exhausted-fixture'
    $exhaustedManifestPath = Join-Path $localBase "RerunManifests\$exhaustedBatch.json"
    $exhaustedRun = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript,
        '-CsvPath', $exhaustedCsv, '-ConfigPath', $config,
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-BatchId', $exhaustedBatch, '-ManifestPath', $exhaustedManifestPath,
        '-SourceRetryMaxAttempts', '1', '-SourceRetryBackoffSeconds', '0'
    )
    Assert-True ($exhaustedRun.ExitCode -ne 0) 'Retry-exhausted live run should return a failed process exit.'
    $exhaustedManifest = Get-Content -LiteralPath $exhaustedManifestPath -Raw | ConvertFrom-Json
    Assert-Equal $exhaustedManifest.status 'completed_with_failures' 'Retry exhaustion used a noncanonical terminal batch status.'
    Assert-Equal $exhaustedManifest.lifecycle_state 'terminal' 'Retry exhaustion did not finalize the execution manifest.'
    Assert-Equal $exhaustedManifest.rows[0].status 'retry_exhausted' 'Retry exhaustion was not retained at row scope.'
    Assert-Equal $exhaustedManifest.failed_count 1 'Retry exhaustion was not included in terminal failure counts.'

    # PlanOnly accepts correlation inputs but still writes no execution manifest or media workspace.
    $planOnlyManifest = Join-Path $localBase 'RerunManifests\plan-batch.json'
    $planOnly = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript,
        '-CsvPath', $csv, '-ConfigPath', $config, '-PlanOnly',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-CommandId', 'plan-command', '-LaunchId', 'plan-launch', '-BatchId', 'plan-batch',
        '-ManifestPath', $planOnlyManifest
    )
    Assert-Equal $planOnly.ExitCode 0 'PlanOnly with correlation parameters should remain a successful read-only plan.'
    Assert-False (Test-Path -LiteralPath $planOnlyManifest) 'PlanOnly wrote an execution manifest.'
    $planOnlyWorkspaceRoot = Join-Path (Split-Path -Parent $localBase) ((Split-Path -Leaf $localBase) + '_RerunWorkspace')
    Assert-False (Test-Path -LiteralPath (Join-Path $planOnlyWorkspaceRoot 'RerunQueue\plan-batch')) 'PlanOnly created a batch scratch workspace.'
    Assert-False (Test-Path -LiteralPath (Join-Path $planOnlyWorkspaceRoot 'RerunParked\plan-batch')) 'PlanOnly created a batch park workspace.'
    Assert-Equal @(Get-ChildItem -LiteralPath (Join-Path $localBase 'RerunManifests') -Filter 'plan-batch.chunk_*.config.psd1' -ErrorAction SilentlyContinue).Count 0 'PlanOnly wrote a nested temp config.'

    # Mixed roots remain independently classified in one dry-run manifest.
    $healthySource = Join-Path $healthyRoot 'Healthy Movie.mkv'
    [System.IO.File]::WriteAllBytes($healthySource, [System.Text.Encoding]::UTF8.GetBytes('healthy-source'))
    $healthyIdentity = Get-RerunSourceIdentityV2 -FileInfo (Get-Item -LiteralPath $healthySource) -FfprobePath ''
    $healthyContentSha256 = Get-RerunContentSha256 -Path $healthySource
    $mixedCsv = Join-Path $root 'mixed.csv'
    @"
enabled,source_path,media_kind,source_identity_v2,source_content_sha256,source_content_sha256_algorithm
true,"$offlineSource",Movie,$('e' * 64),$('b' * 64),sha256-full-file
true,"$healthySource",Movie,$healthyIdentity,$healthyContentSha256,sha256-full-file
"@ | Set-Content -LiteralPath $mixedCsv -Encoding UTF8
    $mixedBatch = 'rerun-mixed-roots'
    $mixedManifestPath = Join-Path $localBase "RerunManifests\$mixedBatch.json"
    $mixed = Invoke-RerunChild -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $rerunScript,
        '-CsvPath', $mixedCsv, '-ConfigPath', $config, '-DryRun',
        '-DefaultReturnMode', 'park', '-DestinationMode', 'review_workspace', '-CollisionPolicy', 'suffix',
        '-BatchId', $mixedBatch, '-ManifestPath', $mixedManifestPath
    )
    Assert-Equal $mixed.ExitCode 0 'Mixed-root dry run should complete without staging media.'
    $mixedManifest = Get-Content -LiteralPath $mixedManifestPath -Raw | ConvertFrom-Json
    $offlineRow = @($mixedManifest.rows | Where-Object { $_.source_path -eq $offlineSource })[0]
    $healthyRow = @($mixedManifest.rows | Where-Object { $_.source_path -eq $healthySource })[0]
    Assert-Equal $offlineRow.status 'waiting' 'Offline-root row did not remain independently recoverable.'
    Assert-Equal $offlineRow.reason_code 'source_location_unavailable' 'Offline-root row lost its typed reason.'
    Assert-Equal $healthyRow.status 'pending' 'Healthy-root row was blocked by another root outage.'
    Assert-Equal $offlineRow.lifecycle_state $offlineRow.timeline[-1].state 'Offline row lifecycle state differs from its latest transition.'
    Assert-Equal $healthyRow.lifecycle_state $healthyRow.timeline[-1].state 'Healthy row lifecycle state differs from its latest transition.'
    Assert-False (Test-Path -LiteralPath $healthyRow.stage_path -PathType Leaf) 'Dry-run staged healthy media.'
} finally {
    & subst.exe "${driveName}:" /D 2>$null | Out-Null
    if (Test-Path -LiteralPath $root) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'Rerun recovery checks passed.'
