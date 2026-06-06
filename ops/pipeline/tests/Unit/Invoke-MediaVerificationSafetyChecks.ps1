[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))

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

$script:MediaVerificationLogs = @()
function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:MediaVerificationLogs = @($script:MediaVerificationLogs) + @([pscustomobject]@{
        Message = $Message
        Level   = $Level
    })
}

. (Join-Path $repoRoot 'ops\pipeline\engine\probe\media_probe.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_result.ps1')

function Get-MediaDuration {
    param([string] $FilePath)
    if ($FilePath -eq 'source.mkv') { return 0.0 }
    if ($FilePath -eq 'output.mkv') { return 120.0 }
    return 0.0
}

$failedClosed = Test-DurationMatch -SourcePath 'source.mkv' -OutputPath 'output.mkv' -Label 'VERIFY'
Assert-True (-not [bool]$failedClosed) 'Source duration probe failure must fail verification closed.'
Assert-True (@($script:MediaVerificationLogs | Where-Object { $_.Level -eq 'ERROR' -and $_.Message -match 'source duration probe failed' }).Count -gt 0) 'Source probe failure should log as a verification error.'

function Get-MediaDuration {
    param([string] $FilePath)
    if ($FilePath -eq 'source.mkv') { return 120.0 }
    if ($FilePath -eq 'output.mkv') { return 120.25 }
    return 0.0
}

$matched = Test-DurationMatch -SourcePath 'source.mkv' -OutputPath 'output.mkv' -ToleranceSeconds 1.0 -Label 'VERIFY'
Assert-True ([bool]$matched) 'Valid duration match should still pass.'

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ('mp-existing-output-' + [guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($tempDir) | Out-Null
try {
    $outputPath = Join-Path $tempDir 'Existing.mkv'
    [System.IO.File]::WriteAllBytes($outputPath, [byte[]](1, 2, 3, 4))
    $sourceFile = [pscustomobject]@{
        FullName = 'C:\Source\ExistingSource.mkv'
        Length   = 987654321L
    }

    $publishResult = New-ExistingOutputPublishResult -SourceFile $sourceFile -OutputPath $outputPath
    Assert-True ([bool]$publishResult.Ok) 'Existing-output publish result should be successful.'
    Assert-Equal $publishResult.PublishState 'published' 'Existing-output publish state mismatch.'
    Assert-Equal $publishResult.PublishMode 'existing-output' 'Existing-output publish mode mismatch.'
    Assert-Equal $publishResult.OutputPath $outputPath 'Existing-output path mismatch.'
    Assert-Equal $publishResult.OutputSizeBytes 4 'Existing-output size mismatch.'
    Assert-Equal $publishResult.SourcePath 'C:\Source\ExistingSource.mkv' 'Existing-output source path mismatch.'
    Assert-Equal $publishResult.SourceSizeBytes 987654321 'Existing-output source size mismatch.'
} finally {
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

$remuxText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\remux.ps1') -Raw
$encodeText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1') -Raw
Assert-True ($remuxText -match '\$script:LastPublishResult\s*=\s*New-ExistingOutputPublishResult') 'Remux existing-output branch must set LastPublishResult.'
Assert-True ($encodeText -match '\$script:LastPublishResult\s*=\s*New-ExistingOutputPublishResult') 'Encode existing-output branch must set LastPublishResult.'

Write-Host 'Media verification safety checks passed.'
