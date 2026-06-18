[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Path boundary guard checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\path_helpers.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\paths\output_path_planning.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\storage\disk.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\audit\probe.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\shared\temp_cleanup.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\storage\scratch_copy.ps1')

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function Write-AuditLog {
    param([string] $Message, [string] $Level = 'INFO')
}

function Invoke-RecursivePathScan {
    param(
        [string] $Path,
        [string] $ItemType = 'File',
        [int] $TimeoutSeconds = 300,
        [string] $Label = 'scan'
    )
    if ($ItemType -eq 'Directory') {
        return @(Get-ChildItem -LiteralPath $Path -Directory -Recurse -Force | ForEach-Object { $_.FullName })
    }
    return @(Get-ChildItem -LiteralPath $Path -File -Recurse -Force | ForEach-Object { $_.FullName })
}

function Resolve-RobocopyPath {
    return 'robocopy.exe'
}

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

function Invoke-WithTempRoot {
    param([Parameter(Mandatory)] [scriptblock] $Body)
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-path-boundary-" + [guid]::NewGuid().ToString("N"))
    try {
        [System.IO.Directory]::CreateDirectory($root) | Out-Null
        & $Body ([System.IO.DirectoryInfo]::new($root))
    } finally {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Set-OldTestItem {
    param([Parameter(Mandatory)] [string] $Path)

    $item = Get-Item -LiteralPath $Path -Force
    $item.LastWriteTime = (Get-Date).AddHours(-25)
}

Invoke-WithTempRoot {
    param($Root)
    $script:CleanupStaleAgeHours = 1
    $script:CleanupScanTimeoutSeconds = 30
    $script:CleanupRemoteStaging = $true

    $copyPartial = Join-Path $Root.FullName ('Movie.mkv.mp-partial.' + ('a' * 32))
    $publishPartial = Join-Path $Root.FullName ('.Movie.mkv.mp-publish-partial.' + ('b' * 32))
    $publishBackup = Join-Path $Root.FullName ('.Movie.mkv.mp-publish-backup.' + ('c' * 32))
    $userOwnedMatchingName = Join-Path $Root.FullName 'Movie.mp-partial-cut.mkv'
    $uncertainPublishPartial = Join-Path $Root.FullName '.Movie.mkv.mp-publish-partial.tx-test'
    $freshCopyPartial = Join-Path $Root.FullName ('Fresh.mkv.mp-partial.' + ('d' * 32))

    foreach ($path in @($copyPartial, $publishPartial, $publishBackup, $userOwnedMatchingName, $uncertainPublishPartial, $freshCopyPartial)) {
        [System.IO.File]::WriteAllText($path, 'fixture', [System.Text.UTF8Encoding]::new($false))
    }
    foreach ($path in @($copyPartial, $publishPartial, $publishBackup, $userOwnedMatchingName, $uncertainPublishPartial)) {
        Set-OldTestItem -Path $path
    }

    $oldStaging = Join-Path (Join-Path $Root.FullName 'old-stage') '.mediapipeline-staging'
    $freshStaging = Join-Path (Join-Path $Root.FullName 'fresh-stage') '.mediapipeline-staging'
    [System.IO.Directory]::CreateDirectory($oldStaging) | Out-Null
    [System.IO.Directory]::CreateDirectory($freshStaging) | Out-Null
    Set-OldTestItem -Path $oldStaging

    Clear-StalePartialFiles -Roots @($Root.FullName)

    Assert-True (-not (Test-Path -LiteralPath $copyPartial -ErrorAction SilentlyContinue)) 'Generated copy partial should be removed when stale.'
    Assert-True (-not (Test-Path -LiteralPath $publishPartial -ErrorAction SilentlyContinue)) 'Generated publish partial should be removed when stale.'
    Assert-True (-not (Test-Path -LiteralPath $publishBackup -ErrorAction SilentlyContinue)) 'Generated publish backup should be removed when stale.'
    Assert-True (Test-Path -LiteralPath $userOwnedMatchingName -PathType Leaf) 'User-owned files that merely contain mp-partial text must be preserved.'
    Assert-True (Test-Path -LiteralPath $uncertainPublishPartial -PathType Leaf) 'Publish-looking files without generated transaction ids must be preserved.'
    Assert-True (Test-Path -LiteralPath $freshCopyPartial -PathType Leaf) 'Fresh generated partial files must be preserved.'
    Assert-True (-not (Test-Path -LiteralPath $oldStaging -ErrorAction SilentlyContinue)) 'Old publish staging directories should still be removed.'
    Assert-True (Test-Path -LiteralPath $freshStaging -PathType Container) 'Fresh publish staging directories must be preserved.'
}

Invoke-WithTempRoot {
    param($Root)
    $safeRoot = Join-Path $Root.FullName 'root'
    $nested = Join-Path $safeRoot 'nested'
    [System.IO.Directory]::CreateDirectory($nested) | Out-Null
    $file = Join-Path $nested 'file.txt'
    [System.IO.File]::WriteAllText($file, 'ok')

    $ok = Test-MediaPipelinePathBoundarySafe -Path $file -Root $safeRoot
    Assert-True ([bool]$ok.Ok) 'Expected nested file to pass boundary guard.'

    $outside = Join-Path $Root.FullName 'outside.txt'
    [System.IO.File]::WriteAllText($outside, 'outside')
    $outsideResult = Test-MediaPipelinePathBoundarySafe -Path $outside -Root $safeRoot
    Assert-Equal $outsideResult.ReasonCode 'OUTSIDE_ALLOWED_ROOT' 'Outside file should be rejected.'

    $rootTarget = Test-MediaPipelinePathBoundarySafe -Path $safeRoot -Root $safeRoot
    Assert-Equal $rootTarget.ReasonCode 'ROOT_MUTATION_TARGET' 'Root mutation target should be rejected.'

    $missingLeaf = Test-MediaPipelinePathBoundarySafe -Path (Join-Path $nested 'missing.txt') -Root $safeRoot -AllowMissingLeaf
    Assert-True ([bool]$missingLeaf.Ok) 'Missing leaf under existing parent should pass with AllowMissingLeaf.'
}

Invoke-WithTempRoot {
    param($Root)
    $safeRoot = Join-Path $Root.FullName 'root'
    $target = Join-Path $Root.FullName 'target'
    $link = Join-Path $safeRoot 'link'
    [System.IO.Directory]::CreateDirectory($safeRoot) | Out-Null
    [System.IO.Directory]::CreateDirectory($target) | Out-Null

    $created = $false
    try {
        New-Item -ItemType SymbolicLink -Path $link -Target $target -ErrorAction Stop | Out-Null
        $created = $true
    } catch {
        try {
            cmd /c "mklink /J `"$link`" `"$target`"" | Out-Null
            if ($LASTEXITCODE -eq 0) { $created = $true }
        } catch {
            $created = $false
        }
    }

    if ($created) {
        $unsafe = Test-MediaPipelinePathBoundarySafe -Path (Join-Path $link 'file.txt') -Root $safeRoot -AllowMissingLeaf
        Assert-Equal $unsafe.ReasonCode 'REPARSE_POINT_COMPONENT' 'Symlink or junction component should be rejected.'
    } else {
        Write-Host 'Skipping symlink/junction assertion; creation was not permitted in this environment.'
    }
}

Invoke-WithTempRoot {
    param($Root)
    $script:LocalEncoded = Join-Path $Root.FullName 'local-output'
    $missingServerRoot = Join-Path $Root.FullName 'missing-server-output'
    [System.IO.Directory]::CreateDirectory($script:LocalEncoded) | Out-Null

    $paths = [pscustomobject]@{
        LocalOut  = Join-Path $script:LocalEncoded 'Movie\Movie.mkv'
        ServerOut = Join-Path $missingServerRoot 'Movie\Movie.mkv'
        OutputRoot = $missingServerRoot
    }

    $result = Test-OutputPathCapability -Paths $paths
    Assert-True ([bool]$result.Ok) 'Missing optional server root should defer to publish/parking instead of blocking preflight.'
    Assert-True (-not (Test-Path -LiteralPath $missingServerRoot -ErrorAction SilentlyContinue)) 'Output path preflight must not create a missing optional server root.'
    Remove-Variable -Name LocalEncoded -Scope Script -ErrorAction SilentlyContinue
}

Invoke-WithTempRoot {
    param($Root)
    $script:LocalEncoded = Join-Path $Root.FullName 'local-output'
    $serverRoot = Join-Path $Root.FullName 'server-output'
    $outsideRoot = Join-Path $Root.FullName 'outside-output'
    [System.IO.Directory]::CreateDirectory($script:LocalEncoded) | Out-Null
    [System.IO.Directory]::CreateDirectory($serverRoot) | Out-Null

    $paths = [pscustomobject]@{
        LocalOut  = Join-Path $script:LocalEncoded 'Movie\Movie.mkv'
        ServerOut = Join-Path $outsideRoot 'Movie\Movie.mkv'
        OutputRoot = $serverRoot
    }

    $result = Test-OutputPathCapability -Paths $paths
    Assert-True (-not [bool]$result.Ok) 'Server output outside configured OutputRoot should fail path capability preflight.'
    Assert-Equal $result.BoundaryReasonCode 'OUTSIDE_ALLOWED_ROOT' 'Outside server output should report boundary failure evidence.'
    Remove-Variable -Name LocalEncoded -Scope Script -ErrorAction SilentlyContinue
}

Invoke-WithTempRoot {
    param($Root)
    $script:LocalEncoded = Join-Path $Root.FullName 'local-output'
    [System.IO.Directory]::CreateDirectory($script:LocalEncoded) | Out-Null
    $outsideParent = Join-Path $Root.FullName 'outside-output\Movie'
    $paths = [pscustomobject]@{
        LocalOut = Join-Path $outsideParent 'Movie.mkv'
        ServerOut = ''
        OutputRoot = ''
    }

    $result = & {
        function Get-Command {
            param([string] $Name)
            if ($Name -eq 'Test-MediaPipelinePathBoundarySafe') { return $null }
            return Microsoft.PowerShell.Core\Get-Command @PSBoundParameters
        }

        Test-OutputPathCapability -Paths $paths
    }
    Remove-Variable -Name LocalEncoded -Scope Script -ErrorAction SilentlyContinue

    Assert-True (-not [bool]$result.Ok) 'Output path capability must fail closed when boundary helper is unavailable.'
    Assert-Equal $result.BoundaryReasonCode 'BOUNDARY_HELPER_UNAVAILABLE' 'Missing boundary helper should report explicit boundary evidence.'
    Assert-True (-not (Test-Path -LiteralPath $outsideParent -ErrorAction SilentlyContinue)) 'Output path capability must not create parents before root-boundary approval.'
}

Invoke-WithTempRoot {
    param($Root)
    foreach ($badLeaf in @('Con.mkv', 'AUX.srt', 'LPT1.mp4')) {
        $reason = Test-PathComponentSupport -Path (Join-Path $Root.FullName $badLeaf)
        Assert-True ($reason -match 'reserved device name') "Expected reserved device-name rejection for $badLeaf."
    }

    foreach ($badPath in @(
        ([string]::Concat($Root.FullName, '\folder.\movie.mkv')),
        ([string]::Concat($Root.FullName, '\folder ', '\movie.mkv'))
    )) {
        $reason = Test-PathComponentSupport -Path $badPath
        Assert-True ($reason -match 'trailing dot or space') "Expected trailing dot/space rejection for $badPath."
    }

    $validUnicodeUnc = "\\server\share\Movie-$([char]0x00E9)\Episode-$([char]0x65E5).mkv"
    Assert-True ($null -eq (Test-PathComponentSupport -Path $validUnicodeUnc)) 'Unicode UNC-style path should pass lexical component support checks.'

    $script:LocalEncoded = Join-Path $Root.FullName 'local-output'
    [System.IO.Directory]::CreateDirectory($script:LocalEncoded) | Out-Null
    $paths = [pscustomobject]@{
        LocalOut = Join-Path $script:LocalEncoded 'CON.mkv'
        ServerOut = ''
        OutputRoot = ''
    }
    $result = Test-OutputPathCapability -Paths $paths
    Assert-True (-not [bool]$result.Ok) 'Output path capability should reject reserved target leaves before write probing.'
    Assert-True ([string]$result.Reason -match 'reserved device name') 'Reserved target leaf should report component support evidence.'
    Remove-Variable -Name LocalEncoded -Scope Script -ErrorAction SilentlyContinue
}

Invoke-WithTempRoot {
    param($Root)
    Remove-Variable -Name LocalBase -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name processingDir -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LocalEncoded -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LocalPendingPush -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LocalRemuxTemp -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name Outsource -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LibraryProfiles -Scope Script -ErrorAction SilentlyContinue

    $sourceDir = Join-Path $Root.FullName 'source'
    [System.IO.Directory]::CreateDirectory($sourceDir) | Out-Null
    $source = Join-Path $sourceDir 'source.mkv'
    [System.IO.File]::WriteAllText($source, 'media')
    $destination = Join-Path $Root.FullName 'untrusted-output\movie.mkv'
    $destinationParent = Split-Path -Parent $destination

    $copied = Copy-FileRobocopy -Source $source -Destination $destination -MaxRetries 1
    Assert-True (-not [bool]$copied) 'Copy-FileRobocopy should reject destinations outside configured roots.'
    Assert-Equal $script:LastCopyFileRobocopyResult.ReasonCode 'COPY_DESTINATION_ROOT_UNTRUSTED' 'Untrusted copy destination should report the root-boundary reason.'
    Assert-True (-not (Test-Path -LiteralPath $destinationParent -ErrorAction SilentlyContinue)) 'Copy-FileRobocopy must not create destination parents before root-boundary approval.'
}

Invoke-WithTempRoot {
    param($Root)
    Remove-Variable -Name LocalBase -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name processingDir -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LocalPendingPush -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LocalRemuxTemp -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name Outsource -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LibraryProfiles -Scope Script -ErrorAction SilentlyContinue

    $script:LocalEncoded = Join-Path $Root.FullName 'local-output'
    [System.IO.Directory]::CreateDirectory($script:LocalEncoded) | Out-Null
    $sourceDir = Join-Path $Root.FullName 'source'
    [System.IO.Directory]::CreateDirectory($sourceDir) | Out-Null
    $source = Join-Path $sourceDir 'source.mkv'
    [System.IO.File]::WriteAllBytes($source, (New-Object byte[] 1024))
    $destination = Join-Path $script:LocalEncoded 'Movie\Movie.mkv'
    $stagingRoot = Join-Path (Split-Path -Parent $destination) '.mediapipeline-staging'

    $script:TestDestinationFreeGB = 0.01
    $script:RobocopyInvoked = $false
    $script:StopRequested = $false
    $StopFlag = Join-Path $Root.FullName 'stop.flag'
    $RobocopyFlags = @()
    function Get-FreeSpaceGBAny { param([string] $Path) return [double]$script:TestDestinationFreeGB }
    function Invoke-NativeCommand { $script:RobocopyInvoked = $true; throw 'robocopy should not run during low-space preflight' }
    function Start-StopAwareSleep { param([int] $Seconds) return $false }

    $copied = Copy-FileRobocopy -Source $source -Destination $destination -MaxRetries 1
    Assert-True (-not [bool]$copied) 'Copy should fail closed on low destination space.'
    Assert-Equal $script:LastCopyFileRobocopyResult.ReasonCode 'OUTPUT_DESTINATION_LOW_SPACE' 'Low-space preflight should report low-space reason.'
    Assert-True (-not $script:RobocopyInvoked) 'Robocopy must not run when destination free space is too low.'
    Assert-True (-not (Test-Path -LiteralPath $stagingRoot -ErrorAction SilentlyContinue)) 'Low-space preflight should not leave an empty staging root.'

    Remove-Variable -Name LocalEncoded -Scope Script -ErrorAction SilentlyContinue
}

Invoke-WithTempRoot {
    param($Root)
    Remove-Variable -Name LocalBase -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name processingDir -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LocalPendingPush -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LocalRemuxTemp -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name Outsource -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name LibraryProfiles -Scope Script -ErrorAction SilentlyContinue

    $script:LocalEncoded = Join-Path $Root.FullName 'local-output'
    [System.IO.Directory]::CreateDirectory($script:LocalEncoded) | Out-Null
    $sourceDir = Join-Path $Root.FullName 'source'
    [System.IO.Directory]::CreateDirectory($sourceDir) | Out-Null
    $source = Join-Path $sourceDir 'source.mkv'
    [System.IO.File]::WriteAllBytes($source, (New-Object byte[] 1024))
    $destination = Join-Path $script:LocalEncoded 'Movie\Movie.mkv'
    $stagingRoot = Join-Path (Split-Path -Parent $destination) '.mediapipeline-staging'

    $script:TestDestinationFreeGB = 100
    $script:RobocopyInvoked = $false
    $script:StopRequested = $true
    $StopFlag = Join-Path $Root.FullName 'stop.flag'
    $RobocopyFlags = @()
    function Get-FreeSpaceGBAny { param([string] $Path) return [double]$script:TestDestinationFreeGB }
    function Invoke-NativeCommand { $script:RobocopyInvoked = $true; throw 'robocopy should not run after stop was requested' }
    function Start-StopAwareSleep { param([int] $Seconds) return $false }

    $copied = Copy-FileRobocopy -Source $source -Destination $destination -MaxRetries 1
    Assert-True (-not [bool]$copied) 'Copy should stop before the first attempt when stop was requested.'
    Assert-Equal $script:LastCopyFileRobocopyResult.ReasonCode 'COPY_STOP_REQUESTED' 'Stop-before-attempt should report stop-requested reason.'
    Assert-True (-not $script:RobocopyInvoked) 'Robocopy must not run after stop was requested.'
    Assert-True (-not (Test-Path -LiteralPath $stagingRoot -ErrorAction SilentlyContinue)) 'Stop-before-attempt should not leave an empty staging root.'

    $script:StopRequested = $false
    Remove-Variable -Name LocalEncoded -Scope Script -ErrorAction SilentlyContinue
}

Invoke-WithTempRoot {
    param($Root)
    $script:ReportRootResolved = Join-Path $Root.FullName 'report'
    $script:ProbeCacheRoot = Join-Path $script:ReportRootResolved 'ProbeCache'
    [System.IO.Directory]::CreateDirectory($script:ProbeCacheRoot) | Out-Null
    $safeEntry = Join-Path $script:ProbeCacheRoot 'entry.json'
    [System.IO.File]::WriteAllText($safeEntry, '{}')

    Clear-ProbeCache
    Assert-True (-not (Test-Path -LiteralPath $safeEntry -ErrorAction SilentlyContinue)) 'Clear-ProbeCache should remove children inside the configured ProbeCache root.'
    Assert-True (Test-Path -LiteralPath $script:ProbeCacheRoot -PathType Container) 'Clear-ProbeCache should leave the ProbeCache root in place.'

    $outsideRoot = Join-Path $Root.FullName 'outside'
    $script:ProbeCacheRoot = Join-Path $outsideRoot 'ProbeCache'
    [System.IO.Directory]::CreateDirectory($script:ProbeCacheRoot) | Out-Null
    $outsideEntry = Join-Path $script:ProbeCacheRoot 'entry.json'
    [System.IO.File]::WriteAllText($outsideEntry, '{}')

    Clear-ProbeCache
    Assert-True (Test-Path -LiteralPath $outsideEntry -PathType Leaf) 'Clear-ProbeCache must not remove cache children outside the configured report root.'
    Remove-Variable -Name ReportRootResolved -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name ProbeCacheRoot -Scope Script -ErrorAction SilentlyContinue
}

Invoke-WithTempRoot {
    param($Root)
    $script:LocalBase = Join-Path $Root.FullName 'local-base'
    $script:processingDir = Join-Path (Join-Path $script:LocalBase 'Incoming') 'Processing'
    [System.IO.Directory]::CreateDirectory($script:processingDir) | Out-Null
    $safeFile = Join-Path $script:processingDir 'sub_old.srt'
    [System.IO.File]::WriteAllText($safeFile, 'old')
    Set-OldTestItem -Path $safeFile
    $safeSrcDir = Join-Path $script:processingDir 'src_old'
    [System.IO.Directory]::CreateDirectory($safeSrcDir) | Out-Null
    Set-OldTestItem -Path $safeSrcDir

    Clear-OldTempFiles
    Assert-True (-not (Test-Path -LiteralPath $safeFile -ErrorAction SilentlyContinue)) 'Clear-OldTempFiles should remove stale temp files inside LocalBase processing.'
    Assert-True (-not (Test-Path -LiteralPath $safeSrcDir -ErrorAction SilentlyContinue)) 'Clear-OldTempFiles should remove stale src_* directories inside LocalBase processing.'

    $outsideProcessing = Join-Path $Root.FullName 'outside-processing'
    $script:processingDir = $outsideProcessing
    [System.IO.Directory]::CreateDirectory($outsideProcessing) | Out-Null
    $outsideSrcDir = Join-Path $outsideProcessing 'src_old'
    [System.IO.Directory]::CreateDirectory($outsideSrcDir) | Out-Null
    Set-OldTestItem -Path $outsideSrcDir

    Clear-OldTempFiles
    Assert-True (Test-Path -LiteralPath $outsideSrcDir -PathType Container) 'Clear-OldTempFiles must not remove src_* directories outside LocalBase.'
    Remove-Variable -Name LocalBase -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name processingDir -Scope Script -ErrorAction SilentlyContinue
}

Invoke-WithTempRoot {
    param($Root)
    $script:LocalBase = Join-Path $Root.FullName 'local-base'
    $script:processingDir = Join-Path (Join-Path $script:LocalBase 'Incoming') 'Processing'
    [System.IO.Directory]::CreateDirectory($script:processingDir) | Out-Null
    $safeContainer = Join-Path $script:processingDir 'src_safe'
    [System.IO.Directory]::CreateDirectory($safeContainer) | Out-Null

    Remove-EmptyScratchContainer -ScratchPath (Join-Path $safeContainer 'movie.mkv')
    Assert-True (-not (Test-Path -LiteralPath $safeContainer -ErrorAction SilentlyContinue)) 'Remove-EmptyScratchContainer should remove empty src_* containers inside processingDir.'

    $outsideContainer = Join-Path (Join-Path $Root.FullName 'outside-processing') 'src_outside'
    [System.IO.Directory]::CreateDirectory($outsideContainer) | Out-Null
    Remove-EmptyScratchContainer -ScratchPath (Join-Path $outsideContainer 'movie.mkv')
    Assert-True (Test-Path -LiteralPath $outsideContainer -PathType Container) 'Remove-EmptyScratchContainer must not remove src_* containers outside processingDir.'
    Remove-Variable -Name LocalBase -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name processingDir -Scope Script -ErrorAction SilentlyContinue
}

function Get-SourceIdentityKey {
    param($SourceFile)
    return 'scratchsafetyfixture'
}

function Copy-FileRobocopy {
    param([string] $Source, [string] $Destination)
    $parent = Split-Path $Destination -Parent
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    return $true
}

function Test-FileIntegrityDetailed {
    param([string] $FilePath)
    return [pscustomobject]@{ Ok = $true; ErrorCode = 'OK'; Reason = 'test integrity stub' }
}

function Set-ProgressStage {
    param(
        [string] $Stage,
        [string] $CopyState,
        $Percent,
        [switch] $SaveNow
    )
}

Invoke-WithTempRoot {
    param($Root)
    $script:LocalBase = Join-Path $Root.FullName 'local-base'
    $script:processingDir = Join-Path (Join-Path $script:LocalBase 'Incoming') 'Processing'
    [System.IO.Directory]::CreateDirectory($script:processingDir) | Out-Null
    $sourceDir = Join-Path $Root.FullName 'source'
    [System.IO.Directory]::CreateDirectory($sourceDir) | Out-Null
    $sourcePath = Join-Path $sourceDir 'source.mkv'
    [System.IO.File]::WriteAllText($sourcePath, 'media', [System.Text.UTF8Encoding]::new($false))
    $source = Get-Item -LiteralPath $sourcePath

    $victimDir = Join-Path $Root.FullName 'victim'
    [System.IO.Directory]::CreateDirectory($victimDir) | Out-Null
    $victimPath = Join-Path $victimDir 'victim.mkv'
    [System.IO.File]::WriteAllText($victimPath, 'do-not-touch', [System.Text.UTF8Encoding]::new($false))

    $traversalResult = Ensure-ScratchCopy -SourceFile $source -SafeName '..\victim.mkv'
    Assert-True ($null -eq $traversalResult) 'Ensure-ScratchCopy should reject parent traversal safe names.'
    Assert-Equal ([System.IO.File]::ReadAllText($victimPath)) 'do-not-touch' 'Traversal safe name must not mutate outside victim file.'

    $rootedResult = Ensure-ScratchCopy -SourceFile $source -SafeName (Join-Path $victimDir 'rooted.mkv')
    Assert-True ($null -eq $rootedResult) 'Ensure-ScratchCopy should reject rooted safe names.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $victimDir 'rooted.mkv') -ErrorAction SilentlyContinue)) 'Rooted safe name must not create outside files.'

    $unicodeSafeName = "Movie-$([char]0x00E9)-$([char]0x65E5).mkv"
    $unicodeResult = Ensure-ScratchCopy -SourceFile $source -SafeName $unicodeSafeName
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$unicodeResult)) 'Ensure-ScratchCopy should accept Unicode leaf safe names.'
    Assert-Equal (Split-Path $unicodeResult -Leaf) $unicodeSafeName 'Unicode scratch leaf should be preserved.'
    Assert-True (Test-Path -LiteralPath $unicodeResult -PathType Leaf) 'Unicode scratch copy should be written under the scratch container.'
    Assert-True (Test-MediaPipelinePathIsEqualOrChild -Path $unicodeResult -Root $script:processingDir) 'Unicode scratch copy must remain under processingDir.'

    Remove-Variable -Name LocalBase -Scope Script -ErrorAction SilentlyContinue
    Remove-Variable -Name processingDir -Scope Script -ErrorAction SilentlyContinue
}

Write-Host 'Path boundary guard checks passed.'
