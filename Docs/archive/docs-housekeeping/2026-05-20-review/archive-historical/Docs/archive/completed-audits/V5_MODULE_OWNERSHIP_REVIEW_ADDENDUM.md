# V5 Module Ownership Review Addendum

Purpose: document the current module structure of the desktop app Python package, identify where fragmentation has grown beyond what the codebase complexity justifies, and note what is working well. This is an advisory addendum — it does not recommend any immediate refactoring and does not describe planned changes.

All counts are approximate and based on the V5 state as audited.

---

## Module Inventory

| Location | File count | Role |
|---|---|---|
| `DesktopApp/mediapipeline_desktop_app/` (top-level) | ~120 | Service layer (`service_*.py`), models, UI components, config schemas, app entry points |
| `application/` | ~65 | Application facade layer (mixins, policies, DTOs) |
| `api/` | ~31 | HTTP API layer (contracts, payload handlers, route dispatch, server) |
| `controllers/` | ~48 | CustomTkinter UI event handler controllers |
| `views/` | ~14 | CustomTkinter UI views |
| `network/` | ~29 | Coordinator/worker dispatcher, protocol, state, auth |
| `contracts/` | ~10 | Data contracts |

**Total Python files in the package: ~317**

---

## What Is Working Well

### Clean separation between layers

The four main layers — API (`api/`), application facade (`application/`), service (`service_*.py`), and UI (`controllers/`, `views/`) — have clear one-directional dependencies. The API layer calls the facade; the facade calls services; the UI calls the facade. No circular dependencies between layers were detected.

### Facade pattern isolates business logic from UI framework

`application/facade.py` aggregates all business operations into one object that the API and UI both use. Switching the UI framework from CustomTkinter to a different frontend does not require touching the service or application layers. This pattern is correct and should be preserved.

### DTO serialization boundaries

The DTO classes in `application/dto*.py` provide typed serialization boundaries between the facade and the API layer. All API responses are derived from DTOs, not from raw service output. This prevents shape leakage and makes response schemas stable.

### No circular imports detected

Despite ~527 relative imports across 199 files, no circular import chains were found. The facade imports 30 mixin files but each mixin has isolated imports.

### Public interfaces are minimal and explicit

- `api/__init__.py` exports 3 items
- `application/__init__.py` exports 18 items (facade + DTOs)
- `__init__.py` at package root has minimal version constants

---

## Fragmentation Concerns

### 1. `service_*.py` explosion at top level (~95 files)

The service layer is spread across ~95 files named `service_<domain>_<variant>.py`. Within each domain (rename, queue, config, status, etc.) there are 5–12 files covering utilities, policies, discovery, planning, apply, and runner phases.

**Concern**: The pattern creates a flat namespace where `service_rename_tv.py`, `service_rename_movie.py`, `service_rename_plan_policy.py`, `service_rename_planner.py`, `service_rename_discovery.py`, `service_rename_apply.py`, `service_rename_apply_runner.py`, and `service_rename_preview_runner.py` are all siblings rather than members of a `service_rename/` submodule.

**Impact**: New contributors must learn 8+ filenames to understand the rename service scope. A typo in an import silently targets the wrong sibling. IDE navigation requires knowing file prefixes rather than following a package hierarchy.

**Mitigation that does not require moving files**: Document the domain groupings explicitly (see the table below). Moving to submodules is a significant refactor with import-chain risk and should not be done until V5 is stable.

### 2. Facade mixin pattern (30 imports in `facade.py`)

`application/facade.py` imports 30 separate mixin modules, each contributing a few methods to the facade class. Each mixin has a paired `_policy.py` file with the business logic it delegates to.

**Concern**: 30 mixin imports plus 18 policy files equals 48 files to trace when debugging a single facade operation. The mixin-plus-policy split is consistent but adds a mandatory two-file lookup for any behavior change.

**Impact**: Adding a new facade capability requires creating two files (mixin + policy) even for a two-method operation.

**Mitigation**: The pattern is consistent and the separation is justified for complex domains (rename, pending publish, settings). For simpler domains (sample validation, maintenance), the mixin and policy could be co-located without loss of clarity.

### 3. Single-line command payload mixin files in `api/`

Seven files in `api/` contain only a class definition with `pass` (or a class that is assembled elsewhere):

