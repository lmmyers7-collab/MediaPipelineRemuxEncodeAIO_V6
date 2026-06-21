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

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\executable_resolution.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\dynamic_hdr.ps1')

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-dynamic-hdr-tools-" + [guid]::NewGuid().ToString('N'))
$oldPath = [string]$env:PATH
try {
    $repoRootForModules = Join-Path $tempRoot 'repo'
    $scriptDir = Join-Path $repoRootForModules 'ops\pipeline\entrypoints'
    $bundledDoviDir = Join-Path $repoRootForModules 'ops\pipeline\tools\dovi_tool'
    $bundledHdr10PlusDir = Join-Path $repoRootForModules 'ops\pipeline\tools\hdr10plus_tool'
    $customDir = Join-Path $tempRoot 'custom'
    $systemDir = Join-Path $tempRoot 'system'
    New-Item -ItemType Directory -Force -Path $scriptDir, $bundledDoviDir, $bundledHdr10PlusDir, $customDir, $systemDir | Out-Null

    $customDovi = Join-Path $customDir 'dovi_tool.exe'
    $bundledDovi = Join-Path $bundledDoviDir 'dovi_tool.exe'
    $bundledHdr10Plus = Join-Path $bundledHdr10PlusDir 'hdr10plus_tool.exe'
    $systemHdr10Plus = Join-Path $systemDir 'hdr10plus_tool.cmd'
    Set-Content -LiteralPath $customDovi -Value 'custom dovi tool' -Encoding ASCII
    Set-Content -LiteralPath $bundledDovi -Value 'bundled dovi tool' -Encoding ASCII
    Set-Content -LiteralPath $bundledHdr10Plus -Value 'bundled hdr10plus tool' -Encoding ASCII
    Set-Content -LiteralPath $systemHdr10Plus -Value '@echo off' -Encoding ASCII

    $script:AllowSystemTools = $false

    $configResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'dovi_tool' `
        -ConfiguredPath $customDovi `
        -RelativeCandidates @('..\tools\dovi_tool\dovi_tool.exe')
    Assert-Equal $configResolution.Source 'config' 'Configured dovi_tool path should win over bundled path.'
    Assert-Equal $configResolution.Path (Resolve-Path -LiteralPath $customDovi).Path 'Configured dovi_tool path mismatch.'

    $bundledResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'dovi_tool' `
        -ConfiguredPath '' `
        -RelativeCandidates @('..\tools\dovi_tool\dovi_tool.exe')
    Assert-Equal $bundledResolution.Source 'bundled' 'Bundled dovi_tool should win when no config override exists.'
    Assert-Equal $bundledResolution.Path (Resolve-Path -LiteralPath $bundledDovi).Path 'Bundled dovi_tool path mismatch.'

    Remove-Item -LiteralPath $bundledHdr10Plus -Force
    $env:PATH = "$systemDir$([System.IO.Path]::PathSeparator)$oldPath"
    $systemResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'hdr10plus_tool' `
        -ConfiguredPath '' `
        -RelativeCandidates @('..\tools\hdr10plus_tool\hdr10plus_tool.exe') `
        -AllowSystemTools
    Assert-Equal $systemResolution.Source 'system' 'AllowSystemTools should allow PATH fallback after bundled lookup.'
    Assert-True ([string]$systemResolution.Path -like '*hdr10plus_tool.cmd') 'System hdr10plus_tool path should resolve to the PATH command.'

    $env:PATH = $oldPath
    $missingResolution = Resolve-DynamicHdrToolPath `
        -CommandName 'hdr10plus_tool' `
        -ConfiguredPath '' `
        -RelativeCandidates @('..\tools\hdr10plus_tool\hdr10plus_tool.exe')
    Assert-Equal $missingResolution.Source 'missing' 'Missing hdr10plus_tool should be nonfatal and marked missing.'
    Assert-True ([string]$missingResolution.Reason -match 'AllowSystemTools is false') 'Missing-tool reason should mention disabled PATH fallback.'

    Assert-Equal (ConvertFrom-DynamicHdrToolVersionText -Text 'dovi_tool 2.3.2') '2.3.2' 'dovi_tool version parsing failed.'
    Assert-Equal (ConvertFrom-DynamicHdrToolVersionText -Text "hdr10plus_tool v1.7.2`n") '1.7.2' 'hdr10plus_tool version parsing failed.'
    Assert-Equal (ConvertFrom-DynamicHdrToolVersionText -Text 'not a version') '' 'Unversioned output should return blank version.'

    $availability = Test-DynamicHdrToolsAvailable -DoviToolPath '' -Hdr10PlusToolPath ''
    Assert-True (-not [bool]$availability.AnyToolAvailable) 'Missing dynamic HDR tools should not report availability.'

    Clear-DynamicHdrCapabilityProbe
    $missingFfmpegA = Join-Path $tempRoot 'missing-a\ffmpeg.exe'
    $missingFfmpegB = Join-Path $tempRoot 'missing-b\ffmpeg.exe'
    $firstCapability = Test-X265DynamicHdrCapability -FfmpegPath $missingFfmpegA
    $cachedCapability = Test-X265DynamicHdrCapability -FfmpegPath $missingFfmpegB
    Assert-Equal $cachedCapability.FfmpegPath $missingFfmpegA 'Capability probe should return cached answer without Force.'
    Assert-True ([string]$cachedCapability.Reason -match 'ffmpeg not found') 'Capability cache should keep missing-ffmpeg reason.'
    $forcedCapability = Test-X265DynamicHdrCapability -FfmpegPath $missingFfmpegB -Force
    Assert-Equal $forcedCapability.FfmpegPath $missingFfmpegB 'Capability probe should refresh when Force is supplied.'

    $warnPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy warn `
        -DoviPresent:$true `
        -DoviProfile 8 `
        -DoviBlCompatId 1
    Assert-Equal $warnPlan.Action 'warn_only' 'Warn policy should not change encode routing.'
    Assert-Equal $warnPlan.recommended_route 'encode' 'Warn policy should keep encode route.'
    Assert-True (-not [bool]$warnPlan.can_preserve_encode) 'Warn policy should not claim encode preservation.'

    $remuxPlan = New-DynamicHdrPreservationPlan `
        -Route remux `
        -Policy preserve_or_review `
        -Hdr10PlusPresent:$true
    Assert-Equal $remuxPlan.Action 'preserve_by_remux' 'Remux should be the preservation path for dynamic HDR metadata.'
    Assert-Equal $remuxPlan.recommended_route 'remux' 'Remux preservation should recommend remux.'

    $profile5RemuxPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_remux `
        -DoviPresent:$true `
        -DoviProfile 5
    Assert-Equal $profile5RemuxPlan.Action 'prefer_remux' 'Unsupported DoVi encode profile should prefer remux under preserve_or_remux.'
    Assert-Equal $profile5RemuxPlan.recommended_route 'remux' 'Unsupported DoVi profile should recommend remux for preserve_or_remux.'
    Assert-True ((@($profile5RemuxPlan.Reasons) -join '; ') -match 'profile 5') 'Unsupported DoVi plan should name the profile.'

    $profile5ReviewPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_review `
        -DoviPresent:$true `
        -DoviProfile 5
    Assert-Equal $profile5ReviewPlan.Action 'hold_review' 'Unsupported DoVi encode profile should hold review under preserve_or_review.'
    Assert-Equal $profile5ReviewPlan.recommended_route 'review' 'Unsupported DoVi profile should recommend review for preserve_or_review.'

    $missingPrereqPlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_review `
        -DoviPresent:$true `
        -DoviProfile 8 `
        -DoviBlCompatId 1 `
        -Hdr10PlusPresent:$true `
        -VideoCodec hevc_nvenc
    Assert-Equal $missingPrereqPlan.Action 'hold_review' 'Missing tools/capabilities should hold review for preserve_or_review.'
    $missingPrereqReasons = @($missingPrereqPlan.Reasons) -join '; '
    Assert-True ($missingPrereqReasons -match 'CPU x265') 'Missing prerequisite plan should require CPU x265.'
    Assert-True ($missingPrereqReasons -match 'dovi_tool') 'Missing prerequisite plan should require dovi_tool.'
    Assert-True ($missingPrereqReasons -match 'hdr10plus_tool') 'Missing prerequisite plan should require hdr10plus_tool.'

    $encodePreservePlan = New-DynamicHdrPreservationPlan `
        -Route encode `
        -Policy preserve_or_review `
        -DoviPresent:$true `
        -DoviProfile 7 `
        -DoviElPresent:$true `
        -Hdr10PlusPresent:$true `
        -DoviToolAvailable:$true `
        -Hdr10PlusToolAvailable:$true `
        -X265DolbyVisionCapable:$true `
        -X265Hdr10PlusCapable:$true `
        -UseCpuFallback:$true
    Assert-Equal $encodePreservePlan.Action 'preserve_encode' 'Satisfied prerequisites should allow encode preservation planning.'
    Assert-True ([bool]$encodePreservePlan.can_preserve_encode) 'Satisfied prerequisites should mark encode preservation possible.'
    Assert-Equal $encodePreservePlan.target_dovi_profile '8.1' 'DoVi P7 encode preservation should target profile 8.1.'
    $artifactText = @($encodePreservePlan.required_artifacts) -join '; '
    Assert-True ($artifactText -match 'dovi_rpu_converted_profile_8_1') 'DoVi P7 plan should require converted RPU artifact.'
    Assert-True ($artifactText -match 'hdr10plus_json') 'HDR10+ plan should require metadata JSON artifact.'

    $missingEvidenceDecision = Resolve-DynamicHdrEncodePreservationDecision -Evidence $null -Policy 'preserve_or_review'
    Assert-Equal $missingEvidenceDecision.action 'none' 'Missing Dynamic HDR evidence should not change encode routing.'
    Assert-Equal $missingEvidenceDecision.reason_code 'dynamic_hdr_evidence_missing' 'Missing evidence reason code mismatch.'

    $noDynamicEvidence = [pscustomobject][ordered]@{
        dynamic_metadata_present = $false
        dovi_present             = $false
        hdr10plus_present        = $false
        summary                  = 'no dynamic HDR metadata detected'
    }
    $noDynamicDecision = Resolve-DynamicHdrEncodePreservationDecision -Evidence $noDynamicEvidence -Policy 'preserve_or_review'
    Assert-Equal $noDynamicDecision.action 'none' 'Absent Dynamic HDR metadata should not change encode routing.'
    Assert-True ([bool]$noDynamicDecision.should_attempt_gpu) 'Absent Dynamic HDR metadata should leave GPU attempts enabled.'

    $doviHdr10PlusEvidence = [pscustomobject][ordered]@{
        dynamic_metadata_present = $true
        dovi_present             = $true
        dovi_profile             = 7
        dovi_bl_compat_id        = -1
        dovi_el_present          = $true
        hdr10plus_present        = $true
        summary                  = 'DoVi profile 7 (EL present) + HDR10+'
    }
    $warnDecision = Resolve-DynamicHdrEncodePreservationDecision -Evidence $doviHdr10PlusEvidence -Policy 'warn' -VideoCodec 'hevc_nvenc'
    Assert-Equal $warnDecision.action 'warn_only' 'Warn policy should not activate Dynamic HDR preservation.'
    Assert-True ([bool]$warnDecision.should_attempt_gpu) 'Warn policy should leave GPU attempts enabled.'
    Assert-True (-not [bool]$warnDecision.should_force_cpu) 'Warn policy should not force CPU.'

    $preserveDecision = Resolve-DynamicHdrEncodePreservationDecision `
        -Evidence $doviHdr10PlusEvidence `
        -Policy 'preserve_or_review' `
        -OutputContainer 'mkv' `
        -VideoCodec 'hevc_nvenc' `
        -DoviToolAvailable:$true `
        -Hdr10PlusToolAvailable:$true `
        -X265DolbyVisionCapable:$true `
        -X265Hdr10PlusCapable:$true
    Assert-Equal $preserveDecision.action 'preserve_encode' 'Satisfied Dynamic HDR preservation decision should preserve via CPU encode.'
    Assert-True ([bool]$preserveDecision.should_extract) 'Satisfied Dynamic HDR preservation decision should require metadata extraction.'
    Assert-True ([bool]$preserveDecision.should_force_cpu) 'Satisfied Dynamic HDR preservation decision should force CPU encode.'
    Assert-True (-not [bool]$preserveDecision.should_attempt_gpu) 'Satisfied Dynamic HDR preservation decision should skip GPU attempts.'
    Assert-Equal $preserveDecision.reason_code 'dynamic_hdr_preserve_encode_cpu' 'Preserve decision reason code mismatch.'
    Assert-Equal $preserveDecision.target_dovi_profile '8.1' 'Preserve decision target profile mismatch.'

    $missingToolDecision = Resolve-DynamicHdrEncodePreservationDecision `
        -Evidence $doviHdr10PlusEvidence `
        -Policy 'preserve_or_remux' `
        -OutputContainer 'mkv' `
        -VideoCodec 'hevc_nvenc' `
        -Hdr10PlusToolAvailable:$true `
        -X265DolbyVisionCapable:$true `
        -X265Hdr10PlusCapable:$true
    Assert-Equal $missingToolDecision.action 'prefer_remux' 'Missing DoVi tool under preserve_or_remux should prefer remux.'
    Assert-True ([bool]$missingToolDecision.should_prefer_remux) 'Missing DoVi tool decision should flag remux preference.'
    Assert-True ((@($missingToolDecision.reasons) -join '; ') -match 'dovi_tool') 'Missing DoVi tool decision should name the missing tool.'

    $unsupportedProfileEvidence = [pscustomobject][ordered]@{
        dynamic_metadata_present = $true
        dovi_present             = $true
        dovi_profile             = 5
        dovi_bl_compat_id        = -1
        dovi_el_present          = $false
        hdr10plus_present        = $false
        summary                  = 'DoVi profile 5'
    }
    $unsupportedReviewDecision = Resolve-DynamicHdrEncodePreservationDecision -Evidence $unsupportedProfileEvidence -Policy 'preserve_or_review' -OutputContainer 'mkv' -DoviToolAvailable:$true -X265DolbyVisionCapable:$true
    Assert-Equal $unsupportedReviewDecision.action 'hold_review' 'Unsupported DoVi profile under preserve_or_review should hold review.'
    Assert-True ([bool]$unsupportedReviewDecision.should_hold_review) 'Unsupported DoVi profile should flag hold review.'
    Assert-Equal $unsupportedReviewDecision.error_code 'DYNAMIC_HDR_UNPRESERVABLE' 'Unsupported DoVi profile review error code mismatch.'

    $mp4Decision = Resolve-DynamicHdrEncodePreservationDecision -Evidence $doviHdr10PlusEvidence -Policy 'preserve_or_remux' -OutputContainer 'mp4' -DoviToolAvailable:$true -Hdr10PlusToolAvailable:$true -X265DolbyVisionCapable:$true -X265Hdr10PlusCapable:$true
    Assert-Equal $mp4Decision.action 'prefer_remux' 'Non-MKV Dynamic HDR preserve_or_remux decision should prefer remux.'
    Assert-Equal $mp4Decision.reason_code 'dynamic_hdr_output_container_unsupported' 'Non-MKV decision reason code mismatch.'

    $noMetadataExtractionPlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'source.mkv' `
        -WorkDir 'work' `
        -PlanId 'noop'
    Assert-True ([bool]$noMetadataExtractionPlan.ok) 'Absent dynamic metadata should produce an ok no-op extraction plan.'
    Assert-True (-not [bool]$noMetadataExtractionPlan.required) 'Absent dynamic metadata should not require extraction.'

    $mkvExtractionPlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'source.mkv' `
        -WorkDir 'work' `
        -DoviPresent:$true `
        -DoviProfile 7 `
        -DoviElPresent:$true `
        -Hdr10PlusPresent:$true `
        -DoviToolPath 'tools\dovi_tool.exe' `
        -Hdr10PlusToolPath 'tools\hdr10plus_tool.exe' `
        -MkvExtractPath 'tools\mkvextract.exe' `
        -VideoTrackId 4 `
        -PlanId 'case-01'
    $expectedHevcPath = Join-Path 'work' 'dynamic_hdr_case-01.hevc'
    $expectedRpuPath = Join-Path 'work' 'dynamic_hdr_case-01.rpu.bin'
    $expectedHdr10PlusPath = Join-Path 'work' 'dynamic_hdr_case-01.hdr10plus.json'
    Assert-True ([bool]$mkvExtractionPlan.ok) 'MKV extraction command plan should be ready.'
    Assert-Equal $mkvExtractionPlan.target_dovi_profile '8.1' 'MKV DoVi P7 extraction plan should target profile 8.1.'
    Assert-Equal $mkvExtractionPlan.dovi_conversion_mode 'profile7_to_81' 'MKV DoVi P7 extraction plan should convert to profile 8.1.'
    Assert-Equal $mkvExtractionPlan.hevc_path $expectedHevcPath 'MKV extraction HEVC path mismatch.'
    Assert-Equal $mkvExtractionPlan.rpu_path $expectedRpuPath 'MKV extraction RPU path mismatch.'
    Assert-Equal $mkvExtractionPlan.hdr10plus_json_path $expectedHdr10PlusPath 'MKV extraction HDR10+ path mismatch.'
    Assert-Equal ((@($mkvExtractionPlan.commands.extract_hevc.arguments) -join '|')) "tracks|source.mkv|4:$expectedHevcPath" 'MKV extraction must use the supplied video track id.'
    Assert-Equal ((@($mkvExtractionPlan.commands.extract_dovi_rpu.arguments) -join '|')) "-m|2|extract-rpu|-i|$expectedHevcPath|-o|$expectedRpuPath" 'DoVi P7 extraction command mismatch.'
    Assert-Equal ((@($mkvExtractionPlan.commands.summarize_dovi_rpu.arguments) -join '|')) "info|-i|$expectedRpuPath|--summary" 'DoVi RPU summary command mismatch.'
    Assert-Equal ((@($mkvExtractionPlan.commands.extract_hdr10plus.arguments) -join '|')) "extract|-i|$expectedHevcPath|-o|$expectedHdr10PlusPath" 'HDR10+ extraction command mismatch.'
    Assert-Equal @($mkvExtractionPlan.temp_files).Count 4 'Extraction plan should track all temp artifacts for cleanup.'
    Assert-True ((@($mkvExtractionPlan.caveats) -join '; ') -match 'enhancement layer') 'DoVi P7 EL caveat should be explicit.'

    $mkvMissingTrackPlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'source.mkv' `
        -WorkDir 'work' `
        -DoviPresent:$true `
        -DoviProfile 8 `
        -DoviBlCompatId 1 `
        -DoviToolPath 'tools\dovi_tool.exe' `
        -MkvExtractPath 'tools\mkvextract.exe' `
        -PlanId 'missing-track'
    Assert-True (-not [bool]$mkvMissingTrackPlan.ok) 'MKV extraction must fail closed without an explicit video track id.'
    Assert-Equal $mkvMissingTrackPlan.error_code 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED' 'MKV missing track-id error code mismatch.'
    Assert-True ([string]$mkvMissingTrackPlan.reason -match 'must not assume track 0') 'MKV missing track-id reason should reject track 0 assumptions.'

    $mp4ExtractionPlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'clip.mp4' `
        -WorkDir 'work' `
        -DoviPresent:$true `
        -DoviProfile 8 `
        -DoviBlCompatId 1 `
        -DoviToolPath 'tools\dovi_tool.exe' `
        -FfmpegPath 'tools\ffmpeg.exe' `
        -PlanId 'mp4-case'
    $mp4HevcPath = Join-Path 'work' 'dynamic_hdr_mp4-case.hevc'
    $mp4RpuPath = Join-Path 'work' 'dynamic_hdr_mp4-case.rpu.bin'
    Assert-True ([bool]$mp4ExtractionPlan.ok) 'MP4 extraction command plan should be ready.'
    Assert-Equal ((@($mp4ExtractionPlan.commands.extract_hevc.arguments) -join '|')) "-i|clip.mp4|-map|0:v:0|-c:v|copy|-bsf:v|hevc_mp4toannexb|-f|hevc|$mp4HevcPath" 'MP4 extraction should use ffmpeg Annex B conversion.'
    Assert-Equal ((@($mp4ExtractionPlan.commands.extract_dovi_rpu.arguments) -join '|')) "extract-rpu|-i|$mp4HevcPath|-o|$mp4RpuPath" 'DoVi P8.1 extraction command mismatch.'

    $unsupportedProfilePlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'clip.mp4' `
        -WorkDir 'work' `
        -DoviPresent:$true `
        -DoviProfile 5 `
        -DoviToolPath 'tools\dovi_tool.exe' `
        -FfmpegPath 'tools\ffmpeg.exe' `
        -PlanId 'profile5'
    Assert-True (-not [bool]$unsupportedProfilePlan.ok) 'Unsupported DoVi profiles must not get extraction commands.'
    Assert-Equal $unsupportedProfilePlan.error_code 'DYNAMIC_HDR_UNPRESERVABLE' 'Unsupported profile error code mismatch.'
    Assert-True ($null -eq $unsupportedProfilePlan.commands.extract_hevc) 'Unsupported DoVi profiles must not populate HEVC extraction commands.'

    $missingToolPlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'clip.mp4' `
        -WorkDir 'work' `
        -Hdr10PlusPresent:$true `
        -FfmpegPath 'tools\ffmpeg.exe' `
        -PlanId 'missing-tool'
    Assert-True (-not [bool]$missingToolPlan.ok) 'Missing HDR10+ tool should fail closed.'
    Assert-Equal $missingToolPlan.error_code 'DYNAMIC_HDR_TOOL_MISSING' 'Missing HDR10+ tool error code mismatch.'

    $script:DynamicHdrCommandInvocations = @()
    $script:DynamicHdrCommandFailures = @{}
    $script:DynamicHdrSuppressArtifact = ''

    function Get-TestOutputPathFromArgs {
        param([array] $ArgumentList)

        $argsList = @($ArgumentList)
        for ($idx = 0; $idx -lt $argsList.Count; $idx++) {
            if ([string]$argsList[$idx] -eq '-o' -and ($idx + 1) -lt $argsList.Count) {
                return [string]$argsList[$idx + 1]
            }
        }
        if ($argsList.Count -gt 0 -and [string]$argsList[0] -eq 'tracks') {
            $trackSpec = [string]$argsList[2]
            $separator = $trackSpec.IndexOf(':')
            if ($separator -ge 0) { return $trackSpec.Substring($separator + 1) }
        }
        if ($argsList -contains '-f' -and $argsList -contains 'hevc' -and $argsList.Count -gt 0) {
            return [string]$argsList[$argsList.Count - 1]
        }
        return ''
    }

    function Invoke-NativeProcess {
        param(
            [string] $FilePath,
            [array] $ArgumentList,
            [int] $TimeoutSeconds = 0,
            [string] $Label = '',
            [int] $MaxStdoutChars = 0,
            [int] $MaxStderrChars = 0,
            [string] $ProcessPriority = 'inherit'
        )

        $script:DynamicHdrCommandInvocations = @($script:DynamicHdrCommandInvocations) + @([pscustomobject][ordered]@{
            FilePath        = $FilePath
            ArgumentList    = @($ArgumentList)
            Label           = $Label
            TimeoutSeconds  = $TimeoutSeconds
            ProcessPriority = $ProcessPriority
        })

        if ($script:DynamicHdrCommandFailures.ContainsKey($Label)) {
            return [pscustomobject][ordered]@{
                ExitCode = [int]$script:DynamicHdrCommandFailures[$Label]
                TimedOut = $false
                Stopped  = $false
                Aborted  = $false
                Stdout   = ''
                Stderr   = 'simulated failure'
            }
        }

        if ($Label -eq 'Dolby Vision RPU summary') {
            return [pscustomobject][ordered]@{
                ExitCode = 0
                TimedOut = $false
                Stopped  = $false
                Aborted  = $false
                Stdout   = 'RPU frames: 42'
                Stderr   = ''
            }
        }

        $outputPath = Get-TestOutputPathFromArgs -ArgumentList $ArgumentList
        if (-not [string]::IsNullOrWhiteSpace($outputPath)) {
            $suppress = -not [string]::IsNullOrWhiteSpace($script:DynamicHdrSuppressArtifact) -and $Label -match [regex]::Escape($script:DynamicHdrSuppressArtifact)
            if (-not $suppress) {
                Set-Content -LiteralPath $outputPath -Value "artifact for $Label" -Encoding ASCII
            }
        }

        return [pscustomobject][ordered]@{
            ExitCode = 0
            TimedOut = $false
            Stopped  = $false
            Aborted  = $false
            Stdout   = ''
            Stderr   = ''
        }
    }

    $executionWorkDir = Join-Path $tempRoot 'execution'
    New-Item -ItemType Directory -Force -Path $executionWorkDir | Out-Null
    $executionPlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'source.mkv' `
        -WorkDir $executionWorkDir `
        -DoviPresent:$true `
        -DoviProfile 7 `
        -DoviElPresent:$true `
        -Hdr10PlusPresent:$true `
        -DoviToolPath 'tools\dovi_tool.exe' `
        -Hdr10PlusToolPath 'tools\hdr10plus_tool.exe' `
        -MkvExtractPath 'tools\mkvextract.exe' `
        -VideoTrackId 4 `
        -PlanId 'execute-ok'
    $executionResult = Export-DynamicHdrMetadata -Plan $executionPlan -TimeoutSeconds 12 -ProcessPriority 'belownormal'
    Assert-True ([bool]$executionResult.ok) 'Dynamic HDR extraction execution should succeed when every command and artifact succeeds.'
    Assert-Equal $executionResult.rpu_frame_count 42 'Dynamic HDR extraction should parse the RPU frame count from summary output.'
    Assert-True (Test-Path -LiteralPath $executionResult.hevc_path -PathType Leaf) 'Dynamic HDR extraction should create the HEVC artifact.'
    Assert-True (Test-Path -LiteralPath $executionResult.rpu_path -PathType Leaf) 'Dynamic HDR extraction should create the RPU artifact.'
    Assert-True (Test-Path -LiteralPath $executionResult.hdr10plus_json_path -PathType Leaf) 'Dynamic HDR extraction should create the HDR10+ artifact.'
    Assert-True (Test-Path -LiteralPath $executionResult.rpu_summary_path -PathType Leaf) 'Dynamic HDR extraction should persist the RPU summary evidence.'
    Assert-Equal @($executionResult.command_results).Count 4 'Dynamic HDR extraction should record all command results.'
    Assert-Equal @($script:DynamicHdrCommandInvocations).Count 4 'Dynamic HDR extraction should run the planned commands only once each.'
    Assert-Equal $script:DynamicHdrCommandInvocations[0].Label 'dynamic HDR HEVC extraction' 'Dynamic HDR extraction should run HEVC extraction first.'
    Assert-Equal $script:DynamicHdrCommandInvocations[1].Label 'Dolby Vision RPU extraction' 'Dynamic HDR extraction should run RPU extraction second.'
    Assert-Equal $script:DynamicHdrCommandInvocations[2].Label 'Dolby Vision RPU summary' 'Dynamic HDR extraction should run RPU summary third.'
    Assert-Equal $script:DynamicHdrCommandInvocations[3].Label 'HDR10+ metadata extraction' 'Dynamic HDR extraction should run HDR10+ extraction last.'

    $x265Paths = Resolve-DynamicHdrX265ArtifactPaths -ExtractionResult $executionResult -BaseDirectory $tempRoot
    Assert-True ([bool]$x265Paths.ok) 'Dynamic HDR x265 artifact path resolution should succeed for same-root artifacts.'
    Assert-True ([bool]$x265Paths.required) 'Dynamic HDR x265 artifact path resolution should be required when artifacts exist.'
    Assert-True (-not [System.IO.Path]::IsPathRooted([string]$x265Paths.dolby_vision_rpu_path)) 'Dynamic HDR RPU x265 path should be relative.'
    Assert-True (-not ([string]$x265Paths.dolby_vision_rpu_path).Contains(':')) 'Dynamic HDR RPU x265 path should be colon-free.'
    Assert-True (-not [System.IO.Path]::IsPathRooted([string]$x265Paths.hdr10plus_json_path)) 'Dynamic HDR10+ x265 path should be relative.'
    Assert-True (-not ([string]$x265Paths.hdr10plus_json_path).Contains(':')) 'Dynamic HDR10+ x265 path should be colon-free.'
    Assert-Equal $x265Paths.rpu_frame_count 42 'Dynamic HDR x265 path result should carry RPU frame-count evidence.'

    $missingArtifactExtraction = [pscustomobject][ordered]@{
        ok                   = $true
        reason               = ''
        error_code           = ''
        rpu_path             = (Join-Path $tempRoot 'missing.rpu.bin')
        hdr10plus_json_path  = ''
        target_dovi_profile  = '8.1'
        rpu_frame_count      = 42
    }
    $missingArtifactPaths = Resolve-DynamicHdrX265ArtifactPaths -ExtractionResult $missingArtifactExtraction -BaseDirectory $tempRoot
    Assert-True (-not [bool]$missingArtifactPaths.ok) 'Dynamic HDR x265 path resolution should fail closed when an artifact is missing.'
    Assert-Equal $missingArtifactPaths.error_code 'DOVI_RPU_EXTRACT_FAILED' 'Missing RPU x265 path error code mismatch.'

    $baseRoot = [System.IO.Path]::GetPathRoot($tempRoot)
    $foreignDrive = if ([string]$baseRoot -like 'Z:*') { 'Y:' } else { 'Z:' }
    $foreignExtraction = [pscustomobject][ordered]@{
        ok                   = $true
        reason               = ''
        error_code           = ''
        rpu_path             = "$foreignDrive\dynamic_hdr\rpu.bin"
        hdr10plus_json_path  = ''
        target_dovi_profile  = '8.1'
        rpu_frame_count      = 42
    }
    $foreignPaths = Resolve-DynamicHdrX265ArtifactPaths -ExtractionResult $foreignExtraction -BaseDirectory $tempRoot
    Assert-True (-not [bool]$foreignPaths.ok) 'Dynamic HDR x265 path resolution should fail closed for cross-drive artifact paths.'
    Assert-Equal $foreignPaths.error_code 'DYNAMIC_HDR_X265_PATH_UNREPRESENTABLE' 'Cross-drive x265 path error code mismatch.'

    $script:DynamicHdrCommandInvocations = @()
    $script:DynamicHdrCommandFailures = @{ 'Dolby Vision RPU extraction' = 2 }
    $failureResult = Export-DynamicHdrMetadata -Plan $executionPlan
    Assert-True (-not [bool]$failureResult.ok) 'Dynamic HDR extraction should fail closed when RPU extraction fails.'
    Assert-Equal $failureResult.error_code 'DOVI_RPU_EXTRACT_FAILED' 'Dynamic HDR RPU extraction failure code mismatch.'
    Assert-Equal @($failureResult.command_results).Count 2 'Dynamic HDR extraction should stop after the failing RPU command.'

    $script:DynamicHdrCommandInvocations = @()
    $script:DynamicHdrCommandFailures = @{}
    $script:DynamicHdrSuppressArtifact = 'HDR10+ metadata extraction'
    $emptyArtifactPlan = New-DynamicHdrMetadataExtractionPlan `
        -ScratchPath 'clip.mp4' `
        -WorkDir $executionWorkDir `
        -Hdr10PlusPresent:$true `
        -Hdr10PlusToolPath 'tools\hdr10plus_tool.exe' `
        -FfmpegPath 'tools\ffmpeg.exe' `
        -PlanId 'empty-hdr10plus'
    $emptyArtifactResult = Export-DynamicHdrMetadata -Plan $emptyArtifactPlan
    Assert-True (-not [bool]$emptyArtifactResult.ok) 'Dynamic HDR extraction should fail closed when HDR10+ extraction creates no artifact.'
    Assert-Equal $emptyArtifactResult.error_code 'HDR10PLUS_EXTRACT_FAILED' 'Dynamic HDR empty HDR10+ artifact failure code mismatch.'
} finally {
    $env:PATH = $oldPath
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host 'Dynamic HDR tooling checks passed.'
