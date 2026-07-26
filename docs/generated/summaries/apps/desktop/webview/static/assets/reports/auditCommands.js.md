---
file: apps/desktop/webview/static/assets/reports/auditCommands.js
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: JavaScript
pipeline_stage: observability
token_priority: medium
owner_domain: webview
last_modified: 2026-07-15
last_reviewed: 2026-06-24
sha256: 2ad223efa1a89a2b65f4b78a3514c58fa3c6a96d602507d87bfb3045251806f2
---
# `apps/desktop/webview/static/assets/reports/auditCommands.js`

**Purpose:** JavaScript implementation for audit commands; exposes addReportAuditSourceFromForm, appendReportAuditCommandResult, appendReportsAuditRefreshWarning.

**Public symbols:** `addReportAuditSourceFromForm`, `appendReportAuditCommandResult`, `appendReportsAuditRefreshWarning`, `applyReportAuditStoppedSnapshot`, `auditRerunExportCsvPath`, `auditRerunExportData`, `auditRerunExportHandoff`, `collectReportAuditScorePolicyForm`, `collectReportAuditStartRequest`, `createReportsAuditCommandsModule`, `exportAuditRerunCsv`, `formatReportAuditCommandDetail`, `handoffAuditRerunCsvToQueue`, `ignoreSelectedAuditRows`, `noop`, `prepareReportAuditSnapshotForAcceptedStart`, `queueReportsAuditRefresh`, `refreshReportsAuditData`, `removeReportAuditSource`, `renderReportAuditLaunchPreflight`, `renderReportAuditSourceCommandResult`, `reportAuditBusyCommand`, `reportAuditBusyOperations`, `reportAuditBusyResult`, `reportAuditJsonDetail`, `reportAuditLaunchPreflightLines`, `reportAuditOperationIsBusy`, `reportAuditReviewCount`, `reportAuditSelectionRequest`, `saveReportAuditScorePolicy`, `scanReportAuditSources`, `setReportAuditOperationBusy`, `startReportAuditFromForm`, `stopReportAuditFromForm`
**In-repo imports:** `);
    setText(`, `,`, `,
        detailId:`, `,
      });
    }
  }

  function auditRerunExportData(result) {
    return result?.data && typeof result.data ===`, `, [
        formatReportAuditCommandDetail(result, request),`, `, [
      formatReportAuditCommandDetail(result, request),`, `, formatReportAuditCommandDetail(result));
      return;
    }
    const request = reportAuditSelectionRequest();
    if (request.row_keys.length && hiddenSelectedAuditCount()) {
      setText(`, `, formatReportAuditCommandDetail(result));
      return;
    }
    const rowKeys = selectedAuditRowKeysList();
    if (!rowKeys.length) {
      setText(`, `, formatReportAuditCommandDetail(result, request));
      if (result.ok) {
        await handoffAuditRerunCsvToQueue(result, request);
      } else {
        refreshAfterCommand = true;
      }
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command:`, `, formatReportAuditCommandDetail(result, request));
      refreshAfterCommand = true;
    } catch (error) {
      const text = error instanceof Error ? error.message : String(error);
      const result = { command:`, `, formatReportAuditCommandDetail(result, request));
    } finally {
      setReportAuditOperationBusy(`, `, hiddenAuditSelectionMessage(`, `, preview?.ok === false ?`, `, request);
      appendReportAuditCommandResult(result);
      setText(`, `, result.ok ?`, `window.__reportsAuditProgressModule`, `window.__reportsAuditSourcesModule`, `window.__reportsViewAuditCommandsModule`, `window.clearTimeout`, `window.commandResultDisplayMessage`, `window.confirm`, `window.mediaPipelineQueueView`, `window.refreshAll`, `window.setTimeout`, `window.showPage`
**HTTP routes:** `/api/audit/export-rerun-csv`, `/api/audit/ignore`, `/api/audit/score-policy`, `/api/audit/sources`, `/api/audit/sources/scan`, `/api/audit/start`, `/api/audit/stop`, `/api/pipeline/start`, `/api/rerun/preview`, `/api/rerun/start`
**DOM selectors:** `[data-audit-score-issue-code]`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/webview/static/assets/reports/auditCommands.js`._
