# Audit Error Ledger

Every nonzero audit command, parser/analysis error, confidence-affecting warning, missing dependency, output truncation, skip/downshift, and external-evidence gap is recorded here. Expected negative-path results remain evidence; they are not product defects unless linked to a confirmed finding.

- Recorded events: **442**
- Events currently blocking some coverage: **44**

## Classification counts

| Classification | Events |
|---|---:|
| confirmed repository defect | 34 |
| environment/setup issue | 173 |
| expected negative-path result | 45 |
| informational warning | 156 |
| missing external fixture | 6 |
| sandbox/permission failure | 1 |
| test failure | 27 |

## Event index

| ID | Phase | Exit | Classification | Coverage blocked | Disposition |
|---|---|---:|---|---|---|
| `AUDIT-ERR-COORD-001` | baseline | 0 | informational warning | no | mitigated by targeted authoritative reads |
| `AUDIT-ERR-COORD-002` | baseline | 0 | informational warning | no | closed after focused rereads |
| `AUDIT-ERR-COORD-003` | baseline | n/a | environment/setup issue | no | closed by valid retry |
| `AUDIT-ERR-COORD-004` | coverage-universe | 1 | expected negative-path result | no | closed after controlled baseline refresh and clean stale-hash check |
| `AUDIT-ERR-COORD-005` | baseline | 0 | informational warning | no | recorded limitation; not used as sole completion authority |
| `AUDIT-ERR-COORD-006` | coordination | n/a | expected negative-path result | no | closed; normal bounded monitoring result |
| `AUDIT-ERR-COORD-007` | coordination | n/a | expected negative-path result | no | closed; normal bounded monitoring result |
| `AUDIT-ERR-COORD-008` | validation-spine | 0 | informational warning | no | closed after source-backed correction |
| `AUDIT-ERR-COORD-009` | coverage-universe | 1 | confirmed repository defect | no | closed after unit proof, independent review, and clean global path/hash check |
| `AUDIT-ERR-COORD-010` | line-level-review-worker-02 | 1 | expected negative-path result | no | recorded; continue indirect test-coverage tracing |
| `AUDIT-ERR-COORD-011` | prior-finding-reconciliation-settings | 1 | expected negative-path result | no | fixture invocation corrected before retry; no product conclusion from this failure |
| `AUDIT-ERR-COORD-012` | prior-finding-reconciliation-settings | 1 | environment/setup issue | no | closed as an audit path-assumption error; product contradiction remains independently evidenced |
| `AUDIT-ERR-COORD-013` | line-level-review-worker-02 | 1 | environment/setup issue | no | audit command construction corrected; config-loader negative-path test search remains in progress |
| `AUDIT-ERR-COORD-014` | line-level-review-worker-02 | 1 | expected negative-path result | no | navigation correction recorded; canonical subprocess result contract review continues |
| `AUDIT-ERR-COORD-015` | line-level-review-worker-02 | 1 | environment/setup issue | no | audit quoting error recorded and corrected; no product conclusion from this failure |
| `AUDIT-ERR-COORD-016` | line-level-review-worker-02 | 1 | environment/setup issue | no | audit command syntax corrected; no product conclusion |
| `AUDIT-ERR-COORD-017` | state-authority-map | 1 | environment/setup issue | no | closed navigation/path correction; no product conclusion from the missing guessed path |
| `AUDIT-ERR-COORD-018` | semantic-review-coordination | n/a | informational warning | no | closed informational coordination timeout |
| `AUDIT-ERR-COORD-019` | process-lifecycle-map | 0 | informational warning | no | open generated-context drift already deduplicated under AUDIT-FIND-COV-001 |
| `AUDIT-ERR-COORD-020` | workflow-finding-reconciliation | n/a | environment/setup issue | no | closed after wrapper correction; no repository command or mutation occurred |
| `AUDIT-ERR-COORD-021` | independent-second-review-reconciliation | n/a | environment/setup issue | no | closed wrapper limitation; no audit evidence or source file changed |
| `AUDIT-ERR-COORD-022` | dependency-and-cycle-map | 0 | environment/setup issue | no | closed command-formatting issue; no repository file changed and no cycle claim relies on the erroring labels |
| `AUDIT-ERR-COORD-023` | dependency-and-cycle-map | 1 | confirmed repository defect | no | closed as reproduced and root-cause-mapped; linked repository finding remains open |
| `AUDIT-ERR-COORD-024` | dependency-and-cycle-map | 1 | environment/setup issue | no | closed command-scope error; useful matches retained only as navigation evidence |
| `AUDIT-ERR-COORD-025` | dependency-and-cycle-map | 1 | expected negative-path result | no | closed expected no-match result |
| `AUDIT-ERR-COORD-026` | audit-ledger-second-review-remediation | 1 | test failure | no | closed after deterministic serialization correction and successful full-suite retry |
| `AUDIT-ERR-COORD-027` | audit-fragment-integrity | 0 | informational warning | no | closed after fragment correction and focused schema validation; combined final fragment validation still required at handoff |
| `AUDIT-ERR-COORD-028` | dependency-and-cycle-map | 0 | informational warning | yes | open aggregate-count freeze requirement; structural finding remains confirmed |
| `AUDIT-ERR-COORD-029` | failure-and-recovery-map-synthesis | 0 | informational warning | no | closed after owner correction |
| `AUDIT-ERR-COORD-030` | independent-second-review-coordination | 0 | environment/setup issue | no | closed after distinct W02 attestation and official join validation |
| `AUDIT-ERR-COORD-031` | module-ownership-map | 1 | environment/setup issue | no | closed after clean retry |
| `AUDIT-ERR-COORD-032` | module-ownership-map | 0 | informational warning | no | closed after immediate documentation correction |
| `AUDIT-ERR-COORD-033` | audit-ledger-remediation-freeze | 1 | environment/setup issue | no | closed after clean hash/size retry |
| `AUDIT-ERR-COORD-034` | independent-second-review-integrity | 0 | environment/setup issue | no | closed after distinct W10 attestation and official join validation |
| `AUDIT-ERR-COORD-035` | audit-independent-attestation-hardening | n/a | environment/setup issue | no | closed after clean fragment creation; no partial file change |
| `AUDIT-ERR-COORD-036` | audit-independent-attestation-hardening | 1 | test failure | no | closed after fixture correction and branch exercise |
| `AUDIT-ERR-COORD-037` | audit-independent-attestation-hardening | 1 | test failure | no | closed after implementation correction and clean full-suite retry |
| `AUDIT-ERR-COORD-038` | audit-ledger-schema-migration | 1 | test failure | no | closed after central migration and clean mirror/invariant check |
| `AUDIT-ERR-COORD-039` | agent-handoff-polling | n/a | environment/setup issue | no | closed after correcting the polling method |
| `AUDIT-ERR-COORD-040` | audit-ledger-schema-migration | 0 | test failure | no | closed after all stale fragments normalized and live reconstruction passed |
| `AUDIT-ERR-COORD-041` | broad-partition-agent-rotation | n/a | environment/setup issue | no | closed after local migration and successful existing-agent rotation |
| `AUDIT-ERR-COORD-042` | git-index-blob-audit-hardening | 1 | test failure | no | closed after implementation correction and clean full-suite retry |
| `AUDIT-ERR-COORD-043` | audit-ledger-schema-migration | 0 | test failure | no | closed after complete evidence-fragment normalization and clean reconstruction |
| `AUDIT-ERR-COORD-044` | audit-ledger-independent-rereview | n/a | environment/setup issue | no | closed by handing the local correctness review to the live child agent |
| `AUDIT-ERR-COORD-045` | windows-path-alias-hardening | n/a | environment/setup issue | no | closed after clean scoped retry and validation |
| `AUDIT-ERR-COORD-046` | worktree-root-boundary-hardening | n/a | environment/setup issue | no | closed after scoped retry and clean validation |
| `AUDIT-ERR-COORD-047` | audit-baseline-progress-accuracy | 1 | test failure | no | closed after implementation correction, rollback proof, and clean full-suite retry |
| `AUDIT-ERR-COORD-048` | audit-error-ledger-maintenance | n/a | environment/setup issue | no | closed after exact raw-string patch retry |
| `AUDIT-ERR-COORD-049` | audit-error-ledger-maintenance | n/a | environment/setup issue | no | closed after contextual patch retry |
| `AUDIT-ERR-COORD-050` | broad-partition-orientation | 1 | environment/setup issue | no | closed after corrected inventory and assignment-source read |
| `AUDIT-ERR-COORD-051` | audit-ledger-independent-rereview | 1 | environment/setup issue | no | closed after post-publication enumeration and bounded read |
| `AUDIT-ERR-COORD-052` | broad-partition-agent-rotation | n/a | environment/setup issue | no | closed after successful existing-agent reassignment |
| `AUDIT-ERR-COORD-053` | audit-ledger-schema-migration | 1 | environment/setup issue | no | closed after corrected direct-function call |
| `AUDIT-ERR-COORD-054` | audit-ledger-independent-rereview | 1 | environment/setup issue | no | closed after fragment restoration and clean exact-hash validator chain |
| `AUDIT-ERR-COORD-055` | audit-ledger-schema-migration | 0 | test failure | no | closed after exact W02 path-local reconciliation and clean official retry |
| `AUDIT-ERR-COORD-056` | audit-ledger-independent-rereview | n/a | environment/setup issue | no | closed after corrected attestation passed official join validation |
| `AUDIT-ERR-COORD-057` | audit-ledger-schema-migration | 0 | test failure | no | closed after exact-set reconciliation and clean independent live reconstruction |
| `AUDIT-ERR-COORD-058` | audit-ledger-schema-migration | n/a | environment/setup issue | no | closed after original-reviewer alignment and clean fragment validation |
| `AUDIT-ERR-COORD-059` | audit-ledger-independent-rereview | 1 | environment/setup issue | no | closed after post-publication exact-row validation |
| `AUDIT-ERR-COORD-060` | audit-ledger-schema-migration | 1 | environment/setup issue | no | closed after syntax-correct discovery retry |
| `AUDIT-ERR-COORD-061` | broad-partition-agent-rotation | n/a | environment/setup issue | no | closed after successful post-checkpoint W05 agent rotation |
| `AUDIT-ERR-COORD-062` | audit-ledger-independent-rereview | n/a | environment/setup issue | no | closed as redundant handoff failure |
| `AUDIT-ERR-COORD-063` | broad-partition-checkpoint-reconciliation | 1 | environment/setup issue | no | closed after syntax-correct read-only census |
| `AUDIT-ERR-COORD-064` | broad-partition-checkpoint-reconciliation | 0 | informational warning | no | closed after owning-reviewer normalization and clean preparation retry |
| `AUDIT-ERR-COORD-065` | map-gap-reconciliation | 1 | environment/setup issue | no | closed after syntax-correct read-only scan |
| `AUDIT-ERR-COORD-066` | map-gap-reconciliation | 0 | informational warning | no | closed after one-line count correction |
| `AUDIT-ERR-COORD-067` | independent-review-capacity-planning | 1 | environment/setup issue | no | closed after syntax-correct read-only census |
| `AUDIT-ERR-COORD-068` | prior-audit-map-reconciliation | 0 | informational warning | no | closed after same-file status/closure alignment |
| `AUDIT-ERR-COORD-069` | worker-04-publish-completed-rename | n/a | environment/setup issue | no | closed after durable fresh-context source checkpoint |
| `AUDIT-ERR-COORD-070` | worker-13-p1-independent-review | 1 | environment/setup issue | no | closed after syntax-correct exact-byte census |
| `AUDIT-ERR-COORD-071` | worker-04-publish-completed-rename | n/a | environment/setup issue | no | closed after replacement reviewer source checkpoint |
| `AUDIT-ERR-COORD-072` | worker-05-p1-independent-review | 1 | environment/setup issue | no | closed after correct generated-summary read |
| `AUDIT-ERR-COORD-073` | worker-04-publish-completed-rename | n/a | environment/setup issue | no | closed after separately spawned reviewer checkpoint |
| `AUDIT-ERR-COORD-074` | worker-05-p1-independent-review | 1 | environment/setup issue | no | closed after attributable individual retries |
| `AUDIT-ERR-COORD-075` | worker-05-p1-independent-review | 1 | expected negative-path result | no | closed after exit-neutral negative-coverage census |
| `AUDIT-ERR-COORD-076` | worker-05-p1-independent-review | 0 | test failure | yes | open pending schema corrections and clean join |
| `AUDIT-ERR-COORD-077` | worker-05-p1-independent-review | 0 | test failure | yes | open pending W09 fragment stabilization |
| `AUDIT-ERR-COORD-078` | worker-15-p1-independent-review | 1 | environment/setup issue | no | closed after exact artifact and prerequisite discovery |
| `AUDIT-ERR-COVERAGE-001` | coverage-universe | n/a | environment/setup issue | no | Agent-orchestration input error only; retain as complete command-error evidence. |
| `AUDIT-ERR-COVERAGE-002` | coverage-universe | 1 | confirmed repository defect | yes | Refresh summaries through repository tooling, rerun --check, and record any remaining missing/stale paths before claiming generated-context coverage. |
| `AUDIT-ERR-COVERAGE-003` | coverage-universe | 1 | confirmed repository defect | yes | Regenerate the three outputs only through the canonical generator after source summaries settle, then rerun --check. |
| `AUDIT-ERR-COVERAGE-004` | coverage-universe | 1 | expected negative-path result | no | Expected search miss, not a repository failure. |
| `AUDIT-ERR-COVERAGE-005` | coverage-universe | 1 | expected negative-path result | no | Search-scope miss resolved by a broader query; no remaining coverage impact. |
| `AUDIT-ERR-COVERAGE-006` | coverage-universe | 1 | informational warning | yes | Generate and validate the missing summary before satisfying the generated-summary completion gate. |
| `AUDIT-ERR-COVERAGE-007` | coverage-universe | 0 | informational warning | no | Preserve as input-integrity warning; do not infer missing trailing requirements beyond the supplied objective. |
| `AUDIT-ERR-COVERAGE-008` | coverage-universe | 0 | informational warning | yes | Quiesce concurrent edits, refresh the coverage ledger, and rerun hash and generated-context checks before using the snapshot as completion proof. |
| `AUDIT-ERR-COVERAGE-009` | coverage-universe | 0 | confirmed repository defect | yes | Add a strict completion mode that recomputes hashes, rejects every required nonterminal row, validates category/status compatibility, and enforces independent high-risk review. |
| `AUDIT-ERR-COVERAGE-010` | coverage-universe | 0 | confirmed repository defect | yes | Regenerate PROJECT_INDEX after summaries stabilize and require zero source-hash mismatches in final coverage validation. |
| `AUDIT-ERR-COVERAGE-011` | coverage-universe | 0 | informational warning | no | Keep Git as the authoritative outer universe and use PROJECT_INDEX only for enrichment; never use index count as exhaustive coverage proof. |
| `AUDIT-ERR-COVERAGE-012` | coverage-universe | 0 | informational warning | no | Do not inherit semantic completion from the prior audit; reconcile findings and symbols path by path against current hashes. |
| `AUDIT-ERR-COVERAGE-013` | coverage-universe | 0 | confirmed repository defect | yes | Restore one-to-one current source/summary/index reconciliation where required, document intentional exclusions, and rerun both canonical --check commands. |
| `AUDIT-ERR-PRIOR-001` | prior-audit-reconciliation | 1 | environment/setup issue | no | Resolved by settled orchestration; no reconciliation evidence remained unavailable. |
| `AUDIT-ERR-PRIOR-002` | prior-audit-reconciliation | 1 | expected negative-path result | no | Expected no-match result; relevant packets were recovered by content search. |
| `AUDIT-ERR-PRIOR-003` | prior-audit-reconciliation | 1 | environment/setup issue | no | Resolved as a Windows wildcard invocation error. |
| `AUDIT-ERR-PRIOR-004` | prior-audit-reconciliation | 0 | environment/setup issue | no | Resolved analysis-script type error; corrected totals used. |
| `AUDIT-ERR-PRIOR-005` | prior-audit-reconciliation | 0 | informational warning | no | Initial delta discarded; high-limit retry is the retained evidence. |
| `AUDIT-ERR-PRIOR-006` | prior-audit-reconciliation | 1 | expected negative-path result | no | Expected no-match result; status was reconciled from authoritative checklist and commit history. |
| `AUDIT-ERR-PRIOR-007` | prior-audit-reconciliation | 1 | environment/setup issue | no | Resolved gh CLI option incompatibility; live main alert count recovered. |
| `AUDIT-ERR-PRIOR-008` | prior-audit-reconciliation | 0 | informational warning | no | Capsule was treated only as navigation; direct reads supplied the reconciliation evidence. |
| `AUDIT-ERR-PRIOR-009` | prior-audit-reconciliation | 0 | environment/setup issue | no | No impact on this bounded worker scope because the parent supplied an explicit task; the root audit must not use the attachment alone as completion authority. |
| `AUDIT-ERR-PRIOR-010` | prior-audit-reconciliation | 0 | informational warning | no | Combined output was not used where truncated; focused rereads are authoritative. |
| `AUDIT-ERR-PRIOR-011` | prior-audit-reconciliation | 0 | informational warning | no | No decisive evidence remained dependent on truncated output. |
| `AUDIT-ERR-PRIOR-012` | prior-audit-reconciliation | 0 | informational warning | no | Focused status evidence replaced the truncated broad result. |
| `AUDIT-ERR-PRIOR-013` | prior-audit-reconciliation | 0 | informational warning | no | Decisive CodeQL and history evidence was recovered independently; noisy full commit stats were not relied upon. |
| `AUDIT-ERR-PRIOR-014` | prior-audit-reconciliation | 0 | informational warning | no | Authoritative aggregate coverage evidence replaced the truncated raw pattern stream. |
| `AUDIT-ERR-PRIOR-015` | prior-audit-reconciliation | 0 | missing external fixture | yes | Zero alerts is not a clean result; current-branch CodeQL coverage remains unproven until an authorized scan runs. |
| `AUDIT-ERR-PRIOR-PROD-001` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | closed; no evidence was inferred from the failed wrapper |
| `AUDIT-ERR-PRIOR-PROD-002` | prior-production-audit-reconciliation | 0 | informational warning | no | mitigated; no classification relies on truncated output |
| `AUDIT-ERR-PRIOR-PROD-003` | prior-production-audit-reconciliation | 1 | confirmed repository defect | no | expected fallback; exact evidence obtained |
| `AUDIT-ERR-PRIOR-PROD-004` | prior-production-audit-reconciliation | 0 | informational warning | no | mitigated by bounded exact reads and reproduction |
| `AUDIT-ERR-PRIOR-PROD-005` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | closed after separated reads |
| `AUDIT-ERR-PRIOR-PROD-006` | prior-production-audit-reconciliation | 0 | informational warning | no | mitigated; bounded evidence retained |
| `AUDIT-ERR-PRIOR-PROD-007` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | closed after authoritative path lookup |
| `AUDIT-ERR-PRIOR-PROD-008` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | closed |
| `AUDIT-ERR-PRIOR-PROD-009` | prior-production-audit-reconciliation | 0 | informational warning | no | mitigated; truncated serialization discarded |
| `AUDIT-ERR-PRIOR-PROD-010` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | mitigated; broad output not used |
| `AUDIT-ERR-PRIOR-PROD-011` | prior-production-audit-reconciliation | 0 | informational warning | no | mitigated |
| `AUDIT-ERR-PRIOR-PROD-012` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | closed after corrected search |
| `AUDIT-ERR-PRIOR-PROD-013` | prior-production-audit-validation | 1 | test failure | yes | open product/test failure |
| `AUDIT-ERR-PRIOR-PROD-014` | prior-production-audit-validation | 1 | confirmed repository defect | no | separate current artifact drift for coordinator/owning worker; original finding root classified fixed |
| `AUDIT-ERR-PRIOR-PROD-015` | prior-production-audit-validation | 1 | confirmed repository defect | no | separate artifact drift retained; original false-green defect fixed |
| `AUDIT-ERR-PRIOR-PROD-016` | prior-production-audit-validation | 0 | expected negative-path result | no | closed expected warning |
| `AUDIT-ERR-PRIOR-PROD-017` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | closed after correct-path execution |
| `AUDIT-ERR-PRIOR-PROD-018` | prior-production-audit-reconciliation | 0 | informational warning | no | mitigated |
| `AUDIT-ERR-PRIOR-PROD-019` | prior-production-audit-reconciliation | n/a | informational warning | yes | terminal audit coverage remains pending independent review |
| `AUDIT-ERR-PRIOR-PROD-020` | prior-production-audit-validation | n/a | informational warning | no | release/field validation outstanding; current source classifications remain bounded to available evidence |
| `AUDIT-ERR-VALIDATION-001` | validation-spine | 1 | environment/setup issue | no | Resolved during inspection; retained as command-level evidence. |
| `AUDIT-ERR-VALIDATION-002` | validation-spine | 2 | environment/setup issue | no | Resolved by safe PowerShell quoting; no audit coverage remained blocked. |
| `AUDIT-ERR-VALIDATION-003` | validation-spine | 0 | informational warning | no | Superseded by the clean final environment inventory; warning preserved. |
| `AUDIT-ERR-VALIDATION-004` | validation-spine | 1 | environment/setup issue | no | Resolved during inspection; final inventory values were based only on the successful retry. |
| `AUDIT-ERR-VALIDATION-005` | validation-spine | 0 | environment/setup issue | no | Resolved by using a literal bounded read; warning did not affect the recorded packaging findings. |
| `AUDIT-ERR-VALIDATION-006` | validation-spine | 1 | environment/setup issue | no | Resolved; the final 67-script Unit inventory and 33-script aggregate count came from the successful query. |
| `AUDIT-ERR-VALIDATION-007` | validation-spine | 1 | environment/setup issue | no | Resolved; absence of those optional config files was not treated as a test failure. |
| `AUDIT-ERR-VALIDATION-008` | validation-spine | 1 | expected negative-path result | yes | Open limitation: the current repository spine cannot prove dynamic execution of every source line without adding or externally supplying coverage instrumentation. |
| `AUDIT-ERR-VALIDATION-009` | validation-spine | 0 | informational warning | no | Mitigated through bounded reads; no final claim relies on the truncated listing alone. |
| `AUDIT-ERR-VALIDATION-010` | validation-spine | 0 | informational warning | no | Expected navigation limitation; mitigated with targeted reads in accordance with AGENTS.md. |
| `AUDIT-ERR-VALIDATION-011` | validation-spine | 0 | informational warning | no | Benign diagnostic stream use, not a validation failure. |
| `AUDIT-ERR-VALIDATION-012` | validation-spine | 0 | informational warning | no | Preserved as an evidence-attribution limitation; unrelated and concurrent changes must not be absorbed into this worker's conclusions. |
| `AUDIT-ERR-VALIDATION-013` | validation-spine | 0 | informational warning | no | Do not cite the preflight result as pass evidence; it is planning evidence only. |
| `AUDIT-ERR-VALIDATION-014` | validation-spine | n/a | missing external fixture | yes | Local CodeQL coverage remains blocked; use the repository's remote CodeQL workflow and retain its artifact/result. |
| `AUDIT-ERR-VALIDATION-015` | validation-spine | n/a | missing external fixture | yes | Local Semgrep coverage remains blocked until the scanner is provisioned; CI's Semgrep step is also non-gating because it uses continue-on-error. |
| `AUDIT-ERR-VALIDATION-016` | validation-spine | n/a | environment/setup issue | no | Mitigated by the bundled Python module; commands must use the module form for reproducibility. |
| `AUDIT-ERR-VALIDATION-017` | validation-spine | 0 | informational warning | no | No objective requirement used by this worker was lost; exact downstream claims were verified from repository source. |
| `AUDIT-ERR-VALIDATION-018` | validation-spine | 0 | informational warning | no | Corrected before reporting; only the reconciled count of 26 is authoritative. |
| `AUDIT-ERR-VALIDATION-019` | validation-spine | 0 | confirmed repository defect | no | Open reproducibility risk; declare/provision pytest or stop relying on it in environments built from requirements/dev.txt alone. |
| `AUDIT-ERR-VALIDATION-020` | validation-spine | 0 | confirmed repository defect | yes | The audit may inventory every file and test surface, but it must not claim every executable line ran without adding language-appropriate coverage collection. |
| `AUDIT-ERR-VALIDATION-021` | validation-spine | n/a | informational warning | yes | No pass/fail claim should be inferred from this worker; dynamic evidence must come from the orchestrated validation run. |
| `AUDIT-ERR-VALIDATION-022` | validation-spine | n/a | informational warning | yes | Real-media behavior remains unvalidated by this subtask and must be reported separately, never silently inferred from generated-media tests. |
| `AUDIT-ERR-VALIDATION-023` | validation-spine | 0 | confirmed repository defect | yes | Deep Audit cannot be treated as automatic validation for normal code pushes until trigger policy is broadened or another required workflow supplies equivalent coverage. |
| `AUDIT-ERR-VALIDATION-024` | validation-spine | 0 | confirmed repository defect | yes | The workflow can be green with omitted modules or environment-driven skips; require the strict wrapper and complete generated inventory. |
| `AUDIT-ERR-VALIDATION-025` | validation-spine | 0 | confirmed repository defect | yes | Unittest success alone is incomplete; execute the pytest supplement or convert/integrate these tests into canonical discovery. |
| `AUDIT-ERR-VALIDATION-026` | validation-spine | 0 | confirmed repository defect | yes | Make dependency provisioning explicit before treating private-beta pytest execution as reproducible. |
| `AUDIT-ERR-VALIDATION-027` | validation-spine | 0 | confirmed repository defect | yes | Deep-audit suite success is insufficient without the four omitted generated/inventory checks or an updated suite definition. |
| `AUDIT-ERR-VALIDATION-028` | validation-spine | 0 | confirmed repository defect | yes | Do not include this generator in an unattended read-only audit unless mutations are isolated or a non-mutating --check mode is implemented. |
| `AUDIT-ERR-VALIDATION-029` | validation-spine | 0 | confirmed repository defect | no | Current local coverage is available; future evidence must record analyzer presence/version and reject the warning path for strict gates. |
| `AUDIT-ERR-VALIDATION-030` | validation-spine | 0 | confirmed repository defect | no | Current environment is capable, but default release evidence can downshift on another host; strict switches should be required for gating. |
| `AUDIT-ERR-VALIDATION-031` | validation-spine | 0 | confirmed repository defect | yes | Do not equate npm run check with Tauri/Rust test coverage. |
| `AUDIT-ERR-VALIDATION-032` | validation-spine | 0 | confirmed repository defect | yes | Release validation must use -RequireTests and retain per-suite output; a default-mode green result is not strict pass evidence. |
| `AUDIT-ERR-VALIDATION-033` | validation-spine | 0 | confirmed repository defect | yes | Treat SARIF as artifact generation only unless separate policy gates scan execution and findings. |
| `AUDIT-ERR-VALIDATION-034` | validation-spine | 0 | confirmed repository defect | yes | Run the remote closure scan with explicit result retention/upload settings and link the artifact in final evidence. |
| `AUDIT-ERR-VALIDATION-035` | validation-spine | 0 | confirmed repository defect | yes | Aggregate success is partial evidence only; retain a complete 67-script result ledger. |
| `AUDIT-ERR-VALIDATION-036` | validation-spine | 0 | confirmed repository defect | no | Record tool paths and reject green skip output in strict audit evidence. |
| `AUDIT-ERR-VALIDATION-037` | validation-spine | 0 | missing external fixture | yes | Report hardware paths as unvalidated unless the opt-in matrix runs and records actual device/driver evidence. |
| `AUDIT-ERR-VALIDATION-038` | validation-spine | 0 | confirmed repository defect | yes | A green SKIP is not adversarial-kill coverage; retain codec availability and exercised-case evidence. |
| `AUDIT-ERR-VALIDATION-039` | validation-spine | 0 | missing external fixture | no | Do not use -AllowMissingTools for audit closure; record any SKIP as missing coverage. |
| `AUDIT-ERR-VALIDATION-040` | validation-spine | 0 | confirmed repository defect | yes | Named wrapper enumeration alone is incomplete; drive execution from the generated module inventory. |
| `AUDIT-ERR-VALIDATION-041` | validation-spine | 0 | informational warning | yes | Use the prior ledger for provenance only; obtain current-commit/worktree evidence before closure. |
| `AUDIT-ERR-W01-001` | worker-01-semantic-review | 0 | informational warning | no | The truncated broad output was discarded for baseline data; exact parsed rows are the retained evidence. |
| `AUDIT-ERR-W01-002` | worker-01-semantic-review | 0 | confirmed repository defect | no | No assigned source coverage is blocked; the generated-docs owner should restore the missing summary before that test row is reviewed through the normal navigation workflow. |
| `AUDIT-ERR-W01-003` | worker-01-fragment-construction | 0 | informational warning | no | No fragment field or finding evidence depends on the truncated example output; targeted source ranges and local validators are authoritative. |
| `AUDIT-ERR-W01-004` | worker-01-semantic-review | n/a | informational warning | yes | Do not infer a test pass or runtime reachability result from this slice. Dynamic validation and independent second review remain required before terminal high-risk coverage. |
| `AUDIT-ERR-W01-SR-001` | worker-01-independent-second-review | 1 | test failure | no | Evidence-bearing nonzero result; it does not block the independent review. |
| `AUDIT-ERR-W01-SR-002` | worker-01-independent-second-review | 0 | expected negative-path result | no | Evidence-bearing expected exception; it partially corrects the original claim by proving request-level correlation while confirming the missing terminal/indeterminate state. |
| `AUDIT-ERR-W01-SR-003` | worker-01-independent-second-review-validation | 0 | expected negative-path result | no | Passing validation with an expected synthetic error log; retained for complete incident accounting. |
| `AUDIT-ERR-W01-SR-004` | worker-01-independent-second-review-test-gap-search | 1 | expected negative-path result | no | No-match retained as test-gap evidence; review coverage continues. |
| `AUDIT-ERR-W01-SR-005` | worker-01-independent-second-review-ledger-validation | 0 | informational warning | no | Corrected in this worker ledger; no audit coverage was lost. |
| `AUDIT-ERR-W01-SR-006` | worker-01-independent-second-review-ledger-normalization | 1 | environment/setup issue | no | Recovered immediately; no source or evidence files were changed by the failed read. |
| `AUDIT-ERR-W01-SR-007` | worker-01-independent-attestation-change-packet-identification | n/a | environment/setup issue | no | Closed after syntax-correct retry; no repository file was read incompletely or changed by the failed cell. |
| `AUDIT-ERR-W01-SR-008` | worker-01-independent-attestation-change-packet-validation | 1 | informational warning | no | W01 machine-attestation coverage remains complete; strict global worktree coverage is explicitly reported as not clean because unrelated owners have not packeted 77 paths. |
| `AUDIT-ERR-W02-001` | worker-02-settings-boundary-review | 1 | expected negative-path result | no | Retained as missing direct-test evidence; the no-match result was not treated as a product command failure. |
| `AUDIT-ERR-W02-002` | worker-02-settings-boundary-review | 2 | environment/setup issue | no | The failed wildcard output was discarded; exact-path reads are the retained evidence. |
| `AUDIT-ERR-W02-003` | worker-02-effective-dump-corroboration | 1 | environment/setup issue | no | Corrected path used for all retained evidence; coordinator was notified. |
| `AUDIT-ERR-W02-004` | worker-02-effective-dump-corroboration | 1 | expected negative-path result | no | Retained as the missing-regression evidence for the coordinator-owned finding. |
| `AUDIT-ERR-W02-005` | worker-02-settings-boundary-validation | 1 | test failure | yes | Clean direct-module evidence for three authority/recovery cases remains blocked until the production-inaccurate test double is corrected. |
| `AUDIT-ERR-W02-006` | worker-02-settings-boundary-validation | 1 | test failure | yes | The repeated error confirms a fixture/platform defect rather than a transient run; the specific test remains blocked. |
| `AUDIT-ERR-W02-007` | worker-02-findings-finalization | 0 | informational warning | no | Combined output discarded as a completeness source; bounded exact reads are authoritative. |
| `AUDIT-ERR-W02-008` | worker-02-prior-audit-reconciliation | 1 | environment/setup issue | no | Correct prior-audit locations supplied the retained reconciliation evidence. |
| `AUDIT-ERR-W02-009` | worker-02-artifact-discovery | 1 | environment/setup issue | no | All worker artifacts were created under the canonical workers directory. |
| `AUDIT-ERR-W02-010` | worker-02-fragment-schema-inspection | 1 | environment/setup issue | no | The failed read was replaced by a bounded fixed-range read; schema inspection is complete. |
| `AUDIT-ERR-W02-011` | worker-02-settings-replay-proof | 0 | informational warning | no | Only the normalized retry is retained as behavioral proof; the initial conflict is recorded to preserve the complete probe trail. |
| `AUDIT-ERR-W02-012` | worker-02-fragment-validation | 0 | informational warning | no | Corrected mechanically through apply_patch; initial invalid fragment state is not retained. |
| `AUDIT-ERR-W02-013` | worker-02-fragment-validation | 0 | informational warning | no | Mechanical schema normalization applied; no review evidence or finding semantics changed. |
| `AUDIT-ERR-W02-014` | worker-02-global-integration-check | 0 | informational warning | yes | Local slice is ready for coordinator integration; global merge remains coordinator-owned and blocked until unrelated fragments/baseline are reconciled. |
| `AUDIT-ERR-W02-015` | worker-02 exact path-local finding reconciliation | 1 | environment/setup issue | no | Closed after exact-path discovery; the failed lookup supplied no review evidence. |
| `AUDIT-ERR-W02-016` | worker-02 error-ledger recording | 1 | environment/setup issue | no | Closed after exact-context apply_patch retry. |
| `AUDIT-ERR-W02-IR-001` | worker-02-independent-settings-store-line-review | 0 | informational warning | no | Unbounded response discarded as completeness evidence; bounded retry required. |
| `AUDIT-ERR-W02-IR-002` | worker-02-independent-policy-line-review | 1 | environment/setup issue | no | Recorded for execution completeness; retry required. |
| `AUDIT-ERR-W02-IR-003` | worker-02-independent-support-test-discovery | 0 | informational warning | no | Recorded; exact evidence will come from bounded reads and executable tests. |
| `AUDIT-ERR-W02-IR-004` | worker-02-independent-settings-store-validation | 1 | test failure | no | Finding independently confirmed; retain exact failure output in report. |
| `AUDIT-ERR-W02-IR-005` | worker-02-independent-policy-config-validation | 1 | environment/setup issue | no | Recorded as invocation error; corrected full-bundle retry required. |
| `AUDIT-ERR-W02-IR-006` | worker-02-independent-legacy-extra-runtime-probe | 1 | environment/setup issue | no | Recorded as invocation error; literal-script retry required. |
| `AUDIT-ERR-W02-IR-007` | worker-02-independent-legacy-extra-runtime-probe | 0 | informational warning | no | Inconclusive attempt discarded; direct-host retry required. |
| `AUDIT-ERR-W02-IR-008` | worker-02-independent-legacy-extra-runtime-probe | 1 | environment/setup issue | no | Recorded as invocation error; sentinel-array retry required. |
| `AUDIT-ERR-W02-IR-009` | worker-02-independent-final-state-reconciliation | 0 | informational warning | no | Broad status discarded as completeness evidence; targeted reconciliation required. |
| `AUDIT-ERR-W02-IR-010` | worker-02-independent-attestation-schema-discovery | 0 | informational warning | no | Broad search discarded as complete schema evidence; bounded reads required. |
| `AUDIT-ERR-W02-IR-011` | worker-02-independent-structured-fragment-validation | 1 | test failure | no | Schema issue is local to the independent error fragment; corrected retry required. |
| `AUDIT-ERR-W03-001` | inventory | 0 | informational warning | no | closed after bounded retries |
| `AUDIT-ERR-W03-002` | inventory | 0 | informational warning | no | mitigated by current-hash review and closing revalidation |
| `AUDIT-ERR-W03-003` | inventory | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-004` | semantic review | 0 | informational warning | no | closed after bounded semantic reads |
| `AUDIT-ERR-W03-005` | finding deduplication | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-006` | finding deduplication | 1 | expected negative-path result | no | closed as expected no-match |
| `AUDIT-ERR-W03-007` | semantic review | 0 | informational warning | no | closed after bounded rereads |
| `AUDIT-ERR-W03-008` | schema orientation | 0 | environment/setup issue | no | closed by discovery-based retry |
| `AUDIT-ERR-W03-009` | semantic review | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-010` | review fragment construction | 124 | environment/setup issue | no | closed by bounded retry |
| `AUDIT-ERR-W03-011` | PowerShell semantic review | n/a | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-012` | PowerShell semantic review | 1 | expected negative-path result | no | closed after independent retries |
| `AUDIT-ERR-W03-013` | PowerShell parse validation | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-014` | PowerShell semantic review | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-015` | PowerShell semantic review | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-016` | finding reconciliation | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-017` | parallel semantic review | n/a | environment/setup issue | no | closed by local review |
| `AUDIT-ERR-W03-018` | authorized W01 mechanical correction validation | 1 | environment/setup issue | no | closed by targeted canonical validation |
| `AUDIT-ERR-W03-019` | fragment schema validation | 1 | environment/setup issue | no | closed after schema normalization |
| `AUDIT-ERR-W03-020` | schedule semantic review | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W03-021` | schedule finding reproduction | 0 | expected negative-path result | no | retained as finding evidence |
| `AUDIT-ERR-W03-022` | schedule semantic review | 0 | informational warning | no | closed after bounded rereads |
| `AUDIT-ERR-W03-023` | checkpoint orientation | 0 | environment/setup issue | no | closed by discovery-based retry |
| `AUDIT-ERR-W03-024` | final fragment validation | 0 | informational warning | no | awaiting correction by owning worker; W03 validated independently |
| `AUDIT-ERR-W03-025` | validation command orientation | 1 | expected negative-path result | no | closed after source-based command verification |
| `AUDIT-ERR-W03-026` | focused Python validation | 1 | test failure | no | confirmed repository defect; focused suite otherwise passed |
| `AUDIT-ERR-W03-027` | failed-test diagnosis | 1 | environment/setup issue | no | closed by corrected bounded retry |
| `AUDIT-ERR-W03-028` | failed-test reproduction | 1 | test failure | no | confirmed repository defect |
| `AUDIT-ERR-W03-029` | focused PowerShell validation | 124 | environment/setup issue | no | closed by isolated reruns |
| `AUDIT-ERR-W03-030` | final fragment validation | 0 | informational warning | no | closed after confirmed global clean retry |
| `AUDIT-ERR-W04-001` | pending-publish concurrency review | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-002` | pending-publish concurrency review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-003` | pending-publish destination-race reproduction | 0 | environment/setup issue | yes | open pending corrected reproduction |
| `AUDIT-ERR-W04-004` | W04 continuation evidence inventory | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-005` | W04 audit-ledger schema discovery | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-006` | W04 source-scope inventory | 0 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-007` | W04 error-fragment validation | 0 | informational warning | no | closed for W04; external finding-location correction reported |
| `AUDIT-ERR-W04-008` | W04 early source-row checkpoint publication | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-009` | completed-domain static semantic review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-010` | PowerShell pending-publish static semantic review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W05-001` | worker-05 universe discovery | 0 | informational warning | no | Closed after bounded structured recovery; no conclusion relies on the omitted display tail. |
| `AUDIT-ERR-W05-002` | worker-05 checkpoint materialization | 1 | environment/setup issue | no | Closed after syntax-correct apply_patch retry; repository evidence was not inferred from the failed wrapper. |
| `AUDIT-ERR-W05-003` | worker-05 PowerShell semantic review | 0 | informational warning | no | Closed after exact-assignment per-domain recovery. |
| `AUDIT-ERR-W05-004` | worker-05 validated checkpoint | 1 | environment/setup issue | no | Closed after the corrected checkpoint validator completed successfully. |
| `AUDIT-ERR-W05-005` | worker-05 Python ASS-helper semantic review | 0 | informational warning | no | Closed after bounded caller- and test-local recovery. |
| `AUDIT-ERR-W05-006` | worker-05 support-evidence discovery | 0 | informational warning | no | Closed after exact structured assignment recovery. |
| `AUDIT-ERR-W05-007` | worker-05 checkpoint validation discovery | 0 | informational warning | no | Closed after direct API discovery and validation replaced the truncated text search. |
| `AUDIT-ERR-W05-008` | worker-05 checkpoint validation discovery | 1 | environment/setup issue | no | Closed after corrected introspection; the noncanonical source_classification field was removed during fragment validation. |
| `AUDIT-ERR-W05-009` | worker-05 active media-policy documentation reconciliation | 1 | environment/setup issue | no | Closed after the corrected read-only metadata query completed. |
| `AUDIT-ERR-W05-010` | worker-05 schema and assignment discovery | 1 | environment/setup issue | no | Closed after canonical assignment-ledger discovery. |
| `AUDIT-ERR-W05-011` | worker-05 error-fragment schema discovery | 1 | environment/setup issue | no | Closed after corrected bounded search. |
| `AUDIT-ERR-W05-012` | worker-05 SRT merger negative-path reproduction | 1 | environment/setup issue | no | Closed after successful synthetic reproduction; no real media or repository product state was used. |
| `AUDIT-ERR-W05-013` | worker-05 finding evidence consolidation | 1 | environment/setup issue | no | Closed after exact-path discovery and successful bounded recovery. |
| `AUDIT-ERR-W05-014` | worker-05 VobSub temporary-file leak test-gap verification | 1 | expected negative-path result | no | Closed as preserved negative-path test-gap evidence after bounded synonym reconciliation. |
| `AUDIT-ERR-W05-015` | worker-05 PowerShell truncated-scan recovery | 1 | environment/setup issue | no | Closed after corrected bounded scan. |
| `AUDIT-ERR-W05-016` | worker-05 generated dependency-atlas provenance | 1 | environment/setup issue | no | Closed after corrected non-mutating reproduction. |
| `AUDIT-ERR-W05-017` | worker-05 finding-fragment normalization | 1 | environment/setup issue | no | Closed after successful fragment normalization. |
| `AUDIT-ERR-W05-018` | worker-05 finding-fragment normalization | 1 | environment/setup issue | no | Closed after simpler normalization and validation. |
| `AUDIT-ERR-W05-019` | worker-05 finding-fragment normalization | 1 | environment/setup issue | no | Closed after simpler normalization and validation. |
| `AUDIT-ERR-W05-020` | worker-05 review-row generation | 1 | environment/setup issue | no | Closed after wrapper-aware parsing. |
| `AUDIT-ERR-W05-021` | worker-05 review-row generation | 1 | informational warning | no | Closed after bounded minimal-field generation. |
| `AUDIT-ERR-W05-022` | worker-05 PowerShell checkpoint validation | 124 | environment/setup issue | no | Closed after separated exact and global validation. |
| `AUDIT-ERR-W05-023` | worker-05 PowerShell checkpoint validation | 0 | test failure | no | Closed after exact fragment validation passed. |
| `AUDIT-ERR-W05-024` | worker-05 final validation discovery | 1 | environment/setup issue | no | Closed after correcting the search root. |
| `AUDIT-ERR-W05-025` | worker-05 final exact validation | 0 | test failure | no | Closed after cross-worker classification correction and exact W05-local validation. |
| `AUDIT-ERR-W05-026` | worker-05 final global validation | 1 | test failure | no | Open external to W05 scope. |
| `AUDIT-ERR-W06-001` | worker-06 generated-summary provenance | 1 | environment/setup issue | no | Closed after correcting the inspection key. |
| `AUDIT-ERR-W06-002` | worker-06 review-row schema discovery | 1 | environment/setup issue | no | Closed after exact schema-source inspection. |
| `AUDIT-ERR-W06-003` | worker-06 schema provenance discovery | 0 | informational warning | no | Closed after bounded generator and registry checks. |
| `AUDIT-ERR-W06-004` | worker-06 PowerShell event-redaction review | 1 | expected negative-path result | no | Closed after explicit negative-result handling. |
| `AUDIT-ERR-W09-001` | Tauri navigation-surface discovery | 1 | environment/setup issue | no | closed after bounded retry |
| `AUDIT-ERR-W09-002` | Tauri navigation-surface discovery | 1 | expected negative-path result | no | closed; negative evidence retained |
| `AUDIT-ERR-W09-003` | Tauri initialization-script API verification | n/a | environment/setup issue | no | closed by authoritative local-source fallback |
| `AUDIT-ERR-W09-004` | mandatory boundary and validation navigation | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W09-005` | PowerShell harness semantic review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W09-006` | audit artifact schema discovery | 1 | environment/setup issue | no | closed after path correction |
| `AUDIT-ERR-W09-007` | audit artifact schema discovery | 1 | environment/setup issue | no | closed after valid-root retry |
| `AUDIT-ERR-W09-008` | current-status and prior-progress reconciliation | 0 | informational warning | no | closed after bounded source reads |
| `AUDIT-ERR-W09-009` | exact dependency implementation verification | 1 | environment/setup issue | no | closed after resolved-version discovery |
| `AUDIT-ERR-W09-010` | package/bootstrap assumption review | 1 | environment/setup issue | no | closed after path correction |
| `AUDIT-ERR-W09-011` | Python launcher dependency review | 1 | environment/setup issue | no | closed after fixed-string retry |
| `AUDIT-ERR-W09-012` | finding severity calibration | 1 | environment/setup issue | no | closed after canonical-directory discovery |
| `AUDIT-ERR-W09-013` | finding severity calibration | 1 | expected negative-path result | no | closed; negative result retained |
| `AUDIT-ERR-W09-014` | finding severity calibration | 1 | environment/setup issue | no | closed by alternate evidence |
| `AUDIT-ERR-W09-015` | Rust validation | 1 | confirmed repository defect | no | open confirmed finding; semantic review remains complete |
| `AUDIT-ERR-W09-016` | Rust validation | 0 | informational warning | no | closed informational stderr record |
| `AUDIT-ERR-W09-017` | Rust validation | 0 | informational warning | no | closed informational stderr record |
| `AUDIT-ERR-W09-018` | cross-language Tauri contract validation | 1 | confirmed repository defect | no | open confirmed finding; remaining scaffold coverage passed |
| `AUDIT-ERR-W09-019` | priority-export contract reconciliation | 2 | environment/setup issue | no | closed after bounded glob retry |
| `AUDIT-ERR-W09-020` | canonical Tauri validation | 0 | informational warning | no | closed informational stderr record; green scope is narrower than formatting |
| `AUDIT-ERR-W09-021` | Rust dependency advisory validation | 1 | environment/setup issue | no | closed with explicit validation limitation |
| `AUDIT-ERR-W09-022` | privacy severity calibration | 2 | environment/setup issue | no | closed after glob retry |
| `AUDIT-ERR-W09-023` | privacy severity calibration | 0 | informational warning | no | closed after bounded file-specific retry |
| `AUDIT-ERR-W09-024` | NSIS payload inventory | 1 | environment/setup issue | no | closed after absolute-path retry |
| `AUDIT-ERR-W09-025` | NSIS productization reconciliation | 2 | environment/setup issue | no | closed after canonical test-path discovery |
| `AUDIT-ERR-W09-026` | NSIS productization reconciliation | 1 | expected negative-path result | no | closed; negative result retained as evidence |
| `AUDIT-ERR-W09-027` | review-fragment schema reconciliation | 2 | environment/setup issue | no | closed after glob retry |
| `AUDIT-ERR-W10-001` | worker-10-semantic-review | 1 | environment/setup issue | no | closed after separated reads; no semantic evidence was inferred from the suppressed payload |
| `AUDIT-ERR-W10-002` | worker-10-semantic-review | 1 | expected negative-path result | no | expected navigation fallback; closed |
| `AUDIT-ERR-W10-003` | worker-10-semantic-review | 0 | informational warning | no | mitigated; no review record or finding relies on the broad truncated output |
| `AUDIT-ERR-W10-004` | worker-10-semantic-review | 1 | environment/setup issue | no | closed after successful --glob retry |
| `AUDIT-ERR-W10-005` | worker-10-semantic-review | 0 | informational warning | no | mitigated by structured targeted parsing |
| `AUDIT-ERR-W10-006` | worker-10-semantic-review | 1 | expected negative-path result | no | expected negative evidence supporting the dependency-contract finding |
| `AUDIT-ERR-W10-007` | worker-10-semantic-review | 0 | informational warning | no | mitigated; findings use bounded current-source evidence |
| `AUDIT-ERR-W10-008` | worker-10-finding-ledger | 1 | environment/setup issue | no | closed; malformed broad-search output was not used as sole evidence |
| `AUDIT-ERR-W10-009` | worker-10-finding-ledger | 0 | informational warning | no | mitigated; final fragments are validated directly against repository functions |
| `AUDIT-ERR-W10-010` | worker-10-semantic-review | 0 | informational warning | no | closed after exact scalar-format retry |
| `AUDIT-ERR-W10-011` | worker-10-review-fragment-finalization | n/a | environment/setup issue | no | mitigated; no review data was changed by the failed attempt |
| `AUDIT-ERR-W10-012` | worker-10-report-finalization | n/a | environment/setup issue | no | mitigated; the failed attempt made no filesystem changes |
| `AUDIT-ERR-W10-013` | worker-10-finding-location-finalization | 0 | informational warning | no | mitigated before handoff; all 15 records restored |
| `AUDIT-ERR-W10-014` | worker-10-finding-semantic-integrity | 0 | environment/setup issue | no | corrected before handoff and covered by final semantic-alignment checks |
| `AUDIT-ERR-W10-IND-001` | independent-review-discovery | 1 | informational warning | no | closed after corrected parser retry |
| `AUDIT-ERR-W10-IND-002` | independent-review-discovery | 0 | informational warning | no | closed after final stable first-pass self-recheck snapshot |
| `AUDIT-ERR-W10-IND-003` | independent-review-summary-discovery | 1 | informational warning | no | closed after corrected command |
| `AUDIT-ERR-W10-IND-004` | independent-review-W10-005 | 0 | informational warning | no | closed after schema-aware retry |
| `AUDIT-ERR-W10-IND-005` | independent-review-W10-005 | 1 | informational warning | no | closed after schema-aware retry |
| `AUDIT-ERR-W10-IND-006` | independent-review-W10-005 | 1 | informational warning | no | closed after corrected search |
| `AUDIT-ERR-W10-IND-007` | independent-review-W10-005 | 1 | expected negative-path result | no | closed as expected negative evidence |
| `AUDIT-ERR-W10-IND-008` | independent-review-W10-010 | 1 | expected negative-path result | no | closed as expected negative reproduction |
| `AUDIT-ERR-W10-IND-009` | independent-review-ledger-validation | 0 | informational warning | no | closed after authorized first-pass normalization and clean validator retry |
| `AUDIT-ERR-W10-IND-010` | independent-review-summary-reconciliation | 0 | informational warning | no | closed after full summary read and hash reconciliation |
| `AUDIT-ERR-W10-IND-011` | independent-review-git-binding | 0 | informational warning | no | confidence constraint recorded; exact-file review remains complete |
| `AUDIT-ERR-W10-IND-012` | independent-review-first-pass-reconciliation | 1 | environment/setup issue | no | closed after safe normalized retry |
| `AUDIT-ERR-W10-IND-013` | independent-review-owning-finding-reconciliation | 1 | environment/setup issue | no | closed after bounded two-row retry |
| `AUDIT-ERR-W10-IND-014` | independent-review-first-pass-schema-validation | 0 | informational warning | no | closed after schema-complete first-pass reconciliation |
| `AUDIT-ERR-W10-IND-015` | independent-review-first-pass-comparison | 0 | informational warning | no | closed after bounded full-file parse and targeted conclusion checks |
| `AUDIT-ERR-W10-SR-001` | worker-10-self-recheck-baseline | 0 | informational warning | no | Confidence constraint recorded; it does not block exact-current-byte review. |
| `AUDIT-ERR-W10-SR-002` | worker-10-self-recheck-summary-discovery | 1 | expected negative-path result | no | No-match recorded; generated-summary-first navigation continues with a broader handled search. |
| `AUDIT-ERR-W10-SR-003` | worker-10-self-recheck-test-inventory | 0 | informational warning | no | Methodology correction recorded; it does not invalidate the exact inventory result. |
| `AUDIT-ERR-W10-SR-004` | worker-10-self-recheck-browser-skip-probe | 0 | expected negative-path result | no | Expected skip evidence recorded; browser smoke execution itself was not required for this control-flow proof. |
| `AUDIT-ERR-W10-SR-005` | worker-10-self-recheck-pytest-discovery-probe | 0 | expected negative-path result | no | Expected discovery-gap evidence recorded; it does not block completion of this read-only review. |
| `AUDIT-ERR-W10-SR-006` | worker-10-self-recheck-release-support-read | 1 | informational warning | no | Recoverable navigation error recorded; release-support review continues from resolved paths. |
| `AUDIT-ERR-W10-SR-007` | worker-10-self-recheck-release-support-discovery | 1 | expected negative-path result | no | No-match recorded; exact discovery continues with separator-neutral globs. |
| `AUDIT-ERR-W10-SR-008` | worker-10-self-recheck-suite-membership-reconciliation | 0 | informational warning | no | Evidence count corrected; the finding's root cause and severity remain confirmed. |
| `AUDIT-ERR-W10-SR-009` | worker-10-self-recheck-severity-calibration | 1 | expected negative-path result | no | No-match recorded; severity reconciliation remains evidence-based and does not block review. |
| `AUDIT-ERR-W10-SR-010` | worker-10-self-recheck-release-identity-probe | n/a | sandbox/permission failure | no | Runtime convenience probe skipped; exact static proof is sufficient for the missing equality invariant. |
| `AUDIT-ERR-W10-SR-011` | worker-10-self-recheck-private-release-static-probe | 0 | informational warning | no | Probe output is not used as negative evidence until corrected. |
| `AUDIT-ERR-W10-SR-012` | worker-10-self-recheck-security-workflow-static-probe | 0 | informational warning | no | Mixed probe discarded; exact source evidence remains complete. |
| `AUDIT-ERR-W10-SR-013` | worker-10-self-recheck-fragment-schema-orientation | 1 | informational warning | no | Recoverable example-navigation error recorded; requested worker-10 fragment construction is unaffected. |
| `AUDIT-ERR-W10-SR-014` | worker-10-self-recheck-support-hash-freeze | 1 | environment/setup issue | no | Recoverable inspection syntax error recorded; support-hash freeze is retried. |
| `AUDIT-ERR-W10-SR-015` | worker-10-self-recheck-support-hash-freeze | 0 | informational warning | no | Partial inventory retained; missing support row is retried separately. |
| `AUDIT-ERR-W10-SR-016` | worker-10-self-recheck-attestation-rename | n/a | environment/setup issue | no | Safe pre-write assertion prevented a partial rename; retry required immediately. |
| `AUDIT-ERR-W11-001` | worker-11-tests-tooling finding materialization | 1 | expected negative-path result | no | Closed command-shape/search-result issue; no repository evidence or reviewed source changed. |
| `AUDIT-ERR-W11-002` | worker-11 final-hash first-pass refresh | 1 | environment/setup issue | no | Closed after exact-directory retry; no reviewed source or test file was modified. |
| `AUDIT-ERR-W11-003` | worker-11 final-hash first-pass refresh | 0 | informational warning | no | Closed as display-only truncation after bounded recovery. |
| `AUDIT-ERR-W11-004` | worker-11 final-hash semantic reread | 0 | informational warning | no | Closed as display-only truncation after bounded exact-source recovery. |
| `AUDIT-ERR-W11-005` | worker-11 final-hash validation | 0 | informational warning | no | Retained as non-blocking validation stderr; focused suite passed. |
| `AUDIT-ERR-W11-006` | worker-11 final-hash evidence join | 0 | environment/setup issue | no | Closed after coordinated shared-fragment repair; the failed join supplied no terminal evidence. |
| `AUDIT-ERR-W11-HIR-001` | worker-11-independent-summary-reconciliation | 0 | informational warning | no | Exact review proceeds; stale summaries cannot satisfy semantic or hash evidence. |
| `AUDIT-ERR-W11-HIR-002` | worker-11-independent-prior-evidence-reconciliation | 0 | informational warning | no | Broad response discarded as complete evidence; bounded current-source and finding reads required. |
| `AUDIT-ERR-W11-HIR-003` | worker-11-independent-hash-lock | 0 | informational warning | no | Older review evidence retained only as historical provenance; no stale attestation emitted. |
| `AUDIT-ERR-W11-HIR-004` | worker-11-independent-adversarial-proof | 0 | confirmed repository defect | no | Closed as superseded after exact independent rereview of final tool ad2805d45ef9cb64dcf7aa4f33d1c16234833efcba2f0c038a7a829eb31db5a9 and test d1cc3dd4de40558317e19a065e3fede4861530ae3f0d4d99de58cd2e1c41b6c2; binding checks and 33/33 tests passed. |
| `AUDIT-ERR-W11-HIR-005` | worker-11-independent-artifact-discovery | 1 | environment/setup issue | no | Closed after successful syntax-correct retry; no coverage evidence was inferred from the failed invocation. |
| `AUDIT-ERR-W11-HIR-006` | worker-11-independent-artifact-discovery | 1 | environment/setup issue | no | Closed after syntax-correct retry; failed output was discarded. |
| `AUDIT-ERR-W11-HIR-007` | worker-11-independent-Windows-path-adversarial-proof | 0 | confirmed repository defect | no | Closed at the superseded hash after implementation and test correction; the next exact-hash pass must confirm rejection. |
| `AUDIT-ERR-W11-HIR-008` | worker-11-independent-Git-special-mode-adversarial-proof | 0 | confirmed repository defect | no | Closed as superseded after exact independent rereview of final tool ad2805d45ef9cb64dcf7aa4f33d1c16234833efcba2f0c038a7a829eb31db5a9 and test d1cc3dd4de40558317e19a065e3fede4861530ae3f0d4d99de58cd2e1c41b6c2; special-mode checks and 33/33 tests passed. |
| `AUDIT-ERR-W11-HIR-009` | worker-11-independent-first-pass-reconciliation | 1 | environment/setup issue | no | Closed after selecting a simpler retry form; no audit conclusion used the failed output. |
| `AUDIT-ERR-W11-HIR-010` | worker-11-independent-final-finding-binding-validation | 1 | environment/setup issue | no | Closed after syntax-correct retry; no evidence was inferred from the failed invocation and no file was changed. |
| `AUDIT-ERR-W11-HIR-011` | worker-11-independent-final-finding-binding-validation | 0 | environment/setup issue | no | Closed after clean structured retry; failed output was discarded and no repository product behavior was implicated. |
| `AUDIT-ERR-W11-HIR-012` | worker-11-independent-final-exact-lock-validation | 0 | informational warning | no | Recorded for exhaustive error and warning provenance; nonblocking and not evidence of a product defect. |
| `AUDIT-ERR-W11-HIR-013` | worker-11-independent-final-artifact-publication | 1 | environment/setup issue | no | Closed after syntax-correct retry; no product file or frozen audit target was changed by the failed command. |
| `AUDIT-ERR-W11-HIR-014` | worker-11-independent-final-artifact-publication | 0 | environment/setup issue | no | Closed after restoration and clean retry; the transient result was not used for any audit conclusion. |
| `AUDIT-ERR-W11-SR-001` | worker-11-independent-second-review-atomicity-probe | 0 | expected negative-path result | no | Evidence-bearing expected failure; it does not block completion of the read-only second review. |
| `AUDIT-ERR-W11-SR-002` | worker-11-independent-second-review-atomicity-proof-gate-probe | 0 | expected negative-path result | no | Evidence-bearing expected failure; it does not block completion of the read-only second review. |
| `AUDIT-ERR-W13-001` | tooling setup | n/a | environment/setup issue | no | closed after alternate dependency discovery |
| `AUDIT-ERR-W13-002` | tooling setup | n/a | environment/setup issue | no | closed after direct runtime discovery |
| `AUDIT-ERR-W13-003` | binary metadata inspection | 1 | environment/setup issue | no | closed after using the available primary runtime |
| `AUDIT-ERR-W13-004` | document structural inspection | 1 | environment/setup issue | no | closed after using the available primary runtime |
| `AUDIT-ERR-W13-005` | packaging policy inspection | 1 | environment/setup issue | no | closed after explicit-path retry |
| `AUDIT-ERR-W13-006` | binary metadata inspection | 0 | informational warning | no | closed after warning-free retry |
| `AUDIT-ERR-W13-007` | document semantic inspection | 0 | informational warning | no | closed with bounded structural and visual evidence |
| `AUDIT-ERR-W13-008` | visual image inspection | n/a | environment/setup issue | no | closed after format conversion for inspection |
| `AUDIT-ERR-W13-009` | document visual rendering | 1 | environment/setup issue | no | closed after current-tool-path retry |
| `AUDIT-ERR-W13-010` | consumer and provenance mapping | 0 | informational warning | no | closed with bounded searches |
| `AUDIT-ERR-W13-011` | packaging and reference mapping | 1 | environment/setup issue | no | closed after exact-source retry |
| `AUDIT-ERR-W13-012` | inventory aggregation | 0 | informational warning | no | closed after normalized, asserted recomputation |
| `AUDIT-ERR-W14-001` | worker-14-route-command-map | 1 | informational warning | no | closed by corrected read-only retry |
| `AUDIT-ERR-W14-002` | worker-14-route-command-map | 1 | informational warning | no | closed by corrected read-only retry |
| `AUDIT-ERR-W14-003` | worker-14-route-command-map | 1 | informational warning | no | closed by exact-context retry |
| `AUDIT-ERR-W14-004` | worker-14-route-command-map | 0 | informational warning | no | closed by bounded summary-first remediation |
| `AUDIT-ERR-W14-005` | worker-14-route-command-map | 1 | informational warning | no | closed by explicit-path retry |
| `AUDIT-ERR-W14-006` | worker-14-route-command-map | 1 | informational warning | no | closed by corrected read-only parser |
| `AUDIT-ERR-W14-007` | worker-14-route-command-map | 1 | informational warning | no | closed by corrected generator quoting |
| `AUDIT-ERR-W14-008` | worker-14-route-command-map | 1 | informational warning | yes | handled with isolated provisional delta; terminal coverage remains blocked for the two concurrently changed routes |
| `AUDIT-ERR-W14-009` | worker-14-route-command-map | 1 | informational warning | no | closed by smaller-chunk retry; no partial artifact existed |
| `AUDIT-ERR-W14-010` | worker-14-artifact-validation | 1 | informational warning | no | closed after corrected validation |
| `AUDIT-ERR-W14-011` | worker-14-finding-reproduction | 1 | informational warning | no | closed after corrected validation |
| `AUDIT-ERR-W14-012` | worker-14-prior-audit-reconciliation | 1 | expected negative-path result | no | closed; findings treated as newly observed in this audit |
| `AUDIT-ERR-W14-013` | worker-14-focused-validation | 1 | test failure | yes | open in concurrent feature work; preserved as validation evidence |
| `AUDIT-ERR-W14-014` | worker-14-artifact-validation | 2 | informational warning | no | closed after correction and successful retry |
| `AUDIT-ERR-W15-001` | worker-15-discovery | 0 | informational warning | no | No broad output was used as sole evidence. |
| `AUDIT-ERR-W15-002` | worker-15-registry-inventory | 1 | environment/setup issue | no | Failed output discarded. |
| `AUDIT-ERR-W15-003` | worker-15-registry-inventory | 0 | informational warning | no | Truncated payload was not retained as complete evidence. |
| `AUDIT-ERR-W15-004` | worker-15-registry-source-read | 0 | informational warning | no | Only complete bounded reads and live registry output were used. |
| `AUDIT-ERR-W15-005` | worker-15-process-result-contract | 1 | environment/setup issue | no | Missing navigation aid recorded; exact schema source was obtained. |
| `AUDIT-ERR-W15-006` | worker-15-process-result-contract | 1 | expected negative-path result | no | No-match retained as navigation-gap evidence only. |
| `AUDIT-ERR-W15-007` | worker-15-failure-state-read | 0 | informational warning | no | Truncated sections were not treated as reviewed until re-read. |
| `AUDIT-ERR-W15-008` | worker-15-finding-deduplication | 2 | environment/setup issue | no | Corrected glob search is retained evidence. |
| `AUDIT-ERR-W15-009` | worker-15-workflow-tracing | 0 | informational warning | no | Broad batch used only for path/symbol leads. |
| `AUDIT-ERR-W15-010` | worker-15-workflow-tracing | 0 | informational warning | no | No omitted symbol was relied upon without a later exact read. |
| `AUDIT-ERR-W15-011` | worker-15-cross-layer-evidence | 0 | informational warning | no | Only bounded follow-up output informed final records. |
| `AUDIT-ERR-W15-012` | worker-15-pending-publish-trace | 0 | informational warning | no | Truncated drain output was not represented as a full-file review. |
| `AUDIT-ERR-W15-013` | worker-15-registry-validation | 1 | test failure | yes | Open repository defect; registry completeness cannot be reported green. |
| `AUDIT-ERR-W15-014` | worker-15-validation-orchestration | 1 | environment/setup issue | no | Registry failure retained separately; sibling evidence recovered. |
| `AUDIT-ERR-W15-015` | worker-15-targeted-python-validation | 1 | test failure | yes | Open deterministic cross-language recovery defect; all other selected tests passed. |
| `AUDIT-ERR-W15-016` | worker-15-repair-drain-reproduction | 1 | test failure | yes | Root cause confirmed; no product changes made by this worker. |
| `AUDIT-ERR-W15-017` | worker-15-ledger-schema-sampling | 1 | environment/setup issue | no | Correct schema evidence obtained; missing guessed path discarded. |
| `AUDIT-ERR-W15-018` | worker-15-finalization | 0 | informational warning | no | Broad finalization output is not used to claim clean global status. |
| `AUDIT-ERR-W16-001` | worker-16-orientation | 0 | informational warning | no | Closed as display-only truncation; no claim relies on omitted combined output. |
| `AUDIT-ERR-W16-002` | worker-16-network-duplication-reconciliation | 0 | informational warning | no | Closed as display-only truncation; no duplication conclusion relies on omitted output. |
| `AUDIT-ERR-W16-003` | worker-16-webview-export-analysis | 124 | environment/setup issue | no | Closed after algorithmic retry; this is audit-tool orchestration overhead, not a repository defect. |
| `AUDIT-ERR-W16-004` | worker-16-python-static-analysis | 0 | missing external fixture | no | Optional scanner unavailable; coverage continues with repository-bundled and standard-library analysis. |
| `AUDIT-ERR-W16-005` | worker-16-python-duplication-analysis | 0 | informational warning | no | Closed as display-only truncation; full aggregate counts and selected high-impact groups remain reproducible. |
| `AUDIT-ERR-W16-006` | worker-16-network-duplication-reconciliation | 1 | expected negative-path result | no | Closed as expected search semantics; not a repository execution failure. |
| `AUDIT-ERR-W16-007` | worker-16-compatibility-surface-inventory | 0 | informational warning | no | Closed after bounded retry; no conclusion relies on bundled-runtime matches or omitted output. |
| `AUDIT-ERR-W16-008` | worker-16-compatibility-surface-inventory | 1 | environment/setup issue | no | Closed after corrected in-memory retry; repository files were not modified. |
| `AUDIT-ERR-W16-009` | worker-16-compatibility-surface-inventory | 0 | informational warning | no | Closed after corrected in-memory retry; no repository claim uses the faulty counts. |
| `AUDIT-ERR-W16-010` | worker-16-prior-finding-deduplication | 1 | environment/setup issue | no | Closed after corrected bounded retry. |
| `AUDIT-ERR-W16-011` | worker-16-prior-finding-deduplication | 1 | expected negative-path result | no | Closed as expected search semantics. |
| `AUDIT-ERR-W16-012` | worker-16-barrel-reexport-inventory | 0 | informational warning | no | Closed after corrected in-memory retry. |
| `AUDIT-ERR-W16-013` | worker-16-unreachable-branch-analysis | 0 | environment/setup issue | no | Closed after direct-host retry; repository files were not modified. |
| `AUDIT-ERR-W16-014` | worker-16-universe-binding | 0 | informational warning | no | Closed after corrected universe definition. |
| `AUDIT-ERR-W16-015` | worker-16-universe-binding | 0 | informational warning | no | Closed after path-specific exclusion correction. |
| `AUDIT-ERR-W16-016` | worker-16-rust-static-analysis | 0 | informational warning | no | Retained as validation warning; no source edit authorized. |
| `AUDIT-ERR-W16-017` | worker-16-duplicate-policy-ownership | 0 | informational warning | no | Closed as display-only truncation. |
| `AUDIT-ERR-W16-018` | worker-16-python-duplication-analysis | 0 | informational warning | no | Closed as display-only truncation. |
| `AUDIT-ERR-W16-019` | worker-16-webview-unused-symbol-analysis | 124 | environment/setup issue | no | Closed after algorithmic retry; repository files were not modified. |
| `AUDIT-ERR-W16-020` | worker-16-powershell-unused-symbol-analysis | 0 | informational warning | no | Closed after guarded retry. |
| `AUDIT-ERR-W16-021` | worker-16-powershell-duplication-analysis | 0 | informational warning | no | Closed after production-only retry. |
| `AUDIT-ERR-W16-022` | worker-16-api-contract-duplication-analysis | 0 | informational warning | no | Closed after corrected structural retry. |
| `AUDIT-ERR-W16-023` | worker-16-duplicate-encoder-policy-reproduction | 1 | expected negative-path result | no | Closed after corrected no-write probe; the failed result is not used as repository evidence. |
| `AUDIT-ERR-W16-024` | worker-16-artifact-formatting | 1 | environment/setup issue | no | Closed after exact-path retry. |
| `AUDIT-ERR-W16-025` | worker-16-webview-unused-symbol-analysis | 1 | environment/setup issue | no | Closed after corrected read-only retry. |
| `AUDIT-ERR-W16-026` | worker-16-prior-finding-deduplication | 1 | environment/setup issue | no | Closed after corrected read-only retry. |
| `AUDIT-ERR-W16-027` | worker-16-byte-duplicate-verification | 0 | environment/setup issue | no | Closed after exact-path guarded retry. |
| `AUDIT-ERR-W16-028` | worker-16-finding-schema-validation | 1 | environment/setup issue | no | Closed after exact-line patch retry. |

Full commands, decisive output, retry results, and source-fragment provenance are in `ERROR_LEDGER.jsonl`.
