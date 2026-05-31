# Deployment Verification and One-Click Setup System

**Purpose:** This document is a technical planning and architecture brief for turning a complicated tool into a reliable, self-verifying, one-click setup experience.

**Primary objective:** A user should be able to start the tool, follow a guided process, and reach a verified working state in about five minutes without reading a README, manually editing config files, using a terminal, or asking an AI to fix broken setup.

**Working app name:** `MediaPipelineRemuxEncodeAIO V6` is the current promoted product name. The Python package exposes `APP_NAME = "MediaPipelineRemuxEncodeAIO"` with product version `v6.000`, and the Tauri shell declares `productName = "MediaPipelineRemuxEncodeAIO V6"`.

**Important note for future Codex work:** This document intentionally avoids assuming final class names, file names, module names, or repository layout. Codex should discover existing architecture, preserve useful current components, and map the concepts below onto the actual codebase.

**Current V6 implementation scope:** For `MediaPipelineRemuxEncodeAIO V6`, this document is a planning guide for a Windows-first deployment verifier layered over the existing backend-owned pipeline. It must not create a parallel media-policy authority, parallel config system, root launcher shim, direct frontend mutation path, or new source of truth for queue/publish/rename/settings behavior. Current canonical authority remains the existing backend contracts, PSD1 config and schemas, `LocalBase\State` runtime evidence, Local API command contracts, and the safety boundaries documented in this repository.

**Example naming note:** Older examples in this document use the short display name `MediaPipeline`. Treat that as illustrative UI copy only. Repository implementation should use `MediaPipelineRemuxEncodeAIO V6` for product identity unless an existing screen intentionally uses a shorter label.

**Sample-validation note:** A generated controlled sample proof can show that the deployment can run a controlled workflow, write logs/state, and produce expected artifacts. It does not replace representative real-media validation after FFmpeg/media-policy, subtitle, audio, publish/drain, source/scratch/output movement, or cleanup behavior changes.

---

## Table of Contents

