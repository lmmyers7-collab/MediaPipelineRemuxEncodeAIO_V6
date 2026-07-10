# Libraries Tab Deep Review — 2026-07-09

Scope: read-only audit of the Libraries tab, `LibraryProfiles` normalization/inheritance, settings preview/save, JSON-authority projection, PowerShell consumers, route-map/summary APIs, configuration-key documentation, and tests. No settings were saved, no mutation route was invoked, and no media or source/output path was touched.

## Executive assessment

The Libraries tab has a sound command boundary: browser edits remain staged, route-map and summary reads are backend-authored evidence, and all persistence is delegated to the shared settings Preview/Save workflow. The backend independently rebuilds the candidate, validates registered keys and overrides, binds save to a backend recomputed review digest, requires strict `confirm_save: true`, and writes JSON authority plus a round-tripped PSD1 projection atomically. Staged frontend data therefore cannot bypass backend preview, validation, review confirmation, or strict-save handling.

There are **no P0 findings**. Two **P1** findings affect path/promotion safety, one **P2** documentation-disclosure finding, and one **P3** regression-coverage finding. The P1 items should be addressed before relying on Library Profile edits for production path or final-library-promotion policy changes.

| Priority | Count | Finding IDs |
|---|---:|---|
| P0 | 0 | None |
| P1 | 2 | CSW-2026-07-09-LIBRARIES-001, CSW-2026-07-09-LIBRARIES-002 |
| P2 | 1 | CSW-2026-07-09-LIBRARIES-003 |
| P3 | 1 | CSW-2026-07-09-LIBRARIES-004 |

## Workflow traces

### 1. Saved summary and route-map load

`page-libraries.html` hosts separate summary, editor, watch, and route-map regions. `settingsLibraries.js` renders the saved library summary; the explicit **Scan Sources** control delegates to Queue scan rather than making the summary GET mutate state. The saved summary path is:

```text
GET /api/libraries/summary
  -> LocalApiLibrariesReadPayloadMixin
  -> LibraryRouteMapFacadeMixin.get_library_summary
  -> build_library_summary(saved resolved.config_data, existing scan artifacts)
```

`build_library_summary()` is marked `read_only`, `mutation_enabled: false`, and only reads existing Queue source-inventory/scan-status artifacts. It reports missing, partial, or failed evidence rather than inventing counts.

Route-map, trace, compare, and validation handoff use the same saved resolved configuration via GET routes. `librariesRouteMap.js` clearly labels its rows as saved backend evidence; while the editor is dirty or staged it displays that the route map is not reflecting those edits. The API inventory and route-ownership map correctly classify all five Libraries GET routes as `effect: none` / read-only evidence.

### 2. Profile create, edit, and delete

The frontend creates a custom profile only in DOM/staged state, using a generated identity (`library-<timestamp>`). The identity input is readonly; default `movies` and `tv` cannot be disabled or deleted in the UI. Deleting a custom profile is an unsaved-editor action and is explicitly described as not changing saved settings until Save succeeds.

`buildPatchFromLibraries()` serializes the current cards only to `Changes JSON` as `LibraryProfiles`. It does not call a library-specific write endpoint. Backend normalization independently slugifies/canonicalizes IDs, supplies the built-in Movie/TV profiles if absent, orders built-ins first, and rejects duplicate normalized IDs. Thus a crafted raw patch cannot delete the required defaults or retain ambiguous duplicate profile identities.

### 3. Defaults, inheritance, resets, and validation

Backend state is the inheritance authority:

```text
LibraryProfiles input
  -> library_profiles_from_config()
  -> default_tracking + inherited fields
  -> effective profile / override-state payload
  -> LibraryProfiles normalization and legacy-key mirror
```

Missing custom `output_path` inherits `Outsource`; a custom source path and promotion destination do not inherit. Explicit values remain explicit even if equal to global values. Reset requests remove a specific explicit override/path state rather than copying a global value into the profile. `apply_library_profile_resets()` rejects malformed targets, missing IDs, unsupported path resets, and unsupported override groups/keys.

