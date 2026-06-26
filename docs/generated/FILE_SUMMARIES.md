# File summaries

This file explains `docs/generated/summaries/`. For the generated navigation
list, see `docs/generated/PROJECT_INDEX.md`.

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

1. Start with `AGENTS.md`, `docs/generated/PROJECT_INDEX.md`,
   `docs/architecture/ARCHITECTURE.md`, and `docs/generated/PIPELINE_MAP.md`.
2. Read the matching summary before editing a source file.
3. Open full source when the summary is high priority or the change requires
   details the summary does not expose.
4. Regenerate summaries after source edits.
5. Do not hand-edit generated per-file summaries.

## Pointers

- Generator: `src/mediapipeline/tools/dev/refresh_summaries.py`
- Summary root: `docs/generated/summaries/`
- Index: `docs/generated/PROJECT_INDEX.md`
- Dependency graph: `docs/generated/DEPENDENCY_GRAPH.md`
