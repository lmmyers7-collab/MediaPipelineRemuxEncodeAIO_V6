# Worker Review: W09 - Join, Discovery, Test Connection, Path Mapping, And Library Roots

## Scope

Review-only audit of coordinator join blobs, worker join import, mDNS coordinator discovery, worker test-connection probes, manual/auto source path maps, worker library-relative claim resolution, local IP selection, coordinator share-block helpers, and WebView/Local API read-only boundaries.

Assigned source scope reviewed:

| File | Symbols reviewed | Coverage |
|---|---|---|
| `src/mediapipeline/core/network/join.py` | `encode_network_join_blob`, `decode_network_join_blob`, `worker_join_patch_from_blob` | complete; findings W09-001 and W09-003 |
| `src/mediapipeline/core/network/facade.py` | join blob, join cluster, discover coordinators, test connection, diagnostic layer helpers | complete |
| `src/mediapipeline/desktop/network/mdns.py` | `CoordinatorAdvertiser`, `discover_coordinators`, async callback path | complete |
| `src/mediapipeline/desktop/network/probe.py` | `probe_coordinator_health`, `probe_worker_auth` | complete |
| `src/mediapipeline/desktop/network/local_ip.py` | `get_all_local_ips`, `get_primary_local_ip`, `rfc1918_priority` | complete |
| `src/mediapipeline/desktop/network/share_block.py` | coordinator share-block formatting helpers | complete |
| `src/mediapipeline/desktop/network/path_map.py` | `parse_source_path_map`, `apply_source_path_map` | complete; findings W09-001 and W09-002 |
| `src/mediapipeline/desktop/network/library_roots.py` | library roots, auto maps, claim fields, library-relative resolution | complete |
| `src/mediapipeline/desktop/network/coordinator_url.py` | wrapper over `validate_coordinator_url` | complete |
| `src/mediapipeline/desktop/network/worker.py` | path-map update/merge, auto-map refresh, `resolve_claim_source_path`, runtime descriptor | complete |

Supporting source opened because assigned code delegates there: `src/mediapipeline/core/network/url_policy.py`, `src/mediapipeline/desktop/api/handler.py`, `src/mediapipeline/desktop/api/http_helpers.py`, `src/mediapipeline/desktop/api/contract_command.py`, `src/mediapipeline/contracts/api_commands.py`, `src/mediapipeline/core/api/commands_network.py`, `src/mediapipeline/desktop/network/protocol.py`, `src/mediapipeline/desktop/network/coordinator_http_handlers.py`, `src/mediapipeline/desktop/network/coordinator_queue.py`, and `apps/desktop/webview/static/assets/settingsView.builders.network.js`.

Assigned tests/evidence reviewed:

