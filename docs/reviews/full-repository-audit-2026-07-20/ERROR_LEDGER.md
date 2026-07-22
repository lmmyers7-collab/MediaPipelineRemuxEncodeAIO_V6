# Audit Error Ledger

Every nonzero audit command, parser/analysis error, confidence-affecting warning, missing dependency, output truncation, skip/downshift, and external-evidence gap is recorded here. Expected negative-path results remain evidence; they are not product defects unless linked to a confirmed finding.

- Recorded events: **1043**
- Events currently blocking some coverage: **0**

## Classification counts

| Classification | Events |
|---|---:|
| confirmed repository defect | 57 |
| environment/setup issue | 425 |
| expected negative-path result | 111 |
| flaky/non-deterministic | 2 |
| informational warning | 356 |
| missing external fixture | 7 |
| sandbox/permission failure | 9 |
| test failure | 76 |

## Event index

| ID | Phase | Exit | Classification | Coverage blocked | Disposition |
|---|---|---:|---|---|---|
| `AUDIT-ERR-CMISC-001` | scope reconciliation | 0 | expected negative-path result | no | Closed after deterministic canonical-ID reconciliation. |
| `AUDIT-ERR-CMISC-002` | review setup | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed orchestration. |
| `AUDIT-ERR-CMISC-003` | generated-summary-before-source navigation | 1 | expected negative-path result | no | Closed; absence is evidence, not a review blocker. |
| `AUDIT-ERR-CMISC-004` | finding reconciliation | 0 | expected negative-path result | no | Closed; zero path-local matches is a valid reconciliation result. |
| `AUDIT-ERR-CMISC-005` | test and behavior relationship review | 0 | informational warning | no | Closed after bounded recovery. |
| `AUDIT-ERR-CMISC-006` | validation selection | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on omitted output. |
| `AUDIT-ERR-CMISC-007` | rerun projection relationship review | 1 | environment/setup issue | no | Closed after corrected bounded invocation. |
| `AUDIT-ERR-CMISC-008` | rerun projection relationship review | 1 | environment/setup issue | no | Closed after syntax correction. |
| `AUDIT-ERR-CMISC-009` | generated-index finding reconciliation | 1 | environment/setup issue | no | Closed after corrected invocation. |
| `AUDIT-ERR-CMISC-010` | generated-index finding reconciliation | 0 | informational warning | no | Closed after structured bounded recovery. |
| `AUDIT-ERR-CMISC-011` | syntax and provenance validation | 1 | environment/setup issue | no | Closed after corrected full rerun. |
| `AUDIT-ERR-CMISC-012` | focused behavior validation | 124 | environment/setup issue | no | Closed after complete isolated reruns; the timeout is not a product-test failure. |
| `AUDIT-ERR-CMISC-013` | audit evidence validation | 1 | environment/setup issue | no | Closed after global and slice-local validation recovery; no conclusion relies on the failed intermediate join. |
| `AUDIT-ERR-CMISC-OP-001` | current-misc-operational-independent-schema-discovery | 0 | informational warning | no | Closed by bounded source reads; no conclusion relies on truncated output. |
| `AUDIT-ERR-CMISC-OP-002` | current-misc-operational-independent-test-navigation | 1 | environment/setup issue | no | Closed after syntax-correct retry; no file was changed or incompletely reviewed because of the failed command. |
| `AUDIT-ERR-CMISC-OP-003` | current-misc-operational-independent-baseline-discovery | 1 | environment/setup issue | no | Closed by literal-path reads and exact Git-tree validation; the partial search output was not treated as complete evidence. |
| `AUDIT-ERR-CMISC-OP-004` | current-misc-operational-independent-artifact-preflight | 1 | environment/setup issue | no | Closed after syntax-correct retry; no repository file changed during the failed command. |
| `AUDIT-ERR-CMISC-OP-005` | current-misc-operational-independent-defect-reproduction | 0 | expected negative-path result | no | Evidence-bearing expected defect result; W01-017 remains confirmed. |
| `AUDIT-ERR-CMISC-OP-006` | current-misc-operational-independent-defect-reproduction | 0 | expected negative-path result | no | Evidence-bearing expected defect result; W01-018 remains confirmed. |
| `AUDIT-ERR-CMISC-OP-007` | current-misc-operational-independent-defect-reproduction | 0 | expected negative-path result | no | Evidence-bearing expected defect result; W01-019 remains confirmed. |
| `AUDIT-ERR-CMISC-OP-008` | current-misc-operational-independent-defect-reproduction | 0 | expected negative-path result | no | Evidence-bearing expected defect result; W01-021 remains confirmed. |
| `AUDIT-ERR-CMISC-OP-009` | current-misc-operational-independent-defect-reproduction | 0 | expected negative-path result | no | Evidence-bearing expected defect result; W01-023 remains confirmed. |
| `AUDIT-ERR-CMISC-OP-010` | current-misc-operational-independent-defect-reproduction | 0 | expected negative-path result | no | Evidence-bearing expected operational routing result; W01-024 remains confirmed without expanding into authentication or secret handling. |
| `AUDIT-ERR-CMISC-OP-011` | current-misc-operational-independent-defect-reproduction | 0 | expected negative-path result | no | Evidence-bearing expected defect result; W01-025 remains confirmed. |
| `AUDIT-ERR-CMISC-OP-012` | current-misc-operational-independent-artifact-validation | 1 | environment/setup issue | no | Closed setup error; no repository or product behavior was implicated. |
| `AUDIT-ERR-CMISC-OP-013` | current-misc-operational-independent-artifact-validation | 1 | environment/setup issue | no | Closed invocation error; the successful retry validated all current fragments without writing central artifacts. |
| `AUDIT-ERR-CMISC-OP-014` | current-misc-operational-independent-artifact-validation | 1 | environment/setup issue | no | Closed audit-query scope error; unrelated concurrent attestation reconciliation was left to its owning workers. |
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
| `AUDIT-ERR-COORD-028` | dependency-and-cycle-map | 0 | informational warning | no | open aggregate-count freeze requirement; structural finding remains confirmed Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
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
| `AUDIT-ERR-COORD-076` | worker-05-p1-independent-review | 0 | test failure | no | closed after clean frozen global join and central check |
| `AUDIT-ERR-COORD-077` | worker-05-p1-independent-review | 0 | test failure | no | closed after W09 stabilization and clean central checkpoint |
| `AUDIT-ERR-COORD-078` | worker-15-p1-independent-review | 1 | environment/setup issue | no | closed after exact artifact and prerequisite discovery |
| `AUDIT-ERR-COORD-079` | worker-09-map-reconciliation | n/a | environment/setup issue | no | closed after smaller exact-anchor map reconciliation |
| `AUDIT-ERR-COORD-080` | worker-05-high-risk-independent-review | 0 | environment/setup issue | no | closed after bounded missing-range read |
| `AUDIT-ERR-COORD-081` | worker-05-high-risk-independent-review | 1 | environment/setup issue | no | closed after discovered PATH PowerShell retry |
| `AUDIT-ERR-COORD-082` | worker-05-high-risk-independent-review | 0 | environment/setup issue | no | closed after bounded missing-range retry |
| `AUDIT-ERR-COORD-083` | worker-05-high-risk-independent-review | 0 | informational warning | no | closed after exact single-fragment extraction |
| `AUDIT-ERR-COORD-084` | worker-05-high-risk-independent-review | n/a | environment/setup issue | no | closed after policy-compatible in-memory harness retry |
| `AUDIT-ERR-COORD-085` | worker-05-high-risk-independent-review | 1 | expected negative-path result | no | closed after exit-neutral test-gap census and direct negative-path reproduction |
| `AUDIT-ERR-COORD-086` | worker-05-high-risk-independent-review | 1 | environment/setup issue | no | closed after newline-independent harness startup correction |
| `AUDIT-ERR-COORD-087` | worker-05-high-risk-independent-review | 1 | environment/setup issue | no | closed after complete in-memory harness startup correction |
| `AUDIT-ERR-COORD-088` | worker-05-high-risk-independent-review | 1 | test failure | no | closed as a current, reproduced, already tracked registry defect |
| `AUDIT-ERR-COORD-089` | worker-06-checkpoint-recovery | 0 | informational warning | no | closed after bounded artifact inspection |
| `AUDIT-ERR-COORD-090` | worker-06-checkpoint-recovery | 0 | environment/setup issue | no | closed after correctly scoped official-helper validation |
| `AUDIT-ERR-COORD-091` | worker-06-checkpoint-recovery | 0 | environment/setup issue | no | closed after scoped W06 error validation and W03 owner reconciliation |
| `AUDIT-ERR-COORD-092` | worker-05-high-risk-independent-review | 1 | environment/setup issue | no | closed after bounded live-tail inspection and exact-context retry |
| `AUDIT-ERR-COORD-093` | worker-05-high-risk-independent-review | 1 | environment/setup issue | no | closed after bounded live-tail reconciliation and coordinator-ID ownership handoff |
| `AUDIT-ERR-COORD-094` | worker-09-high-risk-independent-review | 1 | environment/setup issue | no | closed after syntax-correct bounded census retry |
| `AUDIT-ERR-COORD-095` | change-packet-reconciliation | 1 | expected negative-path result | no | closed after canonical packet-touch reconciliation |
| `AUDIT-ERR-COORD-096` | worker-05-high-risk-independent-review | 0 | test failure | no | closed after canonical disposition reconciliation and clean exact rerun |
| `AUDIT-ERR-COORD-097` | change-packet-reconciliation | 1 | environment/setup issue | no | closed after syntax-correct census and canonical packet-touch reconciliation |
| `AUDIT-ERR-COORD-098` | worker-15-P1-independent-review-orientation | 1 | environment/setup issue | no | closed after Windows-safe glob retry and first-pass availability reconciliation |
| `AUDIT-ERR-COORD-099` | worker-04-worker-15-independent-review-publication | 1 | environment/setup issue | no | closed after switching to context-anchored patch hunks; no product or audit file was changed by the failed attempt |
| `AUDIT-ERR-COORD-100` | worker-15-new-finding-path-reconciliation | 1 | environment/setup issue | no | closed as an expected no-match after interpreting rg exit code 1 explicitly |
| `AUDIT-ERR-COORD-101` | worker-04-generated-independent-review | 0 | environment/setup issue | no | closed after identifying the parser defect; no audit attestation or repository source was written from the false report |
| `AUDIT-ERR-COORD-102` | worker-04-generated-independent-review-publication | 0 | environment/setup issue | no | closed after switching to bounded chunk publication; no partial attestation file was created by the aborted call |
| `AUDIT-ERR-COORD-103` | worker-04-independent-source-orientation | 1 | environment/setup issue | no | closed after switching to structured JSONL path lookup |
| `AUDIT-ERR-COORD-104` | worker-04-pending-destination-lock-independent-review | n/a | sandbox/permission failure | no | closed after restructuring the disposable probe into verifiable bounded steps |
| `AUDIT-ERR-COORD-105` | worker-04-pending-destination-lock-independent-review-cleanup | n/a | sandbox/permission failure | no | closed after safe exact-path .NET cleanup; no product or repository path was targeted |
| `AUDIT-ERR-COORD-106` | worker-06-settings-route-summary-independent-review | 1 | expected negative-path result | no | closed as an expected negative search with no mutation |
| `AUDIT-ERR-COORD-107` | worker-06-settings-route-summary-independent-review | 1 | environment/setup issue | no | closed after logging; retry uses non-throwing structured reads and isolated bounded source reads |
| `AUDIT-ERR-COORD-108` | worker-06-process-route-independent-review | 1 | environment/setup issue | no | closed after logging; retry uses rg's portable --glob filter |
| `AUDIT-ERR-COORD-109` | worker-06-disk-storage-independent-review | 0 | environment/setup issue | no | closed after logging; exact omitted range is recovered in a bounded follow-up read |
| `AUDIT-ERR-COORD-110` | worker-06-disk-storage-independent-review | 1 | environment/setup issue | no | closed after logging; retry uses rg's portable --glob filter |
| `AUDIT-ERR-COORD-111` | worker-06-disk-storage-independent-review | 1 | test failure | no | closed after owner correction and clean scoped-validator retry |
| `AUDIT-ERR-COORD-112` | worker-06-disk-storage-independent-review | 1 | test failure | no | closed after owner correction and clean scoped-validator retry |
| `AUDIT-ERR-COORD-113` | audit-map-reconciliation-planning | 1 | environment/setup issue | no | closed after logging; retry uses an explicit result array |
| `AUDIT-ERR-COORD-114` | worker-10-release-packet-metadata-completion | 1 | environment/setup issue | no | closed after logging; retry is baseline-blob aware |
| `AUDIT-ERR-COORD-115` | worker-10-release-packet-metadata-completion | 1 | informational warning | no | closed for the frozen 1,094-packet slice; live audit packet remains deferred to final freeze |
| `AUDIT-ERR-COORD-116` | worker-10-release-packet-metadata-completion | 0 | informational warning | no | closed after logging; remaining rows use concise non-overlapping fragments |
| `AUDIT-ERR-COORD-117` | worker-10-release-packet-metadata-completion | 0 | informational warning | no | closed after logging; retry uses eight-row transport-safe fragments |
| `AUDIT-ERR-COORD-118` | worker-10-release-packet-metadata-completion | n/a | informational warning | no | closed after exact partial-publication inventory; resume begins at first missing fragment |
| `AUDIT-ERR-COORD-119` | worker-10-release-packet-metadata-completion | 1 | test failure | no | closed after exact fragment replacement and clean scoped-validator retry |
| `AUDIT-ERR-COORD-120` | worker-10-release-script-line-review | 1 | environment/setup issue | no | closed after logging; transport-safe retry selected |
| `AUDIT-ERR-COORD-121` | worker-10-release-script-line-review | 1 | informational warning | no | closed after logging; direct bounded read selected |
| `AUDIT-ERR-COORD-122` | worker-10-release-script-line-review | 1 | environment/setup issue | no | closed after logging; corrected repository-root list selected |
| `AUDIT-ERR-COORD-123` | worker-10-release-script-line-review | n/a | sandbox/permission failure | no | closed after logging; explicit-path bounded retry selected |
| `AUDIT-ERR-COORD-124` | worker-10-release-script-line-review | 1 | test failure | no | closed after logging; production-shaped fixture retry selected |
| `AUDIT-ERR-COORD-125` | worker-10-release-script-line-review | n/a | sandbox/permission failure | no | closed after validated bounded cleanup retry |
| `AUDIT-ERR-COORD-126` | worker-10-release-script-validation | 1 | test failure | no | closed after confirmed-finding reconciliation |
| `AUDIT-ERR-COORD-127` | worker-10-release-script-validation | 1 | environment/setup issue | no | closed after logging; bounded provenance lookup selected |
| `AUDIT-ERR-COORD-128` | cross-worker-baseline-freshness | 0 | informational warning | no | open pending current-HEAD baseline regeneration Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-COORD-129` | cross-worker-baseline-freshness | 0 | informational warning | no | closed after logging; bounded delta summary retry selected |
| `AUDIT-ERR-COORD-130` | worker-10-release-script-validation | 1 | expected negative-path result | no | closed; zero-match result used as deduplication evidence |
| `AUDIT-ERR-COORD-131` | worker-10-release-script-validation | 0 | environment/setup issue | no | closed after corrected bounded retry |
| `AUDIT-ERR-COORD-132` | cross-worker-ledger-validation | 0 | informational warning | no | closed after W12 normalization and validation retry |
| `AUDIT-ERR-COORD-133` | worker-10-release-script-ledger-publication | 1 | expected negative-path result | no | closed; zero-match result established publication gap |
| `AUDIT-ERR-COORD-134` | system-map-completion-assessment | 1 | environment/setup issue | no | closed after corrected bounded retry |
| `AUDIT-ERR-COORD-135` | cross-worker-baseline-freshness | 0 | informational warning | no | closed after successful external non-self-referential preflight; the in-repository mirror remains intentionally non-authoritative for the final tracked-output snapshot |
| `AUDIT-ERR-COORD-136` | cross-worker-baseline-freshness | 1 | expected negative-path result | no | closed; missing direct test recorded as completion work |
| `AUDIT-ERR-COORD-137` | cross-worker-ledger-validation | 0 | informational warning | no | closed after W04 normalization and successful global retry |
| `AUDIT-ERR-COORD-138` | current-head-delta-evidence-review | 0 | informational warning | no | closed after evidence-interpretation correction |
| `AUDIT-ERR-COORD-139` | current-head-delta-assignment | 1 | environment/setup issue | no | closed after schema-corrected retry |
| `AUDIT-ERR-COORD-140` | current-head-delta-assignment | 1 | expected negative-path result | no | closed; zero-match result used to preserve rereview scope |
| `AUDIT-ERR-COORD-141` | current-head-packet-metadata-review | 1 | expected negative-path result | no | closed; missing prior evidence established fresh-review scope |
| `AUDIT-ERR-COORD-142` | current-head-packet-metadata-review | 1 | expected negative-path result | no | closed with explicit project-index reconciliation |
| `AUDIT-ERR-COORD-143` | current-head-packet-metadata-review | 0 | informational warning | no | closed after full summary reconciliation |
| `AUDIT-ERR-COORD-144` | current-head-executable-delta-review | 1 | environment/setup issue | no | closed after syntax-corrected retry |
| `AUDIT-ERR-COORD-145` | current-head-executable-delta-review | 0 | informational warning | no | closed after bounded complete reread |
| `AUDIT-ERR-COORD-146` | current-head-executable-delta-review | 0 | informational warning | no | closed by narrowing subsequent evidence queries |
| `AUDIT-ERR-COORD-147` | current-head-executable-delta-review | 1 | environment/setup issue | no | closed after non-lossy patch separation |
| `AUDIT-ERR-COORD-148` | current-head-executable-delta-validation | 1 | environment/setup issue | no | closed after lossless all-settled retry |
| `AUDIT-ERR-COORD-149` | current-head-executable-delta-validation | 1 | test failure | no | open pending reviewed regeneration of the WebView evidence artifacts |
| `AUDIT-ERR-COORD-150` | current-head-executable-delta-validation | 1 | test failure | no | open pending reviewed ledger/report regeneration and canonical pytest coverage correction |
| `AUDIT-ERR-COORD-151` | current-head-executable-delta-review | 1 | environment/setup issue | no | closed after isolated structured evidence reads |
| `AUDIT-ERR-COORD-152` | current-head-executable-delta-validation | 1 | environment/setup issue | no | closed after corrected PowerShell command structure |
| `AUDIT-ERR-COORD-153` | current-head-executable-delta-validation | 1 | environment/setup issue | no | closed after signature-corrected retry |
| `AUDIT-ERR-COORD-154` | current-head-executable-delta-validation | 0 | informational warning | no | closed after clean exact-current retry |
| `AUDIT-ERR-COORD-155` | non-self-referential-freeze-design | 0 | informational warning | no | closed after bounded complete rereads |
| `AUDIT-ERR-COORD-156` | final-map-refresh-inventory | 0 | informational warning | no | closed by narrowing final reads to canonical top-level artifacts |
| `AUDIT-ERR-COORD-157` | worker-10-current-independent-release-review | 1 | environment/setup issue | no | closed after syntax-corrected retry |
| `AUDIT-ERR-COORD-158` | worker-10-current-independent-release-review | 0 | informational warning | no | closed after narrow file discovery |
| `AUDIT-ERR-COORD-159` | worker-10-current-independent-release-review | n/a | sandbox/permission failure | no | closed with safe non-deleting predicate proof and complete static delete-path trace |
| `AUDIT-ERR-COORD-160` | worker-10-current-independent-release-review | n/a | sandbox/permission failure | no | open nonblocking temp-fixture cleanup limitation |
| `AUDIT-ERR-COORD-161` | worker-10-current-independent-release-review | 1 | test failure | no | open confirmed release-gate blocker pending product remediation |
| `AUDIT-ERR-COORD-162` | worker-10-current-independent-release-review | 0 | informational warning | no | closed after invalid draft removal and reassignment requirement |
| `AUDIT-ERR-COORD-163` | worker-12-current-metrics-review | 1 | environment/setup issue | no | closed after deterministic fixture correction and successful reproduction |
| `AUDIT-ERR-COORD-164` | worker-12-current-metrics-review | 1 | environment/setup issue | no | closed after explicit-path retry |
| `AUDIT-ERR-COORD-165` | worker-12-current-source-review | 1 | environment/setup issue | no | closed after deterministic parser correction |
| `AUDIT-ERR-COORD-166` | worker-12-gap-partitioning | 0 | informational warning | no | closed after lossless aggregate/query-based partitioning |
| `AUDIT-ERR-COORD-167` | worker-12-files-folder-policy-review | 0 | informational warning | no | closed after bounded current-evidence reconciliation |
| `AUDIT-ERR-COORD-168` | worker-12-files-folder-policy-review | 1 | environment/setup issue | no | closed after explicit-path retry |
| `AUDIT-ERR-COORD-169` | worker-12-current-application-shared-ui-validation-review | 0 | environment/setup issue | no | closed after flat-array retry |
| `AUDIT-ERR-COORD-170` | worker-12-current-application-shared-ui-validation-review | 1 | test failure | no | open confirmed stale-test-fixture failure |
| `AUDIT-ERR-COORD-171` | worker-12-current-application-shared-ui-validation-review | 0 | informational warning | no | closed after bounded exact-path reconciliation |
| `AUDIT-ERR-COORD-172` | worker-12-current-maintenance-review | 2 | environment/setup issue | no | closed after glob-filter retry |
| `AUDIT-ERR-COORD-173` | worker-12-current-maintenance-review | 0 | informational warning | no | closed after bounded overlap retry |
| `AUDIT-ERR-COORD-174` | worker-12-current-maintenance-review | 1 | environment/setup issue | no | closed after fixture correction and successful reproduction |
| `AUDIT-ERR-COORD-175` | audit-artifact-publication | n/a | environment/setup issue | no | closed after context-independent Add File publication |
| `AUDIT-ERR-COORD-176` | worker-12-current-validation-review | 0 | informational warning | no | closed after structured bounded reads |
| `AUDIT-ERR-COORD-177` | current-coverage-gap-partitioning | 0 | environment/setup issue | no | closed after direct line recount |
| `AUDIT-ERR-COORD-178` | worker-12-current-maintenance-review | 1 | expected negative-path result | no | closed expected uniqueness result |
| `AUDIT-ERR-COORD-179` | worker-12-current-paths-rerun-review | 1 | expected negative-path result | no | closed after complete-document read |
| `AUDIT-ERR-COORD-180` | worker-12-current-paths-rerun-review | 0 | informational warning | no | closed after bounded rereads |
| `AUDIT-ERR-COORD-181` | worker-12-current-paths-rerun-review | 1 | environment/setup issue | no | closed after corrected probe |
| `AUDIT-ERR-COORD-182` | worker-12-current-paths-rerun-review | 1 | environment/setup issue | no | closed after corrected path |
| `AUDIT-ERR-COORD-183` | worker-12-current-paths-rerun-review | 0 | environment/setup issue | no | closed after schema-correct join |
| `AUDIT-ERR-COORD-184` | worker-12-current-paths-rerun-review | 1 | expected negative-path result | no | closed as expected no-match |
| `AUDIT-ERR-COORD-185` | worker-12-current-paths-rerun-review | 1 | environment/setup issue | no | closed after glob-filter retry |
| `AUDIT-ERR-COORD-186` | worker-12-current-paths-rerun-review | 1 | environment/setup issue | no | closed after syntax-correct retry |
| `AUDIT-ERR-COORD-187` | worker-12-current-paths-rerun-review | 1 | environment/setup issue | no | closed after canonical classification correction |
| `AUDIT-ERR-COORD-188` | worker-12-current-paths-rerun-review | 1 | expected negative-path result | no | closed for slice; global merge intentionally deferred to final freeze |
| `AUDIT-ERR-COORD-DIAG-001` | worker-12-current-diagnostics-review | 1 | environment/setup issue | no | closed after schema-aware retry |
| `AUDIT-ERR-COORD-DIAG-002` | worker-12-current-diagnostics-review | 1 | expected negative-path result | no | closed; expected no-match |
| `AUDIT-ERR-COORD-DIAG-003` | worker-12-current-diagnostics-review | n/a | environment/setup issue | no | closed after command-encoding retry |
| `AUDIT-ERR-COORD-DIAG-004` | worker-12-current-diagnostics-review | 1 | environment/setup issue | no | closed after scoped retry |
| `AUDIT-ERR-COORD-DIAG-005` | worker-12-current-diagnostics-review | 1 | environment/setup issue | no | closed after corrected import |
| `AUDIT-ERR-COORD-DIAG-006` | worker-12-current-diagnostics-review | n/a | environment/setup issue | no | closed after safe literal rewrite |
| `AUDIT-ERR-COORD-DIAG-007` | worker-12-current-diagnostics-review | 0 | environment/setup issue | no | closed after canonical-extension retry |
| `AUDIT-ERR-COORD-DIAG-008` | worker-12-current-diagnostics-review | 1 | environment/setup issue | no | closed after canonical-name retry |
| `AUDIT-ERR-COVERAGE-001` | coverage-universe | n/a | environment/setup issue | no | Agent-orchestration input error only; retain as complete command-error evidence. |
| `AUDIT-ERR-COVERAGE-002` | coverage-universe | 1 | confirmed repository defect | no | Refresh summaries through repository tooling, rerun --check, and record any remaining missing/stale paths before claiming generated-context coverage. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-COVERAGE-003` | coverage-universe | 1 | confirmed repository defect | no | Regenerate the three outputs only through the canonical generator after source summaries settle, then rerun --check. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-COVERAGE-004` | coverage-universe | 1 | expected negative-path result | no | Expected search miss, not a repository failure. |
| `AUDIT-ERR-COVERAGE-005` | coverage-universe | 1 | expected negative-path result | no | Search-scope miss resolved by a broader query; no remaining coverage impact. |
| `AUDIT-ERR-COVERAGE-006` | coverage-universe | 1 | informational warning | no | Generate and validate the missing summary before satisfying the generated-summary completion gate. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-COVERAGE-007` | coverage-universe | 0 | informational warning | no | Preserve as input-integrity warning; do not infer missing trailing requirements beyond the supplied objective. |
| `AUDIT-ERR-COVERAGE-008` | coverage-universe | 0 | informational warning | no | Quiesce concurrent edits, refresh the coverage ledger, and rerun hash and generated-context checks before using the snapshot as completion proof. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-COVERAGE-009` | coverage-universe | 0 | confirmed repository defect | no | Add a strict completion mode that recomputes hashes, rejects every required nonterminal row, validates category/status compatibility, and enforces independent high-risk review. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-COVERAGE-010` | coverage-universe | 0 | confirmed repository defect | no | Regenerate PROJECT_INDEX after summaries stabilize and require zero source-hash mismatches in final coverage validation. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-COVERAGE-011` | coverage-universe | 0 | informational warning | no | Keep Git as the authoritative outer universe and use PROJECT_INDEX only for enrichment; never use index count as exhaustive coverage proof. |
| `AUDIT-ERR-COVERAGE-012` | coverage-universe | 0 | informational warning | no | Do not inherit semantic completion from the prior audit; reconcile findings and symbols path by path against current hashes. |
| `AUDIT-ERR-COVERAGE-013` | coverage-universe | 0 | confirmed repository defect | no | Restore one-to-one current source/summary/index reconciliation where required, document intentional exclusions, and rerun both canonical --check commands. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-FINAL-COORD-001` | final-audit-state-discovery | 1 | expected negative-path result | no | closed after bounded canonical diagnostics |
| `AUDIT-ERR-FINAL-COORD-002` | final-audit-fragment-discovery | 1 | environment/setup issue | no | closed after corrected orchestration |
| `AUDIT-ERR-FINAL-COORD-003` | final-synthesis-preparation | 1 | environment/setup issue | no | closed after corrected orchestration |
| `AUDIT-ERR-FINAL-COORD-004` | final-audit-concurrent-publication | 0 | informational warning | no | closed by excluding in-flight output from conclusions; clean frozen retry required |
| `AUDIT-ERR-FINAL-COORD-005` | final-synthesis-preparation | 1 | environment/setup issue | no | closed after corrected bounded read |
| `AUDIT-ERR-FINAL-COORD-006` | external-freeze-preflight | 0 | environment/setup issue | no | closed after corrected non-destructive copy |
| `AUDIT-ERR-FINAL-COORD-007` | global-completion-gate | 1 | environment/setup issue | no | closed after corrected read-only query |
| `AUDIT-ERR-FINAL-COORD-008` | finding-location-reconciliation | 1 | environment/setup issue | no | closed after corrected bounded search |
| `AUDIT-ERR-FINAL-COORD-009` | external-freeze-preflight | 1 | test failure | no | retained as a confirmed audit-tool finding; does not block the verified external bytes |
| `AUDIT-ERR-FINAL-COORD-010` | external-cli-finding-deduplication | 1 | environment/setup issue | no | closed after corrected bounded search |
| `AUDIT-ERR-FINAL-COORD-011` | change-packet-finalization | 1 | test failure | no | closed after explicit path capture; final strict retry evidence retained |
| `AUDIT-ERR-FINAL-COORD-012` | final-reference-gate | 1 | test failure | no | retained as a known product/documentation-tooling finding; does not represent missing audit coverage |
| `AUDIT-ERR-FINAL-EXTWRITE-INDEP-001` | final external-ledger CLI independent reproduction | 1 | confirmed repository defect | no | finding independently confirmed; remediation remains separate |
| `AUDIT-ERR-FINAL-REMAINING-001` | scope discovery | 0 | informational warning | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-002` | audit contract inspection | 0 | informational warning | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-003` | network semantic review | 0 | informational warning | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-004` | configuration/docs/tooling semantic review | 0 | informational warning | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-005` | operator script and test review | 0 | informational warning | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-006` | structured-record semantic review | 1 | environment/setup issue | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-007` | structured-record semantic review | 0 | informational warning | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-008` | targeted behavioral validation | 1 | test failure | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FINAL-REMAINING-009` | final target reconciliation | 1 | environment/setup issue | no | Closed by the stated bounded retry or exact-current alternate evidence; no review conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-FRIND-001` | independent-navigation | n/a | environment/setup issue | no | Resolved for coverage by the deterministic fallback and complete bounded reads. |
| `AUDIT-ERR-FRIND-002` | summary-first-navigation | 0 | informational warning | no | Resolved by isolated summary rereads. |
| `AUDIT-ERR-FRIND-003` | semantic-line-review | 0 | informational warning | no | Resolved by complete bounded rereads. |
| `AUDIT-ERR-FRIND-004` | semantic-line-review | 0 | informational warning | no | Resolved by bounded nonoverlapping rereads. |
| `AUDIT-ERR-FRIND-005` | focused-independent-reproduction | 1 | test failure | no | Resolved by correcting the synthetic fixture type. |
| `AUDIT-ERR-FRIND-006` | focused-independent-reproduction | 1 | test failure | no | Resolved; the final focused fixture passed. |
| `AUDIT-ERR-FRIND-007` | artifact-and-test-navigation | 1 | environment/setup issue | no | Resolved; no semantic coverage relied on the failed discovery commands. |
| `AUDIT-ERR-GGEN-INDEP-001` | global generated aggregate-map provenance verification | 1 | confirmed repository defect | no | finding-backed generated verification; coordinator regeneration remains separate |
| `AUDIT-ERR-GGEN-INDEP-002` | global generated aggregate-map provenance verification | 1 | confirmed repository defect | no | finding-backed generated verification; coordinator regeneration remains separate |
| `AUDIT-ERR-GHRIND-001` | independent-navigation | n/a | environment/setup issue | no | Resolved for coverage by the deterministic fallback and complete bounded reads. |
| `AUDIT-ERR-GHRIND-002` | semantic-line-review | 0 | informational warning | no | Resolved by complete isolated reread. |
| `AUDIT-ERR-GHRIND-003` | focused-validation | 124 | informational warning | no | Recorded as an unresolved execution limitation, not interpreted as a test pass or failure; semantic review coverage remains complete. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-001` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-002` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-003` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-004` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-005` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-006` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-007` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-008` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-009` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-010` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-011` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-GLOBAL-AUTHORED-FINAL-012` | independent-attestation join reconciliation | 0 | informational warning | no | Recorded for parent central reconciliation; exact-current independent review and hash coverage are complete, and no central artifact was altered. |
| `AUDIT-ERR-HEAD-DELTA-001` | current-head-delta-discovery | 0 | informational warning | no | closed after bounded retry |
| `AUDIT-ERR-HEAD-DELTA-002` | current-head-delta-artifact-correction | 1 | environment/setup issue | no | closed after serialization-matched retry |
| `AUDIT-ERR-INDEP-P1-001` | independent-current-p1-schema-discovery | 1 | environment/setup issue | no | closed after bounded canonical-path retry |
| `AUDIT-ERR-INDEP-P1-002` | independent-current-p1-source-and-test-review | 0 | informational warning | no | closed after bounded exact-source reads |
| `AUDIT-ERR-INDEP-P1-003` | independent-current-p1-defect-reproduction | 0 | expected negative-path result | no | evidence-bearing expected defect result; P1 finding independently confirmed |
| `AUDIT-ERR-INDEP-P1-004` | independent-current-p1-defect-reproduction | 0 | expected negative-path result | no | evidence-bearing expected defect result; threshold finding independently confirmed |
| `AUDIT-ERR-INDEP-P1-005` | independent-current-p1-focused-validation | 1 | test failure | no | existing finding-backed failure; scoped validation completed cleanly |
| `AUDIT-ERR-INDEP-P1-006` | independent-current-p1-defect-reproduction | 0 | expected negative-path result | no | evidence-bearing expected defect result; distinct P3 finding confirmed |
| `AUDIT-ERR-INDEP-P1-007` | independent-current-p1-artifact-validation | 1 | environment/setup issue | no | closed after full-universe validation |
| `AUDIT-ERR-INDEP-P1-008` | independent-current-p1-artifact-validation | 1 | informational warning | no | awaiting owning coordinator correction; independent review conclusions are unaffected |
| `AUDIT-ERR-INDEP-P1-009` | independent-current-p1-first-pass-reconciliation | 1 | environment/setup issue | no | closed after syntax-correct bounded retry |
| `AUDIT-ERR-INDEP-P1-010` | independent-current-p1-artifact-validation | 0 | informational warning | no | closed by loader-compatible authoritative rename |
| `AUDIT-ERR-INDEP-P1-011` | independent-current-p1-artifact-placement | 1 | environment/setup issue | no | closed after valid apply_patch move |
| `AUDIT-ERR-PIPEIND-001` | independent-navigation | n/a | environment/setup issue | no | Recorded; deterministic fallback and exact-source navigation completed the required coverage. |
| `AUDIT-ERR-PIPEIND-002` | semantic-line-review | 0 | informational warning | no | Resolved by bounded rereads. |
| `AUDIT-ERR-PIPEIND-003` | semantic-line-review | 0 | informational warning | no | Resolved by bounded rereads. |
| `AUDIT-ERR-PIPEIND-004` | semantic-line-review | 0 | informational warning | no | Resolved by a complete isolated reread. |
| `AUDIT-ERR-PIPEIND-005` | p1-independent-reproduction | n/a | environment/setup issue | no | Resolved for coverage; successful independent fixture evidence was captured. |
| `AUDIT-ERR-PIPEIND-006` | p1-independent-reproduction-cleanup | n/a | environment/setup issue | no | Recorded as an external temporary cleanup remainder; audit evidence remains valid. |
| `AUDIT-ERR-PIPEIND-007` | focused-validation | 1 | environment/setup issue | no | Resolved by all-settled retry. |
| `AUDIT-ERR-PIPEIND-008` | focused-validation | 1 | test failure | no | Resolved by loading the production dependency expected by the exercised branch. |
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
| `AUDIT-ERR-PRIOR-015` | prior-audit-reconciliation | 0 | missing external fixture | no | Zero alerts is not a clean result; current-branch CodeQL coverage remains unproven until an authorized scan runs. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
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
| `AUDIT-ERR-PRIOR-PROD-013` | prior-production-audit-validation | 1 | test failure | no | open product/test failure Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-PRIOR-PROD-014` | prior-production-audit-validation | 1 | confirmed repository defect | no | separate current artifact drift for coordinator/owning worker; original finding root classified fixed |
| `AUDIT-ERR-PRIOR-PROD-015` | prior-production-audit-validation | 1 | confirmed repository defect | no | separate artifact drift retained; original false-green defect fixed |
| `AUDIT-ERR-PRIOR-PROD-016` | prior-production-audit-validation | 0 | expected negative-path result | no | closed expected warning |
| `AUDIT-ERR-PRIOR-PROD-017` | prior-production-audit-reconciliation | 1 | environment/setup issue | no | closed after correct-path execution |
| `AUDIT-ERR-PRIOR-PROD-018` | prior-production-audit-reconciliation | 0 | informational warning | no | mitigated |
| `AUDIT-ERR-PRIOR-PROD-019` | prior-production-audit-reconciliation | n/a | informational warning | no | terminal audit coverage remains pending independent review Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-PRIOR-PROD-020` | prior-production-audit-validation | n/a | informational warning | no | release/field validation outstanding; current source classifications remain bounded to available evidence |
| `AUDIT-ERR-SMOKE-FIRST-001` | assignment-discovery | 1 | environment/setup issue | no | closed after corrected projection |
| `AUDIT-ERR-SMOKE-FIRST-002` | assignment-discovery | 0 | informational warning | no | closed after exact line-count recovery |
| `AUDIT-ERR-SMOKE-FIRST-003` | prior-finding-reconciliation | 2 | environment/setup issue | no | closed after corrected glob invocation |
| `AUDIT-ERR-SMOKE-FIRST-004` | prior-finding-reconciliation | 1 | expected negative-path result | no | accepted as negative evidence |
| `AUDIT-ERR-SMOKE-FIRST-005` | host-contract-reconciliation | 2 | environment/setup issue | no | closed after corrected search |
| `AUDIT-ERR-SMOKE-FIRST-006` | host-contract-reconciliation | 0 | informational warning | no | closed after bounded authoritative read |
| `AUDIT-ERR-SMOKE-FIRST-007` | syntax-validation | 1 | environment/setup issue | no | closed after clean parser retry |
| `AUDIT-ERR-SMOKE-FIRST-008` | focused-validation | 1 | test failure | no | recorded as external focused-test failures; smoke source review continued |
| `AUDIT-ERR-SMOKE-FIRST-009` | direct-wrapper-validation | 1 | test failure | no | recorded; no smoke-wrapper coverage was blocked |
| `AUDIT-ERR-SMOKE-FIRST-010` | structured-result-review | 0 | informational warning | no | closed after bounded reads |
| `AUDIT-ERR-SMOKE-FIRST-011` | focused-validation | 1 | test failure | no | recorded as an external stale assertion |
| `AUDIT-ERR-SMOKE-FIRST-012` | prior-finding-reconciliation | 1 | expected negative-path result | no | accepted as negative reconciliation evidence |
| `AUDIT-ERR-SMOKE-FIRST-013` | skip-semantics-review | 1 | environment/setup issue | no | closed after corrected search |
| `AUDIT-ERR-SMOKE-FIRST-014` | skip-semantics-review | 1 | environment/setup issue | no | closed after direct reproduction |
| `AUDIT-ERR-SMOKE-FIRST-015` | artifact-schema-preparation | 0 | informational warning | no | closed after bounded validator reads |
| `AUDIT-ERR-SMOKE-FIRST-016` | artifact-schema-preparation | 1 | expected negative-path result | no | accepted as negative evidence |
| `AUDIT-ERR-SMOKE-FIRST-017` | prior-finding-reconciliation | 0 | informational warning | no | closed after bounded reconciliation |
| `AUDIT-ERR-SMOKE-FIRST-018` | defect-reproduction | 0 | confirmed repository defect | no | confirmed and recorded |
| `AUDIT-ERR-SMOKE-FIRST-019` | artifact-validation | 1 | environment/setup issue | no | closed after owner correction and clean global retry; smoke slice coverage remained complete |
| `AUDIT-ERR-UI-DELTA-001` | assignment-discovery | 0 | environment/setup issue | no | Recorded and recovered; no coverage conclusion relied on the empty result. |
| `AUDIT-ERR-UI-DELTA-002` | assignment-discovery | 0 | informational warning | no | Recorded and recovered; no source or review evidence depended on the truncated display. |
| `AUDIT-ERR-UI-DELTA-003` | ledger-tool-discovery | 2 | environment/setup issue | no | Recorded and recovered. |
| `AUDIT-ERR-UI-DELTA-004` | change-reconciliation | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-UI-DELTA-005` | focused-validation | 1 | test failure | no | Recorded and isolated; the remaining focused coverage passed. |
| `AUDIT-ERR-UI-DELTA-006` | focused-validation-isolation | 1 | test failure | no | Recorded as an external validation failure; semantic coverage of the assigned files is complete. |
| `AUDIT-ERR-UI-DELTA-007` | focused-validation-isolation | 1 | test failure | no | Recorded, reproduced, and linked. |
| `AUDIT-ERR-UI-DELTA-008` | finding-reconciliation | 0 | expected negative-path result | no | Recorded as expected negative evidence. |
| `AUDIT-ERR-UI-DELTA-009` | focused-validation-diagnostics | 1 | informational warning | no | Recorded; diagnostic truncation did not block coverage or the finding. |
| `AUDIT-ERR-UI-DELTA-010` | review-fragment-construction | 1 | environment/setup issue | no | Recorded and recovered. |
| `AUDIT-ERR-UI-DELTA-011` | review-fragment-construction | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-UI-DELTA-012` | finding-evidence-reconciliation | 0 | environment/setup issue | no | Recorded and recovered; the corrected source evidence is complete. |
| `AUDIT-ERR-UI-DELTA-013` | global-fragment-validation | 1 | environment/setup issue | no | Recorded, externally corrected by the owning worker, and resolved; assigned semantic coverage was never blocked. |
| `AUDIT-ERR-UI-DELTA-014` | artifact-identity-check | 0 | environment/setup issue | no | Recorded and recovered; no duplicate definition exists. |
| `AUDIT-ERR-VALIDATION-001` | validation-spine | 1 | environment/setup issue | no | Resolved during inspection; retained as command-level evidence. |
| `AUDIT-ERR-VALIDATION-002` | validation-spine | 2 | environment/setup issue | no | Resolved by safe PowerShell quoting; no audit coverage remained blocked. |
| `AUDIT-ERR-VALIDATION-003` | validation-spine | 0 | informational warning | no | Superseded by the clean final environment inventory; warning preserved. |
| `AUDIT-ERR-VALIDATION-004` | validation-spine | 1 | environment/setup issue | no | Resolved during inspection; final inventory values were based only on the successful retry. |
| `AUDIT-ERR-VALIDATION-005` | validation-spine | 0 | environment/setup issue | no | Resolved by using a literal bounded read; warning did not affect the recorded packaging findings. |
| `AUDIT-ERR-VALIDATION-006` | validation-spine | 1 | environment/setup issue | no | Resolved; the final 67-script Unit inventory and 33-script aggregate count came from the successful query. |
| `AUDIT-ERR-VALIDATION-007` | validation-spine | 1 | environment/setup issue | no | Resolved; absence of those optional config files was not treated as a test failure. |
| `AUDIT-ERR-VALIDATION-008` | validation-spine | 1 | expected negative-path result | no | Open limitation: the current repository spine cannot prove dynamic execution of every source line without adding or externally supplying coverage instrumentation. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-009` | validation-spine | 0 | informational warning | no | Mitigated through bounded reads; no final claim relies on the truncated listing alone. |
| `AUDIT-ERR-VALIDATION-010` | validation-spine | 0 | informational warning | no | Expected navigation limitation; mitigated with targeted reads in accordance with AGENTS.md. |
| `AUDIT-ERR-VALIDATION-011` | validation-spine | 0 | informational warning | no | Benign diagnostic stream use, not a validation failure. |
| `AUDIT-ERR-VALIDATION-012` | validation-spine | 0 | informational warning | no | Preserved as an evidence-attribution limitation; unrelated and concurrent changes must not be absorbed into this worker's conclusions. |
| `AUDIT-ERR-VALIDATION-013` | validation-spine | 0 | informational warning | no | Do not cite the preflight result as pass evidence; it is planning evidence only. |
| `AUDIT-ERR-VALIDATION-014` | validation-spine | n/a | missing external fixture | no | Local CodeQL coverage remains blocked; use the repository's remote CodeQL workflow and retain its artifact/result. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-015` | validation-spine | n/a | missing external fixture | no | Local Semgrep coverage remains blocked until the scanner is provisioned; CI's Semgrep step is also non-gating because it uses continue-on-error. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-016` | validation-spine | n/a | environment/setup issue | no | Mitigated by the bundled Python module; commands must use the module form for reproducibility. |
| `AUDIT-ERR-VALIDATION-017` | validation-spine | 0 | informational warning | no | No objective requirement used by this worker was lost; exact downstream claims were verified from repository source. |
| `AUDIT-ERR-VALIDATION-018` | validation-spine | 0 | informational warning | no | Corrected before reporting; only the reconciled count of 26 is authoritative. |
| `AUDIT-ERR-VALIDATION-019` | validation-spine | 0 | confirmed repository defect | no | Open reproducibility risk; declare/provision pytest or stop relying on it in environments built from requirements/dev.txt alone. |
| `AUDIT-ERR-VALIDATION-020` | validation-spine | 0 | confirmed repository defect | no | The audit may inventory every file and test surface, but it must not claim every executable line ran without adding language-appropriate coverage collection. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-021` | validation-spine | n/a | informational warning | no | No pass/fail claim should be inferred from this worker; dynamic evidence must come from the orchestrated validation run. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-022` | validation-spine | n/a | informational warning | no | Real-media behavior remains unvalidated by this subtask and must be reported separately, never silently inferred from generated-media tests. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-023` | validation-spine | 0 | confirmed repository defect | no | Deep Audit cannot be treated as automatic validation for normal code pushes until trigger policy is broadened or another required workflow supplies equivalent coverage. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-024` | validation-spine | 0 | confirmed repository defect | no | The workflow can be green with omitted modules or environment-driven skips; require the strict wrapper and complete generated inventory. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-025` | validation-spine | 0 | confirmed repository defect | no | Unittest success alone is incomplete; execute the pytest supplement or convert/integrate these tests into canonical discovery. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-026` | validation-spine | 0 | confirmed repository defect | no | Make dependency provisioning explicit before treating private-beta pytest execution as reproducible. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-027` | validation-spine | 0 | confirmed repository defect | no | Deep-audit suite success is insufficient without the four omitted generated/inventory checks or an updated suite definition. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-028` | validation-spine | 0 | confirmed repository defect | no | Do not include this generator in an unattended read-only audit unless mutations are isolated or a non-mutating --check mode is implemented. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-029` | validation-spine | 0 | confirmed repository defect | no | Current local coverage is available; future evidence must record analyzer presence/version and reject the warning path for strict gates. |
| `AUDIT-ERR-VALIDATION-030` | validation-spine | 0 | confirmed repository defect | no | Current environment is capable, but default release evidence can downshift on another host; strict switches should be required for gating. |
| `AUDIT-ERR-VALIDATION-031` | validation-spine | 0 | confirmed repository defect | no | Do not equate npm run check with Tauri/Rust test coverage. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-032` | validation-spine | 0 | confirmed repository defect | no | Release validation must use -RequireTests and retain per-suite output; a default-mode green result is not strict pass evidence. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-033` | validation-spine | 0 | confirmed repository defect | no | Treat SARIF as artifact generation only unless separate policy gates scan execution and findings. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-034` | validation-spine | 0 | confirmed repository defect | no | Run the remote closure scan with explicit result retention/upload settings and link the artifact in final evidence. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-035` | validation-spine | 0 | confirmed repository defect | no | Aggregate success is partial evidence only; retain a complete 67-script result ledger. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-036` | validation-spine | 0 | confirmed repository defect | no | Record tool paths and reject green skip output in strict audit evidence. |
| `AUDIT-ERR-VALIDATION-037` | validation-spine | 0 | missing external fixture | no | Report hardware paths as unvalidated unless the opt-in matrix runs and records actual device/driver evidence. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-038` | validation-spine | 0 | confirmed repository defect | no | A green SKIP is not adversarial-kill coverage; retain codec availability and exercised-case evidence. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-039` | validation-spine | 0 | missing external fixture | no | Do not use -AllowMissingTools for audit closure; record any SKIP as missing coverage. |
| `AUDIT-ERR-VALIDATION-040` | validation-spine | 0 | confirmed repository defect | no | Named wrapper enumeration alone is incomplete; drive execution from the generated module inventory. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-VALIDATION-041` | validation-spine | 0 | informational warning | no | Use the prior ledger for provenance only; obtain current-commit/worktree evidence before closure. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W01-001` | worker-01-semantic-review | 0 | informational warning | no | The truncated broad output was discarded for baseline data; exact parsed rows are the retained evidence. |
| `AUDIT-ERR-W01-002` | worker-01-semantic-review | 0 | confirmed repository defect | no | No assigned source coverage is blocked; the generated-docs owner should restore the missing summary before that test row is reviewed through the normal navigation workflow. |
| `AUDIT-ERR-W01-003` | worker-01-fragment-construction | 0 | informational warning | no | No fragment field or finding evidence depends on the truncated example output; targeted source ranges and local validators are authoritative. |
| `AUDIT-ERR-W01-004` | worker-01-semantic-review | n/a | informational warning | no | Do not infer a test pass or runtime reachability result from this slice. Dynamic validation and independent second review remain required before terminal high-risk coverage. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W01-005` | worker-01-resumed-orientation | 0 | informational warning | no | Discarded the truncated preview as evidence; all retained orientation facts came from the successful bounded retry. |
| `AUDIT-ERR-W01-006` | worker-01-prior-finding-reconciliation | 1 | environment/setup issue | no | The failed search produced no usable reconciliation evidence and will not be relied upon. |
| `AUDIT-ERR-W01-007` | worker-01-prior-finding-reconciliation | 1 | expected negative-path result | no | No prior finding alias was identified by the exact shutdown-timer terms; broader path-local reconciliation remains required before finalizing any new record. |
| `AUDIT-ERR-W01-008` | worker-01-focused-test-discovery | n/a | environment/setup issue | no | No repository command ran and no evidence was produced by the failed wrapper. |
| `AUDIT-ERR-W01-009` | worker-01-candidate-validation | 0 | informational warning | no | The truncated broad search is discarded as evidence; no conclusion will rely on omitted output. |
| `AUDIT-ERR-W01-010` | worker-01-candidate-validation | 0 | expected negative-path result | no | Retained as direct reproduction evidence; no application or operator state was mutated. |
| `AUDIT-ERR-W01-011` | worker-01-fragment-validation | 1 | expected negative-path result | no | No repository defect is implied; this was a tooling symbol-name lookup miss. |
| `AUDIT-ERR-W01-012` | worker-01-line-review | 0 | informational warning | no | The truncated output is not accepted as line-review evidence and no conclusion will rely on omitted content. |
| `AUDIT-ERR-W01-013` | worker-01-parallelization | n/a | environment/setup issue | no | No repository command ran, no review evidence was produced, and no repository defect is implied. |
| `AUDIT-ERR-W01-014` | worker-01-prior-finding-reconciliation | 1 | expected negative-path result | no | No repository defect is implied by the search exit itself; it establishes that the candidate is not already recorded under those exact strings. |
| `AUDIT-ERR-W01-015` | worker-01-review-checkpoint-write | 1 | informational warning | no | No source or product file was changed; the review fragment is valid again and all affected exact-hash rows are covered. |
| `AUDIT-ERR-W01-016` | worker-01-error-ledger-normalization | n/a | environment/setup issue | no | The rejected patch changed no repository or audit content and produced no validation evidence. |
| `AUDIT-ERR-W01-017` | worker-01-error-ledger-normalization | n/a | environment/setup issue | no | No repository command ran, no file changed, and no evidence was produced by the failed wrapper. |
| `AUDIT-ERR-W01-018` | worker-01-remaining-path-discovery | 0 | informational warning | no | Only the small directory listing is retained; the truncated ripgrep projection is discarded. |
| `AUDIT-ERR-W01-019` | worker-01-network-call-site-reconciliation | 1 | expected negative-path result | no | Retained as negative reachability evidence; it is not a repository command failure or product runtime error. |
| `AUDIT-ERR-W01-020` | worker-01-network-effective-config-lifecycle-reconciliation | 1 | environment/setup issue | no | The failed second search produced no complete cleanup evidence and will not be relied upon; no file was changed. |
| `AUDIT-ERR-W01-021` | worker-01-finding-fragment-validation | 0 | environment/setup issue | no | The local-only issue is not treated as a finding-record defect; no finding record or product file was changed before the cross-fragment retry. |
| `AUDIT-ERR-W01-022` | worker-01-review-fragment-append | 0 | environment/setup issue | no | No product or central-ledger file was touched; complete appended rows are retained and the malformed W01-local row will be replaced. |
| `AUDIT-ERR-W01-023` | worker-01-review-fragment-append-diagnosis | 0 | expected negative-path result | no | The parser failure is retained as evidence of the malformed append; no inference from the invalid row is used. |
| `AUDIT-ERR-W01-024` | worker-01-network-rerun-rollback-test-reconciliation | 1 | expected negative-path result | no | No product or audit conclusion was changed by the command itself; the negative result supports a test-coverage gap only. |
| `AUDIT-ERR-W01-025` | worker-01-worker-state-watch-registry-proof | 1 | environment/setup issue | no | No repository, product state, media, network, or operator state was changed by the failed probe. |
| `AUDIT-ERR-W01-026` | worker-01-settings-patch-smoke-call-site-reconciliation | 0 | informational warning | no | The truncated broad output is discarded; no file or runtime state was changed. |
| `AUDIT-ERR-W01-027` | worker-01-final-finding-validation | n/a | informational warning | no | No repository or product state changed; validation remains pending until the bounded retry completes. |
| `AUDIT-ERR-W01-028` | worker-01-final-hash-reconciliation | 1 | environment/setup issue | no | The first 19 positive hash checks are retained, but final closing-hash evidence awaits the corrected full retry; no repository or product state changed. |
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
| `AUDIT-ERR-W02-005` | worker-02-settings-boundary-validation | 1 | test failure | no | Clean direct-module evidence for three authority/recovery cases remains blocked until the production-inaccurate test double is corrected. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W02-006` | worker-02-settings-boundary-validation | 1 | test failure | no | The repeated error confirms a fixture/platform defect rather than a transient run; the specific test remains blocked. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W02-007` | worker-02-findings-finalization | 0 | informational warning | no | Combined output discarded as a completeness source; bounded exact reads are authoritative. |
| `AUDIT-ERR-W02-008` | worker-02-prior-audit-reconciliation | 1 | environment/setup issue | no | Correct prior-audit locations supplied the retained reconciliation evidence. |
| `AUDIT-ERR-W02-009` | worker-02-artifact-discovery | 1 | environment/setup issue | no | All worker artifacts were created under the canonical workers directory. |
| `AUDIT-ERR-W02-010` | worker-02-fragment-schema-inspection | 1 | environment/setup issue | no | The failed read was replaced by a bounded fixed-range read; schema inspection is complete. |
| `AUDIT-ERR-W02-011` | worker-02-settings-replay-proof | 0 | informational warning | no | Only the normalized retry is retained as behavioral proof; the initial conflict is recorded to preserve the complete probe trail. |
| `AUDIT-ERR-W02-012` | worker-02-fragment-validation | 0 | informational warning | no | Corrected mechanically through apply_patch; initial invalid fragment state is not retained. |
| `AUDIT-ERR-W02-013` | worker-02-fragment-validation | 0 | informational warning | no | Mechanical schema normalization applied; no review evidence or finding semantics changed. |
| `AUDIT-ERR-W02-014` | worker-02-global-integration-check | 0 | informational warning | no | Local slice is ready for coordinator integration; global merge remains coordinator-owned and blocked until unrelated fragments/baseline are reconciled. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W02-015` | worker-02 exact path-local finding reconciliation | 1 | environment/setup issue | no | Closed after exact-path discovery; the failed lookup supplied no review evidence. |
| `AUDIT-ERR-W02-016` | worker-02 error-ledger recording | 1 | environment/setup issue | no | Closed after exact-context apply_patch retry. |
| `AUDIT-ERR-W02-017` | worker-02 generated-summary semantic review | 0 | informational warning | no | Closed by bounded rereads of every affected summary. |
| `AUDIT-ERR-W02-018` | worker-02 generated-summary prior-finding reconciliation | 1 | environment/setup issue | no | Closed after corrected bounded prior-finding search. |
| `AUDIT-ERR-W02-019` | worker-02 control-flag schema prior-finding reconciliation | 1 | expected negative-path result | no | Closed as expected negative-path evidence. |
| `AUDIT-ERR-W02-020` | worker-02 PowerShell semantic review | 0 | informational warning | no | Closed by bounded rereads of every affected source line. |
| `AUDIT-ERR-W02-021` | worker-02 PowerShell semantic review | 0 | informational warning | no | Closed by a standalone reread of the only clipped range. |
| `AUDIT-ERR-W02-022` | worker-02 Python semantic review | 0 | informational warning | no | Closed by the standalone reread of the only clipped range. |
| `AUDIT-ERR-W02-023` | worker-02 error-ledger schema repair | 0 | informational warning | no | Closed by exact local-record correction; the clipped search is not used as evidence. |
| `AUDIT-ERR-W02-024` | worker-02 candidate deduplication | 0 | informational warning | no | Closed by bounded exact-term retry. |
| `AUDIT-ERR-W02-025` | worker-02 generated-summary semantic reproduction | 1 | expected negative-path result | no | Closed by bounded no-match-aware retry; the successful summary lines remain valid evidence. |
| `AUDIT-ERR-W02-026` | worker-02 finding location binding | 0 | environment/setup issue | no | Closed after exact-path discovery and bounded retry. |
| `AUDIT-ERR-W02-027` | worker-02 finding location binding | 1 | expected negative-path result | no | Closed by repository-wide exact-name discovery. |
| `AUDIT-ERR-W02-028` | worker-02 finding artifact construction | 1 | environment/setup issue | no | Closed after corrected apply_patch hunk construction. |
| `AUDIT-ERR-W02-029` | worker-02 finding artifact construction | 1 | environment/setup issue | no | Closed after robust tail extraction and corrected append. |
| `AUDIT-ERR-W02-030` | worker-02 error-fragment validation | 1 | environment/setup issue | no | Closed after full-universe validation retry. |
| `AUDIT-ERR-W02-031` | worker-02 late generated-context deduplication | 1 | expected negative-path result | no | Closed after owner-resolution retry. |
| `AUDIT-ERR-W02-HR-001` | worker-02-high-risk-independent-scope-discovery | 0 | informational warning | no | Resolved by bounded replacement queries; the truncated output was not used as audit evidence. |
| `AUDIT-ERR-W02-HR-002` | worker-02-high-risk-independent-validator-discovery | 1 | environment/setup issue | no | Resolved by exact-path reads; partial wildcard output was not used as final evidence. |
| `AUDIT-ERR-W02-HR-003` | worker-02-high-risk-independent-scope-census | 0 | informational warning | no | Resolved by fixed bounded ranges and an aggregate reconciliation; no path was inferred from truncated output. |
| `AUDIT-ERR-W02-HR-004` | worker-02-high-risk-independent-exact-source-review | 0 | informational warning | no | Resolved by complete bounded replacement reads; the truncated parallel response was not used as attestation evidence. |
| `AUDIT-ERR-W02-HR-005` | worker-02-high-risk-independent-validation-discovery | 1 | informational warning | no | Resolved by canonical test inventory and direct execution; the empty tests-directory query was not treated as evidence. |
| `AUDIT-ERR-W02-HR-006` | worker-02-high-risk-independent-validation-discovery | 0 | informational warning | no | Resolved by exact canonical test execution; truncated search output was not used as final evidence. |
| `AUDIT-ERR-W02-HR-007` | worker-02-high-risk-independent-official-validation | 1 | environment/setup issue | no | Resolved for this worker scope; foreign coordinator error fragments were preserved and remain a separate global-ledger issue. |
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
| `AUDIT-ERR-W03-IR-001` | worker-03-independent-navigation | n/a | environment/setup issue | no | Recorded; fallback navigation completed successfully and exact-source review continues. |
| `AUDIT-ERR-W03-IR-002` | worker-03-independent-navigation | 0 | informational warning | no | Recorded; the context mismatch is not used as coverage evidence and does not block exact review. |
| `AUDIT-ERR-W03-IR-003` | worker-03-independent-artifact-schema-discovery | 1 | environment/setup issue | no | Recorded for execution completeness; serial retry succeeded. |
| `AUDIT-ERR-W03-IR-004` | worker-03-independent-p1-validation | 1 | test failure | no | P1 finding independently confirmed; retain exact failure evidence. |
| `AUDIT-ERR-W03-IR-005` | worker-03-independent-p1-validation | n/a | environment/setup issue | no | Recorded as an invocation issue; safer non-recursive retry required. |
| `AUDIT-ERR-W03-IR-006` | worker-03-independent-finding-path-orientation | 0 | environment/setup issue | no | Failed output discarded; corrected summary reads required. |
| `AUDIT-ERR-W03-IR-007` | worker-03-independent-dependency-validation | 0 | informational warning | no | Broad output discarded as complete evidence; compact parsed retry required. |
| `AUDIT-ERR-W03-IR-008` | worker-03-independent-no-finding-validation | 124 | environment/setup issue | no | Recorded; longer bounded retry required before PowerShell queue-engine validation can be credited. |
| `AUDIT-ERR-W03-IR-009` | worker-03-independent-generated-provenance | 1 | informational warning | no | Recorded and segregated as unrelated; W03 generated coverage requires a scoped current-hash proof rather than crediting the failed global check. |
| `AUDIT-ERR-W03-IR-010` | worker-03-independent-generated-provenance | 1 | environment/setup issue | no | Recorded; failed invocation discarded and corrected read-only retry required. |
| `AUDIT-ERR-W04-001` | pending-publish concurrency review | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-002` | pending-publish concurrency review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-003` | pending-publish destination-race reproduction | 0 | environment/setup issue | no | closed by static reconciliation; runtime proof intentionally deferred |
| `AUDIT-ERR-W04-004` | W04 continuation evidence inventory | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-005` | W04 audit-ledger schema discovery | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-006` | W04 source-scope inventory | 0 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-007` | W04 error-fragment validation | 0 | informational warning | no | closed for W04; external finding-location correction reported |
| `AUDIT-ERR-W04-008` | W04 early source-row checkpoint publication | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-009` | completed-domain static semantic review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-010` | PowerShell pending-publish static semantic review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-011` | completed-domain prior-audit relationship check | 1 | environment/setup issue | no | closed; normal no-match exit classified |
| `AUDIT-ERR-W04-012` | rename undo test-coverage review | 0 | informational warning | no | closed after bounded reread |
| `AUDIT-ERR-W04-013` | pending-publish destination-concurrency review | 0 | informational warning | no | closed after bounded rereads |
| `AUDIT-ERR-W04-014` | W04 prior-finding relationship reconciliation | 1 | environment/setup issue | no | closed by corrected syntax |
| `AUDIT-ERR-W04-015` | W04 prior-finding relationship reconciliation | 0 | informational warning | no | closed after compact retry |
| `AUDIT-ERR-W04-016` | final-library promotion test-coverage review | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-017` | completed-domain deferred-proof evidence review | 2 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-018` | W04 source review-row publication preflight | 0 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-019` | W04 212-row review-fragment publication | 0 | environment/setup issue | no | closed after full tail regeneration |
| `AUDIT-ERR-W04-020` | W04 malformed review-row diagnosis | 1 | environment/setup issue | no | closed by corrected retry |
| `AUDIT-ERR-W04-021` | W04 malformed review-row repair | n/a | environment/setup issue | no | closed by policy-compatible bounded rewrite |
| `AUDIT-ERR-W04-022` | W04 malformed review-row repair | 1 | environment/setup issue | no | closed by corrected validator |
| `AUDIT-ERR-W04-023` | W04 malformed review-row repair | 1 | environment/setup issue | no | closed by bounded literal validation |
| `AUDIT-ERR-W04-024` | W04 malformed review-row repair | 1 | environment/setup issue | no | closed by simplified retry |
| `AUDIT-ERR-W04-025` | W04 malformed review-row repair | 1 | environment/setup issue | no | closed by explicit empty-array initialization |
| `AUDIT-ERR-W04-026` | W04 post-rebuild review validation | 1 | environment/setup issue | no | closed by corrected syntax |
| `AUDIT-ERR-W04-027` | W04 post-rebuild path-local finding validation | 0 | informational warning | no | closed by authoritative repository validator |
| `AUDIT-ERR-W04-028` | W04 final fragment validation | 0 | informational warning | no | closed for W04; external error-classification correction reported |
| `AUDIT-ERR-W04-029` | W04 final change-packet coverage validation | 1 | informational warning | no | closed for W04; coordinator packet reconciliation required |
| `AUDIT-ERR-W04-030` | W04 completion handoff | n/a | environment/setup issue | no | closed via coordinator handoff |
| `AUDIT-ERR-W04-CHR-R-001` | W04 independent-review parallelization | 1 | environment/setup issue | no | Closed by local review fallback; no repository state changed beyond this audit error record. |
| `AUDIT-ERR-W04-CHR-R-002` | W04 generated-summary navigation | 1 | environment/setup issue | no | Closed after the syntax-correct bounded retry; no review conclusion uses the failed command. |
| `AUDIT-ERR-W04-CHR-R-003` | W04 independent PowerShell semantic review | 0 | informational warning | no | Closed after individual full-file recovery reads; no conclusion relies on clipped text. |
| `AUDIT-ERR-W04-CHR-R-004` | W04 independent PowerShell semantic review | 0 | informational warning | no | Closed after the bounded range recovery; no conclusion relies on clipped text. |
| `AUDIT-ERR-W04-CHR-R-005` | W04 independent PowerShell semantic review | 0 | informational warning | no | Closed after the bounded range recovery; no conclusion relies on clipped text. |
| `AUDIT-ERR-W04-CHR-R-006` | W04 independent Python semantic review | 1 | environment/setup issue | no | Closed by deterministic path discovery before retry. |
| `AUDIT-ERR-W04-CHR-R-007` | W04 pending-recovery finding verification | 0 | informational warning | no | Closed by narrowing search scope before retry. |
| `AUDIT-ERR-W04-CHR-R-008` | W04 pending-recovery finding verification | n/a | sandbox/permission failure | no | Non-blocking; finding confirmation does not depend on this rejected command. |
| `AUDIT-ERR-W04-CHR-R-009` | W04 audit-ledger publication navigation | 1 | environment/setup issue | no | Closed by switching to a platform-safe discovery form before retry. |
| `AUDIT-ERR-W04-CHR-R-010` | W04 finding severity calibration | 1 | expected negative-path result | no | Non-blocking expected negative search. |
| `AUDIT-ERR-W04-CHR-R-011` | W04 first-pass finding reconciliation | n/a | informational warning | no | Closed after exact-row reread and successful bounded retry; no stale patch was forced. |
| `AUDIT-ERR-W04-CHR-R-012` | W04 reconciliation navigation | 0 | informational warning | no | Closed by individual bounded row reads; no edit relies on clipped output. |
| `AUDIT-ERR-W04-CHR-R-013` | W04 rename finding verification | 0 | informational warning | no | Closed by scoped authoritative reads and compact structured deduplication. |
| `AUDIT-ERR-W04-CHR-R-014` | W04 rename finding severity calibration | 1 | environment/setup issue | no | Closed after syntax-correct bounded retry. |
| `AUDIT-ERR-W04-CHR-R-015` | W04 TV logical-collision reproduction | 1 | environment/setup issue | no | Closed after syntax-correct deterministic retry; temporary files were confined to TemporaryDirectory. |
| `AUDIT-ERR-W04-CHR-R-016` | Delegated movie/tv finding deduplication | 0 | informational warning | no | Closed by structured bounded deduplication; exact source and tests were separately read. |
| `AUDIT-ERR-W04-CHR-R-017` | Delegated rename requirement and test discovery | 0 | informational warning | no | Closed for all task-relevant evidence by bounded authoritative reads. |
| `AUDIT-ERR-W04-CHR-R-018` | W04 audit validator navigation | 1 | environment/setup issue | no | Closed after deterministic path discovery and exact-source read. |
| `AUDIT-ERR-W04-CHR-R-019` | W04 independent attestation publication | n/a | environment/setup issue | no | Closed by platform-neutral marker parsing; no partial artifact was written. |
| `AUDIT-ERR-W04-CHR-R-020` | W04 independent attestation publication | 0 | informational warning | no | Closed after complete chunked generation; no conclusion or file content relies on truncated output. |
| `AUDIT-ERR-W04-CHR-R-021` | Final global ledger integration check | 1 | test failure | no | Open only as unrelated global audit-freeze/fragment debt; W04 completion evidence is independently validated and no central file was edited. |
| `AUDIT-ERR-W04-CHR-R-022` | Final global ledger integration check output capture | 1 | informational warning | no | Closed for W04 evidence; global unrelated diagnostics remain coordinator-owned. |
| `AUDIT-ERR-W04-CHR-R-023` | Final W04 evidence-file integrity check | 1 | environment/setup issue | no | Closed after the syntax-correct bounded retry; canonical schema validators also parse all files. |
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
| `AUDIT-ERR-W05-027` | worker-05 candidate semantic review | n/a | environment/setup issue | no | Closed after corrected orchestration started successfully. |
| `AUDIT-ERR-W05-028` | worker-05 candidate semantic review | 0 | informational warning | no | Closed after bounded exact evidence recovery. |
| `AUDIT-ERR-W05-029` | worker-05 candidate semantic review | 0 | informational warning | no | Closed after explicit encoded-command reproduction. |
| `AUDIT-ERR-W05-030` | worker-05 candidate semantic review | 0 | environment/setup issue | no | Closed after switching to noninteractive encoded-command execution. |
| `AUDIT-ERR-W05-031` | worker-05 candidate semantic review | 1 | environment/setup issue | no | Closed after corrected parser/hash check and five passing focused suites. |
| `AUDIT-ERR-W05-032` | worker-05 candidate semantic review | 1 | test failure | no | Closed as an unrelated, previously documented pre-subtitle harness-path failure. |
| `AUDIT-ERR-W05-033` | worker-05 candidate semantic review | 1 | expected negative-path result | no | Closed after current-versus-archived authority reconciliation. |
| `AUDIT-ERR-W06-001` | worker-06 generated-summary provenance | 1 | environment/setup issue | no | Closed after correcting the inspection key. |
| `AUDIT-ERR-W06-002` | worker-06 review-row schema discovery | 1 | environment/setup issue | no | Closed after exact schema-source inspection. |
| `AUDIT-ERR-W06-003` | worker-06 schema provenance discovery | 0 | informational warning | no | Closed after bounded generator and registry checks. |
| `AUDIT-ERR-W06-004` | worker-06 PowerShell event-redaction review | 1 | expected negative-path result | no | Closed after explicit negative-result handling. |
| `AUDIT-ERR-W06-005` | worker-06 exact semantic source review | 0 | informational warning | no | Closed after bounded exact-read retries. |
| `AUDIT-ERR-W06-006` | worker-06 failure-lifecycle guard tracing | 0 | informational warning | no | Closed after compact bounded retry. |
| `AUDIT-ERR-W06-007` | worker-06 Python structured-log redaction reachability | 124 | environment/setup issue | no | Closed after bounded source/test search. |
| `AUDIT-ERR-W06-008` | worker-06 config strict-numeric reachability reproduction | 1 | environment/setup issue | no | Closed after corrected bounded reproduction. |
| `AUDIT-ERR-W06-009` | worker-06 fragment schema validation | 1 | environment/setup issue | no | Closed after signature inspection and corrected invocation. |
| `AUDIT-ERR-W06-010` | worker-06 error-fragment schema validation | 0 | environment/setup issue | no | Closed after normalized ten-record fragment validation. |
| `AUDIT-ERR-W06-011` | worker-06 final behavior-schema exact review | 1 | environment/setup issue | no | Closed after exact path discovery and complete bounded reads. |
| `AUDIT-ERR-W06-012` | worker-06 final row construction and baseline discovery | 0 | informational warning | no | Closed after bounded universe extraction. |
| `AUDIT-ERR-W06-013` | worker-06 final row construction and baseline discovery | 1 | environment/setup issue | no | Closed after corrected universe extraction and hash reconciliation. |
| `AUDIT-ERR-W06-014` | worker-06 complete fragment validation | 0 | environment/setup issue | no | Closed after stable deduplication and complete official-helper validation. |
| `AUDIT-ERR-W06-015` | worker-06-sources-01-independent-schema-consumer-reconciliation | 0 | informational warning | no | No repository or product state changed; the truncated output is discarded and bounded reconciliation remains required. |
| `AUDIT-ERR-W06-016` | worker-06-sources-01-independent-schema-structural-validation | 1 | environment/setup issue | no | No schema conclusion is based on the failed import and no repository or product state changed. |
| `AUDIT-ERR-W07-001` | worker-07-existing-progress-reconciliation | 1 | environment/setup issue | no | Recorded; failed output discarded and corrected recursive search required. |
| `AUDIT-ERR-W07-002` | worker-07-required-navigation | n/a | environment/setup issue | no | Recorded; fallback navigation required before semantic review. |
| `AUDIT-ERR-W07-003` | worker-07-javascript-structural-review | 1 | environment/setup issue | no | Recorded; equivalent read-only AST traversal remains available. |
| `AUDIT-ERR-W07-004` | worker-07-tauri-lifecycle-review | 1 | environment/setup issue | no | Recorded; partial output treated only as a lead pending clean retry. |
| `AUDIT-ERR-W07-005` | worker-07-current-finding-validation | 1 | test failure | no | Current P2 finding confirmed; retain the failing contract output as evidence and continue unrelated coverage. |
| `AUDIT-ERR-W07-006` | worker-07-network-lifecycle-boundary-review | n/a | informational warning | no | Recorded; broad partial output discarded as completeness evidence and replaced by bounded queries. |
| `AUDIT-ERR-W07-007` | worker-07-network-lifecycle-boundary-review | 1 | environment/setup issue | no | Recorded; partial output not credited until the corrected bounded retry succeeded. |
| `AUDIT-ERR-W07-008` | worker-07-network-lifecycle-finding-deduplication | 1 | environment/setup issue | no | Recorded; mixed output treated only as a lead pending clean recursive search. |
| `AUDIT-ERR-W07-009` | worker-07-network-lifecycle-finding-deduplication | 1 | expected negative-path result | no | Recorded for command completeness; no coverage loss. |
| `AUDIT-ERR-W07-010` | worker-07-focused-webview-validation | 1 | test failure | no | Open current command-replay finding; concurrent generated-boundary drift preserved separately without absorbing unrelated dirty changes. |
| `AUDIT-ERR-W08-001` | worker-08-required-navigation | n/a | environment/setup issue | no | Recorded; fallback navigation completed before semantic review. |
| `AUDIT-ERR-W08-002` | worker-08-boundary-orientation | 0 | informational warning | no | Recorded; returned boundary sections retained, truncated tail excluded from completeness claims. |
| `AUDIT-ERR-W08-003` | worker-08-semantic-review | 1 | expected negative-path result | no | Recorded; partial output was not mistaken for a complete ownership lookup. |
| `AUDIT-ERR-W08-004` | worker-08-validation-monitoring | 1 | expected negative-path result | no | Recorded; the test command itself remained active and independent of this census. |
| `AUDIT-ERR-W08-005` | worker-08-validation-monitoring | 1 | expected negative-path result | no | Recorded; this race does not affect validation output or audit coverage. |
| `AUDIT-ERR-W08-006` | worker-08-full-webview-validation | 1 | test failure | no | Recorded; all 283 passing tests remain credited and each non-pass is reconciled before W08 publication. |
| `AUDIT-ERR-W08-007` | worker-08-validation-failure-classification | 1 | test failure | no | Concurrent test drift outside W08 source ownership; preserved as validation error without creating a duplicate W08 product finding. |
| `AUDIT-ERR-W08-008` | worker-08-scoped-ledger-validation | 1 | environment/setup issue | no | Recorded; failed validator result is not credited and corrected retry is required. |
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
| `AUDIT-ERR-W09-028` | post-publication audit verification | 1 | informational warning | no | closed as expected concurrent central-mirror staleness after a previously clean frozen checkpoint |
| `AUDIT-ERR-W09-IR-001` | worker-09-high-risk-independent-review | 1 | test failure | no | closed as an independently reproduced, already tracked formatting defect |
| `AUDIT-ERR-W09-IR-002` | worker-09-high-risk-independent-review | 1 | environment/setup issue | no | closed after a variable-safe in-process policy query |
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
| `AUDIT-ERR-W10-CHM-001` | W10 exact-current metadata/tooling scope derivation | 1 | environment/setup issue | no | Closed for the constant-name error; broader universe correction is logged separately. |
| `AUDIT-ERR-W10-CHM-002` | W10 exact-current metadata/tooling scope derivation | 0 | environment/setup issue | no | Closed by corrected full-baseline scope derivation; the 84-path set is the exact current remainder after concurrent achieved evidence. |
| `AUDIT-ERR-W10-CHM-003` | W10 generated-summary-first navigation | 1 | environment/setup issue | no | Closed after correcting the generated-index extension; no target coverage was lost. |
| `AUDIT-ERR-W10-CHM-004` | W10 exact physical-line review | 0 | informational warning | no | Closed by bounded reread; the truncated output is not used as terminal evidence. |
| `AUDIT-ERR-W10-CHM-005` | W10 current-head metadata/tooling finding reconciliation | 0 | informational warning | no | Closed by bounded structured reread; no path or finding disposition relies on the truncated output. |
| `AUDIT-ERR-W10-CHM-006` | W10 current-head metadata/tooling root-cause reconciliation | 0 | informational warning | no | Closed by bounded focused rereads; clipped content is not treated as complete evidence. |
| `AUDIT-ERR-W10-CHM-007` | W10 GitHub metadata dependency reconciliation | 1 | environment/setup issue | no | Closed by tracked-file enumeration; the ignored scratch failure does not block target review. |
| `AUDIT-ERR-W10-CHM-008` | W10 change-packet schema and evidence reconciliation | 0 | informational warning | no | Closed by bounded structured reruns; clipped details are not used as terminal evidence. |
| `AUDIT-ERR-W10-CHM-009` | W10 current-head metadata/tooling finding reconciliation | 0 | expected negative-path result | no | Closed as a clean deduplication result rather than a coverage failure. |
| `AUDIT-ERR-W10-CHM-010` | W10 WebView tooling false-negative triage | 0 | expected negative-path result | no | Closed with no finding; exact-current semantic coverage remains satisfied. |
| `AUDIT-ERR-W10-CHM-011` | W10 generated-summary-first navigation | 0 | informational warning | no | Closed with direct-source fallback as required by AGENTS.md. |
| `AUDIT-ERR-W10-CHM-012` | W10 complete-packet downstream-impact reconciliation | 0 | expected negative-path result | no | Closed by executable-source selection evidence; generated-output freshness is outside this bounded target set. |
| `AUDIT-ERR-W10-CHM-013` | W10 finding-fragment publication | 1 | environment/setup issue | no | Closed after context-anchored retry; the failed patch made no partial edit. |
| `AUDIT-ERR-W10-CHM-014` | W10 focused syntax validation | 1 | environment/setup issue | no | Closed by corrected harness rerun; the failure is not attributed to any target script. |
| `AUDIT-ERR-W10-CHM-015` | W10 focused tooling validation | 1 | test failure | no | Closed as reproduced pre-existing W12-006 current-worktree drift; exact source review remains complete. |
| `AUDIT-ERR-W10-CHM-016` | W10 focused WebView tooling validation | 1 | test failure | no | Closed as reproduced pre-existing generated/lint drift; target source review and new root-cause findings remain independently validated. |
| `AUDIT-ERR-W10-CHM-017` | W10 strict global 6,499-row validation | 1 | test failure | no | Closed for this bounded slice and handed off as unrelated global merge debt; no W10 target row was among the printed failures. |
| `AUDIT-ERR-W10-CHM-018` | W10 prior-finding location reconciliation | 0 | informational warning | no | Closed by bounded JSON-field verification and restoration of the pre-existing finding's original two workflow locations; unrelated pre-existing rows are preserved. |
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
| `AUDIT-ERR-W10P-001` | scope-census | 1 | environment/setup issue | no | Discarded the failed wildcard invocation; the retry supplied complete census evidence. |
| `AUDIT-ERR-W10P-002` | semantic-line-review | 0 | informational warning | no | No source line remained unread after the targeted retry. |
| `AUDIT-ERR-W10P-003` | semantic-line-review | 0 | informational warning | no | The truncated display was not used as terminal evidence. |
| `AUDIT-ERR-W10P-004` | semantic-line-review | 0 | informational warning | no | All four current hashes received complete semantic review. |
| `AUDIT-ERR-W10P-005` | semantic-line-review | 0 | informational warning | no | No coverage was inferred from omitted output. |
| `AUDIT-ERR-W10P-006` | semantic-line-review | 0 | informational warning | no | The second retry restored complete evidence. |
| `AUDIT-ERR-W10P-007` | semantic-line-review | 0 | informational warning | no | Complete line coverage was achieved. |
| `AUDIT-ERR-W10P-008` | semantic-line-review | 0 | informational warning | no | Complete line coverage was achieved. |
| `AUDIT-ERR-W10P-009` | semantic-line-review | 0 | informational warning | no | Complete line coverage and finding evidence were retained. |
| `AUDIT-ERR-W10P-010` | navigation | 1 | environment/setup issue | no | The nonexistent path was discarded and current placement was reconciled. |
| `AUDIT-ERR-W10P-011` | semantic-line-review | 0 | informational warning | no | No coverage remained blocked. |
| `AUDIT-ERR-W10P-012` | semantic-line-review | 0 | informational warning | no | The focused harness failure was recorded separately; source coverage is complete. |
| `AUDIT-ERR-W10P-013` | semantic-line-review | 0 | informational warning | no | Complete semantic review was retained. |
| `AUDIT-ERR-W10P-014` | semantic-line-review | 0 | informational warning | no | All lines and the canonical-sidecar defect were verified. |
| `AUDIT-ERR-W10P-015` | focused-analysis | 1 | expected negative-path result | no | The negative search was retained as methodology evidence and did not block review. |
| `AUDIT-ERR-W10P-016` | semantic-line-review | 0 | informational warning | no | Complete line coverage was achieved. |
| `AUDIT-ERR-W10P-017` | semantic-line-review | 0 | informational warning | no | Existing path-local findings were joined to the exact-current review. |
| `AUDIT-ERR-W10P-018` | semantic-line-review | 0 | informational warning | no | Complete line coverage was achieved. |
| `AUDIT-ERR-W10P-019` | scope-census | 1 | environment/setup issue | no | Corrected census produced the exact target set. |
| `AUDIT-ERR-W10P-020` | scope-census | 1 | environment/setup issue | no | Corrected census reported 41 high-risk target paths. |
| `AUDIT-ERR-W10P-021` | scope-census | 0 | informational warning | no | Reported only the stable target totals and documented the baseline convention. |
| `AUDIT-ERR-W10P-022` | navigation | 1 | environment/setup issue | no | The corrected search supplied complete rerun matches. |
| `AUDIT-ERR-W10P-023` | focused-analysis | n/a | sandbox/permission failure | no | The safe retry reproduced the product behavior. |
| `AUDIT-ERR-W10P-024` | focused-analysis | 0 | informational warning | no | Only the deterministic thread-assisted reproduction was used as finding evidence. |
| `AUDIT-ERR-W10P-025` | focused-analysis | 0 | environment/setup issue | no | The incomplete fixture output was discarded; the complete fixture confirmed the defect. |
| `AUDIT-ERR-W10P-026` | navigation | 2 | environment/setup issue | no | All six entrypoint fragments were fully read. |
| `AUDIT-ERR-W10P-027` | focused-validation | 1 | test failure | no | Classified as a stale split-unaware harness, not a product defect in these target files; coverage remained complete. |
| `AUDIT-ERR-W10P-028` | focused-validation | 1 | test failure | no | Classified as an incomplete isolated harness; no runtime product defect was inferred and source review remained complete. |
| `AUDIT-ERR-W10P-029` | focused-validation | 1 | test failure | no | The red registry gate remains explicit and does not block exact-current line coverage. |
| `AUDIT-ERR-W10P-030` | fragment-validation | 1 | environment/setup issue | no | Corrected invocation is used for final fragment validation. |
| `AUDIT-ERR-W10P-031` | fragment-validation | 1 | environment/setup issue | no | Subsequent introspection and validation completed successfully. |
| `AUDIT-ERR-W10P-032` | finding-deduplication | 1 | environment/setup issue | no | The corrected search supported deduplication. |
| `AUDIT-ERR-W10P-033` | finding-evidence | 0 | informational warning | no | No finding location or review status relies on omitted display content. |
| `AUDIT-ERR-W10P-034` | scope-census | 1 | expected negative-path result | no | No census evidence depended on the failed search. |
| `AUDIT-ERR-W10P-035` | fragment-validation | 0 | informational warning | no | Only the concise owned-slice result is terminal evidence; the truncated global diagnostic is retained as an error event. |
| `AUDIT-ERR-W10P-036` | fragment-validation | 0 | informational warning | no | These are coordinator/concurrent-fragment issues outside this owned slice; no central ledger or other worker fragment was changed. |
| `AUDIT-ERR-W11-001` | worker-11-tests-tooling finding materialization | 1 | expected negative-path result | no | Closed command-shape/search-result issue; no repository evidence or reviewed source changed. |
| `AUDIT-ERR-W11-002` | worker-11 final-hash first-pass refresh | 1 | environment/setup issue | no | Closed after exact-directory retry; no reviewed source or test file was modified. |
| `AUDIT-ERR-W11-003` | worker-11 final-hash first-pass refresh | 0 | informational warning | no | Closed as display-only truncation after bounded recovery. |
| `AUDIT-ERR-W11-004` | worker-11 final-hash semantic reread | 0 | informational warning | no | Closed as display-only truncation after bounded exact-source recovery. |
| `AUDIT-ERR-W11-005` | worker-11 final-hash validation | 0 | informational warning | no | Retained as non-blocking validation stderr; focused suite passed. |
| `AUDIT-ERR-W11-006` | worker-11 final-hash evidence join | 0 | environment/setup issue | no | Closed after coordinated shared-fragment repair; the failed join supplied no terminal evidence. |
| `AUDIT-ERR-W11-007` | worker-11 prior-finding reconciliation | 0 | informational warning | no | Closed as display-only truncation after bounded recovery. |
| `AUDIT-ERR-W11-008` | worker-11 route-cap finding publication | 1 | environment/setup issue | no | Closed after exact-context retry; the failed patch changed no file. |
| `AUDIT-ERR-W11-009` | worker-11 route-cap finding publication | 1 | environment/setup issue | no | Closed after dedicated-fragment retry; the failed patch changed no file. |
| `AUDIT-ERR-W11-010` | worker-11 code-context finding deduplication | 0 | informational warning | no | Closed as display-only truncation; no conclusion relies on the truncated output. |
| `AUDIT-ERR-W11-011` | worker-11 first-pass semantic source review | 0 | informational warning | no | Closed after bounded retries; the full source is now covered and no conclusion relies on the truncated output. |
| `AUDIT-ERR-W11-012` | worker-11 candidate-finding deduplication | 1 | environment/setup issue | no | Closed after bounded retry; no audit conclusion relies on the failed command. |
| `AUDIT-ERR-W11-013` | worker-11 finding evidence hash capture | 0 | environment/setup issue | no | Closed after clean hash retry; no finding relies on the presentation-failed output. |
| `AUDIT-ERR-W11-CHR-D-001` | W11 exact-current delta review parallelization | 1 | environment/setup issue | no | Closed by local full-review fallback; no repository state changed beyond this audit error record. |
| `AUDIT-ERR-W11-CHR-D-002` | W11 exact-current delta evidence reconciliation | 0 | environment/setup issue | no | Closed by corrected structured query; no review conclusion uses the zero-match output. |
| `AUDIT-ERR-W11-CHR-D-003` | W11 exact-current finding deduplication | 0 | expected negative-path result | no | Closed as expected negative deduplication evidence. |
| `AUDIT-ERR-W11-CHR-D-004` | W11 context-benchmark defect reproduction setup | 1 | environment/setup issue | no | Closed by corrected acceptance reproduction. |
| `AUDIT-ERR-W11-CHR-D-005` | W11 subsystem-inventory defect reproduction | 1 | environment/setup issue | no | Closed by corrected focused test execution. |
| `AUDIT-ERR-W11-CHR-D-006` | W11 archive_completed stale-plan reproduction setup | 1 | environment/setup issue | no | Closed by corrected temporary-root reproductions. |
| `AUDIT-ERR-W11-CHR-D-007` | W11 subsystem-inventory assertion-detector reconciliation | 1 | environment/setup issue | no | Closed by corrected canonical-path assertion census. |
| `AUDIT-ERR-W11-CHR-D-008` | W11 audit error-fragment reconciliation | 1 | environment/setup issue | no | Closed by successful individual apply_patch retries. |
| `AUDIT-ERR-W11-CHR-D-009` | W11 exact-current baseline validation setup | 0 | informational warning | no | Closed after bounded baseline rereads and clean 6,499-row validation. |
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
| `AUDIT-ERR-W11-R-001` | resumed W11 setup | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-002` | scope discovery | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-003` | audit orientation | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-004` | scope inventory | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-005` | prior-audit reconciliation | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-006` | prior-audit reconciliation | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-007` | scope partitioning | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-008` | parallel review setup | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-009` | candidate discovery | 1 | expected negative-path result | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-010` | candidate discovery | 1 | expected negative-path result | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-011` | PowerShell semantic review | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-012` | PowerShell semantic review | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-013` | PowerShell semantic review | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-014` | PowerShell semantic review | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-015` | PowerShell semantic review | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-016` | scope reconciliation | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-017` | tooling semantic review | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-018` | finding deduplication | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-019` | assignment reconciliation | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-020` | candidate finding deduplication | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-021` | contract test candidate verification | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-022` | release finalizer candidate verification | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-023` | summary refresh candidate verification | 1 | expected negative-path result | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-024` | legacy readiness candidate verification | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-025` | legacy readiness test ownership | 1 | expected negative-path result | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-026` | desktop delegate status check | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-027` | change-control candidate triage | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-028` | contract test candidate proof | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-029` | desktop-test prior-evidence discovery | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-030` | desktop-test parallelization | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-031` | desktop finding deduplication | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-032` | desktop structural review | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-033` | desktop structural review | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-034` | desktop validation mapping | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-035` | desktop audit navigation | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-036` | desktop finding deduplication | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-037` | desktop finding deduplication | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-038` | desktop focused validation | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-039` | desktop worktree-isolation review | 1 | environment/setup issue | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-040` | desktop concurrency review | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-041` | desktop final hash reconciliation | 0 | informational warning | no | Closed after bounded recovery; no conclusion relies on the failed or truncated output. |
| `AUDIT-ERR-W11-R-042` | W11 fragment schema validation | 1 | informational warning | no | Closed for scoped W11 validation; central aggregate repair belongs to the W12 artifact owner. |
| `AUDIT-ERR-W11-R-043` | W11 fragment schema validation | 1 | environment/setup issue | no | Closed after correcting the audit record; no review evidence was affected. |
| `AUDIT-ERR-W11-R-044` | W11 current-hash fragment validation | 1 | informational warning | no | Closed for scoped validation after in-memory identity refresh; no central artifact was modified. |
| `AUDIT-ERR-W11-R-045` | W11 scoped syntax and fixture validation | 1 | environment/setup issue | no | Closed after diagnostic retry; all Python compilation and JSON conclusions use the later bounded result. |
| `AUDIT-ERR-W11-R-046` | W11 scoped syntax and fixture validation | 1 | expected negative-path result | no | Closed as a validator-assumption mismatch; the fixture is valid under its documented consumer contract. |
| `AUDIT-ERR-W11-R-047` | W11 PowerShell syntax validation | 1 | expected negative-path result | no | Closed as intentional negative-fixture evidence; no executable PowerShell parse failure remains. |
| `AUDIT-ERR-W11-R-048` | W11 full tooling regression validation | 1 | test failure | no | Open repository findings remain; the nonzero suite is preserved as release evidence and is not reported as a clean gate. |
| `AUDIT-ERR-W11-R-049` | W11 final artifact uniqueness validation | 0 | informational warning | no | Closed after the grouped-ID retry; final uniqueness conclusions use only the corrected result. |
| `AUDIT-ERR-W11-SR-001` | worker-11-independent-second-review-atomicity-probe | 0 | expected negative-path result | no | Evidence-bearing expected failure; it does not block completion of the read-only second review. |
| `AUDIT-ERR-W11-SR-002` | worker-11-independent-second-review-atomicity-proof-gate-probe | 0 | expected negative-path result | no | Evidence-bearing expected failure; it does not block completion of the read-only second review. |
| `AUDIT-ERR-W11-WEB-001` | worker-11-webview-required-navigation | n/a | environment/setup issue | no | Recorded; fallback navigation required before semantic review. |
| `AUDIT-ERR-W11-WEB-002` | worker-11-webview-summary-before-source | 0 | informational warning | no | Recorded and recovered; earlier complete groups remained usable. |
| `AUDIT-ERR-W11-WEB-003` | worker-11-webview-targeted-source-review | 0 | informational warning | no | Recorded and recovered; retry scope was narrowed without rereading accepted small files. |
| `AUDIT-ERR-W11-WEB-004` | worker-11-webview-finding-reconciliation | 1 | environment/setup issue | no | Recorded and recovered; central and worker fragments were reconciled. |
| `AUDIT-ERR-W11-WEB-005` | worker-11-webview-finding-reconciliation | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-006` | worker-11-webview-test-discovery-review | 1 | informational warning | no | Recorded and reconciled to the existing workflow root cause; no duplicate test-path finding. |
| `AUDIT-ERR-W11-WEB-007` | worker-11-webview-test-discovery-review | 0 | informational warning | no | Recorded and recovered; no duplicate finding created. |
| `AUDIT-ERR-W11-WEB-008` | worker-11-webview-embedded-javascript-validation | 1 | environment/setup issue | no | Recorded and recovered; complete UTF-8 retry supersedes the interrupted sweep. |
| `AUDIT-ERR-W11-WEB-009` | worker-11-webview-test-collection-validation | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-010` | worker-11-webview-generated-context-reconciliation | 0 | informational warning | no | Recorded as generated-context drift; review row will preserve stale_unreconciled reconciliation rather than claim hash match. |
| `AUDIT-ERR-W11-WEB-011` | worker-11-webview-focused-execution | 1 | test failure | no | Recorded and isolated; requires generated/docs owner reconciliation. |
| `AUDIT-ERR-W11-WEB-R-001` | required-navigation | n/a | environment/setup issue | no | Recorded and recovered; semantic review proceeded only after the deterministic fallback. |
| `AUDIT-ERR-W11-WEB-R-002` | audit-pack-discovery | 1 | informational warning | no | Recorded and recovered; no conclusion relied on the empty search. |
| `AUDIT-ERR-W11-WEB-R-003` | audit-pack-discovery | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-R-004` | scope-freeze | 0 | informational warning | no | Recorded and recovered; unrelated dirty paths were not absorbed. |
| `AUDIT-ERR-W11-WEB-R-005` | ledger-schema-review | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-R-006` | process-and-assertion-review | 0 | informational warning | no | Recorded and recovered; finding locations come from the complete AST retry. |
| `AUDIT-ERR-W11-WEB-R-007` | artifact-collision-check | 1 | expected negative-path result | no | Accepted as successful negative-path evidence. |
| `AUDIT-ERR-W11-WEB-R-008` | finding-and-generated-context-reconciliation | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-R-009` | isolation-and-mutation-review | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-R-010` | official-browser-validation | 1 | test failure | no | Recorded as time-bound validation evidence; superseded for current counts by R-020. |
| `AUDIT-ERR-W11-WEB-R-011` | focused-browser-reproduction | 1 | test failure | no | Recorded and reproduced. |
| `AUDIT-ERR-W11-WEB-R-012` | focused-direct-node-validation | 1 | test failure | no | Recorded and reconciled to existing product/workflow findings; the reviewed tests correctly fail. |
| `AUDIT-ERR-W11-WEB-R-013` | remaining-nonbrowser-validation | 1 | test failure | no | Recorded and reproduced; failures are outside the tests' assertion implementation. |
| `AUDIT-ERR-W11-WEB-R-014` | exact-hash-freeze | 1 | flaky/non-deterministic | no | Recorded and recovered without overwriting concurrent work. |
| `AUDIT-ERR-W11-WEB-R-015` | ledger-schema-review | 1 | environment/setup issue | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-R-016` | schema-and-prior-error-review | 0 | informational warning | no | Recorded and recovered. |
| `AUDIT-ERR-W11-WEB-R-017` | generated-context-reconciliation | 1 | environment/setup issue | no | Recorded before retry and recovered. |
| `AUDIT-ERR-W11-WEB-R-018` | concurrent-worktree-reconciliation | 0 | flaky/non-deterministic | no | Recorded and recovered; no concurrent source or generated file was modified by this reviewer. |
| `AUDIT-ERR-W11-WEB-R-019` | artifact-collision-check | 1 | environment/setup issue | no | Recorded before retry and recovered. |
| `AUDIT-ERR-W11-WEB-R-020` | official-browser-validation-current | 1 | test failure | no | Recorded as the final current official browser outcome; semantic coverage is not blocked. |
| `AUDIT-ERR-W11-WEB-R-021` | focused-browser-validation-current | 1 | test failure | no | Recorded and isolated. |
| `AUDIT-ERR-W11-WEB-R-022` | parallel-focused-validation | 1 | environment/setup issue | no | Recorded before serial recovery; direct-Node failure evidence remains valid. |
| `AUDIT-ERR-W11-WEB-R-023` | remaining-nonbrowser-validation-current | 1 | test failure | no | Recorded; semantic review concludes the assertions expose current external contract/evidence drift. |
| `AUDIT-ERR-W11-WEB-R-024` | official-ledger-validation | 1 | informational warning | no | Recorded; global coordinator/other-worker cleanup remains outside this handoff, while the W11 scoped fragments are valid. |
| `AUDIT-ERR-W12-001` | W12 progress and ledger-schema discovery | 1 | environment/setup issue | no | Closed after enumerated-path retry; no audit conclusion depends on the failed discovery batch. |
| `AUDIT-ERR-W12-002` | W12 generated-artifact provenance discovery | 0 | informational warning | no | Closed after bounded generator-by-generator retry; no provenance conclusion relies on the clipped tail. |
| `AUDIT-ERR-W12-003` | W12 generated check-mode inventory | 1 | environment/setup issue | no | Closed after canonical-name retry; registry evidence now uses the enumerated suite name. |
| `AUDIT-ERR-W12-004` | W12 generated-artifact check-mode inventory | 1 | environment/setup issue | no | Closed after path-corrected bounded retry; source mapping now uses existing files only. |
| `AUDIT-ERR-W12-005` | W12 generated-artifact freshness validation | 1 | confirmed repository defect | no | Finding-backed smoke-map drift remains open for remediation; the parallel result-suppression limitation is closed. |
| `AUDIT-ERR-W12-006` | W12 generated-summary freshness validation | 1 | confirmed repository defect | no | Open generated drift; remediation deferred until coordinator writer freeze. |
| `AUDIT-ERR-W12-007` | W12 project-index freshness validation | 1 | confirmed repository defect | no | Open generated drift; affected rows must link the existing coordinator finding. |
| `AUDIT-ERR-W12-008` | W12 feature-navigation freshness validation | 1 | confirmed repository defect | no | Open generated drift pending settled-worktree regeneration. |
| `AUDIT-ERR-W12-009` | W12 generated test-report freshness validation | 1 | confirmed repository defect | no | Open generated drift pending canonical regeneration. |
| `AUDIT-ERR-W12-010` | W12 generated-artifact freshness validation | 0 | informational warning | no | Closed after bounded-output recovery; no conclusion depends on the clipped unified diff. |
| `AUDIT-ERR-W12-011` | W12 lint-budget finding deduplication | 1 | expected negative-path result | no | Closed after structured duplicate check. |
| `AUDIT-ERR-W12-012` | W12 WebView generated-artifact freshness validation | 1 | test failure | no | Finding-backed lint drift remains open for remediation; downstream check coverage is complete. |
| `AUDIT-ERR-W12-013` | W12 lint-budget finding deduplication | 1 | environment/setup issue | no | Closed after escape-safe retry; no repository state changed. |
| `AUDIT-ERR-W12-014` | W12 lint-budget evidence localization | 1 | expected negative-path result | no | Closed after structured absence confirmation. |
| `AUDIT-ERR-W12-015` | W12 lint-budget evidence localization | 0 | informational warning | no | Closed after schema-correct structured retry; invalid zero counts were discarded. |
| `AUDIT-ERR-W12-016` | W12 isolated WebView generated checks | 1 | confirmed repository defect | no | Open generated drift; remediation must review current public-export intent before regeneration. |
| `AUDIT-ERR-W12-017` | W12 isolated WebView generated checks | 1 | confirmed repository defect | no | Open generated drift; remediation must confirm intended owners before regeneration. |
| `AUDIT-ERR-W12-018` | W12 isolated WebView generated checks | 1 | confirmed repository defect | no | Open generated drift and linked ownership mismatch pending source-intent review. |
| `AUDIT-ERR-W12-019` | W12 isolated WebView generated checks | 1 | confirmed repository defect | no | Open generated drift; remediation must review consumer changes before regeneration. |
| `AUDIT-ERR-W12-020` | W12 dependency-atlas reproducibility validation | 1 | environment/setup issue | no | Closed after successful disposable-directory reproduction; substantive drift is recorded in AUDIT-FIND-W12-008. |
| `AUDIT-ERR-W12-021` | W12 generated-finding evidence metadata | 1 | environment/setup issue | no | Closed after syntax-correct retry. |
| `AUDIT-ERR-W12-022` | W12 generated-finding evidence metadata | 0 | informational warning | no | Closed after lossless JSON retry; abbreviated table output was discarded. |
| `AUDIT-ERR-W12-023` | W12 standalone-artifact provenance discovery | 0 | informational warning | no | Closed after bounded provenance recovery; no conclusion depends on the clipped output. |
| `AUDIT-ERR-W12-024` | W12 standalone-artifact metadata inventory | 1 | missing external fixture | no | Closed through dependency-free metadata and visual fallback; Pillow was not required. |
| `AUDIT-ERR-W12-025` | W12 archive-candidate-scan provenance refresh | 1 | environment/setup issue | no | Closed after enumerated-path retry. |
| `AUDIT-ERR-W12-026` | W12 error-ledger incident recording | 1 | environment/setup issue | no | Closed after exact-context retry; no audit evidence was affected. |
| `AUDIT-ERR-W12-027` | W12 current-HEAD deletion reconciliation | 1 | environment/setup issue | no | Closed after tracked-inventory retry; reconciliation evidence covers all removed paths. |
| `AUDIT-ERR-W12-028` | W12 current-HEAD generated addendum | 1 | confirmed repository defect | no | Finding-backed current summary drift remains open; addendum materialization and validation are complete. |
| `AUDIT-ERR-W12-ACTIVE-001` | scope discovery | 0 | informational warning | no | Closed after bounded retries; no conclusion relies on clipped output. |
| `AUDIT-ERR-W12-ACTIVE-002` | exact-current scope reconciliation | 0 | informational warning | no | Closed; the final manifest is generated from the exact live filter rather than the clipped dump. |
| `AUDIT-ERR-W12-ACTIVE-003` | active-document reference validation | 1 | confirmed repository defect | no | Confirmed and joined to the affected active document; no product or evidence bytes were changed. |
| `AUDIT-ERR-W12-ACTIVE-004` | generated-summary freshness validation | 1 | confirmed repository defect | no | Known current generated drift; recorded without regenerating concurrent outputs. |
| `AUDIT-ERR-W12-ACTIVE-005` | configuration/generated-artifact validation | 1 | confirmed repository defect | no | Known generated drift; does not block the exact current semantic review. |
| `AUDIT-ERR-W12-ACTIVE-006` | architecture-document claim reconciliation | 1 | confirmed repository defect | no | Existing current finding; no architecture allowlist or product source was edited. |
| `AUDIT-ERR-W12-ACTIVE-007` | structured configuration inspection | 1 | environment/setup issue | no | Closed methodology error; no repository file was changed by the failed probe. |
| `AUDIT-ERR-W12-ACTIVE-008` | bundle-overview ownership verification | 1 | environment/setup issue | no | Closed after corrected bounded search. |
| `AUDIT-ERR-W12-ACTIVE-009` | bundle-overview ownership verification | 1 | expected negative-path result | no | Expected negative evidence retained and closed. |
| `AUDIT-ERR-W12-ACTIVE-010` | active-document semantic review | 0 | informational warning | no | Closed after bounded and canonical-verifier fallbacks. |
| `AUDIT-ERR-W12-ACTIVE-011` | active-document link validation | 0 | informational warning | no | Corrected methodology; only the refined result supports findings. |
| `AUDIT-ERR-W12-ACTIVE-012` | PROJECT_INDEX reconciliation | 1 | environment/setup issue | no | Closed after API-shape correction; no repository state changed. |
| `AUDIT-ERR-W12-ACTIVE-013` | generated-summary provenance verification | 0 | informational warning | no | Corrected methodology; final provenance claims use the actual schema. |
| `AUDIT-ERR-W12-ACTIVE-014` | final evidence collection | 1 | environment/setup issue | no | Closed after isolated retries. |
| `AUDIT-ERR-W12-ACTIVE-015` | concurrent coverage reconciliation | 0 | informational warning | no | Expected concurrent audit progression handled by exact-current filtering. |
| `AUDIT-ERR-W12-ACTIVE-016` | review-fragment generation | 1 | environment/setup issue | no | W12 output completed; shared-ledger strict merge remains coordinator-owned until those unrelated records are corrected. |
| `AUDIT-ERR-W12-ACTIVE-017` | shared-ledger compatibility validation | 0 | informational warning | no | W12 coverage is complete; aggregate blockers are explicitly separated for coordinator reconciliation. |
| `AUDIT-ERR-W12-ARCHIVE-001` | archive-slice discovery | 0 | informational warning | no | Resolved by bounded reads; no archive path or byte evidence was lost. |
| `AUDIT-ERR-W12-ARCHIVE-002` | archive active-reference reconciliation | 0 | informational warning | no | Resolved; the bounded scan covered all tracked text candidates and produced complete aggregates. |
| `AUDIT-ERR-W12-ARCHIVE-003` | archive provenance and authority context inspection | 1 | environment/setup issue | no | Corrected command construction; packet parsing later covered every JSON packet with zero parse errors. |
| `AUDIT-ERR-W12-ARCHIVE-004` | archive provenance and authority context inspection | 0 | informational warning | no | Resolved; exact packet-to-path coverage was computed without relying on truncated text. |
| `AUDIT-ERR-W12-ARCHIVE-005` | archive authority-context review | 0 | informational warning | no | Resolved; every active reference source was classified as archive index, historical redirect, preserved evidence, or change provenance. |
| `AUDIT-ERR-W12-ARCHIVE-006` | archive/reference validation setup | 2 | environment/setup issue | no | Corrected to the canonical module entry point. |
| `AUDIT-ERR-W12-ARCHIVE-007` | archive/reference validation | 1 | confirmed repository defect | no | Reported to the coordinator for active-document ownership; outside this historical-archive slice and does not invalidate archive byte/provenance evidence. |
| `AUDIT-ERR-W12-ARCHIVE-008` | active-doc gate finding reconciliation | 1 | environment/setup issue | no | Corrected command construction. |
| `AUDIT-ERR-W12-ARCHIVE-009` | active-doc gate finding reconciliation | 1 | expected negative-path result | no | Expected no-match evidence retained; no duplicate finding ID was invented inside the archive slice. |
| `AUDIT-ERR-W12-ARCHIVE-010` | archive review-fragment construction | 0 | environment/setup issue | no | Corrected before merge; no malformed row remains. |
| `AUDIT-ERR-W12-ARCHIVE-011` | archive review-fragment validation | 1 | environment/setup issue | no | Resolved; the current fragment parses completely. |
| `AUDIT-ERR-W12-ARCHIVE-012` | archive review-fragment ownership reconciliation | 0 | environment/setup issue | no | Corrected before merge; current ownership has no overlap and no uncovered archive path. |
| `AUDIT-ERR-W12-INDEP-001` | generated-provenance validation | 1 | confirmed repository defect | no | retained as validation evidence |
| `AUDIT-ERR-W12-INDEP-002` | active-document validation | 1 | confirmed repository defect | no | reported to coordinator |
| `AUDIT-ERR-W12-INDEP-003` | first-review join validation | 1 | confirmed repository defect | no | coordinator reconciliation required Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W12-INDEP-004` | finding-disposition join validation | 1 | confirmed repository defect | no | coordinator reconciliation required Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W12-INDEP-005` | evidence discovery | 1 | environment/setup issue | no | recovered |
| `AUDIT-ERR-W12-INDEP-006` | current-owner reconciliation | 0 | environment/setup issue | no | recovered |
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
| `AUDIT-ERR-W14-008` | worker-14-route-command-map | 1 | informational warning | no | handled with isolated provisional delta; terminal coverage remains blocked for the two concurrently changed routes Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W14-009` | worker-14-route-command-map | 1 | informational warning | no | closed by smaller-chunk retry; no partial artifact existed |
| `AUDIT-ERR-W14-010` | worker-14-artifact-validation | 1 | informational warning | no | closed after corrected validation |
| `AUDIT-ERR-W14-011` | worker-14-finding-reproduction | 1 | informational warning | no | closed after corrected validation |
| `AUDIT-ERR-W14-012` | worker-14-prior-audit-reconciliation | 1 | expected negative-path result | no | closed; findings treated as newly observed in this audit |
| `AUDIT-ERR-W14-013` | worker-14-focused-validation | 1 | test failure | no | open in concurrent feature work; preserved as validation evidence Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
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
| `AUDIT-ERR-W15-013` | worker-15-registry-validation | 1 | test failure | no | Open repository defect; registry completeness cannot be reported green. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W15-014` | worker-15-validation-orchestration | 1 | environment/setup issue | no | Registry failure retained separately; sibling evidence recovered. |
| `AUDIT-ERR-W15-015` | worker-15-targeted-python-validation | 1 | test failure | no | Open deterministic cross-language recovery defect; all other selected tests passed. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
| `AUDIT-ERR-W15-016` | worker-15-repair-drain-reproduction | 1 | test failure | no | Root cause confirmed; no product changes made by this worker. Audit-completion disposition: closed as a repository-review coverage blocker after exact-current first-pass and independent high-risk/P0/P1 evidence; the underlying product remediation, external-evidence gap, or validation limitation remains retained by this record and its linked findings and was not remediated by the audit. |
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
