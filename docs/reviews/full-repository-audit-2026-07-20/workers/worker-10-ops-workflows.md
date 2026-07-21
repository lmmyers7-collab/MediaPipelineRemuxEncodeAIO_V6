# Worker 10 — Operations, Release Evidence, and Workflows

## Semantic review batch: GitHub workflows

Status: five assigned workflow files were reviewed line by line at their coverage-baseline SHA-256 values. The hashes were checked before and after the review and did not change. No workflow or directly related implementation file was edited.

Structured artifacts:

- `worker-10-ops-workflows-findings.jsonl`: 15 schema-complete, distinct root-cause records (`AUDIT-FIND-W10-001` through `AUDIT-FIND-W10-015`).
- `worker-10-ops-workflows-errors.jsonl`: 14 schema-complete review/tooling incident records (`AUDIT-ERR-W10-001` through `AUDIT-ERR-W10-014`). IDs 001-010 capture semantic-review incidents; IDs 011-014 capture finalization exceptions/integrity defects and their successful remediation.
- `worker-10-ops-workflows-review.jsonl`: five content-hash-bound, terminal `line_reviewed_with_findings` rows under canonical reviewer `/root/validation_spine`. Their first-pass `second_review_status` fields remain `pending`; the distinct `/root/prior_audit_recon` attestation is recorded outside the first-pass merge glob.

Deduplication result: all 15 finding IDs remain because each represents a distinct root cause. Cross-workflow symptoms were already consolidated within W10-001, W10-004, W10-007, and W10-013; no alias records were necessary. The missing packaging-metadata dependency-search incident was not duplicated because `AUDIT-ERR-VALIDATION-007` already records it in the validation-spine error ledger.

Independent reconciliation: `/root/prior_audit_recon` re-read all five exact workflow files and independently confirmed every root. It corrected W10-005's current `deep-audit` suite count from 18 to 19 and W10-010's severity from P1 to P2 because the missing pytest dependency fails the job before signing or publication. No new finding was opened.

Reviewed files:

| Path | Lines reviewed | SHA-256 | Result |
| --- | ---: | --- | --- |
| `.github/workflows/deep-audit.yml` | 1-359 | `300f862dc1db1ed0b5ca37a2282cc86702cd9ec7783dc364cafb97feb9afec63` | `line_reviewed_with_findings` — independent attestation recorded separately |
| `.github/workflows/phase1-drift.yml` | 1-404 | `e5f1400faa34cdf1a606e0b5de77881241df5874cb4413c575085ff0de1514bc` | `line_reviewed_with_findings` — independent attestation recorded separately |
| `.github/workflows/audit-sarif.yml` | 1-120 | `68189a7956268a20241c43680569a269fc032f69fe1cd98c23a7756e3e5bdd1c` | `line_reviewed_with_findings` |
| `.github/workflows/codeql.yml` | 1-84 | `481c7315a36de110df45a17c20583d982409a1099188305be67562a87a48c7ae` | `line_reviewed_with_findings` |
| `.github/workflows/private-beta-windows.yml` | 1-226 | `4e2840847ca210d50497753290b76f8c2af027413c974f0424caeff5a15ade05` | `line_reviewed_with_findings` — independent attestation recorded separately |

Review method:

- Read every physical line of each current workflow with explicit line numbers.
- Compared each current SHA-256 with `COVERAGE_MATRIX.jsonl` before review and recomputed it after evidence gathering.
- Inspected only directly invoked scripts/configuration or directly selected test inventories needed to establish behavior.
- Treated generated maps and prior ledgers as corroboration, never as a substitute for the workflow reads.
- Did not execute the long workflows, publish a release, import credentials, run media, or mark any corroborating file complete.

## Confirmed finding index

