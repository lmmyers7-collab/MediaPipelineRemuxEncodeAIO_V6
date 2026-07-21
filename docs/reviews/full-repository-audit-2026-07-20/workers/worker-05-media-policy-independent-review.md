# Worker 05 P1 Independent Review

Reviewer: `/root/coordinator_w05`  
First reviewer: `/root/coverage_universe`

`AUDIT-FIND-W05-001` was independently reviewed at the exact first-pass source hash `410a391cfb4c4a160c89faba4155d82cd0526b06a00ff7f99807e117585afce4` and remains confirmed.

The current CLI validates that input, stream, and output arguments are present but does not establish canonical path separation. Its SRT and optional diagnostic writers both commit through `os.replace`. Independent disposable-directory probes confirmed that an input/output alias replaces the original bytes with SRT and that an input/summary alias replaces them with JSON. The focused helper and caller scope has no alias or default no-clobber test.

The production PowerShell caller normally constructs a scratch output path, which reduces ordinary exposure but does not make the mutation-capable helper safe for direct or future callers. The independent disposition therefore matches the first-pass finding.

## High-risk generated-summary batch

The 67 W05 high-risk generated-summary rows were independently re-read, rehashed, and reproduced from their declared current sources with the canonical summary checker. The batch contains 1,318 physical Markdown lines and 74,323 bytes. All 67 current hashes match their first-pass rows, every first-pass status is `generated_verified`, every first reviewer is `/root/coverage_universe`, and every exact path-local finding set is empty. Distinct attestations are recorded for all 67 paths.

This closes independent provenance/reproducibility review for those generated artifacts only. It does not substitute for semantic review of their underlying first-party source files.

## High-risk Python source batch

Five high-risk Python sources were independently reviewed across all 1,392 physical lines: `processing_decision.py`, `subtitles/__init__.py`, `subtitles/facade.py`, `subtitles/qa.py`, and `subtitles/stage.py`. The exact first-pass finding sets remain unchanged: no findings on the first three paths, `AUDIT-FIND-W05-002` on `qa.py`, and `AUDIT-FIND-W05-009` on `stage.py`.

The boolean-QA root was reproduced directly: a coherent Completed decision with `output_exists=False` returned `posture=pass`, while the string value `"false"` blocked. The scratch commit root was also reproduced in a disposable directory: a competing SRT inserted after validation but immediately before commit was replaced, and the stage returned success. All 43 focused processing-decision, subtitle-stage, and subtitle-QA tests passed; none covers those two negative paths.

## High-risk FFmpeg progress source batch

Four high-risk PowerShell sources were independently reviewed across all 1,021 physical lines: `ffmpeg_progress.ps1` and its `events.ps1`, `parsing.ps1`, and `tool_context.ps1` helpers. All exact path-local finding sets remain empty. The FFmpeg/mkvmerge progress suite and seven Python status/progress cases pass. The review covered progress dialects, bounded in-memory tails, active diagnostic capture, process identity callbacks, timeout/stop/abort handling, waste-guard aborts, audio-work evidence, mkvmerge warning classification, repro evidence, and terminal Run Monitor events.

`AUDIT-ERR-COORD-080` preserves one clipped combined source read and its bounded missing-range recovery. `AUDIT-ERR-COORD-081` preserves an incorrect assumed bundled PowerShell path; no bundled `pwsh.exe` was present, so the successful focused retry used the discovered PATH PowerShell 7.6.3 executable.

## High-risk audio state and remux-consumer batch

Three high-risk PowerShell sources were independently reviewed across all 1,265 physical lines: `audio.ps1`, `audio/stream_decisions.ps1`, and `remux_ffmpeg_av_stage.ps1`. Their exact first-pass finding sets remain unchanged: `AUDIT-FIND-W05-006` on `audio.ps1` and the remux consumer, and no finding on the pure decision helper.

The stale-state root was reproduced without source edits or media. An in-memory extension of the current focused harness first built a one-track transcoding plan, then exercised the allowed silent-input branch. The second call returned `-an`, but `LastAudioDefaultIndex=0`, `LastAudioTrackCount=1`, and `LastAudioTranscodeActive=True` remained from the previous file. The remux stage reads the last value directly at lines 115 and 125 to add thread caps and enter CPU-mutex/priority handling. The audio-policy and remux-split-stage suites both pass; the latter's `Build-AudioArgs` stub resets the globals on every invocation and therefore does not cover this sequential early-return path.

