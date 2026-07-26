# Worker 05 — Media Policy

Assigned rows: 132. First-pass status: complete. Reviewer: `/root/coverage_universe`.

Independent high-risk second review remains pending for 93 rows. This worker report does not claim completion of that gate.

## Scope and safety

- Performed exact-byte semantic review of the assigned media-policy decision, encode/remux argument, audio, subtitle, FFmpeg progress, Python subtitle/ASS helper, policy-document, generated-summary, archive, and dependency-asset rows.
- Read the no-touch register before inspection. No product code, media, operator state, production configuration, or generated source was changed. No real-media execution was performed or required because this slice produced audit evidence only.
- No product fixes were attempted. All mutations are confined to the four Worker 05 audit artifacts.

## Coverage and provenance

- Rebuilt the W05 universe and completed 132/132 assigned rows with zero missing, extra, duplicate, path-drift, or SHA-256-drift records.
- Terminal status counts: 71 `generated_verified`, 46 `line_reviewed_no_findings`, 13 `line_reviewed_with_findings`, and 2 `archive_inventoried`.
- Second-review counts: 93 `pending` high-risk rows and 39 `not_required` rows.
- Domain slices: 67 generated summaries; 17 PowerShell decision sources; 13 PowerShell subtitle sources; 5 PowerShell process sources; 2 PowerShell audio sources; 21 Python decision/subtitle/ASS helpers; and 7 supporting documents, tests, archives, or dependency assets.
- All 67 generated summaries reproduce exactly from their declared sources under generator fingerprint `d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d`. Their source hashes, headings, regeneration commands, artifact hashes, and coverage hashes reconcile.
- The ASS-to-SRT CLI dependency PNG reproduces exactly and its SVG is semantically identical after newline normalization. The ASS-to-SRT library dependency PNG/SVG does not reproduce and omits current consumer edges; that drift is recorded as W05-011.

## Findings

Thirteen new, globally deduplicated root-cause findings were recorded: 1 P1, 10 P2, and 2 P3.

- `AUDIT-FIND-W05-001` (P1): ASS-to-SRT CLI accepts identical input/output paths and can replace the source or an existing destination through `os.replace`.
- `AUDIT-FIND-W05-002` (P2): completed subtitle QA normalizes boolean `False` to an empty string, allowing a missing output to report a passing posture.
- `AUDIT-FIND-W05-003` (P2): the Python processing planner returns REMUX with no audio even when `allow_no_audio` is false.
- `AUDIT-FIND-W05-004` (P2): Python `subtitle_mode=convert_preferred` is ignored; planned subtitle actions remain copies and no conversion is scheduled.
- `AUDIT-FIND-W05-005` (P2): the PowerShell SRT merger treats numeric-only cue text as an index and can silently drop valid subtitle text.
- `AUDIT-FIND-W05-006` (P2): the allowed no-audio early return leaves stale `LastAudio*` globals that downstream remux consumers read.
- `AUDIT-FIND-W05-007` (P2): VobSub MP4 staging can leak a temporary MKV when `mkvextract` is unavailable because the early result omits that staged file from `TempFiles`.
- `AUDIT-FIND-W05-008` (P2): optional subtitle-event cleanup invokes `seconv` with an unbounded `Start-Process -Wait`, without timeout, stop handling, or heartbeat evidence.
- `AUDIT-FIND-W05-009` (P3): scratch subtitle staging checks output absence before work but later `os.replace` can overwrite a concurrently created scratch output.
- `AUDIT-FIND-W05-010` (P2): Python decision planning describes only the first video stream while FFmpeg maps all non-attached video streams with `0:V`.
- `AUDIT-FIND-W05-011` (P3): generated ASS-to-SRT dependency atlas PNG/SVG artifacts are stale and omit current `core/subtitles` consumer relationships.
- `AUDIT-FIND-W05-012` (P2): any nonempty sparse `ActiveOverrides` map that omits `RemoveKaraoke` silently resets the global ASS karaoke-removal policy to false.
- `AUDIT-FIND-W05-013` (P2): fixed-priority family dispatch records only one family from an already collected mixed ASS/TX3G/BDPGS/VobSub failure array.

