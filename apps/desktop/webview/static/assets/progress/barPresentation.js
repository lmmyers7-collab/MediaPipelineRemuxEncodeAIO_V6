(function () {
  function createProgressBarPresentationModule({
    formatEtaSeconds,
    progressEtaRows,
    progressBarId,
    progressBarMode,
    progressBarPercent,
    progressBarPercentLabel,
    progressBarStatus,
    progressBarStatusLabel,
    progressUsePendingDrainCompactText,
    progressBarDisplayLabel,
    progressStepDisplayLabel,
    formatProgressUpdatedAt,
  } = {}) {
      function progressTimelineGroupKey(bar) {
        const id = progressBarId(bar);
        const source = String(bar?.source || "").toLowerCase();
        const label = String(bar?.label || "").toLowerCase();
        if (id === "operator_stop") return "primary";
        if (id === "current_stage" || id === "run_total") return "primary";
        if (id === "publish_copy" && progressBarStatus(bar) === "active") return "primary";
        if (id === "audio_track" || label.includes("audio")) return "audio";
        if (id === "publish_output" || id === "publish_copy" || id === "pending_drain") return "publish";
        if (id.startsWith("subtitle") || label.includes("subtitle")) return "subtitles";
        if (progressBarStatus(bar) === "complete" && (id === "audit_progress" || id === "audit_reports" || source.includes("audit_progress"))) {
          return "completed";
        }
        return "other";
      }

      function compactProgressUpdatedAt(value) {
        const full = formatProgressUpdatedAt(value);
        if (!full) return null;
        const match = full.match(/^\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2}(?::\d{2})?)$/);
        return {
          text: `updated ${match ? match[1] : full}`,
          title: `updated: ${full}`,
        };
      }

      function progressTimelineSortRank(bar) {
        const id = progressBarId(bar);
        if (id === "operator_stop") return 0;
        if (id === "publish_copy" && progressBarStatus(bar) === "active") return 0;
        if (id === "current_stage") return 10;
        if (id === "run_total") return 20;
        if (id === "audio_track") return 25;
        if (id === "pending_drain") return 30;
        if (id === "publish_output") return 35;
        if (id === "publish_copy") return 40;
        return 100;
      }

      function sortedProgressTimelineBars(bars) {
        return [...bars].sort((left, right) => {
          const rankDelta = progressTimelineSortRank(left) - progressTimelineSortRank(right);
          if (rankDelta) return rankDelta;
          return String(left?.label || left?.id || "").localeCompare(String(right?.label || right?.id || ""));
        });
      }

      function formatProgressBytes(value) {
        const bytes = Number(value);
        if (!Number.isFinite(bytes) || bytes < 0) return "";
        const units = ["B", "KB", "MB", "GB", "TB"];
        let size = bytes;
        for (const unit of units) {
          if (size < 1024 || unit === units[units.length - 1]) {
            return unit === "B" ? `${Math.round(size)} ${unit}` : `${size.toFixed(1)} ${unit}`;
          }
          size /= 1024;
        }
        return `${Math.round(bytes)} B`;
      }

      function formatProgressByteRate(value) {
        const text = formatProgressBytes(value);
        return text ? `${text}/s` : "";
      }

      function progressEtaRowForBar(bar, snapshot = null, diagnostics = null) {
        const id = progressBarId(bar);
        if (!id) return null;
        const rows = progressEtaRows(snapshot, diagnostics);
        return rows.find((row) => String(row?.worker_id || "").toLowerCase() === id)
          || (id === "publish_copy"
            ? rows.find((row) => String(row?.progress_source || "").toLowerCase() === "pipeline_progress.json")
            : null)
          || null;
      }

      function progressEtaTokensForBar(bar, snapshot = null, diagnostics = null) {
        const row = progressEtaRowForBar(bar, snapshot, diagnostics);
        if (!row) return [];
        const tokens = [];
        if (row.eta_seconds !== undefined && row.eta_seconds !== null) {
          tokens.push({ kind: "eta", text: `eta ${formatEtaSeconds(row.eta_seconds)}`, title: row.basis || "" });
        } else if (row.unavailable_reason) {
          tokens.push({ kind: "eta", text: "ETA unavailable", title: row.unavailable_reason });
        }
        const rate = formatProgressByteRate(row.bytes_per_second);
        if (rate) tokens.push({ kind: "rate", text: `write ${rate}` });
        const remaining = formatProgressBytes(row.bytes_remaining);
        if (remaining) tokens.push({ kind: "eta", text: `remaining ${remaining}` });
        if (row.confidence) tokens.push({ kind: "source", text: `confidence: ${row.confidence}` });
        return tokens;
      }

      function progressBarDetailTextParts(bar) {
        return String(bar?.detail || "")
          .split(/\s*\|\s*/)
          .map((part) => part.trim())
          .filter(Boolean);
      }

      function progressCompactFractionText(text, noun) {
        const match = String(text || "").trim().match(/^(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)(?:\s+(.+))?$/);
        if (!match) return "";
        return `${match[1]} of ${match[2]} ${noun || match[3] || ""}`.trim();
      }

      function progressCompactPrefixedCount(text, prefix, suffix) {
        const match = String(text || "").trim().match(/^(\S+)\s+(\d+(?:\.\d+)?)$/);
        if (!match || match[1].toLowerCase() !== String(prefix || "").toLowerCase()) return "";
        return `${match[2]} ${suffix}`;
      }

      function progressCompactPendingDrainDetailPieces(bar, snapshot = null, diagnostics = null) {
        const id = progressBarId(bar);
        const detailParts = progressBarDetailTextParts(bar);
        const pieces = [];
        if (id === "publish_output") {
          const count = detailParts.find((part) => /\d+\s*\/\s*\d+\s+publish steps/i.test(part));
          const state = detailParts.find((part) => /^(copying|writing|revealing|finalizing|complete|done|pending)$/i.test(part));
          const compactCount = progressCompactFractionText(String(count || "").replace(/\s+publish steps/i, ""), "steps");
          if (compactCount) pieces.push(compactCount);
          if (state) pieces.push(state);
        } else if (id === "publish_copy") {
          const copied = detailParts.find((part) => /\d+(?:\.\d+)?\s+\w+\s*\/\s*\d+(?:\.\d+)?\s+\w+/i.test(part));
          if (copied) pieces.push(copied.replace(/\s*\/\s*/, " of "));
          const etaTokens = progressEtaTokensForBar(bar, snapshot, diagnostics).map((token) => token.text);
          const eta = etaTokens.find((token) => /^eta\s+/i.test(token));
          const remaining = etaTokens.find((token) => /^remaining\s+/i.test(token));
          if (eta) pieces.push(eta.replace(/^eta\s+/i, "ETA "));
          if (remaining) pieces.push(`${remaining.replace(/^remaining\s+/i, "")} left`);
        } else if (id === "pending_drain") {
          const count = detailParts.find((part) => /\d+\s*\/\s*\d+\s+manifests?/i.test(part));
          const compactCount = progressCompactFractionText(String(count || "").replace(/\s+manifests?/i, ""), "manifests");
          const succeeded = detailParts.map((part) => progressCompactPrefixedCount(part, "succeeded", "done")).find(Boolean);
          const remaining = detailParts.map((part) => progressCompactPrefixedCount(part, "remaining", "left")).find(Boolean);
          const errors = detailParts.map((part) => progressCompactPrefixedCount(part, "errors", "errors")).find(Boolean);
          const skipped = detailParts.map((part) => progressCompactPrefixedCount(part, "skipped", "skipped")).find(Boolean);
          if (compactCount) pieces.push(compactCount);
          if (succeeded) pieces.push(succeeded);
          if (remaining) pieces.push(remaining);
          if (errors) pieces.push(errors);
          if (skipped) pieces.push(skipped);
        }
        if (!pieces.length && detailParts.length) pieces.push(detailParts[0]);
        if (bar?.stale) pieces.push("review");
        return pieces;
      }

      function progressBarDetailPieces(bar, snapshot = null, diagnostics = null, options = {}) {
        if (progressUsePendingDrainCompactText(options)) {
          return progressCompactPendingDrainDetailPieces(bar, snapshot, diagnostics);
        }
        const etaTokens = progressEtaTokensForBar(bar, snapshot, diagnostics).map((token) => token.text);
        return [
          bar.detail,
          ...etaTokens,
          bar.source ? `source: ${bar.source}` : "",
          bar.updated_at ? `updated: ${formatProgressUpdatedAt(bar.updated_at)}` : "",
          bar.stale ? "stale/review" : "",
        ].filter(Boolean);
      }

      function progressTimelineTokens(bar, snapshot = null, diagnostics = null) {
        const tokens = [];
        String(bar?.detail || "")
          .split(/\s*\|\s*/)
          .map((part) => part.trim())
          .filter(Boolean)
          .forEach((part) => tokens.push({ kind: "detail", text: part }));
        tokens.push(...progressEtaTokensForBar(bar, snapshot, diagnostics));
        if (bar?.source) tokens.push({ kind: "source", text: `source: ${bar.source}` });
        const updated = compactProgressUpdatedAt(bar?.updated_at);
        if (updated) tokens.push({ kind: "updated", text: updated.text, title: updated.title });
        if (bar?.stale) tokens.push({ kind: "stale", text: "stale/review" });
        if (!tokens.length) tokens.push({ kind: "empty", text: "No progress detail reported." });
        return tokens;
      }

      function createProgressTrack(bar) {
        const mode = progressBarMode(bar);
        const track = document.createElement("div");
        track.className = "progress-track progress-timeline-track";
        track.setAttribute("role", "progressbar");
        track.setAttribute("aria-label", bar?.label || bar?.id || "Progress");
        track.setAttribute("aria-valuetext", progressBarStatusLabel(bar));
        if (mode === "determinate" || mode === "stepped") {
          const percent = progressBarPercent(bar);
          track.setAttribute("aria-valuemin", "0");
          track.setAttribute("aria-valuemax", "100");
          track.setAttribute("aria-valuenow", String(Math.round(percent)));
        }
        const fill = document.createElement("div");
        fill.className = "progress-fill";
        if (mode !== "indeterminate") fill.style.width = `${progressBarPercent(bar)}%`;
        track.appendChild(fill);
        return track;
      }

      function progressStepItems(bar, options = {}) {
        const steps = Array.isArray(bar?.steps) ? bar.steps.filter(Boolean) : [];
        return steps.map((step) => ({
          id: String(step?.id || ""),
          label: progressStepDisplayLabel(step, options),
          status: String(step?.status || "pending").toLowerCase(),
        }));
      }

      function createProgressStepList(bar, options = {}) {
        const steps = progressStepItems(bar, options);
        if (!steps.length) return null;
        const list = document.createElement("div");
        list.className = "progress-step-list";
        list.setAttribute("aria-label", `${progressBarDisplayLabel(bar, options)} steps`);
        steps.forEach((step, index) => {
          const item = document.createElement("span");
          item.className = "progress-step";
          item.dataset.status = step.status;
          item.textContent = step.label;
          item.title = `${index + 1}. ${step.label}: ${step.status}`;
          list.appendChild(item);
        });
        return list;
      }

      function renderHomeProgressTimelineRow(bar, snapshot = null) {
        const status = progressBarStatus(bar);
        const mode = progressBarMode(bar);
        const row = document.createElement("div");
        row.className = "progress-timeline-row";
        row.dataset.status = status;
        row.dataset.mode = mode;
        row.dataset.group = progressTimelineGroupKey(bar);

        const badge = document.createElement("div");
        badge.className = "progress-timeline-badge";
        badge.textContent = progressBarPercentLabel(bar);
        badge.title = progressBarStatusLabel(bar);

        const body = document.createElement("div");
        body.className = "progress-timeline-body";

        const header = document.createElement("div");
        header.className = "progress-timeline-header";
        const label = document.createElement("span");
        label.className = "progress-timeline-label";
        label.textContent = bar?.label || bar?.id || "Progress";
        const statusChip = document.createElement("span");
        statusChip.className = "progress-timeline-status";
        statusChip.textContent = status;
        header.append(label, statusChip);

        const metadata = document.createElement("div");
        metadata.className = "progress-timeline-metadata";
        progressTimelineTokens(bar, snapshot).forEach((token) => {
          const item = document.createElement("span");
          item.className = `progress-timeline-token progress-timeline-token-${token.kind}`;
          item.textContent = token.text;
          if (token.title) item.title = token.title;
          metadata.appendChild(item);
        });

        const steps = createProgressStepList(bar);
        body.append(header, createProgressTrack(bar));
        if (steps) body.appendChild(steps);
        body.appendChild(metadata);
        row.append(badge, body);
        return row;
      }

    return {
      progressTimelineGroupKey,
      compactProgressUpdatedAt,
      progressTimelineSortRank,
      sortedProgressTimelineBars,
      formatProgressBytes,
      formatProgressByteRate,
      progressEtaRowForBar,
      progressEtaTokensForBar,
      progressBarDetailPieces,
      progressTimelineTokens,
      createProgressTrack,
      progressStepItems,
      createProgressStepList,
      renderHomeProgressTimelineRow,
    };
  }

  window.__progressBarPresentationModule = { createProgressBarPresentationModule };
})();
