# Stale Docs / TODO Audit

Date: 2026-05-14

Purpose: identify stale-looking documentation, TODO/FIXME notes, V3/V4 drift, and obsolete checklist language across `Docs\`, root `.ps1` files, and the Python/PowerShell source layers.

This is an observation document. It does not make code changes.

---

## Search Summary

Searches performed:

```powershell
Select-String -Path Docs\*.md -Pattern "TODO|FIXME|deprecated|obsolete|old"
Select-String -Path Pipeline\*.ps1 -Pattern "TODO|FIXME" -Recurse
Select-String -Path DesktopApp\mediapipeline_desktop_app\**\*.py -Pattern "TODO|FIXME"
```

---

## Findings: Stale and Should Update

### DEPLOYABILITY_CHECKLIST.md — Date Stamp

`Docs/DEPLOYABILITY_CHECKLIST.md` states: "Checked on 2026-05-07 from the V5 bundle root." As of 2026-05-14, significant changes have been made (new smoke wrappers, new API routes, new WebView panels, new test files). The checklist should be re-run against the current V5 state.

**Recommendation**: Re-run the checklist items against the current folder and update the "Checked on" date.

**Risk if left stale**: A new contributor reading the checklist may trust an outdated deployability verdict.

---

### README_MediaPipelineRemuxEncodeAIO.md — "Subtitles.ps1 Migration-Only Comments" Reference

`Docs/README_MediaPipelineRemuxEncodeAIO.md` line 46 references "Migration-only comments and obsolete scaffolding have been removed; retained wrappers are treated as compatibility APIs until call sites and docs are deliberately migrated." This is a historical note about a previous refactor. It is not wrong, but the phrase "until call sites and docs are deliberately migrated" implies ongoing future work that may already be complete.

**Recommendation**: Verify whether `Subtitles.ps1` migration is complete. If done, update the note to say "migration is complete" instead of "until."

**Risk if left as-is**: Low — this is engineering context, not operator-facing.

---

## Findings: Historical and Should Remain

These files contain "old/deprecated/V3/V4" language that is deliberately preserved.

| File | Pattern found | Why intentional |
|---|---|---|
| `Docs/CODE_CLEANUP_CHECKLIST.md` | "V4 Code Cleanup Archive" | Archive header — should say V4 |
| `Docs/CONTROL_SURFACE_HARDENING_CHECKLIST.md` | "V4 Control Surface Hardening Archive" | Archive header — should say V4 |
| `Docs/V4_MIGRATION_NOTES.md` | Entire file references V3→V4 | Historical provenance document |
| `Docs/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md` | "Keep V4 Intact", "V4 is working well" | Transition design requires V4 as backup |
| `Docs/TLDR.md` | "V4 remains backup" | Operational guidance |
| `Docs/STALE_VERSION_LABEL_AUDIT.md` | V3/V4 labels discussed throughout | This doc is about V3/V4 — intentional |
| `Docs/STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md` | V4 references | Addendum to the audit — intentional |
| `Docs/OPERATOR_GLOSSARY.md` | "deprecated" used in definition of Tk Fallback | Definitional — "not to be deprecated" |
| `Docs/REMEDIATION_CHANGELOG.md` | "Replaced deprecated UTC timestamp formatting" | Historical change record — intentional |
| All `CLAUDE_HANDOFF_*` docs | "V4 as known-good backup" | Context for AI sessions — intentional |

---

## Findings: False Positives

These occurrences look stale at first glance but are not product version labels.

| File | Pattern | What it actually is |
|---|---|---|
| `Pipeline/Tests/Invoke-ToolIntegrationChecks.ps1` | `'V4+ Styles'`, `'ScriptType: v4.00+'` | ASS/SSA subtitle format version markers — not product version |
| Various subtitle config references | `v4.00` | ASS format version string — not product version |

---

## Findings: No TODO or FIXME

Searched all `Pipeline\*.ps1` (including `Pipeline\Modules\*.ps1`) and all `DesktopApp\mediapipeline_desktop_app\**\*.py` for `TODO` and `FIXME`.

**Result**: Zero matches. The codebase has no inline TODO or FIXME comments.

---

## Findings: Needs Codex / Operator Decision

### CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md — Still Actionable?

`Docs/CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md` is a handoff task document for adding a root smoke wrapper for the rename readiness test. The wrapper `Test-WebViewRenameReadinessSmoke.ps1` now exists in the project root.

**Question**: Is this handoff doc still needed, or should it be archived?

**Recommendation**: If the task described in the doc is complete, mark it as completed in the header and add it to the "completed handoffs" category in DOCS_INDEX.md.

---

### CLAUDE_HANDOFF_20_TASK_BACKLOG.md — Earlier Task Backlog

`Docs/CLAUDE_HANDOFF_20_TASK_BACKLOG.md` is an earlier task backlog (the non-admin set of 20 tasks). Based on prior session history, many or all of those tasks have been completed. The doc should be checked for completed vs remaining work and either archived or updated.

**Question**: Which tasks in CLAUDE_HANDOFF_20_TASK_BACKLOG.md are still pending?

**Recommendation**: Review and update task statuses. If all 20 are complete, archive the doc.

---

### UI_IMPROVEMENT_CHECKLIST.md — Future Ideas, Not Operator-Facing

`Docs/UI_IMPROVEMENT_CHECKLIST.md` contains future UI improvement ideas. It is explicitly noted as "not part of the deployable operator package by default" in DOCS_INDEX.md. However, it is not clear whether any of the items in it have been implemented in the WebView.

**Recommendation**: Low priority. Review against the current parity matrix and mark completed items.

---

### NETWORK_UX_IMPROVEMENTS.md — Unlisted, Status Unclear

`Docs/NETWORK_UX_IMPROVEMENTS.md` is not listed in `Docs/DOCS_INDEX.md`. It describes UX improvements for coordinator/worker setup (showing detected coordinator URLs, copy button, etc.). These improvements may or may not be implemented in the current WebView.

**Recommendation**: Add to DOCS_INDEX.md with a note about its status. If the improvements are implemented, reference the relevant parity matrix rows. If not implemented, note that Network mode is read-only in the WebView.

---

## Summary Table

| File / Area | Finding | Class | Priority |
|---|---|---|---|
| `DEPLOYABILITY_CHECKLIST.md` | Date stamp stale (2026-05-07) | Stale — should update | Medium |
| `README_MediaPipelineRemuxEncodeAIO.md` line 46 | "until migration" — may already be done | Stale or false positive | Low |
| `CLAUDE_HANDOFF_RENAME_READINESS_WRAPPER.md` | Task may be complete | Needs decision | Low |
| `CLAUDE_HANDOFF_20_TASK_BACKLOG.md` | Earlier task statuses unknown | Needs decision | Low |
| `UI_IMPROVEMENT_CHECKLIST.md` | Some items may be implemented | Needs review | Low |
| `NETWORK_UX_IMPROVEMENTS.md` | Not in DOCS_INDEX; status unclear | Needs decision | Low |
| All V3/V4 references in archive docs | Intentional historical context | Historical — remain | N/A |
| `TODO`/`FIXME` in PS/Python code | None found | False positive | N/A |
| ASS `v4.00` format markers | Not product version | False positive | N/A |

---

## See Also

- Version label audit: `Docs/STALE_VERSION_LABEL_AUDIT.md`
- Version label addendum: `Docs/STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md`
- Docs index: `Docs/DOCS_INDEX.md`
- Documentation index audit: `Docs/DOCS_INDEX_AUDIT_NOTES.md` (C-ADM-001 output)
