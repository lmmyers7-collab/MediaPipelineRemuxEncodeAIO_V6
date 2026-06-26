# Copilot Instructions

Use `AGENTS.md` as the authoritative operating contract for this repository.
Before editing, read the active docs named there, especially
`docs/DOCS_INDEX.md`, `docs/architecture/ARCHITECTURE.md`,
`docs/architecture/MODULE_MAP.md`, and the generated summary for any source file
you open.

Core rules:

- Do not mutate source media. Source files may be read, probed, or copied to
  scratch only through existing backend/pipeline flows.
- Backend services and the PowerShell engine own mutation, media policy,
  queue state, settings persistence, pending-publish drain, rename apply,
  process lifecycle, and evidence.
- WebView and Tauri surfaces display backend-authored state and call backend
  routes; they must not implement independent filesystem or media policy.
- Strict JSON confirmations such as `confirm_save`, `confirm_apply`,
  `confirm_promote`, and lifecycle confirmations must remain literal booleans.
- Command journal, duplicate-command guards, and close-readiness are
  release-critical.
- Every meaningful code, docs, tooling, schema, test, config, or UI change
  needs an unreleased change packet under `ops/release/changes/unreleased/`.

For bug fixing:

- Prefer focused fixes over broad refactors.
- Use generated maps and summaries before opening large source files.
- Keep unrelated dirty worktree changes intact.
- Record validation evidence in the change packet.
- Use GitHub Issues for triaged, actionable work. Do not auto-create large
  issue batches from scanners; Code Scanning and Dependabot remain the primary
  alert stores.
- When using GitHub MCP, prefer repository, issue, pull request, code scanning,
  and workflow read tools first. Use write tools only for explicitly requested
  labels, comments, branches, issues, or pull requests.

Validation defaults:

- `.github` or tooling changes: validate config syntax, run the audit-spine
  checker, and run change-packet validation.
- Backend route or command changes: run targeted unit tests plus the matching
  command-journal/strict-JSON checks.
- WebView changes: run WebView static checks and affected smokes.
- Tauri changes: run the Tauri check path.
- PowerShell/media-policy changes: read the no-touch boundary register and use
  the validation ladder; real-media validation may be required.
