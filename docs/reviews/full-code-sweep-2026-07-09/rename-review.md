# Rename workflow review — 2026-07-09

## Executive assessment

The standalone Rename tab has a strong backend-owned mutation boundary and a generally sound transaction model. The WebView stages paths, presents backend preview evidence, requires a modal confirmation, and calls only Local API routes; it does not contain a filesystem or process mutation API. The Local API also rejects non-boolean confirmations, injects authoritative roots, serializes apply/undo work, rebuilds the plan in the backend, rejects selected blocked rows, and writes an undo manifest before changing paths.

However, the review found two material path-safety gaps, no server-side preview-to-apply binding, and an undo/history presentation regression. **Do not treat the current Rename workflow as fully boundary-safe until CSW-2026-07-09-RENAME-001 and -002 are fixed and adversarially tested.**

Finding summary: **P0: 0; P1: 2; P2: 2; P3: 1.** No routes were invoked and no code, configuration, test, inventory, generated document, or change packet was changed during this review.

## Evidence reviewed

Read the requested operating, architecture, current-state, route-inventory, validation, and no-touch documents. Reviewed the Rename partial; `renameView.js`; all `assets/rename/*.js`; Rename labels/history modules; route contracts and payload schemas; command mixin, facade, policies, planner, apply/undo runners, service, path authority, and shared boundary helpers; all Rename-focused Python/WebView tests; the frontend mutation-boundary test; and Rename route/test inventories.

## Workflow traces

### 1. Target selection and preview generation

