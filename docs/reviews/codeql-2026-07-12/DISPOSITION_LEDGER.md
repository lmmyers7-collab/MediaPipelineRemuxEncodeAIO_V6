# CodeQL disposition ledger — 2026-07-12

This ledger covers every alert returned by:

```powershell
gh api --paginate --slurp 'repos/{owner}/{repo}/code-scanning/alerts?state=open&ref=refs/heads/main&per_page=100'
```

The authoritative baseline was `main` at `34e4076720bde468ba9cb221ec617920724c587e` after the non-destructive branch reconciliation. The query returned 1,921 CodeQL alerts in 32 rule groups. Each baseline alert belongs to exactly one row below. “Fixed locally” means the finding was resolved in change packet `MP-CHANGE-2026-0712-005` and required a CodeQL scan of the proposed commit before GitHub could close it. No baseline alert was dismissed, and no query, workflow permission, SARIF upload, or security gate was weakened.

After that baseline, the reconciled changes closed all actionable CodeQL findings except alert 281. A later Semgrep SARIF upload added 29 findings that were not present in the initial inventory. The post-reconciliation addendum below covers every one of those findings and records the current 1,895-alert snapshot at `main` commit `b5e43fff689b8f738086530fad0cc22d1a6efb1e`.

## Security and correctness findings

| Rule | Baseline count | Disposition | Evidence |
| --- | ---: | --- | --- |
| `js/regex/missing-regexp-anchor` | 1 | Security/correctness defect; fixed locally | Alert 5. The accepted full-input pattern is now anchored and its empty-match behavior is covered by WebView checks. |
| `actions/unpinned-tag` | 1 | Supply-chain vulnerability; fixed locally | Alert 1. All workflow actions are pinned to reviewed immutable commit SHAs; the GitHub audit-spine check passes. |
| `py/http-response-splitting` | 1 | Security vulnerability; final sink remediation pending scan | Alert 281 remained after the canonical-origin allowlist fix. Change packet `MP-CHANGE-2026-0712-017` retains that allowlist, rejects CR/LF in header construction, and removes CR/LF again at both final `send_header` sinks using CodeQL's modeled sanitizer. Focused tests inject response-splitting characters and require the safe fallback. |
| `js/overly-large-range` | 1 | Correctness/security issue; fixed locally | Alert 4. The character range typo is replaced with the intended literal hyphen. |
| `js/identity-replacement` | 1 | Correctness/security issue; fixed locally | Alert 900. The no-op replacement was removed. |
| `py/unsafe-cyclic-import` | 10 | Reproducible correctness issue; fixed locally | Alerts 479–488. The coordinator HTTP owner contract is now a local protocol instead of a runtime back-import. |
| `py/uninitialized-local-variable` | 3 | Reproducible correctness issue; fixed locally | Alerts 774–776. Each result variable is initialized or scoped before use. |
| `py/undefined-export` | 3 | Stale compatibility exports; fixed locally | Alerts 2029–2031. Removed names no longer appear in `dry_run_pending.__all__`. |
| `py/inheritance/incorrect-overridden-signature` | 1 | Correctness issue in a test double; fixed locally | Alert 754. The override now preserves the production keyword-only contract. |
| `py/mismatched-multiple-assignment` | 1 | Correctness issue; fixed locally | Alert 345. The maintenance row is shape-checked before unpacking. |
| `js/superfluous-trailing-arguments` | 3 | Correctness issue; fixed locally | Alerts 901–903. Removed arguments that the table helper cannot consume. |
| `js/comparison-between-incompatible-types` | 1 | Correctness issue; fixed locally | Alert 279. Removed the impossible empty-string comparison. |
| `js/regex/duplicate-in-character-class` | 1 | Correctness issue; fixed locally | Alert 18. Removed the duplicate character from the queue pattern. |
| `py/comparison-of-identical-expressions` | 4 | Correctness issue; fixed locally | Alerts 797–799 and 2065. Non-finite checks now use `math.isfinite`. |
| `py/implicit-string-concatenation-in-list` | 12 | Maintainability/correctness issue; fixed locally | Alerts 806–817. Intended command fragments are joined explicitly. |
| `py/multiple-definition` | 4 | Maintainability issue; fixed locally | Alerts 759–762. Removed overwritten startup-progress and source-id assignments. |
| `py/unnecessary-lambda` | 6 | Maintainability issue; fixed locally | Alerts 800–805. Direct callable references preserve behavior. |
| `py/imprecise-assert` | 4 | Test-diagnostic issue; fixed locally | Alerts 755–758. Assertions now report informative membership/equality failures. |
| `py/unused-local-variable` | 11 | Three defects fixed; eight stale/intentional | Alert 763 exposed an uninitialized folder-selection message and is fixed with a regression test. Alerts 769–770 were genuinely dead assignments and are removed. The remaining values are consumed on alternate split-module or exception paths, or intentionally retain an mDNS browser for its lifetime; they are not runtime defects. |
| `js/trivial-conditional` | 4 | One fixed locally, one stale, two intentional compatibility checks | Alert 7 now handles explicit `null`. Alert 8 was already fixed in the reconciled refactor history. Alerts 9–10 are the same `MutationObserver` availability guard required by non-browser/mock environments. |

