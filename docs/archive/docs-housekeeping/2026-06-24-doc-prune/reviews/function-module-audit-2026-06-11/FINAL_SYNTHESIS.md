# Final Synthesis

Status: **partial audit complete**. All 12 requested worker files exist and were merged, but full repository coverage was not achieved because workers reported time-boxed/partial coverage and the generated project index is stale.

## Top 10 Highest-Risk Findings

| Rank | ID | Severity | Domain | Problem |
|---:|---|---|---|---|
| 1 | W02-001 | P1 | W02-core-config-settings-library | Python Settings validation returns only warnings for source/output/scratch nesting that the PowerShell runtime schema rejects as errors, so Settings Save can persist a config that later fails pipeline launch schema validation. |
| 2 | W02-002 | P1 | W02-core-config-settings-library | Final-library promotion treats any file named `<primary stem>.*` as a sidecar, including other media files such as `Movie.sample.mkv`; if cleanup-after-verified is enabled, those extra media files are copied and then deleted from the publish root as if they were sidecars. |
| 3 | W03-001 | P1 | W03-core-queue-process-status | Dead-worker claims with an existing result file are preserved as `result_ready`, but `result_ready` is also treated as an active duplicate claim and startup never consumes old result files outside the current `$active` set. A controller crash/kill after a worker writes its result but before claim release can leave that source blocked from future local-worker runs. |
| 4 | W04-1 | P1 | W04-publish-completed-pending-rename | Existing final sidecar can be removed after a failed reveal when the pre-existing sidecar backup failed. |
| 5 | W04-3 | P1 | W04-publish-completed-pending-rename | Rename apply blocks only `outside_configured_roots`; requests with no configured roots become `unscoped_operator_path` and can proceed with normal confirm-apply. |
| 6 | W05-001 | P1 | W05-media-policy-ffmpeg-subtitles-audio | Folder/override policy drops supported `fallback_remux` size guard mode, so the configured fallback path can silently revert to defaults. |
| 7 | W05-002 | P1 | W05-media-policy-ffmpeg-subtitles-audio | MP4 converted subtitle sidecar planning collapses ASS/BDPGS/VobSub candidates into TX3G sidecar records and selects only the first candidate. |
| 8 | W09-001 | P1 | W09-tauri-rust-shell | The shell exits even if the final safe-only backend shutdown request is blocked after the pre-close readiness check. |
| 9 | W01-001 | P2 | W01-backend-api-application | Authenticated network workers can inject extra physical lines into `cluster.log` through newline-bearing `worker_name` or `message` fields. |
| 10 | W04-2 | P2 | W04-publish-completed-pending-rename | Successful pending park moves the local output before result size is read, so the returned `OutputSizeBytes` can collapse to `0`. |

## Domain Risk Summary

| Domain | Summary |
|---|---|
| W01-backend-api-application | 1 merged findings; coverage partial. All summaries/AST inventory; 36 files line-read; 100 files not semantically reviewed. |
| W02-core-config-settings-library | 2 merged findings; coverage partial. Targeted config/final-library review; many config metadata/PowerShell files summary-only. |
| W03-core-queue-process-status | 1 merged findings; coverage partial. Targeted queue/process review; incomplete groups listed. |
| W04-publish-completed-pending-rename | 3 merged findings; coverage partial. Actual coverage plus 10 summary-only files. |
| W05-media-policy-ffmpeg-subtitles-audio | 2 merged findings; coverage partial. Targeted media/subtitle review; incomplete groups listed. |
| W06-contracts-storage-observability | 6 merged findings; coverage partial. Completed/partial/pending coverage mixed. |
| W07-webview-shell-common | 0 merged findings; coverage partial. Several shell/common files fully reviewed; app.js and others partial. |
| W08-webview-pages | 1 merged findings; coverage partial. All summaries/static scans; 19 targeted source inspections; 100 not line-reviewed. |
| W09-tauri-rust-shell | 2 merged findings; coverage partial. Core lifecycle sources reviewed; long contracts/scripts static-reviewed. |
| W10-ops-powershell-scripts | 6 merged findings; coverage partial. Partial ops/script review; incomplete groups listed. |
| W11-tests-python-webview-tooling | 4 merged findings; coverage partial. 17 files full-source reviewed; remaining summary/search-only. |
| W12-docs-generated-unknown | 5 merged findings; coverage partial. Targeted docs/generated review; remaining summary/grep only. |

## Coverage Proof

- Required entry docs were read before assignment: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, and `docs/generated/PROJECT_INDEX.md`.
- The available index listed 1,296 files and every indexed file had a generated summary.
- 12 worker ledgers were produced under `workers/`.
- `symbol_inventory.json` inventoried 1,296 indexed files with 0 Python parse errors and roughly 15,625 Python/JS/PowerShell/Rust symbols detected.
- Coverage is partial because no worker claimed full coverage and W12 found the index stale.

## Recommended Fix Order

1. Regenerate `PROJECT_INDEX.md`, dependency graph, `PIPELINE_MAP.md`, and `FEATURE_FILE_MAP.md`, then audit the delta files.
2. Fix P1 safety issues across publish/rename/settings/final-library/queue/media/subtitles/Tauri close-readiness.
3. Fix P2 contract, storage, release, WebView, tooling, and stale-doc issues.
4. Fix P3 hardening issues and validation clarity gaps.
5. Rerun incomplete worker slices after generated inputs are fresh.

## Validation Ladder By Fix Group

| Fix group | Validation ladder |
|---|---|
| Generated docs/index | Generator `--check` commands, active-doc reference checks, summary refresh, assignment delta audit. |
| Publish/pending/rename/final-library | Targeted unit tests, pending-publish fixtures, rename apply route tests, final-library promotion tests; real-media validation if movement behavior changes. |
| Settings/config | Python Settings Preview/Save tests plus PowerShell schema parity checks. |
| Queue/process/Tauri close | Process lifecycle tests, stale claim recovery tests, close-readiness adversarial Tauri smoke. |
| Media/subtitles | PowerShell unit tests plus representative real-media validation for fallback remux and ASS/BDPGS/VobSub/MP4 subtitle behavior. |
| Contracts/storage/observability | Contract tests and PowerShell root-boundary cleanup/copy tests. |
| WebView/release/tooling | Static/unit tests, browser smoke with required prerequisites, release package leak/exclusion checks, failure-injection tests. |

## Unresolved Review Gaps

- Full function/module-level coverage was not achieved.
- At least 112 files indicated by current generator output were not assigned from the stale index.
- W08 and W11 have the largest line-by-line gaps.
- W07, W10, W12, and W06 include explicit summary/search-only groups.
- No coordinator tests, smokes, release builds, Tauri checks, or real-media validations were run.
