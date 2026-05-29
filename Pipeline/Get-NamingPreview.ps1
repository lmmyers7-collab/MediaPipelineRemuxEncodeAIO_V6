[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$InputJsonPath,
    [Parameter(Mandatory)] [string]$OutputJsonPath
)

$ErrorActionPreference = 'Stop'

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] $Payload
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $Payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding UTF8 -Force
        if (Test-Path -LiteralPath $Path) {
            [System.IO.File]::Replace($tmp, $Path, $null)
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
    } finally {
        if (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }
}

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    Write-Verbose "[$Level] $Message"
}

$script:PriorityMarkers = @('!')
$script:AggressiveEpisodeParsing = $true
$script:ValidExtensions = @('.mkv','.mp4','.m4v','.avi','.mov','.ts','.m2ts','.webm')
$CreateTVSubfolder = $true

$queuePlanModule = Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\queue\queue_plan.ps1'
$namingModule = Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\naming\naming.ps1'
if (-not (Test-Path -LiteralPath $queuePlanModule)) { throw "QueuePlan module not found: $queuePlanModule" }
if (-not (Test-Path -LiteralPath $namingModule)) { throw "Naming module not found: $namingModule" }
. $queuePlanModule
. $namingModule

$payload = Get-Content -LiteralPath $InputJsonPath -Raw | ConvertFrom-Json -ErrorAction Stop
$rows = [System.Collections.Generic.List[object]]::new()

foreach ($item in @($payload.items)) {
    $sourcePath = [string]$item.path
    $originalName = [string]$item.original_name
    if ([string]::IsNullOrWhiteSpace($originalName) -and -not [string]::IsNullOrWhiteSpace($sourcePath)) {
        $originalName = Split-Path -Leaf $sourcePath
    }
    $extension = [string]$item.extension
    if ([string]::IsNullOrWhiteSpace($extension) -and -not [string]::IsNullOrWhiteSpace($originalName)) {
        $extension = [System.IO.Path]::GetExtension($originalName)
    }
    $mediaKind = ([string]$item.media_kind).Trim()
    if ([string]::IsNullOrWhiteSpace($mediaKind)) { $mediaKind = 'Movie' }

    try {
        if ($mediaKind -eq 'Movie') {
            $plan = New-PlexMovieDestinationPlan -OriginalName $originalName -Extension $extension
        } elseif ($mediaKind -eq 'TV') {
            $file = $null
            if (-not [string]::IsNullOrWhiteSpace($sourcePath) -and (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                $file = Get-Item -LiteralPath $sourcePath -ErrorAction Stop
            } else {
                $directoryName = if (-not [string]::IsNullOrWhiteSpace($sourcePath)) {
                    [System.IO.Path]::GetDirectoryName($sourcePath)
                } else {
                    [System.IO.Path]::GetTempPath()
                }
                if ([string]::IsNullOrWhiteSpace($directoryName)) { $directoryName = [System.IO.Path]::GetTempPath() }
                $file = [pscustomobject]@{
                    Name          = $originalName
                    FullName      = if ($sourcePath) { $sourcePath } else { Join-Path $directoryName $originalName }
                    DirectoryName = $directoryName
                    Extension     = $extension
                }
            }
            $tvInfo = Get-TVInfoFromFile $file
            if (-not $tvInfo.IsReliable) {
                throw $tvInfo.ParseError
            }
            $plan = New-PlexDestinationPlan -MediaKind TV -File $file -TvInfo $tvInfo -OriginalName $originalName -Extension $extension
        } else {
            throw "Unsupported naming preview media kind: $mediaKind"
        }
        $rows.Add([pscustomobject]@{
            ok = $true
            source_path = $sourcePath
            original_name = $originalName
            media_kind = $mediaKind
            file_base_name = [string]$plan.FileBaseName
            file_name = [string]$plan.FileName
            relative_directory = [string]$plan.RelativeDirectory
            relative_path = [string]$plan.RelativePath
            identity_key = [string]$plan.IdentityKey
            error = ''
        })
    } catch {
        $rows.Add([pscustomobject]@{
            ok = $false
            source_path = $sourcePath
            original_name = $originalName
            media_kind = $mediaKind
            file_base_name = ''
            file_name = ''
            relative_directory = ''
            relative_path = ''
            identity_key = ''
            error = [string]$_.Exception.Message
        })
    }
}

Write-JsonAtomic -Path $OutputJsonPath -Payload ([ordered]@{
    schema_version = 'naming_preview.v1'
    rows = @($rows)
})
