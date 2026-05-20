(function () {
  function formatPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "Unavailable";
    return `${Math.round(Number(value))}%`;
  }

  function formatMemoryMb(usedMb, totalMb) {
    const used = Number(usedMb);
    const total = Number(totalMb);
    if (!Number.isFinite(used) || !Number.isFinite(total) || total <= 0) return "";
    return `${(used / 1024).toFixed(1)} / ${(total / 1024).toFixed(1)} GB`;
  }

  function formatProgressValue(value) {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) return value.join(", ");
    if (value && typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function formatConfigValue(value) {
    if (Array.isArray(value)) return value.join(", ");
    if (value && typeof value === "object") return JSON.stringify(value);
    if (value === null || value === undefined) return "";
    return String(value);
  }

  function parseSettingsListText(raw) {
    return String(raw || "")
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function formatSettingsListValue(value) {
    if (Array.isArray(value)) return value.join(", ");
    if (value === undefined || value === null) return "";
    return String(value);
  }

  function normalizedSettingsValue(value) {
    if (Array.isArray(value)) return value.map((item) => String(item));
    if (value && typeof value === "object") return JSON.stringify(value);
    return value;
  }

  function settingsValuesEqual(left, right) {
    return JSON.stringify(normalizedSettingsValue(left)) === JSON.stringify(normalizedSettingsValue(right));
  }

  /**
   * shortenPath(path, maxChars) → shortened string
   *
   * Produces a display-safe path that fits within maxChars by eliding the
   * middle directory segments, preserving the filename (end) and drive root
   * (beginning). Operates on both Windows (backslash) and POSIX (slash) paths.
   *
   * Examples:
   *   shortenPath("D:\\LocalBase\\State\\Pending\\job\\output.mkv", 40)
   *   → "D:\\…\\output.mkv"
   *
   *   shortenPath("/home/user/media/output.mkv", 40)
   *   → "/…/output.mkv"
   *
   * The full path should still be set as td.title for tooltip inspection.
   */
  function shortenPath(path, maxChars) {
    const p = String(path || "");
    const max = Number(maxChars) || 40;
    if (!p || p.length <= max) return p;
    const sep = p.includes("\\") ? "\\" : "/";
    const parts = p.split(sep);
    const filename = parts[parts.length - 1] || "";
    const root = parts[0] !== undefined ? parts[0] : "";
    if (!filename) return p.slice(0, max) + "…";
    const mid = `${sep}…${sep}`;
    if (root.length + mid.length + filename.length <= max) {
      return `${root}${mid}${filename}`;
    }
    // root + mid alone too long — show just filename with leading ellipsis
    return `…${sep}${filename}`;
  }

  /**
   * Public namespace for shared formatting helpers.
   * Prefer this namespace from new code; flat window.* exports are transitional compatibility aliases when present.
   */
  window.mediaPipelineFormatters = {
    formatPercent,
    formatMemoryMb,
    formatProgressValue,
    formatConfigValue,
    parseSettingsListText,
    formatSettingsListValue,
    normalizedSettingsValue,
    settingsValuesEqual,
    shortenPath,
  };
  window.formatPercent = formatPercent;
  window.formatMemoryMb = formatMemoryMb;
  window.formatProgressValue = formatProgressValue;
  window.formatConfigValue = formatConfigValue;
  window.parseSettingsListText = parseSettingsListText;
  window.formatSettingsListValue = formatSettingsListValue;
  window.settingsValuesEqual = settingsValuesEqual;
  window.shortenPath = shortenPath;
})();