| ID | Severity | Confidence | Affected workflow(s) | Short title |
| --- | --- | --- | --- | --- |
| `AUDIT-FIND-W10-001` | P1 | high | deep-audit, phase1-drift | First Python test failure can be overwritten by the second native command |
| `AUDIT-FIND-W10-002` | P2 | high | deep-audit, phase1-drift | Canonical unittest discovery omits 26 pytest tests |
| `AUDIT-FIND-W10-003` | P1 | high | deep-audit, phase1-drift | Browser matrix is incomplete and bypasses strict skip enforcement |
| `AUDIT-FIND-W10-004` | P2 | high | deep-audit, audit-sarif | Push path filters exclude ordinary code changes |
| `AUDIT-FIND-W10-005` | P3 | high | deep-audit, phase1-drift | Generated-check orchestration leaves four available checks outside the named suites |
| `AUDIT-FIND-W10-006` | P3 | high | deep-audit, phase1-drift | PowerShell analysis is unpinned and its helper can soft-skip |
| `AUDIT-FIND-W10-007` | P2 | high | audit-sarif | Scanner failure or findings can leave a green job, including with no SARIF |
| `AUDIT-FIND-W10-008` | P3 | high | audit-sarif | Scanner versions and Semgrep rules are not reproducible |
| `AUDIT-FIND-W10-009` | P2 | high | codeql | CodeQL is artifact-only by default and has no findings gate |
| `AUDIT-FIND-W10-010` | P2 | high | private-beta-windows | Clean-runner pytest dependency is not provisioned by contract |
| `AUDIT-FIND-W10-011` | P1 | high | private-beta-windows | Beta updater endpoint cannot select the beta prerelease |
| `AUDIT-FIND-W10-012` | P1 | high | private-beta-windows | Publish lane omits the repository's strict release acceptance gates |
| `AUDIT-FIND-W10-013` | P1 | high | private-beta-windows | Version, tag, and existing-release identity are not bound before `--clobber` |
| `AUDIT-FIND-W10-014` | P1 | high | private-beta-windows | Signing secrets are exposed job-wide |
| `AUDIT-FIND-W10-015` | P2 | high | private-beta-windows | Concurrent dispatches can race release creation and asset replacement |

## Per-file evidence

### `.github/workflows/deep-audit.yml`

Responsibility and control flow:

- Lines 3-14 define push, weekly schedule, and manual triggers. The only push path is the workflow file itself.
- Lines 16-17 correctly constrain the workflow token to `contents: read`.
- Lines 20-56 run guardrail/static/generated checks and PowerShell analysis on Windows.
- Lines 58-108 provision Python/media/Node and run Python plus non-browser WebView tests.
- Lines 110-186 define 29 isolated browser test IDs and invoke them through raw `python -m unittest`.
- Lines 188-203 aggregate only the two Python/browser job results.
- Lines 205-262 run WebView prework and `npm run check`; the Tauri package script maps that command only to `cargo check`.
- Lines 264-308 run the strict release self-test with `-RequireTests`.
- Lines 310-359 build and verify a temporary release package with tests included.

Positive evidence:

- All reusable GitHub actions are commit-pinned.
- Jobs that exercise local state redirect `TMP`, `TEMP`, and `LOCALAPPDATA` into runner-temporary directories.
- Release self-test explicitly uses `-RequireTests`; package verification uses an explicit runner-temp destination and `-Verify -IncludeTests`.
- The package deletion target is a fixed child of `RUNNER_TEMP`, not a repository/source path.

Candidate findings:

#### `AUDIT-FIND-W10-001` — A failing Python discovery command can be masked

Evidence: lines 101-108 run `python -m unittest discover -s tests/python -q`, then run the non-browser module command, and check `$LASTEXITCODE` only after the second process. PowerShell does not turn an intermediate native-process exit code into a terminating error by itself. A failing first command followed by a passing second command therefore leaves `$LASTEXITCODE = 0`, the step green, and the lines 188-203 aggregate green.

Impact: a real Python regression can merge despite the workflow named “Deep Audit Python and non-browser WebView tests.”

Candidate fix: capture/check each native exit immediately, or route both invocations through a helper that throws on any nonzero result.

#### `AUDIT-FIND-W10-002` — Twenty-six pytest tests are outside canonical discovery

Evidence: line 101 uses only unittest discovery. Current exact test reads show 26 real top-level `def test_*` functions across:

- `tests/python/core/subtitles/test_ass_to_srt_helpers.py` — 7
- `tests/python/desktop/test_marketecture_guard.py` — 11
- `tests/python/tooling/test_dependency_atlas.py` — 2
- `tests/webview/test_webview_touchpoint_ledger.py` — 6

Two additional regex matches in `test_duplicate_test_name_report.py` are fixture text and were excluded from the corrected count. Neither `requirements/dev.txt` nor project dependencies declare pytest.

Impact: successful unittest jobs are not evidence that those subtitle, marketecture, dependency-atlas, and WebView-ledger tests ran.

Candidate fix: declare pytest and run canonical pytest discovery, or convert/integrate those 26 tests into unittest discovery.

