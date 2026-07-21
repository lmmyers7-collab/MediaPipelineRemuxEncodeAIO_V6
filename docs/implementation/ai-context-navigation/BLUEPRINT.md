# Token-Bounded AI Repository Navigation Blueprint

Status: approved after adversarial review  
Change packet: `MP-CHANGE-2026-0720-002`  
Execution mode: direct worktree edits; no branch, commit, push, or PR actions

## Objective

Build one deterministic, generated repository-context pipeline that lets an AI
agent retrieve the files, ownership boundaries, dependencies, tests, risks, and
validation guidance relevant to a task without loading the full project index
or the repository's large orientation documents.

The implementation must remain offline and standard-library-first. It is a
developer-navigation change only; production media behavior is out of scope.

## Invariants

- Root `AGENTS.md` remains the global safety and change-control authority.
- Generated context remains navigation evidence, never runtime or media-policy
  authority.
- Repository source plus canonical inventories are authoritative. One typed
  `ContextRecord` extraction layer renders summaries, Markdown, JSONL, graphs,
  feature cards, and task slices as sibling navigation outputs.
- Summaries carry normalized source SHA-256 plus a deterministic
  schema/parser fingerprint. Either mismatch makes a summary stale and a
  parser-fingerprint change forces full-corpus regeneration.
- Generators build records in process. They never scrape summary, index, map,
  or card Markdown as an authoritative machine interface.
- Default retrieval excludes archives, runtime artifacts, generated summaries,
  and release change packets.
- All output ordering and budget decisions are deterministic.
- No external dependency, embedding service, broad MCP server, or network call
  is introduced.
- The timestamped pre-change dirty-target manifest, not a hard-coded count,
  defines unrelated overlap. Exact pre-existing bytes and hashes are preserved
  outside the generated tree before any write and reported separately.

## Architecture

```text
source files + canonical inventories
  -> shared typed ContextRecord extraction/classification
       -> compact fingerprinted per-file summaries
       -> PROJECT_INDEX.md (human inventory)
       -> PROJECT_INDEX.jsonl (query snapshot)
       -> DEPENDENCY_GRAPH.md
       -> FEATURE_FILE_MAP.md
       -> generated feature cards
       -> context_slice.py (bounded task capsule; may read JSONL)
```

The shared catalog owns record parsing, classification, relationship building,
feature specifications, evidence categories, authority/risk metadata, scoring
primitives, and stable ordering. One generated-output exclusion registry covers
summaries, JSONL, maps, graphs, and cards. A two-pass fixed-point check proves
that generated outputs never re-enter catalog input.

## Dependency Graph

```text
Step 1: baseline, byte snapshot, and tests
  -> Step 2: summary enrichment
  -> Step 3: shared catalog, feature taxonomy, and JSONL
       -> Step 4: context slices
       -> Step 5: feature map/cards
            -> Step 6: startup/scoped instructions
                 -> Step 7: regeneration and completion audit
```

Steps 4 and 5 are pure consumers after Step 3 freezes feature IDs, evidence
taxonomy, authority rules, and scoring primitives. Their generated outputs and
tests are integrated serially to avoid overlapping edits.

## Step 1 — Baseline, Reuse Audit, and Failing Tests

### Context brief

The current generators are
`src/mediapipeline/tools/dev/refresh_summaries.py`,
`generate_project_index.py`, and `generate_feature_file_map.py`. Existing
integrity coverage lives in `tests/python/tooling/test_summary_integrity.py`.
The working tree begins with unrelated generated-index changes, so baseline
measurements and path ownership must be recorded before regeneration.

### Tasks

- Recalculate startup-document, index, summary-quality, owner-domain,
  token-priority, and feature-noise metrics.
- Record the baseline and pre-existing dirty overlap in the change packet.
- Capture a timestamped manifest of every planned generated target intersecting
  the dirty set, including exact pre-write hash and a byte-for-byte backup
  outside the generated tree. Capture the current generator's rendered baseline
  separately from the working copy.
- Before each generated write, require the working-copy hash to match the
  captured hash. Apply the deterministic old-render -> new-render delta to the
  captured working copy with a three-way merge and stop on conflicts.
- Capture the legacy feature labels/IDs in an independent test fixture plus the
  objective's required feature IDs; the new catalog may not define its own
  completeness oracle.
- Search the repository for reusable parsers, path classifiers, token
  estimators, and generator-test helpers.
