# Library Route Map Planning Pack

Date: 2026-06-07
Status: planning only
Change packet: MP-CHANGE-2026-0607-009

## Capability

Library Route Map gives the operator a visual and tabular answer to:

> For this library, what will MediaPipeline do to files, and why?

This is not a Tdarr-style plugin system and not an editable arbitrary flow
engine. It is a backend-authored map of existing MediaPipeline policy:
library profile inheritance, source roots, scratch behavior, route decision,
remux/encode handling, subtitle policy, audio policy, sidecars/manifests,
final publish, pending publish, and review outcomes.

## Placement Decision

The primary home should be the Libraries tab.

Reason:

- The operator is thinking in library/profile terms when asking "what happens
  to files from this library?"
- Library Profiles already own inheritance, source/output identity, promotion
  destinations, and override state.
- The route map can sit beside the existing Library Profile editor without
  implying that Queue, Launch, Diagnostics, or Completed owns policy.
- Later phases can link into the same map from Queue, Launch, Completed,
  Pending Publish, and Sample Validation, but those should be context links,
  not the primary editing surface.

Recommended Libraries tab layout:

| Panel | Purpose | Mutation Authority |
|---|---|---|
| Library Profile List | Select the profile/library to inspect. | Existing profile selection only. |
| Route Map | Graph-style path from source to publish/review. | Read-only in phases 1-3. |
| Decision Matrix | Table of conditions and outcomes. | Read-only in phases 1-3. |
| Node Evidence | Selected graph node evidence and source settings. | Read-only. |
| Profile Compare | Side-by-side diff between two profiles. | Read-only in phase 3. |
| Guided Policy Edit | Existing profile controls opened from graph nodes. | Backend Preview/Save only in phase 4. |
| Validation Handoff | Route branches tied to Launch and sample validation proof. | Read-only/copyable in phase 5. |

## Non-Goals

- No plugins.
- No community plugin marketplace.
- No user-authored JavaScript, PowerShell, or Python execution from the UI.
- No arbitrary graph execution.
- No loops, variables, custom branches, or custom node outputs.
- No WebView-owned media policy.
- No WebView filesystem mutation.
- No bypass around backend Preview/Save, command journal, publish/drain, or
  pending-publish safety.

## Common Route Shape

Every phase should keep the same basic mental model:

| Route Node | What It Shows | Backend Evidence |
|---|---|---|
| Library | Profile identity, designation, inheritance state. | `LibraryProfiles`, `library_profile_state`, metadata. |
| Source Roots | Movie/TV/source roots covered by the profile. | Saved config plus normalized profile evidence. |
| Scratch Copy | Source-copy-to-scratch boundary. | Pipeline safety policy and launch/preflight evidence. |
| Probe | ffprobe/media inspection boundary. | Probe payload, queue preview, diagnostics where available. |
| Decide | Remux vs encode decision. | Route threshold mode, size/bitrate evidence, codec/container evidence. |
| Remux | Direct-copy/remux path and stream handling. | Decide-stage result, FFmpeg command plan. |
| Encode | Encode path, target bucket, codec, size policy. | Effective profile settings, route bucket evidence. |
| Subtitles | Preserve originals and add preferred SRT when configured. | Subtitle settings/evidence and review state. |
| Audio | Passthrough/transcode/downmix policy. | Audio settings/evidence and review state. |
| Sidecars | Manifest, sidecar, proof artifacts. | Completed manifest and sidecar expectations. |
| Publish | Final destination and promotion rule. | Normalized promotion diagnostics. |
| Pending Publish | Parked output when final root is unsafe. | Pending-publish manifest/drain evidence. |
| Review | Manual review, blocked, stale, or unsafe outcomes. | Diagnostics, Completed, Sample Validation, command history. |

## Phase Files

- `PHASE_1_READ_ONLY_LIBRARY_ROUTE_MAP.md`
- `PHASE_2_SELECTED_FILE_DRY_RUN_TRACE.md`
- `PHASE_3_PROFILE_COMPARE_AND_DIFF.md`
- `PHASE_4_GUIDED_POLICY_EDITING.md`
- `PHASE_5_ROUTE_MAP_VALIDATION_HANDOFF.md`

## Phase Order

| Phase | Builds | Why It Comes Here |
|---|---|---|
| 1 | Read-only route map and decision matrix. | Lowest risk and establishes the shared backend DTO. |
| 2 | Selected-file dry-run trace. | Makes the map concrete for one file without adding mutation. |
| 3 | Profile comparison. | Helps tune library profiles before editing from graph nodes. |
| 4 | Guided editing of existing settings/profile fields. | Adds usefulness while preserving backend Preview/Save. |
| 5 | Launch/sample-validation handoff. | Turns the map into operational readiness evidence. |

## Required Boundaries

- Backend owns every route decision and every mutation-capable command.
- The WebView renders DTOs, stages existing settings/profile edits, and calls
  existing or new backend Preview/Save routes.
- The route map is evidence. It is not proof that a real file has already
  passed unless it reconciles to current Completed, Pending Publish,
  Diagnostics, and Sample Validation evidence.
- Any later change touching FFmpeg, subtitles, audio, publish/drain,
  source/scratch/output movement, or cleanup requires the high validation rung
  and renewed real-media validation.

## Open Questions

| Question | Default Recommendation |
|---|---|
| Should the graph be a separate tab or a panel inside Libraries? | Panel inside Libraries first. Add local subtabs only if the page becomes too dense. |
| Should the graph support drag/drop editing? | No. Use node actions that open existing backend-owned controls. |
| Should files outside the queue be traceable? | Not in phase 2. Start with selected queue/completed evidence only. |
| Should graph data be generated in WebView? | No. Generate a backend DTO; WebView renders it. |
| Should this replace Settings route/size controls? | No. It complements Settings and Library Profiles. |
