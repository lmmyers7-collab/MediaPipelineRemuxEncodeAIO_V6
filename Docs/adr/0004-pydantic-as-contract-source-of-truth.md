# 0004. Pydantic as contract source of truth

Status: accepted (partial — see Decision)
Date: 2026-05-28

## Context

Pipeline contracts live in three places today:

1. `Pipeline/MediaPipeline_config_chatgpt.psd1` — the authoritative
   PowerShell-side runtime config.
2. `DesktopApp/mediapipeline_desktop_app/config_schema.py` plus four
   sibling `config_schema_*.py` files — the Python representation,
   hand-maintained.
3. The WebView consumes a third representation as JSON over the API.

Stage payloads have a similar shape: 10 JSON schemas live in
`Pipeline/Schemas/`, hand-written, not generated from any Python source.
Their relationship to the runtime payloads is by convention only.

The plan's §Drift risks ranks
"PSD1 ↔ Python `config_schema*.py` ↔ WebView JSON" as the #1 drift risk.
Every shape change requires touching three files, and the only enforcer
is human review.

## Decision

**Pydantic v2 dataclasses** under `app/contracts/` are the single source
of truth for:

- Configuration shape (`app/contracts/config.py`).
- Pipeline stage payloads and results (`app/contracts/stages.py`).
- Manifest/event/command shapes added in later phases
  (`app/contracts/<name>.py`).

`schemas/<name>.v<n>.schema.json` is **generated** from the contracts
package by CI. The schemas committed under `Pipeline/Schemas/` are
migrated to the generated layout in Phase 4.

The "accepted (partial)" status reflects the current reality:

- `app/contracts/config.py` and `app/contracts/stages.py` exist
  (commit `77b8b4c`) and define the intended shape.
- They are currently stdlib `dataclasses`, not pydantic. The swap
  happens as part of Phase 2 (config) and Phase 4 (schema generation),
  by which point JSON Schema generation and runtime validation become
  automatic.
- `CONFIG_SCHEMA_VERSION` and `STAGE_SCHEMA_VERSION` constants already
  carry the version field on every payload.

Rules in force from today:

- New contract fields land in `app/contracts/` first. The PSD1 template
  and any WebView consumer are updated from there.
- The PSD1 stays as the *runtime* config file (operators edit it), but
  its *shape* derives from the pydantic model. A
  `psd1 ↔ pydantic` round-trip test (`tests/python/contract/test_config_roundtrip.py`,
  planned for Phase 2) asserts the round-trip is whitespace-only.
- `Pipeline/Schemas/*.json` is treated as legacy during transition; do
  not hand-edit it for new shapes after `schemas/` becomes the
  generated home.

## Consequences

Code and structure:

- One place to add a config or payload field.
- `command_payloads_*.py` validation collapses into pydantic
  `model_validate` calls (Phase 4).
- The five `config_schema*.py` files in
  `DesktopApp/mediapipeline_desktop_app/` are eventually deleted; their
  fields move into `app/contracts/config.py`.

Operational surface:

- API responses can validate against the generated schemas at the
  boundary (per `jsonschema`), catching contract drift at runtime
  rather than in a downstream consumer.
- Generated `docs/pipeline-contracts.md` describes the wire shape and
  cannot drift from the model.

Testing and CI:

- "Schema drift" CI job: regenerate `schemas/`, fail on diff.
- The round-trip test is the load-bearing gate for the PSD1
  transition.

Migration cost:

- Phase 2 (config) and Phase 4 (everything else). Each touches one
  contracts file at a time; existing call sites keep working until
  Phase 6 removes the shims.

Reversibility:

- Medium-low once schemas are generated. Reverting means rewriting the
  hand-maintained schemas, which is exactly the work this ADR avoids.

## Alternatives considered

**Marshmallow.** Mature, Python-native. Weaker JSON Schema generation
than pydantic v2, and pydantic's `model_validate` is more ergonomic at
the API boundary. Rejected.

**attrs + cattrs + hand-written schemas.** Cleaner data class
ergonomics but loses the auto-generated JSON Schema. The whole point
here is the generator. Rejected.

**TypedDict + runtime validator (e.g. typeguard).** Cheap, but no
schema generation and no `BaseModel`-level validators (cross-field
constraints, custom validators). Rejected.

**Generate the contracts *from* the PSD1.** Reverses the dependency.
PSD1 has no expression for unions, enums, validators, or version
fields; trying to be a source of truth for those would require an
adapter layer just as large as the pydantic model. Rejected.

## Validation

- `app/contracts/config.py` and `app/contracts/stages.py` already exist
  and define `CONFIG_SCHEMA_VERSION` / `STAGE_SCHEMA_VERSION`.
- `tests/python/contract/test_config_roundtrip.py` (Phase 2 — planned)
  asserts PSD1 → Config → PSD1 is whitespace-equivalent.
- `tests/python/contract/test_<stage>.py` (Phase 5 — planned) validates
  payload and result via the generated schemas.
- A CI step regenerates `schemas/` and fails on diff (Phase 4).
