# Docs Folder Dead Markdown Audit

Date: 2026-05-14

Purpose: classify all `.md` files in `Docs/` as keep-active (operator-facing), keep-active (engineering), archive (completed work), flag-for-review, or future/aspirational. Does not delete or rename any files.

Source: directory listing of `Docs/` with file sizes and modification dates as of 2026-05-14.

Total files in `Docs/`: 60 `.md` files (56 as of 2026-05-14; 4 added in CLN3 session 2026-05-15 — see Freshness Review below).

---

## Category 1: Keep Active — Operator-Facing Daily Reference

Included in clean release packages by default. Current content as of 2026-05-14.

| File | Size | Last Modified | Notes |
|---|---|---|---|
| `README_MediaPipelineRemuxEncodeAIO.md` | 12K | 2026-05-14 | Bundle overview, launchers, first-run order |
| `TLDR.md` | 22K | 2026-05-14 | Daily-use summary; updated this session |
| `OPERATOR_GLOSSARY.md` | 11K | 2026-05-14 | Primary terminology reference; new this session |
| `VALIDATION_LADDER_RUNBOOK.md` | 11K | 2026-05-14 | Ordered validation runbook; new this session |
| `PACKAGING_DEPENDENCY_INVENTORY.md` | 7.5K | 2026-05-14 | Bundled/external dependency inventory; new this session |
| `RELEASE_PACKAGE_ADMIN_INVENTORY.md` | 7.6K | 2026-05-14 | Release package inclusions/exclusions; new this session |
| `WEBVIEW_SMOKE_TEST_CATALOG.md` | 16K | 2026-05-14 | Smoke wrapper catalog; current |
| `WEBVIEW_SMOKE_RESULT_TEMPLATE.md` | 4.3K | 2026-05-14 | Copyable smoke result template; new this session |
| `BROWSER_SMOKE_TEST_RUNBOOK.md` | 11K | 2026-05-14 | Browser smoke prerequisites and interpretation |
| `BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md` | 7K | 2026-05-14 | Step-by-step browser smoke environment checklist; new this session |
| `REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` | 6.1K | 2026-05-14 | Copyable evidence template; new this session |
| `FAILURE_TRIAGE_WORKSHEET.md` | 6.3K | 2026-05-14 | Copyable failure triage worksheet; new this session |
| `POWERSHELL_HOST_EXPECTATIONS.md` | 8.6K | 2026-05-14 | PS7.6.0 resolution order and prohibited patterns |
| `SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md` | 7K | 2026-05-15 | Operator guide for sample validation records; when to record, mutation boundary, privacy warning; new CLN3 session |

---

## Category 2: Keep Active — Engineering Reference

Engineering and admin documentation with ongoing relevance. Some are dev-only (excluded from clean release by build script).

