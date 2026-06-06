# CLAUDE.md — Operating instructions for Claude Code

Last updated: 2026-05-28
Platform: Windows; paths use backslashes; use bundled Python unless AGENTS.md says otherwise
Policy precedence: AGENTS.md > docs/SESSION.md > CLAUDE.md > inline comments
Operator chat: selects the task and may grant current-turn scope approvals only where higher-precedence files
allow
On missing infrastructure files: ask; do not recreate by hand; run documented regeneration scripts only if the
operator chooses that option
On Ollama unavailable: flag the first fallback in chat immediately; batch subsequent fallbacks in §8

This file is an operating manual for Claude Code, not the project architecture record. AGENTS.md owns project
rules, source-of-truth documents, boundaries, and high-risk areas. docs/SESSION.md owns the current branch/session
scope and overrides this file where they disagree.

If this file conflicts with AGENTS.md, AGENTS.md wins. If docs/SESSION.md conflicts with this file on scope,
docs/SESSION.md wins. Operator chat can narrow a task, approve extra paths for the current turn, or choose among
options allowed here; it cannot permanently override AGENTS.md, create standing policy, or authorize
prohibited edits unless AGENTS.md explicitly allows that override. Flag any drift from AGENTS.md immediately
and again in the handoff.

## 1. Session startup

Do this before non-trivial repository work. For read-only questions or tiny single-file fixes, perform the
minimum startup needed to avoid violating AGENTS.md and docs/SESSION.md, then proceed with a named caveat.

1. Read **AGENTS.md** — §§1–3 and §7 in full; skim the rest. §7 changes most often; never skim it.
2. Read **PROJECT_INDEX.md**. If missing, ask whether to regenerate via `python -m mediapipeline.tools.dev.generate_project_index`,
   proceed degraded with a named caveat, or abort. Do not reconstruct it by reading source files.
3. Read **docs/SESSION.md**. If absent, read-only answers, repository discovery, and tiny single-file typo/comment
   fixes may proceed degraded; any non-trivial edit, refactor, migration, validation-sensitive task, or
   multi-file task requires a docs/SESSION.md or explicit operator approval first.
4. Read **docs/audit/latest.md** if present. Treat findings as known issues. If front-matter is older than 7
   days, flag it and treat findings as advisory. If absent, proceed and note it.
