(function () {
  function createCompletedEvidenceModule(deps) {
    const {
      apiGet,
      appendCells,
      byId,
      clearRows,
      commandHistoryCommandText,
      commandHistoryIssueLevel,
      commandHistoryOwnerPage,
      commandHistorySuggestedAction,
      completedEvidenceState: state,
      completedFilterFields,
      completedCurrentRows,
      completedInvestigationFilterLabel,
      completedMatchesInvestigationFilter,
      completedReviewRowReasons,
      completedTableRowStatus,
      filterRows,
      filterRowsByInvestigation,
      filterRowsByStatus,
      getCommandHistory,
      getSelectedCompletedRow,
      makeRowSelectable,
      renderCompletedFinalTrust,
      renderCompletedPilotEvidencePacket,
      renderCompletedRealMediaProof,
      renderCompletedSizeEvidence,
      setText,
      tableStatusFilterLabel,
      updateTableStatusLegend,
    } = deps;

    function completedAcceptancePostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("read-first")) return "changed";
      if (normalized.includes("select")) return "unknown";
      return "match";
    }

    function completedAcceptanceCommandEntries(entries) {
      const source = Array.isArray(entries)
        ? entries
        : typeof getCommandHistory === "function"
          ? getCommandHistory()
          : [];
      return (Array.isArray(source) ? source : []).filter((entry) => {
        const owner = typeof commandHistoryOwnerPage === "function" ? commandHistoryOwnerPage(entry) : "";
        const command = typeof commandHistoryCommandText === "function" ? commandHistoryCommandText(entry) : String(entry?.command || "");
        return owner === "Completed" || owner === "Pending Publish" || command.startsWith("completed.") || command.startsWith("pending_publish.");
      });
    }

    function completedAcceptanceIssueLevel(entry) {
      if (typeof commandHistoryIssueLevel === "function") return commandHistoryIssueLevel(entry);
      if (!entry) return "none";
      if (!entry.ok && String(entry.severity || "").toLowerCase() !== "info") return entry.severity || "error";
      if (entry.severity === "warning" || (Array.isArray(entry.warnings) && entry.warnings.length)) return "warning";
      return "ok";
    }

    function completedAcceptanceProofRowsForItem(item, proofRows = state.lastCompletedPendingProofRows) {
      if (!item) return [];
      const itemKey = completedProofRowKey(item);
      const itemOutput = completedProofNormalizePath(completedProofCompletedOutputPath(item));
      const itemSource = completedProofNormalizePath(completedProofCompletedSourcePath(item));
      return (Array.isArray(proofRows) ? proofRows : []).filter((row) => {
        const completed = row?.completed || {};
        const completedKey = completedProofRowKey(completed);
        const completedOutput = completedProofNormalizePath(completedProofCompletedOutputPath(completed));
        const completedSource = completedProofNormalizePath(completedProofCompletedSourcePath(completed));
        return (
          (itemKey && completedKey && itemKey === completedKey) ||
          (itemOutput && completedOutput && itemOutput === completedOutput) ||
          (itemSource && completedSource && itemSource === completedSource)
        );
      });
    }

    function completedAcceptanceSelectedOrFirst(rows) {
      const selected = getSelectedCompletedRow();
      if (selected) return selected;
      const rowList = Array.isArray(rows) ? rows : [];
      return rowList.find((row) => row?.size_growth_over_5 || completedProofRowMissingOutput(row)) || rowList[0] || null;
    }

    function completedCurrentFilterScope(rows = state.lastCompletedRows) {
      const currentRows = typeof completedCurrentRows === "function"
        ? completedCurrentRows(rows)
        : (Array.isArray(rows) ? rows : []).filter((row) => row?.output_exists !== false);
      const allRows = Array.isArray(currentRows) ? currentRows : [];
      const filterText = byId("completed-filter")?.value || "";
      const statusFilter = byId("completed-status-filter")?.value || "all";
      const investigationFilter = byId("completed-investigation-filter")?.value || "all";
      const normalizedStatus = String(statusFilter || "all").trim().toLowerCase();
      const normalizedInvestigation = String(investigationFilter || "all").trim().toLowerCase();
      const textRows = typeof filterRows === "function" ? filterRows(allRows, filterText, completedFilterFields) : allRows;
      const statusRows = typeof filterRowsByStatus === "function" ? filterRowsByStatus(textRows, statusFilter, completedTableRowStatus) : textRows;
      const visibleRows = typeof filterRowsByInvestigation === "function" ? filterRowsByInvestigation(statusRows, investigationFilter, completedMatchesInvestigationFilter) : statusRows;
      const visibleSet = new Set(visibleRows);
      const hiddenRows = allRows.filter((row) => !visibleSet.has(row));
      const hiddenBlocked = hiddenRows.filter((row) => completedTableRowStatus(row) === "blocked").length;
      const hiddenWarning = hiddenRows.filter((row) => completedTableRowStatus(row) === "warning").length;
      const hiddenReview = hiddenRows.filter((row) => completedReviewRowReasons(row).length || ["blocked", "warning"].includes(completedTableRowStatus(row))).length;
      const active = Boolean(String(filterText || "").trim())
        || (normalizedStatus && normalizedStatus !== "all")
        || (normalizedInvestigation && normalizedInvestigation !== "all");
      return {
        active,
        filterText: String(filterText || "").trim(),
        statusFilter: normalizedStatus || "all",
        statusLabel: typeof tableStatusFilterLabel === "function" ? tableStatusFilterLabel(statusFilter) : statusFilter,
        investigationFilter: normalizedInvestigation || "all",
        investigationLabel: completedInvestigationFilterLabel(investigationFilter),
        totalRows: allRows.length,
        visibleRows: visibleRows.length,
        hiddenRows: hiddenRows.length,
        hiddenBlocked,
        hiddenWarning,
        hiddenReview,
        renderLimit: 250,
      };
    }

    function completedFilterScopePosture(scope) {
      if (!scope?.active) return "Read-only";
      if (scope.hiddenBlocked || scope.hiddenReview) return "Review";
      if (scope.visibleRows === 0 && scope.totalRows > 0) return "Read-first";
      return "Read-first";
    }

    function completedFilterScopeEvidence(scope) {
      return `Filters=${scope.active ? "active" : "inactive"}; visible=${scope.visibleRows}/${scope.totalRows}; hidden=${scope.hiddenRows}; hidden blocked=${scope.hiddenBlocked}; hidden review=${scope.hiddenReview}.`;
    }

    function completedFilterScopeAction(scope) {
      if (!scope.active) {
        return "No local Current Output filter is narrowing the table, but backend manifests and rerun/cleanup decisions still use backend-owned evidence.";
      }
      if (scope.hiddenBlocked || scope.hiddenReview) {
        return "Clear Current Output filters or inspect hidden review rows before accepting outputs, rerunning sources, deleting files, or cleaning up state.";
      }
      return "Treat filters as display-only search. Backend-owned actions do not receive Current Output filter state or visible-row subsets.";
    }

    function completedFilterScopeDetailLines(scope) {
      const lines = [
        "Current Output display filter / backend action scope:",
        `Text filter: ${scope.filterText || "none"}`,
        `Status filter: ${scope.statusLabel || scope.statusFilter || "all"}`,
        `Investigation view: ${scope.investigationLabel || scope.investigationFilter || "all"}`,
        `Visible rows after filters: ${scope.visibleRows} of ${scope.totalRows}`,
        `Hidden rows: ${scope.hiddenRows}; hidden blocked rows: ${scope.hiddenBlocked}; hidden warning rows: ${scope.hiddenWarning}; hidden review rows: ${scope.hiddenReview}`,
        `Render cap: first ${scope.renderLimit} visible rows are rendered when a large filtered set remains.`,
        "Backend action scope: unchanged. Current Output filters do not narrow rerun, cleanup, reconciliation, diagnostics, or manifest authority.",
        "Mutation guardrail: Current Output filters never accept outputs, suppress reruns, delete files, rewrite manifests, repair sidecars, drain pending publish, or change media policy.",
      ];
      if (scope.active && (scope.hiddenBlocked || scope.hiddenReview)) {
        lines.push("Operator warning: the current filters hide completed rows that need review, so the visible table can look safer than the backend manifest evidence.");
      } else if (scope.active) {
        lines.push("Operator note: the current filters are active for visual search only.");
      } else {
        lines.push("Operator note: no Current Output display filter is active.");
      }
      return lines;
    }

    function completedAcceptanceRows(completed, rows, proofRows = state.lastCompletedPendingProofRows, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const item = completedAcceptanceSelectedOrFirst(rowList);
      const relevantProofRows = completedAcceptanceProofRowsForItem(item, proofRows);
      const blockedProofRows = relevantProofRows.filter((row) => row?.status === "blocked");
      const exactProofRows = relevantProofRows.filter((row) => completedPendingProofIsExactPathSignal(row?.signal));
      const sameLeafRows = relevantProofRows.filter((row) => row?.signal === "same-leaf-review");
      const commands = completedAcceptanceCommandEntries(commandEntries);
      const commandIssues = commands.filter((entry) => !["ok", "info", "none"].includes(completedAcceptanceIssueLevel(entry)));
      const latestCommand = commands[0] || null;
      const latestIssue = completedAcceptanceIssueLevel(latestCommand);
      const missingOutput = completedProofRowMissingOutput(item);
      const consistencyIssues = Array.isArray(item?.consistency_issues) ? item.consistency_issues.filter(Boolean) : [];
      const sidecarIssue = item?.sidecar_exists === false || consistencyIssues.length || item?.expected_sidecar_path && item?.sidecar_path && item.expected_sidecar_path !== item.sidecar_path;
      const growthReview = item?.size_growth_over_5 || item?.size_delta_percent === null || item?.size_delta_percent === undefined;
      const runtimeStatus = String(item?.runtime_outcome_status || "").toLowerCase();
      const runtimeFreshness = String(item?.runtime_outcome_freshness_status || "").toLowerCase();
      const runtimeReview = runtimeStatus.includes("fail") || runtimeStatus.includes("error") || runtimeFreshness === "fresh";
      const filterScope = completedCurrentFilterScope(rowList);

      if (!rowList.length) {
        return [
          {
            key: "no-completed-output",
            checkpoint: "Completed output",
            posture: payload.error ? "Blocked review" : "Select history",
            evidence: payload.error ? `Completed history unavailable: ${payload.error}` : "No completed rows are loaded.",
            action: "Open Diagnostics > Completed Manifest and Run Logs before accepting, deleting, rerunning, or reprocessing any output.",
            detail: [
              "Output acceptance checklist:",
              "No completed row can be accepted from this WebView state.",
              "Mutation guardrail: this checklist does not accept, delete, rerun, reprocess, move, drain, or write files.",
            ],
          },
        ];
      }

      return [
        {
          key: "display-filter-scope",
          checkpoint: "Display filter / backend action scope",
          posture: completedFilterScopePosture(filterScope),
          evidence: completedFilterScopeEvidence(filterScope),
          action: completedFilterScopeAction(filterScope),
          completedRow: item,
          detail: completedFilterScopeDetailLines(filterScope),
        },
        {
          key: "selected-output-proof",
          checkpoint: "Selected output proof",
          posture: missingOutput || sidecarIssue ? "Blocked review" : "Read-only",
          evidence: item
            ? `${completedProofRowLabel(item)}; output ${missingOutput ? "missing" : item.output_health || "present/unknown"}; sidecar ${item.sidecar_exists === false ? "missing" : sidecarIssue ? "review" : "ok/unknown"}.`
            : "No completed row selected.",
          action: missingOutput || sidecarIssue
            ? "Read Completed Manifest, output folder, sidecar, Run Logs, and Last Stderr before rerun/delete/reprocess."
            : "Use row detail and diagnostics as supporting evidence before accepting output.",
          completedRow: item,
          detail: [
            "Output acceptance checklist:",
            `Selected row: ${item ? completedProofRowLabel(item) : "none"}`,
            `Output path: ${completedProofCompletedOutputPath(item) || "unknown"}`,
            `Source path: ${completedProofCompletedSourcePath(item) || "unknown"}`,
            `Consistency issues: ${consistencyIssues.join(", ") || "none loaded"}`,
          ],
        },
        {
          key: "size-route-proof",
          checkpoint: "Size and route proof",
          posture: growthReview ? "Review" : "Read-only",
          evidence: item
            ? `Size ${item.size_delta_label || "unknown"}; route ${item.route_decision_summary || item.route_label || item.route || "unknown"}; encoder ${item.encoder || item.encoder_kind || "unknown"}.`
            : "No completed row selected.",
          action: growthReview
            ? "Compare route evidence, encoder/GPU choice, audio/subtitle decisions, Run Logs, and settings policy before accepting growth."
            : "Confirm route evidence matches the intended Plex profile before treating output as accepted.",
          completedRow: item,
          detail: [
            "Oversized outputs can be intentional when subtitle conversion, audio normalization, or compatibility routing changed the mux/encode path.",
            "Do not use size alone as proof that an encode is wrong or right.",
          ],
        },
        {
          key: "pending-publish-proof",
          checkpoint: "Pending/publish proof",
          posture: blockedProofRows.length ? "Blocked review" : exactProofRows.length || sameLeafRows.length ? "Review" : "Read-first",
          evidence: `${relevantProofRows.length} proof row(s); ${blockedProofRows.length} blocked; ${exactProofRows.length} exact; ${sameLeafRows.length} same-leaf advisory.`,
          action: blockedProofRows.length
            ? "Resolve blocked pending proof before rerun, drain, cleanup, delete, or reprocess."
            : exactProofRows.length
              ? "Confirm whether exact pending/drain proof means parked output, stale state, or completed publish before acting."
              : "If output is missing, remember an empty Pending Publish view is not proof that publishing succeeded.",
          completedRow: item,
          detail: [
            "Proof order: completed row -> exact output/source path -> pending row/state -> durable drain summary -> run logs.",
            "Same-leaf matches are duplicate-title hints only; exact full paths are stronger proof.",
          ],
        },
        {
          key: "recent-command-evidence",
          checkpoint: "Recent command evidence",
          posture: commandIssues.length ? "Review" : latestCommand ? "Read-first" : "Read-only",
          evidence: latestCommand
            ? `${commands.length} Completed/Pending command(s); latest ${latestCommand.command || "unknown"} (${latestIssue}).`
            : "No recent Completed/Pending command history loaded.",
          action: commandIssues.length
            ? "Review command-result warnings/errors and their diagnostics handoff before trusting the visible table state."
            : "Use command history as supporting evidence; refresh Completed/Pending after backend-owned actions.",
          completedRow: item,
          detail: [
            `Completed/Pending command entries: ${commands.length}`,
            `Command entries needing review: ${commandIssues.length}`,
            latestCommand ? `Latest command suggested action: ${typeof commandHistorySuggestedAction === "function" ? commandHistorySuggestedAction(latestCommand) : "inspect command detail"}` : "Latest command suggested action: none loaded",
          ],
        },
        {
          key: "diagnostics-read-order",
          checkpoint: "Diagnostics read order",
          posture: runtimeReview ? "Review" : "Read-first",
          evidence: runtimeReview
            ? `Runtime status ${item?.runtime_outcome_status || "unknown"} (${item?.runtime_outcome_freshness_status || "unknown"}).`
            : "Completed Manifest -> Run Logs -> Last Stderr -> Latest Failure -> Pending Publish.",
          action: "Use backend allowlisted diagnostics targets before any destructive operator action outside WebView.",
          completedRow: item,
          detail: [
            "Diagnostics buttons are backend allowlisted.",
            "This checklist never accepts output on the operator's behalf; it only orders evidence.",
          ],
        },
        {
          key: "decision-boundary",
          checkpoint: "Decision boundary",
          posture: "Read-only",
          evidence: "Acceptance here means operator confidence only; WebView does not mark accepted, delete outputs, or suppress future reruns.",
          action: "Use backend-owned settings, queue, pending publish, or maintenance commands for any real action.",
          completedRow: item,
          detail: [
            "Mutation guardrail: no accept, delete, rerun, reprocess, drain, cleanup, manifest write, or policy change happens from this checklist.",
            "If any row above is blocked/review, read diagnostics before changing files outside the app.",
          ],
        },
      ];
    }

    function completedAcceptanceStatus(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (!list.length) return "No checklist";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "blocked")) return "Blocked review";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "warning")) return "Review before accepting";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "changed")) return "Read evidence";
      if (list.some((row) => completedAcceptancePostureStatus(row.posture) === "unknown")) return "Select row";
      return "Read-only";
    }

    function completedAcceptanceSummaryLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const blocked = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "blocked").length;
      const review = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "warning").length;
      const readFirst = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "changed").length;
      const unknown = list.filter((row) => completedAcceptancePostureStatus(row.posture) === "unknown").length;
      const outcome = blocked ? "Blocked review" : review ? "Review before accepting" : readFirst ? "Read evidence" : unknown ? "Select row" : list.length ? "Read-only" : "No checklist";
      const lines = [
        "Completed output acceptance checklist:",
        `Daily-use handoff: Completed evidence supports an operator trust decision; it does not mark output accepted or perform cleanup. Operator outcome: ${outcome}.`,
        `Checkpoints loaded: ${list.length}`,
        `Blocked checkpoints: ${blocked}`,
        `Review checkpoints: ${review}`,
        `Read-first checkpoints: ${readFirst}`,
        "Decision rule: acceptance requires display filter scope, output/sidecar proof, route/size explanation, pending-publish proof, and recent command evidence to agree.",
        "Scope boundary: Current Output filters, Completed History filters, selected rows, proof boards, and rendered row caps never accept outputs, delete files, rerun jobs, repair manifests, or change pending-publish state.",
      ];
      if (blocked) {
        lines.push("First action: do not rerun, delete, cleanup, drain, or reprocess until blocked proof is explained.");
      } else if (review) {
        lines.push("First action: read the review rows, then compare Completed Manifest, Run Logs, Last Stderr, and Pending Publish before accepting output.");
      } else {
        lines.push("First action: use this as read-only confidence support; backend state remains authoritative.");
      }
      lines.push("Mutation guardrail: this checklist does not accept, delete, rerun, reprocess, drain, cleanup, write manifests, or change policy.");
      return lines;
    }

    function completedAcceptanceDetailLines(item) {
      if (!item) {
        return [
          "Completed output acceptance checklist:",
          "Select a completed output acceptance checkpoint for detail.",
          "Mutation guardrail: no action is performed from this detail panel.",
        ];
      }
      const lines = [
        "Completed output acceptance checklist:",
        `Checkpoint: ${item.checkpoint || "unknown"}`,
        `Posture: ${item.posture || "read-only"}`,
        `Evidence: ${item.evidence || ""}`,
        `Safe next step: ${item.action || ""}`,
      ];
      (Array.isArray(item.detail) ? item.detail : []).forEach((line) => lines.push(line));
      if (item.completedRow) {
        lines.push("");
        lines.push("Associated completed row:");
        lines.push(`Title: ${completedProofRowLabel(item.completedRow)}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(item.completedRow) || "unknown"}`);
        lines.push(`Source: ${completedProofCompletedSourcePath(item.completedRow) || "unknown"}`);
        lines.push(`Output growth: ${item.completedRow.size_delta_label || "unknown"}`);
        lines.push(`Safe next action: ${item.completedRow.safe_next_action || "read diagnostics before acting"}`);
      }
      lines.push("");
      lines.push("Guardrail: accepting an output is an operator judgment, not a WebView state mutation.");
      return lines;
    }

    function selectedCompletedAcceptanceRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedCompletedAcceptanceKey) || list[0] || null;
    }

    function selectCompletedAcceptanceRow(item) {
      state.selectedCompletedAcceptanceKey = item?.key || "";
      if (item?.completedRow?.row_key) {
        state.selectedCompletedRowKey = item.completedRow.row_key;
        renderCompletedDetail(item.completedRow);
        renderCompletedRows();
        renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
        renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      }
      renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
    }

    function renderCompletedOutputAcceptance(completed = state.lastCompletedPayload, rows = state.lastCompletedRows, proofRows = state.lastCompletedPendingProofRows, commandEntries) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : [];
      const acceptanceRows = completedAcceptanceRows(payload, rowList, proofRows, commandEntries);
      if (state.selectedCompletedAcceptanceKey && !acceptanceRows.some((row) => row.key === state.selectedCompletedAcceptanceKey)) {
        state.selectedCompletedAcceptanceKey = "";
      }
      const selected = selectedCompletedAcceptanceRow(acceptanceRows);
      setText("completed-output-acceptance-status", completedAcceptanceStatus(acceptanceRows));
      setText("completed-output-acceptance-summary", completedAcceptanceSummaryLines(acceptanceRows).join("\n"));
      setText("completed-output-acceptance-detail", completedAcceptanceDetailLines(selected).join("\n"));
      const tbody = byId("completed-output-acceptance-rows");
      if (!tbody) return;
      if (!acceptanceRows.length) {
        clearRows(tbody, 4, "No completed output acceptance rows loaded.");
        updateTableStatusLegend("completed-output-acceptance-legend", tbody, "Completed output acceptance rows");
        return;
      }
      tbody.replaceChildren();
      acceptanceRows.forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedAcceptancePostureStatus(item.posture);
        appendCells(row, [
          item.checkpoint || "",
          item.posture || "Read-only",
          item.evidence || "",
          item.action || "",
        ]);
        makeRowSelectable(row, () => selectCompletedAcceptanceRow(item), {
          selected: item.key === state.selectedCompletedAcceptanceKey,
          label: `Review completed output acceptance checkpoint ${item.checkpoint || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-output-acceptance-legend", tbody, "Completed output acceptance rows");
    }

    function completedRouteAgreementRouteToken(row, kind = "completed") {
      const value = kind === "queue"
        ? completedProofFirstValue(row, ["route_name", "route", "route_label", "route_decision_summary"])
        : completedProofFirstValue(row, ["route", "route_label", "route_name", "route_decision_summary"]);
      const text = String(value || "").trim().toLowerCase();
      if (!text) return "";
      if (text.includes("remux") || text.includes("copy")) return "remux";
      if (text.includes("encode") || text.includes("transcode")) return "encode";
      return text.replace(/[^a-z0-9]+/g, " ").trim().split(/\s+/)[0] || text;
    }

    function completedRouteAgreementReason(row, kind = "completed") {
      const value = kind === "queue"
        ? completedProofFirstValue(row, ["route_reason_code", "route_reason", "route_decision_summary", "blocked_reason_code"])
        : completedProofFirstValue(row, ["route_reason_code", "route_reason", "route_decision_summary"]);
      return String(value || "").trim().toLowerCase();
    }

    function completedRouteAgreementQueueSourcePath(row) {
      return completedProofFirstValue(row, ["source_path", "path", "file", "input_path"]);
    }

    function completedRouteAgreementQueueRowLabel(row) {
      return completedProofFirstValue(row, ["display_name", "relative_path", "source_path", "path"]) || "(queue row)";
    }

    function completedRouteAgreementRouteEvidenceCount(rows) {
      return (Array.isArray(rows) ? rows : []).filter((row) => {
        const evidence = Array.isArray(row?.route_evidence_lines) ? row.route_evidence_lines : [];
        return Boolean(row?.route_decision_summary || row?.route_reason || row?.route_reason_code || evidence.length);
      }).length;
    }

    function completedRouteAgreementQueueIndexes(queueRows) {
      const exact = new Map();
      const leaf = new Map();
      (Array.isArray(queueRows) ? queueRows : []).forEach((row, index) => {
        const path = completedRouteAgreementQueueSourcePath(row);
        const normalized = completedProofNormalizePath(path);
        const leafKey = completedProofLeaf(path).toLowerCase();
        const record = { row, index, path, normalized, leafKey, label: completedRouteAgreementQueueRowLabel(row) };
        if (normalized) {
          if (!exact.has(normalized)) exact.set(normalized, []);
          exact.get(normalized).push(record);
        }
        if (leafKey) {
          if (!leaf.has(leafKey)) leaf.set(leafKey, []);
          leaf.get(leafKey).push(record);
        }
      });
      return { exact, leaf };
    }

    function completedRouteAgreementPostureStatus(posture) {
      const normalized = String(posture || "").toLowerCase();
      if (normalized.includes("blocked") || normalized.includes("mismatch")) return "blocked";
      if (normalized.includes("review")) return "warning";
      if (normalized.includes("read-first")) return "changed";
      if (normalized.includes("unknown") || normalized.includes("no queue")) return "unknown";
      return "match";
    }

    function completedRouteAgreementRows(completed = state.lastCompletedPayload, completedRows = state.lastCompletedRows, queuePayload, queueRows) {
      const payload = completed || {};
      const rowList = Array.isArray(completedRows) ? completedRows : [];
      const queue = queuePayload && typeof queuePayload === "object" ? queuePayload : {};
      const qRows = Array.isArray(queueRows) ? queueRows : [];
      const rowsOut = [];
      const add = (key, signal, posture, evidence, action, detail = [], completedRow = null, queueRow = null) => {
        rowsOut.push({ key, signal, posture, evidence, action, detail, completedRow, queueRow });
      };
      const completedEvidenceCount = completedRouteAgreementRouteEvidenceCount(rowList);
      const audioRows = rowList.filter((row) => Number(row?.audio_decision_count || 0) > 0 || (Array.isArray(row?.audio_decision_preview) && row.audio_decision_preview.length)).length;
      const subtitleRows = rowList.filter((row) => Number(row?.subtitle_decision_count || 0) > 0 || (Array.isArray(row?.subtitle_decision_preview) && row.subtitle_decision_preview.length)).length;

      add(
        "completed-route-proof-coverage",
        "Completed route proof coverage",
        rowList.length && completedEvidenceCount < rowList.length ? "Review" : rowList.length ? "Ready-looking" : "Read-only",
        `completed rows=${rowList.length}; rows with route proof=${completedEvidenceCount}; audio proof rows=${audioRows}; subtitle proof rows=${subtitleRows}`,
        rowList.length
          ? "Use selected completed rows to compare route, audio, subtitle, size, and publish proof before accepting surprising outputs."
          : "Run or load completed history before using route agreement as real-media proof.",
        [
          "This coverage check only tells whether completed rows expose proof fields in the loaded manifest preview.",
          "It does not prove Plex playback, subtitle OCR quality, or pending-publish completion.",
        ],
      );

      if (payload.error) {
        add(
          "completed-unavailable",
          "Completed manifest unavailable",
          "Blocked review",
          `Completed history unavailable: ${payload.error}`,
          "Open Diagnostics > Completed Manifest, Run Logs, and Last Stderr before trusting route agreement.",
        );
        return rowsOut;
      }
      if (queue.error) {
        add(
          "queue-unavailable",
          "Queue context unavailable",
          "Review",
          `Queue preview unavailable: ${queue.error}`,
          "Open Queue Snapshot and Run Logs; completed rows cannot be compared against current queue state.",
        );
        return rowsOut;
      }

      const indexes = completedRouteAgreementQueueIndexes(qRows);
      let exactMatches = 0;
      let routeMismatches = 0;
      let reasonMismatches = 0;
      let leafHints = 0;
      const matchedCompletedKeys = new Set();

      rowList.forEach((completedRow, completedIndex) => {
        const source = completedProofCompletedSourcePath(completedRow);
        const normalized = completedProofNormalizePath(source);
        const sourceLeaf = completedProofLeaf(source).toLowerCase();
        const exactQueue = normalized ? indexes.exact.get(normalized) || [] : [];
        if (exactQueue.length) {
          matchedCompletedKeys.add(completedRow.row_key || String(completedIndex));
          exactQueue.slice(0, 4).forEach((queueRecord) => {
            exactMatches += 1;
            const completedRoute = completedRouteAgreementRouteToken(completedRow, "completed");
            const queueRoute = completedRouteAgreementRouteToken(queueRecord.row, "queue");
            const completedReason = completedRouteAgreementReason(completedRow, "completed");
            const queueReason = completedRouteAgreementReason(queueRecord.row, "queue");
            const routeMismatch = Boolean(completedRoute && queueRoute && completedRoute !== queueRoute);
            const reasonMismatch = Boolean(completedReason && queueReason && completedReason !== queueReason);
            if (routeMismatch) routeMismatches += 1;
            if (!routeMismatch && reasonMismatch) reasonMismatches += 1;
            add(
              `exact-${completedRow.row_key || completedIndex}-${queueRecord.index}`,
              routeMismatch ? "Route mismatch" : "Completed source still queued",
              routeMismatch ? "Blocked mismatch" : reasonMismatch ? "Review" : "Review",
              `source=${source || "unknown"}; completed route=${completedRoute || "unknown"}; queue route=${queueRoute || "unknown"}; completed reason=${completedReason || "unknown"}; queue reason=${queueReason || "unknown"}`,
              routeMismatch
                ? "Refresh Queue, inspect Completed Manifest and Queue Snapshot, and do not launch this source until the route conflict is explained."
                : "Confirm whether this is stale queue state, intentional reprocess, or an output that completed but still appears runnable.",
              [
                `Completed: ${completedProofRowLabel(completedRow)}`,
                `Queue: ${queueRecord.label}`,
                `Completed output: ${completedProofCompletedOutputPath(completedRow) || "unknown"}`,
                `Queue source: ${queueRecord.path || "unknown"}`,
                "Exact source-path overlap is stronger than title matching and should be resolved before unattended launch.",
              ],
              completedRow,
              queueRecord.row,
            );
          });
          return;
        }
        const leafQueue = sourceLeaf ? indexes.leaf.get(sourceLeaf) || [] : [];
        leafQueue.slice(0, 2).forEach((queueRecord) => {
          leafHints += 1;
          add(
            `leaf-${completedRow.row_key || completedIndex}-${queueRecord.index}`,
            "Same filename review",
            "Read-first",
            `filename=${sourceLeaf || "unknown"}; completed source=${source || "unknown"}; queue source=${queueRecord.path || "unknown"}`,
            "Treat this as a duplicate-title hint only; compare full folders, season/movie context, and route evidence before acting.",
            [
              "Filename-only matches are deliberately weaker than exact path matches.",
              "They can catch duplicate-title or moved-folder surprises, but they are not proof of a completed/queued conflict.",
            ],
            completedRow,
            queueRecord.row,
          );
        });
      });

      if (!qRows.length) {
        add(
          "no-queue-context",
          "No current queue rows",
          rowList.length ? "Ready-looking" : "No queue context",
          `completed rows=${rowList.length}; queue rows=0`,
          rowList.length
            ? "This is expected after a clean run, but empty Queue does not prove missing source discovery is correct. Use Diagnostics if sources are expected."
            : "No completed or queued rows are loaded, so route agreement cannot prove anything yet.",
        );
      } else if (!exactMatches && !leafHints) {
        add(
          "no-overlap",
          "No source overlap",
          "Ready-looking",
          `completed rows=${rowList.length}; queue rows=${qRows.length}; exact overlaps=0; filename hints=0`,
          "Completed sources do not appear in current Queue by exact path. Continue with row-level route proof for surprising output size or subtitle/audio behavior.",
        );
      }

      add(
        "agreement-summary",
        "Agreement summary",
        routeMismatches ? "Blocked mismatch" : exactMatches || reasonMismatches || leafHints ? "Review" : "Ready-looking",
        `exact source overlaps=${exactMatches}; route mismatches=${routeMismatches}; reason mismatches=${reasonMismatches}; filename hints=${leafHints}; matched completed rows=${matchedCompletedKeys.size}`,
        routeMismatches
          ? "Resolve route mismatches before launch/rerun. A completed source appearing queued with a different route is high-risk."
          : exactMatches
            ? "Review exact overlaps before launch; they may indicate stale queue state, intentional reprocess, or completed-history drift."
            : "No loaded queue/completed route conflict is visible.",
        [
          "Agreement checks are read-only and compare loaded WebView payloads only.",
          "Backend launch, completed-history reconciliation, rerun, cleanup, and pending-publish movement remain separate backend-owned workflows.",
        ],
      );

      return rowsOut.sort((left, right) => {
        const rank = { blocked: 0, warning: 1, changed: 2, unknown: 3, match: 4 };
        return (rank[completedRouteAgreementPostureStatus(left.posture)] ?? 5) - (rank[completedRouteAgreementPostureStatus(right.posture)] ?? 5);
      });
    }

    function completedRouteAgreementStatus(rows) {
      const list = Array.isArray(rows) ? rows : [];
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "blocked")) return "Route mismatch";
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "warning")) return "Review overlap";
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "changed")) return "Read filename hints";
      if (list.some((row) => completedRouteAgreementPostureStatus(row.posture) === "unknown")) return "No queue context";
      return list.length ? "Ready-looking" : "Not loaded";
    }

    function completedRouteAgreementSummaryLines(rows) {
      const list = Array.isArray(rows) ? rows : [];
      const blocked = list.filter((row) => completedRouteAgreementPostureStatus(row.posture) === "blocked").length;
      const review = list.filter((row) => completedRouteAgreementPostureStatus(row.posture) === "warning").length;
      const readFirst = list.filter((row) => completedRouteAgreementPostureStatus(row.posture) === "changed").length;
      const lines = [
        "Queue / Completed route agreement:",
        `Rows: ${list.length}; blocked=${blocked}; review=${review}; read-first=${readFirst}.`,
        "Decision rule: a completed source should not appear runnable in Queue unless this is deliberate reprocess; if it does, completed route/reason evidence should not contradict Queue route/reason evidence.",
      ];
      if (blocked) {
        lines.push("First action: refresh Queue, open Completed Manifest and Queue Snapshot, then read Last Stderr/Run Logs before launch or rerun.");
      } else if (review || readFirst) {
        lines.push("First action: select review/read-first rows and compare full paths before trusting same-title or stale queue state.");
      } else {
        lines.push("First action: no loaded queue/completed route conflict is visible; use selected Completed rows for route/audio/subtitle/size proof.");
      }
      lines.push("Mutation guardrail: this agreement panel does not launch, rerun, drain, repair, reconcile, delete, rewrite manifests, or touch media files.");
      return lines;
    }

    function completedRouteAgreementDetailLines(item) {
      if (!item) {
        return [
          "Queue / Completed route agreement:",
          "Select an agreement row to inspect the queue/completed evidence.",
          "Mutation guardrail: no action is performed from this detail panel.",
        ];
      }
      const lines = [
        "Queue / Completed route agreement:",
        `Signal: ${item.signal || "unknown"}`,
        `Posture: ${item.posture || "read-only"}`,
        `Evidence: ${item.evidence || ""}`,
        `Safe next step: ${item.action || ""}`,
      ];
      (Array.isArray(item.detail) ? item.detail : []).forEach((line) => lines.push(line));
      if (item.completedRow) {
        lines.push("");
        lines.push("Completed row proof:");
        lines.push(`Title: ${completedProofRowLabel(item.completedRow)}`);
        lines.push(`Source: ${completedProofCompletedSourcePath(item.completedRow) || "unknown"}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(item.completedRow) || "unknown"}`);
        lines.push(`Route: ${completedRouteAgreementRouteToken(item.completedRow, "completed") || "unknown"}; reason=${completedRouteAgreementReason(item.completedRow, "completed") || "unknown"}`);
        lines.push(`Size: ${item.completedRow.size_delta_label || item.completedRow.size_reduction_text || "unknown"}`);
        const evidence = Array.isArray(item.completedRow.route_evidence_lines) ? item.completedRow.route_evidence_lines.filter(Boolean) : [];
        evidence.slice(0, 5).forEach((line) => lines.push(`Completed evidence: ${line}`));
      }
      if (item.queueRow) {
        lines.push("");
        lines.push("Queue row proof:");
        lines.push(`Source: ${completedRouteAgreementQueueSourcePath(item.queueRow) || "unknown"}`);
        lines.push(`Route: ${completedRouteAgreementRouteToken(item.queueRow, "queue") || "unknown"}; reason=${completedRouteAgreementReason(item.queueRow, "queue") || "unknown"}`);
        lines.push(`Status: ${item.queueRow.operator_status || item.queueRow.status || "unknown"}`);
        const evidence = Array.isArray(item.queueRow.route_evidence_lines) ? item.queueRow.route_evidence_lines.filter(Boolean) : [];
        evidence.slice(0, 5).forEach((line) => lines.push(`Queue evidence: ${line}`));
      }
      lines.push("");
      lines.push("Guardrail: this compares loaded Queue and Completed payloads only. Backend state, launch preflight, and diagnostics remain authoritative.");
      return lines;
    }

    function selectedCompletedRouteAgreementRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row) => row.key === state.selectedCompletedRouteAgreementKey)
        || list.find((row) => completedRouteAgreementPostureStatus(row.posture) !== "match")
        || list[0]
        || null;
    }

    function selectCompletedRouteAgreementRow(item) {
      state.selectedCompletedRouteAgreementKey = item?.key || "";
      if (item?.completedRow?.row_key) {
        state.selectedCompletedRowKey = item.completedRow.row_key;
        renderCompletedDetail(item.completedRow);
        renderCompletedRows();
        renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
        renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
        renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      }
      renderCompletedRouteAgreement(
        state.lastCompletedPayload,
        state.lastCompletedRows,
        typeof window.getLastQueuePayload === "function" ? window.getLastQueuePayload() : {},
        typeof window.getLastQueueRows === "function" ? window.getLastQueueRows() : [],
      );
    }

    function renderCompletedRouteAgreement(completed = state.lastCompletedPayload, completedRows = state.lastCompletedRows, queuePayload, queueRows) {
      const rows = completedRouteAgreementRows(completed, completedRows, queuePayload, queueRows);
      state.lastCompletedRouteAgreementRows = rows;
      if (state.selectedCompletedRouteAgreementKey && !rows.some((row) => row.key === state.selectedCompletedRouteAgreementKey)) {
        state.selectedCompletedRouteAgreementKey = "";
      }
      const selected = selectedCompletedRouteAgreementRow(rows);
      setText("completed-route-agreement-status", completedRouteAgreementStatus(rows));
      const statusNode = byId("completed-route-agreement-status");
      if (statusNode) statusNode.dataset.state = completedRouteAgreementPostureStatus(selected?.posture || completedRouteAgreementStatus(rows));
      setText("completed-route-agreement-summary", completedRouteAgreementSummaryLines(rows).join("\n"));
      setText("completed-route-agreement-detail", completedRouteAgreementDetailLines(selected).join("\n"));
      const tbody = byId("completed-route-agreement-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 4, "No queue/completed route agreement rows loaded.");
        updateTableStatusLegend("completed-route-agreement-legend", tbody, "Queue/completed route agreement rows");
        return;
      }
      tbody.replaceChildren();
      rows.slice(0, 120).forEach((item) => {
        const row = document.createElement("tr");
        row.dataset.status = completedRouteAgreementPostureStatus(item.posture);
        appendCells(row, [
          item.signal || "",
          item.posture || "Read-only",
          item.evidence || "",
          item.action || "",
        ]);
        makeRowSelectable(row, () => selectCompletedRouteAgreementRow(item), {
          selected: item.key === state.selectedCompletedRouteAgreementKey,
          label: `Review queue/completed agreement ${item.signal || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-route-agreement-legend", tbody, "Queue/completed route agreement rows");
    }

    function completedProofRows(payload) {
      return Array.isArray(payload?.rows) ? payload.rows : [];
    }

    function completedProofDrainSummaryPayload(pending) {
      const summary = pending?.drain_summary;
      return summary && typeof summary === "object" ? summary : {};
    }

    function completedProofDrainSummaryItems(pending) {
      const summary = completedProofDrainSummaryPayload(pending || {});
      return Array.isArray(summary.items) ? summary.items : [];
    }

    function completedProofNormalizePath(value) {
      const s = String(value || "").trim().replace(/\//g, "\\");
      const unc = s.startsWith("\\\\") ? "\\\\" : "";
      return (unc + s.slice(unc.length).replace(/\\+/g, "\\")).toLowerCase();
    }

    function completedProofPathLooksAbsolute(value) {
      const text = String(value || "").trim();
      return Boolean(text && (/^[a-zA-Z]:[\\/]/.test(text) || /^\\\\/.test(text) || text.includes("\\") || text.includes("/")));
    }

    function completedProofLeaf(value) {
      const text = String(value || "").trim();
      if (!text) return "";
      const parts = text.split(/[\\/]/).filter(Boolean);
      return parts.length ? parts[parts.length - 1] : text;
    }

    function completedProofFirstValue(item, keys) {
      for (const key of keys) {
        const value = item?.[key];
        if (value !== undefined && value !== null && String(value).trim()) return String(value).trim();
      }
      return "";
    }

    function completedProofCompletedOutputPath(row) {
      return completedProofFirstValue(row, ["output_path", "server_out", "destination_path", "final_path", "output_file"]);
    }

    function completedProofCompletedSourcePath(row) {
      return completedProofFirstValue(row, ["source_path", "input_path", "source_file"]);
    }

    function completedProofRowMissingOutput(row) {
      const outputHealth = String(row?.output_health || row?.output_status || row?.operator_status || "").toLowerCase();
      return Boolean(
        row?.output_exists === false
        || row?.missing_output === true
        || ["missing", "missing output", "not_found", "not found", "deleted", "unavailable"].some((token) => outputHealth.includes(token))
      );
    }

    function completedProofPendingDestinationPath(row) {
      return completedProofFirstValue(row, ["server_out", "destination_path", "output_path"]);
    }

    function completedProofPendingSourcePath(row) {
      return completedProofFirstValue(row, ["source_path", "input_path", "source_file"]);
    }

    function completedProofPendingLocalPath(row) {
      return completedProofFirstValue(row, ["local_file", "payload_path", "scratch_path", "manifest_path"]);
    }

    function completedProofRowKey(row, fallback = "") {
      return String(row?.row_key || row?.source_path || row?.output_path || row?.output_file || fallback || "").trim();
    }

    function completedProofRowLabel(row) {
      return completedProofFirstValue(row, ["lookup_title", "output_file", "title", "route_label"])
        || completedProofLeaf(completedProofCompletedOutputPath(row))
        || completedProofLeaf(completedProofCompletedSourcePath(row))
        || "(completed row)";
    }

    function completedProofPendingLabel(row) {
      return completedProofFirstValue(row, ["lookup_title", "output_file", "title", "state"])
        || completedProofLeaf(completedProofPendingDestinationPath(row))
        || completedProofLeaf(completedProofPendingLocalPath(row))
        || completedProofLeaf(completedProofPendingSourcePath(row))
        || "(pending row)";
    }

    function completedProofDrainItemLabel(item) {
      return completedProofFirstValue(item, ["lookup_title", "output_file", "title", "status"])
        || completedProofLeaf(completedProofPendingDestinationPath(item))
        || completedProofLeaf(completedProofPendingLocalPath(item))
        || completedProofLeaf(completedProofPendingSourcePath(item))
        || "(drain item)";
    }

    function completedPendingProofSignalLabel(signal) {
      const labels = {
        "pending-destination-overlap": "Pending destination overlap",
        "completed-source-still-pending": "Completed source still pending",
        "drain-summary-output-proof": "Drain output proof",
        "drain-summary-source-proof": "Drain source proof",
        "same-leaf-review": "Same leaf review",
        "completed-missing-output-still-pending": "Missing output still parked",
        "completed-missing-output-with-drain-proof": "Missing output with drain proof",
        "completed-missing-output-no-pending-proof": "Missing output without pending proof",
      };
      return labels[signal] || signal || "Review";
    }

    function completedPendingProofIsExactPathSignal(signal) {
      return [
        "pending-destination-overlap",
        "completed-source-still-pending",
        "drain-summary-output-proof",
        "drain-summary-source-proof",
        "completed-missing-output-still-pending",
        "completed-missing-output-with-drain-proof",
      ].includes(String(signal || ""));
    }

    function completedPendingProofIsFinalPlacementReviewSignal(signal) {
      return [
        "completed-missing-output-still-pending",
        "completed-missing-output-with-drain-proof",
      ].includes(String(signal || ""));
    }

    function completedPendingProofDataStatus(value, options = {}) {
      const status = String(value?.status || value?.state || value?.diagnostic_status || value?.result || "").toLowerCase();
      const severity = String(value?.diagnostic_severity || value?.operator_severity || value?.severity || "").toLowerCase();
      const recommendation = String(value?.drain_recommendation || value?.operator_guidance || value?.issue_summary || "").toLowerCase();
      if (value?.do_not_drain || value?.read_error || value?.error || severity === "error") return "blocked";
      if (["error", "failed", "failure", "stopped"].some((token) => status.includes(token))) return "blocked";
      if (status.includes("skipped") && !options.allowSkippedAsReview) return "blocked";
      if (["do not drain", "missing", "invalid", "blocked"].some((token) => recommendation.includes(token))) return "blocked";
      if (["succeeded", "success", "already_published", "already-published", "published"].some((token) => status.includes(token))) return "match";
      if (["warning", "review", "deferred", "skipped", "remaining"].some((token) => status.includes(token) || recommendation.includes(token))) return "warning";
      return options.defaultStatus || "warning";
    }

    function completedPendingProofEvidenceText(item) {
      const parts = [];
      if (item.signal === "pending-destination-overlap") {
        parts.push("Exact completed output path matches a current pending publish destination.");
      } else if (item.signal === "completed-source-still-pending") {
        parts.push("Exact completed source path also exists in current pending publish state.");
      } else if (item.signal === "drain-summary-output-proof") {
        parts.push("Exact completed output path appears in the latest durable pending drain summary.");
      } else if (item.signal === "drain-summary-source-proof") {
        parts.push("Exact completed source path appears in the latest durable pending drain summary.");
      } else if (item.signal === "same-leaf-review") {
        parts.push("Only the filename leaf matches; full paths differ or are missing.");
      } else if (item.signal === "completed-missing-output-still-pending") {
        parts.push("Completed row reports a missing output, but exact Pending Publish proof still exists for this source/output.");
      } else if (item.signal === "completed-missing-output-with-drain-proof") {
        parts.push("Completed row reports a missing output, but exact durable drain-summary proof exists for this source/output.");
      } else if (item.signal === "completed-missing-output-no-pending-proof") {
        parts.push("Completed row reports a missing output and no exact pending or durable drain proof matched this row.");
      }
      if (item.match_path) parts.push(`Path: ${item.match_path}`);
      if (item.pending?.state) parts.push(`Pending state: ${item.pending.state}`);
      if (item.pending?.drain_recommendation) parts.push(`Drain recommendation: ${item.pending.drain_recommendation}`);
      if (item.drain_item?.status) parts.push(`Drain status: ${item.drain_item.status}`);
      if (item.drain_item?.error) parts.push(`Drain error: ${item.drain_item.error}`);
      return parts.join(" ");
    }

    function completedPendingProofNextAction(item) {
      if (item.signal === "same-leaf-review") {
        return "Treat as a duplicate-title/path review only; compare folders before taking action.";
      }
      if (item.signal === "completed-missing-output-still-pending") {
        return "Treat as deferred-publish or stale Completed proof; inspect Pending Publish and do not rerun, clean up, or delete until the parked payload is explained.";
      }
      if (item.signal === "completed-missing-output-with-drain-proof") {
        return "Treat as final-placement conflict; compare output folder, durable drain summary, Run Logs, and Last Stderr before rerun or cleanup.";
      }
      if (item.signal === "completed-missing-output-no-pending-proof") {
        return "Open Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun; an empty Pending Publish page is not proof that the file published.";
      }
      if (item.status === "blocked") {
        return "Open Pending Publish and Diagnostics; do not drain or rerun until the blocker is explained.";
      }
      if (item.signal === "pending-destination-overlap" || item.signal === "completed-source-still-pending") {
        return "Compare Completed, Pending Publish, and Run Logs before retrying or deleting any output.";
      }
      if (item.status === "match") {
        return "Use as supporting publish proof; Completed and Pending evidence still remain read-only here.";
      }
      return "Review row detail and diagnostics before acting.";
    }

    function completedPendingProofRowKey(item, index = 0) {
      if (!item || typeof item !== "object") return `completed-pending-proof-${index}`;
      return [
        item.signal || "proof",
        completedProofRowKey(item.completed, item.completed_index),
        item.pending ? completedProofRowKey(item.pending, item.pending_index) : "",
        item.drain_item ? `${item.drain_index || 0}:${completedProofDrainItemLabel(item.drain_item)}` : "",
        item.match_path || "",
        index,
      ].join("|");
    }

    function completedPendingProofDto(completed, pending) {
      const candidates = [
        completed?.completed_pending_proof,
        pending?.completed_pending_proof,
        state.lastPublishReconciliationPayload?.completed_pending_proof,
      ];
      return candidates.find((candidate) => (
        candidate
        && typeof candidate === "object"
        && candidate.schema_version === "desktop_completed_pending_proof.v1"
        && Array.isArray(candidate.rows)
        && completedPendingProofDtoMatches(candidate, completed || {}, pending || {})
      )) || null;
    }

    function completedPendingProofDtoMatches(dto, completed, pending) {
      const expectedCompletedCount = Number(completed?.count || (Array.isArray(completed?.rows) ? completed.rows.length : 0) || 0);
      if (Number.isFinite(Number(dto?.completed_count)) && Number(dto.completed_count) !== expectedCompletedCount) return false;
      const pendingHasExplicitPayload = pending && typeof pending === "object" && (
        Array.isArray(pending.rows)
        || pending.count !== undefined
        || (pending.drain_summary && typeof pending.drain_summary === "object")
      );
      if (pendingHasExplicitPayload) {
        const expectedPendingCount = Number(pending?.count || (Array.isArray(pending?.rows) ? pending.rows.length : 0) || 0);
        if (Number.isFinite(Number(dto?.pending_count)) && Number(dto.pending_count) !== expectedPendingCount) return false;
        const expectedDrainItems = Array.isArray(pending?.drain_summary?.items) ? pending.drain_summary.items.length : 0;
        if (expectedDrainItems && Number.isFinite(Number(dto?.drain_item_count)) && Number(dto.drain_item_count) !== expectedDrainItems) return false;
      }
      return true;
    }

    function completedPendingProofDtoRows(dto) {
      return Array.isArray(dto?.rows) ? dto.rows.filter((row) => row && typeof row === "object") : [];
    }

    function completedPendingProofSelectedRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row, index) => completedPendingProofRowKey(row, index) === state.selectedCompletedPendingProofKey)
        || list.find((row) => row.status === "blocked")
        || list.find((row) => row.status === "warning")
        || list[0]
        || null;
    }

    function completedPendingProofDetailLines(item) {
      if (!item) {
        return [
          "Completed-to-Pending output proof cross-check:",
          "Select a proof row to inspect the exact Completed, Pending Publish, or durable drain-summary evidence.",
          "Mutation guardrail: this detail panel is read-only and cannot accept, repair, rerun, drain, delete, publish, rewrite manifests, or touch media files.",
        ];
      }
      const lines = [
        "Completed-to-Pending output proof cross-check:",
        `Signal: ${completedPendingProofSignalLabel(item.signal)}`,
        `Status: ${item.status || "review"}`,
        `Evidence: ${completedPendingProofEvidenceText(item) || "no evidence text"}`,
        `Safe next step: ${completedPendingProofNextAction(item)}`,
      ];
      if (item.completed) {
        lines.push("");
        lines.push("Completed row:");
        lines.push(`Title: ${completedProofRowLabel(item.completed)}`);
        lines.push(`Row key: ${item.completed.row_key || completedProofRowKey(item.completed, item.completed_index) || "(not reported)"}`);
        lines.push(`Source: ${completedProofCompletedSourcePath(item.completed) || "unknown"}`);
        lines.push(`Output: ${completedProofCompletedOutputPath(item.completed) || "unknown"}`);
        lines.push(`Output health: ${item.completed.output_health || (item.completed.output_exists === false ? "missing output" : "not reported")}`);
        lines.push(`Route: ${item.completed.route || item.completed.route_label || "unknown"}; reason=${item.completed.route_reason_code || item.completed.route_reason || "unknown"}`);
        lines.push(`Size: ${item.completed.size_delta_label || item.completed.size_reduction_text || "unknown"}`);
      }
      if (item.pending) {
        lines.push("");
        lines.push("Pending Publish row:");
        lines.push(`State: ${item.pending.state || item.pending.diagnostic_status || "unknown"}`);
        lines.push(`Drain recommendation: ${item.pending.drain_recommendation || "not reported"}`);
        lines.push(`Local payload: ${completedProofPendingLocalPath(item.pending) || "unknown"}`);
        lines.push(`Destination: ${completedProofPendingDestinationPath(item.pending) || "unknown"}`);
        lines.push(`Source: ${completedProofPendingSourcePath(item.pending) || "unknown"}`);
        lines.push(`Issue summary: ${item.pending.issue_summary || item.pending.error || "none loaded"}`);
      }
      if (item.drain_item) {
        lines.push("");
        lines.push("Durable drain summary item:");
        lines.push(`Status: ${item.drain_item.status || item.drain_item.result || "unknown"}`);
        lines.push(`Destination: ${completedProofPendingDestinationPath(item.drain_item) || "unknown"}`);
        lines.push(`Source: ${completedProofPendingSourcePath(item.drain_item) || "unknown"}`);
        lines.push(`Local payload: ${completedProofPendingLocalPath(item.drain_item) || "unknown"}`);
        if (item.drain_item.error) lines.push(`Error: ${item.drain_item.error}`);
      }
      lines.push("");
      lines.push("Proof order: Completed Manifest row -> exact output/source path -> Pending Publish row/state -> durable drain summary -> Run Logs / Last Stderr.");
      lines.push("Boundary: same-leaf matches are duplicate-title hints only; exact normalized paths are stronger evidence.");
      lines.push("Mutation guardrail: this detail panel does not accept, repair, rerun, drain, cleanup, delete, publish, rewrite manifests, or touch media files.");
      return lines;
    }

    function renderCompletedPendingProofDetail(item) {
      setText("completed-pending-proof-detail", completedPendingProofDetailLines(item).join("\n"));
    }

    function selectCompletedPendingProofRow(item, index = 0) {
      state.selectedCompletedPendingProofKey = completedPendingProofRowKey(item, index);
      if (item?.completed?.row_key) {
        state.selectedCompletedRowKey = item.completed.row_key;
      }
      renderCompletedDetail(item?.completed || getSelectedCompletedRow());
      renderCompletedRows();
      renderCompletedReviewDigest(state.lastCompletedPayload, state.lastCompletedRows);
      renderCompletedSizeReview(state.lastCompletedPayload, state.lastCompletedRows);
      renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
      renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
      renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
      renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
    }

    function completedPendingProofRows(completed, rows, pending) {
      const dto = completedPendingProofDto(completed || {}, pending || {});
      if (dto) return completedPendingProofDtoRows(dto);
      const completedRows = Array.isArray(rows) ? rows : completedProofRows(completed || {});
      const pendingRows = completedProofRows(pending || {});
      const drainItems = completedProofDrainSummaryItems(pending || {});
      const proofRows = [];
      const seen = new Set();
      const pendingDestinationIndex = new Map();
      const pendingSourceIndex = new Map();
      const pendingLeafIndex = new Map();
      const drainDestinationIndex = new Map();
      const drainSourceIndex = new Map();
      const drainLeafIndex = new Map();

      function addProof(item) {
        const completedKey = completedProofRowKey(item.completed, item.completed_index);
        const pendingKey = item.pending ? completedProofRowKey(item.pending, item.pending_index) : "";
        const drainKey = item.drain_item ? `${item.drain_index}:${completedProofDrainItemLabel(item.drain_item)}` : "";
        const signature = [item.signal, completedKey, pendingKey, drainKey, item.match_path || ""].join("|");
        if (seen.has(signature)) return;
        seen.add(signature);
        proofRows.push(item);
      }

      function addIndex(map, key, record) {
        if (!key) return;
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(record);
      }

      pendingRows.forEach((pendingRow, pendingIndex) => {
        const pendingDestination = completedProofPendingDestinationPath(pendingRow);
        const pendingDestinationKey = completedProofNormalizePath(pendingDestination);
        const pendingDestinationIsPath = completedProofPathLooksAbsolute(pendingDestination);
        const pendingSource = completedProofPendingSourcePath(pendingRow);
        const pendingSourceKey = completedProofNormalizePath(pendingSource);
        const pendingSourceIsPath = completedProofPathLooksAbsolute(pendingSource);
        const pendingLocal = completedProofPendingLocalPath(pendingRow);
        const pendingLeaf = completedProofLeaf(pendingDestination || pendingLocal).toLowerCase();
        const record = {
          row: pendingRow,
          index: pendingIndex,
          destination: pendingDestination,
          destinationKey: pendingDestinationKey,
          destinationIsPath: pendingDestinationIsPath,
          source: pendingSource,
          sourceKey: pendingSourceKey,
          sourceIsPath: pendingSourceIsPath,
          local: pendingLocal,
        };
        if (pendingDestinationIsPath) addIndex(pendingDestinationIndex, pendingDestinationKey, record);
        if (pendingSourceIsPath) addIndex(pendingSourceIndex, pendingSourceKey, record);
        addIndex(pendingLeafIndex, pendingLeaf, record);
      });

      drainItems.forEach((drainItem, drainIndex) => {
        const drainDestination = completedProofPendingDestinationPath(drainItem);
        const drainDestinationKey = completedProofNormalizePath(drainDestination);
        const drainDestinationIsPath = completedProofPathLooksAbsolute(drainDestination);
        const drainSource = completedProofPendingSourcePath(drainItem);
        const drainSourceKey = completedProofNormalizePath(drainSource);
        const drainSourceIsPath = completedProofPathLooksAbsolute(drainSource);
        const drainLocal = completedProofPendingLocalPath(drainItem);
        const drainLeaf = completedProofLeaf(drainDestination || drainLocal).toLowerCase();
        const record = {
          item: drainItem,
          index: drainIndex,
          destination: drainDestination,
          destinationKey: drainDestinationKey,
          destinationIsPath: drainDestinationIsPath,
          source: drainSource,
          sourceKey: drainSourceKey,
          sourceIsPath: drainSourceIsPath,
          local: drainLocal,
        };
        if (drainDestinationIsPath) addIndex(drainDestinationIndex, drainDestinationKey, record);
        if (drainSourceIsPath) addIndex(drainSourceIndex, drainSourceKey, record);
        addIndex(drainLeafIndex, drainLeaf, record);
      });

      completedRows.forEach((completedRow, completedIndex) => {
        const completedOutput = completedProofCompletedOutputPath(completedRow);
        const completedOutputKey = completedProofNormalizePath(completedOutput);
        const completedOutputLeaf = completedProofLeaf(completedOutput).toLowerCase();
        const completedOutputIsPath = completedProofPathLooksAbsolute(completedOutput);
        const completedSource = completedProofCompletedSourcePath(completedRow);
        const completedSourceKey = completedProofNormalizePath(completedSource);
        const completedSourceIsPath = completedProofPathLooksAbsolute(completedSource);
        let exactProofForCompleted = false;
        const missingCompletedOutput = completedProofRowMissingOutput(completedRow);

        if (completedOutputIsPath && completedOutputKey) {
          (pendingDestinationIndex.get(completedOutputKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.row, { defaultStatus: "warning" });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-still-pending" : "pending-destination-overlap",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              pending: record.row,
              pending_index: record.index,
              match_path: record.destination,
            });
          });
          (drainDestinationIndex.get(completedOutputKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.item, { defaultStatus: "match", allowSkippedAsReview: true });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-with-drain-proof" : "drain-summary-output-proof",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              drain_item: record.item,
              drain_index: record.index,
              match_path: record.destination,
            });
          });
        }

        if (completedSourceIsPath && completedSourceKey) {
          (pendingSourceIndex.get(completedSourceKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.row, { defaultStatus: "warning" });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-still-pending" : "completed-source-still-pending",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              pending: record.row,
              pending_index: record.index,
              match_path: record.source,
            });
          });
          (drainSourceIndex.get(completedSourceKey) || []).forEach((record) => {
            const rowStatus = completedPendingProofDataStatus(record.item, { defaultStatus: "match", allowSkippedAsReview: true });
            exactProofForCompleted = true;
            addProof({
              signal: missingCompletedOutput ? "completed-missing-output-with-drain-proof" : "drain-summary-source-proof",
              status: missingCompletedOutput && rowStatus === "match" ? "warning" : rowStatus,
              completed: completedRow,
              completed_index: completedIndex,
              drain_item: record.item,
              drain_index: record.index,
              match_path: record.source,
            });
          });
        }

        if (missingCompletedOutput && !exactProofForCompleted) {
          addProof({
            signal: "completed-missing-output-no-pending-proof",
            status: "blocked",
            completed: completedRow,
            completed_index: completedIndex,
            match_path: completedOutput || completedSource,
          });
        }

        (pendingLeafIndex.get(completedOutputLeaf) || []).forEach((record) => {
          const exactDestination = Boolean(completedOutputIsPath && record.destinationIsPath && completedOutputKey === record.destinationKey);
          if (exactDestination) return;
          addProof({
            signal: "same-leaf-review",
            status: "warning",
            completed: completedRow,
            completed_index: completedIndex,
            pending: record.row,
            pending_index: record.index,
            match_path: record.destination || record.local,
          });
        });

        (drainLeafIndex.get(completedOutputLeaf) || []).forEach((record) => {
          const exactDestination = Boolean(completedOutputIsPath && record.destinationIsPath && completedOutputKey === record.destinationKey);
          if (exactDestination) return;
          addProof({
            signal: "same-leaf-review",
            status: "warning",
            completed: completedRow,
            completed_index: completedIndex,
            drain_item: record.item,
            drain_index: record.index,
            match_path: record.destination || record.local,
          });
        });
      });

      const statusWeight = { blocked: 0, warning: 1, match: 2 };
      return proofRows.sort((a, b) => (statusWeight[a.status] ?? 3) - (statusWeight[b.status] ?? 3));
    }

    function completedPendingProofStatus(completed, rows, pending) {
      const dto = completedPendingProofDto(completed || {}, pending || {});
      if (dto && dto.status) return String(dto.status);
      const rowList = Array.isArray(rows) ? rows : completedProofRows(completed || {});
      const pendingRows = completedProofRows(pending || {});
      const proofRows = completedPendingProofRows(completed || {}, rowList, pending || {});
      if ((completed || {}).error) return "Completed unavailable";
      if ((pending || {}).error) return "Pending unavailable";
      if (!rowList.length) return "No completed proof";
      if (proofRows.some((row) => row.status === "blocked")) return "Review blockers";
      if (proofRows.some((row) => completedPendingProofIsFinalPlacementReviewSignal(row.signal))) return "Review final placement";
      if (proofRows.some((row) => row.signal === "pending-destination-overlap" || row.signal === "completed-source-still-pending")) return "Review overlaps";
      if (proofRows.some((row) => row.signal === "same-leaf-review")) return "Review leaf matches";
      if (proofRows.some((row) => row.status === "match")) return pendingRows.length ? "Proof with parked rows" : "Proof aligned";
      return pendingRows.length ? "No exact overlap" : "No overlap";
    }

    function completedPendingProofSummaryLines(completed, rows, pending) {
      const dto = completedPendingProofDto(completed || {}, pending || {});
      if (dto && Array.isArray(dto.summary_lines) && dto.summary_lines.length) {
        return dto.summary_lines.filter((line) => String(line || "").trim());
      }
      const payload = completed || {};
      const pendingPayload = pending || {};
      const rowList = Array.isArray(rows) ? rows : completedProofRows(payload);
      const pendingRows = completedProofRows(pendingPayload);
      const drainSummary = completedProofDrainSummaryPayload(pendingPayload);
      const proofRows = completedPendingProofRows(payload, rowList, pendingPayload);
      const exactOutput = proofRows.filter((row) => row.signal === "pending-destination-overlap").length;
      const exactSource = proofRows.filter((row) => row.signal === "completed-source-still-pending").length;
      const drainOutput = proofRows.filter((row) => row.signal === "drain-summary-output-proof" || row.signal === "drain-summary-source-proof").length;
      const leafOnly = proofRows.filter((row) => row.signal === "same-leaf-review").length;
      const missingWithPendingProof = proofRows.filter((row) => row.signal === "completed-missing-output-still-pending").length;
      const missingWithDrainProof = proofRows.filter((row) => row.signal === "completed-missing-output-with-drain-proof").length;
      const missingWithoutProof = proofRows.filter((row) => row.signal === "completed-missing-output-no-pending-proof").length;
      const lines = [
        "Completed-to-Pending output proof cross-check:",
        `Completed rows: ${payload.count || rowList.length || 0}`,
        `Pending rows: ${pendingPayload.count || pendingRows.length || 0}`,
        `Exact completed output -> pending destination: ${exactOutput}`,
        `Exact completed source -> pending source: ${exactSource}`,
        `Completed row found in last drain summary: ${drainOutput}`,
        `Missing completed output with pending proof: ${missingWithPendingProof}`,
        `Missing completed output with drain proof: ${missingWithDrainProof}`,
        `Missing completed output without pending/drain proof: ${missingWithoutProof}`,
        `Same leaf review matches: ${leafOnly}`,
        `Last drain summary: ${drainSummary.read_error ? "unreadable" : drainSummary.exists === false ? "not found" : drainSummary.completed_at || drainSummary.started_at ? "loaded" : "not loaded"}`,
        "",
        "Proof order:",
        "1. Completed Manifest row",
        "2. Completed output/source path",
        "3. Pending Publish row/state",
        "4. Last durable pending drain summary",
        "5. Run Logs / Last Stderr from Diagnostics",
        "",
      ];
      if (payload.error) {
        lines.push(`First action: Completed history is unavailable: ${payload.error}. Open Diagnostics > Completed Manifest and Run Logs.`);
      } else if (pendingPayload.error) {
        lines.push(`First action: Pending Publish state is unavailable: ${pendingPayload.error}. Open Diagnostics > Pending Publish and Run Logs.`);
      } else if (missingWithoutProof) {
        lines.push("First action: missing completed outputs have no exact pending/drain proof. Open Completed Manifest, Pending Publish, Run Logs, and Last Stderr before rerun; empty Pending Publish is not proof of publish.");
      } else if (missingWithPendingProof || missingWithDrainProof) {
        lines.push("First action: missing completed outputs have exact pending/drain proof. Treat this as a final-placement conflict; compare output folder, Pending Publish, durable drain summary, Run Logs, and Last Stderr before rerun or cleanup.");
      } else if (proofRows.some((row) => row.status === "blocked")) {
        lines.push("First action: inspect blocked overlap rows before retrying drain, rerun, cleanup, or output deletion.");
      } else if (exactOutput || exactSource) {
        lines.push("First action: review exact overlaps. A completed row that is still parked can mean stale state, a deferred publish, or a failed drain.");
      } else if (leafOnly) {
        lines.push("First action: review same-leaf rows as duplicate-title hints only; full paths do not prove the same file.");
      } else if (drainOutput) {
        lines.push("First action: use drain-summary matches as supporting publish evidence, then confirm with output folder and run logs if a title is missing.");
      } else if (pendingRows.length) {
        lines.push("First action: no exact completed-to-pending overlap was found. Continue review from Pending Publish readiness and drain evidence.");
      } else {
        lines.push("First action: no completed-to-pending overlap is visible in the loaded payloads.");
      }
      lines.push("Mutation guardrail: this cross-check is read-only; repair, reconciliation, rerun, drain, cleanup, and deletion remain backend-owned.");
      return lines;
    }

    function renderCompletedPendingProof(completed, rows, pending) {
      const payload = completed || {};
      const rowList = Array.isArray(rows) ? rows : completedProofRows(payload);
      state.lastCompletedPendingPayload = pending && typeof pending === "object" ? pending : {};
      const proofRows = completedPendingProofRows(payload, rowList, state.lastCompletedPendingPayload);
      state.lastCompletedPendingProofRows = proofRows;
      if (state.selectedCompletedPendingProofKey && !proofRows.some((row, index) => completedPendingProofRowKey(row, index) === state.selectedCompletedPendingProofKey)) {
        state.selectedCompletedPendingProofKey = "";
      }
      const selectedProofRow = completedPendingProofSelectedRow(proofRows);
      if (!state.selectedCompletedPendingProofKey && selectedProofRow) {
        const selectedIndex = proofRows.indexOf(selectedProofRow);
        state.selectedCompletedPendingProofKey = completedPendingProofRowKey(selectedProofRow, selectedIndex < 0 ? 0 : selectedIndex);
      }
      setText("completed-pending-proof-status", completedPendingProofStatus(payload, rowList, state.lastCompletedPendingPayload));
      setText("completed-pending-proof-summary", completedPendingProofSummaryLines(payload, rowList, state.lastCompletedPendingPayload).join("\n"));
      renderCompletedPendingProofDetail(selectedProofRow);
      const tbody = byId("completed-pending-proof-rows");
      if (!tbody) return;
      if (!proofRows.length) {
        clearRows(tbody, 5, rowList.length ? "No completed-to-pending proof overlaps in the loaded payloads." : "No completed rows loaded.");
        updateTableStatusLegend("completed-pending-proof-legend", tbody, "Completed-to-pending proof rows");
        renderCompletedPendingProofDetail(null);
        return;
      }
      tbody.replaceChildren();
      proofRows.slice(0, 250).forEach((item, index) => {
        const row = document.createElement("tr");
        const key = completedPendingProofRowKey(item, index);
        row.dataset.rowKey = key;
        row.dataset.status = item.status || "warning";
        appendCells(row, [
          completedPendingProofSignalLabel(item.signal),
          completedProofRowLabel(item.completed),
          item.pending ? completedProofPendingLabel(item.pending) : completedProofDrainItemLabel(item.drain_item),
          completedPendingProofEvidenceText(item),
          completedPendingProofNextAction(item),
        ]);
        makeRowSelectable(row, () => selectCompletedPendingProofRow(item, index), {
          selected: Boolean(key && key === state.selectedCompletedPendingProofKey),
          label: `Review completed pending proof row ${completedProofRowLabel(item.completed)}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("completed-pending-proof-legend", tbody, "Completed-to-pending proof rows");
    }

    function publishReconciliationStatusLabel(status) {
      const labels = {
        completed_unavailable: "Completed unavailable",
        pending_unavailable: "Pending unavailable",
        no_completed_rows: "No completed rows",
        review_blockers: "Review blockers",
        review_overlaps: "Review overlaps",
        review_leaf_hints: "Review leaf hints",
        review_final_placement: "Review final placement",
        proof_aligned: "Proof aligned",
        no_overlap: "No overlap",
        loading: "Loading",
        error: "Error",
        not_loaded: "Not loaded",
      };
      return labels[String(status || "not_loaded")] || String(status || "Unknown");
    }

    function publishReconciliationTableStatus(item) {
      const status = String(item?.status || "").toLowerCase();
      if (status === "blocked") return "blocked";
      if (status === "warning") return "warning";
      if (status === "match") return "match";
      return "warning";
    }

    function publishReconciliationRows(payload) {
      return Array.isArray(payload?.rows) ? payload.rows : [];
    }

    function publishReconciliationRowKey(item, index = 0) {
      if (!item || typeof item !== "object") return `publish-reconciliation-${index}`;
      return [
        item.signal || "signal",
        item.completed_row_key || item.completed_output || "",
        item.pending_row_key || item.pending_destination || "",
        item.drain_index === undefined || item.drain_index === null ? "" : String(item.drain_index),
        item.match_path || "",
        index,
      ].join("|");
    }

    function publishReconciliationSelectedRow(rows) {
      const list = Array.isArray(rows) ? rows : [];
      return list.find((row, index) => publishReconciliationRowKey(row, index) === state.selectedPublishReconciliationKey)
        || list.find((row) => row.status === "blocked")
        || list.find((row) => row.status === "warning")
        || list[0]
        || null;
    }

    function publishReconciliationDetailLines(item) {
      if (!item) {
        return [
          "Backend publish reconciliation row:",
          "Select a backend reconciliation row to inspect Completed, Pending Publish, and durable drain-summary evidence.",
          "Mutation guardrail: this detail is read-only and cannot mark done, repair, rerun, drain, delete, publish, rewrite manifests, or touch media.",
        ];
      }
      const lines = [
        "Backend publish reconciliation row:",
        `Signal: ${item.signal_label || item.signal || "review"}`,
        `Status: ${item.status || "review"}`,
        `Evidence: ${item.evidence || "not reported"}`,
        `Safe next step: ${item.safe_next_action || "Review owning pages and diagnostics before acting."}`,
        "",
        "Completed row:",
        `Title: ${item.completed_title || "(completed row)"}`,
        `Row key: ${item.completed_row_key || "(not reported)"}`,
        `Output: ${item.completed_output || "unknown"}`,
        `Source: ${item.completed_source || "unknown"}`,
      ];
      if (item.pending_row_key || item.pending_destination || item.pending_local) {
        lines.push("");
        lines.push("Pending Publish row:");
        lines.push(`Title: ${item.pending_title || "(pending row)"}`);
        lines.push(`Row key: ${item.pending_row_key || "(not reported)"}`);
        lines.push(`Destination: ${item.pending_destination || "unknown"}`);
        lines.push(`Source: ${item.pending_source || "unknown"}`);
        lines.push(`Local payload: ${item.pending_local || "unknown"}`);
      }
      if (item.drain_index !== undefined && item.drain_index !== null || item.drain_status) {
        lines.push("");
        lines.push("Durable drain summary:");
        lines.push(`Item index: ${item.drain_index === undefined || item.drain_index === null ? "unknown" : item.drain_index}`);
        lines.push(`Status: ${item.drain_status || "unknown"}`);
      }
      lines.push("");
      lines.push("Proof order: Completed Manifest row -> exact output/source path -> current Pending Publish row/state -> latest durable pending drain summary -> Run Logs / Last Stderr.");
      lines.push("Boundary: same-leaf rows are duplicate-title hints only; exact normalized paths are stronger evidence.");
      lines.push("Mutation guardrail: this backend row cannot mark done, repair, rerun, drain, delete, publish, rewrite manifests, or touch media.");
      return lines;
    }

    function renderPublishReconciliation(payload) {
      const data = payload && typeof payload === "object" ? payload : {};
      const rows = publishReconciliationRows(data);
      const selected = publishReconciliationSelectedRow(rows);
      if (!state.selectedPublishReconciliationKey && selected) {
        const selectedIndex = rows.indexOf(selected);
        state.selectedPublishReconciliationKey = publishReconciliationRowKey(selected, selectedIndex < 0 ? 0 : selectedIndex);
      }
      setText("publish-reconciliation-status", publishReconciliationStatusLabel(data.status));
      setText("publish-reconciliation-summary", [
        ...(Array.isArray(data.summary_lines) ? data.summary_lines : []),
        data.schema_version ? `Schema: ${data.schema_version}` : "",
        data.completed_source ? `Completed source: ${data.completed_source}` : "",
        data.pending_root ? `Pending root: ${data.pending_root}` : "",
        data.drain_summary_path ? `Drain summary: ${data.drain_summary_path}` : "",
      ].filter(Boolean).join("\n") || "No backend publish reconciliation loaded.");
      setText("publish-reconciliation-detail", publishReconciliationDetailLines(selected).join("\n"));
      const tbody = byId("publish-reconciliation-rows");
      if (!tbody) return;
      if (!rows.length) {
        clearRows(tbody, 5, "No backend reconciliation rows were returned.");
        updateTableStatusLegend("publish-reconciliation-legend", tbody, "Backend publish reconciliation rows");
        return;
      }
      tbody.replaceChildren();
      rows.slice(0, 250).forEach((item, index) => {
        const key = publishReconciliationRowKey(item, index);
        const row = document.createElement("tr");
        row.dataset.rowKey = key;
        row.dataset.status = publishReconciliationTableStatus(item);
        appendCells(row, [
          item.signal_label || item.signal || "Review",
          item.status || "review",
          item.completed_title || completedProofLeaf(item.completed_output) || "(completed row)",
          item.evidence || "",
          item.safe_next_action || "",
        ]);
        makeRowSelectable(row, () => selectPublishReconciliationRow(item, index), {
          selected: Boolean(key && key === state.selectedPublishReconciliationKey),
          label: `Review backend publish reconciliation ${item.signal_label || item.signal || ""}`,
        });
        tbody.appendChild(row);
      });
      updateTableStatusLegend("publish-reconciliation-legend", tbody, "Backend publish reconciliation rows");
    }

    function selectPublishReconciliationRow(item, index = 0) {
      state.selectedPublishReconciliationKey = publishReconciliationRowKey(item, index);
      renderPublishReconciliation({
        ...(state.lastPublishReconciliationPayload || {}),
        rows: publishReconciliationRows(state.lastPublishReconciliationPayload || {}),
      });
    }

    function setPublishReconciliationBusy(isBusy) {
      state.publishReconciliationInFlight = Boolean(isBusy);
      const button = byId("publish-reconciliation-refresh-button");
      if (button) button.disabled = state.publishReconciliationInFlight;
    }

    async function requestPublishReconciliation() {
      if (state.publishReconciliationInFlight) {
        setText("publish-reconciliation-status", "Already running");
        return;
      }
      setPublishReconciliationBusy(true);
      setText("publish-reconciliation-status", "Loading");
      setText("publish-reconciliation-summary", "Requesting backend-owned Completed/Pending/drain-summary reconciliation. This does not mutate files.");
      try {
        const payload = await apiGet("/api/publish-reconciliation?limit=250", { timeoutMs: 30000 });
        state.lastPublishReconciliationPayload = payload;
        state.selectedPublishReconciliationKey = "";
        renderPublishReconciliation(payload);
        renderCompletedPendingProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingPayload);
        renderCompletedSizeEvidence(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedOutputAcceptance(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows);
        renderCompletedRealMediaProof(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedFinalTrust(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        renderCompletedPilotEvidencePacket(state.lastCompletedPayload, state.lastCompletedRows, state.lastCompletedPendingProofRows, state.lastCompletedPendingPayload);
        window.mediaPipelineCompletedView?.renderCompletedReconciliationHint?.(state.lastCompletedPayload, state.lastCompletedRows);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        state.lastPublishReconciliationPayload = { status: "error", rows: [], summary_lines: [`Backend publish reconciliation failed: ${message}`] };
        setText("publish-reconciliation-status", "Error");
        setText("publish-reconciliation-summary", [
          `Backend publish reconciliation failed: ${message}`,
          "Safe next step: use Completed Manifest, Pending Publish, Run Logs, and Last Stderr diagnostics before acting.",
          "Mutation guardrail: failed reconciliation did not repair, rerun, drain, publish, rewrite manifests, or touch media.",
        ].join("\n"));
        clearRows(byId("publish-reconciliation-rows"), 5, "Backend reconciliation failed.");
        setText("publish-reconciliation-detail", "No backend reconciliation row selected.");
        window.mediaPipelineCompletedView?.renderCompletedReconciliationHint?.(state.lastCompletedPayload, state.lastCompletedRows);
      } finally {
        setPublishReconciliationBusy(false);
      }
    }


    return {
      completedAcceptancePostureStatus,
      completedAcceptanceCommandEntries,
      completedAcceptanceIssueLevel,
      completedAcceptanceProofRowsForItem,
      completedAcceptanceSelectedOrFirst,
      completedCurrentFilterScope,
      completedFilterScopePosture,
      completedFilterScopeEvidence,
      completedFilterScopeAction,
      completedFilterScopeDetailLines,
      completedAcceptanceRows,
      completedAcceptanceStatus,
      completedAcceptanceSummaryLines,
      completedAcceptanceDetailLines,
      selectedCompletedAcceptanceRow,
      selectCompletedAcceptanceRow,
      renderCompletedOutputAcceptance,
      completedRouteAgreementRouteToken,
      completedRouteAgreementReason,
      completedRouteAgreementQueueSourcePath,
      completedRouteAgreementQueueRowLabel,
      completedRouteAgreementRouteEvidenceCount,
      completedRouteAgreementQueueIndexes,
      completedRouteAgreementPostureStatus,
      completedRouteAgreementRows,
      completedRouteAgreementStatus,
      completedRouteAgreementSummaryLines,
      completedRouteAgreementDetailLines,
      selectedCompletedRouteAgreementRow,
      selectCompletedRouteAgreementRow,
      renderCompletedRouteAgreement,
      completedProofRows,
      completedProofDrainSummaryPayload,
      completedProofDrainSummaryItems,
      completedProofNormalizePath,
      completedProofPathLooksAbsolute,
      completedProofLeaf,
      completedProofFirstValue,
      completedProofCompletedOutputPath,
      completedProofCompletedSourcePath,
      completedProofRowMissingOutput,
      completedProofPendingDestinationPath,
      completedProofPendingSourcePath,
      completedProofPendingLocalPath,
      completedProofRowKey,
      completedProofRowLabel,
      completedProofPendingLabel,
      completedProofDrainItemLabel,
      completedPendingProofSignalLabel,
      completedPendingProofIsExactPathSignal,
      completedPendingProofIsFinalPlacementReviewSignal,
      completedPendingProofDataStatus,
      completedPendingProofEvidenceText,
      completedPendingProofNextAction,
      completedPendingProofRowKey,
      completedPendingProofSelectedRow,
      completedPendingProofDetailLines,
      renderCompletedPendingProofDetail,
      selectCompletedPendingProofRow,
      completedPendingProofRows,
      completedPendingProofStatus,
      completedPendingProofSummaryLines,
      renderCompletedPendingProof,
      publishReconciliationStatusLabel,
      publishReconciliationTableStatus,
      publishReconciliationRows,
      publishReconciliationRowKey,
      publishReconciliationSelectedRow,
      publishReconciliationDetailLines,
      renderPublishReconciliation,
      selectPublishReconciliationRow,
      setPublishReconciliationBusy,
      requestPublishReconciliation,
    };
  }

  window.__completedViewEvidenceModule = {
    createCompletedEvidenceModule,
  };
})();
