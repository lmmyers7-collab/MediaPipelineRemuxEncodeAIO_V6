# Worker 14 — Local API Route and Command Map

## Outcome

The initial coherent Local API baseline is fully joined: **172 active routes (55 GET, 117 POST)** map one-to-one across the route contract, GET/POST handler registries, command registry, POST payload-model registry, journal policy, service/facade ownership, tests, and the three central inventories in effect at capture time.

Two high-confidence defects are recorded:

- `AUDIT-FIND-W14-001` (P2): the rename workbench posts backend-generated regression-case fields that the route's `extra=forbid` Pydantic model rejects.
- `AUDIT-FIND-W14-002` (P3): API inventory section headings say 116 POST routes and 18 process commands, while their tables contain 117 and 19 respectively.

Concurrent work added `GET /api/queue/priority-export` and `POST /api/queue/priority-export` after the baseline. They are included as two **provisional live-delta rows** with `terminal_review=false` and `unresolved_join.status=blocked_by_concurrent_change`; they are not represented as terminally audited.

## Artifacts

- `worker-14-route-command-map.jsonl`: 174 unique rows — 172 stable baseline rows plus two provisional delta rows.
- `worker-14-route-command-findings.jsonl`: two confirmed findings.
- `worker-14-route-command-errors.jsonl`: complete worker command-error/warning ledger.
- This file: method, coverage, interpretation, and validation summary.

No product source, central inventory, generated map, test, or release/change-packet file was edited by this worker.

## Method

The production-audit skill drove an evidence-first join focused on authentication, request/data integrity, idempotency/duplicate-command controls, durable journaling, mutation ownership, and operational evidence. Discovery followed generated summaries before retained source reads. The resulting row for each route links executable contracts and registries to handler/source location, request model, confirmation policy, service owner, state effects, journal semantics, frontend owner, test evidence, and inventory rows.

The initial coherent snapshot was captured on **2026-07-20; exact time not emitted**:

