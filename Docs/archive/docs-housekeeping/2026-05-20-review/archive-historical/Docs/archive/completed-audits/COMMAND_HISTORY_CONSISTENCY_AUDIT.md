# Command History Consistency Audit

Purpose: document the command journal schema, recording policy, bounded FIFO behavior, WebView rendering fidelity, and known gaps. This is an observational document.

---

## Overview

The command journal records the results of backend command routes (POST routes) so the WebView can display recent activity, recover from refresh failures, and provide diagnostics context. It is a backend-owned, in-process, bounded FIFO — not a persistent log file.

**Backend source**: `DesktopApp/mediapipeline_desktop_app/api/command_journal.py`  
**Policy layer**: `DesktopApp/mediapipeline_desktop_app/api/command_journal_policy.py`  
**WebView rendering**: `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js`  
**Read route**: `GET /api/commands` → `desktop_command_history.v1`

---

## Command Result Record Schema

Each journal entry is a summarized snapshot of one command result. The full response payload is not stored — only the normalized summary.

| Field | Type | Max length / items | Notes |
|---|---|---|---|
| `at` | string (ISO 8601 UTC) | — | Timestamp when the command was recorded |
| `command` | string | 160 chars | Command name (e.g., `pipeline.start`, `rename.apply`, `settings.save_patch`) |
| `ok` | boolean | — | Whether the command succeeded |
| `severity` | string | 40 chars | `info`, `warning`, or error classification |
| `message` | string | 2000 chars | Primary result message |
| `job_id` | string | 120 chars | Launch job ID if applicable |
| `refresh_hint` | string | 80 chars | Suggested page to refresh after this command |
| `warnings` | list of strings | 20 items × 500 chars | Non-fatal issues |
| `errors` | list of strings | 20 items × 500 chars | Error detail lines |
| `log_paths` | dict str → str | 12 entries × (120 + 500 chars) | Named log file paths relevant to this command |

All fields are capped at write time by `summarize_command_payload()`. The WebView receives bounded strings — it cannot overflow on render.

---

## Recording Policy

### What Gets Recorded

Only responses with HTTP status codes 2xx–3xx are recorded. HTTP 4xx and 5xx responses are not added to the journal. This is verified by `should_record_command_payload(status_code)` and tested in `test_api_handler_policy.py`.

**Effect**: A rejected command (e.g., a validation error on `settings/validate`, a missing `confirm_apply` on `rename/apply`) is not visible in the command history. The WebView receives a command-result response for that request (displayed inline), but the journal does not retain it across page refreshes.

**Rationale**: The journal is for successful-command audit and refresh recovery. Failed commands are surfaced immediately in the command-result response and through the Diagnostics recent-events feed.

### What Is NOT Recorded

- HTTP 4xx errors (client errors — validation failures, auth failures)
- HTTP 5xx errors (server errors)
- `GET` (read) requests — these are never journaled regardless of status
- Preview/validate routes (`settings/validate`, `settings/preview-patch`, `rename/preview`, `pending-publish/recovery-plan`, `sample-validation/preview`) — these have `"effect": "none"` and their results are ephemeral; if they return 2xx they would technically be recorded under the current policy, but they use `"effect": "none"` and are low-risk

### Deduplication

The journal has no duplicate-command guard. If the same command runs twice in succession, both entries appear. The boundary is time-based FIFO eviction only: entries beyond `max_entries` (default 50) are dropped from the tail. This is intentional — the journal is a recent-activity feed, not a deduplicated command log.

---

## Bounded FIFO Behavior

| Parameter | Value | Configurable |
|---|---|---|
| `max_entries` | 50 | In-process default; not operator-configurable |
| Default `limit` for `GET /api/commands` | 20 | Client-side default; operator can request up to 50 |
| Maximum `limit` (hard cap) | `max_entries` (50) | Backend-enforced clamp |
| Storage | In-process list (not persisted to disk) | — |

On backend restart, the journal is empty. The first `GET /api/commands` after restart returns an empty entry list. The WebView displays "No command result summary loaded" until commands are recorded.

This is expected behavior. The journal is not a durable audit log — for durable records, the operator uses the run logs and state files accessible via Diagnostics.

---

## WebView Rendering Fidelity

### What The WebView Shows

`commandHistory.js` renders journal entries in the command-rows table with:

- **Status badge**: `ok`, `ok with warning`, or severity label
- **Timestamp** (`item.at`)
- **Command name** (`item.command` or `item.raw.command`)
- **Owner page**: derived from command name by `commandHistoryOwnerPage()` — maps `settings.*` → Settings, `rename.*` → Rename, `queue.*` → Queue, etc.
- **Compact evidence line**: single-line summary with status, source (`local` or `journal`), owner page, issue level, and truncated message
- **Full detail**: on row selection, shows full message, warnings list, errors list, log paths, job ID, refresh hint

