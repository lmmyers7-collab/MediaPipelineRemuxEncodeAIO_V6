# Completed / Pending Publish Failure Playbook

Date: 2026-05-14

Operator guidance for diagnosing and resolving failure states in the Completed and Pending Publish pages. Each scenario states the symptom, the likely cause, the investigation sequence, and the safe next action. All actions route through backend-owned commands — no manual file edits, no direct drain, no path manipulation from the WebView.

---

## Scope and Safety

- All investigation uses read-only diagnostics targets and WebView read panels.
- All repair actions use backend-owned routes (`POST /api/pipeline/start`, `POST /api/rerun/start`).
- No scenario in this playbook requires manually editing manifest files, deleting failure markers, or bypassing confirmation prompts.
- Display filters on the Completed and Pending Publish tables are display-only — they do not change backend repair, rerun, drain, or publish scope.
- Before starting any drain investigation, read the **`Pending Backend Drain Scope Preview`** panel on the Pending Publish page. It shows how many parked rows the backend will act on versus how many are visible in the current filtered view, the backend drain route authority, the most recent durable drain summary, and recent drain command evidence. If the panel shows a filter warning (blocked or review rows are hidden by an active filter), clear the filter before proceeding so no rows are missed in your investigation.

---

## Completed Page Failures

### Scenario C-1: Missing Output — Row Exists in Manifest But Output File Is Gone

**Symptom**: Completed row shows an output path in the manifest, but the file does not exist on disk. The Completed page may show a "missing output" warning.

**Likely causes**:
- Output was deleted externally (by the operator, a cleanup script, or an OS tool)
- Output was moved to a different path after the manifest was written
- Network destination was unmounted when the output was written

**Investigation sequence**:
1. Select the Completed row → inspect the output path and sidecar path in the row detail.
2. Tail `completed_manifest` (`GET /api/diagnostics/tail`) to verify the raw `output_path` field.
3. Open `pending_publish` folder if `DeferredPublish=true` — the output may have been parked rather than moved to final destination.
4. Tail `last_stderr_log` for any error messages during the original job run.
5. Check `GET /api/publish-reconciliation` to cross-reference Completed rows with current Pending Publish state.

**Safe next actions**:
- If the output was moved to a known path: update operator records; the manifest is append-only and will not self-repair.
- If the output must be regenerated: use `POST /api/rerun/start` with `dry_run: true` first to verify scope; then run without dry_run using safe defaults (`stage_mode: copy`, `original_mode: keep`, `return_mode: park`).
- If the output was intentionally deleted: no action required; the Completed record is historical only.

---

### Scenario C-2: Stale or Missing Sidecar

**Symptom**: Completed row's sidecar field shows a path but the `.mediapipeline.json` file is absent or shows an older schema version.

**Likely causes**:
- Sidecar was not written due to a pipeline crash after encode but before sidecar write
- Sidecar was deleted externally
- Sidecar path no longer matches the output path (output was moved without a rename operation)

**Investigation sequence**:
1. Select the Completed row → check sidecar status in the row detail panel.
2. Tail `completed_manifest` to see if `sidecar` field is populated with a path that no longer exists.
3. Open the backend-selected sidecar or output folder from the Completed row action if you need to browse sidecar files.
4. Open or tail `completed_manifest` (`POST /api/diagnostics/open` or `GET /api/diagnostics/tail` with `completed_manifest` target) to inspect the manifest file itself.
5. Check `last_stderr_log` for the original run — a crash at sidecar write stage leaves a gap.

**Safe next actions**:
- Sidecar missing after a confirmed encode: the output is still valid; the sidecar gap is a metadata issue. Document the gap in the sample validation log via `POST /api/sample-validation/append`.
- Sidecar schema version mismatch (older version): acceptable if the sidecar fields needed for downstream use are present. Consult `docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md`.

---

### Scenario C-3: Route Disagreement — Manifest Route Differs From Expected

**Symptom**: Completed row shows `route: remux` but the operator expected `route: encode` (or vice versa), based on current settings.

**Likely causes**:
- Settings changed after the job ran (the route reflects settings at run time, not current settings)
- The source file size was under/over the encode threshold at run time
- `AllowH264RemuxIfPlexCompatible` or another policy overrode the expected route

**Investigation sequence**:
1. Select the Completed row → check `route_reason` in the row detail.
2. Tail `completed_manifest` to read the raw `route`, `route_reason_code`, and `route_reason` fields.
3. Tail `last_stderr_log` for the FFmpeg command that was used (remux vs. encode command).
4. Open Settings → check current `RoutingProfile`, `EncodeThresholdGB`, `TVEncodeThresholdGB`.

**Safe next actions**:
- Route disagreement is often expected when settings changed between runs. No immediate action needed.
- If the route was wrong at run time and output quality is incorrect: rerun via `POST /api/rerun/start` with dry_run first.
- Do not treat a route difference alone as a failure — check output quality and size separately.

