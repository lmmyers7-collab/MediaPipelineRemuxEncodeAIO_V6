# ops/pipeline/engine/publish/pending_transactions.ps1

## Current Strain

- Approximate size: 960 lines, 18 functions.
- Risk level: high.
- Mixed concerns: transaction IDs, sidecar backup/undo, sidecar publish,
  server-copy verification, park manifests, park transactions, manifest repair,
  drain sidecar extras, local artifact cleanup, and drain transactions.

## Ideal Split

- `ops/pipeline/engine/publish/pending_sidecar_transactions.ps1`: sidecar backup, restore,
  publish, undo, and completion helpers.
- `ops/pipeline/engine/publish/pending_park_transaction.ps1`: park manifest creation and
  park transaction execution.
- `ops/pipeline/engine/publish/pending_drain_transaction.ps1`: drain extras, local artifact
  cleanup, and drain transaction execution.
- `ops/pipeline/engine/publish/pending_repair.ps1`: manifest-state repair and sidecar
  artifact repair helpers.

## Extraction Order

1. Extract sidecar backup/restore helpers.
2. Extract manifest construction helpers.
3. Extract repair helpers.
4. Split park and drain transaction executors last.

## Validation

- Pending publish ownership and safety PowerShell checks.
- Pending-publish fixture inventory coverage.
- Local API/WebView pending publish contract tests when DTOs are affected.
- Real-media deferred publish to drain lifecycle validation.

## Must Not Change

Drain must require manifest evidence, sidecar rollback must remain conservative,
missing/unsafe final roots must park output, and source media must never be
deleted.