The UI's inherited/default indicators are advisory staging aids only. On Preview and Save, `_settings_patch_candidate()` applies reset requests, normalizes profiles, recomputes legacy mirrors, runs config validation, and returns backend `library_profile_state` evidence.

### 4. Preview, save, stale state, and reload

The Libraries-page Preview and Save buttons both first rebuild the LibraryProfiles patch, then delegate to `settingsView.js`:

```text
DOM staged profiles
  -> Changes JSON: { LibraryProfiles: [...] }
  -> POST /api/settings/preview-patch (no write)
  -> backend diff + validation + review_confirmation
  -> WebView review dialog
  -> POST /api/settings/save-patch
       {confirm_save: true, review_confirmation: <backend preview binding>}
  -> JSON authority + PSD1 projection + reload verification
```

The frontend blocks a stale `LibraryProfiles` entry in Changes JSON when the editor says it no longer matches the staged card state. More importantly, this is not the security control: the save endpoint requires a Pydantic `StrictBool`, checks `confirm_save is True`, recomputes the candidate from the current resolved config, and compares the submitted review contract (request, base-config, candidate-config, review-entries, and changed/removed key digests). A stale preview, a changed patch, or changed resolved settings produces a mismatch and no write.

On success the JSON store is the authority; it is written with the PSD1 projection, projection manifest, round-trip PowerShell import validation, backups/last-good snapshots, and rollback on promotion failure. PowerShell consumes the projected, normalized profile paths and override groups. It does not independently treat the browser DOM as configuration.

## Findings

### P1 — CSW-2026-07-09-LIBRARIES-001: Profile path roots are not strict safety roots

**Evidence.** `validate_library_profiles()` requires enabled profile path fields to be nonblank, but does not require `source_path`, `output_path`, or an enabled `promotion_destination` to be absolute. It treats source/output/promotion equality or nesting as warnings (`_overlap_warning`) rather than errors. The PowerShell profile validation likewise checks nonblank source/promotion fields and duplicate source roots, but does not enforce absolute profile paths, require output paths, or enforce profile source/output/promotion separation. The PowerShell runtime then selects a profile by source root and uses `output_path` directly for output planning.

An in-memory bundled-runtime validation of a custom profile with `relative-source`, `relative-output`, and `relative-final` returned **no errors**. A profile with `F:\Library` as source and `F:\Library\Processed` / `F:\Library\Final` as output/promotion returned warnings only and was save-eligible.

**Impact.** A saved custom profile can introduce a working-directory-relative scan/output/promotion root or place output/final-promotion beneath its source tree. That weakens scratch/source/output separation and can route work or later promotion to an unintended location. It does not directly bypass the source-mutation policy, but it changes the path boundary that downstream media/publish code trusts.

**Recommendation.** Make enabled Library Profile `source_path` and `output_path` absolute; make `promotion_destination` absolute whenever promotion is enabled. Promote same/nested source-output-promotion roots to save-blocking errors (with a narrowly documented exception only if one is genuinely safe). Implement one shared normalization/validation rule used by Python save, PSD1 projection validation, and PowerShell runtime validation.

### P1 — CSW-2026-07-09-LIBRARIES-002: Disabling or deleting a promoted profile can leave its generated fallback promotion rule active

**Evidence.** `promotion_rules_from_library_profiles()` adds profile-derived `library-profile-<id>` rules for enabled promoted profiles, then keeps every existing rule whose source root is not covered by a *currently enabled promoted* profile. If a profile is disabled, has promotion turned off, or is deleted, its former source root is no longer covered, so its already-persisted `library-profile-<id>` rule is retained. In-memory normalization confirmed that a disabled `concerts` profile retained `library-profile-concerts` with its old destination.

The final-library planner first attempts an enabled matching profile and then falls back to `FinalLibraryPromotionRules`; it selects the longest matching enabled rule. Therefore, when global `FinalLibraryPromotionEnabled` remains true, a completed row from the removed/disabled profile's former source root can still become ready for promotion using the stale derived destination. This contradicts the current-state claim that stale fallback rules do not override current profile identity evidence.