- Add focused failing tests for the shared catalog, JSONL determinism, summary
  parsing, task ranking, budget enforcement, feature cards, and startup rules.

### Verification

- New tests fail for missing behavior rather than syntax or fixture errors.
- Existing summary-integrity tests still pass before production changes.
- Backup and old-render manifests reproduce their recorded hashes.

### Exit criteria

- Baseline is reproducible and recorded in the packet.
- Every objective acceptance criterion has at least one planned evidence source.

### Rollback

Remove only the new tests and packet entries; retain the external byte snapshot
until the final completion audit proves no recovery is needed.

## Step 2 — Compact Multi-Language Summary Enrichment

### Context brief

Python and PowerShell parsing already use the standard library and shallow
regular expressions. Unsupported formats currently emit `(unparsed)`, which
prevents useful retrieval for the WebView, Tauri, documentation, schemas, and
change evidence.

### Tasks

- Add deterministic path/symbol-derived purpose fallbacks for every indexed
  file type.
- Extend Python extraction with routes and compact state/config identifiers.
- Add JavaScript functions, window exports/dependencies, API paths, and DOM
  identifiers.
- Add PowerShell dot-source, stage/tool, and state/config identifiers.
- Add compact Rust public symbols and route strings.
- Emit explicit purposes for CSS, HTML, batch, JSON, Markdown, and data files.
- Make owner-domain and token-priority rules discriminative and document their
  active-production metrics.
- Preserve compact summaries and SHA freshness behavior.
- Add a versioned summary schema/parser fingerprint. Full `--check` validates
  both source hash and fingerprint, and a fingerprint change requires `--all`
  regeneration before any downstream generator can pass.

### Verification

- Parser unit tests cover Python, JavaScript, PowerShell, Rust, and generic
  fallbacks.
- Supported executable sources never emit the literal `(unparsed)`.
- Existing line-ending and orphan-summary tests remain green.
- An unchanged source with an old parser fingerprint is proven stale.

### Exit criteria

- Summary records expose enough compact metadata for the catalog without
  opening source files for ordinary navigation.

### Rollback

Restore captured summary bytes when their post-write hashes still match, or
apply the recorded inverse old/new render delta. Never blindly regenerate or
use a destructive Git restore in the dirty tree.

## Step 3 — Shared Catalog and Machine-Readable Index

### Context brief

The existing feature generator reparses `PROJECT_INDEX.md`. This makes Markdown
a machine interface and prevents richer relationships. A shared record model is
required before task slicing or feature cards.

### Tasks

- Add a focused shared catalog module under
  `src/mediapipeline/tools/dev/`.
- Freeze feature IDs/membership aliases, evidence ranks, authority rules,
  validation rules, scoring primitives, and the legacy feature inventory here
  before either task slices or cards are implemented.
- Represent path, type, purpose, domain, feature membership, stage, priority,
  hash, symbols, dependencies, dependents, tests, routes, state identifiers,
  authority, risk, validation, layer, and evidence category.
- Resolve Python imports and other relationships when deterministic; preserve
  unresolved compact identifiers when exact resolution is unavailable.
- Generate byte-stable `docs/generated/PROJECT_INDEX.jsonl` beside the existing
  Markdown index and dependency graph.
- Extend `generate_project_index --check` to validate all outputs and paths.
- Keep the Markdown index human-readable and clearly query-only for bulk data.

### Verification

- Repeated rendering produces identical bytes.
- Every JSONL record decodes, has a unique existing repo-relative path, and
  contains the required schema fields.
- Default-query eligibility excludes historical and change-evidence noise.
- Two consecutive full generations are byte-identical and no generated output
  appears in catalog input.
- Shuffled/reversed inputs and repeated subprocesses with distinct
  `PYTHONHASHSEED` values produce identical bytes; case-colliding paths fail
  explicitly.

### Exit criteria

- All downstream navigation reads the shared catalog or JSONL, not the Markdown
  table.

### Rollback

Remove the JSONL output and shared catalog, restore the previous generator
imports, and regenerate the two legacy outputs.

## Step 4 — Token-Bounded Context Slice

### Context brief

The new CLI is the normal AI entry after `AGENTS.md`. It must produce a useful
vertical slice under a caller-supplied approximate token budget without
network or embedding support.

### Tasks

- Add `src/mediapipeline/tools/dev/context_slice.py` with `--task`, `--budget`,
  `--format markdown|json`, `--include-history`, and `--check`.
- Rank lexical, feature, domain, symbol, entrypoint, relationship, evidence,
  risk, and priority signals deterministically.
