# Claude Handoff: 20 Administrative V5 Transition Tasks

Repository:

`C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5`

Purpose:

This backlog gives Claude twenty low-dependency administrative tasks that support the V5 Tauri/WebView2 transition without changing runtime behavior. These tasks are intentionally documentation, inventory, runbook, checklist, and audit work. They should help Codex verify the project faster later, reduce operator confusion, and keep the migration organized.

## Global Rules For Claude

1. Do not touch V4.
2. Do not remove, freeze, weaken, or criticize-away the Tk fallback.
3. Do not change media policy, FFmpeg/ffprobe behavior, subtitle/audio handling, remux/encode routing, queue semantics, pending-publish behavior, rename mutation behavior, settings persistence, or process lifecycle code.
4. Do not add frontend-owned filesystem mutation.
5. Do not edit backend command contracts, command journal behavior, strict JSON handling, close-readiness checks, duplicate-command guards, or release gates.
6. Keep Network mode read-only in all wording unless documenting a future task.
7. Prefer creating or updating Markdown documents. Only touch tests or source code if a task explicitly asks for an inventory generated from them, and then only read them.
8. Do not run real media, FFmpeg, publish drains, rename apply, settings save, launch, audit, or rerun commands.
9. Keep each task independently reviewable.
10. At the end of each task, report files read, files changed, validation performed, and open questions.

## Preferred Output Style

For each completed task, Claude should produce a concise completion note:

```text
Task ID:
Files changed:
Files inspected:
Validation:
Findings:
Open questions:
Risk:
```

## Recommended Validation For Admin Tasks

Most tasks are documentation-only. Use the smallest relevant checks:

```powershell
Get-ChildItem Docs -Filter *.md
Select-String -Path Docs\*.md -Pattern "<term>"
python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke
```

Do not run the full desktop suite unless the task explicitly asks for a broad docs/package verification pass.

## Task Index

| ID | Title | Primary Output | Risk | Code Changes Allowed |
|---|---|---|---:|---:|
| C-ADM-001 | Documentation Index Consistency Audit | Updated docs index notes | Low | No |
| C-ADM-002 | Operator TLDR Freshness Pass | Updated TLDR wording | Low | No |
| C-ADM-003 | WebView Smoke Result Log Template | New smoke result template | Low | No |
| C-ADM-004 | Validation Ladder Runbook | New or updated validation runbook | Low | No |
| C-ADM-005 | Test Suite Inventory By Subsystem | New test inventory doc | Low | No |
| C-ADM-006 | Release Package Admin Inventory | New release inventory doc | Low | No |
| C-ADM-007 | Runtime Artifact Inventory | New state/log artifact map | Low | No |
| C-ADM-008 | Config Key Glossary Draft | New config glossary doc | Low | No |
| C-ADM-009 | Local API Evidence vs Mutation Matrix | Updated route/effect notes | Low | No |
| C-ADM-010 | Stale Docs/TODO Audit | New stale-docs audit | Low | No |
| C-ADM-011 | Version Label Administrative Audit | Update stale-version audit if needed | Low | No |
| C-ADM-012 | Browser Smoke Prerequisites Checklist | New browser smoke checklist | Low | No |
| C-ADM-013 | V5 Transition Status Board | New status board doc | Low | No |
| C-ADM-014 | Real-Media Validation Evidence Template | Updated validation template doc | Low | No |
| C-ADM-015 | Operator Glossary | New glossary doc | Low | No |
| C-ADM-016 | Migration Risk Register | New risk register doc | Low | No |
| C-ADM-017 | No-Touch Boundary Register | New boundary register doc | Low | No |
| C-ADM-018 | Packaging Dependency Inventory | New dependency inventory doc | Low | No |
| C-ADM-019 | Failure Triage Worksheet | New worksheet doc | Low | No |
| C-ADM-020 | Changelog Navigation / Pruning Proposal | New proposal doc | Low | No |

---

## C-ADM-001 - Documentation Index Consistency Audit

Goal:

Verify that `Docs\DOCS_INDEX.md` accurately points to the current V5 docs and does not describe completed, moved, or stale documents as active work.

Scope:

- Read `Docs\DOCS_INDEX.md`.
- Read only the first 40-80 lines of each referenced Markdown doc unless a mismatch requires more.
- Check whether each listed doc exists.
- Check whether each unlisted high-value doc in `Docs` should be added.

