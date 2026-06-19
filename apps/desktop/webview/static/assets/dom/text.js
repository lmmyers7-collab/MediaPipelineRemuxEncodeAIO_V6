// dom/text.js
// Split child of domHelpers.js. Owns safe text rendering, diagnostic callouts, prose helpers, and JSON detail text.

/* eslint-disable max-lines-per-function */
(function () {
  "use strict";

  function createDomTextModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;

    function diagnosticCalloutText(value) {
      return String(value === null || value === undefined ? "" : value);
    }

    function isDiagnosticCalloutText(value) {
      const text = diagnosticCalloutText(value);
      if (!text || text.split(/\r?\n/).filter((line) => line.trim()).length < 2) return false;
      return /(^|\n).*(mutation|lifecycle|auth-token)?\s*guardrail:/i.test(text)
        || /(^|\n).*button guard:/i.test(text)
        || /(^|\n).*selected-row diagnostic order:/i.test(text)
        || /(^|\n).*diagnostics? (handoff|order|allowlist|actions|links|bridge):/i.test(text)
        || /read-only.*cannot\s+(launch|drain|save|rename|repair|delete|publish|mutate|touch)/i.test(text)
        || /cannot\s+(launch|drain|save|rename|repair|delete|publish|mutate|touch).*files?/i.test(text);
    }

    function shouldRenderDiagnosticCallout(node, value) {
      if (!node || node.dataset?.diagnosticCalloutBody === "true") return false;
      const eligible = node.classList?.contains("prose-block") || node.classList?.contains("diagnostic-callout");
      return Boolean(eligible && isDiagnosticCalloutText(value));
    }

    function ensureDiagnosticCalloutRoot(node) {
      if (!node) return null;
      if (node.dataset && !node.dataset.originalClass) {
        node.dataset.originalClass = node.className || "";
      }
      if (node.tagName && String(node.tagName).toLowerCase() === "pre") {
        const replacement = document.createElement("div");
        Array.from(node.attributes || []).forEach((attr) => {
          replacement.setAttribute(attr.name, attr.value);
        });
        replacement.dataset.originalClass = node.dataset?.originalClass || node.className || "";
        node.replaceWith(replacement);
        return replacement;
      }
      return node;
    }

    function resetDiagnosticCalloutNode(node, value) {
      if (!node) return;
      const originalClass = node.dataset?.originalClass;
      if (originalClass !== undefined) {
        node.className = originalClass;
      }
      node.textContent = diagnosticCalloutText(value);
    }

    function renderDiagnosticCalloutNode(node, value) {
      const root = ensureDiagnosticCalloutRoot(node);
      if (!root) return;
      const text = diagnosticCalloutText(value);
      root.className = "diagnostic-callout";
      root.textContent = "";

      const details = document.createElement("details");
      details.className = "diagnostic-callout-details";
      const summary = document.createElement("summary");
      summary.textContent = "Why?";
      details.appendChild(summary);
      const detailsBody = document.createElement("pre");
      detailsBody.className = "prose-block diagnostic-callout-body";
      detailsBody.dataset.diagnosticCalloutBody = "true";
      detailsBody.textContent = text;
      details.appendChild(detailsBody);
      root.appendChild(details);

      const advancedBody = document.createElement("pre");
      advancedBody.className = "prose-block diagnostic-callout-body diagnostic-callout-advanced";
      advancedBody.dataset.diagnosticCalloutBody = "true";
      advancedBody.setAttribute("data-advanced", "");
      advancedBody.hidden = !document.body.classList.contains("advanced-mode");
      advancedBody.style.display = document.body.classList.contains("advanced-mode") ? "" : "none";
      advancedBody.textContent = text;
      root.appendChild(advancedBody);
    }

    function diagnosticCalloutBodyNode(node) {
      if (!node || typeof node.querySelector !== "function") return null;
      return node.querySelector('[data-diagnostic-callout-body="true"]');
    }

    function isDiagnosticCalloutRoot(node) {
      return Boolean(node?.classList?.contains("diagnostic-callout") || diagnosticCalloutBodyNode(node));
    }

    function renderedTextMatches(node, value) {
      if (!node) return false;
      const text = diagnosticCalloutText(value);
      const calloutBody = diagnosticCalloutBodyNode(node);
      if (calloutBody) return diagnosticCalloutText(calloutBody.textContent) === text;
      return !isDiagnosticCalloutRoot(node) && diagnosticCalloutText(node.textContent) === text;
    }

    function proseBoxCandidate(node) {
      return Boolean(node?.classList?.contains("prose-block")
        || node?.classList?.contains("status-block")
        || node?.classList?.contains("diagnostic-callout"));
    }

    function proseBoxText(node) {
      return diagnosticCalloutText(diagnosticCalloutBodyNode(node)?.textContent || node?.textContent || "");
    }

    function proseBoxIsEmpty(text) {
      const normalized = String(text || "").replace(/\s+/g, " ").trim().toLowerCase();
      if (!normalized) return true;
      return normalized.startsWith("no ")
        || normalized.includes("not loaded")
        || normalized.includes("not selected")
        || normalized.includes("nothing saved yet")
        || normalized.includes("select a row")
        || /\bselect (a|an) .+ (to|before)\b/.test(normalized)
        || normalized.includes("select a target")
        || normalized.includes("preview has not run");
    }

    function proseBoxIsRawArtifact(node, text) {
      const id = String(node?.id || "").toLowerCase();
      if (proseBoxIsEmpty(text)) return false;
      if (node?.closest?.(".settings-save-review-dialog")) return true;
      const idTokens = id.split(/[^a-z0-9]+/).filter(Boolean);
      const hasToken = (...tokens) => tokens.some((token) => idTokens.includes(token));
      if (id === "api-contract" || hasToken("markdown", "json", "tail", "command", "stdout", "stderr")) {
        return true;
      }
      return hasToken("result", "preview", "dry", "run", "apply", "save", "export", "open")
        && !proseBoxShouldSummarize(text);
    }

    function proseBoxShouldSummarize(text) {
      const lines = String(text || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      if (!lines.length || lines.length > 12) return false;
      const factLines = lines.filter((line) => /[:=;]/.test(line));
      return factLines.length >= Math.max(1, Math.ceil(lines.length * 0.5));
    }

    function proseBoxSummaryItems(text) {
      return String(text || "").split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)
        .slice(0, 5)
        .map((line) => {
          const match = line.match(/^([^:=;]{1,34})[:=]\s*(.+)$/);
          if (match) return { label: match[1].trim(), value: match[2].trim() };
          return { label: "Summary", value: line };
        });
    }

    function proseBoxExistingSummary(node) {
      const previous = node?.previousElementSibling;
      if (previous?.classList?.contains("prose-box-summary-strip")) return previous;
      return null;
    }

    function removeProseBoxSummary(node) {
      proseBoxExistingSummary(node)?.remove();
    }

    function renderProseBoxSummary(node, text) {
      if (!node?.parentNode) return;
      let summary = proseBoxExistingSummary(node);
      if (!summary) {
        summary = document.createElement("div");
        summary.className = "prose-box-summary-strip";
        summary.setAttribute("role", "list");
        node.parentNode.insertBefore(summary, node);
      }
      summary.replaceChildren();
      proseBoxSummaryItems(text).forEach((item) => {
        const chip = document.createElement("span");
        chip.className = "prose-box-summary-chip";
        chip.setAttribute("role", "listitem");
        const label = document.createElement("span");
        label.className = "prose-box-summary-label";
        label.textContent = item.label;
        const value = document.createElement("strong");
        value.className = "prose-box-summary-value";
        value.textContent = item.value;
        chip.append(label, value);
        summary.appendChild(chip);
      });
    }

    function classifyProseBox(node) {
      const text = proseBoxText(node);
      if (!proseBoxCandidate(node)) return { disposition: "ignored", defense: "" };
      if (node.classList?.contains("log-block")) {
        return {
          disposition: "defended",
          defense: "true log/output pane; kept because the scrollable text is the payload to inspect or copy",
        };
      }
      if (proseBoxIsEmpty(text)) {
        return {
          disposition: "hidden-empty",
          defense: "empty/default placeholder; hiding removes visual clutter without losing current operator status",
        };
      }
      if (proseBoxShouldSummarize(text) && !proseBoxIsRawArtifact(node, text)) {
        return {
          disposition: "summarized",
          defense: "compact facts were converted into summary chips; full multiline prose stays hidden in the DOM for copy/test access",
        };
      }
      if (proseBoxIsRawArtifact(node, text)) {
        return {
          disposition: "defended",
          defense: "raw operator artifact; kept visible because the full text is the inspectable or copyable payload",
        };
      }
      return {
        disposition: "hidden-guidance",
        defense: "explanatory or guardrail prose; hidden because it does not need default visual space",
      };
    }

    function applyProseBoxDispositionToNode(node) {
      if (!proseBoxCandidate(node) || node.dataset?.diagnosticCalloutBody === "true") return;
      const classification = classifyProseBox(node);
      node.dataset.proseBoxDisposition = classification.disposition;
      node.dataset.proseBoxDefense = classification.defense;
      if (classification.disposition === "summarized") {
        renderProseBoxSummary(node, proseBoxText(node));
        node.hidden = true;
        return;
      }
      removeProseBoxSummary(node);
      if (classification.disposition === "defended") {
        node.hidden = false;
        return;
      }
      if (classification.disposition.startsWith("hidden")) {
        node.hidden = true;
      }
    }

    function applyProseBoxDispositions(root = document) {
      if (!root?.querySelectorAll) return;
      root.querySelectorAll(".prose-block, .status-block, .diagnostic-callout").forEach(applyProseBoxDispositionToNode);
    }

    function setText(id, value) {
      const node = byId(id);
      if (!node) return;
      if (shouldRenderDiagnosticCallout(node, value)) {
        if (diagnosticCalloutBodyNode(node) && renderedTextMatches(node, value)) return;
        renderDiagnosticCalloutNode(node, value);
        applyProseBoxDispositionToNode(byId(id));
        return;
      }
      if (renderedTextMatches(node, value)) return;
      resetDiagnosticCalloutNode(node, value);
      applyProseBoxDispositionToNode(node);
    }

    function applyDiagnosticCallouts(root = document) {
      if (!root?.querySelectorAll) return;
      root.querySelectorAll(".prose-block").forEach((node) => {
        if (shouldRenderDiagnosticCallout(node, node.textContent || "")) {
          renderDiagnosticCalloutNode(node, node.textContent || "");
        }
      });
      applyProseBoxDispositions(root);
    }

    function stateFromStatusText(text) {
      const t = String(text || "").trim().toLowerCase();
      if (!t) return "empty";
      if (t === "not loaded" || t === "not selected" || t === "not available"
          || t === "idle" || t === "none" || t === "no rows" || t === "not evaluated"
          || t.startsWith("no ") || t === "unknown") return "empty";
      if (t === "loading" || t === "loading..." || t === "checking"
          || t === "updating" || t === "requesting") return "loading";
      if (t.includes("blocked") || t.includes("failed") || t.includes("error")
          || t === "missing" || t.includes("unavailable")) return "blocked";
      if (t.includes("warning") || t.includes("review") || t === "limited"
          || t === "active work" || t === "active controls") return "warning";
      if (t === "ready" || t === "safe" || t === "ok" || t === "pass"
          || t === "enabled" || t === "aligned" || t.startsWith("ready")
          || t.includes("complete")) return "ok";
      return "";
    }

    function setTextState(id, text, state) {
      setText(id, text);
      const node = byId(id);
      if (!node) return;
      node.dataset.state = state !== undefined ? String(state) : stateFromStatusText(text);
    }

    function selectedRowAtAGlanceLines(options = {}) {
      const item = options.item || null;
      const title = options.title || "Selected row";
      const authority = options.authority || "Authority: this summary is read-only.";
      if (!item) {
        return [
          `${title}: none`,
          options.emptyNextStep || "Next step: select a row to review backend evidence.",
          authority,
        ];
      }
      return [
        `${title}: ${options.label || "(unnamed row)"}`,
        `Trust/status: ${options.trustStatus || "not reported"}; at-a-glance=${options.atAGlanceStatus || "No selection"}`,
        `${options.proofLabel || "Proof"}: ${options.proof || "not reported"}`,
        `Primary concern: ${options.primaryConcern || "no primary concern reported"}`,
        `Safe next step: ${options.safeNextStep || "Review backend evidence before acting."}`,
        `Filter visibility: ${options.filterVisibility || "not evaluated"}`,
        authority,
      ];
    }

    function humanizeReviewFlagToken(value) {
      return String(value || "")
        .replace(/^consistency:/i, "")
        .replace(/^runtime:/i, "")
        .replace(/^runtime_error:/i, "")
        .replace(/^runtime_outcome:/i, "")
        .replace(/^blocked:/i, "")
        .replace(/[_:.-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
    }

    function reviewFlagExplanation(flag) {
      const raw = String(flag || "").trim();
      if (!raw) return "";
      const normalized = raw.toLowerCase();
      const readable = humanizeReviewFlagToken(raw);
      if (/tv_parse|season|episode|parse/.test(normalized)) {
        return `- ${raw}: title/episode parsing is not trusted. Read the blocker, Queue Snapshot, Last Stderr, and Run Logs before launch.`;
      }
      if (/bad_extension|unsupported|codec|format/.test(normalized)) {
        return `- ${raw}: this source or stream may not be supported by the current route. Check route evidence and diagnostics before processing.`;
      }
      if (/already_processed|duplicate/.test(normalized)) {
        return `- ${raw}: backend evidence suggests duplicate work or an existing output. Compare Completed, Pending Publish, and sidecar proof before reprocessing.`;
      }
      if (/missing_output|output_path_missing|output_missing|publish_missing_output/.test(normalized)) {
        return `- ${raw}: expected output proof is missing. Check Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun or cleanup.`;
      }
      if (/missing_sidecar|sidecar/.test(normalized)) {
        return `- ${raw}: sidecar or metadata proof is missing or inconsistent. Inspect sidecar state before cleanup, rerun, library decisions, or output acceptance.`;
      }
      if (/size_growth|growth_over_5|oversize|larger/.test(normalized)) {
        return `- ${raw}: output grew beyond the size-review threshold. Compare route, encoder, settings, and logs before accepting the larger file as intentional.`;
      }
      if (normalized === "runtime_checks_deferred") {
        return `- ${raw}: backend source/output checks run only when processing starts. The queue snapshot cannot prove launch-time file stability yet.`;
      }
      if (normalized.startsWith("runtime_error:")) {
        return `- ${raw}: previous runtime error ${readable || "not reported"} is attached to this row. Read Last Stderr and Latest Failure before retry, rerun, or cleanup.`;
      }
      if (normalized.startsWith("runtime_outcome:")) {
        return `- ${raw}: previous runtime outcome was ${readable || "not reported"}. Treat it as run-history evidence and compare logs before acting.`;
      }
      if (normalized === "runtime_outcome_stale") {
        return `- ${raw}: runtime history is stale. Use it as context only; current disk/log proof still needs review.`;
      }
      if (normalized.startsWith("runtime:")) {
        return `- ${raw}: backend runtime check ${readable || "not reported"} happens at processing time, not from this read-only table view.`;
      }
      if (/remux/.test(normalized)) {
        return `- ${raw}: route/output uses remux. Compare container and stream compatibility proof before trusting that no encode is needed.`;
      }
      if (/encode|encoded/.test(normalized)) {
        return `- ${raw}: route/output uses encode. Compare size, audio, subtitle, and log proof before treating the result as accepted.`;
      }
      if (/blocked/.test(normalized)) {
        return `- ${raw}: backend marked this row blocked or review-only. Resolve the backend reason before launch, rerun, cleanup, or acceptance decisions.`;
      }
      return `- ${raw}: backend review marker "${readable || raw}". Use the row guidance and diagnostics before acting.`;
    }

    function reviewFlagExplanationLines(flags, options = {}) {
      const rawFlags = Array.isArray(flags) ? flags : [flags];
      const title = options.title || "Review flag explanations:";
      const emptyMessage = options.emptyMessage || "No backend review flags were reported for this row.";
      const guardrail = options.guardrail || "Mutation guardrail: these explanations only translate already-loaded backend markers and cannot change queue, output, publish, or file state.";
      const limit = Number(options.limit || 8);
      const seen = new Set();
      const explanations = [];
      rawFlags.forEach((flag) => {
        const raw = String(flag || "").trim();
        if (!raw || seen.has(raw)) return;
        seen.add(raw);
        const explanation = reviewFlagExplanation(raw);
        if (explanation) explanations.push(explanation);
      });
      if (!explanations.length) {
        return [title, emptyMessage, guardrail];
      }
      const visible = limit > 0 ? explanations.slice(0, limit) : explanations;
      const lines = [title, ...visible];
      if (limit > 0 && explanations.length > limit) {
        lines.push(`Additional backend markers: ${explanations.length - limit} not shown here; inspect the raw Review flags line for the full list.`);
      }
      lines.push(guardrail);
      return lines;
    }

    function selectedRowDetailDrawerLines(options = {}) {
      const title = options.title || "Selected row detail";
      const summaryLines = Array.isArray(options.summaryLines) ? options.summaryLines.filter(Boolean) : [];
      const bodyLines = Array.isArray(options.bodyLines) ? options.bodyLines.filter((line) => line !== undefined && line !== null) : [];
      const guardrail = options.guardrail || "Mutation guardrail: selected-row detail is read-only and cannot submit backend commands.";
      const lines = [`${title}:`];
      if (summaryLines.length) {
        lines.push("At a glance:", ...summaryLines);
      } else {
        lines.push("At a glance: no selected-row summary available.");
      }
      if (bodyLines.length) {
        lines.push("", "Detail:", ...bodyLines);
      }
      lines.push("", guardrail);
      return lines.filter((line, index, array) => line !== "" || array[index - 1] !== "");
    }

    function formatRefreshTimestamp(value) {
      if (!value) return "not reported";
      const date = value instanceof Date ? value : new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      try {
        return date.toLocaleString([], {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
      } catch {
        return date.toISOString();
      }
    }

    function payloadRefreshMeta(payload) {
      return payload && typeof payload === "object" && payload.__mediaPipelineRefreshMeta
        ? payload.__mediaPipelineRefreshMeta
        : {};
    }

    function payloadFreshnessLines(options = {}) {
      const payload = options.payload && typeof options.payload === "object" ? options.payload : {};
      const meta = payloadRefreshMeta(payload);
      const label = options.label || "Payload";
      const rowCount = options.rowCount !== undefined
        ? options.rowCount
        : Array.isArray(payload.rows)
          ? payload.rows.length
          : payload.count;
      const refreshAction = options.refreshAction || "Use Refresh to reload backend state.";
      const lines = [
        `${label} refresh: WebView loaded ${formatRefreshTimestamp(meta.fetched_at)}${meta.name ? ` from ${meta.name}` : ""}; rows=${rowCount ?? "not reported"}.`,
      ];
      if (options.artifactLine) lines.push(options.artifactLine);
      if (options.sourceLine) lines.push(options.sourceLine);
      if (options.readError) lines.push(`Read issue: ${options.readError}`);
      lines.push(`Refresh action: ${refreshAction}`);
      return lines;
    }

    function jsonDetailText(options = {}) {
      const label = options.label || "JSON detail";
      const value = options.value;
      const intro = options.intro || "Read-only structured detail. Select this block to copy it for troubleshooting.";
      const guardrail = options.guardrail || "Mutation guardrail: this viewer only formats already-loaded backend data and does not submit commands.";
      const lines = [
        `${label}:`,
        intro,
        guardrail,
      ];
      if (value === undefined || value === null || value === "") {
        lines.push("", options.emptyMessage || "No JSON payload available.");
        return lines.join("\n");
      }
      try {
        lines.push("", "JSON valid: yes", JSON.stringify(value, null, 2));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        lines.push("", "JSON valid: no", `Render error: ${message}`);
      }
      return lines.join("\n");
    }

    function renderJsonDetail(id, options = {}) {
      setText(id, jsonDetailText(options));
    }

    return {
      diagnosticCalloutText,
      isDiagnosticCalloutText,
      shouldRenderDiagnosticCallout,
      ensureDiagnosticCalloutRoot,
      resetDiagnosticCalloutNode,
      renderDiagnosticCalloutNode,
      diagnosticCalloutBodyNode,
      isDiagnosticCalloutRoot,
      renderedTextMatches,
      setText,
      applyDiagnosticCallouts,
      applyProseBoxDispositions,
      applyProseBoxDispositionToNode,
      stateFromStatusText,
      setTextState,
      selectedRowAtAGlanceLines,
      humanizeReviewFlagToken,
      reviewFlagExplanation,
      reviewFlagExplanationLines,
      selectedRowDetailDrawerLines,
      formatRefreshTimestamp,
      payloadRefreshMeta,
      payloadFreshnessLines,
      jsonDetailText,
      renderJsonDetail,
    };
  }

  window.__domTextModule = {
    createDomTextModule,
  };
})();
