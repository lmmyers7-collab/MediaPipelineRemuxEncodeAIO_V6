# Decisions And History

Last updated: 2026-06-24

This document preserves durable decisions and historical context without requiring future agents to read every old checklist, audit, or handoff file.

## Current Direction

- This is the active promoted WebView/Tauri workspace.
- The external rollback workspace remains the rollback/fallback workspace and should not be modified from current-workspace work.
- The legacy desktop shell and removed root launcher shims are not active current surfaces; do not treat old desktop-shell fallback or root-launcher instructions as active guidance.
- Tauri/WebView2 is the preferred long-term shell direction over PySide6/Qt for this project because it gives a modern operator interface, stronger table/layout ergonomics, and a clearer backend/frontend boundary while keeping the existing Python/PowerShell backend alive.
- Migration must stay adapter-based and incremental. Do not move backend-owned mutation authority into the frontend.

## Safety Decisions

- Backend owns mutation. Frontend code may stage, preview, display warnings, and post command requests, but it must not directly mutate files, config, queue state, pending publish state, or media artifacts.
- Source media must be copied to scratch before processing. Source mutation is forbidden unless an explicit, safe, operator-controlled source-delete toggle is enabled.
- Same-disk source/output/scratch configurations are supported but must be disclosed and guarded.
- Pending publish is a safety mechanism, not a failure by itself. Parked outputs are not final published outputs until drain/final-output evidence proves completion.
- Network lifecycle/setup controls are backend-owned Local API routes. WebView may call provider-guarded coordinator/worker dry-run, start/stop, test-connection, discovery, and join/import routes, but it must not implement lifecycle, queue, claim, done-report, settings-save, publish, rename, or media mutation logic itself.
- Command journal atomicity, strict JSON handling, duplicate-command guards, and backend close-readiness checks are release-critical.

## Product-Integration Decisions (2026-07-11)

### PI-001: SQLite remains a rebuildable observability mirror

Decision: retain `State\mediapipeline_state.sqlite3` as an optional,
best-effort observability index for bounded command-event history, queue
dry-run snapshots, completed-manifest mirrors, and diagnostics health. JSON
state, manifests, and journals remain authoritative for every operator action
and lifecycle decision.

Evidence: `src/mediapipeline/core/storage/db.py` writes the four mirror tables
opportunistically, applies schema migrations, bounds completed rows, and keeps
maintenance failures from changing the outcome of authoritative writes. The
runtime artifact inventory explicitly excludes SQLite from queue scope,
completed acceptance, pending-publish drain, command-history rendering, and
recovery authority.

Alternatives considered: retiring it now would remove an existing bounded
diagnostic index without simplifying any authoritative state flow. Promoting it
to a primary store would require a broad migration and is rejected because it
would introduce a second mutable authority.

Consequences and rollback: existing database files are never deleted
automatically. A database may be ignored if unavailable or incompatible; JSON
remains usable. Any future rebuild/migration needs a separately gated dry-run
comparison against authoritative JSON before implementation.

### PI-002: Python stage dispatcher is a narrow boundary, not the media engine

Decision: retain the dispatcher as a supported probe/decision plus narrowly
guarded scratch-mutation boundary. `probe` and `decide` are read-only. Guarded
`ingest` may only perform its separately validated source-to-scratch copy.
Guarded `rename` may only rename one regular file within a dispatcher-allowed
scratch root that is disjoint from all dispatcher-protected source roots;
payload roots must match that trusted runner configuration. It excludes sidecars, directory moves,
extension changes, overwrite, source/output/final-library paths, and any Local
API or frontend route. Guarded `subtitle-convert` may only turn one standalone
scratch `.ass`/`.ssa` artifact into one new sibling `.srt`, using the existing
Python parser/filter/renderer with fixed conservative policy. It excludes
TX3G extraction, BDPGS OCR, embedded streams, language routing, container or
source mutation, output overwrite, publish integration, and any Local API or
frontend route. Transcode, audio, publish, drain, final
placement, and source movement remain disabled in the dispatcher. The
PowerShell engine remains the production owner of encode/remux/subtitle/audio/
publish mutation, integrated naming, and real-media policy.

The 2026-07-11 next-stage audit found no remaining stage that can be honestly
bounded with temporary fixtures alone. The disabled contracts now carry stable
machine-readable blocker codes and validation gates:

