# Worker 10 workflows: independent second review

Date: 2026-07-20  
Independent reviewer: `/root/prior_audit_recon`  
First-pass reviewer string in the reconciled authoritative fragment: `/root/validation_spine`  
Assigned worker: `worker-10-ops-workflows`

## Outcome

I independently line-reviewed the exact current bytes of all five assigned workflow files and reproduced or static-proved every W10 finding before reading the completed same-reviewer self-recheck. All 15 root causes remain present and distinct. No new root cause was found, so `worker-10-workflows-independent-findings.jsonl` is intentionally a zero-byte, valid JSONL file.

Two evidence corrections are necessary:

1. `AUDIT-FIND-W10-005` remains `confirmed` at P3, but the exact current `deep-audit` suite has **19** members, not the finding's now-stale count of 18. The four named omissions remain outside the relevant named suites.
2. `AUDIT-FIND-W10-010` remains `confirmed`, but its direct effect is fail-closed. A clean copied Python runtime reaches `-m pytest`, reports that pytest is absent, and stops before signing or publishing. The defensible severity is **P2**, not P1.

The independent semantic review is complete. Initial ledger validation exposed a pre-existing first-pass metadata inconsistency: three rows were still `in_review`, and all five used the noncanonical reviewer string `worker-10-validation-spine-agent`. The coordinator then explicitly authorized reconciliation of the owning first-pass fragment. It now records canonical reviewer `/root/validation_spine`, terminal `line_reviewed_with_findings` status for all five paths, and keeps first-pass `second_review_status: pending`. The companion independent attestation now validates cleanly.

## Independence basis

The review began from the campaign objective, the original W10 findings/review rows, generated summaries for bounded supporting sources, and exact current workflow bytes. I did not reuse the first pass's semantic conclusions as proof. I independently:

- read all 1,193 workflow lines (`359 + 404 + 120 + 84 + 226`);
- bound each workflow to SHA-256 and Git state at the beginning and end;
- reproduced native-command exit masking, raw-unittest zero-test success, raw-unittest skip success, and missing-pytest behavior in disposable/local read-only probes;
- recomputed pytest and browser-module inventories from current files;
- introspected the exact current audit-suite registry;
- traced each release, scanner, credential, updater, and publication control into the bounded implementation source it invokes;
- evaluated safeguards and deduplication separately for every finding.

Only after those conclusions were frozen did I compare them with `/root/validation_spine`'s stable `worker-10-workflows-self-recheck.*` artifacts. That comparison corroborated all 15 dispositions and independently reached the same W10-005 count correction and W10-010 severity correction.

## Exact file bindings

Initial observation: branch `codex/ci-browser-shards`, HEAD `039658158d8439a868eff3c8c37e314845e9e22a`, 656 porcelain-status rows, status-stream SHA-256 `328d74a65d5c3fe58f7d9cf88a2ee64252f9e8edd6f4b097114581d4bb63b418`. All five assigned workflows were clean.

| Workflow | Lines | Initial and final SHA-256 | Exact sections reviewed |
| --- | ---: | --- | --- |
| `.github/workflows/deep-audit.yml` | 359 | `300f862dc1db1ed0b5ca37a2282cc86702cd9ec7783dc364cafb97feb9afec63` | triggers, permissions, all jobs/steps, suite execution, Python/WebView/browser matrices, Tauri, release self-test, temporary package build/verification |
| `.github/workflows/phase1-drift.yml` | 404 | `e5f1400faa34cdf1a606e0b5de77881241df5874cb4413c575085ff0de1514bc` | triggers, ref handling, Windows/Linux generated checks, analysis, Python/WebView/browser matrices, Tauri, release and package jobs |
| `.github/workflows/audit-sarif.yml` | 120 | `68189a7956268a20241c43680569a269fc032f69fe1cd98c23a7756e3e5bdd1c` | triggers, permissions, Ruff/Semgrep setup and execution, summaries, artifacts, SARIF publication |
| `.github/workflows/codeql.yml` | 84 | `481c7315a36de110df45a17c20583d982409a1099188305be67562a87a48c7ae` | triggers, permissions, CodeQL initialization/analysis, upload mode, summary and artifact handling |
| `.github/workflows/private-beta-windows.yml` | 226 | `4e2840847ca210d50497753290b76f8c2af027413c974f0424caeff5a15ade05` | dispatch contract, job environment, preflight, runtime setup, tests, dry-run/build/signing, metadata, verification, release create/view/upload |