## Intentional compatibility and non-defect findings

| Rule | Baseline count | Disposition | Evidence |
| --- | ---: | --- | --- |
| `py/unused-import` | 806 | Intentional compatibility/export pattern | Split Python façades re-export parent-owned names through star-import compatibility seams. Ruff’s narrow per-file `F401`/`F405` exceptions document these exact surfaces; removing them would break public imports. |
| `js/unused-local-variable` | 715 | Intentional ordered-script compatibility pattern | Backend-served WebView files are plain ordered scripts. Parent declarations are shared lexical bindings used by child slices; redeclaring them in children would create duplicate-binding failures. |
| `py/ineffectual-statement` | 114 | Intentional export/type-visibility pattern | These statements retain names across split façade/type-checking boundaries. Generated module maps and import-contract tests exercise the public surfaces. |
| `js/useless-assignment-to-local` | 82 | Intentional startup fallback pattern | Parent scripts initialize safe fallbacks before ordered child scripts replace them. Removing the defaults would turn partial-load failures into reference errors and weaken startup diagnostics. |
| `py/empty-except` | 64 | Intentional best-effort isolation; not a hidden failure path | The sites suppress cleanup, optional telemetry, or lossy parsing failures while returning explicit fallback state. Mutation and publish failures use separate fail-closed paths and are not represented by this group. |
| `py/unused-global-variable` | 30 | Intentional compatibility/export pattern | Split registry/config/model modules publish globals consumed by sibling façades or star-import compatibility layers. |
| `py/polluting-import` | 16 | Intentional compatibility/export pattern | These are the documented split-module star-import seams covered by Ruff per-file exceptions and import tests. |
| `py/import-and-import-from` | 14 | Intentional compatibility/export pattern | Modules combine a compatibility export with a direct typed import; the apparent duplication preserves both runtime and public import contracts. |
| `py/catch-base-exception` | 2 | Intentional containment; false positive as a defect | Alert 282 transfers any scanner-thread termination into the owner thread’s result channel; alert 283 is test cleanup that must restore state even for non-`Exception` failures. Neither silently reports success. |
| `js/missing-variable-declaration` | 2 | Intentional ordered-script compatibility pattern | Alerts 904–905 assign `lastSnapshot` and `lastStdoutTail`, declared once in parent `app.js`; child redeclaration would break shared state. |
| `py/conflicting-attributes` | 2 | Intentional mixin/test override pattern | Alerts 751–752 are cooperative mixin attributes whose selected implementation is fixed by façade MRO and covered by façade tests. |
| `rust/unused-variable` | 1 | CodeQL false positive | Alert 2’s `stream_name` is consumed by Rust format-string capture in `eprintln!`; Cargo builds and tests prove the binding is used. |

## Post-reconciliation Semgrep addendum

The Semgrep snapshot was uploaded from commit `6e1124c14f30da20c4e42f2d27af0b8885502879`, so all 29 findings were stale relative to `main` before this final packet. They remain classified on their actual code paths rather than being assumed resolved by age. A manually dispatched `Audit SARIF` run on the review branch and again on merged `main` must prove the updated analysis commit and result set; the workflow's green status alone is insufficient because scan and upload steps are configured `continue-on-error`.

### Remediated Semgrep findings