Deliverable:

- Either update `Docs\DOCS_INDEX.md`, or create `Docs\DOCS_INDEX_AUDIT_NOTES.md` if changes are uncertain.

Acceptance:

- Missing docs are listed.
- Duplicate/stale entries are called out.
- New admin handoff docs are discoverable.
- No runtime files are changed.

Validation:

```powershell
Get-ChildItem Docs -Filter *.md
Select-String -Path Docs\DOCS_INDEX.md -Pattern "CLAUDE_HANDOFF"
```

---

## C-ADM-002 - Operator TLDR Freshness Pass

Goal:

Make sure `Docs\TLDR.md` reflects current operator reality without becoming a long architecture document.

Scope:

- Review current launchers, smoke wrappers, WebView preview language, Diagnostics handoff wording, Rename status, Settings status, and release package behavior.
- Keep the TLDR short.
- Do not add claims that WebView is production replacement for Tk.

Deliverable:

- Updated `Docs\TLDR.md`.

Acceptance:

- Tk remains described as supported/default.
- Tauri/WebView2 remains described as preview.
- V4 remains backup.
- Diagnostics, Rename, Settings, Pending Publish, and WebView smoke language are current.

Validation:

```powershell
Select-String -Path Docs\TLDR.md -Pattern "Tk|Tauri|WebView|Diagnostics|Rename|Pending"
```

---

## C-ADM-003 - WebView Smoke Result Log Template

Goal:

Create a standard Markdown template for recording smoke test runs so operator validation evidence is consistent.

Scope:

- Cover browser-backed and non-browser smokes.
- Include environment, date/time, command, pass/fail, skipped reason, console errors, mutation boundary, and follow-up notes.
- Do not edit smoke wrappers.

Deliverable:

- New `Docs\WEBVIEW_SMOKE_RESULT_TEMPLATE.md`.

Acceptance:

- Template can be copied after any `Test-WebView*.ps1` run.
- Includes a section explicitly stating whether the smoke did or did not launch/process/publish/rename/save.
- Includes fields for Chrome/Edge availability and local API port.

Validation:

```powershell
Test-Path Docs\WEBVIEW_SMOKE_RESULT_TEMPLATE.md
```

---

## C-ADM-004 - Validation Ladder Runbook

Goal:

Create a clear "what to run when" validation ladder for future Codex/Claude work.

Scope:

- Organize commands by change type:
  - docs-only
  - WebView JS only
  - Local API/backend routes
  - settings/rename/pending publish commands
  - Tauri shell
  - release/package-facing changes
- Include expected runtime and skip conditions where known.

Deliverable:

- New `Docs\VALIDATION_LADDER_RUNBOOK.md`.

Acceptance:

- Makes it clear that full desktop suite and release self-test are not always required for docs-only work.
- Makes it clear that media-processing behavior needs targeted tests and real-media validation before trust.
- Uses bundled PowerShell 7 for release checks.

Validation:

```powershell
Select-String -Path Docs\VALIDATION_LADDER_RUNBOOK.md -Pattern "PowerShell-7.6.0|node --check|unittest|Release"
```

---

## C-ADM-005 - Test Suite Inventory By Subsystem

Goal:

Inventory the existing `DesktopApp\tests` suite so future work can quickly choose targeted tests.

Scope:

- Read test filenames and class/test names.
- Group by subsystem:
  - Local API
  - command journal/contracts
  - Queue
  - Completed
  - Pending Publish
  - Rename
  - Settings
  - Diagnostics
  - Tauri shell
  - WebView browser/non-browser smokes
  - network
  - process lifecycle
- Do not rewrite tests.

Deliverable:

- New `Docs\TEST_SUITE_SUBSYSTEM_INVENTORY.md`.

Acceptance:

- Each subsystem has recommended targeted commands.
- Gaps are framed as "coverage gaps", not as required immediate code changes.
- No tests are modified.

Validation:

```powershell
Get-ChildItem DesktopApp\tests -Filter test_*.py
```

---

## C-ADM-006 - Release Package Admin Inventory

Goal:

Document what a clean release package is expected to include and exclude.

Scope:

- Read `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`.
- Read `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`.
- Read current release docs.
- Do not change scripts.

