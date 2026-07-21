(function () {
  const PICKER_TIMEOUT_MS = 15 * 60 * 1000;

  function byId(id) {
    if (!id || typeof document === "undefined") return null;
    if (typeof window.byId === "function") return window.byId(id);
    return document.getElementById(id);
  }

  function commandHistoryAppend(result) {
    if (typeof window.appendCommandResult === "function") {
      window.appendCommandResult(result);
    } else if (window.mediaPipelineCommandHistory?.appendCommandResult) {
      window.mediaPipelineCommandHistory.appendCommandResult(result);
    }
  }

  function buttonScope(button) {
    return (
      button.closest?.("[data-path-picker-scope]") ||
      button.closest?.("label") ||
      button.closest?.("td") ||
      document
    );
  }

  function inputForButton(button) {
    const reference = String(button.dataset.pathPickerInput || "").trim();
    if (!reference) return null;
    if (/^[A-Za-z][A-Za-z0-9_.:-]*$/.test(reference)) {
      return byId(reference);
    }
    if (reference.startsWith("#")) {
      return document.querySelector(reference);
    }
    const scope = buttonScope(button);
    return scope?.querySelector?.(reference) || document.querySelector(reference);
  }

  function splitListValue(value) {
    return String(value || "")
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function initialPathForInput(input, writeMode) {
    if (!input) return "";
    if (writeMode === "append-list") {
      const values = splitListValue(input.value);
      return values[values.length - 1] || "";
    }
    return String(input.value || "");
  }

  function appendListValue(input, selectedPath) {
    const values = splitListValue(input.value);
    const selectedKey = selectedPath.toLowerCase();
    if (!values.some((value) => value.toLowerCase() === selectedKey)) {
      values.push(selectedPath);
    }
    input.value = values.join(", ");
  }

  function stageSelectedPath(button, input, selectedPath) {
    const writeMode = String(button.dataset.pathPickerWrite || "replace").trim().toLowerCase();
    if (writeMode === "append-list") {
      appendListValue(input, selectedPath);
    } else {
      input.value = selectedPath;
    }
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.dispatchEvent(
      new CustomEvent("path-picker:staged", {
        bubbles: true,
        detail: {
          targetKey: button.dataset.pathPickerTarget || "",
          selectedPath,
          writeMode,
        },
      })
    );
  }

  function statusElement(button) {
    return byId(button.dataset.pathPickerStatus || "");
  }

  function setStatus(button, message) {
    const status = statusElement(button);
    if (status) status.textContent = message;
  }

  function setButtonBusy(button, busy) {
    if (!button.dataset.pathPickerOriginalText) {
      button.dataset.pathPickerOriginalText = button.textContent || "Browse";
    }
    button.disabled = busy;
    button.dataset.pathPickerBusy = busy ? "true" : "false";
    button.textContent = busy ? "..." : button.dataset.pathPickerOriginalText;
  }

  async function browsePath(button) {
    if (button.disabled || button.dataset.pathPickerBusy === "true") return;
    const input = inputForButton(button);
    const targetKey = String(button.dataset.pathPickerTarget || "").trim();
    if (!input || !targetKey) return;
    const selectionMode = String(button.dataset.pathPickerMode || "").trim();
    const writeMode = String(button.dataset.pathPickerWrite || "replace").trim().toLowerCase();
    const payload = {
      target_key: targetKey,
      initial_path: initialPathForInput(input, writeMode),
    };
    if (selectionMode) payload.selection_mode = selectionMode;
    if (button.dataset.pathPickerFilter) payload.file_filter = String(button.dataset.pathPickerFilter);
    setButtonBusy(button, true);
    setStatus(button, "Opening Windows picker...");
    try {
      const apiPost = window.mediaPipelineApi?.apiPost || window.apiPost;
      if (typeof apiPost !== "function") throw new Error("Local API client is unavailable.");
      const result = await apiPost("/api/path-picker/browse", payload, { timeoutMs: PICKER_TIMEOUT_MS });
      commandHistoryAppend(result);
      const data = result?.data && typeof result.data === "object" ? result.data : {};
      const selectedPath = String(data.selected_path || "");
      if (!data.canceled && selectedPath) {
        stageSelectedPath(button, input, selectedPath);
        setStatus(button, result.ok ? "Path staged." : (result?.message || "Path staged; review validation before saving."));
      } else if (data.canceled) {
        setStatus(button, "Picker canceled.");
      } else {
        setStatus(button, result?.message || "Path picker needs review.");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      commandHistoryAppend({
        command: "path_picker.browse",
        ok: false,
        severity: "error",
        message,
      });
      setStatus(button, "Path picker failed.");
    } finally {
      setButtonBusy(button, false);
    }
  }

  function handleDocumentClick(event) {
    const button = event.target?.closest?.("[data-path-picker-target]");
    if (!button) return;
    event.preventDefault();
    browsePath(button);
  }

  if (typeof document !== "undefined") {
    document.addEventListener("click", handleDocumentClick);
  }

  /**
   * Public namespace for backend-owned path picker badge helpers.
   * Prefer window.mediaPipelinePathPicker access for new code; this module
   * intentionally exposes no flat window.* exports.
   */
  window.mediaPipelinePathPicker = {
    browsePath,
    inputForButton,
  };
})();
