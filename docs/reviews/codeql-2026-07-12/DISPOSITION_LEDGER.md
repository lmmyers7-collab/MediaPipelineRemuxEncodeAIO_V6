# CodeQL disposition ledger — 2026-07-12

This ledger covers every alert returned by:

```powershell
gh api --paginate --slurp 'repos/{owner}/{repo}/code-scanning/alerts?state=open&ref=refs/heads/main&per_page=100'
```

The authoritative baseline was `main` at `34e4076720bde468ba9cb221ec617920724c587e` after the non-destructive branch reconciliation. The query returned 1,921 CodeQL alerts in 32 rule groups. Each baseline alert belongs to exactly one row below. “Fixed locally” means the finding was resolved in change packet `MP-CHANGE-2026-0712-005` and required a CodeQL scan of the proposed commit before GitHub could close it. No baseline alert was dismissed, and no query, workflow permission, SARIF upload, or security gate was weakened.

After that baseline, the reconciled changes closed the actionable CodeQL findings in reviewable packets. PR 34 merged the final security and Semgrep remediations to `main` as `6f1a1b7ed5cd4815daa33b3f07a793178b7c4b00`. The exact-commit CodeQL scan closed alert 281 as fixed and left 1,865 open CodeQL findings in 14 compatibility or maintainability groups: 1,776 notes, 89 warnings, zero errors, and zero security-severity findings. The exact-commit Semgrep scan closed all nine actionable findings as fixed; its 20 reproduced false positives were dismissed with precise path-specific evidence, leaving zero open Semgrep findings. A final count reconciliation then identified seven low-priority dead assignments that are removed in `MP-CHANGE-2026-0712-019` rather than being mislabeled intentional.

## Security and correctness findings

| Rule | Baseline count | Disposition | Evidence |
| --- | ---: | --- | --- |
| `js/regex/missing-regexp-anchor` | 1 | Security/correctness defect; fixed locally | Alert 5. The accepted full-input pattern is now anchored and its empty-match behavior is covered by WebView checks. |
| `actions/unpinned-tag` | 1 | Supply-chain vulnerability; fixed locally | Alert 1. All workflow actions are pinned to reviewed immutable commit SHAs; the GitHub audit-spine check passes. |
| `py/http-response-splitting` | 1 | Security vulnerability; fixed | Alert 281 remained after the canonical-origin allowlist fix. Change packet `MP-CHANGE-2026-0712-017` retains that allowlist, rejects CR/LF in header construction, and removes CR/LF again at both final `send_header` sinks using CodeQL's modeled sanitizer. Focused tests inject response-splitting characters and require the safe fallback. Merged-main CodeQL run 29218329059 closed the alert as fixed, not dismissed. |
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
| `py/unused-local-variable` | 11 | Three fixed in the initial reconciliation; seven final cleanups; one intentional lifetime binding | Alert 763 exposed an uninitialized folder-selection message and is fixed with a regression test. Alerts 769–770 were dead assignments removed in the initial packet. The merged-main reconciliation found alerts 764–768 and 2045–2046 were also unread assignments rather than alternate-path values; `MP-CHANGE-2026-0712-019` removes them. Alert 771 intentionally retains the mDNS `ServiceBrowser` for its required lifetime. |
| `js/trivial-conditional` | 4 | One fixed; three intentional compatibility/defensive guards | Alert 8 closed after the reconciled refactor. Alert 7 is a legacy primitive-context fallback (`context || lastStdoutTail`) retained for compatibility even though current callers pass objects. Alerts 9–10 are two spans of the reusable table helper's defensive `!table || !tbody` guard; current callers prove the guard redundant, but retaining it keeps the helper fail-closed for partial DOMs. |

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
| `py/import-and-import-from` | 14 | Conventional module/member access; non-defect | The findings combine a module import with direct member imports for `ctypes`, JSON decoding, unittest mocks, or preset-policy tests. Both access forms are used; this is not a duplicate runtime import defect. Alerts 467–470 disappeared on the fresh merged-main scan, leaving ten current findings. |
| `py/catch-base-exception` | 2 | Intentional containment; false positive as a defect | Alert 282 transfers any scanner-thread termination into the owner thread’s result channel; alert 283 is test cleanup that must restore state even for non-`Exception` failures. Neither silently reports success. |
| `js/missing-variable-declaration` | 2 | Intentional ordered-script compatibility pattern | Alerts 904–905 assign `lastSnapshot` and `lastStdoutTail`, declared once in parent `app.js`; child redeclaration would break shared state. |
| `py/conflicting-attributes` | 2 | Intentional mixin/test override pattern | Alerts 751–752 are cooperative mixin attributes whose selected implementation is fixed by façade MRO and covered by façade tests. |
| `rust/unused-variable` | 1 | CodeQL false positive | Alert 2’s `stream_name` is consumed by Rust format-string capture in `eprintln!`; Cargo builds and tests prove the binding is used. |

## Post-merge CodeQL reconciliation

Merged-main run 29218329059 analyzed `refs/heads/main` at `6f1a1b7ed5cd4815daa33b3f07a793178b7c4b00` with CodeQL 2.26.0. Python analysis 1469717156, JavaScript/TypeScript analysis 1469713258, Rust analysis 1469712881, and Actions analysis 1469711452 completed without warnings or errors. No new open alert was created by the scan. The 1,865 remaining alerts belong to exactly these rows:

