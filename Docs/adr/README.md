# Architecture Decision Records

This directory holds the canonical, immutable-once-accepted record of
architectural decisions for MediaPipelineRemuxEncodeAIO V6 → V7.

Format: [MADR](https://adr.github.io/madr/) (see `0000-template.md`).

## Why ADRs

`Docs/CURRENT_PROJECT_STATE.md` and
`Docs/architecture/ARCHITECTURE.md` describe the current operating
state. ADRs are the *decisions*. They are written once, accepted (or
rejected), and only superseded by a later ADR — never silently edited.

If you find yourself wanting to "update" an ADR, write a new one with
`Status: supersedes NNNN` and set the old one's status to
`superseded by MMMM`.

## Numbering

| Number | Status                 | Title                                                  |
| ------ | ---------------------- | ------------------------------------------------------ |
| 0000   | template               | MADR template                                          |
| 0001   | accepted               | Folder-by-domain layout                                |
| 0002   | accepted               | Python orchestrates, PowerShell executes               |
| 0003   | proposed               | SQLite as state store                                  |
| 0004   | accepted (partial)     | Pydantic as contract source of truth                   |
| 0005   | proposed               | Structured JSON logging                                |
| 0006   | accepted               | Local API as the only operator surface                 |
| 0007   | deferred               | WebView framework choice (vanilla vs Lit/Preact)       |
| 0008   | accepted               | Tauri / WebView2 as the shell                          |
| 0009   | accepted               | One canonical CHANGELOG; PR descriptions are not docs  |
| 0010   | historical             | Monolith-split campaign (V5 → V6 facade/service split) |
| 0011   | historical             | V5 → V6 split (WebView-first carve-out from V5)        |

ADR-0011 was written from `V6_SPLIT_NOTES.md` (the original repo-root
source notes, dated 2026-05-20). The source was archived in the same
commit to `Docs/archive/v6-split-notes-2026-05-20.md` so the per-feature
validation detail survives; ADR-0011 itself is the short, immutable
record.

## Rules

1. Once a status reaches `accepted`, do not edit the ADR body. Write a new
   numbered ADR that supersedes it.
2. ADRs are markdown only. No HTML, no diagrams that require external
   tooling. Mermaid in fenced blocks is allowed.
3. Each ADR is self-contained: the `Context` section must let a reader
   understand the decision without reading the rest of the repository.
4. ADRs should be 1-3 pages. Anything longer is usually two ADRs.
5. The `Validation` block (when present) names a contract test or smoke
   that proves the ADR is in force.

## Conventions

- File name: `NNNN-short-slug.md`. `NNNN` is zero-padded to four digits.
- Slug is lowercase kebab-case; no `_chatgpt`, `_v2`, `_new` suffixes.
- Date format: `YYYY-MM-DD`.
- Author: omit. `git log` is authoritative for authorship.

## Where ADRs are referenced from

- `AGENTS.md §10` points new agents here.
- `Docs/architecture/ARCHITECTURE.md` cites the ADRs that establish each
  module boundary.
- `Docs/CURRENT_PROJECT_STATE.md` and `CHANGELOG.md` record how accepted
  decisions have been applied in the promoted V6 workspace.
- `CHANGELOG.md` notes the ADR number alongside the commit that landed an
  ADR-backed change.

## How to add a new ADR

1. Copy `0000-template.md` to `NNNN-short-slug.md` (next available NNNN).
2. Fill in `Context`, `Decision`, `Consequences`, `Alternatives
   considered`. If the decision changes runtime behavior, add a
   `Validation` block.
3. Set `Status: proposed`. Open the PR. Convert to `accepted` only after
   merge.
4. Add the entry to the table above. Update any referencing doc
   (`Docs/architecture/ARCHITECTURE.md`, `AGENTS.md`) in the same PR.