| File | Size | Last Modified | Notes |
|---|---|---|---|
| `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | 15K | 2026-05-14 | All 41 routes; authoritative |
| `LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | 10K | 2026-05-14 | Route mutation classification; new this session |
| `SETTINGS_BUILDER_COVERAGE_MATRIX.md` | 6.9K | 2026-05-14 | Config key to builder coverage map |
| `DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md` | 8.3K | 2026-05-14 | All 22 diagnostics open/tail targets |
| `RENAME_SAFETY_TEST_INVENTORY.md` | 9.7K | 2026-05-14 | Rename test files and coverage gaps |
| `PENDING_PUBLISH_FIXTURE_INVENTORY.md` | 9.5K | 2026-05-14 | Pending publish test files and coverage |
| `TAURI_BACKEND_LIFECYCLE_BOUNDARY.md` | 7.1K | 2026-05-14 | Lifecycle boundary spec |
| `TAURI_WEBVIEW_PARITY_MATRIX.md` | 96K | 2026-05-14 | Tk vs WebView parity matrix; large but active |
| `archive/admin-audits/WEBVIEW_DOM_ID_NAMESPACE_AUDIT.md` | 8.4K | 2026-05-14 | DOM ID naming and ownership map |
| `COMMAND_HISTORY_CONSISTENCY_AUDIT.md` | 10K | 2026-05-14 | Command journal schema and consistency |
| `archive/admin-audits/STALE_VERSION_LABEL_AUDIT.md` | 6.4K | 2026-05-14 | V3/V4 label audit; 4 labels still pending |
| `archive/admin-audits/STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md` | 4.7K | 2026-05-14 | Addendum: no new stale labels in V5 Tauri files |
| `archive/admin-audits/WEBVIEW_OPERATOR_COPY_AUDIT.md` | 7.4K | 2026-05-14 | Operator-facing copy vocabulary audit |
| `V5_MODULE_OWNERSHIP_REVIEW_ADDENDUM.md` | 9.1K | 2026-05-14 | Python module inventory and fragmentation concerns |
| `V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` | 17K | 2026-05-07 | Real-media observational checklist; current |
| `V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md` | 12K | 2026-05-14 | Sample validation JSONL design |
| `V5_TRANSITION_STATUS_BOARD.md` | 8.4K | 2026-05-14 | V5 transition status board; new this session |
| `V5_MIGRATION_RISK_REGISTER.md` | 13K | 2026-05-14 | 15 transition risk entries; new this session |
| `NETWORK_READ_ONLY_PARITY_AUDIT.md` | 11K | 2026-05-14 | Network page parity and read-only scope |
| `NETWORK_UX_IMPROVEMENTS.md` | 11K | 2026-05-02 | Planned coordinator UX; not yet implemented |
| `DEPLOYABILITY_CHECKLIST.md` | 11K | 2026-05-07 | **Date stamp stale** (2026-05-07); re-run needed |
| `archive/admin-audits/STALE_DOCS_TODO_AUDIT.md` | 7.1K | 2026-05-14 | TODO/FIXME audit; new this session |
| `CHANGELOG_NAVIGATION_PROPOSAL.md` | 6.7K | 2026-05-14 | REMEDIATION_CHANGELOG navigation plan |
| `RUNTIME_ARTIFACT_INVENTORY.md` | 8.8K | 2026-05-14 | Runtime state artifact inventory |
| `TEST_SUITE_SUBSYSTEM_INVENTORY.md` | 16K | 2026-05-14 | Test file to subsystem mapping |
| `CONFIG_KEY_GLOSSARY_DRAFT.md` | 13K | 2026-05-14 | Config key glossary |
| `NO_TOUCH_BOUNDARY_REGISTER.md` | 11K | 2026-05-14 | 14 no-touch boundaries |
| `DOCS_INDEX.md` | 14K | 2026-05-14 | Documentation index; updated this session |
| `GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md` | 39K | 2026-05-07 | Architecture decision record; still relevant |
| `SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md` | 9K | 2026-05-15 | All 12 sample validation schema constants with field summaries; new CLN3 session |
| `TAURI_ASSET_GATE_FRAGMENT_AUDIT.md` | 14K | 2026-05-15 | 53 fragments in 7 asset groups from lib.rs validate_backend_web_ui; new CLN3 session |

---

## Category 3: Archive — Completed Work (Retain, Do Not Delete)

These document completed phases and are already excluded from clean release packages by the build script. Keep for historical context.

| File | Size | Last Modified | Notes |
|---|---|---|---|
| `archive/completed-checklists/CODE_CLEANUP_CHECKLIST.md` | 1.3K | 2026-05-06 | Completed V4 cleanup archive; rows pruned |
| `archive/completed-checklists/CONTROL_SURFACE_HARDENING_CHECKLIST.md` | 1.4K | 2026-05-06 | Completed hardening archive |
| `archive/completed-checklists/NETWORK_MODE_CHECKLIST.md` | 1.6K | 2026-05-06 | Completed network implementation archive |
| `archive/completed-checklists/UI_CHECKLIST.md` | 898 B | 2026-05-06 | Completed UI improvement archive; rows pruned |
| `archive/completed-checklists/UI_CHECKLIST_2.md` | 729 B | 2026-05-06 | Same; rows pruned |
| `archive/completed-checklists/UI_CHECKLIST_3.md` | 894 B | 2026-05-06 | Same; rows pruned |
| `archive/historical-reviews/V4_MIGRATION_NOTES.md` | 1.2K | 2026-05-01 | Historical V3→V4 migration provenance |
| `REMEDIATION_CHANGELOG.md` | 1.4M | 2026-05-14 | Incremental change log (1.4 MB); see `CHANGELOG_NAVIGATION_PROPOSAL.md` for navigation strategy |

---

## Category 4: Large Transition Docs — Flag for Review

Very large documents that may be either the current engineering plan or historical background. Size prevents routine inline review.

| File | Size | Last Modified | Concern |
|---|---|---|---|
| `V5_TAURI_TRANSITION_CURRENT_PLAN.md` | 252K | 2026-05-14 | Comprehensive transition plan; confirm whether `V5_TRANSITION_STATUS_BOARD.md` supersedes it as the daily-reference |
| `TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md` | 85K | 2026-05-14 | Groundwork doc; confirm whether it is still the primary architecture reference or historical background |

