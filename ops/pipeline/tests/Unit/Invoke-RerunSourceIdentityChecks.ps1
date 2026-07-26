[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Rerun source identity checks require PowerShell 7. Install pwsh or use the bundled runtime."
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
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

. (Join-Path $repoRoot 'ops\pipeline\engine\audit\rerun_source_identity.ps1')
$metadataScript = Join-Path $repoRoot 'ops\pipeline\entrypoints\Get-RerunSourceMetadata.ps1'

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

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-rerun-identity-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
try {
    $source = Join-Path $tempRoot 'Sample.mkv'
    [System.IO.File]::WriteAllBytes($source, [System.Text.Encoding]::UTF8.GetBytes('same-size-a'))
    $firstInfo = Get-Item -LiteralPath $source
    $firstIdentity = Get-RerunSourceIdentityV2 -FileInfo $firstInfo -FfprobePath ''
    $repeatIdentity = Get-RerunSourceIdentityV2 -FileInfo $firstInfo -FfprobePath ''

    Assert-True ($firstIdentity -match '^[0-9a-f]{64}$') 'Missing-ffprobe fallback should still emit a SHA-256 identity.'
    Assert-Equal $repeatIdentity $firstIdentity 'Missing-ffprobe fallback identity should be deterministic.'

    [System.IO.File]::WriteAllBytes($source, [System.Text.Encoding]::UTF8.GetBytes('same-size-b'))
    $changedInfo = Get-Item -LiteralPath $source
    $changedIdentity = Get-RerunSourceIdentityV2 -FileInfo $changedInfo -FfprobePath ''

    Assert-True ($changedIdentity -match '^[0-9a-f]{64}$') 'Changed-source fallback should still emit a SHA-256 identity.'
    Assert-True ($changedIdentity -ne $firstIdentity) 'Missing-ffprobe fallback identity should change when source sample bytes change.'

    $metadataRequestPath = Join-Path $tempRoot 'metadata-request.json'
    $metadataOutputPath = Join-Path $tempRoot 'metadata-output.json'
    [System.IO.File]::WriteAllText(
        $metadataRequestPath,
        ([ordered]@{ schema_version = 'rerun_source_metadata_request.v1'; source_paths = @($source) } | ConvertTo-Json -Depth 4),
        [System.Text.UTF8Encoding]::new($false)
    )
    & $metadataScript -InputJsonPath $metadataRequestPath -OutputJsonPath $metadataOutputPath
    $metadataPayload = Get-Content -LiteralPath $metadataOutputPath -Raw | ConvertFrom-Json
    $expectedContentSha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert-Equal $metadataPayload.rows[0].source_content_sha256 $expectedContentSha256 'Rerun source metadata omitted the full-file SHA-256 contract.'
    Assert-Equal $metadataPayload.rows[0].source_content_sha256_algorithm 'sha256-full-file' 'Rerun source metadata emitted an unsupported content-hash algorithm token.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'Rerun source identity checks passed.'
