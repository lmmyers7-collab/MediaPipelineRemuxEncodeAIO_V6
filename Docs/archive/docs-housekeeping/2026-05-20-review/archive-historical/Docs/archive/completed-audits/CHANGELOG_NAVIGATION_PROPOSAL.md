# Changelog Navigation and Pruning Proposal

Date: 2026-05-14

Purpose: propose ways to make `Docs/REMEDIATION_CHANGELOG.md` easier to navigate without deleting history. Do not split or prune the file until this proposal is reviewed and approved by the operator.

---

## Current State

`Docs/REMEDIATION_CHANGELOG.md` has grown to over 250 `## ` section headings spanning entries from 2026-05-08 to 2026-05-14 (approximately 6 days of V5 Tauri/WebView2 transition work). The file covers approximately 130 distinct feature and remediation entries plus incremental addenda.

The size is not a bug — it reflects genuine incremental work. The problem is navigation: finding a specific feature entry in 250+ headings is slow in a plain text editor, and the file does not distinguish high-level feature milestones from small addenda or administrative corrections.

---

## Navigation Problems

1. **No table of contents**: Readers must scroll or search for a heading. In editors without outline support, this means repeated searches.
2. **No date anchors**: Entries are ordered by date but headings do not include date prefixes, so searching by date requires reading heading context.
3. **No subsystem tags**: Entries mix WebView JS, backend API, release builder, documentation, and administrative corrections without grouping.
4. **Addenda accumulation**: Many features have 3–8 follow-up addenda immediately after the initial entry. These read as one logical feature but are fragmented across multiple headings.
5. **No milestone markers**: Large feature completions (e.g., Settings patch evidence smoke, Diagnostics owner-page handoff) are not visually distinguished from small corrections.

---

## Risk of Over-Splitting

Splitting the changelog too aggressively creates problems:

- **Cross-reference fragility**: Many addenda reference the feature entry they extend. Splitting to separate files breaks these references without adding a redirect.
- **Reader context loss**: A reader following one feature across its addenda benefits from seeing them together.
- **Maintenance burden**: Multiple files require updates when the format changes.
- **Search scope**: A single file is searchable in one `Select-String` command; multiple files require `-Recurse`.

Splitting is appropriate only when the file becomes large enough that load time or editor stability is affected. For Markdown, 250 headings is large but not typically problematic.

---

## Proposed Minimal First Step: Table of Contents Index

Add a collapsible or pinned table of contents section at the top of `REMEDIATION_CHANGELOG.md` that lists major feature milestones by date and heading anchor, organized by subsystem.

Example structure:

```markdown
## Index

### 2026-05-08 to 2026-05-10: Settings and Launch Handoffs

- [Settings Staged Media Policy Delta](#settings-staged-media-policy-delta)
- [Launch Unsaved Settings Warning](#launch-unsaved-settings-warning)
- [Backend Preview / Save Result Handoff](#backend-preview--save-result-handoff)

### 2026-05-11 to 2026-05-12: Diagnostics and Owner-Page Handoffs

- [Diagnostics Owning Page Evidence Handoff](#diagnostics-owning-page-evidence-handoff)
- [Command Failure Resolution Checklist](#command-failure-resolution-checklist)
- ...

### 2026-05-13 to 2026-05-14: Smoke Wrappers and Admin Tasks

- [Test-WebViewBrowserPendingDrainGuardSmoke](#test-webviewbrowserpendingdrainquardsmoke)
- ...
```

This change does not move, delete, or split any content. It adds only read navigation. It can be reviewed and corrected by the operator before adoption.

---

## Proposed Second Step: Subsystem Tags in Headings

For new entries, prefix heading names with a subsystem tag in brackets:

```markdown
## [WebView/Queue] Launch Decision Checklist Added to Queue Page
## [API] GET /api/launch/preflight Added
## [Smoke] Test-WebViewBrowserSettingsLaunchSmoke Added
## [Admin] Docs Index Updated
## [Pipeline] Versioning.ps1 Version Bump
```

This is a lightweight convention that does not break existing headings and makes future `Select-String -Pattern "\[WebView"` searches significantly more targeted.

---

## Proposed Third Step: Archive Split Criteria

If the file grows beyond a threshold that causes real navigation problems (suggested: 500+ headings), create a dated archive file and start a new active changelog:

- Archive file: `REMEDIATION_CHANGELOG_ARCHIVE_2026_05.md` (all entries up to a clean date boundary)
- Active file: `REMEDIATION_CHANGELOG.md` (new entries only from the archive cutoff)
- Link from the active file header to the archive

Archive split criteria checklist:

- [ ] All entries in the archived date range are complete (no in-progress feature branches)
- [ ] A link from the active file to the archive is added before splitting
- [ ] The archive file gets a header explaining the date range and the reason for archiving
- [ ] No cross-references in code or tests point to archived heading anchors

---

## What Pruning Would Remove

The following types of entries could be pruned from a future consolidated version without losing meaning:

- Small typo/copy corrections (collapse into the original entry as a note)
- Intermediate "in progress" entries for a feature that has a completed addendum
- Administrative task completion notes (move to a separate `CLAUDE_TASK_COMPLETION_LOG.md`)

**Do not prune yet.** Only after the index approach is validated and the operator confirms which entries are safe to consolidate.

---

## Risks of Any Pruning

| Risk | Mitigation |
|---|---|
| Losing intermediate debugging context | Prune only entries with a confirmed final addendum; keep debugging context in the final entry |
| Breaking heading anchor references | Search for `#heading-name` references in all docs before removing any heading |
| Losing date context | Always preserve the first date an entry appeared in the consolidated version |
| Confusing future Claude/Codex sessions | Add a "see archive" note at the top of any pruned section |

---

## Recommended Review Order

1. Operator reviews this proposal and approves the minimal first step (ToC index).
2. Claude/Codex adds the ToC index in a separate focused change.
3. Operator reviews the ToC index after a week of use.
4. If navigation is still painful, apply subsystem tags to new entries (Step 2).
5. Do not split the file until Step 1 and 2 are proven insufficient.

---

## Validation

After adding a ToC index:

```powershell
Select-String -Path Docs\REMEDIATION_CHANGELOG.md -Pattern "^## "
```

This should confirm all headings are still present and the ToC anchor names match the actual heading text.

---

## See Also

- Changelog file: `Docs/REMEDIATION_CHANGELOG.md`
- Stale docs audit: `Docs/archive/admin-audits/STALE_DOCS_TODO_AUDIT.md`
- Documentation index: `Docs/DOCS_INDEX.md`
