// dom/table.js
// Split child of domHelpers.js. Owns shared table primitives, row selection, scroll preservation, and open-target action group rendering.

/* eslint-disable max-lines-per-function */
(function () {
  "use strict";

  function createDomTableModule(deps = {}) {
    const byId = typeof deps.byId === "function" ? deps.byId : () => null;
    const DOCUMENT_SCROLL_TOLERANCE = 2;

    function clearRows(tbody, columns, message) {
      if (!tbody) return;
      tbody.replaceChildren();
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = columns;
      cell.textContent = message;
      row.appendChild(cell);
      tbody.appendChild(row);
    }

    function appendCells(row, values, cellClasses) {
      values.forEach((value, i) => {
        const cell = document.createElement("td");
        cell.textContent = value === null || value === undefined ? "" : String(value);
        if (cellClasses && cellClasses[i]) cell.className = cellClasses[i];
        row.appendChild(cell);
      });
    }

    function deferDomWork(fn) {
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(fn);
      } else {
        window.setTimeout(fn, 0);
      }
    }

    function documentScrollElement() {
      return document.scrollingElement || document.documentElement || document.body || null;
    }

    function maxScrollableTop(node) {
      return Math.max(0, (Number(node?.scrollHeight) || 0) - (Number(node?.clientHeight) || 0));
    }

    function maxScrollableLeft(node) {
      return Math.max(0, (Number(node?.scrollWidth) || 0) - (Number(node?.clientWidth) || 0));
    }

    function scrollElementAllowsUserScroll(node) {
      if (!node) return false;
      if (node.scrollTop > 0 || node.scrollLeft > 0) return true;
      if (typeof window.getComputedStyle !== "function") return true;
      const style = window.getComputedStyle(node);
      if (!style || style.display === "none" || style.visibility === "hidden") return false;
      const values = [style.overflow, style.overflowX, style.overflowY]
        .map((value) => String(value || "").toLowerCase());
      return values.some((value) => value === "auto" || value === "scroll" || value === "overlay");
    }

    function isScrollableElement(node) {
      if (!node) return false;
      const top = Number(node.scrollTop) || 0;
      const left = Number(node.scrollLeft) || 0;
      const maxTop = maxScrollableTop(node);
      const maxLeft = maxScrollableLeft(node);
      return (top > 0 || left > 0 || maxTop > 1 || maxLeft > 1) && scrollElementAllowsUserScroll(node);
    }

    function siblingElementIndex(node) {
      const siblings = Array.from(node?.parentElement?.children || []);
      const index = siblings.indexOf(node);
      return index >= 0 ? index : 0;
    }

    function scrollElementKey(node, index) {
      if (!node) return `missing:${index}`;
      if (node === documentScrollElement() || node === document.documentElement || node === document.body) return "document";
      if (node.id) return `id:${node.id}`;
      if (node.dataset?.scrollPreserveKey) return `scroll-key:${node.dataset.scrollPreserveKey}`;
      const page = node.closest?.("[data-page-panel]")?.dataset?.pagePanel || "";
      const panel = node.closest?.("[data-panel-key]")?.dataset?.panelKey || "";
      const tag = String(node.tagName || "element").toLowerCase();
      const className = String(node.className || "").replace(/\s+/g, ".").slice(0, 80);
      return `path:${page}:${panel}:${tag}:${className}:${siblingElementIndex(node)}:${index}`;
    }

    function captureScrollablePositions(root = document) {
      const entries = [];
      const seen = new Set();
      const addEntry = (node, options = {}) => {
        if (!node || seen.has(node)) return;
        if (!options.force && !isScrollableElement(node)) return;
        seen.add(node);
        entries.push({
          key: scrollElementKey(node, entries.length),
          isDocument: Boolean(options.isDocument),
          node,
          top: Math.max(0, Number(node.scrollTop) || 0),
          left: Math.max(0, Number(node.scrollLeft) || 0),
          maxTop: maxScrollableTop(node),
          maxLeft: maxScrollableLeft(node),
        });
      };
      addEntry(documentScrollElement(), { force: true, isDocument: true });
      if (root?.querySelectorAll) {
        root.querySelectorAll("*").forEach((node) => addEntry(node));
      }
      return { entries };
    }

    function scrollNodeForEntry(entry) {
      if (!entry) return null;
      if (entry.isDocument || entry.key === "document") return documentScrollElement();
      if (entry.node && entry.node.isConnected !== false) return entry.node;
      if (String(entry.key || "").startsWith("id:")) return byId(String(entry.key).slice(3));
      return null;
    }

    function documentScrollMovedAfterRestore(node, entry, restoreState) {
      const lastDocumentPositions = restoreState?.lastDocumentPositions;
      if (!lastDocumentPositions) return false;
      const key = entry.key || "document";
      const last = lastDocumentPositions.get(key);
      if (!last) return false;
      const top = Math.max(0, Number(node.scrollTop) || 0);
      const left = Math.max(0, Number(node.scrollLeft) || 0);
      return Math.abs(top - last.top) > DOCUMENT_SCROLL_TOLERANCE
        || Math.abs(left - last.left) > DOCUMENT_SCROLL_TOLERANCE;
    }

    function documentScrollRestoreWouldClampToEdge(entry, maxTop, maxLeft) {
      const requestedTop = Math.max(0, Number(entry.top) || 0);
      const requestedLeft = Math.max(0, Number(entry.left) || 0);
      return requestedTop > maxTop + DOCUMENT_SCROLL_TOLERANCE
        || requestedLeft > maxLeft + DOCUMENT_SCROLL_TOLERANCE;
    }

    function rememberDocumentScrollRestore(entry, top, left, restoreState) {
      const lastDocumentPositions = restoreState?.lastDocumentPositions;
      if (!lastDocumentPositions) return;
      lastDocumentPositions.set(entry.key || "document", { top, left });
    }

    function restoreScrollEntry(entry, restoreState = null) {
      const node = scrollNodeForEntry(entry);
      if (!node) return;
      const maxTop = maxScrollableTop(node);
      const maxLeft = maxScrollableLeft(node);
      const requestedTop = Math.max(0, Number(entry.top) || 0);
      const requestedLeft = Math.max(0, Number(entry.left) || 0);
      const top = Math.min(requestedTop, maxTop);
      const left = Math.min(requestedLeft, maxLeft);
      if (entry.isDocument || entry.key === "document") {
        if (documentScrollMovedAfterRestore(node, entry, restoreState)) return;
        if (documentScrollRestoreWouldClampToEdge(entry, maxTop, maxLeft)) return;
        if (typeof window.scrollTo === "function") {
          window.scrollTo(left, top);
        }
        node.scrollTop = top;
        node.scrollLeft = left;
        rememberDocumentScrollRestore(entry, top, left, restoreState);
        return;
      }
      node.scrollTop = top;
      node.scrollLeft = left;
    }

    function restoreScrollEntries(entries, restoreState) {
      entries.forEach((entry) => restoreScrollEntry(entry, restoreState));
    }

    function restoreScrollablePositions(snapshot) {
      const entries = Array.isArray(snapshot?.entries) ? snapshot.entries : [];
      if (!entries.length) return;
      const restoreState = { lastDocumentPositions: new Map() };
      const apply = () => restoreScrollEntries(entries, restoreState);
      apply();
      deferDomWork(() => {
        apply();
        deferDomWork(apply);
        window.setTimeout(apply, 0);
      });
    }

    function scrollSelectedRowIntoView(row) {
      if (!row || !row.classList.contains("is-selected")) return;
      deferDomWork(() => {
        try {
          row.scrollIntoView({ block: "nearest", inline: "nearest" });
        } catch (_) {
          row.scrollIntoView(false);
        }
      });
    }

    function selectableRowsFor(row) {
      const tbody = row?.closest ? row.closest("tbody") : null;
      if (!tbody) return [];
      return Array.from(tbody.querySelectorAll('tr[data-selectable-row="true"]'));
    }

    function focusRowWithoutDocumentScroll(row) {
      if (typeof row?.focus !== "function") return;
      try {
        row.focus({ preventScroll: true });
      } catch (_) {
        row.focus();
      }
    }

    function moveSelectableRowFocus(row, delta) {
      const rows = selectableRowsFor(row);
      const index = rows.indexOf(row);
      const next = rows[index + delta];
      if (!next) return;
      focusRowWithoutDocumentScroll(next);
      next.click();
    }

    function makeRowSelectable(row, onSelect, options = {}) {
      if (!row) return;
      const selected = Boolean(options.selected);
      row.dataset.selectableRow = "true";
      row.tabIndex = 0;
      row.setAttribute("role", "row");
      row.setAttribute("aria-selected", selected ? "true" : "false");
      row.classList.toggle("is-selected", selected);
      if (options.label) row.setAttribute("aria-label", options.label);
      row.addEventListener("click", (event) => onSelect(event));
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(event);
        } else if (event.key === "ArrowDown") {
          event.preventDefault();
          moveSelectableRowFocus(row, 1);
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          moveSelectableRowFocus(row, -1);
        }
      });
      if (options.scrollOnRender === true) {
        scrollSelectedRowIntoView(row);
      }
    }

    function setOptionalDataset(node, key, value) {
      if (!node || !key) return;
      node.dataset[key] = value;
    }

    function renderOpenTargetActionGroups(container, groups, options = {}) {
      if (!container) return { readFirst: 0, openNext: 0 };
      if (!options.append) container.replaceChildren();
      const readFirst = Array.isArray(groups?.readFirst) ? groups.readFirst : [];
      const openNext = Array.isArray(groups?.openNext) ? groups.openNext : [];
      const labelFor = typeof options.labelFor === "function" ? options.labelFor : (action) => action?.label || action?.target || "Open target";
      const titleFor = typeof options.titleFor === "function" ? options.titleFor : (action) => action?.hint || "";
      const classFor = typeof options.classFor === "function" ? options.classFor : () => "secondary-button";
      const onTail = typeof options.onTail === "function" ? options.onTail : null;
      const onOpen = typeof options.onOpen === "function" ? options.onOpen : null;
      const groupDataset = options.groupDataset || "";
      const actionDataset = options.actionDataset || "";
      const targetDataset = options.targetDataset || "";
      const emptyLabel = options.emptyLabel || "No allowlisted action";
      const appendGroup = (labelText, actionRows) => {
        if (!actionRows.length) return;
        const label = document.createElement("span");
        label.className = "action-group-label";
        label.textContent = labelText;
        container.appendChild(label);
        actionRows.forEach((action) => {
          const kind = String(action?.kind || "").trim();
          const target = String(action?.target || "").trim();
          const button = document.createElement("button");
          button.className = classFor(action) || "secondary-button";
          button.type = "button";
          button.textContent = labelFor(action);
          button.title = titleFor(action);
          const groupValue = labelText.toLowerCase().replace(/\s+/g, "-");
          button.dataset.openTargetActionGroup = groupValue;
          button.dataset.openTargetAction = kind;
          button.dataset.openTarget = target;
          setOptionalDataset(button, groupDataset, groupValue);
          setOptionalDataset(button, actionDataset, kind);
          setOptionalDataset(button, targetDataset, target);
          if (kind === "tail" && onTail) {
            button.addEventListener("click", () => onTail(target, action));
          } else if (onOpen) {
            button.addEventListener("click", () => onOpen(target, action));
          }
          container.appendChild(button);
        });
      };
      appendGroup("Read first", readFirst);
      appendGroup("Open next", openNext);
      if (!readFirst.length && !openNext.length && options.showEmpty !== false) {
        const button = document.createElement("button");
        button.className = "secondary-button";
        button.type = "button";
        button.textContent = emptyLabel;
        button.disabled = true;
        button.dataset.openTargetAction = "none";
        container.appendChild(button);
      }
      return { readFirst: readFirst.length, openNext: openNext.length };
    }

    return {
      clearRows,
      appendCells,
      deferDomWork,
      documentScrollElement,
      scrollElementAllowsUserScroll,
      isScrollableElement,
      siblingElementIndex,
      scrollElementKey,
      captureScrollablePositions,
      scrollNodeForEntry,
      restoreScrollEntry,
      restoreScrollablePositions,
      scrollSelectedRowIntoView,
      selectableRowsFor,
      moveSelectableRowFocus,
      makeRowSelectable,
      setOptionalDataset,
      renderOpenTargetActionGroups,
    };
  }

  window.__domTableModule = {
    createDomTableModule,
  };
})();
