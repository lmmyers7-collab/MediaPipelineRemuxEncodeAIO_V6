# Phase 4: Guided Policy Editing

Date: 2026-06-07
Status: planning only
Change packet: MP-CHANGE-2026-0607-009

## Goal

Let the operator open existing Library Profile controls from route-map nodes
and stage changes through the existing backend Preview/Save authority.

This phase turns the route map from read-only explanation into a guided entry
point for existing profile settings. It still does not create a custom flow
engine.

## User Promise

When an operator sees a route-map node such as Encode, Subtitles, Audio, or
Publish, they can jump to the relevant existing Library Profile controls,
stage a change, preview backend impact, and save only through the backend-owned
settings/profile save path.

## Non-Goals

- No new persisted config keys unless a separate architecture review approves
  them.
- No graph drag/drop.
- No arbitrary branch creation.
- No custom scripts.
- No plugins.
- No WebView-owned media policy.
- No direct file or media mutation.

## Primary Surface

Libraries tab.

Recommended behavior:

| Route Node | Guided Action |
|---|---|
| Decide | Open route threshold and size/bitrate controls for this profile. |
| Encode | Open codec, container, ladder, size target, and growth tolerance controls. |
| Subtitles | Open subtitle profile controls that are already library-overridable. |
| Audio | Open audio controls that are already library-overridable. |
| Publish | Open source/output/promotion controls owned by Library Profiles. |
| Pending Publish | Show read-only publish safety evidence; do not add drain controls here. |
| Review | Link to Diagnostics, Completed, or Sample Validation evidence owner. |

## Backend Contract

This phase should reuse the existing Library Profile staging and Preview/Save
contracts where possible.

If a new helper route is needed, keep it preview-only:

```text
POST /api/libraries/route-map/edit-preview
```

Candidate payload:

```text
desktop_library_route_edit_preview.v1
```

Minimum DTO shape:

| Field | Purpose |
|---|---|
| `schema` | Constant `desktop_library_route_edit_preview.v1`. |
| `profile_id` | Target library profile. |
| `node_id` | Route-map node the operator edited from. |
| `staged_patch` | Existing LibraryProfiles patch shape. |
| `preview_status` | `ok`, `review`, `blocked`, or `invalid`. |
| `changed_settings[]` | Backend-authored changed setting rows. |
| `route_impact[]` | Backend-authored route-map impact rows. |
| `validation_errors[]` | Backend validation errors. |
| `warnings[]` | Safety and validation warnings. |

The final save must remain the same backend-owned Library Profiles save path
used by existing settings/profile workflows.

## Guided Edit Table

Recommended staged-impact table:

| Setting | Current | Staged | State | Route Impact | Backend Result |
|---|---|---|---|---|---|
| Route threshold mode | Inherited compatibility advisory | Explicit size-or-bitrate | Explicit override | More files may encode | Preview OK |
| TV 1080p target | Inherited 2.0 GB | Explicit 1.6 GB | Explicit override | Smaller target for TV 1080p encodes | Preview OK |
| Subtitle policy | Inherited preferred SRT | Inherited preferred SRT | No change | No route impact | Not staged |

## UI Behavior

- Clicking a route node can scroll/open the relevant existing Library Profile
  section.
- Controls must retain existing inherited/explicit/reset behavior.
- Staged changes must show as staged, not saved.
- Backend Preview must be required before Save if existing workflow requires it.
- Save must go through backend validation and existing command/route handling.
- The route map can re-render a preview impact, but it must label preview
  state separately from saved state.

## Safety Rules

- A graph node does not own the setting. It is only a navigation shortcut.
- If a setting is not currently library-overridable, the graph may explain it
  but must not make it editable.
- If a setting is global-only, link to Settings or show read-only evidence.
- If a setting affects high-risk media behavior, save can stage the config
  change but the docs and UI should remind the operator that representative
  real-media validation becomes stale after behavior changes.

## Implementation Steps

1. Map route nodes to existing Library Profile control groups.
2. Add route-node "edit existing setting" actions only for editable nodes.
3. Preserve existing Library Profile override collection and reset behavior.
4. Add backend preview impact rows for staged profile edits if current preview
   payloads do not already provide enough evidence.
5. Add tests that graph-opened controls stage the same patch as direct Library
   Profile controls.
6. Add no-mutation browser coverage for preview-only actions and save-boundary
   coverage for explicit saves.

## Validation

| Validation | Expected Result |
|---|---|
| Library Profile unit/static tests | Existing inherited, explicit, reset, designation filtering still pass. |
| Local API Preview/Save tests | Invalid staged edits are rejected by backend. |
| WebView static tests | Route map does not add independent settings persistence. |
| Browser smoke | Node-guided edit stages same patch as direct edit. |
| Change-control validation | Any touched files are covered by the change packet. |

If this phase changes only UI staging and existing backend validation, real-media
validation may not be needed. If it changes route policy behavior, FFmpeg
arguments, subtitle behavior, audio behavior, publish/drain, or file movement,
use the high validation rung and rerun representative real-media validation.

## Exit Criteria

- Route-map nodes can open existing profile controls.
- Staged edits use existing LibraryProfiles patch behavior.
- Preview/Save remains backend-owned.
- Unsupported settings stay read-only.
- No plugin/custom-flow/executable graph behavior is introduced.

## Rollback

Remove route-node edit actions, preview-impact helpers if added, tests, docs
index entries, and change packet references. Existing Library Profile controls
should continue to work as before.