- `command_payloads_maintenance.py`
- `command_payloads_process.py`
- `command_payloads_files.py`
- `command_payloads_sample_validation.py`
- `command_payloads_settings.py`
- `command_payloads_policy.py`
- `command_payloads_rename.py` (12 lines — 2 methods)

These exist as separate files to support the mixin aggregation pattern in `command_payloads.py`, but each file's content could be inlined into `command_payloads.py` without loss of clarity.

**Impact**: Low immediate harm; adds cognitive overhead when tracing which file owns a given POST route's payload handler.

**Recommendation**: When any of these files grows to contain 3+ methods, consider keeping it separate. If it remains 1–2 methods, consolidation into `command_payloads.py` is warranted at the next convenient refactor opportunity.

### 4. Ultra-small contract files

- `contract_shared.py` (5 lines — one constant)
- `contract_payload.py` (2 lines — one re-export)

Both could be inlined into `contract.py` or the relevant consumer without loss of clarity. Their existence is not harmful, but they add module lookup steps for no structural reason.

### 5. Controller proliferation (~48 files in `controllers/`)

Each Tk UI feature has a dedicated controller file. For complex features (queue, settings, launch) this is appropriate — these files are genuinely large and the separation prevents a monolithic controller module. For simpler features with fewer event handlers, the granularity is higher than needed.

**Impact**: Low — the controller layer is UI-owned and will shrink relative to the WebView over time as V5 matures. The Tk controllers are not performance-critical and their proliferation does not affect API stability or backend correctness.

---

## Service Layer Domain Map

The 95 `service_*.py` files at the top level form these logical domains:

| Domain | Files | Key responsibility |
|---|---|---|
| Config | `service_config*.py` (~8) | Config loading, key resolution, schema validation |
| Status | `service_status*.py` (~11) | Pipeline state, active jobs, progress, events |
| Telemetry | `service_telemetry*.py` (~4) | CPU/RAM/GPU sampling |
| Process | `service_process_*.py` (~18) | Launch, launch environment, retry, control flags |
| Queue | `service_queue*.py` (~7) | Queue scan, planning, route decisions, exclusion |
| Rename | `service_rename*.py` (~12) | TV/movie name parsing, planning, apply, preview, discovery |
| Completed | `service_completed*.py` (~3) | Manifest reading, consistency checks |
| Pending publish | `service_pending_publish*.py` (~5) | Manifest parsing, path resolution, recovery |
| Audit | `service_audit*.py` (~7) | Library audit, CSV output, priority marking |
| Folder policy | `service_folder_policy*.py` (~4) | Source/output/scratch folder validation |
| Path / file | `service_path*.py`, `service_file*.py` (~8) | Path normalization, file probing |
| Utilities | `service_utils.py`, `service_constants.py`, others (~5) | Shared utilities and constants |

When adding a new file to the service layer, place it in the appropriate domain and follow the existing naming convention for that domain.

---

## Over-Fragmentation Risk Assessment

| Area | Risk | Priority |
|---|---|---|
| `command_payloads_*.py` single-method files | Low — can consolidate opportunistically | Low |
| `contract_shared.py` / `contract_payload.py` ultra-small files | Low — cosmetic only | Low |
| Facade mixin + policy pairs for simple domains | Medium — two-file lookup overhead | Medium (next refactor cycle) |
| `service_*.py` flat namespace | Low short-term; grows with each new service | Medium (when adding submodules is feasible) |
| Controller proliferation | Low — shrinks with WebView maturity | Low |

---

## What NOT To Do

- Do not consolidate modules during a V5 preview stabilization pass. Module moves change import paths, break test discovery, and risk introducing circular imports.
- Do not merge the facade mixin files into one large facade.py. The mixin pattern's value is keeping the facade namespace readable; consolidation would create a 2000+ line file.
- Do not move `service_*.py` into submodules without a coordinated import-chain audit. The flat namespace is a known cost; the migration is a separate workstream.

---

## See Also

- Facade public interface: `DesktopApp/mediapipeline_desktop_app/application/__init__.py`
- API contracts: `DesktopApp/mediapipeline_desktop_app/api/contract_read.py`, `contract_command.py`
- Route ownership: `Docs/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- Settings coverage: `Docs/SETTINGS_BUILDER_COVERAGE_MATRIX.md`
