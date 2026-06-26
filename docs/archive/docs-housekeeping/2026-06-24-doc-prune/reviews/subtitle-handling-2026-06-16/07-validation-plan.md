# Validation Plan

## Static Validation

1. Regenerate targeted summaries for changed review documents and change packet.

2. Run change-control validation.

3. Inspect `git status --short` and confirm only intended review artifacts/change packet/generated summaries were added or changed by this work.

## Targeted Unit/Contract Checks

Run after remediation:

```powershell
& .\ops\pipeline\tests\Unit\Invoke-SubtitleBuilderDecisionChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-SubtitleOcrPathResolutionChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-SrtValidationChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-VobSubSubtitleChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-SidecarWriteSafetyChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-PendingPublishSafetyChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-FileOverrideSubtitleBurnChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1
& .\ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1
```

Python:

```powershell
$env:PYTHONPATH='src'
.\apps\desktop\runtime\Python\python.exe -m pytest tests\python\core\subtitles\test_ass_to_srt_helpers.py -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_subtitle_qa_feature -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_service_config_validation tests.python.desktop.test_metadata_contract -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_telemetry_service -q
```

## New Tests Required Before Source Fix Approval

1. MP4 multiple converted subtitles.

   Fixture: one ASS dialogue, one forced ASS/signs, one TX3G, one BDPGS or VobSub candidate. Expected: every retained source track either gets a published output or a durable review/dropped record; forced/SDH/supplemental losses block or review.

2. ASS blank language.

   Fixture: ASS stream with no language tag. Expected: `und` policy retains it consistently.

3. Completed schema VobSub parity.

   Expected: completed-job schema enumerates every subtitle array required by runtime sidecar validation.

4. SRT validation harness.

   Expected: direct test script runs from repo root and validates empty-cue, embedded-blank, invalid-timing, and all-empty behavior.

5. File override burn harness.

   Expected: direct test script runs from repo root and verifies exact selected burn track is burned while other selectable subtitle outputs are dropped with durable decision records.

6. Supplemental keyword literal behavior.

   Expected: custom keyword `?` or `[` does not overmatch unrelated subtitle titles.

## Real-Media Validation Matrix

| Sample | Expected Result |
| --- | --- |
| ASS/SSA dialogue plus signs/songs | SRT generated; original preserved when container supports it; supplemental decision visible |
| ASS blank language | Retained when policy includes `und`; no silent drop |
| TX3G MP4 | SRT generated; external sidecar publish failure blocks reveal |
| BDPGS English | SUP extracted; OCR SRT non-empty; failures block publish |
| BDPGS unknown language | Fails closed with language-unknown failure; no publish |
| VobSub embedded MKV | IDX/SUB extracted; OCR SRT non-empty; failures block publish |
| VobSub external pair | Complete pair converts or disabled conversion routes to review; missing `.sub` routes failure/review |
| MP4 multiple retained converted subtitles | No unrecorded loss; publish blocked or every non-selected candidate is durably reviewed |

## Acceptance Criteria

- No subtitle conversion failure can reach final publish.
- No sidecar publish failure can reveal final media.
- Every retained subtitle track has one of: embedded preserved, SRT embedded, SRT sidecar published, burned into video, explicit drop decision, or review/failure record.
- Every MP4 compatibility subtitle reduction is durable in sidecar/pending/completed evidence.
- Completed QA sees VobSub evidence through schema and payload.
- Targeted tests and real-media validation pass.
