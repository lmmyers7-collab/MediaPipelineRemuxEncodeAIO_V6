[CmdletBinding()]
param(
    [string] $RepoRoot,
    [switch] $InstallMissing,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    param([string] $Candidate)

    if ($Candidate) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    $scriptPath = $PSCommandPath
    if (-not $scriptPath) {
        throw 'Unable to resolve script path for repository root discovery.'
    }

    return (Resolve-Path -LiteralPath (Join-Path (Split-Path -Parent $scriptPath) '..\..\..')).Path
}

function Resolve-CommandSource {
    param([string] $Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    return $null
}

function Invoke-CheckedCommand {
    param(
        [string] $FilePath,
        [string[]] $Arguments,
        [string] $FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Copy-DirectoryContents {
    param(
        [string] $SourceDir,
        [string] $TargetDir,
        [string[]] $TargetExeNames
    )

    $targetExecutables = @($TargetExeNames | ForEach-Object { Join-Path $TargetDir $_ })
    $allTargetsPresent = $true
    foreach ($targetExe in $targetExecutables) {
        if (-not (Test-Path -LiteralPath $targetExe)) {
            $allTargetsPresent = $false
            break
        }
    }

    if ($allTargetsPresent -and -not $Force) {
        Write-Host "CI media tool already present: $($targetExecutables -join ', ')"
        return
    }

    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

    $sourceResolved = (Resolve-Path -LiteralPath $SourceDir).Path
    $targetResolved = (Resolve-Path -LiteralPath $TargetDir).Path
    if ($sourceResolved -ieq $targetResolved) {
        Write-Host "CI media tool source already matches target: $TargetDir"
        return
    }

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $TargetDir $item.Name) -Recurse -Force
    }

    foreach ($targetExe in $targetExecutables) {
        if (-not (Test-Path -LiteralPath $targetExe)) {
            throw "CI media tool copy did not produce $targetExe"
        }
    }
}

function Find-ExecutableInRoots {
    param(
        [string] $ExeName,
        [string[]] $Roots
    )

    foreach ($root in $Roots) {
        if (-not $root) {
            continue
        }
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        $match = Get-ChildItem -LiteralPath $root -Recurse -Filter $ExeName -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($match) {
            return $match.FullName
        }
    }

    return $null
}

function Install-MissingPackages {
    param([string[]] $MissingCommands)

    if ($MissingCommands.Count -eq 0) {
        return
    }

    if (-not $InstallMissing) {
        throw "Missing CI media tool command(s): $($MissingCommands -join ', '). Re-run with -InstallMissing on CI."
    }

    $choco = Resolve-CommandSource -Name 'choco'
    if (-not $choco) {
        throw "Missing CI media tool command(s): $($MissingCommands -join ', '), and Chocolatey was not found."
    }

    Write-Host "Installing missing CI media packages with Chocolatey: $($MissingCommands -join ', ')"
    Invoke-CheckedCommand `
        -FilePath $choco `
        -Arguments @('install', 'ffmpeg', 'mkvtoolnix', '-y', '--no-progress') `
        -FailureMessage 'Chocolatey media tool install failed.'
}

function Get-ToolRoots {
    $roots = @()

    if ($env:ChocolateyInstall) {
        $roots += (Join-Path $env:ChocolateyInstall 'lib')
    }
    if ($env:ProgramData) {
        $roots += (Join-Path $env:ProgramData 'chocolatey\lib')
    }
    if ($env:ProgramFiles) {
        $roots += (Join-Path $env:ProgramFiles 'MKVToolNix')
        $roots += (Join-Path $env:ProgramFiles 'PowerShell')
    }
    if (${env:ProgramFiles(x86)}) {
        $roots += (Join-Path ${env:ProgramFiles(x86)} 'MKVToolNix')
        $roots += (Join-Path ${env:ProgramFiles(x86)} 'PowerShell')
    }

    return $roots
}

function Resolve-Executable {
    param([string] $Name)

    $exeName = if ($Name.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) { $Name } else { "$Name.exe" }
    $searchRoots = Get-ToolRoots
    $found = Find-ExecutableInRoots -ExeName $exeName -Roots $searchRoots
    if ($found) {
        return $found
    }

    return Resolve-CommandSource -Name $Name
}

$repoRootPath = Resolve-RepoRoot -Candidate $RepoRoot
$pwshTargetDir = Join-Path $repoRootPath 'ops\pipeline\runtime\PowerShell-7.6.0-win-x64'
$ffmpegTargetDir = Join-Path $repoRootPath 'ops\pipeline\tools\ffmpeg\bin'
$mkvTargetDir = Join-Path $repoRootPath 'ops\pipeline\tools\MKVToolNix'
$targetByCommand = @{
    pwsh = Join-Path $pwshTargetDir 'pwsh.exe'
    ffmpeg = Join-Path $ffmpegTargetDir 'ffmpeg.exe'
    ffprobe = Join-Path $ffmpegTargetDir 'ffprobe.exe'
    mkvmerge = Join-Path $mkvTargetDir 'mkvmerge.exe'
}
$pgsTargetDir = Join-Path $repoRootPath 'ops\pipeline\tools\PgsToSrt'
$pgsTargetExe = Join-Path $pgsTargetDir 'PgsToSrt.exe'
$pgsEnglishData = Join-Path $pgsTargetDir 'tessdata\eng.traineddata'
$pgsArchiveUrl = 'https://github.com/Tentacule/PgsToSrt/releases/download/v1.4.8/PgsToStr-1.4.8.zip'
$pgsArchiveSha256 = '27c3e637fe777cabe55b063a5a454e124c395e727d6a270899be3b5a7b2a9c7a'
$pgsEnglishDataUrl = 'https://raw.githubusercontent.com/tesseract-ocr/tessdata/ced78752cc61322fb554c280d13360b35b8684e4/eng.traineddata'
$pgsEnglishDataSha256 = 'daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047'

function Assert-FileSha256 {
    param(
        [string] $Path,
        [string] $ExpectedSha256,
        [string] $Label
    )

    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectedSha256) {
        throw "$Label SHA-256 mismatch. Expected $ExpectedSha256 but found $actual."
    }
}

function Invoke-VerifiedDownload {
    param(
        [string] $Uri,
        [string] $OutFile,
        [string] $ExpectedSha256,
        [string] $Label,
        [int] $MaximumAttempts = 3
    )

    for ($attempt = 1; $attempt -le $MaximumAttempts; $attempt++) {
        try {
            Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
            Invoke-WebRequest -Uri $Uri -OutFile $OutFile
            Assert-FileSha256 -Path $OutFile -ExpectedSha256 $ExpectedSha256 -Label $Label
            return
        }
        catch {
            Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
            if ($attempt -ge $MaximumAttempts) {
                throw
            }
            $delaySeconds = 2 * $attempt
            Write-Warning "$Label download attempt $attempt failed; retrying in $delaySeconds seconds. $($_.Exception.Message)"
            Start-Sleep -Seconds $delaySeconds
        }
    }
}

function Install-PgsToSrtRuntime {
    if ((Test-Path -LiteralPath $pgsTargetExe -PathType Leaf) -and
        (Test-Path -LiteralPath $pgsEnglishData -PathType Leaf) -and
        -not $Force) {
        Write-Host "CI PgsToSrt runtime already present: $pgsTargetExe"
        return
    }

    if (-not $InstallMissing) {
        throw 'PgsToSrt or English tessdata is missing. Re-run with -InstallMissing on CI.'
    }

    $tempParent = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
    $tempRoot = Join-Path $tempParent ("mediapipeline-pgstosrt-" + [guid]::NewGuid().ToString('N'))
    $archivePath = Join-Path $tempRoot 'PgsToStr-1.4.8.zip'
    $expandedPath = Join-Path $tempRoot 'expanded'
    $downloadedEnglishData = Join-Path $tempRoot 'eng.traineddata'

    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        Invoke-VerifiedDownload -Uri $pgsArchiveUrl -OutFile $archivePath -ExpectedSha256 $pgsArchiveSha256 -Label 'PgsToSrt archive'
        Expand-Archive -LiteralPath $archivePath -DestinationPath $expandedPath -Force

        Invoke-VerifiedDownload -Uri $pgsEnglishDataUrl -OutFile $downloadedEnglishData -ExpectedSha256 $pgsEnglishDataSha256 -Label 'PgsToSrt English tessdata'

        New-Item -ItemType Directory -Path $pgsTargetDir -Force | Out-Null
        foreach ($item in Get-ChildItem -LiteralPath $expandedPath -Force) {
            Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $pgsTargetDir $item.Name) -Recurse -Force
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $pgsEnglishData) -Force | Out-Null
        Copy-Item -LiteralPath $downloadedEnglishData -Destination $pgsEnglishData -Force
    }
    finally {
        if (Test-Path -LiteralPath $tempRoot) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }

    if (-not (Test-Path -LiteralPath $pgsTargetExe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $pgsEnglishData -PathType Leaf)) {
        throw 'CI PgsToSrt provisioning did not produce the required executable and English tessdata.'
    }
}

function Resolve-ProvisionSource {
    param([string] $Name)

    $target = $targetByCommand[$Name]
    if ($target -and (Test-Path -LiteralPath $target) -and -not $Force) {
        return $target
    }

    return Resolve-Executable -Name $Name
}

$missingCommands = @()
foreach ($commandName in @('pwsh', 'ffmpeg', 'ffprobe', 'mkvmerge')) {
    if (-not (Resolve-ProvisionSource -Name $commandName)) {
        $missingCommands += $commandName
    }
}

Install-MissingPackages -MissingCommands ($missingCommands | Where-Object { $_ -ne 'pwsh' })

$pwshSource = Resolve-ProvisionSource -Name 'pwsh'
if (-not $pwshSource) {
    throw 'PowerShell 7 pwsh.exe was not found for CI runtime provisioning.'
}

$ffmpegSource = Resolve-ProvisionSource -Name 'ffmpeg'
$ffprobeSource = Resolve-ProvisionSource -Name 'ffprobe'
$mkvmergeSource = Resolve-ProvisionSource -Name 'mkvmerge'

if (-not $ffmpegSource -or -not $ffprobeSource -or -not $mkvmergeSource) {
    throw 'CI media tool installation completed but one or more required tools could not be resolved.'
}

Copy-DirectoryContents -SourceDir (Split-Path -Parent $pwshSource) -TargetDir $pwshTargetDir -TargetExeNames @('pwsh.exe')
Copy-DirectoryContents -SourceDir (Split-Path -Parent $ffmpegSource) -TargetDir $ffmpegTargetDir -TargetExeNames @('ffmpeg.exe', 'ffprobe.exe')
Copy-DirectoryContents -SourceDir (Split-Path -Parent $mkvmergeSource) -TargetDir $mkvTargetDir -TargetExeNames @('mkvmerge.exe')
Install-PgsToSrtRuntime

$pwshTarget = Join-Path $pwshTargetDir 'pwsh.exe'
$ffmpegTarget = Join-Path $ffmpegTargetDir 'ffmpeg.exe'
$ffprobeTarget = Join-Path $ffmpegTargetDir 'ffprobe.exe'
$mkvmergeTarget = Join-Path $mkvTargetDir 'mkvmerge.exe'

Invoke-CheckedCommand `
    -FilePath $pwshTarget `
    -Arguments @('-NoLogo', '-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()') `
    -FailureMessage "CI PowerShell runtime validation failed: $pwshTarget"
Invoke-CheckedCommand `
    -FilePath $ffmpegTarget `
    -Arguments @('-version') `
    -FailureMessage "CI ffmpeg validation failed: $ffmpegTarget"
Invoke-CheckedCommand `
    -FilePath $ffprobeTarget `
    -Arguments @('-version') `
    -FailureMessage "CI ffprobe validation failed: $ffprobeTarget"
Invoke-CheckedCommand `
    -FilePath $mkvmergeTarget `
    -Arguments @('--version') `
    -FailureMessage "CI mkvmerge validation failed: $mkvmergeTarget"