#### `AUDIT-FIND-W10-003` — The browser matrix is incomplete and can green on skips

Evidence: lines 118-147 enumerate 29 method IDs from only 23 browser modules. The authoritative current smoke map contains 34 browser modules, leaving 11 absent:

- `test_webview_browser_evidence_control_census`
- `test_webview_browser_lifecycle_reconciliation_smoke`
- `test_webview_browser_pipeline_log_window_control_census`
- `test_webview_browser_queue_launch_completed_smoke`
- `test_webview_browser_root_control_census`
- `test_webview_browser_run_monitor_smoke`
- `test_webview_browser_safe_operator_commands_smoke`
- `test_webview_browser_settings_control_census_smoke`
- `test_webview_browser_settings_field_matrix_smoke`
- `test_webview_browser_settings_generated_control_census`
- `test_webview_browser_shell_launch_queue_rename_control_census`

Line 186 invokes raw unittest. Browser tests raise `unittest.SkipTest` when Node or Chrome/Edge is missing. Raw unittest exits successfully for skips. The directly related common wrapper rejects zero tests and rejects any skip unless explicitly allowed (`webview_browser_smoke_common.ps1` lines 199-219 and 262-271), but the workflow bypasses it.

Impact: the job named as the browser matrix can pass with eleven modules never selected, or with selected tests skipped.

Candidate fix: generate the matrix from `SMOKE_WRAPPER_MAP.json` and invoke the strict common wrapper (or parse and fail on zero/skipped tests in CI).

#### `AUDIT-FIND-W10-004` — Ordinary code pushes do not trigger Deep Audit

Evidence: lines 4-11 list broad branches but restrict push paths to `.github/workflows/deep-audit.yml`. Changes under `src/`, `apps/`, `ops/`, `tests/`, requirements, and package locks do not trigger this workflow on push. Only a workflow-file change, the weekly schedule, or manual dispatch does.

Impact: the “Deep Audit” check is not fresh push evidence for ordinary feature branches or direct main/master code pushes.

Candidate fix: remove the path restriction or enumerate every behavior/test/dependency path whose changes require this workflow.

#### `AUDIT-FIND-W10-005` — The named audit suite omits available freshness checks

Evidence: line 48 invokes the current 19-check `deep-audit` suite. Current `audit_checks.py` includes `run-monitor-schema` and `legacy-reliability-inventory`; it does not include `smoke-wrapper-map`, `duplicate-test-name-report`, `generate_webview_inventory_docs --check`, or `context_slice --check`. The later release self-test compensates for the first two, but no job in this workflow invokes the WebView-inventory-doc or context-slice checks.

Impact: “deep audit” success does not establish freshness for all available repository inventories/navigation surfaces.

Candidate fix: add the four checks to a suitable suite/job, avoiding duplicate execution where the release self-test already supplies coverage.

#### `AUDIT-FIND-W10-006` — PowerShell analysis is not reproducible and can downshift

Evidence: line 52 installs the latest matching gallery module with no required version. The directly invoked checker returns exit 0 with a warning when PSScriptAnalyzer is unavailable (`check_powershell_analysis.ps1` lines 21-24).

Impact: rule behavior can change without a repository diff, and a failed/missing installation path can be mistaken for analysis evidence if the install step does not terminate the job.

Candidate fix: pin the module version and make analyzer absence fatal in CI.

### `.github/workflows/phase1-drift.yml`

Responsibility and control flow:

- Lines 3-9 correctly run for all pull requests and pushes to main/master.
- Lines 10-11 constrain token permission to `contents: read`.
- Lines 14-83 run generated context, naming/change-packet checks, GitHub audit-spine checks, and PowerShell analysis on Windows.
- Lines 85-114 repeat generated checks on Linux/case-sensitive storage and add WebView map/contract checks.
- Lines 116-167 run Python and non-browser WebView tests.
- Lines 169-245 repeat the same 29-ID browser matrix as Deep Audit.
- Lines 247-262 aggregate Python/browser results.
- Lines 264-305 run WebView and Tauri static checks.
- Lines 307-352 run strict release self-test; lines 354-404 build and verify a temporary package.

Positive evidence:

- Pull-request base refs are moved through environment variables and validated before use; GitHub expressions are not interpolated directly into PowerShell commands.
- The Windows and Linux generated-context jobs cover case-insensitive and case-sensitive filesystems.
- All reusable actions are commit-pinned, and release/package jobs use the strict release flags.