| Stage | Blocker | Minimum unlock evidence |
| --- | --- | --- |
| `transcode` | `production_ffmpeg_policy_parity_and_real_media_required` | PowerShell unit/reliability and tool checks, representative encode and remux media, stream-mapping parity, failed-attempt cleanup, and recovery parity. |
| `audio-mix` | `production_audio_policy_parity_and_multi_audio_real_media_required` | Profile-driven passthrough/transcode/downmix/default-language parity plus representative multi-audio validation. |
| `publish` | `manifest_publish_transaction_parity_and_real_media_required` | Partial-copy/reveal, sidecar rollback, pending-park/recovery, final-placement proof, and representative publish validation. |
| `drain` | `pending_manifest_transaction_parity_and_deferred_publish_real_media_required` | Trusted-manifest, attempt-state, copy/hash, sidecar rollback, crash recovery, fixture, and representative deferred-publish-to-drain validation. |

These are review dispositions, not placeholders for generic execution. A
future change must clear one complete row before changing that stage's
`execution_backend`; temporary fixtures cannot establish production parity.

Evidence: `STAGE_REGISTRY` identifies the PowerShell and Python dispatcher
backends; the runner rejects disabled stages before spawning or mutation.
Ingest execute requires strict confirmation, operation identity, a scratch
reservation, matching dry-run fingerprint, journaling, source-unchanged proof,
and recovery evidence. Rename execute requires strict boolean confirmation, a
UUID operation identity, matching content-bound dry-run fingerprint, strict
command and duplicate-operation journals, trusted scratch/source-root boundary checks,
no-overwrite behavior, content-hash equality, and a scratch-local undo record.
Focused temporary-fixture tests prove absent confirmation, source-root overlap,
outside-scratch targets, untrusted root declarations, stale fingerprints, and missing command journals fail
closed, and terminal-evidence failure rolls the scratch rename back.
Subtitle-convert has the same trusted-root, strict confirmation, fingerprint,
command/operation journal, duplicate replay, and no-overwrite gates. Temporary
representative ASS fixtures prove dry-run parsing, deterministic SRT output,
input-hash preservation, review routing for no-dialogue input, unsafe-path
rejection, and output rollback when terminal evidence cannot commit.

Consequences and rollback: the Python rename and standalone subtitle executors
are validation-only infrastructure and do not change production pipeline
routing. Their recovery records and immediate rollback cover the bounded
scratch mutations; removing either Python backend registration disables that
stage without changing PowerShell behavior. This
avoids a shadow-engine cutover claim and keeps existing PowerShell real-media
validation valid. A genuine cutover would be a separate phased migration with
policy parity, rollback, and representative real-media gates; it is not
authorized by this decision.

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

## Deferred Remediation Decisions

These entries resolve deferred remediation choices before any further
media-policy or pipeline implementation work. They are design authority only;
behavior changes still require their own high-risk change packet, validation
evidence, and rollback plan.

### FR-016: Multi-video Stream Policy

Decision: preserve all real video streams. Multi-angle, PiP, or alternate-video
sources must not be reduced to the first/primary video stream merely because
the file has more than one real video stream. Attached pictures and cover art
are not real video streams for this policy.

Rejected alternatives:

- Primary-only-with-evidence would make outputs easier to reason about, but it
  deliberately discards source content and creates an operator-trust problem
  for bonus-angle and commentary material.
- Block/review is safer than silent stream loss, but it over-blocks sources
  where the command topology can preserve every real video stream and where
  output proof can verify the result.

Required FFmpeg topology:

- Remux topology must map all real video streams with `-map 0:V`, copy video
  with `-c:v copy`, preserve eligible audio/subtitle/attachment/chapter/metadata
  inputs according to the existing policy, and verify source/output real-video
  stream counts before publish.
- Encode topology must use the same `-map 0:V` default when no explicit video
  filter graph is present, apply the selected video encoder flags across the
  mapped real-video outputs, preserve eligible non-video streams according to
  the existing audio/subtitle policy, and verify source/output real-video
  stream counts before publish.
- Subtitle burn-in on multi-video sources must fail closed unless a future
  filter graph can prove one filtered output per real source video stream.

Validation implications: any implementation or future change to this policy is
a high-risk FFmpeg/media-policy change. It needs command-topology tests, output
real-video count verification, representative real-media or generated-media
proof for at least a two-real-video source, and the recurring real-media rerun
gate when broader media behavior changes. The targeted proof should report
source/remux/encode counts, for example `source=2 remux=2 encode=2`.

### FR-042: CSV Rerun DryRun Semantics

