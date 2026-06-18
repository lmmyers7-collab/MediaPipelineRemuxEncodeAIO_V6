# Implementation Ledger

Change packet: `MP-CHANGE-2026-0616-011`

| Issue ID | Source Markdown file | Severity | Affected files/modules | Confirmed / invalid / already fixed / blocked | Required tests | Risk boundary touched | Implementation status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F-001 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | High | `ops/pipeline/engine/subtitles/builders.ps1`; `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`; `ops/pipeline/entrypoints/MediaPipeline/remux.ps1`; publish/pending sidecar modules | Confirmed | Subtitle builder, sidecar, pending publish, ownership, and schema checks | FFmpeg subtitle planning; pending publish; sidecar handling | Validated in `MP-CHANGE-2026-0616-011`: MP4 converted-SRT candidate/reduction evidence is recorded and high-value reductions fail closed before publish. |
| F-002 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Medium | Completed-job and pending-manifest schemas | Confirmed | Contract schema checks; completed-manifest backfill dry-run checks | Completed job schema; pending manifest schema; sidecar evidence | Validated in `MP-CHANGE-2026-0616-011`: VobSub and MP4 converted-SRT evidence fields are exposed in schemas. |
| F-003 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Medium | `ops/pipeline/engine/subtitles/routing_decisions.ps1`; subtitle builder tests | Confirmed | Subtitle builder decision checks | Subtitle language filtering | Validated in `MP-CHANGE-2026-0616-011`: ASS/SSA blank languages normalize through the same policy path as other subtitle formats. |
| F-004 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Medium | Subtitle validation scripts and tests | Confirmed | SRT validation and file-override burn checks from repo root and test directory | Subtitle validation tooling | Validated in `MP-CHANGE-2026-0616-011`: scripts resolve the repository root from stable markers instead of producing `ops/ops` paths. |
| F-005 | `05-findings.md`, `06-remediation-plan.md`, `08-final-review-summary.md` | Low | `ops/pipeline/engine/subtitles/language_policy.ps1`; subtitle builder tests | Confirmed | Subtitle builder decision checks | Supplemental subtitle classification | Validated in `MP-CHANGE-2026-0616-011`: supplemental/SDH keywords now match literally rather than using PowerShell wildcard semantics. |

## Validation Notes

- The full validation evidence is recorded in `ops/release/changes/unreleased/MP-CHANGE-2026-0616-011.json`.
- Real-media OCR/playback validation remains not run because no safe sample media set was provided in this workspace.
