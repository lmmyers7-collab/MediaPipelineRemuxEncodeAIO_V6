# Worker Review Instructions

Workers write only `workers/<worker-id>-<domain>.md`. Do not edit aggregate files.

## Required Per-File Workflow
1. Read the generated summary first if present at `docs/generated/summaries/<path>.md`.
2. Inventory all reviewable symbols for the language/file type.
3. Review assigned files only for correctness, safety boundaries, error handling, path/Windows/UNC behavior, contract/schema drift, command journaling, duplicate-command safety, media/source/scratch/output safety, pending-publish correctness, subtitle/audio preservation, frontend/backend ownership, and test quality.
4. Record `Reviewed: no findings` for files with no issue.
5. If coverage is partial, state exactly what was not reviewed and why.

## Finding Required Fields
- severity: P0, P1, P2, or P3
- file path
- line number or narrow symbol reference
- affected function/module
- problem
- impact
- evidence
- suggested fix direction
- suggested validation/tests

## Worker Markdown Template

```markdown
# Worker Review: <worker-id>

## Scope
- Assigned domain:
- Assigned files:
- Explicit exclusions:

## Coverage Ledger

| File | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|

## Detailed Findings

### <ID>: <short title>
- Severity:
- File:
- Symbol:
- Evidence:
- Impact:
- Suggested fix:
- Suggested tests:

## Test Coverage Gaps

## Boundary Risks

## Files With No Findings

## Incomplete Coverage
```

## Assignment Source
Use `../ASSIGNMENTS.md`; it is generated from `docs/generated/PROJECT_INDEX.md` on 2026-06-11.
