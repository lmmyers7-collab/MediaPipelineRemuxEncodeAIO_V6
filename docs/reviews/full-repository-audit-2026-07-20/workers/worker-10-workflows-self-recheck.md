# Worker 10 workflows: self-recheck

Date: 2026-07-20  
Reviewer: `/root/validation_spine`  
Scope: `.github/workflows/deep-audit.yml`, `phase1-drift.yml`, `audit-sarif.yml`, `codeql.yml`, and `private-beta-windows.yml`, plus bounded supporting evidence directly invoked by those workflows.  
Constraint: read-only review of product/workflow/source files; only the four assigned self-recheck artifacts were created or changed.

## Outcome

All five assigned workflow files received a same-reviewer, line-by-line self-recheck at exact current bytes. All 15 W10 root causes remain present. No genuinely new root cause was found, so `worker-10-workflows-self-recheck-findings.jsonl` is intentionally empty.

Two reconciliation corrections are required:

1. `AUDIT-FIND-W10-005` remains confirmed, but the current `deep-audit` manifest has **19** members, not 18. The same four named checks remain outside the relevant named suites.
2. `AUDIT-FIND-W10-010` remains a confirmed clean-runner dependency defect, but its direct behavior is fail-closed: the missing `pytest` module stops the job before signing and publication. I recommend **P2**, not P1. It is a release-availability/reproducibility defect, unlike W10-011 through W10-014, which are fail-open updater, acceptance, provenance, and credential-boundary defects.

This work does **not** satisfy audit gate 10: `/root/validation_spine` is the same canonical reviewer identity that authored the first-pass W10 rows. It is corroborating self-review only; `second_review_status` remains `pending` until a distinct reviewer attests these paths.

No assigned workflow changed during review. The repository had extensive unrelated concurrent churn, so every conclusion below is bound to a content hash and Git state rather than to the branch name alone.

## Exact file bindings

Branch/commit observed at review start: `codex/ci-browser-shards` at `039658158`.

| Workflow | SHA-256 | HEAD Git blob | Mode | Bytes / lines | Git worktree state | PROJECT_INDEX reconciliation |
| --- | --- | --- | --- | ---: | --- | --- |
| `.github/workflows/deep-audit.yml` | `300f862dc1db1ed0b5ca37a2282cc86702cd9ec7783dc364cafb97feb9afec63` | `738df18e5554e2f1a7a836401d9aad6cb71d194c` | `100644` | 16,789 / 359 | clean | not indexed; exact source/hash used |
| `.github/workflows/phase1-drift.yml` | `e5f1400faa34cdf1a606e0b5de77881241df5874cb4413c575085ff0de1514bc` | `03bdeb4fb2a044e5a35ea8a278818f4bfe6aa8c6` | `100644` | 17,920 / 404 | clean | hash matched |
| `.github/workflows/audit-sarif.yml` | `68189a7956268a20241c43680569a269fc032f69fe1cd98c23a7756e3e5bdd1c` | `ca7bee6bcc8333064ff12e3f8ce196d8b8f4f18d` | `100644` | 3,613 / 120 | clean | not indexed; exact source/hash used |
| `.github/workflows/codeql.yml` | `481c7315a36de110df45a17c20583d982409a1099188305be67562a87a48c7ae` | `e0be27bc08000475ebddea6e45f868d6cd0fc9d8` | `100644` | 2,698 / 84 | clean | not indexed; exact source/hash used |
| `.github/workflows/private-beta-windows.yml` | `4e2840847ca210d50497753290b76f8c2af027413c974f0424caeff5a15ade05` | `6f0dca21990bd0bb4f3c321a663459adcf23f719` | `100644` | 9,723 / 226 | clean | not indexed; exact source/hash used |

The current v2 ledger classifier categorizes each as `behavior-defining configuration/schema/workflow` with obligation `semantic_line_review`. The companion self-recheck attestation records the repeated semantic review but deliberately leaves distinct-reviewer completion pending. It intentionally sits outside the first-pass `worker-*-review.jsonl` merge glob, preventing duplicate coverage claims; the coordinator will reconcile only after a different reviewer supplies valid gate-10 evidence.

## Finding dispositions from self-recheck