**Recommendation**: do not delete or archive these. Confirm with the engineering team whether the new status board + current plan serve as the primary daily-reference, with these large docs as background reading.

---

## Category 5: Handoff Docs — Annotate Completion Status

AI session handoff documents. The tasks they describe may be complete.

| File | Size | Status | Recommendation |
|---|---|---|---|
| `archive/old-ai-directives/CLAUDE_HANDOFF_ADMIN_20_TASK_BACKLOG.md` | 21K | All 20 C-ADM tasks complete (done 2026-05-14) | Mark header "All tasks complete 2026-05-14" |
| `archive/old-ai-directives/CLAUDE_HANDOFF_20_TASK_BACKLOG.md` | 19K | Earlier task backlog; completion status unverified | Review task statuses; annotate completed |
| `archive/old-ai-directives/CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md` | 6.1K | Task complete — `Test-WebViewRenameReadinessSmoke.ps1` exists | Mark header "Task complete" |
| `CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md` | 28K | All 30 CLN3 tasks complete (done 2026-05-15) | Mark header "All tasks complete 2026-05-15" |

---

## Category 6: Future / Aspirational

Not operator-facing production docs. Excluded from clean release packages.

| File | Size | Notes |
|---|---|---|
| `UI_IMPROVEMENT_CHECKLIST.md` | 2.8K | Future UI improvement ideas |
| `NETWORK_UX_IMPROVEMENTS.md` | 11K | Planned coordinator URL/copy UX; Network mode is currently read-only in WebView |

---

## Action Items

| Priority | Action |
|---|---|
| Medium | Re-run `DEPLOYABILITY_CHECKLIST.md` and update date stamp (currently 2026-05-07) |
| Low | Annotate completion headers in CLAUDE_HANDOFF_*.md files |
| Low | Verify whether 20 tasks in `archive/old-ai-directives/CLAUDE_HANDOFF_20_TASK_BACKLOG.md` are complete |
| Low | Confirm daily-driver role of `V5_TAURI_TRANSITION_CURRENT_PLAN.md` vs. `V5_TRANSITION_STATUS_BOARD.md` |
| N/A | All three UI_CHECKLIST*.md files are tiny archives — keep as-is |

---

## Summary Table

| Category | Count |
|---|---|
| Keep Active — Operator | 14 |
| Keep Active — Engineering | 31 |
| Archive — Completed | 8 |
| Large Transition — Flag for Review | 2 |
| Handoff — Annotate Status | 4 |
| Future / Aspirational | 2 (counted in Engineering above) |
| **Total in Docs/** | **60** |

---

---

## Freshness Review — 2026-05-15 (CLN3-028)

Added 4 new docs created during the CLN3 session to their correct categories. Updated total count from 56 to 60.

| New doc | Category | Notes |
|---|---|---|
| `SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md` | Category 1 — Operator | Operator-facing; covers when to record, mutation boundary, privacy warning; release-package-includable |
| `SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md` | Category 2 — Engineering | Engineering reference; all 12 schema version constants documented |
| `TAURI_ASSET_GATE_FRAGMENT_AUDIT.md` | Category 2 — Engineering | Engineering reference; 53 fragments in 7 asset groups from lib.rs; confirms no stale fragments |
| `CLAUDE_HANDOFF_TRANSITION_SUPPORT_30_TASKS_ROUND3.md` | Category 5 — Handoff | AI session handoff; all 30 CLN3 tasks complete as of 2026-05-15 |

No categories deprecated. No files moved to archive. Count correction only.

```
Task ID: CLN3-028
Files inspected: Docs\DOCS_DEAD_MARKDOWN_AUDIT.md
Files changed: Docs\DOCS_DEAD_MARKDOWN_AUDIT.md (4 new docs added to correct categories; total count updated 56→60; CLN3-028 freshness note added)
Validation: Select-String -Path Docs\DOCS_DEAD_MARKDOWN_AUDIT.md -Pattern "SAMPLE_VALIDATION_RECORD|TAURI_ASSET_GATE|CLAUDE_HANDOFF_TRANSITION_SUPPORT_30"
Findings: 4 new CLN3 docs were absent from the audit. Added to correct categories. Summary table counts updated.
Open questions: None.
Risk: Low — documentation only.
```

---

## See Also

- Stale TODO/FIXME audit: `Docs/archive/admin-audits/STALE_DOCS_TODO_AUDIT.md`
- Changelog navigation: `Docs/CHANGELOG_NAVIGATION_PROPOSAL.md`
- Documentation index: `Docs/DOCS_INDEX.md`