| Alerts | Rule | Count | Disposition | Evidence |
| --- | --- | ---: | --- | --- |
| 826–830 | `dependabot-missing-cooldown` | 5 | Supply-chain hardening; fixed in `MP-CHANGE-2026-0712-017` | Each configured ecosystem now has a seven-day version-update cooldown. GitHub documents that cooldown does not delay Dependabot security updates. |
| 876, 2099 | `incomplete-sanitization` | 2 | False security premise but avoidable partial replacement; fixed | The values are backend-authored display percentages, not escaping boundaries. Both parsers now replace every percent marker before numeric parsing, preserving their display-only role. |
| 879 | `detect-non-literal-regexp` | 1 | Realistic WebView responsiveness issue; fixed | A staged file-override title pattern previously constructed a regular expression. It now uses a literal `*`/`?` wildcard matcher with backend-owned 256-character pattern and 1,024-character probed-title limits mirrored fail-closed in the WebView. Runtime tests cover wildcard, case-folding, literal regex metacharacters, over-limit rejection, and non-matches. |
| 2100 | `detect-non-literal-regexp` | 1 | False positive as an injection path; avoidable dynamic expression fixed | All prefixes are fixed internal literals (`succeeded`, `remaining`, `errors`, `skipped`). The helper now parses with a static expression and compares the prefix literally, while the existing compact-progress smoke proves rendered counts. |

### Evidence-backed Semgrep false positives

These findings are eligible for GitHub dismissal with reason `false_positive` only after a fresh merged-main Semgrep upload reproduces them at the current locations.

| Alerts | Rule | Count | Evidence |
| --- | --- | ---: | --- |
| 880–882 | `detect-non-literal-regexp` | 3 | `check-webview-command-boundary.mjs` is a repository developer audit. `field` values are fixed source literals, and `route` values come from repository-owned route contracts and are escaped before expression construction; no operator or network input reaches the patterns. |
| 883–885 | `tainted-sql-string` | 3 | The flagged formatted strings are native path-picker dialog labels/descriptions passed to picker adapters. These modules do not import Django or a database API, and the values are never executed as SQL. |
| 886 | `request-data-write` | 1 | The stage payload is a validated Pydantic `StageRequest`, serialized as JSON, and written through an OS-created `mkstemp` descriptor. The caller cannot choose the temporary path; Local API JSON bodies are capped at 1,000,000 bytes. |
| 887 | `directly-returned-format-string` | 1 | `filename_preview.py` is a pure rename-domain formatter, not a Flask route. It returns a filename string inside a typed backend payload; no HTML response or template sink exists in the module. |
| 888–889 | formatted/raw SQL | 2 | `_sqlite_table_count` has one call site and it passes the literal `completed_jobs`. The query opens the project state database read-only; no request-controlled table identifier reaches it. |
| 890–892 | formatted/raw SQL | 3 | `StateDb` iterates table identifiers from fixed tuples or the fixed `limits` mapping (`commands`, `events`, `queue_snapshots`, `completed_jobs`). Row limits remain parameterized SQL values. |
| 893 | `dynamic-urllib-use-detected` | 1 | The HTTP helper is used by the worker client only after `WorkerCoordinatorUrl` passes `validate_coordinator_url`, which permits only HTTP/HTTPS base URLs with a host and explicit port and rejects paths, queries, fragments, and userinfo. |
| 894–895 | `dynamic-urllib-use-detected` | 2 | Both probe call paths first normalize the coordinator URL through the same HTTP/HTTPS-only validator before the adapter invokes `urlopen`. |
| 896–899 | `dynamic-urllib-use-detected` | 4 | These are smoke-only utilities. Their URLs are built from a locally created `LocalApiServer`; each sink is explicitly annotated `# noqa: S310 - localhost smoke server`, and no external URL input is accepted. |

## Remote closure gate

The local fixes are not eligible for dismissal. Alert 281 must close through a full CodeQL workflow on a reviewable commit. Semgrep must be manually dispatched for the review branch and merged `main`, and the accepted code-scanning analysis commit must be verified because the audit workflow does not run for ordinary source pushes. Any finding remaining after those scans must be re-fetched and compared to this ledger by rule, location, and commit before a precise GitHub disposition is considered.
