# Audio Routing Policy Implementation Ledger

Change packet: `MP-CHANGE-2026-0616-004`

## Ledger

| Issue ID | Source Markdown | Severity | Affected files/modules | Verification status | Required tests | Risk boundary touched | Implementation status |
|---|---|---:|---|---|---|---|---|
| ARP-001 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | High | `ops/pipeline/config/profiles/Default.psd1`; config key registry checks | Confirmed. Current `Default.psd1` had broad `CompatibleAudioCodecs` and no `AudioPassthroughProfile`, so runtime blank-profile resolution could become `custom_codec_list`. | `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1` | Profile/config ownership; Plex direct-play policy | Fixed and validated |
| ARP-002 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | High | `src/mediapipeline/core/decide/encoding_rules.py`; Python decision tests | Confirmed. Python `audio_transcode_reason()` transcodes compatible tracks solely because channels exceed `audio_max_channels`, while PowerShell runtime caps only transcoded output. | `tests/python/core/decide/test_processing_decision.py` | Audio passthrough/transcode; channel caps; Plex direct-play implication | Fixed and validated |
| ARP-003 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | High | `ops/pipeline/engine/process/pipeline_plan_executor.ps1`; plan executor checks | Confirmed. `New-PipelinePlanExecutorAudioArgumentList` emitted `-an` when all audio actions were dropped and did not inspect `presetV2.audio.allowNoAudio`. | `ops/pipeline/tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1` | FFmpeg command planning; no-audio fail-closed behavior | Fixed and validated under `pwsh` |
| ARP-004 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Medium | `src/mediapipeline/core/decide/routing.py`; Python decision tests | Confirmed. Python MP4 selection ranked source default flag before channel count, while PowerShell ranks language, commentary, EAC3, fidelity, then source ordinal. | `tests/python/core/decide/test_processing_decision.py` | MP4 compatibility; language/default selection; track preservation | Fixed and validated |
| ARP-005 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Medium | `src/mediapipeline/core/queue/file_overrides.py`; queue/local API tests | Confirmed. Python validation rejected audio fields that PowerShell can consume (`renameTracks`, `downmixMode`, `transcodeCodec`, `transcodeBitrate`), leaving split ownership for saved/manual override policy. | `tests/python/desktop/test_facade_queue_policy.py`; `tests/python/desktop/test_application_facade_local_api.py` | Queue file overrides; saved audio policy ownership | Fixed and validated |
| ARP-006 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Medium | `tests/python/integration/test_handbrake_remux_regression_matrix.py` | Confirmed. Matrix still expected MP4 multi-audio actions `transcode/copy/copy`, while focused MP4 tests and current planner behavior use single-audio retention. | `tests/python/integration/test_handbrake_remux_regression_matrix.py` | Test coverage for MP4 track preservation/drop behavior | Fixed and validated |
| ARP-007 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Low | `src/mediapipeline/core/config/preview.py`; config preview tests | Confirmed as a helper-level fragility. Current full settings save flows include both audio keys in managed keys, but a profile-only preview could preserve stale manual codecs even when the profile is structured. | `tests/python/desktop/test_service_config_preview.py` | Settings persistence; profile/config ownership | Fixed and validated |

## Batch Status

| Batch | Issue IDs | Scope | Status | Validation evidence |
|---|---|---|---|---|
| 1 | ARP-001, ARP-007 | Config/profile ownership and preview reconciliation | Complete | `powershell -NoProfile -ExecutionPolicy Bypass -File ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1` passed. `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_service_config_preview -q` passed, 6 tests. |
| 2 | ARP-002, ARP-004, ARP-006 | Python audio planner parity and stale matrix | Complete | `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.core.decide.test_processing_decision -q` passed, 27 tests. `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.integration.test_handbrake_remux_regression_matrix -q` passed, 5 tests. |
| 3 | ARP-003 | Plan executor no-audio fail-closed behavior | Complete | `powershell -NoProfile -ExecutionPolicy Bypass -File ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1` failed before assertions because existing `ops\pipeline\engine\shared\media_constants.ps1` uses PowerShell 7 null-coalescing syntax. `pwsh -NoProfile -ExecutionPolicy Bypass -File ops\pipeline\tests\Unit\Invoke-PipelinePlanExecutorChecks.ps1` passed. |
| 4 | ARP-005 | Per-file audio override validation ownership | Complete | `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_facade_queue_policy -q` passed, 28 tests. `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_local_api.LocalApiServerTests.test_local_api_file_override_validates_current_payload_fields -q` passed, 1 test. A prior local API test invocation failed because the method name was incorrect, not because assertions ran. |

## Blocked Or Invalid Findings

None. All confirmed review findings were implemented.

## Final Validation Notes

- Consolidated targeted Python suite passed: `tests.python.core.decide.test_processing_decision`, `tests.python.integration.test_handbrake_remux_regression_matrix`, `tests.python.desktop.test_service_config_preview`, `tests.python.desktop.test_facade_queue_policy`, and `tests.python.desktop.test_application_facade_local_api.LocalApiServerTests.test_local_api_file_override_validates_current_payload_fields` ran 67 tests.
- PowerShell config registry check passed under Windows PowerShell.
- Plan executor check passed under `pwsh`. The same harness still fails before assertions under Windows PowerShell because existing `ops/pipeline/engine/shared/media_constants.ps1` uses PowerShell 7 null-coalescing syntax.
- Strict change-control coverage failed only on unrelated repository state after this packet's type was corrected: `MP-CHANGE-2026-0615-021` lacks required high/critical notes or rollback detail, and 16 unrelated changed files are not covered by an unreleased packet.
- Real-media multi-audio/Plex playback validation was not run; no safe sample media set was provided in this workspace.
