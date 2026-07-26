[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$InputJsonPath,
    [Parameter(Mandatory)] [string]$OutputJsonPath
)

$ErrorActionPreference = 'Stop'

function Write-RerunLog {
    param([string]$Message, [string]$Level = 'INFO')
    Write-Verbose "[$Level] $Message"
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] $Payload
    )
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = Join-Path $dir ('.' + (Split-Path -Leaf $Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $tmp -Encoding UTF8
    [System.IO.File]::Move($tmp, $Path, $true)
}

function Resolve-RerunMetadataFfprobePath {
    param($Payload)
    $requested = [string]($Payload.ffprobe_path)
    if ($requested -and (Test-Path -LiteralPath $requested)) { return $requested }

    $pipelineRoot = Split-Path -Parent $PSScriptRoot
    foreach ($candidate in @(
        (Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffprobe.exe'),
        (Join-Path $pipelineRoot 'tools\ffmpeg\bin\ffprobe'),
        (Join-Path $PSScriptRoot 'Tools\ffmpeg\bin\ffprobe.exe'),
        (Join-Path $PSScriptRoot 'Tools\ffmpeg\bin\ffprobe')
    )) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return ''
}

$pipelineRoot = Split-Path -Parent $PSScriptRoot
$identityModule = Join-Path $pipelineRoot 'engine\audit\rerun_source_identity.ps1'
if (-not (Test-Path -LiteralPath $identityModule)) { throw "Rerun source identity module not found: $identityModule" }
. $identityModule

$payload = Get-Content -LiteralPath $InputJsonPath -Raw | ConvertFrom-Json -ErrorAction Stop
$ffprobePath = Resolve-RerunMetadataFfprobePath -Payload $payload
$rows = [System.Collections.Generic.List[object]]::new()

foreach ($sourcePath in @($payload.source_paths)) {
    $pathText = [string]$sourcePath
    $row = [ordered]@{
        source_path        = $pathText
        exists             = $false
        source_size        = ''
        source_mtime_utc   = ''
        source_identity_v2 = ''
        source_content_sha256 = ''
        source_content_sha256_algorithm = ''
        error              = ''
    }
    try {
        $fileInfo = Get-Item -LiteralPath $pathText -ErrorAction Stop
        if (-not ($fileInfo -is [System.IO.FileInfo])) { throw "source path is not a file: $pathText" }
        $row.exists = $true
        $row.source_size = [string]([long]$fileInfo.Length)
        $row.source_mtime_utc = $fileInfo.LastWriteTimeUtc.ToString('o')
        $row.source_identity_v2 = Get-RerunSourceIdentityV2 -FileInfo $fileInfo -FfprobePath $ffprobePath
        $row.source_content_sha256 = Get-RerunContentSha256 -Path $fileInfo.FullName
        if ([string]::IsNullOrWhiteSpace([string]$row.source_content_sha256)) {
            throw "full-file SHA-256 could not be computed: $pathText"
        }
        $afterInfo = Get-Item -LiteralPath $pathText -ErrorAction Stop
        if ([long]$afterInfo.Length -ne [long]$fileInfo.Length -or $afterInfo.LastWriteTimeUtc.Ticks -ne $fileInfo.LastWriteTimeUtc.Ticks) {
            throw "source changed while rerun metadata was captured: $pathText"
        }
        $row.source_content_sha256_algorithm = 'sha256-full-file'
    } catch {
        $row.error = [string]$_.Exception.Message
    }
    $rows.Add([pscustomobject]$row)
}

Write-JsonAtomic -Path $OutputJsonPath -Payload ([ordered]@{
    schema_version = 'rerun_source_metadata.v1'
    ffprobe_path   = $ffprobePath
    rows           = @($rows)
})