**Impact.** Turning off or deleting a Library Profile's promotion policy can leave an unexpected final-library destination eligible in a subsequent confirmed promotion workflow. The final copy still has its own command confirmation, but its decision surface is no longer an accurate reflection of the Library Profile edit the operator saved.

**Recommendation.** During normalization, remove/rebuild rules identified as profile-derived (`library-profile-<id>` and/or a durable `derived_from_library_profile` provenance field) before preserving manual legacy fallbacks. Preserve only explicitly manual rules. Add a migration/review entry that shows derived-rule removal, so Preview and Save disclose the changed promotion scope.

### P2 — CSW-2026-07-09-LIBRARIES-003: High-impact config documentation does not disclose LibraryProfiles as a path/promotion policy key

**Evidence.** `docs/architecture/CONFIG_KEY_GLOSSARY.md` documents `SourceMovies`, `SourceTV`, `Outsource`, and `LocalBase` but has no `LibraryProfiles` entry. `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md` notes in its preamble that the dedicated editor owns LibraryProfiles but omits a high-impact row for its source/output/promotion and override effects; its stated metadata totals are also stale relative to the current coverage matrix. The coverage matrix and current-state doc contain useful fragments, but none gives the key's complete authority/mirror/path-risk disclosure in the key-reference surfaces.

**Impact.** An operator can reasonably treat the four documented top-level roots as the full path policy while LibraryProfiles can override effective roots and generate compatibility promotion rules. This makes the P1 risks harder to recognize during review.

**Recommendation.** Add a `LibraryProfiles` row to the glossary and ownership map that states: JSON authority with PSD1 projection; backend-owned inheritance; required explicit/derived path behavior; exact legacy mirrors (`SourceMovies`, `SourceTV`, `Outsource`, `FinalLibraryPromotionRules`); and final-library/publish safety implications. Reconcile metadata counts when that inventory is touched.

### P3 — CSW-2026-07-09-LIBRARIES-004: Negative regression coverage does not protect the discovered path and promotion lifecycle boundaries

**Evidence.** Existing tests strongly cover duplicate IDs, missing enabled paths, override allowlists, inherited output behavior, reset semantics, normalization idempotence, preview/save confirmation, JSON-store projection rollback, and a happy-path browser add/save/reload flow. They do not assert that relative profile roots or same/nested profile source-output-promotion roots are rejected, and they cover stale promotion replacement only while a current enabled promoted profile still covers the root—not disabling/deleting that profile or turning promotion off.

**Impact.** The current unsafe behavior is unguarded, and a future fix could regress without a focused signal.

**Recommendation.** Add focused Python Preview/Save tests and PowerShell schema checks for invalid profile roots/separation; add normalization and final-library status tests for enabled → disabled, promoted → promotion-off, and delete lifecycle transitions; then extend the browser smoke with a rejected-path case and retained-staged-edit/reload behavior.

## No-finding coverage

- **Frontend cannot write directly.** `settingsLibraries.js` stages DOM values only. There is no LibraryProfiles mutation route and no direct filesystem/media/policy implementation in the WebView.
- **Read API boundary is intact.** Summary, route map, trace, compare, and validation handoff are token-protected GET routes with backend evidence payloads and no settings/queue/media writes.
- **Default profiles and duplicate identity handling are deterministic.** Movie and TV are synthesized when absent, canonical aliases normalize to those IDs, duplicates are rejected, and final ordering is deterministic.
- **Override authority is backend-derived.** Metadata determines permitted groups/keys; unsupported groups, global keys, friendly display aliases, and invalid option/numeric values are rejected. Explicit equals-global values remain explicit until a targeted reset.
- **Inheritance state is disclosed rather than inferred from the DOM.** Backend state identifies inherited, explicit, synthesized, unresolved, and provenance state; custom output inheritance and promotion explicitness are covered by targeted tests.
- **Staged/route-map state is not misrepresented as saved evidence.** The UI warns whenever edits are dirty/staged/stale; route-map GET requests load saved backend config only.
- **Preview/save anti-bypass controls are present.** Save requires backend recomputation, strict boolean confirmation, matching review confirmation, a save lock, config-identity checks, and a no-change short circuit. A caller using raw Changes JSON still encounters the same backend candidate validation.
- **JSON authority / PSD1 projection reliability is substantive.** The JSON store wins over PSD1 drift, projection is round-trip checked through PowerShell import, and JSON/PSD1/projection bytes are restored if promotion fails.
- **Cross-surface key and override parity has dedicated tests.** `test_config_keys.py` checks Python/PowerShell key order and Library Profile override allowlists; `test_library_profiles.py` checks the persisted override groups and PowerShell allowlist.