| Finding | Self-recheck disposition | Severity / confidence | Reconciliation |
| --- | --- | --- | --- |
| W10-001 | confirmed | P1 / high | Directly reproduced: native exit 7 followed by native exit 0 leaves `$LASTEXITCODE == 0`; both workflows check only after the second process. |
| W10-002 | confirmed | P2 / high | Current AST inventory has 26 executable top-level pytest tests across four modules; raw unittest ran one seven-test module as zero tests and exited 0; pytest remains undeclared. |
| W10-003 | confirmed | P1 / high | Both matrices select 23 of 34 browser modules; the same 11 are absent. Raw unittest accepts `SkipTest` with exit 0 while the shared strict wrapper rejects disallowed skips and zero tests. |
| W10-004 | confirmed | P2 / high | Deep Audit and Audit SARIF push paths contain only their own workflow file; ordinary source/test/dependency pushes do not enqueue those lanes. |
| W10-005 | confirmed with factual correction | P3 / high | The exact current manifest emits 19, not 18, deep-audit checks. The four claimed omissions remain verified again during self-recheck. |
| W10-006 | confirmed | P3 / high | Both workflows install an unpinned gallery module; the helper warns and exits 0 if PSScriptAnalyzer cannot be discovered. |
| W10-007 | confirmed | P2 / high | Ruff and Semgrep scans are `continue-on-error`; summary/artifact/upload steps are file-existence guarded; no final scan-status or findings adjudicator exists. |
| W10-008 | confirmed | P3 / high | Ruff `>=0.8,<1`, Semgrep `>=1,<2`, and remote `p/default` rules can move without a repository diff. |
| W10-009 | confirmed | P2 / high | CodeQL upload defaults to `never`; SARIF is summarized/artifacted, but no finding threshold/baseline gate exists. |
| W10-010 | confirmed; severity correction recommended | **P2** / high | Clean-runner pytest provisioning is absent, but failure occurs before signing/publication and is therefore fail-closed. |
| W10-011 | confirmed | P1 / high | Beta publishes a prerelease while installed clients are configured for `releases/latest/download/latest-beta.json`; GitHub's latest release excludes prereleases. |
| W10-012 | confirmed | P1 / high | The publish lane runs three productization pytest files, `cargo check`, and artifact integrity checks, but never the canonical strict release acceptance or `cargo test`. |
| W10-013 | confirmed | P1 / high | Version and tag are separately regex-validated; existing releases are not bound to `GITHUB_SHA`/channel identity before `--clobber`. |
| W10-014 | confirmed | P1 / high | Updater and certificate credentials are declared in job-scope `env`, exposing them to setup, dependency, test, and validation steps before signing. |
| W10-015 | confirmed | P2 / high | No concurrency group exists around non-atomic view/create/upload-with-clobber publication. |

## Self-recheck evidence

### Required CI and browser gates

- W10-001 was behaviorally reproduced without changing the repository: a first native process exited 7, a second exited 0, and the workflow-style final test evaluated false.
- W10-002 was counted again during self-recheck from current syntax: 7 tests in `test_ass_to_srt_helpers.py`, 11 in `test_marketecture_guard.py`, 2 in `test_dependency_atlas.py`, and 6 in `test_webview_touchpoint_ledger.py`. `requirements/dev.txt` and project dependencies do not include pytest.
- W10-003 was reconciled against the physical current browser-test inventory: 34 modules total, 23 selected, 11 omitted. The omitted set remains `evidence_control_census`, `lifecycle_reconciliation`, `pipeline_log_window_control_census`, `queue_launch_completed`, `root_control_census`, `run_monitor`, `safe_operator_commands`, `settings_control_census`, `settings_field_matrix`, `settings_generated_control_census`, and `shell_launch_queue_rename_control_census`.
- A synthetic raw-unittest skip ran one test, reported `OK (skipped=1)`, and exited zero. The current shared wrapper at SHA-256 `22d1b977110eecf02985605b1990ada27cc621a4b7dbfd3d2891f7692439fb30` explicitly rejects zero tests and disallowed skips.

### Generated/static/security lanes

- `audit_checks emit deep-audit` returned 19 members at `audit_checks.py` SHA-256 `e51f8a1748ac7618ab9a40318c61828710322d0305ab913e11c15abfb7cc2ab6`. `smoke-wrapper-map` and `duplicate-test-name-report` remain outside the phase/deep suites; `generate_webview_inventory_docs --check` and `context_slice --check` are not registered there.
- `check_powershell_analysis.ps1` SHA-256 `defa9d8b8ea7d549082fb76d8f205b5db1b746a16ce95821f2d03cc5083839e8` still exits successfully when the analyzer is absent.
- Audit SARIF lines 36-41 and 86-91 resolve moving scanner inputs and tolerate scanner failures. Lines 43-70 and 93-120 only act when a SARIF file exists; there is no terminal adjudication.
- CodeQL lines 47-53 default upload to `never`; lines 55-84 summarize and upload a workflow artifact only. This is evidence production, not findings acceptance.

### Private release lane

Supporting release evidence was read at these exact clean hashes:

