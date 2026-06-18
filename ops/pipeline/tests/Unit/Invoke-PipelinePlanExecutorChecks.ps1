param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
. (Join-Path $repoRoot 'ops\pipeline\engine\process\pipeline_plan_executor.ps1')

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-SequenceEqual {
    param(
        [array] $Actual,
        [array] $Expected,
        [string] $Message
    )
    if ($Actual.Count -ne $Expected.Count) {
        throw "$Message Expected $($Expected.Count) items but got $($Actual.Count). Actual: $($Actual -join '|')"
    }
    for ($i = 0; $i -lt $Expected.Count; $i++) {
        if ([string]$Actual[$i] -ne [string]$Expected[$i]) {
            throw "$Message Difference at index $i. Expected '$($Expected[$i])' but got '$($Actual[$i])'. Actual: $($Actual -join '|')"
        }
    }
}

function Assert-ContainsText {
    param(
        [string] $Text,
        [string] $Needle,
        [string] $Message
    )
    if ($Text -notlike "*$Needle*") {
        throw "$Message Missing '$Needle' in '$Text'."
    }
}

function Assert-DoesNotContainText {
    param(
        [string] $Text,
        [string] $Needle,
        [string] $Message
    )
    if ($Text -like "*$Needle*") {
        throw "$Message Unexpected '$Needle' in '$Text'."
    }
}

function ConvertTo-NormalizedPlanCommand {
    param(
        [array] $ArgumentList,
        [string] $InputPath,
        [string] $OutputPath
    )
    return @($ArgumentList | ForEach-Object {
        $text = [string]$_
        if ($text -eq $InputPath) { '<input>' }
        elseif ($text -eq $OutputPath) { '<output>' }
        elseif ($text -like '*.temp_av.mkv') { '<temp-av>' }
        else { $text }
    })
}

function New-ExpectedLegacyRemuxAvArgs {
    param(
        $Plan,
        [string] $InputPath,
        [string] $TempAvPath
    )
    $videoAction = Get-PipelinePlanSingleStreamAction -Plan $Plan -StreamType 'video'
    $expected = [System.Collections.Generic.List[string]]::new()
    $expected.AddRange([string[]]@('-i', $InputPath, '-map', '0:V', '-c:v', 'copy'))
    if (([string]$videoAction.inputCodec).Trim().ToLowerInvariant() -in (Get-MediaVideoCodecHevcNames)) {
        $expected.AddRange([string[]]@('-bsf:v', 'hevc_mp4toannexb'))
    }
    $expected.AddRange([string[]]@('-map', '0:t?', '-map_chapters', '0', '-map_metadata', '0'))
    $expected.AddRange([string[]](New-PipelinePlanExecutorAudioArgumentList -Plan $Plan))
    $expected.AddRange([string[]]@('-y', $TempAvPath))
    return @($expected.ToArray())
}

function Get-Phase07BFixturePlans {
    $python = Join-Path $repoRoot 'apps\desktop\runtime\Python\python.exe'
    $script = @'
import json
from pathlib import Path
from mediapipeline.contracts.source_media import source_media_from_ffprobe
from mediapipeline.core.orchestration.planner import build_pipeline_plan_from_preset

root = Path("tests/fixtures/source_media")
for path in sorted(root.glob("*.json")):
    source = source_media_from_ffprobe(json.loads(path.read_text(encoding="utf-8")))
    plan = build_pipeline_plan_from_preset(source, plan_id=path.stem)
    print(json.dumps({"fixture": path.name, "plan": plan.model_dump(mode="json", by_alias=True)}, separators=(",", ":")))
'@
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $repoRoot 'src'
        $output = & $python -c $script
        if ($LASTEXITCODE -ne 0) {
            throw "Python plan generation failed with exit $LASTEXITCODE."
        }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }
    $cases = [System.Collections.Generic.List[object]]::new()
    foreach ($line in @($output)) {
        if ([string]::IsNullOrWhiteSpace([string]$line)) { continue }
        $cases.Add(($line | ConvertFrom-Json -Depth 100)) | Out-Null
    }
    return @($cases.ToArray())
}

function Get-Phase07BMp4FixturePlan {
    $python = Join-Path $repoRoot 'apps\desktop\runtime\Python\python.exe'
    $script = @'
import json
from pathlib import Path
from mediapipeline.contracts.source_media import source_media_from_ffprobe
from mediapipeline.core.orchestration.planner import build_pipeline_plan_from_preset

source = source_media_from_ffprobe(json.loads(Path("tests/fixtures/source_media/multi_audio_tracks.json").read_text(encoding="utf-8")))
plan = build_pipeline_plan_from_preset(source, {"OutputContainer": "mp4"}, plan_id="mp4-compatibility-remux")
print(json.dumps(plan.model_dump(mode="json", by_alias=True), separators=(",", ":")))
'@
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $repoRoot 'src'
        $output = & $python -c $script
        if ($LASTEXITCODE -ne 0) {
            throw "Python MP4 plan generation failed with exit $LASTEXITCODE."
        }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }
    return ($output | Select-Object -First 1 | ConvertFrom-Json -Depth 100)
}

