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

function New-StubProbeResult {
    param(
        [string] $Output = '',
        [int] $ExitCode = 0,
        [string] $ErrorText = '',
        [bool] $TimedOut = $false,
        [bool] $Stopped = $false
    )

    return [pscustomobject]@{
        Output   = $Output
        Error    = $ErrorText
        ExitCode = $ExitCode
        TimedOut = $TimedOut
        Stopped  = $Stopped
    }
}

$script:DynamicHdrProbeQueue = @()
$script:DynamicHdrProbeStages = @()

function Set-StubProbeResults {
    param([array] $Results)
    $script:DynamicHdrProbeQueue = @($Results)
    $script:DynamicHdrProbeStages = @()
}

function Invoke-FFprobeCommand {
    param(
        [array] $ArgumentList,
        [int] $TimeoutSeconds = 30,
        [string] $Stage = ''
    )

    $script:DynamicHdrProbeStages = @($script:DynamicHdrProbeStages) + @([pscustomobject]@{
        Stage          = $Stage
        TimeoutSeconds = $TimeoutSeconds
        Arguments      = @($ArgumentList)
    })
    if ($script:DynamicHdrProbeQueue.Count -eq 0) {
        throw "No stub ffprobe result queued for stage '$Stage'."
    }
    $result = $script:DynamicHdrProbeQueue[0]
    $script:DynamicHdrProbeQueue = @($script:DynamicHdrProbeQueue | Select-Object -Skip 1)
    return $result
}

. (Join-Path $repoRoot 'ops\pipeline\engine\probe\media_probe.ps1')

$doviP7Json = @'
{
  "streams": [
    {
      "codec_name": "hevc",
      "side_data_list": [
        {
          "side_data_type": "DOVI configuration record",
          "dv_profile": 7,
          "dv_level": 6,
          "rpu_present_flag": 1,
          "el_present_flag": 1,
          "bl_present_flag": 1,
          "dv_bl_signal_compatibility_id": 0
        }
      ]
    }
  ]
}
'@
Set-StubProbeResults @((New-StubProbeResult -Output $doviP7Json))
$doviP7 = Get-DolbyVisionState -FilePath 'dovi-p7.mkv'
Assert-True ([bool]$doviP7.Known) 'DoVi P7 probe should be known.'
Assert-True ([bool]$doviP7.DoviPresent) 'DoVi P7 should be detected.'
Assert-Equal $doviP7.DoviProfile 7 'DoVi P7 profile mismatch.'
Assert-True ([bool]$doviP7.DoviElPresent) 'DoVi P7 EL flag should be true.'
Assert-True ([bool]$doviP7.DoviRpuPresent) 'DoVi P7 RPU flag should be true.'
Assert-Equal $script:DynamicHdrProbeStages[0].Stage 'dovi-detection' 'DoVi probe stage mismatch.'
Assert-Equal $script:DynamicHdrProbeStages[0].TimeoutSeconds 30 'DoVi probe timeout mismatch.'

$doviP8Json = @'
{
  "streams": [
    {
      "codec_name": "hevc",
      "side_data_list": [
        {
          "side_data_type": "DOVI configuration record",
          "dv_profile": 8,
          "dv_level": 6,
          "rpu_present_flag": 1,
          "el_present_flag": 0,
          "bl_present_flag": 1,
          "dv_bl_signal_compatibility_id": 1
        }
      ]
    }
  ]
}
'@
Set-StubProbeResults @((New-StubProbeResult -Output $doviP8Json))
$doviP8 = Get-DolbyVisionState -FilePath 'dovi-p8.mkv'
Assert-True ([bool]$doviP8.DoviPresent) 'DoVi P8 should be detected.'
Assert-Equal $doviP8.DoviProfile 8 'DoVi P8 profile mismatch.'
Assert-Equal $doviP8.DoviBlCompatId 1 'DoVi P8 compatibility id mismatch.'
Assert-True (-not [bool]$doviP8.DoviElPresent) 'DoVi P8 EL flag should be false.'

