# Phase 1: Read-Only Library Route Map

Date: 2026-06-07
Status: planning only
Change packet: MP-CHANGE-2026-0607-009

## Goal

Add a read-only Libraries tab surface that shows the operator how each library
profile routes files through MediaPipeline.

This phase answers:

- Which source roots belong to this library profile?
- What effective settings are inherited versus explicit?
- What route outcomes can happen?
- Which conditions send a file to remux, encode, pending publish, or review?
- Which backend evidence produced the displayed answer?

## User Promise

When an operator selects a library profile, they can see a route map and a
decision table that explain what MediaPipeline is configured to do before any
file is launched.

## Non-Goals

- No editing.
- No selected-file trace.
- No launch action.
- No new media processing behavior.
- No graph drag/drop.
- No plugin or custom node system.
- No WebView-owned policy calculations beyond display formatting.

## Primary Surface

Libraries tab.

Recommended local panels:

| Panel | Description |
|---|---|
| Route Map | A graph-style sequence of backend-authored nodes. |
| Decision Matrix | A table of route conditions and outcomes. |
| Node Evidence | Detail for the selected node, including settings and evidence source. |
| Safety Boundary | Compact reminder that the graph is read-only planning evidence. |

This can be implemented with tables first. A visual graph can be added after
the DTO and table semantics are stable.

## Backend Contract

Candidate route:

```text
GET /api/libraries/route-map
```

Candidate payload:

```text
desktop_library_route_map.v1
```

Minimum DTO shape:

| Field | Purpose |
|---|---|
| `schema` | Constant `desktop_library_route_map.v1`. |
| `generated_at` | Backend timestamp for stale-state display. |
| `profiles[]` | One route map per library profile. |
| `profiles[].profile_id` | Stable library profile identifier. |
| `profiles[].label` | Display label. |
| `profiles[].designation` | Movie, TV, auto, or unknown. |
| `profiles[].source_roots[]` | Normalized source-root evidence. |
| `profiles[].output_roots[]` | Normalized output/promotion evidence. |
| `profiles[].nodes[]` | Ordered route nodes. |
| `profiles[].edges[]` | Conditions between nodes. |
| `profiles[].decision_rows[]` | Table rows for operator scanning. |
| `profiles[].warnings[]` | Backend-authored warnings and review reasons. |

Node fields:

| Field | Purpose |
|---|---|
| `id` | Stable node ID within the profile map. |
| `kind` | `library`, `source`, `scratch`, `probe`, `decide`, `remux`, `encode`, `subtitle`, `audio`, `sidecar`, `publish`, `pending_publish`, or `review`. |
| `label` | Short display label. |
| `summary` | Backend-authored plain-language summary. |
| `status` | `ok`, `inherited`, `explicit`, `review`, `blocked`, `unknown`. |
| `evidence[]` | Source keys, route evidence, config keys, or state artifacts. |
| `settings[]` | Relevant settings and override state. |

Edge fields:

| Field | Purpose |
|---|---|
| `from` | Source node ID. |
| `to` | Destination node ID. |
| `condition` | Backend-authored condition label. |
| `status` | `available`, `blocked`, `review`, or `unknown`. |
| `evidence[]` | Reasons the edge exists. |

## Decision Matrix

The first version can be table-first:

| Column | Example |
|---|---|
| Step | Decide |
| Condition | H.264 direct-copy advisory passes |
| Outcome | Remux/direct-copy |
| Evidence | `RouteThresholdMode=compatibility_advisory` |
| Source | Library override inherited from global Settings |
| Risk | OK |
| Next Review | None |

The table should be generated from the same backend DTO as the graph. The UI
should not build route rules independently.

## UI Behavior

- Selecting a library profile updates the route map, decision matrix, and node
  evidence.
- Selecting a route node highlights related decision rows.
- Selecting a decision row highlights the related graph edge.
- Inherited settings are visually distinct from explicit overrides.
- Unknown or blocked evidence is visible before launch.
- Empty state should say there is no backend route-map evidence yet, not that
  the library is safe.

## Implementation Steps

1. Add a backend route-map DTO builder from existing Library Profile state,
   Settings metadata, promotion diagnostics, and known route-policy settings.
2. Add a read-only Local API route for the DTO.
3. Add Libraries tab panels for route map, decision matrix, and node evidence.
4. Render the first version as tables and simple connected blocks.
5. Add static tests proving the Libraries tab contains no mutation controls in
   read-only panels.
6. Add route tests proving the DTO is strict JSON and backend-authored.

## Validation

Minimum validation for this docs-planned phase when implemented:

| Validation | Expected Result |
|---|---|
| Targeted Local API route tests | `GET /api/libraries/route-map` returns strict DTO. |
| WebView static tests | Route-map evidence panels expose no buttons or POST calls. |
| Library Profile tests | Inherited/explicit state remains accurate. |
| Browser no-mutation smoke | Viewing route map does not call mutation routes. |

No real-media validation is required if this phase only displays existing
backend policy and does not change FFmpeg, subtitle, audio, publish, drain, or
file movement behavior.

## Exit Criteria

- Libraries tab shows a read-only route map for each profile.
- Every graph/table statement has backend evidence.
- The UI does not invent media policy.
- No backend mutation route is added.
- Docs, route inventory, and change packet are updated.

## Rollback

Remove the new route-map Local API route, WebView panels, tests, docs index
entries, and change packet references. No media state rollback should be needed
because phase 1 is read-only.