Deliverable:

- New `Docs\RELEASE_PACKAGE_ADMIN_INVENTORY.md`.

Acceptance:

- Includes expected included launchers, docs, DesktopApp files, pipeline files, Tauri preview files, and smoke wrappers.
- Includes expected exclusions: live config, logs, state, caches, node_modules, Rust target, optional tool docs unless requested.
- Includes "private backup only" warning for `-KeepPersonalConfig`.

Validation:

```powershell
Select-String -Path Build-MediaPipelineRemuxEncodeAIO-Release.ps1,Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -Pattern "Exclude|KeepPersonalConfig|IncludeTests|node_modules|release_manifest"
```

---

## C-ADM-007 - Runtime Artifact Inventory

Goal:

Create a reference map of runtime files/folders operators and diagnostics panels discuss.

Scope:

- Inventory state/log artifacts from docs and code references:
  - `State`
  - `RunLogs`
  - `ActiveJobs`
  - queue snapshot
  - completed manifest
  - pending publish root
  - failure reports/markers
  - sample validation log
  - progress files
  - command journal
- Do not change code.

Deliverable:

- New `Docs\RUNTIME_ARTIFACT_INVENTORY.md`.

Acceptance:

- Each artifact lists owner, produced by, consumed by, safe to delete manually yes/no/unknown, and diagnostics target if any.
- Clearly says manual deletion of runtime state is unsafe unless a doc or app command says so.

Validation:

```powershell
Select-String -Path Docs\*.md -Pattern "ActiveJobs|RunLogs|pending publish|sample_validation_log|command journal"
```

---

## C-ADM-008 - Config Key Glossary Draft

Goal:

Create an operator-friendly glossary for major settings/config keys without changing schema.

Scope:

- Read `Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md`.
- Read settings docs and relevant WebView Settings wording.
- Focus on high-impact keys for source/output/scratch, remux/encode, subtitles, audio, pending publish, scheduling, and safety.

Deliverable:

- New `Docs\CONFIG_KEY_GLOSSARY_DRAFT.md`.

Acceptance:

- Each key or key group has a plain-language purpose and risk note.
- Mark raw/advanced keys clearly.
- Do not invent defaults unless current docs/code show them.

Validation:

```powershell
Select-String -Path Docs\SETTINGS_BUILDER_COVERAGE_MATRIX.md -Pattern "Raw|Builder|Source|Subtitle|Audio|Pending"
```

---

## C-ADM-009 - Local API Evidence vs Mutation Matrix

Goal:

Make route ownership easier to audit by separating read/evidence routes from mutation/command routes.

Scope:

- Read `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md`.
- Read Local API contract docs only as needed.
- Do not change route contracts.

Deliverable:

- Either update `Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md` with a concise evidence/mutation summary, or create `Docs\LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`.

Acceptance:

- Every route is classified as read-only, command/mutation, command/dry-run, shell-open, lifecycle, or settings persistence.
- Each command route includes "frontend cannot own this behavior" wording where appropriate.

Validation:

```powershell
Select-String -Path Docs\LOCAL_API_ROUTE_OWNERSHIP_MAP.md -Pattern "/api/"
```

---

## C-ADM-010 - Stale Docs/TODO Audit

Goal:

Find stale-looking docs, TODOs, FIXME notes, "V3/V4" drift, and obsolete checklist language.

Scope:

- Search Markdown, PowerShell comments, Python comments, and docs headers.
- Do not change code behavior.
- Do not delete docs.

Deliverable:

- New `Docs\STALE_DOCS_TODO_AUDIT.md`.

Acceptance:

- Findings are grouped:
  - stale and should update
  - historical and should remain
  - false positive
  - needs Codex/operator decision
- Include exact file paths and short reason.

Validation:

```powershell
Select-String -Path Docs\*.md,*.md,*.ps1,DesktopApp\**\*.py -Pattern "TODO|FIXME|V3|V4|obsolete|deprecated|old"
```

---

## C-ADM-011 - Version Label Administrative Audit

Goal:

Recheck visible version labels and docs after recent V5/Tauri work.

Scope:

- Read `Docs\STALE_VERSION_LABEL_AUDIT.md`.
- Search for visible `V3`, `V4`, `v4.000`, `V5`, `v5`.
- Do not update runtime labels unless explicitly told; this is audit/admin work.