$noSideDataJson = @'
{
  "streams": [
    {
      "codec_name": "hevc"
    }
  ]
}
'@
Set-StubProbeResults @((New-StubProbeResult -Output $noSideDataJson))
$noDovi = Get-DolbyVisionState -FilePath 'hdr10-only.mkv'
Assert-True ([bool]$noDovi.Known) 'Missing side_data_list should be a known non-DoVi result.'
Assert-True (-not [bool]$noDovi.DoviPresent) 'Missing side_data_list should not report DoVi.'

Set-StubProbeResults @((New-StubProbeResult -ExitCode 1 -ErrorText 'broken source'))
$failedDovi = Get-DolbyVisionState -FilePath 'broken.mkv'
Assert-True (-not [bool]$failedDovi.Known) 'ffprobe failure should be unknown.'
Assert-True ([string]$failedDovi.Reason -match 'broken source') 'ffprobe failure reason should include stderr.'
$knownNoHdr10Plus = [pscustomobject][ordered]@{
    Known = $true; Reason = ''; Hdr10PlusPresent = $false; SampledFrames = 0
}
$probeFailedEvidence = New-DynamicHdrEvidence -Route 'encode' -DoviState $failedDovi -Hdr10PlusState $knownNoHdr10Plus
Assert-True (-not [bool]$probeFailedEvidence.probed) 'Probe-failed evidence must set probed=false.'
Assert-Equal $probeFailedEvidence.outcome 'probe_failed' 'Probe-failed evidence outcome mismatch.'
Assert-True ([string]$probeFailedEvidence.probe_error -match 'dovi: broken source') 'Probe-failed evidence must keep the reason.'

$hdr10PlusJson = @'
{
  "frames": [
    { "side_data_list": [] },
    { "side_data_list": [] },
    {
      "side_data_list": [
        { "side_data_type": "HDR Dynamic Metadata SMPTE2094-40 (HDR10+)" }
      ]
    }
  ]
}
'@
Set-StubProbeResults @((New-StubProbeResult -Output $hdr10PlusJson))
$hdr10Plus = Test-Hdr10PlusPresence -FilePath 'hdr10plus.mkv'
Assert-True ([bool]$hdr10Plus.Known) 'HDR10+ probe should be known.'
Assert-True ([bool]$hdr10Plus.Hdr10PlusPresent) 'HDR10+ metadata should be detected.'
Assert-Equal $hdr10Plus.SampledFrames 3 'HDR10+ sampled frame count mismatch.'
Assert-Equal $script:DynamicHdrProbeStages[0].Stage 'hdr10plus-detection' 'HDR10+ probe stage mismatch.'
Assert-Equal $script:DynamicHdrProbeStages[0].TimeoutSeconds 60 'HDR10+ probe timeout mismatch.'

$smpte209410Json = @'
{
  "frames": [
    {
      "side_data_list": [
        { "side_data_type": "HDR Dynamic Metadata SMPTE2094-10" },
        { "side_data_type": "Dolby Vision Metadata" }
      ]
    }
  ]
}
'@
Set-StubProbeResults @((New-StubProbeResult -Output $smpte209410Json))
$notHdr10Plus = Test-Hdr10PlusPresence -FilePath 'dovi-2094-10.mkv'
Assert-True ([bool]$notHdr10Plus.Known) 'SMPTE2094-10 probe should be known.'
Assert-True (-not [bool]$notHdr10Plus.Hdr10PlusPresent) 'SMPTE2094-10 / DoVi frame side data must not be reported as HDR10+.'

$knownNoDovi = [pscustomobject][ordered]@{
    Known = $true
    Reason = ''
    DoviPresent = $false
    DoviProfile = 0
    DoviLevel = 0
    DoviBlCompatId = -1
    DoviRpuPresent = $false
    DoviElPresent = $false
}
$encodeEvidence = New-DynamicHdrEvidence -Route 'encode' -DoviState $doviP7 -Hdr10PlusState $knownNoHdr10Plus
Assert-Equal $encodeEvidence.outcome 'will_drop_encode' 'Encode DoVi evidence should warn about dropped dynamic metadata.'
Assert-True ([bool]$encodeEvidence.dynamic_metadata_present) 'Encode DoVi evidence should mark dynamic metadata present.'
Assert-True ([string]$encodeEvidence.warning -match 'will be dropped') 'Encode DoVi evidence should include warning text.'

