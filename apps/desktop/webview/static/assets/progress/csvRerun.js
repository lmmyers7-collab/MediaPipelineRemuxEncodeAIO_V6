(function () {
  function createProgressCsvRerunModule(deps) {
    const { progressWorkerRows } = deps;

  function stdoutTailText(stdoutTail = null) {
    if (typeof stdoutTail === "string") return stdoutTail;
    if (stdoutTail && typeof stdoutTail === "object") return String(stdoutTail.text || "");
    return "";
  }

  function stdoutTailLines(stdoutTail = null) {
    return stdoutTailText(stdoutTail)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  function csvRerunLineMessage(line) {
    const text = String(line || "").trim();
    const match = text.match(/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\[[A-Z]+\]\s*(.*)$/);
    return (match ? match[1] : text).trim();
  }

  function csvRerunLeaf(value) {
    const text = String(value || "").trim().replace(/^["']|["']$/g, "");
    const parts = text.split(/[\\/]/).filter(Boolean);
    return (parts[parts.length - 1] || text || "").trim();
  }

  function csvRerunStageCopy(line) {
    const match = csvRerunLineMessage(line).match(/^STAGE COPY attempt\s+\d+\/\d+:\s*(.+?)\s+->\s+(.+)$/i);
    if (!match) return null;
    return {
      file: csvRerunLeaf(match[1]),
      destination: String(match[2] || "").trim(),
    };
  }

  function csvRerunStagedCopy(line) {
    const match = csvRerunLineMessage(line).match(/^STAGED copy:\s*(.+)$/i);
    return match ? csvRerunLeaf(match[1]) : "";
  }

  function csvRerunPlannedRows(line) {
    const match = csvRerunLineMessage(line).match(/^Rerun CSV rows listed:\s*(\d+);\s*enabled\/planned:\s*(\d+)/i);
    return match ? `${match[2]} enabled / ${match[1]} CSV rows` : "";
  }

  function csvRerunExplicitLine(line) {
    const message = csvRerunLineMessage(line);
    return /^(Rerun CSV rows listed|STAGE COPY attempt|STAGED copy:|CSV rerun workspace:|PLAN \[|PLAN ONLY complete)/i.test(message)
      || /\bCSV\s+rerun\b|\bRerun\s+CSV\b|RerunQueue|RerunWorkspace|RerunParked/i.test(message);
  }

  function csvRerunTerminalLine(line) {
    const message = csvRerunLineMessage(line);
    return /^(PLAN ONLY complete|DRY RUN complete|Rerun batch complete|No CSV rows are executable)\b/i.test(message)
      || /PIPELINE SHUTDOWN CLEANLY|ROUND COMPLETE|Single-pass mode complete/i.test(message)
      || /\b(CSV\s+rerun|Rerun\s+CSV|Rerun batch)\b.*\b(failed|failure|error|aborted)\b/i.test(message)
      || /\bnested pipeline\b.*\bexited with code\s*[1-9]\d*/i.test(message);
  }

  function csvRerunProcessingMessage(line) {
    const message = csvRerunLineMessage(line);
    if (!message) return "";
    if (/^(Rerun CSV rows listed|PLAN |STAGE COPY|STAGED copy|CSV rerun workspace)/i.test(message)) return "";
    if (/\b(nested pipeline|PIPELINE START|ffmpeg|mkvmerge|remux|encode|publish|processing)\b/i.test(message)) return message;
    return "";
  }

  function csvRerunTailEvidence(stdoutTail = null) {
    const lines = stdoutTailLines(stdoutTail);
    const hasExplicitCsvEvidence = lines.some(csvRerunExplicitLine);
    const evidence = {
      hasEvidence: false,
      plannedRows: "",
      currentImport: "",
      lastImported: "",
      processing: "",
      latestLine: "",
    };
    if (!lines.length) return evidence;

    let stageIndex = -1;
    let stagedIndex = -1;
    let processingIndex = -1;
    lines.forEach((line, index) => {
      const plannedRows = csvRerunPlannedRows(line);
      if (plannedRows) evidence.plannedRows = plannedRows;
      const stageCopy = csvRerunStageCopy(line);
      if (stageCopy?.file) {
        stageIndex = index;
        evidence.currentImport = stageCopy.file;
      }
      const stagedCopy = csvRerunStagedCopy(line);
      if (stagedCopy) {
        stagedIndex = index;
        evidence.lastImported = stagedCopy;
      }
      const processing = hasExplicitCsvEvidence ? csvRerunProcessingMessage(line) : "";
      if (processing) {
        processingIndex = index;
        evidence.processing = processing;
      }
    });

    if (stagedIndex >= stageIndex && stagedIndex >= 0) {
      evidence.currentImport = stageIndex >= 0 ? "Waiting for next copy" : "";
    }
    if (!evidence.processing) {
      evidence.processing = stageIndex >= 0 || stagedIndex >= 0
        ? "Not processing yet; importing staged CSV files"
        : "";
    }
    if (processingIndex >= 0 && processingIndex > Math.max(stageIndex, stagedIndex)) {
      evidence.currentImport = "";
    }
    evidence.latestLine = hasExplicitCsvEvidence ? csvRerunLineMessage(lines[lines.length - 1]) : "";
    evidence.hasEvidence = Boolean(hasExplicitCsvEvidence && (
      evidence.plannedRows
      || evidence.currentImport
      || evidence.lastImported
      || evidence.processing
      || evidence.latestLine
    ));
    return evidence;
  }

  function csvRerunWorkerText(row = {}) {
    return [
      row.job_kind,
      row.worker_label,
      row.worker_id,
      row.stage,
      row.status,
      row.status_state,
      row.source,
      row.last_log_line,
    ].map((value) => String(value || "").trim()).filter(Boolean).join(" ");
  }

  function csvRerunWorkerJobKind(row = {}) {
    return String(row.job_kind || row.kind || "").trim().toLowerCase();
  }

  function csvRerunWorkerIsActive(row = {}) {
    const status = [
      row.status_state,
      row.status,
      row.stage,
    ].map((value) => String(value || "").trim().toLowerCase()).join(" ");
    return /\b(running|active|warning|copying|staging|import|processing|remux|encode|publish)\b/.test(status);
  }

  function csvRerunActivePipelineWorkerPresent(rows = []) {
    return rows.some((row) => {
      const kind = csvRerunWorkerJobKind(row);
      const label = String(row.worker_label || "").trim().toLowerCase();
      return (kind === "pipeline" || label === "local pipeline") && csvRerunWorkerIsActive(row);
    });
  }

  function csvRerunWorkerLooksRelevant(row = {}) {
    const kind = csvRerunWorkerJobKind(row);
    if (kind === "rerun_csv" || kind === "csv_rerun") return true;
    if (kind === "pipeline" || String(row.worker_label || "").trim().toLowerCase() === "local pipeline") return false;
    return /\b(csv|rerun)\b|RerunQueue|STAGE COPY|STAGED copy|Rerun CSV/i.test(csvRerunWorkerText(row));
  }

  function csvRerunWorkerLooksActive(row = {}) {
    const lastLine = String(row.last_log_line || "");
    return /STAGE COPY|STAGED copy|Rerun CSV rows listed|CSV rerun workspace/i.test(lastLine)
      || csvRerunWorkerIsActive(row);
  }

  function csvRerunWorkerEvidence(context = {}) {
    const snapshot = context?.snapshot && typeof context.snapshot === "object" ? context.snapshot : null;
    const diagnostics = context?.diagnostics && typeof context.diagnostics === "object" ? context.diagnostics : null;
    const rows = progressWorkerRows(snapshot, diagnostics).filter(csvRerunWorkerLooksRelevant);
    const activeRow = rows.find(csvRerunWorkerLooksActive) || rows[0] || null;
    const lineText = rows.map((row) => row.last_log_line).filter(Boolean).join("\n");
    const lineEvidence = csvRerunTailEvidence({ text: lineText });
    const sourceLeaf = csvRerunLeaf(activeRow?.source || "");
    return {
      ...lineEvidence,
      hasWorkerEvidence: rows.length > 0,
      workerActive: rows.some(csvRerunWorkerLooksActive),
      currentImport: lineEvidence.currentImport || (csvRerunWorkerLooksActive(activeRow || {}) ? sourceLeaf : ""),
      latestLine: lineEvidence.latestLine || String(activeRow?.last_log_line || "").trim(),
    };
  }

  function csvRerunActivityEvidence(context = {}) {
    const source = context && typeof context === "object" && ("stdoutTail" in context || "snapshot" in context || "diagnostics" in context)
      ? context
      : { stdoutTail: context };
    const tail = csvRerunTailEvidence(source.stdoutTail);
    const allWorkerRows = progressWorkerRows(source.snapshot, source.diagnostics);
    const worker = csvRerunWorkerEvidence(source);
    const activePipelineWorker = csvRerunActivePipelineWorkerPresent(allWorkerRows);
    const tailAllowed = Boolean(tail.hasEvidence && (!activePipelineWorker || worker.hasWorkerEvidence));
    const isActive = Boolean(worker.workerActive)
      || (tailAllowed && !csvRerunTerminalLine(tail.latestLine || ""));
    return {
      hasEvidence: Boolean(tailAllowed || worker.hasEvidence || worker.hasWorkerEvidence),
      plannedRows: tail.plannedRows || worker.plannedRows || "",
      currentImport: tail.currentImport || worker.currentImport || "",
      lastImported: tail.lastImported || worker.lastImported || "",
      processing: tail.processing || worker.processing || "",
      latestLine: worker.latestLine || tail.latestLine || "",
      hasWorkerEvidence: Boolean(worker.hasWorkerEvidence),
      workerActive: Boolean(worker.workerActive),
      tailSuppressedByPipelineWorker: Boolean(tail.hasEvidence && activePipelineWorker && !worker.hasWorkerEvidence),
      isActive,
    };
  }

  function csvRerunActiveFile(evidence = {}) {
    const current = String(evidence.currentImport || "").trim();
    if (!current || /^waiting for next copy$/i.test(current)) return "";
    return current;
  }

  function csvRerunCompactEventLine(line) {
    const raw = String(line || "").trim();
    if (!raw) return "";
    const time = raw.match(/^\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2}:\d{2})\b/)?.[1] || "";
    let message = csvRerunLineMessage(raw).replace(/\s+/g, " ").replace(/\s*\.\.\.$/, "").trim();
    const statusMatch = message.match(/^(ENCODE|REMUX|PUBLISH|COPY|STAGE COPY|FFMPEG)\s*:?\s*(.+)$/i);
    if (statusMatch) {
      const label = statusMatch[1].toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
      message = `${label} ${statusMatch[2]}`.trim();
    }
    if (/^Not processing yet; importing staged CSV files$/i.test(message)) message = "Importing staged files";
    return [time, message].filter(Boolean).join(" ");
  }

  function csvRerunTimelineWaitLine(evidence = {}, backendWorkEvidence = "") {
    const activeFile = csvRerunActiveFile(evidence);
    if (activeFile) return "Importing staged source";
    const activityText = [
      backendWorkEvidence,
      evidence.processing,
      evidence.latestLine,
    ].map((value) => String(value || "").toLowerCase()).join(" ");
    if (/\bencode|transcode|ffmpeg\b/.test(activityText)) return "Waiting for encode to finish";
    if (/\bremux|mkvmerge\b/.test(activityText)) return "Waiting for remux to finish";
    if (/\bpublish|park|sidecar|pending\b/.test(activityText)) return "Waiting for output placement";
    if (/\bnested pipeline\b/.test(activityText)) return "Waiting for nested pipeline";
    if (evidence.isActive) return "Waiting for next CSV item";
    if (evidence.latestLine && csvRerunTerminalLine(evidence.latestLine)) {
      const terminalText = csvRerunLineMessage(evidence.latestLine).toLowerCase();
      return /\b(failed|failure|error|aborted|exited with code\s*[1-9]\d*)\b/.test(terminalText)
        ? "CSV rerun needs review"
        : "CSV rerun complete";
    }
    if (evidence.processing) return csvRerunCompactEventLine(evidence.processing);
    return "";
  }

  function csvRerunTimelineDetail(evidence = {}, backendWorkEvidence = "") {
    const activeFile = csvRerunActiveFile(evidence);
    const primary = evidence.lastImported
      ? `Loaded ${evidence.lastImported}`
      : activeFile
        ? `Loading ${activeFile}`
        : evidence.plannedRows
          ? `CSV rows: ${evidence.plannedRows}`
          : "CSV rerun active";
    return [primary, csvRerunTimelineWaitLine(evidence, backendWorkEvidence)].filter(Boolean).join(". ");
  }

  function csvRerunTimelineEvidenceLine(evidence = {}, backendWorkEvidence = "") {
    const event = csvRerunCompactEventLine(evidence.latestLine || backendWorkEvidence || evidence.processing);
    return event ? `Last event: ${event}` : "";
  }

    return {
      csvRerunTailEvidence,
      csvRerunActivityEvidence,
      csvRerunTerminalLine,
      csvRerunTimelineDetail,
      csvRerunTimelineEvidenceLine,
    };
  }

  window.__progressCsvRerunModule = { createProgressCsvRerunModule };
}());
