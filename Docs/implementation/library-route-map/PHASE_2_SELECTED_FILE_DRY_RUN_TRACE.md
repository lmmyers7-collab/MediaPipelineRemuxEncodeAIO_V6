# Phase 2: Selected-File Dry-Run Trace

Date: 2026-06-07
Status: planning only
Change packet: MP-CHANGE-2026-0607-009

## Goal

Let the operator pick an existing file row and see the route path that file
would take through the Library Route Map.

This phase answers:

- Which library profile applies to this file?
- Which route-map branch does the file follow?
- What evidence makes it remux, encode, publish, park, or review?
- Which proof is missing before the operator should trust the outcome?

## User Promise

When an operator selects a Queue, Completed, or sample-validation file row, the
Libraries tab can highlight the matching route path and show a step-by-step
dry-run trace without launching work or mutating media.

## Non-Goals

- No arbitrary path probing from the WebView.
- No direct filesystem reads from WebView.
- No launch.
- No publish/drain.
- No repair.
- No manifest rewrite.
- No "try this file now" mutation command.

## Primary Surface

Libraries tab remains primary.

Context entry points can be added from:

| Source Page | Behavior |
|---|---|
| Queue | "View route trace" selects the matching library profile and trace row. |
| Launch | Read-only route trace for the selected launch scope/sample. |
| Completed | Read-only post-run trace comparison when completed evidence exists. |
| Sample Validation | Link accepted/review sample category back to route branches. |

The route trace detail itself should live on Libraries so route interpretation
does not drift into Queue or Launch.

## Backend Contract

Candidate route:

```text
GET /api/libraries/route-map/trace?id=<backend-row-id>&source=<queue|completed|sample_validation>
```

Alternative if the request becomes too structured for query parameters:

```text
POST /api/libraries/route-map/trace-preview
```

If POST is used, it must be preview-only, command-journaled if project
conventions require it, and explicitly documented as non-mutating.

Candidate payload:

```text
desktop_library_route_trace.v1
```

Minimum DTO shape:

| Field | Purpose |
|---|---|
| `schema` | Constant `desktop_library_route_trace.v1`. |
| `generated_at` | Backend timestamp. |
| `source` | Queue, Completed, or Sample Validation. |
| `source_id` | Backend row ID. |
| `profile_id` | Matched library profile ID. |
| `profile_match_status` | `matched`, `ambiguous`, `missing`, or `unknown`. |
| `highlighted_nodes[]` | Route-map node IDs this file follows. |
| `highlighted_edges[]` | Route-map edge IDs this file follows. |
| `steps[]` | Ordered trace rows. |
| `warnings[]` | Missing proof, stale evidence, review blockers. |

Trace step fields:

| Field | Purpose |
|---|---|
| `step` | Human-readable route step. |
| `node_id` | Matching route-map node. |
| `condition` | Condition checked. |
| `input_evidence` | Probe, settings, queue, or completed evidence used. |
| `decision` | Backend-authored result. |
| `confidence` | `current`, `stale`, `review`, `blocked`, or `unknown`. |
| `next_action_owner` | Libraries, Launch, Completed, Pending Publish, Diagnostics, or operator playback. |

## Trace Table

Recommended table:

| Step | Condition | Evidence | Decision | Confidence | Owner |
|---|---|---|---|---|---|
| Library match | Path under Movies source root | Normalized source root | Movie profile | Current | Libraries |
| Decide | Codec/container pass direct-copy policy | ffprobe + settings | Remux | Current | Launch |
| Subtitles | Preferred-language SRT required | Saved subtitle policy | Add SRT or review | Review | Completed |
| Publish | Final root reachable | Preflight/publish evidence | Publish or park | Unknown | Pending Publish |

## Data Source Rules

Start with already-known backend evidence:

- Queue rows and queue preview.
- Completed rows and completed manifest evidence.
- Pending Publish rows and durable drain summary where loaded.
- Sample Validation records and current/stale reconciliation.
- Existing probe/decide evidence if present.

Do not add arbitrary "browse a file and probe it" behavior in phase 2. That
would raise file-access and validation scope.

## UI Behavior

- Selecting a trace highlights matching route-map nodes and edges.
- If the library profile cannot be matched, the graph stays unhighlighted and
  the trace shows `missing` or `ambiguous`.
- Stale evidence is visually different from current evidence.
- The trace must distinguish "would happen by policy" from "did happen in a
  completed run."
- No trace result should imply that output acceptance is safe without current
  Completed, Pending Publish, Diagnostics, playback, and Sample Validation
  evidence where relevant.

## Implementation Steps

1. Add backend matching from queue/completed/sample rows to library profile IDs.
2. Add a trace DTO that references phase 1 route-map node/edge IDs.
3. Add Libraries tab trace panel and row highlighting.
4. Add context links from Queue and Launch only after the Libraries route trace
   can render from a direct URL/state selection.
5. Add tests for missing, ambiguous, stale, and current evidence cases.

## Validation

| Validation | Expected Result |
|---|---|
| Local API tests | Trace route returns strict DTO for queue/completed/sample IDs. |
| WebView static tests | Context links do not add mutation calls. |
| Browser no-mutation smoke | Selecting trace rows does not POST to launch, publish, drain, repair, rename, or settings save. |
| Existing sample-validation tests | Current/stale/review labeling remains accurate. |

Real-media validation is not required if phase 2 only traces existing evidence
and does not alter media behavior.

## Exit Criteria

- A selected existing file row can highlight the route map.
- Trace rows are backend-authored.
- The UI separates predicted route from completed proof.
- Missing/stale evidence is visible and not treated as success.

## Rollback

Remove trace DTO route, Libraries trace panel, context links, tests, docs index
entries, and change packet references. No media rollback should be needed.