| Current rule | Count | Current disposition |
| --- | ---: | --- |
| `py/unused-import` | 806 | Intentional split-façade compatibility exports covered by narrow Ruff exceptions and import-contract tests. |
| `js/unused-local-variable` | 715 | Intentional shared lexical bindings across ordered WebView scripts. |
| `py/ineffectual-statement` | 124 | Type/export visibility declarations. Alerts 2101–2110 are specifically the ellipsis bodies of `_CoordinatorDispatcherProtocol` methods in `coordinator_parts/http_server.py`; they are typing-only declarations, not runtime statements. |
| `js/useless-assignment-to-local` | 82 | Intentional safe startup fallbacks replaced by ordered child scripts. |
| `py/empty-except` | 64 | Best-effort cleanup, optional telemetry, or lossy parsing fallbacks; mutation and publish failures remain fail-closed elsewhere. |
| `py/unused-global-variable` | 30 | Intentional registry/config/model exports consumed through split compatibility layers. |
| `py/polluting-import` | 16 | Documented star-import compatibility seams covered by import tests. |
| `py/import-and-import-from` | 10 | Both module and member access forms are used; not a runtime or compatibility defect. Alerts 467–470 are fixed/stale after the fresh scan. |
| `py/unused-local-variable` | 8 | Alerts 764–768 and 2045–2046 are actionable unread assignments removed by `MP-CHANGE-2026-0712-019`; alert 771 intentionally retains the mDNS browser lifetime binding. |
| `js/trivial-conditional` | 3 | Alert 7 is a legacy primitive-context fallback; alerts 9–10 are the reusable table helper's defensive partial-DOM guard. |
| `js/missing-variable-declaration` | 2 | Intentional child-script assignment to parent-owned shared state. |
| `py/catch-base-exception` | 2 | Intentional termination transfer and test cleanup containment; neither reports false success. |
| `py/conflicting-attributes` | 2 | Cooperative mixin/test overrides selected by tested façade MRO. |
| `rust/unused-variable` | 1 | False positive: Rust format-string capture consumes `stream_name`; Cargo check/tests/build pass. |

The four count deltas from the initial ledger are fully accounted for: alerts 2101–2110 added the Protocol ellipsis findings; alerts 467–470 closed; alerts 763, 769, and 770 closed; and trivial-conditional alert 8 closed. The final seven dead-assignment removals require a fresh CodeQL scan of `MP-CHANGE-2026-0712-019`; they are not eligible for dismissal.

## Post-reconciliation Semgrep addendum

The initial Semgrep snapshot was uploaded from commit `6e1124c14f30da20c4e42f2d27af0b8885502879`, so all 29 findings were stale relative to `main` before the final packet. They were classified on their actual code paths rather than assumed resolved by age. Manually dispatched `Audit SARIF` runs on the review branch and merged `main` proved the updated analysis commits and result sets; the workflow's green status alone was not accepted because scan and upload steps are configured `continue-on-error`.

### Remediated Semgrep findings

| Alerts | Rule | Count | Disposition | Evidence |
| --- | --- | ---: | --- | --- |
| 826–830 | `dependabot-missing-cooldown` | 5 | Supply-chain hardening; fixed in `MP-CHANGE-2026-0712-017` | Each configured ecosystem now has a seven-day version-update cooldown. GitHub documents that cooldown does not delay Dependabot security updates. |
| 876, 2099 | `incomplete-sanitization` | 2 | False security premise but avoidable partial replacement; fixed | The values are backend-authored display percentages, not escaping boundaries. Both parsers now replace every percent marker before numeric parsing, preserving their display-only role. |
| 879 | `detect-non-literal-regexp` | 1 | Realistic WebView responsiveness issue; fixed | A staged file-override title pattern previously constructed a regular expression. It now uses a literal `*`/`?` wildcard matcher with backend-owned 256-character pattern and 1,024-character probed-title limits mirrored fail-closed in the WebView. Runtime tests cover wildcard, case-folding, literal regex metacharacters, over-limit rejection, and non-matches. |
| 2100 | `detect-non-literal-regexp` | 1 | False positive as an injection path; avoidable dynamic expression fixed | All prefixes are fixed internal literals (`succeeded`, `remaining`, `errors`, `skipped`). The helper now parses with a static expression and compares the prefix literally, while the existing compact-progress smoke proves rendered counts. |

### Evidence-backed Semgrep false positives

Merged-main Semgrep analysis 1469716375 reproduced these 20 findings at the exact current locations. Each was dismissed with GitHub reason `false positive` and a path-specific explanation; none of the nine actionable alerts was dismissed.

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

## Remote closure evidence

- PR 34 passed all 44 checks and merged normally to protected `main` as `6f1a1b7ed5cd4815daa33b3f07a793178b7c4b00`.
- PR CodeQL run 29217701077 reported zero findings across Python, JavaScript/TypeScript, Rust, and Actions; alert 281 did not reproduce on the PR merge ref.
- Merged-main CodeQL run 29218329059 passed all four languages and closed alert 281 as fixed at 2026-07-13T01:57:26Z.
- Review-branch Audit SARIF run 29217706423 uploaded Semgrep analysis 1469682125 at the exact PR head. It contained the expected 20 false positives and none of the nine remediated findings.
- Merged-main Audit SARIF run 29218334585 uploaded Semgrep analysis 1469716375 at the exact merge commit. It closed alerts 826–830, 876, 879, 2099, and 2100 as fixed. Alerts 880–899 were then dismissed as false positives with exact evidence, leaving zero open Semgrep findings.
- No CodeQL query, workflow permission, SARIF upload behavior, branch protection, or required gate was weakened.