Deliverable:

- Update `Docs\STALE_VERSION_LABEL_AUDIT.md` or create an addendum `Docs\STALE_VERSION_LABEL_AUDIT_2026_05_14_ADDENDUM.md`.

Acceptance:

- Classify visible UI labels separately from historical docs and backup references.
- Preserve V4 backup references as intentional.
- Flag only actual stale operator-facing labels.

Validation:

```powershell
Select-String -Path Docs\*.md,DesktopApp\**\*.py,DesktopApp\**\*.js,Pipeline\*.ps1,Pipeline\Modules\*.ps1 -Pattern "V3|V4|V5|v4|v5"
```

---

## C-ADM-012 - Browser Smoke Prerequisites Checklist

Goal:

Create a checklist for operators/developers to diagnose why browser-backed smokes skip or fail.

Scope:

- Read `Docs\BROWSER_SMOKE_TEST_RUNBOOK.md`.
- Read `SmokeTests/Test-WebViewBrowser*.ps1` wrappers.
- Do not change wrappers.

Deliverable:

- New `Docs\BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`.

Acceptance:

- Covers Chrome/Edge discovery, local API startup, token auth, ports, console error capture, CDP connection, skip vs fail interpretation, and non-mutation boundary.
- Includes a "when not to run" section.

Validation:

```powershell
Get-ChildItem -Filter Test-WebViewBrowser*.ps1
```

---

## C-ADM-013 - V5 Transition Status Board

Goal:

Create a single administrative status board for the transition.

Scope:

- Summarize major areas:
  - Tk fallback
  - local API
  - Tauri shell
  - WebView Home/Queue/Completed/Pending/Rename/Settings/Diagnostics/Network/Maintenance
  - release package
  - tests/smokes
  - real-media validation
- Use current docs as source.

Deliverable:

- New `Docs\V5_TRANSITION_STATUS_BOARD.md`.

Acceptance:

- Uses statuses like stable fallback, preview, partial parity, blocked, deferred, needs real-media validation.
- Does not claim Tauri/WebView is production replacement.
- Lists recommended next administrative and engineering tasks separately.

Validation:

```powershell
Select-String -Path Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md,Docs\TAURI_WEBVIEW_PARITY_MATRIX.md -Pattern "Partial|Strong|Tk|Tauri|real-media"
```

---

## C-ADM-014 - Real-Media Validation Evidence Template

Goal:

Improve the manual evidence template used when validating a real sample media run.

Scope:

- Read `Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`.
- Read sample validation artifact design.
- Do not change backend sample validation code.

Deliverable:

- Either update the playbook with a copyable evidence form, or create `Docs\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`.

Acceptance:

- Includes sample identity, source/output paths, Queue route, remux-vs-encode reason, FFmpeg stderr/log check, subtitle outcome, audio outcome, size growth, Completed proof, Pending Publish proof, Plex/direct-play observation, decision, and follow-up.
- Clearly says this is operator evidence, not automatic acceptance.

Validation:

```powershell
Select-String -Path Docs\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md -Pattern "Queue|Completed|Pending|subtitle|audio|size"
```

---

## C-ADM-015 - Operator Glossary

Goal:

Create a glossary for repeated operator-facing terms.

Scope:

- Terms should include:
  - backend-owned
  - mutation guardrail
  - read-only
  - pending publish
  - drain
  - parked output
  - sidecar
  - scratch
  - remux
  - encode
  - Direct Play
  - diagnostics target
  - command journal
  - close readiness
  - ActiveJobs
  - stale runtime state

Deliverable:

- New `Docs\OPERATOR_GLOSSARY.md`.

Acceptance:

- Plain-language definitions.
- Includes "why the operator should care".
- Does not overspecify implementation details.

Validation:

```powershell
Test-Path Docs\OPERATOR_GLOSSARY.md
```

---

## C-ADM-016 - Migration Risk Register

Goal:

Create an administrative risk register for the V5 transition.

Scope:

- Use current transition plan and parity matrix.
- Separate risks by category:
  - runtime/process safety
  - WebView parity
  - settings/config
  - diagnostics/operator trust
  - packaging/release
  - tests
  - real-media proof
  - over-fragmentation

Deliverable:

- New `Docs\V5_MIGRATION_RISK_REGISTER.md`.

