# Decisions And History

Last updated: 2026-06-02

This document preserves durable decisions and historical context without requiring future agents to read every old checklist, audit, or handoff file.

## Current Direction

- V6 is the active promoted WebView/Tauri workspace.
- V5 remains the external rollback/fallback workspace and should not be modified from V6 work.
- The legacy desktop shell and removed root launcher shims are not active V6 surfaces; do not treat old desktop-shell fallback or root-launcher instructions as active V6 guidance.
- Tauri/WebView2 is the preferred long-term shell direction over PySide6/Qt for this project because it gives a modern operator interface, stronger table/layout ergonomics, and a clearer backend/frontend boundary while keeping the existing Python/PowerShell backend alive.
- Migration must stay adapter-based and incremental. Do not move backend-owned mutation authority into the frontend.

## Safety Decisions

- Backend owns mutation. Frontend code may stage, preview, display warnings, and post command requests, but it must not directly mutate files, config, queue state, pending publish state, or media artifacts.
- Source media must be copied to scratch before processing. Source mutation is forbidden unless an explicit, safe, operator-controlled source-delete toggle is enabled.
- Same-disk source/output/scratch configurations are supported but must be disclosed and guarded.
- Pending publish is a safety mechanism, not a failure by itself. Parked outputs are not final published outputs until drain/final-output evidence proves completion.
- Network mode in WebView remains read-only until lifecycle ownership, auth, cancellation, and recovery contracts are designed and tested.
- Command journal atomicity, strict JSON handling, duplicate-command guards, and backend close-readiness checks are release-critical.

## Media Policy Decisions

- Plex compatibility and Direct Stream/Direct Play friendliness are the guiding default, but not at the cost of blindly re-encoding good low-bitrate sources.
- H.264 sources should generally be remux-safe when bitrate/resolution/profile are reasonable.
- Size growth matters. Default policy should reject or review outputs that exceed source size by configured limits unless a forced/manual policy explicitly allows it.
- FFmpeg, ffprobe, stream mapping, HDR/SDR behavior, audio channel policy, and subtitle conversion are high-risk. Changes need targeted tests and real-media validation where possible.
- Original subtitle tracks are preserved by default unless a configured drop policy says otherwise.
- Preferred-language subtitle conversion to SRT is configurable. Unknown/und tags may be treated as probable English according to current operator preference.
- BDPGS/OCR failure should route to manual review instead of silent bad publish.
- ASS should be preserved unless configured to drop; generated SRT should strip styling according to negative filters when conversion is enabled.
- TX3G should be preserved where container-compatible; SRT may be added unless drop policy is enabled. Do not misbox incompatible subtitle formats into MP4.

## Rename Decisions

- Rename is a standalone tool, separate from Queue.
- Movie mode should show current source, scrubbed/pipeline prediction, editable final name, and a force-pipeline-name option.
- TV mode should support selected-order batch naming with show, season, start episode, and confidence-aware episode-title prediction.
- TV season source-of-truth order:
  - Explicit season/episode in file name wins.
  - Season in parent folder wins if file has episode but no season.
  - Special/OVA/OAD/extras folders map to `S00`.
  - If no season evidence exists, default to `S01`.
- Backend owns actual rename apply and sidecar updates. WebView readiness checks are guardrails, not authority.

## WebView/Tauri Transition Decisions

- WebView should prioritize operator trust: clear empty states, row details, current filter scope, hidden-risk warnings, command results, and backend evidence.
- Table display filters are local display controls only. They must not narrow backend launch, drain, apply, or repair scope.
- WebView command controls should expose command success/failure/pending feedback without forcing the operator to locate logs manually.
- Diagnostics should expose recent errors, allowlisted log tails, state artifact summaries, and owner-row navigation, but should not provide arbitrary filesystem access.
- Tauri shell checks prove shell/package readiness only. They do not prove media pipeline correctness.
- Representative real-media validation was operator-attested complete on 2026-05-28, and default-launcher/package-mode promotion was operator-confirmed complete on 2026-05-30. Future media-policy, FFmpeg, subtitle, audio, publish/drain, source/scratch/output movement, cleanup, launcher, package, Local API, or Tauri changes still require the matching validation ladder rung.

## Architecture And Refactor Decisions

- Avoid "architecture astronautics." A module split is useful only if it creates clear ownership, removes real coupling, or improves testability.
- Keep cohesive service modules; do not split into one-line pass-through files.
- Preserve compatibility shims during refactors.
- PowerShell remains appropriate for pipeline/tool orchestration and bundled runtime integration.
- Python remains appropriate for backend services, local API contracts, DTOs, state summaries, and testable orchestration around the WebView shell.
- Frontend JavaScript should not duplicate backend business rules beyond local preflight/readiness explanation.

## Documentation Decisions

- `CURRENT_PROJECT_STATE.md` is the first current-state read.
- `OPEN_WORK_CHECKLIST.md` is the active unresolved backlog.
- `DECISIONS_AND_HISTORY.md` preserves decision rationale from older long-form docs.
- `ARCHIVED_MD_INDEX.md` indexes old AI directives, completed checklists, and superseded reviews.
- `Docs/DOCS_INDEX.md` is the active documentation map. The 2026-05-20 quarantine root is `Docs/archive/docs-housekeeping/2026-05-20-review/`.
- Old Claude handoff files are not active direction unless explicitly reopened.
- Completed UI/control cleanup checklists are archive material.
- Large historical docs should be retained but not used as primary onboarding.

## Important Historical Milestones

- V5 was copied from working V4 so V4 could remain stable while V5 absorbed remediation and WebView/Tauri work; V6 was later split from V5 as the WebView-first workspace with the legacy desktop shell removed.
- Services were split incrementally from oversized Python modules while preserving existing behavior.
- Rename tool moved toward standalone movie/TV batch editing with backend-owned apply.
- Remux/encode routing gained more explicit size policy, profile, and settings visibility.
- Settings gained structured builder surfaces for high-impact controls.
- Diagnostics gained read-only allowlisted targets and bounded log tails.
- Queue, Completed, and Pending Publish gained row-level trust summaries, filter warnings, and backend-scope explanations.
- Browser and non-browser WebView smokes grew into a substantial no-mutation safety net.
- A selected-row render scroll bug caused Home, Completed, and Launch to snap downward; fixing `makeRowSelectable()` made render-time scrolling opt-in.

## Historical Docs Worth Preserving

- `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/historical-reviews/GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md`: archived detailed framework comparison and migration direction.
- `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/historical-reviews/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md`: archived original transition groundwork.
- `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/historical-plans/V5_TAURI_TRANSITION_CURRENT_PLAN_20260520_ARCHIVED.md`: historical long-form transition log and plan; current state is in `Docs/CURRENT_PROJECT_STATE.md`.
- `REMEDIATION_CHANGELOG.md`: detailed chronological remediation history.
- `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md`: module ownership and fragmentation concerns.
- `Docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/Docs/archive/admin-audits/MD_CLEANUP_AUDIT_REPORT.md`: old Markdown classification evidence retained as a quarantine-only delete candidate.

## Decisions That Are Not Final

- Which future changes justify a fresh package/open/close validation run after the promoted default-launcher state.
- Whether network coordinator/worker lifecycle controls belong in WebView.
- How much of the giant remediation changelog should be archived or indexed.
- Whether `node_modules` should remain in this working tree.
- Which raw settings keys deserve structured builder controls versus intentional advanced/raw handling.
- Whether old Claude transition handoffs still contain work not reflected in active docs.
