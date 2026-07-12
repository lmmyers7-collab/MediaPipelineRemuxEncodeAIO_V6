/* Pending Publish filter fields and table scroll restoration primitives. */
(function () {
  function createPendingPublishTableSupportModule() {
const PENDING_FILTER_FIELDS = [
      "state",
      "row_key",
      "local_file",
      "server_out",
      "source_path",
      "manifest_path",
      "error",
      "issue_summary",
      "primary_concern",
      "safe_next_action",
      "route",
      "publish_mode",
      "diagnostic_status",
      "diagnostic_severity",
      "drain_recommendation",
      "operator_guidance",
      "operator_trust_state",
    ];

    function clampTableScrollOffset(value, maxValue) {
      const numeric = Number(value);
      const maximum = Math.max(0, Number(maxValue) || 0);
      return Math.min(Math.max(0, Number.isFinite(numeric) ? numeric : 0), maximum);
    }

    function tableScrollSnapshot(tbody) {
      const target = tbody?.closest?.(".table-wrap") || null;
      if (!target) return null;
      return {
        target,
        top: target.scrollTop,
        left: target.scrollLeft,
      };
    }

    function restoreTableScrollSnapshot(snapshot) {
      const target = snapshot?.target;
      if (!target || target.isConnected === false) return;
      target.scrollTop = clampTableScrollOffset(snapshot.top, target.scrollHeight - target.clientHeight);
      target.scrollLeft = clampTableScrollOffset(snapshot.left, target.scrollWidth - target.clientWidth);
    }

    function deferTableScrollRestore(snapshot) {
      if (!snapshot) return;
      const schedule = typeof window.requestAnimationFrame === "function"
        ? window.requestAnimationFrame.bind(window)
        : (fn) => window.setTimeout(fn, 0);
      restoreTableScrollSnapshot(snapshot);
      schedule(() => {
        restoreTableScrollSnapshot(snapshot);
        schedule(() => restoreTableScrollSnapshot(snapshot));
        window.setTimeout(() => restoreTableScrollSnapshot(snapshot), 0);
      });
    }
    return { PENDING_FILTER_FIELDS, clampTableScrollOffset, tableScrollSnapshot, restoreTableScrollSnapshot, deferTableScrollRestore };
  }
  window.__pendingPublishTableSupportModule = { createPendingPublishTableSupportModule };
})();