Acceptance:

- Each risk has severity, current mitigation, owner area, next action, and "do not do" warning.
- Explicitly states Tk fallback and V4 backup reduce cutover risk.

Validation:

```powershell
Select-String -Path Docs\V5_TAURI_TRANSITION_CURRENT_PLAN.md -Pattern "risk|fallback|over-fragmentation|real-media"
```

---

## C-ADM-017 - No-Touch Boundary Register

Goal:

Create a concise document listing areas that should not be casually edited during admin or WebView parity work.

Scope:

- Include:
  - V4
  - Tk fallback
  - media policy
  - FFmpeg command generation
  - subtitle conversion
  - audio routing
  - pending-publish mutation
  - source deletion
  - scratch-copy invariants
  - command journal
  - close-readiness
  - strict JSON
  - Network lifecycle controls

Deliverable:

- New `Docs\NO_TOUCH_BOUNDARY_REGISTER.md`.

Acceptance:

- Each boundary explains why it matters and what review/test gate is required before touching it.
- Includes safe admin-only alternatives.

Validation:

```powershell
Test-Path Docs\NO_TOUCH_BOUNDARY_REGISTER.md
```

---

## C-ADM-018 - Packaging Dependency Inventory

Goal:

Inventory bundled and external dependencies relevant to package/admin work.

Scope:

- Include Python runtime expectations, bundled PowerShell, FFmpeg, MKVToolNix, PgsToSrt, Tauri prerequisites, Node/npm, Rust/Cargo, Chrome/Edge for browser smokes.
- Do not verify/install tools unless the task is explicitly expanded by Codex/operator.

Deliverable:

- New `Docs\PACKAGING_DEPENDENCY_INVENTORY.md`.

Acceptance:

- Each dependency has role, bundled/external status, expected path if bundled, checked by which script/test, and failure symptom.
- Includes note that browser smokes may skip if Chrome/Edge is unavailable.

Validation:

```powershell
Select-String -Path Docs\POWERSHELL_HOST_EXPECTATIONS.md,Docs\BROWSER_SMOKE_TEST_RUNBOOK.md,Docs\DEPLOYABILITY_CHECKLIST.md -Pattern "PowerShell|Node|Cargo|Chrome|FFmpeg|MKV"
```

---

## C-ADM-019 - Failure Triage Worksheet

Goal:

Create a copyable worksheet for diagnosing a failed or suspicious run without making changes.

Scope:

- Use existing Diagnostics, Queue, Completed, Pending Publish, and command history terminology.
- Keep it operator-focused.

Deliverable:

- New `Docs\FAILURE_TRIAGE_WORKSHEET.md`.

Acceptance:

- Sections:
  - what happened
  - current app state
  - source/output/scratch paths
  - Queue evidence
  - Completed evidence
  - Pending Publish evidence
  - Diagnostics tail/logs
  - command history
  - safe next action
  - actions not taken yet
- Explicitly says not to delete source/scratch/output or clear state until evidence is captured.

Validation:

```powershell
Test-Path Docs\FAILURE_TRIAGE_WORKSHEET.md
```

---

## C-ADM-020 - Changelog Navigation / Pruning Proposal

Goal:

`Docs\REMEDIATION_CHANGELOG.md` is very large. Create an administrative proposal for making it easier to navigate without deleting history.

Scope:

- Read beginning and headings of `Docs\REMEDIATION_CHANGELOG.md`.
- Do not prune or split it yet unless Codex/operator approves.

Deliverable:

- New `Docs\CHANGELOG_NAVIGATION_PROPOSAL.md`.

Acceptance:

- Proposes an index strategy, date anchors, subsystem tags, archive split criteria, and how to preserve old entries.
- Lists risks of splitting too aggressively.
- Includes a minimal first step that can be reviewed later.

Validation:

```powershell
Select-String -Path Docs\REMEDIATION_CHANGELOG.md -Pattern "^## "
```

---

## Final Claude Completion Bundle

After completing any subset of these tasks, Claude should provide:

1. Completed task IDs.
2. Files changed.
3. Files read.
4. Tests or commands run.
5. Tasks intentionally skipped.
6. Anything that needs Codex verification.
7. Any operator decisions needed.

Claude should not mark the Tauri/WebView2 transition complete. These are administrative support tasks only.

