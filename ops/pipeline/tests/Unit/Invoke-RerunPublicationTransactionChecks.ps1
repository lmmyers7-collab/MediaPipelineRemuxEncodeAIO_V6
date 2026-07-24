[CmdletBinding()]
param([switch]$RepresentativeMedia)

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Rerun publication transaction checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$rerunRoot = Join-Path $pipelineRoot 'engine\rerun'
. (Join-Path $rerunRoot 'entry_support.ps1')
. (Join-Path $rerunRoot 'evidence.ps1')
. (Join-Path $rerunRoot 'recovery.ps1')
. (Join-Path $rerunRoot 'publication_transaction.ps1')
. (Join-Path $rerunRoot 'publish.ps1')

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string]$Message)
    if ($Actual -ne $Expected) { throw "$Message Expected=[$Expected] Actual=[$Actual]" }
}

function Get-Text {
    param([Parameter(Mandatory)] [string]$Path)
    return (Get-Content -LiteralPath $Path -Raw).Trim()
}

function New-PublicationFixture {
    param([Parameter(Mandatory)] [string]$Root, [Parameter(Mandatory)] [string]$Name, [switch]$WithExistingFinal)
    $fixtureRoot = Join-Path $Root $Name
    $verifiedRoot = Join-Path $fixtureRoot 'verified'
    $finalRoot = Join-Path $fixtureRoot 'final'
    $holdRoot = Join-Path $fixtureRoot 'hold'
    $stateRoot = Join-Path $fixtureRoot 'state'
    New-Item -ItemType Directory -Path $verifiedRoot,$finalRoot,$holdRoot,$stateRoot -Force | Out-Null
    $source = Join-Path $fixtureRoot 'source\Movie.mkv'
    New-Item -ItemType Directory -Path (Split-Path -Parent $source) -Force | Out-Null
    Set-Content -LiteralPath $source -Value 'immutable-source-media' -Encoding ASCII
    $verified = Join-Path $verifiedRoot 'Movie.mkv'
    $verifiedSrt = Join-Path $verifiedRoot 'Movie.eng.srt'
    Set-Content -LiteralPath $verified -Value "new-media-$Name" -Encoding ASCII
    Set-Content -LiteralPath $verifiedSrt -Value "new-srt-$Name" -Encoding UTF8
    $verifiedSidecar = Get-RerunPipelineSidecarPath -OutputPath $verified
    [ordered]@{
        schema_version = 'pipeline_sidecar.v1'
        output_path = $verified
        output_file = Split-Path -Leaf $verified
        output_size = [long](Get-Item -LiteralPath $verified).Length
        publish_state = 'published'
        publish_mode = 'immediate'
        tx3g_srt_tracks = @([ordered]@{ path = $verifiedSrt; file_name = Split-Path -Leaf $verifiedSrt; status = 'written'; language = 'eng' })
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $verifiedSidecar -Encoding UTF8
    $destination = Join-Path $finalRoot 'Movie.mkv'
    $destinationSrt = Join-Path $finalRoot 'Movie.eng.srt'
    $destinationSidecar = Get-RerunPipelineSidecarPath -OutputPath $destination
    if ($WithExistingFinal) {
        Set-Content -LiteralPath $destination -Value "old-media-$Name" -Encoding ASCII
        Set-Content -LiteralPath $destinationSrt -Value "old-srt-$Name" -Encoding UTF8
        Set-Content -LiteralPath $destinationSidecar -Value "old-sidecar-$Name" -Encoding UTF8
    }
    $plan = [pscustomobject][ordered]@{
        row_index = 1
        source_path = $source
        verified_output_path = $verified
        planned_output_path = $verified
        final_output_path = $destination
        final_output_root = $finalRoot
        source_overwrite_confirmed = $false
        status = 'complete'
        reason = ''
        original_action = ''
        published_path = ''
        replaced_final_hold_path = ''
        pipeline_sidecar_publish = ''
        pipeline_sidecar_path = ''
        published_sidecar_paths = @()
        replaced_sidecar_hold_paths = @()
        completed_manifest_path = ''
        completed_manifest_append = ''
        publication_transaction_id = ''
        publication_transaction_manifest_path = ''
        publication_transaction_state = ''
    }
    return [pscustomobject]@{
        Root = $fixtureRoot
        Source = $source
        Verified = $verified
        VerifiedSrt = $verifiedSrt
        VerifiedSidecar = $verifiedSidecar
        Destination = $destination
        DestinationSrt = $destinationSrt
        DestinationSidecar = $destinationSidecar
        FinalRoot = $finalRoot
        HoldRoot = $holdRoot
        Completed = Join-Path $stateRoot 'completed_jobs.jsonl'
        Plan = $plan
        Name = $Name
    }
}

function Assert-RolledBackFixture {
    param([Parameter(Mandatory)] $Fixture)
    Assert-Equal (Get-Text $Fixture.Source) 'immutable-source-media' 'Source media changed during publication rollback.'
    Assert-Equal (Get-Text $Fixture.Destination) "old-media-$($Fixture.Name)" 'Original final media was not restored.'
    Assert-Equal (Get-Text $Fixture.DestinationSrt) "old-srt-$($Fixture.Name)" 'Original SRT was not restored.'
    Assert-Equal (Get-Text $Fixture.DestinationSidecar) "old-sidecar-$($Fixture.Name)" 'Original pipeline sidecar was not restored.'
    Assert-True (Test-Path -LiteralPath $Fixture.Verified -PathType Leaf) 'Verified output was consumed by a failed publication.'
    $transaction = Get-Content -LiteralPath ([string]$Fixture.Plan.publication_transaction_manifest_path) -Raw | ConvertFrom-Json
    Assert-Equal ([string]$transaction.state) 'rolled_back' 'Failed publication transaction did not record rolled_back.'
}

function Invoke-ReplacementFixture {
    param([Parameter(Mandatory)] $Fixture, [string]$FaultCheckpoint = '', [switch]$BrokenCompletionPath)
    $script:RerunCompletedJobsManifest = if ($BrokenCompletionPath) { Join-Path $Fixture.Root 'completed-as-directory' } else { $Fixture.Completed }
    if ($BrokenCompletionPath) { New-Item -ItemType Directory -Path $script:RerunCompletedJobsManifest -Force | Out-Null }
    $script:RerunPublicationFaultInjector = if ([string]::IsNullOrWhiteSpace($FaultCheckpoint)) { $null } else {
        { param($checkpoint, $transaction) if ([string]$checkpoint -ceq $FaultCheckpoint) { throw "injected:$FaultCheckpoint" } }.GetNewClosure()
    }
    try {
        Invoke-RerunFinalPublicationTransaction -Plan $Fixture.Plan -VerifiedOutput $Fixture.Verified -Destination $Fixture.Destination -BatchId ('batch-' + $Fixture.Name) -FinalHoldRoot $Fixture.HoldRoot -DestinationPolicy 'publish_replace_final' -SuccessStatus 'published_replace_final' -SuccessReason 'fixture replacement committed' -IsReplacement $true | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        $script:RerunPublicationFaultInjector = $null
    }
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-rerun-publication-transaction-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null

    $nonOverlap = New-PublicationFixture -Root $root -Name 'non-overlap' -WithExistingFinal
    $script:RerunCompletedJobsManifest = $nonOverlap.Completed
    $script:DestinationMode = 'publish_non_overlap'
    $script:CollisionPolicy = 'suffix'
    $script:OriginalPolicy = 'keep'
    $script:ConfirmReplaceFinal = $false
    Invoke-RerunDestinationPolicy -Plans @($nonOverlap.Plan) -BatchId 'batch-non-overlap' -PendingRoot (Join-Path $nonOverlap.Root 'pending') -FinalHoldRoot $nonOverlap.HoldRoot -OriginalHoldRoot (Join-Path $nonOverlap.Root 'original-hold')
    Assert-Equal ([string]$nonOverlap.Plan.status) 'published_non_overlap' 'Non-overlap publication did not succeed.'
    Assert-Equal (Get-Text $nonOverlap.Source) 'immutable-source-media' 'Non-overlap publication mutated source media.'
    Assert-True (([string]$nonOverlap.Plan.published_path) -ne $nonOverlap.Destination) 'Non-overlap publication reused the colliding final path.'
    $nonOverlapFinal = [string]$nonOverlap.Plan.published_path
    Assert-True (Test-Path -LiteralPath $nonOverlapFinal -PathType Leaf) 'Non-overlap media is missing.'
    Assert-True (Test-Path -LiteralPath (Get-RerunPipelineSidecarPath -OutputPath $nonOverlapFinal) -PathType Leaf) 'Non-overlap pipeline sidecar is missing.'
    Assert-True (Test-Path -LiteralPath ([System.IO.Path]::ChangeExtension($nonOverlapFinal, '.eng.srt')) -PathType Leaf) 'Non-overlap SRT is missing.'
    Assert-Equal ([int]@(Get-Content -LiteralPath $nonOverlap.Completed).Count) 1 'Non-overlap completion evidence was not appended exactly once.'
    $nonOverlapCompleted = Get-Content -LiteralPath $nonOverlap.Completed -Raw | ConvertFrom-Json
    Assert-Equal ([string]$nonOverlapCompleted.completed_manifest_source) 'csv_rerun_publish_non_overlap' 'Non-overlap completion source is incorrect.'

    foreach ($checkpoint in @('media_staged','srt_staged','companions_staged','artifact_committed:media','artifact_committed:srt','artifact_committed:pipeline_sidecar','artifacts_committed')) {
        $name = ($checkpoint -replace '[^A-Za-z0-9]+','-').Trim('-')
        $fixture = New-PublicationFixture -Root $root -Name $name -WithExistingFinal
        Assert-True (-not (Invoke-ReplacementFixture -Fixture $fixture -FaultCheckpoint $checkpoint)) "Injected checkpoint unexpectedly committed: $checkpoint"
        Assert-RolledBackFixture -Fixture $fixture
        Assert-True (-not (Test-Path -LiteralPath $fixture.Completed -PathType Leaf)) "Completion evidence exists after rollback: $checkpoint"
    }

    $appendFailure = New-PublicationFixture -Root $root -Name 'append-failure' -WithExistingFinal
    Assert-True (-not (Invoke-ReplacementFixture -Fixture $appendFailure -BrokenCompletionPath)) 'Completion append failure unexpectedly committed.'
    Assert-RolledBackFixture -Fixture $appendFailure

    $replacement = New-PublicationFixture -Root $root -Name 'replace-success' -WithExistingFinal
    Assert-True (Invoke-ReplacementFixture -Fixture $replacement) 'Successful replacement transaction failed.'
    Assert-Equal ([string]$replacement.Plan.status) 'published_replace_final' 'Successful replacement status is incorrect.'
    Assert-Equal (Get-Text $replacement.Destination) 'new-media-replace-success' 'Successful replacement media bytes are incorrect.'
    Assert-True (-not (Test-Path -LiteralPath $replacement.Verified -PathType Leaf)) 'Committed verified output was not cleaned up.'
    Assert-Equal (Get-Text $replacement.Source) 'immutable-source-media' 'Successful replacement mutated source media.'
    $replacementTransaction = Get-Content -LiteralPath ([string]$replacement.Plan.publication_transaction_manifest_path) -Raw | ConvertFrom-Json
    Assert-Equal ([string]$replacementTransaction.state) 'committed' 'Successful replacement transaction is not committed.'
    Assert-True (Test-Path -LiteralPath ([string]$replacement.Plan.replaced_final_hold_path) -PathType Leaf) 'Replaced final backup is missing.'
    Assert-Equal (Get-Text ([string]$replacement.Plan.replaced_final_hold_path)) 'old-media-replace-success' 'Replaced final backup bytes are incorrect.'
    Assert-True (Add-RerunCompletedJobsManifestEntry -OutputPath $replacement.Destination -Payload $replacementTransaction.sidecar_payload) 'Idempotent completion replay failed.'
    Assert-Equal ([int]@(Get-Content -LiteralPath $replacement.Completed).Count) 1 'Completion replay duplicated the transaction row.'

    $abandonedPath = Join-Path $root 'abandoned\completed.jsonl'
    $mutexName = Get-RerunJsonLineMutexName -Path $abandonedPath
    $abandonScript = Join-Path $root 'abandon-mutex.ps1'
    @'
param([string]$MutexName)
$mutex = [System.Threading.Mutex]::new($false, $MutexName)
[void]$mutex.WaitOne()
[Environment]::Exit(0)
'@ | Set-Content -LiteralPath $abandonScript -Encoding UTF8
    $pwshHost = (Get-Process -Id $PID).Path
    $abandon = Start-Process -FilePath $pwshHost -ArgumentList @('-NoProfile','-File',$abandonScript,'-MutexName',$mutexName) -WindowStyle Hidden -Wait -PassThru
    Assert-Equal ([int]$abandon.ExitCode) 0 'Abandoned-mutex fixture process failed.'
    Assert-True (Write-RerunJsonLineAppend -Path $abandonedPath -Payload ([ordered]@{ id = 'after-abandon' }) -IdentityField 'id' -IdentityValue 'after-abandon') 'First append after abandoned mutex was rejected.'
    Assert-Equal ([string](Get-Content -LiteralPath $abandonedPath -Raw | ConvertFrom-Json).id) 'after-abandon' 'Abandoned-mutex append wrote incorrect evidence.'

    $childScript = Join-Path $root 'hard-crash-publication.ps1'
    @'
param(
    [string]$RerunRoot,[string]$Source,[string]$Verified,[string]$Destination,[string]$FinalRoot,
    [string]$HoldRoot,[string]$Completed,[string]$BatchId,[string]$Checkpoint
)
$ErrorActionPreference = 'Stop'
. (Join-Path $RerunRoot 'entry_support.ps1')
. (Join-Path $RerunRoot 'evidence.ps1')
. (Join-Path $RerunRoot 'recovery.ps1')
. (Join-Path $RerunRoot 'publication_transaction.ps1')
. (Join-Path $RerunRoot 'publish.ps1')
$script:RerunCompletedJobsManifest = $Completed
$plan = [pscustomobject][ordered]@{
    row_index=1; source_path=$Source; verified_output_path=$Verified; final_output_path=$Destination; final_output_root=$FinalRoot;
    source_overwrite_confirmed=$false; status='complete'; reason=''; original_action=''; published_path=''; replaced_final_hold_path='';
    pipeline_sidecar_publish=''; pipeline_sidecar_path=''; published_sidecar_paths=@(); replaced_sidecar_hold_paths=@();
    completed_manifest_path=''; completed_manifest_append=''; publication_transaction_id=''; publication_transaction_manifest_path=''; publication_transaction_state=''
}
$script:RerunPublicationFaultInjector = {
    param($name,$transaction)
    if ([string]$name -ceq $Checkpoint) { Stop-Process -Id $PID -Force }
}.GetNewClosure()
Invoke-RerunFinalPublicationTransaction -Plan $plan -VerifiedOutput $Verified -Destination $Destination -BatchId $BatchId -FinalHoldRoot $HoldRoot -DestinationPolicy 'publish_replace_final' -SuccessStatus 'published_replace_final' -SuccessReason 'hard-crash fixture' -IsReplacement $true | Out-Null
'@ | Set-Content -LiteralPath $childScript -Encoding UTF8
    $repairScript = Join-Path $root 'repair-publication.ps1'
    @'
param([string]$RerunRoot,[string]$TransactionPath,[string]$ResultPath)
$ErrorActionPreference = 'Stop'
. (Join-Path $RerunRoot 'entry_support.ps1')
. (Join-Path $RerunRoot 'evidence.ps1')
. (Join-Path $RerunRoot 'recovery.ps1')
. (Join-Path $RerunRoot 'publication_transaction.ps1')
. (Join-Path $RerunRoot 'publish.ps1')
$result = Repair-RerunFinalPublicationTransaction -TransactionPath $TransactionPath
[System.IO.File]::WriteAllText($ResultPath, [string]$result.Status, [System.Text.UTF8Encoding]::new($false))
'@ | Set-Content -LiteralPath $repairScript -Encoding UTF8

    foreach ($hardCheckpoint in @('artifact_committed:media','completion_appended')) {
        $hardName = 'hard-' + ($hardCheckpoint -replace '[^A-Za-z0-9]+','-').Trim('-')
        $hard = New-PublicationFixture -Root $root -Name $hardName -WithExistingFinal
        $hardBatch = 'batch-' + $hardName
        $childArgs = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$childScript,'-RerunRoot',$rerunRoot,'-Source',$hard.Source,'-Verified',$hard.Verified,'-Destination',$hard.Destination,'-FinalRoot',$hard.FinalRoot,'-HoldRoot',$hard.HoldRoot,'-Completed',$hard.Completed,'-BatchId',$hardBatch,'-Checkpoint',$hardCheckpoint)
        $child = Start-Process -FilePath $pwshHost -ArgumentList $childArgs -WindowStyle Hidden -Wait -PassThru
        Assert-True ([int]$child.ExitCode -ne 0) "Hard-crash child unexpectedly exited cleanly: $hardCheckpoint"
        $transactionPath = @(Get-ChildItem -LiteralPath (Join-Path (Join-Path $hard.HoldRoot $hardBatch) 'PublicationTransactions') -Filter '*.publication.json' -File)[0].FullName
        $repairResult = Join-Path $hard.Root 'repair-result.txt'
        $repair = Start-Process -FilePath $pwshHost -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$repairScript,'-RerunRoot',$rerunRoot,'-TransactionPath',$transactionPath,'-ResultPath',$repairResult) -WindowStyle Hidden -Wait -PassThru
        Assert-Equal ([int]$repair.ExitCode) 0 "Distinct-process publication repair failed: $hardCheckpoint"
        $status = Get-Text $repairResult
        if ($hardCheckpoint -eq 'completion_appended') {
            Assert-Equal $status 'committed' 'Completion-backed restart recovery did not finalize committed state.'
            Assert-Equal (Get-Text $hard.Destination) "new-media-$hardName" 'Committed restart recovery changed final media.'
            Assert-True (-not (Test-Path -LiteralPath $hard.Verified -PathType Leaf)) 'Hard-crash commit retained verified media unexpectedly.'
        } else {
            Assert-Equal $status 'rolled_back' 'Partial restart recovery did not roll back.'
            Assert-Equal (Get-Text $hard.Destination) "old-media-$hardName" 'Partial restart recovery did not restore old media.'
            Assert-True (Test-Path -LiteralPath $hard.Verified -PathType Leaf) 'Partial restart recovery consumed verified media.'
        }
        Assert-Equal (Get-Text $hard.Source) 'immutable-source-media' 'Hard-crash recovery mutated source media.'
    }

    if ($RepresentativeMedia) {
        $ffmpeg = Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffmpeg.exe'
        $ffprobe = Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffprobe.exe'
        Assert-True (Test-Path -LiteralPath $ffmpeg -PathType Leaf) 'Representative rerun publication requires bundled ffmpeg.'
        Assert-True (Test-Path -LiteralPath $ffprobe -PathType Leaf) 'Representative rerun publication requires bundled ffprobe.'
        $media = New-PublicationFixture -Root $root -Name 'representative-media' -WithExistingFinal
        & $ffmpeg -y -hide_banner -loglevel error -f lavfi -i 'color=c=green:s=160x90:d=1' -f lavfi -i 'sine=frequency=330:duration=1' -c:v mpeg4 -q:v 5 -c:a aac -shortest $media.Source
        Assert-Equal $LASTEXITCODE 0 'Failed to generate representative source media.'
        & $ffmpeg -y -hide_banner -loglevel error -f lavfi -i 'color=c=blue:s=160x90:d=1' -f lavfi -i 'sine=frequency=440:duration=1' -c:v mpeg4 -q:v 5 -c:a aac -shortest $media.Verified
        Assert-Equal $LASTEXITCODE 0 'Failed to generate representative verified media.'
        & $ffmpeg -y -hide_banner -loglevel error -f lavfi -i 'color=c=red:s=160x90:d=1' -f lavfi -i 'sine=frequency=550:duration=1' -c:v mpeg4 -q:v 5 -c:a aac -shortest $media.Destination
        Assert-Equal $LASTEXITCODE 0 'Failed to generate representative old final media.'
        $sourceHashBefore = (Get-FileHash -LiteralPath $media.Source -Algorithm SHA256).Hash
        $sidecar = Get-Content -LiteralPath $media.VerifiedSidecar -Raw | ConvertFrom-Json
        $sidecar.output_size = [long](Get-Item -LiteralPath $media.Verified).Length
        $sidecar | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $media.VerifiedSidecar -Encoding UTF8
        Assert-True (Invoke-ReplacementFixture -Fixture $media) 'Representative media replacement transaction failed.'
        $probe = (& $ffprobe -v error -show_entries 'format=duration' -show_streams -of json $media.Destination | Out-String) | ConvertFrom-Json
        Assert-Equal $LASTEXITCODE 0 'Representative final output failed ffprobe.'
        Assert-True (@($probe.streams).Count -ge 2) 'Representative final output did not preserve generated video/audio topology.'
        Assert-True ([double]$probe.format.duration -gt 0) 'Representative final output duration is invalid.'
        Assert-True (Test-Path -LiteralPath $media.DestinationSrt -PathType Leaf) 'Representative external SRT was not published.'
        Assert-True (Test-Path -LiteralPath $media.DestinationSidecar -PathType Leaf) 'Representative canonical pipeline sidecar was not published.'
        Assert-Equal (Get-Text $media.DestinationSrt) 'new-srt-representative-media' 'Representative external SRT bytes changed.'
        Assert-Equal (Get-FileHash -LiteralPath $media.Source -Algorithm SHA256).Hash $sourceHashBefore 'Representative source media changed.'
        Assert-Equal ([int]@(Get-Content -LiteralPath $media.Completed).Count) 1 'Representative completion evidence was not appended exactly once.'
    }
} finally {
    $script:RerunPublicationFaultInjector = $null
    if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host 'Rerun publication transaction checks passed.'
