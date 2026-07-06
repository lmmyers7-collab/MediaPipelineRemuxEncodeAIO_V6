(function () {
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

  function initBackendRowOpenActions() {
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
        onOpen: (target) => config.onOpen(target),
      });
    });
  }

  window.mediaPipelineAppRowOpenActions = {
    rowOpenActionGroup,
    initBackendRowOpenActions,
  };
})();