1. [Core Goal](#1-core-goal)
2. [The Problem Being Solved](#2-the-problem-being-solved)
3. [Product Principles](#3-product-principles)
4. [Definition of Ready](#4-definition-of-ready)
5. [The Desired Five-Minute User Experience](#5-the-desired-five-minute-user-experience)
6. [High-Level Architecture](#6-high-level-architecture)
7. [Key Concepts](#7-key-concepts)
8. [Setup as a Product Feature](#8-setup-as-a-product-feature)
9. [Deployment Manifest](#9-deployment-manifest)
10. [Manifest Schema Ideas](#10-manifest-schema-ideas)
11. [Setup State File](#11-setup-state-file)
12. [Setup State Machine](#12-setup-state-machine)
13. [Validation Engine](#13-validation-engine)
14. [Check Result Model](#14-check-result-model)
15. [Health Check Levels](#15-health-check-levels)
16. [File and Directory Verification](#16-file-and-directory-verification)
17. [File Integrity and Checksums](#17-file-integrity-and-checksums)
18. [Permission Checks](#18-permission-checks)
19. [Configuration Management](#19-configuration-management)
20. [Configuration Schema Validation](#20-configuration-schema-validation)
21. [Configuration Templates](#21-configuration-templates)
22. [Versioned Migrations](#22-versioned-migrations)
23. [Wiring Verification](#23-wiring-verification)
24. [Wiring Graph Model](#24-wiring-graph-model)
25. [Runtime Dependency Checks](#25-runtime-dependency-checks)
26. [Environment Variable and Secret Checks](#26-environment-variable-and-secret-checks)
27. [Database and Storage Checks](#27-database-and-storage-checks)
28. [Plugin and Extension Checks](#28-plugin-and-extension-checks)
29. [Model, Asset, and Resource Checks](#29-model-asset-and-resource-checks)
30. [Pipeline Step Registration Checks](#30-pipeline-step-registration-checks)
31. [UI-to-Command Wiring Checks](#31-ui-to-command-wiring-checks)
32. [Output Discovery and Output Verification](#32-output-discovery-and-output-verification)
33. [Sample Project and Functional Proof](#33-sample-project-and-functional-proof)
34. [Auto-Fix System](#34-auto-fix-system)
35. [Repair Mode](#35-repair-mode)
36. [Reset Mode](#36-reset-mode)
37. [Capability-Based Readiness](#37-capability-based-readiness)
38. [Setup Profiles](#38-setup-profiles)
39. [Launcher Behavior](#39-launcher-behavior)
40. [CLI Design](#40-cli-design)
41. [GUI Wizard Design](#41-gui-wizard-design)
42. [Ready Dashboard](#42-ready-dashboard)
43. [Error Codes and User-Facing Messages](#43-error-codes-and-user-facing-messages)
44. [Support Bundle Generator](#44-support-bundle-generator)
45. [Logging Requirements](#45-logging-requirements)
46. [Security, Privacy, and Secrets](#46-security-privacy-and-secrets)
47. [Platform-Specific Concerns](#47-platform-specific-concerns)
48. [Packaging and Installer Strategy](#48-packaging-and-installer-strategy)
49. [Portable Mode](#49-portable-mode)
50. [Update and Upgrade Flow](#50-update-and-upgrade-flow)
51. [Uninstall and Data Retention](#51-uninstall-and-data-retention)
52. [Clean Machine Testing](#52-clean-machine-testing)
53. [Broken Install Test Matrix](#53-broken-install-test-matrix)
54. [Automated Test Strategy](#54-automated-test-strategy)
55. [Release Gate Checklist](#55-release-gate-checklist)
56. [Implementation Roadmap](#56-implementation-roadmap)
57. [MVP Scope](#57-mvp-scope)
58. [Future Enhancements](#58-future-enhancements)
59. [Codex Discovery Instructions](#59-codex-discovery-instructions)
60. [Codex Implementation Prompt](#60-codex-implementation-prompt)
61. [Open Design Questions](#61-open-design-questions)
62. [Appendix A: Example Manifest](#appendix-a-example-manifest)
63. [Appendix B: Example Check Interface](#appendix-b-example-check-interface)
64. [Appendix C: Example Setup Report](#appendix-c-example-setup-report)
65. [Appendix D: Error Code Catalog](#appendix-d-error-code-catalog)
66. [Appendix E: Example UI Copy](#appendix-e-example-ui-copy)
67. [Appendix F: First Successful Job Flow](#appendix-f-first-successful-job-flow)
68. [Appendix G: Repository Inventory Checklist](#appendix-g-repository-inventory-checklist)

---

# 1. Core Goal

The setup system should transform a complicated tool into a reliable, guided, self-verifying product experience.

The core goal is not merely:

> The files exist.

The core goal is:

> The user can complete the core workflow successfully with the default setup, and the tool can prove that the installation, configuration, dependencies, wiring, and output flow are correct.

The final user experience should feel like this:

```text
User clicks Start MediaPipelineRemuxEncodeAIO V6
↓
MediaPipelineRemuxEncodeAIO V6 checks itself
↓
MediaPipelineRemuxEncodeAIO V6 creates safe defaults
↓
MediaPipelineRemuxEncodeAIO V6 verifies files, folders, config, dependencies, wiring, and output/pending-publish posture
↓
MediaPipelineRemuxEncodeAIO V6 runs a tiny controlled sample proof
↓
MediaPipelineRemuxEncodeAIO V6 shows the appropriate readiness state
↓
User can immediately run their first real job
```

This should not require:

- Reading a README.
- Opening a terminal.
- Editing YAML, JSON, `.env`, shell scripts, or source files.
- Understanding the internal directory structure.
- Knowing what command to run.
- Asking an AI assistant to patch setup failures.
- Guessing where output went.
- Guessing whether setup succeeded.

---

# 2. The Problem Being Solved

A complex tool often fails users in several predictable ways:

1. The repository contains many files, but the user does not know which one starts the app.
2. A wizard exists, but it only gathers information; it does not deeply verify that the app is actually usable.
3. Files are present, but components are not wired together correctly.
4. Config files reference paths that do not exist.
5. Dependencies are installed on the developer machine but missing on a fresh user machine.
6. Optional integrations appear required because the setup process does not distinguish core capabilities from optional capabilities.
7. Output and pending-publish evidence locations are not obvious.
8. Logs exist but are not easy to find.
9. The user cannot tell the difference between a successful install, a partially working install, and a broken install.
10. Updates break existing setup because config, data, schema, or wiring expectations changed.
11. Recovery requires manual debugging.
12. The README becomes the setup system, which is fragile and user-hostile.

The desired system solves these problems by introducing a formal deployment contract, automated validation, repair flows, and a productized setup experience.

---

# 3. Product Principles

## 3.1 Setup is part of the product

Setup should be treated as a first-class feature, not as documentation.

The setup system should be designed, tested, versioned, and maintained like any other core subsystem.

## 3.2 The README is a reference, not the setup mechanism

A README can explain advanced behavior, architecture, manual troubleshooting, and developer workflows.

It should not be required for normal setup.

## 3.3 One obvious start path

The user should have one obvious way to start:

```text
Start MediaPipelineRemuxEncodeAIO V6
```

That start path may be implemented as:

- A desktop shortcut or Start menu shortcut.
- A Windows `.exe` launcher.
- The promoted Tauri/WebView2 shell launcher.
- A backend-served browser launcher for support/development.
- Existing canonical scripts under `scripts\dev\`.
- A future CLI command, only after the current command surface is mapped.

For V6, do not implement this by reintroducing removed root launcher shims or generic `start.sh` / root `start.bat` files.

But from the user perspective, there should be one clear action.

## 3.4 Verify before use

The app should detect problems before the user spends time on a real task.

Bad:

```text
User starts a long job.
Ten minutes later the app fails because ffmpeg is missing.
```

Good:

```text
Setup check failed:
ffmpeg is required for video processing and was not found.

[Install Automatically]
[Choose Existing ffmpeg]
[Continue Without Video Features]
```

## 3.5 Prefer safe defaults over questions

The setup process should ask as few questions as possible.

Default local setup should work without custom choices.

A strong default might be:

```text
State:           LocalBase\State
Scratch/proof:   LocalBase\State\Setup\sample-proof
Pending publish: LocalBase\State\PendingPublish
Logs:            LocalBase\State\Logs
Config:          Existing PSD1 Settings Wizard path
```

Advanced customization can exist later in settings.

## 3.6 Prove the core workflow

Setup is not complete because files exist.

Setup is complete only when a minimal version of the core workflow succeeds.

That means the app should run a tiny controlled sample or fixture job and confirm the expected output for deployment proof.

## 3.7 Auto-fix what can be safely fixed

The app should automatically repair low-risk problems:

- Missing folders.
- Missing pipeline config generated from templates.
- Missing logs folder.
- Missing cache folder.
- Old config versions that can be migrated safely.
- Unsafe output/pending-publish posture.
- Missing setup state file that can be regenerated after validation.

The app should ask before risky changes:

- Resetting configuration.
- Replacing user-edited files.
- Deleting data.
- Moving output.
- Installing system dependencies.
- Overwriting extension/plugin files, only if a real extension/plugin system exists.

## 3.8 The user sees plain language; support sees technical detail

Basic user view:

```text
MediaPipelineRemuxEncodeAIO V6 is ready.
```

Advanced details:

```text
✓ Required files found
✓ Pipeline config schema valid
✓ ffmpeg found: 6.1
✓ Output or pending-publish posture valid
✓ Pipeline registry loaded
✓ Controlled sample proof completed
```

Both views should exist.

## 3.9 Idempotent setup

Running setup repeatedly should be safe.

A user should be able to:

- Start setup.
- Cancel halfway.
- Relaunch the app.
- Continue or repair.
- Run setup again without breaking existing data.

Idempotency is essential for real-world reliability.

## 3.10 Recovery is part of setup

Setup is not a one-time event.

Things can break after setup:

- User moves folders.
- Dependencies disappear.
- App updates.
- Config gets corrupted.
- Permissions change.
- Antivirus quarantines a binary.
- Cloud sync locks a file.

The launcher should detect these problems and open repair mode.

---

# 4. Definition of Ready

The app should not say “ready” unless the conditions for the selected readiness level are true. For V6, readiness should be explicit rather than a single vague badge.

## 4.1 Minimum ready criteria

The application should distinguish at least three readiness levels:

- **Install ready:** The app can launch, required files and bundled tools are present, and the Local API/WebView surface can load.
- **Configured ready:** Saved config, path roots, permissions, backend route contracts, and close-readiness are valid for the selected profile.
- **Workflow proven:** A controlled generated sample or fixture workflow completed and produced expected artifacts.

For V6, a generated sample or fixture proves deployment wiring only. Representative real-media validation remains the release gate after media-policy, FFmpeg, subtitle, audio, publish/drain, source/scratch/output movement, or cleanup behavior changes.

The application is ready for the default core workflow when:

1. A valid setup state exists or can be created.
2. Required application files are present.
3. Required directories exist.
4. Required directories have correct permissions.
5. Pipeline configuration exists.
6. Pipeline configuration validates against the current schema.
7. Required runtime dependencies are present and callable.
8. Required app components can load.
9. Pipeline steps required for the default workflow are registered.
10. UI or launcher actions resolve to real commands.
11. Output path is visible and writable.
12. Logs can be written.
13. A controlled generated sample or fixture job can run successfully, when that proof mode is enabled for the selected readiness level.
14. The app can show the user where output appears, or can prove final publish was safely parked with pending-publish evidence.
15. Optional features are either configured or clearly marked optional/unavailable.

## 4.2 What ready should not mean

Ready should not mean:

- The installer completed.
- A folder exists.
- A config file exists.
- The app opened once.
- The wizard reached the final page.
- There were no immediate exceptions.

Those are not enough.

## 4.3 Ready should be capability-aware

The app may be ready for local processing while an optional capability is not configured.

Example:

```text
Core processing: Ready
Local output: Ready
Batch mode: Ready
Optional OCR: Not configured
Browser smoke validation: Not configured
```

This prevents optional failures from blocking first use.

---

# 5. The Desired Five-Minute User Experience

## 5.1 Ideal first launch

```text
User clicks Start MediaPipelineRemuxEncodeAIO V6
↓
Welcome screen appears
↓
"We’ll verify local setup paths using recommended settings. You can change them later."
↓
User clicks Start Setup
↓
The app verifies configured state, scratch/proof, log, and publish-safety folders
↓
The app creates or validates config through the existing PSD1 Settings Wizard path
↓
The app validates dependencies
↓
The app validates wiring
↓
The app runs a controlled sample proof
↓
The app shows a Ready dashboard
↓
User clicks Run First Job or opens Settings
```

## 5.2 Good first-run screen

```text
Welcome to MediaPipelineRemuxEncodeAIO V6

We’ll set up everything needed for local processing.

State:
LocalBase\State

This includes:
✓ Configured source/output settings
✓ Pending-publish safety checks
✓ Logs
✓ Local settings
✓ Setup verification
✓ Controlled sample proof

[Start Setup]
[Customize]
```

## 5.3 Setup progress screen

```text
Setting up MediaPipelineRemuxEncodeAIO V6

✓ Verifying state and setup-proof paths
✓ Creating or validating configuration
✓ Checking required files
✓ Checking dependencies
✓ Checking output and pending-publish posture
✓ Verifying pipeline wiring
• Running controlled sample proof

This usually only takes a few moments.
```

Avoid showing too much technical detail by default, but provide a disclosure option:

```text
[Show technical details]
```

## 5.4 Ready screen

```text
MediaPipelineRemuxEncodeAIO V6 is ready

✓ Required files found
✓ Configuration valid
✓ Dependencies available
✓ Pipeline wiring verified
✓ Local output or pending-publish path validated
✓ Controlled sample proof completed

Source settings:
Configured in Settings

Output/publish status:
Writable, or pending publish is safely parked with manifest evidence

[Run First Job]
[Settings]
```

## 5.5 Failure screen

Failure should be specific and actionable.

Bad:

```text
Setup failed.
```

Good:

```text
MediaPipelineRemuxEncodeAIO V6 needs your attention

Problem:
The configured output root is not writable, and pending publish cannot safely park output.

Recommended fix:
Open Settings to choose a valid output root or repair pending-publish state.

[Open Settings]
[View Details]
[Create Support Bundle]
```

---

# 6. High-Level Architecture

The system should be organized around a deployment verification core with user-facing setup, launch, and repair flows built on top of it.

```text
Installer / Package
        ↓
Launcher
        ↓
Setup Orchestrator
        ↓
Deployment Manifest
        ↓
Validation Engine
        ↓
Auto-Fix Engine
        ↓
Wiring Verifier
        ↓
Sample Job Runner
        ↓
Ready Dashboard
```

## 6.1 Major components

### Installer / Package

Responsible for placing application files on the system and creating a visible launcher.

It should not be trusted as the final proof of readiness.

### Launcher

The user’s start point.

Responsible for:

- Starting the app.
- Detecting whether setup is complete.
- Running a quick health check.
- Opening setup wizard when needed.
- Opening repair mode when setup is broken.
- Opening the main app when ready.

### Setup Orchestrator

Coordinates setup states, checks, auto-fixes, migrations, controlled sample proofs, and user prompts.

### Deployment Manifest

Defines what a valid deployment should look like.

This is the contract.

### Validation Engine

Runs checks against the manifest and current system.

### Auto-Fix Engine

Repairs safe, known problems.

### Wiring Verifier

Checks that components are connected, not merely present.

### Sample Job Runner

Runs a tiny known-good workflow to prove the core app works.

### Ready Dashboard

Shows the user the final verified state and next action.

---

# 7. Key Concepts

## 7.1 Deployment contract

A formal definition of what must exist and work for the app to be usable.

Usually implemented as a manifest file plus schemas and check definitions.

## 7.2 Setup state

A durable record of whether setup has been completed, when it was completed, what version it used, and what checks passed.

## 7.3 Health check

A deterministic test that answers one question about the system.

Example:

```text
Can the app write setup proof evidence and report output/pending-publish posture?
```

## 7.4 Wiring check

A check that verifies relationships between components.

Example:

```text
Does the Run button call a command that exists and maps to a registered pipeline step?
```

## 7.5 Capability

A user-visible feature area that can be ready, degraded, optional, unavailable, or broken.

Generic example capabilities:

- Core processing.
- Local output.
- Batch processing.
- Optional OCR.
- Browser smoke validation.
- Future cloud, notification, or model support only if real features are added.

## 7.6 Auto-fix

A safe corrective action the app can take without requiring the user to manually repair setup.

## 7.7 Repair mode

A guided recovery path for broken existing setups.

## 7.8 Controlled sample proof

A small generated or fixture-backed task that proves deployment wiring can complete a controlled workflow without touching user media.

## 7.9 Support bundle

A zip or folder containing logs, reports, environment details, and redacted config to help debug failures.

---

# 8. Setup as a Product Feature

The first architectural shift is mental: setup is not documentation.

Setup is a product feature with:

- User experience.
- State.
- Failure handling.
- Logging.
- Tests.
- Versioning.
- Support tools.
- Release gates.

## 8.1 What the wizard should become

The wizard should not be the entire setup system.

The wizard should be the friendly user interface on top of the setup system.

Current likely state:

```text
Wizard collects inputs
↓
Wizard writes config
↓
App assumes it works
```

Target state:

```text
Wizard starts setup orchestrator
↓
Orchestrator reads manifest
↓
Validators run checks
↓
Fixers repair safe issues
↓
Wiring verifier checks connections
↓
Controlled sample proof verifies deployment wiring
↓
Wizard presents result
```

## 8.2 The setup system should be callable from multiple places

The same validation and repair system should be available from:

- First-run wizard.
- Launcher quick check.
- Settings → Verify Deployment.
- CLI `doctor` command.
- Installer post-install hook, where appropriate.
- Automated tests.
- Release validation.

This prevents duplicated setup logic.

---

# 9. Deployment Manifest

The deployment manifest is the deployability verification contract.

It should define expected files, directories, dependencies, config schemas, wiring relationships, capabilities, setup profiles, controlled sample proofs, and version compatibility.

For V6, it must not become a new authority for media policy, FFmpeg argument generation, subtitle/audio handling, queue mutation, settings persistence, pending-publish drain, rename apply, or source/scratch/output file movement. Those remain owned by the existing backend contracts and engine behavior.

## 9.1 Why a manifest matters

Without a manifest, the app relies on scattered assumptions.

Examples of scattered assumptions:

- The Settings Wizard assumes the PSD1 config/template/schema paths are present.
- The launcher assumes the canonical `scripts\dev\*.bat` wrapper exists.
- The app assumes the bundled Python runtime and FFmpeg/ffprobe tooling can be resolved.
- The pipeline assumes scratch, output, pending-publish, and log roots are safe to use.
- The UI assumes a backend command route is registered and journaled.
- A README assumes the user will create or choose folders manually.

A manifest centralizes these deployment expectations without replacing backend ownership.

## 9.2 Manifest responsibilities

The manifest should answer:

- What app version is this deployment for?
- What setup schema version is required?
- What files are required?
- Which required files are shipped vs generated?
- Which generated files may be recreated?
- What directories are required?
- Which directories must be writable?
- What dependencies are required?
- What dependencies are optional?
- What environment variables are required?
- What config files exist?
- What schemas validate those configs?
- What migrations exist?
- What entry points should work?
- What commands should be registered?
- What pipeline steps should be registered?
- What optional capabilities exist?
- What checks prove each capability?
- What controlled sample proof demonstrates deployment wiring?

## 9.3 Manifest storage location

Potential V6 locations:

```text
schemas/deployment_manifest.v1.schema.json
DesktopApp/mediapipeline_desktop_app/resources/deployment_manifest.json
Pipeline/Release/deployment_manifest.json
```

For V6, Codex should prefer a generated or checked JSON manifest under the existing schema/resource conventions, such as `schemas\deployment_manifest.v1.schema.json` plus a package-time `release_manifest.json`/deployment-verification manifest. Do not introduce a YAML config tree or a root launcher path just because the examples below use generic names.

## 9.4 Manifest versioning

The manifest itself should have a schema version.

Example:

```yaml
manifest_schema_version: 1
app_version: v6.000
setup_schema_version: 3
```

This allows the validator to detect incompatible manifests.

## 9.5 Manifest should be machine-readable and human-readable

For V6, JSON is the preferred candidate because this repository already uses generated JSON schemas and release manifests for machine-checked contracts.

YAML is acceptable only as an illustrative format in this document; do not create a parallel YAML setup/config system for V6 without a deliberate architecture decision.

TOML may be appropriate for Python-oriented tooling.

The exact format matters less than having one explicit deployment-verification contract.

---

# 10. Manifest Schema Ideas

The manifest can be broad at first and grow over time.

The examples in this section are generic schema sketches. For V6 implementation:

- Use `MediaPipelineRemuxEncodeAIO V6` / `v6.000` identity.
- Map config entries to the existing PSD1 config, `Pipeline\MediaPipeline_config_template.psd1`, `schemas\config.v1.schema.json`, and `Pipeline\Schemas\media_pipeline_config.schema.json`.
- Map runtime/setup state to `LocalBase\State`, not `%APPDATA%\MediaPipeline` or a new `user.yaml`.
- Map entrypoints to canonical `scripts\dev\*.bat`, `scripts\verify-env.*`, and `scripts\release\*.ps1` paths.
- Treat cloud/plugin/model entries as optional future examples unless a real repo feature already exists.
- Avoid `start.sh`, root `start.bat`, or other legacy/root launcher shims.

## 10.1 Top-level structure

```yaml
manifest_schema_version: 1
app:
  id: mediapipeline-remux-encode-aio-v6
  name: MediaPipelineRemuxEncodeAIO V6
  version: v6.000
  min_supported_setup_version: 1
  required_setup_version: 3

profiles:
  - id: windows-local-operator
  - id: windows-developer

entrypoints:
  start_api_and_browser:
    path: scripts/dev/start-api-and-browser.bat
    required: true
  start_tauri_preview:
    path: scripts/dev/start-tauri-preview.bat
    required: false

paths:
  install_root:
    type: app_install
  state_root:
    type: v6_local_state
    default: LocalBase/State
  pipeline_root:
    type: v6_pipeline_root
    default: Pipeline
  desktop_app_root:
    type: v6_desktop_app_root
    default: DesktopApp/mediapipeline_desktop_app
  logs_root:
    type: v6_logs

files: []
directories: []
configs: []
dependencies: []
capabilities: []
wiring: []
sample_jobs: []
checks: []
fixers: []
migrations: []
```

## 10.2 File entries

```yaml
files:
  - id: pipeline_config_template
    path: Pipeline/MediaPipeline_config_template.psd1
    required: true
    origin: shipped
    integrity: sha256:abc123
    purpose: Pipeline configuration template

  - id: config_schema_primary
    path: schemas/config.v1.schema.json
    required: true
    origin: shipped
    integrity: sha256:def456
    purpose: Primary config schema

  - id: pipeline_config_schema
    path: Pipeline/Schemas/media_pipeline_config.schema.json
    required: true
    origin: shipped
    integrity: sha256:fedcba
    purpose: Pipeline config schema

  - id: active_pipeline_config
    path: Pipeline/MediaPipeline_config.psd1
    required: true
    origin: generated
    template: pipeline_config_template
    can_create: true
    schema: config_schema_primary
    purpose: Active pipeline configuration

  - id: start_api_and_browser
    path: scripts/dev/start-api-and-browser.bat
    required_on: [windows]
    origin: shipped
    purpose: Canonical browser/API launcher

  - id: start_tauri_preview
    path: scripts/dev/start-tauri-preview.bat
    required_on: [windows]
    origin: shipped
    purpose: Canonical Tauri/WebView preview launcher
```

## 10.3 Directory entries

```yaml
directories:
  - id: state_root
    path: LocalBase/State
    required: true
    can_create: true
    writable: true
    purpose: Backend-owned runtime state

  - id: sample_proof_dir
    path: ${state_root}/Setup/sample-proof
    required: true
    can_create: true
    writable: true
    cleanup_allowed: true
    purpose: Setup-owned controlled sample output

  - id: logs_dir
    path: ${state_root}/Logs
    required: true
    can_create: true
    writable: true
    purpose: Application and setup logs

  - id: pending_publish_dir
    path: ${state_root}/PendingPublish
    required: true
    can_create: true
    writable: true
    cleanup_allowed: false
    purpose: Parked publish evidence and payloads
```

## 10.4 Dependency entries

```yaml
dependencies:
  - id: ffmpeg
    type: executable
    command: ffmpeg
    required: true
    min_version: "5.0"
    version_arg: "-version"
    capability: core_video_processing
    install_help: dependency_help.ffmpeg

  - id: ffprobe
    type: executable
    command: ffprobe
    required: true
    min_version: "5.0"
    version_arg: "-version"
    capability: media_metadata

  - id: python_runtime
    type: runtime
    required: true
    path: DesktopApp/Runtime/Python/python.exe

  - id: optional_subtitle_ocr_tooling
    type: executable_group
    required: false
    capability: subtitle_ocr_when_enabled
```

## 10.5 Config entries

```yaml
configs:
  - id: pipeline_config
    path: Pipeline/MediaPipeline_config.psd1
    schema: schemas/config.v1.schema.json
    template: Pipeline/MediaPipeline_config_template.psd1
    can_generate: true
    can_migrate: true
    required_version: 3
```

## 10.6 Capability entries

```yaml
capabilities:
  - id: core_processing
    name: Core Processing
    required_for_ready: true
    checks:
      - check.required_files
      - check.pipeline_config_valid
      - check.output_or_pending_publish_posture
      - check.pipeline_registry
      - check.sample_job

  - id: optional_subtitle_ocr
    name: Subtitle OCR When Enabled
    required_for_ready: false
    checks:
      - check.ocr_tooling_available
      - check.ocr_failure_routes_to_review
```

## 10.7 Wiring entries

```yaml
wiring:
  - id: ui_run_button_to_pipeline
    from: ui.action.run_pipeline
    to: command.run_pipeline
    required: true

  - id: command_to_pipeline_step
    from: command.run_pipeline
    to: pipeline.default_workflow
    required: true

  - id: pipeline_to_output_handler
    from: pipeline.default_workflow
    to: output.local_file_writer
    required: true

  - id: transcoder_to_ffmpeg
    from: pipeline.step.transcode
    to: dependency.ffmpeg
    required: true
```

## 10.8 Controlled sample proof entries

```yaml
sample_jobs:
  - id: controlled_fixture_job
    name: Controlled fixture deployment proof
    required_for_ready: true
    input: ${install_root}/Pipeline/TestFixtures/generated_sample.mp4
    expected_outputs:
      - ${state_root}/Setup/sample-proof/sample_output.mp4
      - ${state_root}/Setup/sample-proof/sample_manifest.json
    timeout_seconds: 60
    cleanup_after_success: true
```

---

# 11. Setup State File

The setup state file records what happened during setup and what version of the setup contract was satisfied.

## 11.1 Why file presence is not enough

Do not infer setup completion only from whether a config file exists.

A config file can exist while being:

- Outdated.
- Invalid.
- Pointing to missing folders.
- Generated by an old app version.
- Partially written by a failed setup.
- Copied from another machine.

A durable setup state file provides a more precise signal.

## 11.2 Example setup state

```yaml
setup_status:
  completed: true
  completed_at: "2026-05-31T10:42:00-04:00"
  app_id: mediapipeline-remux-encode-aio-v6
  app_version: "v6.000"
  manifest_schema_version: 1
  setup_schema_version: 3
  profile: windows-local-operator
  state_root: "LocalBase/State"
  last_verified_at: "2026-05-31T10:43:00-04:00"
  last_verification_result: passed
  controlled_sample_passed: true
  capabilities:
    core_processing: ready
    local_output: ready
    optional_subtitle_ocr: not_configured
  checks:
    required_files: passed
    required_directories: passed
    config_schema: passed
    runtime_dependencies: passed
    wiring: passed
    sample_job: passed
```

## 11.3 Setup state location

Store setup state in the existing application state root, not inside the read-only application install directory.

For V6, prefer `LocalBase\State\App` or a sibling `LocalBase\State\Setup` location so setup evidence follows the existing runtime-state ownership model. Do not create a separate `%APPDATA%` setup-state authority unless the state-root architecture is deliberately changed.

Current V6 target:

Windows:

```text
LocalBase/State/Setup/setup_state.json
```

Future macOS, if the product intentionally becomes cross-platform:

```text
~/Library/Application Support/MediaPipelineRemuxEncodeAIO/Setup/setup_state.json
```

Future Linux, if the product intentionally becomes cross-platform:

```text
~/.local/state/mediapipeline-remux-encode-aio/setup_state.json
```

## 11.4 State file rules

- The app may recreate setup state only after validation succeeds.
- The state file should not contain secrets.
- The state file should identify app version and setup schema version.
- The state file should record last verification time.
- The state file should record capability status.
- The state file should not be the only proof of readiness.
- Launch should still perform quick health checks.

---

# 12. Setup State Machine

The first-run process should be a formal state machine rather than a loose sequence of wizard pages.

## 12.1 State list

```text
NOT_STARTED
LOADING_MANIFEST
CHECKING_SYSTEM
SELECTING_PROFILE
CREATING_WORKSPACE
GENERATING_CONFIG
VALIDATING_FILES
VALIDATING_DIRECTORIES
VALIDATING_PERMISSIONS
VALIDATING_CONFIG
VALIDATING_DEPENDENCIES
RUNNING_MIGRATIONS
VALIDATING_WIRING
RUNNING_SAMPLE_JOB
WRITING_SETUP_STATE
READY
NEEDS_USER_ACTION
REPAIRING
FAILED
CANCELLED
```

## 12.2 State metadata

Each state should have:

- State ID.
- User-facing label.
- Technical description.
- Entry action.
- Success transition.
- Failure transition.
- Auto-fix behavior, if any.
- User action options, if needed.
- Log event.
- Error code, if applicable.

## 12.3 Example state definition

```yaml
state: VALIDATING_DEPENDENCIES
label: Checking required tools
technical_description: Verify required runtime dependencies and executable versions.
on_success: VALIDATING_WIRING
on_failure: NEEDS_USER_ACTION
auto_fix: conditional
failure_codes:
  - MP-DEP-001
  - MP-DEP-002
```

## 12.4 State transition flow

```text
NOT_STARTED
  → LOADING_MANIFEST
  → CHECKING_SYSTEM
  → SELECTING_PROFILE
  → CREATING_WORKSPACE
  → GENERATING_CONFIG
  → VALIDATING_FILES
  → VALIDATING_DIRECTORIES
  → VALIDATING_PERMISSIONS
  → VALIDATING_CONFIG
  → VALIDATING_DEPENDENCIES
  → RUNNING_MIGRATIONS
  → VALIDATING_WIRING
  → RUNNING_SAMPLE_JOB
  → WRITING_SETUP_STATE
  → READY
```

Failures go to either:

```text
NEEDS_USER_ACTION
REPAIRING
FAILED
```

## 12.5 Cancellation rules

If the user cancels setup:

- Do not mark setup as complete.
- Preserve safely created folders.
- Preserve generated config only if valid or clearly marked partial.
- Write a setup log.
- Allow resume.

## 12.6 Idempotency rules

Every state should be safe to re-enter.

Examples:

- Creating a directory should not fail if it already exists.
- Generating config should not overwrite an existing pipeline config without backup.
- Running migrations should detect already-applied migrations.
- Running controlled sample proof should use an isolated setup-owned output location.

---

# 13. Validation Engine

The validation engine runs checks and produces structured results.

## 13.1 Responsibilities

The validation engine should:

- Load the deployment manifest.
- Resolve variables and platform-specific paths.
- Build a list of checks for the selected profile.
- Run checks in a deterministic order.
- Support check dependencies.
- Support quick checks and deep checks.
- Support user-friendly result messages.
- Support machine-readable JSON output.
- Feed results to the auto-fix system.
- Feed results to the UI and logs.

## 13.2 Check execution modes

### Quick mode

Used on normal launch.

Checks only what is necessary to decide whether the app can start.

Example:

```text
setup state exists
config parses
output writable
required dependencies still callable
app version compatible with setup version
```

### Standard mode

Used on first setup and Verify Deployment.

Includes all required readiness checks.

### Deep mode

Used for troubleshooting, support, release validation, or advanced diagnostics.

Includes file hashes, controlled sample proof, optional capability checks, and storage checks that match the app's actual authority model. For V6, plugin checks are future-only and SQLite checks are mirror checks unless a backend contract makes them required.

### JSON mode

Used by automation.

Example:

```bash
mediapipeline verify-install --json
```

## 13.3 Check ordering

Checks should be ordered to fail early and explain clearly.

Recommended order:

1. Manifest can load.
2. Platform is supported.
3. Required directories can be resolved.
4. Setup-owned state/proof/log roots can be created.
5. Required files exist.
6. Pipeline config exists or can be generated through the existing settings path.
7. Config schema validates.
8. Permissions and output/pending-publish posture are valid.
9. Dependencies exist.
10. App components import/load.
11. Registry entries exist.
12. Wiring graph is valid.
13. Controlled sample proof succeeds.
14. Setup state can be written.

## 13.4 Check dependency graph

Some checks require earlier checks to pass.

Example:

```text
Config schema check depends on config file existence.
Output write check depends on config path resolution.
Controlled sample proof depends on dependency checks and pipeline registration.
```

This should be explicit.

## 13.5 Result aggregation

The validation engine should aggregate results into:

- Overall status.
- Required readiness status.
- Capability statuses.
- Blocking failures.
- Warnings.
- Auto-fixable issues.
- User-action-required issues.
- Technical detail.

---

# 14. Check Result Model

Each check should return a structured result.

## 14.1 Result fields

```yaml
check_id: check.output_or_pending_publish_posture
status: passed
severity: blocker
capability: local_output
message: Output path is writable or pending publish is safely available.
technical_detail: Verified output path or pending-publish manifest evidence.
fix_available: false
fix_id: null
user_action_required: false
error_code: null
duration_ms: 42
```

## 14.2 Status values

Recommended statuses:

```text
passed
failed
warning
skipped
not_applicable
fixed
needs_user_action
unknown
```

## 14.3 Severity values

Recommended severities:

```text
blocker
error
warning
info
```

Definitions:

- `blocker`: App cannot be considered ready.
- `error`: Capability is broken, but not necessarily core readiness.
- `warning`: App can run, but something may be degraded.
- `info`: Useful diagnostic information.

## 14.4 User action values

Possible user actions:

```yaml
user_actions:
  - id: choose_output_folder
    label: Choose Output Folder
    type: folder_picker

  - id: install_dependency
    label: Install ffmpeg
    type: installer_action

  - id: open_help
    label: View Help
    type: help_link

  - id: create_support_bundle
    label: Create Support Bundle
    type: support_bundle
```

## 14.5 Machine-readable JSON example

```json
{
  "overall_status": "failed",
  "ready": false,
  "blocking_failures": [
    {
      "check_id": "check.output_or_pending_publish_posture",
      "error_code": "MP-PERM-003",
      "message": "Output path is not writable and pending publish is not available.",
      "fix_available": true,
      "fix_id": "fix.open_output_settings"
    }
  ],
  "capabilities": {
    "core_processing": "blocked",
    "local_output": "blocked",
    "optional_subtitle_ocr": "not_configured"
  }
}
```

---

# 15. Health Check Levels

Health checks should be grouped into levels.

## 15.1 Level 1: Install integrity

Checks whether the package appears intact.

Examples:

- Required app files exist.
- Required templates exist.
- Launcher file exists.
- Start script is executable, where relevant.
- File hashes match, if enabled.
- Manifest version is compatible.

## 15.2 Level 2: Runtime readiness

Checks whether the app can run.

Examples:

- Runtime version is supported.
- Required directories exist.
- Output directory is writable.
- Logs directory is writable.
- Config file exists.
- Config schema validates.
- Required dependencies are available.

## 15.3 Level 3: Wiring correctness

Checks whether components connect properly.

Examples:

- UI action maps to command.
- Command maps to pipeline workflow.
- Pipeline workflow references registered steps.
- Pipeline steps reference valid dependencies.
- Output handler is registered.
- Optional/future plugin registry loads only if a real plugin system exists.
- Database or SQLite mirror schema matches expected version only if that storage layer is active.

## 15.4 Level 4: Functional proof

Checks whether the app actually works.

Examples:

- Controlled sample proof runs.
- Expected output file appears.
- Expected metadata file appears.
- Logs are written.
- No blocker-severity errors occur; warnings are classified as blocker, review, or advisory.
- Output or pending-publish evidence can be opened.

---

# 16. File and Directory Verification

## 16.1 Required file checks

Check that all required shipped files exist.

Examples:

- App entrypoint.
- Manifest.
- Default config template.
- Config schema.
- Sample input file.
- UI resources.
- Pipeline definitions.
- Plugin registry file, only if a real plugin system exists.
- Launch scripts.

## 16.2 Generated file checks

Generated files should be created from templates when missing.

Examples:

- Pipeline config.
- Setup state.
- Local database or mirror, only if active for the selected profile.
- Initial setup-state metadata.

## 16.3 Directory checks

Check that required directories exist and are usable.

Examples:

- Input directory.
- Output directory.
- Logs directory.
- Cache directory.
- Temp directory.
- Plugin directory, only if a real plugin system exists.
- Model directory, only if a real model feature exists.
- Database directory, only if active for the selected profile.

## 16.4 Path resolution checks

The validator should resolve path variables before checking.

Example variables:

```text
${install_root}
${state_root}
${logs_root}
${source_movies_dir}
${source_tv_dir}
${outsource_dir}
${sample_proof_dir}
${pending_publish_dir}
${user_home}
${user_documents}
```

## 16.5 Bad path detection

Detect risky paths:

- Running from inside a zip archive.
- App installed in a protected system folder.
- Configured source/output root inside the app install folder, if app install is read-only.
- Configured source/output or state root points to a root drive.
- Path contains unsupported characters.
- Path length exceeds platform limits.
- Path is on a disconnected network drive.
- Path is in cloud sync and locked.
- Path is inside temp folder when persistence is expected.

---

# 17. File Integrity and Checksums

For shipped files, the system may verify hashes.

## 17.1 What to hash

Good candidates:

- Default templates.
- Sample input files.
- Core application resources.
- Built-in extension/plugin files, only if a real extension/plugin system exists.
- Static UI assets required for launch.
- Launch scripts.

## 17.2 What not to hash

Usually avoid hashing:

- Pipeline config.
- Logs.
- Cache.
- Output files.
- Temp files.
- User-installed plugins, unless a real plugin system and manifest explicitly support integrity checks.

## 17.3 Integrity failure behavior

If a required shipped file fails integrity:

```text
Problem:
A required application file appears to be missing or modified.

Recommended fix:
Repair or reinstall MediaPipelineRemuxEncodeAIO V6.

[Repair Installation]
[Create Support Bundle]
[View Details]
```

## 17.4 Hash strategy

Manifest example:

```yaml
files:
  - id: controlled_sample_input
    path: Pipeline/TestFixtures/generated_sample.mp4
    required: true
    integrity:
      algorithm: sha256
      value: "abc123..."
```

Integrity checks can be optional in MVP if packaging makes it difficult.

---

# 18. Permission Checks

The app should verify permissions before real work begins.

## 18.1 Required permission checks

- Can read required shipped files.
- Can read config.
- Can write config directory.
- Can write setup state file.
- Can write logs.
- Can create temp files.
- Can write required local output or setup-owned proof files.
- Can delete temp files.
- Can execute required scripts or binaries.

For V6, final-library output writability and pending-publish drain readiness should be reported separately from local/scratch output readiness. If final output is unavailable or unsafe, the backend may park output through the pending-publish flow rather than treating setup as globally broken.

## 18.2 Setup proof write test

A simple write test:

1. Resolve the setup-owned sample proof directory.
2. Ensure it exists.
3. Create a hidden or temporary test file.
4. Write a short string.
5. Flush and close.
6. Read it back, if useful.
7. Delete the test file.
8. Report success or failure separately from final output/pending-publish readiness.

## 18.3 Permission-specific user messages

Bad:

```text
EACCES
```

Good:

```text
MediaPipelineRemuxEncodeAIO V6 cannot write setup proof evidence or validate output/pending-publish posture.

Open Settings to choose a valid output root, or repair pending-publish state.

[Open Settings]
[View Details]
```

## 18.4 Protected location detection

Warn if the user tries to use protected locations:

- System directories.
- Program Files.
- `/Applications` for writable data.
- `/usr/bin` or `/usr/local/bin` for user output.
- Root filesystem.
- Read-only mounted volumes.

---

# 19. Configuration Management

Configuration should be generated, validated, migrated, and repaired by the app.

The user should not have to manually edit config for the basic setup.

## 19.1 Config categories

### Shipped defaults

Read-only defaults included with the app.

### Pipeline config

Writable pipeline settings created during setup through the existing settings path.

### Runtime state

Generated state that should not be manually edited.

### Secrets

Credentials or tokens, stored separately and securely when possible.

## 19.2 Recommended structure

V6-oriented layout:

```text
App install directory:
  Pipeline/MediaPipeline_config_template.psd1
  Pipeline/Schemas/media_pipeline_config.schema.json
  schemas/config.v1.schema.json
  scripts/dev/start-api-and-browser.bat
  scripts/dev/start-tauri-preview.bat

Pipeline config:
  Pipeline/MediaPipeline_config.psd1

Runtime state root:
  LocalBase/State/
  LocalBase/State/Setup/setup_state.json
  LocalBase/State/PendingPublish/
  LocalBase/State/Queue/

Setup-owned proof/cache directory:
  LocalBase/State/Setup/sample-proof/
  LocalBase/State/Setup/cache/

Logs directory:
  LocalBase/State/Logs/
```

V6 mapping:

- App resources and scripts live under the repository/package root, especially `DesktopApp\`, `Pipeline\`, `engine\`, `schemas\`, and `scripts\`.
- The live pipeline config format is PSD1, with template/schema coverage from `Pipeline\MediaPipeline_config_template.psd1`, `schemas\config.v1.schema.json`, and `Pipeline\Schemas\media_pipeline_config.schema.json`.
- Runtime state belongs under `LocalBase\State`; detailed state artifacts are documented in `Docs\inventories\RUNTIME_ARTIFACT_INVENTORY.md`.
- Network auth tokens remain intentionally hidden from WebView builders and must stay redacted in logs/support bundles.

## 19.3 Config source priority

A common priority order:

1. Built-in defaults.
2. Shipped default config.
3. Pipeline config.
4. Environment overrides.
5. CLI arguments.
6. Runtime UI selections.

Document and enforce this order.

## 19.4 Config writing rules

- Never overwrite pipeline config without backup.
- Create missing config from template.
- Validate config before saving.
- Save atomically where possible.
- Redact secrets in logs.
- Include config schema version.

## 19.5 Example pipeline config

This block is illustrative only. V6 implementation should map the same concepts onto the existing PSD1 config keys rather than adding a parallel `user.yaml`.

```yaml
config_schema_version: 3
paths:
  local_base: "LocalBase"
  source_movies: "${CONFIGURED_SOURCE_MOVIES}"
  source_tv: "${CONFIGURED_SOURCE_TV}"
  outsource: "${CONFIGURED_OUTSOURCE}"
  setup_sample_proof: "${paths.local_base}/State/Setup/sample-proof"
logging:
  level: info
  directory: "${paths.local_base}/State/Logs"
features:
  advanced_mode: false
  optional_ocr: false
  browser_smoke_validation: false
processing:
  default_profile: basic
```

---

# 20. Configuration Schema Validation

Every config file should have a schema.

## 20.1 Schema checks

Validate:

- Required fields.
- Data types.
- Enum values.
- Version numbers.
- Path strings.
- Deprecated fields.
- Unknown fields, if strict mode is desired.
- Compatibility with selected setup profile.

## 20.2 Schema versioning

Include a schema version field:

```yaml
config_schema_version: 3
```

If config schema version is old, run migration.

If config schema version is too new, fail with a clear message:

```text
This configuration was created by a newer version of MediaPipeline.
Update MediaPipeline or choose a different config folder.
```

## 20.3 Invalid config message

```text
Your configuration needs attention.

Field:
paths.outsource

Problem:
The folder path is empty.

Recommended fix:
Choose an output root or allow pending publish to park output safely.

[Open Settings]
[Restore Default]
[View Details]
```

## 20.4 Strict vs tolerant validation

For MVP:

- Required fields should be strict.
- Unknown fields may be warnings.
- Deprecated fields should trigger migration warnings.

For mature versions:

- Strict validation may be enabled in release tests.
- User-facing app may remain tolerant and auto-migrate.

---

# 21. Configuration Templates

Generated config should come from templates.

## 21.1 Why templates help

Templates prevent logic duplication.

The wizard, CLI setup, repair mode, and tests can all generate config the same way.

## 21.2 Template variables

Useful variables:

```text
{{APP_NAME}}
{{APP_VERSION}}
{{USER_HOME}}
{{USER_DOCUMENTS}}
{{USER_CONFIG}}
{{USER_CACHE}}
{{USER_LOGS}}
{{WORKSPACE_ROOT}}
{{INPUT_DIR}}
{{OUTPUT_DIR}}
{{TEMP_DIR}}
{{OS}}
{{ARCH}}
```

## 21.3 Template rendering rules

- Validate variables before rendering.
- Do not render unresolved variables silently.
- Write generated files atomically.
- Back up existing pipeline config before replacement.
- Mark generated files with schema version.

## 21.4 Example template

```yaml
config_schema_version: {{CONFIG_SCHEMA_VERSION}}
paths:
  local_base: "{{LOCAL_BASE}}"
  source_movies: "{{SOURCE_MOVIES}}"
  source_tv: "{{SOURCE_TV}}"
  outsource: "{{OUTSOURCE}}"
  setup_sample_proof: "{{SETUP_SAMPLE_PROOF_DIR}}"
logging:
  level: info
  directory: "{{LOGS_DIR}}"
features:
  advanced_mode: false
```

---

# 22. Versioned Migrations

Updates should not silently break existing setups.

For V6, config/state migration must work through existing backend save, backup, schema, and state-root paths. Do not introduce an independent deployment migration runner that rewrites PSD1 config, `LocalBase\State`, pending-publish manifests, completed manifests, sidecars, or queue state outside established backend-owned flows.

## 22.1 Migration problem

A user may have config version 2 while the new app requires version 3.

The app should detect this and run a migration.

## 22.2 Migration registry

Example:

```yaml
migrations:
  - id: migration.config.1_to_2
    from_version: 1
    to_version: 2
    type: config
    reversible: false

  - id: migration.config.2_to_3
    from_version: 2
    to_version: 3
    type: config
    reversible: false
```

## 22.3 Migration behavior

Before migration:

- Validate current config as much as possible.
- Back up current config.
- Record migration start in logs.

During migration:

- Transform fields.
- Add defaults.
- Remove deprecated fields only if safe.
- Preserve user values.

After migration:

- Validate new config.
- Record migration success.
- If migration fails, restore backup if possible.

## 22.4 Migration user message

```text
MediaPipelineRemuxEncodeAIO V6 needs to update your local settings for this version.
Your current settings will be backed up first.

[Update Settings]
[View Details]
```

## 22.5 Migration tests

Every migration should have tests:

- Old config input.
- Expected new config output.
- Invalid old config behavior.
- Backup creation.
- Idempotent rerun.

---

# 23. Wiring Verification

File existence does not prove the app is wired correctly.

Wiring verification checks whether components are connected properly.

## 23.1 Examples of wiring failures

- UI button calls a command name that no longer exists.
- Command exists but references a missing pipeline step.
- Pipeline step exists but is not registered.
- Config points to a dependency path that is invalid.
- Future plugin file exists but does not load.
- Database or mirror exists but schema does not match app code.
- Output handler exists but is not selected by config.
- A controlled sample proof writes outside the setup-owned proof location.

## 23.2 What to verify

Wiring checks should verify relationships among:

- UI actions.
- CLI commands.
- Internal command handlers.
- Pipeline workflows.
- Pipeline steps.
- Dependency executables.
- Config keys.
- Output handlers.
- Future plugin registries, only if implemented.
- Database or mirror schemas, only if active.
- Background workers.
- Job queues.
- Model/resource loaders, only if real model features exist.

## 23.3 Wiring verification levels

### Static wiring

Can be checked without running a real job.

Examples:

- Does command ID exist?
- Is pipeline step registered?
- Does config key exist in schema?

### Dynamic wiring

Requires calling or simulating the component.

Examples:

- Can dependency execute?
- Can plugin instantiate, only if a real plugin system exists?
- Can output handler write?
- Can pipeline step process sample input?

### Functional wiring

Requires an end-to-end controlled sample or fixture job.

Examples:

- Does the default workflow produce expected output?

---

# 24. Wiring Graph Model

A wiring graph makes relationships explicit.

## 24.1 Graph nodes

Potential node types:

```text
ui.action
cli.command
internal.command
pipeline.workflow
pipeline.step
dependency.executable
config.key
config.file
directory
file
plugin
model
asset
database.schema
output.handler
background.worker
capability
```

## 24.2 Graph edges

Potential edge types:

```text
triggers
requires
reads
writes
loads
registers
provides
uses
produces
validates
configured_by
implemented_by
```

## 24.3 Example graph

```yaml
wiring:
  - id: run_button_triggers_run_command
    from: ui.action.run_button
    edge: triggers
    to: command.run_pipeline
    required: true

  - id: run_command_uses_default_workflow
    from: command.run_pipeline
    edge: uses
    to: pipeline.workflow.default
    required: true

  - id: default_workflow_uses_transcode_step
    from: pipeline.workflow.default
    edge: uses
    to: pipeline.step.transcode
    required: true

  - id: transcode_step_requires_ffmpeg
    from: pipeline.step.transcode
    edge: requires
    to: dependency.ffmpeg
    required: true

  - id: workflow_writes_local_output
    from: pipeline.workflow.default
    edge: writes
    to: directory.output
    required: true
```

## 24.4 Graph validation rules

The verifier should check:

- Every required node exists.
- Every required edge resolves.
- There are no dangling references.
- Required capabilities have all required dependencies.
- Optional capabilities can be missing without blocking core readiness.
- A component marked required by profile is not skipped.
- Config-selected components exist.

## 24.5 Detecting stale wiring

A stale wiring reference occurs when a component was renamed or removed but references remain.

Examples:

```text
ui.action.export_video → command.export_media
```

But the actual command is now:

```text
command.run_export
```

The wiring checker should catch that before the user clicks the button.

---

# 25. Runtime Dependency Checks

External tools should be detected clearly.

## 25.1 Dependency types

- Executable on PATH.
- Executable at configured path.
- Python package.
- Node package.
- System library.
- Runtime version.
- Service process.
- Local database engine or mirror, only if active.
- GPU/CUDA runtime, if applicable.

## 25.2 Executable check

For each executable:

1. Locate command.
2. Run version command.
3. Parse version.
4. Compare with minimum version.
5. Run a smoke test if needed.

Example:

```text
ffmpeg:
Status: Found
Version: 6.1
Path: /usr/local/bin/ffmpeg
Required: 5.0 or newer
```

## 25.3 Missing dependency behavior

Required dependency missing:

```text
ffmpeg is required for video processing and was not found.

[Install ffmpeg]
[Choose Existing ffmpeg]
[View Details]
```

Optional dependency missing:

```text
Optional subtitle OCR tooling is not configured.
You can still use local processing.

[Configure OCR Tooling]
[Skip]
```

## 25.4 Dependency path config

If users can select a dependency path, validate immediately:

- File exists.
- File is executable.
- Version command works.
- Version is supported.
- Tool behaves as expected.

---

# 26. Environment Variable and Secret Checks

Environment variables should not be a hidden setup requirement for normal users.

## 26.1 Required environment variables

Avoid required env vars for basic setup when possible.

If unavoidable, the setup wizard should detect and guide them.

## 26.2 Optional environment variables

Optional integrations may use env vars.

Example:

```yaml
environment:
  - id: OPTIONAL_OCR_TOOL_PATH
    required: false
    capability: subtitle_ocr_when_enabled
    secret: false
```

## 26.3 Secret validation

For secrets:

- Check presence.
- Check format if possible.
- Avoid printing value.
- Redact in logs.
- Prefer secure OS credential storage if available.
- Confirm authentication only if the feature is being enabled.

## 26.4 Secret user message

```text
Optional subtitle OCR tooling is not configured.
This is optional and does not block local processing.

[Configure OCR Tooling]
[Skip]
```

---

# 27. Database and Storage Checks

If the tool uses a database, validate it explicitly.

For V6, JSON/state files remain authoritative and SQLite is a mirror when present. Database checks must not become the only readiness signal, must not repair or rewrite authoritative JSON/manifests by inference, and must not block core readiness solely because the mirror is absent or stale unless the current backend contract says that mode requires it.

## 27.1 Database or mirror checks

- Database or mirror file exists or can be created when that storage layer is active.
- Database or mirror directory is writable.
- Schema version matches expected version.
- Required tables exist.
- Migrations are applied only through the backend-supported path.
- App can open a connection.
- App can perform a read/write smoke test against the mirror without rewriting authoritative JSON/state by inference.
- Corruption detection is reported if supported.

## 27.2 Database state example

```yaml
database:
  id: local_state_db
  type: sqlite
  path: ${state_root}/mediapipeline_state.sqlite3
  required: false
  authority: mirror
  schema_version: 5
  migrations:
    - db.1_to_2
    - db.2_to_3
    - db.3_to_4
    - db.4_to_5
```

## 27.3 Database repair actions

Possible repair actions:

- Create missing mirror, only if the active backend contract expects it.
- Apply migrations only through supported backend migration paths.
- Backup and rebuild the mirror when it is non-authoritative.
- Reset mirror state only.
- Preserve media sources, final outputs, pending-publish payloads, manifests, sidecars, and queue evidence.

## 27.4 User message

```text
MediaPipelineRemuxEncodeAIO V6 needs to update its local state mirror.
Your media files, outputs, pending-publish payloads, manifests, and sidecars will not be deleted.

[Update Mirror]
[View Details]
```

---

# 28. Plugin and Extension Checks

If the tool supports plugins, plugin loading should be verified.

V6 currently has no general media-pipeline plugin system. Treat this section as future-facing guidance only; do not scaffold plugin directories, plugin registries, cloud upload integrations, or plugin lifecycle controls as part of the deployment-verification MVP.

## 28.1 Plugin checks

- Plugin directory exists.
- Plugin manifest exists.
- Plugin manifest schema is valid.
- Plugin entry point exists.
- Plugin can load.
- Plugin declares compatible app version.
- Plugin registers expected commands or pipeline steps.
- Plugin dependencies are available.

## 28.2 Required vs optional plugins

Required built-in plugins may block readiness.

User-installed optional plugins should not block core readiness unless explicitly enabled for a required profile.

## 28.3 Plugin error handling

A broken optional plugin should be isolated.

Example:

```text
One optional plugin failed to load:
AdvancedUploader

Local processing is still ready.

[Disable Plugin]
[View Details]
```

## 28.4 Plugin registry check

The validator should confirm that the registry contains expected items.

Example:

```text
Expected pipeline step: transcode
Actual registry: transcode, extract_metadata, write_output
Result: passed
```

---

# 29. Model, Asset, and Resource Checks

If the app uses models, assets, presets, or sample files, validate them.

For V6, prioritize real existing resources: config profiles, generated schemas, bundled runtimes/tools, WebView/Tauri assets, and controlled test fixtures. Do not add default model downloads or model capability gates unless a real feature requires them.

## 29.1 Asset checks

- File exists.
- File is readable.
- File has expected size or checksum.
- File version is compatible.
- Asset directory is accessible.

## 29.2 Model checks

- Required model file exists.
- Model version is supported.
- Model metadata exists.
- Model can load in smoke-test mode.
- Hardware requirements are available or capability is disabled.

## 29.3 Downloadable assets

If assets can be downloaded:

- Do not force large downloads in first five-minute setup unless essential.
- Mark optional assets as optional.
- Show download size and purpose.
- Verify checksum after download.
- Allow retry.

## 29.4 Asset missing message

```text
The built-in sample file is missing.
Setup cannot prove the pipeline works.

[Repair Installation]
[Create Support Bundle]
```

---

# 30. Pipeline Step Registration Checks

For pipeline-oriented tools, the validator should verify the pipeline registry.

## 30.1 Checks

- Workflow definitions load.
- Each workflow references valid steps.
- Each step is registered.
- Each required step can instantiate.
- Each step dependencies are available.
- Step input/output contracts are compatible.
- Default workflow exists.

## 30.2 Example workflow check

```yaml
pipeline:
  workflows:
    - id: default
      required: true
      steps:
        - extract_metadata
        - transcode
        - write_output
```

Validation:

```text
workflow.default exists
step.extract_metadata registered
step.transcode registered
step.write_output registered
step.extract_metadata output compatible with step.transcode input
step.transcode output compatible with step.write_output input
```

## 30.3 Step contract checks

If possible, each step should declare:

```yaml
step:
  id: transcode
  inputs:
    - media_file
  outputs:
    - transcoded_media_file
  dependencies:
    - ffmpeg
```

This supports automated compatibility checks.

---

# 31. UI-to-Command Wiring Checks

A common hidden failure is UI elements that point to missing commands.

## 31.1 UI action registry

If the app has a UI, define a registry of actions:

```yaml
ui_actions:
  - id: run_pipeline
    label: Run Pipeline
    command: command.run_pipeline
    required: true

  - id: open_output_folder
    label: Open Output Folder
    command: command.open_output_folder
    required: true
```

## 31.2 UI check

Verify:

- Required UI actions exist.
- Each action maps to a real command.
- Command is enabled only when prerequisites are met.
- Disabled actions explain why.
- Critical actions have error handling.

## 31.3 User-visible benefit

The user should not click a button and see nothing happen.

If a command cannot run, the UI should say why:

```text
Run is not available because setup is incomplete.

[Repair Setup]
```

---

# 32. Output Discovery and Output Verification

The app should make outputs easy to find.

## 32.1 Setup output requirements

During setup, verify:

- Configured output root exists or the backend can safely park publish output.
- Output root writability and pending-publish drain readiness are reported separately.
- Output or pending-publish evidence can be opened from the UI.
- Controlled sample proof output appears in the setup-owned expected place.
- Output/pending-publish status is shown on the Ready dashboard.

## 32.2 After job completion

Show:

```text
Job complete.

Created:
- configured-output/video-final.mp4
- configured-output/metadata.json
- logs/job-2026-05-31.log

[Open Output or Pending Evidence]
[Run Another Job]
```

## 32.3 Output manifest

Each job could produce a job output manifest:

```yaml
job_id: job_2026_05_31_104200
status: completed
started_at: "2026-05-31T10:42:00"
completed_at: "2026-05-31T10:42:30"
outputs:
  - type: media
    path: ${outsource_dir}/video-final.mp4
  - type: metadata
    path: ${outsource_dir}/metadata.json
pending_publish:
  parked: false
  manifest_path: ${pending_publish_dir}/job_2026_05_31_104200.json
logs:
  - ${logs_dir}/jobs/job_2026_05_31_104200.log
```

This makes output discovery deterministic.

---

# 33. Sample Project and Functional Proof

A controlled sample or fixture job is strong proof that deployment wiring works. It is not proof of full media-policy correctness for arbitrary real media.

For V6, distinguish:

- **Generated/fixture sample proof:** proves tool discovery, Local API/engine wiring, scratch/local output/log/state behavior, and expected artifact creation in a controlled case.
- **Representative real-media validation:** required after FFmpeg/media-policy, subtitle, audio, publish/drain, source/scratch/output movement, or cleanup behavior changes.

## 33.1 Controlled sample proof requirements

The controlled sample proof should be:

- Tiny.
- Fast.
- Deterministic.
- Included with the app.
- Independent of user files.
- Safe to run repeatedly.
- Easy to clean up.
- Representative of the core workflow.
- Explicitly isolated from real source/output libraries.

## 33.2 Controlled sample proof validation

The controlled sample proof should verify:

- Input file loads.
- Pipeline starts.
- Required dependency executes.
- Output handler writes.
- Expected output exists.
- Log entry is written.
- No fatal errors occur.
- No source media or production library paths are touched.

## 33.3 Expected outputs

Example:

```yaml
expected_outputs:
  - path: ${sample_proof_dir}/sample_output.mp4
    required: true
    min_size_bytes: 1000
  - path: ${sample_proof_dir}/sample_metadata.json
    required: true
    json_schema: schemas/sample_metadata.schema.json
```

## 33.4 Cleanup policy

Options:

- Delete isolated sample outputs after success.
- Keep sample outputs and show them to the user.
- Store sample outputs in a setup verification folder.

Recommended:

- During first setup, keep a visible sample output only if useful.
- During later verification, clean up automatically unless user requests details.

## 33.5 Failure behavior

If the controlled sample proof fails:

```text
MediaPipelineRemuxEncodeAIO V6 could not complete the controlled sample proof.

This means the app is installed, but the processing pipeline is not working yet.

[Repair]
[View Details]
[Create Support Bundle]
```

---

# 34. Auto-Fix System

Auto-fix converts setup problems into guided repairs.

## 34.1 Fix categories

### Safe automatic fixes

Can run without user confirmation:

- Create missing setup-owned state/proof/log folders.
- Generate missing pipeline config through the existing PSD1 settings path.
- Create setup state after successful validation.
- Clean stale temp files only inside known safe setup-owned temp roots, with no active work and no pending-publish/manifest evidence involved.

### Confirmed fixes

Require confirmation:

- Migrate config.
- Reset config to defaults.
- Open Settings for output-root changes.
- Rebuild local database mirror, only if it is not authoritative.
- Disable broken optional plugin, only if a real plugin system exists.

### Manual action required

Cannot be safely automated:

- Install system dependency without package manager support.
- Grant OS-level permission.
- Authenticate external account.
- Repair corrupt app install without installer support.

## 34.2 Fix result model

```yaml
fix_id: fix.create_setup_sample_proof_dir
status: succeeded
message: Created setup-owned sample proof folder.
changed:
  - ${sample_proof_dir}
backup_created: false
requires_recheck: true
```

## 34.3 Fix safety rules

- Never delete user media files automatically.
- Never delete pending-publish parked payloads, completed manifests, queue state, sidecars, or failure evidence as a setup auto-fix.
- Never overwrite pipeline config without backup.
- Never expose secrets in logs.
- Never mark setup ready until checks pass after the fix.
- Never run a fix while backend close-readiness reports active work unless the fix is explicitly designed for that active state.
- Always log what changed.
- Prefer reversible changes.

## 34.4 Fix chaining

A check failure may trigger a fix and then rerun dependent checks.

Example:

```text
check.sample_proof_dir_exists failed
↓
fix.create_setup_sample_proof_dir succeeded
↓
check.sample_proof_dir_exists passed
↓
check.sample_proof_writable passed
```

## 34.5 Auto-fix UI

```text
We found 2 setup issues that can be fixed automatically:

1. Setup proof folder is missing.
2. Logs folder is missing.

[Fix Automatically]
[View Details]
```

---

# 35. Repair Mode

Repair mode handles a setup that used to work but is now broken.

## 35.1 When repair mode opens

Repair mode should open when:

- Setup state says completed but quick check fails.
- Config is invalid.
- Required dependency disappeared.
- Output/pending-publish posture is no longer safe.
- App version requires migration.
- Required plugin no longer loads, only if a real plugin system exists.
- Database or mirror schema is outdated, only if active.

## 35.2 Repair flow

```text
Launcher quick check fails
↓
Open repair screen
↓
Show plain-language problem
↓
Offer recommended fix
↓
Run fix
↓
Rerun validation
↓
Return to Ready or show remaining action
```

## 35.3 Repair screen example

```text
MediaPipelineRemuxEncodeAIO V6 needs repair

Problem:
The configured output root is unavailable, and pending publish cannot safely park output.

Recommended fix:
Open Settings or repair pending-publish state before running media work.

[Fix Automatically]
[Open Settings]
[View Details]
[Create Support Bundle]
```

## 35.4 Repair should preserve data

Repair mode must be cautious.

Rules:

- Preserve user input files.
- Preserve user output files.
- Back up configs before rewriting.
- Ask before disabling plugins, only if a real plugin system exists.
- Ask before resetting state.
- Explain exactly what will change.

---

# 36. Reset Mode

Reset mode is for more serious recovery.

For V6, reset operations must be deliberately narrow and backend-owned. A reset must never delete source media, final outputs, pending-publish parked payloads, completed manifests, queue evidence, sidecars, failure evidence, or validation records unless a future runbook explicitly names and validates that operation.

## 36.1 Reset types

### Reset settings

Resets pipeline config through the existing settings path.

Should not delete source media, final outputs, pending-publish payloads, manifests, queue evidence, sidecars, or validation records.

### Clear cache

Deletes setup-owned temp/cache files only after close-readiness confirms no active work and after excluding pending-publish, completed, queue, sidecar, failure, and validation evidence.

### Rebuild setup roots

Recreates expected setup-owned state, proof, log, and cache roots.

Should not delete existing user files. For V6, this means creating missing roots or showing repair guidance; it is not permission to rewrite source/output/scratch content.

### Reset local database

Rebuilds local state database or mirror only when the database is not authoritative.

Should preserve media outputs and authoritative JSON/manifest evidence.

### Full local reset

Resets config, state, cache, and generated local metadata.

For V6, this should be treated as a future high-risk operation, not an MVP setup feature. It must clearly list what is preserved and what is removed, require explicit confirmation, and use backend-owned runbooks/tests before implementation.

## 36.2 Reset screen

```text
Reset MediaPipelineRemuxEncodeAIO V6 settings?

This will:
✓ Back up your current settings
✓ Restore default local settings
✓ Recreate missing setup-owned folders

This will not:
✗ Delete your source media
✗ Delete final outputs or pending-publish evidence

[Reset Settings]
[Cancel]
```

## 36.3 Backup before reset

Create timestamped backups:

```text
config_backups/
  user_2026-05-31_104200.yaml
  setup_state_2026-05-31_104200.yaml
```

---

# 37. Capability-Based Readiness

Not every feature should block setup.

## 37.1 Capability states

```text
ready
not_configured
degraded
blocked
unsupported
not_installed
unknown
```

## 37.2 Example capability report

```yaml
capabilities:
  core_processing:
    status: ready
    required_for_ready: true
  local_output:
    status: ready
    required_for_ready: true
  batch_processing:
    status: ready
    required_for_ready: false
  optional_ocr:
    status: not_configured
    required_for_ready: false
  browser_smoke_validation:
    status: not_run
    required_for_ready: false
```

## 37.3 Ready logic

Overall app ready if:

- All required capabilities are ready.
- No blocking setup checks failed.
- Controlled sample proof for deployment wiring passed when workflow-proven readiness is required.

Optional capabilities can be unavailable without blocking.

## 37.4 UI example

```text
Ready for local processing

Available:
✓ Core processing
✓ Local output
✓ Batch mode

Optional:
○ Optional OCR not configured
○ Browser smoke validation not run
```

---

# 38. Setup Profiles

Profiles define different valid setup modes.

For V6 MVP, only the Windows-first local operator profile should drive implementation. Developer, server, network-worker, plugin, cloud, model, and portable variations should be documented as future/deferred unless they map cleanly onto existing backend routes and validation.

## 38.1 Recommended profiles

### Basic local

Default for most users.

Goals:

- No terminal.
- No external account.
- No manual config.
- Configured source/output settings stay backend-owned.
- Controlled sample proof included.

### Advanced local

For users who want more control.

May expose:

- Custom paths.
- Existing advanced settings and backend-owned path/tool validation.
- Advanced dependency paths.
- Optional tools that already exist, such as OCR tooling when subtitle OCR is enabled.

### Developer

For contributors.

May include:

- Source checkout validation.
- Test dependencies.
- Development server.
- Hot reload.
- Debug logs.

### Server

For deployment to shared infrastructure.

Future/deferred for the setup-verification MVP.

May include:

- Service account.
- Server paths.
- Port checks.
- Background services.
- Noninteractive setup.

### Portable

For users running from a folder.

May include:

- Relative paths.
- Local state/proof roots inside app folder or sibling folder.
- No system install required.

## 38.2 Profile definition example

```yaml
profiles:
  - id: basic-local
    name: Basic Local Setup
    default: true
    target_user: normal
    required_capabilities:
      - core_processing
      - local_output
    optional_capabilities:
      - optional_ocr
      - browser_smoke_validation
    ask_user_questions:
      - state_root_location_optional
```

## 38.3 Profile-specific checks

Some checks apply only to certain profiles.

Example:

```yaml
checks:
  - id: check.port_available
    profiles: [server]

  - id: check.desktop_launcher
    profiles: [basic-local, advanced-local]
```

---

# 39. Launcher Behavior

The launcher should be smart.

It should not merely start the app.

## 39.1 Launcher algorithm

```text
User starts launcher
↓
Load minimal app runtime
↓
Load manifest
↓
Run quick health check
↓
If no setup state: open first-run setup
↓
If setup state exists and quick check passes: open main app
↓
If setup state exists and quick check fails: open repair mode
↓
If app update requires migration: open migration flow
```

## 39.2 Launcher responsibilities

- Detect first run.
- Detect broken setup.
- Detect incompatible setup version.
- Detect missing core dependencies needed before GUI starts.
- Open setup wizard.
- Open repair wizard.
- Start main app.
- Write launcher logs.

## 39.3 Fallback launchers

Fallback launchers should be existing canonical wrappers, not new root shims:

```text
scripts\dev\start-api-and-browser.bat
scripts\dev\start-tauri-preview.bat
scripts\dev\start-local-api.bat
```

They should:

- Locate the app root.
- Start the launcher.
- Show readable error if runtime is missing.
- Write startup logs.

## 39.4 Launcher should not hide fatal startup errors

If the app cannot start the GUI, show a simple fallback message or write a clear log.

Example:

```text
MediaPipelineRemuxEncodeAIO V6 could not start because the required runtime is missing.

See setup.log for details.
```

---

# 40. CLI Design

Even if normal users never touch the CLI, a CLI is valuable for automation, testing, support, and Codex-driven work.

For V6, do not assume a packaged `mediapipeline` console command exists. The MVP should first wrap or reuse existing canonical scripts and Local API routes: `scripts\verify-env.bat`, `scripts\verify-env.ps1`, `scripts\release\test.ps1`, `scripts\dev\start-local-api.bat`, Settings Wizard routes, Maintenance health/release dry-run routes, and Diagnostics. A future CLI can be added after the command surface is mapped.

## 40.1 Recommended commands

```bash
mediapipeline setup                 # future wrapper; not current V6 command
mediapipeline doctor                # future wrapper; prefer existing scripts first
mediapipeline verify-install --json # future automation shape
mediapipeline run-sample            # future controlled-sample command
mediapipeline collect-support-bundle
```

## 40.2 `setup`

Future wrapper for first-time setup. In current V6, map this to Settings Wizard and canonical setup/verification scripts rather than adding a separate config writer.

Options:

```bash
mediapipeline setup --profile windows-local-operator --accept-defaults
mediapipeline setup --state-root LocalBase\State
mediapipeline setup --skip-controlled-sample
```

`--skip-controlled-sample` may exist for development but should not be used for normal workflow-proven readiness.

## 40.3 `doctor`

Future wrapper for diagnostic checks. In current V6, map this first to `scripts\verify-env.*`, Local API maintenance health, Diagnostics, close-readiness, and route-contract checks.

```bash
mediapipeline doctor
mediapipeline doctor --fix
mediapipeline doctor --json
```

## 40.4 `verify-install`

Future wrapper that checks deployment against the verification manifest. It should not launch media work or mutate config/state.

```bash
mediapipeline verify-install
mediapipeline verify-install --level quick
mediapipeline verify-install --level standard
mediapipeline verify-install --level deep
```

## 40.5 `run-sample`

Future wrapper that runs an isolated generated/fixture sample directly. It must not touch configured source libraries or final output roots unless explicitly designed and validated.

Useful for support:

```bash
mediapipeline run-sample --keep-output
```

## 40.6 `collect-support-bundle`

Creates diagnostic bundle.

```bash
mediapipeline collect-support-bundle
```

Should output path:

```text
Created support bundle:
LocalBase\State\SupportBundles\mediapipeline-support-2026-05-31.zip
```

## 40.7 Exit codes

Use stable exit codes.

Example:

```text
0 = success
1 = general failure
2 = setup incomplete
3 = validation failed
4 = user action required
5 = unsupported platform
6 = dependency missing
7 = config invalid
8 = controlled sample proof failed
```

---

# 41. GUI Wizard Design

The GUI wizard should be the user-friendly surface for the setup orchestrator.

## 41.1 Wizard stages

Recommended stages:

1. Welcome.
2. Recommended setup summary.
3. Settings/path review, optional.
4. Setup progress.
5. User action page, only if needed.
6. Controlled sample proof progress.
7. Ready dashboard.

## 41.2 Wizard should not over-ask

Default setup should require at most one decision:

```text
Use recommended local state and setup-proof paths?
```

Ideally, even that can be accepted by default.

## 41.3 Immediate verification

When the user chooses or changes a path, verify immediately:

- Folder exists or can be created.
- Folder is writable.
- Path is acceptable.
- Enough space exists.
- No obvious platform-specific problem.

## 41.4 Progressive disclosure

Basic view:

```text
Checking setup…
```

Advanced view:

```text
check.required_files: passed
check.output_or_pending_publish_posture: passed
check.ffmpeg_version: passed
```

## 41.5 User action pages

If a problem requires user action, the wizard should stop at a clear page.

Example:

```text
Choose a valid output setting

MediaPipelineRemuxEncodeAIO V6 could not validate the current output/pending-publish posture.
Open Settings to choose a valid output root or repair pending-publish state.

[Open Settings]
[Use Current Safe Default]
[Cancel]
```

## 41.6 Ready page should lead to value

The final page should not merely say done.

It should provide next actions:

```text
[Run First Job]
[Open Input Folder]
[Open Output Folder]
[Settings]
```

---

# 42. Ready Dashboard

The Ready dashboard builds confidence and makes the next step obvious.

## 42.1 Required information

Show:

- Overall readiness.
- Core capability status.
- Source settings status.
- Output/pending-publish status.
- Last verification time.
- Controlled sample proof status.
- Optional features not configured.
- Next action.

## 42.2 Example dashboard

```text
MediaPipelineRemuxEncodeAIO V6 is ready

Verified just now

Core setup:
✓ Required files found
✓ Configuration valid
✓ Dependencies available
✓ Pipeline wiring verified
✓ Output or pending-publish posture validated
✓ Controlled sample proof completed

State:
LocalBase\State

Source settings:
Configured in Settings

Output/publish status:
Writable, or pending publish is safely parked with manifest evidence

Optional:
○ Optional OCR not configured
○ Browser smoke validation not configured

[Run First Job]
[Settings]
[Verify Again]
```

## 42.3 Health summary badge

The app could show a simple status badge:

```text
Deployment: Healthy
```

or:

```text
Deployment: Needs Attention
```

Clicking it opens details.

---

# 43. Error Codes and User-Facing Messages

Stable error codes help debugging and support.

## 43.1 Error code format

Suggested format:

```text
MP-CATEGORY-NUMBER
```

Examples:

```text
MP-FILE-001
MP-CONFIG-002
MP-PERM-003
MP-DEP-004
MP-WIRE-005
MP-SAMPLE-006
```

## 43.2 Error message structure

Each error should have:

- Short user message.
- Problem explanation.
- Recommended fix.
- Technical detail.
- Error code.
- Support bundle option.

## 43.3 Example

```text
MediaPipelineRemuxEncodeAIO V6 cannot validate output/pending-publish posture.

Problem:
The configured output root is unavailable or pending publish cannot safely park output.

Recommended fix:
Choose a writable configured output root or let the backend park output through pending publish.

Error code:
MP-PERM-003

[Choose Different Folder]
[View Details]
[Create Support Bundle]
```

## 43.4 Avoid raw exceptions as primary user messages

Raw exceptions can appear in technical detail, not as the main message.

Bad:

```text
FileNotFoundError: [Errno 2]
```

Good:

```text
A required configuration file is missing.
MediaPipeline can recreate it from the default template.
```

---

# 44. Support Bundle Generator

When setup fails, support should not require the user to manually gather logs.

## 44.1 Bundle contents

Include:

- Setup report.
- Validation report JSON.
- App version.
- OS version.
- Architecture.
- Manifest version.
- Setup state.
- Recent app logs.
- Recent setup logs.
- Dependency versions.
- Config with secrets redacted.
- Path inventory with personal source/output/library roots redacted or summarized.
- Recent migration logs.
- Last controlled sample proof result.
- Error codes.

## 44.2 Do not include

Avoid including:

- API keys.
- Access tokens.
- Passwords.
- User media files.
- Large output files.
- Private project data, personal UNC paths, source/output library roots, machine names, and validation worksheets unless explicitly confirmed and redacted where possible.

## 44.3 Redaction

Redact secrets:

```text
api_key: ****REDACTED****
token: ****REDACTED****
password: ****REDACTED****
C:\Users\Name\Videos\Private Library: <USER_MEDIA_ROOT_REDACTED>
\\SERVER\Share\Movies: <UNC_MEDIA_ROOT_REDACTED>
```

## 44.4 Bundle output

Example:

```text
LocalBase\State\SupportBundles\mediapipeline-support-2026-05-31-104200.zip
```

## 44.5 UI

```text
Create Support Bundle

This will collect diagnostic information, logs, and setup reports.
It will not include your media files or secrets.

[Create Bundle]
[Cancel]
```

---

# 45. Logging Requirements

Setup and repair need high-quality logs.

## 45.1 Log files

Recommended logs:

```text
setup.log
launcher.log
app.log
validation.log
jobs/job_<id>.log
migrations.log
```

## 45.2 Structured logging

Prefer structured logs where possible:

```json
{
  "timestamp": "2026-05-31T10:42:00-04:00",
  "level": "info",
  "event": "check.completed",
  "check_id": "check.output_or_pending_publish_posture",
  "status": "passed",
  "duration_ms": 42
}
```

Plain text is acceptable for human readability, but structured logs make support and automation easier.

## 45.3 Log rotation

Avoid unbounded log growth.

Rules:

- Rotate logs by size or date.
- Keep recent logs.
- Include relevant logs in support bundle.

## 45.4 Logging secrets

Never log secret values.

Mask:

- API keys.
- Tokens.
- Passwords.
- Connection strings.
- Private keys.

---

# 46. Security, Privacy, and Secrets

Setup should be secure by default.

## 46.1 Secret storage

Preferred options:

- OS keychain / credential manager.
- Encrypted local storage.
- Environment variables for advanced/server setups.
- Redacted config fields if no secure option exists.

## 46.2 Secret validation

When validating credentials:

- Ask for permission before contacting external service.
- Do not validate optional integrations during basic setup unless the user enables them.
- Rate-limit repeated validation.
- Never print full secret values.

## 46.3 Least privilege

The setup should not require administrator/root access for basic local use unless absolutely necessary.

## 46.4 File permissions

Generated config files containing sensitive values should have restrictive permissions where possible.

## 46.5 Support bundle privacy

The support bundle should clearly state what it includes.

User should be able to inspect it before sharing.

---

# 47. Platform-Specific Concerns

Windows, macOS, and Linux need separate rules in a generic product. V6 is currently Windows-first, with the promoted operator surface using Tauri/WebView2 plus the local Python API.

For V6 MVP, implement and validate Windows behavior first. macOS/Linux notes below are future reference only.

## 47.1 Windows

Concerns:

- `.exe` launcher.
- Start menu entry.
- Desktop shortcut.
- Existing PSD1 config/template/schema path.
- Configured source/output roots and pending-publish fallback.
- Long path limitations.
- Antivirus quarantine.
- PowerShell execution policy.
- Spaces in paths.
- OneDrive folder locking.
- User Account Control.

Recommended paths:

```text
Config: Pipeline\MediaPipeline_config.psd1
State:  LocalBase\State
Proof:  LocalBase\State\Setup\sample-proof
Logs:   LocalBase\State\Logs
```

## 47.2 macOS

Concerns:

- `.app` bundle.
- Gatekeeper.
- Notarization.
- Application Support directory.
- Documents permissions.
- Apple Silicon vs Intel binaries.
- Quarantine attributes.
- File access privacy prompts.

Recommended paths:

```text
Config: ~/Library/Application Support/MediaPipelineRemuxEncodeAIO
Data:   ~/Documents/MediaPipelineRemuxEncodeAIO
Cache:  ~/Library/Caches/MediaPipelineRemuxEncodeAIO
Logs:   ~/Library/Logs/MediaPipelineRemuxEncodeAIO
```

## 47.3 Linux

Concerns:

- `.desktop` entry.
- AppImage or distro package.
- Executable permissions.
- XDG paths.
- Missing system packages.
- Wayland/X11 GUI differences.
- PATH differences between shell and desktop launch.

Recommended paths:

```text
Config: ~/.config/mediapipeline-remux-encode-aio
Data:   ~/MediaPipelineRemuxEncodeAIO or ~/Documents/MediaPipelineRemuxEncodeAIO
Cache:  ~/.cache/mediapipeline-remux-encode-aio
Logs:   ~/.local/state/mediapipeline-remux-encode-aio/logs
```

## 47.4 Platform-specific manifest fields

```yaml
required_on: [windows]
unsupported_on: [linux]
path_templates:
  windows_state: "LocalBase/State"
  windows_config: "Pipeline/MediaPipeline_config.psd1"
  future_macos_state: "~/Library/Application Support/MediaPipelineRemuxEncodeAIO/State"
  future_linux_state: "~/.local/state/mediapipeline-remux-encode-aio"
```

---

# 48. Packaging and Installer Strategy

The installer should reduce friction, but validation still belongs in the app.

## 48.1 Installer responsibilities

- Place app files.
- Create launcher.
- Register uninstall entry if applicable.
- Include required bundled assets.
- Optionally install bundled dependencies.
- Optionally run a post-install smoke check.

## 48.2 Installer should not be the only verifier

The app should still validate on first run because:

- Installation may be moved.
- Files may be quarantined.
- User permissions may differ.
- Dependencies may not be on PATH in GUI environment.
- Config is user-specific and created after install.

## 48.3 Package formats

Potential package options depending on stack:

- Windows installer.
- Windows portable zip.
- macOS `.dmg` / `.app`.
- Linux AppImage.
- Linux `.deb` / `.rpm`.
- Python wheel with launcher.
- Node/Electron packaged app.
- Docker/server package.

Codex should discover current stack before choosing.

For V6, the active package flow is the existing release builder (`scripts\release\build.ps1`) and Tauri/WebView2 package metadata. Do not add MSI, DMG, AppImage, Docker, Electron, wheel, or server packaging as part of the MVP unless the operator explicitly changes the target.

## 48.4 Bundling dependencies

For five-minute setup, consider bundling hard dependencies when license and size permit.

Examples:

- ffmpeg.
- Local runtime.
- Built-in sample assets.
- Default models, only if a real model feature exists and the assets are small.

If a dependency cannot be bundled, setup must detect it and guide the user.

---

# 49. Portable Mode

Portable mode can greatly reduce setup confusion.

V6 already has a portable-bundle style release flow. Portable validation must preserve the existing package exclusions: no live personal config, no run logs, no runtime state, no `node_modules`, and no Rust target output in clean release packages.

## 49.1 Portable structure

Example:

```text
MediaPipelineRemuxEncodeAIO_V6/
  scripts/dev/start-api-and-browser.bat
  scripts/dev/start-tauri-preview.bat
  DesktopApp/
  Pipeline/
  engine/
  schemas/
  LocalBase/State/
    Setup/sample-proof/
    PendingPublish/
    Logs/
```

## 49.2 Portable mode benefits

- Easy to unzip and run.
- Paths are relative.
- Good for demos.
- Good for users who do not want system install.
- Easier to inspect.

## 49.3 Portable mode risks

- User may put app in read-only folder.
- User may run from Downloads and later move it.
- User may run from inside a zip.
- App updates may overwrite local data if structure is careless.

## 49.4 Portable validation

Portable mode must check:

- App is not running inside archive.
- Setup-owned state/proof/log roots are writable.
- Relative paths resolve.
- App folder can be moved or detects move.
- User data is not overwritten during update.

---

# 50. Update and Upgrade Flow

Updates must be validated like first setup.

## 50.1 Update sequence

```text
App update detected
↓
Load existing setup state
↓
Compare setup schema versions
↓
Run migrations if needed
↓
Run standard validation
↓
Run controlled sample proof if deployment wiring changed; run representative real-media validation if media behavior changed
↓
Update setup state
↓
Open app
```

## 50.2 Version compatibility

Track:

- App version.
- Manifest schema version.
- Setup schema version.
- Config schema version.
- Database or SQLite mirror schema version, if that mirror is active.
- Plugin API version, only if a real plugin system is added.

## 50.3 Update user message

```text
MediaPipelineRemuxEncodeAIO V6 has been updated.
We need to verify your setup before continuing.

[Verify Setup]
```

## 50.4 Failed update behavior

If validation fails after update:

- Open repair mode.
- Offer migration rollback only if supported.
- Preserve old config backups.
- Create support bundle option.

---

# 51. Uninstall and Data Retention

A professional setup system includes clear removal behavior.

## 51.1 Separate app files from user data

Keep these separate:

- App installation files.
- Pipeline config.
- User input.
- User output.
- Logs.
- Cache.
- Downloaded assets.

## 51.2 Uninstall options

```text
Uninstall app only
Uninstall app and remove settings
Uninstall app, settings, and cache
Delete local app state after explicit review
```

The last option must require explicit confirmation and must still exclude user media sources, final outputs, pending-publish parked payloads, completed manifests, sidecars, and evidence needed for recovery unless a separate high-risk runbook explicitly authorizes that exact action.

## 51.3 In-app data management

Settings screen may include:

- Open config folder.
- Open logs folder.
- Open output or pending-publish evidence.
- Clear cache.
- Reset settings.
- Create support bundle.

---

# 52. Clean Machine Testing

The tool must be tested on machines that do not have the developer’s environment.

## 52.1 Why clean machine testing matters

Developer machines hide missing dependencies.

A tool can work locally because:

- Dependencies are already installed.
- Environment variables are set.
- Paths exist.
- Source tree has extra files not included in package.
- The developer runs commands from the correct directory.

Clean testing reveals real user experience.

## 52.2 Test environments

Recommended:

- Clean Windows VM or clean non-admin Windows user account for V6 MVP.
- Clean macOS user account or VM for future non-Windows packaging only.
- Clean Linux VM/container for future non-Windows packaging only.
- Non-admin user account.
- No preconfigured environment variables.
- No developer tools beyond what users are expected to have.

## 52.3 Clean machine test scenario

```text
Install package
Start from desktop/start menu
Accept default setup
Run validation
Run controlled sample proof
Run first real job or test fixture
Open output or pending-publish evidence
Restart app
Verify quick check passes
Break output/pending-publish posture intentionally
Verify repair mode opens
```

---

# 53. Broken Install Test Matrix

The setup system should be tested against intentionally broken states.

## 53.1 File and directory failures

- Missing manifest.
- Missing config template.
- Missing pipeline config.
- Corrupt pipeline config.
- Missing setup proof folder.
- Unsafe output/pending-publish posture.
- Missing logs folder.
- App installed in read-only location.
- Running from inside zip.

## 53.2 Dependency failures

- Required executable missing.
- Required executable too old.
- Required executable found but fails smoke test.
- Dependency path contains spaces.
- Dependency exists in shell PATH but not GUI PATH.
- Optional dependency missing.

## 53.3 Config failures

- Missing required field.
- Wrong field type.
- Deprecated config version.
- Config points to old absolute path.
- Config points to network path.
- Config has unresolved template variable.

## 53.4 Wiring failures

- UI action references missing command.
- Command references missing pipeline workflow.
- Workflow references missing step.
- Step missing dependency.
- Future plugin loads but does not register expected capability.
- Output handler missing.

## 53.5 Runtime failures

- Controlled sample input missing.
- Controlled sample proof times out.
- Controlled sample output not created.
- Log file cannot be written.
- Database or mirror schema outdated, if active.
- Cache folder locked.

## 53.6 User behavior failures

- User cancels setup halfway.
- User runs setup twice.
- User moves configured source/output roots after setup.
- User renames app folder.
- User deletes setup proof folder or breaks pending-publish state.
- User modifies config manually.
- User downgrades app version.

---

# 54. Automated Test Strategy

## 54.1 Unit tests

Test individual checks and fixers.

Examples:

- Path resolver.
- Config schema validator.
- Version parser.
- Dependency checker.
- Permission checker.
- Manifest loader.
- Migration functions.

## 54.2 Integration tests

Test setup flows in temporary directories.

Examples:

- Create new setup-owned state/proof roots.
- Create setup-owned state/proof roots.
- Generate or validate pipeline config through the settings path.
- Validate setup-proof write and output/pending-publish posture.
- Run fake dependency.
- Simulate missing files.

## 54.3 End-to-end tests

Test full first-run flow.

Examples:

- Launch app.
- Complete setup with defaults.
- Run controlled generated/fixture sample proof.
- Confirm Ready dashboard.

## 54.4 Golden install tests

Create a known-good packaged install and verify:

- Manifest loads.
- All shipped files present.
- Controlled generated/fixture sample proof passes.
- Launcher works.

## 54.5 Broken install tests

Generate controlled broken installs from the matrix above.

Each test should assert:

- Problem is detected.
- User message is clear.
- Correct error code is returned.
- Auto-fix works if available.
- Setup is not marked ready until revalidation passes.

## 54.6 Noninteractive tests

Use CLI JSON output for CI:

```bash
mediapipeline verify-install --json
```

CI can parse this and fail builds if readiness fails.

---

# 55. Release Gate Checklist

Before shipping a release, verify:

## 55.1 Build validation

- Package builds successfully.
- Manifest included.
- Config templates included.
- Schemas included.
- Sample assets included.
- Launchers included.
- Required executable permissions set.

## 55.2 Fresh install validation

- Install on clean machine.
- Launch via normal user path.
- Complete default setup.
- Run controlled generated/fixture sample proof.
- Confirm Ready dashboard.
- Run first real fixture job.
- Open output or pending-publish evidence.
- Restart app.
- Quick check passes.

## 55.3 Repair validation

- Break output/pending-publish posture.
- Relaunch app.
- Repair mode detects issue.
- Auto-fix repairs setup-owned roots or directs the operator to Settings.
- App returns to ready.

## 55.4 Update validation

- Install previous version.
- Complete setup.
- Install new version.
- Migration runs.
- Validation passes.
- User data preserved.

## 55.5 Packaging validation

- No source-only files required at runtime.
- No developer absolute paths.
- No hidden local dependencies.
- No missing resources.
- No README-only setup steps.

---

# 56. Implementation Roadmap

This is a large undertaking, so implement in phases.

## 56.1 Phase 1: One obvious start path

Deliverables:

- One obvious promoted start path using existing canonical launchers.
- No new root launcher shims; for V6 use `scripts\dev\start-api-and-browser.bat`, `scripts\dev\start-tauri-preview.bat`, or the current promoted equivalent.
- Clear first screen.
- Basic setup-owned state/proof/log path creation.
- Clear output/pending-publish posture display.

Success criteria:

- User can start without knowing internal files.
- User knows where settings, output/pending-publish evidence, logs, and support bundles are surfaced.

## 56.2 Phase 2: Manifest and basic validation

Deliverables:

- Deployment manifest.
- Manifest loader.
- Required file checks.
- Required directory checks.
- Config existence check.
- Output write check.
- Logs write check.

Success criteria:

- App can say whether basic setup files and folders are valid.

## 56.3 Phase 3: Config generation and schema validation

Deliverables:

- Config template.
- Config schema.
- Config generator.
- Config validator.
- Setup state file.

Success criteria:

- Missing config can be generated.
- Invalid config is caught before use.

## 56.4 Phase 4: Dependency checks

Deliverables:

- Dependency registry.
- Version detection.
- Required vs optional dependency handling.
- Clear missing dependency messages.

Success criteria:

- Missing dependencies fail early with actionable guidance.

## 56.5 Phase 5: Wiring verification

Deliverables:

- Component registry or adapter around existing registries.
- Wiring graph definition.
- UI/command/pipeline checks.
- Step registration checks; plugin checks only if a real plugin system exists.

Success criteria:

- Files can exist but bad wiring is still detected.

## 56.6 Phase 6: Controlled sample proof

Deliverables:

- Built-in generated or fixture sample input.
- Isolated sample workflow that never touches real source libraries or final output roots.
- Expected output validation.
- Controlled sample proof UI progress.

Success criteria:

- Setup can distinguish configured-ready from workflow-proven, and workflow-proven is not granted until the isolated sample passes.

## 56.7 Phase 7: Repair mode

Deliverables:

- Launcher quick check.
- Repair screen.
- Auto-fix engine.
- Support bundle.

Success criteria:

- Broken post-setup states recover without README or AI.

## 56.8 Phase 8: Release automation

Deliverables:

- CI validation.
- Clean install tests.
- Broken install tests.
- Release gate checklist automation.

Success criteria:

- Broken packages are caught before users get them.

---

# 57. MVP Scope

The MVP should prove the architecture without trying to solve everything at once.

## 57.1 MVP must-have features

- One launcher.
- Basic local setup profile.
- State/setup-proof path verification and creation.
- Pipeline config generation or validation through the existing PSD1 Settings Wizard/save path.
- Config schema validation.
- Required file and directory checks.
- Local output or pending-publish posture check.
- Logs write check.
- Required dependency checks.
- Setup state file.
- Ready screen.
- Verify Deployment action.
- Basic repair for missing setup-owned folders/config.
- Explicit V6 safety boundary text: no source mutation, no direct frontend config/state/media writes, no pending-publish bypass, no root launcher shims.

## 57.2 MVP should-have features

- Controlled generated/fixture sample proof for workflow-proven status.
- Internal or script-backed doctor command; packaged CLI can be deferred.
- Machine-readable verify output; packaged `mediapipeline verify-install --json` can be deferred.
- Support bundle.
- Basic wiring graph.

## 57.3 MVP can defer

- Full plugin system validation.
- Deep checksums for every file.
- Advanced profiles.
- Remote analytics.
- Full installer integration.
- Complex database repair.
- Optional cloud integration validation, unless a real cloud feature is added.

## 57.4 MVP success criteria

A fresh user can:

```text
Open launcher
Accept defaults
Pass setup checks
See Ready dashboard
Open Settings or verified output/pending-publish evidence
Run controlled sample proof or first explicitly selected job
Restart app successfully
```

---

# 58. Future Enhancements

Potential enhancements after MVP:

- Full wiring graph visualization.
- Self-healing repair install.
- Dependency auto-installation.
- Plugin marketplace validation.
- Remote support upload with user permission.
- Setup analytics with opt-in.
- Multi-user profiles.
- Server deployment mode.
- Portable update manager.
- Full rollback support.
- Environment snapshot comparison.
- Job replay diagnostics.
- Preflight check before every large job.

---

# 59. Codex Discovery Instructions

Before implementing, Codex should inspect the actual repository.

## 59.1 Discover current entry points

Find:

- Main app entrypoint.
- Existing wizard entrypoint.
- CLI entrypoint, if any.
- Existing launch scripts.
- Package configuration.
- Installer scripts.
- GUI app bootstrap.

Questions:

- What file does the user currently run?
- Are there multiple competing start paths?
- Is there a packaged executable?
- Is there a CLI command?

## 59.2 Discover current config system

Find:

- Config files.
- Default config templates.
- Schema files, if any.
- `.env` usage.
- Path resolution logic.
- User settings storage.
- Config migration code.

Questions:

- Is config generated or manually edited?
- Are paths absolute or relative?
- Is there a schema?
- Are secrets stored in config?

## 59.3 Discover current wizard

Find:

- Wizard screens/components.
- What the wizard asks.
- What files the wizard writes.
- What validation the wizard performs.
- What happens after wizard completion.

Questions:

- Does the wizard verify output writability?
- Does it validate dependencies?
- Does it verify wiring?
- Does it run a controlled sample proof?
- Does it create setup state?

## 59.4 Discover pipeline architecture

Find:

- Workflow definitions.
- Step registration system.
- Command handlers.
- Output handlers.
- Plugin architecture.
- Dependency calls.

Questions:

- How are pipeline steps registered?
- Can steps declare input/output contracts?
- What is the minimal controlled sample proof?
- Which dependencies are required for core workflow?

## 59.5 Discover UI command architecture

Find:

- Buttons/actions.
- Command registry.
- Event handlers.
- Menu actions.
- Disabled-state logic.

Questions:

- Can UI actions be enumerated?
- Can command existence be checked statically?
- How does the Run button reach the pipeline?

## 59.6 Discover output model

Find:

- Output directory logic.
- Job result structure.
- Logs.
- Metadata files.
- User-facing completion screen.

Questions:

- Where do outputs go?
- Does the app show outputs clearly?
- Is there a job manifest?

## 59.7 Discover packaging

Find:

- Build scripts.
- Package definitions.
- Installer config.
- Runtime bundled files.
- Resource inclusion rules.

Questions:

- Are templates and sample assets included in packaged builds?
- Are file permissions preserved?
- Are dependencies bundled?

## 59.8 Discover tests

Find:

- Existing unit tests.
- Integration tests.
- End-to-end tests.
- CI config.
- Test fixtures.

Questions:

- Can setup be tested in temp dirs?
- Are broken install scenarios covered?
- Is there a sample fixture already?

---

# 60. Codex Implementation Prompt

The following prompt can be used later with Codex after this planning document is added to the repository.

```text
You are working in this repository. Read the deployment verification planning document at its actual repository path, then read AGENTS.md, Docs/CURRENT_PROJECT_STATE.md, OPEN_WORK_CHECKLIST.md, and Docs/generated/PROJECT_INDEX.md before touching code.

Goal:
Implement the first MVP slice of a one-click setup and deployment verification system without renaming existing architecture unnecessarily.

First, inspect the repository and report:
1. Current app entry points.
2. Current wizard architecture.
3. Current config files and config loading flow.
4. Current pipeline/workflow/command registration architecture.
5. Current output/log path behavior.
6. Current packaging/build behavior.
7. Current tests.

Then propose a minimal implementation plan that maps the document concepts onto existing files and names.

MVP requirements:
- One obvious launcher or existing launcher improvement.
- Deployment manifest loaded from repository resources.
- Basic local setup profile.
- Setup-owned state/proof/log path creation.
- Pipeline config generation or validation through the existing PSD1 Settings Wizard/save path.
- Config schema validation.
- Required file and directory checks.
- Output/pending-publish posture check.
- Logs write check.
- Required dependency checks.
- Setup state under the existing V6 state-root model.
- Internal or script-backed doctor command; do not require a packaged CLI for MVP.
- Ready/repair status that the wizard can display.

Constraints:
- Preserve existing user data.
- Do not overwrite existing pipeline config without backup.
- Do not require manual README steps for basic setup.
- Keep optional integrations optional.
- Do not introduce root launcher shims, a parallel YAML config system, frontend-owned media mutation, pending-publish bypass, direct queue/settings/state writes from WebView, or a new source of truth for media policy.
- Treat generated sample proof as deployment evidence only; real-media validation remains required after high-risk media behavior changes.
- Add tests for missing config, invalid config, missing setup-owned folder, unsafe output/pending-publish posture, and missing dependency.

Deliver:
1. Architecture mapping.
2. File-level change plan.
3. Implementation in small commits/patches.
4. Tests.
5. Updated documentation for developers only, not as a requirement for normal users.
```

---

# 61. Open Design Questions

Codex or the developer should answer these after repository inspection.

## 61.0 Current V6 answers from repository inspection

Inspection date: 2026-05-31.

Repository inspected:
`C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V6`

Primary evidence:
`README.md`, `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`,
`Docs/inventories/API_ROUTE_INVENTORY.md`,
`Docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`,
`Docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`,
`Docs/inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`,
`Docs/inventories/PACKAGING_DEPENDENCY_INVENTORY.md`,
`Docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md`,
and `Docs/testing/TEST_COVERAGE_MATRIX.md`.

These answers describe the current repository state only. They do not approve
new code changes, media-policy changes, source-file mutation, or launcher
surface changes.

Product answers:

1. The smallest useful setup proof should be a generated-media or tiny sample
   run that proves config loading, bundled runtime/tool discovery,
   source-to-scratch isolation, FFmpeg/ffprobe availability, local output
   write, log/state write, and completed/pending-publish evidence. Real-media
   proof remains the higher release gate for media-policy changes.
2. The default user is a Windows desktop, single-operator Plex-style library
   operator. Developer, server, and network-worker modes exist but should not
   block the basic local ready state.
3. First readiness requires the local API to start, the WebView/Tauri shell or
   browser surface to open, the PSD1 config to validate, source/output/scratch
   roots to resolve safely, required bundled tools to be available, backend
   route contracts to load, close-readiness to be safe, and no source mutation
   to be required.
4. Optional features that should not block basic setup include Network lifecycle
   controls, final-library promotion, OCR tooling unless OCR conversion is
   enabled, browser-smoke tooling, Node/Rust build tooling, and package-build
   workflows.
5. The expected five-minute path is Windows-first: run the canonical launcher
   under `scripts\dev\`, complete or verify Settings Wizard fields, validate
   tools and paths, and reach the WebView/Tauri Ready/Launch state. macOS and
   Linux are not promoted operator targets in this repository.

Architecture answers:

1. No dedicated shipped deployment setup manifest exists yet. Current package
   evidence is generated as `release_manifest.json` by
   `scripts\release\build.ps1`; setup state and runtime evidence belong under
   `LocalBase\State`.
2. A future deployment manifest should use JSON with a checked schema, matching
   the existing generated schemas in `schemas\` and `Pipeline\Schemas\`.
   PowerShell PSD1 remains the live pipeline config format.
3. Config schema support already exists in `schemas\config.v1.schema.json`,
   `Pipeline\Schemas\media_pipeline_config.schema.json`, and
   `app\contracts\config.py`.
4. Command and route registries already exist through `app\api\commands.py`,
   `app\contracts\api_commands.py`, and the Local API contract documents.
   Stage contracts exist in `app\contracts\stages.py` with read-only
   `probe` and `decide` currently enabled through `engine\entrypoint.ps1`.
5. UI actions are enumerable through WebView assets, command-route inventory,
   generated WebView public-contract/route-ownership baselines, and static
   tests such as `DesktopApp\tests\test_application_facade_web_static.py`.
6. Setup state should be stored under `LocalBase\State\App` or a sibling
   `LocalBase\State\Setup` area, not in the install root. The current Settings
   Wizard already records completion through app state.
7. Doctor should be GUI/internal-first for the operator, with CLI wrappers for
   support. The existing support-side pieces are `scripts\verify-env.bat`,
   `scripts\verify-env.ps1`, Local API maintenance routes, and Diagnostics.

Packaging answers:

1. Required bundled dependencies are PowerShell 7, Python, FFmpeg/ffprobe, and
   MKVToolNix `mkvmerge`. PgsToSrt is bundled as an optional OCR capability.
   Node.js, Chrome/Edge, and Rust/Cargo are validation/build dependencies, not
   required for normal media processing.
2. Supported package flow is the repository release builder:
   `scripts\release\build.ps1` creates a clean deployable folder/zip and
   writes `release_manifest.json`. Tauri package metadata lives under
   `DesktopApp\tauri_shell\src-tauri\`.
3. Resource inclusion is documented in
   `Docs\inventories\RELEASE_PACKAGE_ADMIN_INVENTORY.md`; it includes engine,
   desktop app, schemas, templates, bundled runtimes/tools, and excludes live
   personal config, run logs, runtime state, `node_modules`, and Rust targets.
4. Launchers are canonical under `scripts\dev\`: `start-local-api.bat`,
   `start-api-and-browser.bat`, `start-tauri-preview.bat`, `setup.bat`, and
   `run.bat`. Removed root launcher shims must not be reintroduced.
5. Platform constraints are Windows-first operation, WebView2/Tauri shell,
   PowerShell 7, local bearer-token API auth, safe path handling, and package
   exclusion of private operator config/state.

Testing answers:

1. Much of setup can be tested headlessly through bundled Python unittest
   suites, PowerShell unit wrappers, and Local API smoke tests. Tauri live
   preview and browser rendering require GUI/browser availability.
2. Generated-media and fixture-backed smokes can run in automation; real-media
   validation remains operator/manual evidence and must be rerun after
   FFmpeg/media-policy, subtitle, audio, publish/drain, source/scratch/output,
   or cleanup behavior changes.
3. Many dependencies can be mocked or fixture-backed in Python tests. Tool
   integration and release gates intentionally verify real bundled tools.
4. Broken install states can be represented with temporary directories for
   config/path/dependency tests, but a full deployment-verification broken
   install matrix is not yet implemented as a single setup system.
5. A `.github\workflows\phase1-drift.yml` workflow exists. Clean-machine
   package/open/close evidence is currently manual/operator-attested rather
   than a fully automated matrix.

## 61.1 Product questions

Answered for current V6 in section 61.0; keep this list as a future revalidation checklist if the target platform or product scope changes.

1. What is the smallest useful workflow the controlled sample proof should demonstrate?
2. Is the default user a nontechnical desktop user, a developer, or a server operator?
3. Which features are required for first readiness?
4. Which features are optional and should not block setup?
5. What is the expected five-minute path on each platform?

## 61.2 Architecture questions

Answered for current V6 in section 61.0; keep this list as a future revalidation checklist if the architecture changes.

1. Where should the deployment manifest live?
2. What format should the manifest use?
3. Is there already a config schema system?
4. Is there already a registry for commands or pipeline steps?
5. Can UI actions be enumerated?
6. How should setup state be stored?
7. Should doctor be CLI-first, GUI-first, or internal-first?

## 61.3 Packaging questions

Answered for current V6 in section 61.0; keep this list as a future revalidation checklist if packaging targets change.

1. Are dependencies bundled or external?
2. What installer/package formats are supported?
3. How are resources included in builds?
4. How are launchers created?
5. What are platform-specific constraints?

## 61.4 Testing questions

Answered for current V6 in section 61.0; keep this list as a future revalidation checklist if automation or clean-machine targets change.

1. Can the app run headlessly for setup tests?
2. Can controlled sample proofs run in CI?
3. Can dependencies be mocked?
4. Can broken install states be generated in temp dirs?
5. What clean-machine environments are available?

---

# Appendix A: Example Manifest

This is a full illustrative manifest. It is not final. Codex should adapt it to the real repository.

For V6, this example must be translated before implementation: replace YAML with the selected JSON/schema convention, replace `MediaPipeline` with `MediaPipelineRemuxEncodeAIO V6`, replace `user.yaml` with the existing PSD1 config/template/schema flow, replace generic resources paths with current `Pipeline\`, `DesktopApp\`, `engine\`, `schemas\`, and `scripts\` paths, and remove cloud/plugin entries unless a real feature owns them.

```yaml
manifest_schema_version: 1

app:
  id: mediapipeline-remux-encode-aio-v6
  name: MediaPipelineRemuxEncodeAIO V6
  version: v6.000
  required_setup_schema_version: 1
  min_supported_setup_schema_version: 1

profiles:
  - id: windows-local-operator
    name: Windows Local Operator Setup
    default: true
    required_capabilities:
      - core_processing
      - local_output
    optional_capabilities:
      - optional_subtitle_ocr
      - browser_smoke_validation

path_roots:
  install_root:
    type: app_install
    windows: "<package_or_repo_root>"
  state_root:
    type: v6_local_state
    windows: "LocalBase/State"
  sample_proof_root:
    type: setup_owned_workdir
    windows: "LocalBase/State/Setup/sample-proof"
  logs_root:
    type: v6_logs
    windows: "LocalBase/State/Logs"

entrypoints:
  - id: start_api_and_browser
    name: Start Local API and Browser
    path: scripts/dev/start-api-and-browser.bat
    required: true
  - id: start_tauri_preview
    path: scripts/dev/start-tauri-preview.bat
    required: false

files:
  - id: deployment_manifest
    path: ${install_root}/DesktopApp/mediapipeline_desktop_app/resources/deployment_manifest.json
    required: true
    origin: shipped
    purpose: Deployment contract

  - id: pipeline_config_template
    path: ${install_root}/Pipeline/MediaPipeline_config_template.psd1
    required: true
    origin: shipped
    purpose: Template for active pipeline config

  - id: config_schema
    path: ${install_root}/schemas/config.v1.schema.json
    required: true
    origin: shipped
    purpose: Config schema

  - id: controlled_sample_input
    path: ${install_root}/Pipeline/TestFixtures/generated_sample.mp4
    required: true
    origin: shipped
    purpose: Controlled deployment-proof sample input

  - id: active_pipeline_config
    path: ${install_root}/Pipeline/MediaPipeline_config.psd1
    required: true
    origin: generated
    template: pipeline_config_template
    schema: config_schema
    can_create: true
    can_migrate: true
    purpose: Active pipeline configuration

  - id: setup_state
    path: ${state_root}/Setup/setup_state.json
    required: true
    origin: generated
    can_create_after_validation: true
    purpose: Durable setup status

directories:
  - id: state_root
    path: ${state_root}
    required: true
    can_create: true
    writable: true
    purpose: Backend-owned runtime state

  - id: sample_proof_dir
    path: ${sample_proof_root}
    required: true
    can_create: true
    writable: true
    cleanup_allowed: true
    purpose: Setup-owned controlled sample output

  - id: pending_publish_dir
    path: ${state_root}/PendingPublish
    required: true
    can_create: true
    writable: true
    cleanup_allowed: false
    purpose: Parked publish evidence and payloads

  - id: logs_dir
    path: ${logs_root}
    required: true
    can_create: true
    writable: true
    purpose: Logs

dependencies:
  - id: python_runtime
    type: runtime
    required: true
    path: ${install_root}/DesktopApp/Runtime/Python/python.exe
    capability: core_processing

  - id: ffmpeg
    type: executable
    command: ffmpeg
    required: true
    min_version: "5.0"
    version_arg: "-version"
    capability: core_processing
    help_id: help.install_ffmpeg

  - id: ffprobe
    type: executable
    command: ffprobe
    required: true
    min_version: "5.0"
    version_arg: "-version"
    capability: media_metadata

configs:
  - id: pipeline_config
    path: ${install_root}/Pipeline/MediaPipeline_config.psd1
    schema: ${install_root}/schemas/config.v1.schema.json
    template: ${install_root}/Pipeline/MediaPipeline_config_template.psd1
    required_version: 1
    can_generate: true
    can_migrate: true

capabilities:
  - id: core_processing
    name: Core Processing
    required_for_ready: true
    checks:
      - check.required_files
      - check.required_directories
      - check.pipeline_config_valid
      - check.dependencies_required
      - check.pipeline_registry
      - check.sample_job

  - id: local_output
    name: Local Output
    required_for_ready: true
    checks:
      - check.output_or_pending_publish_posture
      - check.open_output_or_pending_evidence_supported

  - id: optional_subtitle_ocr
    name: Subtitle OCR When Enabled
    required_for_ready: false
    checks:
      - check.ocr_tooling_available
      - check.ocr_failure_routes_to_review

wiring:
  - id: ui_run_action_to_command
    from: ui.action.run_pipeline
    edge: triggers
    to: command.run_pipeline
    required: true

  - id: command_to_default_workflow
    from: command.run_pipeline
    edge: uses
    to: pipeline.workflow.default
    required: true

  - id: default_workflow_to_transcode_step
    from: pipeline.workflow.default
    edge: uses
    to: pipeline.step.transcode
    required: true

  - id: transcode_step_to_ffmpeg
    from: pipeline.step.transcode
    edge: requires
    to: dependency.ffmpeg
    required: true

  - id: default_workflow_to_output
    from: pipeline.workflow.default
    edge: writes
    to: directory.sample_proof_dir
    required: true

sample_jobs:
  - id: controlled_fixture_job
    name: Controlled fixture deployment proof
    required_for_ready: true
    input: ${install_root}/Pipeline/TestFixtures/generated_sample.mp4
    output_dir: ${sample_proof_root}
    expected_outputs:
      - path: ${sample_proof_root}/sample_output.mp4
        required: true
        min_size_bytes: 1000
      - path: ${sample_proof_root}/sample_manifest.json
        required: true
    timeout_seconds: 60
    cleanup_after_success: true

checks:
  - id: check.required_files
    type: file_presence
    level: install_integrity
    required_for_ready: true

  - id: check.required_directories
    type: directory_presence
    level: runtime_readiness
    required_for_ready: true

  - id: check.sample_proof_writable
    type: write_test
    target: directory.sample_proof_dir
    level: runtime_readiness
    required_for_ready: true

  - id: check.pipeline_config_valid
    type: config_schema
    target: config.pipeline_config
    level: runtime_readiness
    required_for_ready: true

  - id: check.dependencies_required
    type: dependency_check
    level: runtime_readiness
    required_for_ready: true

  - id: check.wiring
    type: wiring_graph
    level: wiring_correctness
    required_for_ready: true

  - id: check.sample_job
    type: sample_job
    target: sample_job.controlled_fixture_job
    level: functional_proof
    required_for_ready: true
```

---

# Appendix B: Example Check Interface

This is conceptual pseudocode. Codex should adapt to the repository language and style.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"
    FIXED = "fixed"
    NEEDS_USER_ACTION = "needs_user_action"
    UNKNOWN = "unknown"

class Severity(str, Enum):
    BLOCKER = "blocker"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class UserAction:
    id: str
    label: str
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)

@dataclass
class CheckResult:
    check_id: str
    status: CheckStatus
    severity: Severity
    message: str
    technical_detail: Optional[str] = None
    capability: Optional[str] = None
    error_code: Optional[str] = None
    fix_available: bool = False
    fix_id: Optional[str] = None
    user_action_required: bool = False
    user_actions: list[UserAction] = field(default_factory=list)
    duration_ms: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

class CheckContext:
    def __init__(self, manifest, resolved_paths, config, platform_info, logger):
        self.manifest = manifest
        self.resolved_paths = resolved_paths
        self.config = config
        self.platform_info = platform_info
        self.logger = logger

class BaseCheck:
    id: str
    required_for_ready: bool = False

    def run(self, context: CheckContext) -> CheckResult:
        raise NotImplementedError

class SetupProofWritableCheck(BaseCheck):
    id = "check.sample_proof_writable"
    required_for_ready = True

    def run(self, context: CheckContext) -> CheckResult:
        proof_dir = context.resolved_paths["sample_proof_dir"]
        test_file = proof_dir / ".mediapipeline-write-test"
        try:
            proof_dir.mkdir(parents=True, exist_ok=True)
            test_file.write_text("write test", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return CheckResult(
                check_id=self.id,
                status=CheckStatus.PASSED,
                severity=Severity.INFO,
                message="Setup proof folder is writable.",
                technical_detail=f"Write test succeeded at {proof_dir}",
                capability="core_processing",
            )
        except Exception as exc:
            return CheckResult(
                check_id=self.id,
                status=CheckStatus.FAILED,
                severity=Severity.BLOCKER,
                message="MediaPipelineRemuxEncodeAIO V6 cannot write to the setup proof folder.",
                technical_detail=str(exc),
                capability="core_processing",
                error_code="MP-PERM-003",
                fix_available=True,
                fix_id="fix.create_setup_sample_proof_dir",
                user_action_required=True,
                user_actions=[
                    UserAction(
                        id="open_settings",
                        label="Open Settings",
                        action_type="open_settings",
                    )
                ],
            )
```

---

# Appendix C: Example Setup Report

```yaml
report_type: setup_verification
app:
  id: mediapipeline-remux-encode-aio-v6
  version: v6.000
manifest:
  schema_version: 1
setup:
  profile: windows-local-operator
  setup_schema_version: 1
  status: ready
  completed_at: "2026-05-31T10:42:00-04:00"
paths:
  state_root: "LocalBase/State"
  sample_proof: "LocalBase/State/Setup/sample-proof"
  pending_publish: "LocalBase/State/PendingPublish"
  logs: "LocalBase/State/Logs"
capabilities:
  core_processing: ready
  local_output: ready
  optional_subtitle_ocr: not_configured
checks:
  - id: check.required_files
    status: passed
    duration_ms: 12
  - id: check.required_directories
    status: passed
    duration_ms: 8
  - id: check.pipeline_config_valid
    status: passed
    duration_ms: 15
  - id: check.dependencies_required
    status: passed
    duration_ms: 120
  - id: check.wiring
    status: passed
    duration_ms: 32
  - id: check.sample_job
    status: passed
    duration_ms: 3180
warnings:
  - id: capability.optional_subtitle_ocr.not_configured
    message: Optional subtitle OCR tooling is not configured.
```

---

# Appendix D: Error Code Catalog

This catalog should grow as the system matures.

## File errors

| Code | Meaning | Default action |
|---|---|---|
| MP-FILE-001 | Required shipped file missing | Repair installation |
| MP-FILE-002 | Required generated file missing | Generate from template |
| MP-FILE-003 | File integrity check failed | Repair installation |
| MP-FILE-004 | Required file not readable | Check permissions |
| MP-FILE-005 | Sample input missing | Repair installation |

## Directory errors

| Code | Meaning | Default action |
|---|---|---|
| MP-DIR-001 | Required directory missing | Create automatically |
| MP-DIR-002 | Directory path invalid | Ask user to choose path |
| MP-DIR-003 | Directory cannot be created | Ask user to choose path |
| MP-DIR-004 | Running from unsupported location | Move app or choose supported state root |

## Permission errors

| Code | Meaning | Default action |
|---|---|---|
| MP-PERM-001 | Config directory not writable | Choose config location or fix permission |
| MP-PERM-002 | Logs directory not writable | Choose logs location or fix permission |
| MP-PERM-003 | Output/pending-publish posture unsafe | Open Settings or repair pending-publish state |
| MP-PERM-004 | Temp directory not writable | Recreate temp directory |
| MP-PERM-005 | Script not executable | Fix executable permission where possible |

## Config errors

| Code | Meaning | Default action |
|---|---|---|
| MP-CONFIG-001 | Pipeline config missing | Generate through existing settings/template path |
| MP-CONFIG-002 | Config schema invalid | Repair field or restore default |
| MP-CONFIG-003 | Config version too old | Run migration |
| MP-CONFIG-004 | Config version too new | Update app or choose different config |
| MP-CONFIG-005 | Config references missing path | Create path or choose new path |
| MP-CONFIG-006 | Config contains unresolved template variable | Regenerate or repair config |

## Dependency errors

| Code | Meaning | Default action |
|---|---|---|
| MP-DEP-001 | Required dependency missing | Install or choose path |
| MP-DEP-002 | Dependency version too old | Update dependency |
| MP-DEP-003 | Dependency found but failed smoke test | Choose different dependency or reinstall |
| MP-DEP-004 | Runtime version unsupported | Install supported runtime |
| MP-DEP-005 | Optional dependency missing | Mark optional capability unavailable |

## Wiring errors

| Code | Meaning | Default action |
|---|---|---|
| MP-WIRE-001 | UI action references missing command | Repair app or update wiring |
| MP-WIRE-002 | Command references missing workflow | Repair app or update wiring |
| MP-WIRE-003 | Workflow references missing step | Repair app or step registry |
| MP-WIRE-004 | Step references missing dependency | Install dependency |
| MP-WIRE-005 | Output handler missing | Repair app or choose handler |
| MP-WIRE-006 | Future plugin failed to register expected component | Disable or repair plugin only if plugin system exists |

## Controlled sample proof errors

| Code | Meaning | Default action |
|---|---|---|
| MP-SAMPLE-001 | Controlled sample input missing | Repair installation |
| MP-SAMPLE-002 | Controlled sample proof failed | View details / support bundle |
| MP-SAMPLE-003 | Controlled sample proof timed out | Check dependency/performance |
| MP-SAMPLE-004 | Expected output missing | Check pipeline/output handler |
| MP-SAMPLE-005 | Sample output invalid | Check pipeline version |

## Database errors

| Code | Meaning | Default action |
|---|---|---|
| MP-DB-001 | Database or mirror missing | Create mirror only if active |
| MP-DB-002 | Database or mirror schema outdated | Run migrations only if backend contract requires it |
| MP-DB-003 | Database or mirror schema too new | Update app or choose data dir |
| MP-DB-004 | Database or mirror not writable | Fix permissions if mirror is active |
| MP-DB-005 | Database or mirror appears corrupt | Backup and rebuild mirror only if non-authoritative |

## Setup state errors

| Code | Meaning | Default action |
|---|---|---|
| MP-STATE-001 | Setup state missing | Run first setup |
| MP-STATE-002 | Setup incomplete | Resume setup |
| MP-STATE-003 | Setup state incompatible | Reverify or migrate |
| MP-STATE-004 | Last verification failed | Open repair mode |

---

# Appendix E: Example UI Copy

## Welcome

```text
Welcome to MediaPipelineRemuxEncodeAIO V6

We’ll verify local setup paths and make sure everything required is ready.
This includes your settings, required tools, state/log paths, pending-publish posture, and a controlled sample proof.

You can change advanced settings later.

[Start Setup]
[Customize]
```

## Recommended setup

```text
Recommended setup

State:
LocalBase\State

Setup proof:
LocalBase\State\Setup\sample-proof

Pending publish evidence:
LocalBase\State\PendingPublish

[Use Recommended Setup]
[Choose Different Location]
```

## Progress

```text
Setting up MediaPipelineRemuxEncodeAIO V6

✓ Verifying setup-owned state/proof paths
✓ Generating settings
✓ Checking files
✓ Checking output/pending-publish posture
✓ Checking required tools
✓ Verifying wiring
• Running controlled sample proof
```

## Ready

```text
MediaPipelineRemuxEncodeAIO V6 is ready

A controlled sample proof completed successfully, and your output/pending-publish posture is visible.

[Run First Job]
[Settings]
[Open Output or Pending Evidence]
```

## Needs attention

```text
MediaPipelineRemuxEncodeAIO V6 needs your attention

Problem:
The output/pending-publish posture is unsafe.

Recommended fix:
Open Settings or repair pending-publish state before running media work.

[Open Settings]
[View Details]
[Create Support Bundle]
```

## Repair

```text
Repair MediaPipelineRemuxEncodeAIO V6

We found an issue with your existing setup.
Source media, final outputs, pending-publish payloads, manifests, sidecars, and queue evidence will not be deleted.

[Repair Automatically]
[View Details]
```

## Reset

```text
Reset settings?

This will restore default settings and back up your current settings.
It will not delete source media, final outputs, pending-publish payloads, manifests, sidecars, or queue evidence.

[Reset Settings]
[Cancel]
```

---

# Appendix F: First Successful Job Flow

Setup should not stop at “the app opens.”

A guided first job flow helps the user experience value immediately.

## Flow

```text
Setup complete
↓
Run First Job screen
↓
User adds a media file
↓
App validates input
↓
User accepts default output
↓
App runs job
↓
App shows created files
↓
User opens output or pending-publish evidence
```

## Screen copy

```text
Run your first job

Drop a media file here or choose one from your computer.
We’ll use the recommended settings.

[Choose File]
```

## After completion

```text
Your first job is complete

Created:
- video-final.mp4
- metadata.json

Output/publish status:
Configured output written, or pending publish parked with manifest evidence

[Open Output or Pending Evidence]
[Run Another Job]
```

## Validation before job

Before running first real job:

- Confirm setup still ready.
- Confirm selected input exists.
- Confirm output or pending-publish posture is valid.
- Confirm required dependencies available.
- Estimate available disk space if relevant.

---

# Appendix G: Repository Inventory Checklist

Codex should use this checklist while discovering the existing repository.

## Entry points

- [x] Main GUI entrypoint found: promoted Tauri/WebView2 shell under
  `DesktopApp\tauri_shell\`, launched by
  `scripts\dev\start-tauri-preview.bat`; browser WebView path launched by
  `scripts\dev\start-api-and-browser.bat`.
- [x] CLI entrypoint found or confirmed absent: no packaged `mediapipeline`
  console command is documented; support/operator script entrypoints are
  `Pipeline\MediaPipeline.ps1`, `Pipeline\Setup-MediaPipeline.ps1`,
  `scripts\verify-env.ps1`, and release/test scripts.
- [x] Launch scripts found: canonical launchers are
  `scripts\dev\start-local-api.bat`,
  `scripts\dev\start-api-and-browser.bat`,
  `scripts\dev\start-tauri-preview.bat`, `scripts\dev\setup.bat`,
  `scripts\dev\run.bat`, `scripts\verify-env.bat`,
  `scripts\release\build.ps1`, and `scripts\release\test.ps1`.
- [x] Installer/package entrypoints found: `scripts\release\build.ps1`,
  `scripts\release\test.ps1`,
  `DesktopApp\tauri_shell\src-tauri\tauri.conf.json`, and WebView
  Maintenance release dry-run/build command routes.
- [x] Existing wizard entrypoint found: legacy PowerShell setup wizard at
  `Pipeline\Setup-MediaPipeline.ps1` and current WebView Settings Wizard in
  `DesktopApp\mediapipeline_desktop_app\ui_web\static\partials\page-settings.html`,
  `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsWizard.js`,
  and `app\config\settings_wizard.py`.

## Configuration

- [x] Config file locations found: live personal config is
  `Pipeline\MediaPipeline_config_chatgpt.psd1` when present; package builds
  strip it by default. Main operator keys include `SourceMovies`, `SourceTV`,
  `Outsource`, and `LocalBase`.
- [x] Default config found: `Pipeline\Profiles\Default.psd1`.
- [x] Config templates found: `Pipeline\MediaPipeline_config_template.psd1`.
- [x] Config schema found: `schemas\config.v1.schema.json`,
  `Pipeline\Schemas\media_pipeline_config.schema.json`, and
  `app\contracts\config.py`.
- [x] Config migration system found or confirmed absent: config save paths back
  up before writing; state/preset migration helpers exist in
  `app\storage\state_migration.py` and `app\config\preset_migration.py`.
  A dedicated deployment setup-migration manifest is not present yet.
- [x] Secret handling found: Local API uses per-run bearer tokens; Network
  `CoordinatorAuthToken` and `WorkerAuthToken` are intentionally hidden from
  WebView builders and must remain redacted.

## Paths

- [x] Input path logic found: `SourceMovies` and `SourceTV` config keys,
  `app\queue\*`, `engine\queue\*`, and source identity helpers.
- [x] Output path logic found: `Outsource`, publish completion, pending
  publish, final-library promotion, and `engine\paths\output_path_planning.ps1`.
- [x] Logs path logic found: runtime logs under `LocalBase\State\Progress`,
  `RunLogs\`, Diagnostics allowlisted targets, and
  `Docs\inventories\LOG_ARTIFACT_CATALOG.md`.
- [x] Temp/cache path logic found: `LocalBase` scratch/state roots,
  `engine\storage\scratch_copy.ps1`, `engine\shared\temp_cleanup.ps1`, and
  pending-publish parking under `State\PendingServerPush`.
- [x] Path variable/resolution logic found: `app\paths\*`,
  `engine\shared\path_helpers.ps1`, Settings path warnings, and folder-policy
  services.

## Dependencies

- [x] Required external/bundled tools identified: PowerShell 7, Python,
  FFmpeg, ffprobe, and MKVToolNix `mkvmerge`.
- [x] Optional tools identified: PgsToSrt/tessdata for BDPGS OCR when enabled,
  ffplay, extra MKVToolNix tools, Chrome/Edge for browser smokes, Node.js for
  WebView validation, and Rust/Cargo for Tauri builds.
- [x] Runtime version requirements identified: bundled PowerShell 7.6.0,
  Python 3, Node 18+ for validation, Rust 1.77+ for Tauri source builds, and
  Tauri 2 metadata.
- [x] Dependency detection code found: `scripts\verify-env.ps1` and
  `Pipeline\Setup-MediaPipeline\Dependencies.ps1`.

## Pipeline

- [x] Workflow definitions found: `Pipeline\MediaPipeline.ps1`,
  `engine\queue\pipeline_engine.ps1`, `engine\process\pipeline_processing.ps1`,
  and stage contracts under `app\contracts\stages.py`.
- [x] Step registry found: current Python stage contracts and
  `engine\entrypoint.ps1` enable read-only `probe` and `decide`; legacy
  PowerShell module wiring is now under `engine\`.
- [x] Command handlers found: Local API command route registry under
  `app\api\commands.py`, command groups under `app\api\commands_*.py`, and
  DesktopApp API handler modules.
- [x] Output handlers found: `engine\publish\*`, `app\completed\*`,
  `app\publish\*`, completed manifests, sidecars, and pending-publish
  manifests.
- [x] Plugin system found or confirmed absent: no general media-pipeline plugin
  system is active; Network lifecycle and repair/reconcile controls are
  design-gated backend work, not plugins.
- [x] Sample fixture found or confirmed absent: fixture data exists under
  `tests\fixtures\source_media\`; generated-media and WebView smokes exist.
  Real media samples are not checked in and are tracked by operator evidence.

## UI

- [x] Run action found: Launch page `POST /api/pipeline/start`, owned by
  `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
  and backend process facades.
- [x] Open output action found: Completed/Pending/Diagnostics shell-open routes
  in `Docs\inventories\API_ROUTE_INVENTORY.md`, including
  `POST /api/completed/open` and allowlisted Diagnostics targets.
- [x] Settings action found: Settings routes include validate, browse-path,
  preview-patch, save-patch, reload, and Settings Wizard preview/save.
- [x] Wizard UI found: WebView Settings Wizard tab in `page-settings.html`,
  client logic in `settingsWizard.js`, and backend helpers in
  `app\config\settings_wizard.py`.
- [x] Error display pattern found: structured backend error routing and
  command-history/status surfaces are documented in current project state and
  guarded by WebView/static tests.

## Packaging

- [x] Build scripts found: `scripts\release\build.ps1` and
  `scripts\release\test.ps1`.
- [x] Resource inclusion rules found:
  `Docs\inventories\RELEASE_PACKAGE_ADMIN_INVENTORY.md` documents included and
  excluded files, generated `release_manifest.json`, and personal-config
  stripping.
- [x] Installer/package config found: Tauri bundle config at
  `DesktopApp\tauri_shell\src-tauri\tauri.conf.json`; no separate MSI installer
  config is documented as the active release path.
- [x] Platform targets found: Windows-first operator target; Tauri config says
  bundle targets `all`, but the promoted workflow is WebView2/Windows.
- [x] Bundled dependencies found: `DesktopApp\Runtime\Python`,
  `Pipeline\PowerShell-7.6.0-win-x64`, `Pipeline\Tools\ffmpeg\bin`,
  `Pipeline\Tools\MKVToolNix`, and optional `Pipeline\Tools\PgsToSrt`.

## Tests

- [x] Unit tests found: `DesktopApp\tests\`, `tests\contract\`,
  `tests\decide\`, `tests\tooling\`, and
  `Pipeline\Tests\Unit\*.ps1`.
- [x] Integration tests found: `tests\integration\`,
  `tests\orchestration\`, Local API route tests, and PowerShell reliability
  wrappers.
- [x] E2E/smoke tests found: `SmokeTests\*.ps1`,
  `Pipeline\Tests\Invoke-EndToEndSmokeChecks.ps1`,
  `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`, WebView browser
  smokes, and real-media validation playbooks/evidence anchors.
- [x] CI config found: `.github\workflows\phase1-drift.yml`.
- [x] Test fixtures found: `tests\fixtures\source_media\` and fixture-backed
  WebView/local API tests. Detailed real-media samples remain local/operator
  evidence, not repository fixtures.
- [x] Temporary workspace test utilities found: many Python service/facade tests
  use temp directories, and smoke wrappers create isolated temp state for Local
  API and validation-log checks.

---

# Closing Recommendation

Build the deployment verification system around a manifest and validation engine.

The wizard should become the friendly face of that system, not the system itself.

The highest-leverage implementation sequence is:

1. One obvious launcher.
2. Deployment manifest.
3. Basic validation engine.
4. Config generation and schema validation.
5. Setup state file.
6. Output/pending-publish/log/dependency checks.
7. Ready dashboard.
8. Wiring verification.
9. Controlled sample proof.
10. Repair mode.
11. Support bundle.
12. Clean-machine and broken-install tests.

The target is not simply a cleaner setup.

The target is a product that can confidently say:

> MediaPipelineRemuxEncodeAIO V6 is ready for the selected readiness level because the installation was verified, the configuration is valid, the dependencies work, the backend-owned components are wired correctly, and any required controlled sample proof completed successfully.