1. The page provides browse, folder, drag/drop, and manual staging controls; the staged textarea is client-only state ([page-rename.html:19](../../../apps/desktop/webview/static/partials/page-rename.html#L19)-[40](../../../apps/desktop/webview/static/partials/page-rename.html#L40)).
2. `collectRenameRequest()` derives the preview/apply request from staged paths and form options ([renameView.js:74](../../../apps/desktop/webview/static/assets/renameView.js#L74)-[94](../../../apps/desktop/webview/static/assets/renameView.js#L94)). Browse/drop paths are resolved through `POST /api/rename/browse`, not a frontend filesystem API ([renameView.js:1562](../../../apps/desktop/webview/static/assets/renameView.js#L1562)-[1611](../../../apps/desktop/webview/static/assets/renameView.js#L1611)).
3. Preview posts to `POST /api/rename/preview`; request IDs suppress out-of-order results ([renameView.js:2665](../../../apps/desktop/webview/static/assets/renameView.js#L2665)-[2720](../../../apps/desktop/webview/static/assets/renameView.js#L2720)).
4. The backend classifies media versus sidecar/non-media/duplicate staged inputs before planning ([input_classification.py:66](../../../src/mediapipeline/core/rename/input_classification.py#L66)-[98](../../../src/mediapipeline/core/rename/input_classification.py#L98)); the facade annotates the backend plan with root-authority evidence ([facade.py:191](../../../src/mediapipeline/core/rename/facade.py#L191)-[201](../../../src/mediapipeline/core/rename/facade.py#L201)).

### 2. Preview warnings and readiness

1. The planner detects missing/non-file sources, existing targets, long paths, sidecar collisions, and duplicate targets; duplicate rows receive blocking errors ([planner.py:200](../../../src/mediapipeline/core/rename/planner.py#L200)-[224](../../../src/mediapipeline/core/rename/planner.py#L224), [284](../../../src/mediapipeline/core/rename/planner.py#L284)-[297](../../../src/mediapipeline/core/rename/planner.py#L297)).
2. The WebView disables blocked, duplicate-target, and existing-target rows, removes any now-invalid checks, and blocks the Apply button when stale or unsafe ([renameView.js:2500](../../../apps/desktop/webview/static/assets/renameView.js#L2500)-[2561](../../../apps/desktop/webview/static/assets/renameView.js#L2561), [2581](../../../apps/desktop/webview/static/assets/renameView.js#L2581)-[2624](../../../apps/desktop/webview/static/assets/renameView.js#L2624)).
3. The local stale indication compares a JSON signature of the current controls to the last preview request ([renameView.js:96](../../../apps/desktop/webview/static/assets/renameView.js#L96)-[126](../../../apps/desktop/webview/static/assets/renameView.js#L126)). This is helpful UI protection but is not backend authorization; see finding -003.

### 3. Apply confirmation and request validation

1. The confirmation modal makes the filesystem action and sidecar scope explicit and sends no request on cancel ([renameView.js:3072](../../../apps/desktop/webview/static/assets/renameView.js#L3072)-[3117](../../../apps/desktop/webview/static/assets/renameView.js#L3117)).
2. Only after confirmation does the UI send checked `selected_sources`, `confirm_apply: true`, and the outside-root acknowledgement ([renameView.js:3345](../../../apps/desktop/webview/static/assets/renameView.js#L3345)-[3403](../../../apps/desktop/webview/static/assets/renameView.js#L3403)).
3. The route payload is strict and makes `confirm_apply` and the outside-root acknowledgement `StrictBool` ([api_commands.py:282](../../../src/mediapipeline/contracts/api_commands.py#L282)-[306](../../../src/mediapipeline/contracts/api_commands.py#L306)); the handler validates before dispatch ([handler.py:102](../../../src/mediapipeline/desktop/api/handler.py#L102)-[117](../../../src/mediapipeline/desktop/api/handler.py#L117)); the facade independently requires `is True` ([facade.py:119](../../../src/mediapipeline/core/rename/facade.py#L119)-[125](../../../src/mediapipeline/core/rename/facade.py#L125)).

### 4. Preview/fingerprint binding

Apply rebuilds the plan from the submitted request and selects only current matching sources ([facade.py:137](../../../src/mediapipeline/core/rename/facade.py#L137)-[154](../../../src/mediapipeline/core/rename/facade.py#L154)). It does **not** require a server-issued preview ID/fingerprint or revalidate the exact preview that the operator confirmed; see finding -003.

### 5. Transaction result, journal/history, and UI refresh

1. Apply builds all operations, writes a `planned` undo manifest before mutation, updates it while applying, performs reverse rollback on failure, and marks it `completed` only after operations and sidecar metadata handling finish ([apply_runner.py:24](../../../src/mediapipeline/core/rename/apply_runner.py#L24)-[141](../../../src/mediapipeline/core/rename/apply_runner.py#L141)).
2. The UI reports only an in-flight state before `await apiPost()` completes; it renders success/result evidence only from the returned backend result ([renameView.js:3385](../../../apps/desktop/webview/static/assets/renameView.js#L3385)-[3403](../../../apps/desktop/webview/static/assets/renameView.js#L3403)). The result is journaled before the HTTP response is sent ([handler.py:148](../../../src/mediapipeline/desktop/api/handler.py#L148)-[163](../../../src/mediapipeline/desktop/api/handler.py#L163)).
3. Local and backend command history is rendered into Rename history ([commandHistory.js:530](../../../apps/desktop/webview/static/assets/commandHistory.js#L530)-[570](../../../apps/desktop/webview/static/assets/commandHistory.js#L570), [1316](../../../apps/desktop/webview/static/assets/commandHistory.js#L1316)-[1338](../../../apps/desktop/webview/static/assets/commandHistory.js#L1316)). Its apply-only filter creates the undo-state issue in finding -004.

### 6. Undo behavior

1. The UI requires another modal confirmation and sends `confirm_undo: true` plus the last manifest ([renameView.js:3120](../../../apps/desktop/webview/static/assets/renameView.js#L3120)-[3163](../../../apps/desktop/webview/static/assets/renameView.js#L3163), [3406](../../../apps/desktop/webview/static/assets/renameView.js#L3406)-[3440](../../../apps/desktop/webview/static/assets/renameView.js#L3440)).
2. The backend verifies the manifest path is below the resolved undo root, requires schema `rename_undo.v1`, completion status, and an unused undo state before mutation ([undo_runner.py:120](../../../src/mediapipeline/core/rename/undo_runner.py#L120)-[141](../../../src/mediapipeline/core/rename/undo_runner.py#L141)).
3. Operations are boundary-preflighted and reversed in order, but metadata restoration bypasses those boundary checks; see finding -002.

### 7. Collision, traversal, UNC, normalization, duplicate-submit, and sidecar posture

- Media and sidecar duplicate/existing-target collisions are rejected both in planning and operation construction ([planner.py:209](../../../src/mediapipeline/core/rename/planner.py#L209)-[224](../../../src/mediapipeline/core/rename/planner.py#L224), [apply.py:139](../../../src/mediapipeline/core/rename/apply.py#L139)-[178](../../../src/mediapipeline/core/rename/apply.py#L178)).
- Name overrides reject path separators and normalize invalid Windows filename characters ([plan_policy.py:77](../../../src/mediapipeline/core/rename/plan_policy.py#L77)-[94](../../../src/mediapipeline/core/rename/plan_policy.py#L77), [utils.py:20](../../../src/mediapipeline/core/rename/utils.py#L20)-[29](../../../src/mediapipeline/core/rename/utils.py#L20)).
- Per-operation boundaries use absolute common-path checks, reject cross-volume paths, and reject symlink/junction/reparse components ([layout.py:93](../../../src/mediapipeline/core/paths/layout.py#L93)-[151](../../../src/mediapipeline/core/paths/layout.py#L151)).
- Both apply and undo share the non-blocking rename lock, and active pipeline work blocks either action ([facade.py:129](../../../src/mediapipeline/core/rename/facade.py#L129)-[158](../../../src/mediapipeline/core/rename/facade.py#L129), [162](../../../src/mediapipeline/core/rename/facade.py#L162)-[189](../../../src/mediapipeline/core/rename/facade.py#L162)).
- UNC authority classification has a unit test, but no mutation test runs against a UNC share ([test_service_rename_planner.py:174](../../../tests/python/desktop/test_service_rename_planner.py#L174)-[181](../../../tests/python/desktop/test_service_rename_planner.py#L174)).

## Findings

### P0

None.

### P1 — CSW-2026-07-09-RENAME-001: configured-root authority validates the source but not a derived TV hierarchy destination

**Evidence.** Authority is assigned from the source alone ([path_authority.py:156](../../../src/mediapipeline/core/rename/path_authority.py#L156)-[178](../../../src/mediapipeline/core/rename/path_authority.py#L156)); apply only requires outside-root acknowledgement when the selected *source* rows are outside ([facade.py:147](../../../src/mediapipeline/core/rename/facade.py#L147)-[152](../../../src/mediapipeline/core/rename/facade.py#L147)). Manual-TV planning can choose a `mutation_root` above the source parent ([tv.py:235](../../../src/mediapipeline/core/rename/tv.py#L235)-[260](../../../src/mediapipeline/core/rename/tv.py#L235)) and then construct a destination beneath that broader root ([tv.py:263](../../../src/mediapipeline/core/rename/tv.py#L263)-[297](../../../src/mediapipeline/core/rename/tv.py#L263)). The planner adopts both values without rechecking them against configured roots ([planner.py:180](../../../src/mediapipeline/core/rename/planner.py#L180)-[195](../../../src/mediapipeline/core/rename/planner.py#L180)).

**Impact.** If a configured root is a season or a narrow library-profile folder, a source inside it can be moved into a sibling/parent-derived show hierarchy outside that configured root without `allow_outside_configured_roots: true`. The lower boundary check only verifies the derived `mutation_root`, so it does not restore configured-root policy.

**Recommendation.** Compute authority for both source and every derived destination/sidecar destination. Require every operation to remain under the same authorized configured root, or classify the row outside-root and require the existing explicit acknowledgement. Add a regression using a configured root equal to a season folder and a manual-TV hierarchy plan.

### P1 — CSW-2026-07-09-RENAME-002: undo metadata-backup restoration can write or delete paths outside the operation boundary

**Evidence.** Undo preflight validates only `operations` ([undo_runner.py:71](../../../src/mediapipeline/core/rename/undo_runner.py#L71)-[93](../../../src/mediapipeline/core/rename/undo_runner.py#L71)). `_restore_metadata_backups()` accepts each manifest `path`, maps it only if it happens to equal an operation destination, then calls `unlink()` or `atomic_write_text()` without any `ensure_path_boundary_safe_for_mutation()` check ([undo_runner.py:96](../../../src/mediapipeline/core/rename/undo_runner.py#L96)-[117](../../../src/mediapipeline/core/rename/undo_runner.py#L96)). The manifest-root check protects where the manifest is read, not the backup paths contained in it ([undo_runner.py:126](../../../src/mediapipeline/core/rename/undo_runner.py#L126)-[141](../../../src/mediapipeline/core/rename/undo_runner.py#L126)).

**Impact.** A corrupted or locally modified backend-owned undo manifest can direct undo metadata restoration to an arbitrary existing path writable by the Local API process. This violates the requirement that undo cannot escape intended paths even though media/sidecar move operations themselves are boundary-checked.

**Recommendation.** Before every metadata restore, derive the permitted root from its paired operation and require the restore path to be under it, reject unmatched backup entries, and apply the same reparse/cross-volume checks. Add adversarial tests for `..`, absolute out-of-root, UNC, and reparse-point backup paths; assert no target is created, overwritten, or deleted.

### P2 — CSW-2026-07-09-RENAME-003: apply is not bound to a server-issued valid preview/fingerprint

**Evidence.** The API schema and route contract for `/api/rename/apply` contain no preview ID or fingerprint ([api_commands.py:282](../../../src/mediapipeline/contracts/api_commands.py#L282)-[306](../../../src/mediapipeline/contracts/api_commands.py#L282), [api_routes_command.py:752](../../../src/mediapipeline/contracts/api_routes_command.py#L752)-[782](../../../src/mediapipeline/contracts/api_routes_command.py#L752)). The only freshness check is a client-side serialized request signature ([renameView.js:96](../../../apps/desktop/webview/static/assets/renameView.js#L96)-[120](../../../apps/desktop/webview/static/assets/renameView.js#L96)); backend apply builds a fresh current plan from the submitted fields ([facade.py:119](../../../src/mediapipeline/core/rename/facade.py#L119)-[154](../../../src/mediapipeline/core/rename/facade.py#L119)).

**Impact.** The backend correctly avoids trusting a client plan and rechecks collision/blocker state, but it cannot prove that the operator confirmed the exact server-derived destination set that will run. Filesystem/config/naming-preview changes between preview and apply can produce a different valid plan without an explicit stale-preview response.

**Recommendation.** Return an opaque backend preview ID/fingerprint covering selected source identities, options, computed operations, configured-root authority, and source/destination freshness facts. Require it on apply, rebuild/revalidate it under the lock, and return a dedicated stale-preview result if it differs. Keep the UI signature only as an ergonomic early guard.

### P2 — CSW-2026-07-09-RENAME-004: command-history refresh can overwrite completed undo state with the old apply state

**Evidence.** Command-history rendering invokes Rename history every time it renders ([commandHistory.js:1296](../../../apps/desktop/webview/static/assets/commandHistory.js#L1296)-[1338](../../../apps/desktop/webview/static/assets/commandHistory.js#L1296)). Rename history filters out `rename.undo` and renders the latest `rename.apply` as current evidence ([renameHistoryView.js:2](../../../apps/desktop/webview/static/assets/renameHistoryView.js#L2)-[46](../../../apps/desktop/webview/static/assets/renameHistoryView.js#L2)). `renderRenameApplyResult()` then resets `lastRenameUndoCompleted` to `false` and restores the old undo manifest ([renameView.js:2342](../../../apps/desktop/webview/static/assets/renameView.js#L2342)-[2360](../../../apps/desktop/webview/static/assets/renameView.js#L2342)), whereas an undo result correctly sets it to `true` ([renameView.js:2415](../../../apps/desktop/webview/static/assets/renameView.js#L2415)-[2451](../../../apps/desktop/webview/static/assets/renameView.js#L2415)).

**Impact.** A later command-history poll/render can show the old apply outcome and re-enable “Undo Last Apply” after a successful undo. Backend manifest status rejects the second undo, so this is an operator-trust/state-representation defect rather than a second-mutation path.

**Recommendation.** Render the latest Rename command of either type, preserve a completed undo state when history is merged, and derive button state from the newest matching manifest event. Add a browser/Node regression: apply → undo → history refresh/poll → assert “Undo completed,” disabled button, and undo result remain visible.

### P3 — CSW-2026-07-09-RENAME-005: Rename safety inventory inaccurately states active-work blocking has no test

**Evidence.** The inventory says no test verifies active-pipeline blocking ([RENAME_SAFETY_TEST_INVENTORY.md:134](../../inventories/RENAME_SAFETY_TEST_INVENTORY.md#L134)). Current tests do cover facade locking/active work ([test_application_facade_rename.py:408](../../../tests/python/desktop/test_application_facade_rename.py#L408)-[470](../../../tests/python/desktop/test_application_facade_rename.py#L408)) and the Local API active-work rejection/no-mutation path ([test_application_facade_local_api_rename.py:384](../../../tests/python/desktop/test_application_facade_local_api_rename.py#L384)-[425](../../../tests/python/desktop/test_application_facade_local_api_rename.py#L384)).

**Impact.** The stale inventory weakens release/audit triage by overstating a closed coverage gap.

**Recommendation.** Correct the inventory to distinguish its covered temp-fixture active-work guard from still-uncovered real concurrent filesystem/process behavior.

## No-finding coverage

- **Frontend mutation boundary:** confirmed. The Rename UI uses route calls and DOM/local staging only; the repository-wide frontend boundary test forbids direct shell, process, Tauri, and non-centralized fetch APIs ([test_webview_frontend_mutation_boundary.py:945](../../../tests/webview/test_webview_frontend_mutation_boundary.py#L945)-[969](../../../tests/webview/test_webview_frontend_mutation_boundary.py#L945)). Route ownership also pins all Rename POSTs to `renameView.js` ([test_webview_frontend_mutation_boundary.py:123](../../../tests/webview/test_webview_frontend_mutation_boundary.py#L123)-[127](../../../tests/webview/test_webview_frontend_mutation_boundary.py#L123)).
- **Strict confirmation:** confirmed for apply and undo at schema, handler, and facade levels; tests exercise missing, false, and string confirmation with no mutation ([test_application_facade_local_api_rename.py:329](../../../tests/python/desktop/test_application_facade_local_api_rename.py#L329)-[382](../../../tests/python/desktop/test_application_facade_local_api_rename.py#L329), [test_api_command_contracts.py:856](../../../tests/python/desktop/test_api_command_contracts.py#L856)-[888](../../../tests/python/desktop/test_api_command_contracts.py#L856)).
- **Collision fail-safe:** confirmed at planner, operation-builder, UI readiness, and browser smoke levels. Duplicate targets and existing destinations block selected rows before posting apply.
- **Duplicate submit / active work:** confirmed in-process: the shared non-blocking lock protects apply and undo, and active work is rejected before plan building. This is not a cross-process distributed rename lock.
- **Success timing:** confirmed. The UI labels the request as in-flight and explicitly says it does not prove a rename before the backend response; the runner writes a completed undo manifest before returning success.
- **UNC/path normalization/reparse checks:** source authority recognizes a configured UNC child without touching the share; operation boundary code rejects cross-volume paths and reparse components. There was no live UNC mutation exercise.

## Test and contract assessment

The Rename suite is broad and uses temporary files, mocked subprocesses, Node VM, and browser fixtures. It covers strict confirmations, selected-source scope, source authority injection/spoofing rejection, active-work rejection, duplicate targets, existing collisions, sidecar companion movement, case-only rename recovery, rollback, manifest-root confinement, and basic undo reversal. The route inventory correctly identifies only `rename/apply` and `rename/undo` as Rename media-mutation routes ([API_ROUTE_INVENTORY.md:229](../../inventories/API_ROUTE_INVENTORY.md#L229)-[239](../../inventories/API_ROUTE_INVENTORY.md#L229)).

Not covered by tests observed here: destination-versus-configured-root authority; hostile metadata-backup paths in an otherwise in-root undo manifest; server-issued preview/fingerprint mismatch; apply→undo→history-refresh UI state; live UNC mutation; and real concurrent external mutation after preview. The inventory also notes no real interactive Windows dialog and no CI real-media rename evidence. Tests were **not run** for this read-only audit; doing so was unnecessary to establish the line-level control-flow findings and the request prohibited live route invocation.

## Coordinator handoff

1. Treat **-001** and **-002** as the path-safety work package; change them together with adversarial temp-fixture tests before a Rename release gate.
2. Treat **-003** as the preview-contract work package. It changes public request/response contracts and inventories, so plan schema, WebView, Local API, and command-journal validation together.
3. Treat **-004** as a WebView command-evidence regression with a focused browser/Node test; backend remains a safe backstop because duplicate undo is rejected by manifest status.
4. Fold **-005** into the documentation/inventory update that accompanies the code work; no standalone safety mechanism is needed.
5. Any implementation touches the explicit high-risk Rename boundary and requires the validation ladder’s targeted unit tests plus affected WebView/API smokes. Real-media validation is not required for a pure rename-control fix unless the change modifies media/sidecar move behavior beyond these guards; if it does, schedule representative real-file rename and undo evidence.

## Limits

- This was a static, read-only audit of the on-disk workspace on 2026-07-09. No preview, apply, undo, browse, or other live route was called.
- No source, output, UNC share, sidecar, manifest, or runtime state was modified.
- Existing unrelated dirty files were present throughout the workspace, including Rename backend files and inventories; none were changed or attributed to this review.
- Findings describe control-flow and adversarial-input risk. They are not proof of a live-media failure on the operator’s filesystem.