WebView truncation constants (applied at render time):
- `COMMAND_RESULT_LIST_LIMIT = 5`: max warnings/errors items shown per row
- `COMMAND_RESULT_ITEM_CHARS = 240`: max chars per item in compact display

These are display truncations only. The full bounded data from the journal is available in the selected-row detail panel.

### Source Label (`local` vs `journal`)

The WebView distinguishes two command result sources:
- `local`: a result produced by the current page's operation (the in-page command result, fresh from the POST response)
- `journal`: a historical entry from `GET /api/commands` (retrieved on refresh)

This label helps operators distinguish the just-executed result from older journal entries. Both are rendered in the same table; the source label clarifies provenance.

### Owner Page Mapping

The `commandHistoryOwnerPage()` function maps command name prefixes to page labels:

| Command prefix | Owner page shown |
|---|---|
| `settings.*` | Settings |
| `rename.*` | Rename |
| `pipeline.*` | Launch |
| `audit.*` | Launch |
| `rerun.*` | Reports |
| `queue.*` | Queue |
| `pending_publish.*` | Pending Publish |
| `diagnostics.*` | Diagnostics |
| `maintenance.*` | Maintenance |
| `sample_validation.*` | Home |
| `backend.*` | (Shell — not shown to operator) |

---

## Consistency Guarantees

| Property | Guarantee |
|---|---|
| Schema version | `desktop_command_history.v1` is always present in the response |
| Entry count | `count` field matches `len(entries)` in the response |
| Entry order | Most recent entry first (prepend-on-record) |
| Field truncation | All string and list fields are capped at record time; WebView cannot receive unbounded strings |
| Recording on success only | HTTP 4xx/5xx are never recorded; journal contains only 2xx–3xx outcomes |
| No persistence | Journal is empty on every backend restart |
| Limit clamping | `limit` query param is clamped to `[1, max_entries]` by the backend regardless of client request |

---

## Known Gaps

### 1. Failed Commands Not In Journal

Operators debugging a command that failed with a 4xx (e.g., a settings validation error returned from `settings/validate`) will not see it in the journal after navigating away. They must use the in-page result display before navigation, or use `GET /api/diagnostics` (recent events) which captures a broader event feed including errors.

**Impact**: Low for daily use — failed commands are displayed inline immediately. Moderate if an operator navigates away before reading the result.

### 2. No Journal Persistence Across Restarts

If the backend restarts (due to an update, crash recovery, or Tauri shell restart), the entire journal is lost. The WebView shows an empty history. The operator must rely on run logs (via `last_stderr_log`, `last_stdout_log` in Diagnostics) for pre-restart history.

**Impact**: Low for normal operation. An operator who closes and reopens the app loses command history — this is expected behavior but may be surprising.

### 3. No Deduplication — Rapid Retries Pollute The Journal

If an operator clicks a command button multiple times in rapid succession (before the backend responds), each request that returns 2xx will be recorded separately. In the worst case, a slow-to-respond command generates multiple duplicate entries before the UI can update.

**Impact**: Low. The bounded FIFO evicts old entries automatically. The WebView shows the most recent 20 by default.

### 4. Preview/Validate Routes Counted Against Journal If They Return 2xx

`settings/validate`, `settings/preview-patch`, and `rename/preview` have `"effect": "none"` but are POST routes. If they return 2xx, the current recording policy (`should_record_command_payload(status_code)`) would add them to the journal. This is a minor consistency gap: the journal should ideally contain only commands with actual state effects.

**Recommendation**: The recording policy could exclude known `"effect": "none"` POST routes by checking the command name prefix, or the handler layer could annotate preview/validate responses with a `"no_journal": true` flag. Not urgent — preview routes are rarely the source of operator confusion.

### 5. `log_paths` Are Not Validated As Existing Paths

Journal entries may include `log_paths` keys (e.g., `"stdout": "/path/to/log.txt"`). These paths are captured at command time but are not verified as still existing when the WebView fetches the journal entry. A `log_paths` entry may point to a file that has since been rotated or deleted.

**Impact**: Low. The WebView shows log_paths as reference links; the operator opens them via the Diagnostics `open`/`tail` routes, which validate paths through the backend allowlist at access time.

---

## See Also

- Route: `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` (`GET /api/commands`)
- Diagnostics events (broader event feed including errors): `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Command journal tests: `DesktopApp/tests/test_api_command_journal_policy.py`, `test_api_handler_policy.py`