Candidate findings:

- `AUDIT-FIND-W10-001`: lines 160-167 repeat the intermediate-native-exit masking bug from Deep Audit.
- `AUDIT-FIND-W10-002`: line 160 repeats unittest-only discovery and omits the same 26 pytest tests.
- `AUDIT-FIND-W10-003`: lines 176-206/244-245 repeat the incomplete 23-of-34-module raw-unittest browser matrix and green-skip path.
- `AUDIT-FIND-W10-005`: `phase1-generated` omits the same four available checks. Release self-test later covers smoke-wrapper-map and duplicate-test-name-report, but WebView inventory docs and context-slice remain absent.
- `AUDIT-FIND-W10-006`: lines 77-83 repeat the unpinned PSScriptAnalyzer install and soft-skip-capable helper.

### `.github/workflows/audit-sarif.yml`

Responsibility and control flow:

- Lines 3-14 define self-file-only push, daily schedule, and manual triggers.
- Lines 16-19 grant read permissions plus `security-events: write`.
- Lines 22-70 install Ruff, create/summarize/upload its SARIF artifact, and optionally upload to code scanning.
- Lines 72-120 do the same for Semgrep using the remote `p/default` ruleset.

Positive evidence:

- GitHub actions are commit-pinned.
- Each scanner has a bounded timeout and attempts to retain SARIF as an ordinary workflow artifact.
- No workflow step auto-creates issues or grants repository write permission.

Candidate findings:

#### `AUDIT-FIND-W10-004` — Ordinary code pushes do not trigger SARIF scanning

Evidence: lines 4-11 restrict push activation to changes to the workflow file itself. Scanner coverage for code changes is delayed until the daily schedule or manual dispatch. CodeQL covers pull requests, but the Semgrep/Ruff SARIF lane is not code-push evidence.

Candidate fix: trigger on behavior/dependency changes or document the lane explicitly as scheduled observation only.

#### `AUDIT-FIND-W10-007` — Scanner failures and findings are non-gating, including no-output failures

Evidence: Ruff and Semgrep execution both set `continue-on-error: true` (lines 39-41 and 89-91). Summaries and both artifact/upload steps are conditional on the SARIF file existing (lines 43-44, 56-57, 64-66, 93-94, 106-107, 114-116). If a scanner crashes before creating its file, every evidence step skips and the job can still be green. Ruff findings also return nonzero but are explicitly tolerated; no later threshold fails on the summarized result count.

Impact: a green workflow can mean “clean,” “findings present,” or “scanner failed and produced no evidence.”

Candidate fix: tolerate a findings exit only after proving valid SARIF exists, fail operational scanner errors/no-output, and add an explicit accepted-findings policy if this is intended as a gate.

#### `AUDIT-FIND-W10-008` — Scanner inputs drift without repository changes

Evidence: lines 36-37 install any Ruff `>=0.8,<1`; lines 86-91 install any Semgrep `>=1,<2` and fetch the mutable remote `p/default` ruleset. Neither resolved versions nor a pinned ruleset digest/config are committed in this lane.

Impact: two runs at the same commit can produce different rules, failures, or findings, reducing audit reproducibility and making count trends ambiguous.

Candidate fix: pin scanner versions and commit/pin the Semgrep configuration used for release evidence.

### `.github/workflows/codeql.yml`

Responsibility and control flow:

- Lines 3-11 run on pull requests, main/master pushes, weekly schedule, and manual dispatch.
- Lines 13-16 grant the expected read plus security-events permission.
- Lines 19-35 define Python, JavaScript/TypeScript, Rust, and Actions matrices.
- Lines 36-53 initialize and analyze with extended/security-quality queries.
- Lines 55-84 summarize local SARIF and upload it as a workflow artifact.

Positive evidence:

- Checkout, init/analyze, and artifact actions are commit-pinned.
- The matrix covers all first-party languages represented by these workflows.
- Operational CodeQL failures remain failing; no `continue-on-error` is present.

Candidate finding:

#### `AUDIT-FIND-W10-009` — Results are artifact-only by default and never gate on findings

Evidence: line 53 defaults `upload` to `never` unless an external repository variable overrides it. Lines 55-84 only summarize counts and retain artifacts; no step compares findings with an accepted baseline or fails above a threshold. Therefore the out-of-box workflow does not create code-scanning alerts/status from results, and a successful analysis with serious findings is still green.