- Use documented integer weights, NFKC-plus-casefold matching, POSIX path
  normalization, sorted adjacency/BFS, evidence-rank ordering, and final
  `(casefolded_path, exact_path)` tie-breaking.
- Select layer-diverse records for shell/WebView, API, domain/contracts,
  PowerShell, state/config, tests, and boundary/validation documentation.
- Explain each selected record's relevance.
- Enforce the requested budget with a documented estimator and deterministic
  low-ranked removal.
- Define estimated tokens as `ceil(len(final_utf8_bytes) / 4)` with tolerance
  `max(16, ceil(0.02 * requested_budget))`. Re-serialize after each selection,
  reserve mandatory overhead first, reject budgets below the documented
  minimum, and never truncate paths.
- Report `capsule_estimate`, `initial_read_estimate`, and
  `bootstrap_estimate = AGENTS + capsule + complete initial reads`. Large source
  files are on-demand unless the complete initial-read set remains below 8,000.
- Provide low-confidence fallback terms and compact omitted-result counts.
- Make representative checks cover pending publish, queue display names, Tauri
  close readiness, and ASS subtitle conversion.

### Verification

- Markdown and JSON outputs are deterministic.
- Representative 3,000-token slices remain within the allowed estimation
  tolerance and include the required authority layers/tests/boundaries.
- Default results contain no archive, generated-summary, runtime, or change
  packet records.
- Tests cover Unicode, long paths, exact boundary budgets, invalid budgets,
  history re-inclusion, JSON escaping, and read-only `--check` behavior.

### Exit criteria

- An agent can start from `AGENTS.md` and one bounded command without reading
  `PROJECT_INDEX.md` wholesale.

### Rollback

Remove the CLI and its tests; the generated catalog remains independently
useful.

## Step 5 — Ranked Feature Map and Compact Cards

### Context brief

The current feature map ranks primarily by token priority then path and mixes
production, tests, docs, and hundreds of change packets. Feature navigation
must show authority-owning vertical slices first.

### Tasks

- Move feature specifications into the shared catalog.
- Rank production entrypoints and authority owners with concise reasons.
- Separate production, tests, documentation, generated material, history, and
  change evidence.
- Exclude `ops/release/changes/**` from normal primary results.
- Generate compact cards under `docs/generated/features/`, each within an
  approximate 1,200-token ceiling.
- Add `--check` coverage for exact card set, content, and path references.

### Verification

- All feature groups emit a card.
- Card filenames exactly match an independent required-feature fixture that
  preserves the legacy set and the objective's named groups.
- Cards expose the applicable WebView/Tauri -> API -> Python -> state/contract
  -> PowerShell -> tests/validation chain.
- Missing layers are rendered explicitly as `not applicable`, never silently
  omitted, and every card is at most 1,200 tokens using the same byte estimator.
- Generation and check mode are byte-stable.

### Exit criteria

- Feature navigation answers “where does this live?” without a broad index
  scan.

### Rollback

Remove cards, restore the legacy feature renderer, and regenerate the legacy
map.

## Step 6 — One Startup Workflow and Scoped Instructions

### Context brief

Root `AGENTS.md` and `docs/generated/FILE_SUMMARIES.md` currently prescribe
overlapping startup sets. Scoped instructions are useful only if they stay
small and are loaded for their subtree rather than globally.

### Tasks

- Change ordinary startup to: read root `AGENTS.md`, run `context_slice`, then
  open only returned summaries/docs/source.
- Keep status and backlog documents conditional.
- State explicitly that full Markdown indexes are query aids, not startup
  reads.
- Remove duplicated navigation wording without weakening invariants.
- Add concise subtree-specific `AGENTS.md` files for Python, WebView, and
  PowerShell only if instruction-discovery behavior proves a net context win;
  otherwise generate equivalent scoped cards and record the disposition.
- Verify supported client discovery semantics before adding scoped files. For
  root and subtree sessions measure `removed global tokens - newly auto-loaded
  scoped tokens`; require a positive delta and one startup sequence.
- Update the active documentation index and tests for the new workflow.

### Verification

- Instruction-reference tests find exactly one ordinary startup sequence.
- Each scoped instruction file, if added, remains under 500 estimated tokens
  and contains no copied global invariant block.
- Representative bootstrap measurement stays below 8,000 estimated repository
  tokens.
- The startup scanner proves no ordinary workflow requires wholesale reads of
  `PROJECT_INDEX.md`, `DOCS_INDEX.md`, `ARCHITECTURE.md`, or `MODULE_MAP.md`.