No workflow-specific generated summary exists for four files; the generated `phase1-drift.yml` summary was read but executable truth was taken from exact source. Directly relevant implementation summaries were read before their source. The current audit suite evidence is bound to dirty concurrent `src/mediapipeline/tools/dev/audit_checks.py` SHA-256 `e51f8a1748ac7618ab9a40318c61828710322d0305ab913e11c15abfb7cc2ab6`; final introspection still reported 19 `deep-audit`, 13 `phase1-generated`, 14 `release-self-test`, and 26 registered checks.

## Finding-by-finding disposition

| Finding | Independent disposition | Severity review | Exact proof, safeguards, and deduplication |
| --- | --- | --- | --- |
| W10-001 | `confirmed` | P1 retained | Deep Audit lines 100-108 and Phase 1 lines 159-167 run two native Python commands and test `$LASTEXITCODE` only after the second. A safe reproduction produced `first_exit=7`, `second_exit=0`, final exit 0, and a false workflow failure predicate. The later gate and aggregator are safeguards only after the first failure has been overwritten. Consolidating both workflow instances is correct. |
| W10-002 | `confirmed` | P2 retained | The two workflows use unittest discovery, while current AST enumeration found exactly 26 top-level pytest tests: 7 subtitle-helper, 11 marketecture-guard, 2 dependency-atlas, and 6 WebView-touchpoint-ledger tests. Raw unittest imported a seven-test module, ran zero tests, and exited 0. Pytest configuration exists, but pytest is absent from declared project/dev dependencies and no tracked bundled runtime supplies it. This is a collection gap, distinct from W10-010's invoked-but-unprovisioned release command. |
| W10-003 | `confirmed` | P1 retained | Both matrices select 23 of 34 current browser modules and omit the same 11 modules. Raw unittest treats `SkipTest` as green; the repository's shared browser wrapper instead fails zero tests and disallowed skips, but these workflow jobs bypass it. Provisioning and per-module isolation are useful safeguards, not completeness/skip enforcement. Both workflows share one root contract gap. |
| W10-004 | `confirmed` | P2 retained | Deep Audit lines 3-11 and Audit SARIF lines 3-11 limit push paths to their own workflow files. Schedule/manual triggers and broader Phase 1/CodeQL coverage do not make these lanes run on ordinary relevant source, dependency, or test pushes. Both trigger instances are correctly consolidated. |
| W10-005 | `confirmed` | P3 retained; count corrected | The current registry contains 26 checks; `phase1-generated` has 13, `deep-audit` has 19, and `release-self-test` has 14. The four reported omissions remain: `smoke-wrapper-map`, `duplicate-test-name-report`, `generate_webview_inventory_docs --check`, and `context_slice --check`. Release self-test compensates for the first two; no scoped workflow/package/ops invocation compensates for the latter two. The root is unchanged, but “18-check” must be corrected to 19. |
| W10-006 | `confirmed` | P3 retained | Both workflows install PSScriptAnalyzer with `-Force` and no `RequiredVersion`; the helper warns and exits 0 if the module is absent. It does fail a missing target or analyzer findings once the module exists. The explicit install/logging reduce likelihood but do not make analyzer presence or version deterministic. The prerequisite/version facets belong to one analyzer-gate finding. |
| W10-007 | `confirmed` | P2 retained | Ruff and Semgrep scan steps are `continue-on-error`; all later summary/artifact/SARIF steps are guarded by file existence, and there is no terminal status/findings adjudicator. Thus scanner failure, no SARIF, or findings can leave the workflow green. Timeouts, pinned actions, and `if-no-files-found: error` only help when the guarded upload step runs. This is distinct from CodeQL's intentional artifact-only default. |
| W10-008 | `confirmed` | P3 retained | Ruff is constrained only to `>=0.8,<1`, Semgrep to `>=1,<2`, and Semgrep pulls mutable remote `p/default` rules. Major-version caps and retained output limit some risk but do not bind tool/rules content to a repository revision. This is reproducibility drift, not W10-007's fail-open adjudication gap. |
| W10-009 | `confirmed` | P2 retained | CodeQL operational failures remain gating and actions/queries are pinned, but upload defaults to `never`; only result counts, summary, and workflow artifact are produced. There is no threshold/baseline policy that fails on accepted findings. The root is visibility/acceptance policy, not Audit SARIF's ignored scanner failure/no-output path. |
| W10-010 | `confirmed` | **P2 recommended; P1 rebutted** | Private Beta initializes a copied Python runtime without `-InstallDependencies`, then invokes that runtime with `-m pytest`. Pytest is undeclared. A disposable clean venv returned `No module named pytest`. Crucially, that step precedes all signing/publication steps and its nonzero exit is not ignored, so the defect blocks releases rather than publishing an untested artifact. It is an availability/reproducibility defect and should be P2. |
| W10-011 | `confirmed` | P1 retained | Productization config emits `releases/latest/download/latest-<channel>.json`, but beta publication uses `--prerelease`. GitHub defines the latest release endpoint as the most recent non-draft, non-prerelease release, so a beta prerelease cannot serve this asset. Local JSON/preflight checks merely assert the same invalid URL shape. See [GitHub's latest-release API definition](https://docs.github.com/en/rest/releases/releases#get-the-latest-release). |
| W10-012 | `confirmed` | P1 retained | The lane runs three bounded productization pytest modules, `cargo check`, signing/integrity checks, and `build.ps1 -DryRun`; dry-run explicitly copies nothing and skips verification. It never invokes canonical `test.ps1 -RequireTests` or an equivalent strict behavioral acceptance gate before publication. Artifact integrity controls do not substitute for product behavior acceptance. |
| W10-013 | `confirmed` | P1 retained | Version and tag are independently regex-validated without equality; existing releases are only tested for existence before `gh release upload --clobber`. No check binds tag target, release target, channel/prerelease identity, and `GITHUB_SHA`. Input shape, new-release `--target`, and local artifact consistency do not protect the existing-release clobber path. This is provenance/identity, separate from acceptance, secret scope, and serialization. |
| W10-014 | `confirmed` | P1 retained | All updater and Windows-certificate secrets are declared at job scope, so checkout, setup, dependency, test, and validation steps receive them before signing. Environment protection, secret masking, pinned actions, and ephemeral runners do not narrow exposure. GitHub documents that [`jobs.<job_id>.env` applies to all steps](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idenv). |
| W10-015 | `confirmed` | P2 retained | No workflow/job concurrency group protects the non-atomic release-view/create/upload-with-clobber sequence. Manual dispatch, approvals, validation, and API conflict behavior do not serialize two approved runs for the same channel/tag. GitHub permits concurrent runs by default and provides [concurrency groups](https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency) for this control. |

## Browser and suite inventory details

The current generated smoke-wrapper map has SHA-256 `cb704a0f86b74df25f8586cffaa8f9869b4a8f8c95a0ee1b8321bda7adb617d6`. Each workflow selects 23 mapped modules. The 11 omitted modules are:

- `evidence_control_census`
- `lifecycle_reconciliation`
- `pipeline_log_window_control_census`
- `queue_launch_completed`
- `root_control_census`
- `run_monitor`
- `safe_operator_commands`
- `settings_control_census`
- `settings_field_matrix`
- `settings_generated_control_census`
- `shell_launch_queue_rename_control_census`

The strict shared wrapper's zero-test and disallowed-skip policy is a valid compensating mechanism only where invoked. The release self-test statically checks that wrapper policy but does not execute all 34 browser modules, so it does not close W10-003.

## Root-cause deduplication

All 15 existing IDs remain necessary:

- W10-001, W10-004, W10-005, and W10-006 already consolidate repeated cross-workflow instances.
- W10-002 is missing collection in required CI; W10-010 is a release command that is invoked without its runner dependency.
- W10-007 is scanner failure/no-output/findings fail-open behavior; W10-009 is CodeQL's artifact-only visibility and absence of acceptance policy.
- W10-010 is fail-closed release availability; W10-012 is fail-open absence of broad behavioral acceptance once dependencies are available.
- W10-011 is updater routing; W10-013 is release provenance; W10-014 is credential scope; W10-015 is publication serialization.

No split or merge would improve remediation ownership without double-counting or obscuring a separately fixable boundary.

## Comparison with same-reviewer self-recheck

The stable `/root/validation_spine` self-recheck agrees that all 15 roots remain, no new root exists, W10-005 has 19 current suite members, and W10-010 is P2 because it fails before signing/publication. This agreement is corroboration, not the basis for this review. Its artifacts correctly state that they are same-reviewer evidence and do not satisfy gate 10.

## Validation and limitations

Passed or expected-negative evidence:

- all five exact workflow hashes matched at initial and final observation and remained Git-clean;
- deterministic AST count: 26 omitted pytest functions across the four exact modules;
- deterministic browser comparison: 34 mapped modules, 23 selected, 11 omitted in each matrix;
- native exit-mask reproduction: exit 7 followed by exit 0 yields a green final gate;
- raw unittest zero-test and `SkipTest` probes exited 0 as expected;
- disposable clean-Python pytest probe failed with `No module named pytest` as expected and cleaned itself;
- current suite introspection: 19/13/14 members and 26 registered checks at the bound `audit_checks.py` hash;
- all requested JSONL files parse; the independent findings fragment is exactly zero bytes;
- `load_review_fragments` still returns each assigned workflow path exactly once, because the independent attestation filename is outside `worker-*-review.jsonl`;
- attestation field/disposition/hash validation was run against current first-pass rows and central dispositions. The initial first-pass reviewer/status contradictions were recorded in the error fragment, reconciled under coordinator authorization, and the final helper result has zero issues.
- `review_fragment_findings`, `finding_record_findings`, `error_record_findings`, and `second_review_attestation_findings`: zero final issues;
- `python -m unittest tests.python.tooling.test_repository_audit_ledger -v`: 26 tests passed;
- `python -m unittest tests.python.tooling.test_audit_checks -v`: 9 tests passed;
- `ops/scripts/dev/check-github-audit-spine.ps1`: `GitHub audit spine config passed`.

Not run because it is unnecessary or outside this read-only review:

- no workflow dispatch, signing, release mutation, hosted GitHub run, updater-network canary, or real-media test;
- no product, workflow, central ledger, or external-system mutation.

Every command failure, handled no-match, expected negative probe, warning, and schema limitation observed during this review is recorded in `worker-10-workflows-independent-errors.jsonl`.

## Final repository observation

Final freeze at `2026-07-20T23:34:10.1012576-04:00`: branch `codex/ci-browser-shards`, unchanged HEAD `039658158d8439a868eff3c8c37e314845e9e22a`, 524 porcelain-status rows, and status-stream SHA-256 `774bf7a9baae89a4d0fe4eaa9231abb193e8e16ec002a03177dc4ae125fa2399`. Concurrent unrelated worktree churn explains the change from the initial 656-row snapshot. Every assigned workflow was Git-clean and each final SHA-256 exactly matched the initial binding shown above.