Decision: evidence-writing `-DryRun` is intentional, and a separate no-write
`-PlanOnly` mode is required. `-DryRun` may create rerun evidence such as
manifest/staging metadata needed to inspect an executable rerun plan; it must
not be advertised as a no-write planner. `-PlanOnly` is the only CSV rerun mode
that may be used when the operator or tests require no `LocalBase`, output,
stage, park, manifest, temp-config, source, or media writes.

Rejected alternatives:

- Redefining `-DryRun` as no-write would erase the existing evidence-writing
  contract and risk breaking operator diagnostics that rely on dry-run
  manifests.
- Keeping only evidence-writing `-DryRun` would leave no supported way to
  inspect CSV rerun resolution without creating runtime state.

Required command contract:

- `-DryRun` and `-PlanOnly` are mutually exclusive.
- `-PlanOnly` must exit before rerun manifest creation, rerun queue/stage
  directory creation, rerun park/output directory creation, temp config writes,
  nested pipeline launch, and any source-media movement.
- Backend and WebView surfaces must carry plan-only intent separately from
  dry-run intent and must not treat dry-run success as proof that no files were
  written.

Validation implications: temp-LocalBase tests must prove `-PlanOnly` creates
no `LocalBase`, `Outsource`, `RerunManifests`, `RerunQueue`, or `RerunParked`
paths and leaves the representative source path in place. API/WebView launch
tests must prove plan-only and dry-run request fields stay distinct and reject
conflicting requests.

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
- `docs/OPEN_WORK_CHECKLIST.md` is the active unresolved backlog.
- As of 2026-07-20, neither active status document carries completed-work
  narratives. Current state, unresolved work, completed change history, durable
  decisions, and archived evidence remain separate authority surfaces.
- `DECISIONS_AND_HISTORY.md` preserves decision rationale from older long-form docs.
- `ARCHIVED_MD_INDEX.md` indexes old AI directives, completed checklists, and superseded reviews.
- `docs/DOCS_INDEX.md` is the active documentation map. The 2026-05-20 quarantine root is `docs/archive/docs-housekeeping/2026-05-20-review/`.
- Old Claude handoff files are not active direction unless explicitly reopened.
- Completed UI/control cleanup checklists are archive material.
- Large historical docs should be retained but not used as primary onboarding.

## Important Historical Milestones

- The 2026-07-20 active-status consolidation removed closed promotion gates,
  completed remediation narratives, duplicated architecture/validation rules,
  and stale counts from the two onboarding status docs. Existing changelog,
  decision, review, validation, change-packet, and archive surfaces retain the
  historical evidence; legacy checklist anchors remain available where
  practical.
- The current WebView-first workspace was split from the previous remediation workspace after it absorbed WebView/Tauri work, while older fallback evidence remained stable.
- Services were split incrementally from oversized Python modules while preserving existing behavior.
- Rename tool moved toward standalone movie/TV batch editing with backend-owned apply.
- Remux/encode routing gained more explicit size policy, profile, and settings visibility.
- Settings gained structured builder surfaces for high-impact controls.
- Diagnostics gained read-only allowlisted targets and bounded log tails.
- Queue, Completed, and Pending Publish gained row-level trust summaries, filter warnings, and backend-scope explanations.
- Browser and non-browser WebView smokes grew into a substantial no-mutation safety net.
- A selected-row render scroll bug caused Home, Completed, and Launch to snap downward; fixing `makeRowSelectable()` made render-time scrolling opt-in.

## Historical Docs Worth Preserving

- `docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/historical-reviews/GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md`: archived detailed framework comparison and migration direction.
- `docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/historical-reviews/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md`: archived original transition groundwork.
- Archived historical transition plan: historical long-form transition log and plan; current state is in `docs/CURRENT_PROJECT_STATE.md`.
- `docs/REMEDIATION_CHANGELOG.md`: compact authoritative index into the
  mechanically preserved detailed remediation history under
  `docs/archive/remediation-changelog/`.
- `CHANGELOG.md`: canonical notable-change history.
- `docs/ARCHIVED_MD_INDEX.md`: archive inventory and active-status historical
  evidence routing.
- Archived module ownership addendum: module ownership and fragmentation concerns.
- `docs/archive/docs-housekeeping/2026-05-20-review/delete-candidates/docs/archive/admin-audits/MD_CLEANUP_AUDIT_REPORT.md`: old Markdown classification evidence retained as a quarantine-only delete candidate.

## Decisions That Are Not Final

- Whether `node_modules` should remain in this working tree.