### Exit criteria

- AI navigation is unambiguous and task-bounded.

### Rollback

Restore prior navigation text and remove scoped files; generated tools remain
available but non-default.

## Step 7 — Regeneration, Validation, and Completion Audit

### Context brief

Generated-context files are high-governance tooling surfaces. The pre-existing
dirty tree makes a requirement-by-requirement audit and explicit unrelated-path
report mandatory.

### Tasks

- Regenerate affected summaries, indexes, graph, feature map, JSONL, and cards
  through their tools.
- Full-regenerate fingerprinted summaries before any summary freshness check.
- Render legacy and new outputs to external temporary roots, perform
  optimistic-hash three-way integration for dirty intersections, and retain the
  byte snapshot until completion is proven.
- Run targeted tests, all generated-context checks, architecture guardrails,
  naming lint, AI guardrail postflight, and strict change-packet validation.
- Recalculate all baseline metrics and representative retrieval results.
- Record validations, after metrics, rollback, Python impact, and unavoidable
  generated-output overlaps in the packet.
- Audit all fourteen objective acceptance criteria against authoritative
  evidence before declaring completion.
- Enforce a touched-path allowlist limited to tooling, tests, generated context,
  instructions, implementation docs, and the packet; production behavior paths
  are forbidden.

### Verification

- `refresh_summaries --check`
- `generate_project_index --check`
- `generate_feature_file_map --check`
- `context_slice --check`
- `tests.python.tooling.test_context_records`
- `tests.python.tooling.test_context_slice`
- `tests.python.tooling.test_feature_context_cards`
- `tests.python.tooling.test_summary_integrity`
- `tests.python.tooling.test_audit_checks`
- active-production threshold and full executable-purpose corpus assertions
- shuffled-input/PYTHONHASHSEED determinism and two-pass fixed-point assertions
- active-doc/generated-context integrity tests
- AI guardrail postflight
- change packet validation, including strict worktree coverage with unrelated
  pre-existing paths reported separately

### Exit criteria

- Every explicit objective requirement is proven, not merely consistent with
  the implementation.
- No production media behavior changed and no real-media validation is needed.

### Rollback

Use the packet's task-owned manifest for source/tests/docs. Restore captured
generated bytes only when optimistic post-write hashes match, otherwise apply
the recorded inverse three-way patch and stop on conflicts. Never use blind
regeneration, `git checkout`, or reset against this dirty worktree.

## Plan Mutation Protocol

- Split a step when its tests or rollback boundary can stand independently.
- Insert a step only when new evidence reveals a required prerequisite.
- Reorder only when dependency edges remain satisfied.
- Replace a mechanism when measured evidence proves it increases context or
  duplicates authority; record the equivalence and evidence in the packet.
- Never silently skip an acceptance criterion. Mark it complete only with its
  named verification evidence.

## Adversarial Review Gate

Before implementation, a separate strongest-model reviewer must challenge:

- whether the plan creates a second source of truth;
- whether relationships and ranking can be deterministic;
- whether token ceilings are actually enforceable;
- whether generated-output overlap can preserve unrelated work;
- whether scoped instructions reduce rather than increase loaded context;
- whether every acceptance criterion has a direct verification path;
- whether rollback can isolate this change in the dirty worktree.

All critical findings must be fixed in this blueprint before Step 1 exits.

Review disposition: all three critical findings and all nine major/minor design
gaps were incorporated. Completion evidence is mapped as follows:

| Acceptance criterion | Authoritative evidence |
|---|---|
| 1, 10 | Active-instruction scanner, canonical doc diff, and scoped-load cost measurement |
| 2, 3 | Four serialized golden slices with capsule/initial-read/bootstrap estimates |
| 4, 5 | JSONL schema/path/determinism/drift tests and history exclusion/re-inclusion tests |
| 6, 7 | Full executable-purpose scan and reproducible active-production classification thresholds |
| 8 | Ranking assertions proving authority entrypoints precede secondary evidence and all results have reasons |
| 9 | Independent required-feature fixture, exact card set, vertical-layer checks, and token ceilings |
| 11 | Exact command/result ledger in the change packet |
| 12 | Touched-path allowlist plus architecture and AI guardrail checks |
| 13 | Task-owned touch manifest, strict packet validation, and dirty-overlap byte/merge evidence |
| 14 | Versioned before/after measurements from the same estimator, recorded only in the packet |