- `tests/python/desktop/test_network_join.py`
- `tests/python/desktop/test_network_mdns.py`
- `tests/python/desktop/test_network_test_connection.py`
- `tests/python/desktop/test_network_path_auto_map.py`
- `tests/python/desktop/test_network_library_relative_claim.py`
- `tests/python/desktop/test_network_local_ip.py`
- `tests/python/desktop/test_network_drift_descriptor.py`
- `tests/webview/test_webview_network_read_only_boundary.py`

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/CONFIG_KEY_GLOSSARY.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`

Generated summaries were read before full source for all assigned source and test files. Supporting summary read for `src/mediapipeline/desktop/network/protocol.py`. No generated summary exists for supporting `src/mediapipeline/core/network/url_policy.py`; I line-read it because `coordinator_url.py`, join, discovery, and test-connection all delegate URL safety to that helper.

## Coverage Ledger

| Area | Evidence | Result |
|---|---|---|
| Join blob versioning and token handling | `join.py:19-22`, `join.py:92-137`, `facade.py:1268-1365`, `handler.py:145-151`, `test_network_join.py:81-119`, `test_network_join.py:220-296` | Versioned, base64url JSON encoded, confirmation-gated, token value omitted from normal result payload, and unjournaled through Local API. Finding W09-003 for missing semantic bounds. |
| Worker join import settings boundary | `join.py:140-175`, `facade.py:1367-1498`, `test_network_join.py:120-201`, `test_network_join.py:203-218` | Writes only `NetworkRole`, `WorkerCoordinatorUrl`, `WorkerAuthToken`, and optional `WorkerSourcePathMap` through `save_settings_patch(confirm_save=True)`, then runs read-only test connection. Finding W09-001 for order loss while serializing merged maps. |
| Discovery normalization/dedupe | `mdns.py:184-235`, `facade.py:1074-1102`, `facade.py:1500-1605`, `url_policy.py:53-93`, `test_network_mdns.py:309-396` | Reviewed: no findings. mDNS rows are normalized through coordinator URL validation, malformed URLs are warnings, duplicates are removed, and discovery is unjournaled/read-only. |
| Test connection L1/L2/L3 layering | `facade.py:760-825`, `facade.py:845-935`, `facade.py:1607-1677`, `probe.py:32-54`, `test_network_test_connection.py:86-277` | Reviewed: no findings. TCP, signed auth ping, and path-access failures are distinct; L3 uses directory stat/readability checks only and reports no media/queue/lifecycle changes. |
| Manual and auto path maps | `path_map.py:18-59`, `library_roots.py:121-144`, `library_roots.py:199-222`, `worker.py:297-360`, `test_network_path_auto_map.py:96-147`, `test_network_worker_runtime.py:131-152` | Manual maps win over auto maps in memory and prefix matching is case-insensitive with boundary checks. Findings W09-001 and W09-002 for persisted order loss and missing backend path normalization/rejection. |
| Library-relative claims | `library_roots.py:29-44`, `library_roots.py:147-196`, `worker.py:379-388`, `protocol.py:104-165`, `coordinator_http_handlers.py:143-160`, `coordinator_http_handlers.py:248-259`, `test_network_library_relative_claim.py:30-203` | Reviewed: no findings. Additive `library_id`/`relative_path` fields are backward-compatible, coordinator derives fields from source roots, worker prefers library-relative resolution, and absolute/parent relative paths are rejected before fallback. |
| Local IP/share-block helpers | `local_ip.py:15-71`, `share_block.py:7-40`, `test_network_local_ip.py:15-65`, `test_network_coordinator_helpers.py:89-104` | Reviewed: no findings. Local IP ranking prefers 192.168/172/10 RFC1918 order; share block intentionally formats an operator-copy token and is not part of the unjournaled join routes. |
| WebView/contract boundary | `contract_command.py:710-764`, `api_commands.py:242-260`, `test_webview_network_read_only_boundary.py:116-214`, `test_webview_network_read_only_boundary.py:306-454` | Reviewed: no findings. Network setup/test/discovery contracts are backend-owned, join routes require confirmation, secret routes are unjournaled, future controls remain disabled, and auth-token setting keys are not rendered. |

Validation/evidence commands:

| Command | Result |
|---|---|
| `$env:PYTHONPATH='src'; .\apps\desktop\runtime\Python\python.exe -m pytest tests\python\desktop\test_network_join.py tests\python\desktop\test_network_mdns.py tests\python\desktop\test_network_test_connection.py tests\python\desktop\test_network_path_auto_map.py tests\python\desktop\test_network_library_relative_claim.py tests\python\desktop\test_network_local_ip.py tests\python\desktop\test_network_drift_descriptor.py tests\webview\test_webview_network_read_only_boundary.py` | 52 passed in 6.49s. |
| In-process `worker_join_patch_from_blob` check with manual map `\\SERVER\Media\Shows -> D:\Shows` before `\\SERVER\Media -> E:\Media` | Confirmed saved JSON sorted the shorter prefix first and `apply_source_path_map("\\SERVER\Media\Shows\Example\S01.mkv")` resolved to `E:\Media\Shows\Example\S01.mkv`. |
| In-process `apply_source_path_map` check with relative target and parent tail | Confirmed outputs `..\WorkerTV\Show\S01.mkv` and `\\WORKER\TV\..\Other\Escape.mkv`. |

## Findings

| id | severity | file | line / symbol | problem |
|---|---|---|---|---|
| W09-001 | P2 | `src/mediapipeline/core/network/join.py` | `worker_join_patch_from_blob`, `sort_keys=True` at lines 156-161 | Worker join import can reorder existing manual `WorkerSourcePathMap` prefixes even though first-match order is semantically significant. |
| W09-002 | P2 | `src/mediapipeline/desktop/network/path_map.py` | `parse_source_path_map`, `apply_source_path_map`, lines 31-59 | Legacy/manual path-map resolution accepts relative targets and preserves `..` traversal segments in mapped paths. |
| W09-003 | P3 | `src/mediapipeline/core/network/join.py` | `decode_network_join_blob`, `_safe_library_rows`, lines 39-89 | Join blobs are versioned but not semantically bounded by decoded library count or per-field length. |

## Detailed Findings

### W09-001

- `id`: W09-001
- `severity`: P2
- `file`: `src/mediapipeline/core/network/join.py`; supporting `src/mediapipeline/desktop/network/path_map.py`
- `line`: `join.py:156-161`, `path_map.py:31-45`, `path_map.py:54-58`, `tests/python/desktop/test_network_worker_runtime.py:131-152`
- `symbol`: `worker_join_patch_from_blob`, `parse_source_path_map`, `apply_source_path_map`
- `problem`: Join import preserves manual precedence while building `effective_mappings`, but then serializes that ordered list through a dict with `json.dumps(..., sort_keys=True)`. `WorkerSourcePathMap` order matters because `apply_source_path_map()` returns the first matching prefix. If an existing manual map intentionally puts a deeper prefix before a broader prefix, importing a join blob can rewrite the saved JSON so the broader prefix matches first.
- `impact`: A worker can start resolving coordinator source paths to the wrong local/UNC root after an otherwise successful join. This is most likely with overlapping roots such as `\\SERVER\Media\Shows` and `\\SERVER\Media`, and it can send a claimed single-file job to the wrong worker-visible location without touching source media directly.
- `evidence`: `parse_source_path_map()` appends mappings in JSON object order (`path_map.py:31-45`) and `apply_source_path_map()` stops at the first prefix match (`path_map.py:54-58`). Existing tests pin that order-sensitive behavior (`test_network_worker_runtime.py:131-152`). `worker_join_patch_from_blob()` writes the merged map using `sort_keys=True` (`join.py:156-161`). A direct helper check produced saved JSON with `\\SERVER\Media` before `\\SERVER\Media\Shows`, and the sample `\\SERVER\Media\Shows\Example\S01.mkv` resolved to `E:\Media\Shows\Example\S01.mkv` instead of `D:\Shows\Example\S01.mkv`.
- `suggested fix direction`: Preserve mapping order when serializing `WorkerSourcePathMap` from join import. Remove `sort_keys=True` for this order-sensitive setting, or serialize an ordered object from the merged list. Consider sorting auto-derived mappings by descending normalized prefix length before appending them, while keeping all manual rows in original order.
- `suggested validation/tests`: Add a `test_network_join.py` case where an existing manual map has overlapping prefixes and a join import occurs; assert the saved `WorkerSourcePathMap` keeps the deeper manual prefix before the broader prefix and that `apply_source_path_map()` still resolves to the intended target.

### W09-002

- `id`: W09-002
- `severity`: P2
- `file`: `src/mediapipeline/desktop/network/path_map.py`; supporting `src/mediapipeline/desktop/network/worker.py`, `src/mediapipeline/desktop/network/library_roots.py`
- `line`: `path_map.py:31-59`, `worker.py:379-388`, `library_roots.py:29-36`
- `symbol`: `parse_source_path_map`, `apply_source_path_map`, `WorkerDispatcher.resolve_claim_source_path`
- `problem`: The library-relative path path is hardened, but the legacy/manual path-map fallback accepts any non-empty string pair and concatenates the unmatched tail without rejecting relative targets, drive-relative targets, or parent traversal segments in the claimed `source_path` tail. If library-relative fields are absent or rejected, `resolve_claim_source_path()` falls back to this path-map behavior.
- `impact`: A malformed `WorkerSourcePathMap` or malformed legacy coordinator `source_path` can resolve outside the intended worker source root. In network mode that can make a worker process a wrong local path or fail in a confusing way. This does not by itself mutate source media, but it weakens the worker source identity boundary the library-relative claim work is meant to establish.
- `evidence`: `_safe_relative_path()` rejects absolute and `..` relative paths for library-relative claims (`library_roots.py:29-36`), and `resolve_claim_source_path()` only uses that path first when available (`worker.py:379-388`). The fallback parser only replaces separators and strips trailing slashes before accepting non-empty prefix/replacement strings (`path_map.py:31-45`). The mapper then returns `replacement + tail` (`path_map.py:54-58`). A direct helper check resolved a relative target to `..\WorkerTV\Show\S01.mkv` and preserved a parent tail as `\\WORKER\TV\..\Other\Escape.mkv`.
- `suggested fix direction`: Normalize and validate manual map entries in backend code, not only in the WebView row editor. Reject relative and drive-relative replacements, reject prefixes or replacements with `..` segments, and normalize incoming mapped paths with an `ntpath` helper that proves the final result stays under the replacement root before returning it. If a legacy claim contains unsafe traversal, release the claim as unstartable with a bounded reason rather than processing it.
- `suggested validation/tests`: Add `path_map.py` tests for relative replacement, drive-relative replacement, parent segments in source prefix/replacement/tail, UNC case behavior, and exact prefix-boundary behavior. Add a worker loop test proving unsafe mapped claims are released unstartable and do not reach `_worker_start_single_file`.

### W09-003

- `id`: W09-003
- `severity`: P3
- `file`: `src/mediapipeline/core/network/join.py`; supporting `src/mediapipeline/desktop/api/http_helpers.py`, `src/mediapipeline/contracts/api_commands.py`
- `line`: `join.py:39-89`, `join.py:124-137`, `join.py:147-161`, `http_helpers.py:212-244`, `api_commands.py:257-260`
- `symbol`: `_decode_base64url_json`, `_safe_library_rows`, `worker_join_patch_from_blob`, `NetworkWorkerJoinClusterCommandPayload`
- `problem`: Local API request bodies are capped at 1 MB, but the join blob helper itself has no decoded blob length, library count, or per-field length limits. The command payload type accepts `join_blob: Any`, `_decode_base64url_json()` decodes the whole value, `_safe_library_rows()` copies all valid-looking library rows, and `worker_join_patch_from_blob()` can turn all matching rows into a persisted `WorkerSourcePathMap`.
- `impact`: This is not an unauthenticated remote memory issue because the Local API requires a token, body size is capped, and worker import requires `confirm_import=true`. It is still a setup-hardening gap: a pasted malicious or corrupted blob can produce an oversized result, a large settings patch, or noisy UI/state evidence instead of failing with a clear bounded-input error.
- `evidence`: `read_json_body()` caps Local API JSON bodies at 1,000,000 bytes (`http_helpers.py:212-244`). Inside the join helper, `_decode_base64url_json()` has no blob-length check (`join.py:75-89`), `_safe_library_rows()` only de-dupes by library ID and does not cap row count or field length (`join.py:39-62`), and `worker_join_patch_from_blob()` serializes all effective mappings when any exist (`join.py:147-161`). `NetworkWorkerJoinClusterCommandPayload` keeps `join_blob` as `Any` with no schema-level length constraint (`api_commands.py:257-260`).
- `suggested fix direction`: Define conservative semantic caps, for example maximum encoded blob length below the API body cap, maximum decoded JSON bytes, maximum library rows, and maximum field lengths for library ID/name/designation/source/output roots. Reject over-limit blobs before settings save. Keep error messages redacted and do not echo blob content.
- `suggested validation/tests`: Add join helper and Local API route tests for overlong blob text, too many libraries, very long library IDs/source roots, non-object/NaN JSON constants, and verify no token/blob material reaches command history or error strings.

## Test Coverage Gaps

| Gap | Risk | Suggested coverage |
|---|---|---|
| No test covers join import preserving existing manual path-map order with overlapping prefixes. | Import can silently alter first-match path semantics. | Add `test_network_join.py` order-preservation regression and assert post-import `apply_source_path_map()` behavior. |
| No backend test rejects relative/manual path-map escapes or `..` tails in legacy claims. | Worker may resolve outside intended source root when library-relative fields are absent or invalid. | Add direct `path_map.py` tests plus worker-loop unstartable-claim tests. |
| Join blob tests do not cover decoded-size, row-count, or field-length caps. | Malformed setup blobs fail late or create oversized settings payloads. | Add helper and route tests for semantic limits and redacted error handling. |
| Live two-machine validation remains operator-side. | mDNS, UNC reachability, and actual library access can vary by LAN/firewall/share permissions. | After fixes, run operator-approved worker/coordinator test with blank manual map and two libraries; do not claim real media unless explicitly authorized. |

Assigned validation run on 2026-06-15: 52 targeted tests passed. No live LAN probing, normal Launch, real media, queue claim, publish, drain, rename, settings save outside temp tests, runtime state, config, generated summaries, or media files were touched.

## Boundary Risks

- Source mutation: no assigned join/discovery/test-connection/path-map code directly deletes, renames, overwrites, publishes, drains, or cleans source/output media. The path-map findings are source identity and wrong-file-processing risks, not direct mutation paths.
- Settings boundary: worker join import is correctly routed through backend `save_settings_patch(confirm_save=True)`, but W09-001 shows that one saved setting can be reordered during import.
- Secret boundary: join blob creation/import are confirmation-gated and unjournaled. Results expose token fingerprints, not raw tokens. The join blob itself necessarily contains the worker auth token and is returned only on the secret-transfer route.
- Discovery boundary: mDNS discovery is read-only and does not save `WorkerCoordinatorUrl`; selection remains a staged UI action until Settings preview/save.
- Probe boundary: L1/L2/L3 test connection does not claim work or write media/state; L3 path checks use directory existence/readability only.

## Files With No Findings

| File / symbol | Result |
|---|---|
| `src/mediapipeline/core/network/facade.py` / `request_network_coordinator_join_blob` | Reviewed: no findings for confirmation gating, unjournaled result metadata, token fingerprinting, redacted URL output, and no media/lifecycle side effects. |
| `src/mediapipeline/core/network/facade.py` / `request_network_worker_join_cluster` | Reviewed: no findings outside W09-001/W09-003; import writes intended worker network keys through backend settings save and then runs read-only test connection. |
| `src/mediapipeline/core/network/facade.py` / `request_network_worker_discover_coordinators` | Reviewed: no findings; route is read-only, unjournaled, dedupes normalized URLs, and reports malformed mDNS rows as warnings. |
| `src/mediapipeline/core/network/facade.py` / `request_network_test_connection` | Reviewed: no findings; L1/L2/L3 layers are distinct and no mutation side effects are reported or observed. |
| `src/mediapipeline/desktop/network/mdns.py` | Reviewed: no findings for optional dependency handling, loopback advertisement skip, wildcard bind IP selection, resolver failure logging, duplicate suppression in raw discovery, and cleanup on close failures. |
| `src/mediapipeline/desktop/network/probe.py` | Reviewed: no findings for auth ping status separation and token use limited to signed request headers. |
| `src/mediapipeline/desktop/network/local_ip.py` | Reviewed: no findings for RFC1918 preference, loopback/link-local filtering, and UDP fallback behavior. |
| `src/mediapipeline/desktop/network/share_block.py` | Reviewed: no findings; helper intentionally formats operator-copy URL/token text and is not used by the current unjournaled join routes. |
| `src/mediapipeline/desktop/network/library_roots.py` / library-relative helpers | Reviewed: no findings; library IDs are matched case-insensitively, disabled libraries are skipped, duplicate library IDs are deduped, deepest root wins for claim derivation, and unsafe relative paths are rejected. |
| `src/mediapipeline/desktop/network/coordinator_url.py` and supporting `url_policy.py` | Reviewed: no findings; coordinator URLs require http/https, host, port, no bind-all address, no path/query/fragment, and no userinfo. |
| `src/mediapipeline/desktop/network/worker.py` / auto-map refresh and runtime descriptor | Reviewed: no findings outside path-map fallback issues; runtime descriptor uses token/path-map fingerprints and auto-map refresh failures leave manual mappings active. |
| `tests/python/desktop/test_network_join.py` | Reviewed: no findings; gaps listed above. |
| `tests/python/desktop/test_network_mdns.py` | Reviewed: no findings. |
| `tests/python/desktop/test_network_test_connection.py` | Reviewed: no findings. |
| `tests/python/desktop/test_network_path_auto_map.py` | Reviewed: no findings; gaps listed above. |
| `tests/python/desktop/test_network_library_relative_claim.py` | Reviewed: no findings. |
| `tests/python/desktop/test_network_local_ip.py` | Reviewed: no findings. |
| `tests/python/desktop/test_network_drift_descriptor.py` | Reviewed: no findings. |
| `tests/webview/test_webview_network_read_only_boundary.py` | Reviewed: no findings. |

## Incomplete Coverage

- Did not probe a live LAN, live mDNS network, live coordinator, or worker host.
- Did not run normal Launch, claim real work, process media, publish, drain, rename, edit source/config manually, or inspect LocalBase/runtime state.
- Did not line-read every WebView Network implementation path; only the static boundary test and path-map row editor support code were opened as evidence.
- Did not review W01/W02/W03/W05/W06-owned coordinator auth, request signing, registry, worker HTTP, worker state, done/release, or lifecycle behavior beyond supporting lines needed for this W09 scope.

## Suggested Follow-Up Prompts

1. Patch W09-001 by preserving `WorkerSourcePathMap` order during join import, then add an overlapping-prefix regression in `test_network_join.py`.
2. Harden `path_map.py` for W09-002 with backend validation/normalization for manual mappings and unsafe legacy claim tails, then add direct path-map and worker-loop release tests.
3. Add semantic bounds for W09-003 join blobs and tests proving oversized/malformed blobs fail before settings save with redacted errors.
