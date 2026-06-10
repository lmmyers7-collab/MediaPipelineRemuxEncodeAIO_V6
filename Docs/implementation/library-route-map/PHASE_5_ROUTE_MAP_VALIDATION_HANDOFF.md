# Phase 5: Route Map Validation Handoff

Date: 2026-06-07
Status: planning only
Change packet: MP-CHANGE-2026-0607-009

## Goal

Connect the Library Route Map to operational readiness evidence so the operator
can see which route branches have current proof and which branches need pilot
validation before trust.

This phase makes the route map useful during Launch, Completed review, Pending
Publish review, and Sample Validation without turning it into an executable
flow builder.

## User Promise

For a selected library profile, the operator can see whether each important
route branch has current accepted evidence, stale evidence, review evidence, or
no evidence.

## Non-Goals

- No launch button on the route map.
- No pending-publish drain button on the route map.
- No output acceptance button on the route map.
- No repair/reconcile mutation controls.
- No automatic validation record append.
- No plugin system.
- No custom executable flow DSL.

## Primary Surface

Libraries tab remains primary.

Supporting links can appear on:

| Page | Link Purpose |
|---|---|
| Launch | Show route branches covered by the selected launch scope. |
| Completed | Show whether the selected output reconciles to a route branch. |
| Pending Publish | Show deferred-publish branch proof and drain review state. |
| Diagnostics | Point first-response rows back to route-map branch owners. |
| Sample Validation | Map accepted/current sample categories to route branches. |

## Backend Contract

Candidate route:

```text
GET /api/libraries/route-map/validation
```

Candidate payload:

```text
desktop_library_route_validation.v1
```

Minimum DTO shape:

| Field | Purpose |
|---|---|
| `schema` | Constant `desktop_library_route_validation.v1`. |
| `generated_at` | Backend timestamp. |
| `profiles[]` | Validation roll-up by library profile. |
| `profiles[].profile_id` | Profile being evaluated. |
| `profiles[].branch_rows[]` | Required/recommended route branch proof rows. |
| `profiles[].sample_rows[]` | Matching sample-validation records. |
| `profiles[].completed_rows[]` | Matching completed-output proof. |
| `profiles[].pending_publish_rows[]` | Matching pending/drain proof. |
| `profiles[].diagnostic_rows[]` | Diagnostic blockers or warnings. |
| `profiles[].readiness` | Overall `ready`, `review`, `blocked`, or `unknown`. |

Branch row fields:

| Field | Purpose |
|---|---|
| `branch` | Remux, encode-size, subtitle, audio, deferred-publish, final-publish, review. |
| `required` | Whether this branch is required for current operator trust. |
| `route_node_ids[]` | Matching phase 1 route-map nodes. |
| `proof_status` | `current`, `stale`, `review`, `blocked`, `missing`, or `not_applicable`. |
| `evidence[]` | Sample, Completed, Pending Publish, Diagnostics, or command evidence. |
| `next_owner` | Page or operator action that owns the next review. |

## Validation Handoff Table

Recommended table:

| Branch | Required | Proof Status | Evidence | Next Owner |
|---|---|---|---|---|
| H.264 remux/direct-copy | Yes | Current | Accepted sample + Completed proof | Completed |
| Encode/size policy | Yes | Stale | Historical sample only | Launch pilot |
| Preferred subtitle to SRT | Yes | Review | Missing manual subtitle playback check | Operator playback |
| Audio routing/default language | Yes | Missing | No accepted current sample | Sample Validation |
| Deferred publish | Conditional | Current | Pending manifest + drain summary | Pending Publish |

## UI Behavior

- Route-map branches should display proof status without implying readiness
  from route policy alone.
- Clicking a validation row highlights the route-map branch and opens evidence
  detail.
- The route map can offer copyable checklists, but must not append records or
  mutate state.
- Current, stale, review, blocked, missing, and not-applicable states must be
  visually distinct.
- Launch page can summarize branch proof, but Libraries remains the map owner.

## Operational Meaning

Phase 5 should make the following distinction obvious:

| Statement | Meaning |
|---|---|
| Policy says this branch exists. | The saved profile can route files this way. |
| Dry-run trace follows this branch. | A selected file appears to match that route. |
| Current proof exists for this branch. | Recent accepted evidence reconciles to backend proof. |
| Branch is ready for trust. | Required current proof is present and no blockers are active. |

The UI should avoid collapsing these into a single "ready" label.

## Implementation Steps

1. Add backend branch-to-proof reconciliation using existing Sample Validation,
   Completed, Pending Publish, Diagnostics, and command evidence.
2. Add Libraries validation handoff panel.
3. Add route-map branch proof badges sourced from backend validation rows.
4. Add Launch summary links that reference route-map branch status.
5. Add browser no-mutation coverage for validation handoff interactions.
6. Add docs/runbook updates explaining that route-map validation evidence is
   read-only and does not replace real-media validation after policy changes.

## Validation

| Validation | Expected Result |
|---|---|
| Local API tests | Validation DTO classifies current/stale/review/missing proof correctly. |
| Sample Validation tests | Existing current/stale reconciliation remains authoritative. |
| Completed/Pending tests | Missing output, parked output, and drain proof keep distinct states. |
| WebView static tests | Validation handoff has no launch/drain/accept/repair buttons. |
| Browser no-mutation smoke | Route-map validation interactions do not POST mutation commands. |

If this phase only reconciles existing evidence, real-media validation is not
required. If branch requirements or media behavior change, use the high
validation rung and rerun representative real-media validation.

## Exit Criteria

- Route branches show validation proof status.
- Launch can reference the route-map validation roll-up without owning it.
- Completed/Pending/Sample Validation evidence remains authoritative.
- No mutation controls are added to the route map.
- No plugin or custom executable flow behavior is introduced.

## Rollback

Remove validation DTO route, Libraries validation panel, route-map proof badges,
Launch links, tests, docs index entries, and change packet references.