The exact path-local join also retains existing finding `CPA-2026-07-19-007` on `ops/pipeline/engine/subtitles/failure_records.ps1`; it is not duplicated as a new Worker 05 root cause.

## Prior-audit reconciliation

- The archived fallback-remux route-hint defect does not reproduce in current code: `fallback_remux` is preserved by profile selection, oversized-encode rejection is explicit, and the active routing check covers the failure evidence.
- The archived MP4 converted-sidecar provenance defect does not reproduce in current code: typed candidates preserve `SourceKind`, and the active subtitle-builder decision checks assert the selected MP4 sidecar provenance.
- The archived multi-video planner mismatch remains current and is represented by `AUDIT-FIND-W05-010`.
- The two archived reports were inventoried as historical evidence only; no historical completion status was inherited.

## Validation evidence

- Parsed all 21 assigned Python files with the Python AST and all 37 assigned PowerShell files with the PowerShell parser: zero syntax failures.
- Ran `refresh_summaries --check` against all 67 declared sources: passed with no stale or orphan summaries.
- Reproduced and compared both assigned dependency atlases with the current generator; visually inspected both PNGs at original resolution and read both SVGs exactly.
- Ran synthetic, temporary-only reproductions for identical ASS input/output, subtitle QA missing-output handling, no-audio planning, preferred-subtitle conversion planning, numeric SRT cues, stale audio globals, and multi-video planning. These probes support W05-001 through W05-006 and W05-010 without touching real media.
- Python focused suite: 54 tests and 45 subtests passed across decision, ASS-to-SRT, subtitle staging, subtitle QA, and FFmpeg media-policy regression-matrix coverage.
- PowerShell focused suites passed: Audio Policy, Subtitle Builder Decision, VobSub Subtitle, Subtitle Long-Work Heartbeat, FFmpeg/MKVMerge Progress, Encode Flag Policy (23 snapshots), Library Profile Routing, and Remux Split Stage.
- Candidate follow-up probes passed without product or media mutation: sparse override reproduction emitted `global=1, sparse=0`, and a four-family failure input emitted `recorded_count=1, family=bdpgs`. Both exact source hashes still match the coverage baseline and parse with zero PowerShell AST errors.
- Exact W05-local fragment validation passes for all 132 review rows, 13 findings, and 33 execution-error records. Official helpers report zero finding, error, review-fragment, merged-row schema, current-content, or non-achieved issues. Every W05 finding join equals the exact current path-local central-plus-fragment set.
- The legacy all-in-one reliability suite did not reach subtitle assertions because its known project-root/checklist lookup still searches under `ops\docs`; that failure is recorded as W05-032. Five focused PowerShell suites covering the candidate paths passed independently. No real-media run was performed because this task changed audit evidence only.
- An earlier atomic checkpoint passed global review-row preparation across 6,064 rows with zero issues. The final global rerun is currently blocked outside W05 by an out-of-range W09 finding location; because that invalidates global finding preparation, it also produces cascading missing-link errors. The failed and truncated rerun is recorded as W05-026 and is not represented as a W05-local success.

## Handoff

- Worker 05 first-pass review is complete; 93 high-risk rows require independent second review before the repository-wide audit can close.
- The error ledger contains 33 command, truncation, path, syntax, append-recovery, test-harness, or cross-worker validation events. Each event records its disposition; no failed command was silently retried. W05-026 remains an explicitly external global-merge blocker; all candidate-review events are closed and non-blocking.
- Authoritative worker artifacts are `worker-05-media-policy-review.jsonl`, `worker-05-media-policy-findings.jsonl`, `worker-05-media-policy-errors.jsonl`, and this report.