Impact: branch protection cannot consume default CodeQL findings, and reviewers must manually download four artifacts to distinguish a clean scan from one with results.

Candidate fix: default upload to the repository's intended code-scanning mode and define an explicit alert/threshold acceptance policy; if artifact-only is intentional, name/document it as non-gating evidence.

### `.github/workflows/private-beta-windows.yml`

Responsibility and control flow:

- Lines 3-26 expose beta/stable channel, version, release tag, and publish toggle through manual dispatch.
- Lines 28-46 grant `contents: write`, select a channel environment, and place signing/updater/certificate values in job-level environment scope.
- Lines 52-80 validate input shapes and run private-beta preflight.
- Lines 82-115 set up Node/Python/Rust, copy a bundled runtime, import the certificate, and install Tauri dependencies.
- Lines 117-142 generate Tauri config, run a portable-package dry run, execute three pytest files, and run cargo check.
- Lines 144-182 build/sign the NSIS updater, verify Authenticode, generate channel metadata/checksums, and verify local artifacts.
- Lines 184-192 upload workflow artifacts.
- Lines 194-226 optionally create/reuse a GitHub Release and upload assets with `--clobber`.

Positive evidence:

- Input values are routed through environment variables and format-checked before command use.
- Release environments provide a place for GitHub-side reviewer/branch protections.
- Checkout, setup, Rust-toolchain, and artifact actions are commit-pinned.
- Local artifact verification checks NSIS presence, updater signature equality, hashes, channel metadata, absence of MSI, and Authenticode status.

Candidate findings:

#### `AUDIT-FIND-W10-010` — The pytest runtime is not provisioned by contract

Evidence: line 96 invokes `Initialize-CiPythonRuntime.ps1` without `-InstallDependencies`. The target runtime directories are gitignored and absent from a clean checkout. The script copies setup-python into those directories but installs dependencies only when the omitted switch is present (lines 126-133 of the script). Workflow lines 133-137 then invoke that copied runtime with `-m pytest`. Neither `requirements/dev.txt` nor `pyproject.toml` declares pytest. The pytest step is not `continue-on-error` and precedes all signing and publication, so this root fails closed.

Impact: the signed-installer lane depends on an incidental package in the hosted toolcache and can fail before build on a clean or changed runner image, blocking reproducible release availability. It cannot publish an untested artifact from this root alone, so P2 is the appropriate severity.

Candidate fix: declare pytest in the development/test dependency contract and provision the CI runtime with dependencies before invoking it.

#### `AUDIT-FIND-W10-011` — The beta updater endpoint resolves only full releases

Evidence: the workflow publishes beta builds with `--prerelease` (lines 216-218). The directly invoked config generator hard-codes every channel endpoint as `https://github.com/<repo>/releases/latest/download/latest-<channel>.json`. GitHub defines “latest” as the most recent non-prerelease, non-draft full release; prereleases cannot be latest ([GitHub Releases documentation](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)). The preflight test asserts the same broken beta URL rather than exercising a published prerelease.

Impact: a beta client cannot retrieve `latest-beta.json` from the beta prerelease through the configured endpoint; it either receives 404 or resolves a full release that lacks/has stale beta metadata.

Candidate fix: publish channel metadata at a stable channel-specific location or update a non-prerelease channel pointer; add a post-publish HTTP/updater check against the exact configured endpoint.

#### `AUDIT-FIND-W10-012` — A stable or beta release can publish without strict release acceptance

Evidence: the workflow permits `channel: stable` and `publish_release: true`, but never invokes `ops/scripts/release/test.ps1 -RequireTests`. It runs only three productization pytest files and `npm run check`, whose Tauri package definition is only `cargo check`. `build.ps1 -DryRun -Zip` explicitly copies nothing and performs no package verification. The later artifact verifier checks signatures/layout metadata, not core Python, WebView/browser, PowerShell reliability, tool integration, E2E, Rust tests, package open/close, or generated guardrails.

Impact: an operator can publish a correctly signed installer containing regressions that the repository's own release gate would have rejected.

Candidate fix: make strict release self-test, Rust tests, and deployable/package verification prerequisites of the publish step for the exact commit being signed.

#### `AUDIT-FIND-W10-013` — Release identity is not bound before destructive replacement

