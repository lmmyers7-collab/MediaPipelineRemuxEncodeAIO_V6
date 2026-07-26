(function () {
  let rowOpenActionEventsBound = false;

  function rowOpenActionGroup(scope) {
    const groups = {
      completed: {
        targetDataset: "openCompleted",
        actions: [
          { kind: "open", target: "play_output_file", label: "Play Output", primary: true, hint: "Play the backend-selected completed output file with the PC default app." },
          { kind: "open", target: "output_folder", label: "Open Output Folder", hint: "Open the backend-selected completed output folder." },
          { kind: "open", target: "sidecar", label: "Open Sidecar", hint: "Open the backend-selected sidecar file." },
          { kind: "open", target: "source_folder", label: "Open Source Folder", hint: "Open the backend-selected source folder." },
        ],
        onOpen: (target) => window.mediaPipelineCompletedView?.requestCompletedOpen?.(target),
      },
      pending: {
        targetDataset: "openPending",
        actions: [
          { kind: "open", target: "play_local_file", label: "Play Parked Output", primary: true, hint: "Play the backend-selected parked output with the PC default app." },
          { kind: "open", target: "manifest", label: "Open Manifest", hint: "Open the backend-selected pending publish manifest." },
          { kind: "open", target: "destination_folder", label: "Open Destination Folder", hint: "Open the backend-selected destination folder." },
          { kind: "open", target: "source_folder", label: "Open Source Folder", hint: "Open the backend-selected source folder." },
        ],
        onOpen: (target) => window.requestPendingPublishOpen?.(target),
      },
      queue: {
        targetDataset: "openQueue",
        actions: [
          { kind: "open", target: "source_file", label: "Open Source", hint: "Open the backend-selected source file." },
          { kind: "open", target: "source_folder", label: "Open Source Folder", hint: "Open the backend-selected source folder." },
          { kind: "open", target: "source_root", label: "Open Source Root", hint: "Open the backend-selected source root." },
        ],
        onOpen: (target) => window.requestQueueOpen?.(target),
      },
      "queue-excluded": {
        targetDataset: "openQueueExcluded",
        actions: [
          { kind: "open", target: "source_file", label: "Open Excluded Source", hint: "Open the backend-selected excluded source file." },
          { kind: "open", target: "source_folder", label: "Open Excluded Folder", hint: "Open the backend-selected excluded source folder." },
          { kind: "open", target: "source_root", label: "Open Excluded Root", hint: "Open the backend-selected excluded source root." },
        ],
        onOpen: (target) => window.requestQueueOpen?.(target, "excluded"),
      },
    };
    return groups[scope] || null;
  }

  function handleBackendRowOpenAction(event) {
    const button = event.target?.closest?.('button[data-open-target-row-action="open"]');
    const container = button?.closest?.("[data-open-target-row-actions]");
    if (!button || !container || button.disabled) return;
    const config = rowOpenActionGroup(container.dataset.openTargetRowActions || "");
    if (!config) return;
    const target = button.dataset[config.targetDataset] || button.dataset.openTarget || "";
    if (target) config.onOpen(target);
  }

  function normalizedAvailableTargets(value) {
    if (Array.isArray(value)) return new Set(value.filter(Boolean).map(String));
    if (value && typeof value === "object") {
      return new Set(
        Object.entries(value)
          .filter(([, enabled]) => enabled !== false)
          .map(([target]) => target)
      );
    }
    return new Set();
  }

  function rowOpenActionButtons(scope) {
    return Array.from(document.querySelectorAll("[data-open-target-row-actions]"))
      .filter((container) => container.dataset.openTargetRowActions === scope)
      .flatMap((container) => Array.from(container.querySelectorAll('button[data-open-target-row-action="open"]')));
  }

  function applyBackendRowOpenActionState(button) {
    const available = button.dataset.openTargetAvailable === "true";
    const busy = button.dataset.openTargetBusy === "true";
    button.disabled = busy || !available;
    button.setAttribute("aria-disabled", String(button.disabled));
    const baseTitle = button.dataset.openTargetBaseTitle || button.title || "";
    if (!button.dataset.openTargetBaseTitle) button.dataset.openTargetBaseTitle = baseTitle;
    button.title = available
      ? baseTitle
      : [baseTitle, "Unavailable for the selected backend row."].filter(Boolean).join(" ");
  }

  function setBackendRowOpenActionAvailability(scope, availableTargets) {
    const config = rowOpenActionGroup(scope);
    if (!config) return;
    const available = normalizedAvailableTargets(availableTargets);
    rowOpenActionButtons(scope).forEach((button) => {
      const target = button.dataset[config.targetDataset] || button.dataset.openTarget || "";
      button.dataset.openTargetAvailable = available.has(target) ? "true" : "false";
      applyBackendRowOpenActionState(button);
    });
  }

  function setBackendRowOpenActionBusy(scope, isBusy) {
    rowOpenActionButtons(scope).forEach((button) => {
      button.dataset.openTargetBusy = isBusy ? "true" : "false";
      applyBackendRowOpenActionState(button);
    });
  }

  function bindBackendRowOpenActionEvents() {
    if (rowOpenActionEventsBound) return;
    rowOpenActionEventsBound = true;
    document.addEventListener("click", handleBackendRowOpenAction, { capture: true });
  }

  function initBackendRowOpenActions() {
    bindBackendRowOpenActionEvents();
    const renderer = window.mediaPipelineDom?.renderOpenTargetActionGroups;
    document.querySelectorAll("[data-open-target-row-actions]").forEach((container) => {
      const config = rowOpenActionGroup(container.dataset.openTargetRowActions || "");
      if (!container || !config || typeof renderer !== "function") return;
      renderer(container, { readFirst: [], openNext: config.actions }, {
        showEmpty: false,
        labelFor: (action) => action.label || action.target || "Open target",
        titleFor: (action) => action.hint || "",
        classFor: (action) => action.primary ? "primary-button" : "secondary-button",
        groupDataset: "openTargetRowGroup",
        actionDataset: "openTargetRowAction",
        targetDataset: config.targetDataset,
      });
      setBackendRowOpenActionAvailability(container.dataset.openTargetRowActions || "", []);
    });
  }

  window.mediaPipelineAppRowOpenActions = {
    rowOpenActionGroup,
    initBackendRowOpenActions,
    setBackendRowOpenActionAvailability,
    setBackendRowOpenActionBusy,
  };
})();
