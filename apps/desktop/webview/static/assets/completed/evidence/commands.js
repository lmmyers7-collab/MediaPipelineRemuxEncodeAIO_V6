// completed/evidence/commands.js
// Split child of completedView.evidence.js. Owns read-only command-history evidence helpers.

(function () {
  "use strict";

  function createCompletedEvidenceCommandsModule(deps = {}) {
    const commandHistoryCommandText = deps.commandHistoryCommandText;
    const commandHistoryIssueLevel = deps.commandHistoryIssueLevel;
    const commandHistoryOwnerPage = deps.commandHistoryOwnerPage;
    const getCommandHistory = deps.getCommandHistory;

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

    return {
      completedAcceptanceCommandEntries,
      completedAcceptanceIssueLevel,
    };
  }

  window.__completedViewEvidenceCommandsModule = {
    createCompletedEvidenceCommandsModule,
  };
})();
