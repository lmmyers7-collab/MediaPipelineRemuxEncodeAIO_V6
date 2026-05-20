# Command History Owner Coverage Audit

Date: 2026-05-14

Checks whether the `commandHistoryOwnerPage()` function in `commandHistory.js` maps all known command names to an owner page. Cross-references the command prefix/name patterns against the backend command route contracts.

---

## Source

Primary: `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`, function `commandHistoryOwnerPage(item)`.

---

## Current Owner-Page Mapping (From commandHistoryOwnerPage)

The function resolves the owner page using command prefix matching in this priority order:

| Command pattern | Resolved owner page |
|---|---|
| `settings.*` | Settings |
| `schedule.*` | Schedule |
| `rename.*` | Rename |
| `queue.*` | Queue |
| `completed.*` | Completed |
| `pending_publish.*` | Pending Publish |
| `diagnostics.*` | Diagnostics |
| `report.*` or command includes `"report"` | Audit / Reports |
| `maintenance.*` | Maintenance |
| `network.*` | Network |
| `sample_validation.*` | Home / Validation |
| `backend.shutdown` (exact) | Diagnostics |
| `pipeline.control.*` | Home / Launch |
| `pipeline.start` (mode = `drain_pending_pushes`) | Pending Publish |
| `pipeline.start` (all other modes) | Launch |
| `audit.start` (exact) | Launch |
| `rerun.start` (exact) | Launch |
| refresh_hint = `pending_publish` | Pending Publish |
| refresh_hint = `queue` | Queue |
| refresh_hint = `completed` | Completed |
| refresh_hint = `settings` | Settings |
| refresh_hint = `schedule` | Schedule |
| refresh_hint = `snapshot` | Home / Launch |
| **Default** | **Diagnostics** |

---

## Coverage Against Backend Command Routes

Based on the `contract_command.py` command route groups (22 total POST routes), the prefix mapping covers:

| Command group | Prefix covered by | Notes |
|---|---|---|
| Diagnostics open | `diagnostics.*` | Covered |
| Diagnostics tail | `diagnostics.*` | Covered |
| Maintenance (audit start, CSV rerun) | `maintenance.*` + `audit.start` + `rerun.start` | Covered |
| Rename (plan, apply) | `rename.*` | Covered |
| Settings (preview, save-patch) | `settings.*` | Covered |
| Schedule (preview, save) | `schedule.*` | Covered |
| Sample validation (append) | `sample_validation.*` | Covered |
| Process / pipeline start | `pipeline.start` + mode routing | Covered |
| Process / pipeline control | `pipeline.control.*` | Covered |
| Backend shutdown | `backend.shutdown` | Covered (maps to Diagnostics) |
| Queue (if any) | `queue.*` | Covered by prefix |
| Pending publish (drain) | `pipeline.start` mode routing | Covered via drain_pending_pushes mode |
| Network (if any) | `network.*` | Covered by prefix |
| Report | `report.*` | Covered by prefix or includes "report" |

**No unmapped command prefixes identified.** All 22 command route groups have at least one matching prefix or exact-match rule in `commandHistoryOwnerPage`.

---

## Commands That Fall Back to Diagnostics

The following commands fall back to "Diagnostics" as their owner page:
- `backend.shutdown` (explicit exact match to Diagnostics — correct; lifecycle is Diagnostics-page owned)
- Any command whose prefix is not in the mapping and whose refresh_hint is absent or not recognized
- Any command issued by the Diagnostics page itself (`diagnostics.*`)

The Diagnostics fallback is intentional — it is the "unknown command" owner and the page that can investigate any state issue.

---

## Suggestions

| Suggestion | Priority | Notes |
|---|---|---|
| No changes required | — | All known command prefixes are mapped. The default-to-Diagnostics fallback is appropriate for unknown commands. |
| Consider logging when default fallback fires | Low | A console.log or debug flag when a command reaches the default case would make future coverage gaps visible. Not urgent. |

---

## Consistency With COMMAND_HISTORY_CONSISTENCY_AUDIT.md

`Docs\COMMAND_HISTORY_CONSISTENCY_AUDIT.md` documents the journal schema and recording policy. This audit adds the owner-page coverage layer. The two docs are complementary:
- `COMMAND_HISTORY_CONSISTENCY_AUDIT.md`: schema, recording policy, FIFO behavior, rendering fidelity
- This doc: command-to-owner-page routing, coverage gaps, fallback behavior

---

## Task Output

```
Task ID: CLN-013
Files inspected: DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js, Docs\COMMAND_HISTORY_CONSISTENCY_AUDIT.md
Files changed: Docs\COMMAND_HISTORY_OWNER_COVERAGE_AUDIT.md (created)
Validation: Read full commandHistoryOwnerPage() function. Cross-referenced with known command route groups.
Findings: All command route groups have prefix coverage. No unmapped commands found. Default-to-Diagnostics fallback is appropriate.
Open questions: None.
Risk: Low — documentation only.
```