| Surface | SHA-256 |
| --- | --- |
| `src/mediapipeline/contracts/api_routes_read.py` | `39f630efd10fb73b09d714f316483a500d2d9d882b30420d9a4ac6abcabb19ed` |
| `src/mediapipeline/contracts/api_commands.py` | `112123de0a4a909c623163d31c606fd73f352409ccd9329b6a1eac9c44033c12` |
| `src/mediapipeline/core/api/commands.py` | `9598d6c31d663ed7121adbf2023d0e913c4b042760b422eddc801fd6f05a2f87` |
| `src/mediapipeline/desktop/api/routes_read.py` | `6cb30ef76e7ba0a5d6ccf5e7a0649692dd38424f29ac2bbe9e584fe438b4ddfe` |
| `docs/inventories/API_ROUTE_INVENTORY.md` | `f9766f99a08dd3be8cbd07790325d6b70b2f633f47db1826f46e1baad21d52d7` |
| `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` | `d9a60a740daf8db8640916acf3d5c0637edc8e2c32fb51722fb4a4c544336126` |
| `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | `93bdeb058055bf4d2e9a793965ba0cc5e4dba3348d985f9f480595f99de9c8ec` |

At that capture:

- Route contract = GET handlers plus explicit `/api/health` plus POST handlers: 172 exact keys.
- POST contract = `COMMAND_ROUTE_METHODS` = `POST_ROUTE_HANDLERS`: 117 exact keys.
- Every POST route had a payload model.
- API route inventory and ownership map joined all 172 routes; command ownership joined all 117 POST routes.
- 23 POST routes used strict durable accepted-before-mutation / terminal-after-mutation evidence.

## Provisional Concurrent Delta

Matching packet: `ops/release/changes/unreleased/MP-CHANGE-2026-0720-027.json` (“Priority-only queue export and Run Once”), observed in planned/dirty concurrent work.

A final 20-second freeze produced identical hashes for route contracts, command/payload registries, handler registries, the three central inventories, and the matching packet. The live executable route set was therefore 174 (56 GET, 118 POST), but the documentation join was still incomplete:

- `COMMAND_OWNERSHIP_MATRIX.md` included the new POST route.
- `API_ROUTE_INVENTORY.md`, `LOCAL_API_ROUTE_OWNERSHIP_MAP.md`, and `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` still omitted both new routes.
- The command matrix described a “strict empty payload,” while the mapped `EmptyCommandPayload` inherited `extra=allow`.

Those facts are preserved in the provisional rows and error ledger. No defect disposition was assigned to the in-flight feature.

## Join Completeness

| Population | Rows | Unique | Unresolved |
| --- | ---: | ---: | ---: |
| Stable initial snapshot | 172 | 172 | 0 |
| Stable GET | 55 | 55 | 0 |
| Stable POST | 117 | 117 | 0 |
| Provisional live delta | 2 | 2 | 2 |
| Total map | 174 | 174 | 2 |

Set validation confirmed:

- Stable rows exactly equal the current contract minus the two priority-export routes.
- Provisional rows exactly equal `GET/POST /api/queue/priority-export`.
- Current route contract and handler registries are equal at 174 keys.
- Every row contains the required machine-readable top-level fields.

## Row Data Dictionary

| Field | Meaning |
| --- | --- |
| `method`, `route`, `route_key`, `active` | Canonical route identity and active status |
| `snapshot_status`, `terminal_review` | Stable baseline versus concurrent provisional state |
| `route_contract`, `request_contract`, `confirmation_fields`, `validation` | Wire contract, Pydantic field join, strict confirmations, and HTTP/JSON boundary |
| `auth` | Loopback token/cookie, host, and origin enforcement |
| `handler`, `service_domain_owner` | Registry dispatch, exact implementation location, direct calls, facade/domain/frontend ownership |
| `state_reads`, `state_writes`, `powershell_process_filesystem_action` | Data authority and mutation/process/filesystem implications |
| `journal_evidence` | Default, strict-durable, secret/no-journal, validation-failure, and exception evidence behavior |
| `tests`, `inventory_join`, `evidence` | Test references and hashed source/inventory joins |
| `source_disagreements`, `unresolved_join` | Explicit drift, compatibility differences, or blocked joins |

## Request-Contract Reconciliation

Among 117 stable POST routes:

- 92 had exact contract-key/model-field sets.
- 25 had at least one contract/model field-set difference.
- 24 had model-only additive/compatibility fields.
- Six had contract-only fields:
  - `/api/completed/open`
  - `/api/queue/open`
  - `/api/rename/filter-cases`
  - `/api/rename/preview`
  - `/api/sample-validation/append`
  - `/api/sample-validation/preview`

Five of those six use additive `extra=allow` models. `/api/rename/filter-cases` alone combines advertised/backend-emitted fields with `extra=forbid`, producing confirmed finding `AUDIT-FIND-W14-001`.

## Handler, Auth, Validation, and Journal Architecture

- `GET /api/health` is the only public API route. Other routes require loopback token/cookie authorization and host validation; POST/OPTIONS also validate origin.
- POST accepts only `application/json`, a declared body no larger than 1,000,000 bytes, strict UTF-8 JSON with an object root, no duplicate keys, and no non-finite numbers.
- The route-specific Pydantic model validates before handler dispatch.
- Successful ordinary command results are written to the bounded command journal. Validation failures and exceptions are journaled unless route metadata explicitly suppresses secret/no-journal evidence.
- Strict-durable routes persist accepted evidence before mutation and terminal evidence afterward; pre-write failure returns unavailable and post-write failure is marked indeterminate.
- Journal JSON is atomically replaced, bounded, and sensitive-key redacted; the SQLite mirror is best-effort.
- GET routes do not create command-journal entries.

## Confirmed Findings

### AUDIT-FIND-W14-001 — P2

The rename filename-preview backend emits a case payload containing `kind`, `template_preset`, and movie/TV-specific expected fields. The WebView posts that payload to `/api/rename/filter-cases`. The route contract advertises six such fields that `RenameFilterCaseCommandPayload` does not declare, and its `extra=forbid` policy rejects all six before dispatch. Direct current-tree validation reproduced `extra_forbidden` for every missing advertised field.

Recommended direction: make one shared request schema authoritative for route documentation, preview output, and HTTP payload validation, then add an exact preview-to-save HTTP round-trip test.

### AUDIT-FIND-W14-002 — P3

`API_ROUTE_INVENTORY.md` has 172 unique table rows (55 GET, 117 POST) and 19 Process Commands rows, but its section headings state 116 POST and 18 Process Commands. Correct the headings and add deterministic heading/table parity validation.

## Validation

- Focused contract/handler/journal suite: **89 passed, 763 subtests passed**.
  - `test_api_handler_policy.py`
  - `test_api_command_results_policy.py`
  - `test_api_command_journal_policy.py`
  - `test_api_command_contracts.py`
  - `test_api_contract_payload.py`
- Exact map/set/schema validation: **passed** — 174 unique rows, 172 stable + two provisional, contract/handler equality, no missing required top-level keys.
- Cross-artifact JSONL/schema/path validation: **passed** — two finding rows, complete error-ledger enums/links, and 1,879 referenced paths/line locations checked.
- Warning-aware artifact `git diff --no-index --check`: **passed** for all four worker files; four expected repository `core.autocrlf` notices were informational.
- Rename strict-model reproduction: **passed as an expected negative-path assertion** — all six missing advertised keys produced `extra_forbidden`.
- Inventory heading/table parser: **passed** — 172 unique rows, 55 GET, 117 POST, 19 process rows.
- `test_api_route_inventory.py`: **8 failed, 3 passed, 39 subtests passed** because the two concurrently added priority-export routes were not yet added to all central inventories/matrices. This is isolated as concurrent feature drift, not assigned as a terminal worker finding.