`AUDIT-ERR-COORD-082` preserves the clipped middle of the first combined `stream_decisions.ps1` read. Two smaller reads returned lines 241-360 and 361-474 before attestation, restoring exact coverage of all 474 lines.

## High-risk subtitle source batch

All thirteen high-risk subtitle sources were independently reviewed across all 5,714 physical lines: `ass.ps1`, `bdpgs.ps1`, `builders.ps1`, `builders/decisions.ps1`, `common.ps1`, `failure_records.ps1`, `filtering.ps1`, `language_policy.ps1`, `routing_decisions.ps1`, `srt.ps1`, `subtitles.ps1`, `tx3g.ps1`, and `vobsub.ps1`. Their exact current hashes match the first-pass rows, all thirteen parse with zero PowerShell AST errors, and the subtitle builder, VobSub, long-work heartbeat, library-profile, and remux suites pass.

The exact first-pass finding sets remain unchanged: `AUDIT-FIND-W05-012` on `ass.ps1`; `CPA-2026-07-19-007` and `AUDIT-FIND-W05-013` on `failure_records.ps1`; `AUDIT-FIND-W05-005` on `srt.ps1`; `AUDIT-FIND-W05-007` and `AUDIT-FIND-W05-008` on `vobsub.ps1`; and empty sets on the other nine paths. The numeric-only SRT loss and staged-MKV leak were reproduced in memory, and the seconv indefinite-wait root was confirmed by exact control-flow review without launching an unsafe hang probe.

After the distinct first reviewer froze the two candidate sets, independent current-function probes reproduced both new roots without writes. With global `RemoveKaraoke=true`, `Convert-AssToSrt` sent helper argument `1`; adding only `ActiveOverrides={RoutingProfile='manual'}` changed that argument to `0`. A mixed ASS/TX3G/BDPGS/VobSub input to `Register-SubtitleExtractionFailure` registered one BDPGS record containing one detail, discarding the other three already-collected families. The separate nine-code query continues to sustain `CPA-2026-07-19-007`.

`AUDIT-ERR-COORD-084` through `AUDIT-ERR-COORD-087` preserve the rejected, no-match, and malformed initial numeric-cue probes before the successful in-memory reproduction. `AUDIT-ERR-COORD-088` preserves the failure-code registry suite's reproduction of already tracked `AUDIT-FIND-W15-002`; the separate nine-code query independently confirmed the current `CPA-2026-07-19-007` retryability root.

## Validation boundary

- Exact source and generated-summary hashes matched the first-pass evidence.
- The path-local first-pass and independent finding sets are exactly `AUDIT-FIND-W05-001`.
- The 67 generated-summary first-pass and independent finding sets are exactly empty, and canonical regeneration passed for all 67 declared sources.
- The five high-risk Python source attestations match their first-pass status, hash, and exact path-local finding set; both current findings remain independently confirmed.
- The four FFmpeg progress source attestations match their first-pass hashes/statuses and exact empty finding sets; focused PowerShell and Python progress suites passed.
- The three audio-state/remux source attestations match their first-pass hashes, statuses, and exact path-local finding sets; `AUDIT-FIND-W05-006` remains independently confirmed and both focused PowerShell suites passed.
- All thirteen subtitle-source attestations match their first-pass hashes/statuses and exact path-local finding sets; six path-local findings remain independently confirmed, all thirteen sources parse, and the five focused subtitle suites passed.
- The direct official validator passes all 94 W05 attestations, and the W05-scoped completion validator reports zero missing high-risk or P1 obligations.
- `AUDIT-ERR-COORD-072`, `AUDIT-ERR-COORD-074`, and `AUDIT-ERR-COORD-075` preserve all coordinator read/query failures and their successful retries.
- `AUDIT-ERR-COORD-080`, `AUDIT-ERR-COORD-081`, and `AUDIT-ERR-COORD-082` preserve the independent progress/audio read and environment failures and their successful bounded retries.
- `AUDIT-ERR-COORD-084` through `AUDIT-ERR-COORD-088` preserve the independent subtitle probe and already-tracked registry-test outcomes.
- Only disposable text fixtures were used; no real media, source library, application behavior, or operator state was modified.