| Supporting file | SHA-256 |
| --- | --- |
| `Initialize-CiPythonRuntime.ps1` | `22bd29fa1beace39651cd00f538331eaaed47a1b4c9de126910716ca17208bb8` |
| `build.ps1` | `2da098a118246b40fa5c5bfd2e3d073585f4aecbf596223d4747d66b624280ce` |
| `test.ps1` | `ce8efc8147dd1a6853e5f77f5344ea4815bc947022b26d8f9ac64479e5b7c848` |
| `test_support.ps1` | `edcd602897ffada344f5974252dfb93482ed938a1dba371c67d304a25b14e4d7` |
| `Test-PrivateBetaReleasePreflight.ps1` | `dd8c4df53cc9cf23b3506448f5a612f87f9018a7147c02333f25e65d9d3e1cc4` |
| `New-TauriProductizationConfig.ps1` | `25ef1c7a71af20e28b3ceabf81e2aea7ef629114790db5f556116d52573ad69e` |
| `New-TauriUpdaterChannelJson.ps1` | `7bd1c9688bccc9203dd5adb3ff223dd3d123f67db5470bb3c8a108c6343c0975` |
| `Test-PrivateBetaReleaseArtifact.ps1` | `ebeb849d3c6d59cd3bcc18aa2c5bfb55985072ddac3badc72723f38d3c4d80a1` |
| `apps/desktop/tauri/package.json` | `419c73b00e01cc3356d775c877b401b2f9b890477f88e6b2159812905b412e3c` |
| `requirements/dev.txt` | `558357ccd80cd75318114891a219abbd3b381a6207e92a5830f34d897db96338` |
| `pyproject.toml` | `f359af1bb3d8f56c2788f1a90509043f3451a10508a7b76046350d4c7119b1b4` |

The initializer installs dependencies only with `-InstallDependencies`; the workflow omits that switch and then invokes `-m pytest`. This confirms W10-010's mechanism while also proving its direct failure is before the signing build.

`New-TauriProductizationConfig.ps1` line 47 configures `releases/latest/download/latest-<channel>.json`, while the workflow adds `--prerelease` for beta. GitHub defines latest as the most recent non-prerelease, non-draft release in its [official Releases API documentation](https://docs.github.com/en/rest/releases/releases?apiVersion=latest), confirming W10-011.

`build.ps1 -DryRun` returns before copying and explicitly says verification is skipped. The workflow never calls `test.ps1 -RequireTests`; its npm `check` command maps only to `cargo check`. Local artifact verification checks installer/signature/channel JSON/checksums/Authenticode, not application behavior, confirming W10-012.

Both workflow and preflight separately validate version/tag shapes and never assert `ReleaseTag == app-v<Version>`. The existing-release branch checks only whether `gh release view` succeeds, then uploads with `--clobber`; it never compares tag target, release target, channel, or prerelease identity to the current SHA. A disposable runtime convenience probe was rejected before execution because command policy blocked populating release credential environment names; that skip is recorded and does not weaken the exact static proof.

GitHub documents that workflow runs execute concurrently by default and that concurrency groups are the mechanism for limiting them in [GitHub Actions concurrency documentation](https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency). Environment approval controls access/protection, while source-controlled concurrency is a separate mechanism. The workflow has no concurrency key around its view/create/clobber sequence, confirming W10-015.

## Root-cause deduplication

- W10-002 and W10-010 share the undeclared-pytest dependency edge, but they are not duplicates. W10-002 is missing test collection in required CI; W10-010 is an invoked-but-unprovisioned clean-runner dependency. One can be fixed without the other.
- W10-007 and W10-009 both lack findings adjudication, but their causes and controls differ: scanner commands are fail-open/no-output in Audit SARIF, whereas CodeQL intentionally defaults publication to local artifact-only evidence.
- W10-012 is not a substitute for W10-013 through W10-015. Strict product acceptance, provenance identity, secret scope, and publication serialization require independent controls and have independent failure scenarios.
- W10-006's unpinned dependency and missing-tool green skip are retained as one analyzer-prerequisite contract finding; splitting it would double-count the same boundary without changing remediation.

No W10 finding was rebutted or merged away, and no self-recheck-only finding was opened.

## Validation and limitations

Passed:

- repository context-slice fallback for the assigned workflow/release task;
- exact line-numbered reads of all five workflows and bounded support sources after generated-summary checks;
- `ops/scripts/dev/check-github-audit-spine.ps1`: `GitHub audit spine config passed`;
- `python -m unittest tests.python.tooling.test_audit_checks -v`: 9 tests passed;
- `python -m unittest tests.python.tooling.test_repository_audit_ledger -v`: 23 tests passed;
- v2 `build_rows` reconstruction: all five workflow rows reproduced at the hashes above with `semantic_line_review` obligations;
- companion finding/error fragments and the 5-row, SHA-256 `92a0d0b1ce30d4a8ac66fd7224e0ca7a2e444fcbb0e6595ad947e4eaf6a83bf0` out-of-merge self-recheck attestation validated with `repository_audit_ledger.py` helper validators; `load_review_fragments` sees each W10 workflow path exactly once.

Expected/recorded negative-path evidence:

- raw unittest accepted one skipped test;
- raw unittest accepted a seven-pytest-function module as zero tests;
- the release-identity convenience probe was not executed because credential-environment command policy rejected it;
- no hosted GitHub Actions run, signing operation, release mutation, network updater canary, or real-media test was performed. Those are not required to prove the static control-flow defects and would exceed this read-only self-recheck scope.

Every nonzero, warning, correction, and skip is preserved in `worker-10-workflows-self-recheck-errors.jsonl`. No product, workflow, application source, central ledger, release, or external system was modified.
