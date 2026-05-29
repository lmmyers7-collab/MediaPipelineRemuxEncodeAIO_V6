(function () {
  const domHelpers = window.mediaPipelineDom || {};
  const jsonDetailText = domHelpers.jsonDetailText || function (options = {}) {
    const label = options.label || "JSON detail";
    try {
      return `${label}:\n${JSON.stringify(options.value, null, 2)}`;
    } catch (error) {
      return `${label}:\nJSON render error: ${error instanceof Error ? error.message : String(error)}`;
    }
  };
  let lastContractRoutes = [];
  let lastContractPayload = {};
  let selectedContractRouteKey = "";
  let selectedContractSafetyKey = "";

  function contractRoutes(contract) {
    return Array.isArray(contract?.routes) ? contract.routes : [];
  }

  function contractRepairContracts(contract) {
    return Array.isArray(contract?.repair_reconcile_contracts) ? contract.repair_reconcile_contracts : [];
  }

  function contractNetworkLifecycleContracts(contract) {
    return Array.isArray(contract?.network_lifecycle_contracts) ? contract.network_lifecycle_contracts : [];
  }

  function contractRouteKey(route) {
    return [
      route?.method || "",
      route?.path || "",
      route?.effect || "",
      route?.response_schema || "",
    ].join("\u001f").toLowerCase();
  }

  function contractRouteSearchText(route) {
    return [
      route?.method || "",
      route?.path || "",
      route?.effect || "",
      route?.response_schema || "",
      route?.purpose || "",
      (route?.request_keys || []).join(" "),
      (route?.query_keys || []).join(" "),
      (route?.allowed_targets || []).join(" "),
      (route?.allowed_row_scopes || []).join(" "),
      route?.auth_required ? "token protected" : "public",
    ].join(" ").toLowerCase();
  }

  function contractMethodFilter() {
    return String(byId("api-contract-method")?.value || "").trim().toUpperCase();
  }

  function contractScopeFilter() {
    return String(byId("api-contract-scope")?.value || "").trim().toLowerCase();
  }

  function contractTextFilter() {
    return String(byId("api-contract-filter")?.value || "").trim().toLowerCase();
  }

  function routeMatchesContractScope(route, scope) {
    const effect = String(route?.effect || "none").toLowerCase();
    if (!scope) return true;
    if (scope === "read-only") return effect === "none";
    if (scope === "guarded") return effect !== "none";
    if (scope === "token") return Boolean(route?.auth_required);
    if (scope === "public") return !route?.auth_required;
    return true;
  }

  function filteredContractRoutes(routes = lastContractRoutes) {
    const method = contractMethodFilter();
    const scope = contractScopeFilter();
    const query = contractTextFilter();
    return (Array.isArray(routes) ? routes : []).filter((route) => {
      if (method && String(route?.method || "").toUpperCase() !== method) return false;
      if (!routeMatchesContractScope(route, scope)) return false;
      return !query || contractRouteSearchText(route).includes(query);
    });
  }

  function contractSummaryLines(contract, routes) {
    const routeRows = Array.isArray(routes) ? routes : [];
    const tokenRoutes = routeRows.filter((route) => route.auth_required).length;
    const publicRoutes = routeRows.length - tokenRoutes;
    const guardedRoutes = routeRows.filter((route) => String(route.effect || "none") !== "none").length;
    const readRoutes = routeRows.filter((route) => String(route.effect || "none") === "none").length;
    const shellOpenRoutes = routeRows.filter((route) => String(route.effect || "").includes("shell-open")).length;
    const processRoutes = routeRows.filter((route) => String(route.effect || "").includes("process")).length;
    const controlRoutes = routeRows.filter((route) => String(route.effect || "").includes("control")).length;
    const networkLifecycleContracts = contractNetworkLifecycleContracts(contract || {});
    const networkLifecycleSummary = contract?.network_lifecycle_summary || {};
    const repairContracts = contractRepairContracts(contract || {});
    const repairSummary = contract?.repair_reconcile_summary || {};
    return [
      `Schema: ${contract?.schema_version || "not loaded"}`,
      `App version: ${contract?.app_version || ""}`,
      `Host: ${contract?.host || ""}`,
      `Routes: ${routeRows.length}; read-only: ${readRoutes}; guarded actions: ${guardedRoutes}`,
      `Auth: token ${tokenRoutes}; public ${publicRoutes}`,
      `Guarded effect groups: shell-open ${shellOpenRoutes}; process ${processRoutes}; control ${controlRoutes}`,
      `Network lifecycle contracts: ${networkLifecycleContracts.length}; mutation enabled: ${networkLifecycleSummary.mutation_enabled ? "yes" : "no"}; frontend allowed: ${networkLifecycleSummary.frontend_allowed ? "yes" : "no"}`,
      `Repair/reconcile contracts: ${repairContracts.length}; mutation enabled: ${repairSummary.mutation_enabled ? "yes" : "no"}; frontend allowed: ${repairSummary.frontend_allowed ? "yes" : "no"}`,
      "Mutation guardrail: WebView controls must use backend-owned routes from this contract; no frontend filesystem mutation or process control belongs here.",
    ];
  }

  function contractEffect(route) {
    return String(route?.effect || "none").toLowerCase();
  }

  function contractPathList(routes, limit = 5) {
    const routeList = Array.isArray(routes) ? routes : [];
    const paths = routeList.map((route) => `${route.method || ""} ${route.path || ""}`.trim()).filter(Boolean);
    if (paths.length <= limit) return paths.join(", ") || "none";
    return `${paths.slice(0, limit).join(", ")} (+${paths.length - limit} more)`;
  }

  function contractSafetyRowStatus(row) {
    const posture = String(row?.posture || "").toLowerCase();
    if (posture.includes("blocked")) return "blocked";
    if (posture.includes("review")) return "warning";
    if (posture.includes("guarded")) return "warning";
    return "match";
  }

  function contractSafetyRowKey(row) {
    return String(row?.key || row?.surface || "").trim().toLowerCase();
  }

  function contractSafetyReviewRows(contractOrRoutes) {
    const contractPayload = Array.isArray(contractOrRoutes) ? { routes: contractOrRoutes } : (contractOrRoutes || {});
    const routeList = contractRoutes(contractPayload);
    const networkLifecycleContracts = contractNetworkLifecycleContracts(contractPayload);
    const networkLifecycleMutationEnabled = networkLifecycleContracts.filter((contract) => contract?.mutation_enabled || contract?.frontend_allowed);
    const missingNetworkLifecycleProof = networkLifecycleContracts.filter((contract) => {
      return !Array.isArray(contract?.required_preconditions)
        || !Array.isArray(contract?.required_evidence)
        || !Array.isArray(contract?.rollback_requirements)
        || !Array.isArray(contract?.must_not)
        || !contract?.dry_run_contract
        || !contract?.rollback_contract
        || !contract?.source_file_policy
        || !Array.isArray(contract?.route_exposure_gates)
        || !contract?.candidate_command
        || !contract?.current_status;
    });
    const repairContracts = contractRepairContracts(contractPayload);
    const repairMutationEnabled = repairContracts.filter((contract) => contract?.mutation_enabled || contract?.frontend_allowed);
    const missingRepairProof = repairContracts.filter((contract) => {
      return !Array.isArray(contract?.required_preconditions)
        || !Array.isArray(contract?.required_evidence)
        || !Array.isArray(contract?.rollback_requirements)
        || !Array.isArray(contract?.must_not)
        || !contract?.dry_run_contract
        || !contract?.rollback_contract
        || !contract?.source_file_policy
        || !Array.isArray(contract?.route_exposure_gates)
        || !contract?.candidate_command
        || !contract?.current_status;
    });
    const publicRoutes = routeList.filter((route) => !route.auth_required);
    const publicNonHealth = publicRoutes.filter((route) => route.path !== "/api/health");
    const guardedRoutes = routeList.filter((route) => contractEffect(route) !== "none");
    const filesystemRoutes = routeList.filter((route) => contractEffect(route).includes("filesystem-mutation"));
    const configWriteRoutes = routeList.filter((route) => contractEffect(route).includes("config-write") || contractEffect(route).includes("app-state-write"));
    const processRoutes = routeList.filter((route) => contractEffect(route).includes("process-launch") || contractEffect(route).includes("control-flag-write") || contractEffect(route).includes("backend-lifecycle"));
    const shellOpenRoutes = routeList.filter((route) => contractEffect(route).includes("shell-open"));
    const dryRunRoutes = routeList.filter((route) => contractEffect(route).includes("dry-run"));
    const previewPostRoutes = routeList.filter((route) => route.method === "POST" && contractEffect(route) === "none");
    const readOnlyRoutes = routeList.filter((route) => route.method === "GET" && contractEffect(route) === "none");
    const incompleteRoutes = routeList.filter((route) => !route.path || !route.method || !route.response_schema || !route.purpose || typeof route.effect === "undefined");
    const shellOpenWithoutTargets = shellOpenRoutes.filter((route) => !Array.isArray(route.allowed_targets) || route.allowed_targets.length <= 0);
    return [
      {
        key: "auth-boundary",
        surface: "Auth boundary",
        posture: publicNonHealth.length ? "Blocked" : "Ready",
        evidence: `public=${publicRoutes.length}; public non-health=${publicNonHealth.length}; token=${routeList.length - publicRoutes.length}`,
        safeNextStep: publicNonHealth.length
          ? `Review contract: ${contractPathList(publicNonHealth)} must not be public.`
          : "API contract: only /api/health is public; startup HTML/assets are a separate shell bootstrap surface.",
        detail: [
          "Auth boundary:",
          `Public routes: ${contractPathList(publicRoutes)}`,
          `Public non-health routes: ${contractPathList(publicNonHealth)}`,
          "Web shell note: / and /assets/* are served for startup, while this route contract covers /api/* authorization.",
          "Guardrail: WebView shells must keep tokens on all read, command, open, process, settings, rename, and publish routes.",
        ],
      },
      {
        key: "mutation-boundary",
        surface: "Mutation boundary",
        posture: filesystemRoutes.length || configWriteRoutes.length || processRoutes.length ? "Guarded review" : "Ready",
        evidence: `filesystem=${filesystemRoutes.length}; config/app-state=${configWriteRoutes.length}; process/control=${processRoutes.length}`,
        safeNextStep: "Invoke only from owner pages through backend command routes; never reimplement mutation in WebView JavaScript.",
        detail: [
          "Mutation boundary:",
          `Filesystem mutation routes: ${contractPathList(filesystemRoutes)}`,
          `Config/app-state write routes: ${contractPathList(configWriteRoutes)}`,
          `Process/control routes: ${contractPathList(processRoutes)}`,
          "Guardrail: route contracts describe backend-owned authority. Frontend code stages intent and displays results only.",
        ],
      },
      {
        key: "shell-open-boundary",
        surface: "Shell-open boundary",
        posture: shellOpenWithoutTargets.length ? "Blocked" : shellOpenRoutes.length ? "Guarded review" : "Ready",
        evidence: `shell-open routes=${shellOpenRoutes.length}; missing allowlists=${shellOpenWithoutTargets.length}`,
        safeNextStep: shellOpenWithoutTargets.length
          ? `Add allowed_targets before exposing shell-open UI: ${contractPathList(shellOpenWithoutTargets)}.`
          : "Open controls must send backend row keys or target keys only, never filesystem paths.",
        detail: [
          "Shell-open boundary:",
          `Shell-open routes: ${contractPathList(shellOpenRoutes)}`,
          `Missing allowed_targets: ${contractPathList(shellOpenWithoutTargets)}`,
          "Guardrail: shell-open routes are backend allowlists and selected-row targets, not frontend path resolvers.",
        ],
      },
      {
        key: "preview-dry-run-boundary",
        surface: "Preview and dry-run boundary",
        posture: "Ready",
        evidence: `preview POSTs=${previewPostRoutes.length}; dry-run routes=${dryRunRoutes.length}`,
        safeNextStep: "Keep preview/dry-run result panels explicit about what was not written or launched.",
        detail: [
          "Preview and dry-run boundary:",
          `Preview POST routes: ${contractPathList(previewPostRoutes)}`,
          `Dry-run routes: ${contractPathList(dryRunRoutes)}`,
          "Guardrail: effect=none and process-dry-run commands may inspect or plan, but they must not mutate media, queue, publish, settings, or manifests unless the route says so.",
        ],
      },
      {
        key: "read-only-contract",
        surface: "Read-only contract",
        posture: "Ready",
        evidence: `GET read-only routes=${readOnlyRoutes.length}; total routes=${routeList.length}`,
        safeNextStep: "Use read-only routes for WebView dashboards; do not derive write decisions from hidden filtered rows.",
        detail: [
          "Read-only contract:",
          `GET read-only routes: ${contractPathList(readOnlyRoutes, 8)}`,
          "Guardrail: read-only evidence can guide operators, but backend command routes still own launch, drain, save, rename, open, and shutdown actions.",
        ],
      },
      {
        key: "contract-completeness",
        surface: "Contract completeness",
        posture: incompleteRoutes.length ? "Blocked" : "Ready",
        evidence: `routes=${routeList.length}; incomplete=${incompleteRoutes.length}`,
        safeNextStep: incompleteRoutes.length
          ? `Complete method/path/effect/schema/purpose fields: ${contractPathList(incompleteRoutes)}.`
          : "Contract rows include enough schema/effect/purpose data for WebView review and smoke tests.",
        detail: [
          "Contract completeness:",
          `Incomplete routes: ${contractPathList(incompleteRoutes)}`,
          "Required route fields: method, path, effect, response_schema, purpose.",
          "Guardrail: thin or missing contracts let frontend behavior drift from backend authority.",
        ],
      },
      {
        key: "frontend-boundary",
        surface: "Frontend ownership boundary",
        posture: guardedRoutes.length ? "Guarded review" : "Ready",
        evidence: `guarded routes=${guardedRoutes.length}; declared effects=${[...new Set(routeList.map((route) => contractEffect(route)))].sort().join(", ") || "none"}`,
        safeNextStep: "Before adding a WebView control, verify the owner page, allowed request keys, command result rendering, and mutation guardrail.",
        detail: [
          "Frontend ownership boundary:",
          `Guarded routes: ${contractPathList(guardedRoutes, 8)}`,
          "Guardrail: this review is read-only. It cannot call routes, open files, write settings, launch work, drain publish, rename, or mutate media.",
        ],
      },
      {
        key: "network-lifecycle-boundary",
        surface: "Network lifecycle boundary",
        posture: networkLifecycleMutationEnabled.length || missingNetworkLifecycleProof.length ? "Blocked" : networkLifecycleContracts.length ? "Guarded review" : "Ready",
        evidence: `design contracts=${networkLifecycleContracts.length}; mutation enabled=${networkLifecycleMutationEnabled.length}; missing proof fields=${missingNetworkLifecycleProof.length}`,
        safeNextStep: networkLifecycleMutationEnabled.length
          ? "Remove WebView Network lifecycle exposure until backend dry-run, process cleanup, state reconciliation, and journal contracts exist."
          : networkLifecycleContracts.length
            ? "Implement backend dry-run lifecycle checks and command journaling before adding Network lifecycle routes."
            : "No Network lifecycle design contracts are published by the backend yet.",
        detail: [
          "Network lifecycle boundary:",
          `Contracts: ${networkLifecycleContracts.map((contract) => contract.candidate_command || contract.key || "unknown").join(", ") || "none"}`,
          `Mutation-enabled contracts: ${networkLifecycleMutationEnabled.map((contract) => contract.candidate_command || contract.key || "unknown").join(", ") || "none"}`,
          `Missing proof contracts: ${missingNetworkLifecycleProof.map((contract) => contract.candidate_command || contract.key || "unknown").join(", ") || "none"}`,
          "Required contract fields: candidate_command, current_status, required_preconditions, required_evidence, dry_run_contract, rollback_contract, source_file_policy, route_exposure_gates, rollback_requirements, must_not.",
          "Guardrail: WebView may display these contracts, but Network lifecycle commands are not allowed until the backend owns dry-run proof, process cleanup, state reconciliation, and command-journal evidence.",
          ...networkLifecycleContracts.flatMap((contract) => [
            "",
            `${contract.surface || contract.key || "Network lifecycle contract"}:`,
            `Candidate command: ${contract.candidate_command || "not declared"}`,
            `Status: ${contract.current_status || "not declared"}`,
            `Mutation class: ${contract.mutation_class || "not declared"}`,
            `Safe next step: ${contract.safe_next_step || "not declared"}`,
            `Dry-run contract fields: ${(contract.dry_run_contract?.required_result_fields || []).join(", ") || "not declared"}`,
            `Dry-run must report: ${(contract.dry_run_contract?.must_report || []).join("; ") || "not declared"}`,
            `Rollback journal fields: ${(contract.rollback_contract?.journal_fields || []).join(", ") || "not declared"}`,
            `Rollback triggers: ${(contract.rollback_contract?.rollback_on || []).join("; ") || "not declared"}`,
            `Source policy: source media mutation=${contract.source_file_policy?.source_media_mutation || "not declared"}; source delete=${contract.source_file_policy?.source_delete || "not declared"}; path authority=${contract.source_file_policy?.source_path_authority || "not declared"}`,
            `Route exposure gates: ${(contract.route_exposure_gates || []).join("; ") || "not declared"}`,
          ]),
        ],
      },
      {
        key: "repair-reconcile-boundary",
        surface: "Repair/reconcile boundary",
        posture: repairMutationEnabled.length || missingRepairProof.length ? "Blocked" : repairContracts.length ? "Guarded review" : "Ready",
        evidence: `design contracts=${repairContracts.length}; mutation enabled=${repairMutationEnabled.length}; missing proof fields=${missingRepairProof.length}`,
        safeNextStep: repairMutationEnabled.length
          ? "Remove WebView repair/reconcile mutation exposure until backend dry-run, atomic write, and journal contracts exist."
          : repairContracts.length
            ? "Implement backend dry-run diffs and atomic journals before adding any repair/reconcile command routes."
            : "No repair/reconcile design contracts are published by the backend yet.",
        detail: [
          "Repair/reconcile boundary:",
          `Contracts: ${repairContracts.map((contract) => contract.candidate_command || contract.key || "unknown").join(", ") || "none"}`,
          `Mutation-enabled contracts: ${repairMutationEnabled.map((contract) => contract.candidate_command || contract.key || "unknown").join(", ") || "none"}`,
          `Missing proof contracts: ${missingRepairProof.map((contract) => contract.candidate_command || contract.key || "unknown").join(", ") || "none"}`,
          "Required contract fields: candidate_command, current_status, required_preconditions, required_evidence, dry_run_contract, rollback_contract, source_file_policy, route_exposure_gates, rollback_requirements, must_not.",
          "Guardrail: WebView may display these contracts, but repair/reconcile commands are not allowed until the backend owns dry-run proof, atomic write/rollback, and command-journal evidence.",
          ...repairContracts.flatMap((contract) => [
            "",
            `${contract.surface || contract.key || "Repair contract"}:`,
            `Candidate command: ${contract.candidate_command || "not declared"}`,
            `Status: ${contract.current_status || "not declared"}`,
            `Mutation class: ${contract.mutation_class || "not declared"}`,
            `Safe next step: ${contract.safe_next_step || "not declared"}`,
            `Dry-run contract fields: ${(contract.dry_run_contract?.required_result_fields || []).join(", ") || "not declared"}`,
            `Dry-run must report: ${(contract.dry_run_contract?.must_report || []).join("; ") || "not declared"}`,
            `Rollback journal fields: ${(contract.rollback_contract?.journal_fields || []).join(", ") || "not declared"}`,
            `Rollback triggers: ${(contract.rollback_contract?.rollback_on || []).join("; ") || "not declared"}`,
            `Source policy: source media mutation=${contract.source_file_policy?.source_media_mutation || "not declared"}; source delete=${contract.source_file_policy?.source_delete || "not declared"}; path authority=${contract.source_file_policy?.source_path_authority || "not declared"}`,
            `Route exposure gates: ${(contract.route_exposure_gates || []).join("; ") || "not declared"}`,
          ]),
        ],
      },
    ];
  }

  function contractSafetyStatus(rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    if (!rowList.length) return "Not loaded";
    if (rowList.some((row) => contractSafetyRowStatus(row) === "blocked")) return "Blocked";
    if (rowList.some((row) => contractSafetyRowStatus(row) === "warning")) return "Review";
    return "Ready";
  }

  function contractSafetySummaryLines(contract, rows) {
    const rowList = Array.isArray(rows) ? rows : [];
    const status = contractSafetyStatus(rowList);
    const blocked = rowList.filter((row) => contractSafetyRowStatus(row) === "blocked").length;
    const review = rowList.filter((row) => contractSafetyRowStatus(row) === "warning").length;
    const ready = rowList.filter((row) => contractSafetyRowStatus(row) === "match").length;
    return [
      `Contract safety review: ${status}`,
      `Routes: ${contractRoutes(contract || {}).length}; ready rows=${ready}; review rows=${review}; blocked rows=${blocked}`,
      "Decision rule: blocked rows must be fixed before trusting new WebView controls; review rows require owner-page command-result feedback and mutation guardrails.",
      "Mutation guardrail: this panel is read-only over /api/contract and cannot call command routes, open files, save settings, launch work, drain publish, rename, or mutate media.",
    ];
  }

  function selectedContractSafetyRow(rows = null) {
    const rowList = Array.isArray(rows) ? rows : contractSafetyReviewRows(lastContractPayload || { routes: lastContractRoutes });
    if (!selectedContractSafetyKey) return null;
    return rowList.find((row) => contractSafetyRowKey(row) === selectedContractSafetyKey) || null;
  }

  function renderContractSafetyDetail(row) {
    if (!row) {
      setText("api-contract-safety-detail", "Select a contract safety row to inspect route risk and ownership boundaries.");
      return;
    }
    const lines = [
      `Surface: ${row.surface || ""}`,
      `Posture: ${row.posture || ""}`,
      `Evidence: ${row.evidence || ""}`,
      `Safe next step: ${row.safeNextStep || ""}`,
      "",
      ...(Array.isArray(row.detail) ? row.detail : []),
    ];
    setText("api-contract-safety-detail", lines.join("\n"));
  }

  function selectContractSafetyRow(row) {
    selectedContractSafetyKey = contractSafetyRowKey(row);
    const rows = contractSafetyReviewRows(lastContractPayload || { routes: lastContractRoutes });
    renderContractSafetyRows(rows);
    renderContractSafetyDetail(row || selectedContractSafetyRow(rows));
  }

  function renderContractSafetyRows(rows) {
    const rowList = Array.isArray(rows) ? rows : contractSafetyReviewRows(lastContractPayload || { routes: lastContractRoutes });
    if (selectedContractSafetyKey && !rowList.some((row) => contractSafetyRowKey(row) === selectedContractSafetyKey)) {
      selectedContractSafetyKey = "";
    }
    const tbody = byId("api-contract-safety-rows");
    if (!tbody) return;
    if (!rowList.length) {
      clearRows(tbody, 4, "No contract safety rows loaded.");
      updateTableStatusLegend("api-contract-safety-legend", tbody, "API contract safety rows");
      renderContractSafetyDetail(null);
      return;
    }
    tbody.replaceChildren();
    rowList.forEach((row) => {
      const tr = document.createElement("tr");
      const key = contractSafetyRowKey(row);
      tr.dataset.rowKey = key;
      tr.dataset.status = contractSafetyRowStatus(row);
      appendCells(tr, [
        row.surface || "",
        row.posture || "",
        row.evidence || "",
        row.safeNextStep || "",
      ]);
      makeRowSelectable(tr, () => selectContractSafetyRow(row), {
        selected: Boolean(key && key === selectedContractSafetyKey),
        label: `API contract safety ${row.surface || ""}`,
      });
      tbody.appendChild(tr);
    });
    updateTableStatusLegend("api-contract-safety-legend", tbody, "API contract safety rows");
    renderContractSafetyDetail(selectedContractSafetyRow(rowList));
  }

  function renderContractSafetyReview(contract) {
    const rows = contractSafetyReviewRows(contract || {});
    const status = contractSafetyStatus(rows);
    setText("api-contract-safety-status", status);
    setText("api-contract-safety-summary", contractSafetySummaryLines(contract || {}, rows).join("\n"));
    renderContractSafetyRows(rows);
  }

  function contractRouteStatus(route) {
    const effect = String(route?.effect || "none").toLowerCase();
    if (effect.includes("process") || effect.includes("control") || effect.includes("write")) return "warning";
    if (effect.includes("shell-open")) return "match";
    return "";
  }

  function updateContractStatus(filteredCount, totalCount) {
    const guardedRoutes = lastContractRoutes.filter((route) => route.effect && route.effect !== "none").length;
    setText(
      "api-contract-status",
      `${filteredCount} / ${totalCount} route${totalCount === 1 ? "" : "s"}, ${guardedRoutes} guarded action${guardedRoutes === 1 ? "" : "s"}`
    );
  }

  function selectedContractRoute() {
    if (!selectedContractRouteKey) return null;
    return lastContractRoutes.find((route) => contractRouteKey(route) === selectedContractRouteKey) || null;
  }

  function selectContractRoute(route) {
    selectedContractRouteKey = contractRouteKey(route);
    renderContractRouteDetail(route || null);
    renderContractRows();
  }

  function renderContractRouteDetail(route) {
    if (!route) {
      setText("api-contract-detail", "No contract route selected. Select a row to inspect request/query keys, allowed targets, schema, and safety effect.");
      return;
    }
    const lines = [
      `Route: ${route.method || ""} ${route.path || ""}`,
      `Auth: ${route.auth_required ? "token required" : "public"}`,
      `Effect: ${route.effect || "none"}`,
      `Response schema: ${route.response_schema || ""}`,
      `Request keys: ${(route.request_keys || []).join(", ") || "none"}`,
      `Query keys: ${(route.query_keys || []).join(", ") || "none"}`,
      `Allowed targets: ${(route.allowed_targets || []).join(", ") || "none"}`,
      `Allowed row scopes: ${(route.allowed_row_scopes || []).join(", ") || "none"}`,
      `Purpose: ${route.purpose || ""}`,
    ];
    if (String(route.effect || "none") !== "none") {
      lines.push("Operator safety: this is a guarded backend-owned action; the WebView should call this route rather than duplicating mutation logic.");
    } else {
      lines.push("Operator safety: this is read-only from the WebView perspective.");
    }
    lines.push("", jsonDetailText({
      label: "Route contract JSON",
      value: route,
      intro: "Read-only route contract payload from /api/contract. Select this block to copy it for troubleshooting.",
      guardrail: "Mutation guardrail: this Contract page formats already-loaded route data only and cannot call command routes, open files, save settings, launch work, drain publish, rename, or mutate media.",
    }));
    setText("api-contract-detail", lines.join("\n"));
  }

  function renderContractRows(routes = null) {
    if (Array.isArray(routes)) {
      lastContractRoutes = routes;
    }
    if (selectedContractRouteKey && !lastContractRoutes.some((route) => contractRouteKey(route) === selectedContractRouteKey)) {
      selectedContractRouteKey = "";
    }
    const filteredRoutes = filteredContractRoutes(lastContractRoutes);
    updateContractStatus(filteredRoutes.length, lastContractRoutes.length);
    const selectedVisible = !selectedContractRouteKey || filteredRoutes.some((route) => contractRouteKey(route) === selectedContractRouteKey);
    const tbody = byId("api-contract-rows");
    if (!tbody) return;
    if (!filteredRoutes.length) {
      clearRows(tbody, 5, lastContractRoutes.length ? "No contract routes match the current filter." : "No contract routes loaded.");
      updateTableStatusLegend("api-contract-table-legend", tbody, "API contract rows");
      renderContractRouteDetail(selectedVisible ? selectedContractRoute() : null);
      return;
    }
    tbody.replaceChildren();
    filteredRoutes.forEach((route) => {
      const row = document.createElement("tr");
      const key = contractRouteKey(route);
      row.dataset.rowKey = key;
      row.dataset.status = contractRouteStatus(route);
      appendCells(row, [
        route.method || "",
        route.path || "",
        route.auth_required ? "token" : "public",
        route.effect || "none",
        route.response_schema || route.purpose || "",
      ]);
      makeRowSelectable(row, () => selectContractRoute(route), {
        selected: Boolean(key && key === selectedContractRouteKey),
        label: `API contract route ${route.method || ""} ${route.path || ""}`,
      });
      tbody.appendChild(row);
    });
    updateTableStatusLegend("api-contract-table-legend", tbody, "API contract rows");
    renderContractRouteDetail(selectedVisible ? selectedContractRoute() : null);
  }

  function renderContract(contract) {
    const routes = contractRoutes(contract || {});
    lastContractPayload = contract || {};
    lastContractRoutes = routes;
    const filteredCount = filteredContractRoutes(routes).length;
    updateContractStatus(filteredCount, routes.length);
    setText("api-contract", contractSummaryLines(contract || {}, routes).join("\n") || contract?.error || "No contract routes loaded.");
    renderContractSafetyReview(contract || {});
    renderContractRows(routes);
  }

  function initContractViewEvents() {
    const method = byId("api-contract-method");
    if (method) method.addEventListener("change", () => renderContractRows());
    const scope = byId("api-contract-scope");
    if (scope) scope.addEventListener("change", () => renderContractRows());
    const filter = byId("api-contract-filter");
    if (filter) filter.addEventListener("input", () => renderContractRows());
  }

  /**
   * Public namespace for the API Contract page module.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineContractView = {
    contractRoutes,
    contractRepairContracts,
    contractRouteKey,
    contractEffect,
    filteredContractRoutes,
    contractSummaryLines,
    contractSafetyReviewRows,
    contractSafetyStatus,
    contractSafetySummaryLines,
    renderContractSafetyReview,
    renderContractSafetyRows,
    renderContractSafetyDetail,
    selectContractSafetyRow,
    selectedContractSafetyRow,
    updateContractStatus,
    selectContractRoute,
    selectedContractRoute,
    renderContractRouteDetail,
    renderContractRows,
    renderContract,
    initContractViewEvents,
  };
  window.initContractViewEvents = initContractViewEvents;
})();