$fixtureCases = @(Get-Phase07BFixturePlans)
Assert-Equal $fixtureCases.Count 10 'Phase 07B parity harness must cover every Phase 03 source-media fixture.'

function Test-PlanRequiresMkvmergeSubtitleTidMap {
    param([Parameter(Mandatory)] $Plan)

    if ([string]$Plan.routeSummary -ne 'REMUX') { return $false }
    foreach ($action in @(Get-PipelinePlanStreamActions -Plan $Plan -StreamType 'subtitle')) {
        $actionName = ([string]$action.action).Trim().ToLowerInvariant()
        if ($actionName -ne 'drop' -and $actionName -ne 'burn') {
            return $true
        }
    }
    return $false
}

$matched = [System.Collections.Generic.List[string]]::new()
foreach ($case in $fixtureCases) {
    $planJson = $case.plan | ConvertTo-Json -Depth 100
    $plan = ConvertFrom-PipelinePlanJson -Json $planJson
    if (Test-PlanRequiresMkvmergeSubtitleTidMap -Plan $plan) {
        $tidRejected = $false
        try {
            New-PipelinePlanExecutorDryRun -Plan $plan | Out-Null
        } catch {
            $message = [string]$_.Exception.Message
            $tidRejected = ($message -like '*mkvmerge subtitle TID map unavailable*')
        }
        Assert-True $tidRejected "REMUX fixture $($case.fixture) should fail closed without mkvmerge subtitle TID evidence."
        $matched.Add($case.fixture) | Out-Null
        continue
    }

    $dryRun = New-PipelinePlanExecutorDryRun -Plan $plan
    Assert-Equal $dryRun.schemaVersion 'pipeline_plan_executor_dry_run.v1' "Dry-run schema mismatch for $($case.fixture)."
    Assert-True $dryRun.dryRunOnly "Executor result must be dry-run only for $($case.fixture)."
    Assert-True (-not $dryRun.wouldExecute) "Executor result must not execute for $($case.fixture)."

    if ([string]$plan.routeSummary -eq 'REMUX') {
        Assert-Equal $dryRun.commands.Count 2 "REMUX fixture $($case.fixture) should produce remux AV and mux commands."
        $remuxAv = $dryRun.commands[0]
        Assert-Equal $remuxAv.label 'REMUX-AV' "First REMUX command label mismatch for $($case.fixture)."
        Assert-Equal $remuxAv.tool 'ffmpeg' "First REMUX command tool mismatch for $($case.fixture)."
        $expectedTemp = [System.IO.Path]::ChangeExtension([string]$dryRun.outputPath, '.temp_av.mkv')
        $expected = New-ExpectedLegacyRemuxAvArgs -Plan $plan -InputPath ([string]$dryRun.inputPath) -TempAvPath $expectedTemp
        Assert-SequenceEqual `
            (ConvertTo-NormalizedPlanCommand -ArgumentList $remuxAv.argumentList -InputPath ([string]$dryRun.inputPath) -OutputPath ([string]$dryRun.outputPath)) `
            (ConvertTo-NormalizedPlanCommand -ArgumentList $expected -InputPath ([string]$dryRun.inputPath) -OutputPath ([string]$dryRun.outputPath)) `
            "REMUX AV command drift for $($case.fixture)."
        $joined = $remuxAv.argumentList -join ' '
        Assert-ContainsText $joined '-c:v copy' "REMUX fixture $($case.fixture) must copy video."
        Assert-DoesNotContainText $joined 'hevc_nvenc' "REMUX fixture $($case.fixture) must not invoke hardware video encode."
        Assert-DoesNotContainText $joined 'libx265' "REMUX fixture $($case.fixture) must not invoke CPU video encode."
        $matched.Add($case.fixture) | Out-Null
    } elseif ([string]$plan.routeSummary -eq 'ENCODE') {
        Assert-Equal $dryRun.commands.Count 1 "ENCODE fixture $($case.fixture) should produce one ffmpeg command."
        $encode = $dryRun.commands[0]
        Assert-Equal $encode.label 'ENCODE' "Encode command label mismatch for $($case.fixture)."
        Assert-Equal $encode.tool 'ffmpeg' "Encode command tool mismatch for $($case.fixture)."
        Assert-True (@($encode.builtWith) -contains 'New-EncodeAttemptPlan') "Encode fixture $($case.fixture) must use the existing encode attempt builder."
        $joined = $encode.argumentList -join ' '
        Assert-ContainsText $joined '-map 0:V' "Encode fixture $($case.fixture) must keep existing non-attached-picture video map."
        Assert-ContainsText $joined '-map 0:t?' "Encode fixture $($case.fixture) must preserve attachments like the legacy builder."
        Assert-ContainsText $joined '-f matroska' "Encode fixture $($case.fixture) must keep the existing Matroska muxer posture."
        Assert-ContainsText $joined '-c:v hevc_nvenc' "Encode fixture $($case.fixture) must use the plan-selected encoder."
        $matched.Add($case.fixture) | Out-Null
    } elseif ([string]$plan.routeSummary -eq 'COPY') {
        Assert-Equal $dryRun.commands.Count 1 "COPY fixture $($case.fixture) should produce one copy-source dry-run command."
        Assert-Equal $dryRun.commands[0].tool 'copy_source' "COPY fixture $($case.fixture) must stay out of FFmpeg."
        $matched.Add($case.fixture) | Out-Null
    } else {
        throw "Unexpected fixture route $($plan.routeSummary) for $($case.fixture)."
    }
}

Assert-Equal $matched.Count $fixtureCases.Count 'Not every Phase 03 fixture reached a parity assertion.'

$mp4Plan = ConvertFrom-PipelinePlanJson -Json ((Get-Phase07BMp4FixturePlan) | ConvertTo-Json -Depth 100)
$mp4DryRun = New-PipelinePlanExecutorDryRun -Plan $mp4Plan
Assert-Equal $mp4DryRun.commands.Count 1 'MP4 REMUX dry-run should produce one FFmpeg mux command.'
$mp4Command = $mp4DryRun.commands[0]
Assert-Equal $mp4Command.label 'REMUX-MP4' 'MP4 REMUX command label mismatch.'
Assert-Equal $mp4Command.tool 'ffmpeg' 'MP4 REMUX command tool mismatch.'
$mp4Joined = $mp4Command.argumentList -join ' '
Assert-ContainsText $mp4Joined '-map_chapters -1' 'MP4 REMUX should strip chapters.'
Assert-ContainsText $mp4Joined '-map_metadata -1' 'MP4 REMUX should strip source/global metadata.'
Assert-ContainsText $mp4Joined '-movflags +faststart' 'MP4 REMUX should enable faststart.'
Assert-DoesNotContainText $mp4Joined '-map 0:t?' 'MP4 REMUX should not map attachments/fonts.'
Assert-DoesNotContainText $mp4Joined '-map_metadata 0' 'MP4 REMUX should not preserve metadata.'
Assert-DoesNotContainText $mp4Joined '-c:t copy' 'MP4 REMUX should not copy attachments/fonts.'

$allAudioDroppedPlan = [pscustomobject]@{
    streamActions = @(
        [pscustomobject]@{ streamType = 'audio'; streamIndex = 1; action = 'drop'; inputCodec = 'aac'; outputCodec = ''; reasonCodes = @() },
        [pscustomobject]@{ streamType = 'audio'; streamIndex = 2; action = 'drop'; inputCodec = 'eac3'; outputCodec = ''; reasonCodes = @() }
    )
    effectivePresetSnapshot = [pscustomobject]@{
        presetV2 = [pscustomobject]@{
            audio = [pscustomobject]@{ allowNoAudio = $false }
        }
    }
}
$allDroppedRejected = $false
try {
    New-PipelinePlanExecutorAudioArgumentList -Plan $allAudioDroppedPlan | Out-Null
} catch {
    $allDroppedRejected = ([string]$_.Exception.Message -like '*all planned audio streams are dropped but allowNoAudio is not enabled*')
}
Assert-True $allDroppedRejected 'Plan executor audio args must fail closed when every audio stream is dropped without allowNoAudio.'

$allAudioDroppedPlan.effectivePresetSnapshot.presetV2.audio.allowNoAudio = $true
Assert-SequenceEqual (New-PipelinePlanExecutorAudioArgumentList -Plan $allAudioDroppedPlan) @('-an') 'Plan executor audio args should emit -an only when allowNoAudio is enabled.'

$textBurnPlan = [pscustomobject]@{
    streamActions = @(
        [pscustomobject]@{ streamType = 'video'; streamIndex = 0; action = 'encode'; inputCodec = 'h264'; outputCodec = 'hevc_nvenc'; reasonCodes = @() },
        [pscustomobject]@{ streamType = 'container'; action = 'keep'; inputCodec = 'matroska'; outputCodec = 'mkv'; reasonCodes = @() },
        [pscustomobject]@{ streamType = 'subtitle'; streamIndex = 3; action = 'copy'; inputCodec = 'subrip'; outputCodec = ''; reasonCodes = @() },
        [pscustomobject]@{ streamType = 'subtitle'; streamIndex = 7; action = 'burn'; inputCodec = 'subrip'; outputCodec = ''; reasonCodes = @() }
    )
}
$burnFilterArgs = New-PipelinePlanExecutorSubtitleBurnVideoFilterArgs -Plan $textBurnPlan -InputPath 'C:\Media\Input With Subs.mkv'
$burnFilterText = $burnFilterArgs -join ' '
Assert-ContainsText $burnFilterText ':si=1' 'Text subtitle burn must use subtitle ordinal, not global ffprobe stream index.'
Assert-DoesNotContainText $burnFilterText ':si=7' 'Text subtitle burn leaked global ffprobe stream index into si.'

function Get-MkvmergeTidMap {
    param([string] $FilePath, [string] $Context = '')
    return @{ 2 = 9; 5 = 4 }
}

$mkvmergePlan = [pscustomobject]@{
    planId = 'tid-map-plan'
    sourceId = 'source'
    output = [pscustomobject]@{ container = 'mkv' }
    streamActions = @(
        [pscustomobject]@{ streamType = 'video'; streamIndex = 0; action = 'copy'; inputCodec = 'hevc'; outputCodec = ''; reasonCodes = @() },
        [pscustomobject]@{ streamType = 'container'; action = 'remux'; inputCodec = 'matroska'; outputCodec = 'mkv'; reasonCodes = @() },
        [pscustomobject]@{ streamType = 'subtitle'; streamIndex = 2; action = 'copy'; inputCodec = 'hdmv_pgs_subtitle'; outputCodec = ''; reasonCodes = @() },
        [pscustomobject]@{ streamType = 'subtitle'; streamIndex = 5; action = 'convert'; inputCodec = 'ass'; outputCodec = 'subrip'; reasonCodes = @() }
    )
}
$mkvArgs = New-PipelinePlanExecutorMkvmergeArgumentList -Plan $mkvmergePlan -InputPath 'C:\Media\Input.mkv' -TempAvPath 'C:\Temp\Input.temp_av.mkv' -OutputPath 'C:\Out\Input.mkv'
$tracksIndex = [array]::IndexOf([object[]]$mkvArgs, '--subtitle-tracks')
Assert-True ($tracksIndex -ge 0) 'mkvmerge subtitle track selector is missing.'
Assert-Equal $mkvArgs[$tracksIndex + 1] '9,4' 'mkvmerge subtitle selector must use mkvmerge TIDs.'
Assert-DoesNotContainText ($mkvArgs -join ' ') '--subtitle-tracks 2,5' 'mkvmerge subtitle selector leaked ffprobe stream indexes.'

function Get-MkvmergeTidMap {
    param([string] $FilePath, [string] $Context = '')
    return @{}
}

$missingTidRejected = $false
try {
    New-PipelinePlanExecutorMkvmergeArgumentList -Plan $mkvmergePlan -InputPath 'C:\Media\Input.mkv' -TempAvPath 'C:\Temp\Input.temp_av.mkv' -OutputPath 'C:\Out\Input.mkv' | Out-Null
} catch {
    $missingTidRejected = ([string]$_.Exception.Message -like '*mkvmerge subtitle TID map unavailable for ffprobe stream(s) 2,5*')
}
Assert-True $missingTidRejected 'mkvmerge subtitle selector must fail closed when TID evidence is incomplete.'

$invalidPlan = $fixtureCases[0].plan | ConvertTo-Json -Depth 100 | ConvertFrom-Json -Depth 100
$invalidPlan | Add-Member -NotePropertyName 'extraField' -NotePropertyValue 'not allowed'
$invalidJson = $invalidPlan | ConvertTo-Json -Depth 100
$rejected = $false
try {
    ConvertFrom-PipelinePlanJson -Json $invalidJson | Out-Null
} catch {
    $rejected = ([string]$_.Exception.Message -like '*unknown property*')
}
Assert-True $rejected 'PipelinePlan validator must reject unknown plan fields.'

$remuxPlan = @($fixtureCases | Where-Object { [string]$_.plan.routeSummary -eq 'REMUX' } | Select-Object -First 1).plan
$remuxPlan.commandPlans[0].steps += [pscustomobject]@{
    stepId = 'bad-encode'
    operation = 'encode_video'
    streamType = 'video'
    streamIndex = 0
    label = 'Bad encode'
    dryRunText = 'Invalid remux encode step'
    details = @{}
}
$remuxRejected = $false
try {
    ConvertFrom-PipelinePlanJson -Json ($remuxPlan | ConvertTo-Json -Depth 100) | Out-Null
} catch {
    $remuxRejected = ([string]$_.Exception.Message -like '*contains encode_video step*')
}
Assert-True $remuxRejected 'PipelinePlan validator must reject encode_video steps in REMUX/COPY plans.'

Write-Host 'Pipeline plan executor checks passed.'
