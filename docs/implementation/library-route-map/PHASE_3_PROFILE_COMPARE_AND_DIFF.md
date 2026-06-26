# Phase 3: Profile Compare And Diff

Date: 2026-06-07
Status: planning only
Change packet: MP-CHANGE-2026-0607-009

## Goal

Let the operator compare two library profiles and understand how their route
maps differ.

This phase answers:

- What does this library inherit from global Settings?
- Which overrides are explicit?
- Which route branches differ between two profiles?
- Would the same kind of file route differently in Movies versus TV?
- Which profile has missing, stale, or review-only evidence?

## User Promise

The operator can select two library profiles and see a structured diff of
sources, outputs, route decisions, subtitle/audio policy, publish behavior, and
validation evidence.

## Non-Goals

- No editing in this phase.
- No automatic merge.
- No copying settings between profiles.
- No profile creation/deletion.
- No media behavior change.

## Primary Surface

Libraries tab, as a local compare panel or subtab.

Recommended panels:

| Panel | Purpose |
|---|---|
| Profile Picker | Select base profile and comparison profile. |
| Route Difference Summary | High-level differences by domain. |
| Effective Settings Diff | Inherited versus explicit values. |
| Route Branch Diff | Branches that exist, differ, or are blocked. |
| Validation Coverage Diff | Which route branches have current proof. |

## Backend Contract

This phase can use the phase 1 route-map DTO client-side for display, but the
recommended implementation is still backend-authored:

```text
GET /api/libraries/route-map/compare?base=<profile-id>&compare=<profile-id>
```

Candidate payload:

```text
desktop_library_route_compare.v1
```

Minimum DTO shape:

| Field | Purpose |
|---|---|
| `schema` | Constant `desktop_library_route_compare.v1`. |
| `generated_at` | Backend timestamp. |
| `base_profile_id` | Base profile. |
| `compare_profile_id` | Comparison profile. |
| `summary_rows[]` | Domain-level difference summary. |
| `setting_rows[]` | Effective setting and override differences. |
| `branch_rows[]` | Route branch differences. |
| `validation_rows[]` | Current/stale/missing proof differences. |
| `warnings[]` | Ambiguous or unsupported comparison evidence. |

## Summary Table

Recommended summary:

| Domain | Same/Different | Base | Compare | Operator Meaning |
|---|---|---|---|---|
| Source Roots | Different | Movies root | TV root | Different library identity. |
| Route Threshold | Same | Inherited | Inherited | Same remux/encode trigger policy. |
| Size Targets | Different | Movie 1080p target | TV 1080p target | Same height may encode to different target. |
| Subtitles | Same | Preferred SRT | Preferred SRT | Same review expectation. |
| Publish | Different | Movies destination | TV destination | Final placement differs. |

## Effective Settings Diff

Recommended columns:

| Column | Purpose |
|---|---|
| Setting | Backend metadata label. |
| Domain | Routing, size, subtitles, audio, publish, safety. |
| Base Value | Effective value. |
| Base State | Inherited, explicit, default, missing. |
| Compare Value | Effective value. |
| Compare State | Inherited, explicit, default, missing. |
| Impact | Backend-authored explanation. |

## Route Branch Diff

Recommended columns:

| Column | Purpose |
|---|---|
| Branch | Remux, encode, subtitle review, audio review, publish, pending publish. |
| Base Outcome | Outcome under base profile. |
| Compare Outcome | Outcome under comparison profile. |
| Difference | Same, value changed, branch added, branch blocked. |
| Evidence | Backend evidence behind the diff. |

## UI Behavior

- Differences should be grouped by domain instead of shown as a raw key dump.
- Inherited values should not look like explicit overrides.
- Same-value explicit overrides should still be labeled explicit.
- Missing/unknown evidence should be treated as review, not as matching.
- The comparison should not stage any changes.

## Implementation Steps

1. Add backend compare builder over route-map DTOs and library effective state.
2. Add a compare panel to Libraries.
3. Render summary, settings diff, route branch diff, and validation diff.
4. Add tests for inherited same value, explicit same value, changed value,
   missing value, and designation-specific hidden fields.
5. Add browser no-mutation coverage for compare interactions.

## Validation

| Validation | Expected Result |
|---|---|
| Local API tests | Compare DTO handles same, changed, explicit, inherited, and missing values. |
| Library Profile tests | Existing inheritance and designation filtering remain unchanged. |
| WebView static tests | Compare panel has no save/apply controls. |
| Browser no-mutation smoke | Compare selection does not call mutation routes. |

Real-media validation is not required if the phase only compares backend
configuration/evidence and does not alter media behavior.

## Exit Criteria

- Operator can compare two profiles without editing either one.
- Differences are domain-oriented, not just raw config keys.
- Inherited and explicit states remain visible.
- Profile compare can explain route behavior differences before phase 4 adds
  guided editing.

## Rollback

Remove compare route, compare panel, tests, docs index entries, and change
packet references.