---

### Scenario C-4: Size-Growth Outlier

**Symptom**: Completed row shows the output is significantly larger than the source (encode growth % exceeds `MaxEncodeGrowthPercent`), or `SizeGuardMode: strict` triggered a failure.

**Likely causes**:
- Source file has complex video content that the encoder cannot shrink efficiently
- `EncodeThresholdGB` threshold was too low — source should have been remuxed
- `MaxEncodeGrowthPercent` was set too aggressively low for this content type

**Investigation sequence**:
1. Select the Completed row → check size evidence in the row detail (source size vs. output size vs. growth %).
2. Check the Real-Media Output Proof ladder (if visible) for route and size comparison.
3. Tail `last_stderr_log` to find the FFmpeg encode command and output-size logging.
4. Open Settings → check `SizeGuardMode`, `MaxEncodeGrowthPercent`, `CompatibilityEncodeGrowthPercent`.

**Safe next actions**:
- If `SizeGuardMode: strict` triggered: the output was not finalized. Use `POST /api/rerun/start` with adjusted settings after reviewing `EncodeThresholdGB`.
- If growth is within acceptable range but above the configured limit: adjust `MaxEncodeGrowthPercent` and rerun.
- If the source should have been remuxed: consider adjusting `EncodeThresholdGB` or `AllowH264RemuxIfPlexCompatible`.

---

### Scenario C-5: Duplicate or Conflicting Output Titles

**Symptom**: Two Completed rows reference different sources but the same `output_file` basename, or the Completed-to-Pending overlap proof shows a same-leaf duplicate-title warning.

**Likely causes**:
- Two source files produced identical output names (e.g., two different rips of the same movie)
- A rename was applied that created a naming conflict

**Investigation sequence**:
1. In the Completed page, check the Completed-to-Pending Publish Proof ladder (via `Test-WebViewBrowserCompletedPendingProofSmoke` to understand what the proof shows).
2. Use `GET /api/publish-reconciliation` to see the backend's cross-reference of Completed and Pending Publish rows.
3. Tail `completed_manifest` to compare `output_file`, `output_path`, and `source_path` for both rows.

**Safe next actions**:
- Resolve naming conflicts before draining. Use the Rename tool to give distinct names, then apply via `POST /api/rename/apply`.
- Do not drain if duplicate-title guidance is showing on Pending Publish rows.

---

## Pending Publish Failures

### Scenario P-1: Do-Not-Drain Row

**Symptom**: A Pending Publish row shows a "do not drain" warning. The Publish Button Guard is blocked.

**Likely causes**:
- `manifest_state` is `missing_payload` (local/parked file absent)
- `manifest_state` is `retry_copy_failed`, `retry_reveal_failed`, or similar retry failure
- The backend recovery dry-run returned a blocked result for this row
- Backend detected a destination conflict or duplicate-title issue

**Investigation sequence**:
1. Select the Pending Publish row → check `manifest_state` and the drain evidence board in row detail.
2. Run the Recovery Dry-Run (`POST /api/pending-publish/recovery-plan`) to get the backend-authored plan.
3. Tail `last_stderr_log` for the drain attempt error message (if a previous drain was attempted).
4. Tail `latest_failure_json` if a failure was recorded during the drain attempt.
5. Open `pending_publish` folder to inspect the raw manifest JSON.

**Safe next actions**:
- `missing_payload`: the parked file was deleted externally. The manifest cannot be drained. Document in sample validation log; consider rerunning the source via `POST /api/rerun/start`.
- Retry failures: investigate the destination path for write permissions or network issues. Resolve the underlying cause, then retry drain via `POST /api/pipeline/start` with `mode: drain_pending_pushes`.
- Destination conflict: resolve the conflict at the destination, then retry drain.

---

### Scenario P-2: Missing Payload

**Symptom**: `manifest_state: missing_payload`. The Pending Publish row exists but the parked local file (`parked_file` or `local_file`) is not found on disk.

**Likely causes**:
- The parked file was deleted externally between parking and drain
- The scratch disk (LocalBase) was cleaned or reformatted
- A pipeline crash during the park operation left an incomplete manifest

**Investigation sequence**:
1. Select the Pending Publish row → inspect `parked_file` and `local_file` paths in row detail.
2. Open `pending_publish` folder to browse and inspect the raw JSON manifest.
3. Tail `last_stderr_log` for any park operation error messages.
4. Check the Completed manifest for a corresponding `completed_jobs.jsonl` entry — confirm whether the encode completed before parking.

**Safe next actions**:
- If the Completed manifest shows the encode completed: the payload was lost after encode. Rerun via `POST /api/rerun/start` (dry_run first) to regenerate the output.
- If the Completed manifest shows no corresponding entry: the encode may have failed. Check `failed_reports` and `failed_markers`.