5. Do **not** read unless the task explicitly requires it: `ARCHITECTURAL_OVERHAUL_PLAN.md`,
   `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `AI_HANDOFF.md`, `MONOLITH_SPLIT_PLAN.md`, or
   `md_documentation_audit*`. Items marked never in AGENTS.md remain never.

AGENTS.md absence is a hard stop for editing, validation, and any task that relies on project rules. Missing
PROJECT_INDEX.md, docs/SESSION.md, or docs/audit/latest.md permits degraded mode only as described above or if the
operator confirms.

After startup: answer read-only questions directly with citations; for tiny edits that qualify for §3 skip
rules, state scope and proceed; for non-trivial work, summarize task, in-scope files, and Ollama artifacts in
three lines, then wait for confirmation before editing.

## 2. Scope discipline

AGENTS.md is authoritative. The list below is a quick reference; if it disagrees with AGENTS.md, follow
AGENTS.md and flag drift.

- Never edit a file not listed in docs/SESSION.md without explicit current-turn operator approval naming the file,
  directory, glob, or clearly bounded area.
- Operator approval can expand the current turn's editable scope only where AGENTS.md allows; it does not
  rewrite AGENTS.md, docs/SESSION.md, or this file.
- Never touch AGENTS.md §7 high-risk areas unless docs/SESSION.md names them explicitly and the operator has
  acknowledged the validation rung from AGENTS.md §5.
- Never create banned files: `DesktopApp/**/facade_*.py`, `DesktopApp/**/service_*.py`,
  `DesktopApp/**/command_payloads_*.py`, `Pipeline/Modules/*.*.ps1`, root `*_REPORT.md`, root `*_FIXES.md`,
  root `*_CHECKLIST.md`, or any new top-level `*.md` not in AGENTS.md §2.
- Do not create status, review, audit, handoff, or planning Markdown files as a workaround. Put notes in
  docs/SESSION.md or an approved SSOT document.
- Never commit or push. Stage files only when explicitly asked.
- Never delete, overwrite, rename, or move source media unless AGENTS.md and the current operator instruction
  both explicitly authorize that exact operation.
- Never modify source files in `V5/`, `LocalBase/`, `node_modules/`, or `docs/archive/`.

A domain is a top-level directory named in AGENTS.md §2, such as `Pipeline/`, `ui_web/`, `DesktopApp/`,
`ops/pipeline/engine/`, or `app/`. If the next edit would touch a directory outside the current docs/SESSION.md domain set, stop
and ask. Read-only discovery may cross domains when needed, but prefer PROJECT_INDEX.md, summaries, Glob, and
Grep before opening source.

Migration exception: when docs/SESSION.md explicitly names V6 migration work, `DesktopApp/` ↔ `app/` and
`Pipeline/Modules/` ↔ `ops/pipeline/engine/` are each one domain pair for that session. Outside migration sessions, they
are separate domains. If a task requires violating scope, stop, describe the conflict, and propose two
in-scope alternatives.

## 3. Plan before code

For non-trivial work, produce a short written plan and wait for operator approval before editing.

Planning is required when a change touches more than one file; targets a file over 200 lines; is expected to
exceed 50 changed lines; creates, deletes, moves, or renames files; touches AGENTS.md §7; changes contracts,
settings schema, command journal, pending-publish, queue behavior, media identity, destructive operations, or
migration mapping; or is a refactor rather than a direct fix.

A plan must name the objective, exact files, likely functions/sections, out-of-scope files, Ollama use,
validation to run, and validation rung per AGENTS.md §5.

Skip the plan only for single-file edits under 50 changed lines, pure docstring/comment/typo changes, or a
direct fix for a specific pasted error. Even then, stay within docs/SESSION.md scope.

## 4. Local Ollama delegation

Ollama runs at `http://localhost:11434`. Available models: `qwen2.5-coder:32b` for reviewable code generation;
`qwen2.5-coder:14b` for summaries and mid-size drafts; `qwen2.5:14b` for long-context reads;
`qwen2.5-coder:3b` for commit messages, rename suggestions, and tiny utilities.

Check availability with PowerShell: `try { Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -Method
Get } catch { Write-Output 'OLLAMA_UNAVAILABLE' }`

If Ollama is unreachable or the requested model is missing, do the work yourself, flag the first fallback in
chat, and batch later fallbacks in §8. Do not silently switch models, pull models, or change the model list.
Ollama output is advisory; review it, apply only what you understand, and never paste it unreviewed.

Delegate only when all hold: the task is mechanical; context fits in one file or one file plus direct imports;
expected diff is under 100 lines; target is not AGENTS.md §7; target is under `app/`, `ops/pipeline/engine/`, `docs/generated/summaries/`,
`docs/`, or `ops/scripts/smoke/`; prompt does not require secrets, credentials, private media contents, or
unnecessary absolute source-media paths.

Do not delegate when any hold: the task touches AGENTS.md §7; requires reading more than three files to
decide; involves V6 migration mapping; changes contracts, settings schema, command journal, pending-publish,
queue behavior, concurrency, destructive media operations, or path identity; asks whether something is safe;
or the operator says "use Claude directly" or "no Ollama".

Cached artifacts: use `docs/generated/summaries/<mirror-of-source-path>.md`, PROJECT_INDEX.md, and docs/audit/latest.md as
first-pass indexes. Read summaries first, especially `token_priority: high` summaries. If a summary is stale,
incomplete, or insufficient for a safe edit, flag it and read source. If regeneration scripts are missing,
tell the operator; do not create replacements.

## 5. Token economy

- One edit domain per session. Do not mix `Pipeline/` PowerShell work with `ui_web/` JavaScript work unless
  docs/SESSION.md explicitly scopes both.
- Glob and Grep before Read. Never read a file just to learn whether a symbol exists.
- Read summaries before source. Open source only for exact behavior, exact line citations, or edits.
- Use discovery subagents for path/line facts, not decisions. For broad discovery, prefer Claude Code
  subagents or search tools over Ollama unless §4 allows Ollama.
- Compact after planning, after a green test run, and after completing a sub-task. Re-read docs/SESSION.md after
  every compact.
- Per-task input budget is about 35K tokens, roughly 130 KB. If approaching the cap, stop and propose a split.
- Do not paste large code blocks unless asked; reference `path/to/file:line-range` instead.
- Do not opportunistically refactor. Leave adjacent cleanup for a new docs/SESSION.md unless required for the
  approved task.

## 6. Validation

Use the smallest safe validation rung from AGENTS.md §5.

- For AGENTS.md §7 areas, do not self-declare completion. Run agent-side validation only if AGENTS.md
  explicitly permits it; otherwise tell the operator exactly what to run and wait for confirmation.
- For all other changes, run validation before declaring the task complete.
- Use `apps\desktop\runtime\Python\python.exe`, never system Python, unless AGENTS.md specifies a different
  project-owned tool.
- Record validation command and result in the final response or §8 handoff.
- If validation fails, do not broaden the edit. Apply only a direct fix already allowed by the approved plan;
  otherwise stop, report, and ask for the next scope decision.

## 7. Communication style

- Lead with the decision or blocker, then the reasoning.
- No emojis in code, docs, commits, or chat, per AGENTS.md §8.
- Use ISO-8601 dates in saved notes, for example `2026-05-28`; never write "today" or "yesterday" in saved
  notes.
- Cite `path/to/file:line-range` when discussing existing code. Quote at most one line inline; summarize
  longer behavior.
- Distinguish "I changed" from "I propose to change" whenever mentioning edits.
- Ask focused questions when uncertain, but give any safe partial answer first.
- Do not bury blockers, and do not claim completion until scope, edits, validation, and handoff requirements
  are satisfied.

## 8. End-of-session protocol

Run this proactively when context drops below about 20K tokens, any tool response exceeds about 10K tokens,
the operator signals interruption/usage-limit/compact, or docs/SESSION.md exit criteria are met.

Write the summary into docs/SESSION.md under `## Handoff <YYYY-MM-DD>` unless AGENTS.md says otherwise. docs/SESSION.md
is always in scope for current-session handoff notes. If docs/SESSION.md is absent, provide the handoff in chat and
do not create docs/SESSION.md unless asked.

Before close, produce: modified files with one-line change summaries; every Ollama invocation and fallback;
anything learned that should update AGENTS.md, PROJECT_INDEX.md, docs/audit/latest.md, or a summary; AGENTS.md
§7 drift; whether exit criteria were met; validation commands/results or exact operator-run validation still
required.

## 9. Media pipeline safety

If AGENTS.md has stricter or more specific media-pipeline rules, AGENTS.md wins.

- Treat source media, derived media, pending-publish state, queue state, sidecars, command journals, settings
  schemas, and publish/drain scripts as high-risk unless AGENTS.md clearly says otherwise.
- Do not run destructive scripts, drain queues, publish media, delete files, rewrite sidecars, or normalize
  media paths without explicit current-turn approval and the validation rung required by AGENTS.md.
- Preserve media identity. Do not change path casing, relative/absolute path behavior, filename normalization,
  hash logic, timestamp logic, or duplicate-detection behavior as incidental cleanup.
- Do not invent replacement media, fixtures, or sample assets in source-media locations. Use existing test
  fixtures or an approved temporary location.
- Test media behavior with dry-run, fixture, or smoke-test paths before touching real pipeline state.