## Test and contract assessment

Strong existing coverage includes:

- `tests/python/desktop/test_library_profiles.py` for normalization, inheritance, resets, duplicate IDs, override validation, PowerShell override-key parity, and profile/legacy mirror behavior.
- `tests/python/desktop/test_application_facade_settings_patch.py` for normalized LibraryProfiles patches, mirrored review entries, resets, JSON-authority save, confirmation, save lock, and no-write failures.
- `tests/python/desktop/test_settings_store.py` for JSON-authority import, PSD1 projection drift, last-good restore, and rollback.
- `tests/python/core/library/test_route_map.py` and `tests/python/desktop/test_library_route_map_api.py` for saved-evidence route-map semantics, token protection, strict JSON responses, and non-mutation.
- `tests/webview/test_webview_browser_library_profiles_save_smoke.py` for browser add/save, mandatory backend preview before review confirmation, `confirm_save: true`, reload digest visibility, and temp-fixture media non-mutation.

Contract inventories correctly advertise `/api/settings/preview-patch` as non-writing and `/api/settings/save-patch` as high-risk JSON-authority-plus-PSD1 persistence requiring both confirmation fields. They correctly describe the Libraries route-map family as read-only evidence.

## Coordinator handoff

| Order | Owner area | Required outcome | Minimum verification |
|---:|---|---|---|
| 1 | Config validation + PowerShell schema | Resolve CSW-2026-07-09-LIBRARIES-001 with one strict Library Profile root policy across Preview, Save/projection, and runtime validation. | Focused Python config/profile tests; PowerShell config/path checks; Settings Preview/Save smoke. Real-media validation is required before production acceptance because output/promotion path routing changes. |
| 2 | Library promotion normalization + final-library planner | Resolve CSW-2026-07-09-LIBRARIES-002 by distinguishing derived rules from manual legacy rules and deleting/rebuilding only the derived set. | Normalization and final-library status tests for disable/delete/promotion-off/change-root; preview/save review-entry assertions; confirmed final-library workflow dry-run. Real-media promotion validation before acceptance. |
| 3 | Documentation/inventory owner | Resolve CSW-2026-07-09-LIBRARIES-003 after policy direction is finalized. | Active-doc reference/link checks and a review of glossary/ownership-map parity. |
| 4 | WebView + test owner | Add CSW-2026-07-09-LIBRARIES-004 regressions after backend policy is fixed; keep frontend warnings advisory rather than adding duplicate confirmation prompts. | Targeted unit/API/browser smoke coverage; no media mutation outside temporary fixtures. |

## Limits and validation record

- Reviewed generated summaries before opening the relevant source where available, then inspected the full active implementations and selected PowerShell/runtime consumers.
- Performed two in-memory bundled-Python validation probes only. Neither wrote files nor called HTTP routes: (1) relative custom profile roots returned no errors; (2) nested custom source/output/promotion roots returned warnings only. A separate in-memory normalization probe showed a stale `library-profile-concerts` rule surviving when promotion was turned off.
- Did not run browser, API, PowerShell, or real-media test suites; did not start the local API; did not invoke Preview/Save or any other mutation route. Those omissions preserve the requested read-only scope.
- This review did not inspect live operator settings, LocalBase state, actual source/output/final-library files, or external shares. It cannot prove behavior on a production filesystem or real media.