---

### Scenario P-3: Orphan Payload

**Symptom**: A file exists in the `PendingServerPush` folder but no corresponding manifest JSON is found. The Pending Publish page shows an orphan payload warning.

**Likely causes**:
- A pipeline crash wrote the parked file but crashed before writing the manifest
- A manifest was deleted externally while the payload file remained

**Investigation sequence**:
1. Open `pending_publish` folder (`POST /api/diagnostics/open`) to browse the raw contents.
2. Cross-check the orphan payload filename against Completed manifest rows via `GET /api/publish-reconciliation`.
3. Tail `last_stderr_log` for any crash messages from the parking operation.

**Safe next actions**:
- If the payload corresponds to a known Completed row: the orphan payload can likely be safely drained after the manifest is confirmed (contact backend admin to reconstruct the manifest from the Completed row if this is needed).
- If the payload has no corresponding Completed row: the output is of unknown provenance. Do not drain. Investigate via `POST /api/rerun/start` dry_run to understand scope.

---

### Scenario P-4: Unreadable Manifest

**Symptom**: A Pending Publish row shows an `unreadable_manifest` or `invalid_contract` state. The backend cannot parse the manifest file.

**Likely causes**:
- Manifest was partially written during a crash (truncated JSON)
- Manifest was edited externally and is now malformed
- Schema version mismatch between pipeline versions

**Investigation sequence**:
1. Open `pending_publish` folder to inspect the raw JSON file.
2. Attempt to read the file content manually (open in Explorer) to identify truncation or malformation.
3. Tail `last_stderr_log` for any schema validation error messages.

**Safe next actions**:
- If the manifest is truncated: the payload file is likely valid. Document the issue in the sample validation log. Contact backend admin to reconstruct or remove the manifest.
- Do not attempt to repair the JSON file manually while the backend is running.

---

### Scenario P-5: Drain Failure

**Symptom**: A drain was attempted (`POST /api/pipeline/start` with `mode: drain_pending_pushes`) but one or more rows failed to drain. Rows remain in `retry_copy_failed` or similar state.

**Likely causes**:
- Destination is unreachable (network share offline, permission denied)
- Robocopy timeout (`RobocopyTimeoutSeconds`) was too low for large files
- Destination disk is full (`OutsourceMinFreeSpaceGB` check was not triggered before drain)
- Sidecar write to destination failed

**Investigation sequence**:
1. Select the failed Pending Publish row → inspect drain evidence board for the error detail.
2. Tail `last_stderr_log` for Robocopy error codes and destination path messages.
3. Run the Recovery Dry-Run to get the backend-authored planned actions.
4. Check destination free space and network availability before retrying.
5. Review `OutsourceMinFreeSpaceGB` and `RobocopyTimeoutSeconds` in Settings.

**Safe next actions**:
- Resolve the destination issue (remount share, clear space, fix permissions).
- Increase `RobocopyTimeoutSeconds` if the timeout was the cause.
- Retry drain via `POST /api/pipeline/start` with `mode: drain_pending_pushes` after resolving the cause.
- Do not retry drain while the destination issue persists.

---

## Cross-Page Evidence Sequence (General)

For any Completed or Pending Publish failure, use this investigation order before taking any repair action:

1. **Backend Drain Scope Preview** (Pending Publish page) — confirm how many parked rows the backend will evaluate when drain is issued, whether active filters are hiding blocked or review rows, and what the most recent durable drain summary says. If a filter warning is visible, clear the filter before investigating individual rows.
2. **Row detail in WebView** — select the affected row and read the full detail panel (route, state, error messages, diagnostics handoff).
3. **Tail `last_stderr_log`** — the most recent pipeline run's stderr is the first stop for FFmpeg and park errors.
4. **Tail `completed_manifest`** — confirm whether a completion record was written and what route/size/sidecar fields it contains.
5. **Run Recovery Dry-Run** (Pending Publish only) — get the backend's authoritative planned actions before any drain attempt.
6. **`GET /api/publish-reconciliation`** — cross-reference Completed and Pending Publish state if output paths are unclear.
7. **Tail `latest_failure_json`** — if a failure marker exists, read the raw failure record for stage and error code.
8. **`POST /api/rerun/start` with `dry_run: true`** — verify rerun scope before any real rerun.

Never skip the dry-run step before a rerun. Always confirm the destination is writable before retrying a drain.

---

## See Also

- Diagnostics targets runbook: `docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- State schema reference: `docs/inventories/STATE_FILE_SCHEMA_REFERENCE.md`
- Log artifact catalog: `docs/inventories/LOG_ARTIFACT_CATALOG.md`
- Failure triage worksheet: `docs/operator/FAILURE_TRIAGE_WORKSHEET.md`
- Manual operator test script: `docs/operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`