$remuxEvidence = New-DynamicHdrEvidence -Route 'remux' -DoviState $knownNoDovi -Hdr10PlusState $hdr10Plus
Assert-Equal $remuxEvidence.outcome 'expected_preserved_remux' 'Remux HDR10+ evidence outcome mismatch.'
Assert-True ([bool]$remuxEvidence.dynamic_metadata_present) 'Remux HDR10+ evidence should mark dynamic metadata present.'
Assert-True ([string]$remuxEvidence.summary -match 'HDR10\+') 'Remux HDR10+ evidence summary mismatch.'

$noneEvidence = New-DynamicHdrEvidence -Route 'encode' -DoviState $knownNoDovi -Hdr10PlusState $knownNoHdr10Plus
Assert-True ([bool]$noneEvidence.probed) 'Absent-metadata evidence should be fully probed.'
Assert-Equal $noneEvidence.outcome 'none_detected' 'Absent-metadata evidence outcome mismatch.'
Assert-True (-not [bool]$noneEvidence.dynamic_metadata_present) 'Absent-metadata evidence should not mark metadata present.'

$encodeText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\encode.ps1') -Raw
$remuxText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\entrypoints\MediaPipeline\remux.ps1') -Raw
$publishText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_completion.ps1') -Raw
Assert-True ($encodeText -match '\$script:CurrentDynamicHdrEvidence\s*=\s*\$null') 'Encode must reset dynamic HDR evidence per file.'
Assert-True ($remuxText -match '\$script:CurrentDynamicHdrEvidence\s*=\s*\$null') 'Remux must reset dynamic HDR evidence per file.'
Assert-True ($publishText -match '\[''dynamic_hdr''\]\s*=\s*\$script:CurrentDynamicHdrEvidence') 'Publish completion must add dynamic_hdr sidecar evidence.'
Assert-True ($encodeText -match 'Resolve-DynamicHdrEncodePreservationDecision') 'Encode must resolve Dynamic HDR preserve/remux/review policy before building encode attempts.'
Assert-True ($encodeText -match "DynamicHdrPolicy=off; skipping Dynamic HDR probes") 'Encode must skip Dynamic HDR probes when the policy is off.'
Assert-True ($encodeText -match "Register-SourceFailure[\s\S]+-Stage 'dynamic-hdr-policy'") 'Encode preserve_or_review must route unsupported Dynamic HDR encode sources to backend failure review.'
Assert-True ($encodeText -match 'Do-Remux \$file \$isTV \$tvInfo -FallbackFromDynamicHdrEncode') 'Encode preserve_or_remux must use the guarded Dynamic HDR remux fallback.'
Assert-True ($encodeText -match "Test-DynamicHdrToolsAvailable[\s\S]+Test-X265DynamicHdrCapability") 'Encode preserve policies must evaluate tool and x265 capability before claiming preservation.'
Assert-True ($encodeText -match "dynamic_hdr_metadata_dropped[\s\S]+policy_action") 'Encode drop warnings must include Dynamic HDR policy action evidence.'
Assert-True ($remuxText -match '\[switch\] \$FallbackFromDynamicHdrEncode') 'Remux must expose a Dynamic HDR fallback switch.'
Assert-True ($remuxText -match 'LastDynamicHdrRemuxFallbackRejection') 'Remux must record Dynamic HDR remux fallback rejection evidence.'
Assert-True ($remuxText -match 'DYNAMIC HDR REMUX FALLBACK') 'Remux must log Dynamic HDR fallback rejection without bouncing back into encode.'

Write-Host 'Dynamic HDR detection checks passed.'