Evidence: workflow lines 65-69 and preflight lines 58-61 validate `version` and `release_tag` independently but never require `release_tag == app-v<version>`. If a release already exists, lines 200-220 only test that it is viewable; they do not verify its target commit, title, channel/prerelease state, or version. Lines 221-226 then upload current-build assets with `--clobber`. The local artifact verifier checks metadata against the same independent inputs and therefore cannot detect a mismatched pair.

Impact: a validly formatted mismatched input or reused tag can replace assets under a release/tag that points to different source, breaking provenance and updater identity.

Candidate fix: bind tag to version, compare existing release `target_commitish`/tag commit and channel state with `GITHUB_SHA`, and refuse replacement unless an explicit, separately protected rebuild policy is satisfied.

#### `AUDIT-FIND-W10-014` — Signing secrets are available to every step

Evidence: lines 37-46 put updater private key, its password, certificate material, and certificate password in job-level `env`. Those values are therefore visible not only to the certificate import and Tauri build steps that need them, but also to checkout/setup actions, preflight, `npm ci` lifecycle scripts, repository tests, dry-run packaging, and every other process in the job.

Impact: compromise of any executed dependency or repository script in the release lane broadens into release-key/certificate theft.

Candidate fix: scope each secret to the minimum step that consumes it; separate validation/build/publish jobs so untrusted install/test steps run before protected signing credentials are exposed.

#### `AUDIT-FIND-W10-015` — Release publication has no concurrency serialization

Evidence: the workflow defines no top-level or job-level `concurrency` group. Multiple manual dispatches for the same channel/tag can therefore reach the view/create/upload sequence concurrently. That sequence is non-atomic and ends in `--clobber`.

Impact: overlapping runs can race tag creation or replace one another's installer, signature, channel JSON, and checksums, leaving a mixed or last-writer-wins release.

Candidate fix: serialize by repository/channel (and reject duplicate in-progress tag dispatches), then publish immutable versioned assets before advancing a channel pointer.

## Direct corroborating evidence (not marked reviewed/complete)

- `src/mediapipeline/tools/dev/audit_checks.py`
- `ops/scripts/dev/check-github-audit-spine.ps1`
- `ops/scripts/dev/check_powershell_analysis.ps1`
- `ops/scripts/smoke/webview_browser_smoke_common.ps1`
- `ops/scripts/release/Initialize-CiPythonRuntime.ps1`
- `ops/scripts/release/build.ps1`
- `ops/scripts/release/test.ps1` and `test_support.ps1`
- `ops/scripts/release/Test-PrivateBetaReleasePreflight.ps1`
- `ops/scripts/release/New-TauriProductizationConfig.ps1`
- `ops/scripts/release/New-TauriUpdaterChannelJson.ps1`
- `ops/scripts/release/Test-PrivateBetaReleaseArtifact.ps1`
- root `package.json`, Tauri `package.json`, `requirements/dev.txt`, and `pyproject.toml`
- `docs/generated/SMOKE_WRAPPER_MAP.json`
- Exact top-level pytest definitions and browser prerequisite skip sites under `tests/`

## Review incidents (not repository findings)

- One parallel evidence-read batch returned no combined payload because a no-match `rg` discovery exited 1; the reads were repeated separately and succeeded.
- An initial Windows ripgrep call used a positional `test_webview_browser*.py` glob and failed with Windows error 123; the `--glob` retry succeeded.
- A dependency search explicitly named absent `setup.py`, `setup.cfg`, and `tox.ini`, producing an expected nonzero/no-file result; the existing `pyproject.toml` and requirements files supplied the needed evidence.

These incidents did not block coverage, and no candidate finding relies on truncated or failed inspection output.

The complete incident inventory is in `worker-10-ops-workflows-errors.jsonl`; every listed incident records its retry or bounded fallback. The dependency-search no-file result is intentionally represented only by the pre-existing `AUDIT-ERR-VALIDATION-007` record to avoid a duplicate ledger entry.

## Structured-fragment validation

- `finding_record_findings`: no issues across 15 records; IDs are unique and contiguous from W10-001 through W10-015.
- `error_record_findings`: no issues across 14 records; IDs are unique and do not overlap the validation-spine error fragment.
- `review_fragment_findings`: no issues across five baseline-bound rows; the union of row-level finding IDs exactly matches the 15-record finding fragment.
- Review state: five canonical `/root/validation_spine` `line_reviewed_with_findings|pending` first-pass rows; distinct-review completion is supplied by the separate independent attestation.
- Final SHA-256 verification reproduced all five coverage-baseline hashes. `.github/workflows/` remained unmodified.
