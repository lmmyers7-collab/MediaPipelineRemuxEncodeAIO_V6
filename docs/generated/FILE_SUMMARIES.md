# File summaries

This file explains the generated navigation surfaces and their bounded MCP/CLI
entry points. The full `docs/generated/PROJECT_INDEX.md` is a query aid, not an
ordinary startup read.

## Active source roots

One Markdown summary is generated per source file from these active roots:

- `src/mediapipeline/core/`
- `src/mediapipeline/contracts/`
- `src/mediapipeline/desktop/`
- `src/mediapipeline/pipeline/`
- `src/mediapipeline/tools/`
- `apps/desktop/webview/static/`
- `apps/desktop/tauri/src-tauri/src/`
- `ops/pipeline/engine/`
- `ops/pipeline/entrypoints/`
- `ops/pipeline/config/`
- `ops/pipeline/tests/`
- `ops/scripts/`
- `tests/`

The generator also keeps explicitly registered source files such as
`ops/pipeline/entrypoints/MediaPipeline.ps1`,
`ops/pipeline/entrypoints/Audit-MediaLibrary.ps1`,
`ops/pipeline/entrypoints/Setup-MediaPipeline.ps1`,
`ops/pipeline/config/MediaPipeline_config_template.psd1`,
`src/mediapipeline/pipeline/ass_to_srt_cli.py`, and the schema files under
`src/mediapipeline/contracts/schemas/`.

Each summary mirrors the source path:

```text
src/mediapipeline/core/publish/pending_manifest.py
  -> docs/generated/summaries/src/mediapipeline/core/publish/pending_manifest.py.md
src/mediapipeline/pipeline/ass_to_srt/text.py
  -> docs/generated/summaries/src/mediapipeline/pipeline/ass_to_srt/text.py.md
apps/desktop/webview/static/assets/app.js
  -> docs/generated/summaries/apps/desktop/webview/static/assets/app.js.md
ops/pipeline/engine/publish/pending_push.ps1
  -> docs/generated/summaries/ops/pipeline/engine/publish/pending_push.ps1.md
ops/scripts/dev/webview-public-contract.mjs
  -> docs/generated/summaries/ops/scripts/dev/webview-public-contract.mjs.md
```

## Summary format

Each summary has YAML frontmatter plus a compact body:

```markdown
---
file: src/mediapipeline/core/publish/pending_drain.py
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
sha256: <hex>
---
# `src/mediapipeline/core/publish/pending_drain.py`

**Purpose:** one sentence from the module docstring or parser.
```

The `sha256` field is the SHA-256 of the source file when the summary was
written. If a source file changes without regeneration, `--check` reports the
summary as stale.

## Commands

Regenerate summaries after source edits:

```powershell
python -m mediapipeline.tools.dev.refresh_summaries --changed
```

Regenerate the full set and prune orphan summaries after a layout migration:

```powershell
python -m mediapipeline.tools.dev.refresh_summaries --all --prune-orphans
```

Verify freshness:

```powershell
python -m mediapipeline.tools.dev.refresh_summaries --check
```

## Rules for AI sessions

1. Read `AGENTS.md`, then call the `mediapipeline-code` MCP `repo_context` tool
   with the actual task and default 2,000-token budget.
2. Use `code_lookup` for ownership/relationships, `code_bundle` for several
   budgeted source ranges, `code_read` for one exact range, and `code_search`
   only for precise or low-confidence follow-up.
3. If MCP is unavailable, use `context_slice --task "<task>" --budget 2000`.
4. Read the matching summary before editing a source file.
5. Open full source when the summary is high priority or the change requires
   details the summary does not expose.
6. Regenerate summaries after source edits.
7. Do not hand-edit generated per-file summaries.

## Local code-context MCP

The MCP server is read-only. It atomically reloads valid `PROJECT_INDEX.jsonl`
revisions, retains the last valid snapshot after a bad reload, reports stale
returned records without regenerating them, searches current tracked and
untracked active files, and caps every source read.

| Tool | Use |
| --- | --- |
| `repo_context` | Task-ranked implementation slice; default 2,000 tokens |
| `code_lookup` | Catalog ownership, symbols, dependencies, tests, and validation |
| `code_search` | Bounded live literal/regex text search |
| `code_read` | UTF-8 source ranges capped at 400 lines and 64 KiB |
| `code_bundle` | Up to eight source ranges under one shared 800–8,000-token budget |

Run the versioned 48-case retrieval and latency benchmark:

```powershell
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.code_context_benchmark --check
```

Preview or apply setup for both installed clients:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -File .\ops\scripts\dev\setup-code-context-mcp.ps1
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -File .\ops\scripts\dev\setup-code-context-mcp.ps1 -Apply
```

The apply path creates an isolated environment below
`LocalBase/Tooling/code-context-mcp/` and registers `mediapipeline-code` in the
Codex user configuration and Claude local project configuration. It refuses to
replace a different same-named registration unless `-Replace` is supplied.

Remove matching registrations without deleting the environment:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -File .\ops\scripts\dev\setup-code-context-mcp.ps1 -Remove
```

The server denies repository escapes, local state, bundled runtimes/tools,
personal config, credentials, and binary files. Generated evidence, archives,
and release packets are excluded from broad search but may be read or searched
through an explicit path. It has no write, shell-command, network, prompt, or
resource surface.

## Pointers

- Generator: `src/mediapipeline/tools/dev/refresh_summaries.py`
- Summary root: `docs/generated/summaries/`
- Index: `docs/generated/PROJECT_INDEX.md`
- Dependency graph: `docs/generated/DEPENDENCY_GRAPH.md`
